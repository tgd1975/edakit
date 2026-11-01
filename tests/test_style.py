"""The countable rules of the style guide (docs/style.md, "What the test counts") on the documentation as
docs/organisation.md lists it: the entry pages' sentences, sections without a subheading, chapters over 500 lines and
paragraphs over 120 words, bare cross-references, "the user" and "the reference project" in a page's own sentences,
dates outside the history, bold terms the glossary does not have, buzzwords outside docs/architecture.md and the
README's one "harness". It reads documentation only.

A page that does not meet a rule today stands in RED: its test is expected to fail and fails once the page meets the
rule, so that the page leaves RED (steps D.2 and D.5 of docs/concepts/new/documentation.md). A new page meets every
rule from the start."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GLOSSARY = ROOT / "docs" / "glossary.md"
ENTRY = ("README.md", "docs/glossary.md", "docs/quickstart.md", "docs/how-it-works.md")   # the entry layer
HISTORY = ("handbook/13-lessons-learned.md",)       # the history of edakit: its dates are its content
DATED = ("handbook/15-regulatory.md",               # the state of the law the regulatory review relies on
         "examples/coin-cell-led/docs/decisions.md",  # a decision log: each decision with its day
         "examples/blinker-555/docs/decisions.md")
QUOTED = ("11.4",)                                  # the working agreements: the hook reads them, their words stay
SECTION_LINES = 80
CHAPTER_LINES = 500                        # a chapter of the handbook
PARAGRAPH_WORDS = 120
ENTRY_MEAN, ENTRY_MAX = 20, 35
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE = re.compile(rf"\b20\d\d-\d\d-\d\d\b|\b(?:\d{{1,2}}(?:–\d{{1,2}})? )?(?:{MONTHS}) 20\d\d\b")
BUZZ = re.compile(r"\b(?:[Hh]arness(?:es)?|[Aa]gentic|AI-powered|copilots?)\b")   # "GitHub Copilot" is a name
BUZZ_PAGE = "docs/architecture.md"          # the one page that uses "harness", defined
STATUS = re.compile(r"^\s*(?:\*\*)?(?:State|Status)\b|^\s*!!!")


def documentation():
    """The pages of kind documentation (docs/organisation.md): the README, the handbook, docs/ outside concepts/ and
    catalog/, the Markdown of the two walkthroughs' examples."""
    pages = [ROOT / "README.md", *sorted((ROOT / "handbook").glob("*.md"))]
    pages += [p for p in sorted((ROOT / "docs").rglob("*.md"))
              if not p.relative_to(ROOT / "docs").as_posix().startswith(("concepts/", "catalog/"))]
    for name in ("coin-cell-led", "blinker-555"):
        example = ROOT / "examples" / name           # its build/ is gate output, ignored by git
        pages += sorted(p for p in example.rglob("*.md") if "build" not in p.relative_to(example).parts)
    return [p.relative_to(ROOT).as_posix() for p in pages]


def own(text):
    """The page's own text: without generated sections, quote blocks of edakit docs, code blocks, block quotes, inline
    code (one word), link targets, quoted phrases and the sections in QUOTED – line numbers kept."""
    def blank(m):
        return "\n" * m.group(0).count("\n")
    text = re.sub(r"<!-- edakit:generated.*?<!-- edakit:end -->", blank, text, flags=re.S)
    text = re.sub(r"<!--edakit.*?<!--/edakit-->", lambda m: "CODE" + blank(m), text, flags=re.S)
    text = re.sub(r"^ *(```|~~~).*?^ *\1", blank, text, flags=re.S | re.M)
    for n in QUOTED:
        text = re.sub(rf"^## {re.escape(n)} .*?(?=^## |\Z)", blank, text, flags=re.S | re.M)
    text = re.sub(r"^ {0,3}>.*$", "", text, flags=re.M)
    text = re.sub(r"`[^`\n]*`", "CODE", text)
    text = re.sub(r"\]\([^)\s]*\)", "]", text)
    return re.sub(r"\"[^\"\n]*\"|“[^”\n]*”", "QUOTE", text)


def numbers():
    out = set()
    for f in (ROOT / "handbook").glob("[0-9]*.md"):
        out |= set(re.findall(r"^#+ (\d+\.\d+)\s", f.read_text(encoding="utf-8"), re.M))
    return out


def terms():
    """The glossary's terms, lower case, with a plural."""
    heads = re.findall(r"^### (.+)$", GLOSSARY.read_text(encoding="utf-8"), re.M)
    out = {h.strip().lower() for h in heads}
    return out | {t + "s" for t in out}


def paragraphs(text):
    """The prose paragraphs of a page, a list item each on its own: no headings, tables, HTML or list markers."""
    prose = []
    for para in re.split(r"\n\s*\n", text):
        lines = [ln for ln in para.splitlines() if ln.strip() and not ln.lstrip().startswith(("#", "|", "<", "!!!"))]
        items = []
        for ln in lines:
            if re.match(r"\s*(?:[-*]|\d+\.)\s+", ln) or not items:
                items.append(re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", ln))
            else:
                items[-1] += " " + ln.strip()
        prose += items
    return prose


def sentences(text):
    """The prose sentences of a page, split at . ! ? before a capital."""
    out = []
    for p in paragraphs(text):
        out += [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"“(*`])", p) if re.search(r"\w", s)]
    return out


# --- the rules: each gives the page's violations ----------------------------------------------------------------------

def long_sentences(page, text):
    words = [len(re.findall(r"[\w'’-]+", s)) for s in sentences(own(text))]
    out = [f"a sentence of {n} words (at most {ENTRY_MAX})" for n in words if n > ENTRY_MAX]
    mean = sum(words) / len(words) if words else 0
    return out + ([f"{mean:.1f} words per sentence on average (at most {ENTRY_MEAN})"] if mean > ENTRY_MEAN else [])


def long_sections(page, text):
    lines = text.splitlines()
    in_code, starts = False, [0]
    for i, ln in enumerate(lines):                  # a "#" in a code block is no heading
        if re.match(r" *(```|~~~)", ln):
            in_code = not in_code
        elif not in_code and re.match(r"#{1,6} ", ln):
            starts.append(i)
    starts.append(len(lines))
    return [f"line {a + 1}: {b - a} lines without a subheading (at most {SECTION_LINES})"
            for a, b in zip(starts, starts[1:]) if b - a > SECTION_LINES]


def long_chapter(page, text):
    n = len(text.splitlines())
    return [f"{n} lines (at most {CHAPTER_LINES})"] if n > CHAPTER_LINES else []


def long_paragraphs(page, text):
    words = [len(re.findall(r"[\w'’-]+", p)) for p in paragraphs(own(text))]
    return [f"a paragraph of {n} words (at most {PARAGRAPH_WORDS})" for n in words if n > PARAGRAPH_WORDS]


def bare_references(page, text):
    """A section number standing alone: a parenthesis of numbers only at the start of a paragraph or after a
    punctuation mark – "the board file (10.2)" names its subject, also wrapped onto the next line; "… stops. (8.2)"
    does not –, or "see 8.2"."""
    have, out = numbers(), []
    t = own(text)
    for m in re.finditer(r"\((\d+\.\d+(?:\s*(?:,|and|to|–)\s*\d+\.\d+)*)\)", t):
        before = t[:m.start()].rstrip(" \t\n")
        if (not before or before[-1] in ".,;:!?–(" or t[len(before):m.start()].count("\n") > 1) \
                and any(n in have for n in re.findall(r"\d+\.\d+", m.group(1))):
            out.append(f"line {t.count(chr(10), 0, m.start()) + 1}: ({m.group(1)})")
    for m in re.finditer(r"\bsee (\d+\.\d+)\b", t):
        if m.group(1) in have:
            out.append(f"line {t.count(chr(10), 0, m.start()) + 1}: see {m.group(1)}")
    return out


def words_from_inside(page, text):
    t = own(text)
    return [f"line {t.count(chr(10), 0, m.start()) + 1}: {m.group(0)}"
            for m in re.finditer(r"\b[Tt]he (?:user|reference project)\b", t)]


def dates(page, text):
    if page in HISTORY or page in DATED:
        return []
    return [f"line {i}: {m.group(0)}" for i, ln in enumerate(own(text).splitlines(), 1)
            if not STATUS.match(ln) for m in DATE.finditer(ln)]


def bold_terms(page, text):
    """A term in bold – at most three words, not the title of a paragraph or an item – the glossary does not have."""
    have, out = terms(), []
    for m in re.finditer(r"(?<![*\w])\*\*([^*\n]{1,40}?)\*\*(?!\*)(.?)", own(text)):
        term = m.group(1).strip()
        if len(term.split()) > 3 or term.endswith((".", ":")) or m.group(2) in (".", ":"):
            continue
        if term.lower() not in have:
            out.append(term)
    return out


def buzzwords(page, text):
    """A buzzword in a page's own sentences: none outside docs/architecture.md, "harness" once in the README."""
    if page == BUZZ_PAGE:
        return []
    t = own(text)
    found = [f"line {t.count(chr(10), 0, m.start()) + 1}: {m.group(0)}" for m in BUZZ.finditer(t)]
    if page == "README.md" and len(found) == 1 and "arness" in found[0]:
        return []
    return found


RULES = {                                            # rule: (check, the pages it holds)
    "sentences": (long_sentences, lambda pages: [p for p in pages if p in ENTRY]),
    "sections": (long_sections, lambda pages: pages),
    "chapters": (long_chapter, lambda pages: [p for p in pages if re.match(r"handbook/\d\d-", p)]),
    "paragraphs": (long_paragraphs, lambda pages: pages),
    "references": (bare_references, lambda pages: pages),
    "words": (words_from_inside, lambda pages: pages),
    "dates": (dates, lambda pages: pages),
    "bold": (bold_terms, lambda pages: [p for p in pages if p in ENTRY]),
    "buzzwords": (buzzwords, lambda pages: pages),
}

# Today's pages that do not meet a rule yet – measured on main when D.1 was built. D.2 rewrites the README, D.5 the
# chapters; a page that meets its rule fails here until it leaves the list.
RED = {
    "sentences": set(),
    "sections": {f"handbook/{c}.md" for c in ("04-parts-database", "07-pcb",
                                              "08-release-gate", "10-reference", "11-working-with-claude")},
    "chapters": {f"handbook/{c}.md" for c in ("04-parts-database", "05-simulation", "07-pcb",
                                              "08-release-gate", "10-reference", "17-walkthrough")},
    "paragraphs": {"examples/coin-cell-led/docs/decisions.md",
                   "examples/blinker-555/docs/decisions.md"} | {f"handbook/{c}.md" for c in (
        "04-parts-database", "07-pcb",
        "08-release-gate")},
    "references": set(),
    "words": {f"handbook/{c}.md" for c in (
        "04-parts-database", "07-pcb", "08-release-gate",
        "13-lessons-learned")},
    "dates": {"examples/coin-cell-led/README.md", "examples/blinker-555/README.md"} | {f"handbook/{c}.md" for c in (
        "04-parts-database", "07-pcb", "08-release-gate", "10-reference", "17-walkthrough")},
    "bold": set(),
    "buzzwords": set(),
}


def cases():
    pages = documentation()
    for rule, (_, which) in RULES.items():
        for page in which(pages):
            mark = [pytest.mark.xfail(strict=True, reason="does not meet the rule yet")] if page in RED[rule] else []
            yield pytest.param(rule, page, id=f"{rule}:{page}", marks=mark)


@pytest.mark.parametrize("rule,page", list(cases()))
def test_the_page_meets_the_rule(rule, page):
    check, _ = RULES[rule]
    assert check(page, (ROOT / page).read_text(encoding="utf-8")) == []


def test_red_names_pages_that_exist():
    pages = set(documentation())
    assert {r: sorted(p for p in ps if p not in pages) for r, ps in RED.items() if ps - pages} == {}


def test_the_rules_find_what_they_count():
    assert long_sentences("x", " ".join(["word"] * 40) + ".") != []
    assert long_sentences("x", "A short one. Another short one.") == []
    assert long_sections("x", "# A\n" + "text\n" * 90) != [] and long_sections("x", "# A\n" + "x\n" * 10) == []
    assert long_chapter("x", "x\n" * 501) != [] and long_chapter("x", "x\n" * 500) == []
    assert long_paragraphs("x", " ".join(["word"] * 121)) != []
    assert long_paragraphs("x", "- " + " ".join(["word"] * 100) + "\n- " + " ".join(["word"] * 100)) == []
    assert long_sections("x", "# A\n```\n" + "# not a heading\n" * 90 + "```\n") != []
    assert bare_references("x", "The gate stops. (8.2) And see 7.4.") == ["line 1: (8.2)", "line 1: see 7.4"]
    assert bare_references("x", "the sign-off file (8.2), 0.2 mm, steps 2.1 to 2.3") == []
    assert words_from_inside("x", "Ask the user. `the user` and \"the user\" are quoted.") == ["line 1: the user"]
    assert dates("x", "Found on 2026-10-31.\n**State 2026-10-30:** built.\nIn October 2026.") == [
        "line 1: 2026-10-31", "line 3: October 2026"]
    assert bold_terms("x", "A **sign-off** and a **wobble** here. **Volume.** The title.") == ["wobble"]
    assert buzzwords("x", "An agentic harness. GitHub Copilot is a name.") == ["line 1: agentic", "line 1: harness"]
    assert buzzwords("README.md", "A harness.") == [] and buzzwords("docs/architecture.md", "A harness, harnesses.") == []


def test_the_glossary_links_land_on_a_section():
    text = GLOSSARY.read_text(encoding="utf-8")
    heads = re.findall(r"^### (.+)$", text, re.M)
    assert heads == sorted(heads, key=str.lower)
    missing = []
    for target, anchor in re.findall(r"\]\(\.\./handbook/([\w-]+\.md)(?:#([\w-]+))?\)", text):
        chapter = (ROOT / "handbook" / target).read_text(encoding="utf-8")
        slugs = {re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", h.lower()).strip())
                 for h in re.findall(r"^#+ (.+)$", chapter, re.M)}
        if anchor and anchor not in slugs:
            missing.append(f"{target}#{anchor}")
    assert missing == []
    entries = re.split(r"^### .+$", text, flags=re.M)[1:]
    assert [e for e in entries if "Handbook: [" not in e] == []
