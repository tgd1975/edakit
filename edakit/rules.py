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
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from .design import natural_key

CATALOG = Path(__file__).with_name("rules.json")
SIGNAL_TYPES = {"input", "output", "bidirectional", "analog"}


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


# --- hints -----------------------------------------------------------------------------------------------------------
def _part_kind(design, des):
    return (design.part(des) or {}).get("kind")


def _power_inputs(design, cfg, sim):
    """Where the supply comes in: battery holders, connectors with a vbus pin, checks.reverse_protect, sim sources."""
    found = set(design.comps_of_kind("battery_holder"))
    found |= set((design.graph.get("checks") or {}).get("reverse_protect", []))
    found |= {d for d in design.comps_of_kind("connector")
              if "vbus" in {p.get("role") for p in design.part(d)["pins"].values()}}
    found |= set((sim or {}).get("sources", {}))
    return [d for d in found if d in design.comps]


def _resistor_neighbours(design, net):
    """Nets one resistor away from `net`."""
    out = set()
    for des in design.comps_of_kind("resistor"):
        a, b = (design.pin_net.get(f"{des}.{p}") for p in ("1", "2"))
        if net in (a, b):
            out.add(b if a == net else a)
    return out - {None}


def _connector_signals(design, cfg, sim):
    """Connectors with a signal line to an IC or module pin, directly or through one resistor (ground and supply
    nets are no signal lines)."""
    quiet = {design.ground} | {name for name, net in design.nets.items()
                               if any(design.pin_info(r).get("type") in ("power_in", "power_output", "ground")
                                      for r in net["pins"])}
    found = []
    for des in design.comps_of_kind("connector"):
        for num in design.part(des)["pins"]:
            net = design.pin_net.get(f"{des}.{num}")
            if net is None or net in quiet:
                continue
            nets = ({net} | _resistor_neighbours(design, net)) - quiet
            if any(design.pin_info(r).get("type") in SIGNAL_TYPES and _part_kind(design, r.split(".", 1)[0]) in
                   ("ic", "module") for n in nets for r in design.nets[n]["pins"]):
                found.append(des)
                break
    return found


def _transistors_at_connectors(design, cfg, sim):
    """A transistor whose collector or drain is on a connector pin: it switches a load off the board (a supply input
    is no load – a reverse-polarity PMOS has its drain there)."""
    inputs = set(_power_inputs(design, cfg, sim))
    found = []
    for des in design.comps_of_kind("npn", "pnp", "nmos", "pmos"):
        for role in ("collector", "drain"):
            net = design.net_of(des, role)
            conns = sorted({r.split(".", 1)[0] for r in design.nets[net]["pins"]
                            if _part_kind(design, r.split(".", 1)[0]) == "connector"} - inputs) if net else []
            found += [f"{des} at {c}" for c in conns]
    return found


def _switching_regulators(design, cfg, sim):
    regs = [d for d in design.comps_of_kind("ic", "module")
            if (design.part(d).get("params") or {}).get("behavior") in ("buck", "boost")]
    return regs + design.comps_of_kind("inductor")


def _supply_starts(design, cfg, sim):
    """{supply: nets it feeds directly}: the power inputs of H-1 by their supply pins – the plus of a battery holder,
    the vbus pins of a connector, the pins of a connector in checks.reverse_protect, the plus of a sim source – and a
    module's pin of type power_output with the role vbus (its USB VBUS brought out). Ground is no supply net."""
    protect = set((design.graph.get("checks") or {}).get("reverse_protect") or [])
    sources = (sim or {}).get("sources") or {}
    out = {}
    for des in design.comps:
        part = design.part(des) or {}
        pins = part.get("pins") or {}
        roles = {num: str(p.get("role") or "") for num, p in pins.items()}
        take = []
        if part.get("kind") == "battery_holder":
            take = [n for n, r in roles.items() if r.startswith("plus")] or list(pins)
        elif part.get("kind") == "connector" and "vbus" in roles.values():
            take = [n for n, r in roles.items() if r == "vbus"]
        elif des in protect:
            take = list(pins)
        if part.get("kind") == "module":
            take += [n for n, p in pins.items() if p.get("type") == "power_output" and roles[n] == "vbus"]
        if isinstance(sources.get(des), dict) and "plus" in sources[des]:
            take.append(str(sources[des]["plus"]))
        nets = {design.pin_net.get(f"{des}.{n}") for n in take} - {None, design.ground}
        if nets:
            out[des] = nets
    return out


def _supply_steps(design):
    """{net: [(next net, blocks)]} for a supply's current: fuses, switches and inductors (every pin), a MOSFET (drain
    and source both ways – its body diode or its channel conducts), diodes from anode to cathode (a block: nothing
    flows back). Two MOSFETs whose sources share a net – a back-to-back pair – pass nothing either way. A connector's
    pins are separate contacts: a cable joins its nets, not the connector."""
    fets = design.comps_of_kind("nmos", "pmos")
    shared = Counter(design.net_of(q, "source") for q in fets)
    steps = defaultdict(list)
    for des in design.comps:
        part = design.part(des) or {}
        kind = part.get("kind")
        if kind == "diode":
            a, k = design.net_of(des, "anode"), design.net_of(des, "cathode")
            if a and k and design.ground not in (a, k):
                steps[a].append((k, True))
            continue
        if kind in ("nmos", "pmos"):
            source = design.net_of(des, "source")
            if source != design.ground and shared[source] > 1:
                continue   # one of a back-to-back pair
            nets = {design.net_of(des, "drain"), source}
        elif kind in ("fuse", "switch", "inductor"):
            nets = {design.pin_net.get(f"{des}.{p}") for p in part.get("pins") or {}}
        else:
            continue
        nets -= {None, design.ground}
        for n in nets:
            steps[n] += [(m, False) for m in nets - {n}]
    return steps


def _two_supplies(design, cfg, sim):
    """Nets that two supplies reach, at least one of them without a diode on the way – current can flow back into
    that one: 'VIN (J1 unblocked, J2)'."""
    starts = _supply_starts(design, cfg, sim)
    if len(starts) < 2:
        return []
    steps, reached = _supply_steps(design), {}
    for supply, nets in starts.items():
        free = dict.fromkeys(nets, True)   # net -> reached without a block
        todo = list(nets)
        while todo:
            n = todo.pop()
            for m, block in steps.get(n, ()):
                if m not in free or (free[n] and not block and not free[m]):
                    free[m] = free[n] and not block
                    todo.append(m)
        reached[supply] = free
    out = []
    for net in design.nets:
        at = sorted(((s, r[net]) for s, r in reached.items() if net in r), key=lambda x: natural_key(x[0]))
        if len(at) > 1 and any(free for _, free in at):
            out.append(f"{net} ({', '.join(f'{s} unblocked' if free else s for s, free in at)})")
    return out


MATCHERS = {"power_input": _power_inputs, "connector_signal": _connector_signals,
            "transistor_at_connector": _transistors_at_connectors, "switching_regulator": _switching_regulators,
            "two_supplies": _two_supplies}


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
    c = catalog()
    if args.ids:
        unknown = [i for i in args.ids if not entry(i)]
        for i in args.ids:
            if entry(i):
                print("\n".join(explain(i)) + "\n")
        for i in unknown:
            print(f"{i}: not in the catalog")
        return 1 if unknown else 0
    print("Checks (they block the release):")
    for cid, e in c["checks"].items():
        print(f"  {cid:<5} {e['title']:<32} {'retired – ' + e['retired'] if e.get('retired') else e['rule']}")
    print("\nHints (things to consider, no rule a program could decide):")
    for hid, h in c["hints"].items():
        when = h["when"].get("match") or "parts of kind " + ", ".join(h["when"]["kinds"])
        print(f"  {hid:<5} {h['title']:<32} when: {when}")
    print("\nDetails: edakit rules <ID> …")
    return 0


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
