"""A stand-in for the GitHub CLI in the tests of `edakit release publish` (test_publish.py): it writes each call's
arguments into $FAKE_GH/calls.jsonl and keeps the releases it made in $FAKE_GH/releases/<tag>/ – meta.json and the
assets – so that a second publish finds the first. It answers only what publish asks:

    auth status | repo view --json url -q .url | api repos/{owner}/{repo}/git/matching-refs/tags/<prefix> --jq .[].ref
    release list --json … | release download TAG --pattern P … --dir D | release create TAG … FILES |
    release edit TAG --prerelease=false

$FAKE_GH/logged_out: auth status fails. $FAKE_GH/tags: tags the remote has besides those of the releases, one a line.
$FAKE_GH_REMOTE: the bare repository that stands for GitHub – a release that is no draft tags its target there, as
GitHub does.
"""

import fnmatch
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/example/led-bar"


def state():
    return Path(os.environ["FAKE_GH"])


def folders():
    """The folder of every release, oldest first: releases/<n>-<tag>/ with meta.json and assets/."""
    d = state() / "releases"
    return sorted(d.iterdir()) if d.is_dir() else []


def releases():
    return [json.loads((r / "meta.json").read_text()) for r in folders()]


def folder(tag):
    """The folder of the release with this tag – the release, not a draft, where there is one."""
    found = [r for r in folders() if json.loads((r / "meta.json").read_text())["tagName"] == tag]
    return next((r for r in found if not json.loads((r / "meta.json").read_text())["isDraft"]), found[0] if found else None)


def flags(args):
    """({flag: [values]}, positional): every --flag takes the value after it, except the boolean ones."""
    boolean = {"--prerelease", "--draft", "--exclude-drafts"}
    out, pos, i = {}, [], 0
    while i < len(args):
        a = args[i]
        if a.startswith("--") and "=" in a:
            k, _, v = a.partition("=")
            out.setdefault(k, []).append(v)
        elif a in boolean:
            out.setdefault(a, []).append(True)
        elif a.startswith("-"):
            out.setdefault(a, []).append(args[i + 1])
            i += 1
        else:
            pos.append(a)
        i += 1
    return out, pos


def main(argv):
    STATE = state()
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "calls.jsonl").open("a") as f:
        f.write(json.dumps(argv) + "\n")
    if argv[:2] == ["auth", "status"]:
        if (STATE / "logged_out").exists():
            print("You are not logged into any GitHub hosts. To log in, run: gh auth login", file=sys.stderr)
            return 1
        return 0
    if argv[:2] == ["repo", "view"]:
        print(REPO)
        return 0
    if argv[0] == "api":
        prefix = argv[1].split("/git/matching-refs/tags/", 1)[1]
        extra = (STATE / "tags").read_text().split() if (STATE / "tags").exists() else []
        for tag in [r["tagName"] for r in releases() if not r["isDraft"]] + extra:
            if tag.startswith(prefix):
                print(f"refs/tags/{tag}")
        return 0
    opts, pos = flags(argv[2:])
    if argv[:2] == ["release", "list"]:
        rels = [r for r in releases() if not ("--exclude-drafts" in opts and r["isDraft"])]
        print(json.dumps([{k: r[k] for k in ("tagName", "name", "createdAt")} for r in rels]))
        return 0
    if argv[:2] == ["release", "download"]:
        if folder(pos[0]) is None:
            print("release not found", file=sys.stderr)
            return 1
        assets = folder(pos[0]) / "assets"
        hits = [f for f in sorted(assets.iterdir()) if any(fnmatch.fnmatch(f.name, p) for p in opts["--pattern"])]
        for f in hits:
            shutil.copy(f, Path(opts["--dir"][0]) / f.name)
        if not hits:
            print("no assets match the file pattern", file=sys.stderr)
            return 1
        return 0
    if argv[:2] == ["release", "create"]:
        tag, files = pos[0], pos[1:]
        if any(r["tagName"] == tag and not r["isDraft"] for r in releases()):
            print("a release with the same tag name already exists", file=sys.stderr)
            return 1
        n = len(releases())
        d = STATE / "releases" / f"{n:03d}-{tag}"
        (d / "assets").mkdir(parents=True)
        for f in files:
            shutil.copy(f, d / "assets" / Path(f).name)
        meta = {"tagName": tag, "name": opts["--title"][0], "createdAt": f"2026-10-31T00:00:{n:02d}Z",
                "isDraft": "--draft" in opts, "isPrerelease": "--prerelease" in opts,
                "target": opts.get("--target", [None])[0], "notes": Path(opts["--notes-file"][0]).read_text()}
        (d / "meta.json").write_text(json.dumps(meta))
        if not meta["isDraft"] and os.environ.get("FAKE_GH_REMOTE"):
            subprocess.run(["git", "--git-dir", os.environ["FAKE_GH_REMOTE"], "tag", tag, meta["target"]], check=True)
        print(f"{REPO}/releases/tag/{tag}")
        return 0
    if argv[:2] == ["release", "edit"]:
        r = folder(pos[0])
        if r is None:
            print("release not found", file=sys.stderr)
            return 1
        meta = json.loads((r / "meta.json").read_text())
        meta["isPrerelease"] = opts.get("--prerelease", ["true"])[0] != "false"
        (r / "meta.json").write_text(json.dumps(meta))
        print(f"{REPO}/releases/tag/{pos[0]}")
        return 0
    print(f"fake gh: {' '.join(argv)} is not faked", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
