"""GEO.spacing/apart (maker-coverage CK-31): nets the hand-over keeps apart (layout.apart), measured on the Gerber
copper of the written export of test_fab_run (its input stage: VIN, +5V, GND)."""

from test_fab_run import findings, run

from edakit import engines
from edakit.design import Design
from edakit.release import fab


def apart(min_mm, a="VIN", b="GND"):
    def fault(ex, project):
        g = project.graph()
        g["graph"].setdefault("layout", {})["apart"] = [{"a": a, "b": b, "min_mm": min_mm, "what": "test"}]
        project.save_graph(g)
    return fault


def rows_of(rows):
    return [r for r in rows if r["id"] == "GEO.spacing" and r["check"].startswith("VIN and GND")]


def test_two_nets_closer_than_the_hand_over_allows(project):
    rows = run(project, apart(10.0))
    mine = rows_of(rows)
    assert [r["result"] for r in mine] == ["warn"]
    assert mine[0]["expected"] == ">= 10 mm" and " mm on TOP at (" in mine[0]["actual"]
    assert ("GEO.spacing", "warn") in findings(rows)


def test_two_nets_far_enough_apart(project):
    rows = run(project, apart(0.05))
    assert [r["result"] for r in rows_of(rows)] == ["pass"]


def test_without_the_gerber_files_the_pair_is_not_checked(project):
    run(project, apart(10.0))
    cfg = project.config()
    out = fab.Rows()
    fab.check_apart(cfg.board(), Design.from_config(cfg), None, out)
    assert [(r["result"], r["actual"]) for r in out] == [("info", "not checked: the Gerber files are missing")]


def test_a_pair_naming_an_unknown_net(project):
    g = project.graph()
    g["graph"].setdefault("layout", {})["apart"] = [{"a": "LED_SDI", "b": "NOPE", "min_mm": 1}]
    project.save_graph(g)
    cfg = project.config()
    texts = [f.text for f in engines.run(Design.from_config(cfg), cfg).findings if f.code == "STRUCT.ref"]
    assert "layout.apart: no net NOPE in the graph" in texts
