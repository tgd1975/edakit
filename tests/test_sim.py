"""Stage E seen red: reversed LED, overloaded part, too narrow range, too weak supply."""

import json
import shutil

import pytest

from edakit.design import Design
from edakit.sim import run as simrun

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


def simulate(project, sim=None):
    cfg = project.config()
    sim = sim or json.loads((project.root / "hardware" / "sim.json").read_text())
    return simrun.run_all(Design.from_config(cfg), sim)


def failing(out):
    return [c for c in out["checks"] if c["result"] == "fail"]


def test_example_passes(project):
    out = simulate(project)
    assert not failing(out)
    assert all(s["status"] == "ok" for s in out["scenarios"])
    led = [c for c in out["checks"] if c["item"] == "D2" and c["check"].startswith("LED current")]
    assert led and all(c["result"] == "pass" for c in led)
    assert out["net_currents"]["GND"]["i_max_a"] > 0.1   # the supply current returns through GND


def test_reversed_led(project):
    g = project.graph()
    project.net(g, "+5V")["pins"].remove("D5.1")
    project.net(g, "LED3")["pins"].remove("D5.2")
    project.net(g, "+5V")["pins"].append("D5.2")
    project.net(g, "LED3")["pins"].append("D5.1")
    project.save_graph(g)
    bad = failing(simulate(project))
    assert any(c["item"] == "D5" and "reversed" in c["check"] for c in bad)


def test_overloaded_resistor(project):
    part = project.part("C17604")
    part["ratings"]["p_max_w"] = 1e-6
    project.save_part("C17604", part)
    assert any(c["id"] == "E-2" and c["item"] == "R1" for c in failing(simulate(project)))


def test_net_range_too_narrow(project):
    g = project.graph()
    project.net(g, "+5V")["v"] = [0, 4.0]
    project.save_graph(g)
    assert any(c["item"] == "+5V" and "declared range" in c["check"] for c in failing(simulate(project)))


def test_supply_limit(project):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["sources"]["J1"]["i_max_a"] = 0.05
    assert any(c["item"] == "J1" and "supply" in c["check"] for c in failing(simulate(project, sim)))


def test_led_dark_when_oe_high(project):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["loads"]["all_on"]["gpio"]["LED_OE"] = 1      # all_on expects light, OE says dark
    sim["loads"]["all_on"]["leds_on"] = "all"
    out = simulate(project, sim)
    dark = [c for c in out["checks"] if c["scenario"].endswith("all_on/vf-min") and c["item"] == "D2"
            and c["check"] == "LED dark"]
    assert dark and dark[0]["result"] == "pass"


def test_unknown_behaviour_model_fails_cleanly(project):
    part = project.part("C90107")
    part["params"]["behavior"] = "no_such_model"
    project.save_part("C90107", part)
    out = simulate(project)
    assert all(s["status"] == "error" for s in out["scenarios"])
    assert any(c["id"] == "E-1" and "no_such_model" in c["actual"] for c in out["checks"])
