"""Step 3.6: own footprints as data in the parts entry (handbook 4.5) – footprint_data, PARTS.footprint (the data complete and
consistent), SYNC.footprint (the copy pcb dump measured equals the data), edakit part footprint (a library footprint becomes an
own one), edakit part build (the copy in EasyEDA from the data: the translation is tested here, the EasyEDA part on a
fake), and the hashes: the circuit hash covers the data byte for byte, the layout hash adds it only where it exists."""

import copy
import json
import math

import pytest

from helpers import check, executed

from edakit import cli, eda, footprint, pcb, scripts
from edakit.design import Design
from edakit.release import gate

MIL = 1000 / 25.4
J1_DATA = {           # the JST PH connector of the example, as it would be drawn as data
    "origin": [0, 0],
    "pads": {"1": {"x": 1.0, "y": 0, "shape": "RECT", "w": 1.2, "h": 1.7, "hole": [0.9, 0.9]},
             "2": {"x": -1.0, "y": 0, "shape": "OVAL", "w": 1.2, "h": 1.7, "hole": [0.9, 0.9]}},
    "lines": [{"points": [[-3, -2.3], [3, -2.3], [3, 2.3], [-3, 2.3], [-3, -2.3]]}],
    "texts": [{"text": "5V", "x": 0, "y": 3.2, "size": 1.0}],
    "outline": [[-3, -2.3], [3, -2.3], [3, 2.3], [-3, 2.3]],
}
LED_DATA = {          # the example's 0805 LED: pin 1 the anode
    "pads": {"1": {"x": -0.95, "y": 0, "shape": "RECT", "w": 1.0, "h": 1.3},
             "2": {"x": 0.95, "y": 0, "shape": "RECT", "w": 1.0, "h": 1.3}},
    "marks": [{"sign": "+", "x": -0.95, "y": 1.2, "size": 0.6}],
}


def own(project, lcsc, data):
    e = project.part(lcsc)
    e["footprint_data"] = copy.deepcopy(data)
    project.save_part(lcsc, e)
    return e


def report(project):
    cfg = project.config()
    return check(Design.from_config(cfg), cfg)


def found(rep, cid):
    return ([m for c, m in rep.errors if c == cid], [m for c, m in rep.notes if c == cid])


def dumped(project, geo):
    """The geometry pcb dump wrote beside the board file."""
    f = project.root / "hardware" / "boards" / "main.geometry.json"
    f.write_text(json.dumps(geo, indent=1))
    return f


def copy_of(data, footprint_name, shapes=True):
    """The copy as pcb dump measures it when it equals the data: mil, relative to the origin."""
    ox, oy = data.get("origin", [0, 0])
    pads = {}
    for n, p in data["pads"].items():
        pads[n] = {"x": round((p["x"] - ox) * MIL, 2), "y": round((p["y"] - oy) * MIL, 2), "net": "",
                   "tht": bool(p.get("hole"))}
        if p.get("hole"):
            pads[n] |= {"hole": p["hole"], "plated": True}
        if shapes:
            pads[n] |= {"shape": p["shape"], "w": round(p["w"] * MIL, 2), "h": round(p["h"] * MIL, 2),
                        "rot": p.get("rot", 0), "layer": "MULTI" if p.get("hole") else "TOP"}
    return {"footprint": footprint_name, "bbox": [-130, -100, 130, 100], "pads": pads}


# --- no data, no change ------------------------------------------------------------------------------------------

def test_a_project_without_footprint_data_runs_the_checks_it_ran(project):
    cfg = project.config()
    assert not {"PARTS.footprint", "SYNC.footprint"} & set(executed(cfg))
    rep = report(project)
    assert not [c for c, _ in rep.errors + rep.notes + rep.warnings + rep.pending if c in ("PARTS.footprint", "SYNC.footprint")]
    assert gate.footprint_data(cfg) == []
    assert gate.layout_hash(cfg) == gate.file_hash(cfg.root, gate.layout_files(cfg))     # the hash it had


def test_with_footprint_data_p9_and_p10_run_after_p8(project):
    own(project, "C131337", J1_DATA)
    run = executed(project.config())
    assert {"PARTS.footprint", "SYNC.footprint"} <= set(run)
    assert found(report(project), "PARTS.footprint") == ([], [])


# --- PARTS.footprint: complete and consistent ------------------------------------------------------------------------------------

def changed(data, change):
    d = copy.deepcopy(data)
    change(d)
    return d


P9_FAULTS = [
    (lambda d: d["pads"].update({"3": {"x": 0, "y": 2, "shape": "ELLIPSE", "w": 1, "h": 1, "hole": [0.6, 0.6]}}),
     "pad 3 without a pin in the entry – a pin of that number, or \"mechanical\": true on a mounting pad"),
    (lambda d: d["pads"].pop("2"), "pin 2 without a pad"),
    (lambda d: d["pads"]["1"].pop("hole") and d["pads"]["1"].update(layer="MULTI"),
     "pad 1: a through-hole pad (MULTI) without hole"),
    (lambda d: d["pads"]["1"].update(layer="TOP"), "pad 1: a hole in a pad on TOP – a through-hole pad is MULTI"),
    (lambda d: d["pads"]["1"].update(shape="SQUARE"), "pad 1: shape 'SQUARE' – one of RECT, ELLIPSE, OVAL"),
    (lambda d: d["pads"]["2"].pop("w"), "pad 2: size w and h (mm) missing"),
    (lambda d: d["pads"]["2"].update(width=1.2), "pad 2: no field width (x, y, shape, w, h, rot, layer, hole, plated, "
                                                 "mechanical)"),
    (lambda d: d["pads"]["2"].update(hole=[0.9, 0.5]), "pad 2: hole is not [width, length] mm with 0 < width <= "
                                                       "length"),
    (lambda d: d["lines"].append({"points": [[0, 0]]}), "lines[1]: points is not a list of at least two [x, y]"),
    (lambda d: d["texts"][0].pop("size"), "texts[0] '5V': x, y and size (mm) missing"),
    (lambda d: d.update(outline=[[0, 0], [1, 1]]), "outline is not a list of at least three [x, y]"),
    (lambda d: d.update(origin=[0]), "origin is not [x, y] in mm"),
    (lambda d: d.update(courtyard=[]), "footprint_data has no field courtyard (origin, pads, pads_same_number, lines, "
                                       "texts, marks, outline, symbol)"),
    (lambda d: d.update(symbol="drawn"), "symbol 'drawn' – \"box\", or none: the carrier's symbol stays"),
]


@pytest.mark.parametrize("change, message", P9_FAULTS)
def test_p9_finds_data_that_is_not_complete(project, change, message):
    own(project, "C131337", changed(J1_DATA, change))
    assert found(report(project), "PARTS.footprint") == ([f"J1 C131337: {message}"], [])


def test_p9_a_mounting_pad_without_a_pin_is_marked_mechanical(project):
    data = changed(J1_DATA, lambda d: d["pads"].update(
        {"MH": {"x": 0, "y": -3, "shape": "ELLIPSE", "w": 2.2, "h": 2.2, "hole": [2.2, 2.2], "plated": False,
                "mechanical": True}}))
    own(project, "C131337", data)
    assert found(report(project), "PARTS.footprint") == ([], [])


def test_p9_holds_the_polarity_mark_to_the_pin_roles(project):
    """GEO.mark's test on the data: a '+' at the anode passes, at the cathode it is the reference project's LED again."""
    own(project, "C2297", LED_DATA)
    assert found(report(project), "PARTS.footprint") == ([], [])
    own(project, "C2297", changed(LED_DATA, lambda d: d["marks"][0].update(x=0.95)))
    assert found(report(project), "PARTS.footprint")[0] == [
        "D2, D3, D4, D5, D6, D7, D8, D9 C2297: marks[0]: '+' at (0.95, 1.2) mm – the nearest polarised pad 2 is "
        "cathode"]
    own(project, "C2297", changed(LED_DATA, lambda d: d["marks"][0].update(sign="-", x=0.95)))
    assert found(report(project), "PARTS.footprint") == ([], [])                     # a "−" at the cathode


def test_p9_without_footprint_name(project):
    e = own(project, "C131337", J1_DATA)
    del e["footprint"]
    project.save_part("C131337", e)
    assert found(report(project), "PARTS.footprint")[0] == [
        "J1 C131337: footprint missing – the name of the copy in EasyEDA, which SYNC.footprint compares with the PCB"]


def test_p9_names_runs_of_pads_from_to():
    assert footprint.numbers_text(["3"]) == "pad 3"
    assert footprint.numbers_text([str(n) for n in range(24, 0, -1)]) == "pads 1–24"
    assert footprint.numbers_text(["1", "2", "3", "5", "7", "8", "A1", "EP"]) == "pads 1–3, 5, 7, 8, A1, EP"
    assert footprint.numbers_text(["2", "1"], "pin") == "pins 1, 2"


def test_p9_shell_legs_as_the_cache_has_them(project):
    legs = [{"x": 1.0, "y": 0, "shape": "RECT", "w": 1.2, "h": 1.7, "hole": [0.9, 0.9]},
            {"x": 1.0, "y": 2.0, "shape": "RECT", "w": 1.2, "h": 1.7, "hole": [0.9, 0.9]}]
    own(project, "C131337", changed(J1_DATA, lambda d: d.update(pads_same_number={"1": legs})))
    assert found(report(project), "PARTS.footprint") == ([], [])
    own(project, "C131337", changed(J1_DATA, lambda d: d.update(pads_same_number={"1": legs[1:] * 2})))
    assert found(report(project), "PARTS.footprint")[0] == ["J1 C131337: pad 1: not one of its pads_same_number"]


# --- SYNC.footprint: the copy equals the data ---------------------------------------------------------------------------------

def test_p10_the_copy_as_dumped_equals_the_data(project):
    own(project, "C131337", J1_DATA)
    dumped(project, {"J1": copy_of(J1_DATA, "CONN-TH_B2B-PH-K-S")})
    assert found(report(project), "SYNC.footprint") == ([], [])


@pytest.mark.parametrize("change, message", [
    (lambda g: g["pads"]["1"].update(x=g["pads"]["1"]["x"] + 0.1 * MIL),
     "pad 1 at (1.100, 0.000) instead of (1.000, 0.000) mm"),
    (lambda g: g["pads"].pop("2"), "pad 2 not in the copy"),
    (lambda g: g["pads"].update({"3": {"x": 0, "y": 80, "net": "", "tht": False}}), "pad 3 in the copy, not in the data"),
    (lambda g: g["pads"]["2"].update(hole=[0.8, 0.8]), "pad 2: hole 0.80 instead of hole 0.90 mm"),
    (lambda g: g["pads"]["2"].update(tht=False) or g["pads"]["2"].pop("hole"),
     "pad 2: no hole in the copy, the data has hole 0.90 mm"),
    (lambda g: g["pads"]["1"].update(shape="ELLIPSE"), "pad 1: ELLIPSE 1.20 x 1.70 instead of RECT 1.20 x 1.70 mm"),
    (lambda g: g["pads"]["1"].update(w=round(1.4 * MIL, 2)), "pad 1: RECT 1.40 x 1.70 instead of RECT 1.20 x 1.70 mm"),
])
def test_p10_finds_a_copy_that_is_not_the_data(project, change, message):
    """The fault built into the dump of the copy: exactly SYNC.footprint, with the pad and the numbers."""
    own(project, "C131337", J1_DATA)
    geo = copy_of(J1_DATA, "CONN-TH_B2B-PH-K-S")
    change(geo)
    dumped(project, {"J1": geo})
    errors, _ = found(report(project), "SYNC.footprint")
    assert errors == [f"J1: the copy differs from the footprint data of C131337 – {message} – rebuild it (edakit part "
                      "build C131337 --write, delete J1 in the PCB, edakit pcb parts --write, edakit pcb dump) or "
                      "correct the data"]


def test_p10_tolerance_and_turns(project):
    """0.02 mm of place – the bell's copy lies 0.05 mil off –; a pad turned by 90° with w and h swapped is the same."""
    data = changed(J1_DATA, lambda d: d["pads"]["1"].update(rot=90, w=1.7, h=1.2))
    own(project, "C131337", data)
    geo = copy_of(J1_DATA, "CONN-TH_B2B-PH-K-S")
    geo["pads"]["1"]["y"] += 0.015 * MIL
    dumped(project, {"J1": geo})
    assert found(report(project), "SYNC.footprint") == ([], [])


def test_p10_origin_shifts_the_data(project):
    """origin: the point [place] positions – the copy is built and measured from there."""
    data = changed(J1_DATA, lambda d: d.update(origin=[1.0, 0]))
    own(project, "C131337", data)
    dumped(project, {"J1": copy_of(data, "CONN-TH_B2B-PH-K-S")})
    assert found(report(project), "SYNC.footprint") == ([], [])
    assert copy_of(data, "X")["pads"]["1"]["x"] == 0                     # pad 1 sits on the origin


def test_p10_another_footprint_and_no_dump(project):
    own(project, "C131337", J1_DATA)
    assert found(report(project), "SYNC.footprint") == ([], [
        "J1: not in the footprint geometry of its board – edakit pcb dump once it is in the PCB; until then the copy "
        "is not compared with the data of C131337"])
    dumped(project, {"J1": copy_of(J1_DATA, "HDR-TH_2P")})
    assert found(report(project), "SYNC.footprint")[0] == [
        "J1: the dump measured footprint HDR-TH_2P, the entry C131337 names CONN-TH_B2B-PH-K-S – not the copy (SYNC.footprint): "
        "edakit pcb parts --write, then pcb dump"]


def test_p10_names_what_an_older_dump_did_not_measure(project):
    own(project, "C131337", J1_DATA)
    geo = copy_of(J1_DATA, "CONN-TH_B2B-PH-K-S", shapes=False)
    for p in geo["pads"].values():
        p.pop("hole")
    dumped(project, {"J1": geo})
    assert found(report(project), "SYNC.footprint") == ([], [
        "J1: holes not measured – the dump is older than the footprint data (edakit pcb dump measures them)",
        "J1: pad shapes and sizes not measured – the dump is older than the footprint data (edakit pcb dump measures "
        "them)"])


def test_p10_waived_on_the_component(project):
    own(project, "C131337", J1_DATA)
    geo = copy_of(J1_DATA, "CONN-TH_B2B-PH-K-S")
    geo["pads"]["1"]["x"] += 0.1 * MIL
    dumped(project, {"J1": geo})
    g = project.graph()
    project.comp(g, "J1")["accept"] = {"SYNC.footprint": "the copy is rebuilt after the order"}
    project.save_graph(g)
    rep = report(project)
    assert found(rep, "SYNC.footprint")[0] == [] and [c for c, _, _ in rep.waived if c == "SYNC.footprint"] == ["SYNC.footprint"]


# --- the data as geometry: pcb plan, GEO.hole, part diff -----------------------------------------------------------------

def test_the_plan_and_p7_take_the_data_of_a_part_not_yet_in_the_pcb(project, capsys):
    data = changed(J1_DATA, lambda d: [p.update(hole=[0.65, 0.65]) for p in d["pads"].values()])   # too small
    own(project, "C131337", data)
    cfg = project.config()
    geo = pcb.plan_geometry(cfg, cfg.board(), Design.from_config(cfg), ["J1"])
    assert geo["J1"]["source"] == "data" and geo["J1"]["pads"]["1"]["x"] == round(MIL, 2)
    assert {p["net"] for p in geo["J1"]["pads"].values()} == {"VIN", "GND"}
    assert found(report(project), "GEO.hole")[0] == [
        "J1 (pads 1, 2, footprint data of C131337): hole 0.65 mm for diagonal 0.71 mm, play -0.06 mm, worst case "
        "-0.14 mm, manufacturer 0.7 mm"]


def test_part_diff_reads_the_data(project):
    from edakit import part
    own(project, "C131337", J1_DATA)
    cfg = project.config()
    geo, where = part.part_geometry(cfg, Design.from_config(cfg), "C131337")
    assert where == "footprint data of C131337" and set(geo["pads"]) == {"1", "2"}


def test_the_box_of_the_data(project):
    e = own(project, "C131337", J1_DATA)
    x0, y0, x1, y1 = footprint.box(e["footprint_data"])
    half = footprint.OUTLINE_MIL / MIL / 2                               # the outline's line, 6 mil
    assert (x0, x1) == (pytest.approx(-3 - half), pytest.approx(3 + half)) and y1 == pytest.approx(3.7)   # the text


# --- a library footprint becomes an own one: edakit part footprint ----------------------------------------------------

def run(project, *args):
    return cli.main(["part", *args, "--config", str(project.root / "edakit.toml")])


def test_part_footprint_takes_the_dump_over_as_data(project, capsys):
    dumped(project, {"J1": copy_of(J1_DATA, "CONN-TH_B2B-PH-K-S")})
    before = project.part("C131337")
    assert run(project, "footprint", "C131337") == 0
    out = capsys.readouterr().out
    assert "the footprint as data, from the pcb dump of J1 on board main – 2 pads" in out
    assert project.part("C131337") == before                               # shown, not written
    assert run(project, "footprint", "C131337", "--write") == 0
    data = project.part("C131337")["footprint_data"]
    assert data == {"origin": [0, 0], "pads": {
        "1": {"x": 1.0, "y": 0.0, "shape": "RECT", "w": 1.2, "h": 1.7, "hole": [0.9, 0.9]},
        "2": {"x": -1.0, "y": 0.0, "shape": "OVAL", "w": 1.2, "h": 1.7, "hole": [0.9, 0.9]}}}
    assert project.part("C131337")["sources"][-1].startswith("footprint_data: the pcb dump of J1 on board main, ")
    rep = report(project)
    assert found(rep, "PARTS.footprint") == ([], []) and found(rep, "SYNC.footprint") == ([], [])   # the copy is the data now
    assert run(project, "footprint", "C131337", "--write") == 1               # it is its own already
    assert "has footprint_data already" in capsys.readouterr().err


def test_part_footprint_from_an_old_dump_asks_for_what_it_lacks(project, capsys):
    """A dump without shapes and holes, no library footprint: the pads' places, the rest for PARTS.footprint to ask for."""
    geo = copy_of(J1_DATA, "CONN-TH_B2B-PH-K-S", shapes=False)
    for p in geo["pads"].values():
        p.pop("hole")
    dumped(project, {"J1": geo})
    assert run(project, "footprint", "C131337", "--write") == 2
    out = capsys.readouterr().out
    assert "PARTS.footprint pads 1, 2: shape missing (RECT, ELLIPSE, OVAL)" in out           # one finding for the pads alike
    assert "PARTS.footprint pads 1, 2: a through-hole pad (MULTI) without hole" in out
    assert project.part("C131337")["footprint_data"]["pads"]["1"] == {"x": 1.0, "y": 0.0, "layer": "MULTI"}


def test_part_footprint_takes_shapes_from_the_library_footprint(project, capsys, monkeypatch):
    """A dump without shapes: shape and size from the library footprint part import cached, pad by pad at its place."""
    from tests.test_part_import import ANSWERS
    from edakit import part
    monkeypatch.setattr(part, "_open", lambda url: (ANSWERS / "C131337.json").read_bytes())
    assert run(project, "import", "C131337") == 0
    lib = json.loads((project.root / "build/edakit/footprints/CONN-TH_B2B-PH-K-S.json").read_text())
    geo = {"footprint": "CONN-TH_B2B-PH-K-S", "bbox": lib["bbox"],
           "pads": {n: {"x": p["x"], "y": p["y"], "net": "", "tht": True, "hole": p["hole"], "plated": True}
                    for n, p in lib["pads"].items()}}
    dumped(project, {"J1": geo})
    assert run(project, "footprint", "C131337", "--write") == 0
    pads = project.part("C131337")["footprint_data"]["pads"]
    assert {(p["shape"], p["w"], p["h"]) for p in pads.values()} == {
        (q["shape"], round(q["w"] / MIL, 3), round(q["h"] / MIL, 3)) for q in lib["pads"].values()}


def test_part_footprint_without_any_geometry(project, capsys):
    assert run(project, "footprint", "C131337") == 1
    assert "C131337: no footprint geometry – edakit pcb dump once a part of it is in the PCB, or edakit part import " \
           "C131337 for the library's" in capsys.readouterr().err


# --- hashes ----------------------------------------------------------------------------------------------------------

def test_the_circuit_hash_covers_the_data_without_code(project):
    before = gate.state_hash(project.config())
    own(project, "C131337", J1_DATA)
    assert gate.state_hash(project.config()) != before


def test_the_layout_hash_adds_the_data_where_it_exists(project):
    cfg = project.config()
    files_only = gate.file_hash(cfg.root, gate.layout_files(cfg))
    e = own(project, "C131337", J1_DATA)
    cfg = project.config()
    with_data = gate.layout_hash(cfg)
    assert with_data != files_only and gate.header(cfg)["layout_sha256"] == with_data
    assert [name for name, _ in gate.footprint_data(cfg)] == ["footprint_data:C131337"]
    e["limits"]["i_max_a"] = 1.5                                       # a rating: the circuit, not the layout
    project.save_part("C131337", e)
    assert gate.layout_hash(project.config()) == with_data
    e["footprint_data"]["pads"]["1"]["x"] = 1.05                        # a pad: the layout
    project.save_part("C131337", e)
    assert gate.layout_hash(project.config()) not in (with_data, files_only)


def test_the_layout_hash_leaves_hash_ignore_out_of_the_data(project):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("[release]\n", '[release]\nhash_ignore = ["notes"]\n'))
    own(project, "C131337", changed(J1_DATA, lambda d: d["pads"]["1"].update(mechanical=False)))
    first = gate.layout_hash(project.config())
    assert first == gate.layout_hash(project.config())
    e = project.part("C131337")
    e["footprint_data"]["texts"][0]["notes"] = "the supply"     # hash_ignore reaches into the data as into the entry
    project.save_part("C131337", e)
    assert gate.layout_hash(project.config()) == first


def test_a_part_of_a_bought_board_adds_nothing(project):
    """A bought board has no layout: its parts' footprint data is in no layout hash."""
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + '\n[boards.usb]\ntitle = "USB breakout"\nbought = true\n')
    g = project.graph()
    project.comp(g, "J1")["board"] = "usb"
    project.save_graph(g)
    own(project, "C131337", J1_DATA)
    assert gate.footprint_data(project.config()) == []


# --- the build: the translation, the symbol box, EasyEDA on a fake --------------------------------------------------

def test_build_ops_translate_the_data_into_api_calls(project):
    e = own(project, "C131337", changed(J1_DATA, lambda d: d.update(origin=[1.0, 0])))
    ops = footprint.build_ops(e)
    assert ops["pads"] == [
        [12, "1", 0.0, 0.0, 0, ["RECT", 47.244, 66.929, 0], "", ["ROUND", 35.433], 0, 0, 0, True],
        [12, "2", -78.74, 0.0, 0, ["OVAL", 47.244, 66.929], "", ["ROUND", 35.433], 0, 0, 0, True]]
    line, text, outline = ops["print"]
    assert line == ("PCB_PrimitivePolyline.create",
                    ["", 3, {"$polygon": [-157.48, -90.551, "L", 78.74, -90.551, 78.74, 90.551, -157.48, 90.551, -157.48,
                                          -90.551]}, 5.906, False])
    assert text == ("PCB_PrimitiveString.create", [3, -39.37, 125.984, "5V", "default", 39.37, 5.906, 5, 0, False, 0,
                                                   False, False])
    assert outline[0] == "PCB_PrimitivePolyline.create" and outline[1][1] == 48 and outline[1][2]["$polygon"][-2:] \
        == [-157.48, -90.551]                                           # closed
    assert ops["symbol"] is None                                         # the carrier's symbol stays


def test_build_ops_without_print_keep_the_copys(project):
    e = own(project, "C131337", {"pads": J1_DATA["pads"]})
    assert footprint.build_ops(e)["print"] is None


def test_build_ops_marks_and_slots(project):
    e = own(project, "C2297", changed(LED_DATA, lambda d: d["marks"].append({"sign": "−", "x": 0.95, "y": 1.2,
                                                                             "size": 0.6})))
    strokes = [args[2]["$polygon"] for _, args in footprint.build_ops(e)["print"]]
    assert strokes == [[-49.213, 47.244, "L", -25.591, 47.244], [-37.402, 35.433, "L", -37.402, 59.055],
                       [25.591, 47.244, "L", 49.213, 47.244]]           # "+" two strokes, "−" one
    slot = {"x": 0, "y": 0, "shape": "OVAL", "w": 1.0, "h": 2.0, "hole": [0.6, 1.4]}
    assert footprint.pad_args("7", slot, 0, 0)[7:11] == [["SLOT", 23.622, 55.118], 0, 0, 90]   # along the long side


def tdisplay():
    """The bell's T-Display as data (variants/esp32/hardware/lib/tdisplay_device.py): 2 x 12 pins, rows 22.86 mm apart."""
    def at(n):
        return (11.43 if n <= 12 else -11.43), -13.97 + ((n - 1) % 12) * 2.54
    pads = {str(n): {"x": at(n)[0], "y": round(at(n)[1], 3), "shape": "RECT" if n in (1, 13) else "ELLIPSE",
                     "w": 1.7, "h": 1.7, "hole": [1.1, 1.1]} for n in range(1, 25)}
    return {"symbol": "box", "pads": pads,
            "lines": [{"points": [[-12.83, -30.2], [12.83, -30.2], [12.83, 21.9], [-12.83, 21.9], [-12.83, -30.2]]}],
            "texts": [{"text": "USB", "x": 0, "y": -25.8, "size": 1.5}],
            "outline": [[-12.83, -30.2], [12.83, -30.2], [12.83, 21.9], [-12.83, 21.9]]}


def tdisplay_entry():
    names = ["5V", "GND", "IO27", "IO26", "IO25", "IO33", "IO32", "IO39", "IO38", "IO37", "IO36", "3V3",
             "3V3", "GND", "GND", "IO12", "IO13", "IO15", "IO2", "IO17", "IO22", "IO21", "GND", "GND"]
    return {"lcsc": "C18722937", "kind": "module", "footprint": "HDR-TH_24P-P2.54-V-F-R2-C12-S2.54-2",
            "pins": {str(n): {"name": name} for n, name in enumerate(names, 1)},
            "symbol": {"left": [str(n) for n in range(24, 12, -1)], "right": [str(n) for n in range(12, 0, -1)]},
            "footprint_data": tdisplay()}


def test_the_symbol_box_of_the_tdisplay():
    e = tdisplay_entry()
    assert footprint.problems(e) == []
    rect, pins = footprint.symbol_box(e)
    assert rect[:4] == [-30, 10, 60, 130] and len(pins) == 24
    by = {p[2]: p for p in pins}
    assert by["24"] == [-40, 0, "24", "GND", 180, 10] and by["13"] == [-40, -110, "13", "3V3", 180, 10]
    assert by["12"] == [40, 0, "12", "3V3", 0, 10] and by["1"] == [40, -110, "1", "5V", 0, 10]
    assert footprint.summary(e) == "24 pads (24 with a hole), 1 line, 1 text, outline, symbol: a box with 24 pins"


def test_p1_does_not_compare_a_symbol_box_with_the_carriers_library_symbol(project):
    """The stand-in's library symbol (header pins 1…) is not the copy's when the copy's symbol is built from the
    entry."""
    cache = project.root / "build" / "edakit" / "library" / "C131337.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"lcsc": "C131337", "pins": {"1": "VIN", "2": "GND"}}))
    assert any(c == "STRUCT.entry" for c, _ in report(project).errors)
    own(project, "C131337", changed(J1_DATA, lambda d: d.update(symbol="box")))
    assert not any(c == "STRUCT.entry" for c, _ in report(project).errors)


class FakeEditors:
    """The project's copies in their editors, as the bridge answers easyeda_api_call: pads and print of the old copy,
    created primitives kept and read back."""

    def __init__(self, old_pads=3, old_print=((3, "PCB_PrimitivePolyline"), (13, "PCB_PrimitiveString"))):
        self.calls, self.active, self.pads, self.pins = [], None, [f"old{i}" for i in range(old_pads)], []
        self.prims = [(layer, cls, f"p{i}") for i, (layer, cls) in enumerate(old_print)]
        self.made = []

    def call(self, tool, timeout=130, **args):
        if tool == "easyeda_project_save":
            self.calls.append(tool)
            return {"ok": True}
        path, a = args["path"], args["args"]
        self.calls.append((path, a))
        if path.endswith(".openInEditor"):
            self.active = a[0]
            return {"ok": True, "result": "tab"}
        if path == "DMT_SelectControl.getCurrentDocumentInfo":
            return {"ok": True, "result": {"uuid": self.active, "tabId": f"tab-{self.active}"}}
        if path == "PCB_PrimitivePad.getAllPrimitiveId":
            return {"ok": True, "result": list(self.pads)}
        if path == "PCB_PrimitivePad.delete":
            self.pads = [p for p in self.pads if p not in a[0]]
            return {"ok": True, "result": True}
        if path.endswith(".getAll") and path.startswith("PCB_Primitive") and path != "PCB_PrimitivePad.getAll":
            cls = path.split(".")[0]
            return {"ok": True, "result": [{"state": {"Layer": layer, "PrimitiveId": pid}}
                                           for layer, c, pid in self.prims if c == cls]}
        if path.endswith(".delete"):
            self.prims = [p for p in self.prims if p[2] not in a[0]]
            return {"ok": True, "result": True}
        if path == "PCB_PrimitivePad.create":
            self.made.append({"state": {"PadNumber": a[1], "X": a[2], "Y": a[3], "Pad": a[5], "Hole": a[7]}})
            return {"ok": True, "result": {"primitiveId": f"pad{a[1]}"}}
        if path.endswith(".create"):
            if path == "SCH_PrimitivePin.create":
                self.pins.append({"state": {"PinNumber": a[2], "PinName": a[3]}})
            return {"ok": True, "result": {"primitiveId": "x"}}
        if path == "PCB_PrimitivePad.getAll":
            return {"ok": True, "result": self.made}
        if path == "SCH_PrimitivePin.getAll":
            return {"ok": True, "result": self.pins}
        if path.endswith(".getAllPrimitiveId"):
            return {"ok": True, "result": []}
        if path.endswith("Document.save") or path == "DMT_EditorControl.closeDocument":
            return {"ok": True, "result": True}
        raise AssertionError(path)


def test_build_copy_rebuilds_the_copy_on_a_fake_easyeda(monkeypatch):
    monkeypatch.setattr(eda.time, "sleep", lambda s: None)
    e = tdisplay_entry()
    fake = FakeEditors()
    back = eda.build_copy(fake, "project-uuid", {"symbol": "sym", "footprint": "fp"}, footprint.build_ops(e))
    paths = [c[0] for c in fake.calls if isinstance(c, tuple)]
    assert paths[:3] == ["LIB_Footprint.openInEditor", "DMT_SelectControl.getCurrentDocumentInfo",
                         "PCB_PrimitivePad.getAllPrimitiveId"]
    assert ("PCB_PrimitivePad.delete", [["old0", "old1", "old2"]]) in fake.calls
    assert ("PCB_PrimitivePolyline.delete", [["p0"]]) in fake.calls      # the old print on the silkscreen
    assert not any(c == ("PCB_PrimitiveString.delete", [["p1"]]) for c in fake.calls)   # the document layer stays
    assert paths.count("PCB_PrimitivePad.create") == 24 and paths.count("SCH_PrimitivePin.create") == 24
    assert paths.index("PCB_Document.save") < paths.index("PCB_PrimitivePad.getAll")
    assert ("LIB_Symbol.openInEditor", ["sym", "project-uuid"]) in fake.calls
    assert footprint.readback_differences(e, back["pads"], back["pins"]) == []
    wrong = [{**p, "X": p["X"] + 2} if p["PadNumber"] == "3" else p for p in back["pads"]]
    assert footprint.readback_differences(e, wrong, back["pins"]) == ["pad 3 at (452.0, -350.0) instead of (450.0, "
                                                                      "-350.0) mil"]


def test_part_build_offline_shows_what_it_would_build(project, capsys):
    own(project, "C131337", J1_DATA)
    assert run(project, "build", "C131337") == 0
    assert capsys.readouterr().out.splitlines()[0] == (
        "C131337 (J1 on board main): footprint CONN-TH_B2B-PH-K-S – 2 pads (2 with a hole), 1 line, 1 text, outline, "
        "the carrier's symbol kept")


def test_part_build_refuses_data_that_is_not_complete(project, capsys):
    own(project, "C131337", changed(J1_DATA, lambda d: d["pads"].pop("2")))
    assert run(project, "build", "C131337") == 1
    assert "C131337: the footprint data is not complete (PARTS.footprint) – pin 2 without a pad" in capsys.readouterr().err
    assert run(project, "build", "C2297") == 1
    assert "C2297: no footprint_data – edakit part footprint C2297 --write" in capsys.readouterr().err


def test_part_build_writes_through_eda_and_records_the_change(project, capsys, monkeypatch):
    """--write: the copies found on the template, rebuilt, read back; with [scripts] project-library:main is recorded
    as changed, as edakit run records an easyeda script – the parts and the routing are from before it."""
    own(project, "C131337", J1_DATA)
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + '\n[scripts.art]\nkind = "input"\ncmd = ["python", "art.py"]\n'
                    'about = "artwork"\nwrites = ["hardware/art.svg"]\n')
    (project.root / "art.py").write_text("")
    board = project.root / "hardware" / "boards" / "main.toml"
    board.write_text(board.read_text() + '\n[[silk.art]]\nsvg = "hardware/art.svg"\nx = 10\ny = 10\nside = "top"\n')
    fake = FakeEditors()
    monkeypatch.setattr(eda, "connect", lambda cfg, *a, **k: fake)
    monkeypatch.setattr(eda, "open_project", lambda mcp, cfg: "project-uuid")
    found_on = []
    monkeypatch.setattr(eda, "find_copies", lambda mcp, template, on, lcsc: found_on.append((template, on, lcsc))
                        or {"symbol": "sym", "footprint": "fp"})
    monkeypatch.setattr(eda.time, "sleep", lambda s: None)
    fake.close = lambda: None
    assert run(project, "build", "C131337", "--write") == 0
    out = capsys.readouterr().out
    assert found_on == [("generated_main", ["J1"], "C131337")]
    assert "built" in out and "delete J1 in the PCB, edakit pcb parts --write, edakit pcb dump" in out
    assert "easyeda_project_save" in fake.calls
    lock = json.loads((project.root / "hardware" / "scripts.lock").read_text())
    change = lock["changed"]["project-library:main"]
    assert change["script"] == "edakit part build C131337" and change["from_before"] == ["footprints:main",
                                                                                         "routing:main"]
    assert "project-library:main changed by edakit part build C131337" in out
    assert [m for level, m in scripts.findings(project.config()) if "project-library:main changed" in m]


def test_part_build_without_scripts_writes_no_lock(project, capsys, monkeypatch):
    own(project, "C131337", J1_DATA)
    fake = FakeEditors()
    fake.close = lambda: None
    monkeypatch.setattr(eda, "connect", lambda cfg, *a, **k: fake)
    monkeypatch.setattr(eda, "open_project", lambda mcp, cfg: "project-uuid")
    monkeypatch.setattr(eda, "find_copies", lambda *a: {"symbol": "sym", "footprint": "fp"})
    monkeypatch.setattr(eda.time, "sleep", lambda s: None)
    assert run(project, "build", "C131337", "--write") == 0
    assert not (project.root / "hardware" / "scripts.lock").exists()


# --- pcb dump: the pads of a part with data with shape and size -------------------------------------------------------

def test_dump_measures_shapes_only_for_parts_with_data(project, monkeypatch):
    own(project, "C131337", J1_DATA)
    cfg = project.config()
    asked = {}

    def measure(mcp, c, shapes=False):
        asked[c["designator"]] = shapes
        return {"footprint": "X", "bbox": [0, 0, 1, 1], "pads": {}}
    monkeypatch.setattr(pcb.eda, "list_pcb_components", lambda mcp: [{"designator": r} for r in ("J1", "U1", "D2")])
    monkeypatch.setattr(pcb, "measure", measure)
    pcb.dump(cfg, cfg.board(), None)
    assert asked == {"J1": True, "U1": False, "D2": False}


def test_measure_reads_shape_size_rotation_and_layer(monkeypatch):
    pins = [{"padNumber": "1", "x": 1039.37, "y": 2000, "net": "VIN", "hole": ["ROUND", 3.5433], "metallization": True,
             "pad": ["RECT", 47.24, 66.93, 0], "rotation": 90, "layer": 12},
            {"padNumber": "2", "x": 960.63, "y": 2000, "net": "GND", "hole": None, "pad": ["OVAL", 47.24, 66.93],
             "rotation": 0, "layer": 1}]
    calls = {"PCB_Primitive.getPrimitivesBBox": {"minX": 900, "minY": 1900, "maxX": 1100, "maxY": 2100},
             "PCB_PrimitiveComponent.getAllPinsByPrimitiveId": pins}
    monkeypatch.setattr(pcb, "api", lambda mcp, name, *a, **k: calls[name])
    c = {"primitiveId": "p", "rotation": 0, "layer": 1, "x": 1000, "y": 2000, "designator": "J1", "footprintName": "F",
         "deviceName": "D"}
    g = pcb.measure(None, c, shapes=True)
    assert g["pads"]["1"] == {"x": 39.37, "y": 0, "net": "VIN", "tht": True, "hole": [0.9, 0.9], "plated": True,
                              "shape": "RECT", "w": 47.24, "h": 66.93, "rot": 90, "layer": "MULTI"}
    assert g["pads"]["2"]["shape"] == "OVAL" and g["pads"]["2"]["layer"] == "TOP"
    assert "shape" not in pcb.measure(None, c)["pads"]["1"]            # a part without data: as before


def test_the_data_round_trips_through_the_geometry(project):
    """from_geometry(geometry(data)) is the data – what part footprint writes is what the build and SYNC.footprint read."""
    e = own(project, "C131337", {"pads": J1_DATA["pads"]})
    geo = footprint.geometry(e)
    back = footprint.from_geometry(geo)
    assert back["pads"] == {n: {k: v for k, v in p.items()} for n, p in J1_DATA["pads"].items()}
    assert all(math.isclose(a, b) for a, b in zip(footprint.box(e["footprint_data"]), [-1.6, -0.85, 1.6, 0.85]))
