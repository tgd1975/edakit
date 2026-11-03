"""The explorative DSL is a beta ([beta] dsl = true, edakit/beta.py, docs/dsl/README.md): without the switch edakit is
what it is on main – nothing of the DSL is read, offered, checked or mentioned; with it, a project's `.circuit` source
works. These tests hold the side without the switch; the tests of the language (test_lang_*) the side with it."""

import re
import shutil
from pathlib import Path

import pytest
from test_graph_toml import to_toml

from edakit import beta, catalog, cli, config
from edakit.design import Design
from edakit.engines import project as engines_project

ROOT = Path(__file__).resolve().parents[1]


def circuit(project):
    """led-bar with its graph named as a .circuit file – the fixture's source – but without the switch."""
    shutil.copy(ROOT / "tests" / "fixtures" / "led-bar-circuit" / "hardware" / "graph.circuit",
                project.root / "hardware" / "graph.circuit")
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace('graph = "hardware/graph.json"', 'graph = "hardware/graph.circuit"'))
    return toml


def test_a_circuit_graph_parts_list_or_requirements_file_needs_the_switch(project):
    toml = circuit(project)
    with pytest.raises(config.ConfigError, match=r"graph.circuit is the explorative DSL, a beta – edakit reads it "
                                                 r"with \[beta\] dsl = true"):
        config.load(toml)
    toml.write_text(toml.read_text() + "\n[beta]\ndsl = true\n")
    assert config.load(toml).dsl is True
    text = toml.read_text().replace('graph = "hardware/graph.circuit"', 'graph = "hardware/graph.json"')
    toml.write_text(text.replace("[beta]\ndsl = true\n", "").replace('parts = "hardware/parts"',
                                                                       'parts = ["hardware/parts"]'))
    with pytest.raises(config.ConfigError, match=r"\[project\] parts: a path.*a list of folders is the explorative"):
        config.load(toml)


def test_the_beta_table_takes_dsl_alone_and_a_boolean(project):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + '\n[beta]\ndsl = "yes"\nother = 1\n')
    with pytest.raises(config.ConfigError) as e:
        config.load(toml)
    assert "[beta]: unknown key 'other' (known: dsl)" in str(e.value) and "[beta] dsl: true or false" in str(e.value)


def test_a_project_without_the_switch_is_the_one_of_main(project):
    cfg = project.config()
    assert cfg.dsl is False and cfg.parts_dirs == [project.root / "hardware" / "parts"]


def test_the_requirement_s_dsl_keys_are_unknown_without_the_switch(tmp_path):
    from edakit import requirements
    f = tmp_path / "r.toml"
    f.write_text('[[requirement]]\nid = "R-1"\ntext = "t"\nbinding = "must"\nsubject = "led"\n')
    _, problems = requirements.read(f)
    assert problems == ["R-1: unknown key 'subject' (known: id, text, source, from, binding, verify, status, reason)"]
    entries, problems = requirements.read(f, dsl=True)
    assert problems == [] and entries[0].subject == "led"


def test_sync_graph_only_with_the_switch(project):
    cfg = to_toml(project)
    assert cli.main(["graph", "json", "--write", "--config", str(project.root / "edakit.toml")]) == 0
    cfg.graph.write_text(cfg.graph.read_text(encoding="utf-8").replace('"U1.4"', '"U1.7"', 1), encoding="utf-8")
    assert [f for f in engines_project.run(Design.from_config(cfg), cfg) if f.code == "SYNC.graph"] == []



def test_def_only_with_the_switch(project):
    """A derivation record in a JSON graph – written by hand, block add --set is refused – is no finding without the
    switch; with it, a value outside the record's window is DEF.derive."""
    from helpers import check
    g = project.graph()
    r1 = next(c for c in g["graph"]["components"] if c["designator"] == "R1")
    g["graph"]["derivations"] = [{"part": "R1", "key": "value", "rule": "series_resistor", "from": "by hand",
                                  "derived": {"value": 1.0, "unit": "Ω"},
                                  "series": {"name": "E24", "nearest": 1.0, "window": [0.9, 1.1]}, "inputs": []}]
    project.save_graph(g)
    assert r1["value"] not in ("1", "1Ω")
    rep = check(Design.from_config(project.config()), project.config())
    assert [w for w in rep.warnings if w[0] == "DEF.derive"] == []
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + "\n[beta]\ndsl = true\n")
    rep = check(Design.from_config(project.config()), project.config())
    assert [m for c, m in rep.warnings if c == "DEF.derive"][0].startswith("R1: value ")

@pytest.mark.parametrize("argv", [["graph", "fmt"], ["graph", "derive"], ["graph", "sysml"], ["graph", "kerml"],
                                  ["graph", "convert", "--to", "circuit"], ["graph", "json", "--map", "m.json"],
                                  ["block", "add", "led", "--as", "S", "--connect", "in=SIG", "--set", "i=4mA"]])
def test_every_command_of_the_dsl_refuses_without_the_switch(project, capsys, argv):
    before = (project.root / "hardware" / "graph.json").read_bytes()
    assert cli.main([*argv, "--config", str(project.root / "edakit.toml")]) == 1
    err = capsys.readouterr().err
    assert "the explorative DSL, a beta – a project switches it on with [beta] dsl = true" in err
    assert (project.root / "hardware" / "graph.json").read_bytes() == before
    assert not (project.root / "hardware" / "graph.circuit").exists()


def test_the_help_shows_nothing_of_the_dsl(capsys):
    ap = cli.build_parser()
    assert "lsp" not in ap.format_usage() and "lsp" not in ap.format_help()
    graph = ap._subparsers._group_actions[0].choices["graph"].format_help()
    block = ap._subparsers._group_actions[0].choices["block"].format_help()
    for word in ("fmt", "derive", "sysml", "kerml", "--to", "--out", "--map", ".circuit", "circuit language"):
        assert word not in graph, word
    assert "--set" not in block and "--part" not in block



@pytest.mark.parametrize("argv, said", [
    (["bogus"], "argument command: invalid choice: 'bogus' (choose from 'version', "),
    (["graph", "bogus"], "argument action: invalid choice: 'bogus' (choose from 'show', 'json', 'convert')\n"),
    (["graph", "convert", "--to", "x"], "unrecognized arguments: --to"),
    (["graph", "show", "U1", "extra"], "unrecognized arguments: extra"),
    (["block", "add", "led", "--sets", "i=4mA"], "unrecognized arguments: --sets i=4mA"),
])
def test_an_error_of_the_command_line_is_main_s(capsys, argv, said):
    """A command line that names nothing of the DSL is parsed as on main: its error says nothing of the DSL, and no
    command takes more arguments than it declares."""
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    err = capsys.readouterr().err
    assert e.value.code == 2 and said in err, err
    assert not re.search(r"\blsp\b|fmt|derive|sysml|kerml|circuit", err), err


def test_the_dsl_s_words_open_the_dsl_s_parser():
    assert not any(cli.dsl_words(a) for a in (["graph", "show", "U1"], ["order", "--out", "x"],
                                               ["export", "--out=x"], ["graph", "convert", "--to", "x"], []))
    assert all(cli.dsl_words(a) for a in (["lsp"], ["graph", "fmt"], ["graph", "convert", "--to", "circuit"],
                                           ["graph", "convert", "--to=toml"], ["graph", "json", "--map", "m"],
                                           ["block", "add", "led", "--set", "i=4mA"]))

def test_the_language_server_answers_one_line_without_the_switch(tmp_path):
    from edakit.lang import server
    f = tmp_path / "x.circuit"
    f.write_text("part R1 resistor X\n")
    (tmp_path / "edakit.toml").write_text('[project]\nname = "x"\n')
    [d] = server.diagnostics(f, f.read_text())
    assert d["line"] == 0 and "[beta] dsl = true" in d["message"]
    assert server.hover(f, f.read_text(), 0, 6) is None and server.completion(f, f.read_text(), 0, 0) == []
    assert server.formatted(f, f.read_text()) is None
    assert beta.dsl_of(f) is False and beta.dsl_of(ROOT / "edakit" / "blocks" / "led.circuit") is True


def test_the_session_start_names_the_dsl_only_where_it_is_on(project):
    from edakit import agreements
    toml = project.root / "edakit.toml"
    context = agreements.hook({"cwd": str(project.root)})["hookSpecificOutput"]["additionalContext"]
    assert "explorative DSL" not in context and ".circuit" not in context
    toml.write_text(toml.read_text() + "\n[beta]\ndsl = true\n")
    context = agreements.hook({"cwd": str(project.root)})["hookSpecificOutput"]["additionalContext"]
    assert "The explorative DSL is switched on ([beta] dsl = true)" in context and "docs/dsl/README.md" in context


def test_the_catalog_and_edakit_rules_leave_the_dsl_s_codes_out(capsys):
    beta_codes = [n for n in catalog.codes() if catalog.beta(n)]
    assert sorted(beta_codes) == ["DEF.derive", "SYNC.graph"]
    assert cli.main(["rules"]) == 0
    out = capsys.readouterr().out
    assert not any(n in out for n in beta_codes) and "DEF –" not in out
    assert cli.main(["explain", "DEF.derive"]) == 0 and "window" in capsys.readouterr().out   # by name it explains
    index = (ROOT / "docs" / "catalog" / "index.html").read_text(encoding="utf-8")
    assert not any(f'id="{n}"' in index for n in beta_codes) and not (ROOT / "docs" / "catalog" / "def.html").exists()
    tables = (ROOT / "docs" / "catalog" / "tables.html").read_text(encoding="utf-8")
    assert "IEC 60063" not in tables                                              # the E-series: the DSL's table


def test_the_dsl_is_a_tab_of_its_own_and_the_rest_says_nothing_of_it():
    import importlib.util
    spec = importlib.util.spec_from_file_location("pages", ROOT / "docs" / "pages.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    nav = dict(mod.NAV)
    assert [src for src, _ in nav["Explorative DSL"]] == [
        "docs/dsl/README.md", "docs/dsl/language.md", "docs/dsl/derivations.md", "docs/dsl/variants.md",
        "docs/dsl/sysml.md", "docs/dsl/editor.md"]
    assert not any("circuit" in src or "dsl" in src for src, _ in nav["Handbook"])
    assert all('!!! warning "A beta"' in (ROOT / src).read_text(encoding="utf-8") for src, _ in nav["Explorative DSL"])
    silent = ["README.md", *(f"handbook/{p.name}" for p in (ROOT / "handbook").glob("*.md")),
              *(p.relative_to(ROOT).as_posix() for p in (ROOT / "skills").glob("*/SKILL.md")),
              *(p.relative_to(ROOT).as_posix() for p in (ROOT / "agents").glob("*.md"))]
    word = re.compile(r"circuit language|\.circuit\b|explorative DSL|\[beta\]|edakit lsp", re.I)
    assert [f for f in silent if word.search((ROOT / f).read_text(encoding="utf-8"))] == []
