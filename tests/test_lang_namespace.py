"""T.13 of circuit-dsl-toolchain.md: param, alias and include – one namespace over the main file and the files it
includes (language 2, 5.1, 5.2)."""

import pytest
from test_lang_use import HEAD, step

from edakit.lang.compile import compile_path, resolved_of
from edakit.lang.reader import CompileError
from lang_examples import BELL_STEP


def net(g, name):
    return next(n for n in g["nets"] if n["name"] == name)


def bell(project, text=None, head=HEAD):
    path = step(project, "", head)
    body = (text or BELL_STEP).replace("C2895549", "C2297").replace("XL-504UGD", "KT-0805G")
    path.write_text(head + "param vlogic = 0..5.5 V\n" + body, encoding="utf-8")
    return path


def test_a_net_takes_a_parameter_s_range(project):
    g = compile_path(bell(project))
    assert net(g, "LED_G1")["v"] == [0, 5.5] and net(g, "LED_G1_A")["v"] == [0, 5.5]


def test_a_usage_passes_a_parameter(project):
    path = bell(project, BELL_STEP.replace("use led step1 (color = green)", "use led step1 (color = green, i = cur)"))
    path.write_text(path.read_text().replace("param vlogic", "param cur = 4 mA\nparam vlogic"))
    g, _ = resolved_of(path)
    rec = next(r for r in g["derivations"] if r["part"] == "R4")
    assert next(r for r in rec["inputs"] if r["name"] == "i")["value"] == 0.004


def test_a_parameter_without_a_value(project):
    path = bell(project, BELL_STEP.replace("net LED_G1 vlogic", "net LED_G1 vlogx"))
    with pytest.raises(CompileError, match="vlogx: no parameter with a quantity – parameters: vlogic"):
        compile_path(path)


def test_an_alias_in_a_net_a_lock_nc_and_a_cable(project):
    head = HEAD.replace("alias led1 = D6 led2 = D5", "alias led1 = D6 led2 = D5 spare = D7\n  nc spare") + \
        "lock U1.led1 LED_G1\n"
    g = compile_path(bell(project, head=head))
    u1 = next(c for c in g["components"] if c["designator"] == "U1")
    assert u1["nc"] == ["D7"] and g["locks"]["pins"]["U1.D6"] == "LED_G1"


def test_an_alias_that_names_no_pin(project):
    with pytest.raises(CompileError, match="alias led1 = D66: names no pin of U1"):
        compile_path(bell(project, head=HEAD.replace("led1 = D6", "led1 = D66")))


def test_a_definition_in_an_included_file(project):
    defs = BELL_STEP[:BELL_STEP.index("use led step1")]
    (project.root / "hardware" / "defs.circuit").write_text(defs, encoding="utf-8")
    path = bell(project, "include hardware/defs.circuit\n" + BELL_STEP[BELL_STEP.index("use led step1"):])
    g = compile_path(path)
    assert {"R4", "R3"} <= {c["designator"] for c in g["components"]}


def test_a_designator_in_two_files(project):
    (project.root / "hardware" / "more.circuit").write_text('part U1 module X "again"\n', encoding="utf-8")
    path = bell(project, "include hardware/more.circuit\n" + BELL_STEP)
    with pytest.raises(CompileError) as e:
        compile_path(path)
    assert "hardware/more.circuit:1: part U1 twice – first at hardware/graph.circuit:2" in str(e.value)


def test_an_include_cycle_and_a_path_outside(project):
    (project.root / "hardware" / "a.circuit").write_text("include hardware/b.circuit\n", encoding="utf-8")
    (project.root / "hardware" / "b.circuit").write_text("include hardware/a.circuit\n", encoding="utf-8")
    path = bell(project, "include hardware/a.circuit\n" + BELL_STEP)
    with pytest.raises(CompileError, match="a cycle – hardware/graph.circuit → hardware/a.circuit → "
                                           "hardware/b.circuit → hardware/a.circuit"):
        compile_path(path)
    path = bell(project, "include ../outside.circuit\n" + BELL_STEP)
    with pytest.raises(CompileError, match="include ../outside.circuit: outside the project"):
        compile_path(path)


def test_an_included_file_is_no_main_file(project):
    (project.root / "hardware" / "x.circuit").write_text("graph other\n", encoding="utf-8")
    with pytest.raises(CompileError, match="graph in an included file"):
        compile_path(bell(project, "include hardware/x.circuit\n" + BELL_STEP))
