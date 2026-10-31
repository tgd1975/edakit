"""STRUCT.entry against the cached library symbol beyond its names (the owner's choice of 2026-10-31: check and
report): a number the symbol gives to two pins, a pad of its footprint it has no pin for – grade symbol, an error –,
and the pins a parts entry says it follows the datasheet on (symbol_differs) – left out, named in a note (grade
declared).

fixtures/easyeda/ holds EasyEDA's public component data as https://easyeda.com/api/products/<LCSC>/components
?version=6.4.19.5 answered on 2026-10-31, trimmed to the fields edakit reads (the symbol's P~ pins, the footprint's
PAD~ pads, the identification): C2874885 WS2812B-V5/W, C5446 XC6206P332MR-G, C81582 DRV8825PWPR, C41407547 Raspberry
Pi Pico 2, C22451885 6N138S-TA1-L; C2297 from 2026-10-27. EasyEDA refused C719745 (AQY212GS) that day; its cache as
the guitar block agent's `edakit part import` wrote it on 2026-10-31 is in fixtures/library_cache/. No test goes to
the network."""

import json
import shutil
from pathlib import Path

import pytest

from edakit import cli, library, part
from edakit.design import Design
from edakit.engines import struct

FIX = Path(__file__).resolve().parent / "fixtures"
ANSWERS = FIX / "easyeda"


@pytest.fixture
def recorded(monkeypatch):
    def answer(url):
        lcsc = url.split("/products/")[1].split("/")[0]
        f = ANSWERS / f"{lcsc}.json"
        return (f if f.exists() else ANSWERS / "not-found.json").read_bytes()
    monkeypatch.setattr(part, "_open", answer)


def imported(project, key, entry):
    """The entry in the project, the library's symbol cached by edakit part import, a component X9 using it; -> the
    STRUCT.entry findings on X9 as (grade, text)."""
    project.save_part(key, entry)
    cli.main(["part", "import", key, "--config", str(project.root / "edakit.toml")])
    return on_x9(project, key, entry)


def on_x9(project, key, entry):
    g = project.graph()
    g["graph"]["components"].append({"designator": "X9", "type": "ic", "lcsc": key, "board": "main",
                                     "pins": {n: p["name"] for n, p in entry["pins"].items()}})
    project.save_graph(g)
    cfg = project.config()
    return [(f.grade, f.text) for f in struct.entries(Design.from_config(cfg), cfg) if f.place == "X9"]


def without_declaration(key):
    e = library.entry(key)
    e.pop("symbol_differs", None)
    return e


def test_the_parse_keeps_a_number_the_symbol_gives_twice():
    ws = json.loads((ANSWERS / "C2874885.json").read_text(encoding="utf-8"))["result"]
    assert part.parse_component("C2874885", ws, "recorded")["duplicate_pins"] == {"3": ["VSS", "DIN"]}
    pico = json.loads((ANSWERS / "C41407547.json").read_text(encoding="utf-8"))["result"]
    assert sorted(part.parse_component("C41407547", pico, "recorded")["duplicate_pins"]) == ["2", "3", "4", "5", "6"]
    led = json.loads((ANSWERS / "C2297.json").read_text(encoding="utf-8"))["result"]
    assert "duplicate_pins" not in part.parse_component("C2297", led, "recorded")


def test_a_symbol_that_numbers_din_like_vss_is_an_error(project, recorded):
    found = imported(project, "C2874885", without_declaration("C2874885"))
    symbol = [t for g, t in found if g == "symbol"]
    assert len(symbol) == 1 and "numbers 2 pins 3 (VSS, DIN)" in symbol[0] and "joins them on pad 3" in symbol[0]
    assert any(g == "" and "graph only ['4']" in t for g, t in found)          # pin 4 DIN: no pin in the symbol
    cache = json.loads((project.root / "build" / "edakit" / "library" / "C2874885.json").read_text(encoding="utf-8"))
    assert cache["duplicate_pins"] == {"3": ["VSS", "DIN"]}


def test_the_entry_that_follows_the_datasheet_says_so_in_a_note(project, recorded):
    found = imported(project, "C2874885", library.entry("C2874885"))
    assert [g for g, _ in found] == ["declared"]
    assert "pin 4: DIN is pin 4" in found[0][1] and "wires these pins otherwise" in found[0][1]


def test_a_pad_without_a_pin_is_an_error(project, recorded):
    e = without_declaration("C81582")                       # the entry has pin 29, the PowerPAD; the symbol does not
    found = imported(project, "C81582", e)
    assert any(g == "symbol" and "has no pin for pad 29 of its footprint" in t and "(PPAD) unconnected" in t
               for g, t in found)
    again = imported_again(project, "C81582")
    assert [g for g, _ in again] == ["declared"], again


def imported_again(project, key):
    """The library's entry (with symbol_differs) over the one the test put in, the cache as it is."""
    entry = library.entry(key)
    project.save_part(key, entry)
    g = project.graph()
    g["graph"]["components"] = [c for c in g["graph"]["components"] if c["designator"] != "X9"]
    project.save_graph(g)
    return on_x9(project, key, entry)


def test_pico_2_test_pads_numbered_like_pins_and_swapped_debug_pins(project, recorded):
    found = imported(project, "C41407547", without_declaration("C41407547"))
    symbol = next(t for g, t in found if g == "symbol")
    assert all(f"numbers 2 pins {n}" in symbol for n in "23456")
    assert all(f"has no pin for pad TP{n}" in symbol for n in "23456")
    names = next(t for g, t in found if g == "")
    assert "pin 41: symbol 'SWDIO', graph 'SWCLK'" in names and "pin 43: symbol 'SWCLK', graph 'SWDIO'" in names
    again = imported_again(project, "C41407547")
    assert [g for g, _ in again if g != ""] == ["declared"]      # no grade symbol left, the declaration named
    names = next(t for g, t in again if g == "")      # the entry's short GP names against the symbol's long ones stay
    assert "pin 41:" not in names and "pin 43:" not in names and "pin 2:" not in names and "TP2" not in names


def test_a_name_swap_the_check_cannot_see_is_named_by_the_entry(project, recorded):
    assert imported(project, "C5446", without_declaration("C5446")) == []     # names equal the symbol's: no finding
    found = imported_again(project, "C5446")
    assert [g for g, _ in found] == ["declared"] and "pin 2 is VOUT" in found[0][1]


def test_names_a_symbol_got_wrong_are_compared_as_before(project, recorded):
    entry = {"lcsc": "C22451885", "mpn": "6N138S-TA1-L", "kind": "optocoupler",       # the 6N138's pins as its
             "pins": {"1": {"name": "NC", "type": "passive"}, "2": {"name": "A", "type": "passive"},  # data sheet has them
                      "3": {"name": "K", "type": "passive"}, "4": {"name": "NC", "type": "passive"},
                      "5": {"name": "GND", "type": "ground"}, "6": {"name": "VO", "type": "output"},
                      "7": {"name": "VB", "type": "input"}, "8": {"name": "VCC", "type": "power_in"}}}
    found = imported(project, "C22451885", entry)
    assert [g for g, _ in found] == [""]
    assert "pin 2: symbol '2', graph 'A'" in found[0][1] and "pin 3: symbol 'NC', graph 'K'" in found[0][1]


def test_a_symbol_with_three_of_four_pins(project):
    for sub in ("library", "footprints"):
        dst = project.root / "build" / "edakit" / sub
        dst.mkdir(parents=True, exist_ok=True)
        for f in (FIX / "library_cache" / sub).glob("*.json"):
            shutil.copy(f, dst / f.name)
    entry = {"lcsc": "C719745", "mpn": "AQY212GS", "kind": "optocoupler",
             "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"},
                      "3": {"name": "3", "type": "passive"}, "4": {"name": "4", "type": "passive"}}}
    project.save_part("C719745", entry)
    found = on_x9(project, "C719745", entry)
    assert any(g == "symbol" and "has no pin for pad 3 of its footprint" in t for g, t in found)


def test_a_correct_symbol_raises_nothing(project, recorded):
    assert imported(project, "C2297", project.part("C2297")) == []


def test_symbol_differs_has_its_form():
    from edakit import schema
    e = library.entry("C2297")
    assert schema.problems({**e, "symbol_differs": {"1": "read from the data sheet"}}) == []
    assert schema.problems({**e, "symbol_differs": {"1": ""}})
    assert schema.problems({**e, "symbol_differs": []})
