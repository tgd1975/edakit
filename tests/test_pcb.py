"""Placement rule: LEDs side by side have their anode towards the same side, other polarised kinds as the board says. The
pour outline."""

import itertools
import json
import math
import re
import tomllib
from types import SimpleNamespace

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from edakit import cli, config, part, pcb, route
from edakit.design import Design
from edakit.pcb import polarity_findings

PART = {"kind": "led", "pins": {"1": {"role": "anode"}, "2": {"role": "cathode"}}}
GEO = {"pads": {"1": {"x": -50, "y": 0}, "2": {"x": 50, "y": 0}}}


def run(project, rots, y=None):
    board = project.config().board()
    place = {f"D{i}": SimpleNamespace(x=10 * i, y=(y or [20] * len(rots))[i], rot=r, side="top")
             for i, r in enumerate(rots)}
    design = SimpleNamespace(comps=dict.fromkeys(place), part=lambda ref: PART)
    return polarity_findings(board, dict.fromkeys(place, GEO), place, design)


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
    (project.root / "hardware" / "boards" / "main.geometry.json").write_text(json.dumps(geo or led_bar_geo()))
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


def test_place_reads_the_geometry_as_the_plan_does(project, capsys):
    """A part not yet in the PCB dump is placed by the footprint `edakit part import` cached, as pcb plan reads it."""
    geo = led_bar_geo()
    lib = geo.pop("R1")
    place_project(project, geo=geo)
    toml = str(project.root / "edakit.toml")
    capsys.readouterr()
    assert cli.main(["pcb", "place", "--config", toml]) == 2            # without the library footprint: R1 unplaced
    assert "R1: R1 not in the footprint geometry" in capsys.readouterr().out
    cfg = project.config()
    name = project.part("C17604")["footprint"]
    f = cfg.artifact("footprints", part.file_name(name))
    f.write_text(json.dumps({**lib, "footprint": name}))
    assert cli.main(["pcb", "place", "--config", toml]) == 0
    out = capsys.readouterr().out
    assert "library geometry (edakit part import, not yet from the PCB): R1" in out
    assert [r for r in re.findall(r"^  (\w+) = \{", out, re.M)] == ["R1", "C1"]

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
    f = place_project(project, add=hand)
    loose = [ln for ln in f.read_text().splitlines(keepends=True) if ln.startswith(("D1 = ", "R2 = "))]
    assert len(loose) == 2 and all("auto = true" in ln for ln in loose)    # the example's auto rows: no host
    assert cli.main(["pcb", "place", "--write", "--config", str(project.root / "edakit.toml")]) == 0
    text = f.read_text()
    assert hand in text and all(ln in text for ln in loose) and text.count("auto = true }") == 3 and "\nC1 = " in text


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


# --- pcb place --rest (T.1): every part of the board without a row, or with an auto row – not only those tied to a
# host. Taken out of the example: R1 (layout.near: next to U2), its auto rows D1 and R2, J1 (layout.edge), SW1, D5, D6.

REST = ("R1", "D1", "R2", "D5", "D6", "J1", "SW1")


def placed_rows(out):
    return re.findall(r"^  (\w+) = \{", out, re.M)


def test_place_rest_gives_every_part_a_row_and_the_plan_passes(project, capsys):
    f = place_project(project, drop=REST)
    toml = str(project.root / "edakit.toml")
    capsys.readouterr()
    assert cli.main(["pcb", "place", "--config", toml]) == 0                # without --rest: only R1, next to U2
    assert placed_rows(capsys.readouterr().out) == ["R1"]
    assert cli.main(["pcb", "place", "--rest", "--only", "J1,D5", "--config", toml]) == 0
    assert placed_rows(capsys.readouterr().out) == ["D5", "J1"]
    assert cli.main(["pcb", "place", "--rest", "--write", "--config", toml]) == 0
    out = capsys.readouterr().out
    # R1 next to its host first; then the part with the most pins on nets of placed parts – D5, D6, R2 two, D1 and SW1
    # one, J1 none until D1 stands (VIN) –, by designator
    assert placed_rows(out) == ["R1", "D5", "D6", "R2", "D1", "J1", "SW1"]
    start, end = map(float, re.search(r"improvement: .*airline length \(without GND\) ([\d.]+) -> ([\d.]+) mm",
                                      out).groups())
    assert end < start                                                       # the improvement pass shortened it
    cfg = project.config()
    board = cfg.board()
    assert pcb.parts_without_row(board, Design.from_config(cfg)) == []
    assert all(board.place[r].auto for r in REST) and pcb.plan(cfg, board) == []
    after = f.read_text()
    assert cli.main(["pcb", "place", "--rest", "--write", "--config", toml]) == 0  # the same files give the same rows
    assert f.read_text() == after


def test_place_rest_brings_the_parts_tied_to_a_host_it_places(project, capsys):
    """U2 without a row: its R-EXT (layout.near) and its decoupling capacitor (L-12) come with it – U2 takes a spot only
    where they find theirs next to it."""
    place_project(project, drop=("U2", "R1", "C1"))
    toml = str(project.root / "edakit.toml")
    capsys.readouterr()
    assert cli.main(["pcb", "place", "--config", toml]) == 2
    assert "R1: next to U2, which is not in [place] – fix the host first" in capsys.readouterr().out
    assert cli.main(["pcb", "place", "--rest", "--write", "--config", toml]) == 0
    assert placed_rows(capsys.readouterr().out) == ["U2", "R1", "C1", "D1", "R2"]
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == []


def test_place_rest_improvement_swaps_and_moves_its_rows(project):
    """The improvement pass: D5 and D6 in the LED row, each in the other's slot – their cathodes cross on the way to
    U2.8 and U2.9, swapping the rows shortens the airline length by 0.18 mm; back would lengthen it. A move takes D5
    off the row to a spot shorter still. The plan check stays clean."""
    place_project(project, drop=("D5", "D6"))
    cfg = project.config()
    board, design = cfg.board(), Design.from_config(cfg)
    s = pcb.Placing(cfg, board, pcb.plan_geometry(cfg, board, design), design, set(), lambda r: True)
    s.add("D5", config.Placement(69, 34, 0, "top", auto=True))
    s.add("D6", config.Placement(65, 34, 0, "top", auto=True))
    found, total = s.findings(), s.total()
    assert s.swap("D5", "D6", found) == found
    assert (s.place["D5"].x, s.place["D6"].x) == (65, 69) and s.total() == pytest.approx(total - 0.18, abs=0.005)
    assert s.swap("D5", "D6", found) is None
    total = s.total()
    assert s.move("D5", found) == found and s.total() < total - pcb.PLACE_REST_EPS and s.place["D5"].y < 34


def test_place_rest_names_a_part_without_a_spot(project, capsys):
    geo = led_bar_geo()
    geo["SW1"] = footprint(60, 30, BUTTON)                                   # larger than any free part of the board
    f = place_project(project, drop=("SW1", "D5"), geo=geo)
    capsys.readouterr()
    assert cli.main(["pcb", "place", "--rest", "--write", "--config", str(project.root / "edakit.toml")]) == 2
    out = capsys.readouterr().out
    assert "SW1: no free spot on the top side – its box (60.0 x 30.0 mm) fits nowhere clear of the placed parts, the " \
           "holes and the outline" in out
    assert "\nD5 = " in f.read_text() and "SW1 = " not in f.read_text()      # the others are written


# --- the auto-layout's positions into [place], the takeover of a board placed before (step 2.1) ---------------------

# Recorded: easyeda_pcb_components of the Christmas bell's SMD board in its gate run 20261026-123018 (fab/smd/pcb.json),
# and the rows of its board file. EasyEDA keeps mil and reports U1 at -90.00000000000001° where the plan has 270.
BELL_PCB = [("C1", 2578.74, 1181.102, 0, 1), ("J1", 3149.6059999999998, 1181.102, 90, 1),
            ("LED3", 1968.504, 1889.764, 0, 1), ("R6", 2559.055, 472.441, 90, 1), ("R8", 866.142, 641.732, 0, 1),
            ("S2", 2834.646, 472.441, 0, 1), ("U1", 889.764, 1102.362, -90.00000000000001, 1)]
BELL_PLAN = {"C1": (65.5, 30, 0), "J1": (80, 30, 90), "LED3": (50, 48, 0), "R6": (65, 12, 90), "R8": (22, 16.3, 0),
             "S2": (72, 12, 0), "U1": (22.6, 28, 270)}
AUTO = {"C1": (70.2, 22.4, 90), "D1": (75.0, 12.0, 0), "R2": (40.0, 30.0, 180)}   # where an auto-layout left them


def bare_board(**keys):
    return config.Board(name="b", title="b", template="t", schematic="s", pcb="p", **keys)


def comps_of(records):
    return [{"designator": r, "x": x, "y": y, "rotation": rot, "layer": layer} for r, x, y, rot, layer in records]


def eda_at(board, ref, x, y, rot=0, side="top"):
    """A part as easyeda_pcb_components reports it when it stands at (x, y, rot, side) of the plan."""
    ex, ey, erot, layer = board.to_eda(x, y, rot, side)
    return {"designator": ref, "primitiveId": f"id_{ref}", "x": ex * MIL, "y": ey * MIL, "rotation": erot,
            "layer": layer}


def led_bar_pcb(board, spots):
    """The example's PCB as EasyEDA would report it: the parts of [place] where their rows put them, those of `spots`
    {ref: (x, y, rot)} there."""
    return ([eda_at(board, r, p.x, p.y, p.rot, p.side) for r, p in board.place.items() if r not in spots]
            + [eda_at(board, r, *s) for r, s in spots.items()])


def test_rows_from_the_positions_easyeda_reports():
    board = bare_board()
    design = SimpleNamespace(board_comps=lambda name: dict.fromkeys(BELL_PLAN))
    rows, absent = pcb.eda_rows(board, design, comps_of(BELL_PCB), auto=True)
    assert absent == [] and list(rows) == ["C1", "J1", "LED3", "R6", "R8", "S2", "U1"]
    assert {r: (p.x, p.y, p.rot) for r, p in rows.items()} == BELL_PLAN      # the board file's rows, to the float
    assert all(p.side == "top" and p.auto for p in rows.values())
    assert pcb.place_row(rows["U1"]) == '{ x = 22.6, y = 28.0, rot = 270, side = "top", auto = true }'
    board.place = {"U1": config.Placement(0, 0)}                             # a row the board file holds stays
    rows, _ = pcb.eda_rows(board, design, comps_of(BELL_PCB), auto=False)
    assert "U1" not in rows and len(rows) == 6 and not any(p.auto for p in rows.values())


@pytest.mark.parametrize("view", ["top", "bottom"])
@pytest.mark.parametrize("layer", [1, 2])
def test_pcb_apply_puts_a_row_back_where_easyeda_had_the_part(view, layer):
    """The row through Board.to_eda, as pcb apply writes it, is what EasyEDA reported – on either side, the plan seen
    from either side (view = "bottom" mirrors x and turns the rotation into 180 - rot), at any rotation."""
    board = bare_board(view=view)
    design = SimpleNamespace(board_comps=lambda name: {"U9": {}})
    for rot in (-90.00000000000001, 0, 30, 135.5, 270):
        rows, _ = pcb.eda_rows(board, design, comps_of([("U9", 1234.567, -321.5, rot, layer)]), auto=False)
        p = rows["U9"]
        assert p.side == ("top" if layer == 1 else "bottom") and 0 <= p.rot < 360
        x, y, erot, elayer = board.to_eda(p.x, p.y, p.rot, p.side)
        assert (x * MIL, y * MIL) == pytest.approx((1234.567, -321.5), abs=0.001 * MIL)   # within 0.001 mm
        assert abs((erot - rot + 180) % 360 - 180) < 1e-3 and elayer == layer


def test_rows_read_as_written():
    """pcb place's rows, on their 0.1 mm grid, as they always were; rows from EasyEDA to 0.001 mm and degree."""
    P = config.Placement
    assert pcb.place_row(P(62.8, 21.0, 90, "top", auto=True)) == \
        '{ x = 62.8, y = 21.0, rot = 90, side = "top", auto = true }'
    assert pcb.place_row(P(31.356, -5.0, 269.5, "bottom")) == '{ x = 31.356, y = -5.0, rot = 269.5, side = "bottom" }'
    assert pcb.place_row(P(-0.0001, 100, 0)) == '{ x = 0.0, y = 100.0, rot = 0, side = "top" }'


def test_write_back_adds_auto_rows_for_the_parts_without_one(project, capsys):
    f = place_project(project, drop=tuple(AUTO))
    before = f.read_text()
    cfg = project.config()
    board = cfg.board()
    comps = led_bar_pcb(board, AUTO)
    next(c for c in comps if c["designator"] == "U2")["x"] += MIL      # 1 mm off its row: the row stays, L-7 says so
    comps.append(eda_at(board, "X1", 10, 10))                         # in the PCB, not in the graph: no row
    assert pcb.write_back(cfg, board, comps, auto=True) == 0
    after = f.read_text()
    new = [ln for ln in after.splitlines() if ln not in before.splitlines()]
    assert new == ['C1 = { x = 70.2, y = 22.4, rot = 90, side = "top", auto = true }',
                   'D1 = { x = 75.0, y = 12.0, rot = 0, side = "top", auto = true }',
                   'R2 = { x = 40.0, y = 30.0, rot = 180, side = "top", auto = true }']
    assert [ln for ln in after.splitlines() if ln not in new] == before.splitlines()   # every other line as it was
    assert after.index("C2 = { x = 29") < after.index(new[0]) < after.index("[near]")  # at the end of [place]
    assert "3 rows written into hardware/boards/main.toml [place] with auto = true" in capsys.readouterr().out
    cfg = project.config()
    assert pcb.parts_without_row(cfg.board(), Design.from_config(cfg)) == []
    assert pcb.plan(cfg, cfg.board()) == []                  # the plan holds them like any row
    assert pcb.write_back(cfg, cfg.board(), comps, auto=True) == 0                    # again: nothing to write
    assert f.read_text() == after and "nothing to write" in capsys.readouterr().out


def test_write_back_names_a_part_that_is_not_in_the_pcb(project, capsys):
    place_project(project, drop=tuple(AUTO))
    cfg = project.config()
    comps = [c for c in led_bar_pcb(cfg.board(), AUTO) if c["designator"] != "R2"]
    assert pcb.write_back(cfg, cfg.board(), comps, auto=True) == 2
    out = capsys.readouterr().out
    assert "! R2: not in the PCB – no position to write (edakit pcb parts --write)" in out
    assert "2 rows written" in out and "R2" not in project.config().board().place


def stub_autolayout(monkeypatch, readings, clock=lambda: 0.0):
    """pcb.autolayout without EasyEDA: the auto-layout call is recorded, every reading of the PCB is the next of
    `readings`, the 10 s between them do not pass."""
    calls = []
    monkeypatch.setattr(pcb, "ensure_pcb_focus", lambda mcp: None)
    monkeypatch.setattr(pcb, "api", lambda mcp, path, *a, **k: calls.append(path))
    monkeypatch.setattr(pcb, "time", SimpleNamespace(sleep=lambda s: None, monotonic=clock))
    monkeypatch.setattr(pcb.eda, "list_pcb_components", lambda mcp: next(readings))
    return calls


def test_autolayout_writes_back_once_the_positions_stand_still(project, monkeypatch, capsys):
    place_project(project, drop=tuple(AUTO))
    cfg = project.config()
    board = cfg.board()
    moving = led_bar_pcb(board, {r: (x - 5, y, rot) for r, (x, y, rot) in AUTO.items()})
    turned = led_bar_pcb(board, {**AUTO, "R2": (40.0, 30.0, 0)})       # the same spots, R2 turned: still moving
    still = led_bar_pcb(board, AUTO)
    noisy = json.loads(json.dumps(still))                               # as EasyEDA reports it now and then
    next(c for c in noisy if c["designator"] == "C1")["rotation"] = 90.00000000000001
    readings = iter([moving, turned, still, noisy, still])
    calls = stub_autolayout(monkeypatch, readings)
    assert pcb.autolayout(cfg, board, None) == 0
    assert calls == ["PCB_Document.autoLayout"] and next(readings, None) is None   # three readings alike, then written
    got = project.config().board().place
    assert {r: (got[r].x, got[r].y, got[r].rot, got[r].auto) for r in AUTO} == {r: (*s, True) for r, s in AUTO.items()}


def test_autolayout_that_does_not_settle_writes_nothing(project, monkeypatch, capsys):
    f = place_project(project, drop=tuple(AUTO))
    before = f.read_text()
    cfg = project.config()
    board = cfg.board()
    drift = itertools.count()
    readings = (led_bar_pcb(board, {r: (x + next(drift), y, rot) for r, (x, y, rot) in AUTO.items()})
                for _ in itertools.count())
    clock = itertools.count(0, 100)                                    # 100 s each time the clock is read
    stub_autolayout(monkeypatch, readings, lambda: float(next(clock)))
    assert pcb.autolayout(cfg, board, None) == 2
    assert "did not settle in time – nothing written into [place]" in capsys.readouterr().out
    assert f.read_text() == before


class StubMcp:
    def close(self):
        pass


def stub_easyeda(monkeypatch, comps):
    """The EasyEDA commands of pcb without EasyEDA: server, bridge and documents stand in, the PCB reports comps."""
    from edakit import eda
    monkeypatch.setattr(eda, "start", lambda *a, **k: StubMcp())
    monkeypatch.setattr(eda, "wait_for_bridge", lambda mcp: True)
    for name in ("open_project", "open_pcb"):
        monkeypatch.setattr(eda, name, lambda *a, **k: None)
    monkeypatch.setattr(eda, "list_pcb_components", lambda mcp: comps)


def test_takeover_takes_a_board_placed_before_as_fixed_rows(project, monkeypatch, capsys):
    """A board placed and routed before: only U1, U2, J1 and SW1 have a row. The takeover gives every other part a
    fixed row where EasyEDA has it, so that pcb apply leaves it there – the tracks stay on its pads."""
    keep = ("U1", "U2", "J1", "SW1")
    cfg = project.config()
    placed = led_bar_pcb(cfg.board(), AUTO)                            # the PCB as it stands, all 17 parts
    f = place_project(project, drop=tuple(r for r in cfg.board().place if r not in keep) + tuple(AUTO))
    before = f.read_text()
    stub_easyeda(monkeypatch, placed)
    toml = str(project.root / "edakit.toml")
    capsys.readouterr()
    assert cli.main(["pcb", "takeover", "--config", toml]) == 0         # without --write: shown only
    out = capsys.readouterr().out
    assert f.read_text() == before and "13 parts without a row – --write puts them into [place]" in out
    assert '  D1 = { x = 75.0, y = 12.0, rot = 0, side = "top" }\n' in out          # fixed: no auto
    assert cli.main(["pcb", "takeover", "--write", "--config", toml]) == 0
    assert "13 rows written into hardware/boards/main.toml [place] (fixed)" in capsys.readouterr().out
    board = project.config().board()
    assert len(board.place) == 17 and not any(p.auto for p in board.place.values())
    for c in placed:                                                    # what pcb apply writes = what EasyEDA has
        p = board.place[c["designator"]]
        x, y, rot, layer = board.to_eda(p.x, p.y, p.rot, p.side)
        assert (x * MIL, y * MIL) == pytest.approx((c["x"], c["y"]), abs=0.001 * MIL)
        assert (rot, layer) == (c["rotation"] % 360, c["layer"])
    assert cli.main(["pcb", "takeover", "--write", "--config", toml]) == 0   # once: nothing left to take over
    assert "nothing to write" in capsys.readouterr().out


# --- polarised parts of the configured kinds point the same way (#60): the LED tests above with other kinds, one
# direction for the whole board, and the example's bar with D3 turned by 180°

def polar(project, rots, kind="diode", roles=("anode", "cathode"), sides=None, uniform=None, y=None):
    """Parts D0, D1, … of `kind` in a row at y = 20 (or `y`), with the pin roles `roles` (pin 1 at -x, pin 2 at +x at
    0°) -> the findings of the plan's polarity check, with `uniform` as the board file would give it."""
    board = project.config().board()
    if uniform is not None:
        board.uniform = uniform
    part = {"kind": kind, "pins": {"1": {"role": roles[0]}, "2": {"role": roles[1]}}}
    place = {f"D{i}": SimpleNamespace(x=10 * i, y=(y or [20] * len(rots))[i], rot=r, side=(sides or ["top"] * 9)[i])
             for i, r in enumerate(rots)}
    design = SimpleNamespace(comps=dict.fromkeys(place), part=lambda ref: part)
    return pcb.polarity_findings(board, dict.fromkeys(place, GEO), place, design)


def test_diodes_in_a_row_point_the_same_way_when_the_board_asks(project):
    assert polar(project, [0, 180]) == []                                     # no key: only LEDs, as before
    assert polar(project, [0, 180], uniform={"diode": "row"}) == [
        "diodes in a row (D0, D1): cathode of D1 points the other way than D0 – turn it by 180°"]
    assert polar(project, [0, 180, 180], uniform={"diode": "row"}) == [
        "diodes in a row (D0, D1, D2): cathode of D1, D2 points the other way than D0 – turn them by 180°"]
    assert polar(project, [0, 180], kind="led", uniform={"diode": "row"}) == []    # a table names every kind it checks


def test_one_direction_for_the_whole_board(project):
    assert polar(project, [0], kind="led", uniform={"led": "+x"}) == []      # cathode at +x
    assert polar(project, [180], kind="led", uniform={"led": "+x"}) == [
        "D0 (led): cathode points -x, uniform +x – turn it by 180° (rot = 0)"]
    assert polar(project, [90], kind="led", uniform={"led": "+x"}) == [       # alone, not in a row
        "D0 (led): cathode points +y, uniform +x – turn it by 90° (rot = 0)"]
    # the other side than view: seen from its own side, mirrored in x
    assert polar(project, [0], kind="led", sides=["bottom"], uniform={"led": "+x"}) == [
        "D0 (led): cathode points -x, uniform +x – turn it by 180° (rot = 180)"]
    assert polar(project, [180], kind="led", sides=["bottom"], uniform={"led": "+x"}) == []


def test_a_buzzer_points_its_minus_the_given_way(project):
    roles = ("plus", "minus")
    assert polar(project, [0], kind="buzzer", roles=roles, uniform={"buzzer": "-x"}) == [
        "D0 (buzzer): minus points +x, uniform -x – turn it by 180° (rot = 180)"]
    assert polar(project, [180], kind="buzzer", roles=roles, uniform={"buzzer": "-x"}) == []
    assert polar(project, [0, 180], kind="buzzer", roles=("plus_a", "minus_a"), uniform={"buzzer": "row"}) == [
        "buzzers in a row (D0, D1): minus of D1 points the other way than D0 – turn it by 180°"]


def test_a_part_without_one_plus_and_one_minus_pin_is_skipped_and_named(project, capsys):
    place_project(project, drop=())
    rgb = project.part("C2297")
    rgb["pins"]["2"]["role"] = "cathode_red"                                    # no single cathode any more
    project.save_part("C2297", rgb)
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == []                                    # no key: skipped, as before, unnamed
    assert "uniform" not in capsys.readouterr().out
    f = project.root / "hardware" / "boards" / "main.toml"
    f.write_text(f.read_text().replace('view = "top"', 'view = "top"\nuniform = { led = "row" }'))
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == []
    assert "  uniform: skipped – not exactly one anode/plus and one cathode/minus pin: D2, D3, D4, D5, D6, D7, D8, D9 " \
           "(led)" in capsys.readouterr().out


def test_the_bar_with_d3_turned(project, capsys):
    """The proposal's case: with D3 turned the plan names it as long as the LEDs' kind is led; with the parts entry
    saying diode it passed – now `uniform` names the kind."""
    f = place_project(project, drop=())
    f.write_text(f.read_text().replace('D3 = { x = 57, y = 34, rot = 0,', 'D3 = { x = 57, y = 34, rot = 180,'))
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == ["LEDs in a row (D2, D3, D4, D5, D6, D7, D8, D9): anode of D3 points the other "
                                          "way than D2 – turn them by 180°"]
    part = project.part("C2297")
    part["kind"] = "diode"
    project.save_part("C2297", part)
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == []
    f.write_text(f.read_text().replace('view = "top"', 'view = "top"\nuniform = { diode = "row" }'))
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == ["diodes in a row (D2, D3, D4, D5, D6, D7, D8, D9): cathode of D3 points the "
                                          "other way than D2 – turn it by 180°"]
    f.write_text(f.read_text().replace('uniform = { diode = "row" }', 'uniform = { diode = "+x" }'))
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == [                             # the whole board: D1, the SS34, is a diode too
        "D1 (diode): cathode points -x, uniform +x – turn it by 180° (rot = 180)",
        "D3 (diode): cathode points -x, uniform +x – turn it by 180° (rot = 0)"]


# --- mated plugs and the mechanical model (#62): the example with the test geometry; J1 at (84, 12) turned by 90°, so
# that its footprint's +y points into the board (-x) and -y to the right edge (+x, the outline at x = 90); its box
# reaches x = 81.75 … 89.5, y = 9 … 15. U2 (SOIC-16 turned by 90°) covers x = 60.8 … 71.2, y = 14 … 20.

def with_mate(project, mate=None, f=None, **entry):
    """The example with its test geometry, J1's parts entry (C131337) given `mate` and further fields."""
    f = f or place_project(project, drop=())
    part = project.part("C131337")
    if mate is not None:
        part["mate"] = mate
    part.update(entry)
    project.save_part("C131337", part)
    return f


INTO_BOARD = {"box": [-2.5, 2.25, 2.5, 14.25], "h_mm": 4.5, "exit": "+y"}    # 12 mm out of J1 towards U2 (-x)
TO_EDGE = {"box": [-2.5, -7.5, 2.5, -5.5], "h_mm": 4.5, "exit": "-y"}       # 2 mm out of J1, over the edge (+x)


def test_a_mated_plug_into_the_board_names_the_part_it_hits(project, capsys):
    with_mate(project, INTO_BOARD)
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == ["J1: mated plug reaches into D1 (top)", "J1: mated plug reaches into U2 (top)",
                                          "J1: mated plug leaves towards -x but ends 69.8 mm inside the outline"]


def test_a_mated_plug_over_the_edge_passes(project):
    with_mate(project, TO_EDGE)
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == []


def test_a_sideways_plug_that_stops_short_of_the_outline(project):
    with_mate(project, {"box": [-2.5, -5.0, 2.5, -3.0], "exit": "-y"})         # ends at x = 89, 1 mm before the edge
    cfg = project.config()
    assert "J1" in cfg.board().edge_ok                                       # edge_ok lifts neither finding
    assert pcb.plan(cfg, cfg.board()) == ["J1: mated plug leaves towards +x but ends 1.0 mm inside the outline"]


def test_a_cable_that_leaves_upwards_needs_no_outline(project):
    with_mate(project, {**INTO_BOARD, "exit": "+z"})
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == ["J1: mated plug reaches into D1 (top)", "J1: mated plug reaches into U2 (top)"]


def test_a_mated_plug_over_an_smd_part_within_the_silkscreen_tolerance(project):
    """The plug is a body without a margin, the other part's box has its silkscreen and pads: silk_overlap_mm holds
    for an SMD part as it does between two SMD boxes."""
    mate = {"box": [-2.5, 2.25, 2.5, 14.25], "exit": "+z"}                      # y = 9.5 … 14.5: 0.5 mm into U2
    f = with_mate(project, mate, f=place_project(project, drop=("D1",)))       # D1 out of its way
    f.write_text(f.read_text().replace('view = "top"', 'view = "top"\nsilk_overlap_mm = 0.8'))
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == []
    f.write_text(f.read_text().replace("silk_overlap_mm = 0.8", "silk_overlap_mm = 0.3"))
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == ["J1: mated plug reaches into U2 (top) – 0.50 mm (silk_overlap_mm 0.3)"]


def test_a_plug_turns_and_mirrors_with_its_part():
    board = config.Board(name="b", title="b", template="t", schematic="s", pcb="p")
    mate = {"box": [-1.0, 2.0, 1.0, 4.0], "exit": "+y"}
    _, box, d, far = pcb.mate_shape(board, config.Placement(10, 5, 0, "bottom"), mate)   # local y mirrored
    assert box == pytest.approx((9, 1, 11, 3)) and pcb.exit_way(d) == "-y" and far == pytest.approx((10, 1))
    _, box, d, far = pcb.mate_shape(board, config.Placement(10, 5, 90, "top"), mate)
    assert box == pytest.approx((6, 4, 8, 6)) and pcb.exit_way(d) == "-x" and far == pytest.approx((6, 5))
    board.view = "bottom"            # seen from the bottom: x mirrored, EasyEDA rotation 180 - rot (Board.to_eda)
    _, box, d, _ = pcb.mate_shape(board, config.Placement(10, 5, 0, "top"), {**mate, "exit": "+x"})
    assert box == pytest.approx((9, 1, 11, 3)) and pcb.exit_way(d) == "+x"
    _, _, d, _ = pcb.mate_shape(board, config.Placement(10, 5, 45, "top"), {**mate, "exit": "+x"})
    assert pcb.exit_way(d) == pytest.approx([0.7071, 0.7071])                 # turned by 45°: the unit vector
    assert pcb.mate_shape(board, config.Placement(10, 5, 0, "top"), {**mate, "exit": "+z"})[2:] == (None, None)


def test_two_mated_plugs_side_by_side(project):
    f = with_mate(project, {"box": [-4, -7.5, 4, -5.5], "exit": "-y"})          # 8 mm wide plugs, J1's y = 8 … 16
    g = project.graph()
    g["graph"]["components"].append({**project.comp(g, "J1"), "designator": "J2"})
    project.save_graph(g)
    f.write_text(f.read_text().replace('SW1 = {', 'J2 = { x = 84, y = 19, rot = 90, side = "top" }\nSW1 = {'))
    geo = led_bar_geo()
    geo["J2"] = geo["J1"]
    (project.root / "hardware" / "boards" / "main.geometry.json").write_text(json.dumps(geo))
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == ["J1: mated plug reaches into the mated plug of J2 (top)"]


def test_a_parts_entry_with_a_wrong_mate_is_named(project):
    f = with_mate(project, {"box": [-2.5, -7.5, 2.5], "exit": "sideways"}, body={"h_mm": -1})
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == [
        "J1: parts entry C131337: body.h_mm must be a height in mm, 0 or more",
        "J1: parts entry C131337: mate.box must be [x0, y0, x1, y1] in footprint mm with x0 < x1 and y0 < y1",
        "J1: parts entry C131337: mate.exit must be one of +x, -x, +y, -y, +z"]
    with_mate(project, {"box": [-2.5, -7.5, 2.5, -5.5], "exit": ["+x"], "h_mm": "6"}, f=f, body={"h_mm": 6})
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == ["J1: parts entry C131337: mate.exit must be one of +x, -x, +y, -y, +z",
                                          "J1: parts entry C131337: mate.h_mm must be a height in mm, 0 or more"]


def test_mechanical_model(project, capsys):
    lead = project.part("C131337")["lead"]
    lead["*"]["length_mm"] = 3.4
    f = with_mate(project, TO_EDGE, f=place_project(project, drop=("D1", "R2")), body={"h_mm": 6.0}, lead=lead)
    key = project.comp(project.graph(), "U2")["lcsc"]
    part = project.part(key)
    part["body"] = {"h_mm": 1.75}
    project.save_part(key, part)
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == []
    assert "  mechanical model -> " in capsys.readouterr().out
    mech = json.loads((project.root / "build" / "edakit" / "mech_main.json").read_text())
    assert (mech["board"], mech["units"], mech["view"], mech["thickness_mm"]) == ("main", "mm", "top", 1.6)
    assert mech["outline"][0] == pytest.approx([88, 0])
    assert mech["holes"] == [{"x": 3.5, "y": 3.5, "d": 3.2}, {"x": 86.5, "y": 36.5, "d": 3.2}]
    assert mech["tooling"] == [{"x": 3.5, "y": 36.5, "d": 1.152}, {"x": 86.5, "y": 3.5, "d": 1.152}]
    j1 = mech["parts"]["J1"]
    assert (j1["side"], j1["x"], j1["y"], j1["rot"], j1["h_mm"]) == ("top", 84, 12, 90, 6.0)
    assert j1["box"] == pytest.approx([81.75, 9, 89.5, 15])
    assert j1["mate"] == {"box": pytest.approx([89.5, 9.5, 91.5, 14.5]), "h_mm": 4.5, "exit": "+x"}
    assert j1["protrusion_mm"] == pytest.approx(1.8)                         # 3.4 mm lead - 1.6 mm board
    assert [(q["pad"], q["x"], q["y"]) for q in j1["leads"]] == [("1", pytest.approx(84), pytest.approx(11)),
                                                                ("2", pytest.approx(84), pytest.approx(13))]
    assert mech["parts"]["U2"]["h_mm"] == 1.75 and "mate" not in mech["parts"]["U2"]
    assert set(mech["parts"]["R1"]) == {"side", "x", "y", "rot", "box"}       # nothing known: nothing guessed
    assert mech["unplaced"] == ["D1", "R2"]                                   # their rows taken out above
    f.write_text(f.read_text().replace('view = "top"', 'view = "top"\nthickness_mm = 1.0'))
    cfg = project.config()
    pcb.plan(cfg, cfg.board())
    mech = json.loads((project.root / "build" / "edakit" / "mech_main.json").read_text())
    assert mech["parts"]["J1"]["protrusion_mm"] == pytest.approx(2.4)


def test_without_the_new_fields_the_plan_is_as_before(project, capsys):
    place_project(project, drop=())
    cfg = project.config()
    assert pcb.plan(cfg, cfg.board()) == []
    assert "mechanical model" not in capsys.readouterr().out                 # output as before …
    mech = json.loads((project.root / "build" / "edakit" / "mech_main.json").read_text())
    assert sorted(mech["parts"]) == sorted(cfg.board().place)               # … the model is written in any case
    assert all(set(p) == {"side", "x", "y", "rot", "box"} for p in mech["parts"].values())


# --- the DRC's Import Changes item: acknowledgement pending or a real difference (#67) -----------------------------

IMPORT = {"errorType": "Netlist Error", "ruleName": "Import Changes"}
CLEARANCE = {"errorType": "Clearance", "ruleName": "Safe Spacing"}
NO_DIFF = {"parts": {}, "nets": []}


def test_drc_exit_codes():
    """route all|drc and silk apply|check: 3 when EasyEDA only waits for the acknowledgement, as `edakit lock` exits 3
    while waiting for another session."""
    assert pcb.drc_exit([], None) == 0
    assert pcb.drc_exit([IMPORT], NO_DIFF) == 3
    assert pcb.drc_exit([IMPORT], {"parts": {"props": ["D1"]}, "nets": []}) == 2
    assert pcb.drc_exit([IMPORT], None) == 2                  # not compared
    assert pcb.drc_exit([IMPORT, CLEARANCE], NO_DIFF) == 2
    assert pcb.drc_exit([CLEARANCE], None) == 2


def test_import_verdict_names_the_differences_and_the_fix():
    assert pcb.import_verdict([], None) == (True, "no Import Changes item")
    ok, text = pcb.import_verdict([IMPORT], {"parts": {"missing": ["R7"], "props": ["D1", "D2"]},
                                            "nets": [["U1.3", "", "GND"]]})
    assert not ok
    assert text == ("schematic and PCB differ – missing in the PCB: R7; properties differ from the schematic: D1, D2 "
                    "→ edakit pcb parts --write; pad nets: U1.3 – instead of GND → edakit pcb nets --write")


def test_drc_report_compares_only_for_an_import_item(project, monkeypatch, capsys):
    cfg = project.config()
    calls = []
    monkeypatch.setattr(pcb, "netlist_diff", lambda cfg, board, mcp: calls.append(1) or NO_DIFF)
    assert pcb.drc_report(cfg, cfg.board(), None, [CLEARANCE]) == 2 and not calls
    out = cfg.artifact("route", "main_netlist_diff.json")
    assert pcb.drc_report(cfg, cfg.board(), None, [IMPORT], out) == 3 and calls
    assert json.loads(out.read_text()) == NO_DIFF
    assert "open Design → Import Changes once" in capsys.readouterr().out
    assert pcb.drc_report(cfg, cfg.board(), None, []) == 0


def test_route_drc_exits_3_for_the_acknowledgement_alone(project, monkeypatch):
    from argparse import Namespace

    from edakit import eda

    class Mcp:
        def close(self):
            pass
    for name in ("open_project", "open_pcb"):
        monkeypatch.setattr(eda, name, lambda *a, **k: None)
    monkeypatch.setattr(eda, "connect", lambda *a, **k: Mcp())
    monkeypatch.setattr(eda, "drc", lambda mcp, out=None: [IMPORT])
    monkeypatch.setattr(pcb, "netlist_diff", lambda cfg, board, mcp: NO_DIFF)
    args = Namespace(board=None, action="drc", verbose=False, clearance=None, passes=None, threads=1,
                     no_optimizer=False, cleanup=False)
    assert route.main(project.config(), args) == 3
    monkeypatch.setattr(pcb, "netlist_diff", lambda cfg, board, mcp: {"parts": {"swapped": ["D1"]}, "nets": []})
    assert route.main(project.config(), args) == 2
