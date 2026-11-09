#!/usr/bin/env python3
"""Prototype of the perfboard plan (../../perfboard-layout.md): check a plan against an edakit project, draw it, list it.

    python3 perfboard.py bell-perfboard.toml <automatic_christmas_bell>/variants/tht

Reads the plan ([perfboard], [place], [near], [[wire]]), the kind beside it (pad-per-hole.toml) and the project's
hardware/graph.toml and parts entries. Builds the nets the plan makes – pins in holes, solder bridges between
neighbouring holes on the bottom, insulated wires on top joining their two ends – and compares them with the graph's;
checks the grid, the bodies, the wires, the mounting holes and the hand-over's `near`. Writes <plan>.top.svg,
<plan>.bottom.svg (the bottom side in the same orientation as the top, decision 12 of the concept) and <plan>.build.md
(findings, build list, test list for the multimeter, material) beside the plan.

Standard library only (Python 3.11+). A sketch for the concept, not edakit code; edakit's pytest does not collect it.
"""
import argparse
import html
import json
import math
import re
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------------------------------------------------
# Footprints by the parts entry's `footprint`: pads in mm at rot 0 (pin 1 at 0,0; x to the right, y down, seen from
# the top) and the bodies. A stand-in for footprint_data and the library cache (handbook 4.2), which the bell's THT
# entries do not carry. Axial parts take their pad 2 from the plan's span.


def _nano_pads():
    pads = {str(k): (0.0, (k - 1) * 2.54) for k in range(1, 16)}             # TX … D12 down the left side
    pads.update({str(k): (15.24, (30 - k) * 2.54) for k in range(16, 31)})    # D13 … VIN up the right side
    return pads


AXIAL = {  # body length, diameter (the parts entries' package lines)
    "RES-TH_BD2.2-L6.5-P10.50-D0.6": (6.5, 2.2),
    "RES-TH_BD2.5-L6.5-P10.50-D0.6": (6.5, 2.2),
    "RES-TH_BD4.0-L11.5-P15.50-D0.7": (11.5, 4.5),
}
FOOTPRINTS = {
    "COMM-TH_L43.2-W17.8-P2.54_ATMEGA328P": {
        "pads": _nano_pads(),
        "bodies": [("rect", (0.0, 17.78), (2.54, 38.1)), ("rect", (15.24, 17.78), (2.54, 38.1))],   # the sockets
        "raised": ("rect", (7.62, 17.78), (17.8, 43.2)),       # the module, 8.5 mm up on its sockets
        "usb": ("rect", (7.62, 36.4), (7.7, 9.0)),             # at the end of pins 15/16, 1.5 mm past the module
    },
    "LED-TH_BD5.9-P2.54-FD-RED": {"pads": {"1": (0, 0), "2": (2.54, 0)}, "bodies": [("circle", (1.27, 0), 5.9)]},
    "LED-TH_BD5.9-P2.54-RD_YELLOW": {"pads": {"1": (0, 0), "2": (2.54, 0)}, "bodies": [("circle", (1.27, 0), 5.9)]},
    "LED-TH_BD5.0-P2.54-FD": {"pads": {"1": (0, 0), "2": (2.54, 0)}, "bodies": [("circle", (1.27, 0), 5.8)]},
    "CAP-TH_BD10.0-P5.00-D0.6-FD": {"pads": {"1": (0, 0), "2": (5.0, 0)}, "bodies": [("circle", (2.5, 0), 10.0)]},
    "HDR-TH_3P-P2.54-V-M_PZ254V-11-03P": {"pads": {"1": (0, 0), "2": (2.54, 0), "3": (5.08, 0)},
                                          "bodies": [("rect", (2.54, 0), (7.62, 2.54))]},
    "KEY-TH_4P-L6.0-W6.0-P4.50-LS6.50": {"pads": {"1": (0, 0), "2": (6.5, 0), "3": (0, 4.5), "4": (6.5, 4.5)},
                                         "bodies": [("rect", (3.25, 2.25), (6.0, 6.0))]},
}
MOUNT_DRILL, MOUNT_KEEP = 3.2, 3.0          # M3: drilled hole; radius kept free of bodies (nut and washer)

NET_COLOURS = {
    "GND": "#2b2b2b", "+5V": "#d62728", "SERVO": "#17a2b8", "BTN_START": "#f28e2b", "BTN_RESET": "#8e5bc9",
    "LED_G1": "#2e8b2e", "LED_G1_A": "#8fd18a", "LED_G2": "#1b7f6f", "LED_G2_A": "#79cbbd",
    "LED_Y1": "#b08d00", "LED_Y1_A": "#e8d36a", "LED_Y2": "#a0671a", "LED_Y2_A": "#dfb57a",
    "LED_R": "#b0124d", "LED_R_A": "#f08fb4",
}
WIRE_COLOURS = {"orange": "#f28e2b", "violet": "#8e5bc9", "red": "#d62728", "black": "#2b2b2b", "blue": "#1f77b4",
                "green": "#2ca02c", "yellow": "#e6c200", "white": "#f4f4f4"}
LED_FILL = {"red": "#e0302f", "yellow": "#f2c200", "green": "#36b04a"}

# ---------------------------------------------------------------------------------------------------------------------
# Holes


def col_name(c):
    return chr(65 + c) if c < 26 else chr(64 + c // 26) + chr(65 + c % 26)


def parse_hole(name):
    m = re.fullmatch(r"([A-Z]+)(\d+)", name)
    if not m:
        raise SystemExit(f"not a hole: {name!r}")
    letters, row = m.groups()
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - 64)
    return col - 1, int(row)


def hole_name(h):
    return f"{col_name(h[0])}{h[1]}"


def rot(p, deg):
    x, y = p
    return {0: (x, y), 90: (y, -x), 180: (-x, -y), 270: (-y, x)}[deg % 360]


# ---------------------------------------------------------------------------------------------------------------------
# The project: graph and parts


def load_project(root):
    graph = tomllib.loads((root / "hardware/graph.toml").read_text())
    parts = {}
    for d, comp in graph["components"].items():
        entry = json.loads((root / "hardware/parts" / f"{comp['lcsc']}.json").read_text())
        parts[d] = {"comp": comp, "entry": entry}
    return graph, parts


def resolve(parts, ref):
    d, _, p = ref.partition(".")
    pins = parts[d]["entry"]["pins"]
    if p in pins:
        return d, [p]
    for key in ("name", "role"):
        hit = [n for n, v in pins.items() if v.get(key) == p]
        if hit:
            return d, hit
    raise SystemExit(f"{ref}: no such pin in {parts[d]['comp']['lcsc']}")


def joined_inside(entry):
    """Pins the part joins itself: the same name (a module's two GND), or the same role on a button."""
    groups = defaultdict(list)
    for n, v in entry["pins"].items():
        groups[("name", v["name"])].append(n)
        if entry.get("kind") == "button":
            groups[("role", v.get("role"))].append(n)
    return [g for g in groups.values() if len(g) > 1]


# ---------------------------------------------------------------------------------------------------------------------
# Placement


class Part:
    def __init__(self, d, spec, info, pitch, tol):
        self.d, self.spec, self.entry, self.comp = d, spec, info["entry"], info["comp"]
        self.rot = spec.get("rot", 0)
        fp_name = self.entry["footprint"]
        self.anchor = parse_hole(spec["at"])
        if fp_name in AXIAL:
            length, dia = AXIAL[fp_name]
            span = spec["span"]
            fp = {"pads": {"1": (0, 0), "2": (span * pitch, 0)},
                  "bodies": [("rect", (span * pitch / 2, 0), (length, dia))]}
            self.axial = (length, dia, span)
        else:
            fp = FOOTPRINTS[fp_name]
            self.axial = None
        self.fp = fp
        exact = {n: rot(p, self.rot) for n, p in fp["pads"].items()}
        grid = {n: (round(x / pitch), round(y / pitch)) for n, (x, y) in exact.items()}
        self.holes = {n: (self.anchor[0] + g[0], self.anchor[1] + g[1]) for n, g in grid.items()}
        cx = sum(x for x, _ in exact.values()) / len(exact)
        cy = sum(y for _, y in exact.values()) / len(exact)
        gx = sum(g[0] for g in grid.values()) * pitch / len(grid)
        gy = sum(g[1] for g in grid.values()) * pitch / len(grid)
        self.bend = max(math.hypot((x - cx) - (grid[n][0] * pitch - gx), (y - cy) - (grid[n][1] * pitch - gy))
                        for n, (x, y) in exact.items())
        # board position of the anchor hole, and the shift that centres the footprint on its holes
        self.origin = ((self.anchor[0] + 0.5) * pitch + (gx - cx), (self.anchor[1] - 0.5) * pitch + (gy - cy))

    def place(self, p):
        x, y = rot(p, self.rot)
        return self.origin[0] + x, self.origin[1] + y

    def shapes(self, which="bodies"):
        out = []
        items = self.fp.get(which, [])
        if which != "bodies":
            items = [items] if items else []
        for kind, c, size in items:
            cx, cy = self.place(c)
            if kind == "circle":
                out.append(("circle", (cx, cy), size))
            else:
                w, h = size if self.rot % 180 == 0 else (size[1], size[0])
                out.append(("rect", (cx, cy), (w, h)))
        return out


def overlap(a, b, eps=0.05):
    (ka, ca, sa), (kb, cb, sb) = a, b
    if ka == "circle" and kb == "circle":
        return math.dist(ca, cb) < sa / 2 + sb / 2 - eps
    if ka == "rect" and kb == "rect":
        return abs(ca[0] - cb[0]) < (sa[0] + sb[0]) / 2 - eps and abs(ca[1] - cb[1]) < (sa[1] + sb[1]) / 2 - eps
    if ka == "rect":
        (ka, ca, sa), (kb, cb, sb) = b, a
    nx = min(max(ca[0], cb[0] - sb[0] / 2), cb[0] + sb[0] / 2)
    ny = min(max(ca[1], cb[1] - sb[1] / 2), cb[1] + sb[1] / 2)
    return math.dist(ca, (nx, ny)) < sa / 2 - eps


def inside(pt, shape, shrink=0.3):
    kind, c, s = shape
    if kind == "circle":
        return math.dist(pt, c) < s / 2 - shrink
    return abs(pt[0] - c[0]) < s[0] / 2 - shrink and abs(pt[1] - c[1]) < s[1] / 2 - shrink


# ---------------------------------------------------------------------------------------------------------------------
# The check


class UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def expand(path, straight):
    """The holes a wire touches: every hole along a road of bridges, only the ends of an insulated wire."""
    pts = [parse_hole(h) for h in path]
    if not straight:
        return [pts[0], pts[-1]], []          # the points between are bends above the board, not holes
    holes, bad = [pts[0]], []
    for (c1, r1), (c2, r2) in zip(pts, pts[1:]):
        if c1 != c2 and r1 != r2:
            bad.append(f"{hole_name((c1, r1))}–{hole_name((c2, r2))}")
            continue
        n = max(abs(c2 - c1), abs(r2 - r1))
        for i in range(1, n + 1):
            holes.append((c1 + (c2 - c1) * i // n, r1 + (r2 - r1) * i // n))
    return holes, bad


def box(p):
    """The bounding box of a part's bodies on the board: x0, y0, x1, y1."""
    xs, ys = [], []
    for kind_s, (cx, cy), size in p.shapes():
        w, h = (size, size) if kind_s == "circle" else size
        xs += [cx - w / 2, cx + w / 2]
        ys += [cy - h / 2, cy + h / 2]
    return min(xs), min(ys), max(xs), max(ys)


def box_gap(a, b):
    return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3], 0)      # as edakit/pcb.py


def check(plan, kind, graph, parts):
    pitch = kind["pitch_mm"]
    tol = kind["tolerance"]
    cols, rows = plan["perfboard"]["holes"]
    findings = []

    def f(sev, code, text):
        findings.append((sev, code, text))

    placed = {}
    for d, spec in plan["place"].items():
        if d not in parts:
            f("error", "PERF.unknown", f"{d} is placed but not in the graph")
            continue
        placed[d] = Part(d, spec, parts[d], pitch, tol)
    for d in parts:
        if d not in placed:
            f("error", "PERF.unplaced", f"{d} is in the graph but has no place")

    # pins in holes
    pin_at = {}
    for d, p in placed.items():
        for n, h in p.holes.items():
            if not (0 <= h[0] < cols and 1 <= h[1] <= rows):
                f("error", "PERF.offboard", f"{d}.{n} would sit in {hole_name(h)}, off the board")
            if h in pin_at:
                f("error", "PERF.twopins", f"{hole_name(h)} holds {pin_at[h]} and {d}.{n}")
            pin_at[h] = f"{d}.{n}"

    # mounting holes
    keep = {}
    for m in plan["perfboard"].get("mounting", []):
        mc, mr = parse_hole(m)
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                keep[(mc + dc, mr + dr)] = m
        centre = ((mc + 0.5) * pitch, (mr - 0.5) * pitch)
        for d, p in placed.items():
            for s in p.shapes():
                if overlap(("circle", centre, 2 * MOUNT_KEEP), s):
                    f("error", "PERF.mount", f"{d}'s body reaches into the nut of mounting hole {m}")
    for h, who in pin_at.items():
        if h in keep:
            f("error", "PERF.mount", f"{who} in {hole_name(h)}, beside mounting hole {keep[h]}")

    # grid and bodies
    for d, p in placed.items():
        if p.axial:
            length, dia, span = p.axial
            need = length + 2 * tol["axial_bend_mm"]
            if span * pitch < need:
                f("error", "PERF.span", f"{d}: span {span} holes = {span * pitch:.2f} mm, body and bends need "
                                        f"{need:.1f} mm")
        elif p.bend > tol["lead_bend_mm"]:
            f("error", "PERF.grid", f"{d}: leads {p.bend:.2f} mm off the grid, more than {tol['lead_bend_mm']} mm")
        elif p.bend > 0.05:
            f("note", "PERF.grid", f"{d}: leads bent by {p.bend:.2f} mm into the 2.54 mm grid "
                                   f"(allowed {tol['lead_bend_mm']} mm)")
    ds = sorted(placed)
    for i, a in enumerate(ds):
        for b in ds[i + 1:]:
            if any(overlap(sa, sb) for sa in placed[a].shapes() for sb in placed[b].shapes()):
                f("error", "PERF.body", f"the bodies of {a} and {b} overlap")

    def under_body(h, own=None):
        pt = ((h[0] + 0.5) * pitch, (h[1] - 0.5) * pitch)
        return [d for d, p in placed.items() if d != own and any(inside(pt, s) for s in p.shapes())]

    for h, who in pin_at.items():
        for d in under_body(h, who.split(".")[0]):
            f("error", "PERF.body", f"{d}'s body covers the lead {who} in {hole_name(h)}")

    # wires: on the bottom only bridges between neighbouring holes, everything else an insulated wire on top
    uf, ufb = UF(), UF()          # ufb: the board alone, without what a plugged-in module joins inside
    bottom_at, wires = {}, []
    for i, w in enumerate(plan.get("wire", [])):
        side = w.get("side", "bottom")
        kind_w = w.get("kind", "bridge" if side == "bottom" else "wire")
        if side == "bottom" and kind_w != "bridge":
            f("error", "PERF.wire", f"{w['net']}: {' '.join(w['path'])} – on the bottom only bridges between "
                                    f"neighbouring holes; a longer connection is a wire on top")
        if side == "top" and kind_w == "bridge":
            f("error", "PERF.wire", f"{w['net']}: a bridge is soldered on the bottom, not on top")
        holes, bad = expand(w["path"], straight=kind_w == "bridge")
        for seg in bad:
            f("error", "PERF.wire", f"{w['net']}: the bridges {seg} do not run along a row or a column")
        for h in holes:
            if not (0 <= h[0] < cols and 1 <= h[1] <= rows):
                f("error", "PERF.offboard", f"{w['net']}: {hole_name(h)} is off the board")
            if h in keep:
                f("error", "PERF.mount", f"{w['net']}: {hole_name(h)} is beside mounting hole {keep[h]}")
            uf.union(("w", i), ("h", h))
            ufb.union(("w", i), ("h", h))
        if kind_w == "wire":
            for h in holes:
                if h in pin_at:
                    f("error", "PERF.twopins", f"{w['net']}: the wire ends in {hole_name(h)}, where {pin_at[h]} "
                                               f"already is – it goes into a free hole beside it, with a bridge")
                for d in under_body(h):
                    f("error", "PERF.body", f"{w['net']}: the wire's end in {hole_name(h)} lies under {d}")
        else:
            for h in holes:
                bottom_at.setdefault(h, w["net"])
        wires.append({**w, "kind": kind_w, "holes": holes})

    # bridges run straight: no corner within a row of bridges, and none where two rows end in the same empty hole
    run_ends, run_middles = defaultdict(set), set()
    wire_end_holes = {h for w in wires if w["kind"] == "wire" for h in (w["holes"][0], w["holes"][-1])}
    for w in wires:
        if w["kind"] != "bridge" or len(w["holes"]) < 2:
            continue
        pts = [parse_hole(h) for h in w["path"]]
        axes = ["row" if a[1] == b[1] else "column" for a, b in zip(pts, pts[1:])]
        corners = [hole_name(pts[i + 1]) for i in range(len(axes) - 1) if axes[i] != axes[i + 1]]
        if corners:
            f("error", "PERF.corner", f"{w['net']}: the bridges {' … '.join(w['path'])} turn at "
                                      f"{', '.join(corners)} – bridges run straight; take a wire on top")
        for h in (w["holes"][0], w["holes"][-1]):
            run_ends[h].add(axes[0] if h == w["holes"][0] else axes[-1])
        run_middles.update(w["holes"][1:-1])
    for h, axes in run_ends.items():
        if len(axes) > 1 and h not in pin_at and h not in wire_end_holes and h not in run_middles:
            f("error", "PERF.corner", f"bridges turn at the empty hole {hole_name(h)} – bridges run straight; "
                                      f"take a wire on top")

    # nets the plan makes against the graph's
    net_of = {}
    for net, spec in graph["nets"].items():
        for ref in spec["pins"]:
            d, ns = resolve(parts, ref)
            for n in ns:
                net_of[(d, n)] = net
    for d, p in placed.items():
        for n, h in p.holes.items():
            uf.union(("p", d, n), ("h", h))
            ufb.union(("p", d, n), ("h", h))
        for g in joined_inside(p.entry):
            for n in g[1:]:
                uf.union(("p", d, g[0]), ("p", d, n))
                if p.entry.get("kind") != "module":
                    ufb.union(("p", d, g[0]), ("p", d, n))
    comp_nets, net_comps = defaultdict(set), defaultdict(set)
    comp_pins = defaultdict(lambda: defaultdict(list))
    for d, p in placed.items():
        for n in p.holes:
            root = uf.find(("p", d, n))
            net = net_of.get((d, n))
            if net is None:
                net = f"(free {d}.{p.entry['pins'][n]['name']})"
            comp_nets[root].add(net)
            net_comps[net].add(root)
            comp_pins[root][net].append(f"{d}.{pin_label(p.entry, n)} in {hole_name(p.holes[n])}")

    def pins(ps):
        return f"{len(ps)} pins" if len(ps) > 3 else ", ".join(sorted(ps))

    for root, nets in comp_nets.items():
        if len(nets) > 1:
            f("error", "PERF.short", " and ".join(f"{net} ({pins(comp_pins[root][net])})" for net in sorted(nets))
              + " in one piece of copper")
    for net in graph["nets"]:
        if len(net_comps[net]) > 1:
            f("error", "PERF.open", f"{net} is open between " +
              " | ".join(sorted(pins(comp_pins[root][net]) for root in net_comps[net])))
    for i, w in enumerate(wires):
        nets = comp_nets.get(uf.find(("w", i)), set())
        if nets and w["net"] not in nets:
            f("error", "PERF.label", f"{' '.join(w['path'])} is labelled {w['net']} but joins "
                                     f"{', '.join(sorted(nets))}")
    # where two nets meet: a hole whose bridges, wire ends and lead belong to different nets
    meet = defaultdict(list)
    for w in wires:
        if w["kind"] == "bridge":
            what = ("bridge " + "–".join(w["path"])) if len(w["holes"]) == 2 else "bridges " + " … ".join(w["path"])
        else:
            what = "wire " + "–".join([w["path"][0], w["path"][-1]])
        for h in w["holes"]:
            meet[h].append((w["net"], f"{w['net']} {what}"))
    for h, who in pin_at.items():
        d, n = who.split(".")
        if h in meet and (d, n) in net_of:
            meet[h].append((net_of[(d, n)], f"{d}.{pin_label(placed[d].entry, n)} ({net_of[(d, n)]})"))
    for h, items in sorted(meet.items(), key=lambda kv: kv[0][::-1]):
        if len({net for net, _ in items}) > 1:
            f("error", "PERF.meet", f"{hole_name(h)} joins " + " with ".join(dict.fromkeys(t for _, t in items)))
    for net in graph["nets"]:
        if len(net_comps[net]) == 1:
            roots = defaultdict(list)
            for (d, n), nn in net_of.items():
                if nn == net and d in placed:
                    roots[ufb.find(("p", d, n))].append((d, n))
            if len(roots) > 1:
                main = max(roots.values(), key=len)
                for members in roots.values():
                    if members is not main:
                        f("note", "PERF.inside", f"{net}: " + ", ".join(sorted([
                            f"{d}.{pin_label(placed[d].entry, n)} in {hole_name(placed[d].holes[n])}"
                            for d, n in members])) + " join the rest only inside the plugged-in module")

    # the hand-over's near: the gap between the bodies' boxes, as on a PCB
    near_mm = plan.get("near_mm", 6)
    for a, b in plan.get("near", {}).items():
        if a in placed and b in placed:
            gap = box_gap(box(placed[a]), box(placed[b]))
            if gap > near_mm:
                f("warning", "PERF.near", f"{a} is {gap:.1f} mm from {b}, more than {near_mm} mm")

    # parts under the raised module
    for d, p in placed.items():
        for s in p.shapes("raised"):
            for e, q in placed.items():
                if e != d and any(overlap(s, t) for t in q.shapes()):
                    f("note", "PERF.under", f"{e} sits under {d} (8.5 mm sockets)")

    return {"findings": findings, "placed": placed, "wires": wires, "pin_at": pin_at, "net_of": net_of,
            "uf": uf, "ufb": ufb, "bottom_at": bottom_at, "keep": keep}


def pin_label(entry, n):
    """A pin as the builder knows it: anode/cathode, plus/minus by role, else the entry's name."""
    role = entry["pins"][n].get("role")
    return role if role in ("anode", "cathode", "plus", "minus") else entry["pins"][n]["name"]


# ---------------------------------------------------------------------------------------------------------------------
# Drawing


class Svg:
    def __init__(self, w, h, scale=9):
        self.w, self.h = w, h
        self.out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * scale:.0f}" height="{h * scale:.0f}" '
                    f'viewBox="0 0 {w:.2f} {h:.2f}" font-family="DejaVu Sans, Arial, sans-serif">',
                    f'<rect width="{w:.2f}" height="{h:.2f}" fill="#ffffff"/>']

    def add(self, s):
        self.out.append(s)

    def text(self, x, y, s, size=1.4, fill="#222", anchor="middle", weight="normal", rotate=0, halo=False):
        t = f' transform="rotate({rotate} {x:.2f} {y:.2f})"' if rotate else ""
        h = ' paint-order="stroke" stroke="#ffffff" stroke-width="0.35"' if halo else ""
        self.add(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
                 f'dominant-baseline="central" font-weight="{weight}"{t}{h}>{html.escape(s)}</text>')

    def done(self):
        return "\n".join(self.out + ["</svg>"]) + "\n"


def runs(holes):
    """Unit steps of a bridge path: each a bridge between two neighbouring holes."""
    return list(zip(holes, holes[1:]))


def draw(plan, kind, res, parts, title, bottom):
    pitch = kind["pitch_mm"]
    cols, rows = plan["perfboard"]["holes"]
    W, H = cols * pitch, rows * pitch
    ml, mt, mr, mb = 8, 17, 8, 19
    svg = Svg(W + ml + mr, H + mt + mb)

    def X(x):
        return ml + x

    def Y(y):
        return mt + y

    def hc(h):
        return (h[0] + 0.5) * pitch, (h[1] - 0.5) * pitch

    side = ("bottom side – seen through the board from above, in the same orientation as the top view"
            if bottom else "top view – component side, A1 at the top left")
    svg.text(ml, 4.5, title, size=2.6, anchor="start", weight="bold")
    svg.text(ml, 8.4, side, size=1.9, anchor="start", fill="#444")
    svg.text(ml, 11.4, "Prototype of docs/concepts/new/perfboard-layout.md – drawn by perfboard.py, not by edakit",
             size=1.3, anchor="start", fill="#777")
    svg.add(f'<rect x="{ml:.2f}" y="{mt:.2f}" width="{W:.2f}" height="{H:.2f}" rx="0.8" '
            f'fill="{"#d2b886" if bottom else "#dcc596"}" stroke="#8a7146" stroke-width="0.3"/>')
    for c in range(cols):
        x = X((c + 0.5) * pitch)
        svg.text(x, mt - 1.4, col_name(c), size=1.05, fill="#555")
        svg.text(x, mt + H + 1.4, col_name(c), size=1.05, fill="#555")
    for r in range(1, rows + 1):
        y = Y((r - 0.5) * pitch)
        svg.text(ml - 1.6, y, str(r), size=1.05, fill="#555")
        svg.text(ml + W + 1.6, y, str(r), size=1.05, fill="#555")

    placed, wires, pin_at = res["placed"], res["wires"], res["pin_at"]
    mounts = {parse_hole(m) for m in plan["perfboard"].get("mounting", [])}
    wire_ends = {}
    for w in wires:
        if w["kind"] == "wire":
            for h in (w["holes"][0], w["holes"][-1]):
                wire_ends[h] = WIRE_COLOURS.get(w.get("color", ""), NET_COLOURS.get(w["net"], "#555"))

    # empty holes, faint
    for c in range(cols):
        for r in range(1, rows + 1):
            if (c, r) in mounts or (bottom and (c, r) in pin_at):
                continue
            x, y = hc((c, r))
            if bottom:
                svg.add(f'<circle cx="{X(x):.2f}" cy="{Y(y):.2f}" r="0.78" fill="#e4d8c0" stroke="#b9a684" '
                        f'stroke-width="0.1"/>')
                svg.add(f'<circle cx="{X(x):.2f}" cy="{Y(y):.2f}" r="0.36" fill="#8a7654"/>')
            else:
                svg.add(f'<circle cx="{X(x):.2f}" cy="{Y(y):.2f}" r="0.48" fill="#7a6545"/>')
    for (c, r) in mounts:
        x, y = hc((c, r))
        svg.add(f'<circle cx="{X(x):.2f}" cy="{Y(y):.2f}" r="{MOUNT_KEEP}" fill="none" stroke="#999" '
                f'stroke-width="0.15" stroke-dasharray="0.6 0.4"/>')
        svg.add(f'<circle cx="{X(x):.2f}" cy="{Y(y):.2f}" r="{MOUNT_DRILL / 2}" fill="#ffffff" stroke="#777" '
                f'stroke-width="0.2"/>')

    def shape_svg(s, fill, stroke, width=0.2, dash=None, opacity=1.0, rx=0.4):
        kind_s, (cx, cy), size = s
        d = f' stroke-dasharray="{dash}"' if dash else ""
        if kind_s == "circle":
            return (f'<circle cx="{X(cx):.2f}" cy="{Y(cy):.2f}" r="{size / 2:.2f}" fill="{fill}" stroke="{stroke}" '
                    f'stroke-width="{width}" fill-opacity="{opacity}"{d}/>')
        w, h = size
        return (f'<rect x="{X(cx) - w / 2:.2f}" y="{Y(cy) - h / 2:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{width}" fill-opacity="{opacity}"{d}/>')

    if bottom:
        # part outlines for orientation, the bridges, the soldered leads on top of them, the wires coming through
        for d, p in placed.items():
            for s in p.shapes():
                svg.add(shape_svg(s, "none", "#8a7550", width=0.15, dash="0.5 0.35"))
        for h, who in pin_at.items():
            x, y = hc(h)
            svg.add(f'<circle cx="{X(x):.2f}" cy="{Y(y):.2f}" r="1.02" fill="#5c6269" stroke="#16181b" '
                    f'stroke-width="0.28"/>')
            svg.add(f'<circle cx="{X(x):.2f}" cy="{Y(y):.2f}" r="0.3" fill="#d9dde1"/>')
        for w in wires:
            if w["kind"] != "bridge":
                continue
            col = NET_COLOURS.get(w["net"], "#555")
            for a, b in runs(w["holes"]):
                (x1, y1), (x2, y2) = hc(a), hc(b)
                for colour, width in (("#2a2116", 1.3), (col, 0.95)):
                    svg.add(f'<line x1="{X(x1):.2f}" y1="{Y(y1):.2f}" x2="{X(x2):.2f}" y2="{Y(y2):.2f}" '
                            f'stroke="{colour}" stroke-width="{width}" stroke-linecap="round"/>')
        for h, col in wire_ends.items():
            x, y = hc(h)
            svg.add(f'<circle cx="{X(x):.2f}" cy="{Y(y):.2f}" r="0.62" fill="#ffffff" stroke="{col}" '
                    f'stroke-width="0.42"/>')
        for w in wires:
            if w["kind"] == "bridge" and len(w["holes"]) > 4:
                best = max(zip(w["path"], w["path"][1:]), key=lambda s: math.dist(parse_hole(s[0]), parse_hole(s[1])))
                (x1, y1), (x2, y2) = hc(parse_hole(best[0])), hc(parse_hole(best[1]))
                vertical = abs(x1 - x2) < 0.01
                x, y = (x1 + x2) / 2, (y1 + y2) / 2
                x, y = (x + 1.35, y) if vertical else (x + 1.27, y - 1.45)
                svg.text(X(x), Y(y), w["net"], size=0.95, fill=NET_COLOURS.get(w["net"], "#333"),
                         rotate=-90 if vertical else 0, halo=True)
        for d, p in placed.items():
            cx, cy = p.shapes()[0][1]
            if p.fp.get("raised"):
                cx = p.shapes("raised")[0][1][0] + 9
                cy = (p.place(p.fp["pads"]["1"])[1] + p.place(p.fp["pads"]["16"])[1]) / 2 + 1.27
            svg.text(X(cx), Y(cy), d, size=1.25, fill="#4d3f27", halo=True)
    else:
        for d, p in placed.items():
            draw_part_top(svg, d, p, parts[d], X, Y, shape_svg)
        for w in wires:
            if w["kind"] != "wire":
                continue
            col = WIRE_COLOURS.get(w.get("color", ""), NET_COLOURS.get(w["net"], "#555"))
            pts = " ".join(f"{X(hc(parse_hole(h))[0]):.2f},{Y(hc(parse_hole(h))[1]):.2f}" for h in w["path"])
            svg.add(f'<polyline points="{pts}" fill="none" stroke="#333" stroke-width="1.05" stroke-linecap="round" '
                    f'stroke-linejoin="round" stroke-opacity="0.55"/>')
            svg.add(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="0.8" stroke-linecap="round" '
                    f'stroke-linejoin="round"/>')
            for h in (w["path"][0], w["path"][-1]):
                x, y = hc(parse_hole(h))
                svg.add(f'<circle cx="{X(x):.2f}" cy="{Y(y):.2f}" r="0.55" fill="{col}" stroke="#333" '
                        f'stroke-width="0.15"/>')
        for d, p in placed.items():
            if p.fp.get("raised"):
                draw_module_raised(svg, d, p, parts[d], X, Y, shape_svg)

    # legend
    ly = mt + H + 4.2
    if bottom:
        x, y = ml, ly
        svg.add(f'<circle cx="{x + 1:.2f}" cy="{y:.2f}" r="1.02" fill="#5c6269" stroke="#16181b" '
                f'stroke-width="0.28"/><circle cx="{x + 1:.2f}" cy="{y:.2f}" r="0.3" fill="#d9dde1"/>')
        svg.text(x + 2.6, y, "soldered lead", size=1.3, anchor="start")
        svg.add(f'<circle cx="{x + 19:.2f}" cy="{y:.2f}" r="0.62" fill="#ffffff" stroke="#f28e2b" '
                f'stroke-width="0.42"/>')
        svg.text(x + 20.4, y, "wire from the top", size=1.3, anchor="start")
        svg.add(f'<circle cx="{x + 40:.2f}" cy="{y:.2f}" r="0.78" fill="#e4d8c0" stroke="#b9a684" stroke-width="0.1"/>'
                f'<circle cx="{x + 40:.2f}" cy="{y:.2f}" r="0.36" fill="#8a7654"/>')
        svg.text(x + 41.4, y, "empty hole", size=1.3, anchor="start")
        svg.add(f'<line x1="{x + 56:.2f}" y1="{y:.2f}" x2="{x + 59:.2f}" y2="{y:.2f}" stroke="#2a2116" '
                f'stroke-width="1.3" stroke-linecap="round"/><line x1="{x + 56:.2f}" y1="{y:.2f}" x2="{x + 59:.2f}" '
                f'y2="{y:.2f}" stroke="#f28e2b" stroke-width="0.95" stroke-linecap="round"/>')
        svg.text(x + 60, y, "solder bridge, coloured by net",
                 size=1.3, anchor="start", fill="#444")
        used = []
        for w in wires:
            if w["kind"] == "bridge" and w["net"] not in used:
                used.append(w["net"])
        x, y = ml, ly + 3.3
        for net in used:
            svg.add(f'<line x1="{x:.2f}" y1="{y:.2f}" x2="{x + 3:.2f}" y2="{y:.2f}" stroke="{NET_COLOURS.get(net)}" '
                    f'stroke-width="1.3" stroke-linecap="round"/>')
            svg.text(x + 3.8, y, net, size=1.3, anchor="start")
            x += 14
            if x > ml + W - 10:
                x, y = ml, y + 2.8
    else:
        svg.text(ml, ly, "Parts as seen from above; insulated wires in their colour, entering the board at the dots. "
                         "The bridges are in the bottom view.", size=1.3, anchor="start", fill="#444")
        x, y = ml, ly + 3.2
        for w in wires:
            if w["kind"] == "wire":
                col = WIRE_COLOURS.get(w.get("color", ""), "#555")
                svg.add(f'<line x1="{x:.2f}" y1="{y:.2f}" x2="{x + 3:.2f}" y2="{y:.2f}" stroke="{col}" '
                        f'stroke-width="0.8" stroke-linecap="round"/>')
                svg.text(x + 3.8, y, f"{w['net']} {w['path'][0]}–{w['path'][-1]}", size=1.2, anchor="start")
                x += 23
                if x > ml + W - 15:
                    x, y = ml, y + 2.6
        svg.text(ml, y + 3, "LED: flat side = cathode, + = anode (long lead).  C1: stripe = minus.  "
                            "J1: 1 GND (brown), 2 +5V, 3 signal.", size=1.3, anchor="start", fill="#444")
        svg.text(ml, y + 5.4, "Dashed circles: nut of the M3 mounting holes.", size=1.3, anchor="start",
                 fill="#444")
    return svg.done()


def draw_part_top(svg, d, p, info, X, Y, shape_svg):
    entry, comp = info["entry"], info["comp"]
    kind = entry.get("kind")
    holes = p.holes
    pitch = 2.54

    def hc(h):
        return X((h[0] + 0.5) * pitch), Y((h[1] - 0.5) * pitch)

    for n, h in holes.items():
        x, y = hc(h)
        svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.42" fill="#444"/>')
    if kind == "module":
        for s in p.shapes():
            svg.add(shape_svg(s, "#1e1e1e", "#000", rx=0.3))
        for n, h in holes.items():
            x, y = hc(h)
            svg.add(f'<rect x="{x - 0.45:.2f}" y="{y - 0.45:.2f}" width="0.9" height="0.9" fill="#d4af37"/>')
        return
    body = p.shapes()[0]
    (cx, cy) = body[1]
    if kind == "resistor":
        a, b = hc(holes["1"]), hc(holes["2"])
        svg.add(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="#9a9a9a" '
                f'stroke-width="0.45"/>')
        fill = "#5d86c4" if p.axial[1] > 3 else "#8fb3e6"
        svg.add(shape_svg(body, fill, "#3d5f91", rx=min(body[2]) / 2))
        vertical = abs(a[0] - b[0]) < 0.01
        svg.text(X(cx), Y(cy), f"{d} {comp.get('value', '')}", size=1.05 if p.axial[1] < 3 else 1.3,
                 fill="#10233f", rotate=-90 if vertical else 0)
    elif kind == "led":
        colour = entry.get("values", {}).get("color", "red")
        svg.add(shape_svg(body, LED_FILL.get(colour, "#ccc"), "#555", width=0.25, opacity=0.9))
        roles = {v["role"]: n for n, v in entry["pins"].items()}
        ka, kc = hc(holes[roles["anode"]]), hc(holes[roles["cathode"]])
        ux, uy = kc[0] - ka[0], kc[1] - ka[1]
        ln = math.hypot(ux, uy)
        ux, uy = ux / ln, uy / ln
        r = body[2] / 2
        mx, my = X(cx) + ux * r * 0.82, Y(cy) + uy * r * 0.82
        half = math.sqrt(r * r - (r * 0.82) ** 2)
        svg.add(f'<line x1="{mx - uy * half:.2f}" y1="{my + ux * half:.2f}" x2="{mx + uy * half:.2f}" '
                f'y2="{my - ux * half:.2f}" stroke="#222" stroke-width="0.35"/>')
        svg.text(ka[0] - ux * 1.25 + 1.4, ka[1] - uy * 1.25, "+", size=1.4, fill="#222", weight="bold")
        svg.text(X(cx), Y(cy), d, size=1.2, fill="#222", halo=True)
    elif kind == "capacitor":
        svg.add(shape_svg(body, "#2b4c7e", "#1a2f50", width=0.25))
        roles = {v["role"]: n for n, v in entry["pins"].items()}
        mp, mm = hc(holes[roles["plus"]]), hc(holes[roles["minus"]])
        ux, uy = mm[0] - mp[0], mm[1] - mp[1]
        ln = math.hypot(ux, uy)
        ux, uy = ux / ln, uy / ln
        r = body[2] / 2
        mx, my = X(cx) + ux * r * 0.78, Y(cy) + uy * r * 0.78
        half = math.sqrt(r * r - (r * 0.78) ** 2)
        svg.add(f'<line x1="{mx - uy * half:.2f}" y1="{my + ux * half:.2f}" x2="{mx + uy * half:.2f}" '
                f'y2="{my - ux * half:.2f}" stroke="#c9d6ea" stroke-width="1.6"/>')
        svg.text(mx, my, "−", size=1.6, fill="#1a2f50", weight="bold")
        svg.text(mp[0] - ux * 1.6, mp[1] - uy * 1.6, "+", size=1.6, fill="#ffffff", weight="bold")
        svg.text(X(cx) - ux * 1.5 - 2.2, Y(cy) - uy * 1.5, d, size=1.5, fill="#ffffff", weight="bold")
        svg.text(X(cx) - ux * 1.5 + 2.2, Y(cy) - uy * 1.5, "1000 µF", size=1.0, fill="#ffffff")
    elif kind == "button":
        svg.add(shape_svg(body, "#3a3a3a", "#111", rx=0.5))
        svg.add(f'<circle cx="{X(cx):.2f}" cy="{Y(cy):.2f}" r="1.75" fill="#7a7a7a" stroke="#222" '
                f'stroke-width="0.2"/>')
        svg.text(X(cx), Y(cy) - 2.4, d, size=1.1, fill="#ffffff", weight="bold")
        svg.text(X(cx), Y(cy) + 2.4, comp["label"].split()[0].lower(), size=0.95, fill="#ffffff")
    elif kind == "connector":
        svg.add(shape_svg(body, "#1e1e1e", "#000", rx=0.2))
        for n, h in holes.items():
            x, y = hc(h)
            svg.add(f'<rect x="{x - 0.32:.2f}" y="{y - 0.32:.2f}" width="0.64" height="0.64" fill="#d4af37"/>')
        names = {"1": "GND", "2": "+5V", "3": "sig"}
        vertical = len({h[0] for h in holes.values()}) == 1
        if vertical:
            for n, h in holes.items():
                x, y = hc(h)
                svg.text(x + 0.78, y, n, size=0.8, fill="#ffffff", weight="bold")
            last = max(holes.values(), key=lambda h: h[1])
            x, y = hc(last)
            svg.text(x + 1.27, y + 2.0, f"{d} servo", size=1.0, fill="#222", weight="bold", anchor="end", halo=True)
        else:
            for n, h in holes.items():
                x, y = hc(h)
                svg.text(x, y + 1.7, n, size=0.9, fill="#222", weight="bold")
            svg.text(X(cx), Y(cy) + 3.3, f"{d} servo", size=1.1, fill="#222", weight="bold", halo=True)
    else:
        svg.add(shape_svg(body, "#ccc", "#555"))
        svg.text(X(cx), Y(cy), d, size=1.2)


def draw_module_raised(svg, d, p, info, X, Y, shape_svg):
    """The module above its sockets: drawn after the wires that run beneath it, see-through."""
    entry, comp, holes, pitch = info["entry"], info["comp"], p.holes, 2.54

    def hc(h):
        return X((h[0] + 0.5) * pitch), Y((h[1] - 0.5) * pitch)

    usb = p.shapes("usb")[0]
    svg.add(shape_svg(usb, "#b8bcc2", "#6d737a", width=0.2, rx=0.3, opacity=0.8))
    svg.text(X(usb[1][0]) - 1.6, Y(usb[1][1]), "USB", size=1.2, fill="#333", rotate=-90)
    raised = p.shapes("raised")[0]
    svg.add(shape_svg(raised, "#1f5fa8", "#1f5fa8", width=0.25, dash="1 0.6", opacity=0.07, rx=0.8))
    top_row = min(h[1] for h in holes.values())
    for n, h in holes.items():
        x, y = hc(h)
        name = entry["pins"][n].get("print", entry["pins"][n]["name"]).replace("~", "")
        dy = 1.0 if h[1] == top_row else -1.0
        svg.text(x, y + dy * 0.9, name, size=0.78, fill="#1f5fa8", anchor="end" if dy > 0 else "start",
                 rotate=-90)
    rx, ry = raised[1]
    svg.text(X(rx) + 2, Y(ry) - 0.6, f"{d}  {comp['label'].split('(')[0].strip()}", size=1.6, fill="#1f5fa8",
             weight="bold", halo=True)
    svg.text(X(rx) + 2, Y(ry) + 1.6, "on two 1×15 female headers, 8.5 mm", size=1.1, fill="#1f5fa8", halo=True)


# ---------------------------------------------------------------------------------------------------------------------
# Lists


ORDER = [("resistor-low", "Resistors ¼ W, lying flat"), ("resistor-high", "Resistors 1 W, 1–2 mm above the board"),
         ("wire", "Insulated wires on top – each end through its hole, bent onto the pad below"),
         ("module", "Sockets"), ("button", "Buttons"), ("connector", "Pin header"), ("led", "LEDs"),
         ("capacitor", "Electrolytic capacitor"), ("bridge", "Solder bridges on the bottom, once the leads are in"),
         ("test", "Test"), ("plug", "Module")]


def lists(plan, kind, res, graph, parts):
    pitch = kind["pitch_mm"]
    placed, wires, pin_at, net_of = res["placed"], res["wires"], res["pin_at"], res["net_of"]
    out = []
    errors = [x for x in res["findings"] if x[0] == "error"]
    out.append("## Check\n")
    out.append(f"{len(errors)} errors, {len(res['findings']) - len(errors)} warnings and notes.\n")
    for sev, code, text in res["findings"]:
        out.append(f"- **{sev}** `{code}` – {text}")
    out.append("")

    def length(w):
        pts = [parse_hole(h) for h in w["path"]]
        return sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) * pitch

    out.append("## Build list – from low to high\n")
    groups = defaultdict(list)
    for w in wires:
        groups[w["kind"]].append(w)
    for d, p in sorted(placed.items(), key=lambda kv: (len(kv[0]), kv[0])):
        k = p.entry.get("kind")
        if k == "resistor":
            k = "resistor-high" if p.axial[1] > 3 else "resistor-low"
        groups[k].append(d)
    n_bridges = sum(len(w["holes"]) - 1 for w in groups["bridge"])
    wire_total = 0.0
    step = 0
    for key, head in ORDER:
        if key == "plug":
            step += 1
            out.append(f"{step}. **{head}:** plug U1 into its sockets, USB socket at the left edge.")
            continue
        if key == "test":
            step += 1
            out.append(f"{step}. **{head}:** the test list below, before U1 is plugged in.")
            continue
        items = groups.get(key)
        if not items:
            continue
        step += 1
        rows = []
        for it in items:
            if key == "bridge":
                n = len(it["holes"]) - 1
                path = "–".join(it["path"]) if n == 1 else " … ".join(it["path"])
                rows.append(f"{path} {it['net']}" + (f" ({n})" if n > 1 else ""))
            elif key == "wire":
                ln = length(it) + 16
                wire_total += ln
                rows.append(f"{it.get('color', '')} {it['path'][0]}–{it['path'][-1]} {it['net']} ({ln:.0f} mm)")
            else:
                p = placed[it]
                e = p.entry
                comp = parts[it]["comp"]
                roles = {v.get("role"): n for n, v in e["pins"].items()}
                if key == "led":
                    rows.append(f"{it} {e['values'].get('color', '')}: anode (long lead) in "
                                f"{hole_name(p.holes[roles['anode']])}, cathode (flat) in "
                                f"{hole_name(p.holes[roles['cathode']])}")
                elif key == "capacitor":
                    rows.append(f"{it} {comp['part']}: plus in {hole_name(p.holes[roles['plus']])}, minus (stripe) "
                                f"in {hole_name(p.holes[roles['minus']])}")
                elif key == "module":
                    hs = sorted(p.holes.values(), key=lambda h: (h[1], h[0]))
                    rows.append(f"two 1×15 female headers for {it}: {hole_name(hs[0])}–{hole_name(hs[14])} and "
                                f"{hole_name(hs[15])}–{hole_name(hs[29])}")
                elif key == "button":
                    rows.append(f"{it} ({comp['label'].lower()}): " +
                                ", ".join(f"{n} in {hole_name(h)}" for n, h in sorted(p.holes.items())))
                elif key == "connector":
                    rows.append(f"{it}: pin 1 (GND, brown) in {hole_name(p.holes['1'])}, pin 3 (signal) in "
                                f"{hole_name(p.holes['3'])}")
                else:
                    rows.append(f"{it} {comp.get('value', '')}: {hole_name(p.holes['1'])}–{hole_name(p.holes['2'])}")
        extra = f" – {n_bridges} in all" if key == "bridge" else ""
        out.append(f"{step}. **{head}{extra}:** " + "; ".join(rows) + ".")
    out.append("")

    out.append("## Test list – multimeter in beep mode, U1 not plugged in\n")
    between = [d for d in parts if {"+5V", "GND"} <= {net_of.get((d, n)) for n in parts[d]["entry"]["pins"]}]
    res_between = [d for d in between if parts[d]["entry"].get("kind") == "resistor"]
    caps = [d for d in between if parts[d]["entry"].get("kind") == "capacitor"]
    par = 1 / sum(1 / parts[d]["entry"]["values"]["value_ohm"] for d in res_between)
    j1 = placed.get("J1")
    a, b = (hole_name(j1.holes["2"]), hole_name(j1.holes["1"])) if j1 else ("+5V", "GND")
    out.append(f"1. **Before the first power-up:** +5V ({a}) to GND ({b}) reads about {par:.0f} Ω "
               f"({' ∥ '.join(res_between)}) once {', '.join(caps)} has charged – 0 Ω is a short.")
    out.append("2. **Each net beeps** from its first hole to every other:\n")
    out.append("| Net | From | To |")
    out.append("| --- | --- | --- |")
    for net in graph["nets"]:
        members = [(parse_hole(hole_name(placed[d].holes[n])), f"{d}.{pin_label(parts[d]['entry'], n)}")
                   for (d, n), nn in net_of.items() if nn == net and d in placed]
        groups_b = defaultdict(list)
        for h, who in members:
            groups_b[res["ufb"].find(("h", h))].append((h, who))
        parts_of_net = sorted((sorted(g, key=lambda m: (m[0][1], m[0][0])) for g in groups_b.values()),
                              key=len, reverse=True)
        for i, g in enumerate(parts_of_net):
            if len(g) < 2:
                continue
            label = net if len(parts_of_net) == 1 else f"{net} ({i + 1})"
            first = g[0]
            out.append(f"| {label} | {hole_name(first[0])} ({first[1]}) | " +
                       ", ".join(f"{hole_name(h)} ({w})" for h, w in g[1:]) + " |")
        if len(parts_of_net) > 1:
            out.append(f"| | | {net} (1) and (2) are joined inside U1: they beep once it is plugged in |")
    out.append("\n3. **Next to each bridge nothing else beeps** – the neighbouring pads of other nets:\n")
    copper = {}
    for h, who in pin_at.items():
        d, n = who.split(".")
        copper[h] = net_of.get((d, n), f"free {who}")
    for h, net in res["bottom_at"].items():
        copper.setdefault(h, net)
    pairs = set()
    for w in wires:
        if w["kind"] != "bridge":
            continue
        for h in w["holes"]:
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (h[0] + dc, h[1] + dr)
                other = copper.get(nb)
                if other and other != w["net"] and not other.startswith("free"):
                    pairs.add(tuple(sorted([(hole_name(h), w["net"]), (hole_name(nb), other)])))
    by_nets = defaultdict(list)
    for (h1, n1), (h2, n2) in sorted(pairs):
        by_nets[tuple(sorted([n1, n2]))].append(f"{h1}–{h2}")
    out.append("<details><summary>" + f"{len(pairs)} pairs of neighbouring holes" + "</summary>\n")
    out.append("| Nets | Holes |")
    out.append("| --- | --- |")
    for (n1, n2), hs in sorted(by_nets.items()):
        out.append(f"| {n1} / {n2} | {', '.join(hs)} |")
    out.append("\n</details>\n")

    cols, rows = plan["perfboard"]["holes"]
    out.append("## Material\n")
    out.append(f"- Perfboard, a pad per hole: {cols} × {rows} holes ({cols * pitch:.1f} × {rows * pitch:.1f} mm), "
               f"cut from a Euro board 160 × 100 mm; four holes drilled to {MOUNT_DRILL} mm.")
    out.append(f"- Insulated wire, solid core, in the plan's colours: {wire_total / 10:.0f} cm; solder for "
               f"{n_bridges} bridges.")
    out.append("- Two female headers 1×15 for U1 – already an `[[extra]]` of the bell's tht variant.")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("plan", type=Path)
    ap.add_argument("project", type=Path, help="the edakit project (folder with hardware/graph.toml)")
    args = ap.parse_args()
    plan = tomllib.loads(args.plan.read_text())
    kind = tomllib.loads((args.plan.parent / f"{plan['perfboard']['kind']}.toml").read_text())
    graph, parts = load_project(args.project)
    res = check(plan, kind, graph, parts)
    for sev, code, text in res["findings"]:
        print(f"{sev:7} {code:14} {text}")
    stem = args.plan.with_suffix("")
    title = f"{graph['name']} on a perfboard ({kind['name']})"
    stem.with_suffix(".top.svg").write_text(draw(plan, kind, res, parts, title, bottom=False))
    stem.with_suffix(".bottom.svg").write_text(draw(plan, kind, res, parts, title, bottom=True))
    head = (f"# {graph['name']} on a perfboard – check, build list, test list\n\n"
            f"Written by `perfboard.py` from [{args.plan.name}]({args.plan.name}) and the graph of "
            f"`{args.project.name}`; the drawings are [top]({stem.name}.top.svg) and "
            f"[bottom]({stem.name}.bottom.svg), both seen from above. A prototype – see the [README](README.md).\n\n")
    stem.with_suffix(".build.md").write_text(head + lists(plan, kind, res, graph, parts))
    errors = sum(1 for x in res["findings"] if x[0] == "error")
    print(f"{errors} errors, {len(res['findings']) - errors} warnings/notes; wrote {stem.name}.top.svg, "
          f"{stem.name}.bottom.svg, {stem.name}.build.md")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
