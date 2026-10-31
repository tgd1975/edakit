"""REQ.missing/leave for a connector whose wires leave the board without a cable in the graph (maker-coverage CK-16):
the component key off_board."""

from edakit import engines, profile
from edakit.design import Design

# values for the tests, not from datasheets
TERMINAL = {"lcsc": "C9000603", "mpn": "test terminal", "kind": "connector", "verified": {"by": "test"},
            "limits": {"v_max_v": 30, "i_max_a": 5},
            "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}}}


def terminal(project, off_board=True, series=False):
    """J8, a two-pole terminal: pin 1 on FOOT – from GP8 (U1.11), directly or through R8 –, pin 2 on ground."""
    project.save_part(TERMINAL["lcsc"], TERMINAL)
    project.use_library_part("C17414")
    g = project.graph()
    project.free_pins(g, "U1.11")
    comp = {"designator": "J8", "type": "connector", "lcsc": TERMINAL["lcsc"], "bom": False, "pins": {"1": "1", "2": "2"}}
    if off_board:
        comp["off_board"] = True
    g["graph"]["components"].append(comp)
    project.net(g, "GND")["pins"].append("J8.2")
    if series:
        g["graph"]["components"].append({"designator": "R8", "type": "resistor", "lcsc": "C17414", "value": "10k",
                                         "pins": {"1": "1", "2": "2"}})
        g["graph"]["nets"] += [{"name": "FOOT", "pins": ["J8.1", "R8.1"], "v": [0, 3.4]},
                               {"name": "FOOT_IN", "pins": ["R8.2", "U1.11"], "v": [0, 3.4]}]
    else:
        g["graph"]["nets"].append({"name": "FOOT", "pins": ["J8.1", "U1.11"], "v": [0, 3.4]})
    project.save_graph(g)


def leave(project):
    cfg = project.config()
    return [f.text for f in engines.run(Design.from_config(cfg), cfg).findings
            if f.code == "REQ.missing" and f.grade == "leave"]


def test_a_pin_straight_on_an_off_board_connector(project):
    terminal(project)
    assert "cables" in profile.suggested(Design.from_config(project.config()))
    assert leave(project) == ["FOOT: runs to the off-board connector J8 straight to U1.11 – no series resistance on the "
                              "board"]


def test_a_series_resistor_on_the_board(project):
    terminal(project, series=True)
    assert leave(project) == []


def test_a_connector_not_marked_is_left_alone(project):
    terminal(project, off_board=False)
    assert leave(project) == []
