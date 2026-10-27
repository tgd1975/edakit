"""Placement rule: LEDs side by side have their anode towards the same side. The pour outline."""

import json
import math
import re
import tomllib
from types import SimpleNamespace

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from edakit import cli, config, pcb, route
from edakit.pcb import led_rows

PART = {"kind": "led", "pins": {"1": {"role": "anode"}, "2": {"role": "cathode"}}}
GEO = {"pads": {"1": {"x": -50, "y": 0}, "2": {"x": 50, "y": 0}}}


def run(project, rots, y=None):
    board = project.config().board()
    place = {f"D{i}": SimpleNamespace(x=10 * i, y=(y or [20] * len(rots))[i], rot=r, side="top")
             for i, r in enumerate(rots)}
    design = SimpleNamespace(comps=dict.fromkeys(place), part=lambda ref: PART)
    return led_rows(board, dict.fromkeys(place, GEO), place, design)


def test_row_with_same_polarity_passes(project):
    assert run(project, [0, 0, 0]) == []


def test_turned_led_in_a_row_is_found(project):
    found = run(project, [0, 180, 0])
    assert len(found) == 1 and "anode of D1 points the other way than D0" in found[0]


def test_leds_on_different_lines_are_not_a_row(project):
    assert run(project, [0, 180], y=[10, 30]) == []


# --- pour inset (#9): a 40 x 20 mm board, tracks 0.4 mm from the edge (edge_clearance_um), the pours on their own key

MIL = 1000 / 25.4


def inset_board(tmp_path, top=""):
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True, exist_ok=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text(
        top + '\n[outline]\nrect = [40, 20]\n[routing]\nedge_clearance_um = 400\n[[pours]]\nnet = "GND"\n'
        'pour_only = true\n')
    return config.load(tmp_path / "edakit.toml").board()


def insets(board):
    """(pours, tracks) in mm: how far the pour outline and the area the DSN's keep-out strips leave free lie inside
    the outline."""
    outer = Polygon(board.outline)
    pour = Polygon(pcb.pour_outline(board))
    assert outer.contains(pour)
    outer_mil = Polygon([(x * MIL, y * MIL) for x, y in board.outline])
    _, strips = route.outside_strips(route.Rules(board), outer_mil)
    free = outer_mil.difference(unary_union(strips))
    return round(outer.exterior.distance(pour.exterior), 3), round(outer_mil.exterior.distance(free.exterior) / MIL, 3)


def test_pour_inset_of_its_own(tmp_path):
    board = inset_board(tmp_path, "pour_inset_mm = 0.55")
    assert insets(board) == (0.55, 0.4)                                   # the tracks keep the edge clearance
    rules = route.Rules(board)
    assert rules.edge_um == 400                                           # and Freerouting gets it as before
    assert route._pour_area(rules).bounds[:2] == pytest.approx((0.55 * MIL, 0.55 * MIL))   # the computed pours too


def test_pour_inset_default_follows_the_edge_clearance(tmp_path):
    assert insets(inset_board(tmp_path)) == (0.5, 0.4)                    # no key: edge clearance + 0.1 mm, as before


# --- a module on pin headers (#14): U1 a module of 51 x 21 mm with two rows of 20 through-hole pins 17.78 mm apart
# (pins 1-20 below, 21-40 above), 0805 boxes 3.7 x 1.9 mm, D1 an SMA diode, J1 a through-hole connector

def footprint(w, h, pads, tht=False):
    """Geometry as `pcb dump` stores it – mil, relative to the origin at 0° on TOP – from a box and pads in mm."""
    return {"bbox": [-w / 2 * MIL, -h / 2 * MIL, w / 2 * MIL, h / 2 * MIL],
            "pads": {str(n): {"x": x * MIL, "y": y * MIL, "net": "", "tht": tht} for n, (x, y) in pads.items()}}


CHIP = {1: (-0.95, 0), 2: (0.95, 0)}
MODULE = {**{i + 1: (-24.13 + 2.54 * i, -8.89) for i in range(20)}, **{40 - i: (-24.13 + 2.54 * i, 8.89) for i in range(20)}}
HEADER_GEO = {"U1": footprint(51, 21, MODULE, tht=True), "C2": footprint(3.7, 1.9, CHIP),
              "R2": footprint(3.7, 1.9, CHIP), "D1": footprint(6.6, 3.0, {1: (-2.2, 0), 2: (2.2, 0)}),
              "J1": footprint(6, 6, {1: (-1, 0), 2: (1, 0)}, tht=True)}


def plan_check(project, parts, geo, **keys):
    """The plan check of a 90 x 40 mm board without holes: `parts` {ref: (x, y)} at 0°, on top unless a third value
    names the side."""
    rows = "\n".join(f'{r} = {{ x = {p[0]}, y = {p[1]}, rot = 0, side = "{p[2] if len(p) > 2 else "top"}" }}'
                      for r, p in parts.items())
    (project.root / "hardware" / "boards" / "main.toml").write_text(f"[outline]\nrect = [90, 40]\n\n[place]\n{rows}\n")
    cfg = project.config()
    board = cfg.board()
    for key, value in keys.items():          # the keys themselves: test_config.py
        setattr(board, key, value)
    geo = {r: geo[r] for r in board.place}
    place, boxes, tht, _, _ = pcb.build_plan(cfg, board, geo)
    return pcb.check_plan(cfg, board, geo, place, boxes, tht)


def under_module(project, parts, geo=HEADER_GEO, **keys):
    """U1 at (45, 20) mm, `parts` around it."""
    return plan_check(project, {"U1": (45, 20), **parts}, geo, **keys)


UNDER = {"C2": (45, 20),           # between the pin rows, 7.94 mm from the nearest pin
         "D1": (32.3, 11.21)}      # on the lower row: pins 5 and 6 lie 1.4 mm inside its box


def test_parts_under_a_module_overlap_without_on_headers(project):
    assert under_module(project, UNDER) == ["U1 / C2: overlap (top)", "U1 / D1: overlap (top)"]


def test_smd_parts_may_sit_under_a_module_on_headers_but_not_on_its_pins(project):
    assert under_module(project, UNDER, on_headers={"U1"}) == [
        "D1: on the pins of U1 (top) – 0.00 mm from pin 5 (header_keep_mm 1.27)"]


def test_through_hole_part_under_a_module_on_headers_stays_an_overlap(project):
    assert under_module(project, {"J1": (60, 20)}, on_headers={"U1"}) == ["U1 / J1: overlap (top)"]


def test_header_keep_mm(project):
    beside = {"R2": (40, 13.06)}   # its box 1.00 mm above pins 8 and 9
    assert under_module(project, beside, on_headers={"U1"}) == [
        "R2: on the pins of U1 (top) – 1.00 mm from pin 8 (header_keep_mm 1.27)"]
    assert under_module(project, beside, on_headers={"U1"}, header_keep_mm=0.87) == []


def test_module_on_headers_without_through_hole_pins(project):
    flat = {**HEADER_GEO, "U1": footprint(51, 21, MODULE)}
    assert under_module(project, {"C2": (45, 20)}, geo=flat, on_headers={"U1"}) == [
        "U1: in on_headers, but its footprint has no through-hole pins – its overlaps count as usual",
        "U1 / C2: overlap (top)"]


# --- silkscreen tolerance (#15): 0805 boxes 3.7 x 1.9 mm (silkscreen included), J1 a through-hole connector of
# 6 x 6 mm, U2 an SOIC box of 10 x 7.5 mm, C2 a 0201 box of 1.2 x 0.6 mm

SILK_GEO = {"R1": footprint(3.7, 1.9, CHIP), "R2": footprint(3.7, 1.9, CHIP), "C1": footprint(3.7, 1.9, CHIP),
            "J1": HEADER_GEO["J1"], "U2": footprint(10, 7.5, {1: (-2.7, -3.81), 16: (-2.7, 3.81)}),
            "C2": footprint(1.2, 0.6, {1: (-0.3, 0), 2: (0.3, 0)})}
SIDE_BY_SIDE = {"R1": (20, 20), "R2": (23.4, 20),     # boxes 0.3 mm into each other
                "J1": (60, 20), "C1": (64.55, 20)}    # C1's box 0.3 mm into the through-hole connector's


def test_touching_silkscreen_overlaps_without_the_key(project):
    assert plan_check(project, SIDE_BY_SIDE, SILK_GEO) == ["R1 / R2: overlap (top)", "J1 / C1: overlap (top)"]


def test_smd_boxes_may_overlap_by_the_silkscreen_tolerance(project):
    assert plan_check(project, SIDE_BY_SIDE, SILK_GEO, silk_overlap_mm=0.8) == [
        "J1 / C1: overlap (top) – 0.30 mm (J1 through-hole: silk_overlap_mm does not apply)"]


def test_silkscreen_tolerance_is_a_limit(project):
    deeper = {"R1": (20, 20), "R2": (22.7, 20)}             # 1.0 mm into each other
    assert plan_check(project, deeper, SILK_GEO, silk_overlap_mm=0.8) == [
        "R1 / R2: overlap (top) – 1.00 mm (silk_overlap_mm 0.8)"]
    corner = {"R1": (20, 20), "R2": (22.7, 21.6)}           # 1.0 mm in x, 0.3 mm in y: beyond the tolerance in x only
    assert plan_check(project, corner, SILK_GEO, silk_overlap_mm=0.8) == []


def test_small_part_inside_a_box_stays_an_overlap(project):
    # per axis, the distance one box has to move to clear the other: C2 is narrower than the tolerance, but it lies
    # 4.05 mm deep inside U2
    assert plan_check(project, {"U2": (20, 20), "C2": (20, 20)}, SILK_GEO, silk_overlap_mm=0.8) == [
        "U2 / C2: overlap (top) – 4.05 mm (silk_overlap_mm 0.8)"]


def test_silkscreen_tolerance_leaves_parts_under_a_module_on_headers_alone(project):
    assert under_module(project, UNDER, on_headers={"U1"}, silk_overlap_mm=0.8) == [
        "D1: on the pins of U1 (top) – 0.00 mm from pin 5 (header_keep_mm 1.27)"]


# --- the plan's other findings (#18): outline, mounting and tooling holes, through-hole pins of the other side

def test_plan_findings_at_the_outline_the_holes_and_the_other_side(project):
    geo = {**{r: footprint(3.7, 1.9, CHIP) for r in ("R1", "R2", "C1", "C2")}, "J1": HEADER_GEO["J1"]}
    parts = {"R1": (1.5, 20),              # its box reaches 0.35 mm over the left edge
             "R2": (12, 30),               # its box 0.15 mm from the centre of the hole (10, 30): in the keep-out
             "C1": (61, 37),               # over the tooling hole (60, 37)
             "J1": (60, 20), "C2": (60, 20, "bottom")}   # J1's two pins under C2 on the other side
    holes = [{"x": 10, "y": 30, "d": 3.2, "keep": 3.2}, {"x": 1.5, "y": 1.5, "d": 3.2, "keep": 3.2}]
    tooling = [(89.5, 5), (60, 37), (8, 32)]
    assert plan_check(project, parts, geo, holes=holes, tooling=tooling) == [
        "R1: reaches over the outline (keep 0.3 mm)",
        "R2: inside the keep-out of the hole (10, 30)",
        "C1: inside the keep-out of the tooling hole (60, 37)",
        "hole (1.5, 1.5): too close to the outline",
        "tooling hole (89.5, 5): too close to the outline",
        "tooling hole (8, 32): too close to a mounting hole",
        "C2 (bottom): 2 THT pins of the other side underneath"]


def test_one_tooling_hole_is_not_enough(project):
    assert plan_check(project, {"R1": (20, 20)}, {"R1": footprint(3.7, 1.9, CHIP)}, tooling=[(50, 20)]) == [
        "JLCPCB wants 2-3 tooling holes in opposite corners, not one"]


# --- pcb place (#57): the example with a footprint geometry of its own – boxes from the footprint names, pads as the
# packages have them –, C1 (100 nF, the decoupling of U2 on 3V3) and R1 (R-EXT, layout.near R1 -> U2) taken out of
# [place]. U2 is an SOIC-16 at (66, 17) turned by 90°: pins 1-8 along its lower edge, 16-9 along its upper edge.

SOIC16 = {**{i + 1: (-2.7, 4.445 - 1.27 * i) for i in range(8)}, **{16 - i: (2.7, 4.445 - 1.27 * i) for i in range(8)}}
BUTTON = {1: (-3.25, 1.85), 2: (3.25, 1.85), 3: (-3.25, -1.85), 4: (3.25, -1.85)}


def led_bar_geo():
    geo = {"U1": footprint(51, 21, {**MODULE, 41: (25, -2.54), 42: (25, 0), 43: (25, 2.54)}),
           "U2": footprint(6.0, 10.4, SOIC16), "J1": footprint(6.0, 4.5, {1: (-1, 0), 2: (1, 0)}, tht=True),
           "D1": footprint(6.6, 3.0, {1: (-2.2, 0), 2: (2.2, 0)}), "SW1": footprint(6.5, 5.1, BUTTON),
           **{r: footprint(3.7, 1.9, CHIP) for r in ("R1", "R2", "C1", "C2", *(f"D{i}" for i in range(2, 10)))}}
    geo["U1"]["bbox"] = [-21.5 * MIL, -10.5 * MIL, 25.5 * MIL, 10.5 * MIL]   # clear of the mounting hole (3.5, 3.5)
    geo["J1"]["bbox"] = [-3 * MIL, -5.5 * MIL, 3 * MIL, 2.25 * MIL]          # its body reaches the edge (layout.edge)
    return geo


def place_project(project, drop=("C1", "R1"), add="", geo=None):
    """The example with its geometry dumped, the rows of `drop` taken out of [place] and `add` appended to it."""
    f = project.root / "hardware" / "boards" / "main.toml"
    lines = [ln for ln in f.read_text().splitlines(keepends=True) if ln.split(" = ")[0] not in drop]
    text = "".join(lines)
    if add:
        text = text.replace('C2 = { x = 29, y = 28, rot = 0, side = "top" }\n',
                            f'C2 = {{ x = 29, y = 28, rot = 0, side = "top" }}\n{add}')
    f.write_text(text)
    out = project.root / "build" / "edakit" / "pcb_geometry_main.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(geo or led_bar_geo()))
    return f


def pad_at(board, geo, ref, p, num):
    q = geo[ref]["pads"][str(num)]
    return board.transform((q["x"], q["y"]), p.x, p.y, p.rot, p.side)


def nearest_pin(board, geo, ref, p, num, host, hp):
    at = pad_at(board, geo, ref, p, num)
    return min(geo[host]["pads"], key=lambda n: math.dist(at, pad_at(board, geo, host, hp, n)))


def test_example_plan_passes_with_the_test_geometry(project):
    place_project(project, drop=())
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == []


def test_place_puts_the_parts_next_to_their_host(project, capsys):
    place_project(project)
    cfg = project.config()
    board, geo = cfg.board(), led_bar_geo()
    assert pcb.plan(cfg, board) == [                                       # today: two positions to work out by hand
        "L-12 R1: not in hardware/boards/main.toml [place] – the circuit wants it next to U2",
        "L-12 U2: no capacitor of its own from 3V3 to GND within 6 mm – fix C1 next to it"]
    capsys.readouterr()
    assert cli.main(["pcb", "place", "--config", str(project.root / "edakit.toml")]) == 0
    out = capsys.readouterr().out
    rows = re.findall(r"^  (\w+) = (\{.*\})", out, re.M)
    assert [r for r, _ in rows] == ["R1", "C1"]                            # declared hosts first, then decoupling
    place = {r: config._placement(r, tomllib.loads(f"v = {t}")["v"]) for r, t in rows}
    assert all(p.auto and p.side == "top" and p.rot in (0, 90, 180, 270) for p in place.values())
    u2 = board.place["U2"]
    for ref, pad, pin in (("C1", 1, "16"), ("R1", 1, "15")):              # 3V3 to VDD, REXT to R-EXT
        p = place[ref]
        assert pcb.box_gap(pcb.part_box(board, geo[ref], p), pcb.part_box(board, geo["U2"], u2)) <= board.near_mm
        assert nearest_pin(board, geo, ref, p, pad, "U2", u2) == pin
        assert math.dist(pad_at(board, geo, ref, p, pad), pad_at(board, geo, "U2", u2, pin)) < 2.0
    assert "R2" not in out                                                 # the pull-up of LED_OE has no host


def test_place_write_adds_the_rows_and_the_plan_passes(project, capsys):
    f = place_project(project)
    before = f.read_text()
    toml = str(project.root / "edakit.toml")
    assert cli.main(["pcb", "place", "--write", "--config", toml]) == 0
    after = f.read_text()
    new = [ln for ln in after.splitlines() if ln not in before.splitlines()]
    assert [ln.split(" = ")[0] for ln in new] == ["R1", "C1"] and all(ln.endswith("auto = true }") for ln in new)
    assert [ln for ln in after.splitlines() if ln not in new] == before.splitlines()   # nothing else changed
    assert after.index("C2 = { x = 29") < after.index(new[0]) < after.index("[near]")  # at the end of [place]
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == []
    assert cli.main(["pcb", "place", "--write", "--config", toml]) == 0  # a second run changes nothing
    assert f.read_text() == after


def test_place_never_moves_a_hand_written_row(project, capsys):
    hand = 'R1 = { x = 59, y = 17, rot = 90, side = "top" }   # by hand\n'
    loose = 'R2 = { x = 40, y = 30, rot = 0, side = "top", auto = true }\n'   # an auto row whose part has no host
    f = place_project(project, add=hand + loose)
    assert cli.main(["pcb", "place", "--write", "--config", str(project.root / "edakit.toml")]) == 0
    text = f.read_text()
    assert hand in text and loose in text and text.count("auto = true") == 2 and "\nC1 = " in text


def test_place_moves_its_own_rows(project, capsys):
    f = place_project(project, add='C1 = { x = 20, y = 30, rot = 0, side = "top", auto = true }\n')
    assert cli.main(["pcb", "place", "--write", "--only", "C1", "--config", str(project.root / "edakit.toml")]) == 0
    cfg = project.config()
    board = cfg.board()
    assert set(board.place) - {"C1"} == set(project.config().board().place) - {"C1"} and "R1" not in board.place
    c1 = board.place["C1"]
    assert c1.auto and pcb.box_gap(pcb.part_box(board, led_bar_geo()["C1"], c1),
                                   pcb.part_box(board, led_bar_geo()["U2"], board.place["U2"])) <= board.near_mm
    assert f.read_text().count("C1 = ") == 1


def test_place_names_a_part_without_a_free_spot(project, capsys):
    # U2's box spans x 60.8-71.2, y 14-20; four walls 0.05 mm from it reach 6.05 mm out on every side
    walls = {"X1": (66, 23.05, 22.5, 6), "X2": (66, 10.95, 22.5, 6), "X3": (57.75, 17, 6, 6.1),
             "X4": (74.25, 17, 6, 6.1)}
    geo = {**led_bar_geo(), **{r: footprint(w, h, {}) for r, (_, _, w, h) in walls.items()}}
    add = "".join(f'{r} = {{ x = {x}, y = {y}, rot = 0, side = "top" }}\n' for r, (x, y, _, _) in walls.items())
    place_project(project, drop=("C1",), add=add, geo=geo)
    assert cli.main(["pcb", "place", "--config", str(project.root / "edakit.toml")]) == 2
    assert "C1: no free spot within near_mm 6 of U2 (pin 16, 3V3)" in capsys.readouterr().out
