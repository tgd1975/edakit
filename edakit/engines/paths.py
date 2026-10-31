"""PATHS: what a reversed source reaches, which supply pins a supply reaches, and that ground pins are on ground
(concept rules-at-scale.md, section 1: path = reachability through pass-through classes).

Which parts pass a supply on, which take a reversed one and which block it is data: catalog/paths.toml. The engine
walks the graph through those classes and nothing else.
"""

from __future__ import annotations

import tomllib
from collections import defaultdict
from functools import lru_cache

from ..catalog import HERE
from ..circuit import polarized, reach, resistor_value, source_outputs
from ..findings import Finding


@lru_cache(maxsize=1)
def data():
    return tomllib.loads((HERE / "paths.toml").read_text(encoding="utf-8"))


def kind(d, des):
    return (d.part(des) or {}).get("kind")


def negative(d, net):
    """A negative rail: the net's declared range lies at or below 0 V and reaches below it (−12 V of a Eurorack
    module, a op-amp's V−)."""
    v = (d.nets.get(net) or {}).get("v") if net else None
    return isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v) and max(v) <= 0 < -min(v)


def reversible(d):
    """Components the graph marks as a source that may be reversed ("source": "reversible")."""
    return [des for des, c in d.comps.items() if c.get("source") == "reversible"]


def run(ctx):
    return reverse(ctx.joined, ctx.design) + supply(ctx.joined, ctx.sim)


def reverse(d, design):
    """PATH.reverse: the nets a reversed source reaches through the classes that pass it on touch only parts that
    tolerate it, or block it as [reverse] blocks says."""
    t = data()["reverse"]
    starts = set(d.comps_of_kind(*t["sources"])) | {des for des in reversible(design) if des in d.comps}
    side = {d.pin_net.get(f"{h}.{p}") for h in starts if d.part(h) for p in d.part(h)["pins"]} - {None, d.ground}
    todo = list(side)
    while todo:
        net = todo.pop()
        for ref in d.nets[net]["pins"]:
            des = ref.split(".", 1)[0]
            if des in starts or kind(d, des) not in t["passes"]:
                continue
            for p in d.part(des)["pins"]:
                n = d.pin_net.get(f"{des}.{p}")
                if n and n != d.ground and n not in side:
                    side.add(n)
                    todo.append(n)
    out = []
    for net in sorted(side):
        for ref in d.nets[net]["pins"]:
            des = ref.split(".", 1)[0]
            k = kind(d, des)
            if k is None or k in t["passes"]:
                continue
            if polarized(d.part(des)):
                out.append(Finding("PATH.reverse", "G", ref, f"{ref} on {net}: a reversed source reaches the polarized "
                                   f"capacitor {des} – it is reverse biased", "catalog/paths.toml [reverse]",
                                   "a series Schottky diode or a PMOS ahead of it, or a capacitor without polarity",
                                   grade="polarized", on=(("net", net), ("component", des))))
                continue
            if k in t["tolerates"]:
                continue
            role = d.pin_info(ref).get("role")
            if any(b["kind"] == k and b["role"] == role and all(d.net_of(des, o) not in side for o in b["outside"])
                   and (b.get("rail") != "negative" or all(negative(d, d.net_of(des, o)) for o in b["outside"]))
                   for b in t["blocks"]):
                continue
            out.append(Finding("PATH.reverse", "G", ref, f"{ref} on {net}: a reversed source reaches this pin without a "
                               "blocking device", "catalog/paths.toml [reverse]",
                               "a series Schottky diode, or a PMOS with its gate to ground (block reverse-pmos)",
                               on=(("net", net),)))
    return out


def inputs(d, sim=None):
    """Nets a supply feeds: power outputs, the input roles of [supply] inputs, every pin of a reversible source, the
    plus of a simulation source."""
    t = data()["supply"]["inputs"]
    out = {n for n, net in d.nets.items() if any(d.pin_info(r).get("type") == "power_output" for r in net["pins"])}
    marked = set(reversible(d))
    for des in d.comps:
        part = d.part(des) or {}
        roles = {num: str(p.get("role") or "") for num, p in (part.get("pins") or {}).items()}
        k = part.get("kind")
        if k == "battery_holder":
            take = [n for n, r in roles.items() if r.startswith(t[k])] or list(roles)
        elif k in t and t[k] in roles.values():
            take = [n for n, r in roles.items() if r == t[k]]
        elif des in marked:
            take = list(roles)
        else:
            continue
        out |= {d.pin_net.get(f"{des}.{n}") for n in take}
    for des, src in ((sim or {}).get("sources") or {}).items():
        if des in d.comps:
            out |= {d.pin_net.get(f"{des}.{plus}") for _, plus, _ in source_outputs(src)}
    return out - {None}


def steps(d):
    """{net: nets a supply reaches from it through one part} by the classes of [supply]."""
    t = data()["supply"]
    nxt = defaultdict(set)
    for des in d.comps:
        part = d.part(des) or {}
        k, value = part.get("kind"), resistor_value(d, des)
        if k in t["forward"]:
            a, b = (d.net_of(des, r) for r in t["forward"][k])
            if a and b:
                nxt[b if negative(d, a) else a].add(a if negative(d, a) else b)   # a negative rail feeds anode-ward
            continue
        if k in t["passes_roles"]:
            nets = {d.net_of(des, r) for r in t["passes_roles"][k]}
        elif k in t["passes"] or (value is not None and value <= t["resistor_max_ohm"]):
            nets = {d.pin_net.get(f"{des}.{p}") for p in part.get("pins") or {}}
        else:
            continue
        for n in nets - {None}:
            nxt[n] |= nets - {None, n}
    return nxt


def supply(d, sim=None):
    """PATH.ground: ground pins on ground, no supply pin on ground; PATH.unfed: every supply pin on a net a supply
    reaches. A net in the graph's grounds that does not exist: STRUCT.ref."""
    alias = {a: name for name, net in d.nets.items() for a in net.get("joined") or [name]}
    named = d.graph.get("grounds") or []
    out = [Finding("STRUCT.ref", "G", "grounds", f"grounds: no net {n} in the graph") for n in named
           if n not in alias]
    joins = defaultdict(set)
    by_roles = data()["ground"].get("joins_roles") or {}
    for des in d.comps_of_kind(*data()["ground"]["joins"], *by_roles):
        k = d.part(des)["kind"]
        nets = ({d.net_of(des, r) for r in by_roles[k]} if k in by_roles
                else {d.pin_net.get(f"{des}.{p}") for p in d.part(des)["pins"]}) - {None}
        for n in nets:
            joins[n] |= nets - {n}
    grounds = reach({d.ground} | {alias[n] for n in named if n in alias}, joins)
    supplied = reach(inputs(d, sim) - grounds, steps(d), stop=grounds)
    for des in d.comps:
        for num, info in ((d.part(des) or {}).get("pins") or {}).items():
            ref, net = f"{des}.{num}", d.pin_net.get(f"{des}.{num}")
            if net is None:
                continue
            what, on = f"{d.pin_text(ref)} on {net}", (("net", net),)
            if info.get("type") == "ground" and net not in grounds:
                out.append(Finding("PATH.ground", "G", ref, f"{what}, not on {d.ground}", on=on))
            elif info.get("type") == "power_in" and net in grounds:
                out.append(Finding("PATH.ground", "G", ref, f"{what}: a supply pin on ground", on=on))
            elif info.get("type") == "power_in" and net not in supplied:
                out.append(Finding("PATH.unfed", "G", ref, f"{what}: nothing supplies this net",
                                   "catalog/paths.toml [supply]", on=on))
    return out
