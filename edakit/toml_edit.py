"""A line editor for TOML files that keeps comments and arrangement: it reads the text into its statements – tables,
keys with their values, arrays with their items –, inserts lines and items where they belong, and leaves every other
line as it was. `edakit block add` writes a TOML graph with it (circuit-language plan, L.7); `write_place_rows` in
pcb.py is the same idea for the [place] table of a board file.

    doc = Doc(text)
    doc.add_table(("components", "R7"), ['type = "resistor"', ...], after="components", before="nets")
    doc.append(("nets", "GND"), "pins", ["R7.2"])          # False when the table has no such key
    doc.add_keys(("nets", "SDA"), ['bus = "i2c"'])
    doc.text

A table goes after the last table whose key starts with `after` – its sub-tables included –, behind the last line of
a statement there, so that a comment above the next table stays with that table. A key goes behind the last statement
of its own table, before its sub-tables; a top-level key behind the last top-level one. An item goes into its array as
the array is written: inline at the end of the line; over several lines on a line of its own with the indent of the
last item, one item to a line where the array has one to a line, with a trailing comma where the last item has one.

literal() writes a JSON value as TOML: strings as JSON escapes them (TOML's basic strings read those), a long one as a
multi-line string with line-ending backslashes, a long array over several lines, a dict as an inline table, null
refused – the writer of the circuit-language sketch (docs/concepts/done/prototypes/circuit-language/translate.py).
"""

from __future__ import annotations

import bisect
import json
import re
import tomllib
from dataclasses import dataclass

WIDTH = 118                     # the lines a writer wraps: the sketch's width
BARE = re.compile(r"[A-Za-z0-9_-]+")
TOKEN = re.compile(r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?([Zz]|[+-]\d{2}:\d{2})?|[^\s,\]}#]+")


class TomlEditError(ValueError):
    pass


# --- values ----------------------------------------------------------------------------------------------------------
def key(k):
    """A key as TOML writes it: bare where it can be, else quoted."""
    return k if BARE.fullmatch(k) else quoted(k)


def quoted(s):
    """A basic string: JSON's escapes, which TOML reads, and DEL escaped, which JSON leaves as it is."""
    return json.dumps(s, ensure_ascii=False).replace("\x7f", "\\u007f")


def literal(v, start=0):
    """A JSON value as a TOML value that starts at column `start`: a string longer than the line as a multi-line string
    wrapped at its blanks with line-ending backslashes, an array longer than the line over several lines."""
    if v is None:
        raise TomlEditError("TOML has no null")
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        q = quoted(v)
        chunks = re.split(r"(?<=\S) (?=\S)", q[1:-1])
        if start + len(q) <= WIDTH or len(chunks) == 1 or v[:1].isspace():
            return q
        lines, line = [], "  "
        for chunk in chunks:
            if line != "  " and len(line) + len(chunk) + 4 > WIDTH:
                lines.append(line + " \\")
                line = "  "
            line += ("" if line == "  " else " ") + chunk
        return '"""\\\n' + "\n".join(lines + [line + '"""'])
    if isinstance(v, list):
        items = [literal(x) for x in v]
        if start + 2 + len(", ".join(items)) <= WIDTH or any("\n" in x for x in items):
            return "[" + ", ".join(items) + "]"
        lines, line = [], "["
        for k, x in enumerate(items):
            piece = x + ("]" if k == len(items) - 1 else ",")
            if line != "[" and (0 if lines else start) + len(line) + 1 + len(piece) > WIDTH:
                lines.append(line)
                line = " " * (start + 1) + piece
            else:
                line += ("" if line == "[" else " ") + piece
        return "\n".join(lines + [line])
    if isinstance(v, dict):
        return "{" + ", ".join(f"{key(k)} = {literal(x)}" for k, x in v.items()) + "}" if v else "{}"
    raise TomlEditError(f"no TOML for {v!r}")


def pack(items, indent):
    """Items (TOML literals) as lines of an array – "a, b," – that fit WIDTH after the indent; one item a line where an
    item alone is wider."""
    out = [[]]
    for x in items:
        if out[-1] and indent + len(", ".join(out[-1] + [x])) + 1 > WIDTH:
            out.append([])
        out[-1].append(x)
    return out


def line(k, v, prefix=""):
    """`key = value` – `prefix` for a dotted key (accept.)."""
    head = f"{prefix}{key(k)} = "
    return head + literal(v, len(head))


# --- reading the statements ------------------------------------------------------------------------------------------
@dataclass
class Array:
    open: int                   # offsets into the text: the [ and the ]
    close: int
    items: list                 # [(start, end)] of each item
    commas: list                # offsets of the commas


@dataclass
class Statement:
    kind: str                   # "table" (a header) or "key"
    path: tuple                 # the header's key, or the key relative to its table
    table: tuple                # the table a key belongs to: () for the top level; a header's own path
    first: int                  # its lines, a multi-line value included
    last: int
    array: Array | None = None  # the value of a key, where it is an array


class Scanner:
    """The statements of a TOML text, read as far as an editor needs them: where each starts and ends, and the items
    of an array. A text that is no TOML stops with TomlEditError and the line."""

    def __init__(self, text):
        self.t, self.n = text, len(text)

    def fail(self, i, what):
        raise TomlEditError(f"line {self.t.count(chr(10), 0, i) + 1}: {what}")

    def spaces(self, i):
        while i < self.n and self.t[i] in " \t":
            i += 1
        return i

    def blanks(self, i):
        """Past blanks, line ends and comments – what may stand between the items of an array."""
        while i < self.n:
            if self.t[i] in " \t\r\n":
                i += 1
            elif self.t[i] == "#":
                i = self.eol(i)
            else:
                break
        return i

    def eol(self, i):
        j = self.t.find("\n", i)
        return self.n if j < 0 else j

    def string(self, i):
        """The end of the string that starts at i."""
        t, q = self.t, self.t[i]
        if t.startswith(q * 3, i):
            j = i + 3
            while j < self.n:
                if q == '"' and t[j] == "\\":
                    j += 2
                    continue
                if t.startswith(q * 3, j):
                    end = j + 3
                    while end < self.n and t[end] == q and end - j < 5:      # up to two quotes before the end
                        end += 1
                    return end
                j += 1
            self.fail(i, "a multi-line string without its end")
        j = i + 1
        while j < self.n and t[j] != "\n":
            if q == '"' and t[j] == "\\":
                j += 2
                continue
            if t[j] == q:
                return j + 1
            j += 1
        self.fail(i, "a string without its end")

    def key(self, i):
        """A dotted key: (its parts, the offset after it)."""
        parts = []
        while True:
            i = self.spaces(i)
            if i < self.n and self.t[i] in "\"'":
                end = self.string(i)
                parts.append(tomllib.loads(f"k = {self.t[i:end]}")["k"])
                i = end
            else:
                m = BARE.match(self.t, i)
                if not m:
                    self.fail(i, "a key expected")
                parts.append(m.group())
                i = m.end()
            i = self.spaces(i)
            if i < self.n and self.t[i] == ".":
                i += 1
                continue
            return tuple(parts), i

    def value(self, i):
        """(the offset after the value at i, its Array or None)."""
        t = self.t
        if i >= self.n:
            self.fail(i, "a value expected")
        if t[i] in "\"'":
            return self.string(i), None
        if t[i] == "[":
            arr = Array(i, -1, [], [])
            i += 1
            while True:
                i = self.blanks(i)
                if i < self.n and t[i] == "]":
                    arr.close = i
                    return i + 1, arr
                start = i
                i, _ = self.value(i)
                arr.items.append((start, i))
                i = self.blanks(i)
                if i < self.n and t[i] == ",":
                    arr.commas.append(i)
                    i += 1
                elif i < self.n and t[i] == "]":
                    arr.close = i
                    return i + 1, arr
                else:
                    self.fail(i, "an array: , or ] expected")
        if t[i] == "{":
            i = self.blanks(i + 1)
            if i < self.n and t[i] == "}":
                return i + 1, None
            while True:
                _, i = self.key(i)
                i = self.spaces(i)
                if i >= self.n or t[i] != "=":
                    self.fail(i, "an inline table: = expected")
                i, _ = self.value(self.spaces(i + 1))
                i = self.blanks(i)
                if i < self.n and t[i] == ",":
                    i = self.blanks(i + 1)
                elif i < self.n and t[i] == "}":
                    return i + 1, None
                else:
                    self.fail(i, "an inline table: , or } expected")
        m = TOKEN.match(t, i)                         # a number, a boolean, a date
        if not m:
            self.fail(i, "a value expected")
        return m.end(), None

    def statements(self):
        t, out, table = self.t, [], ()
        starts = [0] + [m.end() for m in re.finditer("\n", t)]
        at = lambda offset: bisect.bisect_right(starts, offset) - 1        # noqa: E731 – the line of an offset
        i = 0
        while True:
            i = self.blanks(i)
            if i >= self.n:
                return out
            start = i
            if t[i] == "[":
                double = t.startswith("[[", i)
                path, i = self.key(i + 1 + double)
                close = "]]" if double else "]"
                if not t.startswith(close, i):
                    self.fail(i, f"a table header: {close} expected")
                i += len(close)
                table = path
                out.append(Statement("table", path, path, at(start), at(start)))
            else:
                path, i = self.key(i)
                if i >= self.n or t[i] != "=":
                    self.fail(i, "= expected")
                i, arr = self.value(self.spaces(i + 1))
                out.append(Statement("key", path, table, at(start), at(i - 1), arr))
            i = self.spaces(i)
            if i < self.n and t[i] == "#":
                i = self.eol(i)
            if i < self.n and t[i] not in "\r\n":
                self.fail(i, "the end of the line expected")


# --- the editor ------------------------------------------------------------------------------------------------------
class Doc:
    """A TOML text and its statements, read anew after every edit."""

    def __init__(self, text):
        self.text = text if not text or text.endswith("\n") else text + "\n"
        self._read()

    def _read(self):
        self.lines = self.text.splitlines(keepends=True)
        self.statements = Scanner(self.text).statements()

    def _insert(self, line_no, new_lines):
        self.lines[line_no:line_no] = [ln + "\n" for ln in new_lines]
        self.text = "".join(self.lines)
        self._read()

    def _splice(self, offset, new):
        self.text = self.text[:offset] + new + self.text[offset:]
        self._read()

    def headers(self, first=None):
        """The table headers, or those whose key starts with `first`."""
        return [s for s in self.statements if s.kind == "table" and (first is None or s.path[:1] == (first,))]

    def has_table(self, path):
        return any(s.path == tuple(path) for s in self.headers())

    def find(self, table, k):
        """The statement of key `k` in `table` (() for the top level), or None."""
        return next((s for s in self.statements if s.kind == "key" and s.table == tuple(table) and s.path == (k,)),
                    None)

    def _end(self, header):
        """The last line of a statement in the header's own table – the header's line when it holds none."""
        return max([header.first] + [s.last for s in self.statements if s.kind == "key" and s.table == header.path])

    def _above(self, header):
        """The first line of the comment lines directly above a header – they belong to it."""
        n = header.first
        while n > 0 and self.lines[n - 1].lstrip().startswith("#"):
            n -= 1
        return n

    def add_table(self, path, body, after, before=None):
        """[path] with its body lines behind the last table whose key starts with `after`; without one before the
        first table whose key starts with `before`, else at the end. A top-level `after = []` – a graph's empty list –
        gives way to the first table."""
        header = f"[{'.'.join(key(p) for p in path)}]"
        tables = self.headers(after)
        if tables:
            self._insert(self._end(tables[-1]) + 1, ["", header, *body])
            return
        empty = self.find((), after)
        if empty is not None:
            if not (empty.array and not empty.array.items):
                raise TomlEditError(f"{after} is no table [{after}.<key>] – {header} cannot join it")
            del self.lines[empty.first:empty.last + 1]
            self.text = "".join(self.lines)
            self._read()
        later = self.headers(before) if before else []
        if later:
            self._insert(self._above(later[0]), [header, *body, ""])
        else:
            self._insert(len(self.lines), ([""] if self.lines and self.lines[-1].strip() else []) + [header, *body])

    def add_keys(self, table, new_lines):
        """Lines of keys behind the last statement of `table`, before its sub-tables; at the top level behind the last
        top-level key, without one before the first table and the comment lines directly above it."""
        table = tuple(table)
        if table:
            header = next((s for s in self.headers() if s.path == table), None)
            if header is None:
                raise TomlEditError(f"no table [{'.'.join(key(p) for p in table)}]")
            self._insert(self._end(header) + 1, new_lines)
            return
        top = [s.last for s in self.statements if s.kind == "key" and s.table == ()]
        if top:
            self._insert(max(top) + 1, new_lines)
        elif self.headers():
            self._insert(self._above(self.headers()[0]), [*new_lines, ""])
        else:
            self._insert(len(self.lines), new_lines)

    def append(self, table, k, items):
        """The items (JSON values) at the end of the array `k` of `table`, in the array's style. False when the table
        has no key `k`."""
        s = self.find(table, k)
        if s is None:
            return False
        if s.array is None:
            raise TomlEditError(f"{k} in [{'.'.join(key(p) for p in table)}] is no array")
        arr, t = s.array, self.text
        new = [literal(x) for x in items]
        line_of = lambda offset: t.count("\n", 0, offset)                  # noqa: E731
        if not arr.items:
            self._splice(arr.open + 1, ", ".join(new))
            return True
        last_start, last_end = arr.items[-1]
        trailing = len(arr.commas) == len(arr.items)
        end_line = line_of(arr.commas[-1] if trailing else last_end)
        if line_of(arr.close) == end_line:                                # inline, or ] behind the last item
            if trailing:
                self._splice(arr.commas[-1] + 1, " " + ", ".join(new) + ",")
            else:
                self._splice(last_end, ", " + ", ".join(new))
            return True
        rows = {}                                                         # line -> items starting on it
        for a, _ in arr.items:
            rows.setdefault(line_of(a), []).append(a)
        first_on_line = rows[line_of(last_start)][0]
        bol = t.rfind("\n", 0, first_on_line) + 1
        indent = t[bol:first_on_line] if not t[bol:first_on_line].strip() else " " * (first_on_line - bol)
        one = all(len(v) == 1 for v in rows.values())
        groups = [[x] for x in new] if one else pack(new, len(indent))
        lines = [indent + ", ".join(g) + ("," if trailing or i < len(groups) - 1 else "") for i, g in enumerate(groups)]
        if not trailing:
            self._splice(last_end, ",")
        self._insert(end_line + 1, lines)
        return True
