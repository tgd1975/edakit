"""The board's schematic as a KiCad file (<board>.kicad_sch) – the sheet `edakit schematic draw` lays out (handbook
16.3): the same blocks, parts, wires, flags and notes, with the parts' symbols as KiCad symbols.

    write(cfg, board)            -> (path, problems): the schematic and the board's symbol library (<board>.kicad_sym)
    check(cfg, board, out)       -> Findings: kicad-cli's netlist against the graph (S-2, schematic.compare) and the
                                    errors of KiCad's ERC

Every symbol is the drawing's own, one per part, turned as the sheet turns it (no rotation is left to KiCad); its pins
are the drawing's pin tips, of length 0 – the drawing draws the pin lines –, and passive, so that KiCad's ERC does
not ask for power drivers edakit's own checks (G) reason about. Nets are named by labels where the drawing writes a net
name or a flag, as global labels. The link to the PCB: every symbol's uuid is the path of its
footprint (board.symbol_uid), both written by edakit.

Units: the drawing's unit is 10 mil (0.254 mm), y up; the page's origin is its upper left corner, y down.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

from ...schematic_draw import MM, junctions, net_labels, pt
from ...schematic_layout import rot
from . import board as kb
from . import cli, library, sexp
from .sexp import Sym, uid

VERSION = 20231120             # KiCad 8's schematic format – KiCad 10 reads it
FONT_MM = 1.27
THICK_MM = 0.3


def symbol_lines(s, r):
    """The drawing's shapes of a symbol turned by r, in the symbol's own frame (mm, y up, as KiCad's symbols are)."""
    out = []

    def T(x, y):
        x, y = rot(x, y, r)
        return round(x * MM, 4), round(y * MM, 4)
    for sh in s.shapes:
        stroke = ["stroke", ["width", THICK_MM if sh[0] == "thick" else 0], ["type", Sym("default")]]
        if sh[0] in ("line", "thick"):
            out.append(["polyline", ["pts", *(["xy", *T(*q)] for q in sh[1])], stroke,
                        ["fill", ["type", Sym("none")]]])
        elif sh[0] == "poly":
            pts = [T(*q) for q in sh[1]]
            out.append(["polyline", ["pts", *(["xy", *q] for q in pts + pts[:1])], stroke,
                        ["fill", ["type", Sym("outline" if sh[2] else "none")]]])
        else:
            out.append(["circle", ["center", *T(sh[1], sh[2])], ["radius", round(sh[3] * MM, 4)], stroke,
                        ["fill", ["type", Sym("none")]]])
    return out


def effects(size=FONT_MM, justify=None, hide=False, bold=False):
    font = ["font", ["size", size, size]]
    if bold:
        font.append(["bold", True])
    out = ["effects", font]
    if justify:
        out.append(["justify", *map(Sym, justify)])
    if hide:
        out.append(Sym("hide"))
    return out


def label(net, at, angle, justify, uuid):
    """A global label: its net is named as the graph names it – a local label's net gets the sheet's path in front
    ("/GND"), and KiCad's schematic parity then finds every pad of the PCB on another net (16.8)."""
    return ["global_label", net, ["shape", Sym("passive")], ["at", *at, angle], ["fields_autoplaced", True],
            effects(justify=(justify,)), uuid,
            ["property", "Intersheetrefs", "${INTERSHEET_REFS}", ["at", *at, 0], effects(justify=(justify,),
                                                                                         hide=True)]]


def lib_symbol(name, s, r, ref, value, footprint):
    """(symbol "edakit:<ref>" …) of lib_symbols: the drawing's symbol turned by r, its pins at the tips."""
    base = name.split(":", 1)[1]
    prefix = "".join(ch for ch in ref if ch.isalpha()) or "U"
    pins = []
    for p, (lx, ly, away) in sorted(s.pins.items()):
        x, y = rot(lx, ly, r)
        angle = ((away + r) % 360 + 180) % 360         # KiCad: from the tip towards the body
        pins.append(["pin", Sym("passive"), Sym("line"), ["at", round(x * MM, 4), round(y * MM, 4), angle],
                     ["length", 0], ["name", str(p), effects()], ["number", str(p), effects()]])
    return ["symbol", name, ["pin_numbers", Sym("hide")], ["pin_names", ["offset", 0], Sym("hide")],
            ["exclude_from_sim", False], ["in_bom", True], ["on_board", True],
            ["property", "Reference", prefix, ["at", 0, 0, 0], effects()],
            ["property", "Value", value, ["at", 0, 0, 0], effects()],
            ["property", "Footprint", footprint, ["at", 0, 0, 0], effects(hide=True)],
            ["property", "Datasheet", "", ["at", 0, 0, 0], effects(hide=True)],
            ["property", "Description", "", ["at", 0, 0, 0], effects(hide=True)],
            ["symbol", f"{base}_0_1", *symbol_lines(s, r)],
            ["symbol", f"{base}_1_1", *pins]]


GRID = 5                       # KiCad's connection grid: 50 mil, 5 units of the drawing


def on_grid(sheet, syms, height):
    """(shift in x, page height) that put the drawing's pin tips – and with them its wires, which lie on the same
    grid – on KiCad's connection grid; ERC warns of every end off it (endpoint_off_grid)."""
    tip = next(((cx + rot(lx, ly, r)[0], cy + rot(lx, ly, r)[1]) for d, cx, cy, r in sheet.comps
                for lx, ly, _ in syms[d].pins.values()), None)
    if tip is None:
        return 0, height
    sx = -round(tip[0]) % GRID
    return sx, height + (round(tip[1]) - height) % GRID


def write(cfg, board, verbose=False):
    """The schematic of the board into its KiCad project -> (path, problems of the drawing). Nothing is written when
    the drawing has conflicts (wires of two nets touching, a pin without its wire)."""
    from ...schematic_draw import drawing
    drawn = drawing(cfg, board, drawn_by="edakit (KiCad)")
    if drawn is None:
        raise kb.BoardError(f"board {board.name} has no parts in the graph")
    design, sheet, size, syms, power = (drawn[k] for k in ("design", "sheet", "size", "syms", "power"))
    if drawn["problems"]:
        return None, drawn["problems"]
    W, H = size
    sx, H = on_grid(sheet, syms, H)
    W += sx

    def P(x, y):                       # the drawing's point -> the page (mm, y down), pins on KiCad's 50 mil grid
        return round((x + sx) * MM, 4), round((H - y) * MM, 4)
    refs = sorted(design.board_comps(board.name))
    fps = library.footprints(cfg, design, refs)
    root = kb.root_uid(cfg, board)
    items, libs = [], []
    k = 0

    def tag(*parts):
        nonlocal k
        k += 1
        return ["uuid", uid(board.name, "sch", k, *parts)]
    for d, cx, cy, r in sheet.comps:
        s = syms[d]
        comp = design.comps[d]
        name = f"{library.LIB}:{d}"
        footprint = f"{library.LIB}:{fps[d].name}"
        value = kb.part_value(design, d, fps[d])
        libs.append(lib_symbol(name, s, r, d, value, footprint))
        X, Y = P(cx, cy)
        places = [place for place, _, _ in s.labels]
        if r in (180, 270):
            places.reverse()
        label_at = {}
        for (x, y, anchor), (_, text, _) in zip(places, s.labels):
            rx, ry = rot(x, y, r)
            label_at[text] = (*P(cx + rx, cy + ry), {"start": ("left",), "end": ("right",)}.get(anchor))
        dx, dy, dj = label_at.get(d, (X, Y, None))
        vx, vy, vj = label_at.get(value, label_at.get(next((t for _, t, _ in s.labels if t != d), ""), (X, Y, None)))
        item = ["symbol", ["lib_id", name], ["at", X, Y, 0], ["unit", 1], ["exclude_from_sim", False],
                ["in_bom", comp.get("bom") is not False], ["on_board", True], ["dnp", False],
                ["uuid", kb.symbol_uid(cfg, board, d)],
                ["property", "Reference", d, ["at", dx, dy, 90 if r in (90, 270) else 0], effects(justify=dj)],
                ["property", "Value", value, ["at", vx, vy, 90 if r in (90, 270) else 0], effects(justify=vj)],
                ["property", "Footprint", footprint, ["at", X, Y, 0], effects(hide=True)]]
        if comp.get("lcsc"):
            item.append(["property", "LCSC", comp["lcsc"], ["at", X, Y, 0], effects(hide=True)])
        item += [["pin", str(p), ["uuid", uid(board.name, "pin", d, p)]] for p in sorted(s.pins)]
        item.append(["instances", ["project", board.name, ["path", f"/{root}", ["reference", d], ["unit", 1]]]])
        items.append(item)
        for x, y, text, size_, anchor, angle, _ in s.texts:      # pin names and numbers: texts of the sheet
            rx, ry = rot(x, y, r)
            a = (angle + r) % 360
            just = {"start": ("left",), "end": ("right",)}.get(anchor)
            if a in (180, 270):
                a -= 180
                just = {("left",): ("right",), ("right",): ("left",)}.get(just, just)
            items.append(["text", text, ["exclude_from_sim", False], ["at", *P(cx + rx, cy + ry), a],
                          effects(round(size_ * MM * 0.9, 3), justify=just), tag(d, "text", text)])
        for p in s.nc:
            px, py = rot(*s.pins[p][:2], r)
            items.append(["no_connect", ["at", *P(cx + px, cy + py)], tag(d, "nc", p)])
    tips = set()
    for d, cx, cy, r in sheet.comps:
        for p, (lx, ly, _) in syms[d].pins.items():
            if p not in syms[d].nc:
                px, py = rot(lx, ly, r)
                tips.add(pt(px + cx, py + cy))
    for _, segs in sheet.wires:
        for seg in segs:
            items.append(["wire", ["pts", ["xy", *P(seg[0], seg[1])], ["xy", *P(seg[2], seg[3])]],
                          ["stroke", ["width", 0], ["type", Sym("default")]], tag("wire", *seg)])
    for x, y in junctions(sheet, tips):
        items.append(["junction", ["at", *P(x, y)], ["diameter", 0], ["color", 0, 0, 0, 0], tag("junction", x, y)])
    for x, y, net, anchor, angle in net_labels(sheet, power, tips):
        x, y = (x, y - 4.5) if angle == 0 else (x + 4.5, y)       # on the wire: the drawing sets its text off it
        items.append(label(net, P(x, y), angle, "right" if anchor == "end" else "left", tag("label", net, x, y)))
    for net, x, y, fd in sheet.flags:
        items.append(label(net, P(x, y), fd % 360, "left", tag("flag", net, x, y)))
    for _, (x0, y0, x1, y1) in sheet.frames:
        pts = [P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1), P(x0, y0)]
        items.append(["polyline", ["pts", *(["xy", *q] for q in pts)], ["stroke", ["width", 0], ["type", Sym("dash")]],
                      tag("frame", x0, y0)])
    for x, y, content, size_, bold, align in sheet.texts:
        items.append(["text", content, ["exclude_from_sim", False], ["at", *P(x, y), 0],
                      effects(round(size_ * MM * 0.9, 3), justify=("left", "top"), bold=bold), tag("note", x, y)])
    date = design.graph.get("date") or datetime.date.today().isoformat()
    title = ["title_block", ["title", board.title], ["date", str(date)]]
    if board.revision:
        title.append(["rev", board.revision])
    title += [["company", cfg.company],
              ["comment", 1, f"graph v{design.version} – drawn by edakit: change the graph, not this drawing"]]
    text = sexp.dumps(["kicad_sch", ["version", VERSION], ["generator", "edakit"], ["generator_version", "8.0"],
                       ["uuid", root], ["paper", "User", round(W * MM, 2), round(H * MM, 2)], title,
                       ["lib_symbols", *libs], *items, ["sheet_instances", ["path", "/", ["page", "1"]]]]) + "\n"
    p = kb.paths(cfg, board)
    p["dir"].mkdir(parents=True, exist_ok=True)
    p["sch"].write_text(text, encoding="utf-8")
    write_library(cfg, board, libs)
    if not p["pro"].exists():
        kb.write_project(cfg, board, design)
    return p["sch"], []


def write_library(cfg, board, libs):
    """The board's symbols as a library of their own (<board>.kicad_sym) with its table – the schematic carries them
    too; the library is for looking at them in KiCad."""
    d = kb.paths(cfg, board)["dir"]
    (d / f"{board.name}.kicad_sym").write_text(sexp.dumps(
        ["kicad_symbol_lib", ["version", VERSION], ["generator", "edakit"], ["generator_version", "8.0"],
         *([s[0], s[1].split(":", 1)[1], *s[2:]] for s in libs)]) + "\n", encoding="utf-8")
    table = ["sym_lib_table", ["version", 7],
             ["lib", ["name", library.LIB], ["type", "KiCad"], ["uri", f"${{KIPRJMOD}}/{board.name}.kicad_sym"],
              ["options", ""], ["descr", "the board's symbols, generated by edakit"]]]
    (d / "sym-lib-table").write_text(sexp.dumps(table) + "\n", encoding="utf-8")


def check(cfg, board, verbose=False):
    """S-2 on KiCad: the netlist kicad-cli exports against the graph (schematic.compare), and the errors of KiCad's
    ERC. -> Findings."""
    from ...design import Design
    from ...schematic import Findings, compare
    design = Design.from_config(cfg)
    rep = Findings()
    p = kb.paths(cfg, board)
    if not p["sch"].exists():
        rep.add("schematic", f"{cfg.relative(p['sch'])} missing – edakit schematic create")
        return rep
    work = cfg.artifact("kicad_check", ".keep").parent
    nets, comps = cli.netlist(p["sch"], work / f"{board.name}.net", verbose)
    sch_comps = [{"reference": ref, "lcsc": f.get("LCSC"), "value": f.get("value")} for ref, f in comps.items()
                 if not ref.startswith("#")]
    sch_nets = [{"net_name": name, "nodes": [dict(zip(("component_ref", "pin"), q.split(".", 1))) for q in pins]}
                for name, pins in nets.items() if not name.startswith("unconnected-")]
    print(f"graph v{design.version}: {len(design.board_comps(board.name))} parts; schematic {p['sch'].name}: "
          f"{len(sch_comps)} parts, {len(sch_nets)} nets")
    compare(design.board_comps(board.name), design.board_nets(board.name), sch_comps, sch_nets, rep)
    for f in cli.erc(p["sch"], work / f"{board.name}_erc.json", verbose):
        if f["severity"] == "error":
            rep.add("erc", f"{f['errorType']}: {f['description']} {' / '.join(f['items'][:2])}".strip())
        else:
            print(f"  ERC {f['severity']}: {f['errorType']} {f['description']}")
    return rep


def run_check(cfg, args):
    """edakit schematic check, and the gate's stage S (gate.stage_schematic): the findings printed, with --json written
    as the sections of schematic.check. Exit 0 = the graph, 2 = differences, 1 = error."""
    import json
    board = cfg.board(args.board, made=True)
    try:
        rep = check(cfg, board, getattr(args, "verbose", False))
    except (kb.BoardError, cli.CliError) as e:
        print(f"edakit schematic check: {e}", file=sys.stderr)
        return 1
    rep.print()
    if getattr(args, "json", None):
        Path(args.json).write_text(json.dumps(rep.sections, indent=1, ensure_ascii=False))
    print(f"schematic = graph: {'yes' if not rep.count() else f'no – {rep.count()} differences'}")
    return 2 if rep.count() else 0


def main(cfg, args):
    """edakit schematic create|layout|check|copy on a KiCad project; draw stays the SVG."""
    board = cfg.board(args.board, made=True)
    try:
        if args.action in ("create", "layout"):
            if getattr(args, "dry_run", False):
                from ...schematic_draw import drawing
                problems = (drawing(cfg, board) or {}).get("problems", [])
                print(f"  dry run: {len(problems)} conflicts" + "".join(f"\n  ! {q}" for q in problems))
                return 2 if problems else 0
            path, problems = write(cfg, board, getattr(args, "verbose", False))
            if problems:
                for q in problems:
                    print(f"  ! {q}")
                print(f"{len(problems)} conflicts – nothing written")
                return 2
            print(f"  -> {cfg.relative(path)}")
            rep = check(cfg, board, getattr(args, "verbose", False))
            rep.print()
            print(f"schematic = graph: {'yes' if not rep.count() else f'no – {rep.count()} differences'}")
            return 2 if rep.count() else 0
        if args.action == "check":
            return run_check(cfg, args)
        if args.action == "copy":
            print("  KiCad: one schematic per board, written by schematic create – nothing to copy")
            return 0
    except (kb.BoardError, cli.CliError, library.LibraryError) as e:
        print(f"edakit schematic {args.action}: {e}", file=sys.stderr)
        return 1
    print(f"edakit schematic {args.action}: not a step of the KiCad tool chain", file=sys.stderr)
    return 1
