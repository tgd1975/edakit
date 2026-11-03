"""`edakit order` and check PARTS.supplier (#41): a supplier per line – the assembler's BOM, one cart per other supplier with
spares and minimum or pack size, and the hand-assembly list, for `quantity` sets. The example's J1 (JST PH, C131337,
bom: false) is soldered by hand and bought at LCSC.
"""

import csv
import json

import pytest

from helpers import check, executed

from edakit import cli
from edakit.design import Design


def order(project, monkeypatch, *args):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    return cli.main(["order", *args])


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def out_dir(project):
    return project.root / "build" / "edakit" / "order"


def append_toml(project, text):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("quantity = 5 ", "quantity = 5\n" + text + "\n", 1)
                    if text.startswith("spare_pct") else toml.read_text() + "\n" + text + "\n")


def p5(project):
    cfg = project.config()
    rep = check(Design.from_config(cfg), cfg)
    return [m for c, m in rep.warnings if c == "PARTS.supplier"], rep


def test_j1_lands_in_the_lcsc_cart(project, monkeypatch, capsys):
    assert order(project, monkeypatch) == 0
    d = out_dir(project)
    assert sorted(p.name for p in d.iterdir()) == ["basket.json", "bom_main.csv", "cart_lcsc.csv", "hand_assembly.md"]
    assert read_csv(d / "cart_lcsc.csv") == [["LCSC Part Number", "Quantity", "Comment"],
                                             ["C131337", "5", "B2B-PH-K-S(LF)(SN): J1 (5 + 0)"]]
    out = capsys.readouterr().out
    assert "cart_lcsc.csv: 1 line" in out and "bom_main.csv: 9 lines" in out


def test_minimum_and_spares(project, monkeypatch):
    part = project.part("C131337")
    part["order"] = {"lcsc": {"moq": 10}}
    project.save_part("C131337", part)
    order(project, monkeypatch)
    assert read_csv(out_dir(project) / "cart_lcsc.csv")[1][:2] == ["C131337", "10"]
    part["order"] = {"lcsc": {"moq": 1}}
    project.save_part("C131337", part)
    append_toml(project, "spare_pct = 10")
    order(project, monkeypatch)
    assert read_csv(out_dir(project) / "cart_lcsc.csv")[1][:3] == ["C131337", "6", "B2B-PH-K-S(LF)(SN): J1 (5 + 1)"]


def test_pack_size_and_a_spare_on_the_component(project, monkeypatch):
    part = project.part("C131337")
    part["order"] = {"lcsc": {"moq": 20, "step": 20}}
    project.save_part("C131337", part)
    g = project.graph()
    project.comp(g, "J1")["spare"] = 16
    project.save_graph(g)
    order(project, monkeypatch)
    assert read_csv(out_dir(project) / "cart_lcsc.csv")[1][1] == "40"      # 5 + 16 = 21 → two packs of 20


def test_another_supplier_from_the_entry_or_the_component(project, monkeypatch):
    part = project.part("C131337")
    part["order"] = {"reichelt": "JST PH2P", "lcsc": {"moq": 10}}
    project.save_part("C131337", part)
    order(project, monkeypatch)
    d = out_dir(project)
    assert not (d / "cart_lcsc.csv").exists()
    assert read_csv(d / "cart_reichelt.csv") == [["Code", "Quantity", "Item", "Designators"],
                                                 ["JST PH2P", "5", "B2B-PH-K-S(LF)(SN)", "J1"]]
    g = project.graph()
    project.comp(g, "J1")["supplier"] = "lcsc"
    project.save_graph(g)
    order(project, monkeypatch)
    assert read_csv(d / "cart_lcsc.csv")[1][:2] == ["C131337", "10"] and not (d / "cart_reichelt.csv").exists()


def test_an_extra_gets_its_own_cart(project, monkeypatch):
    append_toml(project, '[[extra]]\nitem = "JST PH cable 20 cm"\nsupplier = "berrybase"\ncode = "AK-PH20"\n'
                         "per_set = 1\nspare = 2\nunit_price = 0.95\ncurrency = \"EUR\"")
    order(project, monkeypatch)
    d = out_dir(project)
    assert read_csv(d / "cart_berrybase.csv") == [["Code", "Quantity", "Item", "Designators"],
                                                  ["AK-PH20", "7", "JST PH cable 20 cm", ""]]
    hand = (d / "hand_assembly.md").read_text(encoding="utf-8")
    assert "| JST PH cable 20 cm | 1 | berrybase |" in hand


def test_the_cost_estimate_prices_the_cart_quantity(project, monkeypatch):
    append_toml(project, '[cost]\ncurrency = "EUR"\nrates = { USD = 0.87 }\n\n[[extra]]\nitem = "feet"\n'
                         'supplier = "hardware store"\nper_set = 4\nmoq = 25\nunit_price = 0.1')
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    cli.main(["cost"])
    est = json.loads((project.root / "build" / "edakit" / "cost.json").read_text())
    assert est["extras"][0]["qty"] == 25 and est["extras"][0]["amount"] == 2.5


def test_hand_assembly_lists_j1_once_per_board(project, monkeypatch):
    order(project, monkeypatch)
    hand = (out_dir(project) / "hand_assembly.md").read_text(encoding="utf-8")
    assert "## Board main (LED bar)" in hand and hand.count("| J1 |") == 1
    assert "| J1 | B2B-PH-K-S(LF)(SN) (C131337) | top | lcsc |" in hand and "5 sets" in hand


def test_the_assemblers_bom_is_the_f1_bom(project, monkeypatch):
    from edakit.release import fab
    order(project, monkeypatch, "--out", str(project.root / "o"))
    cfg = project.config()
    rows = fab.bom_rows(Design.from_config(cfg), cfg.board())
    fab.write_bom(rows, project.root / "f1.csv")
    assert (project.root / "o" / "bom_main.csv").read_bytes() == (project.root / "f1.csv").read_bytes()
    assert "C41407547" in (project.root / "o" / "bom_main.csv").read_text() and \
        "C131337" not in (project.root / "o" / "bom_main.csv").read_text()


# --- PARTS.supplier ------------------------------------------------------------------------------------------------------------

def test_the_example_has_no_p5_row(project):
    warnings, rep = p5(project)
    assert warnings == [] and "PARTS.supplier" in executed(project.config()) and not rep.errors


def test_a_part_bought_separately_without_a_supplier(project, monkeypatch, capsys):
    g = project.graph()
    j1 = project.comp(g, "J1")
    j1.pop("lcsc")                                # found by its mpn now: bought somewhere, nobody says where
    project.save_graph(g)
    (project.root / "hardware" / "parts" / "C131337.json").rename(
        project.root / "hardware" / "parts" / "B2B-PH-K-S_LF__SN_.json")
    warnings, _ = p5(project)
    assert warnings == ["J1 B2B-PH-K-S(LF)(SN): bought separately (bom: false), but neither an LCSC number nor "
                        "`order` in its parts entry – name the supplier and its order code"]
    assert order(project, monkeypatch) == 0
    assert "J1: no supplier" in capsys.readouterr().out
    assert "| J1 | B2B-PH-K-S(LF)(SN) | top | – |" in (out_dir(project) / "hand_assembly.md").read_text()
    part = json.loads((project.root / "hardware" / "parts" / "B2B-PH-K-S_LF__SN_.json").read_text())
    part["order"] = {"rs": "820-1466"}
    (project.root / "hardware" / "parts" / "B2B-PH-K-S_LF__SN_.json").write_text(json.dumps(part))
    assert p5(project)[0] == []


@pytest.mark.parametrize("toml, msg", [
    ("spare_pct = -5", "[project] spare_pct must be a number >= 0, not -5"),
    ('[[extra]]\nitem = "feet"\nsupplier = "x"\nper_set = 4\nmoq = 2.5', "[[extra]] 1 (feet): moq must be a whole "
                                                                          "number > 0, not 2.5"),
    ('[[extra]]\nitem = "feet"\nsupplier = "x"\nper_set = 4\ncolour = "red"', "[[extra]] 1 (feet): unknown key "
                                                                             "'colour'"),
])
def test_order_keys(project, toml, msg):
    from edakit.config import ConfigError
    append_toml(project, toml)
    with pytest.raises(ConfigError) as e:
        project.config()
    assert msg in str(e.value)


def test_an_easyeda_library_number_is_no_number(project, monkeypatch, capsys):
    """C99… numbers are EasyEDA user-library entries (handbook 4.2): LCSC does not sell them – not carted, and PARTS.supplier
    counts them as no number (the owner's answer to #41). With `part` or without, as the bell's Nano has both."""
    part = project.part("C131337")
    part["lcsc"] = "C9900187880"
    project.save_part("C9900187880", part)
    g = project.graph()
    project.comp(g, "J1")["lcsc"] = "C9900187880"
    project.comp(g, "J1").pop("part")
    project.save_graph(g)
    assert order(project, monkeypatch) == 0
    assert not (out_dir(project) / "cart_lcsc.csv").exists()
    out = capsys.readouterr().out
    assert "J1: no supplier" in out and "C9900187880 is an EasyEDA library number" in out
    assert p5(project)[0] == ["J1 B2B-PH-K-S(LF)(SN): bought separately (bom: false), but neither an LCSC number nor "
                              "`order` in its parts entry (C9900187880 is an EasyEDA library number, LCSC does not "
                              "sell it) – name the supplier and its order code"]
    project.comp(g, "J1")["part"] = "B2B-PH-K-S(LF)(SN)"
    project.save_graph(g)
    assert len(p5(project)[0]) == 1
    part["order"] = {"reichelt": "JST PH2P"}
    project.save_part("C9900187880", part)
    assert p5(project)[0] == []


def test_a_supplier_name_becomes_a_file_name(project, monkeypatch):
    append_toml(project, '[[extra]]\nitem = "washer DIN 9021 M10"\nsupplier = "hardware store"\nper_set = 20')
    order(project, monkeypatch)
    assert read_csv(out_dir(project) / "cart_hardware_store.csv")[1] == ["", "100", "washer DIN 9021 M10", ""]


def test_one_basket_for_several_projects(project, monkeypatch, capsys):
    """--with: the carts of another project go into the same files – one line per code, the pieces summed, the comment
    naming each project; two configs of one EasyEDA project are told apart by their boards (the bell's variants,
    2026-11-02, docs/concepts/new/parts-order.md decision 1)."""
    assert order(project, monkeypatch) == 0
    alone = {r[0]: int(r[1]) for r in read_csv(out_dir(project) / "cart_lcsc.csv")[1:]}
    assert order(project, monkeypatch, "--with", str(project.root / "edakit.toml")) == 0
    rows = read_csv(out_dir(project) / "cart_lcsc.csv")
    assert rows[0] == ["LCSC Part Number", "Quantity", "Comment"]
    both = {r[0]: int(r[1]) for r in rows[1:]}
    assert both == {code: 2 * n for code, n in alone.items()}
    comment = next(r[2] for r in rows[1:] if r[0] == "C131337")
    assert comment.count(" | ") == 1 and comment.startswith("led-bar (") and "J1" in comment
    out = capsys.readouterr().out
    assert "hand_assembly_led-bar_main.md" in out and any(p.name == "hand_assembly_led-bar_main.md"
                                                    for p in out_dir(project).iterdir())


def test_the_basket_sums_by_code():
    from edakit import order as o
    a = {"lcsc": [{"code": "C1", "item": "LED", "designators": ["D1"], "qty": 20, "need": 10}]}
    b = {"lcsc": [{"code": "C1", "item": "LED", "designators": ["D2", "D3"], "qty": 10, "need": 10},
                  {"code": "C2", "item": "R", "designators": ["R1"], "qty": 5, "need": 5}],
         "berrybase": [{"code": "X", "item": "Modul", "designators": ["U1"], "qty": 5, "need": 5}]}
    got = o.basket([("tree", a), ("bell", b)])
    assert list(got) == ["berrybase", "lcsc"]
    c1 = next(g for g in got["lcsc"] if g["code"] == "C1")
    assert (c1["qty"], c1["need"], [n for n, _ in c1["parts"]]) == (30, 20, ["tree", "bell"])


# --- the supplier's cart: edakit order check (docs/concepts/new/parts-order.md, steps 2 and 3) -----------------------

def lcsc_cart(project, change=None, page_change=None, weight=None):
    """cart.json and cart_page.txt as the skill cart writes them when LCSC's cart shows the basket exactly."""
    basket = json.loads((out_dir(project) / "basket.json").read_text())
    c = {"supplier": "lcsc", "read": "2026-11-02T10:00:00+01:00", "currency": "USD", "before": [],
         "lines": [{"code": b["code"], "quantity": b["qty"], "stock": 12000, "price": 0.5, "mark": ""}
                   for b in basket["suppliers"]["lcsc"]]}
    if weight is not None:
        c["weight_g"] = weight
    if change:
        change(c)
    page = "\n".join([*(f"{g['code']} Qty {g['quantity']:,} In stock {g['stock']:,} ${g['price']}" for g in
                        c["lines"] + c["before"] if "stock" in g), *(f"{g['code']} {g['quantity']}" for g in c["before"]
                                                                       if "stock" not in g),
                      *([f"Weight {weight} g"] if weight is not None else [])])
    d = out_dir(project) / "lcsc"
    d.mkdir(exist_ok=True)
    (d / "cart.json").write_text(json.dumps(c))
    (d / "cart_page.txt").write_text(page_change(page) if page_change else page)


def test_the_lcsc_profile():
    from edakit import order as o
    p = o.supplier("lcsc")
    assert p["recorded"] is False and p["start"] == "https://www.lcsc.com/bom" and "Checkout" in p["never"]
    assert p["columns"] == o.LCSC_HEAD
    addr = o.address(p["combine"])
    assert p["combine"]["maker"] == "jlcpcb" and addr["Postal Code"] == "999077" and addr["City"] == "KWAI CHUNG"
    assert "page" not in addr and o.supplier("berrybase") is None


def test_the_basket_file(project, monkeypatch):
    assert order(project, monkeypatch) == 0
    b = json.loads((out_dir(project) / "basket.json").read_text())
    assert b["projects"][0]["label"] == "led-bar" and b["projects"][0]["quantity"] == 5
    assert b["suppliers"]["lcsc"] == [{"code": "C131337", "qty": 5, "need": 5, "item": "B2B-PH-K-S(LF)(SN)",
                                       "comment": "B2B-PH-K-S(LF)(SN): J1 (5 + 0)"}]


def test_a_cart_as_the_basket_passes(project, monkeypatch, capsys):
    order(project, monkeypatch)
    lcsc_cart(project, lambda c: c["lines"][0].update(quantity=50, stock=1000))
    capsys.readouterr()
    assert order(project, monkeypatch, "check") == 0
    out = capsys.readouterr().out
    assert "PASS    ORDER.basket LCSC's cart = basket: 1 lines" in out
    assert "C131337: 50 instead of 5 – the supplier's rounding" in out and "never Checkout" in out
    assert "## Findings\n\n- none" in (out_dir(project) / "lcsc" / "check.md").read_text()


@pytest.mark.parametrize("change, page_change, expected", [
    (lambda c: c["lines"].clear(), None, "C131337 (B2B-PH-K-S(LF)(SN), 5 pieces) is not in the cart"),
    (lambda c: c["lines"][0].update(quantity=4), None, "C131337: 4 in the cart, the basket asks 5 (need 5)"),
    (lambda c: c["lines"][0].update(stock=3), None, "C131337: 3 in stock, 5 in the cart"),
    (lambda c: c["lines"][0].update(mark="Discontinued"), None, 'C131337: marked "Discontinued"'),
    (lambda c: c["lines"].append({"code": "C999", "quantity": 5, "stock": 10, "price": 1}), None,
     "C999 (5): in the cart, not in the basket and not there before"),
    (None, lambda p: p.replace("Qty 5", "Qty ?"), "C131337: 5 not in the page text – read, not made up"),
])
def test_each_finding_of_order_check(project, monkeypatch, capsys, change, page_change, expected):
    order(project, monkeypatch)
    lcsc_cart(project, change, page_change)
    capsys.readouterr()
    assert order(project, monkeypatch, "check") == 2
    out = capsys.readouterr().out
    assert "FAIL    ORDER.basket" in out and expected in out and "The parts order stops" in out


def test_lines_there_before_are_the_owners(project, monkeypatch, capsys):
    """2026-11-02 LCSC's cart held 25 lines of earlier work: listed, never touched, never a finding."""
    order(project, monkeypatch)
    lcsc_cart(project, lambda c: c.update(before=[{"code": "C25804", "quantity": 100},
                                                  {"code": "C131337", "quantity": 10}]))
    capsys.readouterr()
    assert order(project, monkeypatch, "check") == 0
    out = capsys.readouterr().out
    assert "in the cart before, not touched: C25804 x 100, C131337 x 10" in out
    assert "C131337: in the cart before the upload too (10) – the owner decides" in out


def test_check_needs_the_basket_and_the_cart(project, monkeypatch, capsys):
    assert order(project, monkeypatch, "check") == 1
    assert "basket.json is not there" in capsys.readouterr().err
    order(project, monkeypatch)
    assert order(project, monkeypatch, "check") == 1
    assert "cart.json is not there – the skill cart reads the cart back" in capsys.readouterr().err
    assert order(project, monkeypatch, "check", "--supplier", "berrybase") == 1
    assert "no profile for supplier berrybase" in capsys.readouterr().err


def test_the_cheapest_shipping_that_arrives_in_time():
    """The methods LCSC offered after combining on 2026-11-02 (parts-order.md): DHL Express was paid, the cheapest
    express was cheaper."""
    import datetime as dt
    from edakit import order as o
    ship = {"currency": "USD", "methods": [{"method": "DHL Express", "amount": 68.40, "days": "2-5 working days"},
                                           {"method": "FedEx IE", "amount": 56.94, "days": "2-5 working days"},
                                           {"method": "Global Direct", "amount": 18.37, "days": "7-15 working days"}]}
    page = "DHL Express $68.40\nFedEx IE $56.94\nGlobal Direct $18.37"
    monday = dt.date(2026, 11, 2)
    assert o.arrival("2-5 working days", monday) == dt.date(2026, 11, 9) and o.arrival("–", monday) is None
    rows, bad = o.shipping_choice(ship, page, dt.date(2026, 11, 10), monday)
    assert not bad and rows[0].startswith("  Global Direct: 18.37 USD") and "cheapest that arrives by 2026-11-10: " \
        "FedEx IE, 56.94 USD" in rows[-1]
    rows, _ = o.shipping_choice(ship, page, None, monday)
    assert "cheapest: Global Direct" in rows[-1]
    rows, _ = o.shipping_choice(ship, page, dt.date(2026, 11, 3), monday)
    assert "no method arrives by 2026-11-03" in rows[-1]
    _, bad = o.shipping_choice(ship, page.replace("68.40", "86.40"), None, monday)
    assert bad == ["shipping DHL Express: 68.4 not in the page text"]


@pytest.mark.parametrize("value, ok", [('"2026-12-10"', True), ("2026-12-10", True), ('"soon"', False)])
def test_needed_by(value, ok):
    import tomllib
    from edakit import makers
    c, bad = makers.cart(tomllib.loads(f"needed_by = {value}"))
    assert (not bad) == ok and (c["needed_by"].isoformat() == "2026-12-10" if ok else c["needed_by"] is None)
