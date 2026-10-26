"""Placement rule: LEDs side by side have their anode towards the same side. The pour outline."""

from types import SimpleNamespace

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from edakit import config, pcb, route
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


def under_module(project, parts, geo=HEADER_GEO, **keys):
    """The plan check of a 90 x 40 mm board without holes: U1 at (45, 20) mm, `parts` {ref: (x, y)} on top at 0°."""
    rows = "\n".join(f'{r} = {{ x = {x}, y = {y}, rot = 0, side = "top" }}' for r, (x, y) in
                     {"U1": (45, 20), **parts}.items())
    (project.root / "hardware" / "boards" / "main.toml").write_text(f"[outline]\nrect = [90, 40]\n\n[place]\n{rows}\n")
    cfg = project.config()
    board = cfg.board()
    for key, value in keys.items():          # the keys themselves: test_config.py
        setattr(board, key, value)
    geo = {r: geo[r] for r in board.place}
    place, boxes, tht, _, _ = pcb.build_plan(cfg, board, geo)
    return pcb.check_plan(cfg, board, geo, place, boxes, tht)


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
