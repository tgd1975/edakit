"""A wire's current rating comes from the wire's own datasheet (maker-coverage FT-2; rules-at-scale.md, decision 22): a
cable's `i_max_a` holds the simulated current of each of its wires (LIM.i/cable). A cable that carries current in
the simulation without `i_max_a` is named – in the simulation's rows of information and by `edakit check --coverage` –
with its highest current and the loss per metre of wire it causes, I² × R of the wire's copper. No table by gauge, no
threshold: what was not checked, and the number that says how much heat goes into the wire."""

import json
import shutil

import pytest
from test_bought import usb_board

from edakit import cli, engines
from edakit.circuit import cable_problems, wire_ohm_per_m
from edakit.design import Design
from edakit.engines.coverage import cable_gaps, coverage, summary
from edakit.sim import run as simrun

ngspice = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


def cable(project, **keys):
    """The example's USB breakout on W1 (test_bought.py), W1 with these keys instead of its wire data."""
    g = project.graph() if "[boards.usb]" in (project.root / "edakit.toml").read_text() else usb_board(project)
    w1 = g["graph"]["cables"][0]
    g["graph"]["cables"][0] = {**{k: w1[k] for k in ("name", "from", "to", "pins")}, **keys}
    project.save_graph(g)
    return g


def simulate(project):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    return simrun.run_all(Design.from_config(project.config()), sim)


def gaps(project, sim=None):
    d = Design.from_config(project.config())
    return coverage(d, engines.profile(d, project.config()), sim)


def cli_run(project, monkeypatch, *argv):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    return cli.main(list(argv))


# --- the resistance per metre ----------------------------------------------------------------------------------------

def test_the_resistance_per_metre_of_a_wire():
    """Copper of the gauge at 20 °C (circuit.wire_ohm), or the given resistance over the given length; None where the
    length is not known."""
    assert round(wire_ohm_per_m({"length_m": 2, "awg": 22}), 5) == 0.05284      # 0.326 mm²: ≈ 53 mΩ/m
    assert round(wire_ohm_per_m({"length_m": 3, "mm2": 0.5}), 4) == 0.0344
    assert wire_ohm_per_m({"length_m": 2, "r_ohm_per_wire": 0.3}) == pytest.approx(0.15)
    assert wire_ohm_per_m({"r_ohm_per_wire": 0.3}) is None and wire_ohm_per_m({}) is None


def test_a_measured_resistance_may_come_with_its_length():
    """r_ohm_per_wire with length_m: the wire's own resistance and its length – the loss per metre, the inductance
    and the capacitance per metre need the length; a gauge besides it is still one source too many."""
    assert cable_problems({"r_ohm_per_wire": 0.3, "length_m": 2, "l_nh_per_m": 600}) == []
    assert cable_problems({"r_ohm_per_wire": 0.1, "length_m": 1, "awg": 24}) == ["r_ohm_per_wire or awg | mm2, not both"]
    assert cable_problems({"length_m": 2}) == ["length_m needs the wire's awg or mm2, or its r_ohm_per_wire"]


# --- with i_max_a: LIM.i/cable ---------------------------------------------------------------------------------------

@ngspice
def test_a_wire_above_the_cables_rating_is_lim_i(project):
    """W1 rated 0.1 A per wire: each of its two wires carries 114.7 mA at full load – above 80 % of 0.1 A; a warning
    while new."""
    cable(project, length_m=1, awg=26, i_max_a=0.1)
    out = simulate(project)
    rows = [r for r in out["checks"] if r["item"] == "cable W1" and r["id"] == "LIM.i" and r["result"] != "info"]
    assert {r["result"] for r in rows} == {"pass", "fail"}
    over = [r for r in rows if r["result"] == "fail"]
    assert {r["check"] for r in over} == {"current through wire W1_8", "current through wire W1_1"}
    assert {r["expected"] for r in over} == {"≤ 80 mA (80% of 100 mA)"}
    found = [f for f in out["findings"] if f["code"] == "LIM.i" and f["place"] == "cable W1"]
    assert found and {f["severity"] for f in found} == {"warning"} and {f["grade"] for f in found} == {"cable"}
    assert not any(r["item"] == "cable W1" and r["result"] == "info" for r in out["checks"])


@ngspice
def test_within_its_rating_the_cable_passes(project):
    cable(project, length_m=1, awg=26, i_max_a=2)
    out = simulate(project)
    rows = [r for r in out["checks"] if r["item"] == "cable W1"]
    assert rows and {r["result"] for r in rows} == {"pass"}
    assert not any(c["code"] == "LIM.i" and c["place"] == "cable W1" for c in out["findings"])


# --- without i_max_a: a row of information, the coverage report ------------------------------------------------------

@ngspice
def test_without_a_rating_the_simulation_names_its_highest_current_and_loss(project):
    """1 m of AWG 26 (0.134 Ω/m): 114.7 mA through each wire at full load, VIN out and GND back – 1.76 mW per metre of
    wire. One row of information over all scenarios, no finding."""
    cable(project, length_m=1, awg=26)
    out = simulate(project)
    assert out["cable_currents"]["W1"]["wire"] in ("1", "8")
    assert out["cable_currents"]["W1"]["i_a"] == pytest.approx(0.1147, rel=2e-3)
    assert out["cable_currents"]["W1"]["scenario"] == "usb-min/all_on/vf-min"
    rows = [r for r in out["checks"] if r["item"] == "cable W1"]
    assert len(rows) == 1 and rows[0]["result"] == "info" and rows[0]["id"] == "LIM.i"
    assert rows[0]["check"].startswith("highest current through a wire, no i_max_a (wire ")
    assert rows[0]["check"].endswith(" – I² × R: 1.756 mW per metre of wire, AWG 26 copper at 20 °C)")
    assert rows[0]["actual"] == "0.1147 A" and rows[0]["expected"] == "information"
    assert not any(f["place"] == "cable W1" for f in out["findings"])


def test_coverage_names_the_cable_with_its_current_and_its_loss_per_metre(project):
    """2 A through 22 AWG (52.8 mΩ/m, maker-coverage LED 10): 211 mW in every metre of the wire."""
    cable(project, length_m=2, awg=22)
    sim = {"cable_currents": {"W1": {"i_a": 2.0, "wire": "8", "scenario": "usb-max/all_on/vf-max"}}}
    line = next(g.line() for g in gaps(project, sim) if g.place == "cable W1")
    assert line == ("LIM.i: cable W1 – no i_max_a – up to 2 A (wire 8, usb-max/all_on/vf-max), I² × R: 211.3 mW per "
                    "metre of wire (AWG 22 copper at 20 °C) – its current is not held to the wire's rating")


def test_the_loss_without_a_length(project):
    """r_ohm_per_wire alone: the loss in the whole wire; no resistance at all: the loss is not known."""
    sim = {"cable_currents": {"W1": {"i_a": 0.5, "wire": "8", "scenario": "s"}}}
    cable(project, r_ohm_per_wire=0.2)
    assert next(g.missing for g in gaps(project, sim) if g.place == "cable W1") == (
        "no i_max_a – up to 500 mA (wire 8, s), I² × R: 50 mW in the wire (r_ohm_per_wire 0.2 Ω, no length_m for the "
        "loss per metre) – its current is not held to the wire's rating")
    cable(project)
    assert "the loss per metre is not known (no length_m with awg, mm2 or r_ohm_per_wire)" in next(
        g.missing for g in gaps(project, sim) if g.place == "cable W1")


def test_a_rated_or_a_quiet_cable_is_no_gap(project):
    sim = {"cable_currents": {"W1": {"i_a": 0.0, "wire": "8", "scenario": "s"}}}
    cable(project, length_m=1, awg=26)
    assert not any(g.place == "cable W1" for g in gaps(project, sim))
    sim["cable_currents"]["W1"]["i_a"] = 0.3
    cable(project, length_m=1, awg=26, i_max_a=1)
    assert not any(g.place == "cable W1" for g in gaps(project, sim))


def test_without_a_simulation_the_current_is_not_known(project):
    cable(project, length_m=1, awg=26)
    g = next(g for g in gaps(project) if g.place == "cable W1")
    assert g.kind == "cable" and g.missing == ("no i_max_a – its current is not known without a simulation of this "
                                               "state (edakit sim) – it is not held to the wire's rating")


def test_the_one_line_names_the_cables(project):
    cable(project, length_m=1, awg=26)
    sim = {"cable_currents": {"W1": {"i_a": 0.1, "wire": "8", "scenario": "s"}}}
    assert summary(gaps(project, sim)).endswith("; cables without i_max_a: W1 – edakit check --coverage")
    assert [g.place for g in cable_gaps(Design.from_config(project.config()), sim)] == ["cable W1"]


@ngspice
def test_check_coverage_reads_the_last_simulation_of_this_state(project, monkeypatch, capsys):
    """edakit check runs no simulation: it reads the one edakit sim saved, while its inputs are unchanged."""
    cable(project, length_m=1, awg=26)
    toml = str(project.root / "edakit.toml")
    assert cli.main(["check", "--coverage", "--config", toml]) == 0
    assert "LIM.i: cable W1 – no i_max_a – its current is not known" in capsys.readouterr().out
    cli_run(project, monkeypatch, "sim")
    capsys.readouterr()
    assert cli.main(["check", "--coverage", "--config", toml]) == 0
    out = capsys.readouterr().out
    assert "LIM.i: cable W1 – no i_max_a – up to 114.7 mA (wire " in out
    assert ", usb-min/all_on/vf-min), I² × R: 1.756 mW per metre of wire (AWG 26 copper at 20 °C)" in out
    assert cli.main(["check", "--config", toml]) == 0
    assert "; cables without i_max_a: W1 – edakit check --coverage" in capsys.readouterr().out
    g = project.graph()
    g["graph"]["cables"][0]["length_m"] = 2                  # another state: the saved simulation does not count
    project.save_graph(g)
    assert cli.main(["check", "--coverage", "--config", toml]) == 0
    assert "LIM.i: cable W1 – no i_max_a – its current is not known" in capsys.readouterr().out


@ngspice
def test_the_gate_protocol_lists_the_cable(project, monkeypatch):
    cable(project, length_m=1, awg=26)
    cli_run(project, monkeypatch, "gate")
    text = (sorted((project.root / "build" / "release").iterdir())[-1] / "protocol.md").read_text()
    two = text.split("## 2 ")[1].split("\n## ")[0]
    assert "- LIM.i: cable W1 – no i_max_a – up to 114.7 mA (wire " in two
    seven = text.split("## 7 ")[1].split("\n## ")[0]
    assert "| LIM.i | highest current through a wire, no i_max_a | 0 | 0 | 0 | 1 |" in seven
