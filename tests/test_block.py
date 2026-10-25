"""Building blocks: every library block is consistent, and once in a graph it passes the checks."""

import json
import shutil

import pytest

from edakit import block, checks, rules
from edakit.design import Design
from edakit.sim import run as simrun

# where each block goes in the example: two free MCU pins become the nets SIG and SIG2
CONNECT = {
    "led": {"in": "SIG"},
    "button": {"in": "SIG", "vcc": "3V3"},
    "i2c-pullups": {"sda": "SIG", "scl": "SIG2", "vcc": "3V3"},
    "npn-switch": {"in": "SIG", "vplus": "+5V"},
    "power-input-jst": {"out": "+5V"},
    "reverse-pmos": {"in": "VIN", "out": "+5V"},
    "usb-c-sink": {"vbus": "+5V"},
}


def signals(project, names=("SIG", "SIG2")):
    """Nets SIG (GP7) and SIG2 (GP8) with one MCU pin each, for the blocks to connect to."""
    g = project.graph()
    for name, ref in (("SIG", "U1.10"), ("SIG2", "U1.11")):
        if name in names:
            project.free_pins(g, ref)
            g["graph"]["nets"].append({"name": name, "pins": [ref], "v": [0, 3.4]})
    project.save_graph(g)


def errors(project):
    cfg = project.config()
    return checks.run(Design.from_config(cfg), cfg).errors


def test_every_block_is_in_this_test():
    assert set(block.library()) == set(CONNECT)


@pytest.mark.parametrize("name", sorted(CONNECT))
def test_library_block_is_consistent(name):
    b = block.load(name)
    comps = {c["designator"]: c for c in b["components"]}
    assert len(comps) == len(b["components"])
    nets = {n["name"]: n for n in b["nets"]}
    assert set(b["ports"]) <= set(nets)
    used = [ref for n in b["nets"] for ref in n["pins"]]
    assert len(used) == len(set(used))
    for des, c in comps.items():
        part = block.library_part(c["lcsc"])
        assert part and part.get("verified"), c["lcsc"]
        assert c["pins"] == {k: v["name"] for k, v in part["pins"].items()}, des
        for pin in c["pins"]:
            assert (f"{des}.{pin}" in used) != (pin in c.get("nc", [])), f"{des}.{pin}"
    for name_, n in nets.items():
        assert name_ in b["ports"] or "v" in n, name_
    assert all(rules.entry(cid) for cid in b.get("covers", []))


@pytest.mark.parametrize("name", sorted(CONNECT))
def test_block_in_the_example_passes_the_checks(project, name):
    signals(project, set(CONNECT[name].values()))
    block.add(project.config(), name, "T", CONNECT[name])
    assert errors(project) == []


def test_designators_continue_and_nets_get_the_instance_name(project):
    signals(project)
    _, comps, new_nets, extended, _, copy, _ = block.add(project.config(), "led", "STATUS", {"in": "SIG"})
    assert [c["designator"] for c in comps] == ["R3", "D10"]
    assert comps[0]["label"] == "STATUS: LED series resistor" and "(block led, STATUS)" in comps[0]["notes"]
    assert new_nets == [{"name": "STATUS_ANODE", "pins": ["R3.2", "D10.1"], "v": [0, 3.4]}]   # "@in": the range of SIG
    assert extended == {"SIG": ["R3.1"], "GND": ["D10.2"]} and copy == ["C17630"]
    assert (project.root / "hardware" / "parts" / "C17630.json").exists()


def test_port_without_connect_becomes_a_net(project):
    signals(project)
    block.add(project.config(), "npn-switch", "BUZ", {"in": "SIG", "vplus": "+5V"})
    g = project.graph()
    assert project.net(g, "BUZ_LOAD") == {"name": "BUZ_LOAD", "pins": ["Q1.3", "D10.2"], "v": [0, 5.5]}


def test_block_marks_its_nets(project):
    signals(project)
    block.add(project.config(), "i2c-pullups", "I2C", {"sda": "SIG", "scl": "SIG2", "vcc": "3V3"})
    g = project.graph()
    assert project.net(g, "SIG")["bus"] == "i2c"
    part = project.part("C17673")
    part["params"]["value_ohm"] = 47000
    project.save_part("C17673", part)
    assert any(c == "G-11" for c, _ in errors(project))   # the mark makes G-11 check GPIO nets


def test_dry_run_writes_nothing(project):
    signals(project)
    before = project.graph_file.read_text()
    block.add(project.config(), "usb-c-sink", "USB", {"vbus": "+5V"}, dry_run=True)
    assert project.graph_file.read_text() == before
    assert not (project.root / "hardware" / "parts" / "C456012.json").exists()


def test_graph_keeps_its_formatting(project):
    signals(project)
    data = project.graph()
    project.graph_file.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    block.add(project.config(), "led", "S", {"in": "SIG"})
    text = project.graph_file.read_text(encoding="utf-8")
    assert text.startswith('{\n "graph"') and "22 µF" in text


def test_mistakes_are_refused(project):
    signals(project)
    cfg = project.config()
    for args, words in ((("led", "S", {"out": "SIG"}), "no port out"),
                        (("led", "S", {"in": "NOPE"}), "does not exist"),
                        (("led", "S-1", {"in": "SIG"}), "--as"),
                        (("nope", "S", {}), "no block")):
        with pytest.raises(block.BlockError, match=words):
            block.add(cfg, *args)
    part = project.part("C2297")          # the project's own entry of the LED has other pin names
    part["pins"]["1"]["name"] = "+"
    project.save_part("C2297", part)
    with pytest.raises(block.BlockError, match="differ from the parts entry"):
        block.add(cfg, "led", "S", {"in": "SIG"})


def test_several_boards_need_a_board(project):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("[boards.main.outline]", "[boards.second]\n\n[boards.main.outline]", 1))
    g = project.graph()
    for c in g["graph"]["components"]:
        c["board"] = "main"
    project.save_graph(g)
    signals(project)
    with pytest.raises(block.BlockError, match="--board"):
        block.add(project.config(), "led", "S", {"in": "SIG"})
    _, comps, *_ = block.add(project.config(), "led", "S", {"in": "SIG"}, board="main")
    assert {c["board"] for c in comps} == {"main"}


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
@pytest.mark.parametrize("name", sorted(CONNECT))
def test_block_in_the_example_passes_the_simulation(project, name):
    signals(project, set(CONNECT[name].values()))
    block.add(project.config(), name, "T", CONNECT[name])
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    out = simrun.run_all(Design.from_config(project.config()), sim)
    assert [c for c in out["checks"] if c["result"] == "fail"] == []


def test_made_up_net_names_do_not_join_existing_nets(project):
    signals(project)
    block.add(project.config(), "npn-switch", "BUZ", {"in": "SIG", "vplus": "+5V"})   # creates BUZ_LOAD, BUZ_BASE
    with pytest.raises(block.BlockError, match="BUZ_BASE, BUZ_LOAD exists already"):
        block.add(project.config(), "npn-switch", "BUZ", {"in": "SIG2", "vplus": "+5V"})
