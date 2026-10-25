"""Board label: title and revision in the free spot nearest to the requested corner."""

from types import SimpleNamespace

from shapely.geometry import Point, box

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
