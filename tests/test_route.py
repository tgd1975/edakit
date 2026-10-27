"""DSN writer, SES reader, connectivity and clearance check of the Freerouting pipeline, offline."""

import json
import math
import re
from pathlib import Path

import pytest
from shapely.ops import unary_union

from edakit import config, route

MIL = 1000 / 25.4
EXAMPLE = Path(__file__).resolve().parent / "fixtures" / "led-bar"


def pad(ref, num, net, x, y, layer=1, shape=("RECT", 40, 40)):
    return {"id": f"{ref}e{num}", "ref": ref, "num": num, "net": net, "x": x, "y": y, "rot": 0, "layer": layer,
            "shape": list(shape), "hole": None, "hole_off": [0, 0]}


@pytest.fixture
def setup(tmp_path):
    (tmp_path / "edakit.toml").write_text("""
[project]
name = "t"
[boards.main]
""")
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text("""
[outline]
rect = [40, 20]
[routing]
clearance_mil = 6.5
classes = { POWER = { width_mil = 20, nets = ["VCC"] } }
[[routing.keepouts]]
layer = "BOTTOM"
what = "wire"
rect = [0, 15, 40, 20]
[[pours]]
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
[outline]
rect = [40, 20]
[[routing.fixed_wires]]
net = "GND"
layer = "TOP"
width_mil = 12
points = [[5, 10], [8, 10]]
[[pours]]
net = "GND"
layers = ["TOP"]
"""


@pytest.fixture
def pour_board(tmp_path):
    def make(extra="pour_only = true"):
        (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
        (tmp_path / "hardware" / "boards").mkdir(parents=True, exist_ok=True)
        (tmp_path / "hardware" / "boards" / "main.toml").write_text(POUR_ONLY + extra + "\n")
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
    rules = make('pour_only = true\n[[pours]]\nnet = "GND"\nlayers = ["BOTTOM"]\npour_only = true')
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
    rules = make('pour_only = true\n[[pours]]\nnet = "V_LED"\nlayers = ["TOP", "BOTTOM"]')
    route.report_check(rules, data, route.check(rules, data, SIG_TOP), SIG_TOP)
    out = capsys.readouterr().out
    assert "GND (pour-only): 2 groups – C" in out
    assert "! GND TOP: the pour of V_LED shares the layer" in out


# --- several nets share one pour layer (#8): GND pads on the left, GND_B pads on the right, SIG across the board on
# TOP between them, both pours on TOP. `edakit route pours` against a recorder instead of EasyEDA

REGIONS = """
pour_regions = true
[outline]
rect = [40, 20]
[[pours]]
net = "GND"
layers = ["TOP"]
pour_only = true
[[pours]]
net = "GND_B"
layers = ["TOP"]
pour_only = true
priority = 2
"""

LEFT, RIGHT = [mm(5, 5), mm(5, 15)], [mm(35, 5), mm(35, 15)]
# a closed SIG2 track around (10, 10), inside GND's area: a pocket of 1.2 mm² outside a GND_B pad and its clearance
POCKET = {"SIG2": {"wires": [("TOP", 10, [mm(8.7, 8.7), mm(11.3, 8.7), mm(11.3, 11.3), mm(8.7, 11.3), mm(8.7, 8.7)])],
                   "vias": []}}


def ses(routes):
    """An SES as Freerouting writes it (mil, resolution 100)."""
    def net(name, r):
        wires = " ".join(f"(wire (path {layer} {w * 100:.0f} " + " ".join(f"{x * 100:.0f} {y * 100:.0f}" for x, y in pts)
                         + "))" for layer, w, pts in r["wires"])
        return f"(net {name} {wires} " + " ".join(f"(via via24 {x * 100:.0f} {y * 100:.0f})" for x, y in r["vias"]) + ")"
    return ("(session t (routes (resolution mil 100) (parser) (network_out "
            + " ".join(net(n, r) for n, r in routes.items()) + ")))")


class Recorder:
    """Stands in for EasyEDA: records every API call, creates succeed, lists are empty."""
    def __init__(self):
        self.calls = []

    def api(self, mcp, name, *args):
        self.calls.append((name, args))
        return True if name.endswith(".create") else []

    def call(self, tool, **kw):
        return {"results": [{"pourId": "p", "status": "ok"}]}

    def close(self):
        pass

    def pours(self):
        """The created pours: [(net, layer id, name, priority, polygon in mm)]."""
        from shapely.geometry import Polygon
        out = []
        for name, a in self.calls:
            if name == "PCB_PrimitivePour.create":
                nums = [v for v in a[2]["$polygon"] if not isinstance(v, str)]
                out.append((a[0], a[1], a[5], a[6], Polygon([(x / MIL, y / MIL) for x, y in zip(nums[0::2], nums[1::2])])))
        return out


@pytest.fixture
def regions(tmp_path, monkeypatch):
    """-> run(action, board file, pads, routes) -> (exit code, created pours): `edakit route <action>` or `edakit pcb
    pour` with the board file and SES of the routing in the artifacts, EasyEDA replaced by a recorder."""
    from argparse import Namespace

    from edakit import eda, pcb
    rec = Recorder()
    for mod in (pcb, route):
        monkeypatch.setattr(mod, "api", rec.api)
        monkeypatch.setattr(mod, "ensure_pcb_focus", lambda mcp: None)
    for name in ("open_project", "open_pcb"):
        monkeypatch.setattr(eda, name, lambda *a, **k: None)
    monkeypatch.setattr(eda, "connect", lambda *a, **k: rec)
    monkeypatch.setattr(eda, "start", lambda *a, **k: rec)
    monkeypatch.setattr(eda, "wait_for_bridge", lambda mcp: True)

    def run(action, toml=REGIONS, pads=(), routes=None, ses_file=True):
        (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
        (tmp_path / "hardware" / "boards").mkdir(parents=True, exist_ok=True)
        (tmp_path / "hardware" / "boards" / "main.toml").write_text(toml)
        cfg = config.load(tmp_path / "edakit.toml")
        board = cfg.board()
        data = {"pcb": "main", "components": [], "outlines": [[mm(0, 0), mm(40, 0), mm(40, 20), mm(0, 20)]],
                "pads": [pad(f"C{i}", "2", net, *xy) for i, (net, xy) in enumerate(
                    [("GND", p) for p in LEFT] + [("GND_B", p) for p in RIGHT] + list(pads), 1)]
                + [pad("TP1", "1", "SIG", *mm(20, 19)), pad("TP2", "1", "SIG", *mm(20, 1))]}
        P = route.paths(cfg, board)
        P["board"].write_text(json.dumps(data))
        if ses_file:
            P["ses"].write_text(ses(dict(SIG_TOP, **(routes or {}))))
        args = Namespace(board=None, action=action, verbose=False, clearance=None, passes=None, threads=1,
                         no_optimizer=False, cleanup=False)
        if action == "pcb pour":
            code = pcb.main(cfg, Namespace(board=None, action="pour", verbose=False))
        else:
            code = route.main(cfg, args)
        return code, rec.pours()
    return run


def holds(poly, points):
    from shapely.geometry import Point
    return [poly.contains(Point(x / MIL, y / MIL)) for x, y in points]


def test_regions_each_net_gets_its_own_outline(regions):
    _, made = regions("pours")
    assert [(net, layer, name, prio) for net, layer, name, prio, _ in made] == [("GND", 1, "GND_TOP", 1),
                                                                               ("GND_B", 1, "GND_B_TOP", 2)]
    gnd, gnd_b = made[0][4], made[1][4]
    assert all(holds(gnd, LEFT)) and not any(holds(gnd, RIGHT))
    assert all(holds(gnd_b, RIGHT)) and not any(holds(gnd_b, LEFT))
    assert gnd.intersection(gnd_b).area < 1e-6                                       # no overlap
    # SIG's edge at 20 - 0.127 mm, the pour 0.25 mm before it, the outline 0.2 mm beyond the pour
    assert gnd.bounds[2] == pytest.approx(20 - 0.127 - 0.25 + 0.2, abs=0.01)


def test_regions_a_sliver_gets_no_outline(regions):
    _, made = regions("pours", pads=[("GND_B", mm(10, 10))], routes=POCKET)
    assert [net for net, *_ in made] == ["GND", "GND_B"]                             # one outline each
    assert not any(holds(made[1][4], [mm(10, 10)]))                                  # none for the pocket


def test_regions_a_piece_inside_another_nets_outline_is_an_error(regions, capsys):
    toml = REGIONS.replace("pour_regions = true", "pour_regions = true\npour_min_piece_mm2 = 1.0")
    where = r"GND_B TOP: its pour at \(10\.0, 10\.0\) mm lies inside the pour of GND"
    with pytest.raises(SystemExit, match=where):
        regions("pours", toml, pads=[("GND_B", mm(10, 10))], routes=POCKET)
    code, made = regions("check", toml, pads=[("GND_B", mm(10, 10))], routes=POCKET)
    assert code == 2 and made == [] and re.search(where, capsys.readouterr().out)   # route check finds it first


def test_regions_route_check_judges_a_pour_only_net_by_its_own_area(regions, capsys):
    # a GND pad on the right as well: GND claims both sides, nothing is left for GND_B
    code, _ = regions("check", pads=[("GND", mm(35, 10))])
    out = capsys.readouterr().out
    assert code == 2 and "GND_B (pour-only): 2 groups – C3.2 | C4.2" in out and "shares the layer" not in out
    assert "pour regions TOP: GND 2, GND_B 0 outlines" in out
    code, _ = regions("check", REGIONS.replace("pour_regions = true", ""), pads=[("GND", mm(35, 10))])
    out = capsys.readouterr().out                                                    # as before: the whole outline
    assert "GND_B (pour-only)" not in out and "! GND_B TOP: the pour of GND shares the layer" in out


def test_regions_without_the_key_or_on_a_layer_of_its_own_nothing_changes(regions):
    _, made = regions("pours", REGIONS.replace("pour_regions = true", ""))
    assert [len(p.exterior.coords) for *_, p in made] == [5, 5] and made[0][4].equals(made[1][4])
    alone = REGIONS + '[[pours]]\nnet = "GND"\nlayers = ["BOTTOM"]\npour_only = true\n'
    _, made = regions("pours", alone)
    bottom = [p for net, layer, *_, p in made if layer == 2]
    assert len(bottom) == 1 and len(bottom[0].exterior.coords) == 5 and bottom[0].area == pytest.approx(39 * 19)


APART = REGIONS.replace('net = "GND_B"\nlayers = ["TOP"]', 'net = "GND_B"\nlayers = ["BOTTOM"]')


def test_regions_pcb_pour_needs_the_routing(regions):
    with pytest.raises(SystemExit, match="pour_regions.*main.ses is missing.*route all"):
        regions("pcb pour", ses_file=False)
    code, made = regions("pcb pour", APART, ses_file=False)                         # no shared layer: no routing
    assert code == 0 and [(net, layer) for net, layer, *_ in made] == [("GND", 1), ("GND_B", 2)]


# --- fanout vias to a plane (#10): a 40 x 20 mm board, plane V on BOTTOM, BOTTOM a wire keep-out (vias allowed);
# V = R1.1 (SMD on TOP, R1's centre to its right) and D1.1 (through hole), a wire keep-out on TOP between them

FANOUT = """
[outline]
rect = [40, 20]
[routing]
clearance_mil = 6.5
classes = { POWER = { width_mil = 20, nets = ["V"] } }
[[routing.keepouts]]
layer = "BOTTOM"
what = "wire"
rect = [0, 0, 40, 20]
[[routing.keepouts]]
layer = "TOP"
what = "wire"
rect = [18, 0, 22, 20]
[[pours]]
net = "V"
layers = ["BOTTOM"]
plane = true
"""
D0 = 20 + 12 + 6.5                       # half the pad's larger side + via radius + clearance (mil)


@pytest.fixture
def plane_board(tmp_path):
    def make(extra="fanout = true", head=""):
        (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
        (tmp_path / "hardware" / "boards").mkdir(parents=True, exist_ok=True)
        (tmp_path / "hardware" / "boards" / "main.toml").write_text(head + FANOUT + extra + "\n")
        return route.Rules(config.load(tmp_path / "edakit.toml").board())
    data = {"pcb": "main",
            "components": [{"ref": "R1", "x": mm(11, 10)[0], "y": mm(11, 10)[1], "rot": 0, "layer": 1},
                           {"ref": "R2", "x": mm(7, 4)[0], "y": mm(7, 4)[1], "rot": 0, "layer": 1},
                           {"ref": "D1", "x": mm(31.27, 10)[0], "y": mm(31.27, 10)[1], "rot": 0, "layer": 1}],
            "pads": [pad("R1", "1", "V", *mm(10, 10)), pad("R1", "2", "SIG", *mm(12, 10)),
                     pad("R2", "1", "SIG", *mm(6, 4)), pad("R2", "2", "", *mm(8, 4)),
                     pad("D1", "1", "V", *mm(30, 10), layer=12, shape=("ELLIPSE", 60, 60)),
                     pad("D1", "2", "", *mm(32.54, 10), layer=12, shape=("ELLIPSE", 60, 60))],
            "outlines": [[mm(0, 0), mm(40, 0), mm(40, 20), mm(0, 20)]]}
    return make, data


def wiring(text):
    return text[text.index("  (wiring"):]


def fanout_routes(rules, data):
    """The routes of the fanouts alone, as they come back in the SES."""
    out = {}
    for net, _, layer, w, start, via in route.fanout(rules, data):
        r = out.setdefault(net, {"wires": [], "vias": []})
        r["wires"].append((layer, w, [start, via]))
        r["vias"].append(via)
    return out


def test_fanout_via_and_stub_in_the_dsn(plane_board, tmp_path):
    make, data = plane_board
    route.write_dsn(make(), data, tmp_path / "t.dsn")
    text = wiring((tmp_path / "t.dsn").read_text())
    [via] = re.findall(r'\(via "via24" (\S+) (\S+) \(net "V"\) \(type protect\)\)', text)
    [stub] = re.findall(r'\(wire \(path TOP 20 (\S+) (\S+) (\S+) (\S+)\) \(net "V"\) \(type protect\)\)', text)
    x, y = mm(10, 10)
    assert [float(v) for v in stub] == pytest.approx([x, y, x - D0, y], abs=0.01)  # from R1.1's centre, away from R1
    assert [float(v) for v in via] == pytest.approx([x - D0, y], abs=0.01)


def test_fanout_via_keeps_clearance_edge_and_holes(plane_board):
    from shapely.geometry import LineString, Point
    make, data = plane_board
    data["pads"] += [pad("R3", "1", "V", *mm(1.1, 15)), pad("R3", "2", "", *mm(2.1, 15))]   # V pad at the left edge
    data["components"].append({"ref": "R3", "x": mm(1.6, 15)[0], "y": mm(1.6, 15)[1], "rot": 0, "layer": 1})
    rules = make("fanout = true", "[tooling]\nholes = [[7.8, 10]]\n")              # in R1.1's preferred spot
    fans = route.fanout(rules, data)
    assert [p for _, p, *_ in fans] == ["R1.1", "R3.1"]
    # both prefer the left (away from their part): the tooling hole and the edge leave the nearest free direction
    assert [math.degrees(math.atan2(v[1] - s[1], v[0] - s[0])) for *_, s, v in fans] == pytest.approx([112.5] * 2, abs=0.05)
    assert [math.dist(s, v) for *_, s, v in fans] == pytest.approx([D0] * 2, abs=0.01)
    inner = route.board_area(data)[0].buffer(-rules.edge_um / 25.4)
    keep = Point(*mm(7.8, 10)).buffer(1.5 * MIL)
    for net, name, layer, w, start, via in fans:
        disc = Point(via).buffer(rules.via[1] / 2)
        assert disc.within(inner) and not disc.intersects(keep)
        for p in data["pads"]:
            if p["net"] != net:
                assert disc.distance(route.pad_outline(p)) >= rules.clear - 1e-6
                assert LineString([start, via]).buffer(w / 2).distance(route.pad_outline(p)) >= rules.clear - 1e-6
    assert route.clearance_check(rules, data, fanout_routes(rules, data)) == []


def test_fanout_vias_keep_apart(plane_board):
    make, data = plane_board
    data["pads"] = [dict(p, shape=["RECT", 20, 20]) for p in data["pads"]]
    data["pads"].append(pad("R4", "1", "V", *mm(10, 10.6), shape=("RECT", 20, 20)))  # beside R1.1: same spot first
    data["components"].append({"ref": "R4", "x": mm(11, 10.6)[0], "y": mm(11, 10.6)[1], "rot": 0, "layer": 1})
    vias = [via for *_, via in route.fanout(make(), data)]
    assert len(vias) == 2 and math.dist(*vias) >= 24 + 6.5 - 1e-6


def test_fanout_connects_the_pad_to_the_plane(plane_board, tmp_path):
    make, data = plane_board
    rules = make()
    assert names(data, route.check(rules, data, {})["V"]) == [["R1.1"], ["D1.1"]]  # as today: V open
    assert "V" not in route.check(rules, data, fanout_routes(rules, data))
    # back from Freerouting 2.4.1 as it writes protected wiring into the SES
    [(_, _, _, _, (x0, y0), (x, y))] = route.fanout(rules, data)
    xy = f"{x * 100:.0f} {y * 100:.0f}"
    (tmp_path / "t.ses").write_text(f"""(session t (routes (resolution mil 100) (parser) (network_out
  (net V (via via24 {xy} (type protect)) (wire (path TOP 2000 {x0 * 100:.0f} {y0 * 100:.0f} {xy}) (type protect)))
)))""")
    routes = route.read_ses(tmp_path / "t.ses", rules)
    assert routes["V"]["vias"] == [(x, y)] and "V" not in route.check(rules, data, routes)
    assert route.clearance_check(rules, data, routes) == []                         # the via in BOTTOM's wire keep-out


def test_fanout_pad_without_room_is_an_error(plane_board):
    make, data = plane_board
    x, y = mm(10, 10)
    data["pads"] = [p for p in data["pads"] if p["ref"] != "R1" or p["num"] == "1"]
    data["pads"] += [pad("X", str(k), "", x + dx, y + dy, shape=s) for k, (dx, dy, s) in enumerate(
        [(-140, 0, ("RECT", 200, 480)), (140, 0, ("RECT", 200, 480)), (0, 140, ("RECT", 480, 200)),
         (0, -140, ("RECT", 480, 200))], 1)]                                       # a frame 20 mil from R1.1
    with pytest.raises(SystemExit, match=r"R1\.1 \(V\): no room for a fanout via"):
        route.fanout(make(), data)


def test_without_fanout_nothing_changes(plane_board, tmp_path):
    make, data = plane_board
    rules = make("")
    assert route.fanout(rules, data) == []
    route.write_dsn(rules, data, tmp_path / "t.dsn")
    assert wiring((tmp_path / "t.dsn").read_text()) == "  (wiring\n  )\n)\n"


# --- edge keep-out in inner corners (#11): an L-shaped 40 x 20 mm board, its inner corner at (20, 10) mm, a track at
# 45° passing that corner

L_SHAPE = "[outline]\npolygon = [[0, 0], [40, 0], [40, 10], [20, 10], [20, 20], [0, 20]]\n"
EDGE_REACH_MM = 0.4 * math.cos(math.radians(135 / 8 / 2))  # 0.3957 mm: the arc's chords span ≤ 16.875°, 8 per quarter


def outline_board(tmp_path, outline):
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text(outline)
    board = config.load(tmp_path / "edakit.toml").board()
    data = {"pcb": "main", "components": [], "pads": [], "outlines": [[mm(x, y) for x, y in board.outline]]}
    return route.Rules(board), data


@pytest.fixture
def l_board(tmp_path):
    return outline_board(tmp_path, L_SHAPE)


def past_the_corner(gap_mm, w=10):
    """A track at 45° whose copper comes gap_mm close to the inner corner, and nowhere closer to the outline."""
    s = gap_mm * MIL + w / 2                      # its centre line from the corner, along the diagonal into the board
    x, y = mm(20, 10)
    x, y, d = x - s / math.sqrt(2), y - s / math.sqrt(2), 3 * MIL
    return {"SIG": {"wires": [("TOP", w, [(x - d, y + d), (x + d, y - d)])], "vias": []}}


def edge_findings(rules, data, routes):
    return [f for f in route.clearance_check(rules, data, routes) if "(edge/hole)" in f]


def test_edge_keepout_in_an_inner_corner_is_the_clearance(l_board):
    rules, data = l_board
    assert rules.edge_um == 400
    assert edge_findings(rules, data, past_the_corner(0.423)) == []        # keeps 0.4 mm: before, mitred, 1 finding
    assert len(edge_findings(rules, data, past_the_corner(0.303))) == 1    # closer than 0.4 mm: as before


def test_edge_strips_reach_no_farther_than_the_clearance(l_board):
    from shapely import segmentize
    from shapely.geometry import Point, Polygon
    rules, data = l_board
    outer = Polygon(data["outlines"][0])
    _, strips = route.outside_strips(rules, outer)
    inside = [Point(p) for g in strips for p in segmentize(g.exterior, 1).coords if outer.contains(Point(p))]
    far = max(outer.exterior.distance(p) for p in inside)    # how far the keep-out reaches into the board
    assert far / MIL == pytest.approx(0.400, abs=0.001)      # before: 0.566 mm at the 90° corner
    corner = Point(mm(20, 10))                  # and it covers the corner up to its arc's chords
    assert unary_union(strips).contains(corner.buffer(EDGE_REACH_MM * MIL - 0.01))


def test_edge_strips_of_an_outline_without_inner_corners_stay():
    from shapely.geometry import Polygon
    fixture = Path(__file__).parent / "fixtures" / "led-bar" / "edakit.toml"
    board = config.load(fixture).board()                    # the example: a rectangle with rounded corners
    rules = route.Rules(board)
    outer = Polygon([mm(x, y) for x, y in board.outline])
    frame, strips = route.outside_strips(rules, outer)
    mitred = outer.buffer(-rules.edge_um / 25.4, join_style="mitre")       # how the strips were cut before #11
    assert frame.difference(mitred).symmetric_difference(unary_union(strips)).area < 1e-6


# a 32° notch from the top edge, its tip at (20, 15) mm: the strips are cut at every vertex of the arc around the tip,
# and some of the slices there are smaller than 1 mil²

NOTCH = "[outline]\npolygon = [[0, 0], [40, 0], [40, 20], [20.5, 20], [20, 15], [17.5, 20], [0, 20]]\n"


def test_edge_strips_keep_the_slivers_at_a_notch_tip(tmp_path):
    from shapely.geometry import Polygon
    rules, data = outline_board(tmp_path, NOTCH)
    outer = Polygon(data["outlines"][0])
    frame, strips = route.outside_strips(rules, outer)
    reach = EDGE_REACH_MM * MIL                               # the chords of the arc
    band = frame.difference(outer.buffer(-reach, quad_segs=64))
    missing = band.difference(unary_union(strips).buffer(1e-6))     # 1e-6 mil closes the seams between the strips
    assert missing.area < 1e-9      # before: 2.9 mil² missing, 4 slices < 1 mil² dropped, 0.296 mm reach at the tip


# inner corners of every angle: a V valley in the top edge of a 40 mm wide board, the outline bending by 1° to 179° at
# (20, 20) mm. GEOS gives an arc of θ round(θ / (90° / quad_segs)) chords, at least one: with 4 per quarter circle a
# 33° arc got one chord and a 50° arc two of 25°, wider than the 22.5° behind the 0.392 mm #11 promised. 8 per
# quarter circle: at most 16.875° (an arc just under it gets one chord), the keep-out reaches EDGE_REACH_MM


def edge_reach(outer, strips):
    """How far the edge keep-out reaches into the board at its shallowest point, in mm."""
    free = outer.difference(unary_union(strips).buffer(1e-6))       # 1e-6 mil closes the seams between the strips
    return outer.exterior.distance(free.boundary) / MIL


def test_edge_strips_reach_the_promised_depth_in_every_inner_corner(l_board):
    from shapely.geometry import Polygon
    rules, _ = l_board
    reach = {}
    for bend in range(1, 180):
        h = 20 * math.tan(math.radians(bend / 2))
        outer = Polygon([mm(0, 0), mm(40, 0), mm(40, 20 + h), mm(20, 20), mm(0, 20 + h)])
        reach[bend] = edge_reach(outer, route.outside_strips(rules, outer)[1])
    shallow = {b: round(r, 4) for b, r in reach.items() if r < EDGE_REACH_MM}
    assert shallow == {}    # before: 163 of 179, 77 short of even 0.392 mm, the least 0.3835 mm at 33°


# --- pads of different parts keep the clearance (L-13, #12): R1 and R2 with pads of 0.8 x 0.9 mm in a row at y = 10;
# R1.2 (N2) and R2.1 (N3) 0.09 mm apart, R1's own pads 0.05 mm apart

PAD = ("RECT", 0.8 * MIL, 0.9 * MIL)


def close_pads(**change):
    """{name: {field: value}} changes single pads."""
    xs = {"R1.1": 10.75, "R1.2": 11.6, "R2.1": 12.49, "R2.2": 13.34}
    nets = {"R1.1": "N1", "R1.2": "N2", "R2.1": "N3", "R2.2": "N4"}
    out = []
    for name, x in xs.items():
        ref, num = name.split(".")
        out.append({**pad(ref, num, nets[name], *mm(x, 10), shape=PAD), **change.get(name, {})})
    return out


def gaps(pads, waivers=({}, {})):
    return [(g["a"], g["b"], g["layers"], round(g["mil"] / MIL, 3), g["waived"])
            for g in route.pad_gaps({"pads": pads}, 6.5, waivers)]


def test_pad_gaps_between_parts_on_different_nets():
    assert gaps(close_pads()) == [("R1.2", "R2.1", ["TOP"], 0.09, None)]          # not R1.1-R1.2: one part
    pair = route.pad_gaps({"pads": close_pads()}, 6.5)[0]
    assert route.gap_text(pair, 6.5) == "R1.2 (N2) – R2.1 (N3): 0.090 mm apart on TOP, below the clearance 0.165 mm"
    assert gaps(close_pads(**{"R2.1": {"net": "N2"}})) == []                      # one net
    assert gaps(close_pads(**{"R1.2": {"net": ""}, "R2.1": {"net": ""}}))[0][:2] == ("R1.2", "R2.1")  # no net: its own
    assert gaps(close_pads(**{"R2.1": {"layer": 2}, "R2.2": {"layer": 2}})) == []  # other side
    tht = gaps(close_pads(**{"R2.1": {"layer": 12}}))                              # through hole: on both layers
    assert tht == [("R1.2", "R2.1", ["TOP"], 0.09, None)]
    both = close_pads(**{"R1.2": {"layer": 12}, "R2.1": {"layer": 12}})
    assert gaps(both) == [("R1.2", "R2.1", ["TOP", "BOTTOM"], 0.09, None)]         # one pair, both layers
    assert gaps(close_pads(**{"R2.1": {"ref": None}})) == []                       # no part (a tooling hole)
    assert gaps(close_pads(**{"R2.1": {"x": mm(12.555, 10)[0]}}))[0][3] == 0.155  # below 6.5 mil (0.1651 mm)
    assert gaps(close_pads(**{"R2.1": {"x": mm(12.5651, 10)[0]}})) == []          # at the clearance
    assert gaps(close_pads(), ({"R2": "close on purpose"}, {})) == [("R1.2", "R2.1", ["TOP"], 0.09, "close on purpose")]
    assert gaps(close_pads(), ({}, {"N2": "net tie"}))[0][4] == "net tie"


def check_project(tmp_path, pads, release=""):
    """A 40 x 20 mm board with these pads read, an SES without tracks -> (cfg, args of `route check`)."""
    from argparse import Namespace
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n' + release)
    (tmp_path / "hardware" / "boards").mkdir(parents=True, exist_ok=True)
    (tmp_path / "hardware" / "boards" / "main.toml").write_text("[outline]\nrect = [40, 20]\n")
    cfg = config.load(tmp_path / "edakit.toml")
    P = route.paths(cfg, cfg.board())
    P["board"].write_text(json.dumps({"pcb": "main", "components": [], "pads": pads,
                                      "outlines": [[mm(0, 0), mm(40, 0), mm(40, 20), mm(0, 20)]]}))
    P["ses"].write_text("(session t (routes (resolution mil 100) (parser) (network_out)))")
    return cfg, Namespace(board=None, action="check", verbose=False, clearance=None, passes=None, threads=1,
                          no_optimizer=False, cleanup=False)


def waive(tmp_path, **rules):
    (tmp_path / "hardware" / "graph.json").write_text(json.dumps(
        {"components": [{"designator": "R2", "waive": rules}], "nets": []}))


def test_route_check_finds_pads_too_close_before_anything_is_written(tmp_path, capsys):
    """The proposal's case: on a 40 x 20 mm board, `route check` reported 0 findings for R1.2 (N2) and R2.1 (N3)
    0.090 mm apart. Every net has one pad, the SES no tracks: only L-13 – and L-14, the paste gap below it – have
    something to find."""
    cfg, args = check_project(tmp_path, close_pads())
    assert route.main(cfg, args) == 2
    out = capsys.readouterr().out
    assert "pads of different parts: 1 pairs closer than the clearance 6.5 mil" in out
    assert "R1.2 (N2) – R2.1 (N3): 0.090 mm apart on TOP" in out and "clearances/keep-outs: 0 findings" in out
    waive(tmp_path, **{"L-13": "close on purpose"})
    assert route.main(cfg, args) == 2                                              # the paste gap (L-14) still
    out = capsys.readouterr().out
    assert "0 pairs closer than the clearance 6.5 mil, 1 waived (L-13)" in out
    assert "SMD pads of different parts on TOP and BOTTOM: 1 pairs closer than the paste gap 0.4 mm" in out
    waive(tmp_path, **{"L-13": "close on purpose", "L-14": "close on purpose"})
    assert route.main(cfg, args) == 0                                              # waived in the graph
    assert "0 pairs closer than the paste gap 0.4 mm, 1 waived (L-14)" in capsys.readouterr().out


# --- SMD pads of different parts leave a paste gap (L-14, #13): the same row with R2 0.21 mm further right, so that
# R1.2 (N2) and R2.1 (N3) are 0.30 mm apart – above the clearance (L-13), below the paste gap of 0.4 mm

def paste_pads(**change):
    xs = {"R2.1": 12.70, "R2.2": 13.55}
    return close_pads(**{n: {"x": mm(x, 10)[0], **change.get(n, {})} for n, x in xs.items()},
                      **{n: c for n, c in change.items() if n not in xs})


def paste_gaps(pads, sides=("TOP", "BOTTOM"), waivers=({}, {})):
    return [(g["a"], g["b"], g["layers"], round(g["mil"] / MIL, 3), g["waived"])
            for g in route.pad_gaps({"pads": pads}, 0.4 * MIL, waivers, sides)]


def test_paste_gap_between_smd_pads_on_the_assembled_sides():
    assert gaps(paste_pads()) == []                                                 # no L-13: above the clearance
    assert paste_gaps(paste_pads()) == [("R1.2", "R2.1", ["TOP"], 0.3, None)]
    pair = route.pad_gaps({"pads": paste_pads()}, 0.4 * MIL, smd_on=("TOP",))[0]
    assert route.gap_text(pair, 0.4 * MIL, "the paste gap") == \
        "R1.2 (N2) – R2.1 (N3): 0.300 mm apart on TOP, below the paste gap 0.400 mm"
    assert paste_gaps(paste_pads(), ("BOTTOM",)) == []                              # TOP not assembled
    assert paste_gaps(paste_pads(), ()) == []                                       # nothing assembled
    bottom = {n: {"layer": 2} for n in ("R1.1", "R1.2", "R2.1", "R2.2")}
    assert paste_gaps(paste_pads(**bottom), ("BOTTOM",)) == [("R1.2", "R2.1", ["BOTTOM"], 0.3, None)]
    assert paste_gaps(paste_pads(**{"R2.1": {"layer": 12}})) == []                  # through hole: no paste
    assert paste_gaps(paste_pads(**{"R2.1": {"net": "N2"}})) == []                  # one net
    assert paste_gaps(paste_pads(**{"R1.2": {"net": ""}}))[0][:2] == ("R1.2", "R2.1")  # no net: a net of its own
    assert paste_gaps(paste_pads(**{"R2.1": {"x": mm(12.8, 10)[0]}})) == []         # 0.40 mm: at the paste gap
    only_l13 = route.pad_waivers({"components": [{"designator": "R2", "waive": {"L-13": "x"}}]}, "L-14")
    assert paste_gaps(paste_pads(), waivers=only_l13)[0][4] is None                 # waivers per check
    net = route.pad_waivers({"nets": [{"name": "N3", "waive": {"L-14": "paste reduced"}}]}, "L-14")
    assert paste_gaps(paste_pads(), waivers=net)[0][4] == "paste reduced"


def test_paste_rule_from_release_assembly(tmp_path):
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n')
    gap, sides = route.paste_rule(config.load(tmp_path / "edakit.toml"))
    assert (round(gap / MIL, 6), sides) == (0.4, ("TOP", "BOTTOM"))                # as F-3: both sides by default
    (tmp_path / "edakit.toml").write_text('[project]\nname = "t"\n[boards.main]\n[release]\n'
                                          'assembly = { sides = ["top"], paste_gap_mm = 0.5 }\n')
    gap, sides = route.paste_rule(config.load(tmp_path / "edakit.toml"))
    assert (round(gap / MIL, 6), sides) == (0.5, ("TOP",))


def test_route_check_finds_smd_pads_closer_than_the_paste_gap(tmp_path, capsys):
    """#13's case: SMD pads of two parts on different nets 0.30 mm apart on a 40 x 20 mm board – `route check`
    reported 0 findings, and the clearance (L-13) has none. L-14 stops the check; assembled on the other side only,
    the pads get no paste and it passes."""
    cfg, args = check_project(tmp_path, paste_pads())
    assert route.main(cfg, args) == 2
    out = capsys.readouterr().out
    assert "pads of different parts: 0 pairs closer than the clearance 6.5 mil" in out
    assert "SMD pads of different parts on TOP and BOTTOM: 1 pairs closer than the paste gap 0.4 mm" in out
    assert "R1.2 (N2) – R2.1 (N3): 0.300 mm apart on TOP, below the paste gap 0.400 mm" in out
    cfg, args = check_project(tmp_path, paste_pads(), '[release]\nassembly = { sides = ["bottom"] }\n')
    assert route.main(cfg, args) == 0
    assert "SMD pads of different parts on BOTTOM: 0 pairs" in capsys.readouterr().out


# --- widths from the simulated currents (#58): the example's input stage routed at 18 mil on TOP – J1 (through-hole)
# at (84, 12) turned by 90°, D1 (SMA) at (75, 12), C2 (0805) at (68, 12) –, 90 x 40 mm, net_currents.json beside it

def stage_pad(ref, num, net, x, y, w, h, tht=False):
    return {**pad(ref, num, net, *mm(x, y), layer=12 if tht else 1, shape=("ELLIPSE" if tht else "RECT", w * MIL,
                                                                        h * MIL)),
            "hole": [1.0 * MIL] if tht else None}


STAGE = {"pcb": "main",
         "components": [{"ref": r, "x": mm(x, y)[0], "y": mm(x, y)[1], "rot": rot, "layer": 1}
                        for r, x, y, rot in (("J1", 84, 12, 90), ("D1", 75, 12, 0), ("C2", 68, 12, 0))],
         "pads": [stage_pad("J1", "1", "VIN", 84, 11, 1.4, 1.4, tht=True),
                  stage_pad("J1", "2", "GND", 84, 13, 1.4, 1.4, tht=True),
                  stage_pad("D1", "1", "+5V", 72.8, 12, 2.5, 1.7), stage_pad("D1", "2", "VIN", 77.2, 12, 2.5, 1.7),
                  stage_pad("C2", "1", "+5V", 67.05, 12, 1.0, 1.3), stage_pad("C2", "2", "GND", 68.95, 12, 1.0, 1.3)],
         "outlines": [[mm(0, 0), mm(90, 0), mm(90, 40), mm(0, 40)]]}
FIXED_GND = [(84, 15), (80, 15)]       # the piece of the GND track a [[routing.fixed_wires]] entry protects


def stage_ses(gnd_fixed_mil=None):
    """The SES Freerouting would return: every track 18 mil; with gnd_fixed_mil the fixed GND piece at its own width."""
    def path(w, pts):
        return f"(wire (path TOP {round(w * 100)} " + " ".join(f"{round(v * 100)}" for p in pts for v in mm(*p)) + "))"
    gnd = [path(18, [(84, 13), (84, 15), (68.95, 15), (68.95, 12)])]
    if gnd_fixed_mil:
        gnd = [path(18, [(84, 13), (84, 15)]), path(gnd_fixed_mil, FIXED_GND),
               path(18, [(80, 15), (68.95, 15), (68.95, 12)])]
    return ("(session main (routes (resolution mil 100) (parser) (network_out\n"
            f'  (net "VIN" {path(18, [(84, 11), (77.2, 11), (77.2, 12)])})\n'
            f'  (net "+5V" {path(18, [(72.8, 12), (72.8, 10), (67.05, 10), (67.05, 12)])})\n'
            f'  (net "GND" {" ".join(gnd)})\n)))\n')


def routed_stage(project, currents=None, gnd_fixed_mil=None, routing=""):
    """The example with the routed input stage as `route read` and Freerouting leave it; currents {net: A} as
    `edakit sim` writes them (None: no net_currents.json); routing: lines for [routing] of the board file."""
    f = project.root / "hardware" / "boards" / "main.toml"
    text = (EXAMPLE / "hardware" / "boards" / "main.toml").read_text()      # each call starts from the example's
    text = text.replace("attempts = 5 ", f"attempts = 5\n{routing}\n" if routing else "attempts = 5 ")
    if gnd_fixed_mil:
        text = text.replace("[[pours]]", '[[routing.fixed_wires]]\nnet = "GND"\nlayer = "TOP"\n'
                                          f"width_mil = {gnd_fixed_mil}\npoints = {[list(p) for p in FIXED_GND]}\n\n"
                                          "[[pours]]", 1)
    f.write_text(text)
    d = project.root / "build" / "edakit"
    (d / "route").mkdir(parents=True, exist_ok=True)
    (d / "route" / "main_board.json").write_text(json.dumps(STAGE))
    (d / "route" / "main.ses").write_text(stage_ses(gnd_fixed_mil))
    if currents is not None:
        (d / "sim").mkdir(exist_ok=True)
        (d / "sim" / "net_currents.json").write_text(json.dumps(
            {"nets": {n: {"i_max_a": i, "scenario": "test"} for n, i in currents.items()}}))
    return project.config()


def route_cmd(project, action, capsys):
    from edakit import cli
    code = cli.main(["route", action, "--config", str(project.root / "edakit.toml")])
    return code, re.sub(r"\[ *[\d.]+ min\] ", "", capsys.readouterr().out)


TWO_AMPS = {"VIN": 2.0, "+5V": 2.0, "GND": 2.0, "3V3": 0.0144}


def test_route_check_holds_the_ipc_width_of_the_simulated_current(project, capsys):
    routed_stage(project, TWO_AMPS)
    code, out = route_cmd(project, "check", capsys)
    assert code == 2
    assert "L-5 (offline) VIN: 0.46 < 1.37 mm" in out and "L-5 (offline) GND: 0.46 < 1.37 mm" in out
    assert "check: 3 nets routed, 8 track pieces, 0 vias; open: 0" in out    # connected all the same


def test_route_check_without_net_currents_as_before(project, capsys):
    routed_stage(project)
    code, out = route_cmd(project, "check", capsys)
    assert code == 0 and "open: 0" in out and "clearances/keep-outs: 0 findings" in out
    assert [ln for ln in out.splitlines() if "L-5" in ln] == [
        "track widths (L-5 offline): no net currents – run `edakit sim` first"]


def test_route_check_names_a_fixed_wire_below_its_net(project, capsys):
    routed_stage(project, {"VIN": 0.1, "+5V": 0.1, "GND": 0.85}, gnd_fixed_mil=16)   # IPC for GND 0.42 mm
    code, out = route_cmd(project, "check", capsys)
    assert code == 2 and "L-5 (offline) fixed wire GND (84, 15)–(80, 15): 0.41 < 0.42 mm" in out
    gnd = [ln for ln in out.splitlines() if "L-5 (offline) GND:" in ln]       # the routed GND tracks: wide enough
    assert gnd == ["    L-5 (offline) GND: 0.46 < 0.60 mm – below the practical width of its class (warning)"]


def test_route_check_passes_a_fixed_wire_at_the_ipc_width(project, capsys):
    routed_stage(project, {"VIN": 0.1, "+5V": 0.1, "GND": 0.85}, gnd_fixed_mil=18)
    code, out = route_cmd(project, "check", capsys)
    assert code == 0
    assert "below IPC" not in out.replace("0 below IPC", "")
    assert "L-5 (offline) GND: 0.46 < 0.60 mm" in out and "warning" in out   # below the class width: a warning


def test_dsn_widths_from_the_simulation(project, capsys, tmp_path):
    cfg = routed_stage(project, TWO_AMPS)
    data = json.loads((project.root / "build" / "edakit" / "route" / "main_board.json").read_text())
    rules = route.Rules(cfg.board())
    route.write_dsn(rules, data, tmp_path / "classes.dsn")
    cfg = routed_stage(project, TWO_AMPS, routing='widths = "classes"')
    route.write_dsn(route.Rules(cfg.board()), data, tmp_path / "explicit.dsn")
    assert (tmp_path / "explicit.dsn").read_text() == (tmp_path / "classes.dsn").read_text()   # the default
    cfg = routed_stage(project, TWO_AMPS, routing='widths = "sim"')
    code, out = route_cmd(project, "dsn", capsys)
    text = (project.root / "build" / "edakit" / "route" / "main.dsn").read_text()
    widths = {m[0]: float(m[1]) for m in re.findall(r'\(class "(\w+)" .*\(rule \(width ([\d.]+)\)', text)}
    assert code == 0 and widths["POWER"] >= 53.8 and widths["GND"] >= 53.8
    assert "class POWER: 18 -> 53.9 mil" in out


def test_sim_widths_give_a_net_outside_the_classes_a_class_of_its_own(project):
    cfg = routed_stage(project, {**TWO_AMPS, "BTN": 1.0, "LED_SDI": 0.01}, routing='widths = "sim"')
    rules = route.Rules(cfg.board())
    route.sim_widths(cfg, cfg.board(), rules)
    assert rules.net_class("BTN") == ("BTN", 20.7)            # IPC 0.53 mm for 1 A above signal_mil 10
    assert rules.net_class("LED_SDI") == ("SIGNAL", 10)       # below signal_mil: as before
    assert rules.net_class("3V3") == ("SUPPLY", 12)           # a class wide enough stays as it is


# --- a declared visible side (#61): the routed input stage with +5V on a detour of 0.18 m on BOTTOM through two vias

DETOUR = [(72.8, 8), (5, 8), (5, 35), (67.05, 35), (67.05, 8)]      # BOTTOM: 67.8 + 27 + 62.05 + 27 mm


def with_detour(project):
    """+5V from D1.1 down to a via, along BOTTOM, up through a via to C2.1 – TOP keeps 0.04 m, BOTTOM gets 0.18 m."""
    def path(layer, pts):
        return f"(wire (path {layer} 1800 " + " ".join(f"{round(v * 100)}" for p in pts for v in mm(*p)) + "))"
    vias = " ".join(f'(via "via24" {round(mm(*p)[0] * 100)} {round(mm(*p)[1] * 100)})' for p in (DETOUR[0], DETOUR[-1]))
    five = (f'(net "+5V" {path("TOP", [(72.8, 12), DETOUR[0]])} {path("BOTTOM", DETOUR)} '
            f'{path("TOP", [DETOUR[-1], (67.05, 12)])} {vias})')
    f = project.root / "build" / "edakit" / "route" / "main.ses"
    f.write_text(re.sub(r'\(net "\+5V" \(wire [^\n]*\)\)', lambda m: five, f.read_text()))


def looks(project, capsys, keys=None):
    routed_stage(project)
    if keys is not None:
        f = project.root / "hardware" / "boards" / "main.toml"
        f.write_text(f.read_text() + f"\n[looks]\n{keys}\n")
    with_detour(project)
    code, out = route_cmd(project, "check", capsys)
    return code, out, [ln.strip() for ln in out.splitlines() if "tracks:" in ln or "(visible)" in ln]


def test_route_check_reports_the_visible_side(project, capsys):
    code, out, lines = looks(project, capsys)
    assert code == 0 and lines == [] and "2 vias; open: 0" in out                    # no [looks]: as before
    code, out, lines = looks(project, capsys, 'visible = "bottom"')
    assert code == 0 and lines == ["tracks: TOP 0.04 m, BOTTOM 0.18 m; vias 2", "BOTTOM (visible): 0.18 m of track, 2 vias"]
    code, out, lines = looks(project, capsys, 'visible = "bottom"\nmax_track_m = 0.1\nmax_vias = 1')
    assert code == 0 and lines[2:] == ["BOTTOM (visible): 0.18 m of track, limit 0.1 m – warning",
                                        "BOTTOM (visible): 2 vias, limit 1 – warning"]
    code, out, lines = looks(project, capsys, 'visible = "top"\nmax_track_m = 0.1\nmax_vias = 2')
    assert code == 0 and lines[1:] == ["TOP (visible): 0.04 m of track, 2 vias"]      # within both limits


# --- route diagnose (#63): why a connection stays open. On the pour board above (GND an ordinary net here): C1.2 and
# C2.2 apart on TOP, the SIG track from the top edge to the bottom edge (SIG_TOP) walls TOP in two; on the example's
# routed input stage: J1.2 (GND) inside a keep-out on both layers, GND left open in the SES.

BOTTOM_WIRE_KEEP = '\n[[routing.keepouts]]\nlayer = "BOTTOM"\nwhat = "wire"\nrect = [0, 0, 40, 20]\n'


def test_diagnose_a_connection_cut_by_the_track_of_another_net(pour_board):
    make, data = pour_board
    [gap] = route.diagnose(make(BOTTOM_WIRE_KEEP), data, SIG_TOP)["open"]
    assert (gap["net"], gap["a"], gap["b"], gap["verdict"], gap["blocked_by"]) == ("GND", "C1.2", "C2.2", "blocked",
                                                                                  ["SIG"])
    assert re.fullmatch(r"GND C1\.2 – C2\.2: blocked by SIG – utilisation \d\.\d\d at \(\d+, \d+\) mm", gap["line"])
    assert gap["way_mm"] == pytest.approx(30, abs=1.5)                    # the empty board's way: straight across


def test_diagnose_a_way_through_the_other_layer_is_not_unreachable(pour_board):
    make, data = pour_board
    [gap] = route.diagnose(make(""), data, SIG_TOP)["open"]               # BOTTOM free: through vias around the wall
    assert gap["verdict"] == "free" and "blocked_by" not in gap
    assert gap["line"] == ("GND C1.2 – C2.2: open, but a free way is left – Freerouting did not find it (more passes, "
                           "another order: route all's attempts)")
    assert route.diagnose(make(""), data, SIG_BOTTOM)["open"][0]["verdict"] == "free"


def test_diagnose_the_wall_alone_is_no_gap(pour_board):
    make, data = pour_board
    gnd = {"GND": {"wires": [("BOTTOM", 10, [mm(5, 10), mm(35, 10)])], "vias": [mm(5, 10), mm(35, 10)]}}
    assert route.diagnose(make(BOTTOM_WIRE_KEEP.replace("wire", "all")), data, {**SIG_TOP, **gnd})["open"] == []


def test_congestion_of_a_dense_strip_above_a_sparse_one(pour_board):
    make, data = pour_board
    dense = [pad(f"A{i}", "1", f"N{i}", *mm(10, 6 + 0.1 * i)) for i in range(20)] + \
            [pad(f"B{i}", "1", f"N{i}", *mm(15, 6 + 0.1 * i)) for i in range(20)]   # 20 nets across a 5 mm strip
    sparse = [pad("S1", "1", "S", *mm(25, 15)), pad("S2", "1", "S", *mm(35, 15))]
    data = {**data, "pads": data["pads"] + dense + sparse}
    c = route.congestion(make(""), data)
    hot, cool = route.utilisation_at(c, *mm(12.5, 7)), route.utilisation_at(c, *mm(30, 15))
    assert hot > 1 > cool and hot > 5 * cool
    assert c["max"] >= hot and abs(c["at"][0] - 12.5) <= 2 and abs(c["at"][1] - 7) <= 2   # plan mm


def gnd_walled_in(project, windows=False):
    """The routed input stage with GND open in the SES and J1.2 inside a keep-out on both layers (K0)."""
    routed_stage(project)
    f = project.root / "hardware" / "boards" / "main.toml"
    f.write_text(f.read_text() + '\n[[routing.keepouts]]\nlayer = ["TOP", "BOTTOM"]\nwhat = "all"\n'
                                 'rect = [82.5, 12.2, 85.5, 14.5]\n' + ('windows = ["J1"]\n' if windows else ""))
    ses = project.root / "build" / "edakit" / "route" / "main.ses"
    ses.write_text(re.sub(r'  \(net "GND" .*\n', "", ses.read_text()))


def test_route_diagnose_names_the_keepout_that_walls_a_pad_in(project, capsys):
    gnd_walled_in(project)
    code, out = route_cmd(project, "check", capsys)
    assert code == 2 and "GND: 2 groups – J1.2 | C2.2" in out              # today: open, the keep-out not named
    code, out = route_cmd(project, "diagnose", capsys)
    assert code == 2
    assert "    GND J1.2 – C2.2: unreachable – J1.2 enclosed by keep-out K0 (TOP, BOTTOM)" in out.splitlines()
    d = project.root / "build" / "edakit" / "route" / "main_diagnose"
    report = json.loads((d / "diagnose.json").read_text())
    assert [g["verdict"] for g in report["open"]] == ["unreachable"] and report["open"][0]["enclosed_by"] == [
        "keep-out K0 (TOP, BOTTOM)"]
    assert (d / report["open"][0]["png"]).exists() and (d / "congestion.png").exists()
    assert report["congestion"]["max"] > 0


def test_route_diagnose_with_a_window_for_the_part(project, capsys):
    gnd_walled_in(project, windows=True)
    code, out = route_cmd(project, "diagnose", capsys)
    assert code == 2 and "unreachable" not in out
    assert "GND J1.2 – C2.2: open, but a free way is left" in out


def test_route_diagnose_with_nothing_open(project, capsys):
    routed_stage(project)
    code, out = route_cmd(project, "diagnose", capsys)
    assert code == 0 and "diagnose: nothing open" in out
    assert route_cmd(project, "diagnose", capsys)[0] == 0


def test_route_diagnose_one_net(project, capsys):
    gnd_walled_in(project)
    from edakit import cli
    assert cli.main(["route", "diagnose", "--net", "VIN", "--config", str(project.root / "edakit.toml")]) == 0
    assert "VIN: not open" in capsys.readouterr().out
