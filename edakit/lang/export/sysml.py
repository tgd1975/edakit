"""The element tree in SysML v2's textual notation (language 10, the SysML v2 column)."""

from __future__ import annotations

from .model import name

KEYWORDS = {"partdef": "part def", "part": "part", "port": "port", "attr": "attribute", "conn": "connection",
            "req": "requirement", "package": "package"}


def render(el, indent=0, kw=KEYWORDS, kernel=False):
    pad = "    " * indent
    if el.kind == "doc":
        text = str(el.value).replace("*/", "* /")
        return [f"{pad}doc /* {text} */"]
    if el.kind == "meta":
        body = " ".join(f"{k} = {v};" for k, v in el.props.items())
        return [f"{pad}@{el.type} {{ {body} }}"]
    if el.kind == "satisfy":
        return [] if kernel else [f"{pad}satisfy {name(el.name)} by {el.value};"]
    if el.kind == "dependency":
        return [f"{pad}dependency {name(el.name)} from {el.ends[1]} to {el.ends[0]};"]
    if el.kind == "attr" and el.redefines:
        return [f"{pad}{':>> ' if not kernel else ':>> '}{name(el.name)} = {el.value};"]
    head = kw[el.kind]
    if el.kind == "package":
        lines = [f"{pad}package {name(el.name)} {{"]
        lines += [f"{pad}    private import {i};" for i in el.imports]
        for c in el.children:
            lines += render(c, indent + 1, kw, kernel)
        return lines + [f"{pad}}}"]
    title = f"{head} {':>> ' if el.redefines else ''}{name(el.name)}"
    if el.type:
        title += f" : {el.type}"
    if el.specializes:
        title += " :> " + ", ".join(el.specializes)
    if el.kind == "conn" and el.ends:
        if kernel:
            title += f" from {el.ends[0]} to {el.ends[1]}" if el.binary else f" ({', '.join(el.ends)})"
        else:
            title += f" connect {el.ends[0]} to {el.ends[1]}" if el.binary else f" connect ({', '.join(el.ends)})"
    if el.kind == "attr":
        return [f"{pad}{title} {'default' if el.default else '='} {el.value};" if el.value is not None
                else f"{pad}{title};"]
    body = []
    for c in el.children:
        body += render(c, indent + 1, kw, kernel)
    if el.kind == "req":
        if el.props.get("subject"):
            body.append(f"{pad}    doc /* subject: {el.props['subject']} */")
        if el.props.get("require"):
            body.append(f"{pad}    doc /* require: {el.props['require']} */" if kernel else
                        f"{pad}    require constraint {{ doc /* {el.props['require']} */ }}")
    if not body:
        return [f"{pad}{title};"]
    return [f"{pad}{title} {{", *body, f"{pad}}}"]


def text(export):
    lines = []
    for el in [*export.before, export.root]:
        lines += render(el)
    return "\n".join(lines) + "\n"
