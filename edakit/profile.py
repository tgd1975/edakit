"""Profiles: the domains a project switches on and what follows from them (concept
docs/concepts/new/rules-at-scale.md, section 5).

    edakit domains [--review electrical|regulatory|pcb]

A domain is a file of edakit/domains/: the findings it switches on ([switch] on: a code, or code:topic for part of
one), the severities it sets (per purpose too), the facts it requires per kind or graph type, the hints it applies,
the questions it gives the reviewers. core is always on; what no other domain switches on is core's. A project names
its domains in edakit.toml, [project] domains = ["usb", "radio"]. Without the key, every domain the graph suggests is
on (suggested_by: a pin role, a value, a radio of a part in the graph) – a project that names its domains and leaves
one out the graph suggests gets a note STRUCT.domain, no silent gap. Severities of several domains: the strictest
wins (error, pending, warning, note).
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

from .findings import Finding, Profile
from .radio import radios

DIR = Path(__file__).with_name("domains")
STRICT = {"error": 0, "pending": 1, "warning": 2, "note": 3}
REVIEWERS = ("electrical", "regulatory", "pcb")


@lru_cache(maxsize=1)
def domains():
    """{name: the domain file as a dict}, core first."""
    out = {p.stem: tomllib.loads(p.read_text(encoding="utf-8")) for p in sorted(DIR.glob("*.toml"))}
    return {"core": out.pop("core"), **out}


def names():
    """The domains a project may name (core is always on)."""
    return [n for n in domains() if n != "core"]


def suggests(design, rule):
    """Whether the graph has what a domain's suggested_by names."""
    parts = [design.part(des) or {} for des in design.comps]
    if any(p.get("kind") in rule.get("kinds", []) for p in parts):
        return True
    roles = set(rule.get("roles", []))
    if roles and any(pin.get("role") in roles for p in parts for pin in (p.get("pins") or {}).values()):
        return True
    keys = set(rule.get("values", []))
    if keys and any(keys & set(p.get("values") or {}) for p in parts):
        return True
    marks = set(rule.get("nets", []))
    if marks and any(marks & set(net) for net in design.nets.values()):
        return True
    if rule.get("cables") and (design.graph.get("cables") or any(c.get("off_board") for c in design.comps.values())):
        return True
    if rule.get("radio"):
        if (design.graph.get("purpose") or {}).get("radio") is not None:
            return True
        return any(radios(p) for p in parts)     # a transmitter stated, with or without its bands
    return False


def suggested(design):
    return [n for n in names() if suggests(design, domains()[n]["domain"].get("suggested_by") or {})]


class ProjectProfile(Profile):
    """The profile of a project: core and its domains – severities, switches, facts, hints, review questions."""

    def __init__(self, enabled, purpose=None, notes=()):
        files = [domains()[n] for n in ["core", *enabled]]
        severity, by_purpose = {}, {}
        for f in files:
            for key, value in (f.get("severity") or {}).items():
                if isinstance(value, dict):
                    for k, sev in value.items():
                        strictest(by_purpose.setdefault(key, {}), k, sev)
                else:
                    strictest(severity, key, value)
        super().__init__(severity, by_purpose, purpose)
        self.enabled = list(enabled)
        self.claimed = {k for n in names() for k in (domains()[n].get("switch") or {}).get("on", [])}
        self.switched = {k for f in files for k in (f.get("switch") or {}).get("on", [])}
        self.hints = {h for f in files for h in (f.get("hints") or {}).get("apply", [])}
        self.facts = {"type": {}, "kind": {}}
        for f in files:
            for by in ("type", "kind"):
                for k, facts in ((f.get("facts") or {}).get(by) or {}).items():
                    self.facts[by].setdefault(k, []).extend(x for x in facts if x not in self.facts[by].get(k, []))
        self.review = {r: [q for f in files for q in (f.get("review") or {}).get(r, [])] for r in REVIEWERS}
        self.notes = list(notes)

    def on(self, f):
        """A finding is reported: its code (or code:topic) is core's or switched on by an enabled domain; a hint is
        applied by one."""
        if f.code.startswith("HINT."):
            return f.code in self.hints
        keys = [f"{f.code}:{f.topic}", f.code] if f.topic else [f.code]
        if not any(k in self.claimed for k in keys):
            return True
        return any(k in self.switched for k in keys)


def strictest(table, key, sev):
    if key not in table or STRICT[sev] < STRICT[table[key]]:
        table[key] = sev


def build(design, cfg=None):
    """The profile of a project: its domains as named in edakit.toml, else the ones the graph suggests."""
    named = getattr(cfg, "domains", None) if cfg is not None else None
    hint = suggested(design)
    enabled = hint if named is None else list(named)
    notes = [Finding("STRUCT.domain", "G", n, f"the graph suggests the domain {n} ({domains()[n]['domain']['about']})"
                     ", but [project] domains does not name it – its findings are not reported", "edakit/domains",
                     f"add \"{n}\" to [project] domains, or accept STRUCT.domain {n} with the reason")
             for n in hint if n not in enabled]
    return ProjectProfile(enabled, (design.graph.get("purpose") or {}).get("use"), notes)


def lint():
    """Problems of the domain files: every switch, severity and hint names a code (code:topic, code/grade) of the
    catalog and a severity it knows, every fact a kind of the parts schema, every review a reviewer. -> [text]"""
    from . import catalog
    from .schema import kinds
    out = []
    for name, f in domains().items():
        at = f"domains/{name}.toml"
        if (f.get("domain") or {}).get("name") != name or not (f.get("domain") or {}).get("about"):
            out.append(f"{at}: [domain] needs name = {name!r} and about")
        for key in (f.get("switch") or {}).get("on", []):
            if not catalog.code(key.split(":")[0]):
                out.append(f"{at}: switch {key} – no code of the catalog")
        if name == "core" and (f.get("switch") or {}).get("on"):
            out.append(f"{at}: core switches nothing on – what no domain switches on is core's")
        for purpose, table in [(None, f.get("severity") or {})] + [
                (k, v) for k, v in (f.get("severity") or {}).items() if isinstance(v, dict)]:
            for key, sev in table.items():
                if isinstance(sev, dict):
                    continue
                code, _, grade = key.partition("/")
                e = catalog.code(code)
                if not e or (grade and grade not in (e.get("grades") or {})):
                    out.append(f"{at}: severity {key} – no code{'/grade' if grade else ''} of the catalog")
                if sev not in STRICT:
                    out.append(f"{at}: severity {key} = {sev!r} – one of {', '.join(STRICT)}")
            if purpose and purpose not in ("private", "gift", "sale"):
                out.append(f"{at}: [severity.{purpose}] – a purpose: private, gift or sale")
        for h in (f.get("hints") or {}).get("apply", []):
            if not h.startswith("HINT.") or not catalog.code(h):
                out.append(f"{at}: hint {h} – no HINT code of the catalog")
        for k in ((f.get("facts") or {}).get("kind") or {}):
            if k not in kinds()["kinds"]:
                out.append(f"{at}: facts.kind.{k} – no kind of catalog/kinds.toml")
        for r in f.get("review") or {}:
            if r not in REVIEWERS:
                out.append(f"{at}: review.{r} – one of {', '.join(REVIEWERS)}")
    return out


# --- command line ----------------------------------------------------------------------------------------------------
def main(cfg, args):
    from .design import Design
    design = Design.from_config(cfg)
    prof = build(design, cfg)
    hint = suggested(design)
    if args.review:
        questions = prof.review.get(args.review, [])
        print(f"Questions for the {args.review} review from the domains core, {', '.join(prof.enabled) or '–'}:")
        for i, q in enumerate(questions, 1):
            print(f"{i}. {q}")
        return 0
    declared = cfg.domains is not None
    print(f"core – {domains()['core']['domain']['about']} (always on)")
    for n in names():
        how = ("named in [project] domains" if declared else "suggested by the graph") if n in prof.enabled else \
            "off – the graph suggests it" if n in hint else "off"
        print(f"{n} – {domains()[n]['domain']['about']} ({how})")
    print("\n" + ("[project] domains names them." if declared else
                  "No [project] domains: every domain the graph suggests is on."))
    return 0
