"""Draw the schematic from the graph and the parts database, without EasyEDA: `edakit schematic draw`.

    edakit schematic draw [--board B] [--out FILE] [--force]    -> <artifacts>/schematic_<board>.svg

The arrangement is the one of `edakit schematic layout` (schematic_layout.Layout: blocks, placement by topology, real
wires, power flags); only the symbols come from the parts database instead of EasyEDA's library:

  - resistor, capacitor ('+' when its pins are plus/minus), inductor, fuse, diode, LED, buzzer, battery holder and
    button: two terminals, anode, plus or the first pin on the left; switch (common, throw_a, throw_b) and
    potentiometer (wiper down) likewise;
  - npn, pnp, nmos, pmos: base or gate on the left, collector/drain and emitter/source up and down, pin numbers shown;
  - everything else is a box with the pin names inside and the numbers outside. ICs and modules show their connected
    pins, down the left side and up the right one in the order of their numbers, as on a DIP package; a parts entry
    can choose the sides: "symbol": {"left": [pins top to bottom], "right": [...], "top": [pins left to right],
    "bottom": [...]}. Connectors (one column), relays (coil on the left), RGB LEDs and DIP switches show every pin.

Without [layout] rows in the schematic file every IC, module, connector, relay and battery holder starts a block of
its own, power inputs first, with the part's notes from the graph; without power_flags the ground and every net with a
ground pin get ground symbols, every supply net and every net with RAIL_PINS pins or more supply flags; without near,
a capacitor between flagged nets sits at the IC or module that takes its supply in. Before the file is written the
drawing is checked like a plan for EasyEDA – no wire touches another net or a foreign pin – and every connected pin
must end in a wire or flag of its own net; --force writes anyway. The page is as big as the drawing plus the title
block.

Units as in schematic_layout: 10 mil (EasyEDA's schematic unit), y up, grid 10. The SVG is to scale: its width and
height are given in millimetres.
"""

from __future__ import annotations

import math
import sys
import textwrap
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

from . import engines
from .engines.hint import MATCHERS
from .circuit import supply_nets
from .design import Design, natural_key
from .schematic_layout import (TITLE_BLOCK, Drawing, Layout, block_notes, box_union, check_geometry, layout_config,
                               merge_wires, on_segment, rot)

MM = 0.254          # one unit (10 mil) in millimetres
PAGE_MARGIN = 40
LABEL_TRIM = 6      # of the layout's margin of 10 round a body, labels may take 6 above and below
RAIL_PINS = 10      # a net with this many pins gets flags instead of a wire when the schematic file has no power_flags
CHAR_W = 0.62       # character width / font size of the drawing font
FONT = "DejaVu Sans, Arial, Helvetica, sans-serif"
NAME, NUMBER, DESIGNATOR, VALUE, NET = 6, 5, 7, 6, 6   # font sizes
COLOR = {"part": "#8b1a1a", "wire": "#16801a", "net": "#1f3a9f", "pin": "#555555", "text": "#000000",
         "frame": "#888888"}
TWO_TERMINAL = ("resistor", "capacitor", "inductor", "fuse", "diode", "led", "buzzer", "battery_holder", "button")
TRANSISTORS = ("npn", "pnp", "nmos", "pmos")
SEED_ORDER = {"module": 1, "ic": 2, "connector": 3, "relay": 4, "battery_holder": 5}   # power inputs come first


def text_w(text, size):
    return len(text) * size * CHAR_W


def text_box(x, y, text, size, anchor):
    w = text_w(text, size)
    x0 = x - w / 2 if anchor == "middle" else x - w if anchor == "end" else x
    return x0, y - size / 2, x0 + w, y + size / 2


def short(text, n=12):
    return text if len(text) <= n else text[:n - 1] + "…"


def pin_key(p):
    return natural_key("P" + p) if p.isdigit() else natural_key(p)


def pt(x, y):
    return round(x, 3), round(y, 3)


class Symbol:
    """A part in its own coordinates: pins (tip and the direction pointing away from the body), shapes, texts."""

    def __init__(self):
        self.pins = {}       # pin -> [x, y, direction]
        self.shapes = []     # ("line"|"thick", points) | ("poly", points, filled) | ("circle", x, y, r)
        self.texts = []      # (x, y, text, size, anchor, angle, colour) – drawn upright whatever the rotation
        self.labels = []     # designator and value: ((x, y, anchor), text, size) – they swap places when the part
                             # is turned by 180° or 270°, so the designator stays above (or left of) it
        self.nc = set()      # pins drawn with a no-connect cross
        self.body = None     # the box the layout keeps free; pins stick out of it by up to 10
        self.problems = []   # connected pins the symbol has no place for

    def pin(self, p, tip, end):
        """Pin p as a line from its tip to where it meets the body."""
        (x, y), (ex, ey) = tip, end
        self.pins[p] = [x, y, 0 if x > ex else 180 if x < ex else 90 if y > ey else 270]
        self.line(tip, end)

    def line(self, *points, thick=False):
        self.shapes.append(("thick" if thick else "line", list(points)))

    def poly(self, *points, fill=False):
        self.shapes.append(("poly", list(points), fill))

    def circle(self, x, y, r):
        self.shapes.append(("circle", x, y, r))

    def text(self, x, y, text, size, anchor="middle", angle=0, colour="text"):
        if text:
            self.texts.append((x, y, text, size, anchor, angle, colour))


def arrowhead(s, tip, dx, dy, size=3.0):
    d = math.hypot(dx, dy)
    ux, uy = dx / d, dy / d
    bx, by, half = tip[0] - size * ux, tip[1] - size * uy, size / 2.5
    s.poly(tip, (bx + half * uy, by - half * ux), (bx - half * uy, by + half * ux), fill=True)


# --- two terminals: the body between x = -10 and 10 around y = 0; returns its top and bottom ---------------------

def _resistor(s, polar):
    s.poly((-10, -4), (10, -4), (10, 4), (-10, 4))
    return 4, -4


def _capacitor(s, polar):
    s.line((-10, 0), (-2.5, 0))
    s.line((2.5, 0), (10, 0))
    s.line((-2.5, -7), (-2.5, 7), thick=True)
    s.line((2.5, -7), (2.5, 7), thick=True)
    if polar:
        s.text(-7, 6, "+", 7)
    return 7, -7


def _inductor(s, polar):
    r = 10 / 3
    s.line(*[(-10 + r * (2 * k + 1) - r * math.cos(math.pi * i / 8), r * math.sin(math.pi * i / 8))
             for k in range(3) for i in range(9)])
    return 4, -2


def _fuse(s, polar):
    s.poly((-10, -3.5), (10, -3.5), (10, 3.5), (-10, 3.5))
    s.line((-10, 0), (10, 0))
    return 4, -4


def _diode(s, polar):
    s.line((-10, 0), (-5, 0))
    s.line((5, 0), (10, 0))
    s.poly((-5, -6), (-5, 6), (5, 0))
    s.line((5, -6), (5, 6))
    return 6, -6


def _led(s, polar):
    _diode(s, polar)
    for x in (-2, 3):
        s.line((x, 7), (x + 4, 11))
        arrowhead(s, (x + 5, 12), 1, 1, 2.5)
    return 12, -6


def _buzzer(s, polar):
    s.line((-10, 0), (-7, 0))
    s.line((7, 0), (10, 0))
    s.circle(0, 0, 7)
    s.text(-9, 7, "+", 7)
    return 8, -7


def _battery(s, polar):
    s.line((-10, 0), (-2, 0))
    s.line((2, 0), (10, 0))
    s.line((-2, -8), (-2, 8))
    s.line((2, -4), (2, 4), thick=True)
    s.text(-7, 8, "+", 7)
    return 8, -8


def _button(s, polar):
    s.line((-10, 0), (-6.5, 0))
    s.line((6.5, 0), (10, 0))
    s.circle(-5, 0, 1.5)
    s.circle(5, 0, 1.5)
    s.line((-8, 4), (8, 4))
    s.line((0, 4), (0, 9))
    s.line((-3, 9), (3, 9))
    return 9, -2


BODY = {"resistor": _resistor, "capacitor": _capacitor, "inductor": _inductor, "fuse": _fuse, "diode": _diode,
        "led": _led, "buzzer": _buzzer, "battery_holder": _battery, "button": _button}


def terminals(kind, pins, role):
    """(left pins, right pins) of a two-terminal part, or None if its pins do not fit that."""
    left = right = []
    if kind in ("diode", "led"):
        left, right = [p for p in pins if role[p] == "anode"], [p for p in pins if role[p] == "cathode"]
    elif kind == "button":
        left, right = [p for p in pins if role[p] == "a"], [p for p in pins if role[p] == "b"]
    elif any(role[p].startswith("plus") for p in pins):
        left = [p for p in pins if role[p].startswith("plus")]
        right = [p for p in pins if role[p].startswith("minus")]
    if not (left or right) and len(pins) == 2:
        left, right = pins[:1], pins[1:]
    if not left or not right or len(left) + len(right) != len(pins):
        return None
    return left, right


def two_terminal(kind, left, right, connected, polar):
    s = Symbol()
    rows = 1
    for side, x in ((left, -1), (right, 1)):
        shown = [p for p in side if p in connected] or side[:1]
        rows = max(rows, len(shown))
        for k, p in enumerate(shown):
            s.pin(p, (20 * x, -20 * k), (10 * x, -20 * k))
        if len(shown) > 1:
            s.line((10 * x, 0), (10 * x, -20 * (len(shown) - 1)))   # pins connected inside the part
    top, bottom = BODY[kind](s, polar)
    bottom = min(bottom, -20 * (rows - 1))
    return s, (0, top + 7, "middle"), (0, bottom - 7, "middle"), (-10, bottom, 10, top)


def transistor(kind, pins, role):
    """Base or gate on the left; collector/drain up for npn and nmos, emitter/source up for pnp and pmos."""
    names = ("base", "collector", "emitter") if kind in ("npn", "pnp") else ("gate", "drain", "source")
    by = {role[p]: p for p in pins}
    if len(pins) != 3 or set(by) != set(names):
        return None
    ctrl, out, ret = (by[n] for n in names)
    top, bottom = (out, ret) if kind in ("npn", "nmos") else (ret, out)
    s = Symbol()
    if kind in ("npn", "pnp"):
        s.pin(ctrl, (-20, 0), (-3, 0))
        s.line((-3, -7), (-3, 7), thick=True)
        s.pin(top, (10, 20), (10, 10))
        s.line((-3, 3), (10, 10))
        s.pin(bottom, (10, -20), (10, -10))
        s.line((-3, -3), (10, -10))
        if kind == "npn":
            arrowhead(s, (10, -10), 13, -7)
        else:
            arrowhead(s, (0.9, 5.1), -13, -7)
    else:
        s.pin(ctrl, (-20, 0), (-6, 0))
        s.line((-6, -7), (-6, 7))
        for y0, y1 in ((5, 9), (-2, 2), (-9, -5)):
            s.line((-3, y0), (-3, y1), thick=True)
        s.pin(top, (10, 20), (10, 7))
        s.line((-3, 7), (10, 7))
        s.pin(bottom, (10, -20), (10, -7))
        s.line((-3, -7), (10, -7))
        s.line((-3, 0), (10, 0), (10, -7 if kind == "nmos" else 7))   # body tied to the source
        if kind == "nmos":
            arrowhead(s, (-2.5, 0), -1, 0)
        else:
            arrowhead(s, (7, 0), 1, 0)
    for x, y, p, anchor in ((-15, 3, ctrl, "middle"), (13, 15, top, "start"), (13, -15, bottom, "start")):
        s.text(x, y, p, NUMBER, anchor, colour="pin")
    return s, (14, 4, "start"), (14, -5, "start"), (-10, -12, 12, 12)


def spdt(pins, role):
    by = {role[p]: p for p in pins}
    if len(pins) != 3 or set(by) != {"common", "throw_a", "throw_b"}:
        return None
    s = Symbol()
    s.pin(by["common"], (-20, 0), (-6.5, 0))
    s.pin(by["throw_a"], (20, 10), (6.5, 10))
    s.pin(by["throw_b"], (20, -10), (6.5, -10))
    for x, y in ((-5, 0), (5, 10), (5, -10)):
        s.circle(x, y, 1.5)
    s.line((-3.6, 0.8), (5, 7.5))
    return s, (0, 18, "middle"), (0, -18, "middle"), (-10, -12, 10, 12)


def potentiometer(pins, role):
    by = {role[p]: p for p in pins}
    if len(pins) != 3 or set(by) != {"end_a", "end_b", "wiper"}:
        return None
    s = Symbol()
    s.pin(by["end_a"], (-20, 0), (-10, 0))
    s.pin(by["end_b"], (20, 0), (10, 0))
    s.poly((-10, -4), (10, -4), (10, 4), (-10, 4))
    s.pin(by["wiper"], (0, -20), (0, -8))
    arrowhead(s, (0, -4), 0, 1, 4)
    return s, (0, 11, "middle"), (4, -13, "start"), (-10, -12, 10, 4)


def box_sides(kind, pins, role, connected, spec):
    """Pins per side of a box: left and right top to bottom, top and bottom left to right."""
    if spec:
        sides = {k: [str(p) for p in spec.get(k, [])] for k in ("left", "right", "top", "bottom")}
        listed = {p for v in sides.values() for p in v}
        sides["right"] += [p for p in pins if p in connected and p not in listed]
        return sides
    by_role = {"relay": ("coil", ""), "led_rgb": ("anode", "cathode"), "dip_switch": ("a", "b")}
    if kind == "connector":
        return {"right": pins}
    if kind in by_role:
        a, b = by_role[kind]
        left = [p for p in pins if role[p].startswith(a)]
        right = [p for p in pins if p not in left and role[p].startswith(b)]
        if left and right and len(left) + len(right) == len(pins):
            return {"left": left, "right": right}
    # as on a DIP package: the first half of the pins down the left side, the second half up the right one
    shown = ([p for p in pins if p in connected] or pins) if kind in ("ic", "module") else pins
    half = math.ceil(len(pins) / 2)
    left_half = set(pins[:half])
    return {"left": [p for p in shown if p in left_half], "right": [p for p in reversed(shown) if p not in left_half]}


def box(sides, names, designator, value):
    left, right, top, bottom = (sides.get(k, []) for k in ("left", "right", "top", "bottom"))

    def name(p):
        n = str(names.get(p, p))
        return "" if n == p else n

    wl = max((text_w(name(p), NAME) for p in left), default=0)
    wr = max((text_w(name(p), NAME) for p in right), default=0)
    hv = max((text_w(name(p), NAME) for p in top + bottom), default=0)   # names of top/bottom pins run upwards
    one_side = bool(right) and not (left or top or bottom)   # a connector: its labels run off to the free left
    w = max(20 if one_side and not wr else 40, wl + wr + (14 if wl and wr else 8),
            10 * (max(len(top), len(bottom)) + 1),
            0 if one_side else max(text_w(designator, DESIGNATOR), text_w(value, VALUE)) + 4)
    w = 20 * math.ceil(w / 20)        # pin tips on the grid
    x0, x1 = -w // 2, w // 2
    rows = max(len(left), len(right), 1)
    room = 10 * math.ceil((hv + 4) / 10)
    y1 = 10 + (room if top else 0)
    y0 = -10 * rows - (room if bottom else 0)
    s = Symbol()
    for k, p in enumerate(left):
        s.pin(p, (x0 - 10, -10 * k), (x0, -10 * k))
        s.text(x0 + 2.5, -10 * k, name(p), NAME, "start")
        s.text(x0 - 1.5, -10 * k + 3, p, NUMBER, "end", colour="pin")
    for k, p in enumerate(right):
        s.pin(p, (x1 + 10, -10 * k), (x1, -10 * k))
        s.text(x1 - 2.5, -10 * k, name(p), NAME, "end")
        s.text(x1 + 1.5, -10 * k + 3, p, NUMBER, "start", colour="pin")
    for k, p in enumerate(top):
        x = x0 + 10 * (k + 1)
        s.pin(p, (x, y1 + 10), (x, y1))
        s.text(x, y1 - 2.5, name(p), NAME, "end", angle=90)
        s.text(x - 3, y1 + 1.5, p, NUMBER, "start", angle=90, colour="pin")
    for k, p in enumerate(bottom):
        x = x0 + 10 * (k + 1)
        s.pin(p, (x, y0 - 10), (x, y0))
        s.text(x, y0 + 2.5, name(p), NAME, "start", angle=90)
        s.text(x - 3, y0 - 1.5, p, NUMBER, "end", angle=90, colour="pin")
    s.poly((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    top_y = y1 + (10 if top else 0) + 6
    low_y = y0 - (10 if bottom else 0) - 6
    x, anchor = (x1, "end") if one_side else (x0, "start")
    return s, (x, top_y, anchor), (x, low_y, anchor), (x0, y0, x1, y1)


def symbol(design, d):
    comp = design.comps[d]
    part = design.part(d) or {}
    info = part.get("pins") or {}
    kind = part.get("kind")
    net_of = {p: design.pin_net.get(f"{d}.{p}") for p in comp["pins"]}
    pins = sorted((p for p in comp["pins"] if (info.get(p) or {}).get("type") != "mechanical" or net_of[p]),
                  key=pin_key)
    connected = {p for p in pins if net_of[p]}
    role = {p: str((info.get(p) or {}).get("role") or "") for p in pins}
    value, part_name = str(comp.get("value") or ""), str(comp.get("part") or "")
    small = short(value) or (part_name if len(part_name) <= 12 else "")   # no cut-off part numbers at small symbols
    built = None
    if kind in TWO_TERMINAL and (sides := terminals(kind, pins, role)):
        polar = kind == "capacitor" and any(r.startswith("plus") for r in role.values())
        built = two_terminal(kind, *sides, connected, polar)
    elif kind in TRANSISTORS:
        built = transistor(kind, pins, role)
    elif kind == "switch":
        built = spdt(pins, role)
    elif kind == "potentiometer":
        built = potentiometer(pins, role)
    if built is None:
        small = value or part_name
        built = box(box_sides(kind, pins, role, connected, part.get("symbol")), comp["pins"], d, small)
    s, dpos, vpos, drawn = built
    labels = [(d, DESIGNATOR), (small, VALUE)]
    core = drawn
    for x, y, anchor in (dpos, vpos):   # room for either text at either place – they swap when the part is turned
        for text, size in labels:
            if text:
                core = box_union(core, text_box(x, y, text, size, anchor))
    if all(direction in (0, 180) for _, _, direction in s.pins.values()):
        # pins only left and right: above and below, the labels may use the margin the layout keeps round a body
        core = (core[0], min(core[1] + LABEL_TRIM, drawn[1]), core[2], max(core[3] - LABEL_TRIM, drawn[3]))
    s.labels = [(place, text, size) for place, (text, size) in zip((dpos, vpos), labels)]
    s.body = list(core)
    s.nc = {p for p in s.pins if p not in connected}
    missing = sorted(connected - set(s.pins), key=pin_key)
    if missing:
        s.problems.append(f"{d}: pins {', '.join(missing)} are connected but not on the symbol (parts entry 'symbol')")
    listed = [str(p) for side in (part.get("symbol") or {}).values() for p in side]
    wrong = sorted({p for p in listed if p not in comp["pins"] or listed.count(p) > 1}, key=pin_key)
    if wrong:
        s.problems.append(f"{d}: the parts entry's 'symbol' lists pins {', '.join(wrong)} twice or the part has none")
    return s


# --- arrangement when the schematic file says nothing ----------------------------------------------------------

def default_power(design):
    """Flags instead of wires: ground symbols for the ground and every net with a ground pin; supply flags for every
    supply net (a supply output or an IC supply pin on it) and every net with RAIL_PINS pins or more – drawn as
    wires, a rail behind a diode or a switch would gather half the board into one tree."""
    supplies = supply_nets(design)
    power = {}
    for name, net in design.nets.items():
        if name == design.ground or any(design.pin_info(r).get("type") == "ground" for r in net["pins"]):
            power[name] = "Ground"
        elif name in supplies or len(net["pins"]) >= RAIL_PINS:
            power[name] = "Power"
    return power


def seed_parts(cfg, design, comps):
    """Parts that start a block: power inputs first, then modules, ICs, connectors, relays, battery holders."""
    kinds = {d: (design.part(d) or {}).get("kind") for d in comps}
    inputs = set(MATCHERS["power_input"](design, cfg, engines.load_sim(cfg)))
    seeds = [d for d in comps if kinds[d] in SEED_ORDER]
    return sorted(seeds, key=lambda d: (0 if d in inputs else SEED_ORDER[kinds[d]], natural_key(d)))


def default_rows(comps, seeds):
    """One block per seed part with its notes from the graph, in rows of about √n blocks. Title: designator and
    label (without its brackets), or the part number if the label is longer than 32 characters."""
    blocks, notes = [], {}
    for d in seeds:
        label = str(comps[d].get("label") or "").split(" (")[0]
        if len(label) > 32 or not label:
            label = str(comps[d].get("part") or "") or label
        title = short(f"{d} {label}".strip(), 40)
        blocks.append((title, [d]))
        if comps[d].get("notes"):
            notes[title] = textwrap.wrap(str(comps[d]["notes"]), 70)
    per_row = max(1, math.ceil(math.sqrt(len(blocks))))
    return [[[b] for b in blocks[i:i + per_row]] for i in range(0, len(blocks), per_row)], notes


def default_near(design, comps, power, hosts):
    """Capacitors that touch only flagged nets sit at the first host part that takes their supply in (a supply pin),
    or else at the first one with any pin on it."""
    near = {}
    for d in sorted(comps, key=natural_key):
        if (design.part(d) or {}).get("kind") != "capacitor":
            continue
        nets = {design.pin_net.get(f"{d}.{p}") for p in comps[d]["pins"]}
        supply = sorted(n for n in nets if n in power and power[n] != "Ground")
        if None in nets or not nets <= set(power) or not supply:
            continue
        on = {h: [design.pin_info(f"{h}.{p}").get("type") for p in comps[h]["pins"]
                  if design.pin_net.get(f"{h}.{p}") == supply[0]] for h in hosts}
        host = next((h for h in hosts if "power_in" in on[h]), None) or next((h for h in hosts if on[h]), None)
        if host:
            near[d] = host
    return near


def loose_pins(sheet, geo, pin_net):
    """Connected pins without a wire end or a flag of their own net at the tip."""
    ends = defaultdict(set)
    for net, segs in sheet.wires:
        for s in segs:
            ends[pt(s[0], s[1])].add(net)
            ends[pt(s[2], s[3])].add(net)
    for net, x, y, _ in sheet.flags:
        ends[pt(x, y)].add(net)
    out = []
    for d, x, y, r in sheet.comps:
        for p, (lx, ly, _) in geo[d]["pins"].items():
            net = pin_net.get(f"{d}.{p}")
            px, py = rot(lx, ly, r)
            if net and net not in ends.get(pt(px + x, py + y), ()):
                out.append(f"{d}.{p} ({net}) ends in nothing")
    return out


# --- SVG ----------------------------------------------------------------------------------------------------------

def junctions(sheet, tips):
    """Points where three or more wire ends (a pin tip counts as one) meet."""
    by_net = defaultdict(list)
    for net, segs in sheet.wires:
        by_net[net] += segs
    dots = []
    for segs in by_net.values():
        deg = Counter()
        for s in segs:
            deg[pt(s[0], s[1])] += 1
            deg[pt(s[2], s[3])] += 1
        for s in segs:   # an end in the middle of another piece: a T junction
            a, b = pt(s[0], s[1]), pt(s[2], s[3])
            for e in list(deg):
                if e not in (a, b) and on_segment(*e, (*a, *b)):
                    deg[e] += 2
        dots += [e for e, n in deg.items() if n + (e in tips) >= 3]
    return dots


class Svg:
    def __init__(self, w, h):
        self.h = h
        self.out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * MM:.1f}mm" height="{h * MM:.1f}mm" '
                    f'viewBox="0 0 {w} {h}" font-family="{FONT}" stroke-linecap="round" stroke-linejoin="round">',
                    f'<rect width="{w}" height="{h}" fill="#ffffff"/>']

    def p(self, x, y):
        return f"{round(x, 2):g},{round(self.h - y, 2):g}"

    def line(self, points, colour, width=1.2, dash=None):
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        self.out.append(f'<polyline points="{" ".join(self.p(*q) for q in points)}" fill="none" stroke="{colour}" '
                        f'stroke-width="{width}"{extra}/>')

    def poly(self, points, colour, fill):
        self.out.append(f'<polygon points="{" ".join(self.p(*q) for q in points)}" '
                        f'fill="{colour if fill else "#ffffff"}" stroke="{colour}" stroke-width="1.2"/>')

    def circle(self, x, y, r, colour, fill=False):
        self.out.append(f'<circle cx="{round(x, 2):g}" cy="{round(self.h - y, 2):g}" r="{r}" '
                        f'fill="{colour if fill else "#ffffff"}" stroke="{colour}" stroke-width="1.2"/>')

    def text(self, x, y, text, size, anchor="start", angle=0, colour="#000000", bold=False, dy="0.35em"):
        """Upright: a text turned by 180° is drawn the other way round, so it never stands on its head."""
        if angle in (180, 270):
            angle -= 180
            anchor = {"start": "end", "end": "start"}.get(anchor, anchor)
        X, Y = round(x, 2), round(self.h - y, 2)
        turn = f' transform="rotate(-90 {X:g} {Y:g})"' if angle == 90 else ""
        weight = ' font-weight="bold"' if bold else ""
        self.out.append(f'<text x="{X:g}" y="{Y:g}" dy="{dy}" font-size="{size}" text-anchor="{anchor}" '
                        f'fill="{colour}"{weight}{turn} xml:space="preserve">{escape(text)}</text>')

    def done(self):
        return "\n".join([*self.out, "</svg>"]) + "\n"


def flag_reach(net, kind, ground):
    """How far a flag of this drawing reaches from its pin: a line of 6, the bars, the name (not for the ground)."""
    if kind == "Ground":
        return 11 if net == ground else 13 + text_w(net, NET)
    return 10 + text_w(net, NET)


class DrawLayout(Layout):
    """The layout with this drawing's flags: 8 high, so flags at neighbouring pins (10 apart) need no jog."""
    ground = "GND"

    def flag_box(self, net):
        return 0, -4, flag_reach(net, self.power.get(net), self.ground), 4


def fit(sheet):
    """The drawing on a page of its own size: a margin all round, the title block below."""
    b = sheet.box
    out = Drawing()
    out.place(sheet, 0, round(PAGE_MARGIN - b[0]), round(TITLE_BLOCK[1] + PAGE_MARGIN - b[1]))
    w = max(b[2] - b[0], TITLE_BLOCK[0]) + 2 * PAGE_MARGIN
    h = b[3] - b[1] + 2 * PAGE_MARGIN + TITLE_BLOCK[1]
    return out, (math.ceil(w), math.ceil(h))


def merged(intervals):
    out = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def net_labels(sheet, power, tips):
    """(x, y, net, anchor, angle): at every loose end of a wire – the net goes on elsewhere – or, without one, in the
    middle of the longest straight run; above horizontal wires, left of vertical ones."""
    flags = {pt(x, y) for _, x, y, _ in sheet.flags}
    out = []
    for net, segs in merge_wires(sheet.wires):
        if net in power:
            continue   # the flags name it
        pieces = [(pt(s[0], s[1]), pt(s[2], s[3])) for s in segs]
        ends = Counter(p for piece in pieces for p in piece)
        loose = []
        for a, b in pieces:
            for end, other in ((a, b), (b, a)):
                if ends[end] == 1 and end not in tips and end not in flags \
                        and not any(end not in q and on_segment(*end, (*q[0], *q[1])) for q in pieces):
                    loose.append((end, other))
        for (x, y), (ox, oy) in loose:
            if y == oy:
                out.append((x, y + 4.5, net, "start" if ox > x else "end", 0))
            else:
                out.append((x - 4.5, y, net, "start" if oy > y else "end", 90))
        if loose:
            continue
        rows, cols = defaultdict(list), defaultdict(list)
        for (x0, y0), (x1, y1) in pieces:
            if y0 == y1:
                rows[y0].append((min(x0, x1), max(x0, x1)))
            else:
                cols[x0].append((min(y0, y1), max(y0, y1)))
        flat = [(b - a, (a + b) / 2, y) for y, iv in rows.items() for a, b in merged(iv)]
        if flat:
            _, x, y = max(flat)
            out.append((x, y + 4.5, net, "middle", 0))
        else:
            _, y, x = max((b - a, (a + b) / 2, x) for x, iv in cols.items() for a, b in merged(iv))
            out.append((x - 4.5, y, net, "middle", 90))
    return out


def render(sheet, size, syms, power, ground, title_lines):
    w, h = size
    g = Svg(w, h)
    g.line([(10, 10), (w - 10, 10), (w - 10, h - 10), (10, h - 10), (10, 10)], COLOR["frame"], 1.5)
    tx, tw, th = w - TITLE_BLOCK[0], TITLE_BLOCK[0] - 10, TITLE_BLOCK[1] - 10
    g.line([(tx, 10), (tx + tw, 10), (tx + tw, 10 + th), (tx, 10 + th), (tx, 10)], COLOR["frame"], 1.5)
    for i, (text, size_, bold) in enumerate(title_lines):
        g.text(tx + 12, 10 + th - 22 - 18 * i - (6 if i else 0), text, size_, bold=bold)
    for _, (x0, y0, x1, y1) in sheet.frames:
        g.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], COLOR["frame"], 1, "6 4")
    for x, y, content, size_, bold, align in sheet.texts:
        lines = content.split("\n")
        y0 = y - 0.8 * size_ if align == 1 else y + (len(lines) - 1) * size_   # first baseline
        for i, ln in enumerate(lines):
            g.text(x, y0 - i * size_, ln, size_, bold=bold, dy="0")
    tips = set()
    for d, cx, cy, r in sheet.comps:
        for p, (lx, ly, _) in syms[d].pins.items():
            if p not in syms[d].nc:
                px, py = rot(lx, ly, r)
                tips.add(pt(px + cx, py + cy))
    for _, segs in sheet.wires:
        for s in segs:
            g.line([s[:2], s[2:]], COLOR["wire"])
    for x, y in junctions(sheet, tips):
        g.circle(x, y, 2.2, COLOR["wire"], fill=True)
    for x, y, net, anchor, angle in net_labels(sheet, power, tips):
        g.text(x, y, net, NET, anchor, angle, COLOR["net"])
    for net, x, y, fd in sheet.flags:
        dx, dy = rot(1, 0, fd)
        px, py = -dy, dx
        ground_flag = power.get(net) == "Ground"
        g.line([(x, y), (x + 6 * dx, y + 6 * dy)], COLOR["part"])
        for dist, half in ((6, 4), (8, 2.5), (10, 1)) if ground_flag else ((6, 4),):
            cx, cy = x + dist * dx, y + dist * dy
            g.line([(cx - half * px, cy - half * py), (cx + half * px, cy + half * py)], COLOR["part"],
                   1.2 if ground_flag else 1.8)
        if not ground_flag or net != ground:
            far = 13 if ground_flag else 9
            g.text(x + far * dx, y + far * dy, net, NET, "start", fd, COLOR["net"])
    for d, cx, cy, r in sheet.comps:
        s = syms[d]

        def T(x, y, r=r, cx=cx, cy=cy):
            x, y = rot(x, y, r)
            return x + cx, y + cy
        for sh in s.shapes:
            if sh[0] in ("line", "thick"):
                g.line([T(*q) for q in sh[1]], COLOR["part"], 2.4 if sh[0] == "thick" else 1.2)
            elif sh[0] == "poly":
                g.poly([T(*q) for q in sh[1]], COLOR["part"], sh[2])
            else:
                g.circle(*T(sh[1], sh[2]), sh[3], COLOR["part"])
        for x, y, text, size_, anchor, angle, colour in s.texts:
            g.text(*T(x, y), text, size_, anchor, (angle + r) % 360, COLOR[colour])
        places = [place for place, _, _ in s.labels]
        if r in (180, 270):
            places.reverse()
        for (x, y, anchor), (_, text, size_) in zip(places, s.labels):
            if text:
                g.text(*T(x, y), text, size_, anchor, r, COLOR["text"])
        for p in sorted(s.nc, key=natural_key):    # a set: sorted, or the SVG changes with the hash seed
            x, y = T(*s.pins[p][:2])
            g.line([(x - 3, y - 3), (x + 3, y + 3)], COLOR["part"])
            g.line([(x - 3, y + 3), (x + 3, y - 3)], COLOR["part"])
    return g.done()


def drawing(cfg, board, drawn_by="edakit schematic draw"):
    """The board's sheet as this drawing lays it out – for the SVG here and the KiCad schematic (toolchain/kicad):
    {"design", "sheet", "size", "syms", "power", "problems"}, or None when the board has no parts in the graph."""
    design = Design.from_config(cfg)
    comps = design.board_comps(board.name)
    if not comps:
        return None
    syms = {d: symbol(design, d) for d in comps}
    geo = {d: {"type": comps[d].get("type"), "pins": s.pins, "body": s.body} for d, s in syms.items()}
    lc = layout_config(cfg, design)
    if not cfg.schematic.get("layout", {}).get("power_flags"):
        lc["power"] = default_power(design)
    notes = block_notes(cfg, design, board, lc, drawn_by=drawn_by)
    seeds = seed_parts(cfg, design, comps)
    if not lc["rows"]:
        lc["rows"], graph_notes = default_rows(comps, seeds)
        for title, lines in graph_notes.items():
            notes.setdefault(title, lines)
    if not lc["near"]:
        hosts = sorted(seeds, key=lambda d: SEED_ORDER[(design.part(d) or {}).get("kind")])
        lc["near"] = default_near(design, comps, lc["power"], hosts)
    graph_nets = {n["name"]: n["pins"] for n in design.graph["nets"]}
    lay = DrawLayout(comps, graph_nets, geo, lc["rows"], notes, lc["power"], lc["near"], lc["stacked"], CHAR_W)
    lay.ground = design.ground
    sheet, size = fit(lay.build()[0])
    for warning in lay.warnings:
        print(f"  ! {warning}")
    problems = [p for s in syms.values() for p in s.problems] + check_geometry(sheet, geo, lay.pin_net) \
        + loose_pins(sheet, geo, lay.pin_net)
    return {"design": design, "sheet": sheet, "size": size, "syms": syms, "power": lc["power"], "problems": problems}


def main(cfg, args):
    board = cfg.board(args.board, made=True)
    drawn = drawing(cfg, board)
    if drawn is None:
        print(f"edakit: board {board.name} has no parts in the graph", file=sys.stderr)
        return 1
    design, sheet, size, syms, problems = (drawn[k] for k in ("design", "sheet", "size", "syms", "problems"))
    for prob in problems:
        print(f"  ! {prob}")
    mm = f"{size[0] * MM:.0f} x {size[1] * MM:.0f} mm"
    print(f"drawn: {len(sheet.comps)} parts, {len(merge_wires(sheet.wires))} wires, {len(sheet.flags)} flags, {mm}")
    if problems and not args.force:
        print(f"{len(problems)} conflicts – nothing written (--force writes anyway)")
        return 2
    out = Path(args.out) if args.out else cfg.artifact(f"schematic_{board.name}.svg")
    out.parent.mkdir(parents=True, exist_ok=True)
    date = design.graph.get("date", "")
    title_lines = [(board.title, 16, True), (f"{cfg.project} · board {board.name}", 8, False),
                   (f"graph v{design.version}" + (f" ({date})" if date else "") + f" · {mm}", 8, False),
                   ("drawn by edakit schematic draw – change the graph, not this drawing", 7, False)]
    out.write_text(render(sheet, size, syms, drawn["power"], design.ground, title_lines), encoding="utf-8")
    print(f"  -> {out}")
    return 2 if problems else 0
