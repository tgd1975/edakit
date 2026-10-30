"""LEVELS: every input defined while the firmware is not running, no two drivers on a net, strapping pins at their
level at reset (concept rules-at-scale.md, section 1: level = (input, state) -> high, low, driven, undefined).

What a pin does to its net at reset comes from its type (catalog/levels.toml [reset]); what holds a net otherwise is a
resistor to a net something defines. A transistor's control pin (base, gate) needs a resistor to the roles the table
names. Stage E's levels – an input between its thresholds, an output that does not reach them – are in sim.py.
"""

from __future__ import annotations

import tomllib
from collections import defaultdict
from functools import lru_cache

from ..catalog import HERE
from ..circuit import resistor_like, resistors_to, supply_nets
from ..findings import Finding


@lru_cache(maxsize=1)
def data():
    return tomllib.loads((HERE / "levels.toml").read_text(encoding="utf-8"))


def reset(t):
    return data()["reset"].get(t)


def defines(t):
    """A pin of this type defines its net while the firmware is not running."""
    return reset(t) in ("driven", "high", "low")


def run(ctx):
    d = ctx.joined
    return undefined_inputs(d) + control_pins(d) + contention(d) + straps(d)


def undefined_inputs(d):
    """LVL.undefined: an input with neither a driver nor a pull, or driven only by pins that float at reset."""
    rails = {name for name, net in d.nets.items() if any(defines(d.pin_info(r).get("type")) for r in net["pins"])}
    pulls = defaultdict(list)
    for des, a, b in resistor_like(d):
        if b in rails:
            pulls[a].append(des)
        if a in rails:
            pulls[b].append(des)
    out = []
    for name, net in d.nets.items():
        types = [d.pin_info(r).get("type") for r in net["pins"]]
        if "input" not in types or pulls[name]:
            continue
        on = (("net", name),)
        if not any(defines(t) or reset(t) == "floating" for t in types):
            out.append(Finding("LVL.undefined", "G", name, "an input without a driver or a pull resistor", on=on,
                               old="G-4"))
        elif not any(defines(t) for t in types):
            out.append(Finding("LVL.undefined", "G", name, "only pins that float at reset drive this input – "
                               "undefined until the firmware runs", fix="a pull resistor to the inactive level",
                               on=on, old="G-4"))
    return out


def control_pins(d):
    """LVL.undefined: a transistor whose control pin (base, gate) has no resistor to the roles of [control] – its
    emitter, its source or a rail."""
    rails = {name for name, net in d.nets.items() if any(defines(d.pin_info(r).get("type")) for r in net["pins"])}
    held = rails | supply_nets(d)
    out = []
    for role, c in data()["control"].items():
        for des in d.comps_of_kind(*c["kinds"]):
            pin = d.net_of(des, role)
            targets = {d.net_of(des, r) for r in c["to"] if r != "rail"} - {None}
            if "rail" in c["to"]:
                if pin is None or pin in held:
                    continue
                targets |= held
            if pin is not None and resistors_to(d, pin, targets):
                continue
            to = " or ".join("a rail" if r == "rail" else f"its {r}" for r in c["to"])
            out.append(Finding("LVL.undefined", "G", des, f"no resistor from its {role} to {to} – undefined while the "
                               "firmware is not running", fix=f"10–100 kΩ from {role} to {c['to'][0]}",
                               on=(("component", des),), old="G-4"))
    return out


def contention(d):
    """LVL.contention: two or more pins that drive (catalog/levels.toml [drivers]) on one net."""
    kinds = set(data()["drivers"]["types"])
    out = []
    for name, net in d.nets.items():
        drivers = [r for r in net["pins"] if d.pin_info(r).get("type") in kinds]
        if len(drivers) > 1:
            out.append(Finding("LVL.contention", "G", name, f"{len(drivers)} outputs drive it: {', '.join(drivers)}",
                               on=(("net", name),), old="G-5"))
    return out


def straps(d):
    """LVL.boot: a pin with strap high or low is held there at reset – by a pull, a rail or its own pull – and nothing
    on its net holds it the other way or drives it."""
    supplies = supply_nets(d)
    out = []
    for des in d.comps:
        for num, info in ((d.part(des) or {}).get("pins") or {}).items():
            ref, want = f"{des}.{num}", info.get("strap")
            net = d.pin_net.get(ref)
            if want not in ("high", "low") or net is None:
                continue
            forces = []
            for r in d.nets[net]["pins"]:
                level = reset(d.pin_info(r).get("type"))
                if r != ref and level in ("driven", "high", "low", "supply"):
                    forces.append(("high" if level == "supply" else level, r))
            forces += [("low", r) for r, _, _ in resistors_to(d, net, {d.ground})]
            forces += [("high", r) for r, _, _ in resistors_to(d, net, supplies)]
            what, on = f"{ref} ({info['name']}) must be {want} at reset", (("net", net),)
            src = f"strap of pin {num} of {d.entry_key(des)}"
            driven = [by for lvl, by in forces if lvl == "driven"]
            wrong = [by for lvl, by in forces if lvl not in (want, "driven")]
            if driven:
                out.append(Finding("LVL.boot", "G", ref, f"{what}, but {', '.join(driven)} drives it – its level at "
                                   "power-up is not defined by the graph", src, on=on, old="G-12"))
            if wrong:
                out.append(Finding("LVL.boot", "G", ref, f"{what}, but {', '.join(wrong)} holds it "
                                   f"{'low' if want == 'high' else 'high'}", src, "another pin, or no pull", on=on,
                                   old="G-12"))
            elif not forces and info.get("pull") != {"high": "up", "low": "down"}[want]:
                out.append(Finding("LVL.boot", "G", ref, f"{what}, but nothing holds it there: no pull on {net} and "
                                   "no internal pull in the parts entry", src, on=on, old="G-12"))
    return out
