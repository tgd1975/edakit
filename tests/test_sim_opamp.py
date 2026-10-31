"""The op-amp model (behaviour opamp, maker-coverage FT-3): the output follows the inputs within the rails and the
swing of the datasheet, LIM.range/opamp holds the inputs to the common-mode range and the output to its linear range."""

import shutil

import pytest
from test_sim import failing, simulate

from edakit.sim import netlist

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")

# an LM358-like part at 5 V: output from 0.02 V above ground to 1.5 V below the supply, inputs from ground to 1.5 V
# below the supply – values for the test, not taken from a datasheet
OPAMP = {"lcsc": "C9000301", "mpn": "test dual op-amp", "kind": "ic", "verified": {"by": "test"},
         "values": {"behavior": "opamp", "vout_swing_v": [0.02, -1.5], "vicm_v": [0, -1.5], "iq_a": 0.0007},
         "pins": {"1": {"name": "OUTA", "type": "output", "role": "out_a"},
                  "2": {"name": "-INA", "type": "input", "role": "in_n_a"},
                  "3": {"name": "+INA", "type": "input", "role": "in_p_a"},
                  "4": {"name": "GND", "type": "ground", "role": "gnd"},
                  "8": {"name": "VCC", "type": "power_in", "role": "vcc"}}}
RES = {"type": "resistor", "lcsc": "C17414", "pins": {"1": "1", "2": "2"}}


def follower(project, top_ohm=10e3, bottom_ohm=10e3, part=None):
    """U9 as a voltage follower on +5V: OUTA joined to -INA, +INA from the divider R91 (to +5V) / R92 (to GND), the
    output loaded by R93 (10 kΩ) to GND."""
    project.use_library_part("C17414")
    project.save_part("C9000301", part or OPAMP)
    for key, ohm in (("C9000302", top_ohm), ("C9000303", bottom_ohm), ("C9000304", 10e3)):
        r = project.part("C17414")
        r.update(lcsc=key, mpn=f"test resistor {ohm:g}")
        r["values"]["value_ohm"] = ohm
        project.save_part(key, r)
    g = project.graph()
    g["graph"]["components"] += [
        {"designator": "U9", "type": "ic", "lcsc": "C9000301", "pins": {n: i["name"] for n, i in OPAMP["pins"].items()}},
        {**RES, "designator": "R91", "lcsc": "C9000302"}, {**RES, "designator": "R92", "lcsc": "C9000303"},
        {**RES, "designator": "R93", "lcsc": "C9000304"}]
    project.net(g, "+5V")["pins"] += ["U9.8", "R91.1"]
    project.net(g, "GND")["pins"] += ["U9.4", "R92.2", "R93.2"]
    g["graph"]["nets"] += [{"name": "OA_IN", "pins": ["U9.3", "R91.2", "R92.1"], "v": [0, 5.5]},
                           {"name": "OA_OUT", "pins": ["U9.1", "U9.2", "R93.1"], "v": [0, 5.5]}]
    project.save_graph(g)


def opamp_rows(out, failed=False):
    return [c for c in out["checks"] if c["item"] == "U9" and (not failed or c["result"] == "fail")]


def test_a_follower_inside_its_ranges_passes(project):
    follower(project)                                     # +INA at half the supply: about 2.2–2.5 V
    out = simulate(project)
    assert not failing(out)
    rows = opamp_rows(out)
    assert {r["check"] for r in rows} == {"input in_p_a inside the common-mode range",
                                          "input in_n_a inside the common-mode range", "output out_a linear, inside its swing"}
    assert all(r["id"] == "LIM.range" for r in rows)
    assert all(s["status"] == "ok" for s in out["scenarios"])


def test_above_the_common_mode_range_the_output_saturates(project):
    """+INA at 4/5 of the supply leaves the inputs' range (up to 1.5 V below the supply) and the output stops 1.5 V
    below the supply: both are LIM.range/opamp findings, warnings."""
    follower(project, top_ohm=2.5e3)
    out = simulate(project)
    bad = {(r["check"], r["expected"][:4]) for r in opamp_rows(out, failed=True)}
    assert ("input in_p_a inside the common-mode range", "0 … ") in bad
    assert any(c.startswith("output out_a linear") for c, _ in bad)
    found = [f for f in out["findings"] if f["code"] == "LIM.range" and f["place"] == "U9"]
    assert found and {f["grade"] for f in found} == {"opamp"}
    held = next(r for r in opamp_rows(out, failed=True) if r["check"].startswith("output"))
    assert "held at the limit" in held["actual"]


def test_a_rail_to_rail_part_follows_where_the_other_saturates(project):
    part = {**OPAMP, "values": {**OPAMP["values"], "vout_swing_v": [0.01, -0.01], "vicm_v": [-0.1, 0.1]}}
    follower(project, top_ohm=2.5e3, part=part)
    assert not opamp_rows(simulate(project), failed=True)


def test_a_comparator_is_meant_to_saturate(project):
    part = {**OPAMP, "values": {**OPAMP["values"], "comparator": True, "vicm_v": [0, -0.5]}}
    follower(project, top_ohm=2.5e3, part=part)
    rows = opamp_rows(simulate(project))
    assert rows and not any(r["check"].startswith("output") for r in rows)


def test_the_model_has_its_channel_and_its_quiescent_current(project):
    follower(project)
    import json
    from edakit.design import Design
    from edakit.sim import run as simrun
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    text, meta = netlist.build(Design.from_config(project.config()), sim, next(simrun.scenarios(sim)))
    assert "B_U9_Oa" in text and "B_U9_IQ" in text and meta["opamps"]["U9"]["channels"]["a"]["out"]
