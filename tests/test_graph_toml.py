"""The graph as TOML (circuit-language plan, steps L.3 and L.4): load_graph reads a .toml graph to the dict the JSON
gives, every reader goes through it, and the circuit hash takes the TOML graph's data – comments and arrangement count
for nothing, every change of data does. A JSON graph loads and hashes as before."""

import hashlib
import json
import re

import pytest

from edakit import block, cli, convert, scripts
from edakit.config import ConfigError
from edakit.design import load_graph
from edakit.release import gate, publish


# --- a graph written as TOML -----------------------------------------------------------------------------------------
def value(v):
    """A JSON value as TOML, on one line."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ", ".join(value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{json.dumps(k)} = {value(x)}" for k, x in v.items()) + "}"
    raise ValueError(f"{v!r}: TOML has no null")


def as_toml(graph):
    """A graph (the inner object) as TOML: components, nets and cables as tables keyed by designator and name, the
    other tables as tables, the rest at the top – pins by number, as in the JSON."""
    keyed = {"components": "designator", "nets": "name", "cables": "name"}
    top, tables = [], []
    for k, v in graph.items():
        if k in keyed and v:
            for row in v:
                tables.append(f"\n[{k}.{json.dumps(row[keyed[k]])}]")
                tables += [f"{json.dumps(x)} = {value(y)}" for x, y in row.items() if x != keyed[k]]
        elif isinstance(v, dict):
            tables.append(f"\n[{k}]")
            tables += [f"{json.dumps(x)} = {value(y)}" for x, y in v.items()]
        else:
            top.append(f"{json.dumps(k)} = {value(v)}")
    return "\n".join(top + tables) + "\n"


def to_toml(project, text=None):
    """The example with its graph as hardware/graph.toml, named by [project] graph; graph.json gone."""
    (project.root / "hardware" / "graph.toml").write_text(text or as_toml(project.graph()["graph"]), encoding="utf-8")
    project.graph_file.unlink()
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace('graph = "hardware/graph.json"', 'graph = "hardware/graph.toml"'))
    return project.config()


SMALL_TOML = '''\
# A small graph by hand: pins by number, as in its JSON below.
name = "small"
version = "0.1"
ground = "GND"
grounds = ["AGND"]
accept = { "HINT.bulk J1" = "C1 sits next to J1" }

[purpose]
use = "private"
market = "EU"
notes = """\\
  Built for the test, \\
  not sold."""

[conventions]
pin_reference = "'<designator>.<pin>' with the pin numbers of the symbol"

[components.U1]          # the order of the file is the order of the list: U1, R2, R1
type = "ic"
lcsc = "C1"
pins = { "1" = "VDD", "2" = "GND", "3" = "OUT", "4" = "NC" }
nc = ["4"]

[components.R2]
type = "resistor"
value = "10kΩ"
pins = { "1" = "1", "2" = "2" }
accept."STRUCT.entry" = "a resistor from the drawer"

[components.R1]
type = "resistor"
value = "330Ω"
bom = false
pins = { "1" = "1", "2" = "2" }

[nets.VDD]
v = [3.0, 3.6]
pins = ["U1.1", "R2.1"]

[nets.OUT]
v = [0, 3.6]
pins = [
  "U1.3",
  "R1.1",   # the series resistor
]
fn = "gpio"

[nets.GND]
v = [0, 0]
pins = ["U1.2", "R1.2", "R2.2"]
notes = "one ground"

[cables.W1]
from = "J1"
to = "J2"
pins = { "1" = "1", "2" = "2" }
r_ohm_per_wire = 0.065

[layout]
edge = ["R1"]
near = { R1 = "U1" }
loops = [{ a = "U1.1", b = "R2.1", max_mm = 8 }]

[locks]
pins = { "U1.3" = "OUT" }
'''

SMALL_JSON = {"graph": {
    "name": "small", "version": "0.1", "ground": "GND", "grounds": ["AGND"],
    "accept": {"HINT.bulk J1": "C1 sits next to J1"},
    "purpose": {"use": "private", "market": "EU", "notes": "Built for the test, not sold."},
    "conventions": {"pin_reference": "'<designator>.<pin>' with the pin numbers of the symbol"},
    "components": [
        {"designator": "U1", "type": "ic", "lcsc": "C1", "pins": {"1": "VDD", "2": "GND", "3": "OUT", "4": "NC"},
         "nc": ["4"]},
        {"designator": "R2", "type": "resistor", "value": "10kΩ", "pins": {"1": "1", "2": "2"},
         "accept": {"STRUCT.entry": "a resistor from the drawer"}},
        {"designator": "R1", "type": "resistor", "value": "330Ω", "bom": False, "pins": {"1": "1", "2": "2"}}],
    "nets": [
        {"name": "VDD", "v": [3.0, 3.6], "pins": ["U1.1", "R2.1"]},
        {"name": "OUT", "v": [0, 3.6], "pins": ["U1.3", "R1.1"], "fn": "gpio"},
        {"name": "GND", "v": [0, 0], "pins": ["U1.2", "R1.2", "R2.2"], "notes": "one ground"}],
    "cables": [{"name": "W1", "from": "J1", "to": "J2", "pins": {"1": "1", "2": "2"}, "r_ohm_per_wire": 0.065}],
    "layout": {"edge": ["R1"], "near": {"R1": "U1"}, "loops": [{"a": "U1.1", "b": "R2.1", "max_mm": 8}]},
    "locks": {"pins": {"U1.3": "OUT"}}}}


# --- L.3 the TOML form, read by load_graph ---------------------------------------------------------------------------
def test_a_toml_graph_loads_to_the_dict_its_json_gives(tmp_path):
    (tmp_path / "graph.toml").write_text(SMALL_TOML, encoding="utf-8")
    (tmp_path / "graph.json").write_text(json.dumps(SMALL_JSON, indent=1, ensure_ascii=False), encoding="utf-8")
    g = load_graph(tmp_path / "graph.toml")
    assert g == load_graph(tmp_path / "graph.json")
    assert [c["designator"] for c in g["components"]] == ["U1", "R2", "R1"]        # the order of the file
    assert [n["name"] for n in g["nets"]] == ["VDD", "OUT", "GND"]
    assert list(g["components"][0])[0] == "designator" and list(g["nets"][0])[0] == "name"   # the key first
    assert g["components"][0]["pins"]["1"] == "VDD"                                # pin words stay as written


def test_the_example_as_toml_loads_to_its_json(project):
    g = project.graph()["graph"]
    path = project.root / "hardware" / "graph.toml"
    path.write_text(as_toml(g), encoding="utf-8")
    assert load_graph(path) == g == load_graph(project.graph_file)


BROKEN = [
    ('[components.R1]\ntype = "resistor"\ntype = "led"\n', "Cannot overwrite a value (at line 3, column 13)"),
    ('[components.R1]\ntype = "resistor"\n\n[components.R1]\nvalue = "1k"\n',
     "Cannot declare ('components', 'R1') twice (at line 4, column 15)"),
    ('[nets.GND]\nv = [0, 0]\nnotes = null\n', "Invalid value (at line 3, column 9)"),
    ('[components.R1]\ndesignator = "R1"\n', "[components.R1]: designator is the table's key"),
    ('[nets.GND]\nname = "AGND"\n', "[nets.GND]: name is the table's key"),
    ('[[components]]\ndesignator = "R1"\n', "components: a table keyed by designator, [components.<designator>]"),
    ('[nets]\nGND = [0, 0]\n', "nets.GND: a table, [nets.GND]"),
]


@pytest.mark.parametrize("text, said", BROKEN)
def test_a_broken_toml_graph_names_the_file_and_the_line(tmp_path, text, said):
    path = tmp_path / "graph.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match=re.escape(f"{path}: {said}")):
        load_graph(path)


def test_a_project_with_a_toml_graph_is_checked_as_with_its_json(project, capsys):
    args = ["check", "--config", str(project.root / "edakit.toml")]
    code = cli.main(args)
    before = capsys.readouterr().out
    cfg = to_toml(project)
    assert cfg.graph == project.root / "hardware" / "graph.toml" and not project.graph_file.exists()
    assert cli.main(args) == code
    assert capsys.readouterr().out == before
    assert "17 components, 18 nets" in before


def test_edakit_check_names_the_line_of_a_broken_toml_graph(project, capsys):
    cfg = to_toml(project)
    cfg.graph.write_text(cfg.graph.read_text(encoding="utf-8") + '\n[components.R1]\nvalue = "1k"\n', encoding="utf-8")
    assert cli.main(["check", "--config", str(project.root / "edakit.toml")]) == 1
    err = capsys.readouterr().err
    assert f"{cfg.graph}: Cannot declare ('components', 'R1') twice (at line" in err


def test_block_add_dry_run_on_a_toml_graph_writes_nothing(project, capsys):
    """block add reads a TOML graph and shows what it would add; with --dry-run nothing is written (the writing:
    tests/test_block_toml.py, step L.7)."""
    cfg = to_toml(project)
    before = cfg.graph.read_text(encoding="utf-8")
    _, comps, *_ = block.add(cfg, "led", "STATUS", {"in": "BTN"}, dry_run=True)
    assert [c["designator"] for c in comps] == ["R3", "D10"]
    assert cli.main(["block", "add", "led", "--as", "STATUS", "--connect", "in=BTN", "--dry-run",
                     "--config", str(project.root / "edakit.toml")]) == 0
    assert "would add block led as STATUS:" in capsys.readouterr().out
    assert cfg.graph.read_text(encoding="utf-8") == before
    assert not (project.root / "hardware" / "parts" / "C17471.json").exists()      # no parts entry copied either


def test_convert_has_nothing_to_do_on_a_toml_graph(project, capsys):
    """A TOML graph is in the form of the restructuring by construction; the parts entries are still converted."""
    to_toml(project)
    p = project.part("C8678")
    p["ratings"] = p.pop("limits")       # a parts entry of before
    project.save_part("C8678", p)
    assert cli.main(["convert", "--write", "--config", str(project.root / "edakit.toml")]) == 0
    out = capsys.readouterr().out
    assert "hardware/graph.toml: a TOML graph is in the form of the restructuring – nothing to convert" in out
    assert "converted: hardware/parts/C8678.json" in out and "graph.toml" not in out.split("converted:")[1]
    assert project.part("C8678")["limits"]["vr_max_v"] == 40
    assert [path.name for path, _, _ in convert.files(project.config())] == []


def test_convert_names_the_form_of_before_in_a_toml_graph(project, capsys):
    text = as_toml(project.graph()["graph"]).replace('"source" = "reversible"', '"waive" = {"P-1" = "free"}', 1)
    to_toml(project, text)
    assert cli.main(["convert", "--config", str(project.root / "edakit.toml")]) == 0
    assert ("hardware/graph.toml: J1: waive – the form of before; convert does not rewrite a TOML graph: write accept "
            "and locks in its place by hand (handbook 3.1)") in capsys.readouterr().out


def test_the_release_notes_read_the_purpose_of_a_toml_graph(project):
    cfg = to_toml(project)
    assert publish.purpose(cfg) == {"use": "private", "market": "EU",
                                    "notes": "An example board for edakit, built for testing, not sold or given away."}


# --- L.4 the circuit hash of a TOML graph ----------------------------------------------------------------------------
def ignore(project, keys):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("[release]\n", f"[release]\nhash_ignore = {json.dumps(keys)}\n"))
    return project.config()


def today(cfg, ignore=()):
    """The circuit hash of a JSON graph as it was before the TOML form: the files byte for byte; with hash_ignore the
    graph and the parts entries as canonical JSON without those keys, purpose and compliance whole."""
    def strip(d):
        if isinstance(d, dict):
            return {k: v if k in ("purpose", "compliance") else strip(v) for k, v in d.items() if k not in ignore}
        return [strip(v) for v in d] if isinstance(d, list) else d
    h = hashlib.sha256()
    documented = [cfg.graph, *cfg.parts.glob("*.json")]
    for f in gate.state_files(cfg):
        data = f.read_bytes() if f.exists() else b"<missing>"
        if ignore and f in documented:
            data = json.dumps(strip(json.loads(data)), sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False).encode()
        h.update(str(f.relative_to(cfg.root)).encode() + b"\0" + data)
    return h.hexdigest()


FROZEN = '{"graph": {"name": "frozen", "components": [{"designator": "R1", "notes": "x", "pins": {"1": "1"}}],\n' \
         ' "nets": [{"name": "A", "pins": ["R1.1"], "v": [0, 5]}], "purpose": {"notes": "y"}}}\n'


def test_a_json_graph_keeps_its_circuit_hash(project, tmp_path):
    """Byte for byte as before: the example's circuit hash by the rule of before, and a frozen graph's hash pinned."""
    cfg = project.config()
    assert gate.state_hash(cfg) == today(cfg)
    cfg = ignore(project, ["notes", "sources"])
    assert gate.state_hash(cfg) == today(cfg, {"notes", "sources"})
    frozen = tmp_path / "graph.json"
    frozen.write_text(FROZEN, encoding="utf-8")
    assert gate.content(frozen) == FROZEN.encode()
    assert hashlib.sha256(gate.content(frozen, ["notes"])).hexdigest() == \
        "7a72f0dca26764e6924de1b22e3c180265bca133ab9a0e07d2774219e42cc8b1"


def edited(project, change):
    """The circuit hash of the example's TOML graph with a change to its text."""
    path = project.root / "hardware" / "graph.toml"
    text = path.read_text(encoding="utf-8")
    assert change(text) != text, "the change does not change the text"
    path.write_text(change(text), encoding="utf-8")
    try:
        return gate.state_hash(project.config())
    finally:
        path.write_text(text, encoding="utf-8")


def rearranged(project):
    """The example's graph as TOML with its components and nets in the opposite order and the pins of GND turned
    round."""
    g = project.graph()["graph"]
    g["components"].reverse()
    g["nets"].reverse()
    next(n for n in g["nets"] if n["name"] == "GND")["pins"].reverse()
    return as_toml(g)


def test_the_circuit_hash_of_a_toml_graph_takes_its_data(project):
    other = rearranged(project)
    cfg = to_toml(project)
    h = gate.state_hash(cfg)
    assert edited(project, lambda t: "# a comment at the top\n" + t) == h
    assert edited(project, lambda t: t.replace('"type" = "connector"', '"type" = "connector"   # the input', 1)) == h
    assert edited(project, lambda t: t.replace("\n[", "\n\n\n[")) == h                   # blank lines
    assert edited(project, lambda t: other) == h                                         # tables and pins moved
    assert edited(project, lambda t: t.replace('"U1.4"', '"U1.3"', 1)) != h               # a pin
    assert edited(project, lambda t: t.replace('"value" = "10k"', '"value" = "4.7k"', 1)) != h
    assert edited(project, lambda t: t.replace("not sold or given away", "sold")) != h    # purpose.notes
    assert edited(project, lambda t: t.replace('"notes" = "Pin 1 = VIN', '"notes" = "Pin one = VIN', 1)) != h
    assert edited(project, lambda t: t + "\n[components.R1\n") != h                       # no TOML: its bytes


def test_hash_ignore_reaches_into_a_toml_graph_and_purpose_stays_whole(project):
    to_toml(project)
    cfg = ignore(project, ["notes"])
    h = gate.state_hash(cfg)
    assert edited(project, lambda t: t.replace('"notes" = "Pin 1 = VIN', '"notes" = "Pin one = VIN', 1)) == h
    assert edited(project, lambda t: t.replace("not sold or given away", "sold")) != h    # KEEP_WHOLE: M-6 reads it
    assert edited(project, lambda t: t.replace('"U1.4"', '"U1.3"', 1)) != h


def test_graph_sha256_names_the_bytes_of_a_toml_graph(project):
    cfg = to_toml(project)
    head = gate.header(cfg)
    assert head["graph_sha256"] == hashlib.sha256(cfg.graph.read_bytes()).hexdigest()
    cfg.graph.write_text("# a comment\n" + cfg.graph.read_text(encoding="utf-8"), encoding="utf-8")
    now = gate.header(cfg)
    assert now["graph_sha256"] != head["graph_sha256"] and now["state_sha256"] == head["state_sha256"]


def test_a_script_reads_a_toml_graph_as_the_circuit_hash_does(project):
    cfg = to_toml(project)
    first = scripts.data_hash(cfg, "graph")
    assert scripts.data_hash(cfg, "hardware/graph.toml") == first
    cfg.graph.write_text("# a comment\n" + cfg.graph.read_text(encoding="utf-8"), encoding="utf-8")
    assert scripts.data_hash(cfg, "graph") == first
    cfg.graph.write_text(cfg.graph.read_text(encoding="utf-8").replace('"U1.4"', '"U1.3"', 1), encoding="utf-8")
    assert scripts.data_hash(cfg, "graph") != first
