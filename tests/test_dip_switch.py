"""A DIP switch's number of positions (handbook 4.1): values.positions, read by the netlist (default 8) – a part with
more than eight positions simulates every one of them, and `edakit part lint` takes the value."""

import json
from pathlib import Path

import edakit
from edakit import schema
from edakit.design import Design
from edakit.sim import netlist
from edakit.sim import run as simrun

N = 10


def ten_position_switch():
    """A 10-position DIP switch entry: the library's C126848 with pins a1 … a10, b1 … b10."""
    data = json.loads((Path(edakit.__file__).parent / "parts" / "C126848.json").read_text())
    data.update(lcsc="C99010", mpn="DIP-10", package="DIP switch, 10 positions")
    data["pins"] = {str(i + (N if side == "b" else 0)): {"name": f"{side.upper()}{i}", "type": "passive",
                                                         "role": f"{side}{i}"}
                    for side in "ab" for i in range(1, N + 1)}
    data.setdefault("values", {})["positions"] = N
    return data


def test_part_lint_takes_the_number_of_positions():
    assert schema.problems(ten_position_switch()) == []
    for bad in (0, 2.5, "10", True):
        entry = ten_position_switch()
        entry["values"]["positions"] = bad
        assert schema.problems(entry) == [f"values.positions: the number of switches of the DIP switch, a whole "
                                          f"number ≥ 1, not {bad!r}"]


def test_every_position_of_a_ten_position_switch_is_simulated(project):
    project.save_part("C99010", ten_position_switch())
    g = project.graph()
    g["graph"]["components"].append({"designator": "SW9", "type": "dip_switch", "lcsc": "C99010",
                                     "pins": {str(i): f"{'A' if i <= N else 'B'}{(i - 1) % N + 1}"
                                              for i in range(1, 2 * N + 1)}})
    project.net(g, "3V3")["pins"].append("SW9.10")                    # a10
    project.net(g, "GND")["pins"].append("SW9.20")                    # b10
    project.save_graph(g)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    for load in sim["loads"].values():
        load["dip_closed"] = {"SW9": [N]}
    text, _ = netlist.build(Design.from_config(project.config()), sim, next(simrun.scenarios(sim)))
    assert f"R_SW9_{N} " in text
