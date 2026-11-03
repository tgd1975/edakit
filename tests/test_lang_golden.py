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
from edakit.lang.compile import resolved_of
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


# the bell's five configurations: where each source lies in a clone of the bell, and the base it names
BELL_SOURCES = {"main": "hardware", "smd": "variants/smd/hardware", "tht": "variants/tht/hardware",
                "esp32": "variants/esp32/hardware", "esp32tht": "variants/esp32tht/hardware"}


@pytest.mark.parametrize("name", list(BELL_SOURCES))
def test_the_bell_s_sources_read_and_are_in_the_canonical_layout(name):
    text = (BELL / f"{name}.circuit").read_text(encoding="utf-8")
    assert read(text, f"{name}.circuit").errors == []
    assert format(text) == text


def without_the_step_s_additions(graph):
    """A graph without what language 11's `def led` adds to the bell's: the records of its derivation, the LEDs'
    `value` – the colour the definition writes – and the accepts of DEF.derive that answer the records where the
    bell chose another resistor (its D-11, D-14, D-23)."""
    g = {k: v for k, v in graph.items() if k != "derivations"}
    comps = []
    for c in graph["components"]:
        c = {k: v for k, v in c.items() if not (c["type"] == "led" and k == "value")}
        if "DEF.derive" in (c.get("accept") or {}):
            c["accept"] = {k: v for k, v in c["accept"].items() if k != "DEF.derive"}
            if not c["accept"]:
                del c["accept"]
        comps.append(c)
    g["components"] = comps
    return g


@pytest.mark.skipif(not os.environ.get("BELL_ROOT"), reason="BELL_ROOT names no clone of the bell")
@pytest.mark.parametrize("name", list(BELL_SOURCES))
def test_the_bell_s_sources_compile_to_its_graphs(tmp_path, name):
    """Every configuration of the bell compiles from its source in the language to the graph it has, but for the
    step's additions: five records and the five LEDs' colours."""
    bell = Path(os.environ["BELL_ROOT"])
    copy = tmp_path / "bell"
    shutil.copytree(bell, copy, ignore=shutil.ignore_patterns(".git", "build"))
    for n, where in BELL_SOURCES.items():
        (copy / where / "graph.circuit").write_text((BELL / f"{n}.circuit").read_text())
    where = BELL_SOURCES[name]
    want = converted(json.loads((copy / where / "graph.json").read_text())["graph"])
    got, _ = resolved_of(copy / where / "graph.circuit")
    assert canonical(without_the_step_s_additions(got)) == canonical(want)
    assert len(got["derivations"]) == 5 and "derivations" not in want
    accepted = {c["designator"] for c in got["components"] if "DEF.derive" in (c.get("accept") or {})}
    assert accepted == {"main": {"R3", "R4"}, "smd": {"R3", "R4"}, "tht": {"R3", "R4"},
                        "esp32": {"R1", "R2", "R3", "R4", "R5"}, "esp32tht": {"R1", "R2", "R3", "R4", "R5"}}[name]
    assert {c["designator"]: c["value"] for c in got["components"] if c["type"] == "led"}.keys() == \
        {c["designator"] for c in want["components"] if c["type"] == "led"}


@pytest.mark.parametrize("case", ["add-led-circuit", "repeat-leds", "variant-smd"])
def test_the_evals_of_the_language_scaffold_their_project(case, tmp_path):
    """T.19: each case writes led-bar-circuit into its workspace; its graders read files of it or of the agent."""
    import subprocess
    root = Path(__file__).resolve().parents[1]
    subprocess.run(["bash", str(root / "evals" / case / "scaffold.sh")], cwd=tmp_path, check=True)
    assert (tmp_path / "hardware" / "graph.circuit").read_text() == (reference.CIRCUIT / "hardware" /
                                                                       "graph.circuit").read_text()
    for grader in (root / "evals" / case / "graders").glob("*.md"):
        text = grader.read_text()
        assert text.startswith("---\ntype: ") and "weight: 1" in text
    assert f"`{case}`" in (root / "evals" / "README.md").read_text()
