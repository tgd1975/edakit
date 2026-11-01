"""edakit's versions (docs/concepts/done/versioning.md): one number in edakit/__init__.py, the marketplace entry and the
changelog held to it, the fragments that make the next one, the checks paths and version of a pull request
(.github/versions.py), and the string `edakit --version` and the gate manifest print (edakit/version.py)."""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from edakit import __version__, cli
from edakit.version import version

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / ".github" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v = _load("versions")


def test_the_number_is_written_once_and_held_everywhere():
    entry = v.entry((ROOT / v.MARKETPLACE).read_text())
    log = (ROOT / v.CHANGELOG).read_text()
    assert v.number((ROOT / v.INIT).read_text()) == __version__
    assert "version" not in json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())   # it would win
    if __version__ == "0.1.0":     # before the first version: no section, the entry from the repository itself
        assert v.top(log) is None and "version" not in entry
        return
    assert entry["version"] == __version__
    assert entry["source"] == {"source": "github", "repo": v.REPO, "ref": f"v{__version__}"}
    assert v.top(log) == __version__ and v.section(log, __version__)


def test_the_fragments_on_this_branch_are_well_formed():
    for p in sorted((ROOT / "changes").glob("*.md")):
        if p.name != "README.md":
            kind, lines = v.fragment(p.name, p.read_text())
            assert kind in ("minor", "patch") and lines


@pytest.mark.parametrize("kind, n", [("patch", "0.2.1"), ("minor", "0.3.0"), ("major", "1.0.0")])
def test_bump(kind, n):
    assert v.bump("0.2.0", kind) == n


@pytest.mark.parametrize("text, error", [("major\n- x", "minor or patch"), ("patch\n", "no line"),
                                         ("- a line, no kind", "minor or patch")])
def test_a_malformed_fragment_names_what_is_wrong(text, error):
    with pytest.raises(ValueError, match=error):
        v.fragment("x.md", text)


def test_what_needs_a_version():
    assert v.needs_version(["tests/test_x.py", ".github/merge.py", "docs/concepts/new/a.md", "TODO.md",
                            "CLAUDE.md", "README.md", "changes/x.md", "CHANGELOG.md", "upstream/README.md"]) == []
    assert v.needs_version(["edakit/check.py", "skills/x/SKILL.md", "handbook/03-hardware-graph.md", "uv.lock",
                            ".claude-plugin/marketplace.json", "newdir/x"]) == [
        "edakit/check.py", "skills/x/SKILL.md", "handbook/03-hardware-graph.md", "uv.lock",
        ".claude-plugin/marketplace.json", "newdir/x"]


def _tree(tmp_path, number="0.2.0", fragments=None, log=None):
    for rel in (v.INIT, v.MARKETPLACE, v.CHANGELOG):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    (tmp_path / v.INIT).write_text(v.set_number((tmp_path / v.INIT).read_text(), number))
    if log is not None:
        (tmp_path / v.CHANGELOG).write_text(log)
    (tmp_path / "changes").mkdir()
    (tmp_path / "changes" / "README.md").write_text("# Fragments\n")
    for name, text in (fragments or {}).items():
        (tmp_path / "changes" / name).write_text(text)
    return tmp_path


LOG = "# Changelog\n\nIntro.\n\n## 0.2.0 – 2026-11-01\n\n- the first\n"


def test_numbering_writes_number_entry_and_section_and_deletes_the_fragments(tmp_path):
    t = _tree(tmp_path, log=LOG, fragments={"b.md": "patch\n- B fixed", "a.md": "minor\n- **When updating:** A"})
    assert v.number_tree(t, "0.2.0", "2026-11-03") == "0.3.0"
    assert v.number((t / v.INIT).read_text()) == "0.3.0"
    entry = v.entry((t / v.MARKETPLACE).read_text())
    assert entry["version"] == "0.3.0" and entry["source"]["ref"] == "v0.3.0"
    log = (t / v.CHANGELOG).read_text()
    assert v.top(log) == "0.3.0" and v.section(log, "0.3.0") == "- **When updating:** A\n- B fixed"
    assert v.section(log, "0.2.0") == "- the first"
    assert [p.name for p in (t / "changes").iterdir()] == ["README.md"]


def test_numbering_takes_the_major_number_only_when_asked(tmp_path):
    t = _tree(tmp_path, log=LOG, fragments={"a.md": "patch\n- a"})
    assert v.number_tree(t, "0.2.0", "2026-11-03", major=True) == "1.0.0"
    assert v.number_tree(_tree(tmp_path / "2", log=LOG), "0.2.0", "2026-11-03") is None


def _reader(files):
    return lambda path: files.get(path)


# a marketplace file of its own, not the repository's: that one carries whatever number main has, which may be the
# one a case below expects to find inconsistent
MARKET = json.dumps({"name": "edakit", "plugins": [{"name": "edakit", "source": "./"}]})


def _files(number, log, ref=True, fragments=None):
    files = {v.INIT: f'__version__ = "{number}"\n',
             v.MARKETPLACE: v.set_marketplace(MARKET, number if ref else "0.0.1"), v.CHANGELOG: log}
    files.update({f"changes/{k}": t for k, t in (fragments or {}).items()})
    return files


BASE = _files("0.2.0", LOG)


def test_version_is_red_until_merge_numbers_it():
    head = _files("0.2.0", LOG, fragments={"x.md": "patch\n- x"})
    ok, description, _ = v.check_version(["edakit/check.py", "changes/x.md"], _reader(BASE), _reader(head), 12)
    assert not ok and "python3 .github/merge.py 12" in description


def test_version_asks_for_a_fragment():
    ok, description, details = v.check_version(["edakit/check.py"], _reader(BASE), _reader(BASE), 12)
    assert not ok and "without a fragment" in description and details == ["edakit/check.py"]


def test_version_passes_a_change_nothing_a_project_reads():
    ok, description, _ = v.check_version(["tests/test_x.py", "TODO.md"], _reader(BASE), _reader(BASE), 12)
    assert ok and "no version" in description


PYPROJECT = """[project]
name = "edakit"
dependencies = ["numpy>=1.26"]

[dependency-groups]
dev = ["pytest>={pytest}"]
"""

LOCK = """version = 1
requires-python = ">=3.11"

[[package]]
name = "edakit"
source = {{ editable = "." }}
dependencies = [{{ name = "numpy" }}]

[package.dev-dependencies]
dev = [{{ name = "pytest" }}]

[[package]]
name = "numpy"
version = "{numpy}"

[[package]]
name = "pytest"
version = "{pytest}"
dependencies = [{{ name = "pluggy" }}]

[[package]]
name = "pluggy"
version = "1.6.0"
"""


def _deps(numpy="2.4.6", pytest="9.1.1", runtime='"numpy>=1.26"'):
    return {**BASE, "pyproject.toml": PYPROJECT.format(pytest=pytest).replace('"numpy>=1.26"', runtime),
            "uv.lock": LOCK.format(numpy=numpy, pytest=pytest)}


def test_an_update_of_the_dev_tools_alone_is_no_version():
    """Dependabot's weekly pytest: pyproject.toml's dev group and uv.lock moved, nothing edakit installs."""
    ok, description, _ = v.check_version(list(v.DEPS), _reader(_deps()), _reader(_deps(pytest="9.2.0")), 12)
    assert ok and "no version" in description


@pytest.mark.parametrize("head", [_deps(numpy="2.5.0"), _deps(pytest="9.2.0", numpy="2.5.0"),
                                  _deps(runtime='"numpy>=2"')], ids=["runtime", "both", "requirement"])
def test_an_update_of_what_edakit_installs_is_a_version(head):
    ok, description, details = v.check_version(list(v.DEPS), _reader(_deps()), _reader(head), 12)
    assert not ok and "without a fragment" in description and set(details) & set(v.DEPS)


def test_the_runtime_follows_the_dependencies_and_leaves_the_dev_group_out():
    assert v.runtime(LOCK.format(numpy="2.4.6", pytest="9.1.1")) == (">=3.11", [("edakit", None),
                                                                              ("numpy", "2.4.6")])


def test_the_runtime_of_this_repository_is_edakits():
    names = {n for n, _ in v.runtime((ROOT / "uv.lock").read_text())[1]}
    assert {"edakit", "numpy", "scipy", "shapely"} <= names and "pytest" not in names


def test_version_passes_a_numbered_pull_request():
    head = _files("0.2.1", "# Changelog\n\n## 0.2.1 – 2026-11-03\n\n- x\n\n" + LOG[LOG.index("## 0.2.0"):])
    ok, description, _ = v.check_version(["edakit/check.py", v.INIT, v.MARKETPLACE, v.CHANGELOG],
                                         _reader(BASE), _reader(head), 12)
    assert ok and description == "numbered 0.2.1"


@pytest.mark.parametrize("number, log, ref, problem", [
    ("0.2.2", "## 0.2.2 – 2026-11-03\n\n- x\n", True, "does not follow"),
    ("0.2.1", "## 0.2.1 – 2026-11-03\n\n- x\n", False, "version and ref"),
    ("0.2.1", LOG, True, "top section"),
])
def test_version_names_an_inconsistent_number(number, log, ref, problem):
    ok, _, details = v.check_version(["edakit/check.py"], _reader(BASE), _reader(_files(number, log, ref)), 12)
    assert not ok and any(problem in d for d in details)


def test_paths_holds_each_branch_family_to_its_paths():
    pipeline = (".github/", "CLAUDE.md", "skills/propose-rule/")
    assert v.check_paths("notes/versioning", ["docs/concepts/new/x.md", "TODO.md"], pipeline)[0]
    ok, _, bad = v.check_paths("notes/versioning", ["TODO.md", "edakit/check.py"], pipeline)
    assert not ok and bad == ["edakit/check.py"]
    ok, _, bad = v.check_paths("rules/proposals", ["edakit/catalog/codes.toml", ".github/workflows/proposals.yml",
                                                   "skills/propose-rule/SKILL.md", "CLAUDE.md"], pipeline)
    assert not ok and bad == [".github/workflows/proposals.yml", "skills/propose-rule/SKILL.md", "CLAUDE.md"]
    assert v.check_paths("rules/proposals", ["edakit/catalog/codes.toml"], pipeline)[0]
    ok, description, _ = v.check_paths("features/proposals", [".github/x"], None)
    assert ok and "not on main yet" in description
    assert v.check_paths("versioning-v1", [".github/merge.py"], pipeline)[0]


def test_the_notes_of_a_version_are_its_section(tmp_path, capsys, monkeypatch):
    t = _tree(tmp_path, log=LOG)
    monkeypatch.setattr(v, "ROOT", t)
    assert v.main(["notes", "0.2.0"]) == 0 and capsys.readouterr().out == "- the first\n"
    assert v.main(["notes", "9.9.9"]) == 1


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_the_version_string_names_the_commit_away_from_the_tag(tmp_path):
    assert version(tmp_path) == __version__          # no .git: the plugin's cache, an install by uvx
    _git(tmp_path, "init", "-q")
    (tmp_path / "x").write_text("x")
    _git(tmp_path, "add", "x")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x")
    sha = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "--short=7", "HEAD"], capture_output=True,
                         text=True).stdout.strip()
    assert version(tmp_path) == f"{__version__}+g{sha}"
    _git(tmp_path, "tag", f"v{__version__}")
    assert version(tmp_path) == __version__


def test_edakit_version(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0 and capsys.readouterr().out.startswith(f"edakit {__version__}")


def test_merge_knows_its_numbering_commit_and_the_checks():
    merge = _load("merge")
    assert merge.NUMBERING.match("edakit 0.2.0") and not merge.NUMBERING.match("edakit 0.2.0: more")
    assert set(merge.REQUIRED) == {"test", "kicad", "build", "paths", "version"}


def test_a_branch_behind_main_is_not_taken_for_numbered(tmp_path, capsys, monkeypatch):
    """The check reads the number the branch started from: main moved on to 0.2.1 after the branch left 0.2.0."""
    def g(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
    g("init", "-q", "-b", "main")
    g("config", "user.name", "t")
    g("config", "user.email", "t@t")
    (tmp_path / "edakit").mkdir()
    (tmp_path / v.INIT).write_text('__version__ = "0.2.0"\n')
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.py").write_text("x\n")
    g("add", ".")
    g("commit", "-q", "-m", "0.2.0")
    g("checkout", "-q", "-b", "work")
    (tmp_path / "tests" / "t.py").write_text("y\n")
    g("commit", "-q", "-am", "a test only")
    g("checkout", "-q", "main")
    (tmp_path / v.INIT).write_text('__version__ = "0.2.1"\n')
    g("commit", "-q", "-am", "0.2.1")
    monkeypatch.setattr(v, "ROOT", tmp_path)
    assert v.main(["check", "version", "main", "work", "work", "9"]) == 0
    assert capsys.readouterr().out.startswith("no version")
