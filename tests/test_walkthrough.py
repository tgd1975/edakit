"""The example of the walkthrough (handbook 17, examples/coin-cell-led): what the chapter quotes still holds."""

import argparse
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from edakit import config, engines, schematic_draw
from edakit.design import Design
from edakit.sim import run as simrun

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "coin-cell-led"
SVG = "{http://www.w3.org/2000/svg}"
needs_ngspice = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


@pytest.fixture
def example(tmp_path):
    """A writable copy without build/ – what a fresh clone has."""
    dst = tmp_path / "coin-cell-led"
    shutil.copytree(EXAMPLE, dst, ignore=shutil.ignore_patterns("build"))
    return config.load(dst / "edakit.toml")


def test_check_has_the_accepts_and_nothing_else(example):
    rep = engines.run_all(Design.from_config(example), example)
    assert rep.errors == [] and rep.warnings == [] and rep.notes == []
    assert sorted((f.code, f.place) for f in rep.accepted) == [
        ("HINT.bulk", "BT1"), ("HINT.lithium", "BT1"), ("PATH.reverse", "R1.1")]   # no MCU reads SW1: no HINT.debounce
    assert {f.code for f in rep.pending} <= {"PARTS.stock"}    # the stock snapshot of 2026-10-29 ages


@needs_ngspice
def test_simulation_gives_the_quoted_currents(example):
    out = simrun.run_all(Design.from_config(example), simrun.load_sim_config(example)[0])
    assert [c for c in out["checks"] if c["result"] != "pass"] == []
    led = {c["scenario"]: float(c["actual"].split()[0]) for c in out["checks"] if c["check"] == "LED on"}
    assert {c["id"] for c in out["checks"] if c["check"] == "LED on"} == {"SIM.state"}   # R-1's rows
    assert led["used/pressed/vf-max"] == pytest.approx(1.22e-3, rel=0.01)     # R-1, D-2: the least
    assert led["fresh/pressed/vf-min"] == pytest.approx(10.7e-3, rel=0.01)    # the most
    reverse = [c["actual"] for c in out["checks"] if c["scenario"] == "reversed/pressed"
               and c["check"] == "reverse voltage"]
    assert reverse == ["3.2 V"]                                                # D-3: D1 blocks
    power = {c["scenario"]: c for c in out["checks"] if c["id"] == "LIM.p" and c["item"] == "D1"}
    assert len(power) == 9 and {c["expected"] for c in power.values()} == {"≤ 0.0325 W (50% of 0.065 W)"}
    assert float(power["fresh/pressed/vf-min"]["actual"].split()[0]) == pytest.approx(14.75e-3, rel=0.01)


@needs_ngspice
def test_the_drawing_quotes_the_simulation(example, tmp_path):
    out = tmp_path / "s.svg"
    assert schematic_draw.main(example, argparse.Namespace(board=None, out=str(out), force=False)) == 0
    texts = {t.text for t in ET.parse(out).getroot().iter(f"{SVG}text")}
    assert "D1 carries 1.22 mA from a used cell, 10.7 mA from a fresh one" in texts
