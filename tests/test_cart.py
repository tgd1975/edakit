"""Ordering step 4 (docs/concepts/done/ordering.md): `edakit cart prepare` writes the job of the skill cart from the
current release, `edakit cart check` holds what the skill brought back – quote.json and the page text – to the job,
the release and the page (ORDER.form to ORDER.review), `--cart` checks the cart line and writes the order record. On recorded data:
the example's export of test_fab_run, released, and a quote and page text as the skill would write them."""

import datetime as dt
import json
import shutil
import zipfile
from pathlib import Path

import pytest

import test_fab_run as fr
from edakit import cli, cost, makers
from edakit.release import gate

RUN = "20261030-120000"


def toml(project, text):
    f = project.root / "edakit.toml"
    head = text.split("\n", 1)[0]
    f.write_text(f.read_text().split("\n" + head + "\n")[0] + "\n" + text + "\n")


def released(project, fault=None, cart='[cart]\nship_to = "DE"\nshipping = { jlcpcb = "DHL Express" }', sign=True):
    """The example exported (test_fab_run), its folder the board folder of run RUN with the upload files, released;
    M-6 signed for its circuit hash; [cart] as given. Returns the run's board folder."""
    if cart:
        toml(project, cart)
    shutil.rmtree(project.root / "build", ignore_errors=True)
    rows = fr.run(project, fault)
    cfg = project.config()
    src = project.root / "build" / "fab" / "main"
    out = cfg.reports / RUN
    d = out / "fab" / "main"
    d.parent.mkdir(parents=True)
    shutil.move(src, d)
    with zipfile.ZipFile(d / "gerber_main.zip", "w") as z:
        for f in sorted((d / "gerber").iterdir()):
            z.write(f, f.name)
    head = {"time": RUN, "git_commit": "abc", "git_dirty": False, "graph_sha256": "g", "graph_version": "1.0",
            "state_sha256": gate.state_hash(cfg), "layout_sha256": gate.layout_hash(cfg),
            "fab_sha256": "f" * 64, "fab_method": "test", "fab_layers": {}}   # as a run with stage F: M-2 binds to it
    gate.write_manifest(cfg, out, head, "RELEASED")
    (out / gate.MAKERS).write_text(json.dumps(gate.maker_findings(cfg, rows)))
    if sign:
        s = json.loads(cfg.signoff.read_text())
        s["state_sha256"] = head["state_sha256"]
        for m in s["manual"]:
            if m["id"] == "M-6":
                m.update(done_by="agent regulatory-reviewer", date="2026-10-30")
        cfg.signoff.write_text(json.dumps(s, indent=1))
    return d


def cart(project, monkeypatch, *args):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    return cli.main(["cart", *args])


def order_dir(project, maker="jlcpcb"):
    return project.config().reports / RUN / "fab" / "main" / "cart" / maker


def job(project):
    return json.loads((order_dir(project) / "job.json").read_text())


def quote_of(j, change=None):
    """quote.json as the skill writes it when the page shows exactly the job – and the page text it kept."""
    q = {"maker": j["maker"]["key"], "read": "2026-10-30T12:30:00+01:00",
         "fields": [{"label": f["label"], "value": f["value"]} for f in j["fields"] if not f.get("read")],
         "files": [{"name": f["name"]} for f in j["files"]],
         "parts": [{"part": p["part"], "designators": p["designators"], "mark": ""} for p in j["bom"]],
         "dnp": list(j["dnp"]),
         "prices": [{"label": "PCB", "amount": round(j["estimate"]["pcb"], 2), "kind": "pcb"},
                    {"label": "Assembly fees", "amount": round(j["estimate"]["fees_total"], 2), "kind": "fee"},
                    {"label": "Components", "amount": round(j["estimate"]["parts_total"], 2), "kind": "parts"},
                    {"label": "Shipping", "amount": 20.48, "kind": "shipping"}],
         "currency": "USD", "lead_time": "3-4 days"}
    if change:
        change(q)
    page = "\n".join([*(f"{f['label']}: {f['value']}" for f in q["fields"]), *(f["name"] for f in q["files"]),
                      *(f"{p['part']} {', '.join(p['designators'])}" for p in q["parts"]),
                      *(f"{p['label']} ${p['amount']:.2f}" for p in q["prices"]), q["lead_time"]])
    return q, page


def write_quote(project, change=None, page_change=None):
    q, page = quote_of(job(project), change)
    d = order_dir(project)
    (d / "quote.json").write_text(json.dumps(q, indent=1))
    (d / "quote_page.txt").write_text(page_change(page) if page_change else page)
    return q


def review(project, verdict="Order: OK", findings="1. note – the board is for yourself (handbook 15.1)"):
    d = order_dir(project)
    sha = {n: gate.hashlib.sha256((d / n).read_bytes()).hexdigest() for n in ("job.json", "quote.json")}
    (d / "regulatory.md").write_text(f"# Regulatory review of the order\n\njob.json {sha['job.json']}\n"
                                     f"quote.json {sha['quote.json']}\n\n{findings}\n\n{verdict}\n")


def results(project):
    return {r["id"]: (r["result"], r["actual"]) for r in json.loads((order_dir(project) / "check.json").read_text())[
        "results"]}


@pytest.fixture
def prepared(project, monkeypatch, capsys):
    released(project, fr.ordered)
    assert cart(project, monkeypatch, "prepare") == 0
    capsys.readouterr()
    return project


# --- prepare ---------------------------------------------------------------------------------------------------------

def test_prepare_writes_the_job_of_the_current_release(project, monkeypatch, capsys):
    released(project, fr.ordered)
    assert cart(project, monkeypatch, "prepare") == 0
    out = capsys.readouterr().out
    j = job(project)
    assert (j["run"], j["board"], j["maker"]["key"], j["quantity"], j["ship_to"], j["shipping"]) == (
        RUN, "main", "jlcpcb", 5, "DE", "DHL Express")
    assert [f["name"] for f in j["files"]] == ["gerber_main.zip", "bom_main.csv", "cpl_main.csv"]
    assert all(len(f["sha256"]) == 64 and f["size"] > 0 for f in j["files"])
    assert {f["label"]: f["value"] for f in j["fields"]}["Mark on PCB"] == "Remove Mark"   # no order number since May 2026
    assert [(p["part"], p["designators"]) for p in j["bom"]] == [("C45783", ["C2"]), ("C8678", ["D1"])]
    assert j["dnp"] == [] and j["purpose"]["use"] == "private" and j["estimate"]["currency"] == "USD"
    assert "C8678" in j["compliance"] and j["maker"]["compliance"]["rohs"]   # the maker's own statement too
    assert "Save to Cart" in j["maker"]["cart"] and "Pay" in j["maker"]["never"]
    assert "job for board main at JLCPCB" in out and 'press only "Save to Cart"' in out


@pytest.mark.parametrize("change, msg", [
    (lambda p: None, None),
    (lambda p: (p.root / "hardware" / "boards" / "main.toml").write_text(
        (p.root / "hardware" / "boards" / "main.toml").read_text() + "\n# a comment\n"),
     "the layout changed since run 20261030-120000"),
    (lambda p: toml(p, '[order]\nmask = "black"'), "the order settings that change the board differ from run"),
])
def test_prepare_stops_on_a_changed_working_tree(project, monkeypatch, capsys, change, msg):
    released(project, fr.ordered)
    change(project)
    code = cart(project, monkeypatch, "prepare")
    assert code == (1 if msg else 0)
    if msg:
        assert msg in capsys.readouterr().err


def test_prepare_needs_m6_for_the_runs_circuit(project, monkeypatch, capsys):
    released(project, fr.ordered, sign=False)
    assert cart(project, monkeypatch, "prepare") == 1
    assert "M-6, the regulatory review, is not signed for the circuit hash of run" in capsys.readouterr().err


def test_prepare_needs_a_current_release_and_the_shipping(project, monkeypatch, capsys):
    toml(project, '[cart]\nship_to = "DE"')
    assert cart(project, monkeypatch, "prepare") == 1
    assert "no current release" in capsys.readouterr().err
    released(project, fr.ordered, cart='[cart]\nmaker = "jlcpcb"')
    assert cart(project, monkeypatch, "prepare") == 1
    assert "[cart] ship_to is not set" in capsys.readouterr().err


def test_prepare_stops_for_a_second_maker_with_findings(project, monkeypatch, capsys):
    """A QR code warns for Eurocircuits as the second maker (it prints no marking of its own) – the release stands for
    JLCPCB, the order at Eurocircuits stops on it."""
    released(project, lambda ex, p: fr.ordered(ex, p, {"barcode": "qr"}), cart='[cart]\nmakers = ["jlcpcb", "eurocircuits"]\nship_to = "DE"\n'
                                       'shipping = { jlcpcb = "DHL Express", eurocircuits = "UPS" }')
    assert cart(project, monkeypatch, "prepare", "--maker", "eurocircuits") == 1
    err = capsys.readouterr().err
    assert "has findings for Eurocircuits, which it did not plan the board for" in err and "Specific marking" in err
    assert cart(project, monkeypatch, "prepare") == 0


# --- check -----------------------------------------------------------------------------------------------------------

def test_a_quote_as_the_job_passes_and_waits_for_the_review(prepared, monkeypatch, capsys):
    write_quote(prepared)
    assert cart(prepared, monkeypatch, "check") == 3
    got = results(prepared)
    assert {k: v[0] for k, v in got.items()} == {"ORDER.form": "pass", "ORDER.parts": "pass", "ORDER.quote": "pass", "ORDER.read": "pass",
                                                 "ORDER.files": "pass", "ORDER.finish": "pass", "ORDER.review": "open"}
    review(prepared)
    assert cart(prepared, monkeypatch, "check") == 0
    assert results(prepared)["ORDER.review"][0] == "pass"
    assert "Every check passed" in (order_dir(prepared) / "check.md").read_text()


@pytest.mark.parametrize("change, page_change, expected", [
    (lambda q: next(f for f in q["fields"] if f["label"] == "Mark on PCB").update(value="2D barcode (Serial Number)"),
     None, ("ORDER.form", "fail", "Mark on PCB: the page '2D barcode (Serial Number)', the job 'Remove Mark'")),
    (lambda q: q["fields"].append({"label": "Engraving", "value": "No"}), None,
     ("ORDER.form", "fail", "Engraving: a field neither in the job nor in the profile's ignore – the maker added a question")),
    (lambda q: q["fields"].pop(0), None, ("ORDER.form", "fail", "Base Material: not read back")),
    (lambda q: q["parts"][1].update(mark="replaced: C123"), None, ("ORDER.parts", "fail", "C8678 D1: replaced: C123")),
    (lambda q: q["parts"].pop(0), None, ("ORDER.parts", "fail", "C45783 C2: not in the maker's matching")),
    (lambda q: q["prices"][1].update(amount=q["prices"][1]["amount"] + 1.5), None,
     ("ORDER.quote", "warn", "assembly fees: quote ")),
    (None, lambda page: page.replace("3-4 days", ""), ("ORDER.read", "fail", "not in quote_page.txt: 3-4 days")),
    (lambda q: q["files"][0].update(name="gerber_old.zip"), None,
     ("ORDER.files", "fail", "gerber_main.zip: not among the uploads the page shows")),
    (lambda q: q["files"][0].update(size="1 KB"), None, ("ORDER.files", "fail", "gerber_main.zip: the page shows 1 KB")),
])
def test_each_finding_of_the_check(prepared, monkeypatch, change, page_change, expected):
    write_quote(prepared, change, page_change)
    code = cart(prepared, monkeypatch, "check")
    cid, result, text = expected
    got = results(prepared)[cid]
    assert got[0] == result and text in got[1], got
    assert code == (2 if result == "fail" else 3)


def test_a_changed_upload_file_fails_b5(prepared, monkeypatch):
    write_quote(prepared)
    f = prepared.config().reports / RUN / "fab" / "main" / "cpl_main.csv"
    f.write_text(f.read_text() + "\n")
    assert cart(prepared, monkeypatch, "check") == 2
    assert "cpl_main.csv: changed since the job" in results(prepared)["ORDER.files"][1]


@pytest.mark.parametrize("use, result", [("sale", "fail"), ("gift", "warn"), ("private", "info")])
def test_lead_in_the_finish_by_purpose(project, monkeypatch, use, result):
    g = project.graph()
    g["graph"]["purpose"]["use"] = use
    project.save_graph(g)
    released(project, lambda ex, p: fr.ordered(ex, p, {"finish": "HASL(with lead)"}))
    assert cart(project, monkeypatch, "prepare") == 0
    write_quote(project)
    cart(project, monkeypatch, "check")
    level, text = results(project)["ORDER.finish"]
    assert level == result and text.startswith(f"HASL(with lead): lead in the product, purpose {use}")


def test_the_review_must_be_of_this_job_and_quote(prepared, monkeypatch):
    write_quote(prepared)
    review(prepared)
    write_quote(prepared, lambda q: q.update(lead_time="3-4 days"))       # the same values, rewritten
    assert cart(prepared, monkeypatch, "check") == 0                      # the bytes are the same: the hash holds
    write_quote(prepared, lambda q: q["prices"][3].update(amount=21.0))   # another quote
    assert cart(prepared, monkeypatch, "check") == 2
    assert "names another quote.json than the one now there" in results(prepared)["ORDER.review"][1]
    review(prepared, verdict="Order: not OK")
    assert cart(prepared, monkeypatch, "check") == 2
    assert results(prepared)["ORDER.review"] == ("fail", "regulatory.md: Order: not OK")


# --- --cart and the order record ---------------------------------------------------------------------------------------

def test_the_cart_line_and_the_order_record(prepared, monkeypatch):
    q = write_quote(prepared)
    review(prepared, findings="1. important – lead-free HASL: no lead (handbook 15.1)\n2. note – private use")
    subtotal = round(sum(p["amount"] for p in q["prices"] if p["kind"] != "shipping"), 2)
    d = order_dir(prepared)
    (d / "cart.json").write_text(json.dumps({"name": "gerber_main", "quantity": 5, "price": subtotal,
                                             "currency": "USD"}))
    assert cart(prepared, monkeypatch, "check", "--cart") == 0
    records = list((prepared.root / "hardware" / "orders").glob("*-main-jlcpcb.json"))
    assert len(records) == 1
    r = json.loads(records[0].read_text())
    assert (r["run"], r["maker"], r["quantity"], r["regulatory"]["verdict"]) == (RUN, "jlcpcb", 5, "Order: OK")
    assert r["regulatory"]["findings"] == [{"n": 1, "grade": "important"}, {"n": 2, "grade": "note"}]
    assert r["cart"]["price"] == subtotal and r["order_number"] is None
    (d / "cart.json").write_text(json.dumps({"name": "gerber_main", "quantity": 10, "price": subtotal}))
    assert cart(prepared, monkeypatch, "check", "--cart") == 2
    assert results(prepared)["cart"][1] == "quantity 10 in the cart, 5 in the job"


def test_the_checked_quote_gives_the_pcb_price(prepared, monkeypatch):
    """The board line of a checked JLCPCB quote is the PCB price of edakit cost while fab hash, quantity and maker are
    the quote's; [cost] pcb_price still wins."""
    write_quote(prepared, lambda q: q["prices"][0].update(amount=3.4))
    cart(prepared, monkeypatch, "check")
    b = cost.estimate(prepared.config())["boards"]["main"]
    assert b["pcb"]["amount"] == 3.4 and b["pcb"]["how"].startswith(f"quote of {RUN} (JLCPCB, 2026-10-30)")
    toml(prepared, "[cost]\npcb_price = 9.0")
    assert cost.estimate(prepared.config())["boards"]["main"]["pcb"]["amount"] == 9.0


def test_check_needs_the_job_and_the_quote(project, monkeypatch, capsys):
    released(project, fr.ordered)
    assert cart(project, monkeypatch, "check") == 1
    assert "edakit cart prepare first" in capsys.readouterr().err
    assert cart(project, monkeypatch, "prepare") == 0
    assert cart(project, monkeypatch, "check") == 1
    assert "quote.json is not there – the skill cart writes it" in capsys.readouterr().err


# --- edakit cart actual (ordering step 6) -----------------------------------------------------------------------------

def actual_of(j, change=None):
    """actual.json as the skill reads the order page – the lines of the estimate, the setup dearer – and its page."""
    e = j["estimate"]
    fees = {f["key"]: f for f in e["fees"]}
    a = {"order_number": "Y8-1234567A", "date": "2026-11-02", "currency": "USD",
         "lines": [{"label": "PCB", "amount": round(e["pcb"], 2), "kind": "pcb"},
                   {"label": "Setup fee", "amount": 8.5, "kind": "fee", "estimate": "setup"},
                   {"label": "Stencil", "amount": round(fees["stencil"]["amount"], 2), "kind": "fee",
                    "estimate": "stencil"},
                   {"label": "SMT assembly", "amount": 0.4, "kind": "fee", "estimate": "smt joints",
                    "count": fees["smt joints"]["count"]},
                   {"label": "Components", "amount": round(e["parts_total"], 2), "kind": "parts"}],
         "order": [{"label": "Shipping", "amount": 20.48, "kind": "shipping"},
                   {"label": "Discount", "amount": -9.0, "kind": "coupon"},      # the page prints -$9.00
                   {"label": "Total", "amount": 40.0, "kind": "total"}]}
    if change:
        change(a)
    page = "\n".join([a["order_number"], *(f"{x['label']} {'-' if x['amount'] < 0 else ''}${abs(x['amount']):.2f}"
                                           + (f" ({x['count']} joints)" if x.get("count") else "")
                                           for x in a["lines"] + a["order"])])
    return a, page


def write_actual(project, change=None):
    a, page = actual_of(job(project), change)
    d = order_dir(project)
    (d / "actual.json").write_text(json.dumps(a, indent=1))
    (d / "actual_page.txt").write_text(page)
    return a


def test_real_cost_into_the_projects_fee_table(prepared, monkeypatch, capsys):
    """What maps one to one goes into hardware/fees/jlcpcb.json with the order as its source; edakit cost takes the
    newest value; actual.md compares estimate, quote and actual; release current shows the totals."""
    write_quote(prepared)
    review(prepared)
    write_actual(prepared)
    assert cart(prepared, monkeypatch, "actual") == 0
    out = capsys.readouterr().out
    assert "ok   ORDER.read read, not made up" in out and "fee table: Setup fee: economic_setup 8.5" in out
    own = json.loads((prepared.root / "hardware" / "fees" / "jlcpcb.json").read_text())
    setup = own["pcba"]["economic_setup"]
    assert (setup["value"], setup["date"], setup["source"]) == (8.5, "2026-11-02", "order Y8-1234567A at JLCPCB, "
                                                                "2026-11-02 (edakit cart actual)")
    joints = own["pcba"]["economic_smt_joint"]
    n = next(f["count"] for f in job(prepared)["estimate"]["fees"] if f["key"] == "smt joints")
    assert joints["read"] == {"tier": [1, 100000], "count": n} and joints["tiers"][0][2] == round(0.4 / n, 4)
    assert own["pcb"]["prices"][0]["source"].startswith("order Y8-1234567A")
    cfg = prepared.config()
    assert cost.load_fee_table(cfg)["pcba"]["economic_setup"]["value"] == 8.5        # the newest value wins
    assert cost.load_fee_table(cfg)["pcba"]["bake"]["value"] == 7.94                 # not on the order: as it was
    md = (order_dir(prepared) / "actual.md").read_text()
    assert "| Line | Estimate | Quote | Actual | Actual − estimate |" in md and "| shipping |" in md
    assert "| coupon | – | 9.00 |" in md                                       # read from -$9.00 on the page
    assert cli.main(["release", "current", "--config", str(cfg.root / "edakit.toml")]) == 0
    assert "  order Y8-1234567A at jlcpcb, board main: estimate " in capsys.readouterr().out


def test_another_count_is_named_not_written(prepared, monkeypatch, capsys):
    write_quote(prepared)
    write_actual(prepared, lambda a: a["lines"][3].update(count=999))
    assert cart(prepared, monkeypatch, "actual") == 0
    assert "not written: SMT assembly: the order counts 999, edakit " in capsys.readouterr().out
    own = json.loads((prepared.root / "hardware" / "fees" / "jlcpcb.json").read_text())
    assert "economic_smt_joint" not in own["pcba"] and "economic_setup" in own["pcba"]


def test_a_value_not_on_the_page_writes_nothing(prepared, monkeypatch, capsys):
    write_actual(prepared)
    d = order_dir(prepared)
    (d / "actual_page.txt").write_text((d / "actual_page.txt").read_text().replace("Y8-1234567A", ""))
    assert cart(prepared, monkeypatch, "actual") == 2
    assert "FAIL ORDER.read read, not made up: not in the page text: Y8-1234567A" in capsys.readouterr().out
    assert not (prepared.root / "hardware" / "fees" / "jlcpcb.json").exists()


def test_the_invoice_saved_as_html(prepared, monkeypatch, tmp_path):
    a = write_actual(prepared)
    _, page = actual_of(job(prepared))
    invoice = tmp_path / "invoice.html"
    invoice.write_text("<html><body><table>" + "".join(f"<tr><td>{line}</td></tr>" for line in page.splitlines())
                       + "</table><script>var x = 'Y9-0';</script></body></html>")
    assert cart(prepared, monkeypatch, "actual", "--from", str(invoice)) == 0
    text = (order_dir(prepared) / "actual_page.txt").read_text()
    assert a["order_number"] in text and "<td>" not in text and "Y9-0" not in text


def test_the_record_gets_the_order_number_and_the_totals(prepared, monkeypatch):
    q = write_quote(prepared)
    review(prepared)
    subtotal = round(sum(p["amount"] for p in q["prices"] if p["kind"] != "shipping"), 2)
    (order_dir(prepared) / "cart.json").write_text(json.dumps({"name": "gerber_main", "quantity": 5,
                                                               "price": subtotal}))
    assert cart(prepared, monkeypatch, "check", "--cart") == 0
    write_actual(prepared)
    assert cart(prepared, monkeypatch, "actual") == 0
    r = json.loads(next((prepared.root / "hardware" / "orders").glob("*.json")).read_text())
    assert r["order_number"] == "Y8-1234567A" and r["actual"]["quote"] == subtotal and r["actual"]["currency"] == "USD"


def test_what_the_live_runs_found_in_the_comparison():
    """Live runs 5.7 and 5.12 (2026-11-01): JLCPCB shows "60 x 28 mm" for edakit's "60.00 x 28.00 mm" and names only
    the Gerber upload, as the project gerber_main; PCBWay takes the files in the cart and shows them there."""
    from edakit import cart as c
    assert c.norm("60.00 x 28.00 mm") == c.norm("60 x 28 mm") and c.norm("1.0") == c.norm("1") != c.norm("10")
    files = [{"name": n, "size": 1000} for n in ("gerber_main.zip", "bom_main.csv", "cpl_main.csv")]
    jlc = {"files": files, "maker": {"unshown": ["bom", "cpl"]}}
    assert c.uploads_shown(jlc, [{"name": "gerber_main"}]) == []
    assert c.uploads_shown({**jlc, "maker": {}}, [{"name": "gerber_main"}]) == [
        "bom_main.csv: not among the uploads the page shows", "cpl_main.csv: not among the uploads the page shows"]
    way = {"files": files, "maker": {"upload": "after_cart"}}
    assert c.uploads_shown(way, [{"name": n, "size": "1 KB"} for n in ("gerber_main.zip", "bom_main.csv",
                                                                         "cpl_main.csv")]) == []
    assert c.uploads_shown(way, [{"name": "gerber_old.zip"}]) == [
        "gerber_main.zip: not among the uploads the page shows", "bom_main.csv: not among the uploads the page shows",
        "cpl_main.csv: not among the uploads the page shows", "gerber_old.zip: uploaded, but no file of the job"]


def test_a_cart_line_named_by_its_size():
    """PCBWay names a cart line "2 Layers Size 60x28mm 1.6mm" – the job's size names the board (live run 5.12)."""
    from edakit import cart as c
    job = {"board": "main", "quantity": 5, "files": [{"name": "gerber_main.zip"}],
           "fields": [{"key": "size_mm", "value": "60.00 x 28.00 mm"}]}
    quote = {"prices": [{"amount": 6.5, "kind": "pcb"}, {"amount": 29.0, "kind": "fee"}]}
    assert c.check_cart(job, quote, {"name": "2 Layers Size 60x28mm 1.6mm", "quantity": 5, "price": 35.5})[0] == []
    assert c.check_cart(job, quote, {"name": "2 Layers Size 50x28mm 1.6mm", "quantity": 5, "price": 35.5})[0] == [
        "the cart line '2 Layers Size 50x28mm 1.6mm' names neither the board nor a file of the job"]


def test_a_cart_line_with_its_vat_apart():
    """Eurocircuits' configurator quotes gross, its basket line shows the net price and the VAT apart (live run 5.8):
    the cart line's price with its VAT is the quote's."""
    from edakit import cart as c
    job = {"board": "main", "quantity": 5, "files": [{"name": "gerber_main.zip"}], "fields": []}
    quote = {"prices": [{"amount": 82.26, "kind": "pcb"}, {"amount": 220.68, "kind": "fee"},
                        {"amount": 23.82, "kind": "parts"}, {"amount": 54.46, "kind": "vat"}]}
    line = {"name": "gerber_main", "quantity": 5, "price": 272.30, "vat": 54.46, "currency": "EUR"}
    assert c.check_cart(job, quote, line)[0] == []
    assert c.check_cart(job, quote, {**line, "vat": None})[0] == ["price 272.3 in the cart, 326.76 in the quote"]
    assert c.check_cart(job, quote, {**line, "vat": 50.0})[0] == [
        "price 272.3 (VAT 50.0 apart) in the cart, 326.76 in the quote"]


def test_the_customs_description_in_the_job(project, monkeypatch, capsys):
    """[order] customs: the job carries JLCPCB's "Product Description" in its words, to set and read back – another
    entry on the page fails ORDER.form. Without the key the field is one the skill only reads: the owner chooses it."""
    released(project, lambda ex, p: fr.ordered(ex, p, {"customs": {"category": "DIY", "hs_code": "902300"}}))
    assert cart(project, monkeypatch, "prepare") == 0
    f = next(f for f in job(project)["fields"] if f["key"] == "customs")
    assert (f["label"], f["value"], f.get("read")) == (
        "Product Description", "Reserch\\Education\\DIY\\Entertainment / DIY - HS Code 902300", None)
    assert "Product Description: Reserch\\Education\\DIY\\Entertainment / DIY - HS Code 902300" in capsys.readouterr().out
    write_quote(project, lambda q: next(x for x in q["fields"] if x["label"] == "Product Description").update(
        value="Reserch\\Education\\DIY\\Entertainment / Development Board - HS Code 847330"))
    assert cart(project, monkeypatch, "check") == 2
    assert "Product Description: the page" in results(project)["ORDER.form"][1]

    shutil.rmtree(project.config().reports)
    released(project, fr.ordered)
    assert cart(project, monkeypatch, "prepare") == 0
    f = next(f for f in job(project)["fields"] if f["key"] == "customs")
    assert (f["value"], f["read"]) == ("–", True)


def test_aisler_as_the_live_run_read_it():
    """Live run 5.10 (2026-11-01, tests/fixtures/makers/aisler/live_2026-11-01): with the parts' MPN in the ODB++
    AISLER assigned every part of the release by "mpn"; the form of /checkout and the Assembly tab are the job's
    fields, the project overview is in the profile's ignore – ORDER.form passes; R1 and R2 out of stock at AISLER stop
    the order at ORDER.parts, as they must."""
    from edakit import cart as c
    d = Path(__file__).parent / "fixtures" / "makers" / "aisler" / "live_2026-11-01"
    job, quote = (json.loads((d / f).read_text()) for f in ("job.json", "quote.json"))
    assert job["match"] == "mpn" and c.b1(job, quote)[0] == []
    assert c.b2(job, quote)[0] == ["0805W8F7503T5E R1: Out of Stock", "0805W8F2000T5E R2: Out of Stock"]


def test_aisler_up_to_the_price():
    """Live run 5.10, its end (2026-11-01, tests/fixtures/makers/aisler/live_2026-11-01/price): R1 and R2 swapped in the
    throwaway copy for YAGEO parts AISLER stocks, released again – every part assigned by "mpn" or by the release's
    manufacturer, /checkout at Amazing Assembly, quantity 5, €348.03 net; ORDER.form, ORDER.parts and the review pass,
    and the skill stops before "Continue to Checkout" (AISLER has no cart)."""
    from edakit import cart as c
    d = Path(__file__).parent / "fixtures" / "makers" / "aisler" / "live_2026-11-01" / "price"
    job, quote = (json.loads((d / f).read_text()) for f in ("job.json", "quote.json"))
    assert c.b1(job, quote)[0] == [] and c.b2(job, quote)[0] == []
    assert job["maker"]["cart"] is None and "Continue to Checkout" in job["maker"]["never"]
    assert (d / "regulatory.md").read_text().rstrip().endswith("Order: OK")


def test_eurocircuits_as_the_live_run_read_it():
    """Live run 5.8 (2026-11-01, tests/fixtures/makers/eurocircuits/live_2026-11-01): with the header Eurocircuits'
    import maps by itself the BOM's nine lines were identified by MPN; every field the configurator showed is the
    job's or in the profile's ignore as edakit ships it now, and every value is in the page text read."""
    from edakit import cart as c
    d = Path(__file__).parent / "fixtures" / "makers" / "eurocircuits" / "live_2026-11-01"
    job, quote = (json.loads((d / f).read_text()) for f in ("job.json", "quote.json"))
    assert job["match"] == "mpn" and c.b1(job, quote)[0] == [] and c.b2(job, quote)[0] == []
    assert c.b4(quote, (d / "quote_page.txt").read_text())[0] == []
    ignore = {c.norm(k) for k in makers.load("eurocircuits").data["ignore"]}
    known = ignore | {c.norm(f["label"]) for f in job["fields"]}
    assert [q["label"] for q in quote["fields"] if c.norm(q["label"]) not in known] == []


# --- the review of the ordering documentation (2026-11-01, the owner's word) -------------------------------------------

def test_a_failed_order_read_leaves_the_order_record_alone(prepared, monkeypatch):
    """ORDER.read failed on the order page: nothing of it is a value – neither the fee table nor the order record takes
    the order number and the totals."""
    q = write_quote(prepared)
    review(prepared)
    subtotal = round(sum(p["amount"] for p in q["prices"] if p["kind"] != "shipping"), 2)
    (order_dir(prepared) / "cart.json").write_text(json.dumps({"name": "gerber_main", "quantity": 5,
                                                               "price": subtotal}))
    assert cart(prepared, monkeypatch, "check", "--cart") == 0
    write_actual(prepared)
    d = order_dir(prepared)
    (d / "actual_page.txt").write_text((d / "actual_page.txt").read_text().replace("Y8-1234567A", ""))
    assert cart(prepared, monkeypatch, "actual") == 2
    r = json.loads(next((prepared.root / "hardware" / "orders").glob("*.json")).read_text())
    assert r["order_number"] is None and r["actual"] is None


def test_the_job_names_the_manufacturer_of_every_part(prepared):
    """AISLER lists an MPN more than once (another manufacturer, "Partner Stock"): the skill assigns the line of the
    release's manufacturer, so the job carries it – from the parts entry, the file the maker matches by aside."""
    from edakit.design import Design
    design = Design.from_config(prepared.config())
    lines = job(prepared)["bom"]
    assert lines and all(p["manufacturer"] == design.part(p["designators"][0])["manufacturer"] for p in lines)


def test_the_budget_without_a_fee_table(prepared):
    """A maker without a fee table has no estimate – the board total of its quote is still held to [cost] budget, in
    [cost] currency through [cost] rates; without a rate for the quote's currency it is named, not compared."""
    from edakit import cart as c
    d = Path(__file__).parent / "fixtures" / "makers" / "aisler" / "live_2026-11-01" / "price"
    j, q = (json.loads((d / f).read_text()) for f in ("job.json", "quote.json"))
    assert j["estimate"] is None
    warn, actual = c.b3({**j, "budget": {"amount": 300.0, "currency": "USD", "rates": {"USD": 1.0, "EUR": 1.15}}}, q)
    assert warn == ["board total 400.23 USD above the budget of 300.00 ([cost] budget)"]
    warn, actual = c.b3({**j, "budget": {"amount": 500.0, "currency": "USD", "rates": {"USD": 1.0, "EUR": 1.15}}}, q)
    assert warn == [] and "budget 500.00 USD" in actual
    warn, actual = c.b3({**j, "budget": {"amount": 300.0, "currency": "USD", "rates": {"USD": 1.0}}}, q)
    assert warn == [] and "budget not compared: [cost] rates has no rate for EUR" in actual


def test_prepare_writes_the_budget_into_the_job(project, monkeypatch, capsys):
    released(project, fr.ordered)
    toml(project, '[cost]\nbudget = 80.0\ncurrency = "EUR"\nrates = { USD = 0.9 }')
    assert cart(project, monkeypatch, "prepare") == 0
    assert job(project)["budget"] == {"amount": 80.0, "currency": "EUR", "rates": {"EUR": 1.0, "USD": 0.9}}


def test_an_aisler_order_gets_its_record_from_the_checkout_page():
    """AISLER has no cart: the saved project is the state, its page /checkout the line – project name, quantity, net
    price and VAT apart. Read into cart.json, edakit cart check --cart holds it to the job and the quote and writes the
    order record; another quantity fails."""
    from edakit import cart as c
    d = Path(__file__).parent / "fixtures" / "makers" / "aisler" / "live_2026-11-01" / "price"
    j, q = (json.loads((d / f).read_text()) for f in ("job.json", "quote.json"))
    line = {"name": "Sandbox / odb_main", "quantity": 5, "price": 348.03, "vat": 66.13, "currency": "EUR"}
    assert c.check_cart(j, q, line)[0] == []
    assert c.check_cart(j, q, {**line, "quantity": 10})[0] == ["quantity 10 in the cart, 5 in the job"]


def test_the_lead_finding_says_it_is_no_legal_advice():
    """ORDER.finish and FILES.order/lead name RoHS and REACH to the reader of check.md and the protocol: once, that it
    is support, not legal advice (CLAUDE.md, handbook 15)."""
    from edakit import cart as c
    for use in ("sale", "gift"):
        assert c.lead(["HASL(with lead)"], {"use": use})[1].endswith("(handbook 15.2 – support, not legal advice)")


# --- compare ---------------------------------------------------------------------------------------------------------

THREE = ('[cart]\nmakers = ["jlcpcb", "eurocircuits", "aisler"]\nship_to = "DE"\n'
         'shipping = { jlcpcb = "DHL Express", eurocircuits = "UPS", aisler = "DHL" }')


def other_maker(project, key, name, currency, change):
    """A second maker's job as prepare writes it – the planned maker's job with this maker – and a quote of it as the
    skill would bring it back, changed by change; returns the order folder."""
    j = job(project)
    jo = dict(j, maker=dict(j["maker"], key=key, name=name, currency=currency, role="other"), estimate=None)
    d = order_dir(project, key)
    d.mkdir(parents=True)
    (d / "job.json").write_text(json.dumps(jo, indent=1))
    q, page = quote_of(j, change)
    q["maker"] = key
    (d / "quote.json").write_text(json.dumps(q, indent=1))
    (d / "quote_page.txt").write_text(page)
    return d


def test_compare_puts_every_makers_quote_side_by_side(project, monkeypatch, capsys):
    """The quotes of every maker of [cart] makers for the board of the current release side by side: the board total in
    the quote's currency and, through [cost] rates, in [cost] currency; the lines a maker marked; the lead time as
    read; whether edakit cart check passed on this very quote. The lowest board total is named, the table goes to
    cart/compare.md – and a maker without a job or a quote is named with what to do."""
    released(project, fr.ordered, cart=THREE)
    toml(project, "[cost]\nbudget = 200\nrates = { EUR = 1.10 }")
    assert cart(project, monkeypatch, "prepare") == 0
    jl = write_quote(project)
    review(project)
    assert cart(project, monkeypatch, "check") == 0
    jl_total = sum(p["amount"] for p in jl["prices"] if p["kind"] in ("pcb", "fee", "parts"))

    def euro(q):
        q.update(currency="EUR", lead_time="10 working days",
                 prices=[{"label": "PCB", "amount": 400.0, "kind": "pcb"},
                         {"label": "Assembly", "amount": 300.0, "kind": "fee"},
                         {"label": "Components", "amount": 50.0, "kind": "parts"}])
        q["parts"][0]["mark"] = "out of stock"
    other_maker(project, "eurocircuits", "Eurocircuits", "EUR", euro)
    first = job(project)["bom"][0]
    capsys.readouterr()

    assert cart(project, monkeypatch, "compare") == 0
    out = capsys.readouterr().out
    rows = {line.split()[0]: line for line in out.splitlines()
            if line[:1].strip() and line.split()[0] in ("JLCPCB", "Eurocircuits", "AISLER")}
    assert f"{jl_total:.2f} USD" in rows["JLCPCB"] and "3-4 days" in rows["JLCPCB"] and "passed" in rows["JLCPCB"]
    assert "750.00 EUR" in rows["Eurocircuits"] and "825.00 USD" in rows["Eurocircuits"]
    assert "10 working days" in rows["Eurocircuits"] and "not checked" in rows["Eurocircuits"]
    assert "1 of" in rows["Eurocircuits"]
    assert any(first["part"] in line and line.rstrip().endswith(": out of stock") for line in out.splitlines())
    assert "no job – edakit cart prepare --maker aisler" in rows["AISLER"]
    assert f"lowest board total: JLCPCB, {jl_total:.2f} USD" in out
    md = (order_dir(project).parent / "compare.md").read_text()
    assert "| Eurocircuits |" in md and "out of stock" in md and "nothing ordered" in md


def test_compare_names_a_check_of_an_older_quote(project, monkeypatch, capsys):
    """A check.json of another quote.json than the one in the folder is no check of this quote."""
    released(project, fr.ordered)
    assert cart(project, monkeypatch, "prepare") == 0
    write_quote(project)
    review(project)
    assert cart(project, monkeypatch, "check") == 0
    write_quote(project, lambda q: q.update(lead_time="5 days"), lambda page: page.replace("3-4 days", "5 days"))
    capsys.readouterr()
    assert cart(project, monkeypatch, "compare") == 0
    row = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("JLCPCB"))
    assert "5 days" in row and "not checked (the quote changed)" in row


def test_a_bare_board_at_jlcpcb_as_the_live_run_read_it():
    """Live run of 2026-11-01 (tests/fixtures/makers/jlcpcb/bare_2026-11-01, the bell's THT variant): a bare board goes
    from JLCPCB's quote page straight to "SAVE TO CART" – no Quote & Order, so no "Product Description" (the job
    asks it at checkout) and no upload's name on the page (unshown_bare: the cart line names the Gerber,
    gerber_tht_Y11); "PCB Assembly" and "Stencil" are off and in the profile's ignore."""
    from edakit import cart as c
    d = Path(__file__).parent / "fixtures" / "makers" / "jlcpcb" / "bare_2026-11-01"
    job, quote, line = (json.loads((d / f).read_text()) for f in ("job.json", "quote.json", "cart.json"))
    customs = next(f for f in job["fields"] if f["key"] == "customs")
    assert job["bom"] == [] and customs.get("checkout") and customs.get("read")
    assert c.b1(job, quote)[0] == [] and c.b4(quote, (d / "quote_page.txt").read_text())[0] == []
    assert c.uploads_shown(job, quote["files"]) == [] and "gerber" in job["maker"]["unshown"]
    assert c.check_cart(job, quote, line)[0] == []
    ignore = {c.norm(k) for k in makers.load("jlcpcb").data["ignore"]}
    assert {c.norm("PCB Assembly"), c.norm("Stencil")} <= ignore


def test_a_field_asked_only_with_assembly():
    """fields.<key>.assembly: true or false, nothing else."""
    assert makers.problems("x", {"fields": {"customs": {"assembly": True}}}) == []
    assert makers.problems("x", {"fields": {"customs": {"assembly": "yes"}}}) == [
        "maker x: fields.customs: assembly must be true or false"]
    assert makers.problems("x", {"unshown_bare": ["gerber"]}) == []
    assert makers.problems("x", {"unshown_bare": ["schematic"]})[0].startswith("maker x: unshown_bare: unknown file")


# --- edakit cart confirm (ordering step 5) -----------------------------------------------------------------------------

def confirm_of(j, change=None):
    """confirm.json as the skill reads the maker's confirmation pages after the order – the production file as released,
    the placement as the maker's engineer adjusted it with every part of the job's BOM, D1 (a diode: on the polarity
    sheet) with its pin 1 and sign – and the page text it kept."""
    parts = [{"designator": d, "part": p["part"]} for p in j["bom"] for d in p["designators"]]
    for x in parts:
        if x["designator"] == "D1":
            x.update(pin1="left pad (magenta dot)", sign="+ at the right pad", ok=True)
    c = {"maker": j["maker"]["key"], "read": "2026-11-02T08:40:00+01:00",
         "production_file": {"asked": True, "renders": ["top", "bottom"], "as_released": True, "notes": []},
         "placement": {"asked": True, "side": "top", "assembled": len(parts), "unassembled": 0, "parts": parts,
                       "dfm": [], "notes": []}}
    if change:
        change(c)
    pl = c["placement"]
    page = "\n".join(["Confirm Product Detail", "Top", "Bottom", "Yes, please proceed to production",
                      f"Assembled ({pl['assembled']})", f"Unassembled ({pl['unassembled']})",
                      *(f"{x['designator']} {x.get('part', '')} top SMT Assembly Yes" for x in pl["parts"])])
    return c, page


def write_confirm(project, change=None, page_change=None):
    c, page = confirm_of(job(project), change)
    d = order_dir(project)
    (d / "confirm.json").write_text(json.dumps(c, indent=1))
    (d / "confirm_page.txt").write_text(page_change(page) if page_change else page)
    return c


def confirm_results(project):
    return {r["id"]: (r["result"], r["actual"]) for r in json.loads((order_dir(project) / "confirm_check.json").read_text())[
        "results"]}


def m2(project):
    s = json.loads(project.config().signoff.read_text())
    return next(m for m in s["manual"] if m["id"] == "M-2"), s


def test_confirm_checks_the_makers_pages_and_signs_m2_on_the_owners_word(prepared, monkeypatch, capsys):
    """Ordering step 5: the production file as released, every part of the BOM in the maker's placement with its part
    number, every polarised part of the polarity sheet read with pin 1 and sign and found right. The sign-off is the
    owner's word: --sign writes M-2 for the job's fab hash, the parts in its note."""
    write_confirm(prepared)
    assert cart(prepared, monkeypatch, "confirm") == 0
    got = confirm_results(prepared)
    assert {k: v[0] for k, v in got.items()} == {"ORDER.read": "pass", "ORDER.parts": "pass", "ORDER.confirm": "pass"}
    assert "D1" in got["ORDER.confirm"][1]
    assert m2(prepared)[0]["done_by"] is None and "M-2 open" in capsys.readouterr().out
    assert cart(prepared, monkeypatch, "confirm", "--sign", "the owner (skill cart)", "--note",
                "requirements met: R-7") == 0
    m, s = m2(prepared)
    assert m["done_by"] == "the owner (skill cart)" and m["date"] == dt.date.today().isoformat()
    assert m["note"].startswith(f"M-2: OK for fab {job(prepared)['fab_sha256']}") and "D1 pin 1 left pad" in m["note"]
    assert m["note"].endswith("requirements met: R-7") and s["fab_sha256"] == job(prepared)["fab_sha256"]
    md = (order_dir(prepared) / "confirm.md").read_text()
    assert "| ORDER.confirm" in md and "M-2 signed" in md


@pytest.mark.parametrize("change, page_change, expected", [
    (lambda c: next(x for x in c["placement"]["parts"] if x["designator"] == "D1").update(
        ok=False, note="cathode at the + pad"), None, ("ORDER.confirm", "fail", "D1: cathode at the + pad")),
    (lambda c: c["placement"]["parts"].remove(next(x for x in c["placement"]["parts"] if x["designator"] == "D1")),
     None, ("ORDER.parts", "fail", "C8678 D1: not in the maker's placement")),
    (lambda c: next(x for x in c["placement"]["parts"] if x["designator"] == "D1").pop("pin1"), None,
     ("ORDER.confirm", "fail", "D1: pin 1 not read")),
    (lambda c: next(x for x in c["placement"]["parts"] if x["designator"] == "C2").update(part="C999"), None,
     ("ORDER.parts", "fail", "C45783 C2: the maker's placement has C999")),
    (lambda c: c["placement"].update(assembled=3), None, ("ORDER.confirm", "fail", "3 parts assembled, the job places 2")),
    (lambda c: c["production_file"].update(as_released=False, notes=["the bottom render lacks the version line"]),
     None, ("ORDER.confirm", "fail", "production file: the bottom render lacks the version line")),
    (None, lambda page: page.replace("D1 C8678", "C8678"), ("ORDER.read", "fail", "not in confirm_page.txt: D1")),
])
def test_each_finding_of_the_confirmation(prepared, monkeypatch, change, page_change, expected):
    write_confirm(prepared, change, page_change)
    assert cart(prepared, monkeypatch, "confirm", "--sign", "the owner") == 2
    cid, result, text = expected
    got = confirm_results(prepared)[cid]
    assert got[0] == result and text in got[1], got
    assert m2(prepared)[0]["done_by"] is None            # nothing is signed on a failed check


def test_confirm_needs_the_pages_and_the_runs_fab_hash(prepared, monkeypatch, capsys):
    assert cart(prepared, monkeypatch, "confirm") == 1
    assert "confirm.json is not there" in capsys.readouterr().err
    write_confirm(prepared)
    s = json.loads(prepared.config().signoff.read_text())
    s["fab_sha256"] = "0" * 64                            # M-5 of the file is bound to another run's files
    prepared.config().signoff.write_text(json.dumps(s, indent=1))
    assert cart(prepared, monkeypatch, "confirm", "--sign", "the owner") == 1
    assert "bound to fab 000000000000" in capsys.readouterr().err


def test_after_a_newer_release_the_orders_run_holds_the_job(prepared, monkeypatch):
    """The order was placed against its run: confirm and actual take that run's job – found through the order record –
    when the current release has none."""
    q = write_quote(prepared)
    review(prepared)
    d = order_dir(prepared)
    subtotal = round(sum(p["amount"] for p in q["prices"] if p["kind"] != "shipping"), 2)
    (d / "cart.json").write_text(json.dumps({"name": "gerber_main", "quantity": 5, "price": subtotal,
                                             "currency": "USD"}))
    assert cart(prepared, monkeypatch, "check", "--cart") == 0
    cfg = prepared.config()
    man = json.loads((cfg.reports / RUN / "fab" / "manifest.json").read_text())
    later = cfg.reports / "20261031-120000"
    shutil.copytree(cfg.reports / RUN / "fab" / "main", later / "fab" / "main")
    shutil.rmtree(later / "fab" / "main" / "cart")
    gate.write_manifest(cfg, later, {**man, "time": "20261031-120000", "git_commit": "abc", "git_dirty": False},
                        "RELEASED")
    assert gate.current(cfg)[0] == "20261031-120000"
    write_confirm(prepared)
    assert cart(prepared, monkeypatch, "confirm") == 0
    write_actual(prepared)
    assert cart(prepared, monkeypatch, "actual") == 0


def test_the_profiles_confirm_table():
    """[confirm] of a profile: what the maker asks for after the order, each entry a string; the job carries it."""
    good = {"page": "https://x/orders", "production_file": "a dialog", "placement": "a second window",
            "viewer": "/smt/dfm-result", "pin1": "a dot", "anode": "a +"}
    assert makers.problems("x", {"confirm": good}) == []
    assert makers.problems("x", {"confirm": {**good, "popup": "yes"}})[0].startswith("maker x: confirm must be a table of")
    assert makers.problems("x", {"confirm": {"page": ""}})[0].startswith("maker x: confirm must be a table of")
    assert makers.load("jlcpcb").data["confirm"]["placement"].startswith("Confirm Parts Placement")


def test_an_order_without_a_number(prepared, monkeypatch):
    """A project that keeps order numbers out of its repository: actual.json without one – ORDER.read has one value
    less, the fee table's source and actual.md say 'the order'."""
    write_quote(prepared)
    write_actual(prepared, lambda a: a.update(order_number=None))
    assert cart(prepared, monkeypatch, "actual") == 0
    own = json.loads((prepared.root / "hardware" / "fees" / "jlcpcb.json").read_text())
    assert own["pcba"]["economic_setup"]["source"] == "the order at JLCPCB, 2026-11-02 (edakit cart actual)"
    assert (order_dir(prepared) / "actual.md").read_text().startswith("# Real cost – board main at JLCPCB, the order (")
