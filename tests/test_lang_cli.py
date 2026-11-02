"""T.4 of circuit-dsl-toolchain.md: a project whose [project] graph is a .circuit file – edakit graph json prints,
writes beside the source and finds drift; edakit check reports what led-bar reports; the circuit hash takes the
compiled data (language 8)."""

import hashlib
import json

from lang_project import fixture_graph, to_circuit

from edakit import cli, scripts
from edakit.graph_form import canonical
from edakit.release import gate


def run(project, *argv):
    return cli.main(["graph", *argv, "--config", str(project.root / "edakit.toml")])


def test_graph_json_prints_writes_and_checks(project, capsys):
    want = fixture_graph(project)
    cfg = to_circuit(project)
    out = project.root / "hardware" / "graph.json"
    capsys.readouterr()
    assert run(project, "json") == 0
    assert canonical(json.loads(capsys.readouterr().out)["graph"]) == canonical(want)
    assert run(project, "json", "--check") == 2 and "not written yet" in capsys.readouterr().out
    assert run(project, "json", "--write") == 0 and "hardware/graph.json written" in capsys.readouterr().out
    first = out.read_bytes()
    assert run(project, "json", "--write") == 0 and "unchanged" in capsys.readouterr().out
    assert out.read_bytes() == first                                  # a second --write changes no bytes
    assert run(project, "json", "--check") == 0 and "is current" in capsys.readouterr().out
    text = cfg.graph.read_text(encoding="utf-8")
    cfg.graph.write_text(text.replace("U2.OUT0 D2.cathode", "U2.OUT1 D2.cathode").replace(
        "U2.OUT1 D3.cathode", "U2.OUT0 D3.cathode"), encoding="utf-8")
    assert run(project, "json", "--check") == 2
    report = capsys.readouterr().out
    assert "drift" in report and "nets.LED0.pins" in report
    assert run(project, "json", "--write") == 0 and run(project, "json", "--check") == 0


def test_the_map_is_written_on_request(project, capsys, tmp_path):
    to_circuit(project)
    where = tmp_path / "map.json"
    assert run(project, "json", "--map", str(where)) == 0
    smap = json.loads(where.read_text())
    assert smap["components"]["U1"]["file"] == "hardware/graph.circuit" and "LED_SDI" in smap["nets"]


def test_led_bar_s_check_is_led_bar_s(project, capsys):
    args = ["check", "--config", str(project.root / "edakit.toml")]
    code = cli.main(args)
    before = capsys.readouterr().out
    to_circuit(project)
    assert cli.main(args) == code
    assert capsys.readouterr().out == before


def edited(project, change):
    path = project.root / "hardware" / "graph.circuit"
    text = path.read_text(encoding="utf-8")
    assert change(text) != text, "the change does not change the text"
    path.write_text(change(text), encoding="utf-8")
    try:
        return gate.state_hash(project.config())
    finally:
        path.write_text(text, encoding="utf-8")


def test_the_circuit_hash_takes_the_compiled_data(project):
    json_hash = gate.state_hash(project.config())
    cfg = to_circuit(project)
    h = gate.state_hash(cfg)
    assert edited(project, lambda t: "# a comment at the top\n" + t) == h
    assert edited(project, lambda t: t.replace("\n\nnet VIN", "\n\n\n\nnet VIN")) == h           # blank lines
    assert edited(project, _swap_parts) == h                                                   # statements moved
    assert edited(project, lambda t: t.replace("U1.GP2 (locked)", "U1.GP7 (locked)")) != h        # a pin
    assert edited(project, lambda t: t.replace("value 10k", "value 4.7k")) != h
    assert edited(project, lambda t: t.replace("not sold or given away", "sold")) != h            # purpose.notes
    assert edited(project, lambda t: t + "\nnet\n") != h                                        # no graph: its bytes
    assert json_hash != h                                                    # the hash changes once, on the move


def _swap_parts(text):
    """The source with the statements of R2 and C1 swapped."""
    lines = text.splitlines(keepends=True)
    i = next(k for k, ln in enumerate(lines) if ln.startswith("part R2 "))
    j = next(k for k, ln in enumerate(lines) if ln.startswith("part C1 "))
    lines[i], lines[j] = lines[j], lines[i]
    return "".join(lines)


def test_graph_sha256_names_the_source_s_bytes(project):
    cfg = to_circuit(project)
    head = gate.header(cfg)
    assert head["graph_sha256"] == hashlib.sha256(cfg.graph.read_bytes()).hexdigest()
    cfg.graph.write_text("# a comment\n" + cfg.graph.read_text(encoding="utf-8"), encoding="utf-8")
    now = gate.header(cfg)
    assert now["graph_sha256"] != head["graph_sha256"] and now["state_sha256"] == head["state_sha256"]


def test_a_script_reads_the_compiled_graph_as_the_hash_does(project):
    cfg = to_circuit(project)
    first = scripts.data_hash(cfg, "graph")
    cfg.graph.write_text("# a comment\n" + cfg.graph.read_text(encoding="utf-8"), encoding="utf-8")
    assert scripts.data_hash(cfg, "graph") == first


def test_led_bar_s_json_hash_is_unchanged(project):
    from test_graph_toml import today
    cfg = project.config()
    assert gate.state_hash(cfg) == today(cfg)
