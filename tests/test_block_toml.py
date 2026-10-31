"""block add on a TOML graph (circuit-language plan, L.7): a line editor that keeps comments and arrangement – a new
component table after the last component table, a new net table after the last net table, a pin on an existing net
appended to its array in the array's style, the block's accept as keys of the table – and the design it gives is the
one the JSON path gives."""

import difflib
import json
import re
import shutil
import tomllib

import pytest

from helpers import check
from test_block import CONNECT, TESTS, signals
from test_graph_toml import to_toml, value

from edakit import block, cli, config, toml_edit
from edakit.design import Design, load_graph


# --- led-bar written by hand as TOML ---------------------------------------------------------------------------------
def key(k):
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else json.dumps(k, ensure_ascii=False)


def as_written(graph):
    """A graph as TOML the way a person writes it: comments at the top, above the components and the nets, at the end
    of a line and inside an array; the pins of GND two to a line with a trailing comma, those of +5V one to a line
    without one and a comment after the last, every other array inline."""
    out = ["# led-bar, written by hand as TOML: block add keeps every comment", ""]
    for k, v in graph.items():
        if k not in ("components", "nets") and not isinstance(v, dict):
            out.append(f"{key(k)} = {value(v)}" + ("    # no wires between boards" if k == "cables" else ""))
    for k, v in graph.items():
        if isinstance(v, dict):
            out += ["", f"[{key(k)}]", *(f"{key(x)} = {value(y)}" for x, y in v.items())]
    out += ["", "", "# ── Components ──"]
    for c in graph["components"]:
        out += ["", f"[components.{key(c['designator'])}]"]
        out += [f"{key(x)} = {value(y)}" + ("   # the Pico" if (c["designator"], x) == ("U1", "type") else "")
                for x, y in c.items() if x != "designator"]
    out += ["", "", "# ── Nets: v is [min, max] in V over all operating states ──"]
    for n in graph["nets"]:
        out += ["", f"[nets.{key(n['name'])}]"]
        for x, y in n.items():
            if x == "name":
                continue
            if x == "pins" and n["name"] == "GND":
                rows = [", ".join(value(p) for p in y[i:i + 2]) + "," for i in range(0, len(y), 2)]
                out += ["pins = [", f"  {rows[0]}     # the connector and the driver", "  # the rest of the board",
                        *(f"  {r}" for r in rows[1:]), "]"]
            elif x == "pins" and n["name"] == "+5V":
                out += ["pins = [", *(f"  {value(p)}," for p in y[:-1]), f"  {value(y[-1])}   # the last LED", "]"]
            else:
                out.append(f"{key(x)} = {value(y)}")
    return "\n".join(out) + "\n"


def twin(project, tmp_path):
    """A copy of the project as it is now, its graph staying JSON."""
    dst = tmp_path / "json"
    shutil.copytree(project.root, dst)
    return config.load(dst / "edakit.toml")


def written(project):
    """The project with its graph as TOML by hand (as_written); it loads to the dict its JSON gives."""
    g = project.graph()["graph"]
    cfg = to_toml(project, as_written(g))
    assert load_graph(cfg.graph) == g
    return cfg


def resolved(cfg):
    """The graph as the engines see it: every pin word resolved, the pin maps the parts entries give."""
    return Design.from_config(cfg).graph


def notes(text):
    return [ln[ln.index("#"):] for ln in text.splitlines() if "#" in ln]


def kept(before, after):
    """Every line of before is in after, in its order – only a line of an array that got a pin has grown: its items
    and its comment as they were."""
    a, b = before.splitlines(), after.splitlines()
    grown = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            for old in a[i1:i2]:
                code, _, note = old.partition("#")
                assert any(new.startswith(code.rstrip().rstrip("]")) and new.partition("#")[2] == note
                           for new in b[j1:j2]), old
                grown += 1
    assert notes(before) == [n for n in notes(after) if n in notes(before)]
    return grown


# --- block add on a TOML graph -----------------------------------------------------------------------------------
def test_block_add_writes_a_toml_graph_and_keeps_its_comments(project, tmp_path):
    json_cfg = twin(project, tmp_path)
    cfg = written(project)
    before = cfg.graph.read_text(encoding="utf-8")
    _, comps, new_nets, extended, _, copy, _ = block.add(cfg, "led", "STATUS", {"in": "BTN"})
    assert [c["designator"] for c in comps] == ["R3", "D10"] and copy == ["C17471"]
    assert extended == {"BTN": ["R3.1"], "GND": ["D10.2"]}
    assert (project.root / "hardware" / "parts" / "C17471.json").exists()
    after = cfg.graph.read_text(encoding="utf-8")
    assert kept(before, after) == 1                                       # BTN's inline array; GND got a line
    assert '[nets.BTN]\npins = ["U1.9", "SW1.1", "R3.1"]\nv = [0, 3.4]\n' in after
    assert '  "U1.33", "U1.38",\n  "U1.42",\n  "D10.2",\n]\n' in after   # not one to a line: the new pins on one
    # the new components after the last component table, before the comment that opens the nets; the new net last
    assert after.index("[components.D9]") < after.index("[components.R3]") < after.index("[components.D10]") \
        < after.index("# ── Nets")
    assert after.rstrip().endswith('[nets.STATUS_ANODE]\nv = [0, 3.4]\npins = ["R3.2", "D10.1"]')
    assert "pins = {" not in after[after.index("[components.R3]"):]       # the pin map is the parts entry's
    block.add(json_cfg, "led", "STATUS", {"in": "BTN"})
    assert resolved(cfg) == resolved(json_cfg)
    assert same_findings(cfg, json_cfg)


def same_findings(cfg, other):
    a, b = (check(Design.from_config(c), c) for c in (cfg, other))
    return all(getattr(a, k) == getattr(b, k) for k in ("errors", "warnings", "notes", "pending", "waived"))


@pytest.mark.parametrize("name", sorted(CONNECT))
def test_every_block_goes_into_a_toml_graph_as_into_its_json(project, tmp_path, name):
    """Each library block where test_block puts it: the TOML graph gives the design the JSON gives – components, nets
    with their pins, accepts, grounds –, every line of before stays, and the graph reads to the JSON's but for the pin
    maps of the block's parts, which their parts entries give."""
    t = TESTS[name]
    signals(project, set(t["connect"].values()))
    connect = {port: net for port, net in t["connect"].items() if net not in (t.get("nets") or {})}
    json_cfg = twin(project, tmp_path)
    cfg = written(project)
    before = cfg.graph.read_text(encoding="utf-8")
    _, comps, *_ = block.add(cfg, name, "T", connect, without=t.get("without", ()))
    block.add(json_cfg, name, "T", connect, without=t.get("without", ()))
    assert resolved(cfg) == resolved(json_cfg)
    kept(before, cfg.graph.read_text(encoding="utf-8"))
    assert load_graph(cfg.graph) == without_maps(load_graph(json_cfg.graph), {c["designator"] for c in comps})


def without_maps(graph, designators):
    return {**graph, "components": [{k: v for k, v in c.items() if not (k == "pins" and c["designator"] in designators)}
                                    for c in graph["components"]]}


def test_the_accept_of_a_block_goes_as_keys_of_its_table(project, tmp_path):
    """usb-c-sink's connector accepts a finding: accept."<code place>" = "<reason>" in its table, named for the
    renamed designator as on the JSON path."""
    json_cfg = twin(project, tmp_path)
    cfg = written(project)
    _, comps, *_ = block.add(cfg, "usb-c-sink", "USB", {"vbus": "+5V"})
    j = next(c for c in comps if c.get("accept"))
    assert j["designator"] == "J2" and list(j["accept"]) == ["LIM.v"]
    text = cfg.graph.read_text(encoding="utf-8")
    table = text[text.index("[components.J2]"):]
    table = table[:table.index("\n[")]
    assert '\naccept."LIM.v" = """\\\n' in table and "accept = " not in table    # a long reason over several lines
    assert tomllib.loads(table)["components"]["J2"]["accept"] == j["accept"]
    block.add(json_cfg, "usb-c-sink", "USB", {"vbus": "+5V"})
    assert resolved(cfg) == resolved(json_cfg)
    assert same_findings(cfg, json_cfg)


def test_the_grounds_of_a_block_go_into_the_graph_keys(project):
    """lipo-charger's cell minus is a ground of its own: led-bar has no grounds, they come as a key before the first
    table; a second charger appends to the array."""
    cfg = written(project)
    block.add(cfg, "lipo-charger", "CHG", {"vbus": "+5V"})
    text = cfg.graph.read_text(encoding="utf-8")
    assert text.index('grounds = ["CHG_CELL_N"]') < text.index("[purpose]")
    block.add(cfg, "lipo-charger", "CHG2", {"vbus": "+5V"})
    assert 'grounds = ["CHG_CELL_N", "CHG2_CELL_N"]' in cfg.graph.read_text(encoding="utf-8")
    assert load_graph(cfg.graph)["grounds"] == ["CHG_CELL_N", "CHG2_CELL_N"]


def test_a_name_clash_on_a_toml_graph_is_refused_as_on_json(project):
    cfg = written(project)
    block.add(cfg, "led", "STATUS", {"in": "BTN"})
    before = cfg.graph.read_text(encoding="utf-8")
    with pytest.raises(block.BlockError, match="net STATUS_ANODE exists already – choose another --as"):
        block.add(cfg, "led", "STATUS", {"in": "BTN"})
    assert cfg.graph.read_text(encoding="utf-8") == before


def test_a_net_that_is_no_table_is_refused_and_the_file_stays(project):
    """The editor writes into [nets.<name>] tables; a net written otherwise is named, and nothing is written."""
    cfg = written(project)
    table = '[nets.BTN]\npins = ["U1.9", "SW1.1"]\nv = [0, 3.4]\nnotes = "Internal pull-up of GP6; pressed = 0."\n'
    text = cfg.graph.read_text(encoding="utf-8")
    assert table in text
    text = text.replace(table, '[nets]\nBTN = { pins = ["U1.9", "SW1.1"], v = [0, 3.4] }\n')
    cfg.graph.write_text(text, encoding="utf-8")
    assert next(n for n in load_graph(cfg.graph)["nets"] if n["name"] == "BTN")["pins"] == ["U1.9", "SW1.1"]
    with pytest.raises(block.BlockError, match=r"net BTN is no table \[nets.BTN\]"):
        block.add(cfg, "led", "STATUS", {"in": "BTN"})
    assert cfg.graph.read_text(encoding="utf-8") == text
    assert not (project.root / "hardware" / "parts" / "C17471.json").exists()


def test_block_add_runs_on_a_toml_graph_without_components(project):
    """components = [] gives way to the first component table, which goes before the nets; a net's empty array gets
    its first pins."""
    cfg = to_toml(project, '# nothing yet\nname = "empty"\nground = "GND"\ncomponents = []    # none yet\n\n'
                           '[purpose]\nuse = "private"\n\n# the ground, for the first block\n[nets.GND]\nv = [0, 0]\n'
                           'pins = []\n')
    block.add(cfg, "power-input-jst", "PWR", {})
    g = load_graph(cfg.graph)
    assert [c["designator"] for c in g["components"]] == ["J1", "D1", "C1"]
    assert [(n["name"], n["pins"]) for n in g["nets"]] == [("GND", ["J1.2", "C1.2"]), ("PWR_VIN", ["J1.1", "D1.2"]),
                                                           ("PWR_OUT", ["D1.1", "C1.1"])]
    text = cfg.graph.read_text(encoding="utf-8")
    assert text.startswith('# nothing yet\nname = "empty"\nground = "GND"\n\n[purpose]\nuse = "private"\n\n'
                           '[components.J1]\n')
    assert text.index("[components.C1]") < text.index("# the ground, for the first block\n[nets.GND]")


def test_the_cli_adds_a_block_to_a_toml_graph(project, capsys):
    cfg = written(project)
    assert cli.main(["block", "add", "led", "--as", "STATUS", "--connect", "in=BTN",
                     "--config", str(project.root / "edakit.toml")]) == 0
    assert "added block led as STATUS:" in capsys.readouterr().out
    assert "[components.D10]" in cfg.graph.read_text(encoding="utf-8")


# --- the line editor ---------------------------------------------------------------------------------------------
NETS = '''\
# nets of a test
[nets.GND]
v = [0, 0]
pins = [
  "U1.3", "U1.8",     # the MCU's grounds
  # the capacitor
  "C1.2",
]

[nets.VCC]
pins = [
  "U1.1",
  "C1.1"   # the last one
]
v = [0, 3.6]

[nets.SIG]
pins = ["U1.5", "R1.1"]  # inline

[nets.OUT]
pins = ["U1.6",
        "R2.1"]

[nets.NONE]
pins = []
notes = "]"
'''


def test_a_pin_goes_into_an_array_in_its_style():
    doc = toml_edit.Doc(NETS)
    for net, pins in (("GND", ["R3.2", "R4.2"]), ("VCC", ["R3.1", "R4.1"]), ("SIG", ["R3.3"]), ("OUT", ["R3.4"]),
                      ("NONE", ["R9.1"])):
        assert doc.append(("nets", net), "pins", pins)
    assert doc.text == '''\
# nets of a test
[nets.GND]
v = [0, 0]
pins = [
  "U1.3", "U1.8",     # the MCU's grounds
  # the capacitor
  "C1.2",
  "R3.2", "R4.2",
]

[nets.VCC]
pins = [
  "U1.1",
  "C1.1",   # the last one
  "R3.1",
  "R4.1"
]
v = [0, 3.6]

[nets.SIG]
pins = ["U1.5", "R1.1", "R3.3"]  # inline

[nets.OUT]
pins = ["U1.6",
        "R2.1", "R3.4"]

[nets.NONE]
pins = ["R9.1"]
notes = "]"
'''
    assert not doc.append(("nets", "GND"), "fn", ["x"])                   # no such key: the caller adds it


def test_a_table_goes_after_the_last_of_its_kind_and_a_key_after_the_last_of_its_table():
    doc = toml_edit.Doc(NETS)
    doc.add_table(("nets", "+5V"), ['v = [0, 5.5]', 'pins = ["J1.1"]'], after="nets")
    doc.add_keys(("nets", "VCC"), ['bus = "i2c"'])
    doc.add_keys((), ['grounds = ["AGND"]'])
    assert doc.text.endswith('pins = []\nnotes = "]"\n\n[nets."+5V"]\nv = [0, 5.5]\npins = ["J1.1"]\n')
    assert 'v = [0, 3.6]\nbus = "i2c"\n\n[nets.SIG]' in doc.text
    assert doc.text.startswith('grounds = ["AGND"]\n\n# nets of a test\n[nets.GND]')
    assert tomllib.loads(doc.text)["nets"]["+5V"] == {"v": [0, 5.5], "pins": ["J1.1"]}


def test_many_pins_go_on_lines_that_fit():
    doc = toml_edit.Doc(NETS)
    doc.append(("nets", "GND"), "pins", [f"U9.{n}" for n in range(1, 41)])
    lines = doc.text[doc.text.index('  "C1.2",\n') + 10:doc.text.index("]\n\n[nets.VCC]")].splitlines()
    assert len(lines) > 2 and all(ln.startswith('  "U9.') and ln.endswith(",") for ln in lines)
    assert all(len(ln) <= toml_edit.WIDTH for ln in lines)
    assert tomllib.loads(doc.text)["nets"]["GND"]["pins"][3:] == [f"U9.{n}" for n in range(1, 41)]


TRICKY = '''\
[components.U1]
notes = """
[nets.FAKE]
# no comment, no table: a string
"""
pins = { "1" = "VDD", "2" = "]" }   # a comment with ] and "

# the nets
[nets.GND]
pins = ['U1.2', "x#y"]
'''


def test_strings_that_look_like_tables_comments_or_brackets_stay_strings():
    doc = toml_edit.Doc(TRICKY)
    doc.add_table(("components", "R1"), ['type = "resistor"'], after="components")
    doc.append(("nets", "GND"), "pins", ["R1.2"])
    assert doc.text == TRICKY.replace('" }   # a comment with ] and "\n',
                                      '" }   # a comment with ] and "\n\n[components.R1]\ntype = "resistor"\n') \
        .replace("""pins = ['U1.2', "x#y"]""", """pins = ['U1.2', "x#y", "R1.2"]""")
    assert list(tomllib.loads(doc.text)["components"]) == ["U1", "R1"]


def test_a_block_that_would_not_read_back_is_not_written(project, monkeypatch):
    """The safety net: when the text the editor made does not read as the graph with the block in it, nothing is
    written – here an editor that loses the pins for existing nets."""
    cfg = written(project)
    before = cfg.graph.read_text(encoding="utf-8")
    monkeypatch.setattr(toml_edit.Doc, "append", lambda self, table, k, items: True)
    with pytest.raises(block.BlockError, match="would not read back as written \\(nets differ\\) – the file is left"):
        block.add(cfg, "led", "STATUS", {"in": "BTN"})
    assert cfg.graph.read_text(encoding="utf-8") == before
    assert not (project.root / "hardware" / "parts" / "C17471.json").exists()


VALUES = ["plain", 'a "quote" and a \\ backslash', "22 µF – ±5 %", "tab\tand\nnewline", "del\x7f", "", 0, -3, 2.5,
          1e-12, True, False, [], [0, 5.5], ["a", "b"], {}, {"LIM.v D1": "a reason", "plain": 1},
          "a long note " * 30, ["U1.1"] * 40]


@pytest.mark.parametrize("v", VALUES)
def test_a_value_is_written_as_a_toml_literal_that_reads_back(v):
    text = toml_edit.line("k", v)
    assert tomllib.loads(text)["k"] == v
    assert all(len(ln) <= toml_edit.WIDTH for ln in text.splitlines()) or isinstance(v, str) and " " not in v


def test_null_has_no_toml_literal():
    with pytest.raises(toml_edit.TomlEditError, match="TOML has no null"):
        toml_edit.line("k", None)
