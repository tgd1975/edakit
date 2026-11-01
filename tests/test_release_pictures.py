"""Pictures of a gate run (release/pictures.py): the schematic in every run, the board from the run's Gerber files with
stage F – each as SVG and PNG in <run>/pictures/, linked in section 12 of the protocol."""

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from edakit import cli, gerber
from edakit.release import pictures

KICAD_EXPORT = Path(__file__).resolve().parent / "fixtures" / "kicad-export" / "led-bar-main"


def gate_offline(project, monkeypatch):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["gate"]) == 2
    return sorted((project.root / "build" / "release").iterdir())[-1]


def section(text, n):
    return text.split(f"## {n} ")[1].split("\n## ")[0]


def test_every_gate_run_draws_the_schematic(project, monkeypatch, tmp_path):
    run = gate_offline(project, monkeypatch)
    pics = run / "pictures"
    drawn = tmp_path / "drawn.svg"
    assert cli.main(["schematic", "draw", "--out", str(drawn)]) == 0
    assert (pics / "schematic_main.svg").read_text() == drawn.read_text()     # the drawing of edakit schematic draw
    png = Image.open(pics / "schematic_main.png")
    svg = (pics / "schematic_main.svg").read_text()
    w_mm = float(svg.split('width="')[1].split("mm")[0])
    assert png.width == pytest.approx(w_mm / 25.4 * pictures.SCHEMATIC_DPI, abs=2)
    ink = sum(png.convert("L").histogram()[:128])
    assert ink > 0.002 * png.width * png.height                              # lines and text, not a white page
    index = json.loads((pics / "pictures.json").read_text())
    assert [s["name"] for s in index["main"]] == ["schematic_main"]
    twelve = section((run / "protocol.md").read_text(), 12)
    assert "![schematic main](pictures/schematic_main.png)" in twelve
    assert "[SVG](pictures/schematic_main.svg)" in twelve
    assert "with stage F" in twelve and "board_main_top" not in twelve


def kicad_run(tmp_path, order=None):
    """A run folder as stage F leaves it: fab/main/gerber with the recorded KiCad export of led-bar."""
    d = tmp_path / "run" / "fab" / "main"
    shutil.copytree(KICAD_EXPORT, d / "gerber")
    if order:
        (d / "order.json").write_text(json.dumps(order))
    return tmp_path / "run"


@pytest.fixture(scope="module")
def plain(tmp_path_factory):
    """The board pictures of the recorded KiCad export without order settings: (run, shots, notes)."""
    run = kicad_run(tmp_path_factory.mktemp("plain"))
    return run, *pictures.board_pictures(run, "main")


def colour(img, view, x, y):
    return img.convert("RGB").getpixel(view.pixel(x, y))


def near(rgb, hex_):
    want = tuple(int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return all(abs(a - b) <= 12 for a, b in zip(rgb, want))


def spots(g, side="top"):
    """(a pad open in the mask, a spot of bare mask over no copper, print or hole, a spot of copper under the mask) of
    this side, in mm."""
    from shapely.ops import unary_union
    board = gerber.outline_shape(g)
    s = "Top" if side == "top" else "Bottom"
    copper = gerber.shape(gerber.parse_gerber(g / f"Gerber_{s}Layer.G{s[0]}L"))
    mask = gerber.shape(gerber.parse_gerber(g / f"Gerber_{s}SolderMaskLayer.G{s[0]}S"))
    silk = gerber.shape(gerber.parse_gerber(g / f"Gerber_{s}SilkscreenLayer.G{s[0]}O"))
    drilled = pictures.holes(sorted(g.glob("Drill_*"))).buffer(0.1)
    pad = (copper & mask).difference(drilled).buffer(-0.1)
    clear = board.buffer(-1).difference(unary_union([copper, mask, silk, drilled]).buffer(0.3))
    under = copper.difference(mask.buffer(0.2)).difference(silk.buffer(0.2)).buffer(-0.15)
    return [(p.x, p.y) for p in (pad.representative_point(), clear.representative_point(),
                                 under.representative_point())]


def test_the_board_as_made_in_the_colours_of_the_order(tmp_path):
    run = kicad_run(tmp_path, {"mask": "blue", "silkscreen": "white", "finish": "ENIG", "thickness_mm": 1.6})
    shots, notes = pictures.board_pictures(run, "main")
    assert notes == []
    pics = run / "pictures"
    names = [s.name for s in shots]
    assert names[:2] == ["board_main_top", "board_main_bottom"]
    for n in names:
        assert (pics / f"{n}.svg").read_text().startswith("<?xml") and (pics / f"{n}.png").stat().st_size
    view = pictures.board_view(run / "fab" / "main" / "gerber", "top")
    img = Image.open(pics / "board_main_top.png")
    assert img.size == view.size
    pad, clear, under = spots(run / "fab" / "main" / "gerber")
    assert near(colour(img, view, *pad), pictures.FINISH["ENIG"])
    assert near(colour(img, view, *clear), pictures.MASK["blue"])
    assert near(colour(img, view, *under), pictures.under_mask(pictures.MASK["blue"]))
    assert near(img.convert("RGB").getpixel((1, 1)), pictures.BACKGROUND)          # outside the board
    bottom = pictures.board_view(run / "fab" / "main" / "gerber", "bottom")
    img_b = Image.open(pics / "board_main_bottom.png")
    pad_b, _, under_b = spots(run / "fab" / "main" / "gerber", "bottom")
    assert near(colour(img_b, bottom, *pad_b), pictures.FINISH["ENIG"])
    assert near(colour(img_b, bottom, *under_b), pictures.under_mask(pictures.MASK["blue"]))
    assert abs(bottom.pixel(*pad_b)[0] - (img_b.width - view.pixel(*pad_b)[0])) <= 1  # seen from below: mirrored


def test_without_order_settings_edakits_defaults(plain):
    run, _, notes = plain
    assert notes == []
    view = pictures.board_view(run / "fab" / "main" / "gerber", "top")
    img = Image.open(run / "pictures" / "board_main_top.png")
    pad, clear, _ = spots(run / "fab" / "main" / "gerber")
    assert near(colour(img, view, *pad), pictures.SILVER)        # LeadFree HASL
    assert near(colour(img, view, *clear), pictures.MASK["green"])


def test_every_layer_the_maker_builds_from_on_its_own(plain):
    run, shots, _ = plain
    layers = {s.name.removeprefix("board_main_"): s.caption for s in shots[3:]}
    assert list(layers) == ["silk_top", "mask_top", "paste_top", "copper_top", "copper_bottom", "paste_bottom",
                            "mask_bottom", "silk_bottom", "outline", "drill_npth_through", "drill_pth_through",
                            "drill_pth_through_via"]
    assert layers["copper_top"] == "copper, top" and layers["drill_npth_through"] == "drill file NPTH_Through"
    view = pictures.board_view(run / "fab" / "main" / "gerber", "top")
    img = Image.open(run / "pictures" / "board_main_copper_top.png")
    pad, clear, _ = spots(run / "fab" / "main" / "gerber")
    assert near(colour(img, view, *pad), pictures.LAYER["copper"])
    assert near(colour(img, view, *clear), pictures.BACKGROUND)


def test_all_layers_over_each_other_as_the_easyeda_editor_shows_them(plain):
    """Bottom silkscreen, bottom copper, top copper – each showing what lies under it –, through-hole pads, top
    silkscreen and holes on black, seen from above (#99)."""
    from shapely.ops import unary_union
    run, shots, notes = plain
    assert notes == []
    assert [s.name for s in shots[:3]] == ["board_main_top", "board_main_bottom", "board_main_layers"]
    assert shots[2].caption == "main, all layers from above"
    pics = run / "pictures"
    assert (pics / "board_main_layers.svg").read_text().startswith("<?xml")
    g = run / "fab" / "main" / "gerber"
    view = pictures.board_view(g, "top")
    img = Image.open(pics / "board_main_layers.png")
    assert img.size == view.size
    ed = pictures.EDITOR
    top = gerber.shape(gerber.parse_gerber(g / "Gerber_TopLayer.GTL"))
    bottom = gerber.shape(gerber.parse_gerber(g / "Gerber_BottomLayer.GBL"))
    silk = unary_union([gerber.shape(gerber.parse_gerber(g / f)) for f in
                        ("Gerber_TopSilkscreenLayer.GTO", "Gerber_BottomSilkscreenLayer.GBO")])
    drilled = pictures.holes(sorted(g.glob("Drill_*")))
    pads = pictures.through_hole_pads(g)
    others = unary_union([silk, drilled, pads]).buffer(0.2)

    def inside(geom, avoid=others):
        p = geom.difference(avoid).buffer(-0.1).representative_point()
        return p.x, p.y
    base = ed["background"]
    blue = pictures.mix(base, *ed["copper bottom"])
    assert near(colour(img, view, *inside(bottom.difference(top.buffer(0.2)))), blue)
    assert near(colour(img, view, *inside(top.difference(bottom.buffer(0.2)))), pictures.mix(base, *ed["copper top"]))
    assert near(colour(img, view, *inside((top & bottom).buffer(-0.1))), pictures.mix(blue, *ed["copper top"]))
    assert near(colour(img, view, *inside(pads, unary_union([silk, drilled]).buffer(0.05))), ed["pad"])
    assert near(img.convert("RGB").getpixel((1, 1)), base)


def test_through_hole_pads_are_the_plated_holes_open_in_the_mask(plain):
    """Two through-hole pads on led-bar's KiCad export (Drill_PTH_Through); the 28 vias are tented, no pads."""
    from shapely.geometry import Point
    run, _, _ = plain
    g = run / "fab" / "main" / "gerber"
    pads = pictures.polygons(pictures.through_hole_pads(g))
    pth = [Point(x, y) for x, y, *_ in gerber.parse_drills(g / "Drill_PTH_Through.DRL")]
    vias = [Point(x, y) for x, y, *_ in gerber.parse_drills(g / "Drill_PTH_Through_Via.DRL")]
    assert len(pads) == len(pth) == 2
    assert all(any(p.intersects(h) for p in pads) for h in pth)
    assert not any(p.intersects(v) for p in pads for v in vias)


def test_the_protocol_shows_the_board_pictures_after_stage_f(plain):
    _, shots, _ = plain
    lines = "\n".join(pictures.section({"main": {"shots": shots, "notes": []}}, with_board=True))
    assert "![main, top](pictures/board_main_top.png)" in lines
    assert "![main, bottom, seen from below](pictures/board_main_bottom.png)" in lines
    assert "![main, all layers from above](pictures/board_main_layers.png)" in lines
    assert "[copper, top](pictures/board_main_copper_top.png) ([SVG](pictures/board_main_copper_top.svg))" in lines
    assert "with stage F" not in lines


def test_a_picture_that_cannot_be_drawn_is_named_and_the_run_goes_on(tmp_path, monkeypatch):
    run = kicad_run(tmp_path)

    def broken(*a, **k):
        raise ValueError("no outline")
    monkeypatch.setattr(pictures, "as_made", broken)
    monkeypatch.setattr(pictures, "area", broken)
    monkeypatch.setattr(pictures, "holes", broken)
    shots, notes = pictures.board_pictures(run, "main")
    assert notes[:4] == ["board_main_top: not drawn – ValueError: no outline",
                         "board_main_bottom: not drawn – ValueError: no outline",
                         "board_main_layers: not drawn – ValueError: no outline",
                         "board_main_silk_top: not drawn – ValueError: no outline"]
    assert len(notes) == 15 and shots == []
    lines = "\n".join(pictures.section({"main": {"shots": shots, "notes": notes}}, with_board=True))
    assert "- board_main_top: not drawn – ValueError: no outline" in lines
