"""Symbol pins against the graph: numbers and names (a wrongly assumed pinout shows up as a name)."""

from edakit import schematic
from edakit.schematic import pin_differences


def test_place_takes_every_hand_soldered_part_out_of_the_bom(monkeypatch):
    """addIntoBom is set on create (M-9, easyeda-mcp-pro 1.7.0): every part with "bom": false – with an LCSC number
    or with an easyeda_device of its own, as pytree's RP2350-Zero – gets it in its create operation, read back after
    placing, and set again only where the bridge did not take it (it applies the flag best-effort)."""
    comps = {"R1": {"lcsc": "C25804"}, "J1": {"lcsc": "C2337", "bom": False},
             "U1": {"bom": False, "easyeda_device": {"uuid": "u", "libraryUuid": "l"}}}
    devices = {"C25804": {"uuid": "r"}, "C2337": {"uuid": "j"}, "dev:U1": {"uuid": "u", "libraryUuid": "l"}}
    writes, calls = [], []

    def batch_write(mcp, ops):
        writes.append(ops)
        return {op["operationId"]: f"id-{op['operationId'][6:]}" for op in ops if op["action"] == "create"}

    def api(mcp, path, *args):
        calls.append((path, *args))
        if path.endswith(".get"):    # J1 took the flag, U1 did not
            return {"state": {"AddIntoBom": args[0] != "id-J1"}}
    monkeypatch.setattr(schematic, "batch_write", batch_write)
    monkeypatch.setattr(schematic, "ensure_focus", lambda mcp: None)
    monkeypatch.setattr(schematic, "api", api)
    monkeypatch.setattr(schematic.eda, "list_sheet_parts",
                        lambda mcp: [{"primitiveId": f"id-{d}", "reference": d} for d in comps])
    schematic.place(None, comps, devices, {d: (0, 0) for d in comps})
    assert {op["operationId"]: op.get("addIntoBom") for op in writes[0]} == \
        {"place-J1": False, "place-R1": None, "place-U1": False}
    assert calls == [("SCH_PrimitiveComponent.get", "id-J1"), ("SCH_PrimitiveComponent.get", "id-U1"),
                     ("SCH_PrimitiveComponent.modify", "id-U1", {"addIntoBom": False})]


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
