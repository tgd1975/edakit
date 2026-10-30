"""The hand-over from the circuit to the layout: requirements in the graph and derived from it, G-1 for their names,
L-12 for the plan, L-11 for the loops the circuit hands over."""

import json
from types import SimpleNamespace

from helpers import check

from edakit import checks, cli, handover, pcb
from edakit.design import Design
from edakit.handover import Requirement
from edakit.release import fab

# boxes (x0, y0, x1, y1) in plan mm on the example's 90 x 40 board that keep every requirement of its graph
KEPT = {"J1": (86, 10, 90, 14), "U2": (62, 12, 70, 22), "C1": (65, 24, 67, 25), "R1": (59, 16, 60, 18),
        "SW1": (78, 23, 82, 27), **{f"D{i}": (4 * i + 44, 33, 4 * i + 46, 35) for i in range(2, 10)}}


def plan_of(boxes):
    return {r: SimpleNamespace(x=(b[0] + b[2]) / 2, y=(b[1] + b[3]) / 2, rot=0, side="top") for r, b in boxes.items()}


def kept(project, boxes, design=None):
    cfg = project.config()
    return pcb.check_handover(cfg.board(), design or Design.from_config(cfg), plan_of(boxes), boxes)


def test_example_hands_over_what_the_graph_says_and_the_decoupling(project):
    req = handover.requirements(Design.from_config(project.config()), "main")
    assert {(r.kind, r.part) for r in req if r.kind in ("fixed", "edge")} == \
        {("fixed", d) for d in ["SW1", *[f"D{i}" for i in range(2, 10)]]} | {("edge", "J1")}
    assert Requirement("near", "R1", ("U2",)) in req
    assert Requirement("decoupling", "U2", ("C1",), "3V3") in req     # U1 is a module: its decoupling is on board
    assert not [r for r in req if r.part == "U1"]


def test_waive_lifts_the_derived_decoupling(project):
    g = project.graph()
    project.comp(g, "U2")["accept"] = {"SYNC.plan": "decoupled on the module next to it"}
    project.save_graph(g)
    assert not [r for r in handover.requirements(Design.from_config(project.config()), "main")
                if r.kind == "decoupling"]


def test_a_capacitor_behind_a_zero_ohm_bridge_still_decouples(project):
    project.save_part("C9000002", {"lcsc": "C9000002", "mpn": "0 Ω bridge", "kind": "resistor",
                                   "values": {"value_ohm": 0.0},
                                   "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}}})
    g = project.graph()
    g["graph"]["components"].append({"designator": "R11", "type": "resistor", "lcsc": "C9000002", "value": "0",
                                     "pins": {"1": "1", "2": "2"}})
    project.net(g, "GND")["pins"].remove("C1.2")      # C1 reaches GND over the bridge R11
    project.net(g, "GND")["pins"].append("R11.1")
    g["graph"]["nets"].append({"name": "GND_B", "pins": ["R11.2", "C1.2"], "v": [0, 0]})
    project.save_graph(g)
    req = handover.requirements(Design.from_config(project.config()), "main")
    assert Requirement("decoupling", "U2", ("C1",), "3V3") in req


def test_names_the_graph_does_not_have_are_g1(project):
    g = project.graph()
    g["graph"]["layout"].update(fixd=["J1"], edge=["J7"], near={"R1": "U9"},
                                loops=[{"a": "C1.1", "b": "C2.1", "max_mm": 5}])
    project.save_graph(g)
    cfg = project.config()
    found = [m for c, m in check(Design.from_config(cfg), cfg).errors if c == "STRUCT.ref"]
    assert found == ["layout: unknown key 'fixd' (known: fixed, edge, near, loops, notes)",
                     "layout.edge: no part J7 in the graph", "layout.near: no part U9 in the graph",
                     "layout.loops: C1.1 and C2.1 are not on one net of one board"]


def test_plan_that_keeps_the_requirements_passes(project):
    assert kept(project, KEPT) == []


def test_plan_that_ignores_them_fails(project):
    boxes = {**KEPT, "J1": (70, 10, 74, 14), "C1": (40, 24, 42, 25)}
    del boxes["SW1"]
    assert kept(project, boxes) == [
        "SW1: not in hardware/boards/main.toml [place] – the circuit wants it fixed",
        "J1: 10.0 mm from the board edge – the circuit wants it at the edge (edge_mm 1)",   # the lower edge
        "U2: no capacitor of its own from 3V3 to GND within 6 mm – fix C1 next to it"]


def test_two_ics_do_not_share_one_capacitor(project, monkeypatch):
    monkeypatch.setattr(handover, "requirements", lambda design, board: [
        Requirement("decoupling", "U2", ("C1", "C3"), "3V3"), Requirement("decoupling", "U3", ("C1", "C3"), "3V3")])
    boxes = {"U2": (10, 10, 20, 20), "U3": (24, 10, 34, 20), "C1": (21, 14, 23, 15), "C3": (60, 30, 62, 31)}
    found = kept(project, boxes)
    assert len(found) == 1 and "no capacitor of its own from 3V3" in found[0]   # C1 serves only one of them
    boxes["C3"] = (35, 14, 37, 15)
    assert kept(project, boxes) == []


def test_near_of_the_plan_counts_only_between_fixed_parts(project):
    cfg = project.config()
    boxes = {"U1": (10, 8, 50, 26)}
    found = pcb.check_plan(cfg, cfg.board(), {}, plan_of(boxes), boxes, {"top": [], "bottom": []})
    assert found == ["near C2: C2 not fixed – near counts only between fixed parts"]


def test_loops_of_the_graph_reach_l11(project, tmp_path):
    g = project.graph()
    g["graph"]["layout"]["loops"] = [{"a": "C1.1", "b": "U2.16", "max_mm": 5, "what": "U2 supply"}]
    project.save_graph(g)
    cfg = project.config()
    design = Design.from_config(cfg)
    assert design.pin_net["C1.1"] == design.pin_net["U2.16"] == "3V3"
    pads = {"C1": ("1", 0), "U2": ("16", 1000)}   # 1000 mil = 25.4 mm apart, joined by one track
    (tmp_path / "pcb.json").write_text(json.dumps({
        "components": [{"designator": d, "pads": [{"PadNumber": n, "X": x, "Y": 0, "Net": "3V3", "Layer": 1}]}
                       for d, (n, x) in pads.items()],
        "lines": [{"Net": "3V3", "Layer": 1, "StartX": 0, "StartY": 0, "EndX": 1000, "EndY": 0, "LineWidth": 10}]}))
    rows = fab.Rows()
    fab.check_loops(cfg.board(), design, tmp_path, rows)
    assert [(r["id"], r["result"]) for r in rows] == [("GEO.loop", "fail")]
    assert "C1.1-U2.16 (U2 supply): 25.4 mm > 5.0 mm" in rows[0]["actual"]


def test_handover_sheet(project, monkeypatch, capsys):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["handover"]) == 0
    out = capsys.readouterr().out
    for line in ["  M-1 ", "  edge   J1", "  near   R1 next to U2",
                 "  near   C1 next to U2 – decoupling of 3V3, a capacitor of its own (derived)",
                 "  - D2 to D9 form the bar"]:
        assert line in out, out
