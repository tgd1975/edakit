"""Placement rule: LEDs side by side have their anode towards the same side."""

from types import SimpleNamespace

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
