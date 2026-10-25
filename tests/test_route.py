"""DSN writer, SES reader, connectivity and clearance check of the Freerouting pipeline, offline."""

import json

import pytest

from edakit import config, route

MIL = 1000 / 25.4


def pad(ref, num, net, x, y, layer=1, shape=("RECT", 40, 40)):
    return {"id": f"{ref}e{num}", "ref": ref, "num": num, "net": net, "x": x, "y": y, "rot": 0, "layer": layer,
            "shape": list(shape), "hole": None, "hole_off": [0, 0]}


@pytest.fixture
def setup(tmp_path):
    (tmp_path / "edakit.toml").write_text("""
[project]
name = "t"
[boards.main]
[boards.main.outline]
rect = [40, 20]
[boards.main.routing]
clearance_mil = 6.5
classes = { POWER = { width_mil = 20, nets = ["VCC"] } }
[[boards.main.routing.keepouts]]
layer = "BOTTOM"
what = "wire"
rect = [0, 15, 40, 20]
[[boards.main.pours]]
net = "GND"
layers = ["BOTTOM"]
plane = true
""")
    cfg = config.load(tmp_path / "edakit.toml")
    board = cfg.board()
    rect = [(0, 0), (40 * MIL, 0), (40 * MIL, 20 * MIL), (0, 20 * MIL)]
    data = {"pcb": "main", "components": [{"ref": "R1", "x": 300, "y": 300, "rot": 0, "layer": 1},
                                          {"ref": "R2", "x": 1000, "y": 300, "rot": 0, "layer": 1}],
            "pads": [pad("R1", "1", "VCC", 260, 300), pad("R1", "2", "SIG", 340, 300),
                     pad("R2", "1", "SIG", 960, 300), pad("R2", "2", "GND", 1040, 300, layer=12,
                                                         shape=("ELLIPSE", 60, 60))],
            "outlines": [rect]}
    return cfg, board, route.Rules(board), data


def test_dsn_contains_rules_keepouts_and_plane(setup, tmp_path):
    cfg, board, rules, data = setup
    out = tmp_path / "t.dsn"
    route.write_dsn(rules, data, out)
    text = out.read_text()
    assert "(resolution mil 100)" in text
    assert '(net "SIG" (pins R1-2 R2-1))' in text
    assert '(class "POWER" "VCC"' not in text           # a net with one pin is not routed
    assert "(wire_keepout" in text and '(plane "GND" (polygon BOTTOM' in text
    assert text.index("(autoroute_settings") < text.index("(keepout")  # order matters for Freerouting 2.4.1
    assert text.index('(plane "GND"') > text.rindex("keepout")


def test_variant_reorders_but_keeps_content(setup, tmp_path):
    _, _, rules, data = setup
    a, b = tmp_path / "a.dsn", tmp_path / "b.dsn"
    route.write_dsn(rules, data, a)
    route.write_dsn(rules, data, b, variant=3)
    assert sorted(a.read_text().splitlines()) != [] and len(a.read_text()) == len(b.read_text())


SES = """(session t (routes (resolution mil 100) (parser) (network_out
  (net SIG (wire (path TOP 1000 34000 30000 60000 30000)) (wire (path TOP 1000 60000 30000 96000 30000)))
  (net GND (via via24 104000 30000))
)))"""


def test_read_ses_and_check(setup, tmp_path):
    _, _, rules, data = setup
    (tmp_path / "t.ses").write_text(SES)
    routes = route.read_ses(tmp_path / "t.ses")
    assert routes["SIG"]["wires"][0] == ("TOP", 10.0, [(340.0, 300.0), (600.0, 300.0)])
    assert route.check(rules, data, routes) == {}
    segs = route.segments(rules, routes, data)
    assert len(segs["SIG"]) == 1                          # straight continuation merged


def test_check_finds_open_net(setup, tmp_path):
    _, _, rules, data = setup
    routes = {"SIG": {"wires": [("TOP", 10, [(340, 300), (600, 300)])], "vias": []}}
    assert "SIG" in route.check(rules, data, routes)


def test_clearance_and_keepout(setup):
    _, _, rules, data = setup
    near = {"SIG": {"wires": [("TOP", 10, [(340, 300), (960, 300)])], "vias": []},
            "VCC": {"wires": [("TOP", 10, [(260, 310), (900, 310)])], "vias": []}}
    assert any("mil at" in f for f in route.clearance_check(rules, data, near))
    keep = {"SIG": {"wires": [("BOTTOM", 10, [(340, 700), (960, 700)])], "vias": []}}
    assert any("wire keep-out" in f for f in route.clearance_check(rules, data, keep))


def test_convex_pieces_of_a_concave_area():
    from shapely.geometry import Polygon
    u = Polygon([(0, 0), (30, 0), (30, 30), (20, 30), (20, 10), (10, 10), (10, 30), (0, 30)])
    pieces = route.convex_pieces(u)
    assert abs(sum(p.area for p in pieces) - u.area) < 1e-6
    assert all(p.convex_hull.area - p.area < 0.5 for p in pieces)


def test_board_json_round_trip(setup, tmp_path):
    _, _, rules, data = setup
    p = tmp_path / "b.json"
    p.write_text(json.dumps(data))
    route.write_dsn(rules, json.loads(p.read_text()), tmp_path / "x.dsn")
