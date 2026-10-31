"""edakit docs and DOCS.quote: documents and schematic notes quote values from graph, parts and simulation (handbook 6.6)."""

import argparse
import json
import xml.etree.ElementTree as ET

import pytest
from test_requirements import NEED, REQUIREMENT, with_requirements

from edakit import cli, docs, eda, schematic_draw
from edakit.design import Design
from edakit.sim import run as simrun

SVG = "{http://www.w3.org/2000/svg}"
LED_CURRENT = "sim:max SIM.state * D2 LED current*"
BLOCK = f"<!--edakit {LED_CURRENT}-->9.45 mA<!--/edakit-->"
R1 = "With all eight LEDs on, the board draws at most 500 mA from J1 at 4.75 to 5.25 V."   # R-1 of the example's file


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
    assert f"DOCS.quote  docs/values.md:3: {LED_CURRENT}: written 9.45 mA, now 4.02 mA" in out
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
    assert src.text("part:C90107.values.vrext_v") == "1.26 V"
    assert src.text("part:C17414.values.value_ohm") == "10 kΩ"
    assert src.text("part:C90107.values.vrext_v", "%.1f V") == "1.3 V"
    assert src.text(LED_CURRENT) == "9.45 mA"
    assert src.text(LED_CURRENT, "%.1f mA") == "9.4 mA"           # scaled to the prefix of the format
    assert src.text("sim:min SIM.state */idle/* D2 LED dark", "%.0f nA") in {"21 nA", "26 nA", "20 nA"}
    src.decimal = ","                                          # [docs] decimal = "," for documents in German
    assert src.text(LED_CURRENT) == "9,45 mA" and src.text("graph:LED_OE.v") == "0 … 3,4 V"
    for bad, why in (("graph:R99.value", "no part, net or cable R99"), ("graph:R1.colour", "no key colour"),
                     ("part:C1.values.x", "no parts entry C1"), ("sim:max XYZ.none *", "no simulation row matches"),
                     ("sim:one SIM.state * D2 LED current*", "rows match, 'one' wants exactly one"),
                     ("sim:avg SIM.state *", "sim:max, sim:min or sim:one"), ("foo:bar", "unknown source")):
        with pytest.raises(docs.QuoteError, match=why):
            src.text(bad)


def test_an_unknown_designator_in_a_note_is_g19(project, monkeypatch, capsys):
    note(project, "R41 is {graph:R41.value}")
    monkeypatch.chdir(project.root)
    assert cli.main(["docs"]) == 2
    out = capsys.readouterr().out
    assert 'DOCS.quote  hardware/schematic.toml [layout.notes] "LED Driver": {graph:R41.value}: no part, net or cable R41' in out


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
    assert "DOCS.quote (documents quote the design data)" in protocol and "written 9.45 mA, now 4.02 mA" in protocol


def test_without_quotes_nothing_happens(project, monkeypatch, capsys):
    monkeypatch.chdir(project.root)
    assert cli.main(["docs"]) == 0 and "nothing quoted" in capsys.readouterr().out
    cfg = project.config()
    assert docs.stage_rows(cfg, Design.from_config(cfg), {"checks": []}) == []


# --- req: a need or requirement quoted by its ID (step 3.5) ------------------------------------------------------------
def test_a_block_quotes_a_requirement_by_its_id(project, monkeypatch, capsys):
    """Red before step 3.5: req: was an unknown source. A block quotes the text of a need or requirement of
    [project] requirements; edakit docs --write fills it in, and a text changed in the file makes the quote stale."""
    with_requirements(project)
    f = listed(project, "Power: <!--edakit req:R-1--><!--/edakit-->\nLight: <!--edakit req:N-2-->old<!--/edakit-->\n")
    monkeypatch.chdir(project.root)
    assert cli.main(["docs"]) == 2
    out = capsys.readouterr().out
    assert f"DOCS.quote  docs/values.md:1: req:R-1: written (empty), now {R1}" in out
    assert "DOCS.quote  docs/values.md:2: req:N-2: written old, now The LEDs can be read in a lit room." in out
    assert cli.main(["docs", "--write"]) == 0
    assert f.read_text() == (f"Power: <!--edakit req:R-1-->{R1}<!--/edakit-->\n"
                             "Light: <!--edakit req:N-2-->The LEDs can be read in a lit room.<!--/edakit-->\n")
    assert cli.main(["docs"]) == 0
    reqs = project.root / "hardware" / "requirements.toml"
    reqs.write_text(reqs.read_text().replace("at most 500 mA", "at most 400 mA"))
    capsys.readouterr()
    assert cli.main(["docs"]) == 2
    assert (f"DOCS.quote  docs/values.md:1: req:R-1: written {R1}, now {R1.replace('500', '400')}"
            in capsys.readouterr().out)


def test_req_quotes_drafts_but_not_dropped_entries(project):
    """A draft is quoted as it stands; a dropped entry no longer holds – like a part gone from the graph, quoting it is
    DOCS.quote; its text stays in the requirements file, edakit req shows it with the reason."""
    with_requirements(project)
    cfg = project.config()
    src = docs.Sources(cfg, Design.from_config(cfg))
    assert src.text("req:N-1") == "The bar runs from a USB charger or from the USB port of a laptop."
    assert src.text("req:R-4") == ("From power-up until the firmware drives LED_OE low, no LED carries more than "
                                   "10 µA.")                                    # a draft
    for bad, why in (("req:R-9", "no need or requirement R-9 in hardware/requirements.toml"),
                     ("req:R4", "'R4' is no ID of a need or requirement"),
                     ("req:N-4", "N-4 is dropped: the TLC5916 and the Pico 2 want 5 V")):
        with pytest.raises(docs.QuoteError, match=why):
            src.text(bad)


def test_without_the_key_req_is_g19_that_names_it(project, monkeypatch, capsys):
    listed(project, f"<!--edakit req:R-1-->{R1}<!--/edakit-->\n")
    monkeypatch.chdir(project.root)
    assert cli.main(["docs"]) == 2
    assert "DOCS.quote  docs/values.md:1: req:R-1: no [project] requirements in edakit.toml" in capsys.readouterr().out


def test_req_quotes_on_one_line_and_names_a_file_that_does_not_read(project):
    with_requirements(project, NEED.replace('text = "t"', 'text = """The bar\n   runs from USB."""'))
    cfg = project.config()
    assert docs.Sources(cfg, Design.from_config(cfg)).text("req:N-1") == "The bar runs from USB."   # a block is a line
    (project.root / "hardware" / "requirements.toml").write_text(REQUIREMENT.replace('binding = "must"\n', ""))
    with pytest.raises(docs.QuoteError, match=r"does not read: hardware/requirements.toml: R-1: binding is missing"):
        docs.Sources(cfg, Design.from_config(cfg)).text("req:R-1")


def test_a_schematic_note_quotes_a_requirement(project, tmp_path):
    with_requirements(project)
    note(project, "R-1: {req:R-1}")
    assert f"R-1: {R1}" in drawn_texts(project, tmp_path)


def test_gate_finds_a_stale_requirement_quote(project, monkeypatch):
    with_requirements(project)
    listed(project, "<!--edakit req:R-1-->at most 600 mA<!--/edakit-->\n")
    monkeypatch.chdir(project.root)
    cli.main(["gate"])
    protocol = next((project.root / "build" / "release").glob("*/protocol.md")).read_text()
    assert f"req:R-1: written at most 600 mA, now {R1}" in protocol
