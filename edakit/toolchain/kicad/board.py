"""The PCB of a board as KiCad files – <board>.kicad_pcb with its rules in <board>.kicad_pro and <board>.kicad_dru –
written from edakit's data and read back into the files the shared checks read (handbook 16.4).

Every step owns its part of the file, as every EasyEDA step owns its primitives, and keeps the rest:

    write_parts    footprints (position from [place]; a part without a row keeps its spot, a new one is parked),
                   outline and mounting holes on Edge.Cuts, tooling holes, nets, rules     pcb parts/nets/apply/tooling
    write_copper   tracks and vias from the SES                                             route apply
    write_zones    the pours of [[pours]] (filled by kicad-cli: cli.fill_zones)             route pours, pcb pour
    write_silk     designators, the board label, texts and artwork                          silk apply

    board_json     the board as `route read` writes it from EasyEDA (<board>_board.json): mil, y up
    pcb_json       the PCB as `fab` reads it from EasyEDA (pcb.json): components with pads, tracks, texts
    geometry       the footprints as `pcb dump` measures them (<board>.geometry.json)

Frames: a point (x, y) of EasyEDA's frame (mil, y up – what route, pcb and fab compute in) lies at (x/39.37 mm,
-y/39.37 mm) in the file; the angle of a part is the same number in both (counter-clockwise as seen from the top). A
part on the bottom side has its footprint mirrored in local y and its layers swapped, as EasyEDA does (Board.transform);
pads carry their absolute angle, as KiCad writes them.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from ...config import MIL_PER_MM
from ...design import Design, natural_key
from . import library, sexp
from .library import VERSION
from .sexp import Sym, find, first, floats, uid, value

# KiCad 8's layer table (the file format edakit writes, see library.VERSION)
LAYER_TABLE = [(0, "F.Cu", "signal"), (31, "B.Cu", "signal"), (32, "B.Adhes", "user", "B.Adhesive"),
               (33, "F.Adhes", "user", "F.Adhesive"), (34, "B.Paste", "user"), (35, "F.Paste", "user"),
               (36, "B.SilkS", "user", "B.Silkscreen"), (37, "F.SilkS", "user", "F.Silkscreen"),
               (38, "B.Mask", "user"), (39, "F.Mask", "user"), (40, "Dwgs.User", "user", "User.Drawings"),
               (41, "Cmts.User", "user", "User.Comments"), (42, "Eco1.User", "user", "User.Eco1"),
               (43, "Eco2.User", "user", "User.Eco2"), (44, "Edge.Cuts", "user"), (45, "Margin", "user"),
               (46, "B.CrtYd", "user", "B.Courtyard"), (47, "F.CrtYd", "user", "F.Courtyard"),
               (48, "B.Fab", "user"), (49, "F.Fab", "user")]
COPPER = {"TOP": "F.Cu", "BOTTOM": "B.Cu"}
LAYER_NAME = {"F.Cu": "TOP", "B.Cu": "BOTTOM"}
EDA_LAYER = {"F.Cu": 1, "B.Cu": 2}          # EasyEDA's layer ids, as board.json and pcb.json carry them
MULTI = 12                                 # EasyEDA: a through-hole pad
EDGE_WIDTH_MM = 0.05
TOOLING = "tooling"                        # property "edakit" of a tooling hole's footprint – no part of the graph
PARK_STEP_MM = 6.0                         # new parts without a row: side by side from the board file's park
# DRC checks whose subject edakit checks itself: the footprints against the parts database (P-10, L-10), overlaps in
# the plan (pcb plan, L-7), the silkscreen on the Gerber files (L-17) – off, so that L-3 reads what only KiCad sees
RULE_SEVERITIES = {"lib_footprint_issues": "ignore", "lib_footprint_mismatch": "ignore",
                   "courtyards_overlap": "ignore", "missing_courtyard": "ignore", "malformed_courtyard": "ignore",
                   "silk_overlap": "ignore", "silk_over_copper": "ignore", "silk_edge_clearance": "ignore",
                   "text_height": "ignore", "text_thickness": "ignore"}
ERC_SEVERITIES = {"lib_symbol_issues": "ignore", "lib_symbol_mismatch": "ignore", "footprint_link_issues": "ignore",
                  "single_global_label": "ignore"}          # a net of the drawing may have one label only


class BoardError(Exception):
    pass


def mm(mil):
    return mil / MIL_PER_MM


def mil(v):
    return v * MIL_PER_MM


def to_kicad(x_mil, y_mil):
    """EasyEDA's frame (mil, y up) -> the file (mm, y down)."""
    return mm(x_mil), -mm(y_mil)


def from_kicad(x, y):
    return mil(x), -mil(y)


def turn(x, y, angle):
    """A local point (mm, y down) of a footprint turned by angle as KiCad turns it: counter-clockwise on the screen."""
    a = math.radians(angle)
    return x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)


def paths(cfg, board):
    d = cfg.kicad_dir(board)
    return {"dir": d, "pcb": d / f"{board.name}.kicad_pcb", "pro": d / f"{board.name}.kicad_pro",
            "dru": d / f"{board.name}.kicad_dru", "sch": d / f"{board.name}.kicad_sch"}


# --- the file ---------------------------------------------------------------------------------------------------------

class Pcb:
    """A .kicad_pcb as parts: nets (name -> number), footprints, drawings (gr_*), tracks (segment, via, arc), zones –
    and whatever else it holds, written back as it was."""

    def __init__(self, root=None):
        self.root = root or ["kicad_pcb"]
        self.nets = {"": 0}
        self.footprints, self.drawings, self.tracks, self.zones, self.other = [], [], [], [], []
        for item in self.root[1:]:
            if not isinstance(item, list):
                continue
            head = item[0]
            if head == "net" and len(item) > 2 and str(item[1]).isdigit():
                self.nets[str(item[2])] = int(item[1])
            elif head == "net":                # a net by its name only: numbered by load()'s renumber
                self.nets.setdefault(str(item[1]) if len(item) > 1 else "", -1)
            elif head == "footprint":
                self.footprints.append(item)
            elif head.startswith("gr_"):
                self.drawings.append(item)
            elif head in ("segment", "via", "arc"):
                self.tracks.append(item)
            elif head == "zone":
                self.zones.append(item)
            elif head not in ("version", "generator", "generator_version", "general", "paper", "title_block",
                              "layers", "setup"):
                self.other.append(item)

    @classmethod
    def load(cls, path):
        """The file, its nets numbered as edakit writes them – also after KiCad saved it in its own format."""
        path = Path(path)
        if not path.exists():
            return None
        pcb = cls(sexp.loads(path.read_text(encoding="utf-8")))
        pcb.renumber(pcb.used())
        return pcb

    def net_name(self, number):
        """The name of a net number – or the name itself, where a file names its nets in items."""
        if not str(number).lstrip("-").isdigit():
            return str(number)
        return next((n for n, k in self.nets.items() if k == int(number)), "")

    def footprint(self, ref):
        return next((f for f in self.footprints if reference(f) == ref), None)

    def used(self):
        """Every net name the pads, tracks and zones name – by number through the table, or by name, as KiCad 10
        writes them when it saves the file (kicad-cli's zone fill)."""
        names = set(self.nets)
        for item in self.tracks + self.zones + [pad for f in self.footprints for pad in find(f, "pad")]:
            for c in item:
                if isinstance(c, list) and c and c[0] == "net" and len(c) > 1:
                    names.add(str(c[2]) if len(c) > 2 else self.net_name(c[1]))
                elif isinstance(c, list) and c and c[0] == "net_name" and len(c) > 1:
                    names.add(str(c[1]))
        return names

    def renumber(self, names):
        """New net numbers for these names (sorted, 0 = no net); tracks, zones and pads keep their nets by name and
        name them as KiCad 8 does – (net 3) in tracks and zones, (net 3 "GND") at pads."""
        old = {k: n for n, k in self.nets.items()}

        def name_of(c):
            return str(c[2]) if len(c) > 2 else old.get(int(c[1]), "") if str(c[1]).isdigit() else str(c[1])
        self.nets = {"": 0} | {n: k for k, n in enumerate(sorted(set(names) - {""}, key=natural_key), 1)}
        for item in self.tracks:
            for c in item:
                if isinstance(c, list) and c and c[0] == "net" and len(c) > 1:
                    c[1:] = [self.nets.get(name_of(c), 0)]
        for zone in self.zones:             # a zone names its net by number, by name, or both (net_name)
            net = next((c for c in zone if isinstance(c, list) and c and c[0] == "net" and len(c) > 1), None)
            label = next((c for c in zone if isinstance(c, list) and c and c[0] == "net_name"), None)
            name = str(label[1]) if label and len(label) > 1 and str(label[1]) else name_of(net) if net else ""
            if net is None:
                net = ["net", 0]
                zone.insert(1, net)
            net[1:] = [self.nets.get(name, 0)]
            if label is None:
                zone.insert(2, ["net_name", name])
            else:
                label[1:] = [name]
        for pad in (pad for f in self.footprints for pad in find(f, "pad")):
            for c in pad:
                if isinstance(c, list) and c and c[0] == "net" and len(c) > 1:
                    name = name_of(c)
                    c[1:] = [self.nets.get(name, 0), name]

    def text(self, cfg, board):
        title = ["title_block", ["title", board.title], ["company", cfg.company]]
        if board.revision:
            title.insert(2, ["rev", board.revision])
        head = [["version", VERSION], ["generator", "edakit"], ["generator_version", "8.0"],
                ["general", ["thickness", board.thickness_mm], ["legacy_teardrops", False]], ["paper", "A4"], title,
                ["layers", *([n, name, Sym(kind), *rest] for n, name, kind, *rest in LAYER_TABLE)],
                ["setup", ["pad_to_mask_clearance", 0], ["allow_soldermask_bridges_in_footprints", False]]]
        nets = [["net", k, n] for n, k in sorted(self.nets.items(), key=lambda kv: kv[1])]
        body = head + nets + self.footprints + self.drawings + self.tracks + self.zones + self.other
        return sexp.dumps(["kicad_pcb", *body]) + "\n"

    def save(self, cfg, board):
        p = paths(cfg, board)["pcb"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.text(cfg, board), encoding="utf-8")
        return p


def reference(fp):
    for c in find(fp, "property"):
        if len(c) > 2 and c[1] == "Reference":
            return str(c[2])
    t = next((c for c in find(fp, "fp_text") if len(c) > 2 and c[1] == "reference"), None)
    return str(t[2]) if t else ""


def prop(fp, name):
    return next((str(c[2]) for c in find(fp, "property") if len(c) > 2 and c[1] == name), None)


def load(cfg, board):
    pcb = Pcb.load(paths(cfg, board)["pcb"])
    if pcb is None:
        raise BoardError(f"no KiCad PCB of board {board.name} yet ({cfg.relative(paths(cfg, board)['pcb'])}) – "
                         "edakit pcb parts --write (or pcb apply) writes it")
    return pcb


# --- writing the parts ------------------------------------------------------------------------------------------------

def root_uid(cfg, board):
    """The uuid of the schematic's root sheet – the project file names it too."""
    return uid(cfg.project, board.name, "sheet")


def symbol_uid(cfg, board, ref):
    """The uuid of a part's symbol: the path of its footprint, so that schematic and PCB belong together."""
    return uid(cfg.project, board.name, "symbol", ref)


def part_value(design, ref, fp):
    """The value a part shows – the same in schematic and PCB (KiCad's schematic parity compares them)."""
    comp, entry = design.comps.get(ref, {}), design.part(ref) or {}
    return str(comp.get("value") or entry.get("mpn") or fp.name)


def net_names(design, board):
    return sorted(design.board_nets(board.name), key=natural_key)


def font(size, width, mirror=False):
    return library.font(size, width, mirror)


def hidden_prop(name, text, layer, key):
    return ["property", name, text, ["at", 0, 0, 0], ["layer", layer], ["hide", True], ["uuid", uid(*key, name)],
            *library.font(1.0, 0.15)]


def placed(cfg, board, design, fp, ref, at, nets, symbol=None, locked=False):
    """The board's (footprint …) of a part: fp turned and, on the bottom, mirrored; at: (x mm, y mm, angle, side)."""
    x, y, angle, side = at
    mirror = side == "bottom"
    key = (board.name, "footprint", ref)
    silk, fab = ("B.SilkS", "B.Fab") if mirror else ("F.SilkS", "F.Fab")
    comp = design.comps.get(ref, {})
    ref_y = fp.bbox[1] - library.REF_SIZE_MM
    item = ["footprint", f"{library.LIB}:{fp.name}", ["layer", "B.Cu" if mirror else "F.Cu"], ["uuid", uid(*key)],
            ["at", x, y, angle]]
    if locked:
        item.insert(2, ["locked", True])
    item += [["property", "Reference", ref, ["at", 0, -ref_y if mirror else ref_y, angle], ["layer", silk],
              ["uuid", uid(*key, "Reference")], *library.font(library.REF_SIZE_MM, library.SILK_WIDTH_MM, mirror)],
             ["property", "Value", part_value(design, ref, fp), ["at", 0, 0, angle],
              ["layer", fab], ["hide", True], ["uuid", uid(*key, "Value")], *library.font(1.0, 0.15, mirror)],
             hidden_prop("Footprint", f"{library.LIB}:{fp.name}", fab, key),
             hidden_prop("Package", fp.package, fab, key)]
    if comp.get("lcsc"):
        item.append(hidden_prop("LCSC", comp["lcsc"], fab, key))
    if symbol:
        item += [["path", f"/{symbol}"], ["sheetname", "Root"], ["sheetfile", f"{board.name}.kicad_sch"]]
    attr = ["attr", Sym("through_hole" if fp.tht else "smd")]
    if comp.get("bom") is False:
        attr += [Sym("exclude_from_pos_files"), Sym("exclude_from_bom")]
    item.append(attr)
    for k, g in enumerate(fp.graphics):
        item += library.graphic_items(g, k, mirror, angle, key)
    for i, pad in enumerate(fp.pads):
        net = design.pin_net.get(f"{ref}.{pad.num}", "")
        item.append(library.pad_item(pad, angle, mirror, (nets[net], net) if net else None, (*key, i)))
    return item


def tooling_footprint(board, k, x, y):
    key = (board.name, "tooling", k)
    return ["footprint", f"{library.LIB}:Tooling", ["locked", True], ["layer", "F.Cu"], ["uuid", uid(*key)],
            ["at", x, y, 0],
            ["property", "Reference", f"TH{k}", ["at", 0, 0, 0], ["layer", "F.SilkS"], ["hide", True],
             ["uuid", uid(*key, "Reference")], *library.font(1.0, 0.15)],
            hidden_prop("Value", "tooling hole", "F.Fab", key), hidden_prop("edakit", TOOLING, "F.Fab", key),
            ["attr", Sym("board_only"), Sym("exclude_from_pos_files"), Sym("exclude_from_bom")],
            ["pad", "", Sym("np_thru_hole"), Sym("circle"), ["at", 0, 0], ["size", board.tooling_d, board.tooling_d],
             ["drill", board.tooling_d], ["layers", "*.Cu", "*.Mask"], ["solder_mask_margin", board.tooling_mask],
             ["uuid", uid(*key, "pad")]]]


def is_tooling(fp):
    return prop(fp, "edakit") == TOOLING


def edge_items(board):
    """The outline as lines and the mounting holes as circles on Edge.Cuts – EasyEDA draws both on its outline layer,
    so the Gerber outline (F-5) and route's board area are the same in both tool chains."""
    from ...pcb import outline_polygon
    pts = [to_kicad(*(mil(v) for v in board.eda_point(x, y))) for x, y in outline_polygon(board).exterior.coords[:-1]]
    out = [["gr_line", ["start", *a], ["end", *b], ["stroke", ["width", EDGE_WIDTH_MM], ["type", Sym("solid")]],
            ["layer", "Edge.Cuts"], ["uuid", uid(board.name, "edge", k)]]
           for k, (a, b) in enumerate(zip(pts, pts[1:] + pts[:1]))]
    for k, h in enumerate(board.holes):
        cx, cy = board.eda_point(h["x"], h["y"])
        out.append(["gr_circle", ["center", cx, -cy], ["end", cx + h["d"] / 2, -cy],
                    ["stroke", ["width", EDGE_WIDTH_MM], ["type", Sym("solid")]], ["fill", Sym("none")],
                    ["layer", "Edge.Cuts"], ["uuid", uid(board.name, "hole", k)]])
    return out


def where(board, row):
    """A row of [place] -> (x mm, y mm, angle, side) in the file."""
    x, y, rot, layer = board.to_eda(row.x, row.y, row.rot, row.side)
    return x, -y, rot % 360, "bottom" if layer == 2 else "top"


def write_parts(cfg, board, design=None, fps=None, symbols=None):
    """The parts of the board into the KiCad PCB: footprints with their nets, outline, holes, tooling holes; the
    library and the project's rules alongside. Positions: the row of [place]; a part without one keeps where it lies
    in the file (moved in KiCad, or parked before), a new one is parked beside the board (board file `park`, as
    `pcb parts --write` drops new parts in EasyEDA). Tracks, zones and silkscreen stay. -> (path, [parked parts])."""
    design = design or Design.from_config(cfg)
    refs = sorted(design.board_comps(board.name), key=natural_key)
    fps = fps or library.footprints(cfg, design, refs)
    library.write(cfg, board, fps)
    symbols = symbols or {ref: symbol_uid(cfg, board, ref) for ref in refs}
    p = paths(cfg, board)
    old = Pcb.load(p["pcb"])
    pcb = old or Pcb()
    pcb.renumber(net_names(design, board))
    parked, out = [], []
    for k, ref in enumerate(refs):
        row = board.place.get(ref)
        if row:
            at, locked = where(board, row), not row.auto
        elif old and (f := old.footprint(ref)) is not None:
            a = floats(f, "at")
            at, locked = (a[0], a[1], a[2] if len(a) > 2 else 0, "bottom" if value(f, "layer") == "B.Cu" else "top"), \
                False
        else:
            px, py = board.park
            at, locked = (px + PARK_STEP_MM * len(parked), -py, 0, "top"), False
            parked.append(ref)
        out.append(placed(cfg, board, design, fps[ref], ref, at, pcb.nets, symbols.get(ref), locked))
    out += [tooling_footprint(board, k, *to_kicad(*(mil(v) for v in board.eda_point(x, y))))
            for k, (x, y) in enumerate(board.tooling, 1)]
    pcb.footprints = out
    pcb.drawings = [d for d in pcb.drawings if value(d, "layer") != "Edge.Cuts"] + edge_items(board)
    path = pcb.save(cfg, board)
    write_project(cfg, board, design)
    return path, parked


def write_project(cfg, board, design):
    """<board>.kicad_pro with the rules of [routing] (drc_rules.wanted: clearance, edge, tracks, via, net classes)
    and <board>.kicad_dru with what the project file has no field for."""
    from ...drc_rules import wanted
    want = wanted(board)
    p = paths(cfg, board)
    classes = [{"name": "Default", "clearance": want["clearance"], "track_width": want["track"][""],
                "via_diameter": want["via"][0], "via_drill": want["via"][1], "microvia_diameter": 0.3,
                "microvia_drill": 0.1, "diff_pair_width": want["track"][""], "diff_pair_gap": want["clearance"],
                "diff_pair_via_gap": want["clearance"], "wire_width": 6, "bus_width": 12, "line_style": 0,
                "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
                "priority": 2147483647}]
    patterns = []
    for k, (name, nets) in enumerate(sorted(want["classes"].items())):
        classes.append({**classes[0], "name": name, "track_width": want["track"].get(name, want["track"][""]),
                        "priority": k})
        patterns += [{"netclass": name, "pattern": net} for net in nets]
    project = {
        "board": {"design_settings": {
            "defaults": {"board_outline_line_width": EDGE_WIDTH_MM, "copper_line_width": want["track"][""],
                         "silk_line_width": library.SILK_WIDTH_MM, "silk_text_size_h": 1.0,
                         "silk_text_size_v": 1.0, "silk_text_thickness": library.SILK_WIDTH_MM},
            "rule_severities": RULE_SEVERITIES,
            "rules": {"min_clearance": want["clearance"], "min_track_width": min(want["track"].values()),
                      "min_via_diameter": want["via"][0], "min_through_hole_diameter": min(want["via"][1], 0.3),
                      "min_via_annular_width": 0.05, "min_copper_edge_clearance": want["edge"],
                      "min_hole_clearance": 0.25, "min_hole_to_hole": 0.2, "min_silk_clearance": 0,
                      "min_text_height": 0.6, "min_text_thickness": 0.08, "allow_blind_buried_vias": False,
                      "allow_microvias": False},
            "track_widths": [0.0], "via_dimensions": [{"diameter": 0.0, "drill": 0.0}]}},
        "erc": {"rule_severities": ERC_SEVERITIES},
        "meta": {"filename": p["pro"].name, "version": 1},
        "net_settings": {"classes": classes, "meta": {"version": 3}, "netclass_patterns": patterns},
        "sheets": [[root_uid(cfg, board), "Root"]],
        "text_variables": {},
    }
    p["pro"].write_text(json.dumps(project, indent=2) + "\n", encoding="utf-8")
    p["dru"].write_text("(version 1)\n# generated by edakit from the board file – the rules of [routing] are in "
                        f"{p['pro'].name}; L-18's keep-outs are Freerouting's and the gate's (handbook 16.4)\n",
                        encoding="utf-8")


# --- reading -------------------------------------------------------------------------------------------------------

def footprint_at(fp):
    a = floats(fp, "at")
    return a[0], a[1], (a[2] if len(a) > 2 else 0.0) % 360, value(fp, "layer") == "B.Cu"


def pad_abs(fp, pad):
    """(x mm, y mm) of a pad in the file's frame."""
    x0, y0, angle, _ = footprint_at(fp)
    a = floats(pad, "at")
    dx, dy = turn(a[0], a[1], angle)
    return x0 + dx, y0 + dy


def pad_layer(pad):
    layers = [str(v) for v in first(pad, "layers")[1:]]
    if any(v.startswith("*.Cu") for v in layers) or {"F.Cu", "B.Cu"} <= set(layers):
        return MULTI
    return EDA_LAYER["B.Cu"] if "B.Cu" in layers else EDA_LAYER["F.Cu"]


def pad_shape(pad):
    """[shape, w mil, h mil] as EasyEDA's API gives a pad's shape (route.pad_shapes reads it)."""
    shape, size = str(pad[3]), floats(pad, "size")
    w, h = mil(size[0]), mil(size[1] if len(size) > 1 else size[0])
    if shape == "custom":
        pts = [floats(xy, "xy") for g in find(first(pad, "primitives") or [], "gr_poly")
               for xy in find(first(g, "pts"), "xy")]
        if pts:
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            return ["POLYGON", round(mil(max(xs) - min(xs)), 4), round(mil(max(ys) - min(ys)), 4)]
    kind = {"circle": "ELLIPSE", "oval": "OVAL"}.get(shape, "RECT")
    return [kind, round(w, 4), round(h, 4)]


def pad_hole(pad):
    """["ROUND", d] or ["SLOT", w, l] in mil, as EasyEDA's API gives a hole; None for an SMD pad."""
    drill = first(pad, "drill")
    if not drill:
        return None
    nums = [float(v) for v in drill[1:] if not isinstance(v, list) and v != "oval"]
    if len(nums) >= 2 and abs(nums[0] - nums[1]) > 1e-6:
        return ["SLOT", round(mil(min(nums)), 4), round(mil(max(nums)), 4)]
    return ["ROUND", round(mil(nums[0]), 4)]


def pad_net(pcb, pad):
    n = first(pad, "net")
    return str(n[2]) if n and len(n) > 2 else (pcb.net_name(n[1]) if n else "")


def parts(pcb):
    """The footprints of the graph's parts (tooling holes left out) as (ref, footprint)."""
    return [(reference(f), f) for f in pcb.footprints if reference(f) and not is_tooling(f)]


def board_json(cfg, board):
    """What `route read` writes from EasyEDA, read from the KiCad PCB: components, pads (mil, y up, absolute angle),
    outlines (the board and the mounting holes), and how much copper is in the PCB."""
    pcb = load(cfg, board)
    comps, pads = [], []
    for ref, fp in parts(pcb):
        x, y, angle, bottom = footprint_at(fp)
        cx, cy = from_kicad(x, y)
        comps.append({"ref": ref, "x": round(cx, 4), "y": round(cy, 4), "rot": angle, "layer": 2 if bottom else 1})
        for k, pad in enumerate(find(fp, "pad")):
            px, py = from_kicad(*pad_abs(fp, pad))
            a = floats(pad, "at")
            pads.append({"id": f"{ref}#{k}", "ref": ref, "num": str(pad[1]), "net": pad_net(pcb, pad),
                         "x": round(px, 4), "y": round(py, 4), "rot": round((a[2] if len(a) > 2 else 0) % 360, 4),
                         "layer": pad_layer(pad), "shape": pad_shape(pad), "hole": pad_hole(pad), "hole_off": [0, 0]})
    for fp in pcb.footprints:          # tooling holes: free pads without a part, as EasyEDA has them
        if is_tooling(fp):
            for pad in find(fp, "pad"):
                px, py = from_kicad(*pad_abs(fp, pad))
                pads.append({"id": f"{reference(fp)}", "ref": None, "num": "", "net": "", "x": round(px, 4),
                             "y": round(py, 4), "rot": 0, "layer": MULTI, "shape": pad_shape(pad),
                             "hole": pad_hole(pad), "hole_off": [0, 0]})
    return {"pcb": board.name, "components": comps, "pads": pads, "outlines": outlines(pcb),
            "existing": {"lines": sum(1 for t in pcb.tracks if t[0] == "segment"),
                         "vias": sum(1 for t in pcb.tracks if t[0] == "via")}}


def outlines(pcb):
    """Closed shapes on Edge.Cuts as point lists (mil, y up): the lines chained into loops, circles as 48-gons."""
    out, segs = [], []
    for d in pcb.drawings:
        if value(d, "layer") != "Edge.Cuts":
            continue
        if d[0] == "gr_circle":
            (cx, cy), (ex, ey) = floats(d, "center"), floats(d, "end")
            r = math.dist((cx, cy), (ex, ey))
            out.append([[round(v, 4) for v in from_kicad(cx + r * math.cos(2 * math.pi * k / 48),
                                                         cy + r * math.sin(2 * math.pi * k / 48))] for k in range(48)])
        elif d[0] == "gr_line":
            segs.append((tuple(floats(d, "start")), tuple(floats(d, "end"))))
        elif d[0] == "gr_poly":
            out.append([[round(v, 4) for v in from_kicad(*floats(xy, "xy"))] for xy in find(first(d, "pts"), "xy")])
    while segs:                     # chain the lines: each loop starts at a free segment
        a, b = segs.pop(0)
        loop = [a, b]
        while True:
            nxt = next((s for s in segs if math.dist(s[0], loop[-1]) < 1e-4 or math.dist(s[1], loop[-1]) < 1e-4),
                       None)
            if nxt is None:
                break
            segs.remove(nxt)
            loop.append(nxt[1] if math.dist(nxt[0], loop[-1]) < 1e-4 else nxt[0])
        if math.dist(loop[0], loop[-1]) < 1e-4:
            loop.pop()
        out.insert(0, [[round(v, 4) for v in from_kicad(*q)] for q in loop])
    return sorted(out, key=lambda o: -abs(area(o)))


def area(pts):
    return sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts))) / 2


def pcb_json(cfg, board):
    """What `fab` reads from EasyEDA into pcb.json, read from the KiCad PCB: components (designator, place in mil,
    rotation, layer, footprint, pads), tracks of the copper layers, texts, and whether each designator is printed."""
    pcb = load(cfg, board)
    comps, shown = [], {}
    for ref, fp in parts(pcb):
        x, y, angle, bottom = footprint_at(fp)
        cx, cy = from_kicad(x, y)
        pads = []
        for pad in find(fp, "pad"):
            px, py = from_kicad(*pad_abs(fp, pad))
            pads.append({"PadNumber": str(pad[1]), "X": round(px, 4), "Y": round(py, 4), "Net": pad_net(pcb, pad),
                         "Layer": pad_layer(pad), "tht": first(pad, "drill") is not None})
        name = prop(fp, "Package") or str(fp[1]).split(":", 1)[-1]   # the parts entry's name of it (L-4)
        comps.append({"designator": ref, "x": round(cx, 4), "y": round(cy, 4), "rotation": angle,
                      "layer": 2 if bottom else 1, "footprintName": name, "deviceName": prop(fp, "Value") or "",
                      "primitiveId": str(value(fp, "uuid") or ref), "pads": pads})
        refprop = next((c for c in find(fp, "property") if c[1] == "Reference"), None)
        shown[ref] = refprop is not None and not any(c[0] == "hide" and c[1:] == ["yes"] or c == ["hide", True]
                                                     for c in refprop if isinstance(c, list))
    lines = []
    for t in pcb.tracks:
        if t[0] == "segment" and value(t, "layer") in EDA_LAYER:
            (sx, sy), (ex, ey) = from_kicad(*floats(t, "start")), from_kicad(*floats(t, "end"))
            lines.append({"Net": pcb.net_name(value(t, "net", 0)), "Layer": EDA_LAYER[value(t, "layer")],
                          "LineWidth": round(mil(float(value(t, "width"))), 4), "StartX": round(sx, 4),
                          "StartY": round(sy, 4), "EndX": round(ex, 4), "EndY": round(ey, 4)})
    strings = []
    for d in pcb.drawings:
        if d[0] == "gr_text" and value(d, "layer") in ("F.SilkS", "B.SilkS"):
            tx, ty = from_kicad(*floats(d, "at")[:2])
            strings.append({"Text": str(d[1]), "X": round(tx, 4), "Y": round(ty, 4),
                            "Layer": 3 if value(d, "layer") == "F.SilkS" else 4})
    return {"components": comps, "lines": lines, "strings": strings, "designators": shown}


def vias(cfg, board, pcb=None):
    """[(x mil, y mil, diameter mil, net)] of the PCB's vias."""
    pcb = pcb or load(cfg, board)
    out = []
    for t in pcb.tracks:
        if t[0] == "via":
            x, y = from_kicad(*floats(t, "at"))
            out.append((x, y, mil(float(value(t, "size"))), pcb.net_name(value(t, "net", 0))))
    return out


def geometry(cfg, board, refs=None):
    """The footprints of the PCB as `pcb dump` measures them in EasyEDA: relative to the origin at 0° on TOP (mil, y
    up), bbox, every pad with net and hole – with shape, size, turn and layer for the parts whose entry has footprint
    data (P-10). Unlike EasyEDA, nothing has to be turned to be measured."""
    from ...footprint import has_data, users
    design = Design.from_config(cfg)
    own = {des for key, e in design.parts.items() if "footprint_data" in e for des in users(design, key)} \
        if has_data(design.parts) else set()
    pcb = load(cfg, board)
    out = {}
    for ref, fp in parts(pcb):
        if refs and ref not in refs:
            continue
        _, _, angle, bottom = footprint_at(fp)
        pads, nums = [], []
        for pad in find(fp, "pad"):
            a = floats(pad, "at")
            lx, ly = a[0], -a[1] if bottom else a[1]
            rot = (a[2] if len(a) > 2 else 0) - angle
            rot = (-rot if bottom else rot) % 360
            hole = pad_hole(pad)
            q = {"x": round(mil(lx), 2), "y": round(-mil(ly), 2), "net": pad_net(pcb, pad), "tht": hole is not None}
            if hole:
                w = hole[1] / MIL_PER_MM
                q |= {"hole": [round(w, 3), round(max(w, (hole[2] if len(hole) > 2 else hole[1]) / MIL_PER_MM), 3)],
                      "plated": pad[2] == "thru_hole"}
            if ref in own:
                kind, w, h = pad_shape(pad)
                q |= {"shape": kind, "w": round(w, 2), "h": round(h, 2), "rot": round(rot, 2),
                      "layer": {MULTI: "MULTI", 1: "TOP", 2: "BOTTOM"}[pad_layer(pad)] if not bottom else
                      {MULTI: "MULTI", 1: "BOTTOM", 2: "TOP"}[pad_layer(pad)]}
            pads.append((str(pad[1]), q))
            nums.append(str(pad[1]))
        g = {"primitiveId": str(value(fp, "uuid") or ref),
             "footprint": prop(fp, "Package") or str(fp[1]).split(":", 1)[-1],
             "device": prop(fp, "Value") or "", "bbox": local_bbox(fp, bottom),
             "pads": {}}
        for n, q in pads:
            g["pads"].setdefault(n, q)
        if dup := sorted({n for n in nums if nums.count(n) > 1}, key=natural_key):
            g["pads_same_number"] = {n: [{k: v for k, v in q.items() if k != "net"} for m, q in pads if m == n]
                                     for n in dup}
        out[ref] = g
    return out


def local_bbox(fp, bottom):
    """[x0, y0, x1, y1] mil, y up, relative to the origin at 0° on TOP: the footprint's fabrication box and pads."""
    xs, ys = [], []
    for d in fp:
        if isinstance(d, list) and d and d[0] in ("fp_line", "fp_poly") and str(value(d, "layer", "")).endswith(".Fab"):
            for key in ("start", "end"):
                if first(d, key):
                    x, y = floats(d, key)
                    xs.append(x)
                    ys.append(-y if bottom else y)
    for pad in find(fp, "pad"):
        a, s = floats(pad, "at"), floats(pad, "size")
        r = max(s) / 2 if s else 0
        y = -a[1] if bottom else a[1]
        xs += [a[0] - r, a[0] + r]
        ys += [y - r, y + r]
    if not xs:
        return [0, 0, 0, 0]
    return [round(mil(min(xs)), 2), round(-mil(max(ys)), 2), round(mil(max(xs)), 2), round(-mil(min(ys)), 2)]


# --- copper -----------------------------------------------------------------------------------------------------------

def write_copper(cfg, board, rules, routes, data):
    """Tracks and vias of the SES (route.read_ses, mil) into the PCB – everything in the copper is generated: the old
    tracks and vias go. The track pieces are the ones route.segments prepares for EasyEDA (snapped, split at T
    junctions, straight runs merged), so both tool chains get the same copper. -> (tracks, vias)."""
    from ...route import segments
    pcb = load(cfg, board)
    names = set(pcb.nets)
    for net in routes:
        if net not in names:
            raise BoardError(f"{net}: a net of the routing the PCB does not have – edakit pcb parts --write first")
    tracks = []
    for net, segs in sorted(segments(rules, routes, data).items()):
        for k, (layer, w, a, b) in enumerate(segs):
            tracks.append(["segment", ["start", *to_kicad(*a)], ["end", *to_kicad(*b)], ["width", mm(w)],
                           ["layer", COPPER[layer]], ["net", pcb.nets[net]],
                           ["uuid", uid(board.name, "segment", net, k, *a, *b)]])
    _, d, drill = rules.via
    for net in sorted(routes):
        for k, (x, y) in enumerate(routes[net]["vias"]):
            tracks.append(["via", ["at", *to_kicad(x, y)], ["size", mm(d)], ["drill", mm(drill)],
                           ["layers", "F.Cu", "B.Cu"], ["net", pcb.nets[net]],
                           ["uuid", uid(board.name, "via", net, k)]])
    pcb.tracks = tracks
    pcb.save(cfg, board)
    return sum(1 for t in tracks if t[0] == "segment"), sum(1 for t in tracks if t[0] == "via")


def write_zones(cfg, board, regions=None):
    """The pours of [[pours]] as zones along the pour outline (pcb.pour_outline) – or, with pour_regions, one zone
    per outline of route.region_outlines ({(net, layer): [outline in EasyEDA mm]}). Unfilled: cli.fill_zones fills
    them. Old zones go. -> number of zones."""
    from ...config import POUR_CLEARANCE_MM
    from ...pcb import pour_outline
    pcb = load(cfg, board)
    pts = [board.eda_point(*q) for q in pour_outline(board)]
    zones = []
    for spec in board.pours:
        if spec["net"] not in pcb.nets:
            print(f"  pour {spec['net']}: no such net on board {board.name} – not poured")
            continue
        for layer in spec.get("layers", ["TOP", "BOTTOM"]):
            for k, shape in enumerate((regions or {}).get((spec["net"], layer), [pts])):
                zones.append(["zone", ["net", pcb.nets[spec["net"]]], ["net_name", spec["net"]],
                              ["layer", COPPER[layer]], ["uuid", uid(board.name, "zone", spec["net"], layer, k)],
                              ["hatch", Sym("edge"), 0.5], ["priority", spec.get("priority", 1)],
                              ["connect_pads", ["clearance", spec.get("clearance_mm", POUR_CLEARANCE_MM)]],
                              ["min_thickness", spec.get("min_width_mm", 0.25)], ["filled_areas_thickness", False],
                              ["fill", True, ["thermal_gap", 0.5], ["thermal_bridge_width", 0.5],
                               ["island_removal_mode", 0]],
                              ["polygon", ["pts", *(["xy", x, -y] for x, y in shape)]]])
    pcb.zones = zones
    pcb.save(cfg, board)
    return len(zones)


# --- silkscreen ------------------------------------------------------------------------------------------------------

SILK = {"top": "F.SilkS", "bottom": "B.SilkS"}


def write_silk(cfg, board, designators, texts, fills, hide_sides):
    """The silkscreen edakit prints: designators {ref: (x mm, y mm, rot, side, height) in EasyEDA's frame, or None to
    hide}, free texts [(text, x, y, rot, height, side)], filled shapes [(side, [rings])] – the old free texts and
    fills go, every designator on a side of hide_sides is hidden unless it is placed."""
    pcb = load(cfg, board)
    for ref, fp in parts(pcb):
        _, _, angle, bottom = footprint_at(fp)
        side = "bottom" if bottom else "top"
        refprop = next(c for c in find(fp, "property") if c[1] == "Reference")
        spot = designators.get(ref)
        refprop[:] = [c for c in refprop if not (isinstance(c, list) and c and c[0] == "hide")]
        if spot is None:
            if side in hide_sides:
                refprop.insert(4, ["hide", True])
            continue
        x, y, rot, on, h = spot
        fx, fy, _, _ = footprint_at(fp)
        dx, dy = x - fx, -y - fy                              # the property's place is local to the footprint
        a = math.radians(angle)
        lx, ly = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
        for c in refprop:
            if isinstance(c, list) and c and c[0] == "at":
                c[1:] = [lx, ly, rot % 360]
            if isinstance(c, list) and c and c[0] == "effects":
                c[1:] = library.font(h, library.SILK_WIDTH_MM, bottom)[0][1:]
    pcb.drawings = [d for d in pcb.drawings if value(d, "layer") not in SILK.values()]
    for k, (text, x, y, rot, h, side) in enumerate(texts):
        pcb.drawings.append(["gr_text", text, ["at", x, -y, rot % 360], ["layer", SILK[side]],
                             ["uuid", uid(board.name, "text", k, text)],
                             *library.font(h, library.SILK_WIDTH_MM, side == "bottom")])
    for k, (side, rings) in enumerate(fills):
        for i, ring in enumerate(rings):
            pcb.drawings.append(["gr_poly", ["pts", *(["xy", x, -y] for x, y in ring)],
                                 ["stroke", ["width", 0], ["type", Sym("solid")]], ["fill", Sym("solid")],
                                 ["layer", SILK[side]], ["uuid", uid(board.name, "fill", k, i)]])
    pcb.save(cfg, board)


def rules_differences(cfg, board):
    """Where the rules of <board>.kicad_pro differ from what [routing] of the board file asks (drc_rules.wanted) – the
    file is written from it, so only a hand in KiCad or an older run makes a difference. L-3, drc_rules = "check"."""
    from ...drc_rules import wanted
    want = wanted(board)
    f = paths(cfg, board)["pro"]
    if not f.exists():
        return [f"{f.name} missing (edakit pcb apply writes it)"]
    pro = json.loads(f.read_text(encoding="utf-8"))
    rules = pro.get("board", {}).get("design_settings", {}).get("rules", {})
    classes = {c.get("name"): c for c in pro.get("net_settings", {}).get("classes", [])}
    off = []
    for what, have, soll in (("clearance", rules.get("min_clearance"), want["clearance"]),
                             ("edge clearance", rules.get("min_copper_edge_clearance"), want["edge"]),
                             ("via diameter", rules.get("min_via_diameter"), want["via"][0]),
                             ("track", (classes.get("Default") or {}).get("track_width"), want["track"][""])):
        if have is None or abs(have - soll) > 1e-4:
            off.append(f"{what} {have if have is not None else '–'} mm instead of {soll:.4f} mm")
    for name, width in want["track"].items():
        if name and abs(((classes.get(name) or {}).get("track_width") or 0) - width) > 1e-4:
            off.append(f"class {name}: track {(classes.get(name) or {}).get('track_width', '–')} mm instead of "
                       f"{width:.4f} mm")
    patterns = {(p.get("netclass"), p.get("pattern")) for p in pro.get("net_settings", {}).get("netclass_patterns", [])}
    off += [f"net {net} not in class {name}" for name, nets in want["classes"].items() for net in nets
            if (name, net) not in patterns]
    return off


def part_boxes(cfg, board, pcb=None):
    """{ref: (x0, y0, x1, y1)} in EasyEDA's frame (mm, y up): what a part covers on the board – its fabrication and
    silkscreen lines and its pads, as EasyEDA's bounding box of a part (silk apply keeps the designators off them)."""
    pcb = pcb or load(cfg, board)
    out = {}
    for ref, fp in parts(pcb):
        x0, y0, angle, _ = footprint_at(fp)
        pts = []
        for d in fp:
            if isinstance(d, list) and d and d[0] == "fp_line" and \
                    str(value(d, "layer", "")).endswith((".Fab", ".SilkS")):
                pts += [floats(d, "start"), floats(d, "end")]
        for pad in find(fp, "pad"):
            (ax, ay), r = floats(pad, "at")[:2], max(floats(pad, "size") or [0]) / 2
            pts += [[ax - r, ay - r], [ax + r, ay + r], [ax - r, ay + r], [ax + r, ay - r]]
        if not pts:
            continue
        absolute = [(x0 + dx, -(y0 + dy)) for dx, dy in (turn(px, py, angle) for px, py in pts)]
        xs, ys = [p[0] for p in absolute], [p[1] for p in absolute]
        out[ref] = (min(xs), min(ys), max(xs), max(ys))
    return out
