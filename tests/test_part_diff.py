"""edakit part diff (#33): how a new footprint maps onto the old one before a swap – turn, shift, mirror, the pad map
by position and by role, pitch, holes, box, and the graph change it implies. The SW5 pair is the library data of
C17179532 and C49284748 (fixtures/easyeda/, see test_part_import.py)."""

import json
from pathlib import Path

import pytest

from edakit import cli, part

ANSWERS = Path(__file__).resolve().parent / "fixtures" / "easyeda"
MIL = 1000 / 25.4

SWITCH_LEAD = {"1": {"shape": "rect", "a_mm": 0.8, "b_mm": 1.3, "tol_mm": 0.2},     # XUNPU SS-12D11G9, as in the
               "2": {"shape": "rect", "a_mm": 0.8, "b_mm": 1.3, "tol_mm": 0.2},     # origin's entry
               "3": {"shape": "rect", "a_mm": 0.8, "b_mm": 1.3, "tol_mm": 0.2},
               "4": {"shape": "rect", "a_mm": 0.25, "b_mm": 1.2, "tol_mm": 0.2},
               "5": {"shape": "rect", "a_mm": 0.25, "b_mm": 1.2, "tol_mm": 0.2}}


@pytest.fixture
def library(monkeypatch):
    monkeypatch.setattr(part, "_open", lambda url: (ANSWERS / f"{url.split('/products/')[1].split('/')[0]}.json")
                        .read_bytes())


def run(project, *args):
    return cli.main(["part", *args, "--config", str(project.root / "edakit.toml")])


def diff(project, old, new, capsys, *more):
    capsys.readouterr()
    code = run(project, "diff", old, new, *more)
    return code, capsys.readouterr().out


def switch_pair(project):
    """Both switches imported, with the roles of a slide switch, the new one with its leads; SW5 on the old one."""
    for lcsc in ("C17179532", "C49284748"):
        assert run(project, "import", lcsc) == 0
        e = project.part(lcsc)
        e["kind"] = "switch"
        for n, role in (("1", "throw_a"), ("2", "common"), ("3", "throw_b")):
            e["pins"][n]["role"] = role
        project.save_part(lcsc, e)
    e = project.part("C49284748")
    e["lead"] = SWITCH_LEAD
    project.save_part("C49284748", e)
    g = project.graph()
    g["graph"]["components"].append({"designator": "SW5", "type": "switch", "lcsc": "C17179532",
                                     "pins": {n: n for n in "12345"}, "nc": ["4", "5"]})
    g["graph"]["nets"] += [{"name": "BAT_SW", "pins": ["SW5.1"], "v": [0, 5]},
                           {"name": "BAT", "pins": ["SW5.2"], "v": [0, 5]}]
    project.save_graph(g)


def test_the_sw5_swap(project, library, capsys):
    switch_pair(project)
    code, out = diff(project, "C17179532", "C49284748", capsys)
    assert code == 2
    assert "turned 180°" in out and "the mirror image fits equally (symmetric: the numbers decide)" in out
    assert "map by position: 1→3, 2→2, 3→1, 4→4, 5→5" in out
    assert "old 1 throw_a → new 3 throw_b" in out and "old 3 throw_b → new 1 throw_a" in out
    assert "pitch 4.70 → 4.80 mm" in out
    assert "hole 1→3: Ø1.50 → slot 1.10 x 1.60 mm" in out and "residual per pad (mm): 1 0.41" in out
    assert "hole 4: Ø1.50 → slot 0.40 x 1.50 mm" in out and "slot narrower than 0.5 mm" in out
    assert "SW5: BAT_SW 1 → 3" in out and "BAT 2 → 2" not in out
    assert diff(project, "C17179532", "C49284748", capsys, "--json", str(project.root / "d.json"))[0] == 2
    data = json.loads((project.root / "d.json").read_text())
    assert data["turn"] == 180 and not data["mirror"] and data["map"] == {"1": "3", "2": "2", "3": "1", "4": "4",
                                                                           "5": "5"}
    assert data["symmetric"] and not data["drop_in"]


def write_footprint(project, name, pads, lcsc, size=1.0):
    """A footprint in the cache format (pads in mm, square, `size` mm or unknown) and the symbol cache that names it."""
    root = project.root / "build" / "edakit"
    (root / "footprints").mkdir(parents=True, exist_ok=True)
    (root / "library").mkdir(parents=True, exist_ok=True)
    geo = {"footprint": name, "bbox": [-3 * MIL, -3 * MIL, 3 * MIL, 3 * MIL],
           "pads": {n: {"x": x * MIL, "y": y * MIL, "net": "", "tht": False, "shape": "RECT", "w": size * MIL,
                        "h": size * MIL, "rot": 0} if size else {"x": x * MIL, "y": y * MIL, "net": "", "tht": False}
                    for n, (x, y) in pads.items()}}
    (root / "footprints" / f"{name}.json").write_text(json.dumps(geo))
    (root / "library" / f"{lcsc}.json").write_text(json.dumps({"lcsc": lcsc, "footprint": name,
                                                                "pins": {n: n for n in pads}}))


ANGLE = {"1": (-1.0, -1.0), "2": (1.0, -1.0), "3": (1.0, 2.0)}           # an L with legs of 2 and 3 mm: no turn
                                                                          # makes it its mirror image


def test_a_mirror_image_only(project, capsys):
    write_footprint(project, "ANGLE", ANGLE, "C1")
    write_footprint(project, "ANGLE-M", {n: (-x, y) for n, (x, y) in ANGLE.items()}, "C2")
    code, out = diff(project, "C1", "C2", capsys)
    assert code == 2 and "mirror image only – not on the same side" in out
    write_footprint(project, "ANGLE-M", {n: (-x, y) for n, (x, y) in ANGLE.items()}, "C2", size=None)
    code, out = diff(project, "C1", "C2", capsys)          # without pad sizes: within half the pad distance
    assert code == 2 and "turned 90°" in out and "row 1-2: pitch 2.00 → 3.00 mm" in out


def test_a_sot23_and_its_mirror_image_differ_only_in_the_numbers(project, capsys):
    """Pads 1 and 2 swapped: the pad positions are the same, so 0° fits – the numbers swap."""
    sot = {"1": (-0.95, -1.0), "2": (0.95, -1.0), "3": (0.0, 1.0)}
    write_footprint(project, "SOT", sot, "C1")
    write_footprint(project, "SOT-M", {"1": sot["2"], "2": sot["1"], "3": sot["3"]}, "C2")
    code, out = diff(project, "C1", "C2", capsys)
    assert code == 2 and "turned 0°" in out and "map by position: 1→2, 2→1, 3→3" in out


def test_drop_in(project, library, capsys):
    pads = {"1": (-1.05, 0.0), "2": (1.05, 0.0)}
    write_footprint(project, "CHIP", pads, "C1")
    write_footprint(project, "CHIP-1", {n: (x + 1, y) for n, (x, y) in pads.items()}, "C2")
    code, out = diff(project, "C1", "C2", capsys)
    assert code == 0 and "drop-in" in out and "shift (-1.00, +0.00) mm" in out
    run(project, "import", "C2297")
    code, out = diff(project, "C2297", "C2297", capsys)
    assert code == 0 and "drop-in" in out


def test_a_part_without_geometry_is_named_with_the_command(project, capsys):
    code = run(project, "diff", "C2297", "C131337")
    assert code == 1 and "C2297: no footprint geometry – edakit part import C2297" in capsys.readouterr().err


def test_parser():
    args = cli.build_parser().parse_args(["part", "diff", "C1", "C2", "--json", "d.json"])
    assert (args.action, args.source, args.new, args.json) == ("diff", "C1", "C2", "d.json")
