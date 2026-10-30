"""S-expressions as KiCad writes them: lists whose first element is a keyword, quoted strings, bare words and numbers.

    loads(text) -> [...]       a file as nested lists: "strings" as str, bare words and numbers as Sym
    dumps(node) -> text        nested lists back to text: str quoted, Sym and numbers bare, True/False as yes/no
    find(node, key)            the child lists of node whose keyword is key
    first(node, key)           the first of them, or None

The first element of a list is always written bare (it is the keyword). Numbers get at most 6 decimals – KiCad's
resolution is 1 nm. route.py reads Specctra with its own small reader; KiCad strings can hold escaped quotes, this one
reads them.
"""

from __future__ import annotations

import re
import uuid

NAMESPACE = uuid.UUID("6c1d0f6e-2b54-4d2e-9a7e-6b3f2b8c5e10")   # uid(): the same object gets the same uuid every run
LINE = 100          # a list whose text fits in this many characters stays on one line


class Sym(str):
    """A bare word: a keyword, a token such as smd or roundrect, a number as read."""


def uid(*parts):
    """A uuid derived from parts – stable from run to run, so that a regenerated file differs only where it changed."""
    return str(uuid.uuid5(NAMESPACE, "/".join(str(p) for p in parts)))


def number(v):
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def quote(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def atom(v):
    if isinstance(v, Sym):
        return str(v)
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        return number(v)
    return quote(v)


def dumps(node, indent=0):
    """Text of a list (and its children); short lists on one line, long ones with a child per line, tab-indented as
    KiCad writes them."""
    head = str(node[0])
    parts = [atom(v) if not isinstance(v, list) else dumps(v, indent + 1) for v in node[1:]]
    flat = "(" + " ".join([head, *parts]) + ")"
    if len(flat) + indent <= LINE and "\n" not in flat:
        return flat
    pad = "\t" * (indent + 1)
    lines, words = [], [head]
    for v, text in zip(node[1:], parts):
        if isinstance(v, list):
            lines.append(pad + text)
        elif lines:
            lines.append(pad + text)
        else:
            words.append(text)            # leading bare values stay on the keyword's line: (pad "1" smd rect
    return "(" + " ".join(words) + "\n" + "\n".join(lines) + "\n" + "\t" * indent + ")"


TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def loads(text):
    """Text -> nested lists."""
    stack, cur = [], []
    for t in TOKEN.findall(text):
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            if not stack:
                raise ValueError("unbalanced ')' in S-expression")
            done, cur = cur, stack.pop()
            cur.append(done)
        elif t.startswith('"'):
            cur.append(re.sub(r"\\(.)", lambda m: "\n" if m.group(1) == "n" else m.group(1), t[1:-1]))
        else:
            cur.append(Sym(t))
    if stack:
        raise ValueError("unbalanced '(' in S-expression")
    return cur[0] if cur else []


def find(node, key):
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            yield c


def first(node, key, default=None):
    return next(find(node, key), default)


def value(node, key, default=None):
    """The first value of the child key: value((at 1 2), "at") -> "1"."""
    c = first(node, key)
    return c[1] if c and len(c) > 1 else default


def floats(node, key):
    """The numbers of the child key: floats(pad, "at") -> [x, y] or [x, y, angle]."""
    c = first(node, key)
    return [float(v) for v in c[1:] if not isinstance(v, list)] if c else []
