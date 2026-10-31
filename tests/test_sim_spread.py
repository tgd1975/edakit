"""The spread of transistor parameters as corners of the simulation (maker-coverage FT-17, sim/spread.py): sim.json
`spread` runs every DC scenario once per corner, hFE, IDSS with VGS(off), VGS(th) and a BJT's leakage at the ends of
their entries' spread; the expected windows of a load (FT-11) and every other check are judged in each corner."""

import json
import math
import shutil

import pytest
from test_sim import simulate

from edakit import engines
from edakit.design import Design
from edakit.sim import netlist, spread
from edakit.sim import run as simrun

NGSPICE = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


def sim_config(project):
    return json.loads((project.root / "hardware" / "sim.json").read_text())


def resistor(project, key, ohm):
    """A resistor entry of the given value (C17414's, renamed) – the stages need values the library does not hold."""
    project.use_library_part("C17414")
    r = project.part("C17414")
    r.update(lcsc=key, mpn=f"test resistor {ohm:g}")
    r["values"]["value_ohm"] = ohm
    project.save_part(key, r)


def stage(project, parts, resistors, nets, plus=(), ground=()):
    """Components and nets added to the example: parts {designator: (lcsc, {pin: name})}, resistors {designator: Ω},
    nets {name: [pins]}, pins on +5V and on GND."""
    g = project.graph()
    for des, (lcsc, pins) in parts.items():
        project.use_library_part(lcsc)
        g["graph"]["components"].append({"designator": des, "type": "transistor", "lcsc": lcsc, "pins": pins})
    for i, (des, ohm) in enumerate(resistors.items()):
        key = f"C9017{i:03d}"
        resistor(project, key, ohm)
        g["graph"]["components"].append({"designator": des, "type": "resistor", "lcsc": key,
                                         "pins": {"1": "1", "2": "2"}})
    project.net(g, "+5V")["pins"] += list(plus)
    project.net(g, "GND")["pins"] += list(ground)
    g["graph"]["nets"] += [{"name": n, "pins": p, "v": [0, 5.5]} for n, p in nets.items()]
    project.save_graph(g)


def expecting(project, net, window, corners=("min", "max")):
    """The example's sim.json with the window on `net` in the load idle and the spread corners."""
    sim = sim_config(project)
    sim["loads"]["idle"]["expect"] = {net: {k: x for k, x in zip(("min_v", "max_v"), window) if x is not None}}
    if corners:
        sim["spread"] = list(corners)
    return sim


def window_rows(out, net, failed=False):
    return [c for c in out["checks"] if c["item"] == net and c["check"] == "net voltage (expected in this load)"
            and (not failed or c["result"] == "fail")]


def corners_of(rows):
    return {r["scenario"].rsplit("/", 1)[-1] for r in rows}


JFET = {"Q50": ("C891687", {"1": "D", "2": "S", "3": "G"})}      # onsemi MMBFJ201: IDSS 0.2 … 1.0 mA


def jfet_booster(project):
    """A J201 booster on +5V biased by fixed resistors: drain resistor R50 6.8 kΩ, source resistor R51 1 kΩ, gate to
    ground through R52 1 MΩ – the drain current is what the part's IDSS and VGS(off) make of R51."""
    stage(project, JFET, {"R50": 6.8e3, "R51": 1e3, "R52": 1e6},
          {"JD": ["Q50.1", "R50.2"], "JS": ["Q50.2", "R51.1"], "JG": ["Q50.3", "R52.1"]},
          plus=["R50.1"], ground=["R51.2", "R52.2"])


def jfet_divider(project):
    """The same J201 with its gate on a divider (R53 3.9 MΩ from +5V, R52 1 MΩ to ground: about 1 V) and a source
    resistor of 10 kΩ – the source follows the gate, the drain current holds whatever the part."""
    stage(project, JFET, {"R50": 10e3, "R51": 10e3, "R52": 1e6, "R53": 3.9e6},
          {"JD": ["Q50.1", "R50.2"], "JS": ["Q50.2", "R51.1"], "JG": ["Q50.3", "R52.1", "R53.2"]},
          plus=["R50.1", "R53.1"], ground=["R51.2", "R52.2"])


# --- JFET: IDSS and VGS(off) ---------------------------------------------------------------------------------------------
@NGSPICE
def test_today_the_typical_jfet_meets_the_window(project):
    """Without spread the J201 is its typical model: the drain sits at 2.7 … 3.2 V over the example's supplies (+5V
    from 4.75 to 5.25 V at J1), inside 1.2 … 3.6 V – the spread of the part is not seen."""
    jfet_booster(project)
    out = simulate(project, expecting(project, "JD", (1.2, 3.6), corners=None))
    rows = window_rows(out, "JD")
    assert rows and {r["result"] for r in rows} == {"pass"}
    assert all("spread" not in s["name"] for s in out["scenarios"])


@NGSPICE
def test_a_fixed_bias_jfet_leaves_its_window_in_the_idss_min_corner(project):
    """IDSS 0.2 mA with VGS(off) −0.3 V: about 0.09 mA through 6.8 kΩ, the drain at 3.8 … 4.3 V – above the window
    of 1.2 … 3.6 V. In the corner max (1.0 mA, −1.5 V) it sits at 1.3 … 1.8 V, inside."""
    jfet_booster(project)
    out = simulate(project, expecting(project, "JD", (1.2, 3.6)))
    bad = window_rows(out, "JD", failed=True)
    assert bad and corners_of(bad) == {"spread-min"} and {r["id"] for r in bad} == {"LIM.v"}
    assert corners_of(window_rows(out, "JD")) == {"spread-min", "spread-max"}
    assert all(3.7 < float(r["actual"].split()[0]) < 4.5 for r in bad)
    assert any(f["code"] == "LIM.v" and f["place"] == "JD" and "spread-min" in f["scenario"] for f in out["findings"])
    assert {s["spread"] for s in out["scenarios"] if "spread" in s} == {"min", "max"}


@NGSPICE
def test_a_window_wide_enough_holds_both_corners(project):
    jfet_booster(project)
    out = simulate(project, expecting(project, "JD", (1.0, 4.6)))
    rows = window_rows(out, "JD")
    assert corners_of(rows) == {"spread-min", "spread-max"} and {r["result"] for r in rows} == {"pass"}


@NGSPICE
def test_a_divider_and_a_large_source_resistor_hold_the_drain(project):
    """The gate on 1 V and 10 kΩ at the source: the drain current moves by a third of the fixed bias's swing, the
    drain sits at 2.7 … 3.9 V over spread and supply – inside 2.5 … 4.2 V in both corners."""
    jfet_divider(project)
    out = simulate(project, expecting(project, "JD", (2.5, 4.2)))
    rows = window_rows(out, "JD")
    assert corners_of(rows) == {"spread-min", "spread-max"} and {r["result"] for r in rows} == {"pass"}


# --- BJT: hFE ------------------------------------------------------------------------------------------------------------
BJT = {"Q60": ("C124482", {"1": "E", "2": "B", "3": "C"})}      # onsemi 2N3904: hFE 70 … 300


@NGSPICE
def test_a_bjt_biased_by_its_hfe_fails_in_the_low_hfe_corner(project):
    """A 2N3904 with its base current from R61 1 MΩ to +5V and R60 2.2 kΩ at the collector: about 4.3 µA of base
    current, 0.3 mA at hFE 70 – the collector at 3.9 … 4.3 V, above 1.8 … 3.8 V; at hFE 300 at 1.9 … 2.1 V,
    inside."""
    stage(project, BJT, {"R60": 2.2e3, "R61": 1e6}, {"QC": ["Q60.3", "R60.2"], "QB": ["Q60.2", "R61.2"]},
          plus=["R60.1", "R61.1"], ground=["Q60.1"])
    out = simulate(project, expecting(project, "QC", (1.8, 3.8)))
    bad = window_rows(out, "QC", failed=True)
    assert bad and corners_of(bad) == {"spread-min"}
    assert corners_of(window_rows(out, "QC")) == {"spread-min", "spread-max"}


@NGSPICE
def test_a_bjt_with_emitter_degeneration_holds_both_corners(project):
    """Base divider R62 33 kΩ / R63 15 kΩ, emitter resistor R64 1 kΩ: the collector current follows the divider, not
    the gain."""
    stage(project, BJT, {"R60": 2.2e3, "R62": 33e3, "R63": 15e3, "R64": 1e3},
          {"QC": ["Q60.3", "R60.2"], "QB": ["Q60.2", "R62.2", "R63.1"], "QE": ["Q60.1", "R64.1"]},
          plus=["R60.1", "R62.1"], ground=["R63.2", "R64.2"])
    out = simulate(project, expecting(project, "QC", (2.0, 4.0)))
    rows = window_rows(out, "QC")
    assert corners_of(rows) == {"spread-min", "spread-max"} and {r["result"] for r in rows} == {"pass"}


@NGSPICE
def test_leakage_shifts_the_bias_in_the_corner_max(project):
    """The fixed-bias stage with a leaky transistor – the 2N3904's entry with 2 µA at 25 °C and 8 µA at 45 °C, values
    for the test in the range of a germanium part, not a datasheet's: at the example's 40 °C about 5.7 µA flow from
    collector to base, more than R61 feeds, and hFE 300 makes 3 mA of them – the stage saturates in the corner max.
    With the 2N3904's own leakage (0.12 µA at 40 °C) the corner max stays inside."""
    stage(project, BJT, {"R60": 2.2e3, "R61": 1e6}, {"QC": ["Q60.3", "R60.2"], "QB": ["Q60.2", "R61.2"]},
          plus=["R60.1", "R61.1"], ground=["Q60.1"])
    sim = expecting(project, "QC", (1.0, 4.6))
    assert not window_rows(simulate(project, sim), "QC", failed=True)
    part = project.part("C124482")
    part["values"]["icbo_a"] = {"25": 2e-6, "45": 8e-6}
    project.save_part("C124482", part)
    bad = window_rows(simulate(project, sim), "QC", failed=True)
    assert bad and corners_of(bad) == {"spread-max"} and all(float(r["actual"].split()[0]) < 0.5 for r in bad)


# --- MOSFET: VGS(th) -----------------------------------------------------------------------------------------------------
@NGSPICE
def test_a_bs170_from_3v3_is_not_on_in_the_high_threshold_corner(project):
    """A BS170 (VGS(th) 0.8 / 2.0 / 3.0 V) pulls a 330 Ω load from +5V, its gate on a divider at 3.3 V: on in the
    typical part and in the corner min, nearly off in the corner max – the drain far above the 1 V a switched-on load
    expects."""
    stage(project, {"Q70": ("C111691", {"1": "D", "2": "G", "3": "S"})}, {"R70": 330, "R71": 10e3, "R72": 20e3},
          {"MD": ["Q70.1", "R70.2"], "MG": ["Q70.2", "R71.2", "R72.1"]},
          plus=["R70.1", "R71.1"], ground=["Q70.3", "R72.2"])
    out = simulate(project, expecting(project, "MD", (None, 1.0), corners=("min", "typ", "max")))
    rows = window_rows(out, "MD")
    assert corners_of(rows) == {"spread-min", "vf-min", "vf-max", "spread-max"}   # typ: named as without spread
    assert corners_of(window_rows(out, "MD", failed=True)) == {"spread-max"}


# --- the corners per part, the config ------------------------------------------------------------------------------------
@NGSPICE
def test_an_extra_scenario_names_its_own_corner_per_part(project):
    jfet_booster(project)
    sim = expecting(project, "JD", (1.2, 3.6), corners=None)
    sim["extra_scenarios"] = [{"name": "Q50 low", "supply": {"J1": 5.0}, "load": "idle", "spread": {"Q50": "min"}}]
    out = simulate(project, sim)
    bad = window_rows(out, "JD", failed=True)
    assert {r["scenario"] for r in bad} == {"Q50 low"}


@NGSPICE
def test_an_ac_run_is_judged_in_each_corner(project):
    """With the domain guitar on (the gate an instrument input), an AC run that names no scenario of its own
    linearises around the first DC scenario of each spread corner (usb-min/idle/vf-min): the booster's gain from its
    gate to its drain, gm × R50 / (1 + gm × R51), is about 10 dB in the corner min; in the corner max the drain sits at
    1.3 V, the JFET leaves its saturation region and the gain falls below 5 dB – SIM.response there only (a warning:
    its row reads warn)."""
    jfet_booster(project)
    g = project.graph()
    project.net(g, "JG")["instrument"] = True
    project.save_graph(g)
    sim = expecting(project, "JD", (1.2, 4.6))
    sim["ac"] = {"boost": {"input": "JG", "output": "JD", "expect": {"gain_db": [{"at_hz": 1000, "min": 8, "max": 12}]}}}
    out = simulate(project, sim)
    assert set(out["ac"]) == {"boost spread-min", "boost spread-max"}
    rows = [r for r in out["checks"] if r["id"] == "SIM.response"]
    assert {r["scenario"] for r in rows} == {"ac boost spread-min", "ac boost spread-max"}
    assert {r["scenario"] for r in rows if r["result"] == "warn"} == {"ac boost spread-max"}
    assert all(float(r["actual"].split()[0]) < 5 for r in rows if r["result"] == "warn")
    assert {r["result"] for r in rows} == {"pass", "warn"}
    assert out["ac"]["boost spread-max"]["scenario"].endswith("/spread-max")


def test_the_spread_config_is_checked(project):
    jfet_booster(project)
    design = Design.from_config(project.config())
    sim = sim_config(project)
    for wrong in (["low"], "min", [], ["min", "min"]):
        with pytest.raises(spread.SpreadError, match="spread"):
            spread.check(design, {**sim, "spread": wrong})
    with pytest.raises(spread.SpreadError, match="R50 – no transistor"):
        spread.check(design, {**sim, "extra_scenarios": [{"name": "x", "supply": {"J1": 5}, "load": "idle",
                                                          "spread": {"R50": "min"}}]})
    with pytest.raises(spread.SpreadError, match="transients t: spread Q50 – one of min, typ, max"):
        spread.check(design, {**sim, "transients": {"t": {"supply": {"J1": 5}, "load": "idle", "stop_s": 1e-3,
                                                          "spread": {"Q50": "hot"}}}})
    with pytest.raises(simrun.SimError, match="spread"):
        simrun.run_all(design, {**sim, "spread": ["high"]})


def test_without_the_key_the_scenarios_stay_as_they_were(project):
    sim = sim_config(project)
    names = [s["name"] for s in simrun.scenarios(sim)]
    assert names == [f"{s}/{ld}/vf-{c}" for s in sim["supplies"] for ld in sim["loads"] for c in sim["corners"]]
    with_spread = [s["name"] for s in simrun.scenarios({**sim, "spread": ["min", "max"]})]
    assert len(with_spread) == 2 * len(names) and with_spread[0] == names[0] + "/spread-min"


# --- the models in the corners -------------------------------------------------------------------------------------------
def entry(project, lcsc):
    project.use_library_part(lcsc)
    return project.part(lcsc)


def params(text):
    return {k: spice_value for k, spice_value in spread.parse_model(text)[2].items()}


def test_the_corner_models(project):
    q = entry(project, "C124482")                          # 2N3904: BF 70 / 300
    assert spread.corner_model(q, "Q1", "typ") == ("2N3904", q["spice"]["model"])
    name, text = spread.corner_model(q, "Q1", "min")
    assert name == "2N3904_min" and params(text)["BF"] == "70" and params(text)["IS"] == "6f"
    assert params(spread.corner_model(q, "Q1", "max")[1])["BF"] == "300"
    j = entry(project, "C891687")                          # MMBFJ201: the paired ends
    p = params(spread.corner_model(j, "Q1", "min")[1])
    assert float(p["VTO"]) == -0.3 and math.isclose(float(p["BETA"]), 0.0002 / 0.09, rel_tol=1e-5)
    p = params(spread.corner_model(j, "Q1", "max")[1])
    assert float(p["VTO"]) == -1.5 and math.isclose(float(p["BETA"]), 0.001 / 2.25, rel_tol=1e-5)
    assert p["LAMBDA"] == "0.016"
    m = entry(project, "C232838")                          # 2N7000: VTO 3.0 (max), KP holds 6 Ω at 4.5 V
    p = params(spread.corner_model(m, "Q1", "min")[1])
    assert float(p["VTO"]) == 0.8 and math.isclose(float(p["KP"]), 0.131 * 1.5 / 3.7, rel_tol=1e-4)
    assert spread.corner_model(m, "Q1", "max")[1].endswith("VTO=3 KP=0.131)")
    pm = entry(project, "C15127")                          # AO3401A: a P-MOSFET, by magnitude
    assert float(params(spread.corner_model(pm, "Q1", "min")[1])["VTO"]) == -0.5
    assert float(params(spread.corner_model(pm, "Q1", "max")[1])["VTO"]) == -1.3
    pj = {**j, "kind": "pjfet", "values": {"idss_a": [0.002, None, 0.008], "vgs_off_v": [1, None, 4]},
          "spice": {"model": ".model P1 PJF(VTO=-2 BETA=1m)"}}
    assert float(params(spread.corner_model(pj, "Q1", "max")[1])["VTO"]) == -4.0   # ngspice: VTO < 0 for a PJF too
    bare = {**q, "values": {}}
    assert spread.corner_model(bare, "Q1", "min") == ("2N3904", q["spice"]["model"])


def test_the_leakage_at_the_ambient(project):
    q = entry(project, "C124482")                          # 50 nA at 25 °C, 15.7 µA at 125 °C
    assert math.isclose(spread.leakage(q, 25), 5e-8)
    assert math.isclose(spread.leakage(q, 125), 1.57e-5)
    assert math.isclose(spread.leakage(q, 75), math.sqrt(5e-8 * 1.57e-5), rel_tol=1e-9)
    assert spread.leakage(q, 145) > 1.57e-5                 # along the last two beyond them
    assert spread.leakage({"values": {"icbo_a": {"25": 1e-6}}}, 60) == 1e-6
    assert spread.leakage({"values": {}}, 60) == 0.0


def test_the_netlist_of_a_corner(project):
    stage(project, BJT, {"R60": 2.2e3, "R61": 1e6}, {"QC": ["Q60.3", "R60.2"], "QB": ["Q60.2", "R61.2"]},
          plus=["R60.1", "R61.1"], ground=["Q60.1"])
    jfet_booster(project)
    design = Design.from_config(project.config())
    sim = sim_config(project)                               # ambient_c 40
    base = next(simrun.scenarios(sim))
    text, meta = netlist.build(design, sim, {**base, "spread": "max"})
    assert "Q_Q60 n_qc n_qb 0 2N3904_max" in text and ".model 2N3904_max NPN(IS=6f BF=300 IKF=0.23)" in text
    leak = spread.leakage(design.part("Q60"), 40)
    assert f"I_Q60_LEAK n_qc n_qb DC {leak:.6g}" in text and meta["leakage"] == {"Q60": leak}
    assert "J_Q50 n_jd n_jg n_js MMBFJ201_max" in text and "print @j_q50[id] @j_q50[ig]" in text
    text, meta = netlist.build(design, sim, {**base, "spread": "min"})
    assert "LEAK" not in text and "leakage" not in meta
    text, _ = netlist.build(design, sim, base)
    assert "2N3904 NPN(IS=6f BF=230 IKF=0.23)" in text and "J_Q50 n_jd n_jg n_js MMBFJ201\n" in text
    assert not any(f"{m}_{c}" in text for m in ("2N3904", "MMBFJ201") for c in ("min", "max"))


def test_the_checks_know_a_jfet(project):
    """A JFET is a transistor of the graph (STRUCT.identity) whose declared drain range stage G holds to VDG: 30 V on
    the drain needs 45 V with the transistors' factor 1.5, the MMBFJ201 has 40 V."""
    jfet_booster(project)
    cfg = project.config()
    found = engines.run_all(Design.from_config(cfg), cfg).findings
    assert not [f for f in found if "Q50" in f.place and f.code in ("STRUCT.identity", "STRUCT.prefix", "PARTS.schema")]
    assert not [f for f in found if f.code == "LIM.v" and f.place == "Q50"]
    g = project.graph()
    project.net(g, "JD")["v"] = [0, 30]
    project.save_graph(g)
    found = engines.run(Design.from_config(cfg), cfg).findings
    assert [f.text for f in found if f.code == "LIM.v" and f.place == "Q50"] == [
        "Q50: |VDG| up to 30.0 V, rated 40 V"]


@NGSPICE
def test_a_jfet_is_held_to_its_limits(project):
    """The J201's drain-gate voltage, gate current and power against its entry; a transistor without a spread is named
    in a row of information."""
    jfet_booster(project)
    out = simulate(project, expecting(project, "JD", (0, 5), corners=("max",)))
    q = {c["check"] for c in out["checks"] if c["item"] == "Q50"}
    assert {"|VDG|", "gate reverse voltage |VGS|", "forward gate current", "power dissipation"} <= q
    assert not [c for c in out["checks"] if c["item"] == "Q50" and c["result"] in ("fail", "warn")]
    assert out["net_currents"]["JD"]["i_max_a"] > 1e-4
    part = json.loads((project.root / "hardware" / "parts" / "C891687.json").read_text())
    part["values"] = {}
    (project.root / "hardware" / "parts" / "C891687.json").write_text(json.dumps(part))
    out = simulate(project, expecting(project, "JD", (0, 5), corners=("max",)))
    info = [c for c in out["checks"] if c["id"] == "SIM.config" and c["item"] == "spread"]
    assert info and info[0]["result"] == "info" and "Q50" in info[0]["actual"]
