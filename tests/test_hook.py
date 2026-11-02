"""`edakit hook`: the project's pre-commit hook – edakit's block written and renewed by `install` (the project's own
steps kept), `check` for the session start, `run` with the steps of each configuration whose files are staged
(edakit/hook.py, handbook 2.7)."""

import os
import stat
import subprocess

from edakit import agreements
from edakit import hook as h


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def _repo(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "edakit.toml").write_text('[project]\nname = "a"\n')
    return tmp_path


def test_the_steps_of_each_configuration_whose_files_are_staged():
    configs = [{"path": "edakit.toml", "dir": "", "inputs": ["docs/hardware.md"], "toml_graph": False,
                "firmware": True, "docs": False},
               {"path": "variants/tht/edakit.toml", "dir": "variants/tht", "inputs": [], "toml_graph": True,
                "firmware": False, "docs": True}]
    assert h.plan(["README.md"], configs) == []
    main = h.plan(["docs/hardware.md"], configs)
    assert [(c, s) for c, s in main] == [("edakit.toml", [["check"], ["sim"], ["firmware", "--check"]])]
    # the main project's hardware/ is read by every variant; a variant's own files only by it
    assert [c for c, _ in h.plan(["hardware/art/logo.svg"], configs)] == ["edakit.toml", "variants/tht/edakit.toml"]
    tht = h.plan(["variants/tht/hardware/graph.toml"], configs)
    assert tht == [("variants/tht/edakit.toml", [["check"], ["sim"], ["graph", "json", "--check"], ["docs"]])]


def test_install_writes_the_hook_and_activates_it(tmp_path):
    root = _repo(tmp_path)
    assert {p["what"] for p in h.check(root)} == {"missing"}
    done = h.install(root)
    f = root / ".githooks" / "pre-commit"
    text = f.read_text()
    assert text.startswith("#!/usr/bin/env bash\n") and h.BEGIN in text and h.END in text and "hook run" in text
    assert f.stat().st_mode & stat.S_IXUSR
    assert _git(root, "config", "core.hooksPath") == ".githooks"
    assert any("written" in x for x in done) and h.check(root) == []


def test_install_keeps_the_projects_own_steps_and_names_its_edakit_calls(tmp_path):
    root = _repo(tmp_path)
    (root / ".githooks").mkdir()
    own = ("#!/usr/bin/env bash\n# pytree's hook\nuv run pytest -q tests || exit 1\n"
           'echo "pre-commit: edakit check …"\nhardware/edakit.sh check 2>&1 | cat >/tmp/p-edakit-check.log || exit 1\n'
           "tail -1 /tmp/p-edakit-check.log\nchanged=$(git diff --cached --name-only -- edakit.toml hardware docs)\n")
    (root / ".githooks" / "pre-commit").write_text(own)
    _git(root, "config", "core.hooksPath", ".githooks")
    assert {p["what"] for p in h.check(root)} == {"no block"}
    done = h.install(root)
    text = (root / ".githooks" / "pre-commit").read_text()
    assert text.index("# pytree's hook") < text.index(h.BEGIN) < text.index("uv run pytest")   # after the header
    assert "uv run pytest -q tests" in text and "hardware/edakit.sh check" in text           # kept, not removed
    named = [x for x in done if "outside the block" in x]
    assert len(named) == 1 and "hardware/edakit.sh check" in named[0]     # the call, not the message or the log
    assert "current" in " ".join(h.install(root))


def test_an_outdated_block_is_renewed_and_an_inactive_hook_named(tmp_path):
    root = _repo(tmp_path)
    h.install(root)
    f = root / ".githooks" / "pre-commit"
    f.write_text(f.read_text().replace("hook run", "hook run --old"))
    assert {p["what"] for p in h.check(root)} == {"outdated"}
    h.install(root)
    assert h.check(root) == []
    _git(root, "config", "--unset", "core.hooksPath")
    assert {p["what"] for p in h.check(root)} == {"inactive"}


def test_run_runs_the_steps_and_blocks_on_a_failure(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    (root / "hardware").mkdir()
    (root / "hardware" / "graph.json").write_text("{}")
    _git(root, "add", "hardware/graph.json")
    calls = []

    def fake(cfg, step):
        calls.append((cfg, tuple(step)))
        return (1, "J1: a finding") if step == ["sim"] else (0, "ok")

    monkeypatch.setattr(h, "_step", fake)
    assert h.run(root) == 2
    out = capsys.readouterr().out
    assert calls[:2] == [("edakit.toml", ("check",)), ("edakit.toml", ("sim",))]
    assert "main: edakit sim failed" in out and "J1: a finding" in out and "commit blocked" in out


def test_the_session_start_names_a_missing_hook(tmp_path):
    root = _repo(tmp_path)
    line = agreements.hooked(root / "edakit.toml")
    assert line and "edakit hook install" in line[0]
    h.install(root)
    assert agreements.hooked(root / "edakit.toml") == []
    assert agreements.hooked(tmp_path / "nowhere" / "edakit.toml") == []        # outside a git repository: nothing
    examples = h.toplevel(__import__("pathlib").Path(__file__).parent) / "examples" / "coin-cell-led" / "edakit.toml"
    assert agreements.hooked(examples) == []                                     # edakit's own examples


def test_the_hook_finds_edakit_without_the_path(tmp_path):
    """A commit by hand outside Claude Code: no edakit on the PATH – the block takes the plugin in effect."""
    root = _repo(tmp_path)
    h.install(root)
    plugin = tmp_path / "plugin"
    (plugin / "bin").mkdir(parents=True)
    (plugin / "bin" / "edakit").write_text("#!/bin/sh\necho \"ran $*\"\n")
    (plugin / "bin" / "edakit").chmod(0o755)
    cfg = tmp_path / "claude" / "plugins"
    cfg.mkdir(parents=True)
    (cfg / "installed_plugins.json").write_text(
        '{"plugins": {"edakit@edakit": [{"scope": "user", "installPath": "%s"}]}}' % plugin)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "CLAUDE_CONFIG_DIR": str(tmp_path / "claude")}
    r = subprocess.run(["bash", str(root / ".githooks" / "pre-commit")], cwd=root, env=env, capture_output=True,
                       text=True)
    assert r.returncode == 0 and "ran hook run" in r.stdout
    (plugin / "bin" / "edakit").write_text("#!/bin/sh\necho finding\nexit 2\n")
    r = subprocess.run(["bash", str(root / ".githooks" / "pre-commit")], cwd=root, env=env, capture_output=True,
                       text=True)
    assert r.returncode == 2 and "finding" in r.stdout                           # the exit code through the pipe
    env.pop("CLAUDE_CONFIG_DIR")
    r = subprocess.run(["bash", str(root / ".githooks" / "pre-commit")], cwd=root, env={**env, "HOME": "/nonexistent"},
                       capture_output=True, text=True)
    assert r.returncode == 1 and "edakit not found" in r.stdout + r.stderr
    assert os.environ.get("EDAKIT") is None
