"""`edakit stock` and check P-4 (parts orderable), offline: JLCPCB's answers are recorded in tests/fixtures/jlcpcb/ –
the catalogue answer of `selectSmtComponentList` per LCSC number (the fields edakit reads) and an excerpt of each part
page jlcpcb.com/partdetail/<C…> (its "PCBA Type" cell and the part's record in the page data), read 2026-10-27.

The example orders Economic (one side, SMD only), and its U1, the Raspberry Pi Pico 2 C41407547, is "Standard Only"
with X-ray at JLCPCB – and out of stock on the day of the recording.
"""

import datetime as dt
import json
from pathlib import Path

import pytest

from edakit import checks, cli
from edakit.design import Design

REC = Path(__file__).resolve().parent / "fixtures" / "jlcpcb"
ASSEMBLED = ["C17414", "C17604", "C2297", "C318884", "C41407547", "C45783", "C49678", "C8678", "C90107"]
TODAY = dt.date.today().isoformat()


def p4(rep):
    return ([m for c, m in rep.errors if c == "P-4"], [m for c, m in rep.pending if c == "P-4"],
            [m for c, m in rep.warnings if c == "P-4"], [m for c, m in rep.notes if c == "P-4"])


def run_checks(project):
    cfg = project.config()
    return checks.run(Design.from_config(cfg), cfg)


def stock_cli(project, monkeypatch, *args):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    return cli.main(["stock", *args])


def snapshot(project):
    return json.loads((project.root / "hardware" / "stock.json").read_text(encoding="utf-8"))


def edit_snapshot(project, change):
    f = project.root / "hardware" / "stock.json"
    s = json.loads(f.read_text(encoding="utf-8"))
    change(s)
    f.write_text(json.dumps(s, indent=1))


@pytest.fixture
def stocked(project, jlcpcb, monkeypatch, capsys):
    """The example with the snapshot of the recordings, U1 out of the way (hand-soldered), so that every other line
    passes and one fault per test shows alone."""
    stock_cli(project, monkeypatch)
    capsys.readouterr()
    g = project.graph()
    project.comp(g, "U1")["bom"] = False
    project.save_graph(g)
    assert p4(run_checks(project)) == ([], [], [], [])
    return project


# --- the sources ----------------------------------------------------------------------------------------------------

def test_parsers_give_the_snapshot_rows():
    from edakit import stock
    rows = {}
    for lcsc in ("C41407547", "C2895493", "C2297"):
        hit = next(h for h in json.loads((REC / "catalogue" / f"{lcsc}.json").read_text())["data"]
                   ["componentPageInfo"]["list"] if h["componentCode"] == lcsc)
        rows[lcsc] = stock.from_catalogue(hit) | stock.from_part_page(
            (REC / "partdetail" / f"{lcsc}.html").read_text(encoding="utf-8"), lcsc)
    pico, led5, led0805 = rows["C41407547"], rows["C2895493"], rows["C2297"]
    assert (pico["listed"], pico["class"], pico["mpn"], pico["stock"]) == (True, "Extended Part", "Raspberry Pi Pico 2", 0)
    assert (pico["assembly_type"], pico["xray"], pico["msl"], pico["mode"]) == ("Standard Only", True, None, "smt")
    assert pico["price_breaks"][0] == [1, 9.2955]
    assert (led5["assembly_type"], led5["msl"], led5["xray"], led5["mode"]) == ("Economic and Standard", 5, False,
                                                                                 "manual")
    assert (led0805["class"], led0805["msl"], led0805["attrition"], led0805["min_qty"]) == ("Basic Part", 3, 10, 20)
    assert led0805["preferred"] is False and led0805["price_breaks"] == sorted(led0805["price_breaks"])


def test_a_part_page_without_the_part_is_refused():
    from edakit import stock
    with pytest.raises(ValueError, match="C9999"):
        stock.from_part_page((REC / "partdetail" / "C2297.html").read_text(encoding="utf-8"), "C9999")


def test_need_with_the_assemblers_attrition():
    from edakit import stock
    ss34, r1k = {"attrition": 8, "min_qty": 5}, {"attrition": 10, "min_qty": 20}
    assert stock.need(5, "standard", ss34) == 13        # the Standard quote of 2026-10-24: 5 + 8
    assert stock.need(15, "standard", {"attrition": 10, "min_qty": 20}) == 25   # KT-0805G, 3 per board
    assert stock.need(5, "standard", r1k) == 20          # 1 kΩ, 1 per board: the minimum
    assert stock.need(5, "economic", r1k) == 5           # the Economic quote of 2026-10-25: exactly the placements


# --- edakit stock ---------------------------------------------------------------------------------------------------

def test_edakit_stock_writes_the_snapshot_of_the_assembled_parts(project, jlcpcb, monkeypatch, capsys):
    assert stock_cli(project, monkeypatch) == 2          # U1 cannot be ordered as the example declares it
    s = snapshot(project)
    assert s["date"] == TODAY and "selectSmtComponentList" in s["source"] and "partdetail" in s["source"]
    assert sorted(s["parts"]) == ASSEMBLED                # J1 is bom: false – soldered by hand, not asked
    assert s["parts"]["C8678"] | {"price_breaks": None} == {
        "date": TODAY, "listed": True, "class": "Basic Part", "preferred": False, "stock": 3563752, "mpn": "SS34",
        "assembly_type": "Economic and Standard", "msl": 1, "xray": False, "mode": "smt", "attrition": 8,
        "min_qty": 5, "price_breaks": None}
    out = capsys.readouterr().out
    assert "[9/9]" in out and "C41407547" in out and "Standard Only" in out
    assert "ERROR   P-4  U1 C41407547" in out
    jlcpcb.clear()
    assert stock_cli(project, monkeypatch) == 2 and jlcpcb == []          # everything is fresh: nothing asked
    assert stock_cli(project, monkeypatch, "--refresh") == 2 and sorted(jlcpcb) == ASSEMBLED


def test_edakit_stock_asks_only_what_is_missing_or_old(project, jlcpcb, monkeypatch):
    stock_cli(project, monkeypatch)
    old = (dt.date.today() - dt.timedelta(days=20)).isoformat()
    edit_snapshot(project, lambda s: (s["parts"].pop("C8678"), s["parts"]["C2297"].update(date=old),
                                      s["parts"]["C90107"].update(error="catalogue: timed out")))
    jlcpcb.clear()
    stock_cli(project, monkeypatch)
    assert sorted(jlcpcb) == ["C2297", "C8678", "C90107"]
    assert snapshot(project)["parts"]["C2297"]["date"] == TODAY


def test_edakit_stock_lcsc_prints_and_writes_nothing(tmp_path, jlcpcb, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)                          # no project: part search asks before the part is in a graph
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["stock", "--lcsc", "C2895493", "C41407547"]) == 0
    out = capsys.readouterr().out
    assert "C2895493" in out and "MSL 5" in out and "Standard Only" in out and "X-ray" in out
    assert not list(tmp_path.iterdir())


# --- P-4 ------------------------------------------------------------------------------------------------------------

def test_without_a_snapshot_p4_is_a_note_and_the_rest_unchanged(project):
    rep = run_checks(project)
    assert p4(rep) == ([], [], [], ["no stock snapshot (hardware/stock.json) – edakit stock asks JLCPCB about the 9 "
                                    "assembled parts"])
    assert not rep.errors and not rep.pending and not rep.warnings and "P-4" in checks.EXECUTED


def test_the_example_with_its_snapshot_fails_u1(project, jlcpcb, monkeypatch, capsys):
    stock_cli(project, monkeypatch)
    errors, pending, warnings, notes = p4(run_checks(project))
    assert errors == [
        "U1 C41407547: 0 in stock at JLCPCB on " + TODAY + ", 5 needed (1 x 5 boards)",
        "U1 C41407547 Raspberry Pi Pico 2: 'Standard Only' at JLCPCB, the order is Economic ([release] "
        "assembly.sides top: one side) – solder it by hand (bom: false), take another part, or order Standard "
        "(assembly.pcba)"]
    assert (pending, warnings, notes) == ([], [], [])
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("smd_only = true }", 'smd_only = true, pcba = "standard" }'))
    errors, _, _, _ = p4(run_checks(project))
    assert errors == ["U1 C41407547: 0 in stock at JLCPCB on " + TODAY + ", 5 needed (1 x 5 boards)"]


@pytest.mark.parametrize("fault, change, expected", [
    ("not listed", lambda s: s["parts"].__setitem__("C8678", {"date": TODAY, "listed": False}),
     ("error", "D1 C8678: not in JLCPCB's assembly catalogue on " + TODAY + " – pre-order only")),
    ("stock short", lambda s: s["parts"]["C90107"].update(stock=3),
     ("error", "U2 C90107: 3 in stock at JLCPCB on " + TODAY + ", 5 needed (1 x 5 boards)")),
    ("another part", lambda s: s["parts"]["C8678"].update(mpn="SS14"),
     ("error", "D1 C8678: JLCPCB names it SS14, the parts entry SS34")),
    ("stock within the margin", lambda s: s["parts"]["C90107"].update(stock=6),
     ("warning", "U2 C90107: 6 in stock at JLCPCB on " + TODAY + ", below 5 needed + 50 % (8)")),
    ("MSL 5", lambda s: s["parts"]["C2297"].update(msl=5),
     ("warning", "D2–D9 C2297 KT-0805G: MSL 5 at JLCPCB – baked before assembly (fee and 2 days more)")),
    ("class", lambda s: s["parts"]["C8678"].update({"class": "Extended Part"}),
     ("warning", "D1 C8678: JLCPCB lists it as Extended Part, the parts entry as Basic Part")),
    ("old", lambda s: s["parts"]["C2297"].update(date=(dt.date.today() - dt.timedelta(days=20)).isoformat()),
     ("pending", "hardware/stock.json: 1 of 8 parts read 20 days ago (stock_max_age_days 14) – edakit stock")),
    ("not asked", lambda s: s["parts"].pop("C2297"),
     ("pending", "D2–D9 C2297: not in the stock snapshot – edakit stock")),
    ("unread", lambda s: s["parts"]["C2297"].update(error="part page: HTTP 503"),
     ("pending", "D2–D9 C2297: not read on " + TODAY + " (part page: HTTP 503) – edakit stock")),
])
def test_one_fault_per_p4_row(stocked, fault, change, expected):
    edit_snapshot(stocked, change)
    toml = stocked.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("quantity = 5 ", "quantity = 5\nstock_margin_pct = 50 "))
    errors, pending, warnings, _ = p4(run_checks(stocked))
    found = [("error", m) for m in errors] + [("pending", m) for m in pending] + [("warning", m) for m in warnings]
    assert found == [expected]


def test_a_p4_finding_can_be_waived(stocked):
    edit_snapshot(stocked, lambda s: s["parts"]["C8678"].update(mpn="SS14"))
    g = stocked.graph()
    stocked.comp(g, "D1")["waive"] = {"P-4": "JLCPCB's catalogue names the SS34 wrongly (ticket 123)"}
    stocked.save_graph(g)
    rep = run_checks(stocked)
    assert p4(rep)[0] == [] and [c for c, _, _ in rep.waived].count("P-4") == 1


def test_the_gate_lists_p4_in_stage_p(project):
    from edakit.release import gate
    rows, _ = gate.stage_graph(project.config(), Design.from_config(project.config()))
    assert {(r["stage"], r["result"]) for r in rows if r["id"] == "P-4"} == {("P", "info"), ("P", "pass")}


def test_stock_keys(project):
    from edakit.config import ConfigError
    cfg = project.config()
    assert cfg.stock == project.root / "hardware" / "stock.json"
    assert (cfg.stock_margin_pct, cfg.stock_max_age_days) == (0, 14)
    assert cfg.pcba() == ("economic", "[release] assembly.sides top: one side")
    toml = project.root / "edakit.toml"
    text = toml.read_text()
    toml.write_text(text.replace('sides = ["top"]', 'sides = ["top", "bottom"]'))
    assert project.config().pcba() == ("standard", "[release] assembly.sides top + bottom: two sides")
    toml.write_text(text.replace("smd_only = true }", 'smd_only = true, pcba = "Standard" }'))
    with pytest.raises(ConfigError, match="assembly.pcba must be one of economic, standard, not 'Standard'"):
        project.config()
    toml.write_text(text.replace("quantity = 5 ", 'quantity = 5\nstock = "parts/stock.json"\nstock_margin_pct = -1\n'
                                                   "stock_max_age_days = 2.5 "))
    with pytest.raises(ConfigError) as e:
        project.config()
    assert "[project] stock_margin_pct must be a number >= 0, not -1" in str(e.value)
    assert "[project] stock_max_age_days must be a whole number >= 0, not 2.5" in str(e.value)
