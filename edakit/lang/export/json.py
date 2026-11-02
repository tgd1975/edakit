"""The element tree as the JSON serialization of KerML clause 10.4 (T.22): an array of element objects with @id,
@type – SysML's metaclass names for `graph sysml`, KerML's for `graph kerml` – and the metaclass's properties; the
relationships – memberships, typings, redefinitions, specializations – as elements of their own, references as
{"@id": …}. The ids are UUID version 5 of the project's name and the element's qualified name."""

from __future__ import annotations

import json

from .model import element_id

SYSML = {"package": "Package", "partdef": "PartDefinition", "part": "PartUsage", "port": "PortUsage",
         "attr": "AttributeUsage", "conn": "ConnectionUsage", "meta": "MetadataUsage", "doc": "Documentation",
         "req": "RequirementUsage", "satisfy": "SatisfyRequirementUsage", "dependency": "Dependency"}
KERML = {"package": "Package", "partdef": "Structure", "part": "Feature", "port": "Feature", "attr": "Feature",
         "conn": "Connector", "meta": "MetadataFeature", "doc": "Documentation", "req": "Feature",
         "satisfy": "Feature", "dependency": "Dependency"}
METACLASSES = set(SYSML.values()) | set(KERML.values()) | {"OwningMembership", "FeatureTyping", "Redefinition",
                                                           "Subclassification", "FeatureValue", "LiteralString"}


def elements(export, view="sysml"):
    kinds = SYSML if view == "sysml" else KERML
    out = []

    def walk(el, path, owner):
        label = el.name or el.type or el.kind
        qualified = f"{path}::{label}" if path else str(label)
        n = sum(1 for x in out if x.get("qualifiedName") == qualified)
        qualified += f"#{n}" if n else ""
        eid = element_id(export.project, f"{view}:{qualified}")
        obj = {"@id": eid, "@type": kinds[el.kind], "qualifiedName": qualified}
        if el.name:
            obj["declaredName"] = str(el.name)
        if el.kind == "doc":
            obj["body"] = el.value
        if el.value is not None and el.kind == "attr":
            obj["value"] = el.value
        if el.kind == "meta":
            obj["metaclass"] = f"Electrical::{el.type}"
            obj["values"] = dict(el.props)
        if el.kind == "conn":
            obj["ends"] = list(el.ends)
        out.append(obj)
        if owner is not None:
            mid = element_id(export.project, f"{view}:{qualified}::membership")
            out.append({"@id": mid, "@type": "OwningMembership", "membershipOwningNamespace": {"@id": owner},
                        "ownedMemberElement": {"@id": eid}})
            obj["owningMembership"] = {"@id": mid}
        if el.type and el.kind not in ("meta", "doc"):
            out.append({"@id": element_id(export.project, f"{view}:{qualified}::typing"), "@type": "FeatureTyping",
                        "typedFeature": {"@id": eid}, "type": el.type})
        for s in el.specializes:
            out.append({"@id": element_id(export.project, f"{view}:{qualified}::{s}"), "@type": "Subclassification",
                        "subclassifier": {"@id": eid}, "superclassifier": f"Electrical::{s}"})
        if el.redefines:
            out.append({"@id": element_id(export.project, f"{view}:{qualified}::redefinition"),
                        "@type": "Redefinition", "redefiningFeature": {"@id": eid}, "redefinedFeature": str(el.name)})
        for c in el.children:
            walk(c, qualified, eid)
    walk(export.root, "", None)
    return out


def text(export, view="sysml"):
    return json.dumps(elements(export, view), indent=1, ensure_ascii=False) + "\n"


def problems(items):
    """What is wrong with an export's JSON: an @id twice, a reference that resolves to nothing, an unknown @type."""
    ids = [x["@id"] for x in items]
    out = [f"@id {i} twice" for i in sorted({i for i in ids if ids.count(i) > 1})]
    have = set(ids)

    def refs(v):
        if isinstance(v, dict):
            if set(v) == {"@id"}:
                yield v["@id"]
            else:
                for x in v.values():
                    yield from refs(x)
        elif isinstance(v, list):
            for x in v:
                yield from refs(x)
    for x in items:
        out += [f"{x['@id']}: @type {x['@type']}" for _ in [0] if x["@type"] not in METACLASSES]
        for k, v in x.items():
            if k != "@id":
                out += [f"{x['@id']}.{k}: {r} resolves to nothing" for r in refs(v) if r not in have]
    return out
