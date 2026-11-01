"""An LED's ideality from the datasheet's IV curve (the 555 blinker, walkthrough 2, M-1): the model's N was fixed at 2,
and D1's curve (Kingbright DSAO7910, p. 3) gave 20–25 mV more at 0.5 mA than the model. values.vf_vs_if [[A, V], …]
– points read off that curve – sets N; vf at vf_at_a of the corner keeps setting IS. Without it N stays 2."""

import json
import math

import pytest

from edakit import schema
from edakit.design import Design
from edakit.sim import netlist

RS = 10


def diode_v(i, n, i_s, rs=RS):
    return n * netlist.VT * math.log(i / i_s + 1) + i * rs


def model_v(line, i):
    """VF at the current i of a .model line led_model wrote."""
    p = dict(kv.split("=") for kv in line.split("(")[1].rstrip(")").split())
    return diode_v(i, float(p["N"]), float(p["IS"]), float(p["RS"]))


# a red AlGaInP LED of N 1.4 through 1.75 V at 2 mA, its curve at 0.5, 1, 2, 5 and 10 mA
N_RED = 1.4
IS_RED = 0.002 / (math.exp((1.75 - 0.002 * RS) / (N_RED * netlist.VT)) - 1)
CURVE = [[i, round(diode_v(i, N_RED, IS_RED), 4)] for i in (0.0005, 0.001, 0.002, 0.005, 0.01)]


def test_the_ideality_follows_the_curve():
    assert netlist.led_ideality(CURVE, RS) == pytest.approx(N_RED, abs=0.01)
    assert netlist.led_ideality(None, RS) == netlist.LED_N == 2.0          # no curve: as before
    assert netlist.led_ideality(CURVE[:1], RS) == netlist.LED_N            # one point gives no slope


def test_the_model_meets_the_curve_at_half_a_milliamp():
    """N = 2 put VF 22 mV below a curve of N 1.4 at 0.5 mA; with the curve the model meets it within 1 mV."""
    fixed = netlist.led_model("a", 1.75, 0.002, RS)
    fitted = netlist.led_model("b", 1.75, 0.002, RS, netlist.led_ideality(CURVE, RS))
    assert model_v(fixed, 0.002) == pytest.approx(1.75, abs=5e-4) == model_v(fitted, 0.002)   # IS of 5 digits
    assert CURVE[0][1] - model_v(fixed, 0.0005) == pytest.approx(0.0217, abs=0.001)
    assert model_v(fitted, 0.0005) == pytest.approx(CURVE[0][1], abs=0.001)


def test_the_netlist_takes_the_curve_of_the_parts_entry(project):
    lcsc = project.comp(project.graph(), "D2")["lcsc"]
    cfg = project.config()
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sc = {"name": "t", "load": sim["loads"]["all_on"], "supply": sim["supplies"]["usb-nom"], "corner": "typ"}
    text, _ = netlist.build(Design.from_config(cfg), sim, sc)
    assert f"LED_{lcsc}_x_typ D(" in text and " N=2 " in text.split(f"LED_{lcsc}_x_typ D(")[1].split("\n")[0]
    entry = project.part(lcsc)
    entry["values"]["vf_vs_if"] = [[0.001, 2.745], [0.005, 2.85], [0.02, 3.06]]
    project.save_part(lcsc, entry)
    text, _ = netlist.build(Design.from_config(project.config()), sim, sc)
    n = netlist.led_ideality(entry["values"]["vf_vs_if"], entry["values"]["rs_ohm"])
    assert 1 < n < 2 and f" N={n:.4g} " in text.split(f"LED_{lcsc}_x_typ D(")[1].split("\n")[0]


@pytest.mark.parametrize("curve, says", [
    ([[0.002, 1.75]], "at least two"),
    ([[0.002, 1.75], [0.001, 1.70]], "rising"),
    ([[0.0, 1.5], [0.002, 1.75]], "above 0"),
    ([[0.001, 1.70], [0.002, 1.70001]], "outside 1 … 4"),
    ("1.75 V", "[[A, V], …]"),
])
def test_part_lint_holds_the_curve_to_its_form(curve, says):
    entry = {"kind": "led", "pins": {"1": {"name": "K", "type": "passive", "role": "cathode"},
                                     "2": {"name": "A", "type": "passive", "role": "anode"}},
             "values": {"vf_typ_v": 1.75, "vf_at_a": 0.002, "vf_vs_if": curve}}
    found = [p for p in schema.problems(entry) if "vf_vs_if" in p]
    assert len(found) == 1 and says in found[0], found
    entry["values"]["vf_vs_if"] = CURVE
    assert not [p for p in schema.problems(entry) if "vf_vs_if" in p]
