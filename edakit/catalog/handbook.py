"""The handbook's tables, generated from the catalog (concept docs/concepts/done/rules-at-scale.md, section 6): the
codes of each stage, the parts schema, the check IDs of before with the codes that replace them.

    python -m edakit.catalog.handbook [--write]

A generated section sits between `<!-- edakit:generated KIND ARGS -->` and `<!-- edakit:end -->` in a chapter of
handbook/; KIND is table (ARGS: engine prefixes – code, title and severity, each code linked to its engine's page of
the catalog), codes (the same with the rule and its details), engines (each engine's prefix and what it decides),
kinds (the parts schema), replaced (the map of before) or command (ARGS: a subcommand – its synopsis and help line from the command line's own parser). Without
--write the command lists the sections that differ from the catalog; tests/test_catalog.py holds the handbook to it.

Chapter 19 takes three more kinds from the tests' own data, not the catalog (concept
docs/concepts/new/verification-and-validation.md): references (each reference circuit of tests/reference.py with its
domain, its description, why it stands for its domain and its seeded faults), designs (each open design of
tests/open_designs/ with its licence, why it was chosen, its findings counted by judgement and its known gaps) and
tally (the counts of both).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from . import codes, old_map

ROOT = Path(__file__).resolve().parents[2] / "handbook"
TESTS = ROOT.parent / "tests"
JUDGEMENTS = ("real", "lacks", "criterion", "known gap")
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


# --- chapter 19: the reference circuits and the open designs of the tests ---------------------------------------------
def reference():
    """tests/reference.py of the repository as a module: REFERENCES, WHY and FAULTS."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("edakit_reference_circuits", TESTS / "reference.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def paragraph(text, label):
    """The paragraph of a README that starts with the bold label, on one line – "" when there is none."""
    if label not in text:
        return ""
    return " ".join(text.split(label, 1)[1].split("\n\n", 1)[0].split())


def open_design(path):
    """An open design of tests/open_designs/: its title, licence, why, findings counted by judgement, false alarms
    fixed and known gaps [(stage, code, place, why)]."""
    import tomllib
    readme = (path / "README.md").read_text(encoding="utf-8")
    company = tomllib.loads((path / "edakit.toml").read_text(encoding="utf-8"))["project"]["company"]
    judged = tomllib.loads((path / "findings.toml").read_text(encoding="utf-8"))
    found = [(stage, f) for stage in ("check", "sim") for f in judged.get(stage, [])]
    return {"name": path.name, "title": readme.splitlines()[0].lstrip("# ").split(" – ")[0],
            "licence": company.split("(", 1)[1].split(")", 1)[0] if "(" in company else None,
            "why": paragraph(readme, "**Why this design:**"),
            "counts": {j: sum(1 for _, f in found if f["judged"] == j) for j in JUDGEMENTS},
            "fixed": len(judged.get("fixed", [])),
            "gaps": [(stage, f["code"], f["place"], " ".join(f["why"].split())) for stage, f in found
                     if f["judged"] == "known gap"]}


def open_designs():
    return [open_design(p) for p in sorted((TESTS / "open_designs").iterdir()) if (p / "edakit.toml").is_file()]


def counted(counts):
    return ", ".join(f"{n} {j}" for j, n in counts.items() if n) or "none"


def references_section():
    """Each reference circuit: its domain, what it is, why, and its seeded faults with the codes each raises."""
    from .. import profile
    ref, out = reference(), []
    for name, build in ref.REFERENCES.items():
        domain = f"domain `{name}`" if name in profile.names() else "no domain – core, on every board"
        out.append(f"**{name}** – {domain} · [drawing and faults](../docs/catalog/circuit-{name}.html)  ")
        out.append(" ".join((build.__doc__ or "").split()) + "  ")
        out.append(f"*Why:* {ref.WHY[name]}")
        out.append("")
        out += [f"- {what} → {', '.join(f'`{c}`' for c in sorted(found))}" for what, _, found in ref.FAULTS[name]]
        out.append("")
    return "\n".join(out)


def designs_section():
    """Each open design: its licence, why, its findings counted by judgement, the false alarms fixed, its known gaps."""
    out = []
    for d in open_designs():
        licence = d["licence"] or "no licence stated – only the circuit's facts transcribed"
        out.append(f"**{d['title']}** (`{d['name']}`) – {licence} · "
                   f"[drawing and findings](../docs/catalog/open-{d['name']}.html)  ")
        out.append(f"*Why:* {d['why']}  ")
        out.append(f"Findings judged: {counted(d['counts'])}; false alarms fixed: {d['fixed']}.")
        out.append("")
        out += [f"- Known gap: `{code}` at {place} ({stage}) – {why}" for stage, code, place, why in d["gaps"]]
        if d["gaps"]:
            out.append("")
    return "\n".join(out)


def tally_section():
    """The counts of chapter 19: reference circuits, seeded faults, their codes, the domains without a circuit, the
    open designs and their judgements."""
    from .. import profile
    ref, designs = reference(), open_designs()
    faults = [f for fs in ref.FAULTS.values() for f in fs]
    raised = {c for _, _, found in faults for c in found}
    bare = sorted(set(profile.names()) - set(ref.REFERENCES))
    total = {j: sum(d["counts"][j] for d in designs) for j in JUDGEMENTS}
    return "\n".join([
        f"- Reference circuits: {len(ref.REFERENCES)}, with {len(faults)} seeded faults that raise {len(raised)} "
        f"codes: {', '.join(f'`{c}`' for c in sorted(raised))}.",
        f"- Domains without a reference circuit: {', '.join(f'`{n}`' for n in bare) or 'none'}.",
        f"- Open designs: {len(designs)}, with {sum(total.values())} findings judged – {counted(total)}; "
        f"{sum(d['fixed'] for d in designs)} false alarms fixed."])


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
    if kind == "command":
        return command_section(args)
    if kind == "references":
        return references_section()
    if kind == "designs":
        return designs_section()
    if kind == "tally":
        return tally_section()
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
