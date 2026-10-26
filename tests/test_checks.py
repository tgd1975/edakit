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
    project.net(g, "LED_CLK")["pins"].remove("U1.5")
    project.net(g, "BTN")["pins"].append("U1.5")
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
