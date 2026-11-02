"""T.16 of circuit-dsl-toolchain.md: block add on a source of the circuit language writes a usage."""

import json

from lang_project import to_circuit
from test_block import signals

from edakit import block, cli
from edakit.graph_form import canonical
from edakit.lang.compile import resolved_of

SIG = "net SIG 0..3.4 V U1.GP7\n"


def circuit_with_sig(project):
    cfg = to_circuit(project)
    text = cfg.graph.read_text(encoding="utf-8")
    cfg.graph.write_text(text.replace("GP7 ", "").replace("\nset cables []", "\n" + SIG + "set cables []"),
                         encoding="utf-8")
    return cfg


def strip_notes(g):
    for c in g["components"]:
        if "notes" in c:
            c["notes"] = c["notes"].replace(" (block led, STATUS)", "").replace("(block led, STATUS)", "").strip()
            if not c["notes"]:
                del c["notes"]
    return g


def test_block_add_writes_a_usage_where_it_goes(project, capsys, tmp_path):
    import shutil
    json_project = tmp_path / "json"
    shutil.copytree(project.root, json_project)
    cfg = circuit_with_sig(project)
    before = cfg.graph.read_text(encoding="utf-8")
    assert cli.main(["block", "add", "led", "--as", "STATUS", "--connect", "in=SIG", "--config",
                     str(project.root / "edakit.toml")]) == 0
    after = cfg.graph.read_text(encoding="utf-8")
    use = "use led STATUS in = SIG\n  R1 = R3\n  D1 = D10\n"
    assert use in after and after.replace(use, "") == before
    assert after.index("part SW1") < after.index(use) < after.index("net VIN")
    got = json.loads((project.root / "hardware" / "graph.json").read_text())["graph"]
    assert {"R3", "D10"} <= {c["designator"] for c in got["components"]} and "derivations" not in got
    # the JSON path's result, the notes suffix stripped: the same graph
    from types import SimpleNamespace
    jp = SimpleNamespace(root=json_project, graph_file=json_project / "hardware" / "graph.json",
                         graph=lambda: json.loads((json_project / "hardware" / "graph.json").read_text()),
                         save_graph=lambda g: (json_project / "hardware" / "graph.json").write_text(json.dumps(g)),
                         free_pins=project.free_pins)
    signals(jp, ("SIG",))
    from edakit import config
    block.add(config.load(json_project / "edakit.toml"), "led", "STATUS", {"in": "SIG"})
    want = strip_notes(json.loads(jp.graph_file.read_text())["graph"])
    have, _ = resolved_of(cfg.graph)
    assert canonical(want) == canonical(have)


def test_a_second_add_numbers_on_and_set_writes_the_parameter(project):
    cfg = circuit_with_sig(project)
    block.add(cfg, "led", "STATUS", {"in": "SIG"}, sets={"i": "4mA"})
    text = cfg.graph.read_text(encoding="utf-8")
    assert "use led STATUS (i = 4mA) in = SIG\n  R1 = R3\n  D1 = D10\n" in text
    g, _ = resolved_of(cfg.graph)
    [rec] = g["derivations"]
    assert rec["part"] == "R3" and rec["derived"]["value"] == 140 and rec["from"] == "def led, use STATUS"
    block.add(project.config(), "led", "OTHER", {"in": "SIG"})
    assert "use led OTHER in = SIG\n  R1 = R4\n  D1 = D11\n" in cfg.graph.read_text(encoding="utf-8")


def test_part_writes_the_binding_s_entry(project):
    cfg = circuit_with_sig(project)
    block.add(cfg, "led", "STATUS", {"in": "SIG"}, sets={"i": "2mA"}, choices={"R1": "C17630"})
    text = cfg.graph.read_text(encoding="utf-8")
    assert "  R1 = R3 0805W8F3300T5E lcsc C17630 value 330\n" in text


def test_dry_run_changes_nothing(project, capsys):
    cfg = circuit_with_sig(project)
    before = cfg.graph.read_text(encoding="utf-8")
    assert cli.main(["block", "add", "led", "--as", "STATUS", "--connect", "in=SIG", "--dry-run", "--config",
                     str(project.root / "edakit.toml")]) == 0
    assert "would write into hardware/graph.circuit:\nuse led STATUS in = SIG" in capsys.readouterr().out
    assert cfg.graph.read_text(encoding="utf-8") == before
