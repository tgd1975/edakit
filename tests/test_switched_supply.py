"""A board on cells behind a power switch (handbook 18, the 555 blinker): a load holds the cells to its current budget
(R-3 and R-4 of the example), and a part the switch turns off is unpowered, not out of its operating range."""

import shutil

import pytest

from edakit.design import Design
from edakit.sim import run as simrun

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")

# test parts – values for the test, not from a datasheet
HOLDER = {"kind": "battery_holder", "verified": {"by": "test"},
          "pins": {"1": {"name": "+", "type": "passive", "role": "plus"},
                   "2": {"name": "-", "type": "passive", "role": "minus"}}}
SWITCH = {"kind": "switch", "verified": {"by": "test"},
          "pins": {"1": {"name": "1", "type": "passive", "role": "throw_a"},
                   "2": {"name": "2", "type": "passive", "role": "common"},
                   "3": {"name": "3", "type": "passive", "role": "throw_b"}}}
CHIP = {"kind": "ic", "verified": {"by": "test"}, "values": {"behavior": "logic", "icc_a": 2e-4},
        "limits": {"vdd_op_min_v": 1.5, "vdd_op_max_v": 15},
        "pins": {"1": {"name": "GND", "type": "ground"}, "2": {"name": "VDD", "type": "power_in"}}}
LOAD = {"kind": "resistor", "verified": {"by": "test"}, "values": {"value_ohm": 1000.0},
        "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}}}


def board():
    """BT8 → SW8 (common to throw_a: on) → VDD: U8 (1.5–15 V) and a 1 kΩ load R8."""
    parts = {"H": HOLDER, "S": SWITCH, "U": CHIP, "R": LOAD}
    comps = [{"designator": "BT8", "type": "battery_holder", "lcsc": "H", "pins": {"1": "+", "2": "-"}},
             {"designator": "SW8", "type": "switch", "lcsc": "S", "pins": {"1": "1", "2": "2", "3": "3"}, "nc": ["3"]},
             {"designator": "U8", "type": "ic", "lcsc": "U", "pins": {"1": "GND", "2": "VDD"}},
             {"designator": "R8", "type": "resistor", "lcsc": "R", "value": "1k", "pins": {"1": "1", "2": "2"}}]
    nets = [{"name": "VBAT", "pins": ["BT8.1", "SW8.2"], "v": [0, 3.3]},
            {"name": "VDD", "pins": ["SW8.1", "U8.2", "R8.1"], "v": [0, 3.3]},
            {"name": "GND", "pins": ["BT8.2", "U8.1", "R8.2"], "v": [0, 0]}]
    return Design.from_data({"name": "t", "version": "1", "ground": "GND", "components": comps, "nets": nets}, parts)


def simulate(cell_v=3.0, on_budget=0.005, off_budget=1e-6):
    sim = {"cells": {"c": {"v": cell_v, "r": 0.5}}, "supplies": {"s": {"BT8": "c"}},
           "loads": {"on": {"leds_on": [], "expect": {"BT8": {"i_max_a": on_budget}}},
                     "off": {"throw": {"SW8": "throw_b"}, "leds_on": [], "expect": {"BT8": {"i_max_a": off_budget}}}}}
    return simrun.run_all(board(), sim)["checks"]


def rows(checks, item, check):
    return {c["scenario"].split("/")[1]: c for c in checks if c["item"] == item and c["check"] == check}


def test_a_load_holds_the_cells_to_its_budget():
    budget = rows(simulate(), "BT8", "current from the cell (expected in this load)")
    assert {s: (r["id"], r["result"]) for s, r in budget.items()} == {"on": ("LIM.i", "pass"), "off": ("LIM.i", "pass")}
    assert float(budget["on"]["actual"].split()[0]) == pytest.approx(3.2e-3, rel=0.01)  # 3 V / 1 kΩ + U8's 0.2 mA
    assert budget["off"]["expected"] == "≤ 0.001 mA"
    budget = rows(simulate(on_budget=0.003), "BT8", "current from the cell (expected in this load)")
    assert budget["on"]["result"] == "fail"                                             # 3.2 mA against 3 mA
    assert not [c for c in simulate() if c["id"] == "SIM.config"]   # before: "BT8 is neither a source nor a net"


def test_a_part_its_switch_turns_off_is_unpowered():
    supply = rows(simulate(), "U8", "supply voltage at VDD inside its operating range")
    assert supply["on"]["result"] == "pass"
    assert (supply["off"]["result"], supply["off"]["actual"]) == ("info", "0 V")        # before: a failure at 0 V
    assert supply["off"]["expected"].startswith("unpowered")
    low = rows(simulate(cell_v=1.0), "U8", "supply voltage at VDD inside its operating range")
    assert low["on"]["result"] == "fail"                         # 1.0 V is powered and below its 1.5 V: still found


def test_a_logic_part_clamps_a_supply_below_its_ground():
    """Cells upside down and no protection: a CMOS IC's substrate diode from its ground to its supply conducts – amps
    from the cells, as on the bench; before, U8's supply simply sat at −3 V and the cells gave R8's 3 mA."""
    budget = rows(simulate(cell_v=-3.0), "BT8", "current from the cell (expected in this load)")
    assert budget["on"]["result"] == "fail" and float(budget["on"]["actual"].split()[0]) > 1.0
    supply = rows(simulate(cell_v=-3.0), "U8", "supply voltage at VDD inside its operating range")
    assert supply["on"]["result"] == "fail"                      # −0.9 V or so: not switched off, reversed


def test_an_output_resistance_spreads_with_the_corners():
    """The LMC555's discharge pin of handbook 18: ≤ 150 mV at 1 mA with 1.5 V, about 15 Ω at 5 V – one r_out_ohm of
    150 Ω held R-4's 5 mA budget on paper while a board at 3.2 V draws 7 mA (M-1). r_out_ohm [min, typ, max] takes the
    spread corner: min with the most current, max with the least."""
    chip = {**CHIP, "values": {"behavior": "logic", "icc_a": 0.0, "r_out_ohm": [15, 50, 150]},
            "pins": {**CHIP["pins"], "3": {"name": "DIS", "type": "output", "drive": "open_drain"}}}
    parts = {"H": HOLDER, "S": SWITCH, "U": chip, "R": LOAD}
    comps = [{"designator": "BT8", "type": "battery_holder", "lcsc": "H", "pins": {"1": "+", "2": "-"}},
             {"designator": "SW8", "type": "switch", "lcsc": "S", "pins": {"1": "1", "2": "2", "3": "3"}, "nc": ["3"]},
             {"designator": "U8", "type": "ic", "lcsc": "U", "pins": {"1": "GND", "2": "VDD", "3": "DIS"},
              "states": {"DIS": "low"}},
             {"designator": "R8", "type": "resistor", "lcsc": "R", "value": "1k", "pins": {"1": "1", "2": "2"}}]
    nets = [{"name": "VBAT", "pins": ["BT8.1", "SW8.2"], "v": [0, 3.3]},
            {"name": "VDD", "pins": ["SW8.1", "U8.2", "R8.1"], "v": [0, 3.3]},
            {"name": "SINK", "pins": ["R8.2", "U8.3"], "v": [0, 3.3]},
            {"name": "GND", "pins": ["BT8.2", "U8.1"], "v": [0, 0]}]
    d = Design.from_data({"name": "t", "version": "1", "ground": "GND", "components": comps, "nets": nets}, parts)
    sim = {"cells": {"c": {"v": 3.0, "r": 0.001}}, "supplies": {"s": {"BT8": "c"}}, "spread": ["min", "typ", "max"],
           "loads": {"on": {"leds_on": [], "expect": {"BT8": {"i_max_a": 1}}}}}
    out = simrun.run_all(d, sim)
    amps = {c["scenario"].rsplit("/", 1)[-1]: float(c["actual"].split()[0]) for c in out["checks"]
            if c["item"] == "BT8" and c["check"] == "current from the cell (expected in this load)"}
    assert amps == pytest.approx({"spread-min": 3.0 / 1015, "vf-typ": 3.0 / 1050, "spread-max": 3.0 / 1150},
                                 rel=0.002)
