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


# --- pour-only nets (#7): a 40 x 20 mm board, GND pads C1.2 (left) and C2.2 (right) SMD on TOP, a GND pour on TOP,
# SIG from a pad at the top edge to one at the bottom edge

def mm(x, y):
    return x * MIL, y * MIL


POUR_ONLY = """
[project]
name = "t"
[boards.main.outline]
rect = [40, 20]
[[boards.main.routing.fixed_wires]]
net = "GND"
layer = "TOP"
width_mil = 12
points = [[5, 10], [8, 10]]
[[boards.main.pours]]
net = "GND"
layers = ["TOP"]
"""


@pytest.fixture
def pour_board(tmp_path):
    def make(extra="pour_only = true"):
        (tmp_path / "edakit.toml").write_text(POUR_ONLY + extra + "\n")
        return route.Rules(config.load(tmp_path / "edakit.toml").board())
    data = {"pcb": "main",
            "components": [{"ref": r, "x": 0, "y": 0, "rot": 0, "layer": 1} for r in ("C1", "C2", "TP1", "TP2")],
            "pads": [pad("C1", "2", "GND", *mm(5, 10)), pad("C2", "2", "GND", *mm(35, 10)),
                     pad("TP1", "1", "SIG", *mm(20, 19)), pad("TP2", "1", "SIG", *mm(20, 1))],
            "outlines": [[mm(0, 0), mm(40, 0), mm(40, 20), mm(0, 20)]]}
    return make, data


SIG_TOP = {"SIG": {"wires": [("TOP", 10, [mm(20, 19), mm(20, 1)])], "vias": []}}
SIG_BOTTOM = {"SIG": {"wires": [("TOP", 10, [mm(20, 19), mm(20, 17.5)]), ("BOTTOM", 10, [mm(20, 17.5), mm(20, 2.5)]),
                                ("TOP", 10, [mm(20, 2.5), mm(20, 1)])],
                      "vias": [mm(20, 17.5), mm(20, 2.5)]}}


def names(data, groups):
    return [[f"{data['pads'][i]['ref']}.{data['pads'][i]['num']}" for i in g] for g in groups]


def test_pour_only_net_is_not_routed(pour_board, tmp_path):
    make, data = pour_board
    route.write_dsn(make(), data, tmp_path / "t.dsn")
    text = (tmp_path / "t.dsn").read_text()
    network = text[text.index("(network"):text.index("(wiring")]
    assert '(net "GND"' not in network and "C1-2" not in text and "C2-2" not in text  # no connection to make
    assert '(net "SIG" (pins TP1-1 TP2-1))' in text
    assert text.count('(pin "ps0" "2"') == 2                                         # GND pads stay as obstacles


def test_pour_only_track_across_the_pour_cuts_it(pour_board):
    make, data = pour_board
    open_nets = route.check(make(), data, SIG_TOP)
    assert names(data, open_nets["GND"]) in ([["C1.2"], ["C2.2"]], [["C2.2"], ["C1.2"]])


def test_pour_only_pour_connects_when_the_track_goes_below(pour_board):
    make, data = pour_board
    assert route.check(make(), data, SIG_BOTTOM) == {}


def test_without_pour_only_nothing_changes(pour_board, tmp_path):
    make, data = pour_board
    rules = make("")
    assert set(route.check(rules, data, SIG_BOTTOM)) == {"GND"}                     # GND still needs tracks
    route.write_dsn(rules, data, tmp_path / "t.dsn")
    assert '(net "GND" (pins C1-2 C2-2))' in (tmp_path / "t.dsn").read_text()


def test_pour_only_neck_narrower_than_min_width(pour_board):
    make, data = pour_board
    # two foreign tracks from the edges towards the middle; between their ends the pour keeps a neck of
    # 0.954 mm - 2 x (0.127 mm half width + 0.25 mm clearance) = 0.2 mm
    data["pads"] += [pad("TP3", "1", "A", *mm(20, 19)), pad("TP4", "1", "B", *mm(20, 1))]
    data["pads"] = [p for p in data["pads"] if p["net"] != "SIG"]
    routes = {"A": {"wires": [("TOP", 10, [mm(20, 19), mm(20, 10.477)])], "vias": []},
              "B": {"wires": [("TOP", 10, [mm(20, 1), mm(20, 9.523)])], "vias": []}}
    assert "GND" in route.check(make(), data, routes)                                # 0.2 mm < 0.25 mm: not filled
    assert route.check(make("pour_only = true\nmin_width_mm = 0.15"), data, routes) == {}
    assert "GND" in route.check(make("pour_only = true\nmin_width_mm = 0.15\nclearance_mm = 0.3"), data, routes)


def test_pour_only_two_pour_layers_join_through_a_via(pour_board):
    make, data = pour_board
    rules = make('pour_only = true\n[[boards.main.pours]]\nnet = "GND"\nlayers = ["BOTTOM"]\npour_only = true')
    data["pads"][1]["layer"] = 2                                                     # C2 on the bottom side
    assert set(route.check(rules, data, SIG_TOP)) == {"GND"}                         # TOP cut, nothing joins the sides
    stitched = dict(SIG_TOP, GND={"wires": [], "vias": [mm(8, 10)]})
    assert route.check(rules, data, stitched) == {}                                  # C1.2 – TOP – via – BOTTOM – C2.2


def test_pour_only_fixed_wire_stays_in_the_routes(pour_board, tmp_path):
    make, _ = pour_board
    (tmp_path / "t.ses").write_text(SES)                                             # Freerouting dropped the GND wire
    routes = route.read_ses(tmp_path / "t.ses", make())
    [(layer, width, pts)] = routes["GND"]["wires"]
    assert (layer, width) == ("TOP", 12)
    assert [v for pt in pts for v in pt] == pytest.approx([*mm(5, 10), *mm(8, 10)], abs=0.01)
    assert routes["GND"]["vias"] == [(1040.0, 300.0)] and routes["SIG"] == route.read_ses(tmp_path / "t.ses")["SIG"]
    assert route.read_ses(tmp_path / "t.ses", make(""))["GND"]["wires"] == []      # a routed net: as Freerouting says
    with_wire = SES.replace("(net GND", "(net GND (wire (path TOP 1200 19685 39370 31496 39370))")
    (tmp_path / "w.ses").write_text(with_wire)                                       # an SES that keeps it: not twice
    assert len(route.read_ses(tmp_path / "w.ses", make())["GND"]["wires"]) == 1


def test_pour_only_on_a_shared_layer_is_said(pour_board, capsys):
    make, data = pour_board
    rules = make('pour_only = true\n[[boards.main.pours]]\nnet = "V_LED"\nlayers = ["TOP", "BOTTOM"]')
    route.report_check(rules, data, route.check(rules, data, SIG_TOP), SIG_TOP)
    out = capsys.readouterr().out
    assert "GND (pour-only): 2 groups – C" in out
    assert "! GND TOP: the pour of V_LED shares the layer" in out
