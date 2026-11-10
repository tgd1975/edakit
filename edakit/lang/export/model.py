"""The element tree of an export (language 10): a project's package, its circuit as a part definition specializing
Electrical::Circuit, the components as part usages with their pins as ports, the nets as n-ary connections, cables,
layout, accepts and locks as metadata, the definitions of the source as part definitions specializing Block, its
usages as part usages typed by them, a variant as a specialization of its base, derivation records as @Derivation,
the requirements as requirement usages."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ...design import load_parts
from .. import model as m

RESERVED = {"in", "out", "inout", "ref", "part", "port", "connect", "connection", "attribute", "item", "package",
            "private", "public", "import", "doc", "def", "abstract", "derived", "binding", "verify", "require",
            "subject", "type", "end", "to", "from", "all", "and", "or", "not", "for", "if", "else", "then", "about",
            "action", "alias", "as", "by", "calc", "case", "comment", "constant", "constraint", "default", "enum",
            "event", "first", "flow", "individual", "interface", "library", "locale", "loop", "member", "message",
            "metadata", "nonunique", "objective", "occurrence", "ordered", "perform", "readonly", "redefines",
            "rendering", "rep", "requirement", "return", "satisfy", "send", "snapshot", "specializes", "stakeholder",
            "state", "subsets", "succession", "timeslice", "transition", "use", "variant", "variation", "view",
            "viewpoint", "when", "while", "true", "false", "null", "new", "language", "assume", "assert", "accept",
            "actor", "allocate", "allocation", "analysis", "bind", "concern", "decide", "dependency", "entry", "exhibit",
            "exit", "expose", "filter", "fork", "frame", "include", "join", "merge", "parallel", "terminate", "until",
            "verification", "after", "at", "do", "hastype", "istype", "meta", "struct", "feature", "connector",
            "function", "predicate", "behavior", "class", "datatype", "assoc", "classifier", "metaclass", "step",
            "expr", "inv", "multiplicity", "namespace", "disjoint", "conjugate", "chains", "inverse",
            "featured", "typed", "unions", "intersects", "differences", "composite", "portion", "var", "const"}
TYPES = {"resistor": "Resistor", "capacitor": "Capacitor", "inductor": "Inductor", "diode": "Diode", "led": "LED",
         "microcontroller": "Microcontroller", "module": "Module", "ic": "IC", "transistor": "Transistor",
         "connector": "Connector", "regulator": "Regulator", "button": "Button", "switch": "Switch",
         "potentiometer": "Potentiometer", "audio": "Audio", "testpoint": "Testpoint",
         "battery_holder": "BatteryHolder", "fuse": "Fuse"}
DECLARED = {"designator", "lcsc", "part", "value", "board", "bom", "label", "notes"}   # Component's own attributes
NET_DECLARED = {"name": "name", "v": "v", "fn": "fn", "fn_bus": "fnBus", "bus": "bus", "pwm_hz": "pwmHz",
                "clock_hz": "clockHz", "notes": "notes"}
RULE_CALC = {"series_resistor": "SeriesResistor", "divider": "Divider", "pullup": "Pullup", "rc": "RC"}
SI = {"V": "V", "A": "A", "Ω": "'Ω'", "F": "F", "H": "H", "Hz": "Hz", "W": "W", "s": "s", "m": "m"}
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/tgd1975/edakit")


@dataclass
class El:
    kind: str                              # package, partdef, part, port, attr, conn, meta, doc, satisfy, req
    name: str | None = None
    type: str | None = None
    specializes: list = field(default_factory=list)
    redefines: bool = False
    value: str | None = None               # an expression as the textual notation writes it
    default: bool = False                  # attr: `default` instead of `=`
    ends: list = field(default_factory=list)
    binary: bool = False                   # conn: `connect a to b`
    imports: list = field(default_factory=list)
    children: list = field(default_factory=list)
    props: dict = field(default_factory=dict)    # meta: name -> expression; req: binding, subject …

    def add(self, *els):
        self.children.extend(e for e in els if e is not None)
        return self


def name(text):
    """A name as both notations write it: bare where it is an identifier and no keyword, else quoted."""
    text = str(text)
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text) and text not in RESERVED:
        return text
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def camel(text):
    """A definition's name for a type: led-bar → LedBar, i2c-pullups → I2cPullups."""
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", str(text)) if p]
    out = "".join(p[:1].upper() + p[1:] for p in parts) or "Circuit"
    return out if out[0].isalpha() else "C" + out


def string(text):
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def number(x):
    return repr(float(x)) if isinstance(x, float) and not float(x).is_integer() else str(int(x)) if \
        float(x).is_integer() else repr(x)


def quantity(x, unit):
    return f"{number(x)} [SI::{SI.get(unit, unit)}]"


def literal(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return number(v)
    if isinstance(v, list):
        return "(" + ", ".join(literal(x) for x in v) + ("," if len(v) == 1 else "") + ")"
    return string(v)


def type_of(v):
    return "Boolean" if isinstance(v, bool) else "Integer" if isinstance(v, int) else "Real" if \
        isinstance(v, float) else "String"


def doc(text):
    return El("doc", value=str(text)) if text else None


def element_id(project, qualified):
    return str(uuid.uuid5(NAMESPACE, f"{project}::{qualified}"))


# --- a component and its pins ---------------------------------------------------------------------------------------
def port_names(design, des):
    """{number: port name}: the entry's name where it names one pin alone, else name_number, else the number."""
    pins = (design.comps.get(des) or {}).get("pins") or {}
    names = list(pins.values())
    out = {}
    for num, pname in pins.items():
        out[num] = str(pname) if names.count(pname) == 1 and pname else f"{pname}_{num}" if pname else str(num)
    return out


def component(design, c, locks, records, redefine=False, local=None):
    des = c["designator"]
    typ = TYPES.get(c.get("type"), "Other")
    el = El("part", local or des, None if redefine else typ, redefines=redefine)
    el.add(El("attr", "designator", value=string(des), redefines=True))
    for key in ("lcsc", "value", "board", "label", "notes"):
        if c.get(key) is not None:
            el.add(El("attr", key, value=string(c[key]), redefines=True))
    if c.get("part") is not None:
        el.add(El("attr", "mpn", value=string(c["part"]), redefines=True))
    if c.get("bom") is False:
        el.add(El("attr", "bom", value="false", redefines=True))
    if typ == "Other" and c.get("type"):
        el.add(El("attr", "type", value=string(c["type"]), redefines=True))
    entry = design.part(des) or {}
    vals = entry.get("values") or {}
    for field_, attr, unit in (("value_ohm", "resistance", "Ω"), ("value_f", "capacitance", "F"),
                               ("value_h", "inductance", "H")):
        if typ in ("Resistor", "Capacitor", "Inductor") and isinstance(vals.get(field_), (int, float)):
            el.add(El("attr", attr, value=quantity(vals[field_], unit), redefines=True))
    for k, v in c.items():
        if k in DECLARED or k in ("designator", "type", "pins", "nc", "accept", "satisfies", "decision"):
            continue
        if isinstance(v, (str, bool, int, float)):
            el.add(El("attr", k, type_of(v), value=literal(v)))
    roles = design._roles(des) if des in design.comps else {}
    for num, pname in port_names(design, des).items():
        p = El("port", pname, "Pin").add(El("attr", "number", value=string(num), redefines=True))
        if (c.get("pins") or {}).get(num):
            p.add(El("attr", "name", value=string(c["pins"][num]), redefines=True))
        if roles.get(num):
            p.add(El("attr", "role", value=string(roles[num]), redefines=True))
        if f"{des}.{num}" in locks:
            p.add(El("meta", type="Lock", props={"net": string(locks[f"{des}.{num}"])}))
        el.add(p)
    for k, reason in (c.get("accept") or {}).items():
        el.add(El("meta", type="Accept", props={"code": string(k), "reason": string(reason)}))
    if c.get("decision"):
        el.add(El("meta", type="Decision", props={"id": literal(list(c["decision"]))}))
    for r in records.get(des, []):
        el.add(El("meta", type="Derivation", props={
            "rule": string(RULE_CALC.get(r["rule"], r["rule"])),
            "inputs": string(", ".join(f"{i['name']} {i['value']}{(' ' + i['unit']) if i.get('unit') else ''}"
                                      for i in r.get("inputs") or [])),
            "derived": number(float(r["derived"]["value"])) if "." in number(float(r["derived"]["value"])) else
            f"{number(r['derived']['value'])}.0", "unit": string(r["derived"]["unit"]),
            "window": "(" + ", ".join(f"{float(w)}" for w in r["series"]["window"]) + ")"}))
    return el


def net(design, n, paths):
    ends = []
    for ref in n.get("pins") or []:
        des, _, num = ref.partition(".")
        ends.append(f"{paths.get(des, name(des))}.{name(port_names(design, des).get(num, num))}")
    el = El("conn", n["name"], "Net", ends=ends)
    el.add(El("attr", "name", value=string(n["name"]), redefines=True))
    v = n.get("v")
    if isinstance(v, list) and len(v) == 2:
        el.add(El("attr", "v", value=f"VoltageRange(min = {quantity(v[0], 'V')}, max = {quantity(v[1], 'V')})",
                  redefines=True))
    for k, val in n.items():
        if k in ("name", "pins", "v", "accept", "satisfies", "decision"):
            continue
        if k in NET_DECLARED and isinstance(val, str):
            el.add(El("attr", NET_DECLARED[k], value=string(val), redefines=True))
        elif k in ("pwm_hz", "clock_hz") and isinstance(val, (int, float)):
            el.add(El("attr", NET_DECLARED[k], value=quantity(val, "Hz"), redefines=True))
        elif isinstance(val, (str, bool, int, float)):
            el.add(El("attr", k, type_of(val), value=literal(val)))
    for k, reason in (n.get("accept") or {}).items():
        el.add(El("meta", type="Accept", props={"code": string(k), "reason": string(reason)}))
    return el


# --- definitions and usages of the source ---------------------------------------------------------------------------
def definition(defn):
    el = El("partdef", camel(defn.name), specializes=["Block"])
    el.add(doc(defn.title or defn.about))
    for a in defn.params:
        from ..units import Quantity
        if isinstance(a.value, Quantity):
            unit = a.value.unit
            typ = {"A": "ElectricCurrentValue", "V": "ElectricPotentialDifferenceValue", "Ω": "ResistanceValue",
                   "F": "CapacitanceValue", "Hz": "FrequencyValue", "s": "DurationValue"}.get(unit, "Real")
            el.add(El("attr", a.name, typ, value=quantity(a.value.centre, unit) if unit else number(a.value.centre),
                      default=True))
        else:
            el.add(El("attr", a.name, "String", value=string(a.text), default=True))
    ports = {p for p, _ in defn.ports}
    for p, about in defn.ports:
        el.add(El("port", p, "Pin").add(doc(about)))
    used = {}
    for n in (x for x in defn.body if isinstance(x, m.Net)):
        for w in n.pins:
            d, _, pin = w.word.partition(".")
            used.setdefault(d, []).append(pin)
    for p in (x for x in defn.body if isinstance(x, m.Part)):
        part = El("part", p.des, TYPES.get(p.type, "Other"))
        for pin in dict.fromkeys(used.get(p.des, [])):
            part.add(El("port", pin, "Pin"))
        el.add(part)
    for n in (x for x in defn.body if isinstance(x, m.Net)):
        ends = [f"{name(w.word.partition('.')[0])}.{name(w.word.partition('.')[2])}" for w in n.pins]
        if n.name in ports:
            ends = [name(n.name), *ends]
        if len(ends) >= 2:
            el.add(El("conn", f"{n.name}_net" if n.name in ports else n.name, "Net", ends=ends))
    for d in (x for x in defn.body if isinstance(x, m.Derive)):
        el.add(doc(f"derive {' '.join(d.targets)} {d.rule}({', '.join(a.text for a in d.args)}) – calc def "
                   f"{RULE_CALC.get(d.rule, d.rule)}"))
    return el


@dataclass
class Export:
    project: str
    root: El                               # the package
    library: str                           # Electrical.sysml's text
    before: list = field(default_factory=list)   # the packages of a variant's bases, written before its own


def variant_base(cfg):
    """The Config of a variant's base project, or None for a source that is no variant."""
    from ... import config
    from ..reader import read
    path = Path(cfg.graph)
    if path.suffix != ".circuit":
        return None
    src = read(path.read_text(encoding="utf-8"), path.name)
    if src.variant is None:
        return None
    base = (cfg.root / src.variant.base).resolve()
    for d in [base.parent, *base.parents]:
        if (d / "edakit.toml").is_file():
            return config.load(d / "edakit.toml")
    return None


def build(cfg, graph=None, flat=False, chain=True):
    """The element tree of a project – its resolved graph and, for a .circuit source, its definitions and usages; a
    variant as a specialization of its base's circuit, every part and net that differs redefined (flat: no usages,
    so that the redefinitions name the designators)."""
    base_cfg = variant_base(cfg) if chain else None
    if base_cfg is not None:
        return _variant(cfg, base_cfg)
    from ...graph_form import design_of, resolved
    from ...design import load_graph
    path = Path(cfg.graph)
    source = load_graph(path) if graph is None else graph
    design = design_of(path, load_parts(cfg.parts_dirs or cfg.parts), list(cfg.boards), source)
    g = resolved(source, design)
    project = g.get("name") or cfg.project
    pkg = El("package", project, imports=["Electrical::*"])
    circuit = El("partdef", camel(project), specializes=["Circuit"], props={"circuit": True})
    pkg.add(circuit)
    for k in ("name", "version", "date", "description"):
        if g.get(k):
            circuit.add(El("attr", k, value=string(g[k]), redefines=True))
    purpose = g.get("purpose") or {}
    if purpose.get("use") in ("private", "gift", "sale"):
        circuit.add(El("attr", "purpose", value=f"Purpose::{name(purpose['use'])}", redefines=True))
    if purpose.get("market"):
        circuit.add(El("attr", "market", value=string(purpose["market"]), redefines=True))
    if purpose.get("notes"):
        circuit.add(El("attr", "purposeNotes", value=string(purpose["notes"]), redefines=True))
    if g.get("ground"):
        circuit.add(El("attr", "ground", value=string(g["ground"]), redefines=True))
    locks = dict((g.get("locks") or {}).get("pins") or {})
    records = {}
    for r in g.get("derivations") or []:
        records.setdefault(r["part"], []).append(r)
    usages, defs = {}, {}
    if path.suffix == ".circuit" and not flat:
        from ..compile import load_sources, project_of, resolve
        root, dirs = project_of(path)
        mdl = resolve(load_sources(path, root), root, dirs)
        for st in mdl.statements:
            if isinstance(st, m.Use) and st.definition in mdl.defs:
                usages[st.instance] = st
                defs[st.definition] = mdl.defs[st.definition]
        for st in mdl.statements:
            if isinstance(st, m.Param) and hasattr(st.value, "lo"):
                q = st.value
                circuit.add(El("attr", st.name, "VoltageRange" if q.unit == "V" else "Real",
                               value=f"VoltageRange(min = {quantity(q.lo, 'V')}, max = {quantity(q.hi, 'V')})"
                               if q.unit == "V" else number(q.centre)))
    for d in defs.values():
        pkg.children.insert(len(pkg.children) - 1, definition(d))
    comps = {c["designator"]: c for c in g.get("components") or []}
    paths, inside = {}, {}
    for inst, use in usages.items():
        defn = defs[use.definition]
        for b in use.bindings:
            if b.left in {p.des for p in defn.body if isinstance(p, m.Part)} and b.right in comps:
                paths[b.right] = f"{name(inst)}.{name(b.left)}"
                inside.setdefault(inst, []).append((b.left, b.right))
    for des, c in comps.items():
        if des not in paths:
            circuit.add(component(design, c, locks, records))
    for inst, use in usages.items():
        defn = defs[use.definition]
        u = El("part", inst, camel(defn.name))
        for a in use.params:
            if a.name:
                val = a.value
                u.add(El("attr", a.name, value=quantity(val.centre, val.unit) if hasattr(val, "lo") and val.unit
                         else string(a.text), redefines=True))
        for local, des in inside.get(inst, []):
            u.add(component(design, comps[des], locks, records, redefine=True, local=local))
        circuit.add(u)
    for n in g.get("nets") or []:
        el = net(design, n, paths)
        if len(el.ends) >= 2:
            circuit.add(el)
        else:                                   # a net of one pin: a connection without ends, its pin as doc
            el.ends = []
            el.add(doc(f"one pin: {', '.join(n.get('pins') or []) or 'none'}"))
            circuit.add(el)
    for c in g.get("cables") or []:
        cab = El("conn", c["name"], "Cable", ends=[name(c["from"]), name(c["to"])], binary=True)
        cab.add(El("attr", "name", value=string(c["name"]), redefines=True))
        if isinstance(c.get("r_ohm_per_wire"), (int, float)):
            cab.add(El("attr", "rOhmPerWire", value=quantity(c["r_ohm_per_wire"], "Ω"), redefines=True))
        cab.add(doc(" ".join(f"{a}={b}" for a, b in (c.get("pins") or {}).items())))
        circuit.add(cab)
    lay = g.get("layout") or {}
    props = {k: literal(list(lay[k])) for k in ("fixed", "edge", "notes") if isinstance(lay.get(k), list) and lay[k]}
    if props:
        circuit.add(El("meta", type="Layout", props=props))
    for k, reason in (g.get("accept") or {}).items():
        circuit.add(El("meta", type="Accept", props={"code": string(k), "reason": string(reason)}))
    from .requirements import requirements
    for r in requirements(cfg, g, usages, paths):
        (circuit if r.props.get("inside") else pkg).add(r)
    return Export(project, pkg, (Path(__file__).resolve().parents[1] / "library" / "Electrical.sysml").read_text())


def _variant(cfg, base_cfg):
    """A variant's export: its base's package (and the base's bases) before its own, its circuit specializing the
    base's with the parts and nets that differ redefined and the new ones added."""
    from ...design import load_graph
    from ...graph_form import design_of
    from ..reader import read
    base = build(base_cfg, flat=True)
    own = build_flat(cfg)
    vname = read(Path(cfg.graph).read_text(encoding="utf-8"), "v").variant.name
    own.project = f"{base.project}-{vname}"
    bg = _resolved(base_cfg)
    vg = _resolved(cfg)
    base_name = _circuit_of(base.root).name
    circuit = El("partdef", camel(own.project), specializes=[f"{name(base.project)}::{base_name}"],
                 props={"circuit": True})
    pkg = El("package", own.project, imports=["Electrical::*", f"{name(base.project)}::*"]).add(circuit)
    bcomps = {c["designator"]: c for c in bg.get("components") or []}
    bnets = {n["name"]: n for n in bg.get("nets") or []}
    design = design_of(Path(cfg.graph), load_parts(cfg.parts_dirs or cfg.parts), list(cfg.boards), load_graph(cfg.graph))
    locks = dict((vg.get("locks") or {}).get("pins") or {})
    records = {}
    for r in vg.get("derivations") or []:
        records.setdefault(r["part"], []).append(r)
    for c in vg.get("components") or []:
        old = bcomps.get(c["designator"])
        if old == c:
            continue
        el = component(design, c, locks, records)
        if old is not None:
            el.redefines = True
        circuit.add(el)
    for n in vg.get("nets") or []:
        old = bnets.get(n["name"])
        if old == n:
            continue
        el = net(design, n, {})
        if old is not None:
            el.redefines = True
        circuit.add(el)
    for k, reason in (vg.get("accept") or {}).items():
        if (bg.get("accept") or {}).get(k) != reason:
            circuit.add(El("meta", type="Accept", props={"code": string(k), "reason": string(reason)}))
    return Export(own.project, pkg, own.library, before=[*base.before, base.root])


def _circuit_of(pkg):
    return next(c for c in pkg.children if c.kind == "partdef" and c.props.get("circuit"))


def _resolved(cfg):
    from ...design import load_graph
    from ...graph_form import design_of, resolved
    src = load_graph(cfg.graph)
    return resolved(src, design_of(Path(cfg.graph), load_parts(cfg.parts_dirs or cfg.parts), list(cfg.boards), src))


def build_flat(cfg):
    """A project's export without usages and without its variant chain: its own resolved graph, flat."""
    return build(cfg, flat=True, chain=False)
