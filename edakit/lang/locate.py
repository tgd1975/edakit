"""A finding of `edakit check` located in the source of the circuit language (T.24): the statement that produced
the place it names – a part, a net, a derivation, a lock, an accept.

    locate(smap, finding)   (file, line) or None – smap the SourceMap of the compile (or its dict, as
                            `edakit graph json --map FILE` writes it), finding a Finding or {code, place, on, text}
"""

from __future__ import annotations

import re


def _get(smap, kind):
    return (smap.get(kind) if isinstance(smap, dict) else getattr(smap, kind, None)) or {}


def _at(entry):
    return (entry["file"], entry["line"]) if entry else None


def locate(smap, finding):
    code = getattr(finding, "code", None) or (finding.get("code") if isinstance(finding, dict) else "")
    place = getattr(finding, "place", None) or (finding.get("place") if isinstance(finding, dict) else "") or ""
    on = getattr(finding, "on", None) or (finding.get("on") if isinstance(finding, dict) else ()) or ()
    comps, nets = _get(smap, "components"), _get(smap, "nets")
    if code.startswith("DEF."):
        des = place.partition(".")[0]
        hit = next((v for k, v in _get(smap, "derivations").items() if k.partition(".")[0] == des), None)
        if hit:
            return _at(hit)
    for kind, name in on:
        if kind == "component" and name in comps:
            return _at(comps[name])
        if kind == "net" and name in nets:
            return _at(nets[name])
    head = re.split(r"[\s:(]", str(place), maxsplit=1)[0]
    des = head.partition(".")[0]
    if head in nets:
        return _at(nets[head])
    if des in comps:
        return _at(comps[des])
    if head in _get(smap, "locks"):
        return _at(_get(smap, "locks")[head])
    if code in _get(smap, "accepts"):
        return _at(_get(smap, "accepts")[code])
    return None
