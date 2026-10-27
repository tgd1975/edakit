"""Stage E seen red at the supplies: a part outside its operating range, an input between its thresholds."""

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
