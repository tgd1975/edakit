"""New relations of the simulation from maker-coverage, warnings while new: a MOSFET switch half on (CK-4), an input
above its own part's supply (CK-5), an ADC pin outside the converter's window and its source resistance (CK-6)."""

import json
import shutil

import pytest
from test_sim import simulate

from edakit import engines
from edakit.design import Design

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


def sim_config(project):
    return json.loads((project.root / "hardware" / "sim.json").read_text())


def rows(out, item, check, failed=False):
    return [c for c in out["checks"] if c["item"] == item and c["check"] == check and (not failed or c["result"] == "fail")]


# --- CK-4 --------------------------------------------------------------------------------------------------------------
def high_side_switch(project):
    """Q8 (AO3401A, C15127 of the block library: vgs_th_v −1.3 … −0.5 V, RDS(on) from −2.5 V on) switches +5V to a
    10 kΩ load R8; its gate on GP8 (U1.11), which the MCU drives – 3.3 V high leaves |VGS| at 1.7 V."""
    project.use_library_part("C15127")
    project.use_library_part("C17414")
    g = project.graph()
    project.free_pins(g, "U1.11")
    g["graph"]["components"] += [
        {"designator": "Q8", "type": "transistor", "lcsc": "C15127", "pins": {"1": "G", "2": "S", "3": "D"}},
        {"designator": "R8", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}}]
    project.net(g, "+5V")["pins"].append("Q8.2")
    project.net(g, "GND")["pins"].append("R8.2")
    g["graph"]["nets"] += [{"name": "SW_GATE", "pins": ["Q8.1", "U1.11"], "v": [0, 3.4]},
                           {"name": "SW_OUT", "pins": ["Q8.3", "R8.1"], "v": [0, 5.5]}]
    project.save_graph(g)
    sim = sim_config(project)
    sim["mcu"]["U1"]["outputs"].append("SW_GATE")
    sim["loads"]["idle"]["gpio"]["SW_GATE"] = 1          # "off": the gate at 3.3 V, 1.7 V below the source
    sim["loads"]["all_on"]["gpio"]["SW_GATE"] = 0        # on: |VGS| 5 V
    return sim


def test_a_p_mosfet_a_3v3_output_cannot_switch_off(project):
    out = simulate(project, high_side_switch(project))
    half = rows(out, "Q8", "gate drive off or specified on", failed=True)
    assert half and {r["id"] for r in half} == {"LIM.range"} and all("half on" in r["actual"] for r in half)
    assert {r["scenario"].split("/")[1] for r in half} == {"idle"}
    found = [f for f in out["findings"] if f["code"] == "LIM.range" and f["place"] == "Q8"]
    assert {f["grade"] for f in found} == {"gate"}


# --- CK-5 --------------------------------------------------------------------------------------------------------------
def test_an_input_above_its_supply(project):
    """U2 (TLC5916) on 3V3, its inputs from the MCU at up to 3.3 V: inside vin_rel_max_v 0.3 V; a limit of −0.1 V – as
    if the part allowed no input at its supply, a value for the test – makes the high inputs fail."""
    part = project.part("C90107")
    part["limits"]["vin_rel_max_v"] = 0.3
    project.save_part("C90107", part)
    out = simulate(project)
    assert rows(out, "U2.13", "input OE(ED2) above its supply") and not rows(out, "U2.13", "input OE(ED2) above its "
                                                                                          "supply", failed=True)
    part["limits"]["vin_rel_max_v"] = -0.1
    project.save_part("C90107", part)
    bad = rows(simulate(project), "U2.13", "input OE(ED2) above its supply", failed=True)
    assert bad and {r["id"] for r in bad} == {"LIM.v"}


# --- CK-6 --------------------------------------------------------------------------------------------------------------
def adc_divider(project, window=(0, 3.3), r_max=1000, c_hold=None):
    """A divider R8/R9 (10 kΩ each) from 3V3 to GND into GP26 (U1.31, adc0) with fn adc; its pin's adc entry – values
    for the test, not from the RP2350's datasheet."""
    project.use_library_part("C17414")
    part = project.part("C41407547")
    part["pins"]["31"]["adc"] = {"range_v": list(window), "r_source_max_ohm": r_max,
                                 **({"c_hold_min_f": c_hold} if c_hold else {})}
    project.save_part("C41407547", part)
    g = project.graph()
    project.free_pins(g, "U1.31")
    g["graph"]["components"] += [
        {"designator": d, "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}}
        for d in ("R8", "R9")]
    project.net(g, "3V3")["pins"].append("R8.1")
    project.net(g, "GND")["pins"].append("R9.2")
    g["graph"]["nets"].append({"name": "VSENSE", "pins": ["R8.2", "R9.1", "U1.31"], "v": [0, 3.4], "fn": "adc"})
    project.save_graph(g)
    return g


def test_the_divider_is_too_high_impedance_for_the_adc(project):
    adc_divider(project)
    cfg = project.config()
    found = [f.text for f in engines.run(Design.from_config(cfg), cfg).findings
             if f.code == "REQ.value" and f.grade == "adc"]
    assert found == ["U1.GP26_ADC0 (31) on VSENSE: source resistance 5 kΩ – the ADC allows 1 kΩ"]


def test_a_hold_capacitor_makes_it_fit(project):
    g = adc_divider(project, c_hold=1e-7)
    g["graph"]["components"].append({"designator": "C8", "type": "capacitor", "lcsc": "C49678", "value": "100nF",
                                     "pins": {"1": "1", "2": "2"}})
    project.net(g, "VSENSE")["pins"].append("C8.1")
    project.net(g, "GND")["pins"].append("C8.2")
    project.save_graph(g)
    cfg = project.config()
    assert not [f for f in engines.run(Design.from_config(cfg), cfg).findings if f.grade == "adc"]


def test_the_adc_window(project):
    adc_divider(project, window=(0.15, 1.5))            # VSENSE at half of 3V3: 1.65 V, above 1.5 V
    bad = rows(simulate(project), "U1.31", "VSENSE inside the ADC's window", failed=True)
    assert bad and {r["id"] for r in bad} == {"LIM.range"} and bad[0]["expected"] == "0.15 … 1.5 V"


# --- FT-11: what a load expects ------------------------------------------------------------------------------------------
def test_a_load_expects_a_current_budget_and_a_level(project):
    """idle expects J1 to deliver at most 20 mA (a sleep budget, a value for the test) and 3V3 at 3.2 V or more."""
    sim = sim_config(project)
    sim["loads"]["idle"]["expect"] = {"J1": {"i_max_a": 0.02}, "3V3": {"min_v": 3.2}}
    out = simulate(project, sim)
    budget = rows(out, "J1", "current from the supply (expected in this load)")
    level = rows(out, "3V3", "net voltage (expected in this load)")
    assert budget and {r["result"] for r in budget} == {"fail"} and {r["id"] for r in budget} == {"LIM.i"}
    assert level and {r["result"] for r in level} == {"pass"}
    sim["loads"]["idle"]["expect"] = {"NOPE": {"min_v": 1}}
    bad = rows(simulate(project, sim), "NOPE", "expect of the load")
    assert bad and bad[0]["id"] == "SIM.config"


def test_new_net_functions():
    from edakit.circuit import FN_NAMES, fn_match
    assert {"i2s.bclk", "i2s.ws", "i2s.sd", "can.tx", "can.rx", "onewire", "usb.dp", "usb.dn"} <= set(FN_NAMES)
    assert fn_match("i2s.bclk", "i2s0.bclk") == ("0", "bclk") and fn_match("usb.dp", "usb0.dp") == ("0", "dp")
