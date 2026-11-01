"""Ordering step 10 (docs/concepts/done/ordering.md): EasyEDA's ODB++ export for a maker that takes it (AISLER),
read by edakit/odb.py and held by SYNC.odb to the run's Gerber, drill, BOM and CPL files and to the graph. The ODB++
here is written by the test from the export of test_fab_run – the same copper, mask and silkscreen, drill hits, outline,
parts and nets –, so that SYNC.odb passes on it, and each fault is one change of it; EasyEDA's own export of a probe
board (ordering step 0b, 2026-11-01) is in fixtures/makers/aisler/probe_2026-11-01."""

import io
import json
import math
import shutil
import tarfile
import zipfile

import pytest

import test_fab_run as fr
from edakit import gerber, odb
from edakit.release import fab

UM = 1000            # symbols of an MM file are in microns
LAYERS = [("comp_+_top", "COMPONENT", "top"), ("top_silk", "SILK_SCREEN", "top_silk"),
          ("top_mask", "SOLDER_MASK", "top_mask"), ("top", "SIGNAL", "top"), ("bottom", "SIGNAL", "bottom"),
          ("bottom_mask", "SOLDER_MASK", "bottom_mask"), ("bottom_silk", "SILK_SCREEN", "bottom_silk"),
          ("comp_+_bot", "COMPONENT", "bottom"), ("drill", "DRILL", None)]


MPN = {"J1": "B2B-PH-K-S(LF)(SN)", "D1": "SS34", "C2": "CL21A226MAQNNNE"}   # the led-bar entries' mpn


def job_of(ex):
    """The ODB++ job of an export, as data a fault can change: layers {name: [items of test_fab_run's Layer]}, holes
    [(x, y, d, kind)], components [{ref, x, y, rot (clockwise), side, part, pins [(num, x, y, net)]}], the profile."""
    layers = {name: [list(i) for i in ex.gerber[key]] for name, kind, key in LAYERS
              if kind in ("SIGNAL", "SOLDER_MASK", "SILK_SCREEN")}
    vias = set(ex.vias)
    holes = [(x, y, d, "via" if (x, y, d) in vias else "plated") for x, y, d in ex.pth] + \
            [(x, y, d, "non_plated") for x, y, d in ex.npth]
    comps = []
    for c in ex.pcb["components"]:
        ref = c["designator"]
        comps.append({"ref": ref, "x": c["x"] / fr.MIL, "y": c["y"] / fr.MIL, "rot": (360 - c["rotation"]) % 360,
                      "side": "top", "part": fr.LCSC[ref], "props": {"MPN": MPN[ref]},
                      "pins": [(p["PadNumber"], p["X"] / fr.MIL, p["Y"] / fr.MIL, p["Net"]) for p in c["pads"]]})
    return {"layers": layers, "holes": holes, "components": comps,
            "profile": [(0, 0), (30, 0), (30, 20), (0, 20), (0, 0)], "drop": set()}


def features(items):
    syms, body = {}, []

    def sym(name):
        return syms.setdefault(name, len(syms))
    for item in items:
        if item[0] == "flash":
            (k, a, b), x, y = item[1], item[2], item[3]
            name = f"r{a * UM:g}" if k == "C" else f"rect{a * UM:g}x{b * UM:g}"
            body.append(f"P {x:.6f} {y:.6f} {sym(name)} P 0 0")
        else:
            _, w, pts, _ = item
            n = sym(f"r{w * UM:g}")
            body += [f"L {a[0]:.6f} {a[1]:.6f} {b[0]:.6f} {b[1]:.6f} {n} P 0" for a, b in zip(pts, pts[1:])]
    return "\n".join(["UNITS=MM", *(f"${n} {name}" for name, n in syms.items()), *body]) + "\n"


def write(job, path, tgz=False):
    """The job as an ODB++ archive: matrix, misc/info, the step pcb with its profile, layers, components, nets."""
    files = {}
    rows = [lay for lay in LAYERS if lay[0] not in job["drop"]]
    files["matrix/matrix"] = "STEP {\n   COL=1\n   NAME=PCB\n}\n" + "".join(
        f"LAYER {{\n   ROW={i}\n   CONTEXT=BOARD\n   TYPE={kind}\n   NAME={name.upper()}\n   POLARITY=POSITIVE\n}}\n"
        for i, (name, kind, _) in enumerate(rows, 1))
    files["misc/info"] = "UNITS=MM\n"
    base = "steps/pcb"
    p = job["profile"]
    files[f"{base}/profile"] = "UNITS=MM\nS P 0\nOB {:.6f} {:.6f} I\n".format(*p[0]) + "".join(
        f"OS {x:.6f} {y:.6f}\n" for x, y in p[1:]) + "OE\nSE\n"
    for name, items in job["layers"].items():
        if name not in job["drop"]:
            files[f"{base}/layers/{name}/features"] = features(items)
    drill = ["UNITS=MM", "@0 .drill"]
    syms = {}
    for x, y, d, kind in job["holes"]:
        n = syms.setdefault(f"r{d * UM:g}", len(syms))
        drill.append(f"P {x:.6f} {y:.6f} {n} P 0 0;0={ {'plated': 0, 'non_plated': 1, 'via': 2}[kind]}")
    drill[2:2] = [f"${n} {name}" for name, n in syms.items()]
    files[f"{base}/layers/drill/features"] = "\n".join(drill) + "\n"
    nets = sorted({pin[3] for c in job["components"] for pin in c["pins"]})
    files[f"{base}/eda/data"] = "UNITS=MM\n" + "".join(f"NET {n}\n" for n in nets)
    for side, layer in (("top", "comp_+_top"), ("bottom", "comp_+_bot")):
        lines = ["UNITS=MM", "@0 .comp_mount_type", "@1 .no_pop"]
        for i, c in enumerate(cp for cp in job["components"] if cp["side"] == side):
            lines += [f"# CMP {i}", f"CMP {i} {c['x']:.6f} {c['y']:.6f} {c['rot']:g} {'M' if side == 'bottom' else 'N'} "
                                     f"{c['ref']} {c['part']}" + (f" ;{c['attrs']}" if c.get("attrs") else ""),
                      f"PRP LCSC '{c['part']}'"]
            lines += [f"PRP {k} '{v}'" for k, v in c.get("props", {}).items()]
            lines += [f"TOP {k} {x:.6f} {y:.6f} 0 N {nets.index(net)} 0 {num}"
                      for k, (num, x, y, net) in enumerate(c["pins"])]
        files[f"{base}/layers/{layer}/components"] = "\n".join(lines) + "\n"
    if tgz:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as t:
            for name, text in files.items():
                data = text.encode()
                info = tarfile.TarInfo(f"led-bar/{name}")
                info.size = len(data)
                t.addfile(info, io.BytesIO(data))
        path.write_bytes(buf.getvalue())
        return
    with zipfile.ZipFile(path, "w") as z:
        for name, text in files.items():
            z.writestr(f"led-bar/{name}", text)


def run(project, change=None, cart='[cart]\nmaker = "aisler"', fault=None, odb_file=True):
    """test_fab_run's export with [cart], its ODB++ written by the test and changed by change, through fab.run."""
    shutil.rmtree(project.root / "build", ignore_errors=True)
    fr.cut(project)
    f = project.root / "edakit.toml"
    f.write_text(f.read_text().split("\n[cart]\n")[0] + "\n" + cart + "\n")
    ex = fr.Export()
    if fault:
        fault(ex, project)
    out = ex.write(project.root)
    job = job_of(ex)
    if change:
        change(job)
    if odb_file:
        write(job, out / "main" / "odb_main.zip")
    cfg = project.config()
    return fab.run(cfg, cfg.board(), out, offline=True)


def f7(rows):
    return [(r["result"], r["check"], r["actual"]) for r in rows if r["id"] == "SYNC.odb"]


def test_the_reader_takes_the_job(project, tmp_path):
    fr.cut(project)
    ex = fr.Export()
    for tgz in (False, True):
        path = tmp_path / ("odb.tgz" if tgz else "odb.zip")
        write(job_of(ex), path, tgz)
        job = odb.read(path)
        assert [lay.name for lay in job.board_layers()][:4] == ["comp_+_top", "top_silk", "top_mask", "top"]
        assert {c.designator for c in job.components} == {"J1", "D1", "C2"}
        d1 = next(c for c in job.components if c.designator == "D1")
        assert (d1.x, d1.y, d1.rot, d1.side, d1.props["LCSC"]) == (13.0, 9.0, 180.0, "top", "C8678")
        assert {pin[0]: pin[3] for pin in d1.pins} == {"1": "+5V", "2": "VIN"}
        assert len(job.of_type("DRILL")[0].holes) == len(ex.pth) + len(ex.npth)
        assert job.profile[0][:2] == [(0.0, 0.0), (30.0, 0.0)]


def test_the_reader_names_what_it_cannot_read(tmp_path):
    (tmp_path / "x.zip").write_bytes(b"not an archive")
    with pytest.raises(odb.OdbError, match="neither a zip nor a tgz"):
        odb.read(tmp_path / "x.zip")
    with zipfile.ZipFile(tmp_path / "y.zip", "w") as z:
        z.writestr("job/steps/pcb/profile", "")
    with pytest.raises(odb.OdbError, match="no matrix/matrix"):
        odb.read(tmp_path / "y.zip")
    assert odb.symbol("r254", "MM") == ("C", 0.254, 0.254) and odb.symbol("rect1000x500", "MM") == ("R", 1.0, 0.5)
    assert odb.symbol("oval10x20", "INCH") == ("O", 0.254, 0.508)
    assert odb.rotated(("R", 2, 1), 90, 0, 0) == ("flash", (("R", 1, 2), 0, 0))
    assert odb.rotated(("R", 2, 1), 45, 0, 0)[0] == "region"


def test_f7_passes_on_an_odb_of_the_same_board(project):
    rows = run(project)
    assert fr.findings(rows) == []
    got = f7(rows)
    assert [r for r, _, _ in got] == ["pass", "pass", "pass", "pass", "info", "pass"]
    assert got[0][2] == "6 layers equal (no spot above 0.01 mm²)"
    assert got[4][2].startswith("J1 (bom: false) – the job lists them")


@pytest.mark.parametrize("change, check, text", [
    (lambda j: j["layers"]["top"].__setitem__(0, ["flash", ("C", 1.4, 1.4), 3.5, 9.0]),
     "every layer of the ODB++", "Gerber_TopLayer.GTL ≠ top: "),
    (lambda j: j["drop"].add("top_silk"), "every layer of the ODB++",
     "Gerber_TopSilkscreenLayer.GTO: no layer of the ODB++ is the silk top"),
    (lambda j: j["holes"].pop(0), "drill holes", "not in the ODB++"),
    (lambda j: j.update(profile=[(0, 0), (30, 0), (30, 21), (0, 21), (0, 0)]), "profile", "1.000 mm apart at most"),
    (lambda j: j["components"][1].update(rot=90), "parts of the ODB++", "D1: rotation 270° (ODB++ 90° clockwise), the "
                                                                        "CPL 180°"),
    (lambda j: j["components"][1].update(x=13.2), "parts of the ODB++", "D1: at (13.200, 9.000), the CPL"),
    (lambda j: j["components"].pop(2), "parts of the ODB++", "C2: 0x in the ODB++"),
    (lambda j: j["components"][2]["props"].update(MPN="CL21A106KAYNNNE"), "parts of the ODB++",
     "C2: part C45783 – the BOM CL21A226MAQNNNE"),
    (lambda j: j["components"][2]["pins"].__setitem__(0, ("1", 19.05, 9, "VIN")), "nets of the ODB++",
     "ODB++ net VIN joins +5V, VIN"),
])
def test_each_fault_of_f7(project, change, check, text):
    rows = run(project, change)
    bad = [(r, c, a) for r, c, a in f7(rows) if r == "fail"]
    assert len(bad) == 1 and bad[0][1].startswith(check) and text in bad[0][2], f7(rows)


def tooling_hole(attrs):
    """A tooling hole as KiCad's ODB++ has it: a footprint TH1 without part or pins, marked by edakit's property."""
    return lambda j: j["components"].append({"ref": "TH1", "x": 3.5, "y": 3.5, "rot": 0, "side": "top", "part": "",
                                             "pins": [], "props": {"edakit": "tooling"}, "attrs": attrs})


def test_a_tooling_hole_of_kicad_passes_only_marked_not_to_place(project):
    """KiCad has no free pads: the KiCad tool chain's tooling holes are footprints, and its ODB++ lists them as
    components – a maker places none that carries .no_pop."""
    assert f7(run(project, tooling_hole("0=0,1"))) == f7(run(project))
    bad = [(c, a) for r, c, a in f7(run(project, tooling_hole("0=0"))) if r == "fail"]
    assert bad == [("parts of the ODB++ = BOM and CPL (once each, place, rotation, side, part number)",
                    "TH1: tooling hole without .no_pop in the ODB++ – AISLER would place it")]


def test_the_reader_takes_the_attributes_of_a_component():
    text = "UNITS=MM\n@0 .comp_mount_type\n@1 .no_pop\nCMP 0 1.0 2.0 0 N TH1 x ;0=0,1\nCMP 1 1.0 2.0 0 N R1 y ;0=1\n"
    a, b = odb.components(text, "top", [])
    assert a.attrs == {".comp_mount_type": "0", ".no_pop": True} and b.attrs == {".comp_mount_type": "1"}


def test_a_second_maker_warns_and_an_export_that_failed_is_named(project):
    rows = run(project, lambda j: j["holes"].pop(0), cart='[cart]\nmakers = ["jlcpcb", "aisler"]')
    bad = [x for x in f7(rows) if x[0] != "pass" and x[0] != "info"]
    assert [r for r, _, _ in bad] == ["warn"] and bad[0][2].startswith("AISLER (not the planned maker): ")
    rows = run(project, odb_file=False)
    assert f7(rows) == [("fail", "ODB++ of this run for AISLER", "odb_main.zip: not exported")]
    rows = run(project, cart='[cart]\nmaker = "jlcpcb"', odb_file=False)
    assert f7(rows) == []                                   # no maker that takes ODB++: no SYNC.odb


def test_a_part_left_in_against_the_makers_dnp_fails(project, tmp_path):
    """A maker whose profile says dnp = "omit" leaves the parts not to place out: one in the ODB++ fails (way a)."""
    own = tmp_path / "odbmaker.toml"
    own.write_text((fab.Path(fab.__file__).parents[1] / "makers" / "aisler.toml").read_text().replace(
        'name = "AISLER"', 'name = "ODB maker"\ndnp = "omit"'))
    rows = run(project, cart=f'[cart]\nmaker = "odbmaker"\nprofiles = {{ odbmaker = {json.dumps(str(own))} }}')
    bad = [a for r, c, a in f7(rows) if r == "fail"]
    assert bad == ["J1: bom: false, but in the ODB++ – ODB maker would place it"]


def shifted(mm):
    """Every line of the ODB++'s top copper and top silkscreen moved up by mm."""
    def change(job):
        for name in ("top", "top_silk"):
            job["layers"][name] = [[i[0], i[1], [(x, y + mm) for x, y in i[2]], *i[3:]] if i[0] == "draw" else i
                                   for i in job["layers"][name]]
    return change


def test_an_edge_one_raster_step_off_is_rounding(project):
    """5.10 (the 555 blinker's live run, 2026-11-01): kicad-cli writes ODB++ coordinates to 0.1 µm, the Gerber files to
    1 nm – a track at y 17.400016 in the Gerber is at 17.4 in the ODB++, and along a long straight edge one row of the
    raster (gerber.RES) flips: 1.06 mm² of "difference" on a 53 mm silkscreen line. An edge one raster step off is
    rounding; a line moved by 0.1 mm is not."""
    assert f7(run(project, shifted(gerber.RES)))[0][0] == "pass"
    bad = f7(run(project, shifted(0.1)))[0]
    assert bad[0] == "fail" and "Gerber_TopLayer.GTL ≠ top: " in bad[2] and "Gerber_TopSilkscreenLayer.GTO ≠ top_silk" in bad[2]


def roundrect_pad(ex, project):
    """A pad's mask opening as EasyEDA writes it: its RoundRect macro (in the ODB++ rect<w>x<h>xr<r>)."""
    ex.gerber["top_mask"].append(("flash", ("RR", 1.3, 1.1), 20.0, 5.0))


def test_an_easyeda_roundrect_opening_equals_its_odb_rect(project):
    """Ordering step 0b (2026-11-01): EasyEDA writes a rounded pad's mask opening as its RoundRect macro with corners of
    0.1016 mm, its ODB++ as rect<w>x<h>xr2.0 – the same opening. Drawn as an obround, as the raster of the fab hash has
    it, the Gerber's opening lost its corners: 1.7 mm² of "difference" at the coin cell's pad of the probe board."""
    got = f7(run(project, fault=roundrect_pad))
    assert got[0] == ("pass", got[0][1], "6 layers equal (no spot above 0.01 mm²)"), got


def test_the_fab_hash_keeps_its_raster_of_a_roundrect():
    """The fab hash (FAB_METHOD v1) is made of Raster.render as it was – the RoundRect an obround –, so that every fab
    hash signed so far stays valid; SYNC.odb alone draws it as its rectangle (rr_box)."""
    r = gerber.Raster(0, 0, 4, 4)
    ops = [("flash", (("RR", 1.3, 1.1), 2, 2))]
    assert fab.FAB_METHOD == f"raster {gerber.RES} mm v1"
    assert r.render(ops).sum() * gerber.RES ** 2 == pytest.approx(math.pi * 0.55 ** 2 + 0.2 * 1.1, abs=0.05)
    assert r.render(ops, rr_box=True).sum() * gerber.RES ** 2 == pytest.approx(1.3 * 1.1, abs=0.05)


def test_the_export_leaves_no_file_of_easyeda_in_the_run(project, tmp_path):
    """Ordering step 0b: the bridge's call names no file, EasyEDA calls its archive "undefined", and the server writes it
    into the run's folder; export_odb packs it into odb_<b>.zip and takes it away."""
    f = project.root / "edakit.toml"
    f.write_text(f.read_text() + '\n[cart]\nmaker = "aisler"\n')
    cfg = project.config()
    d = tmp_path / "main"
    d.mkdir()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        data = b"UNITS=MM\n"
        info = tarfile.TarInfo("job/misc/info")
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    (d / "undefined").write_bytes(buf.getvalue())

    class MCP:
        def call(self, tool, **kw):
            return {"exported": True, "artifact_path": str(d / "undefined")}
    fab.export_odb(cfg, MCP(), cfg.board(), d)
    assert sorted(p.name for p in d.iterdir()) == ["odb_main.zip"]
    assert zipfile.ZipFile(d / "odb_main.zip").namelist() == ["job/misc/info"]


PROBE = fab.Path(__file__).parent / "fixtures" / "makers" / "aisler" / "probe_2026-11-01"
COIN_CELL = fab.Path(__file__).parents[1] / "examples" / "coin-cell-led"


def test_f7_on_easyeda_s_own_export(tmp_path):
    """Ordering step 0b (2026-11-01): EasyEDA's own ODB++ of a probe board – coin-cell-led with D1 turned by 90°, R1 on
    the bottom turned by 90° and AISLER in [cart] (overlay/) –, exported with the patched easyeda_export_odb, against the
    Gerber, drill, BOM and CPL files of the same run (run/). Every layer, hole, part and net equal; EasyEDA turns
    clockwise in its ODB++ (D1 and R1 at 270°, the CPL 90°) and keeps BT1 (bom: false) in it without a mark – the job
    lists it not to place (dnp)."""
    from edakit import config
    root = tmp_path / "probe"
    shutil.copytree(COIN_CELL, root, ignore=shutil.ignore_patterns("build"))
    shutil.copytree(PROBE / "overlay", root, dirs_exist_ok=True)
    out = tmp_path / "run"
    shutil.copytree(PROBE / "run", out)
    cfg = config.load(root / "edakit.toml")
    got = f7(fab.run(cfg, cfg.board(), out, offline=True))
    assert [r for r, _, _ in got] == ["pass", "pass", "pass", "pass", "info", "pass"], got
    assert got[0][2] == "8 layers equal (no spot above 0.01 mm²)"
    assert got[4][2].startswith("BT1 (bom: false) – the job lists them")
    parts = {c.designator: c for c in odb.read(out / "main" / "odb_main.zip").components}
    assert {ref: (c.side, c.rot, c.mirror) for ref, c in parts.items()} == {
        "BT1": ("top", 0, False), "D1": ("top", 270, False), "SW1": ("top", 0, False), "R1": ("bottom", 270, False)}
def test_the_odb_carries_the_number_the_maker_matches_by(project):
    """5.10 (AISLER live, 2026-11-01): AISLER matches by manufacturer part number and knows no LCSC number – an ODB++
    whose parts carry only their LCSC numbers left AISLER's "Auto detect MPN" with one part of ten. For a maker that
    matches by MPN every part carries its entry's MPN."""
    def lcsc_only(job):
        for c in job["components"]:
            c["props"] = {}
    bad = [(r, a) for r, c, a in f7(run(project, lcsc_only)) if c.startswith("parts of the ODB++")]
    assert bad == [("fail", "no part of the ODB++ carries the MPN AISLER matches by – AISLER cannot match them")]
