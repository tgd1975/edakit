"""The derivation rules of the circuit language (language 7): functions of edakit's that derive a part's value from
the parameters, the bound nets' ranges, the bound parts' entries and the catalog's tables – and nothing else.

    RULES                        series_resistor, divider, pullup, rc – each with its inputs, outputs, series, window
    derive(rule, args, scope)    [record] – one per target: what the rule used, with where each number came from, the
                                 derived value, the series' nearest value and the window, the chosen value, a prediction
    refresh(record, design, graph)   the record evaluated again with the entries and nets as they are now
    describe()                   the table of rules for the handbook

The rule proposes, the designer chooses: the part's value stays as bound, DEF.derive reports one outside the window
(engines/derive.py, which reads the records only). A rule that cannot evaluate – a missing field, v_on ≤ vf(i), a
zero or negative input – is a RuleError with the numbers, never a record.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..catalog import table
from . import series as series_
from .units import Quantity, UnitError, parse

I2C = table("i2c")


class RuleError(ValueError):
    pass


@dataclass
class Input:
    name: str
    kind: str                # quantity, part, port, word
    unit: str | None = None
    default: object = None   # a quantity text, a table path ("table:i2c.pullup.sink_a"), a bind ("led", "port")
    doc: str = ""


@dataclass
class Rule:
    name: str
    inputs: list
    outputs: list            # the targets' names, in order
    series: str
    window: str
    formula: str
    fn: object = None
    target_kind: dict = field(default_factory=dict)


def _clean(x, digits=6):
    return float(f"{x:.{digits}g}")


def _num(x):
    x = _clean(x)
    return int(x) if x.is_integer() else x


@dataclass
class Scope:
    """What a rule sees at one usage: parameters, ports and parts by the definition's names."""
    params: dict             # name -> (Quantity or word, source text)
    ports: dict              # port -> (net name, [lo, hi] or None)
    parts: dict              # local designator -> (entry key or None, entry or None, kind)
    targets: list            # local designators of the targets, in order
    names: dict              # local designator -> the project's designator
    origin: str              # "def led, use step1", "block led, STATUS"
    chosen: dict = field(default_factory=dict)   # local designator -> (value, unit, source) as bound


# --- binding the inputs ---------------------------------------------------------------------------------------------
def _quantity(text, unit, scope, what):
    """(value as a number, source) of a quantity argument or a parameter's name; a range gives its centre."""
    if text in scope.params:
        q, src = scope.params[text]
    else:
        try:
            q = parse(text, unit)
        except UnitError as e:
            raise RuleError(f"{what}: {e}") from None
        src = scope.origin + f" ({text})"
    if not isinstance(q, Quantity):
        raise RuleError(f"{what}: {text!r} is no quantity")
    if unit and q.unit not in (None, unit):
        raise RuleError(f"{what}: {q} – in {unit}")
    return q.centre, src


def _port(text, scope, what):
    if text not in scope.ports:
        raise RuleError(f"{what}: {text} is no port of the definition – ports: {', '.join(scope.ports)}")
    net, rng = scope.ports[text]
    if not rng:
        raise RuleError(f"{what}: port {text} is on net {net}, which has no range")
    return rng[1], f"net {net} v[1]"


def _the_one(scope, kinds, what):
    hits = [d for d, (_, _, kind) in scope.parts.items() if kind in kinds]
    if len(hits) != 1:
        raise RuleError(f"{what}: name it – the definition has {len(hits)} parts of kind {'/'.join(kinds)}")
    return hits[0]


def _one_port(scope, what):
    hits = [p for p in scope.ports if p != "gnd"]
    if len(hits) != 1:
        raise RuleError(f"{what}: name the port – the definition has {len(hits)} ports besides gnd")
    return hits[0]


def _entry_value(scope, des, field_, what, default=None, unit=None):
    key, entry, _ = scope.parts.get(des, (None, None, None))
    vals = (entry or {}).get("values") or {}
    if field_ in vals:
        return vals[field_], f"{key} values.{field_}"
    if default is not None:
        return default, f"default {field_} {default}{(' ' + unit) if unit else ''}"
    raise RuleError(f"{what}: {des}'s entry {key or '(none)'} has no values.{field_}")


def _table(path):
    head, *rest = path.split(".")
    node = table(head)
    for k in rest:
        node = node[k]
    return node, f"table {path}"


def bind(rule, args, scope):
    """{name: (value, unit, source)} of every input of the rule – the statement's arguments, else the rule's binding."""
    what = f"{rule.name} at {scope.origin}"
    given = {}
    for k, a in enumerate(args):
        name = a.get("name") or (rule.inputs[k].name if k < len(rule.inputs) else None)
        if name is None or name not in {i.name for i in rule.inputs}:
            raise RuleError(f"{what}: no input {a.get('name') or k} – inputs: {', '.join(i.name for i in rule.inputs)}")
        given[name] = a["text"]
    out = {}
    for inp in rule.inputs:
        text = given.get(inp.name)
        if inp.kind == "word":
            out[inp.name] = (text or inp.default, None, "rule" if text is None else scope.origin)
            continue
        if text is None and inp.default is None:
            if inp.doc == "optional":
                continue
            raise RuleError(f"{what}: {inp.name} has no value")
        if inp.kind == "quantity":
            if text is None and inp.default == "port":
                v, src = _port(_one_port(scope, what), scope, what)
            elif text is None and str(inp.default).startswith("table:"):
                v, src = _table(inp.default[6:])
            elif text is not None and text in scope.ports and inp.unit == "V":
                v, src = _port(text, scope, what)
            else:
                v, src = _quantity(text if text is not None else inp.default, inp.unit, scope, what)
            out[inp.name] = (v, inp.unit, src)
        elif inp.kind == "port":
            port = text if text is not None else _one_port(scope, what)
            v, src = _port(port, scope, what)
            out[inp.name] = (v, inp.unit, src)
        elif inp.kind == "part":
            des = text if text is not None else _the_one(scope, inp.default, what)
            if des not in scope.parts:
                raise RuleError(f"{what}: {des} is no part of the definition")
            out[inp.name] = (des, None, f"part {scope.names.get(des, des)}")
    return out


# --- the rules ------------------------------------------------------------------------------------------------------
def _series_resistor(inputs, scope, entries):
    i = inputs["i"][0]
    v_on = inputs["in"][0]
    led = inputs["led"][0]
    if i <= 0:
        raise RuleError(f"series_resistor: i {i} A – a current above 0")
    vf_typ, s1 = entries(led, "vf_typ_v")
    vf_at, s2 = entries(led, "vf_at_a")
    vf_min, s3 = entries(led, "vf_min_v", vf_typ)
    vf_max, s4 = entries(led, "vf_max_v", vf_typ)
    rs, s5 = entries(led, "rs_ohm", 10, "Ω")
    vf = vf_typ + rs * (i - vf_at)
    if v_on <= vf:
        raise RuleError(f"series_resistor: v_on {v_on:g} V at or below the LED's vf {vf:.3g} V at {i * 1e3:g} mA")
    numbers = [("vf_typ_v", vf_typ, "V", s1), ("vf_min_v", vf_min, "V", s3), ("vf_max_v", vf_max, "V", s4),
               ("vf_at_a", vf_at, "A", s2), ("rs_ohm", rs, "Ω", s5)]
    r = (v_on - vf) / i

    def predicts(chosen, tol, both=None):
        if chosen is None:
            return None
        lo = (v_on - vf_max + rs * vf_at) / (chosen * (1 + tol) + rs)
        hi = (v_on - vf_min + rs * vf_at) / (chosen * (1 - tol) + rs)
        return {"i": [_clean(lo, 3), _clean(hi, 3)], "unit": "A",
                "note": f"at v_on {v_on:g} V, vf {vf_min:g}…{vf_max:g} V, R {chosen:g} Ω ±{tol * 100:g} %; the driving "
                        "pin's drop is not in it – the simulation measures the current"}
    return [r], numbers, predicts


def _divider(inputs, scope, entries):
    v_out, i, v_in = inputs["v_out"][0], inputs["i"][0], inputs["in"][0]
    if i <= 0 or v_out <= 0 or v_in <= v_out:
        raise RuleError(f"divider: v_out {v_out:g} V, i {i:g} A, v_in {v_in:g} V – 0 < v_out < v_in and i above 0")
    top, bottom = (v_in - v_out) / i, v_out / i

    def predicts(chosen, tol, both=None):
        if not both or None in both:
            return None
        t, b = both
        lo = v_in * b * (1 - tol) / (t * (1 + tol) + b * (1 - tol))
        hi = v_in * b * (1 + tol) / (t * (1 - tol) + b * (1 + tol))
        return {"v_out": [_clean(lo, 4), _clean(hi, 4)], "unit": "V", "note": f"at v_in {v_in:g} V, ±{tol * 100:g} %"}
    return [top, bottom], [], predicts


def _pullup(inputs, scope, entries):
    v, i_sink, v_ol = inputs["v"][0], inputs["i_sink"][0], inputs["v_ol"][0]
    if v <= v_ol or i_sink <= 0:
        raise RuleError(f"pullup: v {v:g} V at or below v_ol {v_ol:g} V, or i_sink {i_sink:g} A not above 0")
    r_min = (v - v_ol) / i_sink
    numbers = []
    if "c_bus" in inputs and "t_rise" in inputs:
        c, t = inputs["c_bus"][0], inputs["t_rise"][0]
        if c <= 0 or t <= 0:
            raise RuleError("pullup: c_bus and t_rise above 0")
        r_max = t / (I2C["rise"]["factor"] * c)
        numbers.append(("rise_factor", I2C["rise"]["factor"], None, "table i2c.rise.factor"))
    else:
        r_max, src = _table("i2c.pullup.r_max_ohm")
        numbers.append(("r_max_ohm", r_max, "Ω", src))
    if r_min > r_max:
        raise RuleError(f"pullup: R_min {r_min:.4g} Ω above R_max {r_max:.4g} Ω – less bus capacitance or a slower bus")
    r = math.sqrt(r_min * r_max)

    def predicts(chosen, tol, both=None):
        if chosen is None:
            return None
        out = {"i_sink": _clean((v - v_ol) / chosen, 3), "unit": "A"}
        if "c_bus" in inputs:
            out["t_rise_s"] = _clean(I2C["rise"]["factor"] * chosen * inputs["c_bus"][0], 3)
        return out
    return [r], numbers, predicts, (r_min, r_max)


def _rc(inputs, scope, entries):
    f = inputs["f_c"][0]
    if f <= 0:
        raise RuleError("rc: f_c above 0")
    if "c" in inputs:
        return [1 / (2 * math.pi * f * inputs["c"][0])], [], lambda chosen, tol, both=None: None
    if "r" in inputs:
        return [1 / (2 * math.pi * f * inputs["r"][0])], [], lambda chosen, tol, both=None: None
    raise RuleError("rc: give c or r")


RULES = {
    "series_resistor": Rule(
        "series_resistor",
        [Input("i", "quantity", "A", None, "the LED current; a range gives its centre"),
         Input("led", "part", None, ("led", "led_rgb"), "the LED – the one of the definition"),
         Input("in", "port", "V", "port", "the driving port – the one besides gnd; v_on is its range's upper bound"),
         Input("series", "word", None, "E24")],
        ["value"], "E24", "one step of the series around the derived value",
        "vf(i) = vf_typ_v + rs_ohm·(i − vf_at_a); R = (v_on − vf(i)) / i", _series_resistor,
        {"value": ("Ω", "value_ohm")}),
    "divider": Rule(
        "divider",
        [Input("v_out", "quantity", "V", None, "the output voltage"),
         Input("i", "quantity", "A", None, "the divider's current"),
         Input("in", "port", "V", "port", "the port whose range's upper bound is v_in"),
         Input("series", "word", None, "E24")],
        ["top", "bottom"], "E24", "one step each",
        "R_bottom = v_out / i; R_top = (v_in − v_out) / i", _divider, {"value": ("Ω", "value_ohm")}),
    "pullup": Rule(
        "pullup",
        [Input("v", "quantity", "V", "port", "the supply: a port's upper bound or a quantity"),
         Input("i_sink", "quantity", "A", "table:i2c.pullup.sink_a", "the sink current – the I2C table's"),
         Input("v_ol", "quantity", "V", "table:i2c.pullup.vol_v", "the low level – the I2C table's"),
         Input("c_bus", "quantity", "F", None, "optional"),
         Input("t_rise", "quantity", "s", None, "optional"),
         Input("series", "word", None, "E24")],
        ["value"], "E24", "[R_min, R_max]",
        "R_min = (v − v_ol) / i_sink; R_max = t_rise / (0.8473 · c_bus), else the table's r_max_ohm; "
        "the value nearest √(R_min · R_max)", _pullup, {"value": ("Ω", "value_ohm")}),
    "rc": Rule(
        "rc",
        [Input("f_c", "quantity", "Hz", None, "the corner frequency"),
         Input("c", "quantity", "F", None, "optional"),
         Input("r", "quantity", "Ω", None, "optional"),
         Input("series", "word", None, None)],
        ["value"], "E24 for a resistor, E6 for a capacitor", "one step",
        "R = 1 / (2π f_c C), C = 1 / (2π f_c R)", _rc, {"value": ("Ω", "value_ohm")}),
}
RENAMED = {"series_resistor": {"in": "v_on"}, "divider": {"in": "v_in"}}     # an input's name in the record


def describe():
    """The handbook's table of rules: | rule | inputs | formula | series, window |."""
    rows = ["| Rule | Inputs | Output and formula | Series, window |", "| --- | --- | --- | --- |"]
    for r in RULES.values():
        ins = ", ".join(f"`{i.name}`" + (f" ({i.doc})" if i.doc else "") for i in r.inputs if i.kind != "word")
        outs = ", ".join(r.outputs)
        rows.append(f"| `{r.name}` | {ins} | {outs}: {r.formula} | {r.series}; {r.window} |")
    return "\n".join(rows)


# --- evaluating -----------------------------------------------------------------------------------------------------
def _input_rows(inputs, renamed):
    rows = []
    for name, (v, unit, src) in inputs.items():
        if name == "series" or isinstance(v, str) or v is None:
            continue
        row = {"name": renamed.get(name, name), "value": _num(v)}
        if unit:
            row["unit"] = unit
        row["from"] = src
        rows.append(row)
    return rows


def _tolerance(scope, des):
    key, entry, _ = scope.parts.get(des, (None, None, None))
    tol = ((entry or {}).get("values") or {}).get("tolerance")
    return (tol, f"{key} values.tolerance") if tol is not None else (None, None)


def derive(name, args, scope, unit_of=None):
    """[record] of a derivation at one usage: one per target, in the order of the targets."""
    rule = RULES.get(name)
    if rule is None:
        raise RuleError(f"no derivation rule {name} – rules: {', '.join(RULES)}")
    if len(scope.targets) != len(rule.outputs):
        raise RuleError(f"{name}: {len(rule.outputs)} target{'s' if len(rule.outputs) != 1 else ''} "
                        f"({', '.join(rule.outputs)}), not {len(scope.targets)}")
    inputs = bind(rule, args, scope)

    def entries(des, field_, default=None, unit=None):
        v, src = _entry_value(scope, des, field_, f"{name} at {scope.origin}", default, unit)
        inputs.setdefault(f"{des}:{field_}", (v, unit, src))
        return v, src
    got = rule.fn(inputs, scope, entries)
    values, numbers, predicts = got[0], got[1], got[2]
    bounds = got[3] if len(got) > 3 else None
    series_name = inputs.get("series", ("E24",))[0] or ("E6" if name == "rc" and "r" in inputs else "E24")
    rows = _input_rows({k: v for k, v in inputs.items() if ":" not in k}, RENAMED.get(name, {}))
    rows += [{"name": n, "value": _num(v), **({"unit": u} if u else {}), "from": s} for n, v, u, s in numbers]
    out = []
    chosen_all = [scope.chosen.get(t, (None, None, None))[0] for t in scope.targets]
    for k, (target, value) in enumerate(zip(scope.targets, values)):
        unit = "F" if name == "rc" and "r" in inputs else "Ω"
        tol, tsrc = _tolerance(scope, target)
        trows = rows + ([{"name": "tolerance", "value": tol, "from": tsrc}] if tol is not None else [])
        nearest = series_.nearest(value, series_name)
        window = list(bounds) if bounds else list(series_.window(value, series_name))
        rec = {"part": scope.names.get(target, target), "key": "value", "rule": name, "from": scope.origin,
               "args": {(a.get("name") or rule.inputs[j].name): a["text"] for j, a in enumerate(args)}}
        if len(rule.outputs) > 1:
            rec["output"] = rule.outputs[k]
        rec["inputs"] = trows
        rec["derived"] = {"value": _num(value), "unit": unit}
        rec["series"] = {"name": series_name, "nearest": _num(nearest), "window": [_num(w) for w in window]}
        chosen = scope.chosen.get(target)
        if chosen and chosen[0] is not None:
            rec["chosen"] = {"value": _num(chosen[0]), "unit": unit, "from": chosen[2]}
        p = predicts(chosen[0] if chosen else None, tol or 0.0, chosen_all)
        if p:
            rec["predicts"] = p
        out.append(rec)
    return out


def in_window(record, value):
    lo, hi = record["series"]["window"]
    return lo * (1 - 1e-9) <= value <= hi * (1 + 1e-9)


# --- the record against the design now ------------------------------------------------------------------------------
def source_value(src, design):
    """The number a record's input source names, read now – None where it names nothing that can change (a
    parameter, a rule's default)."""
    if src.startswith("net ") and src.endswith(("v[0]", "v[1]")):
        net = src[4:].rsplit(" ", 1)[0]
        v = (design.nets.get(net) or {}).get("v")
        return v[int(src[-2])] if isinstance(v, list) and len(v) == 2 else "missing"
    if src.startswith("table "):
        try:
            return _table(src[6:])[0]
        except (KeyError, TypeError):
            return "missing"
    key, sep, path = src.partition(" values.")
    if sep and " " not in key:
        entry = design.parts.get(key)
        if entry is None:
            return "missing"
        return ((entry.get("values") or {}).get(path, "missing"))
    return None


def inputs_differ(record, design):
    """[text] for every input whose source says another number now."""
    out = []
    for row in record.get("inputs") or []:
        now = source_value(row.get("from", ""), design)
        if now is None:
            continue
        if now == "missing" or not isinstance(now, (int, float)) or not math.isclose(now, row["value"], rel_tol=1e-9,
                                                                                         abs_tol=1e-12):
            out.append(f"{row['name']} {row['value']:g}{(' ' + row['unit']) if row.get('unit') else ''} from "
                       f"{row['from']} – now {now if isinstance(now, str) else f'{now:g}'}")
    return out


def refresh(record, design, records=()):
    """(record, [what changed]) – the record evaluated again: its inputs read from their sources now, the derived value,
    the series and the window from them, the chosen value through the part's entry now; `records` the graph's others,
    for the sibling of a two-target rule."""
    from ..engines.derive import part_value
    rule = RULES.get(record.get("rule"))
    if rule is None:
        raise RuleError(f"no derivation rule {record.get('rule')}")
    rows = {r["name"]: dict(r) for r in record.get("inputs") or []}
    for r in rows.values():
        now = source_value(r.get("from", ""), design)
        if isinstance(now, (int, float)) and not isinstance(now, bool):
            r["value"] = now
    back = {v: k for k, v in RENAMED.get(rule.name, {}).items()}
    inputs = {back.get(n, n): (r["value"], r.get("unit"), r.get("from", "")) for n, r in rows.items()}
    inputs.setdefault("led", ("led", None, ""))

    def entries(des, field_, default=None, unit=None):
        if field_ in rows:
            return rows[field_]["value"], rows[field_]["from"]
        if default is not None:
            return default, f"default {field_} {default}"
        raise RuleError(f"{rule.name}: the record has no {field_}")
    got = rule.fn(inputs, None, entries)
    values, predicts = got[0], got[2]
    bounds = got[3] if len(got) > 3 else None
    k = rule.outputs.index(record["output"]) if record.get("output") in rule.outputs else 0
    value = values[k]
    name = (record.get("series") or {}).get("name", rule.series)
    new = dict(record)
    new["inputs"] = [rows[r["name"]] for r in record.get("inputs") or []]
    new["derived"] = {"value": _num(value), "unit": (record.get("derived") or {}).get("unit", "Ω")}
    window = list(bounds) if bounds else list(series_.window(value, name))
    new["series"] = {"name": name, "nearest": _num(series_.nearest(value, name)), "window": [_num(w) for w in window]}
    unit = new["derived"]["unit"]
    chosen = part_value(design, record["part"], unit) if record.get("part") in design.comps else None
    if chosen is not None:
        key = design.entry_key(record["part"])
        new["chosen"] = {"value": _num(chosen), "unit": unit,
                         "from": f"{key} values.value_ohm" if key and unit == "Ω" else f"{key} values.value_f"
                         if key and unit == "F" else f"{record['part']} value"}
    tol = rows.get("tolerance", {}).get("value", 0.0) or 0.0
    both = None
    if len(rule.outputs) > 1:
        sib = {r.get("output"): r for r in records if r.get("rule") == record.get("rule")
               and r.get("from") == record.get("from")}
        both = [part_value(design, sib[o]["part"], unit) if o in sib and sib[o].get("part") in design.comps else None
                for o in rule.outputs]
    p = predicts(chosen, tol, both)
    if p:
        new["predicts"] = p
    else:
        new.pop("predicts", None)
    changes = [k for k in ("inputs", "derived", "series", "chosen", "predicts") if new.get(k) != record.get(k)]
    return new, changes
