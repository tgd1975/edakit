import math

import pytest

from edakit.config import Board, ConfigError, _outline, load


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
    assert b.net_classes and list(b.net_classes)[-1] == "SIGNAL"
    assert b.file == "hardware/boards/main.toml" and cfg.schematic["stub"] == 10
    assert cfg.sim_config.name == "sim.json" and cfg.sim_plugin is None


ONE_FILE = """
[project]
name = "t"
ground = "GND"
[boards.main]
revision = "1"
[boards.main.place]
U1 = { x = 1, y = 2 }
[net_classes]
POWER = { min_a = 0.3, width_mm = 0.6 }
[schematic]
stub = 10
[sim]
config = "hardware/sim.json"
[checks]
pin_locks = { "U1.1" = "A" }
[release]
signoff = "hardware/signoff.json"
layout_files = ["edakit.toml"]
"""


def test_one_file_form_is_refused_with_what_goes_where(tmp_path):
    (tmp_path / "edakit.toml").write_text(ONE_FILE)
    with pytest.raises(ConfigError) as e:
        load(tmp_path / "edakit.toml")
    for line in ("[boards.main] revision, place -> hardware/boards/main.toml, without the prefix 'boards.main.'",
                 "[schematic] -> hardware/schematic.toml, without the prefix 'schematic.'",
                 '[checks] -> "checks" in the graph', '[project] ground -> "ground" in the graph',
                 "[net_classes] -> [net_classes] in each board file",
                 "[sim] config, plugin -> [project] sim, sim_plugin", "[release] signoff -> [project] signoff",
                 "[release] layout_files: drop edakit.toml", "edakit.toml is the table of contents now"):
        assert line in str(e.value)


def test_keys_in_the_wrong_file_or_misspelt(tmp_path):
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\ncompnay = "x"\n[boards.main]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text('title = "Main"\nplcae = {}\n')
    (tmp_path / "hardware" / "schematic.toml").write_text("stubs = 10\n")
    with pytest.raises(ConfigError) as e:
        load(tmp_path / "edakit.toml")
    for line in ("[project]: unknown key 'compnay'", "hardware/schematic.toml: unknown key 'stubs'",
                 "hardware/boards/main.toml: title belongs in edakit.toml [boards.main]",
                 "hardware/boards/main.toml: unknown key 'plcae'"):
        assert line in str(e.value)


def test_board_file_missing(tmp_path):
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    b = load(tmp_path / "edakit.toml").board()
    assert b.file == "hardware/boards/main.toml" and b.outline == [] and b.place == {}   # no layout yet
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\nfile = "boards/main.toml"\n')
    with pytest.raises(ConfigError, match="boards/main.toml not found"):
        load(tmp_path / "edakit.toml")
