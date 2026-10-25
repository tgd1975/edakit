"""Rule proposals: an issue in the edakit repository that asks for a check, a hint, a block, a part fact or the
retirement of a check – written in a project (plugin skill propose-rule), triaged in the edakit repository (skill
triage-rule, run by the Action rule-proposals). Handbook 14.4.

    edakit proposal template          the text to fill in
    edakit proposal seal FILE         check the filled-in text and append its SHA-256 – the body of the issue
    edakit proposal verify FILE|-     every section filled in, and the text is the one that was sealed

The checksum shows that the text was not changed after it was sealed – an issue edited by hand fails on purpose.
Who wrote it is what GitHub says about the author; the Action only works on proposals of the repository owner.
Line ends and trailing blanks are normalised before hashing, a round trip through GitHub may change them.
Exit codes: 0 = ok, 2 = findings, 1 = error.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

VERSION = 1
KINDS = ("check", "hint", "block", "part", "retire")
TITLE = "a few words, like the title of a check"
# section -> what goes in it (also the placeholder of the template)
SECTIONS = {
    "Kind": "one of: " + ", ".join(KINDS),
    "Rule": "the rule in one sentence – what a check would test, what a hint says, what a block is for",
    "Why": "what goes wrong without it",
    "Finding": "where it showed: designator or net, the numbers, the state (circuit hash or commit)",
    "Fix": "what to do about a finding",
    "Sources": "every source opened and read: document number, revision, section – or the project's decision",
    "Origin": "project (owner/repo on GitHub, or its name), decision (D-… in which file), commit",
}
SEAL = re.compile(r"^edakit-proposal v(\d+) sha256:([0-9a-f]{64})$")


def canonical(text):
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip("\n")


def digest(text):
    return hashlib.sha256(canonical(text).encode("utf-8")).hexdigest()


def template():
    parts = [f"## <{TITLE}>"] + [f"### {name}\n<{what}>" for name, what in SECTIONS.items()]
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
    problems = []
    if not title or title == f"<{TITLE}>":
        problems.append(f"no title: the first line is '## <{TITLE}>'")
    for name, what in SECTIONS.items():
        content = sections.get(name)
        if content is None:
            problems.append(f"section '{name}' is missing – {what}")
        elif not content or content == f"<{what}>":
            problems.append(f"section '{name}' is not filled in – {what}")
    kind = sections.get("Kind")
    if kind and kind != f"<{SECTIONS['Kind']}>" and kind.split()[0].lower() not in KINDS:
        problems.append(f"kind '{kind.split()[0]}' – {SECTIONS['Kind']}")
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


def main(args):
    if args.action == "template":
        sys.stdout.write(template())
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
