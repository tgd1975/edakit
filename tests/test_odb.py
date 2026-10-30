"""Ordering step 10 (docs/concepts/new/ordering.md): EasyEDA's ODB++ export for a maker that takes it (AISLER),
read by edakit/odb.py and held by F-7 to the run's Gerber, drill, BOM and CPL files and to the graph. No real export
of EasyEDA is at hand yet (ordering step 0b): the ODB++ here is written by the test from the export of
test_fab_run – the same copper, mask and silkscreen, drill hits, outline, parts and nets –, so that F-7 passes on it,
and each fault is one change of it."""

import io
import json
import shutil
import tarfile
import zipfile

import pytest

import test_fab_run as fr
from edakit import odb
from edakit.release import fab

UM = 1000            # symbols of an MM file are in microns
LAYERS = [("comp_+_top", "COMPONENT", "top"), ("top_silk", "SILK_SCREEN", "top_silk"),
          ("top_mask", "SOLDER_MASK", "top_mask"), ("top", "SIGNAL", "top"), ("bottom", "SIGNAL", "bottom"),
          ("bottom_mask", "SOLDER_MASK", "bottom_mask"), ("bottom_silk", "SILK_SCREEN", "bottom_silk"),
          ("comp_+_bot", "COMPONENT", "bottom"), ("drill", "DRILL", None)]


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
                      "side": "top", "part": fr.LCSC[ref],
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
        lines = ["UNITS=MM"]
        for i, c in enumerate(cp for cp in job["components"] if cp["side"] == side):
            lines += [f"# CMP {i}", f"CMP {i} {c['x']:.6f} {c['y']:.6f} {c['rot']:g} {'M' if side == 'bottom' else 'N'} "
                                     f"{c['ref']} {c['part']}", f"PRP LCSC '{c['part']}'"]
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
    return [(r["result"], r["check"], r["actual"]) for r in rows if r["id"] == "F-7"]


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
    (lambda j: j["components"][2].update(part="C1"), "parts of the ODB++", "C2: part C1 – the BOM C45783, "),
    (lambda j: j["components"][2]["pins"].__setitem__(0, ("1", 19.05, 9, "VIN")), "nets of the ODB++",
     "ODB++ net VIN joins +5V, VIN"),
])
def test_each_fault_of_f7(project, change, check, text):
    rows = run(project, change)
    bad = [(r, c, a) for r, c, a in f7(rows) if r == "fail"]
    assert len(bad) == 1 and bad[0][1].startswith(check) and text in bad[0][2], f7(rows)


def test_a_second_maker_warns_and_an_export_that_failed_is_named(project):
    rows = run(project, lambda j: j["holes"].pop(0), cart='[cart]\nmakers = ["jlcpcb", "aisler"]')
    bad = [x for x in f7(rows) if x[0] != "pass" and x[0] != "info"]
    assert [r for r, _, _ in bad] == ["warn"] and bad[0][2].startswith("AISLER (not the planned maker): ")
    rows = run(project, odb_file=False)
    assert f7(rows) == [("fail", "ODB++ of this run for AISLER", "odb_main.zip: not exported")]
    rows = run(project, cart='[cart]\nmaker = "jlcpcb"', odb_file=False)
    assert f7(rows) == []                                   # no maker that takes ODB++: no F-7


def test_a_part_left_in_against_the_makers_dnp_fails(project, tmp_path):
    """A maker whose profile says dnp = "omit" leaves the parts not to place out: one in the ODB++ fails (way a)."""
    own = tmp_path / "odbmaker.toml"
    own.write_text((fab.Path(fab.__file__).parents[1] / "makers" / "aisler.toml").read_text().replace(
        'name = "AISLER"', 'name = "ODB maker"\ndnp = "omit"'))
    rows = run(project, cart=f'[cart]\nmaker = "odbmaker"\nprofiles = {{ odbmaker = {json.dumps(str(own))} }}')
    bad = [a for r, c, a in f7(rows) if r == "fail"]
    assert bad == ["J1: bom: false, but in the ODB++ – ODB maker would place it"]
