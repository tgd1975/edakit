"""Project configuration: edakit.toml and the files it points to.

edakit.toml is the table of contents: the project, its boards with their EasyEDA documents, where the files are, and
the release settings. What one role decides lives in a file of its own, with one owner and one hash (handbook 10.1):

    hardware/requirements.toml    what the circuit must do: needs, requirements            the user          –
    hardware/graph.json           circuit, purpose, hand-over, ground net, check settings  circuit designer  circuit
    hardware/parts/, sim.json     parts database, simulation scenarios                     circuit designer  circuit
    hardware/schematic.toml       arrangement of the schematic: blocks, notes, pin table   circuit designer  –
    hardware/boards/<name>.toml   outline, holes, placement, routing, pours, silk          PCB designer      layout
    SVGs of [[silk.art]]          artwork on the silkscreen                                PCB designer      layout

The tools themselves contain no project knowledge. edakit.toml in the one-file form – board, schematic and checks
inside – is refused with a list of what goes where.

Lookup order: --config PATH, $EDAKIT_CONFIG, then edakit.toml in the current directory or one of its parents.
All relative paths are relative to the directory that contains edakit.toml.
"""

from __future__ import annotations

import math
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

MIL_PER_MM = 1000 / 25.4
TOP, BOTTOM = 1, 2              # EasyEDA layer ids of the two copper sides
LAYER_OF_SIDE = {"top": TOP, "bottom": BOTTOM}
SIDE_OF_LAYER = {TOP: "top", BOTTOM: "bottom"}

DEFAULT_NET_CLASSES = {          # from the largest simulated current (A), practical minimum width (mm)
    "POWER": {"min_a": 0.3, "width_mm": 0.6},
    "SUPPLY": {"min_a": 0.1, "width_mm": 0.4},
    "SIGNAL": {"min_a": 0.0, "width_mm": 0.25},
}
POUR_CLEARANCE_MM = 0.25         # pour_only: what the computed pour keeps from foreign copper (copper-area rule)
POUR_MIN_WIDTH_MM = 0.25         # pour_only: the narrowest neck the computed pour fills
POUR_MIN_PIECE_MM2 = 2.0         # pour_regions: the smallest piece of a shared layer that gets an outline
HEADER_KEEP_MM = 1.27            # on_headers: the plastic of a 2.54 mm pin header, half its width around each pin
PASTE_GAP_MM = 0.4               # [release] assembly paste_gap_mm: SMD pads of different parts, assembled side (L-14)
MAX_BARE_MM = 5.0                # [copper] max_bare_mm: largest copper-free circle on a poured layer (L-15)
UNIFORM = {"led": "row"}         # uniform: LEDs side by side point the same way – the plan check without the key
UNIFORM_WAYS = ("row", "+x", "-x", "+y", "-y")
THICKNESS_MM = 1.6               # board thickness: the order (F-6) and the lead protrusion of the mechanical model

PROJECT_KEYS = ("name", "company", "quantity", "distributors", "lock", "agreements", "graph", "parts", "sim",
                "sim_plugin", "schematic", "signoff", "artifacts", "reports", "datasheets", "stock", "stock_margin_pct",
                "stock_max_age_days", "spare_pct", "requirements")
BOARD_KEYS = ("title", "template", "schematic", "pcb", "file", "bought")  # [boards.<name>] in edakit.toml
BOARD_FILE_KEYS = ("revision", "view", "outline", "holes", "tooling", "place", "near", "near_mm", "edge_mm", "edge_ok",
                   "on_headers", "header_keep_mm", "silk_overlap_mm", "park", "routing", "pours", "pour_regions",
                   "pour_min_piece_mm2", "pour_inset_mm", "silk", "loops", "net_classes", "copper", "order", "uniform",
                   "looks", "thickness_mm")
SCHEMATIC_KEYS = ("stub", "layout")
RELEASE_KEYS = ("layout_files", "state_files", "hash_ignore", "assembly", "stages")
PCBA = ("economic", "standard")  # [release] assembly.pcba: the assembler's class of the order (P-4)
COST_KEYS = ("fees", "budget", "currency", "rates", "shipping", "coupon", "vat_pct", "pcb_price")   # [cost]
EXTRA_KEYS = ("item", "supplier", "code", "per_set", "spare", "moq", "step", "unit_price", "currency")   # [[extra]]
STOCK_MAX_AGE_DAYS = 14          # [project] stock_max_age_days: an older stock snapshot is pending (P-4)
ORDER_KEYS = ("finish", "mark", "remark", "tab_zones", "tab_copper_mm", "mask", "silkscreen")   # [order] (F-6)
MARKS = ("default", "specify", "remove")   # order.mark: JLCPCB's order number anywhere, at the placeholder, none
MASKS = ("green", "purple", "red", "yellow", "blue", "white", "black")   # order.mask: JLCPCB's solder mask colours
SILKSCREENS = ("white", "black")   # order.silkscreen: JLCPCB prints white, on a white mask black (silkscreen_on)
FIRMWARE_KEYS = ("mcu", "out", "gpio")    # [firmware]: the board's firmware contract (edakit firmware), opt-in
DOCS_KEYS = ("files", "decimal")                     # [docs]: Markdown files with quoted values (edakit docs, G-19)

# [scripts.<name>]: a project script that touches edakit's flow – what it reads and writes; edakit/scripts.py
# resolves the entries with edakit's steps into one order (edakit check, handbook 8.6)
SCRIPT_KEYS = ("kind", "cmd", "about", "reads", "writes", "after", "check", "id", "phase", "at", "advisory")


class ConfigError(Exception):
    pass


@dataclass
class Placement:
    x: float
    y: float
    rot: float = 0.0
    side: str = "top"           # EasyEDA side the part sits on: "top" or "bottom"
    lock: bool = True
    auto: bool = False          # written by `pcb place`: a later run may move it; to everything else a fixed part


@dataclass
class Board:
    name: str
    title: str
    template: str               # schematic generated from the graph and replaced on every run
    schematic: str              # readable, board-linked schematic (the PCB hangs on it)
    pcb: str                    # PCB document name in EasyEDA
    file: str = ""              # the board file, as edakit.toml names it: everything below comes from there
    revision: str | None = None  # board revision, printed with the title (silk board_label)
    view: str = "top"           # the plan is drawn looking at this side; "bottom" mirrors x
    outline: list = field(default_factory=list)       # polygon in mm (plan coordinates)
    holes: list = field(default_factory=list)         # [{"x", "y", "d", "keep"}] non-plated mounting holes
    tooling: list = field(default_factory=list)       # [(x, y)] JLCPCB tooling holes (NPTH) for Economic PCBA
    tooling_d: float = 1.152
    tooling_mask: float = 0.148
    tooling_keep: float = 1.5
    place: dict = field(default_factory=dict)         # designator -> Placement (fixed parts)
    near: dict = field(default_factory=dict)          # part -> [host parts it must sit next to]
    near_mm: float = 6.0
    edge_mm: float = 1.0                              # layout.edge of the graph: part box at most this far from the outline
    edge_ok: set = field(default_factory=set)         # parts allowed to touch or overhang the outline
    on_headers: set = field(default_factory=set)      # parts on pin headers: SMD parts of their side may sit under them
    header_keep_mm: float = HEADER_KEEP_MM            # ... clear of this square half width around each of their THT pins
    silk_overlap_mm: float = 0.0                      # how far the boxes of two SMD parts may overlap (silkscreen)
    park: tuple = (10.0, -15.0)                       # where `pcb parts --write` drops new parts (mm, EasyEDA)
    routing: dict = field(default_factory=dict)
    pours: list = field(default_factory=list)
    pour_regions: bool = False                        # nets that share a pour layer get claimed outlines
    pour_min_piece_mm2: float = POUR_MIN_PIECE_MM2
    pour_inset_mm: float | None = None                # pours inside the outline; None: edge clearance + 0.1 mm
    silk: dict = field(default_factory=dict)
    loops: list = field(default_factory=list)         # [(pad a, pad b, max mm, what)] short current loops (L-11)
    net_classes: dict = field(default_factory=lambda: dict(DEFAULT_NET_CLASSES))  # by falling min_a
    force_class: dict = field(default_factory=dict)   # net -> class, whatever its current
    copper: dict = field(default_factory=lambda: _copper("", {}))  # [copper]: max_bare_mm, min_cover (L-15)
    order: dict | None = None                         # [order]: the order form fields of this board (F-6); None: none
    uniform: dict | None = None                       # kind -> "row" | "+x" | "-x" | "+y" | "-y"; None: UNIFORM
    looks: dict | None = None                         # [looks]: visible ("top" | "bottom"), max_track_m, max_vias
    thickness_mm: float = THICKNESS_MM                # board thickness: the order, lead protrusion in mech_<board>.json
    bought: bool = False        # bought = true: on a cable, checked with the graph and the simulation, made by nobody

    # --- plan <-> EasyEDA -------------------------------------------------------------------------------------------
    def to_eda(self, x, y, rot, side):
        """Plan (mm, view side) -> EasyEDA (mm, seen from top), rotation, layer id."""
        layer = LAYER_OF_SIDE[side]
        if self.view == "bottom":
            return -x, y, (180 - rot) % 360, layer
        return x, y, rot % 360, layer

    def from_eda(self, x, y, rot, layer):
        side = SIDE_OF_LAYER.get(layer, "top")
        if self.view == "bottom":
            return -x, y, (180 - rot) % 360, side
        return x, y, rot % 360, side

    def eda_point(self, x, y):
        return (-x, y) if self.view == "bottom" else (x, y)

    def plan_point(self, x, y):
        return self.eda_point(x, y)  # the mirror is its own inverse

    def transform(self, local_mil, x, y, rot, side):
        """Pad or corner of a footprint (mil, relative to its origin at rotation 0 on TOP) -> plan (mm).
        EasyEDA puts a bottom-side part on the board by mirroring local y, then rotating (checked against pads)."""
        ex, ey, erot, layer = self.to_eda(x, y, rot, side)
        lx, ly = local_mil[0] / MIL_PER_MM, local_mil[1] / MIL_PER_MM
        if layer == BOTTOM:
            ly = -ly
        a = math.radians(erot)
        px, py = ex + lx * math.cos(a) - ly * math.sin(a), ey + lx * math.sin(a) + ly * math.cos(a)
        return self.plan_point(px, py)


@dataclass
class Config:
    path: Path
    root: Path
    project: str
    graph: Path
    parts: Path
    sim_config: Path
    sim_plugin: Path | None
    schematic_file: Path
    signoff: Path
    artifacts: Path
    reports: Path
    datasheets: Path            # the datasheets edakit part fetch keeps: <datasheets>/<key>.pdf and .json
    company: str
    quantity: int
    boards: dict
    schematic: dict             # the schematic file: stub, [layout]
    release: dict
    lock: str
    agreements: bool            # the working agreements of handbook 11.4 at session start (edakit/agreements.py)
    raw: dict
    # [project] requirements: the requirements files `edakit req` reads, in the order named (a variant: the main
    # project's file, then its own); [] without the key – no file, no change
    requirements: list = field(default_factory=list)
    stock: Path | None = None           # the stock snapshot of `edakit stock` (P-4); not in the circuit hash
    stock_margin_pct: float = 0.0       # P-4 warns below need x (1 + margin / 100)
    stock_max_age_days: int = STOCK_MAX_AGE_DAYS
    cost: dict | None = None            # [cost] of edakit.toml; None: no cost estimate in the gate
    spare_pct: float = 0.0              # edakit order: spares on every cart line, in % of quantity sets
    extras: list = field(default_factory=list)   # [[extra]]: items off the board – cost estimate and carts
    firmware: dict | None = None  # [firmware] with its defaults; None without the table: no contract
    scripts: dict = field(default_factory=dict)   # [scripts.<name>] as written: name -> entry (edakit/scripts.py)
    docs: list = field(default_factory=list)   # [docs] files: Markdown files whose value blocks edakit docs reads
    docs_decimal: str = "."                    # [docs] decimal: "." or "," in quoted numbers

    def pcba(self):
        """(class, why) of the assembly order: [release] assembly.pcba, or derived from assembly.sides – one side
        Economic, two sides Standard (without [release] assembly both sides count, as for F-3)."""
        a = self.release.get("assembly", {})
        if a.get("pcba"):
            return a["pcba"], f'[release] assembly.pcba = "{a["pcba"]}"'
        sides = a.get("sides", ["top", "bottom"])
        return ("economic" if len(sides) == 1 else "standard"), \
            f"[release] assembly.sides {' + '.join(sides)}: {'one side' if len(sides) == 1 else 'two sides'}"

    def board(self, name=None, made=False) -> Board:
        """The board name, or the only one. made: for what draws or reads a layout – a bought board is refused, and
        without a name the only made board is taken."""
        pool = self.made() if made else self.boards
        if name is None:
            if len(pool) != 1:
                raise ConfigError(f"several boards ({', '.join(pool)}) – pick one with --board" if pool else
                                  f"every board of {self.path.name} is bought – there is no layout to make or read")
            return next(iter(pool.values()))
        if name not in self.boards:
            raise ConfigError(f"board '{name}' is not in {self.path.name} (known: {', '.join(self.boards)})")
        if made and self.boards[name].bought:
            raise ConfigError(f"board {name} is bought (bought = true in {self.path.name} [boards.{name}]): no "
                              "schematic, PCB or manufacturing files – edakit checks it with the graph and the simulation")
        return self.boards[name]

    def made(self) -> dict:
        """The boards edakit makes: every board of [boards] but the bought ones."""
        return {name: b for name, b in self.boards.items() if not b.bought}

    def resolve(self, p) -> Path:
        p = Path(p)
        return p if p.is_absolute() else self.root / p

    def relative(self, p) -> str:
        """A path for messages: relative to the project when it lies inside."""
        p = Path(p)
        return str(p.relative_to(self.root)) if p.is_relative_to(self.root) else str(p)

    def artifact(self, *parts) -> Path:
        out = self.artifacts.joinpath(*parts)
        out.parent.mkdir(parents=True, exist_ok=True)
        return out


def _outline(spec, name):
    if not spec:
        return []
    if "polygon" in spec:
        pts = [tuple(map(float, p)) for p in spec["polygon"]]
    elif "rect" in spec:
        w, h = map(float, spec["rect"])
        x0, y0 = map(float, spec.get("origin", [0, 0]))
        r = float(spec.get("corner_radius", 0))
        if r <= 0:
            pts = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
        else:
            steps = int(spec.get("arc_steps", 6))
            pts = []
            for cx, cy, a0 in ((x0 + w - r, y0 + r, -90), (x0 + w - r, y0 + h - r, 0), (x0 + r, y0 + h - r, 90),
                               (x0 + r, y0 + r, 180)):
                for k in range(steps + 1):
                    a = math.radians(a0 + 90 * k / steps)
                    pts.append((round(cx + r * math.cos(a), 4), round(cy + r * math.sin(a), 4)))
    else:
        raise ConfigError(f"board {name}: outline needs 'polygon' or 'rect'")
    if len(pts) < 3:
        raise ConfigError(f"board {name}: outline has fewer than three points")
    return pts


def _placement(ref, v):
    if isinstance(v, (list, tuple)):
        v = dict(zip(("x", "y", "rot", "side"), v))
    side = v.get("side", "top")
    if side not in LAYER_OF_SIDE:
        raise ConfigError(f"place.{ref}: side must be 'top' or 'bottom', not {side!r}")
    if not isinstance(v.get("auto", False), bool):
        raise ConfigError(f"place.{ref}: auto must be true or false")
    return Placement(float(v["x"]), float(v["y"]), float(v.get("rot", 0)), side, bool(v.get("lock", True)),
                     v.get("auto", False))


def _pours(name, pours, regions=False):
    """[[pours]] of the board file as written. A net with pour_only = true gets no tracks, its pour connects it: every
    entry of that net must say so, none may be a plane (a plane gets connections to make), and each gets its
    clearance_mm and min_width_mm. With regions (pour_regions), a layer that several nets pour on is shared out among
    them: no plane there (a plane takes the whole layer), and their clearance_mm and min_width_mm are used as well.
    fanout = true only on a plane: its SMD pads on the other layer get a via to it."""
    out = [dict(p) for p in pours]
    for p in out:
        if not isinstance(p.get("fanout", False), bool):
            raise ConfigError(f"board {name}: pour {p.get('net')}: fanout must be true or false")
        if p.get("fanout") and not p.get("plane"):
            raise ConfigError(f"board {name}: pour {p.get('net')}: fanout needs plane = true – the fanout vias connect "
                              "SMD pads on the other layer to a plane")
    only = {p.get("net") for p in out if p.get("pour_only")}
    for p in out:
        if p.get("net") not in only:
            continue
        if not p.get("pour_only"):
            raise ConfigError(f"board {name}: pour {p.get('net')} is pour_only in one entry but not in another – "
                              "set it on every entry of the net")
        if p.get("plane"):
            raise ConfigError(f"board {name}: pour {p['net']} cannot be pour_only and a plane – a plane gets tracks "
                              "and vias to it, a pour-only net none")
        for key, default in (("clearance_mm", POUR_CLEARANCE_MM), ("min_width_mm", POUR_MIN_WIDTH_MM)):
            p[key] = float(p.get(key, default))
            if p[key] < 0:
                raise ConfigError(f"board {name}: pour {p['net']}: {key} must not be negative")
    if regions:
        nets = {}  # layer -> nets that pour on it, as `pcb pour` pours them
        for p in out:
            for layer in p.get("layers", ["TOP", "BOTTOM"]):
                nets.setdefault(layer, set()).add(p.get("net"))
        for p in out:
            shared = [layer for layer in p.get("layers", ["TOP", "BOTTOM"]) if len(nets[layer]) > 1]
            if not shared:
                continue
            if p.get("plane"):
                raise ConfigError(f"board {name}: pour {p['net']} is a plane on {shared[0]}, which "
                                  f"{', '.join(sorted(n for n in nets[shared[0]] if n != p['net']))} pour on too – with "
                                  "pour_regions each net gets only its own area there; give the plane a layer of its "
                                  "own or drop plane")
            for key in ("clearance_mm", "min_width_mm"):
                if float(p.get(key, 0)) < 0:
                    raise ConfigError(f"board {name}: pour {p['net']}: {key} must not be negative")
    return out


def _net_classes(nc):
    """[net_classes] of a board file: classes sorted by falling min_a, and the nets forced into a class."""
    nc = dict(nc)
    force = nc.pop("force", {}) if isinstance(nc.get("force"), dict) else {}
    classes = {k: {"min_a": float(v["min_a"]), "width_mm": float(v["width_mm"])} for k, v in nc.items()} \
        or DEFAULT_NET_CLASSES
    return dict(sorted(classes.items(), key=lambda kv: -kv[1]["min_a"])), force


def _copper(name, c):
    """[copper] of a board file (L-15): max_bare_mm (largest copper-free circle on a poured layer, mm) and min_cover
    {layer: least copper share in % of the board area}; without it no share is required."""
    if not isinstance(c, dict):
        raise ConfigError(f"board {name}: [copper] must be a table")
    if lost := [k for k in c if k not in ("max_bare_mm", "min_cover")]:
        raise ConfigError(f"board {name}: [copper] unknown key '{lost[0]}' (known: max_bare_mm, min_cover)")
    bare = float(c.get("max_bare_mm", MAX_BARE_MM))
    if bare <= 0:
        raise ConfigError(f"board {name}: copper.max_bare_mm must be positive")
    cover = c.get("min_cover", {})
    if not isinstance(cover, dict) or not set(cover) <= {"TOP", "BOTTOM"} or not all(
            isinstance(v, (int, float)) and 0 <= v <= 100 for v in cover.values()):
        raise ConfigError(f"board {name}: copper.min_cover must be {{TOP = %, BOTTOM = %}} with values from 0 to 100")
    return {"max_bare_mm": bare, "min_cover": {k: float(v) for k, v in cover.items()}}


def silkscreen_on(mask):
    """The silkscreen colour JLCPCB prints on a solder mask colour: black on a white mask, white on every other."""
    return "black" if mask == "white" else "white"


def _order(name, o):
    """[order] of a board file, with its defaults; None without the table (no order form, no F-6)."""
    if o is None:
        return None
    if not isinstance(o, dict):
        raise ConfigError(f"board {name}: order must be a table ([order])")
    if bad := _unknown(f"board {name}: order", o, ORDER_KEYS):
        raise ConfigError(bad[0])
    for key in ("finish", "remark"):
        if not isinstance(o.get(key, ""), str):
            raise ConfigError(f"board {name}: order.{key} must be a string")
    if o.get("mark", "default") not in MARKS:
        raise ConfigError(f"board {name}: order.mark must be one of {', '.join(MARKS)}, not {o['mark']!r}")
    for key, known in (("mask", MASKS), ("silkscreen", SILKSCREENS)):
        if key in o and o[key] not in known:
            raise ConfigError(f"board {name}: order.{key} must be one of {', '.join(known)}, not {o[key]!r}")
    mask = o.get("mask", "green")
    if bad := _number(f"board {name}: order.tab_copper_mm", o.get("tab_copper_mm", 1.0)):
        raise ConfigError(bad[0])
    zones = o.get("tab_zones", [])
    if not isinstance(zones, list):
        raise ConfigError(f"board {name}: order.tab_zones must be a list of {{ from = [x, y], to = [x, y] }}")
    out = []
    for i, z in enumerate(zones, 1):
        where = f"board {name}: order.tab_zones {i}"
        if isinstance(z, dict) and (bad := _unknown(where, z, ("from", "to"))):
            raise ConfigError(bad[0])
        point = lambda p: isinstance(p, list) and len(p) == 2 and all(  # noqa: E731
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in p)
        if not isinstance(z, dict) or not point(z.get("from")) or not point(z.get("to")):
            raise ConfigError(f"{where}: needs from = [x, y] and to = [x, y] (plan mm, two points on the outline)")
        out.append((tuple(map(float, z["from"])), tuple(map(float, z["to"]))))
    return {"finish": o.get("finish", "LeadFree HASL"), "mark": o.get("mark", "default"), "remark": o.get("remark", ""),
            "tab_zones": out, "tab_copper_mm": float(o.get("tab_copper_mm", 1.0)),
            "mask": mask, "silkscreen": o.get("silkscreen", silkscreen_on(mask))}


def _board(name, entry, b, file=""):
    """A board: its EasyEDA documents from edakit.toml (entry), everything physical from its board file (b)."""
    tooling = b.get("tooling", {})
    view = b.get("view", "top")
    if view not in ("top", "bottom"):
        raise ConfigError(f"board {name}: view must be 'top' or 'bottom'")
    loops = [(lp["a"], lp["b"], float(lp["max_mm"]), lp.get("what", "")) for lp in b.get("loops", [])]
    classes, force = _net_classes(b.get("net_classes", {}))
    regions = b.get("pour_regions", False)
    if not isinstance(regions, bool):
        raise ConfigError(f"board {name}: pour_regions must be true or false")
    min_piece = float(b.get("pour_min_piece_mm2", POUR_MIN_PIECE_MM2))
    if min_piece < 0:
        raise ConfigError(f"board {name}: pour_min_piece_mm2 must not be negative")
    inset = float(b["pour_inset_mm"]) if b.get("pour_inset_mm") is not None else None
    if inset is not None and inset < 0:
        raise ConfigError(f"board {name}: pour_inset_mm must not be negative")
    on_headers = b.get("on_headers", [])
    if not isinstance(on_headers, list) or not all(isinstance(r, str) for r in on_headers):
        raise ConfigError(f"board {name}: on_headers must be a list of designators")
    header_keep = float(b.get("header_keep_mm", HEADER_KEEP_MM))
    if header_keep < 0:
        raise ConfigError(f"board {name}: header_keep_mm must not be negative")
    silk_overlap = float(b.get("silk_overlap_mm", 0.0))
    if silk_overlap < 0:
        raise ConfigError(f"board {name}: silk_overlap_mm must not be negative")
    if b.get("routing", {}).get("widths", "classes") not in ("classes", "sim"):
        raise ConfigError(f"board {name}: routing.widths must be 'classes' or 'sim'")
    uniform = b.get("uniform")
    if uniform is not None and not (isinstance(uniform, dict) and all(
            isinstance(k, str) and v in UNIFORM_WAYS for k, v in uniform.items())):
        raise ConfigError(f"board {name}: uniform must be a table of part kinds, each "
                          f"{' | '.join(repr(w) for w in UNIFORM_WAYS)} – e.g. uniform = {{ led = \"+x\", buzzer = \"-x\" }}")
    looks = b.get("looks")
    if looks is not None:
        def number(v, kind):
            return not isinstance(v, bool) and isinstance(v, kind) and v >= 0
        if not isinstance(looks, dict) or looks.get("visible") not in ("top", "bottom"):
            raise ConfigError(f"board {name}: [looks] needs visible = 'top' or 'bottom' – the side people look at")
        bad = [k for k in looks if k not in ("visible", "max_track_m", "max_vias")]
        if bad:
            raise ConfigError(f"board {name}: [looks] unknown key '{bad[0]}' (known: visible, max_track_m, max_vias)")
        if "max_track_m" in looks and not number(looks["max_track_m"], (int, float)):
            raise ConfigError(f"board {name}: looks.max_track_m must be a length in m, 0 or more")
        if "max_vias" in looks and not number(looks["max_vias"], int):
            raise ConfigError(f"board {name}: looks.max_vias must be a whole number, 0 or more")
    thickness = b.get("thickness_mm", THICKNESS_MM)
    if isinstance(thickness, bool) or not isinstance(thickness, (int, float)) or thickness <= 0:
        raise ConfigError(f"board {name}: thickness_mm must be a thickness in mm, more than 0")
    keep = b.get("routing", {}).get("hand_solder_keep_mm", 0)
    if isinstance(keep, bool) or not isinstance(keep, (int, float)) or keep < 0:
        raise ConfigError(f"board {name}: routing.hand_solder_keep_mm must be a distance in mm, 0 or more (0 = off)")
    silk = b.get("silk", {})
    if not isinstance(silk.get("solder_side", False), bool):
        raise ConfigError(f"board {name}: silk.solder_side must be true or false")
    if silk.get("board_label_side", "top") not in ("top", "bottom"):
        raise ConfigError(f"board {name}: silk.board_label_side must be 'top' or 'bottom'")
    unlabelled = silk.get("unlabelled", {})
    if not isinstance(unlabelled, dict) or not all(isinstance(v, str) and v.strip() for v in unlabelled.values()):
        raise ConfigError(f"board {name}: silk.unlabelled must be a table of designator = reason (L-17), "
                          "e.g. { R21 = \"no room between the star tracks\" }")
    region = silk.get("board_label_region")
    if region is not None and not (isinstance(region, list) and len(region) >= 3 and all(
            isinstance(p, list) and len(p) == 2 and all(isinstance(v, (int, float)) for v in p) for p in region)):
        raise ConfigError(f"board {name}: silk.board_label_region must be a polygon [[x, y], …] of at least 3 points "
                          "in plan mm")
    return Board(
        name=name,
        title=entry.get("title", name),
        template=entry.get("template", f"generated_{name}"),
        schematic=entry.get("schematic", f"layout_{name}"),
        pcb=entry.get("pcb", name),
        file=file,
        revision=str(b["revision"]) if b.get("revision") is not None else None,
        view=view,
        outline=_outline(b.get("outline"), name),
        holes=[{"x": float(h["x"]), "y": float(h["y"]), "d": float(h.get("d", 3.2)),
                "keep": float(h.get("keep", h.get("d", 3.2)))} for h in b.get("holes", [])],
        tooling=[tuple(map(float, t)) for t in tooling.get("holes", [])],
        tooling_d=float(tooling.get("d", 1.152)),
        tooling_mask=float(tooling.get("mask", 0.148)),
        tooling_keep=float(tooling.get("keep", 1.5)),
        place={ref: _placement(ref, v) for ref, v in b.get("place", {}).items()},
        near={k: [v] if isinstance(v, str) else list(v) for k, v in b.get("near", {}).items()},
        near_mm=float(b.get("near_mm", 6.0)),
        edge_mm=float(b.get("edge_mm", 1.0)),
        edge_ok=set(b.get("edge_ok", [])),
        on_headers=set(on_headers),
        header_keep_mm=header_keep,
        silk_overlap_mm=silk_overlap,
        park=tuple(map(float, b.get("park", [10, -15]))),
        routing=b.get("routing", {}),
        pours=_pours(name, b.get("pours", [{"net": "GND", "layers": ["TOP", "BOTTOM"]}]), regions),
        pour_regions=regions,
        pour_min_piece_mm2=min_piece,
        pour_inset_mm=inset,
        silk=silk,
        loops=loops,
        net_classes=classes,
        force_class=force,
        copper=_copper(name, b.get("copper", {})),
        order=_order(name, b.get("order")),
        uniform=dict(uniform) if uniform is not None else None,
        looks=dict(looks) if looks is not None else None,
        thickness_mm=float(thickness),
        bought=entry.get("bought", False),
    )


def _read(path):
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from None


def _unknown(where, table, known, moved=()):
    return [f"{where}: unknown key '{k}' (known: {', '.join(known)})" for k in table if k not in known + tuple(moved)]


def _one_file_form(raw, name):
    """What edakit.toml in the one-file form still holds, each with the place it has now."""
    project, release = raw.get("project", {}), raw.get("release", {})
    out = []
    for b, entry in raw.get("boards", {}).items():
        keys = [k for k in entry if k in BOARD_FILE_KEYS]
        if keys:
            out.append(f"[boards.{b}] {', '.join(keys)} -> {entry.get('file', f'hardware/boards/{b}.toml')}, "
                       f"without the prefix 'boards.{b}.'")
    if "schematic" in raw:
        out.append(f"[schematic] -> {project.get('schematic', 'hardware/schematic.toml')}, without the prefix "
                   f"'schematic.'")
    if "checks" in raw:
        out.append('[checks] -> "checks" in the graph (pin_locks, reverse_protect, doc_pin_table)')
    if "ground" in project:
        out.append('[project] ground -> "ground" in the graph (default GND)')
    if "net_classes" in raw:
        out.append("[net_classes] -> [net_classes] in each board file")
    if "sim" in raw:
        out.append("[sim] config, plugin -> [project] sim, sim_plugin")
    if "signoff" in release:
        out.append("[release] signoff -> [project] signoff")
    if name in release.get("layout_files", []):
        out.append(f"[release] layout_files: drop {name} – the board files are in the layout hash, {name} in none")
    return out


def _number(where, v, integer=False, positive=False):
    ok = isinstance(v, int) if integer else isinstance(v, (int, float))
    if isinstance(v, bool) or not ok or v < 0 or (positive and v == 0):
        return [f"{where} must be a{' whole' if integer else ''} number {'> 0' if positive else '>= 0'}, not {v!r}"]
    return []


def _project_values(p):
    out = []
    for key in ("stock_margin_pct", "spare_pct"):
        if key in p:
            out += _number(f"[project] {key}", p[key])
    if "stock_max_age_days" in p:
        out += _number("[project] stock_max_age_days", p["stock_max_age_days"], integer=True)
    return out


def _release_values(release):
    a = release.get("assembly", {})
    if "pcba" in a and a["pcba"] not in PCBA:
        return [f"[release] assembly.pcba must be one of {', '.join(PCBA)}, not {a['pcba']!r}"]
    return []


def _cost_values(cost):
    if cost is None:
        return []
    if not isinstance(cost, dict):
        return ["[cost] must be a table"]
    out = _unknown("[cost]", cost, COST_KEYS)
    for key in ("budget", "shipping", "coupon", "vat_pct"):
        if key in cost:
            out += _number(f"[cost] {key}", cost[key])
    rates = cost.get("rates", {})
    if not isinstance(rates, dict):
        out.append("[cost] rates must be a table, e.g. { EUR = 1.15 } (value of one unit in [cost] currency)")
    else:
        out += [m for k, v in rates.items() for m in _number(f"[cost] rates.{k}", v, positive=True)]
    price = cost.get("pcb_price")
    if isinstance(price, dict):
        out += [m for k, v in price.items() for m in _number(f"[cost] pcb_price.{k}", v)]
    elif price is not None:
        out += _number("[cost] pcb_price", price)
    return out


def _extras(extras):
    if extras is None:
        return []
    if not isinstance(extras, list) or not all(isinstance(e, dict) for e in extras):
        return ["[[extra]] must be an array of tables: [[extra]] item = …, supplier = …, per_set = …"]
    out = []
    for i, e in enumerate(extras, 1):
        where = f"[[extra]] {i} ({e.get('item', '?')})"
        out += _unknown(where, e, EXTRA_KEYS)
        out += [f"{where}: {k} is missing" for k in ("item", "supplier", "per_set") if k not in e]
        if "per_set" in e:
            out += _number(f"{where}: per_set", e["per_set"], positive=True)
        if "unit_price" in e:
            out += _number(f"{where}: unit_price", e["unit_price"])
        if "spare" in e:
            out += _number(f"{where}: spare", e["spare"], integer=True)
        for key in ("moq", "step"):
            if key in e:
                out += _number(f"{where}: {key}", e[key], integer=True, positive=True)
    return out


def _firmware(fw):
    """[firmware]: mcu (default: the one part with GPIO pins), out (the contract), gpio (regex for the GPIO number in
    the MCU pin's name: its first group, default the first number)."""
    out = {"mcu": fw.get("mcu"), "out": fw.get("out", "hardware/firmware.json"), "gpio": fw.get("gpio", r"(\d+)")}
    try:
        if re.compile(out["gpio"]).groups < 1:
            raise ConfigError("[firmware] gpio: the regex needs a group, the GPIO number – e.g. 'GP(\\d+)'")
    except re.error as e:
        raise ConfigError(f"[firmware] gpio: {e}") from None
    return out


def _scripts(scripts):
    """[scripts.<name>]: (entries as written, problems). Here only their form – known keys, strings, lists of strings;
    whether they resolve with edakit's steps into one order is edakit check's (edakit/scripts.py)."""
    if scripts is None:
        return {}, []
    if not isinstance(scripts, dict):
        return {}, ["[scripts] must be tables [scripts.<name>] with kind, cmd, about, …"]
    out, problems = {}, []
    lists = {"cmd": "strings: the command and its arguments", "check": "strings: the command and its arguments",
             "reads": "data names and paths", "writes": "data names and paths", "after": "script names"}
    for name, s in scripts.items():
        where = f"[scripts.{name}]"
        if not isinstance(s, dict):
            problems.append(f"[scripts] {name}: a table [scripts.{name}] with kind, cmd, about, … – not a value")
            continue
        problems += _unknown(where, s, SCRIPT_KEYS)
        problems += [f"{where} {k} must be a string" for k in ("kind", "about", "id", "phase", "at")
                     if k in s and not isinstance(s[k], str)]
        problems += [f"{where} {k} must be a list of {what}" for k, what in lists.items()
                     if k in s and not (isinstance(s[k], list) and all(isinstance(v, str) and v for v in s[k]))]
        if not isinstance(s.get("advisory", False), bool):
            problems.append(f"{where} advisory: true or false")
        out[name] = dict(s)
    return out, problems


def _requirements(p, root):
    """[project] requirements: the requirements file of `edakit req` – a path, or a list of paths: a variant names the
    main project's file and its own. Relative to edakit.toml. Returns (paths, problems); without the key no file."""
    value = p.get("requirements", [])
    names = [value] if isinstance(value, str) else value
    if not isinstance(names, list) or not all(isinstance(n, str) and n.strip() for n in names):
        return [], ['[project] requirements: a path or a list of paths, e.g. "hardware/requirements.toml"; a variant '
                    'names the main project\'s file and its own: ["../../hardware/requirements.toml", '
                    '"hardware/requirements.toml"]']
    paths = [Path(n) if Path(n).is_absolute() else root / n for n in names]
    seen, problems = set(), []
    for name, path in zip(names, paths):
        if path.resolve() in seen:
            problems.append(f"[project] requirements: {name} named twice")
        seen.add(path.resolve())
    return paths, problems


def find_config(start=None) -> Path:
    env = os.environ.get("EDAKIT_CONFIG")
    if env:
        return Path(env).resolve()
    here = Path(start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if (d / "edakit.toml").is_file():
            return d / "edakit.toml"
    raise ConfigError("no edakit.toml found (current directory and its parents); see handbook/02-setup.md")


def load(path=None) -> Config:
    path = Path(path).resolve() if path else find_config()
    raw = _read(path)
    root = path.parent
    p = raw.get("project", {})
    if "name" not in p:
        raise ConfigError(f"{path}: [project] name (the EasyEDA project) is missing")

    def rel(key, default):
        v = Path(p.get(key, default))
        return v if v.is_absolute() else root / v

    moved = _one_file_form(raw, path.name)
    problems = _unknown(path.name, raw, ("project", "boards", "release", "cost", "extra", "firmware", "docs",
                                         "scripts"),
                        ("schematic", "checks", "net_classes", "sim"))
    problems += _unknown("[project]", p, PROJECT_KEYS, ("ground",))
    problems += _unknown("[release]", raw.get("release", {}), RELEASE_KEYS, ("signoff",))
    ignore = raw.get("release", {}).get("hash_ignore", [])
    if not isinstance(ignore, list) or not all(isinstance(k, str) and k for k in ignore):
        problems.append('[release] hash_ignore: a list of key names, e.g. ["notes", "sources"]')
    problems += _unknown("[firmware]", raw.get("firmware", {}), FIRMWARE_KEYS)
    if not isinstance(p.get("agreements", True), bool):
        problems.append("[project] agreements: true or false")
    requirements, bad = _requirements(p, root)
    problems += bad
    problems += _unknown("[docs]", raw.get("docs", {}), DOCS_KEYS)
    doc_files = raw.get("docs", {}).get("files", [])
    if not isinstance(doc_files, list) or not all(isinstance(f, str) for f in doc_files):
        problems.append("[docs] files must be a list of paths")
    if raw.get("docs", {}).get("decimal", ".") not in (".", ","):
        problems.append('[docs] decimal must be "." or ","')

    scripts, bad = _scripts(raw.get("scripts"))       # [scripts.<name>]: their form; the order is edakit check's
    problems += bad

    files = {}
    for name, entry in raw.get("boards", {}).items():
        problems += _unknown(f"[boards.{name}]", entry, BOARD_KEYS, BOARD_FILE_KEYS)
        file = entry.get("file", f"hardware/boards/{name}.toml")
        bought = entry.get("bought", False)
        if not isinstance(bought, bool):
            problems.append(f"[boards.{name}] bought: true or false")
        if bought is True:     # made by nobody: no EasyEDA documents, no board file
            problems += [f"[boards.{name}] {k}: a bought board is not drawn – no schematic, PCB or board file"
                         for k in ("template", "schematic", "pcb", "file") if k in entry]
            if "file" not in entry and (root / file).exists():
                problems.append(f"{file}: a bought board (bought = true in [boards.{name}]) has no board file")
            files[name] = (file, {})
            continue
        if (root / file).exists():
            files[name] = (file, _read(root / file))
        elif "file" in entry:
            raise ConfigError(f"{path}: [boards.{name}] file: {file} not found")
        else:
            files[name] = (file, {})       # no layout yet: the PCB designer starts the board file
        problems += [f"{file}: {k} belongs in {path.name} [boards.{name}]" for k in files[name][1] if k in BOARD_KEYS]
        problems += _unknown(file, files[name][1], BOARD_FILE_KEYS, BOARD_KEYS)
    schematic_file = rel("schematic", "hardware/schematic.toml")
    schematic = _read(schematic_file) if schematic_file.exists() else {}
    problems += _unknown(p.get("schematic", "hardware/schematic.toml"), schematic, SCHEMATIC_KEYS)
    if moved:
        problems = moved + problems + [
            f"{path.name} is the table of contents now: board, schematic and checks have files of their own "
            "(handbook 10.1)"]
    problems += _project_values(p) + _release_values(raw.get("release", {}))
    problems += _cost_values(raw.get("cost")) + _extras(raw.get("extra"))
    if problems:
        raise ConfigError(f"{path}:\n  " + "\n  ".join(problems))
    boards = {name: _board(name, raw["boards"][name], data, file) for name, (file, data) in files.items()}
    if not boards:
        raise ConfigError(f"{path}: at least one [boards.<name>] section is needed")
    return Config(
        path=path, root=root, project=p["name"],
        graph=rel("graph", "hardware/graph.json"),
        parts=rel("parts", "hardware/parts"),
        sim_config=rel("sim", "hardware/sim.json"),
        sim_plugin=rel("sim_plugin", "") if p.get("sim_plugin") else None,
        schematic_file=schematic_file,
        signoff=rel("signoff", "hardware/signoff.json"),
        artifacts=rel("artifacts", "build/edakit"),
        reports=rel("reports", "build/release"),
        datasheets=rel("datasheets", Path(p.get("artifacts", "build/edakit")) / "datasheets"),
        company=p.get("company", ""),
        quantity=int(p.get("quantity", 5)),
        boards=boards,
        schematic=schematic,
        release=raw.get("release", {}),
        lock=p.get("lock", "auto"),
        agreements=p.get("agreements", True),
        raw=raw,
        requirements=requirements,
        stock=rel("stock", "hardware/stock.json"),
        stock_margin_pct=float(p.get("stock_margin_pct", 0)),
        stock_max_age_days=int(p.get("stock_max_age_days", STOCK_MAX_AGE_DAYS)),
        cost=raw.get("cost"),
        spare_pct=float(p.get("spare_pct", 0)),
        extras=list(raw.get("extra", [])),
        firmware=_firmware(raw["firmware"]) if "firmware" in raw else None,
        scripts=scripts,
        docs=list(doc_files),
        docs_decimal=raw.get("docs", {}).get("decimal", "."),
    )
