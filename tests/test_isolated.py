"""A net isolated from the board's ground (net key isolated, handbook 3): its declared range is its own loop's – a
MIDI-in current loop, the far side of an optocoupler or a digital isolator. Pins there are held to that range only
where their part has a ground pin on the isolated side; the simulation does not compare such a net with the board's
ground."""

import shutil

import pytest

from edakit.design import Design
from edakit.engines.limits import judge_all
from edakit.engines.quantities import pin_voltages
from edakit.sim import run as simrun

ISO = {"kind": "ic", "mpn": "ISO-TEST", "verified": {"by": "test"},
       "pins": {"1": {"name": "A", "type": "input", "v_max_v": 5.5}, "2": {"name": "GND1", "type": "ground"},
                "3": {"name": "Y", "type": "output", "v_max_v": 5.5}, "4": {"name": "GND2", "type": "ground"}}}


def design(isolated, gnd1):
    """ISO-TEST U1: A on a 24 V loop, Y on 3V3, GND2 on the board's ground; GND1 on the board's or the loop's ground."""
    nets = [{"name": "LOOP", "pins": ["U1.1"], "v": [0, 24]},
            {"name": "Y", "pins": ["U1.3"], "v": [0, 3.4]},
            {"name": "GND", "pins": ["U1.4"] + (["U1.2"] if gnd1 == "board" else []), "v": [0, 0]}]
    if gnd1 == "loop":
        nets.append({"name": "LOOP_GND", "pins": ["U1.2"], "v": [0, 0], "isolated": True})
    if isolated:
        nets[0]["isolated"] = True
    graph = {"name": "t", "version": "1", "ground": "GND", "nets": nets,
             "components": [{"designator": "U1", "type": "ic", "part": "ISO-TEST",
                             "pins": {"1": "A", "2": "GND1", "3": "Y", "4": "GND2"}}]}
    return Design.from_data(graph, {"ISO-TEST": ISO})


def on_a(d):
    return [f.text for f in judge_all(d, pin_voltages(d)) if f.place == "U1.1"]


def test_a_pin_on_an_isolated_net_is_held_to_it_only_against_its_own_side():
    assert on_a(design(isolated=False, gnd1="board")) == ["LOOP up to 24 V, but U1.1 (A) allows 5.5 V"]
    assert on_a(design(isolated=True, gnd1="board")) == []          # an optocoupler's LED: no reference on the loop
    assert on_a(design(isolated=True, gnd1="loop")) == ["LOOP up to 24 V, but U1.1 (A) allows 5.5 V"]


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_the_simulation_does_not_hold_an_isolated_net_to_the_boards_ground(project):
    """Two loop nets declared 5–10 V against their own reference: floating against the board's ground they would read
    0 V and fail LIM.declared; isolated, they are not compared."""
    import json
    project.save_part("C17414", json.loads((project.root / "hardware" / "parts" / "C17414.json").read_text()))
    g = project.graph()
    g["graph"]["components"].append({"designator": "R9", "type": "resistor", "lcsc": "C17414", "board": "main",
                                     "pins": {"1": "1", "2": "2"}})
    g["graph"]["nets"] += [{"name": "LOOP_A", "pins": ["R9.1"], "v": [5, 10]},
                           {"name": "LOOP_B", "pins": ["R9.2"], "v": [5, 10]}]
    project.save_graph(g)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())

    def declared():
        out = simrun.run_all(Design.from_config(project.config()), sim)
        return {c["item"] for c in out["checks"] if c["id"] == "LIM.declared" and c["result"] == "fail"}
    assert {"LOOP_A", "LOOP_B"} <= declared()
    for n in g["graph"]["nets"]:
        if n["name"].startswith("LOOP_"):
            n["isolated"] = True
    project.save_graph(g)
    assert not {"LOOP_A", "LOOP_B"} & declared()
