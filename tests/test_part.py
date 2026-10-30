"""Own parts: a board of another edakit project as a part – its datasheet, the copy in the host project, SYNC.source, and the
supply range the simulation holds it to (SIM.state)."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from helpers import check, executed

from edakit import checks, cli, config, part
from edakit.design import Design
from edakit.release import gate
from edakit.sim import run as simrun

EXAMPLE = Path(__file__).resolve().parent / "fixtures" / "led-bar"
pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def board(tmp_path):
    """The own board: a copy of the example as the project "ring", committed in a git repository of its own."""
    dst = tmp_path / "ring"
    shutil.copytree(EXAMPLE, dst, ignore=shutil.ignore_patterns("build"))
    toml = dst / "edakit.toml"
    toml.write_text(toml.read_text().replace('name = "led-bar"', 'name = "ring"'))
    git(dst, "init", "-q")
    git(dst, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "start")
    commit(dst)
    return dst


def commit(root):
    git(root, "add", "-A")
    git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "change")


def cfg_of(root):
    return config.load(root / "edakit.toml")


def export(board, connectors=("J1",)):
    part.write_datasheet(cfg_of(board), list(connectors))
    commit(board)


def use_own(project, net="+5V", name="ring"):
    """M1, the own board, on the host's net `net` and GND – with its capacitor C9, as for any supply pin (REQ.missing)."""
    g = project.graph()
    g["graph"]["components"] += [
        {"designator": "M1", "type": "module", "label": "own board", "part": name, "bom": False,
         "pins": {"1": "VIN", "2": "GND"}, "easyeda_device": {"name": "ring", "uuid": "u1", "libraryUuid": "l1"}},
        {"designator": "C9", "type": "capacitor", "lcsc": "C45783", "value": "22uF", "pins": {"1": "1", "2": "2"}}]
    project.net(g, net)["pins"] += ["M1.1", "C9.1"]
    project.net(g, "GND")["pins"] += ["M1.2", "C9.2"]
    project.save_graph(g)


def run_checks(root):
    cfg = cfg_of(root)
    return check(Design.from_config(cfg), cfg)


def p3(rep):
    return ([m for c, m in rep.errors if c == "SYNC.source"], [m for c, m in rep.pending if c == "SYNC.source"],
            [m for c, m in rep.warnings if c == "SYNC.source"], [m for c, m in rep.notes if c == "SYNC.source"])


# --- the datasheet of the board ------------------------------------------------------------------------------------

def test_datasheet_of_the_example(board):
    cfg = cfg_of(board)
    entry, md = part.datasheet(cfg, ["J1"])
    assert entry["mpn"] == "ring" and entry["kind"] == "module"
    assert entry["pins"]["1"] == {"name": "VIN", "type": "power_in", "role": "vin", "from": "J1.1"}
    assert entry["pins"]["2"] == {"name": "GND", "type": "ground", "role": "gnd", "from": "J1.2"}
    # the supply current and the voltage at the connector over the board's own scenarios
    sim = json.loads(cfg.sim_config.read_text())
    out = simrun.run_all(Design.from_config(cfg), {**sim, "report": ["VIN", "GND"]})
    i_max = max(s["sources"]["J1"] for s in out["scenarios"])
    volts = [s["nets"]["VIN"] - s["nets"]["GND"] for s in out["scenarios"]]
    assert entry["values"] == {"behavior": "current", "i_a": round(i_max, 4)}
    assert entry["limits"] == {"vin_min_v": round(min(volts), 3), "vin_max_v": round(max(volts), 3)}
    assert 4.5 < entry["limits"]["vin_min_v"] < 4.75 <= 5.0 < entry["limits"]["vin_max_v"] <= 5.25
    assert entry["own"]["what"] == "pcb" and entry["own"]["connectors"] == ["J1"]
    assert entry["own"]["state_sha256"] == gate.file_hash(cfg.root, gate.state_files(cfg))
    assert entry["verified"] is None and "rohs" in entry["compliance"]
    assert "| 1 | VIN | power_in | vin |" in md and "J1" in md and f"{i_max * 1e3:.0f} mA" in md


def test_datasheet_states_the_radio_of_the_board(board):
    """PARTS.fact (#23): the board states "none" when none of its parts transmits and its modules and microcontrollers say
    so; the radios of its parts when they transmit; nothing – not known – while a module states nothing."""
    cfg = cfg_of(board)
    assert part.datasheet(cfg, ["J1"])[0]["compliance"]["radio"] == "none"      # the Pico 2: "none"
    pico = board / "hardware/parts/C41407547.json"
    entry = json.loads(pico.read_text())
    entry["compliance"] = {"radio": {"bands_mhz": [[2412, 2472]], "max_dbm": 20, "antenna_dbi": 0}}
    pico.write_text(json.dumps(entry))
    data, md = part.datasheet(cfg, ["J1"])
    assert data["compliance"]["radio"] == {"part": "U1", "bands_mhz": [[2412, 2472]], "max_dbm": 20, "antenna_dbi": 0}
    assert "- radio: U1 [[2412, 2472]] MHz, 20 dBm" in md
    del entry["compliance"]
    pico.write_text(json.dumps(entry))
    data, md = part.datasheet(cfg, ["J1"])
    assert "radio" not in data["compliance"]
    assert "- radio: not stated by every module and microcontroller of the board" in md


def test_datasheet_reads_pull_ups_and_signals(board):
    """A second connector J2 with SDA: its pins follow those of J1, the type comes from the board's parts, the
    pull-up from its resistors, the limit from the MCU pin."""
    g = json.loads((board / "hardware/graph.json").read_text())
    comps = {c["designator"]: c for c in g["graph"]["components"]}
    nets = {n["name"]: n for n in g["graph"]["nets"]}
    g["graph"]["components"] += [
        {**comps["J1"], "designator": "J2", "label": "I2C out"},
        {"designator": "R9", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}}]
    comps["U1"]["nc"].remove("10")
    g["graph"]["nets"].append({"name": "SDA", "pins": ["J2.1", "U1.10", "R9.1"], "v": [0, 3.4]})
    nets["3V3"]["pins"].append("R9.2")
    nets["GND"]["pins"].append("J2.2")
    (board / "hardware/graph.json").write_text(json.dumps(g, indent=1))
    entry, md = part.datasheet(cfg_of(board), ["J1", "J2"])
    assert [(n, p["name"], p["from"]) for n, p in entry["pins"].items()] == [
        ("1", "VIN", "J1.1"), ("2", "GND", "J1.2"), ("3", "SDA", "J2.1"), ("4", "GND", "J2.2")]
    sda = entry["pins"]["3"]
    assert sda["role"] == "sda" and sda["type"] == "bidirectional"
    assert sda["pull"] == "up" and sda["pull_ohm"] == 10000.0
    assert sda["v_max_v"] == 3.63                                             # the Pico's GPIO limit
    assert "| 3 | SDA | bidirectional | sda | 3.63 | up 10 kΩ |" in md


def test_datasheet_needs_a_connector_with_the_supply(board):
    with pytest.raises(part.PartError, match="J9: not in the graph"):
        part.datasheet(cfg_of(board), ["J9"])
    with pytest.raises(part.PartError, match="U1: not a connector"):
        part.datasheet(cfg_of(board), ["U1"])
    sim = json.loads((board / "hardware/sim.json").read_text())
    sim["sources"]["J2"] = sim["sources"].pop("J1")
    (board / "hardware/sim.json").write_text(json.dumps(sim))
    with pytest.raises(part.PartError, match="no source of the simulation"):
        part.datasheet(cfg_of(board), ["J1"])


def test_datasheet_renews_what_was_exported(board):
    cfg = cfg_of(board)
    json_file, md_file = part.write_datasheet(cfg, ["J1"], "ring-v1")
    assert json_file == board / "hardware/datasheet/ring-v1.json" and md_file.exists()
    g = json.loads((board / "hardware/graph.json").read_text())
    g["graph"]["version"] = "1.1"
    (board / "hardware/graph.json").write_text(json.dumps(g, indent=1))
    assert part.renew_datasheets(cfg_of(board)) == [json_file]
    entry = json.loads(json_file.read_text())
    assert entry["own"]["connectors"] == ["J1"] and entry["mpn"] == "ring-v1"
    assert entry["own"]["state_sha256"] == part.state_hash(cfg_of(board))


def test_stale_datasheet_in_the_board_project(board):
    export(board)
    assert p3(run_checks(board)) == ([], [], [], [])
    g = json.loads((board / "hardware/graph.json").read_text())
    g["graph"]["nets"][0]["v"] = [0, 5.6]
    (board / "hardware/graph.json").write_text(json.dumps(g, indent=1))
    pending = p3(run_checks(board))[1]
    assert len(pending) == 1 and pending[0].startswith("ring: datasheet export of an older state")


# --- the copy in the host project --------------------------------------------------------------------------------

def test_own_copies_the_datasheet(project, board):
    export(board)
    path, entry, _ = part.own(project.config(), board)
    assert path == project.root / "hardware/parts/ring.json"
    assert entry["own"]["path"] == "../ring" and entry["own"]["commit"] == git(board, "rev-parse", "HEAD")
    assert entry["own"]["released"] is None
    assert entry["datasheet"]["url"] == "../ring/hardware/datasheet/ring.md"
    use_own(project)
    rep = run_checks(project.root)
    assert not rep.errors
    errors, pending, warnings, _ = p3(rep)
    assert not errors and not pending
    assert warnings == ["M1 ring: ../ring is not released at the state of its datasheet – release it (edakit gate) "
                        "and renew with edakit part own ../ring, or accept the warning in the sign-off file"]


def test_own_takes_the_release_of_the_board(project, board):
    export(board)
    run = board / "build/release/20261102-120000/fab"
    run.mkdir(parents=True)
    (run / "manifest.json").write_text(json.dumps({"released": True, "decision": "RELEASED", "time": "2026-11-02",
                                                   "git": "abc1234", "state_sha256": part.state_hash(cfg_of(board))}))
    _, entry, _ = part.own(project.config(), board)
    assert entry["own"]["released"] == {"time": "2026-11-02", "git": "abc1234"}
    use_own(project)
    assert p3(run_checks(project.root)) == ([], [], [], [])


def test_own_refuses_a_stale_datasheet(project, board):
    export(board)
    (board / "hardware/sim.json").write_text((board / "hardware/sim.json").read_text().replace("0.3", "0.25", 1))
    with pytest.raises(part.PartError, match="older state"):
        part.own(project.config(), board)


def test_host_sees_the_board_change(project, board):
    export(board)
    part.own(project.config(), board)
    use_own(project)
    g = json.loads((board / "hardware/graph.json").read_text())
    g["graph"]["nets"][0]["v"] = [0, 5.6]
    (board / "hardware/graph.json").write_text(json.dumps(g, indent=1))
    pending = p3(run_checks(project.root))[1]
    assert pending == ["M1 ring: ../ring has changed since its datasheet – edakit part datasheet there, then edakit "
                       "part own ../ring"]


def test_host_sees_a_copy_from_uncommitted_changes(project, board):
    part.write_datasheet(cfg_of(board), ["J1"])           # not committed
    _, entry, _ = part.own(project.config(), board)
    assert entry["own"]["commit"].endswith(" + uncommitted changes")
    use_own(project)
    pending = p3(run_checks(project.root))[1]
    assert pending == ["M1 ring: copied from uncommitted changes in ../ring – commit there and renew with edakit part "
                       "own ../ring"]


def test_host_without_the_board_project(project, board):
    export(board)
    part.own(project.config(), board)
    use_own(project)
    shutil.rmtree(board)
    errors, pending, _, notes = p3(run_checks(project.root))
    assert not errors and not pending
    assert notes == ["M1 ring: ../ring not found – the copy is not compared with its source"]


def test_own_part_needs_its_source(project, board):
    export(board)
    path, entry, _ = part.own(project.config(), board)
    del entry["own"]["commit"]
    path.write_text(json.dumps(entry))
    use_own(project)
    assert p3(run_checks(project.root))[0] == ["M1 ring: own part without own.commit – edakit part own"]


def test_renewing_keeps_the_sign_off_of_the_same_state(project, board):
    export(board)
    path, entry, _ = part.own(project.config(), board)
    entry["verified"] = {"by": "t", "date": "2026-11-02", "datasheet": "ring@" + entry["own"]["commit"][:7]}
    path.write_text(json.dumps(entry))
    assert part.own(project.config(), board)[1]["verified"]["by"] == "t"
    g = json.loads((board / "hardware/graph.json").read_text())
    g["graph"]["version"] = "1.1"
    (board / "hardware/graph.json").write_text(json.dumps(g, indent=1))
    export(board)
    assert part.own(project.config(), board)[1]["verified"] is None


def test_gate_asks_to_accept_the_warning(project, board):
    export(board)
    part.own(project.config(), board)
    use_own(project)
    cfg = project.config()
    rows, _ = gate.stage_graph(cfg, Design.from_config(cfg))
    row = next(r for r in rows if r["id"] == "SYNC.source")
    assert row["stage"] == "P" and row["result"] == "warn" and row["check"].startswith("M1 ring: ../ring is not")


def test_cli(project, board, capsys):
    assert cli.main(["part", "datasheet", "--connector", "J1", "--config", str(board / "edakit.toml")]) == 0
    commit(board)
    assert cli.main(["part", "own", str(board), "--config", str(project.root / "edakit.toml")]) == 0
    out = capsys.readouterr().out
    assert "hardware/parts/ring.json" in out and "not released" in out


# --- the simulation holds the board to its range -----------------------------------------------------------------

def supply_rows(project, sim=None):
    cfg = project.config()
    sim = sim or json.loads(cfg.sim_config.read_text())
    out = simrun.run_all(Design.from_config(cfg), sim)
    return [c for c in out["checks"] if c["item"] == "M1" and c["check"].startswith("supply voltage")]


def test_e3_holds_the_board_to_its_simulated_range(project, board):
    export(board)
    part.own(project.config(), board)
    use_own(project)                         # behind the host's reverse-polarity diode: half a volt below the range
    rows = supply_rows(project)
    assert rows and any(r["result"] == "fail" for r in rows)
    lo = json.loads((project.root / "hardware/parts/ring.json").read_text())["limits"]["vin_min_v"]
    assert all(r["expected"].startswith(f"{lo}") for r in rows)


def test_e3_passes_inside_the_range(project, board):
    export(board)
    part.own(project.config(), board)
    use_own(project, net="VIN")
    sim = json.loads((project.root / "hardware/sim.json").read_text())
    sim["sources"]["J1"]["r_ohm"] = 0.01
    sim["supplies"] = {"nom": {"J1": 5.0}}
    rows = supply_rows(project, sim)
    assert rows and all(r["result"] == "pass" for r in rows)


def test_p3_and_e3_leave_the_example_alone(project):
    rep = run_checks(project.root)
    assert p3(rep) == ([], [], [], []) and "SYNC.source" in executed(project.config())
    assert not [c for c in simrun.run_all(Design.from_config(project.config()),
                                          json.loads((project.root / "hardware/sim.json").read_text()))["checks"]
                if "vin_min … vin_max" in c["check"]]


def test_part_parser():
    args = cli.build_parser().parse_args(["part", "own", "../ring", "--name", "ring-v1"])
    assert isinstance(args, argparse.Namespace) and args.action == "own" and args.source == "../ring"
