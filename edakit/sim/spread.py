"""The spread of transistor parameters as corners of the simulation (maker-coverage FT-17), as the LEDs' forward
voltage has its corners: sim.json `spread`, a list of "min", "typ", "max" (no key: ["typ"], every model as its entry
gives it – the simulation as before). Each DC scenario of the matrix runs once per corner of `spread`, every
transistor whose entry gives a spread at that end of it:

  npn, pnp     hFE: BF of the model = values hfe_min | hfe_max; in the corner max also the collector-base leakage
               values icbo_a ({"°C": A}, the datasheet's maximum) at the scenario's ambient_c, a current from the
               collector into the base – log-linear between the temperatures the entry gives, along the nearest two
               beyond them, the one value as it is where the entry gives one
  nmos, pmos   VGS(th): VTO = the smaller (min) or larger (max) magnitude of values vgs_th_v [min, typ, max]; KP so
               that RDS(on) at the lowest gate voltage of rds_on_max_ohm stays what the entry's model gives there – the
               datasheet's maximum holds for every part of the spread
  njfet, pjfet IDSS and VGS(off) together: VTO = −|vgs_off_v| at the end, BETA = idss_a / VTO² – the device that
               has both at that end. The crossed ends (the least IDSS with the largest |VGS(off)|) would need a BETA a
               decade away from the typical device's (MMBFJ201: 0.09 and 11 mA/V² against 0.98 mA/V² read from Fig. 1),
               the paired ends stay within a factor of 2.3 of it (0.44 and 2.2 mA/V²).

"min" is every parameter at the low end of its magnitude, "max" at the high end – all transistors of the board at the
same end, as all LEDs share a corner: the parts of one batch, and the extremes of a stage whose bias moves one way
with each transistor. Where two transistors pull a stage's bias in opposite directions, an extra scenario names its
own corner per part: "spread": {"Q1": "min", "Q2": "max"} (every other part typ). A transistor whose entry has no
spread of its kind keeps its model in every corner; run.py names it in a row of information.
"""

from __future__ import annotations

import math
import re

CORNERS = ("min", "typ", "max")
TRANSISTORS = ("npn", "pnp", "nmos", "pmos", "njfet", "pjfet")
SUFFIX = {"t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3, "mil": 25.4e-6, "m": 1e-3, "u": 1e-6, "µ": 1e-6, "n": 1e-9,
          "p": 1e-12, "f": 1e-15}
MODEL = re.compile(r"^\s*\.model\s+(\S+)\s+([A-Za-z]+)\s*\(?(.*?)\)?\s*$", re.I | re.S)
KP_HEADROOM_V = 0.1   # KP is rescaled only where the lowest specified gate voltage is this far above the new VTO


class SpreadError(ValueError):
    pass


def spice_number(text):
    """'5f' -> 5e-15, '0.97m' -> 9.7e-4, '1Meg' -> 1e6; None for no number."""
    m = re.fullmatch(r"([-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?)([a-zµ]*)", str(text).strip(), re.I)
    if not m:
        return None
    unit = m.group(2).lower()
    for suffix in sorted(SUFFIX, key=len, reverse=True):
        if unit.startswith(suffix):
            return float(m.group(1)) * SUFFIX[suffix]
    return float(m.group(1))


def parse_model(text):
    """'.model NAME TYPE(K=V …)' -> (name, type, {KEY: value text}) – keys upper case, in their order."""
    m = MODEL.match(text or "")
    if not m:
        raise SpreadError(f"{text!r} is no .model line")
    params = {}
    for tok in re.findall(r"([A-Za-z_]\w*)\s*=\s*([^\s=()]+)", m.group(3)):
        params[tok[0].upper()] = tok[1]
    return m.group(1), m.group(2).upper(), params


def model_text(name, typ, params):
    return f".model {name} {typ}(" + " ".join(f"{k}={v}" for k, v in params.items()) + ")"


def corner_of(scenario, des):
    """The corner of one part in a scenario: its spread a word for all parts, or a map per designator (typ for the
    others)."""
    sp = scenario.get("spread", "typ")
    return sp.get(des, "typ") if isinstance(sp, dict) else sp


def ends(x):
    """(low end, high end) of a value by magnitude – [min, typ, max] with null where the datasheet gives none, or a
    number; None where neither end is given."""
    xs = [v for v in (x if isinstance(x, list) else [x]) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not xs:
        return None
    return min(xs, key=abs), max(xs, key=abs)


def has_spread(part):
    """Whether the entry gives a spread its kind's corners use."""
    kind, p = part.get("kind"), part.get("values") or {}
    if kind in ("npn", "pnp"):
        return any(isinstance(p.get(k), (int, float)) for k in ("hfe_min", "hfe_max"))
    if kind in ("nmos", "pmos"):
        e = ends(p.get("vgs_th_v"))
        return e is not None and e[0] != e[1]
    if kind in ("njfet", "pjfet"):
        return ends(p.get("idss_a")) is not None and ends(p.get("vgs_off_v")) is not None
    return False


def leakage(part, ambient_c):
    """The collector-base leakage of the entry (values icbo_a, {"°C": A}) at ambient_c, in A: log-linear between the
    given temperatures, along the nearest two beyond them, the one value as it is; 0 without icbo_a."""
    table = (part.get("values") or {}).get("icbo_a")
    if isinstance(table, (int, float)):
        return float(table)
    pts = sorted((float(t), float(a)) for t, a in (table or {}).items() if a and a > 0)
    if not pts:
        return 0.0
    if len(pts) == 1:
        return pts[0][1]
    i = next((k for k in range(1, len(pts)) if ambient_c <= pts[k][0]), len(pts) - 1)
    (t0, a0), (t1, a1) = pts[i - 1], pts[i]
    return math.exp(math.log(a0) + (math.log(a1) - math.log(a0)) * (ambient_c - t0) / (t1 - t0))


def corner_model(part, des, corner):
    """(model name, .model text) of a transistor in a corner – the entry's own model in typ and where its entry gives
    no spread of its kind."""
    name, typ, params = parse_model(part["spice"]["model"])
    kind, p = part.get("kind"), part.get("values") or {}
    if corner == "typ" or not has_spread(part):
        return name, part["spice"]["model"]
    params = dict(params)
    if kind in ("npn", "pnp"):
        hfe = p.get(f"hfe_{corner}")
        if not isinstance(hfe, (int, float)):
            return name, part["spice"]["model"]
        params["BF"] = f"{hfe:.6g}"
    elif kind in ("nmos", "pmos"):
        lo, hi = ends(p["vgs_th_v"])
        vto = lo if corner == "min" else hi
        old = spice_number(params.get("VTO", "0")) or 0.0
        kp = spice_number(params["KP"]) if "KP" in params else None
        table = p.get("rds_on_max_ohm")
        if kp and isinstance(table, dict) and table:
            ref = min(abs(float(v)) for v in table)
            if ref - abs(vto) > KP_HEADROOM_V and ref - abs(old) > KP_HEADROOM_V:
                params["KP"] = f"{kp * (ref - abs(old)) / (ref - abs(vto)):.6g}"
        params["VTO"] = f"{vto:.6g}"
    elif kind in ("njfet", "pjfet"):
        i_lo, i_hi = ends(p["idss_a"])
        v_lo, v_hi = ends(p["vgs_off_v"])
        idss, voff = (i_lo, v_lo) if corner == "min" else (i_hi, v_hi)
        if not idss or not voff:
            raise SpreadError(f"{des}: idss_a and vgs_off_v need non-zero ends for the corner {corner}")
        params["VTO"] = f"{-abs(voff):.6g}"
        params["BETA"] = f"{abs(idss) / voff ** 2:.6g}"
    else:
        return name, part["spice"]["model"]
    new = f"{name}_{corner}"
    return new, model_text(new, typ, params)


def matrix(sim):
    """The corners of `spread` for the scenario matrix: ["typ"] without the key."""
    sp = sim.get("spread", ["typ"])
    if not isinstance(sp, list) or not sp or not all(x in CORNERS for x in sp) or len(set(sp)) != len(sp):
        raise SpreadError(f"spread: a list of {', '.join(CORNERS)} (each once) expected, not {sp!r}")
    return sp


def check(design, sim):
    """`spread` of sim.json and the spread of every extra scenario and transient run: a corner, or a map from
    transistors of the graph to corners."""
    matrix(sim)
    named = [(f"extra scenario {s.get('name', '?')}", s) for s in sim.get("extra_scenarios", [])]
    named += [(f"transients {n}", r) for n, r in (sim.get("transients") or {}).items() if isinstance(r, dict)]
    for at, s in named:
        sp = s.get("spread", "typ")
        if isinstance(sp, str) and sp in CORNERS:
            continue
        if not isinstance(sp, dict) or not sp:
            raise SpreadError(f"{at}: spread – one of {', '.join(CORNERS)} or a map from transistors to them, not "
                              f"{sp!r}")
        for des, x in sp.items():
            if (design.part(des) or {}).get("kind") not in TRANSISTORS:
                raise SpreadError(f"{at}: spread {des} – no transistor of the graph")
            if x not in CORNERS:
                raise SpreadError(f"{at}: spread {des} – one of {', '.join(CORNERS)}, not {x!r}")


def without(design):
    """{designator: what its entry lacks} of the transistors whose entries give no spread of their kind."""
    need = {"npn": "hfe_min/hfe_max", "pnp": "hfe_min/hfe_max", "nmos": "vgs_th_v [min, typ, max]",
            "pmos": "vgs_th_v [min, typ, max]", "njfet": "idss_a and vgs_off_v", "pjfet": "idss_a and vgs_off_v"}
    out = {}
    for des in sorted(design.comps):
        part = design.part(des) or {}
        if part.get("kind") in TRANSISTORS and part.get("spice") and not has_spread(part):
            out[des] = f"no {need[part['kind']]} ({design.entry_key(des)})"
    return out
