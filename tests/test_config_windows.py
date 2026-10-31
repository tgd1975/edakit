"""REQ.value/window (maker-coverage CK-20): a configuration pin that reads its setting by voltage window sits inside
one window in the operating point. The windows are those of the MAX98357A's SD_MODE (datasheet 19-6779 Rev 11, SD
COMPARATOR TRIP POINTS B0–B2 and Table 5, read from LCSC's copy for C910544): the guaranteed windows lie between one
trip point's maximum and the next one's minimum; the pin's own 100 kΩ pull-down (RPD) is in the netlist."""

import shutil

import pytest
from test_sim import simulate

from edakit import schema

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")

# B0 0.08 / 0.16 / 0.355 V, B1 0.65 / 0.77 / 0.825 V, B2 1.245 / 1.4 / 1.5 V (min / typ / max)
SD_MODE = [{"state": "shutdown", "max_v": 0.08}, {"state": "left/2 + right/2", "min_v": 0.355, "max_v": 0.65},
           {"state": "right", "min_v": 0.825, "max_v": 1.245}, {"state": "left", "min_v": 1.5}]


def amplifier(project, r_pullup):
    """U9, an amplifier whose SD_MODE (pin 4) has the datasheet's windows and its own 100 kΩ pull-down, pulled up
    from 3V3 through R9."""
    project.save_part("C9100090", {"lcsc": "C9100090", "mpn": "SD_MODE windows of MAX98357A (test part)", "kind": "ic",
                                   "verified": {"by": "test"},
                                   "pins": {"1": {"name": "VDD", "type": "power_in"},
                                            "2": {"name": "GND", "type": "ground"},
                                            "4": {"name": "SD_MODE", "type": "input", "pull": "down",
                                                  "pull_ohm": 100e3, "windows": SD_MODE}}})
    r = project.part("C17414")
    r.update(lcsc="C9100091", mpn=f"{r_pullup:g} Ω (test)")
    r["values"]["value_ohm"] = r_pullup
    project.save_part("C9100091", r)
    g = project.graph()
    g["graph"]["components"] += [
        {"designator": "U9", "type": "ic", "lcsc": "C9100090", "pins": {"1": "VDD", "2": "GND", "4": "SD_MODE"}},
        {"designator": "R9", "type": "resistor", "lcsc": "C9100091", "pins": {"1": "1", "2": "2"}},
        {"designator": "C9", "type": "capacitor", "lcsc": "C49678", "value": "100nF", "pins": {"1": "1", "2": "2"}}]
    project.net(g, "3V3")["pins"] += ["U9.1", "R9.1", "C9.1"]
    project.net(g, "GND")["pins"] += ["U9.2", "C9.2"]
    g["graph"]["nets"].append({"name": "SD_MODE", "pins": ["U9.4", "R9.2"], "v": [0, 3.4]})
    project.save_graph(g)


def window_rows(out):
    return [c for c in out["checks"] if c["item"] == "U9.4"]


def test_634k_from_3v3_selects_the_mix(project):
    amplifier(project, 634e3)                  # Table 6: RLARGE 634 kΩ at 3.3 V → (L+R)/2
    rows = window_rows(simulate(project))
    assert rows and {r["result"] for r in rows} == {"pass"}
    assert all(r["check"].endswith("left/2 + right/2") for r in rows)


def test_a_pull_up_between_two_windows(project):
    amplifier(project, 390e3)                  # 3.3 V × 100 k / 490 k ≈ 0.67 V: above mix, below right
    out = simulate(project)
    assert {r["result"] for r in window_rows(out)} == {"warn"}           # REQ.value/window is a warning
    found = [f for f in out["findings"] if f["place"] == "U9.4"]
    assert found and {(f["code"], f["grade"]) for f in found} == {("REQ.value", "window")}


def test_the_field_is_a_list_of_windows():
    entry = {"kind": "ic", "pins": {"1": {"name": "SD", "type": "input", "windows": SD_MODE}}}
    assert not [t for t in schema.problems(entry) if "windows" in t]
    entry["pins"]["1"]["windows"] = [{"state": "off"}]
    assert [t for t in schema.problems(entry) if "windows" in t]
