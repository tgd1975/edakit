"""HINT: patterns that need judgement, as notes (concept rules-at-scale.md, section 2). A hint has no rule a program
could decide; it says what to consider where a kind of part or a pattern is in the graph. Each code HINT.* names in
catalog/codes.toml when it applies – `when` with the kinds of parts, or a matcher of MATCHERS below; each place it
applies to is one finding, severity note unless a domain says otherwise. What is taken care of is accepted in the
graph: "accept": {"HINT.bulk": "C1 1000 µF next to J1"} for every place, "HINT.bulk J1" for one.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from .. import catalog
from ..circuit import values
from ..design import natural_key
from ..findings import Finding

SIGNAL_TYPES = {"input", "output", "bidirectional", "analog"}


def reversible(design):
    """Sources that may be reversed: "source": "reversible" on a component, checks.reverse_protect of before."""
    marked = {des for des, c in design.comps.items() if c.get("source") == "reversible"}
    return marked | set((design.graph.get("checks") or {}).get("reverse_protect") or [])


def _part_kind(design, des):
    return (design.part(des) or {}).get("kind")


def _power_inputs(design, cfg, sim):
    """Where the supply comes in: battery holders, connectors with a vbus pin, checks.reverse_protect, sim sources."""
    found = set(design.comps_of_kind("battery_holder"))
    found |= reversible(design)
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


def _protected(design, net):
    """A net an ESD device guards: a pin of a part whose entry says it is one (values tvs – a TVS diode or an ESD
    array) on the net or one resistor away."""
    return any(values(design.part(r.split(".", 1)[0]) or {}).get("tvs")
               for n in {net} | _resistor_neighbours(design, net) for r in design.nets[n]["pins"])


def _connector_signals(design, cfg, sim):
    """Connectors with a signal line to an IC or module pin, directly or through one resistor (ground and supply
    nets are no signal lines) – not where every such line has its ESD device."""
    quiet = {design.ground} | {name for name, net in design.nets.items()
                               if any(design.pin_info(r).get("type") in ("power_in", "power_output", "ground")
                                      for r in net["pins"])}
    found = []
    for des in design.comps_of_kind("connector"):
        lines = []
        for num in design.part(des)["pins"]:
            net = design.pin_net.get(f"{des}.{num}")
            if net is None or net in quiet:
                continue
            nets = ({net} | _resistor_neighbours(design, net)) - quiet
            if any(design.pin_info(r).get("type") in SIGNAL_TYPES and _part_kind(design, r.split(".", 1)[0]) in
                   ("ic", "module") for n in nets for r in design.nets[n]["pins"]):
                lines.append(net)
        if lines and not all(_protected(design, n) for n in lines):
            found.append(des)
    return found


def _driven_gates(design, cfg, sim):
    """MOSFETs whose gate a signal drives: not a gate on a supply rail or ground (a level shifter's gate sits on its
    low-side supply, it never switches)."""
    from ..circuit import supply_nets
    rails = supply_nets(design) | {design.ground}
    return [des for des in design.comps_of_kind("nmos", "pmos")
            if (g := design.net_of(des, "gate")) is not None and g not in rails]


def _read_switches(design, cfg, sim):
    """Buttons and switches an MCU pin reads – a pin of theirs on an MCU pin's net or one resistor away; a switch no
    firmware reads (a DIP switch that closes a termination) bounces unseen."""
    out = []
    for des in design.comps_of_kind("button", "switch", "dip_switch"):
        nets = {design.pin_net.get(f"{des}.{n}") for n in (design.part(des) or {}).get("pins") or {}} - {None,
                                                                                                        design.ground}
        if any(_mcu_pins(design, n) for n in nets):
            out.append(des)
    return out


def _unprotected_cells(design, cfg, sim):
    """Battery holders whose cell no protection IC guards – recognised as a MOSFET in the cell's minus whose gate a
    protection IC's od or oc output drives (DW01A with FS8205A)."""
    guards = {design.pin_net.get(r) for r, info in ((r, design.pin_info(r)) for r in design.pin_net)
              if info.get("role") in ("od", "oc") and info.get("type") == "output"} - {None}
    out = []
    for des in design.comps_of_kind("battery_holder"):
        minus = {design.pin_net.get(f"{des}.{n}") for n, p in (design.part(des) or {}).get("pins", {}).items()
                 if str(p.get("role") or "").startswith("minus")} - {None}
        guarded = any(design.net_of(q, "gate") in guards and minus & {design.net_of(q, "source"), design.net_of(q, "drain")}
                      for q in design.comps_of_kind("nmos"))
        if not guarded:
            out.append(des)
    return out


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
            if values(design.part(d)).get("behavior") in ("buck", "boost", "buck_boost")]
    return regs + design.comps_of_kind("inductor")


def _supply_starts(design, cfg, sim):
    """{supply: nets it feeds directly}: the power inputs of HINT.bulk by their supply pins – the plus of a battery holder,
    the vbus pins of a connector, the pins of a connector in checks.reverse_protect, the plus of a sim source – and a
    module's pin of type power_output with the role vbus (its USB VBUS brought out). Ground is no supply net."""
    protect = reversible(design)
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


def _mcu_pins(design, net):
    """MCU pins (role gpio) on a net or one resistor away from it."""
    return [r for n in {net} | _resistor_neighbours(design, net) for r in design.nets[n]["pins"]
            if design.pin_info(r).get("role") == "gpio"]


def _output_timing(info):
    """' (changes 12–30 ns after the rising clock edge)' from a pin's out_edge and t_pd_ns ([min, max] in ns, null where
    the datasheet gives none); '' without either."""
    edge, tpd = info.get("out_edge"), info.get("t_pd_ns")
    lo, hi = (tpd if isinstance(tpd, list) and len(tpd) == 2 else [tpd, tpd] if isinstance(tpd, (int, float))
              else [None, None])
    delay = (f"{lo:g} ns" if lo == hi and lo is not None else f"{lo:g}–{hi:g} ns" if lo is not None and hi is not None
             else f"≥ {lo:g} ns" if lo is not None else f"≤ {hi:g} ns" if hi is not None else "")
    if not edge and not delay:
        return ""
    return f" (changes {delay + ' ' if delay else ''}after the {edge + ' ' if edge else ''}clock edge)"


def _read_backs(design, cfg, sim):
    """A serial output read back by an MCU: an `output` pin of a part without MCU pins, on a net with an MCU pin (role
    gpio; directly or through one resistor), of a part that MCU also drives an `input` of – its clock among them. The
    pin's out_edge and t_pd_ns go with it where the parts entry gives them."""
    found = []
    for des in design.comps:
        pins = (design.part(des) or {}).get("pins") or {}
        if any(i.get("role") == "gpio" for i in pins.values()):
            continue
        nets = {num: net for num in pins if (net := design.pin_net.get(f"{des}.{num}"))}
        driving = {r.split(".", 1)[0] for num, net in nets.items() if pins[num].get("type") == "input"
                   for r in _mcu_pins(design, net)}
        for num, net in nets.items():
            if pins[num].get("type") != "output":
                continue
            for ref in _mcu_pins(design, net):
                if ref.split(".", 1)[0] in driving:
                    found.append(f"{des} {pins[num].get('name', num)} to {ref.split('.', 1)[0]} "
                                 f"{design.pin_info(ref).get('name', ref)}{_output_timing(pins[num])}")
    return found


CERAMIC_CLASS2 = ("X5R", "X7R", "X7S", "X6S", "Y5V")


def _analog_nets(design):
    """Nets with an analog pin: the audio path, as far as the entries say."""
    return {name for name, net in design.nets.items() if any(design.pin_info(r).get("type") == "analog"
                                                             for r in net["pins"])}


def _audio_board(design):
    return bool(design.comps_of_kind("speaker") or _analog_nets(design))


def _btl_outputs(design, cfg, sim):
    """Bridge-tied outputs (roles out_p, out_n) that reach a connector – a filterless class-D output on a cable."""
    found = []
    for des in design.comps:
        for num, info in ((design.part(des) or {}).get("pins") or {}).items():
            role = str(info.get("role") or "")
            net = design.pin_net.get(f"{des}.{num}")
            if net and (role.startswith("out_p") or role.startswith("out_n")) and any(
                    _part_kind(design, r.split(".", 1)[0]) == "connector" for r in design.nets[net]["pins"]):
                found.append(des)
    return found


def _switching_near_audio(design, cfg, sim):
    """A switching regulator, a charge pump or a PWM net on a board with an audio path."""
    if not _audio_board(design):
        return []
    found = _switching_regulators(design, cfg, sim)
    found += [name for name, net in design.nets.items() if net.get("pwm_hz") is not None]
    return found


def _ceramics_in_signal_path(design, cfg, sim):
    """A class-2 ceramic (X5R, X7R, Y5V …) on a net with an analog pin – it distorts a signal."""
    analog = _analog_nets(design)
    return [des for des in design.comps_of_kind("capacitor")
            if values(design.part(des)).get("dielectric") in CERAMIC_CLASS2
            and any(design.pin_net.get(f"{des}.{p}") in analog for p in design.part(des)["pins"])]


def _instrument_inputs(design, cfg, sim):
    """Nets an instrument comes in on (instrument: pickup or piezo)."""
    return [name for name, net in design.nets.items() if net.get("instrument")]


def _pedal_power_inputs(design, cfg, sim):
    """The power inputs of a board with an instrument input."""
    return _power_inputs(design, cfg, sim) if _instrument_inputs(design, cfg, sim) else []


def _battery_on_a_board_with_jacks(design, cfg, sim):
    """A battery holder on a board with an instrument input – the jack's ring is the usual switch."""
    return list(design.comps_of_kind("battery_holder")) if _instrument_inputs(design, cfg, sim) else []


def _pwm_leds(design, cfg, sim):
    """Nets with pwm_hz that light LEDs: an LED on the net, one resistor away, or behind a transistor it switches."""
    found = []
    for name, net in design.nets.items():
        if net.get("pwm_hz") is None:
            continue
        near = {name} | _resistor_neighbours(design, name)
        for q in design.comps_of_kind("npn", "pnp", "nmos", "pmos"):
            if design.net_of(q, "base") in near or design.net_of(q, "gate") in near:
                near |= {design.net_of(q, "collector"), design.net_of(q, "drain")} - {None}
        near |= {x for n in list(near) for x in _resistor_neighbours(design, n)}
        if any(_part_kind(design, r.split(".", 1)[0]) in ("led", "led_rgb") for n in near if n in design.nets
               for r in design.nets[n]["pins"]):
            found.append(name)
    return found


def _boost_enable_on_gpio(design, cfg, sim):
    """A boost converter whose enable (role en) an MCU pin drives."""
    return [des for des in design.comps if values(design.part(des)).get("behavior") == "boost"
            and (net := design.net_of(des, "en")) and _mcu_pins(design, net)]


def _unmarked_power_inputs(design, cfg, sim):
    """Battery holders and supply connectors the graph does not mark as reversible – nothing checks their polarity."""
    marked = reversible(design)
    return [des for des in design.comps_of_kind("battery_holder", "connector") if des not in marked and (
        _part_kind(design, des) == "battery_holder"
        or "vbus" in {p.get("role") for p in design.part(des)["pins"].values()})]


def _rated_by_copper(design, cfg, sim):
    """Parts whose temperature rests on rth_ja_k_per_w – a figure for the datasheet's copper."""
    return [des for des in design.comps if "rth_ja_k_per_w" in ((design.part(des) or {}).get("limits") or {})]


def _cable_lines(design, cfg, sim):
    """Signal nets that leave the board – through a cable of the graph, or on a connector marked off_board: not
    ground, not a supply."""
    from .requires import leaving
    quiet = {design.ground} | {name for name, net in design.nets.items()
                               if any(design.pin_info(r).get("type") in ("power_in", "power_output", "ground")
                                      for r in net["pins"])}
    return sorted({net for net, _ in leaving(design) if net not in quiet})


JACK_ROLES = {"tip", "ring", "sleeve", "tip_switch", "ring_switch", "sleeve_switch"}   # roles of a jack's contacts


def _jacks_with_supply(design, cfg, sim):
    """Jacks (connectors with tip, ring or sleeve contacts) where a contact carries a supply – the sleeve too when it
    is not ground."""
    from ..circuit import supply_nets
    supplies = supply_nets(design)
    found = []
    for des in design.comps_of_kind("connector"):
        roles = {num: p.get("role") for num, p in design.part(des)["pins"].items()}
        if not JACK_ROLES & set(roles.values()):
            continue
        if any(role in JACK_ROLES and design.pin_net.get(f"{des}.{num}") in supplies for num, role in roles.items()):
            found.append(des)
    return found


def _relays_switching_off_board(design, cfg, sim):
    """Relays whose contacts (common, no, nc) reach a connector or run through a cable – the load is off the board."""
    leaving = {design.pin_net.get(f"{c['from']}.{a}") for c in design.graph.get("cables", []) for a in c.get("pins", {})}
    leaving |= {design.pin_net.get(f"{d}.{num}") for d in design.comps_of_kind("connector")
                for num in design.part(d)["pins"]}
    leaving -= {None, design.ground}
    return [des for des in design.comps_of_kind("relay")
            if any(p.get("role") in ("common", "no", "nc") and design.pin_net.get(f"{des}.{num}") in leaving
                   for num, p in design.part(des)["pins"].items())]


USB_ROLES = {"cc1", "cc2", "dp", "dn", "dp_a", "dp_b", "dn_a", "dn_b"}


def _usb_ports(design, cfg=None, sim=None):
    """USB receptacles of the board: a connector with a connected vbus pin and a CC or data pin of USB."""
    out = []
    for des in design.comps_of_kind("connector"):
        pins = (design.part(des) or {}).get("pins") or {}
        roles = {p.get("role") for p in pins.values()}
        if roles & USB_ROLES and any(p.get("role") == "vbus" and design.pin_net.get(f"{des}.{num}")
                                     for num, p in pins.items()):
            out.append(des)
    return out


def vbus_capacitance(design, des):
    """(net, farads) – the capacitance directly on a USB port's VBUS net, from the capacitors' value_f."""
    pins = (design.part(des) or {}).get("pins") or {}
    net = next((design.pin_net.get(f"{des}.{num}") for num, p in pins.items()
                if p.get("role") == "vbus" and design.pin_net.get(f"{des}.{num}")), None)
    total = 0.0
    for c in design.comps_of_kind("capacitor"):
        if net in {n for r, n in design.pin_net.items() if r.split(".", 1)[0] == c}:
            total += values(design.part(c)).get("value_f") or 0
    return net, total


def _usb_attach_capacitance(design, cfg=None, sim=None):
    """USB ports whose VBUS net carries more capacitance than a device may show at attach (tables/usb.toml)."""
    limit = catalog.table("usb")["attach"]["c_max_f"]
    return [des for des in _usb_ports(design) if vbus_capacitance(design, des)[1] > limit * (1 + 1e-9)]


MATCHERS = {"power_input": _power_inputs, "connector_signal": _connector_signals,
            "transistor_at_connector": _transistors_at_connectors, "switching_regulator": _switching_regulators,
            "two_supplies": _two_supplies, "read_back": _read_backs, "btl_output": _btl_outputs,
            "switching_near_audio": _switching_near_audio, "ceramic_in_signal_path": _ceramics_in_signal_path,
            "instrument_input": _instrument_inputs, "battery_with_jacks": _battery_on_a_board_with_jacks,
            "pedal_power_input": _pedal_power_inputs, "pwm_leds": _pwm_leds, "boost_enable": _boost_enable_on_gpio,
            "unmarked_power_input": _unmarked_power_inputs, "rated_by_copper": _rated_by_copper,
            "cable_line": _cable_lines, "jack_supply": _jacks_with_supply,
            "relay_off_board": _relays_switching_off_board, "usb_port": _usb_ports,
            "usb_attach_capacitance": _usb_attach_capacitance, "driven_gate": _driven_gates,
            "read_switch": _read_switches, "unprotected_cell": _unprotected_cells}



def matching(design, cfg=None, sim=None, applied=None):
    """{code: [places]} of every hint whose `when` fits the graph – of those `applied` names (a profile's hints)
    where given."""
    out = {}
    for name, e in catalog.codes().items():
        w = e.get("when")
        if not w or (applied is not None and name not in applied):
            continue
        hits = list(design.comps_of_kind(*w.get("kinds", [])))
        if "match" in w:
            hits += MATCHERS[w["match"]](design, cfg, sim)
        if hits:
            out[name] = sorted(set(hits), key=natural_key)
    return out


def part_notes(design):
    """(place, note) from the parts entries: the part's `hints` at its designators, a pin's `hint` at its connected
    pins."""
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


def run(ctx):
    found = [Finding(code, "G", place, catalog.title(code), on=(("component", place),) if place in ctx.design.comps
                     else ())
             for code, places in matching(ctx.design, ctx.cfg, ctx.sim, ctx.profile.hints if ctx.profile else None
                                          ).items() for place in places]
    return found + [Finding("HINT.datasheet", "P", place, note, "the parts entry") for place, note in
                    part_notes(ctx.design)]
