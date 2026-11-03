"""T.9 of circuit-dsl-toolchain.md: the TextMate grammar of the circuit language – valid JSON, generated from the
reader's keywords and the attribute table, every keyword matched."""

import json
import re

import pytest
from lang_examples import LED_BAR

from edakit.lang import grammar
from edakit.lang.reader import KEYWORDS, STATEMENTS


def test_the_files_are_what_is_generated():
    for path, text in grammar.files().items():
        assert path.read_text(encoding="utf-8") == text, "python -m edakit.lang.grammar --write"
        json.loads(text)


def test_the_configuration_names_the_comment():
    conf = json.loads(grammar.CONFIG.read_text())
    assert conf["comments"]["lineComment"] == "#"


def patterns():
    g = json.loads(grammar.GRAMMAR.read_text())
    assert g["scopeName"] == "source.circuit"
    return {k: re.compile(v["match"]) for k, v in g["repository"].items() if "match" in v}


@pytest.mark.parametrize("kw", sorted(KEYWORDS))
def test_every_keyword_is_matched(kw):
    p = patterns()
    line = f"{kw} x" if kw in STATEMENTS else f"part R1 resistor X {kw}"
    assert any(m.search(line) and kw in m.search(line).group(0) for m in p.values()), kw


@pytest.mark.parametrize("text, kind", [
    ("U1.GP3", "pin"), ("D{n+2}.cathode", "pin"), ("0..5.5 V", "quantity"), ("4k7", "quantity"),
    ("LIM.v", "code"), ("(locked)", "locked"), ("{n+1}", "brace"), ("# a note", "comment"), ("R12", "designator"),
])
def test_the_pieces_of_a_line(text, kind):
    assert patterns()[kind].search(f"net X {text} ")


def test_led_bar_s_statements_start_with_a_statement_keyword():
    st = patterns()["statement"]
    heads = [ln for ln in LED_BAR.splitlines() if ln and not ln[0].isspace()]
    assert all(st.match(ln) for ln in heads)
