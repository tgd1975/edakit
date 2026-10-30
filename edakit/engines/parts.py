"""PARTS: parts entries complete – the facts the project's profile requires of each kind and graph type (domains,
[facts]), and of the right form where a fact has one (concept rules-at-scale.md, sections 4 and 5). A missing fact is
PARTS.fact with the fact's last name as its grade (PARTS.fact/radio): its severity is the profile's.
"""

from __future__ import annotations

from collections import defaultdict

from ..design import natural_key
from ..findings import Finding

RADIO_FORM = "\"none\", or its bands and power: {\"bands_mhz\": [[from, to], …], \"max_dbm\": …, \"antenna_dbi\": …, " \
             "\"doc\": …}"


def get(entry, path):
    node = entry
    for k in path.split("."):
        if not isinstance(node, dict) or k not in node:
            return None
        node = node[k]
    return node


def users(d):
    out = defaultdict(list)
    for des in sorted(d.comps, key=natural_key):
        if (key := d.entry_key(des)) is not None:
            out[key].append(des)
    return out


def run(ctx):
    d, prof = ctx.design, ctx.profile
    out = []
    for key, dess in sorted(users(d).items()):
        entry = d.parts[key]
        need = list(prof.facts["kind"].get(entry.get("kind"), [])) if prof else []
        for t in {d.comps[x].get("type") for x in dess} - {None}:
            need += [f for f in (prof.facts["type"].get(t, []) if prof else []) if f not in need]
        on = tuple(("component", x) for x in dess)
        for fact in need:
            if get(entry, fact) is None:
                why = " – the regulatory review (M-6) reads it" if fact == "compliance.radio" else ""
                out.append(Finding("PARTS.fact", "P", key, f"{entry.get('mpn', '')} ({', '.join(dess)}) states no "
                                   f"{fact}{why}", "[facts] of the profile's domains", "fill it in from the datasheet"
                                   + (": its bands and power, or \"none\" when it does not transmit"
                                      if fact == "compliance.radio" else ""),
                                   grade=fact.rsplit(".", 1)[-1], on=on, old="P-11" if fact == "compliance.radio" else ""))
        r = (entry.get("compliance") or {}).get("radio")
        if r is not None and not (r == "none" or isinstance(r, dict) or (isinstance(r, list) and r
                                                                        and all(isinstance(x, dict) for x in r))):
            out.append(Finding("PARTS.schema", "P", key, f"compliance.radio {r!r} ({', '.join(dess)}) – {RADIO_FORM}",
                               old="P-11"))
    return out
