"""merge.py and generated output (TD-79, docs/concepts/done/versioning.md): a conflict that lies only in what a script
writes – the catalog page, the handbook's generated sections – is resolved and regenerated instead of stopping the
merge; a conflict in anybody's own text still stops it."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github"))
spec = importlib.util.spec_from_file_location("merge", ROOT / ".github" / "merge.py")
merge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge)
sys.path.pop(0)

GEN = "<!-- edakit:generated codes HINT -->\n"
END = "<!-- edakit:end -->\n"


def conflict(ours, theirs):
    return f"<<<<<<< HEAD\n{ours}=======\n{theirs}>>>>>>> origin/main\n"


def test_a_conflict_inside_a_generated_section_takes_the_branch_side():
    text = "# 14\n\nProse.\n" + GEN + "| a |\n" + conflict("| b branch |\n", "| b main |\n") + END + "More prose.\n"
    assert merge.only_generated(text) == "# 14\n\nProse.\n" + GEN + "| a |\n| b branch |\n" + END + "More prose.\n"


def test_a_conflict_in_prose_stays_somebodys():
    text = "# 14\n" + conflict("branch's sentence\n", "main's sentence\n") + GEN + "| a |\n" + END
    assert merge.only_generated(text) is None


def test_a_conflict_over_the_section_marker_stays_too():
    text = GEN + "| a |\n" + conflict(END + "prose\n", "| b |\n" + END) + "tail\n"
    assert merge.only_generated(text) is None


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def repo(tmp_path):
    r = tmp_path / "r"
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    git(r, "config", "user.name", "t")
    git(r, "config", "user.email", "t@t")
    (r / "docs" / "catalog").mkdir(parents=True)
    (r / "docs" / "catalog" / "index.html").write_text("<p>catalog 1</p>\n")
    (r / "README.md").write_text("readme 1\n")
    git(r, "add", ".")
    git(r, "commit", "-q", "-m", "seed")
    return r


def branch_and_main(r, path, ours, theirs):
    git(r, "checkout", "-q", "-b", "work")
    (r / path).write_text(ours)
    git(r, "commit", "-q", "-am", "branch")
    git(r, "checkout", "-q", "main")
    (r / path).write_text(theirs)
    git(r, "commit", "-q", "-am", "main")
    git(r, "checkout", "-q", "work")
    assert subprocess.run(["git", "-C", str(r), "merge", "-q", "--no-edit", "main"], capture_output=True).returncode
    return git(r, "diff", "--name-only", "--diff-filter=U").split()


def test_the_catalog_page_in_conflict_is_regenerated_and_the_merge_goes_on(tmp_path, monkeypatch):
    r = repo(tmp_path)
    files = branch_and_main(r, "docs/catalog/index.html", "<p>catalog branch</p>\n", "<p>catalog main</p>\n")
    ran = []
    monkeypatch.setattr(merge, "GENERATORS", (("-c", "pass"),))
    monkeypatch.setattr(merge, "run", lambda *cmd, cwd=None, check=True: (
        ran.append(cmd) if cmd[0] == "uv" else subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)))
    assert merge.resolve_generated(r, files)
    assert ran == [("uv", "run", "--quiet", "python", "-c", "pass")]
    assert (r / "docs" / "catalog" / "index.html").read_text() == "<p>catalog main</p>\n"   # then regenerated
    assert git(r, "log", "-1", "--format=%P").count(" ") == 1                                   # the merge commit


def test_a_conflict_in_a_file_of_its_own_stops_the_merge(tmp_path):
    r = repo(tmp_path)
    files = branch_and_main(r, "README.md", "readme branch\n", "readme main\n")
    assert files == ["README.md"] and not merge.resolve_generated(r, files)


def test_every_page_of_the_split_catalog_is_generated_output():
    """Since step D.4 the catalog is many pages: each is regenerated on a conflict, its generator is not."""
    assert merge.generated("docs/catalog/lim.html") and merge.generated("docs/catalog/index.html")
    assert merge.generated("docs/catalog/circuits/usb.svg")
    assert not merge.generated("docs/catalog/build.py") and not merge.generated("docs/concepts/x.html")
