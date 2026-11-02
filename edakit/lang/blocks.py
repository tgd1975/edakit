"""edakit's building blocks as definitions of the circuit language (T.7): `edakit/blocks/<name>.circuit` is the
source, `edakit/blocks/<name>.json` the generated form `block add` reads (handbook 14.5).

    python -m edakit.lang.blocks           lists every block whose JSON differs from what its source generates
    python -m edakit.lang.blocks --write   writes the JSON of every block from its source

    block_json(definition, parts)   today's block JSON from a definition – its parts with the library entry's pin map,
                                    its nets with pin numbers, ports, covers, optional, notes, test, graph – and the two
                                    keys new to the JSON: params ({name: {"default": "10 mA"}}) and derivations
    from_json(block, parts)         a definition's text from a block JSON – the one-time tool that wrote the sources
    library()                       {name: Def} of the library's sources, read once
"""

from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path

from . import model as m
from .reader import CompileError, read

HERE = Path(__file__).resolve().parent.parent / "blocks"
PARTS = Path(__file__).resolve().parent.parent / "parts"
TOP = ("name", "title", "about", "ports", "params", "components", "nets", "derivations", "covers", "notes", "test",
       "optional", "graph")
HEAD = ("designator", "type", "label", "part", "lcsc", "value")


def library_parts():
    from ..design import load_parts
    return load_parts(PARTS)


def sources():
    return {p.stem: p for p in sorted(HERE.glob("*.circuit"))}


@lru_cache(maxsize=1)
def library():
    """{name: Def} of edakit/blocks/*.circuit; CompileError with every error of a source that does not read."""
    out, errors = {}, []
    for name, path in sources().items():
        src = read(path.read_text(encoding="utf-8"), f"edakit/blocks/{path.name}", "block")
        errors += src.errors
        for d in src.statements:
            if isinstance(d, m.Def):
                out[d.name] = d
    if errors:
        raise CompileError(errors)
    return out


# --- a definition to the block JSON ---------------------------------------------------------------------------------
def _value(key, v):
    from .compile import _value as compiled
    return compiled(key, v)


def block_json(defn, parts):
    """The block JSON of a definition, with pin numbers through the library's entries."""
    from ..graph_form import design_of
    from .compile import check_def
    if errors := check_def(defn):
        raise CompileError(errors)
    comps = []
    for p in (x for x in defn.body if isinstance(x, m.Part)):
        c = {"designator": p.des}
        if p.type is not None:
            c["type"] = p.type
        if p.label is not None:
            c["label"] = p.label
        if p.part is not None:
            c["part"] = p.part
        rest = {}
        for k, v in p.attrs:
            if k.startswith("set:"):
                rest[k[4:]] = v
            else:
                (c if k in HEAD else rest)[k] = _value(k, v)
        c = {k: c[k] for k in HEAD if k in c}
        if p.pins:
            c["pins"] = dict(p.pins)
        else:
            key = c.get("lcsc")
            entry = parts.get(key) if key else None
            if entry is None:
                raise CompileError([_err(p, f"part {p.des}: no library entry {key} – a block's parts are in "
                                            "edakit/parts")])
            c["pins"] = {n: (x or {}).get("name", n) for n, x in (entry.get("pins") or {}).items()}
        if p.nc:
            c["nc"] = [w.word for w in p.nc]
        notes = rest.pop("notes", None)
        c.update(rest)
        if notes is not None:
            c["notes"] = notes
        if p.accepts:
            c["accept"] = {a.key: a.reason for a in p.accepts}
        comps.append(c)
    nets = []
    for n in (x for x in defn.body if isinstance(x, m.Net)):
        row = {"name": n.name, "pins": [w.word for w in n.pins]}
        if n.v is not None:
            row["v"] = n.v if isinstance(n.v, str) else _value("v", n.v)
        notes = None
        for k, v in n.attrs:
            if k == "v":
                row["v"] = v if isinstance(v, str) else _value("v", v)
            elif k == "notes":
                notes = v
            elif k.startswith("set:"):
                row[k[4:]] = v
            else:
                row[k] = _value(k, v)
        if notes is not None:
            row["notes"] = notes
        if n.accepts:
            row["accept"] = {a.key: a.reason for a in n.accepts}
        nets.append(row)
    graph = {"components": [{k: v for k, v in c.items() if k != "nc"} | ({"nc": c["nc"]} if "nc" in c else {})
                            for c in comps], "nets": nets}
    design = design_of(Path(f"edakit/blocks/{defn.name}.circuit"), parts, [], graph)
    for row, resolved in zip(nets, design.graph["nets"]):
        row["pins"] = list(resolved["pins"])
    for c, resolved in zip(comps, design.graph["components"]):
        if "nc" in c:
            c["nc"] = list(resolved["nc"])
    bad = [f"{r}" for row in nets for r in row["pins"] if r.partition(".")[2] not in (
        next((c["pins"] for c in comps if c["designator"] == r.partition(".")[0]), {}))]
    if bad:
        raise CompileError([_err(defn, f"def {defn.name}: {', '.join(bad)} names no pin")])
    out = {"name": defn.name}
    if defn.title is not None:
        out["title"] = defn.title
    if defn.about is not None:
        out["about"] = defn.about
    out["ports"] = {p: (a or "") for p, a in defn.ports}
    if defn.params:
        out["params"] = {a.name: {"default": a.text} for a in defn.params}
    out["components"] = comps
    out["nets"] = nets
    derives = [d for d in defn.body if isinstance(d, m.Derive)]
    if derives:
        out["derivations"] = [{"targets": d.targets, "rule": d.rule,
                               "args": {(a.name or str(k)): a.text for k, a in enumerate(d.args)}} for d in derives]
    if defn.covers:
        out["covers"] = list(defn.covers)
    if defn.notes:
        out["notes"] = list(defn.notes)
    for s in defn.sets:
        out[s.key] = s.value
    optional = {}
    if defn.optional_parts:
        optional["parts"] = list(defn.optional_parts)
    if defn.optional_ports:
        optional["ports"] = list(defn.optional_ports)
    if optional:
        out["optional"] = optional
    return {k: out[k] for k in TOP if k in out}


def _err(node, text):
    from .tokens import LangError
    return LangError(node.file, node.line, text)


def render(block):
    return json.dumps(block, indent=1, ensure_ascii=False) + "\n"


# --- a block JSON to a definition (the one-time tool) ---------------------------------------------------------------
def from_json(block, parts):
    """The text of a definition from a block JSON: the word rule for its pins, its keys by the attribute table."""
    from ..graph_form import design_of
    from . import schema
    from .convert import attrs, pin_words, string, word
    from .fmt import format
    from .units import Quantity, format as quantity
    graph = {"components": [dict(c) for c in block["components"]], "nets": [dict(n) for n in block["nets"]]}
    design = design_of(Path("block.json"), parts, [], graph)
    head = f"def {block['name']}"
    params = block.get("params") or {}
    if params:
        head += " (" + ", ".join(f"{k} = {v['default']}" for k, v in params.items()) + ")"
    out = [head]
    if "title" in block:
        out.append(f"  title {string(block['title'])}")
    if "about" in block:
        out.append(f"  about {string(block['about'])}")
    for p, about in (block.get("ports") or {}).items():
        out.append(f"  port {p} {string(about)}" if about else f"  port {p}")
    for c in block["components"]:
        des = c["designator"]
        line = ["  part", des, word(c["type"], True) if c.get("type") else "-",
                word(c["part"], True) if c.get("part") is not None else "-"]
        w, more = attrs(c, schema.COMPONENT, {"designator", "type", "part", "label", "pins", "nc", "accept", "notes"},
                        f"{block['name']}.{des}")
        line += w
        if "label" in c:
            line.append(string(c["label"]))
        out.append(" ".join(line))
        if c.get("nc"):
            nc = [x.partition(".")[2] for x in pin_words(design, [f"{des}.{p}" for p in c["nc"]], False)]
            out.append("    nc " + " ".join(word(x) for x in nc))
        out += [f"    {x}" for x in more]
        for k, v in (c.get("accept") or {}).items():
            out.append(f"    accept {word(k)} {string(v)}")
        if "notes" in c:
            out.append(f"    notes {string(c['notes'])}")
    for n in block["nets"]:
        line = ["  net", word(n["name"])]
        v = n.get("v")
        if isinstance(v, str):
            line.append(v)
        elif isinstance(v, list):
            line.append(quantity(Quantity(v[0], v[1], "V")))
        line += pin_words(design, list(n["pins"]))
        w, more = attrs(n, schema.NET, {"name", "pins", "v", "accept", "notes"}, f"{block['name']}.{n['name']}")
        out.append(" ".join(line + w))
        out += [f"    {x}" for x in more]
        for k, val in (n.get("accept") or {}).items():
            out.append(f"    accept {word(k)} {string(val)}")
        if "notes" in n:
            out.append(f"    notes {string(n['notes'])}")
    for d in block.get("derivations") or []:
        args = ", ".join(v if k.isdigit() else f"{k} = {v}" for k, v in d["args"].items())
        out.append(f"  derive {' '.join(d['targets'])} {d['rule']}({args})")
    if block.get("covers"):
        out.append("  covers " + " ".join(block["covers"]))
    for x in block.get("notes") or []:
        out.append(f"  notes {string(x)}")
    for key in ("test", "graph"):
        if key in block:
            out.append(f"  set {key} {json.dumps(block[key], ensure_ascii=False)}")
    opt = block.get("optional") or {}
    for key in ("parts", "ports"):
        if opt.get(key):
            out.append(f"  optional {key} " + " ".join(opt[key]))
    return format("\n".join(out) + "\n", f"edakit/blocks/{block['name']}.circuit", role="block")


# --- the command ------------------------------------------------------------------------------------------------------
def generated():
    """{name: (path of the JSON, its text as generated)} of every block source."""
    parts = library_parts()
    return {name: (HERE / f"{name}.json", render(block_json(d, parts))) for name, d in library().items()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write the JSON of every block from its source")
    args = ap.parse_args(argv)
    try:
        gen = generated()
    except CompileError as e:
        print(f"edakit/lang/blocks: {e}", file=sys.stderr)
        return 1
    stale = [name for name, (path, text) in gen.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
    if args.write:
        for name in stale:
            gen[name][0].write_text(gen[name][1], encoding="utf-8")
            print(f"written: edakit/blocks/{name}.json")
        return 0
    for name in stale:
        print(f"differs: edakit/blocks/{name}.json – python -m edakit.lang.blocks --write")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
