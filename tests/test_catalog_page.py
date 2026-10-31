"""The catalog page (docs/catalog/build.py) and its drawings equal what the catalog, the domains and the reference
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


def test_the_page_and_the_drawings_are_current(tmp_path):
    written = build_module().build(tmp_path)
    stale = [f.relative_to(tmp_path).as_posix() for f in written
             if not (PAGE / f.relative_to(tmp_path)).is_file()
             or (PAGE / f.relative_to(tmp_path)).read_bytes() != f.read_bytes()]
    assert stale == [], "rebuild with .venv/bin/python docs/catalog/build.py"


def test_every_code_and_every_reference_circuit_is_on_the_page():
    from edakit import catalog
    import reference
    html = (PAGE / "index.html").read_text(encoding="utf-8")
    assert [c for c in catalog.codes() if f'id="{c}"' not in html] == []
    assert [n for n in reference.REFERENCES if f'id="circuit-{n}"' not in html] == []


def test_the_candidate_status_names_known_codes_and_states():
    from edakit import catalog
    s = tomllib.loads((ROOT / "docs" / "concepts" / "done" / "maker-coverage-status.toml").read_text(encoding="utf-8"))
    assert {e["status"] for sec in ("features", "checks", "hints", "blocks", "review") for e in s[sec].values()} <= \
        {"built", "partial", "open", "out"}
    assert (len(s["features"]), len(s["checks"]), len(s["hints"]), len(s["blocks"])) == (24, 31, 19, 18)
    hints = {e["where"].split()[0] for e in s["hints"].values() if e["status"] == "built"}
    assert hints - set(catalog.codes()) == set()
