"""The requirements in the export (T.23, language 10): needs and requirements as requirement usages of the library's
definitions, `satisfy … by …` from the graph's satisfies, a need's derivation into a requirement as a dependency."""

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
    for e in entries:
        for ref in e.from_ if e.kind == "requirement" else []:
            if ref in ids:
                out.append(El("dependency", f"{ref}_{e.id}", ends=[name(ref), name(e.id)]))
    return out

