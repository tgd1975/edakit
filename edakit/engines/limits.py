"""LIMITS: every quantity within its limit (concept rules-at-scale.md, sections 1 and 2).

It joins quantities with limits by place and name and reports where the value is outside: LIM.v, LIM.i, LIM.p, LIM.t
by the quantity's unit, or the code the producer gives (LIM.range, LIM.declared, LIM.backfeed). It does not care
whether the value came from a declared range or from ngspice – the finding's stage says which. A margin finding (a
fuse's trip current) is not reported where the limit itself is exceeded at the same place.

Radio (LIM.eirp, LIM.band): a transmitter's e.i.r.p. against the limit of each EU band it transmits in, and its bands
against the EU licence-exempt bands (radio.py, catalog/tables/radio_eu.toml); what the firmware keeps is graded
firmware or unknown, its severity the profile's by purpose.
"""

from __future__ import annotations

import math

from ..design import natural_key
from ..findings import Finding
from ..circuit import is_number
from ..radio import (EIRP_BANDS, EU_BANDS, NOT_LEGAL_ADVICE, RADIO_KEYS, band_names, bands_in_use, eirp, mhz_ranges,
                     overlaps, radios, stated_use, within)
from .quantities import fuse_currents, part_limits, part_voltages, pin_voltages

CODE = {"V": "LIM.v", "A": "LIM.i", "W": "LIM.p", "°C": "LIM.t", "dBm": "LIM.eirp"}


def num(x, unit):
    return f"{x:.3g} {unit}" if abs(x) < 1000 else f"{x:.0f} {unit}"


def judge(q, lims):
    """Findings of one quantity against its limits."""
    out = []
    code = q.code or CODE.get(q.unit, "LIM.v")
    for lim in lims:
        if lim.max is not None and q.hi is not None:
            value, bound = q.hi * lim.factor, lim.max * lim.derate
            if math.isnan(value):
                out.append(Finding(code, q.stage, q.place, f"{q.how}: not simulated (no value)", lim.source,
                                   grade=q.grade, scenario=q.scenario, on=q.on, old=q.old))
            elif value > bound + lim.eps:
                need = f" × {lim.factor:g} = {num(value, q.unit)}" if lim.factor != 1 else ""
                allowed = f"{num(bound, q.unit)} ({lim.derate:.0%} of {num(lim.max, q.unit)})" if lim.derate != 1 \
                    else num(lim.max, q.unit)
                out.append(Finding(code, q.stage, q.place, f"{q.how} {num(q.hi, q.unit)}{need}, allowed {allowed}",
                                   lim.source, grade=q.grade, scenario=q.scenario, on=q.on, old=q.old,
                                   data={"value": q.hi, "limit": bound, "unit": q.unit}))
        if lim.min is not None and q.lo is not None and math.isnan(q.lo):
            out.append(Finding(code, q.stage, q.place, f"{q.how}: not simulated (no value)", lim.source,
                               grade=q.grade, scenario=q.scenario, on=q.on, old=q.old))
        elif lim.min is not None and q.lo is not None and q.lo < lim.min - lim.eps:
            out.append(Finding(code, q.stage, q.place, f"{q.how} down to {num(q.lo, q.unit)}, at least "
                                                        f"{num(lim.min, q.unit)}", lim.source, grade=q.grade,
                               scenario=q.scenario, on=q.on, old=q.old,
                               data={"value": q.lo, "limit": lim.min, "unit": q.unit}))
    return out


def judge_all(design, quantities):
    """Every quantity against its limits – the parts entry's, the pin's, its own; margins dropped where the limit
    itself is exceeded at the same place."""
    found = []
    for q in quantities:
        found += judge(q, part_limits(design, q) + q.limits)
    hard = {(f.place, f.code, f.scenario, f.on) for f in found if not f.grade}
    return [f for f in found if not (f.grade == "margin" and (f.place, f.code, f.scenario, f.on) in hard)]


def run(ctx):
    found = judge_all(ctx.design, pin_voltages(ctx.design) + part_voltages(ctx.design))
    found += judge_all(ctx.joined, fuse_currents(ctx.joined, ctx.sim))
    return found + radio_power(ctx.design) + radio_bands(ctx.design)


# --- radio ------------------------------------------------------------------------------------------------------------
def radio_power(d):
    """LIM.eirp: each transmitter's e.i.r.p. within the limit of every band of EIRP_BANDS it transmits in (in the bands
    and with the power purpose.radio states, where it does); unknown e.i.r.p. or no bands_mhz: grade unknown. A value
    of the wrong form is PARTS.schema."""
    out = []
    for des in sorted(d.comps, key=natural_key):
        key, on = d.entry_key(des), (("component", des),)
        wrong = set()
        for radio in radios(d.part(des)):
            if bad := [k for k in ("max_dbm", "antenna_dbi", "eirp_dbm") if k in radio and not is_number(radio[k])]:
                wrong.add(id(radio))
                out.append(Finding("PARTS.schema", "P", key, "compliance.radio: " + ", ".join(
                    f"{k} {radio[k]!r} is no number" for k in bad), old="G-24"))
            if "bands_mhz" not in radio:
                out.append(Finding("LIM.eirp", "G", des, f"compliance.radio of {key} states no bands_mhz – the bands "
                                   f"it transmits in, [[from, to], …] in MHz ({NOT_LEGAL_ADVICE})", grade="unknown",
                                   on=on, old="G-24"))
            elif mhz_ranges(radio["bands_mhz"]) is None:
                out.append(Finding("PARTS.schema", "P", key, f"compliance.radio: bands_mhz {radio['bands_mhz']!r} – a "
                                   "list of [from, to] in MHz, from <= to", old="G-24"))
        for radio, ranges, kept in bands_in_use(d, des):
            bands = [(lo, hi, mw) for lo, hi, mw in EIRP_BANDS if any(overlaps(a, b, lo, hi) for a, b in ranges)]
            if not bands or id(radio) in wrong:
                continue
            dbm, how = eirp(radio, kept)
            if dbm is None:
                missing = [RADIO_KEYS[k] for k in how] + [RADIO_KEYS["eirp_dbm"]]
                out.append(Finding("LIM.eirp", "G", des, f"e.i.r.p. in {', '.join(f'{lo:g}–{hi:g}' for lo, hi, _ in bands)}"
                                   f" MHz not known – {key} has no {', no '.join(missing[:-1])} and no {missing[-1]} "
                                   f"({NOT_LEGAL_ADVICE})", grade="unknown", on=on, old="G-24"))
                continue
            gain = radio.get("antenna_dbi") if is_number(radio.get("antenna_dbi")) and "eirp_dbm" not in how else None
            for lo, hi, mw in bands:
                limit = 10 * math.log10(mw)
                if dbm > limit + 1e-9:
                    keep = (f"the firmware keeps the conducted power at or below {limit - gain:.1f} dBm"
                            if gain is not None else f"the firmware lowers the power by at least {dbm - limit:.1f} dB")
                    out.append(Finding("LIM.eirp", "G", des, f"{dbm:.1f} dBm e.i.r.p. in {lo:g}–{hi:g} MHz ({how}), "
                                       f"allowed {mw:g} mW ({limit:.1f} dBm)", "catalog/tables/radio_eu.toml",
                                       f"{keep} ({NOT_LEGAL_ADVICE})", on=on, old="G-24",
                                       data={"value": dbm, "limit": limit, "unit": "dBm"}))
    return out


def radio_bands(d):
    """LIM.band: every range a part transmits in within an EU licence-exempt band. A part that reaches into none at all
    is LIM.band (no firmware helps); a range beyond the bands otherwise, or a part kept off, the firmware keeps (grade
    firmware). purpose.radio of the wrong form is STRUCT.purpose, one naming no part with bands STRUCT.ref."""
    out = []
    use = (d.graph.get("purpose") or {}).get("radio")
    if use is not None and not isinstance(use, dict):
        out.append(Finding("STRUCT.purpose", "G", "purpose.radio", "{designator: \"off\" or {\"bands_mhz\": "
                           "[[from, to], …], \"max_dbm\": …}}", old="G-25"))
    for des, stated in stated_use(d).items():
        if des not in d.comps:
            out.append(Finding("STRUCT.ref", "G", "purpose.radio", f"no part {des} in the graph", old="G-25"))
            continue
        own = [r for radio in radios(d.part(des)) for r in mhz_ranges(radio.get("bands_mhz")) or []]
        if not own:
            out.append(Finding("STRUCT.ref", "G", "purpose.radio", f"{des}: its parts entry {d.entry_key(des)} states "
                               "no bands_mhz to keep to", old="G-25"))
            continue
        if stated == "off":
            continue
        ranges = mhz_ranges(stated.get("bands_mhz")) if isinstance(stated, dict) else None
        if ranges is None or ("max_dbm" in stated and not is_number(stated["max_dbm"])):
            out.append(Finding("STRUCT.purpose", "G", "purpose.radio", f"{des}: \"off\" or {{\"bands_mhz\": [[from, "
                               "to], …] in MHz, from <= to, \"max_dbm\": a number (optional)}", old="G-25"))
            continue
        for a, b in ranges:
            if not within(a, b, own):
                out.append(Finding("STRUCT.purpose", "G", "purpose.radio", f"{des}: {a:g}–{b:g} MHz is no band of "
                                   f"{d.entry_key(des)} (bands_mhz {', '.join(f'{lo:g}–{hi:g}' for lo, hi in own)} "
                                   "MHz)", old="G-25"))
    known = ", ".join(f"{lo:g}–{hi:g}" for lo, hi in EU_BANDS)
    for des in sorted(d.comps, key=natural_key):
        key, on = d.entry_key(des), (("component", des),)
        stated = stated_use(d).get(des)
        read = isinstance(stated, dict) and mhz_ranges(stated.get("bands_mhz")) is not None
        in_use = {id(radio): ranges for radio, ranges, _ in bands_in_use(d, des)}
        seen = set()
        for radio in radios(d.part(des)):
            own = mhz_ranges(radio.get("bands_mhz"))
            if own is None:
                continue
            if not any(overlaps(a, b, lo, hi) for a, b in own for lo, hi in EU_BANDS):
                where = f"{', '.join(f'{a:g}–{b:g}' for a, b in own)} MHz (bands_mhz of {key})"
                if stated == "off":
                    out.append(Finding("LIM.band", "G", des, f"transmits only in {where}, in no EU licence-exempt band"
                                       " – purpose.radio keeps it off", "catalog/tables/radio_eu.toml",
                                       f"the firmware never switches it on ({NOT_LEGAL_ADVICE})", grade="firmware",
                                       on=on, old="G-25"))
                else:
                    out.append(Finding("LIM.band", "G", des, f"transmits only in {where}, in no EU licence-exempt band "
                                       f"({known} MHz)", "catalog/tables/radio_eu.toml", "a part made for the EU bands, "
                                       "kept off (purpose.radio), or accept with the allocation of a licensed use "
                                       f"({NOT_LEGAL_ADVICE})", on=on, old="G-25"))
                continue
            for a, b in in_use.get(id(radio), []):
                if within(a, b, EU_BANDS) or (a, b) in seen:
                    continue
                seen.add((a, b))
                near = [f"{lo:g}–{hi:g} MHz" for lo, hi in EU_BANDS if overlaps(a, b, lo, hi)]
                where = (f"beyond the EU band{'s' if len(near) > 1 else ''} {' and '.join(near)}" if near else
                         "in no EU licence-exempt band")
                what = (f"purpose.radio states {a:g}–{b:g} MHz, {where}" if read else
                        f"{a:g}–{b:g} MHz (bands_mhz of {key}) {'reaches' if near else 'lies'} {where}")
                keep = band_names([(a, b)] if near else own)
                out.append(Finding("LIM.band", "G", des, what, "catalog/tables/radio_eu.toml",
                                   f"the firmware keeps to {keep}" + ("" if read else "; purpose.radio can state that it "
                                                                      "does") + f" ({NOT_LEGAL_ADVICE})",
                                   grade="firmware", on=on, old="G-25"))
    return out
