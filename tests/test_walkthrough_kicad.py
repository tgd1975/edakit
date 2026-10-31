"""The example of walkthrough 2 (handbook 18, examples/blinker-555): what the chapter quotes still holds."""

import argparse
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from edakit import config, engines, schematic_draw
from edakit.design import Design
from edakit.sim import run as simrun

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "blinker-555"
SVG = "{http://www.w3.org/2000/svg}"
needs_ngspice = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


@pytest.fixture
def example(tmp_path):
    """A writable copy without build/ – what a fresh clone has."""
    dst = tmp_path / "blinker-555"
    shutil.copytree(EXAMPLE, dst, ignore=shutil.ignore_patterns("build"))
    return config.load(dst / "edakit.toml")


def test_a_kicad_project_with_a_toml_graph(example):
    assert example.toolchain == "kicad" and example.graph.name == "graph.toml"


def test_check_has_the_accepts_and_no_finding(example):
    rep = engines.run_all(Design.from_config(example), example)
    assert rep.errors == [] and rep.warnings == []
    assert sorted((f.code, f.place) for f in rep.accepted) == [
        ("HINT.bulk", "BT1"), ("HINT.gate", "Q1"), ("HINT.lithium", "BT1"),
        ("HINT.thermal_copper", "D1"), ("HINT.thermal_copper", "Q1"), ("HINT.thermal_copper", "U1")]
    assert {f.code for f in rep.notes} <= {"HINT.datasheet", "PARTS.library", "PARTS.stock",
                                           "GEO.formed"}     # a fresh clone has no library footprint cache
    assert not [f for f in rep.findings if f.code == "LVL.undefined"]   # D1 into U1's discharge pin: no pull-up wanted


@needs_ngspice
def test_simulation_gives_the_quoted_currents(example):
    out = simrun.run_all(Design.from_config(example), simrun.load_sim_config(example)[0])
    assert {c["result"] for c in out["checks"]} <= {"pass", "info"}
    assert len(out["checks"]) == 688
    led = {c["scenario"]: float(c["actual"].split()[0]) for c in out["checks"]
           if c["item"] == "D1" and c["check"] == "LED on"}
    assert min(led.values()) == pytest.approx(0.519e-3, rel=0.01)            # R-1: 2.2 V, VF max, DIS 150 Ω
    assert led["used/on/vf-max/spread-max"] == min(led.values())
    cells = {c["scenario"]: float(c["actual"].split()[0]) for c in out["checks"]
             if c["item"] == "BT1" and c["check"] == "current from the cell (expected in this load)"}
    assert max(cells.values()) == pytest.approx(7.57e-3, rel=0.01)           # R-4 at 8 mA, D-9: DIS at 15 Ω
    assert max(v for s, v in cells.items() if "/off/" in s) < 1e-9           # R-3: SW1 off
    off = [c for c in out["checks"] if c["item"] == "U1" and c["id"] == "LIM.range" and "/off/" in c["scenario"]]
    assert off and {c["result"] for c in off} == {"info"}                    # switched off, not below its range
    reversed_ = {c["check"]: c["actual"] for c in out["checks"]
                 if c["scenario"].startswith("reversed/on") and c["item"] in ("D1", "Q1")}
    assert reversed_["LED dark"].endswith(" A") and float(reversed_["LED dark"].split()[0]) < 1e-9   # D-4: Q1 blocks


@needs_ngspice
def test_the_drawing_quotes_the_simulation(example, tmp_path):
    out = tmp_path / "s.svg"
    assert schematic_draw.main(example, argparse.Namespace(board=None, out=str(out), force=False)) == 0
    texts = {t.text for t in ET.parse(out).getroot().iter(f"{SVG}text")}
    assert "D1 carries 519 µA at 2.2 V, 7.32 mA from fresh cells" in texts
