"""The order form of one board – written per gate run from [order] (edakit's defaults, [order] of edakit.toml, [order]
of the board file) and thickness_mm, [release] assembly, the stock snapshot and the manufacturing files of the run –
and check FILES.order (order settings = board, per maker). Both when the board has [order] or the project has [cart];
`fab.run` calls `check` after the F checks.

    DIR/<board>/order.md   every field of the planned maker's form ([cart] maker, JLCPCB without it), in the order of
                           its form, with its value in the maker's words and where it comes from: edakit's default,
                           [order] of edakit.toml or of the board file, the Gerber files, [project] quantity,
                           [release] assembly, [tooling], the stock snapshot, [cart]; the remark; the upload files; the
                           tab zones and the outline stretches free of copper; what is bought separately (edakit order)
    DIR/<board>/order.json the order settings that change the board as made (settings): thickness_mm, mask,
                           silkscreen, finish, mark – and of the other keys that change it (config.ORDER, made) those
                           whose value differs from edakit's default. fab.fab_layers puts them into the fab hash. The
                           remark and the tab zones reach the maker only as text: neither changes the board as made,
                           neither is in it. Without [order] the file is not there (a stale one is removed), and the
                           fab hash is the files' alone, as before

  FILES.order  per maker of [cart] makers – a finding fails for [cart] maker and warns for every other one (makers.result):
       every field's value is one the maker's form offers (its profile's fields), no combination its profile excludes;
       the remark fits the form (JLCPCB: at most 200 characters, ASCII); thickness_mm is a thickness of the form; the
       silkscreen colour is the one the maker prints on the mask colour; mark = "specify" needs the maker's placeholder
       (JLCPCB: JLCJLCJLCJLC, PCBWay: WayWayWay) on a silkscreen layer of pcb.json, at least its least height in
       [[silk.texts]] (height not in [[silk.texts]]: warn); the placeholder with another mark warns, and so do the
       placeholder and mark = "specify" while the profile reports the order number gone (JLCPCB); another maker's
       placeholder on the silkscreen is a finding – this maker prints the letters as they are; an assembly class with fewer tooling holes than the profile's
       tooling_min warns (JLCPCB: Economic, 2 – it adds its own); a provisional profile is named as information.
       Independent of the maker: layers and size_mm, where set, are those of the Gerber files; panel_by_customer fails
       – the run's Gerber is one board; pcba_quantity is at most quantity, and another number than [project] quantity
       warns (PARTS.stock counts that many sets); copper within tab_copper_mm of a declared tab zone fails – measured
       on the Gerber copper of both sides against the Gerber outline. The free outline stretches are information.

Coordinates in messages and in order.md are Gerber mm (EasyEDA, seen from the top) – what the maker sees; tab zones
are declared in plan mm like the rest of the board file.
"""

from __future__ import annotations

import math

from .. import gerber, makers, order, stock
from ..config import ORDER, order_defaults, silkscreen_on
from ..design import natural_key

SETTINGS = "order.json"        # the order settings that change the board as made, in the fab hash (fab.fab_layers)
PLACEHOLDER = "JLCJLCJLCJLC"   # JLCPCB's order-number placeholder (its profile, rules.placeholder)
ON_OUTLINE_MM = 0.5            # a tab zone's end points lie this close to the outline
CORNER_DEG = 45                # an outline stretch ends where the outline has turned this far
SLIVER_MM = 1.0                # free stretches shorter than this are not listed
SIZE_TOL_MM = 0.1              # [order] size_mm against the Gerber outline
SILK = {3: "top", 4: "bottom"}
FIVE = ("thickness_mm", "mask", "silkscreen", "finish", "mark")   # in order.json whenever the board has [order]
SETTING_KEYS = FIVE + tuple(k for k, (_, _, made) in ORDER.items() if made and k not in FIVE)
# the fields of a form in edakit's order – a maker's profile lists its own order, these follow for what it does not
FORM = ("material", "layers", "size_mm", "quantity", "delivery", "thickness_mm", "mask", "silkscreen", "finish", "tg",
        "copper_oz", "inner_copper_oz", "vias", "outline_tolerance", "gold_fingers", "castellated", "edge_plating",
        "mark", "barcode", "serial_number", "electrical_test", "quality", "confirm_production_file", "paper_between",
        "packaging", "remark",
        "pcba", "sides", "pcba_quantity", "tooling", "confirm_placement", "photo_confirmation", "bake", "depanel",
        "conformal_coating", "function_test", "pcba_packaging", "ship_to", "shipping")
PCBA_KEYS = FORM[FORM.index("pcba"):FORM.index("ship_to")]
SHIP_KEYS = ("ship_to", "shipping")
DERIVED = ("layers", "size_mm", "pcba", "sides", "tooling", "bake", "ship_to", "shipping")   # not values to offer
FREE = ("quantity", "pcba_quantity", "remark")   # values of the owner's choosing: a form lists none to offer
FROM = {"board": "board file", "project": "edakit.toml"}


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




# --- the order of a board ---------------------------------------------------------------------------------------------

def order_of(cfg, board):
    """The board's order keys: [order] as config read it, or – the project has [cart], the board no [order] – edakit's
    defaults (then no order.json); None when neither."""
    if board.order is not None:
        return board.order
    if not makers.of(cfg).get("given"):
        return None
    o = order_defaults()
    o.update(silkscreen=silkscreen_on(o["mask"]), quantity=cfg.quantity, pcba_quantity=cfg.quantity, _from={})
    return o


def settings(board):
    """The order settings that change the board as made – the thickness as ordered (thickness_mm), the colours of
    solder mask and silkscreen, the surface finish, the order-number mark – and every other key that changes it
    (config.ORDER, made) whose value differs from edakit's default; None without [order]."""
    if board.order is None:
        return None
    o, base = board.order, order_defaults()
    out = {"thickness_mm": board.thickness_mm, **{k: o[k] for k in FIVE[1:]}}
    out.update({k: o[k] for k in SETTING_KEYS[len(FIVE):] if o.get(k) != base[k]})
    return out


def facts(g):
    """(layers, (w, h) or None) of a run's Gerber files: the copper layers there, the size of the outline."""
    layers = sum(not gerber.missing(g, k) for k in ("top", "bottom"))
    poly = outline(g) if not gerber.missing(g, "outline") else None
    if poly is None:
        return layers, None
    x0, y0, x1, y1 = poly.bounds
    return layers, (round(x1 - x0, 2), round(y1 - y0, 2))


def sides_of(cfg):
    """[release] assembly.sides as one value of the form: top, bottom, both; None: nobody assembles."""
    sides = cfg.release.get("assembly", {}).get("sides", ["top", "bottom"])
    return None if not sides else "both" if len(sides) > 1 else sides[0]


def item(maker, key, raw, source, note="", read=False):
    """One field of a maker's form: its key, section, label, the maker's word for raw, edakit's value, where it comes
    from, a note; read: edakit has no value – the skill reads what the page shows and sets nothing."""
    default = "PCBA" if key in PCBA_KEYS else "Shipping" if key in SHIP_KEYS else "PCB"
    out = {"key": key, "section": maker.section(key, default), "label": maker.label(key),
           "value": maker.word(key, raw) if raw is not None else "–", "raw": raw, "from": source, "note": note}
    if read or raw is None:
        out["read"] = True
    return out


def form(cfg, design, board, d, maker, o=None, bom=None, found=None):
    """The order form of one board at one maker as fields, in the order of its form: [{key, section, label, value (the
    maker's word), raw (edakit's value), from, note}] – order.md is printed from it, the job of edakit cart prepare
    holds it. d: the board's folder of the run. A key the maker has no field for (false in its profile) is left out,
    the PCBA fields when no part of the board is assembled, the inner copper on a board of two layers."""
    import json
    from .fab import bom_rows
    o = o if o is not None else order_of(cfg, board)
    if o is None:
        o = order_defaults()
        o.update(silkscreen=silkscreen_on(o["mask"]), quantity=cfg.quantity, pcba_quantity=cfg.quantity, _from={})
    bom = bom if bom is not None else bom_rows(design, board)
    if found is None:
        data = json.loads((d / "pcb.json").read_text()) if (d / "pcb.json").exists() else {}
        found = placeholders(board, data, maker)[0]
    given = o.get("_from", {})
    src = lambda k: FROM.get(given.get(k), "edakit")   # noqa: E731
    layers, size = facts(d / "gerber")
    pcba = makers.pcba(cfg, maker.key)
    c = makers.of(cfg)
    snap_text, hot, snap = bake(cfg, design, board)
    values = {
        "layers": (layers or None, "Gerber files", ""),
        "size_mm": (list(size) if size else None, "Gerber outline", ""),
        "quantity": (o["quantity"], src("quantity") if "quantity" in given else "[project] quantity", ""),
        "pcba_quantity": (o["pcba_quantity"], src("pcba_quantity") if "pcba_quantity" in given else "quantity", ""),
        "thickness_mm": (board.thickness_mm, "board file" if board.thickness_given else "edakit", ""),
        "pcba": (pcba[0], pcba[1], ""),
        "sides": (sides_of(cfg), "[release] assembly.sides", ""),
        "tooling": ("customer" if board.tooling else "maker", "[tooling]",
                    f"{len(board.tooling)} x Ø {board.tooling_d:g} mm" if board.tooling else "the board has none"),
        "bake": (bool(hot) if snap else None, f"stock snapshot {snap.get('date')}" if snap else "no stock snapshot",
                 snap_text),
        "ship_to": (c.get("ship_to"), "[cart] ship_to", ""),
        "shipping": (c.get("shipping", {}).get(maker.key), "[cart] shipping", ""),
    }
    rules = maker.rules
    keys = [k for k in (maker.data.get("fields") or {}) if k in FORM] + list(FORM)
    out = []
    for key in dict.fromkeys(keys):
        if not maker.has(key) or (key in PCBA_KEYS and not bom) or (key == "inner_copper_oz" and (layers or 2) <= 2):
            continue
        raw, source, note = values.get(key) or (o.get(key), src(key), "")
        if key == "mark" and o["mark"] == "specify" and found and rules.get("placeholder"):
            note = f"{rules['placeholder']} at {pt(found[0][1])} on the {found[0][0]} silkscreen"
        if key == "remark" and o["remark"]:
            note = f"{len(o['remark'])} characters"
        if key == "delivery" and o.get("panel"):
            p = o["panel"]
            note = f"panel {p['x']} x {p['y']}, rails {p['rails_mm']:g} mm"
        out.append(item(maker, key, raw, source, note, read=key == "bake" and raw is None))
    return out


def field_text(f):
    """A field's value as order.md shows it: the word, the note after it; a field edakit only reads, its note."""
    if f["raw"] is None and f.get("note"):
        return f["note"]
    return f["value"] + (f" – {f['note']}" if f.get("note") and f["key"] not in ("remark",) else "")


# --- FILES.order --------------------------------------------------------------------------------------------------------------

class Check:
    """The rows of FILES.order for one maker: a finding fails for the planned maker and warns for every other one; a warning
    stays a warning, information stays information."""

    def __init__(self, cfg, board, maker, rows):
        self.cfg, self.board, self.maker, self.rows = cfg, board, maker, rows
        self.other = maker.key != makers.planned(cfg)

    def add(self, check, ok, actual, expected, level=None):
        result = "pass" if ok and level != "info" else level if level in ("warn", "info") else \
            makers.result(self.cfg, self.maker.key, False)
        self.rows.add("F", "FILES.order", self.board.name, check, ok, actual, expected, result)
        self.rows[-1]["maker"] = self.maker.key


def check_remark(c, remark):
    limit = c.maker.rules.get("remark_max")
    if limit is None:
        return
    bad = sorted({ch for ch in remark if not ch.isascii()})
    actual = (f"{len(remark)} characters" + (f", not ASCII: {' '.join(bad)}" if bad else ", ASCII")) if remark \
        else "no remark"
    c.add(f"remark fits {c.maker.name}'s order form", len(remark) <= limit and not bad, actual,
          f"<= {limit} characters, ASCII")


def check_material(c, o):
    """The board thickness and the colours: thickness_mm one of the form's thicknesses, the silkscreen the colour the
    maker prints on the mask."""
    board, m = c.board, c.maker
    values = m.offered("thickness_mm")
    if values is not None:
        t = board.thickness_mm
        ok = m.offers("thickness_mm", t)
        what = m.rules.get("thicknesses_for")
        c.add(f"board thickness {m.name} makes" + (f" ({what})" if what else ""), ok,
              f"{t:g} mm (thickness_mm)" + ("" if ok else f" – not a thickness of {m.name}'s form"),
              ", ".join(f"{x:g}" for x in values) + " mm")
    want = m.silkscreen_on(o["mask"])
    if want is not None:
        mask, silk = o["mask"], o["silkscreen"]
        c.add(f"silkscreen colour {m.name} prints on the solder mask", silk == want,
              f"{silk} on a {mask} mask" if silk == want else
              f'silkscreen = "{silk}" on a {mask} mask – {m.name} prints {want} on it; choose silkscreen = "{want}" '
              "or another mask", f"{want} on a {mask} mask")


def placeholders(board, data, maker=None):
    """[(side, (x, y))] of the order-number placeholder on a silkscreen layer of pcb.json, and the heights
    [[silk.texts]] gives it – the maker's placeholder, or JLCPCB's where the maker has none (the text it would print)."""
    text = (maker.rules.get("placeholder") if maker is not None else None) or PLACEHOLDER
    mm = 25.4 / 1000
    found = [(SILK[s["Layer"]], (s["X"] * mm, s["Y"] * mm)) for s in data.get("strings", [])
             if s.get("Layer") in SILK and text in str(s.get("Text", ""))]
    heights = [float(t.get("h_mm", 1.2)) for t in board.silk.get("texts", []) if text in str(t.get("text", ""))]
    return found, heights


def foreign(board, data, text):
    """[(side, (x, y))] of a placeholder text on a silkscreen layer of pcb.json."""
    mm = 25.4 / 1000
    return [(SILK[s["Layer"]], (s["X"] * mm, s["Y"] * mm)) for s in data.get("strings", [])
            if s.get("Layer") in SILK and text in str(s.get("Text", ""))]


def check_mark(c, o, data):
    board, m = c.board, c.maker
    mark, holder = o["mark"], m.rules.get("placeholder")
    # another maker's placeholder on the silkscreen is text to this one: it prints the letters as they are
    for text, owner in makers.placeholders(c.cfg).items():
        if text == holder or not (found := foreign(board, data, text)):
            continue
        c.add(f"no {text} on the silkscreen – " + (f"{m.name}'s placeholder is {holder}" if holder else
                                                    f"{m.name} has no order-number placeholder"), False,
              f"{text} at {pt(found[0][1])} on the {found[0][0]} silkscreen – {m.name} prints it as it is; a "
              f"release that carries it is a release for {owner}", "no placeholder of another maker")
    if not holder:
        return
    gone = m.rules.get("placeholder_gone")    # the maker reports its order number gone: the letters may be printed
    if gone and (mark == "specify" or foreign(board, data, holder)):
        at = foreign(board, data, holder)
        c.add(f"{holder}: {m.name}'s order number at the placeholder", False,
              (f"{holder} at {pt(at[0][1])} on the {at[0][0]} silkscreen" if at else f'mark = "{mark}"')
              + f" – {gone}; take the placeholder off (mark = \"remove\", a barcode = \"qr\" or \"datamatrix\" "
              "for traceability), or accept it once ordering step 0 has seen the form", "no placeholder", "warn")
    word = m.word("mark", mark)
    found, heights = placeholders(board, data, m)
    what = f"order-number mark = placeholder {holder} on the silkscreen"
    where = f"{holder} at {pt(found[0][1])} on the {found[0][0]} silkscreen" if found else ""
    if mark != "specify":
        if found:
            c.add(what, False, f'{where}, but mark = "{mark}" – {m.name} prints its number elsewhere and leaves the '
                  'placeholder as text; choose mark = "specify"', "mark = specify", "warn")
        else:
            c.add(what, True, f'mark = "{mark}": {word}', "no placeholder")
        return
    least = float(m.rules.get("placeholder_min_mm", 0))
    want = f">= {least:g} mm high"
    if not found:
        c.add(what, False, f"no {holder} on a silkscreen layer (pcb.json) – place it ([[silk.texts]], edakit silk "
              "apply) or choose another mark", f"placeholder, {want}")
    elif not heights:
        c.add(what, False, f"{where}: its height is not in [[silk.texts]] – not checked", want, "warn")
    else:
        h = min(heights)
        c.add(what, h >= least - 1e-9, f"{where}, {h:.2f} mm high" if h >= least - 1e-9
              else f"{holder} {h:.2f} mm high ([[silk.texts]] h_mm) – {m.name} needs {want}", want)


def check_tooling(c, pcba):
    board, m = c.board, c.maker
    least = (m.rules.get("tooling_min") or {}).get(pcba[0])
    if least is None:
        return
    n = len(board.tooling)
    if n >= least:
        actual = f"{n} tooling holes: {m.word('tooling', 'customer')}"
    else:
        actual = (f"{n} tooling hole" if n else "no tooling holes ([tooling])") + f" – {m.name} adds its own " \
            f"({m.word('tooling', 'maker')}), maybe on a visible edge; add [tooling] holes or accept"
    c.add(f"tooling holes of the {pcba[0].capitalize()} PCBA ({pcba[1]})", n >= least, actual, f">= {least} ([tooling])",
          None if n >= least else "warn")


def check_fields(c, fields, o):
    """Every field's value one the maker's form offers; no combination its profile excludes."""
    m = c.maker
    asked = [f for f in fields if f["key"] not in DERIVED and f["raw"] is not None and f["key"] != "thickness_mm"]
    bad = [f for f in asked if m.offers(f["key"], f["raw"]) is False]
    for f in bad:
        offered = m.offered(f["key"])
        c.add(f"{f['label']}: a value {m.name}'s form offers", False,
              f"{f['key']} = {f['raw']!r} ({f['from']}) – {m.name} offers "
              + ", ".join(repr(v) for v in offered), "one of " + ", ".join(repr(v) for v in offered))
    known = [f for f in asked if m.offers(f["key"], f["raw"]) is not None]
    if known and not bad:
        c.add(f"every field of the form is one {m.name}'s form offers", True,
              f"{len(known)} fields with the form's values", "offered")
    for ex in m.data.get("excludes") or []:
        if all(o.get(k) == v for k, v in ex.items()):
            shown = ", ".join(f"{k} = {v!r}" for k, v in ex.items())
            c.add(f"no combination {m.name}'s form refuses", False, f"{shown} – {m.name} does not make it",
                  "not excluded")
    if m.recorded is None:
        open_ = [f["label"] for f in asked if m.offers(f["key"], f["raw"]) is None and f["key"] not in FREE]
        c.add(f"{m.name}'s profile", True, "provisional (recorded = false): labels and words from edakit's reference "
              "orders, not yet read off the form (ordering step 0)" + (f"; values not known for {len(open_)} fields, "
                                                                        "not checked" if open_ else ""),
              "recorded", "info")


def check_derived(cfg, board, o, g, rows):
    """Keys only to check (layers, size_mm), a panel edakit does not draw, the quantities – the same for every maker."""
    layers, size = facts(g)
    if "layers" in o.get("_from", {}):
        rows.add("F", "FILES.order", board.name, "layers = the run's Gerber files ([order] layers)", o["layers"] == layers,
                 f"{layers} copper layers in the Gerber files", f"{o['layers']} ([order] layers)")
    if "size_mm" in o.get("_from", {}):
        ok = size is not None and all(abs(a - b) <= SIZE_TOL_MM for a, b in zip(sorted(size), sorted(o["size_mm"])))
        rows.add("F", "FILES.order", board.name, "size = the run's Gerber outline ([order] size_mm)", ok,
                 f"{size[0]:.2f} x {size[1]:.2f} mm (Gerber outline)" if size else "no closed outline",
                 f"{o['size_mm'][0]:g} x {o['size_mm'][1]:g} mm ± {SIZE_TOL_MM} mm")
    if o["delivery"] == "panel_by_customer":
        rows.add("F", "FILES.order", board.name, "delivery = the run's files", False, 'delivery = "panel_by_customer" – the '
                 "run's Gerber is one board, edakit draws no panel; single, or panel_by_maker with panel",
                 "single or panel_by_maker")
    q, n = o["quantity"], o["pcba_quantity"]
    rows.add("F", "FILES.order", board.name, "PCBA quantity at most the PCB quantity", n <= q,
             f"pcba_quantity {n}, quantity {q}", "pcba_quantity <= quantity")
    if n != cfg.quantity:
        rows.add("F", "FILES.order", board.name, "PCBA quantity = [project] quantity (the sets PARTS.stock counts)", False,
                 f"pcba_quantity {n}, [project] quantity {cfg.quantity} – the stock checks count "
                 f"{cfg.quantity} sets", f"{cfg.quantity}", "warn")


def check_tabs(board, o, g, rows):
    """Copper against the declared tab zones; returns (polygon, free stretches, [(zone text, distance)]) or None."""
    from shapely.geometry import Point
    from shapely.ops import nearest_points
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
    """(text, parts with MSL >= 5, snapshot or None) from the stock snapshot."""
    snap = stock.load(cfg)
    if snap is None:
        return "check the BOM tool – no stock snapshot (edakit stock)", [], None
    hot = [f"{stock.refs_text(refs)} {lcsc} MSL {snap['parts'][lcsc]['msl']}"
           for lcsc, refs in stock.assembled(design, board.name).items()
           if (snap.get("parts", {}).get(lcsc, {}).get("msl") or 0) >= stock.BAKE_MSL]
    return (", ".join(hot) if hot else f"no part with MSL >= {stock.BAKE_MSL}"), hot, snap


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


def sheet(cfg, design, board, maker, o, fields, bom, tabs):
    """order.md: the fields of the planned maker's form, the upload files, the tab zones, what is bought separately."""
    given = makers.of(cfg).get("given")
    L = [f"# Order form – board {board.name} ({board.title}), {cfg.project}\n",
         f"Written by edakit for {maker.name} ({'[cart] maker' if given else 'the maker without [cart]'}) from the "
         "keys of [order] – edakit's defaults, [order] of edakit.toml and of the board file –, [release] assembly, "
         "the stock snapshot and the files of this run; check FILES.order compares them. Upload only from a released run "
         "(manifest.json); `edakit cart prepare` fills the form from these fields. Coordinates: Gerber mm. The "
         "settings that change the board as made count in the fab hash (order.json): a sign-off of scope fab, like "
         "M-5, holds for them as written here.\n"]
    if maker.recorded is None:
        L.append(f"The profile of {maker.name} is provisional (recorded = false): labels and words from edakit's "
                 "reference orders, not yet read off the form (ordering step 0).\n")
    for section, title in (("PCB", "PCB"), ("PCBA", "PCB Assembly"), ("Shipping", "Shipping")):
        rows = [f for f in fields if f["section"] == section]
        L.append(f"## {title}\n")
        if section == "PCBA" and not bom:
            L.append("None – no part of this board is assembled (PCB only).\n")
            continue
        if not rows:
            L.append("–\n")
            continue
        L += ["| Field | Value | From |", "|---|---|---|"]
        for f in rows:
            value = f"below ({f['note']})" if f["key"] == "remark" and f["raw"] else field_text(f)
            L.append(f"| {f['label']} | {value} | {f['from']} |")
        L.append("")
        if section == "PCB" and o["remark"]:
            L += ["```text", o["remark"], "```", ""]
    files = maker.upload(board.name)
    L += ["## Upload\n", "| File | Content |", "|---|---|"]
    names = {"bom": f"bom_{board.name}.csv", "cpl": f"cpl_{board.name}.csv"}
    if names["bom"] in files and names["cpl"] in files:
        L.append(f"| BOM / CPL | {names['bom']} ({len(bom)} lines) / {names['cpl']} |")
    for f in files:
        if f in names.values() and names["bom"] in files and names["cpl"] in files:
            continue
        what = {"zip": "Gerber and drill files" if f.startswith("gerber_") else "ODB++: board, parts, placement"}.get(
            f.rsplit(".", 1)[-1], "BOM with manufacturer part numbers" if f.endswith("_mpn.csv") else "")
        label = "Gerber" if f.startswith("gerber_") else what
        L.append(f"| {label} | {f} |" if f.startswith("gerber_") else f"| {f} | {what} |")
    L.append("")
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
    """FILES.order, order.md and order.json for one board – when it has [order] (of its board file or of edakit.toml) or the
    project has [cart]; order.json only with [order]: without it a stale order.json of an earlier run in d goes, so
    that the fab hash holds no settings the project does not give."""
    import json
    if board.order is None:
        (d / SETTINGS).unlink(missing_ok=True)
    else:
        (d / SETTINGS).write_text(json.dumps(settings(board), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    o = order_of(cfg, board)
    if o is None:
        return
    data = json.loads((d / "pcb.json").read_text())
    planned = makers.get(cfg)
    for m in makers.all_of(cfg):
        c = Check(cfg, board, m, rows)
        pcba = makers.pcba(cfg, m.key)
        fields = form(cfg, design, board, d, m, o, bom, placeholders(board, data, m)[0])
        check_fields(c, fields, o)
        check_remark(c, o["remark"])
        check_material(c, o)
        check_mark(c, o, data)
        if bom:
            check_tooling(c, pcba)
    tabs = check_tabs(board, o, d / "gerber", rows)
    check_derived(cfg, board, o, d / "gerber", rows)
    fields = form(cfg, design, board, d, planned, o, bom, placeholders(board, data, planned)[0])
    (d / "order.md").write_text(sheet(cfg, design, board, planned, o, fields, bom, tabs), encoding="utf-8")
    pcba = makers.pcba(cfg)
    rows.add("F", "FILES.order", board.name, "order form of this run", True,
             f"order.md: {planned.name}, {pcba[0].capitalize() + ' PCBA' if bom else 'PCB only'}, mark "
             f"{planned.word('mark', o['mark'])}"
             + (f", tooling {planned.word('tooling', 'customer' if board.tooling else 'maker')}" if bom else ""),
             "information", "info")
