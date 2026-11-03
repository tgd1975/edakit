"""Tokens and statements of the circuit language (language 3).

    tokenize(text, path)   [Line]: every physical line that starts code, with its tokens and the blank and comment
                           lines before it (`lead`), so that the formatter can keep them
    statements(lines)      [Statement]: a line at the level's indent and the lines indented deeper below it –
                           continuation lines, or for `def`, `for` and `variant` the body, statements one level deeper

A word is a run of characters without whitespace, `"` and `#`; a `(` inside a word extends it to the matching `)`,
so that `U1.3V3(OUT)` and `series_resistor(i, led = D)` stay one word. A word that starts with `(` is a group:
`(locked)`, the parameters of a definition or a usage – its items split at the commas outside quotes. A string is
`"…"` with `\\"` and `\\\\`; a line break inside reads as one space. `#` starts a comment outside quotes. A tab is an
error; lines may end in CR LF, which reads as LF.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BLOCKS = ("def", "for", "variant")


@dataclass(eq=False)
class LangError(Exception):
    file: str
    line: int
    text: str

    def __str__(self):
        return f"{self.file}:{self.line}: {self.text}"


@dataclass(eq=False)
class Tok:
    raw: str                  # the text as written
    kind: str                 # word, string, group, comment
    line: int
    col: int
    file: str
    start: int                # offsets into the source text
    end: int
    value: str = ""           # word: raw; string: the text; group: the inner text; comment: after `#`

    def __repr__(self):
        return f"Tok({self.kind} {self.raw!r} @{self.line})"

    @property
    def word(self):
        """The text a word or a string stands for."""
        return self.value

    def keyword(self, *kws):
        return self.kind == "word" and self.raw in kws

    @property
    def items(self):
        """A group's items: the inner text split at the commas outside quotes and parentheses, stripped."""
        return split_items(self.value) if self.kind == "group" else []


@dataclass(eq=False)
class Line:
    number: int
    indent: int
    toks: list = field(default_factory=list)          # the code tokens, comments excluded
    comment: Tok | None = None                         # an end-of-line comment
    lead: list = field(default_factory=list)          # blank lines ("") and own-line comment tokens before it


@dataclass(eq=False)
class Statement:
    head: Line
    cont: list = field(default_factory=list)          # continuation lines
    body: list = field(default_factory=list)          # body statements of def, for, variant

    @property
    def keyword(self):
        return self.head.toks[0]

    @property
    def line(self):
        return self.head.number

    def lines(self):
        return [self.head, *self.cont]


def split_items(text):
    """Split at top-level commas: outside quotes and parentheses."""
    out, depth, quote, cur, i = [], 0, False, "", 0
    while i < len(text):
        ch = text[i]
        if quote:
            cur += ch
            if ch == "\\" and i + 1 < len(text):
                cur += text[i + 1]
                i += 1
            elif ch == '"':
                quote = False
        elif ch == '"':
            quote, cur = True, cur + ch
        elif ch == "(":
            depth, cur = depth + 1, cur + ch
        elif ch == ")":
            depth, cur = depth - 1, cur + ch
        elif ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
        i += 1
    if cur.strip() or out:
        out.append(cur.strip())
    return out


def _string(text, i, path, line, errors):
    """(end, value, lines spanned) of a string starting at text[i] == '"'; None when it is not closed."""
    j, out, nl = i + 1, [], 0
    while j < len(text):
        ch = text[j]
        if ch == "\\" and j + 1 < len(text) and text[j + 1] in '"\\':
            out.append(text[j + 1])
            j += 2
            continue
        if ch == '"':
            return j + 1, "".join(out), nl
        if ch == "\n":
            nl += 1
            while out and out[-1] == " ":
                out.pop()
            out.append(" ")
            j += 1
            while j < len(text) and text[j] == " ":
                j += 1
            continue
        out.append(ch)
        j += 1
    return None


def _paren(text, i):
    """The end of a parenthesis opened at text[i], on the same line, strings inside skipped; None when unclosed."""
    depth, j = 0, i
    while j < len(text) and text[j] != "\n":
        ch = text[j]
        if ch == '"':
            k = j + 1
            while k < len(text) and text[k] not in '"\n':
                k += 2 if text[k] == "\\" else 1
            if k >= len(text) or text[k] != '"':
                return None
            j = k + 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return None


def tokenize(text, path="<source>", errors=None):
    """[Line] of the code lines; lexical errors go to `errors` (a list of LangError), the scan goes on after them."""
    errors = [] if errors is None else errors
    text = text.replace("\r\n", "\n")
    lines, lead, cur = [], [], None
    i, line, col0 = 0, 1, 0

    def err(msg, at=None):
        errors.append(LangError(path, at or line, msg))

    while i < len(text):
        ch = text[i]
        if ch == "\n":
            if cur is None and not any(isinstance(x, Tok) and x.line == line for x in lead):
                lead.append("")
            cur, line, col0, i = None, line + 1, i + 1, i + 1
            continue
        if ch == " ":
            i += 1
            continue
        if ch == "\t":
            err("a tab – indent and separate with spaces")
            i += 1
            continue
        col = i - col0
        if ch == "#":
            j = text.find("\n", i)
            j = len(text) if j < 0 else j
            tok = Tok(text[i:j], "comment", line, col, path, i, j, text[i + 1:j])
            if cur is None:
                lead.append(tok)
            else:
                cur.comment = tok
            i = j
            continue
        if cur is None:
            cur = Line(line, col, lead=lead)
            lead = []
            lines.append(cur)
        if ch == '"':
            got = _string(text, i, path, line, errors)
            if got is None:
                err("a string without its closing quote")
                j = text.find("\n", i)
                i = len(text) if j < 0 else j
                continue
            j, value, nl = got
            cur.toks.append(Tok(text[i:j], "string", line, col, path, i, j, value))
            if nl:
                line += nl
                col0 = text.rfind("\n", 0, j) + 1
            i = j
            continue
        if ch == "(":
            j = _paren(text, i)
            if j is None:
                err("a parenthesis without its closing one on the line")
                j = text.find("\n", i)
                i = len(text) if j < 0 else j
                continue
            cur.toks.append(Tok(text[i:j], "group", line, col, path, i, j, text[i + 1:j - 1]))
            i = j
            continue
        j = i
        while j < len(text) and text[j] not in ' \t\n"#':
            if text[j] == "(":
                k = _paren(text, j)
                if k is None:
                    err("a parenthesis without its closing one on the line")
                    k = j + 1
                j = k
            else:
                j += 1
        cur.toks.append(Tok(text[i:j], "word", line, col, path, i, j, text[i:j]))
        i = j
    return lines, lead


def statements(lines, path="<source>", errors=None):
    """[Statement] of the code lines at the top level; indentation errors go to `errors`."""
    errors = [] if errors is None else errors
    out, i = _level(lines, 0, 0, path, errors)
    while i < len(lines):           # a line indented less than the first – cannot happen at level 0
        i += 1
    return out


def _level(lines, i, indent, path, errors):
    out = []
    while i < len(lines):
        ln = lines[i]
        if ln.indent < indent:
            break
        if ln.indent > indent:
            errors.append(LangError(path, ln.number, "a continuation line without a statement – indented deeper "
                                                     "than the statement it would belong to allows"))
            i += 1
            continue
        st = Statement(ln)
        i += 1
        if ln.toks and ln.toks[0].keyword(*BLOCKS):
            if i < len(lines) and lines[i].indent > indent:
                st.body, i = _level(lines, i, lines[i].indent, path, errors)
                while i < len(lines) and indent < lines[i].indent:
                    errors.append(LangError(path, lines[i].number, "indented less than the body above it and deeper "
                                                                   "than its statement"))
                    i += 1
        else:
            first = None
            while i < len(lines) and lines[i].indent > indent:
                if first is None:
                    first = lines[i].indent
                elif lines[i].indent < first:
                    errors.append(LangError(path, lines[i].number, "indented less than the continuation line "
                                                                   "before it"))
                st.cont.append(lines[i])
                i += 1
        out.append(st)
    return out, i
