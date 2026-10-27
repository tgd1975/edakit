"""Board label: title and revision in the free spot nearest to the requested corner, on a chosen side, inside a region;
designators of through-hole parts on their solder side."""

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

    def run(table, head=""):
        (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
        (tmp_path / "hardware" / "boards").mkdir(parents=True, exist_ok=True)
        (tmp_path / "hardware" / "boards" / "main.toml").write_text(head + "[outline]\nrect = [40, 20]\n[silk]\n" + table)
        cfg = config.load(tmp_path / "edakit.toml")
        calls.clear()
        assert silk.apply(cfg, cfg.board(), None) == 0
        return list(calls)
    return run


def test_apply_keeps_the_print_it_did_not_place(silk_run, tmp_path):
    """The silk files of the first export – before edakit prints – stay for the gate (L-17)."""
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
