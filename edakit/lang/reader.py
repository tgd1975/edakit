"""The reader of the circuit language: text → Source, every statement of language 5.1 to 5.11 as model objects.

    read(text, path, role="graph")   Source – the statements with file and line; errors collected in Source.errors
    check(source)                    raises CompileError with every error of the source at once
    KEYWORDS                         the keywords of language 5.12 – the grammar (T.9) and the server (T.25) read them

The reader does syntax only: no parts entries, no pin numbers, no expansion. A file's role says what may stand in
it: a graph file (main, included or variant) everything but requirements; a requirements file `need` and
`requirement`; a library file (edakit/blocks/*.circuit) definitions. The old statements of the prototype are refused
with the new form named.
"""

from __future__ import annotations

import json
import re

from . import model as m
from . import schema
from .tokens import LangError, Line, split_items, statements, tokenize
from .units import UnitError, parse

STATEMENTS = ("graph", "description", "purpose", "convention", "ground", "grounds", "accept", "lock", "set",
              "include", "param", "part", "net", "cable", "layout", "def", "use", "for", "derive", "variant", "need",
              "requirement")
INNER = ("nc", "pins", "alias", "notes", "label", "no-bom", "bom", "without", "ports", "port", "title", "about",
         "covers", "optional", "parts", "subject", "require", "verify", "rows", "signoff", "script", "from", "who",
         "source", "status", "reason", "must", "should", "may", "within", "in", "of", "satisfies", "decision",
         "(locked)")
KEYWORDS = frozenset(STATEMENTS + INNER)
OLD = {"waive": "accept KEY \"reason\"", "hint": "accept HINT.code \"reason\"",
       "reverse_protect": "source reversible on the part", "checks": "lock, or set locks.… JSON"}

TOP = ("graph", "description", "purpose", "convention", "ground", "grounds", "accept", "lock", "set", "include",
       "param", "part", "net", "cable", "layout", "def", "use", "for", "variant")
IN_DEF = ("title", "about", "port", "ports", "part", "net", "derive", "covers", "optional", "notes", "set", "accept")
IN_FOR = ("part", "net", "use", "lock", "cable", "layout")
IN_REQUIREMENTS = ("need", "requirement", "include")
IN_LIBRARY = ("def",)

BINDINGS = ("must", "should", "may")
VERIFY = ("rows", "signoff", "script", "accept")
PURPOSE = ("use", "market", "country", "notes")
BOOLEAN = {"yes": True, "true": True, "no": False, "false": False}
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
DEF_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*$")      # a definition's name: the block library's have hyphens
BRACE = re.compile(r"\{([^{}]*)\}")
BRACE_EXPR = re.compile(r"\s*([A-Za-z_]\w*)\s*(?:([-+*])\s*(\d+))?\s*$")
INT = re.compile(r"-?\d+$")


class CompileError(ValueError):
    """Errors of the language, each `PATH:LINE: TEXT`."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("\n".join(str(e) for e in self.errors))


def is_pin(tok):
    """A pin word: DES.WORD – a word with a dot after a designator (letters, digits, braces of a loop)."""
    return tok.kind == "word" and re.match(r"[A-Za-z_{][^.\s]*\.\S", tok.raw) is not None


def number(text):
    """An int or a float of a plain number; None when the text is none."""
    try:
        return int(text) if INT.match(text) else float(text)
    except ValueError:
        return None


class Reader:
    def __init__(self, text, path, role):
        self.text, self.path, self.role = text.replace("\r\n", "\n"), str(path), role
        self.errors = []
        self.in_variant = False
        self.loop_var = None

    # --- errors and tokens -------------------------------------------------------------------------------------------
    def err(self, at, msg):
        line = at if isinstance(at, int) else getattr(at, "line", None) or getattr(at, "number", 0)
        self.errors.append(LangError(self.path, line, msg))

    def node(self, cls, st, **kw):
        return cls(self.path, st.line, **kw)

    def braces(self, tok):
        """In a loop body every {…} that reads as an expression must name the loop's variable with + - * and a whole
        number; elsewhere braces are text."""
        if self.loop_var is None or tok.kind not in ("word", "string"):
            return
        for inner in BRACE.findall(tok.value):
            mm = BRACE_EXPR.match(inner)
            if not mm and re.match(r"\s*[A-Za-z_]", inner):
                self.err(tok, f"{{{inner}}}: in a loop only {{{self.loop_var}}}, {{{self.loop_var}+k}}, "
                              f"{{{self.loop_var}-k}} and {{{self.loop_var}*k}} with a whole number k")
            elif mm and mm.group(1) != self.loop_var:
                self.err(tok, f"{{{inner}}}: the loop's variable is {self.loop_var}")

    def value(self, toks, i, what):
        """The word or string at toks[i]; an error and None when it is missing."""
        if i >= len(toks):
            self.err(toks[-1] if toks else 0, f"{what}: a value is missing")
            return None
        t = toks[i]
        if t.kind == "group":
            self.err(t, f"{what}: a word or a string, not {t.raw}")
            return None
        self.braces(t)
        return t.value

    def json_from(self, lines, li, ti, what):
        """(value, last line index) of the JSON that starts at token ti of lines[li] and runs to the end of that line
        or over the following lines of the statement."""
        start = lines[li].toks[ti].start
        for last in range(li, len(lines)):
            ln = lines[last]
            end = ln.toks[-1].end if ln.toks else start
            try:
                return json.loads(self.text[start:end]), last
            except json.JSONDecodeError:
                continue
        try:
            json.loads(self.text[start:lines[li].toks[-1].end])
        except json.JSONDecodeError as e:
            self.err(lines[li].toks[ti], f"{what}: no valid JSON – {e.msg}")
        return None, li

    def quantity(self, toks, i, unit=None, what="a quantity"):
        """(Quantity or None, next index): the longest run of words from toks[i] that reads as a quantity."""
        for k in range(min(5, len(toks) - i), 0, -1):
            run = toks[i:i + k]
            if any(t.kind != "word" for t in run):
                continue
            text = " ".join(t.raw for t in run)
            try:
                q = parse(text, unit)
            except UnitError as e:
                self.err(run[0], f"{what}: {e}")
                return None, i + k
            if q is not None:
                return q, i + k
        return None, i

    # --- attributes --------------------------------------------------------------------------------------------------
    def attr(self, table, toks, i, out, lines=None, li=None):
        """Read one KEY VALUE pair of `table` at toks[i] into out [(key, value)]; returns the next index (or the end of
        the line for `set`, satisfies, decision), and the line index reached by a `set` over several lines."""
        t = toks[i]
        key = t.raw
        if t.kind != "word":
            self.err(t, f"{t.raw}: a key expected here")
            return i + 1, li
        if key == "no-bom" and table is schema.COMPONENT:
            out.append(("bom", False))
            return i + 1, li
        if key == "set":
            if i + 1 >= len(toks):
                self.err(t, "set KEY JSON: the key is missing")
                return len(toks), li
            name = toks[i + 1].raw
            head = name.split(".")[0]
            if head not in table:
                near = schema.nearest(table, head)
                self.err(toks[i + 1], f"set {name}: unknown key" + (f" – {near}?" if near else ""))
            if i + 2 >= len(toks):
                self.err(t, f"set {name}: the JSON value is missing")
                return len(toks), li
            if lines is None:
                val, _ = self.json_from([Line(t.line, 0, toks=toks)], 0, i + 2, f"set {name}")
                last = li
            else:
                val, last = self.json_from(lines, li, i + 2, f"set {name}")
            out.append(("set:" + name, val))
            return len(toks), last
        if key in OLD:
            self.err(t, f"{key}: the form of before – now {OLD[key]}")
            return len(toks), li
        if key not in table or table[key] in ("list", "table") and key not in ("satisfies", "decision"):
            if key in table:
                self.err(t, f"{key}: a {table[key]} – written `set {key} JSON`")
            else:
                near = schema.nearest(table, key)
                self.err(t, f"unknown key {key!r}" + (f" – {near}?" if near else ""))
            return i + 1, li
        kind = table[key]
        if key in ("satisfies", "decision"):
            ids = [x.value for x in toks[i + 1:] if x.kind in ("word", "string")]
            if not ids:
                self.err(t, f"{key}: at least one ID")
            out.append((key, ids))
            return len(toks), li
        if kind == "boolean":
            if i + 1 < len(toks) and toks[i + 1].kind == "word" and toks[i + 1].raw in BOOLEAN:
                out.append((key, BOOLEAN[toks[i + 1].raw]))
                return i + 2, li
            out.append((key, True))
            return i + 1, li
        if kind in ("range", "number_or_range"):
            if i + 1 < len(toks) and toks[i + 1].kind == "word" and (
                    toks[i + 1].raw.startswith("@") or IDENT.match(toks[i + 1].raw)
                    and toks[i + 1].raw not in table and toks[i + 1].raw not in KEYWORDS):
                out.append((key, toks[i + 1].raw))
                return i + 2, li
            q, j = self.quantity(toks, i + 1, schema.UNIT.get(key), key)
            if q is None:
                if j == i + 1:
                    self.err(t, f"{key}: a range expected – `0..5.5 V`, `0 V`, a parameter or @PORT")
                return max(j, i + 2), li
            out.append((key, q))
            return j, li
        if kind == "number":
            if i + 1 < len(toks) and toks[i + 1].kind == "word":
                n = number(toks[i + 1].raw)
                if n is None:
                    q = parse(toks[i + 1].raw) if toks[i + 1].raw[:1].isdigit() else None
                    n = q.lo if q is not None and q.point else None
                if n is not None:
                    out.append((key, n))
                    return i + 2, li
                if IDENT.match(toks[i + 1].raw):              # a parameter's name, substituted later
                    out.append((key, toks[i + 1].raw))
                    return i + 2, li
            self.err(t, f"{key}: a number expected")
            return i + 2, li
        v = self.value(toks, i + 1, key)
        if v is not None:
            out.append((key, v))
        return i + 2, li

    # --- the file ----------------------------------------------------------------------------------------------------
    def read(self):
        errors = self.errors
        lines, tail = tokenize(self.text, self.path, errors)
        syntax = statements(lines, self.path, errors)
        src = m.Source(self.path, self.role, syntax=syntax, tail=tail, text=self.text)
        allowed = {"graph": TOP, "requirements": IN_REQUIREMENTS, "block": IN_LIBRARY}[self.role]
        for k, st in enumerate(syntax):
            kw = st.keyword
            if self.role == "graph" and kw.keyword("variant"):
                if k != 0:
                    self.err(kw, "variant: the first statement of a variant file, never after another")
                    continue
                var = self.statement(st, TOP)
                src.statements.append(var)
                continue
            if src.variant is not None:
                node = self.statement(st, TOP, variant=True)
                if node is not None:
                    src.variant.body.append(node)
                continue
            if self.role == "graph" and kw.keyword("graph") and k != 0:
                self.err(kw, "graph: the first statement of a main file")
            node = self.statement(st, allowed)
            if node is not None:
                src.statements.append(node)
        src.errors = errors
        return src

    def statement(self, st, allowed, variant=False):
        kw = st.keyword
        name = kw.raw
        if kw.kind != "word" or name not in STATEMENTS:
            if kw.kind == "word" and name in OLD:
                self.err(kw, f"{name}: the form of before – now {OLD[name]}")
            else:
                self.err(kw, f"{kw.raw}: no statement – one of {', '.join(allowed)}")
            return None
        if name not in allowed:
            if name in ("need", "requirement"):
                self.err(kw, f"{name}: requirements stand in the file [project] requirements names, not in the "
                             "graph's source")
            elif self.role == "requirements":
                self.err(kw, f"{name}: a requirements file holds need and requirement statements")
            else:
                self.err(kw, f"{name}: not allowed here – here: {', '.join(allowed)}")
            return None
        was = self.in_variant
        self.in_variant = self.in_variant or variant
        try:
            return getattr(self, "st_" + name)(st)
        finally:
            self.in_variant = was

    # --- the graph as a whole ----------------------------------------------------------------------------------------
    def st_graph(self, st):
        if self.in_variant:
            self.err(st.keyword, "graph: not in a variant – the name, version and date are the base's (set name …)")
            return None
        toks = [t for ln in st.lines() for t in ln.toks]
        node = self.node(m.GraphHead, st)
        if len(toks) < 2:
            self.err(st.keyword, "graph NAME [version V] [date D]")
            return node
        node.name = None if toks[1].keyword("-") else toks[1].value
        i = 2
        while i < len(toks):
            if toks[i].keyword("version", "date"):
                setattr(node, toks[i].raw, self.value(toks, i + 1, toks[i].raw))
                i += 2
            else:
                self.err(toks[i], "graph NAME [version V] [date D]")
                i += 1
        return node

    def st_description(self, st):
        toks = [t for ln in st.lines() for t in ln.toks]
        node = self.node(m.Description, st, text=self.value(toks, 1, "description") or "")
        if len(toks) > 2:
            self.err(toks[2], "description \"…\": one text")
        return node

    def st_purpose(self, st):
        toks = [t for ln in st.lines() for t in ln.toks]
        node = self.node(m.Purpose, st)
        if len(toks) > 1 and not toks[1].keyword(*PURPOSE[1:]):
            node.fields["use"] = toks[1].value
            i = 2
        else:
            i = 1
        while i < len(toks):
            if toks[i].keyword(*PURPOSE[1:]):
                node.fields[toks[i].raw] = self.value(toks, i + 1, toks[i].raw)
                i += 2
            else:
                self.err(toks[i], "purpose USE [market M] [country C] [notes \"…\"]")
                i += 1
        return node

    def st_convention(self, st):
        toks = [t for ln in st.lines() for t in ln.toks]
        return self.node(m.Convention, st, key=self.value(toks, 1, "convention") or "",
                         text=self.value(toks, 2, "convention KEY") or "")

    def st_ground(self, st):
        toks = [t for ln in st.lines() for t in ln.toks]
        return self.node(m.Ground, st, name=self.value(toks, 1, "ground") or "")

    def st_grounds(self, st):
        toks = [t for ln in st.lines() for t in ln.toks]
        if len(toks) < 2:
            self.err(st.keyword, "grounds NAME …")
        return self.node(m.Grounds, st, names=[t.value for t in toks[1:]])

    def accept(self, toks, i, st_line):
        """An Accept from `accept KEY "reason"` at toks[i] (the keyword); returns (Accept, next index)."""
        key = self.value(toks, i + 1, "accept")
        node = m.Accept(self.path, toks[i].line, key=key or "")
        if i + 2 < len(toks) and toks[i + 2].keyword("-"):
            if not self.in_variant:
                self.err(toks[i + 2], "accept KEY -: removes an accept of the base, only in a variant")
            return node, i + 3
        if i + 2 >= len(toks) or toks[i + 2].kind != "string":
            self.err(toks[i], f"accept {key or ''}: the reason, a quoted text")
            return node, i + 2
        node.reason = toks[i + 2].value
        return node, i + 3

    def st_accept(self, st):
        toks = [t for ln in st.lines() for t in ln.toks]
        node, j = self.accept(toks, 0, st.line)
        if j < len(toks):
            self.err(toks[j], "accept KEY \"reason\": one per statement")
        return node

    def st_lock(self, st):
        toks = [t for ln in st.lines() for t in ln.toks]
        if len(toks) != 3 or not is_pin(toks[1]):
            self.err(st.keyword, "lock PINWORD NET")
        for t in toks[1:3]:
            self.braces(t)
        return self.node(m.Lock, st, pin=toks[1].raw if len(toks) > 1 else "",
                         net=toks[2].value if len(toks) > 2 else "")

    def st_set(self, st):
        lines = st.lines()
        toks = lines[0].toks
        node = self.node(m.Set, st)
        if len(toks) < 3:
            self.err(st.keyword, "set KEY JSON")
            return node
        node.key = toks[1].raw
        head = node.key.split(".")[0]
        if head not in schema.GRAPH:
            near = schema.nearest(schema.GRAPH, head)
            self.err(toks[1], f"set {node.key}: no key of the graph" + (f" – {near}?" if near else ""))
        node.value, _ = self.json_from(lines, 0, 2, f"set {node.key}")
        return node

    def st_include(self, st):
        toks = [t for ln in st.lines() for t in ln.toks]
        if len(toks) != 2:
            self.err(st.keyword, "include PATH")
        return self.node(m.Include, st, path=self.value(toks, 1, "include") or "")

    def st_param(self, st):
        toks = [t for ln in st.lines() for t in ln.toks]
        node = self.node(m.Param, st)
        if len(toks) < 4 or not toks[2].keyword("=") or not IDENT.match(toks[1].raw):
            self.err(st.keyword, "param NAME = QUANTITY")
            return node
        node.name = toks[1].raw
        node.text = " ".join(t.raw for t in toks[3:])
        node.value = self.param_value(toks[3:], toks[3], f"param {node.name}")
        return node

    def param_value(self, toks, at, what):
        if len(toks) == 1 and toks[0].kind == "string":
            return toks[0].value
        q, j = self.quantity(toks, 0, None, what)
        if q is not None and j == len(toks):
            return q
        if len(toks) == 1 and toks[0].kind == "word":
            return toks[0].raw
        if q is None:
            self.err(at, f"{what}: a quantity – `10 mA`, `0..5.5 V` – or one word")
        else:
            self.err(toks[j], f"{what}: {toks[j].raw} after the quantity")
        return q

    # --- parts -------------------------------------------------------------------------------------------------------
    def st_part(self, st):
        lines = st.lines()
        toks = lines[0].toks
        node = self.node(m.Part, st)
        node.syntax = st
        if len(toks) < 2:
            self.err(st.keyword, "part DES TYPE PARTNO [attributes…] [\"label\"]")
            return node
        self.braces(toks[1])
        node.des = toks[1].raw
        i = 2

        def bare(t):
            return t.kind == "string" or t.kind == "word" and t.raw not in schema.COMPONENT and t.raw not in KEYWORDS \
                and t.raw not in ("set", "no-bom") and t.raw not in OLD

        if i < len(toks) and toks[i].kind == "word" and bare(toks[i]):
            node.type = None if toks[i].keyword("-") else toks[i].raw
            i += 1
            if i < len(toks) and bare(toks[i]):
                node.part = None if toks[i].keyword("-") else toks[i].value
                self.braces(toks[i])
                i += 1
        elif not self.in_variant:
            self.err(st.keyword, f"part {node.des}: TYPE after the designator – part DES TYPE PARTNO …")
        node.items.append(("head", toks[:i]))
        self.part_attrs(node, lines, 0, i)
        return node

    def part_attrs(self, node, lines, li, i):
        """The attributes of a part from token i of lines[li] on: KEY VALUE pairs, the label, and the line keywords
        nc, pins, alias, accept – each recorded in node.items with its tokens, for the formatter."""
        while li < len(lines):
            toks = lines[li].toks
            while i < len(toks):
                t, start = toks[i], i
                kind = "attr"
                if t.keyword("nc"):
                    kind = "nc"
                    for p in toks[i + 1:]:
                        self.braces(p)
                        node.nc.append(m.PinWord(self.path, p.line, word=p.value))
                    i = len(toks)
                elif t.keyword("pins"):
                    kind = "pins"
                    for p in toks[i + 1:]:
                        k, eq, v = p.raw.partition("=")
                        if not eq or not k:
                            self.err(p, "pins NUMBER=NAME …")
                        else:
                            node.pins.append((k, v))
                    i = len(toks)
                elif t.keyword("alias"):
                    kind = "alias"
                    j = i + 1
                    while j < len(toks):
                        if j + 2 < len(toks) and toks[j + 1].keyword("="):
                            node.aliases.append((toks[j].raw, toks[j + 2].raw))
                            j += 3
                        elif "=" in toks[j].raw and not toks[j].raw.startswith("="):
                            a, _, b = toks[j].raw.partition("=")
                            node.aliases.append((a, b))
                            j += 1
                        else:
                            self.err(toks[j], "alias NAME = PINWORD …")
                            j += 1
                    i = len(toks)
                elif t.keyword("accept"):
                    kind = "accept"
                    acc, i = self.accept(toks, i, t.line)
                    node.accepts.append(acc)
                elif t.kind == "string":
                    kind = "label"
                    if node.label is not None:
                        self.err(t, f"part {node.des}: a second label – a key before the text? (notes \"…\")")
                    self.braces(t)
                    node.label = t.value
                    i += 1
                elif t.keyword("label"):
                    kind = "label"
                    if node.label is not None:
                        self.err(t, f"part {node.des}: a second label")
                    node.label = self.value(toks, i + 1, "label")
                    i += 2
                else:
                    i, li2 = self.attr(schema.COMPONENT, toks, i, node.attrs, lines, li)
                    kind = "set" if t.keyword("set") else self.attr_kind(schema.COMPONENT, t.raw)
                    if li2 is not None and li2 != li:
                        node.items.append((kind, toks[start:]))
                        li, i = li2, len(lines[li2].toks)
                        toks = lines[li].toks
                        continue
                node.items.append((kind, toks[start:max(i, start + 1)]))
            li, i = li + 1, 0

    @staticmethod
    def attr_kind(table, key):
        """The formatter's class of an attribute: string attributes and lists go on lines of their own, the others
        on the head."""
        kind = table.get(key)
        if key == "notes":
            return "notes"
        if kind == "string":
            return "string"
        if kind == "list":
            return "list"
        return "attr"

    # --- nets --------------------------------------------------------------------------------------------------------
    def st_net(self, st):
        lines = st.lines()
        toks = lines[0].toks
        node = self.node(m.Net, st)
        node.syntax = st
        if len(toks) < 2:
            self.err(st.keyword, "net NAME [RANGE] PINWORD …")
            return node
        self.braces(toks[1])
        node.name = toks[1].value
        i = 2
        if i < len(toks) and toks[i].kind == "word" and not is_pin(toks[i]):
            raw = toks[i].raw
            if raw.startswith("@"):
                node.v, i = raw, i + 1
            elif IDENT.match(raw) and raw not in schema.NET and raw not in KEYWORDS and raw != "set" \
                    and raw not in OLD:
                node.v, i = raw, i + 1
            else:
                q, j = self.quantity(toks, i, "V", f"net {node.name}")
                if q is not None:
                    node.v, i = q, j
                elif j != i:
                    i = j
        node.items.append(("head", toks[:i]))
        self.net_tokens(node, lines, 0, i)
        return node

    def net_tokens(self, node, lines, li, i):
        last_pin = None
        while li < len(lines):
            toks = lines[li].toks
            while i < len(toks):
                t, start, kind = toks[i], i, "attr"
                if is_pin(t):
                    kind = "pin"
                    self.braces(t)
                    last_pin = m.PinWord(self.path, t.line, word=t.raw)
                    node.pins.append(last_pin)
                    i += 1
                    if i < len(toks) and toks[i].kind == "group" and toks[i].raw == "(locked)":
                        last_pin.locked = True
                        i += 1
                elif t.kind == "group" and t.raw == "(locked)":
                    self.err(t, "(locked) after the pin word it marks")
                    i += 1
                elif t.keyword("accept"):
                    kind = "accept"
                    acc, i = self.accept(toks, i, t.line)
                    node.accepts.append(acc)
                elif t.keyword("without"):
                    kind = "without"
                    if not self.in_variant:
                        self.err(t, f"net {node.name}: without – takes pins off a net of the base, only in a variant")
                    for p in toks[i + 1:]:
                        if not is_pin(p):
                            self.err(p, "without PINWORD …")
                        node.without.append(m.PinWord(self.path, p.line, word=p.raw))
                    i = len(toks)
                elif t.keyword("pins"):
                    self.err(t, f"net {node.name}: pins are written as pin words, DES.PIN")
                    i += 1
                elif t.kind == "word":
                    i, li2 = self.attr(schema.NET, toks, i, node.attrs, lines, li)
                    kind = "set" if t.keyword("set") else self.attr_kind(schema.NET, t.raw)
                    if li2 is not None and li2 != li:
                        node.items.append((kind, toks[start:]))
                        li, i = li2, len(lines[li2].toks)
                        toks = lines[li].toks
                        continue
                else:
                    self.err(t, f"net {node.name}: {t.raw} – a pin word, (locked) or an attribute")
                    i += 1
                node.items.append((kind, toks[start:max(i, start + 1)]))
            li, i = li + 1, 0

    # --- cables and the layout ---------------------------------------------------------------------------------------
    def st_cable(self, st):
        lines = st.lines()
        toks = lines[0].toks
        node = self.node(m.Cable, st)
        if len(toks) < 4:
            self.err(st.keyword, "cable NAME FROM TO FROMPIN=TOPIN … [attributes]")
            return node
        node.name, node.frm, node.to = toks[1].value, toks[2].value, toks[3].value
        table = {k: v for k, v in schema.CABLE.items() if k not in ("name", "from", "to", "pins")}
        li, i = 0, 4
        while li < len(lines):
            toks = lines[li].toks
            while i < len(toks):
                t = toks[i]
                if t.kind == "word" and "=" in t.raw and not t.raw.startswith("=") and t.raw not in table:
                    a, _, b = t.raw.partition("=")
                    node.pairs.append((a, b))
                    i += 1
                else:
                    i, li2 = self.attr(table, toks, i, node.attrs, lines, li)
                    if li2 is not None and li2 != li:
                        li, i = li2, len(lines[li2].toks)
                        toks = lines[li].toks
            li, i = li + 1, 0
        return node

    def st_layout(self, st):
        toks = [t for ln in st.lines() for t in ln.toks]
        node = self.node(m.Layout, st)
        what = toks[1].raw if len(toks) > 1 else ""
        node.kind = what
        rest = toks[2:]
        for t in rest:
            self.braces(t)
        if what in ("fixed", "edge"):
            node.parts = [t.value for t in rest]
            if not rest:
                self.err(st.keyword, f"layout {what} DES …")
        elif what == "near":
            node.parts = [t.value for t in rest]
            if len(rest) < 2:
                self.err(st.keyword, "layout near DES HOST …")
        elif what == "note":
            if len(rest) != 1 or rest[0].kind != "string":
                self.err(st.keyword, "layout note \"…\"")
            node.text = rest[0].value if rest else ""
        elif what in ("loop", "apart"):
            limit = "max_mm" if what == "loop" else "min_mm"
            if len(rest) < 2:
                self.err(st.keyword, f"layout {what} A B [{limit} N] [\"what\"]")
                return node
            node.a, node.b = rest[0].value, rest[1].value
            j = 2
            if j < len(rest) and rest[j].keyword(limit):
                n = number(rest[j + 1].raw) if j + 1 < len(rest) else None
                if n is None:
                    self.err(rest[j], f"{limit}: a number")
                node.limit, j = n, j + 2
            if j < len(rest) and rest[j].kind == "string":
                node.text, j = rest[j].value, j + 1
            if j < len(rest):
                self.err(rest[j], f"layout {what} A B [{limit} N] [\"what\"]")
        else:
            self.err(st.keyword, "layout fixed|edge|near|loop|apart|note …")
        return node

    # --- definitions and usages --------------------------------------------------------------------------------------
    def args(self, tok, what, defaults=False):
        """[Arg] of a group or a rule's parentheses: `name = value` or a value by position."""
        out = []
        inner = tok.value if tok.kind == "group" else tok.raw[tok.raw.index("(") + 1:-1]
        for item in split_items(inner):
            if not item:
                if inner.strip():
                    self.err(tok, f"{what}: an empty item between commas")
                continue
            name, eq, val = item.partition("=")
            if eq and IDENT.match(name.strip()):
                name, val = name.strip(), val.strip()
            else:
                name, val = None, item.strip()
                if defaults:
                    self.err(tok, f"{what}: NAME = DEFAULT – {item!r}")
                    continue
            arg = m.Arg(self.path, tok.line, name=name, text=val)
            arg.value = self.arg_value(val, tok, f"{what} {name or val}")
            out.append(arg)
        return out

    def arg_value(self, text, tok, what):
        if text.startswith('"') and text.endswith('"') and len(text) >= 2:
            return text[1:-1]
        try:
            q = parse(text)
        except UnitError as e:
            self.err(tok, f"{what}: {e}")
            return None
        if q is not None:
            return q
        if re.match(r"[^\s\"#]+$", text):
            return text
        self.err(tok, f"{what}: {text!r} – a quantity or one word")
        return None

    def st_def(self, st):
        toks = st.head.toks
        node = self.node(m.Def, st)
        if len(toks) < 2 or not DEF_NAME.match(toks[1].raw):
            self.err(st.keyword, "def NAME [(PARAM = DEFAULT, …)] [ports PORT …]")
            return node
        node.name = toks[1].raw
        i = 2
        if i < len(toks) and toks[i].kind == "group":
            node.params = self.args(toks[i], f"def {node.name}", defaults=True)
            i += 1
        if i < len(toks) and toks[i].keyword("ports"):
            node.ports += [(t.raw, None) for t in toks[i + 1:]]
            i = len(toks)
        if i < len(toks):
            self.err(toks[i], "def NAME [(PARAM = DEFAULT, …)] [ports PORT …]")
        for b in st.body:
            self.def_line(node, b)
        return node

    def def_line(self, node, st):
        kw = st.keyword
        toks = [t for ln in st.lines() for t in ln.toks]
        name = kw.raw if kw.kind == "word" else ""
        if name not in IN_DEF:
            if name in STATEMENTS:
                self.err(kw, f"{name}: not inside a definition – there: {', '.join(IN_DEF)}")
            else:
                self.err(kw, f"{kw.raw}: no statement of a definition – {', '.join(IN_DEF)}")
            return
        if name in ("title", "about"):
            setattr(node, name, self.value(toks, 1, name))
        elif name == "port":
            about = toks[2].value if len(toks) > 2 and toks[2].kind == "string" else None
            if len(toks) < 2:
                self.err(kw, "port PORT [\"about\"]")
                return
            node.ports = [(p, a) for p, a in node.ports if p != toks[1].raw] + [(toks[1].raw, about)]
        elif name == "ports":
            node.ports += [(t.raw, None) for t in toks[1:] if t.raw not in dict(node.ports)]
        elif name == "covers":
            node.covers += [t.raw for t in toks[1:]]
        elif name == "optional":
            if len(toks) < 3 or not toks[1].keyword("parts", "ports"):
                self.err(kw, "optional parts DES … | optional ports PORT …")
                return
            target = node.optional_parts if toks[1].raw == "parts" else node.optional_ports
            target += [t.raw for t in toks[2:]]
        elif name == "notes":
            node.notes.append(self.value(toks, 1, "notes") or "")
        elif name == "set":
            s = self.node(m.Set, st)
            if len(toks) < 3:
                self.err(kw, "set KEY JSON")
                return
            s.key = toks[1].raw
            if s.key not in ("test", "graph"):
                self.err(toks[1], f"set {s.key}: in a definition `set test …` or `set graph …`")
            s.value, _ = self.json_from(st.lines(), 0, 2, f"set {s.key}")
            node.sets.append(s)
        elif name == "part":
            node.body.append(self.st_part(st))
        elif name == "net":
            node.body.append(self.st_net(st))
        elif name == "derive":
            node.body.append(self.st_derive(st))
        elif name == "accept":
            self.err(kw, "accept in a definition: on its part or net, as accept KEY \"reason\" there")

    def st_derive(self, st):
        toks = [t for ln in st.lines() for t in ln.toks]
        node = self.node(m.Derive, st)
        call = next((k for k, t in enumerate(toks) if k > 0 and t.kind == "word" and "(" in t.raw), None)
        if call is None or call == 1 or call != len(toks) - 1 or not toks[call].raw.endswith(")"):
            self.err(st.keyword, "derive TARGET … RULE(ARG, …)")
            return node
        node.targets = [t.raw for t in toks[1:call]]
        for t in toks[1:call]:
            if not re.match(r"[A-Za-z_]\w*\.value$", t.raw):
                self.err(t, f"derive: {t.raw} – a target is PART.value")
        node.rule = toks[call].raw[:toks[call].raw.index("(")]
        node.args = self.args(toks[call], f"derive {node.rule}")
        return node

    def st_use(self, st):
        lines = st.lines()
        toks = [t for ln in lines for t in ln.toks]
        node = self.node(m.Use, st)
        if len(toks) < 3:
            self.err(st.keyword, "use DEF INSTANCE [(PARAM = VALUE, …)] [bindings …]")
            return node
        node.definition, node.instance = toks[1].raw, toks[2].raw
        self.braces(toks[2])
        i = 3
        if i < len(toks) and toks[i].kind == "group":
            node.params = self.args(toks[i], f"use {node.instance}")
            i += 1
        cur = None
        while i < len(toks):
            t = toks[i]
            if t.keyword("without"):
                cur, i = None, i + 1
                while i < len(toks) and not self.binding_start(toks, i) and not toks[i].keyword(
                        "satisfies", "decision"):
                    node.without.append(toks[i].raw)
                    i += 1
                continue
            if t.keyword("satisfies", "decision"):
                ids, i = [], i + 1
                while i < len(toks) and not self.binding_start(toks, i) and not toks[i].keyword(
                        "without", "satisfies", "decision"):
                    ids.append(toks[i].value)
                    i += 1
                getattr(node, t.raw).extend(ids)
                cur = None
                continue
            if self.binding_start(toks, i):
                if t.kind == "word" and "=" in t.raw and t.raw != "=":
                    left, _, right = t.raw.partition("=")
                    i += 1
                else:
                    left, right = t.raw, toks[i + 2].value if i + 2 < len(toks) else ""
                    if i + 2 >= len(toks):
                        self.err(t, f"{left} =: the right side is missing")
                    i += 3
                self.braces(t)
                cur = m.Binding(self.path, t.line, left=left, right=right)
                node.bindings.append(cur)
                continue
            if cur is None:
                self.err(t, f"use {node.instance}: {t.raw} – a binding LEFT = RIGHT")
                i += 1
                continue
            # the words after a part binding's designator: PARTNO, attributes, the label
            if cur.part is None:
                cur.part = m.Part(self.path, t.line, des=cur.right, head=False)
                if t.kind == "string" or t.kind == "word" and t.raw not in schema.COMPONENT and t.raw not in (
                        "no-bom", "set", "label") and t.raw not in KEYWORDS:
                    cur.part.part = None if t.keyword("-") else t.value
                    i += 1
                    continue
            j = i
            while j < len(toks) and not self.binding_start(toks, j) and not toks[j].keyword(
                    "without", "satisfies", "decision"):
                j += 1
            seg = toks[i:j]
            self.part_attrs(cur.part, [Line(t.line, 0, toks=seg)], 0, 0)
            i = j
        return node

    @staticmethod
    def binding_start(toks, i):
        t = toks[i]
        if t.kind != "word":
            return False
        if i + 1 < len(toks) and toks[i + 1].keyword("="):
            return True
        left, eq, right = t.raw.partition("=")
        return bool(eq and left and right and IDENT.match(left) and left not in schema.COMPONENT)

    def st_for(self, st):
        toks = st.head.toks
        node = self.node(m.For, st)
        if self.loop_var is not None:
            self.err(st.keyword, "for inside a for: one level only")
            return node
        ok = len(toks) == 4 and IDENT.match(toks[1].raw) and toks[2].keyword("in")
        a, _, b = toks[3].raw.partition("..") if len(toks) > 3 else ("", "", "")
        if not ok or not INT.match(a) or not INT.match(b):
            self.err(st.keyword, "for VAR in A..B – A and B whole numbers")
            return node
        node.var, node.start, node.stop = toks[1].raw, int(a), int(b)
        if node.stop < node.start:
            self.err(toks[3], f"for {node.var} in {a}..{b}: B < A")
        self.loop_var = node.var
        try:
            for b_st in st.body:
                n = self.statement(b_st, IN_FOR)
                if n is not None:
                    node.body.append(n)
        finally:
            self.loop_var = None
        if not st.body:
            self.err(st.keyword, f"for {node.var}: no body – the statements indented below it")
        return node

    def st_variant(self, st):
        toks = st.head.toks
        node = self.node(m.Variant, st)
        if len(toks) != 4 or not toks[2].keyword("of"):
            self.err(st.keyword, "variant NAME of PATH")
        else:
            node.name, node.base = toks[1].raw, toks[3].value
        self.in_variant = True
        for b in st.body:
            if b.keyword.keyword("variant"):
                self.err(b.keyword, "variant inside a variant – a variant of a variant names it as its base")
                continue
            n = self.statement(b, TOP, variant=True)
            if n is not None:
                node.body.append(n)
        return node

    # --- requirements ------------------------------------------------------------------------------------------------
    def st_need(self, st):
        toks = [t for ln in st.lines() for t in ln.toks]
        node = self.node(m.Need, st)
        if len(toks) < 3 or toks[2].kind != "string":
            self.err(st.keyword, "need ID \"text\" who WHO [source \"…\"] [status …] [reason \"…\"]")
            return node
        node.id, node.text = toks[1].raw, toks[2].value
        self.fields(node, toks, 3, ("who", "source", "status", "reason"))
        return node

    def fields(self, node, toks, i, keys):
        while i < len(toks):
            if toks[i].keyword(*keys):
                setattr(node, toks[i].raw, self.value(toks, i + 1, toks[i].raw) or "")
                i += 2
            else:
                self.err(toks[i], f"{toks[i].raw}: one of {', '.join(keys)}")
                i += 1

    def st_requirement(self, st):
        lines = st.lines()
        head = lines[0].toks
        node = self.node(m.Requirement, st)
        b = next((k for k, t in enumerate(head) if t.keyword(*BINDINGS)), None)
        if len(head) < 4 or b is None or b + 1 >= len(head) or head[b + 1].kind != "string":
            self.err(st.keyword, "requirement ID [from ID …] must|should|may \"text\"")
            return node
        node.id = head[1].raw
        if b > 2:
            if not head[2].keyword("from"):
                self.err(head[2], "requirement ID from ID … must|should|may \"text\"")
            node.frm = [t.raw for t in head[3:b]]
        node.binding, node.text = head[b].raw, head[b + 1].value
        rest = [t for t in head[b + 2:]] + [t for ln in lines[1:] for t in ln.toks]
        i = 0
        while i < len(rest):
            t = rest[i]
            if t.keyword("subject"):
                node.subject, i = self.value(rest, i + 1, "subject") or "", i + 2
            elif t.keyword("require"):
                j = i + 1
                while j < len(rest) and not rest[j].keyword("subject", "require", "verify", "source", "status",
                                                             "reason") and rest[j].line == t.line:
                    j += 1
                node.require = " ".join(x.raw for x in rest[i + 1:j])
                if not node.require:
                    self.err(t, "require: the condition – D.i within 2 mA .. 15 mA")
                i = j
            elif t.keyword("verify"):
                if i + 2 >= len(rest) or not rest[i + 1].keyword(*VERIFY):
                    self.err(t, f"verify {' | '.join(VERIFY)} …")
                    i += 2
                    continue
                node.verify.append((rest[i + 1].raw, self.value(rest, i + 2, "verify") or ""))
                i += 3
            elif t.keyword("source", "status", "reason"):
                setattr(node, t.raw, self.value(rest, i + 1, t.raw) or "")
                i += 2
            else:
                self.err(t, f"{t.raw}: subject, require, verify, source, status or reason")
                i += 1
        return node


def read(text, path="<source>", role="graph"):
    """The Source of a text: its statements as model objects, its errors in Source.errors."""
    return Reader(text, path, role).read()


def check(source):
    """Raise CompileError with every error of the source."""
    if source.errors:
        raise CompileError(source.errors)
    return source
