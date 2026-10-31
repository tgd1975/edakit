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


# --- the antenna at or over the board edge (antenna.edge_mm) ----------------------------------------------------------
def edge_rows(rows):
    return [r for r in rows if r["id"] == "GEO.keepout" and "board edge" in r["check"]]


def antenna(box, edge_mm):
    """C2's entry gets an antenna area and how far inside the board's outer edge it may lie – for the test."""
    def fault(ex, project):
        part = project.part("C45783")
        part["antenna"] = {"keepout_mm": box, "edge_mm": edge_mm}
        project.save_part("C45783", part)
    return fault


def test_an_antenna_inside_the_board(project):
    """C2 at (20, 9) on the board of 30 × 20 mm: an area 6–7 mm off its centre lies 3 mm or more inside the outline –
    with edge_mm 1 (Espressif's figure for the ESP32 modules) a warning; the area is free of copper, so only this."""
    rows = run(project, antenna([-2, 6, 2, 7], 1))
    mine = edge_rows(rows)
    assert [r["result"] for r in mine] == ["warn"] and mine[0]["actual"].endswith("mm inside the outline")
    assert float(mine[0]["actual"].split()[0]) > 1
    assert findings(rows) == [("GEO.keepout", "warn")]


def test_an_antenna_over_the_edge(project):
    """The same area stretched beyond the outline: at or over the edge – it passes, the copper check as well."""
    rows = run(project, antenna([-2, 6, 2, 13], 1))
    assert [(r["result"], r["actual"]) for r in edge_rows(rows)] == [("pass", "at or over the edge")]
    assert findings(rows) == []


def test_an_antenna_at_the_edge_within_its_distance(project):
    """An area whose far side ends 0.5 mm inside the outline: it passes with edge_mm 1, warns with edge_mm 0."""
    rows = run(project, antenna([-2, 8, 2, 10.5], 1))
    assert [(r["result"], r["actual"]) for r in edge_rows(rows)] == [("pass", "0.50 mm inside the outline")]
    part = project.part("C45783")
    part["antenna"]["edge_mm"] = 0
    project.save_part("C45783", part)
    cfg = project.config()
    out = fab.Rows()
    fab.check_antenna_edge(cfg.board(), Design.from_config(cfg), project.root / "build" / "fab" / "main", out)
    assert [(r["result"], r["expected"]) for r in out] == [("warn", "<= 0 mm inside")]


def test_a_cut_out_inside_the_board_is_no_edge(project):
    """An area inside the M3 hole at (26, 16) – a closed path of the outline, so no board under it – is still 3.4 mm
    inside the outer outline: a clearance hollowed out on all sides is not the edge Espressif asks for."""
    rows = run(project, antenna([5.4, 6.4, 6.6, 7.6], 1))
    assert [(r["result"], r["actual"]) for r in edge_rows(rows)] == [("warn", "3.40 mm inside the outline")]


def test_without_edge_mm_the_edge_is_not_checked(project):
    assert edge_rows(run(project, keepout([-2, 6, 2, 7]))) == []


def test_edge_mm_is_held_to_its_shape():
    entry = {"kind": "module", "antenna": {"keepout_mm": [0, 0, 1, 5], "edge_mm": -1}, "pins": {}}
    assert schema.problems(entry) == ["antenna.edge_mm: a distance in mm ≥ 0 – how far inside the board's outer edge "
                                      "the antenna area may lie at most (the module maker's layout guide)"]
