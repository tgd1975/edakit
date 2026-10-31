"""Stages L and F on KiCad (handbook 16.6): KiCad's Gerber and drill files read, renamed and split as the checks know
them, the probe file, BOM and CPL from kicad-cli's exports – and `edakit fab` with a kicad-cli that is faked."""

import json
import stat
import sys
import textwrap
import zipfile
from pathlib import Path

import pytest
from test_kicad import kicad_project

from edakit import gerber
from edakit.release import fab
from edakit.toolchain.kicad import board as kb
from edakit.toolchain.kicad import cli
from edakit.toolchain.kicad import fab as kfab

ROUNDRECT = """%AMRoundRect*
0 Rectangle with rounded corners*
0 $1 Rounding radius*
0 $2 $3 $4 $5 $6 $7 $8 $9 X,Y pos of 4 corners*
4,1,4,$2,$3,$4,$5,$6,$7,$8,$9,$2,$3,0*
1,1,$1+$1,$2,$3*
1,1,$1+$1,$4,$5*
1,1,$1+$1,$6,$7*
1,1,$1+$1,$8,$9*
20,1,$1+$1,$2,$3,$4,$5,0*
20,1,$1+$1,$4,$5,$6,$7,0*
20,1,$1+$1,$6,$7,$8,$9,0*
20,1,$1+$1,$8,$9,$2,$3,0*%"""

KICAD_GTL = f"""%TF.GenerationSoftware,KiCad,Pcbnew,10.0.6*%
%TF.FileFunction,Copper,L1,Top*%
%FSLAX46Y46*%
G04 Gerber Fmt 4.6, Leading zero omitted, Abs format (unit mm)*
%MOMM*%
%LPD*%
G01*
G04 Aperture macros list*
{ROUNDRECT}
G04 Aperture macros list end*
%TA.AperFunction,SMDPad,CuDef*%
%ADD10RoundRect,0.250000X-0.450000X-0.350000X0.450000X-0.350000X0.450000X0.350000X-0.450000X0.350000X0*%
%ADD11P,1.000000X4X45.000000*%
%TD*%
%TA.AperFunction,Conductor*%
%ADD12C,0.250000*%
%TD*%
G04 APERTURE END LIST*
D10*
%TO.P,R1,1*%
X10000000Y5000000D03*
D11*
X20000000Y5000000D03*
D12*
%TO.N,GND*%
X10000000Y5000000D02*
X20000000Y5000000D01*
%TD*%
M02*
"""

KICAD_PTH = """M48
; DRILL file {KiCad 10.0.6} date 2026-10-30
; FORMAT={-:-/ absolute / metric / decimal}
; #@! TF.GenerationSoftware,Kicad,Pcbnew,10.0.6
; #@! TF.FileFunction,Plated,1,2,PTH
FMAT,2
METRIC
; #@! TA.AperFunction,Plated,PTH,ViaDrill
T1C0.300
; #@! TA.AperFunction,Plated,PTH,ComponentDrill
T2C1.000
%
G90
G05
T1
X10.0Y5.0
X12.0Y5.0
T2
X20.0Y5.0G85X22.0Y5.0
M30
"""


def test_kicad_macros_and_polygons_become_regions(tmp_path):
    f = tmp_path / "board-F_Cu.gbr"
    f.write_text(KICAD_GTL)
    ops = gerber.parse_gerber(f)
    kinds = [k for k, _ in ops]
    assert kinds == ["region", "region", "draw"]
    pad = gerber.shape([ops[0]])
    assert pad.area == pytest.approx(1.4 * 1.2 - 4 * (0.25 ** 2 - 3.14159 * 0.25 ** 2 / 4), rel=0.01)
    assert pad.bounds == pytest.approx((9.3, 4.4, 10.7, 5.6), abs=0.01)
    diamond = gerber.shape([ops[1]])                  # a square turned by 45°, its corners 0.5 mm from the centre
    assert diamond.area == pytest.approx(0.5, rel=0.01)


def test_easyeda_roundrect_stays_as_it_was(tmp_path):
    f = tmp_path / gerber.FILES["top_mask"]
    f.write_text("%FSLAX45Y45*%\n%MOMM*%\n%ADD10RoundRect,0.2X-0.5X-0.3X0.5X-0.3X0.5X0.3X-0.5X0.3*%\nD10*\n"
                 "X100000Y100000D03*\nM02*\n")
    assert gerber.parse_gerber(f) == [("flash", (("RR", 1.2, 0.8), 1.0, 1.0))]


def test_kicad_drills_parse_and_split_into_component_holes_and_vias(tmp_path):
    parts, vias = kfab.split_vias(KICAD_PTH, [])
    assert "T1C0.300" in vias and "T1C0.300" not in parts and "T2C1.000" in parts
    for text, want in ((vias, [(10.0, 5.0, 10.0, 5.0, 0.3), (12.0, 5.0, 12.0, 5.0, 0.3)]),
                       (parts, [(20.0, 5.0, 22.0, 5.0, 1.0)])):
        f = tmp_path / "x.drl"
        f.write_text(text)
        assert gerber.parse_drills(f) == want


def test_without_x2_comments_the_vias_of_the_pcb_decide():
    plain = KICAD_PTH.replace("; #@! TA.AperFunction,Plated,PTH,ViaDrill\n", "").replace(
        "; #@! TA.AperFunction,Plated,PTH,ComponentDrill\n", "")
    mil = 1000 / 25.4
    parts, vias = kfab.split_vias(plain, [(10.0 * mil, 5.0 * mil, 24, "GND")])
    assert "X10.0Y5.0" in vias and "X12.0Y5.0" in parts and "X10.0Y5.0" not in parts


def test_normalize_names_kicad_files_as_the_checks_know_them(tmp_path):
    for layer in ("F_Cu", "B_Cu", "F_Silkscreen", "B_Silkscreen", "F_Mask", "B_Mask", "Edge_Cuts", "F_Paste"):
        (tmp_path / f"main-{layer}.gbr").write_text(KICAD_GTL)
    (tmp_path / "main-PTH.drl").write_text(KICAD_PTH)
    (tmp_path / "main-NPTH.drl").write_text("M48\nMETRIC\nT1C3.200\n%\nT1\nX3.5Y3.5\nM30\n")
    out = kfab.normalize(tmp_path, [])
    for key in ("top", "bottom", "top_silk", "bottom_silk", "top_mask", "bottom_mask", "outline", "pth", "vias",
                "npth"):
        assert gerber.FILES[key] in out, key
    assert "Gerber_TopPasteMaskLayer.GTP" in out


def test_probe_bom_and_cpl_in_the_form_of_easyeda():
    data = {"components": [{"designator": "R1", "pads": [{"PadNumber": "1", "X": 100, "Y": 50, "Net": "A", "Layer": 1,
                                                          "tht": False}]},
                           {"designator": "J1", "pads": [{"PadNumber": "1", "X": 300, "Y": 50, "Net": "B",
                                                          "Layer": 12, "tht": True}]}]}
    p = kfab.probe(data)["pins"]
    rows = [dict(zip(p["fields"], r)) for r in p["rows"]]
    assert rows[0] == {"PIN_NAME": "R1_1", "PIN_X": 100, "PIN_Y": 50, "NET_NAME": "A", "PIN_TYPE": "SMD", "LAYER": "T",
                       "PAD_SIZEX": 20, "PAD_SIZEY": 20}
    assert rows[1]["PIN_TYPE"] == "THT"
    b = kfab.bom({"R1": {"LCSC": "C17414", "value": "10k"}, "R2": {"LCSC": "C17414", "value": "10k"},
                  "J1": {"LCSC": "C131337", "value": "", "exclude_from_bom": ""}})
    assert b == [{"lcsc": "C17414", "value": "10k", "reference": "R1, R2", "quantity": 2}]


def test_netlist_of_kicad_is_read_with_its_fields():
    text = textwrap.dedent("""\
        (export (version "E")
          (components
            (comp (ref "R1") (value "10k") (footprint "edakit:R0805")
              (fields (field (name "Footprint") "edakit:R0805") (field (name "LCSC") "C17414")))
            (comp (ref "J1") (value "PH") (footprint "edakit:CONN") (property (name "exclude_from_bom"))))
          (nets
            (net (code "1") (name "/VIN") (node (ref "J1") (pin "1")))
            (net (code "2") (name "GND") (node (ref "R1") (pin "2")) (node (ref "J1") (pin "2")))))""")
    nets, comps = cli.read_netlist(text)
    assert nets == {"VIN": ["J1.1"], "GND": ["R1.2", "J1.2"]}
    assert comps["R1"]["LCSC"] == "C17414" and "exclude_from_bom" in comps["J1"]


def test_drc_report_becomes_findings_without_ignored_ones():
    report = {"violations": [{"type": "clearance", "severity": "error", "description": "Clearance violation",
                              "items": [{"description": "Track [GND]"}]},
                             {"type": "silk_overlap", "severity": "ignore", "items": []},
                             {"type": "hole_clearance", "severity": "warning", "excluded": True, "items": []}],
              "unconnected_items": [{"type": "unconnected_items", "severity": "error", "description": "Missing",
                                     "items": [{"description": "Pad 1 [VIN] of J1"}]}],
              "schematic_parity": [{"type": "missing_footprint", "severity": "warning", "description": "R9",
                                    "items": []}]}
    found = cli.findings(report)
    assert [(f["errorType"], f["ruleName"]) for f in found] == [("clearance", "violation"),
                                                                 ("unconnected_items", "unconnected"),
                                                                 ("missing_footprint", "parity")]


# --- edakit fab with a kicad-cli that is faked ------------------------------------------------------------------------

FAKE = '''#!{python}
"""A kicad-cli for the tests: the reports and files of a board without findings."""
import csv, json, sys
from pathlib import Path
sys.path.insert(0, {root!r})
args = sys.argv[1:]
out = Path(args[args.index("--output") + 1]) if "--output" in args else None
if args[:1] == ["version"]:
    print("10.0.6")
elif args[:2] == ["pcb", "drc"]:
    out.write_text(json.dumps({{"violations": [], "unconnected_items": [], "schematic_parity": []}}))
elif args[:3] == ["pcb", "export", "gerbers"]:
    for layer in ("F_Cu", "B_Cu", "F_Silkscreen", "B_Silkscreen", "F_Mask", "B_Mask", "Edge_Cuts", "F_Paste",
                  "B_Paste"):
        (out / f"main-{{layer}}.gbr").write_text("G04 KiCad*\\n%FSLAX46Y46*%\\n%MOMM*%\\nM02*\\n")
elif args[:3] == ["pcb", "export", "drill"]:
    (out / "main-PTH.drl").write_text("M48\\nMETRIC\\n%\\nM30\\n")
    (out / "main-NPTH.drl").write_text("M48\\nMETRIC\\n%\\nM30\\n")
elif args[:3] == ["pcb", "export", "pos"]:
    from edakit.toolchain.kicad import sexp
    root = sexp.loads(Path(args[-1]).read_text())
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"])
        for fp in sexp.find(root, "footprint"):
            ref = next(c[2] for c in sexp.find(fp, "property") if c[1] == "Reference")
            if ref.startswith("TH"):
                continue
            x, y, *r = sexp.floats(fp, "at")
            w.writerow([ref, "", "", x, -y, (r or [0])[0], "bottom" if sexp.value(fp, "layer") == "B.Cu" else "top"])
elif args[:2] == ["sch", "erc"]:
    out.write_text(json.dumps({{"sheets": [{{"violations": []}}]}}))
elif args[:3] == ["sch", "export", "netlist"]:
    from edakit import config
    from edakit.design import Design
    root = Path(args[-1]).resolve()
    while not (root / "edakit.toml").exists():
        root = root.parent
    cfg = config.load(root / "edakit.toml")
    design = Design.from_config(cfg)
    board = Path(args[-1]).stem
    comps = " ".join(f'(comp (ref "{{r}}") (value "v") (fields (field (name "LCSC") "{{c.get('lcsc', '')}}")))'
                     for r, c in design.board_comps(board).items())
    nets = " ".join(f'(net (code "{{k}}") (name "/{{n}}") ' + " ".join(
        f'(node (ref "{{q.split(".")[0]}}") (pin "{{q.split(".")[1]}}"))' for q in pins) + ")"
        for k, (n, pins) in enumerate(design.board_nets(board).items(), 1))
    out.write_text(f"(export (version \\"E\\") (components {{comps}}) (nets {{nets}}))")
elif args[:3] == ["pcb", "export", "odb"]:
    import os, zipfile
    if os.environ.get("FAKE_ODB_FAIL"):
        print("ODB++ export failed", file=sys.stderr)
        sys.exit(1)
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("main/matrix/matrix", "")
elif args[:3] in (["sch", "export", "pdf"], ["pcb", "export", "pdf"]):
    out.write_bytes(b"%PDF-1.4 fake")
else:
    print("fake kicad-cli: " + " ".join(args), file=sys.stderr)
    sys.exit(1)
'''


@pytest.fixture
def fake_cli(tmp_path, monkeypatch):
    f = tmp_path / "kicad-cli"
    f.write_text(FAKE.format(python=sys.executable, root=str(Path(__file__).parents[1])))
    f.chmod(f.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("KICAD_CLI", str(f))
    return f


def test_version_of_the_fake(fake_cli):
    assert cli.version() == "10.0.6"


@pytest.mark.parametrize("text, major", [("10.0.6", 10), ("9.0.8", 9), ("10.0.6-1~ubuntu24.04.1", 10),
                                         ("11.0", 11), ("no version", None)])
def test_the_major_of_kicad_cli(text, major):
    assert cli.major(text) == major


def test_the_live_tests_skip_on_another_major(fake_cli):
    """tests/test_kicad_live.py runs against kicad-cli of cli.MAJOR only (walkthrough-gaps B8: KiCad 9.0.8 failed two
    of them, a red local run that is no regression); with EDAKIT_KICAD_LIVE=required – the CI job kicad – it runs
    against any, and a wrong container fails instead of being skipped."""
    import test_kicad_live as live
    assert live.skip_reason(cli.version()) is None                           # the fake is KiCad 10
    assert live.skip_reason("9.0.8") == ("kicad-cli is KiCad 9.0.8 – edakit writes for and is tested with KiCad 10 "
                                         "(cli.MAJOR); the CI job kicad runs these tests in KiCad 10's container")
    assert live.skip_reason("9.0.8", required=True) is None


def test_fab_collects_the_files_of_stages_l_and_f_from_kicad(project, fake_cli):
    cfg = kicad_project(project)
    board = cfg.board()
    kb.write_parts(cfg, board)
    d = project.root / "build" / "fab" / "main"
    d.mkdir(parents=True)
    kfab.collect(cfg, board, d)
    for name in ("pcb.json", "drc.json", "gerber_main.zip", "cpl_kicad.csv", "bom_kicad.json"):
        assert (d / name).exists(), name
    assert not gerber.missing(d / "gerber", *gerber.REQUIRED)
    with zipfile.ZipFile(d / "gerber_main.zip") as z:
        assert gerber.FILES["probe"] not in z.namelist() and gerber.FILES["top"] in z.namelist()
    (d / "jlc_parts.json").write_text(json.dumps({}))
    rows = fab.Rows()
    from edakit.design import Design
    fab.check_fab(cfg, board, Design.from_config(cfg), d, rows)
    f1 = next(r for r in rows if r["id"] == "SYNC.bom")
    assert f1["result"] == "pass" and "KiCad" in f1["check"], f1
    f3 = next(r for r in rows if r["id"] == "SYNC.cpl")
    assert f3["result"] == "pass", f3


def with_cart(project, cart):
    f = project.root / "edakit.toml"
    f.write_text(f.read_text() + "\n" + cart + "\n")
    return project.config()


def test_fab_exports_odb_from_kicad_for_a_maker_that_takes_it(project, fake_cli, monkeypatch):
    """A KiCad project with AISLER among its makers gets odb_<board>.zip from kicad-cli pcb export odb – SYNC.odb then
    checks it as it checks EasyEDA's; a failed export leaves its reason for SYNC.odb, no such maker no ODB++."""
    kicad_project(project)
    cfg = with_cart(project, '[cart]\nmaker = "aisler"')
    board = cfg.board()
    kb.write_parts(cfg, board)
    d = project.root / "build" / "fab" / "main"
    d.mkdir(parents=True)
    kfab.collect(cfg, board, d)
    with zipfile.ZipFile(d / "odb_main.zip") as z:
        assert "main/matrix/matrix" in z.namelist()
    assert not (d / fab.ODB_ERROR).exists()
    monkeypatch.setenv("FAKE_ODB_FAIL", "1")
    kfab.collect(cfg, board, d)
    assert not (d / "odb_main.zip").exists()
    assert (d / fab.ODB_ERROR).read_text().startswith("kicad-cli pcb export odb: exit 1 – ODB++ export failed")
    rows = fab.Rows()
    from edakit.design import Design
    fab.check_odb(cfg, board, Design.from_config(cfg), d, rows)
    assert [(r["result"], r["actual"]) for r in rows] == [
        ("fail", "odb_main.zip: kicad-cli pcb export odb: exit 1 – ODB++ export failed")]


def test_no_odb_from_kicad_without_a_maker_that_takes_it(project, fake_cli, monkeypatch):
    kicad_project(project)
    cfg = with_cart(project, '[cart]\nmaker = "jlcpcb"')
    board = cfg.board()
    kb.write_parts(cfg, board)
    d = project.root / "build" / "fab" / "main"
    d.mkdir(parents=True)
    (d / "odb_main.zip").write_bytes(b"stale")
    monkeypatch.setenv("FAKE_ODB_FAIL", "1")             # not called: the fake would leave odb_error.txt
    kfab.collect(cfg, board, d)
    assert not (d / "odb_main.zip").exists() and not (d / fab.ODB_ERROR).exists()


def run_cli(project, *args):
    from edakit import cli as edakit_cli
    return edakit_cli.main([*args, "--config", str(project.root / "edakit.toml")])


def test_the_commands_run_on_kicad(project, fake_cli, capsys):
    kicad_project(project)
    assert run_cli(project, "pcb", "parts") == 2                      # no PCB yet: every part is missing
    assert run_cli(project, "pcb", "apply", "--no-scripts") == 0
    assert run_cli(project, "pcb", "parts") == 0 and run_cli(project, "pcb", "nets") == 0
    assert run_cli(project, "pcb", "dump", "--no-scripts") == 0
    assert (project.root / "hardware" / "boards" / "main.geometry.json").exists()
    assert run_cli(project, "pcb", "autolayout", "--no-scripts") == 1
    assert "pcb place --rest" in capsys.readouterr().err
    assert run_cli(project, "schematic", "create") == 0
    assert run_cli(project, "schematic", "check") == 0
    out = capsys.readouterr().out
    assert "schematic = graph: yes" in out


def test_silk_apply_places_the_designators_into_the_kicad_pcb(project, fake_cli):
    from edakit.toolchain.kicad import silk as ksilk
    cfg = kicad_project(project)
    board = cfg.board()
    kb.write_parts(cfg, board)
    assert ksilk.apply(cfg, board) in (0, 2)
    pcb = kb.load(cfg, board)
    shown = {ref for ref, fp in kb.parts(pcb)
             if not any(c[0] == "hide" for c in next(c for c in kb.find(fp, "property") if c[1] == "Reference")
                        if isinstance(c, list))}
    assert len(shown) >= len(kb.parts(pcb)) // 2                     # most designators found a spot
    assert (cfg.artifacts / "silk_footprints_main").exists()


def test_export_on_kicad_keeps_a_copy_of_the_project(project, fake_cli):
    kicad_project(project)
    assert run_cli(project, "pcb", "apply", "--no-scripts") == 0
    assert run_cli(project, "schematic", "create") == 0
    assert run_cli(project, "export") == 0
    d = project.root / "build" / "edakit" / "export" / "main"
    for name in ("kicad_main.zip", "gerber_main.zip", "cpl_main.csv", "pcb_main.pdf", "schematic_main.pdf",
                 "nets_main.txt", "bom_main.json"):
        assert (d / name).exists(), name
    with zipfile.ZipFile(d / "kicad_main.zip") as z:
        assert "main/main.kicad_pcb" in z.namelist() and "main/main.kicad_sch" in z.namelist()
    assert not (d / "odb_main.zip").exists()                     # no maker of [cart] makers takes ODB++


def test_export_on_kicad_writes_odb_for_a_maker_that_takes_it(project, fake_cli):
    kicad_project(project)
    with_cart(project, '[cart]\nmakers = ["jlcpcb", "aisler"]')
    assert run_cli(project, "pcb", "apply", "--no-scripts") == 0
    assert run_cli(project, "export") == 0
    assert (project.root / "build" / "edakit" / "export" / "main" / "odb_main.zip").exists()


def test_doctor_asks_kicad_cli_and_not_the_bridge(project, fake_cli, capsys):
    kicad_project(project)
    run_cli(project, "doctor", "--offline")
    out = capsys.readouterr().out
    assert "KiCad 10.0.6 (kicad-cli" in out and "Node" not in out and "bridge port" not in out


def test_a_session_learns_the_tool_chain(project):
    from edakit import agreements
    kicad_project(project)
    out = agreements.hook({"cwd": str(project.root)})
    assert "Tool chain: KiCad" in out["hookSpecificOutput"]["additionalContext"]


def test_the_gates_stage_s_reads_the_kicad_schematic(project, fake_cli):
    from edakit.release import gate
    cfg = kicad_project(project)
    assert run_cli(project, "schematic", "create") == 0
    out = project.root / "build" / "release" / "run"
    out.mkdir(parents=True)
    rows = gate.stage_schematic(cfg, out)
    assert rows == [{"stage": "S", "id": "SYNC.schematic", "item": "main.kicad_sch", "check": "schematic = graph",
                     "result": "pass"}]
