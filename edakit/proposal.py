"""Proposals: an issue in the edakit repository, written in a project and triaged in the edakit repository by the
Action proposals. Two sorts, told apart by the section Kind:

- a rule proposal asks for a fact (a row of data: a part fact, a default, a table row), a relation (a new code of an
  engine, a hint too), a domain change (a severity, a required fact, a reviewer's question), a block, or the
  retirement of a code (plugin skill propose-rule, repository skill triage-rule; handbook 14.4)
- a feature proposal asks for something edakit cannot do yet and a project had to build or work around itself
  (plugin skill propose-feature, repository skill triage-feature; handbook 11.6)

    edakit proposal template [--feature]   the text to fill in
    edakit proposal seal FILE              check the filled-in text and append its SHA-256 – the body of the issue
    edakit proposal verify FILE|-          every section filled in, and the text is the one that was sealed

The Action proposals runs this module with the system's Python, from main, before and after Claude
(docs/concepts/done/proposals-pipeline.md) – it imports nothing but the standard library:

    python3 -m edakit.proposal queue ISSUES COMMENTS   what the run triages (env OWNER, N, SINCE): the matrix as JSON
    python3 -m edakit.proposal input ISSUE DIR         the owner's text only: DIR/proposal.md and DIR/thread.md
    python3 -m edakit.proposal verify FILE             as above, without the CLI's dependencies
    python3 -m edakit.proposal build N BASE [HEAD]     the commits of a triage, checked before the push

The checksum shows that the text was not changed after it was sealed – an issue edited by hand fails on purpose.
Who wrote it is what GitHub says about the author; the Action only works on proposals of the repository owner.
Line ends and trailing blanks are normalised before hashing, a round trip through GitHub may change them.
Exit codes: 0 = ok, 2 = findings, 1 = error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

VERSION = 1
RULE_KINDS = ("fact", "relation", "domain", "block", "retire")
OLD_KINDS = {"check": "relation", "hint": "relation", "part": "fact"}   # proposals sealed before the restructuring
FEATURE = "feature"
KINDS = RULE_KINDS + (FEATURE,)
TITLE = "a few words, like the title of a check"
# section -> what goes in it (also the placeholder of the template)
SECTIONS = {
    "Kind": "one of: " + ", ".join(RULE_KINDS),
    "Rule": "the rule in one sentence – the fact and its source, what a code would find, what a domain changes, "
            "what a block is for",
    "Why": "what goes wrong without it",
    "Finding": "where it showed: designator or net, the numbers, the state (circuit hash or commit)",
    "Fix": "what to do about a finding",
    "Sources": "every source opened and read: document number, revision, section – or the project's decision",
    "Origin": "project (owner/repo on GitHub, or its name), decision (D-… in which file), commit",
}
FEATURE_SECTIONS = {
    "Kind": FEATURE,
    "Capability": "what edakit should be able to do, in one or two sentences – for any board with this pattern",
    "Gap": "what edakit does today on the origin: the command and its output or numbers – a false finding, a crash, "
           "a part of the circuit left out, a step done by hand",
    "Reference": "how the origin does it today: file, function, commit, and the method in words – code only with the "
                 "owner's OK, the issue is public",
    "Interface": "the keys in edakit.toml or a board or schematic file, fields in graph or parts entries, or options "
                 "it needs, each with the default that leaves existing projects as they are – or 'none'",
    "Test": "how a test shows it without EasyEDA: what is built into the example, what edakit reports before and after",
    "Origin": SECTIONS["Origin"],
}
SEAL = re.compile(r"^edakit-proposal v(\d+) sha256:([0-9a-f]{64})$")
SEALED = "edakit-proposal v"                    # the marker the workflow's if looks for
# the pipeline: what starts, reads, judges, builds and publishes proposals – a build never touches it (the owner's
# no-go of 2026-11-01); a directory ends in '/'
PIPELINE = (".github/", ".claude/", "CLAUDE.md", "edakit/proposal.py", "tests/test_proposal.py",
            "skills/propose-rule/", "skills/propose-feature/", "pyproject.toml", "uv.lock")
TRIAGE = ("github-actions", "github-actions[bot]", "claude", "claude[bot]")    # who writes the triage's results
RESULT = re.compile(r"\*\*(Accepted|Rejected|Question)\*\*")
MOST = 8                                        # proposals one run triages; the rest waits for the next


def canonical(text):
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip("\n")


def digest(text):
    return hashlib.sha256(canonical(text).encode("utf-8")).hexdigest()


def kind_of(sections):
    """The first word of the section Kind, lower case ('' when missing)."""
    words = (sections.get("Kind") or "").split()
    return words[0].lower() if words else ""


def sections_for(kind):
    return FEATURE_SECTIONS if kind == FEATURE else SECTIONS


def template(kind=None):
    """The text to fill in; for a feature proposal the kind is filled in already."""
    wanted = sections_for(kind)
    parts = [f"## <{TITLE}>"] + [f"### {name}\n{what if name == 'Kind' and kind == FEATURE else f'<{what}>'}"
                                 for name, what in wanted.items()]
    return "\n\n".join(parts) + "\n"


def split(body):
    """(text, version, sha) – version and sha None without a seal."""
    lines = canonical(body).split("\n")
    m = SEAL.match(lines[-1])
    if not m:
        return canonical(body), None, None
    rest = lines[:-1]
    while rest and not rest[-1]:
        rest.pop()
    if rest and rest[-1] == "---":
        rest.pop()
    return "\n".join(rest).strip("\n"), int(m.group(1)), m.group(2)


def parse(text):
    """(title, {section: content}) of a proposal text."""
    title, sections, current = None, {}, None
    for line in canonical(text).split("\n"):
        if line.startswith("### "):
            current = line[4:].strip()
            sections[current] = []
        elif line.startswith("## ") and title is None and current is None:
            title = line[3:].strip()
        elif current is not None:
            sections[current].append(line)
    return title, {name: "\n".join(lines).strip() for name, lines in sections.items()}


def check(text):
    """What is missing in the text itself."""
    title, sections = parse(text)
    kind = kind_of(sections)
    problems = []
    if not title or title == f"<{TITLE}>":
        problems.append(f"no title: the first line is '## <{TITLE}>'")
    for name, what in sections_for(kind).items():
        content = sections.get(name)
        if content is None:
            problems.append(f"section '{name}' is missing – {what}")
        elif not content or content == f"<{what}>":
            problems.append(f"section '{name}' is not filled in – {what}")
    if kind and sections.get("Kind") != f"<{SECTIONS['Kind']}>" and kind not in KINDS and kind not in OLD_KINDS:
        problems.append(f"kind '{sections['Kind'].split()[0]}' – one of: {', '.join(KINDS)}")
    return problems


def seal(text):
    """(body, problems): the text with its seal, or the problems that keep it from being sealed. A sealed text is
    sealed again – that is how a proposal is changed after a question."""
    text = split(text)[0]
    problems = check(text)
    if problems:
        return None, problems
    return f"{text}\n\n---\nedakit-proposal v{VERSION} sha256:{digest(text)}\n", []


def verify(body):
    text, version, sha = split(body)
    if version is None:
        return [f"no seal: the last line is not 'edakit-proposal v{VERSION} sha256:…' – seal it with "
                "`edakit proposal seal`"] + check(text)
    problems = []
    if version != VERSION:
        problems.append(f"seal version v{version}, this edakit knows v{VERSION}")
    elif sha != digest(text):
        problems.append("the checksum does not match: the text was changed after it was sealed")
    return problems + check(text)


def pipeline_paths(paths):
    """The paths of the pipeline among `paths`, sorted."""
    return sorted(p for p in paths if any(p == q or (q.endswith("/") and p.startswith(q)) for q in PIPELINE))


def check_build(commits, n):
    """What keeps a triage's build from being pushed: commits as (sha, message, paths), oldest first."""
    if not commits:
        return []
    problems = [f"{len(commits)} commits – one per proposal"] if len(commits) > 1 else []
    problems += [f"the subject does not end in (#{n})" for _, message, _ in commits
                 if not message.strip().split("\n")[0].rstrip().endswith(f"(#{n})")]
    touched = pipeline_paths({p for _, _, paths in commits for p in paths})
    return problems + ([f"it touches the pipeline: {', '.join(touched)}"] if touched else [])


def _who(comment):
    return (comment.get("author") or {}).get("login", "")


def is_result(comment):
    """A comment of the triage: written by the workflow and starting with its result."""
    return _who(comment) in TRIAGE and bool(RESULT.match(comment.get("body", "").lstrip()))


def _labels(issue):
    return {label["name"] for label in issue.get("labels", [])}


def owners_text(issue, owner):
    """(the proposal, the thread) Claude reads: the owner's sealed text – the body of the owner's issue, or on an issue
    by someone else the owner's newest sealed comment – and the owner's comments and the triage's results, oldest
    first. Nothing anyone else wrote; (None, '') without such a text."""
    comments = sorted(issue.get("comments", []), key=lambda c: c["createdAt"])
    if _who(issue) == owner and SEALED in issue.get("body", ""):
        text, own = issue["body"], None
    else:
        sealed = [c for c in comments if _who(c) == owner and SEALED in c["body"]]
        if not sealed:
            return None, ""
        own = sealed[-1]
        text = own["body"]
    thread = [f"### {'the triage' if is_result(c) else 'the owner'}, {c['createdAt']}\n\n{c['body'].strip()}"
              for c in comments if c is not own and (_who(c) == owner or is_result(c))]
    return text, "\n\n".join(thread)


def waiting(issue, owner):
    """A proposal still waiting for its triage: the owner's sealed text and no result yet, or a question the owner
    answered since – in a comment, or by sealing the own issue's body again."""
    labels = _labels(issue)
    if labels & {"accepted", "rejected"} or owners_text(issue, owner)[0] is None:
        return False
    if "needs-info" not in labels:
        return True
    asked = max((c["createdAt"] for c in issue.get("comments", []) if is_result(c)), default="")
    edited = (issue.get("editor") or {}).get("login") == owner and (issue.get("lastEditedAt") or "") > asked
    return edited or any(_who(c) == owner and c["createdAt"] > asked for c in issue.get("comments", []))


def queue(issues, owner, trigger=None, since="", comments=()):
    """What a run triages, one after another, at most MOST: the issue that started it – unless a triage answered it
    after its event (`since`; `comments` are the issue's): then it waited behind the run that took it along –, then
    every proposal still waiting, oldest first."""
    ready = sorted({i["number"] for i in issues if waiting(i, owner)})
    if trigger is not None and not any(is_result(c) and c["createdAt"] > since for c in comments):
        ready = [trigger] + [n for n in ready if n != trigger]
    return ready[:MOST]


def _commits(base, head):
    log = subprocess.run(["git", "log", "--reverse", "--format=%H%x00%B%x01", f"{base}..{head}"], check=True,
                         capture_output=True, text=True).stdout
    out = []
    for entry in filter(str.strip, log.split("\x01")):
        sha, message = entry.strip("\n").split("\x00", 1)
        paths = subprocess.run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "-m", sha], check=True,
                               capture_output=True, text=True).stdout.split()
        out.append((sha, message.strip(), paths))
    return out


def ci(argv):
    """The steps of the Action (module docstring). Exit codes: 0 = ok, 2 = findings, 3 = no text of the owner."""
    ap = argparse.ArgumentParser(prog="python3 -m edakit.proposal")
    sub = ap.add_subparsers(dest="action", required=True)
    p = sub.add_parser("queue")
    p.add_argument("issues", help="JSON list of the open issues to consider")
    p.add_argument("comments", help="JSON list of the comments of the issue that started the run")
    p = sub.add_parser("input")
    p.add_argument("issue")
    p.add_argument("dir")
    p = sub.add_parser("verify")
    p.add_argument("file")
    p = sub.add_parser("build")
    p.add_argument("n", type=int)
    p.add_argument("base")
    p.add_argument("head", nargs="?", default="HEAD")
    args = ap.parse_args(argv)
    owner = os.environ.get("OWNER", "")
    if args.action == "queue":
        n = os.environ.get("N") or None
        print(json.dumps(queue(json.loads(Path(args.issues).read_text()), owner, int(n) if n else None,
                               os.environ.get("SINCE", ""), json.loads(Path(args.comments).read_text()))))
        return 0
    if args.action == "input":
        text, thread = owners_text(json.loads(Path(args.issue).read_text()), owner)
        if text is None:
            print("no sealed text of the owner on this issue")
            return 3
        out = Path(args.dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "proposal.md").write_text(text, encoding="utf-8")
        (out / "thread.md").write_text(thread + "\n", encoding="utf-8")
        return 0
    if args.action == "verify":
        problems = verify(Path(args.file).read_text(encoding="utf-8"))
    else:
        problems = check_build(_commits(args.base, args.head), args.n)
    for p in problems:
        print(f"- {p}")
    return 2 if problems else 0


def main(args):
    if args.action == "template":
        sys.stdout.write(template(FEATURE if args.feature else None))
        return 0
    if not args.file:
        print(f"edakit proposal {args.action}: FILE needed (- for stdin)", file=sys.stderr)
        return 1
    try:
        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    except OSError as e:
        print(f"edakit proposal: {e}", file=sys.stderr)
        return 1
    if args.action == "seal":
        body, problems = seal(text)
        if problems:
            print("not sealed:")
            for p in problems:
                print(f"  - {p}")
            return 2
        if args.out:
            Path(args.out).write_text(body, encoding="utf-8")
            print(f"sealed: {args.out} (sha256 {digest(split(body)[0])[:12]}…)")
        else:
            sys.stdout.write(body)
        return 0
    problems = verify(text)
    if problems:
        print("proposal not ok:")
        for p in problems:
            print(f"  - {p}")
        return 2
    print("proposal ok: every section filled in, checksum matches")
    return 0


if __name__ == "__main__":
    sys.exit(ci(sys.argv[1:]))
