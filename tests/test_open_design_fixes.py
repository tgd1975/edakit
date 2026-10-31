"""What the published open designs (tests/open_designs/, FT-21) showed edakit getting wrong, each fixed and held here:
a TVS judged by its working voltage without the rectifier's margin, the two VOUT pins of a regulator counted as two
drivers, an input's built-in pull-up ignored, a transistor base driven through its resistor by an output that is
defined at reset taken as floating. (The fifth – nets no simulated element touches judged as nan – is held by
tests/test_open_designs.py on the DevKitC's header nets.) The Corne's left half added four: a crystal with four
pads – its two ground pads on the lid – stopped edakit check, a crystal behind the damping resistor at the
oscillator's output (the RP2040's XOUT) was taken as missing, a bare microcontroller (kind ic, behaviour mcu) could
not state the core current and on-chip regulator the model reads, and a pin on a net no simulated element reaches was
judged as nan against its relative limit. (Its fifth – no-connect crosses drawn in the order of a set – is held by
tests/test_catalog_page.py.) Parts here are test entries, not datasheets."""

import json
import shutil

import pytest

from edakit import engines, schema
from edakit.design import Design
from edakit.engines.requires import pin_needs

TVS = {"lcsc": "C9000501", "mpn": "test TVS 5 V", "kind": "diode", "verified": {"by": "test"},
       "pins": {"1": {"name": "K", "type": "passive", "role": "cathode"},
                "2": {"name": "A", "type": "passive", "role": "anode"}},
       "values": {"tvs": True}, "limits": {"vr_max_v": 5.0}}

CHIP = {"lcsc": "C9000502", "mpn": "test regulator and logic", "kind": "ic", "verified": {"by": "test"},
        "pins": {"1": {"name": "GND", "type": "ground"}, "2": {"name": "VOUT", "type": "power_output"},
                 "3": {"name": "VIN", "type": "power_in"}, "4": {"name": "VOUT", "type": "power_output"},
                 "5": {"name": "RXD", "type": "input"}, "6": {"name": "DRV", "type": "output"},
                 "7": {"name": "OUT2", "type": "power_output"}},
        "needs": {"decoupling": False}}


def findings(project, code):
    cfg = project.config()
    return [f.text for f in engines.run(Design.from_config(cfg), cfg).findings if f.code == code]


def add(project, des, key, part, nets, type_="ic"):
    project.save_part(key, part)
    g = project.graph()
    pins = {n: i["name"] for n, i in part["pins"].items()}
    g["graph"]["components"].append({"designator": des, "type": type_, "lcsc": key, "pins": pins,
                                     "nc": [n for n in pins if n not in nets]})
    for num, name in nets.items():
        existing = [n for n in g["graph"]["nets"] if n["name"] == name]
        if existing:
            existing[0]["pins"].append(f"{des}.{num}")
        else:
            g["graph"]["nets"].append({"name": name, "pins": [f"{des}.{num}"], "v": [0, 5.5]})
    project.save_graph(g)
    return g


def set_v(project, net, v):
    g = project.graph()
    project.net(g, net)["v"] = list(v)
    project.save_graph(g)


def test_a_tvs_is_held_to_its_working_voltage_without_the_margin(project):
    add(project, "D20", "C9000501", TVS, {"1": "+5V", "2": "GND"}, "diode")
    set_v(project, "+5V", [0, 4.9])                    # below VRWM: fine (a rectifier needs 4.9 × 1.5 ≤ VRRM)
    assert not [t for t in findings(project, "LIM.v") if t.startswith("D20")]
    set_v(project, "+5V", [0, 5.25])                   # above VRWM: still found
    assert [t for t in findings(project, "LIM.v") if t.startswith("D20")] == [
        "D20: reverse up to 5.2 V, working voltage VRWM 5 V"]
    rectifier = json.loads(json.dumps(TVS))
    del rectifier["values"]["tvs"]
    project.save_part("C9000501", rectifier)
    set_v(project, "+5V", [0, 4.9])                    # the same diode as a rectifier: 4.9 V × 1.5 > 5 V
    assert [t for t in findings(project, "LIM.v") if t.startswith("D20")] == ["D20: reverse up to 4.9 V, VRRM 5 V"]


def test_two_pins_of_one_name_are_one_driver(project):
    add(project, "U20", "C9000502", CHIP, {"1": "GND", "3": "+5V", "2": "R3V3", "4": "R3V3", "5": "RX20"})
    assert not [t for t in findings(project, "LVL.contention") if t.startswith("R3V3")]
    g = project.graph()
    project.net(g, "R3V3")["pins"].append("U20.7")     # OUT2: another output terminal on the same net
    project.comp(g, "U20")["nc"].remove("7")
    project.save_graph(g)
    assert [t for t in findings(project, "LVL.contention") if t.startswith("R3V3")] == [
        "R3V3: several outputs drive this net: U20.2, U20.4, U20.7"]


def test_an_input_with_its_own_pull_up_is_defined(project):
    part = json.loads(json.dumps(CHIP))
    add(project, "U20", "C9000502", part, {"1": "GND", "3": "+5V", "2": "R3V3", "4": "R3V3", "5": "RX20"})
    g = project.graph()
    project.net(g, "RX20")["pins"].append("U1.10")     # an MCU pin (floating at reset) drives RXD
    project.comp(g, "U1")["nc"].remove("10")
    project.save_graph(g)
    assert [t for t in findings(project, "LVL.undefined") if t.startswith("RX20")] == [
        "RX20: only MCU pins drive this input – floating until the firmware runs"]
    part["pins"]["5"]["pull"] = "up"                   # the input's built-in pull-up holds it
    project.save_part("C9000502", part)
    assert not [t for t in findings(project, "LVL.undefined") if t.startswith("RX20")]


def test_a_base_driven_through_its_resistor_by_a_defined_output(project):
    add(project, "U20", "C9000502", CHIP, {"1": "GND", "3": "+5V", "2": "R3V3", "4": "R3V3", "6": "DRV20"})
    g = project.graph()
    g["graph"]["components"] += [
        {"designator": "Q20", "type": "transistor", "lcsc": "C2146", "pins": {"1": "B", "2": "E", "3": "C"}},
        {"designator": "R20", "type": "resistor", "lcsc": "C17414", "pins": {"1": "1", "2": "2"}}]
    project.use_library_part("C2146") if hasattr(project, "use_library_part") else None
    g["graph"]["nets"] += [{"name": "Q20_B", "pins": ["R20.2", "Q20.1"], "v": [0, 5.5]},
                           {"name": "Q20_C", "pins": ["Q20.3", "U1.11"], "v": [0, 5.5]}]
    project.net(g, "DRV20")["pins"].append("R20.1")
    project.net(g, "GND")["pins"].append("Q20.2")
    project.comp(g, "U1")["nc"].remove("11")
    project.save_graph(g)
    assert not [t for t in findings(project, "LVL.undefined") if t.startswith("Q20")]   # DRV is push-pull at reset
    g = project.graph()
    project.net(g, "DRV20")["pins"].remove("R20.1")
    project.net(g, "DRV20")["pins"].append("U1.12")    # an MCU pin instead: floating until the firmware runs
    project.comp(g, "U1")["nc"].remove("12")
    project.comp(g, "U20")["nc"].append("6")
    project.net(g, "DRV20")["pins"].remove("U20.6")
    g["graph"]["nets"].append({"name": "GPIO20", "pins": ["U1.12", "R20.1"], "v": [0, 3.4]})
    project.net(g, "DRV20")["pins"].remove("U1.12")
    g["graph"]["nets"] = [n for n in g["graph"]["nets"] if n["pins"]]
    project.save_graph(g)
    assert [t for t in findings(project, "LVL.undefined") if t.startswith("Q20")] == [
        "Q20: no base-emitter resistor – state undefined while the firmware is not running"]


# --- the Corne (corne-cherry-left): crystals and a bare microcontroller ---------------------------------------------
OSC = {"lcsc": "C9000503", "mpn": "test oscillator IC", "kind": "ic", "verified": {"by": "test"},
       "pins": {"1": {"name": "VDD", "type": "power_in"}, "2": {"name": "GND", "type": "ground"},
                "3": {"name": "XIN", "type": "passive",
                      "needs": [{"what": "crystal", "to": "XOUT", "f_min_hz": 12e6, "f_max_hz": 12e6}]},
                "4": {"name": "XOUT", "type": "passive"}},
       "needs": {"decoupling": False}}


def crystal(pads=2, hz=12e6):
    """A test crystal of two pads, or of four: #1 and #3 the crystal, #2 and #4 ground on the lid (Epson FA-238V)."""
    pins = ({"1": {"name": "1", "type": "passive", "role": "1"}, "2": {"name": "2", "type": "passive", "role": "2"}}
            if pads == 2 else
            {"1": {"name": "1", "type": "passive", "role": "1"}, "2": {"name": "2", "type": "ground"},
             "3": {"name": "3", "type": "passive", "role": "2"}, "4": {"name": "4", "type": "ground"}})
    return {"lcsc": "C9000504", "mpn": f"test crystal {pads} pads", "kind": "crystal", "pins": pins,
            "values": {"f_hz": hz}}


def oscillator(xtal, damping=None, pull_up=False):
    """U1 with XIN and XOUT; Y1 between XIN and XOUT – or, with damping (Ω), between XIN and X2 with R1 from XOUT to
    X2 (the Corne's R3 at the RP2040's XOUT), or with pull_up R1 from the supply to X2; Y1's ground pads on GND."""
    parts = {"C9000503": OSC, "C9000504": xtal}
    comps = [{"designator": "U1", "type": "ic", "lcsc": "C9000503", "board": "main",
              "pins": {n: p["name"] for n, p in OSC["pins"].items()}},
             {"designator": "Y1", "type": "crystal", "lcsc": "C9000504", "board": "main",
              "pins": {n: p["name"] for n, p in xtal["pins"].items()}}]
    four = len(xtal["pins"]) == 4
    nets = {"3V3": ["U1.1"], "GND": ["U1.2"], "XIN": ["U1.3", "Y1.1"], "XOUT": ["U1.4"], "X2": []}
    nets["X2" if damping else "XOUT"].append("Y1.3" if four else "Y1.2")
    if four:
        nets["GND"] += ["Y1.2", "Y1.4"]
    if damping:
        parts["C9000505"] = {"lcsc": "C9000505", "mpn": "test resistor", "kind": "resistor",
                             "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}},
                             "values": {"value_ohm": damping}}
        comps.append({"designator": "R1", "type": "resistor", "lcsc": "C9000505", "board": "main",
                      "pins": {"1": "1", "2": "2"}})
        nets["3V3" if pull_up else "XOUT"].append("R1.1")
        nets["X2"].append("R1.2")
    graph = {"name": "t", "version": "1", "ground": "GND", "components": comps,
             "nets": [{"name": n, "pins": p, "v": [0, 3.4]} for n, p in nets.items() if p]}
    return Design.from_data(graph, parts)


def crystal_needs(d):
    return [(f.code, f.text) for f in pin_needs(d)]


def test_a_crystal_with_two_ground_pads_is_found_between_its_crystal_pins():
    assert crystal_needs(oscillator(crystal(2))) == []
    assert crystal_needs(oscillator(crystal(4))) == []          # before: edakit check stopped (four pins unpacked)
    assert crystal_needs(oscillator(crystal(4, 8e6))) == [
        ("REQ.value", "U1.3 (XIN): needs a crystal of 12 MHz … 12 MHz to U1.4 (XOUT) – Y1: 8 MHz")]


def test_a_crystal_behind_the_damping_resistor_at_xout_counts():
    assert crystal_needs(oscillator(crystal(4), damping=1000)) == []   # before: REQ.missing, none between XIN and XOUT
    assert crystal_needs(oscillator(crystal(4, 8e6), damping=1000)) == [
        ("REQ.value", "U1.3 (XIN): needs a crystal of 12 MHz … 12 MHz to U1.4 (XOUT) – Y1: 8 MHz")]


def test_a_crystal_behind_a_resistor_from_a_rail_does_not_count():
    assert [code for code, _ in crystal_needs(oscillator(crystal(2), damping=1000, pull_up=True))] == ["REQ.missing"]


def test_a_bare_microcontroller_states_its_core_current_and_regulator():
    mcu = {"lcsc": "C9000506", "mpn": "test MCU", "kind": "ic", "verified": {"by": "test"},
           "pins": {"1": {"name": "IOVDD", "type": "power_in", "role": "vdd"}, "2": {"name": "GND", "type": "ground"},
                    "3": {"name": "VREG_IN", "type": "power_in", "role": "vin"},
                    "4": {"name": "VREG_VOUT", "type": "power_output", "role": "vout"}},
           "values": {"behavior": "mcu", "v_io_v": 3.3, "i_core_a": 0.054, "i_core_min_a": 0.01, "gpio_r_out_ohm": 40,
                      "regulator": "ldo", "vout_v": 1.1},
           "limits": {"gpio_i_max_a": 0.012, "gpio_i_total_max_a": 0.05}}
    assert schema.problems(mcu) == []                       # before: not values or limits of kind ic


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_a_relative_pin_limit_on_a_net_nothing_simulated_reaches_is_not_judged(project):
    """U2's pin 14 (TLC5916, nc in the example; an input for the test) on a net with only a spare MCU pin – as a
    flash's QSPI lines or a header's SWD – that no element of the netlist reaches: its voltage is nan, no reading
    against vin_rel_max_v (LIM.v/inject). U2's OE, on a net the simulation drives, is still held."""
    from test_sim import simulate
    part = project.part("C90107")
    part["limits"]["vin_rel_max_v"] = 0.3
    part["pins"]["14"]["type"] = "input"                  # the model drives an output low: an input floats
    project.save_part("C90107", part)
    g = project.graph()
    project.free_pins(g, "U2.14", "U1.10")
    g["graph"]["nets"].append({"name": "SPARE", "pins": ["U2.14", "U1.10"], "v": [0, 3.4]})
    project.save_graph(g)
    out = simulate(project)
    assert [c for c in out["checks"] if c["item"] == "U2.14" and "above" in c["check"]] == []  # before: nan V, failed
    assert [c for c in out["checks"] if c["item"] == "U2.13" and "above its supply" in c["check"]]
