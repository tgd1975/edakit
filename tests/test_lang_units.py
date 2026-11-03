"""T.1 of circuit-dsl-toolchain.md: quantities, units and the E-series (language 4 and 7)."""

import pytest

from edakit.catalog import table, table_problems
from edakit.lang import series
from edakit.lang.units import Quantity, UnitError, format, parse


@pytest.mark.parametrize("text, want", [
    ("330Ω", (330, 330, "Ω")),
    ("330 Ω", (330, 330, "Ω")),
    ("4k7", (4700, 4700, None)),
    ("4k7 Ω", (4700, 4700, "Ω")),
    ("2R2", (2.2, 2.2, "Ω")),
    ("330R", (330, 330, "Ω")),
    ("10 ohm", (10, 10, "Ω")),
    ("100nF", (100e-9, 100e-9, "F")),
    ("22 µF", (22e-6, 22e-6, "F")),
    ("22 uF", (22e-6, 22e-6, "F")),
    ("10 mA", (0.01, 0.01, "A")),
    ("10mA", (0.01, 0.01, "A")),
    ("5 V", (5, 5, "V")),
    ("0.5 W", (0.5, 0.5, "W")),
    ("16 MHz", (16e6, 16e6, "Hz")),
    ("85 °C", (85, 85, "°C")),
    ("2 m", (2, 2, "m")),
    ("20 %", (20, 20, "%")),
    ("330", (330, 330, None)),
    ("0..5.5 V", (0, 5.5, "V")),
    ("0 V", (0, 0, "V")),
    ("2 mA .. 15 mA", (0.002, 0.015, "A")),
    ("2mA..15mA", (0.002, 0.015, "A")),
    ("0..3.4 V", (0, 3.4, "V")),
    ("-12..0 V", (-12, 0, "V")),
    ("10 mA ± 20 %", (0.008, 0.012, "A")),
    ("3.3 V +/- 5 %", (3.135, 3.465, "V")),
])
def test_every_form_of_language_4_parses(text, want):
    q = parse(text)
    assert q.lo == pytest.approx(want[0]) and q.hi == pytest.approx(want[1]) and q.unit == want[2]


@pytest.mark.parametrize("text", ["green", "1N4148", "KT-0805G", "", "LED{n}", "U1.GP3", "4k7x", "0805W8F1002T5E"])
def test_a_word_is_no_quantity(text):
    assert parse(text) is None


@pytest.mark.parametrize("text, said", [
    ("2 mA .. 5 V", "different units"),
    ("5 V..2 V", "lower end above"),
    ("2..15 mA", "lower end above"),
    ("10 mA ± 20 V", "a tolerance in %"),
])
def test_a_range_refuses_what_does_not_fit(text, said):
    with pytest.raises(UnitError, match=said):
        parse(text)


def test_a_unit_where_another_is_expected():
    with pytest.raises(UnitError, match="a voltage"):
        parse("10 mA", unit="V")
    assert parse("0..5.5", unit="V") == Quantity(0, 5.5, "V")     # a plain number takes the unit expected
    assert parse("0..5.5 V", unit="V") == Quantity(0, 5.5, "V")


@pytest.mark.parametrize("text, canonical", [
    ("330Ω", "330 Ω"), ("4k7 ohm", "4.7 kΩ"), ("10mA", "10 mA"), ("0..5.5 V", "0..5.5 V"),
    ("2 mA..15 mA", "2 mA..15 mA"), ("0 V", "0 V"), ("100nF", "100 nF"), ("-12..0 V", "-12..0 V"),
    ("0..15 mA", "0..15 mA"), ("330", "330"),
])
def test_format_writes_the_canonical_text_and_reads_back(text, canonical):
    q = parse(text)
    assert format(q) == canonical
    assert parse(canonical) == q


def test_a_quantity_knows_its_centre():
    assert parse("10 mA").centre == 0.01
    assert parse("2 mA .. 4 mA").centre == pytest.approx(0.003)


def test_the_series_table_has_its_source_and_its_counts():
    assert table_problems(table("series")) == []
    assert [len(series.values(n)) for n in ("E6", "E12", "E24", "E96")] == [6, 12, 24, 96]
    assert series.values("E24")[:4] == [1.0, 1.1, 1.2, 1.3]
    assert series.names() == ["E6", "E12", "E24", "E96"]


def test_nearest_and_window():
    assert series.nearest(260, "E24") == 270
    assert series.window(260, "E24") == (240, 300)
    assert series.nearest(15.9e-9, "E6") == 15e-9
    assert series.nearest(140, "E24") == 150 and series.window(140, "E24") == (130, 160)
    assert series.nearest(50, "E24") == 51 and series.window(50, "E24") == (47, 56)
    assert series.window(10, "E24") == (9.1, 11)                 # across a decade
    assert series.nearest(9.6, "E24") == 10
    with pytest.raises(ValueError, match="E7"):
        series.values("E7")
    with pytest.raises(ValueError, match="positive"):
        series.nearest(0, "E24")
