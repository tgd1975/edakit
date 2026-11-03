"""What the published open designs (tests/open_designs/, FT-21) showed edakit getting wrong, each fixed and held here:
a TVS judged by its working voltage without the rectifier's margin, the two VOUT pins of a regulator counted as two
drivers, an input's built-in pull-up ignored, a transistor base driven through its resistor by an output that is
defined at reset taken as floating. (The fifth – nets no simulated element touches judged as nan – is held by
tests/test_open_designs.py on the DevKitC's header nets.) The Corne's left half added four: a crystal with four
pads – its two ground pads on the lid – stopped edakit check, a crystal behind the damping resistor at the
oscillator's output (the RP2040's XOUT) was taken as missing, a bare microcontroller (kind ic, behaviour mcu) could
not state the core current and on-chip regulator the model reads, and a pin on a net no simulated element reaches was
judged as nan against its relative limit. (Its fifth – no-connect crosses drawn in the order of a set – is held by
tests/test_catalog_page.py.) The Corne v3's key matrix added two: a pressed key whose row is not scanned was judged
starved of its minimum load, and a row could not be released while another is scanned. The GuitarML pedals added
five: a switch of three poles could not be described (roles, simulation, REQ.value/switch), a base biased by
resistors to ground or a divider node was taken as floating, a coupling capacitor's voltage was taken from extreme to
extreme of its nets' ranges, a second wire of one net between two boards stopped the simulation, and contacts on nets
that run through cables were never judged by REQ.value/switch. The Adafruit Micro-Lipo added two: a charger's status
LEDs behind their resistors were taken for a floating net, and a PROG resistor behind a solder jumper – a second charge
current – was counted neither by LIM.i/charge nor by the charger model. The Fuzz Face added one: a base held by a
resistor to a supply that comes in at a connector, which no pin types, was taken as floating. The WLED controller
(ADLSC) added one: the gate of the reverse-polarity N-MOSFET in the ground return, tied straight to the net the supply
comes in on, was taken as floating – the same rails now serve both. The ESPurna-H added one: a need on a regulator's
VOUT pin left open was taken as not connected, though its tab – the same terminal – carries the output. Parts here are
test entries, not datasheets."""

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
        ("REQ.value", "U1.XIN (3): needs a crystal of 12 MHz … 12 MHz to U1.XOUT (4) – Y1: 8 MHz")]


def test_a_crystal_behind_the_damping_resistor_at_xout_counts():
    assert crystal_needs(oscillator(crystal(4), damping=1000)) == []   # before: REQ.missing, none between XIN and XOUT
    assert crystal_needs(oscillator(crystal(4, 8e6), damping=1000)) == [
        ("REQ.value", "U1.XIN (3): needs a crystal of 12 MHz … 12 MHz to U1.XOUT (4) – Y1: 8 MHz")]


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


# --- the Corne v3 (corne-cherry-v3-left): a key matrix ----------------------------------------------------------------
KEY = {"lcsc": "C9000507", "mpn": "test key socket", "kind": "button", "verified": {"by": "test"},
       "pins": {"1": {"name": "1", "type": "passive", "role": "a"}, "2": {"name": "2", "type": "passive", "role": "b"}},
       "values": {"r_on_ohm": 0.1, "min_load_a": 1e-5}}


def matrix_key(project):
    """A key of a key matrix on the example's Pico: SW20 from COL (GP8, read with the pull-up) to K20, its diode D20
    (1N4148W) from K20 to ROW (GP7, the firmware's scan output) – cathode to the row, as the Corne's."""
    project.save_part("C9000507", KEY)
    project.use_library_part("C81598")
    g = project.graph()
    project.free_pins(g, "U1.10", "U1.11")
    g["graph"]["components"] += [
        {"designator": "SW20", "type": "button", "lcsc": "C9000507", "pins": {"1": "1", "2": "2"}},
        {"designator": "D20", "type": "diode", "lcsc": "C81598", "pins": {"1": "K", "2": "A"}}]
    g["graph"]["nets"] += [{"name": "ROW", "pins": ["U1.10", "D20.1"], "v": [0, 3.4], "matrix": "row"},
                           {"name": "COL", "pins": ["U1.11", "SW20.1"], "v": [0, 3.4], "matrix": "col"},
                           {"name": "K20", "pins": ["SW20.2", "D20.2"], "v": [0, 3.4]}]
    project.save_graph(g)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["mcu"]["U1"]["outputs"].append("ROW")
    sim["mcu"]["U1"]["pullups"].append("COL")
    sim["loads"] = {"scanned": {"gpio": {"LED_OE": 1, "ROW": 0}, "leds_on": [], "buttons": ["SW20"]},
                    "not_scanned": {"gpio": {"LED_OE": 1, "ROW": 1}, "leds_on": [], "buttons": ["SW20"]}}
    return sim


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_a_matrix_key_whose_row_is_not_scanned_carries_no_minimum_load(project):
    """A pressed key of a key matrix carries current only while its row is scanned; in the other rows its diode
    blocks it – the point of the diode, not a contact starved of its wetting current (REQ.value/min_load). Scanned,
    its current is held to the socket's minimum load as before."""
    from test_sim import simulate
    sim = matrix_key(project)
    rows = [c for c in simulate(project, sim)["checks"] if c["item"] == "SW20" and "closed contact" in c["check"]]
    assert rows and all("/scanned/" in c["scenario"] for c in rows)        # before: 0 µA failed where not scanned
    assert all(c["result"] == "pass" for c in rows)
    sim["mcu"]["U1"]["pullup_ohm"] = 1e6                                     # 2.7 µA through the key: too little
    rows = [c for c in simulate(project, sim)["checks"] if c["item"] == "SW20" and "closed contact" in c["check"]]
    assert rows and all(c["result"] == "warn" for c in rows)                 # REQ.value/min_load, a warning


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_an_output_a_load_releases_is_held_by_its_pull_up(project):
    """QMK scans a matrix by driving one row low and releasing the others – inputs with the pull-up, not outputs high
    (a ghost runs through a released row, not through a driven one). A load's gpio level null releases an output of
    the mcu config: undriven, its pull-up holds the net. Before, null drove it low."""
    from test_sim import simulate
    sim = matrix_key(project)
    sim["mcu"]["U1"]["pullups"].append("ROW")
    sim["loads"] = {"released": {"gpio": {"LED_OE": 1, "ROW": None}, "leds_on": [], "buttons": []},
                    "low": {"gpio": {"LED_OE": 1, "ROW": 0}, "leds_on": [], "buttons": []}}
    out = simulate(project, sim)
    level = {c["scenario"].split("/")[1]: float(c["actual"].split()[0]) for c in out["checks"]
             if c["item"] == "ROW" and c["id"] == "LIM.declared"}
    assert level["released"] > 3.0 and level["low"] < 0.1                 # before: released read 0 V, driven low


# --- the guitar pedals (guitarml-ts-rat-combo, guitarml-classic-boost): a switch of three poles -----------------------
THREE_POLE = {"lcsc": "C9000508", "mpn": "test 3PDT footswitch", "kind": "switch", "verified": {"by": "test"},
              "pins": {"1": {"name": "1", "type": "passive", "role": "throw_a"},
                       "2": {"name": "2", "type": "passive", "role": "common"},
                       "3": {"name": "3", "type": "passive", "role": "throw_b"},
                       "4": {"name": "4", "type": "passive", "role": "throw_a_2"},
                       "5": {"name": "5", "type": "passive", "role": "common_2"},
                       "6": {"name": "6", "type": "passive", "role": "throw_b_2"},
                       "7": {"name": "7", "type": "passive", "role": "throw_a_3"},
                       "8": {"name": "8", "type": "passive", "role": "common_3"},
                       "9": {"name": "9", "type": "passive", "role": "throw_b_3"}},
              "limits": {"i_contact_max_a": 1.0}}


def three_pole(project, commons, throws_a, pulls):
    """SW20, a 3PDT footswitch (FS5700 lugs: commons 2, 5, 8, throws 1/3, 4/6, 7/9): each pole's common on its net of
    `commons`, its throw a on its net of `throws_a`, the throws b open; every net of `pulls` 10 kΩ to its level
    (3V3 or GND). Nets that are no existing net are new, marked signal."""
    project.save_part("C9000508", THREE_POLE)
    project.use_library_part("C17414")
    g = project.graph()
    g["graph"]["components"].append({"designator": "SW20", "type": "switch", "lcsc": "C9000508",
                                     "pins": {n: n for n in THREE_POLE["pins"]}, "nc": ["3", "6", "9"]})
    known = {n["name"] for n in g["graph"]["nets"]}
    for pins, nets in (("258", commons), ("147", throws_a)):
        for pin, net in zip(pins, nets):
            if net in known:
                project.net(g, net)["pins"].append(f"SW20.{pin}")
            else:
                g["graph"]["nets"].append({"name": net, "pins": [f"SW20.{pin}"], "v": [0, 3.4], "signal": True})
                known.add(net)
    for i, (net, level) in enumerate(pulls.items()):
        g["graph"]["components"].append({"designator": f"R{30 + i}", "type": "resistor", "lcsc": "C17414",
                                         "value": "10k", "pins": {"1": "1", "2": "2"}})
        project.net(g, net)["pins"].append(f"R{30 + i}.1")
        project.net(g, level)["pins"].append(f"R{30 + i}.2")
    project.save_graph(g)


def test_a_switch_of_three_poles_has_its_roles():
    """A 3PDT – the footswitch of nearly every pedal – names each pole's common and throws with the pole's number,
    as a DPDT relay's second set (common_2, no_2, nc_2). Before, the roles of poles 2 and 3 were unknown – and the
    firmware export, which reads a switch through the side it closes against, found none for them."""
    from edakit.firmware import far_side
    assert schema.problems(THREE_POLE) == []
    assert far_side(None, "SW20", "common_2") == ["throw_a_2", "throw_b_2"]       # before: []
    assert far_side(None, "SW20", "throw_b_3") == ["common_3"]
    assert far_side(None, "SW20", "common") == ["throw_a", "throw_b"]


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_every_pole_of_a_switch_follows_the_throw(project):
    """The load's throw moves the actuator, and with it every pole: in throw_a each common joins its throw a. Before,
    only the first pole was switched – the second and third were open whatever the load said."""
    from test_sim import simulate
    three_pole(project, ["3V3", "3V3", "3V3"], ["A1", "A2", "A3"], {"A1": "GND", "A2": "GND", "A3": "GND"})
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["report"] = ["A1", "A2", "A3"]
    sim["loads"] = {"on": {"gpio": {"LED_OE": 1}, "leds_on": [], "throw": {"SW20": "throw_a"}},
                    "off": {"gpio": {"LED_OE": 1}, "leds_on": [], "throw": {"SW20": "throw_b"}}}
    out = simulate(project, sim)
    level = {(s["name"].split("/")[1], n): v for s in out["scenarios"] if "nets" in s for n, v in s["nets"].items()}
    assert all(level[("on", n)] > 3.0 for n in ("A1", "A2", "A3"))          # before: A2 and A3 at 0 V
    assert all(level[("off", n)] < 0.1 for n in ("A1", "A2", "A3"))


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_the_poles_of_a_switch_in_signal_paths_are_judged_apart(project):
    """REQ.value/switch holds the sides of one contact to one DC level – the pop when it moves. Two poles of a 3PDT
    sit in different signal paths, one at the supply, one at ground: each pole at one level passes. Before, all nine
    lugs counted as one contact and the step between the poles was taken for a pop."""
    from test_sim import simulate
    three_pole(project, ["SIG_C1", "SIG_C2", "GND"], ["SIG_A1", "SIG_A2", "GND"],
               {"SIG_C1": "3V3", "SIG_A1": "3V3", "SIG_C2": "GND", "SIG_A2": "GND"})
    rows = [c for c in simulate(project)["checks"] if c["item"] == "SW20" and c["check"].startswith("DC across")]
    assert rows and {c["result"] for c in rows} == {"pass"}                 # before: 3.3 V across "SW20", failed
    g = project.graph()                                     # pole 2's open throw b on a signal net at 3.3 V: a pop
    project.comp(g, "SW20")["nc"].remove("6")
    g["graph"]["components"].append({"designator": "R40", "type": "resistor", "lcsc": "C17414", "value": "10k",
                                     "pins": {"1": "1", "2": "2"}})
    g["graph"]["nets"].append({"name": "SIG_B2", "pins": ["SW20.6", "R40.1"], "v": [0, 3.4], "signal": True})
    project.net(g, "3V3")["pins"].append("R40.2")
    project.save_graph(g)
    rows = [c for c in simulate(project)["checks"] if c["item"] == "SW20" and c["check"].startswith("DC across")]
    assert {c["result"] for c in rows} == {"pass", "warn"}                 # REQ.value/switch, a warning
    failed = [c["check"] for c in rows if c["result"] == "warn"]
    assert failed[0].startswith("DC across SW20 in the signal path (SIG_A2")


# --- the guitar pedals: a transistor biased by resistors, a coupling capacitor, several wires of one net --------------
NPN = {"lcsc": "C9000509", "mpn": "test NPN", "kind": "npn", "verified": {"by": "test"},
       "pins": {"1": {"name": "E", "type": "passive", "role": "emitter"},
                "2": {"name": "B", "type": "passive", "role": "base"},
                "3": {"name": "C", "type": "passive", "role": "collector"}},
       "limits": {"vce_max_v": 30}, "values": {"hfe_min": 300, "hfe_max": 900},
       "spice": {"model": ".model QTEST NPN(IS=8f BF=600)"}}


def boost_stage(bias_to, typed=True):
    """A common-emitter stage as the Classic Boost's: Q1's base on BASE, R1 from BASE to `bias_to` – VCC (with R2 to
    GND: the boost's divider), VREF (alone: the TS's followers on a divider node), or a net nothing holds –, nothing
    with bias_to None; the emitter through R4 to GND, the collector through R3 to VCC. With `typed` U1, a supply IC,
    types VCC and GND by its pins; without it – the boost has no IC – no pin says what VCC and GND are."""
    res = {"lcsc": "C9000510", "mpn": "test resistor", "kind": "resistor",
           "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}},
           "values": {"value_ohm": 10000}}
    reg = {"lcsc": "C9000511", "mpn": "test supply", "kind": "ic", "needs": {"decoupling": False},
           "pins": {"1": {"name": "OUT", "type": "power_output"}, "2": {"name": "GND", "type": "ground"}}}
    comps = [{"designator": "Q1", "type": "transistor", "lcsc": "C9000509", "pins": {"1": "E", "2": "B", "3": "C"}}]
    nets = {"VCC": [], "GND": [], "BASE": ["Q1.2"], "EMIT": ["Q1.1"], "COL": ["Q1.3"]}
    if typed:
        comps.append({"designator": "U1", "type": "ic", "lcsc": "C9000511", "pins": {"1": "OUT", "2": "GND"}})
        nets["VCC"].append("U1.1")
        nets["GND"].append("U1.2")

    def r(des, a, b):
        comps.append({"designator": des, "type": "resistor", "lcsc": "C9000510", "pins": {"1": "1", "2": "2"}})
        nets.setdefault(a, []).append(f"{des}.1")
        nets.setdefault(b, []).append(f"{des}.2")
    r("R3", "COL", "VCC")
    r("R4", "EMIT", "GND")
    if bias_to == "VREF":                            # a divider node: R5/R6 from VCC to GND, as the TS's VREF
        r("R5", "VCC", "VREF")
        r("R6", "VREF", "GND")
    if bias_to == "FLOAT":                           # a net only a capacitor reaches: nothing holds it
        comps.append({"designator": "C1", "type": "capacitor", "lcsc": "C9000512", "pins": {"1": "1", "2": "2"}})
        nets["FLOAT"] = ["C1.1"]
        nets["GND"].append("C1.2")
    if bias_to:
        r("R1", "BASE", bias_to)
    if bias_to == "VCC":
        r("R2", "BASE", "GND")
    cap = {"lcsc": "C9000512", "mpn": "test capacitor", "kind": "capacitor",
           "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}},
           "values": {"value_f": 1e-7}}
    graph = {"name": "t", "version": "1", "ground": "GND", "components": comps,
             "nets": [{"name": n, "pins": p, "v": [0, 9]} for n, p in nets.items()]}
    return Design.from_data(graph, {"C9000509": NPN, "C9000510": res, "C9000511": reg, "C9000512": cap})


def base_findings(d):
    from edakit.engines.levels import control_pins
    return [f.text for f in control_pins(d)]


def test_a_base_biased_by_resistors_to_the_rails_is_defined():
    """The Classic Boost's 2N5088: 430 kΩ from VCC and 43 kΩ to ground hold its base, the emitter sits on 390 Ω. No
    firmware, no resistor from base to emitter – and nothing undefined. Before: LVL.undefined, ground was no rail."""
    assert base_findings(boost_stage("VCC", typed=False)) == []    # before: found – no pin typed GND or VCC
    assert base_findings(boost_stage("VREF")) == []        # the TS's followers: 510 kΩ to a divider node; before: found
    assert base_findings(boost_stage("FLOAT")) == [         # a resistor to a net nothing holds defines nothing
        "Q1: no base-emitter resistor – state undefined while the firmware is not running"]
    assert base_findings(boost_stage(None)) == [
        "Q1: no base-emitter resistor – state undefined while the firmware is not running"]


def coupling(minus_net, minus_v, plus_v=(0, 8.5), signal=True):
    """C1 (16 V, polarized) from SIG_A (plus, `plus_v`) to `minus_net` (`minus_v`) – both nets signal if `signal`,
    only SIG_A with signal "one"."""
    cap = {"lcsc": "C9000513", "mpn": "test electrolytic", "kind": "capacitor",
           "pins": {"1": {"name": "+", "type": "passive", "role": "plus"},
                    "2": {"name": "-", "type": "passive", "role": "minus"}},
           "values": {"value_f": 4.7e-6, "polarized": True}, "limits": {"v_max_v": 16, "vr_max_v": 0}}
    res = {"lcsc": "C9000510", "mpn": "test resistor", "kind": "resistor",
           "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}},
           "values": {"value_ohm": 10000}}
    comps = [{"designator": "C1", "type": "capacitor", "lcsc": "C9000513", "pins": {"1": "+", "2": "-"}},
             {"designator": "R1", "type": "resistor", "lcsc": "C9000510", "pins": {"1": "1", "2": "2"}},
             {"designator": "R2", "type": "resistor", "lcsc": "C9000510", "pins": {"1": "1", "2": "2"}}]
    nets = [{"name": "SIG_A", "pins": ["C1.1", "R1.1"], "v": list(plus_v)},
            {"name": minus_net, "pins": ["C1.2", "R2.1"], "v": list(minus_v)},
            {"name": "GND", "pins": ["R1.2", "R2.2"], "v": [0, 0]}]
    if signal:
        for n in nets[:1 if signal == "one" else 2]:
            n["signal"] = True
    return Design.from_data({"name": "t", "version": "1", "ground": "GND", "components": comps, "nets": nets},
                            {"C9000513": cap, "C9000510": res})


def cap_volts(d):
    from edakit.engines import quantities
    return {q.name: round(q.hi, 3) for q in quantities.part_voltages(d) if q.place == "C1"}


def test_a_coupling_capacitor_carries_the_signal_on_both_sides():
    """The Rat's C10 (4.7 µF, 16 V): its plus at the LM301A's output, biased at half the supply (declared 0 … 8.5 V),
    its minus behind it at ground (±4.5 V of signal). The signal moves both sides together – the DC across it is the
    difference of the two levels, 4.5 V at the extremes, not 8.5 V − (−4.5 V) = 13 V. Before: LIM.v, 13 V × 1.5 above
    16 V. A side that is no signal net – a filter capacitor to ground, a supply – is taken from extreme to extreme."""
    assert cap_volts(coupling("SIG_B", (-4.5, 4.5)))["v"] == 4.5                        # before: 13.0
    assert cap_volts(coupling("SIG_B", (-4.5, 4.5), signal=False))["v"] == 13.0        # not a signal path
    assert cap_volts(coupling("SIG_B", (-4.5, 4.5), signal="one"))["v"] == 13.0        # one side does not follow
    assert cap_volts(coupling("SIG_B", (0, 0)))["v"] == 8.5                             # to a fixed level: as before


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_several_wires_of_one_net_between_two_boards():
    """A pedal's ground reaches the hand-wired parts on several wires – the DC jack's, each jack's sleeve, the LED
    pole of each footswitch – each a cable from a pad of the board. The reference circuit 'cables' (a remote button on
    W20, its ground on pin 2) gets a second wire of GND, W21 from J22 to J23. Before: the simulation stopped – the
    first cable had moved the board's GND pins onto a node of their own, the second found its two ends on different
    nets. Now each wire is a resistor between the same two nodes, in parallel."""
    import tempfile

    from reference import add, wire, write_one
    from test_sim import simulate
    with tempfile.TemporaryDirectory() as t:
        p = write_one(f"{t}/cables", "cables")
        out = simulate(p)
        assert not [c for c in out["checks"] if c["id"] == "SIM.converge" and c["result"] == "fail"]
        g = p.graph()
        add(g, "J22", "connector", "C131337", {"1": "1", "2": "2"}, bom=False, board="main", nc=["2"])
        add(g, "J23", "connector", "C131337", {"1": "1", "2": "2"}, bom=False, board="remote", nc=["2"])
        wire(g, "GND", "J22.1", "J23.1")
        g["graph"]["cables"].append({"name": "W21", "from": "J22", "to": "J23", "pins": {"1": "1"},
                                     "length_m": 1, "awg": 26})
        p.save_graph(g)
        out = simulate(p)
        assert not [c for c in out["checks"] if c["id"] == "SIM.converge" and c["result"] == "fail"]   # before: failed
        assert all(s.get("status") != "error" for s in out["scenarios"])


# --- the WLED controller (ADLSC): a low-side reverse-polarity MOSFET --------------------------------------------------
NMOS = {"lcsc": "C9000514", "mpn": "test N-MOSFET", "kind": "nmos", "verified": {"by": "test"},
        "pins": {"1": {"name": "G", "type": "passive", "role": "gate"},
                 "2": {"name": "D", "type": "passive", "role": "drain"},
                 "3": {"name": "S", "type": "passive", "role": "source"}},
        "limits": {"vds_max_v": 60, "vgs_max_v": 20}}
TERMINAL = {"lcsc": "C9000515", "mpn": "test terminal", "kind": "connector", "verified": {"by": "test"},
            "pins": {"1": {"name": "1", "type": "passive", "role": "pin1"},
                     "2": {"name": "2", "type": "passive", "role": "pin2"}}}


def low_side(gate_net, reversible=True):
    """ADLSC's input: the terminal J1 brings 5 V on VIN (pin 2) and its return on VRTN (pin 1); Q1 sits in the ground
    return – drain on VRTN, source on GND – with its gate on `gate_net`; C1 from VIN to GND – no resistor, no supply pin
    holds VIN. With `gate_net` "CTRL", R2 joins the gate to a net only an MCU pin drives (U1's GPIO, an input until the
    firmware runs)."""
    res = {"lcsc": "C9000510", "mpn": "test resistor", "kind": "resistor",
           "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}},
           "values": {"value_ohm": 10000}}
    mcu = {"lcsc": "C9000511", "mpn": "test MCU", "kind": "ic", "needs": {"decoupling": False},
           "pins": {"1": {"name": "GP0", "type": "bidirectional"}, "2": {"name": "GND", "type": "ground"}}}
    j1 = {"designator": "J1", "type": "connector", "lcsc": "C9000515", "pins": {"1": "1", "2": "2"}}
    if reversible:
        j1["source"] = "reversible"
    cap = {"lcsc": "C9000512", "mpn": "test capacitor", "kind": "capacitor",
           "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}},
           "values": {"value_f": 1e-7}}
    comps = [j1, {"designator": "Q1", "type": "transistor", "lcsc": "C9000514", "pins": {"1": "G", "2": "D", "3": "S"}},
             {"designator": "C1", "type": "capacitor", "lcsc": "C9000512", "pins": {"1": "1", "2": "2"}}]
    nets = {"VIN": ["J1.2", "C1.1"], "VRTN": ["J1.1", "Q1.2"], "GND": ["Q1.3", "C1.2"]}
    nets.setdefault(gate_net, []).append("Q1.1")
    if gate_net == "CTRL":
        comps += [{"designator": "U1", "type": "ic", "lcsc": "C9000511", "pins": {"1": "GP0", "2": "GND"}},
                  {"designator": "R2", "type": "resistor", "lcsc": "C9000510", "pins": {"1": "1", "2": "2"}}]
        nets["CTRL"].append("R2.1")
        nets["GPIO"] = ["R2.2", "U1.1"]
        nets["GND"].append("U1.2")
    graph = {"name": "t", "version": "1", "ground": "GND", "components": comps,
             "nets": [{"name": n, "pins": p, "v": [-0.2, 5.25]} for n, p in nets.items()]}
    return Design.from_data(graph, {"C9000514": NMOS, "C9000515": TERMINAL, "C9000510": res, "C9000511": mcu,
                                    "C9000512": cap})


def test_a_gate_on_the_net_the_supply_comes_in_on_is_defined():
    """ADLSC's Q1 (AOD442): the reverse-polarity N-MOSFET in the ground return has its gate straight on +5V_IN – the
    terminal's plus, on which no part has a supply pin. Before: LVL.undefined, '+5V_IN' was no rail. A net the board's
    supply comes in on – a reversible source's pins, a simulation source's plus (paths.inputs) – defines the gate. A
    gate only an MCU pin drives through its resistor stays undefined."""
    from edakit.engines.levels import control_pins
    undefined = "Q1: no resistor from the gate to its source or a rail – the MOSFET is undefined while the firmware is " \
                "not running"
    assert [f.text for f in control_pins(low_side("VIN"))] == []           # before: found
    sim = {"sources": {"J1": {"plus": "2", "minus": "1"}}}
    assert [f.text for f in control_pins(low_side("VIN", reversible=False), sim)] == []
    assert [f.text for f in control_pins(low_side("VIN", reversible=False))] == [undefined]   # nothing says VIN is one
    assert [f.text for f in control_pins(low_side("CTRL"), sim)] == [undefined]


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_a_contact_on_a_net_that_crosses_a_cable_is_still_in_the_signal_path():
    """The combo's order switch and footswitches sit on nets that run through cables to the pads (IN, TS_SEND …): the
    simulation gives each net a node per board ('IN__main'), and REQ.value/switch looked those names up among the
    signal nets – not found, the contacts were never judged. The reference 'cables': SW20 (the remote button, open)
    between REMOTE (through W20, 10 kΩ to 3V3) and SIG_R (10 kΩ to GND), both marked signal – 3.3 V across it."""
    import tempfile

    from reference import add, wire, write_one
    from test_sim import simulate
    with tempfile.TemporaryDirectory() as t:
        p = write_one(f"{t}/cables", "cables")
        g = p.graph()
        project_net = next(n for n in g["graph"]["nets"] if n["name"] == "GND")
        project_net["pins"].remove("SW20.3")
        add(g, "R22", "resistor", "C17414", {"1": "1", "2": "2"}, value="10k", board="remote", bom=False)
        wire(g, "SIG_R", "SW20.3", "R22.1", v=(0, 3.4), signal=True)
        wire(g, "GND", "R22.2")
        next(n for n in g["graph"]["nets"] if n["name"] == "REMOTE")["signal"] = True
        p.save_graph(g)
        rows = [c for c in simulate(p)["checks"] if c["item"] == "SW20" and c["check"].startswith("DC across")]
        assert rows and {c["result"] for c in rows} == {"warn"}             # before: no rows – never judged
        assert "REMOTE 3.3 V" in rows[0]["check"] and "SIG_R 0 V" in rows[0]["check"]


# --- the Adafruit Micro-Lipo (adafruit-microlipo-usb-c): status LEDs, a PROG resistor behind a solder jumper -------
def status_leds(project):
    """U100, the library's MCP73831 (C424093), charges BT100 through R100 (10 kΩ on PROG); its STAT – a tri-state
    output – lights D101 from +5V through R101 while it charges (low) and D102 to GND through R102 once the charge is
    complete (high): the Micro-Lipo's two LEDs."""
    from reference import add, wire
    from test_charger import HOLDER
    for key in ("C424093", "C17414", "C2297"):
        project.use_library_part(key)
    project.save_part(HOLDER["lcsc"], HOLDER)
    g = project.graph()
    add(g, "U100", "ic", "C424093", {"1": "STAT", "2": "VSS", "3": "VBAT", "4": "VDD", "5": "PROG"})
    for des in ("R100", "R101", "R102"):
        add(g, des, "resistor", "C17414", {"1": "1", "2": "2"})
    add(g, "D101", "led", "C2297", {"1": "A", "2": "K"})
    add(g, "D102", "led", "C2297", {"1": "A", "2": "K"})
    add(g, "BT100", "battery_holder", HOLDER["lcsc"], {"1": "+", "2": "-"}, bom=False)
    wire(g, "+5V", "U100.4", "D101.1")
    wire(g, "GND", "U100.2", "R100.2", "BT100.2", "D102.2")
    wire(g, "CHG_PROG", "U100.5", "R100.1", v=(0, 1.1))
    wire(g, "VBAT", "U100.3", "BT100.1", v=(0, 4.2))
    wire(g, "STAT", "U100.1", "R101.2", "R102.1")
    wire(g, "LED_R", "R101.1", "D101.2")
    wire(g, "LED_G", "R102.2", "D102.1")
    project.save_graph(g)


def test_leds_behind_their_resistors_are_the_status_outputs_load(project):
    """The MCP73831's STAT lets go in shutdown and without a cell; on it sit only the two LEDs, each behind its
    series resistor – the output's load, nothing reads the net. Before: LVL.undefined/open_drain, 'released, it
    floats' (an LED cathode straight on the output counted as its load, one behind a resistor did not). An MCU pin
    that reads STAT keeps the finding: released, it floats under that pin."""
    status_leds(project)
    assert not [t for t in findings(project, "LVL.undefined") if t.startswith("STAT")]     # before: found
    g = project.graph()
    project.free_pins(g, "U1.10")                       # the MCU's GP7 reads STAT as well
    project.net(g, "STAT")["pins"].append("U1.10")
    project.save_graph(g)
    assert [t for t in findings(project, "LVL.undefined") if t.startswith("STAT")] == [
        "STAT: driven only by outputs that let go (U100.1) and nothing holds it – released, it floats"]


JUMPER = {"lcsc": "C9000514", "mpn": "test solder jumper", "kind": "switch", "verified": {"by": "test"},
          "pins": {"1": {"name": "1", "type": "passive", "role": "throw_a"},
                   "2": {"name": "2", "type": "passive", "role": "common"}}}
SELECTOR = {"lcsc": "C9000515", "mpn": "test slide switch SPDT", "kind": "switch", "verified": {"by": "test"},
            "pins": {"1": {"name": "1", "type": "passive", "role": "throw_a"},
                     "2": {"name": "2", "type": "passive", "role": "common"},
                     "3": {"name": "3", "type": "passive", "role": "throw_b"}}}


def behind_a_switch(tmp_path, r_behind, selector=False):
    """test_charger's U100 (1000 V / R_PROG, 500 mA at most) with R100 10 kΩ from PROG to GND – and SW100 on PROG:
    a solder jumper to R101 (`r_behind`) to GND, the Micro-Lipo's 500 mA mode; with `selector` a slide switch whose
    common is PROG, R100 on its throw a and R101 on its throw b instead (the Micro-Lipo v2's 100/500 mA switch).
    -> LIM.i/charge as [(place, severity)]."""
    from reference import Project, add, resistor, wire
    from test_charger import charge, charger
    p = Project.copy_of_example(tmp_path)
    charger(p, 10000)
    resistor(p, "C9100103", r_behind)
    part = SELECTOR if selector else JUMPER
    p.save_part(part["lcsc"], part)
    g = p.graph()
    add(g, "SW100", "switch", part["lcsc"], {n: i["name"] for n, i in part["pins"].items()}, bom=False)
    add(g, "R101", "resistor", "C9100103", {"1": "1", "2": "2"})
    wire(g, "GND", "R101.2")
    wire(g, "CHG_PROG", "SW100.2")
    if selector:
        p.net(g, "CHG_PROG")["pins"].remove("R100.1")
        wire(g, "PROG_A", "SW100.1", "R100.1", v=(0, 1.1))
        wire(g, "PROG_B", "SW100.3", "R101.1", v=(0, 1.1))
    else:
        wire(g, "PROG_B", "SW100.1", "R101.1", v=(0, 1.1))
    p.save_graph(g)
    return [(pl, s) for pl, s, _ in charge(p)]


def test_a_prog_resistor_behind_a_solder_jumper_counts_closed(tmp_path):
    """The Micro-Lipo programs 100 mA with R3 (10 kΩ) and puts R4 (2.2 kΩ) in parallel through the solder jumper SJ1:
    1.80 kΩ, 555 mA – above the MCP73831's 500 mA. LIM.i/charge holds the most a switch on PROG can program. Before:
    only resistors straight from PROG to ground counted – 100 mA, nothing found. 22 kΩ behind the jumper programs
    145 mA and stays quiet; a slide switch that selects 10 kΩ or 2 kΩ programs 500 mA at most, never both at once."""
    assert behind_a_switch(tmp_path / "a", 2200) == [("U100", "warning")]               # before: []
    assert behind_a_switch(tmp_path / "b", 22000) == []
    assert behind_a_switch(tmp_path / "c", 2000, selector=True) == []                   # not 10k ∥ 2k: 600 mA


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_the_charger_model_reads_the_prog_resistor_its_jumper_closes(tmp_path):
    """The simulation's charger reads R_PROG through the contacts a load closes: the Micro-Lipo's SJ1 open (as
    delivered) charges with 100 mA, SJ1 closed with R3 ∥ R4 – 555 mA. Before: 100 mA in both loads."""
    from edakit.sim import run as simrun
    from test_open_designs import copy
    cfg = copy("adafruit-microlipo-usb-c", tmp_path)
    out = simrun.run_all(Design.from_config(cfg), engines.load_sim(cfg))
    amps = {}
    for r in out["checks"]:
        if r["item"] == "U1" and r["check"].startswith("charge current") and r["scenario"].endswith("/vf-min"):
            amps.setdefault(r["scenario"].split("/")[1], []).append(float(r["actual"].split()[0]))
    assert amps["100mA"] == pytest.approx([1000 / 10e3] * 3, rel=0.01)
    assert amps["500mA"] == pytest.approx([1000 / (10e3 * 2.2e3 / 12.2e3)] * 3, rel=0.01)   # before: 0.1 A


# --- the Fuzz Face (whbeers-fuzz-face): a supply brought in at a connector ---------------------------------------------
TRIMMER = {"lcsc": "C9000514", "mpn": "test trimmer", "kind": "potentiometer",
           "pins": {"1": {"name": "1", "type": "passive", "role": "end_a"},
                    "2": {"name": "2", "type": "passive", "role": "wiper"},
                    "3": {"name": "3", "type": "passive", "role": "end_b"}},
           "values": {"value_ohm": 100000}}
HEADER = {"lcsc": "C9000515", "mpn": "test header", "kind": "connector",
          "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}}}


def fed_stage(bias_to="9V0"):
    """The Fuzz Face's Q2 in brief: its base held only by a trimmer as a variable resistor (TRIM1: end_a at
    `bias_to`, wiper and end_b at the base), its emitter through 1 kΩ to GND, its collector through 1 kΩ to 9V0 – the
    supply the effect board gets at its connector J1 from the IO board. No IC: no pin types 9V0 as a supply. FLOAT: a
    net only the trimmer reaches."""
    res = {"lcsc": "C9000510", "mpn": "test resistor", "kind": "resistor",
           "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}},
           "values": {"value_ohm": 1000}}
    comps = [{"designator": "J1", "type": "connector", "lcsc": "C9000515", "pins": {"1": "1", "2": "2"}},
             {"designator": "Q2", "type": "transistor", "lcsc": "C9000509", "pins": {"1": "E", "2": "B", "3": "C"}},
             {"designator": "TRIM1", "type": "potentiometer", "lcsc": "C9000514",
              "pins": {"1": "1", "2": "2", "3": "3"}},
             {"designator": "R3", "type": "resistor", "lcsc": "C9000510", "pins": {"1": "1", "2": "2"}},
             {"designator": "R4", "type": "resistor", "lcsc": "C9000510", "pins": {"1": "1", "2": "2"}}]
    nets = {"9V0": ["J1.1", "R3.2"], "GND": ["J1.2", "R4.2"], "BASE": ["Q2.2", "TRIM1.2", "TRIM1.3"],
            "EMIT": ["Q2.1", "R4.1"], "COL": ["Q2.3", "R3.1"]}
    nets.setdefault(bias_to, []).append("TRIM1.1")
    graph = {"name": "t", "version": "1", "ground": "GND", "components": comps,
             "nets": [{"name": n, "pins": p, "v": [0, 9]} for n, p in nets.items()]}
    return Design.from_data(graph, {"C9000509": NPN, "C9000510": res, "C9000514": TRIMMER, "C9000515": HEADER})


def undefined(d, sim):
    return [f.text for f in engines.run(d, None, sim).findings if f.code == "LVL.undefined"]


def test_a_base_held_by_a_resistor_to_a_supply_brought_in_at_a_connector_is_defined():
    """The Fuzz Face's Q2: its base is Q1's collector, held by TRIM1 from 9V0 – the supply the IO board brings in at
    the effect board's connector, which sim.json's sources name (J1, plus pin 1). No IC types 9V0. Before: LVL.undefined
    – a resistor to a net no pin typed was no rail. The net a source of the simulation feeds at its plus pin is a rail,
    as a supply pin's is. Without the source, or with the trimmer to a net the source does not feed, it stays."""
    sim = {"sources": {"J1": {"plus": "1", "minus": "2"}}}
    found = ["Q2: no base-emitter resistor – state undefined while the firmware is not running"]
    assert undefined(fed_stage(), sim) == []                                  # before: found
    assert undefined(fed_stage(), None) == found                              # nothing says what 9V0 is
    assert undefined(fed_stage(), {"sources": {"J1": {"plus": "2", "minus": "1"}}}) == found    # GND is no supply
    assert undefined(fed_stage("FLOAT"), sim) == found                        # a net the source does not feed


# --- the ESPurna-H (espurna-h): a regulator's output on its tab --------------------------------------------------------
LDO = {"lcsc": "C9000514", "mpn": "test LDO", "kind": "ic", "verified": {"by": "test"},
       "pins": {"1": {"name": "GND", "type": "ground"},
                "2": {"name": "VOUT", "type": "power_output", "needs": [{"what": "capacitor", "c_min_f": 22e-6}]},
                "3": {"name": "VIN", "type": "power_in"}, "4": {"name": "VOUT", "type": "power_output"},
                "5": {"name": "SENSE", "type": "input", "needs": [{"what": "pull_up", "r_max_ohm": 1e5}]}},
       "needs": {"decoupling": False}}


def tab_regulator(out_pins, farad=1e-5):
    """U1, an LDO whose entry asks for 22 µF on VOUT (pin 2) – VOUT is pin 2 and the tab (pin 4), as on an AMS1117 –,
    with `out_pins` on OUT and the others left open; C1 (`farad`) from OUT to GND."""
    cap = {"lcsc": "C9000515", "mpn": "test capacitor", "kind": "capacitor",
           "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}},
           "values": {"value_f": farad}}
    nets = {"VIN": ["U1.3"], "GND": ["U1.1", "C1.2"], "OUT": [f"U1.{p}" for p in out_pins] + ["C1.1"]}
    comps = [{"designator": "U1", "type": "ic", "lcsc": "C9000514",
              "pins": {n: p["name"] for n, p in LDO["pins"].items()},
              "nc": [n for n in LDO["pins"] if n not in ("1", "3", *out_pins)]},
             {"designator": "C1", "type": "capacitor", "lcsc": "C9000515", "pins": {"1": "1", "2": "2"}}]
    graph = {"name": "t", "version": "1", "ground": "GND", "components": comps,
             "nets": [{"name": n, "pins": p, "v": [0, 5.5]} for n, p in nets.items()]}
    return Design.from_data(graph, {"C9000514": LDO, "C9000515": cap})


def test_a_need_on_a_pin_left_open_is_judged_where_its_terminal_is_connected():
    """The ESPurna-H's AMS1117-3.3 (IC1): the Eagle device takes VOUT from the tab (pin 4) and leaves pin 2 – VOUT
    too, the same node inside the part – on no net; the library's entry asks for 22 µF on pin 2. Before:
    REQ.missing, 'not connected', though C12 sits on the output. Now the need is judged on the net of the pin of the
    same name: 10 µF there is too little (REQ.value), 22 µF is enough. A pin left open with no other pin of its name
    (SENSE) is still missing what it needs."""
    sense = ("REQ.missing", "U1.SENSE (5): not connected – needs a pull up of at most 100 kΩ")
    assert sorted((f.code, f.text) for f in pin_needs(tab_regulator(["4"]))) == [
        sense, ("REQ.value", "U1.4: needs a capacitor of at least 22 µF to GND – C1 on OUT: 10 µF")]
    assert [(f.code, f.text) for f in pin_needs(tab_regulator(["4"], 2.2e-5))] == [sense]
    assert sorted((f.code, f.text) for f in pin_needs(tab_regulator(["2", "4"]))) == [
        sense, ("REQ.value", "U1.2: needs a capacitor of at least 22 µF to GND – C1 on OUT: 10 µF")]


# --- the known gaps of the open designs (TD-124 to TD-133) -------------------------------------------------------------
CELL = {"lcsc": "C9000516", "mpn": "test cell holder", "kind": "battery_holder", "verified": {"by": "test"},
        "pins": {"1": {"name": "+", "type": "passive", "role": "plus"},
                 "2": {"name": "-", "type": "passive", "role": "minus"}}}
LOGIC = {"lcsc": "C9000517", "mpn": "test logic", "kind": "ic", "verified": {"by": "test"},
         "pins": {"1": {"name": "VDD", "type": "power_in"}, "2": {"name": "GND", "type": "ground"}},
         "needs": {"decoupling": False}}


def reversed_at(graph_nets, comps, parts):
    """PATH.reverse's places on a design of `comps` with `graph_nets` {name: pins}."""
    from edakit.engines.paths import reverse
    graph = {"name": "t", "version": "1", "ground": "GND", "components": comps,
             "nets": [{"name": n, "pins": p, "v": [0, 5.5]} for n, p in graph_nets.items()]}
    d = Design.from_data(graph, parts)
    return sorted(f.place for f in reverse(d, d))


def test_a_connector_hands_a_reversed_source_on_to_none_of_its_other_pins():
    """The Micro-Lipo's JP4: the cell's VBAT on one pad, 5V on another – edakit let a connector pass a reversed source
    from every pin to every pin, so the charger's VDD (U1.4), the red LED on 5V and the CC resistors behind the
    USB-C receptacle were reached. A connector's contacts are separate: it takes a reversed voltage on the pin it sits
    on and hands nothing on. A part straight on the cell's net is still reached."""
    comps = [{"designator": "BT1", "type": "battery_holder", "lcsc": "C9000516", "pins": {"1": "+", "2": "-"}},
             {"designator": "J1", "type": "connector", "lcsc": "C9000515", "pins": {"1": "1", "2": "2"}},
             {"designator": "U1", "type": "ic", "lcsc": "C9000517", "pins": {"1": "VDD", "2": "GND"}}]
    parts = {"C9000515": TERMINAL, "C9000516": CELL, "C9000517": LOGIC}
    assert reversed_at({"VBAT": ["BT1.1", "J1.1"], "5V": ["J1.2", "U1.1"], "GND": ["BT1.2", "U1.2"]},
                       comps, parts) == []                                 # before: ["U1.1"]
    assert reversed_at({"VBAT": ["BT1.1", "J1.1", "U1.1"], "5V": ["J1.2"], "GND": ["BT1.2", "U1.2"]},
                       comps, parts) == ["U1.1"]


def ground_return(gate="VIN", leak=False):
    """ADLSC's input in brief: the terminal J1 (reversible) brings VIN on pin 2 and its return VRTN on pin 1; Q1 in
    the ground return – drain on VRTN, source on GND, gate on `gate` –; U1's supply from VIN to GND, U2's straight
    across VIN and VRTN. `gate` "VG": through R1 from VIN; "CTRL": a net nothing on the plus side holds. `leak`: R2
    from VRTN to GND beside Q1."""
    res = {"lcsc": "C9000510", "mpn": "test resistor", "kind": "resistor",
           "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}},
           "values": {"value_ohm": 10000}}
    j1 = {"designator": "J1", "type": "connector", "lcsc": "C9000515", "pins": {"1": "1", "2": "2"},
          "source": "reversible"}
    comps = [j1, {"designator": "Q1", "type": "transistor", "lcsc": "C9000514", "pins": {"1": "G", "2": "D", "3": "S"}},
             {"designator": "U1", "type": "ic", "lcsc": "C9000517", "pins": {"1": "VDD", "2": "GND"}},
             {"designator": "U2", "type": "ic", "lcsc": "C9000517", "pins": {"1": "VDD", "2": "GND"}}]
    nets = {"VIN": ["J1.2", "U1.1", "U2.1"], "VRTN": ["J1.1", "Q1.2", "U2.2"], "GND": ["Q1.3", "U1.2"]}
    nets.setdefault(gate, []).append("Q1.1")
    if gate == "VG":
        comps.append({"designator": "R1", "type": "resistor", "lcsc": "C9000510", "pins": {"1": "1", "2": "2"}})
        nets["VIN"].append("R1.1")
        nets["VG"].append("R1.2")
    if leak:
        comps.append({"designator": "R2", "type": "resistor", "lcsc": "C9000510", "pins": {"1": "1", "2": "2"}})
        nets["VRTN"].append("R2.1")
        nets["GND"].append("R2.2")
    return nets, comps, {"C9000510": res, "C9000514": NMOS, "C9000515": TERMINAL, "C9000517": LOGIC}


def test_a_low_side_mosfet_cuts_a_reversed_source_off_ground():
    """ADLSC's Q1 (AOD442) in the ground return: reversed, its gate sits below its source and its body diode blocks –
    the board's ground floats, and only what sits across the terminal's own two nets sees the reversed 5 V. Before:
    PATH.reverse knew the series diode and the high-side P-MOSFET only, and walked from J1's pins as if GND were the
    return – 20 findings on the ADLSC, Q1's own pins among them. Now U2, straight across VIN and VRTN, is still found;
    U1 behind the cut and Q1 are not. A gate through a resistor from the plus side cuts as well; a gate the plus side
    does not hold, or a resistor beside Q1 from the return to ground, does not."""
    assert reversed_at(*ground_return()) == ["U2.1", "U2.2"]          # before: Q1.1, Q1.2, U1.1, U2.1, U2.2
    assert reversed_at(*ground_return("VG")) == ["U2.1", "U2.2"]
    assert reversed_at(*ground_return("CTRL")) == ["Q1.2", "U1.1", "U2.1", "U2.2"]
    assert reversed_at(*ground_return(leak=True)) == ["Q1.1", "Q1.2", "R2.1", "U1.1", "U2.1", "U2.2"]


def tvs_across(tvs):
    """ground_return() with the TVS D4 (`tvs` its values.tvs) straight across VIN and VRTN – cathode on VIN – in place
    of U2."""
    nets, comps, parts = ground_return()
    comps[-1] = {"designator": "D4", "type": "diode", "lcsc": "C9000501", "pins": {"1": "K", "2": "A"}}
    nets = {n: [{"U2.1": "D4.1", "U2.2": "D4.2"}.get(r, r) for r in pins] for n, pins in nets.items()}
    return nets, comps, {**parts, "C9000501": {**TVS, "values": {"tvs": tvs}}}


def test_a_bidirectional_tvs_takes_a_reversed_source():
    """ADLSC's D4, an SMBJ5.0CA across the terminal: bidirectional, it blocks up to its breakdown either way. The
    parts schema had values tvs true only, so a reversed 5 V across it was judged as across a one-way diode – PATH.reverse
    on both pins. values tvs "bidirectional" is tolerated, and LIM.v holds it to its working voltage either way; a
    one-way TVS is still found, and the schema takes nothing but true and "bidirectional"."""
    from edakit.engines.quantities import part_voltages
    assert reversed_at(*tvs_across("bidirectional")) == []                  # before: D4.1, D4.2
    assert reversed_at(*tvs_across(True)) == ["D4.1", "D4.2"]
    graph = {"name": "t", "version": "1", "ground": "GND",
             "components": [{"designator": "D4", "type": "diode", "lcsc": "C9000501", "pins": {"1": "K", "2": "A"}}],
             "nets": [{"name": "LINE", "pins": ["D4.1"], "v": [-6, 3]}, {"name": "GND", "pins": ["D4.2"], "v": [0, 0]}]}
    volts = {t: [q.hi for q in part_voltages(Design.from_data(graph, {"C9000501": {**TVS, "values": {"tvs": t}}}))
                 if q.place == "D4"] for t in (True, "bidirectional")}
    assert volts == {True: [3], "bidirectional": [6]}                       # before: 3 V both
    assert schema.problems({**TVS, "values": {"tvs": "both"}}) == [
        "values.tvs: true for a TVS diode, \"bidirectional\" for one that blocks both ways (the CA suffix), not 'both'"]


# --- the ESPurna-H (espurna-h): the mains side --------------------------------------------------------------------------
def mains_side(ac=True, terminal_rms=300, module=True):
    """The ESPurna-H's mains side in brief: the terminal J1 (rated `terminal_rms` V AC, no DC rating) on NEUTRAL, 230 V
    + 10 % against the line at GND – 358 V peak –, a divider R1 (470 kΩ, rated 200 V) – R2 (1 kΩ) from NEUTRAL through
    TAP (179 V peak) to GND, and the module U1's AC input (85 … 265 V AC, 120 … 350 V DC) on NEUTRAL. `ac`: NEUTRAL and
    TAP are marked AC nets."""
    res = {"lcsc": "C9000510", "mpn": "test resistor", "kind": "resistor",
           "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}},
           "values": {"value_ohm": 470000}, "limits": {"v_max_v": 200}}
    terminal = {**TERMINAL, "limits": {"v_rms_max_v": terminal_rms}}
    mod = {"lcsc": "C9000518", "mpn": "test AC module", "kind": "module", "verified": {"by": "test"},
           "pins": {"1": {"name": "AC", "type": "power_in", "role": "ac_n", "v_max_v": 350, "v_min_v": -350,
                          "v_rms_max_v": 265},
                    "2": {"name": "AC", "type": "power_in", "role": "ac_l", "v_max_v": 350, "v_min_v": -350,
                          "v_rms_max_v": 265}},
           "values": {"behavior": "none"}}
    comps = [{"designator": "J1", "type": "connector", "lcsc": "C9000515", "pins": {"1": "1", "2": "2"}},
             {"designator": "R1", "type": "resistor", "lcsc": "C9000510", "pins": {"1": "1", "2": "2"}},
             {"designator": "R2", "type": "resistor", "lcsc": "C9000510", "pins": {"1": "1", "2": "2"}}]
    nets = {"NEUTRAL": (["J1.1", "R1.1"], 358), "TAP": (["R1.2", "R2.1"], 179), "GND": (["J1.2", "R2.2"], 0)}
    if module:
        comps.append({"designator": "U1", "type": "module", "lcsc": "C9000518", "pins": {"1": "AC", "2": "AC"}})
        nets["NEUTRAL"][0].append("U1.1")
        nets["GND"][0].append("U1.2")
    graph = {"name": "t", "version": "1", "ground": "GND", "components": comps,
             "nets": [{"name": n, "pins": p, "v": [-v, v], **({"ac": True} if ac and v else {})}
                      for n, (p, v) in nets.items()]}
    return Design.from_data(graph, {"C9000510": res, "C9000515": terminal, "C9000518": mod})


def lim_v(d):
    from edakit.engines.limits import judge_all
    from edakit.engines.quantities import part_voltages, pin_voltages
    return sorted((f.place, f.text) for f in judge_all(d, pin_voltages(d) + part_voltages(d)))


def test_an_ac_net_is_held_by_its_rms_and_a_divider_s_taps_move_together():
    """The ESPurna-H's mains side: the KF301 terminals rated 300 V AC, the HLK-PM01's input 85 … 265 V AC, the
    5 × 470 kΩ divider to the HLW8012. edakit knew no AC net: it held the 358 V peak against the terminals' 300 V and
    the module's 350 V DC, and each divider resistor to the highest voltage of its nets against GND (LIM.v on JP2, JP42,
    U$1.2, R51 to R53). A net marked ac is a sine – its range the peaks –, an AC rating (v_rms_max_v) holds its rms in
    place of the DC limits, and a resistor between two AC nets sees the difference of their like ends. A terminal
    rated 250 V AC is still found at 253 V rms; unmarked, the divider resistor is held as before."""
    assert lim_v(mains_side()) == []                                    # before: R1, U1.1 (2×)
    assert lim_v(mains_side(terminal_rms=250)) == [("J1", "J1: up to 253 V rms, rated 250 V rms")]
    assert lim_v(mains_side(ac=False, module=False)) == [("R1", "R1: nets up to 358.0 V, rated 200 V")]


def test_a_varistor_is_held_to_its_ac_rating_on_the_mains():
    """The ESPurna-H's S10K250 (V11) across the module's input: 250 V AC, 320 V DC (TDK SIOV). edakit had no kind for a
    varistor – the transcription took kind ic, and nothing checked it. Kind varistor holds its VRMS on AC nets – 253 V
    rms of 230 V + 10 % is above 250 V –, its VDC elsewhere, both without derating; a 275 V type passes."""
    sv = {"lcsc": "C9000519", "mpn": "test varistor", "kind": "varistor", "verified": {"by": "test"},
          "pins": {"1": {"name": "1", "type": "passive", "role": "1"}, "2": {"name": "2", "type": "passive", "role": "2"}},
          "values": {"v_varistor_v": 390}, "limits": {"v_rms_max_v": 250, "v_max_v": 320}}

    def across(ac=True, rms=250, v=358):
        graph = {"name": "t", "version": "1", "ground": "GND",
                 "components": [{"designator": "RV1", "type": "varistor", "lcsc": "C9000519", "pins": {"1": "1", "2": "2"}}],
                 "nets": [{"name": "MAINS", "pins": ["RV1.1"], "v": [-v, v], **({"ac": True} if ac else {})},
                          {"name": "GND", "pins": ["RV1.2"], "v": [0, 0]}]}
        return lim_v(Design.from_data(graph, {"C9000519": {**sv, "limits": {"v_rms_max_v": rms, "v_max_v": 320}}}))
    assert across() == [("RV1", "RV1: up to 253 V rms, rated 250 V rms")]
    assert across(rms=275) == []
    assert across(ac=False) == [("RV1", "RV1: up to 358.0 V, rated 320 V")]
    assert across(ac=False, v=300) == []
    assert schema.problems(sv) == []
