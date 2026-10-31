"""What the published open designs (tests/open_designs/, FT-21) showed edakit getting wrong, each fixed and held here:
a TVS judged by its working voltage without the rectifier's margin, the two VOUT pins of a regulator counted as two
drivers, an input's built-in pull-up ignored, a transistor base driven through its resistor by an output that is
defined at reset taken as floating. (The fifth – nets no simulated element touches judged as nan – is held by
tests/test_open_designs.py on the DevKitC's header nets.) Parts here are test entries, not datasheets."""

import json

from edakit import engines
from edakit.design import Design

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
