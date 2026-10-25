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


def test_gpio_current_comes_out_of_the_supply(project):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    before = simulate(project, sim)
    sim["mcu"]["U1"]["outputs"].append("BTN")                   # drive the button net high and press the button:
    sim["loads"]["idle"]["gpio"]["BTN"] = 1                     # ~110 mA out of the GPIO into the switch
    sim["loads"]["idle"]["buttons"] = ["SW1"]
    after = simulate(project, sim)
    i0, i1 = (next(s for s in out["scenarios"] if s["name"] == "usb-nom/idle/vf-min")["sources"]["J1"]
              for out in (before, after))
    assert i1 - i0 > 0.05                                       # 3.3 V x 0.11 A through the buck from 5 V


def test_power_bank_minimum_load(project):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["sources"]["J1"]["i_min_a"] = 0.001
    assert not failing(simulate(project, sim))
    sim["sources"]["J1"]["i_min_a"] = 0.5                       # idle draws far less: a power bank would switch off
    assert any(c["item"] == "J1" and "keeps the supply on" in c["check"] for c in failing(simulate(project, sim)))


def test_led_dark_when_oe_high(project):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["loads"]["all_on"]["gpio"]["LED_OE"] = 1      # all_on expects light, OE says dark
    sim["loads"]["all_on"]["leds_on"] = "all"
    out = simulate(project, sim)
    dark = [c for c in out["checks"] if c["scenario"].endswith("all_on/vf-min") and c["item"] == "D2"
            and c["check"] == "LED dark"]
    assert dark and dark[0]["result"] == "pass"


def test_external_load_at_a_connector(project):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    base = simulate(project, sim)
    sim["loads"]["idle"]["external"] = {"J1": {"plus": "1", "minus": "2", "i_a": 0.3}}
    out = simulate(project, sim)
    i0 = next(s for s in base["scenarios"] if s["name"] == "usb-nom/idle/vf-min")["sources"]["J1"]
    i1 = next(s for s in out["scenarios"] if s["name"] == "usb-nom/idle/vf-min")["sources"]["J1"]
    assert i1 - i0 == pytest.approx(0.3, abs=0.01)
    assert out["net_currents"]["VIN"]["i_max_a"] >= 0.3
    sim["loads"]["idle"]["external"]["J1"]["i_a"] = 2.0          # rated 2 A, derated 1.6 A
    assert any(c["item"] == "J1" and "external load" in c["check"] for c in failing(simulate(project, sim)))


def test_input_level_defined(project):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["mcu"]["U1"]["inputs"] = ["BTN"]
    part = project.part("C41407547")
    part["params"].update(vih_v=2.0, vil_v=0.8)
    project.save_part("C41407547", part)
    out = simulate(project, sim)
    levels = [c for c in out["checks"] if c["item"] == "U1 BTN"]
    assert {c["check"].split()[2] for c in levels} == {"high", "low"} and not failing(out)
    part["params"]["vih_v"] = 3.5                                 # the pull-up to 3.3 V no longer reaches VIH
    project.save_part("C41407547", part)
    assert any(c["item"] == "U1 BTN" and "undefined" in c["check"] for c in failing(simulate(project, sim)))


def test_io_level_follows_the_supply_pin(project):
    part = project.part("C41407547")
    part["params"]["v_io"] = "vin"                                # LED_OE high would be VSYS, not 3.3 V
    project.save_part("C41407547", part)
    assert any(c["id"] == "E-1" and "vout_v" in c["actual"] for c in failing(simulate(project)))
    part["params"]["vout_v"] = 3.3
    project.save_part("C41407547", part)
    assert any(c["item"] == "LED_OE" and "declared range" in c["check"] for c in failing(simulate(project)))


def test_fault_load_only_in_extra_scenarios(project):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["loads"]["short"] = {"matrix": False, "external": {"J1": {"plus": "1", "minus": "2", "i_a": 3.0}}}
    sim["extra_scenarios"] = [{"name": "short", "supply": {"J1": 5.0}, "load": "short", "info": True}]
    out = simulate(project, sim)
    assert [s["name"] for s in out["scenarios"] if s["load"] == "short"] == ["short"]
    assert not failing(out) and any(c["scenario"] == "short" and c["result"] == "info" for c in out["checks"])


def test_unknown_behaviour_model_fails_cleanly(project):
    part = project.part("C90107")
    part["params"]["behavior"] = "no_such_model"
    project.save_part("C90107", part)
    out = simulate(project)
    assert all(s["status"] == "error" for s in out["scenarios"])
    assert any(c["id"] == "E-1" and "no_such_model" in c["actual"] for c in out["checks"])


def test_gpio_current_per_pin_and_in_total(project):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["mcu"]["U1"]["outputs"].append("BTN")                   # GPIO high into the pressed button: ~110 mA
    sim["loads"]["all_on"]["gpio"]["BTN"] = 1
    part = project.part("C41407547")
    part["ratings"].update(gpio_i_max_a=0.5, gpio_i_total_max_a=1.0)
    project.save_part("C41407547", part)
    gpio = lambda out: [c for c in out["checks"] if c["check"].startswith("GPIO")]  # noqa: E731
    out = simulate(project, sim)                                  # (the 50-mA button itself fails E-2 here)
    assert any(c["item"] == "U1 BTN" for c in gpio(out)) and not failing({"checks": gpio(out)})
    part["ratings"].update(gpio_i_max_a=0.012, gpio_i_total_max_a=0.05)   # RP2040-like: 12 mA per pin, 50 mA in all
    project.save_part("C41407547", part)
    bad = failing({"checks": gpio(simulate(project, sim))})
    assert any(c["id"] == "E-2" and c["item"] == "U1 BTN" and c["check"] == "GPIO output current" for c in bad)
    assert any(c["id"] == "E-2" and c["check"] == "GPIO current sourced by all outputs together" for c in bad)


def test_output_on_an_input_only_pin(project):
    part = project.part("C41407547")
    part["pins"]["7"]["type"] = "input"                           # GP5 (LED_OE) as if it could only read
    project.save_part("C41407547", part)
    bad = failing(simulate(project))
    assert any(c["id"] == "E-3" and c["item"] == "U1 LED_OE" and "can only be an input" in c["check"] for c in bad)


def test_relay_pulls_in_and_releases(project):
    from test_checks import RELAY, add_flyback, coil_stage
    coil_stage(project, RELAY, ("coil_plus", "coil_minus"))
    add_flyback(project)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["mcu"]["U1"]["outputs"].append("DRIVE")
    sim["loads"]["all_on"]["gpio"]["DRIVE"] = 1
    sim["loads"]["all_on"]["relays_on"] = ["X1"]
    out = simulate(project, sim)
    relay = [c for c in out["checks"] if c["item"] == "X1"]
    assert {c["check"].split(":")[0] for c in relay} >= {"relay pulls in", "relay releases", "coil voltage"}
    assert not failing(out)
    sim["loads"]["idle"]["gpio"]["DRIVE"] = 1                     # driven, but the load says released
    assert any(c["item"] == "X1" and c["check"].startswith("relay releases") for c in failing(simulate(project, sim)))
