"""Stages L and F end to end (#18): `fab.run(cfg, board, out, offline=True)` on an export written for the test –
every row passes – and one fault per check built into a copy of it: the check finds it and names the part, net or
file. Each test lists every row that fails or warns, so a check that fires as well shows up.

The export is the example's input stage: J1 (JST PH, through-hole), D1 (SS34 against reverse polarity) and C2 (22 µF)
with the nets VIN, +5V and GND, on a board of 30 x 20 mm with one M3 hole and two tooling holes, every track on TOP.
The whole example has never been routed or exported, so no real export of it exists. This one has the files that
`fab.collect` leaves, with the fields the checks read: pcb.json, drc.json, bom_easyeda.json, cpl_easyeda.xlsx,
jlc_parts.json (so F-2 stays offline), and the Gerber and drill files with FlyingProbeTesting.json. It also has the
footprint geometry of `edakit pcb dump` and the net currents of `edakit sim`: 0.5 A on all three nets, which puts
them in class POWER (0.6 mm), with an IPC-2221 width of 0.20 mm. J1 is through-hole and the example orders Economic
assembly (SMD only), so the cut-down graph leaves J1 out of the BOM, to be soldered by hand.

A new check of stage L or F gets its fault here: one more entry in FAULTS.
"""

import json
import math

import openpyxl
import pytest

from edakit import cli, gerber
from edakit.release import fab

MIL = 1000 / 25.4
INPUT = ("J1", "D1", "C2")
NET = {"J1.1": "VIN", "J1.2": "GND", "D1.1": "+5V", "D1.2": "VIN", "C2.1": "+5V", "C2.2": "GND"}
LCSC = {"J1": "C131337", "D1": "C8678", "C2": "C45783"}
FOOTPRINTS = {  # at 0° on TOP, mm: body (w, h), pads {number: (x, y)}, pad aperture, through-hole
    "CONN-TH_B2B-PH-K-S": ((6.0, 4.5), {"1": (-1.0, 0.0), "2": (1.0, 0.0)}, ("C", 1.4, 1.4), True),
    "SMA_L4.3-W2.6-LS5.2-RD": ((6.6, 3.0), {"1": (-2.2, 0.0), "2": (2.2, 0.0)}, ("R", 2.5, 1.7), False),
    "C0805": ((3.7, 1.9), {"1": (-0.95, 0.0), "2": (0.95, 0.0)}, ("R", 1.0, 1.3), False),
}
PLACE = {"J1": ("CONN-TH_B2B-PH-K-S", 3, 10, 90), "D1": ("SMA_L4.3-W2.6-LS5.2-RD", 13, 9, 180),
         "C2": ("C0805", 20, 9, 0)}
TRACKS = {"VIN": ["J1.1", "D1.2"], "+5V": ["D1.1", "C2.1"],
          "GND": ["J1.2", (3, 13.5), (22.5, 13.5), (22.5, 9), "C2.2"]}
WIDTH, DRILL = 0.6, 1.0            # tracks, J1's plated holes (mm)
HOLE = (26, 16, 3.2)               # M3, a circle on the outline layer
TOOLING = [(2.5, 17.5), (27.5, 2.5)]
TOOLING_D, TOOLING_OPEN = 1.152, 1.152 + 2 * 0.148
PLUS = (10.8, 10.9)                # "+" on the top silkscreen, next to D1's anode
BOARD = f"""# The input stage of the example on a board of its own (tests/test_fab_run.py)
view = "top"
edge_ok = ["J1"]

[outline]
rect = [30, 20]

[[holes]]
x = {HOLE[0]}
y = {HOLE[1]}
d = {HOLE[2]}
keep = 3.2

[tooling]
holes = {[list(t) for t in TOOLING]}

[place]
""" + "".join(f'{r} = {{ x = {x}, y = {y}, rot = {rot}, side = "top" }}\n' for r, (_, x, y, rot) in PLACE.items()) + """
[near]
C2 = "D1"

[[loops]]
a = "J1.1"
b = "D1.2"
max_mm = 10
what = "input"
"""


def turn(p, rot):
    a = math.radians(rot)
    c, s = round(math.cos(a)), round(math.sin(a))
    return p[0] * c - p[1] * s, p[0] * s + p[1] * c


def cut(project):
    """The example's graph cut down to its input stage, and the board file of that stage."""
    g = project.graph()
    gg = g["graph"]
    gg["components"] = [c for c in gg["components"] if c["designator"] in INPUT]
    project.comp(g, "J1")["bom"] = False
    gg["nets"] = [{**n, "pins": [p for p in n["pins"] if p.split(".")[0] in INPUT]} for n in gg["nets"]]
    gg["nets"] = [n for n in gg["nets"] if n["pins"]]
    gg["layout"] = {"edge": ["J1"]}
    project.save_graph(g)
    (project.root / "hardware" / "boards" / "main.toml").write_text(BOARD)


class Layer(list):
    """Gerber items in mm: ("flash", (kind, a, b), x, y) and ("draw", width, points, tag)."""

    def text(self):
        aps, body = {}, []
        um = lambda v: round(v * 1e6)  # noqa: E731

        def code(ap):
            return aps.setdefault(ap, 10 + len(aps))
        for item in self:
            if item[0] == "flash":
                body += [f"D{code(item[1])}*", f"X{um(item[2])}Y{um(item[3])}D03*"]
            else:
                _, w, pts, _ = item
                body += [f"D{code(('C', w, w))}*", f"X{um(pts[0][0])}Y{um(pts[0][1])}D02*"]
                body += [f"X{um(x)}Y{um(y)}D01*" for x, y in pts[1:]]
        head = ["%FSLAX46Y46*%", "%MOMM*%"] + [f"%ADD{c}{k},{a:.6f}" + ("" if k == "C" else f"X{b:.6f}") + "*%"
                                              for (k, a, b), c in aps.items()]
        return "\n".join(head + body + ["M02*"]) + "\n"

    def drop(self, tag):
        self[:] = [i for i in self if not (i[0] == "draw" and i[3] == tag)]


def drill(holes):
    """Excellon in mm: holes (x, y, d), slots (x0, y0, x1, y1, d)."""
    tools = {}
    for h in holes:
        tools.setdefault(h[-1], len(tools) + 1)
    out = ["M48", "METRIC"] + [f"T{t:02d}C{d:.3f}" for d, t in tools.items()] + ["%"]
    for d, t in tools.items():
        out.append(f"T{t:02d}")
        out += [f"X{h[0]:.3f}Y{h[1]:.3f}" + (f"G85X{h[2]:.3f}Y{h[3]:.3f}" if len(h) == 5 else "")
                for h in holes if h[-1] == d]
    return "\n".join(out + ["M30"]) + "\n"


class Export:
    """The files of one gate run, in memory: a fault changes them, write() puts them where fab.run reads them."""

    def __init__(self):
        self.at, comps, self.geo, probe = {}, [], {}, []
        cu = {k: Layer() for k in gerber.FILES if k not in ("pth", "vias", "npth", "probe")}
        self.pth, self.npth = [], [(x, y, TOOLING_D) for x, y in TOOLING]
        for ref, (fp, x, y, rot) in PLACE.items():
            (w, h), pads, (k, a, b), tht = FOOTPRINTS[fp]
            self.geo[ref] = {"footprint": fp, "bbox": [-w / 2 * MIL, -h / 2 * MIL, w / 2 * MIL, h / 2 * MIL],
                             "pads": {n: {"x": px * MIL, "y": py * MIL, "net": NET[f"{ref}.{n}"], "tht": tht}
                                      for n, (px, py) in pads.items()}}
            a, b = (b, a) if rot % 180 == 90 else (a, b)
            rows = []
            for n, p in pads.items():
                dx, dy = turn(p, rot)
                px, py = self.at[f"{ref}.{n}"] = (x + dx, y + dy)
                rows.append({"PadNumber": n, "X": px * MIL, "Y": py * MIL, "Net": NET[f"{ref}.{n}"],
                             "Layer": fab.MULTI if tht else 1, "tht": tht})
                for layer in ("top", "bottom") if tht else ("top",):
                    cu[layer].append(("flash", (k, a, b), px, py))
                    cu[f"{layer}_mask"].append(("flash", (k, a + 0.1, b + 0.1), px, py))
                if tht:
                    self.pth.append((px, py, DRILL))
                probe.append([f"{ref}_{n}", px * MIL, py * MIL, NET[f"{ref}.{n}"], "THT" if tht else "SMD", "T",
                              a * MIL, b * MIL])
            comps.append({"designator": ref, "footprintName": fp, "x": x * MIL, "y": y * MIL, "rotation": rot,
                          "layer": 1, "pads": rows})
        lines = []
        for net, path in TRACKS.items():
            pts = [self.at[p] if isinstance(p, str) else p for p in path]
            cu["top"].append(("draw", WIDTH, pts, net))
            lines += [{"Net": net, "Layer": 1, "LineWidth": WIDTH * MIL, "StartX": p[0] * MIL, "StartY": p[1] * MIL,
                       "EndX": q[0] * MIL, "EndY": q[1] * MIL} for p, q in zip(pts, pts[1:])]
        for x, y in TOOLING:
            for mask in ("top_mask", "bottom_mask"):
                cu[mask].append(("flash", ("C", TOOLING_OPEN, TOOLING_OPEN), x, y))
        cu["top_silk"] += [("draw", 0.15, [(PLUS[0] - 0.4, PLUS[1]), (PLUS[0] + 0.4, PLUS[1])], "+"),
                           ("draw", 0.15, [(PLUS[0], PLUS[1] - 0.4), (PLUS[0], PLUS[1] + 0.4)], "+")]
        cu["outline"].append(("draw", 0.1, [(0, 0), (30, 0), (30, 20), (0, 20), (0, 0)], "outline"))
        ring = [(HOLE[0] + HOLE[2] / 2 * math.cos(math.pi * k / 12), HOLE[1] + HOLE[2] / 2 * math.sin(math.pi * k / 12))
                for k in range(25)]
        cu["outline"].append(("draw", 0.1, ring, "hole"))
        self.gerber = cu
        self.pcb = {"components": comps, "lines": lines,
                    "strings": [{"Text": "+", "X": PLUS[0] * MIL, "Y": PLUS[1] * MIL, "Layer": 3}]}
        self.probe = {"pins": {"fields": ["PIN_NAME", "PIN_X", "PIN_Y", "NET_NAME", "PIN_TYPE", "LAYER", "PAD_SIZEX",
                                          "PAD_SIZEY"], "rows": probe}}
        self.drc = []
        self.bom = [{"reference": r, "lcsc": LCSC[r], "value": v, "quantity": 1}
                    for r, v in (("J1", ""), ("D1", "SS34"), ("C2", "22uF"))]
        self.jlc = {"C8678": {"componentModelEn": "SS34", "componentLibraryType": "base", "stockCount": 52000},
                    "C45783": {"componentModelEn": "CL21A226MAQNNNE", "componentLibraryType": "base",
                               "stockCount": 310000}}
        self.cpl = [{"Designator": r, "Footprint": fp, "Mid X": x, "Mid Y": y, "Layer": "T", "Rotation": rot,
                     "SMD": "No" if FOOTPRINTS[fp][3] else "Yes"} for r, (fp, x, y, rot) in PLACE.items()]
        self.currents = {"nets": {n: {"i_max_a": 0.5, "scenario": "written for the test"} for n in TRACKS}}

    def at_mil(self, ref):
        return tuple(v * MIL for v in self.at[ref])

    def comp(self, ref):
        return next(c for c in self.pcb["components"] if c["designator"] == ref)

    def pad(self, ref):
        des, _, num = ref.partition(".")
        return next(p for p in self.comp(des)["pads"] if p["PadNumber"] == num)

    def move(self, ref, dx):
        c = self.comp(ref)
        c["x"] += dx * MIL
        for p in c["pads"]:
            p["X"] += dx * MIL

    def turn(self, ref, rot):
        c = self.comp(ref)
        c["rotation"] = (c["rotation"] + rot) % 360
        for p in c["pads"]:
            dx, dy = turn((p["X"] - c["x"], p["Y"] - c["y"]), rot)
            p["X"], p["Y"] = c["x"] + dx, c["y"] + dy

    def width(self, net, mm):
        for ln in self.pcb["lines"]:
            if ln["Net"] == net:
                ln["LineWidth"] = mm * MIL

    def write(self, root):
        art = root / "build" / "edakit"
        (art / "sim").mkdir(parents=True, exist_ok=True)
        for f, data in (("pcb_geometry_main.json", self.geo), ("sim/net_currents.json", self.currents)):
            if data is not None:       # None: `pcb dump` or `edakit sim` never ran
                (art / f).write_text(json.dumps(data))
        d = root / "build" / "fab" / "main"
        (d / "gerber").mkdir(parents=True)
        for name, data in (("pcb", self.pcb), ("drc", self.drc), ("bom_easyeda", self.bom), ("jlc_parts", self.jlc)):
            (d / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False))
        wb = openpyxl.Workbook()
        ws = wb.active
        head = ["Designator", "Footprint", "Mid X", "Mid Y", "Layer", "Rotation", "SMD"]
        ws.append(head)
        for r in self.cpl:
            ws.append([r[k] for k in head])
        wb.save(d / "cpl_easyeda.xlsx")
        g = d / "gerber"
        for key, layer in self.gerber.items():
            (g / gerber.FILES[key]).write_text(layer.text())
        (g / gerber.FILES["pth"]).write_text(drill(self.pth))
        (g / gerber.FILES["npth"]).write_text(drill(self.npth))
        (g / gerber.FILES["probe"]).write_text(json.dumps(self.probe))
        return d.parent


def run(project, fault=None):
    cut(project)
    ex = Export()
    if fault:
        fault(ex, project)
    out = ex.write(project.root)
    cfg = project.config()
    return fab.run(cfg, cfg.board(), out, offline=True)


def findings(rows):
    return sorted((r["id"], r["result"]) for r in rows if r["result"] not in ("pass", "info"))


CHECKS = ["L-1", "L-2", "L-3", "L-4", "L-5", "L-7", "L-8", "L-9", "L-10", "L-11", "L-12", "F-1", "F-2", "F-3", "F-5"]


def test_the_clean_export_passes_every_check(project):
    rows = run(project)
    assert findings(rows) == []
    assert sorted({r["id"] for r in rows if r["stage"] in "LF"}, key=CHECKS.index) == CHECKS
    by = {(r["id"], r["check"]): r["actual"] for r in rows}
    assert by["L-11", "short current loops: path over tracks per pad pair within the limit"] == "J1.1-D1.2 7.8 mm"
    assert by["L-9", "hole takes the lead at nominal size (diagonal or edge, or manufacturer's value)"] == "2 holes"
    assert by["L-8", "silkscreen '+'/'−' = role of the nearest polarised pad"] == "1 signs correct"


def test_edakit_fab_offline_on_the_clean_export(project, monkeypatch, capsys):
    cut(project)
    out = Export().write(project.root)
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["fab", "--offline", "--out", str(out)]) == 0
    rows = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert findings(rows) == []


def board_file(project, old, new):
    f = project.root / "hardware" / "boards" / "main.toml"
    assert old in f.read_text()
    f.write_text(f.read_text().replace(old, new))


def graph(project, change):
    g = project.graph()
    change(g)
    project.save_graph(g)


def short(ex, project):
    ex.gerber["top"].append(("draw", 0.3, [ex.at["J1.1"], ex.at["J1.2"]], "short"))


def detour(ex, project):
    a, b = ex.at["J1.1"], ex.at["D1.2"]
    pts = [a, (a[0], 5), (b[0], 5), b]
    ex.pcb["lines"] = [ln for ln in ex.pcb["lines"] if ln["Net"] != "VIN"] + [
        {"Net": "VIN", "Layer": 1, "LineWidth": WIDTH * MIL, "StartX": p[0] * MIL, "StartY": p[1] * MIL,
         "EndX": q[0] * MIL, "EndY": q[1] * MIL} for p, q in zip(pts, pts[1:])]


def slot(ex, project):
    x, y, _ = ex.pth[0]
    ex.pth[0] = (x, y - 0.375, x, y + 0.375, 0.45)


def assembled_j1(ex, project):
    graph(project, lambda g: project.comp(g, "J1").pop("bom"))
    ex.jlc["C131337"] = {"componentModelEn": "B2B-PH-K-S(LF)(SN)", "componentLibraryType": "extend",
                         "stockCount": 41000}


FAULTS = [
    # L-1
    ("a pad on another net", lambda ex, p: ex.pad("D1.1").update(Net="VIN"),
     [("L-1", "fail", "D1.1: VIN instead of +5V")]),
    ("a part missing", lambda ex, p: ex.pcb["components"].remove(ex.comp("C2")),
     [("L-1", "fail", "missing ['C2']")]),
    ("a part too many", lambda ex, p: ex.pcb["components"].append({**ex.comp("C2"), "designator": "C9"}),
     [("L-1", "fail", "extra ['C9']")]),
    ("a graph pin without a pad", lambda ex, p: ex.comp("C2")["pads"].remove(ex.pad("C2.2")),
     [("L-1", "fail", "C2.2: pad missing in the footprint (GND)")]),
    # L-2
    ("a short across the connector", short, [("L-2", "fail", "GND + VIN (C2_2, D1_2, J1_1, J1_2)")]),
    ("an open net", lambda ex, p: ex.gerber["top"].drop("+5V"), [("L-2", "fail", "+5V: 2 groups")]),
    ("a connected pad missing from the files", lambda ex, p: ex.probe["pins"]["rows"].pop(4),
     [("L-2", "fail", "C2.1")]),
    # L-3
    ("a DRC finding", lambda ex, p: ex.drc.append({"errorType": "Clearance", "ruleName": "Safe Spacing"}),
     [("L-3", "fail", "Clearance (Safe Spacing): 1")]),
    # L-4
    ("another footprint", lambda ex, p: ex.comp("C2").update(footprintName="C0603"),
     [("L-4", "fail", "C2: C0603 instead of C0805")]),
    # L-5
    ("a power net at 3 mil", lambda ex, p: ex.width("VIN", 3 / MIL),
     [("L-5", "fail", "VIN: 0.08 < 0.20 mm"), ("L-5", "warn", "VIN: 0.08 < 0.60 mm")]),
    ("a power net below its class width", lambda ex, p: ex.width("VIN", 0.4),
     [("L-5", "warn", "VIN: 0.40 < 0.60 mm")]),
    ("no simulated currents", lambda ex, p: setattr(ex, "currents", None),
     [("L-5", "fail", "net_currents.json missing (edakit sim)")]),
    # L-7
    ("a fixed part moved by 1 mm", lambda ex, p: ex.move("C2", 1),
     [("L-7", "fail", "C2: (21.00, 9.00, 0°, top) instead of (20.00, 9.00, 0°, top)")]),
    ("a fixed part turned by 90 degrees", lambda ex, p: ex.turn("C2", 90),
     [("L-7", "fail", "C2: (20.00, 9.00, 90°, top) instead of (20.00, 9.00, 0°, top)"),
      ("F-3", "fail", "C2: rotation 0 differs from the PCB")]),
    ("a plan finding", lambda ex, p: board_file(p, 'C2 = "D1"', 'C2 = "J1"'),
     [("L-7", "fail", "C2: 12.9 mm from J1 (near_mm 6)")]),
    ("no footprint geometry", lambda ex, p: setattr(ex, "geo", None),
     [("L-7", "fail", "pcb_geometry_main.json missing (edakit pcb dump)")]),
    # L-8
    ("a minus sign at the anode", lambda ex, p: ex.pcb["strings"][0].update(Text="−"),
     [("L-8", "fail", "'−' at (10.8, 10.9) mm: nearest pad D1.2 is anode")]),
    ("a plus sign on a side without polarised pads",
     lambda ex, p: ex.pcb["strings"].append({**ex.pcb["strings"][0], "Layer": 4}),
     [("L-8", "fail", "'+' at (10.8, 10.9) mm: no polarised pad on this side")]),
    # L-9
    ("a through-hole part without lead data", lambda ex, p: p.save_part("C131337", {
        k: v for k, v in p.part("C131337").items() if k != "lead"}), [("L-9", "fail", "J1")]),
    ("holes too small for the lead", lambda ex, p: ex.pth.__setitem__(slice(None), [h[:2] + (0.5,) for h in ex.pth]),
     [("L-9", "fail", "J1.1: hole 0.50 mm for diagonal 0.71 mm")]),
    ("a plated slot narrower than 0.5 mm", slot,
     [("L-9", "fail", "J1.1: slot 0.45 x 1.20 mm"), ("L-9", "warn", "pad 1: 0.45 x 1.20 mm")]),
    ("a through-hole pad without its hole", lambda ex, p: ex.pth.pop(),     # the bottom pad of J1.2 loses GND too
     [("L-9", "fail", "J1.2: no hole"), ("L-2", "fail", "GND: 2 groups")]),
    # L-10
    ("a pad away from its library position", lambda ex, p: ex.pad("C2.1").update(X=ex.at_mil("C2.1")[0] + 0.2 * MIL),
     [("L-10", "fail", "C2.1: 0.20 mm away from its footprint position")]),
    # L-11
    ("a current loop over its limit", detour, [("L-11", "fail", "J1.1-D1.2 (input): 15.8 mm > 10.0 mm")]),
    # L-12
    ("the circuit's edge part not fixed", lambda ex, p: board_file(p, "J1 = { x = 3", "# J1 = { x = 3"),
     [("L-12", "fail", "J1: not in hardware/boards/main.toml [place] – the circuit wants it at the board edge")]),
    # F-1
    ("another LCSC number in EasyEDA's BOM", lambda ex, p: ex.bom[2].update(lcsc="C15850"),
     [("F-1", "fail", "C2: graph C45783, EasyEDA C15850")]),
    ("an LCSC number not in the parts database", lambda ex, p: (p.root / "hardware" / "parts" / "C45783.json").unlink(),
     [("F-1", "fail", "C45783")]),
    # F-2
    ("a part not in JLCPCB's catalogue", lambda ex, p: ex.jlc.pop("C8678"),
     [("F-2", "fail", "D1 C8678: not in the catalogue (pre-order only)")]),
    ("a part out of stock", lambda ex, p: ex.jlc["C45783"].update(stockCount=3),
     [("F-2", "fail", "C2 C45783: 3 in stock, 5 needed")]),
    ("the catalogue not reachable", lambda ex, p: ex.jlc.update(C8678={"error": "timed out"}),
     [("F-2", "fail", "D1 C8678: catalogue not reachable (timed out)")]),
    # F-3
    ("a part missing from the pick-and-place file", lambda ex, p: ex.cpl.pop(1), [("F-3", "fail", "D1: 0x")]),
    ("a part twice in the pick-and-place file", lambda ex, p: ex.cpl.append(dict(ex.cpl[2])),
     [("F-3", "fail", "C2: 2x")]),
    ("a part on the other side in the pick-and-place file", lambda ex, p: ex.cpl[2].update(Layer="B"),
     [("F-3", "fail", "C2: side B differs from the PCB"), ("F-3", "fail", "Bottom SMD 1")]),
    ("a through-hole part in the BOM of an SMD-only assembly", assembled_j1, [("F-3", "fail", "Top THT 1")]),
    # F-5
    ("a Gerber file missing", lambda ex, p: ex.gerber.pop("outline"),
     [("F-5", "fail", "Gerber_BoardOutlineLayer.GKO")]),
    ("no outline in the outline file", lambda ex, p: ex.gerber["outline"].clear(), [("F-5", "fail", "none")]),
    ("the outline off the plan", lambda ex, p: ex.gerber["outline"].__setitem__(0, (
        "draw", 0.1, [(0, 0), (31, 0), (31, 20), (0, 20), (0, 0)], "outline")),
     [("F-5", "fail", "31.00 x 20.00 mm at (0.00, 0.00)")]),
    ("a mounting hole missing", lambda ex, p: ex.gerber["outline"].drop("hole"), [("F-5", "fail", "missing 1")]),
    ("a tooling hole missing from the NPTH file", lambda ex, p: ex.npth.pop(),
     [("F-5", "fail", "1 NPTH holes, missing 1")]),
    ("the mask closed over a tooling hole", lambda ex, p: ex.gerber["top_mask"].pop(),
     [("F-5", "fail", "top_mask: opening at (27.5, 2.5) smaller than Ø 1.448 mm")]),
    ("copper in a tooling hole's opening",
     lambda ex, p: ex.gerber["top"].append(("flash", ("C", 0.3, 0.3), 3.15, 17.5)),
     [("F-5", "fail", "top: copper in the opening at (2.5, 17.5)")]),
]


@pytest.mark.parametrize("fault, expected", [pytest.param(f, e, id=name) for name, f, e in FAULTS])
def test_each_fault_is_found_by_its_check(project, fault, expected):
    rows = run(project, fault)
    assert findings(rows) == sorted((i, r) for i, r, _ in expected)
    for cid, result, text in expected:
        assert any(r["id"] == cid and r["result"] == result and text in r["actual"] for r in rows), \
            [(r["result"], r["actual"]) for r in rows if r["id"] == cid]


def test_every_check_has_a_fault():
    assert {cid for _, _, e in FAULTS for cid, _, _ in e} == set(CHECKS)
