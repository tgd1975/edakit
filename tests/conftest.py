import json
import shutil
from pathlib import Path

import pytest

import parity

EXAMPLE = Path(__file__).resolve().parent / "fixtures" / "led-bar"
LIBRARY_PARTS = Path(__file__).resolve().parents[1] / "edakit" / "blocks" / "parts"
JLCPCB = Path(__file__).resolve().parent / "fixtures" / "jlcpcb"   # recorded catalogue answers and part pages


@pytest.fixture
def jlcpcb(monkeypatch):
    """JLCPCB from the recordings in fixtures/jlcpcb (test_stock.py); the list of catalogue requests."""
    from edakit import stock
    from edakit.release import fab
    asked = []

    def search(keyword, page_size=10, timeout=30):
        asked.append(keyword)
        f = JLCPCB / "catalogue" / f"{keyword}.json"
        return json.loads(f.read_text(encoding="utf-8"))["data"]["componentPageInfo"]["list"] if f.exists() else []

    def page(lcsc, timeout=30):
        return (JLCPCB / "partdetail" / f"{lcsc}.html").read_text(encoding="utf-8")
    monkeypatch.setattr(fab, "jlc_search", search)
    monkeypatch.setattr(stock, "fetch_part_page", page)
    return asked


@pytest.fixture
def project(tmp_path):
    """A writable copy of the example project; returns a helper to load config, graph and parts."""
    dst = tmp_path / "led-bar"
    shutil.copytree(EXAMPLE, dst, ignore=shutil.ignore_patterns("build"))

    class P:
        root = dst
        graph_file = dst / "hardware" / "graph.json"

        def config(self):
            from edakit import config
            return config.load(dst / "edakit.toml")

        def graph(self):
            return json.loads(self.graph_file.read_text())

        def save_graph(self, g):
            self.graph_file.write_text(json.dumps(g, indent=1))

        def part(self, lcsc):
            return json.loads((dst / "hardware" / "parts" / f"{lcsc}.json").read_text())

        def save_part(self, lcsc, data):
            (dst / "hardware" / "parts" / f"{lcsc}.json").write_text(json.dumps(data, indent=1))

        def use_library_part(self, lcsc):
            """A checked parts entry from the block library, e.g. the S8050 (C2146) for a transistor stage."""
            shutil.copy(LIBRARY_PARTS / f"{lcsc}.json", dst / "hardware" / "parts" / f"{lcsc}.json")

        def free_pins(self, g, *refs):
            """Take MCU pins out of nc, so that a test can put them into nets."""
            for ref in refs:
                des, _, pin = ref.partition(".")
                self.comp(g, des)["nc"].remove(pin)

        def net(self, g, name):
            return next(n for n in g["graph"]["nets"] if n["name"] == name)

        def comp(self, g, des):
            return next(c for c in g["graph"]["components"] if c["designator"] == des)
    return P()


@pytest.fixture(autouse=True)
def engines_agree(monkeypatch, request):
    """Every run of the checks of before is also run by the engines of the restructuring, and both must agree
    (parity.py). A test that breaks a design on purpose for the checks of before only: @pytest.mark.no_parity."""
    from edakit import checks
    if request.node.get_closest_marker("no_parity"):
        return
    before = checks.run

    def run(design, cfg=None):
        rep = before(design, cfg)
        diff = parity.compare(design, cfg, rep)
        assert not diff, "the engines differ from the checks of before:\n" + diff
        return rep
    monkeypatch.setattr(checks, "run", run)
    from edakit.sim import run as simrun
    before_sim = simrun.run_all

    def run_all(*args, **kwargs):
        out = before_sim(*args, **kwargs)
        diff = parity.compare_sim(out)
        assert not diff, "the engine SIM differs from the simulation checks of before:\n" + diff
        return out
    monkeypatch.setattr(simrun, "run_all", run_all)
