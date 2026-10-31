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
    assert "U2.4 (LE(ED1)): an input left open (nc) – it floats" in findings(project, "LVL.undefined", "nc")
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
