"""Schematics in EasyEDA Pro from the graph: create, check, copy, layout (stage S).

    edakit schematic create [--board B] [--only R1,C1] [--dry-run] [--save]   template <- graph (replaced every run);
                                                 --save (also of layout) only when the netlist equals the graph
    edakit schematic check  [--board B] [--schematic NAME] [--no-pins]       read only: schematic = graph?
    edakit schematic copy   [--board B] [--source A --target B]              template -> board schematic
    edakit schematic layout [--board B] [--dry-run] [--save]                 readable sheet with blocks and wires
    edakit schematic draw   [--board B] [--out FILE]                         the same sheet as SVG, without EasyEDA
                                                                             (schematic_draw.py)

Two schematics per board:
  template  (default generated_<board>): built from the graph by `create`, deleted and rebuilt on every run. Nets are
            short stubs with net labels – ugly but exact. Nobody edits it.
  schematic (default layout_<board>): the readable sheet. `copy` makes it from the template while no PCB hangs on it;
            `layout` arranges it by topology and draws real wires. Once the PCB is linked to it, `copy` refuses
            (the PCB would lose its schematic) and `layout` syncs parts with the graph in place instead.

Never wire anything by hand: change the graph, run create, check and layout again.
"""

from __future__ import annotations

import json

from . import eda
from .design import Design, natural_key
from .eda import FOCUS, FOCUS_LOST, PROJECT, MCPError, api, batch_write, ensure_focus

# Template layout: groups as bands from top to bottom, cells (width, height, per row) by component type
GROUPS = [
    ("power", {"battery_holder", "connector", "fuse", "switch", "diode", "inductor", "regulator"}),
    ("mcu", {"microcontroller", "module"}),
    ("ic", {"ic", "transistor"}),
    ("ui", {"button", "potentiometer", "audio", "testpoint"}),
    ("led", {"led"}),
    ("passive", {"resistor", "capacitor"}),
]
CELL = {"microcontroller": (500, 600, 2), "module": (500, 600, 2), "ic": (300, 300, 4)}
CELL_DEFAULT = (160, 100, 9)  # spacing >= length of the net labels at the stubs, otherwise neighbours collide
ORIGIN = (100, 100)
GROUP_GAP = 60


def plan_template(comps):
    positions, y = {}, ORIGIN[1]
    for _, types in GROUPS:
        members = sorted((d for d, c in comps.items() if c.get("type") in types), key=natural_key)
        row_h, x, col = 0, ORIGIN[0], 0
        for d in members:
            w, h, per_row = CELL.get(comps[d]["type"], CELL_DEFAULT)
            if col == per_row:
                x, col, y, row_h = ORIGIN[0], 0, y + row_h, 0
            positions[d] = (x + w // 2, y + h // 2)
            x, col, row_h = x + w, col + 1, max(row_h, h)
        if members:
            y += row_h + GROUP_GAP
    rest = sorted((d for d in comps if d not in positions), key=natural_key)
    for i, d in enumerate(rest):
        positions[d] = (ORIGIN[0] + 60 + (i % 9) * CELL_DEFAULT[0], y + 50 + (i // 9) * CELL_DEFAULT[1])
    return positions


def prepare_schematic(mcp, name):
    """Create the schematic `name` anew (delete one of the same name unless a board hangs on it) and open page 1."""
    for sch in api(mcp, "DMT_Schematic.getAllSchematicsInfo") or []:
        if eda.schematic_name(mcp, sch["uuid"]) != name:
            continue
        if sch.get("parentBoardName"):
            raise MCPError(f"schematic '{name}' belongs to board {sch['parentBoardName']} – not overwritten")
        api(mcp, "DMT_Schematic.deleteSchematic", sch["uuid"])
        print(f"  deleted the existing schematic '{name}'")
    uuid = api(mcp, "DMT_Schematic.createSchematic")
    sch = next(s for s in api(mcp, "DMT_Schematic.getAllSchematicsInfo") if s["uuid"] == uuid)
    eda.focus_page(mcp, uuid, sch["page"][0]["uuid"], timeout=30)
    eda.rename_schematic(mcp, uuid, name)  # only now: right after createSchematic renaming reports true and does nothing
    print(f"  schematic '{name}' created")


def iter_tabs(node):
    if isinstance(node, dict):
        yield from node.get("tabs", [])
        for child in node.get("children", []) or []:
            yield from iter_tabs(child)
    elif isinstance(node, list):
        for child in node:
            yield from iter_tabs(child)


def close_other_schematic_tabs(mcp):
    """Close other (saved) schematic tabs – EasyEDA sometimes switches to one of them on its own, and writes would
    land in the wrong schematic."""
    try:
        tree = api(mcp, "DMT_EditorControl.getSplitScreenTree")
    except MCPError as e:
        print(f"  ? tabs not readable ({e})")
        return
    for tab in list(iter_tabs(tree)):
        data = tab.get("data") or {}
        if not data.get("sch") or data.get("data-schematic-uuid") == FOCUS["schematic"]:
            continue
        if tab.get("isUnSaved"):
            print(f"  ? tab {tab['title']} has unsaved changes – stays open")
            continue
        try:
            api(mcp, "DMT_EditorControl.closeDocument", tab["tabId"])
        except MCPError as e:
            print(f"  ? tab {tab['title']} not closed ({e})")


def resolve_devices(cfg, mcp, comps, refresh=False):
    """LCSC number -> deviceItem (uuid, libraryUuid); one search per number that is not cached. The search is full
    text – "C5613" also finds C5613331 and UC5613PWP – so only hits with exactly this supplierId count."""
    cache_file = cfg.artifact("device_cache.json")
    cache = {} if refresh or not cache_file.exists() else json.loads(cache_file.read_text(encoding="utf-8"))
    devices = {}
    for lcsc in sorted({c["lcsc"] for c in comps.values() if c.get("lcsc")}):
        if lcsc in cache:
            devices[lcsc] = cache[lcsc]
            continue
        found = mcp.call("easyeda_schematic_search_device", key=lcsc, itemsOfPage=20)
        hits = [h for h in found.get("devices", []) if h.get("supplierId") == lcsc]
        if not hits:
            print(f"  ! {lcsc}: not found in the EasyEDA library")
            continue
        devices[lcsc] = {"uuid": hits[0]["uuid"], "libraryUuid": hits[0]["libraryUuid"]}
        print(f"  {lcsc} -> {hits[0]['name']}")
    if devices:
        cache_file.write_text(json.dumps({**cache, **devices}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for d, c in comps.items():  # parts without LCSC number (bare test pads) carry their EasyEDA device in the graph
        if not c.get("lcsc") and c.get("easyeda_device"):
            dev = c["easyeda_device"]
            devices[f"dev:{d}"] = {"uuid": dev["uuid"], "libraryUuid": dev["libraryUuid"]}
    print(f"  {len(devices)} devices ({len(set(devices) & set(cache))} from {cache_file.name})")
    return devices


def place(mcp, comps, devices, positions):
    ops, todo = [], []
    for d in sorted(comps, key=natural_key):
        key = comps[d].get("lcsc") or f"dev:{d}"
        if key not in devices:
            print(f"  ! {d}: skipped (no device for {key})")
            continue
        x, y = positions[d]
        # addIntoBom: false fails for library parts ("Invalid device") – create normally, then modify
        bom = comps[d].get("bom", True) if not comps[d].get("lcsc") else True
        ops.append({"operationId": f"place-{d}", "action": "create", "primitiveKind": "component",
                    "deviceItem": devices[key], "x": x, "y": y, "addIntoBom": bom})
        todo.append(d)
    ids = batch_write(mcp, ops)
    placed = {d: {"id": ids[f"place-{d}"], "ref": d} for d in todo if ids.get(f"place-{d}")}
    batch_write(mcp, [{"operationId": f"ref-{d}", "action": "modify", "primitiveId": p["id"],
                       "property": {"designator": d}} for d, p in placed.items()])
    hand = [d for d in placed if comps[d].get("lcsc") and comps[d].get("bom") is False]
    for n, d in enumerate(hand):  # hand-soldered parts: on the PCB, not in the BOM
        if n % 20 == 0:
            ensure_focus(mcp)
        api(mcp, "SCH_PrimitiveComponent.modify", placed[d]["id"], {"addIntoBom": False})
    ensure_focus(mcp)
    on_sheet = {c["primitiveId"]: c for c in eda.list_sheet_parts(mcp)}
    for d, p in placed.items():
        c = on_sheet.get(p["id"])
        if not c:
            raise MCPError(f"{d} ({p['id']}) is not on the page – focus lost while placing?")
        p["ref"] = c["reference"]
        if c["reference"] != d:
            print(f"  ? {d}: designator in EasyEDA is {c['reference']}")
    if len(on_sheet) != len(placed):
        raise MCPError(f"the page holds {len(on_sheet)} parts, {len(placed)} were placed")
    print(f"  {len(placed)} parts placed")
    return placed


def pin_differences(symbol, graph, labels=("symbol", "graph")):
    """symbol, graph: {pin number: name}. Numbers on one side only, and names that differ (case and blanks ignored) –
    a graph that assumed another pinout shows up as a name, long before the board does."""
    norm = lambda s: "".join(str(s).split()).upper()  # noqa: E731
    a, b = labels
    out = []
    if set(symbol) != set(graph):
        out.append(f"{a} only {sorted(set(symbol) - set(graph))}, {b} only {sorted(set(graph) - set(symbol))}")
    out += [f"pin {n}: {a} '{symbol[n]}', {b} '{graph[n]}'" for n in sorted(set(symbol) & set(graph), key=natural_key)
            if norm(symbol[n]) != norm(graph[n])]
    return out


def check_symbol_pins(mcp, comps, placed):
    """One symbol per part number is enough to read; every designator is compared, the graph may differ per part."""
    problems, symbol_pins = 0, {}
    for d, p in placed.items():
        key = comps[d].get("lcsc") or d
        if key not in symbol_pins:
            pins = mcp.call("easyeda_schematic_component_pins", primitiveId=p["id"]).get("pins", [])
            symbol_pins[key] = {str(pin["pinNumber"]): pin.get("pinName", "") for pin in pins}
        diffs = pin_differences(symbol_pins[key], comps[d]["pins"])
        if diffs:
            problems += 1
            print(f"  ! {d}: " + "; ".join(diffs))
    print(f"  {len(placed) - problems}/{len(placed)} parts with matching pins")
    return problems


def connect_call(mcp, name, pins, stub):
    """connect_pins_by_net with focus guard: on a focus loss get the page back and repeat once."""
    ensure_focus(mcp)
    res = mcp.call("easyeda_schematic_connect_pins_by_net", projectId=PROJECT, netName=name, pins=pins,
                   stubLength=stub, confirmWrite=True)
    lost = [f for f in res.get("failures", []) if FOCUS_LOST in str(f.get("error", ""))]
    if lost:
        ensure_focus(mcp)
        again = mcp.call("easyeda_schematic_connect_pins_by_net", projectId=PROJECT, netName=name,
                         pins=[{"primitiveId": f["primitiveId"], "pinNumber": f["pinNumber"]} for f in lost],
                         stubLength=stub, confirmWrite=True)
        if any(FOCUS_LOST in str(f.get("error", "")) for f in again.get("failures", [])):
            raise MCPError(f"{name}: pins still unreadable (focus) – abort instead of follow-up errors")
        keep = [f for f in res["failures"] if FOCUS_LOST not in str(f.get("error", ""))]
        res = {**again, "failures": keep + again.get("failures", [])}
    return res


def connect(mcp, nets, placed, stub):
    failures = 0
    for name, pins in nets.items():
        items = [{"primitiveId": placed[d]["id"], "pinNumber": n} for d, n in (p.split(".", 1) for p in pins)
                 if d in placed]
        if not items:
            continue
        bad = connect_call(mcp, name, items, stub).get("failures", [])
        # Collision at the stub end (the point belongs to another net inside EasyEDA): retry with longer stubs –
        # EasyEDA would short primitives on the same coordinate otherwise.
        for longer in (stub * 2, stub * 3, stub * 4):
            if not bad:
                break
            bad = connect_call(mcp, name, [{"primitiveId": f["primitiveId"], "pinNumber": f["pinNumber"]}
                                           for f in bad], longer).get("failures", [])
        failures += len(bad)
        print(f"  {name:<14} {len(items) - len(bad)}/{len(items)}" + (f"  ! {bad}" if bad else ""))
    return failures


def repair(mcp, nets, placed, stub):
    """connect_pins_by_net skips a pin silently when its stub end would land on a point EasyEDA already counts to
    another net. Connect every pin that is on no net afterwards one by one with longer stubs."""
    ref_to_graph = {p["ref"]: d for d, p in placed.items()}
    on_net = set()
    for net in mcp.call("easyeda_schematic_nets", projectId=PROJECT, scope="focused").get("nets", []):
        for n in net.get("nodes", []):
            if n["component_ref"] in ref_to_graph:
                on_net.add(f"{ref_to_graph[n['component_ref']]}.{n['pin']}")
    left = 0
    for name, pins in nets.items():
        for pin in pins:
            d, n = pin.split(".", 1)
            if d not in placed or pin in on_net:
                continue
            res = {}
            for longer in (stub * 2, stub * 3, stub * 5, stub * 7):
                res = connect_call(mcp, name, [{"primitiveId": placed[d]["id"], "pinNumber": n}], longer)
                if res.get("created_primitive_ids") and not res.get("failures"):
                    print(f"  {pin:<8} -> {name} with stub {longer:g}")
                    break
            else:
                left += 1
                print(f"  ! {pin} could not be connected to {name}: {res.get('failures')}")
    return left


def mark_nc(mcp, comps, placed):
    ops = [{"operationId": f"nc-{d}.{pin}", "action": "setPinNoConnect", "primitiveId": p["id"], "pinNumber": str(pin)}
           for d, p in placed.items() for pin in comps[d].get("nc", [])]
    if ops:
        batch_write(mcp, ops)
    print(f"  {len(ops)} pins marked no-connect")


def create(cfg, args):
    board = cfg.board(args.board)
    design = Design.from_config(cfg)
    comps, nets = design.board_comps(board.name), design.board_nets(board.name)
    if args.only:
        only = set(args.only.split(","))
        unknown = only - comps.keys()
        if unknown:
            return eda.die(f"unknown designators: {sorted(unknown)}")
        comps = {d: c for d, c in comps.items() if d in only}
        nets = {n: [p for p in pins if p.split(".")[0] in comps] for n, pins in nets.items()}
        nets = {n: p for n, p in nets.items() if p}
    name = args.schematic or board.template
    positions = plan_template(comps)
    print(f"graph v{design.version}: {len(comps)} parts, {len(nets)} nets -> schematic '{name}'")
    if args.dry_run:
        for d in sorted(positions, key=natural_key):
            print(f"  {d:<6} {comps[d].get('type', ''):<16} {positions[d]}")
        return 0
    phase = eda.Progress()
    mcp = eda.start(cfg, args.verbose)
    try:
        phase("bridge")
        if not eda.wait_for_bridge(mcp, args.wait):
            return 1
        phase("project and schematic")
        eda.open_project(mcp, cfg, args.create_project)
        prepare_schematic(mcp, name)
        eda.label_sheet(mcp, cfg, FOCUS["page"], f"{board.title} template", design.version)
        close_other_schematic_tabs(mcp)
        phase("search parts")
        devices = resolve_devices(cfg, mcp, comps, args.refresh_devices)
        phase("place")
        placed = place(mcp, comps, devices, positions)
        cfg.artifact(f"schematic_map_{name}.json").write_text(json.dumps(placed, indent=2) + "\n", encoding="utf-8")
        phase("check symbol pins")
        pin_problems = check_symbol_pins(mcp, comps, placed)
        stub = cfg.schematic.get("stub", 10)
        phase("connect nets")
        failures = connect(mcp, nets, placed, stub)
        phase("connect what is left")
        failures += repair(mcp, nets, placed, stub)
        phase("no-connect")
        mark_nc(mcp, comps, placed)
        phase("netlist against the graph")
        diffs = eda.verify_nets(mcp, nets, placed)
        phase("ERC")
        erc = mcp.call("easyeda_erc_run", projectId=PROJECT, scope="focused")
        print("  " + json.dumps({k: v for k, v in erc.items() if not isinstance(v, (list, dict))}, ensure_ascii=False))
        skipped = len(comps) - len(placed)
        if args.save:
            phase("save")
            eda.save_if_matching(mcp, diffs, failures, pin_problems, skipped)
        phase(None)
        print(f"\ndone: {len(placed)} placed, {skipped} skipped, {pin_problems} pin mismatches, {failures} pin "
              f"failures, {diffs} differing nets")
        return 0 if not (skipped or failures or diffs or pin_problems) else 2
    except MCPError as e:
        return eda.die(str(e))
    finally:
        mcp.close()


# --- check --------------------------------------------------------------------------------------------------------

class Findings:
    def __init__(self):
        self.sections = {}

    def add(self, section, msg):
        self.sections.setdefault(section, []).append(msg)

    def count(self):
        return sum(len(v) for v in self.sections.values())

    def print(self):
        for section, msgs in self.sections.items():
            print(f"\n[{section}] {len(msgs)}")
            for m in msgs:
                print(f"  {m}")


def compare(graph_comps, graph_nets, sch_comps, sch_nets, rep):
    """Parts (missing, extra, duplicate, LCSC), nets (every graph pin on its net, no foreign pins)."""
    from collections import Counter
    for ref, n in Counter(c["reference"] for c in sch_comps).items():
        if n > 1:
            rep.add("parts", f"{ref}: {n}x in the schematic")
    sch = {c["reference"]: c for c in sch_comps}
    for d in sorted(graph_comps.keys() - sch.keys(), key=natural_key):
        rep.add("parts", f"{d}: missing in the schematic")
    for d in sorted(sch.keys() - graph_comps.keys(), key=natural_key):
        rep.add("parts", f"{d}: not in the graph ({sch[d].get('lcsc') or sch[d].get('value')})")
    for d in sorted(graph_comps.keys() & sch.keys(), key=natural_key):
        want, have = graph_comps[d].get("lcsc"), sch[d].get("lcsc")
        if want and want != have:
            rep.add("parts", f"{d}: LCSC {have}, graph {want}")
    pin_net = {}
    for net in sch_nets:
        for n in net.get("nodes", []):
            pin_net.setdefault(f"{n['component_ref']}.{n['pin']}", set()).add(net["net_name"])
    graph_pin = {p: name for name, pins in graph_nets.items() for p in pins}
    for name, pins in graph_nets.items():
        for p in pins:
            if p.split(".", 1)[0] not in sch:
                continue  # already reported as a missing part
            have = pin_net.get(p, set())
            if not have:
                rep.add("nets", f"{name}: {p} not connected")
            elif have != {name}:
                rep.add("nets", f"{name}: {p} is on {sorted(have)}")
    for p, nets in sorted(pin_net.items()):
        if p not in graph_pin and p.split(".", 1)[0] in sch:
            rep.add("nets", f"{p} on {sorted(nets)}, without a net in the graph")
    return sch


def check_pins(mcp, graph_comps, sch, graph_nets, rep):
    in_net = {p for pins in graph_nets.values() for p in pins}
    for d in sorted(graph_comps.keys() & sch.keys(), key=natural_key):
        pins = mcp.call("easyeda_schematic_component_pins", primitiveId=sch[d]["primitiveId"]).get("pins", [])
        for diff in pin_differences({str(p["pinNumber"]): p.get("pinName", "") for p in pins}, graph_comps[d]["pins"]):
            rep.add("pins", f"{d}: {diff}")
        nc_want = {str(p) for p in graph_comps[d].get("nc", [])}
        nc_have = {str(p["pinNumber"]) for p in pins if p.get("noConnected")}
        for p in sorted(nc_want - nc_have):
            if f"{d}.{p}" not in in_net:
                rep.add("pins", f"{d}.{p}: nc in the graph, but no no-connect marker")
        for p in sorted(nc_have - nc_want):
            rep.add("pins", f"{d}.{p}: no-connect marker, not nc in the graph")


def check(cfg, args):
    """Read only (it activates the pages, though). Exit 0 = same as the graph, 2 = differences, 1 = error."""
    board = cfg.board(args.board)
    design = Design.from_config(cfg)
    graph_comps, graph_nets = design.board_comps(board.name), design.board_nets(board.name)
    name = args.schematic or board.template
    print(f"graph v{design.version}: {len(graph_comps)} parts, {len(graph_nets)} nets")
    mcp = eda.start(cfg, args.verbose)
    try:
        if not eda.wait_for_bridge(mcp, args.wait):
            return 1
        eda.open_project(mcp, cfg)
        sch_uuid, pages = eda.find_pages(mcp, name)
        sch_comps, sch_nets = [], {}
        for page in pages:
            eda.focus_page(mcp, sch_uuid, page)
            sch_comps += eda.list_sheet_parts(mcp)
            nets = mcp.call("easyeda_schematic_nets", projectId=PROJECT, scope="focused")
            if nets.get("not_available"):
                raise MCPError(f"nets not readable: {nets.get('error')}")
            for net in nets.get("nets", []):  # nets of the same name are one net across pages
                sch_nets.setdefault(net["net_name"], {"net_name": net["net_name"], "nodes": []})
                sch_nets[net["net_name"]]["nodes"] += net.get("nodes", [])
        sch_comps = [c for c in sch_comps if c.get("component_kind", "part") == "part" and c.get("reference")]
        print(f"schematic '{name}': {len(pages)} page(s), {len(sch_comps)} parts, {len(sch_nets)} nets")
        rep = Findings()
        sch = compare(graph_comps, graph_nets, sch_comps, sch_nets.values(), rep)
        if not args.no_pins:
            check_pins(mcp, graph_comps, sch, graph_nets, rep)
    except MCPError as e:
        return eda.die(str(e))
    finally:
        mcp.close()
    rep.print()
    if args.json:
        from pathlib import Path
        Path(args.json).write_text(json.dumps(rep.sections, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if rep.count():
        print(f"\n{rep.count()} differences.")
        return 2
    print("\nschematic matches the graph.")
    return 0


# --- copy ---------------------------------------------------------------------------------------------------------

def copy(cfg, args):
    """Copy a schematic in seconds instead of generating it for minutes (DMT_Schematic.copySchematic copies parts,
    wires, net names and no-connect markers). Replaces the target unless a board hangs on it."""
    board = cfg.board(args.board)
    source, target = args.source or board.template, args.target or board.schematic
    if source == target:
        return eda.die("source and target are the same")
    mcp = eda.start(cfg, args.verbose)
    try:
        if not eda.wait_for_bridge(mcp, args.wait):
            return 1
        eda.open_project(mcp, cfg)
        by_name = lambda n: [s for s in api(mcp, "DMT_Schematic.getAllSchematicsInfo") or []  # noqa: E731
                             if eda.schematic_name(mcp, s["uuid"]) == n]
        found = by_name(source)
        if len(found) != 1:
            raise MCPError(f"schematic '{source}' {'not found' if not found else 'exists several times'}")
        for sch in by_name(target):
            if sch.get("parentBoardName"):
                raise MCPError(f"'{target}' belongs to board {sch['parentBoardName']} – not overwritten. Use "
                               "`edakit schematic layout`, which syncs the parts in place.")
            api(mcp, "DMT_Schematic.deleteSchematic", sch["uuid"])
            print(f"  deleted the existing schematic '{target}'")
        existing = set(eda.all_schematic_names(mcp))
        uuid = api(mcp, "DMT_Schematic.copySchematic", found[0]["uuid"])
        if not uuid or uuid in existing:
            raise MCPError(f"copySchematic returned no new UUID ({uuid})")
        eda.activate_schematic(mcp, uuid)  # modifySchematicName renames the ACTIVE schematic
        eda.rename_schematic(mcp, uuid, target)
        n_pages = eda.activate_schematic(mcp, uuid)
        comps = mcp.call("easyeda_schematic_components", projectId=PROJECT, scope="focused", limit=1)
        print(f"'{source}' -> '{target}': {n_pages} page(s), {comps.get('total', '?')} parts")
        if args.save:
            mcp.call("easyeda_project_save", projectId=PROJECT, confirmWrite=True)
        return 0
    except MCPError as e:
        return eda.die(str(e))
    finally:
        mcp.close()


def main(cfg, args):
    if args.action == "create":
        return create(cfg, args)
    if args.action == "check":
        return check(cfg, args)
    if args.action == "copy":
        return copy(cfg, args)
    if args.action == "draw":
        from . import schematic_draw
        return schematic_draw.main(cfg, args)
    from . import schematic_layout
    return schematic_layout.main(cfg, args)

