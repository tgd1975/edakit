import json
import shutil
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parent / "fixtures" / "led-bar"


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

        def net(self, g, name):
            return next(n for n in g["graph"]["nets"] if n["name"] == name)

        def comp(self, g, des):
            return next(c for c in g["graph"]["components"] if c["designator"] == des)
    return P()
