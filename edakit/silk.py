"""Silkscreen: designators where there is room, checked on the Gerber export.

    edakit silk apply   hide the designators of the sides in [silk] hide of the board file; place those of the side
                        in `designators` next to their part where nothing is in the way; export Gerber, check, DRC
    edakit silk check   export Gerber and only check: own silkscreen on solder-mask openings (JLCPCB cuts it off there)
Both end with EasyEDA's DRC: exit 2 on findings, 3 when the only one is EasyEDA waiting for the import
acknowledgement (schematic = PCB, compared as `pcb parts` and `pcb nets` do; Design → Import Changes once).

Placement: every designator gets the first free spot above, below, right or left of its part (horizontal, then
vertical, then at the corners) – not on pads, footprint silkscreen, other parts or other labels. Test points and the
tightest parts come first. A spot on a via (tented, the print holds) only when nothing else is free. Groups
([silk] groups = {"R1-R8" = [...]}) get one common label when the single labels do not fit. With solder_side = true the
through-hole parts of the other side are labelled on this side too, next to their solder joints: a free text in the
same font, remembered and replaced like the group labels.

Fixed designators ([silk.place] R4 = {x, y, rot, side}, plan mm as [place]) go where the row says, and the rest is
placed around them. side (default the designators side) is where the name prints: on the part's side its own designator,
on the other a free text, as with solder_side – there and nowhere else. One on a pad (solder-mask opening + 0.15 mm),
beyond the printable board or on a text ([[silk.texts]] + 0.3 mm, another fixed one + 0.2 mm) is a finding, exit 2; it
is written all the same. `edakit silk preview` shows them on the last Gerber export with the same findings, offline.

Board label: the board's title and revision (revision and [silk] board_label of the board file, default
"{title} rev {revision}", also {project} and {board}) in the free spot nearest to a corner (board_label_corner, default
"bottom-left" as seen from the printed side), not on pads, parts, labels, vias or the keep-outs of holes. It goes on the
designators side unless board_label_side names the other one, and anywhere on the board unless board_label_region
(a polygon in plan mm) gives the part it must lie in – the corner is then that region's. edakit remembers the strings
it created and replaces them on the next run, so an old revision never stays on the board.

Artwork and texts ([[silk.art]]: svg, x, y, width_mm, rot, side; [[silk.texts]]: text, x, y, h_mm, rot, side,
font) come first: filled shapes and strokes of the SVG become silkscreen fills, cut free of pads and
solder-mask openings (+0.15 mm) and of strokes thinner than JLCPCB can print (0.15 mm). Designators and the board label
then keep clear of them. `edakit silk preview` draws the artwork onto the last Gerber export offline.

Run it again after every auto-layout and routing: the spots depend on where the small parts and vias ended up. `apply`
keeps the silk files of its first export, before it prints anything, in <artifacts>/silk_footprints_<board>/: the gate
(L-17) fails on print on a solder-mask opening that is not in them – edakit's own – and only warns on the rest.
API notes: designators are attributes (PCB_PrimitiveAttribute, key 'Designator'); modify works on locked parts too;
alignMode 5 = centre on x/y. Stroke font 'default': measured 0.5-0.6 x height per character.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from . import eda, gerber, pcb
from .config import BOTTOM, MIL_PER_MM, TOP
from .design import natural_key
from .eda import api, ensure_pcb_focus
from .toolchain import is_kicad

SIDE = {"top": TOP, "bottom": BOTTOM}
MULTI_LAYER = 12  # EasyEDA layer of through-hole pads
GERBER_KEYS = {TOP: ("top_mask", "top_silk"), BOTTOM: ("bottom_mask", "bottom_silk")}


def mm(v):
    return v / MIL_PER_MM


def to_mil(v):
    return round(v * MIL_PER_MM, 3)


def board_shape(board):
    """Printable board area in EasyEDA coordinates (mm): outline without mounting and tooling holes."""
    holes = [Point(*board.eda_point(h["x"], h["y"])).buffer(h["d"] / 2) for h in board.holes]
    holes += [Point(*board.eda_point(x, y)).buffer(board.tooling_d / 2) for x, y in board.tooling]
    return Polygon([board.eda_point(*p) for p in board.outline]).difference(unary_union(holes))


CAP_RATIO = 0.68  # EasyEDA's font size is the em height; capitals print at 0.69 of it (measured on Gerber) – with margin


def font_size(h):
    """EasyEDA font size for printed capitals of height h (mm). All heights in the board file mean printed capitals –
    JLCPCB wants at least 1.0 mm."""
    return h / CAP_RATIO


def label_size(name, h):
    fs = font_size(h)
    return 0.65 * fs * len(name), fs


def label_box(x, y, rot, w, h):
    """The box of a text w long and h high centred on (x, y): lying at 0° and 180°, standing at 90° and 270°, turned
    with the text at any other angle."""
    turn = float(rot) % 180
    if turn == 0:
        return box(x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    if turn == 90:
        return box(x - h / 2, y - w / 2, x + h / 2, y + w / 2)
    from shapely.affinity import rotate
    return rotate(box(x - w / 2, y - h / 2, x + w / 2, y + h / 2), turn, origin=(x, y))


def label_spots(bb, w, h, gap):
    x0, y0, x1, y1 = bb
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    sides, corners = [], []
    for rot, lw, lh in ((0, w, h), (90, h, w)):
        sides += [(cx, y1 + gap + lh / 2, rot), (cx, y0 - gap - lh / 2, rot), (x1 + gap + lw / 2, cy, rot),
                  (x0 - gap - lw / 2, cy, rot)]
        corners += [(x, y, rot) for y in (y1 + gap + lh / 2, y0 - gap - lh / 2) for x in (x0 + lw / 2, x1 - lw / 2)]
        corners += [(x, y, rot) for x in (x1 + gap + lw / 2, x0 - gap - lw / 2) for y in (y1 - lh / 2, y0 + lh / 2)]
    return sides + corners


def fixed_labels(board):
    """[silk.place] of the board file: {designator: (x, y, rot, side)} – the spot in EasyEDA mm (the rows are plan mm,
    as [place]), the rotation EasyEDA gets (as for [[silk.texts]]), the side the name prints on (default: the
    designators side)."""
    side = board.silk.get("designators", "top")
    return {ref: (*board.eda_point(float(p["x"]), float(p["y"])), float(p.get("rot", 0)), p.get("side", side))
            for ref, p in (board.silk.get("place") or {}).items()}


def fixed_findings(fixed, h, area, openings, texts=(), side="top"):
    """What is in the way of the fixed designators of one side – what place_labels keeps a placed label clear of:
    a pad (the side's solder-mask openings + 0.15 mm), the edge of the printable `area`, a text of [[silk.texts]]
    (silk_texts, + 0.3 mm) and another fixed designator (+ 0.2 mm). fixed: {designator: (x, y, rot)} in EasyEDA mm,
    h: their height. -> ["R4: fixed designator on a pad (top) – 0.42 mm² …"]"""
    if not fixed:
        return []
    out, pads = [], openings.buffer(0.15)
    boxes = {r: label_box(*fixed[r], *label_size(r, h)) for r in sorted(fixed, key=natural_key)}
    for ref, b in boxes.items():
        if b.intersects(pads):
            out.append(f"{ref}: fixed designator on a pad ({side}) – {b.intersection(pads).area:.2f} mm² of its box "
                       "within 0.15 mm of a solder-mask opening")
        if not area.contains(b):
            out.append(f"{ref}: fixed designator beyond the printable board ({side}) – "
                       f"{b.difference(area).area:.2f} mm² of its box outside the outline less 0.5 mm or on a hole")
        for t, x, y, rot, th, *_ in texts:
            other = label_box(x, y, rot, *label_size(t, th))
            if b.intersects(other):
                out.append(f"{ref} / {t}: fixed designator on the text ({side}) – {b.intersection(other).area:.2f} mm² "
                           "in common")
            elif b.distance(other) <= 0.3:
                out.append(f"{ref} / {t}: fixed designator {b.distance(other):.2f} mm from the text ({side}) – a "
                           "placed one keeps 0.3 mm")
    refs = list(boxes)
    for i, a in enumerate(refs):
        for c in refs[i + 1:]:
            if boxes[a].intersects(boxes[c]):
                out.append(f"{a} / {c}: fixed designators overlap ({side}) – "
                           f"{boxes[a].intersection(boxes[c]).area:.2f} mm² in common")
            elif boxes[a].distance(boxes[c]) <= 0.2:
                out.append(f"{a} / {c}: fixed designators {boxes[a].distance(boxes[c]):.2f} mm apart ({side}) – placed "
                           "ones keep 0.2 mm")
    return out


def place_labels(parts, blocked, vias, area, h, gap, groups=None, priority=("TP",), fixed=None):
    """parts: {designator: bbox}, blocked: pads, footprint silk, parts; vias: via areas; area: printable board;
    fixed: {label: (x, y, rotation)} of [silk.place], taken as given – the rest keeps clear of them.
    Returns {label: (x, y, rotation)} with the fixed ones, parts covered by a group label, parts without a spot."""
    hard, soft = blocked, blocked.union(vias)
    placed, taken = {}, []
    for name, spot in (fixed or {}).items():
        placed[name] = spot
        taken.append(label_box(*spot, *label_size(name, h)).buffer(0.2))
    parts = {r: bb for r, bb in parts.items() if r not in placed}   # a fixed one leaves its group too

    def spots(name, bb, obstacles=soft):
        w, hh = label_size(name, h)
        return [s for s in label_spots(bb, w, hh, gap)
                if area.contains(label_box(*s, w, hh)) and not label_box(*s, w, hh).intersects(obstacles)]

    def put(name, cands):
        w, hh = label_size(name, h)
        for s in cands:
            b = label_box(*s, w, hh)
            if not any(b.intersects(t) for t in taken):
                placed[name] = s
                taken.append(b.buffer(0.2))
                return True
        return False
    cands = {ref: spots(ref, bb) for ref, bb in parts.items()}
    grouped = set()
    for name, refs in (groups or {}).items():
        refs = sorted((r for r in refs if r in parts), key=lambda r: (len(cands[r]), natural_key(r)))
        saved = dict(placed), list(taken)
        if not refs or all([put(r, cands[r]) for r in refs]):
            continue
        placed.clear()  # not every part fits alone: back, and one common label at the group
        placed.update(saved[0])
        taken[:] = saved[1]
        bbs = [parts[r] for r in refs]
        if put(name, spots(name, (min(b[0] for b in bbs), min(b[1] for b in bbs), max(b[2] for b in bbs),
                                  max(b[3] for b in bbs)))):
            grouped |= set(refs)
        else:
            for r in refs:
                put(r, cands[r])
    first = lambda r: not any(r.startswith(p) for p in priority)  # noqa: E731
    rest = [r for r in parts if r not in grouped and r not in placed]
    for ref in sorted(rest, key=lambda r: (first(r), len(cands[r]), natural_key(r))):
        put(ref, cands[ref])
    for ref in sorted((r for r in rest if r not in placed), key=lambda r: (first(r), natural_key(r))):
        put(ref, spots(ref, parts[ref], hard))
    missing = sorted((r for r in parts if r not in grouped and r not in placed), key=natural_key)
    return placed, grouped, missing


def label_parts(parts, layer, solder_side=False):
    """parts: {designator: (EasyEDA layer, through-hole)} -> the designators labelled on `layer`: the parts of that side
    and, with solder_side, the through-hole parts of the other side – they are soldered from this one."""
    return sorted((r for r, (on, tht) in parts.items() if on == layer or (solder_side and tht)), key=natural_key)


def through_hole_parts(mcp, comps):
    """Designators of the parts with a through-hole pad (layer 12); a pad's id starts with its part's id."""
    out = set()
    for p in map(eda.state, api(mcp, "PCB_PrimitivePad.getAll") or []):
        if p.get("Layer") == MULTI_LAYER:
            owner = next((c for cid, c in comps.items() if p["PrimitiveId"].startswith(cid)), None)
            if owner and owner.get("Designator"):
                out.add(owner["Designator"])
    return out


def board_label_text(cfg, board):
    template = board.silk.get("board_label", "{title} rev {revision}")
    if not template or ("{revision}" in template and board.revision is None):
        return None
    return template.format(project=cfg.project, title=board.title, board=board.name, revision=board.revision)


def board_label_area(board, area):
    """Where the board label may lie: the printable `area`, cut to [silk] board_label_region (plan mm) if given."""
    region = board.silk.get("board_label_region")
    return area.intersection(Polygon([board.eda_point(*p) for p in region]).buffer(0)) if region else area


def side_obstacles(openings, printed, boxes, art=None):
    """What the board label keeps clear of on the side without designators: pads and mask openings and the print
    already there (+0.15 mm), the boxes of that side's parts, its artwork and texts (already grown)."""
    return unary_union([openings.buffer(0.15), printed.buffer(0.15), *[box(*bb) for bb in boxes]]
                       + ([art] if art is not None else []))


def corner_spot(area, obstacles, w, h, corner="bottom-left", step=0.5):
    """Centre of a free w x h box nearest to a corner of `area` (inside it, clear of `obstacles`), or None."""
    if area.is_empty:
        return None
    x0, y0, x1, y1 = area.bounds
    cx = x1 if "right" in corner else x0
    cy = y1 if "top" in corner else y0
    nx, ny = int((x1 - x0 - w) / step) + 1, int((y1 - y0 - h) / step) + 1
    cands = [(x0 + w / 2 + i * step, y0 + h / 2 + j * step) for i in range(max(nx, 0)) for j in range(max(ny, 0))]
    for x, y in sorted(cands, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2):
        b = label_box(x, y, 0, w, h)
        if area.contains(b) and not b.intersects(obstacles):
            return x, y
    return None


MIN_SILK_MM = 0.15  # JLCPCB: thinner silkscreen does not print
MIN_GAP_MM = 0.2    # narrower gaps inside the artwork fill in
MIN_TEXT_MM = 1.0   # JLCPCB: lower characters are unidentifiable (L-17)


def svg_geometry(path):
    """Filled shapes (even-odd) and strokes of an SVG as one shapely geometry, y up, in the SVG's user units."""
    import numpy as np
    from shapely.geometry import LineString
    from svgelements import SVG, Path as SvgPath, Shape

    shapes = []
    for el in SVG.parse(str(path), reify=True).elements():
        if not isinstance(el, Shape):
            continue
        p = SvgPath(el)
        if not len(p):
            continue
        rings = []
        for sub in p.as_subpaths():
            sub = SvgPath(sub)
            n = max(16, int(sub.length(error=1e-4) * 4))
            rings.append([(float(x), -float(y)) for x, y in sub.npoint(np.linspace(0, 1, n))])
        if el.fill is not None and el.fill.value is not None:
            filled = None
            for r in rings:
                if len(r) >= 3:
                    poly = Polygon(r).buffer(0)
                    filled = poly if filled is None else filled.symmetric_difference(poly)
            if filled is not None:
                shapes.append(filled)
        width = el.stroke_width if el.stroke is not None and el.stroke.value is not None else 0
        if width:
            shapes += [LineString(r).buffer(width / 2) for r in rings if len(r) >= 2]
    return unary_union(shapes)


def art_shapes(cfg, board, side):
    """All artwork of one side in EasyEDA coordinates (mm, seen from the top), as one geometry."""
    out = art_items(cfg, board, side)
    return unary_union(out) if out else Polygon()


def art_items(cfg, board, side):
    """Each artwork item of one side in EasyEDA coordinates (mm, seen from the top). An item is scaled to width_mm,
    centred on its plan position (x, y), turned by rot (counter-clockwise as seen from its side) and mirrored on the
    bottom – EasyEDA mirrors texts there, not graphics."""
    from shapely.affinity import rotate, scale, translate
    out = []
    for item in board.silk.get("art", []):
        if item.get("side", board.silk.get("designators", "top")) != side:
            continue
        g = svg_geometry(cfg.resolve(item["svg"]))
        x0, y0, x1, y1 = g.bounds
        f = float(item["width_mm"]) / (x1 - x0)
        g = scale(translate(g, -(x0 + x1) / 2, -(y0 + y1) / 2), f, f, origin=(0, 0))
        g = rotate(g, float(item.get("rot", 0)), origin=(0, 0))
        if side == "bottom":
            g = scale(g, -1, 1, origin=(0, 0))
        out.append(translate(g, *board.eda_point(float(item["x"]), float(item["y"]))))
    return out


def printable(art, area, openings):
    """What JLCPCB can print of the artwork: inside the board, off pads and mask openings, gaps under 0.2 mm closed,
    nothing thinner than 0.15 mm."""
    g = art.intersection(area).difference(openings.buffer(0.15))
    g = g.buffer(MIN_GAP_MM / 2).buffer(-MIN_GAP_MM / 2)  # gaps the print closes anyway: closed here, so the preview shows it
    return g.buffer(-MIN_SILK_MM / 2).buffer(MIN_SILK_MM / 2).simplify(0.01)


def silk_texts(board, side):
    """[(text, x, y, rot, h, font)] of [[silk.texts]] on this side, positions in EasyEDA mm."""
    out = []
    for t in board.silk.get("texts", []):
        if t.get("side", board.silk.get("designators", "top")) == side:
            x, y = board.eda_point(float(t["x"]), float(t["y"]))
            out.append((t["text"], x, y, float(t.get("rot", 0)), float(t.get("h_mm", 1.2)), t.get("font", "default")))
    return out


def ring_arg(coords):
    pts = [(to_mil(x), to_mil(y)) for x, y in list(coords)[:-1]]
    flat = [pts[0][0], pts[0][1], "L"]
    for x, y in pts[1:] + pts[:1]:
        flat += [x, y]
    return flat


def polygons(g):
    return [p for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and not p.is_empty]


def footprint_print(cfg, board):
    """Where `apply` keeps the silk Gerber files of its first export – the print that is not edakit's own: the
    footprints', and texts and designators edakit did not place. The gate (L-17) tells edakit's print from it."""
    return cfg.artifacts / f"silk_footprints_{board.name}"


def export_gerber(cfg, board, mcp):
    out = cfg.artifact(f"gerber_{board.name}", ".keep").parent
    res = mcp.call("easyeda_export_gerbers", projectId="current", drillFormat="millimeter",
                   productionReview={"mode": "off"}, timeout=300)
    if not res.get("exported"):
        raise SystemExit(f"Gerber export failed: {res}")
    import zipfile
    with zipfile.ZipFile(res["artifact_path"]) as z:
        z.extractall(out)
    return out


def silk_on_openings(folder, layer, own=None):
    """Area (mm²) of silkscreen on solder-mask openings; own: only this silk (e.g. without footprint silk)."""
    mask_key, silk_key = GERBER_KEYS[layer]
    openings = gerber.shape(gerber.parse_gerber(Path(folder) / gerber.FILES[mask_key]))
    silk = own if own is not None else gerber.shape(gerber.parse_gerber(Path(folder) / gerber.FILES[silk_key]))
    return silk.intersection(openings).area, openings


def picture(silk, openings, area, out, mirror=False, extra=(), texts=()):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath
    from shapely.affinity import scale
    from shapely.geometry.polygon import orient

    def patch(g, color):
        verts, codes = [], []
        for p in getattr(g, "geoms", [g]):
            if p.geom_type != "Polygon" or p.is_empty:
                continue
            p = orient(p)
            for ring in (p.exterior, *p.interiors):
                c = list(ring.coords)
                verts += c
                codes += [MPath.MOVETO] + [MPath.LINETO] * (len(c) - 2) + [MPath.CLOSEPOLY]
        return PathPatch(MPath(verts, codes), facecolor=color, edgecolor="none") if verts else None
    if mirror:
        silk, openings, area = (scale(g, -1, 1, origin=(0, 0)) for g in (silk, openings, area))
    x0, y0, x1, y1 = area.bounds
    fig, ax = plt.subplots(figsize=((x1 - x0 + 10) / 25.4, (y1 - y0 + 10) / 25.4), dpi=300)
    fig.patch.set_facecolor("#14161a")
    if mirror:
        extra = [(scale(g, -1, 1, origin=(0, 0)), c) for g, c in extra]
    for g, color in ((area, "#0f5a2a"), (openings.intersection(area), "#c9b26a"), (silk, "#f4f2ea"), *extra):
        p = patch(g, color)
        if p:
            ax.add_patch(p)
    for text, x, y, rot, th, _ in texts:
        ax.text(-x if mirror else x, y, text, rotation=rot, ha="center", va="center", fontsize=th / 0.72 * 72 / 25.4,
                color="#f4f2ea", family="DejaVu Sans")
    ax.set_xlim(x0 - 5, x1 + 5)
    ax.set_ylim(y0 - 5, y1 + 5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(out, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


APPLY_STEPS = 8   # bridge and PCB (main), the five of apply, the two of check


def apply(cfg, board, mcp, step=None):
    """step: eda.Steps of `silk apply` (APPLY_STEPS)."""
    step = step or (lambda _: None)
    step("hide designators, remove the last run's print")
    s = board.silk
    side = s.get("designators", "top")
    h, gap = float(s.get("label_h_mm", 1.0)), float(s.get("gap_mm", 0.25))
    layer = SIDE[side]
    hide = {SIDE[x] for x in s.get("hide", [])} | {layer}  # the placed side is hidden first, then shown at its spot
    ensure_pcb_focus(mcp)
    memo = cfg.artifact(f"silk_strings_{board.name}.json")
    if memo.exists():  # texts and fills edakit created in the last run
        old = json.loads(memo.read_text())
        old = {"strings": old} if isinstance(old, list) else old
        for kind, cls in (("strings", "PCB_PrimitiveString"), ("fills", "PCB_PrimitiveFill")):
            existing = {eda.state(t).get("PrimitiveId") for t in api(mcp, f"{cls}.getAll") or []}
            gone = [p for p in old.get(kind, []) if p in existing]
            if gone:
                api(mcp, f"{cls}.delete", gone)
    comps = {c["PrimitiveId"]: c for c in map(eda.state, api(mcp, "PCB_PrimitiveComponent.getAll") or [])}
    fixed = fixed_labels(board)
    attrs = {}
    for a in map(eda.state, api(mcp, "PCB_PrimitiveAttribute.getAll") or []):
        c = comps.get(a.get("ParentPrimitiveId"))
        if a.get("Key") == "Designator" and c:
            attrs[c["Designator"]] = (a, c)
            away = c["Designator"] in fixed and SIDE[fixed[c["Designator"]][3]] != c.get("Layer")  # name: other side
            if (c.get("Layer") in hide or away) and a.get("ValueVisible"):
                api(mcp, "PCB_PrimitiveAttribute.modify", a["PrimitiveId"], {"valueVisible": False})
    eda.save_pcb(mcp)
    step("Gerber export: the footprints' own print")
    folder = export_gerber(cfg, board, mcp)  # now the silk layer holds only the footprints' own print
    kept = footprint_print(cfg, board)
    kept.mkdir(parents=True, exist_ok=True)
    for key in ("top_silk", "bottom_silk"):              # kept for the gate: what is not in it is edakit's (L-17)
        if (folder / gerber.FILES[key]).exists():
            shutil.copy(folder / gerber.FILES[key], kept / gerber.FILES[key])
    mask_key, silk_key = GERBER_KEYS[layer]
    openings = gerber.shape(gerber.parse_gerber(folder / gerber.FILES[mask_key]))
    fp_silk = gerber.shape(gerber.parse_gerber(folder / gerber.FILES[silk_key]))
    solder_side = s.get("solder_side", False)
    tht = through_hole_parts(mcp, comps) if solder_side else set()
    parts = {}
    for ref in label_parts({r: (c.get("Layer"), r in tht) for r, (_, c) in attrs.items()}, layer, solder_side):
        bb = api(mcp, "PCB_Primitive.getPrimitivesBBox", [attrs[ref][1]["PrimitiveId"]])
        parts[ref] = (mm(bb["minX"]), mm(bb["minY"]), mm(bb["maxX"]), mm(bb["maxY"]))
    other = [r for r in parts if attrs[r][1].get("Layer") != layer]  # solder_side: printed as free texts
    blocked = unary_union([openings.buffer(0.15), fp_silk.buffer(0.15)] + [box(*bb) for bb in parts.values()])
    vias = unary_union([Point(mm(v["X"]), mm(v["Y"])).buffer(mm(v["Diameter"]) / 2 + 0.1)
                        for v in map(eda.state, api(mcp, "PCB_PrimitiveVia.getAll") or [])])
    area = board_shape(board).buffer(-0.5)
    label_layer = SIDE[s.get("board_label_side", side)]
    label_art = None  # the artwork and texts of the board label's side when that is not the designators side
    created = {"strings": [], "fills": []}

    def string(text, x, y, rot, size, font="default", on=layer):
        res = api(mcp, "PCB_PrimitiveString.create", on + 2, to_mil(x), to_mil(y), text, font, to_mil(font_size(size)), 6,
                  5, rot, False, 0, False, False)  # EasyEDA mirrors texts on the bottom by itself
        created["strings"].append(eda.state(res).get("PrimitiveId") if isinstance(res, dict) else res)
    step("artwork and texts")
    for art_side, art_layer in SIDE.items():
        art = art_shapes(cfg, board, art_side)
        texts = silk_texts(board, art_side)
        if art.is_empty and not texts:
            continue
        side_openings = openings if art_layer == layer else gerber.shape(
            gerber.parse_gerber(folder / gerber.FILES[GERBER_KEYS[art_layer][0]]))
        art = printable(art, area, side_openings)
        for n, p in enumerate(polygons(art)):
            if n % 20 == 0:
                ensure_pcb_focus(mcp)
            rings = [p.exterior.coords] + [i.coords for i in p.interiors]
            arg = {"$complexPolygon": [ring_arg(r) for r in rings]} if p.interiors else {"$polygon": ring_arg(rings[0])}
            res = api(mcp, "PCB_PrimitiveFill.create", art_layer + 2, arg, "", "solid", 0, False)
            created["fills"].append(eda.state(res).get("PrimitiveId") if isinstance(res, dict) else res)
        for text, x, y, rot, th, font in texts:
            string(text, x, y, rot, th, font, art_layer)
        if art_layer in (layer, label_layer):  # designators and the board label keep clear of it
            boxes = [label_box(x, y, rot, *label_size(t, th)) for t, x, y, rot, th, _ in texts]
            keep = unary_union([art.buffer(0.3), *[b.buffer(0.3) for b in boxes]])
            if art_layer == layer:
                blocked = unary_union([blocked, keep])
            else:
                label_art = keep
        print(f"  {art_side}: artwork {len(polygons(art))} shapes ({art.area:.0f} mm²), {len(texts)} texts")
    step("designators")
    far = "bottom" if side == "top" else "top"  # [silk.place] rows of the other side print there, nowhere else
    here = {r: (x, y, rot) for r, (x, y, rot, on) in fixed.items() if r in attrs and on == side}
    there = {r: (x, y, rot) for r, (x, y, rot, on) in fixed.items() if r in attrs and on != side}
    findings = [f"{r}: in [silk] place, but no part of this board" for r in sorted(fixed, key=natural_key)
                if r not in attrs]
    findings += fixed_findings(here, h, area, openings, silk_texts(board, side), side)
    if there:
        findings += fixed_findings(there, h, area, gerber.shape(gerber.parse_gerber(
            folder / gerber.FILES[GERBER_KEYS[SIDE[far]][0]])), silk_texts(board, far), far)
    placed, grouped, missing = place_labels({r: bb for r, bb in parts.items() if r not in there}, blocked, vias, area,
                                            h, gap, s.get("groups"), tuple(s.get("priority", ["TP"])), here)
    labels = [(name, spot, layer) for name, spot in placed.items()] + [(r, v, SIDE[far]) for r, v in there.items()]
    for n, (name, (x, y, rot), on) in enumerate(labels):
        if n % 20 == 0:
            ensure_pcb_focus(mcp)
        if name in attrs and attrs[name][1].get("Layer") == on:
            api(mcp, "PCB_PrimitiveAttribute.modify", attrs[name][0]["PrimitiveId"],
                {"x": to_mil(x), "y": to_mil(y), "rotation": rot, "alignMode": 5, "fontSize": to_mil(font_size(h)),
                 "lineWidth": 6,
                 "valueVisible": True})
        else:  # group label, or a part of the other side (its attribute prints there): a text in the same stroke font
            string(name, x, y, rot, h, on=on)
    step("board label, save")
    text = board_label_text(cfg, board)
    if text:
        lh = float(s.get("board_label_h_mm", 1.2))
        lw, _ = label_size(text, lh)
        if label_layer == layer:  # what the designators keep clear of, and the designators
            near = [blocked, *[label_box(x, y, rot, *label_size(name, h)).buffer(0.3) for name, (x, y, rot) in
                               placed.items()]]
        else:  # board_label_side: the other side's openings, print, parts, artwork and texts, its fixed designators
            mask_key, silk_key = GERBER_KEYS[label_layer]
            bbs = [api(mcp, "PCB_Primitive.getPrimitivesBBox", [cid]) for cid, c in comps.items()
                   if c.get("Layer") == label_layer]
            near = [side_obstacles(gerber.shape(gerber.parse_gerber(folder / gerber.FILES[mask_key])),
                                   gerber.shape(gerber.parse_gerber(folder / gerber.FILES[silk_key])),
                                   [(mm(b["minX"]), mm(b["minY"]), mm(b["maxX"]), mm(b["maxY"])) for b in bbs],
                                   label_art)]
            near += [label_box(x, y, rot, *label_size(r, h)).buffer(0.3) for r, (x, y, rot) in there.items()]
        keeps = [Point(*board.eda_point(hl["x"], hl["y"])).buffer(hl["keep"]) for hl in board.holes]
        keeps += [Point(*board.eda_point(x, y)).buffer(board.tooling_keep) for x, y in board.tooling]
        corner = s.get("board_label_corner", "bottom-left")
        if label_layer == BOTTOM:  # seen from the bottom, left and right swap
            corner = corner.replace("left", "@").replace("right", "left").replace("@", "right")
        spot = corner_spot(board_label_area(board, area), unary_union([*near, vias, *keeps]), lw, lh, corner)
        where = f" on the {s['board_label_side']}" if label_layer != layer else ""
        if spot:
            string(text, *spot, 0, lh, on=label_layer)
            print(f"  board label '{text}'{where} at ({spot[0]:.1f}, {spot[1]:.1f}) mm")
        else:
            print(f"  ! board label '{text}': no free spot"
                  + (" in board_label_region" if s.get("board_label_region") else "") + where)
    elif board.revision is None:
        print(f"  ! no board label: set revision in {board.file}")
    memo.write_text(json.dumps(created))
    eda.save_pcb(mcp)
    print(f"  {side}: {sum(1 for n in placed if n in attrs)} of {len((set(parts) - set(there)) | set(here))} "
          "designators placed"
          + (f" ({sum(1 for n in placed if n in other)} of {len(other)} through-hole parts of the other side)"
             if solder_side else "")
          + (f", fixed: {', '.join(sorted(here, key=natural_key))}" if here else "")
          + (f", groups {', '.join(g for g in (s.get('groups') or {}) if g in placed)}" if grouped else "")
          + f"; without room: {', '.join(missing) or '–'}")
    if there:
        print(f"  {far}: {len(there)} fixed designator{'s' if len(there) > 1 else ''}: "
              f"{', '.join(sorted(there, key=natural_key))}")
    for finding in findings:
        print(f"  ! {finding}")
    code = check(cfg, board, mcp, fp_silk, step)
    return 2 if findings else code


def check(cfg, board, mcp, footprint_silk=None, step=None):
    step = step or (lambda _: None)
    step("Gerber export: silkscreen on mask openings")
    folder = export_gerber(cfg, board, mcp)
    bad = 0
    for side, layer in SIDE.items():
        silk = gerber.shape(gerber.parse_gerber(folder / gerber.FILES[GERBER_KEYS[layer][1]]))
        own = silk.difference(footprint_silk.buffer(0.02)) if footprint_silk is not None and layer == SIDE[
            board.silk.get("designators", "top")] else silk
        hit, openings = silk_on_openings(folder, layer, own)
        img = cfg.artifact(f"silk_{board.name}_{side}.png")
        picture(silk, openings, board_shape(board), img, mirror=layer == BOTTOM)
        print(f"  {side}: silkscreen on mask openings {hit:.3f} mm² (target 0), picture -> {img}")
        bad += hit > 0.001
    step("DRC")
    code = pcb.drc_report(cfg, board, mcp, eda.drc(mcp))
    return 2 if bad else code


def preview(cfg, board):
    """Offline: the artwork, texts and fixed designators ([silk.place]) of the board file on the last Gerber export
    (edakit silk apply/check). A fixed designator in the way is a finding, as in apply: exit 2."""
    folder = cfg.artifact(f"gerber_{board.name}", ".keep").parent
    top = folder / gerber.FILES["top_silk"]
    if not top.exists():
        return eda.die(f"no Gerber export in {folder} – run `edakit silk check` once")
    area = board_shape(board).buffer(-0.5)
    h, fixed, findings = float(board.silk.get("label_h_mm", 1.0)), fixed_labels(board), []
    for side, layer in SIDE.items():
        mask_key, silk_key = GERBER_KEYS[layer]
        openings = gerber.shape(gerber.parse_gerber(folder / gerber.FILES[mask_key]))
        silk = gerber.shape(gerber.parse_gerber(folder / gerber.FILES[silk_key]))
        art = printable(art_shapes(cfg, board, side), area, openings)
        texts = silk_texts(board, side)
        here = {r: (x, y, rot) for r, (x, y, rot, on) in fixed.items() if on == side}
        if art.is_empty and not texts and not here:
            continue
        labels = texts + [(r, x, y, rot, h, "default") for r, (x, y, rot) in here.items()]
        boxes = unary_union([label_box(x, y, rot, *label_size(t, th)) for t, x, y, rot, th, _ in labels]) \
            if labels else Polygon()
        img = cfg.artifact(f"silk_preview_{board.name}_{side}.png")
        picture(silk.union(art), openings, board_shape(board), img, mirror=layer == BOTTOM,
                extra=[(boxes, "#7fb3ff")], texts=labels)
        findings += fixed_findings(here, h, area, openings, texts, side)
        print(f"  {side}: artwork {art.area:.0f} mm², {len(texts)} texts"
              + (f", {len(here)} fixed designator{'s' if len(here) > 1 else ''}" if here else "")
              + f" (blue boxes) -> {img}")
    for finding in findings:
        print(f"  ! {finding}")
    return 2 if findings else 0


def main(cfg, args):
    board = cfg.board(args.board, made=True)
    if args.action == "preview":
        return preview(cfg, board)
    if is_kicad(cfg):                 # the KiCad project: the same placement, written into the file (handbook 16)
        from .toolchain.kicad import silk as kicad_silk
        from .toolchain.kicad.board import BoardError
        from .toolchain.kicad.cli import CliError
        try:
            step = eda.Steps(APPLY_STEPS - 1) if args.action == "apply" else None
            return kicad_silk.apply(cfg, board, step, args.verbose) if args.action == "apply" else \
                kicad_silk.check(cfg, board, verbose=args.verbose)
        except (BoardError, CliError) as e:
            return eda.die(str(e))
    step = eda.Steps(APPLY_STEPS) if args.action == "apply" else None
    if step:
        step("bridge and PCB")
    mcp = eda.connect(cfg, args.verbose)
    try:
        eda.open_project(mcp, cfg)
        eda.open_pcb(mcp, board.pcb)
        return apply(cfg, board, mcp, step) if args.action == "apply" else check(cfg, board, mcp)
    except eda.MCPError as e:
        return eda.die(str(e))
    finally:
        mcp.close()
