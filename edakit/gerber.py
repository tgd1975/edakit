"""Read the Gerber and drill files EasyEDA Pro exports, and check the copper without trusting EasyEDA.

Why the detour through Gerber: the bridge cuts DRC details and pour polygons ([MaxDepth]), and the files that go to
the manufacturer are what matters in the end. The Gerber export contains all copper including filled pours, plus
FlyingProbeTesting.json with the pad positions. `Copper` rasterises TOP and BOTTOM (0.02 mm), joins the layers
through the plated holes and groups the pads by connected copper. Target: one group per net, no group with two nets.

Gerber knows no nets, and FlyingProbeTesting.json renames some (a net CHAIN1_D23_A came out as NET_3). So only the
positions and sizes come from the export; the net of each pad comes from the graph ("D23_1" -> D23.1 -> net).

Supported is what EasyEDA Pro writes – apertures C/R/O plus the RoundRect macro on the mask layers, G01/G02/G03
(G75), D01/D02/D03, regions G36/G37, no LPC – and what KiCad writes (the KiCad tool chain, handbook 16): the same, plus
polygon apertures (P) and aperture macros of the primitives circle, outline, polygon, vector line and centre line
(KiCad's RoundRect, RotRect, Outline, FreePoly). A flash of a KiCad macro or polygon becomes a region of its outline;
X2 attributes are skipped.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path

FILES = {"top": "Gerber_TopLayer.GTL", "bottom": "Gerber_BottomLayer.GBL", "top_silk": "Gerber_TopSilkscreenLayer.GTO",
         "bottom_silk": "Gerber_BottomSilkscreenLayer.GBO", "top_mask": "Gerber_TopSolderMaskLayer.GTS",
         "bottom_mask": "Gerber_BottomSolderMaskLayer.GBS", "outline": "Gerber_BoardOutlineLayer.GKO",
         "pth": "Drill_PTH_Through.DRL", "vias": "Drill_PTH_Through_Via.DRL", "npth": "Drill_NPTH_Through.DRL",
         "probe": "FlyingProbeTesting.json"}
REQUIRED = ["top", "bottom", "top_silk", "bottom_silk", "top_mask", "bottom_mask", "outline", "pth", "probe"]
RES = 0.02  # mm per raster point


def missing(folder, *keys):
    """File names of these FILES keys that are not in folder."""
    return [FILES[k] for k in keys if not (Path(folder) / FILES[k]).exists()]


def parse_gerber(path):
    """-> [("draw", ((kind, a, b), points)), ("flash", ((kind, a, b), x, y)), ("region", [contours])] in mm.
    EasyEDA's RoundRect becomes its enclosing rectangle ("RR", width, height); in a file KiCad wrote, a flash of a macro
    or polygon aperture becomes the region of its outline (kind "M")."""
    t = Path(path).read_text()
    div = 10 ** int(re.search(r"%FSLAX\d(\d)Y\d\d\*%", t).group(1))
    aps = {int(m.group(1)): (m.group(2), float(m.group(3)), float(m.group(4) or m.group(3)))
           for m in re.finditer(r"%ADD(\d+)([CRO]),([\d.]+)(?:X([\d.]+))?.*?\*%", t)}
    kicad = "KiCad" in t[:2000] or "Kicad" in t[:2000]
    if kicad:                  # KiCad: macros evaluated from their definitions, polygon apertures
        macros = {m.group(1): m.group(2) for m in re.finditer(r"%AM([A-Za-z_][\w.]*)\*(.*?)%", t, re.S)}
        for m in re.finditer(r"%ADD(\d+)([A-Za-z_][\w.]*),?([^*]*)\*%", t):
            name, args = m.group(2), [float(v) for v in m.group(3).split("X") if v]
            if name == "P":
                aps[int(m.group(1))] = ("M", regular_polygon(*args))
            elif name in macros:
                aps[int(m.group(1))] = ("M", macro_outline(macros[name], args))
    else:
        for m in re.finditer(r"%ADD(\d+)RoundRect,([^*]+)\*%", t):
            r, *c = (float(v) for v in m.group(2).split("X"))
            aps[int(m.group(1))] = ("RR", 2 * max(abs(v) for v in c[0::2]) + r, 2 * max(abs(v) for v in c[1::2]) + r)
    ops, x, y, mode, ap, region = [], 0.0, 0.0, 1, None, None
    for line in t.splitlines():
        line = line.strip()
        if not line or line.startswith(("%", "G04")):
            continue
        m = re.match(r"(?:G54)?D(\d+)\*$", line)
        if m and int(m.group(1)) >= 10:
            ap = int(m.group(1))
            continue
        if line.startswith("G36"):
            region = []
            continue
        if line.startswith("G37"):
            if region:
                ops.append(("region", region))
            region = None
            continue
        m = re.match(r"(G0[123])?(?:X(-?\d+))?(?:Y(-?\d+))?(?:I(-?\d+))?(?:J(-?\d+))?(D0[123])\*", line)
        if not m:
            mg = re.match(r"(G0[123])\*", line)
            if mg:
                mode = int(mg.group(1)[1:])
            continue
        if m.group(1):
            mode = int(m.group(1)[1:])
        nx = int(m.group(2)) / div if m.group(2) else x
        ny = int(m.group(3)) / div if m.group(3) else y
        i = int(m.group(4)) / div if m.group(4) else 0.0
        j = int(m.group(5)) / div if m.group(5) else 0.0
        d = int(m.group(6)[1:])
        if d == 1:
            pts = [(x, y), (nx, ny)] if mode == 1 else arc(x, y, nx, ny, i, j, mode == 2)
            if region is not None:
                if not region:
                    region.append([(x, y)])
                region[-1].extend(pts[1:])
            else:
                ops.append(("draw", (aps[ap], pts)))
        elif d == 2 and region is not None:
            region.append([(nx, ny)])
        elif d == 3 and aps[ap][0] == "M":    # a KiCad macro or polygon: its outline as a region
            ops.append(("region", [[(nx + px, ny + py) for px, py in ring] for ring in aps[ap][1]]))
        elif d == 3:
            ops.append(("flash", (aps[ap], nx, ny)))
        x, y = nx, ny
    return ops


def regular_polygon(diameter, vertices=3, rotation=0.0, *_):
    """The outline of a polygon aperture P (outer diameter, vertices, rotation): [ring]."""
    n = max(3, int(vertices))
    return [[(diameter / 2 * math.cos(math.radians(rotation + 360 * k / n)),
              diameter / 2 * math.sin(math.radians(rotation + 360 * k / n))) for k in range(n)]]


def macro_value(expr, var):
    """An expression of a macro: numbers, $n, + - x (times) / and brackets."""
    expr = re.sub(r"\$(\d+)", lambda m: repr(var.get(int(m.group(1)), 0.0)), expr.strip())
    expr = expr.replace("x", "*").replace("X", "*")
    if not re.fullmatch(r"[\d.+\-*/() eE]*", expr):
        raise ValueError(f"macro expression {expr!r}")
    return float(eval(expr, {"__builtins__": {}}, {})) if expr.strip() else 0.0   # noqa: S307 – digits and + - * / only


def macro_outline(body, args):
    """The outline of an aperture macro with these arguments, as [ring] relative to the flash: the primitives circle (1),
    outline (4), polygon (5), vector line (20) and centre line (21) united, exposure off cut away."""
    from shapely import affinity
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union
    var = {k + 1: v for k, v in enumerate(args)}
    shape = Polygon()
    for stmt in (s.strip() for s in body.replace("\n", "").split("*")):
        if not stmt or stmt.startswith("0"):
            continue
        if stmt.startswith("$") and "=" in stmt:
            k, expr = stmt[1:].split("=", 1)
            var[int(k)] = macro_value(expr, var)
            continue
        code, *vals = stmt.split(",")
        v = [macro_value(e, var) for e in vals]
        code = int(code)
        if code == 1:                                    # circle: exposure, diameter, x, y[, rotation]
            g = Point(v[2], v[3]).buffer(v[1] / 2, 16)
            rot = v[4] if len(v) > 4 else 0
        elif code == 4:                                  # outline: exposure, n, x0, y0, …, xn, yn, rotation
            n = int(v[1])
            g = Polygon(list(zip(v[2:4 + 2 * n:2], v[3:4 + 2 * n:2]))).buffer(0)
            rot = v[4 + 2 * n] if len(v) > 4 + 2 * n else 0
        elif code == 5:                                  # polygon: exposure, vertices, x, y, diameter, rotation
            ring = regular_polygon(v[4], v[1])[0]
            g = Polygon([(v[2] + px, v[3] + py) for px, py in ring])
            rot = v[5] if len(v) > 5 else 0
        elif code == 20:                                 # vector line: exposure, width, x1, y1, x2, y2, rotation
            g = LineString([(v[2], v[3]), (v[4], v[5])]).buffer(v[1] / 2, cap_style="flat")
            rot = v[6] if len(v) > 6 else 0
        elif code == 21:                                 # centre line: exposure, width, height, x, y, rotation
            g = Polygon([(v[3] - v[1] / 2, v[4] - v[2] / 2), (v[3] + v[1] / 2, v[4] - v[2] / 2),
                         (v[3] + v[1] / 2, v[4] + v[2] / 2), (v[3] - v[1] / 2, v[4] + v[2] / 2)])
            rot = v[5] if len(v) > 5 else 0
        else:
            raise ValueError(f"aperture macro primitive {code} not supported")
        if rot:
            g = affinity.rotate(g, rot, origin=(0, 0))
        shape = unary_union([shape, g]) if v[0] else shape.difference(g)
    parts = list(getattr(shape, "geoms", [shape]))
    return [list(p.exterior.coords)[:-1] for p in parts if not p.is_empty]


def arc(x0, y0, x1, y1, i, j, cw):
    cx, cy = x0 + i, y0 + j
    r = math.hypot(x0 - cx, y0 - cy)
    a0, a1 = math.atan2(y0 - cy, x0 - cx), math.atan2(y1 - cy, x1 - cx)
    if cw:
        while a1 >= a0:
            a1 -= 2 * math.pi
    else:
        while a1 <= a0:
            a1 += 2 * math.pi
    n = max(4, int(abs(a1 - a0) * r / 0.05))
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


def parse_drills(path):
    """Drill file -> [(x0, y0, x1, y1, width)] in mm: a round hole has x1, y1 = x0, y0, a slot (G85) its two ends."""
    path = Path(path)
    if not path.exists():
        return []
    t = path.read_text()
    tools = {int(m.group(1)): float(m.group(2)) for m in re.finditer(r"^T(\d+)C([\d.]+)", t, re.M)}
    out, cur = [], None
    for line in t.splitlines():
        if m := re.match(r"^T(\d+)$", line):
            cur = tools.get(int(m.group(1)))
        elif (m := re.match(r"^X(-?[\d.]+)Y(-?[\d.]+)(?:G85X(-?[\d.]+)Y(-?[\d.]+))?", line)) and cur:
            x0, y0 = float(m.group(1)), float(m.group(2))
            x1, y1 = (float(m.group(3)), float(m.group(4))) if m.group(3) else (x0, y0)
            out.append((x0, y0, x1, y1, cur))
    return out


def parse_holes(path):
    """Drill file -> [(x, y, width, length)] in mm; slots (G85) with centre and overall length."""
    return [((x0 + x1) / 2, (y0 + y1) / 2, w, w + math.hypot(x1 - x0, y1 - y0)) for x0, y0, x1, y1, w in parse_drills(path)]


def points(ops):
    """Every coordinate of these Gerber operations (mm)."""
    return [p for kind, dat in ops for p in
            ([dat[1:]] if kind == "flash" else dat[1] if kind == "draw" else [q for c in dat for q in c])]


def shape(ops, quad_segs=16):
    """Gerber operations as one shapely area (mm); circles as polygons of quad_segs segments a quarter."""
    from shapely.geometry import LineString, Point, Polygon, box
    from shapely.ops import unary_union
    parts = []
    for kind_, dat in ops:
        if kind_ == "region":
            parts += [Polygon(c).buffer(0) for c in dat if len(c) >= 3]
        elif kind_ == "flash":
            (kind, a, b), x, y = dat
            if kind == "C":
                parts.append(Point(x, y).buffer(a / 2, quad_segs))
            elif kind == "O":
                d = abs(a - b) / 2
                seg = ((x - d, y), (x + d, y)) if a > b else ((x, y - d), (x, y + d))
                parts.append(LineString(seg).buffer(min(a, b) / 2, quad_segs) if d else
                             Point(x, y).buffer(a / 2, quad_segs))
            else:
                parts.append(box(x - a / 2, y - b / 2, x + a / 2, y + b / 2))
        else:
            (kind, a, b), pts = dat
            parts.append(LineString(pts).buffer(a / 2, quad_segs) if len(pts) > 1 else
                         Point(pts[0]).buffer(a / 2, quad_segs))
    return unary_union(parts)


def loops(path):
    """Closed paths of the outline layer as point lists (pieces chained through shared end points)."""
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    segs = []
    for kind, dat in parse_gerber(path):
        pts = dat[1] if kind == "draw" else [p for c in dat for p in c] if kind == "region" else []
        key = [(round(x, 3), round(y, 3)) for x, y in pts]
        for a, b in zip(key, key[1:]):
            parent[find(a)] = find(b)
        segs.append(key)
    groups = defaultdict(list)
    for key in segs:
        if key:
            groups[find(key[0])].extend(key)
    return list(groups.values())


def bbox(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


class Raster:
    """A frame in mm drawn at RES per point: Gerber operations -> bool image, row 0 at the top (max y)."""

    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0 = x0, y0
        self.w = int((x1 - x0) / RES)
        self.h = int((y1 - y0) / RES)

    def px(self, x, y):
        return (x - self.x0) / RES, self.h - (y - self.y0) / RES

    def mm(self, col, row):
        """Point (column, row) of the image -> (x, y) in mm."""
        return self.x0 + col * RES, self.y0 + (self.h - row) * RES

    def render(self, ops):
        import numpy as np
        from PIL import Image, ImageDraw
        img = Image.new("1", (self.w, self.h), 0)
        dr = ImageDraw.Draw(img)
        for kind, dat in ops:
            if kind == "region":
                for c in dat:
                    if len(c) >= 3:
                        dr.polygon([self.px(*p) for p in c], fill=1)
            elif kind == "flash":
                (k, a, b), x, y = dat
                cx, cy = self.px(x, y)
                bx = [cx - a / 2 / RES, cy - b / 2 / RES, cx + a / 2 / RES, cy + b / 2 / RES]
                if k == "C":
                    dr.ellipse(bx, fill=1)
                elif k == "R":
                    dr.rectangle(bx, fill=1)
                else:
                    dr.rounded_rectangle(bx, radius=min(a, b) / 2 / RES, fill=1)
            else:
                (k, a, b), pts = dat
                q = [self.px(*p) for p in pts]
                dr.line(q, fill=1, width=max(1, round(a / RES)))
                for cx, cy in q:
                    dr.ellipse([cx - a / 2 / RES, cy - a / 2 / RES, cx + a / 2 / RES, cy + a / 2 / RES], fill=1)
        return np.array(img, dtype=bool)


class Copper(Raster):
    """Rasterised copper layers, islands, connections through plated holes, pads per island and net. The raster covers
    the copper and 3 mm around it, and the points of extent (mm) as well – the board outline, say (GEO.pour)."""

    def __init__(self, folder, pin_net, extent=()):
        import numpy as np
        from scipy import ndimage
        self.d = Path(folder)
        self.ops = {"T": parse_gerber(self.d / FILES["top"]), "B": parse_gerber(self.d / FILES["bottom"])}
        self.holes = [(x, y, w) for x, y, w, _ in parse_holes(self.d / FILES["pth"]) + parse_holes(self.d / FILES["vias"])]
        pts = [p for ops in self.ops.values() for p in points(ops)] + list(extent)
        x0, y0 = min(p[0] for p in pts) - 3, min(p[1] for p in pts) - 3
        super().__init__(x0, y0, max(p[0] for p in pts) + 3, max(p[1] for p in pts) + 3)
        self.lab = {k: ndimage.label(self.render(self.ops[k]), structure=np.ones((3, 3)))[0] for k in "TB"}
        self.parent = {}
        for x, y, dia in self.holes:  # the barrel joins what touches the hole on both layers
            for a in self.labels_at("T", x, y, dia / 2 + 0.05):
                for b in self.labels_at("B", x, y, dia / 2 + 0.05):
                    self.union(("T", a), ("B", b))
        graph_net = {p.replace(".", "_", 1): n for p, n in pin_net.items()}
        fp = json.loads((self.d / FILES["probe"]).read_text())
        self.pins = {}
        self.groups = defaultdict(lambda: defaultdict(set))  # net -> island -> pins
        nets_at = defaultdict(set)
        mil = 0.0254
        for row in fp["pins"]["rows"]:
            p = dict(zip(fp["pins"]["fields"], row))
            if p["PIN_NAME"].startswith("PAD"):  # duplicate entries without a part
                continue
            x, y = p["PIN_X"] * mil, p["PIN_Y"] * mil
            net = graph_net.get(p["PIN_NAME"], "")
            self.pins[p["PIN_NAME"]] = (x, y, net)
            r = min(p["PAD_SIZEX"], p["PAD_SIZEY"]) * mil / 4
            for k in ("TB" if p["PIN_TYPE"] != "SMD" else ("T" if p["LAYER"] in ("T", "TOP") else "B")):
                for lab in self.labels_at(k, x, y, r):
                    g = self.find((k, lab))
                    nets_at[g].add(net)
                    if net:
                        self.groups[net][g].add(p["PIN_NAME"])
        self.shorts = [(sorted(n - {""}), sorted(p for net in n - {""} for p in self.groups[net][g]))
                       for g, n in nets_at.items() if len(n - {""}) > 1]

    def find(self, a):
        self.parent.setdefault(a, a)
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)

    def labels_at(self, k, x, y, r):
        import numpy as np
        cx, cy = self.px(x, y)
        rr = max(1, int(r / RES))
        sub = self.lab[k][max(0, int(cy) - rr):int(cy) + rr + 1, max(0, int(cx) - rr):int(cx) + rr + 1]
        return set(np.unique(sub)) - {0}

    def net_groups(self, net):
        """Pad groups of a net, largest first; more than one = the net is open in the copper."""
        return sorted((sorted(p) for p in self.groups.get(net, {}).values()), key=len, reverse=True)


def plus_signs(path, lo=0.3, hi=2.0, tol=0.1):
    """'+' signs drawn in a silkscreen file the way footprints draw them (GEO.mark): two straight strokes of lo to hi mm,
    as long as each other (± 0.2 mm), at right angles (|cos| < 0.1), their middles within tol mm of each other.
    -> [(x, y)] in mm, one per sign. A frame, an arc or a letter does not qualify: its strokes meet at their ends, are
    shorter or longer, or cross at another angle."""
    strokes = []
    for kind, dat in parse_gerber(path):
        if kind == "draw":
            strokes += [(a, b) for a, b in zip(dat[1], dat[1][1:]) if lo <= math.dist(a, b) <= hi]
    mids = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in strokes]
    cells = defaultdict(list)
    for i, (x, y) in enumerate(mids):
        cells[(math.floor(x / tol), math.floor(y / tol))].append(i)
    found = []
    for i, ((a, b), m) in enumerate(zip(strokes, mids)):
        cx, cy = math.floor(m[0] / tol), math.floor(m[1] / tol)
        for j in (j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in cells.get((cx + dx, cy + dy), ()) if j > i):
            (c, e), n = strokes[j], mids[j]
            u, v = (b[0] - a[0], b[1] - a[1]), (e[0] - c[0], e[1] - c[1])
            if (math.dist(m, n) <= tol and abs(math.hypot(*u) - math.hypot(*v)) <= 0.2
                    and abs(u[0] * v[0] + u[1] * v[1]) < 0.1 * math.hypot(*u) * math.hypot(*v)):
                found.append(((m[0] + n[0]) / 2, (m[1] + n[1]) / 2))
    signs = []
    for p in found:                     # a sign drawn twice is one sign
        if not any(math.dist(p, q) <= tol for q in signs):
            signs.append(p)
    return signs


def outline_shape(folder):
    """The board as the outline file draws it (mm, GEO.silk): the area its closed paths enclose – mounting holes and
    cut-outs left open – without the NPTH holes of the drill file. None without a closed path."""
    from shapely.geometry import LineString, Point
    from shapely.ops import polygonize, unary_union
    folder = Path(folder)
    lines = []
    for kind, dat in parse_gerber(folder / FILES["outline"]):
        pts = [(round(x, 3), round(y, 3)) for x, y in (dat[1] if kind == "draw" else [])]
        lines += [LineString([a, b]) for a, b in zip(pts, pts[1:]) if a != b]
    faces = sorted(polygonize(unary_union(lines)), key=lambda p: -p.area) if lines else []
    if not faces:
        return None
    board = faces[0]
    inner = [f for f in faces[1:] if board.contains(f)]     # a closed path inside the board is a cut-out
    drilled = [Point(x, y).buffer(w / 2) for x, y, w, _ in parse_holes(folder / FILES["npth"])]
    return board.difference(unary_union(inner + drilled))
