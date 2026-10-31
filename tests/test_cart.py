"""Ordering step 4 (docs/concepts/done/ordering.md): `edakit cart prepare` writes the job of the skill cart from the
current release, `edakit cart check` holds what the skill brought back – quote.json and the page text – to the job,
the release and the page (ORDER.form to ORDER.review), `--cart` checks the cart line and writes the order record. On recorded data:
the example's export of test_fab_run, released, and a quote and page text as the skill would write them."""

import json
import shutil
import zipfile

import pytest

import test_fab_run as fr
from edakit import cli, cost
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
            "state_sha256": gate.state_hash(cfg), "layout_sha256": gate.layout_hash(cfg)}
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
    assert {f["label"]: f["value"] for f in j["fields"]}["Mark on PCB"] == "Order Number (Specify Position)"
    assert [(p["part"], p["designators"]) for p in j["bom"]] == [("C45783", ["C2"]), ("C8678", ["D1"])]
    assert j["dnp"] == [] and j["purpose"]["use"] == "private" and j["estimate"]["currency"] == "USD"
    assert "C8678" in j["compliance"]
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
    """The placeholder warns for Eurocircuits as the second maker – the release stands for JLCPCB, the order at
    Eurocircuits stops on it."""
    released(project, fr.ordered, cart='[cart]\nmakers = ["jlcpcb", "eurocircuits"]\nship_to = "DE"\n'
                                       'shipping = { jlcpcb = "DHL Express", eurocircuits = "UPS" }')
    assert cart(project, monkeypatch, "prepare", "--maker", "eurocircuits") == 1
    err = capsys.readouterr().err
    assert "has findings for Eurocircuits, which it did not plan the board for" in err and "JLCJLCJLCJLC" in err
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
    (lambda q: next(f for f in q["fields"] if f["label"] == "Mark on PCB").update(value="Remove Mark"), None,
     ("ORDER.form", "fail", "Mark on PCB: the page 'Remove Mark', the job 'Order Number (Specify Position)'")),
    (lambda q: q["fields"].append({"label": "Stencil", "value": "No"}), None,
     ("ORDER.form", "fail", "Stencil: a field neither in the job nor in the profile's ignore – the maker added a question")),
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
                   {"label": "Total", "amount": 40.0, "kind": "total"}]}
    if change:
        change(a)
    page = "\n".join([a["order_number"], *(f"{x['label']} ${x['amount']:.2f}" + (f" ({x['count']} joints)"
                                                                                 if x.get("count") else "")
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
