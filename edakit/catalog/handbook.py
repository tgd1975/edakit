"""The handbook's tables, generated from the catalog (concept docs/concepts/done/rules-at-scale.md, section 6): the
codes of each stage, the parts schema, the check IDs of before with the codes that replace them.

    python -m edakit.catalog.handbook [--write]

A generated section sits between `<!-- edakit:generated KIND ARGS -->` and `<!-- edakit:end -->` in a chapter of
handbook/; KIND is codes (ARGS: engine prefixes), kinds (the parts schema) or replaced (the map of before). Without
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


def render(kind, args):
    if kind == "codes":
        return codes_section(args.split())
    if kind == "kinds":
        return kinds_section()
    if kind == "replaced":
        return replaced_section()
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
