"""The behaviour model logic (schema-gaps.md E1): a part draws its supply current icc_a at its supply pin, and its
outputs rest in a defined state – an open-drain output released, a tri-state output released unless its part ties
every enable pin active, a push-pull output low – unless the pin's `state` in its entry or the component's `states`
says high, low or off. Before, every output of the model was held low through 50 Ω: a pull-up on an open-drain
output read as a load fighting a low. Library parts from edakit/parts/, their currents read from their datasheets."""

import json
import shutil

import pytest
from test_configs import place

from helpers import check

from edakit import library, schema
from edakit.design import Design
from edakit.sim import netlist
from edakit.sim import run as simrun

ngspice = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


def resistor(project, des, a, b, value="10k"):
    """A 10 kΩ (C17414) from net a to net b."""
    project.use_library_part("C17414")
    g = project.graph()
    g["graph"]["components"].append(
        {"designator": des, "type": "resistor", "lcsc": "C17414", "value": value, "pins": {"1": "1", "2": "2"}})
    project.net(g, a)["pins"].append(f"{des}.1")
    project.net(g, b)["pins"].append(f"{des}.2")
    project.save_graph(g)


def states(project, des, **pins):
    g = project.graph()
    project.comp(g, des)["states"] = pins
    project.save_graph(g)


def operating_point(project):
    """The example's usb-nom/idle scenario at the min corner: (design, netlist text, meta, ngspice result)."""
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    d = Design.from_config(project.config())
    sc = next(x for x in simrun.scenarios(sim) if x["supply_name"] == "usb-nom" and x["load_name"] == "idle")
    text, meta = netlist.build(d, sim, sc)
    return d, text, meta, simrun.ngspice(text)


def volts(res, d, net):
    return res.get(netlist.node(net, d.ground), 0.0)


def rail_current(meta, res):
    """What the Pico 2's regulator (U1) delivers to 3V3."""
    return res[meta["regs"]["U1"]["ammeter"]]


def through(res, d, a, b, ohm=10e3):
    return (volts(res, d, a) - volts(res, d, b)) / ohm


def ina226(project):
    """INA226 U9 on 3V3, its Alert on ALERT9 pulled up through R9 10 kΩ to 3V3 (SBOS547C 8.2.1.2)."""
    place(project, "C49851", "U9", {"6": "3V3", "7": "GND", "3": "ALERT9"})
    resistor(project, "R9", "ALERT9", "3V3")


# --- the states ----------------------------------------------------------------------------------------------------
@ngspice
def test_an_open_drain_output_lets_go_and_its_pull_up_carries_nothing(project):
    """Released, Alert sits at the pull-up's rail: R9 carries nothing, and 3V3 delivers the INA226's 420 µA more – its
    IQ, nothing else (the old model sank 330 µA through R9 besides)."""
    *_, meta, res = operating_point(project)
    before = rail_current(meta, res)
    ina226(project)
    d, text, meta, res = operating_point(project)
    assert "R_U9_3 " not in text                                        # nothing of U9 on Alert
    assert abs(through(res, d, "3V3", "ALERT9")) < 1e-9
    assert rail_current(meta, res) - before == pytest.approx(420e-6, abs=2e-6)


@ngspice
def test_the_component_holds_an_open_drain_output_low(project):
    """states {"Alert": "low"} – an alert asserted: R9 carries 3.3 V / 10 kΩ, and 3V3 delivers that on top of IQ."""
    *_, meta, res = operating_point(project)
    before = rail_current(meta, res)
    ina226(project)
    states(project, "U9", Alert="low")
    d, _, meta, res = operating_point(project)
    assert volts(res, d, "ALERT9") < 0.02
    i_pullup = through(res, d, "3V3", "ALERT9")
    assert i_pullup == pytest.approx(3.3 / 10.05e3, rel=0.02)
    assert rail_current(meta, res) - before == pytest.approx(420e-6 + i_pullup, abs=2e-6)


@ngspice
def test_a_push_pull_output_drives_the_state_its_entry_declares(project):
    """CH340C at 3.3 V: its TXD idles high (CH340DS1 3C, 5.1) – into R9 10 kΩ to GND it sits at VCC, and what it
    sources comes out of VCC; the component's states {"TXD": "low"} turns it round."""
    place(project, "C84681", "U9", {"16": "3V3", "1": "GND", "4": "3V3", "2": "TXD9"}, config="3v3")
    resistor(project, "R9", "TXD9", "GND")
    d, text, meta, res = operating_point(project)
    assert volts(res, d, "TXD9") == pytest.approx(volts(res, d, "3V3") * 10e3 / 10.05e3, rel=1e-3)
    sourced = res[meta["logic"]["U9"]["2"]["ammeter"]]
    assert sourced == pytest.approx(through(res, d, "TXD9", "GND"), rel=1e-3)
    states(project, "U9", TXD="low")
    d, _, _, res = operating_point(project)
    assert volts(res, d, "TXD9") < 1e-3


@ngspice
def test_a_push_pull_output_without_a_state_stays_low(project):
    """CH340C DTR# – set by the host application, no idle level in the datasheet: low through 50 Ω, as before."""
    place(project, "C84681", "U9", {"16": "3V3", "1": "GND", "4": "3V3", "13": "DTR9"}, config="3v3")
    resistor(project, "R9", "DTR9", "3V3")
    d, _, _, res = operating_point(project)
    assert volts(res, d, "DTR9") == pytest.approx(volts(res, d, "3V3") * 50 / 10.05e3, rel=0.01)


@ngspice
def test_a_tristate_output_drives_only_with_its_enable_tied_active(project):
    """SN74AHCT1G125 on +5V, Y pulled up through R9 to 3V3: OE# on ground – Y drives (low, the default); OE# on a
    net of its own – Y lets go, R9 carries nothing."""
    place(project, "C7484", "U9", {"5": "+5V", "3": "GND", "1": "GND", "2": "GND", "4": "Y9"})
    resistor(project, "R9", "Y9", "3V3")
    d, _, _, res = operating_point(project)
    assert volts(res, d, "Y9") < 0.02
    g = project.graph()
    project.net(g, "GND")["pins"].remove("U9.1")
    g["graph"]["nets"].append({"name": "OE9", "pins": ["U9.1"], "v": [0, 5.5]})
    project.save_graph(g)
    d, _, _, res = operating_point(project)
    assert abs(through(res, d, "3V3", "Y9")) < 1e-9


# --- the supply current ------------------------------------------------------------------------------------------
def netlist_of(project):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    d = Design.from_config(project.config())
    return netlist.build(d, sim, next(iter(simrun.scenarios(sim))))[0]


def test_icc_is_drawn_at_the_supply_pin_or_per_pin(project):
    """BME280: 714 µA at VDD (role vdd), none at VDDIO; MPU-6050: a table per pin – 3.9 mA at VDD, 100 µA at VLOGIC
    (PS-MPU-6000A-00 Rev 3.4, 6.3)."""
    place(project, "C92489", "U8", {"8": "3V3", "6": "3V3", "1": "GND", "7": "GND", "2": "3V3", "5": "GND"})
    place(project, "C24112", "U9", {"13": "3V3", "8": "3V3", "18": "GND"})
    lines = netlist_of(project).splitlines()
    loads = {ln.split()[0]: ln for ln in lines if ln.startswith(("B_U8_", "B_U9_"))}
    assert "I = 0.000714*" in loads["B_U8_8"] and "B_U8_6" not in loads
    assert "I = 0.0039*" in loads["B_U9_13"] and "I = 0.0001*" in loads["B_U9_8"]


# --- the data ------------------------------------------------------------------------------------------------------
def test_the_schema_holds_state_and_icc_per_pin():
    pins = {"1": {"name": "VDD", "type": "power_in"}, "2": {"name": "INT", "type": "output", "drive": "open_drain"},
            "3": {"name": "TX", "type": "output", "state": "high"}, "4": {"name": "EN", "type": "input"}}
    ok = {"kind": "ic", "values": {"behavior": "logic", "icc_a": {"VDD": 0.001}}, "pins": pins}
    assert schema.problems(ok) == []
    bad = {**ok, "values": {"behavior": "logic", "icc_a": {"VIO": 0.001}},
           "pins": {**pins, "2": {**pins["2"], "state": "high"}, "3": {**pins["3"], "state": "up"},
                    "4": {**pins["4"], "state": "low"}}}
    probs = schema.problems(bad)
    assert "values.icc_a: 'VIO' – not the name of a supply pin (power_in) of the part" in probs
    assert "pins.2.state: an open-drain output cannot drive high – low or off" in probs
    assert "pins.3.state: 'up' – high, low or off" in probs
    assert "pins.4.state: on an output or bidirectional pin only" in probs


def test_a_component_state_names_an_output_of_its_entry(project):
    place(project, "C49851", "U9", {"6": "3V3", "7": "GND", "3": "ALERT9"})
    states(project, "U9", Alert="high", SCL="low", XYZ="off", **{"4": "sideways"})
    cfg = project.config()
    texts = sorted(f.text for f in check(Design.from_config(cfg), cfg).findings
                   if f.code == "STRUCT.entry" and f.place == "U9")
    assert texts == ["U9: states 4 'sideways' – high, low or off",
                     "U9: states Alert 'high' – an open-drain output cannot drive high (low or off)",
                     "U9: states SCL – pin 5 (SCL) is no output",
                     "U9: states XYZ – parts entry C49851 has no such pin"]


DRAFTS = {   # entry: icc_a, from the datasheet named in its sources
    "C92489": 0.000714,                          # BME280, IDDP
    "C49851": 0.00042,                           # INA226, IQ max
    "C24112": {"VDD": 0.0039, "VLOGIC": 0.0001},  # MPU-6050, typ – no maximum given
    "C9866": 0.00065,                            # DS3231, ICCSCONV at 5.5 V
    "C16030": 0.0015,                            # MAX6675, ICC max
    "C52028": 0.0015,                            # MAX31855, ICC max
    "C5438445": 0.0025,                          # INMP441, normal mode at 3.3 V max
    "C18148": 0.0022,                            # MAX3485, ICC max with DE = VCC
    "C19738": 0.0009,                            # MAX485, ICC max with DE = VCC
    "C7605": 0.0001,                             # PCF8574, IDD max
    "C86832": 0.0001,                            # PCF8574A, IDD max
    "C14267": 0.02,                              # CH340G, ICC max at 5 V
    "C84681": 0.02,                              # CH340C, ICC max at 5 V
    "C6705483": {"VSUP": 0.0014, "DVDD": 0.0001},  # HX711, typ with the regulator – no maximum given
}


@pytest.mark.parametrize("key", sorted(DRAFTS))
def test_the_drafts_draw_their_datasheet_current(key):
    e = library.entry(key)
    assert e["values"]["behavior"] == "logic" and e["values"]["icc_a"] == DRAFTS[key]
    assert any("icc_a" in s for s in e["sources"]), "the source of icc_a"
    assert schema.problems(e) == []
