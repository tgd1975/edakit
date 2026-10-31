"""The round trip of translate.py: graph JSON → language → JSON and graph JSON → TOML → JSON without a difference
(canonical JSON: the order of keys aside, every list in its order) on the Christmas bell's four configurations; and
the bell written by hand in both forms (bell.circuit, bell.toml) equals its graph.

    BELL_ROOT=<checkout of the Christmas bell> python3 test_translate.py
    BELL_ROOT=<checkout of the Christmas bell> python3 -m pytest test_translate.py

Without BELL_ROOT the bell's cases are skipped. Two cases need only edakit: its example led-bar, and led-bar with
every field of the graph format the bell does not use. edakit's pytest does not collect this folder.
"""

import copy
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import translate as t  # noqa: E402

BELL = Path(os.environ["BELL_ROOT"]) if os.environ.get("BELL_ROOT") else None
LED_BAR = HERE.parents[4] / "tests" / "fixtures" / "led-bar" / "hardware"
CONFIGS = {"main": ".", "smd": "variants/smd", "tht": "variants/tht", "esp32": "variants/esp32"}
FORMS = {"circuit": (t.to_circuit, t.from_circuit), "toml": (t.to_toml, t.from_toml)}


def load(hardware):
    return json.loads((hardware / "graph.json").read_text(encoding="utf-8")), t.load_parts(hardware / "parts")


def round_trip(graph, parts):
    """{form: (equal, lines of the form)}"""
    out = {}
    for form, (write, read) in FORMS.items():
        text = write(graph, parts)
        out[form] = (t.canonical(read(text, parts)) == t.canonical(graph), len(text.splitlines()))
    return out


def every_field():
    """led-bar with what the bell does not use: cables, loops, ground(s), hints, explicit and empty pin maps, a part
    without parts entry, a lock off its net, values that are no strings, quotes, backslashes, line breaks."""
    graph, parts = load(LED_BAR)
    g = copy.deepcopy(graph)
    inner = g["graph"]
    inner.update(version=2, ground="GND", grounds=["AGND"], extra={"a": [1, 2.5e-06, True], "b.c": "-"},
                 hints={"H-1": 'C2 22 µF "next" to J1 \\ U1\nsecond line  two spaces', "H-3": "#no comment"},
                 cables=[{"name": "W1", "from": "J1", "to": "SW1", "pins": {"1": "1", "2": "3"},
                          "r_ohm_per_wire": 0.065, "i_max_a": 1, "colour": "red"}])
    inner["purpose"]["since"] = "2026"
    inner["conventions"]["count"] = 3
    inner["layout"].update(loops=[{"a": "C1.1", "b": "U2.16", "max_mm": 8, "what": "decoupling loop"}],
                           near={"R1": "U2", "C1": ["U2", "U1"]})
    inner["checks"]["doc_pin_table"] = {"component": "U1", "file": "README.md", "prefix": "GP", "regex": r"\| (\w+) \|"}
    inner["checks"]["pin_locks"]["U2.14"] = "LED_SDI"
    comps = {c["designator"]: c for c in inner["components"]}
    comps["U2"].update(verify="OE polarity: pin 13 – datasheet p. 3?", board="main")
    comps["D2"].update(supplier="lcsc", spare=1, waive={})
    comps["R1"].update(bom=True, easyeda_device={"name": "R", "uuid": "u-1", "libraryUuid": "l-1"})
    comps["SW1"]["pins"] = {"1": "A", "2": "B", "3": "C", "4": "D"}
    comps["J1"].update(type="-", label="5 V input – " * 12)
    comps["C2"]["value"] = 22
    del comps["C1"]["part"]
    inner["components"].append({"designator": "TP1", "type": "testpoint", "pins": {"1": "TP"}, "nc": [],
                                "easyeda_device": {"name": "TP", "uuid": "u-2", "libraryUuid": "l-2"}})
    nets = {n["name"]: n for n in inner["nets"]}
    del nets["REXT"]["v"]
    nets["LED0"]["v"] = [0, 0.0]
    nets["LED1"]["v"] = "5 V"
    nets["BTN"].update(bus="i2c", pwm_hz=1000.5, pins=nets["BTN"]["pins"] + ["TP1.1"])
    nets["LED_OE"]["pwm_hz"] = [400, 4000]
    nets["LED2"].update(notes="Ω µ ∥ – \"quoted\" and a \\ backslash", waive={"G-4": "x", "E-1": "y"})
    inner["nets"].append({"name": "EMPTY", "pins": [], "v": [-1.5, 1e-06]})
    return g, parts


def cases():
    out = {}
    if BELL is not None:
        out.update({f"bell {name}": load(BELL / rel / "hardware") for name, rel in CONFIGS.items()})
    out["led-bar"] = load(LED_BAR)
    out["every field"] = every_field()
    return out


def written_by_hand():
    """{file: equal} – bell.circuit and bell.toml of this folder against the bell's main graph."""
    graph, parts = load(BELL / "hardware")
    return {f: t.canonical(t.to_json(HERE / f, parts)) == t.canonical(graph) for f in ("bell.circuit", "bell.toml")}


def test_round_trip():
    for name, (graph, parts) in cases().items():
        for form, (equal, _) in round_trip(graph, parts).items():
            assert equal, f"{name}: {form} differs"


def test_written_by_hand():
    if BELL is None:
        import pytest
        pytest.skip("BELL_ROOT not set: a checkout of the Christmas bell")
    for f, equal in written_by_hand().items():
        assert equal, f"{f} differs from the bell's hardware/graph.json"


def test_errors_with_line_numbers():
    graph, parts = load(LED_BAR)
    text = t.to_circuit(graph, parts).replace("U1.GP3 (locked)", "U1.GP33 (locked)")
    try:
        t.from_circuit(text, parts)
    except t.TranslateError as e:
        assert str(e).startswith(f"line {text[:text.index('U1.GP33')].count(chr(10)) + 1}: 'U1.GP33'"), e
    else:
        raise AssertionError("an unknown pin passed")


if __name__ == "__main__":
    if BELL is None:
        print("BELL_ROOT not set: the bell's cases skipped")
    ok = True
    for name, (graph, parts) in cases().items():
        res = round_trip(graph, parts)
        ok &= all(equal for equal, _ in res.values())
        json_lines = len(json.dumps(graph, indent=1, ensure_ascii=False).splitlines())
        print(f"{name:12} " + "  ".join(f"{form} {'equal' if equal else 'DIFFERENT'} ({lines} lines)"
                                        for form, (equal, lines) in res.items()) + f"  json {json_lines} lines")
    if BELL is not None:
        for f, equal in written_by_hand().items():
            ok &= equal
            print(f"{f:12} {'equal to' if equal else 'DIFFERENT from'} the bell's hardware/graph.json")
    test_errors_with_line_numbers()
    print("all equal" if ok else "DIFFERENCES")
    sys.exit(0 if ok else 1)
