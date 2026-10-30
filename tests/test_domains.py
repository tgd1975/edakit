"""Domains and profiles (rules-at-scale.md, step 3): which findings a project's domains switch on, their severities,
the suggested domains, the reviewers' questions."""

import json

import pytest

from edakit import config, engines, profile
from edakit.design import Design


def test_domain_files_lint_clean():
    assert profile.lint() == []


def test_lint_names_unknown_codes(monkeypatch):
    bad = {"core": {"domain": {"name": "core", "about": "x"}, "hints": {"apply": ["HINT.nothing"]}},
           "x": {"domain": {"name": "y"}, "switch": {"on": ["REQ.nope:cc"]}, "severity": {"LIM.v/foo": "fatal"},
                 "facts": {"kind": {"opamp": ["values.x"]}}, "review": {"mechanical": []}}}
    monkeypatch.setattr(profile, "domains", lambda: bad)
    text = "\n".join(profile.lint())
    for want in ("hint HINT.nothing", "domains/x.toml: [domain] needs name", "switch REQ.nope:cc",
                 "severity LIM.v/foo – no code/grade", "= 'fatal'", "facts.kind.opamp", "review.mechanical"):
        assert want in text, want


def test_strictest_severity_wins():
    t = {}
    for sev in ("note", "warning", "error", "note"):
        profile.strictest(t, "LIM.v", sev)
    assert t == {"LIM.v": "error"}


def usb_c(project):
    """led-bar with a USB-C receptacle whose CC pins have no resistors."""
    project.use_library_part("C456012")
    g = project.graph()
    entry = project.part("C456012")
    pins = {n: p["name"] for n, p in entry["pins"].items()}
    g["graph"]["components"].append({"designator": "J9", "lcsc": "C456012", "part": entry["mpn"], "pins": pins,
                                     "nc": [n for n, p in entry["pins"].items() if p.get("role") not in ("cc1", "cc2")]})
    for n, p in entry["pins"].items():
        if p.get("role") in ("cc1", "cc2"):
            g["graph"]["nets"].append({"name": f"CC_{n}", "v": [0, 5], "pins": [f"J9.{n}"]})
    project.save_graph(g)


def findings(project):
    cfg = project.config()
    return engines.run(Design.from_config(cfg), cfg).findings


def set_domains(project, names):
    """[project] domains = names; None: without the key."""
    toml = project.root / "edakit.toml"
    lines = [x for x in toml.read_text().splitlines(keepends=True) if not x.startswith("domains = ")]
    text = "".join(lines)
    if names is not None:
        text = text.replace("[project]\n", f"[project]\ndomains = {json.dumps(names)}\n", 1)
    toml.write_text(text)


def test_without_the_key_the_suggested_domains_are_on(project):
    usb_c(project)
    assert "usb" in profile.suggested(Design.from_config(project.config()))
    assert any(f.code == "REQ.missing" and f.topic == "cc" for f in findings(project))


def test_a_domain_left_out_is_silent_but_noted(project):
    usb_c(project)
    set_domains(project, [])
    fs = findings(project)
    assert not any(f.topic == "cc" for f in fs)
    notes = [f for f in fs if f.code == "STRUCT.domain"]
    assert [f.place for f in notes] == ["usb"] and notes[0].severity == "note"
    set_domains(project, ["usb"])
    fs = findings(project)
    assert any(f.topic == "cc" for f in fs) and not any(f.code == "STRUCT.domain" for f in fs)


def test_purpose_grades_the_radio_domain(project):
    p = project.part("C41407547")
    p["compliance"]["radio"] = {"bands_mhz": [[2400, 2483.5]], "max_dbm": 20.5, "antenna_dbi": 2}
    project.save_part("C41407547", p)
    g = project.graph()
    g["graph"]["purpose"] = {"use": "sale"}
    project.save_graph(g)
    fs = [f for f in findings(project) if f.code == "LIM.eirp"]
    assert fs and all(f.severity == "warning" for f in fs)
    g["graph"]["purpose"] = {"use": "private"}
    project.save_graph(g)
    assert all(f.severity == "note" for f in findings(project) if f.code == "LIM.eirp")


def test_unknown_domain_is_a_config_error(project):
    set_domains(project, ["audio"])
    with pytest.raises(config.ConfigError, match="audio – no domain of edakit/domains"):
        project.config()


def test_domains_command_and_review_questions(project, capsys):
    from edakit import cli
    usb_c(project)
    assert cli.main(["domains", "--config", str(project.root / "edakit.toml")]) == 0
    out = capsys.readouterr().out
    assert "usb – USB-C receptacles" in out and "(suggested by the graph)" in out and "core – " in out
    assert cli.main(["domains", "--review", "electrical", "--config", str(project.root / "edakit.toml")]) == 0
    out = capsys.readouterr().out
    assert "What an off-board module brings" in out and "Several sources" in out
