"""New relations of LEVELS and REQUIRES from maker-coverage, warnings while new: an IC input left in nc (CK-1),
open-drain and tri-state outputs (CK-2), an analog node only capacitors reach (CK-25), capacitors in series without a
resistor to share their voltage (CK-29)."""

from edakit import engines
from edakit.design import Design

# a test IC: ground, supply, an open-drain interrupt output, a second output whose drive the tests choose, an analog
# input – values for the test, not from a datasheet
CHIP = {"lcsc": "C9000401", "mpn": "test sensor", "kind": "ic", "verified": {"by": "test"},
        "pins": {"1": {"name": "GND", "type": "ground"}, "2": {"name": "VDD", "type": "power_in"},
                 "3": {"name": "INT", "type": "output", "drive": "open_drain"},
                 "4": {"name": "DO", "type": "output"}, "5": {"name": "AIN", "type": "analog"}},
        "needs": {"decoupling": False}}


def findings(project, code, grade=None):
    cfg = project.config()
    rep = engines.run(Design.from_config(cfg), cfg)
    return [f.text for f in rep.findings if f.code == code and (grade is None or f.grade == grade)]


def chip(project, des="U8", nets=None, part=None):
    """`des` (CHIP) on 3V3 and GND; `nets` {pin: net name} for the others, a new net each unless it exists."""
    project.save_part("C9000401", part or CHIP)
    g = project.graph()
    pins = {n: i["name"] for n, i in (part or CHIP)["pins"].items()}
    nets = nets or {}
    g["graph"]["components"].append({"designator": des, "type": "ic", "lcsc": "C9000401", "pins": pins,
                                     "nc": [n for n in pins if n not in ("1", "2") and n not in nets]})
    project.net(g, "3V3")["pins"].append(f"{des}.2")
    project.net(g, "GND")["pins"].append(f"{des}.1")
    for num, name in nets.items():
        existing = [n for n in g["graph"]["nets"] if n["name"] == name]
        if existing:
            existing[0]["pins"].append(f"{des}.{num}")
        else:
            g["graph"]["nets"].append({"name": name, "pins": [f"{des}.{num}"], "v": [0, 3.4]})
    project.save_graph(g)
    return g


# --- CK-1 --------------------------------------------------------------------------------------------------------------
def test_an_ic_input_left_open(project):
    g = project.graph()
    project.net(g, "LED_LE")["pins"].remove("U2.4")                 # the TLC5916's LE(ED1) into nc
    project.comp(g, "U2")["nc"].append("4")
    project.save_graph(g)
    assert "U2.LE(ED1) (4): an input left open (nc) – it floats" in findings(project, "LVL.undefined", "nc")
    part = project.part("C90107")
    part["pins"]["4"]["float_ok"] = True
    project.save_part("C90107", part)
    assert findings(project, "LVL.undefined", "nc") == []


def test_a_module_input_in_nc_is_left_to_the_module(project):
    assert findings(project, "LVL.undefined", "nc") == []           # the Pico 2's RUN and 3V3_EN are in nc


# --- CK-2 --------------------------------------------------------------------------------------------------------------
def test_an_open_drain_line_needs_its_pull_up(project):
    g = chip(project, nets={"3": "INT"})
    project.free_pins(g, "U1.11")
    project.net(g, "INT")["pins"].append("U1.11")
    project.save_graph(g)
    assert findings(project, "LVL.undefined", "open_drain") == [
        "INT: driven only by outputs that let go (U8.3) and nothing holds it – released, it floats"]
    assert not any(t.startswith("INT:") for t in findings(project, "LVL.undefined", ""))   # not twice
    project.use_library_part("C17414")
    g["graph"]["components"].append({"designator": "R8", "type": "resistor", "lcsc": "C17414", "value": "10k",
                                     "pins": {"1": "1", "2": "2"}})
    project.net(g, "INT")["pins"].append("R8.1")
    project.net(g, "3V3")["pins"].append("R8.2")
    project.save_graph(g)
    assert findings(project, "LVL.undefined", "open_drain") == []


def test_open_drain_outputs_share_a_line_a_push_pull_output_does_not(project):
    chip(project, "U8", {"3": "IRQ"})
    g = chip(project, "U9", {"3": "IRQ"})
    assert not any(t.startswith("IRQ:") for t in findings(project, "LVL.contention"))
    project.net(g, "IRQ")["pins"].append("U9.4")                     # DO, push-pull, on the shared line
    project.comp(g, "U9")["nc"].remove("4")
    project.save_graph(g)
    assert any(t.startswith("IRQ: several outputs drive this net") for t in findings(project, "LVL.contention"))


# --- CK-25 -------------------------------------------------------------------------------------------------------------
def capacitor(project, g, des, a, b):
    g["graph"]["components"].append({"designator": des, "type": "capacitor", "lcsc": "C49678", "value": "100nF",
                                     "pins": {"1": "1", "2": "2"}})
    for pin, net in (("1", a), ("2", b)):
        existing = [n for n in g["graph"]["nets"] if n["name"] == net]
        if existing:
            existing[0]["pins"].append(f"{des}.{pin}")
        else:
            g["graph"]["nets"].append({"name": net, "pins": [f"{des}.{pin}"], "v": [0, 3.4]})


def test_an_analog_node_only_capacitors_reach(project):
    g = chip(project, nets={"5": "AIN"})
    capacitor(project, g, "C8", "AIN", "GND")
    project.save_graph(g)
    assert findings(project, "LVL.undefined", "analog") == [
        "AIN: an analog node only capacitors reach – no DC path to a defined level"]


# --- CK-29 -------------------------------------------------------------------------------------------------------------
def test_capacitors_in_series_without_balancing(project):
    g = project.graph()
    capacitor(project, g, "C8", "+5V", "MID")
    capacitor(project, g, "C9", "MID", "GND")
    project.save_graph(g)
    assert findings(project, "REQ.missing", "balance") == [
        "MID: only capacitors touch it (C8, C9) – in series their voltage divides by leakage"]


# --- CK-3 --------------------------------------------------------------------------------------------------------------
def sensor_on_bus(project, g, des, ad0):
    """`des`: an I2C device at 0x68 + AD0 (a test part shaped like an MPU-6050 – not its datasheet), its SDA on SDA,
    SCL on SCL, AD0 on `ad0` (a net name)."""
    part = {"lcsc": "C9000402", "mpn": "test imu", "kind": "ic", "verified": {"by": "test"}, "needs": {"decoupling": False},
            "address": {"base": 0x68, "pins": {"3": 1}},
            "pins": {"1": {"name": "SDA", "type": "bidirectional", "role": "sda", "drive": "open_drain"},
                     "2": {"name": "SCL", "type": "input", "role": "scl"}, "3": {"name": "AD0", "type": "input"},
                     "4": {"name": "GND", "type": "ground"}, "5": {"name": "VDD", "type": "power_in"}}}
    project.save_part("C9000402", part)
    g["graph"]["components"].append({"designator": des, "type": "ic", "lcsc": "C9000402",
                                     "pins": {n: i["name"] for n, i in part["pins"].items()}})
    for pin, net in (("1", "SDA"), ("2", "SCL"), ("3", ad0), ("4", "GND"), ("5", "3V3")):
        existing = [n for n in g["graph"]["nets"] if n["name"] == net]
        if existing:
            existing[0]["pins"].append(f"{des}.{pin}")
        else:
            g["graph"]["nets"].append({"name": net, "pins": [f"{des}.{pin}"], "v": [0, 3.4]})


def test_two_devices_at_one_address(project):
    g = project.graph()
    sensor_on_bus(project, g, "U8", "GND")
    sensor_on_bus(project, g, "U9", "GND")
    project.save_graph(g)
    assert findings(project, "REQ.forbidden", "address") == ["bus SDA: U8 (AD0 low), U9 (AD0 low) all answer to 0x68"]
    project.net(g, "GND")["pins"].remove("U9.3")
    project.net(g, "3V3")["pins"].append("U9.3")                    # U9 at 0x69
    project.save_graph(g)
    assert findings(project, "REQ.forbidden", "address") == []


def test_an_address_of_the_wrong_form(project):
    g = project.graph()
    sensor_on_bus(project, g, "U8", "GND")
    project.save_graph(g)
    part = project.part("C9000402")
    part["address"] = {"base": "0x68"}
    project.save_part("C9000402", part)
    assert any("address must be {base, pins" in t for t in findings(project, "PARTS.schema"))


# --- CK-26 -------------------------------------------------------------------------------------------------------------
def test_a_uart_line_that_does_not_cross(project):
    """U1's GP0 transmits (fn uart.tx, its functions list uart0.tx); on the net a module's TX – an output –, nothing
    that receives."""
    part = {"lcsc": "C9000403", "mpn": "test gps", "kind": "ic", "verified": {"by": "test"}, "needs": {"decoupling": False},
            "pins": {"1": {"name": "TX", "type": "output"}, "2": {"name": "RX", "type": "input"},
                     "3": {"name": "GND", "type": "ground"}, "4": {"name": "VCC", "type": "power_in"}}}
    project.save_part("C9000403", part)
    g = project.graph()
    project.free_pins(g, "U1.1")
    g["graph"]["components"].append({"designator": "U8", "type": "ic", "lcsc": "C9000403",
                                     "pins": {n: i["name"] for n, i in part["pins"].items()}, "nc": ["2"]})
    g["graph"]["nets"].append({"name": "GPS_TX", "pins": ["U1.1", "U8.1"], "v": [0, 3.4], "fn": "uart.tx"})
    project.net(g, "GND")["pins"].append("U8.3")
    project.net(g, "3V3")["pins"].append("U8.4")
    project.save_graph(g)
    assert findings(project, "REQ.function", "uart") == [
        "GPS_TX: U1.1 transmits (uart.tx), but nothing on it receives – U8.1 (output)"]
    project.net(g, "GPS_TX")["pins"][1] = "U8.2"                     # crossed: GP0 to the module's RX
    project.comp(g, "U8")["nc"] = ["1"]
    project.save_graph(g)
    assert findings(project, "REQ.function", "uart") == []
