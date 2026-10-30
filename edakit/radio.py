"""Radio: what a parts entry states about its transmitter (compliance.radio), the bands a graph's purpose.radio keeps
it to, its e.i.r.p., and the EU licence-exempt bands of the table catalog/tables/radio_eu.toml (handbook 15.2).
"""

from __future__ import annotations

from .catalog import table
from .circuit import is_number

NOT_LEGAL_ADVICE = "support, not legal advice: no claim to correctness, nothing legally guaranteed"   # handbook 15
BANDS = table("radio_eu")
# EU licence-exempt bands whose limit is an e.i.r.p., (from MHz, to MHz, the band's highest limit in mW)
EIRP_BANDS = tuple((b["from_mhz"], b["to_mhz"], b["limit_mw"]) for b in BANDS["eirp"])
# EU licence-exempt bands: the short range devices (limits in e.r.p.) and the bands of EIRP_BANDS
EU_BANDS = tuple((b["from_mhz"], b["to_mhz"]) for b in BANDS["band"]) + tuple((lo, hi) for lo, hi, _ in EIRP_BANDS)
RADIO_TYPES = ("module", "microcontroller")   # graph types whose parts entry states its radio, "none" too (P-11)
RADIO_KEYS = {"max_dbm": "max_dbm (the conducted power at the RF port)",       # what G-24 asks for when it is missing
              "antenna_dbi": "antenna_dbi (the gain of its antenna, from the module's datasheet or a certificate)",
              "eirp_dbm": "eirp_dbm (the e.i.r.p. a certificate states)"}


def radios(part):
    """The radios a parts entry states in compliance.radio: a list of dicts – the entry of an own board lists those of
    its parts (4.5) –, [] when it states none."""
    r = ((part or {}).get("compliance") or {}).get("radio")
    if isinstance(r, dict):
        return [r]
    return [x for x in r if isinstance(x, dict)] if isinstance(r, list) else []


def mhz_ranges(value):
    """[(from, to), …] of a bands_mhz value in MHz, None when it is no list of [from, to] numbers with from <= to."""
    if not isinstance(value, list) or not value:
        return None
    if not all(isinstance(r, list) and len(r) == 2 and all(is_number(x) for x in r) and r[0] <= r[1] for r in value):
        return None
    return [(r[0], r[1]) for r in value]


def within(a, b, ranges):
    """The range a…b lies inside one of the ranges."""
    return any(lo <= a and b <= hi for lo, hi in ranges)


def overlaps(a, b, lo, hi):
    """The range a…b transmits inside the band lo…hi (a single frequency on its edge counts)."""
    return max(a, lo) < min(b, hi) or (a == b and lo <= a <= hi)


def eirp(radio, kept=None):
    """(e.i.r.p. in dBm, how it was found) of one radio of a parts entry: eirp_dbm as a certificate states it, else
    max_dbm – the conducted power at the RF port – plus antenna_dbi, the gain of the antenna in the product; (None,
    the keys that are missing) without them. kept: a lower conducted power the firmware keeps (purpose.radio max_dbm),
    which goes before eirp_dbm where antenna_dbi is known."""
    p, g = radio.get("max_dbm"), radio.get("antenna_dbi")
    if is_number(kept) and is_number(g) and not (is_number(p) and p <= kept):
        return kept + g, f"max_dbm {kept:g} kept by the firmware (purpose.radio) + antenna_dbi {g:g}"
    if is_number(radio.get("eirp_dbm")):
        return radio["eirp_dbm"], "eirp_dbm of the parts entry"
    if is_number(p) and is_number(g):
        return p + g, f"max_dbm {p:g} at the RF port + antenna_dbi {g:g}"
    return None, [k for k, v in (("max_dbm", p), ("antenna_dbi", g)) if not is_number(v)]


def stated_use(d):
    """purpose.radio of the graph, {designator: "off" | {"bands_mhz": [[from, to], …], "max_dbm": …, "notes": …}}:
    how the firmware uses the radio of a part – not at all, or in these bands (with this conducted power)."""
    use = (d.graph.get("purpose") or {}).get("radio")
    return use if isinstance(use, dict) else {}


def bands_in_use(d, des):
    """[(radio, its ranges in use, the conducted power the firmware keeps or None)] for the radios of a component's
    parts entry with bands_mhz: without a statement in purpose.radio the entry's bands; with "off" none; with stated
    bands those of them that lie in the radio's own bands_mhz."""
    stated = stated_use(d).get(des)
    ranges = mhz_ranges(stated.get("bands_mhz")) if isinstance(stated, dict) else None
    kept = stated.get("max_dbm") if isinstance(stated, dict) and is_number(stated.get("max_dbm")) else None
    out = []
    for radio in radios(d.part(des)):
        own = mhz_ranges(radio.get("bands_mhz"))
        if own is None or stated == "off":
            continue
        out.append((radio, own, None) if ranges is None else
                   (radio, [(a, b) for a, b in ranges if within(a, b, own)], kept))
    return out


def band_names(ranges):
    """'2400–2483.5 MHz (for Wi-Fi: channels 1–13)' – the EU bands of EU_BANDS that ranges reach into, as a message says
    what the firmware must keep to."""
    near = [(lo, hi) for lo, hi in EU_BANDS if any(overlaps(a, b, lo, hi) for a, b in ranges)]
    return " or ".join(f"{lo:g}–{hi:g} MHz" + (" (for Wi-Fi: channels 1–13)" if (lo, hi) == (2400, 2483.5) else "")
                       for lo, hi in near)

