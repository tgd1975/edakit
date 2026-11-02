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
    path = Path(path)
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


def load_sources(path, root):
    """[Source] of a project: the main file (includes and the variant chain follow in T.13 and T.14)."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise CompileError([LangError(_name(path, root), 0, "no such file")]) from None
    src = read(text, _name(path, root), "graph")
    return [src]


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

    for src in sources:
        for st in src.statements:
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
    if errors:
        raise CompileError(errors)
    return model


def expand(model):
    """Loops and usages expanded in place (T.11, T.12); a flat model is its own expansion."""
    return model


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
    return _num(v) if isinstance(v, float) else v


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
        if st.v is not None:
            if "v" in n:
                first = self.net_nodes[st.name]
                self.err(st, f"net {st.name}: the range given twice – first at {first.file}:{first.line}")
            elif isinstance(st.v, str):
                self.err(st, f"net {st.name}: {st.v} – a parameter or a port is read in T.13 and T.11")
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
            if isinstance(value, str) and key in ("v",) and not isinstance(value, Quantity):
                self.err(st, f"net {st.name}: v {value} – a parameter or a port is read in T.13 and T.11")
                continue
            n[key] = _value(key, value)
        if st.accepts:
            acc = n.setdefault("accept", {})
            for a in st.accepts:
                if a.reason is not None:
                    acc[a.key] = a.reason

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
    return graph, asm.map, design


def build(path, parts=None):
    """(graph, SourceMap, Design) of a `.circuit` file."""
    root, dirs = project_of(path)
    model = expand(resolve(load_sources(path, root), root, dirs))
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
