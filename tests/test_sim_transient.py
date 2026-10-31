"""Stage E over time: plug, unplug and switch-over as transient runs (LIM.v), and the behaviour models on a dead rail."""

import json
import shutil

import pytest

from edakit import part
from edakit.release import gate
from edakit.sim import run as simrun
from test_sim import failing, simulate

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")

UNPLUG = {"supply": {"J1": [[0, 4.75], [0.001, 4.75], [0.00101, 0]]}, "load": "all_on", "corner": "max",
          "stop_s": 0.0013, "step_s": 1e-6, "expect": {"+5V": {"min_v": 1.8}}}
PLUG = {"supply": {"J1": [[0, 0], [0.001, 4.75]]}, "load": "all_on", "corner": "max", "stop_s": 0.002,
        "step_s": 1e-6, "expect": {"J1": {"i_max_a": 0.1}}}


MCU = ("U1", "lowest supply voltage once started (vsys_min_v)")


def sim_config(project):
    return json.loads((project.root / "hardware" / "sim.json").read_text())


def e5(out):
    """The rows of the transient runs' limits: expect and the MCU's supply once started."""
    return [c for c in out["checks"] if c["scenario"].startswith("usb-") and c["id"] != "SIM.converge"
            and c["check"] in ("lowest voltage", "highest voltage", "peak current from the supply")
            or c["check"].startswith("lowest supply voltage once started")]


def dc_only(project, sim, supply, load="idle"):
    """One extra DC scenario 'x' with `supply`; the voltages the report lists (+5V, 3V3) and J1's current."""
    sim["supplies"] = {}
    sim["extra_scenarios"] = [{"name": "x", "supply": supply, "load": load, "info": True}]
    row = simulate(project, sim)["scenarios"][0]
    return row["nets"], row["sources"].get("J1", 0.0)


def test_regulator_below_its_minimum_is_off(project):
    nets, i = dc_only(project, sim_config(project), {"J1": 1.3})      # U1's VSYS minimum is 1.8 V
    assert 1.0 < nets["+5V"] <= 1.3
    assert abs(nets["3V3"]) < 0.01                                      # the on-board buck is off …
    assert abs(i) < 0.001                                               # … and draws nothing from its input


def test_constant_current_load_on_a_dead_rail(project):
    part = project.part("C41407547")                                    # U1 as a plain current at its supply pins
    part["values"] = {"behavior": "current", "i_a": 0.05}
    project.save_part("C41407547", part)
    nets, _ = dc_only(project, sim_config(project), {})                  # nothing plugged in
    assert abs(nets["+5V"]) < 0.01 and abs(nets["3V3"]) < 0.01         # not pulled below ground


def test_models_unchanged_above_their_minimums(project):
    out = simulate(project)
    assert not failing(out) and len(out["checks"]) == 738 and len(out["scenarios"]) == 12
    low = next(s for s in out["scenarios"] if s["name"] == "usb-min/all_on/vf-max")
    assert round(low["nets"]["+5V"], 3) == 4.443 and round(low["nets"]["3V3"], 3) == 3.3
    assert not e5(out)                                                  # without transients nothing runs


def test_unplug_held_by_the_bulk_capacitor(project):
    sim = sim_config(project)
    sim["transients"] = {"usb-unplug": UNPLUG}
    out = simulate(project, sim)
    row = out["scenarios"][-1]
    assert row["name"] == "usb-unplug" and row["transient"] and row["status"] == "ok"
    assert 2.9 < row["nets"]["+5V"] < 3.1 and row["nets_max"]["+5V"] > 4.4      # C2 = 22 µF: about 2.99 V
    items = {(c["item"], c["check"]): c for c in e5(out)}
    assert set(items) == {("+5V", "lowest voltage"), MCU}
    low = items[("+5V", "lowest voltage")]
    assert low["result"] == "pass" and low["expected"] == "≥ 1.8 V" and low["actual"].startswith("2.9")
    assert low["actual"].endswith("at 1.3 ms") and low["scenario"] == "usb-unplug"
    assert len(out["scenarios"]) == 13 and len([c for c in out["checks"] if c["scenario"] == "usb-unplug"]) == 3


def test_unplug_without_the_bulk_capacitor(project):
    part = project.part("C45783")                                       # C2 22 µF -> 1 µF
    part["values"]["value_f"] = 1e-6
    project.save_part("C45783", part)
    sim = sim_config(project)
    sim["transients"] = {"usb-unplug": UNPLUG}
    out = simulate(project, sim)
    bad = failing(out)
    assert {(c["id"], c["item"], c["expected"]) for c in bad} == {("LIM.v", "+5V", "≥ 1.8 V"), ("LIM.range", "U1", "≥ 1.8 V")}
    assert 1.4 < out["scenarios"][-1]["nets"]["+5V"] < 1.7                    # about 1.59 V
    assert out["scenarios"][-1]["nets"]["3V3"] < 0.1                         # U1 below its 1.8 V: 3V3 gone
    sim["transients"]["usb-unplug"]["info"] = True
    out = simulate(project, sim)
    assert not failing(out) and {c["result"] for c in e5(out)} == {"info"}


def test_plug_starts_from_zero_and_shows_the_inrush(project):
    sim = sim_config(project)
    sim["transients"] = {"usb-plug": PLUG}
    out = simulate(project, sim)
    row = out["scenarios"][-1]
    assert abs(row["nets"]["+5V"]) < 0.01 and abs(row["nets"]["3V3"]) < 0.01     # from 0 V, not from -0.5 V
    assert row["nets_max"]["+5V"] > 4.4 and abs(row["nets_max"]["3V3"] - 3.3) < 0.01
    assert 0.2 < row["sources"]["J1"] < 0.25                             # about 0.22 A into C2 and the loads
    bad = failing(out)
    assert {(c["id"], c["item"], c["check"], c["expected"]) for c in bad} == {
        ("LIM.i", "J1", "peak current from the supply", "≤ 100 mA")}
    assert next(c for c in e5(out) if c["item"] == "U1")["result"] == "pass"     # judged once it has started
    sim["transients"]["usb-plug"]["expect"] = {"J1": {"i_max_a": 0.3}, "3V3": {"min_v": -0.01, "max_v": 3.4}}
    items = {(c["item"], c["check"]): c["result"] for c in e5(simulate(project, sim))}
    assert items == {("J1", "peak current from the supply"): "pass", ("3V3", "lowest voltage"): "pass",
                     ("3V3", "highest voltage"): "pass", (*MCU,): "pass"}


def test_protocol_shows_the_run(project, tmp_path):
    sim = sim_config(project)
    sim["transients"] = {"usb-unplug": UNPLUG}
    out = simulate(project, sim)
    head = {"time": "2026-10-27T10:00:00+01:00", "tester": "test", "graph_version": "1.0", "graph_date": "2026-10-27",
            "graph_sha256": "a", "state_sha256": "b", "layout_sha256": "c", "git_commit": "abc", "git_dirty": False,
            "tools": {"python": "3", "edakit": "0", "ngspice": "ngspice-45", "easyeda-mcp-pro": "1.4.0"}}
    gate.write_protocol(project.config(), tmp_path, head, [], out, {"manual": []}, [], "RELEASED", [], set("PGE"),
                        gate.STAGES, {})
    text = (tmp_path / "protocol.md").read_text()
    assert "| usb-unplug (transient) | ok | +5V 2.985 … 4.443 V, 3V3 3.300 … 3.300 V | J1 peak 114 mA |" in text
    assert "| LIM.v | lowest voltage | 1 | 0 | 0 | 0 |" in text


def test_datasheet_of_the_board_leaves_the_runs_out(project):
    sim = sim_config(project)
    sim["transients"] = {"usb-plug": PLUG}                               # 0.224 A peak, the DC scenarios 0.114 A
    (project.root / "hardware" / "sim.json").write_text(json.dumps(sim))
    entry, _ = part.datasheet(project.config(), ["J1"])
    assert entry["values"]["i_a"] < 0.12


@pytest.mark.parametrize("bad,match", [
    ({"x": {"supply": {"J1": 5}, "load": "nope", "stop_s": 0.001}}, "transients x: load nope"),
    ({"x": {"supply": {"J1": 5}, "load": "idle"}}, "transients x: stop_s"),
    ({"x": {"supply": {"J1": [[0, 5], [0, 0]]}, "load": "idle", "stop_s": 0.001}}, "transients x: J1"),
    ({"x": {"supply": {"J9": 5}, "load": "idle", "stop_s": 0.001}}, "transients x: J9"),
    ({"x": {"supply": {"J1": 5}, "load": "idle", "stop_s": 0.001, "expect": {"NOPE": {"min_v": 1}}}},
     "transients x: expect NOPE"),
    ({"x": {"supply": {"J1": 5}, "load": "idle", "stop_s": 0.001, "expect": {"+5V": {"i_max_a": 1}}}},
     "transients x: expect \\+5V"),
    ([1], "transients: a map"),
])
def test_transients_say_what_is_wrong(project, bad, match):
    sim = sim_config(project)
    sim["transients"] = bad
    with pytest.raises(simrun.SimError, match=match):
        simulate(project, sim)


# --- load steps (maker-coverage FT-1) ----------------------------------------------------------------------------
BURST = [[0, 0.03], [0.001, 0.03], [0.00101, 0.35], [0.003, 0.35], [0.00301, 0.03]]     # a Wi-Fi burst on the core


def test_a_core_step_shows_in_the_supply_current(project):
    """steps turns the MCU's core current into [t, A] points: the burst of 0.35 A shows in J1's peak current, which the
    same run without steps keeps below 0.1 A."""
    sim = sim_config(project)
    run = {"supply": {"J1": 4.75}, "load": "idle", "stop_s": 0.004, "step_s": 1e-5, "expect": {"J1": {"i_max_a": 0.1}}}
    sim["transients"] = {"usb-burst": run}
    assert not failing(simulate(project, sim))
    sim["transients"]["usb-burst"] = {**run, "steps": {"U1": BURST}}
    out = simulate(project, sim)
    peak = next(c for c in failing(out) if c["check"] == "peak current from the supply")
    assert peak["id"] == "LIM.i" and peak["item"] == "J1" and peak["expected"] == "≤ 100 mA"
    assert 0.25 < out["scenarios"][-1]["sources"]["J1"] < 0.5       # 0.35 A at 3.3 V through the on-board buck


def test_an_external_load_starting_browns_the_mcu_out(project):
    """A servo-like load at the input steps from 50 mA to 12 A for 2 ms: the source's 0.3 Ω takes the rail below the
    MCU's minimum, LIM.range finds the brown-out; at its 50 mA the run passes."""
    sim = sim_config(project)
    sim["loads"]["idle"]["external"] = {"J1": {"plus": "1", "minus": "2", "i_a": 0.05}}
    run = {"supply": {"J1": 4.75}, "load": "idle", "stop_s": 0.005, "step_s": 1e-5}
    sim["transients"] = {"usb-servo": run}
    assert not failing(simulate(project, sim))
    sim["transients"]["usb-servo"] = {**run, "steps": {"J1": [[0, 0.05], [0.001, 0.05], [0.00101, 12], [0.003, 12],
                                                             [0.00301, 0.05]]}}
    bad = failing(simulate(project, sim))
    assert ("LIM.range", "U1") in {(c["id"], c["item"]) for c in bad}


@pytest.mark.parametrize("steps, match", [
    ({"C2": [[0, 1]]}, "steps C2 – an external load"),
    ({"U1": [[0, 1], [0, 2]]}, "steps U1 – a list of"),
    ({"U1": [[0, -1]]}, "steps U1 – a list of"),
    ([1], "steps, a map"),
])
def test_steps_say_what_is_wrong(project, steps, match):
    sim = sim_config(project)
    sim["transients"] = {"x": {"supply": {"J1": 5}, "load": "idle", "stop_s": 0.001, "steps": steps}}
    with pytest.raises(simrun.SimError, match=match):
        simulate(project, sim)


def test_an_ngspice_run_past_its_time_is_a_sim_error(monkeypatch):
    """ngspice running into its timeout ends with a SimError naming the run, not with subprocess.TimeoutExpired –
    found with the charger model just above its overcharge threshold."""
    import shutil as _shutil
    import subprocess

    import pytest as _pytest

    from edakit.sim import run as simrun

    def slow(*a, **k):
        raise subprocess.TimeoutExpired(a[0], k.get("timeout"))
    monkeypatch.setattr(_shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(subprocess, "run", slow)
    with _pytest.raises(simrun.SimError, match="no operating point within"):
        simrun.ngspice("* empty\n.end\n", name="usb-min/all_on")
    with _pytest.raises(simrun.SimError, match="transient run took more than"):
        simrun.ngspice_tran("* empty\n.end\n", "out.txt", name="plug")
