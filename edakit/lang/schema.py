"""The attribute table of the circuit language (language 6): the keys a statement passes into the graph, per object,
with the kind of value each takes – the keys of handbook 3.1, and the one place a new key of the schema is added.

    kind_of(COMPONENT, "value")   "word"
    nearest(COMPONENT, "valeu")   "value"   – the error of an unknown key names it

Kinds: word (a word or a string, kept as text), string (a text), number, boolean (`yes`/`no`, or the key alone for
yes), range (a quantity in its unit, written to the graph as [lo, hi]), number_or_range, list and table (only through
`set KEY JSON`). The reader reads `KEY VALUE` pairs by this table; the converter writes them by it and the formatter
orders them by it – the order of each table is the order of a part's or a net's continuation lines.
"""

from __future__ import annotations

import difflib

from ..circuit import CABLE_KEYS

GRAPH = {"name": "word", "version": "word", "date": "word", "description": "string", "purpose": "table",
         "conventions": "table", "components": "list", "nets": "list", "cables": "list", "layout": "table",
         "locks": "table", "accept": "table", "ground": "word", "grounds": "list", "derivations": "list"}

# A component: the head's keys first (part DES TYPE PARTNO …), then the attributes in the order the formatter writes.
COMPONENT = {"type": "word", "part": "word", "lcsc": "word", "value": "word", "bom": "boolean", "label": "string",
             "board": "word", "supplier": "word", "spare": "number", "config": "word", "source": "word",
             "off_board": "boolean", "function": "string", "verify": "string", "satisfies": "list",
             "decision": "list", "states": "table", "strip": "table", "easyeda_device": "table", "pins": "table",
             "nc": "list", "accept": "table", "notes": "string"}

NET = {"v": "range", "fn": "word", "fn_bus": "word", "bus": "word", "pwm_hz": "number_or_range", "clock_hz": "number",
       "signal": "boolean", "isolated": "boolean", "instrument": "word", "load_min_ohm": "number", "matrix": "word",
       "satisfies": "list", "decision": "list", "accept": "table", "notes": "string", "pins": "list"}

CABLE = {k: ("word" if k in ("name", "from", "to") else "table" if k == "pins"
             else "string" if k in ("notes", "about") else "number") for k in sorted(CABLE_KEYS)}

LAYOUT = {"fixed": "list", "edge": "list", "near": "table", "loops": "list", "apart": "list", "notes": "list"}

UNIT = {"v": "V", "pwm_hz": "Hz"}            # the unit of a range attribute

TABLES = {"graph": GRAPH, "component": COMPONENT, "net": NET, "cable": CABLE, "layout": LAYOUT}


class UnknownKey(KeyError):
    def __init__(self, table, key):
        super().__init__(key)
        self.key, self.near = key, nearest(table, key)

    def __str__(self):
        return f"unknown key {self.key!r}" + (f" – {self.near}?" if self.near else "")


def kind_of(table, key):
    """The kind of a key of the table; UnknownKey when the table has none."""
    if key not in table:
        raise UnknownKey(table, key)
    return table[key]


def nearest(table, key):
    """The known key nearest to a misspelt one, or None."""
    got = difflib.get_close_matches(key, list(table), n=1, cutoff=0.6)
    return got[0] if got else None


def written(table):
    """The keys a `KEY VALUE` pair may write – everything but lists and tables, which take `set KEY JSON` or a
    statement of their own."""
    return [k for k, kind in table.items() if kind not in ("list", "table")]
