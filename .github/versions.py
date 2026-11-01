"""The versions of edakit: the number, the fragments that make one, the changelog, and the checks of a pull request.

Every merge that changes edakit is a version of its own (docs/concepts/done/versioning.md). The number is
`__version__` in edakit/__init__.py; the marketplace entry carries it and points at its tag; CHANGELOG.md has a
section for it. A branch says in changes/<branch>.md whether a project must act when it updates (`minor`) or not
(`patch`); .github/merge.py turns the fragments into the number and the section, and the major number is the owner's.

Read by .github/merge.py, the workflows pull-request.yml and release.yml, and tests/test_version.py. Standard library
only: the checks run from main's checkout on pull_request_target and read the pull request's files with git show,
never running its code.

    python3 .github/versions.py current                          the number on this checkout
    python3 .github/versions.py notes <number>                   that version's changelog section
    python3 .github/versions.py check paths <base> <head> <branch> <pr>
    python3 .github/versions.py check version <base> <head> <branch> <pr>
                                                                 exit 1 on a finding; the first line of the output
                                                                 is the status description for the pull request
    python3 .github/versions.py unnumbered <tag> <rev>           exit 1 when <rev> changes edakit since <tag>
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT = "edakit/__init__.py"
MARKETPLACE = ".claude-plugin/marketplace.json"
CHANGELOG = "CHANGELOG.md"
CHANGES = "changes/"
REPO = "tgd1975/edakit"

NUMBER = re.compile(r'^__version__ = "(\d+\.\d+\.\d+)"$', re.M)
HEADING = re.compile(r"^## (\d+\.\d+\.\d+) – (\d{4}-\d{2}-\d{2})$", re.M)
KINDS = ("patch", "minor", "major")

# What a project never reads: a merge that changes only these is no version. Everything else – edakit/, skills/,
# agents/, hooks/, bin/, handbook/, .claude-plugin/, pyproject.toml, uv.lock and whatever is new – is a version.
NO_VERSION = ("tests/", ".github/", "evals/", "docs/", "examples/", "upstream/", ".claude/", "changes/",
              "CHANGELOG.md", "TODO.md", "CLAUDE.md", "README.md", "LICENSE", ".gitignore")

# The notes lane: a pull request from notes/<topic> changes nothing else and merges itself once green.
LANE = ("docs/concepts/", "TODO.md")
PROPOSALS = ("rules/proposals", "features/proposals")


def under(path, prefixes):
    return any(path == p.rstrip("/") or (p.endswith("/") and path.startswith(p)) for p in prefixes)


def needs_version(paths):
    return [p for p in paths if not under(p, NO_VERSION)]


# --- the number -------------------------------------------------------------------------------------------------

def number(init_text):
    m = NUMBER.search(init_text or "")
    if not m:
        raise ValueError(f"{INIT}: no line __version__ = \"X.Y.Z\"")
    return m.group(1)


def bump(n, kind):
    major, minor, patch = map(int, n.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"unknown kind {kind!r}")


def set_number(init_text, n):
    return NUMBER.sub(f'__version__ = "{n}"', init_text, count=1)


def entry(marketplace_text):
    for plugin in json.loads(marketplace_text)["plugins"]:
        if plugin["name"] == "edakit":
            return plugin
    raise ValueError(f"{MARKETPLACE}: no plugin edakit")


def set_marketplace(marketplace_text, n):
    data = json.loads(marketplace_text)
    for plugin in data["plugins"]:
        if plugin["name"] == "edakit":
            plugin["version"] = n
            plugin["source"] = {"source": "github", "repo": REPO, "ref": f"v{n}"}
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


# --- fragments and the changelog --------------------------------------------------------------------------------

def fragment(name, text):
    """(kind, lines) of one fragment: the first line minor or patch, then the lines for the changelog."""
    first, _, rest = text.strip().partition("\n")
    kind = first.strip()
    if kind not in ("minor", "patch"):
        raise ValueError(f"{CHANGES}{name}: the first line must be minor or patch, not {kind!r}")
    if not rest.strip():
        raise ValueError(f"{CHANGES}{name}: no line for the changelog after {kind!r}")
    return kind, rest.strip()


def is_fragment(path):
    return path.startswith(CHANGES) and path.endswith(".md") and path != CHANGES + "README.md"


def top(changelog_text):
    m = HEADING.search(changelog_text or "")
    return m.group(1) if m else None


def section(changelog_text, n):
    """The lines of version n's section, without its heading; None when it has none."""
    heads = list(HEADING.finditer(changelog_text))
    for i, m in enumerate(heads):
        if m.group(1) == n:
            end = heads[i + 1].start() if i + 1 < len(heads) else len(changelog_text)
            return changelog_text[m.end():end].strip()
    return None


def add_section(changelog_text, n, date, lines):
    block = f"## {n} – {date}\n\n{lines.strip()}\n\n"
    m = HEADING.search(changelog_text)
    if m:
        return changelog_text[:m.start()] + block + changelog_text[m.start():]
    return changelog_text.rstrip("\n") + "\n\n" + block.rstrip("\n") + "\n"


def number_tree(root, main_number, date, major=False):
    """Write the version into a checkout: the number from main's and the fragments, the section, the fragments gone.
    Returns the new number, or None when the tree has no fragment."""
    root = Path(root)
    names = sorted(p.name for p in (root / CHANGES).glob("*.md") if p.name != "README.md")
    if not names:
        return None
    parts = [fragment(name, (root / CHANGES / name).read_text()) for name in names]
    kind = "major" if major else max((k for k, _ in parts), key=KINDS.index)
    n = bump(main_number, kind)
    (root / INIT).write_text(set_number((root / INIT).read_text(), n))
    (root / MARKETPLACE).write_text(set_marketplace((root / MARKETPLACE).read_text(), n))
    lines = "\n".join(text for _, text in parts)
    (root / CHANGELOG).write_text(add_section((root / CHANGELOG).read_text(), n, date, lines))
    for name in names:
        (root / CHANGES / name).unlink()
    return n


# --- the checks of a pull request -------------------------------------------------------------------------------

def check_paths(branch, changed, pipeline):
    """(ok, description, details): a branch family held to its paths."""
    if branch.startswith("notes/"):
        bad = [p for p in changed if not under(p, LANE)]
        if bad:
            return False, f"the notes lane takes only {', '.join(LANE)}", bad
        return True, "notes lane: concepts and TODO.md only", []
    if branch in PROPOSALS:
        if pipeline is None:
            return True, "the pipeline's paths are not on main yet (TD-42): not checked", []
        bad = [p for p in changed if under(p, pipeline)]
        if bad:
            return False, "a proposals branch never changes the pipeline", bad
        return True, "the pipeline untouched", []
    return True, "no paths rule for this branch", []


def check_version(changed, base, head, pr):
    """(ok, description, details) – base and head are callables path -> text (None when the file is missing)."""
    fragments = [p for p in changed if is_fragment(p) and head(p) is not None]
    for p in fragments:
        try:
            fragment(p[len(CHANGES):], head(p))
        except ValueError as e:
            return False, "a fragment is malformed", [str(e)]
    needs = needs_version(changed)
    if fragments:
        return False, f"not numbered yet – set when merging: python3 .github/merge.py {pr}", fragments
    main_n, head_n = number(base(INIT)), number(head(INIT))
    if head_n == main_n:
        if needs:
            return (False, f"changes edakit without a fragment – add {CHANGES}<branch>.md (minor or patch, then "
                           "the lines)", needs)
        return True, "no version: nothing a project reads", []
    allowed = {bump(main_n, k) for k in KINDS}
    problems = []
    if head_n not in allowed:
        problems.append(f"{head_n} does not follow main's {main_n} ({', '.join(sorted(allowed))})")
    e = entry(head(MARKETPLACE))
    if e.get("version") != head_n or e.get("source", {}).get("ref") != f"v{head_n}":
        problems.append(f"{MARKETPLACE}: version and ref must be {head_n} and v{head_n}")
    log = head(CHANGELOG) or ""
    if top(log) != head_n or section(base(CHANGELOG) or "", head_n) is not None:
        problems.append(f"{CHANGELOG}: the top section must be the new {head_n}")
    if problems:
        return False, "the number is inconsistent", problems
    return True, f"numbered {head_n}", []


# --- git ----------------------------------------------------------------------------------------------------------

def git(*args, root=ROOT, check=True):
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def show(rev, root=ROOT):
    def read(path):
        r = subprocess.run(["git", "-C", str(root), "show", f"{rev}:{path}"], capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None
    return read


def changed_files(base, head, root=ROOT):
    return [p for p in git("diff", "--name-only", f"{base}...{head}", root=root).splitlines() if p]


def pipeline_paths(root=ROOT):
    """The proposals pipeline's paths from main's edakit/proposal.py (TD-42); None while it has none."""
    sys.path.insert(0, str(root))
    try:
        from edakit import proposal
    finally:
        sys.path.pop(0)
    return getattr(proposal, "PIPELINE", None)


def main(argv):
    if argv[:1] == ["current"]:
        print(number((ROOT / INIT).read_text()))
        return 0
    if argv[:1] == ["notes"] and len(argv) == 2:
        lines = section((ROOT / CHANGELOG).read_text(), argv[1])
        if lines is None:
            print(f"{CHANGELOG}: no section {argv[1]}", file=sys.stderr)
            return 1
        print(lines)
        return 0
    if argv[:1] == ["unnumbered"] and len(argv) == 3:
        stray = needs_version(changed_files(argv[1], argv[2]))
        if stray:
            print(f"changed since {argv[1]} without a version – merge through .github/merge.py:", *stray, sep="\n  ")
            return 1
        return 0
    if argv[:1] == ["check"] and len(argv) == 6 and argv[1] in ("paths", "version"):
        _, name, base, head, branch, pr = argv
        changed = changed_files(base, head)
        if name == "paths":
            ok, description, details = check_paths(branch, changed, pipeline_paths())
        else:
            ok, description, details = check_version(changed, show(base), show(head), pr)
        print(description[:140], *details, sep="\n")
        return 0 if ok else 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
