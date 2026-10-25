"""Silkscreen: designators where there is room, checked on the Gerber export.

    edakit silk apply   hide the designators of the sides in [boards.<b>.silk] hide; place those of the side in
                        `designators` next to their part where nothing is in the way; export Gerber, check, DRC
    edakit silk check   export Gerber and only check: own silkscreen on solder-mask openings (JLCPCB cuts it off there)

Placement: every designator gets the first free spot above, below, right or left of its part (horizontal, then
vertical, then at the corners) – not on pads, footprint silkscreen, other parts or other labels. Test points and the
tightest parts come first. A spot on a via (tented, the print holds) only when nothing else is free. Groups
([boards.<b>.silk] groups = {"R1-R8" = [...]}) get one common label when the single labels do not fit.

Run it again after every auto-layout and routing: the spots depend on where the small parts and vias ended up.
API notes: designators are attributes (PCB_PrimitiveAttribute, key 'Designator'); modify works on locked parts too;
alignMode 5 = centre on x/y. Stroke font 'default': measured 0.5-0.6 x height per character.
"""

from __future__ import annotations

from pathlib import Path

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from . import eda, gerber
from .config import BOTTOM, MIL_PER_MM, TOP
from .design import natural_key
from .eda import api, ensure_pcb_focus

SIDE = {"top": TOP, "bottom": BOTTOM}
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


def label_size(name, h):
    return 0.65 * h * len(name), h


def label_box(x, y, rot, w, h):
    return box(x - w / 2, y - h / 2, x + w / 2, y + h / 2) if rot == 0 else box(x - h / 2, y - w / 2, x + h / 2, y + w / 2)


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


def place_labels(parts, blocked, vias, area, h, gap, groups=None, priority=("TP",)):
    """parts: {designator: bbox}, blocked: pads, footprint silk, parts; vias: via areas; area: printable board.
    Returns {label: (x, y, rotation)}, parts covered by a group label, parts without a spot."""
    hard, soft = blocked, blocked.union(vias)
    placed, taken = {}, []

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


def picture(silk, openings, area, out, mirror=False):
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
    for g, color in ((area, "#0f5a2a"), (openings.intersection(area), "#c9b26a"), (silk, "#f4f2ea")):
        p = patch(g, color)
        if p:
            ax.add_patch(p)
    ax.set_xlim(x0 - 5, x1 + 5)
    ax.set_ylim(y0 - 5, y1 + 5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(out, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def apply(cfg, board, mcp):
    s = board.silk
    side = s.get("designators", "top")
    h, gap = float(s.get("label_h_mm", 1.0)), float(s.get("gap_mm", 0.25))
    layer = SIDE[side]
    hide = {SIDE[x] for x in s.get("hide", [])} | {layer}  # the placed side is hidden first, then shown at its spot
    ensure_pcb_focus(mcp)
    comps = {c["PrimitiveId"]: c for c in map(eda.state, api(mcp, "PCB_PrimitiveComponent.getAll") or [])}
    attrs = {}
    for a in map(eda.state, api(mcp, "PCB_PrimitiveAttribute.getAll") or []):
        c = comps.get(a.get("ParentPrimitiveId"))
        if a.get("Key") == "Designator" and c:
            attrs[c["Designator"]] = (a, c)
            if c.get("Layer") in hide and a.get("ValueVisible"):
                api(mcp, "PCB_PrimitiveAttribute.modify", a["PrimitiveId"], {"valueVisible": False})
    eda.save_pcb(mcp)
    folder = export_gerber(cfg, board, mcp)  # now the silk layer holds only the footprints' own print
    mask_key, silk_key = GERBER_KEYS[layer]
    openings = gerber.shape(gerber.parse_gerber(folder / gerber.FILES[mask_key]))
    fp_silk = gerber.shape(gerber.parse_gerber(folder / gerber.FILES[silk_key]))
    parts = {}
    for ref, (a, c) in attrs.items():
        if c.get("Layer") == layer:
            bb = api(mcp, "PCB_Primitive.getPrimitivesBBox", [c["PrimitiveId"]])
            parts[ref] = (mm(bb["minX"]), mm(bb["minY"]), mm(bb["maxX"]), mm(bb["maxY"]))
    blocked = unary_union([openings.buffer(0.15), fp_silk.buffer(0.15)] + [box(*bb) for bb in parts.values()])
    vias = unary_union([Point(mm(v["X"]), mm(v["Y"])).buffer(mm(v["Diameter"]) / 2 + 0.1)
                        for v in map(eda.state, api(mcp, "PCB_PrimitiveVia.getAll") or [])])
    area = board_shape(board).buffer(-0.5)
    placed, grouped, missing = place_labels(parts, blocked, vias, area, h, gap, s.get("groups"),
                                            tuple(s.get("priority", ["TP"])))
    for n, (name, (x, y, rot)) in enumerate(placed.items()):
        if n % 20 == 0:
            ensure_pcb_focus(mcp)
        if name in attrs:
            api(mcp, "PCB_PrimitiveAttribute.modify", attrs[name][0]["PrimitiveId"],
                {"x": to_mil(x), "y": to_mil(y), "rotation": rot, "alignMode": 5, "fontSize": to_mil(h), "lineWidth": 6,
                 "valueVisible": True})
        else:  # group label in the same stroke font
            api(mcp, "PCB_PrimitiveString.create", layer + 2, to_mil(x), to_mil(y), name, "default", to_mil(h), 6, 5,
                rot, False, 0, False, False)
    eda.save_pcb(mcp)
    print(f"  {side}: {sum(1 for n in placed if n in attrs)} of {len(parts)} designators placed"
          + (f", groups {', '.join(g for g in (s.get('groups') or {}) if g in placed)}" if grouped else "")
          + f"; without room: {', '.join(missing) or '–'}")
    return check(cfg, board, mcp, fp_silk)


def check(cfg, board, mcp, footprint_silk=None):
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
    found = eda.drc(mcp)
    print("  " + eda.describe_drc(found))
    return 2 if bad or found else 0


def main(cfg, args):
    board = cfg.board(args.board)
    mcp = eda.connect(cfg, args.verbose)
    try:
        eda.open_project(mcp, cfg)
        eda.open_pcb(mcp, board.pcb)
        return apply(cfg, board, mcp) if args.action == "apply" else check(cfg, board, mcp)
    except eda.MCPError as e:
        return eda.die(str(e))
    finally:
        mcp.close()
