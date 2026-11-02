"""Building blocks: small circuits with checked parts that go into the hardware graph in one step.

    edakit block list
    edakit block show NAME
    edakit block add NAME --as INSTANCE [--connect PORT=NET ...] [--without DES ...] [--board B] [--file BLOCK.json]
                     [--set PARAM=VALUE ...] [--part DES=KEY ...] [--dry-run]

A block (edakit/blocks/<name>.json, or any file given with --file) is a piece of graph: components with LCSC numbers,
nets, and ports – the nets that connect to the rest of the circuit. `add` copies it into the project's graph:

  - designators get the next free numbers of their prefix (R1 -> R7), "{as}" in labels becomes the instance name
  - internal nets are named <INSTANCE>_<NET>; a port joins the net given with --connect PORT=NET; a port without
    --connect becomes its own net <INSTANCE>_<PORT>, except "gnd", which joins the project's ground
  - a net that does not exist yet gets the block's voltage range: [min, max], or "@port" for the range of the net that
    port is connected to
  - missing parts entries are copied from edakit's parts library (edakit/parts/, edakit part add) with their
    provenance; an existing entry must have the same pins
  - "graph": {"grounds": [net, …]} – graph-level keys the block brings: its nets that are a ground of their own (a
    protection IC on the cell's minus) join the project's `grounds`
  - "optional": {"parts": [designator, …], "ports": [port, …]} – parts --without may leave out, and ports that may stay
    unconnected: a pin left alone on its net goes into its component's nc instead of a net of one pin
  - an accept keyed by "code place" names the block's designators; they are renamed with the parts
  - --set PARAM=VALUE (a block's "params"): every derivation of the block that reads the parameter runs with the
    block's own entries and the ranges of the nets its ports join – the derived value, the series' nearest value and
    the window are printed; a part of the block whose value fits stays, else --part DES=KEY names the entry to take
    (the library's or the project's, inside the window), and without it nothing is written and the entries in the
    window are named. The record goes into the graph's "derivations" (DEF.derive reads it); without --set no rule runs
  - the graph file keeps its formatting (indent, UTF-8); nothing is written with --dry-run
  - a TOML graph is written with a line editor (toml_edit) that keeps its comments and arrangement: a new
    [components.<des>] table after the last component table, a new [nets.<name>] after the last net table, a pin on an
    existing net at the end of its array, as the array is written (inline or over several lines), the block's accept
    as keys of the table (accept."LIM.v J2" = "…"), the graph's grounds into its top-level array; the pin map is left
    out where the parts entry gives it (parts_to_copy found them equal). What would not read back as the graph the
    JSON path gives is not written

The block's notes say what is left to decide (values, sim.json, the graph's checks). Afterwards: edakit check (its HINT
notes among the findings), edakit sim – a block is a starting point that passed the checks once, not a sign-off.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from . import toml_edit
from .design import graph_of_toml, load_graph, natural_key

LIBRARY = Path(__file__).with_name("blocks")


class BlockError(Exception):
    pass


def library():
    return {p.stem: p for p in sorted(LIBRARY.glob("*.json"))}


def load(name=None, file=None):
    path = Path(file) if file else library().get(name)
    if path is None or not path.exists():
        raise BlockError(f"no block '{name or file}' – blocks: {', '.join(library())}")
    return json.loads(path.read_text(encoding="utf-8"))


def library_part(lcsc):
    from . import library as parts_library
    return parts_library.entry(lcsc)


def split_designator(des):
    m = re.fullmatch(r"([A-Za-z]+)(\d+)", des)
    if not m:
        raise BlockError(f"block designator '{des}' is not <letters><number>")
    return m.group(1), int(m.group(2))


def free_numbers(graph):
    """{prefix: highest number in use} of the project graph."""
    top = {}
    for c in graph["components"]:
        m = re.fullmatch(r"([A-Za-z]+)(\d+)", c["designator"])
        if m:
            top[m.group(1)] = max(top.get(m.group(1), 0), int(m.group(2)))
    return top


def without_parts(block, without):
    """The block with the optional parts `without` names left out – their pins out of the nets (a net left without
    pins is not made; one pin alone on an unconnected optional port goes into its component's nc, plan)."""
    optional = block.get("optional") or {}
    unknown = sorted(set(without) - set(optional.get("parts", [])))
    if unknown:
        raise BlockError(f"block {block['name']}: {', '.join(unknown)} is no optional part (optional: "
                         f"{', '.join(optional.get('parts', [])) or 'none'})")
    gone = set(without)
    comps = [dict(c) for c in block["components"] if c["designator"] not in gone]
    nets = [{**n, "pins": [r for r in n["pins"] if r.split(".", 1)[0] not in gone]} for n in block["nets"]]
    return {**block, "components": comps, "nets": nets}     # a net left without pins still lends its range (@port)


def rename_accept(acc, rename):
    """An accept table with the designators its "code place" keys name renamed as the parts are."""
    out = {}
    for key, reason in (acc or {}).items():
        code, sep, place = key.partition(" ")
        if sep:
            des, dot, rest = place.partition(".")
            place = rename.get(des, des) + dot + rest
        out[code + sep + place] = reason
    return out


def plan(block, graph, instance, connect, ground, board=None, without=(), names=None):
    """What `add` would do: (components, new nets, extended nets {name: [pins]}, attributes for existing nets
    {name: {key: value}} such as "bus": "i2c", LCSC numbers used, grounds the block brings). `names`, a dict, gets
    rename {block designator: new}, target {block net: project net} and ranges {block net: [lo, hi]} – what a
    derivation of the block (--set) reads."""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", instance or ""):
        raise BlockError("--as needs a name for this instance: letters, digits, underscore (e.g. STATUS, BUZ)")
    block = without_parts(block, without)
    ports = block.get("ports", {})
    unknown = sorted(set(connect) - set(ports))
    if unknown:
        raise BlockError(f"block {block['name']} has no port {', '.join(unknown)} (ports: {', '.join(ports)})")
    loose = set((block.get("optional") or {}).get("ports", []))       # unconnected, a pin alone goes into nc
    nc_more = {}
    kept = []
    for net in block["nets"]:
        if net["name"] in loose and net["name"] not in connect and len(net["pins"]) == 1:
            des, _, pin = net["pins"][0].partition(".")
            nc_more.setdefault(des, []).append(pin)
            continue
        kept.append(net)
    block = {**block, "nets": kept}
    top = free_numbers(graph)
    rename = {}
    for c in block["components"]:
        prefix, _ = split_designator(c["designator"])
        top[prefix] = top.get(prefix, 0) + 1
        rename[c["designator"]] = f"{prefix}{top[prefix]}"
    existing = {n["name"]: n for n in graph["nets"]}
    target = {}
    for net in block["nets"]:
        name = net["name"]
        if name in ports:
            target[name] = connect.get(name) or (ground if name == "gnd" else f"{instance}_{name}".upper())
        else:
            target[name] = f"{instance}_{name}".upper()
    own = [n for n in target if n not in ports or (n not in connect and n != "gnd")]  # names the block makes up
    clash = sorted(target[n] for n in own if target[n] in existing)
    if clash:
        raise BlockError(f"net {', '.join(clash)} exists already – choose another --as")

    def v_of(name, seen=()):
        net = next(n for n in block["nets"] if n["name"] == name)
        if target[name] in existing:
            return existing[target[name]].get("v")
        v = net.get("v")
        if isinstance(v, str) and v.startswith("@"):
            ref = v[1:]
            if ref in seen or ref not in target:
                raise BlockError(f"block {block['name']}: net {name} takes its range from unknown port {ref}")
            return v_of(ref, seen + (name,))
        if v is None:
            raise BlockError(f"port {name}: net {target[name]} does not exist and the block has no voltage range for "
                             f"it – connect the port to an existing net (--connect {name}=<NET>) or create the net first")
        return v

    comps = []
    for c in block["components"]:
        new = {k: v for k, v in c.items() if k != "designator"}
        new = {"designator": rename[c["designator"]], **{k: (v.replace("{as}", instance) if isinstance(v, str) else v)
                                                          for k, v in new.items()}}
        if c["designator"] in nc_more:
            new["nc"] = list(dict.fromkeys(list(new.get("nc", [])) + nc_more[c["designator"]]))
        if new.get("accept"):
            new["accept"] = rename_accept(new["accept"], rename)
        new["notes"] = (new.get("notes", "") + f" (block {block['name']}, {instance})").strip()
        if board:
            new["board"] = board
        comps.append(new)
    new_nets, extended, attrs = {}, {}, {}
    for net in block["nets"]:
        pins = [f"{rename[p.split('.', 1)[0]]}.{p.split('.', 1)[1]}" for p in net["pins"]]
        if not pins:                       # all its pins were optional parts left out
            continue
        name = target[net["name"]]
        extra = {k: v for k, v in net.items() if k not in ("name", "pins", "v", "notes")}  # e.g. "bus": "i2c"
        if extra.get("accept"):
            extra["accept"] = rename_accept(extra["accept"], rename)
        if name in existing:
            extended.setdefault(name, []).extend(pins)
            attrs.setdefault(name, {}).update(extra)
        elif name in new_nets:  # two ports connected to the same new net
            new_nets[name]["pins"] += pins
            new_nets[name].update(extra)
        else:
            new_nets[name] = {"name": name, "pins": pins, "v": v_of(net["name"]), **extra}
            if net.get("notes"):
                new_nets[name]["notes"] = net["notes"].replace("{as}", instance)
    if names is not None:
        ranges = {}
        for net in block["nets"]:
            try:
                ranges[net["name"]] = v_of(net["name"])
            except BlockError:
                ranges[net["name"]] = None
        names.update(rename=rename, target=target, ranges=ranges)
    lcsc = sorted({c["lcsc"] for c in comps if c.get("lcsc")}, key=natural_key)
    grounds = []
    for name in (block.get("graph") or {}).get("grounds", []):
        if name not in target:
            raise BlockError(f"block {block['name']}: graph.grounds names {name}, which is none of its nets")
        grounds.append(target[name])
    return comps, list(new_nets.values()), extended, attrs, lcsc, grounds


def parts_to_copy(lcsc_numbers, parts_dir, comps):
    """LCSC numbers whose entry must come from the library; an existing project entry must have the block's pins."""
    copy = []
    for lcsc in lcsc_numbers:
        mine = parts_dir / f"{lcsc}.json"
        entry = json.loads(mine.read_text(encoding="utf-8")) if mine.exists() else library_part(lcsc)
        if entry is None:
            raise BlockError(f"{lcsc}: neither in {parts_dir} nor in the parts library – part-search skill first")
        names = {k: v["name"] for k, v in entry["pins"].items()}
        for c in comps:
            if c.get("lcsc") == lcsc and c["pins"] != names:
                raise BlockError(f"{c['designator']}: pins of the block {c['pins']} differ from the parts entry {lcsc} "
                                 f"{names}")
        if not mine.exists():
            copy.append(lcsc)
    return copy


def write_json(path, data):
    """Write like the file was written before: same indent, UTF-8 characters as they are."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^( +)\S", text, re.M)
    path.write_text(json.dumps(data, indent=len(m.group(1)) if m else 1, ensure_ascii=False) + "\n", encoding="utf-8")


def apply(graph, comps, new_nets, extended, attrs, grounds):
    """The block into the graph in memory: its grounds, its components, its pins on existing nets and the attributes
    those lack, its new nets."""
    if grounds:
        graph["grounds"] = list(dict.fromkeys(list(graph.get("grounds") or []) + grounds))
    graph["components"] += comps
    for net in graph["nets"]:
        net["pins"] += extended.get(net["name"], [])
        for key, value in attrs.get(net["name"], {}).items():
            net.setdefault(key, value)
    graph["nets"] += new_nets


# the order of the keys in a table of the TOML form (the writer of the circuit-language sketch); others follow
ORDER = ("type", "label", "part", "lcsc", "value", "bom", "board", "supplier", "spare", "v", "pins", "nc", "accept",
         "verify", "notes")


def toml_lines(obj, skip=()):
    """The lines of a component's or net's table: its keys in ORDER, accept as keys of the table."""
    out = []
    for k in sorted((k for k in obj if k not in skip), key=lambda k: ORDER.index(k) if k in ORDER else len(ORDER)):
        if k == "accept" and isinstance(obj[k], dict) and obj[k]:
            out += [toml_edit.line(code, reason, "accept.") for code, reason in obj[k].items()]
        else:
            out.append(toml_edit.line(k, obj[k]))
    return out


def toml_form(comps):
    """The block's components as a TOML graph holds them: the pin map left out where the component has an LCSC
    number – parts_to_copy found it equal to the parts entry's, and the Design takes the entry's (circuit-language.md,
    decision 3)."""
    return [{k: v for k, v in c.items() if not (k == "pins" and c.get("lcsc"))} for c in comps]


def write_toml(cfg, graph, comps, new_nets, extended, attrs, grounds, records=()):
    """The block into a TOML graph with the line editor: comments and arrangement stay. Written only when the text
    reads back as the graph with the block in it (apply) – else BlockError, and the file stays as it was. Derivation
    records (--set) go at the end, as [[derivations]] tables."""
    from .config import ConfigError
    path, where = Path(cfg.graph), cfg.relative(cfg.graph)
    nets = {n["name"]: n for n in graph["nets"]}
    try:
        doc = toml_edit.Doc(path.read_text(encoding="utf-8"))
        more = [g for g in grounds if g not in (graph.get("grounds") or [])]
        if more and not doc.append((), "grounds", more):
            doc.add_keys((), [toml_edit.line("grounds", more)])
        for c in comps:
            doc.add_table(("components", c["designator"]), toml_lines(c, ("designator",)), after="components",
                          before="nets")
        for name in dict.fromkeys([*extended, *attrs]):
            if not doc.has_table(("nets", name)):
                raise BlockError(f"{where}: net {name} is no table [nets.{toml_edit.key(name)}] – block add writes into "
                                 "the tables of the TOML form (handbook 3.1); write the block's pins there by hand")
            if extended.get(name) and not doc.append(("nets", name), "pins", extended[name]):
                doc.add_keys(("nets", name), [toml_edit.line("pins", extended[name])])
            if keys := {k: v for k, v in attrs.get(name, {}).items() if k not in nets[name]}:
                doc.add_keys(("nets", name), toml_lines(keys))
        for n in new_nets:
            doc.add_table(("nets", n["name"]), toml_lines(n, ("name",)), after="nets", before="cables")
    except toml_edit.TomlEditError as e:
        raise BlockError(f"{where}: {e}") from None
    text = doc.text
    try:
        for rec in records:
            text = text.rstrip("\n") + "\n\n[[derivations]]\n" + "\n".join(toml_edit.line(k, v) for k, v in rec.items())
            text += "\n"
    except toml_edit.TomlEditError as e:
        raise BlockError(f"{where}: {e}") from None
    expected = copy.deepcopy(graph)
    apply(expected, copy.deepcopy(comps), copy.deepcopy(new_nets), extended, attrs, grounds)
    if records:
        expected["derivations"] = [*(expected.get("derivations") or []), *copy.deepcopy(list(records))]
    try:
        got = graph_of_toml(text, where)
    except ConfigError as e:
        got = {"error": str(e)}
    if got != expected:
        off = sorted(k for k in set(got) | set(expected) if got.get(k) != expected.get(k))
        raise BlockError(f"{where}: the block would not read back as written ({', '.join(off)} differ) – the file is "
                         "left as it was; write the block by hand (--dry-run shows it)")
    path.write_text(text, encoding="utf-8")


def entry_of(cfg, key):
    """A parts entry: the project's, else the library's; None for neither."""
    mine = Path(cfg.parts) / f"{key}.json"
    return json.loads(mine.read_text(encoding="utf-8")) if mine.exists() else library_part(key)


def package_of(entry):
    return (entry or {}).get("package") or ((entry or {}).get("footprint") or {}).get("package")


def value_text(x, unit):
    """A value as a block writes it: 330, 4.7k, 100k for a resistor; 100nF for a capacitor."""
    if unit == "Ω":
        for f, p in ((1e6, "M"), (1e3, "k")):
            if x >= f:
                return f"{x / f:g}{p}"
        return f"{x:g}"
    from .circuit import si
    return si(x, unit).replace(" ", "")


def candidates(cfg, kind, package, unit, window):
    """[(key, value)] of the library's and the project's entries of a kind and package whose value lies in a window."""
    from . import library as parts_library
    from .circuit import VALUE_PARAMS
    field = next((k for k, (u, _) in VALUE_PARAMS.items() if u == unit), None)
    seen, out = set(), []
    dirs = [Path(cfg.parts), Path(parts_library.__file__).with_name("parts")]
    lo, hi = window
    for d in dirs:
        for p in sorted(Path(d).glob("*.json")):
            if p.stem in seen or p.name == "README.json":
                continue
            seen.add(p.stem)
            try:
                e = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            v = (e.get("values") or {}).get(field)
            if e.get("kind") == kind and package_of(e) == package and isinstance(v, (int, float)) \
                    and lo * (1 - 1e-9) <= v <= hi * (1 + 1e-9):
                out.append((p.stem, float(v)))
    return sorted(out, key=lambda x: x[1])


def derive_set(cfg, block, instance, sets, choices, comps, names):
    """The records of every derivation of the block whose arguments name a parameter --set sets: the rule evaluated
    with the block's own entries and the ranges of the nets its ports are on; a part outside its window takes the
    entry --part names, else BlockError with the window and the entries in it. -> (records, lines to print)."""
    from .lang.rules import RuleError, Scope, derive, in_window
    from .lang.units import UnitError, parse
    params = block.get("params") or {}
    unknown = sorted(set(sets) - set(params))
    if unknown:
        raise BlockError(f"block {block['name']} has no parameter {', '.join(unknown)} (parameters: "
                         f"{', '.join(params) or 'none'})")
    origin = f"block {block['name']}, {instance}"
    values = {}
    for p, spec in params.items():
        default = parse(spec.get("default"))
        if p in sets:
            try:
                q = parse(sets[p], default.unit if default else None)
            except UnitError as e:
                raise BlockError(f"--set {p}={sets[p]}: {e}") from None
            if q is None:
                raise BlockError(f"--set {p}={sets[p]}: a quantity – 10mA, 3.3V")
            values[p] = (q, f"{origin} (--set {p})")
        elif default is not None:
            values[p] = (default, f"block {block['name']} ({p} default)")
    by_des = {c_new["designator"]: c_new for c_new in comps}
    rename = names["rename"]
    ports = {}
    for port in block.get("ports") or {}:
        net = names["target"].get(port)
        rng = names["ranges"].get(port)
        ports[port] = (net, rng if isinstance(rng, list) else None)
    parts = {}
    for c in block["components"]:
        key = c.get("lcsc")
        entry = entry_of(cfg, key) if key else None
        parts[c["designator"]] = (key, entry, (entry or {}).get("kind") or c.get("type"))
    unknown = sorted(set(choices) - set(parts))
    if unknown:
        raise BlockError(f"--part {', '.join(unknown)}: no part of block {block['name']} ({', '.join(parts)})")
    records, lines = [], []
    for d in block.get("derivations") or []:
        args = [{"name": None if k.isdigit() else k, "text": v} for k, v in d["args"].items()]
        if not any(a["text"] in sets for a in args):
            continue
        targets = [t.partition(".")[0] for t in d["targets"]]

        def scope():
            chosen = {}
            for t in targets:
                key, entry, _ = parts[t]
                v = ((entry or {}).get("values") or {}).get("value_ohm")
                chosen[t] = (v, "Ω", f"{key} values.value_ohm") if v is not None else (None, None, None)
            return Scope(params=values, ports=ports, parts=parts, targets=targets, names=rename, origin=origin,
                         chosen=chosen)
        try:
            recs = derive(d["rule"], args, scope())
        except RuleError as e:
            raise BlockError(str(e)) from None
        again = False
        for rec, t in zip(recs, targets):
            new_des = rename[t]
            lo, hi = rec["series"]["window"]
            unit = rec["derived"]["unit"]
            chosen = (rec.get("chosen") or {}).get("value")
            head = (f"{new_des}: {d['rule']} derives {value_text(rec['derived']['value'], unit)}{unit} – "
                    f"{rec['series']['name']} {value_text(rec['series']['nearest'], unit)}{unit}, window "
                    f"{value_text(lo, unit)}…{value_text(hi, unit)}{unit}")
            key, entry, kind = parts[t]
            if chosen is not None and in_window(rec, chosen) and t not in choices:
                lines.append(f"{head}; the block's {value_text(chosen, unit)}{unit} ({key}) fits – kept")
                continue
            cands = candidates(cfg, kind, package_of(entry), unit, (lo, hi))
            if t not in choices:
                where = (", ".join(f"{k} {value_text(v, unit)}{unit}" for k, v in cands) + f" – --part {t}=KEY"
                         if cands else f"no entry of the library in the window – part-search skill, then --part {t}=KEY")
                raise BlockError(f"{head}; the block's {value_text(chosen, unit) if chosen else '?'}{unit} lies outside. "
                                 f"Entries in the window: {where}")
            pick = choices[t]
            e = entry_of(cfg, pick)
            v = ((e or {}).get("values") or {}).get("value_ohm")
            if e is None or e.get("kind") != kind or v is None:
                raise BlockError(f"--part {t}={pick}: no {kind} entry with a value – in the project's parts or the "
                                 "library")
            if not in_window(rec, v):
                raise BlockError(f"--part {t}={pick}: {value_text(v, unit)}{unit} lies outside the window "
                                 f"{value_text(lo, unit)}…{value_text(hi, unit)}{unit}")
            c = by_des[new_des]
            c["lcsc"], c["value"] = pick, value_text(v, unit)
            if e.get("mpn"):
                c["part"] = e["mpn"]
            c["pins"] = {n: (x or {}).get("name", n) for n, x in (e.get("pins") or {}).items()}
            parts[t] = (pick, e, kind)
            lines.append(f"{head}; --part {t}={pick}: {value_text(v, unit)}{unit}")
            again = True
        if again:
            recs = derive(d["rule"], args, scope())
        records += recs
    return records, lines


def write_circuit(cfg, statement):
    """The usage into a .circuit source, compiled before it stays: a source that no longer compiles is put back, and
    the resolved graph.json beside it is written again."""
    from .config import ConfigError
    from .graph_form import design_of, generated_path, indent_of, render, resolved
    from .lang.write import insert_use
    path = Path(cfg.graph)
    before = path.read_text(encoding="utf-8")
    path.write_text(insert_use(before, statement), encoding="utf-8")
    try:
        source = load_graph(path)
    except ConfigError as e:
        path.write_text(before, encoding="utf-8")
        raise BlockError(f"{cfg.relative(path)}: the usage would not compile – the file is left as it was:\n{e}") from None
    from .design import load_parts
    out = generated_path(cfg)
    g = resolved(source, design_of(path, load_parts(cfg.parts_dirs or cfg.parts), list(cfg.boards), source))
    out.write_text(render(g, indent_of(out)), encoding="utf-8")


def add(cfg, name, instance, connect, board=None, file=None, dry_run=False, without=(), sets=None, choices=None,
        lines=None):
    block = load(name, file)
    toml = Path(cfg.graph).suffix == ".toml"
    circuit = Path(cfg.graph).suffix == ".circuit"
    if toml or circuit:                           # read as every reader does, written with the line editor
        data = graph = load_graph(cfg.graph)
    else:
        data = json.loads(cfg.graph.read_text(encoding="utf-8"))
        graph = data.get("graph", data)
    if board is None and len(cfg.boards) > 1:
        raise BlockError(f"several boards ({', '.join(cfg.boards)}): say which one with --board")
    if board is not None and board not in cfg.boards:
        raise BlockError(f"no board '{board}' in edakit.toml (boards: {', '.join(cfg.boards)})")
    missing = sorted(t for t in connect.values() if t not in {n["name"] for n in graph["nets"]})
    names = {}
    comps, new_nets, extended, attrs, lcsc, grounds = plan(block, graph, instance, connect, graph.get("ground", "GND"),
                                                           board if len(cfg.boards) > 1 else None, without, names)
    records = []
    if sets or choices:
        if not sets:
            raise BlockError("--part goes with --set: it names the entry for a value a derivation asks for")
        records, said = derive_set(cfg, block, instance, sets, choices or {}, comps, names)
        if lines is not None:
            lines += said
        lcsc = sorted({c["lcsc"] for c in comps if c.get("lcsc")}, key=natural_key)
    copy = parts_to_copy(lcsc, cfg.parts, comps)
    if circuit:
        from .lang.write import use_text
        text = use_text(block, instance, connect, comps, names["rename"], sets, without)
        if lines is not None:
            lines.append(("would write" if dry_run else "writes") + f" into {cfg.relative(cfg.graph)}:\n" + text.rstrip())
        if not dry_run:
            from . import library as parts_library
            for n in copy:
                parts_library.copy_into(cfg.parts, n)
            write_circuit(cfg, text)
        return block, comps, new_nets, extended, attrs, copy, missing
    if not dry_run:
        if toml:
            write_toml(cfg, graph, toml_form(comps), new_nets, extended, attrs, grounds, records)
        else:
            apply(graph, comps, new_nets, extended, attrs, grounds)
            if records:
                graph["derivations"] = sorted([*(graph.get("derivations") or []), *records],
                                              key=lambda r: (r["part"], r["key"], r["rule"]))
            write_json(cfg.graph, data)
        from . import library as parts_library
        for n in copy:
            parts_library.copy_into(cfg.parts, n)
    return block, comps, new_nets, extended, attrs, copy, missing


def main(cfg, args):
    try:
        if args.action == "list":
            for name, path in library().items():
                b = json.loads(path.read_text(encoding="utf-8"))
                print(f"{name:<16} {b['title']}\n{'':<16} ports: {', '.join(b['ports'])}")
            print("\nDetails: edakit block show NAME")
            return 0
        if not args.name:
            raise BlockError("which block? edakit block list")
        if args.action == "show":
            b = load(args.name, args.file)
            print(f"{b['name']}: {b['title']}\n\n{b['about']}\n\nPorts:")
            for port, about in b["ports"].items():
                print(f"  {port:<8} {about}")
            print("\nParts:")
            for c in b["components"]:
                print(f"  {c['designator']:<5} {c.get('lcsc', ''):<9} {c.get('value', ''):<8} {c['label']}")
            print("\nNets:")
            for n in b["nets"]:
                print(f"  {n['name']:<8} {', '.join(n['pins'])}" + (f"   v {n['v']}" if "v" in n else ""))
            if b.get("covers"):
                print(f"\nCovers: {', '.join(b['covers'])} (edakit rules …)")
            for note in b.get("notes", []):
                print(f"- {note}")
            return 0
        connect = {}
        for item in args.connect or []:
            port, sep, net = item.partition("=")
            if not sep or not net:
                raise BlockError(f"--connect {item}: expected PORT=NET")
            connect[port] = net
        sets, choices = {}, {}
        for flag, items, into in (("--set", getattr(args, "set", None), sets),
                                  ("--part", getattr(args, "part", None), choices)):
            for item in items or []:
                k, sep, v = item.partition("=")
                if not sep or not k or not v:
                    raise BlockError(f"{flag} {item}: expected NAME=VALUE" if flag == "--set" else
                                     f"{flag} {item}: expected DES=KEY")
                into[k] = v
        said = []
        block, comps, new_nets, extended, attrs, copy, missing = add(cfg, args.name, args.instance, connect,
                                                                     args.board, args.file, args.dry_run,
                                                                     getattr(args, "without", None) or (),
                                                                     sets, choices, said)
    except (BlockError, KeyError, ValueError) as e:
        print(f"edakit block: {e}")
        return 1
    for line in said:
        print(line)
    head = "would add" if args.dry_run else "added"
    print(f"{head} block {block['name']} as {args.instance}:")
    for c in comps:
        print(f"  {c['designator']:<5} {c.get('lcsc', ''):<9} {c.get('value', ''):<8} {c['label']}")
    for name, pins in extended.items():
        print(f"  net {name} (exists) + {', '.join(pins)}"
              + "".join(f", {k}: {v}" for k, v in attrs.get(name, {}).items()))
    for n in new_nets:
        print(f"  net {n['name']} (new, v {n['v']}): {', '.join(n['pins'])}"
              + ("  – created by --connect" if n["name"] in missing else ""))
    if copy:
        print(f"  parts entries {'to copy' if args.dry_run else 'copied'} from the parts library: {', '.join(copy)}")
    for note in block.get("notes", []):
        print(f"- {note}")
    print("Next: edakit check, edakit sim – and the decisions the notes name.")
    return 0
