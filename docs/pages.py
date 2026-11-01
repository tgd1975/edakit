"""edakit's documentation as one site for GitHub Pages, assembled into build/pages and built by MkDocs. The navigation
is data – NAV, a table of group, file and short title, by reader (docs/concepts/new/documentation.md, step D.3): the
start, the circuit, the board, extending the rules, developing edakit, the reference, and at the end the sources as
"Inside edakit" – the concepts, skills and agents behind an index each, every page of them marked as a source.

    python3 docs/pages.py                       assembles build/pages (the Markdown, the catalog, mkdocs.yml)
    uvx --with mkdocs-material==9.6.23 --from mkdocs==1.6.1 mkdocs build --strict -f build/pages/mkdocs.yml
                                                writes the site into build/site

The workflow .github/workflows/pages.yml runs both on every push and publishes the site from main. The sources stay
where they are; a link to a file the site does not carry goes to the file on GitHub, an image goes onto the site
(files/<its path>) – GitHub's page of a file is no image.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/tgd1975/edakit"
SITE = "https://tgd1975.github.io/edakit/"
LINK = re.compile(r"(!?\[[^\]]*\]\()([^)\s]+)(\))")


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


# The navigation: (group, [(repo path, title of at most five words)]); a group's first page may be its index.
NAV = [
    ("Start", [
        ("docs/quickstart.md", "Quickstart"),
        ("docs/how-it-works.md", "How it works"),
        ("docs/catalog/index.html", "Rule catalog"),
        ("docs/projects/README.md", "Projects"),
        ("docs/glossary.md", "Glossary"),
    ]),
    ("The circuit", [
        ("handbook/README.md", "The handbook"),
        ("handbook/01-approach.md", "The approach"),
        ("handbook/02-setup.md", "Setup"),
        ("handbook/11-working-with-claude.md", "Working with Claude"),
        ("handbook/14-design.md", "Designing a circuit"),
        ("handbook/03-hardware-graph.md", "Hardware graph"),
        ("handbook/04-parts-database.md", "Parts"),
        ("handbook/05-simulation.md", "Simulation"),
        ("handbook/15-regulatory.md", "Regulatory review"),
    ]),
    ("The board", [
        ("handbook/06-schematic.md", "Schematic"),
        ("handbook/07-pcb.md", "PCB"),
        ("handbook/08-release-gate.md", "Release gate"),
        ("handbook/16-kicad.md", "KiCad"),
        ("handbook/17-walkthrough.md", "Walkthrough"),
        ("handbook/18-walkthrough-kicad.md", "Walkthrough on KiCad"),
        ("handbook/12-troubleshooting.md", "Troubleshooting"),
        ("handbook/13-lessons-learned.md", "Lessons learned"),
    ]),
    ("Extend the rules", [
        ("docs/adding-a-rule.md", "Adding a rule"),
        ("skills/propose-rule/SKILL.md", "Propose a rule"),
        ("skills/propose-feature/SKILL.md", "Propose a feature"),
    ]),
    ("Develop edakit", [
        ("docs/working-on-edakit.md", "Working on edakit"),
        ("docs/architecture.md", "edakit as a meta-harness"),
        ("docs/organisation.md", "Organisation"),
        ("docs/style.md", "Style guide"),
        ("docs/brand/README.md", "Brand"),
    ]),
    ("Reference", [
        ("handbook/10-reference.md", "Files, keys and commands"),
        ("handbook/09-easyeda-api.md", "EasyEDA API"),
        ("docs/catalog/index.html", "Rule catalog"),
        ("CHANGELOG.md", "Changelog"),
    ]),
    ("Inside edakit", [
        ("docs/concepts/README.md", "Concepts"),
        ("skills/README.md", "Skills"),
        ("agents/README.md", "Agents"),
        ("evals/README.md", "Evals"),
        ("CLAUDE.md", "Rules of a session"),
    ]),
]
GENERATED = {"docs/concepts/README.md", "skills/README.md", "agents/README.md"}   # indexes written by this script
SOURCE = ('!!! note "A source"\n    This page is a source of edakit – a concept, a prompt or the rules of a session –, '
          'shown as it is in the repository. Read it as such; the guides say what edakit does.\n')
ISSUES = f"{REPO}/issues/new/choose"


def site_path(src):
    """Where a repository file lands on the site."""
    special = {"README.md": "index.md", "handbook/README.md": "handbook/index.md", "evals/README.md": "evals.md",
               "CHANGELOG.md": "changelog.md", "CLAUDE.md": "inside/claude.md",
               "docs/brand/README.md": "brand/index.md", "docs/concepts/README.md": "concepts/index.md",
               "docs/projects/README.md": "projects/index.md", "skills/README.md": "skills/index.md",
               "agents/README.md": "agents/index.md"}
    if src in special:
        return special[src]
    if src.startswith("skills/") and src.endswith("/SKILL.md"):
        return f"skills/{src.split('/')[1]}.md"
    if src.startswith("docs/"):
        return src[len("docs/"):]
    return src


def is_source(src):
    """A page of "Inside edakit": a concept, a skill, an agent, an eval, CLAUDE.md – shown with the source line."""
    return src.startswith(("docs/concepts/", "skills/", "agents/", "evals/")) or src == "CLAUDE.md"


def concepts():
    """The concepts in their folders, prototype READMEs left out (their links still work)."""
    root = ROOT / "docs" / "concepts"
    return [p for p in sorted(root.rglob("*.md")) if "prototypes" not in p.parts and p.name != "README.md"]


def sources():
    """[(repo path, site path, section)] of every Markdown page of the site: the navigation's pages in its order, then
    the pages reached from an index – the concepts, skills, agents, the prototypes' READMEs and the project pages."""
    out = [("README.md", "index.md", None)]
    for group, pages in NAV:
        out += [(src, site_path(src), group) for src, _ in pages if src.endswith(".md")]
    more = [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "docs" / "concepts").rglob("*.md"))]
    more += [f"skills/{p.parent.name}/SKILL.md" for p in sorted((ROOT / "skills").glob("*/SKILL.md"))]
    more += [f"agents/{p.name}" for p in sorted((ROOT / "agents").glob("*.md")) if p.name != "README.md"]
    more += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "docs" / "projects").glob("*.md"))
             if p.name != "README.md"] if (ROOT / "docs" / "projects").is_dir() else []
    have = {s for s, _, _ in out}
    out += [(src, site_path(src), "") for src in more if src not in have]
    return out


def first_sentence(text):
    """The first sentence of a concept's status line, or of its first paragraph."""
    body = re.sub(r"^# .*\n", "", text, count=1).strip()
    m = re.search(r"^(?:\*\*)?(?:Status|State)\b.*?(?=\n\n|\Z)", body, re.S | re.M)
    para = " ".join((m.group(0) if m else body.split("\n\n")[0]).split())
    para = re.sub(r"^\*\*(Status|State)[^*]*\*\*\s*", r"\1 ", para)
    cut = re.search(r"(?<=[.;])\s|\s–\s", para)
    return (para[:cut.start()] if cut else para)[:240].rstrip(" .;") + "."


def index_pages():
    """{repo path: Markdown} of the indexes this script writes: the concepts by state, the skills, the agents."""
    lines = ["# Concepts", "", "A concept is how a part of edakit should work, written before it is built and kept as the "
             "record of what was decided. It starts in `new/`, moves to `done/` once it is decided and built, and to "
             "`discarded/` when the owner rejects it ([organisation](../organisation.md)). Each one below with the first "
             "sentence of its status line.", ""]
    for state, title in (("new", "Open"), ("done", "Decided and built"), ("discarded", "Discarded")):
        lines += [f"## {title}", ""]
        for p in concepts():
            rel = p.relative_to(ROOT / "docs" / "concepts")
            if rel.parts[0] == state:
                text = p.read_text(encoding="utf-8")
                lines.append(f"- [{title_of(text, p.stem)}]({rel.as_posix()}) – {first_sentence(text)}")
        lines.append("")
    skills = ["# Skills", "", "The plugin's skills: prompts that run a workflow in a session, each called as "
              "`/edakit:<name>`. What each does for you is in [handbook 11.1](../handbook/11-working-with-claude.md).", ""]
    for p in sorted((ROOT / "skills").glob("*/SKILL.md")):
        meta, _ = front_matter(p.read_text(encoding="utf-8"))
        skills.append(f"- [`/edakit:{p.parent.name}`]({p.parent.name}/SKILL.md) – {meta.get('description', '')}")
    agents = ["# Agents", "", "The plugin's agents: prompts that run Claude in a context of its own for one role, such as "
              "a review. What each does for you is in [handbook 11.1](../handbook/11-working-with-claude.md).", ""]
    for p in sorted((ROOT / "agents").glob("*.md")):
        if p.name != "README.md":
            meta, _ = front_matter(p.read_text(encoding="utf-8"))
            agents.append(f"- [`{p.stem}`]({p.name}) – {meta.get('description', '')}")
    return {"docs/concepts/README.md": "\n".join(lines) + "\n", "skills/README.md": "\n".join(skills) + "\n",
            "agents/README.md": "\n".join(agents) + "\n"}


def version():
    m = re.search(r'__version__ = "([^"]+)"', (ROOT / "edakit" / "__init__.py").read_text(encoding="utf-8"))
    return m.group(1) if m else "?"


def rewrite(text, src, site, mapped, media=None):
    """The page's relative links: to a page of the site its path there, an image to its copy under files/ (its path
    goes into the set media, for assemble to copy), to anything else the file on GitHub."""
    here = (ROOT / src).parent

    def one(m):
        target = m.group(2)
        if re.match(r"[a-z]+:|#|/", target) or "${" in target:
            return m.group(0)
        path, _, anchor = target.partition("#")
        resolved = (here / path).resolve()
        try:
            rel = resolved.relative_to(ROOT).as_posix()
        except ValueError:
            return m.group(0)
        if rel in mapped:
            new = _relpath(mapped[rel], site)
            return f"{m.group(1)}{new}{'#' + anchor if anchor else ''}{m.group(3)}"
        if rel.startswith("docs/brand/") and rel != "docs/brand/README.md":
            # the logo files and the theme's stylesheet are on the site
            return f"{m.group(1)}{_relpath(rel[len('docs/'):], site)}{m.group(3)}"
        if rel == "docs/catalog" or (rel.startswith("docs/catalog/") and not rel.endswith(".py")):
            # the catalog's pages and drawings are on the site; their generator is not
            new = _relpath("catalog/" + rel[len("docs/catalog/"):] if rel != "docs/catalog" else "catalog/", site)
            return f"{m.group(1)}{new}{'#' + anchor if anchor else ''}{m.group(3)}"
        if m.group(1).startswith("!") and media is not None and resolved.is_file():
            media.add(rel)
            return f"{m.group(1)}{_relpath('files/' + rel, site)}{m.group(3)}"
        kind = "tree" if resolved.is_dir() else "blob"
        return f"{m.group(1)}{REPO}/{kind}/main/{rel}{'#' + anchor if anchor else ''}{m.group(3)}"

    # links inside code blocks stay as they are
    parts = re.split(r"(```.*?```)", text, flags=re.S)
    return "".join(p if p.startswith("```") else LINK.sub(one, p) for p in parts)


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
            "features": ["navigation.sections", "navigation.top", "search.highlight",
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
                                {"toc": {"permalink": True}}, "pymdownx.superfences",
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
    nav = [{"Home": "index.md"}]
    for group, entries in NAV:
        nav.append({group: [{title: (site_path(src) if src.endswith(".md") else "catalog/index.html")}
                            for src, title in entries]})
    shutil.copytree(ROOT / "docs" / "catalog", docs / "catalog", ignore=shutil.ignore_patterns("*.py", "__pycache__"))
    shutil.copytree(ROOT / "docs" / "brand", docs / "brand", ignore=shutil.ignore_patterns("README.md"), dirs_exist_ok=True)
    for rel in sorted(media):
        (docs / "files" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, docs / "files" / rel)
    # JSON is YAML: MkDocs reads it without PyYAML here
    (out / "mkdocs.yml").write_text(json.dumps(config(nav), indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(f"assembled: {assemble(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'build' / 'pages')}")
