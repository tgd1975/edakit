"""DC bias of ceramic capacitors and the ESR window of a regulator's output capacitor (maker-coverage FT-9, CK-14).

A capacitor's values.dc_bias – the maker's curve as [[V, ratio], …] – gives the capacitance left at the DC across it:
a pin's capacitor minimum is judged on it (REQ.value/bias where only the bias makes it fail), an ADC's hold capacitor
too, and the transient and AC netlists take it. A pin need's esr_min_ohm/esr_max_ohm is held to the capacitors'
esr_ohm (REQ.value/esr). A capacitor without a curve counts with its nominal value, one without esr_ohm is not judged
– the coverage report names both. The grades are warnings while new."""

import json

from test_configs import place
from test_sim_new import adc_divider

from edakit import circuit, engines, library, schema
from edakit.design import Design
from edakit.engines.coverage import coverage
from edakit.sim import netlist
from edakit.sim import run as simrun

KEMET_4U7 = "C5126849"     # KEMET C0603C475K9PACTU: 4.7 µF, 6.3 V, 0603, X5R – curve and ESR from KEMET's sheet
KEMET_10U = "C2167271"     # KEMET C0805C106K4PACTU: 10 µF, 16 V, 0805, X5R
SAMSUNG_22U = "C45783"     # Samsung CL21A226MAQNNNE: 22 µF X5R – no curve reachable, no esr_ohm

# KEMET T491A106K016AT (LCSC C110055), 10 µF 16 V MnO2 tantalum, case A – a test entry: ESR 3 Ω maximum at 100 kHz
# (KEMET T491 catalogue T2005_T491, 2026-07-08, table 1 p. 9), typical 0.65 Ω read from the graph of KEMET's part
# sheet (generated 2026-10-31, p. 2, K-SIM); its pin numbering is not compared with a library symbol, so it is no
# library entry.
TANTALUM = {"lcsc": "C110055", "mpn": "T491A106K016AT", "manufacturer": "KEMET", "kind": "capacitor",
            "pins": {"1": {"name": "+", "type": "passive", "role": "plus"},
                     "2": {"name": "-", "type": "passive", "role": "minus"}},
            "values": {"value_f": 10e-6, "dielectric": "tantalum", "polarized": True, "tolerance": 0.1,
                       "esr_ohm": [None, 0.65, 3.0]},
            "limits": {"v_max_v": 16, "vr_max_v": 0}}

# TI LM1117 (SNOS412Q, January 2023), 9.2.2.1.3 Output Capacitor: at least 10 µF (tantalum), ESR 0.3 … 22 Ω. The
# AMS1117's entry carries it in these tests – AMS's own data sheet names 22 µF tantalum and no window.
LM1117_OUT = {"what": "capacitor", "c_min_f": 10e-6, "esr_min_ohm": 0.3, "esr_max_ohm": 22,
              "source": "TI LM1117 data sheet SNOS412Q (January 2023), 9.2.2.1.3 Output Capacitor"}


def findings(project, grade):
    cfg = project.config()
    rep = engines.run(Design.from_config(cfg), cfg)
    return [(f.code, f.text, f.severity) for f in rep.findings if f.grade == grade]


def gaps(project):
    d = Design.from_config(project.config())
    return [g.line() for g in coverage(d, engines.profile(d, project.config())) if g.code == "REQ.value"]


def c2_as(project, key):
    """C2 (22 µF from +5V to GND, the net declared 0 … 5.5 V) as library entry `key`."""
    project.use_library_part(key)
    g = project.graph()
    project.comp(g, "C2")["lcsc"] = key
    project.save_graph(g)


def vsys_needs(project, c_min):
    """U1.39 (VSYS, on +5V) needs a capacitor of at least c_min to ground – a value for the test."""
    part = project.part("C41407547")
    part["pins"]["39"]["needs"] = [{"what": "capacitor", "c_min_f": c_min, "source": "test"}]
    project.save_part("C41407547", part)


def ldo(project, cap_key, cap_entry=None):
    """U3, the AMS1117 entry with the LM1117's output window, from +5V to V33 (3.2 … 3.4 V); C10 on V33 to GND."""
    place(project, "C6186", "U3", {"1": "GND", "2": "V33", "3": "+5V", "4": "V33"}, extra_nets={"V33": [3.2, 3.4]})
    part = project.part("C6186")
    part["pins"]["2"]["needs"] = [LM1117_OUT]
    project.save_part("C6186", part)
    if cap_entry:
        project.save_part(cap_key, cap_entry)
    else:
        project.use_library_part(cap_key)
    g = project.graph()
    g["graph"]["components"].append({"designator": "C10", "type": "capacitor", "lcsc": cap_key,
                                     "pins": {"1": "1", "2": "2"}})
    project.net(g, "V33")["pins"].append("C10.1")
    project.net(g, "GND")["pins"].append("C10.2")
    project.save_graph(g)


def test_the_curve_gives_the_capacitance_left():
    part = library.entry(KEMET_4U7)
    assert circuit.capacitance(part, 0) == 4.7e-6
    assert abs(circuit.capacitance(part, 5) - 4.7e-6 * 0.43) < 1e-15
    assert abs(circuit.capacitance(part, 4.5) - 4.7e-6 * (0.54 + 0.43) / 2) < 1e-15    # linear between two points
    assert circuit.capacitance(part, 9) == circuit.capacitance(part, 6.2)             # beyond: the last point
    assert circuit.capacitance(part, -5) == circuit.capacitance(part, 5)              # either polarity
    assert circuit.capacitance(library.entry(SAMSUNG_22U), 5) == 22e-6                 # no curve: nominal


def test_a_4u7_6v3_0603_falls_below_its_minimum_at_5v(project):
    c2_as(project, KEMET_4U7)
    vsys_needs(project, 2.2e-6)                  # 4.7 µF passes nominal; at 5.5 V 40 % of it is left
    assert findings(project, "bias") == [
        ("REQ.value", "U1.39 (VSYS): needs a capacitor of at least 2.2 µF to GND – C2 on +5V: 4.7 µF, after DC bias "
                      "1.864 µF (C2 at 5.5 V)", "warning")]
    assert findings(project, "pin") == []        # the nominal value meets it: no REQ.value/pin


def test_a_10u_16v_0805_keeps_enough(project):
    c2_as(project, KEMET_10U)
    vsys_needs(project, 2.2e-6)                  # 10 µF at 5.5 V: 51 % left, 5.1 µF
    assert findings(project, "bias") == findings(project, "pin") == []


def test_below_the_minimum_already_nominal_stays_grade_pin(project):
    c2_as(project, KEMET_4U7)
    vsys_needs(project, 10e-6)
    assert [(c, s) for c, _, s in findings(project, "pin")] == [("REQ.value", "warning")]
    assert findings(project, "bias") == []


def test_without_a_curve_the_nominal_value_counts_and_coverage_says_so(project):
    vsys_needs(project, 2.2e-6)                  # C2 is the example's C45783: X5R without dc_bias
    assert findings(project, "bias") == findings(project, "pin") == []
    assert gaps(project) == ["REQ.value: C2 – no dc_bias – X5R, counted with its nominal capacitance where a minimum "
                             "is judged (C45783)"]


def test_the_netlist_takes_the_capacitance_at_the_declared_voltage(project):
    def c2_line():
        sim = json.loads((project.root / "hardware" / "sim.json").read_text())
        text, _ = netlist.build(Design.from_config(project.config()), sim, next(simrun.scenarios(sim)))
        return next(x for x in text.splitlines() if x.startswith("C_C2 "))
    assert c2_line() == "C_C2 n__5v 0 2.2e-05"                       # no curve: as before
    c2_as(project, KEMET_4U7)
    assert c2_line() == f"C_C2 n__5v 0 {circuit.capacitance(library.entry(KEMET_4U7), 5.5):.6g}"


def test_an_adc_hold_capacitor_counts_after_dc_bias(project):
    g = adc_divider(project, c_hold=4e-6)        # VSENSE 0 … 3.4 V; 4.7 µF there keeps 65 %, 3.05 µF
    project.use_library_part(KEMET_4U7)
    g["graph"]["components"].append({"designator": "C8", "type": "capacitor", "lcsc": KEMET_4U7,
                                     "pins": {"1": "1", "2": "2"}})
    project.net(g, "VSENSE")["pins"].append("C8.1")
    project.net(g, "GND")["pins"].append("C8.2")
    project.save_graph(g)
    assert [t for _, t, _ in findings(project, "adc")] == [
        "U1.31 (VSENSE): source resistance 5 kΩ – the ADC allows 1 kΩ, or a hold capacitor of 4 µF at the pin "
        "(C8: 3.046 µF after DC bias)"]


def test_a_regulator_that_needs_esr_fails_with_only_a_ceramic(project):
    ldo(project, KEMET_10U)                      # 0.011 Ω at 100 kHz
    assert findings(project, "esr") == [
        ("REQ.value", "U3.2 (VOUT): needs a capacitor of at least 10 µF with an ESR of 0.3 Ω … 22 Ω to GND – C10 "
                      "0.011 Ω on V33: none in the window", "warning")]


def test_a_tantalum_in_the_window_passes(project):
    ldo(project, "C110055", TANTALUM)
    assert findings(project, "esr") == findings(project, "bias") == findings(project, "pin") == []


def test_a_capacitor_without_esr_is_not_judged(project):
    ldo(project, SAMSUNG_22U)
    assert findings(project, "esr") == []
    assert "REQ.value: C10 – no esr_ohm – the ESR window of U3.2 is not judged (C45783)" in gaps(project)


def test_the_entry_fields_are_held_to_their_form():
    entry = library.entry(KEMET_4U7)
    assert schema.problems(entry) == []
    bad = {**entry, "values": {**entry["values"], "dc_bias": [[0, 1.0], [5, 0.4], [3, 0.6]], "esr_ohm": "low"}}
    texts = schema.problems(bad)
    assert any(t.startswith("values.dc_bias: [[V, ratio], …]") for t in texts)
    assert "values.esr_ohm: 'low' is no number in Ω" in texts
    from edakit.engines.requires import pin_needs_problems
    assert pin_needs_problems({"what": "capacitor", "esr_min_ohm": "0.3"}) == [
        "needs capacitor: esr_min_ohm must be a number"]
