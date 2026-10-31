"""Board label: title and revision in the free spot nearest to the requested corner, on a chosen side, inside a region;
designators of through-hole parts on their solder side; designators at a fixed spot ([silk] place)."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from edakit import config, gerber, silk
from edakit.config import BOTTOM, TOP
from edakit.silk import board_label_text, corner_spot


def test_label_text_needs_a_revision():
    cfg = SimpleNamespace(project="bell")
    board = SimpleNamespace(name="main", title="Christmas bell", revision="1.0", silk={})
    assert board_label_text(cfg, board) == "Christmas bell rev 1.0"
    board.silk = {"board_label": "{project} {board} {revision}"}
    assert board_label_text(cfg, board) == "bell main 1.0"
    board.revision = None
    assert board_label_text(cfg, board) is None


def test_spot_nearest_to_the_corner_and_clear_of_obstacles():
    area = box(0, 0, 80, 50)
    hole = Point(3.5, 3.5).buffer(4.8)
    x, y = corner_spot(area, hole, 16, 1.2)
    assert not box(x - 8, y - 0.6, x + 8, y + 0.6).intersects(hole)
    assert y < 10 and x < 30                                   # still in the lower left
    x, y = corner_spot(area, hole, 16, 1.2, "bottom-right")
    assert x > 60 and y < 2


def test_no_room():
    assert corner_spot(box(0, 0, 10, 5), box(0, 0, 10, 5), 4, 1) is None


# --- designators of through-hole parts on their solder side (#16): R1 SMD on top, R2 SMD and D1 through-hole on the
# bottom, designators on top. `silk.apply` against a stand-in for EasyEDA and the Gerber export.

MIL = 1000 / 25.4
COMPS = {"c1": ("R1", TOP, (9, 9.5, 11, 10.5)), "c2": ("R2", BOTTOM, (19, 9.5, 21, 10.5)),
         "c3": ("D1", BOTTOM, (27.5, 7.5, 32.5, 12.5))}                   # id: designator, layer, box (mm)
PADS = {"c1e1": TOP, "c1e2": TOP, "c2e1": BOTTOM, "c2e2": BOTTOM, "c3e1": 12, "c3e2": 12}  # id: layer, 12 through-hole
TOP_OPENINGS = unary_union([box(9, 9.5, 9.6, 10.5), box(10.4, 9.5, 11, 10.5),               # R1's pads, D1's joints
                            Point(28.73, 10).buffer(0.9), Point(31.27, 10).buffer(0.9)])
BOTTOM_OPENINGS = unary_union([box(19, 9.5, 19.6, 10.5), box(20.4, 9.5, 21, 10.5),         # R2's pads, D1's joints
                               Point(28.73, 10).buffer(0.9), Point(31.27, 10).buffer(0.9)])
BOTTOM_PRINT = box(33, 0.5, 39.5, 3)                    # print already on the bottom, in its lower right corner


def project(path, table, head=""):
    """A project with one board of 40 x 20 mm and the given [silk] table -> its configuration."""
    (path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    (path / "hardware" / "boards").mkdir(parents=True, exist_ok=True)
    (path / "hardware" / "boards" / "main.toml").write_text(head + "[outline]\nrect = [40, 20]\n[silk]\n" + table)
    return config.load(path / "edakit.toml")


@pytest.fixture
def silk_run(tmp_path, monkeypatch):
    """-> run(the [silk] table) -> the API calls of `silk.apply` on the three parts."""
    calls = []

    def api(mcp, name, *args):
        calls.append((name, args))
        if name == "PCB_PrimitiveComponent.getAll":
            return [{"state": {"PrimitiveId": i, "Designator": d, "Layer": la}} for i, (d, la, _) in COMPS.items()]
        if name == "PCB_PrimitiveAttribute.getAll":
            return [{"state": {"PrimitiveId": "a" + i, "ParentPrimitiveId": i, "Key": "Designator",
                               "ValueVisible": True}} for i in COMPS]
        if name == "PCB_PrimitivePad.getAll":
            return [{"state": {"PrimitiveId": i, "Layer": la}} for i, la in PADS.items()]
        if name == "PCB_Primitive.getPrimitivesBBox":
            x0, y0, x1, y1 = (v * MIL for v in COMPS[args[0][0]][2])
            return {"minX": x0, "minY": y0, "maxX": x1, "maxY": y1}
        return {"PrimitiveId": f"s{len(calls)}"} if name.endswith(".create") else []
    shapes = {gerber.FILES["top_mask"]: TOP_OPENINGS, gerber.FILES["bottom_mask"]: BOTTOM_OPENINGS,
              gerber.FILES["bottom_silk"]: BOTTOM_PRINT}                     # no footprint silk on top, nothing else
    monkeypatch.setattr(silk, "gerber", SimpleNamespace(FILES=gerber.FILES, parse_gerber=lambda p: Path(p).name,
                                                        shape=lambda name: shapes.get(name, Polygon())))
    monkeypatch.setattr(silk, "api", api)
    monkeypatch.setattr(silk, "ensure_pcb_focus", lambda mcp: None)
    monkeypatch.setattr(silk, "export_gerber", lambda cfg, board, mcp: tmp_path)
    monkeypatch.setattr(silk, "check", lambda *a, **k: 0)
    monkeypatch.setattr(silk.eda, "save_pcb", lambda mcp: None)

    def run(table, head="", code=0):
        cfg = project(tmp_path, table, head)
        calls.clear()
        assert silk.apply(cfg, cfg.board(), None) == code
        return list(calls)
    return run


def test_apply_keeps_the_print_it_did_not_place(silk_run, tmp_path):
    """The silk files of the first export – before edakit prints – stay for the gate (GEO.silk)."""
    for key in ("top_silk", "bottom_silk"):
        (tmp_path / gerber.FILES[key]).write_text(f"{key} before apply")
    silk_run('designators = "top"\n')
    kept = tmp_path / "build" / "edakit" / "silk_footprints_main"
    assert {p.name: p.read_text() for p in kept.iterdir()} == {
        gerber.FILES["top_silk"]: "top_silk before apply", gerber.FILES["bottom_silk"]: "bottom_silk before apply"}


def strings(calls):
    """The free texts created: {text: (layer, x mm, y mm, rotation)}."""
    return {a[3]: (a[0], a[1] / MIL, a[2] / MIL, a[8]) for name, a in calls if name == "PCB_PrimitiveString.create"}


def shown(calls):
    return {a[0] for name, a in calls if name == "PCB_PrimitiveAttribute.modify" and a[1].get("valueVisible")}


def test_through_hole_parts_of_the_other_side_get_their_designator_on_the_solder_side(silk_run):
    calls = silk_run('designators = "top"\nhide = ["bottom"]\nsolder_side = true\n')
    texts = strings(calls)
    assert set(texts) == {"D1"}            # before: no label for D1; R2, SMD on the bottom, gets none either way
    layer, x, y, rot = texts["D1"]
    assert layer == TOP + 2                 # the top silkscreen, in the designators' stroke font and height
    label = silk.label_box(x, y, rot, *silk.label_size("D1", 1.0))
    assert not label.intersects(TOP_OPENINGS.buffer(0.15))                     # clear of its solder joints
    assert label.distance(box(*COMPS["c3"][2])) == pytest.approx(0.25, abs=0.01)  # next to its box, gap_mm away
    assert shown(calls) == {"ac1"}          # R1's designator is moved as before; D1's stays hidden on the bottom


def test_without_solder_side_only_the_designators_side_is_labelled(silk_run):
    calls = silk_run('designators = "top"\nhide = ["bottom"]\n')
    assert strings(calls) == {}
    assert shown(calls) == {"ac1"}
    assert all(name != "PCB_PrimitivePad.getAll" for name, _ in calls)        # no extra call without the key


def test_solder_side_selects_the_through_hole_parts_of_the_other_side():
    parts = {"R1": (TOP, False), "R2": (BOTTOM, False), "D1": (BOTTOM, True)}  # designator: layer, through-hole
    assert silk.label_parts(parts, TOP) == ["R1"]                               # as before
    assert silk.label_parts(parts, TOP, solder_side=True) == ["D1", "R1"]
    assert silk.label_parts(parts, BOTTOM, solder_side=True) == ["D1", "R2"]


# --- the board label on a chosen side, inside a region (#17): the same three parts, revision 2, the label "main rev 2"
# 1.2 mm high; designators on top

LABEL = "main rev 2"


def board_label(calls):
    """(layer, its box) of the board label created, or None."""
    t = strings(calls).get(LABEL)
    return t and (t[0], silk.label_box(t[1], t[2], t[3], silk.label_size(LABEL, 1.2)[0], 1.2))


def test_board_label_without_the_new_keys_stays_where_it_was(silk_run):
    calls = silk_run('designators = "top"\n', head='revision = "2"\n')
    layer, b = board_label(calls)
    assert layer == TOP + 2
    assert b.centroid.x == pytest.approx(6.24, abs=0.01) and b.centroid.y == pytest.approx(1.10, abs=0.01)
    assert [a for name, a in calls if name == "PCB_Primitive.getPrimitivesBBox"] == [(["c1"],)]   # no extra call


def test_board_label_on_the_other_side_keeps_clear_of_that_side(silk_run):
    layer, b = board_label(silk_run('designators = "top"\nboard_label_side = "bottom"\n', head='revision = "2"\n'))
    assert layer == BOTTOM + 2                  # before: on top, with the designators
    assert not b.intersects(unary_union([BOTTOM_PRINT.buffer(0.15), BOTTOM_OPENINGS.buffer(0.15),
                                         box(*COMPS["c2"][2]), box(*COMPS["c3"][2])]))
    assert b.centroid.x > 20 and b.centroid.y < 6   # bottom-left as seen from the bottom: the lower right from the top


def test_board_label_inside_its_region(silk_run):
    region = "board_label_region = [[0, 14], [40, 14], [40, 20], [0, 20]]\n"      # the upper 6 mm
    layer, b = board_label(silk_run('designators = "top"\n' + region, head='revision = "2"\n'))
    assert layer == TOP + 2
    assert box(0, 14, 40, 20).buffer(0.001).contains(b)   # before: at (6.2, 1.1) mm, at the bottom of the board
    assert b.bounds[0] < 1 and b.bounds[1] < 14.6   # in the bottom-left corner of the region


def test_board_label_without_room_in_its_region_is_said(silk_run, capsys):
    region = "board_label_region = [[2, 8.5], [18, 8.5], [18, 11.5], [2, 11.5]]\n"  # 16 x 3 mm, R1 across it
    assert board_label(silk_run('designators = "top"\n' + region, head='revision = "2"\n')) is None
    assert "board label 'main rev 2': no free spot" in capsys.readouterr().out    # before: placed outside the region



def test_board_label_on_the_other_side_inside_its_region(silk_run):
    region = "board_label_region = [[0, 14], [40, 14], [40, 20], [0, 20]]\n"
    layer, b = board_label(silk_run('designators = "top"\nboard_label_side = "bottom"\n' + region,
                                    head='revision = "2"\n'))
    assert layer == BOTTOM + 2 and box(0, 14, 40, 20).buffer(0.001).contains(b)
    assert b.bounds[2] > 39 and b.bounds[1] < 14.6   # the region's bottom-left corner as seen from the bottom


def test_board_label_region_is_in_plan_mm():
    from edakit.config import _board
    board = _board("b", {}, {"view": "bottom", "outline": {"rect": [40, 20]},
                             "silk": {"board_label_region": [[0, 0], [10, 0], [10, 5], [0, 5]]}})
    area = silk.board_shape(board).buffer(-0.5)                             # EasyEDA x from -40 to 0: seen from below
    assert silk.board_label_area(board, area).bounds == pytest.approx((-10, 0.5, -0.5, 5))
    board.silk = {}
    assert silk.board_label_area(board, area) is area                      # no region: the whole board, as before


# --- designators at a fixed spot ([silk] place, step 2.3): the same three parts. A row puts a designator where the
# board file says (plan mm – EasyEDA mm here, the plan is seen from the top), silk apply places the rest around it. On a
# pad, beyond the board or on another text it is a finding, as silk apply keeps a placed one clear of them.

def moved(calls):
    """The designators moved: {attribute id: (x mm, y mm, rotation)}."""
    return {a[0]: (a[1]["x"] / MIL, a[1]["y"] / MIL, a[1]["rotation"]) for name, a in calls
            if name == "PCB_PrimitiveAttribute.modify" and "x" in a[1]}


def test_a_fixed_designator_goes_where_the_board_file_says(silk_run):
    calls = silk_run('designators = "top"\n[silk.place]\nR1 = { x = 5, y = 15, rot = 90 }\n')
    assert moved(calls) == {"ac1": pytest.approx((5, 15, 90), abs=0.001)}    # before: above R1, at (10, 11.5), lying
    assert shown(calls) == {"ac1"} and strings(calls) == {}


def test_the_rest_is_placed_around_a_fixed_designator(silk_run):
    """D1's label (solder_side) goes above its box, at (30, 13.5) – R1's fixed label takes that spot."""
    calls = silk_run('designators = "top"\nhide = ["bottom"]\nsolder_side = true\n'
                     '[silk.place]\nR1 = { x = 30, y = 13.5 }\n')
    assert moved(calls)["ac1"] == pytest.approx((30, 13.5, 0), abs=0.001)
    _, x, y, rot = strings(calls)["D1"]
    fixed = silk.label_box(30, 13.5, 0, *silk.label_size("R1", 1.0))
    assert silk.label_box(x, y, rot, *silk.label_size("D1", 1.0)).distance(fixed) > 0.2   # before: right under R1's
    assert silk.label_box(x, y, rot, *silk.label_size("D1", 1.0)).distance(box(*COMPS["c3"][2])) == pytest.approx(
        0.25, abs=0.01)                                                                   # still next to D1


def test_the_board_label_keeps_clear_of_a_fixed_designator(silk_run):
    layer, b = board_label(silk_run('designators = "top"\n[silk.place]\nR1 = { x = 6, y = 1.5 }\n',
                                    head='revision = "2"\n'))
    assert layer == TOP + 2
    assert b.distance(silk.label_box(6, 1.5, 0, *silk.label_size("R1", 1.0))) > 0.3   # before: at (6.2, 1.1), under it


R1_BODY = box(8, 8, 12, 12)            # a body over R1's footprint box (9, 9.5, 11, 10.5), from body.box of its entry


def test_a_body_larger_than_its_footprint_keeps_the_designator_off(silk_run, monkeypatch, capsys):
    """Walkthrough gaps B3: BT1's designator went right above its footprint box, under the coin cell. With a body
    larger than the footprint (body.box), the label goes beside the body; a fixed one under it is a finding."""
    monkeypatch.setattr(silk, "part_bodies", lambda cfg, comps: {"R1": R1_BODY} if "R1" in comps else {})
    x, y, rot = moved(silk_run('designators = "top"\n'))["ac1"]            # before: above R1, at (10, 11.5)
    label = silk.label_box(x, y, rot, *silk.label_size("R1", 1.0))
    assert not label.intersects(R1_BODY) and label.distance(R1_BODY) == pytest.approx(0.25, abs=0.01)
    capsys.readouterr()
    silk_run('designators = "top"\n[silk.place]\nR1 = { x = 10, y = 11.5 }\n', code=2)
    assert "  ! R1: fixed designator under the body of R1 (top) – " in capsys.readouterr().out
    monkeypatch.setattr(silk, "part_bodies", lambda cfg, comps: {})       # no body.box: as before, under the body
    x, y, rot = moved(silk_run('designators = "top"\n'))["ac1"]
    label = silk.label_box(x, y, rot, *silk.label_size("R1", 1.0))
    assert label.intersects(R1_BODY) and label.distance(box(*COMPS["c1"][2])) == pytest.approx(0.25, abs=0.01)


def test_a_fixed_designator_on_its_part_s_side_moves_that_part_s_own(silk_run):
    """R2 sits on the bottom, whose designators silk apply hides; side = "bottom" shows R2's own one there."""
    calls = silk_run('designators = "top"\nhide = ["bottom"]\n[silk.place]\nR2 = { x = 20, y = 5, side = "bottom" }\n')
    assert moved(calls)["ac2"] == pytest.approx((20, 5, 0), abs=0.001)        # before: hidden
    assert shown(calls) == {"ac1", "ac2"} and strings(calls) == {}


def test_a_fixed_designator_on_the_other_side_of_its_part_is_a_free_text(silk_run):
    """A designator prints only on its part's side: D1 (bottom) labelled on top without solder_side, R1 (top) on the
    bottom – both free texts, as with solder_side, and nowhere else."""
    calls = silk_run('designators = "top"\nhide = ["bottom"]\n[silk.place]\nD1 = { x = 30, y = 16 }\n'
                     'R1 = { x = 10, y = 6, side = "bottom" }\n')
    texts = strings(calls)
    assert texts["D1"] == pytest.approx((TOP + 2, 30, 16, 0), abs=0.001)      # before: no label for D1
    assert texts["R1"] == pytest.approx((BOTTOM + 2, 10, 6, 0), abs=0.001)    # before: R1's own, placed on top
    assert shown(calls) == set()


def test_a_fixed_designator_prints_nowhere_else(silk_run):
    """Without hide the bottom keeps its designators – but D1's name goes to the top, so its own one is hidden."""
    calls = silk_run('designators = "top"\n[silk.place]\nD1 = { x = 30, y = 16 }\n')
    hidden = {a[0] for name, a in calls if name == "PCB_PrimitiveAttribute.modify" and a[1] == {"valueVisible": False}}
    assert hidden == {"ac1", "ac3"}        # before: ac1 only – R1's, hidden first and shown at its spot; R2's stays
    assert strings(calls)["D1"] == pytest.approx((TOP + 2, 30, 16, 0), abs=0.001)


@pytest.mark.parametrize("rows, finding", [
    ("R1 = { x = 10, y = 10 }\n", "R1: fixed designator on a pad (top) – "),                       # on its own pads
    ("R1 = { x = 39.5, y = 15 }\n", "R1: fixed designator beyond the printable board (top) – "),    # half off the board
    ('R1 = { x = 20, y = 15.5 }\n[[silk.texts]]\ntext = "START"\nx = 20\ny = 15\n',
     "R1 / START: fixed designator on the text (top) – "),
    ('R1 = { x = 20, y = 16.73 }\n[[silk.texts]]\ntext = "START"\nx = 20\ny = 15\n',
     "R1 / START: fixed designator 0.11 mm from the text (top) – "),
    ("R1 = { x = 5, y = 15 }\nD1 = { x = 6, y = 15 }\n", "D1 / R1: fixed designators overlap (top) – "),
    ('R2 = { x = 20, y = 10, side = "bottom" }\n', "R2: fixed designator on a pad (bottom) – "),   # its own pads there
    ("R9 = { x = 5, y = 15 }\n", "R9: in [silk] place, but no part of this board"),
])
def test_a_fixed_designator_in_the_way_is_a_finding(silk_run, capsys, rows, finding):
    silk_run('designators = "top"\nhide = ["bottom"]\n[silk.place]\n' + rows, code=2)     # before: exit 0
    assert f"  ! {finding}" in capsys.readouterr().out


def test_a_fixed_designator_in_the_way_is_written_all_the_same(silk_run):
    calls = silk_run('designators = "top"\n[silk.place]\nR1 = { x = 10, y = 10 }\nR9 = { x = 5, y = 15 }\n', code=2)
    assert moved(calls) == {"ac1": pytest.approx((10, 10, 0), abs=0.001)}     # where the board file says; R9 nowhere
    assert strings(calls) == {}


def test_place_labels_takes_the_fixed_ones_as_given():
    parts = {"R1": (9, 9.5, 11, 10.5), "R2": (19, 9.5, 21, 10.5)}
    blocked = unary_union([box(*bb) for bb in parts.values()])
    args = blocked, Polygon(), box(0, 0, 40, 20), 1.0, 0.25
    before, _, _ = silk.place_labels(parts, *args)
    placed, grouped, missing = silk.place_labels(parts, *args, fixed={"R2": before["R1"]})   # R2 where R1's would go
    assert placed["R2"] == before["R1"] and placed["R1"] != before["R1"]
    r1, r2 = (silk.label_box(*placed[r], *silk.label_size(r, 1.0)) for r in ("R1", "R2"))
    assert r1.distance(r2) > 0.2 and not r1.intersects(blocked)
    assert (grouped, missing) == (set(), [])


def test_fixed_findings_without_anything_in_the_way():
    assert silk.fixed_findings({"R1": (5, 15, 0), "R2": (5, 12, 90)}, 1.0, box(0, 0, 40, 20), TOP_OPENINGS, []) == []


def test_preview_draws_the_fixed_designators_and_names_what_is_in_their_way(silk_run, tmp_path, capsys):
    cfg = project(tmp_path, 'designators = "top"\n[silk.place]\nR1 = { x = 10, y = 10 }\nD1 = { x = 30, y = 16 }\n')
    folder = tmp_path / "build" / "edakit" / "gerber_main"
    folder.mkdir(parents=True)
    (folder / gerber.FILES["top_silk"]).write_text("")                     # the last export of silk apply or check
    assert silk.preview(cfg, cfg.board()) == 2                              # before: 0, and nothing to draw
    out = capsys.readouterr().out
    assert "  top: artwork 0 mm², 0 texts, 2 fixed designators (blue boxes) -> " in out
    assert "  ! R1: fixed designator on a pad (top) – " in out and "D1:" not in out
    assert (tmp_path / "build" / "edakit" / "silk_preview_main_top.png").exists()


def test_a_fixed_designator_leaves_its_group():
    """Three resistors too close for three labels share one; with R2 fixed elsewhere R1 and R3 have room each."""
    parts = {"R1": (10, 9.5, 11, 10.5), "R2": (11.3, 9.5, 12.3, 10.5), "R3": (12.6, 9.5, 13.6, 10.5)}
    args = unary_union([box(*bb) for bb in parts.values()]), Polygon(), box(8.5, 8.9, 15, 16), 1.0, 0.25
    groups = {"R1-R3": ["R1", "R2", "R3"]}
    placed, grouped, _ = silk.place_labels(parts, *args, groups)
    assert set(placed) == {"R1-R3"} and grouped == {"R1", "R2", "R3"}
    placed, grouped, missing = silk.place_labels(parts, *args, groups, fixed={"R2": (11.8, 14.5, 0)})
    assert set(placed) == {"R1", "R2", "R3"} and placed["R2"] == (11.8, 14.5, 0)
    assert (grouped, missing) == (set(), [])


def test_label_box_lies_at_0_and_180_degrees_and_stands_at_90_and_270():
    assert silk.label_box(0, 0, 180, 4, 1).bounds == pytest.approx((-2, -0.5, 2, 0.5))   # before: standing
    assert silk.label_box(0, 0, 270, 4, 1).bounds == pytest.approx((-0.5, -2, 0.5, 2))
    turned = silk.label_box(0, 0, 45, 4, 1)                                                # before: standing
    assert turned.area == pytest.approx(4) and turned.bounds == pytest.approx((-1.768, -1.768, 1.768, 1.768), abs=0.001)


def test_fixed_labels_are_plan_mm_on_the_designators_side():
    """Seen from below, plan x is EasyEDA's -x (as [place]); the rotation goes to EasyEDA as written (as for
    [[silk.texts]]); side defaults to the designators side."""
    from edakit.config import _board
    board = _board("b", {}, {"view": "bottom", "outline": {"rect": [40, 20]}, "silk": {
        "designators": "bottom", "place": {"R4": {"x": 12.5, "y": 3, "rot": 90}, "LED1": {"x": 5, "y": 3, "side": "top"}}}})
    assert silk.fixed_labels(board) == {"R4": (-12.5, 3, 90, "bottom"), "LED1": (-5, 3, 0, "top")}
    board.silk = {}
    assert silk.fixed_labels(board) == {}                                  # no key: none
