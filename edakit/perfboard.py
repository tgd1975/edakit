"""Perfboard: the build plan of a hand-wired board on a perfboard, as text in its board file, checked against the graph
and drawn (handbook 7.9, concept docs/concepts/new/perfboard-layout.md).

    edakit perfboard [--board B]    offline: the plan of a board with wired = true and [perfboard] in its board file –
                                    the nets the plan makes against the graph's (PERF.net), the places, the grid, the
                                    bodies, the mounting holes, the wires, the current (PERF.*) and the hand-over
                                    (SYNC.plan); the top view, the bottom view in the orientation of the top view, and
                                    the cut list at 1:1, the cut, build and test lists -> <artifacts>/perfboard/<board>/

The plan, in the board file (hardware/boards/<board>.toml) of a board with wired = true:

    [perfboard]  kind = "pad-per-hole" | "3-hole-strips" (edakit/perfboards/<kind>.toml), holes = [columns, rows],
                 cut_step_mm (optional: the cut list's step, default the kind's)
    [[holes]]    mounting holes in mm, x right and y up from the board's lower left corner seen from the top: x, y, d,
                 keep (the diameter kept free around it, default the nut of its screw)
    [place]      designator = { at = "P9", rot = 270 } – the hole of pin 1, counterclockwise seen from the top in steps
                 of 90°, span = n for an axial part's lead span in holes – or { anode = "L3", cathode = "L2" }: a part
                 with two leads by the holes of its roles
    [[wire]]     net, path = ["N16", "AF16"], side = "bottom" (a straight row of bridges of bare wire between
                 neighbouring holes, the default) or "top" (an insulated wire: its ends and the bends between them),
                 color
    [near], near_mm, edge_mm, edge_ok – the hand-over, as on a PCB

Holes are named by column letter and row number, A1 at the top left seen from the top, as many Euro boards print
them. Board coordinates here: mm, x to the right and y down from the top left corner seen from the top, the corner
half a pitch outside the outer holes.
"""

from __future__ import annotations

import html
import json
import math
import re
import tomllib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import catalog
from .config import MIL_PER_MM, ConfigError
from .design import Design, natural_key
from .findings import Finding, accept_reason

KINDS = Path(__file__).resolve().parent / "perfboards"
PLAN_KEYS = ("revision", "perfboard", "holes", "place", "wire", "near", "near_mm", "edge_mm", "edge_ok")
PERFBOARD_KEYS = ("kind", "holes", "cut_step_mm")
HOLE_KEYS = ("x", "y", "d", "keep")
WIRE_KEYS = ("net", "path", "side", "color")
PLACE_KEYS = ("at", "rot", "span")
NUT_PER_D = 1.875      # the diameter kept free around a mounting hole, per drill: an M3 nut is 6.01 mm across its
                       # corners (ISO 4032, e min), 1.875 x 3.2 mm = 6.0 mm
HEADER_MM = 2.54       # a socket of a plugged-in module: one pitch square around each of its pins
RAISED_KINDS = ("module",)   # on sockets, raised: wires on top may run under it, a part under it is a note (decision 19)
SNAP_MM = 0.05         # a pad this close to its hole counts as on the grid
OVERLAP_EPS = 0.05     # boxes that only touch do not overlap
LEAD_SHRINK = 0.3      # a lead lies under a body only this far inside the body's box
NEAR_MM = 6.0
EDGE_MM = 1.0

NET_PALETTE = ("#1f77b4", "#2ca02c", "#8e5bc9", "#f28e2b", "#17a2b8", "#b0124d", "#a0671a", "#1b7f6f", "#b08d00",
               "#e377c2", "#7f7f7f", "#bcbd22", "#4b3fa0", "#6fbf3a", "#c4572b", "#3a8fd6", "#9c3d8a", "#5a6b2a")
GROUND_COLOUR, SUPPLY_COLOUR = "#2b2b2b", "#d62728"
WIRE_COLOURS = {"orange": "#f28e2b", "violet": "#8e5bc9", "red": "#d62728", "black": "#2b2b2b", "blue": "#1f77b4",
                "green": "#2ca02c", "yellow": "#e6c200", "white": "#f4f4f4", "brown": "#8c564b", "grey": "#8a8a8a",
                "gray": "#8a8a8a"}
LED_FILL = {"red": "#e0302f", "yellow": "#f2c200", "green": "#36b04a", "blue": "#2f6fe0", "white": "#f4f4f4",
            "orange": "#f28e2b"}
SUPPLY = re.compile(r"^(\+|V(CC|DD|BUS|IN|BAT)|\d+V\d*$)", re.I)
POLAR = ("anode", "cathode", "plus", "minus")
ORDER = [("resistor", "Resistors, lying flat"), ("wire", "Insulated wires on top – each end through its hole and "
         "bent onto the pad of the lead beside it"), ("socket", "Sockets"), ("button", "Buttons"),
         ("other", "Other parts"), ("connector", "Connectors"), ("diode", "Diodes"), ("led", "LEDs"),
         ("capacitor", "Capacitors"), ("bridge", "Bare wire on the bottom, once the leads are in – laid over the "
         "pads, soldered at each"), ("test", "Test"), ("plug", "Modules")]


class PlanError(ConfigError):
    """A board file whose plan is not well-formed."""


# --- the kinds ------------------------------------------------------------------------------------------------------

def kind_names():
    return sorted(p.stem for p in KINDS.glob("*.toml"))


def kind_problems(data):
    """What a kind's data lacks or gets wrong."""
    out = []
    for key in ("name", "pitch_mm", "hole_mm", "pad_mm", "groups", "sources"):
        if key not in data:
            out.append(f"{key} missing")
    for key in ("pitch_mm", "hole_mm", "pad_mm"):
        if key in data and not (isinstance(data[key], (int, float)) and data[key] > 0):
            out.append(f"{key} must be a length in mm > 0")
    g = data.get("groups")
    if g is not None and g != "none" and not (isinstance(g, dict) and g.get("along") in ("row", "column")
                                              and isinstance(g.get("length"), int) and g["length"] >= 0):
        out.append('groups must be "none" or { along = "row" | "column", length = n } (0: the whole row or column)')
    tol = data.get("tolerance", {})
    for key in ("lead_bend_mm", "axial_bend_mm"):
        if not isinstance(tol.get(key), (int, float)) or tol[key] < 0:
            out.append(f"tolerance.{key} must be a length in mm >= 0")
    copper = data.get("copper", {})
    if copper.get("max_a", 0) and not copper.get("source"):
        out.append("copper.max_a without its source – a current only with its source, never a guess")
    for key in ("strip_mm", "slack_mm", "bridge_end_mm", "step_mm"):
        if not isinstance(data.get("wires", {}).get(key), (int, float)):
            out.append(f"wires.{key} must be a length in mm")
    if not data.get("sources"):
        out.append("sources: where pitch, hole and copper come from")
    return out


def load_kind(name):
    f = KINDS / f"{name}.toml"
    if not f.is_file():
        raise PlanError(f"perfboard kind {name!r} is not in edakit/perfboards (known: {', '.join(kind_names())})")
    data = tomllib.loads(f.read_text(encoding="utf-8"))
    if bad := kind_problems(data):
        raise PlanError(f"edakit/perfboards/{name}.toml: " + "; ".join(bad))
    return data


# --- holes ----------------------------------------------------------------------------------------------------------

HOLE = re.compile(r"([A-Z]+)(\d+)")


def col_name(c):
    s = ""
    c += 1
    while c:
        c, r = divmod(c - 1, 26)
        s = chr(65 + r) + s
    return s


def parse_hole(name):
    """'AG16' -> (32, 16): column from 0, row from 1."""
    m = HOLE.fullmatch(str(name))
    if not m:
        raise PlanError(f"{name!r} is not a hole – a column letter and a row number as the board prints them, e.g. "
                        "'P9' or 'AG16'")
    col = 0
    for ch in m.group(1):
        col = col * 26 + (ord(ch) - 64)
    return col - 1, int(m.group(2))


def hole_name(h):
    return f"{col_name(h[0])}{h[1]}"


def rot(p, deg):
    """A point turned counterclockwise as seen from the top, in board coordinates (y down)."""
    x, y = p
    return {0: (x, y), 90: (y, -x), 180: (-x, -y), 270: (-y, x)}[deg % 360]


# --- the plan -------------------------------------------------------------------------------------------------------

@dataclass
class Plan:
    kind_name: str
    kind: dict
    cols: int
    rows: int
    mounts: list                      # [{"x", "y", "d", "keep"}] as written: mm, y up from the lower left corner
    place: dict                       # designator -> spec as written
    wires: list                       # [{"net", "path", "side", "color"}]
    near: dict = field(default_factory=dict)
    near_mm: float = NEAR_MM
    edge_mm: float = EDGE_MM
    edge_ok: set = field(default_factory=set)
    cut_step_mm: float | None = None

    @property
    def pitch(self):
        return self.kind["pitch_mm"]

    def centre(self, h):
        return (h[0] + 0.5) * self.pitch, (h[1] - 0.5) * self.pitch

    def on_board(self, h):
        return 0 <= h[0] < self.cols and 1 <= h[1] <= self.rows

    def size_mm(self):
        return self.cols * self.pitch, self.rows * self.pitch

    def mount_points(self):
        """The mounting holes in board coordinates: [(name, x, y down, d, keep)]."""
        return [(f"{m['x']:g}/{m['y']:g}", m["x"], self.rows * self.pitch - m["y"], m["d"], m["keep"])
                for m in self.mounts]

    def group_of(self, h):
        """The copper group a hole belongs to: None on a pad per hole."""
        g = self.kind["groups"]
        if g == "none":
            return None
        c, r = h
        if g["along"] == "row":
            return ("row", r, c // g["length"] if g["length"] else 0)
        return ("column", c, (r - 1) // g["length"] if g["length"] else 0)

    def group_holes(self, key):
        g = self.kind["groups"]
        along, line, n = key
        length = g["length"] or (self.cols if along == "row" else self.rows)
        if along == "row":
            return [(c, line) for c in range(n * length, (n + 1) * length) if c < self.cols]
        return [(line, r) for r in range(n * length + 1, (n + 1) * length + 1) if r <= self.rows]


def _num(where, v, positive=True):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 or (positive and v == 0):
        raise PlanError(f"{where} must be a number{' > 0' if positive else ' >= 0'}, not {v!r}")
    return float(v)


def is_plan(raw):
    return "perfboard" in (raw or {})


def read_plan(raw, where):
    """The plan of a board file (raw TOML) – PlanError where it is not well-formed."""
    if bad := [k for k in raw if k not in PLAN_KEYS]:
        raise PlanError(f"{where}: unknown key{'s' if len(bad) > 1 else ''} {', '.join(bad)} on a perfboard (known: "
                        f"{', '.join(PLAN_KEYS)})")
    pb = raw.get("perfboard")
    if not isinstance(pb, dict):
        raise PlanError(f"{where}: [perfboard] must be a table with kind and holes")
    if bad := [k for k in pb if k not in PERFBOARD_KEYS]:
        raise PlanError(f"{where}: [perfboard] unknown key {', '.join(bad)} (known: {', '.join(PERFBOARD_KEYS)})")
    if "kind" not in pb:
        raise PlanError(f"{where}: [perfboard] kind missing – one of {', '.join(kind_names())}")
    kind = load_kind(pb["kind"])
    size = pb.get("holes")
    if not (isinstance(size, list) and len(size) == 2 and all(isinstance(v, int) and not isinstance(v, bool) and v > 0
                                                                for v in size)):
        raise PlanError(f"{where}: [perfboard] holes = [columns, rows], the piece of the board used, e.g. [33, 22]")
    mounts = []
    for i, h in enumerate(raw.get("holes", [])):
        w = f"{where}: holes[{i}]"
        if not isinstance(h, dict) or "x" not in h or "y" not in h:
            raise PlanError(f"{w} needs x and y in mm, y up from the board's lower left corner seen from the top")
        if bad := [k for k in h if k not in HOLE_KEYS]:
            raise PlanError(f"{w}: unknown key {', '.join(bad)} (known: {', '.join(HOLE_KEYS)})")
        d = _num(f"{w}.d", h.get("d", 3.2))
        mounts.append({"x": _num(f"{w}.x", h["x"], False), "y": _num(f"{w}.y", h["y"], False), "d": d,
                       "keep": _num(f"{w}.keep", h.get("keep", round(NUT_PER_D * d, 2)))})
    place = raw.get("place", {})
    if not isinstance(place, dict):
        raise PlanError(f"{where}: [place] is a table of designator = {{ at = \"P9\", rot = 270 }}")
    for d, spec in place.items():
        if not isinstance(spec, dict):
            raise PlanError(f"{where}: place.{d} must be {{ at = \"P9\", rot = 270 }} or {{ anode = \"L3\", "
                            "cathode = \"L2\" }")
        if "at" in spec:
            parse_hole(spec["at"])
            if bad := [k for k in spec if k not in PLACE_KEYS]:
                raise PlanError(f"{where}: place.{d}: unknown key {', '.join(bad)} beside at (known: "
                                f"{', '.join(PLACE_KEYS)})")
            if spec.get("rot", 0) not in (0, 90, 180, 270):
                raise PlanError(f"{where}: place.{d}.rot must be 0, 90, 180 or 270, not {spec['rot']!r}")
        else:
            for k, v in spec.items():
                if k == "span":
                    continue
                if k == "rot":
                    raise PlanError(f"{where}: place.{d}: rot belongs to a part placed with at – by role edakit "
                                    "derives it")
                parse_hole(v)
        if "span" in spec and not (isinstance(spec["span"], int) and not isinstance(spec["span"], bool)
                                   and spec["span"] > 0):
            raise PlanError(f"{where}: place.{d}.span is the lead span in holes, a whole number > 0")
    wires = []
    for i, w in enumerate(raw.get("wire", [])):
        at = f"{where}: wire[{i}]"
        if not isinstance(w, dict) or "net" not in w or "path" not in w:
            raise PlanError(f"{at} needs net and path")
        if bad := [k for k in w if k not in WIRE_KEYS]:
            raise PlanError(f"{at}: unknown key {', '.join(bad)} (known: {', '.join(WIRE_KEYS)})")
        if not (isinstance(w["path"], list) and len(w["path"]) >= 2):
            raise PlanError(f"{at}: path is a list of at least two holes")
        for h in w["path"]:
            parse_hole(h)
        if w.get("side", "bottom") not in ("top", "bottom"):
            raise PlanError(f"{at}: side must be 'bottom' (bridges of bare wire) or 'top' (an insulated wire)")
        wires.append({"net": str(w["net"]), "path": list(w["path"]), "side": w.get("side", "bottom"),
                      "color": w.get("color")})
    near = raw.get("near", {})
    return Plan(kind_name=pb["kind"], kind=kind, cols=size[0], rows=size[1], mounts=mounts, place=dict(place),
                wires=wires, near={k: [v] if isinstance(v, str) else list(v) for k, v in near.items()},
                near_mm=_num(f"{where}: near_mm", raw.get("near_mm", NEAR_MM)),
                edge_mm=_num(f"{where}: edge_mm", raw.get("edge_mm", EDGE_MM), False),
                edge_ok=set(raw.get("edge_ok", [])),
                cut_step_mm=_num(f"{where}: cut_step_mm", pb["cut_step_mm"]) if "cut_step_mm" in pb else None)


def board_plan(cfg, board):
    """The plan of a hand-wired board, None for a board without one."""
    if not board.wired:
        return None
    f = cfg.resolve(board.file or f"hardware/boards/{board.name}.toml")
    if not f.is_file():
        return None
    raw = tomllib.loads(f.read_text(encoding="utf-8"))
    return read_plan(raw, cfg.relative(f)) if is_plan(raw) else None


def plan_boards(cfg):
    """{name: (board, plan)} of every board with a perfboard plan."""
    out = {}
    for name, b in cfg.boards.items():
        if (p := board_plan(cfg, b)) is not None:
            out[name] = (b, p)
    return out


# --- footprints -----------------------------------------------------------------------------------------------------

AXIAL_NAME = re.compile(r"-L(\d+(?:\.\d+)?)")      # EasyEDA's axial footprints: RES-TH_BD2.5-L6.5-P10.50-D0.6
AXIAL_DIA = re.compile(r"_BD(\d+(?:\.\d+)?)")
RADIAL = re.compile(r"-TH_BD(\d+(?:\.\d+)?)")     # a round body: LED-TH_BD5.0-P2.54-FD, CAP-TH_BD10.0-P5.00


def to_board(x_mil, y_mil):
    """A point of the footprint geometry (mil, y up) in board orientation (mm, y down)."""
    return x_mil / MIL_PER_MM, -y_mil / MIL_PER_MM


def box_of(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def axial_body(entry, geo):
    """(length, diameter) in mm of an axial part's body: its body.box, else the footprint's name (-L6.5, _BD2.5);
    None without either."""
    box = ((entry.get("body") or {}).get("box"))
    if isinstance(box, list) and len(box) == 4:
        w, h = abs(box[2] - box[0]), abs(box[3] - box[1])
        return max(w, h), min(w, h)
    name = geo.get("footprint") or entry.get("footprint") or ""
    if (m := AXIAL_NAME.search(name)) and (n := AXIAL_DIA.search(name)):
        return float(m.group(1)), float(n.group(1))
    return None


class Part:
    """A placed part: its holes, the bend of its leads into the grid, its bodies on the board."""

    def __init__(self, d, spec, entry, geo, plan):
        self.d, self.entry, self.geo, self.plan = d, entry, geo, plan
        self.kind = entry.get("kind", "")
        self.problems = []           # (code, grade, text)
        pitch = plan.pitch
        pads = {n: to_board(p["x"], p["y"]) for n, p in geo["pads"].items() if not p.get("mechanical")}
        self.smd = sorted((n for n, p in geo["pads"].items() if not p.get("tht") and not p.get("hole")
                           and not p.get("mechanical")), key=natural_key)
        first = "1" if "1" in pads else min(pads, key=natural_key)
        ox, oy = pads[first]
        local = {n: (x - ox, y - oy) for n, (x, y) in pads.items()}
        self.first = first
        self.by_role = None
        self.span = spec.get("span")
        if "at" not in spec:                   # by role (decision 14)
            roles = {}
            for n, pin in (entry.get("pins") or {}).items():
                if pin.get("role"):
                    roles.setdefault(pin["role"], n)
            given = {roles[r]: parse_hole(h) for r, h in spec.items() if r != "span" and r in roles}
            unknown = [r for r in spec if r != "span" and r not in roles]
            if unknown or len(given) != 2 or len(local) != 2:
                self.problems.append(("PERF.place", "role", f"{d}: placed by the holes of {', '.join(spec)}, but its "
                                      f"{len(local)} leads have the roles {', '.join(sorted(roles)) or 'none'} – by "
                                      "role takes a part with two leads and their two roles"))
                given = given or {first: (0, 1)}
            self.by_role = given
            a = given.get(first) or next(iter(given.values()))
            other = next((n for n in given if n != first), None)
            r = 0
            if other is not None and other in local:
                hd = (given[other][0] - a[0], given[other][1] - a[1])
                want = (int(math.copysign(1, hd[0])) if hd[0] else 0, int(math.copysign(1, hd[1])) if hd[1] else 0)
                fd = local[other]
                for cand in (0, 90, 180, 270):
                    v = rot(fd, cand)
                    got = tuple(int(math.copysign(1, c)) if round(c / pitch) else 0 for c in v)
                    if got == want:
                        r = cand
                        break
            anchor_hole, self.rot = a, r
        else:
            anchor_hole, self.rot = parse_hole(spec["at"]), spec.get("rot", 0)
        self.anchor = anchor_hole
        self.axial = None
        if self.span is not None:
            if len(local) != 2:
                self.problems.append(("PERF.place", "span", f"{d}: span is for a part with two leads, it has "
                                      f"{len(local)}"))
            else:
                other = next(n for n in local if n != first)
                fd = local[other]
                ln = math.hypot(*fd) or 1.0
                local[other] = (fd[0] / ln * self.span * pitch, fd[1] / ln * self.span * pitch)
                self.axial = axial_body(entry, geo)
        self.local = local
        exact = {n: rot(p, self.rot) for n, p in local.items()}
        grid = {n: (round(x / pitch), round(y / pitch)) for n, (x, y) in exact.items()}
        self.holes = {n: (self.anchor[0] + g[0], self.anchor[1] + g[1]) for n, g in grid.items()}
        k = len(exact)
        cx, cy = sum(x for x, _ in exact.values()) / k, sum(y for _, y in exact.values()) / k
        gx, gy = sum(g[0] for g in grid.values()) * pitch / k, sum(g[1] for g in grid.values()) * pitch / k
        self.bend = max(math.hypot((x - cx) - (grid[n][0] * pitch - gx), (y - cy) - (grid[n][1] * pitch - gy))
                        for n, (x, y) in exact.items())
        if self.by_role and not self.problems:
            off = [n for n, h in self.by_role.items() if self.holes.get(n) != h]
            if off:
                pins = entry.get("pins") or {}
                self.problems.append(("PERF.place", "role", f"{d}: its leads lie " + ", ".join(
                    f"{pins.get(n, {}).get('role', n)} in {hole_name(self.holes[n])}" for n in self.by_role)
                    + " – not in the holes the plan names, " + ", ".join(
                    f"{pins.get(n, {}).get('role', n)} in {hole_name(h)}" for n, h in self.by_role.items())))
        # the board position of the footprint's pad 1 – the footprint centred on its holes
        px, py = plan.centre(self.anchor)
        self.origin = (px + (gx - cx), py + (gy - cy))
        self.pad1_mil = geo["pads"][first]

    def place(self, p):
        x, y = rot(p, self.rot)
        return self.origin[0] + x, self.origin[1] + y

    def _box(self, local_box):
        x0, y0, x1, y1 = local_box
        return box_of([self.place(c) for c in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))])

    def _local(self, mm_box_up):
        """A box in footprint mm (y up, relative to the origin) relative to pad 1 in board orientation."""
        ox, oy = to_board(self.pad1_mil["x"], self.pad1_mil["y"])
        x0, y0, x1, y1 = mm_box_up
        return box_of([(x - ox, -y - oy) for x, y in ((x0, y0), (x1, y1))])

    def bodies(self):
        """The part's bodies on the board, as boxes – a round one too, by its bounding box (round() has the circle)."""
        return [shape_box(s) for s in self.shapes()]

    def shapes(self):
        """The part's bodies on the board: ("rect", box) or ("circle", (x, y), d) – an axial part's body between its
        leads, a module's sockets, a radial part's round body (_BD in its footprint's name), body.box, else the
        footprint's box."""
        if self.axial:
            length, dia = self.axial
            (ax, ay), (bx, by) = (self.local[n] for n in sorted(self.local, key=natural_key))
            mx, my = (ax + bx) / 2, (ay + by) / 2
            horizontal = abs(bx - ax) >= abs(by - ay)
            w, h = (length, dia) if horizontal else (dia, length)
            return [("rect", self._box((mx - w / 2, my - h / 2, mx + w / 2, my + h / 2)))]
        if self.raised:
            return [("rect", self._box((x - HEADER_MM / 2, y - HEADER_MM / 2, x + HEADER_MM / 2, y + HEADER_MM / 2)))
                    for x, y in self.local.values()]
        box = (self.entry.get("body") or {}).get("box")
        if isinstance(box, list) and len(box) == 4:
            return [("rect", self._box(self._local(box)))]
        name = self.geo.get("footprint") or self.entry.get("footprint") or ""
        if (m := RADIAL.search(name)) and not AXIAL_NAME.search(name):
            pts = [self.place(p) for p in self.local.values()]
            return [("circle", (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts)),
                     float(m.group(1)))]
        x0, y0, x1, y1 = self.geo["bbox"]
        return [("rect", self._box(self._local((x0 / MIL_PER_MM, y0 / MIL_PER_MM, x1 / MIL_PER_MM,
                                                y1 / MIL_PER_MM))))]

    @property
    def raised(self):
        return self.kind in RAISED_KINDS

    def raised_box(self):
        x0, y0, x1, y1 = self.geo["bbox"]
        return self._box(self._local((x0 / MIL_PER_MM, y0 / MIL_PER_MM, x1 / MIL_PER_MM, y1 / MIL_PER_MM)))

    def box(self):
        """The bounding box of the part's bodies – what near and edge measure, as on a PCB."""
        bs = self.bodies() + ([self.raised_box()] if self.raised else [])
        return min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)


def shape_box(s):
    if s[0] == "rect":
        return s[1]
    (x, y), d = s[1], s[2]
    return x - d / 2, y - d / 2, x + d / 2, y + d / 2


def shapes_overlap(a, b):
    """Whether two bodies overlap: boxes, circles, or one of each."""
    if a[0] == "rect" and b[0] == "rect":
        return overlap(a[1], b[1])
    if a[0] == "circle" and b[0] == "circle":
        return math.dist(a[1], b[1]) < a[2] / 2 + b[2] / 2 - OVERLAP_EPS
    c, r = (a, b) if a[0] == "circle" else (b, a)
    return circle_box(*c[1], c[2], r[1])


def in_shape(pt, s, shrink=LEAD_SHRINK):
    if s[0] == "rect":
        return inside(pt, s[1], shrink)
    return math.dist(pt, s[1]) < s[2] / 2 - shrink


def overlap(a, b, eps=OVERLAP_EPS):
    return a[0] < b[2] - eps and b[0] < a[2] - eps and a[1] < b[3] - eps and b[1] < a[3] - eps


def inside(pt, b, shrink=LEAD_SHRINK):
    return b[0] + shrink < pt[0] < b[2] - shrink and b[1] + shrink < pt[1] < b[3] - shrink


def box_gap(a, b):
    return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3], 0)


def circle_box(cx, cy, d, b):
    """Whether a circle of diameter d reaches into box b."""
    nx, ny = min(max(cx, b[0]), b[2]), min(max(cy, b[1]), b[3])
    return math.dist((cx, cy), (nx, ny)) < d / 2 - OVERLAP_EPS


# --- the check ------------------------------------------------------------------------------------------------------

class UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def expand(path):
    """The holes a row of bridges touches, one per step; the steps that leave their row or column."""
    pts = [parse_hole(h) for h in path]
    holes, bad = [pts[0]], []
    for (c1, r1), (c2, r2) in zip(pts, pts[1:]):
        if c1 != c2 and r1 != r2:
            bad.append(f"{hole_name((c1, r1))}–{hole_name((c2, r2))}")
            holes.append((c2, r2))
            continue
        n = max(abs(c2 - c1), abs(r2 - r1))
        for i in range(1, n + 1):
            holes.append((c1 + (c2 - c1) * i // n, r1 + (r2 - r1) * i // n))
    return holes, bad


def joined_pins(entry):
    """Pins a part joins inside (decision 18): the groups of its key `joined`, and a button's pins that share a role."""
    groups = [[str(n) for n in g] for g in (entry.get("joined") or []) if isinstance(g, list)]
    if entry.get("kind") == "button":
        by = defaultdict(list)
        for n, p in (entry.get("pins") or {}).items():
            if p.get("role"):
                by[p["role"]].append(n)
        groups += [g for g in by.values() if len(g) > 1]
    return groups


def joined_problems(entry):
    j = entry.get("joined")
    if j is None:
        return []
    pins = set(entry.get("pins") or {})
    if not (isinstance(j, list) and all(isinstance(g, list) and len(g) >= 2 for g in j)):
        return ['joined must be a list of pin groups, e.g. [["4", "29"]]']
    return [f"joined names pin {n}, which the entry does not have" for g in j for n in g if str(n) not in pins]


def pin_label(entry, n):
    """A pin as the builder knows it: anode/cathode, plus/minus by role, else the entry's name."""
    p = (entry.get("pins") or {}).get(n, {})
    return p["role"] if p.get("role") in POLAR else p.get("name", n)


@dataclass
class Result:
    plan: Plan
    findings: list
    placed: dict
    wires: list
    pin_at: dict
    net_of: dict
    uf: UF
    ufb: UF
    bottom_at: dict
    keep: dict
    design: Design
    board: object


class Check:
    def __init__(self, cfg, board, plan, design, geo, currents=None):
        self.cfg, self.board, self.plan, self.design, self.geo = cfg, board, plan, design, geo
        self.currents = currents
        self.findings = []

    def f(self, code, grade, text, part=None):
        sev = catalog.default_severity(code, grade)
        reason = accept_reason(self.design.comps[part], code, grade=grade) if part in self.design.comps else ""
        place = part or text.split(":")[0].split()[0]
        fd = Finding(code, "L", place, text, grade=grade, severity=sev, accepted=reason or "")
        self.findings.append(fd)

    def run(self):
        plan, design = self.plan, self.design
        comps = design.board_comps(self.board.name)
        placed = {}
        for d, spec in plan.place.items():
            if d not in comps:
                where = (f"on board {design.comps[d].get('board')}" if d in design.comps else "not in the graph")
                self.f("PERF.place", "unknown", f"{d}: in the plan of {self.board.name}, but {where}")
                continue
            entry = design.part(d)
            geo = self.geo.get(d)
            if not entry or not geo or not geo.get("pads"):
                self.f("PERF.place", "geometry", f"{d}: no footprint geometry – footprint_data in its parts entry, "
                       "edakit part import for the library's, or a <board>.geometry.json beside the board file", d)
                continue
            p = Part(d, spec, entry, geo, plan)
            for code, grade, text in p.problems:
                self.f(code, grade, text, d)
            placed[d] = p
            for problem in joined_problems(entry):
                self.f("PERF.net", "joined", f"{d}: {problem}", d)
        for d in sorted(comps, key=natural_key):
            if d not in plan.place:
                self.f("PERF.place", "unplaced", f"{d}: on board {self.board.name}, but the plan has no place for it",
                       d)
        pin_at = {}
        for d, p in placed.items():
            for n, h in p.holes.items():
                if not plan.on_board(h):
                    self.f("PERF.place", "offboard", f"{d}.{n}: would sit in {hole_name(h)}, off the board's "
                           f"{plan.cols} × {plan.rows} holes", d)
                if h in pin_at:
                    self.f("PERF.place", "two", f"{hole_name(h)}: holds {pin_at[h]} and {d}.{n} – one lead per hole", d)
                pin_at[h] = f"{d}.{n}"
        keep = self.mounting(placed, pin_at)
        self.grid_and_bodies(placed, pin_at)
        wires, uf, ufb, bottom_at = self.wiring(placed, pin_at, keep)
        net_of = self.nets(placed, pin_at, wires, uf, ufb)
        self.handover(placed)
        self.current(wires)
        return Result(plan, self.findings, placed, wires, pin_at, net_of, uf, ufb, bottom_at, keep, design,
                      self.board)

    # mounting holes, in mm as on a PCB (decision 15): the pads under the nut stay free
    def mounting(self, placed, pin_at):
        plan, keep = self.plan, {}
        w, h = plan.size_mm()
        for m, cx, cy, d, k in plan.mount_points():
            if not (d / 2 < cx < w - d / 2 and d / 2 < cy < h - d / 2):
                self.f("PERF.mount", "", f"mounting hole {m}: lies off the board ({w:.1f} × {h:.1f} mm)")
            for c in range(plan.cols):
                for r in range(1, plan.rows + 1):
                    if math.dist(plan.centre((c, r)), (cx, cy)) < k / 2 + plan.kind["pad_mm"] / 2:
                        keep[(c, r)] = m
            for dd, p in placed.items():
                if any(shapes_overlap(("circle", (cx, cy), k), sh) for sh in p.shapes()):
                    self.f("PERF.mount", "", f"{dd}: its body reaches into the nut of mounting hole {m} ({k:g} mm)",
                           dd)
        for hh, who in pin_at.items():
            if hh in keep:
                self.f("PERF.mount", "", f"{who}: in {hole_name(hh)}, under the nut of mounting hole {keep[hh]}",
                       who.split(".")[0])
        return keep

    def grid_and_bodies(self, placed, pin_at):
        tol = self.plan.kind["tolerance"]
        pitch = self.plan.pitch
        for d, p in placed.items():
            if p.smd:
                self.f("PERF.grid", "smd", f"{d}: SMD pads {', '.join(p.smd)} – a perfboard takes through-hole parts "
                       "only (decision 3); a through-hole part in a variant of its own", d)
            if p.axial is not None or p.span is not None:
                if p.axial is None:
                    self.f("PERF.body", "span", f"{d}: span {p.span} without the body's length – body.box in its "
                           "parts entry", d)
                else:
                    length = p.axial[0]
                    need = length + 2 * tol["axial_bend_mm"]
                    if p.span * pitch < need - 1e-6:
                        self.f("PERF.body", "span", f"{d}: span {p.span} holes = {p.span * pitch:.2f} mm, its body "
                               f"of {length:g} mm and the bends need {need:.1f} mm", d)
            elif p.bend > tol["lead_bend_mm"]:
                self.f("PERF.grid", "", f"{d}: leads {p.bend:.2f} mm off the {pitch} mm grid, more than the "
                       f"{tol['lead_bend_mm']} mm a lead is bent", d)
            elif p.bend > SNAP_MM:
                self.f("PERF.grid", "bent", f"{d}: leads bent by {p.bend:.2f} mm into the {pitch} mm grid (allowed "
                       f"{tol['lead_bend_mm']} mm)", d)
        ds = sorted(placed, key=natural_key)
        for i, a in enumerate(ds):
            for b in ds[i + 1:]:
                if any(shapes_overlap(x, y) for x in placed[a].shapes() for y in placed[b].shapes()):
                    self.f("PERF.body", "", f"{a}: its body and that of {b} overlap", a)
        for h, who in pin_at.items():
            for d in self.under_body(placed, h, who.split(".")[0]):
                self.f("PERF.body", "", f"{d}: its body covers the lead {who} in {hole_name(h)}", d)
        for d, p in placed.items():         # a part under a module on sockets: a note (decision 19)
            if p.raised:
                rb = p.raised_box()
                for e, q in placed.items():
                    if e != d and not q.raised and any(shapes_overlap(("rect", rb), sh) for sh in q.shapes()):
                        self.f("PERF.body", "under", f"{e}: sits under {d}, which is plugged in on sockets", e)

    def under_body(self, placed, h, own=None):
        pt = self.plan.centre(h)
        return [d for d, p in placed.items() if d != own and any(in_shape(pt, s) for s in p.shapes())]

    def wiring(self, placed, pin_at, keep):
        plan = self.plan
        uf, ufb, bottom_at, wires = UF(), UF(), {}, []
        for i, w in enumerate(plan.wires):
            bridge = w["side"] == "bottom"
            if bridge:
                holes, bad = expand(w["path"])
                for seg in bad:
                    self.f("PERF.wire", "", f"{w['net']}: the bridges {seg} do not run along a row or a column – on "
                           "the bottom only bridges between neighbouring holes; a longer way is a wire on top")
            else:
                holes = [parse_hole(w["path"][0]), parse_hole(w["path"][-1])]
            for h in holes:
                if not plan.on_board(h):
                    self.f("PERF.place", "offboard", f"{w['net']}: {hole_name(h)} is off the board")
                if h in keep:
                    self.f("PERF.mount", "", f"{w['net']}: {hole_name(h)} is under the nut of mounting hole {keep[h]}")
                uf.union(("w", i), ("h", h))
                ufb.union(("w", i), ("h", h))
            if not bridge:
                for h in holes:
                    if h in pin_at:
                        self.f("PERF.wire", "end", f"{w['net']}: the wire ends in {hole_name(h)}, where {pin_at[h]} "
                               "is – it goes into a free hole beside it, joined by a bridge (decision 17)")
                    for d in self.under_body(placed, h):
                        if not placed[d].raised:
                            self.f("PERF.wire", "end", f"{w['net']}: the wire's end in {hole_name(h)} lies under {d}")
            else:
                for h in holes:
                    bottom_at.setdefault(h, w["net"])
            wires.append({**w, "kind": "bridge" if bridge else "wire", "holes": holes})
        # bridges run straight: no corner within a row of bridges, none where two rows end in the same empty hole
        ends, middles = defaultdict(set), set()
        wire_ends = {h for w in wires if w["kind"] == "wire" for h in w["holes"]}
        for w in wires:
            if w["kind"] != "bridge":
                continue
            pts = [parse_hole(h) for h in w["path"]]
            axes = ["row" if a[1] == b[1] else "column" for a, b in zip(pts, pts[1:])]
            corners = [hole_name(pts[i + 1]) for i in range(len(axes) - 1) if axes[i] != axes[i + 1]]
            if corners:
                self.f("PERF.wire", "corner", f"{w['net']}: the bridges {' … '.join(w['path'])} turn at "
                       f"{', '.join(corners)} – bridges run straight; a wire on top turns")
            ends[w["holes"][0]].add(axes[0])
            ends[w["holes"][-1]].add(axes[-1])
            middles.update(w["holes"][1:-1])
        for h, axes in ends.items():
            if len(axes) > 1 and h not in pin_at and h not in wire_ends and h not in middles:
                self.f("PERF.wire", "corner", f"{hole_name(h)}: bridges turn at this empty hole – they meet at a lead "
                       "or in the middle of another row (decision 16)")
        return wires, uf, ufb, bottom_at

    def nets(self, placed, pin_at, wires, uf, ufb):
        plan, design = self.plan, self.design
        net_of = {}
        for ref, net in design.pin_net.items():
            d, _, n = ref.partition(".")
            if d in placed:
                net_of[(d, n)] = net
        for d, p in placed.items():         # a free pin the part joins inside to a pin of a net is on that net
            for g in joined_pins(p.entry):
                g = [n for n in g if n in p.holes]
                nets = {net_of[(d, n)] for n in g if (d, n) in net_of}
                if len(nets) == 1:
                    for n in g:
                        net_of.setdefault((d, n), next(iter(nets)))
        groups = set()
        for d, p in placed.items():
            for n, h in p.holes.items():
                uf.union(("p", d, n), ("h", h))
                ufb.union(("p", d, n), ("h", h))
            for g in joined_pins(p.entry):
                g = [n for n in g if n in p.holes]
                for n in g[1:]:
                    uf.union(("p", d, g[0]), ("p", d, n))
                    if not p.raised:
                        ufb.union(("p", d, g[0]), ("p", d, n))
        touched = set(pin_at) | {h for w in wires for h in w["holes"]}
        for h in touched:
            if (key := plan.group_of(h)) is not None:
                groups.add(key)
        for key in groups:
            hs = plan.group_holes(key)
            for h in hs[1:]:
                uf.union(("h", hs[0]), ("h", h))
                ufb.union(("h", hs[0]), ("h", h))
        comp_nets, net_comps = defaultdict(set), defaultdict(set)
        comp_pins = defaultdict(lambda: defaultdict(list))
        for d, p in placed.items():
            for n in p.holes:
                root = uf.find(("p", d, n))
                net = net_of.get((d, n)) or f"(free {d}.{pin_label(p.entry, n)})"
                comp_nets[root].add(net)
                net_comps[net].add(root)
                comp_pins[root][net].append(f"{d}.{pin_label(p.entry, n)} in {hole_name(p.holes[n])}")

        def pins(ps):
            return f"{len(ps)} pins" if len(ps) > 3 else ", ".join(sorted(ps, key=natural_key))

        for root, nets in comp_nets.items():
            real = sorted(n for n in nets if not n.startswith("(free"))
            if len(nets) > 1 and real:
                self.f("PERF.net", "short", f"{real[0]}: " + " and ".join(
                    f"{net} ({pins(comp_pins[root][net])})" for net in sorted(nets)) + " in one piece of copper")
        board_nets = {n for n in set(net_of.values())}
        for net in sorted(board_nets):
            if len(net_comps[net]) > 1:
                self.f("PERF.net", "open", f"{net}: open between " +
                       " | ".join(sorted(pins(comp_pins[root][net]) for root in net_comps[net])))
        for i, w in enumerate(wires):
            nets = {n for n in comp_nets.get(uf.find(("w", i)), set()) if not n.startswith("(free")}
            if nets and w["net"] not in nets:
                self.f("PERF.net", "label", f"{w['net']}: the {'bridges' if w['kind'] == 'bridge' else 'wire'} "
                       f"{' '.join(w['path'])} joins {', '.join(sorted(nets))}, not {w['net']}")
        # where two nets meet: a hole – or a strip – whose bridges, wire ends and leads belong to different nets
        meet = defaultdict(list)
        for w in wires:
            if w["kind"] == "bridge":
                what = ("bridge " + "–".join(w["path"])) if len(w["holes"]) == 2 else "bridges " + " … ".join(w["path"])
            else:
                what = f"wire {w['path'][0]}–{w['path'][-1]}"
            for h in w["holes"]:
                meet[h].append((w["net"], f"{w['net']} {what}"))
        for h, who in pin_at.items():
            d, n = who.split(".", 1)
            if (d, n) in net_of:
                meet[h].append((net_of[(d, n)], f"{d}.{pin_label(placed[d].entry, n)} ({net_of[(d, n)]})"))
        by_place = defaultdict(list)
        for h, items in meet.items():
            key = plan.group_of(h)
            if key is None:
                by_place[(h[1], h[0], hole_name(h))] += items
            else:
                hs = plan.group_holes(key)
                by_place[(hs[0][1], hs[0][0], f"strip {hole_name(hs[0])}–{hole_name(hs[-1])}")] += items
        for (_, _, name), items in sorted(by_place.items()):
            if len({net for net, _ in items}) > 1:
                self.f("PERF.net", "meet", f"{name}: joins " + " with ".join(dict.fromkeys(t for _, t in items)))
        for net in sorted(board_nets):          # nets a plugged-in module joins inside (decision 19)
            if len(net_comps[net]) == 1:
                roots = defaultdict(list)
                for (d, n), nn in net_of.items():
                    if nn == net and d in placed:
                        roots[ufb.find(("p", d, n))].append((d, n))
                if len(roots) > 1:
                    main = max(roots.values(), key=len)
                    for members in roots.values():
                        if members is not main:
                            self.f("PERF.net", "inside", f"{net}: " + ", ".join(sorted(
                                f"{d}.{pin_label(placed[d].entry, n)} in {hole_name(placed[d].holes[n])}"
                                for d, n in members)) + f" join{'s' if len(members) == 1 else ''} the rest only inside "
                                "the plugged-in module – the test list measures them apart")
        return net_of

    def handover(self, placed):
        """SYNC.plan: fixed, edge and near hold as on a PCB (decision 20) – the gap between the bodies' boxes."""
        from shapely.geometry import box as sbox

        from . import handover
        plan, design = self.plan, self.design
        boxes = {d: p.box() for d, p in placed.items()}
        w, h = plan.size_mm()
        edge = sbox(0, 0, w, h).exterior
        where = f"{self.board.file or 'the board file'} [place]"
        for r in handover.requirements(design, self.board.name):
            if r.part not in plan.place:
                continue        # PERF.place names it
            if r.kind == "edge" and r.part in boxes:
                dist = sbox(*boxes[r.part]).distance(edge)
                if dist > plan.edge_mm:
                    self.f("SYNC.plan", "", f"{r.part}: {dist:.1f} mm from the board edge – the circuit wants it at "
                           f"the edge (edge_mm {plan.edge_mm:g})", r.part)
            elif r.kind == "near":
                for host in r.others:
                    if host not in plan.place:
                        self.f("SYNC.plan", "", f"{host}: not in {where} – {r.part} must sit next to it", r.part)
                    elif r.part in boxes and host in boxes and box_gap(boxes[r.part], boxes[host]) > plan.near_mm:
                        self.f("SYNC.plan", "", f"{r.part}: {box_gap(boxes[r.part], boxes[host]):.1f} mm from "
                               f"{host} – the circuit wants it next to it (near_mm {plan.near_mm:g})", r.part)
            elif r.kind == "decoupling" and r.part in boxes:
                if not any(c in boxes and box_gap(boxes[c], boxes[r.part]) <= plan.near_mm for c in r.others):
                    self.f("SYNC.plan", "", f"{r.part}: no capacitor of its own from {r.net} to {design.ground} "
                           f"within {plan.near_mm:g} mm – place {' or '.join(r.others)} next to it", r.part)
        for a, hosts in plan.near.items():
            for b in hosts:
                if a in boxes and b in boxes and (gap := box_gap(boxes[a], boxes[b])) > plan.near_mm:
                    self.f("SYNC.plan", "", f"{a}: {gap:.1f} mm from {b}, more than near_mm {plan.near_mm:g}", a)

    def current(self, wires):
        """PERF.current: a bridge or a wire carries its net's current – from the simulation – against the copper's
        rating of the kind's data; without a rating with its source a note names the currents."""
        if not self.currents:
            return
        rating = self.plan.kind.get("copper", {}).get("max_a") or 0
        carried = {}
        for w in wires:
            i = (self.currents.get(w["net"]) or {}).get("i_max_a")
            if i:
                carried[w["net"]] = max(carried.get(w["net"], 0), i)
        if not carried:
            return
        if not rating:
            top = sorted(carried.items(), key=lambda kv: -kv[1])[:3]
            self.f("PERF.current", "unknown", f"{self.plan.kind_name}: no current rating with its source in the kind's "
                   "data – the wires carry up to " + ", ".join(f"{n} {i:.2f} A" for n, i in top))
            return
        for net, i in sorted(carried.items()):
            if i > rating:
                self.f("PERF.current", "", f"{net}: {i:.2f} A over its bridges and wires, the kind's copper carries "
                       f"{rating:g} A")


def geometry(cfg, board, design, plan):
    """The footprint geometry of the plan's parts: the geometry beside the board file, the footprint data of the parts
    entries, the library cache of `edakit part import` – as for a PCB (pcb.plan_geometry)."""
    from . import pcb
    refs = [d for d in plan.place if d in design.comps]
    try:
        return pcb.plan_geometry(cfg, board, design, refs)
    except SystemExit:
        return {}


def net_currents(cfg):
    f = cfg.artifacts / "sim" / "net_currents.json"
    if not f.is_file():
        return None
    return json.loads(f.read_text(encoding="utf-8")).get("nets")


def check(cfg, board, plan=None, design=None, currents=None):
    """The Result of the plan of a hand-wired board."""
    plan = plan or board_plan(cfg, board)
    design = design or Design.from_config(cfg)
    geo = geometry(cfg, board, design, plan)
    return Check(cfg, board, plan, design, geo, currents if currents is not None else net_currents(cfg)).run()


# --- drawing --------------------------------------------------------------------------------------------------------

class Svg:
    def __init__(self, w, h, scale=9, mm=False):
        """mm: width and height in millimetres, a unit of the drawing one on paper (the cut list at 1:1)."""
        size = f'width="{w:.2f}mm" height="{h:.2f}mm"' if mm else f'width="{w * scale:.0f}" height="{h * scale:.0f}"'
        self.out = [f'<svg xmlns="http://www.w3.org/2000/svg" {size} '
                    f'viewBox="0 0 {w:.2f} {h:.2f}" font-family="DejaVu Sans, Arial, sans-serif">',
                    f'<rect width="{w:.2f}" height="{h:.2f}" fill="#ffffff"/>']

    def add(self, s):
        self.out.append(s)

    def text(self, x, y, s, size=1.4, fill="#222", anchor="middle", weight="normal", rotate=0, halo=False):
        t = f' transform="rotate({rotate} {x:.2f} {y:.2f})"' if rotate else ""
        h = ' paint-order="stroke" stroke="#ffffff" stroke-width="0.35"' if halo else ""
        self.add(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
                 f'dominant-baseline="central" font-weight="{weight}"{t}{h}>{html.escape(str(s))}</text>')

    def done(self):
        return "\n".join(self.out + ["</svg>"]) + "\n"


def net_colours(design, nets):
    out, i = {}, 0
    for n in nets:
        if n == design.ground:
            out[n] = GROUND_COLOUR
        elif SUPPLY.match(n):
            out[n] = SUPPLY_COLOUR
        else:
            out[n] = NET_PALETTE[i % len(NET_PALETTE)]
            i += 1
    return out


def wire_colour(w, colours):
    return WIRE_COLOURS.get(w.get("color") or "", colours.get(w["net"], "#555"))


MIN_WIDTH_MM = 100      # the drawing at least as wide as the legend's longest line: a small board gets room to its right


def draw(res, bottom, title):
    plan, design = res.plan, res.design
    pitch = plan.pitch
    W, H = plan.size_mm()
    ml, mt, mr, mb = 8, 17, 8, 19
    svg = Svg(max(W + ml + mr, MIN_WIDTH_MM), H + mt + mb)
    colours = net_colours(design, list(dict.fromkeys([w["net"] for w in res.wires] + list(res.net_of.values()))))

    def X(x):
        return ml + x

    def Y(y):
        return mt + y

    def hc(h):
        x, y = plan.centre(h)
        return X(x), Y(y)

    def rect(b, fill, stroke, width=0.2, dash=None, opacity=1.0, rx=0.4):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return (f'<rect x="{X(b[0]):.2f}" y="{Y(b[1]):.2f}" width="{b[2] - b[0]:.2f}" height="{b[3] - b[1]:.2f}" '
                f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" fill-opacity="{opacity}"{d}/>')

    side = ("bottom side – seen through the board from above, in the orientation of the top view" if bottom else
            "top view – component side, A1 at the top left")
    svg.text(ml, 4.5, title, size=2.6, anchor="start", weight="bold")
    svg.text(ml, 8.4, side, size=1.9, anchor="start", fill="#444")
    svg.text(ml, 11.4, f"{plan.kind['name']}, {plan.cols} × {plan.rows} holes ({W:.1f} × {H:.1f} mm) – edakit "
             "perfboard", size=1.3, anchor="start", fill="#777")
    svg.add(f'<rect x="{ml:.2f}" y="{mt:.2f}" width="{W:.2f}" height="{H:.2f}" rx="0.8" '
            f'fill="{"#d2b886" if bottom else "#dcc596"}" stroke="#8a7146" stroke-width="0.3"/>')
    for c in range(plan.cols):
        x = X((c + 0.5) * pitch)
        svg.text(x, mt - 1.4, col_name(c), size=1.05, fill="#555")
        svg.text(x, mt + H + 1.4, col_name(c), size=1.05, fill="#555")
    for r in range(1, plan.rows + 1):
        y = Y((r - 0.5) * pitch)
        svg.text(ml - 1.6, y, str(r), size=1.05, fill="#555")
        svg.text(ml + W + 1.6, y, str(r), size=1.05, fill="#555")
    mounts = plan.mount_points()
    gone = {(c, r) for c in range(plan.cols) for r in range(1, plan.rows + 1) for _, cx, cy, d, _ in mounts
            if math.dist(plan.centre((c, r)), (cx, cy)) < d / 2 + plan.kind["pad_mm"] / 2}
    if bottom and plan.kind["groups"] != "none":      # the strips of a kind that has them
        seen = set()
        for c in range(plan.cols):
            for r in range(1, plan.rows + 1):
                key = plan.group_of((c, r))
                if key in seen:
                    continue
                seen.add(key)
                hs = plan.group_holes(key)
                (x0, y0), (x1, y1) = hc(hs[0]), hc(hs[-1])
                svg.add(f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" stroke="#e4d8c0" '
                        f'stroke-width="{plan.kind["pad_mm"]:.2f}" stroke-linecap="round"/>')
    for c in range(plan.cols):
        for r in range(1, plan.rows + 1):
            if (c, r) in gone or (bottom and (c, r) in res.pin_at):
                continue
            x, y = hc((c, r))
            if bottom:
                svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.78" fill="#e4d8c0" stroke="#b9a684" '
                        'stroke-width="0.1"/>')
                svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.36" fill="#8a7654"/>')
            else:
                svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.48" fill="#7a6545"/>')
    for _, cx, cy, d, k in mounts:
        svg.add(f'<circle cx="{X(cx):.2f}" cy="{Y(cy):.2f}" r="{k / 2:.2f}" fill="none" stroke="#999" '
                'stroke-width="0.15" stroke-dasharray="0.6 0.4"/>')
        svg.add(f'<circle cx="{X(cx):.2f}" cy="{Y(cy):.2f}" r="{d / 2:.2f}" fill="#ffffff" stroke="#777" '
                'stroke-width="0.2"/>')
    wire_ends = {h: wire_colour(w, colours) for w in res.wires if w["kind"] == "wire" for h in w["holes"]}
    if bottom:
        for p in res.placed.values():
            for sh in p.shapes():
                if sh[0] == "circle":
                    svg.add(f'<circle cx="{X(sh[1][0]):.2f}" cy="{Y(sh[1][1]):.2f}" r="{sh[2] / 2:.2f}" fill="none" '
                            'stroke="#8a7550" stroke-width="0.15" stroke-dasharray="0.5 0.35"/>')
                else:
                    svg.add(rect(sh[1], "none", "#8a7550", width=0.15, dash="0.5 0.35"))
        for h in res.pin_at:
            x, y = hc(h)
            svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.02" fill="#5c6269" stroke="#16181b" stroke-width="0.28"/>')
            svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.3" fill="#d9dde1"/>')
        for w in res.wires:
            if w["kind"] != "bridge":
                continue
            for a, b in zip(w["holes"], w["holes"][1:]):
                (x1, y1), (x2, y2) = hc(a), hc(b)
                for colour, width in (("#2a2116", 1.3), (colours.get(w["net"], "#555"), 0.95)):
                    svg.add(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{colour}" '
                            f'stroke-width="{width}" stroke-linecap="round"/>')
        for h, col in wire_ends.items():
            x, y = hc(h)
            svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.62" fill="#ffffff" stroke="{col}" stroke-width="0.42"/>')
        for w in res.wires:
            if w["kind"] == "bridge" and len(w["holes"]) > 4:
                (x1, y1), (x2, y2) = hc(w["holes"][0]), hc(w["holes"][-1])
                vertical = abs(x1 - x2) < 0.01
                x, y = (x1 + x2) / 2, (y1 + y2) / 2
                x, y = (x + 1.35, y) if vertical else (x + 1.27, y - 1.45)
                svg.text(x, y, w["net"], size=0.95, fill=colours.get(w["net"], "#333"), rotate=-90 if vertical else 0,
                         halo=True)
        for d, p in res.placed.items():
            b = p.raised_box() if p.raised else p.bodies()[0]
            svg.text(X((b[0] + b[2]) / 2), Y((b[1] + b[3]) / 2), d, size=1.25, fill="#4d3f27", halo=True)
    else:
        for d, p in sorted(res.placed.items(), key=lambda kv: kv[1].raised):
            if not p.raised:
                draw_part(svg, d, p, design, X, Y, hc, rect)
        for w in res.wires:
            if w["kind"] != "wire":
                continue
            col = wire_colour(w, colours)
            pts = " ".join(f"{hc(parse_hole(h))[0]:.2f},{hc(parse_hole(h))[1]:.2f}" for h in w["path"])
            svg.add(f'<polyline points="{pts}" fill="none" stroke="#333" stroke-width="1.05" stroke-linecap="round" '
                    'stroke-linejoin="round" stroke-opacity="0.55"/>')
            svg.add(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="0.8" stroke-linecap="round" '
                    'stroke-linejoin="round"/>')
            for h in (w["path"][0], w["path"][-1]):
                x, y = hc(parse_hole(h))
                svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.55" fill="{col}" stroke="#333" stroke-width="0.15"/>')
        for d, p in res.placed.items():
            if p.raised:
                draw_module(svg, d, p, design, X, Y, hc, rect)
    ly = mt + H + 4.2
    if bottom:
        x, y = ml, ly
        svg.add(f'<circle cx="{x + 1:.2f}" cy="{y:.2f}" r="1.02" fill="#5c6269" stroke="#16181b" '
                f'stroke-width="0.28"/><circle cx="{x + 1:.2f}" cy="{y:.2f}" r="0.3" fill="#d9dde1"/>')
        svg.text(x + 2.6, y, "soldered lead", size=1.3, anchor="start")
        svg.add(f'<circle cx="{x + 19:.2f}" cy="{y:.2f}" r="0.62" fill="#ffffff" stroke="#777777" '
                'stroke-width="0.42"/>')
        svg.text(x + 20.4, y, "wire from the top", size=1.3, anchor="start")
        svg.add(f'<circle cx="{x + 40:.2f}" cy="{y:.2f}" r="0.78" fill="#e4d8c0" stroke="#b9a684" stroke-width="0.1"/>'
                f'<circle cx="{x + 40:.2f}" cy="{y:.2f}" r="0.36" fill="#8a7654"/>')
        svg.text(x + 41.4, y, "empty hole", size=1.3, anchor="start")
        svg.text(x + 56, y, "bars: bridges of bare wire, coloured by net", size=1.3, anchor="start", fill="#444")
        x, y = ml, ly + 3.3
        for net in dict.fromkeys(w["net"] for w in res.wires if w["kind"] == "bridge"):
            svg.add(f'<line x1="{x:.2f}" y1="{y:.2f}" x2="{x + 3:.2f}" y2="{y:.2f}" stroke="{colours.get(net)}" '
                    'stroke-width="1.3" stroke-linecap="round"/>')
            svg.text(x + 3.8, y, net, size=1.3, anchor="start")
            x += 14
            if x > ml + W - 10:
                x, y = ml, y + 2.8
    else:
        svg.text(ml, ly, "Parts as seen from above; insulated wires in their colour, entering the board at the dots. "
                 "The bridges are in the bottom view.", size=1.3, anchor="start", fill="#444")
        x, y = ml, ly + 3.2
        for w in res.wires:
            if w["kind"] == "wire":
                svg.add(f'<line x1="{x:.2f}" y1="{y:.2f}" x2="{x + 3:.2f}" y2="{y:.2f}" '
                        f'stroke="{wire_colour(w, colours)}" stroke-width="0.8" stroke-linecap="round"/>')
                svg.text(x + 3.8, y, f"{w['net']} {w['path'][0]}–{w['path'][-1]}", size=1.2, anchor="start")
                x += 23
                if x > ml + W - 15:
                    x, y = ml, y + 2.6
        kinds = {p.kind for p in res.placed.values()}
        polar = any({"plus", "minus"} <= {v.get("role") for v in (p.entry.get("pins") or {}).values()}
                    for p in res.placed.values() if p.kind not in ("capacitor", "led"))
        marks = [m for m, show in (("LED: flat side = cathode, + = anode (long lead).", "led" in kinds),
                                   ("Capacitor: stripe = minus.", "capacitor" in kinds),
                                   ("+ and −: the ends of a holder or connector.", polar),
                                   ("Dashed circles: the nuts of the mounting holes.", bool(plan.mounts))) if show]
        if marks:
            svg.text(ml, y + 3, "  ".join(marks), size=1.3, anchor="start", fill="#444")
    return svg.done()


def draw_part(svg, d, p, design, X, Y, hc, rect):
    entry, comp = p.entry, design.comps[d]
    holes = p.holes
    for h in holes.values():
        x, y = hc(h)
        svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.42" fill="#444"/>')
    body = p.bodies()[0]
    cx, cy = X((body[0] + body[2]) / 2), Y((body[1] + body[3]) / 2)
    roles = {v.get("role"): n for n, v in (entry.get("pins") or {}).items()}
    vertical = (body[3] - body[1]) > (body[2] - body[0])
    if p.kind == "resistor" and len(holes) == 2:
        a, b = (hc(holes[n]) for n in sorted(holes, key=natural_key))
        svg.add(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="#9a9a9a" '
                'stroke-width="0.45"/>')
        thick = min(body[2] - body[0], body[3] - body[1]) > 3
        svg.add(rect(body, "#5d86c4" if thick else "#8fb3e6", "#3d5f91", rx=min(body[2] - body[0],
                                                                                body[3] - body[1]) / 2))
        svg.text(cx, cy, f"{d} {comp.get('value', '')}".strip(), size=1.3 if thick else 1.05, fill="#10233f",
                 rotate=-90 if vertical else 0)
    elif p.kind == "led" and "anode" in roles and "cathode" in roles:
        colour = str((entry.get("values") or {}).get("color", "red")).lower()
        r = min(body[2] - body[0], body[3] - body[1]) / 2
        svg.add(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{LED_FILL.get(colour, "#ccc")}" '
                'stroke="#555" stroke-width="0.25" fill-opacity="0.9"/>')
        polar_marks(svg, hc(holes[roles["anode"]]), hc(holes[roles["cathode"]]), cx, cy, r, "#222")
        svg.text(cx, cy, d, size=1.2, fill="#222", halo=True)
    elif p.kind == "capacitor" and "plus" in roles and "minus" in roles:
        r = min(body[2] - body[0], body[3] - body[1]) / 2
        svg.add(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="#2b4c7e" stroke="#1a2f50" '
                'stroke-width="0.25"/>')
        polar_marks(svg, hc(holes[roles["plus"]]), hc(holes[roles["minus"]]), cx, cy, r, "#ffffff", stripe=True)
        svg.text(cx, cy - 1.2, d, size=1.5, fill="#ffffff", weight="bold")
        svg.text(cx, cy + 1.2, value_of(comp), size=1.0, fill="#ffffff")
    elif p.kind == "button":
        svg.add(rect(body, "#3a3a3a", "#111", rx=0.5))
        svg.add(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="1.75" fill="#7a7a7a" stroke="#222" stroke-width="0.2"/>')
        svg.text(cx, cy - 2.4, d, size=1.1, fill="#ffffff", weight="bold")
    elif p.kind == "connector":
        svg.add(rect(body, "#1e1e1e", "#000", rx=0.2))
        for n, h in holes.items():
            x, y = hc(h)
            svg.add(f'<rect x="{x - 0.32:.2f}" y="{y - 0.32:.2f}" width="0.64" height="0.64" fill="#d4af37"/>')
            svg.text(x + 0.9, y - 0.9, n, size=0.8, fill="#ffffff", weight="bold")
        svg.text(cx, Y(body[3]) + 1.2, d, size=1.1, fill="#222", weight="bold", halo=True)
    else:
        svg.add(rect(body, "#cfcfcf", "#555"))
        svg.text(cx, cy, d, size=1.2)
        if "plus" in roles and "minus" in roles:   # a holder fits both ways round: its ends marked (M-5 of LR.7)
            for role, sign in (("plus", "+"), ("minus", "−")):
                x, y = hc(holes[roles[role]])
                svg.text(x + (1.6 if x < cx else -1.6), y, sign, size=1.9, fill="#222", weight="bold")


def polar_marks(svg, plus, minus, cx, cy, r, fill, stripe=False):
    ux, uy = minus[0] - plus[0], minus[1] - plus[1]
    ln = math.hypot(ux, uy) or 1.0
    ux, uy = ux / ln, uy / ln
    k = 0.78 if stripe else 0.82
    mx, my = cx + ux * r * k, cy + uy * r * k
    half = math.sqrt(max(r * r - (r * k) ** 2, 0))
    svg.add(f'<line x1="{mx - uy * half:.2f}" y1="{my + ux * half:.2f}" x2="{mx + uy * half:.2f}" '
            f'y2="{my - ux * half:.2f}" stroke="{"#c9d6ea" if stripe else "#222"}" '
            f'stroke-width="{1.6 if stripe else 0.35}"/>')
    svg.text(plus[0] - ux * 1.3 + (0 if stripe else 1.4), plus[1] - uy * 1.3, "+", size=1.5, fill=fill, weight="bold")


def draw_module(svg, d, p, design, X, Y, hc, rect):
    """A module on sockets: drawn after the wires that run beneath it, see-through, with its pin names."""
    entry, comp = p.entry, design.comps[d]
    for b in p.bodies():
        svg.add(rect(b, "#1e1e1e", "#000", rx=0.3))
    for n, h in p.holes.items():
        x, y = hc(h)
        svg.add(f'<rect x="{x - 0.45:.2f}" y="{y - 0.45:.2f}" width="0.9" height="0.9" fill="#d4af37"/>')
    rb = p.raised_box()
    svg.add(rect(rb, "#1f5fa8", "#1f5fa8", width=0.25, dash="1 0.6", opacity=0.07, rx=0.8))
    rows = sorted({h[1] for h in p.holes.values()})
    for n, h in p.holes.items():
        x, y = hc(h)
        pin = (entry.get("pins") or {}).get(n, {})
        name = str(pin.get("print", pin.get("name", n))).replace("~", "")
        dy = 1.0 if h[1] == rows[0] else -1.0
        svg.text(x, y + dy * 0.9, name, size=0.78, fill="#1f5fa8", anchor="end" if dy > 0 else "start", rotate=-90)
    cx, cy = X((rb[0] + rb[2]) / 2), Y((rb[1] + rb[3]) / 2)
    svg.text(cx, cy - 0.6, f"{d}  {str(comp.get('label') or comp.get('part') or '').split('(')[0].strip()}",
             size=1.6, fill="#1f5fa8", weight="bold", halo=True)
    svg.text(cx, cy + 1.6, "plugged in on sockets", size=1.1, fill="#1f5fa8", halo=True)


# --- lists ----------------------------------------------------------------------------------------------------------

def holes_of(w):
    if w["kind"] == "bridge":
        return ("–" if len(w["holes"]) == 2 else " … ").join(w["path"])
    return f"{w['path'][0]}–{w['path'][-1]}"


def cutlist(res):
    """Insulated wires by colour and pieces of bare wire by length, every length rounded up to the step (decision
    22): a straight row of bridges is one piece; a single bridge beside a wire's end is that wire's stripped end
    (decision 23)."""
    plan = res.plan
    cw = plan.kind["wires"]
    step = plan.cut_step_mm or cw["step_mm"]

    def up(x):
        return int(math.ceil(x / step - 1e-9) * step)

    ends = {h for w in res.wires if w["kind"] == "wire" for h in w["holes"]}
    insulated, bare, by_end = [], [], []
    for w in res.wires:
        if w["kind"] == "wire":
            pts = [parse_hole(h) for h in w["path"]]
            top = sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) * plan.pitch
            colour = w.get("color") or ("black" if w["net"] == res.design.ground else
                                        "red" if SUPPLY.match(w["net"]) else "any")
            insulated.append({"colour": colour, "mm": up(top + cw["slack_mm"] + 2 * cw["strip_mm"]), "wire": w})
        else:
            steps = len(w["holes"]) - 1
            if steps == 1 and (w["holes"][0] in ends or w["holes"][1] in ends):
                by_end.append(w)
            else:
                bare.append({"mm": up(steps * plan.pitch + 2 * cw["bridge_end_mm"]), "wire": w})
    return {"step": step, "strip": cw["strip_mm"], "insulated": insulated, "bare": bare, "by_end": by_end}


CUT_ROW_MM = 6.0                 # the cut list at 1:1: a row per piece
CUT_COPPER, CUT_TIN = "#c87f4a", "#a9adb3"   # a stripped end of solid copper, the bare tinned wire


def draw_cut(res, title):
    """The cut list at 1:1 (cut.svg): a centimetre ruler over a 1 cm grid, the insulated wires and then the pieces of
    bare wire, each from the longest down and left-aligned at the ruler's zero; beside each its length, for a wire
    what is stripped at its left and right end, and its holes and net. Printed at 100 % a piece can be laid on it."""
    cut = cutlist(res)
    strip = cut["strip"]
    ins = sorted(cut["insulated"], key=lambda i: -i["mm"])
    bare = sorted(cut["bare"], key=lambda b: -b["mm"])
    span = max(10, math.ceil(max([i["mm"] for i in ins + bare], default=10) / 10) * 10)
    x0, size = 6.0, 2.5
    rows = [("Insulated wire, solid core, on top", None)] * bool(ins) + [
        ("insulated", (i["mm"], f"strip {strip:g} mm left, {strip:g} mm right – "
                       f"{i['colour'] if i['colour'] != 'any' else 'any colour'}, {holes_of(i['wire'])} "
                       f"{i['wire']['net']}", i)) for i in ins] + [
        ("Bare tinned wire, straight, on the bottom", None)] * bool(bare) + [
        ("bare", (b["mm"], f"{holes_of(b['wire'])} {b['wire']['net']}", b)) for b in bare]
    note = (f"Not cut: the bridges {', '.join(holes_of(w) for w in cut['by_end'])} are the wires' stripped ends."
            if cut["by_end"] else "" if ins or bare else "Nothing to cut: the plan has no wire and no bridge.")
    wide = max([11 + len(r[1]) * size * 0.56 for _, r in rows if r] + [0])   # the length, then the text beside it
    top, ruler = 15.0, 6.5
    y_end = top + ruler + sum((5.0 if i == 0 else 7.0) if r is None else CUT_ROW_MM for i, (_, r) in enumerate(rows))
    w = max(x0 + span + 4 + wide + 4, 100.0)
    h = y_end + (6.5 if note else 3)
    svg = Svg(w, h, mm=True)
    svg.text(x0, 5.0, f"{title} – cut list", size=3.4, anchor="start", weight="bold")
    svg.text(x0, 10.0, f"1:1 when printed at 100 % – lengths rounded up to {cut['step']:g} mm; lay a piece on its "
                      "row and cut it at the end", size=2.1, anchor="start", fill="#444")
    base = top + ruler
    for mm in range(span + 1):          # the ruler: mm, 5 mm and cm ticks up from its edge, the cm numbered
        x = x0 + mm
        tick = 3.0 if mm % 10 == 0 else 2.0 if mm % 5 == 0 else 1.2
        svg.add(f'<line x1="{x:.2f}" y1="{base:.2f}" x2="{x:.2f}" y2="{base - tick:.2f}" stroke="#333" '
                f'stroke-width="{0.18 if mm % 10 == 0 else 0.1}"/>')
        if mm % 10 == 0:
            svg.text(x, base - 4.6, str(mm // 10), size=2.2, fill="#333")
            svg.add(f'<line class="cm" x1="{x:.2f}" y1="{base:.2f}" x2="{x:.2f}" y2="{y_end:.2f}" stroke="#c9ced6" '
                    'stroke-width="0.15"/>')
    svg.text(x0 + span + 1.5, base - 4.6, "cm", size=2.2, anchor="start", fill="#333")
    svg.add(f'<line x1="{x0:.2f}" y1="{base:.2f}" x2="{x0 + span:.2f}" y2="{base:.2f}" stroke="#333" '
            'stroke-width="0.2"/>')
    y = base
    for i, (kind, r) in enumerate(rows):
        if r is None:                   # a section's heading, between the grid's lines
            y += 0 if i == 0 else 2.0
            svg.text(x0 + 0.6, y + 2.8, kind, size=2.2, anchor="start", fill="#444", weight="bold", halo=True)
            y += 5.0
            continue
        mm, text, item = r
        yc = y + CUT_ROW_MM / 2
        svg.add(f'<g data-cut="{kind}" data-mm="{mm}">')
        if kind == "insulated":
            svg.add(f'<rect class="conductor" x="{x0:.2f}" y="{yc - 0.35:.2f}" width="{mm:.2f}" height="0.7" '
                    f'fill="{CUT_COPPER}"/>')
            colour = WIRE_COLOURS.get(item["colour"], "#8a8a8a")
            svg.add(f'<rect class="insulation" x="{x0 + strip:.2f}" y="{yc - 0.9:.2f}" width="{mm - 2 * strip:.2f}" '
                    f'height="1.8" rx="0.4" fill="{colour}" stroke="#333" stroke-width="0.12"/>')
        else:
            svg.add(f'<rect class="conductor" x="{x0:.2f}" y="{yc - 0.35:.2f}" width="{mm:.2f}" height="0.7" '
                    f'fill="{CUT_TIN}" stroke="#6b6f75" stroke-width="0.08"/>')
        tx = x0 + span + 4
        svg.text(tx + 9, yc, f"{mm} mm", size=size, anchor="end", weight="bold")      # the lengths right-aligned
        svg.text(tx + 11, yc, text, size=size, anchor="start", fill="#333")
        svg.add("</g>")
        y += CUT_ROW_MM
    if note:
        svg.text(x0, y_end + 3.2, note, size=2.1, anchor="start", fill="#444")
    return svg.done()


def build_group(p):
    if p.raised:
        return "socket"
    return p.kind if p.kind in ("resistor", "button", "connector", "diode", "led", "capacitor") else "other"


def lists(res, title, findings_too=True):
    design = res.design
    placed, wires = res.placed, res.wires
    out = []
    if findings_too:
        errors = [f for f in res.findings if f.severity == "error" and not f.accepted]
        out += ["## Check\n", f"{len(errors)} errors, {len(res.findings) - len(errors)} warnings and notes.\n"]
        out += [f"- **{f.severity}** `{f.code}{'/' + f.grade if f.grade else ''}` – {f.text}" for f in res.findings]
        out.append("")
    cut = cutlist(res)
    out.append(f"## Cut list – lengths rounded up to {cut['step']:g} mm\n")
    out.append("![The cut list at 1:1](cut.svg)\n")
    per_colour = {}
    if cut["insulated"]:
        out.append(f"**Insulated wire, solid core, on top** – may turn corners; strip {cut['strip']:g} mm at each "
                   "end: through its hole and over onto the pad of the lead beside it, which makes the bridge to "
                   "that lead.\n")
        out += ["| Colour | Length | Holes | Net |", "| --- | --- | --- | --- |"]
        for c in dict.fromkeys(i["colour"] for i in cut["insulated"]):
            for i in sorted((i for i in cut["insulated"] if i["colour"] == c), key=lambda i: -i["mm"]):
                out.append(f"| {c} | {i['mm']} mm | {holes_of(i['wire'])} | {i['wire']['net']} |")
            per_colour[c] = sum(i["mm"] for i in cut["insulated"] if i["colour"] == c)
        out.append("\nPer colour: " + ", ".join(f"{c} {mm} mm" for c, mm in per_colour.items()) + ".\n")
    bare_total = sum(b["mm"] for b in cut["bare"])
    if cut["bare"]:
        out.append("**Bare tinned wire, straight, on the bottom** – one piece per row of bridges, laid over the pads "
                   "and soldered at each.\n")
        out += ["| Length | Pieces | Holes |", "| --- | --- | --- |"]
        by_len = defaultdict(list)
        for b in cut["bare"]:
            by_len[b["mm"]].append(b["wire"])
        for mm in sorted(by_len, reverse=True):
            out.append(f"| {mm} mm | {len(by_len[mm])} | " + ", ".join(f"{holes_of(w)} {w['net']}" for w in by_len[mm])
                       + " |")
        out.append(f"\nIn all {len(cut['bare'])} pieces, {bare_total} mm." + (
            f" A wire's stripped end makes the {len(cut['by_end'])} bridges beside the wires' ends: " +
            ", ".join(holes_of(w) for w in cut["by_end"]) + "." if cut["by_end"] else "") + "\n")
    out.append("## Build list – from low to high\n")
    groups = defaultdict(list)
    for w in wires:
        groups[w["kind"]].append(w)
    for d, p in sorted(placed.items(), key=lambda kv: natural_key(kv[0])):
        groups[build_group(p)].append(d)
    cut_mm = {id(i["wire"]): i["mm"] for i in cut["insulated"] + cut["bare"]}
    colour_of = {id(i["wire"]): i["colour"] for i in cut["insulated"]}
    modules = [d for d, p in placed.items() if p.raised]
    step = 0
    for key, head in ORDER:
        if key == "test":
            step += 1
            out.append(f"{step}. **{head}:** the test list below" + (f", before {', '.join(modules)} "
                                                                     "is plugged in." if modules else "."))
            continue
        if key == "plug":
            if modules:
                step += 1
                out.append(f"{step}. **{head}:** plug {', '.join(modules)} into the sockets.")
            continue
        items = groups.get(key)
        if not items:
            continue
        rows = []
        for it in items:
            if key == "bridge":
                if id(it) in cut_mm:
                    rows.append(f"holes {holes_of(it)} {it['net']} ({cut_mm[id(it)]} mm)")
            elif key == "wire":
                colour = colour_of[id(it)]
                rows.append(f"{'any colour' if colour == 'any' else colour}, holes {holes_of(it)} {it['net']} "
                            f"({cut_mm[id(it)]} mm)")
            else:
                rows.append(build_row(it, placed[it], design))
        if not rows:
            continue
        step += 1
        tail = (" The bridges beside the wires' ends are their stripped ends." if key == "bridge" and cut["by_end"] else
                " Bend each stripped end along the pad beside it without covering that hole, and do not solder it "
                "yet: it is soldered with the lead or the bridges in that pad, in their step." if key == "wire" else "")
        out.append(f"{step}. **{head}:** " + "; ".join(rows) + "." + tail)
    out.append("")
    out += test_list(res)
    out += material(res, cut, per_colour, bare_total)
    return "\n".join(out) + "\n"


def runs_text(holes):
    """Holes as straight runs: ['B9–P9', 'B15–P15']."""
    by_row = defaultdict(list)
    for c, r in holes:
        by_row[r].append(c)
    out = []
    for r, cs in sorted(by_row.items()):
        cs.sort()
        start = prev = cs[0]
        for c in cs[1:] + [None]:
            if c is not None and c == prev + 1:
                prev = c
                continue
            out.append(hole_name((start, r)) + (f"–{hole_name((prev, r))}" if prev != start else ""))
            if c is not None:
                start = prev = c
    return out


def value_of(comp):
    return str(comp.get("value") or comp.get("part") or "")


def build_row(d, p, design):
    e, comp = p.entry, design.comps[d]
    roles = {v.get("role"): n for n, v in (e.get("pins") or {}).items()}
    if p.kind == "led" and "anode" in roles and "cathode" in roles:
        return (f"{d} {(e.get('values') or {}).get('color', '')}: anode (long lead) in hole "
                f"{hole_name(p.holes[roles['anode']])}, cathode (flat) in hole {hole_name(p.holes[roles['cathode']])}")
    if "plus" in roles and "minus" in roles:
        if p.kind == "capacitor":
            return (f"{d} {value_of(comp)}: plus in hole {hole_name(p.holes[roles['plus']])}, minus (stripe) in "
                    f"hole {hole_name(p.holes[roles['minus']])}")
        return (f"{d} {value_of(comp)}: its + end on hole {hole_name(p.holes[roles['plus']])}, its − end on hole "
                f"{hole_name(p.holes[roles['minus']])} – find the + on the part, it may fit both ways round")
    if p.kind == "diode" and "anode" in roles and "cathode" in roles:
        return (f"{d}: cathode (ring) in hole {hole_name(p.holes[roles['cathode']])}, anode in hole "
                f"{hole_name(p.holes[roles['anode']])}")
    if p.raised:
        return f"sockets for {d}: holes " + " and ".join(runs_text(p.holes.values()))
    if len(p.holes) == 2:
        a, b = sorted(p.holes, key=natural_key)
        return f"{d} {comp.get('value', '')} in holes {hole_name(p.holes[a])}–{hole_name(p.holes[b])}".replace("  ", " ")
    return f"{d}: " + ", ".join(f"{pin_label(e, n)} in hole {hole_name(h)}" for n, h in
                                sorted(p.holes.items(), key=lambda kv: natural_key(kv[0])))


def test_list(res):
    plan, design, placed, net_of = res.plan, res.design, res.placed, res.net_of
    modules = [d for d, p in placed.items() if p.raised]
    out = [f"## Test list – multimeter in beep mode{', ' + ', '.join(modules) + ' not plugged in' if modules else ''}\n"]
    ground = design.ground
    supplies = [n for n in dict.fromkeys(net_of.values()) if n != ground and SUPPLY.match(n)]
    first = {}
    for (d, n), net in sorted(net_of.items(), key=lambda kv: (placed[kv[0][0]].holes[kv[0][1]][1],
                                                              placed[kv[0][0]].holes[kv[0][1]][0])):
        first.setdefault(net, hole_name(placed[d].holes[n]))
    step = 1
    for s in supplies:
        if ground not in first or s not in first:
            continue
        across = [d for d, p in placed.items() if not p.raised and
                  {net_of.get((d, n)) for n in p.holes} == {s, ground}]
        rs = [d for d in across if placed[d].kind == "resistor" and (placed[d].entry.get("values") or {}).get("value_ohm")]
        caps = [d for d in across if placed[d].kind == "capacitor"]
        if rs:
            par = 1 / sum(1 / placed[d].entry["values"]["value_ohm"] for d in rs)
            reads = f"reads about {par:.0f} Ω ({' ∥ '.join(rs)})"
        else:
            reads = "reads open"
        out.append(f"{step}. **Before the first power-up:** {s} ({first[s]}) to {ground} ({first[ground]}) {reads}"
                   + (f" once {', '.join(caps)} has charged" if caps else "") + " – 0 Ω is a short.")
        step += 1
    out.append(f"{step}. **Each net beeps** from its first hole to every other:\n")
    out += ["| Net | From hole | To holes |", "| --- | --- | --- |"]
    for net in dict.fromkeys(net_of.values()):
        members = [(placed[d].holes[n], f"{d}.{pin_label(placed[d].entry, n)}")
                   for (d, n), nn in net_of.items() if nn == net]
        by = defaultdict(list)
        for h, who in members:
            by[res.ufb.find(("h", h))].append((h, who))
        parts = sorted((sorted(g, key=lambda m: (m[0][1], m[0][0])) for g in by.values()), key=len, reverse=True)
        for i, g in enumerate(parts):
            if len(g) < 2:
                continue
            label = net if len(parts) == 1 else f"{net} ({i + 1})"
            out.append(f"| {label} | {hole_name(g[0][0])} ({g[0][1]}) | " +
                       ", ".join(f"{hole_name(h)} ({w})" for h, w in g[1:]) + " |")
        if len(parts) > 1 and modules:
            out.append(f"| | | {net}'s groups are joined inside {', '.join(modules)}: they beep once it is plugged in |")
    step += 1
    out.append(f"\n{step}. **Next to each bridge nothing else beeps** – the neighbouring pads of other nets:\n")
    copper = {}
    for h, who in res.pin_at.items():
        d, n = who.split(".", 1)
        if (d, n) in net_of:
            copper[h] = net_of[(d, n)]
    for h, net in res.bottom_at.items():
        copper.setdefault(h, net)
    pairs = set()
    for w in res.wires:
        if w["kind"] != "bridge":
            continue
        for h in w["holes"]:
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (h[0] + dc, h[1] + dr)
                other = copper.get(nb)
                if other and other != w["net"] and plan.group_of(nb) != plan.group_of(h) or \
                        (other and other != w["net"] and plan.group_of(nb) is None):
                    pairs.add(tuple(sorted([(hole_name(h), w["net"]), (hole_name(nb), other)])))
    by_nets = defaultdict(list)
    for (h1, n1), (h2, n2) in sorted(pairs):
        by_nets[tuple(sorted([n1, n2]))].append(f"{h1}–{h2}")
    out += ["<details><summary>" + f"{len(pairs)} pairs of neighbouring holes" + "</summary>\n",
            "| Nets | Neighbouring holes |", "| --- | --- |"]
    out += [f"| {n1} / {n2} | {', '.join(hs)} |" for (n1, n2), hs in sorted(by_nets.items())]
    out.append("\n</details>\n")
    return out


def material(res, cut, per_colour, bare_total):
    plan = res.plan
    W, H = plan.size_mm()
    sizes = plan.kind.get("sizes", {})
    whole = next((f" cut from a {k.replace('_', ' ')} board ({v[0]} × {v[1]} holes)" for k, v in
                  sorted(sizes.items(), key=lambda kv: kv[1][0] * kv[1][1])
                  if v[0] >= plan.cols and v[1] >= plan.rows), "")
    out = ["## Material\n",
           f"- {plan.kind['name']}: {plan.cols} × {plan.rows} holes ({W:.1f} × {H:.1f} mm),{whole}" +
           (f"; {len(plan.mounts)} mounting holes drilled to " + ", ".join(sorted({f'{m["d"]:g} mm' for m in
                                                                                    plan.mounts})) if plan.mounts
            else "") + "."]
    if per_colour:
        out.append("- Insulated wire, solid core: " + ", ".join(f"{c} {math.ceil(mm / 10)} cm" for c, mm in
                                                                per_colour.items()) + " – the cut list.")
    if cut["bare"]:
        out.append(f"- Bare tinned copper wire {plan.kind['wires'].get('bare_mm', 0.6):g} mm: "
                   f"{math.ceil(bare_total / 10)} cm in {len(cut['bare'])} pieces – the cut list.")
    modules = [d for d, p in res.placed.items() if p.raised]
    if modules:
        out.append(f"- Sockets for {', '.join(modules)} – an `[[extra]]` of edakit.toml when bought with the parts.")
    out += ["", "For `edakit order`, the board and the wire as `[[extra]]` of edakit.toml (handbook 8.4):", "",
            "```toml", "[[extra]]", f'item = "{plan.kind["name"]}, {plan.cols} x {plan.rows} holes"', "per_set = 1"]
    for c, mm in per_colour.items():
        out += ["", "[[extra]]", f'item = "Insulated solid-core wire, {c}, {math.ceil(mm / 10)} cm"', "per_set = 1"]
    if cut["bare"]:
        out += ["", "[[extra]]", f'item = "Bare tinned copper wire, {math.ceil(bare_total / 10)} cm"', "per_set = 1"]
    out += ["```", ""]
    return out


# --- the command ----------------------------------------------------------------------------------------------------

def out_dir(cfg, board):
    return cfg.artifact("perfboard", board.name)


def write(cfg, res):
    """Top view, bottom view, the cut list at 1:1 and the lists into <artifacts>/perfboard/<board>/: [top, bottom,
    cut, build]."""
    d = out_dir(cfg, res.board)
    d.mkdir(parents=True, exist_ok=True)
    title = f"{res.board.title or res.board.name} on a perfboard"
    files = [d / "top.svg", d / "bottom.svg", d / "cut.svg", d / "build.md"]
    files[0].write_text(draw(res, False, title), encoding="utf-8")
    files[1].write_text(draw(res, True, title), encoding="utf-8")
    files[2].write_text(draw_cut(res, title), encoding="utf-8")
    head = (f"# {title} – check, cut list, build list, test list\n\nWritten by `edakit perfboard` from "
            f"`{res.board.file or 'hardware/boards/' + res.board.name + '.toml'}` and the graph; the drawings are "
            "[top](top.svg) and [bottom](bottom.svg), both seen from above, and the [cut list](cut.svg) at 1:1."
            "\n\n![top](top.svg)\n\n![bottom](bottom.svg)\n\n")
    files[3].write_text(head + lists(res, title), encoding="utf-8")
    return files


BUILD_FILES = ("top.svg", "bottom.svg", "cut.svg", "build.md")   # a perfboard's build files, in a gate run's fab/<board>/


def build_layers(d):
    """SHA-256 per build file of a perfboard in a gate run's fab/<board>/ – what M-5 signs (fab_sha256)."""
    import hashlib
    return {n: hashlib.sha256((Path(d) / n).read_bytes()).hexdigest() for n in BUILD_FILES if (Path(d) / n).is_file()}


def rows(cfg, design=None, outdir=None):
    """Stage L of every hand-wired board with a plan: its findings as rows of the gate; its drawings and lists – the
    build files the person who solders it reads – into <artifacts>/perfboard/<board>/ and, in a gate run, into
    <run>/fab/<board>/."""
    import shutil
    out = []
    design = design or Design.from_config(cfg)
    for name, (board, plan) in plan_boards(cfg).items():
        res = check(cfg, board, plan, design)
        files = write(cfg, res)
        if outdir is not None:
            d = Path(outdir) / "fab" / name
            d.mkdir(parents=True, exist_ok=True)
            for f in files:
                shutil.copy(f, d / f.name)
        for f in res.findings:
            result = ("waived" if f.accepted else "fail" if f.severity in ("error", "pending") else
                      "warn" if f.severity == "warning" else "info")
            out.append({"stage": "L", "id": f.code, "item": f.place, "check": f.text, "result": result})
        if not any(f.severity in ("error", "pending") and not f.accepted for f in res.findings):
            out.append({"stage": "L", "id": "PERF.net", "item": name, "check": f"perfboard plan of {name} = graph, "
                        "buildable", "result": "pass"})
    return out


def main(cfg, args):
    names = [args.board] if getattr(args, "board", None) else [n for n, b in cfg.boards.items() if b.wired]
    plans = plan_boards(cfg)
    todo = [n for n in names if n in plans]
    if not todo:
        if args.board and args.board in cfg.boards:
            b = cfg.boards[args.board]
            why = ("is not hand-wired (wired = true)" if not b.wired else
                   "has no [perfboard] in its board file " + (b.file or f"hardware/boards/{b.name}.toml"))
            print(f"edakit perfboard: board {args.board} {why}")
        else:
            print("edakit perfboard: no hand-wired board with a plan – [perfboard] in the board file of a board with "
                  "wired = true (handbook 7.9)")
        return 1
    design = Design.from_config(cfg)
    errors = 0
    for name in todo:
        board, plan = plans[name]
        res = check(cfg, board, plan, design)
        print(f"{name}: {plan.kind['name']}, {plan.cols} × {plan.rows} holes, {len(res.placed)} parts, "
              f"{sum(1 for w in res.wires if w['kind'] == 'wire')} wires, "
              f"{sum(len(w['holes']) - 1 for w in res.wires if w['kind'] == 'bridge')} bridges")
        for f in res.findings:
            tag = f"{f.code}{'/' + f.grade if f.grade else ''}"
            print(f"  {'accepted' if f.accepted else f.severity:8} {tag:16} {f.text}")
        bad = [f for f in res.findings if f.severity in ("error", "pending") and not f.accepted]
        errors += len(bad)
        files = write(cfg, res)
        print(f"  {len(bad)} errors; -> " + ", ".join(cfg.relative(f) for f in files))
    return 1 if errors else 0
