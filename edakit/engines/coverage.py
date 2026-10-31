"""What went unchecked for lack of data (maker-coverage FT-19; concept rules-at-scale.md, section 8): a relation that
needs a datasheet value skips a part without it and reports nothing – LIM.v on a capacitor without v_max_v, LVL.threshold
on an input without thresholds. coverage() names every such gap, by code; `edakit check` prints one line, `edakit check
--coverage` the list, the gate protocol the list in its section 2. A gap is no finding: nothing is wrong that anybody
saw – nobody looked.

The same list names what the simulation does not model over time (rules-at-scale.md, decision 17): a part whose
behaviour is a charger, a cell's protection or a USB PD sink has states an operating point cannot show – the end of
charge, the release voltages and delays, the negotiation. Each is a gap of SIM.state, "not simulated", with the hint
that names the risk where the part is used.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..circuit import limits, polarized, values
from ..findings import Finding

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
    "fuse": [("LIM.i", ("i_hold_a",), "what it lets pass")],
    "switch": [("LIM.i", ("i_max_a", "i_contact_max_a", "i_switch_max_a"), "its contact current")],
    "button": [("LIM.i", ("i_max_a", "i_contact_max_a", "i_switch_max_a"), "its contact current")],
    "connector": [("LIM.i", ("i_max_a", "i_contact_max_a"), "its contact current")],
    "relay": [("LIM.i", ("i_max_a", "i_contact_max_a", "i_switch_max_a"), "its contact current")],
}
DISSIPATES = ("resistor", "diode", "led", "led_rgb", "npn", "pnp", "nmos", "pmos")
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
    kind: str = "data"   # "data": a value the entry lacks; else the behaviour whose states over time are not simulated

    def line(self):
        return f"{self.code}: {self.place} – {self.missing}"


def _thresholds(part, info):
    return all(any(f"{k}_{x}" in src for src in (info, values(part)) for x in ("v", "ratio")) for k in ("vil", "vih"))


def coverage(design, prof=None):
    """The gaps of the design, by code: [Gap], the designators of one parts entry together; only codes the profile has
    on."""
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
    out = []
    for (code, key, missing), dess in found.items():
        if prof is None or prof.on(Finding(code, "G", "", "")):
            out.append(Gap(code, ", ".join(dess), f"{missing} ({key})",
                           over_time.get((code, key, missing), "data")))
    return sorted(out, key=lambda g: (g.code, g.place))


def summary(gaps):
    """The one line of `edakit check`: per code the number of places, then the parts not simulated over time by their
    behaviour – or None without gaps."""
    if not gaps:
        return None
    per, timed = defaultdict(int), defaultdict(list)
    for g in gaps:
        if g.kind == "data":
            per[g.code] += len(g.place.split(", "))
        else:
            timed[g.kind] += g.place.split(", ")
    parts = []
    if per:
        parts.append("not checked for lack of data: " + ", ".join(f"{code} {n} part{'s' if n > 1 else ''}"
                                                                  for code, n in sorted(per.items())))
    if timed:
        parts.append("not simulated over time: " + ", ".join(f"{', '.join(des)} ({behaviour})"
                                                             for behaviour, des in sorted(timed.items())))
    return "; ".join(parts) + " – edakit check --coverage"
