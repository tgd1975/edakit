"""The KiCad side of the commands that write or read the EDA project (handbook 16): pcb, route's EasyEDA steps,
export. The commands dispatch here when the project's tool chain is KiCad; what they compute is shared.

    edakit pcb parts|nets|apply|tooling [--write]   board.write_parts: one writer for parts, nets, outline, holes
    edakit pcb dump                                 board.geometry -> <board>.geometry.json (nothing is turned)
    edakit pcb pour                                 the zones of [[pours]], filled by kicad-cli
    edakit pcb takeover [--write]                   rows for the parts that lie in the file without one
    edakit pcb autolayout                           none in KiCad: edakit pcb place --rest
"""

from __future__ import annotations

import json
import sys

from ...design import Design, natural_key
from . import board as kb
from . import cli


def say(msg):
    print(msg, flush=True)


def planned_pads(cfg, board, geo):
    """{ref.pad: (x, y) mil} where the plan puts every pad of a part with a row – Board.transform, as pcb apply's own
    comparison of EasyEDA's pads."""
    from ...config import MIL_PER_MM
    out = {}
    for ref, row in board.place.items():
        for num, p in (geo.get(ref) or {}).get("pads", {}).items():
            x, y = board.transform((p["x"], p["y"]), row.x, row.y, row.rot, row.side)
            out[f"{ref}.{num}"] = tuple(v * MIL_PER_MM for v in board.eda_point(x, y))
    return out


def parts_state(cfg, board, design):
    """(missing, extra, net differences) of the KiCad PCB against the graph."""
    pcb = kb.Pcb.load(kb.paths(cfg, board)["pcb"])
    want = design.board_comps(board.name)
    if pcb is None:
        return sorted(want, key=natural_key), [], []
    have = dict(kb.parts(pcb))
    nets = [f"{ref}.{pad[1]}: {kb.pad_net(pcb, pad) or '–'} instead of {design.pin_net.get(f'{ref}.{pad[1]}') or '–'}"
            for ref, fp in have.items() if ref in want for pad in kb.find(fp, "pad")
            if kb.pad_net(pcb, pad) != design.pin_net.get(f"{ref}.{pad[1]}", "")]
    return (sorted(set(want) - set(have), key=natural_key), sorted(set(have) - set(want), key=natural_key), nets)


def apply_check(cfg, board):
    """pcb apply's comparison: every pad of a planned part where the plan puts it (± 0.5 mil). -> findings."""
    from ... import part
    design = Design.from_config(cfg)
    geo = {ref: part.library_footprint(cfg, design, ref) or {} for ref in board.place}
    read = {f"{p['ref']}.{p['num']}": (p["x"], p["y"]) for p in kb.board_json(cfg, board)["pads"] if p["ref"]}
    off = []
    for key, (x, y) in planned_pads(cfg, board, geo).items():
        if key in read and max(abs(read[key][0] - x), abs(read[key][1] - y)) > 0.5:
            off.append(f"{key}: ({read[key][0]:.1f}, {read[key][1]:.1f}) mil instead of ({x:.1f}, {y:.1f})")
    return off


def pcb_main(cfg, board, args, regions=None):
    """edakit pcb <action> on a KiCad project."""
    from ... import pcb
    design = Design.from_config(cfg)
    action = args.action
    try:
        if action in ("parts", "nets"):
            missing, extra, nets = parts_state(cfg, board, design)
            todo = missing + extra if action == "parts" else nets
            say(f"  {action}: " + ("; ".join(
                ([f"missing {', '.join(missing)}"] if missing else []) + ([f"extra {', '.join(extra)}"] if extra else [])
                if action == "parts" else nets[:20]) or "PCB = graph"))
            if todo and args.write:
                path, parked = kb.write_parts(cfg, board, design)
                say(f"  written: {cfg.relative(path)}" + (f"; parked: {', '.join(parked)}" if parked else ""))
                return 0
            return 2 if todo else 0
        if action in ("apply", "tooling"):
            path, parked = kb.write_parts(cfg, board, design)
            say(f"  parts, outline, {len(board.holes)} holes and {len(board.tooling)} tooling holes -> "
                f"{cfg.relative(path)}")
            if parked:
                say(f"  ! without a row in [place], parked beside the board: {', '.join(parked)} – edakit pcb place "
                    "--rest, then pcb apply again")
            off = apply_check(cfg, board) if action == "apply" else []
            for line in off[:20]:
                say(f"  ! {line}")
            return 2 if off else 0
        if action == "dump":
            geo = kb.geometry(cfg, board, args.ref and args.ref.split(","))
            if args.ref:
                f = pcb.geometry_file(cfg, board)
                geo = (json.loads(f.read_text()) if f.exists() else {}) | geo
            say(f"{len(geo)} parts -> {pcb.save_geometry(cfg, board, geo)}")
            return 0
        if action == "pour":
            n = kb.write_zones(cfg, board, regions)
            cli.fill_zones(kb.paths(cfg, board)["pcb"], args.verbose)
            say(f"  {n} zones written and filled by kicad-cli")
            return 0
        if action == "takeover":
            return pcb.write_back(cfg, board, kb.pcb_json(cfg, board)["components"], auto=False, write=args.write)
        if action == "autolayout":
            print("edakit pcb autolayout: KiCad has no auto-layout – edakit places the parts itself: "
                  "edakit pcb place --rest --write, then pcb apply", file=sys.stderr)
            return 1
    except (kb.BoardError, cli.CliError) as e:
        print(f"edakit pcb {action}: {e}", file=sys.stderr)
        return 1
    print(f"edakit pcb {action}: not a step of the KiCad tool chain", file=sys.stderr)
    return 1


def drc_report(found, say=say):
    """Print KiCad's DRC findings by kind -> exit 0 without findings, 2 with."""
    if not found:
        say("  DRC: no findings")
        return 0
    kinds = {}
    for f in found:
        kinds.setdefault(f"{f['errorType']} ({f['severity']})", []).append(f)
    say(f"  DRC: {len(found)} findings – " + ", ".join(f"{k}: {len(v)}" for k, v in kinds.items()))
    for f in found[:15]:
        say(f"    {f['errorType']}: {f['description']} {' / '.join(f['items'][:2])}")
    return 2
