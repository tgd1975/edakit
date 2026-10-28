"""The working agreements of handbook 11.4 at session start: the plugin's SessionStart hook, run as the plugin runs it."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "edakit" / "agreements.py"
CHAPTER = ROOT / "handbook" / "11-working-with-claude.md"
EXAMPLE = Path(__file__).resolve().parent / "fixtures" / "led-bar"


@pytest.fixture(autouse=True)
def no_config_from_outside(monkeypatch):
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)


def run_hook(cwd, env=None):
    """The hook as Claude Code starts it: plain python3, the hook JSON on stdin, from another directory."""
    data = {"session_id": "s1", "hook_event_name": "SessionStart", "source": "startup", "cwd": str(cwd)}
    res = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(data), capture_output=True, text=True,
                         cwd="/", env=env, timeout=10)
    assert res.returncode == 0, res.stderr
    return res.stdout


def titles():
    """The bold title of every numbered item of 11.4."""
    text = CHAPTER.read_text(encoding="utf-8")
    body = re.search(r"^## 11\.4 .*?\n(.*?)(?=^## )", text, re.M | re.S).group(1)
    return re.findall(r"^\d+\. \*\*(.+?)\*\*", body, re.M)


def test_silent_outside_an_edakit_project(tmp_path):
    assert run_hook(tmp_path) == ""


def test_the_digest_names_every_agreement_of_11_4(tmp_path):
    shutil.copytree(EXAMPLE, tmp_path / "led-bar", ignore=shutil.ignore_patterns("build"))
    out = json.loads(run_hook(tmp_path / "led-bar" / "hardware"))      # a subdirectory: found upwards
    spec = out["hookSpecificOutput"]
    assert spec["hookEventName"] == "SessionStart"
    context = spec["additionalContext"]
    assert str(CHAPTER) in context
    found = titles()
    assert len(found) >= 25                       # the fourteen of the extraction and the eleven added since
    for n, title in enumerate(found, 1):
        assert re.search(rf"^{n}\. {re.escape(title)}", context, re.M), title
    assert len(context.splitlines()) == len(found) + 1                 # one line per agreement, one header


def test_agreements_false_turns_it_off(tmp_path):
    shutil.copytree(EXAMPLE, tmp_path / "led-bar", ignore=shutil.ignore_patterns("build"))
    toml = tmp_path / "led-bar" / "edakit.toml"
    toml.write_text(toml.read_text().replace('quantity = 5', 'quantity = 5\nagreements = false', 1))
    assert run_hook(tmp_path / "led-bar") == ""
    toml.write_text(toml.read_text().replace('agreements = false', 'agreements = true'))
    assert run_hook(tmp_path / "led-bar") != ""


def test_edakit_config_names_the_project(tmp_path):
    shutil.copytree(EXAMPLE, tmp_path / "led-bar", ignore=shutil.ignore_patterns("build"))
    env = {"PATH": "/usr/bin:/bin", "EDAKIT_CONFIG": str(tmp_path / "led-bar" / "edakit.toml")}
    (tmp_path / "elsewhere").mkdir()
    assert "11.4" in run_hook(tmp_path / "elsewhere", env)


def test_a_broken_hook_input_or_toml_does_not_stop_the_session(tmp_path):
    res = subprocess.run([sys.executable, str(SCRIPT)], input="not json", capture_output=True, text=True, timeout=10)
    assert res.returncode == 0
    (tmp_path / "edakit.toml").write_text("[project\nname = ")
    assert "11.4" in run_hook(tmp_path)           # an edakit project all the same; edakit check reports the file
