"""False alarms the block and parts agents found (build/schema-gaps.md, 2026-10-31), each with the circuit where the
finding was wrong and the circuit where it is right and still raised."""

import copy
from types import SimpleNamespace

from edakit import library
from edakit.design import Design
from edakit.engines import hint, levels, paths, requires
from edakit.engines.limits import judge, judge_all
from edakit.engines.quantities import Quantity, part_limits, pin_voltages
from edakit.engines.sim import gate_drive

HEADER = {"kind": "connector", "mpn": "test header", "pins": {
    "1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}, "3": {"name": "3", "type": "passive"}}}
OPAMP = {"kind": "ic", "mpn": "test op-amp", "pins": {
    "1": {"name": "V-", "type": "power_in", "role": "vee"}, "2": {"name": "V+", "type": "power_in", "role": "vcc"},
    "3": {"name": "GND", "type": "ground"}}}


def design(components, nets, parts, grounds=None):
    graph = {"name": "t", "version": "1", "ground": "GND", "components": components, "nets": nets}
    if grounds:
        graph["grounds"] = grounds
    return Design.from_data(graph, parts)


def comp(des, key, parts, kind="ic", **extra):
    return {"designator": des, "type": kind, "lcsc": key, "board": "main",
            "pins": {n: p["name"] for n, p in parts[key]["pins"].items()}, **extra}


def lib(*keys, **own):
    return {**{k: library.entry(k) for k in keys}, **own}


# --- 1, 2, 4: a negative rail behind its series diode -----------------------------------------------------------------
def eurorack(cathode_to_header=True, rail=(-12.6, 0), opamp_pin="1"):
    """A reversible header J1, a Schottky D2 between header and rail, an op-amp's supply pin on the rail."""
    parts = lib("C2480", J=HEADER, OA=OPAMP)
    d_pins = ("1", "2") if cathode_to_header else ("2", "1")      # (pin on the header net, pin on the rail)
    comps = [comp("J1", "J", parts, "connector", source="reversible"), comp("D2", "C2480", parts, "diode"),
             comp("U9", "OA", parts)]
    other = "2" if opamp_pin == "1" else "1"
    nets = [{"name": "HDR", "pins": ["J1.1", f"D2.{d_pins[0]}"], "v": [-12.6, 12.6]},
            {"name": "RAIL", "pins": [f"D2.{d_pins[1]}", f"U9.{opamp_pin}"], "v": list(rail)},
            {"name": "GND", "pins": ["J1.2", "U9.3"], "v": [0, 0]},
            {"name": "OTHER", "pins": ["J1.3", f"U9.{other}"], "v": [0, 12.6]}]
    return design(comps, nets, parts)


def reverse_at(d):
    return [f.place for f in paths.reverse(d, d)]


def unfed(d):
    return [f.place for f in paths.supply(d) if f.code == "PATH.unfed"]


def test_a_cathode_toward_the_header_blocks_on_a_negative_rail():
    assert "D2.1" not in reverse_at(eurorack())                      # −12 V: the cathode faces the header, it blocks
    assert "D2.1" in reverse_at(eurorack(rail=(0, 12.6)))           # +12 V the same way round: it conducts reversed


def test_a_negative_rail_behind_its_diode_is_fed():
    assert unfed(eurorack()) == []                                   # the −12 V rail feeds the op-amp's V−
    assert "U9.1" in unfed(eurorack(rail=(0, 12.6)))                # a positive rail behind a cathode-facing diode


def test_a_negative_supply_pin_is_held_to_its_own_range_not_to_the_signal_floor():
    def lim_v(d):
        return [f.place for f in judge_all(d, pin_voltages(d)) if f.code == "LIM.v"]
    assert "U9.1" not in lim_v(eurorack())                           # V− (role vee) on −12.6 V
    assert "U9.2" in lim_v(eurorack(opamp_pin="2"))                 # V+ (role vcc) on −12.6 V: below −0.3 V


# --- 3: a limit of 0 V in the simulation ------------------------------------------------------------------------------
def test_a_limit_of_zero_volts_tolerates_ngspice_noise():
    parts = lib("C2895284")
    dd = SimpleNamespace(parts=parts)

    def found(value):
        q = Quantity("C1", "vr", value, stage="E", kind="capacitor", entry="C2895284", grade="polarized")
        return judge(q, part_limits(dd, q))
    assert found(7.6e-19) == []                                       # noise of an unfed rail
    assert len(found(0.05)) == 1                                      # a real reverse voltage


# --- 5, 8: levels -----------------------------------------------------------------------------------------------------
def buffer(oe="GND", chain=True, a_net="A"):
    """SN74AHCT1G125 U1 with Y on DATA; R1 330 Ω DATA–DOUT and R3 10 kΩ DOUT–GND (the addressable-led-input block)."""
    parts = lib("C7484", "C17630", "C17414")
    comps = [comp("U1", "C7484", parts), comp("R1", "C17630", parts, "resistor")]
    nets = [{"name": "DATA", "pins": ["U1.4", "R1.1"], "v": [0, 5.5]},
            {"name": "VCC", "pins": ["U1.5"] + (["U1.1"] if oe == "VCC" else []), "v": [0, 5.5]},
            {"name": a_net, "pins": ["U1.2"], "v": [0, 5.5]}]
    gnd = ["U1.3"] + (["U1.1"] if oe == "GND" else [])
    if chain:
        comps.append(comp("R3", "C17414", parts, "resistor"))
        nets.append({"name": "DOUT", "pins": ["R1.2", "R3.1"], "v": [0, 5.5]})
        gnd.append("R3.2")
    else:
        nets.append({"name": "DOUT", "pins": ["R1.2"], "v": [0, 5.5]})
    if oe == "GPIO":
        nets.append({"name": "OEN", "pins": ["U1.1"], "v": [0, 5.5]})
    nets.append({"name": "GND", "pins": gnd, "v": [0, 0]})
    return design(comps, nets, parts)


def released(d):
    return [f.place for f in levels.released_nets(d)]


def test_a_tristate_output_with_its_enable_tied_active_drives_its_net():
    assert released(buffer(oe="GND", chain=False)) == []            # OE# on ground: Y drives
    assert released(buffer(oe="GPIO", chain=False)) == ["DATA"]     # OE# on a pin: Y lets go, nothing holds DATA


def test_a_net_held_through_two_resistors_in_series_is_held():
    assert released(buffer(oe="GPIO", chain=True)) == []            # DATA – 330 Ω – DOUT – 10 kΩ – GND


def test_an_input_tied_to_a_supply_rail_is_defined():
    def undefined(d):
        return [f.place for f in levels.undefined_inputs(d)]
    d = buffer(oe="VCC", a_net="A")
    assert "VCC" not in undefined(d)                                 # OE# on VCC, no resistor on the net
    assert "A" in undefined(d)                                       # A alone: undefined, as before


# --- 6: a switchable termination and the failsafe bias ----------------------------------------------------------------
def rs485(switch=True, bias_ohm_key="C17590"):
    """MAX3485 U1 on A/B; R1 120 Ω from A to a switch SW1 to B (the rs485 block); bias R4 A–3V3, R5 B–GND."""
    parts = lib("C18148", "C17437", "C126848", bias_ohm_key)
    comps = [comp("U1", "C18148", parts), comp("R1", "C17437", parts, "resistor"),
             comp("R4", bias_ohm_key, parts, "resistor"), comp("R5", bias_ohm_key, parts, "resistor")]
    nets = [{"name": "A", "pins": ["U1.6", "R1.1", "R4.1"], "v": [0, 3.4]},
            {"name": "B", "pins": ["U1.7", "R5.1"] + (["SW1.2"] if switch else []), "v": [0, 3.4]},
            {"name": "MID", "pins": ["R1.2"] + (["SW1.1"] if switch else []), "v": [0, 3.4]},
            {"name": "3V3", "pins": ["U1.8", "R4.2"], "v": [0, 3.4]},
            {"name": "CTL", "pins": ["U1.1", "U1.2", "U1.3", "U1.4"], "v": [0, 3.4]},
            {"name": "GND", "pins": ["U1.5", "R5.2"], "v": [0, 0]}]
    if switch:
        comps.append(comp("SW1", "C126848", parts, "switch"))
    return design(comps, nets, parts)


def termination(d):
    return [(f.code, f.grade, f.text) for f in requires.bus_terminations(d)]


def test_a_termination_behind_a_switch_counts():
    missing = [t for c, g, t in termination(rs485()) if (c, g) == ("REQ.missing", "termination")]
    assert missing and "1 termination(s)" in missing[0]               # the switched 120 Ω is the board's end
    missing = [t for c, g, t in termination(rs485(switch=False)) if (c, g) == ("REQ.missing", "termination")]
    assert missing and "0 termination(s)" in missing[0]               # a resistor to nowhere is none


def test_the_failsafe_bias_is_judged_at_the_supplys_minimum_with_the_far_end_assumed():
    assert [t for c, g, t in termination(rs485()) if g == "failsafe"] == []   # 270 Ω: 300 mV at 3.0 V
    weak = [t for c, g, t in termination(rs485(bias_ohm_key="C17414")) if g == "failsafe"]
    assert weak and "at 3 V" in weak[0] and "the far end's 120 Ω assumed" in weak[0]   # 10 kΩ: far too weak


# --- 7, 11: hints -----------------------------------------------------------------------------------------------------
def test_an_esd_device_on_every_line_answers_the_esd_hint():
    parts = lib("C5274290", "C7484", J=HEADER)
    comps = [comp("J1", "J", parts, "connector"), comp("U1", "C7484", parts)]
    nets = [{"name": "SIG", "pins": ["J1.1", "U1.2"], "v": [0, 3.4]},
            {"name": "GND", "pins": ["J1.2", "U1.3"], "v": [0, 0]}]
    plain = design(copy.deepcopy(comps), copy.deepcopy(nets), parts)
    assert hint._connector_signals(plain, None, None) == ["J1"]
    comps.append(comp("D1", "C5274290", parts, "diode"))
    nets[0]["pins"].append("D1.1")
    nets[1]["pins"].append("D1.2")
    assert hint._connector_signals(design(comps, nets, parts), None, None) == []


def test_a_gate_on_a_rail_needs_no_gate_resistor_hint():
    parts = lib("C82045", "C7484")
    comps = [comp("Q1", "C82045", parts, "transistor"), comp("U1", "C7484", parts)]
    nets = [{"name": "3V3", "pins": ["Q1.1", "U1.5"], "v": [0, 3.4]},           # the level shifter's gate on 3V3
            {"name": "LV", "pins": ["Q1.2"], "v": [0, 3.4]}, {"name": "HV", "pins": ["Q1.3"], "v": [0, 5.5]},
            {"name": "GND", "pins": ["U1.3"], "v": [0, 0]}]
    assert hint._driven_gates(design(comps, nets, parts), None, None) == []
    nets[0]["pins"].remove("Q1.1")
    nets.append({"name": "GATE", "pins": ["Q1.1"], "v": [0, 3.4]})
    assert hint._driven_gates(design(comps, nets, parts), None, None) == ["Q1"]


def test_a_switch_no_mcu_pin_reads_needs_no_debounce_hint():
    pico = "C41407547"
    parts = lib("C126848", pico)
    comps = [comp("SW1", "C126848", parts, "switch"), comp("U1", pico, parts, "microcontroller")]
    nets = [{"name": "MID", "pins": ["SW1.1"], "v": [0, 3.4]}, {"name": "B", "pins": ["SW1.2"], "v": [0, 3.4]}]
    assert hint._read_switches(design(comps, nets, parts), None, None) == []
    gpio = next(n for n, p in parts[pico]["pins"].items() if p.get("role") == "gpio")
    nets[1]["pins"].append(f"U1.{gpio}")
    assert hint._read_switches(design(comps, nets, parts), None, None) == ["SW1"]


def test_a_line_on_an_off_board_connector_is_a_cable_line():
    parts = lib("C7484", J=HEADER)
    comps = [comp("J1", "J", parts, "connector"), comp("U1", "C7484", parts)]
    nets = [{"name": "SIG", "pins": ["J1.1", "U1.2"], "v": [0, 3.4]},
            {"name": "GND", "pins": ["J1.2", "U1.3"], "v": [0, 0]}]
    assert hint._cable_lines(design(copy.deepcopy(comps), nets, parts), None, None) == []
    comps[0]["off_board"] = True
    assert hint._cable_lines(design(comps, nets, parts), None, None) == ["SIG"]


def test_a_cell_its_protection_ic_guards_needs_no_lithium_hint():
    holder = {"kind": "battery_holder", "mpn": "test holder", "pins": {
        "1": {"name": "+", "type": "passive", "role": "plus"}, "2": {"name": "-", "type": "passive", "role": "minus"}}}
    parts = lib("C351410", "C2830320", BT=holder)
    comps = [comp("BT1", "BT", parts, "battery_holder"), comp("U1", "C351410", parts),
             comp("Q1", "C2830320", parts, "transistor")]
    nets = [{"name": "CELL_P", "pins": ["BT1.1", "U1.5"], "v": [0, 4.2]},
            {"name": "CELL_M", "pins": ["BT1.2", "U1.6", "Q1.1"], "v": [0, 0]},       # the cell's minus at S1
            {"name": "OD", "pins": ["U1.1", "Q1.6"], "v": [0, 4.2]},                  # DW01A OD drives G1
            {"name": "GND", "pins": ["Q1.3"], "v": [0, 0]}]
    assert hint._unprotected_cells(design(comps, nets, parts), None, None) == []
    nets[2]["pins"].remove("Q1.6")
    nets.append({"name": "G1", "pins": ["Q1.6"], "v": [0, 4.2]})
    assert hint._unprotected_cells(design(comps, nets, parts), None, None) == ["BT1"]


# --- 9: decoupling against the graph's grounds ------------------------------------------------------------------------
def test_decoupling_to_a_net_of_the_graphs_grounds_counts():
    parts = lib("C351410", "C49678")
    comps = [comp("U1", "C351410", parts), comp("C1", "C49678", parts, "capacitor")]
    nets = [{"name": "VCC", "pins": ["U1.5", "C1.1"], "v": [0, 4.2]},
            {"name": "CELL_M", "pins": ["U1.6", "C1.2"], "v": [0, 0]}]
    assert [f for f in requires.decoupling(design(comps, nets, parts, grounds=["CELL_M"]))] == []
    assert len(requires.decoupling(design(comps, nets, parts))) == 1          # CELL_M not a ground: no capacitor


# --- 10: VGS with the device's polarity -------------------------------------------------------------------------------
def test_a_pmos_gate_above_its_source_is_off_not_half_on():
    part = library.entry("C15127")                                            # AO3401A, VGS(th) −0.5 … −1.3 V
    rows = []
    s = SimpleNamespace(res={"d": 0.0, "g": 5.0, "s": 3.3}, n=SimpleNamespace(entry_key=lambda des: "C15127"),
                        check=lambda *a, **k: rows.append(a))

    def ok(g):
        rows.clear()
        s.res["g"] = g
        gate_drive(s, "Q1", part, ("d", "g", "s"))
        return rows[0][5]
    assert ok(5.0)                    # gate 1.7 V above its source: reverse-biased, off – not "half on" by |VGS|
    assert not ok(2.0)                # VSG 1.3 V: between the threshold and the specified −2.5 V – half on
    assert ok(0.0)                    # VSG 3.3 V: on as specified at −2.5 V


# --- 12: the series resistor of an RF filter at an instrument input ---------------------------------------------------
def instrument(extra_load=False):
    """The instrument-buffer block's input: R2 2.2 MΩ to ground, R1 10 kΩ in series into C1 100 pF to ground and C2
    10 nF on to R3 2.2 MΩ – the pickup's DC load is R2 alone."""
    def res(ohm):
        return {"kind": "resistor", "mpn": f"{ohm:g} Ω", "values": {"value_ohm": ohm},
                "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}}}
    cap = {"kind": "capacitor", "mpn": "cap", "values": {"value_f": 1e-10},
           "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}}}
    parts = {"R22M": res(2.2e6), "R10K": res(1e4), "CAP": cap}
    comps = [comp("R2", "R22M", parts, "resistor"), comp("R1", "R10K", parts, "resistor"),
             comp("C1", "CAP", parts, "capacitor"), comp("C2", "CAP", parts, "capacitor"),
             comp("R3", "R22M", parts, "resistor")]
    nets = [{"name": "GTR_IN", "pins": ["R2.1", "R1.1"], "v": [0, 1], "instrument": "pickup", "load_min_ohm": 1e6},
            {"name": "FILT", "pins": ["R1.2", "C1.1", "C2.1"], "v": [0, 1]},
            {"name": "BIAS", "pins": ["C2.2", "R3.1"], "v": [0, 9]},
            {"name": "GND", "pins": ["R2.2", "C1.2", "R3.2"], "v": [0, 0]}]
    if extra_load:
        comps.append(comp("R4", "R10K", parts, "resistor"))
        nets[0]["pins"].append("R4.1")
        nets[3]["pins"].append("R4.2")
    return design(comps, nets, parts)


def test_a_series_resistor_into_a_capacitor_is_no_load_on_an_instrument_input():
    assert requires.instrument_loads(instrument()) == []                          # DC load 2.2 MΩ, not 9.95 kΩ
    found = requires.instrument_loads(instrument(extra_load=True))
    assert len(found) == 1 and "9.95 kΩ" in found[0].text                         # a real 10 kΩ to ground
