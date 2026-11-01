"""Proposals: an issue in the edakit repository, written in a project and triaged in the edakit repository by the
Action proposals. Two sorts, told apart by the section Kind:

- a rule proposal asks for a fact (a row of data: a part fact, a default, a table row), a relation (a new code of an
  engine, a hint too), a domain change (a severity, a required fact, a reviewer's question), a block, or the
  retirement of a code (plugin skill propose-rule, repository skill triage-rule; handbook 14.4)
- a feature proposal asks for something edakit cannot do yet and a project had to build or work around itself
  (plugin skill propose-feature, repository skill triage-feature; handbook 11.6)

An issue someone else opened is a request: the Action wrap wraps its texts – plain text, numbered within the issue,
sealed –, and the owner answers with a command – review, accept or reject (repository skill triage-request).

    edakit proposal template [--feature]   the text to fill in
    edakit proposal seal FILE              check the filled-in text and append its SHA-256 – the body of the issue
    edakit proposal verify FILE|-          every section filled in, and the text is the one that was sealed

The Actions proposals and wrap run this module with the system's Python, from main, before and after Claude
(docs/concepts/done/proposals-pipeline.md) – it imports nothing but the standard library:

    python3 -m edakit.proposal queue ISSUES TRIGGER    what the run triages (env OWNER, SINCE): the matrix as JSON
    python3 -m edakit.proposal input ISSUE DIR         what Claude reads: DIR/mode, DIR/thread.md, DIR/proposal.md
    python3 -m edakit.proposal verify FILE             as above, without the CLI's dependencies
    python3 -m edakit.proposal build N BASE [HEAD]     the commits of a triage, checked before the push
    python3 -m edakit.proposal wrap ISSUE DIR          the texts by others not wrapped yet: DIR/1.md … one per comment
    python3 -m edakit.proposal start ISSUE             the owner's command waiting on an issue by someone else

The checksum shows that the text was not changed after it was sealed – an issue edited by hand fails on purpose.
Who wrote it is what GitHub says about the author; the Action triages the repository owner's proposals, and on an
issue by someone else only what a command of the owner releases: the texts wrapped before it.
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
# the last line of a text by someone else that the Action wrap posted: its number within the issue, where it stands –
# the issue's title and body, or a comment by its node id – and the SHA-256 of the text in its code block
WRAP = re.compile(r"^edakit-wrapped v1 (\d+) (issue|comment:[\w-]+) sha256:([0-9a-f]{64})$")
CUT = 60000                                     # UTF-8 bytes of a wrapped text – a comment holds 65536 characters
COMMANDS = ("review", "accept", "reject")       # the owner's answers on an issue by someone else
# the end of the first wrapped text of an issue: what the owner answers with
HOW = "\n".join([
    "---",
    "",
    "Waiting for the repository owner: nothing on this issue reaches Claude until the owner answers with a comment "
    "that starts with a command.",
    "",
    "| Command | What happens |",
    "| --- | --- |",
    "| `review` | Claude reviews it – sound, feasible, does it fit edakit? – and answers **Review**, with questions for "
    "the author |",
    "| `accept` | Claude builds it into the proposals pull request: **Accepted**, or **Question** or **Rejected** if "
    "building shows otherwise |",
    "| `reject` | closed as not planned; the rest of the comment is the reason |",
    "",
    "Every later text by someone else is wrapped too, numbered, and waits for the next command.",
])
# the pipeline: what starts, reads, judges, builds and publishes proposals – a build never touches it (the owner's
# no-go of 2026-11-01); a directory ends in '/'
PIPELINE = (".github/", ".claude/", "CLAUDE.md", "edakit/proposal.py", "tests/test_proposal.py",
            "skills/propose-rule/", "skills/propose-feature/", "pyproject.toml", "uv.lock")
# who posts the triage's results and the wrapped texts: the workflow's own token since 0.3.1 – not "claude", a login
# a GitHub user holds too, and gh shows the Claude app's comments under it
TRIAGE = ("github-actions", "github-actions[bot]")
RESULT = re.compile(r"\*\*(Accepted|Rejected|Question|Review)\*\*")
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


def command(body):
    """The owner's command a comment starts with – review, accept or reject, in any case, followed by the end, a blank
    or a mark ('accept – 1b') – or None: 'reviewed' and 'please review' are none."""
    m = re.match(r"([A-Za-z]+)(?![\w-])", body or "")
    word = m.group(1).lower() if m else None
    return word if word in COMMANDS else None


def start(comment, owner):
    """What a comment starts on an issue by someone else: the owner's command, or 'triage' for a sealed proposal of
    the owner; None for anything else – any other comment of the owner starts nothing."""
    if _who(comment) != owner:
        return None
    return command(comment.get("body", "")) or ("triage" if SEALED in comment.get("body", "") else None)


def pending(issue, owner):
    """(what, comment): the owner's newest start on an issue by someone else, while no result of the triage came after
    it; None otherwise, and on the owner's own issues."""
    if _who(issue) == owner:
        return None
    found = None
    for c in sorted(issue.get("comments", []), key=lambda c: c["createdAt"]):
        what = start(c, owner)
        if what:
            found = (what, c)
        elif found and is_result(c):
            found = None
    return found


def fence(text):
    """A code fence longer than every run of backticks in the text, so that nothing in it ends the block."""
    return "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", text)), default=0))


def wrap_seal(comment):
    """(n, source, sha) of a comment the Action wrap posted – its last line –, else None."""
    if _who(comment) not in TRIAGE:
        return None
    m = WRAP.match(canonical(comment.get("body", "")).split("\n")[-1])
    return (int(m.group(1)), m.group(2), m.group(3)) if m else None


def unwrap(comment):
    """A comment the Action wrap posted: {n, header, text, holds} – the text its code block holds, and whether the
    seal still matches it –, else None."""
    seal = wrap_seal(comment)
    if seal is None:
        return None
    lines = canonical(comment["body"]).split("\n")
    text = None
    for i, line in enumerate(lines):
        m = re.fullmatch(r"(`{3,})text", line)
        if m and m.group(1) in lines[i + 1:]:
            text = "\n".join(lines[i + 1:lines.index(m.group(1), i + 1)])
            break
    return {"n": seal[0], "header": lines[0], "text": text, "holds": text is not None and digest(text) == seal[2]}


def wrap_comment(n, source, what, who, when, text, cut=False, replaces=None, how=False):
    """The comment that wraps a text by someone else: its number within the issue, the text as plain text in a code
    block – no link, image or mention in it renders –, and as its last line the seal over exactly that text."""
    head = f"**Wrapped {n}** – {what} by `{who}`" + (f", {when[:10]} {when[11:16]} UTC" if when else "")
    head += f" – edited, replaces Wrapped {replaces}" if replaces else ""
    head += f" – cut to its first {CUT} bytes" if cut else ""
    f = fence(text)
    parts = [head, f"{f}text\n{text}\n{f}"] + ([HOW] if how else [])
    return "\n\n".join(parts + [f"edakit-wrapped v1 {n} {source} sha256:{digest(text)}"]) + "\n"


def to_wrap(issue, owner):
    """The comments the Action wrap posts on an issue by someone else: every text by someone else – the issue's title
    and body, each comment by anyone but the owner and the workflow – not wrapped as it stands now, numbered on from
    the last wrapped one; an edited text again, naming the number it replaces. The first of an issue lists the
    owner's commands. Nothing on the owner's own issues."""
    if _who(issue) == owner:
        return []
    comments = sorted(issue.get("comments", []), key=lambda c: c["createdAt"])
    seals = sorted(s for s in map(wrap_seal, comments) if s)
    last = max((n for n, _, _ in seals), default=0)
    done = {(source, sha) for _, source, sha in seals}
    newest = {source: n for n, source, _ in seals}
    texts = [] if _who(issue) in TRIAGE else [("issue", "the issue", issue.get("createdAt", ""), _who(issue),
                                               f"{issue.get('title', '')}\n\n{issue.get('body') or ''}")]
    texts += [(f"comment:{c['id']}", "a comment", c["createdAt"], _who(c), c.get("body", ""))
              for c in comments if _who(c) != owner and _who(c) not in TRIAGE]
    out = []
    for source, what, when, who, text in texts:
        text = canonical(text)
        cut = len(text.encode("utf-8")) > CUT        # bytes: within the limit however GitHub counts
        text = canonical(text.encode("utf-8")[:CUT].decode("utf-8", errors="ignore")) if cut else text
        if (source, digest(text)) in done:
            continue
        last += 1
        out.append(wrap_comment(last, source, what, who, when, text, cut, newest.get(source), how=last == 1))
        done.add((source, digest(text)))
        newest[source] = last
    return out


def reading(issue, owner):
    """What Claude reads: (mode, proposal, thread) – 'triage' with the owner's sealed text and its thread
    (owners_text); 'review' or 'accept' for the owner's command on an issue by someone else, with the thread alone:
    the wrapped texts that came before the command (one whose seal no longer holds named as left out), the owner's
    comments and the triage's results, oldest first – never a text by someone else as its author wrote it. None when
    nothing of the owner's starts a triage here."""
    found = pending(issue, owner)
    if _who(issue) == owner or (found and found[0] == "triage"):
        text, thread = owners_text(issue, owner)
        return None if text is None else ("triage", text, thread)
    if found is None or found[0] == "reject":
        return None
    items = []
    for c in sorted(issue.get("comments", []), key=lambda c: c["createdAt"]):
        w = unwrap(c)
        if w is None:
            if _who(c) == owner or is_result(c):
                items.append(f"### {'the owner' if _who(c) == owner else 'the triage'}, {c['createdAt']}\n\n"
                             f"{c['body'].strip()}")
        elif c["createdAt"] < found[1]["createdAt"] and w["holds"]:
            f = fence(w["text"])
            items.append(f"### {w['header'].replace('**', '')} – someone else's text, quoted\n\n"
                         f"{f}text\n{w['text']}\n{f}")
        elif c["createdAt"] < found[1]["createdAt"]:
            items.append(f"### Wrapped {w['n']} – left out: its seal does not match its text")
    return found[0], None, "\n\n".join(items)


def waiting(issue, owner):
    """A proposal still waiting for its triage: the owner's sealed text and no result yet, or a question the owner
    answered since – in a comment, or by sealing the own issue's body again. On an issue by someone else: the owner's
    newest command – review or accept – or sealed comment, with no result after it."""
    if _who(issue) != owner:
        found = pending(issue, owner)
        return found is not None and found[0] != "reject"
    labels = _labels(issue)
    if labels & {"accepted", "rejected"} or owners_text(issue, owner)[0] is None:
        return False
    if "needs-info" not in labels:
        return True
    asked = max((c["createdAt"] for c in issue.get("comments", []) if is_result(c)), default="")
    edited = (issue.get("editor") or {}).get("login") == owner and (issue.get("lastEditedAt") or "") > asked
    return edited or any(_who(c) == owner and c["createdAt"] > asked for c in issue.get("comments", []))


def queue(issues, owner, trigger=None, since=""):
    """What a run triages, one after another, at most MOST: the issue that started it (`trigger`, with its comments)
    – the owner's own unless a triage answered it after its event (`since`): then it waited behind the run that took
    it along; one by someone else while the owner's command waits –, then every proposal still waiting, oldest
    first."""
    pool = {i["number"]: i for i in issues}
    if trigger:
        pool[trigger["number"]] = {**pool.get(trigger["number"], {}), **trigger}
    ready = sorted(n for n, i in pool.items() if waiting(i, owner))
    if trigger:
        n = trigger["number"]
        if (not any(is_result(c) and c["createdAt"] > since for c in trigger.get("comments", []))
                if _who(trigger) == owner else n in ready):
            ready = [n] + [m for m in ready if m != n]
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
    """The steps of the Actions (module docstring). Exit codes: 0 = ok, 2 = findings, 3 = nothing of the owner's starts
    a triage on the issue."""
    ap = argparse.ArgumentParser(prog="python3 -m edakit.proposal")
    sub = ap.add_subparsers(dest="action", required=True)
    p = sub.add_parser("queue")
    p.add_argument("issues", help="JSON list of the open issues to consider")
    p.add_argument("trigger", help="JSON of the issue that started the run, with its comments – null when by hand")
    for action in ("input", "wrap"):
        p = sub.add_parser(action)
        p.add_argument("issue")
        p.add_argument("dir")
    p = sub.add_parser("start")
    p.add_argument("issue")
    p = sub.add_parser("verify")
    p.add_argument("file")
    p = sub.add_parser("build")
    p.add_argument("n", type=int)
    p.add_argument("base")
    p.add_argument("head", nargs="?", default="HEAD")
    args = ap.parse_args(argv)
    owner = os.environ.get("OWNER", "")
    if args.action == "queue":
        print(json.dumps(queue(json.loads(Path(args.issues).read_text()), owner,
                               json.loads(Path(args.trigger).read_text()), os.environ.get("SINCE", ""))))
        return 0
    if args.action == "start":
        found = pending(json.loads(Path(args.issue).read_text()), owner)
        print(found[0] if found else "")
        return 0
    if args.action in ("input", "wrap"):
        issue = json.loads(Path(args.issue).read_text())
        out = Path(args.dir)
        out.mkdir(parents=True, exist_ok=True)
        if args.action == "wrap":
            bodies = to_wrap(issue, owner)
            for i, body in enumerate(bodies, 1):
                (out / f"{i}.md").write_text(body, encoding="utf-8")
            print(f"{len(bodies)} text(s) by others to wrap on #{issue.get('number')}")
            return 0
        found = reading(issue, owner)
        if found is None:
            print("nothing of the owner's starts a triage on this issue")
            return 3
        mode, text, thread = found
        (out / "mode").write_text(mode + "\n", encoding="utf-8")
        if text is not None:
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
