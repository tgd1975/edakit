"""What is ordered, published as a GitHub release – `edakit release publish` (handbook 8.3): offline, with the example
in a git repository of its own, a bare repository as its remote and a fake gh on the PATH (fake_gh.py) that writes
down its arguments and keeps the releases it made."""

import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fake_gh import flags

from edakit import cli, config
from edakit.release import fab, gate

OLD, NEW = "20261030-232043", "20261031-101500"
TODAY = dt.date.today().isoformat()
FAKE = Path(__file__).resolve().parent / "fake_gh.py"
LAYERS = {"Gerber_TopLayer.GTL": "t1", "Drill_PTH_Through.DRL": "d1", "bom_{b}.csv": "b1", "cpl_{b}.csv": "c1"}


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def commit(root, push=True):
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "change")
    if push:
        git(root, "push", "-q")


class Gh:
    """The fake gh's record: every call, the releases it made."""

    def __init__(self, state):
        self.state = state

    def calls(self):
        f = self.state / "calls.jsonl"
        return [json.loads(line) for line in f.read_text().splitlines()] if f.exists() else []

    def created(self):
        return [c for c in self.calls() if c[:2] == ["release", "create"]]

    def release(self, tag):
        return next(json.loads(m.read_text()) for m in sorted(self.state.glob("releases/*/meta.json"))
                    if json.loads(m.read_text())["tagName"] == tag)


@pytest.fixture
def gh(project, tmp_path, monkeypatch):
    """The example committed in a git repository and pushed to a bare one, gate runs ignored as edakit's .gitignore
    has it; the fake gh first on the PATH, GitHub's tags in the bare repository."""
    for k, v in {"GIT_CONFIG_GLOBAL": str(tmp_path / "no-gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
                 "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                 "GIT_COMMITTER_EMAIL": "t@t", "FAKE_GH": str(tmp_path / "gh"),
                 "FAKE_GH_REMOTE": str(tmp_path / "remote.git")}.items():
        monkeypatch.setenv(k, v)
    root = project.root
    (root / ".gitignore").write_text("build/\n")
    git(tmp_path, "init", "-q", "--bare", "-b", "main", "remote.git")
    git(root, "init", "-q", "-b", "main")
    git(root, "remote", "add", "origin", str(tmp_path / "remote.git"))
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "led-bar")
    git(root, "push", "-q", "-u", "origin", "main")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "gh").write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" "$@"\n')
    (bin_ / "gh").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")
    return Gh(tmp_path / "gh")


def released(cfg, run, board="main", layers=None, gerber=None):
    """A RELEASED gate run of the board as gate.main leaves it after stage F: the upload files, the polarity sheet and
    the manifest with fab layers (the manufacturing files as the maker builds from them) and fab hash."""
    out = cfg.reports / run
    d = out / "fab" / board
    d.mkdir(parents=True)
    (d / f"gerber_{board}.zip").write_bytes(gerber or f"gerber of {board}, exported {run}".encode())
    (d / f"bom_{board}.csv").write_text("Comment,Designator,Footprint,LCSC Part #\n22uF,C2,C0805,C45783\n")
    (d / f"cpl_{board}.csv").write_text("Designator,Mid X,Mid Y,Layer,Rotation\nC2,20,9,Top,0\n")
    (out / "fab" / f"polarity_{board}.png").write_bytes(f"polarity sheet of {board}".encode())
    layers = {board: {k.format(b=board): v for k, v in (layers or LAYERS).items()}}
    head = {"time": run, "git_commit": git(cfg.root, "rev-parse", "--short", "HEAD"), "git_dirty": False,
            "graph_sha256": "g", "state_sha256": "s1", "layout_sha256": "l", "graph_version": "1.0",
            "fab_method": fab.FAB_METHOD, "fab_layers": layers, "fab_sha256": fab.fab_hash(layers)}
    gate.write_manifest(cfg, out, head, "RELEASED")
    return d


def variant(project, name="v2"):
    """A variant below the example – a folder with an edakit.toml of its own and the board <name> (handbook 10.4)."""
    d = project.root / "variants" / name
    d.mkdir(parents=True)
    (d / "edakit.toml").write_text(f'[project]\nname = "led-bar"\ngraph = "../../hardware/graph.json"\n'
                                   f'parts = "../../hardware/parts"\n\n[boards.{name}]\ntitle = "LED bar {name}"\n')
    return config.load(d / "edakit.toml")


def publish(cfg, *args):
    return cli.main(["release", "publish", *args, "--config", str(cfg.root / "edakit.toml")])


def sums_of(folder):
    return {n: d for d, n in (line.split("  ") for line in (folder / "SHA256SUMS").read_text().splitlines())}


def row(notes, board):
    return next(line for line in notes.splitlines() if line.startswith(f"| {board} "))


def test_dry_run_stages_the_order_files_and_writes_the_notes(project, gh, capsys):
    cfg = project.config()
    released(cfg, NEW)
    assert publish(cfg, "--dry-run") == 0
    dest = project.root / "build" / "publish" / TODAY
    assert sorted(p.name for p in dest.iterdir()) == ["SHA256SUMS", "bom_main.csv", "cpl_main.csv", "gerber_main.zip",
                                                      "manifest_main.json", "notes.md", "polarity_main.png"]
    sums = sums_of(dest)
    assert sums == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.iterdir()
                    if p.name not in ("SHA256SUMS", "notes.md")}
    assert (dest / "manifest_main.json").read_bytes() == (cfg.reports / NEW / "fab" / "manifest.json").read_bytes()
    notes = (dest / "notes.md").read_text()
    fab_sha = json.loads((dest / "manifest_main.json").read_text())["fab_sha256"]
    head = git(project.root, "rev-parse", "HEAD")
    assert row(notes, "main").startswith(f"| main | {NEW} | [{head[:7]}](https://github.com/example/led-bar/commit/")
    assert f"`{fab_sha[:12]}…`" in row(notes, "main") and row(notes, "main").endswith("| first release |")
    assert f"[{head[:7]}](https://github.com/example/led-bar/commit/{head})" in notes
    assert f"(https://github.com/example/led-bar/blob/{head}/hardware/graph.json)" in notes   # absolute links only
    assert "](hardware/" not in notes and "](./" not in notes
    assert "Purpose: private – built for oneself" in notes and "support, not legal advice" in notes
    assert "**Pre-release**" in notes and "gerber_<board>.zip" in notes
    assert not gh.created()
    assert f"dry run: nothing uploaded – {dest}" in capsys.readouterr().out


def test_a_changed_byte_stops_before_the_staging_and_gh(project, gh, capsys):
    cfg = project.config()
    zipped = released(cfg, NEW) / "gerber_main.zip"
    data = bytearray(zipped.read_bytes())
    data[0] ^= 1
    zipped.write_bytes(bytes(data))
    assert publish(cfg) == 2
    out = capsys.readouterr()
    assert "FAIL gerber_main.zip: unknown" in out.out and "refused by release verify" in out.err
    assert not (project.root / "build" / "publish").exists()
    assert gh.calls() == []


def test_a_variant_without_a_current_release_stops_with_its_name(project, gh, capsys):
    cfg = project.config()
    variant(project)
    commit(project.root)
    released(cfg, NEW)
    assert publish(cfg, "--dry-run") == 2
    out = capsys.readouterr()
    assert "led-bar (variants/v2): no current release" in out.err
    assert gh.calls() == [] and not (project.root / "build" / "publish").exists()
    # [release] publish.variants = false: the project alone
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + "publish = { variants = false }\n")
    commit(project.root)
    assert publish(project.config(), "--dry-run") == 0
    assert "v2" not in (project.root / "build" / "publish" / TODAY / "notes.md").read_text()


def test_publish_needs_a_clean_tree_on_the_remote_and_makes_a_pre_release_on_head(project, gh, capsys):
    cfg = project.config()
    released(cfg, NEW)
    readme = project.root / "README.md"
    readme.write_text(readme.read_text() + "\nOne more line.\n")
    assert publish(cfg) == 1
    assert "uncommitted changes" in capsys.readouterr().err
    commit(project.root, push=False)
    assert publish(cfg) == 1
    assert "HEAD is not on origin/main – push first" in capsys.readouterr().err
    assert gh.calls() == []
    git(project.root, "push", "-q")
    assert publish(cfg) == 0
    head = git(project.root, "rev-parse", "HEAD")
    (create,) = gh.created()
    opts, pos = flags(create[2:])
    dest = project.root / "build" / "publish" / TODAY
    assert pos[0] == TODAY and opts["--prerelease"] == [True] and opts["--target"] == [head]
    assert "--draft" not in opts and opts["--notes-file"] == [str(dest / "notes.md")]
    assert sorted(Path(f).name for f in pos[1:]) == sorted(p.name for p in dest.iterdir() if p.name != "notes.md")
    rel = gh.release(TODAY)
    assert rel["name"] == f"Manufacturing files {TODAY}" and rel["isPrerelease"] and rel["target"] == head
    assert git(project.root, "rev-parse", f"{TODAY}^{{commit}}") == head      # the tag, fetched back
    out = capsys.readouterr().out
    assert f"upload to the maker from: {dest}" in out and f"edakit release publish --built {TODAY}" in out


def test_a_draft_needs_no_guards_and_makes_no_tag(project, gh, capsys):
    cfg = project.config()
    released(cfg, NEW)
    (project.root / "README.md").write_text("changed, not committed\n")
    assert publish(cfg, "--draft") == 0
    (create,) = gh.created()
    opts, pos = flags(create[2:])
    assert pos[0] == f"draft-{TODAY}" and opts["--draft"] == [True] and "--target" not in opts
    assert "gh release delete draft-" in capsys.readouterr().out
    assert "**Draft" in gh.release(f"draft-{TODAY}")["notes"]


def test_a_second_publish_names_the_board_that_changed(project, gh, capsys):
    """The boards of the variant are exported again – another ZIP, the same fab layers: unchanged; the main board's
    copper changed: changed. The decisions since the first release are listed, the earlier ones not."""
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + 'publish = { decisions = "docs/decisions.md" }\n')
    log = project.root / "docs" / "decisions.md"
    log.parent.mkdir()
    log.write_text("# Decisions\n\n## D-1 Five boards (2026-10-20)\n\nText.\n")
    cfg, vcfg = project.config(), variant(project)
    commit(project.root)
    released(cfg, OLD)
    released(vcfg, OLD, board="v2")
    assert publish(cfg) == 0
    log.write_text(log.read_text() + "\n## D-2 Black solder mask (2026-10-31)\n\nText.\n")
    commit(project.root)
    released(cfg, NEW, layers={**LAYERS, "Gerber_TopLayer.GTL": "t2"})
    released(vcfg, NEW, board="v2", gerber=b"the same board, exported once more")
    assert publish(cfg) == 0
    assert f"tag {TODAY}: the remote has it – {TODAY}-2" in capsys.readouterr().out
    notes = gh.release(f"{TODAY}-2")["notes"]
    assert row(notes, "main").endswith(f"| changed since {TODAY} |")
    assert row(notes, "v2 (variants/v2)").endswith(f"| unchanged since {TODAY} |")
    assert "Purpose: private – built for oneself" in notes          # the variant shares the graph: one line
    assert f"Decisions since {TODAY} ([docs/decisions.md](https://github.com/example/led-bar/blob/" in notes
    assert "- D-2 Black solder mask (2026-10-31)" in notes and "D-1 Five" not in notes
    assert sums_of(project.root / "build" / "publish" / f"{TODAY}-2")["gerber_v2.zip"] != \
        sums_of(project.root / "build" / "publish" / TODAY)["gerber_v2.zip"]       # the bytes differ, the board not


def test_without_fab_layers_the_sums_decide(project, gh):
    """Manifests from before the fab hash: the SHA-256 of the upload files against SHA256SUMS of the previous release."""
    cfg = project.config()
    d = released(cfg, OLD)
    m = cfg.reports / OLD / "fab" / "manifest.json"
    m.write_text(json.dumps({k: v for k, v in json.loads(m.read_text()).items() if not k.startswith("fab_")}))
    assert publish(cfg) == 0
    for name in ("gerber_main.zip", "bom_main.csv", "cpl_main.csv"):     # the same files in a new run
        (cfg.reports / NEW / "fab" / "main").mkdir(parents=True, exist_ok=True)
        (cfg.reports / NEW / "fab" / "main" / name).write_bytes((d / name).read_bytes())
    gate.write_manifest(cfg, cfg.reports / NEW, {"time": NEW, "git_commit": "abc1234", "git_dirty": False,
                                                 "graph_sha256": "g", "state_sha256": "s1", "layout_sha256": "l"},
                        "RELEASED")
    assert publish(cfg) == 0
    assert row(gh.release(f"{TODAY}-2")["notes"], "main").endswith(f"| unchanged since {TODAY} |")


def test_built_drops_the_pre_release_mark(project, gh, capsys):
    cfg = project.config()
    released(cfg, NEW)
    assert publish(cfg) == 0
    assert gh.release(TODAY)["isPrerelease"] is True
    assert publish(cfg, "--built", TODAY) == 0
    assert gh.calls()[-1] == ["release", "edit", TODAY, "--prerelease=false"]
    assert gh.release(TODAY)["isPrerelease"] is False


def test_without_gh_or_its_login_one_sentence(project, gh, capsys, monkeypatch, tmp_path):
    cfg = project.config()
    released(cfg, NEW)
    (tmp_path / "gh" / "logged_out").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "gh" / "logged_out").write_text("")
    assert publish(cfg, "--dry-run") == 1
    assert capsys.readouterr().err == "edakit release publish: gh is not logged in – gh auth login\n"
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert publish(cfg, "--dry-run") == 1
    assert capsys.readouterr().err == ("edakit release publish: gh not found – install the GitHub CLI and log in "
                                       "(gh auth login)\n")


def test_a_variant_with_its_own_purpose_gets_a_line_of_its_own(project, gh):
    cfg, vcfg = project.config(), variant(project)
    graph = json.loads(project.graph_file.read_text())
    graph["graph"]["purpose"] = {"use": "gift", "market": "EU", "notes": "For a friend."}
    (vcfg.root / "hardware").mkdir()
    (vcfg.root / "hardware" / "graph.json").write_text(json.dumps(graph))
    toml = vcfg.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("../../hardware/graph.json", "hardware/graph.json"))
    commit(project.root)
    released(cfg, NEW)
    released(config.load(toml), NEW, board="v2")
    assert publish(cfg, "--dry-run") == 0
    notes = (project.root / "build" / "publish" / TODAY / "notes.md").read_text()
    assert "Purpose, per project:\n\n- led-bar: private – built for oneself" in notes
    assert "- variants/v2: gift – given away ([purpose in the graph](https://github.com/example/led-bar/blob/" in notes
    assert "/variants/v2/hardware/graph.json)): For a friend." in notes
    assert "\n\nThe regulatory review M-6 is support, not legal advice" in notes


def test_a_decision_log_that_is_not_there_stops_at_once(project, gh, capsys):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + 'publish = { decisions = "docs/decisions.md" }\n')
    assert publish(project.config(), "--dry-run") == 1
    assert "[release] publish.decisions: docs/decisions.md not found" in capsys.readouterr().err
    assert gh.calls() == []


@pytest.mark.parametrize("release, said", [
    ('archive = "svn"', '[release] archive must be "none"'),
    ("publish = { variant = true }", "[release] publish: unknown key 'variant'"),
    ('publish = { variants = "yes" }', "[release] publish.variants: true or false"),
    ("publish = { decisions = 3 }", "[release] publish.decisions: the path of the decision log"),
])
def test_archive_and_publish_are_checked(project, release, said):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + release + "\n")
    with pytest.raises(config.ConfigError, match=said.replace("[", r"\[").replace("]", r"\]")):
        project.config()


# --- [release] archive (gate runs are build output by default) ------------------------------------------------------

def test_release_current_names_an_untracked_run_only_with_archive_git(project, gh, capsys):
    cfg = project.config()
    released(cfg, NEW)
    assert cli.main(["release", "current", "--config", str(project.root / "edakit.toml")]) == 0
    assert "not in git yet" not in capsys.readouterr().out                       # default "none": build output
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + 'archive = "git"\n')
    assert cli.main(["release", "current", "--config", str(toml)]) == 0
    assert f"  not in git yet: git add -f build/release/{NEW} – with the superseded manifests" in capsys.readouterr().out
    git(project.root, "add", "-f", f"build/release/{NEW}")
    commit(project.root)
    assert cli.main(["release", "current", "--config", str(toml)]) == 0
    assert "not in git yet" not in capsys.readouterr().out


def test_the_protocol_names_the_archive_setting(project):
    head = {"time": "2026-10-31T10:00:00+01:00", "tester": "t", "graph_version": "1", "graph_date": "d",
            "graph_sha256": "g", "state_sha256": "s", "layout_sha256": "l", "git_commit": "c", "git_dirty": False,
            "tools": {"python": "3", "edakit": "0", "ngspice": "n", "easyeda-mcp-pro": "m"}}
    sim = {"checks": [], "scenarios": []}
    for setting, said in (("", "| Archive | `none` ([release] archive): the run is build output, not committed"),
                          ('archive = "git"\n', "| Archive | `git` ([release] archive): a released run is committed – "
                                                "`git add -f build/release/run`")):
        toml = project.root / "edakit.toml"
        toml.write_text(toml.read_text() + setting)
        cfg = project.config()
        out = cfg.reports / "run"
        out.mkdir(parents=True, exist_ok=True)
        signoff, notes = gate.load_signoff(cfg, head)
        gate.write_protocol(cfg, out, head, [], sim, signoff, notes, "NOT RELEASED", [], set("PGE"), gate.STAGES, {})
        assert said in (out / "protocol.md").read_text()
