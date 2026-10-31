"""The graph's two files: the TOML form a person writes and the resolved JSON edakit generates beside it
(docs/concepts/new/circuit-language-plan.md, steps L.5 and L.6; the decisions of docs/concepts/done/circuit-language.md).

    edakit graph json            the resolved graph on stdout: {"graph": …} as a JSON graph has always been – pin
                                 numbers everywhere (the Design's reading of every pin word), the full pin map of
                                 every component (its parts entry's where the graph has none), the lists in the order
                                 of the file
    edakit graph json --write    writes it beside a TOML graph: hardware/graph.toml -> hardware/graph.json – never over
                                 a JSON graph, which is the source itself
    edakit graph json --check    exit 2 when the committed file differs from the graph, with what differs (pre-commit
                                 hook); writes nothing
    edakit graph convert         moves a JSON project to the TOML form once: hardware/graph.toml, [project] graph in
                                 edakit.toml, the resolved hardware/graph.json in place of the source, the sign-offs of
                                 scope circuit carried over; --dry-run prints what would change

The generated graph.json is derived: the circuit hash takes the TOML source (gate.state_files names [project] graph),
and the data name graph of the scripts is the source too; the generated file is a file like any other there. It
exists so that a rewire through a parts entry – a corrected role, LED5.anode now on pad 2 – shows as pin numbers in a
diff, where the TOML does not change (decision 4), and so that project scripts that read the graph as JSON keep
running (decided by Claude and confirmed, 5).

The TOML writer (convert): components, nets and cables as tables keyed by designator and name, in the order of the
JSON, their keys in the JSON's order; the other tables as tables, nested tables one level deep as [table.key]; pins by
the word rule of Design.word – and a name or role several pins share (U1.GND) for all of them where they all stand in
the net, wherever (the pins of a net are compared sorted: decided by Claude and confirmed, 2) – in nc only for a run
in the entry's order; the pin map left out where it equals the entry's; accept as dotted keys, other maps inline where
they fit and dotted where not; every value through toml_edit.literal, the one TOML value writer edakit has (block add
writes with it too) – a string longer than the line as a multi-line string with line-ending backslashes. A graph TOML
cannot hold or the checks reject – null, a designator or net name twice, a pin that names none of its part –
is refused with what to fix in the JSON. What is written is read back before anything is written: it gives the same
resolved graph, or convert stops.
"""

from __future__ import annotations

import copy
import json
import re
import sys
import tomllib
from pathlib import Path

from . import toml_edit
from .design import KEYED, Design, graph_of_toml, load_graph, load_parts

PIN_REFERENCE = ("'<designator>.<pin>' with the pin's name or role, else its symbol number – the parts entry says "
                 "which pin that is")
HEAD = ("designator", "type", "label", "part", "lcsc", "value", "bom", "board", "supplier", "spare")   # before `pins`
HEADER = ["# The hardware graph (handbook 3.1): components, nets and cables keyed by designator and name, pins by name",
          "# or role through the parts entries. edakit graph json writes the resolved graph beside it (graph.json)."]


class FormError(ValueError):
    pass


# --- the resolved graph (L.5) ---------------------------------------------------------------------------------------
def design_of(path, parts, boards, graph):
    """The Design of a graph, built on a copy: it resolves every pin word and takes the entries' maps (L.1, L.2)."""
    return Design(path, None, boards, graph=copy.deepcopy(graph), parts=parts)


def resolved(source, design):
    """The graph as a JSON graph holds it: `source` (the inner graph as the file has it) with what the Design read –
    pin numbers in the nets, nc, locks.pins, layout.loops and the cables; every component's pin map, the entry's put
    where a JSON graph has it (after part, lcsc, value and the like) – and nothing else the Design adds."""
    g = copy.deepcopy(design.graph)
    for src, comp in zip(source.get("components") or [], g.get("components") or []):
        if not isinstance(src, dict) or not isinstance(comp, dict):
            continue
        if "board" not in src:
            comp.pop("board", None)
        if "pins" not in src and "pins" in comp:
            pins = comp.pop("pins")
            keys = list(comp)
            at = max((i + 1 for i, k in enumerate(keys) if k in HEAD), default=len(keys))
            items = list(comp.items())
            comp.clear()
            comp.update(items[:at] + [("pins", pins)] + items[at:])
    return g


def render(graph, indent=1):
    """The resolved graph as the file: {"graph": …}, UTF-8 as it is, `indent` as the file had it."""
    return json.dumps({"graph": graph}, indent=indent, ensure_ascii=False) + "\n"


def indent_of(path):
    """The indent of a JSON file, as edakit's writers keep it (block.write_json); 1 for a new one."""
    path = Path(path)
    if not path.exists():
        return 1
    m = re.search(r"^( +)\S", path.read_text(encoding="utf-8"), re.M)
    return len(m.group(1)) if m else 1


def generated_path(cfg):
    """Where the resolved graph of a TOML graph goes: beside it, as .json; None for a JSON graph, the source itself."""
    graph = Path(cfg.graph)
    return graph.with_suffix(".json") if graph.suffix == ".toml" else None


def keyed(graph):
    """The graph with components, nets and cables keyed by designator and name, so that a difference names its place
    (nets.LED0.pins) – a list with a key missing or twice stays a list."""
    out = dict(graph) if isinstance(graph, dict) else {}
    for key, field in KEYED.items():
        rows = out.get(key)
        if isinstance(rows, list) and all(isinstance(r, dict) and isinstance(r.get(field), str) for r in rows):
            names = [r[field] for r in rows]
            if len(set(names)) == len(names):
                out[key] = {r[field]: {k: v for k, v in r.items() if k != field} for r in rows}
    return out


def main_json(cfg, args):
    from .firmware import differences
    source = load_graph(cfg.graph)
    design = design_of(cfg.graph, load_parts(cfg.parts), list(cfg.boards), source)
    g = resolved(source, design)
    out = generated_path(cfg)
    words = [f"{where}: {why}" for where, _, why in design.unresolved]
    summary = f"{len(g.get('components') or [])} components, {len(g.get('nets') or [])} nets"
    if args.check:
        if out is None:
            print(f"{cfg.relative(cfg.graph)} is the graph – nothing is generated from a JSON graph (edakit graph json "
                  "--check checks the file beside a TOML graph)")
            return 0
        rel = cfg.relative(out)
        if not out.exists():
            print(f"{rel}: drift – not written yet (edakit graph json --write)")
            return 2
        old, text = out.read_text(encoding="utf-8"), render(g, indent_of(out))
        if old == text:
            print(f"{rel} is current: {summary}")
            return 0
        try:
            data = json.loads(old)
            lines = differences(keyed(data.get("graph", data) if isinstance(data, dict) else data), keyed(g))
        except json.JSONDecodeError:
            lines = ["not valid JSON"]
        print(f"{rel}: drift – it no longer matches {cfg.relative(cfg.graph)} and the parts entries (edakit graph json "
              "--write writes it again):")
        for line in lines or ["formatting only"]:
            print(f"  {line}")
        return 2
    if args.write:
        if out is None:
            print(f"edakit graph json: {cfg.relative(cfg.graph)} is the graph itself – --write writes the file beside "
                  "a TOML graph, never over a JSON one", file=sys.stderr)
            return 1
        text = render(g, indent_of(out))
        same = out.exists() and out.read_text(encoding="utf-8") == text
        if not same:
            out.write_text(text, encoding="utf-8")
        print(f"{cfg.relative(out)} {'unchanged' if same else 'written'}: resolved from {cfg.relative(cfg.graph)} – "
              f"{summary}")
    else:
        sys.stdout.write(render(g, indent_of(out) if out else indent_of(cfg.graph)))
    for line in words:
        print(f"  ! {line} – STRUCT.pin (edakit check); the word stays as written", file=sys.stderr)
    return 0


# --- the TOML writer (L.6) ------------------------------------------------------------------------------------------
def element(header, body):
    """A component, net or cable: its keys in their order; accept as dotted keys (accept."LIM.i" = "…"), another map
    inline where it fits on its line and dotted where not."""
    out = ["", header]
    for k, v in body.items():
        if isinstance(v, dict) and v:
            inline = toml_edit.line(k, v)
            if k == "accept" or len(inline) > toml_edit.WIDTH:
                out += [toml_edit.line(x, y, f"{toml_edit.key(k)}.") for x, y in v.items()]
                continue
            out.append(inline)
        else:
            out.append(toml_edit.line(k, v))
    return out


def table(name, body):
    """A table of the graph – purpose, conventions, layout, locks, accept: its keys, then a map in it as [name.key]."""
    nested = [k for k, v in body.items() if isinstance(v, dict) and v]
    out = [toml_edit.line(k, v) for k, v in body.items() if k not in nested]
    out = ["", f"[{name}]"] + out if out or not nested else []
    for k in nested:
        out += ["", f"[{name}.{toml_edit.key(k)}]"] + [toml_edit.line(x, y) for x, y in body[k].items()]
    return out


def written(design, refs, anywhere=True):
    """The words for a list of pins ["DES.NUM", …]: each pin's first word that names it alone (Design.word), or a
    word several pins share (U1.GND) where all of them are in the list and none is written yet – wherever they stand
    with `anywhere` (a net), else only as a run in the order the word reads them (nc) –, at the place of the first;
    else the number. A list with a pin twice keeps every pin as it is."""
    plain = len(set(refs)) != len(refs)
    present, done, grouped, out = set(refs), set(), set(), []
    for i, ref in enumerate(refs):
        if ref in grouped:                  # a shared word written at an earlier place stands for it
            continue
        des, dot, num = str(ref).partition(".")
        word = num
        for w in [] if plain or not dot else design.words(des, num):
            group = [f"{des}.{h}" for h in design.resolve(des, w)]
            if group == [ref]:
                word = w
                break
            if len(group) > 1 and ref in group and not done & set(group) and (
                    present >= set(group) if anywhere else refs[i:i + len(group)] == group):
                word = w
                grouped.update(group)
                break
        done.add(ref)
        out.append(f"{des}.{word}" if dot else ref)
    return out


def problems(source, design):
    """What TOML cannot hold or the checks reject, so that convert refuses: null, a designator or net name missing or
    twice, a pin that names none of its part."""
    out = [f"{where}: null – TOML has none" for where in nulls(keyed(source))]
    for key, field in KEYED.items():
        rows = source.get(key)
        if rows in (None, []):
            continue
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            out.append(f"{key}: not a list of tables")
            continue
        names = [r.get(field) for r in rows]
        out += [f"{key}: a {field} missing or not a string" for n in names if not isinstance(n, str)][:1]
        out += [f"{key}: {n} twice" for n in dict.fromkeys(n for n in names if isinstance(n, str) and names.count(n) > 1)]
    for net in design.graph.get("nets") or []:
        refs = net.get("pins") if isinstance(net, dict) and isinstance(net.get("pins"), list) else []
        for ref in refs:
            des, dot, num = str(ref).partition(".")
            if des not in design.comps:
                out.append(f"net {net.get('name')}: {ref} – no part {des}")
            elif not dot or num not in (design.comps[des].get("pins") or {}):
                out.append(f"net {net.get('name')}: {ref} names no pin of {des}")
    for des, c in design.comps.items():
        out += [f"{des}: nc {p} names no pin of {des}" for p in c.get("nc") or [] if str(p) not in (c.get("pins") or {})]
    return out + [why for _, _, why in design.unresolved]


def nulls(value, where=""):
    """The places of null in a JSON value: components.R1.notes, layout.loops[0].a."""
    if value is None:
        return [where]
    if isinstance(value, dict):
        return [w for k, v in value.items() for w in nulls(v, f"{where}.{k}" if where else str(k))]
    if isinstance(value, list):
        return [w for i, v in enumerate(value) for w in nulls(v, f"{where}[{i}]")]
    return []


def entry_map(design, des):
    key = design.entry_key(des)
    pins = design.parts[key].get("pins") if key else None
    return {num: (p or {}).get("name", num) for num, p in pins.items()} if isinstance(pins, dict) else None


def converted(graph):
    """The graph with the convention a converted project states – pins by name or role –, where it states one."""
    if isinstance(graph.get("conventions"), dict) and "pin_reference" in graph["conventions"]:
        graph["conventions"]["pin_reference"] = PIN_REFERENCE
    return graph


def to_toml(source, design):
    """The TOML form of a JSON graph: `source` the inner graph as the file has it, `design` its Design."""
    if bad := problems(source, design):
        raise FormError("; ".join(bad[:12]) + (f" (and {len(bad) - 12} more)" if len(bad) > 12 else ""))
    g = converted(resolved(source, design))
    tables = [k for k, v in g.items() if (isinstance(v, dict) or k in KEYED) and v]
    out = HEADER + [toml_edit.line(k, v) for k, v in g.items() if k not in tables]
    for key in tables:
        if key == "components":
            for src, c in zip(source["components"], g["components"]):
                des = c["designator"]
                body = {k: v for k, v in c.items() if k != "designator"}
                if "pins" not in src or c["pins"] == entry_map(design, des):
                    body.pop("pins", None)
                if isinstance(c.get("nc"), list):
                    body["nc"] = [w.partition(".")[2] for w in written(design, [f"{des}.{p}" for p in c["nc"]], False)]
                out += element(f"[components.{toml_edit.key(des)}]", body)
        elif key == "nets":
            for n in g["nets"]:
                body = {k: v for k, v in n.items() if k != "name"}
                if isinstance(n.get("pins"), list):
                    body["pins"] = written(design, n["pins"])
                out += element(f"[nets.{toml_edit.key(n['name'])}]", body)
        elif key == "cables":
            for c in g["cables"]:
                body = {k: v for k, v in c.items() if k != "name"}
                if isinstance(c.get("pins"), dict):
                    body["pins"] = {design.word(c.get("from"), a): design.word(c.get("to"), b)
                                    for a, b in c["pins"].items()}
                out += element(f"[cables.{toml_edit.key(c['name'])}]", body)
        else:
            body = dict(g[key])
            if key == "layout" and isinstance(body.get("loops"), list):
                body["loops"] = [{**lp, **{e: one(design, lp[e]) for e in "ab" if isinstance(lp.get(e), str)}}
                                 if isinstance(lp, dict) else lp for lp in body["loops"]]
            if key == "locks" and isinstance(body.get("pins"), dict):
                body["pins"] = {one(design, r): n for r, n in body["pins"].items()}
            out += table(toml_edit.key(key), body)
    return "\n".join(out) + "\n"


def one(design, ref):
    des, dot, num = str(ref).partition(".")
    return f"{des}.{design.word(des, num)}" if dot else ref


# --- edakit graph convert -------------------------------------------------------------------------------------------
def set_graph(text, value):
    """edakit.toml with [project] graph = value: its graph line's value replaced – the comment after it kept –, or a
    line added after the last key of [project]."""
    lines = text.splitlines(keepends=True)
    head = next((i for i, ln in enumerate(lines) if re.match(r"\s*\[project\]\s*(#.*)?$", ln)), None)
    if head is None:
        raise FormError("edakit.toml has no [project] table")
    end = next((i for i in range(head + 1, len(lines)) if re.match(r"\s*\[", lines[i])), len(lines))
    at = next((i for i in range(head + 1, end) if re.match(r"\s*graph\s*=", lines[i])), None)
    if at is not None:
        m = re.match(r"""(\s*graph\s*=\s*)("(?:[^"\\]|\\.)*"|'[^']*')(.*)""", lines[at], re.S)
        if m:
            lines[at] = m.group(1) + toml_edit.quoted(value) + m.group(3)
    else:
        last = max((i for i in range(head + 1, end) if re.match(r"""\s*[\w"'-]+\s*=""", lines[i])), default=head)
        lines[last] = lines[last] if lines[last].endswith("\n") else lines[last] + "\n"
        lines.insert(last + 1, f"graph = {toml_edit.quoted(value)}\n")
    new = "".join(lines)
    if tomllib.loads(new).get("project", {}).get("graph") != value:
        raise FormError("edakit.toml: [project] graph could not be set by a line edit – set it by hand")
    return new


def canonical(graph):
    from .release import gate
    return json.dumps(gate.arranged(graph), sort_keys=True, ensure_ascii=False)


def main_convert(cfg, args):
    from . import config, convert
    from .firmware import differences
    from .release import gate
    src_path = Path(cfg.graph)
    rel = cfg.relative(src_path)
    if src_path.suffix == ".toml":
        print(f"{rel} is TOML already – nothing to convert")
        return 0
    target = src_path.with_suffix(".toml")
    if target.exists():
        print(f"edakit graph convert: {cfg.relative(target)} is there already – remove it, or set [project] graph to it",
              file=sys.stderr)
        return 1
    parts, boards = load_parts(cfg.parts), list(cfg.boards)
    source = load_graph(src_path)
    try:
        design = design_of(src_path, parts, boards, source)
        text = to_toml(source, design)
    except (FormError, toml_edit.TomlEditError) as e:
        print(f"edakit graph convert: {rel}: {e} – what TOML cannot hold or STRUCT reports (edakit check): fix the "
              "JSON first", file=sys.stderr)
        return 1
    except (KeyError, TypeError, AttributeError) as e:
        print(f"edakit graph convert: {rel} does not load as a graph ({e!r}) – edakit check names what is wrong",
              file=sys.stderr)
        return 1
    want = converted(resolved(source, design))
    back = graph_of_toml(text, target)
    got = resolved(back, design_of(target, parts, boards, back))
    if canonical(got) != canonical(want):           # the writer's own check: what it writes reads back to the graph
        lines = differences(keyed(gate.arranged(want)), keyed(gate.arranged(got)))
        print(f"edakit graph convert: the TOML would not read back to {rel} – nothing written:\n  "
              + "\n  ".join(lines), file=sys.stderr)
        return 1
    value = target.relative_to(cfg.root).as_posix() if target.is_relative_to(cfg.root) else str(target)
    try:
        toml_text = set_graph(cfg.path.read_text(encoding="utf-8"), value)
    except FormError as e:
        print(f"edakit graph convert: {e}", file=sys.stderr)
        return 1
    generated = render(got, indent_of(src_path))
    lines = text.count("\n")
    if args.dry_run:
        sys.stdout.write(text)
        print(f"\nwould write {cfg.relative(target)} ({lines} lines; {rel} has "
              f"{src_path.read_text(encoding='utf-8').count(chr(10))})")
        print(f"would set [project] graph = {toml_edit.quoted(value)} in {cfg.relative(cfg.path)}")
        print(f"would write {rel} again: the resolved graph, generated from {cfg.relative(target)} (edakit graph json)")
        print("the circuit hash takes the TOML graph from then on: when the files are the signed ones, the sign-offs "
              "of scope 'circuit' keep counting (rehashed)")
        return 0
    before = gate.state_hash(cfg)
    target.write_text(text, encoding="utf-8")
    cfg.path.write_text(toml_text, encoding="utf-8")
    src_path.write_text(generated, encoding="utf-8")
    print(f"{cfg.relative(target)} written: {lines} lines, components, nets and cables keyed, pins by name or role")
    print(f"{cfg.relative(cfg.path)}: [project] graph = {toml_edit.quoted(value)}")
    print(f"{rel} written: the resolved graph, generated from {cfg.relative(target)} – commit both; the pre-commit "
          "hook runs edakit graph json --check")
    new = config.load(cfg.path)
    why = (f"the graph moved to {value} (edakit graph convert): the circuit hash takes its data, every value and "
           "connection carried over; the files were the signed ones")
    if line := convert.carry_signoffs(new, before, by="edakit graph convert", why=why):
        print(line)
    if new.firmware is not None:
        print("with [firmware]: edakit firmware writes the contract again – its state_sha256 is the new circuit hash")
    return 0


def main(cfg, args):
    if args.action == "json":
        if args.write and args.check:
            print("edakit graph json: --write or --check, not both", file=sys.stderr)
            return 1
        return main_json(cfg, args)
    return main_convert(cfg, args)
