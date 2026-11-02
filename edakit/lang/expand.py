"""The expansion of usages (T.11, language 5.6): a `use` becomes the parts and nets of its definition, as if written
at the place of the `use`.

    expand_use(use, definition, ctx)   ([statements], [Job]) – the definition's parts with the usage's designators and
                                       the bindings' attributes over the definition's, its nets with their pins renamed,
                                       the ports joined to the bound nets, the internal nets named; the derivations as
                                       jobs the compiler evaluates once the graph is assembled

A port joins the net it is bound to – a new net gets the range the definition gives the port, `@PORT` resolved as
block.plan's v_of –; `gnd` without a binding joins the project's ground; an internal net is `<INSTANCE>_<NET>` in
capitals unless a binding names it. An optional part left out with `without` leaves its nets, a net left without pins
is not made, and a pin alone on an optional port that is not bound goes into its component's `nc` (block.plan's
rules). `{as}` in a text becomes the instance's name, as `block add` writes it. Nothing is appended to `notes`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import model as m
from .tokens import LangError


@dataclass
class Job:
    """A derivation to evaluate at one usage, once the graph is assembled."""
    derive: object                 # the Derive of the definition
    use: object                    # the Use
    defn: object
    names: dict                    # local designator -> the project's
    ports: dict                    # port -> the project's net
    params: dict                   # name -> (Quantity or word, source)
    origin: str


@dataclass
class Context:
    """What a usage's expansion reads of the project: its nets as declared, its ground, the designators taken."""
    nets: dict = field(default_factory=dict)       # name -> [Net statements of the project]
    ground: str = "GND"
    taken: dict = field(default_factory=dict)      # designator -> node that took it


def _place(node):
    return f"{node.file}:{node.line}"


def _err(node, text, also=None):
    return LangError(node.file, node.line, text + (f" – the definition at {_place(also)}" if also is not None else ""))


def _rename_word(word, rename):
    des, dot, rest = word.partition(".")
    return f"{rename.get(des, des)}{dot}{rest}" if dot else word


def _as(text, instance):
    return text.replace("{as}", instance) if isinstance(text, str) else text


def _param(value, params):
    """A definition's value that names one of its parameters, as the usage gives it: a word as it is, a quantity as
    its canonical text where a text is expected."""
    from .units import Quantity, format
    if isinstance(value, str) and value in params:
        got = params[value][0]
        return format(got) if isinstance(got, Quantity) else got
    return value


def _accepts(accepts, rename, instance):
    from ..block import rename_accept
    out = []
    for a in accepts:
        key = next(iter(rename_accept({a.key: ""}, rename)))
        out.append(m.Accept(a.file, a.line, key=key, reason=_as(a.reason, instance)))
    return out


def _range_of(name, ctx):
    """The range the project declares for a net: a Quantity or a parameter's name; None where none is given."""
    for st in ctx.nets.get(name, []):
        if st.v is not None:
            return st.v
        for k, v in st.attrs:
            if k == "v":
                return v
    return None


def expand_use(use, defn, ctx):
    """([statements], [Job], [LangError]) of one usage."""
    errors = []
    parts = [st for st in defn.body if isinstance(st, m.Part)]
    nets = [st for st in defn.body if isinstance(st, m.Net)]
    part_names = {p.des for p in parts}
    net_names = {n.name for n in nets}
    ports = dict(defn.ports)
    instance = use.instance

    # parameters
    params = {}
    for a in defn.params:
        params[a.name] = (a.value, f"def {defn.name} ({a.name})")
    for a in use.params:
        if a.name is None:
            errors.append(_err(use, f"use {instance}: ({a.text}) – parameters by name, NAME = VALUE"))
        elif a.name not in params:
            errors.append(_err(use, f"use {instance}: def {defn.name} has no parameter {a.name} – parameters: "
                                    f"{', '.join(params) or 'none'}", defn))
        else:
            params[a.name] = (a.value, f"use {instance} ({a.name})")

    # bindings
    port_to, net_to, part_to = {}, {}, {}
    for b in use.bindings:
        if b.left in ports:
            port_to[b.left] = b.right
        elif b.left in net_names:
            net_to[b.left] = b.right
        elif b.left in part_names:
            if b.left in part_to:
                errors.append(_err(b, f"use {instance}: {b.left} bound twice"))
            part_to[b.left] = b
        else:
            errors.append(_err(b, f"use {instance}: {b.left} is no port, net or part of def {defn.name} – ports: "
                                  f"{', '.join(ports)}; parts: {', '.join(sorted(part_names))}", defn))
    left_out = set(use.without)
    for des in left_out - set(defn.optional_parts):
        errors.append(_err(use, f"use {instance}: without {des} – no optional part of def {defn.name} (optional: "
                                f"{', '.join(defn.optional_parts) or 'none'})", defn))
    rename = {}
    for p in parts:
        if p.des in left_out:
            continue
        b = part_to.get(p.des)
        if b is None:
            errors.append(_err(use, f"use {instance}: part {p.des} of def {defn.name} is not bound – {p.des} = DES",
                               p))
            continue
        des = b.right
        if des in ctx.taken:
            errors.append(_err(b, f"use {instance}: designator {des} is taken – at {_place(ctx.taken[des])}"))
        ctx.taken.setdefault(des, b)
        rename[p.des] = des
    for port in ports:
        if port not in port_to and port != "gnd" and port not in defn.optional_ports:
            errors.append(_err(use, f"use {instance}: port {port} of def {defn.name} is not bound – {port} = NET",
                               defn))
    if errors:
        return [], [], errors

    # the project's nets of the ports and the names of the internal nets
    target = {}
    for n in nets:
        if n.name in ports:
            if n.name in port_to:
                target[n.name] = port_to[n.name]
            elif n.name == "gnd":
                target[n.name] = ctx.ground
            else:
                target[n.name] = None                                    # an optional port left open
        else:
            target[n.name] = net_to.get(n.name) or f"{instance}_{n.name}".upper()

    def v_of(name, seen=()):
        n = next(x for x in nets if x.name == name)
        project = target[name]
        if project is not None and project in ctx.nets:
            return _range_of(project, ctx), True
        v = n.v if n.v is not None else dict(n.attrs).get("v")
        if isinstance(v, str) and v in params:
            v = params[v][0]
        if isinstance(v, str) and v.startswith("@"):
            ref = v[1:]
            if ref in seen or ref not in target:
                errors.append(_err(use, f"use {instance}: net {name} of def {defn.name} takes its range from "
                                        f"unknown port {ref}", n))
                return None, False
            return v_of(ref, seen + (name,))
        return v, False

    # parts
    out, nc_more = [], {}
    loose = set(defn.optional_ports) - set(port_to)
    for n in nets:
        pins = [w for w in n.pins if w.word.partition(".")[0] not in left_out]
        if n.name in loose and len(pins) == 1:
            des, _, pin = pins[0].word.partition(".")
            nc_more.setdefault(des, []).append(pin)
    for p in parts:
        if p.des in left_out:
            continue
        b = part_to[p.des]
        bp = b.part
        new = m.Part(b.file, b.line, des=rename[p.des], type=p.type)
        new.part = bp.part if bp is not None and bp.part is not None else p.part
        new.label = _as(bp.label if bp is not None and bp.label is not None else p.label, instance)
        attrs = [(k, _param(_as(v, instance), params)) for k, v in p.attrs]
        for k, v in (bp.attrs if bp is not None else []):
            attrs = [(x, y) for x, y in attrs if x != k] + [(k, v)]
        for key, ids in (("satisfies", use.satisfies), ("decision", use.decision)):
            if ids:
                attrs = [(x, y) for x, y in attrs if x != key] + [(key, list(ids))]
        new.attrs = attrs
        new.pins = list(bp.pins) if bp is not None and bp.pins else list(p.pins)
        new.nc = [m.PinWord(w.file, w.line, word=w.word) for w in p.nc]
        new.nc += [m.PinWord(use.file, use.line, word=x) for x in nc_more.get(p.des, [])]
        if bp is not None and bp.nc:
            new.nc = [m.PinWord(w.file, w.line, word=w.word) for w in bp.nc]
        new.aliases = list(bp.aliases) if bp is not None and bp.aliases else list(p.aliases)
        new.accepts = _accepts(p.accepts, rename, instance) + (list(bp.accepts) if bp is not None else [])
        new.expanded = (use, p)
        out.append(new)

    # nets
    for n in nets:
        name = target[n.name]
        if name is None:
            continue
        pins = [w for w in n.pins if w.word.partition(".")[0] not in left_out]
        if not pins:
            continue
        if n.name in loose and len(pins) == 1:
            continue
        new = m.Net(use.file, use.line, name=name)
        new.pins = [m.PinWord(w.file, w.line, word=_rename_word(w.word, rename), locked=w.locked) for w in pins]
        existing = name in ctx.nets
        v, _ = v_of(n.name)
        if not existing:
            if v is None:
                errors.append(_err(use, f"use {instance}: net {name} does not exist and def {defn.name} gives net "
                                        f"{n.name} no range – bind it to a net of the project", n))
            new.v = v
        have = {k for st in ctx.nets.get(name, []) for k, _ in st.attrs}
        new.attrs = [(k, _as(v2, instance)) for k, v2 in n.attrs if k != "v" and not (existing and (
            k in have or k == "notes"))]
        new.accepts = _accepts(n.accepts, rename, instance)
        new.expanded = (use, n)
        out.append(new)
        ctx.nets.setdefault(name, []).append(new)

    jobs = [Job(d, use, defn, dict(rename), {p: target.get(p) for p in ports}, params,
                f"def {defn.name}, use {instance}") for d in defn.body if isinstance(d, m.Derive)]
    return out, jobs, errors


def project_context(statements):
    """The Context of a flat model: its nets as declared, its ground, its part statements' designators."""
    ctx = Context()
    for st in statements:
        if isinstance(st, m.Net):
            ctx.nets.setdefault(st.name, []).append(st)
        elif isinstance(st, m.Ground):
            ctx.ground = st.name
        elif isinstance(st, m.Part):
            ctx.taken.setdefault(st.des, st)
    return ctx


def expand_uses(statements, defs):
    """(statements, [Job], [LangError]) – every `use` of a flat list replaced by its expansion."""
    ctx = project_context(statements)
    out, jobs, errors = [], [], []
    for st in statements:
        if not isinstance(st, m.Use):
            out.append(st)
            continue
        defn = defs.get(st.definition)
        if defn is None:
            errors.append(LangError(st.file, st.line, f"use {st.instance}: no definition {st.definition} – the "
                                                      f"project's and edakit's: {', '.join(sorted(defs))}"))
            continue
        got, more, errs = expand_use(st, defn, ctx)
        out += got
        jobs += more
        errors += errs
    return out, jobs, errors

