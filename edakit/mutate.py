"""What no code catches (concept rules-at-scale.md, section 7: the mutation sweep; maker-coverage FT-21): mistakes
built into a copy of the design one at a time, each judged by the engines – a mistake that raises no new error, warning
or pending finding is reported. In memory: nothing is written.

    edakit mutate [--sim] [--json FILE]

The mistakes: every part left out; every diode, LED and polarized capacitor turned round; every resistor a hundred
times larger and smaller; every net that is neither ground nor a supply shorted to ground. --sim judges each with the
simulation as well (much slower). What it reports is a list to read, not a list of faults: some mistakes change nothing
that matters (a spare test point left out), others need a check nobody has built – that is what the sweep is for.
"""

from __future__ import annotations

import copy
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .circuit import polarized, supply_nets
from .design import Design

SEVERE = ("error", "warning", "pending")
FLIP_ROLES = {"diode": ("anode", "cathode"), "led": ("anode", "cathode"), "capacitor": ("plus", "minus")}


@dataclass
class Mutation:
    what: str                       # "R2 left out"
    graph: dict
    parts: dict
    caught: list = field(default_factory=list)   # the new findings: "LVL.undefined LED_OE"


def mutations(design):
    """Every mistake of the sweep: [(what, graph, parts)] – graph the dict inside "graph", parts {key: entry}."""
    base, parts = design.graph, design.parts
    out = []

    def without(des):
        g = copy.deepcopy(base)
        g["components"] = [c for c in g["components"] if c["designator"] != des]
        for n in g["nets"]:
            n["pins"] = [r for r in n["pins"] if r.split(".", 1)[0] != des]
        g["nets"] = [n for n in g["nets"] if n["pins"]]
        return g
    for des in sorted(design.comps):
        out.append((f"{des} left out", without(des), parts))
    for des in sorted(design.comps):
        part = design.part(des) or {}
        roles = FLIP_ROLES.get(part.get("kind"))
        if not roles or (part.get("kind") == "capacitor" and not polarized(part)):
            continue
        pins = {p.get("role"): f"{des}.{num}" for num, p in part["pins"].items()}
        a, b = pins.get(roles[0]), pins.get(roles[1])
        if not a or not b:
            continue
        g = copy.deepcopy(base)
        for n in g["nets"]:
            n["pins"] = [b if r == a else a if r == b else r for r in n["pins"]]
        out.append((f"{des} turned round", g, parts))
    for des in sorted(design.comps_of_kind("resistor")):
        key, ohm = design.entry_key(des), ((design.part(des) or {}).get("values") or {}).get("value_ohm")
        if not ohm:
            continue
        for factor, word in ((100, "a hundred times larger"), (0.01, "a hundred times smaller")):
            e = copy.deepcopy(design.parts[key])
            e["values"]["value_ohm"] = ohm * factor
            e["lcsc"] = f"MUTATED-{des}"
            g = copy.deepcopy(base)
            for c in g["components"]:
                if c["designator"] == des:
                    c["lcsc"] = e["lcsc"]
                    c.pop("value", None)
            out.append((f"{des} {word}", g, {**parts, e["lcsc"]: e}))
    quiet = {design.ground} | supply_nets(design) | set(design.graph.get("grounds") or [])
    for name in sorted(design.nets):
        if name in quiet:
            continue
        g = copy.deepcopy(base)
        pins = next(n for n in g["nets"] if n["name"] == name)["pins"]
        g["nets"] = [n for n in g["nets"] if n["name"] != name]
        next(n for n in g["nets"] if n["name"] == design.ground)["pins"] += pins
        out.append((f"{name} shorted to {design.ground}", g, parts))
    return out


def judged(design, cfg, sim=None):
    """(code, place) of every error, warning and pending finding – with `sim` also every failing simulation row."""
    from . import engines
    found = {(f.code, f.place) for f in engines.run(design, cfg).findings
             if f.severity in SEVERE and not f.accepted}
    if sim is not None:
        from .sim import run as simrun
        try:
            out = simrun.run_all(Design.from_data(design.graph, design.parts, design.boards), sim)
            found |= {(r["id"], r["item"]) for r in out["checks"] if r["result"] == "fail"}
        except Exception as e:      # a mistake the simulation cannot take is caught by it, in its way
            found.add(("SIM.config", f"{type(e).__name__}: {e}"[:80]))
    return found


def sweep(design, cfg, sim=None):
    """[Mutation] with what each raised that the design without the mistake does not."""
    base = judged(design, cfg, sim)
    out = []
    for what, graph, parts in mutations(design):
        d = Design.from_data(graph, parts, design.boards, design.graph_path)
        new = judged(d, cfg, sim) - base
        out.append(Mutation(what, graph, parts, sorted(f"{code} {place}" for code, place in new)))
    return out


def main(cfg, args):
    from . import engines
    d = Design.from_config(cfg)
    sim = engines.load_sim(cfg) if args.sim else None
    found = sweep(d, cfg, sim)
    missed = [m for m in found if not m.caught]
    for m in missed:
        print(f"not caught: {m.what}")
    print(f"{len(found)} mistakes, {len(found) - len(missed)} caught, {len(missed)} not caught"
          + ("" if args.sim else " (without the simulation – --sim adds it)"))
    if args.json:
        Path(args.json).write_text(json.dumps([{"what": m.what, "caught": m.caught} for m in found], indent=1,
                                              ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(0)
