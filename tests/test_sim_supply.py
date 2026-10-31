"""Stage E seen red at the supplies: a part outside its operating range, an input between its thresholds, a source or
a cell fed backwards, a power bank that switches off at the board's least current."""

import json
import shutil

import pytest

from edakit.sim import run as simrun
from test_sim import failing, simulate

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")

RANGE = "supply voltage at VDD inside its operating range"


def test_supply_inside_the_operating_range(project):
    out = simulate(project)                                       # the example: U2 (TLC5916, VDD 3–5.5 V) on 3V3
    ok = [c for c in out["checks"] if c["item"] == "U2" and c["check"] == RANGE]
    assert len(ok) == 12 and all(c["result"] == "pass" and c["actual"] == "3.3 V" for c in ok)
    part = project.part("C90107")
    part["limits"]["vdd_op_min_v"] = 4.5                           # a 5 V-only part like the TPIC6B595 on 3V3
    project.save_part("C90107", part)
    bad = failing(simulate(project))
    assert {(c["id"], c["item"], c["check"], c["actual"], c["expected"]) for c in bad} == {
        ("LIM.range", "U2", RANGE, "3.3 V", "4.5 … 5.5 V")}
    assert len(bad) == 12                                         # in every scenario
    part["limits"]["vdd_op_min_v"] = 3.0
    part["pins"]["16"].update(v_op_min_v=4.5, v_op_max_v=5.5)    # the pin's own range wins over the part's
    project.save_part("C90107", part)
    assert {(c["item"], c["expected"]) for c in failing(simulate(project))} == {("U2", "4.5 … 5.5 V")}


def five_volt_driver(project):
    """U2 (TLC5916) on +5V instead of 3V3, with its thresholds from TI SLVS695D 7.3: VIH 0.7 × VDD, VIL 0.3 × VDD."""
    g = project.graph()
    for ref in ("U2.16", "C1.1"):
        project.net(g, "3V3")["pins"].remove(ref)
        project.net(g, "+5V")["pins"].append(ref)
    project.save_graph(g)
    thresholds(project)


def thresholds(project):
    part = project.part("C90107")
    part["values"].update(vih_ratio=0.7, vil_ratio=0.3)
    project.save_part("C90107", part)


def test_inputs_at_a_valid_logic_level(project):
    thresholds(project)                                           # U2 on 3V3: VIH 2.31 V, the MCU's 3.3 V reach it
    out = simulate(project)
    assert not failing(out)
    levels = [c for c in out["checks"] if c["item"].startswith("U2 ") and c["check"].startswith("input level")]
    assert {c["item"] for c in levels} == {"U2 LED_SDI", "U2 LED_CLK", "U2 LED_LE", "U2 LED_OE"}
    assert {c["check"].split()[2] for c in levels} == {"high", "low"}
    high = [c for c in out["checks"] if c["check"].startswith("output high level reaches VIH")]
    assert {c["item"] for c in high} == {"U1 LED_SDI", "U1 LED_CLK", "U1 LED_LE", "U1 LED_OE"} and len(high) == 48


def test_input_between_its_thresholds(project):
    five_volt_driver(project)                                     # VDD 4.4–5.0 V: VIH 3.1–3.5 V against 3.3 V
    bad = failing(simulate(project))
    assert {c["id"] for c in bad} == {"LVL.threshold"}
    assert {c["item"] for c in bad} == {"U1 LED_SDI", "U1 LED_CLK", "U1 LED_LE", "U1 LED_OE", "U2 LED_OE"}
    oe = next(c for c in bad if c["item"] == "U2 LED_OE" and c["scenario"] == "usb-max/idle/vf-min")
    assert oe["check"].startswith("input level undefined at OE(ED2)") and oe["actual"] == "3.3 V"
    sdi = next(c for c in bad if c["item"] == "U1 LED_SDI" and c["scenario"] == "usb-max/idle/vf-min")
    assert sdi["check"] == "output high level reaches VIH of U2 SDI" and sdi["actual"] == "3.3 V"
    assert not [c for c in bad if c["scenario"].startswith("usb-min/")]   # +5V at 4.4 V: VIH 3.1 V


def test_ratio_needs_one_supply_pin(project):
    thresholds(project)
    part = project.part("C90107")
    part["pins"]["16"].pop("role")                                # two power_in pins on two nets, neither marked vdd
    part["pins"]["15"]["type"] = "power_in"
    project.save_part("C90107", part)
    bad = failing(simulate(project))
    assert {(c["item"], c["check"]) for c in bad if c["check"].startswith("input thresholds")} == {
        ("U2", "input thresholds as a ratio of the supply")}


BACK = "current into the supply (fed backwards)"
CHARGE = "current into the cell (charging)"


def sim_config(project):
    return json.loads((project.root / "hardware" / "sim.json").read_text())


def module_usb(sim, **supplies):
    """U1 (Pico 2) as a second source at VSYS, as a module whose USB reaches its 5 V pin without a diode."""
    sim["sources"]["U1"] = {"plus": "39", "minus": "3", "r_ohm": 0.3, "i_max_a": 0.5}
    sim["supplies"] = supplies or sim["supplies"]
    return sim


def test_no_source_is_fed_backwards(project):
    out = simulate(project)
    fed = [c for c in out["checks"] if c["item"] == "J1" and c["check"] == BACK]
    assert len(fed) == 12 and all(c["result"] == "pass" and c["actual"] == "0 A" for c in fed)
    sim = module_usb(sim_config(project), both={"J1": 5.25, "U1": 4.75})   # the PC's USB below the supply at J1
    bad = failing(simulate(project, sim))
    assert {(c["id"], c["item"], c["check"], c["expected"]) for c in bad} == {("LIM.backfeed", "U1", BACK, "≤ 1 mA")}
    assert len(bad) == 4 and all(0.2 < float(c["actual"].split()[0]) < 0.35 for c in bad)   # 0.25–0.29 A into the PC
    sim["sources"]["U1"]["i_back_max_a"] = 0.5                    # the source's own limit
    assert not failing(simulate(project, sim))
    sim = module_usb(sim_config(project), both={"U1": 5.25, "J1": 4.75})   # D1 blocks the way into J1
    out = simulate(project, sim)
    assert not failing(out)
    j1 = [c for c in out["checks"] if c["item"] == "J1" and c["check"] == BACK]
    assert len(j1) == 4 and all(float(c["actual"].split()[0]) < 1e-3 for c in j1)


# A holder for one cell, kind battery_holder, roles plus and minus – the test's own entry
HOLDER = {"lcsc": "C9000001", "mpn": "test holder", "kind": "battery_holder", "verified": {"by": "test"},
          "pins": {"1": {"name": "+", "type": "power_output", "role": "plus"},
                   "2": {"name": "-", "type": "ground", "role": "minus"}},
          "values": {"cells": 1}, "limits": {}}


def cells_on_the_rail(project):
    """BT1 straight on +5V, next to J1 behind D1: primary cells, nothing between them and the USB supply."""
    project.save_part(HOLDER["lcsc"], HOLDER)
    g = project.graph()
    g["graph"]["components"].append({"designator": "BT1", "type": "battery_holder", "lcsc": HOLDER["lcsc"],
                                     "part": HOLDER["mpn"], "pins": {"1": "+", "2": "-"}})
    project.net(g, "+5V")["pins"].append("BT1.1")
    project.net(g, "GND")["pins"].append("BT1.2")
    project.save_graph(g)
    sim = sim_config(project)
    sim["cells"] = {"fresh": {"v": 4.8, "r": 0.45}}               # three fresh AA cells as one: 3 x 1.6 V, 3 x 0.15 Ω
    sim["supplies"] = {"usb+cells": {"J1": 5.25, "BT1": "fresh"}, "cells": {"BT1": "fresh"}}
    return sim


def test_no_cell_is_charged(project):
    sim = cells_on_the_rail(project)
    out = simulate(project, sim)
    bad = failing(out)
    assert {(c["id"], c["scenario"].split("/")[0], c["item"], c["check"], c["expected"]) for c in bad} == {
        ("LIM.backfeed", "usb+cells", "BT1", CHARGE, "≤ 1 mA")}
    assert len(bad) == 4 and all(float(c["actual"].split()[0]) > 0.01 for c in bad)
    alone = [c for c in out["checks"] if c["scenario"].startswith("cells/") and c["check"] == CHARGE]
    assert len(alone) == 4 and all(c["result"] == "pass" and c["actual"] == "0 A" for c in alone)
    sim["cells"]["fresh"]["i_charge_max_a"] = 0.5                 # a rechargeable pack, charged on purpose
    assert not failing(simulate(project, sim))


ON = "current keeps the supply on"
LEAST = f"{ON} (least current: U1 40 mA)"


def power_bank_and_wifi(project):
    """J1 a power bank that switches off below 100 mA; U1 a module whose current varies – 0.27 A while it transmits
    Wi-Fi (an ESP32: 240 mA at +19.5 dBm, Espressif ESP32 datasheet v5.3 table 5-4), 40 mA at the least."""
    part = project.part("C41407547")
    part["values"].update(i_core_a=0.27, i_core_min_a=0.04)
    project.save_part("C41407547", part)
    sim = sim_config(project)
    sim["sources"]["J1"]["i_min_a"] = 0.1
    return sim


def test_minimum_load_at_the_least_current(project):
    sim = power_bank_and_wifi(project)
    out = simulate(project, sim)
    on = {c["scenario"]: c for c in out["checks"] if c["item"] == "J1" and c["check"].startswith(ON)}
    assert len(on) == 12 and {c["check"] for c in on.values()} == {LEAST}
    bad = failing(out)                                            # idle with U1 at 40 mA: 42–47 mA from J1
    assert {(c["id"], c["item"], c["check"], c["expected"]) for c in bad} == {("LIM.i", "J1", LEAST, "≥ 100 mA")}
    assert {c["scenario"].split("/")[1] for c in bad} == {"idle"} and len(bad) == 6
    assert all(0.04 < float(c["actual"].split()[0]) < 0.05 for c in bad)
    assert all(0.11 < float(c["actual"].split()[0]) < 0.13 for s, c in on.items() if "/all_on/" in s)
    drawn = {c["scenario"]: c for c in out["checks"] if c["item"] == "J1" and c["check"] == "current from the supply"}
    for row in out["scenarios"]:                                  # every other check: U1 at its upper bound, 0.27 A
        assert drawn[row["name"]]["actual"] == f"{row['sources']['J1']:.4g} A" and row["sources"]["J1"] > 0.22
    part = project.part("C41407547")
    del part["values"]["i_core_min_a"]                            # without it: the minimum load at i_core_a, as before
    project.save_part("C41407547", part)
    out = simulate(project, sim)
    on = [c for c in out["checks"] if c["item"] == "J1" and c["check"].startswith(ON)]
    assert len(on) == 12 and {c["check"] for c in on} == {ON} and not failing(out)


def test_least_current_runs_only_for_a_minimum_load(project, monkeypatch):
    sim = power_bank_and_wifi(project)
    runs, real = [], simrun.ngspice

    def counted(text, keep=None, name="run"):
        runs.append(name)
        return real(text, keep, name)
    monkeypatch.setattr(simrun, "ngspice", counted)
    simulate(project, sim)
    assert len(runs) == 24 and runs[:2] == ["usb-min/idle/vf-min", "usb-min/idle/vf-min least current"]
    runs.clear()
    del sim["sources"]["J1"]["i_min_a"]                           # no source with a minimum load: no second run
    out = simulate(project, sim)
    assert len(runs) == 12 and not [c for c in out["checks"] if c["check"].startswith(ON)]


def test_least_current_inside_the_upper_bound(project):
    sim = power_bank_and_wifi(project)
    part = project.part("C41407547")
    part["values"]["i_core_min_a"] = 0.3                          # above i_core_a: no least current
    project.save_part("C41407547", part)
    bad = failing(simulate(project, sim))
    assert {(c["id"], c["item"]) for c in bad} == {("SIM.converge", "circuit")} and len(bad) == 12
    assert "U1: i_core_min_a 0.3 – the least current, a number from 0 to i_core_a (0.27 A)" in bad[0]["actual"]


def names(sim):
    return [s["name"] for s in simrun.scenarios(sim)]


def test_scenarios_for_every_combination_of_sources(project):
    sim = module_usb(sim_config(project))                         # U1 a source, but no supply switches it on
    before = names(sim)
    sim["combine_sources"] = {"J1": [4.75, 5.25], "U1": [4.75, 5.25]}
    generated = simrun.generated_supplies(sim)                    # J1 4.75 and J1 5.25 are usb-min and usb-max
    assert list(generated) == ["U1 4.75", "U1 5.25", "J1 5.25 + U1 4.75", "U1 5.25 + J1 4.75"]
    assert generated["J1 5.25 + U1 4.75"] == {"J1": 5.25, "U1": 4.75}
    after = names(sim)
    assert after[:12] == before and len(after) == 12 + 4 * 2 * 2  # every load and corner
    assert "J1 5.25 + U1 4.75/all_on/vf-min" in after
    out = simulate(project, sim)
    row = next(s for s in out["scenarios"] if s["name"] == "J1 5.25 + U1 4.75/all_on/vf-min")
    assert row["supply"] == "J1 5.25 + U1 4.75" and row["sources"]["U1"] == pytest.approx(-0.247, abs=0.01)
    bad = failing(out)                                            # the back-feed into U1 – SIM.state says so
    assert {(c["scenario"].split("/")[0], c["item"], c["check"]) for c in bad} == {
        ("J1 5.25 + U1 4.75", "U1", "current into the supply (fed backwards)")}
    sim.pop("combine_sources")
    assert names(sim) == before                                   # no key: the scenarios of today


def test_an_extra_scenario_takes_a_combination_over(project):
    sim = module_usb(sim_config(project))
    sim["combine_sources"] = {"J1": [4.75, 5.25], "U1": [4.75, 5.25]}
    sim["extra_scenarios"] = [{"name": "flashing with J1 plugged in", "supply": {"J1": 5.25, "U1": 4.75},
                               "load": "idle", "info": True}]    # excluded by procedure: unplug J1 while flashing
    got = names(sim)
    assert not [n for n in got if n.startswith("J1 5.25 + U1 4.75/idle/")]
    assert [n for n in got if n.startswith("J1 5.25 + U1 4.75/all_on/")] and got[-1] == "flashing with J1 plugged in"
    sim["supplies"]["pc"] = {"U1": 5.25, "note": "the PC alone"}    # the same settings by hand: run once, by its name
    assert "U1 5.25" not in simrun.generated_supplies(sim)


def test_combinations_with_cells():
    sim = {"sources": {"J1": {"plus": "1", "minus": "2"}}, "cells": {"empty": {"v": 1.0, "r": 0.4},
                                                                     "fresh": {"v": 1.6, "r": 0.15}},
           "supplies": {}, "combine_sources": {"J1": [4.75, 5.25], "BT1": ["empty", "fresh"]}}
    assert simrun.generated_supplies(sim) == {
        "J1 4.75": {"J1": 4.75}, "J1 5.25": {"J1": 5.25}, "BT1 empty": {"BT1": "empty"}, "BT1 fresh": {"BT1": "fresh"},
        "J1 5.25 + BT1 empty": {"J1": 5.25, "BT1": "empty"}, "BT1 fresh + J1 4.75": {"BT1": "fresh", "J1": 4.75}}
    sim["combine_sources"] = {"J1": [4.75, 5.25]}                 # one source: its two cases alone
    assert list(simrun.generated_supplies(sim)) == ["J1 4.75", "J1 5.25"]


@pytest.mark.parametrize("combine", [True, {"J9": [4.75, 5.25]}, {"J1": [5.0]}, {"BT1": ["empty", "full"]}])
def test_combine_sources_names_what_it_combines(combine):
    sim = {"sources": {"J1": {"plus": "1", "minus": "2"}}, "cells": {"empty": {"v": 1.0, "r": 0.4}},
           "supplies": {}, "combine_sources": combine}
    with pytest.raises(simrun.SimError, match="combine_sources"):
        simrun.generated_supplies(sim)


def test_sim_prints_the_generated_supplies(project, capsys):
    import argparse
    sim = module_usb(sim_config(project))
    sim["combine_sources"] = {"J1": [4.75, 5.25], "U1": [4.75, 5.25]}
    (project.root / "hardware" / "sim.json").write_text(json.dumps(sim))
    simrun.main(project.config(), argparse.Namespace(json=None, keep=None))
    text = capsys.readouterr().out
    assert text.count("combine_sources:") == 1
    assert "combine_sources: U1 4.75, U1 5.25, J1 5.25 + U1 4.75, U1 5.25 + J1 4.75" in text
