"""A JSON or TOML graph as flat statements of the circuit language (T.6) – the writer `edakit graph convert --to
circuit` uses.

    to_circuit(source, design)   the text: the graph's head, the parts, the nets, the cables, the layout, the locks
                                 that are no `(locked)` mark, the graph's accept, ground and the keys without a form
                                 of their own as `set KEY JSON`; formatted by fmt.py

Pins are written by the word rule (graph_form.written): a pin's name or role where it names that pin alone, a word
several pins share where all of them stand in the net, else the number; a part's pin map only where it differs from
its entry's; a lock as `(locked)` where every pin its word stands for is locked to that net, else a `lock` line. No
usages: those come from `block add` or by hand. A key the attribute table does not know is refused, so that nothing
of the graph is lost on the way.
"""

from __future__ import annotations

import json
import re

from . import schema
from .reader import KEYWORDS, OLD
from .units import Quantity, format as quantity

BARE = re.compile(r'[^\s"#(][^\s"#]*$')
PURPOSE = ("use", "market", "country")


class ConvertError(ValueError):
    pass


def word(v, head=False):
    """A value as a word where one reads back as it is, else a quoted string; `head`: TYPE and PARTNO of a part,
    where a keyword or an attribute key would be read as one."""
    v = str(v)
    if v and BARE.match(v) and _balanced(v) and v not in ("-", "=") and not (head and (
            v in KEYWORDS or v in schema.COMPONENT or v in ("set", "no-bom") or v in OLD)):
        return v
    return string(v)


def _balanced(v):
    depth = 0
    for ch in v:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if depth < 0:
            return False
    return depth == 0


def string(v):
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def number(v):
    return repr(v) if isinstance(v, float) else str(v)


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def attrs(obj, table, skip, where):
    """(head words, lines) of an object's keys: words, numbers, booleans and ranges as `KEY VALUE` on the head, text
    attributes on lines of their own, lists and tables as `set KEY JSON`; a key the table does not know refused."""
    head, lines = [], []
    for k, v in obj.items():
        if k in skip:
            continue
        kind = table.get(k)
        if kind is None:
            raise ConvertError(f"{where}: key {k!r} has no form in the circuit language – the attribute table "
                               "(edakit/lang/schema.py) lists the keys it passes through")
        if k == "bom" and table is schema.COMPONENT:
            head.append("no-bom" if v is False else "bom yes")
        elif kind == "boolean" and isinstance(v, bool):
            head.append(k if v else f"{k} no")
        elif kind in ("number", "number_or_range") and isinstance(v, (int, float)) and not isinstance(v, bool):
            head.append(f"{k} {number(v)}")
        elif kind == "range" and isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
            head.append(f"{k} {quantity(Quantity(v[0], v[1], schema.UNIT.get(k)))}")
        elif kind == "word" and isinstance(v, (str, int, float)) and not isinstance(v, bool):
            head.append(f"{k} {word(v)}")
        elif kind == "string" and isinstance(v, str):
            lines.append(f"{k} {string(v)}")
        elif kind == "list" and k in ("satisfies", "decision") and isinstance(v, list) and v and all(
                isinstance(x, str) for x in v):
            lines.append(f"{k} {' '.join(word(x) for x in v)}")
        else:
            lines.append(f"set {k} {compact(v)}")
    return head, lines


def _range(v):
    if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
        return quantity(Quantity(v[0], v[1], "V"))
    return None


def to_circuit(source, design):
    """The flat statements of a graph: `source` the inner graph as the file has it, `design` its Design."""
    from ..graph_form import FormError, converted, entry_map, problems, resolved, written
    if bad := problems(source, design):
        raise FormError("; ".join(bad[:12]) + (f" (and {len(bad) - 12} more)" if len(bad) > 12 else ""))
    g = converted(resolved(source, design))
    out = []
    done = {"components", "nets", "cables", "layout", "locks", "accept", "name", "version", "date", "description",
            "purpose", "conventions", "ground", "grounds"}

    head = ["graph", word(g["name"]) if g.get("name") else "-"]
    for k in ("version", "date"):
        if k in g:
            head += [k, word(g[k])]
    out.append(" ".join(head))
    if "description" in g:
        out.append(f"description {string(g['description'])}")
    if isinstance(g.get("purpose"), dict):
        p = g["purpose"]
        line = ["purpose", word(p["use"]) if "use" in p else ""]
        line += [f"{k} {word(p[k])}" for k in PURPOSE[1:] if k in p]
        out.append(" ".join(x for x in line if x))
        if "notes" in p:
            out.append(f"  notes {string(p['notes'])}")
        out += [f"set purpose.{k} {compact(v)}" for k, v in p.items() if k not in (*PURPOSE, "notes")]
    for k, v in (g.get("conventions") or {}).items():
        out.append(f"convention {word(k)} {string(v)}")
    if "ground" in g:
        out.append(f"ground {word(g['ground'])}")
    if g.get("grounds"):
        out.append("grounds " + " ".join(word(x) for x in g["grounds"]))

    locks = dict((g.get("locks") or {}).get("pins") or {})
    marked = set()

    # parts
    if g.get("components"):
        out.append("")
    for src, c in zip(source.get("components") or [], g.get("components") or []):
        des = c["designator"]
        line = ["part", des, word(c["type"], True) if c.get("type") else "-",
                word(c["part"], True) if c.get("part") is not None else "-"]
        skip = {"designator", "type", "part", "label", "pins", "nc", "accept", "notes"}
        words, more = attrs(c, schema.COMPONENT, skip, f"components.{des}")
        line += words
        if "label" in c:
            line.append(string(c["label"]))
        out.append(" ".join(line))
        if isinstance(c.get("nc"), list) and c["nc"]:
            nc = [w.partition(".")[2] for w in written(design, [f"{des}.{p}" for p in c["nc"]], False)]
            out.append("  nc " + " ".join(word(x) for x in nc))
        if "pins" in src and c.get("pins") != entry_map(design, des) and isinstance(c.get("pins"), dict):
            out.append("  pins " + " ".join(f"{k}={v}" for k, v in c["pins"].items()))
        out += [f"  {x}" for x in more]
        for k, v in (c.get("accept") or {}).items():
            out.append(f"  accept {word(k)} {string(v)}")
        if "notes" in c:
            out.append(f"  notes {string(c['notes'])}")

    # nets
    if g.get("nets"):
        out.append("")
    for n in g.get("nets") or []:
        name = n["name"]
        line = ["net", word(name)]
        if (r := _range(n.get("v"))) is not None:
            line.append(r)
        refs = list(n.get("pins") or [])
        for w in written(design, refs):
            des, _, rest = w.partition(".")
            stands = [f"{des}.{h}" for h in design.resolve(des, rest)] if rest and des in design.comps else [w]
            line.append(w)
            if stands and all(locks.get(r) == name for r in stands):
                line.append("(locked)")
                marked.update(stands)
        skip = {"name", "pins", "v", "accept", "notes"}
        if "v" in n and _range(n.get("v")) is None:
            skip.discard("v")
        words, more = attrs({k: v for k, v in n.items() if not (k == "v" and _range(v) is not None)},
                            schema.NET, skip, f"nets.{name}")
        line += words
        out.append(" ".join(line))
        out += [f"  {x}" for x in more]
        for k, v in (n.get("accept") or {}).items():
            out.append(f"  accept {word(k)} {string(v)}")
        if "notes" in n:
            out.append(f"  notes {string(n['notes'])}")

    # cables, the layout, the locks left, the graph's accept, the rest
    tail = []
    if "cables" in g:
        if not g["cables"]:
            tail.append("set cables []")
        for c in g["cables"]:
            pairs = [f"{design.word(c['from'], a)}={design.word(c['to'], b)}" if c.get("from") in design.comps
                     and c.get("to") in design.comps else f"{a}={b}" for a, b in (c.get("pins") or {}).items()]
            words, more = attrs(c, schema.CABLE, {"name", "from", "to", "pins"}, f"cables.{c.get('name')}")
            tail.append(" ".join(["cable", word(c["name"]), word(c["from"]), word(c["to"]), *pairs, *words]))
            tail += [f"  {x}" for x in more]
    lay = g.get("layout") or {}
    for k, v in lay.items():
        if k in ("fixed", "edge") and isinstance(v, list):
            tail.append(f"layout {k} " + " ".join(word(x) for x in v))
        elif k == "near" and isinstance(v, dict):
            for part, host in v.items():
                hosts = host if isinstance(host, list) else [host]
                tail.append(f"layout near {word(part)} " + " ".join(word(h) for h in hosts))
        elif k == "notes" and isinstance(v, list):
            tail += [f"layout note {string(x)}" for x in v]
        elif k in ("loops", "apart") and isinstance(v, list) and all(isinstance(x, dict) for x in v):
            limit = "max_mm" if k == "loops" else "min_mm"
            for x in v:
                a, b = x.get("a"), x.get("b")
                if k == "loops":
                    a, b = (_one(design, a), _one(design, b))
                line = [f"layout {'loop' if k == 'loops' else 'apart'}", word(a), word(b)]
                if limit in x:
                    line.append(f"{limit} {number(x[limit])}")
                if "what" in x:
                    line.append(string(x["what"]))
                if set(x) - {"a", "b", limit, "what"}:
                    raise ConvertError(f"layout.{k}: keys {sorted(set(x) - {'a', 'b', limit, 'what'})} have no form")
                tail.append(" ".join(line))
        else:
            tail.append(f"set layout.{k} {compact(v)}")
    for ref, net in locks.items():
        if ref not in marked:
            tail.append(f"lock {_one(design, ref)} {word(net)}")
    for k, v in (g.get("locks") or {}).items():
        if k != "pins":
            tail.append(f"set locks.{k} {compact(v)}")
    for k, v in (g.get("accept") or {}).items():
        tail.append(f"accept {word(k)} {string(v)}")
    for k, v in g.items():
        if k not in done:
            if k not in schema.GRAPH or k == "derivations":
                raise ConvertError(f"the graph's key {k!r} has no form in the circuit language")
            tail.append(f"set {k} {compact(v)}")
    if tail:
        out += [""] + tail
    from .fmt import format
    return format("\n".join(out) + "\n")


def _one(design, ref):
    des, dot, num = str(ref).partition(".")
    return f"{des}.{design.word(des, num)}" if dot and des in design.comps else ref
