"""merge.py and notes.py speak to GitHub through REST only (`gh api`): a cloud session's GitHub proxy refuses GraphQL,
and with it `gh pr view`, `gh pr create` and `gh pr merge`, so both scripts run there as on the owner's machine. Each
call is checked here against what GitHub's REST API expects – no network, `run` stands in for gh."""

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github"))
spec = importlib.util.spec_from_file_location("merge", ROOT / ".github" / "merge.py")
merge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge)
sys.path.pop(0)

PULL = {"number": 276, "state": "open", "title": "TODO.md: TD-123",
        "head": {"ref": "notes/todo", "repo": {"full_name": "tgd1975/edakit"}},
        "base": {"ref": "main", "repo": {"full_name": "tgd1975/edakit"}}}


def fake(monkeypatch, answer=None, code=0):
    """`run` records each command and answers with `answer` as JSON."""
    calls = []

    def run(*cmd, cwd=None, check=True):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, code, json.dumps(answer or {}), "")
    monkeypatch.setattr(merge, "run", run)
    return calls


def fields(cmd):
    """The -f fields of a gh api command as a dict."""
    return dict(cmd[i + 1].split("=", 1) for i, a in enumerate(cmd) if a == "-f")


def test_no_script_calls_gh_pr():
    """`gh pr …` and `gh api graphql` speak GraphQL – none of them in the scripts a session runs."""
    for script in ("merge.py", "notes.py"):
        text = (ROOT / ".github" / script).read_text(encoding="utf-8")
        assert not re.search(r'"gh",\s*"pr"', text) and not re.search(r'"api",\s*"graphql"', text), script


def test_pr_view_reads_the_pull_request(monkeypatch):
    calls = fake(monkeypatch, PULL)
    assert merge.pr_view(276) == {"number": 276, "state": "OPEN", "headRefName": "notes/todo", "baseRefName": "main",
                                  "title": "TODO.md: TD-123", "isCrossRepository": False}
    assert calls == [("gh", "api", "repos/tgd1975/edakit/pulls/276")]


def test_a_pull_request_from_a_fork_or_a_deleted_one_is_cross_repository(monkeypatch):
    fake(monkeypatch, dict(PULL, head={"ref": "x", "repo": {"full_name": "someone/edakit"}}))
    assert merge.pr_view(1)["isCrossRepository"]
    fake(monkeypatch, dict(PULL, head={"ref": "x", "repo": None}))
    assert merge.pr_view(1)["isCrossRepository"]


def test_pr_create_posts_the_branch_into_main(monkeypatch):
    calls = fake(monkeypatch, {"number": 277})
    assert merge.pr_create("notes/x", "a title", "a body\n\n🤖 footer") == 277
    (cmd,) = calls
    assert cmd[:5] == ("gh", "api", "-X", "POST", "repos/tgd1975/edakit/pulls")
    assert fields(cmd) == {"head": "notes/x", "base": "main", "title": "a title", "body": "a body\n\n🤖 footer"}


def test_pr_merge_is_a_merge_commit_bound_to_the_checked_head(monkeypatch):
    calls = fake(monkeypatch, {"merged": True})
    assert merge.pr_merge(276, "d90bccf", "Merge branch 'notes/x': a title").returncode == 0
    (cmd,) = calls
    assert cmd[:5] == ("gh", "api", "-X", "PUT", "repos/tgd1975/edakit/pulls/276/merge")
    assert fields(cmd) == {"merge_method": "merge", "sha": "d90bccf",
                           "commit_title": "Merge branch 'notes/x': a title", "commit_message": ""}


def test_a_refused_merge_comes_back_to_the_caller(monkeypatch):
    """GitHub answers 409 when the head moved, 405 when main's rules refuse: the caller goes round again."""
    fake(monkeypatch, code=1)
    assert merge.pr_merge(276, "d90bccf", "s").returncode == 1


def test_the_merged_branch_is_deleted_without_stopping(monkeypatch):
    calls = fake(monkeypatch, code=1)        # already deleted by GitHub, or refused: no matter
    assert merge.delete_branch("notes/x").returncode == 1
    assert calls == [("gh", "api", "-X", "DELETE", "repos/tgd1975/edakit/git/refs/heads/notes/x")]
