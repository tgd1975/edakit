"""What went unchecked for lack of data (engines/coverage.py, maker-coverage FT-19): edakit check names it in one line,
--coverage lists it, the gate protocol has it in section 2 – no finding, since nobody looked."""

from edakit import cli, engines
from edakit.design import Design
from edakit.engines.coverage import coverage, summary


def gaps(project):
    d = Design.from_config(project.config())
    return coverage(d, engines.profile(d, project.config()))


def test_the_example_names_its_gaps(project):
    lines = [g.line() for g in gaps(project)]
    assert "LIM.t: D2, D3, D4, D5, D6, D7, D8, D9 – no rth_ja_k_per_w – no junction temperature (C2297)" in lines
    assert any(x.startswith("LVL.threshold: U2 – inputs without thresholds (vih, vil): SDI, CLK") for x in lines)
    assert summary(gaps(project)) == ("not checked for lack of data: LIM.t 11 parts, LVL.threshold 1 part – edakit check "
                                      "--coverage")


def test_a_limit_the_entry_lacks_is_a_gap(project):
    part = project.part("C45783")                           # C2's capacitor without its voltage limit
    part["limits"].pop("v_max_v")
    project.save_part("C45783", part)
    assert "LIM.v: C2 – no v_max_v – its voltage is not held to a limit (C45783)" in [g.line() for g in gaps(project)]


def test_thresholds_close_the_gap(project):
    part = project.part("C90107")
    part["values"].update(vih_ratio=0.7, vil_ratio=0.3)    # TI SLVS695D 7.3, as the catalog's LIM.range sources name it
    project.save_part("C90107", part)
    assert not any(g.code == "LVL.threshold" for g in gaps(project))


def test_check_prints_the_line_and_the_list(project, capsys):
    toml = str(project.root / "edakit.toml")
    assert cli.main(["check", "--config", toml]) == 0
    assert "not checked for lack of data: LIM.t 11 parts" in capsys.readouterr().out
    assert cli.main(["check", "--coverage", "--config", toml]) == 0
    out = capsys.readouterr().out
    assert "Not checked for lack of data:\n  LIM.t: D1 – no rth_ja_k_per_w" in out
    assert "not checked for lack of data:" not in out


def test_the_protocol_lists_the_gaps(project, monkeypatch):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["gate"]) == 2
    text = (sorted((project.root / "build" / "release").iterdir())[-1] / "protocol.md").read_text()
    two = text.split("## 2 ")[1].split("\n## ")[0]
    assert "Not checked for lack of data – no finding, nobody looked" in two
    assert "- LVL.threshold: U2 – inputs without thresholds" in two
