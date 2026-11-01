"""Merge a pull request into main as a version of its own (docs/concepts/new/versioning.md) – on the owner's OK.

    python3 .github/merge.py <pr> [--major] [--dry-run]

In a worktree of its own, so the session's checkout stays as it is:

1. the branch onto the newest main (a merge of origin/main; an earlier numbering commit at its tip is dropped first);
2. its fragments in changes/ make the number – minor if one says so, else patch; --major only on the owner's word –,
   written into edakit/__init__.py, the marketplace entry and CHANGELOG.md, the fragments deleted, one commit
   "edakit X.Y.Z"; a branch without fragments that changes nothing a project reads is merged without a version;
3. pushed, the checks waited for (test, kicad, build, paths, version – about five minutes);
4. merged with --match-head-commit while main still has the number it was numbered from – a push of TODO.md or a
   concept meanwhile changes nothing; a version merged meanwhile does, for a pull request that is a version: then from
   1 again, since two merges must never share a number.

The workflow release.yml then sets the tag v<number> and the GitHub release. --dry-run does 1 and 2 and shows the diff.
Progress goes to stdout line by line, for a monitor.
"""

import argparse
import datetime as dt
import json
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import versions as v  # noqa: E402

ROOT = v.ROOT
REQUIRED = ("test", "kicad", "build", "paths", "version")
NUMBERING = re.compile(r"^edakit \d+\.\d+\.\d+$")
ROUNDS = 5
WAIT_S = 45 * 60


NAME = "merge"   # the prefix of the progress lines; .github/notes.py sets its own
MERGE = ("--merge",)   # merge commits only; main has no bypass, so no flag takes one (.github/rulesets/)


def say(*args):
    print(f"[{NAME} {dt.datetime.now():%H:%M:%S}]", *args, flush=True)


def run(*cmd, cwd=ROOT, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f"{' '.join(cmd)}: {(r.stderr or r.stdout).strip()}")
    return r


def gh_json(*args):
    return json.loads(run("gh", *args).stdout)


def prepare(tree, branch, major):
    """Steps 1 and 2 in the worktree: returns (the branch's sha on origin, the head sha, main's number, the number or
    None)."""
    run("git", "fetch", "-q", "origin", "main", branch, cwd=tree)
    before = run("git", "rev-parse", f"origin/{branch}", cwd=tree).stdout.strip()
    run("git", "checkout", "-q", "--detach", before, cwd=tree)
    subjects = run("git", "log", "--first-parent", "--format=%s", "origin/main..HEAD", cwd=tree).stdout.splitlines()
    if subjects and NUMBERING.match(subjects[0]):
        say(f"dropping the earlier numbering commit {subjects[0]!r}")
        run("git", "reset", "-q", "--hard", "HEAD~1", cwd=tree)
        subjects = subjects[1:]
    if any(NUMBERING.match(s) for s in subjects):
        raise SystemExit("the branch has commits after its numbering commit – move them below it, then run again")
    if run("git", "merge-base", "--is-ancestor", "origin/main", "HEAD", cwd=tree, check=False).returncode:
        say("merging the newest main into the branch")
        r = run("git", "merge", "-q", "--no-edit", "origin/main", cwd=tree, check=False)
        if r.returncode:
            files = run("git", "diff", "--name-only", "--diff-filter=U", cwd=tree).stdout.split()
            run("git", "merge", "--abort", cwd=tree, check=False)
            raise SystemExit("conflict with main – rebase the branch yourself: " + " ".join(files))
    main_n = v.number(v.show("origin/main", root=tree)(v.INIT))
    n = v.number_tree(tree, main_n, dt.date.today().isoformat(), major=major)
    if n is None:
        stray = v.needs_version(v.changed_files("origin/main", "HEAD", root=tree))
        if stray:
            raise SystemExit("the branch changes edakit but has no fragment in changes/ – add changes/<branch>.md "
                             "(first line minor or patch, then the lines):\n  " + "\n  ".join(stray))
        say("nothing a project reads changed: merged without a version")
        return before, run("git", "rev-parse", "HEAD", cwd=tree).stdout.strip(), main_n, None
    run("git", "add", "-A", v.INIT, v.MARKETPLACE, v.CHANGELOG, v.CHANGES, cwd=tree)
    run("git", "commit", "-q", "-m", f"edakit {n}", cwd=tree)
    say(f"numbered {n} (main is {main_n})")
    return before, run("git", "rev-parse", "HEAD", cwd=tree).stdout.strip(), main_n, n


FAILED = ("failure", "error", "cancelled", "timed_out", "action_required")
PASSED = ("success", "skipped", "neutral")


def checks(sha, required):
    """{name: state} of the required checks on a commit, from its check runs and commit statuses. A name that runs
    twice – a workflow on push and on pull_request – fails when one run fails, and passes when both passed."""
    seen = {}
    for c in gh_json("api", f"repos/{v.REPO}/commits/{sha}/check-runs?per_page=100")["check_runs"]:
        seen.setdefault(c["name"], []).append(c["conclusion"] or c["status"])
    for s in gh_json("api", f"repos/{v.REPO}/commits/{sha}/status")["statuses"]:
        seen.setdefault(s["context"], []).append(s["state"])
    out = {}
    for name in required:
        states = seen.get(name, [])
        out[name] = ("missing" if not states else "failure" if any(s in FAILED for s in states)
                     else "success" if all(s in PASSED for s in states) else "pending")
    return out


def required(tree):
    """The checks to wait for; paths and version only once main has the workflow that writes them."""
    if v.show("origin/main", root=tree)(".github/workflows/pull-request.yml") is None:
        say("main has no pull-request.yml yet: paths and version not waited for")
        return tuple(c for c in REQUIRED if c not in ("paths", "version"))
    return REQUIRED


def wait(sha, names):
    start = time.monotonic()
    last = None
    while time.monotonic() - start < WAIT_S:
        st = checks(sha, names)
        line = ", ".join(f"{k} {s}" for k, s in st.items())
        if line != last:
            say(line)
            last = line
        failed = [k for k, s in st.items() if s == "failure"]
        if failed:
            raise SystemExit(f"checks failed on {sha[:7]}: {', '.join(failed)}")
        if all(s == "success" for s in st.values()):
            return
        time.sleep(20)
    raise SystemExit(f"the checks on {sha[:7]} did not finish in {WAIT_S // 60} minutes")


def again(n, main_n, now):
    """Number once more before the merge? Only a version whose main has become another version meanwhile – a pull
    request without a version merges onto any main, and a push of TODO.md or a concept leaves the number alone."""
    return n is not None and now != main_n


def main(argv=None):
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))   # a stopped run still removes its worktree
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pr", type=int)
    ap.add_argument("--major", action="store_true", help="the major number – only on the owner's word")
    ap.add_argument("--dry-run", action="store_true", help="number in a worktree, show the diff, push nothing")
    args = ap.parse_args(argv)

    pr = gh_json("pr", "view", str(args.pr), "--json", "number,state,headRefName,baseRefName,title,isCrossRepository")
    if pr["state"] != "OPEN" or pr["baseRefName"] != "main" or pr["isCrossRepository"]:
        raise SystemExit(f"#{args.pr}: not an open pull request from this repository into main")
    branch = pr["headRefName"]
    tree = Path(tempfile.mkdtemp(prefix="edakit-merge-"))
    run("git", "worktree", "add", "-q", "--detach", str(tree), "origin/main")
    try:
        for round_ in range(1, ROUNDS + 1):
            say(f"#{args.pr} {branch}: round {round_}")
            before, sha, main_n, n = prepare(tree, branch, args.major)
            if args.dry_run:
                print(run("git", "diff", f"origin/{branch}", "HEAD", "--", v.INIT, v.MARKETPLACE, v.CHANGELOG,
                          v.CHANGES, cwd=tree).stdout)
                return 0
            if sha != before:
                run("git", "push", "-q", f"--force-with-lease={branch}:{before}", "origin", f"HEAD:refs/heads/{branch}",
                    cwd=tree)
                say(f"pushed {sha[:7]}")
            wait(sha, required(tree))
            run("git", "fetch", "-q", "origin", "main", cwd=tree)
            now = v.number(v.show("origin/main", root=tree)(v.INIT))
            if again(n, main_n, now):
                say(f"main became {now} while the checks ran – numbered again")
                continue
            r = run("gh", "pr", "merge", str(args.pr), *MERGE, "--match-head-commit", sha,
                    "--subject", f"Merge branch '{branch}': {pr['title']}", "--body", "", check=False)
            if r.returncode:
                say(f"merge refused: {(r.stderr or r.stdout).strip()} – again")
                continue
            say(f"merged #{args.pr}" + (f" as edakit {n} – release.yml sets the tag v{n}" if n else " (no version)"))
            return 0
        raise SystemExit(f"main kept moving: {ROUNDS} rounds without a merge")
    finally:
        run("git", "worktree", "remove", "--force", str(tree), check=False)
        shutil.rmtree(tree, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
