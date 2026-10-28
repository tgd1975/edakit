"""P-6 (#35): the graph and the parts entry name the same part – number, file name, mpn, value, kind – seen red in a
copy of the example, and the patterns of the real projects that must stay quiet."""

import json
import shutil

import pytest

from edakit import checks
from edakit.design import Design


def run(project):
    cfg = project.config()
    return checks.run(Design.from_config(cfg), cfg)


def p6(rep):
    return sorted(m for c, m in rep.errors if c == "P-6")


def rename(g, old, new):
    for c in g["graph"]["components"]:
        if c["designator"] == old:
            c["designator"] = new
    for n in g["graph"]["nets"]:
        n["pins"] = [f"{new}.{r.split('.', 1)[1]}" if r.split(".", 1)[0] == old else r for r in n["pins"]]


def test_five_identity_faults(project):
    """The faults of the proposal, built in at once: today `edakit check` passes them all."""
    parts = project.root / "hardware" / "parts"
    g = project.graph()
    project.comp(g, "R2")["value"] = "1k"                                    # entry C17414: 10 kΩ
    project.comp(g, "U2")["part"] = "UC5613PWP"                              # entry C90107: TLC5916IDR
    project.comp(g, "C1")["type"] = "resistor"                               # entry C49678: a capacitor
    project.comp(g, "D3")["lcsc"] = "C9900005314"                            # a user-library number
    shutil.copy(parts / "C2297.json", parts / "C9900005314.json")           # … its entry a copy of C2297's
    project.save_graph(g)
    e = project.part("C17604")
    project.save_part("C17604", {**e, "lcsc": "C25789"})                     # R1's entry, written for another number
    assert p6(run(project)) == [
        "C17604.json: lcsc C25789 – the file is named C17604 (R1)",
        "C1: type resistor does not fit kind capacitor of parts entry C49678",
        "C9900005314.json: lcsc C2297 – the file is named C9900005314 (D3)",
        "D3: lcsc C9900005314 is a part of an EasyEDA user library – nobody sells it (handbook 4.2)",
        "R2: value 1k reads 1 kΩ, parts entry C17414 has value_ohm 10 kΩ",
        "U2: part UC5613PWP does not name TLC5916IDR, the mpn of parts entry C90107",
    ]
    assert not [c for c, _ in run(project).errors if c != "P-6"]


@pytest.mark.parametrize("text, value", [
    ("10k", (1e4, None)), ("4k7", (4700, None)), ("2R2", (2.2, "Ω")), ("0Ω", (0, "Ω")), ("330 Ω 0805", (330, "Ω")),
    ("10 kΩ", (1e4, "Ω")), ("4.7kΩ", (4700, "Ω")), ("1M", (1e6, None)), ("100m", (0.1, None)),
    ("100nF", (1e-7, "F")), ("22uF", (2.2e-5, "F")), ("22µF", (2.2e-5, "F")), ("4n7", (4.7e-9, None)),
    ("1000uF 16V", (1e-3, "F")), ("4,7 µH", (4.7e-6, "H")), ("10 Ohm", (10, "Ω")),
    ("green", None), ("0805W8F3300T5E", None), ("1N4148", None), ("74HC165", None), ("5V", None), ("", None),
])
def test_values_read_as_a_quantity(text, value):
    got = checks.read_value(text)
    assert (got is None) == (value is None)
    if value:
        assert got[0] == pytest.approx(value[0], rel=1e-9) and got[1] == value[1]


@pytest.mark.parametrize("value, fires", [("10k", False), ("10.05k", False), ("10.2k", True), ("10 kΩ", False),
                                          ("100nF", True), ("ten k", True)])
def test_a_value_within_one_percent(project, value, fires):
    g = project.graph()
    project.comp(g, "R2")["value"] = value
    project.save_graph(g)
    assert bool(p6(run(project))) == fires


@pytest.mark.parametrize("part, fires", [
    ("UNI-ROYAL 0805W8F1002T5E", False),                 # manufacturer before the number (the reference project)
    ("0805w8f1002t5e", False),                           # case does not matter
    ("10 kΩ 0805", False),                               # a description: its value is compared (the bell)
    ("4.7 kΩ 0805", True),
    ("0805W8F1001T5E", True),                            # 1 kΩ's number on the 10 kΩ entry
])
def test_part_names_the_entry(project, part, fires):
    g = project.graph()
    project.comp(g, "R2")["part"] = part
    project.save_graph(g)
    assert bool(p6(run(project))) == fires


def test_remarks_of_the_mpn_are_left_out(project):
    """S8050 J3Y(RANGE:200-350), RP2350-Zero (Waveshare); Symbol und Footprint vom RP2040-Zero – as entries say."""
    e = project.part("C41407547")
    project.save_part("C41407547", {**e, "mpn": "Raspberry Pi Pico 2 (RP2350); symbol of the Pico"})
    assert not p6(run(project))
    g = project.graph()
    project.comp(g, "U1")["part"] = "Waveshare RP2350-Zero"
    project.save_graph(g)
    assert p6(run(project)) == ["U1: part Waveshare RP2350-Zero does not name Raspberry Pi Pico 2, the mpn of parts "
                                "entry C41407547"]


def test_a_user_library_number_outside_the_bom(project):
    """The Christmas bell's plugged-in Nano: symbol and footprint of a user library, never ordered."""
    parts = project.root / "hardware" / "parts"
    entry = json.loads((parts / "C2297.json").read_text())
    (parts / "C9900005314.json").write_text(json.dumps({**entry, "lcsc": "C9900005314"}))
    g = project.graph()
    project.comp(g, "D3")["lcsc"] = "C9900005314"
    project.save_graph(g)
    assert p6(run(project)) == [
        "D3: lcsc C9900005314 is a part of an EasyEDA user library – nobody sells it (handbook 4.2)"]
    project.comp(g, "D3")["bom"] = False
    project.save_graph(g)
    assert not p6(run(project))


def test_an_intended_mismatch_is_waived(project):
    g = project.graph()
    project.comp(g, "U2")["part"] = "UC5613PWP"
    project.comp(g, "U2")["waive"] = {"P-6": "the UC5613 is soldered by hand, the TLC5916's entry stands in for it"}
    project.save_graph(g)
    rep = run(project)
    assert not p6(rep) and [c for c, _, _ in rep.waived].count("P-6") == 1


def test_a_designator_prefix_against_the_kind_is_a_warning(project):
    """The early test circuit's LED came in as U1."""
    g = project.graph()
    rename(g, "D2", "U9")
    project.save_graph(g)
    rep = run(project)
    assert not p6(rep)
    assert ("P-6", "U9: designator prefix U, but parts entry C2297 is a led (D)") in rep.warnings


def test_an_entry_without_kind_is_not_compared(project):
    """An entry written with kind null: whoever signs it off fills it in (G-9 stays open)."""
    e = project.part("C49678")
    project.save_part("C49678", {**e, "kind": None})
    g = project.graph()
    project.comp(g, "C1")["type"] = "resistor"
    project.save_graph(g)
    rep = run(project)
    assert not [m for m in p6(rep) if "kind" in m] and not [m for c, m in rep.warnings if c == "P-6"]
