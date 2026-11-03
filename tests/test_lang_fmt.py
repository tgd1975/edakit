"""T.5 of circuit-dsl-toolchain.md: edakit graph fmt – the canonical layout, idempotent, comments kept, the graph
unchanged."""

import pytest
from lang_examples import BELL_SMD, BELL_STEP, LED_BAR, REQUIREMENTS
from lang_project import as_fixture, flat, to_circuit

from edakit import cli
from edakit.graph_form import canonical
from edakit.lang.compile import resolved_of
from edakit.lang.fmt import WIDTH, format

MISALIGNED = '''\
# the board
graph  demo   version 1

part R1   resistor  X    value 1k     "pull-up"   # the pull-up
    notes   "a note"
part U1 ic Y lcsc C1 "the IC"
  # its unused pin
  nc   A    B



net  A   0..3.3 V   R1.1   U1.C
net B 0 V R1.2 U1.D fn pwm
  notes "{}"
'''.format("word " * 40)


@pytest.mark.parametrize("text", [LED_BAR, BELL_STEP, BELL_SMD, REQUIREMENTS, MISALIGNED])
def test_formatting_is_idempotent(text):
    once = format(text)
    assert format(once) == once
    assert all(len(ln) <= WIDTH or "#" in ln for ln in once.splitlines())


def test_led_bar_is_in_the_canonical_layout():
    assert format(LED_BAR) == LED_BAR


def test_the_misaligned_source_is_laid_out():
    out = format(MISALIGNED)
    lines = out.splitlines()
    assert lines[:2] == ["# the board", "graph demo version 1"]
    assert 'part R1 resistor X value 1k "pull-up"  # the pull-up' in lines
    assert "  notes \"a note\"" in lines
    assert lines[lines.index('part U1 ic Y lcsc C1 "the IC"') + 1:][:2] == ["  # its unused pin", "  nc A B"]
    assert "\n\n\n" not in out                                         # several blank lines as one
    notes = [ln for ln in lines if ln.startswith("  notes") or ln.startswith("    word")]
    assert len(notes) > 1                                                # a long string over several lines


def test_comments_are_kept_in_place_and_in_number():
    out = format(MISALIGNED)
    assert out.count("#") == MISALIGNED.count("#")
    assert out.index("# the board") < out.index("graph demo")


def test_the_formatted_source_compiles_to_the_same_graph(project):
    text = as_fixture(flat())
    messy = text.replace("part R2 resistor", "part   R2   resistor").replace("\nnet VIN", "\n\n\n\nnet VIN")
    cfg = to_circuit(project, messy)
    before = resolved_of(cfg.graph)[0]
    cfg.graph.write_text(format(messy), encoding="utf-8")
    assert canonical(resolved_of(cfg.graph)[0]) == canonical(before)


def test_a_part_with_its_attributes_on_the_head_and_its_lines_after_it():
    src = 'part U2 ic TLC5916IDR "TLC5916" lcsc C90107\n  notes "n"\n  function "sink"\n  nc SDO\n'
    assert format(src) == 'part U2 ic TLC5916IDR lcsc C90107 "TLC5916"\n  nc SDO\n  function "sink"\n  notes "n"\n'


def test_a_label_after_the_type_alone_stays_a_label():
    assert format('part D led\n  label "the LED"\n') == 'part D led label "the LED"\n'


def test_the_check_exit_codes(project, capsys):
    cfg = to_circuit(project)
    args = ["graph", "fmt", "--check", "--config", str(project.root / "edakit.toml")]
    assert cli.main(args) == 0 and "1 file in the canonical layout" in capsys.readouterr().out
    cfg.graph.write_text(cfg.graph.read_text().replace("part R2 resistor", "part  R2 resistor"))
    assert cli.main(args) == 2
    assert "hardware/graph.circuit:" in capsys.readouterr().out
    assert cli.main(["graph", "fmt", "--config", str(project.root / "edakit.toml")]) == 0
    assert cli.main(args) == 0


def test_files_named_are_formatted_where_their_project_switches_the_dsl_on(tmp_path, capsys):
    f = tmp_path / "x.circuit"
    f.write_text("part  R1 resistor X\n")
    assert cli.main(["graph", "fmt", "--check", str(f)]) == 1                 # no project: the beta is not on
    assert "[beta] dsl = true" in capsys.readouterr().err and f.read_text() == "part  R1 resistor X\n"
    (tmp_path / "edakit.toml").write_text('[project]\nname = "x"\n\n[beta]\ndsl = true\n')
    assert cli.main(["graph", "fmt", "--check", str(f)]) == 2
    assert cli.main(["graph", "fmt", str(f)]) == 0 and f.read_text() == "part R1 resistor X\n"


def test_a_set_of_json_too_long_for_a_line_is_one_member_to_a_line():
    import json

    from edakit.lang.reader import read
    long = "Wi-Fi channels 1-13 only " * 6
    text = ('graph demo\nset purpose.radio {"U1": {"bands_mhz": [[2412, 2472]], "notes": "' + long + '"}, '
            '"U2": {"bands_mhz": []}}\n')
    out = format(text)
    assert out.splitlines()[1:] == ['set purpose.radio {', '    "U1": {', '      "bands_mhz": [[2412, 2472]],',
                                    f'      "notes": "{long}"}},', '    "U2": {"bands_mhz": []}}']
    assert format(out) == out and read(out, "x").errors == []
    tail = "".join(out.splitlines()[1:])
    assert json.loads(tail[tail.index("{"):]) == json.loads(text.splitlines()[1].split(" ", 2)[2])
