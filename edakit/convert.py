"""The conversion to the data model of the restructuring (concept docs/concepts/done/rules-at-scale.md, sections 3
and 4): parts entries, graph and sign-off file of before into the form the engines read: `edakit convert --write` converts
a project once; a design of before does not load (design.old_form).

Parts entry: ratings -> limits, params -> values; every name ends in its unit (vrrm -> vr_max_v, vceo -> vce_max_v,
v_max -> v_max_v, a pin's vmax -> v_max_v, v_op [min, max] -> v_op_min_v and v_op_max_v; the table RENAME). Graph:
waive on nets and components -> accept keyed by the codes that replace the check ID; hints {"H-1": how} -> accept
{"HINT.bulk": how} on the graph; checks.pin_locks and doc_pin_table -> locks.pins and locks.doc_pin_table;
checks.reverse_protect [J1] -> "source": "reversible" on J1. Sign-off file: accepted_warnings -> accept, the pattern's
leading check ID replaced by its codes; documents, schematic notes and requirements files: their quotes and rows
patterns (text). The files written as they were: their indent, UTF-8 as it is. Converting what is converted changes
nothing. A TOML graph is in the form of the restructuring by construction and is not rewritten (toml_graph). When the
files were the signed ones, the sign-offs of scope 'circuit' keep counting: the new circuit hash goes into the sign-off
file and both into its `rehashed` (carry_signoffs).
"""

from __future__ import annotations

import copy
import json
import re
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
ACCEPT_NOTE = "per net or component: {code: reason} accepts a finding on purpose (edakit explain <code>)"


def _renamed(section, table):
    out = {}
    for k, v in (table or {}).items():
        if k in COLORS and isinstance(v, dict):
            out[k] = _renamed(section, v)       # per colour of an RGB LED
        else:
            out[RENAME[section].get(k, k)] = v
    return out


def part(entry):
    """A parts entry in the new form (a copy), its keys in their order."""
    e = {}
    for k, v in copy.deepcopy(entry).items():
        if k == "ratings":
            e["limits"] = {**_renamed("limits", v), **(entry.get("limits") or {})}
        elif k == "params":
            e["values"] = {**_renamed("values", v), **(entry.get("values") or {})}
        elif k not in e:
            e[k] = v
    for num, pin in (e.get("pins") or {}).items():
        new = _renamed("pin", pin)
        op = new.pop("v_op", None)
        if isinstance(op, list) and len(op) == 2:
            new.setdefault("v_op_min_v", op[0])
            new.setdefault("v_op_max_v", op[1])
        e["pins"][num] = new
    return e


# a waiver of before that lifted one part of what its code holds: its accept key names that topic
TOPICS = {"L-13": ["GEO.spacing:clearance"], "L-14": ["GEO.spacing:paste"], "L-18": ["GEO.spacing:joint"],
          "L-16": ["GEO.ring", "GEO.spacing:holes"], "L-19": ["GEO.silk:visible"], "L-12": ["SYNC.plan:handover"],
          "G-14": ["REQ.missing:cc", "REQ.value:cc", "REQ.forbidden:cc"], "G-18": ["REQ.missing", "PARTS.fact/hot_loop"],
          "G-9": ["PARTS.verified/device"], "G-17": ["LIM.i"], "P-7": ["GEO.hole"], "L-9": ["GEO.hole"]}


def accept_codes(old):
    """The accept keys an accept of before keyed by `old` (a check or hint ID) is converted to."""
    return TOPICS.get(old) or catalog.old_map().get(old, [old])


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
    conv = inner.get("conventions")
    if isinstance(conv, dict) and "waive" in conv:            # the graph's own note on its keys
        inner["conventions"] = {("accept" if k == "waive" else k): (ACCEPT_NOTE if k == "waive" else v)
                                for k, v in conv.items()}
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
    if missing := [des for des in checks.get("reverse_protect") or [] if des not in comps]:
        unknown["reverse_protect"] = missing   # names no part: left for STRUCT.ref to report
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


def block(b):
    """A building block of edakit/blocks in the new form (a copy): its components' and nets' waive -> accept, covers ->
    the codes replacing the check IDs."""
    data = graph({"graph": {k: b[k] for k in ("components", "nets") if k in b}})["graph"]
    out = {**copy.deepcopy(b), **data}
    if "covers" in b:
        out["covers"] = list(dict.fromkeys(c for old in b["covers"] for c in accept_codes(old)))
    return out


# a row of the simulation by the words of its check -> its code (for patterns that quote rows: docs, requirements)
ROW_CODES = [("current from the supply", "LIM.i"), ("current keeps the supply on", "LIM.i"),
             ("current into the", "LIM.backfeed"), ("output voltage", "SIM.state"), ("input voltage", "LIM.range"),
             ("output current", "LIM.i"), ("load on the on-board regulator", "LIM.i"), ("junction temperature", "LIM.t"),
             ("temperature where people touch", "LIM.t"), ("supply voltage", "LIM.range"), ("input level", "LVL.threshold"),
             ("output on", "LVL.direction"), ("relay", "LIM.range"), ("output headroom", "LIM.range"),
             ("LED", "SIM.state"), ("current sharing", "SIM.state"), ("diode blocks", "SIM.state"),
             ("net voltage", "LIM.declared"), ("output high level", "LVL.threshold"), ("input thresholds", "SIM.config"),
             ("power dissipation", "LIM.p"), ("current", "LIM.i"), ("voltage", "LIM.v"), ("|V", "LIM.v"),
             ("peak current", "LIM.i"), ("lowest supply voltage once started", "LIM.range"), ("lowest voltage", "LIM.v"),
             ("highest voltage", "LIM.v"), ("operating point", "SIM.converge"), ("transient run", "SIM.converge")]


def pattern(p):
    """A pattern of protocol rows ("ID scenario item check") with its check ID of before replaced by its code: the one
    code, or for a check of several codes the one its words name (ROW_CODES)."""
    old, _, rest = p.partition(" ")
    if not catalog.OLD_ID.fullmatch(old):
        return p
    codes = accept_codes(old)
    if len(codes) > 1:
        words = rest.split(" ", 2)[-1] if rest.count(" ") >= 2 else rest
        said = words.lower().replace("*", "").strip()
        codes = [c for w, c in ROW_CODES if said and (w.lower() in said or w.lower().startswith(said))] or codes
    return f"{codes[0]} {rest}".strip()


def text(t):
    """A document, schematic notes or a requirements file with its quotes in the new form: sim: patterns, part: paths
    (params -> values, ratings -> limits, names with their unit), rows patterns of verify."""
    import re

    def sim(m):
        return f"{{sim:{m.group(1)} {pattern(m.group(2))}}}"

    def part_path(m):
        section = {"params": "values", "ratings": "limits"}[m.group(2)]
        return f"part:{m.group(1)}.{section}.{RENAME[section].get(m.group(3), m.group(3))}"
    t = re.sub(r"\{sim:(max|min|one) ([^}]+)\}", sim, t)
    t = re.sub(r"part:([\w.-]+?)\.(params|ratings)\.(\w+)", part_path, t)
    return re.sub(r'(rows\s*=\s*")([^"]+)(")', lambda m: m.group(1) + pattern(m.group(2)) + m.group(3), t)


# --- edakit convert --------------------------------------------------------------------------------------------------
def files(cfg):
    """[(path, old text, new text)] of the project files the conversion changes."""
    out = []

    def one(path, fn):
        if not path.exists():
            return
        old = path.read_text(encoding="utf-8")
        m = re.search(r"^( +)\S", old, re.M)              # written as the file was: its indent, UTF-8 as it is
        new = json.dumps(fn(json.loads(old)), indent=len(m.group(1)) if m else 1, ensure_ascii=False) + "\n"
        if json.loads(new) != json.loads(old):
            out.append((path, old, new))
    if Path(cfg.graph).suffix != ".toml":         # a TOML graph: toml_graph says why there is nothing to do
        one(Path(cfg.graph), graph)
    for p in sorted(Path(cfg.parts).glob("*.json")):
        one(p, part)
    one(Path(cfg.signoff), signoff)
    for path in [*cfg.requirements, *cfg.docs, Path(cfg.schematic_file)]:
        path = Path(path)
        if path.exists() and (new := text(old := path.read_text(encoding="utf-8"))) != old:
            out.append((path, old, new))
    return out


CARRIED = ("graph, parts entries and sign-off file in the form of the restructuring (handbook 14.2): names with their "
           "unit, accept by code, locks – every value carried over; the files were the signed ones")


def carry_signoffs(cfg, before, by="edakit convert", why=CARRIED):
    """After the conversion: when the files were the signed ones (the sign-off file's state_sha256 was their circuit
    hash), the sign-offs of scope 'circuit' keep counting – the new hash goes into the file and both into `rehashed`,
    as the gate records a change of [release] hash_ignore. `by` and `why` say which conversion (edakit graph convert
    too). -> the line to print, or None."""
    import datetime as dt
    from .release import gate
    path = Path(cfg.signoff)
    if not path.exists():
        return None
    old = path.read_text(encoding="utf-8")
    s = json.loads(old)
    after = gate.state_hash(cfg)
    if s.get("state_sha256") != before or after == before:
        return None
    s["state_sha256"] = after
    s.setdefault("rehashed", []).append({"date": dt.date.today().isoformat(), "by": by, "why": why,
                                         "state_sha256": [before, after]})
    m = re.search(r"^( +)\S", old, re.M)
    path.write_text(json.dumps(s, indent=len(m.group(1)) if m else 1, ensure_ascii=False) + "\n", encoding="utf-8")
    return (f"{cfg.relative(path)}: the sign-offs of scope 'circuit' keep counting – state_sha256 {before[:12]}… → "
            f"{after[:12]}… (rehashed)")


def toml_graph(cfg):
    """The line for a TOML graph, or None for a JSON one: a TOML graph is in the form of the restructuring by
    construction – it was written after it –, and convert does not rewrite one; a key of before in it is named."""
    if Path(cfg.graph).suffix != ".toml" or not Path(cfg.graph).exists():
        return None
    from .design import load_graph, old_form
    why = old_form(load_graph(cfg.graph), {})
    return f"{cfg.relative(cfg.graph)}: " + (
        "a TOML graph is in the form of the restructuring – nothing to convert" if why is None else
        f"{why} – the form of before; convert does not rewrite a TOML graph: write accept and locks in its place by "
        "hand (handbook 3.1)")


def main(cfg, args):
    if line := toml_graph(cfg):
        print(line)
    changed = files(cfg)
    before = None
    if args.write and changed:
        from .release import gate
        before = gate.state_hash(cfg)
    for path, _old, new in changed:
        print(f"{'converted' if args.write else 'would convert'}: {cfg.relative(path)}")
        if args.write:
            path.write_text(new, encoding="utf-8")
    print(f"{len(changed)} files" + ("" if args.write else " – edakit convert --write converts them"))
    if before and (line := carry_signoffs(cfg, before)):
        print(line)
    return 0
