"""The site for GitHub Pages (docs/pages.py): every page of the handbook, the concepts, the skills and the agents is
on it, a link to a page of the site stays on the site, an image goes onto the site, a link to anything else goes to
the file on GitHub."""

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
    want = (["index.md", "handbook/index.md", "evals.md", "catalog/index.html"]
            + [f"handbook/{p.name}" for p in (ROOT / "handbook").glob("[0-9]*.md")]
            + [f"skills/{p.parent.name}.md" for p in (ROOT / "skills").glob("*/SKILL.md")]
            + [f"agents/{p.name}" for p in (ROOT / "agents").glob("*.md")]
            + [f"catalog/circuits/{p.name}" for p in (ROOT / "docs" / "catalog" / "circuits").glob("*.svg")])
    assert [w for w in want if not (docs / w).is_file()] == []
    cfg = json.loads((out / "mkdocs.yml").read_text(encoding="utf-8"))
    assert cfg["docs_dir"] == "docs" and {"Rule catalog": "catalog/index.html"} in cfg["nav"]


def test_links_stay_on_the_site_or_go_to_github():
    mod = pages()
    mapped = {"handbook/14-design.md": "handbook/14-design.md", "README.md": "index.md"}
    text = ("[a](handbook/14-design.md#144-x) [b](tests/reference.py) [c](edakit/domains/) [d](https://x.org) "
            "[e](#here) [f](docs/catalog/build.py)\n```\n[g](tests/x.py)\n```\n")
    out = mod.rewrite(text, "README.md", "index.md", mapped)
    assert "[a](handbook/14-design.md#144-x)" in out
    assert f"[b]({mod.REPO}/blob/main/tests/reference.py)" in out
    assert f"[c]({mod.REPO}/tree/main/edakit/domains)" in out
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
