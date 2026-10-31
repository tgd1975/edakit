"""edakit part import (#32): the symbol pins and the footprint of an LCSC number from the library data, without
EasyEDA – the parts entry, the geometry cache, STRUCT.entry against the symbol, `pcb plan` on library geometry.

fixtures/easyeda/ holds EasyEDA's public component data as https://easyeda.com/api/products/<LCSC>/components
?version=6.4.19.5 answered on 2026-10-27, trimmed to the fields edakit reads; not-found.json is the answer to a number
that does not exist (C299999). No test goes to the network."""

import json
import urllib.error
from pathlib import Path

import pytest

from helpers import check as engines_check

from edakit import catalog, cli, part, pcb
from edakit.design import Design

ANSWERS = Path(__file__).resolve().parent / "fixtures" / "easyeda"
MIL = 1000 / 25.4


@pytest.fixture
def library(monkeypatch):
    """The library answers from the recordings; the numbers asked for, in order."""
    asked = []

    def answer(url):
        lcsc = url.split("/products/")[1].split("/")[0]
        asked.append(lcsc)
        f = ANSWERS / f"{lcsc}.json"
        return (f if f.exists() else ANSWERS / "not-found.json").read_bytes()
    monkeypatch.setattr(part, "_open", answer)
    return asked


def run(project, *args):
    return cli.main(["part", *args, "--config", str(project.root / "edakit.toml")])


def entry_file(project, lcsc):
    return project.root / "hardware" / "parts" / f"{lcsc}.json"


def cache(project, footprint):
    return json.loads((project.root / "build" / "edakit" / "footprints" / f"{footprint}.json").read_text())


def check(project):
    cfg = project.config()
    return engines_check(Design.from_config(cfg), cfg)


def test_import_writes_a_new_entry(project, library, capsys):
    entry_file(project, "C2297").unlink()
    assert "STRUCT.entry" in {c for c, _ in check(project).errors}           # today: no entry for D2-D9
    assert run(project, "import", "C2297") == 0
    e = json.loads(entry_file(project, "C2297").read_text())
    assert (e["lcsc"], e["mpn"], e["manufacturer"], e["footprint"], e["jlc_class"]) == \
        ("C2297", "KT-0805G", "KENTO", "LED0805-R-RD", "Basic Part")
    assert e["pins"] == {"1": {"name": "A"}, "2": {"name": "K"}}     # type and role for whoever signs it off
    assert e["verified"] is None and e["kind"] is None
    assert any("easyeda.com/api/products/C2297" in s for s in e["sources"])
    pads = cache(project, "LED0805-R-RD")["pads"]
    assert sorted(pads) == ["1", "2"] and not any(p["tht"] for p in pads.values())
    assert [round(pads[n]["x"] / MIL, 2) for n in ("1", "2")] == [1.05, -1.05]
    assert all((round(p["w"] / MIL, 2), round(p["h"] / MIL, 2)) == (1.0, 1.4) for p in pads.values())
    rep = check(project)
    assert not [m for c, m in rep.errors if c == "STRUCT.entry"]
    assert [m for c, m in rep.pending if c == "PARTS.verified" and m.startswith("C2297")]
    assert "new entry" in capsys.readouterr().out


def test_import_reads_plated_holes(project, library):
    assert run(project, "import", "C131337") == 0                   # the signed entry agrees with the library
    pads = cache(project, "CONN-TH_B2B-PH-K-S")["pads"]
    assert all(p["tht"] and p["plated"] and p["hole"] == [0.9, 0.9] for p in pads.values())
    assert sorted(round(p["x"] / MIL, 2) for p in pads.values()) == [-1.0, 1.0]


def test_an_existing_entry_is_never_overwritten(project, library, capsys):
    before = entry_file(project, "C2297").read_bytes()
    assert run(project, "import", "C2297") == 0
    assert entry_file(project, "C2297").read_bytes() == before
    e = project.part("C2297")
    e["pins"]["1"]["name"] = "K"
    project.save_part("C2297", e)
    before = entry_file(project, "C2297").read_bytes()
    capsys.readouterr()
    assert run(project, "import", "C2297") == 2
    assert "pin 1: library 'A', entry 'K'" in capsys.readouterr().out
    assert entry_file(project, "C2297").read_bytes() == before
    assert run(project, "import", "C2297", "--update") == 2          # --update fills in, it never corrects
    assert entry_file(project, "C2297").read_bytes() == before


def test_update_fills_in_only_missing_fields(project, library, capsys):
    e = project.part("C2297")
    del e["footprint"], e["jlc_class"]
    e["manufacturer"] = "Kento"                                     # differs only in case: not a difference
    project.save_part("C2297", e)
    assert run(project, "import", "C2297") == 2
    assert "footprint: missing in the entry" in capsys.readouterr().out
    assert run(project, "import", "C2297", "--update") == 0
    after = project.part("C2297")
    assert (after["footprint"], after["jlc_class"], after["manufacturer"]) == ("LED0805-R-RD", "Basic Part", "Kento")
    assert after["verified"] == e["verified"] and after["pins"] == e["pins"]


def test_refusals(project, library, capsys):
    assert run(project, "import", "C9900005314") == 1
    assert run(project, "import", "2297") == 1
    assert library == []                                            # refused before asking
    assert run(project, "import", "C299999") == 1
    assert "C299999: not in the library" in capsys.readouterr().err
    assert not entry_file(project, "C299999").exists()


def test_a_refusing_or_silent_library(project, monkeypatch, capsys):
    def refuse(url):
        raise urllib.error.HTTPError(url, 403, "Forbidden", None, None)
    monkeypatch.setattr(part, "_open", refuse)
    assert run(project, "import", "C2297") == 1
    assert "C2297: the library refused (HTTP 403)" in capsys.readouterr().err
    data = json.loads((ANSWERS / "C2297.json").read_text())
    data["result"]["dataStr"]["head"]["c_para"]["Manufacturer"] = "null"     # how the library says "nothing"
    assert part.parse_component("C2297", data["result"], "recorded")["manufacturer"] is None


def test_p1_compares_the_graph_with_the_symbol(project, library):
    e = project.part("C2297")                                       # graph and entry agree on a wrong pinout
    e["pins"]["1"]["name"], e["pins"]["2"]["name"] = "K", "A"
    project.save_part("C2297", e)
    g = project.graph()
    for i in range(2, 10):
        project.comp(g, f"D{i}")["pins"] = {"1": "K", "2": "A"}
    project.save_graph(g)
    assert not [m for c, m in check(project).errors if c == "STRUCT.entry"]  # without the cache: as today
    assert run(project, "import", "C2297") == 2                     # the entry differs: reported, kept
    found = [m for c, m in check(project).errors if c == "STRUCT.entry"]
    assert len(found) == 8 and found[0].startswith("D2: pins differ from the library symbol of C2297")
    assert "pin 1: symbol 'A', graph 'K'" in found[0]
    g = project.graph()
    project.comp(g, "D2")["accept"] = {"STRUCT.entry": "pin names of our own"}
    project.save_graph(g)
    assert [c for c, _, _ in check(project).waived if c == "STRUCT.entry"]


def test_p1_names_the_case_of_a_pin_mismatch(project, library):
    """STRUCT.entry for pins that differ from the entry (walkthrough-gaps A2): with the library symbol cached the
    finding says whether the symbol agrees with the entry – the graph has another part's pins (17.6: the green LED's
    pins on the red LED's entry) – or with the graph – the entry to be checked; the code's fix has the advice of each
    case under the words its findings start with."""
    def pin_findings():
        return [m for c, m in check(project).errors if c == "STRUCT.entry" and "pins differ from parts entry" in m]
    g = project.graph()
    project.comp(g, "D2")["pins"] = {"1": "K", "2": "A"}            # another part's pinout on C2297's entry
    project.save_graph(g)
    assert pin_findings() == ["D2: pins differ from parts entry C2297: graph {'1': 'K', '2': 'A'} vs parts "
                              "{'1': 'A', '2': 'K'}"]                 # without the cache: which is right is open
    assert run(project, "import", "C2297") == 0                      # the symbol: pin 1 A, pin 2 K, as the entry
    assert pin_findings() == ["D2: pins differ from parts entry C2297: graph {'1': 'K', '2': 'A'} vs parts "
                              "{'1': 'A', '2': 'K'} – the library symbol agrees with the entry: the graph has the pins "
                              "of another part"]
    project.comp(g, "D2")["pins"] = {"1": "A", "2": "K"}
    project.save_graph(g)
    e = project.part("C2297")                                        # now the entry is the odd one out
    e["pins"]["1"]["name"], e["pins"]["2"]["name"] = "K", "A"
    project.save_part("C2297", e)
    found = pin_findings()
    assert len(found) == 8 and found[0].endswith("– the library symbol agrees with the graph: the entry's pins to be "
                                                 "checked against the datasheet")
    fix = catalog.code("STRUCT.entry")["fix"]
    for case in ("No parts entry:", "Pins differ from the parts entry:", "Pins differ from the library symbol",
                 "A supply pin marked nc:", "A config the entry does not know:", "A state:", "An LED strip:"):
        assert case in fix
    pins = fix.split("Pins differ from the parts entry:")[1].split("Pins differ from the library symbol")[0]
    assert "pin names and the nets on its pins" in pins and "corrected from the datasheet" in pins
    assert "part-search" not in pins and "symbol_differs" not in pins     # the advice of the other cases


def placed_geometry(project, without=()):
    """main.geometry.json for every placed part of the example but `without`: 2 x 2 mm, one pad."""
    cfg = project.config()
    side = 1 * MIL
    geo = {r: {"footprint": "X", "bbox": [-side, -side, side, side], "pads": {"1": {"x": 0, "y": 0, "net": "",
                                                                                   "tht": False}}}
           for r in cfg.board().place if r not in without}
    (project.root / "hardware" / "boards" / "main.geometry.json").write_text(json.dumps(geo))
    return cfg


def test_plan_takes_the_library_geometry_of_a_part_not_yet_in_the_pcb(project, library):
    cfg = placed_geometry(project, without=["J1"])
    assert "J1: in the plan but not in the footprint geometry" in " ".join(pcb.plan(cfg, cfg.board()))
    run(project, "import", "C131337")
    assert "J1: in the plan but not" not in " ".join(pcb.plan(cfg, cfg.board()))
    geo = pcb.plan_geometry(cfg, cfg.board(), Design.from_config(cfg))
    assert geo["J1"]["source"] == "library" and geo["J1"]["bbox"] == cache(project, "CONN-TH_B2B-PH-K-S")["bbox"]
    assert {p["net"] for p in geo["J1"]["pads"].values()} == {"VIN", "GND"}   # the nets from the graph


def test_plan_without_a_dump_runs_on_the_library_geometry(project, library):
    cfg = project.config()
    with pytest.raises(SystemExit, match="hardware/boards/main.geometry.json is missing"):
        pcb.plan(cfg, cfg.board())                                  # as today
    run(project, "import", "C131337")
    problems = pcb.plan(cfg, cfg.board())
    assert "U1: in the plan but not in the footprint geometry" in " ".join(problems)
    assert "J1: in the plan but not" not in " ".join(problems)


def test_library_geometry_is_the_easyeda_pro_geometry(project, library):
    """C295747 against an EasyEDA Pro dump of the same footprint (pytree's J1, mil, y up, origin of the part)."""
    run(project, "import", "C295747")
    geo = cache(project, "CONN-SMD_P2.00_S2B-PH-SM4-TB-LF-SN")
    dump = {"1": (-39.33, 115.12), "2": (39.37, 115.12), "3": (131.87, -115.18), "4": (-131.93, -115.18)}
    assert max(abs(geo["pads"][n][k] - v) for n, xy in dump.items() for k, v in zip("xy", xy)) < 0.05
    assert max(abs(a - b) for a, b in zip(geo["bbox"], [-161.42, -182.09, 161.42, 189.96])) < 1   # BBox: 1 mil steps


def test_parser():
    args = cli.build_parser().parse_args(["part", "import", "C2297", "--update"])
    assert (args.action, args.source, args.update) == ("import", "C2297", True)
