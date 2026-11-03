"""The compiler of the circuit language: a project's `.circuit` source → the graph (language 6).

    compile_path(path)   the graph of a `.circuit` file as load_graph gives it – a dict as graph_of_toml gives a TOML
                         graph's: components, nets and cables as lists, pin words as written with a part's aliases
                         replaced; CompileError with every error (PATH:LINE: TEXT)
    compile(cfg)         (graph, SourceMap) of a project
    resolved_of(path)    (resolved graph, SourceMap): pin numbers everywhere, every pin map – what `edakit graph json`
                         writes beside the source

The phases: read (reader.py), namespace, variant chain, parameters, loops, usages, parts entries and pins,
derivations, assembly, source map. The project is found from the file: edakit.toml upward from it, its
`[project] parts`. A word that names no pin is an error at its statement (language 12, item 17); the Design of
design.py reads every word, so the compiler and the checks never disagree about what a word means.
"""

from __future__ import annotations

import copy
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import model as m
from .reader import CompileError, read
from .tokens import LangError
from .units import Quantity

GRAPH_ORDER = ("name", "version", "date", "description", "purpose", "conventions", "components", "nets", "cables",
               "layout", "locks", "accept", "ground", "grounds")
COMPONENT_HEAD = ("designator", "type", "label", "part", "lcsc")


@dataclass
class SourceMap:
    """Where each element of the graph was written: {kind: {name: {"file", "line"}}} – kept in memory for the language
    server, written by `edakit graph json --map FILE`; nothing of it is in the graph."""
    components: dict = field(default_factory=dict)
    nets: dict = field(default_factory=dict)
    usages: dict = field(default_factory=dict)
    locks: dict = field(default_factory=dict)
    accepts: dict = field(default_factory=dict)
    derivations: dict = field(default_factory=dict)

    def put(self, kind, name, node, **more):
        getattr(self, kind).setdefault(name, {"file": node.file, "line": node.line, **more})

    def as_dict(self):
        return {k: getattr(self, k) for k in ("components", "nets", "usages", "locks", "accepts", "derivations")}


@dataclass
class Model:
    """The flat model of a project's source: its statements in order, the definitions and parameters by name."""
    root: Path
    parts_dirs: list
    sources: list = field(default_factory=list)
    statements: list = field(default_factory=list)
    defs: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    jobs: list = field(default_factory=list)          # the derivations of the usages, evaluated at assembly


# --- the project ----------------------------------------------------------------------------------------------------
def project_of(path):
    """(root, parts_dirs) of a source file: the folder of the edakit.toml found upward from it and its [project] parts
    – a string or a list of folders, relative to it; without an edakit.toml the file's folder and no parts."""
    path = Path(path).resolve()
    for d in [path.parent, *path.parent.parents]:
        toml = d / "edakit.toml"
        if toml.is_file():
            try:
                project = tomllib.loads(toml.read_text(encoding="utf-8")).get("project") or {}
            except tomllib.TOMLDecodeError:
                project = {}
            parts = project.get("parts", "hardware/parts")
            parts = parts if isinstance(parts, list) else [parts]
            return d, [p if Path(p).is_absolute() else d / p for p in map(Path, parts)]
    return path.parent, []


def load_parts(dirs):
    """{key: entry} over several folders – the first that has an entry wins."""
    from ..design import load_parts as one
    out = {}
    for d in dirs:
        for key, entry in one(d).items():
            out.setdefault(key, entry)
    return out


def _name(path, root):
    """A file as an error names it: relative to the project's root – a variant's base as ../../hardware/…"""
    import os
    path = Path(path)
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(os.path.relpath(path.resolve(), Path(root).resolve())).as_posix()


def load_sources(path, root):
    """[Source] of a project: the main file and every file it includes, each read once – an Include knows its Source
    (`.source`); a cycle, a missing file and a path outside the project are errors at the include (T.13)."""
    root = Path(root).resolve()
    out, errors, seen = [], [], {}

    def visit(p, stack, at=None):
        p = p.resolve()
        if p in stack:
            chain = " → ".join(_name(x, root) for x in [*stack, p])
            errors.append(LangError(at.file, at.line, f"include {at.path}: a cycle – {chain}"))
            return None
        if p in seen:
            return seen[p]
        try:
            text = p.read_text(encoding="utf-8")
        except (FileNotFoundError, IsADirectoryError):
            if at is None:
                raise CompileError([LangError(_name(p, root), 0, "no such file")]) from None
            errors.append(LangError(at.file, at.line, f"include {at.path}: no such file"))
            return None
        src = read(text, _name(p, root), "graph")
        seen[p] = src
        out.append(src)
        if at is not None:
            src.included = True
            for st in src.statements[:1]:
                if isinstance(st, (m.GraphHead, m.Variant)):
                    errors.append(LangError(st.file, st.line, f"{'graph' if isinstance(st, m.GraphHead) else 'variant'}"
                                                              f" in an included file – it stands in the main file"))
        own = project_of(p)[0].resolve()                # a path is relative to the edakit.toml of its file
        body = src.variant.body if src.variant is not None else src.statements
        for st in [*body, *(src.statements[1:] if src.variant is not None else [])]:
            if isinstance(st, m.Include):
                target = (own / st.path).resolve()
                if not target.is_relative_to(own):
                    errors.append(LangError(st.file, st.line, f"include {st.path}: outside the project"))
                    continue
                st.source = visit(target, [*stack, p], st)
        if src.variant is not None:
            v = src.variant
            base = (own / v.base).resolve()
            if base in [x.resolve() for x in [*stack, p]]:
                chain = " → ".join(_name(x, root) for x in [*stack, p, base])
                errors.append(LangError(v.file, v.line, f"variant {v.name} of {v.base}: the chain loops – {chain}"))
            elif not base.is_file():
                errors.append(LangError(v.file, v.line, f"variant {v.name} of {v.base}: no such file"))
            else:
                v.base_source = visit(base, [*stack, p], None) if base not in seen else seen[base]
        return src

    visit(Path(path), [])
    if errors:
        raise CompileError([e for s in out for e in s.errors] + errors)
    return out


# --- namespace ------------------------------------------------------------------------------------------------------
def resolve(sources, root, parts_dirs):
    """The Model of the sources: their statements in order, with the declarations checked across the files – a
    designator, a definition, a parameter or an instance twice is an error that names both places."""
    model = Model(Path(root), list(parts_dirs), list(sources))
    errors = [e for s in sources for e in s.errors]
    seen = {}

    def declare(kind, name, node):
        first = seen.get((kind, name))
        if first is not None:
            errors.append(LangError(node.file, node.line, f"{kind} {name} twice – first at {first.file}:{first.line}"))
        else:
            seen[(kind, name)] = node

    from .expand import expand_for
    done = set()

    def flat(src):
        """The statements of a source with every include's put in its place, a file once."""
        if id(src) in done:
            return []
        done.add(id(src))
        out = []
        for s in src.statements:
            if isinstance(s, m.Include):
                out += flat(s.source) if getattr(s, "source", None) is not None else []
            elif isinstance(s, m.For):
                out += expand_for(s)
            else:
                out.append(s)
        return out

    def statements_of(src):
        """A main file's statements; a variant's: its base's, with its own applied – redefinitions merged, additions
        appended (language 5.9)."""
        if src.variant is None:
            return flat(src)
        base = getattr(src.variant, "base_source", None)
        out = statements_of(base) if base is not None else []
        body = [*src.variant.body, *src.statements[1:]]
        own = m.Source(src.file, statements=body)
        done.discard(id(own))
        errors.extend(apply_variant(out, flat(own), src.variant))
        return out

    for src in sources[:1]:
        for st in statements_of(src):
            model.statements.append(st)
            if isinstance(st, m.Part):
                declare("part", st.des, st)
            elif isinstance(st, m.Def):
                declare("def", st.name, st)
                model.defs[st.name] = st
            elif isinstance(st, m.Param):
                declare("param", st.name, st)
                model.params[st.name] = st
            elif isinstance(st, m.Use):
                declare("use", st.instance, st)
    for d in model.defs.values():
        errors += check_def(d)
    if errors:
        raise CompileError(errors)
    if any(isinstance(st, m.Use) for st in model.statements):
        from .blocks import library
        lib = library()
        for name in sorted(set(model.defs) & set(lib)):
            d = model.defs[name]
            note = f"{d.file}:{d.line}: def {name}: the project's definition shadows edakit's block {name}"
            if note not in _SAID:                    # once a run – a command compiles its source more than once
                _SAID.add(note)
                print(note, file=sys.stderr)
        model.defs = {**lib, **model.defs}
    return model


_SAID = set()


def _merge_attrs(base, new):
    """Attributes of a redefinition over the base's: a key given replaces the base's; `bom yes` sets it back."""
    out = list(base)
    for k, v in new:
        out = [(x, y) for x, y in out if x != k]
        if not (k == "bom" and v is True):
            out.append((k, v))
    return out


def _merge_accepts(base, new):
    keep = {a.key: a for a in base}
    for a in new:
        if a.reason is None:
            keep.pop(a.key, None)
        else:
            keep[a.key] = a
    return list(keep.values())


def _merge_part(base, new):
    out = copy.copy(base)
    out.file, out.line = new.file, new.line
    if new.type is not None:
        out.type = new.type
    if new.part is not None:
        out.part = new.part
    if new.label is not None:
        out.label = new.label
    entry_changed = new.part is not None or any(k == "lcsc" for k, _ in new.attrs)
    out.attrs = _merge_attrs(base.attrs, new.attrs)
    out.pins = list(new.pins) if new.pins else ([] if entry_changed else list(base.pins))
    out.nc = list(new.nc) if new.nc else list(base.nc)
    out.aliases = list(new.aliases) if new.aliases else list(base.aliases)
    out.accepts = _merge_accepts(base.accepts, new.accepts)
    return out


def _merge_use(base, new):
    out = copy.copy(base)
    params = {a.name: a for a in base.params}
    for a in new.params:
        params[a.name] = a
    out.params = list(params.values())
    bindings = {b.left: b for b in base.bindings}
    for b in new.bindings:
        old = bindings.get(b.left)
        if old is not None and old.part is not None and b.part is not None:
            nb = copy.copy(b)
            nb.part = _merge_part(old.part, b.part)
            nb.part.des = b.right
            bindings[b.left] = nb
        else:
            bindings[b.left] = b
    out.bindings = list(bindings.values())
    out.without = list(new.without) or list(base.without)
    out.satisfies = list(new.satisfies) or list(base.satisfies)
    out.decision = list(new.decision) or list(base.decision)
    return out


def apply_variant(out, statements, variant):
    """A variant's statements applied to its base's flat list, in place: a part, a usage or a parameter of the base
    redefined where it stands, a net's statement appended as a redefinition, everything else appended; a usage or a
    parameter the base does not have is an error."""
    errors = []
    where = {}
    for k, st in enumerate(out):
        if isinstance(st, m.Part):
            where[("part", st.des)] = k
        elif isinstance(st, m.Use):
            where[("use", st.instance)] = k
        elif isinstance(st, m.Param):
            where[("param", st.name)] = k
    bound = {}
    for k, st in enumerate(out):
        if isinstance(st, m.Use):
            for b in st.bindings:
                bound[b.right] = (k, b.left)
    for st in statements:
        if isinstance(st, m.Part) and ("part", st.des) in where:
            k = where[("part", st.des)]
            out[k] = _merge_part(out[k], st)
        elif isinstance(st, m.Part) and st.des in bound:          # a part a usage of the base binds: its binding
            k, left = bound[st.des]
            nb = m.Binding(st.file, st.line, left=left, right=st.des, part=copy.copy(st))
            nb.part.head = False
            out[k] = _merge_use(out[k], m.Use(st.file, st.line, definition=out[k].definition,
                                              instance=out[k].instance, bindings=[nb]))
        elif isinstance(st, m.Use):
            k = where.get(("use", st.instance))
            if k is None:
                errors.append(LangError(st.file, st.line, f"use {st.instance}: no usage {st.instance} in the base of "
                                                          f"variant {variant.name} – a new one needs its definition and "
                                                          "every binding"))
                out.append(st)
                where[("use", st.instance)] = len(out) - 1
            elif out[k].definition != st.definition:
                errors.append(LangError(st.file, st.line, f"use {st.instance}: the base uses def {out[k].definition}"
                                                          f" – a variant cannot change the definition"))
            else:
                out[k] = _merge_use(out[k], st)
        elif isinstance(st, m.Param):
            k = where.get(("param", st.name))
            if k is None:
                errors.append(LangError(st.file, st.line, f"param {st.name}: the base has no parameter {st.name}"))
            else:
                out[k] = st
        else:
            if isinstance(st, m.Net):
                st.redefine = True
            out.append(st)
            if isinstance(st, m.Part):
                where[("part", st.des)] = len(out) - 1
    return errors


def check_def(defn):
    """The errors of a definition by itself (language 5.5): a port that is none of its nets, a part or a net named twice,
    a derivation whose target is no part of it, an optional part or port it does not have."""
    errors, parts, nets = [], {}, {}
    for st in defn.body:
        if isinstance(st, m.Part):
            if st.des in parts:
                errors.append(LangError(st.file, st.line, f"def {defn.name}: part {st.des} twice – first at line "
                                                          f"{parts[st.des].line}"))
            parts.setdefault(st.des, st)
        elif isinstance(st, m.Net):
            if st.name in nets:
                errors.append(LangError(st.file, st.line, f"def {defn.name}: net {st.name} twice – first at line "
                                                          f"{nets[st.name].line}"))
            nets.setdefault(st.name, st)
    for port, _ in defn.ports:
        if port not in nets:
            errors.append(LangError(defn.file, defn.line, f"def {defn.name}: port {port} is none of its nets – "
                                                          f"nets: {', '.join(nets) or 'none'}"))
    for st in defn.body:
        if isinstance(st, m.Derive):
            for target in st.targets:
                des = target.partition(".")[0]
                if des not in parts:
                    errors.append(LangError(st.file, st.line, f"derive {target}: {des} is no part of def {defn.name}"
                                                              f" – parts: {', '.join(parts)}"))
    for des in defn.optional_parts:
        if des not in parts:
            errors.append(LangError(defn.file, defn.line, f"def {defn.name}: optional part {des} is no part of it"))
    for port in defn.optional_ports:
        if port not in dict(defn.ports):
            errors.append(LangError(defn.file, defn.line, f"def {defn.name}: optional port {port} is no port of it"))
    return errors


def expand(model):
    """Usages expanded in place (T.11, expand.py); the loops were expanded with the namespace, so that what they make
    is declared as what is written."""
    from .expand import expand_uses
    statements, jobs, errors = expand_uses(model.statements, model.defs)
    if errors:
        raise CompileError(errors)
    model.statements, model.jobs = statements, jobs
    return model


def evaluate(jobs, design, smap):
    """The derivation records of the usages: each rule evaluated with the usage's values, the bound nets' ranges and
    the bound parts' entries (language 7); a rule that cannot evaluate is an error at the derivation and the usage."""
    from ..engines.derive import part_value
    from .rules import RuleError, Scope, derive
    nets = {n["name"]: n for n in design.graph.get("nets") or []}
    records, errors = [], []
    for job in jobs:
        d = job.derive
        parts = {}
        for local, proj in job.names.items():
            key = design.entry_key(proj)
            entry = design.parts.get(key) if key else None
            parts[local] = (key, entry, (entry or {}).get("kind") or design.comps[proj].get("type"))
        ports = {p: (net, (nets.get(net) or {}).get("v")) for p, net in job.ports.items() if net}
        targets = [t.partition(".")[0] for t in d.targets]
        chosen = {}
        for t in targets:
            proj = job.names.get(t)
            v = part_value(design, proj, "Ω") if proj in design.comps else None
            key = design.entry_key(proj) if proj in design.comps else None
            chosen[t] = (v, "Ω", f"{key} values.value_ohm" if key else f"{proj} value")
        scope = Scope(params=job.params, ports=ports, parts=parts, targets=targets, names=job.names,
                      origin=job.origin, chosen=chosen)
        try:
            recs = derive(d.rule, [{"name": a.name, "text": a.text} for a in d.args], scope)
        except RuleError as e:
            errors.append(LangError(job.use.file, job.use.line, f"use {job.use.instance}: {e} – derive at "
                                                                f"{d.file}:{d.line}"))
            continue
        for r in recs:
            smap.put("derivations", f"{r['part']}.{r['key']}", job.use, derive=f"{d.file}:{d.line}")
        records += recs
    return sorted(records, key=lambda r: (r["part"], r["key"], r["rule"])), errors


# --- assembly -------------------------------------------------------------------------------------------------------
def _num(x):
    return int(x) if isinstance(x, float) and x.is_integer() else x


def _range(q):
    return [_num(q.lo), _num(q.hi)]


def _value(key, v):
    """An attribute's value as the graph holds it: a range as [lo, hi], a point of pwm_hz as a number."""
    if isinstance(v, Quantity):
        if key == "pwm_hz" and v.point:
            return _num(v.lo)
        return _range(v)
    return v


def _set(target, key, value):
    """A `set` key: one level down for a dotted key (locks.doc_pin_table, purpose.radio)."""
    head, dot, rest = key.partition(".")
    if dot:
        sub = target.setdefault(head, {})
        if isinstance(sub, dict):
            sub[rest] = value
    else:
        target[key] = value


class Assembler:
    def __init__(self, model):
        self.model = model
        self.errors = []
        self.map = SourceMap()
        self.g = {}
        self.comps, self.nets, self.net_nodes = {}, {}, {}
        self.cables, self.layout, self.locks, self.accept = [], {}, {}, {}
        self.sets = []                                      # graph keys set by `set`, in order
        self.aliases = {}                                   # des -> {alias: word}
        self.own_pins = set()                               # designators with a pin map of their own (pins …)
        self.places = {}                                    # id(PinWord-like) -> node, for errors

    def err(self, node, msg):
        self.errors.append(LangError(node.file, node.line, msg))

    def param(self, node, name):
        """The value of a project parameter where a quantity is expected; an error for a name without one."""
        p = self.model.params.get(name)
        if p is None or not isinstance(p.value, Quantity):
            have = ", ".join(sorted(self.model.params)) or "none"
            self.err(node, f"{name}: no parameter with a quantity – parameters: {have}" if not name.startswith("@")
                     else f"{name}: a port's range, only inside a definition")
            return None
        return p.value

    def word(self, w):
        """A pin word with its part's alias replaced."""
        des, dot, rest = w.partition(".")
        if dot and rest in self.aliases.get(des, {}):
            return f"{des}.{self.aliases[des][rest]}"
        return w

    def run(self):
        for st in self.model.statements:
            if isinstance(st, m.Part):
                self.aliases[st.des] = dict(st.aliases)
                if st.aliases:
                    self.places.setdefault("alias", []).append(st)
        for st in self.model.statements:
            handler = getattr(self, "on_" + type(st).__name__.lower(), None)
            if handler is None:
                self.err(st, f"{type(st).__name__.lower()}: not compiled yet")
                continue
            handler(st)
        g = self.g
        if self.comps:
            g["components"] = list(self.comps.values())
        else:
            g["components"] = []
        g["nets"] = list(self.nets.values())
        if self.cables:
            g["cables"] = self.cables
        if self.layout:
            g["layout"] = self.layout
        if self.locks:
            g.setdefault("locks", {})["pins"] = self.locks
        if self.accept:
            g["accept"] = self.accept
        for key, value in self.sets:
            _set(g, key, value)
        order = [k for k in GRAPH_ORDER if k in g] + [k for k in g if k not in GRAPH_ORDER and k != "derivations"]
        order += ["derivations"] if "derivations" in g else []
        return {k: g[k] for k in order}

    # the graph as a whole
    def on_graphhead(self, st):
        for k in ("name", "version", "date"):
            if getattr(st, k) is not None:
                self.g[k] = getattr(st, k)

    def on_description(self, st):
        self.g["description"] = st.text

    def on_purpose(self, st):
        self.g["purpose"] = {**self.g.get("purpose", {}), **st.fields}

    def on_convention(self, st):
        self.g.setdefault("conventions", {})[st.key] = st.text

    def on_ground(self, st):
        self.g["ground"] = st.name

    def on_grounds(self, st):
        self.g.setdefault("grounds", []).extend(st.names)

    def on_accept(self, st):
        if st.reason is None:
            self.accept.pop(st.key, None)
        else:
            self.accept[st.key] = st.reason
        self.map.put("accepts", st.key, st)

    def on_lock(self, st):
        self.locks[self.word(st.pin)] = st.net
        self.map.put("locks", st.pin, st)
        self.places.setdefault("locks", []).append((st, self.word(st.pin)))

    def on_set(self, st):
        self.sets.append((st.key, st.value))

    def on_param(self, st):
        pass                                                # read where a quantity is expected (T.13)

    def on_def(self, st):
        pass                                                # a definition is not in the graph; its usages are

    # parts
    def on_part(self, st):
        if getattr(st, "expanded", None) is not None:
            use, defpart = st.expanded
            self.map.put("usages", use.instance, use)
            self.map.put("components", st.des, st, use=f"{use.file}:{use.line}",
                         definition=f"{defpart.file}:{defpart.line}")
        c = {"designator": st.des}
        if st.type is not None:
            c["type"] = st.type
        if st.label is not None:
            c["label"] = st.label
        if st.part is not None:
            c["part"] = st.part
        for key, value in st.attrs:
            if key.startswith("set:"):
                _set(c, key[4:], value)
            else:
                c[key] = _value(key, value)
        if st.pins:
            c["pins"] = dict(st.pins)
            self.own_pins.add(st.des)
        if st.nc:
            c["nc"] = [self.word(f"{st.des}.{p.word}").partition(".")[2] for p in st.nc]
            self.places.setdefault("nc", []).append((st, [(p, self.word(f"{st.des}.{p.word}")) for p in st.nc]))
        if st.accepts:
            acc = c.setdefault("accept", {})
            for a in st.accepts:
                if a.reason is not None:
                    acc[a.key] = a.reason
        head = {k: c[k] for k in COMPONENT_HEAD if k in c}
        self.comps[st.des] = {**head, **{k: v for k, v in c.items() if k not in head}}
        self.map.put("components", st.des, st)

    # nets
    def on_net(self, st):
        n = self.nets.get(st.name)
        if n is None:
            n = self.nets[st.name] = {"name": st.name, "pins": []}
            self.net_nodes[st.name] = st
            self.map.put("nets", st.name, st)
        redefine = getattr(st, "redefine", False)
        if redefine and st.without:
            for w in st.without:
                word = self.word(w.word)
                if word in n["pins"]:
                    n["pins"].remove(word)
                    self.places["net"] = [x for x in self.places.get("net", []) if not (x[1] == st.name
                                                                                        and x[2] == word)]
                else:
                    self.err(w, f"net {st.name}: without {w.word} – not on the net (pins: {', '.join(n['pins'])})")
        if redefine:
            n.pop("v", None) if st.v is not None else None
            for key, _ in st.attrs:
                n.pop(key, None)
        if st.v is not None:
            if "v" in n:
                first = self.net_nodes[st.name]
                self.err(st, f"net {st.name}: the range given twice – first at {first.file}:{first.line}")
            elif isinstance(st.v, str):
                q = self.param(st, st.v)
                if q is not None:
                    n["v"] = _range(q)
            else:
                n["v"] = _range(st.v)
        for p in st.pins:
            w = self.word(p.word)
            n["pins"].append(w)
            self.places.setdefault("net", []).append((p, st.name, w))
            if p.locked:
                self.locks[w] = st.name
                self.map.put("locks", p.word, p)
                self.places.setdefault("locks", []).append((p, w))
        for key, value in st.attrs:
            if key.startswith("set:"):
                _set(n, key[4:], value)
                continue
            if key in n:
                first = self.net_nodes[st.name]
                self.err(st, f"net {st.name}: {key} given twice – first at {first.file}:{first.line}")
                continue
            if isinstance(value, str) and key in ("v", "pwm_hz"):
                q = self.param(st, value)
                if q is not None:
                    n[key] = _value(key, q)
                continue
            n[key] = _value(key, value)
        if st.accepts:
            acc = n.setdefault("accept", {})
            for a in st.accepts:
                if a.reason is not None:
                    acc[a.key] = a.reason
                else:
                    acc.pop(a.key, None)
            if not acc:
                n.pop("accept")

    # cables and the layout
    def on_cable(self, st):
        c = {"name": st.name, "from": st.frm, "to": st.to, "pins": {}}
        for a, b in st.pairs:
            wa = self.word(f"{st.frm}.{a}").partition(".")[2]
            wb = self.word(f"{st.to}.{b}").partition(".")[2]
            c["pins"][wa] = wb
            self.places.setdefault("cable", []).append((st, f"{st.frm}.{wa}", f"{st.to}.{wb}"))
        for key, value in st.attrs:
            if key.startswith("set:"):
                _set(c, key[4:], value)
            else:
                c[key] = _value(key, value)
        self.cables.append(c)

    def on_layout(self, st):
        lay = self.layout
        if st.kind in ("fixed", "edge"):
            lay.setdefault(st.kind, []).extend(st.parts)
        elif st.kind == "near":
            hosts = st.parts[1:]
            lay.setdefault("near", {})[st.parts[0]] = hosts[0] if len(hosts) == 1 else hosts
        elif st.kind == "note":
            lay.setdefault("notes", []).append(st.text)
        elif st.kind == "loop":
            lp = {"a": self.word(st.a), "b": self.word(st.b)}
            if st.limit is not None:
                lp["max_mm"] = _num(st.limit)
            if st.text is not None:
                lp["what"] = st.text
            lay.setdefault("loops", []).append(lp)
            self.places.setdefault("loop", []).append((st, lp["a"], lp["b"]))
        elif st.kind == "apart":
            ap = {"a": st.a, "b": st.b}
            if st.limit is not None:
                ap["min_mm"] = _num(st.limit)
            if st.text is not None:
                ap["what"] = st.text
            lay.setdefault("apart", []).append(ap)


# --- pins through the Design ----------------------------------------------------------------------------------------
def _candidates(design, des, aliases):
    """The words a part's pins may be written by: its entry's names and roles, then its aliases."""
    pins = (design.comps.get(des) or {}).get("pins") or {}
    roles = design._roles(des)
    words = list(dict.fromkeys([*[str(v) for v in pins.values()], *[r for r in roles.values() if r]]))
    words = [w for w in words if not re.search(r'[\s"#]', w)]           # OE#: by its role or number here
    return words + [f"{a} (alias)" for a in aliases]


def check_pins(asm, design):
    """Every pin word to its pins through the Design; one that names none – or several where one is meant – is an
    error at its statement, with the candidates; a pin in two nets, or in a net and nc, names both places."""
    errors = []

    def place(node):
        return f"{node.file}:{node.line}"

    def names(node, ref, one=False):
        des, dot, word = ref.partition(".")
        if not dot or des not in design.comps:
            errors.append(LangError(node.file, node.line, f"{ref}: no part {des}" + (
                f" – parts: {', '.join(sorted(design.comps)[:12])}" if design.comps else "")))
            return []
        hits = design.resolve(des, word)
        if design.entry_key(des) is None and des not in asm.own_pins and not word.isdigit():
            c = design.comps[des]
            key = c.get("lcsc") or c.get("part") or des
            errors.append(LangError(node.file, node.line, f"{ref}: {des} has no parts entry ({key}) – edakit part add "
                                                          f"{key}, write the pin's number, or the map: pins 1=NAME …"))
            return []
        if not hits:
            cands = _candidates(design, des, asm.aliases.get(des, {}))
            errors.append(LangError(node.file, node.line, f"{ref}: names no pin of {des} – its pins: "
                                                          f"{', '.join(cands[:24])}"))
            return []
        if one and len(hits) > 1:
            errors.append(LangError(node.file, node.line, f"{ref}: names {len(hits)} pins of {des} "
                                                          f"({', '.join(hits)}) – one is meant here"))
        return [f"{des}.{h}" for h in hits]

    where = {}
    for node, net, ref in asm.places.get("net", []):
        for r in names(node, ref):
            if r in where:
                first_net, first = where[r]
                what = f"twice in net {net}" if first_net == net else f"in net {net} and in {first_net}"
                errors.append(LangError(node.file, node.line, f"{ref}: {r} {what} – first at {place(first)}"))
            else:
                where[r] = (net, node)
    for st, items in asm.places.get("nc", []):
        for p, ref in items:
            for r in names(p, ref):
                if r in where:
                    errors.append(LangError(p.file, p.line, f"{ref}: in nc of {st.des} and in net {where[r][0]} – at "
                                                            f"{place(where[r][1])}"))
    for node, ref in asm.places.get("locks", []):
        if not isinstance(node, m.PinWord):
            names(node, ref)
    for st, a, b in asm.places.get("cable", []) + asm.places.get("loop", []):
        names(st, a, one=True)
        names(st, b, one=True)
    for st in asm.places.get("alias", []):
        for alias, word in st.aliases:
            if st.des in design.comps and not design.resolve(st.des, word):
                cands = _candidates(design, st.des, {})
                errors.append(LangError(st.file, st.line, f"alias {alias} = {word}: names no pin of {st.des} – its "
                                                          f"pins: {', '.join(cands[:24])}"))
    return errors


def assemble(model, parts=None):
    """(graph, SourceMap): the graph in today's key order, every pin word checked through the Design."""
    from ..graph_form import design_of
    asm = Assembler(model)
    graph = asm.run()
    if asm.errors:
        raise CompileError(asm.errors)
    parts = load_parts(model.parts_dirs) if parts is None else parts
    design = design_of(model.root / "graph.circuit", parts, [], graph)
    errors = check_pins(asm, design)
    if errors:
        raise CompileError(errors)
    if model.jobs:
        records, errors = evaluate(model.jobs, design, asm.map)
        if errors:
            raise CompileError(errors)
        if records:
            graph["derivations"] = records
            design.graph["derivations"] = records
    return graph, asm.map, design


def build(path, parts=None):
    """(graph, SourceMap, Design) of a `.circuit` file."""
    root, dirs = project_of(path)
    model = expand(resolve(load_sources(path, root), root, dirs))
    return assemble(model, parts)


def build_text(text, path, root, parts):
    """(graph, SourceMap, Design) of a source not written yet – the converter reads its own text back with it."""
    src = read(text, _name(path, root), "graph")
    model = expand(resolve([src], root, []))
    return assemble(model, parts)


def compile_path(path):
    """The graph of a `.circuit` file, as load_graph gives a graph: pin words as written, aliases replaced."""
    return build(path)[0]


def compile(cfg):
    """(graph, SourceMap) of a project whose [project] graph is a `.circuit` file."""
    graph, smap, _ = build(cfg.graph)
    return graph, smap


def resolved_of(path):
    """(resolved graph, SourceMap): what `edakit graph json` writes beside the source."""
    from ..graph_form import resolved
    graph, smap, design = build(path)
    return resolved(graph, design), smap
