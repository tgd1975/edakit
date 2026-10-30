"""Own footprints as data in the parts entry (handbook 4.5): the footprint of a part as text – origin, pads, outline
and print in mm –, from which edakit builds the project's copy in EasyEDA and to which it holds the copy.

    edakit part footprint KEY [--board B] [--write]
                    a library footprint becomes an own one: the footprint pcb dump measured on a placed part of KEY
                    (<board>.geometry.json), else the one edakit part import cached, as data; --write puts it into the
                    entry as footprint_data. From then on a footprint change is a line of text
    edakit part build KEY [--board B] [--write]
                    the project's copy from the data: offline what would be built; --write rebuilds, under the EasyEDA
                    claim, the copy of the carrier – the device the part is placed with, from its LCSC number or its
                    easyeda_device – in the project library (eda.build_copy): its footprint, and with "symbol": "box"
                    its symbol. It changes project-library:<b> (8.6)

The field footprint_data of a parts entry – mm, y up, seen from the top at 0°, as pcb dump measures (in mil there):

    origin   [x, y], optional: where the footprint's origin lies in these coordinates – the point [place] positions
             and pcb dump measures from (default [0, 0])
    pads     number -> {x, y, shape (RECT, ELLIPSE, OVAL), w, h, rot (degrees, default 0), layer (TOP, BOTTOM or
             MULTI; default MULTI with a hole, TOP without), hole [w, l] (a slot when l > w), plated (default true),
             mechanical (true on a pad whose number is no pin of the entry: a mounting pad)} – the form edakit part
             import caches pads in, in mm
    pads_same_number   number -> [pad, …]: every pad of a number used several times (shell legs), as in the cache;
             pads holds the first of them
    lines    [{points [[x, y], …], width}]: silkscreen polylines, closed when the last point is the first
    texts    [{text, x, y, size, width, rot}]: silkscreen texts, centred on x, y
    marks    [{sign "+" or "−", x, y, size, width}]: polarity marks on the silkscreen – a "+" two strokes of size, as
             L-8 finds them in the Gerber file, a "−" one
    outline  [[x, y], …]: the body on the component-shape layer – the part's extent in EasyEDA
    symbol   "box": the copy's symbol is rebuilt as a box with the entry's pins on the sides its "symbol" names, as
             edakit schematic draw draws one; without it the carrier's symbol stays
Width defaults to 0.15 mm (JLCPCB's thinnest print). Without lines, texts, marks and outline the build keeps the print
of the copy; with any of them the copy's print is exactly the data's.

Checks (checks.run, only where an entry of the parts database has footprint_data – a project without keeps its
checks):
  P-9   the footprint data of a parts entry is complete and consistent: every pad with its place, shape and size, a
        through-hole pad with its hole; every pad a pin of the entry or mechanical, every pin a pad; lines, texts,
        marks and the outline well formed; a polarity mark next to a pad whose role has its sign (L-8's test, on the
        data); a symbol box whose sides name pins of the entry, each once
  P-10  the copy equals the data: the footprint pcb dump measured on the board (<board>.geometry.json) has the data's
        pads – the same numbers, each within 0.02 mm of its place (L-7's tolerance), its hole and, where the dump
        measured them, its shape and size within 0.01 mm
The print is not measured by pcb dump; the gate holds it to the silkscreen of the Gerber files (L-8, L-17).
"""

from __future__ import annotations

import datetime
import json
import math
import sys

from .config import MIL_PER_MM
from .design import Design, natural_key

KEYS = ("origin", "pads", "pads_same_number", "lines", "texts", "marks", "outline", "symbol")
PAD_KEYS = ("x", "y", "shape", "w", "h", "rot", "layer", "hole", "plated", "mechanical")
PRINT = ("lines", "texts", "marks", "outline")
SHAPES = ("RECT", "ELLIPSE", "OVAL")               # pad shapes the data knows (EasyEDA's names)
LAYERS = {"TOP": 1, "BOTTOM": 2, "MULTI": 12}       # EasyEDA layer ids of pads
SIGNS = {"+": "+", "−": "−", "-": "−"}             # a mark's sign; "-" is read as the minus L-8 uses
SILK = 3                    # EasyEDA: top silkscreen – a footprint is drawn as seen from the top
COMPONENT_SHAPE = 48        # EasyEDA: the component's shape, its extent
PRINT_LAYERS = (3, 48, 49, 50)   # replaced by a build with print: silkscreen, shape, marking, pin soldering
PRINT_CLASSES = ("PCB_PrimitivePolyline", "PCB_PrimitiveLine", "PCB_PrimitiveArc", "PCB_PrimitiveFill",
                 "PCB_PrimitiveString")
WIDTH_MM = 0.15             # default line width: JLCPCB does not print thinner (silk.MIN_SILK_MM)
OUTLINE_MIL = 6             # the outline's line on the component-shape layer, as the bell drew it
FONT = "default"            # EasyEDA's stroke font
CENTRE = 5                  # EPCB_PrimitiveStringAlignMode.CENTER
CHAR_W = 0.6                # the stroke font: about 0.6 × height per character (handbook 9.4) – for the box only
POS_MM = 0.02               # P-10: a pad further than this from its place in the data is elsewhere (L-7's tolerance)
SIZE_MM = 0.01              # P-10: a hole or pad size that differs by more than this differs
PIN_LENGTH = 10             # symbol: pins 10 units of 10 mil long, as edakit schematic draw draws them
READBACK_MIL = 0.5          # the editor's pads read back: within this of what was created (the bell's check)


class FootprintError(Exception):
    pass


def data_of(entry):
    """The footprint data of a parts entry, None without."""
    return (entry or {}).get("footprint_data")


def has_data(parts):
    """Whether any entry of the parts database (key -> entry) has footprint data."""
    return any("footprint_data" in (e or {}) for e in parts.values())


def own_symbol(entry):
    """The copy's symbol is built from the entry: footprint_data says "symbol": "box"."""
    data = data_of(entry)
    return isinstance(data, dict) and data.get("symbol") == "box"


def mil(v):
    return round(v * MIL_PER_MM, 3)


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def point(p):
    return isinstance(p, (list, tuple)) and len(p) == 2 and all(number(v) for v in p)


def layer_of(pad):
    return pad.get("layer") or ("MULTI" if pad.get("hole") else "TOP")


def origin(data):
    o = data.get("origin", [0, 0])
    return (o[0], o[1]) if point(o) else (0, 0)


def pad_list(data):
    """[(number, pad)] – every pad, each leg of a number used several times (pads_same_number)."""
    same = data.get("pads_same_number") or {}
    out = []
    for n, pad in (data.get("pads") or {}).items():
        legs = same.get(n) if isinstance(same, dict) else None
        out += [(n, p) for p in (legs if isinstance(legs, list) and legs else [pad])]
    return out


def sorted_numbers(numbers):
    return sorted(numbers, key=natural_key)


# --- P-9: complete and consistent ---------------------------------------------------------------------------------

def numbers_text(numbers, word="pad"):
    """"pad 3", "pads 1–24", "pads 1–3, 7, A1": runs of whole numbers written from–to."""
    ns = sorted_numbers(dict.fromkeys(numbers))
    parts, run = [], []
    for n in ns + [None]:
        if n is not None and n.isdigit() and run and int(n) == int(run[-1]) + 1:
            run.append(n)
            continue
        if run:
            parts.append(f"{run[0]}–{run[-1]}" if len(run) > 2 else ", ".join(run))
        run = [n] if n is not None and n.isdigit() else []
        if n is not None and not n.isdigit():
            parts.append(n)
    return f"{word}{'s' * (len(ns) > 1)} {', '.join(parts)}"


def pad_problems(pad):
    """What a pad of the data lacks or has wrong, without its number."""
    if not isinstance(pad, dict):
        return ["not an object"]
    out = []
    if foreign := [k for k in pad if k not in PAD_KEYS]:
        out.append(f"no field {', '.join(foreign)} ({', '.join(PAD_KEYS)})")
    if not (number(pad.get("x")) and number(pad.get("y"))):
        out.append("x and y (mm) missing")
    if pad.get("shape") not in SHAPES:
        out.append(f"shape {pad.get('shape')!r} – one of {', '.join(SHAPES)}"
                   if "shape" in pad else f"shape missing ({', '.join(SHAPES)})")
    if not all(number(pad.get(k)) and pad[k] > 0 for k in ("w", "h")):
        out.append("size w and h (mm) missing")
    if "rot" in pad and not number(pad["rot"]):
        out.append("rot is not a number of degrees")
    layer = pad.get("layer")
    if layer is not None and layer not in LAYERS:
        out.append(f"layer {layer!r} – TOP, BOTTOM or MULTI")
    hole = pad.get("hole")
    if hole is not None and not (point(hole) and 0 < hole[0] <= hole[1]):
        out.append("hole is not [width, length] mm with 0 < width <= length")
    elif layer == "MULTI" and not hole:
        out.append("a through-hole pad (MULTI) without hole")
    elif layer in ("TOP", "BOTTOM") and hole:
        out.append(f"a hole in a pad on {layer} – a through-hole pad is MULTI")
    for k in ("plated", "mechanical"):
        if k in pad and not isinstance(pad[k], bool):
            out.append(f"{k} is true or false")
    return out


def same_pad(a, b):
    return isinstance(a, dict) and isinstance(b, dict) and all(a.get(k) == b.get(k) for k in PAD_KEYS)


def mark_problems(i, mark, data, pins):
    """A polarity mark: its sign, place and size – and L-8's test on the data: the nearest pad whose pin role has a
    sign has this one."""
    from .release.fab import role_sign
    if not isinstance(mark, dict):
        return [f"marks[{i}] is not an object"]
    sign = SIGNS.get(mark.get("sign"))
    out = []
    if sign is None:
        out.append(f"marks[{i}]: sign {mark.get('sign')!r} – \"+\" or \"−\"")
    if not (number(mark.get("x")) and number(mark.get("y"))):
        out.append(f"marks[{i}]: x and y (mm) missing")
    if not (number(mark.get("size")) and mark["size"] > 0):
        out.append(f"marks[{i}]: size (mm, the length of a stroke) missing")
    if "width" in mark and not (number(mark["width"]) and mark["width"] > 0):
        out.append(f"marks[{i}]: width is not a length in mm")
    if out:
        return out
    polar = [(n, p, role) for n, p in pad_list(data) if isinstance(p, dict) and number(p.get("x"))
             and number(p.get("y")) and (role := (pins.get(n) or {}).get("role")) and role_sign(role)]
    if not polar:
        return [f"marks[{i}]: '{sign}' at ({mark['x']:g}, {mark['y']:g}) mm, but no pad of the entry has a pin role "
                "with a sign (anode, cathode, plus, minus, vbus)"]
    n, _, role = min(polar, key=lambda t: math.hypot(t[1]["x"] - mark["x"], t[1]["y"] - mark["y"]))
    if role_sign(role) != sign:
        return [f"marks[{i}]: '{sign}' at ({mark['x']:g}, {mark['y']:g}) mm – the nearest polarised pad {n} is "
                f"{role}"]
    return []


def symbol_problems(entry):
    """With "symbol": "box", the sides of the entry's symbol name pins of the entry, each once."""
    pins = entry.get("pins") or {}
    spec = entry.get("symbol")
    if spec is None:
        return []
    if not isinstance(spec, dict) or not all(isinstance(v, list) for v in spec.values()):
        return ["symbol is not {\"left\": [pins], \"right\": [...], \"top\": [...], \"bottom\": [...]}"]
    out = []
    if foreign := [k for k in spec if k not in ("left", "right", "top", "bottom")]:
        out.append(f"symbol has no side {', '.join(foreign)} (left, right, top, bottom)")
    listed = [str(p) for side in spec.values() for p in side]
    if wrong := sorted_numbers({p for p in listed if p not in pins or listed.count(p) > 1}):
        out.append(f"symbol lists pin{'s' * (len(wrong) > 1)} {', '.join(wrong)} twice or the entry has none")
    return out


def problems(entry):
    """P-9: [(level, text)] – level "error" – what keeps the footprint data of a parts entry from being complete and
    consistent. [] when it is."""
    data = data_of(entry)
    if not isinstance(data, dict):
        return [("error", "footprint_data is not an object")]
    out = []
    if foreign := [k for k in data if k not in KEYS]:
        out.append(f"footprint_data has no field {', '.join(foreign)} ({', '.join(KEYS)})")
    if not entry.get("footprint"):
        out.append("footprint missing – the name of the copy in EasyEDA, which L-4 compares with the PCB")
    if "origin" in data and not point(data["origin"]):
        out.append("origin is not [x, y] in mm")
    if data.get("symbol") not in (None, "box"):
        out.append(f"symbol {data['symbol']!r} – \"box\", or none: the carrier's symbol stays")
    pads, same = data.get("pads"), data.get("pads_same_number", {})
    if not isinstance(pads, dict) or not pads:
        return [("error", t) for t in out + ["pads missing – number -> {x, y, shape, w, h, …}"]]
    wrong = {}                     # the same problem of several pads: one finding, "pads 1–24: …"
    for n, pad in pads.items():
        for what in pad_problems(pad):
            wrong.setdefault(what, []).append(n)
    if not isinstance(same, dict):
        out.append("pads_same_number is not number -> [pad, …]")
        same = {}
    for n, legs in same.items():
        if n not in pads:
            out.append(f"pads_same_number {n}: there is no pad {n} in pads")
        elif not isinstance(legs, list) or len(legs) < 2:
            out.append(f"pads_same_number {n}: not a list of the pads of number {n} – at least two")
        else:
            for what in dict.fromkeys(w for leg in legs for w in pad_problems(leg)):
                wrong.setdefault(f"{what} (pads_same_number)", []).append(n)
            if not any(same_pad(pads[n], leg) for leg in legs):
                out.append(f"pad {n}: not one of its pads_same_number")
    out += [f"{numbers_text(ns)}: {what}" for what, ns in wrong.items()]
    pins = entry.get("pins") or {}
    if lone := [n for n, p in pads.items() if n not in pins and not (isinstance(p, dict) and p.get("mechanical"))]:
        out.append(f"{numbers_text(lone)} without a pin in the entry – a pin of that number, or \"mechanical\": true "
                   "on a mounting pad")
    if padless := [p for p in pins if p not in pads]:
        out.append(f"{numbers_text(padless, 'pin')} without a pad")
    lines, texts, marks, shape = (data.get(k, []) for k in ("lines", "texts", "marks", "outline"))
    for key, items in (("lines", lines), ("texts", texts), ("marks", marks)):
        if not isinstance(items, list):
            out.append(f"{key} is not a list")
    for i, line in enumerate(lines if isinstance(lines, list) else []):
        pts = line.get("points") if isinstance(line, dict) else None
        if not (isinstance(pts, list) and len(pts) >= 2 and all(point(p) for p in pts)):
            out.append(f"lines[{i}]: points is not a list of at least two [x, y]")
        if isinstance(line, dict) and "width" in line and not (number(line["width"]) and line["width"] > 0):
            out.append(f"lines[{i}]: width is not a length in mm")
    for i, text in enumerate(texts if isinstance(texts, list) else []):
        if not (isinstance(text, dict) and isinstance(text.get("text"), str) and text["text"].strip()):
            out.append(f"texts[{i}]: text missing")
            continue
        if not (number(text.get("x")) and number(text.get("y")) and number(text.get("size")) and text["size"] > 0):
            out.append(f"texts[{i}] '{text['text']}': x, y and size (mm) missing")
        if "rot" in text and not number(text["rot"]):
            out.append(f"texts[{i}] '{text['text']}': rot is not a number of degrees")
    for i, mark in enumerate(marks if isinstance(marks, list) else []):
        out += mark_problems(i, mark, data, pins)
    if "outline" in data and not (isinstance(shape, list) and len(shape) >= 3 and all(point(p) for p in shape)):
        out.append("outline is not a list of at least three [x, y]")
    if data.get("symbol") == "box":
        out += symbol_problems(entry)
    return [("error", t) for t in out]


# --- the data as geometry (mil, as pcb dump and the cache) -----------------------------------------------------------

def pad_extent(pad):
    """Half width and half height of a pad's box, turned by its rotation (mm)."""
    a = math.radians(pad.get("rot", 0) or 0)
    w, h = pad["w"] / 2, pad["h"] / 2
    return abs(w * math.cos(a)) + abs(h * math.sin(a)), abs(w * math.sin(a)) + abs(h * math.cos(a))


def box(data):
    """[x0, y0, x1, y1] mm of everything the data draws – pads, lines, marks, texts (their width estimated), the
    outline –, relative to the origin."""
    ox, oy = origin(data)
    xs, ys = [], []

    def add(x, y, rx=0.0, ry=0.0):
        xs.extend((x - ox - rx, x - ox + rx))
        ys.extend((y - oy - ry, y - oy + ry))
    for _, p in pad_list(data):
        add(p["x"], p["y"], *pad_extent(p))
    for line in data.get("lines", []):
        half = line.get("width", WIDTH_MM) / 2
        for x, y in line["points"]:
            add(x, y, half, half)
    for mark in data.get("marks", []):
        half = mark["size"] / 2 + mark.get("width", WIDTH_MM) / 2
        add(mark["x"], mark["y"], half, half)
    for text in data.get("texts", []):
        w, h = len(text["text"]) * text["size"] * CHAR_W / 2, text["size"] / 2
        a = math.radians(text.get("rot", 0) or 0)
        add(text["x"], text["y"], abs(w * math.cos(a)) + abs(h * math.sin(a)), abs(w * math.sin(a)) + abs(h * math.cos(a)))
    half = OUTLINE_MIL / MIL_PER_MM / 2
    for x, y in data.get("outline", []):
        add(x, y, half, half)
    return [min(xs), min(ys), max(xs), max(ys)]


def mil_pad(pad, ox, oy):
    """A pad of the data as the cache and pcb dump have it: mil, relative to the origin."""
    out = {"x": round((pad["x"] - ox) * MIL_PER_MM, 2), "y": round((pad["y"] - oy) * MIL_PER_MM, 2), "net": "",
           "tht": bool(pad.get("hole")), "shape": pad["shape"], "w": round(pad["w"] * MIL_PER_MM, 2),
           "h": round(pad["h"] * MIL_PER_MM, 2), "rot": pad.get("rot", 0), "layer": layer_of(pad)}
    if pad.get("hole"):
        out["hole"] = [round(v, 3) for v in pad["hole"]]
        out["plated"] = pad.get("plated", True)
    return out


def geometry(entry):
    """The footprint data of a parts entry as footprint geometry – the form pcb dump and the library cache have (mil,
    relative to the origin), "source": "data" –, for pcb plan, P-7 and part diff before the copy is dumped. None when
    the data is not complete (P-9 says why)."""
    data = data_of(entry)
    if problems(entry):
        return None
    ox, oy = origin(data)
    geo = {"footprint": entry.get("footprint"), "bbox": [round(v * MIL_PER_MM, 2) for v in box(data)],
           "pads": {n: mil_pad(p, ox, oy) for n, p in data["pads"].items()}, "source": "data"}
    if same := data.get("pads_same_number"):
        geo["pads_same_number"] = {n: [mil_pad(p, ox, oy) for p in legs] for n, legs in same.items()}
    return geo


# --- P-10: the copy equals the data ----------------------------------------------------------------------------------

def normal(shape, w, h, rot):
    """(shape, w, h, rot) of a pad, written one way: a turn by 180° is none, one by 90° swaps w and h, a round pad
    has no turn."""
    rot = (rot or 0) % 180
    if abs(rot - 90) < 0.01:
        w, h, rot = h, w, 0.0
    if abs(w - h) < SIZE_MM:
        rot = 0.0 if shape == "ELLIPSE" else rot % 90
    if abs(rot) < 0.01 or abs(rot - 180) < 0.01:
        rot = 0.0
    return shape, w, h, rot


def size_text(shape, w, h, rot=0):
    return f"{shape} {w:.2f} x {h:.2f}" + (f" turned {rot:g}°" if rot else "")


def hole_text(hole):
    return "no hole" if not hole else f"hole {hole[0]:.2f}" if abs(hole[1] - hole[0]) < SIZE_MM else \
        f"slot {hole[0]:.2f} x {hole[1]:.2f}"


def copy_differences(entry, geo):
    """P-10: ([what differs], [what the dump did not measure]) between the footprint data of a parts entry and the
    footprint pcb dump measured on the board (geo: mil, relative to the placed part's origin at 0° on TOP)."""
    from .part import pad_points
    data = data_of(entry)
    ox, oy = origin(data)
    want = {}
    for n, p in pad_list(data):
        want.setdefault(n, []).append(p)
    have = {}
    for n, x, y, p in pad_points(geo):
        have.setdefault(n, []).append((x, y, p))
    diffs, unmeasured = [], set()
    if missing := set(want) - set(have):
        diffs.append(f"{numbers_text(missing)} not in the copy")
    if extra := set(have) - set(want):
        diffs.append(f"{numbers_text(extra)} in the copy, not in the data")
    for n in sorted_numbers(set(want) & set(have)):
        free = list(have[n])
        for p in want[n]:
            x, y = p["x"] - ox, p["y"] - oy
            hx, hy, hp = min(free, key=lambda q: math.hypot(q[0] - x, q[1] - y))
            free.remove((hx, hy, hp))
            if math.hypot(hx - x, hy - y) > POS_MM:
                diffs.append(f"pad {n} at ({hx:.3f}, {hy:.3f}) instead of ({x:.3f}, {y:.3f}) mm")
            hole = p.get("hole")
            if bool(hp.get("tht")) != bool(hole):
                diffs.append(f"pad {n}: " + (f"no hole in the copy, the data has {hole_text(hole)} mm" if hole else
                                             "a hole in the copy, none in the data"))
            elif hole and not hp.get("hole"):
                unmeasured.add("holes")
            elif hole and any(abs(a - b) > SIZE_MM for a, b in zip(hp["hole"], hole)):
                diffs.append(f"pad {n}: {hole_text(hp['hole'])} instead of {hole_text(hole)} mm")
            if hole and hp.get("hole") and hp.get("plated", True) != p.get("plated", True):
                diffs.append(f"pad {n}: " + ("plated" if hp.get("plated", True) else "not plated")
                             + " in the copy, " + ("plated" if p.get("plated", True) else "not plated") + " in the data")
            if not (hp.get("shape") and hp.get("w") and hp.get("h")):
                unmeasured.add("pad shapes and sizes")
                continue
            got = normal(hp["shape"], hp["w"] / MIL_PER_MM, hp["h"] / MIL_PER_MM, hp.get("rot", 0))
            should = normal(p["shape"], p["w"], p["h"], p.get("rot", 0))
            if got[0] != should[0] or any(abs(a - b) > SIZE_MM for a, b in zip(got[1:3], should[1:3])) \
                    or abs(got[3] - should[3]) > 0.01:
                diffs.append(f"pad {n}: {size_text(*got)} instead of {size_text(*should)} mm")
            if hp.get("layer") and hp["layer"] != layer_of(p):
                diffs.append(f"pad {n}: on {hp['layer']} in the copy, on {layer_of(p)} in the data")
    return diffs, sorted(unmeasured)


def users(d, key):
    """The designators whose parts entry is key, in natural order."""
    return sorted((des for des in d.comps if d.entry_key(des) == key), key=natural_key)


def check(d, rep, cfg):
    """P-9 on every parts entry with footprint data that a component uses, and P-10 on every such component that pcb
    dump measured on its board."""
    from .checks import board_dumps
    keys = sorted({k for des in d.comps if (k := d.entry_key(des)) and "footprint_data" in d.parts[k]},
                  key=natural_key)
    valid = set()
    for key in keys:
        found = problems(d.parts[key])
        for _, text in found:
            rep.errors.append(("P-9", f"{', '.join(users(d, key))} {key}: {text}"))
        if not found:
            valid.add(key)
    dumped = board_dumps(d, cfg)
    unmeasured = {}
    for des in sorted(d.comps, key=natural_key):
        key = d.entry_key(des)
        if key not in keys:
            continue
        geo = dumped(des)
        if not geo:
            rep.notes.append(("P-10", f"{des}: not in the footprint geometry of its board – edakit pcb dump once it is "
                                      f"in the PCB; until then the copy is not compared with the data of {key}"))
            continue
        if key not in valid:
            continue                                  # P-9 says what the data lacks
        entry = d.parts[key]
        if geo.get("footprint") != entry.get("footprint"):
            rep.error("P-10", f"{des}: the dump measured footprint {geo.get('footprint')}, the entry {key} names "
                              f"{entry.get('footprint')} – not the copy (L-4): edakit pcb parts --write, then pcb dump",
                      d.comps[des].get("waive"))
            continue
        diffs, lacks = copy_differences(entry, geo)
        for what in lacks:
            unmeasured.setdefault(what, []).append(des)
        if diffs:
            rep.error("P-10", f"{des}: the copy differs from the footprint data of {key} – " + "; ".join(diffs)
                      + f" – rebuild it (edakit part build {key} --write, delete {des} in the PCB, edakit pcb parts "
                        "--write, edakit pcb dump) or correct the data", d.comps[des].get("waive"))
    for what, des in unmeasured.items():
        rep.notes.append(("P-10", f"{', '.join(des)}: {what} not measured – the dump is older than the footprint data "
                                  "(edakit pcb dump measures them)"))


# --- a library footprint becomes an own one (part footprint) -----------------------------------------------------------

def mm(v):
    return round(v / MIL_PER_MM, 3) + 0.0


def data_pad(p, lib=None):
    """A pad of a footprint geometry (mil) as data (mm): place and hole from it; shape, size, rotation and layer from
    it where the dump measured them, else from lib, the library's pad of the same number at the same place."""
    out = {"x": mm(p["x"]), "y": mm(p["y"])}
    src = p if p.get("shape") and p.get("w") and p.get("h") else lib if lib and lib.get("shape") and lib.get("w") \
        and math.hypot(lib["x"] - p["x"], lib["y"] - p["y"]) / MIL_PER_MM <= POS_MM else None
    if src:
        out.update(shape=src["shape"], w=mm(src["w"]), h=mm(src["h"]))
        if rot := round((src.get("rot") or 0) % 360, 3):
            out["rot"] = rot
    hole = p.get("hole") or (lib or {}).get("hole") if p.get("tht") else None
    layer = (src or {}).get("layer")
    if p.get("tht") and not hole:
        out["layer"] = "MULTI"                      # a hole nobody measured: P-9 asks for it
    elif layer == "BOTTOM" or (layer == "MULTI" and not hole) or (layer == "TOP" and hole):
        out["layer"] = layer
    if hole:
        out["hole"] = [round(v, 3) for v in hole]
        if p.get("plated", (lib or {}).get("plated", True)) is False:
            out["plated"] = False
    return out


def from_geometry(geo, lib=None):
    """The footprint data of a measured footprint (pcb dump, or the library cache): origin and every pad – place and
    hole, shape and size where geo has them or lib (the cached library footprint) has the pad at that place. No print:
    pcb dump does not measure it, so the build keeps the copy's print until the data has one."""
    lib_pads = (lib or {}).get("pads") or {}
    lib_same = (lib or {}).get("pads_same_number") or {}

    def partner(n, p):
        legs = lib_same.get(n) or ([lib_pads[n]] if n in lib_pads else [])
        return min(legs, key=lambda q: math.hypot(q["x"] - p["x"], q["y"] - p["y"]), default=None)
    data = {"origin": [0, 0], "pads": {n: data_pad(p, partner(n, p)) for n, p in geo["pads"].items()}}
    if same := geo.get("pads_same_number"):
        data["pads_same_number"] = {n: [data_pad({**geo["pads"][n], **q}, partner(n, q)) for q in legs]
                                    for n, legs in same.items()}
        for n, legs in data["pads_same_number"].items():      # pads holds the first leg, as the cache does
            data["pads"][n] = dict(next((q for q in legs if (q["x"], q["y"]) == (data["pads"][n]["x"],
                                                                                 data["pads"][n]["y"])), legs[0]))
    return data


def measured(cfg, d, key, board=None):
    """(geometry, where from, the board) of a parts entry's footprint: the dump of a placed component that uses it –
    on board if given –, else the library footprint edakit part import cached for its footprint name."""
    from . import part
    from .pcb import geometry_file
    boards = [cfg.board(board, made=True)] if board else list(cfg.made().values())
    for b in boards:
        dump = part._read(geometry_file(cfg, b)) or {}
        for des in users(d, key):
            if des in dump and (d.comps[des].get("board") in (None, b.name)):
                return dump[des], f"the pcb dump of {des} on board {b.name}", b
    entry = d.parts[key]
    lib = part.cached_footprint(cfg, entry.get("footprint"))
    if lib:
        return lib, f"the library footprint {entry['footprint']} (edakit part import)", None
    raise FootprintError(f"{key}: no footprint geometry – edakit pcb dump once a part of it is in the PCB, or edakit "
                         f"part import {entry.get('lcsc') or '<LCSC>'} for the library's")


def entry_key(d, key):
    """The key of a parts entry named by its key (LCSC number) or its mpn."""
    if key in d.parts:
        return key
    if key in d.by_mpn:
        return d.by_mpn[key]
    raise FootprintError(f"{key}: no parts entry of that key or mpn")


def take_over(cfg, key, board=None, write=False, today=None):
    """part footprint: (the entry's file, the data, where from, findings of P-9 on the entry with it). With write the
    data goes into the entry as footprint_data, with a line in its sources – an entry that has data is refused."""
    from . import part
    from .block import write_json
    d = Design.from_config(cfg)
    key = entry_key(d, key)
    entry = d.parts[key]
    if "footprint_data" in entry:
        raise FootprintError(f"{key}: has footprint_data already – it is an own footprint: change the data, and edakit "
                             f"part build {key} rebuilds the copy")
    geo, where, _ = measured(cfg, d, key, board)
    data = from_geometry(geo, part.cached_footprint(cfg, entry.get("footprint")))
    found = problems({**entry, "footprint_data": data})
    out = cfg.parts / f"{key}.json"
    if write:
        today = today or datetime.date.today().isoformat()
        stored = json.loads(out.read_text(encoding="utf-8"))
        stored["footprint_data"] = data
        stored["sources"] = [*(stored.get("sources") or []),
                             f"footprint_data: {where}, {today} (edakit part footprint) – the print is the copy's in "
                             "EasyEDA until lines, texts, marks or outline are written"]
        write_json(out, stored)
    return out, data, where, found


# --- the build: data -> EasyEDA (part build) ----------------------------------------------------------------------------

def poly(points, close=False):
    """An EasyEDA polygon source in mil: x0, y0, "L", x1, y1, …"""
    pts = [tuple(p) for p in points]
    if close and pts[0] != pts[-1]:
        pts.append(pts[0])
    out = [round(pts[0][0], 3), round(pts[0][1], 3), "L"]
    for x, y in pts[1:]:
        out += [round(x, 3), round(y, 3)]
    return {"$polygon": out}


def pad_args(n, pad, ox, oy):
    """The arguments of PCB_PrimitivePad.create for a pad of the data: layer, number, x, y (mil), rotation, shape,
    net, hole, hole offset x and y, hole rotation, metallization. A slot runs along the pad's longer side (hole
    rotation 0 along w, 90 along h – an assumption the live run of step 3.6 has to confirm)."""
    w, h = mil(pad["w"]), mil(pad["h"])
    shape = ["RECT", w, h, 0] if pad["shape"] == "RECT" else [pad["shape"], w, h]
    hole, turn = None, 0
    if pad.get("hole"):
        hw, hl = pad["hole"]
        hole = ["ROUND", mil(hw)] if hl - hw < 1e-9 else ["SLOT", mil(hw), mil(hl)]
        turn = 0 if hole[0] == "ROUND" or pad["w"] >= pad["h"] else 90
    return [LAYERS[layer_of(pad)], n, mil(pad["x"] - ox), mil(pad["y"] - oy), pad.get("rot", 0) or 0, shape, "", hole,
            0, 0, turn, bool(pad.get("plated", True)) if hole else False]


def mark_strokes(mark):
    """The strokes of a polarity mark (mm): a "+" two of its size crossing at its place, a "−" one."""
    x, y, half = mark["x"], mark["y"], mark["size"] / 2
    strokes = [[[x - half, y], [x + half, y]]]
    if SIGNS[mark["sign"]] == "+":
        strokes.append([[x, y - half], [x, y + half]])
    return strokes


def symbol_box(entry):
    """The copy's symbol as a box: (rectangle args, [pin args]) for SCH_PrimitiveRectangle.create and
    SCH_PrimitivePin.create, in the schematic's units (10 mil, y up) – the box edakit schematic draw draws, every pin
    of the entry on it (those its "symbol" does not name on the right)."""
    from .schematic_draw import box as draw_box
    from .schematic_draw import box_sides, pin_key
    pins = entry.get("pins") or {}
    numbers = sorted(pins, key=pin_key)
    roles = {p: str((pins[p] or {}).get("role") or "") for p in numbers}
    sides = box_sides(entry.get("kind"), numbers, roles, set(numbers), entry.get("symbol"))
    names = {p: str((pins[p] or {}).get("name") or p) for p in numbers}
    s, _, _, (x0, y0, x1, y1) = draw_box(sides, names, "", "")
    rect = [x0, y1, x1 - x0, y1 - y0, 0, 0, None, None, 1, 0]
    return rect, [[x, y, p, names[p], turn, PIN_LENGTH] for p, (x, y, turn) in sorted(s.pins.items(),
                                                                                     key=lambda kv: pin_key(kv[0]))]


def build_ops(entry):
    """What edakit part build does in the copy's editors, as data: {"pads": [args of PCB_PrimitivePad.create],
    "print": [(API path, args)] or None (None: the copy keeps its print), "symbol": (rectangle args, [pin args]) or
    None (the carrier's symbol stays)} – mil and y up, relative to the origin: the footprint editor's coordinates.
    A pure function; eda.build_copy carries it out."""
    data = data_of(entry)
    ox, oy = origin(data)
    pads = [pad_args(n, p, ox, oy) for n, p in pad_list(data)]
    printed = None
    if any(k in data for k in PRINT):
        printed = []

        def at(p):
            return [mil(p[0] - ox), mil(p[1] - oy)]
        for line in data.get("lines", []):
            closed = line["points"][0] == line["points"][-1] and len(line["points"]) > 2
            printed.append(("PCB_PrimitivePolyline.create",
                            ["", SILK, poly([at(p) for p in line["points"]], closed), mil(line.get("width", WIDTH_MM)),
                             False]))
        for text in data.get("texts", []):
            x, y = at((text["x"], text["y"]))
            printed.append(("PCB_PrimitiveString.create",
                            [SILK, x, y, text["text"], FONT, mil(text["size"]), mil(text.get("width", WIDTH_MM)),
                             CENTRE, text.get("rot", 0) or 0, False, 0, False, False]))
        for mark in data.get("marks", []):
            for stroke in mark_strokes(mark):
                printed.append(("PCB_PrimitivePolyline.create",
                                ["", SILK, poly([at(p) for p in stroke]), mil(mark.get("width", WIDTH_MM)), False]))
        if data.get("outline"):
            printed.append(("PCB_PrimitivePolyline.create",
                            ["", COMPONENT_SHAPE, poly([at(p) for p in data["outline"]], close=True), OUTLINE_MIL,
                             False]))
    return {"pads": pads, "print": printed, "symbol": symbol_box(entry) if own_symbol(entry) else None}


def readback_differences(entry, pads, pins=None):
    """What the copy's editors hold after the build against the data: pads read back in the footprint editor
    (PCB_PrimitivePad.getAll, their state) – numbers, places within READBACK_MIL, shapes and sizes, holes –, and with
    a symbol box the pins (number -> name) read back in the symbol editor. [] when they agree."""
    want = {}
    for args in build_ops(entry)["pads"]:
        want.setdefault(args[1], []).append(args)
    have = {}
    for p in pads:
        have.setdefault(str(p.get("PadNumber")), []).append(p)
    out = []
    if missing := set(want) - set(have):
        out.append(f"{numbers_text(missing)} not created")
    if extra := set(have) - set(want):
        out.append(f"{numbers_text(extra)} there but not in the data")
    for n in sorted_numbers(set(want) & set(have)):
        free = list(have[n])
        for args in want[n]:
            x, y = args[2], args[3]
            got = min(free, key=lambda p: math.hypot((p.get("X") or 0) - x, (p.get("Y") or 0) - y))
            free.remove(got)
            if math.hypot((got.get("X") or 0) - x, (got.get("Y") or 0) - y) > READBACK_MIL:
                out.append(f"pad {n} at ({got.get('X')}, {got.get('Y')}) instead of ({x}, {y}) mil")
            shape = got.get("Pad") or []
            if shape[:3] and (shape[0] != args[5][0] or any(abs(a - b) > READBACK_MIL for a, b in
                                                             zip(shape[1:3], args[5][1:3]))):
                out.append(f"pad {n}: {shape[:3]} instead of {args[5][:3]}")
            hole = got.get("Hole")
            if bool(hole) != bool(args[7]) or (hole and (hole[0] != args[7][0] or any(
                    abs(a - b) > READBACK_MIL for a, b in zip(hole[1:], args[7][1:])))):
                out.append(f"pad {n}: hole {hole} instead of {args[7]}")
    if pins is not None and own_symbol(entry):
        names = {p: str((v or {}).get("name") or p) for p, v in (entry.get("pins") or {}).items()}
        if pins != names:
            wrong = sorted_numbers({p for p in set(pins) | set(names) if pins.get(p) != names.get(p)})
            out.append("symbol pins differ: " + ", ".join(f"{p} {pins.get(p, '–')} instead of {names.get(p, '–')}"
                                                         for p in wrong))
    return out


def summary(entry):
    """One line of what the build makes: pads, print, symbol."""
    data, ops = data_of(entry), build_ops(entry)
    holes = sum(1 for args in ops["pads"] if args[7])
    parts = [f"{len(ops['pads'])} pads" + (f" ({holes} with a hole)" if holes else "")]
    if ops["print"] is None:
        parts.append("the copy's print kept")
    else:
        counts = [(len(data.get(k, [])), k.rstrip("s")) for k in ("lines", "texts", "marks")]
        parts.append(", ".join(f"{n} {w}{'s' * (n != 1)}" for n, w in counts if n) or "no print")
        if data.get("outline"):
            parts.append("outline")
    if ops["symbol"]:
        parts.append(f"symbol: a box with {len(ops['symbol'][1])} pins")
    else:
        parts.append("the carrier's symbol kept")
    return ", ".join(parts)


def carrier(cfg, d, key, board):
    """The components of board that use the entry key – the carrier's copies are found through them."""
    on = [des for des in users(d, key) if d.comps[des].get("board") in (None, board.name)]
    if not on:
        raise FootprintError(f"{key}: no component of board {board.name} uses it – nothing to build")
    return on


def build(cfg, key, board=None, write=False, mcp=None):
    """part build: (entry key, entry, the components that carry it, [what differs after a write], the recorded change
    of the project library or None). Offline (write False) only the data is checked and the plan made; with write the
    copy is rebuilt in EasyEDA (eda.build_copy), read back, and the change recorded (scripts.record_library_change)."""
    from . import eda, scripts
    d = Design.from_config(cfg)
    key = entry_key(d, key)
    entry = d.parts[key]
    if "footprint_data" not in entry:
        raise FootprintError(f"{key}: no footprint_data – edakit part footprint {key} --write takes the footprint over "
                             "as data first")
    if found := problems(entry):
        raise FootprintError(f"{key}: the footprint data is not complete (P-9) – " + "; ".join(t for _, t in found))
    b = cfg.board(board, made=True)
    on = carrier(cfg, d, key, b)
    if not write:
        return key, entry, on, [], None
    from .toolchain import is_kicad
    if is_kicad(cfg):        # KiCad: the board's library is written from the data, and the PCB's footprints with it
        from .toolchain.kicad import board as kicad_board
        kicad_board.write_parts(cfg, b, d)
        return key, entry, on, [], None
    own = mcp is None
    mcp = mcp or eda.connect(cfg)
    try:
        project = eda.open_project(mcp, cfg)
        copies = eda.find_copies(mcp, b.template, on, entry.get("lcsc"))
        back = eda.build_copy(mcp, project, copies, build_ops(entry))
        mcp.call("easyeda_project_save", projectId="current", confirmWrite=True)
    finally:
        if own:
            mcp.close()
    try:
        said = scripts.record_library_change(cfg, b.name, f"edakit part build {key}")
    except scripts.StampError as e:
        said = f"not recorded – {e}"
    return key, entry, on, readback_differences(entry, back["pads"], back.get("pins")), said


# --- commands --------------------------------------------------------------------------------------------------------

def main_footprint(cfg, args):
    if not args.source:
        raise FootprintError("the parts entry is missing (edakit part footprint C2297)")
    out, data, where, found = take_over(cfg, args.source, args.board, args.write)
    name = cfg.relative(out)
    pads = len(pad_list(data))
    if args.write:
        print(f"{name}: footprint_data from {where} – {pads} pads; the circuit and the layout hash change (4.5)")
    else:
        print(f"{name}: the footprint as data, from {where} – {pads} pads:")
        print(json.dumps(data, indent=1, ensure_ascii=False))
        print(f"  edakit part footprint {args.source} --write puts it into the entry as footprint_data")
    print("  from then on a footprint change is a line of text, and edakit part build rebuilds the copy from it; the "
          "print stays the copy's until lines, texts, marks or outline are written (handbook 4.5)")
    for _, text in found:
        print(f"  P-9 {text}")
    return 2 if found else 0


def main_build(cfg, args):
    if not args.source:
        raise FootprintError("the parts entry is missing (edakit part build C18722937)")
    key, entry, on, diffs, said = build(cfg, args.source, args.board, args.write)
    board = cfg.board(args.board, made=True).name
    head = f"{key} ({', '.join(on)} on board {board}): footprint {entry['footprint']} – {summary(entry)}"
    if not args.write:
        print(head)
        print(f"  edakit part build {key} --write rebuilds the copy in the project library of EasyEDA (under the "
              "claim)")
        return 0
    print(f"{head} – built")
    from .toolchain import is_kicad
    if is_kicad(cfg):
        print(f"  the board's library and the footprints of {', '.join(on)} in the KiCad PCB are written from the "
              "data – edakit pcb dump, then edakit check holds them to it (P-10)")
        return 0
    for text in diffs:
        print(f"  read back: {text}", file=sys.stderr)
    if said:
        print(f"  {said}")
    print(f"  the parts in the PCB keep their old copy: delete {', '.join(on)} in the PCB, edakit pcb parts --write, "
          "edakit pcb dump – then edakit check holds the copy to the data (P-10), and the round goes on through "
          "route all (handbook 4.5)")
    return 2 if diffs else 0
