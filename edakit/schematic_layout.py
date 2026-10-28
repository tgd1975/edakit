"""Arrange the readable schematic by topology and draw real wires: `edakit schematic layout`.

Meant for the board schematic (default layout_<board>). It deletes all wires, net flags, ports, rectangles and texts
of the page, moves and rotates the parts and wires everything again (what was added by hand is lost):

  - Blocks ([layout] rows of the schematic file, hardware/schematic.toml): rows -> columns -> blocks with a title
    and start parts (ICs, connectors, the MCU). Every block gets a dashed frame with its title and notes. All other
    parts attach by breadth-first search over signal nets (not over power nets and not past another start part).
  - Capacitors that touch only supply nets sit at the part named in [layout] near.
  - Every child is rotated so that its connecting pin points at the parent pin; children of one pin are stacked,
    branches of one side are spread without overlaps and without crossings.
  - Nets inside a block: one branched wire with the net name. Nets to other blocks: a labelled stub (same name =
    connected). Power nets: ground and power flags.
  - Page: the smallest landscape standard size that holds the content plus the title block.

Before writing, the plan is checked for shorts (wires of different nets touching, foreign pins, crossings with four
branches – SCH_PrimitiveWire.create fails on those). --force writes anyway. Afterwards: netlist against the graph and
ERC. If the page is board-linked, missing, extra and swapped parts are synced with the graph first (a swapped part
keeps its UniqueId and with it the link to its PCB footprint).

The symbol geometry is cached per schematic in <artifacts>/layout_geometry_<schematic>.json; --dry-run works offline
with it and writes the preview <artifacts>/layout_preview_<schematic>.svg. Coordinates: EasyEDA API, y points up on
screen; pin direction 0 = +x, 90 = +y.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from html import escape

from . import eda
from .design import Design, natural_key
from .eda import FOCUS, PROJECT, MCPError, api, batch_write, ensure_focus

PAGE_FORMATS = [("A4", 1170, 825), ("A3", 1654, 1170), ("A2", 2339, 1654), ("A1", 3311, 2339), ("A0", 4681, 3311)]
TITLE_BLOCK = (400, 130)  # room of the title block at the bottom right (width, height)
GRID = 10
GAP = 10          # between stacked children
SIDE_GAP = 2      # between branches of neighbouring pins (pin grid 10, stub 8 high)
BUS = 10          # x of the distribution wire in a branch
LEAD = 30         # x where stacked children start
MARGIN = 10       # margin around a part body (designator/value)
TREE_GAP = 80     # between trees inside a block
BLOCK_GAP = 60
ROW_GAP = 60
FRAME_PAD = 20
TITLE_H = 30
TITLE_SIZE = 16
NOTE_SIZE = 8
NOTE_CHAR_W = 0.45  # character width ≈ 0.45 x font size (measured, EasyEDA default font)
SHEET_MARGIN = 80
TITLE_MARGIN = 160
# SCH_PrimitiveText.delete and .modify are not saved in EasyEDA Pro 3.2.206: the text is gone until the page is
# reloaded and back afterwards (every run had left another layer of titles and notes). Deleted through another
# primitive class, it stays gone. So texts are never modified, only deleted this way and created anew.
TEXT_DELETE = "SCH_PrimitiveCircle.delete"


def rot(x, y, r):
    r %= 360
    if r == 0:
        return x, y
    if r == 90:
        return -y, x
    if r == 180:
        return -x, -y
    return y, -x


def box_rot(b, r):
    xs, ys = zip(rot(b[0], b[1], r), rot(b[2], b[3], r))
    return min(xs), min(ys), max(xs), max(ys)


def box_move(b, dx, dy):
    return b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy


def box_union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def box_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def snap_up(v):
    return -(-v // GRID) * GRID


class Drawing:
    """Parts, wires and flags in a local coordinate system."""

    def __init__(self):
        self.comps = []   # (designator, x, y, rotation)
        self.wires = []   # (net, [(x1, y1, x2, y2), ...])
        self.flags = []   # (net, x, y, direction the symbol points to)
        self.frames = []  # (title, box)
        self.texts = []   # (x, y, content, size, bold, alignMode) – 1 = (x, y) top left, 3 = bottom left of last line
        self.box = None

    def add_box(self, b):
        self.box = box_union(self.box, b)

    def wire(self, net, points):
        segs = [(*points[i], *points[i + 1]) for i in range(len(points) - 1) if points[i] != points[i + 1]]
        if segs:
            self.wires.append((net, segs))
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            self.add_box((min(xs), min(ys) - 4, max(xs), max(ys) + 4))

    def place(self, other, r, dx, dy):
        def t(x, y):
            x, y = rot(x, y, r)
            return x + dx, y + dy
        for d, x, y, cr in other.comps:
            self.comps.append((d, *t(x, y), (cr + r) % 360))
        for net, segs in other.wires:
            self.wires.append((net, [(*t(s[0], s[1]), *t(s[2], s[3])) for s in segs]))
        for net, x, y, fd in other.flags:
            self.flags.append((net, *t(x, y), (fd + r) % 360))
        for title, b in other.frames:
            self.frames.append((title, box_move(box_rot(b, r), dx, dy)))
        for x, y, *rest in other.texts:
            self.texts.append((*t(x, y), *rest))
        if other.box:
            self.add_box(box_move(box_rot(other.box, r), dx, dy))


def pava(targets, weights):
    """Weighted isotonic regression (non-decreasing) – pool adjacent violators."""
    blocks = []
    for t, w in zip(targets, weights):
        blocks.append([t, w, 1])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            m2, w2, n2 = blocks.pop()
            m1, w1, n1 = blocks.pop()
            blocks.append([(m1 * w1 + m2 * w2) / (w1 + w2), w1 + w2, n1 + n2])
    out = []
    for m, _, n in blocks:
        out += [m] * n
    return out


class Layout:
    def __init__(self, graph_comps, graph_nets, geometry, rows, notes, power, near, stacked=(), note_char_w=NOTE_CHAR_W):
        self.geo = geometry
        self.rows, self.notes, self.power, self.near, self.stacked = rows, notes, power, near, set(stacked)
        self.note_char_w = note_char_w  # width of a note character / font size – frames are sized with it
        self.placed = set(geometry) & set(graph_comps)
        self.nc = {d: {str(p) for p in graph_comps[d].get("nc", [])} for d in self.placed}
        self.nets = {}
        for name, pins in graph_nets.items():
            pins = [p for p in pins if p.split(".", 1)[0] in self.placed]
            if pins:
                self.nets[name] = pins
        self.pin_net = {p: name for name, pins in self.nets.items() for p in pins}
        self.kids = defaultdict(list)   # (part, pin) -> [(child, connecting pin)]
        self.blocks = []
        self.warnings = []
        self._build_trees()

    def pins_of(self, d):
        return sorted(self.geo[d]["pins"], key=lambda p: natural_key("P" + p) if p.isdigit() else natural_key(p))

    def _build_trees(self):
        seeds = [s for row in self.rows for col in row for _, roots in col for s in roots if s in self.placed]
        claimed = set(seeds)
        order = sorted(seeds, key=lambda s: self.geo[s].get("type") in ("microcontroller", "module"))  # MCU last
        for seed in order:
            q = deque([seed])
            while q:
                c = q.popleft()
                for p in self.pins_of(c):
                    net = self.pin_net.get(f"{c}.{p}")
                    if not net or net in self.power:
                        continue
                    for ref in self.nets[net]:
                        k, kp = ref.split(".", 1)
                        if k in claimed or k in self.near:
                            continue
                        claimed.add(k)
                        self.kids[(c, p)].append((k, kp))
                        q.append(k)
        for cap, host in self.near.items():
            if cap not in self.placed or host not in self.placed:
                continue
            cap_pin = next((p for p in self.pins_of(cap) if self.pin_net.get(f"{cap}.{p}") not in (None,)
                            and self.power.get(self.pin_net.get(f"{cap}.{p}")) != "Ground"), None)
            net = self.pin_net.get(f"{cap}.{cap_pin}")
            host_pin = next((p for p in self.pins_of(host) if self.pin_net.get(f"{host}.{p}") == net), None)
            if host_pin is None:
                self.warnings.append(f"{cap}: {host} has no pin on {net}")
                continue
            claimed.add(cap)
            self.kids[(host, host_pin)].append((cap, cap_pin))
        self.blocks = [[[(title, [s for s in roots if s in self.placed]) for title, roots in col
                         if title in self.notes or any(s in self.placed for s in roots)] for col in row]
                       for row in self.rows]
        rest = sorted(self.placed - claimed, key=natural_key)
        if rest:
            self.warnings.append(f"without a block (last row): {', '.join(rest)}")
            self.blocks.append([[("Other", rest)]])

    def flag_box(self, net):
        """Room of a power flag at (0, 0) pointing to +x (EasyEDA's flag symbols)."""
        return 0, -10, 25, 10

    def branch(self, d, p, net):
        """A branch starts at a pin tip (0, 0) and grows towards +x."""
        kids = self.kids.get((d, p), [])
        items = []
        if net in self.power:
            flag = Drawing()
            flag.flags.append((net, 0, 0, 0))
            flag.add_box(self.flag_box(net))
            items.append(flag)
        for k, kp in kids:
            items.append(self.node(k, kp))
        if not items:
            label = Drawing()
            length = max(30, snap_up(6 * len(net) + 10))
            label.wire(net, [(0, 0), (length, 0)])
            label.add_box((0, -4, length, 4))
            return label
        if len(items) == 1 and not kids:
            return items[0]  # flag right at the pin tip
        # Stack children vertically, the first at pin height. T junctions only: a crossing with four branches makes
        # SCH_PrimitiveWire.create fail ("create failed").
        heights = [(snap_up(-it.box[1]), snap_up(it.box[3])) for it in items]
        pos, y = [], 0
        for i, (lo, hi) in enumerate(heights):
            if i:
                y -= heights[i - 1][0] + GAP + hi
            pos.append(y)
        br = Drawing()
        stops = sorted({0, *pos})
        segs = [(BUS, a, BUS, b) for a, b in zip(stops, stops[1:])]
        br.wire(net, [(0, 0), (BUS, 0)])
        for it, py in zip(items, pos):
            shift = max(0, snap_up(-it.box[0] + GAP)) if it.box[0] < 0 else 0
            br.wire(net, [(BUS, py), (LEAD + shift, py)])
            br.place(it, 0, LEAD + shift, py)
        if segs:
            br.wires.append((net, segs))
        return br

    def node(self, d, entry):
        """Part d with its subtree. With entry, that pin's tip sits at (0, 0) and points to -x."""
        geo = self.geo[d]
        if entry:
            lx, ly, ldir = geo["pins"][entry]
            r = (180 - ldir) % 360
            ex, ey = rot(lx, ly, r)
            ox, oy = -ex, -ey
        else:
            r, ox, oy = 0, 0, 0
        dr = Drawing()
        dr.comps.append((d, ox, oy, r))
        b = geo["body"]
        dr.add_box(box_move(box_rot((b[0] - MARGIN, b[1] - MARGIN, b[2] + MARGIN, b[3] + MARGIN), r), ox, oy))
        sides = defaultdict(list)
        if entry:
            sides[180].append(((0, 0), None, None))  # keep room for the incoming wire
        for p in self.pins_of(d):
            if p == entry or p in self.nc[d]:
                continue
            net = self.pin_net.get(f"{d}.{p}")
            if net is None:
                continue
            lx, ly, ldir = geo["pins"][p]
            px, py = rot(lx, ly, r)
            sides[(ldir + r) % 360].append(((px + ox, py + oy), net, self.branch(d, p, net)))
        side_dr = {}
        for dirn in sorted(sides, key=lambda s: s % 180 != 0):  # left/right first, then top/bottom
            extra = 0
            sd = None
            for _ in range(5):
                sd = self.pack_side(sides[dirn], dirn, extra)
                hit = [o for o in side_dr.values() if o.box and sd.box and box_overlap(o.box, sd.box)]
                if not hit or dirn % 180 == 0:
                    break
                need = 0
                for o in hit:  # move a vertical side further out until it clears the horizontal ones
                    ob, sb = box_rot(o.box, -dirn), box_rot(sd.box, -dirn)
                    need = max(need, ob[2] - sb[0] + GAP)
                extra += snap_up(need)
            side_dr[dirn] = sd
        for sd in side_dr.values():
            dr.place(sd, 0, 0, 0)
        return dr

    def pack_side(self, items, dirn, extra):
        """Stack the branches of one side of a part without overlaps; result in the part's coordinate system."""
        rows = []
        for tip, net, br in items:
            tx, ty = rot(*tip, -dirn)
            lo, hi = ((-4, 4) if br is None else (min(br.box[1], -4), max(br.box[3], 4)))
            rows.append({"x": tx, "u": ty, "lo": lo, "hi": hi, "net": net, "br": br})
        rows.sort(key=lambda it: it["u"])
        c, cs = 0, []
        for i, it in enumerate(rows):
            if i:
                c += rows[i - 1]["hi"] + SIDE_GAP - it["lo"]
            cs.append(c)
        weights = [1000 if it["br"] is None else 1 for it in rows]
        q = pava([it["u"] - ci for it, ci in zip(rows, cs)], weights)
        prev_top = None
        for it, qi, ci in zip(rows, q, cs):
            s = round((qi + ci - it["u"]) / GRID) * GRID
            while prev_top is not None and it["u"] + s + it["lo"] < prev_top + SIDE_GAP:
                s += GRID
            it["s"] = s
            prev_top = it["u"] + s + it["hi"]
        fixed = next((it["s"] for it in rows if it["br"] is None), 0)
        for it in rows:
            it["s"] -= fixed
        up = sorted((it for it in rows if it["s"] > 0), key=lambda it: -it["u"])
        down = sorted((it for it in rows if it["s"] < 0), key=lambda it: it["u"])
        for group in (up, down):
            for k, it in enumerate(group):
                it["k"] = k
        jogs = max(len(up), len(down))
        x_base = max(it["x"] for it in rows)
        x0 = x_base + (GRID * (jogs + 1) if jogs else 0) + extra
        sd = Drawing()
        for it in rows:
            if it["br"] is None:
                continue
            u, s = it["u"], it["s"]
            if s:
                xj = x_base + GRID * (it["k"] + 1)
                sd.wire(it["net"], [(it["x"], u), (xj, u), (xj, u + s), (x0, u + s)])
            elif x0 > it["x"]:
                sd.wire(it["net"], [(it["x"], u), (x0, u)])
            sd.place(it["br"], 0, x0, u + s)
        out = Drawing()
        out.place(sd, dirn, 0, 0)
        return out

    def block(self, title, roots):
        """Trees side by side (top aligned) – stacked blocks one below the other – in a frame with title and notes."""
        blk = Drawing()
        x = y = 0
        for root in roots:
            t = self.node(root, None)
            if title in self.stacked:
                blk.place(t, 0, -snap_up(t.box[0]), snap_up(y - t.box[3]))
                y = blk.box[1] - TREE_GAP
            else:
                blk.place(t, 0, snap_up(x - t.box[0]), -snap_up(t.box[3]))
                x = blk.box[2] + TREE_GAP
        b = blk.box or (0, 0, 0, 0)
        lines = self.notes.get(title, [])
        note_w = max((len(ln) for ln in lines), default=0) * NOTE_SIZE * self.note_char_w
        note_h = len(lines) * NOTE_SIZE + 2 * GAP if lines else 0
        x0 = b[0] - FRAME_PAD
        x1 = max(b[2] + FRAME_PAD, x0 + len(title) * TITLE_SIZE * 0.7 + 20, x0 + 10 + note_w + 10)
        y1 = snap_up(b[3] + FRAME_PAD + note_h + TITLE_H)
        frame = (x0, b[1] - FRAME_PAD, snap_up(x1), y1)
        blk.frames.append((title, frame))
        blk.texts.append((x0 + 10, y1 - 22, title, TITLE_SIZE, True, 3))
        if lines:
            blk.texts.append((x0 + 10, y1 - TITLE_H, "\n".join(lines), NOTE_SIZE, False, 1))
        blk.add_box(frame)
        return blk

    def build(self):
        """Arrange the blocks on the page. Returns (drawing, (format, width, height))."""
        sheet = Drawing()
        top = 0
        for row in self.blocks:
            x = 0
            for col in row:
                y, right = top, x
                for title, roots in col:
                    blk = self.block(title, roots)
                    dx, dy = snap_up(x - blk.box[0]), snap_up(y - blk.box[3])
                    sheet.place(blk, 0, dx, dy)
                    y = blk.box[1] + dy - BLOCK_GAP
                    right = max(right, blk.box[2] + dx)
                if col:
                    x = right + BLOCK_GAP
            if sheet.box:
                top = sheet.box[1] - ROW_GAP
        w = sheet.box[2] - sheet.box[0] + 2 * SHEET_MARGIN
        h = sheet.box[3] - sheet.box[1] + 2 * SHEET_MARGIN
        for name, pw, ph in PAGE_FORMATS:  # smallest standard size that holds content and a free title block
            if w > pw or h > ph:
                continue
            out = Drawing()
            out.place(sheet, 0, snap_up(SHEET_MARGIN - sheet.box[0]), snap_up(ph - SHEET_MARGIN - sheet.box[3]))
            title_box = (pw - TITLE_BLOCK[0], 0, pw, TITLE_BLOCK[1])
            if not any(box_overlap(title_box, b) for _, b in out.frames):
                return out, (name, pw, ph)
        out = Drawing()
        out.place(sheet, 0, snap_up(SHEET_MARGIN - sheet.box[0]), snap_up(TITLE_MARGIN - sheet.box[1]))
        return out, ("Custom", int(snap_up(out.box[2] + SHEET_MARGIN)), int(snap_up(out.box[3] + SHEET_MARGIN)))


def merge_wires(wires):
    """Segments per net into connected groups (one EasyEDA wire per group)."""
    groups, by_net = [], defaultdict(list)
    for net, segs in wires:
        by_net[net] += segs
    for net, segs in by_net.items():
        parent = list(range(len(segs)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        at = defaultdict(list)
        for i, s in enumerate(segs):
            at[(s[0], s[1])].append(i)
            at[(s[2], s[3])].append(i)
        for idx in at.values():
            for j in idx[1:]:
                parent[find(j)] = find(idx[0])
        grouped = defaultdict(list)
        for i, s in enumerate(segs):
            grouped[find(i)].append(s)
        groups += [(net, g) for g in grouped.values()]
    return groups


def on_segment(x, y, s):
    x1, y1, x2, y2 = s
    if x1 == x2 == x:
        return min(y1, y2) <= y <= max(y1, y2)
    if y1 == y2 == y:
        return min(x1, x2) <= x <= max(x1, x2)
    return False


def collinear_overlap(a, b):
    if a[0] == a[2] == b[0] == b[2]:
        return min(max(a[1], a[3]), max(b[1], b[3])) > max(min(a[1], a[3]), min(b[1], b[3]))
    if a[1] == a[3] == b[1] == b[3]:
        return min(max(a[0], a[2]), max(b[0], b[2])) > max(min(a[0], a[2]), min(b[0], b[2]))
    return False


def check_geometry(sheet, geo, pin_net):
    """Shorts in the plan: wires of different nets touching or overlapping, wires on foreign pins, 4-way crossings."""
    problems = []
    segs = [(net, s) for net, ss in sheet.wires for s in ss]
    points = []
    for d, x, y, r in sheet.comps:
        for p, (lx, ly, _) in geo[d]["pins"].items():
            px, py = rot(lx, ly, r)
            points.append((pin_net.get(f"{d}.{p}"), px + x, py + y, f"{d}.{p}"))
    points += [(net, x, y, f"flag {net}") for net, x, y, _ in sheet.flags]
    for i, (na, a) in enumerate(segs):
        for nb, b in segs[i + 1:]:
            if na == nb:
                continue
            if collinear_overlap(a, b) or any(on_segment(x, y, b) for x, y in (a[:2], a[2:])) \
                    or any(on_segment(x, y, a) for x, y in (b[:2], b[2:])):
                problems.append(f"wire {na} {a} touches {nb} {b}")
        for net, x, y, what in points:
            if net != na and on_segment(x, y, a):
                problems.append(f"wire {na} {a} touches {what} ({net})")
    for net, ss in merge_wires(sheet.wires):
        ends = defaultdict(int)
        for sg in ss:
            ends[sg[:2]] += 1
            ends[sg[2:]] += 1
        for pt, n in ends.items():
            if n > 3:
                problems.append(f"wire {net}: crossing with {n} branches at {pt}")
    return problems


def layout_config(cfg, design):
    lay = cfg.schematic.get("layout", {})
    rows = [[[(b["title"], list(b.get("start", []))) for b in col] for col in row] for row in lay.get("rows", [])]
    power = lay.get("power_flags") or {design.ground: "Ground"}
    return {"rows": rows, "notes": {k: list(v) for k, v in lay.get("notes", {}).items()}, "power": power,
            "near": dict(lay.get("near", {})), "stacked": lay.get("stacked", []), "pin_table": lay.get("pin_table")}


def block_notes(cfg, design, board, lc, drawn_by="edakit schematic layout"):
    """Notes from the schematic file – their quoted values filled in (edakit docs) – plus a GPIO table from the graph
    and the open 'verify' notes."""
    notes = {k: list(v) for k, v in lc["notes"].items()}
    comps = design.board_comps(board.name)
    pt = lc.get("pin_table")
    if pt and pt["component"] in comps:
        mcu, prefix, block = pt["component"], pt.get("prefix", "GP"), pt.get("block", "MCU")
        rows, spare = [], []
        for pin, name in comps[mcu]["pins"].items():
            net = design.pin_net.get(f"{mcu}.{pin}")
            m = re.match(re.escape(prefix) + r"(\d+)", name)
            if m and net and net not in lc["power"]:
                rows.append((int(m.group(1)), f"{prefix}{m.group(1)}", net))
            elif m and not net:
                spare.append(f"{prefix}{m.group(1)}")
        lines = notes.setdefault(block, [])
        lines.append(f"Spare: {', '.join(sorted(spare, key=natural_key)) or '–'}")
        lines += ["", f"{prefix.upper()}  net  function"]
        lines += [f"{gp}  {net}  {pt.get('notes', {}).get(net, '')}".rstrip() for _, gp, net in sorted(rows)]
    verify = [d for d in sorted(comps, key=natural_key) if comps[d].get("verify")]
    target = "Notes" if "Notes" in notes or any(t == "Notes" for row in lc["rows"] for col in row for t, _ in col) \
        else None
    if target:
        notes.setdefault("Notes", [])
        if verify:
            notes["Notes"].append(f"Before layout, check pin numbers/polarity against the footprint: {', '.join(verify)}.")
        notes["Notes"] += [f"Source: {cfg.graph.name} v{design.version} ({design.graph.get('date', '')})",
                           f"Drawn by {drawn_by} – change the graph, not this sheet."]
    from . import docs
    return docs.fill_notes(cfg, design, notes)   # {graph:…}, {part:…}, {sim:…} quoted from the design data


def sync_parts(cfg, mcp, graph_comps):
    """Sync the parts on the page with the graph (the board schematic cannot be regenerated). Missing ones are placed
    (device by LCSC number as in `create`), extra ones deleted, swapped ones (other LCSC number) replaced – keeping the
    UniqueId of the old one, so it stays linked to its PCB part. Brand-new parts get their UniqueId from
    `edakit pcb parts --write`."""
    from .schematic import resolve_devices
    on_sheet = {c["reference"]: c for c in eda.list_sheet_parts(mcp)
                if c.get("component_kind", "part") == "part" and c.get("reference")}
    missing = sorted(set(graph_comps) - set(on_sheet), key=natural_key)
    extra = sorted(set(on_sheet) - set(graph_comps), key=natural_key)
    swapped = sorted((d for d in set(graph_comps) & set(on_sheet)
                      if graph_comps[d].get("lcsc") and graph_comps[d]["lcsc"] != on_sheet[d].get("lcsc")),
                     key=natural_key)
    for title, refs in (("missing", missing), ("not in the graph", extra), ("swapped (LCSC)", swapped)):
        if refs:
            print(f"  {title}: {', '.join(refs)}")
    if not (missing or extra or swapped):
        print(f"  {len(on_sheet)} parts as in the graph")
        sync_bom(mcp, graph_comps)
        return 0
    uids = {}
    for d in swapped:
        st = eda.state(api(mcp, "SCH_PrimitiveComponent.get", on_sheet[d]["primitiveId"]) or {})
        uids[d] = st.get("UniqueId") or ""
    gone = [on_sheet[d]["primitiveId"] for d in extra + swapped]
    if gone:
        ensure_focus(mcp)
        api(mcp, "SCH_PrimitiveComponent.delete", gone)
    new = {d: graph_comps[d] for d in missing + swapped}
    if new:
        devices = resolve_devices(cfg, mcp, new)
        ops = []
        for i, d in enumerate(sorted(new, key=natural_key)):
            key = new[d].get("lcsc") or f"dev:{d}"
            if key not in devices:
                raise MCPError(f"{d}: no device found for {key}")
            ops.append({"operationId": f"place-{d}", "action": "create", "primitiveKind": "component",
                        "deviceItem": devices[key], "x": 100 + 60 * (i % 10), "y": 100 + 60 * (i // 10),
                        "addIntoBom": new[d].get("bom", True) if not new[d].get("lcsc") else True})
        ids = batch_write(mcp, ops)
        batch_write(mcp, [{"operationId": f"ref-{d}", "action": "modify", "primitiveId": ids[f"place-{d}"],
                           "property": {"designator": d}} for d in new if ids.get(f"place-{d}")])
        for d, uid in uids.items():
            if uid and ids.get(f"place-{d}"):
                api(mcp, "SCH_PrimitiveComponent.modify", ids[f"place-{d}"], {"uniqueId": uid})
        print(f"  placed: {', '.join(d for d in sorted(new, key=natural_key) if ids.get(f'place-{d}'))}")
    sync_bom(mcp, graph_comps)
    return len(missing) + len(extra) + len(swapped)


def sync_bom(mcp, graph_comps):
    """'In BOM' as in the graph: parts with "bom": false (hand-soldered) belong on the PCB, not into the BOM."""
    changed = []
    for c in eda.list_sheet_parts(mcp):
        d = c.get("reference")
        if d not in graph_comps:
            continue
        want = graph_comps[d].get("bom", True) is not False
        st = eda.state(api(mcp, "SCH_PrimitiveComponent.get", c["primitiveId"]) or {})
        if bool(st.get("AddIntoBom", True)) != want:
            ensure_focus(mcp)
            api(mcp, "SCH_PrimitiveComponent.modify", c["primitiveId"], {"addIntoBom": want})
            changed.append(d)
    print(f"  'in BOM' changed: {', '.join(changed)}" if changed else "  'in BOM' as in the graph")


def sync_nc(mcp, graph_comps):
    """No-connect markers as in the graph: set where missing, remove where the pin has a net now."""
    changed = []
    for c in eda.list_sheet_parts(mcp):
        d = c.get("reference")
        if d not in graph_comps:
            continue
        want = {str(p) for p in graph_comps[d].get("nc", [])}
        for pin in mcp.call("easyeda_schematic_component_pins", primitiveId=c["primitiveId"]).get("pins", []):
            num = str(pin["pinNumber"])
            if bool(pin.get("noConnected")) != (num in want):
                mcp.call("easyeda_schematic_set_pin_no_connect", projectId=PROJECT, primitiveId=c["primitiveId"],
                         pinNumber=num, noConnected=num in want, confirmWrite=True)
                changed.append(f"{d}.{num}")
    print(f"  no-connect changed: {', '.join(changed)}" if changed else "  no-connect as in the graph")
    return len(changed)


def read_geometry(mcp, graph_comps):
    comps = [c for c in eda.list_sheet_parts(mcp) if c.get("reference") in graph_comps]
    bounds = {}
    for i in range(0, len(comps), 50):
        ids = [c["primitiveId"] for c in comps[i:i + 50]]
        for item in mcp.call("easyeda_schematic_primitive_bounds", projectId=PROJECT, primitiveIds=ids)["items"]:
            bounds[item["id"]] = item["body"]["bounds"]
    geo, symbol_pins = {}, {}  # pin positions relative to the origin are the same per part number – read once
    for c in comps:
        if c.get("mirror"):
            raise MCPError(f"{c['reference']} is mirrored – not supported")
        ox, oy, r = c["x"], c["y"], c.get("rotation", 0) or 0
        key = graph_comps[c["reference"]].get("lcsc") or c["reference"]
        if key not in symbol_pins:
            symbol_pins[key] = {}
            for pin in mcp.call("easyeda_schematic_component_pins", primitiveId=c["primitiveId"])["pins"]:
                lx, ly = rot(pin["x"] - ox, pin["y"] - oy, -r)
                symbol_pins[key][str(pin["pinNumber"])] = [lx, ly, (pin["rotation"] - r) % 360]
        b = bounds[c["primitiveId"]]
        body = box_rot(box_move((b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"]), -ox, -oy), -r)
        geo[c["reference"]] = {"id": c["primitiveId"], "type": graph_comps[c["reference"]].get("type"),
                               "pins": {p: list(v) for p, v in symbol_pins[key].items()}, "body": list(body)}
    return geo


def flag_rotation(kind, direction):
    # Empirical (EasyEDA Pro 3.2.206): ground points to -y at 0, power to +y; both rotate the other way round.
    return (270 - direction) % 360 if kind == "Ground" else (90 - direction) % 360


def clear_sheet(mcp):
    wires = api(mcp, "SCH_PrimitiveWire.getAllPrimitiveId") or []
    if wires:
        api(mcp, "SCH_PrimitiveWire.delete", wires)
    parts = {c["primitiveId"] for c in eda.list_sheet_parts(mcp)}
    others = [i for i in api(mcp, "SCH_PrimitiveComponent.getAllPrimitiveId") or [] if i not in parts]
    flags = []
    if others:
        flags = [c["primitiveId"] for c in api(mcp, "SCH_PrimitiveComponent.get", others) or []
                 if c.get("componentType") in ("netflag", "netport")]
    if flags:
        api(mcp, "SCH_PrimitiveComponent.delete", flags)
    drawn = 0
    for cls, delete in (("SCH_PrimitiveRectangle", "SCH_PrimitiveRectangle.delete"), ("SCH_PrimitiveText", TEXT_DELETE)):
        ids = api(mcp, f"{cls}.getAllPrimitiveId") or []
        for i in range(0, len(ids), 200):
            api(mcp, delete, ids[i:i + 200])
        drawn += len(ids)
        left = api(mcp, f"{cls}.getAllPrimitiveId") or []
        if left:
            raise MCPError(f"{cls}: {len(left)} of {len(ids)} not deleted")
    orphans = clear_orphan_attributes(mcp)
    print(f"  deleted {len(wires)} wires, {len(flags)} flags/ports, {drawn} frames/texts, {orphans} orphan attributes")


def clear_orphan_attributes(mcp):
    """Attribute texts whose part is gone. Deleting a part or a net flag through the API leaves its attributes
    (designator, name, pin texts) on the page as loose texts. Parent id of a pin attribute is '<part>-e<n>'."""
    comps = set(api(mcp, "SCH_PrimitiveComponent.getAllPrimitiveId") or [])
    comps |= set(api(mcp, "SCH_PrimitiveWire.getAllPrimitiveId") or [])
    ids = api(mcp, "SCH_PrimitiveAttribute.getAllPrimitiveId") or []
    attrs = []
    for i in range(0, len(ids), 200):
        attrs += api(mcp, "SCH_PrimitiveAttribute.get", ids[i:i + 200]) or []
    orphan = [a["primitiveId"] for a in attrs
              if a.get("parentPrimitiveId") and a["parentPrimitiveId"].split("-")[0] not in comps]
    for i in range(0, len(orphan), 200):
        api(mcp, "SCH_PrimitiveAttribute.delete", orphan[i:i + 200])
    return len(orphan)


APPLY_PHASES = 6   # page and title block … wires


def apply(cfg, mcp, geo, sheet, page_format, board, version, power, phase=None):
    """Write the plan; returns the wires EasyEDA could not create. phase: the eda.Progress of `schematic layout`."""
    phase = phase or eda.Progress()
    phase("page and title block")
    name, w, h = page_format
    eda.label_sheet(mcp, cfg, FOCUS["page"], board.title, version, {"Page Size": name, "Width": w, "Height": h})
    print(f"  {name} landscape, {w} x {h}, page '{board.title}', graph v{version}")
    phase("clear the page")
    clear_sheet(mcp)
    phase("move parts")
    now = {c["primitiveId"]: (c["x"], c["y"], (c.get("rotation") or 0) % 360) for c in eda.list_sheet_parts(mcp)}
    # batch_write gives the same geometry as single calls (modify, flags in all rotations, rectangle anchor top left,
    # text alignment). Not for wires: a new piece touching one of the same net merges with it and the batch rolls
    # back – so wires go one by one.
    moves = [{"operationId": f"move-{d}", "action": "modify", "primitiveId": geo[d]["id"],
              "property": {"x": x, "y": y, "rotation": r}} for d, x, y, r in sheet.comps
             if now.get(geo[d]["id"]) != (x, y, r)]
    if moves:
        batch_write(mcp, moves)
    print(f"  {len(moves)} parts")
    phase("flags")
    if sheet.flags:
        batch_write(mcp, [{"operationId": f"flag-{i}", "action": "create", "primitiveKind": "netflag",
                           "identification": power[net], "netName": net, "x": x, "y": y,
                           "rotation": flag_rotation(power[net], fd)} for i, (net, x, y, fd) in enumerate(sheet.flags)])
    print(f"  {len(sheet.flags)} flags")
    phase("block frames and notes")
    ops = [{"operationId": f"frame-{i}", "action": "create", "primitiveKind": "rectangle", "x": x0, "y": y1,
            "width": x1 - x0, "height": y1 - y0, "color": "#808080", "lineWidth": 1, "lineType": 1}
           for i, (_, (x0, y0, x1, y1)) in enumerate(sheet.frames)]
    ops += [{"operationId": f"text-{i}", "action": "create", "primitiveKind": "text", "x": x, "y": y,
             "content": content, "fontSize": size, "bold": bool(bold), "alignMode": align, "rotation": 0}
            for i, (x, y, content, size, bold, align) in enumerate(sheet.texts) if content]
    if ops:
        batch_write(mcp, ops)
    print(f"  {len(sheet.frames)} blocks, {len(sheet.texts)} texts")
    phase("wires")
    groups = merge_wires(sheet.wires)
    failed = []
    for n, (net, segs) in enumerate(groups, 1):
        if n % 20 == 1:
            ensure_focus(mcp)
        try:
            api(mcp, "SCH_PrimitiveWire.create", [list(s) for s in segs], net)
        except MCPError as e:
            failed.append((net, segs))
            print(f"  ! {net}: {e} {segs[:3]}")
        if n % 50 == 0:
            print(f"  {n}/{len(groups)}")
    print(f"  {len(groups) - len(failed)}/{len(groups)} wires")
    phase(None)
    return failed


def write_svg(path, geo, sheet):
    b = sheet.box
    pad = 40
    w, h = b[2] - b[0] + 2 * pad, b[3] - b[1] + 2 * pad

    def X(x):
        return x - b[0] + pad

    def Y(y):
        return b[3] - y + pad
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
           'font-family="sans-serif">', f'<rect width="{w}" height="{h}" fill="white"/>']
    for _, (x0, y0, x1, y1) in sheet.frames:
        out.append(f'<rect x="{X(x0)}" y="{Y(y1)}" width="{x1 - x0}" height="{y1 - y0}" fill="none" stroke="#888" '
                   'stroke-dasharray="6 4"/>')
    for x, y, content, size, bold, align in sheet.texts:
        lines = content.split("\n")
        y = y - 0.8 * size if align == 1 else y + (len(lines) - 1) * size
        spans = "".join(f'<tspan x="{X(x)}" dy="{size if i else 0}">{escape(ln)}</tspan>' for i, ln in enumerate(lines))
        weight = ' font-weight="bold"' if bold else ""
        out.append(f'<text x="{X(x)}" y="{Y(y)}" font-size="{size}"{weight} xml:space="preserve">{spans}</text>')
    for d, x, y, r in sheet.comps:
        bb = box_move(box_rot(geo[d]["body"], r), x, y)
        out.append(f'<rect x="{X(bb[0])}" y="{Y(bb[3])}" width="{bb[2] - bb[0]}" height="{bb[3] - bb[1]}" '
                   'fill="#fff6d0" stroke="#a00" stroke-width="1"/>')
        for lx, ly, _ in geo[d]["pins"].values():
            px, py = rot(lx, ly, r)
            out.append(f'<circle cx="{X(px + x)}" cy="{Y(py + y)}" r="1.5" fill="#a00"/>')
        out.append(f'<text x="{X(bb[0])}" y="{Y(bb[3]) - 2}" font-size="7" fill="#008">{d}</text>')
    for _, segs in sheet.wires:
        for s in segs:
            out.append(f'<line x1="{X(s[0])}" y1="{Y(s[1])}" x2="{X(s[2])}" y2="{Y(s[3])}" stroke="#080" '
                       'stroke-width="1"/>')
    for net, segs in merge_wires(sheet.wires):
        s = max(segs, key=lambda s: abs(s[2] - s[0]) + abs(s[3] - s[1]))
        out.append(f'<text x="{X((s[0] + s[2]) / 2)}" y="{Y((s[1] + s[3]) / 2) - 2}" font-size="5" fill="#00c" '
                   f'text-anchor="middle">{escape(net)}</text>')
    for net, x, y, fd in sheet.flags:
        dx, dy = rot(12, 0, fd)
        out.append(f'<line x1="{X(x)}" y1="{Y(y)}" x2="{X(x + dx)}" y2="{Y(y + dy)}" stroke="#a00"/>')
        out.append(f'<text x="{X(x + dx)}" y="{Y(y + dy) + 2}" font-size="5" fill="#a00">{escape(net)}</text>')
    out.append("</svg>")
    path.write_text("\n".join(out), encoding="utf-8")


def main(cfg, args):
    board = cfg.board(args.board, made=True)
    name = args.schematic or board.schematic
    if name == board.template and not args.dry_run:
        return eda.die(f"{name} is the template – copy it first (edakit schematic copy)")
    design = Design.from_config(cfg)
    graph_comps = design.board_comps(board.name)
    graph_nets = {n["name"]: n["pins"] for n in design.graph["nets"]}
    lc = layout_config(cfg, design)
    if not lc["rows"]:
        return eda.die(f"{cfg.relative(cfg.schematic_file)} has no [layout] rows – define the blocks first "
                       "(handbook/06-schematic.md)")
    cache = cfg.artifact(f"layout_geometry_{name}.json")
    mcp = None
    need_eda = not args.dry_run or args.reread or not cache.exists()
    # bridge and project, sync, symbol geometry, plan; writing: the phases of apply, netlist, ERC, save
    phase = eda.Progress(need_eda + (need_eda and not args.dry_run) + 2
                         + (0 if args.dry_run else APPLY_PHASES + 2 + bool(args.save)))
    try:
        if need_eda:
            phase("bridge and project")
            mcp = eda.start(cfg, args.verbose)
            if not eda.wait_for_bridge(mcp, args.wait):
                return 1
            eda.open_project(mcp, cfg)
            if name == board.schematic and not args.dry_run:
                eda.ensure_board(mcp, board)
            sch_uuid, pages = eda.find_pages(mcp, name)
            if len(pages) != 1:
                raise MCPError(f"'{name}' has {len(pages)} pages – only one is supported")
            eda.focus_page(mcp, sch_uuid, pages[0])
            if not args.dry_run:
                phase("sync parts with the graph")
                sync_parts(cfg, mcp, graph_comps)
                sync_nc(mcp, graph_comps)
        if args.reread or not cache.exists():
            phase("read symbol geometry")
            geo = read_geometry(mcp, graph_comps)
            cache.write_text(json.dumps(geo, indent=1) + "\n", encoding="utf-8")
        else:
            phase("symbol geometry from the cache")
            geo = json.loads(cache.read_text(encoding="utf-8"))
            if mcp:  # primitive ids belong to the page – the cache must match it
                ids = {c["primitiveId"] for c in eda.list_sheet_parts(mcp)}
                if not {g["id"] for g in geo.values()} <= ids or set(graph_comps) - set(geo):
                    print("  the cache does not match the page – reading the symbol geometry again")
                    geo = read_geometry(mcp, graph_comps)
                    cache.write_text(json.dumps(geo, indent=1) + "\n", encoding="utf-8")
        phase("plan and preview")
        lay = Layout(graph_comps, graph_nets, geo, lc["rows"], block_notes(cfg, design, board, lc), lc["power"],
                     lc["near"], lc["stacked"])
        sheet, page_format = lay.build()
        for w in lay.warnings:
            print(f"  ! {w}")
        b = sheet.box
        print(f"plan: {len(sheet.comps)} parts, {len(merge_wires(sheet.wires))} wires, {len(sheet.flags)} flags, area "
              f"{b[2] - b[0]:.0f} x {b[3] - b[1]:.0f}, page {page_format[0]} ({page_format[1]} x {page_format[2]})")
        preview = cfg.artifact(f"layout_preview_{name}.svg")
        write_svg(preview, geo, sheet)
        cfg.artifact(f"layout_plan_{name}.json").write_text(json.dumps(
            {"comps": sheet.comps, "flags": sheet.flags, "wires": merge_wires(sheet.wires)}, indent=1) + "\n")
        print(f"  preview -> {preview}")
        problems = check_geometry(sheet, geo, lay.pin_net)
        for prob in problems:
            print(f"  ! {prob}")
        if problems and not args.force:
            print(f"{len(problems)} geometry conflicts – nothing written (--force writes anyway)")
            return 2
        if args.dry_run:
            phase(None)
            return 0
        failed = apply(cfg, mcp, geo, sheet, page_format, board, design.version, lc["power"], phase)
        phase("netlist against the graph")
        diffs = eda.verify_nets(mcp, lay.nets, {d: {"ref": d} for d in lay.placed})
        phase("ERC")
        erc = mcp.call("easyeda_erc_run", projectId=PROJECT, scope="focused")
        print("  " + json.dumps({k: v for k, v in erc.items() if not isinstance(v, (list, dict))}, ensure_ascii=False))
        if args.save:   # --force wrote despite geometry conflicts; the save still needs a matching netlist
            phase("save")
            eda.save_if_matching(mcp, diffs, len(failed))
        phase(None)
        return 0 if not (diffs or failed) else 2
    except MCPError as e:
        return eda.die(str(e))
    finally:
        if mcp:
            mcp.close()
