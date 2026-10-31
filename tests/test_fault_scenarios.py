"""Generated fault scenarios of the simulation (maker-coverage FT-8): a reversed source, a cable wire shorted at its far
end, one source off – opt-in through sim.json fault_scenarios, findings warnings at most."""

import json

import pytest
import reference
from test_sim import simulate

pytestmark = pytest.mark.ngspice


def with_faults(p, **spec):
    f = p.root / "hardware" / "sim.json"
    s = json.loads(f.read_text())
    s["fault_scenarios"] = spec
    f.write_text(json.dumps(s, indent=1))
    return s


def faults(out):
    return {sc["name"]: sc["status"] for sc in out["scenarios"] if sc["name"].startswith("fault ")}


def test_without_the_key_nothing_is_generated(project):
    assert faults(simulate(project)) == {}


def test_a_reversed_source_behind_its_diode(project):
    """J1 is marked reversible; D1 blocks the reversed supply – the scenario runs and passes."""
    with_faults(project, reversed=True)
    out = simulate(project)
    assert faults(out) == {"fault J1 reversed/idle": "ok"}


def test_a_reversed_source_without_its_diode_warns(project):
    """Without D1 the reversed 4.75 V reach the LEDs' anodes: about 4.6 V reverse across each – above a reverse limit
    of 4 V (a value for the test; the example's LEDs give 5 V)."""
    with_faults(project, reversed=True)
    led = project.part("C2297")
    led["limits"]["vr_max_v"] = 4
    project.save_part("C2297", led)
    g = project.graph()
    g["graph"]["components"] = [c for c in g["graph"]["components"] if c["designator"] != "D1"]
    vin = project.net(g, "VIN")
    g["graph"]["nets"].remove(vin)
    for n in g["graph"]["nets"]:
        n["pins"] = [r for r in n["pins"] if not r.startswith("D1.")]
    project.net(g, "+5V")["pins"] += [r for r in vin["pins"] if not r.startswith("D1.")]
    project.save_graph(g)
    out = simulate(project)
    assert faults(out) == {"fault J1 reversed/idle": "warn"}
    mine = [f for f in out["findings"] if f.get("scenario") == "fault J1 reversed/idle"]
    assert mine and {(f["code"], f["severity"]) for f in mine} == {("LIM.v", "warning")}
    assert {f["place"] for f in mine} == {f"D{k}" for k in range(2, 10)}
    assert {c["result"] for c in out["checks"] if c.get("scenario") == "fault J1 reversed/idle"} <= {"pass", "warn",
                                                                                                    "info"}


def test_a_cable_wire_shorted_at_its_far_end(tmp_path):
    p = reference.write_one(tmp_path / "cables", "cables")
    with_faults(p, shorted=True)
    out = simulate(p)
    assert set(faults(out)) == {"fault REMOTE shorted at J20/idle"}


def test_one_source_off_while_the_other_stays_on(tmp_path):
    p = reference.write_one(tmp_path / "power", "power")
    with_faults(p, off=True, supply="cells")
    out = simulate(p)
    assert faults(out) == {}                      # the supply cells has one source: nothing to leave out
    f = p.root / "hardware" / "sim.json"
    s = json.loads(f.read_text())
    s["supplies"]["both"] = {"J1": 5.0, "BT20": "fresh"}
    s["fault_scenarios"]["supply"] = "both"
    f.write_text(json.dumps(s, indent=1))
    assert set(faults(simulate(p))) == {"fault J1 off/idle", "fault BT20 off/idle"}


def test_an_unknown_key_is_an_error(project):
    from edakit.sim.run import SimError
    with_faults(project, reverse=True)
    with pytest.raises(SimError, match="fault_scenarios: a table of reversed, shorted, off, supply, load"):
        simulate(project)
