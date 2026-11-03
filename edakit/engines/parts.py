"""PARTS: parts entries complete – the facts the project's profile requires of each kind and graph type, of every
part for the graph's purpose.use, and of every part the BOM lists (domains, [facts]), and of the right form where a
fact has one (concept rules-at-scale.md, sections 4 and 5). A missing fact is PARTS.fact with the fact's last name as
its grade (PARTS.fact/radio): its severity is the profile's. [facts] bom names the facts of every part the BOM lists
(bom not false) – compliance.rohs (PARTS.fact/rohs). The board's own copper (own.what copper: a solder jumper, a test
pad) is bought from nobody: no compliance fact is asked of it.
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
        need += [f for f in (prof.facts["purpose"].get(prof.purpose, []) if prof else []) if f not in need]
        if prof and any(d.comps[x].get("bom") is not False for x in dess):
            need += [f for f in prof.facts["bom"] if f not in need]
        if (entry.get("own") or {}).get("what") == "copper":     # the board's copper: no supplier to state anything
            need = [f for f in need if not f.startswith("compliance.")]
        on = tuple(("component", x) for x in dess)
        for fact in need:
            if get(entry, fact) in (None, "", [], {}):
                text = (f"{key} {entry.get('mpn', '')} ({', '.join(dess)}) states no radio – compliance.radio in its "
                        "parts entry: its bands and power, or \"none\" when it does not transmit; the regulatory review "
                        "(M-6) reads it" if fact == "compliance.radio" else
                        f"{key} {entry.get('mpn', '')} ({', '.join(dess)}) states no SVHC – compliance.reach in its "
                        "parts entry: the supplier's REACH statement, or \"none above 0.1 %\" with its source; a board "
                        f"{'given away' if prof.purpose == 'gift' else 'that is sold'} is placed on the market, and REACH "
                        "Art. 33 asks to name a substance of very high concern above 0.1 %" if fact == "compliance.reach" else
                        f"{key} {entry.get('mpn', '')} ({', '.join(dess)}) states no RoHS status – compliance.rohs in "
                        "its parts entry: true, false or the exemption, from the manufacturer's statement or the "
                        "distributor's page; the regulatory review (M-6) reads it" if fact == "compliance.rohs" else
                        f"{key} {entry.get('mpn', '')} ({', '.join(dess)}) states no {fact}")
                out.append(Finding("PARTS.fact", "P", key, text, "[facts] of the profile's domains",
                                   "fill it in from the datasheet", grade=fact.rsplit(".", 1)[-1], on=on))
        r = (entry.get("compliance") or {}).get("radio")
        if r is not None and not (r == "none" or isinstance(r, dict) or (isinstance(r, list) and r
                                                                        and all(isinstance(x, dict) for x in r))):
            out.append(Finding("PARTS.schema", "P", key, f"{key} ({', '.join(dess)}): compliance.radio {r!r} – "
                                                         f"{RADIO_FORM}"))
    return out
