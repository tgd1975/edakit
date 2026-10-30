"""GEO.formed (#80): formed leads fit only one way round. A through-hole part whose plated holes the board's footprint moves
away from its library footprint, with three or more of them, has a hole pattern that no turn by 90°, 180° or 270°
lays onto itself with a pin in the hole of a pin on another net.

The example gets the origin's RGB star LED as D10 (XINGLIGHT XL-B504RGBC, common anode, four legs in one row at
1.25 mm, library footprint LED-TH_4P-BD5.8-P1.25 as `edakit part import C7371895` cached it) – round 1 of the origin's
decision D-49 with pins 1 and 4 bent 1.6 mm towards the tip, round 2 with pin 4 bent towards the trunk instead."""

import json

import pytest

from helpers import check, executed

from edakit import checks, part
from edakit.design import Design
from edakit.release import gate

MIL = 1000 / 25.4
STAR = "LED-TH_4P-BD5.8-P1.25"
ROW = {"4": -1.875, "3": -0.625, "1": 0.625, "2": 1.875}        # the library's row, x in mm (y 0)
NETS = {"1": "+5V", "2": "STAR_R_K", "3": "STAR_G_K", "4": "STAR_B_K"}


def pads(at, hole=0.9):
    """{number: pad} of a dump or a library footprint: plated holes at {number: (x, y) mm}."""
    return {n: {"x": round(x * MIL, 2), "y": round(y * MIL, 2), "net": "", "tht": True, "hole": [hole, hole],
                "plated": True} for n, (x, y) in at.items()}


def star(project, nets=NETS):
    """D10 in the graph (pins on `nets`), its parts entry and the library footprint part import caches."""
    g = project.graph()
    g["graph"]["components"].append({"designator": "D10", "type": "led", "lcsc": "C7371895", "part": "XL-B504RGBC",
                                     "pins": {"1": "A", "2": "R-", "3": "G-", "4": "B-"}})
    for pin, name in nets.items():
        net = next((n for n in g["graph"]["nets"] if n["name"] == name), None)
        if net is None:
            g["graph"]["nets"].append(net := {"name": name, "pins": [], "v": [0, 5.5]})
        net["pins"].append(f"D10.{pin}")
    project.save_graph(g)
    project.save_part("C7371895", {
        "lcsc": "C7371895", "mpn": "XL-B504RGBC", "kind": "led_rgb", "footprint": STAR,
        "pins": {"1": {"name": "A", "type": "passive", "role": "anode"},
                 "2": {"name": "R-", "type": "passive", "role": "cathode_red"},
                 "3": {"name": "G-", "type": "passive", "role": "cathode_green"},
                 "4": {"name": "B-", "type": "passive", "role": "cathode_blue"}},
        "lead": {"*": {"shape": "square", "a_mm": 0.5, "tol_mm": 0.05}}})
    library(project, STAR, {n: (x, 0) for n, x in ROW.items()}, hole=0.7)


def library(project, name, at, hole=0.7):
    f = part.footprint_file(project.config(), name)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"footprint": name, "bbox": [-120, -115, 100, 115], "pads": pads(at, hole)}))


def dump(project, at, ref="D10", name=STAR):
    """main.geometry.json with the footprint of `ref` as placed: its holes at `at` (mm)."""
    f = project.root / "hardware" / "boards" / "main.geometry.json"
    geo = json.loads(f.read_text()) if f.exists() else {}
    geo[ref] = {"footprint": name, "bbox": [-120, -120, 120, 120], "pads": pads(at)}
    f.write_text(json.dumps(geo))


def bent(**dy):
    """The row with the legs bent: pin = offset in mm along y."""
    return {n: (x, dy.get(f"p{n}", 0)) for n, x in ROW.items()}


ROUND_1 = bent(p1=1.6, p4=1.6)       # pins 1 and 4 towards the tip
ROUND_2 = bent(p1=1.6, p4=-1.6)      # pin 4 towards the trunk


def p8(project):
    cfg = project.config()
    rep = check(Design.from_config(cfg), cfg)
    return {kind: [m for c, m, *_ in getattr(rep, kind) if c == "GEO.formed"]
            for kind in ("errors", "pending", "warnings", "notes", "waived")}


def test_round_1_fits_turned(project):
    star(project)
    dump(project, ROUND_1)
    assert p8(project)["errors"] == [
        "D10: its formed holes lie on each other turned by 180° – pin 1 (+5V) in the hole of pin 3 (STAR_G_K), "
        "pin 2 (STAR_R_K) in the hole of pin 4 (STAR_B_K)"]
    assert "GEO.formed" in executed(project.config())


def test_round_2_fits_one_way_only(project):
    star(project)
    dump(project, ROUND_2)
    assert p8(project) == {"errors": [], "pending": [], "warnings": [], "notes": [], "waived": []}


@pytest.mark.parametrize("p4, found", [(1.6, True), (1.2, True), (1.0, False)])
def test_a_lead_off_by_a_push_still_goes_in(project, p4, found):
    """Turned, pin 4's hole lands |1.6 - p4| / 2 from pin 2's: within 0.25 mm the formed lead goes in with a push."""
    star(project)
    dump(project, bent(p1=1.6, p4=p4))
    assert bool(p8(project)["errors"]) == found


def test_the_library_pattern_is_not_judged(project):
    """One row is symmetric by nature – its orientation is the print's job (GEO.mark, FILES.sheet, M-2), not this check's. A
    footprint drawn around another origin is still the library's pattern."""
    star(project)
    dump(project, {n: (x, 0) for n, x in ROW.items()})
    assert p8(project)["errors"] == []
    dump(project, {n: (x + 0.4, -1.0) for n, x in ROW.items()})
    assert p8(project)["errors"] == []


def test_pins_on_one_net_do_not_count(project):
    """Turned by 180° pin 1 goes into the hole of pin 3 and pin 2 into pin 4's: on one net each, nothing changes."""
    star(project, {"1": "+5V", "3": "+5V", "2": "STAR_K", "4": "STAR_K"})
    dump(project, ROUND_1)
    assert p8(project)["errors"] == []


def test_two_holes_are_not_judged(project):
    """J1 with one leg bent: two holes always lie on each other turned by 180°."""
    library(project, "CONN-TH_B2B-PH-K-S", {"1": (1.0, 0), "2": (-1.0, 0)})
    dump(project, {"1": (1.0, 1.0), "2": (-1.0, 0)}, ref="J1", name="CONN-TH_B2B-PH-K-S")
    assert p8(project) == {"errors": [], "pending": [], "warnings": [], "notes": [], "waived": []}


def test_a_square_names_every_turn(project):
    """Legs bent onto a square: every quarter turn lays it onto itself; the first is named with its pins."""
    star(project)
    dump(project, {"1": (0.625, 0.625), "2": (0.625, -0.625), "3": (-0.625, -0.625), "4": (-0.625, 0.625)})
    assert p8(project)["errors"] == [
        "D10: its formed holes lie on each other turned by 90° (also 180°, 270°) – pin 1 (+5V) in the hole of pin 4 "
        "(STAR_B_K), pin 2 (STAR_R_K) in the hole of pin 1 (+5V), pin 3 (STAR_G_K) in the hole of pin 2 (STAR_R_K), "
        "pin 4 (STAR_B_K) in the hole of pin 3 (STAR_G_K)"]


def test_waive(project):
    star(project)
    dump(project, ROUND_1)
    g = project.graph()
    project.comp(g, "D10")["accept"] = {"GEO.formed": "the print shows the anode, the body's flat stands on the board"}
    project.save_graph(g)
    found = p8(project)
    assert found["errors"] == [] and len(found["waived"]) == 1


def test_without_the_library_footprint_a_note(project):
    star(project)
    dump(project, ROUND_1)
    part.footprint_file(project.config(), STAR).unlink()
    assert p8(project) == {"errors": [], "pending": [], "warnings": [], "waived": [], "notes": [
        "D10: formed leads not judged – no library footprint LED-TH_4P-BD5.8-P1.25 to compare the holes with (edakit "
        "part import <LCSC>)"]}
    library(project, STAR, {n: (x, 0) for n, x in ROW.items() if n != "4"})     # another footprint of that name
    assert p8(project)["notes"] == ["D10: formed leads not judged – the library footprint LED-TH_4P-BD5.8-P1.25 has "
                                    "no pad 4"]


def test_without_a_dump_nothing_is_formed(project):
    star(project)                      # the library footprint alone: the part sits on its library pattern
    assert p8(project) == {"errors": [], "pending": [], "warnings": [], "notes": [], "waived": []}


def test_the_gate_counts_p8_in_stage_p(project):
    star(project)
    dump(project, ROUND_1)
    cfg = project.config()
    rows, _ = gate.stage_graph(cfg, Design.from_config(cfg))
    assert [(r["stage"], r["result"]) for r in rows if r["id"] == "GEO.formed"] == [("P", "fail")]
