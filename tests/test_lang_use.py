"""T.11 of circuit-dsl-toolchain.md: usages – a `use` becomes its definition's parts and nets (language 5.6), the
derivations evaluated at each usage (language 7)."""

import pytest
from lang_examples import BELL_STEP

from edakit.lang.compile import compile_path, resolved_of
from edakit.lang.reader import CompileError

HEAD = '''graph bell-step
part U1 module A000005 lcsc A000005 "Arduino Nano"
  alias led1 = D6 led2 = D5
net GND 0 V U1.GND
'''


def step(project, text=None, head=HEAD):
    """The bell's step with the library's entries: C17630 for the resistors, C2297 for the LEDs."""
    body = (text or BELL_STEP).replace("C2895549", "C2297").replace("XL-504UGD", "KT-0805G").replace(
        "vlogic", "0..5.5 V")
    path = project.root / "hardware" / "graph.circuit"
    for key in ("C17630", "C2297", "A000005"):
        project.use_library_part(key)
    path.write_text(head + body, encoding="utf-8")
    return path


def comp(g, des):
    return next(c for c in g["components"] if c["designator"] == des)


def net(g, name):
    return next(n for n in g["nets"] if n["name"] == name)


def test_the_bell_step_compiles_to_its_parts_and_nets(project):
    g = compile_path(step(project))
    r4, led5 = comp(g, "R4"), comp(g, "LED5")
    assert (r4["type"], r4["part"], r4["lcsc"], r4["value"], r4["label"]) == ("resistor", "330 Ω 0805", "C17630",
                                                                            "330Ω", "Series resistor LED5")
    assert (led5["type"], led5["value"], led5["bom"]) == ("led", "green", False)    # the definition's value, color
    assert net(g, "LED_G1_A")["pins"] == ["R4.2", "LED5.anode"]                     # named by the binding
    assert net(g, "LED_G1_A")["v"] == [0, 5.5]                                      # @in: the range of LED_G1
    assert net(g, "LED_G1")["pins"] == ["R4.1", "U1.D6"]                            # the port on the project's net
    assert "R3.1" in net(g, "LED_G2")["pins"] and "LED5.cathode" in net(g, "GND")["pins"]
    assert g["locks"]["pins"] == {"U1.D6": "LED_G1", "U1.D5": "LED_G2"}
    assert [c["designator"] for c in g["components"]] == ["U1", "R4", "LED5", "R3", "LED4"]


def test_the_derivation_of_each_usage(project):
    g, smap = resolved_of(step(project))
    recs = {r["part"]: r for r in g["derivations"]}
    assert set(recs) == {"R4", "R3"} and recs["R4"]["from"] == "def led, use step1"
    assert recs["R4"]["derived"] == {"value": 260, "unit": "Ω"}
    assert recs["R4"]["chosen"]["value"] == 330
    assert any(r["from"] == "net LED_G1 v[1]" for r in recs["R4"]["inputs"])
    assert smap.usages["step1"]["line"] > 0 and "R4.value" in smap.derivations


def test_an_internal_net_gets_the_instance_s_name(project):
    path = step(project, BELL_STEP.replace(" anode = LED_G1_A", ""))
    g = compile_path(path)
    assert net(g, "STEP1_ANODE")["pins"] == ["R4.2", "LED5.anode"]


def test_gnd_without_a_binding_joins_the_ground(project):
    g = compile_path(step(project, BELL_STEP.replace(" gnd = GND", "")))
    assert "LED5.cathode" in net(g, "GND")["pins"]


@pytest.mark.parametrize("change, said", [
    (lambda t: t.replace("in = LED_G1 ", ""), "use step1: port in of def led is not bound"),
    (lambda t: t.replace("  R = R4 ", "  X = R4 "), "use step1: X is no port, net or part of def led"),
    (lambda t: t.replace("(color = green)  in = LED_G1", "(colour = green)  in = LED_G1"),
     "use step1: def led has no parameter colour"),
    (lambda t: t.replace("R = R3", "R = R4"), "use step2: designator R4 is taken"),
    (lambda t: t.replace("  D = LED5 ", "  Q = LED5 ").replace('"5 mm LED, green, countdown step 1"', ""),
     "use step1: Q is no port"),
    (lambda t: t.replace("use led step1", "use lamp step1"), "use step1: no definition lamp"),
    (lambda t: t.replace("use led step2 (color = green)  in = LED_G2 gnd = GND anode = LED_G2_A\n", "use led step2 in = "
                         "LED_G2 gnd = GND anode = LED_G2_A without R\n"), "without R – no optional part of def led"),
])
def test_the_errors_name_the_usage(project, change, said):
    with pytest.raises(CompileError) as e:
        compile_path(step(project, change(BELL_STEP)))
    assert said in str(e.value), str(e.value)


def test_an_unbound_part_is_an_error(project):
    text = BELL_STEP.replace('  D = LED5 KT-0805G lcsc C2895549 no-bom "5 mm LED, green, countdown step 1"\n', "")
    text = text.replace('  D = LED5 XL-504UGD lcsc C2895549 no-bom "5 mm LED, green, countdown step 1"\n', "")
    with pytest.raises(CompileError, match="part D of def led is not bound"):
        compile_path(step(project, text))


def test_a_project_definition_shadows_the_library_s(project, capsys):
    from edakit.lang import compile as c
    c._SAID.clear()
    path = step(project)
    g = compile_path(path)
    assert comp(g, "R4")["type"] == "resistor"
    compile_path(path)
    assert capsys.readouterr().err.count("shadows edakit's block led") == 1   # said once, however often compiled


def test_a_library_block_is_used_by_name(project):
    head = HEAD + "net SIG 0..3.4 V U1.D7\n"
    text = ("use led status (i = 4 mA) in = SIG\n"
            "  R1 = R9\n"
            "  D1 = D9\n")
    for key in ("C17471",):
        project.use_library_part(key)
    g = compile_path(step(project, text, head))
    assert comp(g, "R9")["label"] == "status: LED series resistor" and comp(g, "R9")["lcsc"] == "C17471"
    assert net(g, "STATUS_ANODE")["v"] == [0, 3.4]
    [rec] = resolved_of(project.root / "hardware" / "graph.circuit")[0]["derivations"]
    assert rec["derived"]["value"] == 140 and rec["from"] == "def led, use status"


def test_an_optional_part_left_out(project):
    from edakit import block
    b = block.load("npn-switch")
    binds = " ".join(f"{c['designator']} = {c['designator']}9" for c in b["components"] if c["designator"] != "D1")
    ports = " ".join(f"{p} = LOAD" for p in b["ports"] if p not in ("in", "gnd"))
    for c in b["components"]:
        project.use_library_part(c["lcsc"])
    head = HEAD + "net SIG 0..3.4 V U1.D7\nnet LOAD 0..5.5 V\n"
    g = compile_path(step(project, f"use npn-switch sw in = SIG {ports} without D1\n  {binds}\n", head))
    assert not any(c["designator"] == "D19" for c in g["components"])
    assert "Q19" in {c["designator"] for c in g["components"]}
