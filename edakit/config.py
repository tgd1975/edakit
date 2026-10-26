"""Project configuration: edakit.toml and the files it points to.

edakit.toml is the table of contents: the project, its boards with their EasyEDA documents, where the files are, and
the release settings. What one role decides lives in a file of its own, with one owner and one hash (handbook 10.1):

    hardware/graph.json           circuit, purpose, hand-over, ground net, check settings  circuit designer  circuit
    hardware/parts/, sim.json     parts database, simulation scenarios                     circuit designer  circuit
    hardware/schematic.toml       arrangement of the schematic: blocks, notes, pin table   circuit designer  –
    hardware/boards/<name>.toml   outline, holes, placement, routing, pours, silk          PCB designer      layout

The tools themselves contain no project knowledge. edakit.toml in the one-file form – board, schematic and checks
inside – is refused with a list of what goes where.

Lookup order: --config PATH, $EDAKIT_CONFIG, then edakit.toml in the current directory or one of its parents.
All relative paths are relative to the directory that contains edakit.toml.
"""

from __future__ import annotations

import math
import os
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

PROJECT_KEYS = ("name", "company", "quantity", "distributors", "lock", "graph", "parts", "sim", "sim_plugin",
                "schematic", "signoff", "artifacts", "reports")
BOARD_KEYS = ("title", "template", "schematic", "pcb", "file")            # [boards.<name>] in edakit.toml
BOARD_FILE_KEYS = ("revision", "view", "outline", "holes", "tooling", "place", "near", "near_mm", "edge_mm", "edge_ok",
                   "park", "routing", "pours", "silk", "loops", "net_classes")
SCHEMATIC_KEYS = ("stub", "layout")
RELEASE_KEYS = ("layout_files", "state_files", "assembly", "stages")


class ConfigError(Exception):
    pass


@dataclass
class Placement:
    x: float
    y: float
    rot: float = 0.0
    side: str = "top"           # EasyEDA side the part sits on: "top" or "bottom"
    lock: bool = True


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
    park: tuple = (10.0, -15.0)                       # where `pcb parts --write` drops new parts (mm, EasyEDA)
    routing: dict = field(default_factory=dict)
    pours: list = field(default_factory=list)
    silk: dict = field(default_factory=dict)
    loops: list = field(default_factory=list)         # [(pad a, pad b, max mm, what)] short current loops (L-11)
    net_classes: dict = field(default_factory=lambda: dict(DEFAULT_NET_CLASSES))  # by falling min_a
    force_class: dict = field(default_factory=dict)   # net -> class, whatever its current

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
    company: str
    quantity: int
    boards: dict
    schematic: dict             # the schematic file: stub, [layout]
    release: dict
    lock: str
    raw: dict

    def board(self, name=None) -> Board:
        if name is None:
            if len(self.boards) != 1:
                raise ConfigError(f"several boards ({', '.join(self.boards)}) – pick one with --board")
            return next(iter(self.boards.values()))
        if name not in self.boards:
            raise ConfigError(f"board '{name}' is not in {self.path.name} (known: {', '.join(self.boards)})")
        return self.boards[name]

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
    return Placement(float(v["x"]), float(v["y"]), float(v.get("rot", 0)), side, bool(v.get("lock", True)))


def _pours(name, pours):
    """[[pours]] of the board file as written. A net with pour_only = true gets no tracks, its pour connects it: every
    entry of that net must say so, none may be a plane (a plane gets connections to make), and each gets its
    clearance_mm and min_width_mm."""
    out = [dict(p) for p in pours]
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
    return out


def _net_classes(nc):
    """[net_classes] of a board file: classes sorted by falling min_a, and the nets forced into a class."""
    nc = dict(nc)
    force = nc.pop("force", {}) if isinstance(nc.get("force"), dict) else {}
    classes = {k: {"min_a": float(v["min_a"]), "width_mm": float(v["width_mm"])} for k, v in nc.items()} \
        or DEFAULT_NET_CLASSES
    return dict(sorted(classes.items(), key=lambda kv: -kv[1]["min_a"])), force


def _board(name, entry, b, file=""):
    """A board: its EasyEDA documents from edakit.toml (entry), everything physical from its board file (b)."""
    tooling = b.get("tooling", {})
    view = b.get("view", "top")
    if view not in ("top", "bottom"):
        raise ConfigError(f"board {name}: view must be 'top' or 'bottom'")
    loops = [(lp["a"], lp["b"], float(lp["max_mm"]), lp.get("what", "")) for lp in b.get("loops", [])]
    classes, force = _net_classes(b.get("net_classes", {}))
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
        park=tuple(map(float, b.get("park", [10, -15]))),
        routing=b.get("routing", {}),
        pours=_pours(name, b.get("pours", [{"net": "GND", "layers": ["TOP", "BOTTOM"]}])),
        silk=b.get("silk", {}),
        loops=loops,
        net_classes=classes,
        force_class=force,
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
    problems = _unknown(path.name, raw, ("project", "boards", "release"), ("schematic", "checks", "net_classes", "sim"))
    problems += _unknown("[project]", p, PROJECT_KEYS, ("ground",))
    problems += _unknown("[release]", raw.get("release", {}), RELEASE_KEYS, ("signoff",))
    files = {}
    for name, entry in raw.get("boards", {}).items():
        problems += _unknown(f"[boards.{name}]", entry, BOARD_KEYS, BOARD_FILE_KEYS)
        file = entry.get("file", f"hardware/boards/{name}.toml")
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
            "(handbook 10.1); scripts/split_config.py of edakit moves a project once, its sign-offs with it"]
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
        company=p.get("company", ""),
        quantity=int(p.get("quantity", 5)),
        boards=boards,
        schematic=schematic,
        release=raw.get("release", {}),
        lock=p.get("lock", "auto"),
        raw=raw,
    )
