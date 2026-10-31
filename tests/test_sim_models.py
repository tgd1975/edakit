"""Behaviour models of schema-gaps E2–E4 and E6, each doing what its datasheet says (values in the library entries,
read 2026-10-31): a bridge driver's outputs follow its truth table and drop I × r_on (DRV8833, TB6612), a linear
charger charges with prog_v / R_PROG, less below its precondition threshold, and holds its float voltage (MCP73831,
TP4056), a cell protection IC drives its two MOSFETs and switches the cell off below overdischarge and above
overcharge (DW01A with both channels of an FS8205A), a buck-boost regulator holds its output below and above it."""

import json
import shutil

import pytest
from reference import MOTOR
from test_sim import simulate

from edakit import library
from edakit.engines.limits import charge_currents
from edakit.design import Design

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


def load_sim(project):
    return json.loads((project.root / "hardware" / "sim.json").read_text(encoding="utf-8"))


def comp(des, key, nc=()):
    e = library.entry(key)
    c = {"designator": des, "type": "ic" if e["kind"] in ("ic", "module") else e["kind"], "lcsc": key,
         "pins": {n: p["name"] for n, p in e["pins"].items()}}
    if nc:
        c["nc"] = list(nc)
    return c


def resistor(project, key, ohm):
    r = project.part("C17414")
    r.update(lcsc=key, mpn=f"test resistor {ohm:g}")
    r["values"]["value_ohm"] = ohm
    project.save_part(key, r)
    return {"type": "resistor", "lcsc": key, "pins": {"1": "1", "2": "2"}}


def nets(g, **named):
    for name, (pins, v) in named.items():
        g["graph"]["nets"].append({"name": name, "pins": pins, "v": list(v)})


def scenario(out, load, supply="usb-nom", corner="max"):
    return next(s for s in out["scenarios"] if s["name"].startswith(f"{supply}/{load}/") and s["name"].endswith(corner))


# --- E2: bridge drivers ---------------------------------------------------------------------------------------------
def drv8833(project):
    """U9 DRV8833 on +5V: nSLEEP on 3V3 (awake), AIN1 on SIG (GP7), AIN2 on SIG2 (GP8), the 33 Ω motor M9 between
    AOUT1 (MA) and AOUT2 (MB), AISEN/BISEN and BIN1/BIN2 on GND."""
    for key in ("C50506",):
        project.save_part(key, library.entry(key))
    project.save_part(MOTOR["lcsc"], MOTOR)
    g = project.graph()
    project.free_pins(g, "U1.10", "U1.11")
    g["graph"]["components"] += [comp("U9", "C50506", nc=["5", "7", "8", "11", "14"]),
                                 {"designator": "M9", "type": "motor", "lcsc": MOTOR["lcsc"], "pins": {"1": "+", "2": "-"}}]
    project.net(g, "+5V")["pins"] += ["U9.12"]
    project.net(g, "3V3")["pins"] += ["U9.1"]
    project.net(g, "GND")["pins"] += ["U9.3", "U9.6", "U9.9", "U9.10", "U9.13", "U9.17"]
    nets(g, SIG=(["U1.10", "U9.16"], (0, 3.4)), SIG2=(["U1.11", "U9.15"], (0, 3.4)),
         MA=(["U9.2", "M9.1"], (0, 5.5)), MB=(["U9.4", "M9.2"], (0, 5.5)))
    project.save_graph(g)
    sim = load_sim(project)
    sim["mcu"]["U1"]["outputs"] += ["SIG", "SIG2"]
    sim["loads"] = {"forward": {"gpio": {"LED_OE": 1, "SIG": 1, "SIG2": 0}, "leds_on": []},
                    "reverse": {"gpio": {"LED_OE": 1, "SIG": 0, "SIG2": 1}, "leds_on": []},
                    "brake": {"gpio": {"LED_OE": 1, "SIG": 1, "SIG2": 1}, "leds_on": []},
                    "coast": {"gpio": {"LED_OE": 1, "SIG": 0, "SIG2": 0}, "leds_on": []}}
    sim["report"] = ["+5V", "MA", "MB"]
    return sim


def test_a_bridge_follows_its_truth_table_and_drops_i_times_r_on(project):
    out = simulate(project, drv8833(project))
    e = library.entry("C50506")["values"]
    for load in ("forward", "reverse", "brake", "coast"):
        sc = scenario(out, load)
        assert sc["status"] == "ok", (load, sc)
        vm, ma, mb = (sc["nets"][n] for n in ("+5V", "MA", "MB"))
        i = (vm) / (e["r_on_high_ohm"] + e["r_on_low_ohm"] + MOTOR["values"]["coil_ohm"])
        if load == "forward":            # AOUT1 high, AOUT2 low
            assert ma == pytest.approx(vm - i * e["r_on_high_ohm"], abs=0.01)
            assert mb == pytest.approx(i * e["r_on_low_ohm"], abs=0.01)
        elif load == "reverse":          # AOUT1 low, AOUT2 high
            assert mb == pytest.approx(vm - i * e["r_on_high_ohm"], abs=0.01)
            assert ma == pytest.approx(i * e["r_on_low_ohm"], abs=0.01)
        elif load == "brake":            # both low: the winding shorted
            assert ma < 0.01 and mb < 0.01
        else:                            # coast: both off, no current through the winding
            assert abs(ma - mb) < 1e-3
    rows = [c for c in out["checks"] if c["item"] == "U9 out1_a" and c["scenario"].startswith("usb-nom/forward")]
    assert rows and rows[0]["result"] == "pass"            # the output current against i_out_max_a 1.5 A


def tb6612(project):
    """U9 TB6612 with VCC on 3V3 and VM on +5V: AIN1 on SIG (GP7), AIN2 on SIG2 (GP8), PWMA on PWM (GP9), STBY on
    STBY (GP10); the 33 Ω motor M9 between AO1 (MA) and AO2 (MB), channel B's inputs on GND, its outputs open."""
    project.save_part("C141517", library.entry("C141517"))
    project.save_part(MOTOR["lcsc"], MOTOR)
    g = project.graph()
    project.free_pins(g, "U1.10", "U1.11", "U1.12", "U1.14")
    g["graph"]["components"] += [comp("U9", "C141517", nc=["7", "8", "11", "12"]),
                                 {"designator": "M9", "type": "motor", "lcsc": MOTOR["lcsc"], "pins": {"1": "+", "2": "-"}}]
    project.net(g, "+5V")["pins"] += ["U9.13", "U9.14", "U9.24"]
    project.net(g, "3V3")["pins"] += ["U9.20"]
    project.net(g, "GND")["pins"] += ["U9.3", "U9.4", "U9.9", "U9.10", "U9.18", "U9.15", "U9.16", "U9.17"]
    nets(g, SIG=(["U1.10", "U9.21"], (0, 3.4)), SIG2=(["U1.11", "U9.22"], (0, 3.4)), PWM=(["U1.12", "U9.23"], (0, 3.4)),
         STBY=(["U1.14", "U9.19"], (0, 3.4)), MA=(["U9.1", "U9.2", "M9.1"], (0, 5.5)),
         MB=(["U9.5", "U9.6", "M9.2"], (0, 5.5)))
    project.save_graph(g)
    sim = load_sim(project)
    sim["mcu"]["U1"]["outputs"] += ["SIG", "SIG2", "PWM", "STBY"]

    def load(stby, in1, in2, pwm):
        return {"gpio": {"LED_OE": 1, "STBY": stby, "SIG": in1, "SIG2": in2, "PWM": pwm}, "leds_on": []}
    sim["loads"] = {"cw": load(1, 1, 0, 1), "pwm-low": load(1, 1, 0, 0), "stop": load(1, 0, 0, 1),
                    "standby": load(0, 1, 0, 1)}
    sim["report"] = ["+5V", "MA", "MB"]
    return sim


def test_tb6612_brakes_when_pwm_is_low_and_stops_when_standby(project):
    """H-SW control function p. 4: IN1 IN2 = H L with PWM H turns CW (AO1 high, AO2 low), with PWM L short brake
    (both low); L L stop (both off); STBY L standby (both off) whatever the inputs say."""
    out = simulate(project, tb6612(project))
    e = library.entry("C141517")["values"]
    for load in ("cw", "pwm-low", "stop", "standby"):
        sc = scenario(out, load)
        assert sc["status"] == "ok", (load, sc)
        vm, ma, mb = (sc["nets"][n] for n in ("+5V", "MA", "MB"))
        if load == "cw":
            i = vm / (e["r_on_high_ohm"] + e["r_on_low_ohm"] + MOTOR["values"]["coil_ohm"])
            assert ma == pytest.approx(vm - i * e["r_on_high_ohm"], abs=0.01)
            assert mb == pytest.approx(i * e["r_on_low_ohm"], abs=0.01)
        elif load == "pwm-low":
            assert ma < 0.01 and mb < 0.01
        else:
            assert abs(ma - mb) < 1e-3


# --- E3 and E4: a charger with cell protection ----------------------------------------------------------------------
CELL = {"lcsc": "C9200001", "mpn": "one Li-ion cell holder (test)", "kind": "battery_holder",
        "verified": {"by": "test"}, "values": {"cells": 1}, "limits": {"v_max_v": 4.35},
        "pins": {"1": {"name": "+", "type": "power_out", "role": "plus"},
                 "2": {"name": "-", "type": "power_out", "role": "minus"}}}


def charger(project, cell_v=3.7, prog_ohm=10e3, key="C424093"):
    """U8 charger (MCP73831 or TP4056) from +5V into BAT, R_PROG to GND; the cell BT8 between BAT and BAT_N; U7 DW01A
    on the cell (VCC through 100 Ω, GND on BAT_N, VM through 1 kΩ to GND), Q7 FS8205A: channel 1 BAT_N – MID (gate
    OD), channel 2 MID – GND (gate OC); R73 1 kΩ from BAT to GND, the system's load, so that the cell's current
    always returns through the MOSFETs."""
    for k in (key, "C351410", "C2830320", "C17414", "C17408", "C17513"):
        project.save_part(k, library.entry(k))
    project.save_part(CELL["lcsc"], CELL)
    rp = resistor(project, "C9200002", prog_ohm)
    g = project.graph()
    pins = {k2: p for k2, p in library.entry(key)["pins"].items()}
    vin = next(n for n, p in pins.items() if p.get("role") == "vin")
    bat = next(n for n, p in pins.items() if p.get("role") == "bat")
    prog = next(n for n, p in pins.items() if p.get("role") == "prog")
    gnd = [n for n, p in pins.items() if p.get("role") == "gnd" or p["type"] == "ground"]
    rest = [n for n in pins if n not in (vin, bat, prog, *gnd)]
    g["graph"]["components"] += [
        comp("U8", key, nc=rest), {**rp, "designator": "R81"},
        {"designator": "BT8", "type": "battery_holder", "lcsc": CELL["lcsc"], "pins": {"1": "+", "2": "-"}, "bom": False},
        comp("U7", "C351410"), comp("Q7", "C2830320"),
        {"designator": "R71", "type": "resistor", "lcsc": "C17408", "pins": {"1": "1", "2": "2"}, "value": "100"},
        {"designator": "R72", "type": "resistor", "lcsc": "C17513", "pins": {"1": "1", "2": "2"}, "value": "1k"},
        {"designator": "R73", "type": "resistor", "lcsc": "C17513", "pins": {"1": "1", "2": "2"}, "value": "1k"}]
    project.net(g, "+5V")["pins"] += [f"U8.{vin}"]
    project.net(g, "GND")["pins"] += [f"U8.{p}" for p in gnd] + ["R81.2", "R72.2", "Q7.3", "R73.2"]
    nets(g, PROG=([f"U8.{prog}", "R81.1"], (0, 1.2)), BAT=([f"U8.{bat}", "BT8.1", "R71.1", "R73.1"], (0, 4.35)),
         BAT_N=(["BT8.2", "U7.6", "U7.4", "Q7.1"], (-0.2, 0.2)), VCC_DW=(["U7.5", "R71.2"], (0, 4.35)),
         OD=(["U7.1", "Q7.6"], (-0.2, 4.35)), OC=(["U7.3", "Q7.4"], (-0.2, 4.35)), VM=(["U7.2", "R72.1"], (-0.2, 0.2)),
         MID=(["Q7.2", "Q7.5"], (-0.2, 0.2)))
    project.save_graph(g)
    sim = load_sim(project)
    sim["cells"] = {"cell": {"v": cell_v, "r": 0.1, "i_charge_max_a": 1.0}}
    sim["supplies"] = {"usb-nom": {"J1": 5.0, "BT8": "cell"}, "battery": {"BT8": "cell"}}
    sim["loads"] = {"idle": {"gpio": {"LED_OE": 1}, "leds_on": []}}
    sim["report"] = ["+5V", "BAT", "BAT_N", "OD", "OC", "MID", "VM"]
    return sim


def charge_row(out, supply="usb-nom"):
    return next(c for c in out["checks"] if c["item"] == "U8" and c["check"].startswith("charge current")
                and c["scenario"].startswith(supply))


def amps(row):
    return float(row["actual"].split()[0]) * (1e-3 if row["actual"].split()[1] == "mA" else 1)


def converged(sc, cell_v):
    """The operating point is the circuit's, not ngspice's fallback: the cell between BAT and BAT_N at its voltage
    (plus or minus what its 0.1 Ω drops)."""
    assert abs(sc["nets"]["BAT"] - sc["nets"]["BAT_N"] - cell_v) < 0.1, sc["nets"]


def test_the_charger_charges_with_prog_v_over_r_prog_through_the_protected_cell(project):
    out = simulate(project, charger(project, cell_v=3.7, prog_ohm=10e3))
    assert amps(charge_row(out)) == pytest.approx(1000 / 10e3, rel=0.02)       # MCP73831: 1000 V / R_PROG
    sc = scenario(out, "idle")
    converged(sc, 3.7)
    assert sc["nets"]["OD"] > 3.5 and sc["nets"]["OC"] > 3.5                    # the DW01A holds both MOSFETs on
    assert abs(sc["nets"]["BAT_N"]) < 0.02                                       # both channels conduct: the cell's
    #                                                                              minus sits on ground


def test_below_the_precondition_threshold_the_charger_charges_with_a_tenth(project):
    out = simulate(project, charger(project, cell_v=2.6, prog_ohm=10e3))          # 2.6 V < 2.793 V, above 2.50 V
    converged(scenario(out, "idle"), 2.6)
    assert amps(charge_row(out)) == pytest.approx(0.10 * 1000 / 10e3, rel=0.05)


def test_the_tp4056_programs_1100_v_over_r_prog(project):
    out = simulate(project, charger(project, cell_v=3.7, prog_ohm=2.2e3, key="C16581"))
    converged(scenario(out, "idle"), 3.7)
    assert amps(charge_row(out)) == pytest.approx(1100 / 2.2e3, rel=0.02)


def test_overdischarge_and_overcharge_switch_the_cell_off(project):
    """The DW01A's outputs against its own ground, the cell's minus (BAT_N): below 2.50 V OD falls to it and the
    discharge MOSFET opens; above 4.30 V OC falls to VM and the charge MOSFET opens. (With the charge MOSFET open the
    load's current returns through its body diode, VM rises above 150 mV and the model's OD follows as for an
    overcurrent: an operating point has no history – the datasheet's release by a load is not modelled.)"""
    def rel(sc, net):
        return sc["nets"][net] - sc["nets"]["BAT_N"]
    out = simulate(project, charger(project, cell_v=2.3))                         # below 2.50 V: OD low
    sc = scenario(out, "idle", supply="battery")
    converged(sc, 2.3)
    assert rel(sc, "OD") < 0.3 and rel(sc, "OC") > 2.0
    out = simulate(project, charger(project, cell_v=4.40))                        # above 4.30 V: OC low
    sc = scenario(out, "idle", supply="battery")
    converged(sc, 4.40)
    assert abs(sc["nets"]["OC"] - sc["nets"]["VM"]) < 0.05                        # OC low at VM


def test_the_charge_check_reads_any_supply_scenario_with_a_cell(project):
    sim = charger(project, cell_v=3.7, prog_ohm=2e3)                              # 500 mA programmed
    sim["cells"]["cell"]["i_charge_max_a"] = 0.2
    cfg = project.config()
    found = charge_currents(Design.from_config(cfg), sim)
    assert [(f.place, f.grade) for f in found] == [("U8", "charge")]               # no supply scenario named "cells"
    assert "i_charge_max_a of cells.cell" in found[0].source


# --- E4: the dual MOSFET's second channel ---------------------------------------------------------------------------
def test_a_dual_mosfet_is_two_transistors(project):
    from edakit.sim import netlist
    sim = charger(project)
    cfg = project.config()
    d = Design.from_config(cfg)
    sc = {"name": "t", "load": sim["loads"]["idle"], "supply": sim["supplies"]["battery"], "corner": "max"}
    text, meta = netlist.build(d, sim, sc)
    assert "M_Q7 " in text and "M_Q7_2 " in text
    assert [el["kind"] for el in meta["elements"]["Q7"]] == ["nmos", "nmos"]


# --- E6: buck-boost -------------------------------------------------------------------------------------------------
def test_a_buck_boost_regulator_holds_its_output_below_and_above_it(project):
    """A buck-boost (the Pico's RT6150: 3.3 V from 1.8 V to 5.5 V, Pico datasheet 4.4) on a cell at 2.5 V and at
    4.5 V: 3.3 V out in both, the input power the output's over the efficiency."""
    assert library.entry("C7203002")["values"]["regulator"] == "buck_boost"
    part = {"lcsc": "C9200003", "mpn": "test buck-boost", "kind": "ic", "verified": {"by": "test"},
            "values": {"behavior": "buck_boost", "vout_v": 3.3, "efficiency": 0.9},
            "limits": {"vin_min_v": 1.8},
            "pins": {"1": {"name": "VIN", "type": "power_in", "role": "vin"},
                     "2": {"name": "VOUT", "type": "power_out", "role": "vout"},
                     "3": {"name": "GND", "type": "ground", "role": "gnd"}}}
    project.save_part(part["lcsc"], part)
    project.save_part(CELL["lcsc"], CELL)
    load = resistor(project, "C9200004", 330)
    g = project.graph()
    g["graph"]["components"] += [
        comp_from(part, "U6"), {**load, "designator": "R61"},
        {"designator": "BT6", "type": "battery_holder", "lcsc": CELL["lcsc"], "pins": {"1": "+", "2": "-"}, "bom": False}]
    project.net(g, "GND")["pins"] += ["U6.3", "R61.2", "BT6.2"]
    nets(g, BB_IN=(["U6.1", "BT6.1"], (0, 5.5)), BB_OUT=(["U6.2", "R61.1"], (0, 3.4)))
    project.save_graph(g)
    sim = load_sim(project)
    sim["cells"] = {"low": {"v": 2.5, "r": 1.0}, "high": {"v": 4.5, "r": 1.0}}
    sim["supplies"] = {"low": {"J1": 5.0, "BT6": "low"}, "high": {"J1": 5.0, "BT6": "high"}}
    sim["loads"] = {"idle": {"gpio": {"LED_OE": 1}, "leds_on": []}}
    sim["report"] = ["BB_IN", "BB_OUT"]
    out = simulate(project, sim)
    for supply in ("low", "high"):
        sc = scenario(out, "idle", supply=supply)
        assert sc["status"] == "ok", (sc, [c for c in out["checks"] if c["result"] == "fail"])
        v_in, v_out = sc["nets"]["BB_IN"], sc["nets"]["BB_OUT"]
        assert v_out == pytest.approx(3.3, abs=1e-3)                       # below and above its output
        i_in = (sim["cells"][supply]["v"] - v_in) / sim["cells"][supply]["r"]
        assert v_in * i_in == pytest.approx(3.3 ** 2 / 330 / 0.9, rel=0.01)


def comp_from(part, des):
    return {"designator": des, "type": "ic", "lcsc": part["lcsc"], "pins": {n: p["name"] for n, p in part["pins"].items()}}
