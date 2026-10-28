"""edakit docs and G-19: documents and schematic notes quote values from graph, parts and simulation (handbook 6.6)."""

import argparse
import json
import xml.etree.ElementTree as ET

import pytest

from edakit import cli, docs, eda, schematic_draw
from edakit.design import Design
from edakit.sim import run as simrun

SVG = "{http://www.w3.org/2000/svg}"
LED_CURRENT = "sim:max E-3 * D2 LED current*"
BLOCK = f"<!--edakit {LED_CURRENT}-->9.45 mA<!--/edakit-->"


@pytest.fixture(autouse=True)
def no_easyeda(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("started EasyEDA")
    monkeypatch.setattr(eda, "start", refuse)
    monkeypatch.setattr(eda, "connect", refuse)


def r1_to_4k7(project):
    """R1 swapped from 2 k (C17604) to 4.7 k (C17673 from the block library): 15 x 1.26 V / 4.7 k = 4.02 mA."""
    project.use_library_part("C17673")
    g = project.graph()
    r1 = project.comp(g, "R1")
    r1.update(lcsc="C17673", part="0805W8F4701T5E", value="4.7k")
    project.save_graph(g)


def listed(project, text, name="docs/values.md"):
    f = project.root / name
    f.parent.mkdir(exist_ok=True)
    f.write_text(text)
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + f'\n[docs]\nfiles = ["{name}"]\n')
    return f


def note(project, line):
    f = project.root / "hardware" / "schematic.toml"
    f.write_text(f.read_text().replace('"TLC5916: I_OUT = 15 x 1.26 V / R1 = 9.45 mA"', json.dumps(line)))


def drawn_texts(project, tmp_path):
    out = tmp_path / "s.svg"
    code = schematic_draw.main(project.config(), argparse.Namespace(board=None, out=str(out), force=False))
    assert code == 0
    return {t.text for t in ET.parse(out).getroot().iter(f"{SVG}text")}


def test_schematic_note_quotes_the_simulation(project, tmp_path):
    note(project, "TLC5916: I_OUT = 15 x 1.26 V / R1 = {" + LED_CURRENT + "}")
    assert "TLC5916: I_OUT = 15 x 1.26 V / R1 = 9.45 mA" in drawn_texts(project, tmp_path)
    r1_to_4k7(project)
    assert "TLC5916: I_OUT = 15 x 1.26 V / R1 = 4.02 mA" in drawn_texts(project, tmp_path)


def test_a_stale_block_is_g19_and_write_fills_it(project, monkeypatch, capsys):
    f = listed(project, f"# Values\n\nLED current: {BLOCK} per LED.\n")
    monkeypatch.chdir(project.root)
    assert cli.main(["docs"]) == 0
    r1_to_4k7(project)
    capsys.readouterr()
    assert cli.main(["docs"]) == 2
    out = capsys.readouterr().out
    assert f"G-19  docs/values.md:3: {LED_CURRENT}: written 9.45 mA, now 4.02 mA" in out
    assert cli.main(["docs", "--write"]) == 0
    assert f.read_text() == f"# Values\n\nLED current: <!--edakit {LED_CURRENT}-->4.02 mA<!--/edakit--> per LED.\n"
    assert cli.main(["docs"]) == 0


def test_text_outside_blocks_and_files_not_listed_stay_untouched(project, tmp_path, monkeypatch, capsys):
    other = project.root / "docs" / "other.md"
    other.parent.mkdir()
    other.write_text("<!--edakit graph:R99.value-->x<!--/edakit-->\n")    # not listed: never read
    note(project, "Braces {not a source} and {R1} stay as they are")
    monkeypatch.chdir(project.root)
    assert cli.main(["docs"]) == 0 and "R99" not in capsys.readouterr().out
    assert "Braces {not a source} and {R1} stay as they are" in drawn_texts(project, tmp_path)


def test_sources_and_formats(project):
    cfg = project.config()
    src = docs.Sources(cfg, Design.from_config(cfg))
    assert src.text("graph:R1.value") == "2k"
    assert src.text("graph:version") == "1.0"
    assert src.text("graph:LED_OE.v") == "0 … 3.4 V"
    assert src.text("part:C90107.params.vrext_v") == "1.26 V"
    assert src.text("part:C17414.params.value_ohm") == "10 kΩ"
    assert src.text("part:C90107.params.vrext_v", "%.1f V") == "1.3 V"
    assert src.text(LED_CURRENT) == "9.45 mA"
    assert src.text(LED_CURRENT, "%.1f mA") == "9.4 mA"           # scaled to the prefix of the format
    assert src.text("sim:min E-3 */idle/* D2 LED dark", "%.0f nA") in {"21 nA", "26 nA", "20 nA"}
    src.decimal = ","                                          # [docs] decimal = "," for documents in German
    assert src.text(LED_CURRENT) == "9,45 mA" and src.text("graph:LED_OE.v") == "0 … 3,4 V"
    for bad, why in (("graph:R99.value", "no part, net or cable R99"), ("graph:R1.colour", "no key colour"),
                     ("part:C1.params.x", "no parts entry C1"), ("sim:max E-9 *", "no simulation row matches"),
                     ("sim:one E-3 * D2 LED current*", "rows match, 'one' wants exactly one"),
                     ("sim:avg E-3 *", "sim:max, sim:min or sim:one"), ("foo:bar", "unknown source")):
        with pytest.raises(docs.QuoteError, match=why):
            src.text(bad)


def test_an_unknown_designator_in_a_note_is_g19(project, monkeypatch, capsys):
    note(project, "R41 is {graph:R41.value}")
    monkeypatch.chdir(project.root)
    assert cli.main(["docs"]) == 2
    out = capsys.readouterr().out
    assert 'G-19  hardware/schematic.toml [layout.notes] "LED Driver": {graph:R41.value}: no part, net or cable R41' in out


def test_the_last_simulation_result_is_reused(project, monkeypatch, capsys):
    listed(project, f"{BLOCK}\n")
    monkeypatch.chdir(project.root)
    assert cli.main(["sim"]) == 0
    real = simrun.run_all

    def no_run(*a, **k):
        raise AssertionError("simulated again")
    monkeypatch.setattr(simrun, "run_all", no_run)
    assert cli.main(["docs"]) == 0                      # the result of `edakit sim`, its inputs unchanged
    monkeypatch.setattr(simrun, "run_all", real)
    r1_to_4k7(project)                                  # the inputs changed: simulated again
    capsys.readouterr()
    assert cli.main(["docs"]) == 2 and "now 4.02 mA" in capsys.readouterr().out


def test_gate_runs_g19_on_its_own_simulation(project, monkeypatch, capsys):
    listed(project, f"{BLOCK}\n")
    monkeypatch.chdir(project.root)
    r1_to_4k7(project)
    cli.main(["gate"])
    protocol = next((project.root / "build" / "release").glob("*/protocol.md")).read_text()
    assert "G-19 (documents quote the design data)" in protocol and "written 9.45 mA, now 4.02 mA" in protocol


def test_without_quotes_nothing_happens(project, monkeypatch, capsys):
    monkeypatch.chdir(project.root)
    assert cli.main(["docs"]) == 0 and "nothing quoted" in capsys.readouterr().out
    cfg = project.config()
    assert docs.stage_rows(cfg, Design.from_config(cfg), {"checks": []}) == []
