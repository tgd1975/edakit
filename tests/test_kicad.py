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
from edakit.toolchain import is_kicad
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
        for p in fp["pads"].values():     # pads that keep the routing clearance, as KiCad's DRC asks (16.8)
            if p["tht"]:
                p.update(shape="ELLIPSE", w=70, h=70, rot=0, layer="MULTI", hole=[1.0, 1.0], plated=True)
            elif c["designator"] == "U2":     # SOIC-16, 1.27 mm pitch
                p.update(shape="RECT", w=60, h=24, rot=0, layer="TOP")
            elif c["designator"] == "U1":     # the module's castellated pads, clear of the mounting hole
                p.update(shape="ELLIPSE", w=35, h=35, rot=0, layer="TOP")
            else:
                p.update(shape="RECT", w=40, h=50, rot=0, layer="TOP")
        b = fp["bbox"]
        fp["silk"] = [{"layer": "TOP", "points": [[b[0], b[1]], [b[2], b[1]]], "width": 6, "fill": False}]
        (d / file_name(name)).write_text(json.dumps(fp))
    return project.config()


def cached(cfg, design, ref):
    return json.loads((cfg.artifacts / "footprints" / file_name(design.part(ref)["footprint"])).read_text())


# --- the key ----------------------------------------------------------------------------------------------------------

def test_without_the_key_the_project_stays_easyeda(project):
    cfg = project.config()
    assert cfg.toolchain == "easyeda" and not is_kicad(cfg)


def test_the_key_chooses_kicad_and_its_folder(project):
    cfg = kicad_project(project)
    assert is_kicad(cfg)
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


# --- S-expressions ----------------------------------------------------------------------------------------------------

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


# --- the library ------------------------------------------------------------------------------------------------------

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
    l1 = [r for r in rows if r["id"] in ("SYNC.pcb", "SYNC.footprint")]
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


# --- the schematic ----------------------------------------------------------------------------------------------------

def connectivity(text):
    """The nets of a .kicad_sch as KiCad finds them on one sheet: wires join at their ends, a pin, label or junction
    joins a wire it lies on, labels of one name are one net. -> {net: {ref.pin}} – our own reading, KiCad's is
    kicad-cli's (cli.netlist)."""
    from edakit.toolchain.kicad import sexp as sx
    root = sx.loads(text)
    libs = {s[1]: s for s in sx.find(sx.first(root, "lib_symbols"), "symbol")}
    q = lambda x, y: (round(x, 3), round(y, 3))  # noqa: E731
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def join(a, b):
        parent[find(a)] = find(b)
    wires = [tuple(q(float(xy[1]), float(xy[2])) for xy in sx.find(sx.first(w, "pts"), "xy"))
             for w in sx.find(root, "wire")]

    def on(p, w):
        (x1, y1), (x2, y2) = w
        return (min(x1, x2) - 1e-3 <= p[0] <= max(x1, x2) + 1e-3 and min(y1, y2) - 1e-3 <= p[1] <= max(y1, y2) + 1e-3
                and abs((x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1)) < 1e-3)
    for a, b in wires:
        join(("pt", a), ("pt", b))
    points = []
    for j in sx.find(root, "junction"):
        points.append(("pt", q(*sx.floats(j, "at")[:2])))
    names = {}
    labels = [*sx.find(root, "label"), *sx.find(root, "global_label")]
    for lab in labels:
        p = q(*sx.floats(lab, "at")[:2])
        join(("pt", p), ("net", str(lab[1])))
        points.append(("pt", p))
    pins = {}
    for s in sx.find(root, "symbol"):
        if not sx.first(s, "lib_id"):
            continue
        lib = libs[sx.value(s, "lib_id")]
        X, Y = sx.floats(s, "at")[:2]
        ref = next(c[2] for c in sx.find(s, "property") if c[1] == "Reference")
        for unit in sx.find(lib, "symbol"):
            for pin in sx.find(unit, "pin"):
                lx, ly = sx.floats(pin, "at")[:2]
                p = q(X + lx, Y - ly)
                pins[f"{ref}.{sx.value(pin, 'number')}"] = ("pt", p)
                points.append(("pt", p))
    for p in points:
        for w in wires:
            if on(p[1], w):
                join(p, ("pt", w[0]))
    for key, p in pins.items():
        names.setdefault(find(p), set()).add(key)
    out = {}
    for lab in labels:
        out.setdefault(str(lab[1]), set()).update(names.get(find(("net", str(lab[1]))), set()))
    return out


def test_the_schematic_connects_every_pin_as_the_graph(project):
    from edakit.toolchain.kicad import schematic as ks
    cfg = kicad_project(project)
    board, design = cfg.board(), Design.from_config(cfg)
    path, problems = ks.write(cfg, board)
    assert problems == [] and path.exists()
    nets = connectivity(path.read_text())
    for name, pins in design.board_nets("main").items():
        assert nets.get(name) == set(pins), name
    root = sexp.loads(path.read_text())
    syms = [s for s in sexp.find(root, "symbol") if sexp.first(s, "lib_id")]
    assert len(syms) == len(design.board_comps("main"))
    fps = {r: f for r, f in kb.parts(kb.Pcb.load(kb.write_parts(cfg, board)[0]))}
    for s in syms:                                       # the link to the PCB: the footprint's path is the symbol
        ref = next(c[2] for c in sexp.find(s, "property") if c[1] == "Reference")
        assert sexp.value(fps[ref], "path") == f"/{sexp.value(s, 'uuid')}"
        foot = next(c[2] for c in sexp.find(s, "property") if c[1] == "Footprint")
        assert foot == str(fps[ref][1])
        value = next(c[2] for c in sexp.find(s, "property") if c[1] == "Value")
        assert value == kb.prop(fps[ref], "Value")
    j1 = next(s for s in syms if sexp.value(s, "lib_id") == "edakit:J1")
    assert sexp.value(j1, "in_bom") == "no"              # bom: false in the graph – soldered by hand


def test_a_pcb_kicad_saved_with_nets_by_name_is_read_and_written_by_number(project):
    """KiCad 10 names nets in items when it saves the file (zone fill): (net "GND") – read as edakit's numbers."""
    cfg = kicad_project(project)
    board = cfg.board()
    path, _ = kb.write_parts(cfg, board)
    text = path.read_text()
    text = re.sub(r'\(net (\d+) "([^"]*)"\)', r'(net "\2")', text)               # pads: by name only
    text = re.sub(r'^\t\(net \d+ "[^"]*"\)\n', "", text, flags=re.M)             # no table
    path.write_text(text + "")
    pcb = kb.load(cfg, board)
    assert pcb.nets["GND"] > 0 and kb.pad_net(pcb, next(kb.find(pcb.footprint("C1"), "pad"))) == "3V3"
    data = kb.pcb_json(cfg, board)
    assert {p["Net"] for c in data["components"] for p in c["pads"]} >= {"GND", "3V3", "+5V"}
    pcb.save(cfg, board)
    assert '(net 0 "")' in path.read_text() and re.search(r'\(net \d+ "GND"\)', path.read_text())


def test_the_schematic_puts_pins_and_wire_ends_on_kicads_grid(project):
    from edakit.toolchain.kicad import schematic as ks
    cfg = kicad_project(project)
    path, _ = ks.write(cfg, cfg.board())
    root = sexp.loads(path.read_text())
    ends = [(float(xy[1]), float(xy[2])) for w in sexp.find(root, "wire") for xy in sexp.find(sexp.first(w, "pts"), "xy")]
    off = [(x, y) for x, y in ends if abs(x / 1.27 - round(x / 1.27)) > 1e-6 or abs(y / 1.27 - round(y / 1.27)) > 1e-6]
    assert ends and off == []


def test_the_library_silkscreen_of_easyeda_standard_is_cached_in_mil_y_up():
    """part.footprint_silk on the shapes EasyEDA Standard writes for a footprint's print (10 mil units, y down,
    absolute): a line, a circle, an arc, a filled region and the strokes of a "+" – the designator's text is left out."""
    from edakit.part import footprint_silk
    ds = {"shape": ["TRACK~1~3~~3995 3004 4005 3004~gge5~0",
                    "CIRCLE~3992~2996~0.5~1~3~gge6~0~~",
                    "ARC~1~3~~M 3998,3004 A 2,2 0 0 1 4002,3004~~gge7~0",
                    "SOLIDREGION~3~~M 3990 3000 L 3992 3000 L 3992 3002 Z ~solid~gge8~~~~0",
                    "TEXT~L~4000~3000~0.6~0~0~3~~4.5~+~M 3998 3000 L 4002 3000 M 4000 2998 L 4000 3002~~gge9~~0~pinpart",
                    "TEXT~P~4000~2990~0.6~0~0~3~~4.5~R1~M 3990 2990 L 3992 2990~~gge10~~0~pinpart",
                    "TRACK~1~1~~3995 3004 4005 3004~gge11~0"]}
    silk = footprint_silk(ds, 4000, 3000)
    lines = [s for s in silk if not s["fill"]]
    assert silk[0] == {"layer": "TOP", "points": [[-50, -40], [50, -40]], "width": 10, "fill": False}
    assert len([s for s in silk if s["fill"]]) == 1
    plus = [s for s in lines if s["width"] == 6]
    assert sorted(map(tuple, (tuple(map(tuple, s["points"])) for s in plus))) == [((-20.0, 0.0), (20.0, 0.0)),
                                                                                  ((0.0, 20.0), (0.0, -20.0))]
    assert all(s["layer"] == "TOP" for s in silk) and len(silk) == 6     # copper (layer 1) and the designator out


@pytest.mark.parametrize("form", ['(net "GND")', '(net_name "GND")', '(net 7) (net_name "GND")'])
def test_a_zone_keeps_its_net_however_the_file_names_it(project, form):
    cfg = kicad_project(project)
    board = cfg.board()
    kb.write_parts(cfg, board)
    kb.write_zones(cfg, board)
    path = kb.paths(cfg, board)["pcb"]
    text = re.sub(r'\(net \d+\)\s*\(net_name "GND"\)', form, path.read_text())
    path.write_text(re.sub(r'^\t\(net \d+ "[^"]*"\)\n', "", text, flags=re.M))
    kb.write_parts(cfg, board)                            # read and written again, as after KiCad saved it
    pcb = kb.load(cfg, board)
    assert len(pcb.zones) == 2
    for z in pcb.zones:
        assert sexp.value(z, "net_name") == "GND" and pcb.net_name(sexp.value(z, "net")) == "GND"


def test_a_zone_kicad_saved_without_the_thickness_flag_keeps_its_fill_exact(project):
    """KiCad 10 writes no (filled_areas_thickness no); written back under KiCad 8's version the fill would get a stroke
    of min_thickness – the CI job measured 0.1255 mm instead of the zone clearance 0.25 mm."""
    cfg = kicad_project(project)
    board = cfg.board()
    kb.write_parts(cfg, board)
    kb.write_zones(cfg, board)
    path = kb.paths(cfg, board)["pcb"]
    path.write_text(path.read_text().replace("(filled_areas_thickness no)", ""))
    kb.write_parts(cfg, board)
    assert all(sexp.value(z, "filled_areas_thickness") == "no" for z in kb.load(cfg, board).zones)
    assert path.read_text().count("(filled_areas_thickness no)") == 2
