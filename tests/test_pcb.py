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
