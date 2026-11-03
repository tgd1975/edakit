"""The statements of the circuit language as data (language 5): one dataclass per statement, each with its file and
line. The reader fills them from the tokens; nothing here knows a parts entry, a pin number or an expansion.

A pin word stays the word as written (`U1.GP3`, `D{n+2}.cathode`); a range is a Quantity, a parameter's name or
`@PORT`; an attribute is (key, value) in the order written, the value already of its kind (schema.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .units import Quantity


@dataclass(eq=False)
class Node:
    file: str
    line: int
    syntax = None                                     # the tokens.Statement a part or a net was read from


@dataclass(eq=False)
class GraphHead(Node):
    name: str | None = None
    version: str | None = None
    date: str | None = None


@dataclass(eq=False)
class Description(Node):
    text: str = ""


@dataclass(eq=False)
class Purpose(Node):
    fields: dict = field(default_factory=dict)        # use, market, country, notes – in the order written


@dataclass(eq=False)
class Convention(Node):
    key: str = ""
    text: str = ""


@dataclass(eq=False)
class Ground(Node):
    name: str = ""


@dataclass(eq=False)
class Grounds(Node):
    names: list = field(default_factory=list)


@dataclass(eq=False)
class Accept(Node):
    key: str = ""
    reason: str | None = None                         # None: `accept KEY -` in a variant, which removes it


@dataclass(eq=False)
class Lock(Node):
    pin: str = ""
    net: str = ""


@dataclass(eq=False)
class Set(Node):
    key: str = ""                                     # may be dotted: locks.doc_pin_table
    value: object = None                              # the parsed JSON


@dataclass(eq=False)
class Include(Node):
    path: str = ""


@dataclass(eq=False)
class Param(Node):
    name: str = ""
    value: Quantity | str | None = None               # a quantity, or a word (color = green)
    text: str = ""


@dataclass(eq=False)
class PinWord(Node):
    word: str = ""
    locked: bool = False


@dataclass(eq=False)
class Part(Node):
    des: str = ""
    type: str | None = None
    part: str | None = None                           # None: written `-`, or not given in a variant
    label: str | None = None
    attrs: list = field(default_factory=list)         # [(key, value)]: lcsc, value, bom, board, … and `set` keys
    nc: list = field(default_factory=list)            # [PinWord]
    pins: list = field(default_factory=list)          # [(number, name)]
    aliases: list = field(default_factory=list)       # [(name, word)]
    accepts: list = field(default_factory=list)       # [Accept]
    head: bool = True                                 # False: a binding's part in a usage (no TYPE, no PARTNO given)
    items: list = field(default_factory=list)         # [(kind, tokens)] as written – the formatter lays them out

    def attr(self, key, default=None):
        return next((v for k, v in reversed(self.attrs) if k == key), default)


@dataclass(eq=False)
class Net(Node):
    name: str = ""
    v: Quantity | str | None = None                   # a range, a parameter's name, or "@PORT"
    pins: list = field(default_factory=list)          # [PinWord]
    attrs: list = field(default_factory=list)         # [(key, value)]
    accepts: list = field(default_factory=list)
    without: list = field(default_factory=list)       # [PinWord] – only in a variant
    items: list = field(default_factory=list)         # [(kind, tokens)] as written – the formatter lays them out


@dataclass(eq=False)
class Cable(Node):
    name: str = ""
    frm: str = ""
    to: str = ""
    pairs: list = field(default_factory=list)         # [(from word, to word)]
    attrs: list = field(default_factory=list)


@dataclass(eq=False)
class Layout(Node):
    kind: str = ""                                    # fixed, edge, near, loop, apart, note
    parts: list = field(default_factory=list)         # fixed, edge: designators; near: [part, host, …]
    a: str = ""                                       # loop: pin words; apart: net names
    b: str = ""
    limit: float | None = None                        # max_mm of a loop, min_mm of apart
    text: str | None = None                           # loop and apart: what; note: the note


@dataclass(eq=False)
class Arg(Node):
    name: str | None = None                           # None: by position
    text: str = ""                                    # the value as written
    value: Quantity | str | None = None


@dataclass(eq=False)
class Derive(Node):
    targets: list = field(default_factory=list)       # ["R.value"]
    rule: str = ""
    args: list = field(default_factory=list)          # [Arg]


@dataclass(eq=False)
class Def(Node):
    name: str = ""
    params: list = field(default_factory=list)        # [Arg] with name and default
    ports: list = field(default_factory=list)         # [(name, about or None)]
    title: str | None = None
    about: str | None = None
    body: list = field(default_factory=list)          # Part, Net, Derive in order
    covers: list = field(default_factory=list)
    optional_parts: list = field(default_factory=list)
    optional_ports: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    sets: list = field(default_factory=list)          # [Set]: test, graph


@dataclass(eq=False)
class Binding(Node):
    left: str = ""
    right: str = ""
    part: Part | None = None                          # a part binding's attributes: PARTNO, lcsc, value, label …


@dataclass(eq=False)
class Use(Node):
    definition: str = ""
    instance: str = ""
    params: list = field(default_factory=list)        # [Arg]
    bindings: list = field(default_factory=list)      # [Binding]
    without: list = field(default_factory=list)       # [designator of the definition]
    satisfies: list = field(default_factory=list)
    decision: list = field(default_factory=list)


@dataclass(eq=False)
class For(Node):
    var: str = ""
    start: int = 0
    stop: int = 0
    body: list = field(default_factory=list)


@dataclass(eq=False)
class Variant(Node):
    name: str = ""
    base: str = ""
    body: list = field(default_factory=list)


@dataclass(eq=False)
class Need(Node):
    id: str = ""
    text: str = ""
    who: str = ""
    source: str = ""
    status: str = ""
    reason: str = ""


@dataclass(eq=False)
class Requirement(Node):
    id: str = ""
    frm: list = field(default_factory=list)
    binding: str = ""
    text: str = ""
    subject: str = ""
    require: str = ""
    verify: list = field(default_factory=list)        # [(kind, text)]
    source: str = ""
    status: str = ""
    reason: str = ""


@dataclass(eq=False)
class Source:
    file: str
    role: str = "graph"                               # graph, requirements, block
    statements: list = field(default_factory=list)    # the model objects in order
    syntax: list = field(default_factory=list)        # the tokens.Statement objects, for the formatter
    tail: list = field(default_factory=list)          # blank and comment lines after the last statement
    errors: list = field(default_factory=list)        # [LangError]
    text: str = ""

    @property
    def variant(self):
        first = self.statements[0] if self.statements else None
        return first if isinstance(first, Variant) else None
