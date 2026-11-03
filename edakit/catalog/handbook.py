"""The handbook's tables, generated from the catalog (concept docs/concepts/done/rules-at-scale.md, section 6): the
codes of each stage, the parts schema, the check IDs of before with the codes that replace them.

    python -m edakit.catalog.handbook [--write]

A generated section sits between `<!-- edakit:generated KIND ARGS -->` and `<!-- edakit:end -->` in a chapter of
handbook/; KIND is table (ARGS: engine prefixes – code, title and severity, each code linked to its engine's page of
the catalog), codes (the same with the rule and its details), engines (each engine's prefix and what it decides),
kinds (the parts schema), replaced (the map of before), rules (the circuit language's derivation rules, lang/rules.py)
or command (ARGS: a subcommand – its synopsis and help line from the command line's own parser). Without
--write the command lists the sections that differ from the catalog; tests/test_catalog.py holds the handbook to it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from . import codes, old_map

ROOT = Path(__file__).resolve().parents[2] / "handbook"
BLOCK = re.compile(r"(<!-- edakit:generated ([a-z]+)([^>]*) -->\n)(.*?)(<!-- edakit:end -->)", re.S)


def severity(e):
    return e["severity"] + "".join(f", {g}: {s}" for g, s in (e.get("grades") or {}).items())


def codes_section(prefixes):
    """Each code of the engines with these prefixes: title, severity, what it replaces, the rule and its details."""
    out = []
    for name, e in codes().items():
        if name.split(".")[0] not in prefixes:
            continue
        old = f"; replaces {', '.join(e['replaces'])}" if e.get("replaces") else ""
        out.append(f"**`{name}`** – {e['title']} ({severity(e)}{old})  ")
        out.append(e["rule"])
        out += [f"- {d}" for d in e.get("details", [])]
        out.append("")
    return "\n".join(out)


def page_of(name):
    """The catalog page of a code's engine, relative to a chapter of handbook/ (docs/catalog/build.py writes it)."""
    return f"../docs/catalog/{name.split('.')[0].lower()}.html"


def table_section(prefixes):
    """The short kind: each code of the engines with these prefixes as a row – code, title, severity –, the code
    linked to the catalog page; rule, why, fix and sources are there and in edakit explain."""
    out = ["| Code | Title | Severity |", "| --- | --- | --- |"]
    for name, e in codes().items():
        if name.split(".")[0] in prefixes:
            old = f"; replaces {', '.join(e['replaces'])}" if e.get("replaces") else ""
            out.append(f"| [`{name}`]({page_of(name)}#{name}) | {e['title']} | {severity(e)}{old} |")
    out += ["", "Rule, why, fix and sources of each: `edakit explain CODE`, or the code on its page of the catalog."]
    return "\n".join(out)


def engines_section():
    """Each engine of the catalog: its prefix and what it decides, in the catalog's order."""
    from . import engines
    out = ["| Engine | Decides |", "|---|---|"]
    out += [f"| {e['prefix']} | {e['decides']} |" for e in engines().values()]
    return "\n".join(out)


def kinds_section():
    """Per kind its limits and values; the names every kind may give, the units, the words."""
    from ..schema import kinds
    k = kinds()
    def names(xs):
        return ", ".join(f"`{x}`" for x in xs) or "–"
    out = ["| kind | limits | values |", "|---|---|---|",
           f"| every kind | {names(k['common']['limits'])} | {names(k['common']['values'])} |"]
    out += [f"| `{kind}` | {names(d.get('limits', []))} | {names(d.get('values', []))} |"
            for kind, d in k["kinds"].items()]
    out += ["", f"Per pin: {names(k['common']['pin'])}; and {names(k['free']['pin'])}. Every name ends in its unit: "
                + ", ".join(f"`_{u}` {v}" for u, v in k["units"].items()) + ". Words: "
                + "; ".join(f"`{n}` {', '.join(v)}" for n, v in k["enums"].items()) + "."]
    return "\n".join(out)


def replaced_section():
    """The check IDs of before the restructuring and the codes that replace them."""
    def key(old):
        return "PGESLFHB".index(old[0]), int(old[2:])
    out = ["| before | now |", "|---|---|"]
    out += [f"| {old} | {', '.join(f'`{c}`' for c in new)} |" for old, new in sorted(old_map().items(),
                                                                                         key=lambda x: key(x[0]))]
    return "\n".join(out)


def command_section(name):
    """A subcommand's synopsis and help line, from edakit/cli.py's parser: the options every command shares (-h,
    --config, -v) left out, as 10.5 says them once."""
    from ..cli import build_parser
    sub = build_parser()._subparsers._group_actions[0]
    if name not in sub.choices:
        raise ValueError(f"no subcommand {name!r}")
    usage = " ".join(sub.choices[name].format_usage().replace("usage: ", "", 1).split())
    for shared in (" [-h]", " [--config CONFIG]", " [-v]"):
        usage = usage.replace(shared, "")
    help_ = next(a.help for a in sub._choices_actions if a.dest == name)
    return f"`{usage}`\n\n{help_[0].upper()}{help_[1:]}."


def commands():
    """The subcommands of the command line, in the parser's order."""
    from ..cli import build_parser
    return list(build_parser()._subparsers._group_actions[0].choices)


def render(kind, args):
    if kind == "table":
        return table_section(args.split())
    if kind == "codes":
        return codes_section(args.split())
    if kind == "engines":
        return engines_section()
    if kind == "kinds":
        return kinds_section()
    if kind == "replaced":
        return replaced_section()
    if kind == "rules":                                  # the circuit language's derivation rules (lang/rules.py)
        from ..lang.rules import describe
        return describe() + "\n"
    if kind == "command":
        return command_section(args)
    raise ValueError(f"unknown generated section {kind!r}")


def update(text):
    """The chapter with every generated section rendered anew."""
    return BLOCK.sub(lambda m: m.group(1) + render(m.group(2), m.group(3).strip()).rstrip() + "\n" + m.group(5), text)


def stale(root=ROOT):
    """Chapters whose generated sections differ from the catalog."""
    return [p for p in sorted(Path(root).glob("*.md")) if update(t := p.read_text(encoding="utf-8")) != t]


def main(argv=None):
    write = "--write" in (argv if argv is not None else sys.argv[1:])
    found = stale()
    for p in found:
        if write:
            p.write_text(update(p.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"{'written' if write else 'stale'}: handbook/{p.name}")
    return 1 if found and not write else 0


if __name__ == "__main__":
    sys.exit(main())
