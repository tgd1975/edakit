"""More simulation models and sources (schema-gaps.md W5, the owner's decision of 2026-10-31): a sim.json source with
several outputs (±12 V from one header), every contact set of a relay, a photo-MOS output, a pass-gate translator, a
USB PD sink's VDD shunt and the voltage its pins request, an ESD array as a kind."""

import json
import shutil

import pytest
from test_block import place
from test_sim import failing, simulate

from edakit import library
from edakit.design import Design
from edakit.engines import requires
from edakit.sim import netlist
from edakit.sim import run as simrun

ngspice = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
RES = {"type": "resistor", "pins": {"1": "1", "2": "2"}}


def sim_of(project):
    return json.loads((project.root / "hardware" / "sim.json").read_text())


def resistor(project, key, ohm):
    project.use_library_part("C17414")
    r = project.part("C17414")
    r.update(lcsc=key, mpn=f"test resistor {ohm:g}")
    r["values"]["value_ohm"] = ohm
    project.save_part(key, r)


def rows(out, item, word=""):
    return [c for c in out["checks"] if c["item"] == item and word in c["check"]]


# --- I2: a source with several outputs ------------------------------------------------------------------------------
def eurorack(project):
    """The eurorack-power block in the example, J2 its header, the sim.json of its test table."""
    _, comps, *_ = place(project, "eurorack-power")
    sim = sim_of(project)
    from test_block import TESTS
    for key, value in TESTS["eurorack-power"]["sim"].items():
        sim[key] = {**sim.get(key, {}), **value}
    return sim


@ngspice
def test_one_header_feeds_both_rails_of_a_split_supply(project):
    sim = eurorack(project)
    out = simulate(project, sim)
    assert not failing(out)
    nom = next(s for s in out["scenarios"] if s["name"].startswith("usb-nom"))
    assert set(nom["sources"]) >= {"J1", "J2:p12", "J2:n12"}
    d = Design.from_config(project.config())
    sc = next(x for x in simrun.scenarios(sim) if x["supply_name"] == "usb-nom")
    text, meta = netlist.build(d, sim, sc)
    res = simrun.ngspice(text)
    p12, n12 = (netlist.node(n, d.ground) for n in ("T_P12", "T_N12"))
    assert 11.5 < res[p12.lower()] <= 12.001 and -12.001 <= res[n12.lower()] < -11.5   # behind each rail's Schottky
    assert meta["sources"]["J2:n12"]["nodes"][0] != meta["sources"]["J2:p12"]["nodes"][0]


@ngspice
def test_a_negative_rail_supplies_with_the_sign_of_supplying(project):
    """Current drawn from the −12 V rail counts as supplied, not as fed back (LIM.backfeed stays quiet)."""
    sim = eurorack(project)
    sim["loads"]["idle"].setdefault("external", {})
    sim["loads"]["idle"]["external"]["J2"] = {"plus": "3", "minus": "1", "i_a": 0.05}    # GND → −12 V, 50 mA
    out = simulate(project, sim)
    idle = next(s for s in out["scenarios"] if s["name"].startswith("usb-nom/idle"))
    assert idle["sources"]["J2:n12"] == pytest.approx(0.05, rel=0.05)
    assert not [c for c in failing(out) if c["id"] == "LIM.backfeed"]


def test_a_source_with_outputs_is_checked(project):
    d = Design.from_config(project.config())
    bad = {"sources": {"J1": {"minus": "2", "outputs": {"a": {"v_ratio": 1}}}}}
    with pytest.raises(simrun.SimError, match="plus, the pin of the rail"):
        simrun.check_sources(d, bad)
    with pytest.raises(simrun.SimError, match="v_ratio"):
        simrun.check_sources(d, {"sources": {"J1": {"minus": "2", "outputs": {"a": {"plus": "1", "v_ratio": 0}}}}})
    with pytest.raises(simrun.SimError, match="instead of plus"):
        simrun.check_sources(d, {"sources": {"J1": {"minus": "2", "plus": "1", "outputs": {"a": {"plus": "1"}}}}})
    simrun.check_sources(d, sim_of(project))                                            # the example's own


# --- I3: every contact set of a relay ------------------------------------------------------------------------------
def test_every_contact_set_of_a_relay_is_switched(project):
    place(project, "relay-bypass")
    entry = library.entry("C64399")
    assert {entry["pins"][n]["role"] for n in ("5", "6", "7")} == {"no_2", "common_2", "nc_2"}
    d = Design.from_config(project.config())
    sim = sim_of(project)
    sc = list(simrun.scenarios(sim))[0]
    k = next(des for des in d.comps if d.entry_key(des) == "C64399")
    for on in (False, True):
        load = {**sc["load"], "relays_on": [k] if on else []}
        text, meta = netlist.build(d, sim, {**sc, "load": load})
        contacts = [el for el in meta["elements"][k] if el["kind"] == "switch"]
        assert len(contacts) == 2                                    # both sets, not the first only
        common_2, throw_2 = (netlist.pin_node(d, f"{k}.{n}") for n in ("6", "5" if on else "7"))
        assert any(set(el["nodes"]) == {common_2, throw_2} for el in contacts)


# --- I4: a photo-MOS output ------------------------------------------------------------------------------------------
def photomos(project, led_ohm):
    """The AQY212GSX: its LED from GP7 (SIG) through led_ohm to GND, its output switching 10 mA from +5V through
    470 Ω to GND."""
    project.save_part("C415471", library.entry("C415471"))
    resistor(project, "C9005001", led_ohm)
    resistor(project, "C9005002", 470)
    g = project.graph()
    project.free_pins(g, "U1.10")
    g["graph"]["components"] += [
        {"designator": "OK9", "type": "optocoupler", "lcsc": "C415471", "pins": {"1": "1", "2": "2", "3": "3", "4": "4"}},
        {**RES, "designator": "R91", "lcsc": "C9005001"}, {**RES, "designator": "R92", "lcsc": "C9005002"}]
    project.net(g, "GND")["pins"] += ["OK9.2", "OK9.4"]
    project.net(g, "+5V")["pins"] += ["R92.1"]
    g["graph"]["nets"] += [{"name": "SIG", "pins": ["U1.10", "R91.1"], "v": [0, 3.4]},
                           {"name": "PM_LED", "pins": ["R91.2", "OK9.1"], "v": [0, 3.4]},
                           {"name": "PM_OUT", "pins": ["R92.2", "OK9.3"], "v": [0, 5.5]}]
    project.save_graph(g)
    sim = sim_of(project)
    sim["mcu"]["U1"]["outputs"].append("SIG")
    sim["loads"]["idle"]["gpio"] = {**sim["loads"]["idle"].get("gpio", {}), "SIG": 1}
    return sim


def pm_out(project, sim, load="idle"):
    d = Design.from_config(project.config())
    sc = next(s for s in simrun.scenarios(sim) if s["load_name"] == load and s["supply_name"] == "usb-nom")
    text, _ = netlist.build(d, sim, sc)
    return simrun.ngspice(text)[netlist.node("PM_OUT", d.ground).lower()]


@ngspice
def test_a_lit_photomos_closes_with_its_on_resistance(project):
    sim = photomos(project, 330)                     # (3.3 − 1.14) V / 330 Ω ≈ 6.5 mA ≥ IFon 3 mA
    out = simulate(project, sim)
    state = [r for r in rows(out, "OK9", "guarantees a state") if "idle" in r["scenario"]]
    assert state and all(r["result"] == "pass" for r in state)
    assert pm_out(project, sim) < 10e-3 * 0.7 + 1e-3  # 10 mA through at most 0.7 Ω
    assert pm_out(project, sim, "all_on") > 4.5      # SIG low: open, only the 1 µA leakage


@ngspice
def test_an_led_current_between_off_and_on_guarantees_neither(project):
    sim = photomos(project, 2.2e3)                   # ≈ 1 mA: above IFoff 0.3 mA, below IFon 3 mA
    out = simulate(project, sim)
    bad = [r for r in rows(out, "OK9", "guarantees a state") if r["result"] == "warn"]    # LIM.range/photomos: warn
    assert bad and "neither" in bad[0]["expected"]
    assert {f["grade"] for f in out["findings"] if f["code"] == "LIM.range" and f["place"] == "OK9"} == {"photomos"}


# --- I4: a pass-gate translator ---------------------------------------------------------------------------------------
PASS = {"lcsc": "C9005101", "mpn": "test pass-gate translator", "kind": "ic", "verified": {"by": "test"},
        "values": {"behavior": "pass_gate", "r_on_ohm": 3.5, "vgs_th_v": 0.6},
        "sources": ["values for the test, not a data sheet's"],
        "pins": {"1": {"name": "GND", "type": "ground", "role": "gnd"},
                 "2": {"name": "VREF1", "type": "power_in", "role": "vref1"},
                 "3": {"name": "SCL1", "type": "bidirectional", "role": "a1"},
                 "6": {"name": "SCL2", "type": "bidirectional", "role": "b1"},
                 "8": {"name": "EN", "type": "input", "role": "en"}}}


def pass_gate(project):
    """U9 between 3V3 (side 1, pull-up R91) and +5V (side 2, pull-up R92), EN on +5V; SW9 pulls side 1 to GND."""
    project.save_part("C9005101", PASS)
    resistor(project, "C9005102", 10e3)
    project.use_library_part("C318884")                               # the example's push button
    g = project.graph()
    g["graph"]["components"] += [
        {"designator": "U9", "type": "ic", "lcsc": "C9005101", "pins": {n: i["name"] for n, i in PASS["pins"].items()}},
        {**RES, "designator": "R91", "lcsc": "C9005102"}, {**RES, "designator": "R92", "lcsc": "C9005102"},
        {"designator": "SW9", "type": "button", "lcsc": "C318884",
         "pins": {n: p["name"] for n, p in library.entry("C318884")["pins"].items()}}]
    sw = library.entry("C318884")["pins"]
    a, b = (next(n for n, p in sw.items() if p.get("role") == r) for r in ("a", "b"))
    rest = [n for n in sw if n not in (a, b)]
    project.net(g, "GND")["pins"] += ["U9.1", f"SW9.{b}"]
    project.net(g, "3V3")["pins"] += ["U9.2", "R91.1"]
    project.net(g, "+5V")["pins"] += ["U9.8", "R92.1"]
    g["graph"]["nets"] += [{"name": "PG_A", "pins": ["U9.3", "R91.2", f"SW9.{a}"], "v": [0, 3.4]},
                           {"name": "PG_B", "pins": ["U9.6", "R92.2"], "v": [0, 5.5]}]
    if rest:
        project.comp(g, "SW9")["nc"] = rest
    project.save_graph(g)
    return sim_of(project), "SW9"


@ngspice
def test_a_pass_gate_keeps_released_sides_apart_and_passes_a_low(project):
    sim, sw = pass_gate(project)
    d = Design.from_config(project.config())
    sc = next(s for s in simrun.scenarios(sim) if s["supply_name"] == "usb-nom")
    for pressed, (lo_a, hi_a), (lo_b, hi_b) in ((False, (3.0, 3.4), (4.5, 5.3)), (True, (0, 0.05), (0, 0.1))):
        load = {**sc["load"], "buttons": [sw] if pressed else []}
        text, _ = netlist.build(d, sim, {**sc, "load": load})
        res = simrun.ngspice(text)
        va, vb = (res[netlist.node(n, d.ground).lower()] for n in ("PG_A", "PG_B"))
        assert lo_a <= va <= hi_a and lo_b <= vb <= hi_b, (pressed, va, vb)


# --- E5: a USB PD sink ------------------------------------------------------------------------------------------------
def pd_sink(project, vdd_ohm, cfg2_up=True, vbus_top=21.0):
    """The CH224K (C970725) as the example's VIN sink: VDD through vdd_ohm and the VBUS sense pin through 10 kΩ from
    VIN, CFG1 and CFG3 on GND, CFG2 pulled up to VDD by 10 kΩ – 20 V by CFG1 CFG2 CFG3 = 0 1 0 (table 6.2) – VIN
    declared up to vbus_top."""
    project.save_part("C970725", library.entry("C970725"))
    resistor(project, "C9005201", vdd_ohm)
    resistor(project, "C9005202", 10e3)
    project.use_library_part("C49678")
    g = project.graph()
    pins = library.entry("C970725")["pins"]
    g["graph"]["components"] += [
        {"designator": "U9", "type": "ic", "lcsc": "C970725", "pins": {n: p["name"] for n, p in pins.items()},
         "nc": ["4", "5", "6", "7", "10"]},
        {**RES, "designator": "R91", "lcsc": "C9005201"}, {**RES, "designator": "R92", "lcsc": "C9005202"},
        {**RES, "designator": "R93", "lcsc": "C9005202"},
        {"designator": "C91", "type": "capacitor", "lcsc": "C49678", "pins": {"1": "1", "2": "2"}}]
    vin = project.net(g, "VIN")
    vin["pins"] += ["R91.1", "R92.1"]
    vin["v"] = [0, vbus_top]
    project.net(g, "GND")["pins"] += ["U9.11", "U9.9", "U9.3", "C91.2"]
    g["graph"]["nets"] += [{"name": "PD_VDD", "pins": ["U9.1", "R91.2", "C91.1"] + (["R93.1"] if cfg2_up else []),
                            "v": [0, 3.6]},
                           {"name": "PD_SENSE", "pins": ["U9.8", "R92.2"], "v": [0, vbus_top]},
                           {"name": "PD_CFG2", "pins": ["U9.2"] + (["R93.2"] if cfg2_up else []), "v": [0, 3.6]}]
    project.save_graph(g)


def test_the_request_the_pins_select_is_held_to_the_vbus_range(project):
    pd_sink(project, 1e3, vbus_top=21.0)
    d = Design.from_config(project.config())
    assert requires.pd_levels(d, "U9") == "010"
    assert requires.pd_requests(d) == []
    pd_sink(project, 1e3, vbus_top=21.0)
    g = project.graph()
    project.net(g, "VIN")["v"] = [0, 5.5]
    project.save_graph(g)
    found = requires.pd_requests(Design.from_config(project.config()))
    assert [(f.code, f.grade) for f in found] == [("REQ.value", "pd_request")]
    assert "requests up to 20 V" in found[0].text and "VIN is declared up to 5.5 V" in found[0].text


def test_a_floating_cfg_pin_may_select_either_level(project):
    pd_sink(project, 1e3, cfg2_up=False, vbus_top=13.0)                # CFG2 open: 9 V or 20 V
    d = Design.from_config(project.config())
    assert requires.pd_levels(d, "U9") == "0?0"
    found = requires.pd_requests(d)
    assert found and "may select 9, 20 V" in found[0].text


def vbus_at(project, volts):
    sim = sim_of(project)
    for name in sim["supplies"]:
        sim["supplies"][name]["J1"] = volts
    sim["sources"]["J1"]["i_max_a"] = 1.0
    return sim


@ngspice
def test_the_shunt_holds_vdd_while_its_resistor_keeps_the_current_in_range(project):
    pd_sink(project, 1e3)                                       # (20 − 3.3) V / 1 kΩ ≈ 17 mA ≤ 30 mA
    out = simulate(project, vbus_at(project, 20.0))
    shunt = rows(out, "U9", "VDD shunt current")
    assert shunt and all(r["result"] == "pass" for r in shunt)
    assert not [c for c in failing(out) if c["item"] == "U9"]


@ngspice
def test_a_series_resistor_too_small_saturates_the_shunt(project):
    pd_sink(project, 470)                                       # (20 − 3.3) V / 470 Ω ≈ 36 mA > 30 mA: VDD rises
    out = simulate(project, vbus_at(project, 20.0))
    bad = [c for c in failing(out) if c["item"] == "U9"]
    assert any("VDD shunt current" in c["check"] for c in bad)
    assert any(c["id"] == "LIM.declared" and c["item"] == "PD_VDD" for c in failing(out))   # VDD rises past 3.6 V


# --- I4: an ESD array as a kind ----------------------------------------------------------------------------------------
def test_an_esd_array_guards_its_lines_and_holds_its_rail_to_its_stand_off(project):
    from edakit.engines import hint
    from edakit.engines.quantities import part_voltages
    place(project, "usb-c-data")
    d = Design.from_config(project.config())
    u = next(des for des in d.comps if d.entry_key(des) == "C7519")
    assert d.part(u)["kind"] == "esd_array" and "tvs" not in d.part(u)["values"]
    q = [x for x in part_voltages(d) if x.place == u and x.name == "vrwm"]
    assert len(q) == 1 and q[0].hi == pytest.approx(5.5) and q[0].kind == "tvs"
    dp = d.net_of(u, "io1")
    assert hint._protected(d, dp)

