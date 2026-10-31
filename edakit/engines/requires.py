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
            + balancing(d) + addresses(d) + uart_lines(d) + adc_sources(d))


def decoupling(d):
    """REQ.missing: per supply pin on a net a capacitor from that net to ground."""
    n = needs()["decoupling"]
    gnd, caps = d.ground, Counter()
    for des in d.comps_of_kind("capacitor"):
        a, b = d.pin_net.get(f"{des}.1"), d.pin_net.get(f"{des}.2")
        if gnd in (a, b):
            caps[b if a == gnd else a] += 1
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
    """REQ.missing: a coil a transistor or an output switches has a diode across it, cathode at its plus."""
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
                     if d.pin_info(r).get("type") in ("output", "bidirectional")]
        if switches and not any(d.net_of(x, "cathode") == plus and d.net_of(x, "anode") == minus
                                for x in d.comps_of_kind("diode")):
            out.append(Finding("REQ.missing", "G", des, f"{des}: coil switched by {', '.join(switches)} without a diode "
                               f"across it (cathode at {plus}, anode at {minus})", n["source"],
                               "a diode directly across the coil", on=(("component", des),)))
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


def functions(d):
    """REQ.function: the pin of a net with fn has that function, the nets of one fn_bus one peripheral instance per
    part, PWM nets of one slice one fixed pwm_hz and a channel each. A pin without functions: PARTS.fact/functions; a
    net's fn or pwm_hz of the wrong form: STRUCT.net."""
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
        known = [(r, d.pin_info(r)) for r in net["pins"] if isinstance(d.pin_info(r).get("functions"), list)]
        if not known:
            out.append(Finding("PARTS.fact", "G", name, f"{name}: needs {fn}, but no pin on it has functions in its parts "
                               "entry – not checked", grade="functions", on=on))
            continue
        hits[name] = [(r, *m) for r, info in known for f in info["functions"] if (m := fn_match(fn, f))]
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
        if len(nets) > 1 and not set.intersection(*map(set, nets.values())):
            where = ", ".join(f"{n} on " + "/".join(f"{kind}{i}" for i in sorted(inst)) + " ("
                              + ", ".join(inst[i] for i in sorted(inst)) + ")" for n, inst in sorted(nets.items()))
            out.append(Finding("REQ.function", "G", f"bus {bus}", f"bus {bus}: {where} – the nets of one bus need one {kind} of "
                               f"{des}", on=tuple(("net", n) for n in sorted(nets))))
    slices = defaultdict(list)
    for name, pins in hits.items():
        if d.nets[name]["fn"] == "pwm":
            for ref, inst, channel in pins:
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



def pin_needs_problems(need):
    """What is wrong with one entry of a pin's needs: a known `what`, its window as numbers, min ≤ max."""
    n = needs()["pin"]
    if not isinstance(need, dict) or need.get("what") not in n["what"]:
        return [f"needs {need!r}: what must be one of {', '.join(n['what'])}"]
    window = n["windows"].get(need["what"], [])
    out = [f"needs {need['what']}: unknown key '{k}'" for k in sorted(set(need) - {"what", "source", "why", *window})]
    lo, hi = (need.get(k) for k in window) if window else (None, None)
    out += [f"needs {need['what']}: {k} must be a number" for k in window if k in need and not is_number(need[k])]
    if is_number(lo) and is_number(hi) and lo > hi:
        out.append(f"needs {need['what']}: {window[0]} above {window[1]}")
    return out


def pin_needs(d):
    """REQ.missing/pin, REQ.value/pin, REQ.forbidden/pin: what a pin's parts entry says it needs – a capacitor to
    ground, a pull-up to a supply or a pull-down to ground, a series resistor, each in its window; to be on ground, or
    never on it. A needs entry of the wrong form: PARTS.schema."""
    n = needs()["pin"]
    grounds = {d.ground} | set(d.graph.get("grounds") or [])
    supplies = supply_nets(d) - grounds
    caps = defaultdict(list)            # net -> [(capacitor, value)] of the capacitors to ground
    for des in d.comps_of_kind("capacitor"):
        a, b = (d.pin_net.get(f"{des}.{p}") for p in d.part(des)["pins"])
        for here, there in ((a, b), (b, a)):
            if there in grounds and here and here not in grounds:
                caps[here].append((des, values(d.part(des)).get("value_f")))
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
            for need in pin_needs_list:
                problems = pin_needs_problems(need)
                if problems:
                    if (key, num) not in seen:
                        out += [Finding("PARTS.schema", "P", key, f"{key}: pin {num} {p}") for p in problems]
                    continue
                what, src = need["what"], need.get("source") or n["source"]
                lo, hi = (need.get(k) for k in n["windows"].get(what, ["", ""]))

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
                unit = "F" if what == "capacitor" else "Ω"
                window = (f" of {si(lo, unit)} … {si(hi, unit)}" if lo is not None and hi is not None else
                          f" of at least {si(lo, unit)}" if lo is not None else
                          f" of at most {si(hi, unit)}" if hi is not None else "")
                if net is None:
                    finding("REQ.missing", f"not connected – needs a {what.replace('_', ' ')}{window}")
                    continue
                if what == "capacitor":
                    found = caps.get(net, [])
                    total = sum(x for _, x in found if is_number(x)) if all(is_number(x) for _, x in found) else None
                    names, there = ", ".join(c for c, _ in found), f"to {d.ground}"
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


def addresses(d):
    """REQ.forbidden/address: two devices on one bus at the same address. An entry's address gives its base, the pins
    that add to it when high ({pin: value}) and further addresses it answers to (also); the bus is the net of its pin
    `on`, by default the pin with the role sda. A pin whose level the graph does not decide leaves the device out."""
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
        if not (isinstance(a, dict) and isinstance(a.get("base"), int) and isinstance(a.get("pins", {}), dict)
                and all(str(p) in pins and isinstance(v, int) for p, v in a.get("pins", {}).items())
                and all(isinstance(x, int) for x in a.get("also", []))):
            out.append(Finding("PARTS.schema", "P", key, f"{key}: address must be {{base, pins: {{pin: value}}, also: "
                               f"[…], on: pin}} with integers, not {a!r}", grade="address"))
            continue
        on = a.get("on") or next((n for n, i in pins.items() if i.get("role") == "sda"), None)
        bus = d.pin_net.get(f"{des}.{on}") if on else None
        if bus is None:
            continue
        value, how = a["base"], []
        for num, add in sorted(a.get("pins", {}).items()):
            level = pin_level(d, f"{des}.{num}", pins[str(num)], supplies, grounds)
            if level is None:
                value = None
                break
            value += add if level == "high" else 0
            how.append(f"{pins[str(num)].get('name', num)} {level}")
        if value is None:
            continue
        for x in [value, *a.get("also", [])]:
            buses[bus].append((x, des, ", ".join(how) if x == value else "fixed"))
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
