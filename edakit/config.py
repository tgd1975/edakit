"""Project configuration: edakit.toml in the project root.

Everything that differs between projects lives here (or in the files it points to): where the graph and the parts
database are, the boards with their EasyEDA document names, the placement plan, routing rules, schematic blocks,
simulation scenarios and release settings. The tools themselves contain no project knowledge.

Lookup order: --config PATH, $EDAKIT_CONFIG, then edakit.toml in the current directory or one of its parents.
All relative paths in the file are relative to the directory that contains it.
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
    edge_ok: set = field(default_factory=set)         # parts allowed to touch or overhang the outline
    park: tuple = (10.0, -15.0)                       # where `pcb parts --write` drops new parts (mm, EasyEDA)
    routing: dict = field(default_factory=dict)
    pours: list = field(default_factory=list)
    silk: dict = field(default_factory=dict)
    loops: list = field(default_factory=list)         # [(pad a, pad b, max mm, what)] short current loops (L-11)

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
    artifacts: Path
    reports: Path
    company: str
    ground: str
    quantity: int
    boards: dict
    net_classes: dict
    force_class: dict
    schematic: dict
    sim: dict
    checks: dict
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


def _board(name, b):
    tooling = b.get("tooling", {})
    view = b.get("view", "top")
    if view not in ("top", "bottom"):
        raise ConfigError(f"board {name}: view must be 'top' or 'bottom'")
    loops = [(lp["a"], lp["b"], float(lp["max_mm"]), lp.get("what", "")) for lp in b.get("loops", [])]
    return Board(
        name=name,
        title=b.get("title", name),
        template=b.get("template", f"generated_{name}"),
        schematic=b.get("schematic", f"layout_{name}"),
        pcb=b.get("pcb", name),
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
        edge_ok=set(b.get("edge_ok", [])),
        park=tuple(map(float, b.get("park", [10, -15]))),
        routing=b.get("routing", {}),
        pours=b.get("pours", [{"net": "GND", "layers": ["TOP", "BOTTOM"]}]),
        silk=b.get("silk", {}),
        loops=loops,
    )


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
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from None
    root = path.parent
    p = raw.get("project", {})
    if "name" not in p:
        raise ConfigError(f"{path}: [project] name (the EasyEDA project) is missing")

    def rel(key, default):
        v = Path(p.get(key, default))
        return v if v.is_absolute() else root / v

    boards = {name: _board(name, b) for name, b in raw.get("boards", {}).items()}
    if not boards:
        raise ConfigError(f"{path}: at least one [boards.<name>] section is needed")
    nc = raw.get("net_classes", {})
    force = nc.pop("force", {}) if isinstance(nc.get("force"), dict) else {}
    classes = {k: {"min_a": float(v["min_a"]), "width_mm": float(v["width_mm"])} for k, v in nc.items()} \
        or DEFAULT_NET_CLASSES
    return Config(
        path=path, root=root, project=p["name"],
        graph=rel("graph", "hardware/graph.json"),
        parts=rel("parts", "hardware/parts"),
        artifacts=rel("artifacts", "build/edakit"),
        reports=rel("reports", "build/release"),
        company=p.get("company", ""),
        ground=p.get("ground", "GND"),
        quantity=int(p.get("quantity", 5)),
        boards=boards,
        net_classes=dict(sorted(classes.items(), key=lambda kv: -kv[1]["min_a"])),
        force_class=force,
        schematic=raw.get("schematic", {}),
        sim=raw.get("sim", {}),
        checks=raw.get("checks", {}),
        release=raw.get("release", {}),
        lock=p.get("lock", "auto"),
        raw=raw,
    )
