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


def test_zero_ohm_bridges(project):
    from test_checks import bridged
    bridged(project)                                              # R10–R12: 0 Ω, D9 reaches OUT7 through R12
    out = simulate(project)
    assert not failing(out) and all(s["status"] == "ok" for s in out["scenarios"])
    d9 = [c for c in out["checks"] if c["item"] == "D9" and c["check"] == "LED current (LED7)"]
    assert len(d9) == 6 and all(c["result"] == "pass" for c in d9)   # all_on: 3 supplies x 2 corners


def test_bridge_is_simulated_with_its_maximum_resistance(project):
    from test_checks import BRIDGE, bridged
    from edakit.sim import netlist
    bridged(project)

    def line():
        sim = json.loads((project.root / "hardware" / "sim.json").read_text())
        text, _ = netlist.build(Design.from_config(project.config()), sim, next(simrun.scenarios(sim)))
        return next(x for x in text.splitlines() if x.startswith("R_R10 "))
    assert line() == "R_R10 n_3v3 n_3v3_b 0.05"                 # no r_max_ohm in the entry: 50 mΩ
    project.save_part(BRIDGE["lcsc"], {**BRIDGE, "params": {"value_ohm": 0.0, "r_max_ohm": 0.02}})
    assert line() == "R_R10 n_3v3 n_3v3_b 0.02"


# XINGLIGHT XL-B504RGBC, 5 mm RGB LED with a common anode: pin 1 = anode, 2 = red, 3 = green, 4 = blue cathode;
# IF 20 mA, VR 5 V per colour; VF at 20 mA red 1.8–2.4 V, green and blue 2.8–3.4 V (no typical value: the middle)
RGB = {"lcsc": "C7371895", "mpn": "XL-B504RGBC", "manufacturer": "XINGLIGHT", "kind": "led_rgb",
       "verified": {"by": "test"},
       "pins": {"1": {"name": "A", "type": "passive", "role": "anode"},
                "2": {"name": "R", "type": "passive", "role": "cathode_red"},
                "3": {"name": "G", "type": "passive", "role": "cathode_green"},
                "4": {"name": "B", "type": "passive", "role": "cathode_blue"}},
       "params": {"red": {"vf_min": 1.8, "vf_typ": 2.1, "vf_max": 2.4, "vf_at_a": 0.02, "rs_ohm": 10},
                  "green": {"vf_min": 2.8, "vf_typ": 3.1, "vf_max": 3.4, "vf_at_a": 0.02, "rs_ohm": 10},
                  "blue": {"vf_min": 2.8, "vf_typ": 3.1, "vf_max": 3.4, "vf_at_a": 0.02, "rs_ohm": 10}},
       "ratings": {c: {"if_max_a": 0.02, "vr_max": 5} for c in ("red", "green", "blue")}}
COMMON_CATHODE = {"1": "cathode", "2": "anode_red", "3": "anode_green", "4": "anode_blue"}


def rgb_led(project, roles=None):
    """D7–D9 out, one RGB LED D10 in: pin 1 at +5V, pins 2–4 on LED5–LED7 (OUT5–OUT7 of U2). `roles` changes the
    roles of the parts entry, e.g. to the common cathode."""
    part = json.loads(json.dumps(RGB))
    for num, role in (roles or {}).items():
        part["pins"][num]["role"] = role
    project.save_part(RGB["lcsc"], part)
    g = project.graph()
    g["graph"]["components"] = [c for c in g["graph"]["components"] if c["designator"] not in ("D7", "D8", "D9")]
    g["graph"]["components"].append({"designator": "D10", "type": "led", "lcsc": RGB["lcsc"], "part": RGB["mpn"],
                                     "pins": {"1": "A", "2": "R", "3": "G", "4": "B"}, "value": "RGB"})
    for net in g["graph"]["nets"]:
        net["pins"] = [p for p in net["pins"] if p.split(".")[0] not in ("D7", "D8", "D9")]
    g["graph"]["layout"]["fixed"] = [d for d in g["graph"]["layout"]["fixed"] if d not in ("D7", "D8", "D9")] + ["D10"]
    project.net(g, "+5V")["pins"].append("D10.1")
    for pin, net in (("2", "LED5"), ("3", "LED6"), ("4", "LED7")):
        project.net(g, net)["pins"].append(f"D10.{pin}")
    project.save_graph(g)


def test_rgb_led_with_a_common_anode(project):
    rgb_led(project)
    out = simulate(project)
    assert not failing(out) and all(s["status"] == "ok" for s in out["scenarios"])
    assert len(out["checks"]) == 714                              # as many as the example with D7–D9
    for color, net in (("RED", "LED5"), ("GREEN", "LED6"), ("BLUE", "LED7")):
        mine = [c for c in out["checks"] if c["item"] == f"D10_{color}"]
        on = [c for c in mine if c["check"] == f"LED current ({net})"]
        assert len(on) == 6 and all(float(c["actual"].split()[0]) == pytest.approx(0.00945, rel=0.02) for c in on)
        assert len([c for c in mine if c["check"] == "LED dark"]) == 6          # idle: 3 supplies x 2 corners
        assert len([c for c in mine if c["id"] == "E-2"]) == 24                 # forward current, reverse voltage
    j1 = next(s for s in out["scenarios"] if s["name"] == "usb-min/all_on/vf-max")["sources"]["J1"]
    assert j1 == pytest.approx(0.114, abs=0.002)


def test_rgb_led_with_a_common_anode_by_leds_on(project):
    rgb_led(project)                                              # each cathode through 1 kΩ to GND, no driver output:
    project.use_library_part("C17513")                            # E-3 goes by the load's leds_on
    g = project.graph()
    for pin, net, des in (("2", "LED5", "R10"), ("3", "LED6", "R11"), ("4", "LED7", "R12")):
        project.net(g, net)["pins"].remove(f"D10.{pin}")
        g["graph"]["components"].append({"designator": des, "type": "resistor", "lcsc": "C17513",
                                         "pins": {"1": "1", "2": "2"}, "value": "1k"})
        g["graph"]["nets"].append({"name": f"K{pin}", "pins": [f"D10.{pin}", f"{des}.1"], "v": [0, 5.5]})
        project.net(g, "GND")["pins"].append(f"{des}.2")
    project.save_graph(g)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["loads"]["idle"]["leds_on"] = ["D10"]                     # the designator: all three colours
    sim["loads"]["all_on"]["leds_on"] = ["D10_RED"]               # one colour – green and blue light all the same
    out = simulate(project, sim)
    led = {(c["scenario"].split("/")[1], c["item"], c["check"], c["result"]) for c in out["checks"]
           if c["item"].startswith("D10_") and c["id"] == "E-3"}
    assert led == {("idle", f"D10_{x}", "LED on", "pass") for x in ("RED", "GREEN", "BLUE")} | {
        ("all_on", "D10_RED", "LED on", "pass"), ("all_on", "D10_GREEN", "LED dark", "fail"),
        ("all_on", "D10_BLUE", "LED dark", "fail")}


@pytest.mark.parametrize("roles,anode,cathode", [(None, "n__5v", "n_led{}"), (COMMON_CATHODE, "n_led{}", "n__5v")])
def test_rgb_led_layout_from_its_roles(project, roles, anode, cathode):
    from edakit.sim import netlist
    rgb_led(project, roles)                                       # the common pin is anode or cathode by its role
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sc = next(simrun.scenarios(sim))
    text, meta = netlist.build(Design.from_config(project.config()), sim, sc)
    for i, color in ((5, "red"), (6, "green"), (7, "blue")):
        a, k = anode.format(i), cathode.format(i)
        assert f"D_D10_{color} {a} {k} LED_C7371895_{color}_{sc['corner']}" in text.splitlines()
        assert meta["leds"][f"d_d10_{color}"]["des"] == "D10"


def resistor(ohm):
    """A test resistor, 0805 1/8 W, its value in its own entry (as the 0 Ω bridge of test_checks.py)."""
    return {"lcsc": f"C9{ohm:06d}", "mpn": f"test {ohm} Ω 0805", "kind": "resistor", "verified": {"by": "test"},
            "params": {"value_ohm": float(ohm)}, "ratings": {"p_max_w": 0.125, "v_max": 150},
            "pins": {"1": {"name": "1", "type": "passive", "role": "1"},
                     "2": {"name": "2", "type": "passive", "role": "2"}}}


def balanced(project, r10=68, r11=68):
    """Two LEDs in parallel on OUT7 of U2, each behind its balancing resistor: D9's cathode moves to D9_K with R10 to
    LED7, a second green LED D10 (anode at +5V) gets D10_K with R11 to LED7. 68 Ω keep the output at 1.0 V at usb-min;
    330 Ω (the block library's resistor until 65a1af9) would pull it below its 0.6 V knee."""
    g = project.graph()
    for des, ohm in (("R10", r10), ("R11", r11)):
        part = resistor(ohm)
        project.save_part(part["lcsc"], part)
        g["graph"]["components"].append({"designator": des, "type": "resistor", "lcsc": part["lcsc"],
                                         "pins": {"1": "1", "2": "2"}, "value": str(ohm)})
    g["graph"]["components"].append({"designator": "D10", "type": "led", "lcsc": "C2297", "part": "KT-0805G",
                                     "pins": {"1": "A", "2": "K"}, "value": "green"})
    project.net(g, "+5V")["pins"].append("D10.1")
    project.net(g, "LED7")["pins"] = ["U2.12", "R10.2", "R11.2"]
    for led, des in (("D9", "R10"), ("D10", "R11")):
        g["graph"]["nets"].append({"name": f"{led}_K", "pins": [f"{led}.2", f"{des}.1"], "v": [0, 5.5]})
    project.save_graph(g)


def test_leds_behind_balancing_resistors_count_on_their_output(project):
    balanced(project)
    out = simulate(project)
    assert not failing(out) and all(s["status"] == "ok" for s in out["scenarios"])
    assert len(out["checks"]) == 804                              # 786 before: no E-3 for D9, D10, LED7 in all_on
    for led in ("D9", "D10"):
        mine = [c for c in out["checks"] if c["item"] == led and c["id"] == "E-3"]
        on = [c for c in mine if c["check"] == "LED current (LED7)"]
        assert len(on) == 6                                       # all_on: 3 supplies x 2 corners, half of 9.45 mA
        assert all(float(c["actual"].split()[0]) == pytest.approx(0.00945 / 2, rel=0.02) for c in on)
        assert len([c for c in mine if c["check"] == "LED dark"]) == 6          # idle: the channel is off
    share = [c for c in out["checks"] if c["item"] == "LED7" and c["check"].startswith("current sharing")]
    assert len(share) == 6 and all(float(c["actual"]) == pytest.approx(1.0, abs=0.01) for c in share)


def test_unbalanced_leds_on_one_output(project):
    balanced(project, r11=330)                                    # D10 gets 1.92 mA, D9 7.48 mA at usb-min/vf-max
    out = simulate(project)
    bad = {(c["scenario"].split("/")[1], c["item"], c["check"]) for c in failing(out)}
    assert bad == {("all_on", "D10", "LED current (LED7)"), ("all_on", "LED7", "current sharing of parallel LEDs "
                                                                                "(min/mean)")}
    d10 = next(c for c in failing(out) if c["scenario"] == "usb-min/all_on/vf-max" and c["item"] == "D10")
    share = next(c for c in failing(out) if c["scenario"] == "usb-min/all_on/vf-max" and c["item"] == "LED7")
    assert (d10["actual"], d10["expected"], share["actual"]) == ("0.001922 A", "≥ 80% of 4.72 mA", "0.409")


def test_which_nets_are_behind_a_balancing_resistor(project):
    from test_checks import R, bridge, comp
    balanced(project)
    g = project.graph()
    bridge(project, g, "R12", "LED7", "R10.2")                    # R10 reaches OUT7 through a 0 Ω bridge as well
    part = resistor(68)
    g["graph"]["components"] += [comp("R13", part["lcsc"], R, value="68"), comp("R14", part["lcsc"], R, value="68")]
    project.net(g, "LED6")["pins"].append("R13.1")                # D10_K reaches OUT6 and OUT7: no single output
    project.net(g, "D10_K")["pins"].append("R13.2")
    project.net(g, "LED5")["pins"].append("R14.1")                # a resistor from OUT5 to ground: ground is never
    project.net(g, "GND")["pins"].append("R14.2")                 # behind an output
    project.save_graph(g)
    d = Design.from_config(project.config())
    assert simrun.behind_resistor(d, d.joined_nets(), {f"LED{i}" for i in range(8)}) == {"D9_K": "LED7"}


def read_back(project):
    """U2's SDO (pin 14) to GP7 (U1.10), an input that reads the chain back: net LED_SDO. GP7 is not under the MCU's
    outputs, so only SDO drives the net."""
    g = project.graph()
    project.free_pins(g, "U1.10")
    g["graph"]["nets"].append({"name": "LED_SDO", "pins": ["U2.14", "U1.10"], "v": [0, 3.4]})
    project.save_graph(g)


def test_driver_sdo_is_driven_low(project):
    read_back(project)
    out = simulate(project)
    assert not failing(out) and all(s["status"] == "ok" for s in out["scenarios"])
    assert len(out["checks"]) == 726                              # the example's 714 + LED_SDO's range in 12 scenarios
    sdo = [c for c in out["checks"] if c["item"] == "LED_SDO"]
    assert len(sdo) == 12 and all(c["actual"] == "0 V" for c in sdo)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["mcu"]["U1"]["pullups"].append("LED_SDO")                 # GP7's pull-up: the driven output holds it low
    out = simulate(project, sim)
    sdo = [c for c in out["checks"] if c["item"] == "LED_SDO"]
    assert not failing(out) and len(sdo) == 12
    assert all(float(c["actual"].split()[0]) == pytest.approx(3.3 * 50 / 50050, rel=0.01) for c in sdo)   # 3.3 mV


def test_driver_sdo_in_the_netlist(project):
    from edakit.sim import netlist
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sc = next(simrun.scenarios(sim))
    text, _ = netlist.build(Design.from_config(project.config()), sim, sc)
    assert not any(line.startswith("R_U2_14 ") for line in text.splitlines())
    read_back(project)                                            # unconnected: left out, as before; connected: 50 Ω
    text, _ = netlist.build(Design.from_config(project.config()), sim, sc)
    assert "R_U2_14 n_led_sdo 0 50" in text.splitlines()
