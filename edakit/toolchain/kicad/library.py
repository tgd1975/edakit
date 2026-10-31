"""The board's footprints for KiCad, from the parts database (handbook 16.3).

Where the pads come from (decision 3 of docs/concepts/new/kicad-toolchain.md): the entry's footprint_data (handbook
4.5), else the geometry `edakit part import` caches from the LCSC data – EasyEDA's footprint, the one JLCPCB's
assembly works from, so origin and rotation of the CPL need no correction. A part whose footprint is not cached yet is
read from the library first, into the cache only (as part import does; the entry is not touched).

    footprints(cfg, design, refs) -> {designator: Footprint}
    write(cfg, board, fps)        -> <kicad dir>/<board>.pretty/<name>.kicad_mod and fp-lib-table

A Footprint holds KiCad's view: mm, y down, relative to the origin, on the top side. Board.py places it – turned, and
for the bottom side mirrored in local y as EasyEDA mirrors it (Board.transform), so both tool chains put every pad on
the same spot.

    pad shapes   RECT -> rect, ELLIPSE -> circle (w = h) or oval, OVAL -> oval, POLYGON -> custom with its corners
    holes        [w, l] mm -> (drill w) or (drill oval …) along the pad's long side; not plated -> np_thru_hole
    silkscreen   footprint_data lines, texts, marks (a "+" two strokes, as GEO.mark reads them) and outline (F.Fab); else
                 the library's silkscreen (part.footprint_silk); the body box on F.Fab
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field

from ...config import MIL_PER_MM
from . import sexp
from .sexp import Sym, uid

LIB = "edakit"                 # the library's nickname in the tables of the board's KiCad project
VERSION = 20240108             # the file format edakit writes: KiCad 8 – KiCad 10 reads it and keeps it
SILK_WIDTH_MM = 0.15           # JLCPCB's thinnest print, the default of footprint_data
FAB_WIDTH_MM = 0.1
REF_SIZE_MM = 1.0              # designator text until edakit silk apply places it
SMD_LAYERS = {"TOP": ("F.Cu", "F.Paste", "F.Mask"), "BOTTOM": ("B.Cu", "B.Paste", "B.Mask")}
THT_LAYERS = ("*.Cu", "*.Mask")


class LibraryError(Exception):
    pass


def mm(mil):
    return mil / MIL_PER_MM


@dataclass
class Pad:
    num: str
    kind: str                  # smd, thru_hole, np_thru_hole
    shape: str                 # rect, circle, oval, custom
    x: float                   # mm, y down, relative to the origin
    y: float
    w: float
    h: float
    angle: float = 0.0         # degrees, counter-clockwise as seen from the top
    drill: tuple | None = None  # (d,) or ("oval", x, y)
    layer: str = "TOP"         # TOP, BOTTOM (smd) or MULTI
    points: list | None = None  # custom: the corners relative to the pad (mm, y down)


@dataclass
class Graphic:
    kind: str                  # line, poly, text
    layer: str                 # F.SilkS, F.Fab
    points: list = field(default_factory=list)   # mm, y down
    width: float = SILK_WIDTH_MM
    fill: bool = False
    text: str = ""
    size: float = 1.0
    angle: float = 0.0


@dataclass
class Footprint:
    name: str
    pads: list
    graphics: list
    bbox: tuple                # (x0, y0, x1, y1) mm, y down
    source: str = ""           # "data" or "library <footprint>"
    package: str = ""          # the footprint's name in the parts entry – name is the same as a file name

    @property
    def tht(self):
        return any(p.kind != "smd" for p in self.pads)


def file_name(name):
    return re.sub(r"[^A-Za-z0-9._+-]", "_", name) or "footprint"


def pad_of(num, p):
    """A pad of the geometry (mil, y up – as pcb dump and the cache have it) -> Pad."""
    w, h = mm(p["w"]), mm(p["h"])
    shape = {"RECT": "rect", "ELLIPSE": "oval", "OVAL": "oval", "POLYGON": "custom"}.get(p.get("shape"), "rect")
    if shape == "oval" and abs(w - h) < 1e-4:
        shape = "circle"
    points = None
    if shape == "custom":
        if p.get("points"):
            points = [[mm(x), -mm(y)] for x, y in p["points"]]
        else:
            shape = "rect"            # corners unknown: the rectangle that encloses the pad, as route.pad_shapes
    hole = p.get("hole")
    drill = None
    if hole:
        hw, hl = float(hole[0]), float(hole[1] if len(hole) > 1 else hole[0])
        drill = (hw,) if hl - hw < 1e-4 else (("oval", hl, hw) if w >= h else ("oval", hw, hl))
        kind = "thru_hole" if p.get("plated", True) else "np_thru_hole"
    else:
        kind = "smd"
    return Pad(num=str(num), kind=kind, shape=shape, x=mm(p["x"]), y=-mm(p["y"]), w=w, h=h,
               angle=float(p.get("rot") or 0) if points is None else 0.0, drill=drill,
               layer="MULTI" if hole else (p.get("layer") if p.get("layer") in SMD_LAYERS else "TOP"), points=points)


def pads_of(geo):
    out = []
    for num, p in geo["pads"].items():
        legs = (geo.get("pads_same_number") or {}).get(num)
        out += [pad_of(num, q) for q in legs] if legs else [pad_of(num, p)]
    return out


def silk_layer(layer):
    return "B.SilkS" if layer == "BOTTOM" else "F.SilkS"


def library_graphics(geo):
    """The library's silkscreen (part.footprint_silk, mil, y up) and the body box."""
    out = []
    for s in geo.get("silk") or []:
        pts = [[mm(x), -mm(y)] for x, y in s["points"]]
        out.append(Graphic("poly" if s.get("fill") else "line", silk_layer(s.get("layer")), pts,
                           mm(s.get("width") or 0) or SILK_WIDTH_MM, fill=bool(s.get("fill"))))
    return out


def data_graphics(data):
    """Lines, texts, marks and outline of footprint_data (mm, y up, relative to its origin)."""
    from ...footprint import mark_strokes, origin
    ox, oy = origin(data)

    def pt(p):
        return [p[0] - ox, -(p[1] - oy)]
    out = [Graphic("line", "F.SilkS", [pt(p) for p in ln["points"]], ln.get("width", SILK_WIDTH_MM))
           for ln in data.get("lines") or []]
    out += [Graphic("text", "F.SilkS", [pt((t["x"], t["y"]))], t.get("width", SILK_WIDTH_MM), text=t["text"],
                    size=t.get("size", 1.0), angle=t.get("rot", 0)) for t in data.get("texts") or []]
    out += [Graphic("line", "F.SilkS", [pt(p) for p in stroke], m.get("width", SILK_WIDTH_MM))
            for m in data.get("marks") or [] for stroke in mark_strokes(m)]
    if data.get("outline"):
        pts = [pt(p) for p in data["outline"]]
        out.append(Graphic("line", "F.Fab", pts + pts[:1], FAB_WIDTH_MM))
    return out


def from_geometry(name, geo, data=None):
    """Footprint of a geometry (mil, y up) – with data the silkscreen of footprint_data, else the library's."""
    x0, y0, x1, y1 = (mm(v) for v in geo["bbox"])
    box = (x0, -y1, x1, -y0)
    graphics = data_graphics(data) if data else library_graphics(geo)
    if not (data and data.get("outline")):
        graphics.append(Graphic("line", "F.Fab", [[box[0], box[1]], [box[2], box[1]], [box[2], box[3]],
                                                  [box[0], box[3]], [box[0], box[1]]], FAB_WIDTH_MM))
    return Footprint(name=file_name(name), pads=pads_of(geo), graphics=graphics, bbox=box,
                     source="data" if data else f"library {geo.get('footprint') or name}", package=name)


def geometry_of(cfg, design, des, fetch=True, today=None):
    """(name, geometry, footprint_data or None) of a component: its entry's data, else the cached LCSC geometry –
    read from the library first when it is not cached yet or cached without its silkscreen (an older cache)."""
    from ... import part
    from ...footprint import data_of, geometry
    entry = design.part(des) or {}
    if "footprint_data" in entry:
        geo = geometry(entry)
        if geo is None:
            raise LibraryError(f"{des}: the footprint data of its parts entry is not complete – edakit check names "
                               "what PARTS.footprint misses")
        return entry.get("footprint") or design.entry_key(des), geo, data_of(entry)
    lcsc = design.comps[des].get("lcsc")
    name = entry.get("footprint") or (part.cached(cfg, lcsc) or {}).get("footprint")
    geo = part.cached_footprint(cfg, name)
    if (geo is None or "silk" not in geo) and fetch and lcsc:
        try:
            lib = part.library_part(lcsc)
            part.write_cache(cfg, lib, today or datetime.date.today().isoformat())
            name = name or lib["footprint"]
            geo = part.cached_footprint(cfg, name) or geo
        except part.PartError as e:
            if geo is None:
                raise LibraryError(f"{des}: no footprint – {e}") from None
            print(f"  {des}: library not read again ({e}) – its footprint without the silkscreen of the library")
    if geo is None:
        raise LibraryError(f"{des}: no footprint – its parts entry has neither footprint_data nor an LCSC number "
                           "whose footprint `edakit part import` could cache")
    return name, geo, None


def footprints(cfg, design, refs, fetch=True):
    """{designator: Footprint} for these components; one Footprint per name – two geometries of one name (data of
    one entry, the library's of another) get the entry's key appended."""
    out, by_name = {}, {}
    for des in refs:
        name, geo, data = geometry_of(cfg, design, des, fetch)
        fp = from_geometry(name, geo, data)
        seen = by_name.get(fp.name)
        if seen is not None and module(seen) != module(fp):
            fp.name = file_name(f"{name}_{design.entry_key(des)}")
        by_name.setdefault(fp.name, fp)
        out[des] = by_name[fp.name]
    return out


# --- KiCad text ------------------------------------------------------------------------------------------------------

def font(size, width, mirror=False, hide=False):
    effects = ["effects", ["font", ["size", size, size], ["thickness", width]]]
    if mirror:
        effects.append(["justify", Sym("mirror")])
    out = [effects]
    if hide:
        out.insert(0, ["hide", True])
    return out


def pad_item(pad, angle=0.0, mirror=False, net=None, key=()):
    """(pad …) of a Pad on a footprint turned by angle – pads carry the absolute angle in KiCad's files; mirror:
    the footprint lies on the bottom side (local y mirrored, layers swapped, the pad's own turn negated)."""
    x, y, a = pad.x, -pad.y if mirror else pad.y, -pad.angle if mirror else pad.angle
    if pad.kind == "smd":
        side = {"TOP": "BOTTOM", "BOTTOM": "TOP"}[pad.layer] if mirror else pad.layer
        layers = SMD_LAYERS[side]
    else:
        layers = THT_LAYERS
    size = [pad.w, pad.h] if pad.shape != "custom" else [min(pad.w, pad.h) / 2] * 2   # custom: a small anchor
    item = ["pad", pad.num, Sym(pad.kind), Sym(pad.shape), ["at", x, y, (angle + a) % 360], ["size", *size]]
    if pad.drill:
        item.append(["drill", Sym("oval"), *pad.drill[1:]] if pad.drill[0] == "oval" else ["drill", pad.drill[0]])
    item.append(["layers", *layers])
    if pad.shape == "custom":
        pts = [[p[0], -p[1] if mirror else p[1]] for p in pad.points]
        item += [["options", ["clearance", Sym("outline")], ["anchor", Sym("rect")]],
                 ["primitives", ["gr_poly", ["pts", *(["xy", px, py] for px, py in pts)], ["width", 0],
                                 ["fill", True]]]]
    if net:
        item.append(["net", net[0], net[1]])
    item.append(["uuid", uid(*key, "pad", pad.num, pad.x, pad.y)])
    return item


def flip_layer(layer):
    return layer.replace("F.", "B.", 1) if layer.startswith("F.") else layer


def graphic_items(g, k, mirror=False, angle=0.0, key=()):
    layer = flip_layer(g.layer) if mirror else g.layer
    pts = [[x, -y if mirror else y] for x, y in g.points]
    tag = uid(*key, "graphic", k)
    if g.kind == "text":
        turned = (angle + (-g.angle if mirror else g.angle)) % 360
        return [["fp_text", Sym("user"), g.text, ["at", pts[0][0], pts[0][1], turned],
                 ["layer", layer], ["uuid", tag], *font(g.size, g.width, mirror)]]
    stroke = ["stroke", ["width", g.width], ["type", Sym("solid")]]
    if g.kind == "poly":
        return [["fp_poly", ["pts", *(["xy", x, y] for x, y in pts)], stroke,
                 ["fill", Sym("solid" if g.fill else "none")], ["layer", layer], ["uuid", tag]]]
    return [["fp_line", ["start", *a], ["end", *b], stroke, ["layer", layer], ["uuid", uid(tag, i)]]
            for i, (a, b) in enumerate(zip(pts, pts[1:]))]


def module(fp):
    """The footprint as a library file (.kicad_mod): top side, angle 0, no nets."""
    key = ("library", fp.name)
    ref_y = fp.bbox[1] - REF_SIZE_MM
    items = ["footprint", fp.name, ["version", VERSION], ["generator", "edakit"], ["layer", "F.Cu"],
             ["descr", f"edakit: {fp.source}"],
             ["property", "Reference", "REF**", ["at", 0, ref_y, 0], ["layer", "F.SilkS"], ["uuid", uid(*key, "ref")],
              *font(REF_SIZE_MM, SILK_WIDTH_MM)],
             ["property", "Value", fp.name, ["at", 0, fp.bbox[3] + REF_SIZE_MM, 0], ["layer", "F.Fab"],
              ["uuid", uid(*key, "value")], *font(REF_SIZE_MM, SILK_WIDTH_MM, hide=True)],
             ["attr", Sym("through_hole" if fp.tht else "smd")]]
    for k, g in enumerate(fp.graphics):
        items += graphic_items(g, k, key=key)
    items += [pad_item(p, key=(*key, i)) for i, p in enumerate(fp.pads)]
    return sexp.dumps(items) + "\n"


def write(cfg, board, fps):
    """The library files of the board's footprints and the project's footprint table -> the .pretty folder."""
    d = cfg.kicad_dir(board)
    pretty = d / f"{board.name}.pretty"
    pretty.mkdir(parents=True, exist_ok=True)
    names = set()
    for fp in {fp.name: fp for fp in fps.values()}.values():
        (pretty / f"{fp.name}.kicad_mod").write_text(module(fp), encoding="utf-8")
        names.add(f"{fp.name}.kicad_mod")
    for old in pretty.glob("*.kicad_mod"):    # generated: what no part uses any more goes
        if old.name not in names:
            old.unlink()
    table = ["fp_lib_table", ["version", 7],
             ["lib", ["name", LIB], ["type", "KiCad"], ["uri", f"${{KIPRJMOD}}/{pretty.name}"], ["options", ""],
              ["descr", "the board's footprints, generated by edakit from the parts database"]]]
    (d / "fp-lib-table").write_text(sexp.dumps(table) + "\n", encoding="utf-8")
    return pretty
