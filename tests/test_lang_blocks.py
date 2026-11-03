"""T.7 of circuit-dsl-toolchain.md: the block library as definitions – edakit/blocks/*.circuit the source, the JSON
`block add` reads generated from it and held equal by this test."""

import json

import pytest

from edakit import block
from edakit.lang import blocks
from edakit.lang.compile import check_def
from edakit.lang.fmt import format
from edakit.lang.reader import CompileError, read

NAMES = sorted(blocks.sources())


def test_every_block_has_its_source():
    assert NAMES == sorted(block.library()) and len(NAMES) == 26


@pytest.mark.parametrize("name", NAMES)
def test_every_generated_json_equals_the_committed_one(name):
    path, text = blocks.generated()[name]
    assert path.read_text(encoding="utf-8") == text, "python -m edakit.lang.blocks --write"


@pytest.mark.parametrize("name", NAMES)
def test_every_source_reads_and_is_in_the_canonical_layout(name):
    path = blocks.sources()[name]
    text = path.read_text(encoding="utf-8")
    assert read(text, path.name, "block").errors == []
    assert format(text, path.name, "block") == text


def test_the_json_names_its_params_and_derivations():
    led = block.load("led")
    assert led["params"] == {"i": {"default": "10 mA"}}
    assert led["derivations"] == [{"targets": ["R1.value"], "rule": "series_resistor", "args": {"0": "i"}}]
    assert [d["targets"] for d in block.load("battery-sense")["derivations"]] == [["R3.value", "R4.value"]]
    assert len(block.load("i2c-pullups")["derivations"]) == 2


def test_from_json_gives_back_the_definition():
    parts = blocks.library_parts()
    for name in NAMES:
        b = block.load(name)
        text = blocks.from_json(b, parts)
        assert blocks.block_json(read(text, f"{name}.circuit", "block").statements[0], parts) == b, name


def defn(text):
    src = read(text, "x.circuit", "block")
    assert src.errors == []
    return src.statements[0]


@pytest.mark.parametrize("text, said", [
    ("def a ports in out\n  part R1 resistor X\n  net in R1.1\n", "port out is none of its nets"),
    ("def a\n  part R1 resistor X\n  net n R1.1\n  derive R9.value series_resistor(i)\n", "R9 is no part of def a"),
    ("def a\n  part R1 resistor X\n  part R1 resistor Y\n", "part R1 twice"),
    ("def a\n  part R1 resistor X\n  net n R1.1\n  net n R1.2\n", "net n twice"),
    ("def a\n  part R1 resistor X\n  optional parts R2\n", "optional part R2 is no part of it"),
])
def test_the_errors_of_a_definition(text, said):
    got = [e.text for e in check_def(defn(text))]
    assert any(said in e for e in got), got


def test_a_block_with_a_wrong_pin_word_is_refused():
    text = blocks.sources()["led"].read_text(encoding="utf-8").replace("D1.anode", "D1.anod")
    with pytest.raises(CompileError, match="names no pin"):
        blocks.block_json(defn(text), blocks.library_parts())


def test_the_command_lists_and_writes(tmp_path, monkeypatch, capsys):
    assert blocks.main([]) == 0
    path = blocks.HERE / "led.json"
    before = path.read_text(encoding="utf-8")
    try:
        path.write_text(before.replace('"150"', '"151"'), encoding="utf-8")
        assert blocks.main([]) == 1 and "differs: edakit/blocks/led.json" in capsys.readouterr().out
        assert blocks.main(["--write"]) == 0
        assert path.read_text(encoding="utf-8") == before
    finally:
        path.write_text(before, encoding="utf-8")


def test_block_add_reads_the_generated_json_as_before(project):
    from test_block import signals
    signals(project)
    _, comps, new_nets, extended, _, copy, _ = block.add(project.config(), "led", "STATUS", {"in": "SIG"})
    assert [c["designator"] for c in comps] == ["R3", "D10"] and comps[0]["value"] == "150"
    assert new_nets == [{"name": "STATUS_ANODE", "pins": ["R3.2", "D10.1"], "v": [0, 3.4]}]
    assert json.loads(project.graph_file.read_text())["graph"].get("derivations") is None   # no --set, no record
