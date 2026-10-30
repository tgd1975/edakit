"""The order form of one board – written per gate run from [order] and thickness_mm of the board file, [release]
assembly, the stock snapshot and the manufacturing files of the run – and check FILES.order (order settings = board). Both
only when the board file has [order]; `fab.run` calls `check` after the F checks.

    DIR/<board>/order.md   every field of JLCPCB's form that depends on the board: layers, size, quantity, thickness,
                           colours of solder mask and silkscreen, surface finish, mark on PCB (at the placeholder),
                           remark; PCBA type and side, tooling holes, bake, the upload files; the tab zones and the
                           outline stretches free of copper; what is bought separately (edakit order)
    DIR/<board>/order.json the order settings that change the board as made – thickness_mm, mask, silkscreen, finish,
                           mark (settings): fab.fab_layers puts them into the fab hash. The remark is free text to
                           JLCPCB and the tab zones reach it only through the remark: neither changes the board as
                           made, neither is in it. Without [order] the file is not there (a stale one is removed), and
                           the fab hash is the files' alone, as before

  FILES.order  the remark fits the form (at most 200 characters, ASCII) (fail); thickness_mm is a thickness of JLCPCB's form
       (fail); the silkscreen colour is the one JLCPCB prints on the mask colour (fail); mark = "specify" needs the
       placeholder JLCJLCJLCJLC on a silkscreen layer of pcb.json, at least 0.8 mm high in [[silk.texts]] (fail;
       height not in [[silk.texts]]: warn); the placeholder with another mark warns; Economic PCBA with fewer than 2
       tooling holes warns (JLCPCB adds its own); copper within tab_copper_mm of a declared tab zone fails – measured
       on the Gerber copper of both sides against the Gerber outline. The free outline stretches are information.

Coordinates in messages and in order.md are Gerber mm (EasyEDA, seen from the top) – what JLCPCB sees; tab zones are
declared in plan mm like the rest of the board file.
"""

from __future__ import annotations

import math

from .. import gerber, order, stock
from ..config import silkscreen_on
from ..design import natural_key

SETTINGS = "order.json"        # the order settings that change the board as made, in the fab hash (fab.fab_layers)
PLACEHOLDER = "JLCJLCJLCJLC"   # JLCPCB prints the order number here with "Order Number (Specify Position)"
PLACEHOLDER_MIN_MM = 0.8       # least height of the placeholder JLCPCB recognises (#40)
REMARK_MAX = 200               # JLCPCB's remark field
THICKNESSES_MM = (0.4, 0.6, 0.8, 1.0, 1.2, 1.6, 2.0)   # "PCB Thickness" of JLCPCB's form, FR-4 with 2 layers
TOOLING_MIN = 2                # Economic PCBA: fewer and JLCPCB drills its own ("Added by JLCPCB")
ON_OUTLINE_MM = 0.5            # a tab zone's end points lie this close to the outline
CORNER_DEG = 45                # an outline stretch ends where the outline has turned this far
SLIVER_MM = 1.0                # free stretches shorter than this are not listed
SILK = {3: "top", 4: "bottom"}
MARK = {"default": "Order Number (JLCPCB places it)", "specify": "Order Number (Specify Position)",
        "remove": "Remove Mark"}


def pt(p):
    return f"({p[0]:.1f}, {p[1]:.1f})"


# --- geometry on the Gerber files -------------------------------------------------------------------------------------

def outline(g):
    """The board as one polygon (the largest closed loop of the outline layer), exterior counter-clockwise; None
    when the layer has none."""
    from shapely.geometry import LineString
    from shapely.geometry.polygon import orient
    from shapely.ops import polygonize, unary_union
    segs = []
    for kind, dat in gerber.parse_gerber(g / gerber.FILES["outline"]):
        pts = [(round(x, 3), round(y, 3)) for x, y in (dat[1] if kind == "draw" else [])]
        segs += [LineString([a, b]) for a, b in zip(pts, pts[1:]) if a != b]
    polys = sorted(polygonize(unary_union(segs)), key=lambda p: -p.area) if segs else []
    return orient(polys[0], 1.0) if polys else None


def copper(g):
    from shapely.ops import unary_union
    return unary_union([gerber.shape(gerber.parse_gerber(g / gerber.FILES[k])) for k in ("top", "bottom")])


def heading(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def turn(a, b):
    return abs((a - b + 180) % 360 - 180)


def stretches(ring):
    """The outline split where it turns by more than CORNER_DEG from the start of the stretch: the edges of a
    rectangle, the flanks and tier edges of a tree. Starts at the sharpest corner."""
    from shapely.geometry import LineString
    pts = list(ring.coords)[:-1]
    n = len(pts)
    seg = [heading(pts[i], pts[(i + 1) % n]) for i in range(n)]
    start = max(range(n), key=lambda i: turn(seg[i - 1], seg[i]))
    out, cur, h0 = [], [pts[start]], seg[start]
    for k in range(n):
        i = (start + k) % n
        if len(cur) > 1 and turn(seg[i], h0) > CORNER_DEG:
            out.append(LineString(cur))
            cur, h0 = [pts[i]], seg[i]
        cur.append(pts[(i + 1) % n])
    out.append(LineString(cur))
    return out


def free_stretches(ring, cu, mm):
    """Pieces of the outline with no copper within mm, at least SLIVER_MM long, in the order of the outline."""
    zone = cu.buffer(mm)
    out = []
    for s in stretches(ring):
        rest = s.difference(zone)
        out += [p for p in getattr(rest, "geoms", [rest]) if not p.is_empty and p.length >= SLIVER_MM]
    return out


def zone_line(ring, a, b):
    """The shorter stretch of the outline between the points nearest to a and b."""
    from shapely.geometry import Point
    from shapely.ops import linemerge, substring
    da, db = sorted((ring.project(Point(a)), ring.project(Point(b))))
    if db - da <= ring.length / 2:
        return substring(ring, da, db)
    return linemerge([substring(ring, db, ring.length), substring(ring, 0, da)])


def piece_text(p):
    c = list(p.coords)
    return f"{pt(c[0])} → {pt(c[-1])}, {p.length:.1f} mm"


# --- FILES.order and order.md -------------------------------------------------------------------------------------------------

def settings(board):
    """The order settings that change the board as JLCPCB makes it – the thickness as ordered (thickness_mm), the
    colours of solder mask and silkscreen, the surface finish, the order-number mark –; None without [order]."""
    if board.order is None:
        return None
    o = board.order
    return {"thickness_mm": board.thickness_mm, "mask": o["mask"], "silkscreen": o["silkscreen"],
            "finish": o["finish"], "mark": o["mark"]}


def check_remark(remark, rows, name):
    bad = sorted({ch for ch in remark if not ch.isascii()})
    actual = (f"{len(remark)} characters" + (f", not ASCII: {' '.join(bad)}" if bad else ", ASCII")) if remark \
        else "no remark"
    rows.add("F", "FILES.order", name, "remark fits JLCPCB's order form", len(remark) <= REMARK_MAX and not bad, actual,
             f"<= {REMARK_MAX} characters, ASCII")


def check_material(board, rows):
    """The board thickness and the colours: thickness_mm one of the form's thicknesses, the silkscreen the colour
    JLCPCB prints on the mask."""
    t = board.thickness_mm
    ok = any(abs(t - x) < 1e-6 for x in THICKNESSES_MM)
    rows.add("F", "FILES.order", board.name, "board thickness JLCPCB makes (FR-4, 2 layers)", ok,
             f"{t:g} mm (thickness_mm)" + ("" if ok else " – not a thickness of JLCPCB's form"),
             ", ".join(f"{x:g}" for x in THICKNESSES_MM) + " mm")
    mask, silk = board.order["mask"], board.order["silkscreen"]
    want = silkscreen_on(mask)
    rows.add("F", "FILES.order", board.name, "silkscreen colour JLCPCB prints on the solder mask", silk == want,
             f"{silk} on a {mask} mask" if silk == want else
             f'silkscreen = "{silk}" on a {mask} mask – JLCPCB prints {want} on it; choose silkscreen = "{want}" or '
             "another mask", f"{want} on a {mask} mask")


def placeholders(board, data):
    """[(side, (x, y))] of the placeholder on a silkscreen layer of pcb.json, and the heights [[silk.texts]] gives it."""
    mm = 25.4 / 1000
    found = [(SILK[s["Layer"]], (s["X"] * mm, s["Y"] * mm)) for s in data.get("strings", [])
             if s.get("Layer") in SILK and PLACEHOLDER in str(s.get("Text", ""))]
    heights = [float(t.get("h_mm", 1.2)) for t in board.silk.get("texts", []) if PLACEHOLDER in str(t.get("text", ""))]
    return found, heights


def check_mark(board, data, rows):
    mark = board.order["mark"]
    found, heights = placeholders(board, data)
    what = f"order-number mark = placeholder {PLACEHOLDER} on the silkscreen"
    where = f"{PLACEHOLDER} at {pt(found[0][1])} on the {found[0][0]} silkscreen" if found else ""
    if mark != "specify":
        if found:
            rows.add("F", "FILES.order", board.name, what, False, f'{where}, but mark = "{mark}" – JLCPCB prints its number '
                     'elsewhere and leaves the placeholder as text; choose mark = "specify"', "mark = specify", "warn")
        else:
            rows.add("F", "FILES.order", board.name, what, True, f'mark = "{mark}": {MARK[mark]}', "no placeholder")
        return
    want = f">= {PLACEHOLDER_MIN_MM} mm high"
    if not found:
        rows.add("F", "FILES.order", board.name, what, False, f"no {PLACEHOLDER} on a silkscreen layer (pcb.json) – place it "
                 "([[silk.texts]], edakit silk apply) or choose another mark", f"placeholder, {want}")
    elif not heights:
        rows.add("F", "FILES.order", board.name, what, False, f"{where}: its height is not in [[silk.texts]] – not checked",
                 want, "warn")
    else:
        h = min(heights)
        rows.add("F", "FILES.order", board.name, what, h >= PLACEHOLDER_MIN_MM - 1e-9,
                 f"{where}, {h:.2f} mm high" if h >= PLACEHOLDER_MIN_MM - 1e-9
                 else f"{PLACEHOLDER} {h:.2f} mm high ([[silk.texts]] h_mm) – JLCPCB needs {want}", want)


def check_tooling(board, pcba, rows):
    n = len(board.tooling)
    if n >= TOOLING_MIN:
        actual = f"{n} tooling holes: Added by Customer"
    else:
        actual = (f"{n} tooling hole" if n else "no tooling holes ([tooling])") + " – JLCPCB adds its own (Added by " \
            "JLCPCB), maybe on a visible edge; add [tooling] holes or accept"
    rows.add("F", "FILES.order", board.name, f"tooling holes of the Economic PCBA ({pcba[1]})", n >= TOOLING_MIN, actual,
             f">= {TOOLING_MIN} ([tooling])", None if n >= TOOLING_MIN else "warn")


def check_tabs(board, g, rows):
    """Copper against the declared tab zones; returns (polygon, free stretches, [(zone text, distance)]) or None."""
    from shapely.geometry import Point
    from shapely.ops import nearest_points
    o = board.order
    lost = gerber.missing(g, "outline", "top", "bottom")
    if lost:
        if o["tab_zones"]:
            rows.add("F", "FILES.order", board.name, "tab zones free of copper", False, f"{', '.join(lost)} missing", "present")
        return None
    poly = outline(g)
    if poly is None:
        if o["tab_zones"]:
            rows.add("F", "FILES.order", board.name, "tab zones free of copper", False, "no closed outline in the Gerber files",
                     "closed outline")
        return None
    ring, cu, mm = poly.exterior, copper(g), o["tab_copper_mm"]
    zones = []
    for a, b in o["tab_zones"]:
        ea, eb = board.eda_point(*a), board.eda_point(*b)
        name = f"{pt(ea)} → {pt(eb)}"
        off = [f"{pt(p)} is {Point(p).distance(ring):.2f} mm off the outline" for p in (ea, eb)
               if Point(p).distance(ring) > ON_OUTLINE_MM]
        if off:
            rows.add("F", "FILES.order", board.name, f"tab zone {name} on the outline", False, "; ".join(off),
                     f"<= {ON_OUTLINE_MM} mm")
            zones.append((name, None))
            continue
        line = zone_line(ring, ea, eb)
        dist = line.distance(cu) if not cu.is_empty else math.inf
        at = nearest_points(line, cu)[0] if not cu.is_empty else None
        ok = dist >= mm - 1e-6
        rows.add("F", "FILES.order", board.name, f"tab zone {name}: no copper within tab_copper_mm of the edge", ok,
                 f"{line.length:.1f} mm, nearest copper {dist:.2f} mm" if ok
                 else f"copper {dist:.2f} mm from the edge at {pt((at.x, at.y))}", f">= {mm:.2f} mm (tab_copper_mm)")
        zones.append((name, dist))
    free = free_stretches(ring, cu, mm)
    longest = sorted(free, key=lambda p: -p.length)
    rows.add("F", "FILES.order", board.name, f"outline stretches with no copper within {mm:.2f} mm (where tabs can go)", True,
             f"{len(free)}, {sum(p.length for p in free):.1f} of {ring.length:.1f} mm"
             + (": " + "; ".join(piece_text(p) for p in longest[:4]) if free else ""), "information", "info")
    return poly, free, zones


def bake(cfg, design, board):
    """(field, parts with MSL >= 5) from the stock snapshot."""
    snap = stock.load(cfg)
    if snap is None:
        return "check the BOM tool – no stock snapshot (edakit stock)", []
    hot = [f"{stock.refs_text(refs)} {lcsc} MSL {snap['parts'][lcsc]['msl']}"
           for lcsc, refs in stock.assembled(design, board.name).items()
           if (snap.get("parts", {}).get(lcsc, {}).get("msl") or 0) >= stock.BAKE_MSL]
    when = f"stock snapshot {snap.get('date')}"
    return (f"Yes – {', '.join(hot)} ({when})" if hot else f"No – no part with MSL >= {stock.BAKE_MSL} ({when})"), hot


def bought(design, board):
    """[(designators, part, supplier, code)] of this board's parts bought separately (edakit order)."""
    groups = {}
    for d in sorted(order.bought_by_hand(design), key=natural_key):
        if design.comps[d].get("board") != board.name:
            continue
        c, entry = design.comps[d], design.part(d) or {}
        sup, offer = order.source(design, d)
        part = " ".join(x for x in (c.get("lcsc"), entry.get("mpn") or c.get("part")) if x)
        groups.setdefault((part, sup or "–", (offer or {}).get("code") or "–"), []).append(d)
    return [(stock.refs_text(refs), *key) for key, refs in groups.items()]


def sheet(cfg, design, board, d, bom, pcba, tabs, found):
    o, g = board.order, d / "gerber"
    sides = cfg.release.get("assembly", {}).get("sides", ["top", "bottom"])
    side = "Both Sides" if len(sides) > 1 else f"{sides[0].capitalize()} Side" if sides else "–"
    size = "–"
    if tabs:
        x0, y0, x1, y1 = tabs[0].bounds
        size = f"{x1 - x0:.2f} x {y1 - y0:.2f} mm (Gerber outline)"
    layers = sum(not gerber.missing(g, k) for k in ("top", "bottom"))
    mark = MARK[o["mark"]] + (f" – {PLACEHOLDER} at {pt(found[0][1])} on the {found[0][0]} silkscreen"
                              if o["mark"] == "specify" and found else "")
    remark = f"below ({len(o['remark'])} characters)" if o["remark"] else "–"
    L = [f"# Order form – board {board.name} ({board.title}), {cfg.project}\n",
         "Written by edakit from [order] of the board file, [release] assembly, the stock snapshot and the files of "
         "this run; check FILES.order compares them. Upload only from a released run (manifest.json). Coordinates: Gerber mm. "
         "Thickness, colours, finish and mark count in the fab hash (order.json): a sign-off of scope fab, like M-5, "
         "holds for them as written here.\n",
         "## PCB\n", "| Field | Value |", "|---|---|", f"| Layers | {layers} |", f"| Dimensions | {size} |",
         f"| PCB Qty | {cfg.quantity} |", f"| PCB Thickness | {board.thickness_mm:g} mm |",
         f"| PCB Color | {o['mask'].capitalize()} |", f"| Silkscreen | {o['silkscreen'].capitalize()} |",
         f"| Surface Finish | {o['finish']} |", f"| Mark on PCB | {mark} |",
         f"| Remark | {remark} |", ""]
    if o["remark"]:
        L += ["```text", o["remark"], "```", ""]
    L += ["## PCB Assembly\n"]
    if not bom:
        L.append("None – no part of this board is assembled (PCB only).\n")
    else:
        holes = (f"Added by Customer ({len(board.tooling)} x Ø {board.tooling_d:g} mm)" if board.tooling
                 else "Added by JLCPCB – the board has none ([tooling])")
        L += ["| Field | Value |", "|---|---|", f"| PCBA Type | {pcba[0].capitalize()} ({pcba[1]}) |",
              f"| Assembly Side | {side} |", f"| PCBA Qty | {cfg.quantity} |", f"| Tooling holes | {holes} |",
              f"| Bake Components | {bake(cfg, design, board)[0]} |",
              f"| BOM / CPL | bom_{board.name}.csv ({len(bom)} lines) / cpl_{board.name}.csv |",
              f"| Gerber | gerber_{board.name}.zip |", ""]
    L += ["## Tabs\n"]
    if tabs is None:
        L.append("Not measured – Gerber outline or copper missing (FILES.set).\n")
    else:
        _, free, zones = tabs
        L.append(f"Copper kept from the edge where a tab may go: {o['tab_copper_mm']:.2f} mm (tab_copper_mm), "
                 "both copper layers.\n")
        if zones:
            L += ["| Declared tab zone | Nearest copper |", "|---|---|"]
            L += [f"| {z} | {'off the outline' if dist is None else f'{dist:.2f} mm'} |" for z, dist in zones]
            L.append("")
        L.append("Outline stretches with no copper within that distance:\n")
        L += [f"- {piece_text(p)}" for p in free] or ["- none"]
        L.append("")
    hand = bought(design, board)
    L += ["## Bought separately (edakit order)\n"]
    if hand:
        L += ["| Designators | Part | Supplier | Code |", "|---|---|---|---|"]
        L += [f"| {refs} | {part} | {sup} | {code} |" for refs, part, sup, code in hand]
        L.append("\nQuantities with spares and minimums: the carts of `edakit order`.\n")
    else:
        L.append("Nothing.\n")
    return "\n".join(L)


def check(cfg, board, design, d, rows, bom):
    """FILES.order, order.md and order.json for one board – only when its board file has [order]; without it a stale
    order.json of an earlier run in d goes, so that the fab hash holds no settings the board file does not give."""
    import json
    if board.order is None:
        (d / SETTINGS).unlink(missing_ok=True)
        return
    (d / SETTINGS).write_text(json.dumps(settings(board), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    pcba = cfg.pcba()
    data = json.loads((d / "pcb.json").read_text())
    check_remark(board.order["remark"], rows, board.name)
    check_material(board, rows)
    check_mark(board, data, rows)
    if bom and pcba[0] == "economic":
        check_tooling(board, pcba, rows)
    tabs = check_tabs(board, d / "gerber", rows)
    found, _ = placeholders(board, data)
    (d / "order.md").write_text(sheet(cfg, design, board, d, bom, pcba, tabs, found), encoding="utf-8")
    rows.add("F", "FILES.order", board.name, "order form of this run", True,
             f"order.md: {pcba[0].capitalize() + ' PCBA' if bom else 'PCB only'}, mark {MARK[board.order['mark']]}"
             + (f", tooling {'Added by Customer' if board.tooling else 'Added by JLCPCB'}" if bom else ""),
             "information", "info")
