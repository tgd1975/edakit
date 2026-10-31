"""Reference circuits per domain (concept rules-at-scale.md, section 7; maker-coverage FT-21): the example led-bar with
one circuit of a domain added – a motor switch, a class-D amplifier, an instrument buffer, a battery next to USB, a
button on a cable, a USB-C receptacle with data, a key matrix. Each passes clean under its domains; each fault of
FAULTS builds one mistake into it and expects exactly its codes (the overlap test).

These are edakit's own circuits, shaped after common maker designs, not copies of published ones: the parts are the
block library's checked entries and test entries whose values are chosen for the test, not taken from datasheets. The
well-known open designs of FT-21 (an ESP32 DevKitC, a Tube Screamer, a QMK keyboard …) replace or join them once their
schematics can be read.

    python tests/reference.py DIR                  write every reference circuit as a project under DIR/<name>
    python tests/reference.py DIR NAME [FAULT]     write one into DIR – led-bar the example as it is –, with FAULT
                                                   (its words in FAULTS) built in: the evals' scaffold (evals/)
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "tests" / "fixtures" / "led-bar"
LIBRARY = ROOT / "edakit" / "parts"


class Project:
    """A writable project directory with the helpers the tests use (as conftest's fixture)."""

    def __init__(self, root):
        self.root = Path(root)
        self.graph_file = self.root / "hardware" / "graph.json"

    @classmethod
    def copy_of_example(cls, dst):
        shutil.copytree(EXAMPLE, dst, ignore=shutil.ignore_patterns("build"), dirs_exist_ok=True)
        return cls(dst)

    def config(self):
        from edakit import config
        return config.load(self.root / "edakit.toml")

    def graph(self):
        return json.loads(self.graph_file.read_text())

    def save_graph(self, g):
        self.graph_file.write_text(json.dumps(g, indent=1, ensure_ascii=False) + "\n")

    def part(self, key):
        return json.loads((self.root / "hardware" / "parts" / f"{key}.json").read_text())

    def save_part(self, key, data):
        (self.root / "hardware" / "parts" / f"{key}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False)
                                                                        + "\n")

    def use_library_part(self, key):
        shutil.copy(LIBRARY / f"{key}.json", self.root / "hardware" / "parts" / f"{key}.json")

    def sim(self):
        return json.loads((self.root / "hardware" / "sim.json").read_text())

    def save_sim(self, s):
        (self.root / "hardware" / "sim.json").write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n")

    @staticmethod
    def net(g, name):
        return next(n for n in g["graph"]["nets"] if n["name"] == name)

    @staticmethod
    def comp(g, des):
        return next(c for c in g["graph"]["components"] if c["designator"] == des)

    def free_pins(self, g, *refs):
        for ref in refs:
            des, num = ref.split(".")
            self.comp(g, des)["nc"].remove(num)


BUTTON_PINS = {n: i["name"] for n, i in json.loads((LIBRARY / "C318884.json").read_text())["pins"].items()}


def add(g, des, kind_type, key, pins, **extra):
    g["graph"]["components"].append({"designator": des, "type": kind_type, "lcsc": key, "pins": pins, **extra})


def wire(g, name, *pins, v=(0, 5.5), **extra):
    """Pins onto a net – the net is made if it does not exist."""
    for n in g["graph"]["nets"]:
        if n["name"] == name:
            n["pins"] += list(pins)
            n.update(extra)
            return
    g["graph"]["nets"].append({"name": name, "pins": list(pins), "v": list(v), **extra})


def resistor(p, key, ohm):
    """A resistor entry `key` of `ohm`, from the library's 10 kΩ (C17414) – for values the library lacks."""
    r = json.loads((LIBRARY / "C17414.json").read_text())
    r.update(lcsc=key, mpn=f"0805 {ohm:g} Ω (reference circuit)")
    r["values"]["value_ohm"] = ohm
    p.save_part(key, r)


def block(p, title, start, notes, board_title, near=None):
    """The circuit's own block in the drawing (hardware/schematic.toml, a third row) and the board's title; near: the
    capacitors drawn at a part."""
    f = p.root / "hardware" / "schematic.toml"
    t = f.read_text()
    if near:
        t = t.replace('near = { C1 = "U2", C2 = "U1" }',
                      'near = { C1 = "U2", C2 = "U1", ' + ", ".join(f'{c} = "{x}"' for c, x in near.items()) + " }")
    starts = ", ".join(json.dumps(s) for s in start)
    last = '  [ [ { title = "LED Driver", start = ["U2"] } ], [ { title = "Notes" } ] ],\n]'
    row = '  [ [ { title = %s, start = [%s] } ] ],\n' % (json.dumps(title), starts)
    t = t.replace(last, last[:-1] + row + "]")
    keep = 'Notes = ["Nets with the same name are connected (labels and power flags)."]'
    said = "%s = [%s]\n" % (json.dumps(title), ", ".join(json.dumps(n, ensure_ascii=False) for n in notes))
    t = t.replace(keep, said + keep)
    f.write_text(t)
    toml = p.root / "edakit.toml"
    toml.write_text(toml.read_text().replace('title = "LED bar"', 'title = %s' % json.dumps(board_title), 1))


def drive(p, net, *, idle=0, all_on=1):
    """U1 drives `net` as an output: low in idle, high with all on (sim.json)."""
    s = p.sim()
    s["mcu"]["U1"]["outputs"].append(net)
    s["loads"]["idle"]["gpio"][net] = idle
    s["loads"]["all_on"]["gpio"][net] = all_on
    p.save_sim(s)


# --- the circuits --------------------------------------------------------------------------------------------------------
MOTOR = {"lcsc": "C9100001", "mpn": "130-size DC motor (reference circuit)", "kind": "motor",
         "verified": {"by": "reference circuit"}, "limits": {"v_max_v": 6, "i_max_a": 0.3}, "values": {"coil_ohm": 33},
         "pins": {"1": {"name": "+", "type": "passive", "role": "plus"},
                  "2": {"name": "-", "type": "passive", "role": "minus"}},
         "sources": ["values for the reference circuit, not from a datasheet"]}


def motors(p):
    """M1 (33 Ω winding) from +5V to the collector of an S8050 Q20, 1 kΩ from GP8 to the base, 10 kΩ base to emitter;
    an SS14 across the winding."""
    for key in ("C2146", "C17513", "C17414", "C2480"):
        p.use_library_part(key)
    p.save_part(MOTOR["lcsc"], MOTOR)
    g = p.graph()
    p.free_pins(g, "U1.11")
    add(g, "M1", "motor", MOTOR["lcsc"], {"1": "+", "2": "-"})
    add(g, "Q20", "transistor", "C2146", {"1": "B", "2": "E", "3": "C"})
    add(g, "R20", "resistor", "C17513", {"1": "1", "2": "2"}, value="1k")
    add(g, "R21", "resistor", "C17414", {"1": "1", "2": "2"}, value="10k")
    add(g, "D20", "diode", "C2480", {"1": "K", "2": "A"})
    wire(g, "+5V", "M1.1", "D20.1")
    wire(g, "GND", "Q20.2", "R21.2")
    wire(g, "MOTOR_SW", "M1.2", "Q20.3", "D20.2")
    wire(g, "MOTOR_B", "Q20.1", "R20.2", "R21.1", v=(0, 3.4))
    wire(g, "MOTOR_EN", "R20.1", "U1.11", v=(0, 3.4))
    p.save_graph(g)
    drive(p, "MOTOR_EN")
    block(p, "Motor", ["Q20"], ["M1 (33 Ω) switched low-side by Q20 from GP8", "D20 SS14: flyback diode across the winding"],
          "Reference: motors")


AMP = {"lcsc": "C9100002", "mpn": "mono class-D amplifier (reference circuit)", "kind": "ic",
       "verified": {"by": "reference circuit"}, "values": {"behavior": "logic", "icc_a": 0.004},
       "limits": {"vdd_op_min_v": 2.5, "vdd_op_max_v": 5.5},
       "pins": {"1": {"name": "OUT+", "type": "output", "role": "out_p"},
                "2": {"name": "OUT-", "type": "output", "role": "out_n"},
                "3": {"name": "IN", "type": "analog"}, "4": {"name": "GND", "type": "ground"},
                "5": {"name": "VDD", "type": "power_in", "role": "vdd"}},
       "sources": ["values for the reference circuit, not from a datasheet"]}
SPEAKER = {"lcsc": "C9100003", "mpn": "8 Ω speaker (reference circuit)", "kind": "speaker",
           "verified": {"by": "reference circuit"}, "values": {"impedance_ohm": 8}, "limits": {"p_max_w": 1},
           "pins": {"1": {"name": "+", "type": "passive", "role": "plus"},
                    "2": {"name": "-", "type": "passive", "role": "minus"}},
           "sources": ["values for the reference circuit, not from a datasheet"]}


def audio(p):
    """U20, a class-D amplifier on +5V with 100 nF, its bridge-tied outputs to the speaker LS20; its input from GP8
    through 1 kΩ (a PWM DAC's filter resistor)."""
    for key in ("C17513",):
        p.use_library_part(key)
    p.save_part(AMP["lcsc"], AMP)
    p.save_part(SPEAKER["lcsc"], SPEAKER)
    g = p.graph()
    p.free_pins(g, "U1.11")
    add(g, "U20", "ic", AMP["lcsc"], {n: i["name"] for n, i in AMP["pins"].items()})
    add(g, "LS20", "audio", SPEAKER["lcsc"], {"1": "+", "2": "-"})
    add(g, "C20", "capacitor", "C49678", {"1": "1", "2": "2"}, value="100nF")
    add(g, "R20", "resistor", "C17513", {"1": "1", "2": "2"}, value="1k")
    wire(g, "+5V", "U20.5", "C20.1")
    wire(g, "GND", "U20.4", "C20.2")
    wire(g, "SPK_P", "U20.1", "LS20.1")
    wire(g, "SPK_N", "U20.2", "LS20.2")
    wire(g, "AUDIO_IN", "U20.3", "R20.2", v=(0, 3.4))
    wire(g, "AUDIO_PWM", "R20.1", "U1.11", v=(0, 3.4), fn="pwm", pwm_hz=40000)
    p.save_graph(g)
    drive(p, "AUDIO_PWM")
    block(p, "Amplifier", ["U20"], ["U20 class-D amplifier, bridge-tied to the speaker LS20", "R20: input from GP8 (PWM)"],
          "Reference: audio", near={"C20": "U20"})


OPAMP = {"lcsc": "C9100004", "mpn": "single op-amp, rail to rail out (reference circuit)", "kind": "ic",
         "verified": {"by": "reference circuit"},
         "values": {"behavior": "opamp", "vout_swing_v": [0.05, -0.05], "vicm_v": [0, -1.2], "iq_a": 0.001,
                    "gain_min_ratio": 1},
         "limits": {"vdd_op_min_v": 2.7, "vdd_op_max_v": 5.5},
         "pins": {"1": {"name": "OUT", "type": "output", "role": "out"},
                  "2": {"name": "-IN", "type": "input", "role": "in_n", "z_in_ohm": 1e12},
                  "3": {"name": "+IN", "type": "input", "role": "in_p", "z_in_ohm": 1e12},
                  "4": {"name": "GND", "type": "ground", "role": "gnd"},
                  "5": {"name": "VCC", "type": "power_in", "role": "vcc"}},
         "sources": ["values for the reference circuit, not from a datasheet"]}


def guitar(p):
    """An instrument buffer: the jack J20's tip on GTR_IN (a pickup that wants at least 1 MΩ), 2.2 MΩ to the
    reference VREF (10 kΩ / 10 kΩ from +5V, 22 µF), U20 an op-amp follower on +5V with 100 nF."""
    p.use_library_part("C17414")
    resistor(p, "C9100005", 2.2e6)
    p.save_part(OPAMP["lcsc"], OPAMP)
    g = p.graph()
    add(g, "U20", "ic", OPAMP["lcsc"], {n: i["name"] for n, i in OPAMP["pins"].items()})
    add(g, "J20", "connector", "C131337", {"1": "1", "2": "2"}, bom=False)
    add(g, "R20", "resistor", "C9100005", {"1": "1", "2": "2"}, value="2.2M")
    add(g, "R21", "resistor", "C17414", {"1": "1", "2": "2"}, value="10k")
    add(g, "R22", "resistor", "C17414", {"1": "1", "2": "2"}, value="10k")
    add(g, "C20", "capacitor", "C45783", {"1": "1", "2": "2"}, value="22uF")
    add(g, "C21", "capacitor", "C49678", {"1": "1", "2": "2"}, value="100nF")
    wire(g, "+5V", "U20.5", "R21.1", "C21.1")
    wire(g, "GND", "U20.4", "R22.2", "C20.2", "C21.2", "J20.2")
    wire(g, "VREF", "R21.2", "R22.1", "C20.1", "R20.2")
    wire(g, "GTR_IN", "J20.1", "R20.1", "U20.3", instrument="pickup", load_min_ohm=1e6)
    wire(g, "GTR_OUT", "U20.1", "U20.2")
    p.save_graph(g)
    block(p, "Instrument Buffer", ["U20"], ["J20: the instrument (pickup) in, R20 2.2 MΩ bias to VREF",
                                             "R21/R22 + C20: VREF at half the supply; U20 a follower"],
          "Reference: guitar", near={"C21": "U20"})


HOLDER = {"lcsc": "C9100006", "mpn": "3 × AA holder (reference circuit)", "kind": "battery_holder",
          "verified": {"by": "reference circuit"}, "values": {"cells": 1}, "limits": {"i_max_a": 2},
          "pins": {"1": {"name": "+", "type": "power_output", "role": "plus"},
                   "2": {"name": "-", "type": "ground", "role": "minus"}},
          "sources": ["values for the reference circuit, not from a datasheet"]}


def power(p):
    """Three AA cells in BT20 next to USB: through an SS14 D20 onto VIN behind J1, so that neither feeds the other."""
    p.use_library_part("C2480")
    p.save_part(HOLDER["lcsc"], HOLDER)
    g = p.graph()
    add(g, "BT20", "battery_holder", HOLDER["lcsc"], {"1": "+", "2": "-"}, bom=False, source="reversible")
    add(g, "D20", "diode", "C2480", {"1": "K", "2": "A"})
    wire(g, "BAT", "BT20.1", "D20.2")
    wire(g, "+5V", "D20.1")
    wire(g, "GND", "BT20.2")
    p.save_graph(g)
    s = p.sim()
    s["cells"] = {"fresh": {"v": 4.8, "r": 0.45, "i_max_a": 0.5}}
    s["supplies"]["cells"] = {"BT20": "fresh"}
    p.save_sim(s)
    block(p, "Battery", ["BT20"], ["BT20: three AA cells, D20 SS14 onto +5V", "neither USB nor the cells feed the other"],
          "Reference: power")


def cables(p):
    """A button SW20 on a bought remote board, wired by cable W20 (1 m of AWG 26) from J21 to J20 on main; on main
    the line reaches GP8 through 1 kΩ, with 10 kΩ to 3V3."""
    for key in ("C17513", "C17414"):
        p.use_library_part(key)
    toml = p.root / "edakit.toml"
    toml.write_text(toml.read_text() + '\n[boards.remote]\ntitle = "Remote button"\nbought = true\n')
    g = p.graph()
    for c in g["graph"]["components"]:
        c.setdefault("board", "main")
    p.free_pins(g, "U1.11")
    add(g, "J20", "connector", "C131337", {"1": "1", "2": "2"}, bom=False, board="main")
    add(g, "J21", "connector", "C131337", {"1": "1", "2": "2"}, bom=False, board="remote")
    add(g, "SW20", "button", "C318884", BUTTON_PINS, bom=False, board="remote", nc=["2", "4"])
    add(g, "R20", "resistor", "C17513", {"1": "1", "2": "2"}, value="1k", board="main")
    add(g, "R21", "resistor", "C17414", {"1": "1", "2": "2"}, value="10k", board="main")
    wire(g, "REMOTE", "SW20.1", "J21.1", "J20.1", "R20.1", "R21.1", v=(0, 3.4))
    wire(g, "REMOTE_IN", "R20.2", "U1.11", v=(0, 3.4))
    wire(g, "3V3", "R21.2")
    wire(g, "GND", "SW20.3", "J21.2", "J20.2")
    g["graph"]["cables"].append({"name": "W20", "from": "J21", "to": "J20", "pins": {"1": "1", "2": "2"},
                                 "length_m": 1, "awg": 26})
    p.save_graph(g)
    block(p, "Remote Button", ["J20"], ["W20: 1 m of AWG 26 to the remote board (J21, SW20)",
                                        "R20 1 kΩ in series at GP8, R21 10 kΩ pull-up"], "Reference: cables")


RECEPTACLE = {"lcsc": "C9100007", "mpn": "USB-C receptacle, USB 2.0 (reference circuit)", "kind": "connector",
              "verified": {"by": "reference circuit"}, "limits": {"i_max_a": 3},
              "pins": {"A5": {"name": "CC1", "type": "passive", "role": "cc1"},
                       "B5": {"name": "CC2", "type": "passive", "role": "cc2"},
                       "A6": {"name": "D+", "type": "passive", "role": "dp_a"},
                       "B6": {"name": "D+", "type": "passive", "role": "dp_b"},
                       "A7": {"name": "D-", "type": "passive", "role": "dn_a"},
                       "B7": {"name": "D-", "type": "passive", "role": "dn_b"},
                       "A1": {"name": "GND", "type": "passive", "role": "gnd"}},
              "sources": ["values for the reference circuit, not from a datasheet"]}


def usb(p):
    """J20, a USB-C receptacle for data: 5.1 kΩ from each CC pin to GND, D+ and D− of both rows joined to GP8 and
    GP9 through 27 Ω."""
    p.use_library_part("C27834")
    resistor(p, "C9100008", 27)
    p.save_part(RECEPTACLE["lcsc"], RECEPTACLE)
    g = p.graph()
    p.free_pins(g, "U1.11", "U1.12")
    add(g, "J20", "connector", RECEPTACLE["lcsc"], {n: i["name"] for n, i in RECEPTACLE["pins"].items()}, bom=False)
    for i, (des, key, val) in enumerate((("R20", "C27834", "5.1k"), ("R21", "C27834", "5.1k"),
                                         ("R22", "C9100008", "27"), ("R23", "C9100008", "27"))):
        add(g, des, "resistor", key, {"1": "1", "2": "2"}, value=val)
    wire(g, "CC1", "J20.A5", "R20.1")
    wire(g, "CC2", "J20.B5", "R21.1")
    wire(g, "GND", "R20.2", "R21.2", "J20.A1")
    wire(g, "USB_DP_C", "J20.A6", "J20.B6", "R22.1", v=(0, 3.6))
    wire(g, "USB_DN_C", "J20.A7", "J20.B7", "R23.1", v=(0, 3.6))
    wire(g, "USB_DP", "R22.2", "U1.11", v=(0, 3.6))
    wire(g, "USB_DN", "R23.2", "U1.12", v=(0, 3.6))
    p.save_graph(g)
    block(p, "USB-C", ["J20"], ["R20/R21 5.1 kΩ: Rd on CC1 and CC2", "D+ and D− of both rows joined, 27 Ω to GP8/GP9"],
          "Reference: usb")


def keyboard(p):
    """A 2 × 2 key matrix: SW20–SW23 from the rows (GP8, GP9) to an SS14 each, cathodes to the rows, anodes … the
    columns (GP10, GP11)."""
    p.use_library_part("C2480")
    g = p.graph()
    p.free_pins(g, "U1.11", "U1.12", "U1.14", "U1.15")
    wire(g, "ROW0", "U1.11", v=(0, 3.4), matrix="row")
    wire(g, "ROW1", "U1.12", v=(0, 3.4), matrix="row")
    wire(g, "COL0", "U1.14", v=(0, 3.4), matrix="col")
    wire(g, "COL1", "U1.15", v=(0, 3.4), matrix="col")
    for i, (row, col) in enumerate((("ROW0", "COL0"), ("ROW0", "COL1"), ("ROW1", "COL0"), ("ROW1", "COL1"))):
        sw, dio = f"SW{20 + i}", f"D{20 + i}"
        add(g, sw, "button", "C318884", BUTTON_PINS, nc=["2", "4"])
        add(g, dio, "diode", "C2480", {"1": "K", "2": "A"})
        wire(g, col, f"{sw}.1")
        wire(g, f"K_{sw}", f"{sw}.3", f"{dio}.2", v=(0, 3.4))
        wire(g, row, f"{dio}.1")
    p.save_graph(g)
    s = p.sim()                          # a scan: the rows driven low, the columns pulled up
    s["mcu"]["U1"]["outputs"] += ["ROW0", "ROW1"]
    s["mcu"]["U1"]["pullups"] += ["COL0", "COL1"]
    for load in s["loads"].values():
        load.setdefault("gpio", {}).update(ROW0=0, ROW1=0)
    p.save_sim(s)
    block(p, "Key Matrix", ["SW20"], ["SW20–SW23: rows GP8/GP9, columns GP10/GP11",
                                     "a diode per key, cathodes to the rows (col2row)"], "Reference: keyboard")


REFERENCES = {"motors": motors, "audio": audio, "guitar": guitar, "power": power, "cables": cables, "usb": usb,
              "keyboard": keyboard}


# --- seeded faults: (what, the change, the codes it must raise – exactly) ----------------------------------------------
def _move(p, des_pin, net_from, net_to):
    g = p.graph()
    p.net(g, net_from)["pins"].remove(des_pin)
    wire(g, net_to, des_pin)
    g["graph"]["nets"] = [n for n in g["graph"]["nets"] if n["pins"]]
    p.save_graph(g)


def _merge(p, net_from, net_to):
    """Every pin of net_from onto net_to."""
    g = p.graph()
    pins = p.net(g, net_from)["pins"]
    g["graph"]["nets"] = [n for n in g["graph"]["nets"] if n["name"] != net_from]
    wire(g, net_to, *pins)
    p.save_graph(g)


def _resistor_to(p, des, key, ohm, text):
    """`des` becomes a resistor of `ohm` – a new entry `key`, the graph's value with it."""
    resistor(p, key, ohm)
    g = p.graph()
    p.comp(g, des).update(lcsc=key, value=text)
    p.save_graph(g)


def _unconnect(p, des, num):
    """Pin `num` of `des` off its net into nc; a net left with one pin goes with it."""
    g = p.graph()
    for n in g["graph"]["nets"]:
        n["pins"] = [r for r in n["pins"] if r != f"{des}.{num}"]
    g["graph"]["nets"] = [n for n in g["graph"]["nets"] if n["pins"]]
    p.comp(g, des).setdefault("nc", []).append(num)
    p.save_graph(g)


def _remove(p, des):
    g = p.graph()
    for n in g["graph"]["nets"]:
        n["pins"] = [r for r in n["pins"] if r.split(".")[0] != des]
    g["graph"]["components"] = [c for c in g["graph"]["components"] if c["designator"] != des]
    g["graph"]["nets"] = [n for n in g["graph"]["nets"] if n["pins"]]
    p.save_graph(g)


def _value(p, key, **values):
    e = p.part(key)
    e["values"].update(values)
    p.save_part(key, e)


def _limit(p, key, **lims):
    e = p.part(key)
    e["limits"].update(lims)
    p.save_part(key, e)


def _cell(p, **kw):
    s = p.sim()
    s["cells"]["fresh"].update(kw)
    p.save_sim(s)


def _flip(p, des):
    g = p.graph()
    c = p.comp(g, des)
    a, b = list(c["pins"])
    for n in g["graph"]["nets"]:
        n["pins"] = [f"{des}.{b}" if r == f"{des}.{a}" else f"{des}.{a}" if r == f"{des}.{b}" else r for r in n["pins"]]
    p.save_graph(g)


FAULTS = {
    "motors": [("no flyback diode", lambda p: _remove(p, "D20"), {"REQ.missing"}),
               ("a winding of 10 Ω", lambda p: _value(p, "C9100001", coil_ohm=10), {"LIM.i", "LIM.p"})],
    "audio": [("an output on ground", lambda p: _merge(p, "SPK_N", "GND"), {"REQ.forbidden"})],
    "guitar": [("a bias of 470 kΩ", lambda p: _resistor_to(p, "R20", "C9100010", 470e3, "470k"), {"REQ.value"}),
               ("a reference above the inputs' range", lambda p: _resistor_to(p, "R22", "C9100011", 100e3, "100k"),
                {"LIM.range"})],
    "power": [("the cells' current limit", lambda p: _cell(p, i_max_a=0.02), {"LIM.i"}),
              ("no diode in front of the cells", lambda p: (_remove(p, "D20"), _merge(p, "BAT", "+5V")),
               {"PATH.reverse"})],
    "cables": [("no series resistor at the pin", lambda p: (_remove(p, "R20"), _merge(p, "REMOTE_IN", "REMOTE")),
                {"REQ.missing"})],
    "usb": [("D+ of one row only", lambda p: _unconnect(p, "J20", "B6"), {"REQ.missing"}),
            ("no Rd on CC2", lambda p: (_remove(p, "R21"), _unconnect(p, "J20", "B5")), {"REQ.missing"})],
    "keyboard": [("a key without its diode", lambda p: (_remove(p, "D21"), _merge(p, "K_SW21", "ROW0")),
                  {"REQ.missing"}),
                 ("a diode the wrong way round", lambda p: _flip(p, "D22"), {"REQ.forbidden"})],
}


def write_all(dst):
    """Every reference circuit as a project under dst/<name> (for the evals)."""
    dst = Path(dst)
    for name, build in REFERENCES.items():
        target = dst / name
        if target.exists():
            shutil.rmtree(target)
        p = Project.copy_of_example(target)
        build(p)
        toml = target / "edakit.toml"
        toml.write_text(toml.read_text().replace('name = "led-bar"', f'name = "reference-{name}"', 1))
    return sorted(REFERENCES)


def write_one(dst, name, fault=None):
    """One reference circuit – or the example, name led-bar – as a project in dst, with a fault of FAULTS built in."""
    p = Project.copy_of_example(dst)
    if name != "led-bar":
        REFERENCES[name](p)
    if fault:
        next(change for what, change, _ in FAULTS[name] if what == fault)(p)
    return p


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    if len(sys.argv) > 2:
        write_one(Path(sys.argv[1]), sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        print("\n".join(write_all(sys.argv[1])))
