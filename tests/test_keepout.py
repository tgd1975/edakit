"""GEO.keepout (maker-coverage CK-11): no copper inside the antenna keep-out a parts entry gives, measured on the
Gerber copper of the written export of test_fab_run; the coverage report names a radio without the field."""

from test_fab_run import findings, run

from edakit import schema
from edakit.design import Design
from edakit.engines.coverage import coverage
from edakit.release import fab


def keepout(box):
    """C2's entry (C45783, at (20, 9) in the export) gets an antenna keep-out – for the test, C2 has no antenna."""
    def fault(ex, project):
        part = project.part("C45783")
        part["antenna"] = {"keepout_mm": box}
        project.save_part("C45783", part)
    return fault


def rows_of(rows):
    return [r for r in rows if r["id"] == "GEO.keepout"]


def test_copper_inside_the_keep_out(project):
    rows = run(project, keepout([-2, -1.5, 2, 1.5]))     # C2's own pads lie in it
    mine = rows_of(rows)
    assert [r["result"] for r in mine] == ["warn"] and "mm² on TOP" in mine[0]["actual"]
    assert ("GEO.keepout", "warn") in findings(rows)


def test_a_free_keep_out(project):
    rows = run(project, keepout([-2, 6, 2, 7]))
    assert [(r["result"], r["actual"]) for r in rows_of(rows)] == [("pass", "free")]


def test_without_the_field_nothing_is_checked(project):
    assert rows_of(run(project)) == []


def test_without_the_gerber_files_the_part_is_not_checked(project):
    run(project, keepout([-2, 6, 2, 7]))
    cfg = project.config()
    out = fab.Rows()
    fab.check_keepout(cfg.board(), Design.from_config(cfg), project.root / "build" / "fab" / "main", None, out)
    assert [(r["result"], r["actual"]) for r in out] == [("info", "not checked: the Gerber files are missing")]


def test_the_field_is_held_to_its_shape():
    entry = {"kind": "module", "antenna": {"keepout_mm": [3, 0, 1, 5]}, "pins": {}}
    assert "antenna.keepout_mm: [x0, y0, x1, y1] in mm with x0 < x1 and y0 < y1 (the footprint's frame)" in \
        schema.problems(entry)


def test_a_radio_without_a_keep_out_is_a_gap(project):
    u1 = project.graph()["graph"]["components"][[c["designator"] for c in project.graph()["graph"]["components"]]
                                                 .index("U1")]["lcsc"]
    part = project.part(u1)
    part.setdefault("compliance", {})["radio"] = {"bands_mhz": [[2400, 2483.5]], "power_dbm": 10}
    project.save_part(u1, part)
    gaps = [g for g in coverage(Design.from_config(project.config())) if g.code == "GEO.keepout"]
    assert [(g.place, g.missing.split(" (")[0]) for g in gaps] == [
        ("U1", "no antenna.keepout_mm – the copper under its antenna is not checked")]
