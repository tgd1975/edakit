"""Cell current (maker-coverage CK-18), a driver's supply-pin current (CK-21), an MCU's clock against its supply
(CK-23), USB-C data in both orientations (CK-12), lines that leave on a cable (CK-16), a key matrix (CK-19), and the
hints of the domains power and cables and of LED PWM (HT-1, HT-4, HT-6, HT-9, HT-11)."""

import shutil

import pytest
from test_sim import simulate

from edakit import engines, profile
from edakit.design import Design

ngspice = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


def found(project, code, grade=None):
    cfg = project.config()
    return [f for f in engines.run(Design.from_config(cfg), cfg).findings if f.code == code
            and (grade is None or f.grade == grade)]


def rows(out, item, check):
    return [c for c in out["checks"] if c["item"] == item and c["check"] == check]


# --- simulation: CK-21, CK-23 -------------------------------------------------------------------------------------------
@ngspice
def test_the_drivers_ground_pin_carries_all_outputs(project):
    """U2's eight channels at about 9.5 mA each and its own supply current through its pins – a limit of 50 mA (a
    value for the test) is exceeded with all on: LIM.i/supply_pin, a warning, reads warn."""
    part = project.part("C90107")
    part["limits"]["i_supply_pin_max_a"] = 0.05
    project.save_part("C90107", part)
    r = rows(simulate(project), "U2", "current through its supply pins (all outputs together)")
    assert {c["result"] for c in r if "/all_on/" in c["scenario"]} == {"warn"}
    assert {c["result"] for c in r if "/idle/" in c["scenario"]} == {"pass"}


@ngspice
def test_the_clock_against_the_supply(project):
    """U1 at 3.3 V (its on-board regulator): a clock of 200 MHz above the 150 MHz a table of the test allows there
    (LIM.range/clock, a warning: warn)."""
    part = project.part("C41407547")
    part["values"]["f_clock_hz"] = 200e6
    part["limits"]["f_max_hz"] = {"1.8": 100e6, "3.0": 150e6}
    project.save_part("C41407547", part)
    r = rows(simulate(project), "U1", "clock within what its supply allows")
    assert r and {c["result"] for c in r} == {"warn"} and r[0]["actual"].startswith("200 MHz at 3.3")
    part["values"]["f_clock_hz"] = 150e6
    project.save_part("C41407547", part)
    assert {c["result"] for c in rows(simulate(project), "U1", "clock within what its supply allows")} == {"pass"}


# --- CK-12 -------------------------------------------------------------------------------------------------------------
def test_usb_c_data_must_join_both_rows(project):
    part = project.part("C131337")                          # J1 as a receptacle with data, for the test
    part["pins"].update({"3": {"name": "A6", "type": "passive", "role": "dp_a"},
                         "4": {"name": "B6", "type": "passive", "role": "dp_b"}})
    project.save_part("C131337", part)
    g = project.graph()
    project.comp(g, "J1")["pins"].update({"3": "A6", "4": "B6"})
    project.free_pins(g, "U1.11")
    g["graph"]["nets"].append({"name": "USB_DP", "pins": ["J1.3", "U1.11"], "v": [0, 3.4]})
    project.comp(g, "J1").setdefault("nc", []).append("4")
    project.save_graph(g)
    assert "usb" in profile.suggested(Design.from_config(project.config()))
    texts = [f.text for f in found(project, "REQ.missing", "usb_data")]
    assert texts == ["J1: D+ of both rows not joined (dp_a on USB_DP, dp_b on nothing) – turned round, the plug has no "
                     "data"]


# --- CK-16, HT-1 -------------------------------------------------------------------------------------------------------
def test_a_line_on_a_cable_straight_to_a_pin(project):
    from test_bought import usb_board
    g = usb_board(project)
    project.comp(g, "J9")["nc"].remove("3")                 # a free contact of the breakout carries a signal
    project.free_pins(g, "U1.11")
    j1 = project.part("C131337")
    j1["pins"]["3"] = {"name": "3", "type": "passive"}
    project.save_part("C131337", j1)
    project.comp(g, "J1")["pins"]["3"] = "3"
    g["graph"]["nets"].append({"name": "REMOTE", "pins": ["J9.3", "J1.3", "U1.11"], "v": [0, 3.4]})
    g["graph"]["cables"][0]["pins"]["3"] = "3"
    project.save_graph(g)
    assert "cables" in profile.suggested(Design.from_config(project.config()))
    assert [f.text for f in found(project, "REQ.missing", "leave")] == [
        "REMOTE: runs through cable W1 straight to U1.11 – no series resistance on the board"]
    assert [f.place for f in found(project, "HINT.cable_line")] == ["REMOTE"]


# --- CK-19 -------------------------------------------------------------------------------------------------------------
def key(g, des, row, col, diode=None, cathode_to="row"):
    """`des` (a button C318884 of the example) from `row` to an internal net, a diode (C8678) on to `col`."""
    inner = f"K_{des}"
    g["graph"]["components"].append({"designator": des, "type": "button", "lcsc": "C318884",
                                     "pins": {"1": "1", "2": "2", "3": "3", "4": "4"}, "nc": ["3", "4"]})
    nets = {n["name"]: n for n in g["graph"]["nets"]}
    for name, kind in ((row, "row"), (col, "col")):
        if name not in nets:
            nets[name] = {"name": name, "pins": [], "v": [0, 3.4], "matrix": kind}
            g["graph"]["nets"].append(nets[name])
    if diode:
        g["graph"]["components"].append({"designator": diode, "type": "diode", "lcsc": "C8678",
                                         "pins": {"1": "K", "2": "A"}})
        nets[row]["pins"].append(f"{des}.1")
        k, a = ("1", "2")
        to_inner, to_col = (f"{diode}.{a}", f"{diode}.{k}") if cathode_to == "col" else (f"{diode}.{k}", f"{diode}.{a}")
        g["graph"]["nets"].append({"name": inner, "pins": [f"{des}.2", to_inner], "v": [0, 3.4]})
        nets[col]["pins"].append(to_col)
    else:
        nets[row]["pins"].append(f"{des}.1")
        nets[col]["pins"].append(f"{des}.2")


def test_a_key_without_its_diode(project):
    g = project.graph()
    key(g, "SW8", "ROW0", "COL0", diode="D8")
    key(g, "SW9", "ROW0", "COL1")
    project.save_graph(g)
    assert [f.text for f in found(project, "REQ.missing", "matrix")] == [
        "SW9: joins a row and a column without a diode – keys pressed together ghost"]


def test_diodes_pointing_both_ways(project):
    g = project.graph()
    key(g, "SW8", "ROW0", "COL0", diode="D8")
    key(g, "SW9", "ROW0", "COL1", diode="D9", cathode_to="col")
    project.save_graph(g)
    texts = [f.text for f in found(project, "REQ.forbidden", "matrix")]
    assert len(texts) == 1 and texts[0].startswith("matrix: the diodes point both ways")


# --- hints -------------------------------------------------------------------------------------------------------------
def test_pwm_on_leds_and_the_power_domain(project):
    g = project.graph()
    project.net(g, "LED_OE")["pwm_hz"] = 490
    project.save_graph(g)
    assert [f.place for f in found(project, "HINT.flicker")] == []          # OE switches U2, no LED on its net
    g["graph"]["components"].append({"designator": "D10", "type": "led", "lcsc": "C2297", "pins": {"1": "1", "2": "2"}})
    project.net(g, "LED_OE")["pins"].append("D10.2")
    project.net(g, "GND")["pins"].append("D10.1")
    project.save_graph(g)
    assert [f.place for f in found(project, "HINT.flicker")] == ["LED_OE"]


# --- CK-18 and the domain power ----------------------------------------------------------------------------------------
@ngspice
def test_a_cell_above_its_current(project):
    """The cells of test_sim_supply on +5V alone: everything runs from them – above an i_max_a of 50 mA (a value for
    the test) with all LEDs on (LIM.i/cell, a warning: warn); the holder suggests the domain power, but not its polarity hint – PATH.reverse checks
    every holder by its kind."""
    from test_sim_supply import cells_on_the_rail
    sim = cells_on_the_rail(project)
    sim["cells"]["fresh"]["i_max_a"] = 0.05
    out = simulate(project, sim)
    cell = [c for c in out["checks"] if c["item"] == "BT1" and c["check"] == "current from the cell"
            and c["scenario"].startswith("cells/")]
    assert {c["result"] for c in cell if "/all_on/" in c["scenario"]} == {"warn"}
    assert {c["id"] for c in cell} == {"LIM.i"}
    assert "power" in profile.suggested(Design.from_config(project.config()))
    assert "BT1" not in [f.place for f in found(project, "HINT.input_polarity")]



@ngspice
def test_an_accept_on_the_holder_takes_the_cell_current(project):
    """walkthrough-gaps C1: the current from a cell above its i_max_a is accepted on the holder, as a finding at any
    other part – `accept: {"LIM.i/cell": …}` on BT1 (the walkthrough's coin cell, pressed for a moment) –, and the
    comparison's row says so: the gate counts it waived, not failed."""
    from test_sim_supply import cells_on_the_rail
    sim = cells_on_the_rail(project)
    sim["cells"]["fresh"]["i_max_a"] = 0.05

    def cell():
        return [f for f in simulate(project, sim)["findings"] if f["code"] == "LIM.i" and f.get("grade") == "cell"]
    assert cell() and not any(f.get("accepted") for f in cell())
    g = project.graph()
    project.comp(g, "BT1")["accept"] = {"LIM.i/cell": "a test: the load is short"}
    project.save_graph(g)
    assert cell() and all(f.get("accepted") == "a test: the load is short" for f in cell())
    rows = [c for c in simulate(project, sim)["checks"] if c["item"] == "BT1" and c["check"] == "current from the cell"
            and c["result"] != "pass"]                   # the gate counts these rows: accepted, a row is waived
    assert rows and {(c["result"], c.get("reason")) for c in rows} == {("waived", "a test: the load is short")}

def test_a_plug_whose_polarity_nobody_checks(project):
    """HT-6: a supply connector the graph does not mark as reversible gets the polarity hint; marked, PATH.reverse
    checks it and the hint is quiet. A battery holder never gets it – the walkthrough of handbook 17 had to accept it
    for a CR2032 that PATH.reverse had already checked."""
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("[project]", '[project]\ndomains = ["power"]', 1))
    part = project.part("C131337")                       # the JST PH input, pin 1 its supply
    part["pins"]["1"]["role"] = "vbus"
    project.save_part("C131337", part)
    assert "J1" not in [f.place for f in found(project, "HINT.input_polarity")]
    g = project.graph()
    del project.comp(g, "J1")["source"]
    project.save_graph(g)
    assert "J1" in [f.place for f in found(project, "HINT.input_polarity")]
