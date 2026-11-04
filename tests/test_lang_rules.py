"""T.8 of circuit-dsl-toolchain.md: the derivation rules and their records (language 7), block add --set and --part,
edakit graph derive, and the engine DEF."""

import json
import math

import pytest
from helpers import check
from test_block import signals

from edakit import block, cli
from edakit.design import Design, load_parts
from edakit.lang.rules import RULES, RuleError, Scope, derive, describe, inputs_differ, refresh
from edakit.lang.units import parse

PARTS = load_parts("edakit/parts")


def scope(i="10 mA", v_on=5.5, r="C17630", led="C2297", chosen=True):
    return Scope(params={"i": (parse(i), "use step1 (i)")}, ports={"in": ("LED_G1", [0, v_on]), "gnd": ("GND", [0, 0])},
                 parts={"R": (r, PARTS.get(r), "resistor"), "D": (led, PARTS.get(led), "led")}, targets=["R"],
                 names={"R": "R4", "D": "LED5"}, origin="def led, use step1",
                 chosen={"R": (PARTS[r]["values"]["value_ohm"], "Ω", f"{r} values.value_ohm")} if chosen else {})


def test_series_resistor_with_c2297():
    [rec] = derive("series_resistor", [{"name": None, "text": "i"}], scope())
    assert rec["derived"] == {"value": 260, "unit": "Ω"}
    assert rec["series"] == {"name": "E24", "nearest": 270, "window": [240, 300]}
    vf = {r["name"]: r["value"] for r in rec["inputs"]}
    assert vf["vf_typ_v"] + vf["rs_ohm"] * (0.01 - vf["vf_at_a"]) == pytest.approx(2.90)
    assert rec["chosen"] == {"value": 330, "unit": "Ω", "from": "C17630 values.value_ohm"}
    assert rec["predicts"]["i"] == pytest.approx([0.0071, 0.0088], abs=5e-5)
    assert {r["from"] for r in rec["inputs"]} >= {"net LED_G1 v[1]", "C2297 values.vf_typ_v", "C17630 values.tolerance"}
    assert (rec["part"], rec["key"], rec["from"]) == ("R4", "value", "def led, use step1")


def test_divider_two_targets():
    s = Scope(params={"v_out": (parse("2.75 V"), "p"), "i": (parse("275 uA"), "p")},
              ports={"bat": ("+5V", [0, 5.5]), "gnd": ("GND", [0, 0])},
              parts={"R3": ("C17414", PARTS["C17414"], "resistor"), "R4": ("C17414", PARTS["C17414"], "resistor")},
              targets=["R3", "R4"], names={"R3": "R13", "R4": "R14"}, origin="block battery-sense, BAT",
              chosen={"R3": (10000.0, "Ω", "C17414 values.value_ohm"), "R4": (10000.0, "Ω", "C17414 values.value_ohm")})
    top, bottom = derive("divider", [{"name": None, "text": "v_out"}, {"name": None, "text": "i"},
                                     {"name": "in", "text": "bat"}], s)
    assert (top["output"], bottom["output"]) == ("top", "bottom")
    assert top["derived"]["value"] == pytest.approx(10000) and bottom["derived"]["value"] == pytest.approx(10000)
    assert top["predicts"]["v_out"] == pytest.approx([5.5 * 0.99 / 2, 5.5 * 1.01 / 2], rel=1e-3)


def test_pullup_with_the_i2c_table():
    s = Scope(params={}, ports={"vcc": ("3V3", [0, 3.3]), "sda": ("SDA", [0, 3.3])},
              parts={"R1": ("C17673", PARTS["C17673"], "resistor")}, targets=["R1"], names={"R1": "R5"},
              origin="block i2c-pullups, I2C", chosen={"R1": (4700.0, "Ω", "C17673 values.value_ohm")})
    [rec] = derive("pullup", [{"name": "v", "text": "vcc"}], s)
    r_min, r_max = (3.3 - 0.4) / 0.003, 10000
    assert rec["series"]["window"] == pytest.approx([r_min, r_max], rel=1e-5)
    assert rec["derived"]["value"] == pytest.approx(math.sqrt(r_min * r_max), rel=1e-5)
    [rec] = derive("pullup", [{"name": "v", "text": "vcc"}, {"name": "c_bus", "text": "100 pF"},
                              {"name": "t_rise", "text": "1 us"}], s)
    assert rec["series"]["window"][1] == pytest.approx(1e-6 / (0.8473 * 100e-12), rel=1e-5)


def test_rc_both_ways():
    s = Scope(params={}, ports={}, parts={"R1": (None, None, "resistor")}, targets=["R1"], names={"R1": "R1"},
              origin="t")
    [rec] = derive("rc", [{"name": "f_c", "text": "1 kHz"}, {"name": "c", "text": "100 nF"}], s)
    assert rec["derived"]["value"] == pytest.approx(1 / (2 * math.pi * 1000 * 100e-9), rel=1e-5)
    assert rec["series"]["name"] == "E24"
    [rec] = derive("rc", [{"name": "f_c", "text": "1 kHz"}, {"name": "r", "text": "1.6 kΩ"}], s)
    assert rec["derived"] == {"value": pytest.approx(1 / (2 * math.pi * 1000 * 1600), rel=1e-5), "unit": "F"}
    assert rec["series"]["name"] == "E6"


@pytest.mark.parametrize("change, said", [
    (dict(v_on=2.5), "v_on 2.5 V at or below the LED's vf"),
    (dict(i="0 mA"), "a current above 0"),
    (dict(led="C17414"), "has no values.vf_typ_v"),
])
def test_the_errors_have_the_numbers(change, said):
    with pytest.raises(RuleError, match=said):
        derive("series_resistor", [{"name": None, "text": "i"}], scope(**change))


def test_the_table_for_the_handbook():
    text = describe()
    assert all(f"`{r}`" in text for r in RULES) and text.startswith("| Rule |")


# --- the engine DEF ------------------------------------------------------------------------------------------------
def with_record(project, value="150"):
    signals(project)
    block.add(project.config(), "led", "STATUS", {"in": "SIG"}, sets={"i": "4mA"})
    g = project.graph()
    r = next(c for c in g["graph"]["components"] if c["designator"] == "R3")
    r["value"] = value
    project.save_graph(g)
    return g


def test_a_value_inside_the_window_is_no_finding(project):
    with_record(project)
    rep = check(Design.from_config(project.config()), project.config())
    assert not [w for w in rep.warnings if w[0] == "DEF.derive"]


def test_a_value_outside_the_window_is_def_derive(project):
    g = with_record(project)
    r = next(c for c in g["graph"]["components"] if c["designator"] == "R3")
    r["lcsc"], r["part"], r["value"] = "C17630", "0805W8F3300T5E", "330"
    project.save_graph(g)
    project.use_library_part("C17630")
    rep = check(Design.from_config(project.config()), project.config())
    found = [m for c, m in rep.warnings if c == "DEF.derive"]
    assert found and found[0].startswith("R3: value 330 Ω, derived 140 Ω by series_resistor (E24 150 Ω, window "
                                         "130 Ω…160 Ω)")


def test_an_entry_changed_after_the_record_is_def_derive_inputs(project):
    with_record(project)
    led = project.part("C2297")
    led["values"]["vf_typ_v"] = 2.8
    project.save_part("C2297", led)
    rep = check(Design.from_config(project.config()), project.config())
    found = [m for c, m in rep.warnings if c == "DEF.derive"]
    assert any("vf_typ_v 2.85 V from C2297 values.vf_typ_v – now 2.8" in m for m in found), found


def test_an_accept_on_the_component_silences_it(project):
    g = with_record(project)
    r = next(c for c in g["graph"]["components"] if c["designator"] == "R3")
    r["accept"] = {"DEF.derive": "chosen brighter on purpose"}
    r["lcsc"], r["part"], r["value"] = "C17630", "0805W8F3300T5E", "330"
    project.save_graph(g)
    project.use_library_part("C17630")
    rep = check(Design.from_config(project.config()), project.config())
    assert not [w for w in rep.warnings if w[0] == "DEF.derive"]


def test_inputs_differ_reads_the_sources(project):
    g = with_record(project)
    rec = g["graph"]["derivations"][0]
    assert inputs_differ(rec, Design.from_config(project.config())) == []


# --- block add --set and --part -------------------------------------------------------------------------------------
def run_add(project, *more):
    return cli.main(["block", "add", "led", "--as", "STATUS", "--connect", "in=SIG", *more, "--config",
                     str(project.root / "edakit.toml")])


def test_set_4ma_keeps_the_block_s_part_and_writes_the_record(project, capsys):
    signals(project)
    assert run_add(project, "--set", "i=4mA") == 0
    out = capsys.readouterr().out
    assert "R3: series_resistor derives 140Ω – E24 150Ω, window 130…160Ω; the block's 150Ω (C17471) fits – kept" in out
    g = project.graph()["graph"]
    [rec] = g["derivations"]
    assert rec["part"] == "R3" and rec["from"] == "block led, STATUS" and rec["chosen"]["value"] == 150
    assert next(c for c in g["components"] if c["designator"] == "R3")["lcsc"] == "C17471"


def test_set_10ma_stops_and_names_the_window(project, capsys):
    signals(project)
    before = project.graph_file.read_text()
    assert run_add(project, "--set", "i=10mA") == 1
    out = capsys.readouterr().out
    assert "derives 50Ω – E24 51Ω, window 47…56Ω" in out
    assert "no entry of the library in the window – part-search skill, then --part R1=KEY" in out
    assert project.graph_file.read_text() == before


def test_part_takes_an_entry_in_the_window(project, capsys):
    signals(project)
    assert run_add(project, "--set", "i=2mA") == 1
    out = capsys.readouterr().out
    assert "window 270…330Ω" in out and "C17590 270Ω, C17630 330Ω – --part R1=KEY" in out
    assert run_add(project, "--set", "i=2mA", "--part", "R1=C17630") == 0
    g = project.graph()["graph"]
    r3 = next(c for c in g["components"] if c["designator"] == "R3")
    assert (r3["lcsc"], r3["value"], r3["part"]) == ("C17630", "330", "0805W8F3300T5E")
    assert g["derivations"][0]["chosen"] == {"value": 330, "unit": "Ω", "from": "C17630 values.value_ohm"}
    assert (project.root / "hardware" / "parts" / "C17630.json").exists()


def test_dry_run_and_without_set(project, capsys):
    signals(project)
    before = project.graph_file.read_text()
    assert run_add(project, "--set", "i=4mA", "--dry-run") == 0
    assert project.graph_file.read_text() == before
    assert run_add(project, "--set", "x=1") == 1 and "has no parameter x" in capsys.readouterr().out
    assert run_add(project) == 0
    assert "derivations" not in project.graph()["graph"]


def test_block_add_set_on_a_toml_graph_writes_a_table(project):
    from test_graph_toml import to_toml
    signals(project)
    cfg = to_toml(project)
    block.add(cfg, "led", "STATUS", {"in": "SIG"}, sets={"i": "4mA"})
    text = cfg.graph.read_text()
    assert "\n[[derivations]]\npart = \"R3\"\n" in text
    from edakit.design import load_graph
    assert load_graph(cfg.graph)["derivations"][0]["rule"] == "series_resistor"


# --- edakit graph derive ----------------------------------------------------------------------------------------------
def test_graph_derive_reports_and_rewrites(project, capsys):
    with_record(project)
    args = ["graph", "derive", "--config", str(project.root / "edakit.toml")]
    assert cli.main(args) == 0 and "1 record current" in capsys.readouterr().out
    led = project.part("C2297")
    led["values"]["vf_typ_v"] = 2.8
    project.save_part("C2297", led)
    assert cli.main(args) == 0
    out = capsys.readouterr().out
    assert "R3: series_resistor (block led, STATUS) – inputs, derived" in out
    assert cli.main([*args, "--write"]) == 0
    rec = project.graph()["graph"]["derivations"][0]
    assert next(r for r in rec["inputs"] if r["name"] == "vf_typ_v")["value"] == 2.8
    new, changes = refresh(rec, Design.from_config(project.config()))
    assert changes == []


def test_graph_show_names_the_record(project, capsys):
    with_record(project)
    assert cli.main(["graph", "show", "R3", "--config", str(project.root / "edakit.toml")]) == 0
    assert "derived   value 140 Ω by series_resistor (block led, STATUS) – E24 150, window 130…160, chosen 150 Ω" in \
        capsys.readouterr().out
    assert json.dumps(1)
