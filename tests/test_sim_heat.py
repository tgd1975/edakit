"""Stage E seen red at the heat of a part: a junction above its limit, a part too hot to touch."""

import json
import shutil

import pytest

from edakit import block
from edakit.sim import run as simrun
from test_sim import failing, simulate

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")

JUNCTION = "junction temperature at 40 °C"
TOUCH = "temperature where people touch (board main)"


def sim_config(project):
    return json.loads((project.root / "hardware" / "sim.json").read_text())


def body_diode_in_the_supply_path(project):
    """D1 replaced by the block reverse-pmos (AO3401A, RθJA 125 K/W) with its gate at its source: switched off, its
    body diode carries the supply current – 0.07 W in all_on, inside E-2's 0.45 W."""
    block.add(project.config(), "reverse-pmos", "T", {"in": "VIN", "out": "+5V"})      # Q1, R3, net T_GATE
    g = project.graph()
    g["graph"]["components"] = [c for c in g["graph"]["components"] if c["designator"] != "D1"]
    for net in g["graph"]["nets"]:
        net["pins"] = [p for p in net["pins"] if not p.startswith("D1.") and p != "Q1.1"]
    project.net(g, "+5V")["pins"].append("Q1.1")
    project.save_graph(g)


def test_junction_of_a_discrete_part(project):
    body_diode_in_the_supply_path(project)
    out = simulate(project)
    assert not failing(out)
    tj = [c for c in out["checks"] if c["item"] == "Q1" and c["check"].startswith(JUNCTION)]
    assert len(tj) == 12 and all(c["id"] == "E-2" and c["expected"] == "≤ 110 °C" for c in tj)
    hot = next(c for c in tj if c["scenario"] == "usb-nom/all_on/vf-min")
    assert hot["check"] == f"{JUNCTION}: 0.0751 W × 125 K/W" and hot["actual"] == "49.38 °C"
    assert not [c for c in out["checks"] if c["check"].startswith("temperature where people touch")]


def test_too_hot_to_touch(project):
    body_diode_in_the_supply_path(project)
    sim = sim_config(project)
    sim["touch_c"] = {"main": 48}           # IEC 62368-1 TS1: plastic or metal touched longer than a minute
    bad = failing(simulate(project, sim))
    assert {(c["id"], c["item"], c["check"], c["expected"]) for c in bad} == {
        ("E-2", "Q1", TOUCH, "≤ 48 °C"), ("E-2", "U2", TOUCH, "≤ 48 °C")}
    assert {c["scenario"].split("/")[1] for c in bad} == {"all_on"} and len(bad) == 12
    sim["touch_c"] = {"main": 60}           # plastic touched 10 s to 1 min
    out = simulate(project, sim)
    assert not failing(out)
    assert len([c for c in out["checks"] if c["check"] == TOUCH]) == 24      # Q1 and U2 in 12 scenarios


def test_junction_of_a_diode(project):
    part = project.part("C8678")                                  # D1 (SS34) carries the supply current: 0.03 W
    part["ratings"]["rth_ja_k_per_w"] = 3000
    project.save_part("C8678", part)
    bad = failing(simulate(project))
    assert {(c["id"], c["item"], c["expected"]) for c in bad} == {("E-2", "D1", "≤ 110 °C")}   # the criteria's limit
    assert {c["scenario"].split("/")[1] for c in bad} == {"all_on"}
    part["ratings"]["tj_max_c"] = 60                              # the part's own limit, when it is the lower one
    project.save_part("C8678", part)
    bad = failing(simulate(project))
    assert {(c["item"], c["expected"]) for c in bad} == {("D1", "≤ 60 °C")} and len(bad) == 12


def test_driver_junction_against_its_own_limit(project):
    part = project.part("C90107")                                 # U2 (TLC5916) at 44–57 °C
    part["ratings"]["tj_max_c"] = 50
    project.save_part("C90107", part)
    bad = failing(simulate(project))
    assert {(c["id"], c["item"], c["expected"]) for c in bad} == {("E-3", "U2", "≤ 50 °C")}


def test_touch_limit_of_an_unknown_board(project):
    sim = sim_config(project)
    sim["touch_c"] = {"base": 48}
    with pytest.raises(simrun.SimError, match="touch_c: base is no board of the project"):
        simulate(project, sim)
    sim["touch_c"] = 48
    with pytest.raises(simrun.SimError, match="touch_c: a map"):
        simulate(project, sim)


def test_example_has_no_new_items(project):
    out = simulate(project)
    assert len(out["checks"]) == 738
    assert not [c for c in out["checks"] if c["check"].startswith(JUNCTION) and c["id"] == "E-2"]
