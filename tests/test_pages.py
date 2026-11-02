"""The site for GitHub Pages (docs/pages.py): every page of the documentation, the concepts, the skills and the agents
is on it, the navigation is NAV – tabs by reader, at most eight entries a tab but for the handbook, short titles –, a
link to a page of the site stays on the site, an image goes onto the site, a link to anything else goes to the file on
GitHub."""

import importlib.util
import json
import posixpath
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pages():
    spec = importlib.util.spec_from_file_location("pages", ROOT / "docs" / "pages.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_description_is_a_page_of_the_site(tmp_path):
    out = pages().assemble(tmp_path / "pages")
    docs = out / "docs"
    want = (["index.md", "handbook/index.md", "inside/evals.md", "catalog/index.html", "inside/index.md",
             "inside/claude.md", "inside/concepts/index.md", "inside/skills/index.md", "inside/agents/index.md",
             "reference/index.md", "reference/changelog.md"]
            + [f"handbook/{p.name}" for p in (ROOT / "handbook").glob("[0-9]*.md")]
            + [f"{'extend' if p.parent.name.startswith('propose-') else 'inside/skills'}/{p.parent.name}.md"
               for p in (ROOT / "skills").glob("*/SKILL.md")]
            + [f"inside/agents/{p.name}" for p in (ROOT / "agents").glob("*.md") if p.name != "README.md"]
            + [f"catalog/circuits/{p.name}" for p in (ROOT / "docs" / "catalog" / "circuits").glob("*.svg")])
    assert [w for w in want if not (docs / w).is_file()] == []
    mod = pages()
    text = (out / "mkdocs.yml").read_text(encoding="utf-8")
    assert f'"format": {mod.FENCE_FORMAT}\n' in text            # a YAML tag, unquoted, nothing after it
    cfg = json.loads(text.replace(mod.FENCE_FORMAT, json.dumps(mod.FENCE_FORMAT)))
    fences = next(e["pymdownx.superfences"] for e in cfg["markdown_extensions"] if "pymdownx.superfences" in e)
    assert fences["custom_fences"][0]["name"] == "mermaid"
    reference = next(g["Reference"] for g in cfg["nav"] if "Reference" in g)
    assert cfg["docs_dir"] == "docs" and {"Rule catalog": "catalog/index.html"} in reference
    assert "edakit" in cfg["copyright"] and "issues/new/choose" in cfg["copyright"]   # the version, the feedback line
    features = cfg["theme"]["features"]
    assert "navigation.tabs" in features and "navigation.indexes" in features
    assert cfg["nav"][0] == {"Start": [{"Start": "index.md"}, {"Quickstart": "start/quickstart.md"},
                                       {"How it works": "start/how-it-works.md"},
                                       {"Projects": "start/projects/index.md"}, {"Glossary": "start/glossary.md"}]}
    # every page under its tab: the address's first part is the tab's
    for group in cfg["nav"][1:]:
        (tab, entries), = group.items()
        assert all(path.startswith(mod.TAB_DIR[tab] + "/") or path == "catalog/index.html"
                   for entry in entries for path in entry.values()), tab


def test_the_navigation_is_tabs_by_reader_with_short_titles():
    """Steps N.1 and N.2 of docs/concepts/done/documentation-newcomer.md: tabs by reader, at most eight entries a tab
    but for the handbook, titles of at most five words; every page of kind documentation in a tab, the steps among
    them; the sources only in the tab "Inside edakit", its overview and the index of each kind – the pages stay on the
    site, out of the navigation."""
    mod = pages()
    tabs = [g for g, _ in mod.NAV]
    assert tabs == ["Start", "A circuit", "A board", "Extend", "Develop", "Handbook", "Reference", "Inside edakit"]
    chapters = [int(Path(src).name[:2]) for src, _ in dict(mod.NAV)["Handbook"] if Path(src).name[:2].isdigit()]
    assert chapters == sorted(chapters)                          # by number; the index says which to read when
    assert all(len(entries) <= mod.SIDEBAR for tab, entries in mod.NAV if tab != "Handbook")
    assert all(len(title.split()) <= 5 for _, entries in mod.NAV for _, title in entries)
    listed = {src for _, entries in mod.NAV for src, _ in entries}
    docs = {"README.md", *(f"handbook/{p.name}" for p in (ROOT / "handbook").glob("*.md")),
            *(p.relative_to(ROOT).as_posix() for p in (ROOT / "docs").glob("*.md")), "docs/brand/README.md",
            *(p.relative_to(ROOT).as_posix() for p in (ROOT / "docs" / "steps").glob("*.md")),
            "docs/projects/README.md"}
    assert sorted(docs - listed) == []
    assert all((ROOT / src).is_file() for src in listed - mod.GENERATED)
    inside = dict(mod.NAV)["Inside edakit"]
    assert [src for src, _ in inside] == ["docs/inside-edakit.md", *mod.INSIDE]
    assert not any(mod.is_source(src) for tab, entries in mod.NAV if tab != "Inside edakit" for src, _ in entries
                   if not src.startswith("skills/propose-"))
    on_site = {src for src, _, _ in mod.sources()}
    assert set(mod.INSIDE) <= on_site and "docs/inside-edakit.md" in on_site


def test_a_source_carries_the_source_line_and_the_concepts_an_index(tmp_path):
    docs = pages().assemble(tmp_path / "pages") / "docs"
    assert "A source" in (docs / "inside" / "concepts" / "done" / "documentation.md").read_text(encoding="utf-8")
    assert "A source" in (docs / "inside" / "skills" / "cart.md").read_text(encoding="utf-8")
    assert "A source" not in (docs / "handbook" / "08-release-gate.md").read_text(encoding="utf-8")
    index = (docs / "inside" / "concepts" / "index.md").read_text(encoding="utf-8")
    assert "## Open" in index and "(new/parts-on-hand.md)" in index and "prototypes" not in index
    assert "## Decided and built" in index and "(done/documentation.md)" in index
    inside = (docs / "inside" / "index.md").read_text(encoding="utf-8")
    assert "(concepts/index.md)" in inside and "(skills/index.md)" in inside and "(claude.md)" in inside
    assert 'url=../inside/"' in (docs / "inside-edakit" / "index.html").read_text(encoding="utf-8")   # the old address


def test_links_stay_on_the_site_or_go_to_github():
    mod = pages()
    mapped = {"handbook/14-design.md": "handbook/14-design.md", "README.md": "index.md"}
    text = ("[a](handbook/14-design.md#144-x) [b](tests/reference.py) [c](edakit/domains/) [d](https://x.org) "
            "[e](#here) [f](docs/catalog/build.py)\n```\n[g](tests/x.py)\n```\n")
    out = mod.rewrite(text, "README.md", "index.md", mapped)
    assert "[a](handbook/14-design.md#144-x)" in out
    assert f"[b]({mod.REPO}/blob/main/tests/reference.py)" in out
    assert f"[c]({mod.REPO}/tree/main/edakit/domains)" in out
    assert mod.rewrite("[k](../skills/)", "docs/inside-edakit.md", "inside-edakit.md",
                       {"skills/README.md": "skills/index.md"}) == "[k](skills/index.md)"
    assert "[d](https://x.org)" in out and "[e](#here)" in out
    assert "[f](catalog/build.py)" not in out and "[g](tests/x.py)" in out
    back = mod.rewrite("[home](../README.md) [ch](05-simulation.md)", "handbook/14-design.md", "handbook/14-design.md",
                       {"README.md": "index.md", "handbook/05-simulation.md": "handbook/05-simulation.md"})
    assert back == "[home](../index.md) [ch](05-simulation.md)"


def test_an_image_goes_onto_the_site(tmp_path):
    """GitHub's page of a file is HTML, no image: the walkthrough's drawings (handbook 17) are copied under files/."""
    mod = pages()
    media = set()
    out = mod.rewrite("![s](../examples/coin-cell-led/docs/schematic.svg) [r](../examples/coin-cell-led/README.md)",
                      "handbook/17-walkthrough.md", "handbook/17-walkthrough.md", {}, media)
    assert out == (f"![s](../files/examples/coin-cell-led/docs/schematic.svg) "
                   f"[r]({mod.REPO}/blob/main/examples/coin-cell-led/README.md)")
    assert media == {"examples/coin-cell-led/docs/schematic.svg"}
    docs = mod.assemble(tmp_path / "pages") / "docs"
    assert (docs / "files" / "examples" / "coin-cell-led" / "docs" / "pcb_plan_main.png").is_file()


def test_the_start_pages_links_to_the_site_land_on_its_pages():
    """The README links its readers to the site, not to the Markdown on GitHub: every such link names a page the
    site has (a page "x/" is x.md or x/index.md there)."""
    import re
    mod = pages()
    have = {site for _, site, _ in mod.sources()} | {"catalog/index.html"}
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    links = re.findall(re.escape(mod.SITE) + r"([^)\s>#]*)", readme)
    assert len(links) > 10
    missing = [u for u in links if u and not ({u.rstrip("/") + ".md", u + "index.md", u + "index.html"} & have)]
    assert missing == []


def test_an_old_address_sends_the_reader_on(tmp_path):
    """Since the addresses follow the tabs, every page that moved keeps its old address as a page that sends the reader
    on, the anchor kept – links from outside (posts, issues, other projects) hold."""
    import re
    mod = pages()
    docs = pages().assemble(tmp_path / "pages") / "docs"
    moved = mod.redirects(mod.sources())
    assert {"quickstart/index.html", "steps/index.html", "skills/cart/index.html",
            "concepts/done/documentation/index.html", "changelog/index.html"} <= set(moved)
    for old, new in moved.items():
        text = (docs / old).read_text(encoding="utf-8")
        assert f'url={new}"' in text and "location.hash" in text
        target = posixpath.normpath(posixpath.join(posixpath.dirname(old), new))
        assert (docs / target / "index.md").is_file() or (docs / (target + ".md")).is_file(), (old, new)
    assert not re.search(r"handbook/\d\d-", " ".join(moved))       # the handbook kept its addresses
