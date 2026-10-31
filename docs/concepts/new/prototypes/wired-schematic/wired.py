#!/usr/bin/env python3
"""Prototype: the schematic with every connection drawn through – no net labels, no power flags – the way Fritzing's
schematic view and the drawings of the maker scene do it (docs/concepts/new/wired-schematic.md).

    uv run --project <edakit> python wired.py <project dir> [--board B] [--out FILE] [--names] [--gap N]

It reuses edakit's drawing (edakit/schematic_draw.py, edakit/schematic_layout.py): the symbols from the parts
database, the trees of parts hanging on the pins of the modules, ICs and connectors, the page and the title block.
What it changes:

  - a pin without a child gets a lead of one cell instead of a labelled stub, a power net no flag (WiredLayout);
  - modules show every pin, as the board does, the unused ones grey (full_symbol);
  - the blocks stand further apart – the gaps are the channels the wires run in – and have no frames;
  - then a router on the schematic grid (10 mil x 10 = 2.54 mm cells) joins every net: the ground and the supplies
    along a rail below and above the drawing, the signals by the cheapest path (Dijkstra: a step 1, a bend 4, a
    crossing of another net 12, running beside one 1; never through a part, never along another net's wire, never
    through its ends, bends or pin tips);
  - every net gets a colour – ground black, supplies red – chosen so that nets that cross or run side by side differ
    where ten colours allow it;
  - it measures what a drawing like this costs: wire length, crossings, bends, unrouted connections, page size.

Nothing of edakit is changed; the prototype imports it. Coordinates as in schematic_layout: 10 mil, y up.
"""

from __future__ import annotations

import argparse
import heapq
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]   # docs/concepts/new/prototypes/wired-schematic -> edakit
sys.path.insert(0, str(ROOT))

from edakit import config, schematic_layout as sl   # noqa: E402
from edakit import schematic_draw as sd   # noqa: E402
from edakit.design import Design   # noqa: E402
from edakit.schematic_draw import (DrawLayout, Svg, box, box_sides, default_near, default_power, default_rows,   # noqa: E402
                                   fit, junctions, net_labels, pin_key, pt, seed_parts, symbol, text_box)
from edakit.schematic_layout import Drawing, block_notes, box_union, layout_config, merge_wires, rot, snap_up   # noqa: E402

CELL = 10               # the grid: EasyEDA's schematic grid
LEAD = 10               # a pin without a child gets a lead of one cell; the router starts there
STEP, TURN, CROSS, BESIDE = 1, 4, 12, 1   # costs of the router
RAIL_OFF = 3            # cells between the drawing and the first rail
RAIL_GAP = 2            # cells between two rails
PALETTE = ["#1f5fbf", "#2a8f3a", "#8a3fb0", "#b0652a", "#0f8f8f", "#c42f7a", "#7a7a1f", "#4f6f9f", "#9f3f3f",
           "#3f8f6f"]
GROUND_COLOUR = "#202020"
SUPPLY_COLOURS = ["#d42020", "#e07a10", "#b8a000", "#d4207a"]
H, V, X = "h", "v", "x"   # how a net occupies a cell: horizontally, vertically, or an end, bend, junction or pin tip
DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))


# --- edakit's layout without labels and flags ---------------------------------------------------------------------

class WiredLayout(DrawLayout):
    labelled = frozenset()   # nets that keep edakit's labelled stubs (the mixed style)

    def branch(self, d, p, net):
        """As edakit's branch, but a pin without a child gets a lead of one cell and a power net no flag. A net of
        `labelled` gets the labelled stub edakit draws."""
        kids = self.kids.get((d, p), [])
        items = [self.node(k, kp) for k, kp in kids]
        if not items:
            lead = Drawing()
            length = max(30, snap_up(6 * len(net) + 10)) if net in self.labelled else LEAD
            lead.wire(net, [(0, 0), (length, 0)])
            lead.add_box((0, -4, length, 4))
            return lead
        heights = [(snap_up(-it.box[1]), snap_up(it.box[3])) for it in items]
        pos, y = [], 0
        for i, (lo, hi) in enumerate(heights):
            if i:
                y -= heights[i - 1][0] + sl.GAP + hi
            pos.append(y)
        br = Drawing()
        stops = sorted({0, *pos})
        segs = [(sl.BUS, a, sl.BUS, b) for a, b in zip(stops, stops[1:])]
        br.wire(net, [(0, 0), (sl.BUS, 0)])
        for it, py in zip(items, pos):
            shift = max(0, snap_up(-it.box[0] + sl.GAP)) if it.box[0] < 0 else 0
            br.wire(net, [(sl.BUS, py), (sl.LEAD + shift, py)])
            br.place(it, 0, sl.LEAD + shift, py)
        if segs:
            br.wires.append((net, segs))
        return br


def full_symbol(design, d):
    """A module with every pin, as the board shows them – not only the connected ones; the unused ones in `unused`."""
    comp = design.comps[d]
    part = design.part(d) or {}
    info = part.get("pins") or {}
    net_of = {p: design.pin_net.get(f"{d}.{p}") for p in comp["pins"]}
    pins = sorted((p for p in comp["pins"] if (info.get(p) or {}).get("type") != "mechanical" or net_of[p]),
                  key=pin_key)
    role = {p: str((info.get(p) or {}).get("role") or "") for p in pins}
    value, part_name = str(comp.get("value") or ""), str(comp.get("part") or "")
    small = value or part_name
    s, dpos, vpos, drawn = box(box_sides(part.get("kind"), pins, role, set(pins), part.get("symbol")),
                               comp["pins"], d, small)
    labels = [(d, sd.DESIGNATOR), (small, sd.VALUE)]
    core = drawn
    for x, y, anchor in (dpos, vpos):
        for text, size in labels:
            if text:
                core = box_union(core, text_box(x, y, text, size, anchor))
    s.labels = [(place, text, size) for place, (text, size) in zip((dpos, vpos), labels)]
    s.body = list(core)
    s.nc = set()
    s.unused = {p for p in s.pins if not net_of[p]}
    return s


# --- the router -------------------------------------------------------------------------------------------------

def cells_of(seg):
    """The cells a segment (x1, y1, x2, y2) covers, in order."""
    x1, y1, x2, y2 = (round(v / CELL) for v in seg)
    if x1 == x2:
        step = 1 if y2 >= y1 else -1
        return [(x1, y) for y in range(y1, y2 + step, step)]
    step = 1 if x2 >= x1 else -1
    return [(x, y1) for x in range(x1, x2 + step, step)]


class Router:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1   # the grid in cells, inclusive
        self.blocked = set()               # cells inside a part, and the tips of unconnected pins
        self.occ = defaultdict(dict)       # cell -> {net: H | V | X}
        self.tips = set()                  # the tips of connected pins: a path starts or ends at a lead, not there
        self.stats = {"length": 0, "bends": 0, "unrouted": 0, "paths": 0}

    def inside(self, c):
        return self.x0 <= c[0] <= self.x1 and self.y0 <= c[1] <= self.y1

    def mark(self, net, cells, ends=True):
        """A run of cells of one net; an end or a bend takes the whole cell."""
        for i, c in enumerate(cells):
            if i == 0 or i == len(cells) - 1:
                how = X if ends else (H if (i and cells[i - 1][1] == c[1]) or (not i and cells[1][1] == c[1]) else V)
            else:
                a, b = cells[i - 1], cells[i + 1]
                how = H if a[1] == b[1] else V if a[0] == b[0] else X
            had = self.occ[c].get(net)
            self.occ[c][net] = X if had and had != how else how

    def components(self, net, runs):
        """The connected pieces of a net: lists of cells, joined where runs share a cell."""
        parent = {}

        def find(c):
            while parent.setdefault(c, c) != c:
                parent[c] = parent[parent[c]]
                c = parent[c]
            return c
        for run in runs:
            for a, b in zip(run, run[1:]):
                parent[find(a)] = find(b)
            if len(run) == 1:
                find(run[0])
        groups = defaultdict(list)
        for c in parent:
            groups[find(c)].append(c)
        return list(groups.values())

    def others_at(self, c, net):
        return {n: how for n, how in self.occ.get(c, {}).items() if n != net}

    def route(self, net, sources, targets):
        """The cheapest path from any source cell to any target cell, or None (A*: the distance to the targets' box
        as the estimate)."""
        bx0, bx1 = min(c[0] for c in targets), max(c[0] for c in targets)
        by0, by1 = min(c[1] for c in targets), max(c[1] for c in targets)

        def guess(c):
            return STEP * (max(0, bx0 - c[0], c[0] - bx1) + max(0, by0 - c[1], c[1] - by1))
        heap, dist, prev = [], {}, {}
        for i, c in enumerate(sources):
            dist[(c, None)] = 0
            heapq.heappush(heap, (guess(c), i, 0, c, None))
        n = len(sources)
        while heap:
            _, _, cost, c, d = heapq.heappop(heap)
            if dist.get((c, d), math.inf) < cost:
                continue
            if c in targets and d is not None:
                path = [c]
                k = (c, d)
                while k in prev:
                    k = prev[k]
                    path.append(k[0])
                return path[::-1]
            for nd, (dx, dy) in enumerate(DIRS):
                nc = (c[0] + dx, c[1] + dy)
                if not self.inside(nc) or nc in self.blocked:
                    continue
                how = H if dy == 0 else V
                step = STEP + (TURN if d is not None and nd != d else 0)
                own = self.occ.get(nc, {}).get(net)
                if own and nc not in targets:
                    continue              # along the net's own wires: nothing to gain
                others = self.others_at(nc, net)
                if others:
                    if nc in targets or any(h == X or h == how for h in others.values()):
                        continue          # an end, a bend, a pin tip, or along another wire – and no junction there
                    step += CROSS
                for sx, sy in ((dy, dx), (-dy, -dx)):   # beside another wire of the same direction
                    side = (nc[0] + sx, nc[1] + sy)
                    if any(h == how for h in self.others_at(side, net).values()):
                        step += BESIDE
                        break
                nk = (nc, nd)
                if cost + step < dist.get(nk, math.inf):
                    dist[nk] = cost + step
                    prev[nk] = (c, d)
                    n += 1
                    heapq.heappush(heap, (cost + step + guess(nc), n, cost + step, nc, nd))
        return None

    def connect(self, net, runs):
        """Join the pieces of a net; returns the new runs (lists of cells)."""
        pieces = self.components(net, runs)
        new = []
        while len(pieces) > 1:
            pieces.sort(key=len)
            src = [c for c in pieces[0] if c not in self.tips] or pieces[0]
            targets = {c for p in pieces[1:] for c in p if not self.others_at(c, net) and c not in self.tips}
            path = self.route(net, src, targets) if targets else None
            if path is None:
                self.stats["unrouted"] += 1
                pieces = pieces[1:]      # give it up; the rest still joins
                continue
            self.mark(net, path)
            new.append(path)
            hit = next(i for i, p in enumerate(pieces) if path[-1] in p)
            pieces[hit] = pieces[hit] + src + path
            pieces = pieces[1:]
            self.stats["paths"] += 1
            self.stats["length"] += len(path) - 1
            self.stats["bends"] += bends(path)
        return new

    def undo(self, net, paths):
        """Take routed paths away again (their first cell belongs to what they started from)."""
        for path in paths:
            for c in path[1:]:
                self.occ[c].pop(net, None)
            self.stats["paths"] -= 1
            self.stats["length"] -= len(path) - 1
            self.stats["bends"] -= bends(path)


def bends(path):
    return sum(1 for a, b, c in zip(path, path[1:], path[2:]) if (a[0] == b[0]) != (b[0] == c[0]))


def polyline(cells):
    """A run of cells as the corner points of a wire, in units."""
    pts = [cells[0]]
    for a, b, c in zip(cells, cells[1:], cells[2:]):
        if (a[0] == b[0]) != (b[0] == c[0]):
            pts.append(b)
    pts.append(cells[-1])
    return [(x * CELL, y * CELL) for x, y in pts]


# --- the drawing ----------------------------------------------------------------------------------------------------

def tips(sheet, syms):
    """(cell, net, designator.pin) of every pin tip; net None for an unconnected one."""
    out = []
    for d, cx, cy, r in sheet.comps:
        for p, (lx, ly, _) in syms[d].pins.items():
            px, py = rot(lx, ly, r)
            out.append(((round((px + cx) / CELL), round((py + cy) / CELL)), f"{d}.{p}"))
    return out


def body_cells(sheet, syms):
    out = set()
    for d, cx, cy, r in sheet.comps:
        b = syms[d].body
        xs, ys = zip(rot(b[0], b[1], r), rot(b[2], b[3], r))
        x0, x1 = min(xs) + cx, max(xs) + cx
        y0, y1 = min(ys) + cy, max(ys) + cy
        for x in range(math.ceil((x0 + 1) / CELL), math.floor((x1 - 1) / CELL) + 1):
            for y in range(math.ceil((y0 + 1) / CELL), math.floor((y1 - 1) / CELL) + 1):
                out.add((x, y))
    return out


def wire_through(sheet, syms, pin_net, power, ground, labelled=frozenset()):
    """Route every net on the sheet but the labelled ones: rails for the power nets, paths for the rest. Returns the
    router."""
    b = sheet.box
    supplies = sorted((n for n in power if power[n] != "Ground"), key=lambda n: -len([p for p in pin_net.values() if p == n]))
    grounds = sorted(n for n in power if power[n] == "Ground")
    x0, x1 = math.floor(b[0] / CELL) - RAIL_OFF - 2, math.ceil(b[2] / CELL) + RAIL_OFF + 2
    y0 = math.floor(b[1] / CELL) - RAIL_OFF - RAIL_GAP * max(len(grounds), 1) - 2
    y1 = math.ceil(b[3] / CELL) + RAIL_OFF + RAIL_GAP * max(len(supplies), 1) + 2
    rt = Router(x0, y0, x1, y1)
    rt.blocked |= body_cells(sheet, syms)
    runs = defaultdict(list)
    for c, ref in tips(sheet, syms):
        net = pin_net.get(ref)
        if net:
            rt.occ[c][net] = X
            rt.tips.add(c)
            runs[net].append([c])
        else:
            rt.blocked.add(c)
    for net, segs in sheet.wires:
        for s in segs:
            cells = cells_of(s)
            rt.mark(net, cells)
            runs[net].append(cells)
    # rails: the ground below the drawing, the supplies above, each at its own height, as wide as its pins reach
    rails = {}
    for k, net in enumerate(grounds):
        rails[net] = math.floor(b[1] / CELL) - RAIL_OFF - RAIL_GAP * k
    for k, net in enumerate(supplies):
        rails[net] = math.ceil(b[3] / CELL) + RAIL_OFF + RAIL_GAP * k
    order = grounds + supplies + sorted((n for n in runs if n not in power and n not in labelled),
                                        key=lambda n: (span(runs[n]), n))
    for net in order:
        if not runs.get(net):
            continue   # a power net of another board
        if net in rails:
            xs = [c[0] for run in runs[net] for c in run]
            rail = [(x, rails[net]) for x in range(min(xs) - 1, max(xs) + 2)]
            rt.mark(net, rail)
            runs[net].append(rail)
        new = rt.connect(net, runs[net])
        if net in rails:
            on_rail = set(rail)
            drops = [path for path in new if path[-1] in on_rail]
            joined = sorted({path[-1][0] for path in drops})
            if len(joined) < 2:   # one drop or none: a rail gathers nothing here – take it away and join without it
                for c in rail:
                    rt.occ[c].pop(net, None)
                rt.undo(net, new)
                new = rt.connect(net, runs[net][:-1])
            else:
                for c in rail:   # trim the rail to what hangs on it
                    if c[0] < joined[0] or c[0] > joined[-1]:
                        del rt.occ[c][net]
                sheet.wire(net, [(joined[0] * CELL, rails[net] * CELL), (joined[-1] * CELL, rails[net] * CELL)])
        for path in new:
            sheet.wire(net, polyline(path))
    return rt


def span(runs):
    xs = [c[0] for run in runs for c in run]
    ys = [c[1] for run in runs for c in run]
    return (max(xs) - min(xs)) + (max(ys) - min(ys))


def crossings(rt):
    """(count, {net: set of nets it crosses or runs beside})."""
    conflicts = defaultdict(set)
    count = 0
    for c, nets in rt.occ.items():
        names = list(nets)
        if len(names) > 1:
            count += 1
            for a in names:
                for b in names:
                    if a != b:
                        conflicts[a].add(b)
        for net, how in nets.items():
            if how == X:
                continue
            dx, dy = (0, 1) if how == H else (1, 0)
            for other, oh in rt.occ.get((c[0] + dx, c[1] + dy), {}).items():
                if other != net and oh == how:
                    conflicts[net].add(other)
                    conflicts[other].add(net)
    return count, conflicts


def colours(nets, power, ground, conflicts):
    out = {}
    k = 0
    for net in nets:
        if net in power:
            if power[net] == "Ground":
                out[net] = GROUND_COLOUR
            else:
                out[net] = SUPPLY_COLOURS[min(k, len(SUPPLY_COLOURS) - 1)]
                k += 1
    clashes = 0
    use = defaultdict(int)
    for net in sorted((n for n in nets if n not in power), key=lambda n: (-len(conflicts.get(n, ())), n)):
        taken = {out[o] for o in conflicts.get(net, ()) if o in out}
        free = [c for c in PALETTE if c not in taken]
        if not free:
            clashes += 1
            free = sorted(PALETTE, key=lambda c: use[c])
        out[net] = free[0]
        use[free[0]] += 1
    return out, clashes


def fit_plain(sheet):
    """The drawing on a page of its own size without a frame: a margin all round, no title block."""
    b = sheet.box
    out = Drawing()
    out.place(sheet, 0, round(sd.PAGE_MARGIN - b[0]), round(sd.PAGE_MARGIN - b[1]))
    return out, (math.ceil(b[2] - b[0] + 2 * sd.PAGE_MARGIN), math.ceil(b[3] - b[1] + 2 * sd.PAGE_MARGIN))


def render(sheet, size, syms, colour, names, labelled, title_lines, frame=True):
    w, h = size
    g = Svg(w, h)
    if frame:
        g.line([(10, 10), (w - 10, 10), (w - 10, h - 10), (10, h - 10), (10, 10)], sd.COLOR["frame"], 1.5)
        tx, tw, th = w - sd.TITLE_BLOCK[0], sd.TITLE_BLOCK[0] - 10, sd.TITLE_BLOCK[1] - 10
        g.line([(tx, 10), (tx + tw, 10), (tx + tw, 10 + th), (tx, 10 + th), (tx, 10)], sd.COLOR["frame"], 1.5)
        for i, (text, size_, bold) in enumerate(title_lines):
            g.text(tx + 12, 10 + th - 22 - 18 * i - (6 if i else 0), text, size_, bold=bold)
    for x, y, content, size_, bold, align in sheet.texts:
        lines = content.split("\n")
        y0 = y - 0.8 * size_ if align == 1 else y + (len(lines) - 1) * size_
        for i, ln in enumerate(lines):
            g.text(x, y0 - i * size_, ln, size_, bold=bold, dy="0")
    tip_set = set()
    for d, cx, cy, r in sheet.comps:
        for p, (lx, ly, _) in syms[d].pins.items():
            px, py = rot(lx, ly, r)
            tip_set.add(pt(px + cx, py + cy))
    for net, segs in sheet.wires:
        for s in segs:
            g.line([s[:2], s[2:]], colour.get(net, sd.COLOR["wire"]), 1.4)
    by_net = defaultdict(list)
    for net, segs in sheet.wires:
        by_net[net] += segs
    for net, segs in by_net.items():
        for x, y in junctions(_one(net, segs), tip_set):
            g.circle(x, y, 2.4, colour.get(net, sd.COLOR["wire"]), fill=True)
    shown = Drawing()
    shown.wires = [(net, segs) for net, segs in sheet.wires if names or net in labelled]
    for x, y, net, anchor, angle in net_labels(shown, {}, tip_set):
        g.text(x, y, net, sd.NET, anchor, angle, colour.get(net, sd.COLOR["net"]))
    for d, cx, cy, r in sheet.comps:
        s = syms[d]

        def T(x, y, r=r, cx=cx, cy=cy):
            x, y = rot(x, y, r)
            return x + cx, y + cy
        unused = getattr(s, "unused", set())
        for sh in s.shapes:
            if sh[0] in ("line", "thick"):
                grey = len(sh[1]) == 2 and any(pt(*sh[1][0]) == pt(*s.pins[p][:2]) for p in unused)
                g.line([T(*q) for q in sh[1]], "#aaaaaa" if grey else sd.COLOR["part"],
                       2.4 if sh[0] == "thick" else 1.2)
            elif sh[0] == "poly":
                g.poly([T(*q) for q in sh[1]], sd.COLOR["part"], sh[2])
            else:
                g.circle(*T(sh[1], sh[2]), sh[3], sd.COLOR["part"])
        for x, y, text, size_, anchor, angle, col in s.texts:
            g.text(*T(x, y), text, size_, anchor, (angle + r) % 360, sd.COLOR[col])
        places = [place for place, _, _ in s.labels]
        if r in (180, 270):
            places.reverse()
        for (x, y, anchor), (_, text, size_) in zip(places, s.labels):
            if text:
                g.text(*T(x, y), text, size_, anchor, r, sd.COLOR["text"])
        for p in sorted(s.nc):
            x, y = T(*s.pins[p][:2])
            g.line([(x - 3, y - 3), (x + 3, y + 3)], sd.COLOR["part"])
            g.line([(x - 3, y + 3), (x + 3, y - 3)], sd.COLOR["part"])
    return g.done()


def _one(net, segs):
    d = Drawing()
    d.wires.append((net, segs))
    return d


# --- main -------------------------------------------------------------------------------------------------------

BUS = 6   # a signal net with this many pins or more stays labelled in the mixed style


def labelled_nets(design, comps, power):
    """The mixed style: a net stays a labelled stub when nothing but modules, ICs and connectors hang on it – a pin
    passed through to a header, a bus line – or when it has BUS pins or more (a key matrix, a shared line); the
    power nets are rails anyway."""
    out = set()
    for net, entry in design.nets.items():
        pins = [p for p in entry["pins"] if p.split(".", 1)[0] in comps]
        if len(pins) < 2 or net in power:
            continue
        kinds = {(design.part(p.split(".", 1)[0]) or {}).get("kind") for p in pins}
        if kinds <= {"module", "ic", "connector"} or len(pins) >= BUS:
            out.add(net)
    return out


def draw(cfg, board, names=False, gap=120, all_pins=True, mixed=False, frame=True):
    t0 = time.time()
    design = Design.from_config(cfg)
    comps = design.board_comps(board.name)
    if not comps:
        raise SystemExit(f"board {board.name} has no parts in the graph")
    syms = {}
    for d in comps:
        kind = (design.part(d) or {}).get("kind")
        syms[d] = full_symbol(design, d) if all_pins and kind == "module" else symbol(design, d)
    geo = {d: {"type": comps[d].get("type"), "pins": s.pins, "body": s.body} for d, s in syms.items()}
    lc = layout_config(cfg, design)
    if not cfg.schematic.get("layout", {}).get("power_flags"):
        lc["power"] = default_power(design)
    notes = block_notes(cfg, design, board, lc, drawn_by="wired.py (prototype)")
    seeds = seed_parts(cfg, design, comps)
    if not lc["rows"]:
        lc["rows"], graph_notes = default_rows(comps, seeds)
    if not lc["near"]:
        hosts = sorted(seeds, key=lambda d: sd.SEED_ORDER[(design.part(d) or {}).get("kind")])
        lc["near"] = default_near(design, comps, lc["power"], hosts)
    graph_nets = {n["name"]: n["pins"] for n in design.graph["nets"]}
    sl.BLOCK_GAP = sl.ROW_GAP = gap
    labelled = labelled_nets(design, comps, lc["power"]) if mixed else set()
    WiredLayout.labelled = frozenset(labelled)
    lay = WiredLayout(comps, graph_nets, geo, lc["rows"], {}, lc["power"], lc["near"], lc["stacked"], sd.CHAR_W)
    lay.ground = design.ground
    sheet = lay.build()[0]
    sheet.frames, sheet.texts = [], []
    for warning in lay.warnings:
        print(f"  ! {warning}")
    rt = wire_through(sheet, syms, lay.pin_net, lc["power"], design.ground, labelled)
    sheet, size = fit(sheet) if frame else fit_plain(sheet)
    count, conflicts = crossings(rt)
    colour, clashes = colours(list(lay.nets), lc["power"], design.ground, conflicts)
    pins = sum(len(p) for p in lay.nets.values())
    stats = dict(parts=len(comps), nets=len(lay.nets), pins=pins, wires=len(merge_wires(sheet.wires)),
                 length_m=rt.stats["length"] * CELL * sd.MM / 1000, crossings=count, bends=rt.stats["bends"],
                 unrouted=rt.stats["unrouted"], clashes=clashes, labelled=len(labelled),
                 size=f"{size[0] * sd.MM:.0f} x {size[1] * sd.MM:.0f}", seconds=time.time() - t0)
    date = design.graph.get("date", "")
    title_lines = [(board.title, 16, True), (f"{cfg.project} · board {board.name}", 8, False),
                   (f"graph v{design.version}" + (f" ({date})" if date else "") + f" · {stats['size']} mm", 8, False),
                   ("drawn by wired.py, a prototype of edakit's concept wired-schematic – change the graph, not this drawing", 7, False)]
    svg = render(sheet, size, syms, colour, names, labelled, title_lines, frame)
    return svg, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project", help="the project directory (edakit.toml)")
    ap.add_argument("--board")
    ap.add_argument("--out")
    ap.add_argument("--names", action="store_true", help="print every net's name once")
    ap.add_argument("--gap", type=int, default=120, help="room between blocks, in units of 10 mil (edakit: 60)")
    ap.add_argument("--connected-pins", action="store_true", help="modules with their connected pins only, as edakit")
    ap.add_argument("--mixed", action="store_true", help="the mixed style: bus and pass-through nets stay labelled")
    ap.add_argument("--no-frame", action="store_true", help="no sheet border and no title block")
    ap.add_argument("--row", action="store_true", help="print a Markdown table row of the measures")
    args = ap.parse_args(argv)
    cfg = config.load(str(Path(args.project) / "edakit.toml"))
    board = cfg.board(args.board)
    svg, stats = draw(cfg, board, names=args.names, gap=args.gap, all_pins=not args.connected_pins, mixed=args.mixed,
                      frame=not args.no_frame)
    out = Path(args.out) if args.out else HERE / "out" / f"{cfg.project}_{board.name}{'_mixed' if args.mixed else ''}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    s = stats
    print(f"{cfg.project}/{board.name}: {s['parts']} parts, {s['nets']} nets, {s['pins']} pin connections, "
          f"{s['wires']} wires, {s['length_m']:.2f} m of wire, {s['crossings']} crossings, {s['bends']} bends, "
          f"{s['unrouted']} unrouted, {s['clashes']} colour clashes, {s['labelled']} nets labelled, {s['size']} mm, "
          f"{s['seconds']:.1f} s -> {out}")
    if args.row:
        print(f"| {cfg.project} ({board.name}){' mixed' if args.mixed else ''} | {s['parts']} | {s['nets']} | "
              f"{s['pins']} | {s['labelled']} | {s['length_m']:.1f} | {s['crossings']} | {s['bends']} | "
              f"{s['unrouted']} | {s['clashes']} | {s['size']} | {s['seconds']:.1f} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
