"""What went unchecked for lack of data (maker-coverage FT-19; concept rules-at-scale.md, section 8): a relation that
needs a datasheet value skips a part without it and reports nothing – LIM.v on a capacitor without v_max_v, LVL.threshold
on an input without thresholds. coverage() names every such gap, by code; `edakit check` prints one line, `edakit check
--coverage` the list, the gate protocol the list in its section 2. A gap is no finding: nothing is wrong that anybody
saw – nobody looked.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..circuit import limits, values
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
    "switch": [("LIM.i", ("i_max_a",), "its contact current")],
    "button": [("LIM.i", ("i_max_a",), "its contact current")],
    "connector": [("LIM.i", ("i_max_a",), "its contact current")],
    "relay": [("LIM.i", ("i_max_a",), "its contact current")],
}
DISSIPATES = ("resistor", "diode", "led", "led_rgb", "npn", "pnp", "nmos", "pmos")
OWN_RANGE = {"ldo": ("vin_min_v",), "buck": ("vin_min_v",), "boost": ("vin_min_v",), "mcu": ("vin_min_v", "vsys_min_v"),
             "current": ("vin_min_v", "vin_max_v")}


@dataclass
class Gap:
    code: str
    place: str        # the designators, "C1, C3"
    missing: str      # "no v_max_v – its voltage"

    def line(self):
        return f"{self.code}: {self.place} – {self.missing}"


def _thresholds(part, info):
    return all(any(f"{k}_{x}" in src for src in (info, values(part)) for x in ("v", "ratio")) for k in ("vil", "vih"))


def coverage(design, prof=None):
    """The gaps of the design, by code: [Gap], the designators of one parts entry together; only codes the profile has
    on."""
    found = defaultdict(list)      # (code, entry key, missing) -> designators
    for des, comp in sorted(design.comps.items()):
        part = design.part(des)
        if not part:
            continue
        key, kind, r, p = design.entry_key(des), part.get("kind"), limits(part), values(part)
        for code, names, what in LIMITS_OF.get(kind, []):
            if not any(n in r for n in names):
                found[(code, key, f"no {' or '.join(names)} – {what} is not held to a limit")].append(des)
        if kind in DISSIPATES and "rth_ja_k_per_w" not in r:
            found[("LIM.t", key, "no rth_ja_k_per_w – no junction temperature")].append(des)
        if kind in ("ic", "module"):
            behavior = p.get("behavior", "none")
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
            out.append(Gap(code, ", ".join(dess), f"{missing} ({key})"))
    return sorted(out, key=lambda g: (g.code, g.place))


def summary(gaps):
    """The one line of `edakit check`: per code the number of places, or None without gaps."""
    if not gaps:
        return None
    per = defaultdict(int)
    for g in gaps:
        per[g.code] += len(g.place.split(", "))
    return ("not checked for lack of data: " + ", ".join(f"{code} {n} part{'s' if n > 1 else ''}"
                                                       for code, n in sorted(per.items()))
            + " – edakit check --coverage")
