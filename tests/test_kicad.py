"""The KiCad tool chain (toolchain = "kicad", handbook 16): the key, the S-expressions, the board's library and PCB
as files – written from the plan, read back into what the shared checks read (docs/concepts/new/kicad-toolchain.md,
steps T.2 to T.7). Nothing here needs KiCad: kicad-cli is faked where a step calls it."""

import json
import re

import pytest
from test_pcb import led_bar_geo

from edakit import config
from edakit.config import ConfigError
from edakit.design import Design
from edakit.part import file_name
from edakit.toolchain import kicad
from edakit.toolchain.kicad import board as kb
from edakit.toolchain.kicad import library, sexp


def kicad_project(project, rows=None):
    """The example as a KiCad project: toolchain = "kicad", no EasyEDA document names, the library's footprints in the
    cache (from test_pcb's geometry: boxes from the footprint names, pads as the packages have them). rows: [place]
    rows replaced, {ref: row text}."""
    t = (project.root / "edakit.toml").read_text()
    t = t.replace('name = "led-bar"', 'name = "led-bar"\ntoolchain = "kicad"')
    (project.root / "edakit.toml").write_text(re.sub(r"^(template|schematic|pcb) = .*\n", "", t, flags=re.M))
    f = project.root / "hardware" / "boards" / "main.toml"
    text = f.read_text()
    for ref, row in (rows or {}).items():
        text = re.sub(rf"^{ref} = .*$", f"{ref} = {row}", text, flags=re.M)
    f.write_text(text)
    geo, d = led_bar_geo(), project.root / "build" / "edakit" / "footprints"
    d.mkdir(parents=True, exist_ok=True)
    g = project.graph()["graph"]
    for c in g["components"]:
        name = project.part(c["lcsc"])["footprint"]
        fp = json.loads(json.dumps(geo[c["designator"]]))
        fp["footprint"] = name
        for p in fp["pads"].values():
            if p["tht"]:
                p.update(shape="ELLIPSE", w=70, h=70, rot=0, layer="MULTI", hole=[1.0, 1.0], plated=True)
            else:
                p.update(shape="RECT", w=40, h=50, rot=0, layer="TOP")
        b = fp["bbox"]
        fp["silk"] = [{"layer": "TOP", "points": [[b[0], b[1]], [b[2], b[1]]], "width": 6, "fill": False}]
        (d / file_name(name)).write_text(json.dumps(fp))
    return project.config()


def cached(cfg, design, ref):
    return json.loads((cfg.artifacts / "footprints" / file_name(design.part(ref)["footprint"])).read_text())


# --- the key -----------------------------------------------------------------------------------------------------------

def test_without_the_key_the_project_stays_easyeda(project):
    cfg = project.config()
    assert cfg.toolchain == "easyeda" and not kicad(cfg)


def test_the_key_chooses_kicad_and_its_folder(project):
    cfg = kicad_project(project)
    assert kicad(cfg)
    assert cfg.kicad_dir(cfg.board()) == project.root / "build" / "edakit" / "kicad" / "main"


def test_an_unknown_tool_chain_is_refused(project):
    t = (project.root / "edakit.toml").read_text()
    (project.root / "edakit.toml").write_text(t.replace('name = "led-bar"', 'name = "led-bar"\ntoolchain = "altium"'))
    with pytest.raises(ConfigError, match="toolchain must be one of easyeda, kicad"):
        project.config()


def test_easyeda_document_names_are_refused_with_kicad(project):
    t = (project.root / "edakit.toml").read_text()
    (project.root / "edakit.toml").write_text(t.replace('name = "led-bar"', 'name = "led-bar"\ntoolchain = "kicad"'))
    with pytest.raises(ConfigError, match=r"\[boards.main\] template: the name of an EasyEDA document"):
        config.load(project.root / "edakit.toml")


# --- S-expressions -----------------------------------------------------------------------------------------------------

def test_sexp_round_trip_keeps_quotes_words_and_numbers():
    node = ["footprint", 'a "b" \\ c', ["at", 1.5, -0.0000001, 90], ["layer", "F.Cu"], ["hide", True],
            ["pad", "1", sexp.Sym("smd"), sexp.Sym("rect")]]
    text = sexp.dumps(node)
    assert '(at 1.5 0 90)' in text and "(hide yes)" in text and '(pad "1" smd rect)' in text
    back = sexp.loads(text)
    assert back[1] == 'a "b" \\ c'
    assert sexp.floats(back, "at") == [1.5, 0, 90]
    assert sexp.value(back, "layer") == "F.Cu" and isinstance(back[5][2], sexp.Sym)


def test_uid_is_the_same_every_run():
    assert sexp.uid("main", "footprint", "R1") == sexp.uid("main", "footprint", "R1") != sexp.uid("main", "R2")


# --- the library -------------------------------------------------------------------------------------------------------

def test_footprints_from_the_cache_with_pads_holes_and_silkscreen(project):
    cfg = kicad_project(project)
    design = Design.from_config(cfg)
    fps = library.footprints(cfg, design, ["J1", "R1", "U2"], fetch=False)
    j1 = fps["J1"]
    assert j1.tht and {p.kind for p in j1.pads} == {"thru_hole"} and j1.pads[0].drill == (1.0,)
    assert j1.package == "CONN-TH_B2B-PH-K-S"
    text = library.module(fps["U2"])
    root = sexp.loads(text)
    assert root[0] == "footprint" and sexp.value(root, "version") == str(library.VERSION)
    pads = list(sexp.find(root, "pad"))
    assert len(pads) == 16 and all(p[2] == "smd" for p in pads)
    assert any(sexp.value(g, "layer") == "F.SilkS" for g in sexp.find(root, "fp_line"))


def test_a_slot_lies_along_the_long_side_of_its_pad():
    pad = library.pad_of("1", {"x": 0, "y": 0, "shape": "OVAL", "w": 40, "h": 80, "rot": 0, "hole": [0.6, 1.2],
                               "plated": True, "layer": "MULTI"})
    assert pad.drill == ("oval", 0.6, 1.2) and pad.shape == "oval" and pad.kind == "thru_hole"
    flat = library.pad_of("1", {"x": 0, "y": 0, "shape": "OVAL", "w": 80, "h": 40, "hole": [0.6, 1.2],
                                "plated": False})
    assert flat.drill == ("oval", 1.2, 0.6) and flat.kind == "np_thru_hole"


def test_footprint_data_brings_its_marks_as_strokes():
    data = {"pads": {"1": {"x": -1, "y": 0, "shape": "RECT", "w": 1, "h": 1}, "2": {"x": 1, "y": 0, "shape": "RECT",
                                                                                      "w": 1, "h": 1}},
            "marks": [{"sign": "+", "x": -2, "y": 0, "size": 0.8}], "outline": [[-1.5, -1], [1.5, -1], [1.5, 1]]}
    out = library.data_graphics(data)
    plus = sorted(tuple(map(tuple, g.points)) for g in out if g.layer == "F.SilkS")
    assert plus == [((-2.4, 0), (-1.6, 0)), ((-2, 0.4), (-2, -0.4))]          # a "+": two strokes, y down
    assert any(g.layer == "F.Fab" for g in out)


# --- the PCB ---------------------------------------------------------------------------------------------------------

def plan_pads(cfg, board, design):
    """Every pad where Board.transform puts it (mil, EasyEDA's frame) – the plan's view of the board."""
    out = {}
    for ref, row in board.place.items():
        for num, p in cached(cfg, design, ref)["pads"].items():
            x, y = board.transform((p["x"], p["y"]), row.x, row.y, row.rot, row.side)
            out[f"{ref}.{num}"] = tuple(v * config.MIL_PER_MM for v in board.eda_point(x, y))
    return out


@pytest.mark.parametrize("rows", [
    {},
    {"R2": '{ x = 40.0, y = 30.0, rot = 90, side = "bottom", auto = true }',
     "D1": '{ x = 75.0, y = 12.0, rot = 180, side = "bottom" }', "SW1": '{ x = 80, y = 25, rot = 270, side = "top" }'},
])
def test_every_pad_lies_where_the_plan_puts_it(project, rows):
    cfg = kicad_project(project, rows)
    board, design = cfg.board(), Design.from_config(cfg)
    path, parked = kb.write_parts(cfg, board)
    assert path.exists() and parked == []
    read = {f"{p['ref']}.{p['num']}": p for p in kb.board_json(cfg, board)["pads"] if p["ref"]}
    for key, (x, y) in plan_pads(cfg, board, design).items():
        assert read[key]["x"] == pytest.approx(x, abs=0.01) and read[key]["y"] == pytest.approx(y, abs=0.01), key
        assert read[key]["net"] == design.pin_net.get(key, "")


def test_view_from_the_bottom_mirrors_like_easyeda(project):
    cfg = kicad_project(project)
    f = project.root / "hardware" / "boards" / "main.toml"
    f.write_text(f.read_text().replace('view = "top"', 'view = "bottom"'))
    cfg = project.config()
    board, design = cfg.board(), Design.from_config(cfg)
    kb.write_parts(cfg, board)
    read = {f"{p['ref']}.{p['num']}": p for p in kb.board_json(cfg, board)["pads"] if p["ref"]}
    for key, (x, y) in plan_pads(cfg, board, design).items():
        assert (read[key]["x"], read[key]["y"]) == pytest.approx((x, y), abs=0.01), key


def test_bottom_parts_measure_as_the_library_footprint(project):
    cfg = kicad_project(project, {"R2": '{ x = 40.0, y = 30.0, rot = 90, side = "bottom" }'})
    board, design = cfg.board(), Design.from_config(cfg)
    kb.write_parts(cfg, board)
    geo = kb.geometry(cfg, board)
    for ref in ("R2", "U2", "J1"):
        want = cached(cfg, design, ref)["pads"]
        for num, p in want.items():
            q = geo[ref]["pads"][num]
            assert (q["x"], q["y"]) == pytest.approx((p["x"], p["y"]), abs=0.01), f"{ref}.{num}"
    assert geo["J1"]["pads"]["1"]["hole"] == [1.0, 1.0] and geo["J1"]["footprint"] == "CONN-TH_B2B-PH-K-S"


def test_pcb_json_has_the_parts_their_nets_and_no_tooling_hole(project):
    from edakit.release import fab
    cfg = kicad_project(project)
    board, design = cfg.board(), Design.from_config(cfg)
    kb.write_parts(cfg, board)
    data = kb.pcb_json(cfg, board)
    assert sorted(c["designator"] for c in data["components"]) == sorted(design.board_comps("main"))
    d = project.root / "build" / "fab" / "main"
    d.mkdir(parents=True)
    (d / "pcb.json").write_text(json.dumps(data))
    (d / "drc.json").write_text("[]")
    rows = fab.Rows()
    fab.check_pcb(cfg, board, design, d, rows)
    l1 = [r for r in rows if r["id"] in ("L-1", "L-4")]
    assert l1 and all(r["result"] == "pass" for r in l1), l1
    holes = [p for p in kb.board_json(cfg, board)["pads"] if p["ref"] is None]
    assert len(holes) == len(board.tooling) and all(p["hole"] == ["ROUND", pytest.approx(1.152 * config.MIL_PER_MM)]
                                                    for p in holes)


def test_outline_and_mounting_holes_come_back_as_outlines(project):
    cfg = kicad_project(project)
    board = cfg.board()
    kb.write_parts(cfg, board)
    loops = kb.board_json(cfg, board)["outlines"]
    xs = [p[0] for p in loops[0]]
    assert len(loops) == 1 + len(board.holes)
    assert (min(xs), max(xs)) == pytest.approx((0, 90 * config.MIL_PER_MM), abs=0.01)


def test_a_part_without_a_row_is_parked_and_then_kept_where_it_lies(project):
    cfg = kicad_project(project)
    f = project.root / "hardware" / "boards" / "main.toml"
    f.write_text("\n".join(ln for ln in f.read_text().splitlines() if not ln.startswith("R2 = ")) + "\n")
    cfg = project.config()
    board = cfg.board()
    _, parked = kb.write_parts(cfg, board)
    assert parked == ["R2"]
    pcb = kb.load(cfg, board)
    fp = pcb.footprint("R2")
    fp[[i for i, c in enumerate(fp) if isinstance(c, list) and c[0] == "at"][0]] = ["at", 12.5, -7.5, 0]
    pcb.save(cfg, board)
    _, parked = kb.write_parts(cfg, board)
    assert parked == [] and sexp.floats(kb.load(cfg, board).footprint("R2"), "at")[:2] == [12.5, -7.5]


def test_tracks_vias_and_zones_are_written_and_kept_by_the_next_parts_run(project):
    from edakit import route
    cfg = kicad_project(project)
    board = cfg.board()
    kb.write_parts(cfg, board)
    data = kb.board_json(cfg, board)
    rules = route.Rules(board)
    a = next(p for p in data["pads"] if p["ref"] == "C1" and p["num"] == "2")       # GND
    routes = {"GND": {"wires": [("TOP", 18, [(a["x"], a["y"]), (a["x"], a["y"] - 100)])],
                      "vias": [(a["x"], a["y"] - 100)]}}
    assert kb.write_copper(cfg, board, rules, routes, data) == (1, 1)
    assert kb.write_zones(cfg, board) == 2                                          # GND on TOP and BOTTOM
    kb.write_parts(cfg, board)                                                     # pcb apply again: copper stays
    pcb = kb.load(cfg, board)
    assert len(pcb.tracks) == 2 and len(pcb.zones) == 2
    lines = kb.pcb_json(cfg, board)["lines"]
    assert lines == [{"Net": "GND", "Layer": 1, "LineWidth": pytest.approx(18), "StartX": pytest.approx(a["x"]),
                      "StartY": pytest.approx(a["y"]), "EndX": pytest.approx(a["x"]),
                      "EndY": pytest.approx(a["y"] - 100)}]
    assert kb.vias(cfg, board) == [(pytest.approx(a["x"]), pytest.approx(a["y"] - 100), pytest.approx(24), "GND")]


def test_the_project_file_carries_the_rules_of_the_board_file(project):
    cfg = kicad_project(project)
    board = cfg.board()
    kb.write_parts(cfg, board)
    pro = json.loads(kb.paths(cfg, board)["pro"].read_text())
    rules = pro["board"]["design_settings"]["rules"]
    assert rules["min_clearance"] == pytest.approx(6.5 / config.MIL_PER_MM)
    assert rules["min_copper_edge_clearance"] == pytest.approx(0.4)
    classes = {c["name"]: c for c in pro["net_settings"]["classes"]}
    assert classes["POWER"]["track_width"] == pytest.approx(18 / config.MIL_PER_MM)
    assert {"netclass": "POWER", "pattern": "+5V"} in pro["net_settings"]["netclass_patterns"]
    assert pro["board"]["design_settings"]["rule_severities"]["lib_footprint_mismatch"] == "ignore"
