"""Symbol pins against the graph: numbers and names (a wrongly assumed pinout shows up as a name)."""

from edakit.schematic import pin_differences


def test_same_pins_pass():
    assert pin_differences({"1": "A", "2": "K"}, {"1": "a", "2": " K"}) == []


def test_name_differs():
    assert pin_differences({"14": "D11", "27": "+5V"}, {"14": "D11/MOSI", "27": "+5V"}) == \
        ["pin 14: symbol 'D11', graph 'D11/MOSI'"]


def test_numbers_differ():
    assert pin_differences({"1": "A", "2": "K"}, {"1": "A", "3": "K"})[0] == "symbol only ['2'], graph only ['3']"
