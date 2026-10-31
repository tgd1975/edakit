"""Symbol pins against the graph: numbers and names (a wrongly assumed pinout shows up as a name)."""

from edakit.schematic import pin_differences


def test_same_pins_pass():
    assert pin_differences({"1": "A", "2": "K"}, {"1": "a", "2": " K"}) == []


def test_name_differs():
    assert pin_differences({"14": "D11", "27": "+5V"}, {"14": "D11/MOSI", "27": "+5V"}) == \
        ["pin 14: symbol 'D11', graph 'D11/MOSI'"]


def test_numbers_differ():
    assert pin_differences({"1": "A", "2": "K"}, {"1": "A", "3": "K"})[0] == "symbol only ['2'], graph only ['3']"


def test_pins_the_entry_declares_differing_are_left_out():
    """symbol_differs of the parts entry (4.1): the pin follows the datasheet, not the library symbol – schematic create
    leaves it out of its pin check as edakit check does (the live run of 2026-10-31: the Pico 2's SWDIO/SWCLK)."""
    symbol, graph = {"41": "SWDIO", "42": "GND", "43": "SWCLK"}, {"41": "SWCLK", "42": "GND", "43": "SWDIO"}
    assert len(pin_differences(symbol, graph)) == 2
    assert pin_differences(symbol, graph, skip={"41", "43"}) == []
