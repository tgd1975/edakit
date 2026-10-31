"""Route a board with Freerouting instead of EasyEDA's autorouter, and write the result into EasyEDA.

EasyEDA's autorouter (PCB_Document.autoRouting, beta) keeps its result only if the whole run succeeds – otherwise it
throws every track away (1773 lines -> 223 in one observed run). It runs past the bridge timeout, sometimes does not
start, has a fixed 900 s limit and left nets open. So routing happens outside EasyEDA, reproducibly:

    1 read     pads, outline, holes, parts from EasyEDA -> <artifacts>/route/<board>_board.json
    2 dsn      offline: our own Specctra DSN (rules from [routing] of the board file; with widths = "sim" every net
               at least the IPC-2221 width of its simulated current); parts, pins and nets in a fixed order; with
               fanout on a plane, a protected via and stub for each SMD pad on the other layer; with
               hand_solder_keep_mm a via keep-out around every hand-soldered joint on its solder side (GEO.spacing)
    3 route    offline: Freerouting (pinned, downloads itself once, SHA-256 checked), no GUI -> <board>.ses
    4 check    offline: pads of different parts on different nets at least the clearance apart (GEO.spacing), SMD pads on
               an assembled side at least the paste gap apart (GEO.spacing), pads of other nets at least
               hand_solder_keep_mm from a hand-soldered joint on its solder side (GEO.spacing; no new attempt helps there),
               every net connected, clearances >= rule, nothing in keep-outs, vias of other nets at least
               hand_solder_keep_mm from a hand-soldered joint (GEO.spacing), track widths of the SES and the fixed wires
               against the simulated currents (GEO.width as in the gate: below IPC-2221 fails, below the class width
               warns); with [looks] the track length per side, the vias and the visible side against its limits
               (warnings only); preview PNG with open connections in yellow.
               In `all`: up to `attempts` runs with a reshuffled DSN while something is open.
               A pour-only net (pour_only in [[pours]] of the board file) gets no tracks: its pour, computed here,
               connects it
    5 apply    delete all tracks, vias and pours in the PCB, create the ones from the SES, compare geometrically,
               delete anything unplanned
    6 pours    pours of [[pours]] anew and filled; optional stitching of loose islands with vias. With
               pour_regions, nets that share a layer get the outlines of their own areas, computed from board and SES
    7 reload   save, close the PCB tab, open it again – otherwise the DRC reports false connection errors
    8 drc      EasyEDA DRC with details -> <board>_drc.json; exit 2 on findings. With a "Netlist Error – Import
               Changes" item it compares schematic and PCB as `pcb parts` and `pcb nets` do (-> <board>_netlist_diff.json):
               no difference = EasyEDA only waits for the import acknowledgement (Design → Import Changes once),
               exit 3 when that is the only item

    edakit route all                 # 1-8, progress per step; exit 0 = DRC 0, 3 = only the acknowledgement pending
    edakit route route --passes 60   # single steps
    edakit route diagnose [--net N]  # offline: why each open connection is open – unreachable on the empty board
                                     # (what walls it in), blocked by the routed copper of other nets (which), or a
                                     # free way left; congestion (RUDY); pictures in route/<board>_diagnose/

We write the DSN ourselves instead of PCB_ManufactureData.getDsnFile: that returned null (PCB tab "inactive"), and
the SES import (importAutoRouteSesFile) needs a File object the bridge cannot pass. Units: mil like EasyEDA (DSN
resolution mil 100), y up.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import re
import shutil
import subprocess
import time
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from . import eda, pcb
from .config import MIL_PER_MM, PASTE_GAP_MM, POUR_CLEARANCE_MM, POUR_MIN_WIDTH_MM
from .design import natural_key
from .eda import api, ensure_pcb_focus
from .toolchain import is_kicad

LAYERS = {1: "TOP", 2: "BOTTOM"}
SNAP_MIL = 0.5  # points closer than this count as one (EasyEDA drops pieces < ~0.5 mil)
POURED_UNIT = 10  # mil per unit: EasyEDA returns pour fills (PourFills) in 10 mil, tracks and pads in mil
REGION_GROW_MM = 0.2       # pour_regions: an outline reaches this far beyond its pieces, under the tracks between nets
REGION_SIMPLIFY_MM = 0.03  # and is simplified by this much (thousands of points otherwise)
REGION_NESTED_MM2 = 0.5    # a piece of another net larger than this inside a net's outline: EasyEDA cannot fill that
FANOUT_DIRECTIONS = 16     # fanout: a via is tried in this many directions around an SMD pad (22.5° apart),
FANOUT_STEP_MIL = 5        # the distance growing in these steps
FANOUT_REACH_MIL = 60      # up to this much beyond the nearest spot
EDGE_ARC_SEGMENTS = 8      # edge keep-out: chords per quarter circle around an inner corner (reach ≥ 0.989 d)
DSN_STEPS_PER_MIL = 100    # (resolution mil 100): Freerouting reads every DSN coordinate in steps of 0.01 mil

FR_VERSION = "2.4.1"
FR_ZIP = f"https://github.com/freerouting/freerouting/releases/download/v{FR_VERSION}/freerouting-{FR_VERSION}-linux-x64.zip"
FR_ZIP_SHA256 = "3ad5a956ab474b12f331d24195feadac90e8344b8e013c6a4ab26e203ce51519"
FR_HOME = Path(os.environ.get("EDAKIT_FREEROUTING_HOME") or Path.home() / ".local/share/freerouting")
FR_BIN = FR_HOME / f"freerouting-{FR_VERSION}-linux-x64/bin/freerouting"

T0 = time.time()


def say(msg):
    print(f"[{(time.time() - T0) / 60:4.1f} min] {msg}", flush=True)


class Rules:
    def __init__(self, board, clearance=None):
        r = board.routing
        self.board = board
        self.clear = clearance or r.get("clearance_mil", 6.5)
        self.signal = r.get("signal_mil", 10)
        d, drill = r.get("via", [24, 12])
        self.via = (f"via{d}", d, drill)
        self.edge_um = r.get("edge_clearance_um", 400)
        self.cost = {k: tuple(v) for k, v in r.get("layer_cost", {"TOP": [1.0, 1.8], "BOTTOM": [1.5, 2.5]}).items()}
        self.passes = r.get("passes", 40)
        self.attempts = r.get("attempts", 5)
        self.classes = {name: (c["width_mil"], set(c["nets"])) for name, c in r.get("classes", {}).items()}
        self.pour_only = defaultdict(list)  # net -> [(layer, clearance mil, min width mil)]
        for p in board.pours:
            if p.get("pour_only"):
                for layer in p.get("layers", ["TOP", "BOTTOM"]):  # as `pcb pour` pours them
                    self.pour_only[p["net"]].append((layer, p.get("clearance_mm", POUR_CLEARANCE_MM) * MIL_PER_MM,
                                                     p.get("min_width_mm", POUR_MIN_WIDTH_MM) * MIL_PER_MM))
        self.pour_only = dict(self.pour_only)
        # GEO.spacing: copper of other nets keeps this much (mil) from a hand-soldered joint on its solder side; 0 = off.
        # hand: the designators soldered by hand (bom: false in the graph) – set by the caller, who has the graph
        self.joint_keep = r.get("hand_solder_keep_mm", 0) * MIL_PER_MM
        self.hand = set()
        # pour_regions: layer -> [(net, clearance mil, min width mil)] in claim order (priority, then as written), for
        # the layers that several nets pour on
        self.regions = {}
        if board.pour_regions:
            by_layer = defaultdict(list)
            for _, p in sorted(enumerate(board.pours), key=lambda ip: (ip[1].get("priority", 1), ip[0])):
                for layer in p.get("layers", ["TOP", "BOTTOM"]):  # as `pcb pour` pours them
                    if all(n != p["net"] for n, _, _ in by_layer[layer]):
                        by_layer[layer].append((p["net"], p.get("clearance_mm", POUR_CLEARANCE_MM) * MIL_PER_MM,
                                                p.get("min_width_mm", POUR_MIN_WIDTH_MM) * MIL_PER_MM))
            self.regions = {layer: nets for layer, nets in sorted(by_layer.items()) if len(nets) > 1}
        self.min_piece = board.pour_min_piece_mm2 * MIL_PER_MM ** 2

    def net_class(self, net):
        for name, (w, nets) in self.classes.items():
            if net in nets:
                return name, w
        return "SIGNAL", self.signal


def paths(cfg, board):
    d = cfg.artifact("route", ".keep").parent
    return {k: d / f"{board.name}{suffix}" for k, suffix in
            (("board", "_board.json"), ("dsn", ".dsn"), ("ses", ".ses"), ("log", "_freerouting.log"),
             ("png", "_routing.png"), ("drc", "_drc.json"), ("netlist_diff", "_netlist_diff.json"),
             ("stitch", "_stitch.json"), ("diagnose", "_diagnose"))}


# --- 1 read -------------------------------------------------------------------------------------------------------

def polyline_points(poly):
    src = poly["polygon"] if isinstance(poly, dict) else poly
    nums = [v for v in src if isinstance(v, (int, float))]
    if any(isinstance(v, str) and v != "L" for v in src):
        raise SystemExit(f"outline contains arcs ({[v for v in src if isinstance(v, str)]}) – only lines supported; "
                         "draw it with `edakit pcb apply`")
    return list(zip(nums[0::2], nums[1::2]))


def read_board(mcp, board):
    comps = {}
    for c in api(mcp, "PCB_PrimitiveComponent.getAll") or []:
        st = eda.state(c)
        if st.get("Designator"):
            comps[st["PrimitiveId"]] = {"ref": st["Designator"], "x": st["X"], "y": st["Y"], "rot": st["Rotation"],
                                        "layer": st["Layer"]}
    pads = []
    for p in api(mcp, "PCB_PrimitivePad.getAll") or []:
        st = eda.state(p)
        owner = next((cid for cid in comps if st["PrimitiveId"].startswith(cid)), None)
        pads.append({"id": st["PrimitiveId"], "ref": comps[owner]["ref"] if owner else None, "num": st["PadNumber"],
                     "net": st.get("Net") or "", "x": st["X"], "y": st["Y"], "rot": st.get("Rotation") or 0,
                     "layer": st["Layer"], "shape": st["Pad"], "hole": st.get("Hole"),
                     "hole_off": [st.get("HoleOffsetX") or 0, st.get("HoleOffsetY") or 0]})
    outlines = [polyline_points(eda.state(p)["Polygon"]) for p in api(mcp, "PCB_PrimitivePolyline.getAll") or []
                if eda.state(p)["Layer"] == pcb.BOARD_OUTLINE_LAYER]
    lines = [eda.state(x) for x in api(mcp, "PCB_PrimitiveLine.getAll") or [] if eda.state(x)["Layer"] in LAYERS]
    vias = [eda.state(v) for v in api(mcp, "PCB_PrimitiveVia.getAll") or []]
    out = {"pcb": board.pcb, "components": list(comps.values()), "pads": pads, "outlines": outlines,
           "existing": {"lines": len(lines), "vias": len(vias)}}
    say(f"read: {len(comps)} parts, {len(pads)} pads ({sum(1 for p in pads if not p['ref'])} without a part), "
        f"{len(outlines)} outlines, in the PCB {len(lines)} track pieces, {len(vias)} vias")
    return out


# --- 2 dsn --------------------------------------------------------------------------------------------------------

def q(s):
    return '"' + str(s).replace('"', "'") + '"'


def f(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")


def rot(pt, deg):
    a = math.radians(deg)
    return pt[0] * math.cos(a) - pt[1] * math.sin(a), pt[0] * math.sin(a) + pt[1] * math.cos(a)


def pad_layers(pad):
    return ["TOP", "BOTTOM"] if pad["layer"] == 12 else [LAYERS[pad["layer"]]]


def pad_shapes(pad):
    """DSN shapes of a pad relative to its centre, rotated (EasyEDA: width in x, height in y, then rotated
    counter-clockwise by 'rot'). THT pads (layer 12) on both layers."""
    kind, w, h = pad["shape"][0], pad["shape"][1], pad["shape"][2]
    r = pad["rot"] % 360
    if kind in ("ELLIPSE", "OVAL") and abs(w - h) < 1e-6:
        return [f"(circle {{L}} {f(w)})"]
    if kind in ("ELLIPSE", "OVAL"):  # slot shape; a true ellipse lies inside it
        d, half = min(w, h), (max(w, h) - min(w, h)) / 2
        a, b = ((-half, 0), (half, 0)) if w > h else ((0, -half), (0, half))
        a, b = rot(a, r), rot(b, r)
        return [f"(path {{L}} {f(d)} {f(a[0])} {f(a[1])} {f(b[0])} {f(b[1])})"]
    if kind in ("RECT", "POLYGON"):  # corner radius ignored – the rectangle encloses the pad
        corners = [rot(c, r) for c in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
        if r % 90 == 0:
            xs, ys = [c[0] for c in corners], [c[1] for c in corners]
            return [f"(rect {{L}} {f(min(xs))} {f(min(ys))} {f(max(xs))} {f(max(ys))})"]
        return ["(polygon {L} 0 " + " ".join(f"{f(x)} {f(y)}" for x, y in corners) + ")"]
    raise SystemExit(f"pad shape {pad['shape']} ({pad['ref']}.{pad['num']}) not supported – extend route.pad_shapes")


def pad_outline(pad):
    """Copper of a pad in absolute coordinates (shapely), for checking the SES."""
    kind, w, h = pad["shape"][0], pad["shape"][1], pad["shape"][2]
    c = Point(pad["x"], pad["y"])
    if kind in ("ELLIPSE", "OVAL"):
        d, half = min(w, h), (max(w, h) - min(w, h)) / 2
        if half < 1e-6:
            return c.buffer(d / 2)
        a, b = ((-half, 0), (half, 0)) if w > h else ((0, -half), (0, half))
        a, b = rot(a, pad["rot"]), rot(b, pad["rot"])
        return LineString([(pad["x"] + a[0], pad["y"] + a[1]), (pad["x"] + b[0], pad["y"] + b[1])]).buffer(d / 2)
    corners = [rot(p, pad["rot"]) for p in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
    return Polygon([(pad["x"] + x, pad["y"] + y) for x, y in corners])


def board_area(data):
    """Largest outline = the board, the others (circles of mounting holes) = holes."""
    polys = sorted((Polygon(o) for o in data["outlines"]), key=lambda p: -p.area)
    if not polys:
        raise SystemExit("no board outline (layer 11) in the PCB – run `edakit pcb apply` first")
    return polys[0], polys[1:]


def hole_keeps(rules, data):
    """Keep-out circles (x, y, r in mil) around mounting holes: radius 'keep' of the matching hole in the board file."""
    board = rules.board
    _, holes = board_area(data)
    out = []
    for h in holes:
        c = h.centroid
        r = math.sqrt(h.area / math.pi)
        spec = min(board.holes, key=lambda s: math.dist(board.eda_point(s["x"], s["y"]),
                                                        (c.x / MIL_PER_MM, c.y / MIL_PER_MM)), default=None)
        keep = spec["keep"] * MIL_PER_MM if spec else r + 0.5 * MIL_PER_MM
        out.append((c.x, c.y, max(keep, r)))
    return out


def tooling_keeps(rules):
    b = rules.board
    return [(*(v * MIL_PER_MM for v in b.eda_point(x, y)), b.tooling_keep * MIL_PER_MM) for x, y in b.tooling]


def circles(keeps):
    return [Point(x, y).buffer(r) for x, y, r in keeps]


def planes(rules):
    """Pours declared as planes ([[pours]] plane = true): (net, layer). Freerouting takes the net's pads on that layer
    (and its through-hole pads) as joined by the plane; it does not connect a pad on the other layer to it with a via –
    it routes a track to another pad of the net, or, with fanout = true, the fanout via connects it."""
    return [(p["net"], layer) for p in rules.board.pours if p.get("plane") for layer in p.get("layers", ["BOTTOM"])]


def _parts(geom):
    return [g for g in getattr(geom, "geoms", [geom]) if not g.is_empty]


def _polygons(geom):
    """The polygons of any geometry, also inside collections."""
    if geom.geom_type == "Polygon":
        return [] if geom.is_empty else [geom]
    return [p for g in getattr(geom, "geoms", []) for p in _polygons(g)]


def flat_on_grid(poly):
    """True for a polygon with no area left once its corners are rounded to the DSN's grid (DSN_STEPS_PER_MIL), as
    Freerouting reads them: a slice thinner than 0.01 mil. Freerouting skips such a keep-out with "Keepout zone … was
    skipped because its geometry is degenerate"."""
    return Polygon([(round(x * DSN_STEPS_PER_MIL), round(y * DSN_STEPS_PER_MIL))
                    for x, y in poly.exterior.coords]).area == 0


def convex_pieces(geom, min_area=1.0):
    """Split a (possibly concave, multi-part) area into convex pieces: horizontal strips at every vertex, then
    vertical cuts where a strip is still concave. Freerouting wants convex keep-outs. A piece under min_area (mil²)
    is left out, and so is one with no area on the DSN's grid (flat_on_grid) – two vertices less than 0.01 mil apart
    in height leave such a slice."""
    pieces = []
    for g in _parts(geom):
        if g.geom_type != "Polygon":
            continue
        x0, y0, x1, y1 = g.bounds
        ys = sorted({y for ring in (g.exterior, *g.interiors) for _, y in ring.coords} | {y0, y1})
        for a, b in zip(ys, ys[1:]):
            if b - a < 1e-6:
                continue
            for s in _parts(g.intersection(box(x0 - 1, a, x1 + 1, b))):
                if s.geom_type != "Polygon" or s.area < min_area or flat_on_grid(s):
                    continue
                if s.convex_hull.area - s.area < 0.5:
                    pieces.append(s)
                    continue
                xs = sorted({x for x, _ in s.exterior.coords})
                for c, d in zip(xs, xs[1:]):
                    pieces += [u for u in _parts(s.intersection(box(c, a, d, b)))
                               if u.geom_type == "Polygon" and u.area >= min_area and not flat_on_grid(u)]
    bad = [p for p in pieces if p.convex_hull.area - p.area > 0.5]
    if bad:
        raise SystemExit(f"{len(bad)} keep-out pieces are not convex – route.convex_pieces needs a look")
    return pieces


def outside_strips(rules, outer, margin=20.0):
    """Area between a rectangle around the board and the outline moved in by the edge clearance, as convex pieces.
    Freerouting 2.4.1 routed nothing in the upper part of a concave outline given as boundary; the same nets routed at
    once with a rectangle. So: rectangle as boundary, everything outside the board as keep-outs. The outline is moved
    in with round joins: around an inner corner (a notch) the keep-out is an arc of the edge clearance d, in chords.
    GEOS gives an arc of θ round(θ / (90° / EDGE_ARC_SEGMENTS)) chords, at least one, so with 8 a chord spans at most
    16.875° (an arc just under that: one chord) and the keep-out reaches at least d · cos(8.4375°) = 0.989 d into the
    board – 0.3957 mm with 0.4 mm, 4.3 µm short of the arc. With 4 a chord spanned up to 33.75° (0.383 mm). Mitred
    joins reached d / sin(θ/2) into the board there – 0.57 mm at a 90° corner and 1.3 mm at a 36° notch with 0.4 mm.
    Outlines without inner corners get the same strips either way.
    Every piece Freerouting can read is kept, however small: the cuts at the arc's vertices leave slices under 1 mil²
    at a sharp notch tip, and without them the keep-out reached 0.3 mm into the board there instead of the clearance.
    Only a slice with no area on the DSN's grid is left out (flat_on_grid): on a round board read back from EasyEDA,
    mirrored corners lie up to 1e-4 mil apart in height, and the cuts at both left slices of 4e-6 to 7e-5 mil that
    Freerouting skipped as degenerate. The seam such a slice leaves is thinner than 0.01 mil – no copper passes it –,
    and `route check` tests the strips Freerouting was given."""
    inner = outer.buffer(-rules.edge_um / 25.4, join_style="round", quad_segs=EDGE_ARC_SEGMENTS)
    x0, y0, x1, y1 = outer.bounds
    frame = box(x0 - margin, y0 - margin, x1 + margin, y1 + margin)
    return frame, convex_pieces(frame.difference(inner), min_area=0)


def keepout_areas(rules, data):
    """[[routing.keepouts]] as the board file has them: [(index, layers, what, area in mil)], the windows cut out."""
    board = rules.board
    out = []
    for i, k in enumerate(board.routing.get("keepouts", [])):
        if "rect" in k:
            x0, y0, x1, y1 = k["rect"]
            pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        else:
            pts = [tuple(p) for p in k["polygon"]]
        area = Polygon([tuple(v * MIL_PER_MM for v in board.eda_point(x, y)) for x, y in pts]).buffer(0)
        m = k.get("window_mm", 1.5) * MIL_PER_MM
        win = [pad_outline(p).buffer(m, join_style=2).envelope for p in data["pads"] if p["ref"] in k.get("windows", [])]
        if win:
            area = area.difference(unary_union(win))
        layers = [k["layer"]] if isinstance(k.get("layer"), str) else list(k.get("layer", ["TOP", "BOTTOM"]))
        out.append((i, layers, k.get("what", "wire"), area))
    return out


def config_keepouts(rules, data):
    """[[routing.keepouts]]: {layer, rect | polygon (plan mm), what: "wire" (vias allowed) | "all",
    windows: [parts whose pads stay reachable, with window_mm margin]} -> [(layer, kind, convex piece in mil)]."""
    return [(layer, what, piece) for _, layers, what, area in keepout_areas(rules, data) for layer in layers
            for piece in convex_pieces(area)]


def hand_soldered(graph, board):
    """Designators of the parts soldered by hand on this board: bom: false in the graph (the inner object, as
    design.load_graph returns it) – on an Economic PCBA order the through-hole parts you solder yourself (8.4)."""
    return {c["designator"] for c in graph.get("components", [])
            if c.get("bom") is False and c.get("board", board) in (None, board)}


def hand_joints(data, hand):
    """GEO.spacing: every through-hole pad of a part in `hand`, with its solder side – the copper layer its part does not sit
    on. -> [(pad, layer)] in the order of the pads."""
    side = {c["ref"]: c["layer"] for c in data["components"]}
    return [(p, LAYERS[3 - side[p["ref"]]]) for p in data["pads"]
            if p["ref"] in hand and p["layer"] == 12 and side.get(p["ref"]) in LAYERS]


def joint_keepouts(rules, data):
    """GEO.spacing in the DSN: a via keep-out on the solder side around every hand-soldered joint, the pad grown by
    joint_keep – Specctra via_keepout, which Freerouting 2.4.1 reads. Its chords lie outside the true distance.
    Freerouting's keep-outs are not per net: a via of the joint's own net stays out too, its tracks still reach it.
    -> [(layer, convex polygon in mil)]"""
    if not rules.joint_keep:
        return []
    segs = 4
    grow = rules.joint_keep / math.cos(math.pi / (4 * segs))
    return [(layer, pad_outline(p).buffer(grow, quad_segs=segs)) for p, layer in hand_joints(data, rules.hand)]


def joint_gaps(data, keep_mil, hand, vias=(), waivers=({}, {})):
    """GEO.spacing: on the solder side of every through-hole pad of a hand-soldered part (hand_joints), vias and pads of other
    nets closer than keep_mil, copper to copper. Tracks do not count: they run under the solder mask, between the pins
    of a 2.54 mm part too (the owner's decision on #59). A pad without a net counts as a net of its own; the part's own
    pads are not compared, nor pads without a part (tooling holes). vias: [(net, or None when unknown, (x, y),
    diameter)] in mil; a via of unknown net counts as another net's. A finding is waived when the joint's part or net,
    or the other pad's part or the other net, has the accept (pad_accepts(graph, "GEO.spacing", "joint")). -> [{"joint", "net",
    "layer", "kind" ("pad", "via"), "other" (pad name, net or None), "other_net", "mil", "at" (the other pad's
    closest point, the via's centre), "waived"}], closest first; a pair of two joints once."""
    from shapely.ops import nearest_points
    from shapely.strtree import STRtree
    parts, nets = waivers
    items = {"TOP": [], "BOTTOM": []}   # (kind, name, net, ref, geometry, radius)
    for q in data["pads"]:
        if q["ref"]:
            for layer in pad_layers(q):
                items[layer].append(("pad", f"{q['ref']}.{q['num']}", q["net"] or None, q["ref"], pad_outline(q), 0))
    for net, v, d in vias:
        for layer in items:
            items[layer].append(("via", net, net, None, Point(v), d / 2))
    trees = {layer: STRtree([it[4] for it in its]) for layer, its in items.items()}
    found = {}
    for p, layer in hand_joints(data, hand):
        g, own = pad_outline(p), p["net"] or None
        name = f"{p['ref']}.{p['num']}"
        reach = keep_mil + max((it[5] for it in items[layer]), default=0)
        for j in trees[layer].query(g, predicate="dwithin", distance=reach):
            kind, other, onet, oref, h, r = items[layer][j]
            if oref == p["ref"] or (own and onet == own):
                continue
            gap = g.distance(h) - r
            if gap >= keep_mil - 0.01:
                continue
            key = tuple(sorted((name, other))) if kind == "pad" else (name, kind, other, h.x, h.y)
            if key in found and found[key]["mil"] <= gap:
                continue
            at = nearest_points(g, h)[1]
            found[key] = {"joint": name, "net": own, "layer": layer, "kind": kind, "other": other, "other_net": onet,
                          "mil": gap, "at": (at.x, at.y),
                          "waived": next((w[k] for w, k in ((parts, p["ref"]), (parts, oref), (nets, own), (nets, onet))
                                          if k and k in w), None)}
    return sorted(found.values(), key=lambda x: (round(x["mil"], 3), natural_key(x["joint"]), str(x["other"])))


def joint_text(item, keep_mil, board=None):
    """'J1.1 (VIN) – via GND at (84.00, 9.70): 0.30 mm apart on BOTTOM, the solder side of J1, below
    hand_solder_keep_mm 0.5' – the point in plan mm with the board, else in EasyEDA mm."""
    mm = 1 / MIL_PER_MM
    x, y = (v * mm for v in item["at"])
    if board is not None:
        x, y = board.plan_point(x, y)
    other = (f"pad {item['other']} ({item['other_net'] or 'no net'})" if item["kind"] == "pad"
             else f"via {item['other'] or '(no track, net unknown)'}")
    return (f"{item['joint']} ({item['net'] or 'no net'}) – {other} at ({x:.2f}, {y:.2f}): {item['mil'] * mm:.2f} mm "
            f"apart on {item['layer']}, the solder side of {item['joint'].split('.')[0]}, below hand_solder_keep_mm "
            f"{keep_mil * mm:g}")


def fixed_wires(rules):
    """[[routing.fixed_wires]]: {net, layer, width_mil, points (plan mm)} – protected in the DSN: Freerouting
    routes around them and keeps them (e.g. a short switching loop)."""
    b = rules.board
    return [(w["net"], w.get("layer", "TOP"), w.get("width_mil", rules.signal),
             [tuple(round(v * MIL_PER_MM, 2) for v in b.eda_point(x, y)) for x, y in w["points"]])
            for w in b.routing.get("fixed_wires", [])]


def fanout(rules, data):
    """[[pours]] fanout = true on a plane: every SMD pad of the net on a layer without its plane gets a via next to it
    and a stub from the pad's centre at the net's class width. Freerouting 2.4.1 does not connect such a pad to the
    plane, with its own fanout on or off; written into the DSN as protected wiring, it routes around them and keeps
    them. The spot: the nearest distance first (half the pad's larger side + via radius + clearance, then in
    FANOUT_STEP_MIL steps up to FANOUT_REACH_MIL further), at each distance FANOUT_DIRECTIONS directions, the one closest
    to the direction away from the part's centre first. Via and stub keep the clearance from foreign copper (pads, fixed
    wires, the other fanouts) and the fanout vias from each other; the via stays inside the edge clearance and off the
    hole, tooling and `what = "all"` keep-outs, the stub off those and off every keep-out on its layer; with GEO.spacing on, the
    via keeps joint_keep from the hand-soldered joints of other nets. A pad without a spot stops the run. -> [(net, "R1.1", layer, width, pad centre, via)] in mil, by net and pad."""
    on_plane = defaultdict(set)
    for net, layer in planes(rules):
        on_plane[net].add(layer)
    nets = {p["net"] for p in rules.board.pours if p.get("plane") and p.get("fanout")}
    todo = sorted((p for p in data["pads"] if p["net"] in nets and p["layer"] in LAYERS
                   and LAYERS[p["layer"]] not in on_plane[p["net"]]),
                  key=lambda p: (p["net"], natural_key(p["ref"] or "~"), natural_key(p["num"])))
    if not todo:
        return []
    r_via, clear, eps = rules.via[1] / 2, rules.clear, 0.01
    outer, _ = board_area(data)
    _, strips = outside_strips(rules, outer)
    forbidden = unary_union(strips + circles(hole_keeps(rules, data) + tooling_keeps(rules)))
    keep = config_keepouts(rules, data)
    keep_all = unary_union([g for _, what, g in keep if what != "wire"])                # no vias on either layer
    keep_wire = {lay: unary_union([g for la, _, g in keep if la == lay]) for lay in LAYERS.values()}  # no tracks
    # copper to keep the clearance from: (net, layers, geometry, half width, a fanout via)
    copper = [(p["net"] or f"nc:{p['id']}", set(pad_layers(p)), pad_outline(p), 0, False) for p in data["pads"]]
    copper += [(net, {layer}, LineString(pts), w / 2, False) for net, layer, w, pts in fixed_wires(rules)]
    comp_at = {c["ref"]: c for c in data["components"]}
    joints = [(p["net"], pad_outline(p)) for p, _ in hand_joints(data, rules.hand)] if rules.joint_keep else []
    steps = range(int(FANOUT_REACH_MIL / FANOUT_STEP_MIL) + 1)
    out = []

    def apart(g, half, other):
        return g.is_empty or g.distance(other) >= half + eps

    for p in todo:
        net, layer, w = p["net"], LAYERS[p["layer"]], rules.net_class(p["net"])[1]
        name, x, y = f"{p['ref'] or 'FREE'}.{p['num']}", p["x"], p["y"]
        c = comp_at.get(p["ref"])
        away = math.degrees(math.atan2(y - c["y"], x - c["x"])) if c and math.dist((x, y), (c["x"], c["y"])) > 0.01 \
            else 0.0
        turn = 360 / FANOUT_DIRECTIONS
        dirs = sorted(range(FANOUT_DIRECTIONS), key=lambda k: (abs((k * turn - away + 180) % 360 - 180), k))
        d0 = max(p["shape"][1], p["shape"][2]) / 2 + r_via + clear
        reach = Point(x, y).buffer(d0 + FANOUT_REACH_MIL + r_via + clear + w)
        near = [(n, lays, g, half, via) for n, lays, g, half, via in copper
                if (n != net or via) and g.distance(reach) <= half]
        spot = None
        for d in (d0 + i * FANOUT_STEP_MIL for i in steps):
            for k in dirs:
                a = math.radians(k * turn)
                v = (round(x + d * math.cos(a), 2), round(y + d * math.sin(a), 2))
                via, stub = Point(v), LineString([(x, y), v])
                if not (apart(forbidden, r_via, via) and apart(keep_all, r_via, via) and apart(forbidden, w / 2, stub)
                        and apart(keep_wire[layer], w / 2, stub)):
                    continue
                if all(via.distance(g) >= half + r_via + clear - eps and
                       (n == net or layer not in lays or stub.distance(g) >= half + w / 2 + clear - eps)
                       for n, lays, g, half, _ in near) and \
                        all(via.distance(g) >= r_via + rules.joint_keep - eps for n, g in joints if n != net):
                    spot = v
                    break
            if spot:
                break
        if spot is None:
            raise SystemExit(f"{name} ({net}): no room for a fanout via to the {net} plane – {FANOUT_DIRECTIONS} "
                             f"directions, {d0:.1f} to {d0 + FANOUT_REACH_MIL:.1f} mil from the pad's centre, keeping "
                             f"{clear} mil from foreign copper with a {rules.via[1]} mil via, inside the edge clearance "
                             "and off hole, tooling and keep-out areas"
                             + (" and hand_solder_keep_mm from hand-soldered joints of other nets" if joints else "")
                             + "; give the pad room in the plan")
        out.append((net, name, layer, w, (x, y), spot))
        copper.append((net, {"TOP", "BOTTOM"}, Point(spot), r_via, True))
        copper.append((net, {layer}, LineString([(x, y), spot]), w / 2, False))
    return out


def write_dsn(rules, data, out, variant=0):
    """Specctra DSN. Parts, pins and nets in a fixed order (designator, pad number, net name): Freerouting is
    deterministic but order-dependent – a part EasyEDA puts at the end of its list changed the result (one GND link
    open). variant > 0 shuffles parts and nets reproducibly so another attempt finds another way."""
    pads = sorted(data["pads"], key=lambda p: (natural_key(p["ref"] or "~"), str(p["num"])))
    rng = random.Random(variant) if variant else None
    if rng:
        refs = list(dict.fromkeys(p["ref"] or "FREE" for p in pads))
        rng.shuffle(refs)
        rank = {r: i for i, r in enumerate(refs)}
        pads.sort(key=lambda p: rank[p["ref"] or "FREE"])
    outer, _ = board_area(data)
    frame, strips = outside_strips(rules, outer)
    padstacks, images = {}, defaultdict(list)
    comp_at = {c["ref"]: c for c in data["components"]}
    nets, used_pin = defaultdict(list), defaultdict(set)
    for pad in pads:
        layers, shapes = pad_layers(pad), pad_shapes(pad)
        key = json.dumps([layers, shapes])
        if key not in padstacks:
            name = f"ps{len(padstacks)}"
            body = " ".join(f"(shape {s.replace('{L}', L)})" for L in layers for s in shapes)
            padstacks[key] = (name, f"(padstack {q(name)} {body} (attach off))")
        ref = pad["ref"] or "FREE"
        origin = comp_at.get(ref, {"x": 0, "y": 0})
        pin = re.sub(r"[^A-Za-z0-9_]", "_", str(pad["num"])) or "x"
        while pin in used_pin[ref]:
            pin += "_"
        used_pin[ref].add(pin)
        images[ref].append(f"(pin {q(padstacks[key][0])} {q(pin)} {f(pad['x'] - origin['x'])} {f(pad['y'] - origin['y'])})")
        if pad["net"]:
            nets[pad["net"]].append(f"{ref}-{pin}")
    # a pour-only net is left out of the network: its pads stay pins without a net, obstacles Freerouting keeps clear of
    routed = {n: p for n, p in nets.items() if len(p) > 1 and n not in rules.pour_only}
    cls = defaultdict(list)
    for n in sorted(routed):
        cls[rules.net_class(n)].append(n)
    keep = hole_keeps(rules, data) + tooling_keeps(rules)
    extra = config_keepouts(rules, data)
    fixed = fixed_wires(rules)
    fans = fanout(rules, data)
    L = [f"(pcb {q(data['pcb'])}",
         '  (parser (string_quote ") (space_in_quoted_tokens on) (host_cad "edakit") (host_version "1"))',
         # 1/100 mil: with 1/1000 mil Freerouting 2.4.1 computes wrongly (board ≈ 7 million units high: unreachable
         # pads, 19 phantom violations); with mil 100 it routed at once
         f"  (resolution mil {DSN_STEPS_PER_MIL})", "  (unit mil)", "  (structure"]
    for i, name in enumerate(("TOP", "BOTTOM")):
        L.append(f"    (layer {name} (type signal) (property (index {i})))")
    L.append("    (boundary (path pcb 0 " + " ".join(f"{f(x)} {f(y)}" for x, y in frame.exterior.coords) + "))")
    L.append(f"    (via {q(rules.via[0])})")
    L.append(f"    (rule (width {rules.signal}) (clearance {rules.clear}) (clearance {rules.clear} (type default_smd))"
             f" (clearance {rules.clear} (type smd_smd)))")
    # before the keep-outs: with autoroute_settings after them Freerouting 2.4.1 read no parts any more
    L.append("    (autoroute_settings (fanout off) (autoroute on) (postroute on) (vias on) (via_costs 50)"
             " (plane_via_costs 5) (start_ripup_costs 100) (start_pass_no 1)")
    for name, (pref, against) in rules.cost.items():
        direction = "horizontal" if name == "TOP" else "vertical"
        L.append(f"      (layer_rule {name} (active on) (preferred_direction {direction})"
                 f" (preferred_direction_trace_costs {pref}) (against_preferred_direction_trace_costs {against}))")
    L.append("    )")
    for i, (x, y, r) in enumerate(keep):
        for layer in ("TOP", "BOTTOM"):
            L.append(f"    (keepout {q(f'H{i}_{layer}')} (circle {layer} {f(2 * r)} {f(x)} {f(y)}))")
    for i, g in enumerate(strips):
        pts = list(g.exterior.coords)[:-1]
        for layer in ("TOP", "BOTTOM"):
            L.append(f"    (keepout {q(f'R{i}_{layer}')} (polygon {layer} 0 " + " ".join(f"{f(x)} {f(y)}" for x, y in pts)
                     + "))")
    for i, (layer, what, g) in enumerate(extra):
        kw = "wire_keepout" if what == "wire" else "keepout"
        pts = list(g.exterior.coords)[:-1]
        L.append(f"    ({kw} {q(f'K{i}')} (polygon {layer} 0 " + " ".join(f"{f(x)} {f(y)}" for x, y in pts) + "))")
    joints = joint_keepouts(rules, data)
    for i, (layer, g) in enumerate(joints):
        pts = list(g.exterior.coords)[:-1]
        L.append(f"    (via_keepout {q(f'J{i}_{layer}')} (polygon {layer} 0 " + " ".join(f"{f(x)} {f(y)}" for x, y in pts)
                 + "))")
    # planes last in the structure: placed further up, Freerouting 2.4.1 read no connections any more (0 unrouted)
    for net, layer in planes(rules):
        L.append(f"    (plane {q(net)} (polygon {layer} 0 "
                 + " ".join(f"{f(x)} {f(y)}" for x, y in list(outer.exterior.coords)[:-1]) + "))")
    L.append("  )")
    L.append("  (placement")
    for ref in images:
        o = comp_at.get(ref, {"x": 0, "y": 0})
        L.append(f"    (component {q('IMG_' + ref)} (place {q(ref)} {f(o['x'])} {f(o['y'])} front 0))")
    L.append("  )")
    L.append("  (library")
    for ref, pins in images.items():
        L.append(f"    (image {q('IMG_' + ref)}")
        L.extend(f"      {p}" for p in pins)
        L.append("    )")
    for _, text in padstacks.values():
        L.append(f"    {text}")
    L.append(f"    (padstack {q(rules.via[0])} (shape (circle TOP {rules.via[1]})) (shape (circle BOTTOM {rules.via[1]}))"
             " (attach off))")
    L.append("  )")
    L.append("  (network")
    order = sorted(routed)
    if rng:
        rng.shuffle(order)
    for n in order:
        L.append(f"    (net {q(n)} (pins {' '.join(routed[n])}))")
    for (name, w), members in cls.items():
        L.append(f"    (class {q(name)} {' '.join(q(m) for m in members)} (circuit (use_via {q(rules.via[0])}))"
                 f" (rule (width {w}) (clearance {rules.clear})))")
    L.append("  )")
    L.append("  (wiring")
    for net, layer, w, pts in fixed:
        L.append(f"    (wire (path {layer} {f(w)} " + " ".join(f"{f(x)} {f(y)}" for x, y in pts)
                 + f") (net {q(net)}) (type protect))")
    for net, _, layer, w, (x0, y0), (x, y) in fans:
        L.append(f"    (wire (path {layer} {f(w)} {f(x0)} {f(y0)} {f(x)} {f(y)}) (net {q(net)}) (type protect))")
        L.append(f"    (via {q(rules.via[0])} {f(x)} {f(y)} (net {q(net)}) (type protect))")
    L.append("  )")
    L.append(")")
    out.write_text("\n".join(L) + "\n")
    say(f"DSN: {len(routed)} nets with >= 2 pins, {len(data['pads'])} pads, {len(padstacks)} padstacks, {len(keep)} hole "
        f"keep-outs, {len(strips)} edge strips, {len(extra)} keep-out pieces, {len(fixed)} fixed wires, "
        + (f"{len(fans)} fanout vias, " if fans else "")
        + (f"{len(joints)} via keep-outs at hand-soldered joints (GEO.spacing), " if joints else "") + f"clearance {rules.clear} mil"
        + (f", order {variant}" if variant else "")
        + (f", pour-only (no tracks): {', '.join(sorted(rules.pour_only))}" if rules.pour_only else "") + f" -> {out}")
    for (name, w), members in sorted(cls.items()):
        print(f"    class {name}: {w} mil, {len(members)} nets", flush=True)


def sim_widths(cfg, board, rules):
    """[routing] widths = "sim": every class of [routing.classes] at least the IPC-2221 width (1.5 x the simulated
    current, as GEO.width of the gate) of its widest net, and a net outside the classes that needs more than signal_mil a
    class of its own, named after the net; widths rounded up to 0.1 mil. Changes rules.classes, prints what it widened.
    Fixed wires keep their own width_mil – `route check` measures them."""
    from .design import Design
    from .release.fab import required_widths
    need = required_widths(cfg, Design.from_config(cfg), board) if cfg.graph.exists() else None
    if need is None:
        raise SystemExit(f'board {board.name}: [routing] widths = "sim" needs the simulated currents '
                         f"({cfg.relative(cfg.artifacts / 'sim' / 'net_currents.json')}) – run `edakit sim` first")
    mil = {n: math.ceil(v[0] * MIL_PER_MM * 10 - 1e-9) / 10 for n, v in need.items()}
    lines = []
    for name, (w, nets) in list(rules.classes.items()):
        top = max((mil[n] for n in nets if n in mil), default=0)
        if top > w:
            rules.classes[name] = (top, nets)
            why = ", ".join(f"{n} {need[n][2]:.2f} A" for n in sorted(nets) if mil.get(n) == top)
            lines.append(f"class {name}: {w:g} -> {top:g} mil ({why})")
    taken = {n for _, nets in rules.classes.values() for n in nets}
    for n in sorted(mil):
        if n not in taken and mil[n] > rules.signal:
            name = n if n not in rules.classes else f"{n}_NET"
            rules.classes[name] = (mil[n], {n})
            lines.append(f"class {name}: {mil[n]:g} mil, a class of its own ({n} {need[n][2]:.2f} A; signal_mil "
                         f"{rules.signal:g})")
    say('widths = "sim": ' + ("; ".join(lines) if lines else "every class already at its IPC-2221 width"))
    return lines


def report_widths(cfg, board, rules, routes):
    """GEO.width offline: the narrowest SES track of every net and every fixed wire against the widths of the gate's GEO.width
    (release.fab.required_widths): below IPC-2221 for 1.5 x the simulated current fails, below the practical width of
    the net class warns. Without net_currents.json one line and nothing fails, as before. -> the failures."""
    from .design import Design
    from .release.fab import required_widths
    need = required_widths(cfg, Design.from_config(cfg), board) if cfg.graph.exists() else None
    if need is None:
        say("track widths (GEO.width offline): no net currents – run `edakit sim` first")
        return []
    fixed = fixed_wires(rules)
    mm = 1 / MIL_PER_MM

    def is_fixed(net, layer, pts):
        return any(net == n and layer == lay and len(pts) == len(p2) and
                   max(map(math.dist, pts, p2), default=0) <= SNAP_MIL for n, lay, _, p2 in fixed)
    narrow = {}
    for net, r in routes.items():
        ws = [w for layer, w, pts in r["wires"] if not is_fixed(net, layer, pts)]
        if ws:
            narrow[net] = min(ws) * mm
    items = [(net, net, w) for net, w in sorted(narrow.items())]
    for spec, (net, _, w, _) in zip(rules.board.routing.get("fixed_wires", []), fixed):
        (x0, y0), (x1, y1) = spec["points"][0], spec["points"][-1]
        items.append((net, f"fixed wire {net} ({x0:g}, {y0:g})–({x1:g}, {y1:g})", w * mm))
    fail = [f"GEO.width (offline) {what}: {w:.2f} < {need[net][0]:.2f} mm" for net, what, w in items
            if net in need and w < need[net][0] - 0.005]
    warn = [f"GEO.width (offline) {what}: {w:.2f} < {need[net][1]:.2f} mm – below the practical width of its class "
            "(warning)" for net, what, w in items if net in need and need[net][0] - 0.005 <= w < need[net][1] - 0.005]
    wires = f" and {len(fixed)} fixed wire{'s' * (len(fixed) != 1)}" if fixed else ""
    say(f"track widths (GEO.width offline): {len(narrow)} nets{wires}, {len(fail)} below IPC-2221 for 1.5 x the simulated "
        f"current, {len(warn)} below the class width")
    for line in fail + warn:
        print(f"    {line}", flush=True)
    return fail


# --- 3 route ------------------------------------------------------------------------------------------------------

def freerouting_command():
    """Freerouting: $FREEROUTING_BIN, or $FREEROUTING_JAR with java >= 21, or (Linux x64) the release zip with its own
    Java runtime, downloaded once and checked by SHA-256. The system Java 17 is too old for Freerouting 2.x."""
    if os.environ.get("FREEROUTING_BIN"):
        return [os.environ["FREEROUTING_BIN"]]
    if os.environ.get("FREEROUTING_JAR"):
        return ["java", "-jar", os.environ["FREEROUTING_JAR"]]
    if FR_BIN.exists():
        return [str(FR_BIN)]
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        raise SystemExit(f"no Freerouting: set FREEROUTING_JAR to freerouting-{FR_VERSION}.jar (Java 21+) or "
                         "FREEROUTING_BIN to the executable")
    say(f"Freerouting {FR_VERSION} missing – downloading {FR_ZIP}")
    FR_HOME.mkdir(parents=True, exist_ok=True)
    tmp = FR_HOME / f"freerouting-{FR_VERSION}.zip"
    with urllib.request.urlopen(FR_ZIP) as r, open(tmp, "wb") as fh:
        shutil.copyfileobj(r, fh)
    digest = hashlib.sha256(tmp.read_bytes()).hexdigest()
    if digest != FR_ZIP_SHA256:
        tmp.unlink()
        raise SystemExit(f"checksum mismatch: {digest} instead of {FR_ZIP_SHA256}")
    with zipfile.ZipFile(tmp) as z:
        z.extractall(FR_HOME)
    tmp.unlink()
    FR_BIN.chmod(0o755)
    return [str(FR_BIN)]


def run_freerouting(dsn, ses, log, passes, threads, optimize=True, edge_um=400):
    exe = freerouting_command()
    ses.unlink(missing_ok=True)
    # no GUI, no usage data, no API server; fanout off (it would put a via at every SMD pad first)
    cmd = [*exe, "-de", str(dsn), "-do", str(ses), "-mp", str(passes), "-mt", str(threads), "--gui.enabled=false",
           "--api_server.enabled=false", "-da", "--router.fanout.enabled=false",
           f"--router.copper_to_edge_clearance_um={edge_um}", f"--router.optimizer.enabled={str(optimize).lower()}"]
    say(f"Freerouting {FR_VERSION}: up to {passes} passes, {threads} threads, optimiser {'on' if optimize else 'off'}")
    t = time.time()
    with open(log, "w") as fh:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=dsn.parent)
        last = 0
        for line in proc.stdout:
            fh.write(line)
            low = line.lower()
            if re.search(r"pass #|unrouted|optimi|error|exception|warn|saving|completed|finished", low):
                if time.time() - last > 5 or re.search(r"pass #|error|exception|completed|finished|saving", low):
                    msg = re.sub(r"^\S+ \S+ +\w+ +(\[[^]]*\] )?", "", line.strip())
                    print(f"    {time.time() - t:5.0f} s  {re.sub(r' on board .[0-9a-f]+.', '', msg)[:150]}", flush=True)
                    last = time.time()
        proc.wait()
    if proc.returncode != 0 or not ses.exists():
        raise SystemExit(f"Freerouting without result (exit {proc.returncode}) – log: {log}")
    say(f"Freerouting done after {(time.time() - t) / 60:.1f} min -> {ses}")


def sexp(text):
    """Minimal S-expression reader (Specctra): lists, words, "strings"."""
    stack, cur = [], []
    for t in re.findall(r'\(|\)|"[^"]*"|[^\s()]+', text):
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done, cur = cur, stack.pop()
            cur.append(done)
        else:
            cur.append(t[1:-1] if t.startswith('"') else t)
    return cur[0]


def find(node, key):
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            yield c


def read_ses(ses, rules=None):
    """-> {net: {"wires": [(layer, width, [(x, y), …])], "vias": [(x, y)]}} in mil. With rules: the fixed wires of
    pour-only nets added back – Freerouting leaves a net that is not in the network out of the SES."""
    root = sexp(Path(ses).read_text())
    routes = next(find(root, "routes"))
    res = next(find(routes, "resolution"))
    scale = float(res[2])
    if res[1].lower() != "mil":
        raise SystemExit(f"unexpected SES unit {res[1]} (the DSN is written in mil)")
    out = {}
    for net in find(next(find(routes, "network_out")), "net"):
        entry = out.setdefault(net[1], {"wires": [], "vias": []})
        for wire in find(net, "wire"):
            path = next(find(wire, "path"))
            nums = [float(v) / scale for v in path[2:] if not isinstance(v, list)]
            entry["wires"].append((path[1], nums[0], list(zip(nums[1::2], nums[2::2]))))
        for via in find(net, "via"):
            entry["vias"].append((float(via[2]) / scale, float(via[3]) / scale))
    for net, layer, w, pts in fixed_wires(rules) if rules else []:
        if net in rules.pour_only:
            entry = out.setdefault(net, {"wires": [], "vias": []})
            if not any(lay == layer and len(p2) == len(pts) and max(map(math.dist, p2, pts), default=0) <= SNAP_MIL
                       for lay, _, p2 in entry["wires"]):
                entry["wires"].append((layer, w, pts))
    return out


def on_segment(p, a, b, tol=0.002):
    ax, ay, bx, by = *a, *b
    l2 = (bx - ax) ** 2 + (by - ay) ** 2
    if l2 == 0:
        return False
    t = ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / l2
    return 0 < t < 1 and math.dist(p, (ax + t * (bx - ax), ay + t * (by - ay))) < tol


def segments(rules, routes, data=None):
    """Track pieces per net, prepared so that EasyEDA takes them unchanged and sees them as connected:
    1. snap points closer than SNAP_MIL (vias are anchors) – EasyEDA drops tiny pieces, and it connects track to
       track only through ends that coincide to ~0.01 mil;
    2. split a piece where another one ends on its middle (T junction);
    3. merge straight continuations of the same width (EasyEDA does that itself anyway), not at vias and not inside
       pads of the same net. Pieces completely inside a via are dropped (EasyEDA discards them)."""
    pads = defaultdict(list)
    for p in (data or {}).get("pads", []):
        if p["net"]:
            for layer in pad_layers(p):
                pads[(p["net"], layer)].append(pad_outline(p))
    r_via = rules.via[1] / 2
    out = {}
    for net, r in routes.items():
        vias = [tuple(v) for v in r["vias"]]
        anchors = {layer: list(vias) for layer in ("TOP", "BOTTOM")}

        def snap(layer, pt):
            for a in anchors[layer]:
                if abs(a[0] - pt[0]) <= SNAP_MIL and abs(a[1] - pt[1]) <= SNAP_MIL and math.dist(a, pt) <= SNAP_MIL:
                    return a
            anchors[layer].append(pt)
            return pt
        segs = []
        for layer, w, pts in r["wires"]:
            for a, b in zip(pts, pts[1:]):
                a, b = snap(layer, a), snap(layer, b)
                if a != b:
                    segs.append((layer, w, a, b))
        ends = {(layer, p) for layer, _, a, b in segs for p in (a, b)} | {(lay, v) for v in vias for lay in ("TOP", "BOTTOM")}
        split = []
        for layer, w, a, b in segs:
            cut = sorted((p for (lay, p) in ends if lay == layer and p not in (a, b) and on_segment(p, a, b, tol=0.05)),
                         key=lambda p: math.dist(a, p))
            chain = [a] + [p for p in cut if math.dist(p, a) > SNAP_MIL and math.dist(p, b) > SNAP_MIL] + [b]
            split += [(layer, w, x, y) for x, y in zip(chain, chain[1:])]
        split = [s for s in split if not any(math.dist(s[2], v) <= r_via and math.dist(s[3], v) <= r_via for v in vias)]
        seen, uniq = set(), []
        for layer, w, a, b in split:
            key = (layer, min(a, b), max(a, b))
            if key not in seen:
                seen.add(key)
                uniq.append((layer, w, a, b))
        segs, merged = uniq, True
        while merged:
            merged = False
            at = defaultdict(list)
            for i, (layer, w, a, b) in enumerate(segs):
                at[(layer, a)].append(i)
                at[(layer, b)].append(i)
            for (layer, p), idx in at.items():
                if len(idx) != 2 or p in vias:
                    continue
                i, j = idx
                _, w1, a1, b1 = segs[i]
                _, w2, a2, b2 = segs[j]
                if w1 != w2:
                    continue
                o1, o2 = (a1 if b1 == p else b1), (a2 if b2 == p else b2)
                cross = (o1[0] - p[0]) * (o2[1] - p[1]) - (o1[1] - p[1]) * (o2[0] - p[0])
                dot = (o1[0] - p[0]) * (o2[0] - p[0]) + (o1[1] - p[1]) * (o2[1] - p[1])
                if abs(cross) > 1e-6 * max(1.0, math.dist(o1, p) * math.dist(o2, p)) or dot >= 0:
                    continue
                if any(g.intersects(Point(p)) for g in pads.get((net, layer), [])):
                    continue
                segs = [s for k, s in enumerate(segs) if k not in (i, j)] + [(layer, w1, o1, o2)]
                merged = True
                break
        out[net] = segs
    return out


# --- 4 check ------------------------------------------------------------------------------------------------------

def _pour_area(rules):
    """The pour outline of `pcb pour` in mil."""
    board = rules.board
    if not board.outline:
        raise SystemExit(f"board {board.name}: pour_only and pour_regions need the outline in the board file – the pour "
                         "outline is computed from it")
    return Polygon([tuple(v * MIL_PER_MM for v in board.eda_point(x, y)) for x, y in pcb.pour_outline(board)])


def _layer_copper(rules, data, routes, segs):
    """(net, copper) per layer: pads (those without a net too), tracks, vias."""
    copper = {"TOP": [], "BOTTOM": []}
    for p in data["pads"]:
        for layer in pad_layers(p):
            copper[layer].append((p["net"], pad_outline(p)))
    for net, ss in segs.items():
        for layer, w, a, b in ss:
            copper[layer].append((net, LineString([a, b]).buffer(w / 2)))
    for net, r in routes.items():
        for v in r["vias"]:
            for layer in copper:
                copper[layer].append((net, Point(v).buffer(rules.via[1] / 2)))
    return copper


def _computed(outline, copper, net, clearance, width, taken=None):
    """The pour of a net on one layer: the outline without foreign copper grown by clearance (and without `taken`, the
    area earlier nets fill, grown by clearance), opened by half of width."""
    area = outline.difference(unary_union([g for n, g in copper if n != net]).buffer(clearance))
    if taken is not None:
        area = area.difference(taken.buffer(clearance))
    if width > 0:
        area = area.buffer(-width / 2).buffer(width / 2)
    return [g for g in _parts(area) if g.geom_type == "Polygon"]


def pour_pieces(rules, data, routes, segs=None, regions=None):
    """The pours of the pour-only nets as EasyEDA fills them, computed offline: {(net, layer): [polygon, …]} in mil.
    Per net and layer: the pour outline of `pcb pour`, without the copper of other nets on that layer – pads (those
    without a net too), tracks, vias – grown by clearance_mm, opened by half of min_width_mm (EasyEDA does not fill
    narrower necks). The net's own copper is not taken away: the pour reaches its pads, tracks and vias. On a layer
    that several nets pour on, with pour_regions: the pieces the net claims there (pour_regions); without it, the other
    pours are not taken into account."""
    if not rules.pour_only:
        return {}
    outline = _pour_area(rules)
    segs = segments(rules, routes, data) if segs is None else segs
    copper = _layer_copper(rules, data, routes, segs)
    claims = {}
    if rules.regions:
        claims = (regions or _regions(rules, outline, copper))["claims"]
    out = {}
    for net, specs in sorted(rules.pour_only.items()):
        for layer, clearance, width in specs:
            out[(net, layer)] = claims[(net, layer)] if (net, layer) in claims \
                else _computed(outline, copper[layer], net, clearance, width)
    return out


def pour_regions(rules, data, routes, segs=None):
    """pour_regions: on every layer that several nets pour on, the nets claim their area in priority order. A net takes
    the pieces of its computed pour (pour_pieces) without what the nets before it fill, kept away from that by its
    clearance_mm, opened by its min_width_mm – those that hold its copper there (pads, tracks, vias; EasyEDA drops the
    others as islands) and have more than pour_min_piece_mm2 outside that copper grown by the clearance (EasyEDA leaves
    smaller ones empty). Its outlines: the pieces without their holes, grown by REGION_GROW_MM, simplified, within the
    pour outline and without the outlines of the nets before it. A piece of one net inside the outline of another needs
    an outline with a hole, which EasyEDA does not fill: a problem naming the place.
    -> {"claims": {(net, layer): [piece]}, "outlines": {(net, layer): [polygon]}, "problems": [text]}, in mil."""
    if not rules.regions:
        return {"claims": {}, "outlines": {}, "problems": []}
    segs = segments(rules, routes, data) if segs is None else segs
    return _regions(rules, _pour_area(rules), _layer_copper(rules, data, routes, segs))


def _regions(rules, outline, copper):
    claims, outlines, problems = {}, {}, []
    grow, tolerance = REGION_GROW_MM * MIL_PER_MM, REGION_SIMPLIFY_MM * MIL_PER_MM
    for layer, nets in rules.regions.items():
        taken = []
        for net, clearance, width in nets:
            own = unary_union([g for n, g in copper[layer] if n == net])
            near = own.buffer(clearance)
            pieces = _computed(outline, copper[layer], net, clearance, width, unary_union(taken) if taken else None)
            claims[(net, layer)] = [g for g in pieces if g.intersects(own) and g.difference(near).area > rules.min_piece]
            taken += claims[(net, layer)]
        done = Polygon()
        for net, _, _ in nets:
            mine = claims[(net, layer)]
            hull = unary_union([Polygon(g.exterior) for g in mine])
            for other, _, _ in nets:
                for g in claims[(other, layer)] if other != net else []:
                    inside = hull.intersection(g)
                    if inside.area > REGION_NESTED_MM2 * MIL_PER_MM ** 2:
                        c = inside.representative_point()
                        x, y = rules.board.plan_point(c.x / MIL_PER_MM, c.y / MIL_PER_MM)
                        problems.append(f"{other} {layer}: its pour at ({x:.1f}, {y:.1f}) mm lies inside the pour of "
                                        f"{net} – EasyEDA does not fill an outline with a hole; route so that {net} "
                                        f"does not enclose it, or leave {other} off {layer}")
            area = hull.buffer(grow).simplify(tolerance).intersection(outline).difference(done) if mine else Polygon()
            outlines[(net, layer)] = [Polygon(p.exterior) for p in _polygons(area) if any(p.intersects(g) for g in mine)]
            done = done.union(area)
    return {"claims": claims, "outlines": outlines, "problems": problems}


def region_outlines(cfg, board, rules=None):
    """pour_regions: the outlines `pcb pour` gives the nets on a shared layer, in EasyEDA mm, from the board file and
    the SES of the last routing -> {(net, layer): [[(x, y), …], …]}; None when no layer is shared. Stops when one is
    missing or a net's pour lies inside another's."""
    rules = rules or Rules(board)
    if not rules.regions:
        return None
    P = paths(cfg, board)
    missing = [str(f) for f in (P["board"], P["ses"]) if not f.exists()]
    if missing:
        raise SystemExit(f"board {board.name}: pour_regions – the outlines on {', '.join(rules.regions)} come from the "
                         f"routing, and {' and '.join(missing)} {'is' if len(missing) == 1 else 'are'} missing: "
                         "`edakit route all` pours at its end, or run `edakit route read` and `edakit route route` "
                         "first")
    r = pour_regions(rules, json.loads(P["board"].read_text()), read_ses(P["ses"], rules))
    if r["problems"]:
        raise SystemExit("\n".join(r["problems"]) + "\nnothing poured")
    for (net, layer), polys in r["outlines"].items():
        print(f"  pour region {net} {layer}: {len(polys)} outline{'s' * (len(polys) != 1)}", flush=True)
    return {k: [[(x / MIL_PER_MM, y / MIL_PER_MM) for x, y in list(p.exterior.coords)[:-1]] for p in polys]
            for k, polys in r["outlines"].items()}


def check(rules, data, routes):
    """Per net: are all pads connected through tracks and vias – and for a pour-only net its computed pour (pieces on
    two layers join through its through-hole pads and vias)? Net -> groups of pad indices, largest first."""
    segs = segments(rules, routes, data)
    pours = pour_pieces(rules, data, routes, segs)
    pads_by_net = defaultdict(list)
    for i, p in enumerate(data["pads"]):
        if p["net"]:
            pads_by_net[p["net"]].append(i)
    open_nets = {}
    for net, idx in sorted(pads_by_net.items()):
        if len(idx) < 2:
            continue
        parent = {}

        def root(k):
            while parent.setdefault(k, k) != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k
        r = routes.get(net, {"wires": [], "vias": []})
        nodes = [(("pad", i), set(pad_layers(data["pads"][i])), pad_outline(data["pads"][i])) for i in idx]
        nodes += [(("via", k), {"TOP", "BOTTOM"}, Point(v).buffer(rules.via[1] / 2)) for k, v in enumerate(r["vias"])]
        nodes += [(("seg", k), {layer}, LineString([a, b]).buffer(w / 2 * 0.2))
                  for k, (layer, w, a, b) in enumerate(segs.get(net, []))]
        for layer, _, _ in rules.pour_only.get(net, []):
            nodes += [(("pour", layer, k), {layer}, g) for k, g in enumerate(pours[(net, layer)])]
        for x in range(len(nodes)):
            for y in range(x + 1, len(nodes)):
                if nodes[x][1] & nodes[y][1] and nodes[x][2].intersects(nodes[y][2]):
                    parent[root(nodes[x][0])] = root(nodes[y][0])
        for n2, layer in planes(rules):  # everything of this net on a plane layer hangs on the plane
            if n2 == net:
                for k, layers, _ in nodes:
                    if layer in layers:
                        parent[root(k)] = root(("plane", layer))
        groups = defaultdict(list)
        for i in idx:
            groups[root(("pad", i))].append(i)
        if len(groups) > 1:
            open_nets[net] = sorted(groups.values(), key=len, reverse=True)
    return open_nets


def clearance_check(rules, data, routes):
    """Independent of Freerouting: clearance of every track and via to foreign copper >= rule, nothing in keep-outs."""
    from shapely.strtree import STRtree
    clear = rules.clear - 0.05  # rounding of SES coordinates
    outer, _ = board_area(data)
    _, strips = outside_strips(rules, outer)
    forbidden = unary_union(strips + circles(hole_keeps(rules, data) + tooling_keeps(rules)))
    wire_keep = {lay: unary_union([g for la, _, g in config_keepouts(rules, data) if la == lay])
                 for lay in ("TOP", "BOTTOM")}
    items = {"TOP": [], "BOTTOM": []}
    for p in data["pads"]:
        for layer in pad_layers(p):
            items[layer].append((p["net"] or f"nc:{p['id']}", pad_outline(p), f"pad {p['ref']}.{p['num']}", True))
    for net, ss in segments(rules, routes, data).items():
        for layer, w, a, b in ss:
            items[layer].append((net, LineString([a, b]).buffer(w / 2, quad_segs=4), f"track {net}", False))
    for net, r in routes.items():
        for v in r["vias"]:
            for layer in ("TOP", "BOTTOM"):
                items[layer].append((net, Point(v).buffer(rules.via[1] / 2, quad_segs=4), f"via {net}", None))
    found = []
    for layer, its in items.items():
        tree = STRtree([g for _, g, _, _ in its])
        for i, (net, g, text, kind) in enumerate(its):
            if kind is True:
                continue
            if g.intersects(forbidden):
                found.append(f"{layer}: {text} in a keep-out (edge/hole) at {g.centroid.x:.0f}, {g.centroid.y:.0f}")
            if kind is False and not wire_keep[layer].is_empty and g.intersects(wire_keep[layer]):
                found.append(f"{layer}: {text} in a wire keep-out at {g.centroid.x:.0f}, {g.centroid.y:.0f}")
            for j in tree.query(g, predicate="dwithin", distance=clear):
                n2, g2, t2, k2 = its[j]
                if n2 != net and (k2 is True or j > i):
                    found.append(f"{layer}: {text} – {t2}: {g.distance(g2):.2f} mil at {g.centroid.x:.0f}, "
                                 f"{g.centroid.y:.0f}")
    return found


def pad_accepts(graph, code="GEO.spacing", topic="clearance"):
    """The accepts of one code (and topic) in the graph (the inner object, as design.load_graph returns it): ({designator:
    reason}, {net: reason}) – GEO.spacing:clearance between pads of different parts, :paste the paste gap, :joint the
    hand-soldered joints, :holes the hole-to-hole spacing; GEO.ring the annular ring."""
    from .findings import accept_reason

    def of(items, key):
        return {x[key]: r for x in items if (r := accept_reason(x, code, topic))}
    return of(graph.get("components", []), "designator"), of(graph.get("nets", []), "name")


def graph_accepts(cfg, code="GEO.spacing", topic="clearance"):
    """pad_accepts of the project's graph; none for a board without its graph file."""
    from .design import load_graph
    return pad_accepts(load_graph(cfg.graph), code, topic) if cfg.graph.exists() else ({}, {})


def paste_rule(cfg):
    """GEO.spacing:paste from [release] assembly: (paste gap in mil, the assembled sides as copper layers, e.g.
    ("TOP",))."""
    assembly = cfg.release.get("assembly", {})
    sides = tuple(s.upper() for s in assembly.get("sides", ["top", "bottom"]))
    return assembly.get("paste_gap_mm", PASTE_GAP_MM) * MIL_PER_MM, sides


def pad_gaps(data, gap_mil, waivers=({}, {}), smd_on=None):
    """GEO.spacing: pads of different parts on different nets closer than gap_mil on a copper layer both are on (a
    through-hole pad is on both). A pad without a net counts as a net of its own; pads of one part belong to its
    footprint, and a pad without a part (a tooling hole) is no part. A pair is waived when one of its parts or nets
    has the code's accept in the graph (waivers: pad_accepts). smd_on (GEO.spacing): only SMD pads on these layers ("TOP",
    "BOTTOM") – the sides that get paste. -> [{"a", "b" (pad names), "nets", "layers", "mil", "waived" (reason or
    None)}], closest first."""
    from shapely.strtree import STRtree
    parts, nets = waivers
    pairs = {}
    for layer in ("TOP", "BOTTOM") if smd_on is None else [x for x in ("TOP", "BOTTOM") if x in smd_on]:
        its = [(p, pad_outline(p)) for p in data["pads"] if p["ref"] and layer in pad_layers(p)
               and (smd_on is None or p["layer"] in LAYERS)]
        tree = STRtree([g for _, g in its])
        for i, (p, g) in enumerate(its):
            for j in tree.query(g, predicate="dwithin", distance=gap_mil):
                q, h = its[j]
                if j <= i or q["ref"] == p["ref"] or (p["net"] and p["net"] == q["net"]):
                    continue
                gap = g.distance(h)
                if gap >= gap_mil - 0.01:
                    continue
                a, b = sorted((p, q), key=lambda x: (natural_key(x["ref"]), natural_key(x["num"])))
                name = (f"{a['ref']}.{a['num']}", f"{b['ref']}.{b['num']}")
                pair = pairs.setdefault(name, {"a": name[0], "b": name[1], "nets": (a["net"], b["net"]), "layers": [],
                                               "mil": gap, "waived": None})
                pair["layers"].append(layer)
                pair["mil"] = min(pair["mil"], gap)
                pair["waived"] = next((w[k] for w, k in ((parts, a["ref"]), (parts, b["ref"]), (nets, a["net"]),
                                                         (nets, b["net"])) if k and k in w), None)
    return sorted(pairs.values(), key=lambda x: (round(x["mil"], 3), natural_key(x["a"]), natural_key(x["b"])))


def gap_text(pair, gap_mil, what="the clearance"):
    """'R22.2 (N3) – R37.1 (N2): 0.090 mm apart on TOP, below the clearance 0.165 mm'"""
    (na, nb), mm = pair["nets"], 1 / MIL_PER_MM
    return (f"{pair['a']} ({na or 'no net'}) – {pair['b']} ({nb or 'no net'}): {pair['mil'] * mm:.3f} mm apart on "
            f"{' and '.join(pair['layers'])}, below {what} {gap_mil * mm:.3f} mm")


def board_as_read(cfg, board, components):
    """For stage L, whose pcb.json has no pad shapes: the board file of `route read` – if it still is the PCB. Every
    pad of the PCB's parts (components of pcb.json) must be there with its number, place (SNAP_MIL), layer and net,
    and no part may have other pads. -> (data, None) or (None, why not)."""
    f = paths(cfg, board)["board"]
    if not f.exists():
        return None, f"{cfg.relative(f)} missing (edakit route read)"
    data = json.loads(f.read_text())
    read = defaultdict(list)
    for p in data["pads"]:
        if p["ref"]:
            read[p["ref"]].append(p)
    pcb_pads = {c["designator"]: c["pads"] for c in components if c.get("designator")}
    off = []
    for ref in sorted(set(read) | set(pcb_pads), key=natural_key):
        have, saw = pcb_pads.get(ref, []), read.get(ref, [])
        if len(have) != len(saw):
            off.append(f"{ref} ({len(saw)} pads read, {len(have)} in the PCB)")
            continue
        off += [f"{ref}.{p['PadNumber']}" for p in have
                if not any(str(q["num"]) == str(p["PadNumber"]) and q["layer"] == p["Layer"]
                           and (q["net"] or "") == (p.get("Net") or "")
                           and math.dist((q["x"], q["y"]), (p["X"], p["Y"])) <= SNAP_MIL for q in saw)]
    if off:
        return None, (f"{cfg.relative(f)} is not the PCB any more – {', '.join(off[:8])}{' …' if len(off) > 8 else ''}"
                      " moved or changed since: edakit route read")
    return data, None


def report_pads(rules, data, waivers):
    """The placement's part of the check, printed: pads of different parts closer than the clearance (GEO.spacing), waived
    ones with their reason -> those not waived."""
    gaps = pad_gaps(data, rules.clear, waivers)
    tight = [g for g in gaps if not g["waived"]]
    say(f"pads of different parts: {len(tight)} pairs closer than the clearance {rules.clear} mil"
        + (f", {len(gaps) - len(tight)} waived (GEO.spacing)" if len(gaps) > len(tight) else ""))
    for g in gaps[:20]:
        print(f"    {gap_text(g, rules.clear)}" + (f" – waived: {g['waived']}" if g["waived"] else ""), flush=True)
    return tight


def report_paste(cfg, data):
    """GEO.spacing, printed: SMD pads of different parts on different nets closer than the paste gap on an assembled side,
    waived ones with their reason -> those not waived."""
    gap, sides = paste_rule(cfg)
    if not sides:
        return []
    gaps = pad_gaps(data, gap, graph_accepts(cfg, "GEO.spacing", "paste"), sides)
    tight = [g for g in gaps if not g["waived"]]
    say(f"SMD pads of different parts on {' and '.join(sides)}: {len(tight)} pairs closer than the paste gap "
        f"{gap / MIL_PER_MM:g} mm" + (f", {len(gaps) - len(tight)} waived (GEO.spacing)" if len(gaps) > len(tight) else ""))
    for g in gaps[:20]:
        print(f"    {gap_text(g, gap, 'the paste gap')}" + (f" – waived: {g['waived']}" if g["waived"] else ""),
              flush=True)
    return tight


def looks_rows(board, length_m, vias):
    """[looks] of the board file: the visible side's track length and the board's vias (a via shows on both sides)
    -> (information line, [(warning, actual, limit)] above max_track_m / max_vias), or None without [looks].
    length_m: {"TOP": m, "BOTTOM": m}. Used by `route check` and stage L alike."""
    lk = board.looks
    if not lk:
        return None
    side = lk["visible"].upper()
    track = f"{length_m[side]:.2f} m of track"
    warns = []
    if lk.get("max_track_m") is not None and length_m[side] > lk["max_track_m"]:
        warns.append((f"{side} (visible): {track}, limit {lk['max_track_m']:g} m", track,
                      f"<= {lk['max_track_m']:g} m"))
    if lk.get("max_vias") is not None and vias > lk["max_vias"]:
        warns.append((f"{side} (visible): {vias} vias, limit {lk['max_vias']}", f"{vias} vias",
                      f"<= {lk['max_vias']} vias"))
    return f"{side} (visible): {track}, {vias} via{'s' * (vias != 1)}", warns


def report_looks(rules, data, routes):
    """[looks], printed: the track length per side and the vias of the SES, the visible side's row and its warnings.
    Nothing without [looks]; no exit code changes."""
    if not rules.board.looks:
        return
    length = {"TOP": 0.0, "BOTTOM": 0.0}
    for ss in segments(rules, routes, data).values():
        for layer, _, a, b in ss:
            length[layer] += math.dist(a, b) / MIL_PER_MM / 1000
    vias = sum(len(r["vias"]) for r in routes.values())
    say(f"tracks: TOP {length['TOP']:.2f} m, BOTTOM {length['BOTTOM']:.2f} m; vias {vias}")
    row, warns = looks_rows(rules.board, length, vias)
    say(row)
    for w, _, _ in warns:
        print(f"    {w} – warning", flush=True)


def report_joints(cfg, board, rules, data, routes=None):
    """GEO.spacing, printed: with routes None the pads of other nets at the hand-soldered joints (the placement's part: no
    new routing moves them), else the vias of the SES. Waived ones with their reason -> those not waived."""
    if not rules.joint_keep:
        return []
    vias = [] if routes is None else [(net, tuple(v), rules.via[1]) for net, r in routes.items() for v in r["vias"]]
    gaps = [g for g in joint_gaps(data, rules.joint_keep, rules.hand, vias, graph_accepts(cfg, "GEO.spacing", "joint"))
            if (g["kind"] == "pad") == (routes is None)]
    near = [g for g in gaps if not g["waived"]]
    what = "pads" if routes is None else "vias"
    n = len(hand_joints(data, rules.hand))
    say(f"hand-soldered joints (GEO.spacing): {n} on their solder side, {len(near)} {what} of other nets closer than "
        f"hand_solder_keep_mm {rules.joint_keep / MIL_PER_MM:g}"
        + (f", {len(gaps) - len(near)} waived" if len(gaps) > len(near) else ""))
    for g in gaps[:20]:
        print(f"    {joint_text(g, rules.joint_keep, board)}" + (f" – waived: {g['waived']}" if g["waived"] else ""),
              flush=True)
    return near


def report_check(rules, data, open_nets, routes):
    n_seg = sum(len(s) for s in segments(rules, routes, data).values())
    n_via = sum(len(r["vias"]) for r in routes.values())
    say(f"check: {len(routes)} nets routed, {n_seg} track pieces, {n_via} vias; open: {len(open_nets)}")
    name = lambda i: f"{data['pads'][i]['ref']}.{data['pads'][i]['num']}"  # noqa: E731
    for net, groups in open_nets.items():
        print(f"    {net}{' (pour-only)' if net in rules.pour_only else ''}: {len(groups)} groups – " + " | ".join(
            ", ".join(name(i) for i in g[:6]) + (" …" if len(g) > 6 else "") for g in groups), flush=True)
    for net, specs in sorted(rules.pour_only.items()):
        for layer, _, _ in specs:
            others = sorted({p["net"] for p in rules.board.pours
                             if p["net"] != net and layer in p.get("layers", ["TOP", "BOTTOM"])})
            if others and layer not in rules.regions:
                print(f"    ! {net} {layer}: the pour of {', '.join(others)} shares the layer – the computed pour of "
                      f"{net} does not leave it out, and EasyEDA fills overlapping pours by priority (pour_regions "
                      "gives each net its own area)", flush=True)


def report_regions(rules, data, routes):
    """pour_regions: the outlines per shared layer, and what EasyEDA cannot fill -> those problems."""
    if not rules.regions:
        return []
    r = pour_regions(rules, data, routes)
    for layer, nets in rules.regions.items():
        say(f"pour regions {layer}: " + ", ".join(f"{net} {len(r['outlines'][(net, layer)])}" for net, _, _ in nets)
            + " outlines")
    for line in r["problems"]:
        print(f"    {line}", flush=True)
    return r["problems"]


def render(rules, data, routes, png, open_nets=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MPoly
    outer, holes = board_area(data)
    segs = segments(rules, routes, data)
    regions = pour_regions(rules, data, routes, segs)
    pours = pour_pieces(rules, data, routes, segs, regions)
    pours.update({k: v for k, v in regions["claims"].items() if k not in pours})  # the other nets on a shared layer
    fig, axes = plt.subplots(1, 2, figsize=(14, 8))
    for ax, side, color in ((axes[0], "TOP", "#d62728"), (axes[1], "BOTTOM", "#1f77b4")):
        ax.add_patch(MPoly(list(outer.exterior.coords), closed=True, fc="#0b3d1a", ec="#aaaaaa", lw=1))
        for h in holes:
            ax.add_patch(MPoly(list(h.exterior.coords), closed=True, fc="white", ec="#aaaaaa"))
        for g in (g for (_, layer), gs in pours.items() if layer == side for g in gs):  # pours of pour-only nets
            ax.add_patch(MPoly(list(g.exterior.coords), closed=True, fc=color, ec="none", alpha=0.25))
            for ring in g.interiors:
                ax.add_patch(MPoly(list(ring.coords), closed=True, fc="#0b3d1a", ec="none"))
        for k, ((net, layer), gs) in enumerate(regions["outlines"].items()):  # pour_regions: what `pcb pour` creates
            edge = ("#ff7f0e", "#2ca02c", "#17becf", "#e377c2", "#bcbd22")[k % 5]
            for g in gs if layer == side else []:
                ax.add_patch(MPoly(list(g.exterior.coords), closed=True, fc="none", ec=edge, lw=1.0, ls="--"))
                c = g.representative_point()
                ax.annotate(net, (c.x, c.y), color=edge, fontsize=7, ha="center")
        for p in data["pads"]:
            if side in pad_layers(p):
                ax.add_patch(MPoly(list(pad_outline(p).exterior.coords), closed=True, fc="#c8a040", ec="none", alpha=0.9))
        for ss in segs.values():
            for layer, w, a, b in ss:
                if layer == side:
                    ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=max(0.6, w / 12), solid_capstyle="round")
                else:
                    ax.plot([a[0], b[0]], [a[1], b[1]], color="#ffffff", lw=0.4, alpha=0.15)
        for r in routes.values():
            for x, y in r["vias"]:
                ax.add_patch(plt.Circle((x, y), rules.via[1] / 2, fc="#dddddd", ec="black", lw=0.3))
        for net, groups in (open_nets or {}).items():  # open connections: airline to the nearest group
            main = [data["pads"][i] for i in groups[0]]
            for g in groups[1:]:
                a, b = min(((m, data["pads"][i]) for m in main for i in g),
                           key=lambda ab: math.dist((ab[0]["x"], ab[0]["y"]), (ab[1]["x"], ab[1]["y"])))
                ax.plot([a["x"], b["x"]], [a["y"], b["y"]], color="#ffe000", lw=1.6, ls="--")
                ax.annotate(net, ((a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2), color="#ffe000", fontsize=6)
        length = sum(math.dist(a, b) for ss in segs.values() for (lay, _, a, b) in ss if lay == side) * 0.0254
        ax.set_title(f"{side} (seen from top): {length / 1000:.2f} m of track")
        ax.set_aspect("equal")
        ax.autoscale_view()
        ax.axis("off")
    fig.suptitle(f"{data['pcb']}: {sum(len(r['vias']) for r in routes.values())} vias, {len(open_nets or {})} nets open "
                 "(yellow, dashed)")
    fig.tight_layout()
    fig.savefig(png, dpi=110, facecolor="white")
    plt.close(fig)
    say(f"preview -> {png}")


# --- diagnose: why a connection stays open --------------------------------------------------------------------------

DIAG_EPS_MIL = 0.5          # an obstacle this close to a free area bounds it
DIAG_STEP_MIL = 4.0         # the raster of the shortest way: no finer than 0.1 mm …
DIAG_CELLS = 200_000        # … and at most this many cells per layer
DIAG_MARGIN_MIL = 200.0     # first a window this much around the two pads (5 mm), then the whole board
DIAG_VIA_COST_MIL = 40.0    # a via counts as 1 mm of way
RUDY_CELL_MIL = MIL_PER_MM  # congestion on a 1 mm grid
RUDY_SMOOTH_CELLS = 3       # demand and capacity averaged over 3 x 3 cells: single cells at the edge are outliers


def net_way(rules, net):
    """How a connection of `net` is made: (track width, clearance, layers, vias) – a pour-only net by its pour
    (min_width_mm and clearance_mm, on its pour layers, no vias), any other net by its class on both layers."""
    if net in rules.pour_only:
        specs = rules.pour_only[net]
        return max(w for _, _, w in specs), max(c for _, c, _ in specs), sorted({lay for lay, _, _ in specs}), False
    return rules.net_class(net)[1], rules.clear, ["TOP", "BOTTOM"], True


def plan_mm(rules, x, y):
    """EasyEDA mil -> plan mm, rounded to 0.1 mm."""
    px, py = rules.board.plan_point(x / MIL_PER_MM, y / MIL_PER_MM)
    return round(px, 1), round(py, 1)


def walls(rules, data):
    """What walls a track in on the empty board: (the area inside the edge clearance, {layer: [(name, area)]} for
    tracks, [(name, area)] for vias – a wire keep-out lets a via through). Names: "hole at (x, y) mm", "tooling hole
    at (x, y) mm" (plan mm), "keep-out K<i>" (the i-th [[routing.keepouts]] of the board file, counted from 0)."""
    outer, _ = board_area(data)
    inner = outer.buffer(-rules.edge_um / 25.4, join_style="round", quad_segs=EDGE_ARC_SEGMENTS)
    holes = [(f"{what} at ({plan_mm(rules, x, y)[0]:g}, {plan_mm(rules, x, y)[1]:g}) mm", Point(x, y).buffer(r))
             for what, keeps in (("hole", hole_keeps(rules, data)), ("tooling hole", tooling_keeps(rules)))
             for x, y, r in keeps]
    keeps = keepout_areas(rules, data)
    track = {lay: holes + [(f"keep-out K{i}", a) for i, layers, _, a in keeps if lay in layers]
             for lay in ("TOP", "BOTTOM")}
    via = holes + [(f"keep-out K{i}", a) for i, _, what, a in keeps if what != "wire"]
    return inner, track, via


def free_space(rules, data, net, walls_, copper=None):
    """Where the middle of a track of `net` may run on each of its layers, and where a via of it may sit: inside the
    edge clearance, off holes and keep-outs, the clearance away from foreign pads – and from `copper` ({layer:
    [area]}, the routed copper of other nets) –, shrunk by half the track width (by the via radius for vias).
    -> ({layer: area}, via area or None) in mil."""
    w, c, layers, vias = net_way(rules, net)
    inner, track, via = walls_
    grown = {}
    for lay in ("TOP", "BOTTOM"):
        foreign = [pad_outline(p) for p in data["pads"] if p["net"] != net and lay in pad_layers(p)]
        foreign += list((copper or {}).get(lay, []))
        grown[lay] = unary_union(foreign).buffer(c) if foreign else Polygon()
    areas = {lay: inner.difference(unary_union([g for _, g in track[lay]] + [grown[lay]])).buffer(-w / 2)
             for lay in layers}
    if not vias:
        return areas, None
    blocked = unary_union([g for _, g in via] + [grown["TOP"], grown["BOTTOM"]])
    return areas, inner.difference(blocked).buffer(-rules.via[1] / 2)


def regions_of(data, areas, vias_area, groups):
    """The free areas split into regions, joined where a via fits in both, through a pad of the net that touches
    several (a through-hole pad on both layers), and within a group of pads the net's own copper already joins.
    -> (root, {key: region}, {pad index: [keys of the regions it touches]})."""
    from shapely import prepare
    from shapely.strtree import STRtree
    regions = {(lay, k): g for lay, a in areas.items() for k, g in enumerate(_polygons(a))}
    for g in regions.values():
        prepare(g)
    parent = {}

    def root(k):
        while parent.setdefault(k, k) != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def join(keys):
        for k in keys[1:]:
            parent[root(k)] = root(keys[0])
    pad_keys = {}
    for i in (i for g in groups for i in g):
        p = data["pads"][i]
        shape = pad_outline(p)
        pad_keys[i] = [k for k, g in regions.items() if k[0] in pad_layers(p) and g.intersects(shape)]
        join(pad_keys[i])
    for g in groups:
        join([k for i in g for k in pad_keys[i]])
    if vias_area is not None and not vias_area.is_empty:
        bottoms = [k for k in regions if k[0] == "BOTTOM"]
        tree = STRtree([regions[k] for k in bottoms])
        for t in (k for k in regions if k[0] == "TOP"):
            spots = regions[t].intersection(vias_area)
            if not spots.is_empty:
                for j in tree.query(spots, predicate="intersects"):
                    join([t, bottoms[j]])
    return root, regions, pad_keys


def joined(root, pad_keys, g1, g2):
    r1 = {root(k) for i in g1 for k in pad_keys[i]}
    return any(root(k) in r1 for i in g2 for k in pad_keys[i])


def reached(root, regions, pad_keys, group):
    """The regions the pads of `group` reach -> {layer: [region]}."""
    roots = {root(k) for i in group for k in pad_keys[i]}
    out = defaultdict(list)
    for k, g in regions.items():
        if root(k) in roots:
            out[k[0]].append(g)
    return out


def enclosure(rules, data, net, walls_, regions, root, pad_keys, group):
    """What walls the pads of `group` in on the empty board: the edge, holes, keep-outs and foreign pads along the outer
    rings of the regions they reach – or, where they reach none, on and around the pads themselves.
    -> ["keep-out K0 (TOP, BOTTOM)", "pads U1.2, U1.4 (TOP)", …]"""
    w, c, layers, _ = net_way(rules, net)
    inner, track, _ = walls_
    mine = reached(root, regions, pad_keys, group)
    found = {}
    for lay in layers:
        if mine.get(lay):
            near = unary_union([g.exterior for g in mine[lay]])
        else:
            shapes = [pad_outline(data["pads"][i]) for i in group if lay in pad_layers(data["pads"][i])]
            if not shapes:
                continue
            near = unary_union(shapes)
        hits = [name for name, g in track[lay] if near.distance(g) <= w / 2 + DIAG_EPS_MIL]
        if near.distance(inner.boundary) <= w / 2 + DIAG_EPS_MIL or not inner.contains(near):
            hits.insert(0, "the edge")
        pads = sorted((f"{p['ref'] or 'FREE'}.{p['num']}" for p in data["pads"] if p["net"] != net
                       and lay in pad_layers(p) and near.distance(pad_outline(p)) <= c + w / 2 + DIAG_EPS_MIL),
                      key=natural_key)
        if pads:
            hits.append("pads " + ", ".join(pads[:6]) + (" …" if len(pads) > 6 else ""))
        for name in hits:
            found.setdefault(name, []).append(lay)
    return [f"{name} ({', '.join(lays)})" for name, lays in found.items()]


def shortest_way(rules, data, areas, vias_area, starts, ends, window):
    """The shortest way from a pad of `starts` to one of `ends` (pad indices) over the free areas, on a raster of the
    window (x0, y0, x1, y1 in mil): 8 neighbours on a layer, a via where one fits. -> [(layer, x, y)] in mil or None."""
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    from shapely import contains_xy
    x0, y0, x1, y1 = window
    step = max(DIAG_STEP_MIL, math.sqrt((x1 - x0) * (y1 - y0) / DIAG_CELLS))
    nx, ny = int((x1 - x0) / step) + 2, int((y1 - y0) / step) + 2
    X, Y = np.meshgrid(x0 + np.arange(nx) * step, y0 + np.arange(ny) * step)
    layers = list(areas)
    free = np.stack([contains_xy(areas[lay], X, Y) for lay in layers])
    idx = np.arange(len(layers) * nx * ny).reshape(len(layers), ny, nx)
    rows, cols, cost = [], [], []
    for li in range(len(layers)):
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            a = (slice(0, ny - dy), slice(max(0, -dx), nx - max(0, dx)))
            b = (slice(dy, ny), slice(max(0, dx), nx - max(0, -dx)))
            both = free[li][a] & free[li][b]
            rows.append(idx[li][a][both])
            cols.append(idx[li][b][both])
            cost.append(np.full(int(both.sum()), step * math.hypot(dx, dy)))
    if vias_area is not None and len(layers) == 2:
        v = contains_xy(vias_area, X, Y) & free[0] & free[1]
        rows.append(idx[0][v])
        cols.append(idx[1][v])
        cost.append(np.full(int(v.sum()), DIAG_VIA_COST_MIL))
    n = idx.size
    graph = coo_matrix((np.concatenate(cost), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()

    def cells(pads):
        out = []
        for i in pads:
            p = data["pads"][i]
            inside = contains_xy(pad_outline(p).buffer(step * 0.75), X, Y)
            out += [idx[li][inside & free[li]] for li, lay in enumerate(layers) if lay in pad_layers(p)]
        return np.unique(np.concatenate(out)) if out else np.array([], int)
    src, dst = cells(starts), cells(ends)
    if not len(src) or not len(dst):
        return None
    dist, pred, _ = dijkstra(graph, directed=False, indices=src, return_predecessors=True, min_only=True)
    end = dst[np.argmin(dist[dst])]
    if not np.isfinite(dist[end]):
        return None
    way, k = [], int(end)
    while k >= 0:
        li, rest = divmod(k, nx * ny)
        j, i = divmod(rest, nx)
        way.append((layers[li], float(X[j, i]), float(Y[j, i])))
        k = int(pred[k])
    return way[::-1]


def way_runs(way):
    """The way as runs per layer and the vias between them -> ([(layer, [(x, y), …])], [(x, y)])."""
    runs, vias = [], []
    for lay, x, y in way:
        if runs and runs[-1][0] == lay:
            runs[-1][1].append((x, y))
        else:
            if runs:
                vias.append((x, y))
            runs.append((lay, [(x, y)]))
    return runs, vias


def way_length(way):
    return sum(math.dist(a[1:], b[1:]) for a, b in zip(way, way[1:]))


def crossing(way, others, reach):
    """The nets whose routed copper ({net: {layer: area}}) comes closer than `reach` to the way."""
    runs, vias = way_runs(way)
    lines = {lay: unary_union([LineString(pts) if len(pts) > 1 else Point(pts[0]) for la, pts in runs if la == lay]
                              + [Point(v) for v in vias]) for lay in ("TOP", "BOTTOM")}
    return sorted((n for n, per in others.items()
                   if any(not lines[lay].is_empty and lines[lay].distance(g) < reach for lay, g in per.items())),
                  key=natural_key)


def fence(regions, others, reach):
    """The nets whose routed copper lies along the outer rings of the regions -> sorted names."""
    rings = {lay: unary_union([g.exterior for g in gs]) for lay, gs in regions.items() if gs}
    return sorted((n for n, per in others.items()
                   if any(lay in rings and rings[lay].distance(g) <= reach for lay, g in per.items())), key=natural_key)


def congestion(rules, data, walls_=None):
    """RUDY: each routed net's wire demand – half the perimeter of its pads' bounding box over its area – spread on a
    1 mm grid, against the capacity of each cell – the layers tracks may use there, times cell / (signal width +
    clearance) –, both averaged over RUDY_SMOOTH_CELLS x RUDY_SMOOTH_CELLS cells. -> {"util": [ny, nx] (nan off the
    board), "x0", "y0", "cell" (mil), "max", "at" (plan mm), "at_mil"}"""
    import numpy as np
    from scipy.ndimage import uniform_filter
    from shapely import contains_xy
    inner, track, _ = walls_ or walls(rules, data)
    outer, _ = board_area(data)
    bx0, by0, bx1, by1 = outer.bounds
    cell = RUDY_CELL_MIL
    nx, ny = max(1, math.ceil((bx1 - bx0) / cell)), max(1, math.ceil((by1 - by0) / cell))
    gx, gy = bx0 + np.arange(nx + 1) * cell, by0 + np.arange(ny + 1) * cell
    pins = defaultdict(list)
    for p in data["pads"]:
        if p["net"] and p["net"] not in rules.pour_only:
            pins[p["net"]].append((p["x"], p["y"]))
    demand = np.zeros((ny, nx))
    for pts in pins.values():
        if len(pts) < 2:
            continue
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        w, h = max(max(xs) - min(xs), cell), max(max(ys) - min(ys), cell)
        cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        ovx = np.clip(np.minimum(gx[1:], cx + w / 2) - np.maximum(gx[:-1], cx - w / 2), 0, None)
        ovy = np.clip(np.minimum(gy[1:], cy + h / 2) - np.maximum(gy[:-1], cy - h / 2), 0, None)
        demand += (w + h) / (w * h) * np.outer(ovy, ovx) / cell          # tracks across each cell
    k = 4                                                                 # samples per cell side for the capacity
    SX, SY = np.meshgrid(bx0 + (np.arange(nx * k) + 0.5) * cell / k, by0 + (np.arange(ny * k) + 0.5) * cell / k)
    capacity = np.zeros((ny, nx))
    for lay in ("TOP", "BOTTOM"):
        allowed = inner.difference(unary_union([g for _, g in track[lay]]))
        share = contains_xy(allowed, SX, SY).reshape(ny, k, nx, k).mean(axis=(1, 3))
        capacity += share * cell / (rules.signal + rules.clear)
    d, c = (uniform_filter(a, RUDY_SMOOTH_CELLS, mode="constant") for a in (demand, capacity))
    util = np.full((ny, nx), np.nan)
    ok = (capacity > 0) & (c > 1e-9)
    util[ok] = d[ok] / c[ok]
    out = {"util": util, "x0": bx0, "y0": by0, "cell": cell, "max": 0.0, "at": None, "at_mil": None}
    if ok.any():
        j, i = np.unravel_index(np.nanargmax(util), util.shape)
        at = (bx0 + (i + 0.5) * cell, by0 + (j + 0.5) * cell)
        out.update({"max": float(util[j, i]), "at": plan_mm(rules, *at), "at_mil": at})
    return out


def utilisation_at(cong, x, y):
    """The congestion at a point (mil); 0 off the grid or off the board."""
    i, j = int((x - cong["x0"]) // cong["cell"]), int((y - cong["y0"]) // cong["cell"])
    ny, nx = cong["util"].shape
    if not (0 <= i < nx and 0 <= j < ny) or math.isnan(cong["util"][j, i]):
        return 0.0
    return float(cong["util"][j, i])


def routed_copper(rules, segs, routes):
    """{net: {layer: area}} of the routed tracks and vias."""
    parts = defaultdict(lambda: defaultdict(list))
    for net, ss in segs.items():
        for layer, w, a, b in ss:
            parts[net][layer].append(LineString([a, b]).buffer(w / 2))
    for net, r in routes.items():
        for v in r["vias"]:
            for layer in ("TOP", "BOTTOM"):
                parts[net][layer].append(Point(v).buffer(rules.via[1] / 2))
    return {net: {lay: unary_union(gs) for lay, gs in per.items()} for net, per in parts.items()}


def diagnose(rules, data, routes, only=None, out_dir=None):
    """Why each connection the SES leaves open is open. A connection is the closest pad pair between the largest group
    of an open net and each other group (the yellow airline of the routing preview); the net is routed with its class
    width and the clearance (a pour-only net with its pour's), as Freerouting routes it.
    - unreachable: on the empty board – inside the edge clearance, off holes, tooling holes and keep-outs (a wire
      keep-out lets vias through), the clearance from foreign pads – no way joins the two groups; named: what walls in
      the side that reaches less (enclosure)
    - blocked: a way on the empty board, none between the routed copper of the other nets; named: the nets whose
      copper lies on the shortest way of the empty board (a raster, vias included) and the highest congestion along it
    - free: a way is left – Freerouting did not find it
    -> {"board", "open": [{net, a, b, verdict, line, …}], "congestion": {max, at}}; with out_dir one PNG per connection,
    congestion.png and diagnose.json there."""
    open_nets = {n: g for n, g in check(rules, data, routes).items() if only is None or n == only}
    segs = segments(rules, routes, data)
    walls_ = walls(rules, data)
    cong = congestion(rules, data, walls_)
    copper = routed_copper(rules, segs, routes)
    outer, _ = board_area(data)
    name = lambda i: f"{data['pads'][i]['ref'] or 'FREE'}.{data['pads'][i]['num']}"  # noqa: E731
    gaps = []
    for net, groups in open_nets.items():
        w, c, _, _ = net_way(rules, net)
        empty = free_space(rules, data, net, walls_)
        e_root, e_regions, e_keys = regions_of(data, *empty, groups)
        others = {n: per for n, per in copper.items() if n != net}
        routed = free_space(rules, data, net, walls_, {lay: [per[lay] for per in others.values() if lay in per]
                                                       for lay in ("TOP", "BOTTOM")})
        r_root, r_regions, r_keys = regions_of(data, *routed, groups)
        for g in groups[1:]:
            a, b = min(((i, j) for i in groups[0] for j in g), key=lambda ij: math.dist(
                (data["pads"][ij[0]]["x"], data["pads"][ij[0]]["y"]), (data["pads"][ij[1]]["x"], data["pads"][ij[1]]["y"])))
            gap = {"net": net, "a": name(a), "b": name(b)}
            head = f"{net} {name(a)} – {name(b)}"
            way = None
            if not joined(e_root, e_keys, groups[0], g):
                def area(group):
                    return sum(r.area for gs in reached(e_root, e_regions, e_keys, group).values() for r in gs)
                side, pad = (g, b) if area(g) <= area(groups[0]) else (groups[0], a)
                by = enclosure(rules, data, net, walls_, e_regions, e_root, e_keys, side)
                gap.update(verdict="unreachable", enclosed=name(pad), enclosed_by=by)
                gap["line"] = f"{head}: unreachable – {name(pad)} " + (
                    f"enclosed by {', '.join(by)}" if by else f"has no way {w:g} mil wide")
            elif not joined(r_root, r_keys, groups[0], g):
                pa, pb = data["pads"][a], data["pads"][b]
                margin = max(DIAG_MARGIN_MIL, math.dist((pa["x"], pa["y"]), (pb["x"], pb["y"])) / 2)
                bx0, by0, bx1, by1 = outer.bounds
                window = (max(bx0, min(pa["x"], pb["x"]) - margin), max(by0, min(pa["y"], pb["y"]) - margin),
                          min(bx1, max(pa["x"], pb["x"]) + margin), min(by1, max(pa["y"], pb["y"]) + margin))
                way = shortest_way(rules, data, *empty, g, groups[0], window) or \
                    shortest_way(rules, data, *empty, g, groups[0], outer.bounds)
                reach = c + w / 2 - DIAG_EPS_MIL
                blockers = crossing(way, others, reach) if way else []
                if not blockers:   # no way on the raster: the nets along the walls of the smaller side
                    small = min((groups[0], g), key=lambda grp: sum(
                        r.area for gs in reached(r_root, r_regions, r_keys, grp).values() for r in gs))
                    blockers = fence(reached(r_root, r_regions, r_keys, small), others, c + w / 2 + DIAG_EPS_MIL)
                points = [(x, y) for _, x, y in way] if way else [(pa["x"] + (pb["x"] - pa["x"]) * t / 20,
                                                                  pa["y"] + (pb["y"] - pa["y"]) * t / 20)
                                                                 for t in range(21)]
                u, at = max(((utilisation_at(cong, x, y), (x, y)) for x, y in points), key=lambda ua: ua[0])
                gap.update(verdict="blocked", blocked_by=blockers, utilisation=round(u, 2), at=plan_mm(rules, *at))
                if way:
                    gap["way_mm"] = round(way_length(way) / MIL_PER_MM, 1)
                gap["line"] = (f"{head}: blocked by {', '.join(blockers) or 'the routed copper'} – utilisation {u:.2f} "
                               f"at ({gap['at'][0]:.0f}, {gap['at'][1]:.0f}) mm")
            else:
                gap.update(verdict="free")
                gap["line"] = (f"{head}: open, but a free way is left – Freerouting did not find it (more passes, "
                               "another order: route all's attempts)")
            gaps.append(gap)
            if out_dir:
                gap["png"] = f"{len(gaps):02d}_{re.sub(r'[^A-Za-z0-9_+-]', '_', net)}.png"
                render_gap(rules, data, segs, routes, gap, net, empty[0], way, walls_, out_dir / gap["png"])
    result = {"board": rules.board.name, "open": gaps,
              "congestion": {"max": round(cong["max"], 2), "at": cong["at"], "png": "congestion.png"}}
    if out_dir:
        render_congestion(rules, data, cong, out_dir / "congestion.png")
        (out_dir / "diagnose.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    return result


def _patch(ax, geom, **kw):
    """A shapely area (with holes) as one matplotlib patch per polygon."""
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath
    for g in _polygons(geom):
        verts, codes = [], []
        for ring in (g.exterior, *g.interiors):
            pts = list(ring.coords)
            verts += pts
            codes += [MPath.MOVETO] + [MPath.LINETO] * (len(pts) - 2) + [MPath.CLOSEPOLY]
        ax.add_patch(PathPatch(MPath(verts, codes), **kw))


def render_gap(rules, data, segs, routes, gap, net, areas, way, walls_, png):
    """One open connection, cropped: where the net's track may run on the empty board (green), keep-outs and holes
    (red), pads (the two of the connection outlined), the routed copper (the blocking nets orange, the net's own cyan,
    the others grey), the shortest way of the empty board (yellow)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection, PolyCollection
    outer, holes = board_area(data)
    _, track, _ = walls_
    ends = [p for p in data["pads"] if f"{p['ref'] or 'FREE'}.{p['num']}" in (gap["a"], gap["b"])]
    xs = [p["x"] for p in ends] + [x for _, x, _ in way or []]
    ys = [p["y"] for p in ends] + [y for _, _, y in way or []]
    m = 3 * MIL_PER_MM
    x0, y0, x1, y1 = min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m
    window = box(x0, y0, x1, y1)
    blockers = set(gap.get("blocked_by", []))
    runs, vias = way_runs(way) if way else ([], [])
    height = min(8.0, max(3.0, 6.0 * (y1 - y0) / (x1 - x0) + 1.2))
    fig, axes = plt.subplots(1, 2, figsize=(12, height))
    for ax, lay in zip(axes, ("TOP", "BOTTOM")):
        ax.set_facecolor("#1a1a1a")
        _patch(ax, outer.intersection(window), fc="#0b3d1a", ec="#aaaaaa", lw=1)
        for h in holes:
            _patch(ax, h.intersection(window), fc="white", ec="#aaaaaa")
        if lay in areas:
            _patch(ax, areas[lay].intersection(window), fc="#3fae5a", ec="none", alpha=0.35)
        for _, g in track[lay]:
            _patch(ax, g.intersection(window), fc="#c0392b", ec="#ff6b5b", alpha=0.4, hatch="//")
        pads = [(pad_outline(p), p in ends) for p in data["pads"] if lay in pad_layers(p)]
        pads = [(g, mark) for g, mark in pads if g.intersects(window)]
        if pads:
            ax.add_collection(PolyCollection([list(g.exterior.coords) for g, _ in pads], facecolors="#c8a040",
                                             edgecolors=["white" if mark else "none" for _, mark in pads],
                                             linewidths=[1.5 if mark else 0 for _, mark in pads]))
        lines = [((a, b), "#ff8c00" if n in blockers else "#00e5ff" if n == net else "#888888", max(0.8, w / 8))
                 for n, ss in segs.items() for layer, w, a, b in ss
                 if layer == lay and LineString([a, b]).intersects(window)]
        if lines:
            ax.add_collection(LineCollection([seg for seg, _, _ in lines], colors=[c for _, c, _ in lines],
                                             linewidths=[w for _, _, w in lines], capstyle="round"))
        for n, r in routes.items():
            for x, y in r["vias"]:
                if x0 <= x <= x1 and y0 <= y <= y1:
                    ax.add_patch(plt.Circle((x, y), rules.via[1] / 2, fc="#ff8c00" if n in blockers else "#dddddd",
                                            ec="black", lw=0.3))
        for layer, pts in runs:
            if layer == lay and len(pts) > 1:
                ax.plot([x for x, _ in pts], [y for _, y in pts], color="#ffe000", lw=1.6)
        for x, y in vias:
            ax.add_patch(plt.Circle((x, y), rules.via[1] / 2, fc="none", ec="#ffe000", lw=1.2))
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(f"{lay} (seen from top)")
    fig.suptitle(gap["line"], fontsize=9)
    fig.tight_layout()
    fig.savefig(png, dpi=110, facecolor="white")
    plt.close(fig)


def render_congestion(rules, data, cong, png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    outer, holes = board_area(data)
    ny, nx = cong["util"].shape
    x0, y0, cell = cong["x0"], cong["y0"], cong["cell"]
    fig, ax = plt.subplots(figsize=(9, min(10.0, max(3.5, 7.5 * ny / max(nx, 1) + 1.0))))
    im = ax.imshow(np.ma.masked_invalid(cong["util"]), origin="lower", cmap="viridis", vmin=0,
                   vmax=max(1.0, cong["max"]), extent=[x0, x0 + nx * cell, y0, y0 + ny * cell])
    for ring in (outer.exterior, *(h.exterior for h in holes)):
        ax.plot(*ring.xy, color="#444444", lw=1)
    if cong["at_mil"]:
        ax.plot(*cong["at_mil"], "o", mfc="none", mec="#ff3030", ms=14, mew=2)
    fig.colorbar(im, ax=ax, label="utilisation: wire demand / track capacity")
    at = f" at ({cong['at'][0]:.0f}, {cong['at'][1]:.0f}) mm" if cong["at"] else ""
    ax.set_title(f"{data['pcb']}: congestion (RUDY, 1 mm grid, averaged over {RUDY_SMOOTH_CELLS} mm) – "
                 f"highest {cong['max']:.2f}{at}", fontsize=10)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(png, dpi=110, facecolor="white")
    plt.close(fig)


def diagnose_main(cfg, board, rules, only=None):
    """`route diagnose`: offline from the board as read, the board file and the last SES -> exit 0 nothing open, 2 open
    connections explained."""
    P = paths(cfg, board)
    missing = [cfg.relative(f) for f in (P["board"], P["ses"]) if not f.exists()]
    if missing:
        raise SystemExit(f"{' and '.join(missing)} missing – `edakit route read` and `edakit route route` (or `route "
                         "all`) first")
    out = P["diagnose"]
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    r = diagnose(rules, json.loads(P["board"].read_text()), read_ses(P["ses"], rules), only, out)
    cong = r["congestion"]
    at = f" at ({cong['at'][0]:.0f}, {cong['at'][1]:.0f}) mm" if cong["at"] else ""
    if only and not r["open"]:
        print(f"    {only}: not open", flush=True)
        return 0
    if not r["open"]:
        say("diagnose: nothing open")
    else:
        nets = len({g["net"] for g in r["open"]})
        say(f"diagnose: {len(r['open'])} open connection{'s' * (len(r['open']) != 1)} in {nets} "
            f"net{'s' * (nets != 1)}")
        for g in r["open"]:
            print(f"    {g['line']}", flush=True)
    say(f"congestion: highest utilisation {cong['max']:.2f}{at} -> {cfg.relative(out)}")
    return 2 if r["open"] else 0


# --- 5 apply ------------------------------------------------------------------------------------------------------

def copper(mcp):
    lines = [eda.state(x)["PrimitiveId"] for x in api(mcp, "PCB_PrimitiveLine.getAll") or []
             if eda.state(x)["Layer"] in LAYERS]
    vias = api(mcp, "PCB_PrimitiveVia.getAllPrimitiveId") or []
    pours = [eda.state(p)["PrimitiveId"] for p in api(mcp, "PCB_PrimitivePour.getAll") or []]
    return {"PCB_PrimitiveLine": lines, "PCB_PrimitiveVia": vias, "PCB_PrimitivePour": pours}


def apply_ses(rules, mcp, routes, data, stitch_file):
    """Everything in the PCB copper is generated: delete it, create the planned tracks and vias, compare."""
    ensure_pcb_focus(mcp)
    before = copper(mcp)
    attempt = 0
    for attempt in range(6):  # deleting sometimes needs several passes (7 of 223 pieces survived one)
        left = copper(mcp)
        if not any(left.values()):
            break
        for cls, ids in left.items():
            for i in range(0, len(ids), 100):
                ensure_pcb_focus(mcp)
                api(mcp, f"{cls}.delete", ids[i:i + 100])
    if any(copper(mcp).values()):
        raise SystemExit(f"old copper cannot be deleted: { {k: len(v) for k, v in copper(mcp).items()} }")
    say(f"deleted: {len(before['PCB_PrimitiveLine'])} track pieces, {len(before['PCB_PrimitiveVia'])} vias, "
        f"{len(before['PCB_PrimitivePour'])} pours" + (f" ({attempt} passes)" if attempt > 1 else ""))
    stitch_file.unlink(missing_ok=True)
    segs = segments(rules, routes, data)
    todo = [(net, s) for net in sorted(segs) for s in segs[net]]
    vias_todo = [(net, v) for net in sorted(routes) for v in routes[net]["vias"]]
    total, done = len(todo) + len(vias_todo), 0
    for net, (layer, w, a, b) in todo:
        if done % 100 == 0:
            ensure_pcb_focus(mcp)
            say(f"creating {done}/{total}, {eda.easyeda_memory()}")
        if not api(mcp, "PCB_PrimitiveLine.create", net, 1 if layer == "TOP" else 2, a[0], a[1], b[0], b[1], w, False):
            raise SystemExit(f"track {net} {layer} {a}-{b} not created")
        done += 1
    for net, (x, y) in vias_todo:
        if done % 100 == 0:
            ensure_pcb_focus(mcp)
            say(f"creating {done}/{total}, {eda.easyeda_memory()}")
        # like the vias of EasyEDA's autorouter: type 0, no blind via rule, mask expansion by rule (null)
        if not api(mcp, "PCB_PrimitiveVia.create", net, x, y, rules.via[2], rules.via[1], 0, "", None, False):
            raise SystemExit(f"via {net} ({x}, {y}) not created")
        done += 1
    problems = remove_stray(rules, mcp, segs, routes, stitch_file)
    if problems:
        for line in problems[:15]:
            print(f"    {line}", flush=True)
        raise SystemExit(f"{len(problems)} differences between plan and PCB – see above")


def verify(rules, mcp, segs, routes, stitch_file, tol=0.5):
    """Plan <-> PCB geometrically. EasyEDA merges straight consecutive pieces of a net while creating them (1510
    created, 1494 in the PCB), so counting is no check: every planned piece must lie on a track of the same net and
    layer, every track in the PCB on planned pieces (finds leftovers), every via in its place."""
    lines = [eda.state(x) for x in api(mcp, "PCB_PrimitiveLine.getAll") or [] if eda.state(x)["Layer"] in LAYERS]
    vias = [eda.state(v) for v in api(mcp, "PCB_PrimitiveVia.getAll") or []]
    have = defaultdict(list)
    for x in lines:
        have[(x["Net"], LAYERS[x["Layer"]])].append(LineString([(x["StartX"], x["StartY"]), (x["EndX"], x["EndY"])]))
    plan = defaultdict(list)
    for net, ss in segs.items():
        for layer, _, a, b in ss:
            plan[(net, layer)].append(LineString([a, b]))
    out, stray = [], []
    plan_union = {k: unary_union(g) for k, g in plan.items()}
    for key, geoms in plan.items():
        h = unary_union(have[key]) if have.get(key) else None
        for g in geoms:
            if h is None or h.distance(Point(g.coords[0])) > tol or h.distance(Point(g.coords[-1])) > tol \
                    or h.distance(g.interpolate(0.5, normalized=True)) > tol:
                out.append(f"missing in the PCB: {key[0]} {key[1]} {g.coords[0]}-{g.coords[-1]}")
    for x in lines:
        key = (x["Net"], LAYERS[x["Layer"]])
        g = LineString([(x["StartX"], x["StartY"]), (x["EndX"], x["EndY"])])
        if key not in plan_union or plan_union[key].distance(g.interpolate(0.5, normalized=True)) > tol:
            out.append(f"not planned: {key[0]} {key[1]} {g.coords[0]}-{g.coords[-1]}")
            stray.append(("PCB_PrimitiveLine", x["PrimitiveId"]))
    want_v = defaultdict(list)
    if stitch_file.exists():
        for net, x, y in json.loads(stitch_file.read_text()):
            want_v[net].append((x, y))
    have_v = defaultdict(list)
    for v in vias:
        have_v[v["Net"]].append((v["X"], v["Y"]))
    for net, r in routes.items():
        for x, y in r["vias"]:
            want_v[net].append((x, y))
            if not any(math.dist((x, y), p) <= tol for p in have_v.get(net, [])):
                out.append(f"via missing in the PCB: {net} ({x}, {y})")
    for v in vias:
        if not any(math.dist((v["X"], v["Y"]), p) <= tol for p in want_v.get(v["Net"], [])):
            out.append(f"via not planned: {v['Net']} ({v['X']:.2f}, {v['Y']:.2f})")
            stray.append(("PCB_PrimitiveVia", v["PrimitiveId"]))
    say(f"plan <-> PCB: {len(lines)} tracks, {len(vias)} vias, {len(out)} differences")
    return out, stray


def remove_stray(rules, mcp, segs, routes, stitch_file):
    """Delete tracks/vias that are not in the plan (old autorouter tracks survived deleting and came back after a
    reload), repeated until the comparison is clean or nothing changes."""
    for _ in range(4):
        problems, stray = verify(rules, mcp, segs, routes, stitch_file)
        if not stray:
            return problems
        ensure_pcb_focus(mcp)
        for cls in ("PCB_PrimitiveLine", "PCB_PrimitiveVia"):
            ids = [i for c, i in stray if c == cls]
            if ids:
                api(mcp, f"{cls}.delete", ids)
        say(f"{len(stray)} unplanned tracks/vias deleted")
    return verify(rules, mcp, segs, routes, stitch_file)[0]


# --- 6-8 pours, reload, DRC -------------------------------------------------------------------------------------

def arc_points(p0, p1, angle_deg):
    th = math.radians(angle_deg)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    d = math.hypot(dx, dy)
    if abs(th) < 1e-9 or d < 1e-9:
        return [p1]
    h = d / 2 / math.tan(th / 2)
    cx, cy = (p0[0] + p1[0]) / 2 - dy / d * h, (p0[1] + p1[1]) / 2 + dx / d * h
    a0, r = math.atan2(p0[1] - cy, p0[0] - cx), math.hypot(p0[0] - cx, p0[1] - cy)
    n = max(2, int(abs(angle_deg) / 15) + 1)
    return [(cx + r * math.cos(a0 + th * k / n), cy + r * math.sin(a0 + th * k / n)) for k in range(1, n + 1)]


def ring_points(src):
    """complexPolygon ring [x, y, "L", x, y, …, "ARC", angle, x, y, …] of a fill -> points."""
    pts, i, mode = [(src[0], src[1])], 2, "L"
    while i < len(src):
        if isinstance(src[i], str):
            mode, i = src[i], i + 1
        elif mode == "ARC":
            pts += arc_points(pts[-1], (src[i + 1], src[i + 2]), src[i])
            i += 3
        else:
            pts.append((src[i], src[i + 1]))
            i += 2
    return pts


def poured(mcp, layer, net):
    """Filled areas of a net's pour on one layer as shapely polygons (mil)."""
    from shapely.affinity import scale
    out = []
    for pid in api(mcp, "PCB_PrimitivePoured.getAllPrimitiveId") or []:
        st = eda.state(api(mcp, "PCB_PrimitivePour.get", pid))
        if st["Layer"] != layer or st.get("Net") != net:
            continue
        for fill in eda.state(api(mcp, "PCB_PrimitivePoured.get", pid))["PourFills"]:
            rings = [Polygon(ring_points(r)).buffer(0) for r in fill["path"]["complexPolygon"] if len(r) >= 6]
            if rings:
                g = rings[0]
                for h in rings[1:]:
                    g = g.symmetric_difference(h)
                out.append(scale(g, POURED_UNIT, POURED_UNIT, origin=(0, 0)))
    return out


def stitch_islands(rules, mcp, data, routes, net, layer_name, stitch_file):
    """Every loose island of the pour on `layer_name` gets a via where it has the most room inside the island AND
    inside the pour of the other layer – there the pour already keeps its distance to foreign copper. Islands without
    such room stay loose; the next fill without islands removes them."""
    from shapely.ops import polylabel
    layer = pcb.LAYER_ID[layer_name]
    other = 1 if layer == 2 else 2
    margin = rules.via[1] / 2 + 2
    own = [pad_outline(p) for p in data["pads"] if p["net"] == net and p["layer"] in (layer, 12)]
    own += [Point(v["X"], v["Y"]).buffer(rules.via[1] / 2) for v in (eda.state(s) for s in
                                                                      api(mcp, "PCB_PrimitiveVia.getAll") or [])
            if v["Net"] == net]
    own += [LineString([a, b]).buffer(w / 2) for lay, w, a, b in segments(rules, routes, data).get(net, [])
            if lay == layer_name]
    own = unary_union(own).buffer(1)
    keep = unary_union(circles(hole_keeps(rules, data) + tooling_keeps(rules)))
    target = unary_union(poured(mcp, other, net)).buffer(-margin)
    loose, vias = 0, []
    for g in poured(mcp, layer, net):
        if g.intersects(own):
            continue
        loose += 1
        room = g.buffer(-margin).intersection(target).difference(keep)
        if room.is_empty or room.area < 1:
            continue
        best = max(getattr(room, "geoms", [room]), key=lambda x: x.area)
        pt = polylabel(best, tolerance=1)
        vias.append((net, round(pt.x, 2), round(pt.y, 2)))
    ensure_pcb_focus(mcp)
    for n, x, y in vias:
        if not api(mcp, "PCB_PrimitiveVia.create", n, x, y, rules.via[2], rules.via[1], 0, "", None, False):
            raise SystemExit(f"via {n} ({x}, {y}) not created")
    old = json.loads(stitch_file.read_text()) if stitch_file.exists() else []
    stitch_file.write_text(json.dumps(old + vias))
    say(f"{net} {layer_name}: {loose} loose islands, {len(vias)} stitched with a via, {loose - len(vias)} without room")


def fill(cfg, board, mcp, nets, keep_islands_on=None, regions=None):
    pcb.pour(cfg, board, mcp, keep_islands_on, regions)
    ensure_pcb_focus(mcp)
    for net in nets:
        res = mcp.call("easyeda_pcb_rebuild_copper", confirmWrite=True, net=net, timeout=300)
        # status 'readback-mismatch' is harmless: the bridge only compares the id the rebuild returned with the stored
        # one; what counts is the number of filled areas per layer afterwards
        for r in res.get("results") or [res]:
            print(f"    pour {r.get('pourId')}: {r.get('status')}", flush=True)


def pours(cfg, board, rules, mcp, data=None, routes=None, stitch_file=None, regions=None):
    """Pours anew and filled. Tooling holes (free pads) are taken out before filling and set again afterwards –
    with a free pad in the PCB the fill fails. With stitching configured ([[pours]] stitch = "BOTTOM"),
    fill with islands first, stitch the loose islands to the other side with vias, then fill without islands.
    regions: the outlines of region_outlines for the nets on a shared layer."""
    nets = sorted({p["net"] for p in board.pours})
    pcb.remove_tooling(mcp)
    stitched = [p for p in board.pours if p.get("stitch")]
    if data is not None and stitched:
        for spec in stitched:
            fill(cfg, board, mcp, [spec["net"]], keep_islands_on=spec["stitch"], regions=regions)
            stitch_islands(rules, mcp, data, routes, spec["net"], spec["stitch"], stitch_file)
    fill(cfg, board, mcp, nets, regions=regions)
    pcb.tooling(cfg, board, mcp)
    for pid in api(mcp, "PCB_PrimitivePoured.getAllPrimitiveId") or []:
        st = eda.state(api(mcp, "PCB_PrimitivePour.get", pid))
        fills = eda.state(api(mcp, "PCB_PrimitivePoured.get", pid))["PourFills"]
        say(f"pour {st.get('Net')} {LAYERS.get(st['Layer'], st['Layer'])}: {len(fills)} filled areas")


def main(cfg, args):
    board = cfg.board(args.board, made=True)
    rules = Rules(board, args.clearance)
    if rules.joint_keep and cfg.graph.exists():
        from .design import load_graph
        rules.hand = hand_soldered(load_graph(cfg.graph), board.name)
    P = paths(cfg, board)
    passes = args.passes or rules.passes
    steps = {"all": ["read", "dsn", "route", "check", "apply", "pours", "reload", "drc"]}.get(args.action, [args.action])
    if board.routing.get("widths") == "sim" and {"dsn", "route", "check", "diagnose"} & set(steps):
        sim_widths(cfg, board, rules)
    mcp = None
    kc = is_kicad(cfg)                # the KiCad project: files and kicad-cli instead of the bridge (handbook 16)
    if kc:
        from .toolchain.kicad import board as kicad_board
        from .toolchain.kicad import cli as kicad_cli
        from .toolchain.kicad import commands as kicad_commands
    step_line = eda.Steps(len(steps), clock=time.time, t0=T0)   # the minutes of say()
    try:
        for step in steps:
            if len(steps) > 1:
                step_line(step)
            if step in ("read", "apply", "verify", "pours", "reload", "drc", "save") and mcp is None and not kc:
                mcp = eda.connect(cfg, args.verbose)
                eda.open_project(mcp, cfg)
                eda.open_pcb(mcp, board.pcb)
            if step == "read":
                data = kicad_board.board_json(cfg, board) if kc else read_board(mcp, board)
                if kc:
                    say(f"read: {len(data['components'])} parts, {len(data['pads'])} pads, "
                        f"{len(data['outlines'])} outlines from {cfg.relative(kicad_board.paths(cfg, board)['pcb'])}")
                P["board"].write_text(json.dumps(data, indent=1))
            elif step == "dsn":
                write_dsn(rules, json.loads(P["board"].read_text()), P["dsn"])
            elif step == "route":  # always a fresh DSN: a stale one routes against old rules (cheap, ~1 s)
                write_dsn(rules, json.loads(P["board"].read_text()), P["dsn"])
                run_freerouting(P["dsn"], P["ses"], P["log"], passes, args.threads, not args.no_optimizer, rules.edge_um)
            elif step == "check":
                data = json.loads(P["board"].read_text())
                tight = report_pads(rules, data, graph_accepts(cfg))  # the placement's: another routing keeps them
                tight += report_paste(cfg, data)
                tight += report_joints(cfg, board, rules, data)
                attempts = rules.attempts if args.action == "all" and not tight else 1
                for attempt in range(1, attempts + 1):
                    if attempt > 1:
                        say(f"attempt {attempt}/{attempts}: Freerouting with another order of parts and nets")
                        write_dsn(rules, data, P["dsn"], variant=attempt - 1)
                        run_freerouting(P["dsn"], P["ses"], P["log"], passes, args.threads, not args.no_optimizer,
                                        rules.edge_um)
                    routes = read_ses(P["ses"], rules)
                    open_nets = check(rules, data, routes)
                    render(rules, data, routes, P["png"], open_nets)
                    report_check(rules, data, open_nets, routes)
                    report_looks(rules, data, routes)
                    bad = clearance_check(rules, data, routes)
                    say(f"clearances/keep-outs: {len(bad)} findings")
                    for line in bad[:20]:
                        print(f"    {line}", flush=True)
                    near = report_joints(cfg, board, rules, data, routes)
                    nested = report_regions(rules, data, routes)
                    thin = report_widths(cfg, board, rules, routes)   # no new attempt routes wider
                    if not (open_nets or bad or near or nested) or thin:
                        break
                else:
                    if args.action == "all":
                        raise SystemExit(f"after {attempts} attempts nets are still open, clearances too small, a via "
                                         "at a hand-soldered joint (GEO.spacing) or a pour inside another – nothing "
                                         "written to EasyEDA. More passes (--passes), or check rules/placement."
                                         + (" Pads too close as well (above)." if tight else ""))
                    return 2
                if tight:
                    if args.action == "all":
                        pairs = len({(g["a"], g["b"]) if "a" in g else (g["joint"], g["other"]) for g in tight})
                        raise SystemExit(f"{pairs} pad pairs of different parts closer than the clearance (GEO.spacing), "
                                         "the paste gap (GEO.spacing) or the keep of a hand-soldered joint (GEO.spacing) – nothing "
                                         "written to EasyEDA. Freerouting cannot move a pad: move or turn one of the "
                                         "two parts in [place] of the board file (fix it there if the auto-layout put "
                                         "it), then place and read the board again.")
                    return 2
                if thin:
                    if args.action == "all":
                        raise SystemExit(f"{len(thin)} track widths below IPC-2221 for 1.5 x the simulated current "
                                         "(GEO.width, above) – nothing written to EasyEDA. Widen the class in "
                                         '[routing.classes] or the fixed wire, or route with [routing] widths = "sim".'
                                         + (" Nets are open as well (above)." if open_nets else ""))
                    return 2
            elif step == "diagnose":
                return diagnose_main(cfg, board, rules, getattr(args, "net", None))
            elif step == "apply" and kc:
                n, v = kicad_board.write_copper(cfg, board, rules, read_ses(P["ses"], rules),
                                                json.loads(P["board"].read_text()))
                say(f"written: {n} track pieces, {v} vias")
            elif step == "apply":
                apply_ses(rules, mcp, read_ses(P["ses"], rules), json.loads(P["board"].read_text()), P["stitch"])
            elif step == "verify" and kc:
                say("verify: the copper is written into the file as planned – nothing to compare")
            elif step == "verify":
                data, routes = json.loads(P["board"].read_text()), read_ses(P["ses"], rules)
                segs = segments(rules, routes, data)
                problems = remove_stray(rules, mcp, segs, routes, P["stitch"]) if args.cleanup \
                    else verify(rules, mcp, segs, routes, P["stitch"])[0]
                for line in problems[:30]:
                    print(f"    {line}", flush=True)
                if problems:
                    return 2
            elif step == "pours" and kc:
                if any(p.get("stitch") for p in board.pours):
                    say("  stitch of [[pours]]: EasyEDA's step – KiCad removes the loose islands")
                n = kicad_board.write_zones(cfg, board, region_outlines(cfg, board, rules))
                kicad_cli.fill_zones(kicad_board.paths(cfg, board)["pcb"], args.verbose)
                say(f"pours: {n} zones written and filled by kicad-cli")
            elif step == "pours":
                regions = region_outlines(cfg, board, rules)  # before anything is written
                data = json.loads(P["board"].read_text()) if P["board"].exists() else None
                routes = read_ses(P["ses"], rules) if P["ses"].exists() else {}
                pours(cfg, board, rules, mcp, data, routes, P["stitch"], regions)
            elif step == "reload" and kc:
                say("nothing to reload: the KiCad PCB is a file")
            elif step == "reload":
                eda.reload_pcb(mcp)
                say("PCB saved and reloaded")
            elif step == "drc" and kc:
                found = kicad_cli.drc(kicad_board.paths(cfg, board)["pcb"], P["drc"].with_suffix(".kicad.json"),
                                      verbose=args.verbose)
                P["drc"].write_text(json.dumps(found, indent=1, ensure_ascii=False))
                code = kicad_commands.drc_report(found, say=say)
                if code:
                    return code
            elif step == "drc":
                found = eda.drc(mcp, P["drc"])
                P["netlist_diff"].unlink(missing_ok=True)
                code = pcb.drc_report(cfg, board, mcp, found, P["netlist_diff"], say=say)
                if code:
                    return code
            elif step == "save" and kc:
                say("nothing to save: the KiCad PCB is a file")
            elif step == "save":
                say(f"PCB saved: {eda.save_pcb(mcp)}")
    except eda.MCPError as e:
        return eda.die(str(e))
    except Exception as e:
        if kc and type(e).__name__ in ("BoardError", "CliError"):
            return eda.die(str(e))
        raise
    finally:
        if mcp:
            mcp.close()
    return 0
