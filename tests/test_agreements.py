"""The working agreements of handbook 11.4 at session start: the plugin's SessionStart hook, run as the plugin runs it.
After them the project's own scripts and agents (handbook 8.6), one line each – the reference project's entries as the
concept project-scripts writes them; a project without entries starts as before."""

import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import test_agents as ta
import test_scripts as ts

from edakit import agreements, scripts

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "edakit" / "agreements.py"
CHAPTER = ROOT / "handbook" / "11-working-with-claude.md"
EXAMPLE = Path(__file__).resolve().parent / "fixtures" / "led-bar"
TREE = ts.TREE + ta.PYTREE       # the reference project's seven scripts (review left out, decision 8) and two agents
OFF = ("quantity = 5", "quantity = 5\nagreements = false")       # [project] agreements = false in the example


@pytest.fixture(autouse=True)
def no_config_from_outside(monkeypatch):
    import os
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    monkeypatch.setenv("PATH", f"{ROOT / 'bin'}:{os.environ.get('PATH', '')}")     # edakit found: no line for it


def run_hook(cwd, env=None, on_path=True):
    """The hook as Claude Code starts it: plain python3, the hook JSON on stdin, from another directory – with the
    plugin's bin/ on PATH, as a session that finds edakit has it."""
    import os
    data = {"session_id": "s1", "hook_event_name": "SessionStart", "source": "startup", "cwd": str(cwd)}
    env = dict(env if env is not None else os.environ)
    path = [x for x in env.get("PATH", "").split(":") if x and not (Path(x) / "edakit").exists()]
    env["PATH"] = ":".join(([str(ROOT / "bin")] if on_path else []) + path)
    res = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(data), capture_output=True, text=True,
                         cwd="/", env=env, timeout=10)
    assert res.returncode == 0, res.stderr
    return res.stdout


def context(out):
    """The text the hook puts into the session's context."""
    return json.loads(out)["hookSpecificOutput"]["additionalContext"]


def led_bar(where, entries="", replace=None):
    """A copy of the example in `where`, with these entries at the end of its edakit.toml and `replace` (old, new)
    done in it."""
    root = where / "led-bar"
    shutil.copytree(EXAMPLE, root, ignore=shutil.ignore_patterns("build"))
    toml = root / "edakit.toml"
    text = toml.read_text() + entries
    toml.write_text(text.replace(*replace, 1) if replace else text)
    return root


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


# --- the project's scripts and agents after the agreements (step 3.3) ------------------------------------------------
def test_without_scripts_and_agents_the_session_starts_as_before(tmp_path):
    """No [scripts], no [agents], as in the example and the Christmas bell: the agreements alone, nothing added."""
    assert context(run_hook(led_bar(tmp_path))) == agreements.digest()


def test_the_projects_scripts_and_agents_follow_the_agreements(tmp_path):
    """Red before step 3.3: the session knew nothing of the project's scripts. Now, after the agreements, a head that
    points to edakit scripts and one line per script – its name, kind and about, a check also with its id and phase –,
    then a head and one line per agent – its name, what it signs and whom it replaces, as edakit scripts says it, and
    its about –, in the order of edakit.toml. No state: that needs the hashes, edakit scripts gives it."""
    lines = context(run_hook(led_bar(tmp_path, TREE))).splitlines()
    digest = agreements.digest().splitlines()
    assert lines[:len(digest)] == digest
    entries = tomllib.loads(TREE)
    made, team = entries["scripts"], entries["agents"]
    head, *listed = lines[len(digest):len(digest) + 1 + len(made)]
    for words in ("[scripts.<name>]", "handbook 8.6", "`edakit scripts`", "current, outdated, never run", "order",
                  "an input runs by itself before the step that reads it", "`edakit run <name>`", "on command only",
                  "under the easyeda claim", "a check"):
        assert words in head.lower(), words
    assert [line.split(" (")[0] for line in listed] == [f"- {name}" for name in made]
    for line, (name, e) in zip(listed, made.items()):
        assert line.startswith(f"- {name} ({e['kind']}") and line.endswith(f") – {e['about']}"), line
    assert listed[2] == ("- led-footprints (easyeda) – The same polarity print on every LED footprint (owner, "
                         "2026-10-25)")
    assert listed[5] == "- mechanik (check K, phase export) – The tree fits the stand: slot, hill, cable, feet (D-36)"
    assert listed[6].startswith("- abnahme (check A, phase acceptance) – Camera test of every tree after delivery")
    head, *listed = lines[len(digest) + 1 + len(made):]
    for words in ("[agents.<name>]", "handbook 8.6", "own session", "in place of", "done_by", "`edakit scripts`",
                  "who reviews where"):
        assert words in head.lower(), words
    assert listed == [f"- {name} ({scripts._agent_said(a)}) – {a['about']}" for name, a in team.items()]
    assert listed[1] == ("- pcb-pruefer (signs M-5 in place of pcb-reviewer, phase export) – Checks the tree board for "
                         "manufacturability, mechanics, operation and looks")
    assert not [line for line in lines[len(digest):] if line.startswith("- ")
                and re.search(r"\b(current|outdated|never run|stamped)\b", line)]
    shown = re.search(r"^## 11\.4 .*?^```text\n(.*?)^```", CHAPTER.read_text(encoding="utf-8"), re.M | re.S)
    assert shown and set(shown.group(1).splitlines()) <= set(lines)      # 11.4 shows lines as the hook prints them


def test_an_agent_with_a_sign_off_of_its_own_as_edakit_scripts_says_it(tmp_path):
    """The hook says what each agent signs as edakit scripts does: on the hash of its scope, its phase, the agents it
    reviews after."""
    entries = ta.own(after=["pcb-pruefer"]) + ta.KAMERA_AGENT
    lines = context(run_hook(led_bar(tmp_path, entries))).splitlines()
    assert lines[-2:] == [f"- {name} ({scripts._agent_said(a)}) – {a['about']}"
                          for name, a in tomllib.loads(entries)["agents"].items()]
    assert lines[-2].startswith("- optik (signs M-7 on the layout hash, phase export; after pcb-pruefer) – ")
    assert not [line for line in lines if line.startswith("The project's scripts")]      # no scripts: no head


def test_agreements_false_turns_off_the_agreements_not_the_list(tmp_path):
    """The list is the project's own data, registered for every session: it stays when the agreements are off."""
    lines = context(run_hook(led_bar(tmp_path, TREE, OFF))).splitlines()
    assert lines[0].startswith("The project's scripts") and len(lines) == 1 + 7 + 1 + 2
    assert agreements.digest().splitlines()[0] not in lines


def test_without_tomllib_one_line_names_edakit_scripts(tmp_path, monkeypatch):
    """python3 older than 3.11 has no tomllib: the entries cannot be read here, so one line says that the project has
    some and that edakit scripts lists them; agreements = false is read by hand as before; without entries nothing is
    added."""
    monkeypatch.setitem(sys.modules, "tomllib", None)              # import tomllib fails, as before 3.11

    def said(root):
        out = agreements.hook({"cwd": str(root)})
        return out and out["hookSpecificOutput"]["additionalContext"].splitlines()
    lines = said(led_bar(tmp_path / "a", TREE))
    assert lines[:-1] == agreements.digest().splitlines()
    assert "`edakit scripts`" in lines[-1] and "[scripts.<name>]" in lines[-1] and "[agents.<name>]" in lines[-1]
    assert said(led_bar(tmp_path / "b")) == agreements.digest().splitlines()
    assert said(led_bar(tmp_path / "c", TREE, OFF)) == lines[-1:]
    assert said(led_bar(tmp_path / "d", "", OFF)) is None


def test_entries_that_cannot_be_read_cost_no_agreement(tmp_path):
    """A file that does not parse: one line names edakit scripts. An entry that is no table is left out – edakit check
    names it –, a field of an odd type is shown as it is; the agreements come all the same."""
    broken = led_bar(tmp_path / "a", '\n[scripts.kunst]\nkind = "input"\nabout = \n')
    lines = context(run_hook(broken)).splitlines()
    assert lines[:-1] == agreements.digest().splitlines() and "`edakit scripts`" in lines[-1]
    odd = led_bar(tmp_path / "b", '\n[scripts]\nkunst = 3\n\n[agents.x]\nabout = ["one", "two"]\n')
    lines = context(run_hook(odd)).splitlines()
    assert lines[:-2] == agreements.digest().splitlines()
    assert lines[-2].startswith("The project's agents") and lines[-1].startswith("- x (signs ?")


def test_where_edakit_is_not_on_path_the_hook_names_it(tmp_path):
    root = tmp_path / "led-bar"
    shutil.copytree(EXAMPLE, root, ignore=shutil.ignore_patterns("build"))
    assert "is not on PATH" not in context(run_hook(root))
    line = context(run_hook(root, on_path=False)).splitlines()[-1]
    assert line == f"The edakit command line is {ROOT / 'bin' / 'edakit'} – it is not on PATH."
