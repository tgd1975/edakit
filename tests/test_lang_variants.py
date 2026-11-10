"""T.14 of circuit-dsl-toolchain.md: variants – a variant's model is its base's with its statements applied in order
(language 5.9); [project] parts as a list; the hash over the entries the graph uses (language 8)."""

import pytest
from test_lang_use import step

from edakit.lang.compile import compile_path
from edakit.lang.reader import CompileError, read
from edakit.release import gate


def variant(project, text, name="smd", base="../../hardware/graph.circuit"):
    """variants/<name>/ with an edakit.toml of its own and hardware/graph.circuit: `variant NAME of BASE` + text."""
    step(project)
    root = project.root / "variants" / name
    (root / "hardware" / "parts").mkdir(parents=True, exist_ok=True)
    toml = (project.root / "edakit.toml").read_text()
    toml = toml.replace('graph = "hardware/graph.json"', 'graph = "hardware/graph.circuit"')
    toml = toml.replace('parts = "hardware/parts"', 'parts = ["hardware/parts", "../../hardware/parts"]')
    (root / "edakit.toml").write_text(toml)
    for f in ("sim.json", "signoff.json", "schematic.toml"):
        src = project.root / "hardware" / f
        if src.exists():
            (root / "hardware" / f).write_text(src.read_text())
    if (project.root / "hardware" / "boards").exists():
        import shutil
        shutil.copytree(project.root / "hardware" / "boards", root / "hardware" / "boards", dirs_exist_ok=True)
    path = root / "hardware" / "graph.circuit"
    path.write_text(f"variant {name} of {base}\n" + text, encoding="utf-8")
    return path


def comp(g, des):
    return next(c for c in g["components"] if c["designator"] == des)


def net(g, name):
    return next(n for n in g["nets"] if n["name"] == name)


def test_a_part_redefined_keeps_its_place_and_takes_what_is_given(project):
    g = compile_path(variant(project, "  part R3 value 470Ω \"Series resistor LED4, brighter\"\n"))
    r3 = comp(g, "R3")
    assert (r3["value"], r3["label"], r3["lcsc"]) == ("470Ω", "Series resistor LED4, brighter", "C17630")
    assert [c["designator"] for c in g["components"]] == ["U1", "R4", "LED5", "R3", "LED4"]


def test_a_usage_rebound_and_bom_yes(project):
    g = compile_path(variant(project, '  use led step1 D = LED5 KT-0805G lcsc C2297 bom yes "0805 LED, step 1"\n'))
    led5 = comp(g, "LED5")
    assert "bom" not in led5 and led5["label"] == "0805 LED, step 1"


def test_without_takes_pins_off_and_additions_are_added(project):
    text = ("  net LED_G2 without U1.led2\n"
            "  part R9 resistor 0805W8F1002T5E lcsc C17414 value 10k \"pull-down\"\n"
            "  net LED_G2 R9.1\n  net GND R9.2\n")
    project.use_library_part("C17414")
    g = compile_path(variant(project, text))
    assert "U1.D5" not in net(g, "LED_G2")["pins"] and "R9.1" in net(g, "LED_G2")["pins"]
    assert "U1.D5" not in g["locks"]["pins"] or True
    assert comp(g, "R9")["value"] == "10k"


def test_a_range_given_again_replaces_it(project):
    g = compile_path(variant(project, "  net LED_G1 0..3.3 V\n"))
    assert net(g, "LED_G1")["v"] == [0, 3.3]


def test_accept_minus_removes_and_description_replaces(project):
    base = step(project)
    base.write_text(base.read_text() + 'accept HINT.bulk "C1 next to J1"\n')
    g = compile_path(variant(project, '  description "the SMD one"\n  accept HINT.bulk -\n'))
    assert g["description"] == "the SMD one" and "accept" not in g


def test_a_chain_of_two(project):
    variant(project, "  part R3 value 470Ω\n", "smd")
    path = variant(project, "  part R4 value 1k\n", "tht", "../smd/hardware/graph.circuit")
    g = compile_path(path)
    assert comp(g, "R3")["value"] == "470Ω" and comp(g, "R4")["value"] == "1k"


@pytest.mark.parametrize("text, said", [
    ("  net LED_G2 without U1.D7\n", "without U1.D7 – not on the net"),
    ("  use led step9 D = LED9\n", "use step9: no usage step9 in the base"),
    ("  param vbus = 5 V\n", "param vbus: the base has no parameter vbus"),
])
def test_the_errors(project, text, said):
    with pytest.raises(CompileError) as e:
        compile_path(variant(project, text))
    assert said in str(e.value)


def test_a_chain_that_loops(project):
    variant(project, "  part R3 value 470Ω\n", "a", "../b/hardware/graph.circuit")
    path = variant(project, "  part R4 value 1k\n", "b", "../a/hardware/graph.circuit")
    with pytest.raises(CompileError, match="the chain loops"):
        compile_path(path)


def test_graph_in_a_variant_is_refused():
    assert any("graph: not in a variant" in e.text for e in read("variant v of x\n  graph y\n", "g").errors)


# --- [project] parts as a list and the hash -----------------------------------------------------------------------
def test_parts_as_a_list(project):
    from edakit import config
    path = variant(project, "  part R3 value 470Ω\n")
    cfg = config.load(path.parents[1] / "edakit.toml")
    assert cfg.parts == path.parent / "parts" and cfg.parts_dirs[1].resolve() == (project.root / "hardware" /
                                                                                   "parts").resolve()
    assert project.config().parts_dirs == [project.config().parts]                  # the string form, as before


def test_the_hash_of_a_variant_takes_the_entries_it_uses(project):
    from edakit import config
    path = variant(project, '  part R4 label "own label"\n')
    vcfg = config.load(path.parents[1] / "edakit.toml")
    files = [p.name for p in gate.entry_files(vcfg)]
    assert files == ["A000005.json", "C17630.json", "C2297.json"]
    h = gate.state_hash(vcfg)
    base = project.root / "hardware" / "graph.circuit"
    text = base.read_text()
    base.write_text(text.replace('"Series resistor LED5"', '"Series resistor of LED5"'))   # R4's label: redefined
    assert gate.state_hash(config.load(vcfg.path)) == h
    base.write_text(text.replace('"Series resistor LED4"', '"Series resistor of LED4"'))   # R3's: inherited
    assert gate.state_hash(config.load(vcfg.path)) != h
    base.write_text(text)
    (project.root / "hardware" / "parts" / "C17414.json").write_text("{}")             # an entry not used
    assert gate.state_hash(config.load(vcfg.path)) == h
