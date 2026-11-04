"""T.2 of circuit-dsl-toolchain.md: tokens, statements, the model and the reader (language 3 and 5)."""

import pytest
from lang_examples import BELL_SMD, BELL_STEP, LED_BAR, REQUIREMENTS

from edakit.lang import model as m
from edakit.lang.reader import KEYWORDS, CompileError, check, read
from edakit.lang.tokens import statements, tokenize
from edakit.lang.units import Quantity


def errors(text, role="graph"):
    return [f"{e.line}: {e.text}" for e in read(text, "g.circuit", role).errors]


def one(text, cls, role="graph"):
    src = check(read(text, "g.circuit", role))
    assert len(src.statements) == 1 and isinstance(src.statements[0], cls), src.statements
    return src.statements[0]


# --- tokens and statements -------------------------------------------------------------------------------------------
def test_words_strings_groups_and_comments():
    lines, tail = tokenize('part U1 microcontroller "Raspberry Pi Pico 2" U1.3V3(OUT) (locked)  # the MCU\n')
    toks = lines[0].toks
    assert [t.kind for t in toks] == ["word", "word", "word", "string", "word", "group"]
    assert toks[3].value == "Raspberry Pi Pico 2" and toks[4].raw == "U1.3V3(OUT)" and toks[5].items == ["locked"]
    assert lines[0].comment.value == " the MCU" and tail == []


def test_a_string_over_lines_reads_as_one_space_and_keeps_its_line():
    lines, _ = tokenize('description "one\n    two \\"three\\""\npart R1 resistor')
    assert lines[0].toks[1].value == 'one two "three"' and lines[1].number == 3


def test_a_word_with_parentheses_is_one_word():
    lines, _ = tokenize("derive R.value series_resistor(i, led = D)\n")
    assert [t.raw for t in lines[0].toks] == ["derive", "R.value", "series_resistor(i, led = D)"]


def test_continuation_lines_and_bodies():
    text = "part U1 ic X\n  nc A\n  notes \"n\"\nfor n in 0..1\n  part R{n} resistor X\n    value 1k\nnet A\n"
    lines, _ = tokenize(text)
    sts = statements(lines)
    assert [s.keyword.raw for s in sts] == ["part", "for", "net"]
    assert len(sts[0].cont) == 2 and len(sts[1].body) == 1 and len(sts[1].body[0].cont) == 1


def test_blank_lines_and_comments_lead_the_next_line():
    lines, tail = tokenize("# head\n\npart R1 resistor X\n# end\n")
    assert lines[0].lead[0].value == " head" and lines[0].lead[1] == "" and tail[0].value == " end"


# --- the statements ----------------------------------------------------------------------------------------------------
def test_led_bar_reads_without_error():
    src = check(read(LED_BAR, "graph.circuit"))
    kinds = [type(s).__name__ for s in src.statements]
    assert kinds[:4] == ["GraphHead", "Description", "Purpose", "Convention"]
    assert kinds.count("Part") == 9 and kinds.count("Net") == 10 and kinds.count("For") == 1
    head = src.statements[0]
    assert (head.name, head.version, head.date) == ("led-bar", "1.0", "2026-10-25")
    u1 = next(s for s in src.statements if isinstance(s, m.Part) and s.des == "U1")
    assert u1.type == "microcontroller" and u1.part == "Raspberry Pi Pico 2" and u1.attr("lcsc") == "C41407547"
    assert u1.label == "Raspberry Pi Pico 2 (SMD module)" and len(u1.nc) == 33 and u1.nc[-1].word == "BOOTSEL"
    j1 = next(s for s in src.statements if isinstance(s, m.Part) and s.des == "J1")
    assert j1.attrs[:3] == [("lcsc", "C131337"), ("bom", False), ("source", "reversible")]
    sdi = next(s for s in src.statements if isinstance(s, m.Net) and s.name == "LED_SDI")
    assert sdi.v == Quantity(0, 3.4, "V") and [(p.word, p.locked) for p in sdi.pins] == [("U1.GP3", True),
                                                                                       ("U2.SDI", False)]
    assert sdi.attrs == [("fn", "spi.tx"), ("fn_bus", "LED")] and sdi.accepts[0].key == "LVL.undefined"
    loop = next(s for s in src.statements if isinstance(s, m.For))
    assert (loop.var, loop.start, loop.stop) == ("n", 0, 7) and len(loop.body) == 3
    cables = next(s for s in src.statements if isinstance(s, m.Set))
    assert (cables.key, cables.value) == ("cables", [])
    lay = [s for s in src.statements if isinstance(s, m.Layout)]
    assert [x.kind for x in lay] == ["fixed", "edge", "near", "note"] and lay[0].parts[-1] == "D9"


def test_the_bell_step_reads_its_definition_and_usages():
    src = check(read(BELL_STEP, "graph.circuit"))
    d = src.statements[0]
    assert isinstance(d, m.Def) and d.name == "led" and [a.name for a in d.params] == ["color", "i"]
    assert d.params[1].value == Quantity(0.01, 0.01, "A") and d.ports == [("in", None), ("gnd", None)]
    assert [type(b).__name__ for b in d.body] == ["Part", "Part", "Net", "Net", "Net", "Derive"]
    anode = d.body[3]
    assert anode.attrs == [("v", "@in")] and [p.word for p in anode.pins] == ["R.2", "D.anode"]
    der = d.body[5]
    assert der.targets == ["R.value"] and der.rule == "series_resistor" and der.args[0].text == "i"
    u = src.statements[1]
    assert isinstance(u, m.Use) and (u.definition, u.instance) == ("led", "step1")
    assert [(b.left, b.right) for b in u.bindings] == [("in", "LED_G1"), ("gnd", "GND"), ("anode", "LED_G1_A"),
                                                      ("R", "R4"), ("D", "LED5")]
    r = u.bindings[3].part
    assert r.part == "330 Ω 0805" and r.attr("lcsc") == "C17630" and r.attr("value") == "330Ω"
    assert r.label == "Series resistor LED5"
    d5 = u.bindings[4].part
    assert d5.part == "XL-504UGD" and d5.attr("bom") is False
    net = src.statements[3]
    assert net.v == "vlogic" and net.pins[0].locked


def test_a_variant_reads_its_body():
    src = check(read(BELL_SMD, "variants/smd/hardware/graph.circuit"))
    v = src.variant
    assert (v.name, v.base) == ("smd", "../../hardware/graph.circuit")
    assert [type(s).__name__ for s in v.body] == ["Description", "Part", "Part", "Use", "Use", "Accept"]
    assert v.body[1].attr("bom") is True and v.body[3].bindings[0].part.attr("bom") is True


def test_requirements_read_in_their_file():
    src = check(read(REQUIREMENTS, "hardware/requirements.circuit", "requirements"))
    need, r3, r7 = src.statements
    assert (need.id, need.who, need.status) == ("N-1", "owner", "accepted")
    assert (r3.id, r3.frm, r3.binding, r3.subject) == ("R-3", ["N-1"], "must", "led")
    assert r3.require == "D.i within 2 mA .. 15 mA"
    assert r3.verify == [("rows", "LIM.i *"), ("rows", "SIM.state *")] and r3.status == "accepted"
    assert r7.verify == [("signoff", "M-1")] and r7.frm == ["D-8"]


def test_each_statement_with_its_line():
    src = check(read(LED_BAR, "graph.circuit"))
    by = {(type(s).__name__, getattr(s, "des", getattr(s, "name", ""))): s.line for s in src.statements}
    assert by[("Part", "J1")] == 11 and by[("Net", "VIN")] == 32


def test_set_reaches_a_dotted_key_and_runs_over_lines():
    s = one('set locks.doc_pin_table {"component": "U1",\n  "file": "docs/pins.md"}\n', m.Set)
    assert s.key == "locks.doc_pin_table" and s.value == {"component": "U1", "file": "docs/pins.md"}


def test_part_attributes_and_line_keywords():
    p = one('part U1 module X lcsc C1 board main spare 1 off_board\n  pins 1=VCC 2=GND\n  alias led1 = PD6 led2 = PD5\n'
            '  accept LIM.v "on purpose"\n  set states {"GP0": "high"}\n  satisfies R-3 R-7\n', m.Part)
    assert p.attrs[:4] == [("lcsc", "C1"), ("board", "main"), ("spare", 1), ("off_board", True)]
    assert p.pins == [("1", "VCC"), ("2", "GND")] and p.aliases == [("led1", "PD6"), ("led2", "PD5")]
    assert p.accepts[0].reason == "on purpose" and ("set:states", {"GP0": "high"}) in p.attrs
    assert ("satisfies", ["R-3", "R-7"]) in p.attrs


def test_a_param_takes_a_quantity_or_a_word():
    assert one("param vlogic = 0..5.5 V\n", m.Param).value == Quantity(0, 5.5, "V")
    assert one("param color = green\n", m.Param).value == "green"


def test_keywords_are_language_5_12():
    assert {"graph", "part", "net", "use", "for", "variant", "need", "(locked)", "within"} <= KEYWORDS


# --- the errors --------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text, said", [
    ("wire A B\n", "1: wire: no statement"),
    ('description "open\n', "1: a string without its closing quote"),
    ("part R1\tresistor X\n", "1: a tab"),
    ("  part R1 resistor X\n", "1: a continuation line without a statement"),
    ("part\n", "1: part DES TYPE PARTNO"),
    ("net\n", "1: net NAME"),
    ("for n in 3..1\n  part R{n} resistor X\n", "1: for n in 3..1: B < A"),
    ("for n in 0..1\n  part R{m} resistor X\n", "2: {m}: the loop's variable is n"),
    ("for n in 0..1\n  part R{n/2} resistor X\n", "2: {n/2}: in a loop only"),
    ("for n in 0..1\n  for m in 0..1\n    part R1 resistor X\n", "2: for: not allowed here"),
    ("use led s1 in LED_G1\n", "1: use s1: in – a binding LEFT = RIGHT"),
    ("graph a\nvariant v of ../graph.circuit\n", "2: variant: the first statement of a variant file"),
    ("variant v of ../g.circuit\n  graph x\n", "2: graph: not in a variant"),
    ('need N-1 "x" who owner\n', "1: need: requirements stand in the file [project] requirements names"),
    ("part R1 resistor X valeu 1k\n", "1: unknown key 'valeu' – value?"),
    ("net A 10 mA R1.1\n", "1: net A: 10 mA: a voltage is expected"),
    ("net A 0..1 V R1.1\n  without R1.1\n", "2: net A: without"),
    ("waive LIM.v \"x\"\n", "1: waive: the form of before – now accept"),
    ("set nets.x {\n", "1: set nets.x: no valid JSON"),
    ("accept LIM.v\n", "1: accept LIM.v: the reason"),
    ("def led\n  wire A\n", "2: wire: no statement of a definition"),
    ("derive R.value series_resistor(i)\n", "1: derive: not allowed here"),
])
def test_the_errors_name_their_line(text, said):
    got = errors(text)
    assert any(e.startswith(said) for e in got), got


def test_a_requirements_file_holds_requirements_only():
    assert any("a requirements file holds need and requirement" in e for e in errors("part R1 resistor X\n",
                                                                                     "requirements"))


def test_check_raises_every_error_with_file_and_line():
    with pytest.raises(CompileError) as e:
        check(read("wire A\nnet\n", "hardware/graph.circuit"))
    assert str(e.value).splitlines() == ["hardware/graph.circuit:1: wire: no statement – one of graph, description, "
                                         "purpose, convention, ground, grounds, accept, lock, set, include, param, part,"
                                         " net, cable, layout, def, use, for, variant",
                                         "hardware/graph.circuit:2: net NAME [RANGE] PINWORD …"]
