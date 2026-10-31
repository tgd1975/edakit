"""Sign-offs on the manufacturing files (#65): `fab_sha256` over what the manufacturer builds from – every Gerber layer
rasterised as GEO.copper does (0.02 mm), the drill hits, the BOM and CPL rows, and with [order] the order settings that change
the made board – and `edakit fab diff`, on the export of tests/test_fab_run.py written twice. Documentation and
drill-drawing layers are left out."""

import json
import re
import shutil

import pytest
import test_fab_run as fr
from edakit import cli, gerber
from edakit.release import fab, gate

DOC = "G04 documentation*\n%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.1*%\nD10*\nX1000000Y1000000D02*\nX{x}Y1000000D01*\nM02*\n"


def paste(ex):
    """The paste layer of the SMD pads (the test export has none)."""
    layer = fr.Layer()
    for item in ex.gerber["top"]:
        if item[0] == "flash" and item[1][0] == "R":
            layer.append(item)
    return layer


def write(project, run, change=None, renumber=False):
    """One gate run's export under <reports>/<run>/fab/main – as fab.collect leaves it – plus BOM and CPL."""
    ex = fr.Export()
    if change:
        change(ex)
    out = ex.write(project.root / "w" / run)
    g = out / "main" / "gerber"
    (g / "Gerber_TopPasteMaskLayer.GTP").write_text(paste(ex).text())
    (g / "Gerber_DocumentLayer.GDL").write_text(DOC.format(x=5000000 if renumber else 9000000))
    (g / "Gerber_DrillDrawingLayer.GDD").write_text(DOC.format(x=7000000 if renumber else 3000000))
    (g / "How-to-order-PCB.txt").write_text(run)
    if renumber:   # what every export does: other aperture numbers, a date comment
        for f in g.glob("Gerber_*"):
            t = re.sub(r"^(%ADD|D)(\d+)", lambda m: f"{m.group(1)}{int(m.group(2)) + 10}", f.read_text(), flags=re.M)
            f.write_text("G04 EasyEDA Pro, 2026-10-25 23:22:27*\n" + t)
    d = project.root / "build" / "release" / run / "fab"
    d.mkdir(parents=True)
    (out / "main").rename(d / "main")
    cpl = ["Designator,Mid X,Mid Y,Layer,Rotation"] + [f"{r},{x}mm,{y}mm,Top,{rot}" for r, (_, x, y, rot) in
                                                         sorted(fr.PLACE.items(), reverse=renumber)]
    (d / "main" / "cpl_main.csv").write_text("\n".join(cpl) + "\n")
    (d / "main" / "bom_main.csv").write_text("Comment,Designator,Footprint,LCSC Part #\n22uF,C2,C0805,C45783\n"
                                             "SS34,D1,SMA,C8678\n")
    return d / "main"


def layers(d):
    return fab.fab_layers(d, "main")


def test_equal_exports_have_the_same_fab_hash(project, capsys):
    a, b = write(project, "20261025-224607"), write(project, "20261025-232212", renumber=True)
    assert (a / "gerber" / "Gerber_TopLayer.GTL").read_bytes() != (b / "gerber" / "Gerber_TopLayer.GTL").read_bytes()
    la, lb = layers(a), layers(b)
    assert la == lb
    assert "Gerber_DocumentLayer.GDL" not in la and "Gerber_DrillDrawingLayer.GDD" not in la
    assert {"Gerber_TopLayer.GTL", "Gerber_TopPasteMaskLayer.GTP", "Drill_PTH_Through.DRL", "bom_main.csv",
            "cpl_main.csv"} <= set(la)
    assert fab.fab_hash({"main": la}) == fab.fab_hash({"main": lb})
    cfg = project.config()
    assert cli.main(["fab", "diff", "20261025-224607", "20261025-232212", "--config", str(cfg.root / "edakit.toml")]) == 0
    assert "equal" in capsys.readouterr().out


def test_a_moved_part_changes_copper_mask_and_paste(project, monkeypatch, capsys):
    a = write(project, "20261025-204229")
    fp, x, y, rot = fr.PLACE["C2"]
    monkeypatch.setitem(fr.PLACE, "C2", (fp, x + 0.1, y, rot))
    b = write(project, "20261025-205344")
    la, lb = layers(a), layers(b)
    changed = {k for k in la if la[k] != lb[k]}
    assert changed == {"Gerber_TopLayer.GTL", "Gerber_TopSolderMaskLayer.GTS", "Gerber_TopPasteMaskLayer.GTP",
                       "cpl_main.csv"}
    assert fab.fab_hash({"main": la}) != fab.fab_hash({"main": lb})
    cfg = project.config()
    assert cli.main(["fab", "diff", "20261025-204229", "20261025-205344", "--config", str(cfg.root / "edakit.toml")]) == 2
    out = capsys.readouterr().out
    verdict = {ln.split()[0]: ln.split()[1] for ln in out.splitlines() if ln.startswith("  ") and ln.split()}
    assert {k for k, v in verdict.items() if v == "changed"} == changed
    assert verdict["Gerber_BottomLayer.GBL"] == verdict["Gerber_TopSilkscreenLayer.GTO"] == "equal"
    spots = [tuple(map(float, m)) for m in re.findall(r"x ([\d.]+)–([\d.]+), y ([\d.]+)–([\d.]+) mm", out)]
    assert spots and all(18 <= x0 and x1 <= 22 and 8 <= y0 and y1 <= 10 for x0, x1, y0, y1 in spots)   # at C2
    assert "- C2,20mm,9mm,Top,0" in out and "+ C2,20.1mm,9mm,Top,0" in out


def test_a_longer_plus_changes_only_the_top_silkscreen(project):

    def longer(ex):
        ex.gerber["top_silk"][:] = [("draw", w, [(fr.PLUS[0] + (px - fr.PLUS[0]) * 1.1, fr.PLUS[1] + (py - fr.PLUS[1]) * 1.1)
                                                 for px, py in pts], t) for _, w, pts, t in ex.gerber["top_silk"]]
    la, lb = layers(write(project, "20261025-204229")), layers(write(project, "20261025-205344", longer))
    assert {k for k in la if la[k] != lb[k]} == {"Gerber_TopSilkscreenLayer.GTO"}


def test_a_signoff_with_scope_fab_counts_for_its_files_only(project, monkeypatch):
    cfg = project.config()
    la = layers(write(project, "20261025-204229"))
    fp, x, y, rot = fr.PLACE["C2"]
    monkeypatch.setitem(fr.PLACE, "C2", (fp, x + 0.1, y, rot))
    lb = layers(write(project, "20261025-205344"))
    ha, hb = fab.fab_hash({"main": la}), fab.fab_hash({"main": lb})
    path = cfg.signoff
    s = json.loads(path.read_text())
    s["fab_sha256"] = ha
    for m in s["manual"]:
        if m["id"] == "M-5":
            m.update(scope="fab", done_by="agent pcb-reviewer", date="2026-10-25")
    path.write_text(json.dumps(s))
    by = lambda head: {m["id"]: m["done_by"] for m in gate.load_signoff(cfg, head)[0]["manual"]}  # noqa: E731
    base = {"state_sha256": None, "layout_sha256": None}
    assert by({**base, "fab_sha256": ha})["M-5"] == "agent pcb-reviewer"
    assert by({**base, "fab_sha256": hb})["M-5"] is None
    signoff, notes = gate.load_signoff(cfg, base)            # offline: no stage F, no fab hash
    m5 = next(m for m in signoff["manual"] if m["id"] == "M-5")
    assert m5["done_by"] is None and m5["unchecked"]["fab_sha256"] == ha     # bound to ha, checked by stage F
    assert any("scope 'fab'" in n and f"bound to fab {ha[:12]}…" in n for n in notes)


def test_the_raster_frame_is_the_outline(tmp_path):
    (tmp_path / gerber.FILES["outline"]).write_text(fr.Layer([("draw", 0.1, [(0, 0), (30, 0), (30, 20), (0, 20), (0, 0)],
                                                               "o")]).text())
    f = fab.frame(tmp_path, [])
    assert (round(f.x0, 3), round(f.y0, 3)) == (-1.0, -1.0)
    assert abs(f.w - 32 / gerber.RES) <= 1 and abs(f.h - 22 / gerber.RES) <= 1


def test_the_gate_writes_the_fab_hash_into_the_manifest(project):
    cfg = project.config()
    write(project, "20261025-232212")
    out = cfg.reports / "20261025-232212"
    head = {"time": "t", "git_commit": "abc", "git_dirty": False, "graph_sha256": "g", "state_sha256": "s",
            "layout_sha256": "l", "graph_version": "1.0"}
    head.update(gate.fab_hashes(cfg, out))
    assert head["fab_method"] == "raster 0.02 mm v1" and set(head["fab_layers"]) == {"main"}
    gate.write_manifest(cfg, out, head, "NOT RELEASED")
    m = json.loads((out / "fab" / "manifest.json").read_text())
    assert m["fab_sha256"] == fab.fab_hash(m["fab_layers"]) == head["fab_sha256"]
    assert m["fab_layers"]["main"]["Gerber_TopLayer.GTL"] == layers(out / "fab" / "main")["Gerber_TopLayer.GTL"]


# --- the order settings that change the made board: thickness, colours, finish, mark ([order], step 1.7) --------------

def exported(project, fault=None):
    """`edakit fab --offline` on the export of test_fab_run, the board file changed by fault: (the board folder, its
    fab hash)."""
    shutil.rmtree(project.root / "build", ignore_errors=True)
    fr.run(project, fault)
    d = project.root / "build" / "fab" / "main"
    return d, fab.fab_hash({"main": layers(d)})


def ordered(**order):
    """[order] in the board file as test_fab_run orders it (mark = "specify", the placeholder, a remark), changed by
    order."""
    return lambda ex, p: fr.ordered(ex, p, order)


def test_a_board_without_order_keeps_its_fab_hash(project):
    """No [order], no order settings: fab_layers holds the files the manufacturer builds from and nothing else, so the
    fab hash of a board without [order] stays what it was (the bell's reviewed runs, its D-20)."""
    d, _ = exported(project)
    gerbers, drills = fab.built_files(d / "gerber")
    assert set(layers(d)) == {f.name for f in gerbers + drills} | {"bom_main.csv", "cpl_main.csv"}
    assert not (d / "order.json").exists()


def test_a_stale_order_file_leaves_with_the_order(project):
    """`edakit fab --offline` on the folder of a run with [order], when the board file has none any more: the settings
    leave the folder and the fab hash."""
    d, _ = exported(project, ordered())
    assert "order.json" in layers(d)
    f = project.root / "hardware" / "boards" / "main.toml"
    f.write_text(f.read_text().split("\n[order]\n")[0] + "\n")
    cfg = project.config()
    fab.run(cfg, cfg.board(), d.parent, offline=True)
    assert not (d / "order.json").exists() and "order.json" not in layers(d)


@pytest.mark.parametrize("fault", [ordered(mask="black"), ordered(mask="white"), ordered(finish="ENIG"),
                                   ordered(mark="remove"), fr.thickness(1.0)],
                         ids=["mask black", "mask white", "finish ENIG", "mark remove", "1.0 mm"])
def test_an_order_setting_that_changes_the_board_changes_the_fab_hash(project, fault):
    """Thickness as ordered, the colours of mask and silkscreen, finish and mark change what JLCPCB makes: they are
    in the fab hash – with every Gerber layer, drill hit and BOM and CPL row the same."""
    d, green = exported(project, ordered())
    settings = json.loads((d / "order.json").read_text())
    assert settings == {"thickness_mm": 1.6, "mask": "green", "silkscreen": "white", "finish": "LeadFree HASL",
                        "mark": "specify"}
    files = {k: v for k, v in layers(d).items() if k != "order.json"}
    d, other = exported(project, fault)
    assert other != green and {k: v for k, v in layers(d).items() if k != "order.json"} == files


@pytest.mark.parametrize("change", [{"remark": "No V-cut."}, {"tab_zones": [((30, 0), (30, 20))]},
                                    {"tab_copper_mm": 0.5}])
def test_remark_and_tab_zones_stay_out_of_the_fab_hash(project, change):
    """The remark is free text to JLCPCB, and the tab zones reach it only through the remark: neither changes the
    board as made, so neither is in the fab hash (both are in the layout hash with the board file)."""
    _, h = exported(project, ordered())
    assert exported(project, ordered(**change))[1] == h


def test_a_new_colour_lets_the_layout_review_of_scope_fab_lapse(project):
    """M-5 signed on the fab hash of a green board does not count for the same files ordered black – and counts
    again when the order is green again."""
    _, green = exported(project, ordered())
    _, black = exported(project, ordered(mask="black"))
    cfg = project.config()
    s = json.loads(cfg.signoff.read_text())
    s["fab_sha256"] = green
    for m in s["manual"]:
        if m["id"] == "M-5":
            m.update(scope="fab", done_by="agent pcb-reviewer", date="2026-10-28")
    cfg.signoff.write_text(json.dumps(s))
    m5 = lambda h: {m["id"]: m["done_by"] for m in gate.load_signoff(cfg, {"fab_sha256": h})[0]["manual"]}["M-5"]  # noqa: E731
    assert m5(black) is None and m5(green) == "agent pcb-reviewer"
    assert exported(project, ordered(mask="green"))[1] == green


def test_fab_diff_names_the_changed_order_settings(project, capsys):
    runs = project.root / "runs"
    for run, fault in (("20261028-100000", ordered()), ("20261028-110000", fr.thickness(1.0, {"mask": "black"}))):
        d, _ = exported(project, fault)
        (runs / run / "fab").mkdir(parents=True)
        d.rename(runs / run / "fab" / "main")
    cfg = project.config()
    assert cli.main(["fab", "diff", str(runs / "20261028-100000"), str(runs / "20261028-110000"),
                     "--config", str(cfg.root / "edakit.toml")]) == 2
    out = capsys.readouterr().out
    assert "  order.json  changed\n" in out and "1 file(s) changed" in out
    for line in ('- mask = "green"', '+ mask = "black"', "- thickness_mm = 1.6", "+ thickness_mm = 1.0"):
        assert f"      {line}\n" in out, line
