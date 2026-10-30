"""The conversion to the data model of the restructuring (concept docs/concepts/new/rules-at-scale.md, sections 3
and 4): parts entries, graph and sign-off file of before into the form the engines read. Until the switch-over the
engines convert in memory (design()); then `edakit convert --write` converts a project once.

Parts entry: ratings -> limits, params -> values; every name ends in its unit (vrrm -> vr_max_v, vceo -> vce_max_v,
v_max -> v_max_v, a pin's vmax -> v_max_v, v_op [min, max] -> v_op_min_v and v_op_max_v; the table RENAME). Graph:
waive on nets and components -> accept keyed by the codes that replace the check ID; hints {"H-1": how} -> accept
{"HINT.bulk": how} on the graph; checks.pin_locks and doc_pin_table -> locks.pins and locks.doc_pin_table;
checks.reverse_protect [J1] -> "source": "reversible" on J1. Sign-off file: accepted_warnings -> accept, the pattern's
leading check ID replaced by its codes. Converting what is converted changes nothing.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from . import catalog

# old name -> new name, per section; a name not listed keeps its name
RENAME = {
    "limits": {"v_max": "v_max_v", "vrrm": "vr_max_v", "vr_max": "vr_max_v", "vceo": "vce_max_v",
               "vebo": "veb_max_v", "vds_max": "vds_max_v", "vgs_max": "vgs_max_v", "if_avg_a": "if_max_a",
               "ifsm_a": "ifsm_max_a", "vdd_max": "vdd_max_v", "vdd_op_min": "vdd_op_min_v",
               "vdd_op_max": "vdd_op_max_v", "vin_min": "vin_min_v", "vin_max": "vin_max_v", "vsys_min": "vsys_min_v",
               "vsys_max": "vsys_max_v", "vout_max": "vout_max_v", "i_3v3_ext_max_a": "i_out_max_a",
               "iout_max_a": "i_out_max_a", "i_gpio_max_a": "gpio_i_max_a", "gpio_v_max": "gpio_v_max_v",
               "i_rated_a": "i_max_a", "v_coil_max": "v_coil_max_v"},
    "values": {"vf_typ": "vf_typ_v", "vf_min": "vf_min_v", "vf_max": "vf_max_v", "v_io": "v_io_v",
               "v_operate": "v_operate_v", "v_release": "v_release_v"},
    "pin": {"vmax": "v_max_v"},
}
COLORS = ("red", "green", "blue")
CHECK_KEYS = {"pin_locks": "pins", "doc_pin_table": "doc_pin_table"}


def _renamed(section, table):
    out = {}
    for k, v in (table or {}).items():
        if k in COLORS and isinstance(v, dict):
            out[k] = _renamed(section, v)       # per colour of an RGB LED
        else:
            out[RENAME[section].get(k, k)] = v
    return out


def part(entry):
    """A parts entry in the new form (a copy)."""
    e = copy.deepcopy(entry)
    if "ratings" in e or "limits" in e:
        e["limits"] = {**_renamed("limits", e.pop("ratings", None)), **(e.get("limits") or {})}
    if "params" in e or "values" in e:
        e["values"] = {**_renamed("values", e.pop("params", None)), **(e.get("values") or {})}
    for num, pin in (e.get("pins") or {}).items():
        new = _renamed("pin", pin)
        op = new.pop("v_op", None)
        if isinstance(op, list) and len(op) == 2:
            new.setdefault("v_op_min_v", op[0])
            new.setdefault("v_op_max_v", op[1])
        e["pins"][num] = new
    return e


def accept_codes(old):
    """The codes an accept of before keyed by `old` (a check or hint ID) is converted to."""
    return catalog.old_map().get(old, [old])


def _accept(waive):
    out = {}
    for old, reason in (waive or {}).items():
        for c in accept_codes(old):
            out.setdefault(c, reason)
    return out


def graph(g):
    """The graph in the new form (a copy): the dict of graph.json, with or without its "graph" wrapper."""
    data = copy.deepcopy(g)
    inner = data.get("graph", data)
    for obj in [*inner.get("components", []), *inner.get("nets", [])]:
        if "waive" in obj:
            acc = {**_accept(obj.pop("waive")), **(obj.get("accept") or {})}
            if acc:
                obj["accept"] = acc
            else:
                obj.pop("accept", None)
    hints = inner.pop("hints", None) or {}
    if hints:
        inner["accept"] = {**_accept(hints), **(inner.get("accept") or {})}
    checks = inner.pop("checks", None) or {}
    locks = {CHECK_KEYS[k]: v for k, v in checks.items() if k in CHECK_KEYS}
    if locks:
        inner["locks"] = {**locks, **(inner.get("locks") or {})}
    comps = {c["designator"]: c for c in inner.get("components", [])}
    for des in checks.get("reverse_protect") or []:
        if des in comps:
            comps[des]["source"] = "reversible"
    unknown = {k: v for k, v in checks.items() if k not in CHECK_KEYS and k != "reverse_protect"}
    if unknown:
        inner["checks"] = unknown          # left for STRUCT.ref to report
    return data


def signoff(s):
    """The sign-off file in the new form (a copy): accepted_warnings -> accept, each pattern's check ID replaced by
    the codes that replace it – one entry per code."""
    data = copy.deepcopy(s)
    out = list(data.get("accept") or [])
    for a in data.pop("accepted_warnings", None) or []:
        old, _, rest = str(a.get("match", "")).partition(" ")
        for c in accept_codes(old) if catalog.OLD_ID.fullmatch(old) else [old]:
            out.append({**a, "match": f"{c} {rest}".strip(), **({"converted_from": a["match"]} if c != old else {})})
    data["accept"] = out
    return data


def design(d):
    """A Design of the new form from one of before: graph and parts entries converted in memory."""
    from .design import Design
    return Design.from_data(graph({"graph": d.graph})["graph"], {k: part(e) for k, e in d.parts.items()},
                            d.boards, d.graph_path)


# --- edakit convert --------------------------------------------------------------------------------------------------
def files(cfg):
    """[(path, old text, new text)] of the project files the conversion changes."""
    out = []

    def one(path, fn):
        if not path.exists():
            return
        old = path.read_text(encoding="utf-8")
        new = json.dumps(fn(json.loads(old)), indent=1, ensure_ascii=False) + "\n"
        if json.loads(new) != json.loads(old):
            out.append((path, old, new))
    one(Path(cfg.graph), graph)
    for p in sorted(Path(cfg.parts).glob("*.json")):
        one(p, part)
    one(Path(cfg.signoff), signoff)
    return out


def main(cfg, args):
    changed = files(cfg)
    for path, _old, new in changed:
        print(f"{'converted' if args.write else 'would convert'}: {cfg.relative(path)}")
        if args.write:
            path.write_text(new, encoding="utf-8")
    print(f"{len(changed)} files" + ("" if args.write else " – edakit convert --write converts them"))
    return 0
