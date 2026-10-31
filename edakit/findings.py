"""Findings – what every engine reports, and the only interface to people and to the model (concept
docs/concepts/done/rules-at-scale.md, section 3).

A finding carries its code (ENGINE.relation), the stage it was found in (P G E S L F), the place (a part, a pin, a
net, a board), what was found – the value against what it was held to –, the source of that limit, and the fix. Its
severity is not the engine's: the profile of the project sets it (edakit/domains), the catalog's default where the
profile says nothing.

    error     blocks edakit check
    warning   the gate wants it accepted in the sign-off file
    note      information
    pending   blocks the release and cannot be accepted (an unverified part, an old stock snapshot)

One mechanism accepts what a person has seen and answered: `accept` with a reason, keyed by code – on a net or a
component of the graph (by "code", or by "code place" for the finding at one pin or designator only), or on the graph
itself keyed by "code" or "code place" (circuit scope: part of the circuit hash), or in the sign-off file for a warning
(release scope). A key "LIM.i/margin" accepts only that grade,
"GEO.spacing:paste" only that topic.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field

from . import catalog

SHOWN = 5          # findings shown per code; the rest is counted (and in the JSON file)
ORDER = {"error": 0, "pending": 1, "warning": 2, "note": 3}


def names_place(text, place):
    """Whether a finding's text names its place: as it is written, or a pin "U1.9" by its word, "U1.PD6 (9)"
    (Design.pin_text) – then the place is not put in front of the text."""
    if place in text:
        return True
    des, dot, num = place.partition(".")
    num = num.split(" ", 1)[0]               # a place "U9.2 (CSB)"
    if not (dot and num):
        return False
    d, n = re.escape(des), re.escape(num)
    return re.search(rf"(?<![\w.]){d}\.(?:{n}(?![\w.])|\S+ \({n}\))", text) is not None


@dataclass
class Finding:
    code: str
    stage: str
    place: str
    text: str                 # what was found: the value against what it is held to
    source: str = ""          # where the limit or the rule comes from
    fix: str = ""             # what to do here; empty: the code's fix
    grade: str = ""           # a sub-case with its own severity: margin, firmware, the name of a missing fact
    topic: str = ""           # part of a code a domain may switch on alone: "cc" of REQ.missing (code:topic)
    scenario: str = ""        # the simulation scenario or run (stage E)
    on: tuple = ()            # where an accept may sit: (("net", "BTN"), ("component", "C1"))
    severity: str = ""        # set by Report.resolve from the profile
    accepted: str = ""        # the reason, once accepted
    data: dict = field(default_factory=dict)   # value, limit, unit … for programs reading the JSON

    @property
    def key(self):
        """'LIM.v E usb/idle C1 7.5 V across …' – what a sign-off's accept pattern is matched against."""
        return " ".join(x for x in (self.code, self.scenario, self.place, self.text) if x)

    @property
    def keyed(self):
        """The accept keys that name this finding, most specific first: code/grade, code:topic, code."""
        return keys(self.code, self.topic, self.grade)

    def line(self):
        where = f"{self.stage}  " + (f"[{self.scenario}] " if self.scenario else "")
        out = where + (self.text if names_place(self.text, self.place) else f"{self.place}: {self.text}")
        if self.source:
            out += f"   ({self.source})"
        if self.fix:
            out += f"   → {self.fix}"
        return out

    def to_dict(self):
        d = {k: v for k, v in asdict(self).items() if v not in ("", (), {}, None)}
        d.pop("on", None)
        return d


def keys(code, topic="", grade=""):
    """The accept keys of a finding, most specific first."""
    return ([f"{code}/{grade}"] if grade else []) + ([f"{code}:{topic}"] if topic else []) + [code]


def accept_reason(obj, code, topic="", grade=""):
    """The reason a net, component or graph (`obj`) gives for accepting a finding of this code, or None."""
    acc = (obj or {}).get("accept") or {}
    return next((acc[k] for k in keys(code, topic, grade) if k in acc), None)


class Profile:
    """The severities a project's domains set: {code or code/grade: severity}, each per purpose (private, gift, sale)
    where a domain says so. Without domains: the catalog's defaults."""

    def __init__(self, severity=None, by_purpose=None, purpose=None):
        self.severity = dict(severity or {})
        self.by_purpose = {p: dict(s) for p, s in (by_purpose or {}).items()}
        self.purpose = purpose

    def of(self, f):
        for key in f.keyed:
            for table in (self.by_purpose.get(self.purpose) or {}, self.severity):
                if key in table:
                    return table[key]
        return catalog.default_severity(f.code, f.grade)


class Report:
    """The findings of one run, with their severities resolved and the graph's accepts applied."""

    def __init__(self, findings=(), profile=None):
        self.findings = list(findings)
        self.profile = profile or Profile()

    def add(self, *findings):
        self.findings += findings

    def resolve(self, graph=None):
        """Severity from the profile; accepted where the graph accepts it – on its net or component, or on the graph
        keyed by code or "code place". -> self"""
        for f in self.findings:
            f.severity = "note" if f.data.get("info") else self.profile.of(f)   # an informational scenario
            if f.data.get("fault") and f.severity == "error":    # a generated fault scenario (FT-8): a warning
                f.severity = "warning"
            if graph is not None and not f.accepted:
                f.accepted = accepted_in_graph(f, graph) or ""
        self.findings.sort(key=lambda f: (ORDER.get(f.severity, 9), f.code))
        return self

    def of(self, severity, accepted=False):
        return [f for f in self.findings if f.severity == severity and bool(f.accepted) == accepted]

    @property
    def errors(self):
        return self.of("error")

    @property
    def warnings(self):
        return self.of("warning")

    @property
    def notes(self):
        return self.of("note")

    @property
    def pending(self):
        return [f for f in self.findings if f.severity == "pending"]   # never accepted

    @property
    def accepted(self):
        return [f for f in self.findings if f.accepted and f.severity != "pending"]

    def counts(self):
        return Counter(f.severity if not f.accepted or f.severity == "pending" else "accepted" for f in self.findings)

    def to_dict(self):
        return {"findings": [f.to_dict() for f in self.findings], "counts": dict(self.counts())}

    def to_json(self):
        return json.dumps(self.to_dict(), indent=1, ensure_ascii=False) + "\n"


def places(f):
    """The places an accept key may name for a finding: its place ("U1.3", "J1", "+5V") and the designator in it."""
    des = f.place.split(".", 1)[0].split(" ", 1)[0]
    return [f.place] + ([des] if des and des != f.place else [])


def accepted_in_graph(f, graph):
    """The reason the graph gives for accepting a finding, or None: accept on its net or component – keyed by code, or
    by "code place" where only the finding at that place (a pin, a designator) is meant –, else on the graph keyed by
    code or by "code place"."""
    nets = {n["name"]: n for n in graph.get("nets", [])}
    comps = {c["designator"]: c for c in graph.get("components", [])}
    for kind, name in f.on:
        obj = (nets if kind == "net" else comps).get(name) or {}
        acc = obj.get("accept") or {}
        for key in f.keyed:
            for k in [f"{key} {p}" for p in places(f)] + [key]:
                if k in acc:
                    return acc[k]
    acc = graph.get("accept") or {}
    for key in f.keyed:
        for k in [f"{key} {p}" for p in places(f)] + [key]:
            if k in acc:
                return acc[k]
    return None


def grouped(findings):
    """{code: [findings]} in the order the findings come – a code with findings of several severities, or some
    accepted, once per severity and acceptance ("GEO.hole" errors, then its notes)."""
    out = defaultdict(list)
    for f in findings:
        out[(f.code, f.severity, bool(f.accepted))].append(f)
    return out


def format_findings(findings, shown=SHOWN, explain=True):
    """The findings grouped by code, each group with its severity and count, the first `shown` of each; below them
    the fix of every code that failed (its rule: edakit explain). -> lines"""
    lines = []
    for (code, _, _), fs in grouped(findings).items():
        sev = fs[0].severity + (" (accepted)" if fs[0].accepted else "")
        lines.append(f"{code} – {catalog.title(code)}: {len(fs)} {sev}")
        for f in fs[:shown]:
            lines.append(f"  {f.line()}")
            if f.accepted:
                lines.append(f"      accepted: {f.accepted}")
        if len(fs) > shown:
            lines.append(f"  … {len(fs) - shown} more (--json)")
    failing = list(dict.fromkeys(c for (c, sev, acc), fs in grouped(findings).items()
                                 if not acc and sev in ("error", "warning")))
    if explain and failing:
        lines.append("\nWhat to do (edakit explain <code> for rule, why and sources):")
        lines += [f"  {c}: {(catalog.code(c) or {}).get('fix', '')}" for c in failing]
    return lines
