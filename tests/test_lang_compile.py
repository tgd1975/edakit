"""T.4 of circuit-dsl-toolchain.md: the compiler for flat statements – led-bar's source compiles to its graph, every
error with file and line (language 6 and 12, item 17)."""

import json

import pytest
from lang_project import as_fixture, fixture_graph, flat, to_circuit

from edakit.firmware import differences
from edakit.graph_form import canonical, keyed
from edakit.lang.compile import compile_path, project_of, resolved_of
from edakit.lang.reader import CompileError
from edakit.release import gate


def test_led_bar_compiles_canonically_equal_to_its_graph(project):
    want = fixture_graph(project)
    cfg = to_circuit(project)
    got, smap = resolved_of(cfg.graph)
    assert canonical(got) == canonical(want), differences(keyed(gate.arranged(want)), keyed(gate.arranged(got)))
    assert f"hardware/graph.circuit:{smap.components['J1']['line']}" == at(cfg.graph, "part J1")
    assert f"hardware/graph.circuit:{smap.nets['VIN']['line']}" == at(cfg.graph, "net VIN") and "U1.GP3" in smap.locks


def test_the_graph_keeps_today_s_key_order_and_the_words_as_written(project):
    cfg = to_circuit(project)
    g = compile_path(cfg.graph)
    assert list(g) == ["name", "version", "date", "description", "purpose", "conventions", "components", "nets",
                       "cables", "layout", "locks"]
    u2 = next(c for c in g["components"] if c["designator"] == "U2")
    assert list(u2)[:5] == ["designator", "type", "label", "part", "lcsc"] and u2["nc"] == ["SDO"]
    assert "pins" not in u2                                    # the entry's map, as a TOML graph without one
    sdi = next(n for n in g["nets"] if n["name"] == "LED_SDI")
    assert sdi["pins"] == ["U1.GP3", "U2.SDI"] and sdi["v"] == [0, 3.4]
    assert g["locks"]["pins"]["U1.GP3"] == "LED_SDI"


def test_project_of_finds_edakit_toml_upward(project):
    cfg = to_circuit(project)
    root, parts = project_of(cfg.graph)
    assert root == project.root.resolve() and parts == [project.root.resolve() / "hardware" / "parts"]


def src(project, change):
    cfg = to_circuit(project, as_fixture(change(flat())))
    return cfg.graph


def at(path, needle):
    """hardware/graph.circuit:LINE of the first line holding the needle."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return f"hardware/graph.circuit:{next(i for i, ln in enumerate(lines, 1) if needle in ln)}"


def errors(project, change):
    path = src(project, change)
    with pytest.raises(CompileError) as e:
        compile_path(path)
    return path, [str(x) for x in e.value.errors]


@pytest.mark.parametrize("change, needle, said", [
    (lambda t: t.replace("U1.GP6 (locked) SW1.A", "U1.GP6 (locked) SW9.A"), "net BTN", "SW9.A: no part SW9"),
    (lambda t: t.replace("U2.R-EXT R1.1", "U2.R-EXTRA R1.1"), "net REXT",
     "U2.R-EXTRA: names no pin of U2 – its pins: GND, SDI, CLK"),
    (lambda t: t.replace("U2.R-EXT R1.1", "U2.R-EXT R1.1 SW1.A"), "net REXT",
     "SW1.A: SW1.1 in net REXT and in BTN – first at {net BTN}"),
    (lambda t: t.replace("  nc SDO\n", "  nc SDO OUT0\n"), "  nc SDO OUT0", "U2.OUT0: in nc of U2 and in net LED0"),
    (lambda t: t.replace("net REXT 0..1.3 V", "net REXT 0..1.3 mA"), "net REXT",
     "net REXT: 0..1.3 mA: a voltage is expected"),
    (lambda t: t.replace("lcsc C90107", "lcsc C99999999"), "U2.SDI",
     "U2.SDI: U2 has no parts entry (C99999999) – edakit part add C99999999, write the pin's number"),
    (lambda t: t.replace("part C1 capacitor", "part R2 capacitor"), "part R2 capacitor",
     "part R2 twice – first at {part R2 resistor}"),
    (lambda t: t + "net REXT 0..1.3 V\n", "net REXT 0..1.3 V\n", "net REXT: the range given twice – first at {net REXT}"),
])
def test_the_errors_with_file_and_line(project, change, needle, said):
    path, got = errors(project, change)
    text = path.read_text(encoding="utf-8")
    line = at(path, needle) if not needle.endswith("\n") else f"hardware/graph.circuit:{text.count(chr(10))}"
    for ref in ("net BTN", "part R2 resistor", "net REXT"):
        said = said.replace("{" + ref + "}", at(path, ref))
    assert f"{line}: {said}" in "\n".join(got), got


def test_a_part_without_an_entry_compiles_with_numbers(project):
    path = src(project, lambda t: t.replace("lcsc C17604", "lcsc C99999999"))
    g = compile_path(path)
    assert any(c.get("lcsc") == "C99999999" for c in g["components"])


def test_a_compile_error_stops_load_graph_as_a_broken_toml_graph(project):
    from edakit.config import ConfigError
    from edakit.design import load_graph
    path = src(project, lambda t: t.replace("SW1.A", "SW9.A"))
    with pytest.raises(ConfigError, match=r"hardware/graph.circuit:\d+: SW9.A: no part SW9"):
        load_graph(path)


def test_aliases_are_replaced_before_the_design_reads_the_words(project):
    path = src(project, lambda t: t.replace("  nc SDO\n", "  nc SDO\n  alias serial = SDI\n")
               .replace("U2.SDI fn spi.tx", "U2.serial fn spi.tx"))
    g = compile_path(path)
    sdi = next(n for n in g["nets"] if n["name"] == "LED_SDI")
    assert sdi["pins"] == ["U1.GP3", "U2.SDI"]
    path.write_text(path.read_text().replace("U2.serial fn", "U2.serail fn"))
    with pytest.raises(CompileError, match=r"U2.serail: names no pin of U2 – its pins: .*serial \(alias\)"):
        compile_path(path)


def test_two_compiles_give_the_same_bytes(project):
    cfg = to_circuit(project)
    a = json.dumps(resolved_of(cfg.graph)[0], ensure_ascii=False)
    b = json.dumps(resolved_of(cfg.graph)[0], ensure_ascii=False)
    assert a == b
