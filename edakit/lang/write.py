"""`block add` on a source of the circuit language (T.16): the usage it writes, at the place it goes.

    use_text(block, instance, connect, comps, rename, sets, without)   the `use` statement: the parameters --set sets,
                                       every port bound (gnd and an optional port left open excepted), every part bound
                                       to its designator with what differs from the block – lcsc, part, value, board
    insert_use(text, statement)        the source with the statement after its last top-level part or use before the
                                       first net, else at the end – every other byte kept
"""

from __future__ import annotations

from .convert import word
from .tokens import statements, tokenize


def use_text(block, instance, connect, comps, rename, sets=None, without=()):
    head = f"use {block['name']} {instance}"
    if sets:
        head += " (" + ", ".join(f"{k} = {v}" for k, v in sets.items()) + ")"
    loose = set((block.get("optional") or {}).get("ports", []))
    binds = []
    for port in block.get("ports") or {}:
        if port in connect:
            binds.append(f"{port} = {word(connect[port])}")
        elif port != "gnd" and port not in loose:
            binds.append(f"{port} = {f'{instance}_{port}'.upper()}")
    lines = [" ".join([head, *binds])]
    if without:
        lines.append("  without " + " ".join(without))
    by_des = {c["designator"]: c for c in comps}
    for c in block["components"]:
        if c["designator"] not in rename:
            continue
        des = rename[c["designator"]]
        new = by_des.get(des, {})
        line = [f"  {c['designator']} = {des}"]
        if new.get("part") != c.get("part") and new.get("part") is not None:
            line.append(word(new["part"]))
        for key in ("lcsc", "value", "board"):
            if new.get(key) is not None and new.get(key) != c.get(key):
                line.append(f"{key} {word(new[key])}")
        lines.append(" ".join(line))
    return "\n".join(lines) + "\n"


def insert_use(text, statement):
    """The text with the statement inserted after the last top-level `part` or `use` before the first `net`, else
    appended – every other byte as it was."""
    lines, _ = tokenize(text)
    sts = statements(lines)
    end, first_net = None, None
    for st in sts:
        kw = st.keyword.raw
        if kw == "net" and first_net is None:
            first_net = st
        if kw in ("part", "use") and first_net is None:
            last = st.cont[-1] if st.cont else st.head
            body_last = st.body[-1] if st.body else None
            end = (body_last.cont[-1] if body_last and body_last.cont else body_last.head) if body_last else last
    src = text.splitlines(keepends=True)
    if end is None:
        sep = "" if not text or text.endswith("\n") else "\n"
        return text + sep + statement
    # the last physical line of that statement: a string may run over the following lines
    k = end.number - 1
    tail = end.toks[-1] if end.toks else None
    if tail is not None:
        k += text[tail.start:tail.end].count("\n")
    return "".join(src[:k + 1]) + statement + "".join(src[k + 1:])
