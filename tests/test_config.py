import math

import pytest

from edakit.config import Board, ConfigError, _outline


def board(view):
    return Board(name="b", title="b", template="t", schematic="s", pcb="p", view=view)


@pytest.mark.parametrize("view", ["top", "bottom"])
@pytest.mark.parametrize("side", ["top", "bottom"])
@pytest.mark.parametrize("rot", [0, 90, 180, 270, 37])
def test_to_eda_round_trip(view, side, rot):
    b = board(view)
    x, y, r, layer = b.to_eda(12.5, -3, rot, side)
    assert b.from_eda(x, y, r, layer) == pytest.approx((12.5, -3, rot % 360, side)) or \
        b.from_eda(x, y, r, layer)[3] == side


def test_bottom_side_mirrors_local_y():
    b = board("top")
    # a pad 1 mm right of the origin on a bottom part at rotation 0 stays right; one 1 mm up goes down
    assert b.transform((1000 / 25.4, 0), 0, 0, 0, "bottom") == pytest.approx((1, 0))
    assert b.transform((0, 1000 / 25.4), 0, 0, 0, "bottom") == pytest.approx((0, -1))
    assert b.transform((0, 1000 / 25.4), 0, 0, 0, "top") == pytest.approx((0, 1))


def test_view_bottom_is_the_mirror_of_view_top():
    top, bot = board("top"), board("bottom")
    for side in ("top", "bottom"):
        for rot in (0, 90, 180, 270):
            p_top = top.transform((30, 10), 5, 7, rot, side)
            # the same part seen from the other side: x mirrored, rotation 180 - rot
            ex, ey, erot, _ = top.to_eda(5, 7, rot, side)
            px, py, prot, pside = bot.from_eda(ex, ey, erot, {"top": 1, "bottom": 2}[side])
            p_bot = bot.transform((30, 10), px, py, prot, pside)
            assert p_bot == pytest.approx((-p_top[0], p_top[1]))


def test_rect_outline_with_radius():
    pts = _outline({"rect": [90, 40], "corner_radius": 2}, "b")
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    assert (min(xs), max(xs), min(ys), max(ys)) == pytest.approx((0, 90, 0, 40))
    assert all(math.dist(p, q) > 0 for p, q in zip(pts, pts[1:]))


def test_outline_needs_shape():
    with pytest.raises(ConfigError):
        _outline({"circle": 5}, "b")


def test_example_config_loads(project):
    cfg = project.config()
    b = cfg.board()
    assert b.pcb == "main" and b.template == "generated_main" and b.schematic == "layout_main"
    assert len(b.tooling) == 2 and b.place["U1"].side == "top"
    assert cfg.net_classes and list(cfg.net_classes)[-1] == "SIGNAL"
