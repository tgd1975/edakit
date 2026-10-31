"""REQUIRES: what a part requires on its pins is in the graph and in range (concept rules-at-scale.md, section 1:
requirement = (pin or role, what, params, source)).

The requirements are data – catalog/needs.toml names which pins have them by type, role or kind, tables/ hold the
numbers, a parts entry's `needs` switches a default off. Each section of needs.toml is one kind of requirement this
engine knows: decoupling, i2c, flyback, cc, hot_loop, pin – the last what a pin's own entry says it needs (a capacitor,
a pull, a series resistor, ground or never ground) – and the pin functions a net's fn asks for (REQ.function).
"""

from __future__ import annotations

import tomllib
from collections import Counter, defaultdict
from functools import lru_cache

from ..catalog import HERE
from ..circuit import (FN_NAMES, I2C_R_MAX, I2C_SINK_A, I2C_VOL, USB_C_CC, USB_RD, USB_RD_TOL, cc_lines, fn_match,
                       hz_text, i2c_name, is_number, ohm, resistors_to, si, supply_nets, v_range, valid_hz, values)
from ..findings import Finding


@lru_cache(maxsize=1)
def needs():
    return tomllib.loads((HERE / "needs.toml").read_text(encoding="utf-8"))


def switched_off(d, des, need):
    """The parts entry of `des` switches the default requirement off: "needs": {need: false}."""
    return ((d.part(des) or {}).get("needs") or {}).get(need) is False


def run(ctx):
    d = ctx.joined
    return (decoupling(d) + i2c(d) + flyback(d) + usb_c(d) + functions(d) + hot_loops(ctx.design) + pin_needs(d)
            + balancing(d) + addresses(d) + uart_lines(d) + adc_sources(d) + btl_outputs(d) + instrument_loads(d)
            + stable_gains(d) + usb_data(d) + leaving_lines(d) + matrix(d) + bus_terminations(d) + bridge_clamps(d)
            + feedback_dividers(d) + pd_requests(d))


def decoupling(d):
    """REQ.missing: per supply pin on a net a capacitor from that net to ground – the graph's ground or a net of its
    grounds (a part referenced to its own ground: a cell protection IC on the cell's minus)."""
    n = needs()["decoupling"]
    gnd, caps = d.ground, Counter()
    grounds = {gnd} | set(d.graph.get("grounds") or [])
    for des in d.comps_of_kind("capacitor"):
        a, b = d.pin_net.get(f"{des}.1"), d.pin_net.get(f"{des}.2")
        if a in grounds and b not in grounds:
            caps[b] += 1
        elif b in grounds and a not in grounds:
            caps[a] += 1
    out = []
    for name, net in d.nets.items():
        supply = [r for r in net["pins"] if d.pin_info(r).get("type") == n["pin_type"]
                  and not switched_off(d, r.partition(".")[0], "decoupling")]
        if supply and caps[name] < len(supply):
            out.append(Finding("REQ.missing", "G", name, f"{name}: {len(supply)} IC supply pins ({', '.join(supply)}) but "
                               f"{caps[name]} capacitor(s) to {gnd}", n["source"], "100 nF next to each supply pin",
                               on=(("net", name),)))
    return out


def i2c_line(info):
    roles = needs()["i2c"]["roles"]
    if info.get("role"):
        return info["role"] if info["role"] in roles else None
    return i2c_name(info.get("name", ""))


def i2c(d):
    """REQ.missing: an I2C line without a pull-up to a supply; REQ.value: one outside (V − VOL) / sink … R max."""
    n = needs()["i2c"]
    supplies = supply_nets(d)
    out = []
    for name, net in d.nets.items():
        names = net.get("joined") or [name]
        if net.get("bus") != n["bus"] and not any(map(i2c_name, names)) and \
                not any(i2c_line(d.pin_info(r)) for r in net["pins"]):
            continue
        on, src = (("net", name),), f"{n['source']}; tables/i2c.toml"
        pulls = [(r, rail) for _, r, rail in resistors_to(d, name, supplies)]
        pulls += [(d.pin_info(r).get("pull_ohm"), None) for r in net["pins"] if d.pin_info(r).get("pull") == "up"]
        if not pulls:
            out.append(Finding("REQ.missing", "G", name, f"{name}: I2C line without a pull-up to a supply – the outputs "
                               "are open-drain", src, "4.7 kΩ to the bus supply (block i2c-pullups)", on=on))
            continue
        if any(r is None for r, _ in pulls):
            continue          # a pull-up of unknown value: its presence is all that can be checked
        r_eff = 1 / sum(1 / r for r, _ in pulls)
        v = max([v_range(d.nets[rail])[1] for _, rail in pulls if rail] or [v_range(net)[1]])
        r_min = (v - I2C_VOL) / I2C_SINK_A
        if r_eff > I2C_R_MAX:
            out.append(Finding("REQ.value", "G", name, f"{name}: pull-up {ohm(r_eff)} – above {ohm(I2C_R_MAX)}, the rising "
                               "edges get too slow", src, on=on))
        elif r_eff < r_min:
            out.append(Finding("REQ.value", "G", name, f"{name}: pull-up {ohm(r_eff)} – below ({v} V − {I2C_VOL} V) / "
                               f"{I2C_SINK_A * 1e3:g} mA = {ohm(r_min)}, a device cannot pull the line low enough",
                               src, on=on))
    return out


def flyback(d):
    """REQ.missing: a coil a transistor or an output switches has a diode across it, cathode at its plus – not where the
    output's entry says how it clamps (pin clamp: internal, or none – then REQ.missing/clamp asks for the bridge's
    diodes)."""
    n = needs()["flyback"]
    out = []
    for des in d.comps_of_kind(*n["coils"]):
        part = d.part(des)
        if (need := n["coil_if"].get(part["kind"])) and need not in values(part):
            continue
        plus, minus = (d.net_of(des, role) for role in n["coils"][part["kind"]])
        if not plus or not minus or plus == minus:
            continue
        switches = [q for q in d.comps_of_kind("npn", "pnp", "nmos", "pmos")
                    if {d.net_of(q, "collector"), d.net_of(q, "drain")} & {plus, minus}]
        switches += [r for net in (plus, minus) for r in d.nets[net]["pins"]
                     if d.pin_info(r).get("type") in ("output", "bidirectional")
                     and d.pin_info(r).get("clamp") not in ("internal", "none")]
        # an output with clamp = internal clamps the winding itself (a bridge's body or regenerative diodes); with
        # clamp = none a single diode across a winding a bridge drives both ways would short it – REQ.missing/clamp
        if switches and not any(d.net_of(x, "cathode") == plus and d.net_of(x, "anode") == minus
                                for x in d.comps_of_kind("diode")):
            word = {"motor": "the motor's winding", "solenoid": "the solenoid's winding"}.get(part["kind"],
                                                                                         f"the {part['kind']}'s coil")
            out.append(Finding("REQ.missing", "G", des, f"{des}: {word} switched by {', '.join(switches)} without a diode "
                               f"across it (cathode at {plus}, anode at {minus})", n["source"],
                               "a diode directly across the coil", on=(("component", des),)))
    return out


def feedback_dividers(d):
    """REQ.missing/feedback, REQ.value/feedback (maker-coverage FT-5): an adjustable regulator (values vref_v, a pin
    with the role adj or fb) has its divider – R1 from the output to that pin, R2 from it to ground –, and the output it
    sets stays within the output net's declared range."""
    from ..circuit import feedback_vout
    out = []
    for des in sorted(d.comps):
        part = d.part(des) or {}
        role = next((r for r in ("adj", "fb") if d.net_of(des, r)), None)
        if not is_number(values(part).get("vref_v")) or not role:
            continue
        net, on = d.net_of(des, "vout"), (("component", des),)
        fb = feedback_vout(d, des)
        if fb is None:
            out.append(Finding("REQ.missing", "G", des, f"{des}: an adjustable regulator ({role.upper()}) without its "
                               f"divider – a resistor from {net or 'its output'} to {d.net_of(des, role)} and one from "
                               f"there to {d.ground}", f"vref_v of {d.entry_key(des)}", "the divider of the datasheet's "
                               "application circuit", grade="feedback", on=on))
            continue
        vout, r1, r2 = fb
        hi = v_range(d.nets[net])[1] if net in d.nets else None
        if hi is not None and vout > hi + 1e-9:
            out.append(Finding("REQ.value", "G", des, f"{des}: R1 {ohm(r1)} and R2 {ohm(r2)} set the output to "
                               f"{vout:.3g} V, the net {net} declares up to {hi:g} V", f"vref_v of {d.entry_key(des)} "
                               "(VOUT = VREF × (1 + " + ("R2/R1" if role == "adj" else "R1/R2") + "))",
                               "the divider for the output the net is meant to carry, or the net's range",
                               grade="feedback", on=on))
    return out


def bridge_clamps(d):
    """REQ.missing/clamp (maker-coverage CK-15): an output whose entry says it has no clamp diodes of its own (pin field
    clamp = "none" – the L298's bridges) and that drives a winding or a connector has a diode from the output to a supply
    (cathode at the supply) and one from ground (anode at ground): the winding's current has a path when the bridge
    turns off."""
    n = needs()["flyback"]
    supplies, gnd, out = supply_nets(d), d.ground, []
    windings = set(d.comps_of_kind(*n["coils"])) | set(d.comps_of_kind("connector"))
    diodes = [(x, d.net_of(x, "anode"), d.net_of(x, "cathode")) for x in d.comps_of_kind("diode")]
    for des in sorted(d.comps):
        for num, pin in ((d.part(des) or {}).get("pins") or {}).items():
            net = d.pin_net.get(f"{des}.{num}")
            if pin.get("clamp") != "none" or not net:
                continue
            loads = sorted({r.partition(".")[0] for r in d.nets[net]["pins"]} & windings)
            if not loads:
                continue
            up = any(a == net and c in supplies for _, a, c in diodes)
            down = any(c == net and a == gnd for _, a, c in diodes)
            if up and down:
                continue
            lost = " and ".join(w for w, ok in ((f"one from {net} to the supply (cathode at the supply)", up),
                                                (f"one from {gnd} to {net} (anode at {gnd})", down)) if not ok)
            out.append(Finding("REQ.missing", "G", f"{des}.{num}", f"{des}.{num} ({pin.get('name', num)}) drives "
                               f"{', '.join(loads)} and has no clamp diodes of its own (clamp = none) – missing: {lost}",
                               "ST L298 datasheet (January 2000), 3 Applications: an external bridge of diodes is required "
                               "when inductive loads are driven", "fast diodes (trr ≤ 200 ns, Schottky preferred) from "
                               "each output to the supply and from ground", grade="clamp", on=(("component", des),)))
    return out


def usb_c(d):
    """REQ.missing, REQ.value, REQ.forbidden on the CC pins of the receptacles the graph shows, and of a module or
    breakout whose entry states it does not terminate them (values.usb_c cc none)."""
    n = needs()["cc"]
    src = f"{n['source']}; tables/usb.toml"
    want = f"{ohm(USB_RD)} to {d.ground} on each CC pin"
    out = []
    for des in d.comps:
        part = d.part(des)
        if not part:
            continue
        cc, usb, on = cc_lines(d, des), values(part).get("usb_c"), (("component", des),)

        def miss(text):
            out.append(Finding("REQ.missing", "G", des, f"{des}: {text}", src, f"{ohm(USB_RD)} per CC pin (block usb-c-sink)",
                               on=on, topic="cc"))
        if usb is not None:
            state = usb.get("cc") if isinstance(usb, dict) else None
            if state not in USB_C_CC:
                out.append(Finding("PARTS.schema", "P", d.entry_key(des), f"{des}: values.usb_c of {d.entry_key(des)} needs cc "
                                   f"{', '.join(USB_C_CC[:-1])} or {USB_C_CC[-1]}, not {state!r}", topic="cc"))
                continue
            if state != "none":
                continue
            if set(cc) != set(n["roles"]):
                miss(f"USB-C receptacle without CC termination (values.usb_c of {d.entry_key(des)}: cc none) and its "
                     f"CC lines are no pins of the graph – a USB-C source switches VBUS on only with {want}")
                continue
        elif part.get("kind") != n["kind"] or set(cc) != set(n["roles"]):
            continue
        if any(d.pin_info(r).get("type") not in (None, "passive") for net in cc.values() if net
               for r in d.nets[net]["pins"] if not r.startswith(f"{des}.")):
            continue          # a Type-C or PD controller drives the CC lines
        if cc["cc1"] and cc["cc1"] == cc["cc2"]:
            out.append(Finding("REQ.forbidden", "G", des, f"{des}: CC1 and CC2 on one net {cc['cc1']} – each needs its own "
                               f"{ohm(USB_RD)} to {d.ground}", src, on=on, topic="cc"))
            continue
        for line, net in sorted(cc.items()):
            if net is None:
                miss(f"{line.upper()} not connected – a USB-C source switches VBUS on only with {want}")
                continue
            rd = resistors_to(d, net, {d.ground})
            known = [r for _, r, _ in rd if r is not None]
            if not rd:
                miss(f"{line.upper()} ({net}) without a resistor to {d.ground} – needs {ohm(USB_RD)}")
            elif known and not any(abs(r - USB_RD) <= USB_RD * USB_RD_TOL for r in known):
                out.append(Finding("REQ.value", "G", des, f"{des}: {line.upper()} ({net}) has "
                                   f"{', '.join(ohm(r) for r in known)} to {d.ground} – needs {ohm(USB_RD)} ± "
                                   f"{USB_RD_TOL:.0%}", src, on=on, topic="cc"))
    return out


MATRIX_INPUT_LINES = ("rx",)       # what an input-only GPIO takes through a matrix


def controller(d, des):
    """A microcontroller or module – the parts whose pin functions a net's fn is held to; a peripheral's own pin
    functions (an amplifier's I2S inputs) would hide an MCU pin that cannot do it (schema-gaps A5)."""
    part = d.part(des) or {}
    return (part.get("kind") == "module" or values(part).get("behavior") == "mcu"
            or (d.comps.get(des) or {}).get("type") in ("microcontroller", "module"))


def matrix_kinds(d, des):
    """The fn kinds the part's GPIO matrix routes to any GPIO pin (entry matrix: ["uart", "i2c", "pwm"])."""
    m = (d.part(des) or {}).get("matrix")
    return set(m) if isinstance(m, list) else set()


def matrix_hit(d, ref, fn):
    """('m', None) where the part's GPIO matrix routes fn to this GPIO (a pin whose entry lists functions) – an output
    to a pin that can drive, an input line (rx) to an input-only pin too."""
    kind, _, line = fn.partition(".")
    info = d.pin_info(ref)
    if kind not in matrix_kinds(d, ref.partition(".")[0]) or not isinstance(info.get("functions"), list):
        return None
    if info.get("type") in ("bidirectional", "output") or (info.get("type") == "input" and line in MATRIX_INPUT_LINES):
        return "m", None
    return None


def functions(d):
    """REQ.function: the pin of a net with fn has that function – among the pins of microcontrollers and modules, or
    through their GPIO matrix (entry matrix) –, the nets of one fn_bus one peripheral instance per part, PWM nets of one
    slice one fixed pwm_hz and a channel each (a matrix routes any channel to any pin: no fixed slice). A pin without
    functions: PARTS.fact/functions; a net's fn or pwm_hz of the wrong form: STRUCT.net."""
    out, hits = [], {}
    for name, net in sorted(d.nets.items()):
        fn, on = net.get("fn"), (("net", name),)
        if not valid_hz(net.get("pwm_hz")):
            out.append(Finding("STRUCT.net", "G", name, f"{name}: pwm_hz must be a frequency in Hz or [min, max], not "
                               f"{net['pwm_hz']!r}", on=on))
        if not fn:
            continue
        if fn not in FN_NAMES:
            out.append(Finding("STRUCT.net", "G", name, f"{name}: unknown fn {fn!r} (known: {', '.join(FN_NAMES)})", on=on))
            continue
        known = [(r, d.pin_info(r)) for r in net["pins"]
                 if isinstance(d.pin_info(r).get("functions"), list) and controller(d, r.partition(".")[0])]
        if not known:
            out.append(Finding("PARTS.fact", "G", name, f"{name}: needs {fn}, but no pin of a microcontroller or module "
                               "on it has functions in its parts entry – not checked", grade="functions", on=on))
            continue
        hits[name] = [(r, *m) for r, info in known for f in info["functions"] if (m := fn_match(fn, f))]
        hits[name] += [(r, *m) for r, _ in known
                       if not any(h[0] == r for h in hits[name]) and (m := matrix_hit(d, r, fn))]
        if not hits[name]:
            has = "; ".join(f"{r} ({info['name']}) has " + (", ".join(info["functions"]) or "no free function")
                            for r, info in known)
            out.append(Finding("REQ.function", "G", name, f"{name}: needs {fn}, but {has}", "functions of the pins' entries",
                               on=on))
    buses = defaultdict(dict)
    for name, pins in hits.items():
        if bus := d.nets[name].get("fn_bus"):
            for ref, inst, _ in pins:
                buses[(bus, d.nets[name]["fn"].partition(".")[0], ref.partition(".")[0])].setdefault(name, {})[inst] = ref
    for (bus, kind, des), nets in sorted(buses.items()):
        if kind in matrix_kinds(d, des):
            continue                     # the matrix routes one instance to whichever pins the nets sit on
        if len(nets) > 1 and not set.intersection(*map(set, nets.values())):
            where = ", ".join(f"{n} on " + "/".join(f"{kind}{i}" for i in sorted(inst)) + " ("
                              + ", ".join(inst[i] for i in sorted(inst)) + ")" for n, inst in sorted(nets.items()))
            out.append(Finding("REQ.function", "G", f"bus {bus}", f"bus {bus}: {where} – the nets of one bus need one {kind} of "
                               f"{des}", on=tuple(("net", n) for n in sorted(nets))))
    slices = defaultdict(list)
    for name, pins in hits.items():
        if d.nets[name]["fn"] == "pwm":
            for ref, inst, channel in pins:
                if inst != "m":          # a matrix routes any channel to any pin: no fixed slice to share
                    slices[(ref.partition(".")[0], inst)].append((name, channel, ref))
    for (des, inst), users in sorted(slices.items()):
        for i, (a, ch_a, ref_a) in enumerate(users):
            for b, ch_b, ref_b in users[i + 1:]:
                if a == b:
                    continue
                on = (("net", a), ("net", b))
                hz_a, hz_b = d.nets[a].get("pwm_hz"), d.nets[b].get("pwm_hz")
                where = f"PWM slice {inst} of {des} ({ref_a}, {ref_b})"
                if ch_a == ch_b:
                    text = f"{a} and {b} on the same PWM channel pwm{inst}.{ch_a} of {des} ({ref_a}, {ref_b}) – one " \
                           "output for both"
                elif hz_a is None or hz_b is None:
                    text = f"{a} ({hz_text(hz_a)}) and {b} ({hz_text(hz_b)}) share {where} – give both their pwm_hz: " \
                           "a slice has one frequency"
                elif isinstance(hz_a, list) or isinstance(hz_b, list):
                    text = f"{a} ({hz_text(hz_a)}) and {b} ({hz_text(hz_b)}) share {where} – a slice has one " \
                           "frequency, a net whose frequency changes needs a slice of its own"
                elif hz_a != hz_b:
                    text = f"{a} ({hz_text(hz_a)}) and {b} ({hz_text(hz_b)}) share {where} – a slice has one frequency"
                else:
                    continue
                out.append(Finding("REQ.function", "G", a, text, on=on))
    return out


def hot_loops(d):
    """REQ.missing: a layout.loops entry on every net of the hot loop a parts entry names (hot_loop: pin roles; "gnd"
    also for ground pins) and on the net one diode behind its switch node. A switching regulator without hot_loop:
    PARTS.fact/hot_loop; a role the part does not have: PARTS.schema."""
    n = needs()["hot_loop"]
    covered = {d.pin_net.get(lp.get("a")) for lp in (d.graph.get("layout") or {}).get("loops") or []} - {None}
    out = []
    for des in d.comps:
        part = d.part(des) or {}
        roles, behavior = part.get("hot_loop"), values(part).get("behavior")
        who, key = (f"{des} ({behavior})" if behavior else des), d.entry_key(des)
        if roles is None:
            if part.get("kind") == "ic" and behavior in n["switchers"]:
                out.append(Finding("PARTS.fact", "P", who, f"{who}: parts entry {key} names no hot_loop – its hot loop "
                                   "cannot be asked for in layout.loops", grade="hot_loop", on=(("component", des),)))
            continue
        pins = {num: "gnd" if p.get("type") == "ground" and p.get("role") is None else p.get("role")
                for num, p in part["pins"].items()}
        for role in [r for r in roles if r not in pins.values()]:
            out.append(Finding("PARTS.schema", "P", key, f"{des}: hot_loop of {key} names '{role}', no pin role of the part"))
        nets = {}
        for num, role in pins.items():
            if role in roles and (net := d.pin_net.get(f"{des}.{num}")):
                nets.setdefault(net, f"{des}.{num} {part['pins'][num]['name']}")
        sw = {d.pin_net.get(f"{des}.{num}") for num, role in pins.items() if role == "sw" and role in roles} - {None}
        for dio in d.comps_of_kind("diode"):
            a, k = d.net_of(dio, "anode"), d.net_of(dio, "cathode")
            for here, there in ((a, k), (k, a)):
                if here in sw and there and there not in nets:
                    nets[there] = f"behind {dio}"
        for net, why in nets.items():
            if net not in covered:
                out.append(Finding("REQ.missing", "G", who, f"{who}: no layout.loops entry on {net} ({why})", n["source"],
                                   "a pad pair of the net with max_mm in layout.loops",
                                   on=(("net", net), ("component", des))))
    return out



def pin_needs_problems(need, pins=None):
    """What is wrong with one entry of a pin's needs: a known `what`, its window and v_min_v as numbers, min ≤ max;
    `to` naming another pin of the part (by number or name, where the part's pins are given), and given where the
    requirement always names one (crystal, tie); dir up or down."""
    n = needs()["pin"]
    if not isinstance(need, dict) or need.get("what") not in n["what"]:
        return [f"needs {need!r}: what must be one of {', '.join(n['what'])}"]
    what = need["what"]
    window, extra = n["windows"].get(what, []), n.get("keys", {}).get(what, [])
    out = [f"needs {what}: unknown key '{k}'" for k in sorted(set(need) - {"what", "source", "why", *window, *extra})]
    lo, hi = (need.get(k) for k in window) if window else (None, None)
    out += [f"needs {what}: {k} must be a number" for k in [*window, "v_min_v"] if k in need and not is_number(need[k])]
    if is_number(lo) and is_number(hi) and lo > hi:
        out.append(f"needs {what}: {window[0]} above {window[1]}")
    if what in n.get("needs_to", []) and "to" not in need:
        out.append(f"needs {what}: to – the other pin of the part – is missing")
    if "to" in need and pins is not None and other_pin(pins, need["to"]) is None:
        out.append(f"needs {what}: to {need['to']!r} names no pin of the part")
    if "dir" in need and need["dir"] not in ("up", "down"):
        out.append(f"needs {what}: dir must be up or down, not {need['dir']!r}")
    return out


def other_pin(pins, to):
    """The number of the pin `to` names – a pin number, else the first pin of that name – or None."""
    to = str(to)
    if to in pins:
        return to
    return next((num for num, p in pins.items() if (p or {}).get("name") == to), None)


def near_parts(d, des):
    """The parts layout.near places next to `des`, and those it places `des` next to."""
    near = (d.graph.get("layout") or {}).get("near") or {}

    def hosts(v):
        return [v] if isinstance(v, str) else list(v or [])
    return {k for k, v in near.items() if des in hosts(v)} | set(hosts(near.get(des)))


def pin_needs(d):
    """REQ.missing/pin, REQ.value/pin, REQ.forbidden/pin: what a pin's parts entry says it needs – a capacitor to
    ground or to another of its pins (to), rated at least v_min_v, a pull-up to a supply or a pull-down to ground, a
    series resistor, each in its window; a crystal to another of its pins in its frequency window; to be tied to
    another of its pins; to be on ground, or never on it; no pull resistor, no series resistor. A capacitor window is
    judged on the capacitors layout.near places next to the part where it names any on the net – the local
    decoupling –, else on the net's sum. A needs entry of the wrong form: PARTS.schema."""
    n = needs()["pin"]
    grounds = {d.ground} | set(d.graph.get("grounds") or [])
    supplies = supply_nets(d) - grounds
    between = defaultdict(list)         # frozenset of two nets -> [(capacitor, value, rating)]
    for des in d.comps_of_kind("capacitor"):
        a, b = (d.pin_net.get(f"{des}.{p}") for p in d.part(des)["pins"])
        if a and b and a != b:
            part = d.part(des)
            between[frozenset((a, b))].append((des, values(part).get("value_f"), (part.get("limits") or {}).get("v_max_v")))
    crystals = defaultdict(list)        # frozenset of two nets -> [(crystal, f_hz)]
    for des in d.comps_of_kind("crystal"):
        a, b = (d.pin_net.get(f"{des}.{p}") for p in d.part(des)["pins"])
        if a and b and a != b:
            crystals[frozenset((a, b))].append((des, values(d.part(des)).get("f_hz")))

    def caps_to(net, others):
        return [c for o in others for c in between.get(frozenset((net, o)), [])]
    out, seen = [], set()
    for des in sorted(d.comps):
        part = d.part(des) or {}
        for num, info in (part.get("pins") or {}).items():
            pin_needs_list = info.get("needs")
            if pin_needs_list is None:
                continue
            key = d.entry_key(des)
            if not isinstance(pin_needs_list, list):
                if key not in seen:
                    out.append(Finding("PARTS.schema", "P", key, f"{key}: pin {num} needs must be a list of requirements"))
                continue
            ref, net = f"{des}.{num}", d.pin_net.get(f"{des}.{num}")
            who, on = f"{ref} ({info.get('name', num)})", (("component", des),) + ((("net", net),) if net else ())
            pins = part.get("pins") or {}
            for need in pin_needs_list:
                problems = pin_needs_problems(need, pins)
                if problems:
                    if (key, num) not in seen:
                        out += [Finding("PARTS.schema", "P", key, f"{key}: pin {num} {p}") for p in problems]
                    continue
                what, src = need["what"], need.get("source") or n["source"]
                lo, hi = (need.get(k) for k in n["windows"].get(what, ["", ""]))
                to = other_pin(pins, need["to"]) if "to" in need else None
                to_name = f"{des}.{to} ({pins[to].get('name', to)})" if to else ""
                to_net = d.pin_net.get(f"{des}.{to}") if to else None

                def finding(code, text):
                    out.append(Finding(code, "G", who, f"{who}: {text}", src, grade="pin", on=on))
                if what == "to_ground":
                    if net not in grounds:
                        finding("REQ.missing", f"must be on ground ({d.ground}), is on {net or 'no net'}")
                    continue
                if what == "never_to_ground":
                    if net in grounds:
                        finding("REQ.forbidden", f"must never be on ground, is on {net}")
                    continue
                if what == "tie":
                    if net is None or net != to_net:
                        finding("REQ.missing", f"must be tied to {to_name} ({to_net or 'no net'}), is on {net or 'no net'}")
                    continue
                if what == "no_pull":
                    dirs = [need["dir"]] if need.get("dir") else ["up", "down"]
                    targets = (supplies if "up" in dirs else set()) | (grounds if "down" in dirs else set())
                    pulls = [r for r, _, _ in resistors_to(d, net, targets - {net})] if net else []
                    if pulls:
                        finding("REQ.forbidden", f"must have no external pull{'-' + dirs[0] if len(dirs) == 1 else ''} "
                                                 f"resistor – {', '.join(pulls)} on {net}")
                    continue
                if what == "no_series":
                    series = [r for r, _, _ in resistors_to(d, net, set(d.nets) - supplies - grounds - {net})] \
                        if net else []
                    if series:
                        finding("REQ.forbidden", f"must have no series resistor – {', '.join(series)} on {net}")
                    continue
                unit = {"capacitor": "F", "crystal": "Hz"}.get(what, "Ω")
                window = (f" of {si(lo, unit)} … {si(hi, unit)}" if lo is not None and hi is not None else
                          f" of at least {si(lo, unit)}" if lo is not None else
                          f" of at most {si(hi, unit)}" if hi is not None else "")
                if net is None:
                    finding("REQ.missing", f"not connected – needs a {what.replace('_', ' ')}{window}")
                    continue
                if what == "crystal":
                    found = crystals.get(frozenset((net, to_net)), []) if to_net else []
                    if not found:
                        finding("REQ.missing", f"needs a crystal{window} to {to_name} ({to_net or 'no net'}) – none "
                                               f"between {net} and it")
                    elif any(is_number(f) and ((lo is not None and f < lo) or (hi is not None and f > hi))
                             for _, f in found):
                        finding("REQ.value", f"needs a crystal{window} to {to_name} – "
                                             + ", ".join(f"{c}: {si(f, 'Hz')}" for c, f in found if is_number(f)))
                    continue
                if what == "capacitor":
                    if to:
                        found = caps_to(net, [to_net]) if to_net and to_net != net else []
                        there = f"to {to_name} ({to_net or 'no net'})"
                    else:
                        found = caps_to(net, grounds - {net})
                        there = f"to {d.ground}"
                    local = near_parts(d, des)
                    if any(c in local for c, _, _ in found):          # the decoupling next to the part, not the net's sum
                        found = [x for x in found if x[0] in local]
                        there += " next to the part (layout.near)"
                    low = [(c, v) for c, _, v in found if is_number(v) and "v_min_v" in need and v < need["v_min_v"]]
                    if low:
                        finding("REQ.value", f"needs a capacitor rated at least {si(need['v_min_v'], 'V')} {there} – "
                                             + ", ".join(f"{c} {si(v, 'V')}" for c, v in low))
                    found = [(c, x) for c, x, _ in found]
                    total = sum(x for _, x in found if is_number(x)) if all(is_number(x) for _, x in found) else None
                    names = ", ".join(c for c, _ in found)
                elif what in ("pull_up", "pull_down"):
                    targets = supplies if what == "pull_up" else grounds
                    found = [(r, x) for r, x, _ in resistors_to(d, net, targets)]
                    total = (1 / sum(1 / x for _, x in found)) if found and all(is_number(x) and x > 0 for _, x in found) \
                        else None
                    names, there = ", ".join(r for r, _ in found), "to a supply" if what == "pull_up" else f"to {d.ground}"
                else:
                    found = [(r, x) for r, x, _ in resistors_to(d, net, set(d.nets) - supplies - grounds - {net})]
                    total = min((x for _, x in found if is_number(x)), default=None)
                    names, there = ", ".join(r for r, _ in found), "in series"
                if not found:
                    finding("REQ.missing", f"needs a {what.replace('_', ' ')}{window} {there} – {net} has none")
                elif total is not None and ((lo is not None and total < lo) or (hi is not None and total > hi)):
                    finding("REQ.value", f"needs a {what.replace('_', ' ')}{window} {there} – {names} on {net}: "
                                         f"{si(total, unit)}")
            seen.add((key, num))
    return out


def balancing(d):
    """REQ.missing/balance: a net that only capacitors touch – capacitors in series, whose voltage divides by their
    leakage unless a resistor across each one shares it (a supercapacitor stack, two electrolytics for a higher
    voltage)."""
    out = []
    for name, net in d.nets.items():
        dess = {r.partition(".")[0] for r in net["pins"]}
        if len(net["pins"]) >= 2 and all((d.part(x) or {}).get("kind") == "capacitor" for x in dess):
            out.append(Finding("REQ.missing", "G", name, f"{name}: only capacitors touch it ({', '.join(sorted(dess))}) – "
                               "in series their voltage divides by leakage", "edakit handbook 3.3",
                               "a balancing resistor across each capacitor", grade="balance", on=(("net", name),)))
    return out


def pin_level(d, ref, info, supplies, grounds):
    """'high', 'low' or None: what holds a pin – its net a supply or ground, a resistor to one, its own pull."""
    net = d.pin_net.get(ref)
    if net in grounds:
        return "low"
    if net in supplies:
        return "high"
    if net is not None:
        up, down = resistors_to(d, net, supplies), resistors_to(d, net, grounds)
        if up and not down:
            return "high"
        if down and not up:
            return "low"
        if up or down:
            return None
    return {"up": "high", "down": "low"}.get(info.get("pull"))


ADDRESS_STATES = ("low", "high", "sda", "scl")   # what an address pin can be tied to


def addresses(d):
    """REQ.forbidden/address: two devices on one bus at the same address. An entry's address gives its base, the pins
    that add to it when high ({pin: value}) – or, for a pin with four states, what each adds ({pin: {low, high, sda,
    scl}} – INA219: tied to GND, VS, SDA or SCL) – and further addresses it answers to (also); the bus is the net of
    its pin `on`, by default the pin with the role sda. A pin whose level the graph does not decide leaves the device
    out."""
    buses, out = bus_devices(d)
    for bus, devs in sorted(buses.items()):
        by = defaultdict(list)
        for x, des, how in devs:
            by[x].append((des, how))
        for x, users in sorted(by.items()):
            if len({des for des, _ in users}) > 1:
                who = ", ".join(f"{des} ({how})" if how else des for des, how in users)
                out.append(Finding("REQ.forbidden", "G", f"bus {bus}", f"bus {bus}: {who} all answer to 0x{x:02X}",
                                   "address of the parts entries", "another address by its pins, another part, or a "
                                   "second bus", grade="address", on=tuple(("component", des) for des, _ in users)))
    return out


def bus_devices(d):
    """({bus net: [(address, des, how)]}, [PARTS.schema findings]) – every device whose entry gives its address, at
    the address its pins decide ('A0 low, A1 high'), and its further fixed addresses (how 'fixed')."""
    grounds = {d.ground} | set(d.graph.get("grounds") or [])
    supplies = supply_nets(d) - grounds
    buses = defaultdict(list)            # net -> [(address, des, how)]
    out = []
    for des in sorted(d.comps):
        part = d.part(des) or {}
        a = part.get("address")
        if a is None:
            continue
        key, pins = d.entry_key(des), part.get("pins") or {}

        def state_map(v):
            return isinstance(v, int) or (isinstance(v, dict) and v and set(v) <= set(ADDRESS_STATES)
                                          and all(isinstance(x, int) for x in v.values()))
        if not (isinstance(a, dict) and isinstance(a.get("base"), int) and isinstance(a.get("pins", {}), dict)
                and all(str(p) in pins and state_map(v) for p, v in a.get("pins", {}).items())
                and all(isinstance(x, int) for x in a.get("also", []))):
            out.append(Finding("PARTS.schema", "P", key, f"{key}: address must be {{base, pins: {{pin: value when high, "
                               f"or {{low, high, sda, scl: value}}}}, also: […], on: pin}} with integers, not {a!r}",
                               grade="address"))
            continue
        on = a.get("on") or next((n for n, i in pins.items() if i.get("role") == "sda"), None)
        bus = d.pin_net.get(f"{des}.{on}") if on else None
        if bus is None:
            continue
        scl = next((d.pin_net.get(f"{des}.{n}") for n, i in pins.items() if i.get("role") == "scl"), None)
        value, how = a["base"], []
        for num, add in sorted(a.get("pins", {}).items()):
            net = d.pin_net.get(f"{des}.{num}")
            # a pin with four states (INA219: GND, VS, SDA, SCL) reads the bus lines as states of their own
            state = ("sda" if net is not None and net == bus else "scl" if net is not None and net == scl
                     else pin_level(d, f"{des}.{num}", pins[str(num)], supplies, grounds))
            if isinstance(add, int):
                state = "high" if state in ("sda", "scl") else state      # a two-state pin: the bus lines idle high
                add = {"low": 0, "high": add}
            if state is None or state not in add:
                value = None
                break
            value += add[state]
            how.append(f"{pins[str(num)].get('name', num)} {state}")
        if value is None:
            continue
        for x in [value, *a.get("also", [])]:
            buses[bus].append((x, des, ", ".join(how) if x == value else "fixed"))
    return buses, out


def uart_lines(d):
    """REQ.function/uart: a UART line crosses – on a net whose fn is uart.tx the MCU transmits and another part
    receives (an input), on uart.rx another part transmits (an output). A net with a passive pin (a connector, a
    cable) goes off the board and is left alone."""
    out = []
    for name, net in sorted(d.nets.items()):
        fn = net.get("fn")
        if fn not in ("uart.tx", "uart.rx"):
            continue
        infos = [(r, d.pin_info(r)) for r in net["pins"]]
        mine = [r for r, i in infos if any(fn_match(fn, f) for f in i.get("functions") or [])]
        others = [(r, i) for r, i in infos if r not in mine]
        if not mine or any(i.get("type") in (None, "passive") for _, i in others):
            continue
        want = "input" if fn == "uart.tx" else "output"
        if not any(i.get("type") in (want, "bidirectional") for _, i in others):
            have = ", ".join(f"{r} ({i.get('type')})" for r, i in others) or "nothing else"
            text = (f"{name}: {mine[0]} transmits (uart.tx), but nothing on it receives – {have}" if fn == "uart.tx"
                    else f"{name}: {mine[0]} receives (uart.rx), but nothing on it transmits – {have}")
            out.append(Finding("REQ.function", "G", name, text, "fn of the net, pin types of the entries",
                               "cross the lines: TX to RX, RX to TX", grade="uart", on=(("net", name),)))
    return out


def adc_sources(d):
    """REQ.value/adc: the source resistance an ADC pin sees – the resistors on its net in parallel – within what its
    entry allows (pin adc.r_source_max_ohm), unless a hold capacitor of at least adc.c_hold_min_f sits at the pin."""
    grounds = {d.ground} | set(d.graph.get("grounds") or [])
    out = []
    for name, net in sorted(d.nets.items()):
        if net.get("fn") != "adc":
            continue
        for ref in net["pins"]:
            adc = d.pin_info(ref).get("adc")
            if not isinstance(adc, dict) or not is_number(adc.get("r_source_max_ohm")):
                continue
            rs = [x for _, x, _ in resistors_to(d, name, set(d.nets) - {name})]
            if not rs or not all(is_number(x) and x > 0 for x in rs):
                continue
            r_src = 1 / sum(1 / x for x in rs)
            hold = 0.0
            for c in d.comps_of_kind("capacitor"):
                ends = [d.pin_net.get(f"{c}.{p}") for p in d.part(c)["pins"]]
                if name in ends and any(e in grounds for e in ends):
                    hold += values(d.part(c)).get("value_f") or 0
            if r_src > adc["r_source_max_ohm"] and not (is_number(adc.get("c_hold_min_f")) and hold >= adc["c_hold_min_f"]):
                held = f", or a hold capacitor of {si(adc['c_hold_min_f'], 'F')} at the pin" if is_number(
                    adc.get("c_hold_min_f")) else ""
                out.append(Finding("REQ.value", "G", ref, f"{ref} ({name}): source resistance {ohm(r_src)} – the ADC "
                                   f"allows {ohm(adc['r_source_max_ohm'])}{held}", f"adc of pin {ref}",
                                   "a smaller divider, a buffer, or the hold capacitor", grade="adc",
                                   on=(("net", name),)))
    return out


def btl_outputs(d):
    """REQ.forbidden/btl: a bridge-tied output (roles out_p, out_n – a suffix per channel) on ground, on a net another
    part drives or reads, or on another channel's net; the load between a pair is a speaker."""
    grounds = {d.ground} | set(d.graph.get("grounds") or [])
    out = []
    for des in sorted(d.comps):
        pins = (d.part(des) or {}).get("pins") or {}
        mine = {}
        for num, info in pins.items():
            role = str(info.get("role") or "")
            if role.startswith(("out_p", "out_n")) and (net := d.pin_net.get(f"{des}.{num}")):
                mine[f"{des}.{num}"] = (role, net)
        for ref, (role, net) in mine.items():
            who, on = f"{ref} ({role})", (("component", des), ("net", net))

            def bad(text):
                out.append(Finding("REQ.forbidden", "G", who, f"{who}: {text}", "roles out_p, out_n of "
                                   f"{d.entry_key(des)}", "a speaker between the pair and nothing else on it",
                                   grade="btl", topic="btl", on=on))
            if net in grounds:
                bad(f"a bridge-tied output on {net} – it is never ground")
                continue
            twins = [r for r, (ro, n) in mine.items() if n == net and r != ref]
            if twins:
                bad(f"on {net} with {', '.join(twins)} – each output of a bridge needs its own net")
            others = [r for r in d.nets[net]["pins"] if not r.startswith(f"{des}.") and d.pin_info(r).get("type")
                      in ("input", "output", "bidirectional", "analog", "power_in", "power_output")]
            if others:
                bad(f"on {net} with {', '.join(others)} – a bridge-tied output drives the speaker and nothing else")
    return out


def instrument_loads(d):
    """REQ.value/instrument: an instrument input (a net with instrument and load_min_ohm) loaded by less than it
    allows – its DC load: the resistors from it and the inputs on it (pin z_in_ohm) in parallel, a resistor in series
    to a net that reaches only capacitors and high-impedance pins (an RF filter's 10 kΩ into its 100 pF) no load, one
    to a net with a further path (a bias divider) with that path's resistance added."""
    out = []
    for name, net in sorted(d.nets.items()):
        least = net.get("load_min_ohm")
        if not net.get("instrument") or not is_number(least):
            continue
        load = dc_load(d, name)
        if load is None or load == float("inf"):
            continue
        if load < least:
            out.append(Finding("REQ.value", "G", name, f"{name}: the {net['instrument']} sees {ohm(load)} – it wants at "
                               f"least {ohm(least)}", f"load_min_ohm of net {name}",
                               "a buffer with a high input impedance first (block instrument-buffer, maker-coverage "
                               "BL-16), larger bias resistors", grade="instrument", on=(("net", name),)))
    return out


def dc_load(d, net, seen=frozenset()):
    """The DC resistance from `net` to a fixed level – ground, a supply, a net a pin drives –, capacitors open: every
    resistor to a fixed net in parallel with every resistor on to a net that has a DC path itself (its resistance
    added), and the inputs' z_in_ohm. inf without a DC path; None where a resistor has no value."""
    from .levels import pin_defines
    fixed = {d.ground} | supply_nets(d) | {n for n, x in d.nets.items()
                                          if any(pin_defines(d.pin_info(r)) for r in x["pins"])}
    branches = [d.pin_info(r)["z_in_ohm"] for r in d.nets[net]["pins"] if is_number(d.pin_info(r).get("z_in_ohm"))]
    for _, r, other in resistors_to(d, net, set(d.nets) - {net} - set(seen)):
        if not is_number(r) or r <= 0:
            return None
        if other in fixed:
            branches.append(r)
            continue
        onward = dc_load(d, other, seen | {net})
        if onward is None:
            return None
        if onward != float("inf"):
            branches.append(r + onward)
    return 1 / sum(1 / x for x in branches) if branches else float("inf")


def stable_gains(d):
    """REQ.value/gain: an op-amp channel whose closed-loop gain – 1 + Rf / Rg from its feedback resistors, a follower
    1 – is below the part's minimum stable gain (values gain_min_ratio)."""
    from ..sim.netlist import OPAMP_ROLE
    out = []
    for des in sorted(d.comps):
        part = d.part(des) or {}
        least = values(part).get("gain_min_ratio")
        if not is_number(least):
            continue
        chans = defaultdict(dict)
        for num, info in (part.get("pins") or {}).items():
            m = OPAMP_ROLE.match(str(info.get("role") or ""))
            if m and (net := d.pin_net.get(f"{des}.{num}")):
                chans[(m.group(2) or "")[1:]][m.group(1)] = net
        for ch, n in sorted(chans.items()):
            if not {"in_n", "out"} <= set(n):
                continue
            if n["in_n"] == n["out"]:
                gain = 1.0
            else:
                rf = [x for _, x, _ in resistors_to(d, n["in_n"], {n["out"]})]
                rg = [x for _, x, other in resistors_to(d, n["in_n"], set(d.nets) - {n["out"], n["in_n"]})]
                if not rf or not rg or not all(is_number(x) and x > 0 for x in rf + rg):
                    continue
                gain = 1 + (1 / sum(1 / x for x in rf)) / (1 / sum(1 / x for x in rg))
            if gain < least:
                who = f"{des}{' channel ' + ch if ch else ''}"
                out.append(Finding("REQ.value", "G", des, f"{who}: closed-loop gain {gain:.3g} – the part is stable from "
                                   f"{least:g}", f"gain_min_ratio of {d.entry_key(des)}",
                                   "more gain, or a part stable at unity gain", grade="gain", on=(("component", des),)))
    return out


def usb_data(d):
    """REQ.missing/usb_data: a USB-C receptacle whose D+ or D− is used joins both rows – A6 with B6 (roles dp_a, dp_b),
    A7 with B7 (dn_a, dn_b) – or a plug turned round has no data."""
    out = []
    for des in sorted(d.comps_of_kind("connector")):
        nets = {r: d.net_of(des, r) for r in ("dp_a", "dp_b", "dn_a", "dn_b")}
        if not any(nets.values()):
            continue
        for a, b, what in (("dp_a", "dp_b", "D+"), ("dn_a", "dn_b", "D−")):
            if nets[a] != nets[b]:
                out.append(Finding("REQ.missing", "G", des, f"{des}: {what} of both rows not joined ({a} on "
                                   f"{nets[a] or 'nothing'}, {b} on {nets[b] or 'nothing'}) – turned round, the plug has "
                                   "no data", "USB Type-C Cable and Connector Specification (USB-IF)",
                                   "join A6 with B6 and A7 with B7", grade="usb_data", topic="usb_data",
                                   on=(("component", des),)))
    return out


def leaving(d):
    """[(net, how it leaves)] of the nets that leave the board: through a cable of the graph, or on a connector the
    graph marks off_board (its wires go to the world, not to another board of the project) – each net once."""
    out = {}
    for c in d.graph.get("cables", []):
        for a in c.get("pins", {}):
            if net := d.pin_net.get(f"{c['from']}.{a}"):
                out.setdefault(net, f"through cable {c['name']}")
    for des, comp in sorted(d.comps.items()):
        if comp.get("off_board"):
            for num in comp.get("pins", {}):
                if net := d.pin_net.get(f"{des}.{num}"):
                    out.setdefault(net, f"to the off-board connector {des}")
    return list(out.items())


def leaving_lines(d):
    """REQ.missing/leave: a signal net that leaves the board – through a cable, or on a connector marked off_board –
    reaches an IC or module pin with no resistor in between: a short on the wire or a discharge at its end hits the
    pin. A pin with short_proof, and I2C lines (needs.toml [i2c]), are left alone."""
    quiet = {d.ground} | supply_nets(d)
    out = []
    for net, how in leaving(d):
        if net in quiet or d.nets[net].get("bus") == "i2c" or i2c_name(net):
            continue
        hit = [r for r in d.nets[net]["pins"] if (d.part(r.partition(".")[0]) or {}).get("kind") in ("ic", "module")
               and d.pin_info(r).get("type") in ("input", "output", "bidirectional", "analog")
               and not d.pin_info(r).get("short_proof") and not i2c_line(d.pin_info(r))]
        if hit:
            out.append(Finding("REQ.missing", "G", net, f"{net}: runs {how} straight to {', '.join(hit)} – no series "
                               "resistance on the board", "maker-coverage CK-16",
                               "a series resistor (100 Ω–1 kΩ) at the pin, a TVS at the connector", grade="leave",
                               topic="leave", on=(("net", net),)))
    return out


def matrix(d):
    """REQ.missing/matrix, REQ.forbidden/matrix: in a key matrix (nets with matrix row or col) every switch reaches
    the other side through a diode, and all diodes point the same way."""
    side = {name: net.get("matrix") for name, net in d.nets.items() if net.get("matrix") in ("row", "col")}
    if not side:
        return []
    out, ways = [], defaultdict(list)
    for des in sorted(d.comps_of_kind("button", "switch")):
        nets = {d.pin_net.get(f"{des}.{p}") for p in d.part(des)["pins"]} - {None}
        on = [n for n in nets if n in side]
        if not on:
            continue
        other = (nets - set(on)) or set()
        if len({side[n] for n in on}) > 1:
            out.append(Finding("REQ.missing", "G", des, f"{des}: joins a row and a column without a diode – keys pressed "
                               "together ghost", "QMK how_a_matrix_works (maker-coverage CK-19)", "a diode per key",
                               grade="matrix", on=(("component", des),)))
            continue
        found = None
        for dio in d.comps_of_kind("diode"):
            a, k = d.net_of(dio, "anode"), d.net_of(dio, "cathode")
            for here, there, at in ((a, k, "cathode"), (k, a, "anode")):
                if here in other and there in side and side[there] != side[on[0]]:
                    found = (dio, side[there] if at == "cathode" else side[on[0]])
        if found is None:
            out.append(Finding("REQ.missing", "G", des, f"{des}: no diode to the {'col' if side[on[0]] == 'row' else 'row'}"
                               " side – keys pressed together ghost", "QMK how_a_matrix_works (maker-coverage CK-19)",
                               "a diode per key", grade="matrix", on=(("component", des),)))
        else:
            ways[found[1]].append(des)        # the side the cathodes face: row for col2row
    if len(ways) > 1:
        text = "; ".join(f"cathodes to the {w}s: {', '.join(keys)}" for w, keys in sorted(ways.items()))
        out.append(Finding("REQ.forbidden", "G", "matrix", f"matrix: the diodes point both ways – {text}",
                           "QMK config_options DIODE_DIRECTION (maker-coverage CK-19)",
                           "all diodes the same way, as the firmware's diode direction says", grade="matrix"))
    return out


# --- differential buses (maker-coverage CK-17) ----------------------------------------------------------------------
BUS_ROLES = {"rs485": ("rs485_a", "rs485_b"), "can": ("canh", "canl")}    # a and b alone are a switch's pins


def buses(d):
    """{(kind, net a, net b): [transceivers]} – the pairs of nets the transceivers' bus pins (roles rs485_a/rs485_b,
    canh/canl)
    sit on; a pair across boards is one pair, its cable wires join the nets."""
    out = defaultdict(list)
    for des in d.comps:
        pins = (d.part(des) or {}).get("pins") or {}
        for kind, (ra, rb) in BUS_ROLES.items():
            na = next((d.pin_net.get(f"{des}.{n}") for n, p in pins.items() if p.get("role") == ra), None)
            nb = next((d.pin_net.get(f"{des}.{n}") for n, p in pins.items() if p.get("role") == rb), None)
            if na and nb:
                out[(kind, na, nb)].append(des)
    return out


def bus_terminations(d):
    """REQ.missing/termination, REQ.forbidden/termination, REQ.value/termination: a differential bus has one
    termination at each end – two across the boards of the graph –, each of the cable's 120 Ω, directly across the pair
    or split (two resistors to a middle net); REQ.value/failsafe: an RS-485 bus with idle bias (a resistor from A to a
    supply, one from B to ground) holds at least 200 mV across the pair with the lowest supply (tables/buses.toml)."""
    from .. import catalog
    t = catalog.table("buses")
    gnd, supplies, out = d.ground, supply_nets(d), []
    for (kind, na, nb), who in sorted(buses(d).items()):
        want, src = t[kind]["termination_ohm"], f"catalog/tables/buses.toml [{kind}]"
        place, on = f"{na}/{nb}", (("net", na), ("net", nb))
        # a termination behind a switch or jumper (a switchable one) counts closed: the switch's nets are its ends
        ends_a, ends_b = closed(d, na), closed(d, nb)
        terms = [(des, r) for x in ends_a for des, r, _ in resistors_to(d, x, ends_b)]
        via_a = {other: (des, r) for x in ends_a
                 for des, r, other in resistors_to(d, x, set(d.nets) - ends_a - ends_b - {gnd} - supplies)}
        for x in ends_b:
            for des_b, r_b, mid in resistors_to(d, x, set(via_a)):
                des_a, r_a = via_a[mid]
                terms.append((f"{des_a}+{des_b}", (r_a + r_b) if is_number(r_a) and is_number(r_b) else None))
        terms = list(dict.fromkeys(terms))
        bus = f"{'RS-485' if kind == 'rs485' else 'CAN'} bus {place} ({', '.join(sorted(who))})"
        if len(terms) < 2:
            out.append(Finding("REQ.missing", "G", place, f"{bus}: {len(terms)} termination(s) in the graph, a bus has one "
                               f"at each end of its cable – {want:g} Ω each", src, f"{want:g} Ω across the pair at the "
                               "board at each end of the bus, or accept naming where the other end is terminated",
                               grade="termination", on=on))
        elif len(terms) > 2:
            out.append(Finding("REQ.forbidden", "G", place, f"{bus}: {len(terms)} terminations "
                               f"({', '.join(des for des, _ in terms)}) – only the two ends of the cable are terminated",
                               src, "keep the terminations at the two ends of the bus, take the others out (or make "
                               "them switchable)", grade="termination", on=on))
        for des, r in terms:
            if is_number(r) and abs(r - want) > 0.01 * want:
                out.append(Finding("REQ.value", "G", place, f"{bus}: termination {des} is {ohm(r)}, the cable's "
                                   f"impedance is {want:g} Ω", src, f"{want:g} Ω", grade="termination", on=on))
        if kind == "rs485":
            out += failsafe_bias(d, bus, place, on, na, nb, [r for des, r in terms if "+" not in des and is_number(r)],
                                 t["rs485"]["idle_min_v"], src, want, who)
    return out


SWITCH_KINDS = ("switch", "dip_switch", "jumper")


def closed(d, net):
    """The net and every net a switch or jumper joins it to when closed."""
    out = {net}
    for des in d.comps_of_kind(*SWITCH_KINDS):
        nets = {d.pin_net.get(f"{des}.{n}") for n in (d.part(des) or {}).get("pins") or {}} - {None}
        if net in nets:
            out |= nets - {d.ground}
    return out


def failsafe_bias(d, bus, place, on, na, nb, direct, need_v, src, want=120.0, who=()):
    """REQ.value/failsafe: the idle voltage a bias pair (A to a supply, B to ground) sets across the terminations – at
    the supply's lowest voltage while it is on, with the far end's termination assumed where the graph holds one end
    only."""
    supplies = supply_nets(d)
    ups = [(des, r, other) for des, r, other in resistors_to(d, na, supplies) if is_number(r)]
    downs = [(des, r) for des, r, _ in resistors_to(d, nb, {d.ground}) if is_number(r)]
    if not ups or not downs:
        return []
    lo = min(lowest_on(d, other, who) for _, _, other in ups)
    r_up, r_down = min(r for _, r, _ in ups), min(r for _, r in downs)
    assumed = len(direct) < 2                      # one end in the graph: the other end's termination is assumed
    loads = list(direct) + ([want] * (2 - len(direct)) if assumed else [])
    req = 1 / sum(1 / r for r in loads)
    vab = lo * req / (r_up + r_down + req)
    if vab >= need_v:
        return []
    far = f", the far end's {want:g} Ω assumed" if assumed and direct else (
        f", both ends' {want:g} Ω assumed" if assumed else "")
    return [Finding("REQ.value", "G", place, f"{bus}: idle bias {ups[0][0]}/{downs[0][0]} holds {vab * 1e3:.0f} mV "
                    f"across the pair at {lo:g} V with the terminations{far}, below the {need_v * 1e3:.0f} mV a "
                    "receiver detects", src, "smaller bias resistors (SLLA272: VAB = 200 mV + the noise), or "
                    "transceivers with built-in failsafe and no bias", grade="failsafe", on=on)]


def lowest_on(d, net, who=()):
    """The lowest voltage a supply net has while it is on: the floor of its declared range where that is above 0 V;
    where the range starts at 0 V (a rail that is off as well), the lowest supply the transceivers on the bus operate
    at (vdd_op_min_v, or a supply pin's v_op_min_v); without either, the top of the range."""
    v = v_range(d.nets[net])
    if v[0] > 0:
        return v[0]
    mins = []
    for des in who:
        part = d.part(des) or {}
        lim = (part.get("limits") or {}).get("vdd_op_min_v")
        mins += [lim] if is_number(lim) else []
        mins += [p["v_op_min_v"] for n, p in (part.get("pins") or {}).items()
                 if p.get("type") == "power_in" and d.pin_net.get(f"{des}.{n}") == net and is_number(p.get("v_op_min_v"))]
    return min(mins) if mins else v[1]


PD_CFG_ROLES = ("cfg1", "cfg2", "cfg3")


def pd_levels(d, des):
    """The level each configuration pin of a PD sink sets – "0" on ground, "1" on a supply net or one resistor from
    one, "?" otherwise (an MCU pin the firmware sets, a pin that floats: both levels possible)."""
    supplies, out = supply_nets(d), []
    for role in PD_CFG_ROLES:
        net = d.net_of(des, role)
        if net is None:
            out.append("?")
        elif net == d.ground:
            out.append("0")
        elif net in supplies or resistors_to(d, net, supplies - {net}):
            out.append("1")
        elif resistors_to(d, net, {d.ground}):
            out.append("0")
        else:
            out.append("?")
    return "".join(out)


def pd_requests(d):
    """REQ.value/pd_request (decision of 2026-10-31, schema W5): a USB PD sink (behaviour pd_sink) requests the
    voltage its configuration pins select (values pd_request_v: a table of CFG1 CFG2 CFG3 levels, "x" for either, to
    volts – CH224K table 6.2); every voltage the levels on the board can select lies within the declared range of the
    VBUS net its sense pin (role vbus_sense) reaches through its series resistor – else the parts on VBUS are judged
    against a range the charger will exceed."""
    out = []
    for des in sorted(d.comps):
        part = d.part(des) or {}
        p = values(part)
        table = p.get("pd_request_v")
        if p.get("behavior") != "pd_sink" or not isinstance(table, dict):
            continue
        levels = pd_levels(d, des)
        chosen = sorted({v for pattern, v in table.items()
                         if len(pattern) == len(levels) and all(a in ("x", b) or b == "?" for a, b in zip(pattern, levels))})
        sense = d.net_of(des, "vbus_sense")
        if not chosen or sense is None:
            continue
        vbus = {other for _, _, other in resistors_to(d, sense, set(d.nets) - {sense})} or {sense}
        for net in sorted(vbus):
            top = v_range(d.nets[net])[1]
            if max(chosen) > top + 1e-9:
                out.append(Finding("REQ.value", "G", des, f"{des}: requests up to {max(chosen):g} V by its CFG pins "
                                   f"(CFG1 CFG2 CFG3 = {levels}, ? either level; it may select "
                                   f"{', '.join(f'{x:g}' for x in chosen)} V) – {net} is declared up to {top:g} V",
                                   f"pd_request_v of {d.entry_key(des)}", "declare the VBUS net over every voltage the "
                                   "pins can request (and rate its parts for it), or fix the CFG pins to the voltage meant",
                                   grade="pd_request", on=(("component", des),)))
    return out

