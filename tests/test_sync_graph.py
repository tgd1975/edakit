"""SYNC.graph (T.4 of circuit-dsl-toolchain.md, language 12 item 16): edakit check reports a generated graph.json
that is no longer what its TOML or .circuit source resolves to, as an error of stage G; a current one, one not
written and a JSON project nothing."""

from helpers import check
from lang_project import to_circuit
from test_graph_toml import to_toml

from edakit import cli
from edakit.design import Design
from edakit.engines import project as engines_project


def sync(cfg):
    return [f for f in engines_project.run(Design.from_config(cfg), cfg) if f.code == "SYNC.graph"]


def write(project):
    assert cli.main(["graph", "json", "--write", "--config", str(project.root / "edakit.toml")]) == 0


def test_a_json_project_has_none(project):
    assert sync(project.config()) == []


def test_a_toml_project_with_a_stale_generated_file(project, capsys):
    cfg = to_toml(project)
    assert sync(cfg) == []                                     # not written: the hook's --check says so
    write(project)
    assert sync(cfg) == []
    cfg.graph.write_text(cfg.graph.read_text(encoding="utf-8").replace('"U1.4"', '"U1.7"', 1), encoding="utf-8")
    found = sync(cfg)
    assert len(found) == 1 and found[0].stage == "G" and found[0].data["class"] == "error"
    assert found[0].text.startswith("hardware/graph.json: drift from hardware/graph.toml – nets.")
    report = check(Design.from_config(cfg), cfg)
    assert any(code == "SYNC.graph" for code, _ in report.errors)


def test_a_language_project_with_a_stale_generated_file(project, capsys):
    cfg = to_circuit(project)
    write(project)
    assert sync(cfg) == []
    cfg.graph.write_text(cfg.graph.read_text(encoding="utf-8").replace("value 10k", "value 4.7k"), encoding="utf-8")
    found = sync(cfg)
    assert len(found) == 1 and "components.R2.value" in found[0].text
    args = ["check", "--config", str(project.root / "edakit.toml")]
    assert cli.main(args) == 1 and "SYNC.graph" in capsys.readouterr().out
