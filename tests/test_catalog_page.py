"""The catalog pages (docs/catalog/build.py) and their drawings equal what the catalog, the domains and the reference
circuits give – rebuild with `.venv/bin/python docs/catalog/build.py` after a change to any of them."""

import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "catalog"


def build_module():
    spec = importlib.util.spec_from_file_location("catalog_page", PAGE / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_pages_and_the_drawings_are_current(tmp_path):
    written = build_module().build(tmp_path)
    stale = [f.relative_to(tmp_path).as_posix() for f in written
             if not (PAGE / f.relative_to(tmp_path)).is_file()
             or (PAGE / f.relative_to(tmp_path)).read_bytes() != f.read_bytes()]
    assert stale == [], "rebuild with .venv/bin/python docs/catalog/build.py"
    # nothing beside them that the build no longer writes, and no page over 300 KB
    names = {f.relative_to(tmp_path).as_posix() for f in written}
    there = {f.relative_to(PAGE).as_posix() for f in [*PAGE.glob("*.html"), *PAGE.glob("circuits/*.svg")]}
    assert there - names == set(), "a page or drawing the build no longer writes"
    assert [(f.name, f.stat().st_size) for f in written if f.suffix == ".html" and f.stat().st_size > 300_000] == []


def test_pages_names_the_pages_written_in_order(tmp_path):
    """PAGES – what docs/pages.py puts into the site's navigation – is every page written but the one per reference
    circuit and per open design, which circuits.html and open-designs.html list; the index first, then the engines."""
    from edakit import catalog
    mod = build_module()
    files = [f for f, _ in mod.PAGES]
    assert files[0] == "index.html" and len(files) == len(set(files))
    assert files[1:1 + len(catalog.engines())] == [f'{e["prefix"].lower()}.html' for e in catalog.engines().values()]
    written = {f.name for f in PAGE.glob("*.html")}
    sub = {f for f in written if f.startswith(("circuit-", "open-")) and f != "open-designs.html"}
    assert set(files) == written - sub


def test_every_code_and_every_reference_circuit_is_on_the_pages():
    """Each code on its engine's page – the page handbook.page_of links to – and as a row of index.html, so an old
    link catalog/#CODE still lands on it; each reference circuit on index.html, circuits.html and a page of its own."""
    from edakit import catalog
    from edakit.catalog.handbook import page_of
    import reference
    index = (PAGE / "index.html").read_text(encoding="utf-8")
    assert [c for c in catalog.codes() if f'id="{c}"' not in index] == []
    pages = {}
    missing = []
    for c in catalog.codes():
        f = PAGE / Path(page_of(c)).name
        assert page_of(c) == f"../docs/catalog/{f.name}"
        html = pages.setdefault(f, f.read_text(encoding="utf-8") if f.is_file() else "")
        if f'id="{c}"' not in html:
            missing.append(c)
    assert missing == []
    circuits = (PAGE / "circuits.html").read_text(encoding="utf-8")
    for n in reference.REFERENCES:
        own = PAGE / f"circuit-{n}.html"
        assert f'id="circuit-{n}"' in index and f'id="circuit-{n}"' in circuits
        assert own.is_file() and f'id="circuit-{n}"' in own.read_text(encoding="utf-8")


def test_the_candidate_status_names_known_codes_and_states():
    from edakit import catalog
    s = tomllib.loads((ROOT / "docs" / "concepts" / "done" / "maker-coverage-status.toml").read_text(encoding="utf-8"))
    assert {e["status"] for sec in ("features", "checks", "hints", "blocks", "review") for e in s[sec].values()} <= \
        {"built", "partial", "open", "out"}
    assert (len(s["features"]), len(s["checks"]), len(s["hints"]), len(s["blocks"])) == (24, 31, 19, 18)
    hints = {e["where"].split()[0] for e in s["hints"].values() if e["status"] == "built"}
    assert hints - set(catalog.codes()) == set()
