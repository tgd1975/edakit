"""Stage E seen red at the supplies: a part outside its operating range, an input between its thresholds, a source or
a cell fed backwards."""

import json
import shutil

import pytest

from test_sim import failing, simulate

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")

RANGE = "supply voltage at VDD inside its operating range"


def test_supply_inside_the_operating_range(project):
    out = simulate(project)                                       # the example: U2 (TLC5916, VDD 3–5.5 V) on 3V3
    ok = [c for c in out["checks"] if c["item"] == "U2" and c["check"] == RANGE]
    assert len(ok) == 12 and all(c["result"] == "pass" and c["actual"] == "3.3 V" for c in ok)
    part = project.part("C90107")
    part["ratings"]["vdd_op_min"] = 4.5                           # a 5 V-only part like the TPIC6B595 on 3V3
    project.save_part("C90107", part)
    bad = failing(simulate(project))
    assert {(c["id"], c["item"], c["check"], c["actual"], c["expected"]) for c in bad} == {
        ("E-3", "U2", RANGE, "3.3 V", "4.5 … 5.5 V")}
    assert len(bad) == 12                                         # in every scenario
    part["ratings"]["vdd_op_min"] = 3.0
    part["pins"]["16"]["v_op"] = [4.5, 5.5]                       # the pin's own range wins over the part's
    project.save_part("C90107", part)
    assert {(c["item"], c["expected"]) for c in failing(simulate(project))} == {("U2", "4.5 … 5.5 V")}


def five_volt_driver(project):
    """U2 (TLC5916) on +5V instead of 3V3, with its thresholds from TI SLVS695D 7.3: VIH 0.7 × VDD, VIL 0.3 × VDD."""
    g = project.graph()
    for ref in ("U2.16", "C1.1"):
        project.net(g, "3V3")["pins"].remove(ref)
        project.net(g, "+5V")["pins"].append(ref)
    project.save_graph(g)
    thresholds(project)


def thresholds(project):
    part = project.part("C90107")
    part["params"].update(vih_ratio=0.7, vil_ratio=0.3)
    project.save_part("C90107", part)


def test_inputs_at_a_valid_logic_level(project):
    thresholds(project)                                           # U2 on 3V3: VIH 2.31 V, the MCU's 3.3 V reach it
    out = simulate(project)
    assert not failing(out)
    levels = [c for c in out["checks"] if c["item"].startswith("U2 ") and c["check"].startswith("input level")]
    assert {c["item"] for c in levels} == {"U2 LED_SDI", "U2 LED_CLK", "U2 LED_LE", "U2 LED_OE"}
    assert {c["check"].split()[2] for c in levels} == {"high", "low"}
    high = [c for c in out["checks"] if c["check"].startswith("output high level reaches VIH")]
    assert {c["item"] for c in high} == {"U1 LED_SDI", "U1 LED_CLK", "U1 LED_LE", "U1 LED_OE"} and len(high) == 48


def test_input_between_its_thresholds(project):
    five_volt_driver(project)                                     # VDD 4.4–5.0 V: VIH 3.1–3.5 V against 3.3 V
    bad = failing(simulate(project))
    assert {c["id"] for c in bad} == {"E-3"}
    assert {c["item"] for c in bad} == {"U1 LED_SDI", "U1 LED_CLK", "U1 LED_LE", "U1 LED_OE", "U2 LED_OE"}
    oe = next(c for c in bad if c["item"] == "U2 LED_OE" and c["scenario"] == "usb-max/idle/vf-min")
    assert oe["check"].startswith("input level undefined at OE(ED2)") and oe["actual"] == "3.3 V"
    sdi = next(c for c in bad if c["item"] == "U1 LED_SDI" and c["scenario"] == "usb-max/idle/vf-min")
    assert sdi["check"] == "output high level reaches VIH of U2 SDI" and sdi["actual"] == "3.3 V"
    assert not [c for c in bad if c["scenario"].startswith("usb-min/")]   # +5V at 4.4 V: VIH 3.1 V


def test_ratio_needs_one_supply_pin(project):
    thresholds(project)
    part = project.part("C90107")
    part["pins"]["16"].pop("role")                                # two power_in pins on two nets, neither marked vdd
    part["pins"]["15"]["type"] = "power_in"
    project.save_part("C90107", part)
    bad = failing(simulate(project))
    assert {(c["item"], c["check"]) for c in bad if c["check"].startswith("input thresholds")} == {
        ("U2", "input thresholds as a ratio of the supply")}


BACK = "current into the supply (fed backwards)"
CHARGE = "current into the cell (charging)"


def sim_config(project):
    return json.loads((project.root / "hardware" / "sim.json").read_text())


def module_usb(sim, **supplies):
    """U1 (Pico 2) as a second source at VSYS, as a module whose USB reaches its 5 V pin without a diode."""
    sim["sources"]["U1"] = {"plus": "39", "minus": "3", "r_ohm": 0.3, "i_max_a": 0.5}
    sim["supplies"] = supplies or sim["supplies"]
    return sim


def test_no_source_is_fed_backwards(project):
    out = simulate(project)
    fed = [c for c in out["checks"] if c["item"] == "J1" and c["check"] == BACK]
    assert len(fed) == 12 and all(c["result"] == "pass" and c["actual"] == "0 A" for c in fed)
    sim = module_usb(sim_config(project), both={"J1": 5.25, "U1": 4.75})   # the PC's USB below the supply at J1
    bad = failing(simulate(project, sim))
    assert {(c["id"], c["item"], c["check"], c["expected"]) for c in bad} == {("E-3", "U1", BACK, "≤ 1 mA")}
    assert len(bad) == 4 and all(0.2 < float(c["actual"].split()[0]) < 0.35 for c in bad)   # 0.25–0.29 A into the PC
    sim["sources"]["U1"]["i_back_max_a"] = 0.5                    # the source's own limit
    assert not failing(simulate(project, sim))
    sim = module_usb(sim_config(project), both={"U1": 5.25, "J1": 4.75})   # D1 blocks the way into J1
    out = simulate(project, sim)
    assert not failing(out)
    j1 = [c for c in out["checks"] if c["item"] == "J1" and c["check"] == BACK]
    assert len(j1) == 4 and all(float(c["actual"].split()[0]) < 1e-3 for c in j1)


# A holder for one cell, kind battery_holder, roles plus and minus – the test's own entry
HOLDER = {"lcsc": "C9000001", "mpn": "test holder", "kind": "battery_holder", "verified": {"by": "test"},
          "pins": {"1": {"name": "+", "type": "power_output", "role": "plus"},
                   "2": {"name": "-", "type": "ground", "role": "minus"}},
          "params": {"cells": 1}, "ratings": {}}


def cells_on_the_rail(project):
    """BT1 straight on +5V, next to J1 behind D1: primary cells, nothing between them and the USB supply."""
    project.save_part(HOLDER["lcsc"], HOLDER)
    g = project.graph()
    g["graph"]["components"].append({"designator": "BT1", "type": "battery_holder", "lcsc": HOLDER["lcsc"],
                                     "part": HOLDER["mpn"], "pins": {"1": "+", "2": "-"}})
    project.net(g, "+5V")["pins"].append("BT1.1")
    project.net(g, "GND")["pins"].append("BT1.2")
    project.save_graph(g)
    sim = sim_config(project)
    sim["cells"] = {"fresh": {"v": 4.8, "r": 0.45}}               # three fresh AA cells as one: 3 x 1.6 V, 3 x 0.15 Ω
    sim["supplies"] = {"usb+cells": {"J1": 5.25, "BT1": "fresh"}, "cells": {"BT1": "fresh"}}
    return sim


def test_no_cell_is_charged(project):
    sim = cells_on_the_rail(project)
    out = simulate(project, sim)
    bad = failing(out)
    assert {(c["id"], c["scenario"].split("/")[0], c["item"], c["check"], c["expected"]) for c in bad} == {
        ("E-3", "usb+cells", "BT1", CHARGE, "≤ 1 mA")}
    assert len(bad) == 4 and all(float(c["actual"].split()[0]) > 0.01 for c in bad)
    alone = [c for c in out["checks"] if c["scenario"].startswith("cells/") and c["check"] == CHARGE]
    assert len(alone) == 4 and all(c["result"] == "pass" and c["actual"] == "0 A" for c in alone)
    sim["cells"]["fresh"]["i_charge_max_a"] = 0.5                 # a rechargeable pack, charged on purpose
    assert not failing(simulate(project, sim))
