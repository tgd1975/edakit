"""merge.py and Dependabot (.github/dependabot.yml): an update of uv.lock or pyproject.toml is a version, and
Dependabot writes no fragment – merge.py writes it, patch with the pull request's title. An update of the Actions
alone stays without a version, and a branch of anyone else without a fragment still stops."""

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


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def branch(tmp_path, path):
    """A repository whose HEAD changes path against origin/main."""
    r = tmp_path / "r"
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    git(r, "config", "user.name", "t")
    git(r, "config", "user.email", "t@t")
    (r / "changes").mkdir()
    (r / "changes" / "README.md").write_text("# Fragments\n")
    (r / ".github" / "workflows").mkdir(parents=True)
    (r / ".github" / "workflows" / "tests.yml").write_text("uses: actions/checkout@v4\n")
    (r / "uv.lock").write_text("numpy 2.3.0\n")
    git(r, "add", ".")
    git(r, "commit", "-q", "-m", "seed")
    git(r, "update-ref", "refs/remotes/origin/main", "HEAD")
    (r / path).write_text("updated\n")
    git(r, "commit", "-q", "-am", "bump")
    return r


def test_a_dependabot_update_of_the_lock_gets_a_patch_fragment(tmp_path):
    r = branch(tmp_path, "uv.lock")
    name = merge.dependabot_fragment(r, "dependabot/uv/python-1a2b", "Bump the python group with 2 updates", 190)
    assert name == "dependabot-uv-python-1a2b.md"
    kind, lines = merge.v.fragment(name, (r / "changes" / name).read_text())
    assert kind == "patch" and lines == "- Dependencies: Bump the python group with 2 updates (#190)."


def test_an_update_of_the_actions_alone_stays_without_a_version(tmp_path):
    r = branch(tmp_path, ".github/workflows/tests.yml")
    assert merge.dependabot_fragment(r, "dependabot/github_actions/actions-3c4d", "Bump actions", 191) is None
    assert sorted(p.name for p in (r / "changes").iterdir()) == ["README.md"]


def test_a_fragment_of_its_own_is_kept(tmp_path):
    r = branch(tmp_path, "uv.lock")
    (r / "changes" / "dependabot-uv-x.md").write_text("minor\n- When updating: …\n")
    assert merge.dependabot_fragment(r, "dependabot/uv/x", "Bump", 192) is None


def test_another_branch_without_a_fragment_gets_none(tmp_path):
    r = branch(tmp_path, "uv.lock")
    assert merge.dependabot_fragment(r, "claude/bump-numpy", "Bump numpy", 193) is None
