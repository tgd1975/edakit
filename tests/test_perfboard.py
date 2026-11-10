"""The plan of a hand-wired board on a perfboard (handbook 7.9, concept perfboard-layout.md, steps LR.1 to LR.4): the
kinds as data, the plan in the board file of a board with wired = true, the nets it makes against the graph's, the
checks of grid, bodies, mounting holes, wires and current, the hand-over, and the drawings and lists.

The project tests/fixtures/perfboard: a pin header J1, a push button SW1, an axial resistor R1 and a 5 mm LED D1 on
14 x 8 holes of a pad per hole – every footprint as data. Each check is seen red once on a copy with one mistake
built in, the clean plan beside it."""

import html
import json
import re
import shutil
import tomllib
from pathlib import Path

import pytest

from edakit import catalog, cli, perfboard
from edakit.config import ConfigError, load
from edakit.design import Design

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "perfboard"
ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "coin-cell-led"            # its variant perfboard: LR.7


@pytest.fixture
def pb(tmp_path):
    dst = tmp_path / "perfboard"
    shutil.copytree(FIXTURE, dst, ignore=shutil.ignore_patterns("build"))

    class P:
        root = dst
        plan_file = dst / "hardware" / "boards" / "panel.toml"

        def config(self):
            return load(dst / "edakit.toml")

        def edit(self, old, new):
            text = self.plan_file.read_text()
            assert old in text, old
            self.plan_file.write_text(text.replace(old, new, 1))

        def add(self, text):
            self.plan_file.write_text(self.plan_file.read_text() + "\n" + text)

        def part(self, key):
            return json.loads((dst / "hardware" / "parts" / f"{key}.json").read_text())

        def save_part(self, key, data):
            (dst / "hardware" / "parts" / f"{key}.json").write_text(json.dumps(data, indent=1))

        def graph(self):
            return json.loads((dst / "hardware" / "graph.json").read_text())

        def save_graph(self, g):
            (dst / "hardware" / "graph.json").write_text(json.dumps(g, indent=1))

        def result(self, currents=None):
            cfg = self.config()
            board = cfg.boards["panel"]
            return perfboard.check(cfg, board, currents=currents or {})

        def found(self, currents=None):
            """[(code/grade, severity, text)] of the plan."""
            return [(f"{f.code}/{f.grade}" if f.grade else f.code, f.severity, f.text)
                    for f in self.result(currents).findings]

        def errors(self, currents=None):
            return [(c, t) for c, s, t in self.found(currents) if s == "error"]
    return P()


def codes(found):
    return sorted({c for c, *_ in found})


# --- LR.1: the kinds -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["pad-per-hole", "3-hole-strips"])
def test_each_kind_reads_and_names_its_sources(name):
    kind = perfboard.load_kind(name)
    assert perfboard.kind_problems(kind) == []
    assert kind["pitch_mm"] == 2.54 and kind["sources"] and kind["tolerance"]["lead_bend_mm"] > 0


def test_the_kinds_are_the_two_the_owner_has():
    assert perfboard.kind_names() == ["3-hole-strips", "pad-per-hole"]


def test_a_kind_without_a_source_for_its_current_or_with_bad_groups_is_refused():
    kind = perfboard.load_kind("pad-per-hole")
    assert any("copper.max_a without its source" in p for p in perfboard.kind_problems(
        {**kind, "copper": {"max_a": 1.0, "source": ""}}))
    assert any(p.startswith("groups must be") for p in perfboard.kind_problems({**kind, "groups": "rows"}))
    with pytest.raises(perfboard.PlanError, match="perfboard kind 'stripboard' is not in edakit/perfboards"):
        perfboard.load_kind("stripboard")


def test_the_cut_list_counts_in_whole_millimetres():
    """Decision 22 as the owner changed it on 2026-11-10: no 5 mm steps, and no fraction of a millimetre either – the
    kinds' step is 1 mm, a step or a strip of a fraction is refused, a plan's cut_step_mm may only be coarser."""
    kind = perfboard.load_kind("pad-per-hole")
    assert kind["wires"]["step_mm"] == 1 == perfboard.load_kind("3-hole-strips")["wires"]["step_mm"]
    for key, v in (("step_mm", 0.5), ("strip_mm", 2.5), ("step_mm", 0)):
        assert f"wires.{key} must be a whole number of mm >= 1, not {v!r}" in perfboard.kind_problems(
            {**kind, "wires": {**kind["wires"], key: v}})
    with pytest.raises(perfboard.PlanError, match="cut_step_mm must be a whole number of mm >= 1, not 2.5"):
        perfboard.read_plan({"perfboard": {"kind": "pad-per-hole", "holes": [3, 3], "cut_step_mm": 2.5}}, "x")
    assert perfboard.read_plan({"perfboard": {"kind": "pad-per-hole", "holes": [3, 3], "cut_step_mm": 5.0}},
                               "x").cut_step_mm == 5


def test_three_hole_strips_join_runs_of_three_along_a_row():
    plan = perfboard.read_plan({"perfboard": {"kind": "3-hole-strips", "holes": [7, 2]}}, "x.toml")
    assert plan.group_of((0, 1)) == plan.group_of((2, 1)) != plan.group_of((3, 1))
    assert plan.group_holes(plan.group_of((6, 2))) == [(6, 2)]       # the last strip of a row cut short
    assert perfboard.read_plan({"perfboard": {"kind": "pad-per-hole", "holes": [3, 3]}}, "x").group_of((0, 1)) is None


def test_holes_are_named_as_the_board_prints_them():
    assert [perfboard.hole_name((c, 1)) for c in (0, 25, 26, 32)] == ["A1", "Z1", "AA1", "AG1"]
    assert perfboard.parse_hole("AG16") == (32, 16)
    with pytest.raises(perfboard.PlanError, match="'R-8' is not a hole"):
        perfboard.parse_hole("R-8")


# --- LR.2: the plan in the board file ------------------------------------------------------------------------------

def test_a_wired_board_takes_a_plan_and_still_no_other_board_file(pb):
    pb.config()
    pb.plan_file.write_text("[order]\n")
    with pytest.raises(ConfigError, match=r"a hand-wired board \(wired = true in \[boards.panel\]\) has no board file "
                                          r"– only the plan of a perfboard"):
        pb.config()


@pytest.mark.parametrize("old, new, message", [
    ('kind = "pad-per-hole"', 'kind = "veroboard"', "perfboard kind 'veroboard' is not in edakit/perfboards"),
    ("holes = [14, 8]", "holes = [14]", r"holes = \[columns, rows\]"),
    ('J1 = { at = "A4", rot = 270 }', 'J1 = { at = "A4", rot = 45 }', "place.J1.rot must be 0, 90, 180 or 270"),
    ('D1 = { anode = "L2", cathode = "L3" }', 'D1 = { anode = "L2", cathode = "L3", rot = 90 }',
     "rot belongs to a part placed with at"),
    ('path = ["F2", "G2"]', 'path = ["F2", "G 2"]', "'G 2' is not a hole"),
    ('color = "black"', 'colour = "black"', r"wire\[4\]: unknown key colour"),
    ("[[holes]] ", "[[holes]] \nr = 1.6", r"holes\[0\]: unknown key r"),
])
def test_a_plan_that_is_not_well_formed_stops_edakit(pb, old, new, message):
    pb.edit(old, new)
    with pytest.raises(ConfigError, match=message):
        pb.config()


def test_the_clean_plan_makes_the_graphs_nets(pb):
    found = pb.found()
    assert [c for c, s, _ in found if s != "note"] == []
    assert codes(found) == ["PERF.grid/bent"]        # the button's 6.5 x 4.5 mm leads on 7.62 x 5.08 mm


def test_a_bridge_forgotten_is_an_open_net(pb):
    pb.edit('path = ["F2", "G2"]', 'path = ["F2", "F1"]')
    assert pb.errors() == [("PERF.net/open", "LED_SW: open between R1.1 in G2 | SW1.1 in C2, SW1.2 in F2")]


def test_a_bridge_into_the_neighbouring_net_is_a_short_with_the_hole_where_they_meet(pb):
    pb.edit('path = ["A4", "C4"]', 'path = ["A4", "A5"]')     # VCC's bridge down onto J1.2 instead of along row 4
    found = pb.errors()
    assert ("PERF.net/short", "GND: GND (D1.cathode in L3, J1.2 in A5) and VCC (J1.1 in A4) in one piece of "
                              "copper") in found
    assert ("PERF.net/meet", "A5: joins VCC bridge A4–A5 with GND bridge A5–B5 with J1.2 (GND)") in found
    assert ("PERF.net/open", "VCC: open between J1.1 in A4 | SW1.3 in C4, SW1.4 in F4") in found


def test_a_wire_labelled_with_another_net_is_found(pb):
    pb.edit('net = "LED_A"', 'net = "GND"')
    assert ("PERF.net/label", "GND: the bridges K2 L2 joins LED_A, not GND") in pb.errors()


def test_a_part_without_a_place_or_in_no_hole_of_the_board(pb):
    pb.edit('J1 = { at = "A4", rot = 270 }', "")
    assert ("PERF.place/unplaced", "J1: on board panel, but the plan has no place for it") in pb.errors()


def test_a_designator_of_no_part_on_the_board(pb):
    pb.edit("[place]\n", '[place]\nR9 = { at = "M7" }\n')
    assert ("PERF.place/unknown", "R9: in the plan of panel, but not in the graph") in pb.errors()


def test_a_lead_off_the_board(pb):
    pb.edit('J1 = { at = "A4", rot = 270 }', 'J1 = { at = "A8", rot = 270 }')
    assert ("PERF.place/offboard", "J1.2: would sit in A9, off the board's 14 × 8 holes") in pb.errors()


def test_two_leads_in_one_hole(pb):
    pb.edit('R1 = { at = "G2", span = 4 }', 'R1 = { at = "F2", span = 4 }')
    assert ("PERF.place/two", "F2: holds SW1.2 and R1.1 – one lead per hole") in pb.errors()


def test_a_part_by_role_whose_leads_do_not_span_the_holes_named(pb):
    pb.edit('cathode = "L3"', 'cathode = "L4"')
    assert ("PERF.place/role", "D1: its leads lie anode in L3, cathode in L4 – not in the holes the plan names, "
                               "anode in L2, cathode in L4") in pb.errors()


def test_by_role_the_rotation_follows_the_polarity(pb):
    """Decision 14: two LEDs whose cathode is pin 1 on one and pin 2 on the other read alike by role."""
    pb.edit('anode = "L2", cathode = "L3"', 'anode = "L3", cathode = "L2"')
    res = pb.result()
    d1 = res.placed["D1"]
    assert {perfboard.hole_name(h) for h in d1.holes.values()} == {"L2", "L3"}
    assert d1.holes["2"] == perfboard.parse_hole("L3")        # the anode, pin 2, where the plan names it
    assert any(f.code == "PERF.net" and f.grade == "short" for f in res.findings)   # turned round: shorts LED_A, GND


def test_pins_a_part_joins_inside_need_a_well_formed_key(pb):
    e = pb.part("T-HDR2")
    e["joined"] = [["1", "9"]]
    pb.save_part("T-HDR2", e)
    assert ("PERF.net/joined", "J1: joined names pin 9, which the entry does not have") in pb.errors()


def test_a_net_a_plugged_in_module_joins_inside_is_a_note_and_two_groups_in_the_test_list(pb):
    """Decision 19: J1 as a module on sockets with two GND pins joined inside; its pin 3 reaches the LED's cathode
    only through it."""
    e = pb.part("T-HDR2")
    e.update(kind="module", joined=[["2", "3"]])
    e["pins"]["3"] = {"name": "GND", "type": "power", "role": "gnd"}
    e["footprint_data"]["pads"]["3"] = {**e["footprint_data"]["pads"]["2"], "x": 3.81}
    pb.save_part("T-HDR2", e)
    g = pb.graph()
    next(c for c in g["graph"]["components"] if c["designator"] == "J1")["pins"]["3"] = "3"
    next(n for n in g["graph"]["nets"] if n["name"] == "GND")["pins"].append("J1.3")
    pb.save_graph(g)
    pb.edit('path = ["A5", "B5"]', 'path = ["A6", "B6"]')        # the cathode's wire to pin 3 now
    pb.edit('path = ["L4", "L6", "B6", "B5"]', 'path = ["L4", "L7", "B7", "B6"]')
    found = pb.found()
    assert [(c, s) for c, s, _ in found if c.startswith("PERF.net")] == [("PERF.net/inside", "note")]
    assert next(t for c, _, t in found if c == "PERF.net/inside") == (
        "GND: J1.2 in A5 joins the rest only inside the plugged-in module – the test list measures them apart")
    text = perfboard.lists(pb.result(), "t")
    assert "| GND (1) | L3 (D1.cathode) | A6 (J1.GND) |" in text and "plugged in" in text


# --- LR.3: the other checks ----------------------------------------------------------------------------------------

def test_an_smd_part_is_an_error(pb):
    e = pb.part("T-BTN6")
    for p in e["footprint_data"]["pads"].values():
        del p["hole"]
    pb.save_part("T-BTN6", e)
    assert ("PERF.grid/smd", "SW1: SMD pads 1, 2, 3, 4 – a perfboard takes through-hole parts only (decision 3); a "
                             "through-hole part in a variant of its own") in pb.errors()


def test_leads_further_off_the_grid_than_a_lead_bends_are_an_error(pb):
    e = pb.part("T-HDR2")                        # a terminal block at 3.5 mm: three pins, the outer ones 0.85 mm off
    e["pins"]["3"] = {"name": "3", "type": "passive", "role": "3"}
    e["footprint_data"]["pads"] = {n: {**e["footprint_data"]["pads"]["2"], "x": x} for n, x in
                                   (("1", -3.5), ("2", 0.0), ("3", 3.5))}
    pb.save_part("T-HDR2", e)
    pb.edit('J1 = { at = "A4", rot = 270 }', 'J1 = { at = "A3", rot = 270 }')
    assert ("PERF.grid", "J1: leads 0.85 mm off the 2.54 mm grid, more than the 0.8 mm a lead is bent") in pb.errors()


def test_bodies_that_overlap_and_a_body_over_a_lead(pb):
    pb.edit('SW1 = { at = "C2" }', 'SW1 = { at = "E2" }')
    errors = pb.errors()
    assert ("PERF.body", "SW1: its body covers the lead R1.1 in G2") in errors


def test_an_axial_span_too_short_for_its_body(pb):
    pb.edit("span = 4", "span = 3")
    assert ("PERF.body/span", "R1: span 3 holes = 7.62 mm, its body of 6.5 mm and the bends need 9.5 mm") in \
        pb.errors()


def test_a_round_body_is_round(pb):
    """The LED's 5 mm body (LED-TH_BD5.0) leaves the diagonal hole free that its box would cover."""
    res = pb.result()
    assert res.placed["D1"].shapes()[0][0] == "circle"
    assert not perfboard.in_shape(res.plan.centre(perfboard.parse_hole("K4")), res.placed["D1"].shapes()[0])


def test_a_lead_or_a_body_under_the_nut_of_a_mounting_hole(pb):
    pb.edit("x = 32.5\ny = 3.0", "x = 6.35\ny = 11.43")         # on SW1.3 in C4
    errors = pb.errors()
    assert ("PERF.mount", "SW1.3: in C4, under the nut of mounting hole 6.35/11.43") in errors
    assert ("PERF.mount", "SW1: its body reaches into the nut of mounting hole 6.35/11.43 (6 mm)") in errors
    pb.edit("x = 6.35", "x = 40")
    assert ("PERF.mount", "mounting hole 40/11.43: lies off the board (35.6 × 20.3 mm)") in pb.errors()


def test_bridges_that_turn_a_corner(pb):
    pb.edit('path = ["A4", "C4"]', 'path = ["A4", "B4", "B3"]')
    assert ("PERF.wire/corner", "VCC: the bridges A4 … B4 … B3 turn at B4 – bridges run straight; a wire on top "
                                "turns") in pb.errors()


def test_two_rows_of_bridges_that_end_at_right_angles_in_an_empty_hole(pb):
    pb.edit('path = ["A4", "C4"]', 'path = ["A4", "B4"]\n\n[[wire]]\nnet = "VCC"\npath = ["B4", "B3"]\n\n[[wire]]\n'
                                   'net = "VCC"\npath = ["B3", "C3", "C4"]')
    errors = pb.errors()
    assert ("PERF.wire/corner", "B4: bridges turn at this empty hole – they meet at a lead or in the middle of "
                                "another row (decision 16)") in errors


def test_a_bridge_between_holes_that_are_no_neighbours_in_a_row(pb):
    pb.edit('path = ["A4", "C4"]', 'path = ["A4", "C2"]')
    assert any(c == "PERF.wire" and "the bridges A4–C2 do not run along a row or a column" in t
               for c, t in pb.errors())


def test_a_wire_ends_in_a_free_hole_not_in_a_leads(pb):
    pb.edit('path = ["L4", "L6", "B6", "B5"]', 'path = ["L3", "L6", "B6", "B5"]')
    assert ("PERF.wire/end", "GND: the wire ends in L3, where D1.1 is – it goes into a free hole beside it, joined "
                             "by a bridge (decision 17)") in pb.errors()


def test_the_current_against_the_kinds_rating(pb):
    currents = {"GND": {"i_max_a": 0.81}, "VCC": {"i_max_a": 0.02}}
    assert [(c, s) for c, s, _ in pb.found(currents) if c.startswith("PERF.current")] == [
        ("PERF.current/unknown", "note")]
    res_kind = perfboard.load_kind("pad-per-hole")
    cfg = pb.config()
    board = cfg.boards["panel"]
    plan = perfboard.board_plan(cfg, board)
    plan.kind = {**res_kind, "copper": {"max_a": 0.5, "source": "a datasheet"}}
    res = perfboard.check(cfg, board, plan, currents=currents)
    assert [(f.code, f.text) for f in res.findings if f.code == "PERF.current"] == [
        ("PERF.current", "GND: 0.81 A over its bridges and wires, the kind's copper carries 0.5 A")]


def test_the_hand_over_holds_as_on_a_pcb(pb):
    pb.add('[near]\nD1 = "J1"\n')
    assert ("SYNC.plan", "D1: 24.1 mm from J1, more than near_mm 6") in pb.errors()


def test_three_hole_strips_join_what_shares_a_strip(pb):
    pb.edit('kind = "pad-per-hole"', 'kind = "3-hole-strips"')
    assert pb.errors() == []                       # every strip the fixture touches holds one net
    pb.edit('path = ["K2", "L2"]', 'path = ["K2", "K1"]')
    assert pb.errors() == []                       # K2 and L2 share the strip J2–L2: no bridge needed
    pb.edit('R1 = { at = "G2", span = 4 }', 'R1 = { at = "G3", span = 4 }')
    assert ("PERF.net/meet", "strip J3–L3: joins GND bridge L3–L4 with D1.cathode (GND) with R1.2 (LED_A)") in \
        pb.errors()


def test_every_code_is_in_the_catalog():
    import edakit.perfboard as m
    used = set(re.findall(r'"(PERF\.\w+)"', Path(m.__file__).read_text()))
    assert used <= set(catalog.codes()) and "PERF.net" in used


# --- LR.4: drawings and lists --------------------------------------------------------------------------------------

def test_the_command_draws_both_views_and_writes_the_lists(pb, monkeypatch, capsys):
    monkeypatch.chdir(pb.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["perfboard"]) == 0
    out = capsys.readouterr().out
    assert "panel: Lochraster, a pad per hole, 14 × 8 holes, 4 parts, 1 wires, 6 bridges" in out
    d = pb.root / "build" / "edakit" / "perfboard" / "panel"
    top, bottom, build = (d / n for n in ("top.svg", "bottom.svg", "build.md"))
    assert top.read_text().startswith("<svg") and "top view – component side, A1 at the top left" in top.read_text()
    assert "in the orientation of the top view" in bottom.read_text()
    assert '<rect width=' in top.read_text() and 'fill="#ffffff"' in top.read_text()   # its own white ground
    width = float(re.search(r'viewBox="0 0 ([\d.]+)', top.read_text()).group(1))
    assert width >= perfboard.MIN_WIDTH_MM         # a board of 14 columns: the legend's lines still fit beside it
    text = build.read_text()
    for line in ("## Cut list – lengths in whole millimetres, rounded up", "| black | 49 mm | L4–B5 | GND |",
                 "| 8 mm | 1 | A4 … C4 VCC |",
                 "Not cut: the wires' stripped ends make the bridges L3–L4, A5–B5. A lead bent over on the bottom "
                 "makes the bridges F2–G2 (R1's lead in G2), K2–L2 (D1's anode lead in L2).",
                 "holes A4 … C4 VCC (8 mm of bare wire); R1's lead in G2 bent onto the pad of F2; D1's anode lead in L2 "
                 "bent onto the pad of K2. The bridges beside the wires' ends are their stripped ends.",
                 "R1 150 in holes G2–K2 – leave R1's lead in G2 long and unsoldered: bent onto the pad of F2 once the "
                 "leads are in, it is the bridge there.",
                 "D1 red: anode (long lead) in hole L2, cathode (flat) in hole L3",
                 "| LED_SW | C2 (SW1.1) | F2 (SW1.2), G2 (R1.1) |", "item = \"Lochraster, a pad per hole, 14 x 8 holes\""):
        assert line in text, line
    order = [text.index(k) for k in ("**Resistors", "**Insulated wires", "**Buttons", "**LEDs", "**Bridges",
                                     "**Test")]
    assert order == sorted(order)                  # from low to high, the bridges once the leads are in (21)


def test_a_plan_with_errors_fails_the_command(pb, monkeypatch, capsys):
    pb.edit('path = ["F2", "G2"]', 'path = ["F2", "F1"]')
    monkeypatch.chdir(pb.root)
    assert cli.main(["perfboard"]) == 1
    assert "PERF.net/open" in capsys.readouterr().out


def test_a_board_without_a_plan(project, monkeypatch, capsys):
    monkeypatch.chdir(project.root)
    assert cli.main(["perfboard"]) == 1
    assert "no hand-wired board with a plan" in capsys.readouterr().out


def test_the_cut_list_rounds_up_to_its_step(pb):
    pb.edit('holes = [14, 8]', 'holes = [14, 8]\ncut_step_mm = 10')
    cut = perfboard.cutlist(pb.result())
    assert [b["mm"] for b in cut["bare"]] == [10] and [i["mm"] for i in cut["insulated"]] == [50]


def test_a_lead_bends_over_to_its_neighbour(pb):
    """The owner on 2026-11-10: a single bridge to a hole with the lead of an LED, a diode, a capacitor or a resistor
    is that lead bent over on the bottom – an LED's first, a lead once; a button's or a header's pins do not bend.
    What is left is bare wire."""
    cut = perfboard.cutlist(pb.result())
    assert [(perfboard.holes_of(b["wire"]), b["part"], perfboard.hole_name(b["at"]), perfboard.hole_name(b["to"]))
            for b in cut["bent"]] == [("F2–G2", "R1", "G2", "F2"), ("K2–L2", "D1", "L2", "K2")]
    assert [(b["mm"], perfboard.holes_of(b["wire"])) for b in cut["bare"]] == [(8, "A4 … C4")]   # J1 and SW1 do not bend
    assert [perfboard.holes_of(w) for w in cut["by_end"]] == ["L3–L4", "A5–B5"]


def test_a_row_of_bridges_at_a_wires_end_is_its_stripped_end(pb):
    """The owner on 2026-11-10: a straight row of bridges that starts at a wire's end is that wire's stripped end, the
    strip there longer by the row – the black wire ends in C5, and its end runs on along the bottom over B5 to A5."""
    pb.edit('path = ["L4", "L6", "B6", "B5"]', 'path = ["L4", "L6", "C6", "C5"]')
    pb.edit('path = ["A5", "B5"]', 'path = ["A5", "C5"]')
    assert pb.errors() == []
    cut = perfboard.cutlist(pb.result())
    (black,) = cut["insulated"]
    assert black["strips"] == (5, 8) and black["mm"] == 49            # 12 pitches + 5 slack + 5 + 5 + 2.54, up
    assert [perfboard.holes_of(w) for w in cut["by_end"]] == ["L3–L4", "A5 … C5"]
    assert [b["mm"] for b in cut["bare"]] == [8]


def cut_rows(svg):
    """cut.svg's rows in drawing order: (kind, mm, [(rect class, x, width)])."""
    out = []
    for kind, mm, body in re.findall(r'<g data-cut="(\w+)" data-mm="(\d+)">(.*?)</g>', svg, re.S):
        rects = re.findall(r'<rect class="(conductor|insulation)" x="([\d.]+)" y="[\d.]+" width="([\d.]+)"', body)
        out.append((kind, int(mm), [(c, float(x), float(w)) for c, x, w in rects]))
    return out


def test_the_cut_list_is_drawn_at_full_size(pb, monkeypatch, capsys):
    """cut.svg: the cut list at 1:1 – a centimetre ruler over a 1 cm grid, each piece left-aligned at the ruler's
    zero and as long as it is cut, the insulated wires and then the bare pieces each from the longest down, beside
    each its length and, for an insulated wire, what is stripped at its left and right end."""
    monkeypatch.chdir(pb.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["perfboard"]) == 0
    d = pb.root / "build" / "edakit" / "perfboard" / "panel"
    svg = html.unescape((d / "cut.svg").read_text())
    w, h, vw, vh = re.search(r'width="([\d.]+)mm" height="([\d.]+)mm" viewBox="0 0 ([\d.]+) ([\d.]+)"', svg).groups()
    assert (w, h) == (vw, vh)                      # a unit of the drawing is a millimetre on paper
    rows = cut_rows(svg)
    assert [(k, mm) for k, mm, _ in rows] == [("insulated", 49), ("bare", 8)]     # F2–G2, K2–L2: bent leads
    zero = rows[0][2][0][1]
    assert [r[2][0] for r in rows] == [("conductor", zero, 49.0), ("conductor", zero, 8.0)]
    assert rows[0][2][1] == ("insulation", zero + 5, 39.0)            # strip 5 mm at each end
    cm = [float(x) for x in re.findall(r'<line class="cm" x1="([\d.]+)"', svg)]
    assert cm == [zero + 10 * i for i in range(6)]                     # 0 to 5 cm: up to the longest piece, 49 mm
    for text in ("49 mm", "strip 5 mm left at L4, 5 mm right at B5 – black, GND", "A4 … C4 VCC",
                 "A lead bent over on the bottom makes the bridges F2–G2 (R1's lead in G2)",
                 "0 to 5 cm must measure 50 mm on a ruler", "Lengths in whole millimetres, rounded up"):
        assert text in svg, text
    assert "![The cut list at 1:1](cut.svg)" in (d / "build.md").read_text()


def test_the_fixture_is_its_own_design():
    """The fixture's graph and plan are what the module docstring of this file says."""
    cfg = load(FIXTURE / "edakit.toml")
    assert cfg.boards["panel"].wired and set(Design.from_config(cfg).comps) == {"J1", "SW1", "R1", "D1"}
    assert tomllib.loads((FIXTURE / "hardware" / "boards" / "panel.toml").read_text())["perfboard"]["holes"] == [14, 8]


# --- LR.5: stage L of the gate -------------------------------------------------------------------------------------

def gate(pb, monkeypatch, eda=False):
    """`edakit gate` on the fixture, the simulation stubbed (the fixture has no scenarios): (exit code, run folder)."""
    from edakit.sim import run as simrun
    monkeypatch.setattr(simrun, "load_sim_config", lambda cfg: ({}, None))
    monkeypatch.setattr(simrun, "run_all", lambda *a, **k: {"checks": [], "scenarios": [], "findings": [],
                                                           "net_currents": {}})
    monkeypatch.chdir(pb.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    code = cli.main(["gate", *(["--eda"] if eda else [])])
    return code, sorted((pb.root / "build" / "release").iterdir())[-1]


def test_the_plan_is_stage_l_and_its_build_files_are_the_manufacturing_files(pb, monkeypatch):
    """Decision 4: a project whose boards are all hand-wired runs S, L and F without EasyEDA; the plan is stage L,
    its drawings and lists go into fab/<board>/ and the manifest, and M-5 is bound to their fab hash."""
    code, run = gate(pb, monkeypatch)
    text = (run / "protocol.md").read_text()
    stages = text.split("## 1 Stages")[1].split("\n## ")[0]
    assert "stages not run" not in text
    assert "| L Board |" in stages and stages.split("| L Board |")[1].split("\n")[0].endswith("| passed |")
    built = {"top.svg", "bottom.svg", "cut.svg", "build.md"}
    assert {f.name for f in (run / "fab" / "panel").iterdir()} == built
    manifest = json.loads((run / "fab" / "manifest.json").read_text())
    assert set(manifest["files"]) == {f"fab/panel/{n}" for n in built}
    assert set(manifest["fab_layers"]["panel"]) == built and manifest["fab_sha256"]
    assert "M-5" in text and code == 2               # nothing signed in the fixture: M-1, M-5, M-6 open


def test_a_mistake_in_the_plan_fails_stage_l(pb, monkeypatch):
    pb.edit('path = ["F2", "G2"]', 'path = ["F2", "F1"]')
    code, run = gate(pb, monkeypatch)
    text = (run / "protocol.md").read_text()
    assert code == 2 and "PERF.net" in text and "LED_SW: open between" in text


def test_the_plan_is_in_the_layout_hash(pb):
    from edakit.release import gate as g
    cfg = pb.config()
    before = g.layout_hash(cfg)
    assert pb.plan_file in g.layout_files(cfg)
    pb.edit("y = 3.0", "y = 3.5")
    assert g.layout_hash(pb.config()) != before
    e = pb.part("T-LED5")                        # the footprint data of a part on the perfboard counts as well
    e["footprint_data"]["pads"]["2"]["x"] = 1.3
    pb.save_part("T-LED5", e)
    assert g.layout_hash(pb.config()) != before


def test_a_project_without_a_plan_keeps_its_gate(project, monkeypatch):
    """No [perfboard] anywhere: the offline gate runs P, G and E only, as before."""
    from edakit.release import gate as g
    cfg = project.config()
    assert g.layout_files(cfg) == [cfg.resolve(b.file) for b in cfg.made().values()] + [
        f for f in g.layout_files(cfg) if f.name.endswith(".geometry.json")]


# --- LR.7: the example ----------------------------------------------------------------------------------------------

def test_the_example_variant_is_built_from_its_plan(tmp_path, monkeypatch, capsys):
    """coin-cell-led on a perfboard, examples/coin-cell-led/variants/perfboard: the circuit checked, the plan clean, the
    lines the steps page "Build it on a perfboard" quotes printed, its cut list the one of build.md, and the drawings of
    docs/pictures/ the command's – the cut list's from the longest wire down, whatever its colour."""
    shutil.copytree(EXAMPLE, tmp_path / "coin-cell-led", ignore=shutil.ignore_patterns("build"))
    monkeypatch.chdir(tmp_path / "coin-cell-led" / "variants" / "perfboard")
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["check"]) == 0
    capsys.readouterr()
    assert cli.main(["perfboard"]) == 0
    out = capsys.readouterr().out
    page = (ROOT / "docs" / "steps" / "prototype.md").read_text(encoding="utf-8")
    block = re.search(r"```text\n\$ edakit perfboard\n(.*?)```", page, re.S).group(1)
    quoted = [ln.strip() for ln in block.splitlines() if ln.strip() and ln.strip() != "…"]
    assert len(quoted) >= 3 and [q for q in quoted if q not in out] == [], out
    drawn = Path("build/edakit/perfboard/main")
    build, top = (drawn / "build.md").read_text(), (drawn / "top.svg").read_text()
    rows = [ln for ln in page.split("## What you have")[1].splitlines() if ln.startswith("| ")]
    assert len(rows) == 4 and [r for r in rows if r not in build] == [] and "(D1's anode lead in J3)" in build
    # its M-5: a holder fits both ways round – its ends named and marked, no stripe; a wire's end soldered with its lead
    assert "BT1 KH-CR2032-2-1: its + end on hole D10, its − end on hole L10" in build and "(stripe)" not in build
    assert "do not solder it yet" in build and "black, holes J1–N10 GND" in build
    assert ">+<" in top and ">−<" in top and "Capacitor" not in top and "mounting holes" not in top
    assert [(k, mm) for k, mm, _ in cut_rows((drawn / "cut.svg").read_text())][:2] == [("insulated", 52),
                                                                                       ("insulated", 41)]
    assert '<img src="../pictures/perfboard-cut.svg"' in page
    for side in ("top", "bottom", "cut"):
        assert (drawn / f"{side}.svg").read_text() == (ROOT / "docs" / "pictures" / f"perfboard-{side}.svg").read_text()


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_the_example_variant_passes_the_gate(tmp_path, monkeypatch, capsys):
    """Its gate without EasyEDA: stage L is the plan, M-1, M-6 and M-5 signed for the hashes of this state."""
    shutil.copytree(EXAMPLE, tmp_path / "coin-cell-led", ignore=shutil.ignore_patterns("build"))
    monkeypatch.chdir(tmp_path / "coin-cell-led" / "variants" / "perfboard")
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    code = cli.main(["gate"])
    out = capsys.readouterr().out
    assert code == 0 and "\nRELEASED" in out, out

