"""Published open designs, transcribed into edakit projects (tests/open_designs/<name>/, maker-coverage FT-21): what
edakit check and edakit sim find on each – exactly the findings its findings.toml lists, every one judged there: real
(a point of the design), lacks (a fact the transcription or the datasheets lack), criterion (edakit's yardstick, not
the design's) or known gap (edakit judges it wrong, not fixed yet, with the reason). edakit's false alarms the designs
showed are fixed and listed there under [[fixed]] (tests/test_open_design_fixes.py holds them). The designs stay as
published; a finding that appears or goes is a change in edakit to look at, not to wave through.

  corne-cherry-left                foostan's Corne keyboard v4, left half (corne-cherry hotswap), KiCad schematic
                                   pcbs/common/left.kicad_sch at commit 63366fb of https://github.com/foostan/crkbd,
                                   CC BY 4.0 – an RP2040 board with USB-C, 23 keys each on its own GPIO (no matrix), a
                                   chain of 23 SK6812MINI-E one diode below 5 V, a TRS link to the other half
  corne-cherry-v3-left             foostan's Corne Cherry v3, left half, KiCad schematic corne-cherry/pcb/
                                   corne-cherry.kicad_sch at commit b473521 of https://github.com/foostan/crkbd, MIT – a
                                   Pro Micro, 21 keys in a 4 × 6 matrix with a diode per key, 27 RGB LEDs, a TRRS link
  esp32-devkitc-v4                Espressif ESP32-DevKitC V4, schematic Rev V4 (2017-12-06),
                                   https://dl.espressif.com/dl/schematics/esp32_devkitc_v4-sch.pdf – no licence stated;
                                   the circuit's facts transcribed: usb, radio and power in one board
  sparkfun-logic-level-converter   SparkFun Logic Level Converter Bi-Directional, Rev V01 (2013-09-26), CC BY-SA 3.0,
                                   https://cdn.sparkfun.com/datasheets/BreakoutBoards/Logic_Level_Bidirectional.pdf –
                                   four BSS138 channels, both directions simulated

Each design's README names its source and licence, what was transcribed and the parts that stand in for unnamed ones.
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
    assert len(NAMES) >= 3


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
    assert "**Source:**" in text and "https://" in text and "licence" in text.lower()


def test_the_corne_attributes_its_source_and_names_its_changes():
    """CC BY 4.0 asks for the attribution and a note of changes; the repository and its commit are named."""
    text = " ".join((DESIGNS / "corne-cherry-left" / "README.md").read_text(encoding="utf-8").split())
    assert "CC BY 4.0" in text and "Changes:" in text and "foostan" in text and "63366fb" in text


def test_the_corne_wires_every_key_to_its_own_gpio_not_a_matrix():
    """The Corne v4 has no key matrix: each key goes from one RP2040 GPIO to GND (QMK's direct pins) – no net is a
    matrix row or column, no diode sits at a key, and edakit's matrix rules find nothing to judge. FT-21's key matrix
    is the v3's (corne-cherry-v3-left)."""
    cfg = config.load(DESIGNS / "corne-cherry-left" / "edakit.toml")
    d = Design.from_config(cfg)
    keys = sorted(des for des, c in d.comps.items() if c["type"] == "button" and not des.startswith("SMDSW"))
    assert len(keys) == 23
    gpios = set()
    for des in keys:
        nets = {d.pin_net[f"{des}.{p}"] for p in d.comps[des]["pins"]}
        assert "GND" in nets and len(nets) == 2, des
        (line,) = nets - {"GND"}
        mcu = [r for r in d.nets[line]["pins"] if r.startswith("U1.")]
        assert len(d.nets[line]["pins"]) == 2 and len(mcu) == 1, des
        gpios.add(mcu[0])
    assert len(gpios) == 23
    assert not any("matrix" in n for n in d.nets.values())
    assert not [f for f in check(d, cfg).findings if f.grade == "matrix"]


# --- the Corne v3: a key matrix ---------------------------------------------------------------------------------------
V3 = "corne-cherry-v3-left"


def v3_graph(tmp_path, change=None):
    """The Corne v3 copied to tmp_path, its graph changed by change(graph) – the Design and the project's config."""
    cfg = copy(V3, tmp_path)
    if change:
        f = tmp_path / V3 / "hardware" / "graph.json"
        g = json.loads(f.read_text(encoding="utf-8"))
        change(g["graph"])
        f.write_text(json.dumps(g, indent=1), encoding="utf-8")
        cfg = config.load(tmp_path / V3 / "edakit.toml")
    return Design.from_config(cfg), cfg


def net(g, name):
    return next(n for n in g["nets"] if n["name"] == name)


def matrix_findings(d, cfg):
    return sorted((f.code, f.place) for f in check(d, cfg).findings if f.grade == "matrix")


def test_the_corne_v3_matrix_is_a_diode_per_key_cathodes_to_the_rows(tmp_path):
    """21 keys, each from a column through its own diode to a row, the cathode at the row (QMK COL2ROW); rows and
    columns on the Pro Micro's pins. edakit's matrix rules find it well formed."""
    d, cfg = v3_graph(tmp_path)
    rows = {n for n, x in d.nets.items() if x.get("matrix") == "row"}
    cols = {n for n, x in d.nets.items() if x.get("matrix") == "col"}
    assert (len(rows), len(cols)) == (4, 6)
    keys = sorted(des for des, c in d.comps.items() if des.startswith("SW"))
    assert len(keys) == 21
    for des in keys:
        col, inner = d.pin_net[f"{des}.1"], d.pin_net[f"{des}.2"]
        (dio,) = [r.split(".")[0] for r in d.nets[inner]["pins"] if r.startswith("D")]
        assert col in cols and d.net_of(dio, "anode") == inner and d.net_of(dio, "cathode") in rows, des
    assert all(any(r.startswith("U1.") for r in d.nets[n]["pins"]) for n in rows | cols)
    assert matrix_findings(d, cfg) == []


def test_the_corne_v3_matrix_rules_catch_a_seeded_fault(tmp_path):
    """A key without its diode (SW2 straight on row0) is REQ.missing/matrix; one diode turned round (D1, anode at the
    row) is REQ.forbidden/matrix – the diodes point both ways."""
    def bridge(g):
        g["components"] = [c for c in g["components"] if c["designator"] != "D2"]
        g["nets"] = [n for n in g["nets"] if n["name"] != "D2_A"]
        net(g, "row0")["pins"] = [p for p in net(g, "row0")["pins"] if p != "D2.1"] + ["SW2.2"]
    assert matrix_findings(*v3_graph(tmp_path / "a", bridge)) == [("REQ.missing", "SW2")]

    def turn(g):
        net(g, "row0")["pins"] = [("D1.2" if p == "D1.1" else p) for p in net(g, "row0")["pins"]]
        net(g, "D1_A")["pins"] = [("D1.1" if p == "D1.2" else p) for p in net(g, "D1_A")["pins"]]
    assert matrix_findings(*v3_graph(tmp_path / "b", turn)) == [("REQ.forbidden", "matrix")]


def turn_all(g):
    for i in range(1, 22):
        row = next(n for n in g["nets"] if f"D{i}.1" in n["pins"])
        net(g, row["name"])["pins"] = [(f"D{i}.2" if p == f"D{i}.1" else p) for p in row["pins"]]
        net(g, f"D{i}_A")["pins"] = [(f"D{i}.1" if p == f"D{i}.2" else p) for p in net(g, f"D{i}_A")["pins"]]


def scan(d, cfg, load):
    """The expectations (LIM.v) of one load of the Corne v3's simulation: {(net, result)} over its scenarios."""
    from edakit.sim import run as simrun
    sim = engines.load_sim(cfg)
    sim["loads"] = {load: sim["loads"][load]}
    out = simrun.run_all(d, sim)
    return {(r["item"], r["result"]) for r in out["checks"] if r["check"] == "net voltage (expected in this load)"}


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_the_corne_v3_scan_reads_through_the_diodes_and_ghosts_without_them(tmp_path):
    """The simulation scans the matrix as the firmware does: row0 low with SW1 pressed reads col0 low; with SW1, SW2
    and SW7 pressed while row1 is scanned col1 stays high. All diodes turned round, the static rules stay quiet – they
    hold the diodes to one direction, the firmware's is not in the schematic – but the scan no longer reads SW1;
    without the diodes col1 ghosts low."""
    d, cfg = v3_graph(tmp_path / "as")
    assert scan(d, cfg, "scan_row0_sw1") == {("col0", "pass"), ("col1", "pass")}
    assert scan(d, cfg, "ghost_row1") == {("col0", "pass"), ("col1", "pass")}
    d, cfg = v3_graph(tmp_path / "turned", turn_all)
    assert matrix_findings(d, cfg) == []
    assert ("col0", "fail") in scan(d, cfg, "scan_row0_sw1")

    def no_diodes(g):
        for i in range(1, 22):
            row = next(n for n in g["nets"] if f"D{i}.1" in n["pins"])
            row["pins"] = [p for p in row["pins"] if p != f"D{i}.1"] + [f"SW{i}.2"]
        g["components"] = [c for c in g["components"] if not (c["designator"].startswith("D")
                                                               and c["designator"][1:].isdigit())]
        g["nets"] = [n for n in g["nets"] if not n["name"].endswith("_A")]
    d, cfg = v3_graph(tmp_path / "bare", no_diodes)
    assert ("col1", "fail") in scan(d, cfg, "ghost_row1")
