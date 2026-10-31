"""LEVELS: every input defined while the firmware is not running, no two drivers on a net, strapping pins at their
level at reset (concept rules-at-scale.md, section 1: level = (input, state) -> high, low, driven, undefined).

What a pin does to its net at reset comes from its type (catalog/levels.toml [reset]) – an output with drive
open_drain or tristate defines nothing, it lets go –; what holds a net otherwise is a resistor to a net something
defines. A transistor's control pin (base, gate) needs a resistor to the roles the table
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


def releases(info):
    """An output that lets go of its net: drive open_drain or tristate."""
    return info.get("drive") in ("open_drain", "tristate")


def pin_defines(info):
    return defines(info.get("type")) and not releases(info)


def run(ctx):
    d = ctx.joined
    return (undefined_inputs(d) + control_pins(d) + contention(d) + straps(d) + open_inputs(d) + released_nets(d)
            + analog_nodes(d))


def undefined_inputs(d):
    """LVL.undefined: an input with neither a driver nor a pull, or driven only by pins that float at reset."""
    rails = {name for name, net in d.nets.items() if any(pin_defines(d.pin_info(r)) for r in net["pins"])}
    pulls = defaultdict(list)
    for des, a, b in resistor_like(d):
        if b in rails:
            pulls[a].append(des)
        if a in rails:
            pulls[b].append(des)
    out = []
    for name, net in d.nets.items():
        infos = [d.pin_info(r) for r in net["pins"]]
        types = [i.get("type") for i in infos]
        if "input" not in types or pulls[name]:
            continue
        if any(releases(i) for i in infos):
            continue              # outputs that let go: released_nets asks for the pull-up
        on = (("net", name),)
        if not any(defines(t) or reset(t) == "floating" for t in types):
            out.append(Finding("LVL.undefined", "G", name, f"{name}: input without driver or pull resistor", on=on))
        elif not any(defines(t) for t in types):
            out.append(Finding("LVL.undefined", "G", name, f"{name}: only MCU pins drive this input – floating until the "
                               "firmware runs", fix="a pull resistor to the inactive level", on=on))
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
            text = (f"{des}: no base-emitter resistor – state undefined while the firmware is not running" if role == "base"
                    else f"{des}: no resistor from the gate to its source or a rail – the MOSFET is undefined while the "
                         "firmware is not running")
            out.append(Finding("LVL.undefined", "G", des, text, fix=f"10–100 kΩ from {role} to {c['to'][0]}",
                               on=(("component", des),)))
    return out


def contention(d):
    """LVL.contention: two or more pins that drive (catalog/levels.toml [drivers]) on one net – open-drain and
    tri-state outputs share a line among themselves, a push-pull output shares it with nobody."""
    kinds = set(data()["drivers"]["types"])
    out = []
    for name, net in d.nets.items():
        drivers = [r for r in net["pins"] if d.pin_info(r).get("type") in kinds]
        push = [r for r in drivers if not releases(d.pin_info(r))]
        if len(drivers) > 1 and push:
            out.append(Finding("LVL.contention", "G", name, f"{name}: several outputs drive this net: {', '.join(drivers)}",
                               on=(("net", name),)))
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
                                   "power-up is not defined by the graph", src, on=on))
            if wrong:
                out.append(Finding("LVL.boot", "G", ref, f"{what}, but {', '.join(wrong)} holds it "
                                   f"{'low' if want == 'high' else 'high'}", src, "another pin, or no pull", on=on))
            elif not forces and info.get("pull") != {"high": "up", "low": "down"}[want]:
                out.append(Finding("LVL.boot", "G", ref, f"{what}, but nothing holds it there: no pull on {net} and "
                                   "no internal pull in the parts entry", src, on=on))
    return out


def open_inputs(d):
    """LVL.undefined/nc: an input pin of an IC left in nc – a floating CMOS input switches at random and draws current
    – unless its entry gives it a pull or float_ok. A module is left out: it brings its own resistors, which its entry
    may not name."""
    out = []
    for des, comp in sorted(d.comps.items()):
        part = d.part(des) or {}
        if part.get("kind") != "ic":
            continue
        for num in comp.get("nc") or []:
            info = (part.get("pins") or {}).get(str(num)) or {}
            if info.get("type") == "input" and not info.get("pull") and not info.get("float_ok"):
                out.append(Finding("LVL.undefined", "G", f"{des}.{num}", f"{des}.{num} ({info.get('name', num)}): an input "
                                   "left open (nc) – it floats", f"pin {num} of {d.entry_key(des)}",
                                   "tie it to its inactive level, or float_ok on the pin where the datasheet allows it",
                                   grade="nc", on=(("component", des),)))
    return out


def released_nets(d):
    """LVL.undefined/open_drain: a net whose only drivers are open-drain or tri-state outputs and that nothing pulls up
    – released, it floats. An I2C line is REQ.missing's (needs.toml [i2c])."""
    from ..circuit import i2c_name
    from .requires import i2c_line
    rails = {name for name, net in d.nets.items() if any(pin_defines(d.pin_info(r)) for r in net["pins"])}
    held = rails | supply_nets(d) | {d.ground}
    out = []
    for name, net in d.nets.items():
        infos = [d.pin_info(r) for r in net["pins"]]
        open_ = [r for r, i in zip(net["pins"], infos) if releases(i)]
        if not open_ or any(pin_defines(i) for i in infos) or any(i.get("pull") == "up" for i in infos):
            continue
        if net.get("bus") == "i2c" or any(map(i2c_name, net.get("joined") or [name])) or any(map(i2c_line, infos)):
            continue
        if resistors_to(d, name, held - {name}):
            continue
        out.append(Finding("LVL.undefined", "G", name, f"{name}: driven only by outputs that let go ({', '.join(open_)}) "
                           "and nothing holds it – released, it floats", fix="a pull-up to the bus supply",
                           grade="open_drain", on=(("net", name),)))
    return out


def analog_nodes(d):
    """LVL.undefined/analog: a net with an analog pin that only capacitors reach – no resistor, no driver, no supply:
    it has no DC level, picks up hum, and a switch on it pops."""
    resistive = {x for _, a, b in resistor_like(d) for x in (a, b)}
    out = []
    for name, net in d.nets.items():
        infos = [(r, d.pin_info(r)) for r in net["pins"]]
        if name in resistive or not any(i.get("type") == "analog" for _, i in infos):
            continue
        others = [r for r, i in infos if i.get("type") not in ("analog", "input")]
        if all((d.part(r.partition(".")[0]) or {}).get("kind") == "capacitor" for r in others):
            out.append(Finding("LVL.undefined", "G", name, f"{name}: an analog node only capacitors reach – no DC "
                               "path to a defined level", fix="a resistor to the bias (a reference, ground)",
                               grade="analog", on=(("net", name),)))
    return out
