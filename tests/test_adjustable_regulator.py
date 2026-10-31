"""Adjustable regulators (maker-coverage FT-5): the output set by the divider and vref_v – in the check (REQ.missing and
REQ.value with the grade feedback) and in the simulation (the regulator's output source) –, and a regulator's minimum
load (LIM.range/min_load). The numbers are the AMS1117's: VREF 1.25 V, VOUT = VREF (1 + R2/R1), minimum load 10 mA
(datasheet, Application Hints and Electrical Characteristics, read from LCSC's copy for C6186)."""

import shutil

import pytest
from helpers import check
from reference import Project, add, resistor, wire
from test_sim import simulate

from edakit.circuit import feedback_vout
from edakit.design import Design

ADJ = {"lcsc": "C9100080", "mpn": "AMS1117-ADJ numbers (test part)", "kind": "ic", "verified": {"by": "test"},
       "values": {"behavior": "ldo", "vref_v": 1.25, "i_load_min_a": 0.010, "dropout_v": 1.3},
       "pins": {"1": {"name": "ADJ", "type": "passive", "role": "adj"},
                "2": {"name": "VOUT", "type": "power_output", "role": "vout"},
                "3": {"name": "VIN", "type": "power_in", "role": "vin"}}}


def regulator(p, r1, r2, top=3.4):
    """U80 from +5V onto ADJ_OUT (declared up to `top` V), R80 = R1 (OUT–ADJ), R81 = R2 (ADJ–GND), 22 µF on the
    output; no ground pin – the adjustable LM317 family has none."""
    p.save_part(ADJ["lcsc"], ADJ)
    resistor(p, "C9100081", r1)
    resistor(p, "C9100082", r2)
    g = p.graph()
    add(g, "U80", "ic", ADJ["lcsc"], {"1": "ADJ", "2": "VOUT", "3": "VIN"})
    add(g, "R80", "resistor", "C9100081", {"1": "1", "2": "2"})
    add(g, "R81", "resistor", "C9100082", {"1": "1", "2": "2"})
    wire(g, "+5V", "U80.3")
    wire(g, "ADJ_OUT", "U80.2", "R80.1", v=(0, top))
    wire(g, "ADJ_FB", "U80.1", "R80.2", "R81.1", v=(0, top))
    wire(g, "GND", "R81.2")
    p.save_graph(g)


def feedback(p):
    cfg = p.config()
    rep = check(Design.from_config(cfg), cfg)
    return sorted((f.code, f.severity) for f in rep.findings if f.grade == "feedback")


def test_the_divider_sets_the_output(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    regulator(p, 120, 200)
    cfg = p.config()
    vout, r1, r2 = feedback_vout(Design.from_config(cfg), "U80")
    assert (r1, r2) == (120, 200) and abs(vout - 1.25 * (1 + 200 / 120)) < 1e-9      # 3.33 V
    assert feedback(p) == []


def test_a_divider_for_more_than_the_net_carries(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    regulator(p, 120, 390)                       # 1.25 × (1 + 390/120) = 5.31 V on a net of up to 3.4 V
    assert feedback(p) == [("REQ.value", "warning")]


def test_a_regulator_without_its_divider(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    regulator(p, 120, 200)
    g = p.graph()
    g["graph"]["components"] = [c for c in g["graph"]["components"] if c["designator"] != "R81"]
    for n in g["graph"]["nets"]:
        n["pins"] = [r for r in n["pins"] if not r.startswith("R81.")]
    p.save_graph(g)
    assert feedback(p) == [("REQ.missing", "warning")]


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_the_simulation_regulates_to_the_divider_and_holds_the_minimum_load(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    regulator(p, 120, 200)                       # the divider draws 3.33 V / 320 Ω ≈ 10.4 mA itself
    out = simulate(p)
    nominal = [c for c in out["checks"] if c["item"] == "U80" and c["scenario"].startswith("usb-nom")]
    volts = [c for c in nominal if c["check"].startswith("output voltage")]
    assert volts and all(c["result"] == "pass" and c["expected"].startswith("3.3333") for c in volts)
    assert {c["result"] for c in nominal if "minimum load" in c["check"]} == {"pass"}
    # at the USB minimum the 1.3 V dropout leaves less than 3.33 V – the regulator is out of regulation, as it is
    p = Project.copy_of_example(tmp_path / "b")
    regulator(p, 1200, 2000)                     # the same 3.33 V, but only 1 mA through the divider
    out = simulate(p)
    low = [f for f in out["findings"] if f["place"] == "U80" and f["code"] == "LIM.range"]
    assert low and {f["grade"] for f in low} == {"min_load"}
