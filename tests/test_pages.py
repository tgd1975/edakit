"""The site for GitHub Pages (docs/pages.py): every page of the documentation, the concepts, the skills and the agents
is on it, the navigation is NAV – tabs by reader, at most eight entries a tab but for the handbook, short titles –, a
link to a page of the site stays on the site, an image goes onto the site, a link to anything else goes to the file on
GitHub."""

import importlib.util
import json
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
    want = (["index.md", "handbook/index.md", "evals.md", "catalog/index.html", "inside-edakit.md", "inside/claude.md",
             "concepts/index.md", "skills/index.md", "agents/index.md"]
            + [f"handbook/{p.name}" for p in (ROOT / "handbook").glob("[0-9]*.md")]
            + [f"skills/{p.parent.name}.md" for p in (ROOT / "skills").glob("*/SKILL.md")]
            + [f"agents/{p.name}" for p in (ROOT / "agents").glob("*.md")]
            + [f"catalog/circuits/{p.name}" for p in (ROOT / "docs" / "catalog" / "circuits").glob("*.svg")])
    assert [w for w in want if not (docs / w).is_file()] == []
    cfg = json.loads((out / "mkdocs.yml").read_text(encoding="utf-8"))
    reference = next(g["Reference"] for g in cfg["nav"] if "Reference" in g)
    assert cfg["docs_dir"] == "docs" and {"Rule catalog": "catalog/index.html"} in reference
    assert "edakit" in cfg["copyright"] and "issues/new/choose" in cfg["copyright"]   # the version, the feedback line
    features = cfg["theme"]["features"]
    assert "navigation.tabs" in features and "navigation.indexes" in features
    assert cfg["nav"][0] == {"Start": [{"Start": "index.md"}, {"Quickstart": "quickstart.md"},
                                       {"How it works": "how-it-works.md"}, {"Projects": "projects/index.md"},
                                       {"Glossary": "glossary.md"}]}


def test_the_navigation_is_tabs_by_reader_with_short_titles():
    """Step N.1 of docs/concepts/new/documentation-newcomer.md: tabs by reader, at most eight entries a tab but for the
    handbook, titles of at most five words; every page of kind documentation in a tab, the sources in none – they
    stand behind "Inside edakit" and stay on the site."""
    mod = pages()
    tabs = [g for g, _ in mod.NAV]
    assert tabs == ["Start", "Extend", "Develop", "Handbook", "Reference"]
    assert all(len(entries) <= mod.SIDEBAR for tab, entries in mod.NAV if tab != "Handbook")
    assert all(len(title.split()) <= 5 for _, entries in mod.NAV for _, title in entries)
    listed = {src for _, entries in mod.NAV for src, _ in entries}
    docs = {"README.md", *(f"handbook/{p.name}" for p in (ROOT / "handbook").glob("*.md")),
            *(p.relative_to(ROOT).as_posix() for p in (ROOT / "docs").glob("*.md")), "docs/brand/README.md",
            "docs/projects/README.md"}
    assert sorted(docs - listed) == []
    assert all((ROOT / src).is_file() for src in listed)
    assert not any(mod.is_source(src) for src in listed if not src.startswith("skills/propose-"))
    on_site = {src for src, _, _ in mod.sources()}
    assert set(mod.INSIDE) <= on_site and "docs/inside-edakit.md" in on_site


def test_a_source_carries_the_source_line_and_the_concepts_an_index(tmp_path):
    docs = pages().assemble(tmp_path / "pages") / "docs"
    assert "A source" in (docs / "concepts" / "done" / "documentation.md").read_text(encoding="utf-8")
    assert "A source" in (docs / "skills" / "cart.md").read_text(encoding="utf-8")
    assert "A source" not in (docs / "handbook" / "08-release-gate.md").read_text(encoding="utf-8")
    index = (docs / "concepts" / "index.md").read_text(encoding="utf-8")
    assert "## Open" in index and "(new/documentation-newcomer.md)" in index and "prototypes" not in index
    assert "## Decided and built" in index and "(done/documentation.md)" in index
    inside = (docs / "inside-edakit.md").read_text(encoding="utf-8")
    assert "(concepts/index.md)" in inside and "(skills/index.md)" in inside and "(inside/claude.md)" in inside


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
