"""The addresses the automation reads in the handbook (docs/concepts/new/documentation.md, "What the automation reads"):
every "handbook N" and "handbook N.N" named in the code, the skills, the agents and this repository's skills is a
chapter or a section of the handbook, every chapter file they name exists, and every path a skill or an agent opens
under ${CLAUDE_PLUGIN_ROOT} exists. Red before a section disappears, not after a session finds the gap."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHERE = ("edakit", "skills", "agents", ".claude", "hooks")      # what reads the handbook
KINDS = {".py", ".md", ".toml", ".sh", ".json", ".mjs", ".yml"}
NUM = r"\d+(?:\.\d+)*"
SECTION = re.compile(rf"[Hh]andbook,?\s+(?:chapters?\s+|sections?\s+)?({NUM}(?:\s*(?:,|/|–|-|and|or|to)\s*{NUM})*)")
CHAPTER = re.compile(r"(?<![\w.-])(?:handbook/)?(\d\d-[a-z][\w-]*\.md)")
PLUGIN = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s`\"')\\]+)")


def files():
    for top in WHERE:
        for p in sorted((ROOT / top).rglob("*")):
            if p.suffix in KINDS and p.is_file() and "node_modules" not in p.parts:
                yield p, p.read_text(encoding="utf-8", errors="replace")


def numbers():
    """{"8", "8.6", …}: the chapters and sections of the handbook, by the numbers of their headings."""
    out = set()
    for f in (ROOT / "handbook").glob("[0-9]*.md"):
        out |= set(re.findall(rf"^#+ ({NUM})\s", f.read_text(encoding="utf-8"), re.M))
    return out


def norm(n):
    return ".".join(str(int(x)) for x in n.split("."))     # "handbook 02" is chapter 2


def test_every_section_named_exists():
    have = numbers()
    named, missing = set(), []
    for p, text in files():
        for m in SECTION.finditer(text):
            for n in re.findall(NUM, m.group(1)):
                named.add(norm(n))
                if norm(n) not in have:
                    missing.append(f"{p.relative_to(ROOT)}: handbook {n}")
    assert len(named) > 40                  # the pattern still finds what the automation names
    assert missing == []


def test_every_chapter_file_named_exists():
    named, missing = 0, []
    for p, text in files():
        for m in CHAPTER.finditer(text):
            named += 1
            if not (ROOT / "handbook" / m.group(1)).is_file():
                missing.append(f"{p.relative_to(ROOT)}: {m.group(1)}")
    assert named > 30
    assert missing == []


def test_every_path_a_skill_opens_exists():
    named, missing = 0, []
    for p, text in files():
        for m in PLUGIN.finditer(text):
            named += 1
            pattern = re.sub(r"<[^>]+>", "*", m.group(1).rstrip(".,;:"))
            if not (any(ROOT.glob(pattern.rstrip("/"))) if "*" in pattern else (ROOT / pattern).exists()):
                missing.append(f"{p.relative_to(ROOT)}: ${{CLAUDE_PLUGIN_ROOT}}/{m.group(1)}")
    assert named > 20
    assert missing == []


def test_a_missing_section_is_found():
    text = "see handbook 8.6 and 99.1, the file handbook/99-nowhere.md"
    assert [norm(n) for m in SECTION.finditer(text) for n in re.findall(NUM, m.group(1))] == ["8.6", "99.1"]
    assert "99.1" not in numbers() and "8.6" in numbers()
    assert [m.group(1) for m in CHAPTER.finditer(text)] == ["99-nowhere.md"]
