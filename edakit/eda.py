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


def start(cfg, verbose=False, artifact_dir=None):
    """Claim EasyEDA for the calling Claude session and start an own MCP server through mcp-server.sh."""
    lock.claim_for_script(mode=cfg.lock)
    env = {"ARTIFACT_DIR": str(artifact_dir or cfg.artifact("mcp", ".keep").parent),
           "BRIDGE_TIMEOUT_MS": os.environ.get("BRIDGE_TIMEOUT_MS", "120000")}
    return MCPClient(["bash", str(MCP_SERVER)], verbose=verbose, env=env, cwd=cfg.root, lock_mode=cfg.lock)


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


class Progress:
    """Phase headings with the duration of the previous phase and EasyEDA's memory."""

    def __init__(self):
        self.t0 = self.t = time.monotonic()
        self.title = None

    def __call__(self, title=None):
        now = time.monotonic()
        if self.title:
            print(f"  ({self.title}: {now - self.t:.1f} s, {easyeda_memory()})")
        self.title, self.t = title, now
        if title:
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


def find_pages(mcp, name):
    for sch in api(mcp, "DMT_Schematic.getAllSchematicsInfo") or []:
        if schematic_name(mcp, sch["uuid"]) == name:
            return sch["uuid"], [p["uuid"] for p in sch.get("page", [])]
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


def focus_page(mcp, sch_uuid, page_uuid, timeout=200):
    """Open a page and wait until it is active. A large A1 sheet (120 parts) took up to 160 s."""
    api(mcp, "DMT_EditorControl.openDocument", page_uuid)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sheet = mcp.call("easyeda_schematic_sheet_info")
        if not sheet.get("not_available") and sheet["sheet"].get("uuid") == page_uuid:
            FOCUS.update(schematic=sch_uuid, page=page_uuid)
            return
        time.sleep(1)
    raise MCPError(f"page {page_uuid} did not become active")


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

PCB = {}  # name and uuid of the PCB this command works on


def open_pcb(mcp, name):
    pcbs = {p["name"]: p["uuid"] for p in api(mcp, "DMT_Pcb.getAllPcbsInfo") or []}
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
