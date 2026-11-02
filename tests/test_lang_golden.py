"""T.17 of circuit-dsl-toolchain.md: the fixture led-bar-circuit – golden, determinism and round trip; the bell's
sources, compiled against the bell where BELL_ROOT names a clone."""

import json
import os
import shutil
from pathlib import Path

import pytest

import reference
from edakit import cli
from edakit.design import load_graph, load_parts
from edakit.graph_form import canonical, converted, design_of, indent_of, render
from edakit.lang.compile import compile_path, resolved_of
from edakit.lang.convert import to_circuit
from edakit.lang.fmt import format
from edakit.lang.reader import read

BELL = Path(__file__).parent / "fixtures" / "bell"


def test_the_fixture_compiles_to_led_bar_s_graph(project_circuit):
    want = converted(json.loads((reference.EXAMPLE / "hardware" / "graph.json").read_text())["graph"])
    got, _ = resolved_of(project_circuit.graph_file)
    assert canonical(got) == canonical(want)


def test_two_compiles_are_byte_equal_and_the_committed_file_is_the_compile(project_circuit):
    indent = indent_of(reference.CIRCUIT / "hardware" / "graph.json")
    a = render(resolved_of(project_circuit.graph_file)[0], indent)
    b = render(resolved_of(project_circuit.graph_file)[0], indent)
    assert a == b == (reference.CIRCUIT / "hardware" / "graph.json").read_text()
    assert cli.main(["graph", "json", "--check", "--config", str(project_circuit.root / "edakit.toml")]) == 0


@pytest.mark.parametrize("command", [["check"], ["sim"], ["gate"]])
def test_check_sim_and_gate_report_what_led_bar_reports(project_circuit, tmp_path, command, capsys):
    plain = reference.Project.copy_of_example(tmp_path / "led-bar")
    codes = []
    outs = []
    for root in (plain.root, project_circuit.root):
        capsys.readouterr()
        codes.append(cli.main([*command, "--config", str(root / "edakit.toml")]))
        outs.append(capsys.readouterr().out)
    assert codes[0] == codes[1]
    if command == ["check"]:
        assert outs[0].splitlines()[-1] == outs[1].splitlines()[-1]


def test_the_round_trip_led_bar_convert_compile(project_circuit, tmp_path):
    src = load_graph(reference.EXAMPLE / "hardware" / "graph.json")
    cfg = project_circuit.config()
    text = to_circuit(src, design_of(cfg.graph, load_parts(cfg.parts), list(cfg.boards), src))
    path = project_circuit.root / "hardware" / "again.circuit"
    path.write_text(text)
    assert canonical(resolved_of(path)[0]) == canonical(converted(json.loads(
        (reference.EXAMPLE / "hardware" / "graph.json").read_text())["graph"]))


@pytest.mark.parametrize("name", ["main", "smd", "tht"])
def test_the_bell_s_sources_read_and_are_in_the_canonical_layout(name):
    text = (BELL / f"{name}.circuit").read_text(encoding="utf-8")
    assert read(text, f"{name}.circuit").errors == []
    assert format(format(text)) == format(text)


@pytest.mark.skipif(not os.environ.get("BELL_ROOT"), reason="BELL_ROOT names no clone of the bell")
def test_the_bell_s_sources_compile_to_its_graphs(tmp_path):
    bell = Path(os.environ["BELL_ROOT"])
    copy = tmp_path / "bell"
    shutil.copytree(bell, copy, ignore=shutil.ignore_patterns(".git", "build"))
    for name, where in (("main", "hardware"), ("smd", "variants/smd/hardware"), ("tht", "variants/tht/hardware")):
        want = json.loads((copy / where / "graph.json").read_text())["graph"]
        (copy / where / "graph.circuit").write_text((BELL / f"{name}.circuit").read_text())
        got = compile_path(copy / where / "graph.circuit")
        assert {c["designator"] for c in got["components"]} == {c["designator"] for c in want["components"]}, name
