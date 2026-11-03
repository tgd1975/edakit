"""The requirements in the export (T.23, language 10): needs and requirements as requirement usages of the library's
definitions, `satisfy … by …` from the graph's satisfies, a requirement's `from` as a derivation connection of SysML
v2's RequirementDerivation library – one per original, its derived requirements as the other ends (decision 46) –, in
KerML, which has not that library, as a dependency per pair."""

from __future__ import annotations

from .model import El, name, string


def requirements(cfg, graph, usages, paths):
    """[El] of the project's requirements files – none without [project] requirements."""
    if not cfg.requirements:
        return []
    from ...requirements import RequirementsError, load
    try:
        entries = load(cfg)
    except RequirementsError:
        return []
    out = []
    for e in entries:
        typ = "Need" if e.kind == "need" else "CircuitRequirement"
        r = El("req", e.id, typ).add(El("doc", value=e.text))
        r.add(El("attr", "status", value=f"Status::{name(e.status)}", redefines=True))
        if e.kind == "need":
            if e.who:
                r.add(El("attr", "who", value=string(e.who), redefines=True))
        else:
            r.add(El("attr", "binding", value=f"Binding::{name(e.binding)}", redefines=True))
            if e.subject:
                r.props["subject"] = e.subject
            if e.require:
                r.props["require"] = e.require
            if e.verify:
                r.add(El("attr", "verify", value="(" + ", ".join(string(f"{k} {v}") for k, v in e.verify) +
                         ("," if len(e.verify) == 1 else "") + ")", redefines=True))
        out.append(r)
    ids = {e.id for e in entries}
    for kind, key in (("components", "designator"), ("nets", "name")):
        for obj in graph.get(kind) or []:
            for rid in obj.get("satisfies") or []:
                if rid in ids:
                    out.append(El("satisfy", rid, value=paths.get(obj[key], name(obj[key])), props={"inside": True}))
    derived = {}
    for e in entries:
        for ref in e.from_ if e.kind == "requirement" else []:
            if ref in ids and ref != e.id:
                derived.setdefault(ref, []).append(e.id)
    for ref, those in derived.items():
        out.append(El("derivation", f"{ref}_derivation", value=name(ref), ends=[name(x) for x in those],
                      props={"original": ref, "derived": those}))
    return out

