"""PCB: placement plan, footprint geometry, parts and nets from the schematic without dialogs, fixed parts, outline,
mounting and tooling holes, copper pours, EasyEDA's auto-layout.

    edakit pcb dump [--ref U1,J1]   footprint geometry -> <board file>.geometry.json beside the board file
                                    (hardware/boards/<board>.geometry.json), versioned – the layout hash covers it;
                                    through-hole pads with their hole [w, l] in mm (P-7); the pads of a part whose
                                    parts entry has footprint data also with shape, size, rotation, layer (P-10)
                                    (turns every measured part to 0°/TOP and leaves it there – run apply afterwards)
    edakit pcb plan                 offline: check the plan (overlaps – under a part on pin headers only its pins,
                                    SMD parts within silk_overlap_mm –, outline, holes, THT pins under parts of the
                                    other side, near, polarised parts of the kinds in `uniform` pointing the same way
                                    (default: LEDs in a row), mated plugs (`mate` of the parts entry) clear of the
                                    other parts and out through the outline; L-12 the layout requirements of the
                                    circuit; P-7 holes and leads), airline length, preview PNG, net classes from the
                                    simulation, the mechanical model mech_<board>.json; a part not in the dump yet
                                    takes the library footprint `edakit part import` cached
    edakit pcb place [--rest] [--write] [--only C1,R1]
                                    offline: a spot next to its host for every part the circuit or the board file
                                    ties to one (layout.near, [near], the decoupling of L-12) and [place] lacks;
                                    --rest: every other part of the board without a row as well, by airline length
                                    (most pins on nets of placed parts first, the shortest airline length on an
                                    assembled side, then moves and swaps while it falls); --write adds the rows to
                                    [place] with auto = true (a later run may move those)
    edakit pcb parts [--write]      parts of the board schematic -> PCB without the "Import Changes" dialog
    edakit pcb nets [--write]       pad nets in the PCB = graph
    edakit pcb apply                outline, holes, tooling holes, fixed parts (locked); all other parts unlocked
    edakit pcb autolayout           EasyEDA auto-layout of the unlocked parts, waits until positions are stable, then
                                    writes the position of every part of the board without a row into [place], with
                                    auto = true
    edakit pcb takeover [--write]   a board placed before: the position EasyEDA has for every part of the board
                                    without a row; --write adds them to [place] as fixed rows – pcb apply leaves the
                                    parts where they are, the tracks stay on their pads
    edakit pcb tooling              only the tooling holes again
    edakit pcb pour                 copper pours of [[pours]] in the board file (replaces old ones, not filled);
                                    with pour_regions the outlines on a shared layer from the last routing

Plan coordinates: mm, as seen from the board's `view` side (board file); `side` of a part is the EasyEDA side.
EasyEDA PCB unit: mil, y up. Footprint geometry is stored relative to the part origin at rotation 0 on TOP, so the
plan can be computed offline.
"""

from __future__ import annotations

import copy
import itertools
import json
import math
import re
import time

from . import checks, eda, handover
from .config import BOTTOM, MIL_PER_MM, TOP
from .design import Design, natural_key
from .eda import MCPError, api, ensure_pcb_focus
from .toolchain import is_kicad

BOARD_OUTLINE_LAYER = 11  # EPCB_LayerId.BOARD_OUTLINE
MULTI_LAYER = 12          # through-hole pads
LAYER_NAME = {TOP: "TOP", BOTTOM: "BOTTOM"}
LAYER_ID = {"TOP": TOP, "BOTTOM": BOTTOM}


def mm(v):
    return v / MIL_PER_MM


def to_mil(v):
    return round(v * MIL_PER_MM, 3)


GEOMETRY = ".geometry.json"     # the footprint geometry beside the board file: hardware/boards/main.geometry.json


def geometry_home(cfg, board):
    """Where `pcb dump` writes the footprint geometry: beside the board file, with its name (hardware/boards/main.toml:
    hardware/boards/main.geometry.json) – versioned with it, so that CI and a fresh clone have the layout hash."""
    f = cfg.resolve(board.file or f"hardware/boards/{board.name}.toml")
    return f.with_name(f.stem + GEOMETRY)


def unmoved_geometry(cfg, board):
    """<artifacts>/pcb_geometry_<board>.json, where `pcb dump` wrote the geometry before it was versioned – while it
    lies only there, else None."""
    old = cfg.artifacts / f"pcb_geometry_{board.name}.json"
    return old if old.is_file() and not geometry_home(cfg, board).exists() else None


def geometry_file(cfg, board):
    """The footprint geometry the plan, the checks and the layout hash read: the one beside the board file – until it
    is moved there, the one from before among the artifacts."""
    return unmoved_geometry(cfg, board) or geometry_home(cfg, board)


def move_note(cfg, board):
    """What edakit check, pcb plan and the gate say while the board's geometry lies only among the artifacts; None
    once it is moved."""
    if old := unmoved_geometry(cfg, board):
        return (f"{cfg.relative(old)}: footprint geometry of board {board.name} among the artifacts, which are not "
                f"versioned – move it beside the board file and commit it: mv {cfg.relative(old)} "
                f"{cfg.relative(geometry_home(cfg, board))} (the layout hash changes once, sign-offs with scope "
                "'layout' lapse)")
    return None


def move_notes(cfg):
    """move_note of every made board."""
    return [note for b in cfg.made().values() if (note := move_note(cfg, b))]


def save_geometry(cfg, board, geo):
    """Writes the geometry beside the board file; one from before that was read among the artifacts goes – it is
    moved."""
    f, moving = geometry_home(cfg, board), unmoved_geometry(cfg, board)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(geo, indent=1, ensure_ascii=False))
    if moving:
        moving.unlink()
        print(f"  {cfg.relative(moving)} moved beside the board file: commit {cfg.relative(f)} – the layout hash "
              "covers it (it changes once, sign-offs with scope 'layout' lapse)")
    return f


def load_geometry(cfg, board):
    f = geometry_file(cfg, board)
    if not f.exists():
        raise SystemExit(f"{cfg.relative(f)} is missing – run `edakit pcb dump` once the parts are in the PCB")
    return json.loads(f.read_text())


def plan_geometry(cfg, board, design, refs=None):
    """The geometry the plan works with: the dump of the PCB, and for a part of refs (default: the planned ones) that
    is not in it the footprint data of its parts entry ("source": "data", 4.5), else the footprint `edakit part
    import` cached ("source": "library") – the pad nets from the graph."""
    from . import part
    f = geometry_file(cfg, board)
    geo = json.loads(f.read_text()) if f.exists() else {}
    for ref in board.place if refs is None else refs:
        if ref not in geo and ref in design.comps and (lib := part.library_footprint(cfg, design, ref)):
            pads = {n: {**p, "net": design.pin_net.get(f"{ref}.{n}", "")} for n, p in lib["pads"].items()}
            geo[ref] = {**lib, "pads": pads, "source": "data" if lib.get("source") == "data" else "library"}
    if not geo:
        raise SystemExit(f"{cfg.relative(f)} is missing – run `edakit pcb dump` once the parts are in the PCB, or "
                         "`edakit part import <LCSC>` for the library's footprints")
    return geo


# --- plan ---------------------------------------------------------------------------------------------------------

GEOMETRY_FROM = {"library": "library geometry {}", "data": "footprint data ({})"}   # what P-7 names besides pcb dump


def say_unmeasured(geo, refs):
    """The parts of refs the plan takes from the library footprint or from the footprint data – not yet from the
    PCB."""
    for source, what in (("library", "library geometry (edakit part import, not yet from the PCB)"),
                         ("data", "footprint data of the parts entry (not yet from the PCB)")):
        if found := sorted((r for r in refs if geo.get(r, {}).get("source") == source), key=natural_key):
            print(f"  {what}: {', '.join(found)}")


def part_box(board, geo, p):
    x0, y0, x1, y1 = geo["bbox"]
    pts = [board.transform(c, p.x, p.y, p.rot, p.side) for c in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    return min(xs), min(ys), max(xs), max(ys)


def overlap(a, b, gap=0.0):
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


def box_gap(a, b):
    return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3], 0)


def overlap_depth(a, b):
    """How far two overlapping boxes reach into each other: per axis the distance one has to move to clear the other,
    the smaller of x and y. For parts side by side that is the width of the strip they share; a small part inside a
    large box lies as deep as its way out."""
    return min(a[2] - b[0], b[2] - a[0], a[3] - b[1], b[3] - a[1])


def through_hole(geo):
    return any(q.get("tht") for q in geo.get("pads", {}).values())


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


def header_pins(board, geo, place):
    """The through-hole pins of the fixed parts in on_headers, in plan coordinates: {ref: {pad: (x, y)}}."""
    out = {}
    for r in sorted(board.on_headers, key=natural_key):
        if r in place and r in geo:
            p = place[r]
            out[r] = {n: board.transform((q["x"], q["y"]), p.x, p.y, p.rot, p.side)
                      for n, q in geo[r].get("pads", {}).items() if q.get("tht")}
    return out


def overlap_finding(board, geo, place, boxes, pins, a, b):
    """Two parts of one side whose boxes overlap. When one of them stands on pin headers (pins), the board under it is
    free but for the plastic of its headers: an SMD part is a finding only where its box comes closer than
    header_keep_mm to one of the through-hole pins (a square around the pin centre); a through-hole part stays an
    overlap. Otherwise the boxes, silkscreen included, of two SMD parts may reach silk_overlap_mm into each other;
    with a through-hole part the overlap stays a finding."""
    host = a if pins.get(a) else b if pins.get(b) else None
    other = b if host == a else a
    if host is not None and not through_hole(geo[other]):
        gap, pin = min(((box_gap(boxes[other], (x, y, x, y)), n) for n, (x, y) in pins[host].items()),
                       key=lambda g: (round(g[0], 6), natural_key(g[1])))
        if gap < board.header_keep_mm:
            return [f"{other}: on the pins of {host} ({place[other].side}) – {gap:.2f} mm from pin {pin} "
                    f"(header_keep_mm {board.header_keep_mm:g})"]
        return []
    found = f"{a} / {b}: overlap ({place[a].side})"
    tol = board.silk_overlap_mm
    if not tol:
        return [found]
    depth = overlap_depth(boxes[a], boxes[b])
    tht = [r for r in (a, b) if through_hole(geo[r])]
    if tht:
        return [f"{found} – {depth:.2f} mm ({', '.join(tht)} through-hole: silk_overlap_mm does not apply)"]
    if round(depth, 6) > tol:
        return [f"{found} – {depth:.2f} mm (silk_overlap_mm {tol:g})"]
    return []


def check_plan(cfg, board, geo, place, boxes, tht):
    from shapely.geometry import Point, box
    problems = []
    outline = outline_polygon(board)
    refs = [r for r in place if r in boxes]
    pins = header_pins(board, geo, place)
    problems += [f"{r}: in on_headers, but its footprint has no through-hole pins – its overlaps count as usual"
                 for r, p in pins.items() if not p]
    for i, a in enumerate(refs):
        if a not in board.edge_ok and not outline.buffer(-0.3).contains(box(*boxes[a])):
            problems.append(f"{a}: reaches over the outline (keep 0.3 mm)")
        for b in refs[i + 1:]:
            if place[a].side == place[b].side and overlap(boxes[a], boxes[b]):
                problems += overlap_finding(board, geo, place, boxes, pins, a, b)
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
        loose = [d for d in (part, *hosts) if d not in place]
        if loose:   # the auto-layout knows nothing about belonging: near holds only between fixed parts
            problems.append(f"near {part}: {', '.join(loose)} not fixed – near counts only between fixed parts")
            continue
        for host in hosts:
            if part in boxes and host in boxes and box_gap(boxes[part], boxes[host]) > board.near_mm:
                problems.append(f"{part}: {box_gap(boxes[part], boxes[host]):.1f} mm from {host} "
                                f"(near_mm {board.near_mm:g})")
    design = Design.from_config(cfg)
    problems += polarity_findings(board, geo, place, design)
    problems += mate_findings(board, geo, place, boxes, design)
    return problems


def check_handover(board, design, place, boxes):
    """L-12: the plan keeps the layout requirements of the circuit (handover.py) – parts that are not fixed, too far
    from the edge or from their host, an IC without a decoupling capacitor of its own next to it."""
    from shapely.geometry import box
    edge = outline_polygon(board).exterior
    where = f"{board.file} [place]"
    reqs = handover.requirements(design, board.name)
    out = []
    for r in reqs:
        if r.part not in place:
            want = {"fixed": "fixed", "edge": "at the board edge", "near": f"next to {', '.join(r.others)}",
                    "decoupling": f"fixed with its decoupling capacitor ({r.net})"}[r.kind]
            out.append(f"{r.part}: not in {where} – the circuit wants it {want}")
        elif r.kind == "edge" and r.part in boxes:
            dist = box(*boxes[r.part]).distance(edge)
            if dist > board.edge_mm:
                out.append(f"{r.part}: {dist:.1f} mm from the board edge – the circuit wants it at the edge "
                           f"(edge_mm {board.edge_mm:g})")
        elif r.kind == "near":
            for host in r.others:
                if host not in place:
                    out.append(f"{host}: not in {where} – {r.part} must sit next to it")
                elif r.part in boxes and host in boxes and box_gap(boxes[r.part], boxes[host]) > board.near_mm:
                    out.append(f"{r.part}: {box_gap(boxes[r.part], boxes[host]):.1f} mm from {host} – the circuit "
                               f"wants it next to it (near_mm {board.near_mm:g})")
    # decoupling: every IC gets a capacitor of its own – two ICs sharing one while another sits far away is no
    # decoupling (a matching per supply net, Kuhn's augmenting paths)
    ics = [r for r in reqs if r.kind == "decoupling" and r.part in boxes]
    for net in sorted({r.net for r in ics}):
        close = {r.part: [c for c in r.others if c in boxes and box_gap(boxes[c], boxes[r.part]) <= board.near_mm]
                 for r in ics if r.net == net}
        owner = {}

        def assign(ic, seen):
            for c in close[ic]:
                if c not in seen:
                    seen.add(c)
                    if c not in owner or assign(owner[c], seen):
                        owner[c] = ic
                        return True
            return False
        for r in ics:
            if r.net == net and not assign(r.part, set()):
                caps = r.others[0] if len(r.others) == 1 else f"one of {', '.join(r.others)}"
                out.append(f"{r.part}: no capacitor of its own from {net} to {design.ground} within "
                           f"{board.near_mm:g} mm – fix {caps} next to it")
    return out


AXES = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}


def polar_pins(part):
    """The plus and the minus pin of a polarised part from the roles of its parts entry – anode or plus…, cathode or
    minus… -> (plus, minus, the minus pin's word: "cathode" or "minus"), or None unless there is exactly one of each
    (an RGB LED, a battery holder of several cells)."""
    roles = [(n, (i or {}).get("role") or "") for n, i in ((part or {}).get("pins") or {}).items()]
    plus = [n for n, r in roles if r == "anode" or r.startswith("plus")]
    minus = [(n, r) for n, r in roles if r == "cathode" or r.startswith("minus")]
    if len(plus) != 1 or len(minus) != 1:
        return None
    return plus[0], minus[0][0], "cathode" if minus[0][1] == "cathode" else "minus"


def polarity_findings(board, geo, place, design, tol=1.0, skipped=None):
    """Polarised parts of the kinds in the board's `uniform` point the same way – whoever solders a bag of them by hand
    turns each one alike, by the "+" mark or the flat side. Per kind: "row" – parts of the kind side by side on one
    side of the board (centres on one line within tol mm) have their plus pin towards the same side; "+x", "-x", "+y",
    "-y" – the minus pin (cathode) of every part of the kind points that way, seen from the side the part sits on (a part
    on the other side than `view` is mirrored in x). Without the key: LEDs in rows (config.UNIFORM). A part counts with
    exactly one anode/plus… and one cathode/minus… pin (polar_pins); the others of a listed kind go to `skipped`."""
    from .config import UNIFORM
    uniform = UNIFORM if board.uniform is None else board.uniform
    parts = {}   # ref -> (kind, pins, word)
    for ref, p in place.items():
        part = design.part(ref) if ref in design.comps else None
        kind = (part or {}).get("kind")
        if kind not in uniform or ref not in geo:
            continue
        pins, pads = polar_pins(part), geo[ref].get("pads", {})
        if not pins or pins[0] not in pads or pins[1] not in pads:
            if skipped is not None:
                skipped.append((ref, kind))
            continue
        parts[ref] = (kind, pins[:2], pins[2])
    problems = []
    for kind, way in uniform.items():
        mine = {r: (place[r], polar_vector(board, geo[r], place[r], pins), word)
                for r, (k, pins, word) in parts.items() if k == kind}
        if way == "row":
            problems += polarity_rows(kind, mine, tol)
        else:
            problems += [polarity_way(board, geo[r], place[r], parts[r][1], r, kind, way, word)
                         for r, (_, _, word) in sorted(mine.items(), key=lambda kv: natural_key(kv[0]))
                         if not points_to(board, place[r].side, mine[r][1], way)]
    return problems


def polar_vector(board, geo, p, pins, rot=None):
    """Plus pad minus minus pad of a part placed as p (rot: another rotation), in plan mm."""
    a, k = (board.transform((geo["pads"][n]["x"], geo["pads"][n]["y"]), p.x, p.y, p.rot if rot is None else rot,
                            p.side) for n in pins)
    return a[0] - k[0], a[1] - k[1]


def minus_way(board, side, d):
    """The direction the minus pin points (from plus to minus), seen from the side the part sits on."""
    m = (-d[0], -d[1])
    return (-m[0], m[1]) if side != board.view else m


def points_to(board, side, d, way):
    """The minus pin points within 45° of `way`."""
    m, t = minus_way(board, side, d), AXES[way]
    return m[0] * t[0] + m[1] * t[1] > math.hypot(*m) * math.cos(math.radians(45)) + 1e-9


def polarity_rows(kind, parts, tol):
    """"row": {ref: (placement, plus - minus, word)} -> parts in a row or column whose plus pin points the other way
    than the first one's. LEDs keep the words the plan check always had."""
    problems, seen = [], set()
    for axis, name in ((1, "row"), (0, "column")):
        for ref, (p, _, _) in sorted(parts.items(), key=lambda kv: natural_key(kv[0])):
            c = (p.x, p.y)
            line = sorted((r for r, (q, _, _) in parts.items() if q.side == p.side and abs((q.x, q.y)[axis] - c[axis])
                           <= tol), key=lambda r: (parts[r][0].x, parts[r][0].y)[1 - axis])
            if len(line) < 2 or tuple(line) in seen:
                continue
            seen.add(tuple(line))
            first = parts[line[0]][1]
            other = [r for r in line[1:] if parts[r][1][0] * first[0] + parts[r][1][1] * first[1] < 0]
            if not other:
                continue
            if kind == "led":
                problems.append(f"LEDs in a {name} ({', '.join(line)}): anode of {', '.join(other)} points the other "
                                f"way than {line[0]} – turn them by 180°")
            else:
                problems.append(f"{kind.replace('_', ' ')}s in a {name} ({', '.join(line)}): {parts[line[0]][2]} of "
                                f"{', '.join(other)} points the other way than {line[0]} – turn "
                                f"{'it' if len(other) == 1 else 'them'} by 180°")
    return problems


def polarity_way(board, geo, p, pins, ref, kind, way, word):
    """The finding of a part whose minus pin does not point `way`: where it points, and the turn and the rotation in
    [place] that make it."""
    m = minus_way(board, p.side, polar_vector(board, geo, p, pins))
    points = max(AXES, key=lambda a: m[0] * AXES[a][0] + m[1] * AXES[a][1])
    turn = next(dt for dt in (90, 180, 270)
                if points_to(board, p.side, polar_vector(board, geo, p, pins, p.rot + dt), way))
    return (f"{ref} ({kind}): {word} points {points}, uniform {way} – turn it by {min(turn, 360 - turn)}° "
            f"(rot = {(p.rot + turn) % 360:g})")


# --- the third dimension: body height, lead length, mated plug; the mechanical model --------------------------------

EXITS = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1), "+z": None}   # +z: away from the board
EXIT_TOL_MM = 0.05     # a sideways plug whose far end lies less than this inside the outline reaches it


def _given_mm(v, low=None, above=False):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    return low is None or (v > low if above else v >= low)


def part_mech(part):
    """The third dimension of a parts entry, every field optional: `body.h_mm` (height of the body above the board, on
    the part's side), `lead.<pad or "*">.length_mm` (lead length below the seating plane, beside the cross-section of
    L-9), `mate` – the mated plug with its strain relief: `box` [x0, y0, x1, y1] in footprint mm (relative to the
    part's origin at 0° on TOP, as the geometry dump), `h_mm`, and `exit`, the direction the cable leaves the box:
    "+x", "-x", "+y", "-y", or "+z" away from the board. -> ({"h_mm", "leads": {pad: length}, "mate"} as far as the
    entry gives them, [what is wrong])."""
    part, out, bad = part or {}, {}, []
    if "body" in part:
        h = part["body"].get("h_mm") if isinstance(part["body"], dict) else None
        if _given_mm(h, 0):
            out["h_mm"] = float(h)
        else:
            bad.append("body.h_mm must be a height in mm, 0 or more")
    leads = {}
    for pad, lead in (part.get("lead") or {}).items():
        if isinstance(lead, dict) and "length_mm" in lead:
            if _given_mm(lead["length_mm"], 0, above=True):
                leads[str(pad)] = float(lead["length_mm"])
            else:
                bad.append(f"lead.{pad}.length_mm must be a length in mm, more than 0")
    if leads:
        out["leads"] = leads
    if "mate" in part:
        m = part["mate"] if isinstance(part["mate"], dict) else {}
        box, wrong = m.get("box"), []
        if not (isinstance(box, list) and len(box) == 4 and all(_given_mm(v) for v in box) and box[0] < box[2]
                and box[1] < box[3]):
            wrong.append("mate.box must be [x0, y0, x1, y1] in footprint mm with x0 < x1 and y0 < y1")
        if not isinstance(m.get("exit"), str) or m["exit"] not in EXITS:
            wrong.append(f"mate.exit must be one of {', '.join(EXITS)}")
        if "h_mm" in m and not _given_mm(m["h_mm"], 0):
            wrong.append("mate.h_mm must be a height in mm, 0 or more")
        if not wrong:
            out["mate"] = {"box": [float(v) for v in box], "exit": m["exit"]}
            if "h_mm" in m:
                out["mate"]["h_mm"] = float(m["h_mm"])
        bad += wrong
    return out, bad


def mate_shape(board, p, mate):
    """The mated plug of a part placed as p, in plan mm -> (its corners, its box, the plan direction of `exit` – None
    for "+z" –, the middle of its far end in that direction)."""
    x0, y0, x1, y1 = mate["box"]

    def at(x, y):
        return board.transform((x * MIL_PER_MM, y * MIL_PER_MM), p.x, p.y, p.rot, p.side)
    corners = [at(x0, y0), at(x1, y0), at(x1, y1), at(x0, y1)]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    box = (min(xs), min(ys), max(xs), max(ys))
    d = EXITS[mate["exit"]]
    if d is None:
        return corners, box, None, None
    fx, fy = (x0 + x1) / 2 + d[0] * (x1 - x0) / 2, (y0 + y1) / 2 + d[1] * (y1 - y0) / 2
    a, b = at(fx, fy), at(fx + d[0], fy + d[1])
    return corners, box, (b[0] - a[0], b[1] - a[1]), a


def exit_way(d):
    """A plan direction: "+x", "-x", "+y", "-y" ("+z" for None); turned by an angle that is no multiple of 90°, the
    unit vector [dx, dy]."""
    if d is None:
        return "+z"
    for name, v in EXITS.items():
        if v and math.dist(d, v) < 1e-6:
            return name
    return [round(d[0], 4), round(d[1], 4)]


def inside_by(outline, point, d):
    """How far `point` lies inside the outline along the direction d: its way to the outline's edge (mm), 0 on or
    outside the outline."""
    from shapely.geometry import LineString, Point
    pt = Point(point)
    if not outline.contains(pt):
        return 0.0
    x0, y0, x1, y1 = outline.bounds
    reach = 2 * math.hypot(x1 - x0, y1 - y0) + 1
    n = math.hypot(*d)
    ray = LineString([point, (point[0] + d[0] / n * reach, point[1] + d[1] / n * reach)])
    hit = ray.intersection(outline.exterior)
    return 0.0 if hit.is_empty else pt.distance(hit)


def mate_findings(board, geo, place, boxes, design):
    """Mated plugs (`mate` of the parts entry) of the placed parts. The plug box, turned and placed with its part, runs
    into no other part's box on its side – into an SMD part's box at most silk_overlap_mm, as two SMD boxes may – and
    into no other part's plug; a plug whose cable leaves sideways reaches the outline in that direction, measured
    from the middle of its far end. edge_ok lifts neither. Fields of the third dimension that are wrong are named."""
    problems, plugs = [], {}
    for ref in sorted((r for r in place if r in boxes), key=natural_key):
        part = design.part(ref) if ref in design.comps else None
        if not part:
            continue
        mech, bad = part_mech(part)
        problems += [f"{ref}: parts entry {design.entry_key(ref)}: {b}" for b in bad]
        if "mate" in mech:
            plugs[ref] = mate_shape(board, place[ref], mech["mate"])
    if not plugs:
        return problems
    outline, tol = outline_polygon(board), board.silk_overlap_mm
    order = list(plugs)
    for i, ref in enumerate(order):
        _, box, d, far = plugs[ref]
        side = place[ref].side
        for other in sorted(boxes, key=natural_key):
            if other == ref or place[other].side != side or not overlap(box, boxes[other]):
                continue
            found = f"{ref}: mated plug reaches into {other} ({side})"
            depth = overlap_depth(box, boxes[other])
            if not tol:
                problems.append(found)
            elif through_hole(geo[other]):
                problems.append(f"{found} – {depth:.2f} mm ({other} through-hole: silk_overlap_mm does not apply)")
            elif round(depth, 6) > tol:
                problems.append(f"{found} – {depth:.2f} mm (silk_overlap_mm {tol:g})")
        problems += [f"{ref}: mated plug reaches into the mated plug of {other} ({side})" for other in order[i + 1:]
                     if place[other].side == side and overlap(box, plugs[other][1])]
        if d is not None:
            inside = inside_by(outline, far, d)
            if inside >= EXIT_TOL_MM:
                problems.append(f"{ref}: mated plug leaves towards {exit_way(d)} but ends {inside:.1f} mm inside the "
                                "outline")
    return problems


def mech_model(board, geo, place, boxes, design, unplaced):
    """The board in three dimensions, for the project's mechanics stage and enclosure scripts (`mech_<board>.json`):
    plan mm seen from `view`; outline, holes, tooling holes, thickness_mm; per placed part its side, position, box
    (the footprint's, silkscreen included) and, where its parts entry knows them, h_mm, the through-hole leads with
    their protrusion (lead length - thickness_mm, per lead and the largest) and the mated plug (box, h_mm, exit as a
    plan direction); the parts the plan leaves to the auto-layout by name. Unknown values are left out."""
    parts = {}
    for ref in sorted((r for r in place if r in boxes), key=natural_key):
        p = place[ref]
        mech, _ = part_mech(design.part(ref) if ref in design.comps else None)
        row = {"side": p.side, "x": p.x, "y": p.y, "rot": p.rot, "box": [round(v, 3) for v in boxes[ref]]}
        if "h_mm" in mech:
            row["h_mm"] = mech["h_mm"]
        lengths, pads, leads = mech.get("leads", {}), geo[ref].get("pads", {}), []
        for num in sorted(pads, key=natural_key):
            length = lengths.get(num, lengths.get("*"))
            if not pads[num].get("tht") or length is None:
                continue
            for q in geo[ref].get("pads_same_number", {}).get(num) or [pads[num]]:
                x, y = board.transform((q["x"], q["y"]), p.x, p.y, p.rot, p.side)
                leads.append({"pad": num, "x": round(x, 3), "y": round(y, 3),
                              "protrusion_mm": round(length - board.thickness_mm, 3)})
        if leads:
            row["protrusion_mm"] = max(q["protrusion_mm"] for q in leads)
            row["leads"] = leads
        if "mate" in mech:
            _, box, d, _ = mate_shape(board, p, mech["mate"])
            row["mate"] = {"box": [round(v, 3) for v in box], "exit": exit_way(d)}
            if "h_mm" in mech["mate"]:
                row["mate"]["h_mm"] = mech["mate"]["h_mm"]
        parts[ref] = row
    return {"board": board.name, "units": "mm", "view": board.view, "thickness_mm": board.thickness_mm,
            "outline": [[round(x, 4), round(y, 4)] for x, y in board.outline],
            "holes": [{"x": h["x"], "y": h["y"], "d": h["d"]} for h in board.holes],
            "tooling": [{"x": tx, "y": ty, "d": board.tooling_d} for tx, ty in board.tooling],
            "parts": parts, "unplaced": list(unplaced)}


def render(cfg, board, geo, place, boxes, tht, problems, plugs=None):
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
            if own and r in (plugs or {}):   # the mated plug, dashed
                m = plugs[r]
                mx0, mx1 = (m[0], m[2]) if mirror == 1 else (-m[2], -m[0])
                ax.add_patch(Rectangle((mx0, m[1]), mx1 - mx0, m[3] - m[1], fc="none", ec=col, lw=1, ls="--"))
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
    out = {name: {"width_mm": c["width_mm"], "nets": []} for name, c in board.net_classes.items()}
    for net, v in sorted(nets.items()):
        i = max(v["i_max_a"], v.get("i_peak_a") or 0)
        cls = board.force_class.get(net) or next(n for n, c in board.net_classes.items() if i >= c["min_a"])
        out[cls]["width_mm"] = round(max(out[cls]["width_mm"], ipc2221_width_mm(i)), 2)
        out[cls]["nets"].append(net)
    path = cfg.artifact(f"pcb_netclasses_{board.name}.json")
    path.write_text(json.dumps(out, indent=1))
    for name, c in out.items():
        if c["nets"] and name != list(out)[-1]:
            print(f"  net class {name}: {c['width_mm']} mm – {', '.join(c['nets'])}")
    return out


def plan(cfg, board):
    design = Design.from_config(cfg)
    geo = plan_geometry(cfg, board, design)
    if note := move_note(cfg, board):
        print(f"  {note}")
    place, boxes, tht, unplaced, missing = build_plan(cfg, board, geo)
    problems = [f"{r}: in the plan but not in the footprint geometry (edakit pcb parts --write, then dump)"
                for r in missing]
    say_unmeasured(geo, place)
    problems += check_plan(cfg, board, geo, place, boxes, tht)
    problems += [f"L-12 {p}" for p in check_handover(board, design, place, boxes)]
    holes = checks.Report()      # P-7 on the plan's geometry: a hole that does not take its lead is a plan finding
    checks.check_holes(design, holes, lambda r: (geo[r], GEOMETRY_FROM.get(geo[r].get("source"), "{}").format(
        geo[r].get("footprint")) if geo[r].get("source") else "pcb dump") if r in geo else (None, None))
    problems += [f"P-7 {m}" for _, m in holes.errors]
    for kind, found in (("pending", holes.pending), ("warning", holes.warnings)):
        for _, m in found:
            print(f"  P-7 {kind}: {m}")
    for p in problems:
        print("  !", p)
    if board.uniform is not None:   # the board asks for its kinds: name the parts the polarity check cannot judge
        skipped = []
        polarity_findings(board, geo, place, design, skipped=skipped)
        for kind in dict.fromkeys(k for _, k in skipped):
            print("  uniform: skipped – not exactly one anode/plus and one cathode/minus pin: "
                  + ", ".join(sorted((r for r, k in skipped if k == kind), key=natural_key)) + f" ({kind})")
    print(f"  {len(place)} fixed parts, {len(unplaced)} for the auto-layout; airline length of the fixed parts "
          f"(without {design.ground}): {wirelength(board, geo, place, design.ground) / 1000:.2f} m")
    mech = mech_model(board, geo, place, boxes, design, unplaced)
    plugs = {r: row["mate"]["box"] for r, row in mech["parts"].items() if "mate" in row}
    print(f"  preview -> {render(cfg, board, geo, place, boxes, tht, problems, plugs)}")
    cfg.artifact(f"pcb_plan_{board.name}.json").write_text(json.dumps(
        {r: {"x": p.x, "y": p.y, "rot": p.rot, "side": p.side} for r, p in place.items()}, indent=1))
    path = cfg.artifact(f"mech_{board.name}.json")
    path.write_text(json.dumps(mech, indent=1))
    if any(k in row for row in mech["parts"].values() for k in ("h_mm", "leads", "mate")):
        print(f"  mechanical model -> {path}")
    net_classes(cfg, board)
    return problems


# --- place: the parts the circuit ties to a host, next to that host; with --rest every other part ------------------

PLACE_STEPS_PER_MM = 10            # pcb place: spots on a 0.1 mm grid of the plan
PLACE_ROTATIONS = (0, 90, 180, 270)
PLACE_EPS = 1e-6                   # boxes that only touch count as touching: a spot keeps clear of them
PLACE_TRIES = 500                  # spots the full plan check may turn down before a part counts as without one
PLACE_REST_GRID_MM = 0.5           # --rest: the whole board on this grid first ...
PLACE_REST_SEEDS = 8               # ... then the plan grid around its best spots
PLACE_REST_TRIES = 10              # --rest: spots the plan check may turn down for a move – or, once a spot is clean
                                   # but a part tied to the part found none next to it, while a better one is sought
PLACE_REST_PASSES = 4              # --rest: improvement passes at most
PLACE_REST_EPS = 1e-3              # mm: an airline length shorter by less than this counts as no shorter
PLACE_HEADER = re.compile(r"^\s*\[\s*place\s*\]\s*(#.*)?$")
TABLE_HEADER = re.compile(r"""^\s*\[\[?\s*[\w."' -]+\s*\]\]?\s*(#.*)?$""")


def declared_hosts(board, design):
    """part -> [hosts]: layout.near of the graph first, then [near] of the board file."""
    out = {}
    pairs = [(r.part, r.others) for r in handover.requirements(design, board.name) if r.kind == "near"]
    for part, hosts in pairs + list(board.near.items()):
        mine = out.setdefault(part, [])
        mine += [h for h in hosts if h not in mine]
    return out


def missing_decoupling(board, reqs, boxes):
    """The decoupling requirements of L-12 the plan does not keep yet – one capacitor of its own per IC within near_mm,
    matched as check_handover matches them."""
    ics = [r for r in reqs if r.kind == "decoupling" and r.part in boxes]
    out = []
    for net in sorted({r.net for r in ics}):
        close = {r.part: [c for c in r.others if c in boxes and box_gap(boxes[c], boxes[r.part]) <= board.near_mm]
                 for r in ics if r.net == net}
        owner = {}

        def assign(ic, seen):
            for c in close[ic]:
                if c not in seen:
                    seen.add(c)
                    if c not in owner or assign(owner[c], seen):
                        owner[c] = ic
                        return True
            return False
        out += [r for r in ics if r.net == net and not assign(r.part, set())]
    return out


def tie_pads(pin_net, ground, geo, part, host, supply=None):
    """The pads that should face each other: (primary, secondary), each [(net, pads of part, pins of host)].
    Decoupling (supply): the supply, ground as the tie-break. Otherwise the nets part and host share without ground –
    or ground when that is all they share –, no tie-break."""
    def pads(ref, net):
        return [n for n in sorted(geo[ref]["pads"], key=natural_key) if pin_net.get(f"{ref}.{n}") == net]
    shared = ({pin_net.get(f"{part}.{n}") for n in geo[part]["pads"]}
              & {pin_net.get(f"{host}.{n}") for n in geo[host]["pads"]}) - {None}
    primary = [supply] if supply else sorted(shared - {ground}) or sorted(shared & {ground})
    secondary = [ground] if supply and ground in shared else []
    rows = lambda nets: [(n, pads(part, n), pads(host, n)) for n in nets if pads(part, n) and pads(host, n)]  # noqa
    return rows(primary), rows(secondary)


def plan_state(board, geo, place):
    """Boxes and through-hole pads per side of the parts in place, as build_plan computes them."""
    boxes = {r: part_box(board, geo[r], p) for r, p in place.items() if r in geo}
    tht = {"top": [], "bottom": []}
    for r, p in place.items():
        for pad in geo.get(r, {}).get("pads", {}).values():
            if pad["tht"]:
                tht[p.side].append(board.transform((pad["x"], pad["y"]), p.x, p.y, p.rot, p.side))
    return boxes, tht


def plan_findings(cfg, board, geo, design, place, boxes, tht):
    from collections import Counter
    return Counter(check_plan(cfg, board, geo, place, boxes, tht) + check_handover(board, design, place, boxes))


def gap_to(corners, b):
    """box_gap of every box of `corners` – arrays x0, y0, x1, y1, plan mm – to the box b."""
    import numpy as np
    c0, c1, c2, c3 = corners
    return np.maximum.reduce([b[0] - c2, c0 - b[2], b[1] - c3, c1 - b[3], np.zeros_like(c0)])


def free_mask(board, geo, place, boxes, tht, part, side, corners, inner=None):
    """Which of the boxes `corners` (arrays x0, y0, x1, y1, plan mm) part may take on `side`: the plan's rules towards
    what is placed – overlaps with silk_overlap_mm and on_headers, holes, tooling holes, THT pins of the other side –
    and roughly the outline (the box's corners inside `inner`, the outline 0.3 mm in, unless edge_ok) -> array of
    bool."""
    import numpy as np
    from shapely import contains_xy
    c0, c1, c2, c3 = corners
    zero = np.zeros_like(c0)
    ok = np.ones(c0.shape, bool)
    header = header_pins(board, geo, place)
    smd = not through_hole(geo[part])
    for r in place:
        if r not in boxes or place[r].side != side:
            continue
        b = boxes[r]
        touch = ((c0 < b[2] + PLACE_EPS) & (b[0] < c2 + PLACE_EPS)
                 & (c1 < b[3] + PLACE_EPS) & (b[1] < c3 + PLACE_EPS))
        if header.get(r) and smd:            # under a module on pin headers: clear of its pins
            gap = np.minimum.reduce([np.maximum.reduce([px - c2, c0 - px, py - c3, c1 - py, zero])
                                     for px, py in header[r].values()])
            ok &= ~touch | (gap >= board.header_keep_mm + PLACE_EPS)
        elif board.silk_overlap_mm and smd and not through_hole(geo[r]):
            depth = np.minimum.reduce([c2 - b[0], b[2] - c0, c3 - b[1], b[3] - c1])
            ok &= ~touch | (depth <= board.silk_overlap_mm - PLACE_EPS)
        else:
            ok &= ~touch
    for cx, cy, r in [(h["x"], h["y"], h["keep"]) for h in board.holes] + \
            [(tx, ty, board.tooling_keep) for tx, ty in board.tooling]:
        dx = np.maximum.reduce([c0 - cx, cx - c2, zero])
        dy = np.maximum.reduce([c1 - cy, cy - c3, zero])
        ok &= np.hypot(dx, dy) > r + PLACE_EPS
    for px, py in tht["bottom" if side == "top" else "top"]:
        ok &= ~((c0 - 0.5 < px) & (px < c2 + 0.5) & (c1 - 0.5 < py) & (py < c3 + 0.5))
    if part not in board.edge_ok:
        inner = outline_polygon(board).buffer(-0.3) if inner is None else inner
        for xs, ys in ((c0, c1), (c2, c1), (c2, c3), (c0, c3)):
            at = np.flatnonzero(ok)        # only where nothing else ruled the spot out: the costly test
            ok[at] = contains_xy(inner, xs[at], ys[at])
    return ok


def spot_candidates(board, geo, place, boxes, tht, part, hosts, rows):
    """Every spot of part within near_mm of all hosts, on the side of the first, at 0/90/180/270°, on the plan grid,
    that keeps the plan's rules towards what is placed (free_mask: overlaps with silk_overlap_mm and on_headers, holes,
    tooling holes, THT pins of the other side, roughly the outline) -> [(x, y, rot)], the best first: the pads of
    `rows` nearest to the host's pins – with a tie-break (decoupling) to 0.1 mm, then the tie-break pads –, then
    rotation, y, x."""
    import numpy as np

    from .config import Placement
    host = place[hosts[0]]
    side, n = host.side, board.near_mm
    S = PLACE_STEPS_PER_MM
    primary, secondary = rows
    pins = {num: board.transform((q["x"], q["y"]), host.x, host.y, host.rot, host.side)
            for num, q in geo[hosts[0]]["pads"].items()}
    out = []
    for k, rot in enumerate(PLACE_ROTATIONS):
        bx0, by0, bx1, by1 = part_box(board, geo[part], Placement(0, 0, rot, side))
        hb = boxes[hosts[0]]
        kx = np.arange(math.ceil((hb[0] - n - bx1) * S), math.floor((hb[2] + n - bx0) * S) + 1)
        ky = np.arange(math.ceil((hb[1] - n - by1) * S), math.floor((hb[3] + n - by0) * S) + 1)
        X, Y = (a.ravel() / S for a in np.meshgrid(kx, ky))
        corners = (X + bx0, Y + by0, X + bx1, Y + by1)
        ok = free_mask(board, geo, place, boxes, tht, part, side, corners)
        for h in hosts:
            ok &= gap_to(corners, boxes[h]) <= n - PLACE_EPS
        X, Y = X[ok], Y[ok]

        def dist(pairs):
            total = np.zeros_like(X)
            for _, mine, theirs in pairs:
                d = np.full(X.shape, np.inf)
                for a in mine:
                    q = geo[part]["pads"][a]
                    ox, oy = board.transform((q["x"], q["y"]), 0, 0, rot, side)
                    for b in theirs:
                        d = np.minimum(d, np.hypot(X + ox - pins[b][0], Y + oy - pins[b][1]))
                total += d
            return total
        if primary:
            first, second = dist(primary), dist(secondary)
        else:   # nothing shared: as close to the host's box as possible, then centre to centre
            first = np.maximum.reduce([hb[0] - (X + bx1), X + bx0 - hb[2], hb[1] - (Y + by1), Y + by0 - hb[3],
                                       np.zeros_like(X)])
            second = np.hypot(X + (bx0 + bx1) / 2 - (hb[0] + hb[2]) / 2, Y + (by0 + by1) / 2 - (hb[1] + hb[3]) / 2)
        out.append((np.round(first, 1 if secondary else 6), np.round(second, 6), np.full(X.shape, k), Y, X))
    first, second, rot, Y, X = (np.concatenate(a) for a in zip(*out))
    order = np.lexsort((X, Y, rot, second, first))
    return [(float(X[i]), float(Y[i]), PLACE_ROTATIONS[rot[i]]) for i in order]


def find_spot(cfg, board, geo, design, state, part, hosts, rows):
    """The first spot of spot_candidates where check_plan and check_handover report nothing new -> (Placement or None,
    the first new finding of the best spot turned down)."""
    from shapely.geometry import box

    from .config import Placement
    place, boxes, tht = state
    side = place[hosts[0]].side
    edge = outline_polygon(board).exterior
    inner = outline_polygon(board).buffer(-0.3)
    at_edge = any(r.kind == "edge" and r.part == part for r in handover.requirements(design, board.name))
    before = plan_findings(cfg, board, geo, design, place, boxes, tht)
    tried, why = 0, None
    for x, y, rot in spot_candidates(board, geo, place, boxes, tht, part, hosts, rows):
        p = Placement(x, y, rot, side, auto=True)
        b = part_box(board, geo[part], p)
        if part not in board.edge_ok and not inner.contains(box(*b)):
            continue
        if at_edge and box(*b).distance(edge) > board.edge_mm:
            continue
        pads = [board.transform((q["x"], q["y"]), x, y, rot, side) for q in geo[part]["pads"].values() if q["tht"]]
        new = plan_findings(cfg, board, geo, design, {**place, part: p}, {**boxes, part: b},
                            {s: v + (pads if s == side else []) for s, v in tht.items()}) - before
        if not new:
            return p, None
        why = why or sorted(new)[0]   # the best spot's first new finding, for the message
        tried += 1
        if tried >= PLACE_TRIES:
            break
    return None, why


def auto_place(cfg, board, geo, design, only=None, rest=False, report=None):
    """pcb place: a spot for every part that is not in [place] (or is there with auto = true) but tied to a host –
    by layout.near of the graph, [near] of the board file (in that order, by designator), then the decoupling of L-12:
    an IC without a capacitor of its own within near_mm gets the first free capacitor between its supply and ground
    that declares no host. The spot: on the host's side, within near_mm of every host, at 0/90/180/270°, the part's
    pad on a net it shares with the host as close as possible to the host's pin on that net (decoupling: the supply,
    ground pad to the nearest ground pin as the tie-break); accepted only where the plan check reports nothing new;
    each placed part is an obstacle for the next. rest (--rest): every other part of the board as well, by airline
    length (Placing.rest, Placing.improve); report gets what that did. A row with auto = true is placed anew; one whose
    part has no host any more (without rest), or no spot, stays where it is – an obstacle like any row.
    -> ([(ref, Placement, why)], problems)."""
    keep = lambda r: only is None or r in only  # noqa: E731
    moving = {r for r, p in board.place.items() if p.auto and keep(r)}
    stuck = []
    while True:
        rows, problems = _auto_place(cfg, board, geo, design, moving, keep, rest, report)
        placed = {r for r, _, _ in rows}
        if moving <= placed:
            return rows, [text for _, text in stuck + problems]
        stuck += [(r, f"{text} – its row stays where it is") for r, text in problems if r in moving - placed]
        moving &= placed


def _auto_place(cfg, board, geo, design, moving, keep, rest=False, report=None):
    s = Placing(cfg, board, geo, design, moving, keep)
    while s.tied() or (rest and s.rest()):
        pass
    if rest:
        s.improve(report)
    s.loose()
    return s.rows, s.problems


def assembled_sides(cfg):
    """The sides --rest places parts on: [release] assembly sides, top first; without the key – or with no side in
    it – both."""
    sides = cfg.release.get("assembly", {}).get("sides", ["top", "bottom"])
    return [s for s in ("top", "bottom") if s in sides] or ["top", "bottom"]


def part_nets(design, geo, ref):
    """{net: [pad numbers]}: the pads of a part on the nets of the graph, ground left out – what airline lengths are
    measured on."""
    out = {}
    for num in sorted(geo[ref]["pads"], key=natural_key):
        net = design.pin_net.get(f"{ref}.{num}")
        if net and net != design.ground:
            out.setdefault(net, []).append(num)
    return out


def net_pads(board, geo, design, place):
    """{net: [(x, y)]}: the pads of the placed parts per net of the graph, ground left out, plan mm."""
    out = {}
    for ref, p in place.items():
        for num, q in geo.get(ref, {}).get("pads", {}).items():
            net = design.pin_net.get(f"{ref}.{num}")
            if net and net != design.ground:
                out.setdefault(net, []).append(board.transform((q["x"], q["y"]), p.x, p.y, p.rot, p.side))
    return out


def mst_lengths(fixed, moving):
    """The length of the minimum spanning tree over the points `fixed` [(x, y)] and, per row, the points of `moving`
    (array C x k x 2) – Prim's algorithm as wirelength runs it, for every row at once -> array of C, mm."""
    import numpy as np
    c = len(moving)
    fixed = np.asarray(fixed, float).reshape(1, -1, 2)
    pts = np.concatenate([np.broadcast_to(fixed, (c, fixed.shape[1], 2)), moving], axis=1)
    n, total = pts.shape[1], np.zeros(c)
    if n < 2 or not c:
        return total
    rows = np.arange(c)
    inside = np.zeros((c, n), bool)
    inside[:, 0] = True
    near = np.hypot(pts[:, :, 0] - pts[:, :1, 0], pts[:, :, 1] - pts[:, :1, 1])
    for _ in range(n - 1):
        u = np.argmin(np.where(inside, np.inf, near), axis=1)
        total += near[rows, u]
        inside[rows, u] = True
        near = np.minimum(near, np.hypot(pts[:, :, 0] - pts[rows, u, 0][:, None],
                                         pts[:, :, 1] - pts[rows, u, 1][:, None]))
    return total


def mst_edges(points):
    """The lengths of the edges of the minimum spanning tree over `points` [(x, y)] (Prim's algorithm) -> array."""
    import numpy as np
    p = np.asarray(points, float).reshape(-1, 2)
    inside, out = np.zeros(len(p), bool), []
    if len(p):
        inside[0] = True
        near = np.hypot(p[:, 0] - p[0, 0], p[:, 1] - p[0, 1])
    for _ in range(len(p) - 1):
        u = int(np.argmin(np.where(inside, np.inf, near)))
        out.append(near[u])
        inside[u] = True
        near = np.minimum(near, np.hypot(p[:, 0] - p[u, 0], p[:, 1] - p[u, 1]))
    return np.array(out)


def mst_length(points):
    return float(mst_edges(points).sum())


def airline_terms(board, geo, design, place, part):
    """What the airline length of `part` is measured against: its nets {net: its pads} (part_nets), the pads of the
    placed parts on them {net: [(x, y)]} and the edges of their minimum spanning trees {net: lengths}."""
    nets, pads = part_nets(design, geo, part), net_pads(board, geo, design, place)
    fixed = {n: pads.get(n, []) for n in nets}
    return nets, fixed, {n: mst_edges(fixed[n]) for n in nets}


def pad_points(board, geo, part, nums, X, Y, rot, side):
    """The pads `nums` of part with its origin at (X, Y) – arrays –, rot, side -> array C x k x 2, plan mm."""
    import numpy as np
    offsets = [board.transform((geo[part]["pads"][n]["x"], geo[part]["pads"][n]["y"]), 0, 0, rot, side) for n in nums]
    return np.stack([np.stack([X + ox, Y + oy], axis=1) for ox, oy in offsets], axis=1)


def added_airline(board, geo, part, terms, X, Y, rot, side):
    """What the pads of `part` at (X, Y) – arrays –, rot, side add to the minimum spanning trees of their nets, terms
    as airline_terms gives them -> array, mm."""
    import numpy as np
    X, Y = np.asarray(X, float), np.asarray(Y, float)
    nets, fixed, trees = terms
    total = np.zeros(len(X))
    for net, nums in nets.items():
        total += mst_lengths(fixed[net], pad_points(board, geo, part, nums, X, Y, rot, side)) - trees[net].sum()
    return total


def airline_floor(board, geo, part, terms, X, Y, rot, side):
    """A lower bound of added_airline, cheaper: per net the shortest distance d from the part's pads to the placed
    pads, less what the tree's edges longer than d could give up – a tree's length is the integral, over the
    threshold, of the number of its parts minus one, and the pads cannot join the tree below d nor more of it than
    there is above d. A net without placed pads counts as in added_airline."""
    import numpy as np
    nets, fixed, trees = terms
    total = np.zeros(len(X))
    for net, nums in nets.items():
        pts = pad_points(board, geo, part, nums, X, Y, rot, side)
        if not fixed[net]:
            total += mst_lengths([], pts)
            continue
        f = np.asarray(fixed[net], float)
        d = np.hypot(pts[:, :, None, 0] - f[:, 0], pts[:, :, None, 1] - f[:, 1]).min(axis=(1, 2))
        total += d - np.maximum(trees[net][None, :] - d[:, None], 0).sum(axis=1)
    return total


def rest_spots(board, geo, design, state, part, sides, near=(), edge=False, below=None):
    """Every spot free_mask leaves `part`: on the assembled `sides`, at 0/90/180/270°, its box inside the outline's
    bounds (an edge_ok part: its pads on the board), within near_mm of one part of each group of `near`, with `edge`
    within edge_mm of the outline – on a grid of PLACE_REST_GRID_MM over the board, and on the plan grid around the
    PLACE_REST_SEEDS best of those; with `below` only those shorter than that by PLACE_REST_EPS (airline_floor skips
    the others first). -> [(x, y, rot, side, airline)], the shortest airline length first – what the part's pads add
    to the minimum spanning trees of their nets over the placed pads (graph nets, ground left out) –, then side (in
    the order of `sides`), rotation, y, x."""
    import numpy as np
    import shapely

    from .config import Placement
    place, boxes, tht = state
    S, g = PLACE_STEPS_PER_MM, round(PLACE_REST_GRID_MM * PLACE_STEPS_PER_MM)
    outline = outline_polygon(board)
    x0, y0, x1, y1 = outline.bounds
    inner = outline.buffer(-0.3)
    shapely.prepare(outline)
    shapely.prepare(inner)
    terms = airline_terms(board, geo, design, place, part)
    groups = {}     # (side, rotation) -> the box at the origin, the range of grid indices of the origin in x and y
    for si, side in enumerate(sides):
        for ri, rot in enumerate(PLACE_ROTATIONS):
            b = part_box(board, geo[part], Placement(0, 0, rot, side))
            groups[si, ri] = (b, math.ceil((x0 - b[0]) * S), math.floor((x1 - b[2]) * S),
                              math.ceil((y0 - b[1]) * S), math.floor((y1 - b[3]) * S))

    def free(si, ri, kx, ky):
        """The grid indices kx, ky of the origin in group (si, ri) where the part may go -> (kx, ky, airline)."""
        side, rot, b = sides[si], PLACE_ROTATIONS[ri], groups[si, ri][0]
        X, Y = kx / S, ky / S
        corners = (X + b[0], Y + b[1], X + b[2], Y + b[3])
        ok = free_mask(board, geo, place, boxes, tht, part, side, corners, inner)
        for refs in near:
            ok &= np.logical_or.reduce([gap_to(corners, boxes[r]) <= board.near_mm - PLACE_EPS for r in refs])
        if part in board.edge_ok:
            for q in geo[part]["pads"].values():
                ox, oy = board.transform((q["x"], q["y"]), 0, 0, rot, side)
                ok &= shapely.contains_xy(outline, X + ox, Y + oy)
        if edge and ok.any():
            at = np.flatnonzero(ok)
            ok[at] = shapely.distance(shapely.box(*(c[at] for c in corners)), outline.exterior) <= board.edge_mm
        if below is not None:
            at = np.flatnonzero(ok)
            ok[at] = airline_floor(board, geo, part, terms, X[at], Y[at], rot, side) < below - PLACE_REST_EPS
        kx, ky = kx[ok], ky[ok]
        a = added_airline(board, geo, part, terms, kx / S, ky / S, rot, side)
        if below is not None:
            shorter = a < below - PLACE_REST_EPS
            kx, ky, a = kx[shorter], ky[shorter], a[shorter]
        return np.full(len(kx), si), np.full(len(kx), ri), kx, ky, a

    def ordered(found):
        """The spots free found, in the order of rest_spots -> arrays side, rotation, kx, ky, airline."""
        si, ri, kx, ky, a = (np.concatenate(v) for v in zip(*found))
        order = np.lexsort((kx, ky, ri, si, np.round(a, 6)))
        return si[order], ri[order], kx[order], ky[order], a[order]

    coarse = []
    for (si, ri), (_, lx, hx, ly, hy) in groups.items():
        kx, ky = np.meshgrid(np.arange(-(-lx // g) * g, hx + 1, g), np.arange(-(-ly // g) * g, hy + 1, g))
        coarse.append(free(si, ri, kx.ravel(), ky.ravel()))
    si, ri, kx, ky, _ = (v[:PLACE_REST_SEEDS] for v in ordered(coarse))
    fine, d = [], np.arange(1 - g, g)      # the plan grid between a seed and its neighbours on the coarse grid
    dx, dy = (v.ravel() for v in np.meshgrid(d, d))
    for s, r in sorted({(int(a), int(b)) for a, b in zip(si, ri)}):
        seeds = (si == s) & (ri == r)
        _, lx, hx, ly, hy = groups[s, r]
        fx, fy = (kx[seeds][:, None] + dx).ravel(), (ky[seeds][:, None] + dy).ravel()
        inside = (lx <= fx) & (fx <= hx) & (ly <= fy) & (fy <= hy) & ((fx % g != 0) | (fy % g != 0))
        pts = np.unique(np.stack([fx[inside], fy[inside]], axis=1), axis=0)
        fine.append(free(s, r, pts[:, 0], pts[:, 1]))
    si, ri, kx, ky, a = ordered(coarse + fine)
    for i in range(len(a)):
        yield int(kx[i]) / S, int(ky[i]) / S, PLACE_ROTATIONS[ri[i]], sides[si[i]], float(a[i])


class Placing:
    """pcb place at work: the rows it holds – place: the fixed ones and what it placed so far, with their boxes and the
    through-hole pads per side (tht) as build_plan computes them –, the rows it adds (rows: ref, Placement, why), the
    parts it could not place (problems: ref, text). moving: the auto rows it places anew; keep: the parts it may place
    (--only)."""

    def __init__(self, cfg, board, geo, design, moving, keep):
        self.cfg, self.board, self.geo, self.design, self.keep = cfg, board, geo, design, keep
        self.place = {r: p for r, p in board.place.items() if r not in moving}
        self.boxes, self.tht = plan_state(board, geo, self.place)
        names = design.joined_nets()
        self.pin_net = {r: names.get(n, n) for r, n in design.pin_net.items()}
        self.hosts_of = declared_hosts(board, design)
        self.reqs = handover.requirements(design, board.name)
        self.rows, self.problems, self.failed, self.tried = [], [], set(), set()
        near = {r.part for r in self.reqs if r.kind == "near"}
        self.jobs = sorted((d for d in self.hosts_of if d not in self.place and keep(d)),
                           key=lambda d: (d not in near, natural_key(d)))
        self.hosted = []     # the hosts of the parts placed next to one
        self.airline = []    # the parts --rest placed by airline length, in their order
        self.nets = {}       # part -> the nets of its pins in the graph, ground left out (a net once per pin)
        for pin, net in design.pin_net.items():
            if net != design.ground:
                self.nets.setdefault(pin.partition(".")[0], []).append(net)

    def copy(self):
        """A copy to try a spot on: what it changes stays its own."""
        twin = copy.copy(self)
        twin.place, twin.boxes, twin.tht = dict(self.place), dict(self.boxes), {s: list(v) for s, v in self.tht.items()}
        twin.rows, twin.problems, twin.jobs = list(self.rows), list(self.problems), list(self.jobs)
        twin.hosted, twin.airline = list(self.hosted), list(self.airline)
        twin.failed, twin.tried = set(self.failed), set(self.tried)
        return twin

    def adopt(self, twin):
        vars(self).update(vars(twin))

    def state(self):
        return self.place, self.boxes, self.tht

    def add(self, part, p):
        self.place[part] = p
        self.boxes[part] = part_box(self.board, self.geo[part], p)
        self.tht[p.side] += [self.board.transform((q["x"], q["y"]), p.x, p.y, p.rot, p.side)
                             for q in self.geo[part]["pads"].values() if q["tht"]]

    def remove(self, part):
        del self.place[part]
        self.boxes, self.tht = plan_state(self.board, self.geo, self.place)

    def findings(self):
        return plan_findings(self.cfg, self.board, self.geo, self.design, *self.state())

    def put(self, part, hosts, supply=None):
        board, geo = self.board, self.geo
        missing = [d for d in (part, *hosts) if d not in geo]
        if missing:
            self.problems.append((part, f"{part}: {', '.join(missing)} not in the footprint geometry (edakit pcb parts "
                                        "--write, then dump)"))
            self.failed.add(part)
            return
        pairs = tie_pads(self.pin_net, self.design.ground, geo, part, hosts[0], supply)
        p, why = find_spot(self.cfg, board, geo, self.design, self.state(), part, hosts, pairs)
        pins = "; ".join(f"pin{'s' * (len(theirs) > 1)} {', '.join(theirs)}, {net}" for net, _, theirs in pairs[0])
        if p is None:
            self.problems.append((part, f"{part}: no free spot within near_mm {board.near_mm:g} of {hosts[0]}"
                                        + (f" ({pins})" if pins else "")
                                        + (f" – the plan check: {why}" if why else "")))
            self.failed.add(part)
            return
        self.add(part, p)
        self.hosted += hosts
        host = self.place[hosts[0]]
        near = []
        for net, mine, theirs in pairs[0]:
            d, a, b = min((math.dist(board.transform((geo[part]["pads"][a]["x"], geo[part]["pads"][a]["y"]),
                                                     p.x, p.y, p.rot, p.side),
                                     board.transform((geo[hosts[0]]["pads"][b]["x"], geo[hosts[0]]["pads"][b]["y"]),
                                                     host.x, host.y, host.rot, host.side)), a, b)
                          for a in mine for b in theirs)
            near.append(f"pad {a} {d:.1f} mm from {hosts[0]}.{b} ({net})")
        what = f"decoupling of {hosts[0]} on {supply}" if supply else f"next to {', '.join(hosts)}"
        self.rows.append((part, p, what + (": " + ", ".join(near) if near else "")))

    def tied(self):
        """One round of the parts tied to a host: each whose declared hosts are all placed, then the decoupling of L-12
        -> whether it placed or named one."""
        progress = False
        for part in [d for d in self.jobs if all(h in self.place for h in self.hosts_of[d])]:
            self.jobs.remove(part)
            self.put(part, self.hosts_of[part])
            progress = True
        for r in sorted((r for r in self.reqs if r.kind == "decoupling"), key=lambda r: (natural_key(r.part), r.net)):
            if (r.part, r.net) in self.tried or not any(m.part == r.part and m.net == r.net
                                                        for m in missing_decoupling(self.board, self.reqs, self.boxes)):
                continue
            cap = self.free_cap(r)
            if cap:   # one capacitor per IC and supply: one that finds no spot is named, not replaced by the next
                self.tried.add((r.part, r.net))
                self.put(cap, [r.part], r.net)
                progress = True
        return progress

    def free_cap(self, r):
        """The first capacitor of a decoupling requirement that is not placed, declares no host and is not named."""
        return next((c for c in r.others if c not in self.place and c not in self.hosts_of and c not in self.failed
                     and self.keep(c)), None)

    def loose(self):
        """The parts with a declared host that is not placed, named."""
        for part in self.jobs:
            loose = [h for h in self.hosts_of[part] if h not in self.place]
            self.problems.append((part, f"{part}: next to {', '.join(loose)}, which "
                                        f"{'is' if len(loose) == 1 else 'are'} not in [place] – fix the host first"))

    # --- --rest: every other part of the board, by airline length ------------------------------------------------

    def next_rest(self):
        """The part --rest places next: of the board's parts without a row (or with an auto row) that no declared
        host ties to one, the one with the most pins on nets of placed parts (ground left out), by designator. A
        capacitor that may decouple an IC not placed yet waits for it – it comes with its IC (rest_spot)."""
        todo = [r for r in sorted(self.design.board_comps(self.board.name), key=natural_key)
                if r not in self.place and r not in self.failed and r not in self.hosts_of and self.keep(r)]
        ics = {r.part for r in self.reqs if r.kind == "decoupling" and r.part not in self.place
               and r.part not in self.failed and self.keep(r.part)}
        held = {c for r in self.reqs if r.kind == "decoupling" and r.part in ics for c in r.others}
        todo = [r for r in todo if r not in held] or todo
        if not todo:
            return None
        placed = {n for r in self.place for n in self.nets.get(r, [])}
        return min(todo, key=lambda r: (-sum(n in placed for n in self.nets.get(r, [])), natural_key(r)))

    def rest(self):
        """--rest, one part: next_rest at the spot rest_spot finds it, or named -> whether there was one."""
        part = self.next_rest()
        if part is None:
            return False
        if part not in self.geo:
            self.problems.append((part, f"{part}: {part} not in the footprint geometry (edakit pcb parts --write, then "
                                        "dump)"))
            self.failed.add(part)
            return True
        twin, why = self.rest_spot(part)
        if twin is not None:
            self.adopt(twin)
            return True
        x0, y0, x1, y1 = self.geo[part]["bbox"]
        reason = f"the plan check: {why}" if why else (f"its box ({mm(x1 - x0):.1f} x {mm(y1 - y0):.1f} mm) fits "
                                                       "nowhere clear of the placed parts, the holes and the outline")
        self.problems.append((part, f"{part}: no free spot on the {' or '.join(assembled_sides(self.cfg))} side – "
                                    f"{reason}"))
        self.failed.add(part)
        return True

    def anchors(self, part):
        """The groups of placed parts `part` has to stay within near_mm of – one part of each group: a part that names
        it as its host; for an IC whose decoupling capacitors are none of them free, those placed."""
        out = [[d] for d in sorted(self.hosts_of, key=natural_key) if part in self.hosts_of[d] and d in self.place]
        for r in self.reqs:
            if r.kind == "decoupling" and r.part == part and self.free_cap(r) is None:
                if caps := [c for c in r.others if c in self.place]:
                    out.append(caps)
        return out

    def spots(self, part, below=None):
        return rest_spots(self.board, self.geo, self.design, self.state(), part, assembled_sides(self.cfg),
                          self.anchors(part), any(r.kind == "edge" and r.part == part for r in self.reqs), below)

    def fits(self, part, p):
        """A spot of rest_spots that keeps the outline as the plan check measures it, and an edge part at the edge."""
        from shapely.geometry import box
        b, outline = box(*part_box(self.board, self.geo[part], p)), outline_polygon(self.board)
        if part not in self.board.edge_ok and not outline.buffer(-0.3).contains(b):
            return False
        return not (any(r.kind == "edge" and r.part == part for r in self.reqs)
                    and b.distance(outline.exterior) > self.board.edge_mm)

    def rest_spot(self, part):
        """The first spot of rest_spots where the plan check reports nothing new once the parts tied to `part` stand
        next to it (tied: a part that names it as its host, the decoupling capacitor of an IC) – preferably one where
        every one of them finds its spot: once a spot is clean but a tied part found none, PLACE_REST_TRIES more are
        tried for one where all do. -> (the plan with them or None, the first new finding of the best spot turned
        down)."""
        from .config import Placement
        before = self.findings()
        tried, why, fallback, since = 0, None, None, 0
        for x, y, rot, side, _ in self.spots(part):
            p = Placement(x, y, rot, side, auto=True)
            if not self.fits(part, p):
                continue
            twin = self.copy()
            twin.add(part, p)
            twin.rows.append((part, p, ""))
            twin.airline.append(part)
            while twin.tied():
                pass
            new = twin.findings() - before
            if not new and len(twin.problems) == len(self.problems):
                return twin, None
            if new:
                why = why or sorted(new)[0]   # the best spot's first new finding, for the message
            elif fallback is None:
                fallback, since = twin, tried
            tried += 1
            if tried >= PLACE_TRIES or (fallback is not None and tried - since >= PLACE_REST_TRIES):
                break
        return fallback, why

    def total(self, nets=None, place=None):
        """The airline length of the plan – or of `place` –: the minimum spanning trees of the nets – all, or those of
        `nets` –, ground left out, mm."""
        pads = net_pads(self.board, self.geo, self.design, self.place if place is None else place)
        return sum(mst_length(v) for n, v in pads.items() if nets is None or n in nets)

    def improve(self, report=None):
        """--rest's improvement: each part it placed by airline length – unless a part was placed next to it – moves
        to the first spot of rest_spots that is shorter, then each pair of them swaps rows where the airline length
        falls; a change counts only where the plan check reports nothing new. Until a pass changes nothing,
        PLACE_REST_PASSES at most. Then the rows' comments. report gets the parts, the airline length before and
        after, the moves, swaps and passes."""
        movers = sorted((r for r in self.airline if r not in self.hosted), key=natural_key)
        start, moves, swaps, passes = self.total(), 0, 0, 0
        while movers and passes < PLACE_REST_PASSES:
            passes += 1
            found, changed = self.findings(), False
            for part in movers:
                if (f := self.move(part, found)) is not None:
                    found, moves, changed = f, moves + 1, True
            for a, b in itertools.combinations(movers, 2):
                if (f := self.swap(a, b, found)) is not None:
                    found, swaps, changed = f, swaps + 1, True
            if not changed:
                break
        mine = set(self.airline)
        self.rows = [(r, self.place[r], self.why(r) if r in mine else why) for r, _, why in self.rows]
        if report is not None:
            report.update(rest=list(self.airline), airline=(start, self.total()), moves=moves, swaps=swaps,
                          passes=passes)

    def move(self, part, found):
        """part to the first spot of rest_spots shorter than where it stands at which the plan check finds nothing
        beyond `found` -> the findings there, or None."""
        from .config import Placement
        without = self.copy()
        without.remove(part)
        p0 = self.place[part]
        terms = airline_terms(self.board, self.geo, self.design, without.place, part)
        now = float(added_airline(self.board, self.geo, part, terms, [p0.x], [p0.y], p0.rot, p0.side)[0])
        tried = 0
        for x, y, rot, side, _ in without.spots(part, below=now):
            if tried >= PLACE_REST_TRIES:
                return None
            p = Placement(x, y, rot, side, auto=True)
            if not without.fits(part, p):
                continue
            twin = without.copy()
            twin.add(part, p)
            if not ((f := twin.findings()) - found):
                self.adopt(twin)
                return f
            tried += 1
        return None

    def swap(self, a, b, found):
        """a and b swap their rows where the airline length of their nets falls and the plan check finds nothing
        beyond `found` -> the findings then, or None."""
        from .config import Placement
        pa, pb = self.place[a], self.place[b]
        qa, qb = Placement(pb.x, pb.y, pb.rot, pb.side, auto=True), Placement(pa.x, pa.y, pa.rot, pa.side, auto=True)
        nets = {*part_nets(self.design, self.geo, a), *part_nets(self.design, self.geo, b)}
        if self.total(nets, {**self.place, a: qa, b: qb}) > self.total(nets) - PLACE_REST_EPS:
            return None
        twin = self.copy()
        twin.remove(a)
        twin.remove(b)
        twin.add(a, qa)
        twin.add(b, qb)
        if (f := twin.findings()) - found:
            return None
        self.adopt(twin)
        return f

    def why(self, part):
        """The comment of a row --rest placed: the airline length its pads add to their nets in the plan, which nets."""
        mine = part_nets(self.design, self.geo, part)
        pads = net_pads(self.board, self.geo, self.design, self.place)
        others = net_pads(self.board, self.geo, self.design, {r: p for r, p in self.place.items() if r != part})
        nets = [n for n in mine if others.get(n)]
        if not nets:
            text = "by airline length: no net it shares with a placed part (ground aside) – the first free spot"
        else:
            added = round(sum(mst_length(pads[n]) - mst_length(others.get(n, [])) for n in mine), 1) + 0.0
            text = f"by airline length: adds {added:.1f} mm on {', '.join(nets)}"
        if any(r.kind == "fixed" and r.part == part for r in self.reqs):
            text += " – layout.fixed: check the spot, then drop auto = true"
        return text


ROW_DECIMALS = 3                   # rows from EasyEDA: mm and degrees to 0.001 – well inside L-7's 0.02 mm and 0.01°


def row_number(v):
    """A coordinate of a row of [place]: at most ROW_DECIMALS decimals, at least one (62.8, 75.0, 31.356) – the rows
    of pcb place, on their 0.1 mm grid, read as they always did."""
    text = f"{round(v, ROW_DECIMALS) + 0.0:.{ROW_DECIMALS}f}".rstrip("0")
    return text + "0" if text.endswith(".") else text


def place_row(p):
    """A row of [place] as an inline table; auto = true for a spot nobody designed (pcb place, the auto-layout)."""
    rot = round(p.rot, ROW_DECIMALS) + 0.0
    return (f'{{ x = {row_number(p.x)}, y = {row_number(p.y)}, rot = {rot:g}, side = "{p.side}"'
            + (", auto = true" if p.auto else "") + " }")


def write_place_rows(path, rows):
    """rows {ref: inline table}: a row that is already in [place] gets its new table on its own line (only an auto row
    is ever moved), the others go as new lines at the end of [place]; every other line stays as it is. -> number of
    lines changed or added."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    start = next((i for i, ln in enumerate(lines) if PLACE_HEADER.match(ln)), None)
    if start is None:
        lines += ["\n", "[place]\n"] if lines else ["[place]\n"]
        start = len(lines) - 1
    end = next((i for i in range(start + 1, len(lines)) if TABLE_HEADER.match(lines[i])), len(lines))
    changed, new = 0, []
    for ref, table in rows.items():
        pat = re.compile(rf"""^(\s*["']?{re.escape(ref)}["']?\s*=\s*)\{{[^}}]*\}}(.*)$""", re.S)
        at = next((i for i in range(start + 1, end) if pat.match(lines[i])), None)
        if at is None:
            new.append(f"{ref} = {table}\n")
        else:
            line = pat.sub(lambda m: m.group(1) + table + m.group(2), lines[at])
            changed += line != lines[at]
            lines[at] = line
    last = max((i for i in range(start, end) if i == start or (lines[i].strip() and
                                                                not lines[i].lstrip().startswith("#"))))
    lines[last + 1:last + 1] = new
    if changed or new:
        path.write_text("".join(lines), encoding="utf-8")
    return changed + len(new)


def write_rows(cfg, board, rows):
    """rows {ref: Placement} into [place] of the board file (write_place_rows), then read back: when one does not read
    back as written, the file is put back as it was and the command stops. -> number of lines changed or added."""
    from . import config
    f = cfg.resolve(board.file)
    old = f.read_text(encoding="utf-8") if f.exists() else None
    n = write_place_rows(f, {ref: place_row(p) for ref, p in rows.items()})
    try:
        got = config.load(cfg.path).board(board.name).place
        off = [ref for ref, p in rows.items() if ref not in got or (got[ref].x, got[ref].y, got[ref].rot, got[ref].side,
                                                                    got[ref].auto) != (p.x, p.y, p.rot, p.side, p.auto)]
    except config.ConfigError as e:
        off = [str(e)]
    if off:
        if old is None:
            f.unlink()
        else:
            f.write_text(old, encoding="utf-8")
        raise SystemExit(f"{board.file}: {', '.join(off)} did not read back as written – the file is left as it was")
    return n


def place_main(cfg, board, write=False, only=None, rest=False):
    """pcb place: the geometry as pcb plan reads it, for every part of the board – a part not yet in the PCB is
    placed by the library footprint `edakit part import` cached. rest: every other part as well (--rest)."""
    design = Design.from_config(cfg)
    geo = plan_geometry(cfg, board, design, [*board.place, *(r for r in sorted(design.board_comps(board.name),
                                                                                key=natural_key) if r not in board.place)])
    report = {}
    rows, problems = auto_place(cfg, board, geo, design, set(only) if only else None, rest, report)
    say_unmeasured(geo, [r for r, _, _ in rows])
    for ref, p, why in rows:
        print(f"  {ref} = {place_row(p)}   # {why}")
    for p in problems:
        print("  !", p)
    if report.get("rest"):
        (a, b), moves, swaps, passes = report["airline"], report["moves"], report["swaps"], report["passes"]
        print(f"  improvement: {moves} move{'s' * (moves != 1)} and {swaps} swap{'s' * (swaps != 1)} in {passes} "
              f"pass{'es' * (passes != 1)}, airline length (without {design.ground}) {a:.1f} -> {b:.1f} mm"
              if moves or swaps else f"  improvement: no move or swap shortens the airline length (without "
                                     f"{design.ground}) of {a:.1f} mm")
    if write and rows:
        n = write_rows(cfg, board, {ref: p for ref, p, _ in rows})
        print(f"  {n} row{'s' * (n != 1)} written into {board.file} [place]"
              + (f", {len(rows) - n} unchanged" if len(rows) > n else ""))
    elif not rows and not problems:
        print(f"  nothing to place: every part of board {board.name} has a row in [place] that is not auto" if rest
              else "  nothing to place: every part the circuit or the board file ties to a host is in [place]")
    elif rest:
        n = len(report.get("rest", []))
        print(f"  {len(rows) - n} part{'s' * (len(rows) - n != 1)} next to {'its' if len(rows) - n == 1 else 'their'} "
              f"host, {n} by airline length" + ("" if write else " – --write puts them into [place]"))
    else:
        print(f"  {len(rows)} part{'s' * (len(rows) != 1)} next to {'its' if len(rows) == 1 else 'their'} host"
              + ("" if write else " – --write puts them into [place]"))
    return 2 if problems else 0


# --- the positions EasyEDA has: the auto-layout's, written back; a board placed before, taken over -----------------

def parts_without_row(board, design):
    """The parts the graph puts on the board that have no row in [place], by designator (L-20). A part on a bought
    board – off the board, at the far end of a cable – is on no made board and needs none."""
    return sorted((r for r in design.board_comps(board.name) if r not in board.place), key=natural_key)


def eda_rows(board, design, comps, auto):
    """Rows for [place] from the positions EasyEDA reports – comps as eda.list_pcb_components gives them: designator,
    x and y in mil, rotation, layer. Every part of parts_without_row that is in the PCB gets one, in plan coordinates
    (Board.from_eda, mm and degrees to ROW_DECIMALS) with its side; a row the board file holds stays as it is, and a
    part of the PCB the graph does not put on the board gets none. auto: the auto-layout placed them (auto = true – a
    later pcb place may move the row); otherwise fixed rows, the takeover of a board placed before.
    -> ({ref: Placement}, [parts without a row that are not in the PCB])."""
    from .config import Placement
    at = {c.get("designator"): c for c in comps}
    rows, absent = {}, []
    for ref in parts_without_row(board, design):
        c = at.get(ref)
        if c is None:
            absent.append(ref)
            continue
        x, y, rot, side = board.from_eda(mm(c["x"]), mm(c["y"]), c["rotation"], c["layer"])
        rows[ref] = Placement(round(x, ROW_DECIMALS) + 0.0, round(y, ROW_DECIMALS) + 0.0,
                              round(rot, ROW_DECIMALS) % 360 + 0.0, side, auto=auto)
    return rows, absent


def write_back(cfg, board, comps, auto, write=True):
    """The rows eda_rows makes of the positions EasyEDA reports, printed, and with write added to [place] of the board
    file – read again first, so that a row written there meanwhile stays as it is. -> 0, or 2 when a part of the board
    without a row is not in the PCB."""
    from . import config
    board = config.load(cfg.path).board(board.name)
    rows, absent = eda_rows(board, Design.from_config(cfg), comps, auto)
    for ref, p in rows.items():
        print(f"  {ref} = {place_row(p)}")
    for ref in absent:
        print(f"  ! {ref}: not in the PCB – no position to write (edakit pcb parts --write)")
    if not rows:
        print(f"  nothing to write: every part of board {board.name} in the PCB has a row in [place]")
    elif write:
        n = write_rows(cfg, board, rows)
        print(f"  {n} row{'s' * (n != 1)} written into {board.file} [place]"
              + (" with auto = true" if auto else " (fixed)"))
    else:
        print(f"  {len(rows)} part{'s' * (len(rows) != 1)} without a row – --write puts them into [place]")
    return 2 if absent else 0


# --- EasyEDA ------------------------------------------------------------------------------------------------------

def pad_hole(p):
    """{"hole": [w, l] mm, "plated"} of a pin whose hole the API gives in mil – ["ROUND", d] or ["SLOT", d, length]
    (a length below the diameter follows it) – or {} for an SMD pad."""
    h = p.get("hole")
    if not h:
        return {}
    w = h[1] / MIL_PER_MM
    length = max(w, (h[2] if len(h) > 2 else h[1]) / MIL_PER_MM)
    return {"hole": [round(w, 3), round(length, 3)], "plated": bool(p.get("metallization", True))}


PAD_LAYER_NAMES = {TOP: "TOP", BOTTOM: "BOTTOM", MULTI_LAYER: "MULTI"}


def pad_shape(p):
    """{"shape", "w", "h", "rot", "layer"} of a pin as the import cache has them (mil, degrees) – read from the pad's
    own fields (pad: [shape, w, h, …], rotation, layer), for a part whose parts entry has footprint data: P-10 holds
    them to the data. {} where the API gives none. NOT RUN against EasyEDA yet (step 3.6): the fields are those of
    IPCB_PrimitivePad in the client's api-types.d.ts, as measure reads x, y and hole."""
    st = p.get("state") or {}
    shape = p.get("pad") or st.get("Pad")
    if not (isinstance(shape, list) and len(shape) >= 3 and shape[0] in ("RECT", "ELLIPSE", "OVAL")):
        return {}
    layer = p.get("layer", st.get("Layer"))
    return {"shape": shape[0], "w": round(shape[1], 2), "h": round(shape[2], 2),
            "rot": round((p.get("rotation", st.get("Rotation")) or 0) % 360, 2),
            "layer": PAD_LAYER_NAMES.get(layer, layer)}


def measure(mcp, c, shapes=False):
    """Geometry of a part relative to its origin; turns it to 0°/TOP for that and leaves it so. Through-hole pads keep
    their hole (P-7); with shapes – a part whose parts entry has footprint data (4.5) – every pad its shape, size,
    rotation and layer too (P-10)."""
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
                                   "tht": p["hole"] is not None, **pad_hole(p), **(pad_shape(p) if shapes else {})}
                  for p in pads}}
    nums = [p["padNumber"] for p in pads]  # numbers used several times (shell legs): "pads" keeps one, all here
    if dup := sorted({n for n in nums if nums.count(n) > 1}):
        g["pads_same_number"] = {n: [{"x": round(p["x"] - x, 2), "y": round(p["y"] - y, 2), **pad_hole(p),
                                      **(pad_shape(p) if shapes else {})} for p in pads if p["padNumber"] == n]
                                 for n in dup}
    w, h = g["bbox"][2] - g["bbox"][0], g["bbox"][3] - g["bbox"][1]
    print(f"  {c['designator']:<6} {mm(w):6.1f} x {mm(h):5.1f} mm  {c['footprintName']}")
    return g


def dump(cfg, board, mcp, refs=None):
    from .footprint import has_data, users
    f = geometry_file(cfg, board)
    out = json.loads(f.read_text()) if refs and f.exists() else {}
    design = Design.from_config(cfg)
    own = {des for key, e in design.parts.items() if "footprint_data" in e for des in users(design, key)} \
        if has_data(design.parts) else set()       # their pads with shape and size: P-10 holds them to the data
    out |= {c["designator"]: measure(mcp, c, shapes=True) if c["designator"] in own else measure(mcp, c)
            for c in eda.list_pcb_components(mcp) if c.get("designator") and (not refs or c["designator"] in refs)}
    print(f"{len(out)} parts -> {save_geometry(cfg, board, out)}")


def outline_arg(points):
    poly = [to_mil(points[0][0]), to_mil(points[0][1]), "L"]
    for x, y in points[1:] + points[:1]:
        poly += [to_mil(x), to_mil(y)]
    return {"$polygon": poly}


def circle_points(cx, cy, r, n=24):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


APPLY_STEPS = 7   # bridge and PCB (main), then the six of apply


def apply(cfg, board, mcp, verify_all=False, step=None):
    """Fixed parts locked in place, outline and holes drawn, tooling holes set; then the pads of one part per
    (footprint, side, rotation) are compared with the plan – it checks that EasyEDA mirrors and rotates like
    Board.transform. --verify-all compares every part. step: eda.Steps of `pcb apply` (APPLY_STEPS)."""
    step = step or (lambda _: None)
    step("plan and geometry")
    geo = load_geometry(cfg, board)
    problems = plan(cfg, board)
    ids = {c["designator"]: c["primitiveId"] for c in eda.list_pcb_components(mcp) if c.get("designator")}
    missing = [r for r in board.place if r not in geo or r not in ids]
    if missing:
        raise SystemExit(f"not in the PCB or without geometry (first `edakit pcb parts --write`, `dump`): {missing}")
    step("fixed parts")
    for n, (ref, p) in enumerate(board.place.items()):
        if n % 20 == 0:  # focus check per block instead of before every write
            ensure_pcb_focus(mcp)
        x, y, rot, layer = board.to_eda(p.x, p.y, p.rot, p.side)
        api(mcp, "PCB_PrimitiveComponent.modify", ids[ref],
            {"x": to_mil(x), "y": to_mil(y), "rotation": rot, "layer": layer, "primitiveLock": p.lock})
    print(f"  {len(board.place)} fixed parts placed")
    step("unlock the other parts")
    loose = [r for r in ids if r not in board.place]
    for n, ref in enumerate(loose):  # parts that were fixed before: unlock them for the auto-layout
        if n % 20 == 0:
            ensure_pcb_focus(mcp)
        api(mcp, "PCB_PrimitiveComponent.modify", ids[ref], {"primitiveLock": False})
    print(f"  {len(loose)} parts unlocked for the auto-layout")
    step("outline and holes")
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
    step("tooling holes")
    tooling(cfg, board, mcp)
    step("pad check")
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
    """Pour polygon (plan mm): the outline, set in by pour_inset_mm of the board file – without it by the edge clearance
    of the routing rules + 0.1 mm (EasyEDA itself keeps only about 0.26 mm) –, without the keep-out circle of every
    mounting hole, with a notch around every tooling hole. EasyEDA takes a polygon with a hole only as its outer
    contour, and copper must not lie under the tooling hole – so the notch reaches the edge."""
    from shapely.geometry import Point, box
    edge = board.pour_inset_mm
    if edge is None:
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


def pour(cfg, board, mcp, keep_islands_on=None, regions=None):
    """Copper pours of [[pours]] in the board file (default GND on both layers) along the outline; old pours of the same
    nets are replaced. keep_islands_on: layer name whose islands are kept (to find them for stitching). regions:
    {(net, layer name): [outline in EasyEDA mm, …]} – a pour per outline instead (route.region_outlines)."""
    ensure_pcb_focus(mcp)
    nets = {p["net"] for p in board.pours}
    old = [eda.state(p)["PrimitiveId"] for p in api(mcp, "PCB_PrimitivePour.getAll") or []
           if eda.state(p).get("Net") in nets]
    if old:
        api(mcp, "PCB_PrimitivePour.delete", old)
    pts = [board.eda_point(*q) for q in pour_outline(board)]
    for spec in board.pours:
        for layer_name in spec.get("layers", ["TOP", "BOTTOM"]):
            shapes = (regions or {}).get((spec["net"], layer_name), [pts])
            if not shapes:
                print(f"  pour {spec['net']} {layer_name}: no area of its own on the shared layer – not poured")
            for k, shape in enumerate(shapes, 1):
                ensure_pcb_focus(mcp)
                layer = LAYER_ID[layer_name]
                part = f"_{k}" if len(shapes) > 1 else ""
                # 5th value preserveSilos: keep islands. Loose islands count as DRC connection errors – only for finding
                # them
                r = api(mcp, "PCB_PrimitivePour.create", spec["net"], layer, outline_arg(shape), "solid",
                        keep_islands_on == layer_name, f"{spec['net']}_{layer_name}{part}", spec.get("priority", 1),
                        spec.get("line_mil", 10))
                print(f"  pour {spec['net']} {layer_name}{part}: {'ok' if r else 'FAILED'}")


def nets_diff(cfg, mcp):
    """Pads whose net in the PCB differs from the graph: [(pad, pad id, PCB net, graph net)]. Pads of parts have their
    own ids from getAllPinsByPrimitiveId."""
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
    return changes


def sync_nets(cfg, mcp, write=False):
    """Pad nets in the PCB = graph (replaces importChanges for pure net changes: its confirmation dialog needs a click,
    'force' has no effect)."""
    changes = nets_diff(cfg, mcp)
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


PARTS_DIFF = {"missing": "missing in the PCB", "extra": "not in the schematic", "swapped": "swapped (LCSC/footprint)",
              "unlinked": "not linked (UniqueId)", "props": "properties differ from the schematic"}


def parts_diff(mcp, board):
    """Schematic parts against PCB parts: ({kind of PARTS_DIFF: [designators]}, schematic uuid, schematic parts,
    PCB parts)."""
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
    found = {"missing": missing, "extra": extra, "swapped": swapped, "unlinked": unlinked, "props": props}
    return found, sch_uuid, sch, pcb


def sync_parts(cfg, board, mcp, write=False):
    """PCB parts = parts of the board schematic, without the "Import Changes" dialog (importChanges(uuid, true) opens
    it anyway). Schematic and PCB part are linked through the same UniqueId (ggeN). Missing parts are created (device
    from the project library, designator, UniqueId, the COMPLETE OtherProperty of the schematic part with a new
    Channel ID, pad nets from the graph) and parked next to the board; swapped ones (other LCSC number or footprint)
    are replaced the same way; extra ones deleted; unlinked ones linked. Without write only shown.
    Then: dump/plan, apply, auto-layout, route."""
    project = api(mcp, "DMT_Project.getCurrentProjectInfo")["uuid"]
    found, sch_uuid, sch, pcb = parts_diff(mcp, board)
    missing, extra, swapped, unlinked, props = (found[k] for k in PARTS_DIFF)
    for kind, refs in found.items():
        if refs:
            print(f"  {PARTS_DIFF[kind]}: {', '.join(refs)}")
    todo = sum(map(len, found.values()))
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
        save_geometry(cfg, board, geo)
    print(f"  PCB saved: {eda.save_pcb(mcp)}")
    return 0


# --- the DRC's "Netlist Error – Import Changes" -------------------------------------------------------------------

IMPORT_CHANGES = ("Netlist Error", "Import Changes")
ACKNOWLEDGE = ("EasyEDA waits for the import acknowledgement: open Design → Import Changes once, it shows no changes "
               "(schematic = PCB: parts, links, properties, pad nets)")


def import_items(found):
    """The DRC items EasyEDA writes while schematic and PCB netlist differ in its eyes – also, after parts were placed
    in the schematic, until the import view has been opened once."""
    return [f for f in found if (f.get("errorType"), f.get("ruleName")) == IMPORT_CHANGES]


def netlist_diff(cfg, board, mcp):
    """The dry runs of `pcb parts` and `pcb nets`: {"parts": {kind: [designators]}, "nets": [[pad, PCB net, graph
    net]]} – only the kinds with a difference."""
    parts = {k: refs for k, refs in parts_diff(mcp, board)[0].items() if refs}
    return {"parts": parts, "nets": [[key, old or "", new] for key, _, old, new in nets_diff(cfg, mcp)]}


def import_verdict(items, diff):
    """(ok, what) for 'schematic and PCB in sync (Import Changes)': no item; not compared; the acknowledgement alone;
    or the differences with the command that fixes them."""
    if not items:
        return True, "no Import Changes item"
    if diff is None:
        return False, (f"Netlist Error (Import Changes): {len(items)}; schematic and PCB not compared (EasyEDA's DRC "
                       "and the comparison of `edakit pcb parts` and `pcb nets` run together)")
    parts = [f"{PARTS_DIFF.get(k, k)}: {', '.join(refs)}" for k, refs in diff.get("parts", {}).items() if refs]
    nets = [f"{pad} {have or '–'} instead of {want or '–'}" for pad, have, want in diff.get("nets", [])]
    if not parts and not nets:
        return False, ACKNOWLEDGE
    out = ["; ".join(parts) + " → edakit pcb parts --write"] if parts else []
    out += [f"pad nets: {'; '.join(nets[:12])}" + (f" (+{len(nets) - 12})" if len(nets) > 12 else "")
            + " → edakit pcb nets --write"] if nets else []
    return False, "schematic and PCB differ – " + "; ".join(out)


def drc_exit(found, diff):
    """Exit code of `route all|drc` and `silk apply|check` for the DRC: 0 without items; 3 when the only items are
    Import Changes and the comparison shows no difference – EasyEDA waits for the acknowledgement, as `edakit lock`
    exits 3 while another session holds EasyEDA –; 2 otherwise."""
    if not found:
        return 0
    if len(import_items(found)) == len(found) and import_verdict(found, diff)[1] == ACKNOWLEDGE:
        return 3
    return 2


def drc_report(cfg, board, mcp, found, out=None, say=print):
    """Print the DRC; with an Import Changes item compare schematic and PCB (written to out) and say which case it is.
    Returns drc_exit."""
    say(f"  {eda.describe_drc(found)}")
    items, diff = import_items(found), None
    if items:
        diff = netlist_diff(cfg, board, mcp)
        if out:
            out.write_text(json.dumps(diff, indent=1, ensure_ascii=False))
        say(f"  {import_verdict(items, diff)[1]}")
    return drc_exit(found, diff)


def autolayout(cfg, board, mcp, timeout_min=20):
    """EasyEDA's auto-layout places only unlocked parts and only on TOP; it knows nothing about belonging
    (decoupling capacitors, pull-ups) – fix those in the plan. It keeps running after the bridge timeout, so the end is
    detected by positions, rotations and sides that stay the same for two readings. Then every part of the board
    without a row in [place] – the parts it placed – gets one where it stands, with auto = true (write_back): from then
    on the plan holds them like any row, and the auto-layout places only parts without one. Not settled in time:
    nothing is written."""
    ensure_pcb_focus(mcp)
    try:
        api(mcp, "PCB_Document.autoLayout", timeout=20)
    except MCPError as e:
        print(f"  (auto-layout keeps running in EasyEDA: {str(e)[:80]})")
    last, stable, t0 = None, 0, time.monotonic()
    while time.monotonic() - t0 < timeout_min * 60:
        time.sleep(10)
        comps = eda.list_pcb_components(mcp)   # rotation to 0.01°: EasyEDA reports -90.00000000000001 now and then
        now = sorted((c.get("designator") or "", round(c["x"], 1), round(c["y"], 1), round(c["rotation"], 2),
                      c["layer"]) for c in comps)
        stable = stable + 1 if now == last else 0
        last = now
        print(f"  {(time.monotonic() - t0) / 60:4.1f} min: {'stable' if stable else 'moving'}")
        if stable >= 2:
            return write_back(cfg, board, comps, auto=True)
    print("  auto-layout did not settle in time – nothing written into [place]")
    return 2


def takeover(cfg, board, mcp, write=False):
    """pcb takeover, once for a board placed before – by hand, or by the auto-layout before it wrote its positions
    back – and maybe routed: every part of the board without a row in [place] gets a fixed row (no auto) where EasyEDA
    has it, so that pcb apply locks it there and the tracks stay on its pads; a new auto-layout would move it off them.
    Rows the board file holds stay as they are – L-7 compares them with the PCB. Without write: shown only."""
    return write_back(cfg, board, eda.list_pcb_components(mcp), auto=False, write=write)


def main(cfg, args):
    board = cfg.board(args.board, made=True)
    if args.action == "plan":
        return 2 if plan(cfg, board) else 0
    if args.action == "place":
        return place_main(cfg, board, args.write, args.only and args.only.split(","), args.rest)
    regions = None
    if args.action == "pour":  # pour_regions: the outlines from the last routing, before EasyEDA is touched
        from . import route
        regions = route.region_outlines(cfg, board)
    if is_kicad(cfg):                 # the KiCad project: files and kicad-cli (handbook 16)
        from .toolchain.kicad import commands
        return commands.pcb_main(cfg, board, args, regions)
    step = eda.Steps(APPLY_STEPS) if args.action == "apply" else None
    if step:
        step("bridge and PCB")
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
            return apply(cfg, board, mcp, args.verify_all, step)
        elif args.action == "tooling":
            tooling(cfg, board, mcp)
        elif args.action == "pour":
            pour(cfg, board, mcp, regions=regions)
        elif args.action == "nets":
            n = sync_nets(cfg, mcp, write=args.write)
            return 2 if n and not args.write else 0
        elif args.action == "autolayout":
            return autolayout(cfg, board, mcp)
        elif args.action == "takeover":
            return takeover(cfg, board, mcp, args.write)
        return 0
    except MCPError as e:
        return eda.die(str(e))
    finally:
        mcp.close()
