"""LIM.i/charge (maker-coverage FT-4): a linear charger's programmed current – prog_v over the PROG resistor – within
the charger's i_out_max_a and the cell's i_charge_max_a. The numbers are the MCP73831's: IREG = 1000 V / RPROG,
15–500 mA (data sheet DS20001984H, 5.1.2)."""

import json

from helpers import check
from reference import Project, add, resistor, wire

from edakit.design import Design

CHARGER = {"lcsc": "C9100100", "mpn": "MCP73831 numbers (test part)", "kind": "ic", "verified": {"by": "test"},
           "values": {"prog_v": 1000}, "limits": {"i_out_max_a": 0.5},
           "pins": {"1": {"name": "STAT", "type": "output"}, "2": {"name": "VSS", "type": "ground"},
                    "3": {"name": "VBAT", "type": "power_output", "role": "bat"},
                    "4": {"name": "VDD", "type": "power_in"}, "5": {"name": "PROG", "type": "passive", "role": "prog"}}}
HOLDER = {"lcsc": "C9100102", "mpn": "single-cell holder (test part)", "kind": "battery_holder",
          "verified": {"by": "test"}, "limits": {"i_max_a": 2},
          "pins": {"1": {"name": "+", "type": "passive", "role": "plus"},
                   "2": {"name": "-", "type": "passive", "role": "minus"}}}


def charger(p, r_prog, cell_max=None):
    """U100 from +5V charges BT100 through VBAT; R100 = R_PROG to ground."""
    p.save_part(CHARGER["lcsc"], CHARGER)
    p.save_part(HOLDER["lcsc"], HOLDER)
    resistor(p, "C9100101", r_prog)
    g = p.graph()
    add(g, "U100", "ic", CHARGER["lcsc"], {"1": "STAT", "2": "VSS", "3": "VBAT", "4": "VDD", "5": "PROG"}, nc=["1"])
    add(g, "R100", "resistor", "C9100101", {"1": "1", "2": "2"})
    add(g, "BT100", "battery_holder", HOLDER["lcsc"], {"1": "+", "2": "-"}, bom=False)
    wire(g, "+5V", "U100.4")
    wire(g, "GND", "U100.2", "R100.2", "BT100.2")
    wire(g, "CHG_PROG", "U100.5", "R100.1", v=(0, 1.1))
    wire(g, "VBAT", "U100.3", "BT100.1", v=(0, 4.2))
    p.save_graph(g)
    if cell_max is not None:
        sim = json.loads((p.root / "hardware" / "sim.json").read_text())
        sim.setdefault("cells", {})["lipo"] = {"v": 3.7, "r": 0.1, "i_charge_max_a": cell_max}
        sim.setdefault("supplies", {}).setdefault("cells", {})["BT100"] = "lipo"
        (p.root / "hardware" / "sim.json").write_text(json.dumps(sim, indent=1))


def charge(p):
    cfg = p.config()
    rep = check(Design.from_config(cfg), cfg)
    return [(f.place, f.severity, f.source) for f in rep.findings if f.code == "LIM.i" and f.grade == "charge"]


def test_2k_programs_500_mA_the_charger_allows(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    charger(p, 2000)
    assert charge(p) == []


def test_a_smaller_prog_resistor_exceeds_the_charger(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    charger(p, 1500)                                  # 1000 V / 1.5 kΩ = 667 mA
    assert [(pl, s) for pl, s, _ in charge(p)] == [("U100", "warning")]


def test_the_cell_takes_less_than_the_charger_gives(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    charger(p, 2000, cell_max=0.2)                    # 500 mA into a cell of 0.2 A
    found = charge(p)
    assert [(pl, s) for pl, s, _ in found] == [("U100", "warning")] and "cells.lipo" in found[0][2]
