"""Every graph rule seen red once: build the fault into a copy of the example and expect exactly that check."""

import argparse
import json

import pytest

from edakit import checks
from edakit.design import Design


def run(project):
    cfg = project.config()
    return checks.run(Design.from_config(cfg), cfg)


def ids(rep):
    return {c for c, _ in rep.errors}


def test_example_is_clean(project):
    rep = run(project)
    assert rep.errors == []
    assert rep.pending == []
    assert {c for c, _, _ in rep.waived} == {"G-4"}


def test_g1_unconnected_pin(project):
    g = project.graph()
    net = project.net(g, "BTN")
    net["pins"].remove("SW1.1")
    project.save_graph(g)
    assert "G-1" in ids(run(project))


def test_g1_pin_in_two_nets(project):
    g = project.graph()
    project.net(g, "BTN")["pins"].append("R2.1")
    project.save_graph(g)
    assert any("used in 2 nets" in m for c, m in run(project).errors)


def test_g1_check_settings_and_ground_name_what_the_graph_has(project):
    g = project.graph()
    g["graph"]["checks"]["reverse_protect"] = ["J9"]
    g["graph"]["checks"]["pin_lock"] = {}            # pin_locks misspelt
    g["graph"]["ground"] = "0V"
    project.save_graph(g)
    msgs = [m for c, m in run(project).errors if c == "G-1"]
    assert "checks.reverse_protect: no part J9 in the graph" in msgs and "ground: no net 0V in the graph" in msgs
    assert any(m.startswith("checks: unknown key 'pin_lock'") for m in msgs)


def test_g2_pin_lock(project):
    g = project.graph()
    project.net(g, "LED_CLK")["pins"].remove("U1.4")
    project.net(g, "BTN")["pins"].append("U1.4")
    project.save_graph(g)
    assert "G-2" in ids(run(project))


def test_g3_voltage_above_pin_limit(project):
    g = project.graph()
    project.net(g, "BTN")["v"] = [0, 5.0]   # 5 V on a 3.63-V GPIO
    project.save_graph(g)
    assert "G-3" in ids(run(project))


def test_g4_floating_input(project):
    g = project.graph()
    oe = project.net(g, "LED_OE")
    oe["pins"].remove("R2.2")
    project.net(g, "3V3")["pins"].remove("R2.1")
    g["graph"]["components"] = [c for c in g["graph"]["components"] if c["designator"] != "R2"]
    project.save_graph(g)
    assert any("LED_OE" in m for c, m in run(project).errors if c == "G-4")


def test_g5_two_outputs(project):
    g = project.graph()
    sdo = {"name": "CLASH", "pins": ["U2.14", "U1.10"], "v": [0, 3.4]}
    project.comp(g, "U2")["nc"].remove("14")
    project.comp(g, "U1")["nc"].remove("10")
    g["graph"]["nets"].append(sdo)
    project.save_graph(g)
    rep = run(project)
    # U1.10 is bidirectional, U2.14 an output: one output – no G-5; make the MCU pin an output too
    part = project.part("C41407547")
    part["pins"]["10"]["type"] = "output"
    project.save_part("C41407547", part)
    rep = run(project)
    assert "G-5" in ids(rep)


def test_g6_missing_decoupling(project):
    g = project.graph()
    project.net(g, "3V3")["pins"].remove("C1.1")
    project.net(g, "GND")["pins"].remove("C1.2")
    g["graph"]["components"] = [c for c in g["graph"]["components"] if c["designator"] != "C1"]
    project.save_graph(g)
    assert "G-6" in ids(run(project))


def test_g8_capacitor_rating(project):
    part = project.part("C45783")
    part["ratings"]["v_max"] = 6.3   # 22 µF on a 5.5-V rail needs 8.25 V
    project.save_part("C45783", part)
    assert "G-8" in ids(run(project))


def test_g10_reverse_protection_bypassed(project):
    g = project.graph()
    project.net(g, "VIN")["pins"] += ["U1.39"]          # VSYS directly at the connector
    project.net(g, "+5V")["pins"].remove("U1.39")
    project.save_graph(g)
    assert any("U1.39" in m for c, m in run(project).errors if c == "G-10")


def test_p1_pin_name_differs(project):
    g = project.graph()
    project.comp(g, "U2")["pins"]["2"] = "DATA"
    project.save_graph(g)
    assert "P-1" in ids(run(project))


def test_p1_missing_parts_entry(project):
    (project.root / "hardware" / "parts" / "C17414.json").unlink()
    assert "P-1" in ids(run(project))


def test_g9_unverified_part_is_pending(project):
    part = project.part("C2297")
    part["verified"] = None
    project.save_part("C2297", part)
    rep = run(project)
    assert not rep.errors
    assert any(c == "G-9" for c, _ in rep.pending)


def test_waive_needs_reason_and_is_reported(project):
    g = project.graph()
    project.net(g, "LED_CLK").pop("waive")
    project.save_graph(g)
    assert "G-4" in ids(run(project))


# --- checks adopted from CircuitSmith's rule catalog and the reference project -------------------------------------
def comp(des, lcsc, pins, kind="resistor", **extra):
    return {"designator": des, "type": kind, "lcsc": lcsc, "pins": pins, **extra}


R = {"1": "1", "2": "2"}


def i2c_bus(project, g, name="SDA"):
    """A net SDA between two free MCU pins (GP7, GP8)."""
    project.free_pins(g, "U1.10", "U1.11")
    g["graph"]["nets"].append({"name": name, "pins": ["U1.10", "U1.11"], "v": [0, 3.4]})


def test_g11_i2c_line_without_pullup(project):
    g = project.graph()
    i2c_bus(project, g)
    project.save_graph(g)
    assert any("SDA" in m and "without a pull-up" in m for c, m in run(project).errors if c == "G-11")


def test_g11_pullup_in_range(project):
    g = project.graph()
    i2c_bus(project, g)
    g["graph"]["components"].append(comp("R10", "C17414", R, value="10k"))
    project.net(g, "SDA")["pins"].append("R10.2")
    project.net(g, "3V3")["pins"].append("R10.1")
    project.save_graph(g)
    assert "G-11" not in ids(run(project))
    for value, words in ((47000, "above"), (680, "below")):
        part = project.part("C17414")
        part["params"]["value_ohm"] = value
        project.save_part("C17414", part)
        assert any(words in m for c, m in run(project).errors if c == "G-11")


def test_g11_pullup_on_a_module_pin_counts(project):
    g = project.graph()
    i2c_bus(project, g)
    project.save_graph(g)
    part = project.part("C41407547")
    part["pins"]["10"].update(pull="up", pull_ohm=4700)
    project.save_part("C41407547", part)
    assert "G-11" not in ids(run(project))


def test_g11_bus_found_by_pin_name_and_role(project):
    g = project.graph()
    i2c_bus(project, g, name="BUS_A")       # a neutral net name: only the pin can make it I2C
    project.comp(g, "U1")["pins"]["10"] = "SDA"
    project.save_graph(g)
    part = project.part("C41407547")
    part["pins"]["10"]["name"] = "SDA"
    project.save_part("C41407547", part)
    assert "G-11" not in ids(run(project))  # the role gpio says what the pin is: no I2C
    del part["pins"]["10"]["role"]
    project.save_part("C41407547", part)
    assert "G-11" in ids(run(project))      # without a role its name counts


def strap(project, level, pull=None):
    """GP8 (U1.11) becomes a strapping pin that must be `level` at reset, on the net BOOT with GP7."""
    g = project.graph()
    project.free_pins(g, "U1.10", "U1.11")
    g["graph"]["nets"].append({"name": "BOOT", "pins": ["U1.10", "U1.11"], "v": [0, 3.4]})
    part = project.part("C41407547")
    part["pins"]["11"]["strap"] = level
    if pull:
        part["pins"]["11"]["pull"] = pull
    project.save_part("C41407547", part)
    return g


def test_g12_strap_held_by_internal_pull(project):
    project.save_graph(strap(project, "high", pull="up"))
    assert "G-12" not in ids(run(project))


def test_g12_strap_floats(project):
    project.save_graph(strap(project, "high"))
    assert any("nothing holds it" in m for c, m in run(project).errors if c == "G-12")


def test_g12_pull_against_the_boot_level(project):
    g = strap(project, "high", pull="up")
    g["graph"]["components"].append(comp("R10", "C17414", R, value="10k"))
    project.net(g, "BOOT")["pins"].append("R10.1")
    project.net(g, "GND")["pins"].append("R10.2")
    project.save_graph(g)
    assert any("R10 holds it low" in m for c, m in run(project).errors if c == "G-12")


def test_g12_strap_driven_by_an_output(project):
    g = strap(project, "low", pull="down")
    project.comp(g, "U2")["nc"].remove("14")   # SDO of the LED driver: a push-pull output
    project.net(g, "BOOT")["pins"].append("U2.14")
    project.save_graph(g)
    assert any("U2.14 drives it" in m for c, m in run(project).errors if c == "G-12")


def coil_stage(project, coil_part, coil_pins):
    """A coil between +5V and COIL_N, switched by an S8050 from GP7 – the buzzer stage of the reference project."""
    for lcsc in ("C2146", "C2480", "C17513"):
        project.use_library_part(lcsc)
    project.save_part(coil_part["lcsc"], coil_part)
    g = project.graph()
    project.free_pins(g, "U1.10")
    g["graph"]["components"] += [
        comp("X1", coil_part["lcsc"], {k: v["name"] for k, v in coil_part["pins"].items()}, kind=coil_part["kind"],
             nc=[k for k, v in coil_part["pins"].items() if v.get("role") not in coil_pins]),
        comp("Q1", "C2146", {"1": "B", "2": "E", "3": "C"}, kind="transistor"),
        comp("R10", "C17513", R, value="1k"), comp("R11", "C17414", R, value="10k")]
    plus, minus = (next(k for k, v in coil_part["pins"].items() if v.get("role") == r) for r in coil_pins)
    project.net(g, "+5V")["pins"].append(f"X1.{plus}")
    project.net(g, "GND")["pins"] += ["Q1.2", "R11.2"]
    g["graph"]["nets"] += [{"name": "COIL_N", "pins": [f"X1.{minus}", "Q1.3"], "v": [0, 5.5]},
                           {"name": "DRIVE", "pins": ["U1.10", "R10.1"], "v": [0, 3.4]},
                           {"name": "BASE", "pins": ["Q1.1", "R10.2", "R11.1"], "v": [0, 0.9]}]
    project.save_graph(g)


def add_flyback(project):
    g = project.graph()
    g["graph"]["components"].append(comp("D20", "C2480", {"1": "K", "2": "A"}, kind="diode"))
    project.net(g, "+5V")["pins"].append("D20.1")
    project.net(g, "COIL_N")["pins"].append("D20.2")
    project.save_graph(g)


BUZZER = {"lcsc": "C409842", "mpn": "YS-MBZ12085C05R42", "kind": "buzzer", "params": {"coil_ohm": 42},
          "ratings": {"v_max": 7}, "verified": {"by": "test"},
          "pins": {"1": {"name": "+", "type": "passive", "role": "plus"},
                   "2": {"name": "-", "type": "passive", "role": "minus"}}}
RELAY = {"lcsc": "C9000001", "mpn": "test relay 5 V", "kind": "relay", "verified": {"by": "test"},
         "params": {"coil_ohm": 70, "v_operate": 3.75, "v_release": 0.5}, "ratings": {"v_coil_max": 6.5, "i_max_a": 2},
         "pins": {"1": {"name": "A1", "type": "passive", "role": "coil_plus"},
                  "2": {"name": "A2", "type": "passive", "role": "coil_minus"},
                  "3": {"name": "COM", "type": "passive", "role": "common"},
                  "4": {"name": "NO", "type": "passive", "role": "no"},
                  "5": {"name": "NC", "type": "passive", "role": "nc"}}}


@pytest.mark.parametrize("part,roles", [(BUZZER, ("plus", "minus")), (RELAY, ("coil_plus", "coil_minus"))])
def test_g13_flyback_diode(project, part, roles):
    coil_stage(project, part, roles)
    assert any("X1" in m and "without a diode" in m for c, m in run(project).errors if c == "G-13")
    add_flyback(project)
    rep = run(project)
    assert "G-13" not in ids(rep) and not rep.errors


def test_g13_piezo_buzzer_has_no_coil(project):
    piezo = json.loads(json.dumps(BUZZER))
    del piezo["params"]["coil_ohm"]
    coil_stage(project, piezo, ("plus", "minus"))
    assert "G-13" not in ids(run(project))


def usb_c(project, rd=("C27834", "C27834"), shared=False):
    """The USB-C receptacle of the reference project feeding +5V, CC1/CC2 with resistors of the given LCSC numbers."""
    for lcsc in ("C456012", "C27834"):
        project.use_library_part(lcsc)
    g = project.graph()
    g["graph"]["components"].append(comp("J5", "C456012", {"A12": "GND", "A9": "VBUS", "A5": "CC1", "B5": "CC2",
                                                           "B9": "VBUS", "B12": "GND", "7": "EH"}, kind="connector",
                                         waive={"G-8": "vSafe5V up to 5.5 V"}))
    project.net(g, "+5V")["pins"] += ["J5.A9", "J5.B9"]
    project.net(g, "GND")["pins"] += ["J5.A12", "J5.B12", "J5.7"]
    if shared:
        g["graph"]["components"].append(comp("R20", rd[0], R))
        g["graph"]["nets"].append({"name": "CC", "pins": ["J5.A5", "J5.B5", "R20.1"], "v": [0, 5.5]})
        project.net(g, "GND")["pins"].append("R20.2")
    else:
        for i, (pin, lcsc) in enumerate(zip(("A5", "B5"), rd)):
            if lcsc is None:
                project.comp(g, "J5").setdefault("nc", []).append(pin)
                continue
            g["graph"]["components"].append(comp(f"R2{i}", lcsc, R))
            g["graph"]["nets"].append({"name": f"CC{i + 1}", "pins": [f"J5.{pin}", f"R2{i}.1"], "v": [0, 5.5]})
            project.net(g, "GND")["pins"].append(f"R2{i}.2")
    project.save_graph(g)


def test_g14_usb_c_with_its_own_rd_per_cc(project):
    usb_c(project)
    rep = run(project)
    assert "G-14" not in ids(rep) and not rep.errors


def test_g14_cc_not_connected(project):
    usb_c(project, rd=("C27834", None))
    assert any("CC2 not connected" in m for c, m in run(project).errors if c == "G-14")


def test_g14_cc_lines_share_one_resistor(project):
    usb_c(project, shared=True)
    assert any("on one net" in m for c, m in run(project).errors if c == "G-14")


def test_g14_wrong_rd(project):
    usb_c(project, rd=("C27834", "C17414"))   # 10 k on CC2
    assert any("CC2" in m and "needs 5.1 kΩ" in m for c, m in run(project).errors if c == "G-14")


def test_g14_silent_with_a_controller(project):
    usb_c(project, rd=("C27834", "C17414"))
    g = project.graph()
    project.free_pins(g, "U1.10")
    project.net(g, "CC2")["pins"].append("U1.10")   # an IC on the CC line: it handles CC itself
    project.save_graph(g)
    assert "G-14" not in ids(run(project))


# a bought USB-C breakout (the reference project's Soldered 333011): eight solder eyes, no CC resistors on it
BREAKOUT = {"mpn": "333011", "manufacturer": "Soldered", "kind": "module", "verified": {"by": "test"},
            "pins": {"1": {"name": "GND", "type": "ground"}, "2": {"name": "CC2", "type": "passive"},
                     "3": {"name": "SBU2", "type": "passive"}, "4": {"name": "D-", "type": "passive"},
                     "5": {"name": "D+", "type": "passive"}, "6": {"name": "SBU1", "type": "passive"},
                     "7": {"name": "CC1", "type": "passive"}, "8": {"name": "VUSB", "type": "power_output",
                                                                    "role": "vbus"}}}


def breakout(project, usb=None, cc_pins=True):
    """The breakout as a module J9 feeding +5V, only VUSB and GND wired; `usb` its params.usb_c; without `cc_pins`
    its entry leaves the CC eyes out, as a model of VBUS and GND only."""
    part = json.loads(json.dumps(BREAKOUT))
    if not cc_pins:
        part["pins"] = {"1": part["pins"]["1"], "8": part["pins"]["8"]}
    if usb is not None:
        part["params"] = {"usb_c": usb}
    (project.root / "hardware" / "parts" / "333011.json").write_text(json.dumps(part))
    g = project.graph()
    pins = {k: v["name"] for k, v in part["pins"].items()}
    g["graph"]["components"].append({"designator": "J9", "type": "module", "part": "333011", "bom": False,
                                     "pins": pins, "nc": [k for k in pins if k not in ("1", "8")],
                                     "easyeda_device": {"name": "333011"}})
    project.net(g, "+5V")["pins"].append("J9.8")
    project.net(g, "GND")["pins"].append("J9.1")
    project.save_graph(g)
    return g


def g14(rep):
    return [m for c, m in rep.errors if c == "G-14"]


def test_g14_breakout_as_a_module_without_the_field_is_not_checked(project):
    breakout(project)
    assert g14(run(project)) == []                     # as before: a module is no receptacle for G-14


def test_g14_breakout_without_rd_and_its_cc_pins_unconnected(project):
    breakout(project, {"cc": "none", "source": "Soldered 333011 KiCad data V1.2.0: no CC resistors"})
    assert g14(run(project)) == ["J9: CC1 not connected – a USB-C source switches VBUS on only with 5.1 kΩ to GND on "
                                 "each CC pin", "J9: CC2 not connected – a USB-C source switches VBUS on only with "
                                 "5.1 kΩ to GND on each CC pin"]


def test_g14_breakout_without_rd_gets_them_on_the_board(project):
    g = breakout(project, {"cc": "none"})
    project.use_library_part("C27834")
    project.comp(g, "J9")["nc"] = ["3", "4", "5", "6"]
    for i, pin in enumerate(("7", "2"), 1):              # CC1, CC2 each with a 5.1 kΩ to GND on the host board
        g["graph"]["components"].append(comp(f"R2{i}", "C27834", R))
        g["graph"]["nets"].append({"name": f"CC{i}", "pins": [f"J9.{pin}", f"R2{i}.1"], "v": [0, 5.5]})
        project.net(g, "GND")["pins"].append(f"R2{i}.2")
    project.save_graph(g)
    assert run(project).errors == []


def test_g14_receptacle_that_is_no_pin_of_the_graph(project):
    breakout(project, {"cc": "none"}, cc_pins=False)
    msg = ("J9: USB-C receptacle without CC termination (params.usb_c of 333011: cc none) and its CC lines are no pins "
           "of the graph – a USB-C source switches VBUS on only with 5.1 kΩ to GND on each CC pin")
    assert g14(run(project)) == [msg]
    g = project.graph()
    project.comp(g, "J9")["waive"] = {"G-14": "powered from a C-to-A cable only, the cable is part of the kit"}
    project.save_graph(g)
    rep = run(project)
    assert g14(rep) == [] and ("G-14", msg, "powered from a C-to-A cable only, the cable is part of the kit") \
        in rep.waived


@pytest.mark.parametrize("cc", ["rd_5k1", "controller"])
def test_g14_module_that_terminates_its_receptacle(project, cc):
    """An MCU module with USB-C on board (RP2350-Zero: 5.1 kΩ on CC1 and CC2) or a breakout with a PD controller."""
    part = project.part("C41407547")
    part["params"]["usb_c"] = {"cc": cc, "source": "module schematic"}
    project.save_part("C41407547", part)
    breakout(project, {"cc": cc}, cc_pins=False)
    assert g14(run(project)) == []


def test_g14_usb_c_field_needs_a_known_termination(project):
    breakout(project, {"cc": "5k1"}, cc_pins=False)
    assert g14(run(project)) == ["J9: params.usb_c of 333011 needs cc rd_5k1, controller or none, not '5k1'"]


def test_g4_mosfet_gate_needs_a_resistor(project):
    project.use_library_part("C15127")
    g = project.graph()
    project.free_pins(g, "U1.10")
    g["graph"]["components"] += [comp("Q5", "C15127", {"1": "G", "2": "S", "3": "D"}, kind="transistor"),
                                 comp("R10", "C17414", R, value="10k")]   # the switched load
    g["graph"]["nets"] += [{"name": "GATE", "pins": ["Q5.1", "U1.10"], "v": [0, 3.4]},
                           {"name": "SWITCHED", "pins": ["Q5.3", "R10.1"], "v": [0, 3.4]}]
    project.net(g, "3V3")["pins"].append("Q5.2")
    project.net(g, "GND")["pins"].append("R10.2")
    project.save_graph(g)
    assert [m for c, m in run(project).errors] == ["Q5: no resistor from the gate to its source or a rail – the MOSFET "
                                                    "is undefined while the firmware is not running"]
    g["graph"]["components"].append(comp("R11", "C17414", R, value="10k"))
    project.net(g, "GATE")["pins"].append("R11.1")
    project.net(g, "3V3")["pins"].append("R11.2")    # gate to source (3V3): off while the pin floats
    project.save_graph(g)
    assert not run(project).errors


def test_failed_checks_are_explained(project, capsys):
    g = project.graph()
    i2c_bus(project, g)
    project.save_graph(g)
    assert checks.main(project.config(), argparse.Namespace(release=False, json=None)) == 1
    out = capsys.readouterr().out
    assert "G-11 (I2C pull-ups):" in out and "why:" in out and "UM10204" in out
    assert "design hints open: H-1, H-3" in out


# --- 0 Ω bridges join their nets (feature proposal #1) --------------------------------------------------------------
BRIDGE = {"lcsc": "C9000002", "mpn": "test 0 Ω bridge 0805", "kind": "resistor", "verified": {"by": "test"},
          "params": {"value_ohm": 0.0}, "ratings": {"p_max_w": 0.125, "v_max": 150},
          "pins": {"1": {"name": "1", "type": "passive", "role": "1"},
                   "2": {"name": "2", "type": "passive", "role": "2"}}}


def bridge(project, g, des, net, pin, value_ohm=0.0):
    """`pin` moves from `net` to a new net <net>_B, joined to `net` by the resistor `des` – a 0 Ω bridge that crosses a
    track on a board with all tracks on one side."""
    project.save_part(BRIDGE["lcsc"], {**BRIDGE, "params": {"value_ohm": value_ohm}})
    g["graph"]["components"].append(comp(des, BRIDGE["lcsc"], R, value="0"))
    project.net(g, net)["pins"].remove(pin)
    project.net(g, net)["pins"].append(f"{des}.1")
    g["graph"]["nets"].append({"name": f"{net}_B", "pins": [f"{des}.2", pin], "v": project.net(g, net)["v"]})


def bridged(project, value_ohm=0.0):
    """The example with three bridges: R2 pulls OE up through R10, C1 reaches GND through R11, D9's cathode reaches
    OUT7 of the LED driver through R12."""
    g = project.graph()
    for des, net, pin in (("R10", "3V3", "R2.1"), ("R11", "GND", "C1.2"), ("R12", "LED7", "D9.2")):
        bridge(project, g, des, net, pin, value_ohm)
    project.save_graph(g)


def test_zero_ohm_bridges_join_their_nets(project, capsys):
    bridged(project)
    rep = run(project)
    assert rep.errors == [] and rep.pending == []
    assert {c for c, _, _ in rep.waived} == {"G-4"}
    assert checks.main(project.config(), argparse.Namespace(release=False, json=None)) == 0
    assert ("joined by 0 Ω bridges, checked as one net: GND = GND_B (R11); 3V3 = 3V3_B (R10); LED7 = LED7_B (R12)"
            in capsys.readouterr().out)


def test_a_resistor_joins_no_nets(project):
    bridged(project, value_ohm=10000)            # the same places with 10 kΩ: the pull-up and the capacitor are cut off
    assert sorted(run(project).errors) == [
        ("G-4", "LED_OE: only MCU pins drive this input – floating until the firmware runs"),
        ("G-6", "3V3: 1 IC supply pins (U2.16) but 0 capacitor(s) to GND")]


def test_joined_nets_are_one_net_for_the_checks(project):
    g = project.graph()
    project.free_pins(g, "U1.10")
    project.comp(g, "U2")["nc"].remove("14")
    g["graph"]["nets"].append({"name": "CLASH", "pins": ["U2.14", "U1.10"], "v": [0, 3.4]})
    bridge(project, g, "R13", "CLASH", "U1.10")  # SDO of the LED driver and an MCU output, a bridge between them
    project.save_graph(g)
    part = project.part("C41407547")
    part["pins"]["10"]["type"] = "output"
    project.save_part("C41407547", part)
    assert ("G-5", "CLASH: several outputs drive this net: U2.14, U1.10") in run(project).errors


def test_g1_purpose_says_what_the_board_is_for(project):
    g = project.graph()
    g["graph"]["purpose"]["use"] = "hobby"
    project.save_graph(g)
    assert any("purpose.use must be one of private, gift, sale" in m for c, m in run(project).errors if c == "G-1")


def test_a_part_bought_elsewhere_finds_its_entry_by_the_manufacturer_number(project):
    entry = project.part("C17414")                       # R2, 10 kΩ – now ordered at another distributor
    entry.pop("lcsc", None)
    entry["mpn"], entry["order"] = "RC0805FR-0710KL", {"rs": "223-0562"}
    (project.root / "hardware" / "parts" / "RC0805FR-0710KL.json").write_text(json.dumps(entry))
    g = project.graph()
    r2 = project.comp(g, "R2")
    del r2["lcsc"]
    r2["part"] = "RC0805FR-0710KL"
    project.save_graph(g)
    cfg = project.config()
    design = Design.from_config(cfg)
    assert design.entry_key("R2") == "RC0805FR-0710KL" and design.part("R2")["order"] == {"rs": "223-0562"}
    assert run(project).errors == []
    r2["part"] = "RC0805FR-0710KX"                       # a manufacturer number without an entry
    project.save_graph(g)
    assert ("P-1", "R2: no parts entry with mpn RC0805FR-0710KX") in run(project).errors


# --- G-15 pin functions (rule proposal #43) -------------------------------------------------------------------------
def g15(rep):
    return sorted(m for c, m in rep.errors if c == "G-15")


def test_g15_spi_roles_swapped(project):
    """The example before G-15: data on GP2 (SPI0 SCK), clock on GP3 (SPI0 TX) – fine bit-banged, not on SPI0."""
    g = project.graph()
    project.net(g, "LED_SDI")["pins"][0], project.net(g, "LED_CLK")["pins"][0] = "U1.4", "U1.5"
    g["graph"]["checks"]["pin_locks"].update({"U1.4": "LED_SDI", "U1.5": "LED_CLK"})
    project.save_graph(g)
    assert g15(run(project)) == [
        "LED_CLK: needs spi.sck, but U1.5 (GP3) has spi0.tx, uart0.rts, i2c1.scl, pwm1.b, uart0.rx",
        "LED_SDI: needs spi.tx, but U1.4 (GP2) has spi0.sck, uart0.cts, i2c1.sda, pwm1.a, uart0.tx"]
    for name in ("LED_SDI", "LED_CLK"):
        project.net(g, name)["waive"]["G-15"] = "bit-banged, no SPI peripheral"
    project.save_graph(g)
    rep = run(project)
    assert rep.errors == [] and sum(c == "G-15" for c, _, _ in rep.waived) == 2


def test_g15_one_bus_one_peripheral(project):
    g = project.graph()
    project.free_pins(g, "U1.15")                    # GP11: SPI1 TX
    project.net(g, "LED_SDI")["pins"][0] = "U1.15"
    project.comp(g, "U1")["nc"].append("5")
    project.save_graph(g)
    assert g15(run(project)) == ["bus LED: LED_CLK on spi0 (U1.4), LED_SDI on spi1 (U1.15) – the nets of one bus "
                                 "need one spi of U1"]


def pwm_pair(project, pins, hz):
    """Two PWM nets STAR and TONE on free pins of U1, each with a 10 kΩ load to GND."""
    g = project.graph()
    project.free_pins(g, *(f"U1.{p}" for p in pins))
    for i, (name, pin, f) in enumerate(zip(("STAR", "TONE"), pins, hz)):
        g["graph"]["components"].append(comp(f"R1{i}", "C17414", R, value="10k"))
        g["graph"]["nets"].append({"name": name, "pins": [f"U1.{pin}", f"R1{i}.1"], "v": [0, 3.4], "fn": "pwm",
                                   **({"pwm_hz": f} if f is not None else {})})
        project.net(g, "GND")["pins"].append(f"R1{i}.2")
    project.save_graph(g)


@pytest.mark.parametrize("hz,msg", [
    ((1000, [523, 2700]), "STAR (1000 Hz) and TONE (523–2700 Hz) share PWM slice 4 of U1 (U1.11, U1.12) – a slice "
                          "has one frequency, a net whose frequency changes needs a slice of its own"),
    ((1000, 500), "STAR (1000 Hz) and TONE (500 Hz) share PWM slice 4 of U1 (U1.11, U1.12) – a slice has one "
                  "frequency"),
    ((1000, None), "STAR (1000 Hz) and TONE (pwm_hz missing) share PWM slice 4 of U1 (U1.11, U1.12) – give both "
                   "their pwm_hz: a slice has one frequency"),
])
def test_g15_pwm_nets_of_one_slice_share_one_frequency(project, hz, msg):
    pwm_pair(project, ("11", "12"), hz)               # GP8 and GP9: slice 4, like the star and the buzzer of the origin
    assert g15(run(project)) == [msg]


def test_g15_pwm_nets_of_one_slice_at_one_frequency(project):
    pwm_pair(project, ("11", "12"), (1000, 1000))
    rep = run(project)
    assert rep.errors == [] and not [m for c, m in rep.notes if c == "G-15"]


def test_g15_pwm_channel_used_twice(project):
    pwm_pair(project, ("1", "21"), (1000, 1000))      # GP0 and GP16: both PWM_A_0
    assert g15(run(project)) == ["STAR and TONE on the same PWM channel pwm0.a of U1 (U1.1, U1.21) – one output "
                                 "for both"]
    g = project.graph()                               # GP21 is PWM_B_2, the channel of LED_OE on GP5
    project.net(g, "TONE")["pins"][0] = "U1.27"
    project.comp(g, "U1")["nc"] = [p for p in project.comp(g, "U1")["nc"] if p != "27"] + ["21"]
    project.save_graph(g)
    assert g15(run(project)) == ["LED_OE and TONE on the same PWM channel pwm2.b of U1 (U1.7, U1.27) – one output "
                                 "for both"]


def test_g15_adc_only_on_adc_pins(project):
    g = project.graph()
    project.free_pins(g, "U1.10", "U1.31")
    g["graph"]["components"].append(comp("R10", "C17414", R, value="10k"))
    g["graph"]["nets"].append({"name": "SENSE", "pins": ["U1.10", "R10.1"], "v": [0, 3.4], "fn": "adc"})
    project.net(g, "3V3")["pins"].append("R10.2")
    project.comp(g, "U1")["nc"].append("31")
    project.save_graph(g)
    assert g15(run(project)) == ["SENSE: needs adc, but U1.10 (GP7) has spi0.tx, uart1.rts, i2c1.scl, pwm3.b, "
                                 "uart1.rx"]
    project.net(g, "SENSE")["pins"][0] = "U1.31"      # GP26_ADC0
    project.comp(g, "U1")["nc"] = [p for p in project.comp(g, "U1")["nc"] if p != "31"] + ["10"]
    project.save_graph(g)
    assert run(project).errors == []


def test_g15_used_pin_has_no_free_function(project):
    g = project.graph()
    project.free_pins(g, "U1.TP5")                    # GPIO25: the module's LED
    project.net(g, "LED_OE")["pins"].append("U1.TP5")
    project.net(g, "LED_OE")["pins"].remove("U1.7")
    project.comp(g, "U1")["nc"].append("7")
    project.save_graph(g)
    assert g15(run(project)) == ["LED_OE: needs pwm, but U1.TP5 (GPIO25/LED) has no free function"]


def test_g15_pin_without_functions_is_a_note(project):
    part = project.part("C41407547")
    del part["pins"]["5"]["functions"]
    project.save_part("C41407547", part)
    rep = run(project)
    assert rep.errors == []
    assert ("G-15", "LED_SDI: needs spi.tx, but no pin on it has functions in its parts entry – not checked") \
        in rep.notes


def test_g15_unknown_fn_and_pwm_hz(project):
    g = project.graph()
    project.net(g, "LED_SDI")["fn"] = "spi.mosi"
    project.net(g, "LED_OE")["pwm_hz"] = "fast"
    project.save_graph(g)
    assert g15(run(project)) == [
        "LED_OE: pwm_hz must be a frequency in Hz or [min, max], not 'fast'",
        "LED_SDI: unknown fn 'spi.mosi' (known: pwm, adc, spi.sck, spi.tx, spi.rx, spi.cs, i2c.sda, i2c.scl, uart.tx, "
        "uart.rx)"]


def test_g15_sees_through_0_ohm_bridges(project):
    g = project.graph()
    project.net(g, "LED_SDI")["pins"][0], project.net(g, "LED_CLK")["pins"][0] = "U1.4", "U1.5"
    bridge(project, g, "R13", "LED_SDI", "U2.2")      # the driver's SDI behind a bridge, fn stated there
    sdi_b = project.net(g, "LED_SDI_B")
    sdi_b["fn"] = project.net(g, "LED_SDI").pop("fn")
    project.save_graph(g)
    assert "LED_SDI: needs spi.tx, but U1.4 (GP2) has spi0.sck, uart0.cts, i2c1.sda, pwm1.a, uart0.tx" \
        in g15(run(project))


# --- G-16 ground and supply pins (rule proposal #44) ----------------------------------------------------------------
def g16(rep):
    return sorted(m for c, m in rep.errors if c == "G-16")


def move(project, g, pins, to, v=(0, 3.4)):
    """Take `pins` out of their nets and put them on the net `to` (created if it does not exist)."""
    for net in g["graph"]["nets"]:
        net["pins"] = [p for p in net["pins"] if p not in pins]
    if not any(n["name"] == to for n in g["graph"]["nets"]):
        g["graph"]["nets"].append({"name": to, "pins": [], "v": list(v)})
    project.net(g, to)["pins"] += pins


def test_g16_supply_rail_split_by_a_typo(project):
    g = project.graph()
    move(project, g, ["U2.16", "C1.1"], "3.3V")       # 3.3V instead of 3V3: G-6 is content, the capacitor came along
    project.save_graph(g)
    rep = run(project)
    assert g16(rep) == ["U2.16 (VDD) on 3.3V: nothing supplies this net"] and "G-6" not in ids(rep)


def test_g16_ground_pin_on_a_net_of_its_own(project):
    g = project.graph()
    move(project, g, ["U2.1", "R1.2"], "GND_U2", v=(0, 0))
    project.save_graph(g)
    assert g16(run(project)) == ["U2.1 (GND) on GND_U2, not on GND"]
    g["graph"]["grounds"] = ["GND_U2"]                 # a ground that is separate on purpose
    project.save_graph(g)
    assert g16(run(project)) == []
    g["graph"]["grounds"] = ["AGND"]
    project.save_graph(g)
    assert "grounds: no net AGND in the graph" in g16(run(project))


INDUCTOR = {"lcsc": "C9000003", "mpn": "test ferrite bead 0805", "kind": "inductor", "verified": {"by": "test"},
            "params": {"value_h": 1e-6, "dcr_ohm": 0.1},
            "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}}}


def test_g16_ground_and_supply_through_a_ferrite(project):
    project.save_part(INDUCTOR["lcsc"], INDUCTOR)
    g = project.graph()
    move(project, g, ["U2.1", "R1.2"], "GND_U2", v=(0, 0))
    move(project, g, ["U2.16", "C1.1"], "3V3_U2")
    g["graph"]["components"] += [comp("L1", INDUCTOR["lcsc"], R, kind="inductor"),
                                 comp("L2", INDUCTOR["lcsc"], R, kind="inductor")]
    project.net(g, "GND")["pins"].append("L1.1")
    project.net(g, "GND_U2")["pins"].append("L1.2")
    project.net(g, "3V3")["pins"].append("L2.1")
    project.net(g, "3V3_U2")["pins"].append("L2.2")
    project.save_graph(g)
    assert g16(run(project)) == []


def test_g16_supply_and_signal_pins_swapped(project):
    g = project.graph()
    project.net(g, "3V3")["pins"][project.net(g, "3V3")["pins"].index("U2.16")] = "U2.3"
    project.net(g, "LED_CLK")["pins"][project.net(g, "LED_CLK")["pins"].index("U2.3")] = "U2.16"
    project.save_graph(g)
    assert g16(run(project)) == ["U2.16 (VDD) on LED_CLK: nothing supplies this net"]


def test_g16_supply_pin_on_ground(project):
    g = project.graph()
    move(project, g, ["U2.16"], "GND")
    project.save_graph(g)
    assert g16(run(project)) == ["U2.16 (VDD) on GND: a supply pin on ground"]


@pytest.mark.parametrize("value_ohm,found", [(100, False), (150, True)])
def test_g16_supply_through_a_resistor_up_to_100_ohm(project, value_ohm, found):
    """U2 behind a series resistor from 3V3: a shunt or a filter passes, a larger one is no supply path."""
    project.save_part("C9000004", {**BRIDGE, "lcsc": "C9000004", "params": {"value_ohm": value_ohm}})
    g = project.graph()
    move(project, g, ["U2.16", "C1.1"], "3V3_U2")
    g["graph"]["components"].append(comp("R20", "C9000004", R))
    project.net(g, "3V3")["pins"].append("R20.1")
    project.net(g, "3V3_U2")["pins"].append("R20.2")
    project.save_graph(g)
    assert g16(run(project)) == (["U2.16 (VDD) on 3V3_U2: nothing supplies this net"] if found else [])
    project.net(g, "3V3_U2")["waive"] = {"G-16": "U2 runs from 3V3 through R20 on purpose"}
    project.save_graph(g)
    assert g16(run(project)) == []


def test_g16_supply_only_through_a_diode_in_forward_direction(project):
    g = project.graph()
    project.net(g, "VIN")["pins"][project.net(g, "VIN")["pins"].index("D1.2")] = "D1.1"   # D1 reversed: blocks VIN
    project.net(g, "+5V")["pins"][project.net(g, "+5V")["pins"].index("D1.1")] = "D1.2"
    project.save_graph(g)
    assert g16(run(project)) == ["U1.39 (VSYS) on +5V: nothing supplies this net"]


# --- G-17 fuse against what it protects (rule proposal #45) ---------------------------------------------------------
def g17(rep):
    return sorted(m for c, m in rep.errors if c == "G-17"), sorted(m for c, m in rep.warnings if c == "G-17")


def fused_input(project):
    """F1 (C495353: hold 1.5 A, trip 3.0 A) behind J1 (JST PH, 2 A): VIN -> F1 -> VIN_F -> D1."""
    project.use_library_part("C495353")
    g = project.graph()
    g["graph"]["components"].append(comp("F1", "C495353", R, kind="fuse", value="1.5A"))
    vin = project.net(g, "VIN")
    vin["pins"][vin["pins"].index("D1.2")] = "F1.1"
    g["graph"]["nets"].append({"name": "VIN_F", "pins": ["F1.2", "D1.2"], "v": [0, 5.5]})
    project.save_graph(g)
    return g


def set_sim(project, **kv):
    path = project.root / "hardware" / "sim.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), **kv}))


def test_g17_trip_current_above_the_connector_is_a_warning(project):
    fused_input(project)
    assert g17(run(project)) == ([], ["F1: trips at 3 A, above the 2 A of J1 – an overload in between may last for "
                                      "minutes"])


def test_g17_hold_current_at_the_lowest_ambient(project):
    fused_input(project)
    set_sim(project, ambient_min_c=-40)               # C495353 holds 2.2 A at -40 °C
    assert g17(run(project))[0] == ["F1: holds 2.2 A at -40 °C, above the 2 A of J1 – an overload in between never "
                                    "trips it"]
    set_sim(project, ambient_min_c=-30)               # 2.1 A between the table's -40 and -20 °C
    assert g17(run(project))[0] == ["F1: holds 2.1 A at -30 °C, above the 2 A of J1 – an overload in between never "
                                    "trips it"]


def test_g17_cable_and_switch_in_the_path(project):
    g = fused_input(project)
    project.save_part("C9000005", {"lcsc": "C9000005", "mpn": "test slide switch", "kind": "switch",
                                   "verified": {"by": "test"}, "ratings": {"i_max_a": 0.5, "v_max": 12},
                                   "pins": {"1": {"name": "1", "type": "passive", "role": "common"},
                                            "2": {"name": "2", "type": "passive", "role": "throw_a"}}})
    g["graph"]["components"] += [comp("SW2", "C9000005", R, kind="switch"),
                                 comp("J2", "C131337", {"1": "1", "2": "2"}, kind="connector", bom=False)]
    project.net(g, "VIN_F")["pins"][project.net(g, "VIN_F")["pins"].index("D1.2")] = "SW2.1"
    g["graph"]["nets"].append({"name": "VIN_S", "pins": ["SW2.2", "D1.2"], "v": [0, 5.5]})
    project.net(g, "VIN")["pins"].append("J2.1")      # J2 – cable W1 – J1: the supply from another board
    project.net(g, "GND")["pins"].append("J2.2")
    g["graph"]["cables"] = [{"name": "W1", "from": "J2", "to": "J1", "pins": {"1": "1", "2": "2"}, "i_max_a": 1.0}]
    project.save_graph(g)
    errors, warnings = g17(run(project))
    assert errors == ["F1: holds 1.5 A, above the 0.5 A of SW2 – an overload in between never trips it",
                      "F1: holds 1.5 A, above the 1 A of cable W1 – an overload in between never trips it"]
    assert warnings == ["F1: trips at 3 A, above the 2 A of J1 – an overload in between may last for minutes",
                        "F1: trips at 3 A, above the 2 A of J2 – an overload in between may last for minutes"]
    project.comp(g, "F1")["waive"] = {"G-17": "normal current 0.2 A, a short trips within 100 ms"}
    project.save_graph(g)
    rep = run(project)
    assert g17(rep) == ([], []) and sum(c == "G-17" for c, _, _ in rep.waived) == 4


def test_g17_usb_c_sink_block(project):
    """The block's receptacle carries 2.5 A (two ground contacts at 1.25 A) – above the fuse's hold, below its trip."""
    from edakit import block
    block.add(project.config(), "usb-c-sink", "USB", {"vbus": "+5V"})
    rep = run(project)
    assert g17(rep) == ([], ["F1: trips at 3 A, above the 2.5 A of J2 – an overload in between may last for minutes"])
    part = project.part("C456012")
    part["ratings"]["i_max_a"] = 1.25                 # one ground contact for the whole receptacle
    project.save_part("C456012", part)
    assert g17(run(project))[0] == ["F1: holds 1.5 A, above the 1.25 A of J2 – an overload in between never trips it"]


def test_g17_needs_the_ratings(project):
    fused_input(project)
    part = project.part("C495353")
    del part["ratings"]["i_hold_a"], part["ratings"]["i_trip_a"]
    project.save_part("C495353", part)
    assert g17(run(project)) == ([], [])
