"""Ordering steps 2 and 3 (docs/concepts/new/ordering.md): every field of a maker's form as a key of [order] with
edakit's default – [order] of edakit.toml under [order] of the board file –, order.json with the keys that change the
board where they differ from the default, the maker's profile ([cart], edakit/makers/<maker>.toml) and F-6 per maker:
a finding fails for [cart] maker and warns for every other maker."""

import json
import shutil

import pytest

import test_fab_hash as fh
import test_fab_run as fr
from edakit import cli, makers
from edakit.config import ORDER, ConfigError, _board, load
from edakit.release import order_sheet


def toml(project, text):
    """text at the end of edakit.toml – a table written again replaces the one written before."""
    f = project.root / "edakit.toml"
    head = text.split("\n", 1)[0]
    f.write_text(f.read_text().split("\n" + head + "\n")[0] + "\n" + text + "\n")


def run(project, fault=None):
    """test_fab_run.run on a fresh build folder – a test may export several times."""
    shutil.rmtree(project.root / "build", ignore_errors=True)
    return fr.run(project, fault)


def f6(rows):
    return [(r["result"], r["check"], r["actual"]) for r in rows if r["id"] == "F-6"]


def sheet(project):
    return (project.root / "build" / "fab" / "main" / "order.md").read_text()


# --- the keys -----------------------------------------------------------------------------------------------------

def test_every_key_has_edakits_default():
    """No [order] in the board file and none in edakit.toml: no order (as before). An empty [order]: every key at
    edakit's default – the board of the reference orders at JLCPCB."""
    assert _board("b", {}, {}).order is None
    o = _board("b", {}, {"order": {}}, quantity=4).order
    assert {k: o[k] for k in ("material", "tg", "delivery", "copper_oz", "vias", "outline_tolerance", "gold_fingers",
                              "electrical_test", "quality", "confirm_placement", "pcba_packaging")} == {
        "material": "FR-4", "tg": "TG135", "delivery": "single", "copper_oz": 1, "vias": "tented",
        "outline_tolerance": "regular", "gold_fingers": False, "electrical_test": "flying_probe", "quality": "ipc2",
        "confirm_placement": True, "pcba_packaging": "antistatic_bag"}
    assert (o["quantity"], o["pcba_quantity"], o["_from"]) == (4, 4, {})      # [project] quantity, then quantity
    o = _board("b", {}, {"order": {"quantity": 10}}, quantity=4).order
    assert (o["quantity"], o["pcba_quantity"], o["_from"]) == (10, 10, {"quantity": "board"})


@pytest.mark.parametrize("order, msg", [
    ({"vias": "open"}, "order.vias must be one of tented, untented, plugged, epoxy_filled, not 'open'"),
    ({"delivery": "panel"}, "order.delivery must be one of single, panel_by_customer, panel_by_maker"),
    ({"gold_fingers": "no"}, "order.gold_fingers must be true or false"),
    ({"copper_oz": 0}, r"order.copper_oz must be a number > 0, not 0"),
    ({"quantity": 2.5}, r"order.quantity must be a whole number > 0, not 2.5"),
    ({"size_mm": [30]}, r"order.size_mm must be \[width, height\] in mm"),
    ({"material": 4}, "order.material must be a string"),
    ({"delivery": "panel_by_maker"}, r'needs panel = \{ x, y, rails_mm \}'),
    ({"delivery": "panel_by_maker", "panel": {"x": 2}}, r"order.panel must be \{ x = boards across"),
])
def test_a_key_of_the_wrong_kind_is_an_error(order, msg):
    with pytest.raises(ConfigError, match=msg):
        _board("b", {}, {"order": order})


def test_the_project_order_and_the_board_order(tmp_path):
    """[order] of edakit.toml is the project's choice for every board, the board file's [order] wins per key; keys of
    one board (tab zones, size, layers) stay in the board file."""
    t = tmp_path / "edakit.toml"
    t.write_text('[project]\nname = "t"\n[order]\nmask = "black"\nvias = "plugged"\n[boards.main]\n[boards.usb]\n')
    (tmp_path / "hardware" / "boards").mkdir(parents=True)
    (tmp_path / "hardware" / "boards" / "usb.toml").write_text('[order]\nmask = "white"\n')
    cfg = load(t)
    main, usb = cfg.boards["main"].order, cfg.boards["usb"].order
    assert (main["mask"], main["silkscreen"], main["vias"]) == ("black", "white", "plugged")
    assert (usb["mask"], usb["silkscreen"], usb["vias"]) == ("white", "black", "plugged")   # print on a white mask
    assert usb["_from"] == {"mask": "board", "vias": "project"}
    t.write_text('[project]\nname = "t"\n[order]\ntab_zones = []\n[boards.main]\n')
    with pytest.raises(ConfigError, match=r"\[order\] tab_zones: a key of one board – it goes into \[order\] of the "
                                          "board file"):
        load(t)
    t.write_text('[project]\nname = "t"\n[order]\nmasks = "black"\n[boards.main]\n')
    with pytest.raises(ConfigError, match=r"edakit.toml \[order\]: unknown key 'masks'"):
        load(t)


def test_order_json_holds_a_new_key_only_where_it_differs(project):
    """order.json keeps the five settings it has; a key that changes the board joins it only with another value than
    edakit's default – a default set on purpose leaves the fab hash as it is, 2 oz copper changes it."""
    d, h = fh.exported(project, fh.ordered())
    assert set(json.loads((d / "order.json").read_text())) == set(order_sheet.FIVE)
    _, same = fh.exported(project, fh.ordered(copper_oz=1, vias="tented", gold_fingers=False))
    assert same == h
    d, heavy = fh.exported(project, fh.ordered(copper_oz=2, vias="plugged"))
    assert heavy != h
    settings = json.loads((d / "order.json").read_text())
    assert (settings["copper_oz"], settings["vias"]) == (2, "plugged") and "material" not in settings
    _, other = fh.exported(project, fh.ordered(electrical_test="fixture", pcba_packaging="tray"))
    assert other == h                                     # neither changes the board as made


def test_every_key_that_changes_the_board_is_known():
    made = {k for k, (_, _, m) in ORDER.items() if m} | {"thickness_mm"}     # thickness_mm: the board file's key
    assert made == set(order_sheet.SETTING_KEYS) and order_sheet.SETTING_KEYS[:5] == order_sheet.FIVE


def test_the_project_order_gives_every_board_an_order_json(project):
    def project_wide(ex, p):
        fr.ordered(ex, p)                   # the placeholder, and [order] in the board file – which goes again
        f = p.root / "hardware" / "boards" / "main.toml"
        head, _, rest = f.read_text().partition("\n[order]\n")
        f.write_text(head + rest[rest.index("\n[[silk.texts]]"):])
        toml(p, '[order]\nmark = "specify"\nmask = "black"')
    rows = run(project, project_wide)
    assert fr.findings(rows) == [("F-6", "warn")]       # the placeholder: JLCPCB's order number reported gone
    settings = json.loads((project.root / "build" / "fab" / "main" / "order.json").read_text())
    assert (settings["mask"], settings["mark"]) == ("black", "specify")
    assert "| PCB Color | Black | edakit.toml |" in sheet(project)


# --- the form ------------------------------------------------------------------------------------------------------

def test_order_md_lists_every_field_with_where_it_comes_from(project):
    run(project, lambda ex, p: fr.ordered(ex, p, {"vias": "untented", "copper_oz": 2}))
    text = sheet(project)
    for line in ("| Base Material | FR-4 | edakit |", "| Via Covering | Untented | board file |",
                 "| Outer Copper Weight | 2 oz | board file |", "| Confirm Parts Placement | Yes | edakit |",
                 "| Ship to | – | [cart] ship_to |"):
        assert line in text, line
    assert "Inner Copper Weight" not in text                  # two layers: no inner copper


def test_cart_without_order_writes_the_form_but_no_order_json(project):
    """[cart] alone: the form of edakit's defaults, F-6 – and no order.json, so the fab hash stays the files'."""
    def cart(ex, p):
        toml(p, '[cart]\nmaker = "jlcpcb"\nship_to = "DE"\nshipping = { jlcpcb = "DHL Express" }')
    rows = run(project, cart)
    assert fr.findings(rows) == []
    d = project.root / "build" / "fab" / "main"
    assert not (d / "order.json").exists() and (d / "order.md").exists()
    assert "| Ship to | DE | [cart] ship_to |\n| Shipping Method | DHL Express | [cart] shipping |" in sheet(project)
    assert ("info", "order form of this run", "order.md: JLCPCB, Economic PCBA, mark Order Number (JLCPCB places it), "
            "tooling Added by Customer") in f6(rows)


# --- the profiles ----------------------------------------------------------------------------------------------------

def test_the_shipped_profiles_are_valid():
    assert makers.shipped() == ["aisler", "eurocircuits", "jlcpcb", "pcbway"]
    for key in makers.shipped():
        m = makers.load(key)
        assert m.name and m.classes and m.files and m.seat and m.currency, key
        assert all(k in ORDER or k in order_sheet.FORM for k in m.data.get("fields", {})), key
    jlc = makers.load("jlcpcb")
    assert jlc.rules["thicknesses_mm"] == [0.4, 0.6, 0.8, 1.0, 1.2, 1.6, 2.0] and jlc.rules["remark_max"] == 200
    assert jlc.silkscreen_on("white") == "black" and jlc.silkscreen_on("blue") == "white"
    assert jlc.word("mask", "green") == "Green" and jlc.word("gold_fingers", False) == "No"
    assert jlc.word("thickness_mm", 1.6) == "1.6 mm" and jlc.word("size_mm", [30, 20]) == "30.00 x 20.00 mm"
    assert jlc.offers("finish", "ENIG") and jlc.offers("finish", "OSP") is False
    assert makers.load("eurocircuits").offers("finish", "ENIG") is None      # not recorded yet: not checked


def test_a_profile_with_an_unknown_key_is_refused(tmp_path):
    (tmp_path / "own.toml").write_text('name = "Own"\nfiles = ["gerber", "pdf"]\n[fields.mask]\nlabel = "Colour"\n'
                                       'colours = ["green"]\n')
    with pytest.raises(makers.MakerError) as e:
        makers.load("own", {"own": str(tmp_path / "own.toml")})
    assert "files: unknown file 'pdf'" in str(e.value) and "fields.mask: unknown key 'colours'" in str(e.value)


@pytest.mark.parametrize("cart, msg", [
    ('maker = "nextpcb"', r"maker nextpcb: no profile – edakit ships aisler, eurocircuits, jlcpcb, pcbway"),
    ('maker = "jlcpcb"\nmakers = ["eurocircuits"]', r"does not name \[cart\] maker 'jlcpcb'"),
    ('shipping = { aisler = "DHL" }', r"\[cart\] shipping names aisler, which is not in \[cart\] makers"),
    ('tolerance = -1', r"\[cart\] tolerance must be a number >= 0"),
    ('makers = "jlcpcb"', r"\[cart\] makers must be a list of makers"),
    ('basket = "x"', r"\[cart\]: unknown key 'basket'"),
])
def test_cart_is_checked(project, cart, msg):
    toml(project, f"[cart]\n{cart}")
    with pytest.raises(ConfigError, match=msg):
        project.config()


def test_the_assembly_class_is_one_of_the_planned_makers(project):
    toml(project, '[cart]\nmaker = "eurocircuits"')
    cfg = project.config()
    assert cfg.pcba() == ("proto", "the first assembly class of Eurocircuits")
    assert cfg.pcba("jlcpcb") == ("economic", "[release] assembly.sides top: one side")
    f = project.root / "edakit.toml"
    f.write_text(f.read_text().replace('smd_only = true }', 'smd_only = true, pcba = "economic" }'))
    with pytest.raises(ConfigError, match=r"\[release\] assembly.pcba must be one of proto, series \(the classes of "
                                          r"Eurocircuits, \[cart\] maker\), not 'economic'"):
        project.config()


# --- F-6 per maker ---------------------------------------------------------------------------------------------------

def test_a_second_maker_warns_where_the_first_fails(project):
    """1.57 mm is no thickness of JLCPCB's form: F-6 fails for JLCPCB as the planned maker – and only warns when
    JLCPCB is the second maker, beside Eurocircuits, whose thicknesses are not recorded yet."""
    rows = run(project, fr.thickness(1.57))
    assert ("fail", "board thickness JLCPCB makes (FR-4, 2 layers)",
            "1.57 mm (thickness_mm) – not a thickness of JLCPCB's form") in f6(rows)

    def second(ex, p):
        fr.thickness(1.57)(ex, p)
        toml(p, '[cart]\nmaker = "eurocircuits"\nmakers = ["eurocircuits", "jlcpcb"]')
    rows = run(project, second)
    assert ("warn", "board thickness JLCPCB makes (FR-4, 2 layers)",
            "1.57 mm (thickness_mm) – not a thickness of JLCPCB's form") in f6(rows)


def test_the_placeholder_is_jlcpcbs(project):
    """JLCJLCJLCJLC on the silkscreen is JLCPCB's placeholder: a maker without one prints the letters – a finding for
    that maker, a warning while it is the second one."""
    def both(planned):
        def fault(ex, p):
            fr.ordered(ex, p)
            toml(p, f'[cart]\nmaker = "{planned}"\nmakers = ["jlcpcb", "eurocircuits"]')
        return fault
    rows = run(project, both("jlcpcb"))
    text = ("no JLCJLCJLCJLC on the silkscreen – Eurocircuits has no order-number placeholder", "JLCJLCJLCJLC at "
            "(18.0, 3.0) on the top silkscreen – Eurocircuits prints it as it is; a release that carries it is a "
            "release for JLCPCB")
    assert ("warn", *text) in f6(rows)
    assert fr.findings(rows) == [("F-6", "warn"), ("F-6", "warn")]       # and JLCPCB's own, reported gone
    rows = run(project, both("eurocircuits"))
    assert ("fail", *text) in f6(rows)


def test_a_value_the_form_does_not_offer(project):
    rows = run(project, lambda ex, p: fr.ordered(ex, p, {"finish": "OSP"}))
    assert ("fail", "Surface Finish: a value JLCPCB's form offers", "finish = 'OSP' (board file) – JLCPCB offers "
            "'HASL(with lead)', 'LeadFree HASL', 'ENIG'") in f6(rows)


def test_a_provisional_profile_is_named(project):
    def euro(ex, p):
        fr.ordered(ex, p)
        toml(p, '[cart]\nmakers = ["jlcpcb", "eurocircuits"]')
    rows = run(project, euro)
    infos = [a for r, c, a in f6(rows) if r == "info" and c == "Eurocircuits's profile"]
    assert infos and "values not known for" in infos[0]


@pytest.mark.parametrize("order, expected", [
    ({"layers": 4}, ("fail", "layers = the run's Gerber files ([order] layers)", "2 copper layers in the Gerber files")),
    ({"size_mm": [30, 25]}, ("fail", "size = the run's Gerber outline ([order] size_mm)",
                             "30.00 x 20.00 mm (Gerber outline)")),
    ({"delivery": "panel_by_customer"}, ("fail", "delivery = the run's files", 'delivery = "panel_by_customer" – the '
                                         "run's Gerber is one board, edakit draws no panel; single, or panel_by_maker "
                                         "with panel")),
    ({"quantity": 5, "pcba_quantity": 6}, ("fail", "PCBA quantity at most the PCB quantity",
                                           "pcba_quantity 6, quantity 5")),
    ({"quantity": 10}, ("warn", "PCBA quantity = [project] quantity (the sets P-4 and F-2 count)",
                        "pcba_quantity 10, [project] quantity 5 – the stock checks count 5 sets")),
])
def test_keys_only_to_check_and_the_quantities(project, order, expected):
    rows = run(project, lambda ex, p: fr.ordered(ex, p, order))
    assert expected in f6(rows)


def test_layers_and_size_that_agree_pass(project):
    rows = run(project, lambda ex, p: fr.ordered(ex, p, {"layers": 2, "size_mm": [30.05, 20]}))
    assert fr.findings(rows) == [("F-6", "warn")]       # the placeholder: JLCPCB's order number reported gone


# --- edakit cart fields ----------------------------------------------------------------------------------------------

def test_cart_fields_prints_the_form(project, monkeypatch, capsys):
    """Before any gate run: the fields from the keys, the Gerber facts not known yet."""
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    f = project.root / "hardware" / "boards" / "main.toml"
    f.write_text(f.read_text() + '\n[order]\nmask = "black"\n')
    assert cli.main(["cart", "fields"]) == 0
    out = capsys.readouterr().out
    assert "board main at JLCPCB (the planned maker; profile provisional)" in out
    assert "  PCB Color                 Black                       board file   mask = 'black'\n" in out
    assert "  Layers                    –                           no gate run yet" in out
    assert cli.main(["cart", "fields", "--maker", "aisler"]) == 1
    assert "aisler is not in [cart] makers" in capsys.readouterr().err


# --- P-4, F-2 and edakit stock per maker ------------------------------------------------------------------------------

def test_p4_runs_only_with_a_maker_of_jlcpcbs_catalogue(project, jlcpcb, monkeypatch, capsys):
    """Ordering step 3: P-4 asks JLCPCB's catalogue only where a maker of [cart] makers orders from it. As the planned
    maker JLCPCB's findings fail; as the second maker they warn, named; without it P-4 does not run."""
    from test_stock import p4, run_checks, stock_cli
    from edakit import checks
    stock_cli(project, monkeypatch)
    capsys.readouterr()
    errors, _, warnings, _ = p4(run_checks(project))
    assert len(errors) == 2 and not warnings                              # U1: out of stock, "Standard Only"
    toml(project, '[cart]\nmaker = "eurocircuits"\nmakers = ["eurocircuits", "jlcpcb"]')
    errors, pending, warnings, _ = p4(run_checks(project))
    assert not errors and not pending and len(warnings) == 2
    assert all(w.startswith("JLCPCB (not the planned maker): U1 C41407547") for w in warnings)
    toml(project, '[cart]\nmaker = "eurocircuits"')
    errors, pending, warnings, notes = p4(run_checks(project))
    assert (errors, pending, warnings) == ([], [], []) and notes == [
        "not run: no maker of [cart] makers orders from JLCPCB's parts catalogue – Eurocircuits matches the parts at "
        "the order (B-2); no stock snapshot needed"]
    assert "P-4" not in checks.executed(project.config()) and "P-4" in checks.executed()
    assert stock_cli(project, monkeypatch) == 1
    assert "no maker of [cart] makers orders from JLCPCB's parts catalogue" in capsys.readouterr().err


def test_f2_per_maker(project):
    """F-2 reads JLCPCB's catalogue (here the recorded answer in jlc_parts.json): a line missing there fails while
    JLCPCB is the planned maker and warns while it is the second one; without JLCPCB F-2 does not run."""
    def missing_line(planned, makers_):
        def fault(ex, p):
            ex.jlc.pop("C8678", None)
            toml(p, f'[cart]\nmaker = "{planned}"\nmakers = {json.dumps(makers_)}')
        return fault
    rows = run(project, missing_line("jlcpcb", ["jlcpcb"]))
    assert ("F-2", "fail") in fr.findings(rows)
    rows = run(project, missing_line("eurocircuits", ["eurocircuits", "jlcpcb"]))
    f2 = [r for r in rows if r["id"] == "F-2"]
    assert [r["result"] for r in f2] == ["warn"] and f2[0]["actual"].startswith("JLCPCB (not the planned maker): D1 ")
    rows = run(project, missing_line("eurocircuits", ["eurocircuits"]))
    assert not [r for r in rows if r["id"] == "F-2"]


# --- edakit cost with the keys and the makers -------------------------------------------------------------------------

def test_cost_prices_quantity_pcbs_and_assembles_pcba_quantity(project):
    """[order] quantity: the PCBs ordered (the fee table prices 5); pcba_quantity: of them assembled – the joints and
    parts of 2 boards cost 2/5 of those of 5."""
    from edakit import cost
    five = cost.estimate(project.config())["boards"]["main"]
    f = project.root / "hardware" / "boards" / "main.toml"
    f.write_text(f.read_text() + "\n[order]\npcba_quantity = 2\n")
    two = cost.estimate(project.config())["boards"]["main"]
    assert two["pcb"]["amount"] == five["pcb"]["amount"]
    joints = lambda b: next(x["amount"] for x in b["fees"] if x["key"] == "smt joints")  # noqa: E731
    assert joints(two) == pytest.approx(joints(five) * 2 / 5)


def test_cost_names_every_key_that_changes_the_board(project, monkeypatch, capsys):
    from edakit import cost
    f = project.root / "hardware" / "boards" / "main.toml"
    f.write_text(f.read_text() + '\n[order]\ncopper_oz = 2\nvias = "plugged"\nelectrical_test = "fixture"\n')
    est = cost.estimate(project.config())
    assert est["boards"]["main"]["not_in_price"] == {"copper_oz": 2, "vias": "plugged"}   # the test is no setting
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["cost"]) == 0
    out = capsys.readouterr().out
    assert ("not in the price: copper_oz 2, vias plugged ([order]; the fee table prices 1.6 mm, green mask, white "
            "silkscreen, LeadFree HASL, edakit's defaults otherwise)\n    JLCPCB may charge extra for another "
            "copper_oz or vias") in out


def test_cost_without_a_fee_table_for_the_maker(project, monkeypatch, capsys):
    """A maker without a fee table: edakit cost has nothing to price – exit 1; the gate's cost row is information."""
    from edakit import cost
    toml(project, '[cart]\nmaker = "eurocircuits"')
    toml(project, '[cost]\nbudget = 100')
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["cost"]) == 1
    assert "no fee table for Eurocircuits ([cart] maker)" in capsys.readouterr().err
    assert [r["result"] for r in cost.gate_rows(project.config())] == ["info"]


# --- P-12 and the BOM with MPN (ordering step 8) ---------------------------------------------------------------------

def test_p12_needs_mpn_and_manufacturer_for_a_maker_that_matches_by_mpn(project):
    """Ordering step 8: Eurocircuits matches by MPN – every assembled part's entry names mpn and manufacturer; an
    error while Eurocircuits is the planned maker, a warning while it is the second; not run without such a maker."""
    from edakit import checks
    from edakit.design import Design

    def p12():
        cfg = project.config()
        rep = checks.run(Design.from_config(cfg), cfg)
        return [m for c, m in rep.errors if c == "P-12"], [m for c, m in rep.warnings if c == "P-12"], cfg
    errors, warnings, cfg = p12()
    assert (errors, warnings) == ([], []) and "P-12" not in checks.executed(cfg)
    part = project.part("C8678")
    del part["manufacturer"]
    project.save_part("C8678", part)
    assert p12()[:2] == ([], [])
    toml(project, '[cart]\nmaker = "eurocircuits"')
    errors, warnings, cfg = p12()
    assert errors == ["D1 C8678: the parts entry has no manufacturer – Eurocircuits matches the BOM by manufacturer "
                      "part number"] and "P-12" in checks.executed(cfg)
    toml(project, '[cart]\nmakers = ["jlcpcb", "eurocircuits"]')
    errors, warnings, _ = p12()
    assert not errors and warnings == ["Eurocircuits (not the planned maker): D1 C8678: the parts entry has no "
                                       "manufacturer – Eurocircuits matches the BOM by manufacturer part number"]


def test_the_bom_with_mpn_for_a_maker_that_takes_it(project):
    import csv
    run(project, lambda ex, p: toml(p, '[cart]\nmakers = ["jlcpcb", "eurocircuits"]'))
    d = project.root / "build" / "fab" / "main"
    with open(d / "bom_main_mpn.csv", newline="") as f:
        rows = list(csv.reader(f))
    assert rows == [["Designator", "Quantity", "Manufacturer", "MPN", "Comment"],
                    ["C2", "1", "SAMSUNG(三星)", "CL21A226MAQNNNE", "22uF"], ["D1", "1", "MDD(辰达半导体)", "SS34", "SS34"]]
    run(project, lambda ex, p: toml(p, '[cart]\nmakers = ["jlcpcb"]'))
    assert not (d / "bom_main_mpn.csv").exists()


def test_pcbway_has_a_placeholder_of_its_own(project):
    """PCBWay (planned with the user on 2026-10-30): its placeholder is WayWayWay – JLCPCB's letters on the silkscreen
    are text to it, and mark = "specify" there needs WayWayWay; it matches the BOM by MPN (P-12, bom_<b>_mpn.csv)."""
    m = makers.load("pcbway")
    assert (m.matches_by, m.rules["placeholder"], m.seat, m.data["cart"]) == ("mpn", "WayWayWay", "CN", "Save to Cart")

    def at_pcbway(ex, p):
        fr.ordered(ex, p)                                   # mark = "specify", JLCJLCJLCJLC on the top silkscreen
        toml(p, '[cart]\nmaker = "pcbway"')
    rows = run(project, at_pcbway)
    got = {(r, c) for r, c, _ in f6(rows)}
    assert ("fail", "no JLCJLCJLCJLC on the silkscreen – PCBWay's placeholder is WayWayWay") in got  # printed as text
    assert ("fail", "order-number mark = placeholder WayWayWay on the silkscreen") in got
    assert (project.root / "build" / "fab" / "main" / "bom_main_mpn.csv").exists()


def test_pcbways_placeholder_is_text_to_jlcpcb(project):
    def wayway(ex, p):
        fr.ordered(ex, p, {"mark": "default"}, placeholder=False)
        ex.pcb["strings"].append({"Text": "WayWayWay", "X": 18 * fr.MIL, "Y": 3 * fr.MIL, "Layer": 3})
    rows = run(project, wayway)
    assert ("fail", "no WayWayWay on the silkscreen – JLCPCB's placeholder is JLCJLCJLCJLC",
            "WayWayWay at (18.0, 3.0) on the top silkscreen – JLCPCB prints it as it is; a release that carries it is "
            "a release for PCBWay") in f6(rows)


def test_jlcpcbs_placeholder_warns_and_the_barcode_is_a_key(project):
    """The owner's decision of 2026-10-30: JLCPCB reports its order number gone since May 2026 – F-6 warns about the
    placeholder, as long as the profile says so (rules.placeholder_gone); without the placeholder, mark = "remove" and
    a QR code nothing warns. The barcode and the serial number change the board: order.json has them where set."""
    rows = run(project, lambda ex, p: fr.ordered(ex, p))
    warn = [a for r, c, a in f6(rows) if r == "warn"]
    assert len(warn) == 1 and warn[0].startswith("JLCJLCJLCJLC at (18.0, 3.0) on the top silkscreen – JLCPCB's help "
                                                 "article (last updated 2026-05-22) reports the order number gone")
    rows = run(project, lambda ex, p: fr.ordered(ex, p, {"mark": "remove", "barcode": "qr", "serial_number": True},
                                                  placeholder=False))
    assert fr.findings(rows) == []
    settings = json.loads((project.root / "build" / "fab" / "main" / "order.json").read_text())
    assert (settings["barcode"], settings["serial_number"]) == ("qr", True)
    assert "| 2D Barcode | QR Code | board file |\n| Serial Number | Yes | board file |" in sheet(project)

