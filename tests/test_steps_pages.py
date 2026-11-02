"""The steps (docs/steps/), the person's manual of docs/concepts/done/documentation-newcomer.md, step N.2: ten pages and
an index in the order of the walkthrough, each within its budget and in its shape, every command a page quotes printing the
lines it quotes on a fresh copy of the example, every question it quotes standing in a skill, and nothing the
automation reads naming a steps page – the steps change freely, the handbook is what a session reads. Glossary links
and terms, sentences and asides are counted by tests/test_style.py."""

import importlib.util
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STEPS = ROOT / "docs" / "steps"
INDEX = STEPS / "README.md"
PAGES = sorted(STEPS.glob("[0-9][0-9]-*.md"))
EXAMPLE = ROOT / "examples" / "coin-cell-led"
PAGE_WORDS, INDEX_WORDS, ALL_WORDS = 400, 300, 4000
TO_A_CIRCUIT, TO_A_BOARD = 3000, 6000          # words from the start page to a checked circuit, to an ordered board
NEEDS_NGSPICE = {"edakit sim", "edakit gate"}
READERS = ("edakit", "skills", "agents", ".claude")   # what the automation reads: none of it names a steps page


def words(path):
    return len(path.read_text(encoding="utf-8").split())


def first_screen():
    """The start page up to "What it does": the words a newcomer reads before the doors lead on."""
    return len((ROOT / "README.md").read_text(encoding="utf-8").split("\n## What it does")[0].split())


def body_and_links(path):
    """(the page without its last section, the links of its last section "Read on")."""
    text = path.read_text(encoding="utf-8")
    body, sep, tail = text.rpartition("\n## Read on\n")
    return (body, re.findall(r"\]\(([^)\s]+)\)", tail)) if sep else (text, [])


def test_ten_pages_and_an_index_in_the_navigation():
    assert len(PAGES) == 10 and INDEX.is_file()
    assert [int(p.name[:2]) for p in PAGES] == list(range(1, 11))
    index = INDEX.read_text(encoding="utf-8")
    assert [p.name for p in PAGES if f"({p.name})" not in index] == []
    spec = importlib.util.spec_from_file_location("pages", ROOT / "docs" / "pages.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    nav = dict(mod.NAV)
    steps = [p.relative_to(ROOT).as_posix() for p in PAGES]
    assert [s for s, _ in nav["A circuit"]] == ["docs/steps/README.md"] + steps[:7]
    assert [s for s, _ in nav["A board"]] == steps[7:]


def test_the_budgets():
    over = [f"{p.name}: {words(p)}" for p in PAGES if words(p) > PAGE_WORDS]
    assert over == [] and words(INDEX) <= INDEX_WORDS
    assert sum(map(words, PAGES)) + words(INDEX) <= ALL_WORDS


def test_the_way_to_a_circuit_and_to_a_board_is_short():
    """The concept's measure: the first screen, the quickstart and steps 1 to 5 under 3,000 words; to an ordered board
    under 6,000."""
    start = first_screen() + words(ROOT / "docs" / "quickstart.md")
    assert start + sum(map(words, PAGES[:5])) < TO_A_CIRCUIT
    assert start + sum(map(words, PAGES)) < TO_A_BOARD


@pytest.mark.parametrize("page", PAGES, ids=[p.name for p in PAGES])
def test_a_page_has_the_shape_of_a_step(page):
    """The step's number in the title, a first line that says what you have after it, what you do, decide and have, and
    two links at the end – the walkthrough's step and the chapter; no other link into the handbook, no section number
    standing alone."""
    text = page.read_text(encoding="utf-8")
    assert re.match(rf"# {int(page.name[:2])} [A-Z]", text)
    assert text.split("\n\n")[1].startswith("After this step")
    heads = re.findall(r"^## (.+)$", text, re.M)
    assert {"What you do", "What you decide", "What you have", "Read on"} <= set(heads) and heads[-1] == "Read on"
    body, links = body_and_links(page)
    assert len(links) == 2 and links[0].startswith("../../handbook/17-walkthrough.md#")
    assert re.match(r"\.\./\.\./handbook/\d\d-[\w-]+\.md", links[1])
    prose = re.sub(r"```.*?```", "", body, flags=re.S)
    assert "handbook/" not in prose
    assert re.findall(r"\b(?:chapter|section) \d+|\(\d+\.\d+\)", prose) == []


def quoted_commands():
    """[(page, command, [quoted lines])] – each text block of a steps page that starts with `$ edakit …`."""
    out = []
    for page in PAGES:
        for block in re.findall(r"```text\n(.*?)^ *```", page.read_text(encoding="utf-8"), re.S | re.M):
            lines = textwrap.dedent(block).rstrip("\n").splitlines()
            if lines and lines[0].startswith("$ edakit "):
                out.append((page.name, lines[0][2:], [ln for ln in lines[1:] if ln.strip() and ln.strip() != "…"]))
    return out


def test_the_pages_quote_commands():
    assert len(quoted_commands()) >= 8


@pytest.mark.parametrize("page,command,lines", quoted_commands(), ids=[f"{p}:{c}" for p, c, _ in quoted_commands()])
def test_the_command_prints_what_the_page_quotes(tmp_path, page, command, lines):
    if command in NEEDS_NGSPICE and not shutil.which("ngspice"):
        pytest.skip("ngspice not installed")
    work = tmp_path / "coin-cell-led"
    shutil.copytree(EXAMPLE, work, ignore=shutil.ignore_patterns("build"))
    run = subprocess.run([sys.executable, "-c", "import sys; from edakit.cli import main; sys.exit(main())",
                          *command.split()[1:]], cwd=work, capture_output=True, text=True)
    printed = run.stdout + run.stderr
    missing = [ln for ln in lines if ln.split("…")[0].rstrip() not in printed]
    assert missing == [], printed


def test_a_quoted_question_stands_in_a_skill():
    """A question a page quotes – a line of a block quote – is the skill's own words."""
    skills = " ".join(re.sub(r"\s+", " ", p.read_text(encoding="utf-8")) for p in (ROOT / "skills").glob("*/SKILL.md"))
    quoted = [re.sub(r"^>\s*(?:-\s*)?", "", ln).strip() for p in PAGES
              for ln in p.read_text(encoding="utf-8").splitlines() if ln.startswith(">")]
    assert len(quoted) >= 10 and [q for q in quoted if q and q not in skills] == []


def test_nothing_the_automation_reads_names_a_steps_page():
    names = [p.relative_to(ROOT).as_posix() for top in READERS for p in (ROOT / top).rglob("*")
             if p.is_file() and p.suffix in (".py", ".md", ".toml", ".json", ".sh", ".yaml", ".yml")
             and "docs/steps" in p.read_text(encoding="utf-8", errors="ignore")]
    assert names == []
