"""Read an ODB++ archive – the export EasyEDA Pro writes for AISLER (getOpenDatabaseDoublePlusFile, ordering step 10) –
far enough for check SYNC.odb to hold it to the released Gerber and pick-and-place files without trusting EasyEDA.

    read(path) -> Job      a .zip or .tgz with one job: matrix, units, the step's profile, layers with features,
                           drill holes, components with their pins, nets

What is read (ODB++ v7/v8, the parts of the format a board export uses):
    matrix/matrix                       LAYER blocks: ROW, CONTEXT, TYPE, NAME, POLARITY, START_NAME/END_NAME
    steps/<step>/profile                the board outline: a surface
    steps/<step>/layers/<l>/features    symbols ($n name), attributes (@n name, &n text), features: L line, P pad,
                                        A arc, S surface (OB/OS/OC/OE, SE), T text (skipped); polarity P/N, orient
                                        0–7 and 8/9 with an angle; UNITS=MM or INCH (U MM)
    steps/<step>/layers/comp_+_top|comp_+_bot/components   CMP records (package, x, y, rotation, mirror, designator,
                                        part name, attributes such as .no_pop), PRP properties, TOP pins with their
                                        net numbers
    steps/<step>/eda/data               NET records: the net names the pins' numbers refer to

Standard symbols: r (round), s (square), rect (with xr/xc corners as a rectangle), oval, di (diamond, as a
rectangle), oct (as a rectangle), donut_r (as round). Dimensions of symbols are in mils in an INCH file and in microns
in an MM file; coordinates in inch or mm. Everything returned is in mm. Rotations as ODB++ gives them: degrees
clockwise; SYNC.odb converts them to the CPL's sense. A features file compressed with .Z is not read (named in the
error); plain and .gz are.
"""

from __future__ import annotations

import gzip
import io
import math
import re
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

INCH = 25.4


class OdbError(Exception):
    pass


@dataclass
class Layer:
    name: str
    type: str                 # SIGNAL, POWER_GROUND, MIXED, SOLDER_MASK, SILK_SCREEN, SOLDER_PASTE, DRILL, ROUT, …
    context: str              # BOARD or MISC
    row: int
    polarity: str = "POSITIVE"
    features: list = field(default_factory=list)   # [(polarity "P"/"N", gerber-style op)]
    holes: list = field(default_factory=list)      # drill layers: [(x, y, d, "plated"|"non_plated"|"via")]


@dataclass
class Component:
    designator: str
    side: str                 # "top" or "bottom"
    x: float
    y: float
    rot: float                # degrees, clockwise (ODB++)
    mirror: bool
    package: str = ""
    part: str = ""
    props: dict = field(default_factory=dict)
    attrs: dict = field(default_factory=dict)      # {".no_pop": True, ".comp_mount_type": "0"} – name: value or True
    pins: list = field(default_factory=list)       # [(pin name, x, y, net name or "")]


@dataclass
class Job:
    layers: dict              # name -> Layer, in matrix row order
    profile: list             # outline contours [[(x, y), …]] in mm
    components: list
    nets: list                # net names by number
    units: str = "MM"

    def board_layers(self):
        return [lay for lay in self.layers.values() if lay.context == "BOARD"]

    def of_type(self, *types):
        return [lay for lay in self.board_layers() if lay.type in types]


# --- the archive ------------------------------------------------------------------------------------------------------

def files_of(path):
    """{path inside the job (without the job folder): bytes} of a .zip or .tgz with one ODB++ job."""
    raw = Path(path).read_bytes()
    out = {}
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            out = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    elif raw[:2] == b"\x1f\x8b" or tarfile.is_tarfile(io.BytesIO(raw)):
        with tarfile.open(fileobj=io.BytesIO(raw)) as t:
            out = {m.name: t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
    else:
        raise OdbError(f"{Path(path).name}: neither a zip nor a tgz archive")
    matrix = [n for n in out if n.replace("\\", "/").endswith("matrix/matrix")]
    if len(matrix) != 1:
        raise OdbError(f"{Path(path).name}: {'no' if not matrix else 'more than one'} matrix/matrix – not one ODB++ job")
    root = matrix[0][:-len("matrix/matrix")]
    return {n[len(root):].replace("\\", "/"): data for n, data in out.items() if n.startswith(root)}


def text_of(files, name):
    """A file of the job as text – plain or gzip; None when it is not there. A .Z file is named, not read."""
    for candidate, unzip in ((name, None), (name + ".gz", gzip.decompress)):
        if candidate in files:
            data = files[candidate]
            return (unzip(data) if unzip else data).decode("utf-8", errors="replace")
    if name + ".Z" in files:
        raise OdbError(f"{name}.Z: compressed with compress(1) – not read; export without compression")
    return None


# --- matrix, units, features ------------------------------------------------------------------------------------------

def blocks(text, kind):
    """The KEY=VALUE blocks `KIND { … }` of a matrix-like file."""
    out = []
    for m in re.finditer(rf"^\s*{kind}\s*\{{(.*?)^\s*\}}", text, re.M | re.S):
        out.append({k.strip().upper(): v.strip() for k, v in re.findall(r"^\s*([A-Za-z_]+)\s*=\s*(.*?)\s*$", m.group(1),
                                                                          re.M)})
    return out


def units_of(text, default="INCH"):
    m = re.search(r"^\s*(?:UNITS\s*=\s*|U\s+)(MM|INCH)\b", text or "", re.M | re.I)
    return m.group(1).upper() if m else default


def symbol(name, units):
    """A standard symbol -> (gerber aperture (kind, a, b) in mm) or None."""
    f = 0.001 if units == "MM" else INCH / 1000     # microns or mils
    m = re.fullmatch(r"r([\d.]+)", name)
    if m:
        d = float(m.group(1)) * f
        return ("C", d, d)
    m = re.fullmatch(r"s([\d.]+)", name)
    if m:
        s = float(m.group(1)) * f
        return ("R", s, s)
    m = re.fullmatch(r"(rect|oval|di|oct)([\d.]+)x([\d.]+)(?:x[rc]?[\d.]+(?:x\d+)?)?", name)
    if m:
        a, b = float(m.group(2)) * f, float(m.group(3)) * f
        return ("O" if m.group(1) == "oval" else "R", a, b)
    m = re.fullmatch(r"donut_r([\d.]+)x([\d.]+)", name)
    if m:
        d = float(m.group(1)) * f
        return ("C", d, d)
    return None


def orient(fields):
    """(angle clockwise, mirror) of a pad's orient_def: 0–3 = 0/90/180/270, 4–7 the same mirrored, 8/9 an angle."""
    if not fields:
        return 0.0, False
    o = int(fields[0])
    if o in (8, 9):
        return float(fields[1]), o == 9
    return 90.0 * (o % 4), o >= 4


def rotated(ap, angle, x, y):
    """A pad's aperture turned by angle (clockwise): a gerber op – a flash, or a region where the angle is not a
    multiple of 90°."""
    kind, a, b = ap
    k = round(angle / 90) % 4 if abs(angle / 90 - round(angle / 90)) < 1e-6 else None
    if kind == "C" or k is not None:
        if k in (1, 3):
            a, b = b, a
        return ("flash", ((kind, a, b), x, y))
    t = math.radians(-angle)
    corners = [(-a / 2, -b / 2), (a / 2, -b / 2), (a / 2, b / 2), (-a / 2, b / 2)]
    return ("region", [[(x + u * math.cos(t) - v * math.sin(t), y + u * math.sin(t) + v * math.cos(t))
                        for u, v in corners]])


def arc_points(xs, ys, xe, ye, xc, yc, cw, step_deg=5):
    a0, a1 = math.atan2(ys - yc, xs - xc), math.atan2(ye - yc, xe - xc)
    r = math.hypot(xs - xc, ys - yc)
    if cw:
        while a1 >= a0:
            a1 -= 2 * math.pi
    else:
        while a1 <= a0:
            a1 += 2 * math.pi
    if abs(xs - xe) < 1e-9 and abs(ys - ye) < 1e-9:
        a1 = a0 + (-2 * math.pi if cw else 2 * math.pi)
    n = max(2, int(abs(a1 - a0) / math.radians(step_deg)) + 1)
    return [(xc + r * math.cos(a0 + (a1 - a0) * i / n), yc + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


DRILL = {"0": "plated", "1": "non_plated", "2": "via"}     # options of the system attribute .drill


def features(text, units_default="INCH"):
    """[(polarity, op)] of a features file in mm, and the drill holes [(x, y, d, kind)] of its pads; ops in the form
    of gerber.parse_gerber, so that both render alike."""
    units = units_of(text, units_default)
    f = INCH if units == "INCH" else 1.0
    syms, attrs, out, holes = {}, {}, [], []
    surface, contour = None, None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        body, _, attr = line.partition(";")
        tok = body.split()
        head = tok[0]
        if head.startswith("$") and len(tok) >= 2:
            syms[head[1:]] = symbol(tok[1], units)
        elif head.startswith("@") and len(tok) >= 2:
            attrs[head[1:]] = tok[1]
        elif head == "L" and len(tok) >= 7:
            ap = syms.get(tok[5])
            if ap:
                out.append((tok[6], ("draw", (("C", ap[1], ap[1]) if ap[0] == "C" else ap,
                                              [(float(tok[1]) * f, float(tok[2]) * f),
                                               (float(tok[3]) * f, float(tok[4]) * f)]))))
        elif head == "P" and len(tok) >= 5:
            ap = syms.get(tok[3])
            if ap:
                angle, _ = orient(tok[6:])
                x, y = float(tok[1]) * f, float(tok[2]) * f
                out.append((tok[4], rotated(ap, angle, x, y)))
                kind = next((DRILL.get(v) for k, v in (kv.split("=", 1) for kv in attr.split(",") if "=" in kv)
                             if attrs.get(k) == ".drill"), None)
                holes.append((x, y, ap[1], kind or "plated"))
        elif head == "A" and len(tok) >= 10:
            ap = syms.get(tok[7])
            if ap:
                pts = arc_points(*(float(v) * f for v in tok[1:7]), cw=tok[10].upper() == "Y" if len(tok) > 10 else True)
                out.append((tok[8], ("draw", (("C", ap[1], ap[1]), pts))))
        elif head == "S":
            surface = tok[1] if len(tok) > 1 else "P"
        elif head == "OB" and surface is not None:
            contour = (tok[3].upper() if len(tok) > 3 else "I", [(float(tok[1]) * f, float(tok[2]) * f)])
        elif head == "OS" and contour is not None:
            contour[1].append((float(tok[1]) * f, float(tok[2]) * f))
        elif head == "OC" and contour is not None:
            xs, ys = contour[1][-1]
            pts = arc_points(xs, ys, float(tok[1]) * f, float(tok[2]) * f, float(tok[3]) * f, float(tok[4]) * f,
                             cw=(tok[5].upper() == "Y") if len(tok) > 5 else True)
            contour[1].extend(pts[1:])
        elif head == "OE" and contour is not None:
            island, pts = contour
            pol = surface if island == "I" else ("N" if surface == "P" else "P")
            out.append((pol, ("region", [pts])))
            contour = None
        elif head == "SE":
            surface = None
    return out, holes


def outline(text, units_default="INCH"):
    """The profile's contours in mm (the islands)."""
    return [op[1][0] for pol, op in features(text, units_default)[0] if op[0] == "region" and pol == "P"]


def components(text, side, nets, units_default="INCH"):
    units = units_of(text, units_default)
    f = INCH if units == "INCH" else 1.0
    out, names = [], {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        body, _, attrs = line.partition(";")
        tok = body.split()
        if not tok:
            continue
        if m := re.match(r"@(\d+)\s+(\S+)", line):
            names[m.group(1)] = m.group(2)
        elif tok[0] == "CMP" and len(tok) >= 7:
            out.append(Component(designator=tok[6], side=side, x=float(tok[2]) * f, y=float(tok[3]) * f,
                                 rot=float(tok[4]), mirror=tok[5].upper() == "M", package=tok[1],
                                 part=tok[7] if len(tok) > 7 else ""))
            for a in filter(None, (a.strip() for a in attrs.split(","))):
                n, eq, v = a.partition("=")
                out[-1].attrs[names.get(n, n)] = v if eq else True
        elif tok[0] == "PRP" and out and len(tok) >= 3:
            out[-1].props[tok[1]] = " ".join(tok[2:]).strip("'\"")
        elif tok[0] == "TOP" and out and len(tok) >= 7:
            n = int(tok[6]) if tok[6].lstrip("-").isdigit() else -1
            name = tok[8] if len(tok) > 8 else tok[1]     # TOP pin x y rot mirror net subnet toeprint_name
            out[-1].pins.append((name, float(tok[2]) * f, float(tok[3]) * f,
                                 nets[n] if 0 <= n < len(nets) else ""))
    return out


def net_names(text):
    """The net names of eda/data, by number."""
    return [m.group(1) for m in re.finditer(r"^\s*NET\s+(\S+)", text or "", re.M)]


def read(path):
    """The job of an ODB++ archive: layers in matrix order with their features and holes, the profile, the
    components, the nets."""
    files = files_of(path)
    matrix = text_of(files, "matrix/matrix") or ""
    steps = [b.get("NAME", "").lower() for b in blocks(matrix, "STEP")]
    step = steps[0] if steps else next((n.split("/")[1] for n in files if n.startswith("steps/")), "pcb")
    base = f"steps/{step}"
    info = text_of(files, "misc/info") or ""
    default = units_of(info, "INCH")
    nets = net_names(text_of(files, f"{base}/eda/data"))
    layers = {}
    for b in sorted(blocks(matrix, "LAYER"), key=lambda b: int(b.get("ROW", 0) or 0)):
        name = b.get("NAME", "").lower()
        lay = Layer(name=name, type=b.get("TYPE", "").upper(), context=b.get("CONTEXT", "").upper(),
                    row=int(b.get("ROW", 0) or 0), polarity=b.get("POLARITY", "POSITIVE").upper())
        text = text_of(files, f"{base}/layers/{name}/features")
        if text is not None:
            lay.features, holes = features(text, default)
            if lay.type == "DRILL":
                lay.holes = holes
        layers[name] = lay
    comps = []
    for name, side in (("comp_+_top", "top"), ("comp_+_bot", "bottom")):
        text = text_of(files, f"{base}/layers/{name}/components")
        if text is not None:
            comps += components(text, side, nets, default)
    profile = outline(text_of(files, f"{base}/profile") or "", default)
    return Job(layers=layers, profile=profile, components=comps, nets=nets, units=default)


def render(raster, items):
    """[(polarity, op)] onto a bool image of raster, in order: P adds, N clears – runs of one polarity drawn at once."""
    import numpy as np
    img = np.zeros((raster.h, raster.w), dtype=bool)
    run, pol = [], None
    for p, op in [*items, (None, None)]:
        if p != pol and run:
            m = raster.render(run)
            img = img | m if pol == "P" else img & ~m
            run = []
        pol = p
        if op is not None:
            run.append(op)
    return img
