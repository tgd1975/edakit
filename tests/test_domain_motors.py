"""The kinds motor, solenoid, speaker, heater and optocoupler (maker-coverage FT-6), the flyback diode for every
switched winding (CK-15), and the domain motors with its hints (HT-10, HT-12)."""

import json
import shutil

import pytest
from test_sim import simulate

from edakit import engines, profile
from edakit.design import Design

# values for the tests, not from datasheets
MOTOR = {"lcsc": "C9000501", "mpn": "test motor", "kind": "motor", "verified": {"by": "test"},
         "limits": {"v_max_v": 6, "i_max_a": 0.4}, "values": {"coil_ohm": 10},
         "pins": {"1": {"name": "+", "type": "passive", "role": "plus"}, "2": {"name": "-", "type": "passive",
                                                                            "role": "minus"}}}
HEATER = {"lcsc": "C9000502", "mpn": "test heater", "kind": "heater", "verified": {"by": "test"},
          "limits": {"v_max_v": 12, "p_max_w": 2}, "values": {"value_ohm": 10},
          "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}}}


def motor_on_switch(project, des="M1", part=MOTOR, kind="motor"):
    """`des` from +5V to the collector of an S8050 Q8, its base through R8 (10 kΩ) from GP8 (U1.11)."""
    project.use_library_part("C2146")
    project.use_library_part("C17414")
    project.save_part(part["lcsc"], part)
    g = project.graph()
    project.free_pins(g, "U1.11")
    g["graph"]["components"] += [
        {"designator": des, "type": kind, "lcsc": part["lcsc"], "pins": {"1": "1", "2": "2"}},
        {"designator": "Q8", "type": "transistor", "lcsc": "C2146", "pins": {"1": "B", "2": "E", "3": "C"}},
        {"designator": "R8", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}},
        {"designator": "R9", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}}]
    project.net(g, "+5V")["pins"].append(f"{des}.1")
    project.net(g, "GND")["pins"] += ["Q8.2", "R9.2"]
    g["graph"]["nets"] += [{"name": "M_DRIVE", "pins": [f"{des}.2", "Q8.3"], "v": [0, 5.5]},
                           {"name": "M_BASE", "pins": ["Q8.1", "R8.2", "R9.1"], "v": [0, 3.4]},
                           {"name": "M_CTRL", "pins": ["R8.1", "U1.11"], "v": [0, 3.4]}]
    project.save_graph(g)
    return g


def run(project):
    cfg = project.config()
    return engines.run(Design.from_config(cfg), cfg).findings


def test_a_switched_motor_needs_its_flyback_diode(project):
    motor_on_switch(project)
    found = [f.text for f in run(project) if f.code == "REQ.missing"]
    assert "M1: the motor's winding switched by Q8 without a diode across it (cathode at +5V, anode at M_DRIVE)" in found


def test_the_motor_suggests_its_domain_and_its_hint(project):
    motor_on_switch(project)
    d = Design.from_config(project.config())
    assert "motors" in profile.suggested(d)
    hints = [(f.code, f.place) for f in run(project) if f.code.startswith("HINT.")]
    assert ("HINT.motor_supply", "M1") in hints


def test_without_the_domain_no_motor_hint(project):
    motor_on_switch(project)
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("[project]", '[project]\ndomains = []', 1))
    found = run(project)
    assert not any(f.code == "HINT.motor_supply" for f in found)
    assert any(f.code == "STRUCT.domain" and f.place == "motors" for f in found)


def test_a_heater_gets_its_hint(project):
    motor_on_switch(project, "HE1", HEATER, "heater")
    assert ("HINT.heater", "HE1") in [(f.code, f.place) for f in run(project) if f.code.startswith("HINT.")]


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_the_winding_carries_its_stall_current(project):
    """M1 (10 Ω) straight across +5V and GND, a motor at standstill: about 0.45 A – above its 0.4 A derated to 80 %,
    LIM.i in every scenario."""
    project.save_part("C9000501", MOTOR)
    g = project.graph()
    g["graph"]["components"].append({"designator": "M1", "type": "motor", "lcsc": "C9000501", "pins": {"1": "1", "2": "2"}})
    project.net(g, "+5V")["pins"].append("M1.1")
    project.net(g, "GND")["pins"].append("M1.2")
    project.save_graph(g)
    out = simulate(project)
    cur = [c for c in out["checks"] if c["item"] == "M1" and c["check"] == "winding current (at standstill)"]
    assert cur and all(c["result"] == "fail" and c["id"] == "LIM.i" for c in cur)


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_an_optocoupler_passes_its_led_current_on(project):
    """U8: LED from GP8 through 330 Ω to GND (about 6 mA), its transistor from 3V3 through 10 kΩ to GND passes
    0.5 × 6 mA – more than the resistor lets through, so its emitter sits near 3V3."""
    from edakit.sim import netlist
    project.use_library_part("C17414")
    opto = {"lcsc": "C9000503", "mpn": "test opto", "kind": "optocoupler", "verified": {"by": "test"},
            "limits": {"if_max_a": 0.05}, "values": {"vf_v": 1.2, "vf_at_a": 0.01, "ctr_min_ratio": 0.5},
            "pins": {"1": {"name": "A", "type": "passive", "role": "anode"}, "2": {"name": "K", "type": "passive",
                                                                                 "role": "cathode"},
                     "3": {"name": "E", "type": "passive", "role": "emitter"},
                     "4": {"name": "C", "type": "passive", "role": "collector"}}}
    project.save_part("C9000503", opto)
    r330 = project.part("C17414")
    r330.update(lcsc="C9000504", mpn="test 330")
    r330["values"]["value_ohm"] = 330
    project.save_part("C9000504", r330)
    g = project.graph()
    project.free_pins(g, "U1.11")
    g["graph"]["components"] += [
        {"designator": "U8", "type": "optocoupler", "lcsc": "C9000503", "pins": {"1": "A", "2": "K", "3": "E", "4": "C"}},
        {"designator": "R8", "type": "resistor", "lcsc": "C9000504", "value": "330", "pins": {"1": "1", "2": "2"}},
        {"designator": "R9", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}}]
    g["graph"]["nets"] += [{"name": "OPTO_IN", "pins": ["U1.11", "R8.1"], "v": [0, 3.4]},
                           {"name": "OPTO_A", "pins": ["R8.2", "U8.1"], "v": [0, 3.4]},
                           {"name": "OPTO_OUT", "pins": ["U8.3", "R9.1"], "v": [0, 3.4]}]
    project.net(g, "GND")["pins"] += ["U8.2", "R9.2"]
    project.net(g, "3V3")["pins"].append("U8.4")
    project.save_graph(g)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["mcu"]["U1"]["outputs"].append("OPTO_IN")
    sim["loads"]["all_on"]["gpio"]["OPTO_IN"] = 1
    sim.setdefault("report", []).append("OPTO_OUT")
    out = simulate(project, sim)
    on = next(s for s in out["scenarios"] if s["name"].endswith("all_on/vf-max"))
    off = next(s for s in out["scenarios"] if s["name"].endswith("idle/vf-max"))
    assert on["nets"]["OPTO_OUT"] > 2.5 and abs(off["nets"]["OPTO_OUT"]) < 0.05
    led = [c for c in out["checks"] if c["item"] == "U8" and c["check"] == "LED forward current"]
    assert led and all(c["result"] == "pass" for c in led)
    from edakit.sim import run as simrun
    text, _ = netlist.build(Design.from_config(project.config()), sim, next(simrun.scenarios(sim)))
    assert "B_U8_CE" in text
