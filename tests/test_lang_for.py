"""T.12 of circuit-dsl-toolchain.md: repetition – a `for` over an integer range, its body once per value with {n},
{n+k}, {n-k} and {n*k} put in (language 5.7)."""

import pytest
from lang_examples import LED_BAR
from lang_project import as_fixture, flat, to_circuit

from edakit.graph_form import canonical
from edakit.lang.compile import compile_path, resolved_of
from edakit.lang.reader import CompileError, read


def test_the_loop_equals_the_flat_form(project):
    cfg = to_circuit(project, as_fixture(LED_BAR))
    looped, smap = resolved_of(cfg.graph)
    cfg.graph.write_text(as_fixture(flat()), encoding="utf-8")
    assert canonical(looped) == canonical(resolved_of(cfg.graph)[0])
    loop_line = as_fixture(LED_BAR).splitlines().index("for n in 0..7") + 1
    assert all(smap.components[f"D{n}"]["line"] == loop_line + 1 for n in range(2, 10))


def test_the_expressions_in_designators_pin_words_and_strings(project):
    cfg = to_circuit(project, as_fixture(LED_BAR))
    g = compile_path(cfg.graph)
    d5 = next(c for c in g["components"] if c["designator"] == "D5")
    assert d5["label"] == "LED 4 (green 0805)"
    led3 = next(n for n in g["nets"] if n["name"] == "LED3")
    assert led3["pins"] == ["U2.OUT3", "D5.cathode"]
    plus = next(n for n in g["nets"] if n["name"] == "+5V")
    assert plus["pins"][-8:] == [f"D{n}.anode" for n in range(2, 10)]


def test_times_and_minus(project):
    text = as_fixture(LED_BAR).replace("for n in 0..7\n", "for n in 1..8\n").replace("{n+2}", "{n+1}").replace(
        "{n+1} (green", "{n} (green").replace("U2.OUT{n}", "U2.OUT{n-1}").replace("net LED{n}", "net LED{n*10}")
    cfg = to_circuit(project, text)
    g = compile_path(cfg.graph)
    assert {"LED10", "LED80"} <= {n["name"] for n in g["nets"]}


def test_a_loop_that_makes_a_designator_twice(project):
    text = as_fixture(LED_BAR).replace("part D{n+2} led", "part D2 led")
    cfg = to_circuit(project, text)
    with pytest.raises(CompileError, match="part D2 twice"):
        compile_path(cfg.graph)


@pytest.mark.parametrize("text, said", [
    ("for n in 3..1\n  part R{n} resistor X\n", "B < A"),
    ("for n in 0..1\n  for m in 0..1\n    part R{m} resistor X\n", "for: not allowed here"),
    ("for n in 0..1\n  part R{m} resistor X\n", "{m}: the loop's variable is n"),
    ("for n in 0..1\n  part R{n/2} resistor X\n", "{n/2}: in a loop only"),
])
def test_the_errors(text, said):
    assert any(said in e.text for e in read(text, "g.circuit").errors)
