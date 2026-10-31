"""A hand-wired board – [boards.<name>] wired = true (maker-coverage FT-2; rules-at-scale.md, decision 22): parts
with no PCB of their own, wired by hand – panel parts, jacks, pots, a strip on a cable. Like a bought board (`bought =
true`, test_bought.py) it is in the graph, the checks and the simulation, and nobody draws or assembles it: no
schematic, PCB or manufacturing files, no assembler's BOM, no PCB in the cost. What differs is what it is: a bought
board is one purchased assembly – a module with its own parts entry and supplier –, a hand-wired board's parts are
the project's, each ordered separately and fitted by hand. `bought = true` on such a board still works; a note
names the key that says what it is."""

import json
import shutil

import pytest
from test_bought import usb_board
from test_checks import run

from edakit import cli, cost
from edakit.design import Design
from edakit.release import gate
from edakit.sim import run as simrun

SKIPPED = "hand-wired board – no schematic, PCB or manufacturing files"
REFUSED = ("edakit: board panel is hand-wired (wired = true in edakit.toml [boards.panel]): no schematic, PCB or "
           "manufacturing files – edakit checks it with the graph and the simulation\n")


def panel(project, key="wired = true"):
    """The example's button SW1 on a front panel of its own: two wires of W2 (0.5 m of AWG 24) soldered to its lugs,
    to J3 on main (a JST PH like J1, bom: false), which joins BTN and GND."""
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + f'\n[boards.panel]\ntitle = "Front panel"\n{key}\n')
    g = project.graph()
    for c in g["graph"]["components"]:
        c["board"] = "main"
    project.comp(g, "SW1").update(board="panel", bom=False)
    g["graph"]["components"].append({"designator": "J3", "type": "connector", "lcsc": "C131337", "bom": False,
                                     "board": "main", "pins": {"1": "1", "2": "2"}})
    project.net(g, "BTN")["pins"].append("J3.1")
    project.net(g, "GND")["pins"].append("J3.2")
    g["graph"]["cables"] = [{"name": "W2", "from": "SW1", "to": "J3", "pins": {"1": "1", "3": "2"},
                             "length_m": 0.5, "awg": 24}]
    project.save_graph(g)
    return g


def cli_run(project, monkeypatch, *argv):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    return cli.main(list(argv))


# --- the checks and the simulation see it ----------------------------------------------------------------------------

def test_the_panel_is_checked_like_any_board(project):
    panel(project)
    rep = run(project)
    assert rep.errors == [] and not any(c == "STRUCT.board" for c, _ in rep.notes + rep.warnings)


def test_a_part_on_it_without_bom_false_is_struct_board(project):
    g = panel(project)
    project.comp(g, "SW1").pop("bom")
    project.save_graph(g)
    assert [m for c, m in run(project).errors if c == "STRUCT.board"] == [
        "SW1: on the hand-wired board panel – wired by hand, no assembler: bom: false"]


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_the_simulation_reads_the_button_through_the_wires(project):
    panel(project)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    out = simrun.run_all(Design.from_config(project.config()), sim)
    assert [c for c in out["checks"] if c["result"] == "fail"] == []
    assert "W2" in out["cable_currents"]


# --- nobody draws it ------------------------------------------------------------------------------------------------

def test_it_is_no_made_board(project):
    panel(project)
    cfg = project.config()
    assert list(cfg.made()) == ["main"] and cfg.board(made=True).name == "main"
    assert cfg.boards["panel"].wired and not cfg.boards["panel"].bought
    assert cfg.boards["panel"].unmade == "hand-wired" and cfg.boards["main"].unmade is None


@pytest.mark.parametrize("argv", [["pcb", "plan"], ["route", "dsn"], ["schematic", "check"], ["export"], ["cost"]])
def test_layout_commands_refuse_it_with_one_line(project, monkeypatch, capsys, argv):
    panel(project)
    capsys.readouterr()
    assert cli_run(project, monkeypatch, *argv, "--board", "panel") == 1
    assert capsys.readouterr().err == REFUSED


def test_the_gate_leaves_it_out_of_s_and_l(project, monkeypatch):
    from edakit import schematic
    panel(project)
    monkeypatch.setattr(schematic, "check", lambda cfg, args: 0)      # main's comparison: EasyEDA, not this test's
    rows = gate.stage_schematic(project.config(), project.root)
    assert {"stage": "S", "id": "SYNC.schematic", "item": "panel", "check": SKIPPED, "result": "info"} in rows
    before = gate.layout_files(project.config())
    assert before == [f for f in before if "panel" not in str(f)]


def test_the_protocol_names_it_hand_wired(project, monkeypatch):
    panel(project)
    usb_board(project)
    assert cli_run(project, monkeypatch, "gate") == 2
    text = (sorted((project.root / "build" / "release").iterdir())[-1] / "protocol.md").read_text()
    assert "; bought, not made: usb; hand-wired, not made: panel |" in text


# --- order and cost -------------------------------------------------------------------------------------------------

def test_order_writes_no_bom_for_it_and_puts_its_parts_in_the_carts(project, monkeypatch):
    panel(project)
    assert cli_run(project, monkeypatch, "order") == 0
    out = project.root / "build" / "edakit" / "order"
    assert not (out / "bom_panel.csv").exists() and (out / "bom_main.csv").exists()
    assert "C318884,5,TS-1187A-B-A-B: SW1 (5 + 0)" in (out / "cart_lcsc.csv").read_text().splitlines()
    hand = (out / "hand_assembly.md").read_text()
    assert "## Board panel (Front panel) – hand-wired, no PCB\n" in hand
    assert "| SW1 |" in hand.split("## Board panel")[1]


def test_cost_has_no_pcb_for_it(project):
    panel(project)
    assert list(cost.estimate(project.config())["boards"]) == ["main"]


# --- bought = true on a hand-wired panel: it still works, a note names the key ---------------------------------------

def test_bought_on_a_panel_works_and_a_note_names_the_key(project):
    panel(project, "bought = true")
    rep = run(project)
    assert rep.errors == []
    assert ("STRUCT.board", "[boards.panel]: bought = true, but no part on it is a bought module – a board of parts "
                            "wired by hand says so with wired = true (handbook 4.5)") in rep.notes
    assert list(project.config().made()) == ["main"]


def test_a_bought_breakout_gets_no_note(project):
    usb_board(project)
    assert not any(c == "STRUCT.board" for c, _ in run(project).notes)
