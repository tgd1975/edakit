"""The schematic drawn without EasyEDA: a symbol for every kind of part, the layout of `schematic layout`, a check."""

import argparse
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from edakit import config, eda, schematic_draw
from edakit.design import Design
from edakit.schematic_draw import symbol
from edakit.schematic_layout import Drawing, check_geometry, crossings

SVG = "{http://www.w3.org/2000/svg}"
OPEN_DESIGNS = Path(__file__).parent / "open_designs"

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


def draw(cfg, tmp_path, no_frame=False, name="schematic.svg", board=None):
    out = tmp_path / name
    args = argparse.Namespace(board=board, out=str(out), force=False, no_frame=no_frame)
    return schematic_draw.main(cfg, args), out


def without_layout(project):
    """The example without its schematic file: nothing tells the drawing how."""
    (project.root / "hardware" / "schematic.toml").unlink()


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
    assert {"Power Input", "MCU", "LED Driver", "GP2  LED_CLK  out, SPI SCK"} <= texts   # blocks and pin table


def test_frame_is_optional(project, tmp_path, capsys):
    """--no-frame, or frame = false in the schematic file: no sheet border, no title block, the page only as big as
    the drawing and its margin – for a drawing embedded in a document."""
    code, framed = draw(project.config(), tmp_path, name="framed.svg")
    assert code == 0, capsys.readouterr().out
    code, out = draw(project.config(), tmp_path, no_frame=True)
    assert code == 0, capsys.readouterr().out
    framed_svg, plain_svg = ET.parse(framed).getroot(), ET.parse(out).getroot()
    texts = {t.text for t in plain_svg.iter(f"{SVG}text")}
    assert "LED bar" in {t.text for t in framed_svg.iter(f"{SVG}text")} and "LED bar" not in texts
    assert {c["designator"] for c in project.graph()["graph"]["components"]} <= texts
    assert len(list(plain_svg.iter(f"{SVG}polyline"))) == len(list(framed_svg.iter(f"{SVG}polyline"))) - 2
    height = lambda svg: float(svg.get("height").rstrip("m"))   # noqa: E731
    assert height(plain_svg) < height(framed_svg)
    schematic = project.root / "hardware" / "schematic.toml"
    schematic.write_text("frame = false\n" + schematic.read_text())
    code, by_key = draw(project.config(), tmp_path, name="by_key.svg")
    assert code == 0 and by_key.read_text() == out.read_text()


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


def test_the_boards_print_beside_the_symbols_name():
    one = OnePart("module", {"1": "gpio", "2": "gpio", "3": "gpio"})
    one.comps["X1"]["pins"]["3"] = "3"                                   # a symbol pin without a name
    one._part["pins"]["1"]["print"] = "D2"
    one._part["pins"]["2"]["print"] = "GPIO"                             # the same as the symbol's name
    one._part["pins"]["3"]["print"] = "A7"
    texts = {text for _, _, text, *_ in symbol(one, "X1").texts}
    assert {"GPIO (D2)", "GPIO", "A7"} <= texts and "GPIO (GPIO)" not in texts


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


def with_style(project, style):
    schematic = project.root / "hardware" / "schematic.toml"
    schematic.write_text(f"style = {style}\n" + schematic.read_text())


def svg_parts(out):
    root = ET.parse(out).getroot()
    texts = {t.text for t in root.iter(f"{SVG}text")}
    colours = {e.get("stroke") for e in root.iter(f"{SVG}polyline")}
    return texts, colours


def test_wired_style_draws_every_connection_through(project, tmp_path, capsys):
    """style = "wires": no net names, no flags – every net a wire of its own colour, ground black, supplies red;
    the module with every pin; the output line counts crossings and wire, the title block names the style."""
    code, labelled = draw(project.config(), tmp_path, name="labels.svg")
    assert code == 0, capsys.readouterr().out
    capsys.readouterr()
    with_style(project, '"wires"')
    code, out = draw(project.config(), tmp_path)
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "drawn (wires through): 17 parts" in printed and " crossings, " in printed and " m of wire" in printed
    texts, colours = svg_parts(out)
    nets = {n["name"] for n in project.graph()["graph"]["nets"]} - {"GND"}   # GND: the name of the Pico's pins too
    assert not nets & texts                                  # no labels, no flags
    assert {"LED_CLK", "GND", "+5V"} <= svg_parts(labelled)[0]
    assert {schematic_draw.GROUND_COLOUR, schematic_draw.SUPPLY_COLOURS[0]} <= colours and len(colours) > 6
    assert {"GP19", "SWDIO"} <= texts                         # the Pico's open pins are drawn too
    assert any("wires through" in t for t in texts if t)
    assert "Power Input" not in texts                         # no block titles: the gaps are the channels
    code, again = draw(project.config(), tmp_path, name="again.svg")
    assert again.read_text() == out.read_text()               # the same drawing every time


def test_mixed_style_keeps_labels_for_buses(project, tmp_path, capsys):
    """style = "mixed": a net with nothing but modules, ICs and connectors on it keeps its labelled stubs."""
    with_style(project, '"mixed"')
    code, out = draw(project.config(), tmp_path)
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "3 nets named" in printed
    texts, _ = svg_parts(out)
    assert {"LED_CLK", "LED_SDI", "LED_LE"} <= texts and not {"+5V", "3V3", "BTN"} & texts


def test_style_by_board_and_the_hand_wired_board_is_drawn(tmp_path, capsys):
    """A hand-wired board is drawn – with --board; without it the only made board, as before."""
    project = tmp_path / "boost"
    shutil.copytree(OPEN_DESIGNS / "guitarml-classic-boost", project, ignore=shutil.ignore_patterns("build"))
    (project / "hardware" / "schematic.toml").write_text('style = {wiring = "wires"}\n')
    cfg = config.load(project / "edakit.toml")
    code, out = draw(cfg, tmp_path, name="wiring.svg", board="wiring")
    printed = capsys.readouterr().out
    assert code == 0 and "drawn (wires through): 4 parts" in printed, printed
    code, out = draw(cfg, tmp_path, name="main.svg")
    printed = capsys.readouterr().out
    assert code == 0 and "drawn: " in printed and "drawn (" not in printed, printed   # main: labels


def segs(*wires):
    sheet = Drawing()
    sheet.wires = [(net, [s]) for net, s in wires]
    return sheet


def test_geometry_tells_a_crossing_from_a_t():
    """Two nets crossing inside both wires: a crossing, no short. An end on the other wire – a T, a bend, a junction
    or a pin tip there – is one; so is a net crossing itself without a dot."""
    cross = segs(("A", (0, 0, 40, 0)), ("B", (20, -20, 20, 20)))
    assert check_geometry(cross, {}, {}) == [] and crossings(cross) == [(20, 0, "A", "B")]
    tee = segs(("A", (0, 0, 40, 0)), ("B", (20, 0, 20, 20)))
    assert check_geometry(tee, {}, {}) and not crossings(tee)
    bend = segs(("A", (0, 0, 20, 0)), ("A", (20, 0, 20, 20)), ("B", (0, 10, 40, 10)), ("B", (20, -20, 20, 40)))
    assert any("touches" in p for p in check_geometry(bend, {}, {}))   # B runs through A's bend
    junction = segs(("A", (0, 0, 40, 0)), ("A", (20, 0, 20, 20)), ("B", (20, -20, 20, -1)))
    assert check_geometry(junction, {}, {}) == []
    junction.wires.append(("B", [(20, -1, 20, 30)]))                    # B goes straight through A's junction
    assert any("touches" in p for p in check_geometry(junction, {}, {}))
    tip = segs(("B", (0, 0, 40, 0)))
    tip.comps.append(("R1", 20, 10, 0))
    assert check_geometry(tip, {"R1": {"pins": {"1": [0, -10, 270]}}}, {"R1.1": "A"})  # across A's pin tip
    itself = segs(("A", (0, 0, 40, 0)), ("A", (20, -20, 20, 20)))
    assert check_geometry(itself, {}, {}) == ["wire A crosses itself at (20, 0) without a junction"]


def test_router_joins_around_a_part_and_crosses_only_inside_wires():
    """Two pins of net A on either side of a part, net B's wire across the way: the path goes around the body, crosses
    B in the open and never along it."""
    sheet = Drawing()
    sheet.comps.append(("R1", 0, 0, 0))
    sheet.wires = [("B", [(-60, -40, -60, 40)])]
    sheet.add_box((-100, -60, 100, 60))
    sym = schematic_draw.Symbol()
    sym.pins = {"1": [-20, 0, 180], "2": [20, 0, 0]}
    sym.body = [-10, -8, 10, 8]
    sheet.wires.append(("A", [(-20, 0, -80, 0)]))
    sheet.wires.append(("A", [(20, 0, 40, 0)]))
    got = schematic_draw.wire_through(sheet, {"R1": sym}, {"R1.1": "A", "R1.2": "A"}, {})
    assert not got["unjoined"]
    geo = {"R1": {"pins": sym.pins}}
    assert check_geometry(sheet, geo, {"R1.1": "A", "R1.2": "A"}) == []


def block(box, bodies=()):
    blk = Drawing()
    blk.add_box(box)
    blk.bodies = list(bodies) or [box]
    return blk


def test_wired_blocks_stand_around_the_module_their_pins_facing_it():
    """The module's pin A points left: the block on A goes to its left, its pin level with the module's and facing it
    – turned round when it faces away –, a channel left free between them; a block without a wire to the others
    goes where the drawing grows least, not in a row of its own."""
    hub = block((0, 0, 40, 100))
    facing = block((0, 0, 40, 40))
    got = schematic_draw.around([hub, facing], [{"A": [(0, 50, 180)]}, {"A": [(40, 20, 0)]}], [True, False], set())
    assert got[0] == (0, 0, 0)
    r, dx, dy = got[1]
    assert r == 0 and 20 + dy == 50 and 40 + dx < 0       # level with A, left of the module, not turned
    away = block((0, 0, 40, 40))
    r, dx, dy = schematic_draw.around([hub, away], [{"A": [(0, 50, 180)]}, {"A": [(0, 20, 180)]}], [True, False],
                                      set())[1]
    tip = schematic_draw.moved(0, 20, r, dx, dy)
    assert r == 180 and tip[1] == 50 and tip[0] < 0        # turned: its pin now faces the module
    alone = block((0, 0, 200, 20))
    r, dx, dy = schematic_draw.around([hub, alone], [{"A": [(0, 50, 180)]}, {}], [True, False], set())[1]
    assert dy + 20 <= 0 or dy >= 100                        # above or below the module: a wide block grows least so
