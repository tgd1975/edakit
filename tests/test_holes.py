"""P-7 (#36): through-hole leads known and fitting the footprint before the layout – L-9's test on the holes of the
footprint geometry (`pcb dump`, else the library footprint of `edakit part import`), in `edakit check` and `pcb plan`.
J1 of the example is the only through-hole part: B2B-PH-K-S, leads □0.5 mm, the maker's hole 0.7 mm."""

import json
from pathlib import Path

import pytest

from edakit import checks, cli, part, pcb
from edakit.design import Design
from edakit.release import gate

MIL = 1000 / 25.4
ANSWERS = Path(__file__).resolve().parent / "fixtures" / "easyeda"


def dump(project, hole=(0.9, 0.9), **pad):
    """main.geometry.json with the parts of the plan; J1's two pads plated with `hole` (None: an older dump)."""
    cfg = project.config()
    geo = {r: {"footprint": "X", "bbox": [-MIL, -MIL, MIL, MIL], "pads": {"1": {"x": 0, "y": 0, "net": "",
                                                                              "tht": False}}}
           for r in cfg.board().place}
    geo["J1"] = {"footprint": "CONN-TH_B2B-PH-K-S", "bbox": [-3 * MIL, -2.3 * MIL, 3 * MIL, 2.3 * MIL],
                 "pads": {n: {"x": x * MIL, "y": 0, "net": "", "tht": True,
                              **({"hole": list(hole), "plated": True} if hole else {}), **pad}
                          for n, x in (("1", 1.0), ("2", -1.0))}}
    (project.root / "hardware" / "boards" / "main.geometry.json").write_text(json.dumps(geo))


def lead(project, **change):
    e = project.part("C131337")
    if change.pop("drop", False):
        del e["lead"]
    else:
        e["lead"]["*"].update(change)
    project.save_part("C131337", e)


def p7(project):
    cfg = project.config()
    rep = checks.run(Design.from_config(cfg), cfg)
    return {kind: [m for c, m, *_ in getattr(rep, kind) if c == "P-7"]
            for kind in ("errors", "pending", "warnings", "notes", "waived")}


def test_holes_that_take_the_lead(project):
    dump(project)
    assert p7(project) == {"errors": [], "pending": [], "warnings": [], "notes": [], "waived": []}
    assert "P-7" in checks.EXECUTED


def test_a_hole_too_small_for_the_lead(project):
    dump(project, (0.70, 0.70))
    assert p7(project)["errors"] == []                     # 0.7 mm is the maker's hole: it fits by that (L-9)
    dump(project, (0.65, 0.65))
    assert p7(project)["errors"] == ["J1 (pads 1, 2, pcb dump): hole 0.65 mm for diagonal 0.71 mm, play -0.06 mm, "
                                     "worst case -0.14 mm, manufacturer 0.7 mm"]
    lead(project, hole_rec_mm=None)                        # the case of the origin's star LED: no maker's value
    dump(project, (0.70, 0.70))
    assert p7(project)["errors"] == ["J1 (pads 1, 2, pcb dump): hole 0.70 mm for diagonal 0.71 mm, play -0.01 mm, "
                                     "worst case -0.09 mm"]


def test_a_through_hole_part_without_lead_is_pending(project, capsys):
    dump(project)
    lead(project, drop=True)
    assert p7(project)["pending"] == ["J1 C131337: plated holes but no lead in the parts entry – the lead's "
                                      "cross-section from the datasheet (handbook 4.1)"]
    assert cli.main(["check", "--release", "--config", str(project.root / "edakit.toml")]) == 1


def test_a_narrow_slot(project):
    dump(project, (0.40, 1.50))
    lead(project, shape="rect", a_mm=0.25, b_mm=1.2, tol_mm=0.2, hole_rec_mm=None)
    found = p7(project)["warnings"]
    assert len(found) == 2 and "tight" in found[0] and "slot narrower than 0.5 mm" in found[1]
    assert p7(project)["errors"] == []


def test_without_hole_sizes_or_geometry_only_a_note(project, capsys):
    assert p7(project)["notes"] == ["not run: no footprint geometry – edakit pcb dump once the parts are in the PCB, "
                                    "or edakit part import <LCSC> for the library's"]
    dump(project, None)
    assert p7(project)["notes"] == ["J1: hole size unknown – edakit pcb dump (the geometry is older than P-7)"]
    assert cli.main(["check", "--config", str(project.root / "edakit.toml")]) == 0


def test_the_library_footprint_is_the_second_source(project, monkeypatch):
    monkeypatch.setattr(part, "_open", lambda url: (ANSWERS / "C131337.json").read_bytes())
    part.import_part(project.config(), "C131337")         # no dump: the library's 0.90 mm holes
    assert p7(project) == {"errors": [], "pending": [], "warnings": [], "notes": [], "waived": []}
    f = project.root / "build" / "edakit" / "footprints" / "CONN-TH_B2B-PH-K-S.json"
    geo = json.loads(f.read_text())
    for p in geo["pads"].values():
        p["hole"] = [0.65, 0.65]
    f.write_text(json.dumps(geo))
    assert p7(project)["errors"][0].startswith("J1 (pads 1, 2, library geometry CONN-TH_B2B-PH-K-S): hole 0.65 mm")
    dump(project)                                          # the dump wins: it has the project's footprint
    assert p7(project)["errors"] == []


def test_waive(project):
    dump(project, (0.65, 0.65))
    g = project.graph()
    project.comp(g, "J1")["waive"] = {"P-7": "reworked by hand"}
    project.save_graph(g)
    assert p7(project)["errors"] == [] and len(p7(project)["waived"]) == 1


def test_the_gate_counts_p7_in_stage_p(project):
    dump(project, (0.65, 0.65))
    cfg = project.config()
    rows, _ = gate.stage_graph(cfg, Design.from_config(cfg))
    assert {r["stage"] for r in rows if r["id"] == "P-7"} == {"P"}


def test_plan_reports_p7(project):
    dump(project, (0.65, 0.65))
    cfg = project.config()
    assert [p for p in pcb.plan(cfg, cfg.board()) if p.startswith("P-7")] == [
        "P-7 J1 (pads 1, 2, pcb dump): hole 0.65 mm for diagonal 0.71 mm, play -0.06 mm, worst case -0.14 mm, "
        "manufacturer 0.7 mm"]


@pytest.mark.parametrize("hole, want", [(["ROUND", 35.433], [0.9, 0.9]), (["SLOT", 15.748, 59.055], [0.4, 1.5]),
                                        (["SLOT", 39.37, 20], [1.0, 1.0]), (None, None)])
def test_dump_keeps_the_hole_size(monkeypatch, hole, want):
    pins = [{"padNumber": "1", "x": 1010, "y": 2000, "net": "VIN", "hole": hole, "metallization": True}]
    calls = {"PCB_Primitive.getPrimitivesBBox": {"minX": 990, "minY": 1980, "maxX": 1030, "maxY": 2020},
             "PCB_PrimitiveComponent.getAllPinsByPrimitiveId": pins}
    monkeypatch.setattr(pcb, "api", lambda mcp, name, *a, **k: calls[name])
    g = pcb.measure(None, {"primitiveId": "p", "rotation": 0, "layer": 1, "x": 1000, "y": 2000, "designator": "J1",
                           "footprintName": "F", "deviceName": "D"})
    pad = g["pads"]["1"]
    assert pad["tht"] == (hole is not None) and pad.get("hole") == want
    assert pad.get("plated", None) == (True if hole else None)
