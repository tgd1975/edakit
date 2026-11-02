"""T.3 of circuit-dsl-toolchain.md: the attribute table of the language against handbook 3.1."""

import re
from pathlib import Path

import pytest

from edakit.lang import schema
from edakit.lang.reader import read

ROOT = Path(__file__).resolve().parents[1]
# Keys the language passes through that handbook 3.1's table of fields does not list, each with where it comes from.
BEYOND = {"function": "a component's function in words, in led-bar's graph – read by no check",
          "satisfies": "language 5.10, documented with T.15", "decision": "language 5.10, documented with T.15",
          "derivations": "language 8, the compiler's records – documented with T.10"}


def handbook_fields():
    """(object, key) of every row of handbook 3.1's table of fields."""
    text = (ROOT / "handbook" / "03-hardware-graph.md").read_text(encoding="utf-8")
    table = text[text.index("### Fields"):text.index("### A pin by number")]
    out = []
    for row in table.splitlines():
        if not row.startswith("| ") or row.startswith("| Field") or row.startswith("|---"):
            continue
        cell = row.split("|")[1]
        obj = "net" if cell.strip().startswith("net ") else "graph" if "(graph)" in cell else "any"
        out += [(obj, k.split(":")[0]) for k in re.findall(r"`([^`]+)`", cell)]
    return out


def test_every_field_of_handbook_3_1_is_in_the_table():
    fields = handbook_fields()
    assert len(fields) > 35
    known = set(schema.GRAPH) | set(schema.COMPONENT) | {"designator"}
    for obj, key in fields:
        if obj == "net":
            assert key in schema.NET, key
        elif obj == "graph":
            assert key in schema.GRAPH, key
        else:
            assert key in known, key


def test_every_key_of_the_table_is_documented_or_named_here():
    documented = {k for _, k in handbook_fields()} | {"name", "pins", "v", "components", "nets"}
    for table in (schema.GRAPH, schema.COMPONENT, schema.NET):
        for key in table:
            assert key in documented or key in BEYOND, key


def test_the_cable_keys_are_edakit_s():
    from edakit.circuit import CABLE_KEYS
    assert set(schema.CABLE) == CABLE_KEYS


def test_kind_and_nearest():
    assert schema.kind_of(schema.COMPONENT, "value") == "word"
    assert schema.kind_of(schema.NET, "v") == "range"
    assert schema.nearest(schema.COMPONENT, "labl") == "label"
    assert schema.nearest(schema.NET, "pwmhz") == "pwm_hz"
    with pytest.raises(schema.UnknownKey) as e:
        schema.kind_of(schema.COMPONENT, "valeu")
    assert str(e.value) == "unknown key 'valeu' – value?"


@pytest.mark.parametrize("text, said", [
    ("part R1 resistor X labl \"x\"\n", "unknown key 'labl' – label?"),
    ("net A 0 V R1.1 pwmhz 100\n", "unknown key 'pwmhz' – pwm_hz?"),
    ("part R1 resistor X states 1\n", "states: a table – written `set states JSON`"),
    ("part R1 resistor X\n  set stat {}\n", "set stat: unknown key – states?"),
])
def test_an_unknown_key_names_the_nearest(text, said):
    assert said in [e.text for e in read(text, "g.circuit").errors]
