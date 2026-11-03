"""The formatter of the circuit language: the canonical layout of a source, comments kept (language 3, T.5).

    format(text, path)   the text laid out: two spaces per level, one space between words, lines of at most 118
                         characters, a long string over several lines; statements in the source's order, never
                         reordered; blank lines kept, several as one; an own-line comment before the line it preceded,
                         an end-of-line comment on its line

A part and a net without a comment inside are laid out as language 11 writes them: the head – `part DES TYPE PARTNO`
with its word attributes and the label, `net NAME RANGE` with its pins and word attributes –, then a line each for
nc, pins, alias, the text attributes, the lists, `set`, every accept and the notes. One with a comment inside keeps
the author's lines. Every other statement keeps its lines too; only `layout`, `grounds`, `covers`, `optional` and
`use` wrap between their words, every statement inside its strings.
"""

from __future__ import annotations

import json
import re

from . import schema
from .reader import CompileError, read

WIDTH = 118
STEP = 2
WRAP = ("layout", "grounds", "covers", "optional", "use", "lock")
LINE_KEYWORDS = ("nc", "pins", "alias", "without")
PART_ORDER = list(schema.COMPONENT)
NET_ORDER = list(schema.NET)


def _escape(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


class Out:
    """The lines written so far, with the rule for blank lines."""

    def __init__(self):
        self.lines = []

    def blank(self):
        if self.lines and self.lines[-1] != "":
            self.lines.append("")

    def add(self, text):
        self.lines.append(text)

    def lead(self, lead, indent):
        for x in lead:
            if x == "":
                self.blank()
            else:
                self.add(" " * indent + x.raw)

    def text(self):
        while self.lines and self.lines[-1] == "":
            self.lines.pop()
        while self.lines and self.lines[0] == "":
            self.lines.pop(0)
        return "\n".join(self.lines) + "\n" if self.lines else ""


def string_pieces(value, col, cont):
    """The text of a string written from column `col`, broken at single spaces so that each line keeps within the
    width; a break continues at column `cont`. Returns the text with its line breaks."""
    words = re.split(r"(?<=\S) (?=\S)", _escape(value))
    out, line, at = [], '"', col + 1
    for k, w in enumerate(words):
        piece = w if line in ('"', "") else " " + w
        last = k == len(words) - 1
        need = len(piece) + (1 if last else 0)
        if line not in ('"', "") and at + need > WIDTH:
            out.append(line)
            line, at, piece = "", cont, w
        line += piece
        at += len(piece)
    out.append(line + '"')
    return ("\n" + " " * cont).join(out)


def render(tok):
    """A token's text when it does not wrap: a string re-escaped, every other token as written."""
    return f'"{_escape(tok.value)}"' if tok.kind == "string" else tok.raw


def flow(out, indent, items, cont=None, prefix=None, comment=None, wrap=True):
    """Write items – each a list of tokens that stays on one line – from `indent`; with `wrap` a new line at `cont`
    when one does not fit (with `prefix` before it: a line keyword repeated). A lone string that does not fit is broken
    inside instead, while at least a few characters of it fit; a string is broken inside wherever it overruns."""
    cont = indent + STEP if cont is None else cont
    line, col, first = " " * indent, indent, True
    for item in items:
        texts = [render(t) for t in item]
        width = sum(len(x) for x in texts) + len(texts) - 1
        lone_string = len(item) == 1 and item[0].kind == "string"
        if not first and wrap and col + 1 + width > WIDTH and not (lone_string and col + 12 <= WIDTH):
            out.add(line)
            line = " " * cont + (prefix + " " if prefix else "")
            col, first = len(line), True
        for tok, x in zip(item, texts):
            sep = "" if first else " "
            if tok.kind == "string" and col + len(sep) + len(x) > WIDTH:
                x = string_pieces(tok.value, col + len(sep), cont + STEP)
            line += sep + x
            col = len(line) - line.rfind("\n") - 1
            first = False
    if comment is not None:
        line += "  " + comment.raw
    out.add(line)


def _compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def _json_lines(value, ind):
    """[(indent, text)] of a list's or a table's members below its opening bracket: one to a line, compact where the
    line fits, else opened in turn two deeper; each closing bracket ends the last line of its members – no line below
    the statement is less indented than the first, as the reader asks of continuation lines."""
    items = list(value.items()) if isinstance(value, dict) else [(None, v) for v in value]
    close = "}" if isinstance(value, dict) else "]"
    out = []
    for n, (k, v) in enumerate(items):
        prefix = "" if k is None else json.dumps(k, ensure_ascii=False) + ": "
        text = prefix + _compact(v)
        if ind + len(text) + 2 <= WIDTH or not isinstance(v, (dict, list)) or not v:
            out.append((ind, text))
        else:
            out.append((ind, prefix + ("{" if isinstance(v, dict) else "[")))
            out.extend(_json_lines(v, ind + STEP))
        if n < len(items) - 1:
            out[-1] = (out[-1][0], out[-1][1] + ",")
    out[-1] = (out[-1][0], out[-1][1] + close)
    return out


def _key(item):
    k = item[1][0].raw
    return "bom" if k == "no-bom" else k


def _lines_of(st):
    """{id(token): index of its line in the statement}."""
    return {id(t): k for k, ln in enumerate(st.lines()) for t in ln.toks}


def _commented(st):
    lines = st.lines()
    return any(ln.comment is not None for ln in lines[1:]) or any(x != "" for ln in lines[1:] for x in ln.lead)


class Formatter:
    def __init__(self, src):
        self.src = src
        self.out = Out()

    def run(self):
        for st in self.src.syntax:
            self.statement(st, 0)
        self.out.lead(self.src.tail, 0)
        return self.out.text()

    def statement(self, st, level):
        indent = level * STEP
        self.out.lead(st.head.lead, indent)
        node = self.node_of(st)
        if st.keyword.keyword("set") and len(st.head.toks) >= 3:
            self.set_statement(st, indent)
        elif node is not None and not _commented(st):
            (self.part if st.keyword.raw == "part" else self.net)(node, st, indent)
        elif node is not None:
            self.by_lines(node, st, indent)
        else:
            wrap = st.keyword.raw in WRAP
            for k, ln in enumerate(st.lines()):
                if k:
                    self.out.lead(ln.lead, indent + STEP)
                at = indent if k == 0 else indent + STEP
                flow(self.out, at, [[t] for t in ln.toks], comment=ln.comment, wrap=wrap)
        for b in st.body:
            self.statement(b, level + 1)

    def set_statement(self, st, indent):
        """`set KEY JSON`: the JSON written again – compact on one line where it fits, else one key or item to a line
        below the statement."""
        toks = st.head.toks
        last = (st.cont[-1].toks if st.cont else toks)[-1]
        value = json.loads(self.src.text[toks[2].start:last.end])
        head = " " * indent + f"set {toks[1].raw} "
        compact = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
        comment = "  " + st.head.comment.raw if st.head.comment is not None else ""
        if len(head) + len(compact) <= WIDTH or not isinstance(value, (dict, list)) or not value:
            self.out.add(head + compact + comment)
            return
        lines = _json_lines(value, indent + 2 * STEP)
        self.out.add(head + ("{" if isinstance(value, dict) else "[") + comment)
        for ind, ln in lines:
            self.out.add(" " * ind + ln)

    def node_of(self, st):
        if not st.keyword.keyword("part", "net"):
            return None
        return self.nodes.get(id(st))

    @property
    def nodes(self):
        if not hasattr(self, "_nodes"):
            self._nodes = {}

            def walk(nodes):
                for n in nodes:
                    if getattr(n, "syntax", None) is not None:
                        self._nodes[id(n.syntax)] = n
                    walk(getattr(n, "body", []) or [])
            walk(self.src.statements)
        return self._nodes

    # --- a part and a net, laid out ----------------------------------------------------------------------------------
    def set_items(self, node, item):
        """A `set` item with its JSON as one line of compact JSON."""
        key = item[1][1].raw if len(item[1]) > 1 else ""
        value = next((v for k, v in node.attrs if k == "set:" + key), None)
        text = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
        return [item[1][0], item[1][1], _Raw(text)]

    def tail(self, node, items, cont):
        """The lines after the head: nc, pins, alias, without, text attributes, lists, set, accept, notes."""
        for kind in LINE_KEYWORDS:
            for it in items:
                if it[0] == kind:
                    self._keyword_line(it[1], cont)
        for kind in ("string", "list", "set", "accept", "notes"):
            for it in items:
                if it[0] == kind:
                    toks = self.set_items(node, it) if kind == "set" else it[1]
                    flow(self.out, cont, [[t] for t in toks], cont=cont)

    def _keyword_line(self, toks, cont):
        flow(self.out, cont, [[toks[0]], *[[t] for t in toks[1:]]], cont=cont, prefix=toks[0].raw)

    def part(self, node, st, indent):
        items = node.items
        head = next((it[1] for it in items if it[0] == "head"), [])
        attrs = sorted((it for it in items if it[0] == "attr"),
                       key=lambda it: PART_ORDER.index(_key(it)) if _key(it) in PART_ORDER else len(PART_ORDER))
        label = next((it[1] for it in items if it[0] == "label"), None)
        line = [[t] for t in head] + [it[1] for it in attrs]
        if label is not None:
            string = label[-1]
            bare_ok = node.part is not None or attrs or node.type is None
            line.append([string] if bare_ok else [_Raw("label"), string])
        flow(self.out, indent, line, cont=indent + STEP, comment=st.head.comment)
        self.tail(node, items, indent + STEP)

    def net(self, node, st, indent):
        items = node.items
        head = next((it[1] for it in items if it[0] == "head"), [])
        pins = [it[1] for it in items if it[0] == "pin"]
        attrs = sorted((it for it in items if it[0] == "attr"),
                       key=lambda it: NET_ORDER.index(_key(it)) if _key(it) in NET_ORDER else len(NET_ORDER))
        flow(self.out, indent, [[t] for t in head] + pins + [it[1] for it in attrs], cont=indent + STEP,
             comment=st.head.comment)
        self.tail(node, items, indent + STEP)

    def by_lines(self, node, st, indent):
        """A part or a net with a comment inside: its items on the lines the author wrote them on."""
        where = _lines_of(st)
        lines = st.lines()
        per = [[] for _ in lines]
        for kind, toks in node.items:
            if toks:
                per[where.get(id(toks[0]), 0)].append((kind, toks))
        for k, ln in enumerate(lines):
            at = indent if k == 0 else indent + STEP
            if k:
                self.out.lead(ln.lead, at)
            its = per[k]
            if len(its) == 1 and its[0][0] in LINE_KEYWORDS:
                toks = its[0][1]
                flow(self.out, at, [[toks[0]], *[[t] for t in toks[1:]]], cont=at, prefix=toks[0].raw,
                     comment=ln.comment)
                continue
            flat = []
            for kind, toks in its:
                if kind == "head":
                    flat += [[t] for t in toks]
                elif kind == "set":
                    flat.append(self.set_items(node, (kind, toks)))
                else:
                    flat.append(toks)
            flow(self.out, at, flat, cont=indent + STEP, comment=ln.comment)


class _Raw:
    """A piece of text that is no token of the source: a keyword the formatter adds, JSON it writes again."""
    kind = "word"

    def __init__(self, raw):
        self.raw = raw
        self.value = raw


def format(text, path="<source>", role=None):
    """The canonical text of a source; CompileError when it does not read."""
    if role is None:
        role = "requirements" if re.search(r"^(need|requirement)\b", text, re.M) else "graph"
    src = read(text, path, role)
    if src.errors:
        raise CompileError(src.errors)
    return Formatter(src).run()
