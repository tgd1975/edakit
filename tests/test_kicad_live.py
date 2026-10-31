"""The KiCad tool chain against a real kicad-cli (KiCad 10): KiCad reads what edakit writes, and its exports are what
the gate's checks read (handbook 16.8). Skipped without kicad-cli, and with a kicad-cli of another major version than
cli.MAJOR (read once per session) – KiCad 9 fails some of them, which says nothing about edakit. The CI job kicad runs
them in KiCad's container with EDAKIT_KICAD_LIVE=required: there a missing kicad-cli or another major fails."""

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

REQUIRED = os.environ.get("EDAKIT_KICAD_LIVE") == "required"      # the CI job kicad: run, never skip

pytestmark = [pytest.mark.kicad,
              pytest.mark.skipif(not (REQUIRED or os.environ.get("KICAD_CLI") or shutil.which("kicad-cli")),
                                 reason="kicad-cli not installed")]


def skip_reason(version, required=REQUIRED):
    """Why the tests do not run against a kicad-cli of this version: None for KiCad cli.MAJOR (or when they are
    required), else the reason."""
    if required or cli.major(version) == cli.MAJOR:
        return None
    return (f"kicad-cli is KiCad {version} – edakit writes for and is tested with KiCad {cli.MAJOR} (cli.MAJOR); the "
            f"CI job kicad runs these tests in KiCad {cli.MAJOR}'s container")


@pytest.fixture(scope="session")
def kicad_version():
    return cli.version()


@pytest.fixture(autouse=True)
def kicad_of_the_major(kicad_version):
    if why := skip_reason(kicad_version):
        pytest.skip(why)


def test_kicad_cli_is_kicad_10(kicad_version):
    assert cli.major(kicad_version) == cli.MAJOR


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
    # the position file of KiCad and the parts as edakit reads them from the PCB agree (SYNC.cpl)
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


def test_kicad_odb_is_read_and_equals_the_runs_files(project):
    """kicad-cli's ODB++ for a maker that takes it (AISLER): edakit's reader takes it, and SYNC.odb finds it equal to
    the Gerber, drill, BOM and CPL files of the same run – layers, holes, profile, parts and nets."""
    from edakit import odb
    from edakit.release import fab
    cfg = kicad_project(project)
    f = project.root / "edakit.toml"
    f.write_text(f.read_text() + '\n[cart]\nmaker = "aisler"\n')
    cfg = project.config()
    board = cfg.board()
    kb.write_parts(cfg, board)
    ks.write(cfg, board)
    out = project.root / "build" / "fab"
    d = out / "main"
    d.mkdir(parents=True)
    kfab.collect(cfg, board, d, verbose=True)
    assert not (d / fab.ODB_ERROR).exists(), (d / fab.ODB_ERROR).read_text()
    assert {c.designator for c in odb.read(d / "odb_main.zip").components} >= set(Design.from_config(cfg).board_comps("main"))
    (d / "jlc_parts.json").write_text("{}")
    rows = [r for r in fab.run(cfg, board, out, offline=True) if r["id"] == "SYNC.odb"]
    bad = [(r["result"], r["check"], r["actual"]) for r in rows if r["result"] not in ("pass", "info")]
    assert rows and not bad, bad


def test_kicad_puts_every_pad_where_edakit_reads_it_also_on_the_bottom(project):
    """The frames (handbook 16.3): a part turned and one mirrored onto the bottom – KiCad's own Gerber copper lies at
    every pad edakit reads from the file, on the pad's side, and its position file turns the parts on the bottom as
    the PCB does."""
    cfg = kicad_project(project, {"R2": '{ x = 40.0, y = 30.0, rot = 90, side = "bottom", auto = true }',
                                  "D1": '{ x = 75.0, y = 12.0, rot = 180, side = "bottom" }',
                                  "SW1": '{ x = 80, y = 25, rot = 270, side = "top" }'})
    board = cfg.board()
    kb.write_parts(cfg, board)
    ks.write(cfg, board)
    d = project.root / "build" / "fab" / "main"
    d.mkdir(parents=True)
    kfab.collect(cfg, board, d, verbose=True)
    cu = gerber.Copper(d / "gerber", Design.from_config(cfg).pin_net)
    missing = []
    for c in kb.pcb_json(cfg, board)["components"]:
        for p in c["pads"]:
            sides = "TB" if p["Layer"] == kb.MULTI else ("B" if p["Layer"] == 2 else "T")
            x, y = p["X"] / kb.MIL_PER_MM, p["Y"] / kb.MIL_PER_MM
            missing += [f"{c['designator']}.{p['PadNumber']} {k}" for k in sides if not cu.labels_at(k, x, y, 0.05)]
    assert missing == []
    # SYNC.cpl on the bottom: a turn read from below (-a) would leave D1 at 180, one of 180-a R2 at 90 – the two together
    cpl = {r["Designator"]: r for r in kfab.read_cpl(d / "cpl_kicad.csv")}
    assert [(cpl[r]["Layer"], float(cpl[r]["Rotation"])) for r in ("R2", "D1")] == [("B", 90), ("B", 180)]


@pytest.mark.freerouting
def test_route_all_on_kicad_leaves_only_what_freerouting_left_open(project, capsys, monkeypatch):
    """route all on the KiCad project: Freerouting, the SES into the file, the zones filled by kicad-cli, KiCad's
    DRC without findings; the file KiCad saved written again; then stages L and F on KiCad's export."""
    import json

    from edakit import cli as edakit_cli
    from edakit.release import fab
    cfg = kicad_project(project)
    board = cfg.board()

    def run(*args):
        try:
            return edakit_cli.main([*args, "--config", str(project.root / "edakit.toml")])
        except SystemExit as e:              # route all stops with a message when nets stay open
            return e.code
    assert run("pcb", "apply", "--no-scripts") == 0
    assert run("schematic", "create") == 0
    code = run("route", "all", "--no-scripts")
    print(capsys.readouterr().out[-4000:])
    found = json.loads((cfg.artifacts / "route" / "main_drc.json").read_text()) if code in (0, 2) else []
    assert [f for f in found if f["ruleName"] != "unconnected"] == [], found
    # the file KiCad saved with the filled zones, written again by edakit: pcb apply and silk apply keep the copper
    assert run("pcb", "apply", "--no-scripts") == 0
    assert run("silk", "apply", "--no-scripts") in (0, 2)
    print(capsys.readouterr().out[-3000:])
    again = cli.drc(kb.paths(cfg, board)["pcb"], project.root / "drc_again.json", verbose=True)
    assert [f for f in again if f["ruleName"] != "unconnected"] == [], again
    assert len([f for f in again if f["ruleName"] == "unconnected"]) == \
        len([f for f in found if f["ruleName"] == "unconnected"])
    # stages L and F on what KiCad exports – JLCPCB's catalogue (PARTS.stock) and the simulation (GEO.width) left out, the rest
    # as the gate runs it, after pcb dump (SYNC.plan)
    assert run("pcb", "dump", "--no-scripts") == 0
    monkeypatch.setattr(fab, "fetch_jlc", lambda bom, d: (d / "jlc_parts.json").write_text("{}"))
    rows = fab.run(cfg, board, project.root / "build" / "fab")
    print("\n".join(f"{r['id']:<5} {r['result']:<4} {r['check']}: {r['actual']}"[:220] for r in rows))
    for cid in ("SYNC.pcb", "GEO.copper", "GEO.drc", "SYNC.footprint", "GEO.hole", "GEO.spacing", "GEO.ring",
                "GEO.pour", "SYNC.bom", "SYNC.cpl", "FILES.set"):
        bad = [r for r in rows if r["id"] == cid and r["result"] == "fail"]
        assert not bad, bad
    # SYNC.plan: every part has a row in [place] (L-20 of before); the plan's own row is the test footprints' (below)
    assert [r["result"] for r in rows if r["id"] == "SYNC.plan" and r["check"].startswith("every part of the board")] \
        == ["pass"]
    # SYNC.plan: every part where the plan puts it – the plan's own check is the test footprints' (pads beyond their box)
    assert [r["result"] for r in rows if r["id"] == "SYNC.plan" and r["check"].startswith("fixed parts")] == ["pass"]
