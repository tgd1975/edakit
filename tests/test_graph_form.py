"""edakit graph json and edakit graph convert (circuit-language plan, steps L.5 and L.6): the resolved graph as JSON –
pin numbers, every pin map, the lists in the order of the file –, generated beside a TOML graph and checked for drift;
a JSON project moved to hardware/graph.toml once, its sign-offs of scope circuit carried over. The touchstone of the
sketch: led-bar and the reference circuits converted in a scratch copy, edakit graph json equal to the graph before,
edakit check with the same findings."""

import json
import tomllib

import pytest
from test_graph_toml import to_toml
from test_pin_words import named

import reference
from edakit import cli, scripts, toml_edit
from edakit.design import load_graph
from edakit.graph_form import PIN_REFERENCE
from edakit.release import gate


def run(project, *argv):
    return cli.main(["graph", *argv, "--config", str(project.root / "edakit.toml")])


def printed(project, capsys):
    """The graph edakit graph json prints."""
    capsys.readouterr()
    assert run(project, "json") == 0
    return json.loads(capsys.readouterr().out)


def canonical(data):
    """The graph with the arrangement no check reads taken out (circuit-language decision 2, gate.arranged): keys
    sorted, components and nets sorted, the pins of a net sorted – U1.GND stands for its pins where it stands."""
    return json.dumps(gate.arranged(data.get("graph", data)), sort_keys=True, ensure_ascii=False)


def checked(project, capsys):
    capsys.readouterr()
    code = cli.main(["check", "--config", str(project.root / "edakit.toml")])
    return code, capsys.readouterr().out


# --- L.5 edakit graph json -------------------------------------------------------------------------------------------
def test_graph_json_prints_a_json_graph_as_it_is_with_numbers(project, capsys):
    assert printed(project, capsys) == project.graph()


def test_graph_json_resolves_names_roles_and_the_entry_maps(project, capsys):
    """led-bar by names and roles, no component with a pin map: graph json gives the numbers and maps of today's
    file – the pins of a net in the order the words stand, U1.GND's in the entry's order."""
    original = project.graph()
    named(project, maps=False)
    out = printed(project, capsys)
    assert canonical(out) == canonical(original)
    assert list(out) == ["graph"] and out["graph"]["components"][2]["pins"] == original["graph"]["components"][2]["pins"]
    assert list(out["graph"]["components"][0]) == list(original["graph"]["components"][0])   # pins where they were


def test_graph_json_of_a_toml_graph(project, capsys):
    original = project.graph()
    named(project, maps=False)
    to_toml(project)
    out = printed(project, capsys)
    assert canonical(out) == canonical(original)
    assert [c["designator"] for c in out["graph"]["components"]] == [c["designator"] for c in
                                                                    original["graph"]["components"]]
    assert "board" not in out["graph"]["components"][0]            # nothing the Design adds


def test_write_and_check_find_drift(project, capsys):
    """As edakit firmware --check: exit 2 while the generated file is missing or differs, with what differs; --check
    writes nothing. A rewire through a parts entry shows in the generated file, not in the TOML (decision 4)."""
    named(project, maps=False)
    cfg = to_toml(project)
    out = project.root / "hardware" / "graph.json"
    assert run(project, "json", "--check") == 2 and "not written yet" in capsys.readouterr().out
    assert run(project, "json", "--write") == 0 and out.exists()
    assert "hardware/graph.json written" in capsys.readouterr().out
    assert run(project, "json", "--check") == 0 and "is current" in capsys.readouterr().out
    text = cfg.graph.read_text(encoding="utf-8")
    cfg.graph.write_text(text.replace('"U2.OUT0", "D2.cathode"', '"U2.OUT1", "D2.cathode"'), encoding="utf-8")
    written = out.read_text(encoding="utf-8")
    assert run(project, "json", "--check") == 2
    report = capsys.readouterr().out
    assert "drift" in report and "nets.LED0.pins" in report and '"U2.5"' in report and '"U2.6"' in report
    assert out.read_text(encoding="utf-8") == written                  # --check writes nothing
    cfg.graph.write_text(text, encoding="utf-8")
    led = project.part("C2297")                                       # the LED's anode found on pad 2
    led["pins"]["1"]["role"], led["pins"]["2"]["role"] = "cathode", "anode"
    project.save_part("C2297", led)
    assert cfg.graph.read_text(encoding="utf-8") == text
    assert run(project, "json", "--check") == 2
    report = capsys.readouterr().out
    assert "nets.LED0.pins" in report and '"D2.2"' in report and '"D2.1"' in report


def test_the_generated_file_keeps_its_indent_and_takes_the_entry_maps(project, capsys):
    named(project, maps=False)
    to_toml(project)
    out = project.root / "hardware" / "graph.json"
    out.write_text("{\n    \"graph\": {}\n}\n", encoding="utf-8")
    assert run(project, "json", "--write") == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith('{\n    "graph": {\n        "name": "led-bar"') and text.endswith("}\n")
    u1 = next(c for c in json.loads(text)["graph"]["components"] if c["designator"] == "U1")
    assert u1["pins"]["9"] == "GP6" and len(u1["pins"]) == 49 and u1["pins"]["TP1"] == "GND (USB)"


def test_never_over_a_json_source(project, capsys):
    before = project.graph_file.read_bytes()
    assert run(project, "json", "--write") == 1
    assert "hardware/graph.json is the graph itself" in capsys.readouterr().err
    assert run(project, "json", "--check") == 0
    assert "nothing is generated from a JSON graph" in capsys.readouterr().out
    assert project.graph_file.read_bytes() == before


def test_the_generated_file_is_derived(project, capsys):
    """Not in the circuit hash, not the data name graph of the scripts: graph stays the TOML source."""
    cfg = to_toml(project)
    h, data = gate.state_hash(cfg), scripts.data_hash(cfg, "graph")
    out = project.root / "hardware" / "graph.json"
    assert run(project, "json", "--write") == 0
    assert out not in gate.state_files(cfg)
    assert gate.state_hash(cfg) == h and scripts.data_hash(cfg, "graph") == data
    out.write_text(out.read_text(encoding="utf-8").replace('"U1.4"', '"U1.3"'), encoding="utf-8")
    assert gate.state_hash(cfg) == h and scripts.data_hash(cfg, "graph") == data
    key, why = scripts._Names(cfg).parse("hardware/graph.json")
    assert key == ("file", "hardware/graph.json") and why is None
    assert scripts._Names(cfg).parse("hardware/graph.toml")[0] == ("graph", None)


def test_graph_show_still_wants_a_name(project, capsys):
    assert run(project, "show") == 1 and "a designator or a net name" in capsys.readouterr().err
    assert run(project, "show", "R1") == 0 and "R1" in capsys.readouterr().out


# --- L.6 edakit graph convert: the touchstone -------------------------------------------------------------------------
def converted(project, capsys):
    """Converts the project; (graph json before, check before) to compare with."""
    before, check = printed(project, capsys), checked(project, capsys)
    assert run(project, "convert") == 0
    return before, check


def expected(before):
    """The graph before, with the convention the conversion rewrites."""
    g = json.loads(json.dumps(before))
    g["graph"].get("conventions", {}).update({"pin_reference": PIN_REFERENCE} if "pin_reference" in
                                             g["graph"].get("conventions", {}) else {})
    return g


def same_after(project, capsys, before, check):
    """graph json equals the graph before (canonically), the generated file is current, edakit check finds the same."""
    assert canonical(printed(project, capsys)) == canonical(expected(before))
    assert canonical(json.loads((project.root / "hardware" / "graph.json").read_text())) == canonical(expected(before))
    assert run(project, "json", "--check") == 0
    assert checked(project, capsys) == check


def test_convert_led_bar(project, capsys):
    toml_before = (project.root / "edakit.toml").read_text()
    before, check = converted(project, capsys)
    out = capsys.readouterr().out
    assert "hardware/graph.toml written" in out and "hardware/graph.json written" in out
    assert (project.root / "edakit.toml").read_text() == toml_before.replace(
        'graph = "hardware/graph.json"    # the single', 'graph = "hardware/graph.toml"    # the single')
    assert project.config().graph == project.root / "hardware" / "graph.toml"
    same_after(project, capsys, before, check)
    text = (project.root / "hardware" / "graph.toml").read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert "pins" not in data["components"]["U1"] and "pins" not in data["components"]["D2"]   # the entries' maps
    assert data["nets"]["GND"]["pins"] == ["J1.2", "U2.GND", "R1.2", "C1.2", "C2.2", "SW1.C", "U1.GND", "U1.AGND"]
    assert data["nets"]["LED0"]["pins"] == ["U2.OUT0", "D2.cathode"]
    assert data["nets"]["VIN"]["pins"] == ["J1.1", "D1.anode"]
    assert data["locks"]["pins"] == {"U1.GP2": "LED_CLK", "U1.GP3": "LED_SDI", "U1.GP4": "LED_LE", "U1.GP5": "LED_OE",
                                     "U1.GP6": "BTN"}
    assert {"GP0", "SWCLK", "BOOTSEL", "TP1", "TP4"} <= set(data["components"]["U1"]["nc"])   # TP1 "GND (USB)": no word
    assert data["conventions"]["pin_reference"] == PIN_REFERENCE
    assert '\n[components.U1]\ntype = "microcontroller"\n' in text and '\n[nets."+5V"]\n' in text
    assert 'description = """\\\n' in text                          # a long string over several lines
    assert all(len(line) <= 120 for line in text.splitlines() if not line.startswith(("pins = ", "nc = ")))
    assert [c for c in data["components"]] == [c["designator"] for c in before["graph"]["components"]]


@pytest.mark.parametrize("name", sorted(reference.REFERENCES))
def test_convert_the_reference_circuits(tmp_path, capsys, name):
    project = reference.write_one(tmp_path / name, name)
    before, check = converted(project, capsys)
    same_after(project, capsys, before, check)


@pytest.mark.parametrize("name", ["led-bar", *sorted(reference.REFERENCES)])
def test_convert_a_graph_written_with_words(tmp_path, capsys, name):
    """A JSON graph that names its pins by name or role already (L.1) converts to the same TOML as one with numbers."""
    plain = reference.write_one(tmp_path / "numbers", name)
    words = reference.write_one(tmp_path / "words", name)
    g = words.graph()
    cfg = words.config()
    from edakit.design import Design
    d = Design.from_config(cfg)
    for net in g["graph"]["nets"]:
        net["pins"] = [f"{r.partition('.')[0]}.{d.word(*r.split('.', 1))}" for r in net["pins"]]
    words.save_graph(g)
    for p in (plain, words):
        before, check = converted(p, capsys)
        same_after(p, capsys, before, check)
    assert (words.root / "hardware" / "graph.toml").read_text() == (plain.root / "hardware" / "graph.toml").read_text()


def every_field(project):
    """led-bar with what it does not use (a cable: the reference circuit cables): loops by words, ground and grounds,
    accepts, a pin map of its own, parts without entry with and without a map, a lock off its net, values that are no
    strings, quotes, backslashes, tabs, DEL and line breaks, long lines of text, one starting with blanks."""
    g = project.graph()
    gr = g["graph"]
    gr["ground"], gr["grounds"] = "GND", ["AGND"]
    gr["accept"] = {"HINT.bulk J1": 'C2 "10 µF" next to J1 \\ the board\'s input'}
    gr["description"] = "Line one.\nLine two\twith a tab, a quote \" and a backslash \\ – " + "long " * 40 + "end."
    gr["purpose"]["notes"] = "  two blanks first, " + "then  two between " * 10 + "and DEL \x7f at the end \\"
    gr["purpose"]["radio"] = {"U1": "off"}
    gr["layout"]["loops"] = [{"a": "C1.1", "b": "U2.16", "max_mm": 8, "what": "the TLC's supply"}]
    gr["layout"]["notes"].append("x" * 200)
    gr["locks"]["pins"]["U2.14"] = "LED_SDI"                     # a lock off its net: STRUCT.lock reports it
    comps = {c["designator"]: c for c in gr["components"]}
    comps["R2"]["pins"] = {"1": "A", "2": "B"}                  # a map of its own: kept, STRUCT.entry reports it
    comps["R1"]["accept"] = {"STRUCT.identity": "x", "LIM.p/margin": "a long reason " * 12}
    comps["C1"]["states"] = {"x": 1.5e-06, "y": [1, 2.0, True, {"z": "w"}], "e": {}}
    gr["components"].append({"designator": "TP1", "type": "testpoint", "part": "pad", "bom": False,
                             "pins": {"1": "TP"}, "notes": "no entry, a map"})
    gr["components"].append({"designator": "TP2", "type": "testpoint", "part": "pad2", "bom": False})
    gr["nets"].append({"name": "TEST", "pins": ["TP1.1", "TP2.1"], "v": [0, 3.4], "pwm_hz": [100, 200.5],
                       "notes": "A net\nover two lines"})
    gr["nets"][0]["accept"] = {}
    project.save_graph(g)


def test_convert_every_field(project, capsys):
    every_field(project)
    before, check = converted(project, capsys)
    same_after(project, capsys, before, check)
    data = tomllib.loads((project.root / "hardware" / "graph.toml").read_text(encoding="utf-8"))
    assert data["components"]["R2"]["pins"] == {"1": "A", "2": "B"} and data["components"]["TP1"]["pins"] == {"1": "TP"}
    assert "pins" not in data["components"]["TP2"]
    assert data["layout"]["loops"][0] == {"a": "C1.1", "b": "U2.VDD", "max_mm": 8, "what": "the TLC's supply"}
    assert data["locks"]["pins"]["U2.SDO"] == "LED_SDI"


def test_convert_writes_its_values_as_block_add_does(project, capsys):
    """One TOML value writer (toml_edit.literal) for convert and block add: every line of the converted graph within
    the width, but for a text that cannot be broken – one word of 200 letters, a text that starts with blanks."""
    every_field(project)
    converted(project, capsys)
    text = (project.root / "hardware" / "graph.toml").read_text(encoding="utf-8")
    assert [ln.strip()[:24] for ln in text.splitlines() if len(ln) > toml_edit.WIDTH] == [
        'notes = "  two blanks fi', '"' + "x" * 23]
    data = tomllib.loads(text)
    for k, v in [("description", data["description"]), ("notes", data["components"]["U1"]["notes"])]:
        assert text.count(toml_edit.line(k, v)) == 1           # the same literal block add would write


def written_by(entry_pins, refs, anywhere=True, kind="ic"):
    from edakit.design import Design
    from edakit.graph_form import written
    parts = {"C1": {"kind": kind, "pins": entry_pins}}
    d = Design.from_data({"components": [{"designator": "U1", "lcsc": "C1"}], "nets": []}, parts)
    return written(d, refs, anywhere)


def test_a_shared_name_is_written_once_where_its_first_pin_stands():
    pins = {"1": {"name": "GND"}, "2": {"name": "VA", "role": "pwr"}, "3": {"name": "GND"}, "4": {"name": "V B",
                                                                                                 "role": "pwr"}}
    assert written_by(pins, ["U1.3", "X.1", "U1.1"]) == ["U1.GND", "X.1"]            # wherever they stand, in a net
    assert written_by(pins, ["U1.3", "X.1"]) == ["U1.3", "X.1"]                       # one of them: its number
    assert written_by(pins, ["U1.3", "U1.1"], anywhere=False) == ["U1.3", "U1.1"]     # nc: only a run in order
    assert written_by(pins, ["U1.1", "U1.3"], anywhere=False) == ["U1.GND"]
    assert written_by(pins, ["U1.1", "U1.3", "U1.1"]) == ["U1.1", "U1.3", "U1.1"]     # a pin twice: as it is
    # pin 2 has a name of its own; pin 4 has no word for a name, and the role it shares with 2 is no group any more
    assert written_by(pins, ["U1.2", "U1.4"]) == ["U1.VA", "U1.4"]
    assert written_by(pins, ["U1.4", "U1.2"]) == ["U1.pwr"]                           # both by the role, at 4's place
    assert written_by({"1": {"name": "A", "role": "a"}, "2": {"name": "B", "role": "a"}}, ["U1.2", "U1.1"],
                      kind="button") == ["U1.a"]                                      # a button's side: its role


def test_set_graph_keeps_the_comment_or_adds_the_line():
    from edakit.graph_form import set_graph
    text = '# top\n[project]\nname = "x"   # the name\ngraph = "hardware/graph.json"  # the circuit\n\n[boards.main]\n'
    assert set_graph(text, "hardware/graph.toml") == text.replace("graph.json\"  #", "graph.toml\"  #")
    text = '[project]\nname = "x"   # the name\nquantity = 5\n\n# boards\n[boards.main]\ntitle = "y"\n'
    assert set_graph(text, "hardware/graph.toml") == text.replace("quantity = 5\n",
                                                                   'quantity = 5\ngraph = "hardware/graph.toml"\n')


def test_convert_carries_the_circuit_sign_offs_of_the_signed_files(project, capsys):
    cfg = project.config()
    signed = gate.state_hash(cfg)
    s = json.loads(cfg.signoff.read_text())
    cfg.signoff.write_text(json.dumps({**s, "state_sha256": signed}, indent=2) + "\n")
    assert run(project, "convert") == 0
    assert "the sign-offs of scope 'circuit' keep counting" in capsys.readouterr().out
    cfg = project.config()
    s = json.loads(cfg.signoff.read_text())
    assert s["state_sha256"] == gate.state_hash(cfg) != signed
    assert s["rehashed"][-1]["state_sha256"] == [signed, s["state_sha256"]]
    assert s["rehashed"][-1]["by"] == "edakit graph convert" and "hardware/graph.toml" in s["rehashed"][-1]["why"]


def test_convert_carries_nothing_signed_for_another_state(project, capsys):
    cfg = project.config()
    s = json.loads(cfg.signoff.read_text())
    cfg.signoff.write_text(json.dumps({**s, "state_sha256": "0" * 64}, indent=2) + "\n")
    assert run(project, "convert") == 0
    assert "keep counting" not in capsys.readouterr().out
    assert json.loads(cfg.signoff.read_text())["state_sha256"] == "0" * 64


def test_convert_dry_run_writes_nothing(project, capsys):
    files = {p: p.read_bytes() for p in project.root.rglob("*") if p.is_file()}
    assert run(project, "convert", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "[components.U1]" in out and "would write hardware/graph.toml" in out
    assert 'would set [project] graph = "hardware/graph.toml" in edakit.toml' in out
    assert {p: p.read_bytes() for p in project.root.rglob("*") if p.is_file()} == files


def test_convert_has_nothing_to_do_on_a_toml_graph(project, capsys):
    to_toml(project)
    assert run(project, "convert") == 0
    assert "hardware/graph.toml is TOML already – nothing to convert" in capsys.readouterr().out


def test_convert_refuses_what_toml_cannot_hold_and_writes_nothing(project, capsys):
    toml = (project.root / "edakit.toml").read_text()
    (project.root / "hardware" / "graph.toml").write_text("# there\n")
    assert run(project, "convert") == 1 and "hardware/graph.toml is there already" in capsys.readouterr().err
    (project.root / "hardware" / "graph.toml").unlink()
    g = project.graph()
    g["graph"]["components"].append(dict(g["graph"]["components"][-1]))   # SW1 twice
    g["graph"]["nets"][0]["pins"].append("U2.99")
    g["graph"]["nets"][1]["notes"] = None
    project.save_graph(g)
    before = project.graph_file.read_bytes()
    assert run(project, "convert") == 1
    err = capsys.readouterr().err
    assert "components: SW1 twice" in err and "net VIN: U2.99 names no pin of U2" in err
    assert "nets.+5V.notes: null – TOML has none" in err
    assert "fix the JSON first" in err
    assert project.graph_file.read_bytes() == before and (project.root / "edakit.toml").read_text() == toml
    assert not (project.root / "hardware" / "graph.toml").exists()


def test_a_converted_graph_reads_back_through_load_graph(project, capsys):
    """What convert writes is the TOML form of L.3, read by load_graph."""
    assert run(project, "convert") == 0
    g = load_graph(project.root / "hardware" / "graph.toml")
    assert g["nets"][2]["name"] == "GND" and "U1.GND" in g["nets"][2]["pins"]
