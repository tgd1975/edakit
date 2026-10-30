"""The KiCad tool chain against a real kicad-cli (KiCad 10): KiCad reads what edakit writes, and its exports are what
the gate's checks read (handbook 16.8). Skipped without kicad-cli; the CI job kicad runs them in KiCad's container."""

import os
import shutil

import pytest
from test_kicad import kicad_project

from edakit import gerber
from edakit.design import Design
from edakit.toolchain.kicad import board as kb
from edakit.toolchain.kicad import cli
from edakit.toolchain.kicad import fab as kfab
from edakit.toolchain.kicad import schematic as ks

pytestmark = [pytest.mark.kicad,
              pytest.mark.skipif(not (os.environ.get("KICAD_CLI") or shutil.which("kicad-cli")),
                                 reason="kicad-cli not installed")]


def test_kicad_cli_is_kicad_10():
    assert cli.version().split(".")[0] == str(cli.MAJOR)


def test_kicad_reads_the_schematic_and_its_netlist_is_the_graph(project):
    cfg = kicad_project(project)
    board = cfg.board()
    kb.write_parts(cfg, board)
    path, problems = ks.write(cfg, board)
    assert problems == []
    rep = ks.check(cfg, board, verbose=True)
    assert rep.count() == 0, rep.sections


def test_kicad_reads_the_pcb_fills_its_zones_and_finds_only_open_nets(project, tmp_path):
    cfg = kicad_project(project)
    board = cfg.board()
    kb.write_parts(cfg, board)
    ks.write(cfg, board)
    assert kb.write_zones(cfg, board) == 2
    pcb = kb.paths(cfg, board)["pcb"]
    cli.fill_zones(pcb, verbose=True)
    assert any(z for z in kb.load(cfg, board).zones if kb.first(z, "filled_polygon"))
    found = cli.drc(pcb, tmp_path / "drc.json", verbose=True)
    other = [f for f in found if f["ruleName"] not in ("unconnected",)]   # not routed: open nets are expected
    print("\n".join(f"{f['errorType']} ({f['severity']}): {f['description']} {f['items']}" for f in found))
    assert other == [], other


def test_the_exports_are_what_the_checks_read(project):
    cfg = kicad_project(project)
    board = cfg.board()
    kb.write_parts(cfg, board)
    ks.write(cfg, board)
    d = project.root / "build" / "fab" / "main"
    d.mkdir(parents=True)
    kfab.collect(cfg, board, d, verbose=True)
    assert not gerber.missing(d / "gerber", *gerber.REQUIRED), sorted(p.name for p in (d / "gerber").iterdir())
    for key in ("top", "bottom", "top_silk", "bottom_silk", "top_mask", "bottom_mask", "outline"):
        assert gerber.parse_gerber(d / "gerber" / gerber.FILES[key]) is not None, key
    holes = gerber.parse_holes(d / "gerber" / gerber.FILES["npth"])
    assert len(holes) == len(board.tooling)                       # the mounting holes are cut-outs of the outline
    loops = gerber.loops(d / "gerber" / gerber.FILES["outline"])
    assert len(loops) == 1 + len(board.holes)
    # the position file of KiCad and the parts as edakit reads them from the PCB agree (F-3)
    data = kb.pcb_json(cfg, board)
    cpl = {r["Designator"]: r for r in kfab.read_cpl(d / "cpl_kicad.csv")}
    for c in data["components"]:
        if Design.from_config(cfg).comps[c["designator"]].get("bom") is False:
            continue
        r = cpl[c["designator"]]
        assert float(r["Mid X"][:-2]) == pytest.approx(c["x"] / kb.MIL_PER_MM, abs=0.01)
        assert float(r["Mid Y"][:-2]) == pytest.approx(c["y"] / kb.MIL_PER_MM, abs=0.01)
        assert float(r["Rotation"]) == pytest.approx(c["rotation"])
    # the copper of the Gerber files lies where pcb.json has the pads
    cu = gerber.Copper(d / "gerber", Design.from_config(cfg).pin_net)
    assert len(cu.pins) == sum(len(c["pads"]) for c in data["components"])
