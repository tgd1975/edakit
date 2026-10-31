"""#82: a bought board on a cable – [boards.usb] bought = true: the USB-C breakout J9 (Soldered 333011, CC on solder
eyes, no resistors) wired by the cable W1 to J1 of the example. The graph checks and the simulation see it like any
board; nobody draws or assembles it, so the gate's stages S and L/F, the layout commands, the assembler's BOM and the
PCB cost leave it out. The origin is pytree (E-18, E-19): there the breakout stayed out of the graph and its missing
CC resistors were found by no check."""

import json
import shutil

import pytest
from test_checks import BREAKOUT, run

from edakit import cli, cost, pcb
from edakit.design import Design
from edakit.release import fab, gate
from edakit.sim import run as simrun

KEY = "bought = true"
SKIPPED = "bought board – no schematic, PCB or manufacturing files"


def usb_board(project, fixed=True):
    """The example with [boards.usb] bought; J9 on usb, only VUSB and GND wired, its CC eyes – fixed: R21, R22
    (5.1 kΩ, bom: false) from CC1 and CC2 to GND on usb; W1 J9 → J1; the simulation's source at J9."""
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + f'\n[boards.usb]\ntitle = "USB-C breakout"\n{KEY}\n')
    part = json.loads(json.dumps(BREAKOUT))
    part["values"] = {"usb_c": {"cc": "none", "source": "Soldered 333011 KiCad data V1.2.0: no CC resistors"}}
    part["order"] = {"berrybase": "SOL-333011"}
    project.save_part("333011", part)
    g = project.graph()
    for c in g["graph"]["components"]:
        c["board"] = "main"
    g["graph"]["components"].append({
        "designator": "J9", "type": "module", "part": "333011", "bom": False, "board": "usb",
        "pins": {k: v["name"] for k, v in part["pins"].items()}, "nc": ["3", "4", "5", "6"] + ([] if fixed else ["2", "7"]),
        "easyeda_device": {"name": "333011"}})
    project.net(g, "VIN")["pins"].append("J9.8")
    project.net(g, "GND")["pins"].append("J9.1")
    if fixed:
        project.use_library_part("C27834")
        for r, cc, pin in (("R21", "CC1", "7"), ("R22", "CC2", "2")):
            g["graph"]["components"].append({"designator": r, "type": "resistor", "lcsc": "C27834", "value": "5.1k",
                                             "board": "usb", "bom": False, "pins": {"1": "1", "2": "2"}})
            g["graph"]["nets"].append({"name": cc, "pins": [f"J9.{pin}", f"{r}.1"], "v": [0, 5.5]})
            project.net(g, "GND")["pins"].append(f"{r}.2")
    g["graph"]["cables"] = [{"name": "W1", "from": "J9", "to": "J1", "pins": {"8": "1", "1": "2"},
                             "r_ohm_per_wire": 0.065}]
    project.comp(g, "J1").pop("source")             # the supply comes from USB-C now, W1 is soldered to the breakout
    project.save_graph(g)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["sources"] = {"J9": {**sim["sources"].pop("J1"), "plus": "8", "minus": "1"}}
    sim["supplies"] = {name: {"J9": v["J1"]} for name, v in sim["supplies"].items()}
    (project.root / "hardware" / "sim.json").write_text(json.dumps(sim, indent=1))
    return g


def cli_run(project, monkeypatch, *argv):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    return cli.main(list(argv))


def found(project, check):
    return [m for c, m in run(project).errors if c == check]


# --- checks and simulation: they see the bought board ----------------------------------------------------------------

def test_g14_finds_the_missing_cc_resistors_on_the_bought_board(project):
    usb_board(project, fixed=False)
    assert found(project, "REQ.missing") == [
        "J9: CC1 not connected – a USB-C source switches VBUS on only with 5.1 kΩ to GND on each CC pin",
        "J9: CC2 not connected – a USB-C source switches VBUS on only with 5.1 kΩ to GND on each CC pin"]


def test_with_the_two_resistors_the_graph_is_clean(project):
    usb_board(project)
    assert run(project).errors == []


def test_a_part_on_a_bought_board_without_bom_false_is_g1(project):
    g = usb_board(project)
    project.comp(g, "R21")["bom"] = True
    project.save_graph(g)
    assert found(project, "STRUCT.board") == ["R21: on the bought board usb – nobody assembles it: bom: false"]


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_the_simulation_feeds_the_supply_at_the_breakout_through_w1(project):
    from edakit.sim import netlist
    usb_board(project)
    cfg = project.config()
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    out = simrun.run_all(Design.from_config(cfg), sim)
    assert [c for c in out["checks"] if c["result"] == "fail"] == []
    text, _ = netlist.build(Design.from_config(cfg), sim, next(simrun.scenarios(sim)))
    assert any(line.startswith("R_W1_8 ") for line in text.splitlines())


# --- the gate: stages S and L/F for made boards only -----------------------------------------------------------------

def test_the_gate_makes_only_the_made_boards(project, monkeypatch):
    usb_board(project)
    called = {"schematic": [], "fab": [], "layers": []}

    def schematic_check(cfg, args):
        called["schematic"].append(args.board)
        return 0

    def fab_run(cfg, board, out, offline=False, verbose=False):
        called["fab"].append(board.name)
        for pattern in gate.UPLOAD:
            f = out / board.name / pattern.format(b=board.name)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(board.name)
        return []

    def fab_layers(d, board):
        called["layers"].append(board)
        return {f"{board}.gbr": "0"}
    from edakit import schematic
    from edakit.release import fab
    monkeypatch.setattr(schematic, "check", schematic_check)
    monkeypatch.setattr(fab, "run", fab_run)
    monkeypatch.setattr(fab, "fab_layers", fab_layers)
    assert cli_run(project, monkeypatch, "gate", "--easyeda") == 2            # M-1, M-5, M-6 open, as in the example
    assert called == {"schematic": ["main"], "fab": ["main"], "layers": ["main"]}
    runs = sorted((project.root / "build" / "release").iterdir())
    manifest = json.loads((runs[-1] / "fab" / "manifest.json").read_text())
    assert sorted(manifest["files"]) == [f"fab/main/{p.format(b='main')}" for p in sorted(gate.UPLOAD)]
    assert list(manifest["fab_layers"]) == ["main"]
    text = (runs[-1] / "protocol.md").read_text()
    assert "boards main in EasyEDA project led-bar; bought, not made: usb |" in text
    other = text.split("## 8 Other stages")[1].split("\n## ")[0]
    assert f"| S | SYNC.schematic | usb | {SKIPPED} |  |  | information |" in other
    assert f"| L | L | usb | {SKIPPED} |  |  | information |" in other
    assert "| F | FILES.manifest | main |" in other and "| F | FILES.manifest | usb |" not in other


def test_parts_on_the_bought_board_need_no_row_in_the_plan(project):
    """SYNC.plan wants a row in [place] for every part the graph puts on a made board. J9 and its two resistors are on the
    bought board – off the made board, at the far end of the cable W1: no row, and the auto-layout's write-back and the
    takeover give them none."""
    usb_board(project)
    cfg = project.config()
    design = Design.from_config(cfg)
    rows = fab.Rows()
    fab.check_rows(cfg.board("main"), design, rows)
    assert [(r["id"], r["result"], r["actual"]) for r in rows] == [("SYNC.plan", "pass", "17 parts, each with a row")]
    pcb_parts = [{"designator": r, "x": 0, "y": 0, "rotation": 0, "layer": 1} for r in ("J9", "R21", "R22")]
    assert pcb.eda_rows(cfg.board("main"), design, pcb_parts, auto=True) == ({}, [])


def test_the_layout_hash_covers_the_made_boards_only(project):
    before = gate.layout_files(project.config())
    usb_board(project)
    assert gate.layout_files(project.config()) == before


# --- the commands that make or read a layout --------------------------------------------------------------------------

@pytest.mark.parametrize("argv", [["pcb", "plan"], ["pcb", "takeover"], ["route", "dsn"], ["silk", "preview"],
                                  ["schematic", "draw"],
                                  ["schematic", "check"], ["fab", "--out", "x", "--offline"], ["handover"],
                                  ["export"], ["cost"]])
def test_layout_commands_refuse_the_bought_board_with_one_line(project, monkeypatch, capsys, argv):
    usb_board(project)
    capsys.readouterr()
    assert cli_run(project, monkeypatch, *argv, "--board", "usb") == 1
    err = capsys.readouterr().err
    assert err == ("edakit: board usb is bought (bought = true in edakit.toml [boards.usb]): no schematic, PCB or "
                   "manufacturing files – edakit checks it with the graph and the simulation\n")


def test_over_all_boards_they_skip_it(project, monkeypatch, capsys):
    usb_board(project)
    assert project.config().board(made=True).name == "main"      # no --board: the one made board, not "several boards"
    capsys.readouterr()
    assert cli_run(project, monkeypatch, "handover") == 0
    out = capsys.readouterr().out
    assert "board main – the plan keeps this" in out and "board usb" not in out


# --- order and cost ---------------------------------------------------------------------------------------------------

def test_order_writes_no_bom_for_it_and_keeps_its_parts(project, monkeypatch, capsys):
    usb_board(project)
    assert cli_run(project, monkeypatch, "order") == 0
    out = project.root / "build" / "edakit" / "order"
    assert sorted(f.name for f in out.iterdir()) == ["bom_main.csv", "cart_berrybase.csv", "cart_lcsc.csv",
                                                     "hand_assembly.md"]
    assert "SOL-333011,5,333011,J9" in (out / "cart_berrybase.csv").read_text()
    assert "C27834,10," in (out / "cart_lcsc.csv").read_text()
    hand = (out / "hand_assembly.md").read_text()
    assert "## Board usb (USB-C breakout) – bought, nobody assembles it\n" in hand
    assert all(f"| {d} |" in hand.split("## Board usb")[1] for d in ("J9", "R21", "R22"))


def test_cost_has_no_pcb_and_no_assembly_for_it(project):
    usb_board(project)
    assert list(cost.estimate(project.config())["boards"]) == ["main"]


# --- cables with length and gauge (maker-coverage FT-2) ---------------------------------------------------------------

def test_wire_resistance_from_length_and_gauge():
    from edakit.circuit import cable_problems, wire_h, wire_mm2, wire_ohm
    assert round(wire_mm2({"awg": 24}), 4) == 0.2047                  # d = 0.511 mm
    assert round(wire_ohm({"length_m": 1, "awg": 24}), 4) == 0.0840
    assert round(wire_ohm({"length_m": 2, "mm2": 0.5}), 4) == 0.0688
    assert wire_ohm({"r_ohm_per_wire": 0.2}) == 0.2 and wire_ohm({}) == 0.05
    assert wire_h({"length_m": 2, "l_nh_per_m": 600}) == pytest.approx(1.2e-6)
    assert cable_problems({"name": "W1", "length_m": 2, "awg": 24, "l_nh_per_m": 600}) == []
    assert cable_problems({"length_m": 2}) == ["length_m needs the wire's awg or mm2"]
    assert cable_problems({"awg": 24}) == ["awg needs the cable's length_m"]
    assert cable_problems({"length_m": 1, "awg": 24, "mm2": 0.2}) == ["awg or mm2, not both"]
    assert cable_problems({"r_ohm_per_wire": 0.1, "length_m": 1, "awg": 24}) == [
        "r_ohm_per_wire or length_m with awg or mm2, not both"]
    assert cable_problems({"awg": 50, "length_m": 1, "colour": "red"})[:2] == [
        "unknown key 'colour' (known: about, at_m, awg, c_pf_per_m, i_max_a, l_nh_per_m, length_m, mm2, notes, r_ohm_per_wire)",
        "awg must be a gauge from 0 to 40, not 50"]


def test_a_cable_without_its_gauge_is_a_finding(project):
    g = usb_board(project)
    g["graph"]["cables"][0] = {**g["graph"]["cables"][0], "length_m": 2}
    g["graph"]["cables"][0].pop("r_ohm_per_wire")
    project.save_graph(g)
    assert found(project, "STRUCT.net") == ["cable W1: length_m needs the wire's awg or mm2"]


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_a_long_thin_cable_drops_the_supply(project):
    """W1 as 2 m of AWG 28 (0.42 Ω per wire) instead of 65 mΩ: +5V falls by the drop over both wires; with
    l_nh_per_m the wires are an inductance as well."""
    from edakit.sim import netlist
    g = usb_board(project)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())

    def plus5():
        out = simrun.run_all(Design.from_config(project.config()), sim)
        return next(s for s in out["scenarios"] if s["name"].endswith("all_on/vf-max"))["nets"]["+5V"]
    short = plus5()
    cable = {k: v for k, v in g["graph"]["cables"][0].items() if k != "r_ohm_per_wire"}
    g["graph"]["cables"][0] = {**cable, "length_m": 2, "awg": 28, "l_nh_per_m": 600}
    project.save_graph(g)
    long = plus5()
    assert 0.02 < short - long < 0.2
    text, _ = netlist.build(Design.from_config(project.config()), sim, next(simrun.scenarios(sim)))
    lines = text.splitlines()
    assert any(line.startswith("R_W1_8 ") and line.endswith(" 0.42482") for line in lines)
    assert any(line.startswith("L_W1_8 ") and line.endswith(" 1.2e-06") for line in lines)
