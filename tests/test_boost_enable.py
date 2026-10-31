"""An asynchronous boost converter switched off by its enable (maker-coverage FT-5, appendix PWR 15): the MT3608 of the
library (C84817) as behaviour boost – its output is the net behind the Schottky diode on SW, set by the divider and VREF
0.6 V (data sheet Rev1.1, p. 3, 6). With EN low the converter stops, but the inductor and the diode still join the input
to the output: the output sits at VIN − VD, and what hangs on it sees that (TI SLVA191A: 'The input voltage … is
connected to the output voltage when the device is disabled')."""

import shutil

import pytest
from helpers import check
from reference import Project, add, resistor, wire
from test_sim import simulate

from edakit.design import Design

COIL = {"lcsc": "C9300011", "mpn": "10 µH power inductor numbers (test part)", "kind": "inductor",
        "verified": {"by": "test"}, "values": {"value_h": 10e-6, "dcr_ohm": 0.05}, "limits": {"i_max_a": 2.0},
        "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}}}


def boost(p, r1=190e3, r2=10e3, top=12.5, en="gpio"):
    """U110 MT3608 from +5V: L110 from +5V to BOOST_SW, D110 (SS34) from BOOST_SW to BOOST_OUT, R110 = R1 from BOOST_OUT
    to BOOST_FB, R111 = R2 from BOOST_FB to GND (0.6 V × (1 + R1/R2) = 12 V), 22 µF at the output and 1 kΩ (R112) as
    its load; EN on the MCU's GP7 (net BOOST_EN), or with `en` "vin" on +5V."""
    p.use_library_part("C84817")
    p.save_part(COIL["lcsc"], COIL)
    resistor(p, "C9300012", r1)
    resistor(p, "C9300013", r2)
    resistor(p, "C9300014", 1000)
    g = p.graph()
    add(g, "U110", "ic", "C84817", {"1": "SW", "2": "GND", "3": "FB", "4": "EN", "5": "IN", "6": "NC"}, nc=["6"])
    add(g, "L110", "inductor", COIL["lcsc"], {"1": "1", "2": "2"})
    add(g, "D110", "diode", "C8678", {"1": "K", "2": "A"})
    add(g, "R110", "resistor", "C9300012", {"1": "1", "2": "2"})
    add(g, "R111", "resistor", "C9300013", {"1": "1", "2": "2"})
    add(g, "R112", "resistor", "C9300014", {"1": "1", "2": "2"})
    add(g, "C110", "capacitor", "C45783", {"1": "1", "2": "2"})
    wire(g, "+5V", "U110.5", "L110.1")
    wire(g, "GND", "U110.2", "R111.2", "R112.2", "C110.2")
    wire(g, "BOOST_SW", "L110.2", "U110.1", "D110.2", v=(0, top + 0.5))
    wire(g, "BOOST_OUT", "D110.1", "R110.1", "R112.1", "C110.1", v=(0, top))
    wire(g, "BOOST_FB", "R110.2", "R111.1", "U110.3", v=(0, 0.7))
    if en == "vin":
        wire(g, "+5V", "U110.4")
    else:
        p.free_pins(g, "U1.10")
        wire(g, "BOOST_EN", "U1.10", "U110.4", v=(0, 3.4))
    p.save_graph(g)
    sim = p.sim()
    sim["loads"] = {"idle": {"gpio": {"LED_OE": 1}, "leds_on": []}}
    if en != "vin":
        sim["mcu"]["U1"]["outputs"].append("BOOST_EN")
        sim["loads"] = {"on": {"gpio": {"LED_OE": 1, "BOOST_EN": 1}, "leds_on": []},
                        "off": {"gpio": {"LED_OE": 1, "BOOST_EN": 0}, "leds_on": [],
                                "expect": {"BOOST_OUT": {"max_v": 0.5}}}}
    sim["report"] = ["+5V", "BOOST_OUT", "BOOST_SW"]
    return sim


def scenario(out, load):
    return next(s for s in out["scenarios"] if s["name"].startswith(f"usb-nom/{load}/"))


def test_the_divider_sets_the_mt3608_output_behind_its_diode(tmp_path):
    """Stage G: the divider from the net behind the diode sets 12 V – no REQ.missing/feedback for the missing vout pin;
    more than the net declares is REQ.value/feedback."""
    for top, want in ((12.5, []), (5.5, [("REQ.value", "warning")])):
        p = Project.copy_of_example(tmp_path / f"top{top}")
        boost(p, top=top)
        cfg = p.config()
        rep = check(Design.from_config(cfg), cfg)
        assert sorted((f.code, f.severity) for f in rep.findings if f.grade == "feedback") == want


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_en_high_regulates_and_en_low_passes_the_input_through_the_diode(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    out = simulate(p, boost(p))
    assert all(s["status"] != "error" for s in out["scenarios"])
    on, off = scenario(out, "on"), scenario(out, "off")
    assert on["nets"]["BOOST_OUT"] == pytest.approx(12.0, rel=0.01)
    vin = off["nets"]["+5V"]
    assert vin - 0.5 < off["nets"]["BOOST_OUT"] < vin - 0.1        # VIN − VD of the SS34 at about 5 mA
    state = [c for c in out["checks"] if c["item"] == "U110" and c["check"].startswith("output voltage")]
    assert state and all(c["result"] == "pass" and "/on/" in c["scenario"] for c in state)
    shown = [c for c in out["checks"] if c["item"] == "U110" and c["check"].startswith("output with EN low")]
    assert shown and all(c["result"] == "info" and "/off/" in c["scenario"] for c in shown)
    seen = [f for f in out["findings"] if f["place"] == "BOOST_OUT" and f["code"] == "LIM.v"]
    assert seen and all("/off/" in f["scenario"] for f in seen)      # the load expecting off sees the input
    assert not [f for f in out["findings"] if f["place"] == "U110" and f["code"] == "SIM.state"]


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_en_on_the_input_runs_the_converter(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    out = simulate(p, boost(p, en="vin"))
    sc = scenario(out, "idle")
    assert sc["nets"]["BOOST_OUT"] == pytest.approx(12.0, rel=0.01)
    load = 12.0 / 1000 + 12.0 / 200e3                               # R112 and the divider
    supply = sc["sources"]["J1"]
    assert supply > 12.0 * load / (0.85 * 5.0)                      # the boost's input power at 85 % on top of the rest
    assert not [f for f in out["findings"] if f["place"] == "U110" and f["code"] in ("SIM.state", "SIM.converge")]
