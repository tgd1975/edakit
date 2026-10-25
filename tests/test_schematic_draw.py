"""The schematic drawn without EasyEDA: a symbol for every kind of part, the layout of `schematic layout`, a check."""

import argparse
import xml.etree.ElementTree as ET

import pytest

from edakit import eda, schematic_draw
from edakit.design import Design
from edakit.schematic_draw import symbol
from edakit.schematic_layout import Drawing

SVG = "{http://www.w3.org/2000/svg}"

# roles as in handbook 4.1, pin number -> role
SYMBOLS = {
    "resistor": {"1": "1", "2": "2"},
    "capacitor": {"1": "plus", "2": "minus"},
    "inductor": {"1": "1", "2": "2"},
    "fuse": {"1": "1", "2": "2"},
    "diode": {"1": "cathode", "2": "anode"},
    "led": {"1": "anode", "2": "cathode"},
    "buzzer": {"1": "plus", "2": "minus"},
    "battery_holder": {"1": "plus_a", "2": "minus_a", "3": "plus_b", "4": "minus_b"},
    "button": {"1": "a", "2": "a", "3": "b", "4": "b"},
    "switch": {"1": "common", "2": "throw_a", "3": "throw_b"},
    "potentiometer": {"1": "end_a", "2": "wiper", "3": "end_b"},
    "npn": {"1": "base", "2": "emitter", "3": "collector"},
    "pnp": {"1": "base", "2": "emitter", "3": "collector"},
    "nmos": {"1": "gate", "2": "source", "3": "drain"},
    "pmos": {"1": "gate", "2": "source", "3": "drain"},
    "relay": {"1": "coil_plus", "2": "coil_minus", "3": "common", "4": "no", "5": "nc"},
    "led_rgb": {"1": "anode_red", "2": "anode_green", "3": "anode_blue", "4": "cathode"},
    "dip_switch": {"1": "a1", "2": "a2", "3": "b2", "4": "b1"},
    "connector": {"1": "pin1", "2": "pin2", "3": "pin3"},
    "ic": {str(i): "" for i in range(1, 9)},
    "module": {str(i): "gpio" for i in range(1, 31)},
    None: {"1": "", "2": "", "3": ""},   # no parts entry, or a kind without a symbol: a box
}


class OnePart:
    """Just enough of a Design for symbol(): one part X1, every pin on a net of its own unless left open."""

    def __init__(self, kind, roles, open_pins=(), types=None, spec=None):
        self.comps = {"X1": {"designator": "X1", "pins": {p: (r or f"P{p}").upper() for p, r in roles.items()},
                             "value": "1k"}}
        self._part = {"kind": kind, "pins": {p: {"name": (r or f"P{p}").upper(), "role": r,
                                                 "type": (types or {}).get(p, "passive")} for p, r in roles.items()}}
        if spec:
            self._part["symbol"] = spec
        self.pin_net = {f"X1.{p}": f"N{p}" for p in roles if p not in open_pins}

    def part(self, des):
        return self._part


def draw(cfg, tmp_path):
    out = tmp_path / "schematic.svg"
    return schematic_draw.main(cfg, argparse.Namespace(board=None, out=str(out), force=False)), out


def without_layout(project):
    """The example's edakit.toml without [schematic.layout] and its tables: nothing tells the drawing how."""
    path = project.root / "edakit.toml"
    keep, skip = [], False
    for line in path.read_text().splitlines():
        if line.startswith("["):
            skip = line.startswith("[schematic.layout")
        if not skip:
            keep.append(line)
    path.write_text("\n".join(keep) + "\n")


@pytest.fixture(autouse=True)
def no_easyeda(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("the drawing started EasyEDA")
    monkeypatch.setattr(eda, "start", refuse)
    monkeypatch.setattr(eda, "connect", refuse)


def test_example_is_drawn(project, tmp_path, capsys):
    code, out = draw(project.config(), tmp_path)
    assert code == 0, capsys.readouterr().out
    texts = {t.text for t in ET.parse(out).getroot().iter(f"{SVG}text")}
    assert {c["designator"] for c in project.graph()["graph"]["components"]} <= texts
    assert {"Power Input", "MCU", "LED Driver", "GP2  LED_SDI  out, SPI TX"} <= texts   # blocks and pin table


def test_without_layout_config_every_part_finds_a_block(project, tmp_path, capsys):
    without_layout(project)
    code, out = draw(project.config(), tmp_path)
    printed = capsys.readouterr().out
    assert code == 0 and "without a block" not in printed, printed
    texts = {t.text for t in ET.parse(out).getroot().iter(f"{SVG}text")}
    assert {"J1 5 V input", "U1 Raspberry Pi Pico 2", "U2 TLC5916IDR"} <= texts


def test_defaults_power_inputs_first_flags_and_capacitors(project):
    cfg = project.config()
    design = Design.from_config(cfg)
    assert schematic_draw.seed_parts(cfg, design, design.comps) == ["J1", "U1", "U2"]
    power = schematic_draw.default_power(design)
    assert power["GND"] == "Ground" and power["+5V"] == power["3V3"] == "Power"
    assert "VIN" not in power and "LED_SDI" not in power
    # C1 decouples U2's VDD (3V3), not the module that makes 3V3; C2 sits at the module's VSYS (+5V)
    assert schematic_draw.default_near(design, design.comps, power, ["U1", "U2", "J1"]) == {"C1": "U2", "C2": "U1"}


@pytest.mark.parametrize("kind", list(SYMBOLS), ids=str)
def test_every_kind_has_a_symbol_the_layout_can_use(kind):
    s = symbol(OnePart(kind, SYMBOLS[kind]), "X1")
    assert set(s.pins) == set(SYMBOLS[kind]) and not s.nc
    tips = [tuple(v[:2]) for v in s.pins.values()]
    assert len(set(tips)) == len(tips)
    assert all(x % 10 == 0 and y % 10 == 0 for x, y in tips)                          # on the grid
    x0, y0, x1, y1 = s.body
    assert all(x0 - 10 <= x <= x1 + 10 and y0 - 10 <= y <= y1 + 10 for x, y in tips)   # in the layout's margin


def test_polarity_and_transistor_pins():
    def pins(kind):
        return symbol(OnePart(kind, SYMBOLS[kind]), "X1").pins
    assert pins("diode")["2"][0] < 0 < pins("diode")["1"][0]           # anode left, cathode right
    assert pins("capacitor")["1"][0] < 0                                # plus left
    npn, pnp, nmos, pmos = pins("npn"), pins("pnp"), pins("nmos"), pins("pmos")
    assert npn["1"][2] == 180 and npn["3"][1] > 0 > npn["2"][1]         # base left, collector up, emitter down
    assert pnp["2"][1] > 0 > pnp["3"][1]                                # emitter up
    assert nmos["3"][1] > 0 > nmos["2"][1] and pmos["2"][1] > 0 > pmos["3"][1]


def test_ic_pins_as_on_a_dip_package_and_only_connected_ones():
    s = symbol(OnePart("ic", SYMBOLS["ic"]), "X1")
    side = {p: ("left" if x < 0 else "right") for p, (x, _, _) in s.pins.items()}
    down = sorted(s.pins, key=lambda p: -s.pins[p][1])
    assert [p for p in down if side[p] == "left"] == ["1", "2", "3", "4"]
    assert [p for p in down if side[p] == "right"] == ["8", "7", "6", "5"]
    assert "3" not in symbol(OnePart("ic", SYMBOLS["ic"], open_pins={"3"}), "X1").pins
    connector = symbol(OnePart("connector", SYMBOLS["connector"], open_pins={"2"}), "X1")
    assert "2" in connector.pins and connector.nc == {"2"}               # a connector shows every pin


def test_parts_entry_chooses_the_sides():
    s = symbol(OnePart("ic", SYMBOLS["ic"], spec={"left": ["8", "1"], "right": ["2", "3"], "bottom": ["4"]}), "X1")
    assert s.pins["8"][0] < 0 and s.pins["8"][1] > s.pins["1"][1]
    assert s.pins["4"][2] == 270
    assert all(s.pins[p][0] > 0 for p in "567")   # connected but not listed: added on the right
    assert not s.problems
    typo = symbol(OnePart("ic", SYMBOLS["ic"], spec={"left": ["1", "1", "9"]}), "X1")
    assert typo.problems == ["X1: the parts entry's 'symbol' lists pins 1, 9 twice or the part has none"]


def test_mechanical_pins_only_when_connected():
    roles = {**SYMBOLS["switch"], "4": ""}
    s = symbol(OnePart("switch", roles, open_pins={"4"}, types={"4": "mechanical"}), "X1")
    assert set(s.pins) == {"1", "2", "3"}


def test_a_pin_without_wire_or_flag_is_reported():
    sheet = Drawing()
    sheet.comps.append(("R1", 0, 0, 0))
    sheet.wires.append(("A", [(-20, 0, -40, 0)]))
    geo = {"R1": {"pins": {"1": [-20, 0, 180], "2": [20, 0, 0]}}}
    assert schematic_draw.loose_pins(sheet, geo, {"R1.1": "A", "R1.2": "B"}) == ["R1.2 (B) ends in nothing"]
