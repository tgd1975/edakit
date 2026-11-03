"""The session as a chat (docs/session.md, docs/concepts/done/session-chat.md): its ```chat fence parses, its steps are
the steps pages, every code, slash command and edakit command in it exists, every number with a unit stands in the
example's files or the walkthrough, every line done outside the chat is a step's "What you do" or a click of
upstream/README.md – a click in EasyEDA with its footnote and the issue its row names –, and the page keeps the entry
register: a chat line counts as a sentence. The start page's excerpt and its tally follow the page, How it works' decision
round is a fence too, and the site turns each fence into the chat's HTML."""

import importlib.util
import re
from pathlib import Path

import pytest

import test_style as style

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "session.md"
EXAMPLE = ROOT / "examples" / "coin-cell-led"
WALKTHROUGH = ROOT / "handbook" / "17-walkthrough.md"
UPSTREAM = ROOT / "upstream" / "README.md"
WORDS = 1000
FENCED = ("README.md", "docs/session.md", "docs/how-it-works.md")
# Every line done outside the chat, by its start: the step whose "What you do" says it, with the words it says it in,
# and the requirements E-… of upstream/README.md whose click it is. A new do: line needs its row here.
DO = {
    "Once: add the plugin": ("01-install.md", "add the plugin", ()),
    "Start each reviewer in a new session": ("08-have-it-reviewed.md", "Start each reviewer in a session of its own", ()),
    "Install EasyEDA Pro and import its bridge extension": ("09-lay-out-the-board.md", "File → New → Project",
                                                           ("E-1", "E-4", "E-17")),
    "Start a new session and type /edakit:pcb-round": ("09-lay-out-the-board.md", "start a new session", ()),
    "Check D1's cathode in JLCPCB's preview": ("08-have-it-reviewed.md", "orientation in the manufacturer's preview", ()),
    "When the boards arrive": ("08-have-it-reviewed.md", "every delivered board, tested", ()),
}
GONE = ("E-2",)                 # a click that is gone, which a footnote names as gone


def pages():
    spec = importlib.util.spec_from_file_location("pages", ROOT / "docs" / "pages.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fences(path):
    return pages().CHAT_FENCE.findall((ROOT / path).read_text(encoding="utf-8"))


def chat():
    (fence,) = fences("docs/session.md")
    return pages().chat_parse(fence)


def lines(entries, kinds=("you", "claude", "ran", "do", "form", "note")):
    """The text of each entry, a form's title, questions, options and answers each a line."""
    out = []
    for kind, value in entries:
        if kind == "form" and "form" in kinds:
            out += [value["title"]] + [s for q in value["questions"] for s in (q["q"], *q["options"], q["answer"])]
        elif kind in kinds and kind != "form":
            out.append(value)
    return out


def rows():
    """{E-…: (the click today, the upstream cell)} of upstream/README.md."""
    out = {}
    for line in UPSTREAM.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 6 and re.fullmatch(r"E-\d+", cells[1]):
            out[cells[1]] = (cells[3], cells[5])
    return out


@pytest.mark.parametrize("path", FENCED)
def test_every_fence_parses(path):
    assert fences(path), path
    for fence in fences(path):
        assert pages().chat_parse(fence)


def test_the_parser_reads_every_kind_and_refuses_the_rest():
    mod = pages()
    entries = mod.chat_parse("--- 1 Install the tools\nyou: hi\n  there\nform: T\n  ? Q\n    on\n  - a\n  - b\n  > a\n"
                             "do: click\n  † a [note](https://x.org)\n  more\nimg: x.png | Alt\nran: edakit check\n")
    assert [k for k, _ in entries] == ["step", "you", "form", "do", "note", "img", "ran"]
    assert entries[1][1] == "hi there" and entries[4][1] == "a [note](https://x.org) more"
    assert entries[2][1]["questions"] == [{"q": "Q on", "options": ["a", "b"], "answer": "a"}]
    assert mod.chat_tally(entries) == {"typed": 1, "answers": 1, "forms": 1, "outside": 1}
    for bad in ("claud: hi\n", "  ? Q\n", "form: T\n  - a\n"):
        with pytest.raises(ValueError):
            mod.chat_parse(bad)
    out = mod.chat_html(entries)
    assert 'class="chat-tally"' in out and "\n\n" not in out and "<code>edakit check</code>" in out
    assert 'class="chat-note">† a <a href="https://x.org">note</a> more' in out and "click †</p>" in out
    assert 'class="chat-tally"' not in mod.chat_html(entries[1:])          # an excerpt has no tally


def test_the_steps_are_the_steps_pages_in_order():
    steps = [v for k, v in chat() if k == "step"]
    titles = [re.match(r"# (.+)", p.read_text(encoding="utf-8")).group(1)
              for p in sorted((ROOT / "docs" / "steps").glob("[0-9][0-9]-*.md"))]
    assert steps == titles


def test_every_code_skill_and_command_exists():
    text = " ".join(lines(chat()))
    codes = set(re.findall(r"codes\.\"([A-Z]+\.[\w/]+)\"", (ROOT / "edakit" / "catalog" / "codes.toml").read_text()))
    named = set(re.findall(r"\b[A-Z]{3,}\.[a-z_]+\b", text))
    assert named and named - codes == set()
    skills = set(re.findall(r"/edakit:([\w-]+)", text))
    assert skills and [s for s in skills if not (ROOT / "skills" / s / "SKILL.md").is_file()] == []
    commands = set(re.findall(r"\bedakit ([a-z]+)", text)) - {"writes", "now"}
    assert commands and commands - set(pages().cli_commands()) == set()


def test_every_number_stands_in_the_record():
    """A number with a unit, or with a decimal point, in what Claude says, asks or ran – as the example's files or the
    walkthrough have it."""
    record = WALKTHROUGH.read_text(encoding="utf-8")
    record += " ".join(p.read_text(encoding="utf-8", errors="ignore") for p in EXAMPLE.rglob("*")
                       if p.is_file() and "build" not in p.relative_to(EXAMPLE).parts
                       and p.suffix in (".md", ".json", ".toml", ".svg"))
    record = record.replace(" ", " ")
    text = " ".join(lines(chat(), ("claude", "ran", "form")))
    numbers = re.findall(r"\d+(?:\.\d+)? (?:mA|µA|V|mm|USD)\b|\b\d+\.\d+\b", text)
    assert len(numbers) >= 15
    assert sorted({n for n in numbers if n not in record}) == []


def test_every_line_outside_the_chat_is_a_step_or_a_click():
    steps = ROOT / "docs" / "steps"
    clicks = rows()
    entries = chat()
    for n, (kind, value) in enumerate(entries):
        if kind != "do":
            continue
        (start,) = [s for s in DO if value.startswith(s)] or [value]
        assert start in DO, f"a do: line without its row in DO: {value}"
        page, words, need = DO[start]
        doing = re.search(r"^## What you do\n(.*?)^## ", (steps / page).read_text(encoding="utf-8"), re.S | re.M)
        assert words.lower() in " ".join(doing.group(1).replace("*", "").split()).lower(), (page, words)
        notes = " ".join(v for k, v in entries[n + 1:n + 2] if k == "note")
        for e in need:
            click, upstream = clicks[e]
            assert not click.startswith("none"), f"{e}'s click is gone – its line goes too"
            issue = re.search(r"\((https://github\.com/easyeda/[^)]+/issues/\d+)\)", upstream).group(1)
            assert issue in notes, (e, issue)
        if need:
            assert "KiCad" in notes                    # a click in EasyEDA: KiCad does without it
            for e in GONE:
                click, upstream = clicks[e]
                issue = re.search(r"\((https://github\.com/[^)]+/issues/\d+)\)", upstream).group(1)
                assert click.startswith("none") and issue in notes, e


def test_the_page_keeps_the_entry_register():
    """Two paragraphs before the chat, at most 1,000 words, sentences of at most 20 words on average and none over 35 –
    a chat line counts as a sentence."""
    text = PAGE.read_text(encoding="utf-8")
    assert len(text.split()) <= WORDS
    intro = text.split("```chat")[0]
    assert len([p for p in re.split(r"\n\s*\n", intro) if p.strip() and not p.startswith("#")]) == 2
    said = style.sentences(style.own(intro))
    for line in lines(chat(), ("you", "claude", "do", "form", "note")):
        line = re.sub(r"\]\([^)\s]*\)", "]", line)
        said += [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"“(])", line) if re.search(r"\w", s)]
    counts = [len(re.findall(r"[\w'’-]+", s)) for s in said]
    assert max(counts) <= style.ENTRY_MAX and sum(counts) / len(counts) <= style.ENTRY_MEAN


def test_the_start_page_quotes_the_session_and_its_tally():
    mod = pages()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    (fence,) = fences("README.md")
    excerpt = mod.chat_parse(fence)
    assert not mod.chat_whole(excerpt)
    whole = lines(chat())
    assert [s for s in lines([e for e in excerpt if e[0] != "form"]) if s not in whole] == []
    forms = [q for k, v in excerpt if k == "form" for q in v["questions"]]
    assert forms and [q for q in forms if q not in [q for k, v in chat() if k == "form" for q in v["questions"]]] == []
    t = mod.chat_tally(chat())
    assert (f"{t['typed']} messages typed, {t['answers']} answers in {t['forms']} forms, {t['outside']} things done "
            f"outside the chat") in " ".join(readme.split())
    assert f"({mod.SITE}start/session/)" in readme


def test_the_site_shows_the_chat(tmp_path):
    docs = pages().assemble(tmp_path / "pages") / "docs"
    page = (docs / "start" / "session.md").read_text(encoding="utf-8")
    assert "```chat" not in page and page.count('class="chat-step"') == 10 and 'class="chat-tally"' in page
    assert 'href="../../circuit/05-decide-on-what-was-found/"' in page
    assert 'src="../../files/examples/coin-cell-led/docs/pcb_plan_main.png"' in page
    assert (docs / "files" / "examples" / "coin-cell-led" / "docs" / "silk_main_top.png").is_file()
    for site in ("index.md", "start/how-it-works.md"):
        text = (docs / site).read_text(encoding="utf-8")
        assert "```chat" not in text and 'class="chat-form"' in text and 'class="chat-tally"' not in text
    css = (ROOT / "docs" / "brand" / "edakit.css").read_text(encoding="utf-8")
    used = set(re.findall(r'class="(chat[\w-]*)', page)) | {"chat-rec", "chat-q-row"}
    assert [c for c in used if f".{c}" not in css] == []
    assert '[data-md-color-scheme="slate"]' in css and "--chat-copper" in css
