"""Stages P and G: what edakit check checks, offline, in well under a second (concept
docs/concepts/new/rules-at-scale.md).

    edakit check [--release] [--json FILE]

The engines decide (edakit/engines): STRUCT, LIMITS, LEVELS, REQUIRES, PATHS, PARTS and HINT on the graph and the
parts entries, and beyond the graph own parts, footprint copies, stock, supplier, the requirements file, scripts and
agents (engines/project.py) – with the holes against their leads (GEO.hole), formed leads (GEO.formed) and the sign-off
of every part (PARTS.verified) below. The project's domains (edakit/domains, [project] domains) say which findings
count and how much. The findings are printed grouped by code, the first five of each, with what to do; rule, why and
sources: edakit explain <code>.

What a person has seen and answered is accepted in the graph – "accept": {"<code>": "reason"} on the net or component,
or on the graph keyed by "<code>" or "<code> <place>"; a warning also in the sign-off file (8.2). Exit code 1 on
errors; with --release also on pending findings (an unverified part, an old stock snapshot).
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from .design import natural_key

FOOTPRINT_CODES = ("PARTS.footprint", "SYNC.footprint")   # own footprints as data: only where an entry has any
FORMED_MM = 0.05      # GEO.formed: a hole this far from the library's hole of its number is formed for the board
LEAD_PUSH_MM = 0.25   # GEO.formed: a formed lead this far off a hole still goes in with a push (about a lead's radius)


def has_footprint_data(cfg, design=None):
    """Whether a parts entry of the project has footprint data (4.5): PARTS.footprint and SYNC.footprint run then."""
    from .design import load_parts
    from .footprint import has_data
    return has_data(design.parts if design is not None else load_parts(cfg.parts))


def board_dumps(d, cfg):
    """dumped(des) -> the component's footprint as `pcb dump` measured it on its board, or None."""
    from . import part as parts
    from .pcb import geometry_file
    dumps = {name: parts._read(geometry_file(cfg, b)) or {} for name, b in cfg.boards.items()}

    def dumped(des):
        board = d.comps[des].get("board")
        return next((dump[des] for name, dump in dumps.items() if board in (None, name) and des in dump), None)
    return dumped


def footprint_geometry(d, cfg):
    """geometry(des) -> (footprint geometry, where from) or (None, None): the dump of the component's board – the
    project's footprint as placed –, else the footprint data of its parts entry (4.5), else the library footprint
    `edakit part import` cached."""
    from . import part as parts
    dumped = board_dumps(d, cfg)

    def geometry(des):
        if geo := dumped(des):
            return geo, "pcb dump"
        lib = parts.library_footprint(cfg, d, des)
        if not lib:
            return None, None
        return lib, (f"footprint data of {d.entry_key(des)}" if lib.get("source") == "data"
                     else f"library geometry {lib['footprint']}")
    return geometry


def check_holes(d, rep, geometry):
    """GEO.hole: the gate's hole-against-lead test (fab.hole_ok) on the plated holes of the footprint geometry, before anything
    is placed or routed. Same words and thresholds as the gate's test on the drill file."""
    from .part import pad_points
    from .release.fab import HOLE_PLAY_MM, HOLE_TOL_MM, JLC_SLOT_MM, hole_ok
    seen, unknown = False, []
    for des in sorted(d.comps, key=natural_key):
        entry = d.part(des)
        geo, where = geometry(des) if entry else (None, None)
        if not geo:
            continue
        seen = True
        holes = [(n, p) for n, _, _, p in pad_points(geo) if p.get("tht") and p.get("plated", True)]
        if not holes:
            continue
        if any(not p.get("hole") for _, p in holes):
            unknown.append(des)
            continue
        leads = entry.get("lead")
        if not leads:
            rep.add("pending", "PARTS.fact", f"{des} {d.entry_key(des)}: plated holes but no lead in the parts entry – "
                                       "the lead's cross-section from the datasheet (handbook 4.1)", grade="lead")
            continue
        bad, tight, narrow, nolead = defaultdict(list), defaultdict(list), defaultdict(list), []
        for n, p in holes:
            lead = leads.get(n) or leads.get("*")
            if lead is None:
                nolead.append(n)
                continue
            w, length = p["hole"]
            ok, is_tight, text = hole_ok(lead, w, length)
            if not ok:
                bad[text].append(n)
            elif is_tight:
                tight[text].append(n)
            if length > w + 0.01 and w < JLC_SLOT_MM - 1e-6:
                narrow[f"{w:.2f} x {length:.2f} mm"].append(n)
        pads = lambda ns: ", ".join(sorted(dict.fromkeys(ns), key=natural_key))  # noqa: E731
        for text, ns in bad.items():
            rep.error("GEO.hole", f"{des} (pads {pads(ns)}, {where}): {text}", d.comps[des].get("accept"))
        if tight:
            rep.warnings.append(("GEO.hole", f"{des} ({where}): tight hole – worst case below {HOLE_PLAY_MM} mm play (hole "
                                        f"-{HOLE_TOL_MM} mm, lead + tolerance): "
                                        + "; ".join(f"pad {pads(ns)}: {t}" for t, ns in tight.items())))
        if narrow:
            rep.warnings.append(("GEO.hole", f"{des} ({where}): slot narrower than {JLC_SLOT_MM} mm (JLCPCB minimum, plated, "
                                        "2 layers): " + "; ".join(f"pad {pads(ns)}: {s}" for s, ns in narrow.items())))
        if nolead:
            rep.add("pending", "PARTS.fact", f"{des} {d.entry_key(des)}: no lead for pad {pads(nolead)} in the parts "
                    "entry", grade="lead")
    if unknown:
        rep.notes.append(("GEO.hole", f"{', '.join(unknown)}: hole size unknown – edakit pcb dump (the geometry is older "
                                 "than P-7)"))
    return seen


def plated_holes(geo):
    """[(number, x mm, y mm, pad)] of the plated through-hole pads of a footprint geometry (P-7 reads the same)."""
    from .part import pad_points
    return [pt for pt in pad_points(geo) if pt[3].get("tht") and pt[3].get("plated", True)]


def on_library_pattern(holes, lib, pad_map):
    """GEO.formed: every hole lies within FORMED_MM of the library footprint's pad of its number (pad_map: intended swaps, as
    L-10), the two laid on each other by the shift that fits the numbers best – a footprint drawn around another
    origin keeps the library's pattern. -> True, False, or the numbers the library lacks."""
    import math

    from .part import pad_points
    at = defaultdict(list)
    for n, x, y, _ in pad_points(lib):
        at[n].append((x, y))
    pairs = [(x, y, at.get(pad_map.get(n, n))) for n, x, y, _ in holes]
    if lacks := sorted({n for (n, *_), (*_, c) in zip(holes, pairs) if not c}, key=natural_key):
        return lacks
    ones = [(c[0][0] - x, c[0][1] - y) for x, y, c in pairs if len(c) == 1]   # shell legs: no shift from them
    dx, dy = (sum(v[0] for v in ones) / len(ones), sum(v[1] for v in ones) / len(ones)) if ones else (0.0, 0.0)
    return all(min(math.dist((x + dx, y + dy), q) for q in c) <= FORMED_MM for x, y, c in pairs)


def self_fits(holes):
    """GEO.formed: [(turn, [(pin, pin whose hole it lands in)])] for every turn of 90°, 180° and 270° that lays the holes on
    themselves, every hole within LEAD_PUSH_MM of a hole – the position-only matching of `part diff` (part.fit)."""
    from .part import TURNS, fit
    out = []
    for turn in (t for t in TURNS if t):
        c = fit(holes, holes, turn, False)
        if max(r for _, _, r in c["pairs"]) <= LEAD_PUSH_MM:
            out.append((turn, [(holes[j][0], holes[i][0]) for i, j, _ in c["pairs"]]))
    return out


def check_formed(d, rep, cfg):
    """GEO.formed: a through-hole part whose plated holes the board's footprint (`pcb dump`) moves away from its library
    footprint – leads formed for this board – and that has three or more of them fits only one way round: no turn by
    90°, 180° or 270° lays its holes onto themselves with a pin in the hole of a pin on another net of the graph. The
    library footprint is the one of the dump's footprint name that `edakit part import` cached; without it, or when
    it lacks a pad number of the dump, a note. A part on its library pattern is not judged: its orientation is the
    print's job (L-8, P-2, M-2)."""
    from . import part as parts
    dumped = board_dumps(d, cfg)
    for des in sorted(d.comps, key=natural_key):
        geo = dumped(des)
        holes = plated_holes(geo) if geo else []
        if len(holes) < 3:
            continue
        name = geo.get("footprint")
        lib = parts.cached_footprint(cfg, name)
        if not lib:
            rep.notes.append(("GEO.formed", f"{des}: formed leads not judged – no library footprint {name} to compare the "
                                     "holes with (edakit part import <LCSC>)"))
            continue
        same = on_library_pattern(holes, lib, (d.part(des) or {}).get("pad_map") or {})
        if isinstance(same, list):
            rep.notes.append(("GEO.formed", f"{des}: formed leads not judged – the library footprint {name} has no pad "
                                     f"{', '.join(same)}"))
            continue
        if same:
            continue
        net = lambda n: d.pin_net.get(f"{des}.{n}")  # noqa: E731
        swaps = []
        for turn, pairs in self_fits(holes):
            shown = []
            for pin, hole in sorted(set(pairs), key=lambda p: (natural_key(p[0]), natural_key(p[1]))):
                if net(pin) != net(hole) and (hole, pin) not in shown:
                    shown.append((pin, hole))
            if shown:
                swaps.append((turn, shown))
        if swaps:
            (turn, shown), more = swaps[0], [t for t, _ in swaps[1:]]
            pin = lambda n: f"pin {n} ({net(n) or 'no net'})"  # noqa: E731
            rep.error("GEO.formed", f"{des}: its formed holes lie on each other turned by {turn}°"
                             + (f" (also {', '.join(f'{t}°' for t in more)})" if more else "") + " – "
                             + ", ".join(f"{pin(a)} in the hole of {pin(b)}" for a, b in shown),
                      d.comps[des].get("accept"))


def check_signoff(d, rep):
    for key in sorted({d.entry_key(des) for des in d.comps} - {None}):
        part = d.parts[key]
        if not part.get("verified"):
            users = [des for des in d.comps if d.entry_key(des) == key]
            rep.pending.append(("PARTS.verified", f"{key} {part.get('mpn', '')} ({', '.join(users)}) not verified against "
                                       "its datasheet"))
    for des, c in d.comps.items():
        if c.get("verify"):
            rep.pending.append(("PARTS.verified", f"{des}: open note 'verify': {c['verify']}"))
        if not c.get("lcsc") and not c.get("easyeda_device"):
            msg = f"{des}: neither an LCSC part nor an EasyEDA device"
            acc = c.get("accept") or {}
            rep.add("warning", "PARTS.verified", msg, acc.get("PARTS.verified/device") or acc.get("PARTS.verified", ""),
                    grade="device")



def main(cfg, args):
    from . import engines, requirements
    from .design import Design
    from .findings import format_findings
    try:        # a requirements file named in [project] requirements that is missing or not valid stops the check
        entries = requirements.load(cfg)
    except requirements.RequirementsError as e:
        print(f"edakit check: {e}", file=sys.stderr)
        return 1
    d = Design.from_config(cfg)
    rep = engines.run_all(d, cfg)
    prof = engines.profile(d, cfg)
    print(f"domains: core{''.join(', ' + n for n in prof.enabled)}"
          + ("" if cfg.domains is not None else " (suggested by the graph – edakit domains)"))
    if rep.findings:
        print("\n".join(format_findings(rep.findings)))
    groups = d.bridge_groups()
    if groups:
        print("joined by 0 Ω bridges, checked as one net: " + "; ".join(
            " = ".join([name] + [n for n in nets if n != name]) + f" ({', '.join(des)})" for name, nets, des in groups))
    c = rep.counts()
    print(f"{len(d.comps)} components, {len(d.nets)} nets, {len(d.parts)} parts entries; "
          + (", ".join(f"{c[k]} {k}" for k in ("error", "pending", "warning", "note", "accepted") if c[k])
             or "no finding")
          + (f"; requirements: {requirements.counts(entries)}" if cfg.requirements else ""))
    if args.json:
        Path(args.json).write_text(rep.to_json(), encoding="utf-8")
    return 1 if rep.errors or (args.release and rep.pending) else 0
