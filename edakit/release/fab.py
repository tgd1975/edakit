"""Stages L (board) and F (manufacturing files) of the release gate for one board.

    edakit fab --board main --out DIR            read the PCB, save + reload, DRC, export Gerber/CPL, BOM from the graph
    edakit fab --board main --out DIR --offline  only check what is already in DIR/<board>/
    edakit fab diff RUN_A RUN_B [--board B]     where the manufacturing files of two gate runs differ

Result in DIR/<board>/:
    gerber/ and gerber_<board>.zip   Gerber and drill files as EasyEDA exports them (upload the ZIP)
    bom_<board>.csv                  BOM in JLCPCB format, generated from the graph
    odb_<board>.zip                  with a maker of [cart] makers that takes ODB++ (AISLER): EasyEDA's ODB++ export
                                     (easyeda_export_odb), checked by SYNC.odb; odb_error.txt when the export failed
    bom_<board>_mpn.csv              with a maker of [cart] makers that matches by MPN (Eurocircuits): the same rows
                                     with manufacturer and MPN of the parts entries, in the maker's columns
    cpl_<board>.csv                  pick-and-place file in JLCPCB format (BOM parts only)
    jlc_parts.json                   JLCPCB assembly catalogue entry per LCSC number of the BOM (PARTS.stock)
    pcb.json, drc.json, bom_easyeda.json, cpl_easyeda.xlsx   raw data from EasyEDA (for --offline)
    order.md                         with [order] (board file or edakit.toml) or [cart]: the order form of this
                                     board at the planned maker, every field with where it comes from (order_sheet.py)
    order.json                       with [order]: the order settings that change the board as made (fab hash)
    netlist_diff.json                schematic against PCB (`pcb parts`, `pcb nets`), when the DRC has an Import
                                     Changes item
    drc_rules.json                   with [routing] drc_rules in the board file: the rule set the DRC ran with, as
                                     EasyEDA answers (configuration, net rules, net classes – eda.read_drc_rules)
and DIR/polarity_<board>.png: every polarised part with pad, role and net, to compare with datasheets and with the
assembly preview at JLCPCB.

  SYNC.pcb  parts in the PCB = graph; every pad carries the graph's net; every graph pin has a pad
  GEO.copper  copper from the Gerber files: every net connected, no short, every connected pad present
  GEO.drc  EasyEDA DRC without findings (after save and reload): other kinds; and schematic and PCB in sync – a
       "Netlist Error – Import Changes" item with no difference in netlist_diff.json is EasyEDA waiting for the
       import acknowledgement (Design → Import Changes once), otherwise the differences with the command that fixes
       them. With [routing] drc_rules = "check" in the board file also: the rule set the DRC ran with = the board
       file's (clearance, edge clearance, track widths of the classes, via, net classes – drc_rules.py), named in the
       row
  SYNC.footprint  footprint per part = parts database
  GEO.width  track width per net >= IPC-2221 for 1.5 x the simulated current (fail); below the practical class width (warn);
       voltage drop as an upper bound (info)
  SYNC.plan  fixed parts in the PCB = plan (± 0.02 mm, rotation, side); the plan itself without findings
  GEO.mark  silkscreen "+"/"−" next to a pad of that sign: PCB texts, and the "+" footprints draw as two crossing strokes in
       the silk Gerber files; cathode and minus pads "−", anode, plus and vbus pads "+" (waive GEO.mark on the nearest part)
  GEO.hole  every through hole takes its lead at nominal size (lead data in the parts database); tight in the worst case
       or plated slots narrower than JLCPCB's minimum: warn
  SYNC.footprint every pad sits where the library footprint has the pad with that number (pad_map in the parts DB for
       intended swaps)
  GEO.loop short current loops ([[loops]] of the board file and layout.loops of the graph): shortest path over tracks of the
       same net per pad pair
  SYNC.plan the plan keeps the layout requirements of the circuit: layout.fixed, .edge, .near of the graph and a
       decoupling capacitor next to every IC (handover.py)
  GEO.spacing pads of different parts on different nets at least the routing clearance apart, on the pad shapes of
       `edakit route read` while they are the PCB's (route.pad_gaps, as `route check` measures)
  GEO.spacing on every assembled side, SMD pads of different parts on different nets at least the paste gap apart
       ([release] assembly paste_gap_mm), measured as GEO.spacing
  GEO.pour copper per layer from the Gerber files: share of the board area and largest copper-free circle (info); a
       circle above [copper] max_bare_mm on a poured layer, a share below [copper] min_cover, a copper piece without
       pad, via or plated hole: warn
  GEO.ring every plated hole keeps JLCPCB's annular ring (component hole 0.18 mm, warn below 0.20 mm; via 0.05 mm) and
       every two plated holes JLCPCB's hole-to-hole spacing, edge to edge (0.45 mm with a component hole, 0.2 mm vias)
  GEO.silk silkscreen from the Gerber files: edakit's own print on a solder-mask opening (fail), other print there per part,
       print beyond the outline, a part of the designators side without a visible designator or group label (not in
       [silk] unlabelled), a text height edakit prints below 1.0 mm (warn)
  GEO.spacing with [routing] hand_solder_keep_mm: on the solder side of every through-hole pad of a hand-soldered part
       (bom: false), vias and pads of other nets at least that far away; pads as GEO.spacing, vias from the via drill file
       (net: the tracks of pcb.json that end on them)
  GEO.silk with [looks]: on the visible side every PCB text of the silkscreen is one the board file puts there (the board
       label on its side, the [[silk.texts]] of the side, with [silk] designators on it the designators and group
       labels), and no part on it shows its designator while [silk] designators names the other side (waive GEO.silk on
       the part)
  SYNC.plan every part the graph puts on the board has a row in [place] of the board file – fixed, from pcb place, or
       written back by pcb autolayout (auto = true); a part on a bought board is on no made board and needs none
  [looks] of the board file: the visible side's track length and the board's vias, an information row; above
       max_track_m or max_vias a warning (row ID "L": the stage's own, no check of the catalog)
  SYNC.bom  BOM from the graph = BOM of EasyEDA; every LCSC number in the parts database
  PARTS.stock  for the maker of [cart] makers that orders from JLCPCB's catalogue (fails as the planned maker, warns as
       another one, does not run without it): every BOM part listed in JLCPCB's assembly catalogue with stock for
       `quantity` boards, under the MPN of its parts entry; another class than the entry's jlc_class warns (check
       PARTS.stock reads the same offline, from the stock snapshot)
  SYNC.cpl  pick and place: every BOM part exactly once, side and rotation = PCB; sides/SMD as [release] assembly says
  FILES.set  Gerber set complete; outline and holes = plan (± 0.2 mm); tooling holes in the NPTH file, mask open, no copper
  SYNC.odb  with a maker of [cart] makers that takes ODB++ (AISLER; fails for the planned maker, warns for another one):
       odb_<board>.zip, exported through the patched easyeda_export_odb, against this run's files – every layer
       (copper, mask, paste, silkscreen) rasterised as GEO.copper and XOR'd with its Gerber layer, no spot above
       SPOT_MM2 and no layer in one only; the drill hits = the drill files (1 µm, diameter, plated or not); the profile
       = the Gerber outline; every BOM part once at the CPL's place, rotation (ODB++ clockwise) and side with its part
       number, a part with bom: false as the maker's dnp says; the nets of the pins as the graph's, compared as groups
  FILES.order  with [order] or [cart], per maker of [cart] makers (fails for the planned maker, warns for another one):
       every field a value of the maker's form, the remark, thickness_mm and the colours of mask and silkscreen as its
       form has them, mark = its placeholder on the silkscreen – JLCPCB's placeholder at a maker without one –, its
       tooling holes; for every maker layers and size where set, the quantities, no copper near the edge in a tab zone
       (order_sheet.py)
Last stdout line: JSON list of rows {stage, id, item, check, actual, expected, result}. Exit 0 / 2 / 1.

What the manufacturer builds from, hashed for the sign-offs with scope 'fab' (fab_sha256, FAB_METHOD): every Gerber
layer rasterised as GEO.copper does (gerber.RES) in the frame of the board outline – documentation and drill-drawing layers
left out –, the drill hits rounded to 1 µm, the BOM and CPL rows sorted, and with [order] the order settings that
change the board as made (order.json: thickness, colours of mask and silkscreen, finish, mark – not the remark, not the
tab zones). Aperture numbers, comments and the order in which EasyEDA writes its objects do not change it; a board
without [order] keeps the hash it had. `fab diff` compares the same rasters: XOR, labelled into spots – and the
settings one by one.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import math
import re
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from .. import drc_rules, gerber, handover, stock
from ..config import BOTTOM, MIL_PER_MM, TOP
from ..design import Design, natural_key
from ..findings import accept_reason
from ..toolchain import is_kicad

MM = 1 / MIL_PER_MM
SILK = {3: TOP, 4: BOTTOM}   # silkscreen layer -> copper layer of the SMD pads on the same side
MULTI = 12                   # through-hole pads are on all layers
HOLE_TOL_MM = 0.08           # JLCPCB: finished plated hole +0.13/-0.08 mm, slots the same
HOLE_PLAY_MM = 0.05          # below this play in the worst case the lead goes in only with force (warn)
SLOT_TWIST_MM = 0.1          # slot: allowance on the lead edge in case the lead sits slightly twisted
JLC_SLOT_MM = 0.5            # JLCPCB: plated slots on 2 layers at least 0.5 mm wide
JLC_SEARCH = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"


class Rows(list):
    def add(self, stage, cid, item, check, ok, actual="", expected="", result=None):
        self.append({"stage": stage, "id": cid, "item": item, "check": check, "actual": str(actual),
                     "expected": str(expected), "result": result or ("pass" if ok else "fail")})


def merge_bom(entries):
    """BOM lines of several schematic pages -> one line per LCSC number. The bridge lists every part of a
    board-linked schematic twice ("C1, C1"): every designator counts once."""
    merged = {}
    for e in entries:
        m = merged.setdefault(e.get("lcsc") or e.get("value"), {**e, "reference": [], "quantity": 0})
        for r in e.get("reference", "").split(", "):
            if r and r not in m["reference"]:
                m["reference"].append(r)
        m["quantity"] = len(m["reference"])
    return [{**m, "reference": ", ".join(m["reference"])} for m in merged.values()]


# --- collect from EasyEDA -----------------------------------------------------------------------------------------

def collect(cfg, board, d, verbose=False):
    from .. import eda, pcb
    (d / "netlist_diff.json").unlink(missing_ok=True)
    (d / "drc_rules.json").unlink(missing_ok=True)
    compare_rules = drc_rules.mode(board)    # [routing] drc_rules: GEO.drc compares the rule set the DRC ran with
    mcp = eda.connect(cfg, verbose, artifact_dir=d)
    try:
        eda.open_project(mcp, cfg)
        eda.open_pcb(mcp, board.pcb)
        comps = eda.list_pcb_components(mcp)
        for c in comps:
            pads = eda.api(mcp, "PCB_PrimitiveComponent.getAllPinsByPrimitiveId", c["primitiveId"]) or []
            c["pads"] = [{k: eda.state(p)[k] for k in ("PadNumber", "X", "Y", "Net", "Layer")}
                         | {"tht": bool(eda.state(p)["Hole"])} for p in pads]
        lines = [{k: s[k] for k in ("Net", "Layer", "LineWidth", "StartX", "StartY", "EndX", "EndY")}
                 for s in (eda.state(x) for x in eda.api(mcp, "PCB_PrimitiveLine.getAll") or []) if s["Layer"] in (1, 2)]
        strings = [{k: s[k] for k in ("Text", "X", "Y", "Layer")}
                   for s in (eda.state(x) for x in eda.api(mcp, "PCB_PrimitiveString.getAll") or [])]
        ids = {c["primitiveId"]: c["designator"] for c in comps if c.get("designator")}
        shown = {ids[a["ParentPrimitiveId"]]: bool(a.get("ValueVisible"))       # GEO.silk: designator printed or hidden
                 for a in map(eda.state, eda.api(mcp, "PCB_PrimitiveAttribute.getAll") or [])
                 if a.get("Key") == "Designator" and a.get("ParentPrimitiveId") in ids}
        (d / "pcb.json").write_text(json.dumps({"components": comps, "lines": lines, "strings": strings,
                                                "designators": shown}, indent=1))
        eda.reload_pcb(mcp)  # the DRC is reliable only on the saved, reloaded state
        found = eda.drc(mcp)
        (d / "drc.json").write_text(json.dumps(found, indent=1, ensure_ascii=False))
        if compare_rules:
            try:
                held = eda.read_drc_rules(mcp)
            except eda.MCPError as e:          # GEO.drc then says: not read
                held = {"error": str(e)}
            (d / "drc_rules.json").write_text(json.dumps(held, indent=1, ensure_ascii=False))
        res = mcp.call("easyeda_export_gerbers", projectId="current", drillFormat="millimeter",
                       productionReview={"mode": "off"}, timeout=300)
        if not res.get("exported"):
            raise SystemExit(f"Gerber export failed: {res}")
        shutil.copy(res["artifact_path"], d / f"gerber_{board.name}.zip")
        export_odb(cfg, mcp, board, d)        # a maker of [cart] makers that takes ODB++ (AISLER): SYNC.odb checks it
        res = mcp.call("easyeda_export_pick_place", projectId="current", format="csv", timeout=120)
        if not res.get("exported"):
            raise SystemExit(f"pick-and-place export failed: {res}")
        shutil.copy(res["file_path"], d / "cpl_easyeda.xlsx")  # EasyEDA delivers xlsx even when csv is asked for
        # easyeda_bom_generate lists the parts of the FOCUSED schematic page, not of the board: focus every page of
        # the board schematic in turn and merge (otherwise the template or another board would be compared)
        sch_uuid, pages = eda.find_pages(mcp, board.schematic)
        entries = []
        for page in pages:
            eda.focus_page(mcp, sch_uuid, page)
            res = mcp.call("easyeda_bom_generate", projectId="current", format="json", groupBy="lcsc", timeout=120)
            entries += res.get("entries", [])
        (d / "bom_easyeda.json").write_text(json.dumps(merge_bom(entries), indent=1, ensure_ascii=False))
        if pcb.import_items(found):   # last: the comparison focuses the schematic pages
            try:
                diff = pcb.netlist_diff(cfg, board, mcp)
                (d / "netlist_diff.json").write_text(json.dumps(diff, indent=1, ensure_ascii=False))
            except eda.MCPError as e:          # GEO.drc then says: not compared
                print(f"  schematic and PCB not compared: {e}", file=sys.stderr)
    finally:
        mcp.close()
    shutil.rmtree(d / "gerber", ignore_errors=True)
    with zipfile.ZipFile(d / f"gerber_{board.name}.zip") as z:
        z.extractall(d / "gerber")


ODB_ERROR = "odb_error.txt"     # why the ODB++ export of a run failed – SYNC.odb names it


def odb_takers(cfg):
    from .. import makers
    return [m for m in makers.all_of(cfg) if "odb" in m.files]


def export_odb(cfg, mcp, board, d):
    """odb_<b>.zip through the patched MCP tool easyeda_export_odb (handbook 2.5) – only for a maker that takes ODB++;
    a .tgz from EasyEDA is packed into a zip with the same files. A failed export leaves odb_error.txt for SYNC.odb."""
    from .. import eda
    target = d / f"odb_{board.name}.zip"
    target.unlink(missing_ok=True)
    (d / ODB_ERROR).unlink(missing_ok=True)
    if not odb_takers(cfg):
        return
    try:
        res = mcp.call("easyeda_export_odb", projectId="current", unit="mm", timeout=300)
    except eda.MCPError as e:
        (d / ODB_ERROR).write_text(f"easyeda_export_odb: {e} – the patched MCP server and bridge (handbook 2.5)")
        return
    if not res.get("exported"):
        (d / ODB_ERROR).write_text(f"easyeda_export_odb: {res.get('error') or res}")
        return
    raw = Path(res["artifact_path"]).read_bytes()
    if raw[:2] == b"PK":
        target.write_bytes(raw)
        return
    import tarfile
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for m in sorted(tar.getmembers(), key=lambda m: m.name):
            if m.isfile():
                z.writestr(m.name, tar.extractfile(m).read())


def jlc_search(keyword, page_size=10, timeout=30):
    """JLCPCB's public assembly catalogue (no login; only the keyword leaves the machine): the hits of a full-text
    search as the catalogue gives them. Network errors and a changed answer raise."""
    import urllib.request
    req = urllib.request.Request(JLC_SEARCH, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                                 data=json.dumps({"keyword": keyword, "currentPage": 1, "pageSize": page_size}).encode())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)["data"]["componentPageInfo"]["list"] or []


def jlc_part(lcsc, timeout=30):
    """The catalogue entry of exactly this LCSC number – the search is full text – or None: not listed, a number that
    can only be pre-ordered."""
    return next((c for c in jlc_search(lcsc, timeout=timeout) if c.get("componentCode") == lcsc), None)


def fetch_jlc(bom, d):
    """PARTS.stock: the catalogue entry per LCSC number of the BOM, into jlc_parts.json."""
    out = {}
    for lcsc in sorted({r["LCSC Part #"] for r in bom}):
        try:
            hit = jlc_part(lcsc)
        except Exception as e:  # network, changed API
            out[lcsc] = {"error": str(e)[:200]}
            continue
        out[lcsc] = hit and {k: hit.get(k) for k in ("componentModelEn", "componentLibraryType",
                                                     "preferredComponentFlag", "stockCount")}
    (d / "jlc_parts.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))


# --- helpers ------------------------------------------------------------------------------------------------------

def to_plan(board, c):
    return board.from_eda(c["x"] * MM, c["y"] * MM, c["rotation"], c["layer"])


def pin_role(design, comp, num):
    return (design.parts.get(comp.get("lcsc") or "", {}).get("pins") or {}).get(num, {}).get("role")


def role_sign(role):
    """The sign a pin role takes in the silkscreen (GEO.mark): anode, plus… and vbus "+", cathode and minus… "−"; the
    anodes and cathodes of the colours of an RGB LED (anode_red, cathode_red …) like the plain ones."""
    if not role:
        return None
    if role.startswith(("plus", "anode")) or role == "vbus":
        return "+"
    if role.startswith(("minus", "cathode")):
        return "−"
    return None


def bom_rows(design, board):
    groups = defaultdict(list)
    comps = design.board_comps(board.name)
    for ref, c in comps.items():
        if c.get("bom") is False or not c.get("lcsc"):
            continue
        groups[c["lcsc"]].append(ref)
    out = []
    for lcsc, refs in sorted(groups.items(), key=lambda kv: min(natural_key(r) for r in kv[1])):
        part, c = design.parts.get(lcsc, {}), comps[refs[0]]
        out.append({"Comment": c.get("value") or part.get("mpn") or c.get("part", ""),
                    "Designator": ",".join(sorted(refs, key=natural_key)), "Footprint": part.get("footprint", ""),
                    "LCSC Part #": lcsc})
    return out


def write_bom(bom, path):
    """The BOM in JLCPCB's columns – SYNC.bom and `edakit order` write the same file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Comment", "Designator", "Footprint", "LCSC Part #"])
        w.writeheader()
        w.writerows(bom)


MPN_COLUMNS = ["Designator", "Quantity", "Manufacturer", "MPN", "Comment"]


def mpn_rows(design, bom):
    """The rows of SYNC.bom with the manufacturer and the manufacturer part number of each line's parts entry – the BOM of a
    maker that matches parts by MPN (PARTS.fact/mpn finds an entry without them)."""
    out = []
    for r in bom:
        entry = design.parts.get(r["LCSC Part #"]) or {}
        out.append({"Designator": r["Designator"], "Quantity": len(r["Designator"].split(",")),
                    "Manufacturer": entry.get("manufacturer", ""), "MPN": entry.get("mpn", ""),
                    "Comment": r["Comment"], "Footprint": r["Footprint"], "LCSC Part #": r["LCSC Part #"]})
    return out


def write_mpn_bom(cfg, design, board, bom, d):
    """bom_<b>_mpn.csv for the makers of [cart] makers that take a BOM with MPN, in the columns of the first one's
    profile; none without such a maker. Not in the fab hash: it adds nothing the maker builds from beyond the parts
    entries, which are in the circuit hash."""
    from .. import makers
    takers = [m for m in makers.all_of(cfg) if "bom_mpn" in m.files]
    path = d / f"bom_{board.name}_mpn.csv"
    if not takers:
        path.unlink(missing_ok=True)
        return
    columns = (takers[0].data.get("bom") or {}).get("columns") or MPN_COLUMNS
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(mpn_rows(design, bom))


def required_widths(cfg, design, board):
    """Per net: (IPC-2221 width for 1.5 x the largest simulated current, practical class width, current)."""
    from ..pcb import ipc2221_width_mm
    f = cfg.artifacts / "sim" / "net_currents.json"
    if not f.exists():
        return None
    cur = json.loads(f.read_text())["nets"]
    out = {}
    for net in design.nets:
        e = cur.get(f"{net}__{board.name}") or cur.get(net)
        if not e:
            continue
        i = max(e["i_max_a"], e.get("i_peak_a") or 0)
        cls = board.force_class.get(net) or next(n for n, c in board.net_classes.items() if i >= c["min_a"])
        out[net] = (ipc2221_width_mm(i), board.net_classes[cls]["width_mm"], i)
    return out


# --- L checks -----------------------------------------------------------------------------------------------------

def check_pcb(cfg, board, design, d, rows):
    from .. import pcb as pcbmod
    data = json.loads((d / "pcb.json").read_text())
    want = design.board_comps(board.name)
    on_pcb = {c["designator"]: c for c in data["components"] if c.get("designator")}
    missing, extra = sorted(set(want) - set(on_pcb), key=natural_key), sorted(set(on_pcb) - set(want), key=natural_key)
    rows.add("L", "SYNC.pcb", board.name, "parts in the PCB = graph", not missing and not extra,
             f"{len(on_pcb)} in the PCB" + (f", missing {missing}" if missing else "") + (f", extra {extra}" if extra else ""),
             f"{len(want)} in the graph")
    bad, total = [], 0
    for ref, c in sorted(on_pcb.items()):
        if ref not in want:
            continue
        have = {p["PadNumber"]: p.get("Net") or "" for p in c["pads"]}
        total += len(have)
        for num, net in have.items():
            soll = design.pin_net.get(f"{ref}.{num}", "")
            if net != soll:
                bad.append(f"{ref}.{num}: {net or '–'} instead of {soll or '–'}")
        for pin in want[ref]["pins"]:
            if f"{ref}.{pin}" in design.pin_net and pin not in have:
                bad.append(f"{ref}.{pin}: pad missing in the footprint ({design.pin_net[f'{ref}.{pin}']})")
    rows.add("L", "SYNC.pcb", board.name, "pad nets in the PCB = graph, every graph pin has a pad", not bad,
             f"{total} pads" + (f", {len(bad)} differences: {'; '.join(bad[:12])}" if bad else ""), "no difference")
    wrong = []
    for ref, c in sorted(on_pcb.items()):
        part = design.part(ref) if ref in want else None
        if part and part.get("footprint") and c["footprintName"] != part["footprint"]:
            wrong.append(f"{ref}: {c['footprintName']} instead of {part['footprint']}")
    rows.add("L", "SYNC.footprint", board.name, "footprint per part = parts database", not wrong, "; ".join(wrong) or "all equal", "equal")
    geo_file = pcbmod.geometry_file(cfg, board)
    if geo_file.exists():
        geo = json.loads(geo_file.read_text())
        check_pad_layout(board, design, on_pcb, want, geo, rows)
        place, boxes, tht, _, _ = pcbmod.build_plan(cfg, board, geo)
        problems = pcbmod.check_plan(cfg, board, geo, place, boxes, tht)
        off = []
        for ref, p in sorted(place.items()):
            if ref not in on_pcb:
                continue
            x, y, rot, side = to_plan(board, on_pcb[ref])
            if math.hypot(x - p.x, y - p.y) > 0.02 or abs((rot - p.rot + 180) % 360 - 180) > 0.01 or side != p.side:
                off.append(f"{ref}: ({x:.2f}, {y:.2f}, {rot:g}°, {side}) instead of ({p.x:.2f}, {p.y:.2f}, {p.rot:g}°, {p.side})")
        rows.add("L", "SYNC.plan", board.name, "fixed parts in the PCB = plan (position, rotation, side)", not off,
                 f"{len(place)} parts" + (f", {len(off)} off: {'; '.join(off[:8])}" if off else ""), "± 0.02 mm")
        rows.add("L", "SYNC.plan", board.name, "plan without findings (outline, overlaps, holes, THT pins, near)", not problems,
                 "; ".join(problems[:10]) or "none", "none")
        kept = pcbmod.check_handover(board, design, place, boxes)
        rows.add("L", "SYNC.plan", board.name, "plan keeps the layout requirements of the circuit (fixed, edge, near, "
                 "decoupling)", not kept, "; ".join(kept[:10]) or "all kept", "all kept")
    else:
        rows.add("L", "SYNC.plan", board.name, "footprint geometry for the plan checks", False, f"{geo_file.name} missing "
                 "(edakit pcb dump)", "present")
    widths, length = defaultdict(lambda: 1e9), defaultdict(float)
    for ln in data["lines"]:
        if ln["Net"]:
            widths[ln["Net"]] = min(widths[ln["Net"]], ln["LineWidth"] * MM)
            length[ln["Net"]] += math.hypot(ln["EndX"] - ln["StartX"], ln["EndY"] - ln["StartY"]) * MM
    need = required_widths(cfg, design, board)
    if need is None:
        rows.add("L", "GEO.width", board.name, "simulated net currents for the track widths", False,
                 "net_currents.json missing (edakit sim)", "present")
    else:
        ipc = [f"{n}: {w:.2f} < {need[n][0]:.2f} mm" for n, w in sorted(widths.items()) if n in need and w < need[n][0] - 0.005]
        rows.add("L", "GEO.width", board.name, "track width per net >= IPC-2221 for 1.5 x the simulated current (1 oz, 10 K)",
                 not ipc, "; ".join(ipc) or f"{len(widths)} nets with tracks", ">= IPC width")
        thin = [f"{n}: {w:.2f} < {need[n][1]:.2f} mm" for n, w in sorted(widths.items()) if n in need and w < need[n][1] - 0.005]
        if thin:
            rows.add("L", "GEO.width", board.name, "track width >= practical width of the net class", False, "; ".join(thin),
                     ">= class width", "warn")
        # upper bound: all pieces of the net in series, narrowest width, 35 µm copper (0.0172 Ohm mm²/m), no pours
        drop = {n: length[n] / 1000 * 0.0172 / (widths[n] * 0.035) * need[n][2] for n in length
                if n in need and need[n][2] > 0.05}
        if drop:
            rows.add("L", "GEO.width", board.name, "voltage drop on tracks, upper bound (all pieces in series x largest current)",
                     True, ", ".join(f"{n} {v * 1e3:.0f} mV" for n, v in sorted(drop.items(), key=lambda kv: -kv[1])),
                     "information", "info")
    drc = json.loads((d / "drc.json").read_text())
    if is_kicad(cfg):                     # KiCad: schematic parity is part of its DRC (cli.findings)
        items = [f for f in drc if f.get("ruleName") == "parity"]
        other = [f for f in drc if f not in items]
        kinds = Counter(f"{f.get('errorType')} ({f.get('severity')})" for f in other)
        rows.add("L", "GEO.drc", board.name, "KiCad DRC without findings (other kinds)", not other,
                 ", ".join(f"{k}: {n}" for k, n in kinds.items()) or "0", "0")
        rows.add("L", "GEO.drc", board.name, "schematic and PCB in sync (KiCad's schematic parity)", not items,
                 "; ".join(f"{f['errorType']}: {', '.join(f['items'][:2])}" for f in items[:8]) or "in sync",
                 "no parity finding")
    else:
        items = pcbmod.import_items(drc)
        other = [f for f in drc if f not in items]
        kinds = Counter(f"{f.get('errorType')} ({f.get('ruleName')})" for f in other)
        rows.add("L", "GEO.drc", board.name, "EasyEDA DRC without findings (other kinds)", not other,
                 ", ".join(f"{k}: {n}" for k, n in kinds.items()) or "0", "0")
        diff = json.loads((d / "netlist_diff.json").read_text()) if (d / "netlist_diff.json").exists() else None
        ok, what = pcbmod.import_verdict(items, diff)
        rows.add("L", "GEO.drc", board.name, "schematic and PCB in sync (Import Changes)", ok, what, "no Import Changes item")
    if drc_rules.mode(board) and is_kicad(cfg):
        from ..toolchain.kicad import board as kicad_board
        off = kicad_board.rules_differences(cfg, board)
        rows.add("L", "GEO.drc", board.name, "KiCad's DRC rule set = [routing] of the board file", not off,
                 "; ".join(off) or "written from the board file", drc_rules.summary(drc_rules.wanted(board)))
    elif drc_rules.mode(board):
        ok, what, expected = drc_rules.verdict(board, d / "drc_rules.json")
        rows.add("L", "GEO.drc", board.name, "EasyEDA's DRC rule set = [routing] of the board file", ok, what, expected)
    check_polarity_marks(cfg, board, design, d, data, want, on_pcb, rows)


ROWS_NAMED = 20       # SYNC.plan: parts without a row named in the protocol row, the others counted


def check_rows(board, design, rows):
    """SYNC.plan: every part the graph puts on the board has a row in [place] of the board file (pcb.parts_without_row) –
    position, rotation and side as text, whoever wrote it. The board file decides it alone: no export is read."""
    from .. import pcb as pcbmod
    want = design.board_comps(board.name)
    missing = pcbmod.parts_without_row(board, design)
    names = ", ".join(missing[:ROWS_NAMED]) + (f" … (+{len(missing) - ROWS_NAMED})" if len(missing) > ROWS_NAMED else "")
    rows.add("L", "SYNC.plan", board.name, "every part of the board has a row in [place] (position, rotation, side)",
             not missing, f"{names}: no row in {board.file} [place] ({len(missing)} of {len(want)} parts)" if missing
             else f"{len(want)} parts, each with a row", "a row for every part")


TEXT_REACH_MM = 1.2   # GEO.mark: how far from its anchor, per character, the strokes of a PCB text may lie


def polarity_signs(cfg, board, d, data):
    """GEO.mark: the signs of the silkscreen as [(sign, x, y, silk layer, how)] in mm – the PCB texts "+", "−", "-", and the
    "+" a footprint draws as two crossing strokes, read from the silk Gerber files (gerber.plus_signs). A drawn "+"
    near a PCB text with a "+" is that text's print (a "+" text counts once, a "+5V" is a label); one inside the box
    of a [[silk.art]] item is artwork. -> (signs, silk files missing)."""
    from shapely.geometry import Point

    from .. import silk
    signs = [("+" if s["Text"] == "+" else "−", s["X"] * MM, s["Y"] * MM, s["Layer"], "text")
             for s in data["strings"] if s["Layer"] in SILK and s["Text"] in ("+", "−", "-")]
    lost = gerber.missing(d / "gerber", "top_silk", "bottom_silk")
    for key, layer, side in (("top_silk", 3, "top"), ("bottom_silk", 4, "bottom")):
        if gerber.FILES[key] in lost:
            continue
        drawn = gerber.plus_signs(d / "gerber" / gerber.FILES[key])
        texts = [(s["X"] * MM, s["Y"] * MM, TEXT_REACH_MM * len(s["Text"])) for s in data["strings"]
                 if s["Layer"] == layer and "+" in s["Text"]]
        drawn = [p for p in drawn if not any(math.dist(p, t[:2]) <= t[2] for t in texts)]
        if drawn and board.silk.get("art"):
            art = [g.envelope for g in silk.art_items(cfg, board, side)]
            drawn = [p for p in drawn if not any(a.covers(Point(p)) for a in art)]
        signs += [("+", x, y, layer, "drawn") for x, y in drawn]
    return signs, lost


def check_polarity_marks(cfg, board, design, d, data, want, on_pcb, rows):
    """GEO.mark: every sign of the silkscreen (polarity_signs) is compared with the nearest pad on its side whose pin role
    has a sign (role_sign); a sign at a pad of the other sign fails. `accept: {"GEO.mark": "…"}` on the nearest part lists
    its finding as waived – a decorative cross, or a footprint whose print is known and wrong."""
    signs, lost = polarity_signs(cfg, board, d, data)
    if lost:
        rows.add("L", "GEO.mark", board.name, "silk Gerber files for the drawn signs", False,
                 f"{', '.join(lost)} missing (Gerber export)", "present")
    polar = {r for r in want if r in on_pcb and any(role_sign(p.get("role")) for p in
                                                   (design.parts.get(want[r].get("lcsc") or "", {}).get("pins") or {}).values())}
    if not signs or not polar:
        return
    wrong, waived = [], []
    for sign, x, y, layer, _ in signs:
        pads = [(ref, p) for ref in polar for p in on_pcb[ref]["pads"]
                if p["Layer"] in (SILK[layer], MULTI) and role_sign(pin_role(design, want[ref], p["PadNumber"]))]
        if not pads:
            wrong.append(f"'{sign}' at ({x:.1f}, {y:.1f}) mm: no polarised pad on this side")
            continue
        ref, p = min(pads, key=lambda rp: math.hypot(rp[1]["X"] * MM - x, rp[1]["Y"] * MM - y))
        role = pin_role(design, want[ref], p["PadNumber"])
        if role_sign(role) != sign:
            text = f"'{sign}' at ({x:.1f}, {y:.1f}) mm: nearest pad {ref}.{p['PadNumber']} is {role}"
            reason = accept_reason(want[ref], "GEO.mark")
            if reason:
                waived.append((text, reason))
            else:
                wrong.append(text)
    n_text = sum(1 for s in signs if s[4] == "text")
    rows.add("L", "GEO.mark", board.name, "silkscreen '+'/'−' = role of the nearest polarised pad", not wrong,
             "; ".join(wrong) or f"{len(signs) - len(waived)} signs correct" + (f", {len(waived)} waived" if waived else "")
             + f": {n_text} as PCB text, {len(signs) - n_text} drawn in the silkscreen", "every sign at the right pole")
    for text, reason in waived:
        rows.add("L", "GEO.mark", board.name, f"polarity mark: {text}", True, text, "every sign at the right pole", "waived")
        rows[-1]["reason"] = reason


SILK_SPOT_MM2 = 0.0005    # GEO.silk: smaller pieces of print on an opening or beyond the outline are rounding
SILK_LIMIT_MM2 = 0.001    # GEO.silk: from this much on, a side or a part has print where it is not printed
SILK_PART_MM = 3.0        # GEO.silk: print on an opening further than this from every pad belongs to no part


def check_silk(cfg, board, design, d, rows):
    """GEO.silk: the silkscreen as the fab gets it – the print on solder-mask openings and beyond the outline (silk_print),
    the designators (silk_designators) and the text heights edakit prints (silk_heights)."""
    data = json.loads((d / "pcb.json").read_text())
    if lost := gerber.missing(d / "gerber", "top_silk", "bottom_silk", "top_mask", "bottom_mask", "outline"):
        rows.add("L", "GEO.silk", board.name, "Gerber files for the silkscreen check", False,
                 f"{', '.join(lost)} missing (Gerber export)", "present")
    else:
        silk_print(cfg, board, data, d / "gerber", rows)
    silk_designators(board, design, data, rows)
    silk_heights(cfg, board, rows)


def silk_spots(g):
    """The pieces of a geometry larger than SILK_SPOT_MM2, largest first."""
    return sorted((p for p in getattr(g, "geoms", [g]) if p.area > SILK_SPOT_MM2), key=lambda p: -p.area)


def nearest_pad(pads, spot):
    """'C2.1': the pad of pads [(name, x, y)] nearest to the spot's centre, within SILK_PART_MM; '' if none."""
    c = spot.centroid
    dist, name = min(((math.dist((x, y), (c.x, c.y)), name) for name, x, y in pads), default=(None, ""))
    return name if dist is not None and dist <= SILK_PART_MM else ""


def spots_text(spots, pads=None, around=""):
    """'0.165 mm² in 1 spot: (19.1, 9.0) mm at C2.1' – the five largest, with their nearest pad if pads are given."""
    def mm1(v):
        return f"{v:.1f}" if round(v, 1) else "0.0"         # never "-0.0"
    at = [f"{around}({mm1(p.centroid.x)}, {mm1(p.centroid.y)}) mm"
          + (f" at {pin}" if pads is not None and (pin := nearest_pad(pads, p)) else "") for p in spots[:5]]
    return (f"{sum(p.area for p in spots):.3f} mm² in {len(spots)} spot{'s' if len(spots) > 1 else ''}: "
            + ", ".join(at) + (" …" if len(spots) > 5 else ""))


def silk_print(cfg, board, data, g, rows):
    """GEO.silk, per side from the silk, mask and outline Gerber files. Print on a solder-mask opening: edakit's own –
    what is not in the footprint print `silk apply` kept (silk.footprint_print) – fails, the rest warns per part, the
    part of the nearest pad (JLCPCB clips print on openings). Print beyond the outline warns."""
    from .. import silk
    memo, kept = cfg.artifacts / f"silk_strings_{board.name}.json", silk.footprint_print(cfg, board)
    what = "edakit's own print (designators, texts, artwork of silk apply) off the solder-mask openings"
    if not kept.is_dir():
        rows.add("L", "GEO.silk", board.name, what, not memo.exists(), f"{memo.name} exists, {kept.name}/ does not: "
                 "edakit's print cannot be told from the footprints' (silk apply of an older edakit) – run edakit silk "
                 "apply" if memo.exists() else "edakit printed nothing on this board (no silk apply)",
                 "0 mm² – the footprint print silk apply keeps tells it apart")
    outline = gerber.outline_shape(g)
    if outline is None:
        rows.add("L", "GEO.silk", board.name, "board outline for the print beyond it", False,
                 f"no closed outline in {gerber.FILES['outline']}", "a closed outline")
    for side, layer in silk.SIDE.items():
        name = side.upper()
        mask_key, silk_key = silk.GERBER_KEYS[layer]
        pads = [(f"{c['designator']}.{p['PadNumber']}", p["X"] * MM, p["Y"] * MM) for c in data["components"]
                if c.get("designator") for p in c["pads"] if p["Layer"] in (layer, MULTI)]
        printed = gerber.shape(gerber.parse_gerber(g / gerber.FILES[silk_key]))
        other = printed.intersection(gerber.shape(gerber.parse_gerber(g / gerber.FILES[mask_key])))
        if kept.is_dir():
            if (kept / gerber.FILES[silk_key]).exists():
                theirs = gerber.shape(gerber.parse_gerber(kept / gerber.FILES[silk_key])).buffer(0.02)
                own, other = silk_spots(other.difference(theirs)), other.intersection(theirs)
            else:
                own, other = silk_spots(other), other.difference(other)
            rows.add("L", "GEO.silk", board.name, f"{name}: {what}", sum(p.area for p in own) <= SILK_LIMIT_MM2,
                     f"{name}: " + (spots_text(own, pads) if own else "0.000 mm²"),
                     "0 mm² – run silk apply after the last routing")
        by_part = defaultdict(list)
        for p in silk_spots(other):
            by_part[nearest_pad(pads, p).split(".")[0]].append(p)
        bad = {ref: spots for ref, spots in by_part.items() if sum(p.area for p in spots) > SILK_LIMIT_MM2}
        for ref, spots in sorted(bad.items(), key=lambda kv: natural_key(kv[0])):
            rows.add("L", "GEO.silk", board.name, f"{ref}: silkscreen on its solder-mask openings – JLCPCB clips it there"
                     if ref else f"{name}: silkscreen on solder-mask openings away from every pad", False,
                     f"{name}: {spots_text(spots, pads)}", "0 mm²", "warn")
        if not bad:
            rows.add("L", "GEO.silk", board.name, f"{name}: other print (footprints, texts by hand) off the solder-mask "
                     "openings", True, f"{name}: {sum(p.area for p in silk_spots(other)):.3f} mm²", "0 mm²")
        if outline is not None:
            out = silk_spots(printed.difference(outline.buffer(0.01)))
            area = sum(p.area for p in out)
            rows.add("L", "GEO.silk", board.name, f"{name}: silkscreen inside the board outline", area <= SILK_LIMIT_MM2,
                     f"{name}: " + (spots_text(out, around="around ").replace(" in ", " beyond it in ", 1) if out
                                    else "0.000 mm² beyond it"), "0 mm²", None if area <= SILK_LIMIT_MM2 else "warn")


def silk_designators(board, design, data, rows):
    """GEO.silk: every part of the `designators` side has a visible designator (read with the PCB into pcb.json), lies
    under a group label ([silk] groups, printed as a text) or a text with its name, or is listed in [silk] unlabelled
    with the reason – otherwise a warning per part."""
    from .. import silk
    side = board.silk.get("designators", "top")
    layer = silk.SIDE[side]
    shown = data.get("designators")
    if shown is None:
        rows.add("L", "GEO.silk", board.name, f"designators of the {side} side read with the PCB", False,
                 "pcb.json without the designators (written by an older edakit) – edakit fab without --offline",
                 "read with the PCB")
        return
    want = design.board_comps(board.name)
    texts = {s["Text"] for s in data["strings"] if s["Layer"] == layer + 2}
    grouped = {r for name, refs in (board.silk.get("groups") or {}).items() if name in texts for r in refs}
    unlabelled = board.silk.get("unlabelled") or {}
    parts = sorted((c["designator"] for c in data["components"] if c.get("designator") in want and c["layer"] == layer),
                   key=natural_key)
    bare = [r for r in parts if not shown.get(r) and r not in texts]
    in_group = [r for r in bare if r in grouped]
    listed = [r for r in bare if r not in grouped and r in unlabelled]
    rows.add("L", "GEO.silk", board.name, f"designators of the {side} side read with the PCB", True,
             f"{len(parts)} parts: {len(parts) - len(bare)} with a visible designator"
             + (f", {len(in_group)} under a group label" if in_group else "")
             + (", unlabelled on purpose: " + "; ".join(f"{r} ({unlabelled[r]})" for r in listed) if listed else ""),
             "every part labelled")
    for r in bare:
        if r not in grouped and r not in unlabelled:
            rows.add("L", "GEO.silk", board.name, f"{r}: no visible designator, no group label, not in [silk] unlabelled",
                     False, f"{r} on the {side} without a visible designator",
                     "a visible designator, a group label or [silk] unlabelled", "warn")


def silk_heights(cfg, board, rows):
    """GEO.silk: the text heights edakit prints – label_h_mm, board_label_h_mm when there is a board label, h_mm of
    [[silk.texts]] – at least JLCPCB's minimum text height; a warning per height below it."""
    from .. import silk
    s = board.silk
    heights = [("label_h_mm", float(s.get("label_h_mm", 1.0)))]
    if silk.board_label_text(cfg, board):
        heights.append(("board_label_h_mm", float(s.get("board_label_h_mm", 1.2))))
    heights += [(f"h_mm of [[silk.texts]] '{t['text']}'", float(t.get("h_mm", 1.2))) for t in s.get("texts", [])]
    low = [(k, h) for k, h in heights if h < silk.MIN_TEXT_MM - 1e-9]
    for k, h in low:
        rows.add("L", "GEO.silk", board.name, f"{k}: text height below JLCPCB's minimum", False, f"{k} = {h:g} mm",
                 f">= {silk.MIN_TEXT_MM:.1f} mm", "warn")
    if not low:
        rows.add("L", "GEO.silk", board.name, f"text heights edakit prints at least {silk.MIN_TEXT_MM:.1f} mm (JLCPCB minimum "
                 "text height)", True, ", ".join(f"{k} {h:g} mm" for k, h in heights), f">= {silk.MIN_TEXT_MM:.1f} mm")


def check_pad_layout(board, design, on_pcb, want, geo, rows):
    """SYNC.footprint: every pad sits where the library footprint has the pad with this number. Intended swaps are listed as
    pad_map {PCB pad: library pad} in the parts database. Numbers used several times (shell legs) count at each of
    their positions (pads_same_number from the dump)."""
    bad, n = [], 0
    for ref, c in sorted(on_pcb.items()):
        g = geo.get(ref, {}).get("pads")
        if ref not in want or not g or geo[ref].get("footprint") != c["footprintName"]:
            continue
        pad_map = design.parts.get(want[ref].get("lcsc") or "", {}).get("pad_map", {})
        same = geo[ref].get("pads_same_number", {})
        x, y, rot, side = to_plan(board, c)
        for pad in c["pads"]:
            num = pad_map.get(pad["PadNumber"], pad["PadNumber"])
            libs = same.get(num) or ([g[num]] if num in g else [])
            if not libs:
                bad.append(f"{ref}.{pad['PadNumber']}: unknown in the library footprint")
                continue
            have = board.plan_point(pad["X"] * MM, pad["Y"] * MM)
            off = min(math.dist(have, board.transform((lib["x"], lib["y"]), x, y, rot, side)) for lib in libs)
            n += 1
            if off > 0.05:
                bad.append(f"{ref}.{pad['PadNumber']}: {off:.2f} mm away from its footprint position")
    rows.add("L", "SYNC.footprint", board.name, "pad numbers sit as in the library footprint (exceptions: pad_map)", not bad,
             "; ".join(bad[:10]) or f"{n} pads", "± 0.05 mm")


def check_pad_clearance(cfg, board, design, d, rows):
    """GEO.spacing: pads of different parts on different nets keep the routing clearance on every copper layer – measured as
    `edakit route check` does, on the pad shapes of `route read` (pcb.json has none), when they still are the PCB's.
    A pair waived in the graph (waive GEO.spacing on one of its parts or nets) is listed with its reason."""
    from .. import route
    clear = route.Rules(board).clear
    want = f">= {clear * MM:.3f} mm (clearance_mil {clear:g})"
    data, why = route.board_as_read(cfg, board, json.loads((d / "pcb.json").read_text())["components"])
    if data is None:
        rows.add("L", "GEO.spacing", board.name, "pad shapes for the pad clearance", False, why, "the PCB as read")
        return
    gaps = route.pad_gaps(data, clear, route.pad_accepts(design.graph))
    bad = [route.gap_text(g, clear) for g in gaps if not g["waived"]]
    rows.add("L", "GEO.spacing", board.name, "pads of different parts on different nets at least the routing clearance apart",
             not bad, "; ".join(bad[:10]) + (f" … ({len(bad)} pairs)" if len(bad) > 10 else "")
             or f"{sum(1 for p in data['pads'] if p['ref'])} pads", want)
    for g in gaps:
        if g["waived"]:
            rows.add("L", "GEO.spacing", board.name, f"pad clearance: {route.gap_text(g, clear)}", True,
                     f"{g['mil'] * MM:.3f} mm", want, "waived")
            rows[-1]["reason"] = g["waived"]


def check_paste_gap(cfg, board, design, d, rows):
    """GEO.spacing: on every side that is assembled ([release] assembly sides), SMD pads of different parts on different nets
    at least the paste gap apart (paste_gap_mm, 0.4 mm) – the stencil keeps a web between their prints. Measured on
    the pad shapes of `route read` as GEO.spacing and `route check` measure them. A pair waived in the graph (waive GEO.spacing on
    one of its parts or nets) is listed with its reason."""
    from .. import route
    gap, sides = route.paste_rule(cfg)
    what = "SMD pads of different parts on different nets at least the paste gap apart on the assembled sides"
    if not sides:
        rows.add("L", "GEO.spacing", board.name, what, True, "no side assembled ([release] assembly sides)", "–")
        return
    want = f">= {gap * MM:.3f} mm on {' and '.join(sides)} ([release] assembly paste_gap_mm)"
    data, why = route.board_as_read(cfg, board, json.loads((d / "pcb.json").read_text())["components"])
    if data is None:
        rows.add("L", "GEO.spacing", board.name, "pad shapes for the paste gap", False, why, "the PCB as read")
        return
    gaps = route.pad_gaps(data, gap, route.pad_accepts(design.graph, "GEO.spacing", "paste"), sides)
    bad = [route.gap_text(g, gap, "the paste gap") for g in gaps if not g["waived"]]
    smd = sum(1 for p in data["pads"] if p["ref"] and route.LAYERS.get(p["layer"]) in sides)
    rows.add("L", "GEO.spacing", board.name, what, not bad,
             "; ".join(bad[:10]) + (f" … ({len(bad)} pairs)" if len(bad) > 10 else "") or f"{smd} SMD pads", want)
    for g in gaps:
        if g["waived"]:
            rows.add("L", "GEO.spacing", board.name, f"paste gap: {route.gap_text(g, gap, 'the paste gap')}", True,
                     f"{g['mil'] * MM:.3f} mm", want, "waived")
            rows[-1]["reason"] = g["waived"]


def check_looks(board, d, rows):
    """[looks] of the board file: the visible side's track length (pcb.json, lines per layer) and the vias of the board
    (the via drill file; none when EasyEDA wrote none) – an information row, and a warning per limit it exceeds. No
    check of the catalog: the stage's own row, like route check's line."""
    from .. import route
    if not board.looks:
        return
    data = json.loads((d / "pcb.json").read_text())
    length = {"TOP": 0.0, "BOTTOM": 0.0}
    for ln in data["lines"]:
        length[route.LAYERS[ln["Layer"]]] += math.hypot(ln["EndX"] - ln["StartX"], ln["EndY"] - ln["StartY"]) * MM / 1000
    vias = len(gerber.parse_holes(d / "gerber" / gerber.FILES["vias"]))
    row, warns = route.looks_rows(board, length, vias)
    lk = board.looks
    limits = ([f"<= {lk['max_track_m']:g} m"] if "max_track_m" in lk else []) + \
        ([f"<= {lk['max_vias']} vias"] if "max_vias" in lk else [])
    rows.add("L", "L", board.name, f"visible side ([looks] visible = {lk['visible']}): track length on it, vias of the "
             "board", True, f"{row} (TOP {length['TOP']:.2f} m, BOTTOM {length['BOTTOM']:.2f} m)",
             ", ".join(limits) or "information", "info")
    for text, actual, limit in warns:
        rows.add("L", "L", board.name, f"visible side within its [looks] limit: {text}", False, actual, limit, "warn")


def check_visible_print(cfg, board, design, d, rows):
    """GEO.silk with [looks]: the visible side carries only the texts the board file puts there. Every PCB text of its
    silkscreen (pcb.json strings) is the board label of that side (board_label_side, default the designators side),
    the text of a [[silk.texts]] entry of that side, or – when [silk] designators is that side – a designator of the
    board or a key of [silk] groups (what silk apply prints there). While [silk] designators names the other side, no
    part on the visible side shows its designator (pcb.json designators; waive GEO.silk on the part). The footprints'
    own print is no PCB text (GEO.mark and GEO.silk read it from the Gerber files), artwork is fills. Without [looks]: no row."""
    from .. import silk
    if not board.looks:
        return
    side = board.looks["visible"]
    name, layer = side.upper(), silk.SIDE[side]
    data = json.loads((d / "pcb.json").read_text())
    s = board.silk
    labelled = s.get("designators", "top")
    want = design.board_comps(board.name)
    allowed = {t for t, *_ in silk.silk_texts(board, side)}
    label = silk.board_label_text(cfg, board)
    if label and s.get("board_label_side", labelled) == side:
        allowed.add(label)
    if labelled == side:
        allowed |= set(want) | set(s.get("groups") or {})
    allowed = {t.strip() for t in allowed}
    texts = [t for t in data["strings"] if t["Layer"] == layer + 2]
    what = "the board label" if labelled != side else "the board label, a designator, a group label"
    check = f"{name} (visible): only the texts the board file puts there"
    expected = "the board label, [[silk.texts]] of this side" + (", designators, group labels" if labelled == side
                                                                  else "")
    stray = [t for t in texts if t["Text"].strip() not in allowed]
    for t in stray:
        rows.add("L", "GEO.silk", board.name, check, False, f"{name} (visible): text '{t['Text']}' at ({t['X'] * MM:.1f}, "
                 f"{t['Y'] * MM:.1f}) mm is neither {what} nor a [[silk.texts]] entry of this side", expected)
    if not stray:
        rows.add("L", "GEO.silk", board.name, check, True, f"{name}: {len(texts)} PCB text{'' if len(texts) == 1 else 's'}"
                 ", each one the board file puts there" if texts else f"{name}: no PCB text", expected)
    if labelled == side:
        return
    check = f"{name} (visible): no designator shown – [silk] designators is {labelled}"
    shown = data.get("designators")
    if shown is None:
        rows.add("L", "GEO.silk", board.name, f"designators of the {side} side (visible) read with the PCB", False,
                 "pcb.json without the designators (written by an older edakit) – edakit fab without --offline",
                 "read with the PCB")
        return
    parts = sorted((c["designator"] for c in data["components"] if c.get("designator") in want and c["layer"] == layer),
                   key=natural_key)
    for ref in (r for r in parts if shown.get(r)):
        text = f"{name} (visible): {ref} shows its designator – [silk] designators is {labelled}"
        reason = accept_reason(want[ref], "GEO.silk", "visible")
        if reason:
            rows.add("L", "GEO.silk", board.name, f"designator on the visible side: {text}", True, text, "hidden", "waived")
            rows[-1]["reason"] = reason
        else:
            rows.add("L", "GEO.silk", board.name, check, False, text, "hidden (silk apply hides it: [silk] hide)")
    if not any(shown.get(r) for r in parts):
        rows.add("L", "GEO.silk", board.name, check, True, f"{len(parts)} parts on the {side}, none shows its designator",
                 "hidden")


def pcb_vias(d, lines, diameter_mil):
    """Vias of the PCB from the via drill file (pcb.json has none): [(net or None, (x, y) mil, diameter mil)], the
    copper diameter the routing's (vias are created at [routing] via), the net that of the tracks ending on the via –
    None when no track or several nets end there."""
    holes = gerber.parse_holes(d / "gerber" / gerber.FILES["vias"])
    out = []
    for x, y, _, _ in holes:
        v = (x * MIL_PER_MM, y * MIL_PER_MM)
        nets = {ln["Net"] for ln in lines if ln["Net"] and any(
            math.dist(v, e) <= diameter_mil / 2 for e in ((ln["StartX"], ln["StartY"]), (ln["EndX"], ln["EndY"])))}
        out.append((nets.pop() if len(nets) == 1 else None, v, diameter_mil))
    return out


def check_hand_joints(cfg, board, design, d, rows):
    """GEO.spacing with [routing] hand_solder_keep_mm: on the solder side of every through-hole pad of a hand-soldered part
    (bom: false), no via or pad of another net closer than the keep – the pads as `route read` saw them (as GEO.spacing), the
    vias from the via drill file with the net of the tracks of pcb.json that end on them. Tracks do not count. A pair
    waived in the graph (waive GEO.spacing on the joint's part or net, or on the other part or net) is listed with its reason.
    Off (0): no row."""
    from .. import route
    rules = route.Rules(board)
    keep = rules.joint_keep
    if not keep:
        return
    want = f">= {keep * MM:g} mm ([routing] hand_solder_keep_mm)"
    pcb = json.loads((d / "pcb.json").read_text())
    data, why = route.board_as_read(cfg, board, pcb["components"])
    if data is None:
        rows.add("L", "GEO.spacing", board.name, "pad shapes for the hand-soldered joints", False, why, "the PCB as read")
        return
    hand = route.hand_soldered(design.graph, board.name)
    vias = pcb_vias(d, pcb["lines"], rules.via[1])
    gaps = route.joint_gaps(data, keep, hand, vias, route.pad_accepts(design.graph, "GEO.spacing", "joint"))
    bad = [route.joint_text(g, keep, board) for g in gaps if not g["waived"]]
    joints = route.hand_joints(data, hand)
    rows.add("L", "GEO.spacing", board.name, "vias and pads of other nets keep clear of the hand-soldered joints on their "
             "solder side", not bad, "; ".join(bad[:10]) + (f" … ({len(bad)} findings)" if len(bad) > 10 else "")
             or f"{len(joints)} joints of {len({p['ref'] for p, _ in joints})} parts, {len(vias)} vias", want)
    for g in gaps:
        if g["waived"]:
            rows.add("L", "GEO.spacing", board.name, f"hand-soldered joint: {route.joint_text(g, keep, board)}", True,
                     f"{g['mil'] * MM:.2f} mm", want, "waived")
            rows[-1]["reason"] = g["waived"]


def lead_max(lead, tol=True):
    t = (lead.get("tol_mm") or 0) if tol else 0
    a = lead["a_mm"] + t
    b = (lead.get("b_mm") or lead["a_mm"]) + t
    return (a, a) if lead["shape"] == "round" else (min(a, b), math.hypot(a, b))


def hole_ok(lead, width, length):
    """(fits, tight, text). Fits: the lead goes in at nominal size, or the hole is at least what the manufacturer
    recommends. Tight: in the worst case (hole - JLCPCB tolerance, lead + tolerance) less than HOLE_PLAY_MM is left."""
    rec = lead.get("hole_rec_mm")
    by_rec = rec is not None and width >= rec - 1e-6 and length >= (lead.get("hole_rec_b_mm") or rec) - 1e-6
    if lead.get("a_mm") is None:
        return by_rec, False, f"hole {width:.2f} x {length:.2f} mm, manufacturer recommends {rec} mm"
    slot = length > width + 0.01

    def play(tol):
        edge, diag = lead_max(lead, tol)
        w, ln = (width - HOLE_TOL_MM, length - HOLE_TOL_MM) if tol else (width, length)
        return min(w - edge - SLOT_TWIST_MM, ln - diag) if slot else w - diag
    nominal, worst = play(False), play(True)
    edge, diag = lead_max(lead, False)
    text = (f"slot {width:.2f} x {length:.2f} mm for lead {edge:.2f} mm" if slot
            else f"hole {width:.2f} mm for diagonal {diag:.2f} mm")
    text += f", play {nominal:+.2f} mm, worst case {worst:+.2f} mm" + (f", manufacturer {rec} mm" if rec else "")
    return nominal >= 0 or by_rec, worst < HOLE_PLAY_MM and not by_rec, text


def check_drills(board, design, d, rows):
    if lost := gerber.missing(d / "gerber", "pth"):
        rows.add("L", "GEO.hole", board.name, "drill file for the hole check", False, f"{lost[0]} missing (Gerber export)",
                 "present")
        return
    data = json.loads((d / "pcb.json").read_text())
    want = design.board_comps(board.name)
    holes = gerber.parse_holes(d / "gerber" / gerber.FILES["pth"])
    bad, tight, narrow, nodata, n = [], defaultdict(lambda: defaultdict(list)), defaultdict(list), [], 0
    for c in data["components"]:
        pads = [p for p in c["pads"] if p["tht"]]
        if not pads or c.get("designator") not in want:
            continue
        leads = design.parts.get(want[c["designator"]].get("lcsc") or "", {}).get("lead")
        if not leads:
            nodata.append(c["designator"])
            continue
        for pad in pads:
            x, y = pad["X"] * MM, pad["Y"] * MM
            hole = min((h for h in holes if math.hypot(h[0] - x, h[1] - y) < 0.3), key=lambda h: h[2], default=None)
            lead = leads.get(pad["PadNumber"]) or leads.get("*")
            if hole is None or lead is None:
                bad.append(f"{c['designator']}.{pad['PadNumber']}: {'no hole' if hole is None else 'no lead data'}")
                continue
            n += 1
            if hole[3] > hole[2] + 0.01 and hole[2] < JLC_SLOT_MM - 1e-6:
                narrow[c["designator"]].append(f"pad {pad['PadNumber']}: {hole[2]:.2f} x {hole[3]:.2f} mm")
            ok, is_tight, text = hole_ok(lead, hole[2], hole[3])
            if not ok:
                bad.append(f"{c['designator']}.{pad['PadNumber']}: {text}")
            elif is_tight:
                tight[c["designator"]][text].append(pad["PadNumber"])
    rows.add("L", "GEO.hole", board.name, "lead size of every through-hole part in the parts database (field lead)",
             not nodata, ", ".join(nodata) or "all", "all")
    rows.add("L", "GEO.hole", board.name, "hole takes the lead at nominal size (diagonal or edge, or manufacturer's value)",
             not bad, "; ".join(bad[:10]) or f"{n} holes", "play >= 0")
    for ref, by_text in tight.items():  # one warning per part, so an accepted warning covers only that part
        rows.add("L", "GEO.hole", board.name, f"{ref}: tight hole – worst case below {HOLE_PLAY_MM} mm play (hole -{HOLE_TOL_MM} "
                 "mm, lead + tolerance): lead only with force, or the part sits higher", False,
                 "; ".join(f"pad {', '.join(sorted(p, key=natural_key))}: {t}" for t, p in by_text.items()),
                 f">= {HOLE_PLAY_MM} mm", "warn")
    for ref, slots in narrow.items():
        rows.add("L", "GEO.hole", board.name, f"{ref}: slot narrower than {JLC_SLOT_MM} mm (JLCPCB minimum, plated, 2 layers) – "
                 "JLCPCB widens it or asks", False, "; ".join(slots), f">= {JLC_SLOT_MM} mm", "warn")


JLC_RING_MM = 0.18           # GEO.ring, JLCPCB 2 layers 1 oz: PTH annular ring, absolute minimum (fail below)
JLC_RING_WARN_MM = 0.20      # ... the capability value "≧0.20mm" (warn below; recommended 0.25 mm)
JLC_VIA_RING_MM = 0.05       # ... via diameter at least the via hole + 0.1 mm
JLC_PAD_GAP_MM = 0.45        # ... "Pad Hole-to-Hole Spacing", read edge to edge (a component hole is one of the two)
JLC_VIA_GAP_MM = 0.2         # ... "Via Hole-to-Hole Spacing" (two vias), edge to edge
RING_TOL_MM = 0.001          # the files' rounding (EasyEDA keeps mil, writes mm) and the circle polygons (64 a quarter)
RING_REACH_MM = 1.0          # a ring is measured up to this width – wider is wide enough


def drill_axis(h):
    """A drilled hole (x0, y0, x1, y1, width) as its centre point, or a slot as the line between its two ends."""
    from shapely.geometry import LineString, Point
    return Point(h[0], h[1]) if (h[0], h[1]) == (h[2], h[3]) else LineString([h[:2], h[2:4]])


def ring_mm(parts, hole):
    """Narrowest copper around a drilled hole on one layer: from the hole's edge to the nearest point without copper
    (mm, at most RING_REACH_MM); None when no copper covers the hole's centre. Pad, track and pour count alike – it is
    the copper the plating sits in. parts: [(bounds, area)] per Gerber operation of the layer."""
    import shapely
    from shapely.geometry import box
    axis, half = drill_axis(hole), hole[4] / 2
    x0, y0, x1, y1 = axis.bounds
    m = half + RING_REACH_MM
    win = (x0 - m, y0 - m, x1 + m, y1 + m)
    near = [g.intersection(box(*win)) for b, g in parts
            if b[0] <= win[2] and b[2] >= win[0] and b[1] <= win[3] and b[3] >= win[1]]
    centre = axis.interpolate(0.5, normalized=True) if axis.geom_type == "LineString" else axis
    pieces = shapely.get_parts(shapely.unary_union(near)) if near else []
    piece = next((q for q in pieces if q.geom_type == "Polygon" and q.covers(centre)), None)
    return None if piece is None else piece.boundary.distance(axis) - half


def check_rings(board, design, d, rows):
    """GEO.ring: every plated hole keeps JLCPCB's annular ring on TOP and BOTTOM (2 layers, 1 oz: a component hole 0.18 mm,
    warning below 0.20 mm; a via 0.05 mm, via Ø >= hole + 0.1 mm), and every two plated holes – also two of one part –
    keep JLCPCB's hole-to-hole spacing, edge to edge (0.45 mm when a component hole is one of them, 0.2 mm between two
    vias). Vias are the holes of the via drill file (EasyEDA writes them into the PTH file as well); the other plated
    holes are named by the through-hole pad of pcb.json at their place. The ring is the copper around the hole in the
    Gerber files, whatever it belongs to. accept {"GEO.ring": …} (or "GEO.spacing:holes") on a part or net of the graph lists them as accepted."""
    g = d / "gerber"
    if lost := gerber.missing(g, "top", "bottom", "pth"):
        rows.add("L", "GEO.ring", board.name, "Gerber and drill files for the annular rings", False,
                 f"{', '.join(lost)} missing (Gerber export)", "present")
        return
    from shapely import STRtree

    from .. import route
    vias = list(dict.fromkeys(gerber.parse_drills(g / gerber.FILES["vias"])))
    at_via = {(round(h[0], 3), round(h[1], 3)) for h in vias}
    pth = [h for h in dict.fromkeys(gerber.parse_drills(g / gerber.FILES["pth"]))
           if (round(h[0], 3), round(h[1], 3)) not in at_via]
    pads = [(f"{c['designator']}.{p['PadNumber']}", c["designator"], p.get("Net") or "", p["X"] * MM, p["Y"] * MM)
            for c in json.loads((d / "pcb.json").read_text())["components"] if c.get("designator")
            for p in c["pads"] if p["tht"]]
    holes = []                   # (hole, name, part, net, via)
    for h in pth:
        x, y = drill_axis(h).centroid.coords[0]
        pad = min(pads, key=lambda p: math.hypot(p[3] - x, p[4] - y), default=None)
        if pad and math.hypot(pad[3] - x, pad[4] - y) < 0.3:
            holes.append((h, pad[0], pad[1], pad[2], False))
        else:
            holes.append((h, f"plated hole at ({x:.2f}, {y:.2f})", "", "", False))
    holes += [(h, f"via at ({h[0]:.2f}, {h[1]:.2f})", "", "", True) for h in vias]
    ring_acc = route.pad_accepts(design.graph, "GEO.ring")
    gap_acc = route.pad_accepts(design.graph, "GEO.spacing", "holes")

    def waiver(*items, acc=ring_acc):
        parts_of, nets_of = acc
        return next((parts_of.get(p) or nets_of.get(n) for _, _, p, n, _ in items if parts_of.get(p) or nets_of.get(n)),
                    None)

    def size(h):
        return f"Ø {h[4]:.2f} mm" if h[:2] == h[2:4] else \
            f"{h[4]:.2f} x {h[4] + math.hypot(h[2] - h[0], h[3] - h[1]):.2f} mm"
    copper = {name: [(a.bounds, a) for a in (gerber.shape([op], 64) for op in gerber.parse_gerber(g / gerber.FILES[k]))
                      if not a.is_empty] for name, k in (("TOP", "top"), ("BOTTOM", "bottom"))}
    narrow, low, waived, narrowest = [], defaultdict(lambda: defaultdict(list)), [], {}   # narrowest: via? -> ring
    for item in holes:
        h, name, part, _, is_via = item
        rings = {layer: ring_mm(parts, h) for layer, parts in copper.items()}
        none = [layer for layer, r in rings.items() if r is None]
        least = min((r for r in rings.values() if r is not None), default=None)
        where = " and ".join(layer for layer, r in rings.items() if r is not None and abs(r - least) < RING_TOL_MM)
        limit = JLC_VIA_RING_MM if is_via else JLC_RING_MM
        if none:
            text, value = f"{name}: no copper around the hole on {' and '.join(none)} (hole {size(h)})", "no copper"
        elif least + RING_TOL_MM < limit:
            text, value = f"{name}: {least:.3f} mm on {where} (hole {size(h)})", f"{least:.3f} mm"
        else:
            if not is_via and least + RING_TOL_MM < JLC_RING_WARN_MM:
                low[part or name][f"{least:.3f} mm on {where} (hole {size(h)})"].append(name.partition(".")[2] or name)
            if is_via not in narrowest or least < narrowest[is_via][0]:
                narrowest[is_via] = (least, name)
            continue
        if reason := waiver(item):
            waived.append(("annular ring", text, value, f">= {limit} mm", reason))
        else:
            narrow.append(text)
    n_via = sum(1 for *_, v in holes if v)
    count = [f"{len(holes) - n_via} holes", f"{n_via} vias"]
    for k, (ring, name) in narrowest.items():
        count[k] += f" (narrowest ring {ring:.3f} mm" + ("" if k else f", {name}") + ")"
    narrow.sort(key=natural_key)
    rows.add("L", "GEO.ring", board.name, f"plated holes keep JLCPCB's annular ring: component holes {JLC_RING_MM} mm, vias "
             f"{JLC_VIA_RING_MM} mm (2 layers, 1 oz)", not narrow, "; ".join(narrow[:10])
             + (f" … ({len(narrow)} holes)" if len(narrow) > 10 else "") or ", ".join(count),
             f">= {JLC_RING_MM} mm (component hole), >= {JLC_VIA_RING_MM} mm (via)")
    for ref, by_text in low.items():   # one warning per part, so an accepted warning covers only that part
        reason = waiver(*(item for item in holes if item[2] == ref))
        rows.add("L", "GEO.ring", board.name, f"{ref}: annular ring below {JLC_RING_WARN_MM} mm – JLCPCB's capability value "
                 "(recommended 0.25 mm)", False, "; ".join(f"pad {', '.join(sorted(p, key=natural_key))}: {t}"
                                                         for t, p in by_text.items()),
                 f">= {JLC_RING_WARN_MM} mm", "waived" if reason else "warn")
        if reason:
            rows[-1]["reason"] = reason
    geoms = [drill_axis(h) for h, *_ in holes]
    tree, reach = STRtree(geoms), max((h[4] for h, *_ in holes), default=0) + RING_REACH_MM + JLC_PAD_GAP_MM
    close, kept = [], []
    for i, a in enumerate(holes):
        for j in sorted(tree.query(geoms[i].buffer(reach))):
            if j <= i:
                continue
            b = holes[j]
            gap = geoms[i].distance(geoms[j]) - (a[0][4] + b[0][4]) / 2
            limit = JLC_VIA_GAP_MM if a[4] and b[4] else JLC_PAD_GAP_MM
            if gap + RING_TOL_MM >= limit:
                kept.append((gap, f"{a[1]} – {b[1]}"))
            elif reason := waiver(a, b, acc=gap_acc):
                waived.append(("hole spacing", f"{a[1]} – {b[1]}: {gap:.3f} mm apart, below {limit:.2f} mm",
                               f"{gap:.3f} mm", f">= {limit} mm", reason))
            else:
                close.append(f"{a[1]} – {b[1]}: {gap:.3f} mm apart, below {limit:.2f} mm")
    least = min(kept, default=None)
    rows.add("L", "GEO.spacing", board.name, f"plated holes at least JLCPCB's hole-to-hole spacing apart, edge to edge: "
             f"{JLC_PAD_GAP_MM} mm with a component hole, {JLC_VIA_GAP_MM} mm between vias", not close,
             "; ".join(close[:10]) + (f" … ({len(close)} pairs)" if len(close) > 10 else "")
             or (f"closest {least[0]:.3f} mm ({least[1]})" if least else f"{len(holes)} holes, none near another"),
             f">= {JLC_PAD_GAP_MM} mm, between vias >= {JLC_VIA_GAP_MM} mm")
    for what, text, value, want, reason in sorted(waived, key=lambda w: natural_key(w[1])):
        rows.add("L", "GEO.spacing" if what == "hole spacing" else "GEO.ring", board.name, f"{what}: {text}", True,
                 value, want, "waived")
        rows[-1]["reason"] = reason


def loop_length_mm(data, a, b, snap=0.5, pad_mm=0.9):
    """Shortest path (mm) from pad a to pad b over tracks of their net on their layer; None without a connection.
    Pours do not count: the loop is supposed to be closed by a track, not by a detour through a plane."""
    import heapq
    pads = {f"{c['designator']}.{p['PadNumber']}": p for c in data["components"] for p in c["pads"]}
    pa, pb = pads[a], pads[b]
    if pa["Net"] != pb["Net"]:
        raise ValueError(f"{a} and {b}: different nets")
    layer = pa["Layer"] if pa["Layer"] != MULTI else pb["Layer"]
    graph = defaultdict(list)

    def key(x, y):
        return round(x / snap) * snap, round(y / snap) * snap
    for ln in data["lines"]:
        if ln["Net"] == pa["Net"] and (ln["Layer"] == layer or layer == MULTI):
            u, v = key(ln["StartX"], ln["StartY"]), key(ln["EndX"], ln["EndY"])
            w = math.dist(u, v) * MM
            graph[u].append((v, w))
            graph[v].append((u, w))
    near = lambda p: [n for n in graph if math.dist(n, (p["X"], p["Y"])) * MM <= pad_mm]  # noqa: E731
    dist, todo = {}, [(0.0, n) for n in near(pa)]
    goal = set(near(pb))
    while todo:
        dd, n = heapq.heappop(todo)
        if n in dist:
            continue
        dist[n] = dd
        if n in goal:
            return round(dd, 1)
        for m, w in graph[n]:
            if m not in dist:
                heapq.heappush(todo, (dd + w, m))
    return None


def check_loops(board, design, d, rows):
    """GEO.loop over the loops of the plan and those the circuit hands over (layout.loops of the graph). A pad that is not
    in the PCB, or two pads on different nets there, is a finding of the loop (SYNC.pcb names the cause)."""
    loops = board.loops + handover.loops(design, board.name)
    if not loops:
        return
    data = json.loads((d / "pcb.json").read_text())
    net = {f"{c['designator']}.{p['PadNumber']}": p["Net"] for c in data["components"] for p in c["pads"]}
    found, bad = [], []
    for a, b, limit, what in loops:
        if lost := [p for p in (a, b) if p not in net]:
            bad.append(f"{a}-{b} ({what}): {', '.join(lost)} not in the PCB")
        elif net[a] != net[b]:
            bad.append(f"{a}-{b} ({what}): different nets ({net[a] or '–'}, {net[b] or '–'})")
        else:
            mm = loop_length_mm(data, a, b)
            found.append(f"{a}-{b} {mm} mm")
            if mm is None or mm > limit:
                bad.append(f"{a}-{b} ({what}): " + ("no track" if mm is None else f"{mm} mm") + f" > {limit} mm")
    rows.add("L", "GEO.loop", board.name, "short current loops: path over tracks per pad pair within the limit", not bad,
             "; ".join(bad) or "; ".join(found), ", ".join(f"{a}-{b} <= {limit} mm" for a, b, limit, _ in loops))


def check_copper(board, design, d, rows):
    """GEO.copper on the Gerber files; -> the Copper raster (None when the files are missing) for GEO.spacing/apart."""
    if lost := gerber.missing(d / "gerber", "top", "bottom", "pth", "probe"):
        rows.add("L", "GEO.copper", board.name, "Gerber and drill files for the copper check", False,
                 f"{', '.join(lost)} missing (Gerber export)", "present")
        return None
    with contextlib.redirect_stdout(io.StringIO()):
        cu = gerber.Copper(d / "gerber", design.pin_net)
    want = design.board_comps(board.name)
    nets = defaultdict(list)
    for p, n in design.pin_net.items():
        if p.split(".")[0] in want:
            nets[n].append(p)
    have = {name.replace("_", ".", 1) for name in cu.pins}
    lost = sorted((p for ps in nets.values() if len(ps) > 1 for p in ps if p not in have), key=natural_key)
    rows.add("L", "GEO.copper", board.name, "every connected pad is in the manufacturing files", not lost,
             ", ".join(lost[:15]) or f"{len(have)} pads", "all")
    broken = []
    for net, ps in sorted(nets.items()):
        if len(ps) > 1 and len(groups := cu.net_groups(net)) > 1:
            broken.append(f"{net}: {len(groups)} groups ({' | '.join(', '.join(g[:4]) for g in groups[:3])})")
    rows.add("L", "GEO.copper", board.name, "copper from the Gerber files: every net connected", not broken,
             "; ".join(broken[:8]) or f"{sum(len(p) > 1 for p in nets.values())} nets complete", "1 group per net")
    shorts = [f"{' + '.join(n)} ({', '.join(p[:4])})" for n, p in cu.shorts]
    rows.add("L", "GEO.copper", board.name, "copper from the Gerber files: no short between nets", not shorts,
             "; ".join(shorts[:8]) or "none", "none")
    return cu


KEEPOUT_SPOT_MM2 = 0.01     # GEO.keepout: less copper than this inside the area is the raster's rounding


def keepout_polygon(c, box):
    """The corners (mm, the Gerber frame) of a keep-out box [x0, y0, x1, y1] given in a part's footprint frame (mm,
    rotation 0 on top), for the part c of pcb.json – EasyEDA mirrors local y on the bottom, then rotates."""
    x0, y0, x1, y1 = box
    a = math.radians(c["rotation"])
    out = []
    for lx, ly in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        if str(c.get("layer")) in ("2", "BOTTOM"):
            ly = -ly
        out.append((c["x"] * MM + lx * math.cos(a) - ly * math.sin(a), c["y"] * MM + lx * math.sin(a) + ly * math.cos(a)))
    return out


def check_keepout(board, design, d, cu, rows):
    """GEO.keepout: no copper of the board, on either layer, inside the antenna keep-out a part's entry gives
    (antenna.keepout_mm) – on the raster of GEO.copper, the area placed where the part sits in pcb.json. A part without
    the field is not checked (edakit check --coverage names the radios without it); without the Gerber files the
    part is listed as not checked. A warning while new."""
    import numpy as np
    from PIL import Image, ImageDraw
    want = design.board_comps(board.name)
    boxes = {ref: (design.part(ref) or {}).get("antenna", {}).get("keepout_mm") for ref in want
             if isinstance((design.part(ref) or {}).get("antenna"), dict)}
    boxes = {ref: b for ref, b in boxes.items() if b}
    if not boxes:
        return
    on_pcb = {c["designator"]: c for c in json.loads((d / "pcb.json").read_text())["components"] if c.get("designator")}
    for ref, box in sorted(boxes.items(), key=lambda x: natural_key(x[0])):
        what = f"{ref}: no copper inside the antenna keep-out of its parts entry (antenna.keepout_mm)"
        if ref not in on_pcb:
            continue
        if cu is None:
            rows.add("L", "GEO.keepout", board.name, what, True, "not checked: the Gerber files are missing", "none",
                     "info")
            continue
        poly = keepout_polygon(on_pcb[ref], box)
        img = Image.new("1", (cu.w, cu.h), 0)
        ImageDraw.Draw(img).polygon([cu.px(x, y) for x, y in poly], fill=1)
        area = np.array(img, dtype=bool)
        hit = {k: float((area & (cu.lab[k] > 0)).sum()) * gerber.RES ** 2 for k in "TB"}
        bad = {k: a for k, a in hit.items() if a > KEEPOUT_SPOT_MM2}
        actual = ", ".join(f"{a:.2f} mm² on {'TOP' if k == 'T' else 'BOTTOM'}" for k, a in bad.items()) or "free"
        rows.add("L", "GEO.keepout", board.name, what, not bad, actual, "no copper", None if not bad else "warn")


def check_apart(board, design, cu, rows):
    """GEO.spacing/apart: the pairs of layout.apart whose nets are on this board keep min_mm between their copper on
    every layer, measured on the raster of GEO.copper – a warning while new; without the Gerber files the pair is
    listed as not checked."""
    from ..handover import layout
    mine = design.board_comps(board.name)
    on_board = {n for n, net in design.nets.items() if any(r.partition(".")[0] in mine for r in net["pins"])}
    for ap in layout(design).get("apart", []):
        a, b, least = ap.get("a"), ap.get("b"), ap.get("min_mm")
        if a not in on_board or b not in on_board:
            continue
        what = f"{a} and {b} at least {least:g} mm apart (layout.apart{': ' + ap['what'] if ap.get('what') else ''})"
        if cu is None:
            rows.add("L", "GEO.spacing", board.name, what, True, "not checked: the Gerber files are missing", f">= {least:g} mm",
                     "info")
            continue
        found = cu.distance(a, b)
        if found is None:
            rows.add("L", "GEO.spacing", board.name, what, True, "no layer with copper of both", f">= {least:g} mm")
            continue
        gap, x, y, layer = found
        ok = gap >= least - gerber.RES
        rows.add("L", "GEO.spacing", board.name, what, ok, f"{gap:.2f} mm on {layer} at ({x:.1f}, {y:.1f})",
                 f">= {least:g} mm", None if ok else "warn")


BARE_STEP = 5                # GEO.pour: the copper-free circle is measured on blocks of 5 x 5 raster points (0.1 mm)


def free_circle(free, step=BARE_STEP):
    """Largest circle inside the True area of a raster: (diameter, row, column) in raster points, measured on blocks
    of step x step points that are free throughout (so never larger than the truth, at most a block smaller)."""
    import numpy as np
    from scipy import ndimage
    h, w = free.shape[0] // step * step, free.shape[1] // step * step
    blocks = free[:h, :w].reshape(h // step, step, w // step, step).all(axis=(1, 3))
    if not blocks.any():
        return 0.0, 0, 0
    dist = ndimage.distance_transform_edt(blocks)
    r, c = np.unravel_index(np.argmax(dist), dist.shape)
    return 2 * dist[r, c] * step, (r + 0.5) * step, (c + 0.5) * step


def check_copper_sides(board, design, d, rows):
    """GEO.pour: copper per layer from the Gerber files on the raster of GEO.copper, widened to the outline. Per layer the copper
    share of the board area (outline without mounting and NPTH holes) and the largest copper-free circle inside
    the pour outline (pcb.pour_outline, as `pcb pour` pours): information on a layer without pour, a warning above
    [copper] max_bare_mm on a layer the board file pours ([[pours]], default GND on both) – a pour EasyEDA left empty
    where its net has no pad, or never filled. A share below [copper] min_cover warns. On every layer a copper piece that
    touches no pad (FlyingProbeTesting.json), via or plated hole warns: an island left by a fill with islands kept.
    Copper inside an NPTH or mounting hole is drilled away and does not count."""
    g = d / "gerber"
    if lost := gerber.missing(g, "top", "bottom", "probe"):
        rows.add("L", "GEO.pour", board.name, "Gerber files for the copper per side", False,
                 f"{', '.join(lost)} missing (Gerber export)", "present")
        return
    import numpy as np
    from PIL import Image, ImageDraw
    from scipy import ndimage

    from .. import pcb
    with contextlib.redirect_stdout(io.StringIO()):
        pour = [board.eda_point(*p) for p in pcb.pour_outline(board)]
        outline = [board.eda_point(*p) for p in board.outline]
        cu = gerber.Copper(g, design.pin_net, extent=outline)
    res = gerber.RES

    def area(poly, cut=()):
        """The polygon without the circles (x, y, r) – or, without a polygon, the circles alone."""
        img = Image.new("1", (cu.w, cu.h), 0)
        dr = ImageDraw.Draw(img)
        if poly:
            dr.polygon([cu.px(*q) for q in poly], fill=1)
        for x, y, r in cut:
            (cx, cy), rr = cu.px(x, y), r / res
            dr.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=0 if poly else 1)
        return np.array(img, dtype=bool)
    drilled = area([], [(x, y, w / 2) for x, y, w, _ in gerber.parse_holes(g / gerber.FILES["npth"])]
                   + [(*board.eda_point(h["x"], h["y"]), h["d"] / 2) for h in board.holes])   # NPTH, mounting holes
    whole = area(outline) & ~drilled
    inside = area(pour) & ~drilled
    probe = json.loads((g / gerber.FILES["probe"]).read_text())["pins"]
    anchors = {"T": [], "B": []}       # (x, y, r): pads of FlyingProbeTesting.json (all of them), plated holes and vias
    for row in probe["rows"]:
        p = dict(zip(probe["fields"], row))
        r = min(p["PAD_SIZEX"], p["PAD_SIZEY"]) / MIL_PER_MM / 4
        for k in ("TB" if p["PIN_TYPE"] != "SMD" else "T" if p["LAYER"] in ("T", "TOP") else "B"):
            anchors[k].append((p["PIN_X"] / MIL_PER_MM, p["PIN_Y"] / MIL_PER_MM, r))
    for x, y, w in cu.holes:
        for k in "TB":
            anchors[k].append((x, y, w / 2 + 0.05))
    poured = defaultdict(list)
    for p in board.pours:
        for layer in p.get("layers", ["TOP", "BOTTOM"]):
            poured[layer].append(p["net"])
    limit, cover = board.copper["max_bare_mm"], board.copper["min_cover"]
    for k, layer in (("T", "TOP"), ("B", "BOTTOM")):
        copper = cu.render(cu.ops[k]) & ~drilled
        share = 100 * (copper & whole).sum() / max(1, whole.sum())
        dia, r, c = free_circle(inside & ~copper)
        dia *= res
        at = f"({cu.x0 + c * res:.1f}, {cu.y0 + (cu.h - r) * res:.1f}) mm"
        text = f"{share:.0f} % copper, largest copper-free circle Ø {dia:.1f} mm" + (f" at {at}" if dia else "")
        if poured[layer]:
            rows.add("L", "GEO.pour", board.name, f"{layer}: no copper-free circle above {limit:g} mm inside the pour "
                     f"outline (poured: {', '.join(poured[layer])})", dia <= limit, f"{layer}: {text}",
                     f"Ø <= {limit:g} mm ([copper] max_bare_mm)", None if dia <= limit else "warn")
        else:
            rows.add("L", "GEO.pour", board.name, f"{layer}: copper share and largest copper-free circle (no pour)", True,
                     f"{layer}: {text}", "information", "info")
        if layer in cover:
            rows.add("L", "GEO.pour", board.name, f"{layer}: copper share at least {cover[layer]:g} % ([copper] min_cover)",
                     share >= cover[layer], f"{layer}: {share:.0f} % copper", f">= {cover[layer]:g} %",
                     None if share >= cover[layer] else "warn")
        lab, n = ndimage.label(copper, structure=np.ones((3, 3)))
        held = set()
        for x, y, rad in anchors[k]:
            (cx, cy), rr = cu.px(x, y), max(1, int(rad / res))
            held |= set(np.unique(lab[max(0, int(cy) - rr):int(cy) + rr + 1, max(0, int(cx) - rr):int(cx) + rr + 1]))
        size = np.bincount(lab.ravel(), minlength=n + 1) * res * res
        loose = sorted((i for i in range(1, n + 1) if i not in held), key=lambda i: -size[i])
        where, boxes = [], ndimage.find_objects(lab) if loose else []
        for i in loose[:5]:
            rs, cs = boxes[i - 1]
            x = cu.x0 + (cs.start + cs.stop) / 2 * res
            y = cu.y0 + (cu.h - (rs.start + rs.stop) / 2) * res
            where.append(f"{size[i]:.1f} mm² around ({x:.1f}, {y:.1f}) mm")
        many = f"{len(loose)} pieces, {sum(size[i] for i in loose):.1f} mm² together" if len(loose) > 1 else "1 piece"
        rows.add("L", "GEO.pour", board.name, f"{layer}: every copper piece touches a pad, via or plated hole", not loose,
                 f"{layer}: {many} without pad, via or hole: " + "; ".join(where) + (" …" if len(loose) > 5 else "")
                 if loose else f"{layer}: {n} pieces", "none loose", None if not loose else "warn")


# --- F checks -----------------------------------------------------------------------------------------------------

def check_fab(cfg, board, design, d, rows):
    want = design.board_comps(board.name)
    bom = bom_rows(design, board)
    write_bom(bom, d / f"bom_{board.name}.csv")
    write_mpn_bom(cfg, design, board, bom, d)          # a maker that matches by MPN (Eurocircuits)
    ours = {ref: r["LCSC Part #"] for r in bom for ref in r["Designator"].split(",")}
    tool = "KiCad" if is_kicad(cfg) else "EasyEDA"
    eda_bom = {ref.strip(): e["lcsc"] for e in json.loads((d / f"bom_{tool.lower()}.json").read_text())
               for ref in e["reference"].split(",") if ref.strip() in want}
    diff = [f"{r}: graph {ours.get(r, '–')}, {tool} {eda_bom.get(r, '–')}" for r in sorted(set(ours) | set(eda_bom), key=natural_key)
            if ours.get(r) != eda_bom.get(r) and not (r not in ours and want[r].get("bom") is False)]
    rows.add("F", "SYNC.bom", board.name, f"BOM (from the graph) = BOM of {tool}, LCSC per designator", not diff,
             "; ".join(diff[:10]) or f"{len(ours)} parts in {len(bom)} lines", "equal")
    unknown = sorted({lc for lc in ours.values() if lc not in design.parts})
    rows.add("F", "SYNC.bom", board.name, "every LCSC number of the BOM is in the parts database", not unknown,
             ", ".join(unknown) or "all", "all")
    from .. import makers
    users = makers.with_catalogue(cfg, "jlcpcb")     # PARTS.stock: for the maker that orders from JLCPCB's catalogue
    if users:
        check_catalogue(cfg, board, design, d, bom, rows, users[0])
    check_cpl(cfg, board, design, d, ours, rows)


def check_catalogue(cfg, board, design, d, bom, rows, maker):
    """PARTS.stock for a maker that orders from JLCPCB's catalogue: fails for the planned maker, warns for another one."""
    from .. import makers
    other_maker = maker != makers.planned(cfg)
    who_of = f"{makers.get(cfg, maker).name} (not the planned maker): " if other_maker else ""
    jlc_file = d / "jlc_parts.json"
    if not jlc_file.exists():
        fetch_jlc(bom, d)
    jlc, bad, other = json.loads(jlc_file.read_text()), [], []
    for r in bom:
        n, hit = len(r["Designator"].split(",")) * cfg.quantity, jlc.get(r["LCSC Part #"])
        who, entry = f"{r['Designator']} {r['LCSC Part #']}", design.parts.get(r["LCSC Part #"]) or {}
        if not hit:
            bad.append(f"{who}: not in the catalogue (pre-order only)")
            continue
        if hit.get("error"):
            bad.append(f"{who}: catalogue not reachable ({hit['error'][:60]})")
            continue
        if (hit.get("stockCount") or 0) < n:
            bad.append(f"{who}: {hit.get('stockCount')} in stock, {n} needed")
        if entry.get("mpn") and hit.get("componentModelEn") and not stock.same_mpn(entry["mpn"], hit["componentModelEn"]):
            bad.append(f"{who}: JLCPCB names it {hit['componentModelEn']}, the parts entry {entry['mpn']}")
        cls = stock.CLASS.get(hit.get("componentLibraryType"), hit.get("componentLibraryType"))
        if stock.class_differs(cls, hit.get("preferredComponentFlag"), entry.get("jlc_class")):
            other.append(f"{who}: JLCPCB lists it as {cls}, the parts entry as {entry['jlc_class']}")
    rows.add("F", "PARTS.stock", board.name, f"every BOM part in JLCPCB's assembly catalogue, stock for {cfg.quantity} boards, "
             "the MPN of its parts entry", not bad, who_of + "; ".join(bad) if bad else f"{len(bom)} lines listed and "
             "in stock", "all", makers.result(cfg, maker, not bad))
    rows[-1]["maker"] = maker
    if other:
        rows.add("F", "PARTS.stock", board.name, "catalogue class = jlc_class of the parts entry", False,
                 who_of + "; ".join(other), "equal", "warn")
        rows[-1]["maker"] = maker


def check_cpl(cfg, board, design, d, ours, rows):
    """SYNC.cpl and FILES.set: pick and place against the PCB, the Gerber set, outline and tooling holes."""
    if is_kicad(cfg):                     # kicad-cli's position file in the columns of EasyEDA's CPL
        from ..toolchain.kicad import fab as kicad_fab
        cpl = kicad_fab.read_cpl(d / "cpl_kicad.csv")
    else:
        import openpyxl
        ws = openpyxl.load_workbook(d / "cpl_easyeda.xlsx", read_only=True).worksheets[0]
        rx = list(ws.iter_rows(values_only=True))
        cpl = [dict(zip(rx[0], r)) for r in rx[1:] if r and r[0]]
    count = Counter(r["Designator"] for r in cpl)
    data = {c["designator"]: c for c in json.loads((d / "pcb.json").read_text())["components"] if c.get("designator")}
    probs = [f"{r}: {count[r]}x" for r in sorted(ours, key=natural_key) if count[r] != 1]
    side = {"T": TOP, "B": BOTTOM}
    probs += [f"{r['Designator']}: side {r['Layer']} differs from the PCB" for r in cpl
              if r["Designator"] in ours and r["Designator"] in data and side.get(r["Layer"]) != data[r["Designator"]]["layer"]]
    probs += [f"{r['Designator']}: rotation {r['Rotation']} differs from the PCB" for r in cpl if r["Designator"] in ours
              and r["Designator"] in data and abs((float(r["Rotation"]) - data[r["Designator"]]["rotation"] + 180) % 360 - 180) > 0.01]
    rows.add("F", "SYNC.cpl", board.name, "pick and place: every BOM part exactly once, side and rotation = PCB", not probs,
             "; ".join(probs[:10]) or f"{len(ours)} parts", "exactly once, equal")
    with open(d / f"cpl_{board.name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in sorted((r for r in cpl if r["Designator"] in ours), key=lambda r: natural_key(r["Designator"])):
            w.writerow([r["Designator"], r["Mid X"], r["Mid Y"], "Top" if r["Layer"] == "T" else "Bottom", r["Rotation"]])
    assembly = cfg.release.get("assembly", {})
    mix = Counter((r["Layer"], "SMD" if r.get("SMD") == "Yes" else "THT") for r in cpl if r["Designator"] in ours)
    allowed = {("T" if s == "top" else "B", k) for s in assembly.get("sides", ["top", "bottom"])
               for k in (("SMD",) if assembly.get("smd_only") else ("SMD", "THT"))}
    rows.add("F", "SYNC.cpl", board.name, f"assembly only on {', '.join(assembly.get('sides', ['top', 'bottom']))}"
             + (", SMD only" if assembly.get("smd_only") else "") + " ([release] assembly)", set(mix) <= allowed,
             ", ".join(f"{'Top' if s == 'T' else 'Bottom'} {k} {n}" for (s, k), n in sorted(mix.items())), str(sorted(allowed)))
    g = d / "gerber"
    lost = gerber.missing(g, *gerber.REQUIRED)
    rows.add("F", "FILES.set", board.name, "Gerber set complete (copper, silk, mask, outline, drills)", not lost,
             ", ".join(lost) or f"{len(gerber.REQUIRED)} files", "all")
    if not lost:
        check_outline(board, g, rows)
        check_tooling(board, g, rows)


# --- SYNC.odb: the ODB++ export against the run's files ----------------------------------------------------------------------

ODB_POS_MM = 0.01            # SYNC.odb: a part's place against the CPL
ODB_HOLE_MM = 0.001          # SYNC.odb: a drill hit's place and diameter against the drill files
ODB_PROFILE_MM = 0.05        # SYNC.odb: the profile against the Gerber outline (Hausdorff distance)
ROLES = (("TopLayer", ("copper", "top")), ("BottomLayer", ("copper", "bottom")), ("TopSolderMask", ("mask", "top")),
         ("BottomSolderMask", ("mask", "bottom")), ("TopSilkscreen", ("silk", "top")),
         ("BottomSilkscreen", ("silk", "bottom")), ("TopPaste", ("paste", "top")), ("BottomPaste", ("paste", "bottom")))
ODB_KIND = {"SIGNAL": "copper", "POWER_GROUND": "copper", "MIXED": "copper", "SOLDER_MASK": "mask",
            "SILK_SCREEN": "silk", "SOLDER_PASTE": "paste"}


def gerber_role(f):
    """What a Gerber file of EasyEDA's export is: (kind, side) – copper, mask, silk, paste of top or bottom, an inner
    copper layer (copper, "inner <n>") –, "outline", or None."""
    name = f.name
    if "BoardOutline" in name:
        return "outline"
    m = re.search(r"Inner(?:Layer)?(\d+)", name)
    if m:
        return ("copper", f"inner {m.group(1)}")
    return next((role for key, role in ROLES if key in name), None)


def odb_roles(job):
    """{(kind, side): layer} of the ODB++ board layers: the copper layers in matrix order are top, inner 1 …, bottom;
    mask, silk and paste above the top copper are of the top, below the bottom copper of the bottom."""
    copper = [lay for lay in job.board_layers() if ODB_KIND.get(lay.type) == "copper"]
    out = {}
    for i, lay in enumerate(copper):
        side = "top" if i == 0 else "bottom" if i == len(copper) - 1 else f"inner {i}"
        out[("copper", side)] = lay
    if copper:
        first, last = copper[0].row, copper[-1].row
        for lay in job.board_layers():
            kind = ODB_KIND.get(lay.type)
            if kind and kind != "copper":
                side = "top" if lay.row < first else "bottom" if lay.row > last else None
                if side and (kind, side) not in out:
                    out[(kind, side)] = lay
    return out


def check_odb(cfg, board, design, d, rows):
    """SYNC.odb for a maker of [cart] makers that takes ODB++ (AISLER): every layer, the drill hits, the profile, the parts
    and the nets of odb_<b>.zip against this run's Gerber, drill, BOM and CPL files and the graph – fails for the
    planned maker, warns for another one."""
    from .. import makers, odb
    takers = odb_takers(cfg)
    if not takers:
        return
    m = takers[0]
    who = "" if m.key == makers.planned(cfg) else f"{m.name} (not the planned maker): "

    def add(check, ok, actual, expected, level=None):
        rows.add("F", "SYNC.odb", board.name, check, ok, actual if ok or not who else who + str(actual), expected,
                 level or makers.result(cfg, m.key, ok))
        rows[-1]["maker"] = m.key
    path = d / f"odb_{board.name}.zip"
    if not path.exists():
        why = (d / ODB_ERROR).read_text() if (d / ODB_ERROR).exists() else "not exported"
        add(f"ODB++ of this run for {m.name}", False, f"{path.name}: {why}", "exported")
        return
    try:
        job = odb.read(path)
    except odb.OdbError as e:
        add(f"ODB++ of this run for {m.name}", False, str(e), "readable")
        return
    g = d / "gerber"
    gerbers, drills = built_files(g)
    roles = odb_roles(job)
    r = frame(g, gerbers)
    bad, seen = [], set()
    for f in gerbers:
        role = gerber_role(f)
        if role == "outline":
            continue
        lay = roles.get(role)
        if lay is None:
            bad.append(f"{f.name}: no layer of the ODB++ is the {' '.join(role) if role else 'same'}")
            continue
        seen.add(lay.name)
        xor = r.render(gerber.parse_gerber(f)) ^ odb.render(r, lay.features)
        found = [s for s in spots(xor, r) if s[0] >= SPOT_MM2]
        if found:
            a, (x0, x1, y0, y1) = found[0]
            bad.append(f"{f.name} ≠ {lay.name}: {len(found)} spots, the largest {a:.3f} mm² at ({(x0 + x1) / 2:.2f}, "
                       f"{(y0 + y1) / 2:.2f})")
    bad += [f"{lay.name}: in the ODB++, no Gerber layer of the run" for role, lay in roles.items() if lay.name not in seen]
    add("every layer of the ODB++ = the Gerber layer of the run (copper, mask, paste, silkscreen; raster XOR)", not bad,
        "; ".join(bad[:6]) or f"{len(seen)} layers equal (no spot above {SPOT_MM2} mm²)", "equal")

    # each hole once: EasyEDA writes a via into the PTH file and into a via file of its own
    want = sorted({(round(x, 3), round(y, 3), round(w, 3), "non_plated" if "NPTH" in f.name else "plated")
                   for f in drills for x, y, w, _ in gerber.parse_holes(f)})
    got = sorted({(round(x, 3), round(y, 3), round(dia, 3), "plated" if kind == "via" else kind)
                  for lay in job.of_type("DRILL") for x, y, dia, kind in lay.holes})
    lost = [h for h in want if not any(abs(h[0] - o[0]) <= ODB_HOLE_MM and abs(h[1] - o[1]) <= ODB_HOLE_MM
                                       and abs(h[2] - o[2]) <= ODB_HOLE_MM and h[3] == o[3] for o in got)]
    extra = len(got) - (len(want) - len(lost))
    add("drill holes of the ODB++ = the drill files (place 1 µm, diameter, plated or not)", not lost and extra == 0,
        f"{len(got)} holes" if not lost and extra == 0 else
        "; ".join([f"({h[0]:.3f}, {h[1]:.3f}) Ø {h[2]:.3f} {h[3]}: not in the ODB++" for h in lost[:4]]
                  + ([f"{extra} holes in the ODB++ the drill files do not have"] if extra > 0 else [])), "equal")

    from shapely.geometry import Polygon

    from . import order_sheet
    edge = order_sheet.outline(g) if not gerber.missing(g, "outline") else None
    shape = max((Polygon(c) for c in job.profile if len(c) >= 3), key=lambda p: p.area, default=None)
    dist = edge.exterior.hausdorff_distance(shape.exterior) if edge is not None and shape is not None else None
    add("profile of the ODB++ = the Gerber outline", dist is not None and dist <= ODB_PROFILE_MM,
        "no profile in the ODB++" if shape is None else "no closed Gerber outline" if edge is None else
        f"{dist:.3f} mm apart at most", f"<= {ODB_PROFILE_MM} mm")

    check_odb_parts(cfg, board, design, d, job, m, add)
    check_odb_nets(design, board, job, add)


def mm_value(v):
    return float(str(v).lower().replace("mm", "").strip())


def check_odb_parts(cfg, board, design, d, job, m, add):
    """The components of the ODB++: every BOM part exactly once, at the place, rotation and side of the CPL, with the
    BOM's part number; the parts not to place (bom: false) as the maker's profile says (dnp)."""
    with open(d / f"cpl_{board.name}.csv", newline="", encoding="utf-8") as f:
        cpl = {r["Designator"]: r for r in csv.DictReader(f)}
    bom = {}
    with open(d / f"bom_{board.name}.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for ref in r["Designator"].split(","):
                bom[ref.strip()] = r
    comps = defaultdict(list)
    for c in job.components:
        comps[c.designator].append(c)
    bad = [f"{ref}: {len(comps[ref])}x in the ODB++" for ref in sorted(bom, key=natural_key) if len(comps[ref]) != 1]
    for ref in sorted(bom, key=natural_key):
        if len(comps[ref]) != 1 or ref not in cpl:
            continue
        c, row = comps[ref][0], cpl[ref]
        x, y = mm_value(row["Mid X"]), mm_value(row["Mid Y"])
        if abs(c.x - x) > ODB_POS_MM or abs(c.y - y) > ODB_POS_MM:
            bad.append(f"{ref}: at ({c.x:.3f}, {c.y:.3f}), the CPL ({x:.3f}, {y:.3f})")
        side = "top" if row["Layer"].lower().startswith("t") else "bottom"
        if c.side != side:
            bad.append(f"{ref}: on the {c.side} in the ODB++, the CPL {side}")
        rot = (360 - c.rot) % 360          # ODB++ turns clockwise, the CPL counter-clockwise (ordering step 0b)
        if abs((rot - float(row["Rotation"]) + 180) % 360 - 180) > 0.01:
            bad.append(f"{ref}: rotation {rot:g}° (ODB++ {c.rot:g}° clockwise), the CPL {float(row['Rotation']):g}°")
    numbered = [c for c in job.components if c.designator in bom]
    names = lambda c: {c.part, *c.props.values()}  # noqa: E731
    keys = lambda r: {r.get("LCSC Part #"), (design.parts.get(r.get("LCSC Part #")) or {}).get("mpn")} - {None, ""}  # noqa: E731
    if numbered and not any(names(c) & keys(bom[c.designator]) for c in numbered):
        bad.append("no part of the ODB++ carries its BOM's part number (LCSC or MPN) – the maker cannot match them")
    else:
        bad += [f"{c.designator}: part {c.part or '–'} – the BOM {', '.join(sorted(keys(bom[c.designator])))}"
                for c in numbered if not names(c) & keys(bom[c.designator])]
    placed = design.board_comps(board.name)
    hand = sorted((ref for ref in comps if ref in placed and placed[ref].get("bom") is False), key=natural_key)
    alien = sorted((ref for ref in comps if ref not in bom and ref not in hand), key=natural_key)
    bad += [f"{ref}: in the ODB++, neither in the BOM nor a part of the board not to place" for ref in alien]
    if hand and m.data.get("dnp") == "omit":
        bad += [f"{ref}: bom: false, but in the ODB++ – {m.name} would place it" for ref in hand]
    add("parts of the ODB++ = BOM and CPL (once each, place, rotation, side, part number)", not bad,
        "; ".join(bad[:6]) or f"{len(bom)} parts", "equal")
    if hand and m.data.get("dnp") != "omit":
        add("parts not to place, in the ODB++", True, f"{', '.join(hand)} (bom: false) – the job lists them, the skill "
            "cart marks them on the maker's page and ORDER.form checks the marks", "information", "info")


def check_odb_nets(design, board, job, add):
    """The nets of the ODB++ pins as the graph has them: the pins of one graph net on one ODB++ net, none other on it
    – compared as groups, not by name (a renamed net counts as long as it joins the same pins)."""
    pin_net = {p: name for name, pins in design.board_nets(board.name).items() for p in pins}
    odb_net = {f"{c.designator}.{pin}": net for c in job.components for pin, _, _, net in c.pins
               if net and not net.startswith("$NONE")}
    groups = defaultdict(set)
    for p, net in odb_net.items():
        if p in pin_net:
            groups[net].add(pin_net[p])
    bad = [f"ODB++ net {net} joins {', '.join(sorted(n))}" for net, n in groups.items() if len(n) > 1]
    by_graph = defaultdict(set)
    for p, net in odb_net.items():
        if p in pin_net:
            by_graph[pin_net[p]].add(net)
    bad += [f"{name}: on {len(nets)} ODB++ nets ({', '.join(sorted(nets))})" for name, nets in sorted(by_graph.items())
            if len(nets) > 1]
    lost = sorted((p for p in pin_net if p.split(".")[0] in {c.designator for c in job.components} and p not in odb_net),
                  key=natural_key)
    bad += [f"{p}: no net in the ODB++, the graph {pin_net[p]}" for p in lost[:4]]
    add("nets of the ODB++ pins = the graph", not bad, "; ".join(bad[:6]) or f"{len(odb_net)} pins on "
        f"{len(groups)} nets", "equal")


def check_outline(board, g, rows):
    outline = [board.eda_point(*p) for p in board.outline]
    holes = [(*board.eda_point(h["x"], h["y"]), h["d"]) for h in board.holes]
    found = sorted((gerber.bbox(lp) for lp in gerber.loops(g / gerber.FILES["outline"])),
                   key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]))
    if not found:
        rows.add("F", "FILES.set", board.name, "outline in the Gerber files", False, "none", "closed outline")
        return
    o, want = found[0], gerber.bbox(outline)
    rows.add("F", "FILES.set", board.name, "outline (Gerber) = plan", all(abs(a - b) <= 0.2 for a, b in zip(o, want)),
             f"{o[2] - o[0]:.2f} x {o[3] - o[1]:.2f} mm at ({o[0]:.2f}, {o[1]:.2f})",
             f"{want[2] - want[0]:.2f} x {want[3] - want[1]:.2f} mm at ({want[0]:.2f}, {want[1]:.2f}) ± 0.2")
    inner = found[1:]
    expect = [(x - dia / 2, y - dia / 2, x + dia / 2, y + dia / 2) for x, y, dia in holes]
    miss = [e for e in expect if not any(all(abs(a - b) <= 0.2 for a, b in zip(e, f)) for f in inner)]
    extra = [f for f in inner if not any(all(abs(a - b) <= 0.2 for a, b in zip(e, f)) for e in expect)]
    rows.add("F", "FILES.set", board.name, f"mounting holes (Gerber) = plan ({len(holes)} holes)", not miss and not extra,
             f"{len(inner)} inner outlines" + (f", missing {len(miss)}" if miss else "") + (f", extra {len(extra)}" if extra else ""),
             f"{len(expect)}, position ± 0.2 mm")


def check_tooling(board, g, rows):
    """Tooling holes of the Economic assembly as planned in the NPTH drill file, mask open by tooling_mask on both
    sides, no copper in the opening except the hole itself (JLCPCB: 1.152 mm, non-plated, mask + 0.148 mm)."""
    if not board.tooling:
        return
    from shapely.geometry import Point
    want = [board.eda_point(x, y) for x, y in board.tooling]
    holes = gerber.parse_holes(g / gerber.FILES["npth"])
    miss = [w for w in want if not any(math.dist(w, h[:2]) <= 0.05 and abs(h[2] - board.tooling_d) <= 0.01 for h in holes)]
    rows.add("F", "FILES.set", board.name, f"tooling holes in the NPTH drill file = plan ({len(want)} x Ø {board.tooling_d} mm)",
             not miss, f"{len(holes)} NPTH holes" + (f", missing {len(miss)}" if miss else ""), f"{len(want)}, ± 0.05 mm")
    r_open = board.tooling_d / 2 + board.tooling_mask
    bad = []
    for mask, cu in (("top_mask", "top"), ("bottom_mask", "bottom")):
        opening, copper = gerber.shape(gerber.parse_gerber(g / gerber.FILES[mask])), \
            gerber.shape(gerber.parse_gerber(g / gerber.FILES[cu]))
        for x, y in want:
            if not opening.buffer(0.01).contains(Point(x, y).buffer(r_open - 0.02)):
                bad.append(f"{mask}: opening at ({x:.1f}, {y:.1f}) smaller than Ø {2 * r_open:.3f} mm")
            ring = Point(x, y).buffer(r_open + 0.05).difference(Point(x, y).buffer(board.tooling_d / 2 + 0.01))
            if copper.intersects(ring):
                bad.append(f"{cu}: copper in the opening at ({x:.1f}, {y:.1f})")
    rows.add("F", "FILES.set", board.name, "tooling holes: mask open, no copper in the opening", not bad,
             "; ".join(bad) or "both sides clear", f"opening Ø {2 * r_open:.3f} mm, clear")


def run(cfg, board, out, offline=False, verbose=False):
    d = Path(out) / board.name
    d.mkdir(parents=True, exist_ok=True)
    design = Design.from_config(cfg)
    if not offline:
        if is_kicad(cfg):                 # the same files from the KiCad project and kicad-cli (handbook 16.6)
            from ..toolchain.kicad import fab as kicad_fab
            kicad_fab.collect(cfg, board, d, verbose)
        else:
            collect(cfg, board, d, verbose)
        (d / "jlc_parts.json").unlink(missing_ok=True)
    rows = Rows()
    check_pcb(cfg, board, design, d, rows)
    check_rows(board, design, rows)
    check_silk(cfg, board, design, d, rows)
    cu = check_copper(board, design, d, rows)
    check_apart(board, design, cu, rows)
    check_keepout(board, design, d, cu, rows)
    check_copper_sides(board, design, d, rows)
    check_drills(board, design, d, rows)
    check_rings(board, design, d, rows)
    check_loops(board, design, d, rows)
    check_pad_clearance(cfg, board, design, d, rows)
    check_paste_gap(cfg, board, design, d, rows)
    check_hand_joints(cfg, board, design, d, rows)
    check_looks(board, d, rows)
    check_visible_print(cfg, board, design, d, rows)
    check_fab(cfg, board, design, d, rows)
    check_odb(cfg, board, design, d, rows)           # SYNC.odb, only with a maker that takes ODB++
    from . import order_sheet
    order_sheet.check(cfg, board, design, d, rows, bom_rows(design, board))   # FILES.order, only with [order]
    if not gerber.missing(d / "gerber", "top", "bottom", "top_silk", "bottom_silk"):   # otherwise FILES.set names them
        from . import polarity
        img, n = polarity.sheet(cfg, board, design, d)
        rows.add("P", "FILES.sheet", board.name, "polarity sheet to compare with the datasheets and the JLCPCB preview", True,
                 f"{img.name}: {n} parts", "information", "info")
    return rows


# --- what the manufacturer builds from: fab_sha256 and `edakit fab diff` ----------------------------------------------

FAB_METHOD = f"raster {gerber.RES} mm v1"
NOT_BUILT = ("Gerber_DocumentLayer", "Gerber_DrillDrawingLayer")   # drawings for people; the factory builds nothing
FRAME_MM = 1.0           # the raster frame: the board outline and this much around it
SPOT_MM2 = 0.01          # changed spots below this area are only counted and summed
SHOW = 5                 # changed spots, drill hits and rows listed per file


def sha(data):
    return hashlib.sha256(data).hexdigest()


def built_files(g):
    """(Gerber layers, drill files) in a gerber folder that the manufacturer builds from – without the documentation
    and drill-drawing layers, the probe file and the order notes."""
    files = sorted(p for p in Path(g).iterdir() if p.is_file()) if Path(g).is_dir() else []
    return ([p for p in files if p.name.startswith("Gerber_") and not p.name.startswith(NOT_BUILT)],
            [p for p in files if p.name.startswith("Drill_")])


def outline_box(g, gerbers):
    """(x0, y0, x1, y1) in mm: the board outline – without one, every layer's extent – and FRAME_MM around it."""
    outline = Path(g) / gerber.FILES["outline"]
    pts = (gerber.points(gerber.parse_gerber(outline)) if outline.exists() else
           [p for f in gerbers for p in gerber.points(gerber.parse_gerber(f))]) or [(0.0, 0.0)]
    return (min(p[0] for p in pts) - FRAME_MM, min(p[1] for p in pts) - FRAME_MM,
            max(p[0] for p in pts) + FRAME_MM, max(p[1] for p in pts) + FRAME_MM)


def frame(g, gerbers):
    return gerber.Raster(*outline_box(g, gerbers))


def drill_rows(path):
    """Drill hits [x0, y0, x1, y1, diameter] rounded to 1 µm, sorted."""
    return sorted([round(v, 3) for v in hit] for hit in gerber.parse_drills(path))


def csv_rows(path):
    """Header, then the rows sorted."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.reader(f) if r]
    return rows[:1] + sorted(rows[1:])


def order_settings(path):
    """The order settings of a run (order_sheet.SETTINGS): {setting: value}."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def setting_rows(path):
    """The order settings as rows [setting, value as JSON], sorted – for `fab diff`."""
    return sorted([k, json.dumps(v, ensure_ascii=False)] for k, v in order_settings(path).items())


def fab_layers(d, board):
    """SHA-256 per file the manufacturer builds from, for one board folder <run>/fab/<board>: every Gerber layer
    rasterised in the outline's frame, the drill hits, the BOM and CPL rows – and with [order] the order settings that
    change the board as made (order.json: thickness, colours, finish, mark). A board without [order] has no such file:
    its hash is the files' alone, as before."""
    import numpy as np

    from .order_sheet import SETTINGS
    gerbers, drills = built_files(Path(d) / "gerber")
    out = {}
    if gerbers:
        r = frame(Path(d) / "gerber", gerbers)
        where = f"{r.x0:.3f} {r.y0:.3f} {r.w} {r.h} ".encode()
        for f in gerbers:
            out[f.name] = sha(where + np.packbits(r.render(gerber.parse_gerber(f))).tobytes())
    for f in drills:
        out[f.name] = sha(json.dumps(drill_rows(f)).encode())
    for name in (f"bom_{board}.csv", f"cpl_{board}.csv"):
        if (Path(d) / name).exists():
            out[name] = sha(json.dumps(csv_rows(Path(d) / name), ensure_ascii=False).encode())
    if (Path(d) / SETTINGS).exists():
        out[SETTINGS] = sha(json.dumps(order_settings(Path(d) / SETTINGS), sort_keys=True, ensure_ascii=False).encode())
    return out


def fab_hash(layers):
    """fab_sha256 over {board: fab_layers(…)} and the method."""
    return sha(json.dumps({"method": FAB_METHOD, "boards": layers}, sort_keys=True).encode())


def spots(xor, r):
    """Changed spots of a XOR image, largest first: [(area mm², (x0, x1, y0, y1) mm)]."""
    import numpy as np
    from scipy import ndimage
    lab, n = ndimage.label(xor, structure=np.ones((3, 3)))
    if not n:
        return []
    out = []
    for size, (rows, cols) in zip(ndimage.sum(xor, lab, range(1, n + 1)), ndimage.find_objects(lab)):
        x0, y0 = r.mm(cols.start, rows.stop)
        x1, y1 = r.mm(cols.stop, rows.start)
        out.append((float(size) * gerber.RES ** 2, (x0, x1, y0, y1)))
    return sorted(out, key=lambda s: -s[0])


def diff_layer(r, fa, fb):
    """Detail lines of one Gerber layer in two runs, or [] when the raster is the same."""
    a, b = r.render(gerber.parse_gerber(fa)), r.render(gerber.parse_gerber(fb))
    if (a == b).all():
        return []
    found = spots(a ^ b, r)
    big, small = [s for s in found if s[0] >= SPOT_MM2], [s for s in found if s[0] < SPOT_MM2]
    lines = [f"+{(b & ~a).sum() * gerber.RES ** 2:.3f} mm² / −{(a & ~b).sum() * gerber.RES ** 2:.3f} mm² in "
             f"{len(found)} spot(s)"]
    lines += [f"{area:.3f} mm² at x {x0:.2f}–{x1:.2f}, y {y0:.2f}–{y1:.2f} mm" for area, (x0, x1, y0, y1) in big[:SHOW]]
    if len(big) > SHOW:
        lines.append(f"{len(big) - SHOW} more spot(s), {sum(s[0] for s in big[SHOW:]):.3f} mm² together")
    if small:
        lines.append(f"{len(small)} spot(s) under {SPOT_MM2} mm², {sum(s[0] for s in small):.3f} mm² together")
    return lines


def diff_rows(a, b, show):
    """Detail lines of rows removed (−) and added (+) between two lists of rows."""
    ca, cb = Counter(map(tuple, a)), Counter(map(tuple, b))
    gone, new = sorted((ca - cb).elements()), sorted((cb - ca).elements())
    lines = [f"- {show(x)}" for x in gone[:SHOW]] + ([f"  … {len(gone) - SHOW} more removed"] if len(gone) > SHOW else [])
    lines += [f"+ {show(x)}" for x in new[:SHOW]] + ([f"  … {len(new) - SHOW} more added"] if len(new) > SHOW else [])
    return lines


def hole(h):
    x0, y0, x1, y1, d = h
    return f"Ø{d:.3f} at ({x0:.3f}, {y0:.3f})" + (f"–({x1:.3f}, {y1:.3f})" if (x0, y0) != (x1, y1) else "")


def diff_board(da, db, board):
    """[(file, changed, detail lines)] for one board folder in two runs: Gerber layers, drill hits, BOM and CPL, the
    order settings."""
    from .order_sheet import SETTINGS
    (ga, dra), (gb, drb) = built_files(da / "gerber"), built_files(db / "gerber")
    out = []
    boxes = [outline_box(d / "gerber", g) for d, g in ((da, ga), (db, gb)) if g]
    r = gerber.Raster(min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
                      max(b[3] for b in boxes)) if boxes else None
    pairs = [({f.name: f for f in xa}, {f.name: f for f in xb}) for xa, xb in ((ga, gb), (dra, drb))]
    csvs = [f"bom_{board}.csv", f"cpl_{board}.csv"]
    pairs.append(({n: da / n for n in csvs if (da / n).exists()}, {n: db / n for n in csvs if (db / n).exists()}))
    pairs.append(tuple({SETTINGS: d / SETTINGS} if (d / SETTINGS).exists() else {} for d in (da, db)))
    for kind, (fa, fb) in zip(("gerber", "drill", "csv", "order"), pairs):
        for name in sorted(set(fa) | set(fb), key=lambda n: (csvs.index(n) if n in csvs else 0, n)):
            if name not in fb or name not in fa:
                out.append((name, True, ["only in " + ("the first run" if name in fa else "the second run")]))
            elif kind == "gerber":
                lines = diff_layer(r, fa[name], fb[name])
                out.append((name, bool(lines), lines))
            elif kind == "drill":
                lines = diff_rows(drill_rows(fa[name]), drill_rows(fb[name]), hole)
                out.append((name, bool(lines), lines))
            elif kind == "order":
                lines = diff_rows(setting_rows(fa[name]), setting_rows(fb[name]), " = ".join)
                out.append((name, bool(lines), lines))
            else:
                lines = diff_rows(csv_rows(fa[name])[1:], csv_rows(fb[name])[1:], ",".join)
                out.append((name, bool(lines) or csv_rows(fa[name])[:1] != csv_rows(fb[name])[:1], lines))
    return out


def run_folder(cfg, run):
    p = Path(run)
    for d in (p, cfg.reports / run):
        if (d / "fab").is_dir():
            return d
    raise SystemExit(f"edakit fab diff: {run}: no gate run with manufacturing files (neither a folder nor in "
                     f"{cfg.reports})")


def main_diff(cfg, args):
    if len(args.runs) != 2:
        print("edakit fab diff RUN_A RUN_B: two gate runs", file=sys.stderr)
        return 1
    try:
        a, b = (run_folder(cfg, r) for r in args.runs)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1
    boards = [args.board] if args.board else sorted({d.name for run in (a, b) for d in (run / "fab").iterdir()
                                                     if d.is_dir()})
    changed = 0
    for board in boards:
        print(f"{board}: {a.name} → {b.name}")
        if not (a / "fab" / board).is_dir() or not (b / "fab" / board).is_dir():
            print(f"  {board}  only in {'the first run' if (a / 'fab' / board).is_dir() else 'the second run'}")
            changed += 1
            continue
        for name, diff, lines in diff_board(a / "fab" / board, b / "fab" / board, board):
            changed += diff
            print(f"  {name}  {'changed' if diff else 'equal'}")
            print("".join(f"      {ln}\n" for ln in lines), end="")
    print(f"{changed} file(s) changed" if changed else "the manufacturing files are equal")
    return 2 if changed else 0


def main(cfg, args):
    if args.action == "diff":
        return main_diff(cfg, args)
    if not args.out:
        print("edakit fab: --out is required (or: edakit fab diff RUN_A RUN_B)", file=sys.stderr)
        return 1
    board = cfg.board(args.board, made=True)
    rows = run(cfg, board, args.out, args.offline, args.verbose)
    for r in rows:
        print(f"  {r['result']:<4} {r['id']} {r['check']}: {r['actual']}", file=sys.stderr)
    print(json.dumps(rows, ensure_ascii=False))
    return 2 if any(r["result"] == "fail" for r in rows) else 0
