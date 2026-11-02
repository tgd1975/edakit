"""`edakit version`: what runs, what the plugin installed per scope, the newest tag, the changelog in between with
its "When updating:" lines, and where the project pins edakit (edakit/update.py, handbook 2.3)."""

import json

from edakit import __version__, cli
from edakit import update as u

PLUGINS = {"version": 2, "plugins": {"edakit@edakit": [
    {"scope": "user", "version": "1.0.3", "installPath": "/c/edakit/1.0.3"},
    {"scope": "project", "projectPath": "/p/pytree", "version": "1.0.2", "installPath": "/c/edakit/1.0.2"},
    {"scope": "project", "projectPath": "/p/bell", "version": "1.0.3", "installPath": "/c/edakit/1.0.3"},
], "other@x": [{"scope": "user", "version": "9.9.9"}]}}

CHANGELOG = """# Changelog

Intro text.

## 1.1.0 – 2026-11-03

- **When updating:** run `edakit convert --write`, then sign
  M-2 again.
- A new check.

## 1.0.5 – 2026-11-02

- Six more diagrams.

## 1.0.3 – 2026-11-02

- A fix.

## 1.0.2 – 2026-11-02

- cart confirm.
"""

LS_REMOTE = """d02c6bd16de8861dcc92b517a9c93e0738c3e596\trefs/tags/v1.0.2
246d610a5106bf7cb0c9177667c86488182e20eb\trefs/tags/v1.0.3
33c0c1bc66e1d060593b160cf86aa84faacfb21e\trefs/tags/v1.0.10
1111111111111111111111111111111111111111\trefs/tags/v1.0.10^{}
2222222222222222222222222222222222222222\trefs/tags/not-a-version
"""


def test_the_plugin_per_scope_and_the_one_in_effect_here():
    found = u.installed(PLUGINS, "/p/pytree")
    assert [(x["scope"], x["version"]) for x in found] == [("user", "1.0.3"), ("project", "1.0.2"),
                                                          ("project", "1.0.3")]
    assert [x["here"] for x in found] == [False, True, False]
    assert [x["here"] for x in u.installed(PLUGINS, "/p/other")] == [True, False, False]   # the user scope
    assert u.installed({}, "/p") == []


def test_the_newest_version_tag_by_number_not_by_text():
    tags = u.tags(LS_REMOTE)
    assert u.newest(tags) == "1.0.10"
    assert tags["246d610a5106bf7cb0c9177667c86488182e20eb"] == "1.0.3"
    assert tags["1111111111111111111111111111111111111111"] == "1.0.10"      # an annotated tag's commit
    assert u.newest({}) is None


def test_the_changelog_after_a_version_and_what_a_project_must_do():
    secs = u.between(CHANGELOG, "1.0.3", "1.1.0")
    assert [s["number"] for s in secs] == ["1.1.0", "1.0.5"]
    assert secs[0]["date"] == "2026-11-03"
    assert secs[0]["lines"][0] == "- **When updating:** run `edakit convert --write`, then sign M-2 again."
    assert u.todo(secs) == [("1.1.0", "run `edakit convert --write`, then sign M-2 again.")]
    assert u.between(CHANGELOG, "1.1.0", "1.1.0") == []


def test_the_places_that_pin_edakit(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps({"extraKnownMarketplaces": {"edakit": {
        "source": {"source": "github", "repo": "tgd1975/edakit", "ref": "v1.0.3"}}}}))
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "steps:\n  - run: uvx --from git+https://github.com/tgd1975/edakit@v1.0.2 edakit check\n")
    (tmp_path / "hardware").mkdir()
    (tmp_path / "hardware" / "edakit.sh").write_text(
        "EDAKIT_REV=246d610a5106bf7cb0c9177667c86488182e20eb\n"
        'exec uvx --from "git+https://github.com/tgd1975/edakit@$EDAKIT_REV" edakit "$@"\n')
    (tmp_path / "hardware" / "naehte.sh").write_text(   # reads the pin of edakit.sh – no pin of its own
        'uv run --with "edakit @ git+https://github.com/tgd1975/edakit@$(grep -oP x hardware/edakit.sh)"\n')
    (tmp_path / "README.md").write_text("Pin it: `uvx --from git+https://github.com/tgd1975/edakit@v0.2.0`\n")
    found = u.pins(tmp_path, u.tags(LS_REMOTE))
    assert [(p["where"], p["ref"], p["version"]) for p in found] == [
        (".claude/settings.json", "v1.0.3", "1.0.3"),
        (".github/workflows/ci.yml:2", "v1.0.2", "1.0.2"),
        ("hardware/edakit.sh:2", "246d610a5106bf7cb0c9177667c86488182e20eb", "1.0.3"),
    ]
    assert u.pins(tmp_path / "hardware", {}) [0]["version"] is None          # a commit without a known tag


def test_the_report_names_what_is_behind_and_what_to_do():
    state = {"running": "1.0.3", "path": "/c/edakit/1.0.3", "installed": u.installed(PLUGINS, "/p/pytree"),
             "newest": "1.1.0", "changes": u.between(CHANGELOG, "1.0.2", "1.1.0"), "pins": [], "required": []}
    lines, findings = u.report(state)
    text = "\n".join(lines)
    assert "edakit 1.0.3 runs" in text and "project /p/pytree: 1.0.2 (in effect here)" in text
    assert "newest: 1.1.0" in text
    assert "When updating" in text and "sign M-2 again" in text
    assert "--scope project" in text                                    # the update for the scope in effect
    assert findings and "1.0.2" in findings[0] and "1.1.0" in findings[0]


def test_the_report_of_an_edakit_up_to_date_and_of_one_offline():
    up = {"running": "1.1.0", "path": "/x", "installed": [{"scope": "user", "version": "1.1.0", "here": True}],
          "newest": "1.1.0", "changes": [], "pins": [], "required": []}
    lines, findings = u.report(up)
    assert findings == [] and any("up to date" in x for x in lines)
    lines, findings = u.report({**up, "newest": None, "offline": "no network"})
    assert findings == [] and any("newest: unknown (no network)" in x for x in lines)


def test_pins_that_disagree_or_differ_from_what_runs_are_findings():
    pins = [{"where": ".claude/settings.json", "ref": "v1.0.3", "version": "1.0.3"},
            {"where": "hardware/edakit.sh:2", "ref": "027a4587", "version": None}]
    state = {"running": "1.0.3", "path": "/x", "installed": [{"scope": "user", "version": "1.0.3", "here": True}],
             "newest": "1.0.3", "changes": [], "pins": pins, "required": []}
    _, findings = u.report(state)
    assert any("disagree" in f and "hardware/edakit.sh:2" in f for f in findings)


def test_a_requirement_the_running_edakit_does_not_meet():
    state = {"running": "1.0.3", "path": "/x", "installed": [], "newest": "1.0.3", "changes": [], "pins": [],
             "required": [("edakit.toml", ">=1.1")]}
    _, findings = u.report(state)
    assert findings == ['edakit.toml: [project] edakit asks for ">=1.1", 1.0.3 runs']


def test_edakit_version_offline_outside_a_project(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    assert cli.main(["version", "--offline"]) == 0
    out = capsys.readouterr().out
    assert f"edakit {__version__} runs" in out and "newest: unknown (--offline)" in out


def test_the_requirements_of_the_projects_edakit_toml_files(tmp_path):
    (tmp_path / "edakit.toml").write_text('[project]\nname = "a"\nedakit = ">=1.0"\n')
    (tmp_path / "variants" / "b").mkdir(parents=True)
    (tmp_path / "variants" / "b" / "edakit.toml").write_text('[project]\nname = "b"\n')
    assert u.required(tmp_path) == [("edakit.toml", ">=1.0")]
