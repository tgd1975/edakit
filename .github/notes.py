"""Land concepts and TODO.md on main through the notes lane (docs/concepts/done/versioning.md) – no OK needed.

    python3 .github/notes.py "<message>" <file>…

From any worktree on any branch; the checkout stays as it is until the merge:

1. every file must lie in the lane – docs/concepts/ or TODO.md (LANE in .github/versions.py);
2. the session's own edits of those files – the diff against the commit the checkout stands on, new files included –
   are applied with a three-way merge onto the newest main, in a temporary index: a TODO.md taken whole from an older
   checkout would undo what other sessions landed meanwhile; an edit of the same lines as one on main stops it,
   naming the file;
3. the commit goes to notes/<topic>, a pull request is opened, the checks are waited for (about a minute: test and
   kicad skip a change of concepts and TODO.md alone, tests.yml), and it is merged from the owner's account, so the
   site is published as after any merge; when main has moved into a conflict, from 2 again;
4. then the files in the checkout go back to its commit – unless they were edited again meanwhile – and come back
   with main: the main clone on main is fast-forwarded here, a code branch gets them with its next rebase.

Run it in the background; progress goes to stdout line by line. A merge through the lane is no version.
"""

import argparse
import datetime as dt
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import merge as m  # noqa: E402
import versions as v  # noqa: E402

ROUNDS = 5
FOOTER = "\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n"


def git(root, *args, env=None, input=None, check=True):
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=env, input=input)
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(args[:2])}: {(r.stderr or r.stdout).strip()}")
    return r


def in_head(root, files):
    return set(git(root, "ls-tree", "-r", "--name-only", "HEAD", "--", *files).stdout.split())


def patch(root, files):
    """The checkout's own edits of the files against its commit, new files included, with the blobs' ids."""
    out = git(root, "diff", "--full-index", "--binary", "HEAD", "--", *files).stdout
    known = in_head(root, files)
    for f in files:
        if f not in known and (Path(root) / f).is_file():
            out += git(root, "diff", "--no-index", "--full-index", "--binary", "/dev/null", f, check=False).stdout
    return out


def build(root, files, message, base="origin/main"):
    """(commit, patch): the edits as one commit on top of base; commit None when base has them already."""
    bad = [f for f in files if not v.under(f, v.LANE)]
    if bad:
        raise SystemExit(f"not in the notes lane ({', '.join(v.LANE)}): {' '.join(bad)}")
    p = patch(root, files)
    if not p.strip():
        raise SystemExit("no edits of these files against the checkout's commit")
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(d) / "index"))
        git(root, "read-tree", base, env=env)
        r = git(root, "apply", "--cached", "--3way", "-", env=env, input=p, check=False)
        if r.returncode:
            raise SystemExit("the edits conflict with main – pull, then run again:\n" + (r.stderr or r.stdout).strip())
        tree = git(root, "write-tree", env=env).stdout.strip()
    if tree == git(root, "rev-parse", f"{base}^{{tree}}").stdout.strip():
        return None, p
    return git(root, "commit-tree", tree, "-p", base, "-m", message).stdout.strip(), p


def restore(root, files, landed):
    """The files back to the checkout's commit, if nobody edited them since they were landed."""
    if patch(root, files) != landed:
        m.say("the files were edited again meanwhile – left as they are")
        return False
    known = in_head(root, files)
    if known:
        git(root, "checkout", "HEAD", "--", *sorted(known))
    for f in files:
        if f not in known and (Path(root) / f).is_file():
            (Path(root) / f).unlink()
    return True


def follow_main(root):
    """The main clone on main, clean, fast-forwarded to origin/main."""
    if git(root, "symbolic-ref", "-q", "--short", "HEAD", check=False).stdout.strip() != "main":
        return
    if git(root, "status", "--porcelain").stdout.strip():
        return
    git(root, "fetch", "-q", "origin", "main")
    if git(root, "merge", "-q", "--ff-only", "origin/main", check=False).returncode == 0:
        m.say("the main clone follows main")


def slug(message):
    return re.sub(r"[^a-z0-9]+", "-", message.lower()).strip("-")[:40].strip("-") or "notes"


def main(argv=None):
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("message", help="the commit message, also the pull request's title")
    ap.add_argument("files", nargs="+", help="files under docs/concepts/ or TODO.md")
    args = ap.parse_args(argv)
    m.NAME = "notes"

    root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").stdout.strip())
    files = sorted({Path(os.path.abspath(f)).relative_to(root).as_posix() for f in args.files})
    branch = f"notes/{slug(args.message)}-{dt.datetime.now():%H%M%S}"
    message = args.message + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
    pr = None
    for round_ in range(1, ROUNDS + 1):
        git(root, "fetch", "-q", "origin", "main")
        commit, landed = build(root, files, message)
        if commit is None:
            m.say("main has these edits already")
            break
        git(root, "push", "-q", "--force", "origin", f"{commit}:refs/heads/{branch}")
        m.say(f"round {round_}: {branch} at {commit[:7]}")
        if pr is None:
            body = ("The notes lane (docs/concepts/done/versioning.md): only docs/concepts/ and TODO.md, merged by "
                    ".github/notes.py once the checks are green – no version." + FOOTER)
            url = m.run("gh", "pr", "create", "--base", "main", "--head", branch, "--title", args.message,
                        "--body", body).stdout.strip()
            pr = url.rstrip("/").rsplit("/", 1)[-1]
            m.say(f"pull request #{pr}")
        m.wait(commit, m.required(root))
        r = m.run("gh", "pr", "merge", pr, *m.MERGE, "--match-head-commit", commit, "--delete-branch",
                  "--subject", f"Merge branch '{branch}': {args.message}", "--body", "", check=False)
        if r.returncode == 0:
            m.say(f"merged #{pr}")
            break
        m.say(f"merge refused: {(r.stderr or r.stdout).strip()} – again on the newest main")
    else:
        raise SystemExit(f"main kept moving: {ROUNDS} rounds without a merge (#{pr} stays open)")
    if restore(root, files, landed):
        follow_main(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
