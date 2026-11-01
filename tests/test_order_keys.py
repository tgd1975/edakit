"""Ordering steps 2 and 3 (docs/concepts/done/ordering.md): every field of a maker's form as a key of [order] with
edakit's default – [order] of edakit.toml under [order] of the board file –, order.json with the keys that change the
board where they differ from the default, the maker's profile ([cart], edakit/makers/<maker>.toml) and FILES.order per maker:
a finding fails for [cart] maker and warns for every other maker."""

import json
import shutil
from pathlib import Path

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
    return [(r["result"], r["check"], r["actual"]) for r in rows if r["id"] == "FILES.order"]


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


LOOKS = {"visible": "top"}


def test_a_board_people_look_at_is_ordered_without_the_order_number():
    """The owner's decision of 2026-10-31 (walkthrough-gaps C4): on a board with [looks] edakit's default of mark is
    "remove" – decided in the files, so it is in the fab hash before the gate and M-5, not chosen at the form. A mark
    given in [order] – of the board file or of edakit.toml – wins; a board without [looks] keeps "default"."""
    o = _board("b", {}, {"looks": LOOKS, "order": {}}).order
    assert (o["mark"], o["_from"]) == ("remove", {"mark": "looks"})
    o = _board("b", {}, {"looks": LOOKS, "order": {"mark": "default"}}).order
    assert (o["mark"], o["_from"]) == ("default", {"mark": "board"})
    o = _board("b", {}, {"looks": LOOKS}, project={"mark": "specify"}).order
    assert (o["mark"], o["_from"]) == ("specify", {"mark": "project"})
    assert _board("b", {}, {"order": {}}).order["mark"] == "default"
    assert _board("b", {}, {"looks": LOOKS}).order is None          # no [order]: no order of its own, as before


def looked_at(ex, p):
    """[looks] on the export's board, whose [order] gives a remark and no mark (and the "+" as the board file's text on
    the visible side, for GEO.silk)."""
    fr.visible(p)


def test_order_json_says_remove_on_a_board_people_look_at(project):
    """order.json has the mark whenever the board has [order]: on a [looks] board without a mark of its own "remove", so
    the fab hash is that of a board made without the order number – another one than the same files with "default"."""
    d, plain = fh.exported(project)
    assert json.loads((d / "order.json").read_text())["mark"] == "default"
    rows = run(project, looked_at)
    assert fr.findings(rows) == []
    d = project.root / "build" / "fab" / "main"
    assert json.loads((d / "order.json").read_text())["mark"] == "remove"
    assert "| Mark on PCB | Remove Mark | [looks] |" in sheet(project)
    assert fh.exported(project, looked_at)[1] != plain


def test_cart_alone_on_a_board_people_look_at(project):
    """[cart] without [order] on a [looks] board: order.md has "Remove Mark" – and still no order.json (the fab hash of
    a board without [order] stays the files')."""
    def cart(ex, p):
        fr.unordered(ex, p)
        looked_at(ex, p)
        toml(p, '[cart]\nmaker = "jlcpcb"')
    rows = run(project, cart)
    assert fr.findings(rows) == []
    assert not (project.root / "build" / "fab" / "main" / "order.json").exists()
    assert "| Mark on PCB | Remove Mark | [looks] |" in sheet(project)


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
        fr.unordered(ex, p)                 # no [order] in the board file: edakit.toml's holds for every board
        toml(p, '[order]\nmark = "remove"\nmask = "black"')
    rows = run(project, project_wide)
    assert fr.findings(rows) == []
    settings = json.loads((project.root / "build" / "fab" / "main" / "order.json").read_text())
    assert (settings["mask"], settings["mark"]) == ("black", "remove")
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
    """[cart] alone: the form of edakit's defaults, FILES.order – and no order.json, so the fab hash stays the files'."""
    def cart(ex, p):
        fr.unordered(ex, p)
        toml(p, '[cart]\nmaker = "jlcpcb"\nship_to = "DE"\nshipping = { jlcpcb = "DHL Express" }')
    rows = run(project, cart)
    assert fr.findings(rows) == []
    d = project.root / "build" / "fab" / "main"
    assert not (d / "order.json").exists() and (d / "order.md").exists()
    assert "| Ship to | DE | [cart] ship_to |\n| Shipping Method | DHL Express | [cart] shipping |" in sheet(project)
    assert ("info", "order form of this run", "order.md: JLCPCB, Economic PCBA, mark Remove Mark, "
            "tooling Added by Customer") in f6(rows)


# --- tooling holes nobody tells the maker about (walkthrough-gaps B4) ---------------------------------------------

UNTOLD = "tooling holes of the Economic PCBA ([release] assembly.sides top: one side) told to JLCPCB"


def test_tooling_holes_without_order_warn(project):
    """Without [order] and [cart] no order.md is written: the Economic board's own tooling holes are in no file the
    maker reads, and JLCPCB's form stays at "Added by JLCPCB" – FILES.order warns (grade tooling). [order] with a remark,
    as the example coin-cell-led has it, writes order.md with "Added by Customer"."""
    rows = run(project, fr.unordered)
    assert fr.findings(rows) == [("FILES.order", "warn")]
    assert f6(rows) == [("warn", UNTOLD, '2 tooling holes ([tooling]), but no [order] or [cart]: no order.md says '
                         '"Added by Customer" – the form stays at "Added by JLCPCB" and JLCPCB may drill its own on a '
                         'visible face; add [order] to the board file (a remark: tooling holes added by customer)')]
    assert not (project.root / "build" / "fab" / "main" / "order.md").exists()
    rows = run(project)                                       # the export's [order] remark
    assert fr.findings(rows) == [] and UNTOLD not in [c for _, c, _ in f6(rows)]
    assert "| Tooling holes | Added by Customer – 2 x Ø 1.152 mm | [tooling] |" in sheet(project)


def no_tooling_holes(ex, p):
    fr.unordered(ex, p)
    fr.board_file(p, "[tooling]\nholes", "# [tooling]\n# holes")


def standard(ex, p):
    fr.unordered(ex, p)
    f = p.root / "edakit.toml"
    f.write_text(f.read_text().replace('smd_only = true }', 'smd_only = true, pcba = "standard" }'))


def bare(ex, p):
    fr.unordered(ex, p)
    fr.graph(p, lambda g: [c.update(bom=False) for c in g["graph"]["components"]])
    f = p.root / "edakit.toml"
    f.write_text(f.read_text().replace('sides = ["top"]', "sides = []"))


@pytest.mark.parametrize("fault", [no_tooling_holes, standard, bare], ids=["no tooling holes", "Standard PCBA",
                                                                          "nothing assembled"])
def test_no_warning_where_the_form_does_not_ask_for_tooling_holes(project, fault):
    """No [order], no [cart] – and no tooling holes of the board's own (the maker drills its own, as the form says by
    default), a Standard assembly (JLCPCB's form asks for no tooling holes there) or no part assembled (no PCBA): FILES.order
    has nothing to say."""
    rows = run(project, fault)
    assert fr.findings(rows) == [] and f6(rows) == []


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
    assert jlc.offers("finish", "ENIG") and jlc.offers("finish", "OSP") is None       # OSP is offered, not edakit's
    assert jlc.word("mark", "default") == jlc.word("mark", "remove") == "Remove Mark"  # no order number since May 2026
    assert jlc.offers("mark", "specify") is False and "placeholder" not in jlc.rules
    assert jlc.rules["former_placeholder"] == "JLCJLCJLCJLC" and jlc.recorded == "2026-10-31"
    euro = makers.load("eurocircuits")                                         # recorded by ordering step 0
    assert euro.offers("finish", "LeadFree HASL") and euro.offers("finish", "ENIG") is None   # more = true: not read
    assert euro.offers("thickness_mm", 1.55) and euro.offers("thickness_mm", 1.6) is False   # live run 5.8
    assert euro.offers("mark", "specify") is False and makers.load("aisler").offers("finish", "OSP") is False
    assert not makers.load("aisler").has("mark") and euro.data["cart"] == "Add to basket"
    way = makers.load("pcbway")
    assert way.word("mark", "remove") == "Yes (extra+$ 1.5)" and not way.has("confirm_placement")
    assert all(m.recorded for m in map(makers.load, ("aisler", "eurocircuits", "pcbway")))
    for key in makers.shipped():                       # the maker's own RoHS and REACH statements, with the pages read
        c = makers.load(key).data["compliance"]
        assert c["rohs"] and c["reach"] and all("2026-" in src for src in c["sources"]), key


def test_a_profile_with_an_unknown_key_is_refused(tmp_path):
    (tmp_path / "own.toml").write_text('name = "Own"\nfiles = ["gerber", "pdf"]\n[fields.mask]\nlabel = "Colour"\n'
                                       'colours = ["green"]\n')
    with pytest.raises(makers.MakerError) as e:
        makers.load("own", {"own": str(tmp_path / "own.toml")})
    assert "files: unknown file 'pdf'" in str(e.value) and "fields.mask: unknown key 'colours'" in str(e.value)
    (tmp_path / "own.toml").write_text('name = "Own"\n[compliance]\nrohs = "RoHS compliant"\n')
    with pytest.raises(makers.MakerError, match="compliance must be a table of rohs and reach"):
        makers.load("own", {"own": str(tmp_path / "own.toml")})


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


# --- FILES.order per maker ---------------------------------------------------------------------------------------------------

def test_a_second_maker_warns_where_the_first_fails(project):
    """1.57 mm is no thickness of JLCPCB's form: FILES.order fails for JLCPCB as the planned maker – and only warns when
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


def test_the_former_placeholder_is_text_everywhere(project):
    """JLCJLCJLCJLC on the silkscreen was JLCPCB's placeholder until its order number went (ordering step 0,
    2026-10-31): every maker prints the letters now, JLCPCB too – a warning at each."""
    def both(ex, p):
        fr.ordered(ex, p, placeholder=True)
        toml(p, '[cart]\nmaker = "jlcpcb"\nmakers = ["jlcpcb", "eurocircuits"]')
    rows = run(project, both)
    got = [(r, c, a) for r, c, a in f6(rows) if "JLCJLCJLCJLC" in c]
    assert got == [("warn", "no JLCJLCJLCJLC on the silkscreen – JLCPCB no longer prints its order number there",
                    f"JLCJLCJLCJLC at (18.0, 3.0) on the top silkscreen – {m} prints it as it is; take it off "
                    '(mark = "remove", or a barcode = "qr" or "datamatrix" for traceability)')
                   for m in ("JLCPCB", "Eurocircuits")]
    assert fr.findings(rows) == [("FILES.order", "warn")] * 3 + [("SYNC.cpl", "warn")]   # and 1.6 mm, which
    # Eurocircuits does not make; D1's footprint is not in its [cpl.turns]


def test_a_value_the_form_does_not_offer(project):
    rows = run(project, lambda ex, p: fr.ordered(ex, p, {"copper_oz": 3}))
    assert ("fail", "Outer Copper Weight: a value JLCPCB's form offers", "copper_oz = 3 (board file) – JLCPCB offers "
            "1, 2, 2.5, 3.5, 4.5") in f6(rows)


def test_a_provisional_profile_is_named(project):
    def euro(ex, p):
        fr.ordered(ex, p)
        own = makers.DIR / "eurocircuits.toml"               # the project's own copy, not recorded yet
        (p.root / "eurocircuits.toml").write_text(own.read_text().replace('recorded = "2026-10-31"', "recorded = false"))
        toml(p, '[cart]\nmakers = ["jlcpcb", "eurocircuits"]\nprofiles = { eurocircuits = "eurocircuits.toml" }')
    rows = run(project, euro)
    infos = [a for r, c, a in f6(rows) if r == "info" and c == "Eurocircuits's profile"]
    assert infos and infos[0].startswith("provisional (recorded = false)")


@pytest.mark.parametrize("order, expected", [
    ({"layers": 4}, ("fail", "layers = the run's Gerber files ([order] layers)", "2 copper layers in the Gerber files")),
    ({"size_mm": [30, 25]}, ("fail", "size = the run's Gerber outline ([order] size_mm)",
                             "30.00 x 20.00 mm (Gerber outline)")),
    ({"delivery": "panel_by_customer"}, ("fail", "delivery = the run's files", 'delivery = "panel_by_customer" – the '
                                         "run's Gerber is one board, edakit draws no panel; single, or panel_by_maker "
                                         "with panel")),
    ({"quantity": 5, "pcba_quantity": 6}, ("fail", "PCBA quantity at most the PCB quantity",
                                           "pcba_quantity 6, quantity 5")),
    ({"quantity": 10}, ("warn", "PCBA quantity = [project] quantity (the sets PARTS.stock counts)",
                        "pcba_quantity 10, [project] quantity 5 – the stock checks count 5 sets")),
])
def test_keys_only_to_check_and_the_quantities(project, order, expected):
    rows = run(project, lambda ex, p: fr.ordered(ex, p, order))
    assert expected in f6(rows)


def test_layers_and_size_that_agree_pass(project):
    rows = run(project, lambda ex, p: fr.ordered(ex, p, {"layers": 2, "size_mm": [30.05, 20]}))
    assert fr.findings(rows) == []


# --- edakit cart fields ----------------------------------------------------------------------------------------------

def test_cart_fields_prints_the_form(project, monkeypatch, capsys):
    """Before any gate run: the fields from the keys, the Gerber facts not known yet."""
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    f = project.root / "hardware" / "boards" / "main.toml"
    f.write_text(f.read_text() + '\n[order]\nmask = "black"\n')
    assert cli.main(["cart", "fields"]) == 0
    out = capsys.readouterr().out
    assert "board main at JLCPCB (the planned maker; profile recorded 2026-10-31)" in out
    assert "  PCB Color                 Black                       board file   mask = 'black'\n" in out
    assert "  Layers                    –                           no gate run yet" in out
    assert cli.main(["cart", "fields", "--maker", "aisler"]) == 1
    assert "aisler is not in [cart] makers" in capsys.readouterr().err


# --- PARTS.stock and edakit stock per maker ------------------------------------------------------------------------------

def test_p4_runs_only_with_a_maker_of_jlcpcbs_catalogue(project, jlcpcb, monkeypatch, capsys):
    """Ordering step 3: PARTS.stock asks JLCPCB's catalogue only where a maker of [cart] makers orders from it. As the
    planned maker JLCPCB's findings fail; as the second maker they warn (grade other_maker), named; without it
    PARTS.stock does not run."""
    from helpers import executed
    from test_stock import p4, run_checks, stock_cli
    stock_cli(project, monkeypatch)
    capsys.readouterr()
    errors, _, warnings, _ = p4(run_checks(project))
    assert len(errors) == 2 and not warnings                              # U1: out of stock, "Standard Only"
    toml(project, '[cart]\nmaker = "eurocircuits"\nmakers = ["eurocircuits", "jlcpcb"]')
    rep = run_checks(project)
    errors, pending, warnings, _ = p4(rep)
    assert not errors and not pending and len(warnings) == 2
    assert all(w.startswith("U1 C41407547") and w.endswith("– JLCPCB, not the planned maker") for w in warnings)
    assert {f.grade for f in rep.findings if f.code == "PARTS.stock" and f.severity == "warning"} == {"other_maker"}
    toml(project, '[cart]\nmaker = "eurocircuits"')
    errors, pending, warnings, notes = p4(run_checks(project))
    assert (errors, pending, warnings) == ([], [], []) and notes == [
        "not run: no maker of [cart] makers orders from JLCPCB's parts catalogue – Eurocircuits matches the parts at "
        "the order (ORDER.parts); no stock snapshot needed"]
    assert "PARTS.stock" not in executed(project.config())
    toml(project, '[cart]\nmaker = "jlcpcb"')
    assert "PARTS.stock" in executed(project.config())
    toml(project, '[cart]\nmaker = "eurocircuits"')
    assert stock_cli(project, monkeypatch) == 1
    assert "no maker of [cart] makers orders from JLCPCB's parts catalogue" in capsys.readouterr().err


def test_f2_per_maker(project):
    """PARTS.stock reads JLCPCB's catalogue (here the recorded answer in jlc_parts.json): a line missing there fails while
    JLCPCB is the planned maker and warns while it is the second one; without JLCPCB PARTS.stock does not run."""
    def missing_line(planned, makers_):
        def fault(ex, p):
            ex.jlc.pop("C8678", None)
            toml(p, f'[cart]\nmaker = "{planned}"\nmakers = {json.dumps(makers_)}')
        return fault
    rows = run(project, missing_line("jlcpcb", ["jlcpcb"]))
    assert ("PARTS.stock", "fail") in fr.findings(rows)
    rows = run(project, missing_line("eurocircuits", ["eurocircuits", "jlcpcb"]))
    f2 = [r for r in rows if r["id"] == "PARTS.stock"]
    assert [r["result"] for r in f2] == ["warn"] and f2[0]["actual"].startswith("JLCPCB (not the planned maker): D1 ")
    rows = run(project, missing_line("eurocircuits", ["eurocircuits"]))
    assert not [r for r in rows if r["id"] == "PARTS.stock"]


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


# --- PARTS.fact/mpn and the BOM with MPN (ordering step 8) ---------------------------------------------------------------------

def test_p12_needs_mpn_and_manufacturer_for_a_maker_that_matches_by_mpn(project):
    """Ordering step 8: Eurocircuits matches by MPN – every assembled part's entry names mpn and manufacturer
    (PARTS.fact/mpn); an error while Eurocircuits is the planned maker, a warning (grade other_maker) while it is the
    second; not run without such a maker."""
    from helpers import check
    from edakit.design import Design

    def p12():
        cfg = project.config()
        rep = check(Design.from_config(cfg), cfg)
        mine = [f for f in rep.findings if f.code == "PARTS.fact" and f.grade in ("mpn", "other_maker")]
        return ([f.text for f in mine if f.severity == "error"], [f.text for f in mine if f.severity == "warning"])
    assert p12() == ([], [])
    part = project.part("C8678")
    del part["manufacturer"]
    project.save_part("C8678", part)
    assert p12() == ([], [])
    toml(project, '[cart]\nmaker = "eurocircuits"')
    assert p12() == (["D1 C8678: the parts entry has no manufacturer – Eurocircuits matches the BOM by manufacturer "
                      "part number"], [])
    toml(project, '[cart]\nmakers = ["jlcpcb", "eurocircuits"]')
    assert p12() == ([], ["D1 C8678: the parts entry has no manufacturer – Eurocircuits matches the BOM by manufacturer "
                          "part number – Eurocircuits, not the planned maker"])


def test_the_bom_with_mpn_for_a_maker_that_takes_it(project):
    import csv
    run(project, lambda ex, p: toml(p, '[cart]\nmakers = ["jlcpcb", "eurocircuits"]'))
    d = project.root / "build" / "fab" / "main"
    with open(d / "bom_main_mpn.csv", newline="") as f:
        rows = list(csv.reader(f))
    assert rows == [["Designator", "Quantity", "Value", "Package", "Manufacturer", "Manufacturer Part Number"],
                    ["C2", "1", "22uF", "C0805", "SAMSUNG(三星)", "CL21A226MAQNNNE"],
                    ["D1", "1", "SS34", "SMA_L4.3-W2.6-LS5.2-RD", "MDD(辰达半导体)", "SS34"]]
    run(project, lambda ex, p: toml(p, '[cart]\nmakers = ["jlcpcb"]'))
    assert not (d / "bom_main_mpn.csv").exists()


def test_one_bom_with_mpn_serves_every_maker_that_takes_it():
    """Live run 5.8 (2026-11-01): Eurocircuits' import left a column "MPN" unmapped and took "Comment" for the part
    number – C1 became a foam adhesive, R2 a battery holder. bom_<b>_mpn.csv is one file for every maker of [cart]
    makers, so they share the header Eurocircuits maps by itself."""
    from edakit.release.fab import MPN_COLUMNS
    takers = [m for m in map(makers.load, makers.shipped()) if "bom_mpn" in m.files]
    assert {m.key for m in takers} >= {"pcbway", "eurocircuits"}
    for m in takers:
        assert m.data["bom"]["columns"] == MPN_COLUMNS, m.key
    assert "MPN" not in MPN_COLUMNS and "Comment" not in MPN_COLUMNS


def cpl_rows(path):
    import csv
    with open(path, newline="") as f:
        return [(r["Designator"], r["Layer"], r["Rotation"]) for r in csv.DictReader(f)]


def test_eurocircuits_turns_a_sot23_by_90():
    """Live run 5.8 (2026-11-01): Eurocircuits' Assembly Editor drew Q1, EasyEDA's SOT-23-3_…-BR at 180°, turned by 90°
    against its pads; U1 (SOIC-8, -BL), D1 (the LED) and the 0805s sat on theirs. Eurocircuits reads IEC 61188-7 –
    pin 1 lower left –, the -BR footprint has pin 1 bottom right: Q1 is 270° there. JLCPCB draws EasyEDA's footprints.
    The probe the same day drew the CPL so turned with Q1 on its pads (live_2026-11-01/turn_probe.md)."""
    m = makers.load("eurocircuits")
    probe = Path(__file__).parent / "fixtures" / "makers" / "eurocircuits" / "live_2026-11-01" / "cpl_main_eurocircuits.csv"
    assert dict((ref, rot) for ref, _, rot in cpl_rows(probe))["Q1"] == "270"
    assert m.zero == "IEC 61188-7"
    assert {fp: m.turn(fp) for fp in ("SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR", "SOIC-8_L4.9-W3.9-P1.27-LS6.0-BL", "C0805",
                                      "R0805", "C0603", "LED-SMD_L2.0-W1.3_APTD2012SF4C", "SMA_L4.3-W2.6-LS5.2-RD")} == {
        "SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR": 90, "SOIC-8_L4.9-W3.9-P1.27-LS6.0-BL": 0, "C0805": 0, "R0805": 0,
        "C0603": 0, "LED-SMD_L2.0-W1.3_APTD2012SF4C": 0, "SMA_L4.3-W2.6-LS5.2-RD": None}
    assert (180 + m.turn("SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR")) % 360 == 270
    j = makers.load("jlcpcb")
    assert (j.zero, j.turn("SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR"), j.turn("anything")) == (None, 0, 0)
    assert (m.upload("main")[-1], j.upload("main")[-1]) == ("cpl_main_eurocircuits.csv", "cpl_main.csv")


def test_a_cpl_of_its_own_for_a_maker_with_another_zero(project, monkeypatch):
    """A maker whose zero orientation is not the footprint's gets cpl_<b>_<maker>.csv, every part turned by its
    footprint's [cpl.turns]; a footprint the profile does not list keeps its rotation and SYNC.cpl warns for that
    maker – M-2 checks it in the maker's preview. cpl_<b>.csv stays as it was, the fab hash with it."""
    from edakit.release import fab, gate
    rows = run(project, lambda ex, p: toml(p, '[cart]\nmakers = ["jlcpcb", "eurocircuits"]'))
    d = project.root / "build" / "fab" / "main"
    assert cpl_rows(d / "cpl_main.csv") == cpl_rows(d / "cpl_main_eurocircuits.csv") == [
        ("C2", "Top", "0"), ("D1", "Top", "180")]
    mine = [(r["result"], r["actual"]) for r in rows if r["id"] == "SYNC.cpl" and r.get("maker") == "eurocircuits"]
    assert mine == [("warn", "SMA_L4.3-W2.6-LS5.2-RD (D1): not in the profile's [cpl.turns]")]
    assert gate.upload(project.config(), "main") == ["gerber_main.zip", "bom_main.csv", "cpl_main.csv",
                                                     "bom_main_mpn.csv", "cpl_main_eurocircuits.csv"]
    layers = fab.fab_layers(d, "main")
    assert "cpl_main.csv" in layers and "cpl_main_eurocircuits.csv" not in layers

    monkeypatch.setitem(makers.load("eurocircuits").data["cpl"]["turns"], "SMA_*", 90)
    rows = run(project, lambda ex, p: toml(p, '[cart]\nmakers = ["jlcpcb", "eurocircuits"]'))
    assert cpl_rows(d / "cpl_main_eurocircuits.csv") == [("C2", "Top", "0"), ("D1", "Top", "270")]
    assert cpl_rows(d / "cpl_main.csv") == [("C2", "Top", "0"), ("D1", "Top", "180")]
    mine = [(r["result"], r["actual"]) for r in rows if r["id"] == "SYNC.cpl" and r.get("maker") == "eurocircuits"]
    assert mine == [("pass", "turned D1 180° → 270°")]
    assert fab.fab_layers(d, "main") == layers

    run(project, lambda ex, p: toml(p, '[cart]\nmakers = ["jlcpcb"]'))
    assert not (d / "cpl_main_eurocircuits.csv").exists()


def test_a_turned_part_on_the_bottom_keeps_its_rotation(project, monkeypatch):
    """The maker's rule for the bottom is unread (Eurocircuits' pages leave it out): a part on the bottom whose footprint
    has a turn keeps the footprint's rotation, and SYNC.cpl warns."""
    from edakit.release import fab
    toml(project, '[cart]\nmaker = "eurocircuits"\nmakers = ["eurocircuits"]')
    monkeypatch.setitem(makers.load("eurocircuits").data["cpl"]["turns"], "SMA_*", 90)
    cpl = [{"Designator": "C2", "Mid X": "20mm", "Mid Y": "9mm", "Layer": "B", "Rotation": 90},
           {"Designator": "D1", "Mid X": "13mm", "Mid Y": "9mm", "Layer": "B", "Rotation": 180.0}]
    data = {"C2": {"footprintName": "C0805"}, "D1": {"footprintName": "SMA_L4.3-W2.6-LS5.2-RD"}}
    rows, d = fab.Rows(), project.root / "out"
    d.mkdir()
    fab.write_maker_cpls(project.config(), project.config().board(), cpl, data, d, rows)
    assert cpl_rows(d / "cpl_main_eurocircuits.csv") == [("C2", "Bottom", "90"), ("D1", "Bottom", "180")]
    assert [(r["result"], r["actual"]) for r in rows] == [
        ("warn", "D1 (SMA_L4.3-W2.6-LS5.2-RD): on the bottom, not turned – the bottom rule of Eurocircuits is unread")]


@pytest.mark.parametrize("cpl, msg", [
    ({"zero": "IEC 61188-7", "turns": {"SOT-23*": 45}}, "cpl.turns must be a table of footprint pattern = degrees"),
    ({"turns": {"SOT-23*": 90}}, "cpl.turns needs cpl.zero"),
    ({"zero": "IEC 61188-7", "turn": {}}, "cpl: unknown key 'turn'"),
])
def test_a_profile_with_wrong_turns(cpl, msg):
    assert any(msg in p for p in makers.problems("x", {"cpl": cpl}))


def test_pcbway_has_a_placeholder_of_its_own(project):
    """PCBWay (planned with the user on 2026-10-30): its placeholder is WayWayWay – JLCPCB's letters on the silkscreen
    are text to it, and mark = "specify" there needs WayWayWay; it matches the BOM by MPN (PARTS.fact/mpn, bom_<b>_mpn.csv)."""
    m = makers.load("pcbway")
    assert (m.matches_by, m.rules["placeholder"], m.seat, m.data["cart"]) == ("mpn", "WayWayWay", "CN", "Save to Cart")

    def at_pcbway(ex, p):
        fr.ordered(ex, p, {"mark": "specify"}, placeholder=True)   # JLCJLCJLCJLC on the top silkscreen
        toml(p, '[cart]\nmaker = "pcbway"')
    rows = run(project, at_pcbway)
    got = {(r, c) for r, c, _ in f6(rows)}
    assert ("warn", "no JLCJLCJLCJLC on the silkscreen – JLCPCB no longer prints its order number there") in got
    assert ("fail", "order-number mark = placeholder WayWayWay on the silkscreen") in got
    assert (project.root / "build" / "fab" / "main" / "bom_main_mpn.csv").exists()


def test_pcbways_placeholder_is_text_to_jlcpcb(project):
    def wayway(ex, p):
        fr.ordered(ex, p, {"mark": "default"}, placeholder=False)
        ex.pcb["strings"].append({"Text": "WayWayWay", "X": 18 * fr.MIL, "Y": 3 * fr.MIL, "Layer": 3})
    rows = run(project, wayway)
    assert ("fail", "no WayWayWay on the silkscreen – JLCPCB has no order-number placeholder",
            "WayWayWay at (18.0, 3.0) on the top silkscreen – JLCPCB prints it as it is; a release that carries it is "
            "a release for PCBWay") in f6(rows)


def test_jlcpcbs_mark_and_barcode(project):
    """Ordering step 0 (2026-10-31): JLCPCB's "Mark on PCB" offers "Remove Mark" and "2D barcode (Serial Number)"
    only – mark = "specify" is refused; a barcode shows its dialog's "Printing", and a serial number without a barcode
    ("Number Only") is a combination edakit's keys do not name. The barcode and the serial number change the board:
    order.json has them where set."""
    rows = run(project, lambda ex, p: fr.ordered(ex, p, {"mark": "specify"}))
    assert ("fail", "Mark on PCB: a value JLCPCB's form offers") in {(r, c) for r, c, _ in f6(rows)}
    rows = run(project, lambda ex, p: fr.ordered(ex, p, {"barcode": "qr", "serial_number": True}))
    assert fr.findings(rows) == []
    settings = json.loads((project.root / "build" / "fab" / "main" / "order.json").read_text())
    assert (settings["barcode"], settings["serial_number"]) == ("qr", True)
    text = sheet(project)
    assert "| Mark on PCB | 2D barcode (Serial Number) | board file |" in text and "Remove Mark" not in text
    assert "| Printing | 2D barcode & Number | board file |" in text
    rows = run(project, lambda ex, p: fr.ordered(ex, p, {"serial_number": True}))
    assert ("fail", "no combination JLCPCB's form refuses") in {(r, c) for r, c, _ in f6(rows)}


# --- the customs description ----------------------------------------------------------------------------------------

DIY = {"category": "DIY", "hs_code": "902300"}


@pytest.mark.parametrize("customs, msg", [
    ("902300", r"order.customs must be \{ category = "),
    ({"category": "DIY"}, r"order.customs must be \{ category = "),
    ({"category": "DIY", "hs_code": "90-23"}, r"order.customs.hs_code must be the HS code's digits, 4 to 10, not '90-23'"),
    ({"category": "DIY", "hs_code": "902300", "value": 30}, r"order.customs: unknown key 'value'"),
])
def test_customs_of_the_wrong_kind_is_an_error(customs, msg):
    with pytest.raises(ConfigError, match=msg):
        _board("b", {}, {"order": {"customs": customs}})


def test_customs_is_no_setting_of_the_board(project):
    """The customs description tells the shipment, not the board: it is not in order.json, and the fab hash stays."""
    d, h = fh.exported(project, fh.ordered())
    d, same = fh.exported(project, fh.ordered(customs=DIY))
    assert same == h and "customs" not in json.loads((d / "order.json").read_text())


def test_jlcpcbs_product_description(project):
    """JLCPCB's Quote & Order asks a customs category with its HS code (a cascader, ordering step 0): [order] customs
    picks its entry, order.md shows it in JLCPCB's words, FILES.order holds it to the entries the form offers – one it
    does not offer fails and names the entries of the same HS code; without the key FILES.order names it, the owner's
    choice at the cart. A maker that asks nothing (Eurocircuits) has no such field."""
    rows = run(project, lambda ex, p: fr.ordered(ex, p, {"customs": DIY}))
    assert fr.findings(rows) == []
    assert ("| Product Description | Reserch\\Education\\DIY\\Entertainment / DIY - HS Code 902300 | board file |"
            in sheet(project))
    rows = run(project, lambda ex, p: fr.ordered(ex, p, {"customs": {"category": "Blinker", "hs_code": "847330"}}))
    assert ("fail", "Product Description: a value JLCPCB's form offers",
            "customs = Blinker, HS 847330 (board file) – JLCPCB offers no such entry; with HS 847330: PC(Personal "
            "Computer), Mouse, Keyboard, SSD(Solid State Disk), Reader, Development Board") in f6(rows)
    rows = run(project, lambda ex, p: fr.ordered(ex, p))
    assert ("info", "Product Description: the customs category with its HS code",
            "not set ([order] customs) – JLCPCB's form asks it before the cart; the owner chooses it there") in f6(rows)
    assert fr.findings(rows) == []
    assert "| Product Description | – |" in sheet(project)

    def euro(ex, p):
        fr.ordered(ex, p, {"customs": DIY})
        toml(p, '[cart]\nmaker = "eurocircuits"\nmakers = ["eurocircuits"]')
    run(project, euro)
    assert "Product Description" not in sheet(project)
