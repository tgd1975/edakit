"""Pin limits of the schema extension (docs/concepts/new/schema-gaps.md, A6, B1–B3, C1–C4): a pin's own relative limit
against the supply it names (v_rel_max_v, ref), threshold ratios of that supply, the order of two supplies
(supply_order), a limit only while powered (v_max_powered_v), a pin's and a group's current (i_max_a, i_group_max_a),
a pin's own negative limit (v_min_v), the current into a clamp (i_inject_max_a), what an output may drive
(r_load_min_ohm, c_load_max_f). Each with the circuit the limit catches and the one it lets pass."""

import json
import shutil

import pytest
from test_sim import simulate

from helpers import check

from edakit import schema
from edakit.design import Design

needs_ngspice = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


def sim_rows(out, item, what=None, failed=False):
    return [c for c in out["checks"] if c["item"] == item and (what is None or what in c["check"])
            and (not failed or c["result"] == "fail")]


def g_findings(project, code, grade=None):
    cfg = project.config()
    return [f for f in check(Design.from_config(cfg), cfg).findings
            if f.code == code and (grade is None or f.grade == grade)]


# --- schema ------------------------------------------------------------------------------------------------------------
def test_the_schema_knows_the_new_pin_fields():
    entry = {"kind": "ic", "pins": {"1": {"name": "VDD", "type": "power_in"},
                                    "2": {"name": "VIO", "type": "power_in"},
                                    "3": {"name": "A", "type": "input", "ref": "VIO", "v_rel_max_v": 0.3, "v_min_v": -0.3,
                                          "i_max_a": 0.02, "i_inject_max_a": 4e-4, "v_max_powered_v": 5.5},
                                    "4": {"name": "Y", "type": "output", "v_rel_max_v": None, "r_load_min_ohm": 4700,
                                          "c_load_max_f": 1e-8}},
             "supply_order": [["VIO", "VDD"]], "i_group_max_a": {"port": {"pins": ["3", "4"], "max": 0.1}}}
    assert schema.problems(entry) == []
    entry["pins"]["3"]["ref"] = "VCCX"
    entry["supply_order"] = [["VIO", "VXX"]]
    entry["i_group_max_a"] = {"port": {"pins": ["9"], "max": 0.1}}
    assert len(schema.problems(entry)) == 3


# --- A6, B1: a pin's own relative limit against the supply it names ---------------------------------------------------
@needs_ngspice
def test_a_pin_held_against_the_supply_its_ref_names(project):
    """U2's OE (TLC5916) at the MCU's 3.3 V: against its own supply (VDD, 3V3) within 0.3 V; named against GND – a
    reference for the test – it is 3.3 V above it and fails."""
    part = project.part("C90107")
    part["pins"]["13"]["v_rel_max_v"] = 0.3
    project.save_part("C90107", part)
    out = simulate(project)
    assert sim_rows(out, "U2.13", "above its supply") and not sim_rows(out, "U2.13", "above", failed=True)
    part["pins"]["13"]["ref"] = "GND"
    project.save_part("C90107", part)
    bad = sim_rows(simulate(project), "U2.13", "above GND", failed=True)
    assert bad and {r["id"] for r in bad} == {"LIM.v"}
    part["pins"]["13"]["rel_ref"] = "VDD"           # the relative limit's own reference: back to VDD, it passes
    project.save_part("C90107", part)
    out = simulate(project)
    assert sim_rows(out, "U2.13", "above VDD") and not sim_rows(out, "U2.13", "above", failed=True)


@needs_ngspice
def test_a_null_relative_limit_exempts_a_pin_and_outputs_are_held_too(project):
    """The part's vin_rel_max_v holds inputs, bidirectional pins and outputs; a pin rated above its supply says
    v_rel_max_v null. With a limit of −0.1 V (for the test) U2's OE – high at its supply – fails, its SDO output is held
    as well; with v_rel_max_v null on OE it is not checked."""
    sdo_net(project)
    part = project.part("C90107")
    part["limits"]["vin_rel_max_v"] = -0.1
    project.save_part("C90107", part)
    out = simulate(project)
    assert sim_rows(out, "U2.13", "above its supply", failed=True)
    assert sim_rows(out, "U2.14", "output SDO above its supply")
    part["pins"]["13"]["v_rel_max_v"] = None
    project.save_part("C90107", part)
    out = simulate(project)
    assert not sim_rows(out, "U2.13", "above") and sim_rows(out, "U2.14", "output SDO above its supply")


def sdo_net(project):
    """U2's SDO (output; nc in the example) on its own net SDO_OUT with a 10 kΩ R8 and a 100 nF C8 to ground."""
    project.use_library_part("C17414")
    project.use_library_part("C49678")
    g = project.graph()
    project.free_pins(g, "U2.14")
    g["graph"]["components"] += [
        {"designator": "R8", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}},
        {"designator": "C8", "type": "capacitor", "lcsc": "C49678", "value": "100nF", "pins": {"1": "1", "2": "2"}}]
    g["graph"]["nets"].append({"name": "SDO_OUT", "pins": ["U2.14", "R8.1", "C8.1"], "v": [0, 3.4]})
    project.net(g, "GND")["pins"] += ["R8.2", "C8.2"]
    project.save_graph(g)


# --- B1: threshold ratios of the named supply --------------------------------------------------------------------------
@needs_ngspice
def test_threshold_ratios_refer_to_the_pin_ref_names(project):
    """U2's OE with VIH 0.7 × its reference: of VDD (3V3) the MCU's 3.3 V reaches it; of a 5 V pin it would need
    3.5 V – here U2's VDD stays on 3V3 and the reference is made the +5V net through a pin named VREF5 (for the test)."""
    part = project.part("C90107")
    part["pins"]["13"].update(vih_ratio=0.7, vil_ratio=0.3)
    project.save_part("C90107", part)
    out = simulate(project)
    ok = [r for r in out["checks"] if r["id"] == "LVL.threshold" and "OE(ED2)" in r["check"]]
    assert ok and all(r["result"] == "pass" for r in ok)
    part["pins"]["17"] = {"name": "VREF5", "type": "power_in"}
    part["pins"]["13"]["ref"] = "VREF5"
    project.save_part("C90107", part)
    g = project.graph()
    u2 = next(c for c in g["graph"]["components"] if c["designator"] == "U2")
    u2["pins"]["17"] = "VREF5"
    project.net(g, "+5V")["pins"].append("U2.17")
    project.save_graph(g)
    bad = [r for r in simulate(project)["checks"] if r["id"] == "LVL.threshold" and "OE(ED2)" in r["check"]
           and r["result"] == "fail"]
    assert bad and any("VIH 3.5" in r["check"] for r in bad)


# --- B2: one supply never above another --------------------------------------------------------------------------------
def test_a_supply_declared_above_the_one_it_must_stay_below(project):
    """U2 with supply_order [["VDD", "VREF5"]] – VDD (3V3, up to 3.4 V) below a second supply pin: on +5V (5.5 V) it
    holds, on GND (0 V) it does not."""
    from edakit.engines.limits import supply_order
    part = project.part("C90107")
    part["pins"]["17"] = {"name": "VREF5", "type": "power_in"}
    part["supply_order"] = [["VDD", "VREF5"]]
    project.save_part("C90107", part)
    g = project.graph()
    u2 = next(c for c in g["graph"]["components"] if c["designator"] == "U2")
    u2["pins"]["17"] = "VREF5"
    project.net(g, "+5V")["pins"].append("U2.17")
    project.save_graph(g)
    cfg = project.config()
    assert supply_order(Design.from_config(cfg)) == []
    project.net(g, "+5V")["pins"].remove("U2.17")
    project.net(g, "GND")["pins"].append("U2.17")
    project.save_graph(g)
    found = supply_order(Design.from_config(project.config()))
    assert [(f.code, f.grade, f.place) for f in found] == [("LIM.v", "order", "U2")]
    assert "VDD on 3V3 up to 3.4 V, above VREF5 on GND" in found[0].text


# --- B3: a limit only while powered ------------------------------------------------------------------------------------
def test_a_pin_above_its_unpowered_limit_is_a_warning_of_grade_powered(project):
    """U2's SDI declared up to 3.4 V: with v_max_v 3.0 V and v_max_powered_v 5.5 V (values for the test) the declared
    range is within the powered limit – a finding of grade powered, not an error; above 5.5 V an error."""
    part = project.part("C90107")
    part["pins"]["2"].update(v_max_v=3.0, v_max_powered_v=5.5)
    project.save_part("C90107", part)
    found = [f for f in g_findings(project, "LIM.v") if f.place == "U2.2"]
    assert [(f.grade, f.severity) for f in found] == [("powered", "warning")]
    part["pins"]["2"]["v_max_powered_v"] = 3.2
    project.save_part("C90107", part)
    found = [f for f in g_findings(project, "LIM.v") if f.place == "U2.2"]
    assert sorted(f.grade for f in found) == ["", "powered"]


@needs_ngspice
def test_while_powered_the_pin_takes_its_powered_limit(project):
    """U2's OE at 3.3 V while U2 is powered (VDD 3V3 ≥ its vdd_op_min_v): within v_max_powered_v 5.5 V although above
    v_max_v 3.0 V; with v_max_powered_v 3.0 V it fails."""
    part = project.part("C90107")
    part["pins"]["13"].update(v_max_v=3.0, v_max_powered_v=5.5)
    project.save_part("C90107", part)
    out = simulate(project)
    rows = sim_rows(out, "U2.13", "while U2 is powered")
    assert rows and all(r["result"] == "pass" for r in rows)
    part["pins"]["13"]["v_max_powered_v"] = 3.0
    project.save_part("C90107", part)
    assert sim_rows(simulate(project), "U2.13", "while U2 is powered", failed=True)


# --- C1: a pin's and a group's current ---------------------------------------------------------------------------------
@needs_ngspice
def test_a_sink_pin_and_a_group_of_them_held_to_their_currents(project):
    """U2's OUT0 sinks one LED's current (≈ 9.4 mA): within i_max_a 20 mA, above 5 mA (values for the test); the eight
    outputs together against a group maximum."""
    part = project.part("C90107")
    part["pins"]["5"]["i_max_a"] = 0.02
    part["i_group_max_a"] = {"outputs": {"pins": [str(n) for n in range(5, 13)], "max": 0.2}}
    project.save_part("C90107", part)
    out = simulate(project)
    rows = sim_rows(out, "U2.5", "current of pin OUT0")
    assert rows and all(r["result"] == "pass" for r in rows)
    group = sim_rows(out, "U2 outputs")
    assert group and all(r["result"] == "pass" for r in group)
    part["pins"]["5"]["i_max_a"] = 0.005
    part["i_group_max_a"]["outputs"]["max"] = 0.03
    project.save_part("C90107", part)
    out = simulate(project)
    assert sim_rows(out, "U2.5", "current of pin OUT0", failed=True)
    assert sim_rows(out, "U2 outputs", "sunk", failed=True)
    part["i_group_max_a"]["outputs"]["dir"] = "sourced"     # a sum of sourced currents only: the sinks are not in it
    project.save_part("C90107", part)
    out = simulate(project)
    assert not sim_rows(out, "U2 outputs", "sunk") and sim_rows(out, "U2 outputs", "sourced")


@needs_ngspice
def test_an_mcus_port_group_sums_its_output_ammeters(project):
    """The MCU's outputs LED_SDI, LED_CLK, LED_LE, LED_OE (GP2–GP5, pins 4–7 of the Pico 2) as a group: OE low sinks
    the 10 kΩ pull-up's 0.33 mA – within 100 mA, beyond 0.1 mA (values for the test)."""
    part = project.part("C41407547")
    part["i_group_max_a"] = {"spi": {"pins": ["4", "5", "6", "7"], "max": 0.1, "dir": "sunk"}}
    project.save_part("C41407547", part)
    out = simulate(project)
    rows = sim_rows(out, "U1 spi", "sunk")
    assert rows and all(r["result"] == "pass" for r in rows) and not sim_rows(out, "U1 spi", "sourced")
    part["i_group_max_a"]["spi"]["max"] = 1e-4
    project.save_part("C41407547", part)
    assert sim_rows(simulate(project), "U1 spi", "sunk", failed=True)


# --- C2: a pin's own negative limit ------------------------------------------------------------------------------------
def test_a_pin_with_its_own_negative_limit_is_not_held_to_the_floor(project):
    """An input on a net declared down to −7 V: the floor of an active pin (−0.3 V) fails it; with v_min_v −7.5 V – an
    RS-485 line's – it passes, and below that it fails."""
    g = project.graph()
    project.net(g, "LED_SDI")["v"] = [-7, 3.4]
    project.save_graph(g)
    assert [f.place for f in g_findings(project, "LIM.v") if f.place == "U2.2"] == ["U2.2"]
    part = project.part("C90107")
    part["pins"]["2"]["v_min_v"] = -7.5
    project.save_part("C90107", part)
    assert [f for f in g_findings(project, "LIM.v") if f.place == "U2.2"] == []
    part["pins"]["2"]["v_min_v"] = -5
    project.save_part("C90107", part)
    assert [f.place for f in g_findings(project, "LIM.v") if f.place == "U2.2"] == ["U2.2"]


# --- C3: the current into a clamp --------------------------------------------------------------------------------------
@needs_ngspice
def test_an_input_above_its_supply_through_a_resistor_is_held_to_its_injection_current(project):
    """U2's OE(ED2) pulled to +5V through 10 kΩ (the fixture's R2 moved there): 1.6 V above U2's 3.3 V supply. With
    v_rel_max_v 0.3 V alone it fails; with i_inject_max_a 400 µA the clamp takes (5 − 3.3 − 0.3) V / 10 kΩ ≈ 0.14 mA – it
    passes, and with 50 µA it fails."""
    g = project.graph()
    oe = project.net(g, "LED_OE")
    pull = next(r for r in oe["pins"] if r.startswith("R"))
    r_des, r_pin = pull.split(".")
    other = f"{r_des}.{'1' if r_pin == '2' else '2'}"
    for net in g["graph"]["nets"]:
        if other in net["pins"]:
            net["pins"].remove(other)
    project.net(g, "+5V")["pins"].append(other)
    oe["pins"] = [p for p in oe["pins"] if not p.startswith("U1.")]
    oe["v"] = [0, 5.5]
    g["graph"]["nets"] = [n for n in g["graph"]["nets"] if n["pins"]]
    project.save_graph(g)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["mcu"]["U1"]["outputs"] = [o for o in sim["mcu"]["U1"]["outputs"] if o != "LED_OE"]
    for load in sim["loads"].values():
        load.get("gpio", {}).pop("LED_OE", None)
    part = project.part("C90107")
    part["pins"]["13"]["v_rel_max_v"] = 0.3
    project.save_part("C90107", part)
    assert sim_rows(simulate(project, sim), "U2.13", "above its supply", failed=True)
    part["pins"]["13"]["i_inject_max_a"] = 4e-4
    project.save_part("C90107", part)
    out = simulate(project, sim)
    rows = sim_rows(out, "U2.13", "current into the clamp")
    assert rows and all(r["result"] == "pass" for r in rows)
    part["pins"]["13"]["i_inject_max_a"] = 5e-5
    project.save_part("C90107", part)
    assert sim_rows(simulate(project, sim), "U2.13", "current into the clamp", failed=True)


# --- C4: what an output may drive --------------------------------------------------------------------------------------
def test_an_output_drives_no_less_resistance_and_no_more_capacitance_than_it_allows(project):
    """U2's SDO (output, on its own net SDO_OUT) with a 10 kΩ to ground and a 100 nF: within r_load_min_ohm 4.7 kΩ and
    c_load_max_f 1 µF; above 22 kΩ and 10 nF (values for the test) both fail."""
    from edakit.engines import requires
    sdo_net(project)
    part = project.part("C90107")
    part["pins"]["14"].update(r_load_min_ohm=4700, c_load_max_f=1e-6)
    project.save_part("C90107", part)
    cfg = project.config()
    assert requires.output_loads(Design.from_config(cfg)) == []
    part["pins"]["14"].update(r_load_min_ohm=22000, c_load_max_f=1e-8)
    project.save_part("C90107", part)
    found = requires.output_loads(Design.from_config(project.config()))
    assert [(f.code, f.grade) for f in found] == [("REQ.value", "load"), ("REQ.value", "load")]
    assert "drives 10 kΩ" in found[0].text and "drives 100 nF" in found[1].text


# --- rules-at-scale.md, decision 15: the INA226's Alert held to VS + 0.3 V like SCL -----------------------------------
@needs_ngspice
def test_ina226_alert_pulled_above_its_supply_is_held(project):
    """INA226 U9 on 3V3 (SBOS547C 8.2.1.2: Alert 'must' be pulled up to VS): its Alert pulled up through 10 kΩ to +5V
    is above its supply (LIM.v, the entry's vin_rel_max_v 0.3 V); pulled up to 3V3 it passes."""
    from test_configs import place
    place(project, "C49851", "U9", {"6": "3V3", "7": "GND", "3": "ALERT9"})
    project.use_library_part("C17414")
    g = project.graph()
    g["graph"]["components"].append(
        {"designator": "R9", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}})
    project.net(g, "ALERT9")["pins"].append("R9.1")
    project.net(g, "+5V")["pins"].append("R9.2")
    project.net(g, "ALERT9")["v"] = [0, 5.5]
    project.save_graph(g)
    bad = sim_rows(simulate(project), "U9.3", "above", failed=True)
    assert bad and {r["id"] for r in bad} == {"LIM.v"}
    g = project.graph()
    project.net(g, "+5V")["pins"].remove("R9.2")
    project.net(g, "3V3")["pins"].append("R9.2")
    project.net(g, "ALERT9")["v"] = [0, 3.4]
    project.save_graph(g)
    out = simulate(project)
    assert sim_rows(out, "U9.3", "above") and not sim_rows(out, "U9.3", "above", failed=True)
