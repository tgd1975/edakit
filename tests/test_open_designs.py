"""Published open designs, transcribed into edakit projects (tests/open_designs/<name>/, maker-coverage FT-21): what
edakit check and edakit sim find on each – exactly the findings its findings.toml lists, every one judged there: real
(a point of the design), lacks (a fact the transcription or the datasheets lack), criterion (edakit's yardstick, not
the design's) or known gap (edakit judges it wrong, not fixed yet, with the reason). edakit's false alarms the designs
showed are fixed and listed there under [[fixed]] (tests/test_open_design_fixes.py holds them). The designs stay as
published; a finding that appears or goes is a change in edakit to look at, not to wave through.

  esp32-devkitc-v4                 Espressif ESP32-DevKitC V4, schematic Rev V4 (2017-12-06),
                                   https://dl.espressif.com/dl/schematics/esp32_devkitc_v4-sch.pdf – no licence stated;
                                   the circuit's facts transcribed: usb, radio and power in one board
  sparkfun-logic-level-converter   SparkFun Logic Level Converter Bi-Directional, Rev V01 (2013-09-26), CC BY-SA 3.0,
                                   https://cdn.sparkfun.com/datasheets/BreakoutBoards/Logic_Level_Bidirectional.pdf –
                                   four BSS138 channels, both directions simulated

Each design's README names its source, what was transcribed and the parts that stand in for unnamed ones.
"""

import json
import shutil
import tomllib
from pathlib import Path

import pytest

from helpers import check

from edakit import config, engines, schema
from edakit.design import Design

DESIGNS = Path(__file__).resolve().parent / "open_designs"
NAMES = sorted(p.name for p in DESIGNS.iterdir() if (p / "edakit.toml").is_file())
JUDGED = {"real", "lacks", "criterion", "known gap"}


def judged(name):
    return tomllib.loads((DESIGNS / name / "findings.toml").read_text(encoding="utf-8"))


def copy(name, tmp_path):
    dst = tmp_path / name
    shutil.copytree(DESIGNS / name, dst, ignore=shutil.ignore_patterns("build"))
    return config.load(dst / "edakit.toml")


def test_there_are_open_designs():
    assert len(NAMES) >= 2


@pytest.mark.parametrize("name", NAMES)
def test_what_edakit_check_finds_is_what_is_judged(name, tmp_path):
    cfg = copy(name, tmp_path)
    rep = check(Design.from_config(cfg), cfg)
    found = {(f.code, f.grade, f.place) for f in rep.findings if f.severity in ("error", "warning", "pending")}
    assert found == {(f["code"], f.get("grade", ""), f["place"]) for f in judged(name).get("check", [])}


@pytest.mark.parametrize("name", NAMES)
def test_what_edakit_sim_finds_is_what_is_judged(name, tmp_path):
    from edakit.sim import run as simrun
    cfg = copy(name, tmp_path)
    out = simrun.run_all(Design.from_config(cfg), engines.load_sim(cfg))
    failed = {(r["id"], r["item"]) for r in out["checks"] if r["result"] == "fail"}
    assert failed == {(f["code"], f["place"]) for f in judged(name).get("sim", [])}


@pytest.mark.parametrize("name", NAMES)
def test_every_finding_is_judged_with_a_reason(name):
    j = judged(name)
    for f in j.get("check", []) + j.get("sim", []):
        assert f["judged"] in JUDGED and len(f["why"]) > 20, f


@pytest.mark.parametrize("name", NAMES)
def test_every_parts_entry_names_its_datasheet_and_fits_the_schema(name):
    for f in sorted((DESIGNS / name / "hardware" / "parts").glob("*.json")):
        e = json.loads(f.read_text(encoding="utf-8"))
        assert schema.problems(e) == [], f.name
        assert e.get("sources") and e.get("verified", {}).get("datasheet"), f.name


@pytest.mark.parametrize("name", NAMES)
def test_every_design_cites_its_source(name):
    text = (DESIGNS / name / "README.md").read_text(encoding="utf-8")
    assert "**Source:**" in text and "https://" in text
