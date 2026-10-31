"""A constant-current step-down LED driver (maker-coverage FT-14, appendix LED 19): behaviour cc_led_driver – the LED
current is the sense voltage over R_S, the input has to stay above the LED string plus what R_S, the inductor and the
switch drop, R_S at least the datasheet's minimum, the current within the driver's maximum. The drivers are the
library's PT4115 (C84512: IOUT = 0.1 V / RS, RS ≥ 0.082 Ω, VCSN 95 / 98 / 101 mV, 1.2 A, RSW 0.6 Ω – data sheet
PT4115_DS Rev EN_2.9) and AL8860 (C125330: VSENSE 96 / 100 / 104 mV, TSOT25 1 A, RSW 0.3 Ω, 98 % duty – DS39014
Rev. 8 - 2); LEDs, inductor and sense resistor are test parts."""

import json
import shutil

import pytest
from reference import Project, add, wire
from test_sim import simulate

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")

LED = {"lcsc": "C9300001", "mpn": "white 1 W LED numbers (test part)", "kind": "led", "verified": {"by": "test"},
       "values": {"color": "white", "vf_typ_v": 3.2, "vf_min_v": 3.0, "vf_max_v": 3.4, "vf_at_a": 0.35, "rs_ohm": 0.5},
       "limits": {"if_max_a": 1.0, "vr_max_v": 5},
       "pins": {"1": {"name": "A", "type": "passive", "role": "anode"},
                "2": {"name": "K", "type": "passive", "role": "cathode"}}}
COIL = {"lcsc": "C9300002", "mpn": "68 µH power inductor numbers (test part)", "kind": "inductor",
        "verified": {"by": "test"}, "values": {"value_h": 68e-6, "dcr_ohm": 0.2},
        "limits": {"i_max_a": 1.6, "i_sat_a": 1.8},
        "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}}}


def sense(p, ohm):
    """C9300003: a sense resistor of `ohm`, 1 W (test part)."""
    p.save_part("C9300003", {"lcsc": "C9300003", "mpn": f"sense resistor {ohm:g} Ω (test part)", "kind": "resistor",
                             "verified": {"by": "test"}, "values": {"value_ohm": ohm}, "limits": {"p_max_w": 1.0},
                             "pins": {"1": {"name": "1", "type": "passive", "role": "1"},
                                      "2": {"name": "2", "type": "passive", "role": "2"}}})


def driver(p, key="C84512", rs=0.13, vin=15.0, leds=3, dim=False, coil=None):
    """U100 (PT4115 or AL8860) from J100 (vin) on LED_VIN: R100 = R_S from LED_VIN to LED_CS, `leds` LEDs D100 …
    in series from LED_CS to LED_K, L100 from LED_K to LED_SW, the Schottky D110 (SS34) from LED_SW back to LED_VIN,
    22 µF at the input. With `dim` the MCU's GP7 drives DIM (net LED_DIM), else DIM floats."""
    p.use_library_part(key)
    p.save_part(LED["lcsc"], LED)
    p.save_part(COIL["lcsc"], coil or COIL)
    sense(p, rs)
    entry = json.loads((p.root / "hardware" / "parts" / f"{key}.json").read_text())
    role = {i.get("role"): n for n, i in entry["pins"].items()}
    g = p.graph()
    add(g, "U100", "ic", key, {n: i["name"] for n, i in entry["pins"].items()}, nc=[] if dim else [role["dim"]])
    add(g, "J100", "connector", "C131337", {"1": "1", "2": "2"})
    add(g, "R100", "resistor", "C9300003", {"1": "1", "2": "2"})
    add(g, "L100", "inductor", COIL["lcsc"], {"1": "1", "2": "2"})
    add(g, "D110", "diode", "C8678", {"1": "K", "2": "A"})
    add(g, "C100", "capacitor", "C45783", {"1": "1", "2": "2"})
    top = (0, vin + 0.5)
    wire(g, "LED_VIN", "J100.1", f"U100.{role['vin']}", "R100.1", "D110.1", "C100.1", v=top)
    wire(g, "GND", "J100.2", f"U100.{role['gnd']}", "C100.2")
    wire(g, "LED_CS", f"U100.{role['sense']}", "R100.2", v=top)
    prev = "LED_CS"
    for i in range(leds):
        add(g, f"D{100 + i}", "led", LED["lcsc"], {"1": "A", "2": "K"})
        wire(g, prev, f"D{100 + i}.1", v=top)
        prev = "LED_K" if i == leds - 1 else f"LED_A{i + 1}"
        wire(g, prev, f"D{100 + i}.2", v=top)
    wire(g, "LED_K", "L100.1", v=top)
    wire(g, "LED_SW", "L100.2", f"U100.{role['sw']}", "D110.2", v=(0, vin + 1))
    if dim:
        p.free_pins(g, "U1.10")
        wire(g, "LED_DIM", "U1.10", f"U100.{role['dim']}", v=(0, 3.4))
    p.save_graph(g)
    sim = p.sim()
    sim["sources"]["J100"] = {"plus": "1", "minus": "2", "r_ohm": 0.05}
    sim["supplies"] = {"in": {"J1": 5.0, "J100": vin}}
    sim["loads"] = {"run": {"gpio": {"LED_OE": 1}, "leds_on": []}}
    if dim:
        sim["mcu"]["U1"]["outputs"].append("LED_DIM")
        sim["loads"] = {"lit": {"gpio": {"LED_OE": 1, "LED_DIM": 1}, "leds_on": []},
                        "dark": {"gpio": {"LED_OE": 1, "LED_DIM": 0}, "leds_on": []}}
    sim["report"] = ["LED_VIN", "LED_CS", "LED_SW"]
    return sim


def on_driver(out, grade="cc"):
    """(code, grade) of the findings on U100 and its LEDs with the grade."""
    return sorted({(f["code"], f["grade"]) for f in out["findings"] if f.get("grade") == grade})


def rows(out, item, start):
    return [c for c in out["checks"] if c["item"] == item and c["check"].startswith(start)]


def test_a_pt4115_with_its_sense_resistor_drives_the_string_at_0_1_v_over_rs(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    out = simulate(p, driver(p))                         # 0.1 V / 0.13 Ω: 731 … 777 mA (95 … 101 mV)
    assert all(s["status"] != "error" for s in out["scenarios"])
    assert on_driver(out) == []
    current = rows(out, "U100", "LED current set by R_S")
    assert current and all(c["result"] == "pass" for c in current)
    for led in ("D100", "D101", "D102"):
        lit = rows(out, led, "LED current")
        assert lit and all(c["result"] == "pass" for c in lit), lit
    sc = next(s for s in out["scenarios"] if s["name"].startswith("in/run/"))
    i_cs = (sc["nets"]["LED_VIN"] - sc["nets"]["LED_CS"]) / 0.13
    assert i_cs == pytest.approx(0.101 / 0.13, rel=0.02)            # the model runs at the top of the tolerance
    supply = sc["sources"]["J100"]
    assert 0.4 < supply < 0.6, supply                    # a buck: about P_LED / VIN, not the LED current itself


def test_a_sense_resistor_below_the_minimum_drives_more_than_the_pt4115_allows(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    out = simulate(p, driver(p, rs=0.068))               # 101 mV / 0.068 Ω = 1.49 A > 1.2 A, 0.068 Ω < 0.082 Ω
    found = {(f["code"], f["place"]) for f in out["findings"] if f.get("grade") == "cc"}
    assert ("LIM.i", "U100") in found and ("REQ.value", "U100") in found


def test_an_input_below_the_string_and_its_drops_is_out_of_regulation(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    out = simulate(p, driver(p, vin=10.0))               # three LEDs need about 10.5 V plus I × (RS + rL + RSW)
    assert ("LIM.range", "cc") in on_driver(out)
    head = [f for f in out["findings"] if f["code"] == "LIM.range" and f.get("grade") == "cc"]
    assert all(f["place"] == "U100" for f in head)


def test_dim_low_turns_the_string_off_and_high_on(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    out = simulate(p, driver(p, dim=True))               # GP7 at 3.3 V ≥ 2.5 V full current, at 0 V ≤ 0.3 V off
    assert on_driver(out) == []
    dark = [c for c in out["checks"] if c["item"] == "D100" and "/dark/" in c["scenario"] and c["check"] == "LED dark"]
    lit = [c for c in out["checks"] if c["item"] == "D100" and "/lit/" in c["scenario"]
           and c["check"].startswith("LED current")]
    assert dark and lit and all(c["result"] == "pass" for c in dark + lit)


def test_the_inductor_saturates_below_the_peak_current(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    weak = {**COIL, "limits": {"i_max_a": 1.6, "i_sat_a": 0.8}}    # peak 777 mA × (1 + 0.3 / 2) = 894 mA
    out = simulate(p, driver(p, coil=weak))
    found = {(f["code"], f["place"]) for f in out["findings"] if f.get("grade") == "cc"}
    assert found == {("LIM.i", "L100")}


def test_the_al8860_in_its_tsot25_drives_up_to_1_a(tmp_path):
    p = Project.copy_of_example(tmp_path / "a")
    out = simulate(p, driver(p, key="C125330", rs=0.15))      # 104 mV / 0.15 Ω = 693 mA
    assert on_driver(out) == []
    p = Project.copy_of_example(tmp_path / "b")
    out = simulate(p, driver(p, key="C125330", rs=0.1))       # 104 mV / 0.1 Ω = 1.04 A > 1 A
    assert {(f["code"], f["place"]) for f in out["findings"] if f.get("grade") == "cc"} == {("LIM.i", "U100")}
