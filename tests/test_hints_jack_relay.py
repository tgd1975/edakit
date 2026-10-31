"""HINT.jack_supply (maker-coverage HT-7): a supply on a jack contact; HINT.relay_load (HT-14): relay contacts that
switch a load off the board."""

from edakit import engines
from edakit.design import Design

# values for the tests, not from datasheets
JACK = {"lcsc": "C9000601", "mpn": "test TRS jack", "kind": "connector", "verified": {"by": "test"},
        "limits": {"v_max_v": 30, "i_max_a": 1},
        "pins": {"1": {"name": "T", "type": "passive", "role": "tip"}, "2": {"name": "R", "type": "passive",
                                                                          "role": "ring"},
                 "3": {"name": "S", "type": "passive", "role": "sleeve"}}}
RELAY = {"lcsc": "C9000602", "mpn": "test relay", "kind": "relay", "verified": {"by": "test"},
         "limits": {"v_coil_max_v": 6, "i_max_a": 2, "v_max_v": 30}, "values": {"coil_ohm": 125},
         "pins": {"1": {"name": "A1", "type": "passive", "role": "coil_plus"},
                  "2": {"name": "A2", "type": "passive", "role": "coil_minus"},
                  "3": {"name": "COM", "type": "passive", "role": "common"},
                  "4": {"name": "NO", "type": "passive", "role": "no"}}}
TERMINAL = {"lcsc": "C9000603", "mpn": "test terminal", "kind": "connector", "verified": {"by": "test"},
            "limits": {"v_max_v": 30, "i_max_a": 5},
            "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}}}


def hints(project, code):
    cfg = project.config()
    return [f.place for f in engines.run(Design.from_config(cfg), cfg).findings if f.code == code]


def jack(project, ring_net):
    """J8, a TRS jack: tip on a signal net from GP8, ring on `ring_net`, sleeve on ground."""
    project.save_part(JACK["lcsc"], JACK)
    g = project.graph()
    project.free_pins(g, "U1.11")
    g["graph"]["components"].append({"designator": "J8", "type": "connector", "lcsc": JACK["lcsc"], "bom": False,
                                     "pins": {"1": "T", "2": "R", "3": "S"}})
    g["graph"]["nets"].append({"name": "EXPR", "pins": ["J8.1", "U1.11"], "v": [0, 3.4]})
    project.net(g, ring_net)["pins"].append("J8.2")
    project.net(g, "GND")["pins"].append("J8.3")
    project.save_graph(g)


def test_a_supply_on_the_ring_of_a_jack(project):
    jack(project, "3V3")
    assert hints(project, "HINT.jack_supply") == ["J8"]


def test_a_jack_without_a_supply_is_left_alone(project):
    jack(project, "GND")
    assert hints(project, "HINT.jack_supply") == []


def relay(project, load_on_connector):
    """K8 switches +5V through its contact to LOAD; LOAD on the terminal J9 when load_on_connector, else on R9."""
    project.save_part(RELAY["lcsc"], RELAY)
    project.save_part(TERMINAL["lcsc"], TERMINAL)
    project.use_library_part("C17414")
    g = project.graph()
    g["graph"]["components"].append({"designator": "K8", "type": "relay", "lcsc": RELAY["lcsc"], "bom": False,
                                     "pins": {"1": "A1", "2": "A2", "3": "COM", "4": "NO"}})
    other = ({"designator": "J9", "type": "connector", "lcsc": TERMINAL["lcsc"], "bom": False,
              "pins": {"1": "1", "2": "2"}} if load_on_connector else
             {"designator": "R9", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}})
    g["graph"]["components"].append(other)
    near = other["designator"]
    project.net(g, "+5V")["pins"] += ["K8.1", "K8.3"]
    project.net(g, "GND")["pins"] += ["K8.2", f"{near}.2"]
    g["graph"]["nets"].append({"name": "LOAD", "pins": ["K8.4", f"{near}.1"], "v": [0, 5.5]})
    project.save_graph(g)


def test_relay_contacts_reaching_a_connector(project):
    relay(project, True)
    assert hints(project, "HINT.relay_load") == ["K8"]


def test_relay_contacts_on_the_board_are_left_alone(project):
    relay(project, False)
    assert hints(project, "HINT.relay_load") == []
