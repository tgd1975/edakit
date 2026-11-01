"""Pictures of a gate run (handbook 8.3): the circuit and the board as SVG and PNG in <run>/pictures/, linked in section 12
of the protocol and published with the release (publish.py).

    schematic_<board>.svg|png        edakit's drawing of the board's circuit, as `edakit schematic draw` writes it –
                                     every run, every board but a bought one
    board_<board>_top.svg|png        the board as made, from the run's Gerber and drill files: solder mask, silkscreen
    board_<board>_bottom.svg|png     and finish in the colours of the run's order settings (order.json; without them
                                     edakit's defaults: green, white, HASL), copper under the mask a shade of it; the
                                     bottom seen from below, mirrored – with stage F
    board_<board>_layers.svg|png     the copper layers and silkscreens over each other, seen from above, in the colours
                                     of the EasyEDA editor (EDITOR): the bottom under the top and showing through it,
                                     through-hole pads, holes and outline – with stage F
    board_<board>_<layer>.svg|png    every Gerber layer and drill file the maker builds from on its own, as the file
                                     draws it (seen from above), the board's outline faint – with stage F
    pictures.json                    {board: [{name, caption}]} – what the protocol and publish show

Pictures are documentation: in no hash, and a picture that cannot be drawn is named in the protocol while the gate goes
on. The board's SVG is at scale (1 mm on paper = 1 mm of board), its PNG PX_PER_MM pixels a millimetre.
"""

from __future__ import annotations

import contextlib
import io
import json
from dataclasses import dataclass
from pathlib import Path

from .. import gerber
from ..config import order_defaults, silkscreen_on
from .fab import built_files, gerber_role

DIR = "pictures"
INDEX = "pictures.json"
SCHEMATIC_DPI = 300      # the schematic's PNG: 3 pixels a unit of the drawing
PX_PER_MM = 40           # the board's PNG: pixels a millimetre …
MAX_PX = 4000            # … at most this many on its longer side
MARGIN_MM = 2.0          # white around the board
MASK = {"green": "#1a7a3c", "purple": "#5b2a86", "red": "#b3202a", "yellow": "#d9b700", "blue": "#1f4fa3",
        "white": "#f0f0f0", "black": "#1c1c1c"}      # config.MASKS
SILK = {"white": "#fafafa", "black": "#141414"}       # config.SILKSCREENS
FINISH = {"ENIG": "#d4a537"}                          # every other finish is a HASL: SILVER
SILVER = "#c4c4c4"
COPPER = "#b87333"
SUBSTRATE = "#cdbb83"    # FR-4 where the mask is open and there is no copper
BACKGROUND = "#ffffff"   # around the board and through its holes
EDGE = "#7a7a7a"         # the board's edge
LAYER = {"copper": COPPER, "mask": "#2e7d4f", "silk": "#202020", "paste": "#808080", "outline": "#000000",
         "drill": "#000000", None: "#404040"}
EDITOR = {"background": "#000000", "silk bottom": ("#66cc33", 0.9), "copper bottom": ("#0000ff", 0.55),
          "copper top": ("#ff0000", 0.8), "pad": "#a0a0a0", "silk top": "#ffcc00", "hole": "#141414",
          "outline": "#cc00cc"}  # the layers picture: the EasyEDA editor's colours, (colour, opacity) bottom to top
STACK = {("silk", "top"): 0, ("mask", "top"): 1, ("paste", "top"): 2, ("copper", "top"): 3, ("copper", "bottom"): 5,
         ("paste", "bottom"): 6, ("mask", "bottom"): 7, ("silk", "bottom"): 8, "outline": 9}   # inner copper: 4


@dataclass
class Shot:
    name: str        # file name in pictures/ without .svg and .png
    caption: str


@dataclass
class View:
    """Where the board's PNG puts a point: x0 and y1 the picture's left and top edge in mm (the bottom view's x
    mirrored), ppm pixels a millimetre."""
    x0: float
    y1: float
    ppm: float
    size: tuple
    mirror: bool = False

    def pixel(self, x, y):
        """(column, row) of the point (x, y) mm of the board."""
        return int(((-x if self.mirror else x) - self.x0) * self.ppm), int((self.y1 - y) * self.ppm)


def mix(a, b, t):
    """The colour a with the part t of b in it, as #rrggbb."""
    ca, cb = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def under_mask(mask):
    """Copper under the solder mask: the mask's colour with some of the copper's."""
    return mix(mask, COPPER, 0.35)


def colours(fab_dir):
    """(mask, silkscreen, finish) as colours: the run's order settings (order.json) – what the board is made with –,
    without them edakit's defaults."""
    o = order_defaults()
    f = Path(fab_dir) / "order.json"
    if f.is_file():
        o.update(json.loads(f.read_text(encoding="utf-8")))
    mask = o.get("mask") or "green"
    silk = o.get("silkscreen") or silkscreen_on(mask)
    return MASK.get(mask, MASK["green"]), SILK.get(silk, SILK["white"]), FINISH.get(o.get("finish"), SILVER)


# --- geometry -----------------------------------------------------------------------------------------------------

def layers(g):
    """{role: Gerber file} of a gerber folder's built layers (fab.gerber_role); inner copper as ("copper", "inner n")."""
    return {gerber_role(f) or f.stem: f for f in built_files(g)[0]}


def area(f):
    from shapely.geometry import Polygon
    return gerber.shape(gerber.parse_gerber(f)) if f else Polygon()


def holes(files):
    """Every hole of these drill files as one area (mm): round ones and slots."""
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union
    return unary_union([Point(x0, y0).buffer(w / 2) if (x0, y0) == (x1, y1) else
                        LineString([(x0, y0), (x1, y1)]).buffer(w / 2)
                        for f in files for x0, y0, x1, y1, w in gerber.parse_drills(f)])


def outline(g):
    """The board as an area: the outline's closed paths (gerber.outline_shape, without its holes and cut-outs) – without
    a closed path the box around every layer."""
    from shapely.geometry import box
    board = gerber.outline_shape(g)
    if board is not None and not board.is_empty:
        return board
    pts = [p for f in built_files(g)[0] for p in gerber.points(gerber.parse_gerber(f))]
    return box(*gerber.bbox(pts)) if pts else None


def board_view(g, side):
    """The View of the board's pictures of this side: the outline's box and MARGIN_MM around it."""
    board = outline(g)
    x0, y0, x1, y1 = board.bounds if board is not None else (0, 0, 10, 10)
    if side == "bottom":
        x0, x1 = -x1, -x0
    w, h = x1 - x0 + 2 * MARGIN_MM, y1 - y0 + 2 * MARGIN_MM
    ppm = min(PX_PER_MM, MAX_PX / max(w, h))
    return View(x0 - MARGIN_MM, y1 + MARGIN_MM, ppm, (round(w * ppm), round(h * ppm)), side == "bottom")


def as_made(g, side):
    """[(area, colour)] of one side as the board is made, bottom first: the board in the mask's colour, copper under
    the mask, the mask's openings – the finish on copper, FR-4 beside it –, the silkscreen off the openings, the holes."""
    mask_c, silk_c, finish_c = colours(Path(g).parent)
    found = layers(g)
    board = outline(g)
    if board is None:
        raise ValueError("no outline and no layer")
    cu = area(found.get(("copper", side))) & board
    op = area(found.get(("mask", side))) & board
    silk = (area(found.get(("silk", side))) - op) & board
    return [(board, mask_c), (cu - op, under_mask(mask_c)), (op - cu, SUBSTRATE), (op & cu, finish_c),
            (silk, silk_c), (holes(built_files(g)[1]), BACKGROUND)]


def through_hole_pads(g):
    """The through-hole pads as an area: the pieces of top copper open in the top mask that hold a plated hole (a drill
    file without NPTH in its name) – a tented via is no pad."""
    from shapely.geometry import Point
    from shapely.ops import unary_union
    found = layers(g)
    centres = [Point(x0, y0) for f in built_files(g)[1] if "NPTH" not in f.name.upper()
               for x0, y0, *_ in gerber.parse_drills(f)]
    pieces = polygons(area(found.get(("copper", "top"))) & area(found.get(("mask", "top"))))
    return unary_union([p for p in pieces if any(p.intersects(c) for c in centres)])


def all_layers(g):
    """[(area, colour[, opacity])] of the layers picture, bottom first, as the EasyEDA editor shows the board from
    above: bottom silkscreen, bottom copper, top copper – each letting what lies under it show through –, the
    through-hole pads, top silkscreen, holes."""
    found = layers(g)
    return [(area(found.get(("silk", "bottom"))), *EDITOR["silk bottom"]),
            (area(found.get(("copper", "bottom"))), *EDITOR["copper bottom"]),
            (area(found.get(("copper", "top"))), *EDITOR["copper top"]),
            (through_hole_pads(g), EDITOR["pad"]),
            (area(found.get(("silk", "top"))), EDITOR["silk top"]),
            (holes(built_files(g)[1]), EDITOR["hole"])]


# --- drawing ------------------------------------------------------------------------------------------------------

def polygons(geom):
    """The polygons of a shapely geometry, exterior anticlockwise and holes clockwise (filled right by any rule)."""
    from shapely.geometry.polygon import orient
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [orient(geom)]
    return [p for part in getattr(geom, "geoms", []) for p in polygons(part)]


def patch(geom, colour, alpha=1.0):
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath
    verts, codes = [], []
    for poly in polygons(geom):
        for ring in (poly.exterior, *poly.interiors):
            pts = list(ring.coords)
            verts += pts
            codes += [MPath.MOVETO] + [MPath.LINETO] * (len(pts) - 2) + [MPath.CLOSEPOLY]
    return PathPatch(MPath(verts, codes), facecolor=colour, edgecolor="none", lw=0,
                     alpha=alpha) if verts else None


def save(view, shapes, edge, out, name, background=BACKGROUND, edge_colour=EDGE):
    """shapes [(area, colour)] – or (area, colour, opacity) – in this order, the board's edge as a thin line over them,
    into out/name.svg and .png."""
    import matplotlib
    from matplotlib.figure import Figure
    from shapely import affinity
    w, h = view.size[0] / view.ppm, view.size[1] / view.ppm
    flip = (lambda geom: affinity.scale(geom, xfact=-1, yfact=1, origin=(0, 0))) if view.mirror else (lambda geom: geom)
    with matplotlib.rc_context({"svg.hashsalt": "edakit", "svg.fonttype": "path"}):
        fig = Figure(figsize=(w / 25.4, h / 25.4), dpi=view.ppm * 25.4, facecolor=background)
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set_xlim(view.x0, view.x0 + w)
        ax.set_ylim(view.y1 - h, view.y1)
        ax.axis("off")
        for geom, colour, *alpha in shapes:
            p = patch(flip(geom), colour, *alpha)
            if p is not None:
                ax.add_patch(p)
        if edge is not None:
            for poly in polygons(flip(edge)):
                for ring in (poly.exterior, *poly.interiors):
                    ax.plot(*ring.xy, color=edge_colour, lw=0.5, solid_joinstyle="round")
        fig.savefig(out / f"{name}.svg", facecolor=background, metadata={"Date": None})
        fig.savefig(out / f"{name}.png", dpi=view.ppm * 25.4, facecolor=background, metadata={"Software": None})


def layer_name(role, f):
    """(name, caption) of a layer picture: copper_top "copper, top", copper_inner1 "copper, inner 1", outline,
    drill_<file> "drill file <file>"."""
    if f.name.startswith("Drill_"):
        what = f.stem.removeprefix("Drill_")
        return f"drill_{what.lower()}", f"drill file {what}"
    if isinstance(role, tuple):
        return f"{role[0]}_{role[1].replace(' ', '')}", f"{role[0]}, {role[1]}"
    return (role, role) if role == "outline" else (f.stem.removeprefix("Gerber_").lower(), f.stem)


def stack_key(item):
    role = item[0]
    return (STACK.get(role, 4 if isinstance(role, tuple) and role[1].startswith("inner") else 10),
            str(role[1]) if isinstance(role, tuple) else "")


def board_pictures(run, board):
    """The pictures of one board from <run>/fab/<board>/gerber into <run>/pictures: ([Shot], [what was not drawn]) –
    as made, top and bottom, all layers over each other, then every layer and drill file on its own."""
    g = Path(run) / "fab" / board / "gerber"
    out = Path(run) / DIR
    out.mkdir(parents=True, exist_ok=True)
    shots, notes = [], []
    edge = outline(g)

    def one(name, caption, draw):
        try:
            draw(name)
        except Exception as e:    # a picture is documentation: named in the protocol, the gate goes on
            notes.append(f"{name}: not drawn – {type(e).__name__}: {e}")
            return
        shots.append(Shot(name, caption))
    for side, caption in (("top", "top"), ("bottom", "bottom, seen from below")):
        one(f"board_{board}_{side}", f"{board}, {caption}",
            lambda name, side=side: save(board_view(g, side), as_made(g, side), edge, out, name))
    one(f"board_{board}_layers", f"{board}, all layers from above",
        lambda name: save(board_view(g, "top"), all_layers(g), edge, out, name, EDITOR["background"], EDITOR["outline"]))
    files = sorted(layers(g).items(), key=stack_key) + [(None, f) for f in built_files(g)[1]]
    for role, f in files:
        name, caption = layer_name(role, f)
        kind = "drill" if role is None else role[0] if isinstance(role, tuple) else role
        geom = (lambda f=f: holes([f])) if role is None else (lambda f=f: area(f))
        one(f"board_{board}_{name}", caption,
            lambda name, geom=geom, kind=kind: save(board_view(g, "top"), [(geom(), LAYER.get(kind, LAYER[None]))],
                                                    edge, out, name))
    return shots, notes


def schematic(cfg, board, out):
    """edakit's drawing of the board (schematic_draw) into out/schematic_<board>.svg and .png: ([Shot], notes) – the
    drawing's own warnings and conflicts among the notes; no Shot for a board without parts in the graph."""
    from .. import schematic_draw as sd
    frame = cfg.schematic.get("frame", True) is not False
    style = sd.board_style(cfg, board)
    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        drawn = sd.drawing(cfg, board, frame=frame, style=style)
    notes = [line.strip().removeprefix("! ") for line in said.getvalue().splitlines() if line.strip()]
    if drawn is None:
        return [], notes + [f"schematic_{board.name}: the board has no parts in the graph"]
    if drawn["problems"]:
        notes.append(f"schematic_{board.name}: {len(drawn['problems'])} conflicts in the drawing – "
                     "`edakit schematic draw` lists them")
    g = sd.draw(drawn["sheet"], drawn["size"], drawn["syms"], drawn["power"], drawn["design"].ground,
                sd.title_lines(cfg, board, drawn, style), frame, drawn["wires"])
    name = f"schematic_{board.name}"
    (out / f"{name}.svg").write_text(g.done(), encoding="utf-8")
    g.png(out / f"{name}.png", dpi=SCHEMATIC_DPI)
    return [Shot(name, f"schematic {board.name}")], notes


def draw_run(cfg, outdir):
    """Every picture of a gate run into <outdir>/pictures and its index: {board: {"shots": [Shot], "notes": [...]}} –
    the schematic of every board but a bought one, the board pictures of every board stage F exported."""
    out = Path(outdir) / DIR
    out.mkdir(parents=True, exist_ok=True)
    found = {}
    for name, b in cfg.boards.items():
        if b.bought:
            continue
        try:
            shots, notes = schematic(cfg, b, out)
        except Exception as e:    # documentation: named, the gate goes on
            shots, notes = [], [f"schematic_{name}: not drawn – {type(e).__name__}: {e}"]
        if built_files(Path(outdir) / "fab" / name / "gerber")[0]:
            more, said = board_pictures(outdir, name)
            shots, notes = shots + more, notes + said
        found[name] = {"shots": shots, "notes": notes}
    (out / INDEX).write_text(json.dumps({b: [vars(s) for s in v["shots"]] for b, v in found.items()}, indent=1,
                                        ensure_ascii=False) + "\n", encoding="utf-8")
    return found


SHOWN = ("schematic_{b}", "board_{b}_top", "board_{b}_bottom")   # what the release notes show of a board


def files_of(run, board):
    """The picture files of a board in a gate run, as its pictures.json lists them – SVG and PNG; [] for a run without."""
    pics = Path(run) / DIR
    try:
        listed = json.loads((pics / INDEX).read_text(encoding="utf-8")).get(board, [])
    except (OSError, ValueError):
        return []
    return [f for s in listed for f in (pics / f"{s['name']}.png", pics / f"{s['name']}.svg") if f.is_file()]


def section(found, with_board):
    """The lines of section 12 of the protocol."""
    L = ["Each picture as SVG and PNG in `pictures/`. The schematic is edakit's drawing of the graph (`edakit "
         "schematic draw`); the board is drawn from this run's Gerber and drill files – as made, in the colours of the "
         "order settings, the bottom seen from below –, all layers over each other in the colours of the EasyEDA editor, "
         "then every layer and drill file on its own as the file draws "
         "it. Documentation, in no hash."]
    if not with_board:
        L.append("\nThe board pictures come with stage F (the manufacturing files).")
    for b, v in found.items():
        L.append(f"\n### Board {b}\n")
        made = [s for s in v["shots"] if s.name in (f"board_{b}_top", f"board_{b}_bottom", f"board_{b}_layers")]
        for s in v["shots"]:
            if s.name.startswith("schematic_") or s in made:
                L += [f"![{s.caption}]({DIR}/{s.name}.png)", f"[SVG]({DIR}/{s.name}.svg)", ""]
        rest = [s for s in v["shots"] if not s.name.startswith("schematic_") and s not in made]
        if rest:
            L.append("Layers: " + ", ".join(f"[{s.caption}]({DIR}/{s.name}.png) ([SVG]({DIR}/{s.name}.svg))"
                                            for s in rest))
        L += [f"- {n}" for n in v["notes"]]
    return L
