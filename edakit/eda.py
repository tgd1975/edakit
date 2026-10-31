"""MCP client for easyeda-mcp-pro and helpers around the EasyEDA Pro extension API.

EasyEDA Pro has no CLI and no HTTP API. It is scriptable only through its extension API (DMT_*, SCH_*, PCB_*, LIB_*),
which exists inside the running editor. easyeda-mcp-pro exposes it through a bridge extension:

    Claude Code --stdio--> easyeda-mcp-pro <--WebSocket 127.0.0.1:49620--> bridge extension in EasyEDA Pro
    edakit ------stdio--> easyeda-mcp-pro  (its own server instance, the same bridge connection)

Each edakit command starts its own server through mcp-server.sh and speaks MCP over stdio (JSON-RPC 2.0, one message
per line). It shares the bridge connection with the server of a running Claude Code session; neither disturbs the
other. Every behaviour of the API that cost time to find out is noted where it matters and collected in
handbook/09-easyeda-api.md.
"""

from __future__ import annotations

import base64
import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path

from . import lock
from .design import natural_key

HERE = Path(__file__).resolve().parent
MCP_SERVER = HERE / "easyeda" / "mcp-server.sh"
PROJECT = "current"  # projectId for the MCP tools: the project that is open in EasyEDA
FOCUS_LOST = "获取器件关联的所有引脚失败"  # EasyEDA: "could not read the pins" – typical when another tab is active
# Sheet frame of the system library (LIB_Device.search("Drawing-Symbol")); size and fields are set by label_sheet
FRAME_DEVICE = {"libraryUuid": "0819f05c4eef4c71ace90d822a990e87", "uuid": "754952feec9e48d6afd574513e1ca00b"}


class MCPError(Exception):
    pass


class MCPClient:
    """Minimal MCP client (JSON-RPC 2.0, one message per line over stdio)."""

    def __init__(self, command, verbose=False, env=None, cwd=None, lock_mode="auto"):
        self.verbose = verbose
        self.lock_mode = lock_mode
        self.next_id = 0
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                     encoding="utf-8", bufsize=1, cwd=cwd, env={**os.environ, **(env or {})})
        self.lines = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()
        self._request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "edakit", "version": "0.1"}}, timeout=180)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _pump(self):
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def _send(self, msg):
        if self.verbose:
            print(f"  >> {json.dumps(msg, ensure_ascii=False)[:300]}")
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def _request(self, method, params, timeout):
        self.next_id += 1
        rid = self.next_id
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            try:
                line = self.lines.get(timeout=max(0.1, deadline - time.monotonic()))
            except queue.Empty:
                raise MCPError(f"timeout after {timeout} s: {method}") from None
            if line is None:
                raise MCPError("MCP server exited (check the output of mcp-server.sh)")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") != rid:
                continue  # notifications, logs
            if self.verbose:
                print(f"  << {line.strip()[:300]}")
            if "error" in msg:
                raise MCPError(f"{method}: {msg['error'].get('message', msg['error'])}")
            return msg.get("result", {})

    def call(self, tool, timeout=130, **args):
        if not lock.read_only(tool, args):  # library lookups need no claim (lock.READ_ONLY_TOOLS, READ_ONLY_API)
            lock.claim_for_script(renew=True, mode=self.lock_mode)
        result = self._request("tools/call", {"name": tool, "arguments": args}, timeout)
        if "structuredContent" in result:
            data = result["structuredContent"]
        else:
            text = "".join(c.get("text", "") for c in result.get("content", []))
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = {"text": text}
        if result.get("isError"):
            raise MCPError(f"{tool}: {json.dumps(data, ensure_ascii=False)[:500]}")
        return data

    def call_image(self, tool, timeout=130, **args):
        """Like call, but returns the image of the answer (PNG bytes) – canvas captures send an image block."""
        lock.claim_for_script(renew=True, mode=self.lock_mode)
        result = self._request("tools/call", {"name": tool, "arguments": args}, timeout)
        for c in result.get("content", []):
            if c.get("type") == "image":
                return base64.b64decode(c["data"])
        raise MCPError(f"{tool}: no image ({json.dumps(result.get('structuredContent', result))[:300]})")

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def start(cfg, verbose=False, artifact_dir=None, lock_mode=None):
    """Claim EasyEDA for the calling Claude session and start an own MCP server through mcp-server.sh. `lock_mode="off"`
    claims nothing (edakit doctor); without a project (cfg None) artifact_dir is needed."""
    mode = lock_mode or cfg.lock
    lock.claim_for_script(mode=mode)
    env = {"ARTIFACT_DIR": str(artifact_dir or cfg.artifact("mcp", ".keep").parent),
           "BRIDGE_TIMEOUT_MS": os.environ.get("BRIDGE_TIMEOUT_MS", "120000")}
    return MCPClient(["bash", str(MCP_SERVER)], verbose=verbose, env=env, cwd=cfg.root if cfg else None, lock_mode=mode)


def wait_for_bridge(mcp, seconds=90):
    """A freshly started server needs a few seconds until EasyEDA connects through Auto-Connect."""
    deadline = time.monotonic() + seconds
    hinted = False
    while True:
        if mcp.call("easyeda_bridge_status").get("connected"):
            return True
        if time.monotonic() > deadline:
            print("Bridge not connected – in EasyEDA: MCP Bridge -> Connect (or enable Auto-Connect).")
            return False
        if not hinted:
            print(f"  waiting up to {seconds} s for the bridge (EasyEDA running, project open, Auto-Connect on?) …")
            hinted = True
        time.sleep(2)


def api(mcp, path, *args, timeout=130):
    """Documented EasyEDA API through easyeda_api_call. Read calls need confirmWrite as well."""
    res = mcp.call("easyeda_api_call", path=path, args=list(args), confirmWrite=True, timeout=timeout)
    if not res.get("ok"):
        raise MCPError(f"{path}: {res.get('error')}")
    return res.get("result")


def state(o):
    """Primitives come as {"state": {...}} from getAll, as flat objects elsewhere."""
    return o.get("state", o) if isinstance(o, dict) else {}


def easyeda_memory():
    """Resident memory of the largest EasyEDA process – long runs crashed EasyEDA twice with V8 out-of-memory."""
    try:
        out = subprocess.run(["ps", "-C", "easyeda-pro", "-o", "rss="], capture_output=True, text=True).stdout
        return f"EasyEDA {max(int(x) for x in out.split()) / 1024 ** 2:.2f} GB"
    except (OSError, ValueError):
        return "EasyEDA memory ?"


class Steps:
    """`[x.x min] step n/m: <step>` before each step of a long command, flushed at once – a Monitor on the log shows
    where a run is and since when, and a stalled run shows the step it stalled in. Used by route all, gate, pcb apply,
    silk apply, export and (through Progress) schematic create/layout."""

    def __init__(self, total, out=None, clock=time.monotonic, t0=None):
        self.total, self.n, self.out, self.clock = total, 0, out, clock
        self.t0 = clock() if t0 is None else t0

    def __call__(self, step):
        self.n += 1
        print(f"[{(self.clock() - self.t0) / 60:4.1f} min] step {self.n}/{self.total}: {step}",
              file=self.out or sys.stdout, flush=True)


class Progress:
    """Phase headings with the duration of the previous phase and EasyEDA's memory; with a total the heading is the
    step line of Steps."""

    def __init__(self, total=None):
        self.t0 = self.t = time.monotonic()
        self.title = None
        self.steps = Steps(total, t0=self.t0) if total else None

    def __call__(self, title=None):
        now = time.monotonic()
        if self.title:
            print(f"  ({self.title}: {now - self.t:.1f} s, {easyeda_memory()})")
        self.title, self.t = title, now
        if title and self.steps:
            print()
            self.steps(title)
        elif title:
            print(f"\n[{title}]  (+{(now - self.t0) / 60:.1f} min)")

    def say(self, msg):
        print(f"[{(time.monotonic() - self.t0) / 60:4.1f} min] {msg}", flush=True)


# --- project ------------------------------------------------------------------------------------------------------

def open_project(mcp, cfg, create=False):
    """Make sure the project cfg.project is open. EasyEDA does not list local projects (getAllProjectsUuid is empty),
    so the UUID is remembered as soon as the project was seen open once; after a restart EasyEDA sits on its start
    page (all DMT_* calls return null) and the project is reopened by that UUID."""
    memo = cfg.artifact("easyeda_project.json")
    info = api(mcp, "DMT_Project.getCurrentProjectInfo")
    if info and info.get("friendlyName") == cfg.project:
        memo.write_text(json.dumps({"name": cfg.project, "uuid": info["uuid"]}))
        return info["uuid"]
    uuid = None
    if memo.exists():
        m = json.loads(memo.read_text())
        uuid = m.get("uuid") if m.get("name", cfg.project) == cfg.project else None
    if not uuid:
        for u in api(mcp, "DMT_Project.getAllProjectsUuid") or []:
            pi = api(mcp, "DMT_Project.getProjectInfo", u)
            if pi and pi.get("friendlyName") == cfg.project:
                uuid = u
                break
    if not uuid and create:
        # The desktop client in local mode refuses it ("请求参数path错误", the path parameter) and returns null.
        uuid = api(mcp, "DMT_Project.createProject", cfg.project)
        if not uuid:
            raise MCPError(f"EasyEDA did not create the project '{cfg.project}' (the local desktop client refuses "
                           "createProject) – create it by hand: File → New → Project, named exactly like [project] "
                           "name in edakit.toml, then run the command again")
        print(f"  project '{cfg.project}' created")
    if not uuid:
        raise MCPError(f"project '{cfg.project}' is not open and EasyEDA does not list local projects – open it in "
                       "EasyEDA once (edakit remembers its UUID)")
    print(f"  project {cfg.project} is not open – opening it")
    api(mcp, "DMT_Project.openProject", uuid)
    # Never go on unless the open project is the right one: every step after this writes into whatever is open.
    for _ in range(60):
        info = api(mcp, "DMT_Project.getCurrentProjectInfo")
        if info and info.get("friendlyName") == cfg.project:
            memo.write_text(json.dumps({"name": cfg.project, "uuid": uuid}))
            return uuid
        time.sleep(2)
    raise MCPError(f"project {cfg.project} did not open (open is '{(info or {}).get('friendlyName')}')")


def connect(cfg, verbose=False, wait=90, artifact_dir=None):
    mcp = start(cfg, verbose, artifact_dir)
    if not wait_for_bridge(mcp, wait):
        mcp.close()
        raise SystemExit(1)
    return mcp


# --- schematics ---------------------------------------------------------------------------------------------------

FOCUS = {}  # schematic and page this command writes to


def schematic_name(mcp, uuid):
    """Current name; getAllSchematicsInfo returns names partly stale or lower-case. Right after createSchematic,
    getSchematicInfo throws for a moment (page not initialised yet)."""
    try:
        return (api(mcp, "DMT_Schematic.getSchematicInfo", uuid) or {}).get("name")
    except MCPError:
        return None


def all_schematic_names(mcp):
    return {s["uuid"]: schematic_name(mcp, s["uuid"]) for s in api(mcp, "DMT_Schematic.getAllSchematicsInfo") or []}


def find_pages(mcp, name, wait_s=30):
    """Right after openProject the schematics are listed, but getSchematicInfo answers only a few seconds later –
    wait for the name instead of reporting it missing."""
    for _ in range(max(int(wait_s / 2), 1)):
        for sch in api(mcp, "DMT_Schematic.getAllSchematicsInfo") or []:
            if schematic_name(mcp, sch["uuid"]) == name:
                return sch["uuid"], [p["uuid"] for p in sch.get("page", [])]
        time.sleep(2)
    raise MCPError(f"schematic '{name}' not found")


def ensure_focus(mcp):
    """Our page must be active – another script, a click or EasyEDA itself may switch the tab."""
    sheet = mcp.call("easyeda_schematic_sheet_info")
    if not sheet.get("not_available") and sheet["sheet"].get("parentSchematicUuid") == FOCUS["schematic"]:
        return
    print("  ? focus lost – activating the page again")
    api(mcp, "DMT_EditorControl.openDocument", FOCUS["page"])
    for _ in range(15):
        sheet = mcp.call("easyeda_schematic_sheet_info")
        if not sheet.get("not_available") and sheet["sheet"].get("parentSchematicUuid") == FOCUS["schematic"]:
            return
        time.sleep(1)
    raise MCPError("the page cannot be activated again – is someone working in EasyEDA in parallel? Abort.")


def active_page(mcp):
    """The uuid of the schematic page EasyEDA has active; None when no schematic page is (the PCB, the start page)."""
    sheet = mcp.call("easyeda_schematic_sheet_info")
    return None if sheet.get("not_available") else (sheet.get("sheet") or {}).get("uuid")


def focus_page(mcp, sch_uuid, page_uuid, timeout=200):
    """Open a page and wait until it is active. A large A1 sheet (120 parts) took up to 160 s."""
    api(mcp, "DMT_EditorControl.openDocument", page_uuid)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if active_page(mcp) == page_uuid:
            FOCUS.update(schematic=sch_uuid, page=page_uuid)
            return
        time.sleep(1)
    raise MCPError(f"page {page_uuid} did not become active")


def read_on_page(mcp, sch_uuid, page_uuid, read, tries=3):
    """read() – a tool that answers for the FOCUSED page (the BOM, the page's parts and nets) – on one page of a
    schematic, counted only when the page is still the active one afterwards: EasyEDA switches tabs on its own, and
    with another schematic open (the template, another board's) the answer would be that schematic's. Read again
    otherwise; MCPError after tries."""
    for _ in range(tries):
        focus_page(mcp, sch_uuid, page_uuid)
        out = read()
        if active_page(mcp) == page_uuid:
            return out
        print(f"  ? page {page_uuid} lost the focus while it was read – reading it again")
    raise MCPError(f"page {page_uuid}: another tab became active while it was read, {tries} times – is someone "
                   "working in EasyEDA in parallel?")


def activate_schematic(mcp, uuid):
    """Activate the first page of a schematic; returns the number of pages."""
    for _ in range(15):  # right after copySchematic the copy has no pages for a moment
        pages = (api(mcp, "DMT_Schematic.getSchematicInfo", uuid) or {}).get("page", [])
        if pages:
            break
        time.sleep(1)
    else:
        raise MCPError(f"schematic {uuid} has no pages")
    focus_page(mcp, uuid, pages[0]["uuid"])
    return len(pages)


def batch_write(mcp, ops, chunk=40):
    """easyeda_schematic_batch_write in blocks; each block is atomic, focus checked before each. 100-operation
    blocks crashed EasyEDA once. Returns operationId -> primitive_id."""
    ids = {}
    for i in range(0, len(ops), chunk):
        ensure_focus(mcp)
        res = mcp.call("easyeda_schematic_batch_write", projectId=PROJECT, operations=ops[i:i + chunk],
                       confirmWrite=True, timeout=600)
        if not res.get("success") or not res.get("committed"):
            failed = [r for r in res.get("results", []) if r.get("status") == "failed"] or res
            raise MCPError(f"batch_write rolled back: {json.dumps(failed, ensure_ascii=False)[:1500]}")
        ids.update({r["operation_id"]: r.get("primitive_id") for r in res.get("results", [])})
    return ids


def rename_schematic(mcp, uuid, name):
    """Rename with checks. modifySchematicName renames the ACTIVE schematic, not the one passed by UUID (EasyEDA Pro
    3.2.206), and right after createSchematic it reports true without effect. So: check that `uuid` is active before
    every attempt, compare all names afterwards, never delete anything on a mismatch."""
    before = all_schematic_names(mcp)
    for attempt in range(10):
        sheet = mcp.call("easyeda_schematic_sheet_info")
        if sheet.get("not_available") or sheet["sheet"].get("parentSchematicUuid") != uuid:
            raise MCPError(f"{uuid} is not active before renaming – nothing renamed")
        api(mcp, "DMT_Schematic.modifySchematicName", uuid, name)
        after = all_schematic_names(mcp)
        wrong = {u: n for u, n in after.items() if u != uuid and n != before.get(u)}
        if wrong:
            raise MCPError(f"renaming changed other schematics: {wrong} (before {before}) – check EasyEDA, "
                           "nothing deleted")
        if after.get(uuid) == name:
            time.sleep(3)  # names reach getSchematicInfo only after 1–2 s – check the final state
            final = all_schematic_names(mcp)
            wrong = {u: n for u, n in final.items() if u != uuid and n != before.get(u)}
            if wrong or final.get(uuid) != name:
                raise MCPError(f"names inconsistent after renaming: {final} (before {before}) – nothing deleted")
            return
        time.sleep(1 + attempt)
    raise MCPError(f"schematic {uuid} could not be renamed to '{name}' – not deleted, check EasyEDA")


def verify_nets(mcp, nets, placed):
    """Compare the netlist in EasyEDA with the graph (through the designators). Right after many writes EasyEDA
    sometimes returns an empty netlist (0/88, two minutes later 88/88) – then wait and read again."""
    ref_to_graph = {p["ref"]: d for d, p in placed.items()}
    actual = defaultdict(set)
    for _ in range(10):
        actual = defaultdict(set)
        for net in mcp.call("easyeda_schematic_nets", projectId=PROJECT, scope="focused").get("nets", []):
            for n in net.get("nodes", []):
                d = ref_to_graph.get(n["component_ref"])
                if d:
                    actual[net["net_name"]].add(f"{d}.{n['pin']}")
        if actual or not placed:
            break
        time.sleep(2)
    diffs = 0
    for name, pins in nets.items():
        want = {p for p in pins if p.split(".", 1)[0] in placed}
        have = actual.get(name, set())
        if want != have:
            diffs += 1
            print(f"  ! {name}: missing {sorted(want - have)}, extra {sorted(have - want)}")
    print(f"  {len(nets) - diffs}/{len(nets)} nets match the graph")
    return diffs


def save_if_matching(mcp, diffs, failures=0, pin_problems=0, skipped=0):
    """--save of `schematic create` and `schematic layout`: save the project only when the netlist equals the graph –
    no differing net (an empty netlist on every read counts every net), no failed connection, no symbol pin mismatch,
    no part skipped. Returns 0 (saved) or 2."""
    if diffs or failures or pin_problems or skipped:
        print(f"not saved: {diffs} differing nets, {failures} failed connections, {pin_problems} pin mismatches"
              + (f", {skipped} parts skipped" if skipped else "") + " – fix and run again, or save in EasyEDA by hand")
        return 2
    mcp.call("easyeda_project_save", projectId=PROJECT, confirmWrite=True)
    print("project saved")
    return 0


def ensure_frame(mcp):
    """The title block belongs to the sheet frame, a component of type 'sheet'. Without a frame titleBlockData is
    empty. SCH_PrimitiveComponent.create places the frame at once but never answers – short timeout, then look."""
    if api(mcp, "SCH_PrimitiveComponent.getAll", "sheet"):
        return False
    try:
        mcp.call("easyeda_api_call", path="SCH_PrimitiveComponent.create", args=[FRAME_DEVICE, 0, 0],
                 confirmWrite=True, timeout=10)
    except MCPError:
        pass
    for _ in range(15):
        if api(mcp, "SCH_PrimitiveComponent.getAll", "sheet"):
            return True
        time.sleep(2)
    raise MCPError("sheet frame missing and could not be created")


def label_sheet(mcp, cfg, page_uuid, title, graph_version, extra=None):
    """Page name and title block: company, graph version, 'generated'. The page must be active (the rename API acts
    on the active document). getSchematicPageInfo shows new values only after a while, so there is no read-back."""
    sheet = mcp.call("easyeda_schematic_sheet_info")
    if sheet.get("not_available") or sheet["sheet"].get("uuid") != page_uuid:
        raise MCPError(f"page {page_uuid} is not active – title block unchanged")
    if ensure_frame(mcp):
        print("  sheet frame was missing – created")
    fields = {"Company": cfg.company, "Version": f"graph v{graph_version}", "Drawn": "generated", "Reviewed": "",
              **(extra or {})}
    api(mcp, "DMT_Schematic.modifySchematicPageTitleBlock", page_uuid,
        {k: {"showTitle": None, "showValue": None, "value": str(v)} for k, v in fields.items()})
    api(mcp, "DMT_Schematic.modifySchematicPageName", page_uuid, title)


def list_sheet_parts(mcp):
    comps, offset = [], 0
    while True:
        res = mcp.call("easyeda_schematic_components", projectId=PROJECT, scope="focused", limit=500, offset=offset)
        if res.get("not_available"):
            raise MCPError(f"components not readable: {res.get('error')}")
        comps += res.get("components", [])
        offset += 500
        if offset >= res.get("total", 0):
            return comps


# --- PCB ----------------------------------------------------------------------------------------------------------

def ensure_board(mcp, board):
    """edakit's board = one EasyEDA board named board.name that joins the board schematic (board.schematic) and the PCB
    (board.pcb). A new project comes with one empty default board (Board1: Schematic1 + PCB1); it is renamed once.
    Anything else is left alone – a board is never created or rebuilt behind the user's back."""
    boards = api(mcp, "DMT_Board.getAllBoardsInfo") or []
    mine = [b for b in boards if b.get("name") == board.name]
    if mine:
        sch, pcb = (mine[0].get("schematic") or {}).get("uuid"), (mine[0].get("pcb") or {}).get("name")
        if schematic_name(mcp, sch) != board.schematic or pcb != board.pcb:
            raise MCPError(f"board '{board.name}' joins '{schematic_name(mcp, sch)}' and '{pcb}', edakit.toml says "
                           f"'{board.schematic}' and '{board.pcb}'")
        return
    default = [b for b in boards if b.get("name") == "Board1" and (b.get("pcb") or {}).get("name") == "PCB1"
               and str((b.get("schematic") or {}).get("name", "")).lower() == "schematic1"]
    if len(boards) != 1 or not default:
        raise MCPError(f"no board '{board.name}' in the project (there are: {', '.join(b['name'] for b in boards) or '–'})"
                       f" – create it in EasyEDA with the schematic '{board.schematic}' and the PCB '{board.pcb}'")
    b = default[0]
    api(mcp, "DMT_Board.modifyBoardName", b["name"], board.name)
    api(mcp, "DMT_Pcb.modifyPcbName", b["pcb"]["uuid"], board.pcb)
    activate_schematic(mcp, b["schematic"]["uuid"])
    rename_schematic(mcp, b["schematic"]["uuid"], board.schematic)
    if not [x for x in api(mcp, "DMT_Board.getAllBoardsInfo") or [] if x.get("name") == board.name]:
        raise MCPError(f"renaming the default board to '{board.name}' did not take effect")
    print(f"  default board renamed: Board1 -> {board.name} (schematic {board.schematic}, PCB {board.pcb})")


PCB = {}  # name and uuid of the PCB this command works on


def open_pcb(mcp, name, wait_s=30):
    """Right after openProject, getAllPcbsInfo is empty for a few seconds – wait for the documents to appear."""
    pcbs = {}
    for _ in range(max(int(wait_s / 2), 1)):
        pcbs = {p["name"]: p["uuid"] for p in api(mcp, "DMT_Pcb.getAllPcbsInfo") or []}
        if pcbs:
            break
        time.sleep(2)
    if name not in pcbs:
        raise MCPError(f"PCB '{name}' is not in the project (there are: {', '.join(pcbs) or '–'})")
    PCB.update(name=name, uuid=pcbs[name])
    api(mcp, "DMT_EditorControl.openDocument", pcbs[name])
    ensure_pcb_focus(mcp)


def ensure_pcb_focus(mcp, tries=10):
    """EasyEDA sometimes switches the tab on its own – check before writing, get the PCB back otherwise."""
    info = {}
    for _ in range(tries):
        info = api(mcp, "DMT_SelectControl.getCurrentDocumentInfo") or {}
        if info.get("uuid") == PCB["uuid"]:
            return
        api(mcp, "DMT_EditorControl.openDocument", PCB["uuid"])
        time.sleep(1)
    raise MCPError(f"PCB {PCB['name']} cannot be focused (active: {info})")


def activate_pcb(mcp):
    """The PCB editor answers PCB_Drc.check, getDsnFile and exports only after EasyEDA reported its tab as active.
    That report comes only on a tab switch; openDocument on the current tab does not help. Probe: the rule
    configuration name (empty = inactive). Remedy: switch to the start page and back."""
    for _ in range(3):
        if api(mcp, "PCB_Drc.getCurrentRuleConfigurationName"):
            return
        print("  PCB tab counts as inactive in EasyEDA – switching away and back")
        api(mcp, "DMT_EditorControl.openDocument", "tab_page1")
        time.sleep(2)
        open_pcb(mcp, PCB["name"])
        time.sleep(2)
    raise MCPError(f"PCB tab cannot be activated – click the tab '{PCB['name']}' in EasyEDA once")


def save_pcb(mcp):
    ensure_pcb_focus(mcp)
    return api(mcp, "PCB_Document.save")  # saves only the active PCB


def reload_pcb(mcp):
    """Save, close the PCB tab and open it again. Needed before the DRC: right after many API changes the DRC reports
    false 'Connection Error's on correct tracks (320 of them, minutes later still); reloaded from disk: 0."""
    if not save_pcb(mcp):
        raise MCPError("saving the PCB failed")
    info = api(mcp, "DMT_SelectControl.getCurrentDocumentInfo")
    api(mcp, "DMT_EditorControl.closeDocument", info["tabId"])
    time.sleep(2)
    open_pcb(mcp, PCB["name"])
    time.sleep(3)


def list_pcb_components(mcp):
    comps, offset = [], 0
    while True:
        res = mcp.call("easyeda_pcb_components", projectId=PROJECT, limit=200, offset=offset)
        comps += res["components"]
        offset += len(res["components"])
        if not res["components"] or offset >= res["total"]:
            return comps


def drc(mcp, out=None):
    """EasyEDA DRC with details (PCB_Drc.check(true, false, true)). Needs the bridge with return depth 12, otherwise
    only [MaxDepth] comes back. With details it always returns a list ([] = no findings); null = it did not run
    (tab inactive, internal timeout)."""
    ensure_pcb_focus(mcp)
    activate_pcb(mcp)
    res = mcp.call("easyeda_api_call", path="PCB_Drc.check", args=[True, False, True], confirmWrite=True, timeout=150)
    if not res.get("ok"):
        raise MCPError(f"DRC failed: {res.get('error')} – is EasyEDA throttled? (handbook/12-troubleshooting.md)")
    res = res.get("result")
    if not isinstance(res, list):
        raise MCPError(f"DRC returned no result ({res!r}) – PCB tab inactive or EasyEDA throttled")
    found = []

    def walk(o):
        if isinstance(o, dict):
            if "errorType" in o:
                found.append(o)
            else:
                for x in o.values():
                    walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(res)
    if res and not found and "[MaxDepth]" in json.dumps(res):
        raise MCPError("DRC details cut off ([MaxDepth]) – import the patched bridge (edakit/easyeda/"
                       "bridge-extension-patch.sh)")
    if out:
        Path(out).write_text(json.dumps(res, indent=1))
    return found


def read_drc_rules(mcp):
    """The rule set of the DRC of the active PCB, as EasyEDA answers (drc_rules.py): {"configuration": {"name",
    "config"}, "net_rules": [...], "net_classes": [...]} from PCB_Drc.getCurrentRuleConfiguration, getNetRules and
    getAllNetClasses. The PCB tab must count as active (activate_pcb – drc() does it). The configuration lies up to 9
    levels deep: with the original bridge (depth 5) it is cut off, and that raises."""
    out = {"configuration": api(mcp, "PCB_Drc.getCurrentRuleConfiguration"),
           "net_rules": api(mcp, "PCB_Drc.getNetRules"),
           "net_classes": api(mcp, "PCB_Drc.getAllNetClasses")}
    if "[MaxDepth]" in json.dumps(out):
        raise MCPError("DRC rule set cut off ([MaxDepth]) – import the patched bridge (edakit/easyeda/"
                       "bridge-extension-patch.sh)")
    if not (out["configuration"] or {}).get("config"):
        raise MCPError(f"no DRC rule configuration ({out['configuration']!r}) – PCB tab inactive?")
    return out


def write_drc_rules(mcp, want):
    """Make the DRC rule set of the active PCB the board file's (want = drc_rules.wanted(board)): the net classes
    first, then the rule configuration, then the net rules – each call stops on an answer that is not true – and return
    the differences read back right after ([] = written). The editor takes either overwrite without a check and answers
    true whenever the PCB tab counts as active (handbook 9.4), so only the read-back says what came of it. NOT RUN
    against EasyEDA yet: the live probe of step 2.2 decides whether edakit writes the rule set this way. Before
    reporting anything written, the caller saves, reloads (reload_pcb) and reads back once more – working agreement 16."""
    from . import drc_rules

    def call(method, *args):
        if (res := api(mcp, f"PCB_Drc.{method}", *args)) is not True:
            raise MCPError(f"PCB_Drc.{method} returned {json.dumps(res)} "
                           f"({json.dumps(args, ensure_ascii=False)[:200]})")
    for method, *args in drc_rules.class_changes(want, read_drc_rules(mcp)):
        call(method, *args)
    have = read_drc_rules(mcp)
    call("overwriteCurrentRuleConfiguration", drc_rules.config_for(want, have["configuration"]))
    call("overwriteNetRules", drc_rules.net_rules_for(want, read_drc_rules(mcp)["net_rules"]))
    return drc_rules.differences(want, read_drc_rules(mcp))


# --- the project's copy of a device: an own footprint built from data (edakit part build, handbook 4.5) -------------

def find_copies(mcp, template, designators, lcsc=None):
    """{"symbol": uuid, "footprint": uuid} of the project's copies of the device a component of designators – or,
    failing that, a part of the LCSC number lcsc – is placed with on the template schematic: the carrier of an own
    footprint. The template holds every part of the graph (edakit schematic create); its pages are searched in turn.
    NOT RUN against EasyEDA yet (step 3.6): the bell's tdisplay_device.py finds the copies of its stand-in this way."""
    sch_uuid, pages = find_pages(mcp, template)
    for page in pages:
        focus_page(mcp, sch_uuid, page)
        for c in (state(x) for x in api(mcp, "SCH_PrimitiveComponent.getAll", "part") or []):
            if c.get("Designator") in designators or (lcsc and c.get("SupplierId") == lcsc):
                symbol, footprint = (c.get("Symbol") or {}).get("uuid"), (c.get("Footprint") or {}).get("uuid")
                if symbol and footprint:
                    return {"symbol": symbol, "footprint": footprint}
    raise MCPError(f"none of {', '.join(designators)} on the template '{template}' – edakit schematic create places "
                   "the carrier first")


def open_library_editor(mcp, cls, uuid, project, wait_s=30):
    """Open a library document of the project (LIB_Footprint, LIB_Symbol) in its editor and wait until it is the
    active document; its tab id. openInEditor takes the project's UUID ("project" fails, 9.4) and may report an error
    while it opens anyway – the active document decides."""
    try:
        api(mcp, f"{cls}.openInEditor", uuid, project, timeout=30)
    except MCPError as e:
        print(f"  ({cls}.openInEditor: {str(e)[:80]})")
    for _ in range(wait_s):
        cur = api(mcp, "DMT_SelectControl.getCurrentDocumentInfo") or {}
        if cur.get("uuid") == uuid:
            time.sleep(2)
            return cur["tabId"]
        time.sleep(1)
    raise MCPError(f"{cls} {uuid} did not become the active document")


def _create(mcp, path, args):
    if not api(mcp, path, *args):
        raise MCPError(f"{path} created nothing ({json.dumps(args, ensure_ascii=False)[:160]})")


def build_copy(mcp, project, copies, ops):
    """Rebuild the project's copy of a device from its footprint data (footprint.build_ops): in the footprint editor
    every pad deleted and the data's pads created – with print in the data also the old print deleted (silkscreen,
    component shape, marking and pin-soldering layers) and the data's drawn –, saved; with a symbol box the symbol's
    pins and body deleted and the box drawn, saved. Returns what the editors hold afterwards: {"pads": [the state of
    every pad], "pins": {number: name} or None}, for footprint.readback_differences. Parts placed in the PCB keep
    their old copy until they are deleted and created again (9.4). The bell's tdisplay_device.py and the reference
    project's led_footprints.py rebuild their copies with these calls; NOT RUN in this form against EasyEDA yet – the
    live run of step 3.6 (implementation plan) does it on a throwaway document first."""
    from .footprint import PRINT_CLASSES, PRINT_LAYERS
    tab = open_library_editor(mcp, "LIB_Footprint", copies["footprint"], project)
    try:
        if old := api(mcp, "PCB_PrimitivePad.getAllPrimitiveId") or []:
            api(mcp, "PCB_PrimitivePad.delete", old)
        if ops["print"] is not None:
            for cls in PRINT_CLASSES:
                for prim in map(state, api(mcp, f"{cls}.getAll") or []):
                    if prim.get("Layer") in PRINT_LAYERS:
                        api(mcp, f"{cls}.delete", [prim["PrimitiveId"]])
        for args in ops["pads"]:
            _create(mcp, "PCB_PrimitivePad.create", args)
        for path, args in ops["print"] or []:
            _create(mcp, path, args)
        if not api(mcp, "PCB_Document.save"):
            raise MCPError("the footprint editor did not save")
        pads = [state(p) for p in api(mcp, "PCB_PrimitivePad.getAll") or []]
    finally:
        api(mcp, "DMT_EditorControl.closeDocument", tab)
    pins = None
    if ops["symbol"]:
        rect, made = ops["symbol"]
        tab = open_library_editor(mcp, "LIB_Symbol", copies["symbol"], project)
        try:
            for cls in ("SCH_PrimitivePin", "SCH_PrimitiveRectangle", "SCH_PrimitivePolygon", "SCH_PrimitiveCircle"):
                if old := api(mcp, f"{cls}.getAllPrimitiveId") or []:
                    api(mcp, f"{cls}.delete", old)
            _create(mcp, "SCH_PrimitiveRectangle.create", rect)
            for args in made:            # pins anew: SCH_PrimitivePin.modify is not saved (the bell, 2026-10-26)
                _create(mcp, "SCH_PrimitivePin.create", args)
            if not api(mcp, "SCH_Document.save"):
                raise MCPError("the symbol editor did not save")
            pins = {str(p.get("PinNumber")): p.get("PinName") for p in map(state, api(mcp, "SCH_PrimitivePin.getAll")
                                                                               or [])}
        finally:
            api(mcp, "DMT_EditorControl.closeDocument", tab)
    return {"pads": pads, "pins": pins}


def describe_drc(found, limit=25):
    from collections import Counter
    counts = Counter((f["errorType"], f.get("ruleName"), f.get("net")) for f in found)
    lines = [f"DRC: {len(found)} findings" + (f" – {dict(counts)}" if found else "")]
    for f in found[:limit]:
        err = f.get("errData") or {}
        pos = err.get("position") or {}
        lines.append(f"    {f['errorType']}: {(f.get('obj1') or {}).get('typeName')} {(f.get('obj1') or {}).get('suffix')}"
                     f" <-> {(f.get('obj2') or {}).get('typeName')} {(f.get('obj2') or {}).get('suffix')}"
                     f"  at {pos.get('x')}, {pos.get('y')}  distance {err.get('minDistance')}")
    return "\n".join(lines)


def die(msg, code=1):
    print(f"\nERROR: {msg}", file=sys.stderr)
    return code


__all__ = ["MCPClient", "MCPError", "PROJECT", "api", "connect", "natural_key", "open_project", "start", "state",
           "wait_for_bridge"]
