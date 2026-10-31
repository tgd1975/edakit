"""edakit's documentation as one site for GitHub Pages: the README as the start page, the handbook, the rule catalog
(docs/catalog), the concepts, the skills, the agents and the evals – assembled into build/pages, built by MkDocs.

    python3 docs/pages.py                       assembles build/pages (the Markdown, the catalog, mkdocs.yml)
    uvx --with mkdocs-material==9.6.23 --from mkdocs==1.6.1 mkdocs build --strict -f build/pages/mkdocs.yml
                                                writes the site into build/site

The workflow .github/workflows/pages.yml runs both on every push and publishes the site from main. The sources stay
where they are; a link to a file the site does not carry goes to the file on GitHub.
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


def sources():
    """[(repo path, site path, section)] of every Markdown page of the site, in the order of the navigation."""
    out = [("README.md", "index.md", None)]
    out.append(("handbook/README.md", "handbook/index.md", "Handbook"))
    out += [(f"handbook/{p.name}", f"handbook/{p.name}", "Handbook") for p in sorted((ROOT / "handbook").glob("[0-9]*.md"))]
    concepts = sorted((ROOT / "docs" / "concepts").rglob("*.md"))
    out += [(p.relative_to(ROOT).as_posix(), "concepts/" + p.relative_to(ROOT / "docs" / "concepts").as_posix(),
             "Concepts") for p in concepts]
    out += [(f"skills/{p.parent.name}/SKILL.md", f"skills/{p.parent.name}.md", "Skills")
            for p in sorted((ROOT / "skills").glob("*/SKILL.md"))]
    out += [(f"agents/{p.name}", f"agents/{p.name}", "Agents") for p in sorted((ROOT / "agents").glob("*.md"))]
    out.append(("evals/README.md", "evals.md", "Evals"))
    return out


def rewrite(text, src, site, mapped):
    """The page's relative links: to a page of the site its path there, to anything else the file on GitHub."""
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
        if rel == "docs/catalog" or (rel.startswith("docs/catalog/") and not rel.endswith(".py")):
            # the catalog page and its drawings are on the site; its generator is not
            new = _relpath("catalog/" + rel[len("docs/catalog/"):] if rel != "docs/catalog" else "catalog/", site)
            return f"{m.group(1)}{new}{m.group(3)}"
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
        "site_description": "Circuit design as code – handbook, rule catalog, concepts, skills and agents of edakit",
        "site_url": SITE,
        "repo_url": REPO,
        "repo_name": "tgd1975/edakit",
        "edit_uri": "",
        "docs_dir": "docs",
        "site_dir": "../site",
        "use_directory_urls": True,
        "theme": {
            "name": "material",
            "features": ["navigation.sections", "navigation.top", "navigation.indexes", "search.highlight",
                         "content.code.copy", "toc.follow"],
            "palette": [
                {"media": "(prefers-color-scheme: light)", "scheme": "default", "primary": "teal", "accent": "teal",
                 "toggle": {"icon": "material/brightness-7", "name": "Dark mode"}},
                {"media": "(prefers-color-scheme: dark)", "scheme": "slate", "primary": "teal", "accent": "teal",
                 "toggle": {"icon": "material/brightness-4", "name": "Light mode"}},
            ],
        },
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
    """Write the site's sources into out: docs/ with every page and the catalog, mkdocs.yml beside it."""
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    docs = out / "docs"
    pages = sources()
    mapped = {src: site for src, site, _ in pages}
    nav, sections = [], {}
    for src, site, section in pages:
        text = (ROOT / src).read_text(encoding="utf-8")
        meta, body = front_matter(text)
        name = Path(src).parent.name if src.endswith("SKILL.md") else Path(src).stem
        if meta:
            title = title_of(body, meta.get("name", name))
            lead = f"\n_{meta['description']}_\n" if meta.get("description") else ""
            body = (re.sub(r"^# .+$", lambda m: m.group(0) + "\n" + lead, body, count=1, flags=re.M)
                    if re.search(r"^# ", body, re.M) else f"# {meta.get('name', name)}\n{lead}\n{body}")
            text = body
        title = title_of(text, name)
        f = docs / site
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(rewrite(text, src, site, mapped), encoding="utf-8")
        if section is None:
            nav.append({"Home": site})
            continue
        if section not in sections:
            sections[section] = []
            nav.append({section: sections[section]})
            if section == "Handbook":
                nav.append({"Rule catalog": "catalog/index.html"})
        sections[section].append(site if site.endswith("index.md") else {title: site})
    shutil.copytree(ROOT / "docs" / "catalog", docs / "catalog", ignore=shutil.ignore_patterns("*.py", "__pycache__"))
    # JSON is YAML: MkDocs reads it without PyYAML here
    (out / "mkdocs.yml").write_text(json.dumps(config(nav), indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(f"assembled: {assemble(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'build' / 'pages')}")
