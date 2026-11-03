"""edakit's documentation as one site for GitHub Pages, assembled into build/pages and built by MkDocs. The navigation
is data – NAV, a table of tab, file and short title, by reader (docs/concepts/done/documentation-newcomer.md, steps N.1
and N.2): Start, A circuit, A board, Extend, Develop, Handbook, Reference and Inside edakit as tabs across the top, the
sidebar showing the current tab alone, at most eight entries but for the handbook. The sources – the concepts, skills,
agents, evals and the rules of a session – are on the site behind the tab "Inside edakit": its sidebar holds an
overview and the index of each kind, the pages themselves are not in the navigation, every page of them marked as a
source.

    python3 docs/pages.py                       assembles build/pages (the Markdown, the catalog, mkdocs.yml)
    uvx --with mkdocs-material==9.6.23 --from mkdocs==1.6.1 mkdocs build --strict -f build/pages/mkdocs.yml
                                                writes the site into build/site

The workflow .github/workflows/pages.yml runs both on every push and publishes the site from main. The sources stay
where they are; a link to a file the site does not carry goes to the file on GitHub, an image goes onto the site
(files/<its path>) – GitHub's page of a file is no image.
"""

from __future__ import annotations

import html
import itertools
import json
import posixpath
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/tgd1975/edakit"
SITE = "https://tgd1975.github.io/edakit/"
LINK = re.compile(r"(!?\[[^\]]*\]\()([^)\s]+)(\))")
ATTR = re.compile(r'(<(?:a|img)\s[^>]*?\b(?:href|src)=")([^"]+)(")')     # a link in an HTML tag


def front_matter(text):
    """({key: value}, body) – the YAML front matter of a skill or an agent, read flat (one key per line)."""
    if not text.startswith("---\n"):
        return {}, text
    head, _, body = text[4:].partition("\n---\n")
    meta = {}
    for line in head.splitlines():
        key, sep, value = line.partition(":")
        if sep and not line.startswith((" ", "\t")):
            meta[key.strip()] = value.strip()
    return meta, body


def title_of(text, fallback):
    m = re.search(r"^# (.+)$", text, re.M)
    return m.group(1).strip() if m else fallback


# The navigation: (tab, [(repo path, title of at most five words)]); a tab's first page is its index page where it is
# one (README.md, handbook/README.md). "A circuit" and "A board" are the steps, the person's manual, in the order of the
# walkthrough. The handbook's chapters stand by their numbers, 1 to 18 – its index says which to read when; Reference
# points to 9 and 10 from its overview.
NAV = [
    ("Start", [
        ("README.md", "Start"),
        ("docs/session.md", "A session"),
        ("docs/quickstart.md", "Quickstart"),
        ("docs/how-it-works.md", "How it works"),
        ("docs/projects/README.md", "Projects"),
        ("docs/glossary.md", "Glossary"),
    ]),
    ("A circuit", [
        ("docs/steps/README.md", "The steps"),
        ("docs/steps/01-install.md", "1 Install the tools"),
        ("docs/steps/02-start-a-project.md", "2 Start a project"),
        ("docs/steps/03-say-what-it-must-do.md", "3 What it must do"),
        ("docs/steps/04-design-the-circuit.md", "4 Design the circuit"),
        ("docs/steps/05-decide-on-what-was-found.md", "5 Decide on the findings"),
        ("docs/steps/06-settle-parts-and-cost.md", "6 Parts and cost"),
        ("docs/steps/07-draw-and-hand-over.md", "7 Draw and hand over"),
    ]),
    ("A board", [
        ("docs/steps/08-have-it-reviewed.md", "8 Have it reviewed"),
        ("docs/steps/09-lay-out-the-board.md", "9 Lay out the board"),
        ("docs/steps/10-order-the-board.md", "10 Order the board"),
    ]),
    ("Extend", [
        ("docs/adding-a-rule.md", "Adding a rule"),
        ("skills/propose-rule/SKILL.md", "Propose a rule"),
        ("skills/propose-feature/SKILL.md", "Propose a feature"),
    ]),
    ("Develop", [
        ("docs/working-on-edakit.md", "Working on edakit"),
        ("docs/architecture.md", "edakit as a meta-harness"),
        ("docs/organisation.md", "Organisation"),
        ("docs/style.md", "Style guide"),
        ("docs/brand/README.md", "Brand"),
    ]),
    ("Handbook", [
        ("handbook/README.md", "The handbook"),
        ("handbook/01-approach.md", "1 The approach"),
        ("handbook/02-setup.md", "2 Setup"),
        ("handbook/03-hardware-graph.md", "3 Hardware graph"),
        ("handbook/04-parts-database.md", "4 Parts"),
        ("handbook/05-simulation.md", "5 Simulation"),
        ("handbook/06-schematic.md", "6 Schematic"),
        ("handbook/07-pcb.md", "7 PCB"),
        ("handbook/08-release-gate.md", "8 Release gate"),
        ("handbook/09-easyeda-api.md", "9 EasyEDA API"),
        ("handbook/10-reference.md", "10 Files, keys, commands"),
        ("handbook/11-working-with-claude.md", "11 Working with Claude"),
        ("handbook/12-troubleshooting.md", "12 Troubleshooting"),
        ("handbook/13-lessons-learned.md", "13 Lessons learned"),
        ("handbook/14-design.md", "14 Designing a circuit"),
        ("handbook/15-regulatory.md", "15 Regulatory review"),
        ("handbook/16-kicad.md", "16 KiCad"),
        ("handbook/17-walkthrough.md", "17 Walkthrough on EasyEDA"),
        ("handbook/18-walkthrough-kicad.md", "18 Walkthrough on KiCad"),
        ("handbook/19-verification.md", "19 How edakit is tested"),
    ]),
    ("Reference", [              # what is looked up: an overview pointing into the handbook, the catalog, the changelog
        ("docs/reference/README.md", "Overview"),
        ("docs/catalog/index.html", "Rule catalog"),
        ("CHANGELOG.md", "Changelog"),
    ]),
    ("Inside edakit", [          # the sources: an overview, then the index of each kind
        ("docs/inside-edakit.md", "Overview"),
        ("docs/concepts/README.md", "Concepts"),
        ("skills/README.md", "Skills"),
        ("agents/README.md", "Agents"),
        ("evals/README.md", "Evals"),
        ("CLAUDE.md", "Rules of a session"),
    ]),
]
SIDEBAR = 8                      # entries a tab shows at most, the handbook's excepted
GENERATED = {"docs/concepts/README.md", "skills/README.md", "agents/README.md",   # indexes written by this script
             "docs/reference/README.md"}
INSIDE = ("docs/concepts/README.md", "skills/README.md", "agents/README.md", "evals/README.md", "CLAUDE.md")
SOURCE = ('!!! note "A source"\n    This page is a source of edakit – a concept, a prompt or the rules of a session –, '
          'shown as it is in the repository. Read it as such; the guides say what edakit does.\n')
ISSUES = f"{REPO}/issues/new/choose"
# A ```mermaid block is drawn by Material, as GitHub draws it: a custom fence whose format is a Python function – a YAML
# tag, which mkdocs.yml carries unquoted (assemble).
FENCE_FORMAT = "!!python/name:pymdownx.superfences.fence_code_format"
# The old address of a page that moved on the site: a page there that sends the reader on, so a link from outside holds.
REDIRECTS = {"inside-edakit/index.html": "../inside/"}


# Where a page lands on the site follows its tab (the owner's decision of 2026-11-02): /start/…, /circuit/…, /board/…,
# /extend/…, /develop/…, /handbook/…, /reference/…, /inside/…; the files in the repository stay where the code, the
# skills and the projects name them. The catalog's own pages stay at /catalog/: generated HTML whose relative links
# (../brand/…) are those of docs/catalog/ in the repository.
TAB_DIR = {"Start": "start", "A circuit": "circuit", "A board": "board", "Extend": "extend", "Develop": "develop",
           "Handbook": "handbook", "Reference": "reference", "Inside edakit": "inside"}
INDEXES = {"README.md": "index.md", "handbook/README.md": "handbook/index.md", "docs/steps/README.md": "circuit/index.md",
           "docs/projects/README.md": "start/projects/index.md", "docs/reference/README.md": "reference/index.md",
           "docs/inside-edakit.md": "inside/index.md",   # a tab's index: Material shows the tab's other entries
           "docs/concepts/README.md": "inside/concepts/index.md", "skills/README.md": "inside/skills/index.md",
           "agents/README.md": "inside/agents/index.md", "evals/README.md": "inside/evals.md",
           "CLAUDE.md": "inside/claude.md", "docs/brand/README.md": "develop/brand.md", "CHANGELOG.md": "reference/changelog.md"}


def page_name(src):
    """A page's last path part on the site: a skill by its folder, every other file by its own name."""
    p = Path(src)
    return f"{p.parent.name}.md" if p.name == "SKILL.md" else p.name


def site_path(src):
    """Where a repository file lands on the site: under its tab, or – a source the navigation does not list – under
    Inside edakit, a project page under Start."""
    if src in INDEXES:
        return INDEXES[src]
    tab = next((tab for tab, entries in NAV for s, _ in entries if s == src), None)
    if tab:
        return f"{TAB_DIR[tab]}/{page_name(src)}"
    if src.startswith("docs/concepts/"):
        return "inside/" + src[len("docs/"):]
    if src.startswith(("skills/", "agents/")):
        return f"inside/{src.split('/')[0]}/{page_name(src)}"
    if src.startswith("docs/projects/"):
        return "start/projects/" + page_name(src)
    return src[len("docs/"):] if src.startswith("docs/") else src


def old_site_path(src):
    """Where a page stood on the site until the addresses followed the tabs (edakit 1.0.7) – for the redirects."""
    special = {"README.md": "index.md", "handbook/README.md": "handbook/index.md", "evals/README.md": "evals.md",
               "CHANGELOG.md": "changelog.md", "CLAUDE.md": "inside/claude.md", "docs/inside-edakit.md": "inside/index.md",
               "docs/brand/README.md": "brand/index.md", "docs/concepts/README.md": "concepts/index.md",
               "docs/projects/README.md": "projects/index.md", "docs/steps/README.md": "steps/index.md",
               "skills/README.md": "skills/index.md", "agents/README.md": "agents/index.md"}
    if src in special:
        return special[src]
    if src.startswith("skills/") and src.endswith("/SKILL.md"):
        return f"skills/{src.split('/')[1]}.md"
    return src[len("docs/"):] if src.startswith("docs/") else src


def url_of(md):
    """The directory URL of a page's site path: "start/quickstart.md" → "start/quickstart/", "index.md" → ""."""
    stem = md[:-len(".md")]
    return "" if stem == "index" else (stem[:-len("index")] if stem.endswith("/index") else stem + "/")


def redirects(pages):
    """{file of the old address: relative URL of the page now} – for every page whose address changed, and the older
    ones of REDIRECTS."""
    out = dict(REDIRECTS)
    now = {site for _, site, _ in pages}
    for src, site, _ in pages:
        old = old_site_path(src)
        if old != site and old not in now:
            old_url, new_url = url_of(old), url_of(site)
            rel = posixpath.relpath(new_url or ".", old_url.rstrip("/") or ".")
            out[old_url + "index.html"] = (rel.rstrip("/") + "/") if rel != "." else "./"
    return out


def is_source(src):
    """A page of "Inside edakit": a concept, a skill, an agent, an eval, CLAUDE.md – shown with the source line."""
    return src.startswith(("docs/concepts/", "skills/", "agents/", "evals/")) or src == "CLAUDE.md"


def concepts():
    """The concepts in their folders, prototype READMEs left out (their links still work)."""
    root = ROOT / "docs" / "concepts"
    return [p for p in sorted(root.rglob("*.md")) if "prototypes" not in p.parts and p.name != "README.md"]


def sources():
    """[(repo path, site path, section)] of every Markdown page of the site: the navigation's pages in its order, then
    the pages reached from "Inside edakit" and its indexes – the concepts, skills, agents, evals, the rules of a
    session, the prototypes' READMEs – and the project pages."""
    out = []
    for group, pages in NAV:
        out += [(src, site_path(src), group) for src, _ in pages if src.endswith(".md")]
    more = list(INSIDE)
    more += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "docs" / "concepts").rglob("*.md"))]
    more += [f"skills/{p.parent.name}/SKILL.md" for p in sorted((ROOT / "skills").glob("*/SKILL.md"))]
    more += [f"agents/{p.name}" for p in sorted((ROOT / "agents").glob("*.md")) if p.name != "README.md"]
    more += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "docs" / "projects").glob("*.md"))
             if p.name != "README.md"] if (ROOT / "docs" / "projects").is_dir() else []
    have = {s for s, _, _ in out}
    out += [(src, site_path(src), "") for src in more if src not in have]
    return out


def short_title(text, fallback):
    """A concept's title up to its colon: "Claude independence: edakit with …" gives "Claude independence"."""
    return title_of(text, fallback).split(":")[0].strip()


def status_of(text):
    """(date, state) from a concept's status line: "Status 2026-10-31: decided – …" gives ("2026-10-31", "decided")."""
    m = re.search(r"^(?:\*\*)?(?:Status|State)\b[^\n]*", text, re.M)
    if not m:
        return "", ""
    line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", re.sub(r"\*\*", "", m.group(0)))
    date = re.search(r"20\d\d-\d\d-\d\d", line)
    state = re.split(r"[:.]", line, maxsplit=1)[1] if ":" in line else ""
    state = re.split(r"\s[–(]|[,;.]", state.strip(), maxsplit=1)[0].strip()
    return (date.group(0) if date else ""), state[:40]


def first_sentence(text, limit=110):
    """The first sentence of a description, cut at a dash or a full stop, at most limit characters."""
    s = re.split(r"(?<=[a-z0-9)])\.\s|\s–\s", " ".join(text.split()), maxsplit=1)[0].rstrip(".")
    return s if len(s) <= limit else s[:limit].rsplit(" ", 1)[0] + " …"


def index_pages():
    """{repo path: Markdown} of the indexes this script writes: the concepts by state as tables – title, date, state –,
    the folders of a concept (its reviews) as one row; the skills and the agents as tables of name and what for."""
    root = ROOT / "docs" / "concepts"
    lines = ["# Concepts", "", "A concept is how a part of edakit should work, written before it is built and kept as the "
             "record of what was decided. It starts in `new/`, moves to `done/` once it is decided and built, and to "
             "`discarded/` when the owner rejects it ([organisation](../organisation.md)).", ""]
    for state, title in (("new", "Open"), ("done", "Decided and built"), ("discarded", "Discarded")):
        rows, folders = [], {}
        mine = [p for p in concepts() if p.relative_to(root).parts[0] == state]
        shorts = [short_title(p.read_text(encoding="utf-8"), p.stem) for p in mine]
        for p in concepts():
            rel = p.relative_to(root)
            if rel.parts[0] != state:
                continue
            if len(rel.parts) > 2:                      # a concept's folder, e.g. documentation-review/
                folders.setdefault(rel.parts[1], []).append(rel)
                continue
            text = p.read_text(encoding="utf-8")
            date, what = status_of(text)
            name = short_title(text, p.stem)
            name = name if shorts.count(name) == 1 else title_of(text, p.stem)
            rows.append(f"| [{name}]({rel.as_posix()}) | {date.replace('-', chr(0x2011))} | {what} |")
        rows += [f"| {name}/ – " + " ".join(f"[{f.stem.split('-')[0]}]({f.as_posix()})" for f in files)
                 + f" | | {len(files)} files |" for name, files in folders.items()]
        if rows:
            lines += [f"## {title}", "", "| Concept | Date | State |", "| --- | --- | --- |", *rows, ""]
    def table(head, entries):
        return [head, "", "| | What for |", "| --- | --- |", *entries, ""]
    skills = ["# Skills", "", "The plugin's skills: prompts that run a workflow in a session, each called as "
              "`/edakit:<name>`. What each does for you is in [handbook 11.1](../handbook/11-working-with-claude.md).", ""]
    skills += table("", [f"| [`/edakit:{p.parent.name}`]({p.parent.name}/SKILL.md) | "
                         f"{first_sentence(front_matter(p.read_text(encoding='utf-8'))[0].get('description', ''))} |"
                         for p in sorted((ROOT / "skills").glob("*/SKILL.md"))])[1:]
    agents = ["# Agents", "", "The plugin's agents: prompts that run Claude in a context of its own for one role, such as "
              "a review. What each does for you is in [handbook 11.1](../handbook/11-working-with-claude.md).", ""]
    agents += table("", [f"| [`{p.stem}`]({p.name}) | "
                         f"{first_sentence(front_matter(p.read_text(encoding='utf-8'))[0].get('description', ''))} |"
                         for p in sorted((ROOT / "agents").glob("*.md")) if p.name != "README.md"])[1:]
    reference = ["# Reference", "", "What you look up rather than read through.", "",
                 "- [Files, keys and commands](../../handbook/10-reference.md) – handbook 10: every key of edakit.toml, "
                 "of a board file and of the schematic file, and every command.",
                 "- [EasyEDA API](../../handbook/09-easyeda-api.md) – handbook 9: how the EasyEDA Pro API and its MCP "
                 "server really behave.",
                 "- [Rule catalog](../catalog/index.html) – every check edakit runs: its rule, why it exists, what to "
                 "do and its sources.",
                 "- [Changelog](../../CHANGELOG.md) – what each version changed, and what a project does when it "
                 "updates.",
                 "- [Glossary](../glossary.md) – the words edakit uses.", ""]
    return {"docs/concepts/README.md": "\n".join(lines) + "\n", "skills/README.md": "\n".join(skills) + "\n",
            "agents/README.md": "\n".join(agents) + "\n", "docs/reference/README.md": "\n".join(reference)}


def version():
    m = re.search(r'__version__ = "([^"]+)"', (ROOT / "edakit" / "__init__.py").read_text(encoding="utf-8"))
    return m.group(1) if m else "?"


def rewrite(text, src, site, mapped, media=None):
    """The page's relative links: to a page of the site its path there, an image to its copy under files/ (its path
    goes into the set media, for assemble to copy), to anything else the file on GitHub. A Markdown link is written
    from the page's file – MkDocs turns it into one from the page's address –, a link in an HTML tag (href, src, as the
    drawings' thumbnails of handbook 19 and a ```chat fence's HTML have) from the page's address itself: MkDocs leaves
    HTML as it is."""
    here = (ROOT / src).parent
    address = url_of(site) + "index.html"       # a file in the page's directory URL, for _relpath

    def where(target, image):
        """(kind, target, anchor) of a relative link – kind page (a page's site path), file (a file on the site) or
        url (on GitHub) –, None for a link that stays as it is."""
        if re.match(r"[a-z]+:|#|/", target) or "${" in target:
            return None
        path, _, anchor = target.partition("#")
        resolved = (here / path).resolve()
        try:
            rel = resolved.relative_to(ROOT).as_posix()
        except ValueError:
            return None
        if rel in mapped or rel + "/README.md" in mapped:       # a page, or a folder whose README is one
            return "page", mapped.get(rel) or mapped[rel + "/README.md"], anchor
        if rel.startswith("docs/brand/") and rel != "docs/brand/README.md":
            # the logo files and the theme's stylesheet are on the site
            return "file", rel[len("docs/"):], ""
        if rel == "docs/catalog" or (rel.startswith("docs/catalog/") and not rel.endswith(".py")):
            # the catalog's pages and drawings are on the site; their generator is not
            return "file", "catalog/" + rel[len("docs/catalog/"):] if rel != "docs/catalog" else "catalog/", anchor
        if image and media is not None and resolved.is_file():
            media.add(rel)
            return "file", "files/" + rel, ""
        kind = "tree" if resolved.is_dir() else "blob"
        return "url", f"{REPO}/{kind}/main/{rel}", anchor

    def markdown(m):
        w = where(m.group(2), m.group(1).startswith("!"))
        if w is None:
            return m.group(0)
        kind, target, anchor = w
        new = target if kind == "url" else _relpath(target, site)
        return f"{m.group(1)}{new}{'#' + anchor if anchor else ''}{m.group(3)}"

    def html(m):
        w = where(m.group(2), m.group(1).endswith('src="'))
        if w is None:
            return m.group(0)
        kind, target, anchor = w
        new = target if kind == "url" else _relpath(url_of(target) if kind == "page" else target, address)
        return f"{m.group(1)}{new}{'#' + anchor if anchor else ''}{m.group(3)}"

    # a chat fence becomes its HTML, its links written from the page's file like those of any HTML tag
    steps = {int(p.name[:2]): posixpath.relpath(p.as_posix(), here.as_posix())
             for p in (ROOT / "docs" / "steps").glob("[0-9][0-9]-*.md")}
    text = CHAT_FENCE.sub(lambda m: chat_html(chat_parse(m.group(1)), steps=steps), text)
    # links inside code blocks stay as they are
    parts = re.split(r"(```.*?```)", text, flags=re.S)
    return "".join(p if p.startswith("```") else ATTR.sub(html, LINK.sub(markdown, p)) for p in parts)


# A session as a chat (docs/concepts/done/session-chat.md): a ```chat fence, a plain transcript on GitHub, turned into
# HTML on assembly – one class a kind of entry, the styles in docs/brand/edakit.css, the format in docs/style.md. One
# entry a line, an indented line continuing the one above:
#
#     --- <n> <step>         a step of the steps pages, as a divider linked to its page
#     you: <text>            what the person types
#     claude: <text>         what Claude says
#     ran: <text>            what Claude ran – a quiet line, no bubble
#     do: <text>             what the person does outside the chat: an install, a click, a new session, paying
#       † <text>             under a do: its footnote, [text](url) a link
#     img: <path> | <alt>    a picture Claude shows
#     form: <title>          Claude Code's question form, then per question:
#       ? <question>
#       - <option>           the recommended one first
#       > <answer>           what the person picked or typed
#
# Under a whole session – one that starts with step 1 – the tally of the person's part, counted from the entries.
CHAT_FENCE = re.compile(r"^```chat\n(.*?)^```[ \t]*$", re.M | re.S)
CHAT_KINDS = ("you", "claude", "ran", "do", "img", "form")


def chat_parse(text):
    """[(kind, value)] of a chat fence – value a string, a form {"title", "questions": [{"q", "options", "answer"}]};
    a footnote is ("note", text) right after its do."""
    entries = []
    for line in text.splitlines():
        if not line.strip():
            continue
        body = line.strip()
        if line.startswith((" ", "\t")):
            if not entries:
                raise ValueError(f"chat: an indented line before any entry: {line!r}")
            kind, value = entries[-1]
            if kind == "form":
                mark, rest = body[:2], body[2:]
                if mark == "? ":
                    value["questions"].append({"q": rest, "options": [], "answer": ""})
                elif not value["questions"]:
                    raise ValueError(f"chat: a form's line before its first question: {line!r}")
                elif mark == "- ":
                    value["questions"][-1]["options"].append(rest)
                elif mark == "> ":
                    value["questions"][-1]["answer"] = rest
                else:                                # the question, its last option or its answer continued
                    q = value["questions"][-1]
                    if q["answer"]:
                        q["answer"] += " " + body
                    elif q["options"]:
                        q["options"][-1] += " " + body
                    else:
                        q["q"] += " " + body
            elif body.startswith("† ") and kind in ("do", "note"):
                entries.append(("note", body[2:]))
            else:
                entries[-1] = (kind, f"{value} {body}")
            continue
        if line.startswith("--- "):
            entries.append(("step", body[4:].strip()))
            continue
        kind, sep, rest = line.partition(": ")
        if not sep or kind not in CHAT_KINDS:
            raise ValueError(f"chat: not an entry: {line!r}")
        entries.append((kind, {"title": rest.strip(), "questions": []} if kind == "form" else rest.strip()))
    return entries


def chat_tally(entries):
    """The person's part: messages typed, answers given in forms, forms, things done outside the chat."""
    forms = [v for k, v in entries if k == "form"]
    return {"typed": sum(k == "you" for k, _ in entries), "answers": sum(len(f["questions"]) for f in forms),
            "forms": len(forms), "outside": sum(k == "do" for k, _ in entries)}


def chat_whole(entries):
    """A whole session, the one that gets the tally: it starts with step 1."""
    return bool(entries) and entries[0][0] == "step" and entries[0][1].split()[0] == "1"


def cli_commands():
    """edakit's commands, read from edakit/cli.py: a chat sets them in mono, and no other words after "edakit"."""
    text = (ROOT / "edakit" / "cli.py").read_text(encoding="utf-8")
    return sorted(set(re.findall(r'add_parser\(\s*"([\w-]+)"', text)))


def chat_text(text, commands):
    """A chat line as HTML: [text](url) a link, the slash commands, edakit's commands and the file names in mono."""
    def mono(s):
        s = re.sub(r"(\d) (?=(?:mA|µA|mm|V|USD)\b)", "\\1\u00a0", html.escape(s, quote=False))   # 2.5 V on one line
        return re.sub(rf"(/edakit:[\w-]+|\bedakit (?:{'|'.join(commands)})\b[\w -]*?(?= ·|[:.,;]|$)"
                      r"|\b[\w./-]+\.(?:toml|json|md)\b)", r"<code>\1</code>", s)
    out, last = [], 0
    for m in re.finditer(r"\[([^\]]+)\]\(([^)\s]+)\)", text):
        out += [mono(text[last:m.start()]), f'<a href="{html.escape(m.group(2))}">{mono(m.group(1))}</a>']
        last = m.end()
    return "".join(out) + mono(text[last:])


def chat_html(entries, steps=None):
    """The chat as one block of HTML for Markdown – no blank line inside, a class for each kind of entry, its links as
    the page's source has them (rewrite turns them into the site's); steps {number: the link to its steps page}."""
    commands, steps = cli_commands(), steps or {}

    def t(s):
        return chat_text(s, commands)
    parts = ['<div class="chat">']
    for n, (kind, value) in enumerate(entries):
        if kind == "step":
            number, name = value.split()[0], html.escape(value)
            link = steps.get(int(number)) if number.isdigit() else None
            parts.append(f'<div class="chat-step"><a href="{html.escape(link)}">{name}</a></div>' if link
                         else f'<div class="chat-step"><span>{name}</span></div>')
        elif kind in ("you", "claude"):
            parts.append(f'<div class="chat-msg chat-{kind}"><span class="chat-who">'
                         f'{"You" if kind == "you" else "Claude"}</span><p>{t(value)}</p></div>')
        elif kind == "ran":
            parts.append(f'<div class="chat-ran"><span>ran</span> {t(value)}</div>')
        elif kind == "do":
            notes = [v for _, v in itertools.takewhile(lambda e: e[0] == "note", entries[n + 1:])]
            parts.append('<div class="chat-do"><span class="chat-do-label">You, outside the chat</span>'
                         f'<p>{t(value)}{" †" if notes else ""}</p>'
                         + "".join(f'<p class="chat-note">† {t(v)}</p>' for v in notes) + "</div>")
        elif kind == "img":
            path, _, alt = (s.strip() for s in value.partition("|"))
            parts.append(f'<figure class="chat-img"><img src="{html.escape(path)}" '
                         f'alt="{html.escape(alt)}"><figcaption>{html.escape(alt)}</figcaption></figure>')
        elif kind == "form":
            rows = []
            for q in value["questions"]:
                opts = "".join(('<li class="chat-rec">' if i == 0 else "<li>") + f"{t(o)}</li>"
                               for i, o in enumerate(q["options"]))
                rows.append(f'<div class="chat-q{"" if opts else " chat-q-row"}"><p>{t(q["q"])}</p>'
                            + (f"<ol>{opts}</ol>" if opts else "") + f'<p class="chat-a">{t(q["answer"])}</p></div>')
            count = len(value["questions"])
            parts.append(f'<div class="chat-form"><div class="chat-form-title">{html.escape(value["title"])}'
                         f'<span>{count} question{"" if count == 1 else "s"}</span></div>{"".join(rows)}</div>')
    if chat_whole(entries):
        c = chat_tally(entries)
        parts.append(f'<div class="chat-tally"><b>Your part:</b> {c["typed"]} messages typed, {c["answers"]} answers '
                     f'in {c["forms"]} forms, {c["outside"]} things done outside the chat.</div>')
    return "\n".join(parts + ["</div>"])


def _relpath(target, start):
    """target relative to the directory of the site page start (both site paths)."""
    t, s = target.split("/"), start.split("/")[:-1]
    i = 0
    while i < min(len(t) - 1, len(s)) and t[i] == s[i]:
        i += 1
    return "/".join([".."] * (len(s) - i) + t[i:]) or "./"


def config(nav):
    return {
        "site_name": "edakit",
        "site_description": "Circuit design as code – the documentation of edakit",
        "copyright": (f"Built from edakit {version()} · Something unclear or wrong? "
                      f'<a href="{ISSUES}">Open an issue</a>, with the form for a bug or a question.'),
        "site_url": SITE,
        "repo_url": REPO,
        "repo_name": "tgd1975/edakit",
        "edit_uri": "",
        "docs_dir": "docs",
        "site_dir": "../site",
        "use_directory_urls": True,
        "theme": {
            "name": "material",
            "features": ["navigation.tabs", "navigation.indexes", "navigation.top", "search.highlight",
                         "content.code.copy", "toc.follow"],
            "logo": "brand/edakit-mark-mono-white.svg",
            "favicon": "brand/edakit-favicon.svg",
            "font": {"text": "IBM Plex Sans", "code": "IBM Plex Mono"},
            "palette": [
                {"media": "(prefers-color-scheme: light)", "scheme": "default", "primary": "custom", "accent": "custom",
                 "toggle": {"icon": "material/brightness-7", "name": "Dark mode"}},
                {"media": "(prefers-color-scheme: dark)", "scheme": "slate", "primary": "custom", "accent": "custom",
                 "toggle": {"icon": "material/brightness-4", "name": "Light mode"}},
            ],
        },
        "extra_css": ["brand/edakit.css"],
        "markdown_extensions": ["tables", "admonition", "attr_list", "md_in_html", "def_list",
                                {"toc": {"permalink": True}},
                                {"pymdownx.superfences": {"custom_fences": [
                                    {"name": "mermaid", "class": "mermaid", "format": FENCE_FORMAT}]}},   # format last
                                {"pymdownx.highlight": {"anchor_linenums": False}}, "pymdownx.inlinehilite",
                                "pymdownx.details"],
        "validation": {"nav": {"omitted_files": "info", "not_found": "warn"},
                       "links": {"not_found": "warn", "absolute_links": "info", "unrecognized_links": "info",
                                 "anchors": "warn"}},
        "nav": nav,
    }


def assemble(out=ROOT / "build" / "pages"):
    """Write the site's sources into out: docs/ with every page, the indexes and the catalog, mkdocs.yml beside it."""
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    docs = out / "docs"
    pages = sources()
    mapped = {src: site for src, site, _ in pages}
    generated = index_pages()
    media = set()
    for src, site, _ in pages:
        text = generated[src] if src in generated else (ROOT / src).read_text(encoding="utf-8")
        meta, body = front_matter(text)
        name = Path(src).parent.name if src.endswith("SKILL.md") else Path(src).stem
        if meta:
            lead = f"\n_{meta['description']}_\n" if meta.get("description") else ""
            body = (re.sub(r"^# .+$", lambda m: m.group(0) + "\n" + lead, body, count=1, flags=re.M)
                    if re.search(r"^# ", body, re.M) else f"# {meta.get('name', name)}\n{lead}\n{body}")
            text = body
        if is_source(src) and src not in generated:
            text = (re.sub(r"^# .+$", lambda m: m.group(0) + "\n\n" + SOURCE, text, count=1, flags=re.M)
                    if re.search(r"^# ", text, re.M) else SOURCE + "\n" + text)
        f = docs / site
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(rewrite(text, src, site, mapped, media), encoding="utf-8")
    nav = []
    for group, entries in NAV:
        nav.append({group: [{title: (site_path(src) if src.endswith(".md") else "catalog/index.html")}
                            for src, title in entries]})
    shutil.copytree(ROOT / "docs" / "catalog", docs / "catalog", ignore=shutil.ignore_patterns("*.py", "__pycache__"))
    shutil.copytree(ROOT / "docs" / "brand", docs / "brand", ignore=shutil.ignore_patterns("README.md"), dirs_exist_ok=True)
    for old, new in redirects(pages).items():
        (docs / old).parent.mkdir(parents=True, exist_ok=True)
        (docs / old).write_text(f'<!doctype html><meta charset="utf-8"><title>Moved</title><link rel="canonical" '
                                f'href="{new}"><meta http-equiv="refresh" content="0; url={new}">'
                                f'<script>location.replace("{new}" + location.hash)</script>'
                                f'<a href="{new}">This page moved.</a>\n', encoding="utf-8")
    for rel in sorted(media):
        (docs / "files" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, docs / "files" / rel)
    # JSON is YAML: MkDocs reads it without PyYAML here – the fence's format unquoted, a tag, not a string
    text = json.dumps(config(nav), indent=1, ensure_ascii=False).replace(json.dumps(FENCE_FORMAT), FENCE_FORMAT)
    (out / "mkdocs.yml").write_text(text, encoding="utf-8")
    return out


if __name__ == "__main__":
    print(f"assembled: {assemble(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'build' / 'pages')}")
