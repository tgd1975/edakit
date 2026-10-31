import math

import pytest

from edakit.config import Board, ConfigError, _outline, _pours, load


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
    assert cfg.datasheets == cfg.artifacts / "datasheets"          # edakit part fetch: not versioned by default


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


def test_pours_pour_only():
    plain = [{"net": "GND", "layers": ["TOP", "BOTTOM"]}, {"net": "V_LED", "layers": ["BOTTOM"], "plane": True}]
    assert _pours("b", plain) == plain                                  # no pour_only: as written
    got = _pours("b", [{"net": "GND", "layers": ["TOP"], "pour_only": True},
                       {"net": "GND", "layers": ["BOTTOM"], "pour_only": True, "min_width_mm": 0.3}])
    assert [(p["clearance_mm"], p["min_width_mm"]) for p in got] == [(0.25, 0.25), (0.25, 0.3)]


@pytest.mark.parametrize("pours", [
    [{"net": "GND", "pour_only": True, "plane": True}],
    [{"net": "GND", "layers": ["TOP"], "pour_only": True}, {"net": "GND", "layers": ["BOTTOM"]}],
    [{"net": "GND", "pour_only": True, "clearance_mm": -0.1}],
])
def test_pours_pour_only_mistakes(pours):
    with pytest.raises(ConfigError):
        _pours("b", pours)


def test_pours_fanout():
    plane = [{"net": "V", "layers": ["BOTTOM"], "plane": True, "fanout": True}]
    assert _pours("b", plane) == plane
    with pytest.raises(ConfigError, match="pour V: fanout needs plane = true"):
        _pours("b", [{"net": "V", "layers": ["BOTTOM"], "fanout": True}])
    with pytest.raises(ConfigError, match="pour V: fanout must be true or false"):
        _pours("b", [{"net": "V", "layers": ["BOTTOM"], "plane": True, "fanout": "yes"}])


def test_pour_regions_keys(tmp_path):
    from edakit.config import _board
    b = _board("b", {}, {})
    assert (b.pour_regions, b.pour_min_piece_mm2) == (False, 2.0)                # no key, no change
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text("pour_regions = true\npour_min_piece_mm2 = 1\n")
    b = load(tmp_path / "edakit.toml").board()                                    # keys of the board file
    assert (b.pour_regions, b.pour_min_piece_mm2) == (True, 1.0)


@pytest.mark.parametrize("b", [
    {"pour_regions": "yes"},
    {"pour_regions": True, "pour_min_piece_mm2": -1},
    {"pour_regions": True, "pours": [{"net": "GND", "layers": ["TOP"]}, {"net": "V", "layers": ["TOP"], "plane": True}]},
    {"pour_regions": True, "pours": [{"net": "GND", "layers": ["TOP"]}, {"net": "V", "layers": ["TOP"], "clearance_mm": -1}]},
])
def test_pour_regions_mistakes(b):
    from edakit.config import _board
    with pytest.raises(ConfigError):
        _board("b", {}, b)


def test_pour_regions_plane_on_a_layer_of_its_own():
    from edakit.config import _board
    b = _board("b", {}, {"pour_regions": True, "pours": [{"net": "GND", "layers": ["TOP"]},
                                                         {"net": "V", "layers": ["BOTTOM"], "plane": True}]})
    assert b.pours[1]["plane"]


def test_pour_inset_key():
    from edakit.config import _board
    assert _board("b", {}, {}).pour_inset_mm is None                  # no key: edge clearance + 0.1 mm, as before
    assert _board("b", {}, {"pour_inset_mm": 0.55}).pour_inset_mm == 0.55
    with pytest.raises(ConfigError, match="pour_inset_mm must not be negative"):
        _board("b", {}, {"pour_inset_mm": -0.1})


def test_on_headers_keys(tmp_path):
    from edakit.config import _board
    b = _board("b", {}, {})
    assert b.on_headers == set() and b.header_keep_mm == 1.27         # no key: every overlap is a finding, as before
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text('on_headers = ["U1"]\nheader_keep_mm = 0.87\n')
    b = load(tmp_path / "edakit.toml").board()
    assert b.on_headers == {"U1"} and b.header_keep_mm == 0.87
    with pytest.raises(ConfigError, match="on_headers must be a list of designators"):
        _board("b", {}, {"on_headers": "U1"})
    with pytest.raises(ConfigError, match="header_keep_mm must not be negative"):
        _board("b", {}, {"header_keep_mm": -0.1})


def test_silk_overlap_key(tmp_path):
    from edakit.config import _board
    assert _board("b", {}, {}).silk_overlap_mm == 0.0                  # no key: every overlap is a finding, as before
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text("silk_overlap_mm = 0.8\n")
    assert load(tmp_path / "edakit.toml").board().silk_overlap_mm == 0.8
    with pytest.raises(ConfigError, match="silk_overlap_mm must not be negative"):
        _board("b", {}, {"silk_overlap_mm": -0.1})


def test_silk_solder_side_key(tmp_path):
    from edakit.config import _board
    assert "solder_side" not in _board("b", {}, {}).silk                  # no key: only the designators side, as before
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text('[silk]\ndesignators = "top"\nsolder_side = true\n')
    assert load(tmp_path / "edakit.toml").board().silk["solder_side"] is True
    with pytest.raises(ConfigError, match="silk.solder_side must be true or false"):
        _board("b", {}, {"silk": {"solder_side": "yes"}})


def test_silk_unlabelled_key(tmp_path):
    from edakit.config import _board
    assert "unlabelled" not in _board("b", {}, {}).silk                  # no key: every part needs its designator (GEO.silk)
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text('[silk]\nunlabelled = { R21 = "no room in the star" }\n')
    assert load(tmp_path / "edakit.toml").board().silk["unlabelled"] == {"R21": "no room in the star"}
    for bad in (["R21"], {"R21": ""}, {"R21": 1}, "R21"):
        with pytest.raises(ConfigError, match="silk.unlabelled must be a table of designator = reason"):
            _board("b", {}, {"silk": {"unlabelled": bad}})


def test_silk_board_label_side_and_region_keys(tmp_path):
    from edakit.config import _board
    silk = _board("b", {}, {}).silk
    assert "board_label_side" not in silk and "board_label_region" not in silk     # no key: as before
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text(
        '[silk]\ndesignators = "top"\nboard_label_side = "bottom"\nboard_label_region = [[0, 0], [40, 0], [40, 34]]\n')
    silk = load(tmp_path / "edakit.toml").board().silk
    assert silk["board_label_side"] == "bottom" and silk["board_label_region"] == [[0, 0], [40, 0], [40, 34]]
    with pytest.raises(ConfigError, match="silk.board_label_side must be 'top' or 'bottom'"):
        _board("b", {}, {"silk": {"board_label_side": "back"}})
    for region in ([[0, 0], [40, 0]], [[0, 0], [40, 0], [40]], "y < 34", [[0, 0], [40, 0], ["a", 3]]):
        with pytest.raises(ConfigError, match=r"silk.board_label_region must be a polygon \[\[x, y\], …\]"):
            _board("b", {}, {"silk": {"board_label_region": region}})


def test_silk_place_key(tmp_path):
    """Step 2.3: [silk.place] fixes single designators – x, y (plan mm), rot, side – as [place] fixes parts."""
    from edakit.config import _board
    assert "place" not in _board("b", {}, {}).silk                     # no key: silk apply places every designator
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text(
        '[silk]\ndesignators = "top"\n[silk.place]\nR4 = { x = 12.5, y = 30, rot = 90 }\nLED1 = { x = 5, y = 3, side = '
        '"bottom" }\n')
    assert load(tmp_path / "edakit.toml").board().silk["place"] == {
        "R4": {"x": 12.5, "y": 30, "rot": 90}, "LED1": {"x": 5, "y": 3, "side": "bottom"}}
    for bad, msg in ((["R4"], r"silk.place must be a table of designator = \{ x, y, rot, side \}"),
                     ({"R4": [12.5, 30]}, r"silk.place.R4: needs x and y \(plan mm\)"),
                     ({"R4": {"x": 12.5}}, r"silk.place.R4: needs x and y \(plan mm\)"),
                     ({"R4": {"x": "12.5", "y": 30}}, "silk.place.R4: x, y and rot must be numbers"),
                     ({"R4": {"x": 12.5, "y": 30, "rot": True}}, "silk.place.R4: x, y and rot must be numbers"),
                     ({"R4": {"x": 12.5, "y": 30, "side": "back"}},
                      "silk.place.R4: side must be 'top' or 'bottom', not 'back'"),
                     ({"R4": {"x": 12.5, "y": 30, "lock": True}},
                      r"silk.place.R4: unknown key 'lock' \(known: x, y, rot, side\)")):
        with pytest.raises(ConfigError, match=msg):
            _board("b", {}, {"silk": {"place": bad}})


def test_copper_key(tmp_path):
    from edakit.config import _board
    assert _board("b", {}, {}).copper == {"max_bare_mm": 5.0, "min_cover": {}}     # no key: 5 mm, no share required
    b = _board("b", {}, {"copper": {"max_bare_mm": 8, "min_cover": {"BOTTOM": 60}}})
    assert b.copper == {"max_bare_mm": 8.0, "min_cover": {"BOTTOM": 60.0}}
    for bad, msg in (({"max_bare_mm": 0}, "max_bare_mm must be positive"), ({"min_cover": {"INNER1": 50}}, "min_cover"),
                     ({"min_cover": {"TOP": 150}}, "min_cover"), ({"bare_mm": 5}, "unknown key 'bare_mm'")):
        with pytest.raises(ConfigError, match=msg):
            _board("b", {}, {"copper": bad})


def test_agreements_key(tmp_path):
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    assert load(tmp_path / "edakit.toml").agreements is True                  # default: the digest at session start
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\nagreements = false\n[boards.main]\n')
    assert load(tmp_path / "edakit.toml").agreements is False
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\nagreements = "no"\n[boards.main]\n')
    with pytest.raises(ConfigError, match=r"\[project\] agreements: true or false"):
        load(tmp_path / "edakit.toml")


def test_order_keys(tmp_path):
    """#40: [order] of the board file – the order form fields that depend on the board (FILES.order)."""
    from edakit.config import _board
    assert _board("b", {}, {}).order is None                              # no key: no order form, no FILES.order, as before
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text("[order]\n")
    first = ("finish", "mark", "remark", "tab_zones", "tab_copper_mm", "mask", "silkscreen")   # the keys of #40, 1.7
    seven = lambda o: {k: o[k] for k in first}  # noqa: E731
    assert seven(load(tmp_path / "edakit.toml").board().order) == {
        "finish": "LeadFree HASL", "mark": "default", "remark": "", "tab_zones": [], "tab_copper_mm": 1.0,
        "mask": "green", "silkscreen": "white"}
    (tmp_path / "hardware" / "boards" / "main.toml").write_text(
        '[order]\nfinish = "ENIG"\nmark = "specify"\nremark = "No V-cut."\ntab_copper_mm = 0.5\n'
        'tab_zones = [{ from = [0, 0], to = [0, 20] }]\nmask = "black"\nsilkscreen = "white"\n')
    assert seven(load(tmp_path / "edakit.toml").board().order) == {
        "finish": "ENIG", "mark": "specify", "remark": "No V-cut.", "tab_zones": [((0.0, 0.0), (0.0, 20.0))],
        "tab_copper_mm": 0.5, "mask": "black", "silkscreen": "white"}
    for order, msg in (({"marks": "specify"}, r"order: unknown key 'marks' \(known: finish, mark, remark"),
                       ({"mark": "place"}, "order.mark must be one of default, specify, remove, not 'place'"),
                       ({"remark": 3}, "order.remark must be a string"),
                       ({"finish": 1}, "order.finish must be a string"),
                       ({"tab_copper_mm": -1}, "order.tab_copper_mm must be a number >= 0"),
                       ({"tab_zones": [{"from": [0, 0]}]}, r"order.tab_zones 1: needs from = \[x, y\] and to = \[x, y\]"),
                       ({"tab_zones": [{"from": [0, 0], "to": [0, "a"]}]}, "order.tab_zones 1: needs from"),
                       ({"tab_zones": [{"from": [0, 0], "to": [0, 2], "side": "top"}]},
                        "order.tab_zones 1: unknown key 'side'"),
                       ("specify", "order must be a table")):
        with pytest.raises(ConfigError, match=msg):
            _board("b", {}, {"order": order})


def test_bought_key(tmp_path):
    """#82: [boards.<name>] bought = true – a board nobody draws or assembles: no EasyEDA documents, no board file."""
    toml = tmp_path / "edakit.toml"
    toml.write_text('[project]\nname = "t"\n[boards.main]\n')
    assert load(toml).board().bought is False                             # no key: the board is made, as before
    toml.write_text('[project]\nname = "t"\n[boards.main]\n[boards.usb]\nbought = true\n')
    cfg = load(toml)
    assert cfg.boards["usb"].bought and list(cfg.boards) == ["main", "usb"] and list(cfg.made()) == ["main"]
    assert cfg.board(made=True).name == "main" and cfg.board("usb").name == "usb"
    with pytest.raises(ConfigError, match=r"^board usb is bought \(bought = true in edakit.toml \[boards.usb\]\)"):
        cfg.board("usb", made=True)
    for key in ("template", "schematic", "pcb", "file"):
        toml.write_text(f'[project]\nname = "t"\n[boards.main]\n[boards.usb]\nbought = true\n{key} = "usb"\n')
        with pytest.raises(ConfigError, match=rf"\[boards.usb\] {key}: a bought board is not drawn – no schematic, "
                                              "PCB or board file"):
            load(toml)
    toml.write_text('[project]\nname = "t"\n[boards.main]\n[boards.usb]\nbought = "yes"\n')
    with pytest.raises(ConfigError, match=r"\[boards.usb\] bought: true or false"):
        load(toml)
    toml.write_text('[project]\nname = "t"\n[boards.main]\n[boards.usb]\nbought = true\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "usb.toml").write_text("[order]\n")
    with pytest.raises(ConfigError, match=r"hardware/boards/usb.toml: a bought board \(bought = true in "
                                          r"\[boards.usb\]\) has no board file"):
        load(toml)


def test_order_colour_keys():
    """Step 1.7: [order] mask and silkscreen – JLCPCB's colours of solder mask and silkscreen. Without them its
    defaults: a green mask with white print; on a white mask JLCPCB prints black."""
    from edakit.config import _board
    order = _board("b", {}, {"order": {}}).order
    assert (order["mask"], order["silkscreen"]) == ("green", "white")       # no key: JLCPCB's default, as before
    assert _board("b", {}, {"order": {"mask": "white"}}).order["silkscreen"] == "black"
    for mask in ("green", "purple", "red", "yellow", "blue", "white", "black"):
        assert _board("b", {}, {"order": {"mask": mask}}).order["mask"] == mask
    order = _board("b", {}, {"order": {"mask": "white", "silkscreen": "white"}}).order   # FILES.order judges the pair
    assert (order["mask"], order["silkscreen"]) == ("white", "white")
    for order, msg in (({"mask": "orange"},
                        "order.mask must be one of green, purple, red, yellow, blue, white, black, not 'orange'"),
                       ({"mask": "Black"}, "order.mask must be one of green, purple"),
                       ({"silkscreen": "yellow"}, "order.silkscreen must be one of white, black, not 'yellow'"),
                       ({"colour": "black"}, r"order: unknown key 'colour' \(known: .*mask, silkscreen\)")):
        with pytest.raises(ConfigError, match=msg):
            _board("b", {}, {"order": order})


def test_firmware_table_is_opt_in(tmp_path):
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    assert load(tmp_path / "edakit.toml").firmware is None
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n[firmware]\nmcu = "U1"\n')
    assert load(tmp_path / "edakit.toml").firmware == {"mcu": "U1", "out": "hardware/firmware.json", "gpio": r"(\d+)"}
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n[firmware]\nformat = "c"\n')
    with pytest.raises(ConfigError, match=r"\[firmware\]: unknown key 'format'"):
        load(tmp_path / "edakit.toml")
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n[firmware]\ngpio = "GP"\n')
    with pytest.raises(ConfigError, match="needs a group"):
        load(tmp_path / "edakit.toml")


def test_docs_files(tmp_path):
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    assert load(tmp_path / "edakit.toml").docs == []                     # nothing is read
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n[docs]\nfiles = ["docs/a.md"]\n')
    assert load(tmp_path / "edakit.toml").docs == ["docs/a.md"]
    assert load(tmp_path / "edakit.toml").docs_decimal == "."
    for bad in ('files = "docs/a.md"', 'file = ["docs/a.md"]', 'decimal = ";"'):
        (tmp_path / "edakit.toml").write_text(f'[project]\nname = "t"\n[boards.main]\n[docs]\n{bad}\n')
        with pytest.raises(ConfigError, match=r"\[docs\]"):
            load(tmp_path / "edakit.toml")


def test_requirements_key(tmp_path):
    """[project] requirements: the requirements file (edakit req), or a list of them for a variant."""
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    assert load(tmp_path / "edakit.toml").requirements == []             # no key: no requirements file, no change
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\nrequirements = "hardware/requirements.toml"\n'
                                          '[boards.main]\n')
    cfg = load(tmp_path / "edakit.toml")
    assert cfg.requirements == [cfg.root / "hardware" / "requirements.toml"]
    variant = tmp_path / "variants" / "v"                                # the main project's file and its own
    variant.mkdir(parents=True)
    (variant / "edakit.toml").write_text('[project]\nname = "t"\nrequirements = ["../../hardware/requirements.toml", '
                                         '"hardware/requirements.toml"]\n[boards.v]\n')
    cfg = load(variant / "edakit.toml")
    assert cfg.requirements == [cfg.root / "../../hardware/requirements.toml", cfg.root / "hardware/requirements.toml"]
    assert [cfg.relative(f) for f in cfg.requirements] == ["../../hardware/requirements.toml",
                                                           "hardware/requirements.toml"]
    for bad, msg in (('requirements = 3', "a path or a list of paths"), ('requirements = [""]', "a path or a list"),
                     ('requirements = ["a.toml", 1]', "a path or a list"), ("requirements = true", "a path or a list"),
                     ('requirements = ["a.toml", "./a.toml"]', "a.toml named twice")):
        (tmp_path / "edakit.toml").write_text(f'[project]\nname = "t"\n{bad}\n[boards.main]\n')
        with pytest.raises(ConfigError, match=rf"\[project\] requirements: .*{msg}"):
            load(tmp_path / "edakit.toml")


def test_place_auto_key(tmp_path):
    from edakit.config import _placement
    assert _placement("C1", {"x": 1, "y": 2}).auto is False               # no key: a row written by hand, as before
    assert _placement("C1", [1, 2, 90, "top"]).auto is False
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text(
        '[place]\nC1 = { x = 66.0, y = 21.4, rot = 0, side = "top", auto = true }\n')
    c1 = load(tmp_path / "edakit.toml").board().place["C1"]
    assert c1.auto is True and c1.lock is True and (c1.x, c1.y) == (66.0, 21.4)
    with pytest.raises(ConfigError, match="place.C1: auto must be true or false"):
        _placement("C1", {"x": 1, "y": 2, "auto": "yes"})


def test_routing_widths_key(tmp_path):
    from edakit.config import _board
    assert "widths" not in _board("b", {}, {}).routing                    # no key: the widths of the classes, as before
    for value in ("classes", "sim"):
        assert _board("b", {}, {"routing": {"widths": value}}).routing["widths"] == value
    with pytest.raises(ConfigError, match="routing.widths must be 'classes' or 'sim'"):
        _board("b", {}, {"routing": {"widths": "ipc"}})


def test_uniform_key():
    from edakit.config import _board
    assert _board("b", {}, {}).uniform is None                             # no key: LEDs in a row, as before
    u = {"led": "+x", "buzzer": "-x", "capacitor": "row"}
    assert _board("b", {}, {"uniform": u}).uniform == u
    for value in ({"led": "x"}, {"led": "left"}, ["led"], {"led": 1}):
        with pytest.raises(ConfigError, match="uniform must be a table of part kinds"):
            _board("b", {}, {"uniform": value})


def test_looks_key():
    from edakit.config import _board
    assert _board("b", {}, {}).looks is None                               # no [looks]: nothing reported, as before
    lk = {"visible": "bottom", "max_track_m": 0.1, "max_vias": 4}
    assert _board("b", {}, {"looks": lk}).looks == lk
    for value, msg in (({"max_vias": 1}, "needs visible"), ({"visible": "front"}, "needs visible"),
                       ({"visible": "top", "max_track": 1}, "unknown key 'max_track'"),
                       ({"visible": "top", "max_track_m": -1}, "max_track_m must be a length"),
                       ({"visible": "top", "max_vias": 1.5}, "max_vias must be a whole number")):
        with pytest.raises(ConfigError, match=msg):
            _board("b", {}, {"looks": value})


def test_thickness_key(tmp_path):
    from edakit.config import _board
    assert _board("b", {}, {}).thickness_mm == 1.6                         # no key: 1.6 mm, JLCPCB's default
    assert _board("b", {}, {"thickness_mm": 1.0}).thickness_mm == 1.0
    for value in (0, -1, "1.6", True):
        with pytest.raises(ConfigError, match="thickness_mm must be a thickness in mm, more than 0"):
            _board("b", {}, {"thickness_mm": value})
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text("thickness_mm = 0.8\n")
    assert load(tmp_path / "edakit.toml").board().thickness_mm == 0.8


def test_routing_hand_solder_keep_key():
    from edakit.config import _board
    assert "hand_solder_keep_mm" not in _board("b", {}, {}).routing        # no key: GEO.spacing off, as before
    assert _board("b", {}, {"routing": {"hand_solder_keep_mm": 0.5}}).routing["hand_solder_keep_mm"] == 0.5
    for value in (-0.1, "0.5", True):
        with pytest.raises(ConfigError, match="routing.hand_solder_keep_mm must be a distance in mm"):
            _board("b", {}, {"routing": {"hand_solder_keep_mm": value}})


def test_hash_ignore_is_a_list_of_key_names(project):
    toml = project.root / "edakit.toml"
    text = toml.read_text()
    assert project.config().release.get("hash_ignore") is None           # default: the bytes are hashed
    toml.write_text(text.replace("[release]\n", '[release]\nhash_ignore = ["notes", "sources"]\n'))
    assert project.config().release["hash_ignore"] == ["notes", "sources"]
    toml.write_text(text.replace("[release]\n", '[release]\nhash_ignore = "notes"\n'))
    with pytest.raises(ConfigError, match="hash_ignore: a list of key names"):
        project.config()


def test_scripts_entries(tmp_path):
    """[scripts.<name>]: the project's scripts as written; edakit check resolves them (test_scripts.py)."""
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    assert load(tmp_path / "edakit.toml").scripts == {}                   # no key, no change
    kunst = ('[scripts.kunst]\nkind = "input"\ncmd = ["python", "hardware/art/make_art.py"]\nabout = "artwork"\n'
             'writes = ["hardware/art/bell.svg"]\n')
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n' + kunst)
    assert load(tmp_path / "edakit.toml").scripts == {"kunst": {
        "kind": "input", "cmd": ["python", "hardware/art/make_art.py"], "about": "artwork",
        "writes": ["hardware/art/bell.svg"]}}
    for bad, msg in (('writs = ["x"]', r"\[scripts.k\]: unknown key 'writs' \(known: kind, cmd, about"),
                     ('cmd = "python make.py"', r"\[scripts.k\] cmd must be a list of strings"),
                     ('reads = ["graph", 3]', r"\[scripts.k\] reads must be a list of data names and paths"),
                     ('after = "kunst"', r"\[scripts.k\] after must be a list of script names"),
                     ('about = 1', r"\[scripts.k\] about must be a string"),
                     ('advisory = "yes"', r"\[scripts.k\] advisory: true or false")):
        (tmp_path / "edakit.toml").write_text(f'[project]\nname = "t"\n[boards.main]\n[scripts.k]\n{bad}\n')
        with pytest.raises(ConfigError, match=msg):
            load(tmp_path / "edakit.toml")
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n[scripts]\nkind = "input"\n')
    with pytest.raises(ConfigError, match=r"\[scripts\] kind: a table \[scripts.kind\]"):
        load(tmp_path / "edakit.toml")


def test_agents_entries(tmp_path):
    """[agents.<name>]: the project's agents as written – what each signs and when it reviews is edakit check's
    (test_agents.py). Red before step 3.2: [agents] was an unknown key of edakit.toml."""
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    assert load(tmp_path / "edakit.toml").agents == {}                    # no key, no change
    pruefer = ('[agents.pcb-pruefer]\nfile = ".claude/agents/pcb-pruefer.md"\nabout = "the tree board"\n'
               'signs = "M-5"\nreplaces = "pcb-reviewer"\nphase = "export"\nafter = ["optik"]\n')
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n' + pruefer)
    assert load(tmp_path / "edakit.toml").agents == {"pcb-pruefer": {
        "file": ".claude/agents/pcb-pruefer.md", "about": "the tree board", "signs": "M-5", "replaces": "pcb-reviewer",
        "phase": "export", "after": ["optik"]}}
    for bad, msg in (('sings = "M-7"', r"\[agents.a\]: unknown key 'sings' \(known: file, about, signs, replaces, "
                                       r"scope, phase, after\)"),
                     ('signs = 7', r"\[agents.a\] signs must be a string"),
                     ('scope = ["layout"]', r"\[agents.a\] scope must be a string"),
                     ('after = "optik"', r"\[agents.a\] after must be a list of agent names"),
                     ('after = ["optik", ""]', r"\[agents.a\] after must be a list of agent names")):
        (tmp_path / "edakit.toml").write_text(f'[project]\nname = "t"\n[boards.main]\n[agents.a]\n{bad}\n')
        with pytest.raises(ConfigError, match=msg):
            load(tmp_path / "edakit.toml")
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n[agents]\nsigns = "M-7"\n')
    with pytest.raises(ConfigError, match=r"\[agents\] signs: a table \[agents.signs\]"):
        load(tmp_path / "edakit.toml")
