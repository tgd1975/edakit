"""Published open designs, transcribed into edakit projects (tests/open_designs/<name>/, maker-coverage FT-21): what
edakit check and edakit sim find on each, every finding judged – a real point of the design, a fact the transcription
lacks, or edakit's own false alarm (then fixed: tests/test_open_design_fixes.py). The designs stay as published; a
finding that changes is a change in edakit to look at, not to wave through.

ESP32-DevKitC V4 (Espressif, schematic Rev V4 of 2017-12-06, https://dl.espressif.com/dl/schematics/esp32_devkitc_v4-sch.pdf,
no licence stated; the circuit's facts transcribed, see its README):

  LIM.v D6               real – the LESD5D5.0's working voltage (VRWM 5.0 V) is below USB's 5.25 V; it breaks down at
                         5.6 V at the earliest, so it leaks more than its datasheet promises, it does not clamp
  LVL.undefined SENSOR_VP, SENSOR_VN, IO34, IO35
                         real, intended – input-only pins without pull resistors (GPIO34–39 have none) that only go to
                         the header: they float until the user's circuit drives them
  LIM.band D2            real, the firmware's – the module's 2412–2484 MHz reach channel 14 (Japan); in the EU the
                         firmware keeps to channels 1–13
  LIM.eirp D2 (2x)       the transcription lacks – the module datasheet states neither its PCB antenna's gain nor the
                         Bluetooth bands
  REQ.value D2.3 (EN)    real – Espressif's own module datasheet recommends 10 kΩ / 1 µF at EN; the DevKitC V4 has
                         100 nF (with SW2's 100 nF, 200 nF) – the short reset delay behind its known boot problems
  REQ.value U1.9 (RSTb)  real, minor – the CP2102N datasheet recommends a 1 kΩ pull-up on RSTb, the DevKitC fits 2 kΩ
  STRUCT.prefix D2       real, naming – the schematic calls the module D2
  sim LIM.i J1           real – with the module at the 0.5 A its datasheet asks the supply for, the board draws 526 mA
                         from a USB 2.0 port that gives 500 mA
  sim LIM.t D3           real – the BAT760 dissipates 0.22 W at 0.5 A; at 500 K/W (its datasheet's minimum pad) its
                         junction reaches 137 °C at 25 °C ambient
  sim SIM.state U2       real – at 4.75 V, after the cable and the Schottky, the AMS1117 (1.1 V dropout) gives 3.07 V,
                         below 3.3 V ± 3 % – still above the module's 3.0 V
  sim SIM.state D1       edakit's criterion – the power LED gets 0.96 mA at the lowest supply and the highest VF, below
                         edakit's 1 mA for an LED that is on; the design's own aim for it is not known

edakit's false alarms on this design, fixed: a TVS held to its working voltage with a rectifier's margin, the AMS1117's
two VOUT pins as two drivers, the CP2102N's RXD pull-up ignored, the auto-program bases taken as floating, header
nets judged as nan in the simulation.
"""

import shutil
from pathlib import Path

import pytest

from helpers import check

from edakit import config, engines
from edakit.design import Design

DESIGNS = Path(__file__).resolve().parent / "open_designs"

FOUND = {
    "esp32-devkitc-v4": {
        ("LIM.v", "", "D6"), ("LVL.undefined", "", "SENSOR_VP"), ("LVL.undefined", "", "SENSOR_VN"),
        ("LVL.undefined", "", "IO34"), ("LVL.undefined", "", "IO35"), ("LIM.band", "firmware", "D2"),
        ("LIM.eirp", "unknown", "D2"), ("REQ.value", "pin", "D2.3 (EN)"), ("REQ.value", "pin", "U1.9 (RSTb)"),
        ("STRUCT.prefix", "", "D2")},
}
SIM_FOUND = {
    "esp32-devkitc-v4": {("LIM.i", "J1"), ("LIM.t", "D3"), ("SIM.state", "U2"), ("SIM.state", "D1")},
}


def copy(name, tmp_path):
    dst = tmp_path / name
    shutil.copytree(DESIGNS / name, dst, ignore=shutil.ignore_patterns("build"))
    return config.load(dst / "edakit.toml")


@pytest.mark.parametrize("name", sorted(FOUND))
def test_what_edakit_check_finds_on_the_published_design(name, tmp_path):
    cfg = copy(name, tmp_path)
    rep = check(Design.from_config(cfg), cfg)
    found = {(f.code, f.grade, f.place) for f in rep.findings if f.severity in ("error", "warning", "pending")}
    assert found == FOUND[name]


@pytest.mark.parametrize("name", sorted(SIM_FOUND))
def test_what_edakit_sim_finds_on_the_published_design(name, tmp_path):
    from edakit.sim import run as simrun
    cfg = copy(name, tmp_path)
    d = Design.from_config(cfg)
    out = simrun.run_all(d, engines.load_sim(cfg))
    failed = {(r["id"], r["item"]) for r in out["checks"] if r["result"] == "fail"}
    assert failed == SIM_FOUND[name]


@pytest.mark.parametrize("name", sorted(FOUND))
def test_every_parts_entry_names_its_datasheet_and_fits_the_schema(name):
    import json
    from edakit import schema
    for f in sorted((DESIGNS / name / "hardware" / "parts").glob("*.json")):
        e = json.loads(f.read_text(encoding="utf-8"))
        assert schema.problems(e) == [], f.name
        assert e.get("sources") and e.get("verified", {}).get("datasheet"), f.name


def test_every_design_cites_its_source():
    for d in sorted(p for p in DESIGNS.iterdir() if p.is_dir()):
        text = (d / "README.md").read_text(encoding="utf-8")
        assert "**Source:**" in text and "https://" in text, d.name
