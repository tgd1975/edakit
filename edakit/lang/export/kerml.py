"""The element tree in KerML's textual notation – the kernel view (language 10, the KerML column): a part definition
is a struct, a part, a port and an attribute are features, a connection is a connector; KerML has no requirement –
a requirement is written as a feature of the library's definition, its condition as documentation."""

from __future__ import annotations

import re

from .sysml import render

KEYWORDS = {"partdef": "struct", "part": "feature", "port": "feature", "attr": "feature", "conn": "connector",
            "req": "feature", "package": "package"}
LIBRARY = [(r"\battribute def\b", "datatype"), (r"\benum def\b", "datatype"), (r"\bport def\b", "struct"),
           (r"\babstract part def\b", "abstract struct"), (r"\bpart def\b", "struct"),
           (r"\bconnection def\b", "assoc struct"), (r"\bmetadata def\b", "metaclass"), (r"\bcalc def\b", "function"),
           (r"\brequirement def\b", "predicate"), (r"\bverification def\b", "behavior"),
           (r"\battribute\b", "feature"), (r"\bport\b", "feature"), (r"\bpart\b", "feature"),
           (r"\bconnection\b", "connector"), (r"\breturn\b", "return feature"), (r"\bin\b(?= \w+ :)", "in feature")]


def text(export):
    lines = []
    for el in [*export.before, export.root]:
        lines += render(el, kw=KEYWORDS, kernel=True)
    return "\n".join(lines) + "\n"


def library(sysml_text):
    """Electrical.kerml: the library's text with KerML's keywords – an enumeration as a datatype with its values as
    features."""
    out = sysml_text.replace("library package Electrical", "library package Electrical")
    out = re.sub(r"datatype (\w+) \{ ([^}]*) \}", lambda m: m.group(0), out)
    for pat, rep in LIBRARY:
        out = re.sub(pat, rep, out)
    out = re.sub(r"enum def (\w+) \{([^}]*)\}", lambda m: f"datatype {m.group(1)} {{{m.group(2)}}}", out)
    out = re.sub(r"(datatype (?:Purpose|Binding|Status) \{)([^}]*)\}",
                 lambda m: m.group(1) + " ".join(f"feature {x.strip()};" for x in m.group(2).split(";") if x.strip())
                 + " }", out)
    return out
