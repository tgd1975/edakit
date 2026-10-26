"""Route a board with Freerouting instead of EasyEDA's autorouter, and write the result into EasyEDA.

EasyEDA's autorouter (PCB_Document.autoRouting, beta) keeps its result only if the whole run succeeds – otherwise it
throws every track away (1773 lines -> 223 in one observed run). It runs past the bridge timeout, sometimes does not
start, has a fixed 900 s limit and left nets open. So routing happens outside EasyEDA, reproducibly:

    1 read     pads, outline, holes, parts from EasyEDA -> <artifacts>/route/<board>_board.json
    2 dsn      offline: our own Specctra DSN (rules from [routing] of the board file); parts, pins and nets in a
               fixed order
    3 route    offline: Freerouting (pinned, downloads itself once, SHA-256 checked), no GUI -> <board>.ses
    4 check    offline: every net connected, clearances >= rule, nothing in keep-outs; preview PNG with open
               connections in yellow. In `all`: up to `attempts` runs with a reshuffled DSN while something is open.
               A pour-only net (pour_only in [[pours]] of the board file) gets no tracks: its pour, computed here,
               connects it
    5 apply    delete all tracks, vias and pours in the PCB, create the ones from the SES, compare geometrically,
               delete anything unplanned
    6 pours    pours of [[pours]] anew and filled; optional stitching of loose islands with vias
    7 reload   save, close the PCB tab, open it again – otherwise the DRC reports false connection errors
    8 drc      EasyEDA DRC with details -> <board>_drc.json; exit 2 on findings

    edakit route all                 # 1-8, progress per step; exit 0 = DRC 0
    edakit route route --passes 60   # single steps

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
from .config import MIL_PER_MM, POUR_CLEARANCE_MM, POUR_MIN_WIDTH_MM
from .design import natural_key
from .eda import api, ensure_pcb_focus

LAYERS = {1: "TOP", 2: "BOTTOM"}
SNAP_MIL = 0.5  # points closer than this count as one (EasyEDA drops pieces < ~0.5 mil)
POURED_UNIT = 10  # mil per unit: EasyEDA returns pour fills (PourFills) in 10 mil, tracks and pads in mil

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

    def net_class(self, net):
        for name, (w, nets) in self.classes.items():
            if net in nets:
                return name, w
        return "SIGNAL", self.signal


def paths(cfg, board):
    d = cfg.artifact("route", ".keep").parent
    return {k: d / f"{board.name}{suffix}" for k, suffix in
            (("board", "_board.json"), ("dsn", ".dsn"), ("ses", ".ses"), ("log", "_freerouting.log"),
             ("png", "_routing.png"), ("drc", "_drc.json"), ("stitch", "_stitch.json"))}


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
    """Pours declared as planes ([[pours]] plane = true): (net, layer). Freerouting then connects the
    net's pads on that layer to the plane with vias instead of tracks."""
    return [(p["net"], layer) for p in rules.board.pours if p.get("plane") for layer in p.get("layers", ["BOTTOM"])]


def _parts(geom):
    return [g for g in getattr(geom, "geoms", [geom]) if not g.is_empty]


def convex_pieces(geom, min_area=1.0):
    """Split a (possibly concave, multi-part) area into convex pieces: horizontal strips at every vertex, then
    vertical cuts where a strip is still concave. Freerouting wants convex keep-outs."""
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
                if s.geom_type != "Polygon" or s.area < min_area:
                    continue
                if s.convex_hull.area - s.area < 0.5:
                    pieces.append(s)
                    continue
                xs = sorted({x for x, _ in s.exterior.coords})
                for c, d in zip(xs, xs[1:]):
                    pieces += [u for u in _parts(s.intersection(box(c, a, d, b)))
                               if u.geom_type == "Polygon" and u.area >= min_area]
    bad = [p for p in pieces if p.convex_hull.area - p.area > 0.5]
    if bad:
        raise SystemExit(f"{len(bad)} keep-out pieces are not convex – route.convex_pieces needs a look")
    return pieces


def outside_strips(rules, outer, margin=20.0):
    """Area between a rectangle around the board and the outline moved in by the edge clearance, as convex pieces.
    Freerouting 2.4.1 routed nothing in the upper part of a concave outline given as boundary; the same nets routed at
    once with a rectangle. So: rectangle as boundary, everything outside the board as keep-outs."""
    inner = outer.buffer(-rules.edge_um / 25.4, join_style=2)
    x0, y0, x1, y1 = outer.bounds
    frame = box(x0 - margin, y0 - margin, x1 + margin, y1 + margin)
    return frame, convex_pieces(frame.difference(inner))


def config_keepouts(rules, data):
    """[[routing.keepouts]]: {layer, rect | polygon (plan mm), what: "wire" (vias allowed) | "all",
    windows: [parts whose pads stay reachable, with window_mm margin]} -> [(layer, kind, convex piece in mil)]."""
    board = rules.board
    out = []
    for k in board.routing.get("keepouts", []):
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
        for layer in ([k["layer"]] if isinstance(k.get("layer"), str) else k.get("layer", ["TOP", "BOTTOM"])):
            out += [(layer, k.get("what", "wire"), piece) for piece in convex_pieces(area)]
    return out


def fixed_wires(rules):
    """[[routing.fixed_wires]]: {net, layer, width_mil, points (plan mm)} – protected in the DSN: Freerouting
    routes around them and keeps them (e.g. a short switching loop)."""
    b = rules.board
    return [(w["net"], w.get("layer", "TOP"), w.get("width_mil", rules.signal),
             [tuple(round(v * MIL_PER_MM, 2) for v in b.eda_point(x, y)) for x, y in w["points"]])
            for w in b.routing.get("fixed_wires", [])]


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
    L = [f"(pcb {q(data['pcb'])}",
         '  (parser (string_quote ") (space_in_quoted_tokens on) (host_cad "edakit") (host_version "1"))',
         # 1/100 mil: with 1/1000 mil Freerouting 2.4.1 computes wrongly (board ≈ 7 million units high: unreachable
         # pads, 19 phantom violations); with mil 100 it routed at once
         "  (resolution mil 100)", "  (unit mil)", "  (structure"]
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
    L.append("  )")
    L.append(")")
    out.write_text("\n".join(L) + "\n")
    say(f"DSN: {len(routed)} nets with >= 2 pins, {len(data['pads'])} pads, {len(padstacks)} padstacks, {len(keep)} hole "
        f"keep-outs, {len(strips)} edge strips, {len(extra)} keep-out pieces, {len(fixed)} fixed wires, clearance "
        f"{rules.clear} mil" + (f", order {variant}" if variant else "")
        + (f", pour-only (no tracks): {', '.join(sorted(rules.pour_only))}" if rules.pour_only else "") + f" -> {out}")
    for (name, w), members in sorted(cls.items()):
        print(f"    class {name}: {w} mil, {len(members)} nets", flush=True)


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

def pour_pieces(rules, data, routes, segs=None):
    """The pours of the pour-only nets as EasyEDA fills them, computed offline: {(net, layer): [polygon, …]} in mil.
    Per net and layer: the pour outline of `pcb pour`, without the copper of other nets on that layer – pads (those
    without a net too), tracks, vias – grown by clearance_mm, opened by half of min_width_mm (EasyEDA does not fill
    narrower necks). The net's own copper is not taken away: the pour reaches its pads, tracks and vias. Other pours on
    the same layer are not taken into account."""
    if not rules.pour_only:
        return {}
    board = rules.board
    if not board.outline:
        raise SystemExit(f"board {board.name}: pour_only needs the outline in the board file – the pour outline is "
                         "computed from it")
    outline = Polygon([tuple(v * MIL_PER_MM for v in board.eda_point(x, y)) for x, y in pcb.pour_outline(board)])
    segs = segments(rules, routes, data) if segs is None else segs
    copper = {"TOP": [], "BOTTOM": []}  # (net, copper) per layer
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
    out = {}
    for net, specs in sorted(rules.pour_only.items()):
        for layer, clearance, width in specs:
            area = outline.difference(unary_union([g for n, g in copper[layer] if n != net]).buffer(clearance))
            if width > 0:
                area = area.buffer(-width / 2).buffer(width / 2)
            out[(net, layer)] = [g for g in _parts(area) if g.geom_type == "Polygon"]
    return out


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
            if others:
                print(f"    ! {net} {layer}: the pour of {', '.join(others)} shares the layer – the computed pour of "
                      f"{net} does not leave it out, and EasyEDA fills overlapping pours by priority", flush=True)


def render(rules, data, routes, png, open_nets=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MPoly
    outer, holes = board_area(data)
    segs = segments(rules, routes, data)
    pours = pour_pieces(rules, data, routes, segs)
    fig, axes = plt.subplots(1, 2, figsize=(14, 8))
    for ax, side, color in ((axes[0], "TOP", "#d62728"), (axes[1], "BOTTOM", "#1f77b4")):
        ax.add_patch(MPoly(list(outer.exterior.coords), closed=True, fc="#0b3d1a", ec="#aaaaaa", lw=1))
        for h in holes:
            ax.add_patch(MPoly(list(h.exterior.coords), closed=True, fc="white", ec="#aaaaaa"))
        for g in (g for (_, layer), gs in pours.items() if layer == side for g in gs):  # pours of pour-only nets
            ax.add_patch(MPoly(list(g.exterior.coords), closed=True, fc=color, ec="none", alpha=0.25))
            for ring in g.interiors:
                ax.add_patch(MPoly(list(ring.coords), closed=True, fc="#0b3d1a", ec="none"))
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


def fill(cfg, board, mcp, nets, keep_islands_on=None):
    pcb.pour(cfg, board, mcp, keep_islands_on)
    ensure_pcb_focus(mcp)
    for net in nets:
        res = mcp.call("easyeda_pcb_rebuild_copper", confirmWrite=True, net=net, timeout=300)
        # status 'readback-mismatch' is harmless: the bridge only compares the id the rebuild returned with the stored
        # one; what counts is the number of filled areas per layer afterwards
        for r in res.get("results") or [res]:
            print(f"    pour {r.get('pourId')}: {r.get('status')}", flush=True)


def pours(cfg, board, rules, mcp, data=None, routes=None, stitch_file=None):
    """Pours anew and filled. Tooling holes (free pads) are taken out before filling and set again afterwards –
    with a free pad in the PCB the fill fails. With stitching configured ([[pours]] stitch = "BOTTOM"),
    fill with islands first, stitch the loose islands to the other side with vias, then fill without islands."""
    nets = sorted({p["net"] for p in board.pours})
    pcb.remove_tooling(mcp)
    stitched = [p for p in board.pours if p.get("stitch")]
    if data is not None and stitched:
        for spec in stitched:
            fill(cfg, board, mcp, [spec["net"]], keep_islands_on=spec["stitch"])
            stitch_islands(rules, mcp, data, routes, spec["net"], spec["stitch"], stitch_file)
    fill(cfg, board, mcp, nets)
    pcb.tooling(cfg, board, mcp)
    for pid in api(mcp, "PCB_PrimitivePoured.getAllPrimitiveId") or []:
        st = eda.state(api(mcp, "PCB_PrimitivePour.get", pid))
        fills = eda.state(api(mcp, "PCB_PrimitivePoured.get", pid))["PourFills"]
        say(f"pour {st.get('Net')} {LAYERS.get(st['Layer'], st['Layer'])}: {len(fills)} filled areas")


def main(cfg, args):
    board = cfg.board(args.board)
    rules = Rules(board, args.clearance)
    P = paths(cfg, board)
    passes = args.passes or rules.passes
    steps = {"all": ["read", "dsn", "route", "check", "apply", "pours", "reload", "drc"]}.get(args.action, [args.action])
    mcp = None
    try:
        for n, step in enumerate(steps, 1):
            if len(steps) > 1:
                say(f"step {n}/{len(steps)}: {step}")
            if step in ("read", "apply", "verify", "pours", "reload", "drc", "save") and mcp is None:
                mcp = eda.connect(cfg, args.verbose)
                eda.open_project(mcp, cfg)
                eda.open_pcb(mcp, board.pcb)
            if step == "read":
                P["board"].write_text(json.dumps(read_board(mcp, board), indent=1))
            elif step == "dsn":
                write_dsn(rules, json.loads(P["board"].read_text()), P["dsn"])
            elif step == "route":  # always a fresh DSN: a stale one routes against old rules (cheap, ~1 s)
                write_dsn(rules, json.loads(P["board"].read_text()), P["dsn"])
                run_freerouting(P["dsn"], P["ses"], P["log"], passes, args.threads, not args.no_optimizer, rules.edge_um)
            elif step == "check":
                data = json.loads(P["board"].read_text())
                attempts = rules.attempts if args.action == "all" else 1
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
                    bad = clearance_check(rules, data, routes)
                    say(f"clearances/keep-outs: {len(bad)} findings")
                    for line in bad[:20]:
                        print(f"    {line}", flush=True)
                    if not (open_nets or bad):
                        break
                else:
                    if args.action == "all":
                        raise SystemExit(f"after {attempts} attempts nets are still open or clearances too small – "
                                         "nothing written to EasyEDA. More passes (--passes), or check rules/placement.")
                    return 2
            elif step == "apply":
                apply_ses(rules, mcp, read_ses(P["ses"], rules), json.loads(P["board"].read_text()), P["stitch"])
            elif step == "verify":
                data, routes = json.loads(P["board"].read_text()), read_ses(P["ses"], rules)
                segs = segments(rules, routes, data)
                problems = remove_stray(rules, mcp, segs, routes, P["stitch"]) if args.cleanup \
                    else verify(rules, mcp, segs, routes, P["stitch"])[0]
                for line in problems[:30]:
                    print(f"    {line}", flush=True)
                if problems:
                    return 2
            elif step == "pours":
                data = json.loads(P["board"].read_text()) if P["board"].exists() else None
                routes = read_ses(P["ses"], rules) if P["ses"].exists() else {}
                pours(cfg, board, rules, mcp, data, routes, P["stitch"])
            elif step == "reload":
                eda.reload_pcb(mcp)
                say("PCB saved and reloaded")
            elif step == "drc":
                found = eda.drc(mcp, P["drc"])
                say(eda.describe_drc(found))
                if found:
                    return 2
            elif step == "save":
                say(f"PCB saved: {eda.save_pcb(mcp)}")
    except eda.MCPError as e:
        return eda.die(str(e))
    finally:
        if mcp:
            mcp.close()
    return 0
