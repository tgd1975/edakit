"""`edakit cost` (#39): the order estimate from the graph, the parts entries, the board files, the stock snapshot and
the dated fee table edakit/fees/jlcpcb.json.

The fee model is tested on the origin's three quotes as plain numbers (pytree, 2026-10-24 and 2026-10-25), with the
fee table as it was read then – the SMT joint was 0.0017 $ on 2026-10-24, 0.0016 $ on 2026-10-27; JLCPCB converts to
USD daily. The example runs with the snapshot of tests/fixtures/jlcpcb (test_stock.py).
"""

import copy
import json
import math

import pytest

from edakit import cli, cost
from edakit.design import Design

SHIPPED = cost.load_fee_table()
OCT24 = copy.deepcopy(SHIPPED)
OCT24["pcba"]["economic_smt_joint"]["tiers"] = [[1, 100000, 0.0017]]


def line(lcsc, cls="Basic Part", refs=1, joints=0, side="top", **row):
    refs = [f"{lcsc}_{i}" for i in range(refs)]
    return {"lcsc": lcsc, "refs": refs, "sides": {r: side for r in refs}, "joints": joints, "listed": True,
            "class": cls, "preferred": False, "mode": "smt", "msl": 1, "xray": False,
            "assembly_type": "Economic and Standard", "attrition": 0, "min_qty": 0, "price_breaks": [[1, 0.0]]} | row


def stock_cli(project, monkeypatch, *args):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    return cli.main(["stock", *args])


def fees_of(est, *keys):
    return round(sum(f["amount"] for f in est["fees"] if f["key"].split(" ")[0] in keys), 2)


LISTED = ("setup", "stencil", "loading", "smt", "bake")


# --- the fee table --------------------------------------------------------------------------------------------------

def test_every_value_of_the_fee_table_has_a_date_and_a_source():
    found = []

    def walk(node, where):
        if isinstance(node, dict):
            if "value" in node or "tiers" in node:
                found.append(where)
                assert node.get("date") and node.get("source"), where
            for k, v in node.items():
                walk(v, f"{where}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{i}]")
    walk(SHIPPED, "jlcpcb")
    assert len(found) >= 20 and SHIPPED["date"] and SHIPPED["currency"] == "USD"


def test_pcb_price_from_the_table():
    assert cost.pcb_price(SHIPPED, 100, 170, 5) == (13.7, "fee table: 100 × 170 mm, 2026-10-25")
    assert cost.pcb_price(SHIPPED, 170, 110, 5)[0] == 14.5                      # turned: the same board
    price, how = cost.pcb_price(SHIPPED, 105, 170, 5)                            # between two sizes, by area
    assert 13.7 < price < 14.5 and "interpolated" in how
    price, how = cost.pcb_price(SHIPPED, 90, 40, 5)
    assert price == 10.7 and how.startswith("at most")                          # smaller than any priced size
    assert cost.pcb_price(SHIPPED, 100, 170, 10) == (None, "the fee table prices 5 boards, not 10 – [cost] pcb_price")


# --- the fee model on the origin's quotes ---------------------------------------------------------------------------

def usb_tree():
    """2026-10-25: Economic, top, 16 types (3 Extended), 169 joints per board, parts 16.95 $ for 5."""
    lines = [line("C1", joints=169, price_breaks=[[1, 16.95 / 5]])]
    lines += [line(f"C{i}", "Extended Part" if i < 5 else "Basic Part") for i in range(2, 17)]
    return lines


def test_usb_tree_economic(monkeypatch):
    est = cost.estimate_board(OCT24, 5, usb_tree(), ("economic", "one side"), size_mm=(100, 170))
    assert est["class"] == "economic"
    assert est["drivers"] == [f"C{i}_0 C{i} Extended Part – 3.07 loading fee" for i in (2, 3, 4)]
    assert fees_of(est, *LISTED) == 20.36                    # 9.71 + 3 x 3.07 + 845 x 0.0017
    alt = est["alternative"]
    assert alt["class"] == "standard" and fees_of(alt, "setup", "stencil", "loading") == 58.25  # 25.56 + 8.21 + 16 x 1.53
    assert not [f for f in est["fees"] if f["key"] == "handling"]                # 37.89 $ apart, more than 14.93
    assert est["pcb"]["amount"] == 13.7 and est["parts_total"] == pytest.approx(16.95)
    order = cost.order_total([est], {"shipping": 30.52, "coupon": 10}, rate=1.0)
    assert round(order["total"], 2) == 71.53                                     # the cart said 72.58
    shipped = cost.estimate_board(SHIPPED, 5, usb_tree(), ("economic", "one side"), size_mm=(100, 170))
    assert fees_of(shipped, *LISTED) == 20.27                                    # 845 x 0.0016 on 2026-10-27


def test_base_standard_bottom():
    """2026-10-24: Standard, bottom only, 10 types."""
    lines = [line(f"C{i}", side="bottom", joints=2) for i in range(10)]
    est = cost.estimate_board(OCT24, 5, lines, ("standard", "declared"), main_side="bottom", size_mm=(100, 100))
    assert est["class"] == "standard" and fees_of(est, "setup", "stencil", "loading") == 49.07    # quote: 50.48
    assert est["pcb"]["amount"] == 10.7 and est["pcb"]["size_mm"] == [110, 100]                    # edge rails
    assert [f["key"] for f in est["fees"] if f["key"] in ("packing", "smt joints")] == ["smt joints", "packing"]


def test_battery_tree_standard_both_sides():
    """2026-10-24: Standard, both sides, 41 types (23 Extended), bake, the Pico 2 with X-ray."""
    lines = [line("C41407547", "Extended Part", xray=True, assembly_type="Standard Only"),
             line("C2895493", "Extended Part", refs=2, side="bottom", msl=5)]
    lines += [line(f"C{i}", "Extended Part" if i < 21 else "Basic Part") for i in range(39)]
    est = cost.estimate_board(OCT24, 5, lines, ("standard", "two sides"), size_mm=(100, 170))
    assert est["class"] == "standard"
    assert fees_of(est, *LISTED[:3], "bake") == 138.21        # 2 x 25.56 + 2 x 8.21 + 41 x 1.53 + 7.94; quote 151.87
    assert [f["amount"] for f in est["fees"] if f["key"] == "x-ray"] == [8.2]   # 5 x 1.64, a value of its own
    drivers = " | ".join(est["drivers"])
    assert "both sides" in drivers and "C2895493 MSL 5" in drivers and "C41407547 X-ray" in drivers
    assert "C41407547 'Standard Only'" in drivers


def test_attrition_under_standard_only():
    rows = [line("C8678", refs=1, attrition=8, min_qty=5, price_breaks=[[1, 0.1]]),
            line("C17513", refs=1, attrition=10, min_qty=20, price_breaks=[[1, 0.01]])]
    std = cost.estimate_board(SHIPPED, 5, rows, ("standard", "declared"))
    eco = cost.estimate_board(SHIPPED, 5, rows, ("economic", "declared"))
    assert [p["qty"] for p in std["parts"]] == [13, 20] and [p["qty"] for p in eco["parts"]] == [5, 5]


def test_the_handling_fee_tops_up_a_standard_order_economic_could_assemble():
    lines = [line(f"C{i}", "Extended Part") for i in range(10)]   # Economic: 9.71 + 10 x 3.07 = 40.41
    est = cost.estimate_board(SHIPPED, 5, lines, ("standard", "declared"))
    eco = est["alternative"]
    assert eco["class"] == "economic" and est["total"] - eco["total"] == pytest.approx(14.93)
    assert [f["key"] for f in est["fees"]][-1] == "handling"
    one = cost.estimate_board(SHIPPED, 5, [line("C1")], ("standard", "declared"))   # 35.80 against 9.71
    assert "handling" not in [f["key"] for f in one["fees"]]


# --- the example ----------------------------------------------------------------------------------------------------

def run_cost(project, monkeypatch, *args):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    return cli.main(["cost", *args])


def last_estimate(project):
    return json.loads((project.root / "build" / "edakit" / "cost.json").read_text(encoding="utf-8"))


def test_the_example_is_standard_because_of_u1(project, jlcpcb, monkeypatch, capsys):
    stock_cli(project, monkeypatch)
    assert run_cost(project, monkeypatch) == 0
    out = capsys.readouterr().out
    main = last_estimate(project)["boards"]["main"]
    assert main["class"] == "standard"
    assert main["drivers"][0] == "U1 C41407547 'Standard Only' – Standard PCBA"
    assert any("U1 C41407547 X-ray" in d for d in main["drivers"])
    assert fees_of(main, "setup", "stencil", "loading") == 47.54                 # 25.56 + 8.21 + 9 x 1.53
    assert main["alternative"]["class"] == "economic" and main["alternative"]["without"] == ["U1"]
    assert "Standard PCBA" in out and "as Economic without U1" in out and "no PCB price" not in out


def test_the_example_with_u1_soldered_by_hand_is_economic(project, jlcpcb, monkeypatch):
    stock_cli(project, monkeypatch)
    g = project.graph()
    project.comp(g, "U1")["bom"] = False
    project.save_graph(g)
    run_cost(project, monkeypatch)
    main = last_estimate(project)["boards"]["main"]
    assert main["class"] == "economic" and main["drivers"] == ["U2 C90107 Extended Part – 3.07 loading fee"]
    assert fees_of(main, *LISTED) == round(8.18 + 1.53 + 3.07 + 46 * 5 * 0.0016, 2)   # 13.15; with 0.0017 13.17
    board = project.root / "hardware" / "boards" / "main.toml"
    board.write_text(board.read_text().replace('C1 = { x = 66, y = 25, rot = 0, side = "top" }',
                                               'C1 = { x = 66, y = 25, rot = 0, side = "bottom" }'))
    run_cost(project, monkeypatch)
    main = last_estimate(project)["boards"]["main"]
    assert main["class"] == "standard" and main["drivers"][0] == "C1 on bottom – both sides assembled, Standard PCBA"
    assert fees_of(main, "setup", "stencil") == round(2 * (25.56 + 8.21), 2)


def test_without_a_snapshot_only_the_fees(project, monkeypatch, capsys):
    assert run_cost(project, monkeypatch) == 0
    est = last_estimate(project)
    main = est["boards"]["main"]
    assert main["class"] == "economic" and all(p["amount"] is None for p in main["parts"])
    assert "no price" in capsys.readouterr().out and est["unpriced"] == 9


def test_the_change_since_the_last_estimate(project, jlcpcb, monkeypatch, capsys):
    stock_cli(project, monkeypatch)
    g = project.graph()
    project.comp(g, "U1")["bom"] = False
    project.save_graph(g)
    run_cost(project, monkeypatch)
    capsys.readouterr()
    part = project.part("C17414")
    part["jlc_class"] = "Extended Part"
    project.save_part("C17414", part)
    edit = project.root / "hardware" / "stock.json"
    s = json.loads(edit.read_text())
    s["parts"]["C17414"]["class"] = "Extended Part"
    edit.write_text(json.dumps(s))
    run_cost(project, monkeypatch)
    out = capsys.readouterr().out
    assert "+3.07 USD  main: loading fee C17414 (new)" in out


def test_extras_shipping_coupon_vat_and_currency(project, monkeypatch):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + """
[cost]
currency = "EUR"
rates = { USD = 0.86 }
shipping = 26.0
coupon = 8.6
vat_pct = 20

[[extra]]
item = "JST PH cable 20 cm"
supplier = "berrybase"
per_set = 1
unit_price = 0.95
currency = "EUR"
""")
    run_cost(project, monkeypatch)
    est = last_estimate(project)
    assert est["currency"] == "EUR"
    boards = est["boards"]["main"]["total"] * 0.86
    assert est["vat"] == pytest.approx(0.2 * (boards + 26.0 - 8.6), abs=0.01)
    assert est["extras"] == [{"item": "JST PH cable 20 cm", "supplier": "berrybase", "qty": 5, "unit_price": 0.95,
                              "currency": "EUR", "amount": 4.75}]
    assert est["total"] == pytest.approx(boards + 26.0 - 8.6 + est["vat"] + 4.75, abs=0.01)


def test_a_currency_without_a_rate_is_an_error(project, monkeypatch, capsys):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + '\n[cost]\ncurrency = "EUR"\n')
    assert run_cost(project, monkeypatch) == 1
    assert "[cost] rates has no rate for USD" in capsys.readouterr().err


# --- the gate -------------------------------------------------------------------------------------------------------

def gate_cost_rows(project):
    from edakit.release import gate
    cfg = project.config()
    rows, _ = gate.stage_graph(cfg, Design.from_config(cfg))
    return [r for r in rows if r["id"] == "cost"]


def test_the_gate_without_cost_has_no_new_row(project):
    assert gate_cost_rows(project) == []


def test_the_gate_with_cost_and_a_budget(project, monkeypatch, capsys):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + "\n[cost]\n")
    rows = gate_cost_rows(project)
    assert [(r["stage"], r["result"]) for r in rows] == [("P", "info")] and rows[0]["actual"].endswith(" USD")
    toml.write_text(toml.read_text() + "budget = 10\n")
    rows = gate_cost_rows(project)
    assert [(r["result"], r["expected"]) for r in rows] == [("warn", "at most 10.00 USD ([cost] budget)")]
    assert run_cost(project, monkeypatch) == 2
    assert "above the budget of 10.00 USD" in capsys.readouterr().out


def test_cost_keys(project):
    from edakit.config import ConfigError
    toml = project.root / "edakit.toml"
    text = toml.read_text()
    toml.write_text(text + '\n[cost]\nbudgte = 100\nrates = { EUR = 0 }\n\n[[extra]]\nitem = "feet"\nper_set = 4\n')
    with pytest.raises(ConfigError) as e:
        project.config()
    for msg in ("[cost]: unknown key 'budgte'", "[cost] rates.EUR must be a number > 0, not 0",
                "[[extra]] 1 (feet): supplier is missing"):
        assert msg in str(e.value)
    toml.write_text(text + '\n[cost]\nbudget = 100\n\n[[extra]]\nitem = "feet"\nsupplier = "x"\nper_set = 4\n')
    cfg = project.config()
    assert cfg.cost == {"budget": 100} and cfg.extras[0]["per_set"] == 4
    assert math.isclose(cost.load_fee_table(cfg)["pcba"]["bake"]["value"], 7.94)


# --- [order]: what the fee table's board is not -----------------------------------------------------------------------

PRICED = "1.6 mm, green mask, white silkscreen, LeadFree HASL"   # the shipped fee table's board (pcb.board)


def order(project, text, thickness=None):
    """[order] in the example's board file, and thickness_mm at its top."""
    f = project.root / "hardware" / "boards" / "main.toml"
    f.write_text((f"thickness_mm = {thickness}\n" if thickness else "") + f.read_text() + f"\n[order]\n{text}")


def test_a_deviating_order_is_named_as_not_in_the_price(project, monkeypatch, capsys):
    """Decided 2026-10-28: edakit cost prices the fee table's board; what [order] orders otherwise it names per board,
    with what that may mean at JLCPCB – it does not price it."""
    order(project, 'mask = "black"\n', thickness=1.0)
    assert run_cost(project, monkeypatch) == 0
    out = capsys.readouterr().out
    assert (f"  not in the price: thickness 1 mm, mask black ([order]; the fee table prices {PRICED})\n"
            "    JLCPCB may charge extra for another thickness; a colour other than green takes about two days longer\n"
            ) in out
    main = last_estimate(project)["boards"]["main"]
    assert main["not_in_price"] == {"thickness_mm": 1.0, "mask": "black"}
    assert main["pcb"]["how"] == "at most the price of the smallest size in the fee table, 110 × 100 mm – [cost] " \
                                 "pcb_price"                                       # the price itself as before


@pytest.mark.parametrize("text, shown, hint", [
    ('finish = "ENIG"\n', "finish ENIG", "JLCPCB may charge extra for another finish"),
    ('mask = "white"\n', "mask white, silkscreen black", "a colour other than green takes about two days longer"),
])
def test_each_deviating_setting_with_its_hint(project, monkeypatch, capsys, text, shown, hint):
    order(project, text)
    run_cost(project, monkeypatch, "--board", "main")
    out = capsys.readouterr().out
    assert f"  not in the price: {shown} ([order]; the fee table prices {PRICED})\n    {hint}\n" in out


def test_an_order_of_the_fee_tables_board_changes_nothing(project, monkeypatch, capsys):
    """Without [order], or with its defaults – the remark, the mark and the tab zones are no question of price –,
    the output stays as it was."""
    run_cost(project, monkeypatch)
    before = capsys.readouterr().out
    (project.root / "build" / "edakit" / "cost.json").unlink()               # no "since the last estimate"
    order(project, 'mask = "green"\nsilkscreen = "white"\nfinish = "LeadFree HASL"\nmark = "specify"\n'
                   'remark = "No V-cut."\n', thickness=1.6)
    run_cost(project, monkeypatch)
    assert capsys.readouterr().out == before
    assert "not_in_price" not in last_estimate(project)["boards"]["main"]


def test_a_board_nobody_assembles_is_priced_as_pcb_only(project, monkeypatch, capsys):
    """[release] assembly.sides = [] and every part bom: false (the bell's THT variant): no PCBA, no main side – the
    estimate prices the PCB only instead of failing on the first side."""
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace('sides = ["top"]', "sides = []"))
    g = project.graph()
    for c in g["graph"]["components"]:
        c["bom"] = False
    project.save_graph(g)
    assert run_cost(project, monkeypatch) == 0
    main = last_estimate(project)["boards"]["main"]
    assert main["fees"] == [] and main["parts"] == []
