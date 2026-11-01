"""The notes lane's command (.github/notes.py, docs/concepts/done/versioning.md): a session's edits of concepts and
TODO.md as one commit on the newest main – the diff, not the file, so what another session landed meanwhile stays –,
nothing outside the lane, and the checkout given back afterwards. On real git repositories: an origin and two clones,
as two sessions."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github"))
spec = importlib.util.spec_from_file_location("notes", ROOT / ".github" / "notes.py")
notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notes)
sys.path.pop(0)

TODO = "".join(f"- [ ] TD-{i} - item {i}\n" for i in range(1, 11))


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def clone(origin, path):
    subprocess.run(["git", "clone", "-q", str(origin), str(path)], check=True, capture_output=True)
    git(path, "config", "user.name", "t")
    git(path, "config", "user.email", "t@t")
    return path


@pytest.fixture
def two(tmp_path):
    """An origin with main, and two clones of it: a and b."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    seed = clone(origin, tmp_path / "seed")
    (seed / "TODO.md").write_text(TODO)
    (seed / "docs" / "concepts" / "new").mkdir(parents=True)
    (seed / "docs" / "concepts" / "new" / "x.md").write_text("# X\n")
    (seed / "edakit").mkdir()
    (seed / "edakit" / "a.py").write_text("A = 1\n")
    git(seed, "add", ".")
    git(seed, "commit", "-q", "-m", "seed")
    git(seed, "push", "-q", "origin", "HEAD:main")
    return clone(origin, tmp_path / "a"), clone(origin, tmp_path / "b")


def land(clone_, path, old, new, message):
    f = clone_ / path
    f.write_text(f.read_text().replace(old, new))
    git(clone_, "commit", "-q", "-am", message)
    git(clone_, "push", "-q", "origin", "HEAD:main")


def test_the_diff_lands_on_the_newest_main_and_keeps_what_another_session_landed(two):
    a, b = two
    land(b, "TODO.md", "- [ ] TD-10 - item 10", "- [x] TD-10 - item 10", "b ticks TD-10")
    (a / "TODO.md").write_text(TODO.replace("- [ ] TD-1 - item 1\n", "- [x] TD-1 - item 1\n"))
    git(a, "fetch", "-q", "origin", "main")
    commit, _ = notes.build(a, ["TODO.md"], "a ticks TD-1")
    text = git(a, "show", f"{commit}:TODO.md")
    assert "- [x] TD-1 - item 1\n" in text and "- [x] TD-10 - item 10\n" in text
    assert git(a, "rev-parse", f"{commit}^").strip() == git(a, "rev-parse", "origin/main").strip()


def test_an_edit_of_the_same_lines_stops_with_the_conflict(two):
    a, b = two
    land(b, "TODO.md", "- [ ] TD-1 - item 1", "- [x] TD-1 - item 1 (b)", "b")
    (a / "TODO.md").write_text(TODO.replace("- [ ] TD-1 - item 1", "- [x] TD-1 - item 1 (a)"))
    git(a, "fetch", "-q", "origin", "main")
    with pytest.raises(SystemExit, match="conflict with main"):
        notes.build(a, ["TODO.md"], "a")


def test_a_new_concept_and_a_change_together(two):
    a, _ = two
    (a / "docs" / "concepts" / "new" / "y.md").write_text("# Y\n")
    (a / "TODO.md").write_text(TODO + "- [ ] TD-11 - item 11\n")
    git(a, "fetch", "-q", "origin", "main")
    commit, landed = notes.build(a, ["TODO.md", "docs/concepts/new/y.md"], "y")
    assert git(a, "show", f"{commit}:docs/concepts/new/y.md") == "# Y\n"
    assert git(a, "show", f"{commit}:TODO.md").endswith("TD-11 - item 11\n")
    assert notes.restore(a, ["TODO.md", "docs/concepts/new/y.md"], landed)
    assert (a / "TODO.md").read_text() == TODO and not (a / "docs" / "concepts" / "new" / "y.md").exists()


def test_files_edited_again_meanwhile_stay(two):
    a, _ = two
    (a / "TODO.md").write_text(TODO + "- [ ] TD-11\n")
    git(a, "fetch", "-q", "origin", "main")
    _, landed = notes.build(a, ["TODO.md"], "11")
    (a / "TODO.md").write_text(TODO + "- [ ] TD-11\n- [ ] TD-12\n")
    assert not notes.restore(a, ["TODO.md"], landed)
    assert (a / "TODO.md").read_text().endswith("TD-12\n")


def test_nothing_outside_the_lane(two):
    a, _ = two
    (a / "edakit" / "a.py").write_text("A = 2\n")
    with pytest.raises(SystemExit, match="not in the notes lane"):
        notes.build(a, ["edakit/a.py"], "code")


def test_no_edits_no_commit(two):
    a, _ = two
    git(a, "fetch", "-q", "origin", "main")
    with pytest.raises(SystemExit, match="no edits"):
        notes.build(a, ["TODO.md"], "nothing")


def test_main_with_the_edits_already(two):
    a, b = two
    land(b, "TODO.md", "- [ ] TD-2 - item 2", "- [x] TD-2 - item 2", "b ticks TD-2")
    (a / "TODO.md").write_text(TODO.replace("- [ ] TD-2 - item 2", "- [x] TD-2 - item 2"))
    git(a, "fetch", "-q", "origin", "main")
    assert notes.build(a, ["TODO.md"], "a ticks TD-2 too")[0] is None


def test_the_branch_name():
    assert notes.slug("TODO.md: TD-46 closed – the notes lane (#107)") == "todo-md-td-46-closed-the-notes-lane-107"
    assert notes.slug("–") == "notes"
