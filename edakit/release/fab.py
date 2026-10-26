"""Stages L (board) and F (manufacturing files) of the release gate for one board.

    edakit fab --board main --out DIR            read the PCB, save + reload, DRC, export Gerber/CPL, BOM from the graph
    edakit fab --board main --out DIR --offline  only check what is already in DIR/<board>/

Result in DIR/<board>/:
    gerber/ and gerber_<board>.zip   Gerber and drill files as EasyEDA exports them (upload the ZIP)
    bom_<board>.csv                  BOM in JLCPCB format, generated from the graph
    cpl_<board>.csv                  pick-and-place file in JLCPCB format (BOM parts only)
    jlc_parts.json                   JLCPCB assembly catalogue entry per LCSC number of the BOM (F-2)
    pcb.json, drc.json, bom_easyeda.json, cpl_easyeda.xlsx   raw data from EasyEDA (for --offline)
and DIR/polarity_<board>.png: every polarised part with pad, role and net, to compare with datasheets and with the
assembly preview at JLCPCB.

  L-1  parts in the PCB = graph; every pad carries the graph's net; every graph pin has a pad
  L-2  copper from the Gerber files: every net connected, no short, every connected pad present
  L-3  EasyEDA DRC without findings (after save and reload)
  L-4  footprint per part = parts database
  L-5  track width per net >= IPC-2221 for 1.5 x the simulated current (fail); below the practical class width (warn);
       voltage drop as an upper bound (info)
  L-7  fixed parts in the PCB = plan (± 0.02 mm, rotation, side); the plan itself without findings
  L-8  silkscreen "+"/"−" next to a pad with that polarity role
  L-9  every through hole takes its lead at nominal size (lead data in the parts database); tight in the worst case
       or plated slots narrower than JLCPCB's minimum: warn
  L-10 every pad sits where the library footprint has the pad with that number (pad_map in the parts DB for
       intended swaps)
  L-11 short current loops ([[loops]] of the board file and layout.loops of the graph): shortest path over tracks of the
       same net per pad pair
  L-12 the plan keeps the layout requirements of the circuit: layout.fixed, .edge, .near of the graph and a
       decoupling capacitor next to every IC (handover.py)
  L-13 pads of different parts on different nets at least the routing clearance apart, on the pad shapes of
       `edakit route read` while they are the PCB's (route.pad_gaps, as `route check` measures)
  F-1  BOM from the graph = BOM of EasyEDA; every LCSC number in the parts database
  F-2  every BOM part listed in JLCPCB's assembly catalogue with stock for `quantity` boards
  F-3  pick and place: every BOM part exactly once, side and rotation = PCB; sides/SMD as [release] assembly says
  F-5  Gerber set complete; outline and holes = plan (± 0.2 mm); tooling holes in the NPTH file, mask open, no copper
Last stdout line: JSON list of rows {stage, id, item, check, actual, expected, result}. Exit 0 / 2 / 1.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import math
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from .. import gerber, handover
from ..config import BOTTOM, MIL_PER_MM, TOP
from ..design import Design, natural_key

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
    from .. import eda
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
        (d / "pcb.json").write_text(json.dumps({"components": comps, "lines": lines, "strings": strings}, indent=1))
        eda.reload_pcb(mcp)  # the DRC is reliable only on the saved, reloaded state
        found = eda.drc(mcp)
        (d / "drc.json").write_text(json.dumps(found, indent=1, ensure_ascii=False))
        res = mcp.call("easyeda_export_gerbers", projectId="current", drillFormat="millimeter",
                       productionReview={"mode": "off"}, timeout=300)
        if not res.get("exported"):
            raise SystemExit(f"Gerber export failed: {res}")
        shutil.copy(res["artifact_path"], d / f"gerber_{board.name}.zip")
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
    finally:
        mcp.close()
    shutil.rmtree(d / "gerber", ignore_errors=True)
    with zipfile.ZipFile(d / f"gerber_{board.name}.zip") as z:
        z.extractall(d / "gerber")


def fetch_jlc(bom, d):
    """F-2: JLCPCB's public assembly catalogue (no login; only part numbers leave the machine). A number missing there
    can only be pre-ordered."""
    import urllib.request
    out = {}
    for lcsc in sorted({r["LCSC Part #"] for r in bom}):
        req = urllib.request.Request(JLC_SEARCH, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                                     data=json.dumps({"keyword": lcsc, "currentPage": 1, "pageSize": 10}).encode())
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                found = json.load(resp)["data"]["componentPageInfo"]["list"] or []
        except Exception as e:  # network, changed API
            out[lcsc] = {"error": str(e)[:200]}
            continue
        hit = next((c for c in found if c.get("componentCode") == lcsc), None)  # full-text search: exact number only
        out[lcsc] = hit and {k: hit.get(k) for k in ("componentModelEn", "componentLibraryType", "stockCount")}
    (d / "jlc_parts.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))


# --- helpers ------------------------------------------------------------------------------------------------------

def to_plan(board, c):
    return board.from_eda(c["x"] * MM, c["y"] * MM, c["rotation"], c["layer"])


def pin_role(design, comp, num):
    return (design.parts.get(comp.get("lcsc") or "", {}).get("pins") or {}).get(num, {}).get("role")


def role_sign(role):
    if not role:
        return None
    if role.startswith("plus") or role in ("vbus", "anode"):
        return "+"
    if role.startswith("minus"):
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
    rows.add("L", "L-1", board.name, "parts in the PCB = graph", not missing and not extra,
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
    rows.add("L", "L-1", board.name, "pad nets in the PCB = graph, every graph pin has a pad", not bad,
             f"{total} pads" + (f", {len(bad)} differences: {'; '.join(bad[:12])}" if bad else ""), "no difference")
    wrong = []
    for ref, c in sorted(on_pcb.items()):
        part = design.part(ref) if ref in want else None
        if part and part.get("footprint") and c["footprintName"] != part["footprint"]:
            wrong.append(f"{ref}: {c['footprintName']} instead of {part['footprint']}")
    rows.add("L", "L-4", board.name, "footprint per part = parts database", not wrong, "; ".join(wrong) or "all equal", "equal")
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
        rows.add("L", "L-7", board.name, "fixed parts in the PCB = plan (position, rotation, side)", not off,
                 f"{len(place)} parts" + (f", {len(off)} off: {'; '.join(off[:8])}" if off else ""), "± 0.02 mm")
        rows.add("L", "L-7", board.name, "plan without findings (outline, overlaps, holes, THT pins, near)", not problems,
                 "; ".join(problems[:10]) or "none", "none")
        kept = pcbmod.check_handover(board, design, place, boxes)
        rows.add("L", "L-12", board.name, "plan keeps the layout requirements of the circuit (fixed, edge, near, "
                 "decoupling)", not kept, "; ".join(kept[:10]) or "all kept", "all kept")
    else:
        rows.add("L", "L-7", board.name, "footprint geometry for the plan checks", False, f"{geo_file.name} missing "
                 "(edakit pcb dump)", "present")
    widths, length = defaultdict(lambda: 1e9), defaultdict(float)
    for ln in data["lines"]:
        if ln["Net"]:
            widths[ln["Net"]] = min(widths[ln["Net"]], ln["LineWidth"] * MM)
            length[ln["Net"]] += math.hypot(ln["EndX"] - ln["StartX"], ln["EndY"] - ln["StartY"]) * MM
    need = required_widths(cfg, design, board)
    if need is None:
        rows.add("L", "L-5", board.name, "simulated net currents for the track widths", False,
                 "net_currents.json missing (edakit sim)", "present")
    else:
        ipc = [f"{n}: {w:.2f} < {need[n][0]:.2f} mm" for n, w in sorted(widths.items()) if n in need and w < need[n][0] - 0.005]
        rows.add("L", "L-5", board.name, "track width per net >= IPC-2221 for 1.5 x the simulated current (1 oz, 10 K)",
                 not ipc, "; ".join(ipc) or f"{len(widths)} nets with tracks", ">= IPC width")
        thin = [f"{n}: {w:.2f} < {need[n][1]:.2f} mm" for n, w in sorted(widths.items()) if n in need and w < need[n][1] - 0.005]
        if thin:
            rows.add("L", "L-5", board.name, "track width >= practical width of the net class", False, "; ".join(thin),
                     ">= class width", "warn")
        # upper bound: all pieces of the net in series, narrowest width, 35 µm copper (0.0172 Ohm mm²/m), no pours
        drop = {n: length[n] / 1000 * 0.0172 / (widths[n] * 0.035) * need[n][2] for n in length
                if n in need and need[n][2] > 0.05}
        if drop:
            rows.add("L", "L-5", board.name, "voltage drop on tracks, upper bound (all pieces in series x largest current)",
                     True, ", ".join(f"{n} {v * 1e3:.0f} mV" for n, v in sorted(drop.items(), key=lambda kv: -kv[1])),
                     "information", "info")
    drc = json.loads((d / "drc.json").read_text())
    kinds = Counter(f"{f.get('errorType')} ({f.get('ruleName')})" for f in drc)
    rows.add("L", "L-3", board.name, "EasyEDA DRC without findings", not drc,
             ", ".join(f"{k}: {n}" for k, n in kinds.items()) or "0", "0")
    labels = [s for s in data["strings"] if s["Layer"] in SILK and s["Text"] in ("+", "−", "-")]
    polar = {r for r in want if r in on_pcb and any(role_sign(p.get("role")) for p in
                                                   (design.parts.get(want[r].get("lcsc") or "", {}).get("pins") or {}).values())}
    if labels and polar:
        wrong = []
        for s in labels:
            pads = [(ref, p) for ref in polar for p in on_pcb[ref]["pads"]
                    if p["Layer"] in (SILK[s["Layer"]], MULTI) and role_sign(pin_role(design, want[ref], p["PadNumber"]))]
            if not pads:
                wrong.append(f"'{s['Text']}' at ({s['X'] * MM:.1f}, {s['Y'] * MM:.1f}) mm: no polarised pad on this side")
                continue
            ref, p = min(pads, key=lambda rp: math.hypot(rp[1]["X"] - s["X"], rp[1]["Y"] - s["Y"]))
            role = pin_role(design, want[ref], p["PadNumber"])
            if role_sign(role) != ("+" if s["Text"] == "+" else "−"):
                wrong.append(f"'{s['Text']}' at ({s['X'] * MM:.1f}, {s['Y'] * MM:.1f}) mm: nearest pad {ref}.{p['PadNumber']} "
                             f"is {role}")
        rows.add("L", "L-8", board.name, "silkscreen '+'/'−' = role of the nearest polarised pad", not wrong,
                 "; ".join(wrong) or f"{len(labels)} signs correct", "every sign at the right pole")


def check_pad_layout(board, design, on_pcb, want, geo, rows):
    """L-10: every pad sits where the library footprint has the pad with this number. Intended swaps are listed as
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
    rows.add("L", "L-10", board.name, "pad numbers sit as in the library footprint (exceptions: pad_map)", not bad,
             "; ".join(bad[:10]) or f"{n} pads", "± 0.05 mm")


def check_pad_clearance(cfg, board, design, d, rows):
    """L-13: pads of different parts on different nets keep the routing clearance on every copper layer – measured as
    `edakit route check` does, on the pad shapes of `route read` (pcb.json has none), when they still are the PCB's.
    A pair waived in the graph (waive L-13 on one of its parts or nets) is listed with its reason."""
    from .. import route
    clear = route.Rules(board).clear
    want = f">= {clear * MM:.3f} mm (clearance_mil {clear:g})"
    data, why = route.board_as_read(cfg, board, json.loads((d / "pcb.json").read_text())["components"])
    if data is None:
        rows.add("L", "L-13", board.name, "pad shapes for the pad clearance", False, why, "the PCB as read")
        return
    gaps = route.pad_gaps(data, clear, route.pad_waivers(design.graph))
    bad = [route.gap_text(g, clear) for g in gaps if not g["waived"]]
    rows.add("L", "L-13", board.name, "pads of different parts on different nets at least the routing clearance apart",
             not bad, "; ".join(bad[:10]) + (f" … ({len(bad)} pairs)" if len(bad) > 10 else "")
             or f"{sum(1 for p in data['pads'] if p['ref'])} pads", want)
    for g in gaps:
        if g["waived"]:
            rows.add("L", "L-13", board.name, f"pad clearance: {route.gap_text(g, clear)}", True,
                     f"{g['mil'] * MM:.3f} mm", want, "waived")
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
    rows.add("L", "L-9", board.name, "lead size of every through-hole part in the parts database (field lead)",
             not nodata, ", ".join(nodata) or "all", "all")
    rows.add("L", "L-9", board.name, "hole takes the lead at nominal size (diagonal or edge, or manufacturer's value)",
             not bad, "; ".join(bad[:10]) or f"{n} holes", "play >= 0")
    for ref, by_text in tight.items():  # one warning per part, so an accepted warning covers only that part
        rows.add("L", "L-9", board.name, f"{ref}: tight hole – worst case below {HOLE_PLAY_MM} mm play (hole -{HOLE_TOL_MM} "
                 "mm, lead + tolerance): lead only with force, or the part sits higher", False,
                 "; ".join(f"pad {', '.join(sorted(p, key=natural_key))}: {t}" for t, p in by_text.items()),
                 f">= {HOLE_PLAY_MM} mm", "warn")
    for ref, slots in narrow.items():
        rows.add("L", "L-9", board.name, f"{ref}: slot narrower than {JLC_SLOT_MM} mm (JLCPCB minimum, plated, 2 layers) – "
                 "JLCPCB widens it or asks", False, "; ".join(slots), f">= {JLC_SLOT_MM} mm", "warn")


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
    """L-11 over the loops of the plan and those the circuit hands over (layout.loops of the graph)."""
    loops = board.loops + handover.loops(design, board.name)
    if not loops:
        return
    data = json.loads((d / "pcb.json").read_text())
    found = [(a, b, limit, what, loop_length_mm(data, a, b)) for a, b, limit, what in loops]
    bad = [f"{a}-{b} ({what}): " + ("no track" if mm is None else f"{mm} mm") + f" > {limit} mm"
           for a, b, limit, what, mm in found if mm is None or mm > limit]
    rows.add("L", "L-11", board.name, "short current loops: path over tracks per pad pair within the limit", not bad,
             "; ".join(bad) or "; ".join(f"{a}-{b} {mm} mm" for a, b, _, _, mm in found),
             ", ".join(f"{a}-{b} <= {limit} mm" for a, b, limit, _ in loops))


def check_copper(board, design, d, rows):
    with contextlib.redirect_stdout(io.StringIO()):
        cu = gerber.Copper(d / "gerber", design.pin_net)
    want = design.board_comps(board.name)
    nets = defaultdict(list)
    for p, n in design.pin_net.items():
        if p.split(".")[0] in want:
            nets[n].append(p)
    have = {name.replace("_", ".", 1) for name in cu.pins}
    lost = sorted((p for ps in nets.values() if len(ps) > 1 for p in ps if p not in have), key=natural_key)
    rows.add("L", "L-2", board.name, "every connected pad is in the manufacturing files", not lost,
             ", ".join(lost[:15]) or f"{len(have)} pads", "all")
    broken = []
    for net, ps in sorted(nets.items()):
        if len(ps) > 1 and len(groups := cu.net_groups(net)) > 1:
            broken.append(f"{net}: {len(groups)} groups ({' | '.join(', '.join(g[:4]) for g in groups[:3])})")
    rows.add("L", "L-2", board.name, "copper from the Gerber files: every net connected", not broken,
             "; ".join(broken[:8]) or f"{sum(len(p) > 1 for p in nets.values())} nets complete", "1 group per net")
    shorts = [f"{' + '.join(n)} ({', '.join(p[:4])})" for n, p in cu.shorts]
    rows.add("L", "L-2", board.name, "copper from the Gerber files: no short between nets", not shorts,
             "; ".join(shorts[:8]) or "none", "none")


# --- F checks -----------------------------------------------------------------------------------------------------

def check_fab(cfg, board, design, d, rows):
    want = design.board_comps(board.name)
    bom = bom_rows(design, board)
    with open(d / f"bom_{board.name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Comment", "Designator", "Footprint", "LCSC Part #"])
        w.writeheader()
        w.writerows(bom)
    ours = {ref: r["LCSC Part #"] for r in bom for ref in r["Designator"].split(",")}
    eda_bom = {ref.strip(): e["lcsc"] for e in json.loads((d / "bom_easyeda.json").read_text())
               for ref in e["reference"].split(",") if ref.strip() in want}
    diff = [f"{r}: graph {ours.get(r, '–')}, EasyEDA {eda_bom.get(r, '–')}" for r in sorted(set(ours) | set(eda_bom), key=natural_key)
            if ours.get(r) != eda_bom.get(r) and not (r not in ours and want[r].get("bom") is False)]
    rows.add("F", "F-1", board.name, "BOM (from the graph) = BOM of EasyEDA, LCSC per designator", not diff,
             "; ".join(diff[:10]) or f"{len(ours)} parts in {len(bom)} lines", "equal")
    unknown = sorted({lc for lc in ours.values() if lc not in design.parts})
    rows.add("F", "F-1", board.name, "every LCSC number of the BOM is in the parts database", not unknown,
             ", ".join(unknown) or "all", "all")
    jlc_file = d / "jlc_parts.json"
    if not jlc_file.exists():
        fetch_jlc(bom, d)
    jlc, bad = json.loads(jlc_file.read_text()), []
    for r in bom:
        n, hit = len(r["Designator"].split(",")) * cfg.quantity, jlc.get(r["LCSC Part #"])
        if not hit:
            bad.append(f"{r['Designator']} {r['LCSC Part #']}: not in the catalogue (pre-order only)")
        elif hit.get("error"):
            bad.append(f"{r['Designator']} {r['LCSC Part #']}: catalogue not reachable ({hit['error'][:60]})")
        elif (hit.get("stockCount") or 0) < n:
            bad.append(f"{r['Designator']} {r['LCSC Part #']}: {hit.get('stockCount')} in stock, {n} needed")
    rows.add("F", "F-2", board.name, f"every BOM part in JLCPCB's assembly catalogue, stock for {cfg.quantity} boards",
             not bad, "; ".join(bad) or f"{len(bom)} lines listed and in stock", "all")
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
    rows.add("F", "F-3", board.name, "pick and place: every BOM part exactly once, side and rotation = PCB", not probs,
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
    rows.add("F", "F-3", board.name, f"assembly only on {', '.join(assembly.get('sides', ['top', 'bottom']))}"
             + (", SMD only" if assembly.get("smd_only") else "") + " ([release] assembly)", set(mix) <= allowed,
             ", ".join(f"{'Top' if s == 'T' else 'Bottom'} {k} {n}" for (s, k), n in sorted(mix.items())), str(sorted(allowed)))
    g = d / "gerber"
    lost = [gerber.FILES[k] for k in gerber.REQUIRED if not (g / gerber.FILES[k]).exists()]
    rows.add("F", "F-5", board.name, "Gerber set complete (copper, silk, mask, outline, drills)", not lost,
             ", ".join(lost) or f"{len(gerber.REQUIRED)} files", "all")
    if not lost:
        check_outline(board, g, rows)
        check_tooling(board, g, rows)


def check_outline(board, g, rows):
    outline = [board.eda_point(*p) for p in board.outline]
    holes = [(*board.eda_point(h["x"], h["y"]), h["d"]) for h in board.holes]
    found = sorted((gerber.bbox(lp) for lp in gerber.loops(g / gerber.FILES["outline"])),
                   key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]))
    if not found:
        rows.add("F", "F-5", board.name, "outline in the Gerber files", False, "none", "closed outline")
        return
    o, want = found[0], gerber.bbox(outline)
    rows.add("F", "F-5", board.name, "outline (Gerber) = plan", all(abs(a - b) <= 0.2 for a, b in zip(o, want)),
             f"{o[2] - o[0]:.2f} x {o[3] - o[1]:.2f} mm at ({o[0]:.2f}, {o[1]:.2f})",
             f"{want[2] - want[0]:.2f} x {want[3] - want[1]:.2f} mm at ({want[0]:.2f}, {want[1]:.2f}) ± 0.2")
    inner = found[1:]
    expect = [(x - dia / 2, y - dia / 2, x + dia / 2, y + dia / 2) for x, y, dia in holes]
    miss = [e for e in expect if not any(all(abs(a - b) <= 0.2 for a, b in zip(e, f)) for f in inner)]
    extra = [f for f in inner if not any(all(abs(a - b) <= 0.2 for a, b in zip(e, f)) for e in expect)]
    rows.add("F", "F-5", board.name, f"mounting holes (Gerber) = plan ({len(holes)} holes)", not miss and not extra,
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
    rows.add("F", "F-5", board.name, f"tooling holes in the NPTH drill file = plan ({len(want)} x Ø {board.tooling_d} mm)",
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
    rows.add("F", "F-5", board.name, "tooling holes: mask open, no copper in the opening", not bad,
             "; ".join(bad) or "both sides clear", f"opening Ø {2 * r_open:.3f} mm, clear")


def run(cfg, board, out, offline=False, verbose=False):
    d = Path(out) / board.name
    d.mkdir(parents=True, exist_ok=True)
    design = Design.from_config(cfg)
    if not offline:
        collect(cfg, board, d, verbose)
        (d / "jlc_parts.json").unlink(missing_ok=True)
    rows = Rows()
    check_pcb(cfg, board, design, d, rows)
    check_copper(board, design, d, rows)
    check_drills(board, design, d, rows)
    check_loops(board, design, d, rows)
    check_pad_clearance(cfg, board, design, d, rows)
    check_fab(cfg, board, design, d, rows)
    if (d / "gerber").exists():
        from . import polarity
        img, n = polarity.sheet(cfg, board, design, d)
        rows.add("P", "P-2", board.name, "polarity sheet to compare with the datasheets and the JLCPCB preview", True,
                 f"{img.name}: {n} parts", "information", "info")
    return rows


def main(cfg, args):
    board = cfg.board(args.board)
    rows = run(cfg, board, args.out, args.offline, args.verbose)
    for r in rows:
        print(f"  {r['result']:<4} {r['id']} {r['check']}: {r['actual']}", file=sys.stderr)
    print(json.dumps(rows, ensure_ascii=False))
    return 2 if any(r["result"] == "fail" for r in rows) else 0
