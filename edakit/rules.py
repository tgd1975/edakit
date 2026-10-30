"""The rule catalog (rules.json): every check edakit runs and every design hint, each with its rule, why it exists,
what to do about a finding and where the knowledge comes from.

    edakit rules [ID ...]       the catalog as a list, or the full entries of some checks and hints
    edakit hints [--json FILE]  the hints that apply to the project's graph, and the notes in its parts entries

Checks (P, G, E, S, L, F) find faults and block the release. A hint (H) has no rule that a program could decide: it
says what to consider when a kind of part is in the graph. The skill circuit-design works through the hints, the
agent electrical-reviewer confirms them, and a hint that is taken care of gets a line in the graph:
"hints": {"H-1": "C1 1000 µF next to J1"}.

Parts entries may carry their own notes: "hints" (a list, for the part) and "hint" per pin, e.g. on an ESP32 pin
that belongs to ADC2 ("no analog reads while WiFi is on"). `edakit hints` lists them for the parts and connected
pins of the graph.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .design import natural_key
from .engines.hint import MATCHERS, SIGNAL_TYPES  # noqa: F401 – the matchers of the hints live with the engine HINT

CATALOG = Path(__file__).with_name("rules.json")
@lru_cache(maxsize=1)
def catalog():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def entry(cid):
    c = catalog()
    return c["checks"].get(cid) or c["hints"].get(cid)


def title(cid):
    return (entry(cid) or {}).get("title", "")


def label(cid):
    """'L-9 (hole fits the lead)' – checks are named with words; nobody remembers the letters."""
    t = title(cid)
    return f"{cid} ({t})" if t else cid


def explain(cid, indent="    "):
    """Lines that explain a check or a hint: the rule, why it exists, what to do, the sources."""
    e = entry(cid)
    if not e:
        return []
    lines = [f"{label(cid)}: {e['rule']}" if "rule" in e else label(cid)]
    if e.get("retired"):
        lines.append(f"{indent}retired: {e['retired']}")
    lines += [f"{indent}why: {e['why']}", f"{indent}what to do: {e['fix']}"]
    lines += [f"{indent}source: {s}" for s in e.get("sources", [])]
    return lines


def matching_hints(design, cfg=None, sim=None):
    """{hint id: [what it applies to]} for every hint whose 'when' fits the graph."""
    out = {}
    for hid, h in catalog()["hints"].items():
        w = h["when"]
        hits = list(design.comps_of_kind(*w.get("kinds", [])))
        if "match" in w:
            hits += MATCHERS[w["match"]](design, cfg, sim)
        if hits:
            out[hid] = sorted(set(hits), key=natural_key)
    return out


def handled_hints(design):
    """The graph's record of hints that are taken care of: {"H-1": "how"}."""
    return design.graph.get("hints") or {}


def open_hints(design, cfg=None, sim=None):
    handled = handled_hints(design)
    return {h: hits for h, hits in matching_hints(design, cfg, sim).items() if h not in handled}


def part_notes(design):
    """(where, note) from the parts entries: the part's 'hints' and the 'hint' of every connected pin."""
    out = []
    for key in sorted({design.entry_key(d) for d in design.comps} - {None}, key=natural_key):
        part = design.parts[key]
        users = sorted((d for d in design.comps if design.entry_key(d) == key), key=natural_key)
        out += [(", ".join(users), note) for note in part.get("hints", [])]
        for num, pin in part["pins"].items():
            refs = [f"{d}.{num}" for d in users if f"{d}.{num}" in design.pin_net]
            if pin.get("hint") and refs:
                out.append((f"{', '.join(refs)} ({pin['name']})", pin["hint"]))
    return out


def load_sim(cfg):
    """The simulation config if there is one – hints use its sources; a missing or broken file is no error here."""
    try:
        return json.loads(cfg.sim_config.read_text(encoding="utf-8"))
    except (OSError, ValueError, AttributeError):
        return None


# --- command line ----------------------------------------------------------------------------------------------------
def main_rules(args):
    """edakit rules: the engines and codes of the catalog (edakit/catalog); per name a code's explanation, or – until
    the switch-over – an old check ID's entry of rules.json with the codes that replace it."""
    from . import catalog as codes
    if not args.ids:
        return codes.main_rules(args)
    unknown = []
    for i in args.ids:
        if entry(i):
            new = codes.old_map().get(i)
            print("\n".join(explain(i)) + (f"\n    replaced by: {', '.join(new)}" if new else "") + "\n")
        elif lines := codes.explain(i):
            print("\n".join(lines) + "\n")
        else:
            unknown.append(i)
    for i in unknown:
        print(f"{i}: not in the catalog")
    return 1 if unknown else 0


def main_hints(cfg, args):
    from .design import Design
    design = Design.from_config(cfg)
    found = matching_hints(design, cfg, load_sim(cfg))
    handled = handled_hints(design)
    open_ = {h: hits for h, hits in found.items() if h not in handled}
    for hid, hits in open_.items():
        lines = explain(hid)
        print(f"{lines[0]} – {', '.join(hits)}")
        print("\n".join(lines[1:]) + "\n")
    for hid, how in handled.items():
        if hid in found:
            print(f"{label(hid)} – {', '.join(found[hid])}\n    taken care of: {how}\n")
        elif not entry(hid):
            print(f"{hid}: in the graph's hints but not in the catalog\n")
    notes = part_notes(design)
    if notes:
        print("From the parts database:")
        for where, note in notes:
            print(f"  {where}: {note}")
        print()
    print(f"{len(open_)} open, {sum(h in found for h in handled)} taken care of"
          + (f", {len(notes)} notes from the parts database" if notes else "")
          + ". A hint that is taken care of gets a line in the graph: \"hints\": {\"H-…\": \"how\"}.")
    if args.json:
        Path(args.json).write_text(json.dumps(
            {"open": open_, "handled": {h: {"applies_to": found.get(h, []), "how": how} for h, how in handled.items()},
             "parts": [{"where": w, "note": n} for w, n in notes]}, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8")
    return 0
