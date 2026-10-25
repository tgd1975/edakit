"""PCB: placement plan, footprint geometry, parts and nets from the schematic without dialogs, fixed parts, outline,
mounting and tooling holes, copper pours, EasyEDA's auto-layout.

    edakit pcb dump [--ref U1,J1]   footprint geometry -> <artifacts>/pcb_geometry_<board>.json
                                    (turns every measured part to 0°/TOP and leaves it there – run apply afterwards)
    edakit pcb plan                 offline: check the plan (overlaps, outline, holes, THT pins under parts of the
                                    other side, near), airline length, preview PNG, net classes from the simulation
    edakit pcb parts [--write]      parts of the board schematic -> PCB without the "Import Changes" dialog
    edakit pcb nets [--write]       pad nets in the PCB = graph
    edakit pcb apply                outline, holes, tooling holes, fixed parts (locked); all other parts unlocked
    edakit pcb autolayout           EasyEDA auto-layout of the unlocked parts, waits until positions are stable
    edakit pcb tooling              only the tooling holes again
    edakit pcb pour                 copper pours of [[boards.<b>.pours]] (replaces old ones, not filled)

Plan coordinates: mm, as seen from the board's `view` side (edakit.toml); `side` of a part is the EasyEDA side.
EasyEDA PCB unit: mil, y up. Footprint geometry is stored relative to the part origin at rotation 0 on TOP, so the
plan can be computed offline.
"""

from __future__ import annotations

import json
import math
import re
import time

from . import eda
from .config import BOTTOM, MIL_PER_MM, TOP
from .design import Design, natural_key
from .eda import MCPError, api, ensure_pcb_focus

BOARD_OUTLINE_LAYER = 11  # EPCB_LayerId.BOARD_OUTLINE
MULTI_LAYER = 12          # through-hole pads
LAYER_NAME = {TOP: "TOP", BOTTOM: "BOTTOM"}
LAYER_ID = {"TOP": TOP, "BOTTOM": BOTTOM}


def mm(v):
    return v / MIL_PER_MM


def to_mil(v):
    return round(v * MIL_PER_MM, 3)


def geometry_file(cfg, board):
    return cfg.artifact(f"pcb_geometry_{board.name}.json")


def load_geometry(cfg, board):
    f = geometry_file(cfg, board)
    if not f.exists():
        raise SystemExit(f"{f} is missing – run `edakit pcb dump` once the parts are in the PCB")
    return json.loads(f.read_text())


# --- plan ---------------------------------------------------------------------------------------------------------

def part_box(board, geo, p):
    x0, y0, x1, y1 = geo["bbox"]
    pts = [board.transform(c, p.x, p.y, p.rot, p.side) for c in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    return min(xs), min(ys), max(xs), max(ys)


def overlap(a, b, gap=0.0):
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


def outline_polygon(board):
    from shapely.geometry import Polygon
    return Polygon(board.outline)


def build_plan(cfg, board, geo):
    place = {r: p for r, p in board.place.items()}
    missing = sorted(r for r in place if r not in geo)
    boxes = {r: part_box(board, geo[r], p) for r, p in place.items() if r in geo}
    tht = {"top": [], "bottom": []}  # THT pads per side of their part – they block the other side
    for r, p in place.items():
        for pad in geo.get(r, {}).get("pads", {}).values():
            if pad["tht"]:
                tht[p.side].append(board.transform((pad["x"], pad["y"]), p.x, p.y, p.rot, p.side))
    unplaced = sorted((r for r in geo if r not in place), key=natural_key)
    return place, boxes, tht, unplaced, missing


def wirelength(board, geo, place, ground):
    """Sum of minimum spanning trees per net over the pads of fixed parts (mm) – a figure to compare plans."""
    pads = {}
    for ref, p in place.items():
        for pad in geo.get(ref, {}).get("pads", {}).values():
            if pad["net"] and pad["net"] != ground:
                pads.setdefault(pad["net"], []).append(board.transform((pad["x"], pad["y"]), p.x, p.y, p.rot, p.side))
    total = 0.0
    for pts in pads.values():
        if len(pts) < 2:
            continue
        tree, rest = [pts[0]], pts[1:]
        while rest:
            d, j = min((min(math.dist(a, b) for a in tree), j) for j, b in enumerate(rest))
            total += d
            tree.append(rest.pop(j))
    return total


def check_plan(cfg, board, geo, place, boxes, tht):
    from shapely.geometry import Point, box
    problems = []
    outline = outline_polygon(board)
    refs = [r for r in place if r in boxes]
    for i, a in enumerate(refs):
        if a not in board.edge_ok and not outline.buffer(-0.3).contains(box(*boxes[a])):
            problems.append(f"{a}: reaches over the outline (keep 0.3 mm)")
        for b in refs[i + 1:]:
            if place[a].side == place[b].side and overlap(boxes[a], boxes[b]):
                problems.append(f"{a} / {b}: overlap ({place[a].side})")
        for h in board.holes:
            if box(*boxes[a]).intersects(Point(h["x"], h["y"]).buffer(h["keep"])):
                problems.append(f"{a}: inside the keep-out of the hole ({h['x']:g}, {h['y']:g})")
        for tx, ty in board.tooling:
            if box(*boxes[a]).intersects(Point(tx, ty).buffer(board.tooling_keep)):
                problems.append(f"{a}: inside the keep-out of the tooling hole ({tx:g}, {ty:g})")
    for h in board.holes:
        if not outline.contains(Point(h["x"], h["y"]).buffer(h["d"] / 2 + 0.3)):
            problems.append(f"hole ({h['x']:g}, {h['y']:g}): too close to the outline")
    for tx, ty in board.tooling:
        if not outline.contains(Point(tx, ty).buffer(board.tooling_d / 2 + 0.3)):
            problems.append(f"tooling hole ({tx:g}, {ty:g}): too close to the outline")
        if any(math.dist((tx, ty), (h["x"], h["y"])) < h["d"] / 2 + board.tooling_keep for h in board.holes):
            problems.append(f"tooling hole ({tx:g}, {ty:g}): too close to a mounting hole")
    if board.tooling and len(board.tooling) < 2:
        problems.append("JLCPCB wants 2-3 tooling holes in opposite corners, not one")
    for side, other in (("top", "bottom"), ("bottom", "top")):
        for r, p in place.items():
            if p.side != other or r not in boxes:
                continue
            b = boxes[r]
            hits = [1 for px, py in tht[side] if b[0] - 0.5 < px < b[2] + 0.5 and b[1] - 0.5 < py < b[3] + 0.5]
            if hits:
                problems.append(f"{r} ({other}): {len(hits)} THT pins of the other side underneath")
    for part, hosts in board.near.items():
        if part in boxes:
            for host in hosts:
                if host in boxes:
                    a, b = boxes[part], boxes[host]
                    gap = max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3], 0)
                    if gap > board.near_mm:
                        problems.append(f"{part}: {gap:.1f} mm from {host} (near_mm {board.near_mm:g})")
    problems += led_rows(board, geo, place, Design.from_config(cfg))
    return problems


def led_rows(board, geo, place, design, tol=1.0):
    """LEDs side by side on one side of the board (centres on one line within tol mm) have their anode towards the
    same side – whoever solders them by the "+" mark should not have to turn every other one."""
    leds = {}
    for ref, p in place.items():
        part = design.part(ref) if ref in design.comps else None
        if not part or part.get("kind") != "led" or ref not in geo:
            continue
        roles = {i.get("role"): n for n, i in part["pins"].items()}
        pads = geo[ref]["pads"]
        if roles.get("anode") in pads and roles.get("cathode") in pads:
            a, k = (board.transform((pads[roles[r]]["x"], pads[roles[r]]["y"]), p.x, p.y, p.rot, p.side)
                    for r in ("anode", "cathode"))
            leds[ref] = (p.side, (p.x, p.y), (a[0] - k[0], a[1] - k[1]))
    problems, seen = [], set()
    for axis, name in ((1, "row"), (0, "column")):
        for ref, (side, c, d) in sorted(leds.items(), key=lambda kv: natural_key(kv[0])):
            line = sorted((r for r, (s, c2, _) in leds.items() if s == side and abs(c2[axis] - c[axis]) <= tol),
                          key=lambda r: leds[r][1][1 - axis])
            if len(line) < 2 or tuple(line) in seen:
                continue
            seen.add(tuple(line))
            first = leds[line[0]][2]
            other = [r for r in line[1:] if leds[r][2][0] * first[0] + leds[r][2][1] * first[1] < 0]
            if other:
                problems.append(f"LEDs in a {name} ({', '.join(line)}): anode of {', '.join(other)} points the other "
                                f"way than {line[0]} – turn them by 180°")
    return problems


def render(cfg, board, geo, place, boxes, tht, problems):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon, Rectangle
    poly = board.outline
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    fig, axes = plt.subplots(1, 2, figsize=(14, max(4, 7 * h / max(w, 1)) + 1))
    colors = {"U": "#3b6ea8", "D": "#d0453a", "SW": "#6b8e23", "R": "#888", "C": "#a07850", "Q": "#555",
              "L": "#7a4fa0", "F": "#e08b00", "J": "#c9a227", "BT": "#c9a227"}
    for ax, side in ((axes[0], board.view), (axes[1], "bottom" if board.view == "top" else "top")):
        mirror = 1 if side == board.view else -1   # the other side seen from its own face
        ax.add_patch(Polygon([(mirror * x, y) for x, y in poly], closed=True, fc="#0d3b1e", ec="#7fd18b", lw=2))
        for hl in board.holes:
            ax.add_patch(Circle((mirror * hl["x"], hl["y"]), hl["d"] / 2, fc="#1a1a1a", ec="#7fd18b"))
        for tx, ty in board.tooling:
            ax.add_patch(Circle((mirror * tx, ty), board.tooling_d / 2, fc="#1a1a1a", ec="#e0c060"))
        for r, p in place.items():
            if r not in boxes:
                continue
            b = boxes[r]
            col = colors.get(re.sub(r"\d.*", "", r), "#999")
            own = p.side == side
            x0, x1 = (b[0], b[2]) if mirror == 1 else (-b[2], -b[0])
            ax.add_patch(Rectangle((x0, b[1]), x1 - x0, b[3] - b[1], fc=col if own else "none", ec=col,
                                   lw=1 if own else 0.6, ls="-" if own else ":", alpha=0.9 if own else 0.6))
            if own:
                ax.text((x0 + x1) / 2, (b[1] + b[3]) / 2, r, ha="center", va="center", color="white",
                        fontsize=6 if (b[2] - b[0]) < 8 else 8)
        for px, py in tht["top"] + tht["bottom"]:
            ax.add_patch(Circle((mirror * px, py), 0.45, fc="#ffd700", ec="none"))
        ax.set_title(f"{side} side" + ("" if mirror == 1 else " (seen from that side)"))
        ax.set_xlim(*(sorted((mirror * (min(xs) - 5), mirror * (max(xs) + 5)))))
        ax.set_ylim(min(ys) - 5, max(ys) + 5)
        ax.set_aspect("equal")
        ax.grid(alpha=0.2)
        ax.set_facecolor("#1a1a1a")
    fig.suptitle(f"{cfg.project} / {board.name}: plan {w:.0f} x {h:.0f} mm · {len(problems)} findings", fontsize=13)
    fig.tight_layout()
    out = cfg.artifact(f"pcb_plan_{board.name}.png")
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def ipc2221_width_mm(i_a, dt_k=10, oz=1.0, reserve=1.5):
    """Outer layer, IPC-2221: A[mil²] = (I / (k · ΔT^0.44))^(1/0.725), k = 0.048."""
    area_mil2 = (i_a * reserve / (0.048 * dt_k ** 0.44)) ** (1 / 0.725)
    return area_mil2 / (1.378 * oz) * 0.0254


def net_classes(cfg, board):
    """Net classes from the simulated currents: class by current, width = max(practical minimum, IPC-2221)."""
    f = cfg.artifacts / "sim" / "net_currents.json"
    if not f.exists():
        print("  (no net currents – run `edakit sim` first)")
        return {}
    nets = json.loads(f.read_text())["nets"]
    out = {name: {"width_mm": c["width_mm"], "nets": []} for name, c in cfg.net_classes.items()}
    for net, v in sorted(nets.items()):
        i = max(v["i_max_a"], v.get("i_peak_a") or 0)
        cls = cfg.force_class.get(net) or next(n for n, c in cfg.net_classes.items() if i >= c["min_a"])
        out[cls]["width_mm"] = round(max(out[cls]["width_mm"], ipc2221_width_mm(i)), 2)
        out[cls]["nets"].append(net)
    path = cfg.artifact(f"pcb_netclasses_{board.name}.json")
    path.write_text(json.dumps(out, indent=1))
    for name, c in out.items():
        if c["nets"] and name != list(out)[-1]:
            print(f"  net class {name}: {c['width_mm']} mm – {', '.join(c['nets'])}")
    return out


def plan(cfg, board):
    geo = load_geometry(cfg, board)
    place, boxes, tht, unplaced, missing = build_plan(cfg, board, geo)
    problems = [f"{r}: in the plan but not in the footprint geometry (edakit pcb parts --write, then dump)"
                for r in missing]
    problems += check_plan(cfg, board, geo, place, boxes, tht)
    for p in problems:
        print("  !", p)
    print(f"  {len(place)} fixed parts, {len(unplaced)} for the auto-layout; airline length of the fixed parts "
          f"(without {cfg.ground}): {wirelength(board, geo, place, cfg.ground) / 1000:.2f} m")
    print(f"  preview -> {render(cfg, board, geo, place, boxes, tht, problems)}")
    cfg.artifact(f"pcb_plan_{board.name}.json").write_text(json.dumps(
        {r: {"x": p.x, "y": p.y, "rot": p.rot, "side": p.side} for r, p in place.items()}, indent=1))
    net_classes(cfg, board)
    return problems


# --- EasyEDA ------------------------------------------------------------------------------------------------------

def measure(mcp, c):
    """Geometry of a part relative to its origin; turns it to 0°/TOP for that and leaves it so."""
    pid = c["primitiveId"]
    if c["rotation"] or c["layer"] != TOP:
        ensure_pcb_focus(mcp)
        api(mcp, "PCB_PrimitiveComponent.modify", pid, {"rotation": 0, "layer": TOP})
        g = api(mcp, "PCB_PrimitiveComponent.get", pid)  # other field names than easyeda_pcb_components
        c = {**c, "x": g["x"], "y": g["y"]}
    x, y = c["x"], c["y"]
    bb = api(mcp, "PCB_Primitive.getPrimitivesBBox", [pid])
    pads = api(mcp, "PCB_PrimitiveComponent.getAllPinsByPrimitiveId", pid)
    g = {"primitiveId": pid, "footprint": c["footprintName"], "device": c["deviceName"],
         "bbox": [round(bb["minX"] - x, 2), round(bb["minY"] - y, 2), round(bb["maxX"] - x, 2), round(bb["maxY"] - y, 2)],
         "pads": {p["padNumber"]: {"x": round(p["x"] - x, 2), "y": round(p["y"] - y, 2), "net": p["net"],
                                   "tht": p["hole"] is not None} for p in pads}}
    nums = [p["padNumber"] for p in pads]  # numbers used several times (shell legs): "pads" keeps one, all here
    if dup := sorted({n for n in nums if nums.count(n) > 1}):
        g["pads_same_number"] = {n: [{"x": round(p["x"] - x, 2), "y": round(p["y"] - y, 2)} for p in pads
                                     if p["padNumber"] == n] for n in dup}
    w, h = g["bbox"][2] - g["bbox"][0], g["bbox"][3] - g["bbox"][1]
    print(f"  {c['designator']:<6} {mm(w):6.1f} x {mm(h):5.1f} mm  {c['footprintName']}")
    return g


def dump(cfg, board, mcp, refs=None):
    f = geometry_file(cfg, board)
    out = json.loads(f.read_text()) if refs and f.exists() else {}
    out |= {c["designator"]: measure(mcp, c) for c in eda.list_pcb_components(mcp)
            if c.get("designator") and (not refs or c["designator"] in refs)}
    f.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"{len(out)} parts -> {f}")


def outline_arg(points):
    poly = [to_mil(points[0][0]), to_mil(points[0][1]), "L"]
    for x, y in points[1:] + points[:1]:
        poly += [to_mil(x), to_mil(y)]
    return {"$polygon": poly}


def circle_points(cx, cy, r, n=24):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def apply(cfg, board, mcp, verify_all=False):
    """Fixed parts locked in place, outline and holes drawn, tooling holes set; then the pads of one part per
    (footprint, side, rotation) are compared with the plan – it checks that EasyEDA mirrors and rotates like
    Board.transform. --verify-all compares every part."""
    geo = load_geometry(cfg, board)
    problems = plan(cfg, board)
    ids = {c["designator"]: c["primitiveId"] for c in eda.list_pcb_components(mcp) if c.get("designator")}
    missing = [r for r in board.place if r not in geo or r not in ids]
    if missing:
        raise SystemExit(f"not in the PCB or without geometry (first `edakit pcb parts --write`, `dump`): {missing}")
    for n, (ref, p) in enumerate(board.place.items()):
        if n % 20 == 0:  # focus check per block instead of before every write
            ensure_pcb_focus(mcp)
        x, y, rot, layer = board.to_eda(p.x, p.y, p.rot, p.side)
        api(mcp, "PCB_PrimitiveComponent.modify", ids[ref],
            {"x": to_mil(x), "y": to_mil(y), "rotation": rot, "layer": layer, "primitiveLock": p.lock})
    print(f"  {len(board.place)} fixed parts placed")
    loose = [r for r in ids if r not in board.place]
    for n, ref in enumerate(loose):  # parts that were fixed before: unlock them for the auto-layout
        if n % 20 == 0:
            ensure_pcb_focus(mcp)
        api(mcp, "PCB_PrimitiveComponent.modify", ids[ref], {"primitiveLock": False})
    print(f"  {len(loose)} parts unlocked for the auto-layout")
    ensure_pcb_focus(mcp)
    for pid in api(mcp, "PCB_PrimitivePolyline.getAllPrimitiveId") or []:
        line = api(mcp, "PCB_PrimitivePolyline.get", pid)
        if line and line.get("layer") == BOARD_OUTLINE_LAYER:
            api(mcp, "PCB_PrimitivePolyline.delete", [pid])
    api(mcp, "PCB_PrimitivePolyline.create", "", BOARD_OUTLINE_LAYER,
        outline_arg([board.eda_point(*q) for q in board.outline]), 10)
    for h in board.holes:  # a hole is a circle on the outline layer
        cx, cy = board.eda_point(h["x"], h["y"])
        api(mcp, "PCB_PrimitivePolyline.create", "", BOARD_OUTLINE_LAYER, outline_arg(circle_points(cx, cy, h["d"] / 2)), 6)
    print(f"  outline: {len(board.outline)} points, {len(board.holes)} holes")
    tooling(cfg, board, mcp)
    ensure_pcb_focus(mcp)
    worst, seen = (0.0, None), set()
    for ref, p in board.place.items():
        key = (geo[ref]["footprint"], p.rot, p.side)
        if key in seen and not verify_all:
            continue
        seen.add(key)
        for pad in api(mcp, "PCB_PrimitiveComponent.getAllPinsByPrimitiveId", ids[ref]):
            lib = geo[ref]["pads"].get(pad["padNumber"])
            if not lib:
                continue
            want = board.transform((lib["x"], lib["y"]), p.x, p.y, p.rot, p.side)
            have = board.plan_point(mm(pad["x"]), mm(pad["y"]))
            d = math.dist(have, want)
            if d > worst[0]:
                worst = (d, f"{ref}.{pad['padNumber']}")
    print(f"  pad check ({len(seen)} parts): largest deviation {worst[0]:.3f} mm ({worst[1]})")
    if worst[0] > 0.05:
        print("  ! pads are not where the plan puts them – check rotation/mirroring of the bottom side")
        return 2
    return 2 if problems else 0


def remove_tooling(mcp):
    """Delete tooling holes (pads without a part, number TL…). Needed before every pour fill: while a free pad is
    in the PCB, easyeda_pcb_rebuild_copper fails ("Cannot read properties of undefined (reading 'length')")."""
    ensure_pcb_focus(mcp)
    comps = [eda.state(c)["PrimitiveId"] for c in api(mcp, "PCB_PrimitiveComponent.getAll") or []]
    old = [st["PrimitiveId"] for st in (eda.state(p) for p in api(mcp, "PCB_PrimitivePad.getAll") or [])
           if str(st["PadNumber"]).startswith("TL") and not any(st["PrimitiveId"].startswith(c) for c in comps)]
    if old:
        api(mcp, "PCB_PrimitivePad.delete", old)
    return len(old)


def tooling(cfg, board, mcp):
    """Tooling holes as free pads without copper ring: non-plated (they end up in the NPTH drill file), solder mask
    tooling_mask larger on both sides. Replaces earlier ones."""
    old = remove_tooling(mcp)
    d, mask = to_mil(board.tooling_d), to_mil(board.tooling_mask)
    for n, (tx, ty) in enumerate(board.tooling, 1):
        ensure_pcb_focus(mcp)
        x, y = board.eda_point(tx, ty)
        # arguments in the order of the fields of PCB_PrimitivePad.get: layer 12 (both), number, x, y, rotation,
        # shape, net, hole, hole offset x/y, hole rotation, plated, pad type, special shape, mask/paste, thermal, lock
        if not api(mcp, "PCB_PrimitivePad.create", MULTI_LAYER, f"TL{n}", to_mil(x), to_mil(y), 0, ["ELLIPSE", d, d],
                   "", ["ROUND", d], 0, 0, 0, False, 0, [],
                   {"topSolderMask": mask, "bottomSolderMask": mask, "topPasteMask": 0, "bottomPasteMask": 0}, None,
                   True):
            raise SystemExit(f"tooling hole TL{n} ({tx}, {ty}) not created")
    if board.tooling or old:
        print(f"  {len(board.tooling)} tooling holes Ø {board.tooling_d} mm (NPTH), {old} old ones replaced")


def pour_outline(board):
    """Pour polygon (plan mm): the outline, set in by the edge clearance of the routing rules (+0.1 mm; EasyEDA itself
    keeps only about 0.26 mm), without the keep-out circle of every mounting hole, with a notch around every tooling
    hole. EasyEDA takes a polygon with a hole only as its
    outer contour, and copper must not lie under the tooling hole – so the notch reaches the edge."""
    from shapely.geometry import Point, box
    edge = float(board.routing.get("edge_clearance_um", 400)) / 1000 + 0.1
    poly = outline_polygon(board).buffer(-edge, join_style="mitre")
    for h in board.holes:  # 'keep' = radius free of parts and copper (screw head, washer)
        cut = poly.difference(Point(h["x"], h["y"]).buffer(h["keep"]))
        if cut.geom_type == "Polygon" and not cut.interiors:
            poly = cut
        else:  # the circle lies inside: a notch to the edge, as for tooling holes
            half = max(h["keep"], poly.exterior.distance(Point(h["x"], h["y"])) + 0.05)
            cut = poly.difference(box(h["x"] - half, h["y"] - half, h["x"] + half, h["y"] + half))
            if cut.geom_type == "Polygon" and not cut.interiors:
                poly = cut
            else:
                print(f"  ! hole ({h['x']}, {h['y']}) is not near an edge – the pour keeps only EasyEDA's clearance")
    for tx, ty in board.tooling:
        half = max(board.tooling_keep, poly.exterior.distance(Point(tx, ty)) + 0.05)
        cut = poly.difference(box(tx - half, ty - half, tx + half, ty + half))
        if cut.geom_type == "Polygon" and not cut.interiors:
            poly = cut
        else:
            print(f"  ! tooling hole ({tx}, {ty}) is not near an edge – the pour cannot leave it out")
    return [tuple(q) for q in list(poly.exterior.coords)[:-1]]


def pour(cfg, board, mcp, keep_islands_on=None):
    """Copper pours of [[boards.<b>.pours]] (default GND on both layers) along the outline; old pours of the same
    nets are replaced. keep_islands_on: layer name whose islands are kept (to find them for stitching)."""
    ensure_pcb_focus(mcp)
    nets = {p["net"] for p in board.pours}
    old = [eda.state(p)["PrimitiveId"] for p in api(mcp, "PCB_PrimitivePour.getAll") or []
           if eda.state(p).get("Net") in nets]
    if old:
        api(mcp, "PCB_PrimitivePour.delete", old)
    pts = [board.eda_point(*q) for q in pour_outline(board)]
    for spec in board.pours:
        for layer_name in spec.get("layers", ["TOP", "BOTTOM"]):
            ensure_pcb_focus(mcp)
            layer = LAYER_ID[layer_name]
            # 5th value preserveSilos: keep islands. Loose islands count as DRC connection errors – only for finding them
            r = api(mcp, "PCB_PrimitivePour.create", spec["net"], layer, outline_arg(pts), "solid",
                    keep_islands_on == layer_name, f"{spec['net']}_{layer_name}", spec.get("priority", 1),
                    spec.get("line_mil", 10))
            print(f"  pour {spec['net']} {layer_name}: {'ok' if r else 'FAILED'}")


def sync_nets(cfg, mcp, write=False):
    """Pad nets in the PCB = graph (replaces importChanges for pure net changes: its confirmation dialog needs a click,
    'force' has no effect). Pads of parts have their own ids from getAllPinsByPrimitiveId."""
    design = Design.from_config(cfg)
    want = dict(design.pin_net)
    ensure_pcb_focus(mcp)
    changes = []
    for c in api(mcp, "PCB_PrimitiveComponent.getAll") or []:
        st = eda.state(c)
        ref = st.get("Designator")
        if not ref:
            continue
        for pin in api(mcp, "PCB_PrimitiveComponent.getAllPinsByPrimitiveId", st["PrimitiveId"]) or []:
            ps = eda.state(pin)
            key = f"{ref}.{ps['PadNumber']}"
            net = want.get(key, "")  # not in the graph = unconnected (nc)
            if (ps.get("Net") or "") != net:
                changes.append((key, ps["PrimitiveId"], ps.get("Net"), net))
    for n, (key, pid, old, new) in enumerate(changes):
        print(f"  {key}: {old} -> {new or '–'}")
        if write:
            if n % 20 == 0:
                ensure_pcb_focus(mcp)
            api(mcp, "PCB_PrimitivePad.modify", pid, {"net": new})
    print(f"  {len(changes)} pad nets {'changed' if write else 'differ'}")
    return len(changes)


def _number(text, pattern):
    m = re.fullmatch(pattern, text or "")
    return int(m.group(1)) if m else None


def schematic_parts(mcp, board):
    sch_uuid, pages = eda.find_pages(mcp, board.schematic)
    parts = {}
    for page in pages:
        eda.focus_page(mcp, sch_uuid, page)
        for c in api(mcp, "SCH_PrimitiveComponent.getAll") or []:
            st = eda.state(c)
            if st.get("ComponentType") == "part" and st.get("AddIntoPcb", True) and st.get("Designator"):
                parts[st["Designator"]] = {**st, "_page": page}
    return sch_uuid, parts


def bom_differs(sch_part, pcb_part):
    """'Add into BOM' of schematic and PCB part differ – the import dialog lists that as a change."""
    a, b = sch_part.get("AddIntoBom"), pcb_part.get("AddIntoBom")
    return a is not None and b is not None and bool(a) != bool(b)


def sync_parts(cfg, board, mcp, write=False):
    """PCB parts = parts of the board schematic, without the "Import Changes" dialog (importChanges(uuid, true) opens
    it anyway). Schematic and PCB part are linked through the same UniqueId (ggeN). Missing parts are created (device
    from the project library, designator, UniqueId, the COMPLETE OtherProperty of the schematic part with a new
    Channel ID, pad nets from the graph) and parked next to the board; swapped ones (other LCSC number or footprint)
    are replaced the same way; extra ones deleted; unlinked ones linked. Without write only shown.
    Then: dump/plan, apply, auto-layout, route."""
    project = api(mcp, "DMT_Project.getCurrentProjectInfo")["uuid"]
    sch_uuid, sch = schematic_parts(mcp, board)
    eda.open_pcb(mcp, board.pcb)
    pcb = {}
    for c in api(mcp, "PCB_PrimitiveComponent.getAll") or []:
        st = eda.state(c)
        if st.get("Designator"):
            pcb[st["Designator"]] = st

    def same(r):
        a, b = sch[r], pcb[r]
        return a.get("SupplierId") == b.get("SupplierId") and \
            (a.get("Footprint") or {}).get("name") == (b.get("Footprint") or {}).get("name")
    missing = sorted(set(sch) - set(pcb), key=natural_key)
    extra = sorted(set(pcb) - set(sch), key=natural_key)
    swapped = sorted((r for r in set(sch) & set(pcb) if not same(r)), key=natural_key)
    unlinked = sorted((r for r in set(sch) & set(pcb) if same(r) and (not sch[r].get("UniqueId")
                       or sch[r].get("UniqueId") != pcb[r].get("UniqueId"))), key=natural_key)
    # The DRC compares the properties like the dialog does ("Netlist Error – Import Changes"): a part created through
    # the API carried the Description from the library instead of the one from the schematic
    props = sorted((r for r in set(sch) & set(pcb) if same(r) and (any(
        (pcb[r].get("OtherProperty") or {}).get(k) != v for k, v in (sch[r].get("OtherProperty") or {}).items())
        or bom_differs(sch[r], pcb[r]))), key=natural_key)
    for title, refs in (("missing in the PCB", missing), ("not in the schematic", extra),
                        ("swapped (LCSC/footprint)", swapped), ("not linked (UniqueId)", unlinked),
                        ("properties differ from the schematic", props)):
        if refs:
            print(f"  {title}: {', '.join(refs)}")
    todo = len(missing) + len(extra) + len(swapped) + len(unlinked) + len(props)
    print(f"  schematic {board.schematic}: {len(sch)} parts, PCB {board.pcb}: {len(pcb)}; {todo} difference(s)")
    if not write or not todo:
        return todo
    used_uid = {n for st in [*sch.values(), *pcb.values()] if (n := _number(st.get("UniqueId"), r"gge(\d+)"))}
    used_ch = {n for st in pcb.values() if (n := _number((st.get("OtherProperty") or {}).get("Channel ID"), r"\$1I(\d+)"))}

    def fresh(used):
        n = max(used, default=0) + 1
        used.add(n)
        return n
    sch_uid = {}
    ensure_pcb_focus(mcp)
    if extra:
        api(mcp, "PCB_PrimitiveComponent.delete", [pcb[r]["PrimitiveId"] for r in extra])
        print(f"  deleted: {', '.join(extra)}")
    created = []
    for k, ref in enumerate(missing + swapped):
        st, old = sch[ref], pcb.get(ref) or {}
        uid = st.get("UniqueId") or old.get("UniqueId") or f"gge{fresh(used_uid)}"
        if st.get("UniqueId") != uid:
            sch_uid[st["PrimitiveId"]] = uid
        # the schematic's Channel ID wins: the import dialog compares it (a swap once kept the old PCB one)
        channel = ((st.get("OtherProperty") or {}).get("Channel ID") or (old.get("OtherProperty") or {}).get("Channel ID")
                   or f"$1I{fresh(used_ch)}")
        ensure_pcb_focus(mcp)
        if old:
            api(mcp, "PCB_PrimitiveComponent.delete", [old["PrimitiveId"]])  # its tracks stay
        x, y = to_mil(board.park[0] + 8 * (k % 6)), to_mil(board.park[1] - 8 * (k // 6))
        res = api(mcp, "PCB_PrimitiveComponent.create", {"libraryUuid": project, "uuid": st["Component"]["uuid"]},
                  TOP, x, y, 0, False)
        new = eda.state(res or {})
        if not new.get("PrimitiveId"):
            raise SystemExit(f"{ref}: PCB_PrimitiveComponent.create returned nothing (device {st['Component']})")
        other = {**(new.get("OtherProperty") or {}), **(st.get("OtherProperty") or {}),
                 "Device": st["Component"].get("name") or "", "Reuse Block": "", "Group ID": "", "Channel ID": channel}
        # otherProperty replaces ALL properties – so pass the complete set
        api(mcp, "PCB_PrimitiveComponent.modify", new["PrimitiveId"],
            {"designator": ref, "uniqueId": uid, "otherProperty": other})
        if st.get("AddIntoBom") is not None:  # hand-soldered parts: not in the BOM, as in the schematic
            api(mcp, "PCB_PrimitiveComponent.modify", new["PrimitiveId"], {"addIntoBom": bool(st["AddIntoBom"])})
        created.append(ref)
        print(f"  created: {ref} ({st.get('SupplierId')}, {uid}, {channel})")
    for ref in unlinked:
        uid = sch[ref].get("UniqueId") or pcb[ref].get("UniqueId") or f"gge{fresh(used_uid)}"
        if sch[ref].get("UniqueId") != uid:
            sch_uid[sch[ref]["PrimitiveId"]] = uid
        if pcb[ref].get("UniqueId") != uid:
            ensure_pcb_focus(mcp)
            api(mcp, "PCB_PrimitiveComponent.modify", pcb[ref]["PrimitiveId"], {"uniqueId": uid})
        print(f"  linked: {ref} ({uid})")
    for ref in props:
        ensure_pcb_focus(mcp)
        api(mcp, "PCB_PrimitiveComponent.modify", pcb[ref]["PrimitiveId"],
            {"otherProperty": {**(pcb[ref].get("OtherProperty") or {}), **(sch[ref].get("OtherProperty") or {})}})
        if bom_differs(sch[ref], pcb[ref]):
            api(mcp, "PCB_PrimitiveComponent.modify", pcb[ref]["PrimitiveId"],
                {"addIntoBom": bool(sch[ref]["AddIntoBom"])})
        print(f"  properties from the schematic: {ref}")
    if sch_uid:
        for page in {sch[r]["_page"] for r in sch if sch[r]["PrimitiveId"] in sch_uid}:
            eda.focus_page(mcp, sch_uuid, page)
            for st in sch.values():
                if st["_page"] == page and st["PrimitiveId"] in sch_uid:
                    api(mcp, "SCH_PrimitiveComponent.modify", st["PrimitiveId"], {"uniqueId": sch_uid[st["PrimitiveId"]]})
            api(mcp, "SCH_Document.save")
        print(f"  UniqueId written back into the schematic: {len(sch_uid)}, schematic saved")
        eda.open_pcb(mcp, board.pcb)
    sync_nets(cfg, mcp, write=True)  # before measuring: the geometry carries the pad nets
    if created:  # geometry of the new parts (they sit at 0°/TOP like after dump)
        f = geometry_file(cfg, board)
        geo = json.loads(f.read_text()) if f.exists() else {}
        for c in eda.list_pcb_components(mcp):
            if c["designator"] in created:
                geo[c["designator"]] = measure(mcp, c)
        f.write_text(json.dumps(geo, indent=1, ensure_ascii=False))
    print(f"  PCB saved: {eda.save_pcb(mcp)}")
    return 0


def autolayout(cfg, board, mcp, timeout_min=20):
    """EasyEDA's auto-layout places only unlocked parts and only on TOP; it knows nothing about belonging
    (decoupling capacitors, pull-ups) – fix those in the plan. It keeps running after the bridge timeout, so the end is
    detected by positions that stay the same for two readings."""
    ensure_pcb_focus(mcp)
    try:
        api(mcp, "PCB_Document.autoLayout", timeout=20)
    except MCPError as e:
        print(f"  (auto-layout keeps running in EasyEDA: {str(e)[:80]})")
    last, stable, t0 = None, 0, time.monotonic()
    while time.monotonic() - t0 < timeout_min * 60:
        time.sleep(10)
        now = sorted((c["designator"], round(c["x"], 1), round(c["y"], 1)) for c in eda.list_pcb_components(mcp))
        stable = stable + 1 if now == last else 0
        last = now
        print(f"  {(time.monotonic() - t0) / 60:4.1f} min: {'stable' if stable else 'moving'}")
        if stable >= 2:
            return 0
    print("  auto-layout did not settle in time")
    return 2


def main(cfg, args):
    board = cfg.board(args.board)
    if args.action == "plan":
        return 2 if plan(cfg, board) else 0
    mcp = eda.start(cfg, args.verbose)
    try:
        if not eda.wait_for_bridge(mcp):
            return 1
        eda.open_project(mcp, cfg)
        if args.action == "parts":
            todo = sync_parts(cfg, board, mcp, write=args.write)
            return 2 if todo and not args.write else 0
        eda.open_pcb(mcp, board.pcb)
        if args.action == "dump":
            dump(cfg, board, mcp, args.ref and args.ref.split(","))
        elif args.action == "apply":
            return apply(cfg, board, mcp, args.verify_all)
        elif args.action == "tooling":
            tooling(cfg, board, mcp)
        elif args.action == "pour":
            pour(cfg, board, mcp)
        elif args.action == "nets":
            n = sync_nets(cfg, mcp, write=args.write)
            return 2 if n and not args.write else 0
        elif args.action == "autolayout":
            return autolayout(cfg, board, mcp)
        return 0
    except MCPError as e:
        return eda.die(str(e))
    finally:
        mcp.close()
