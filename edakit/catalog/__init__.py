"""The catalog – the single source of what edakit checks (concept docs/concepts/new/rules-at-scale.md, section 6).

    codes.toml        every code ENGINE.relation: title, rule, why, fix, sources, severity, grades, the old IDs
    tables/*.toml     numbers from standards and manufacturers, each row with its source and tag (r read, x extracted,
                      v to verify)
    kinds.toml        the parts schema: per kind the limits and values an entry may give, with their units
    ../domains/*.toml the profiles a project switches on (edakit.toml [project] domains)

    edakit rules            the engines and the codes with their titles
    edakit explain CODE …   rule, why, fix and sources of a code (an old ID such as G-8 names the codes replacing it)

What is read about a rule – the explanations below `edakit check`, the handbook's tables, the reviewers' questions –
is generated from here, never written by hand.
"""

from __future__ import annotations

import re
import tomllib
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).parent
SEVERITIES = ("error", "warning", "note", "pending")
STAGES = "PGESLF"
TAGS = ("r", "x", "v")
CODE = re.compile(r"([A-Z]+)\.([a-z][a-z0-9_]*)")
OLD_ID = re.compile(r"[PGESLFH]-\d+")


@lru_cache(maxsize=1)
def data():
    return tomllib.loads((HERE / "codes.toml").read_text(encoding="utf-8"))


def codes():
    return data()["codes"]


def engines():
    return data()["engines"]


def retired():
    """{code: what holds it now} – codes taken out of the engines; a name once used is not used again."""
    return data().get("retired") or {}


def code(name):
    """The entry of a code, or None."""
    return codes().get(name)


def engine_of(name):
    """'LIMITS' for 'LIM.v' – the engine whose prefix the code carries."""
    prefix = name.partition(".")[0]
    return next((e for e, x in engines().items() if x["prefix"] == prefix), None)


def title(name):
    return (code(name) or {}).get("title", "")


def label(name):
    t = title(name)
    return f"{name} ({t})" if t else name


def default_severity(name, grade=""):
    """The catalog's severity of a code, or of one of its grades (a grade the code does not know takes the code's)."""
    e = code(name) or {}
    return (e.get("grades") or {}).get(grade) or e.get("severity", "error")


@lru_cache(maxsize=1)
def old_map():
    """{old check ID: [codes that replace it]} – for reading protocols of before the restructuring."""
    out = {}
    for name, e in codes().items():
        for old in e.get("replaces", []):
            out.setdefault(old, []).append(name)
    return out


@lru_cache(maxsize=None)
def table(name):
    """A table of tables/<name>.toml as a dict."""
    return tomllib.loads((HERE / "tables" / f"{name}.toml").read_text(encoding="utf-8"))


def table_names():
    return sorted(p.stem for p in (HERE / "tables").glob("*.toml"))


def explain(name, indent="    "):
    """Lines that explain a code: rule, why, fix, sources, severity; for an old ID the codes that replace it."""
    if OLD_ID.fullmatch(name):
        new = old_map().get(name)
        return [f"{name}: replaced by {', '.join(new)} (edakit explain {new[0]})"] if new else []
    if name in retired():
        return [f"{name}: retired – {retired()[name]}"]
    e = code(name)
    if not e:
        return []
    sev = e["severity"] + "".join(f", {g}: {s}" for g, s in (e.get("grades") or {}).items())
    lines = [f"{label(name)}: {e['rule']}", f"{indent}why: {e['why']}", f"{indent}what to do: {e['fix']}",
             f"{indent}severity: {sev} (the profile may set others – edakit/domains)"]
    lines += [f"{indent}source: {s}" for s in e.get("sources", [])]
    return lines


def lint():
    """Problems of the catalog itself: every code well-named with engine, title, rule, why, fix and a known severity;
    every table row with a source tagged r. -> [text]"""
    out = []
    prefixes = {x["prefix"] for x in engines().values()}
    for name, e in codes().items():
        m = CODE.fullmatch(name)
        if not m or m[1] not in prefixes:
            out.append(f"{name}: not ENGINE.relation with a known engine prefix ({', '.join(sorted(prefixes))})")
        for key in ("title", "rule", "why", "fix"):
            if not str(e.get(key) or "").strip():
                out.append(f"{name}: no {key}")
        for sev in [e.get("severity"), *(e.get("grades") or {}).values()]:
            if sev not in SEVERITIES:
                out.append(f"{name}: severity {sev!r} – one of {', '.join(SEVERITIES)}")
        for old in e.get("replaces", []):
            if not OLD_ID.fullmatch(old):
                out.append(f"{name}: replaces {old!r} – no check ID of before the restructuring")
    out += [f"{name}: retired and still a code – a name once retired is not used again"
            for name in retired() if name in codes()]
    for t in table_names():
        out += [f"tables/{t}.toml: {p}" for p in table_problems(table(t))]
    return out


def table_problems(t):
    """A table's rows without a source tagged r: the table's own [table] source counts for rows without one."""
    head = t.get("table") or {}
    out = [] if head.get("source") and head.get("tag") in TAGS else ["[table] needs source and tag"]

    def rows(node, path):
        if isinstance(node, list):
            for i, x in enumerate(node):
                yield from rows(x, f"{path}[{i}]")
        elif isinstance(node, dict) and any(not isinstance(v, (dict, list)) for v in node.values()):
            yield path, node
        elif isinstance(node, dict):
            for k, v in node.items():
                yield from rows(v, f"{path}.{k}" if path else k)
    for path, row in rows({k: v for k, v in t.items() if k != "table"}, ""):
        tag = row.get("tag", head.get("tag"))
        if tag != "r":
            out.append(f"{path}: tag {tag!r} – a table row is read from its source (r) before it is used")
        if "source" not in row and not head.get("source"):
            out.append(f"{path}: no source")
    return out


# --- command line ----------------------------------------------------------------------------------------------------
def main_rules(args):
    """edakit rules: the engines and their codes with titles and severities; with names, as edakit explain."""
    if args.ids:
        return main_explain(args)
    for eng, e in engines().items():
        names = [n for n in codes() if engine_of(n) == eng]
        print(f"{eng} – {e['decides']}")
        for n in names:
            c = codes()[n]
            grades = ", ".join(f"{g} {s}" for g, s in (c.get("grades") or {}).items())
            print(f"  {n:<20} {c['severity']:<8} {c['title']}" + (f"  ({grades})" if grades else ""))
    print(f"\n{len(codes())} codes. Rule, why, fix and sources: edakit explain <code>. Severities are the catalog's; "
          "a project's domains may set others.")
    return 0


def main_explain(args):
    unknown = []
    for name in args.ids:
        lines = explain(name)
        if lines:
            print("\n".join(lines) + "\n")
        else:
            unknown.append(name)
    for name in unknown:
        near = [n for n in codes() if n.startswith(name.split(".")[0] + ".")]
        print(f"{name}: no code of the catalog" + (f" – {', '.join(near)}" if near else ""))
    return 1 if unknown else 0
