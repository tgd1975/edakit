"""What went unchecked for lack of data (maker-coverage FT-19; concept rules-at-scale.md, section 8): a relation that
needs a datasheet value skips a part without it and reports nothing – LIM.v on a capacitor without v_max_v, LVL.threshold
on an input without thresholds. coverage() names every such gap, by code; `edakit check` prints one line, `edakit check
--coverage` the list, the gate protocol the list in its section 2. A gap is no finding: nothing is wrong that anybody
saw – nobody looked.

The same list names what the simulation does not model over time (rules-at-scale.md, decision 17): a part whose
behaviour is a charger, a cell's protection or a USB PD sink has states an operating point cannot show – the end of
charge, the release voltages and delays, the negotiation. Each is a gap of SIM.state, "not simulated", with the hint
that names the risk where the part is used.

And it names every cable without a current rating (maker-coverage FT-2; rules-at-scale.md, decision 22): a wire's
rating comes from the wire's own datasheet, `i_max_a` on the cable, and edakit derives none from the gauge. A cable
that carries current in the simulation without it is a gap of LIM.i, with its highest current and the loss per metre
of wire it causes – I² × R of the wire, a number and no verdict: the case nothing else sees is a wire that heats while
its voltage drop and its connectors pass. The currents come from the simulation edakit sim saved for this state (the
gate's own run); without one the cable is named with its current not known.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..circuit import is_number, limits, polarized, si, values, wire_mm2, wire_ohm_per_m
from ..findings import Finding

# a wire with less current carries only the solver's leakage – gmin 1e-12 S and rshunt 1e12 Ω give picoamperes per
# node: numerical zero, no judgement of the wire
CARRIES_A = 1e-9

# per kind: (code, the limits of which at least one must be given, what it guards)
LIMITS_OF = {
    "capacitor": [("LIM.v", ("v_max_v",), "its voltage")],
    "resistor": [("LIM.p", ("p_max_w",), "its power")],
    "potentiometer": [("LIM.p", ("p_max_w",), "its power")],
    "diode": [("LIM.v", ("vr_max_v",), "its reverse voltage"), ("LIM.i", ("if_max_a",), "its forward current")],
    "led": [("LIM.i", ("if_max_a",), "its forward current")],
    "led_rgb": [("LIM.i", ("if_max_a",), "its forward current")],
    "npn": [("LIM.v", ("vce_max_v",), "VCE"), ("LIM.i", ("ic_max_a",), "its collector current")],
    "pnp": [("LIM.v", ("vce_max_v",), "VCE"), ("LIM.i", ("ic_max_a",), "its collector current")],
    "nmos": [("LIM.v", ("vds_max_v",), "VDS"), ("LIM.v", ("vgs_max_v",), "VGS"),
             ("LIM.i", ("id_max_a",), "its drain current")],
    "pmos": [("LIM.v", ("vds_max_v",), "VDS"), ("LIM.v", ("vgs_max_v",), "VGS"),
             ("LIM.i", ("id_max_a",), "its drain current")],
    "njfet": [("LIM.v", ("vdg_max_v", "vds_max_v"), "its drain voltage")],
    "pjfet": [("LIM.v", ("vdg_max_v", "vds_max_v"), "its drain voltage")],
    "fuse": [("LIM.i", ("i_hold_a",), "what it lets pass")],
    "switch": [("LIM.i", ("i_max_a", "i_contact_max_a", "i_switch_max_a"), "its contact current")],
    "button": [("LIM.i", ("i_max_a", "i_contact_max_a", "i_switch_max_a"), "its contact current")],
    "connector": [("LIM.i", ("i_max_a", "i_contact_max_a"), "its contact current")],
    "relay": [("LIM.i", ("i_max_a", "i_contact_max_a", "i_switch_max_a"), "its contact current")],
    "led_strip": [("LIM.range", ("vdd_op_min_v", "vdd_op_max_v"), "the supply of its pixels")],
}
DISSIPATES = ("resistor", "diode", "led", "led_rgb", "npn", "pnp", "nmos", "pmos", "njfet", "pjfet")
OWN_RANGE = {"ldo": ("vin_min_v",), "buck": ("vin_min_v",), "boost": ("vin_min_v",), "buck_boost": ("vin_min_v",),
             "mcu": ("vin_min_v", "vsys_min_v"),
             "current": ("vin_min_v", "vin_max_v")}


def _termination(p):
    ratio = p.get("i_term_ratio")
    return f" – termination at {ratio * 100:g} % of the programmed current" if isinstance(ratio, (int, float)) else ""


# per behaviour: what the simulation leaves out over time – a function of the entry's values -> the text
OVER_TIME = {
    "charger": lambda p: (f"not simulated: the end of the charge cycle{_termination(p)}, the recharge, the status "
                          "outputs – the model charges while the cell is below its float voltage "
                          "(HINT.charge_termination, HINT.power_path)"),
    "protection": lambda p: ("not simulated: the release voltages and the delays – the model is a cell coming from the "
                             "normal range, switched at the thresholds without delay (HINT.protection_timing)"),
    "pd_sink": lambda p: ("not simulated: the USB PD negotiation, PG and the CC lines – VBUS is the voltage a "
                          "scenario's source gives (HINT.pd_negotiation)"),
}


@dataclass
class Gap:
    code: str
    place: str        # the designators, "C1, C3"
    missing: str      # "no v_max_v – its voltage"
    kind: str = "data"   # "data": a value the entry lacks; "cable": a cable without i_max_a; else the behaviour whose
                         # states over time are not simulated

    def line(self):
        return f"{self.code}: {self.place} – {self.missing}"


def _thresholds(part, info):
    return all(any(f"{k}_{x}" in src for src in (info, values(part)) for x in ("v", "ratio")) for k in ("vil", "vih"))


def cable_loss(cable, i):
    """(amount, basis) of the heat a wire of the cable takes at the current i: I² × R per metre where its resistance
    per metre is known (circuit.wire_ohm_per_m), else in the whole wire of r_ohm_per_wire."""
    per_m, r = wire_ohm_per_m(cable), cable.get("r_ohm_per_wire")
    if per_m is not None:
        gauge = f"AWG {cable['awg']:g}" if is_number(cable.get("awg")) else f"{wire_mm2(cable):g} mm²"
        basis = (f"r_ohm_per_wire {r:g} Ω over length_m {cable['length_m']:g}" if is_number(r)
                 else f"{gauge} copper at 20 °C")
        return f"I² × R: {si(i * i * per_m, 'W')} per metre of wire", basis
    if is_number(r):
        return f"I² × R: {si(i * i * r, 'W')} in the wire", f"r_ohm_per_wire {r:g} Ω, no length_m for the loss per metre"
    return "the loss per metre is not known", "no length_m with awg, mm2 or r_ohm_per_wire"


NOT_HELD = "it is not held to the wire's rating"


def cable_gaps(design, sim=None):
    """LIM.i on the cables without i_max_a: each that carries current in the simulation result `sim` (its
    cable_currents), with its highest current and the loss per metre; without a result each such cable, its current
    not known."""
    known = (sim or {}).get("cable_currents")
    out = []
    for c in design.graph.get("cables") or []:
        if is_number(c.get("i_max_a")):
            continue
        place, e = f"cable {c.get('name', '')}", (known or {}).get(c.get("name"))
        if known is None:
            out.append(Gap("LIM.i", place, "no i_max_a – its current is not known without a simulation of this state "
                                           f"(edakit sim) – {NOT_HELD}", "cable"))
        elif e is None:
            out.append(Gap("LIM.i", place, f"no i_max_a – no scenario of the simulation gave its current – {NOT_HELD}",
                           "cable"))
        elif e["i_a"] >= CARRIES_A:
            amount, basis = cable_loss(c, e["i_a"])
            out.append(Gap("LIM.i", place, f"no i_max_a – up to {si(e['i_a'], 'A')} (wire {e['wire']}, {e['scenario']}),"
                                           f" {amount} ({basis}) – its current is not held to the wire's rating",
                           "cable"))
    return out


def coverage(design, prof=None, sim=None):
    """The gaps of the design, by code: [Gap], the designators of one parts entry together; only codes the profile has
    on. `sim`: the simulation result of this state (sim/run.py), for the cables' currents."""
    found = defaultdict(list)      # (code, entry key, missing) -> designators
    over_time = {}                 # (code, entry key, missing) -> the behaviour not simulated over time
    for des, comp in sorted(design.comps.items()):
        part = design.part(des)
        if not part:
            continue
        key, kind, r, p = design.entry_key(des), part.get("kind"), limits(part), values(part)
        for code, names, what in LIMITS_OF.get(kind, []):
            if not any(n in r for n in names):
                found[(code, key, f"no {' or '.join(names)} – {what} is not held to a limit")].append(des)
        if polarized(part) and "vr_max_v" not in r:
            found[("LIM.v", key, "no vr_max_v – its reverse voltage is not held to a limit")].append(des)
        if kind in DISSIPATES and "rth_ja_k_per_w" not in r:
            found[("LIM.t", key, "no rth_ja_k_per_w – no junction temperature")].append(des)
        from ..radio import radios
        if radios(part) and not (part.get("antenna") or {}).get("keepout_mm"):
            found[("GEO.keepout", key, "no antenna.keepout_mm – the copper under its antenna is not checked")].append(des)
        elif radios(part) and "edge_mm" not in (part.get("antenna") or {}):
            found[("GEO.keepout", key, "no antenna.edge_mm – its antenna's place at the board edge is not checked")
                  ].append(des)
        if kind in ("ic", "module"):
            behavior = p.get("behavior", "none")
            if behavior in OVER_TIME:
                gap = ("SIM.state", key, OVER_TIME[behavior](p))
                found[gap].append(des)
                over_time[gap] = behavior
            supply = [i for i in (part.get("pins") or {}).values() if i.get("type") == "power_in"]
            need = OWN_RANGE.get(behavior, ("vdd_op_min_v", "vdd_op_max_v"))
            pin_range = any("v_op_min_v" in i or "v_op_max_v" in i for i in supply)
            if supply and behavior != "none" and not pin_range and not any(n in r for n in need):
                found[("LIM.range", key, f"no {' or '.join(need)} – its supply is not held to an operating range")
                      ].append(des)
            if behavior == "opamp":
                for name, what in (("vicm_v", "the inputs' common-mode range"), ("vout_swing_v", "the output's swing")):
                    if name not in p:
                        found[("LIM.range", key, f"no {name} – {what} is not checked")].append(des)
            if behavior != "mcu":
                bare = [i.get("name", n) for n, i in (part.get("pins") or {}).items()
                        if i.get("type") == "input" and f"{des}.{n}" in design.pin_net and not _thresholds(part, i)]
                if bare:
                    found[("LVL.threshold", key, f"inputs without thresholds (vih, vil): {', '.join(bare)}")].append(des)
    from .requires import pin_needs
    lacking = []                   # a pin's capacitor need: a class-2 ceramic without dc_bias, a capacitor without esr_ohm
    pin_needs(design.joined(), lacking)
    for des, missing in dict.fromkeys(lacking):
        if des not in found[("REQ.value", design.entry_key(des), missing)]:
            found[("REQ.value", design.entry_key(des), missing)].append(des)
    out = []
    for (code, key, missing), dess in found.items():
        if prof is None or prof.on(Finding(code, "G", "", "")):
            out.append(Gap(code, ", ".join(dess), f"{missing} ({key})",
                           over_time.get((code, key, missing), "data")))
    out += [g for g in cable_gaps(design, sim) if prof is None or prof.on(Finding(g.code, "G", "", ""))]
    return sorted(out, key=lambda g: (g.code, g.place))


def summary(gaps):
    """The one line of `edakit check`: per code the number of places, then the parts not simulated over time by their
    behaviour, then the cables without a rating – or None without gaps."""
    if not gaps:
        return None
    per, timed, cables = defaultdict(int), defaultdict(list), []
    for g in gaps:
        if g.kind == "data":
            per[g.code] += len(g.place.split(", "))
        elif g.kind == "cable":
            cables.append(g.place.removeprefix("cable "))
        else:
            timed[g.kind] += g.place.split(", ")
    parts = []
    if per:
        parts.append("not checked for lack of data: " + ", ".join(f"{code} {n} part{'s' if n > 1 else ''}"
                                                                  for code, n in sorted(per.items())))
    if timed:
        parts.append("not simulated over time: " + ", ".join(f"{', '.join(des)} ({behaviour})"
                                                             for behaviour, des in sorted(timed.items())))
    if cables:
        parts.append(f"cables without i_max_a: {', '.join(cables)}")
    return "; ".join(parts) + " – edakit check --coverage"
