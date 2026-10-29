"""The hand-over from the circuit to the layout: what the board must keep, written into the graph by the circuit
designer or derived from it. The PCB designer works from it and does not change the graph (handbook 14.1).

    edakit handover [--board B]   the hand-over sheet: the circuit's state and sign-offs, the layout requirements

"layout" in the graph:
    fixed  [parts]                    the auto-layout must not decide them: a position in [place] of the board file
    edge   [parts]                    fixed at the board edge: within edge_mm of the outline (plan, default 1 mm)
    near   {part: host or [hosts]}    fixed within near_mm of the host (plan, default 6 mm)
    loops  [{a, b, max_mm, what}]     short current loop between two pads of one net, checked on the routed board (L-11)
    notes  [text]                     what no program checks – for the PCB designer and the layout review (M-5)
Derived without a line in the graph: every IC (kind "ic") with a supply pin is fixed with a capacitor of its own from
that supply to ground within near_mm – a module brings its own decoupling. An IC's waive {"L-12": reason} lifts it.

  G-1  the layout requirements name parts and pins of the graph (edakit check)
  L-12 the plan keeps them (edakit pcb plan, the gate)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .design import Design, natural_key

KEYS = ("fixed", "edge", "near", "loops", "notes")


@dataclass
class Requirement:
    kind: str            # fixed, edge, near, decoupling
    part: str
    others: tuple = ()   # near: the hosts; decoupling: the capacitors that can do it
    net: str = ""        # decoupling: the supply


def layout(design):
    return design.graph.get("layout") or {}


def hosts(value):
    return [value] if isinstance(value, str) else list(value or [])


def board_of(design, ref):
    return design.comps[ref.partition(".")[0]].get("board")


def problems(design):
    """G-1: unknown keys, parts or pins the graph does not have, a host on another board, a loop across nets."""
    lay = layout(design)
    out = [f"layout: unknown key '{k}' (known: {', '.join(KEYS)})" for k in lay if k not in KEYS]
    for key in ("fixed", "edge"):
        out += [f"layout.{key}: no part {d} in the graph" for d in lay.get(key, []) if d not in design.comps]
    for part, value in lay.get("near", {}).items():
        out += [f"layout.near: no part {d} in the graph" for d in (part, *hosts(value)) if d not in design.comps]
        if part in design.comps:
            out += [f"layout.near: {part} and {h} are on different boards" for h in hosts(value)
                    if h in design.comps and board_of(design, h) != board_of(design, part)]
    for lp in lay.get("loops", []):
        a, b = lp.get("a", ""), lp.get("b", "")
        lost = [r for r in (a, b) if r not in design.pin_net]
        if lost:
            out.append(f"layout.loops: {', '.join(lost)} is no connected pin of the graph")
        elif design.pin_net[a] != design.pin_net[b] or board_of(design, a) != board_of(design, b):
            out.append(f"layout.loops: {a} and {b} are not on one net of one board")
        if not isinstance(lp.get("max_mm"), (int, float)) or lp["max_mm"] <= 0:
            out.append(f"layout.loops: {a}-{b} needs max_mm above 0")
    return out


def decoupling_caps(design, comps):
    """Supply net -> capacitors between it and ground."""
    caps = defaultdict(list)
    for c in sorted(comps, key=natural_key):
        if (design.part(c) or {}).get("kind") == "capacitor":
            nets = {design.pin_net.get(f"{c}.{p}") for p in comps[c]["pins"]}
            if design.ground in nets and len(nets) == 2 and None not in nets:
                caps[(nets - {design.ground}).pop()].append(c)
    return caps


def requirements(design, board):
    """What the plan of one board must keep: layout.fixed, .edge, .near and the derived decoupling."""
    lay, mine = layout(design), design.board_comps(board)
    out = [Requirement(kind, d) for kind in ("fixed", "edge") for d in lay.get(kind, []) if d in mine]
    out += [Requirement("near", d, tuple(hosts(v))) for d, v in lay.get("near", {}).items() if d in mine]
    joined = design.joined()   # a capacitor that reaches its supply or ground over a 0 Ω bridge decouples as well
    ics = joined.board_comps(board)
    caps = decoupling_caps(joined, ics)
    for d in sorted(ics, key=natural_key):
        part = joined.part(d) or {}
        if part.get("kind") != "ic" or "L-12" in (ics[d].get("waive") or {}):
            continue
        supplies = {joined.pin_net.get(f"{d}.{n}") for n, p in part["pins"].items() if p.get("type") == "power_in"}
        out += [Requirement("decoupling", d, tuple(caps[n]), n) for n in sorted(supplies - {None}) if caps[n]]
    return out


def loops(design, board):
    """layout.loops of one board in the form of [[loops]] in the board file: (pad a, pad b, max mm, what)."""
    mine = design.board_comps(board)
    return [(lp["a"], lp["b"], float(lp["max_mm"]), lp.get("what", "")) for lp in layout(design).get("loops", [])
            if lp.get("a", "").partition(".")[0] in mine]


def signoffs(cfg):
    """Manual checks of scope 'circuit': (id, text, done or None) – done only for the current state of the circuit."""
    from .release import gate
    head = {"state_sha256": gate.state_hash(cfg),
            "layout_sha256": gate.layout_hash(cfg)}
    signoff, _ = gate.load_signoff(cfg, head)
    done = lambda m: f"{m['done_by']}, {m.get('date', '?')}" if m.get("done_by") else None  # noqa: E731
    return head["state_sha256"], [(m["id"], m.get("text", ""), done(m)) for m in signoff.get("manual", [])
                                  if m.get("scope", "circuit") == "circuit"]


def sheet(cfg, design, boards):
    state, signed = signoffs(cfg)
    lines = [f"hand-over: {cfg.project}, graph {design.version} ({design.graph.get('date', '?')}), "
             f"circuit {state[:12]}"]
    lines += [f"  {sid} {text[:60]}{'…' if len(text) > 60 else ''}: {done or 'open'}" for sid, text, done in signed]
    notes = layout(design).get("notes", [])
    for name in boards:
        req = requirements(design, name)
        lines.append(f"board {name} – the plan keeps this (L-12: edakit pcb plan, the gate)")
        for kind in ("fixed", "edge"):
            parts = [r.part for r in req if r.kind == kind]
            if parts:
                lines.append(f"  {kind:<6} {', '.join(parts)}")
        lines += [f"  near   {r.part} next to {', '.join(r.others)}" for r in req if r.kind == "near"]
        lines += [f"  near   {r.others[0] if len(r.others) == 1 else 'one of ' + ', '.join(r.others)} next to "
                  f"{r.part} – decoupling of {r.net}, a capacitor of its own (derived)"
                  for r in req if r.kind == "decoupling"]
        lines += [f"  loop   {a}-{b} at most {m:g} mm over tracks{f' ({w})' if w else ''} – L-11 on the routed board"
                  for a, b, m, w in loops(design, name)]
        if not req and not loops(design, name):
            lines.append("  nothing – no layout requirements in the graph and no IC to decouple")
    lines += ["notes for the layout:", *[f"  - {n}" for n in notes]] if notes else ["notes for the layout: none"]
    return lines


def main(cfg, args):
    design = Design.from_config(cfg)
    bad = problems(design)
    for p in bad:
        print(f"  ! G-1 {p}")
    boards = [cfg.board(args.board, made=True).name] if args.board else list(cfg.made())   # the layout part
    for line in sheet(cfg, design, boards):
        print(line)
    return 2 if bad else 0
