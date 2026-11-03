"""The order at the maker: what edakit prepares for the skill cart and checks of what it brings back (handbook 8.4).

    edakit cart fields  [--board B] [--maker M]          every field of the maker's form: value, where it comes from
    edakit cart prepare [--board B] [--maker M]          the job of the skill cart, from the current release
    edakit cart check   [--board B] [--maker M] [--cart] ORDER.form to ORDER.review on what the skill brought back; --cart: the cart line
    edakit cart confirm [--board B] [--maker M] [--sign BY] [--note T]   the maker's confirmations after the order (M-2)
    edakit cart actual  [--board B] [--maker M] [--from FILE]   the real cost of the order
    edakit cart compare [--board B]                      the quotes of every maker of [cart] makers side by side

The skill cart (Claude in Chrome, in the owner's browser) fills the maker's form from the job and stops at the maker's
cart button – it never orders and never pays. edakit is deterministic and knows the release; Claude reads and fills
pages that change. Nothing Claude brings back counts until `edakit cart check` has checked it against the job, the
release and the page text Claude kept. The files of an order live next to the upload files of the released run:

    <reports>/<run>/fab/<board>/cart/<maker>/
        job.json          the job: run, hashes, board, maker, the upload files with SHA-256, the fields of the form in
                          the maker's words, the expected BOM, the parts not to place, the estimate, the compliance
        quote.json        written by the skill: the fields, parts and price lines as read on the page
        quote_page.txt    the page text of the form, the matching and the quote, as read
        screens/          screenshots of the filled form, the matching and the placement preview (M-2)
        regulatory.md     the agent regulatory-reviewer on the order, unchanged (ORDER.review)
        check.md          the result of edakit cart check
        cart.json         the cart line as read back after the cart button (--cart)
        confirm.json, confirm_page.txt, confirm.md, confirm_check.json   what the maker asked to confirm after the
                          order, as the skill read it, and edakit cart confirm's result; --sign writes M-2
        actual.json, actual_page.txt, actual.md   the real cost after the owner ordered and paid
    <reports>/<run>/fab/<board>/cart/compare.md       edakit cart compare: every maker's quote side by side

After the order, confirm and actual read the order's run: the current release's job, or – when a newer release has
none for the board at the maker – the job of the run the order record names, which the order was placed against.

Exit codes: 0 = ok, 2 = findings (the order stops), 1 = error; edakit cart check 3 = ORDER.form to ORDER.finish passed, the regulatory
review of the order (ORDER.review) is open.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

from . import makers
from .design import Design, natural_key

JOB, QUOTE, PAGE, SCREENS = "job.json", "quote.json", "quote_page.txt", "screens"
REVIEW, CHECK, CHECK_JSON, CART = "regulatory.md", "check.md", "check.json", "cart.json"
COMPARE = "compare.md"
ACTUAL, ACTUAL_PAGE, ACTUAL_MD = "actual.json", "actual_page.txt", "actual.md"
CONFIRM, CONFIRM_PAGE, CONFIRM_MD, CONFIRM_CHECK = "confirm.json", "confirm_page.txt", "confirm.md", "confirm_check.json"
ORDERS = Path("hardware") / "orders"   # the order records, versioned, outside every hash
CHECKS = {"ORDER.form": "form = job", "ORDER.parts": "parts = release", "ORDER.quote": "quote against the estimate",
          "ORDER.read": "read, not made up", "ORDER.files": "the same files", "ORDER.finish": "lead in the finish",
          "ORDER.review": "regulatory review of this order",
          "ORDER.confirm": "the maker's confirmations as released and as the sheet"}
NEVER = ("Order", "Buy", "Checkout", "Pay", "Submit order", "Place order")   # the skill's fixed list, besides the profile's
GRADES = ("block", "important", "note")
OK_LINE, NOT_OK_LINE = "Order: OK", "Order: not OK"


class CartError(Exception):
    pass


def sha_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def norm(text):
    """For comparing what a page shows with the job: case and blanks ignored, a number's trailing zeros too (JLCPCB
    shows "60 x 28 mm" for edakit's "60.00 x 28.00 mm")."""
    t = re.sub(r"\s+", "", str(text)).casefold()
    return re.sub(r"(\d)\.(?!\d)", r"\1", re.sub(r"(\d\.\d*?)0+(?!\d)", r"\1", t))


def kind_of(name):
    """The kind of an upload file by its name (makers.UPLOAD): gerber, bom, bom_mpn, cpl, odb."""
    n = str(name)
    return "bom_mpn" if n.startswith("bom_") and n.endswith("_mpn.csv") else n.split("_", 1)[0]


def folder(cfg, run, board, maker):
    """Where the files of an order live: next to the upload files of the run, one folder per maker."""
    return cfg.reports / run / "fab" / board / "cart" / maker


def maker_of(cfg, key=None):
    """The profile of a maker of [cart] makers (default the planned one); CartError for another maker."""
    key = key or makers.planned(cfg)
    if key not in makers.listed(cfg):
        raise CartError(f"maker {key} is not in [cart] makers ({', '.join(makers.listed(cfg))}) – add it there; "
                        "its checks and files are then in the next gate run")
    return makers.get(cfg, key)


def run_folder(cfg, board):
    """(run, the board's folder of it, what it is) – the current release, else the newest gate run with the board's
    manufacturing files; (None, None, why) without one."""
    from .release import gate
    cur = gate.current(cfg)
    if cur and (cfg.reports / cur[0] / "fab" / board).is_dir():
        return cur[0], cfg.reports / cur[0] / "fab" / board, "current release"
    for run in sorted((p.parent.parent.name for p in cfg.reports.glob(f"*/fab/{board}/gerber")), reverse=True):
        return run, cfg.reports / run / "fab" / board, "newest gate run, not released"
    return None, None, "no gate run yet"


def fields(cfg, args):
    from .release import order_sheet
    board = cfg.board(args.board, made=True)
    m = maker_of(cfg, args.maker)
    run, d, what = run_folder(cfg, board.name)
    design = Design.from_config(cfg)
    out = order_sheet.form(cfg, design, board, d if d is not None else cfg.reports / "-", m)
    role = "the planned maker" if m.key == makers.planned(cfg) else "not the planned maker"
    print(f"board {board.name} at {m.name} ({role}; profile {'recorded ' + m.recorded if m.recorded else 'provisional'})"
          + (f", Gerber facts from run {run} ({what})" if run else f" – {what}: layers and size not known"))
    section = None
    for f in out:
        if f["section"] != section:
            section = f["section"]
            print(section)
        src = f["from"] if run or f["key"] not in ("layers", "size_mm") else "no gate run yet"
        key = f"{f['key']} = {f['raw']!r}" if f["raw"] is not None and f["key"] not in order_sheet.DERIVED else f["key"]
        print(f"  {f['label']:<25} {order_sheet.field_text(f):<27} {src:<12} {key}")
    left = [k for k in order_sheet.FORM if not m.has(k)]
    if left:
        print(f"not on {m.name}'s form (left out of its job): {', '.join(left)}")
    return 0


# --- edakit cart prepare --------------------------------------------------------------------------------------------

def bom_of(d, board, m, design):
    """The expected parts: [{part, designators, comment, manufacturer}] – by the key the maker matches by (LCSC number
    or MPN), from the run's BOM file for the maker (bom_<b>_mpn.csv for a maker that matches by MPN, else bom_<b>.csv);
    the manufacturer from that file, else the parts entry – the line to assign where a maker lists an MPN twice."""
    import csv
    match = m.matches_by or "lcsc"
    path = d / (f"bom_{board}_mpn.csv" if match == "mpn" and (d / f"bom_{board}_mpn.csv").exists() else f"bom_{board}.csv")
    out = []
    if path.exists():
        with open(path, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                refs = [x.strip() for x in re.split(r"[,\s]+", r.get("Designator", "")) if x.strip()]
                entry = (design.part(refs[0]) if refs else None) or {}
                part = r.get("Manufacturer Part Number") if match == "mpn" else r.get("LCSC Part #")
                if match == "mpn" and not part:
                    lcsc = r.get("LCSC Part #") or entry.get("lcsc")
                    part = (design.parts.get(lcsc) or {}).get("mpn")
                out.append({"part": part or "", "designators": sorted(refs, key=natural_key),
                            "comment": r.get("Value", r.get("Comment", "")),
                            "manufacturer": r.get("Manufacturer") or entry.get("manufacturer") or ""})
    return out, match, path.name


def not_placed(design, board, m):
    """The board's parts not to place (bom: false) – listed in the job where the maker's files still hold them
    (ODB++); a maker whose files leave them out (dnp = "omit") gets none to mark."""
    if m.data.get("dnp") == "omit":
        return []
    return sorted((d for d, c in design.board_comps(board).items() if c.get("bom") is False), key=natural_key)


def estimate_of(cfg, board, m):
    """The estimate of edakit cost for the board without shipping, in the fee table's currency; None (and why) for a
    maker without a fee table."""
    from . import cost
    try:
        est = cost.estimate(cfg, board, maker=m.key)
    except cost.CostError as e:
        return None, str(e)
    b = est["boards"][board]
    fees = cost.load_fee_table(cfg, m.key)
    cur, rate = cost.converter(cfg, fees)
    return {"currency": fees["currency"], "class": b["class"], "pcb": b["pcb"]["amount"], "pcb_how": b["pcb"]["how"],
            "pcb_size_mm": b["pcb"]["size_mm"], "not_in_price": b.get("not_in_price", {}),
            "fees": [{k: f[k] for k in ("key", "item", "amount", "count", "area_cm2") if k in f} for f in b["fees"]],
            "fees_total": b["fees_total"], "parts_total": b["parts_total"], "unpriced": b["unpriced"],
            "total": b["total"], "fee_table": fees.get("date"), "budget": (cfg.cost or {}).get("budget"),
            "budget_currency": cur, "rate": rate(fees["currency"])}, ""


def combine_of(cfg, design, m):
    """The combined shipment for the job (docs/concepts/done/parts-order.md, decision 5): when a supplier's profile
    combines with this maker and the project's basket has lines of that supplier – LCSC's warehouse address, the
    conditions, the weight above which only express is left; None otherwise."""
    from . import order
    prof = order.supplier("lcsc")
    c = (prof or {}).get("combine")
    if not c or c["maker"] != m.key:
        return None
    path = cfg.artifacts / "order" / order.BASKET
    try:
        if path.exists():
            n, src = len(json.loads(path.read_text(encoding="utf-8"))["suppliers"].get("lcsc") or []), cfg.relative(path)
        else:
            n, src = len(order.carts(cfg, design)[0].get("lcsc", [])), "this project's parts (edakit order writes the basket)"
    except order.OrderError as e:
        raise CartError(str(e)) from None
    if not n:
        return None
    needed = makers.of(cfg).get("needed_by")
    return {"supplier": "lcsc", "name": prof["name"], "lines": n, "basket": str(src), "page": c["page"],
            "read": c["read"], "address": order.address(c), "conditions": list(c.get("conditions", [])),
            "express_above_g": c.get("express_above_g"), "needed_by": needed.isoformat() if needed else None}


def prepare(cfg, args):
    """The job of the skill cart for one board at one maker, from the current release – or why there is none."""
    from .release import gate, order_sheet
    board = cfg.board(args.board, made=True)
    m = maker_of(cfg, args.maker)
    cur = gate.current(cfg)
    if cur is None:
        raise CartError("no current release – edakit gate --eda releases a run (edakit release current)")
    run, man = cur
    d = cfg.reports / run / "fab" / board.name
    if not d.is_dir():
        raise CartError(f"the current release {run} has no board {board.name}")
    names = m.upload(board.name)
    lost = [n for n in names if not (d / n).exists()]
    if lost:
        raise CartError(f"run {run} has no {', '.join(lost)} – {m.name} takes them; the gate writes the files of every "
                        "maker of [cart] makers (edakit gate --eda)")
    _, found = gate.verify(cfg, [d / n for n in names])                      # 2. release verify, the same function
    if bad := [f"{f.name}: {what}" for f, ok, what in found if not ok]:
        raise CartError("the files are not the current release's – " + "; ".join(bad))
    if gate.state_hash(cfg) != man.get("state_sha256"):
        raise CartError(f"the circuit changed since run {run} (circuit hash) – the order is placed against the run: a "
                        "new gate run first, or the working tree back to the release")
    if gate.layout_hash(cfg) != man.get("layout_sha256"):
        raise CartError(f"the layout changed since run {run} (layout hash: the board files, [order] among them) – a new "
                        "gate run first, or the working tree back to the release")
    settings, ran = order_sheet.settings(board), d / order_sheet.SETTINGS
    if (json.loads(ran.read_text(encoding="utf-8")) if ran.exists() else None) != settings:
        raise CartError(f"the order settings that change the board differ from run {run}'s {order_sheet.SETTINGS} "
                        "([order] of edakit.toml?) – a new gate run first")
    head = {k: man.get(k) for k in ("state_sha256", "layout_sha256", "fab_sha256")}
    head["electrical_sha256"] = man.get("electrical_sha256") or gate.electrical_hash(cfg)   # the files are the run's
    signoff, _ = gate.load_signoff(cfg, head)                                   # 3. M-6 for the run's circuit hash
    m6 = next((x for x in signoff.get("manual", []) if x.get("id") == "M-6"), None)
    if not (m6 and m6.get("done_by")):
        raise CartError(f"M-6, the regulatory review, is not signed for the circuit hash of run {run} – the order is "
                        "placed against the run")
    seen = cfg.reports / run / gate.MAKERS                                     # 4. the run's checks for this maker
    checked = json.loads(seen.read_text(encoding="utf-8")) if seen.exists() else {}
    if m.key not in checked:
        raise CartError(f"run {run} did not check {m.name} – [cart] makers at the gate run held "
                        f"{', '.join(checked) or 'jlcpcb only'}; a new gate run with it")
    if checked[m.key]["role"] == "other" and checked[m.key]["findings"]:
        rows = "; ".join(f"{r['id']} {r['check']}: {r['actual']}" for r in checked[m.key]["findings"][:6])
        raise CartError(f"run {run} has findings for {m.name}, which it did not plan the board for: {rows} – plan the "
                        "board for it ([cart] maker) and run the gate, or settle them")
    c = makers.of(cfg)
    if not c.get("ship_to"):
        raise CartError("[cart] ship_to is not set – the country the order goes to; the skill sets every field of the "
                        "job and none it was not given")
    if not c["shipping"].get(m.key):
        raise CartError(f"[cart] shipping names no method for {m.key} – e.g. shipping = {{ {m.key} = \"…\" }}")
    design = Design.from_config(cfg)
    o = order_sheet.order_of(cfg, board)
    form = order_sheet.form(cfg, design, board, d, m)
    bom, match, bom_file = bom_of(d, board.name, m, design)
    estimate, why = estimate_of(cfg, board.name, m) if m.data.get("fees") else (None, f"{m.name} has no fee table")
    money = cfg.cost or {}
    budget = None if money.get("budget") is None else {           # ORDER.quote, with or without a fee table
        "amount": float(money["budget"]), "currency": money.get("currency", "USD"),
        "rates": {money.get("currency", "USD"): 1.0, **{k: float(v) for k, v in (money.get("rates") or {}).items()}}}
    keys = {(design.entry_key(r) or "") for p in bom for r in p["designators"] if r in design.comps}
    job = {
        "made": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "run": run, "fab_sha256": man.get("fab_sha256"), "state_sha256": man.get("state_sha256"),
        "layout_sha256": man.get("layout_sha256"), "purpose": design.graph.get("purpose"),
        "board": board.name, "title": board.title, "project": cfg.project,
        "maker": {"key": m.key, "name": m.name, "profile": str(m.path), "recorded": m.recorded, "start":
                  m.data.get("start"), "cart": m.data.get("cart"),
                  "never": list({w.casefold(): w for w in reversed([*NEVER, *m.data.get("never", [])])}.values())[::-1],
                  "ignore": m.data.get("ignore", {}),
                  "unshown": [*m.data.get("unshown", []), *([] if bom else m.data.get("unshown_bare", []))],
                  "upload": m.data.get("upload", "before_cart"), "matching": m.data.get("matching", "page"),
                  "seat": m.seat, "currency": m.currency, "compliance": m.data.get("compliance"),
                  "confirm": m.data.get("confirm"),
                  "role": "planned" if m.key == makers.planned(cfg) else "other"},
        "quantity": o["quantity"] if o else cfg.quantity, "pcba_quantity": o["pcba_quantity"] if o else cfg.quantity,
        "files": [{"name": n, "path": str((d / n).resolve()), "size": (d / n).stat().st_size, "sha256": sha_of(d / n)}
                  for n in names],
        "fields": form, "bom": bom, "match": match, "bom_file": bom_file,
        "dnp": not_placed(design, board.name, m),
        "estimate": estimate, "estimate_why": why, "budget": budget,
        "compliance": {k: design.parts[k].get("compliance") for k in sorted(keys, key=natural_key) if k in design.parts},
        "ship_to": c["ship_to"], "shipping": c["shipping"][m.key], "tolerance": c["tolerance"],
        "combine": combine_of(cfg, design, m),
    }
    out = folder(cfg, run, board.name, m.key)
    out.mkdir(parents=True, exist_ok=True)
    (out / JOB).write_text(json.dumps(job, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    show_job(cfg, job, out)
    return 0


def show_job(cfg, job, out):
    m = job["maker"]
    print(f"job for board {job['board']} at {m['name']} – run {job['run']}, fab {str(job['fab_sha256'])[:12]}…, "
          f"{job['quantity']} PCBs, " + (f"{job['pcba_quantity']} assembled" if job.get("bom") else "bare"))
    print(f"  folder   {cfg.relative(out)}  (job.json sha256 {sha_of(out / JOB)[:16]}…)")
    print(f"  start    {m['start'] or '– (the profile names no start page: ordering step 0)'}")
    for f in job["files"]:
        print(f"  upload   {f['name']}  {f['size']} bytes  sha256 {f['sha256'][:16]}…  {f['path']}")
    section = None
    for f in job["fields"]:
        if f["section"] != section:
            section = f["section"]
            print(f"  {section}")
        shown = f["value"] + (f"  ({f['note']})" if f.get("note") else "")
        print(f"    {f['label']}: " + (f"{shown} – at checkout, the owner's" if f.get("checkout") else
                                       "read, set nothing" + (f" ({f['note']})" if f.get("note") else "")
                                       if f.get("read") else shown))
    print(f"  parts    {len(job['bom'])} lines by {job['match']}: "
          + "; ".join(f"{p['part']} {','.join(p['designators'])}" for p in job["bom"][:8])
          + (" …" if len(job["bom"]) > 8 else ""))
    print(f"  not to place  {', '.join(job['dnp']) or '–'}")
    e = job["estimate"]
    print("  estimate " + (f"{e['total']:.2f} {e['currency']} without shipping (PCB {e['pcb'] or 0:.2f}, fees "
                           f"{e['fees_total']:.2f}, parts {e['parts_total']:.2f})" if e else f"– {job['estimate_why']}"))
    print(f"  shipping {job['shipping']} to {job['ship_to']}")
    print(f"  cart     press only \"{m['cart'] or '– (not recorded: stop before the cart)'}\"; never "
          + ", ".join(m["never"]) + " – no address, payment method or coupon"
          + (f" (but {job['combine']['name']}'s warehouse, below, on the owner's choice)" if job.get("combine") else ""))
    if k := job.get("combine"):
        print(f"  combine  the basket has {k['lines']} {k['name']} line{'s' if k['lines'] != 1 else ''} ({k['basket']}): "
              f"one parcel if this order goes to {k['name']}'s warehouse – the owner's choice before the checkout, after "
              f"both carts' weights (edakit order check); it buys speed, not a lower price")
        print(f"           the address, from {k['page']} (read {k['read']}) – entered at the checkout and read back, "
              "nothing else there:")
        for label, value in k["address"].items():
            print(f"             {label}: {value}")
        print("           " + "; ".join(k["conditions"]))
        print(f"           after the owner paid: the order page shows the warehouse; then at {k['name']}'s checkout the "
              f"order ticked to combine, its methods read into shipping.json – stop before its order button"
              + (f"; cheapest arriving by {k['needed_by']}" if k.get("needed_by") else ""))


# --- edakit cart check ------------------------------------------------------------------------------------------------

def has_lead(finish):
    """A surface finish with lead: HASL that is not lead-free."""
    f = norm(finish)
    return "hasl" in f and not any(w in f for w in ("leadfree", "lead-free", "pbfree", "rohs"))


def page_has(page, value):
    """value occurs in the page text – a word or number on its own, case and repeated blanks ignored."""
    v = re.sub(r"\s+", " ", str(value)).strip()
    if not v:
        return True
    text = re.sub(r"\s+", " ", page)
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(v) + r"(?![A-Za-z0-9])", text, re.I) is not None


def amount_text(a):
    return f"{float(a):.2f}"


def designators(v):
    return sorted((x for x in (re.split(r"[,\s]+", v) if isinstance(v, str) else v) if x), key=natural_key)


SIZE = re.compile(r"([\d.,]+)\s*(B|KB|KiB|MB|MiB|bytes?)?\s*$", re.I)


def size_fits(shown, size):
    """A size the page shows ("12.3 KB") against the file's bytes: within the rounding of its last digit, in units of
    1000 or 1024."""
    m = SIZE.match(str(shown).strip())
    if not m:
        return False
    value, unit = float(m.group(1).replace(",", ".")), (m.group(2) or "B").lower()
    digits = len(m.group(1).split(".")[1]) if "." in m.group(1) else 0
    step = 10 ** -digits
    for base in (1000, 1024):
        factor = {"b": 1, "byte": 1, "bytes": 1, "kb": base, "kib": 1024, "mb": base ** 2, "mib": 1024 ** 2}[unit]
        if abs(value * factor - size) <= (step / 2 + 1e-9) * factor + 1:
            return True
    return False


def b1(job, quote):
    """Form = job: every field of the job read back with its value, the parts not to place marked; no field of the page
    that is neither in the job nor in the profile's ignore."""
    got = {norm(q.get("label", "")): q.get("value") for q in quote.get("fields", [])}
    wanted = [f for f in job["fields"] if not f.get("read")]
    lost = [f["label"] for f in wanted if norm(f["label"]) not in got]
    other = [f"{f['label']}: the page {got[norm(f['label'])]!r}, the job {f['value']!r}" for f in wanted
             if norm(f["label"]) in got and norm(got[norm(f["label"])]) != norm(f["value"])]
    known = {norm(f["label"]) for f in job["fields"]} | {norm(k) for k in job["maker"].get("ignore", {})}
    added = [q.get("label", "") for q in quote.get("fields", []) if norm(q.get("label", "")) not in known]
    marks = []
    if job.get("dnp"):
        shown = set(designators(quote.get("dnp", [])))
        if shown != set(job["dnp"]):
            marks.append(f"parts marked not to place {', '.join(sorted(shown, key=natural_key)) or 'none'}, the job "
                         f"{', '.join(job['dnp'])}")
    bad = [*(f"{x}: not read back" for x in lost), *other, *(f"{x}: a field neither in the job nor in the profile's "
                                                              "ignore – the maker added a question" for x in added), *marks]
    return bad, f"{len(wanted)} fields as the job says" + (f", {len(job['dnp'])} parts marked not to place"
                                                           if job.get("dnp") else "")


def b2(job, quote):
    """Parts = release: the maker's lines are the job's BOM – same part numbers, same designators, none marked. A maker
    that matches the BOM only in its review after the cart (matching = "review", PCBWay) shows no lines before it."""
    want = {p["part"]: designators(p["designators"]) for p in job["bom"]}
    if job["maker"].get("matching") == "review" and not quote.get("parts"):
        return [], (f"{len(want)} lines – {job['maker']['name']} matches the BOM in its review after the cart; the "
                    "parts it buys show on the order page (edakit cart actual)")
    got = {p.get("part", ""): designators(p.get("designators", [])) for p in quote.get("parts", [])}
    bad = [f"{k} {','.join(v)}: not in the maker's matching" for k, v in want.items() if k not in got]
    bad += [f"{k} {','.join(v)}: in the maker's matching, not in the BOM of the release" for k, v in got.items()
            if k not in want]
    bad += [f"{k}: the maker places {','.join(got[k])}, the release {','.join(v)}" for k, v in want.items()
            if k in got and got[k] != v]
    bad += [f"{p.get('part')} {','.join(designators(p.get('designators', [])))}: {p['mark']}"
            for p in quote.get("parts", []) if p.get("mark")]
    return bad, f"{len(want)} lines, {sum(len(v) for v in want.values())} parts as the release"


def board_lines(quote):
    """The price lines of the board (PCB, assembly fees, parts) – shipping, VAT and the totals belong to the order."""
    return [p for p in quote.get("prices", []) if p.get("kind") in ("pcb", "fee", "parts")]


def b3(job, quote):
    """The quote against the estimate: per kind of line (PCB, assembly fees, parts) and the board total; above
    [cart] tolerance per line a warning with both values. The board total against [cost] budget – without an estimate
    (a maker without a fee table, a quote in another currency) through the job's budget and [cost] rates."""
    e, tol, warn, info = job.get("estimate"), float(job.get("tolerance", makers.TOLERANCE)), [], []
    lines = board_lines(quote)
    kinds = {k: [p for p in lines if p["kind"] == k] for k in ("pcb", "fee", "parts")}
    total = round(sum(float(p["amount"]) for p in lines), 2)
    if e is None:
        info.append(f"no estimate – {job.get('estimate_why', 'the maker has no fee table')}")
    elif quote.get("currency") and quote["currency"] != e["currency"]:
        info.append(f"the quote is in {quote['currency']}, the estimate in {e['currency']} – not compared")
        e = None
    if e is not None:
        for kind, label, est in (("pcb", "PCB", e["pcb"] or 0), ("fee", "assembly fees", e["fees_total"]),
                                 ("parts", "parts", e["parts_total"])):
            got = round(sum(float(p["amount"]) for p in kinds[kind]), 2)
            if abs(got - est) > tol * max(1, len(kinds[kind])) + 1e-9:
                warn.append(f"{label}: quote {got:.2f}, estimate {est:.2f} {e['currency']}")
        budget = e.get("budget")
        if budget is not None and total * e["rate"] > budget + 1e-9:
            warn.append(f"board total {total * e['rate']:.2f} {e['budget_currency']} above the budget of "
                        f"{budget:.2f} ([cost] budget)")
    b = job.get("budget")
    if e is None and b:                       # no estimate to compare with: the board total against the budget alone
        cur = quote.get("currency") or job["maker"].get("currency")
        rate = (b.get("rates") or {}).get(cur)
        if rate is None:
            info.append(f"budget not compared: [cost] rates has no rate for {cur}")
        elif total * rate > b["amount"] + 1e-9:
            warn.append(f"board total {total * rate:.2f} {b['currency']} above the budget of {b['amount']:.2f} "
                        "([cost] budget)")
        else:
            info.append(f"budget {b['amount']:.2f} {b['currency']}")
    actual = f"board {total:.2f} {quote.get('currency', '')}".rstrip() + (
        f", estimate {e['total']:.2f} {e['currency']}" if e is not None else "")
    return warn, actual + ("; " + "; ".join(info) if info else "")


def b4(quote, page):
    """Read, not made up: every value of quote.json occurs in the page text Claude kept."""
    values = [*(q.get("value") for q in quote.get("fields", [])), *(p.get("part") for p in quote.get("parts", [])),
              *(r for p in quote.get("parts", []) for r in designators(p.get("designators", []))),
              *(amount_text(p["amount"]) for p in quote.get("prices", []) if p.get("amount") is not None),
              *(f.get("name") for f in quote.get("files", [])), quote.get("lead_time")]
    values = [v for v in values if v not in (None, "")]
    lost = list(dict.fromkeys(str(v) for v in values if not page_has(page, v)))
    return [f"not in {PAGE}: " + ", ".join(lost[:12]) + (f" and {len(lost) - 12} more" if len(lost) > 12 else "")] \
        if lost else [], f"{len(values)} values, each in {PAGE}"


def b5(cfg, job, quote, cart=None):
    """The same files: the SHA-256 of the upload files is still that of the job and of the manifest, and the names –
    and sizes where the page shows them – of the uploads are the job's. At a maker whose files go up in the cart
    (upload = "after_cart") the names come with the cart line (cart.json files), and before it only the hashes count."""
    from .release import gate
    cur = gate.current(cfg)
    files = (cur[1].get("files", {}) if cur and cur[0] == job["run"] else {})
    bad = []
    if not cur or cur[0] != job["run"]:
        bad.append(f"run {job['run']} is not the current release any more ({cur[0] if cur else 'none'})")
    for f in job["files"]:
        p = Path(f["path"])
        if not p.exists():
            bad.append(f"{f['name']}: gone")
            continue
        now = sha_of(p)
        if now != f["sha256"]:
            bad.append(f"{f['name']}: changed since the job")
        rel = f"fab/{job['board']}/{f['name']}"
        if files and files.get(rel) != now:
            bad.append(f"{f['name']}: not the file of the manifest")
    after = job["maker"].get("upload") == "after_cart"
    if after and cart is None:
        return bad, f"{len(job['files'])} files, SHA-256 of the job and the manifest – they go up in the cart"
    bad += uploads_shown(job, (cart or {}).get("files", []) if after else quote.get("files", []))
    return bad, f"{len(job['files'])} files, SHA-256 of the job and the manifest"


def uploads_shown(job, files):
    """The uploads a page shows ([{name, size}]) against the job's files: a name without its extension is the same
    upload; a kind the profile says the page names nowhere (unshown) is held by its hash alone."""
    bad = []
    stem = lambda n: norm(Path(str(n)).stem if Path(str(n)).suffix else n)   # noqa: E731 – gerber_main = gerber_main.zip
    shown = {stem(f.get("name", "")): f for f in files}
    unshown = set(job["maker"].get("unshown", []))           # kinds of upload the maker's page names nowhere
    for f in job["files"]:
        q = shown.get(stem(f["name"]))
        if q is None:
            if kind_of(f["name"]) not in unshown:
                bad.append(f"{f['name']}: not among the uploads the page shows")
        elif q.get("size") and not size_fits(q["size"], f["size"]):
            bad.append(f"{f['name']}: the page shows {q['size']}, the file has {f['size']} bytes")
    names = {stem(f["name"]) for f in job["files"]}
    bad += [f"{f.get('name')}: uploaded, but no file of the job" for f in files if stem(f.get("name", "")) not in names]
    return bad


def b6(job, quote):
    """Lead in the finish of the job or on the page (lead)."""
    finish = next((f for f in job["fields"] if f["key"] == "finish"), None)
    read = next((q.get("value") for q in quote.get("fields", []) if finish and norm(q.get("label", "")) ==
                 norm(finish["label"])), None)
    return lead([str(x) for x in (finish and finish.get("raw"), finish and finish.get("value"), read) if x],
                job.get("purpose"))


def lead(words, purpose):
    """Lead in the finish, graded by purpose – ORDER.finish at the cart, FILES.order/lead at the release: sale, or no
    purpose, fails (RoHS), gift warns (REACH Art. 33), private is a note. -> (pass|fail|warn|info, text)"""
    use = ((purpose or {}).get("use") or "sale") if isinstance(purpose, dict) else "sale"
    if not any(has_lead(w) for w in words):
        return "pass", f"{words[0] if words else 'no finish'}: no lead"
    level = {"sale": "fail", "gift": "warn"}.get(use, "info")
    return level, (f"{words[-1]}: lead in the product, purpose {use} – " + {
        "sale": "RoHS: lead above 0.1 % is not allowed in what is placed on the market (handbook 15.2 – support, not "
                "legal advice)",
        "gift": "lead is a substance of very high concern: REACH Art. 33 asks to name it to a consumer who asks "
                "(handbook 15.2 – support, not legal advice)",
        "private": "for yourself: a note (handbook 15.1)"}[use if use in ("sale", "gift") else "private"])


def review_of(path):
    """(verdict line, numbered findings [{n, grade}], text) of regulatory.md; None when it is not there."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    found = [{"n": int(m.group(1)), "grade": m.group(2).lower()} for ln in lines
             if (m := re.match(r"(\d+)\.\s+\**(block|important|note)\b", ln, re.I))]
    return (lines[-1] if lines else ""), found, text


def b7(out):
    """The regulatory review of this order: regulatory.md names the SHA-256 of job.json and quote.json as they are
    now and ends with "Order: OK"."""
    got = review_of(out / REVIEW)
    if got is None:
        return "open", f"{REVIEW} not there – the agent regulatory-reviewer on the order (skill cart, step 8)"
    last, found, text = got
    stale = [n for n in (JOB, QUOTE) if sha_of(out / n) not in text]
    if stale:
        return "fail", f"{REVIEW} names another {' and '.join(stale)} than the one now there – review it again"
    if last == OK_LINE:
        return "pass", f"{REVIEW}: {len(found)} findings, {OK_LINE}"
    return "fail", f"{REVIEW}: " + (last if last == NOT_OK_LINE else f"last line {last!r}, not {OK_LINE!r}")


def check_cart(job, quote, cart):
    """With --cart: the cart line names the job's board (its name, a file's, or – where the maker names a line by its
    specification, PCBWay's "2 Layers Size 60x28mm 1.6mm" – its size) and quantity, and the quote's price within
    [cart] tolerance – the line's price, or with its VAT where the line shows it apart (vat; Eurocircuits quotes
    gross and shows the basket line net)."""
    tol, lines = float(job.get("tolerance", makers.TOLERANCE)), board_lines(quote)
    subtotal = round(sum(float(p["amount"]) for p in lines), 2)
    names = [job["board"]] + [Path(f["name"]).stem for f in job["files"]]
    names += [f["value"].removesuffix(" mm").replace(" ", "") + "mm" for f in job["fields"] if f.get("key") == "size_mm"
              and f.get("value") not in (None, "–")]
    bad = []
    if not any(norm(n) in norm(cart.get("name", "")) for n in names):
        bad.append(f"the cart line {cart.get('name')!r} names neither the board nor a file of the job")
    if cart.get("quantity") != job["quantity"]:
        bad.append(f"quantity {cart.get('quantity')} in the cart, {job['quantity']} in the job")
    price, vat = cart.get("price"), cart.get("vat")
    seen = [] if price is None else [float(price)] + ([float(price) + float(vat)] if vat is not None else [])
    if all(abs(p - subtotal) > tol * max(1, len(lines)) + 1e-9 for p in seen):
        apart = f" (VAT {vat} apart)" if vat is not None else ""
        bad.append(f"price {price}{apart} in the cart, {subtotal:.2f} in the quote")
    return bad, f"{cart.get('name')}: {cart.get('quantity')} at {price} {cart.get('currency', '')}".rstrip()


def evaluate(cfg, out, job, quote, page, cart=None):
    """ORDER.form to ORDER.review: [(id, result, actual)]; cart: the cart line read back (--cart)."""
    res = []
    for cid, (bad, ok_text) in (("ORDER.form", b1(job, quote)), ("ORDER.parts", b2(job, quote))):
        res.append((cid, "fail" if bad else "pass", "; ".join(bad) if bad else ok_text))
    warn, actual = b3(job, quote)
    res.append(("ORDER.quote", "warn" if warn else "pass", "; ".join(warn) + " – " + actual if warn else actual))
    for cid, (bad, ok_text) in (("ORDER.read", b4(quote, page)), ("ORDER.files", b5(cfg, job, quote, cart))):
        res.append((cid, "fail" if bad else "pass", "; ".join(bad) if bad else ok_text))
    res.append(("ORDER.finish", *b6(job, quote)))
    res.append(("ORDER.review", *b7(out)))
    return res


def write_check(out, job, quote, res, cart=None):
    """check.md and check.json of the order folder."""
    head = {"time": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "job_sha256": sha_of(out / JOB),
            "quote_sha256": sha_of(out / QUOTE)}
    rows = [{"id": c, "check": CHECKS.get(c, "cart line"), "result": r, "actual": a} for c, r, a in res]
    quote_ok = all(r["result"] != "fail" for r in rows if r["id"] in ("ORDER.form", "ORDER.parts", "ORDER.read", "ORDER.files"))
    done = {**head, "results": rows, "quote_ok": quote_ok,
            "passed": all(r["result"] in ("pass", "warn", "info") for r in rows)}
    (out / CHECK_JSON).write_text(json.dumps(done, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    word = {"pass": "passed", "fail": "FAILED", "warn": "warning", "info": "note", "open": "open"}
    L = [f"# Order check – board {job['board']} at {job['maker']['name']}, run {job['run']}\n",
         f"Written by edakit cart check at {head['time']}: what the skill cart brought back (quote.json, "
         f"{PAGE}) against the job, the release and the page text. job.json `{head['job_sha256']}`, quote.json "
         f"`{head['quote_sha256']}`.\n", "| Check | Result | Actual |", "|---|---|---|"]
    L += [f"| {r['id']} {r['check']} | {word.get(r['result'], r['result'])} | {r['actual']} |" for r in rows]
    L.append("\n" + ("Every check passed: the skill may press the maker's cart button."
                     if done["passed"] and cart is None else
                     "The cart line is the job's; the order record is written." if done["passed"] else
                     "The order stops here: nothing into the cart until the checks pass.") + "\n")
    (out / CHECK).write_text("\n".join(L), encoding="utf-8")
    return done


def record(cfg, out, job, quote, cart, done):
    """The order record hardware/orders/<date>-<board>-<maker>.json: run, hashes, board, maker, quantity, the
    regulatory verdict with the numbers and grades of its findings, the cart line – versioned, outside every hash."""
    last, found, _ = review_of(out / REVIEW)
    date = dt.date.today().isoformat()
    path = cfg.root / ORDERS / f"{date}-{job['board']}-{job['maker']['key']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"date": date, "run": job["run"], "fab_sha256": job["fab_sha256"], "state_sha256": job["state_sha256"],
            "board": job["board"], "maker": job["maker"]["key"], "quantity": job["quantity"],
            "pcba_quantity": job["pcba_quantity"], "job_sha256": done["job_sha256"], "quote_sha256": done["quote_sha256"],
            "regulatory": {"verdict": last, "findings": found},
            "quote": {"currency": quote.get("currency"), "board": round(sum(float(p["amount"]) for p in
                                                                          board_lines(quote)), 2)},
            "estimate": (job.get("estimate") or {}).get("total"),
            "cart": cart, "order_number": None, "actual": None}
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def ordered_run(cfg, board, maker):
    """The run of the newest order record of the board at the maker whose job is still there – the run the order was
    placed against; None without one."""
    for path in sorted((cfg.root / ORDERS).glob(f"*-{board}-{maker}.json"), reverse=True):
        try:
            run = json.loads(path.read_text(encoding="utf-8")).get("run")
        except (OSError, json.JSONDecodeError):
            continue
        if run and (folder(cfg, run, board, maker) / JOB).exists():
            return run
    return None


def load_order(cfg, args, need=(QUOTE, PAGE), ordered=False):
    """(board, maker, folder, job, the files of need) of the current release's order; CartError when one is missing.
    ordered: after the order (confirm, actual) – when the current release has no job for the board at the maker, the
    run the order record names, which the order was placed against."""
    from .release import gate
    board = cfg.board(args.board, made=True)
    m = maker_of(cfg, args.maker)
    cur = gate.current(cfg)
    if cur is None:
        raise CartError("no current release")
    out = folder(cfg, cur[0], board.name, m.key)
    if ordered and not (out / JOB).exists() and (run := ordered_run(cfg, board.name, m.key)):
        out = folder(cfg, run, board.name, m.key)
    if not (out / JOB).exists():
        raise CartError(f"no job for board {board.name} at {m.name} in run {cur[0]} – edakit cart prepare first")
    job = json.loads((out / JOB).read_text(encoding="utf-8"))
    got = []
    for n in need:
        if not (out / n).exists():
            raise CartError(f"{cfg.relative(out / n)} is not there – the skill cart writes it")
        got.append(json.loads((out / n).read_text(encoding="utf-8")) if n.endswith(".json") else
                   (out / n).read_text(encoding="utf-8"))
    return board, m, out, job, got


# --- edakit cart confirm -----------------------------------------------------------------------------------------------

M2_TEXT = ("At the maker after the order: the placement as its engineer adjusted it – rotation and polarity of every "
           "polarised part (polarity_<board>.png); the BOM without missing parts; the production file as released")


def polarised(cfg, job):
    """The designators of the job's BOM that are on the polarity sheet (FILES.sheet): the parts edakit cart confirm
    expects read in the maker's placement."""
    from .release.polarity import is_polar
    design = Design.from_config(cfg)
    return [d for line in job["bom"] for d in line["designators"] if is_polar(design.part(d) or {})]


def b4_confirm(confirm, page):
    """ORDER.read on the confirmations: every designator and part number of the placement and its counts in the page text."""
    pl = confirm.get("placement") or {}
    values = [*(x.get("designator") for x in pl.get("parts", [])), *(x.get("part") for x in pl.get("parts", [])),
              *(pl.get(k) for k in ("assembled", "unassembled"))]
    values = [v for v in values if v not in (None, "")]
    lost = list(dict.fromkeys(str(v) for v in values if not page_has(page, v)))
    return [f"not in {CONFIRM_PAGE}: {', '.join(lost[:12])}"] if lost else [], f"{len(values)} values, each in the page"


def b2_confirm(job, confirm):
    """ORDER.parts on the placement: every designator of the job's BOM in the maker's placement with the job's part
    number, none the job does not place."""
    shown = {x["designator"]: x for x in (confirm.get("placement") or {}).get("parts", []) if x.get("designator")}
    bad = []
    for line in job["bom"]:
        for d in designators(line["designators"]):
            x = shown.get(d)
            if x is None:
                bad.append(f"{line['part']} {d}: not in the maker's placement")
            elif norm(str(x.get("part") or "")) != norm(str(line["part"])):
                bad.append(f"{line['part']} {d}: the maker's placement has {x.get('part') or 'no part number'}")
    placed = {d for line in job["bom"] for d in line["designators"]}
    if extra := sorted(set(shown) - placed, key=natural_key):
        bad.append(f"in the maker's placement, not in the job: {', '.join(extra[:12])}")
    return bad, f"{len(placed)} parts, each with the job's part number"


def b8(job, confirm, polar):
    """ORDER.confirm: the production file as released where the maker asked for it (both renders seen), the placement's
    counts the job's, every polarised part of the sheet read with its pin 1 and judged right, no part judged wrong,
    no DFM finding."""
    bad, seen = [], []
    pf = confirm.get("production_file") or {}
    if pf.get("asked"):
        if not pf.get("as_released"):
            bad.append("production file: " + ("; ".join(pf.get("notes") or []) or "not as released"))
        if lost := [r for r in ("top", "bottom") if r not in [str(x).lower() for x in pf.get("renders", [])]]:
            bad.append(f"production file: the {' and '.join(lost)} render not seen")
    pl = confirm.get("placement") or {}
    placed = [d for line in job["bom"] for d in line["designators"]]
    if pl.get("asked", True):
        if pl.get("assembled") != len(placed):
            bad.append(f"{pl.get('assembled')} parts assembled, the job places {len(placed)}")
        if pl.get("unassembled"):
            bad.append(f"{pl['unassembled']} parts unassembled")
        shown = {x.get("designator"): x for x in pl.get("parts", [])}
        for d in polar:
            x = shown.get(d)
            if x is None:                       # ORDER.parts names it
                continue
            if x.get("ok") is False:
                bad.append(f"{d}: {x.get('note') or 'judged wrong'}")
            elif not x.get("pin1"):
                bad.append(f"{d}: pin 1 not read")
            elif x.get("ok") is not True:
                bad.append(f"{d}: read, not judged (ok)")
            else:
                seen.append(f"{d} pin 1 {x['pin1']}" + (f", {x['sign']}" if x.get("sign") else ""))
        bad += [f"{d}: {x.get('note') or 'judged wrong'}" for d, x in shown.items()
                if d not in polar and x.get("ok") is False]
        bad += [f"DFM: {w}" for w in pl.get("dfm") or []]
    text = ("production file as released; " if pf.get("asked") else "") + f"{len(placed)} parts placed, " \
        + (f"{len(polar)} polarised parts as the sheet: " + "; ".join(seen) if polar else "no polarised part")
    return bad, text


def sign_m2(cfg, job, confirm, found, by, extra):
    """M-2 into the sign-off file for the job's fab hash, signed by `by` – the owner's word –, its note what the check
    found; CartError when the file's fab sign-offs are bound to another run's files."""
    from .release import gate
    path = cfg.signoff
    s = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"manual": [], "accept": []}
    bound = s.get("fab_sha256")
    if not job.get("fab_sha256"):
        raise CartError(f"run {job['run']} has no fab hash (stage F) – M-2 is bound to the files the maker builds from")
    if bound and bound != job["fab_sha256"]:
        raise CartError(f"{path.name}: its sign-offs of scope 'fab' are bound to fab {bound[:12]}…, the order's run "
                        f"{job['run']} has fab {job['fab_sha256'][:12]}… – M-2 is signed for the order's files")
    s["fab_sha256"] = job["fab_sha256"]
    m = next((x for x in s.setdefault("manual", []) if x.get("id") == "M-2"), None)
    if m is None:
        m = {"id": "M-2", "phase": "order", "scope": "fab", "text": M2_TEXT, "done_by": None, "date": None, "note": None}
        s["manual"].append(m)
    note = (f"M-2: OK for fab {job['fab_sha256']} (run {job['run']}, order at {job['maker']['name']}, the pages read "
            f"{confirm.get('read')}). {found}." + (f" {extra}" if extra else ""))
    m.update(done_by=by, date=dt.date.today().isoformat(), note=note)
    gate.save_manifest(path, s, indent=2)
    return m


def confirm_check(cfg, args):
    """The maker's confirmations after the order, as the skill cart read them: ORDER.read, ORDER.parts and
    ORDER.confirm on confirm.json and its page text; with --sign and every check passed, M-2 into the sign-off file."""
    board, m, out, job, _ = load_order(cfg, args, need=(), ordered=True)
    for n in (CONFIRM, CONFIRM_PAGE):
        if not (out / n).exists():
            raise CartError(f"{cfg.relative(out / n)} is not there – the skill cart reads the maker's confirmation "
                            "pages into it (its mode confirm)")
    confirm = json.loads((out / CONFIRM).read_text(encoding="utf-8"))
    page = (out / CONFIRM_PAGE).read_text(encoding="utf-8")
    polar = polarised(cfg, job)
    res = []
    for cid, (bad, ok_text) in (("ORDER.read", b4_confirm(confirm, page)), ("ORDER.parts", b2_confirm(job, confirm)),
                                ("ORDER.confirm", b8(job, confirm, polar))):
        res.append((cid, "fail" if bad else "pass", "; ".join(bad) if bad else ok_text))
    passed = all(r != "fail" for _, r, _ in res)
    signed = sign_m2(cfg, job, confirm, res[2][2], args.sign, args.note) if passed and args.sign else None
    head = {"time": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "job_sha256": sha_of(out / JOB),
            "confirm_sha256": sha_of(out / CONFIRM)}
    rows = [{"id": c, "check": CHECKS[c], "result": r, "actual": a} for c, r, a in res]
    (out / CONFIRM_CHECK).write_text(json.dumps({**head, "results": rows, "passed": passed, "polarised": polar,
                                                 "signed": signed}, indent=1, ensure_ascii=False) + "\n",
                                     encoding="utf-8")
    word = {"pass": "passed", "fail": "FAILED"}
    status = (f"M-2 signed by {signed['done_by']} ({signed['date']}) in {cfg.relative(cfg.signoff)}: {signed['note']}"
              if signed else "M-2 open: the sign-off is the owner's word – edakit cart confirm --sign BY" if passed
              else "The confirmation stops here: nothing signed until the checks pass; a part judged wrong is "
                   "'Not good, modification needed' on the maker's page.")
    L = [f"# Confirmations after the order – board {job['board']} at {job['maker']['name']}, run {job['run']}\n",
         f"Written by edakit cart confirm at {head['time']}: what the skill cart read on the maker's confirmation pages "
         f"({CONFIRM}, {CONFIRM_PAGE}) against the job, the polarity sheet and the page text. job.json "
         f"`{head['job_sha256']}`, {CONFIRM} `{head['confirm_sha256']}`.\n", "| Check | Result | Actual |", "|---|---|---|",
         *(f"| {r['id']} {r['check']} | {word[r['result']]} | {r['actual']} |" for r in rows), "", status, ""]
    (out / CONFIRM_MD).write_text("\n".join(L), encoding="utf-8")
    for c, r, a in res:
        print(f"{'ok  ' if r == 'pass' else 'FAIL'} {c} {CHECKS[c]}: {a}")
    print(status if signed is None else f"M-2 signed by {signed['done_by']} ({signed['date']}) in "
                                        f"{cfg.relative(cfg.signoff)}")
    print(f"result: {cfg.relative(out / CONFIRM_MD)}")
    return 0 if passed else 2


# --- edakit cart actual ------------------------------------------------------------------------------------------------

PER_ORDER = {"setup": "{cls}_setup", "stencil": "{cls}_stencil", "hand soldering": "hand_soldering_labour",
             "bake": "bake", "large size": "large_size", "packing": "standard_packing"}
PER_UNIT = {"loading": "{cls}_loading", "smt joints": "{cls}_smt_joint", "manual joints": "manual_joint",
            "reflow joints": "reflow_joint", "x-ray": "xray"}


def page_text(path):
    """The text of a saved order page or invoice for ORDER.read: HTML without its tags, a PDF through pdftotext, text as is."""
    import html
    import shutil
    import subprocess
    p = Path(path)
    if not p.exists():
        raise CartError(f"{p}: not found")
    if p.suffix.lower() == ".pdf":
        if not shutil.which("pdftotext"):
            raise CartError(f"{p.name}: a PDF needs pdftotext (poppler-utils) – or save the order page as HTML")
        return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True, check=True).stdout
    text = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix.lower() in (".html", ".htm"):
        text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return text


def order_word(actual):
    """'order Y8-1234567A', or 'the order' where actual.json names no number (a project that keeps order numbers out of
    its repository)."""
    return f"order {actual['order_number']}" if actual.get("order_number") else "the order"


def b4_actual(actual, page):
    """ORDER.read on the real cost: the order number, every amount and every count of actual.json in the page text – an
    amount by its figure (a coupon's -10.00 on a page that prints -$10.00)."""
    values = [actual.get("order_number"), *(amount_text(abs(float(x["amount"]))) for x in [*actual.get("lines", []),
                                                                                            *actual.get("order", [])]
                                            if x.get("amount") is not None),
              *(x["count"] for x in actual.get("lines", []) if x.get("count") is not None)]
    values = [v for v in values if v not in (None, "")]
    lost = list(dict.fromkeys(str(v) for v in values if not page_has(page, v)))
    return [f"not in the page text: {', '.join(lost[:12])}"] if lost else [], f"{len(values)} values, each in the page"


def estimate_fees(job, key):
    """The estimate's fee lines of an actual line's key – "loading" all the loading lines, one per type."""
    fees = (job.get("estimate") or {}).get("fees", [])
    return [f for f in fees if f["key"] == key or (key == "loading" and f["key"].startswith("loading "))]


def fee_updates(job, actual, table):
    """What maps one to one onto the fee table: [(fee, entry or None, line text)] – a fee per order or per side its
    value, a fee per unit whose count on the order is edakit's count its value per unit, into the tier the count falls
    in; another count: nothing written, the line named with both counts. Values before coupons and discounts."""
    cls = (job.get("estimate") or {}).get("class", "economic")
    out = []
    for line in actual.get("lines", []):
        key = line.get("estimate")
        if line.get("kind") != "fee" or not key:
            continue
        mine = estimate_fees(job, key)
        if not mine:
            out.append((None, None, f"{line['label']}: no line {key!r} in the estimate – not written"))
            continue
        base = "loading" if key.startswith("loading") else key        # one type ("loading C2297") or all of them
        units = sum(int(f.get("count", 1)) for f in mine) if key == "loading" else int(mine[0].get("count", 1))
        name = (PER_ORDER.get(base) or PER_UNIT.get(base) or "").format(cls=cls)
        spec = table["pcba"].get(name)
        if spec is None:
            out.append((None, None, f"{line['label']}: {key} has no value of its own in the fee table – not written"))
            continue
        count = line.get("count", units if base in PER_ORDER or key != base else None)
        if count is None or int(count) != units:
            out.append((name, None, f"{line['label']}: the order counts {count if count is not None else 'nothing'}, "
                                    f"edakit {units} – the count is the finding, not the rate; not written"))
            continue
        amount = float(line["amount"])
        if key == "packing":
            amount -= spec.get("per_cm2", 0) * float(mine[0].get("area_cm2", 0))
            value = round(amount, 4)
        else:
            value = round(amount / units, 4)          # per unit, per side – a fee per order has one unit
        entry = {k: v for k, v in spec.items() if k not in ("value", "tiers", "date", "source", "read")}
        if "tiers" in spec:
            tiers = [list(t) for t in spec["tiers"]]
            hit = next((t for t in tiers if t[0] <= units <= t[1]), tiers[-1])
            hit[2] = value
            entry.update(tiers=tiers, read={"tier": hit[:2], "count": units})
        else:
            entry["value"] = value
        out.append((name, entry, f"{line['label']}: {name} {value:g}" + (f" (tier {entry['read']['tier'][0]}–"
                                                                          f"{entry['read']['tier'][1]})"
                                                                          if "read" in entry else "")))
    return out


def ordered_size(job):
    """The PCB size the maker priced, [w, h] mm: the estimate's – with the edge rails of its assembly class – for an
    order with parts to place; for a bare board, which gets no rails, the Gerber outline of the job's form (size_mm).
    The bell's tht (2026-11-02): estimated Standard with rails as 85 × 66 mm, ordered bare and priced as 85 × 56 mm."""
    e = job.get("estimate") or {}
    if job.get("bom"):
        return e.get("pcb_size_mm")
    f = next((x for x in job.get("fields", []) if x.get("key") == "size_mm"), None)
    m = re.match(r"\s*([\d.]+)\s*[x×]\s*([\d.]+)", str((f or {}).get("value", "")))
    return [float(m.group(1)), float(m.group(2))] if m else e.get("pcb_size_mm")


def write_fees(cfg, m, job, actual, updates, rows):
    """The project's fee table (cost.own_fee_path), created by the first order: the values that map one to one, each
    with the order as its source and the order's date; the PCB price for the size, quantity and board settings as a
    row of pcb.prices. A maker without a fee model: the order's lines kept as they are."""
    from . import cost
    path = cost.own_fee_path(cfg, m.key)
    own = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    source = f"{order_word(actual)} at {m.name}, {actual.get('date')} (edakit cart actual)"
    date = str(actual.get("date") or dt.date.today().isoformat())
    if not m.data.get("fees"):
        own.setdefault("orders", []).append({"order_number": actual.get("order_number"), "date": date,
                                             "board": job["board"], "lines": actual.get("lines", [])})
        own.setdefault("about", f"Real costs of {m.name} from the owner's orders, as read (edakit cart actual); no fee "
                                "model prices them yet.")
        written = ["the order's lines kept (no fee model for this maker)"]
    else:
        shipped = cost.load_fee_table(cfg, m.key)
        own.setdefault("assembler", shipped.get("assembler", m.name))
        own.setdefault("currency", shipped["currency"])
        own.setdefault("about", f"The project's fee table for {m.name}: values from its own orders, written by edakit "
                                "cart actual; edakit cost takes per fee the value with the newest date from this table "
                                "or the shipped one.")
        own.setdefault("pcba", {})
        written = []
        for name, entry, text in updates:
            if entry is not None:
                own["pcba"][name] = {**entry, "date": date, "source": source}
                written.append(text)
        e, pcb = job.get("estimate") or {}, [x for x in actual.get("lines", []) if x.get("kind") == "pcb"]
        size = ordered_size(job)
        if pcb and size and job["quantity"] == shipped["pcb"]["qty"] and not e.get("not_in_price"):
            price = round(sum(float(x["amount"]) for x in pcb), 2)
            own.setdefault("pcb", {"qty": shipped["pcb"]["qty"], "prices": []})
            own["pcb"]["prices"] = [x for x in own["pcb"]["prices"] if sorted((x["w_mm"], x["h_mm"])) != sorted(size)]
            own["pcb"]["prices"].append({"w_mm": size[0], "h_mm": size[1], "value": price, "date": date,
                                         "source": source})
            written.append(f"PCB {size[0]:g} × {size[1]:g} mm, {job['quantity']} boards: {price:.2f}")
        elif pcb:
            rows.append(f"PCB: not written – {'another quantity than the table prices' if size and job['quantity'] != shipped['pcb']['qty'] else 'board settings the table does not price' if e.get('not_in_price') else 'no size'}")
    own["date"] = max(str(own.get("date", "")), date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(own, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path, written


def actual_cost(cfg, args):
    """The real cost after the owner ordered and paid: ORDER.read on it, actual.md – estimate, quote and actual line by line,
    per order shipping, VAT and coupon against [cost] –, the project's fee table one to one, the order record."""
    board, m, out, job, _ = load_order(cfg, args, need=(), ordered=True)
    if not (out / ACTUAL).exists():
        raise CartError(f"{cfg.relative(out / ACTUAL)} is not there – the skill cart reads the order page into it")
    actual = json.loads((out / ACTUAL).read_text(encoding="utf-8"))
    if args.source:
        (out / ACTUAL_PAGE).write_text(page_text(args.source), encoding="utf-8")
    if not (out / ACTUAL_PAGE).exists():
        raise CartError(f"{cfg.relative(out / ACTUAL_PAGE)} is not there – the page text the skill read, or --from FILE")
    page = (out / ACTUAL_PAGE).read_text(encoding="utf-8")
    quote = json.loads((out / QUOTE).read_text(encoding="utf-8")) if (out / QUOTE).exists() else None
    bad, b4_text = b4_actual(actual, page)
    e = job.get("estimate") or {}
    kinds = (("pcb", "PCB", e.get("pcb")), ("fee", "assembly fees", e.get("fees_total")),
             ("parts", "parts", e.get("parts_total")))

    def total(lines, kind=None):
        got = [x for x in lines or [] if (x.get("kind") == kind if kind else x.get("kind") in ("pcb", "fee", "parts"))]
        return round(sum(float(x["amount"]) for x in got), 2) if got else None
    money = lambda v: "–" if v is None else f"{v:.2f}"  # noqa: E731
    diff = lambda a, b: "–" if a is None or b is None else f"{a - b:+.2f}"  # noqa: E731
    cur = actual.get("currency") or (quote or {}).get("currency") or e.get("currency", "")
    L = [f"# Real cost – board {job['board']} at {m.name}, {order_word(actual)} ({actual.get('date')})\n",
         f"Written by edakit cart actual from {ACTUAL} and {'--from ' + Path(args.source).name if args.source else ACTUAL_PAGE}"
         f" (ORDER.read: {'; '.join(bad) if bad else b4_text}). Run {job['run']}, fab {str(job['fab_sha256'])[:12]}…, "
         f"{job['quantity']} PCBs, " + (f"{job['pcba_quantity']} assembled" if job.get("bom") else "bare")
         + f". Amounts in {cur}.\n",
         "| Line | Estimate | Quote | Actual | Actual − estimate |", "|---|---:|---:|---:|---:|"]
    for kind, label, est in kinds:
        a, q = total(actual.get("lines"), kind), total((quote or {}).get("prices"), kind)
        L.append(f"| {label} | {money(est)} | {money(q)} | {money(a)} | {diff(a, est)} |")
    a, q, est = total(actual.get("lines")), total((quote or {}).get("prices")), e.get("total")
    L += [f"| **board** | {money(est)} | {money(q)} | {money(a)} | {diff(a, est)} |", ""]
    c = cfg.cost or {}
    order_lines = {x.get("kind"): float(x["amount"]) for x in actual.get("order", []) if x.get("amount") is not None}
    L += ["Per order (all boards of the order), against [cost]:\n", "| Line | [cost] | Actual |", "|---|---:|---:|",
          f"| shipping | {money(c.get('shipping'))} | {money(order_lines.get('shipping'))} |",
          f"| coupon | {money(c.get('coupon'))} | {money(abs(order_lines['coupon']) if 'coupon' in order_lines else None)} |",
          f"| VAT | {c.get('vat_pct', 0):g} % | {money(order_lines.get('vat'))} |",
          f"| total | – | {money(order_lines.get('total'))} |", ""]
    notes, written, path = [], [], None
    if not bad:
        table = None
        if m.data.get("fees"):
            from . import cost
            table = cost.load_fee_table(cfg, m.key)
        updates = fee_updates(job, actual, table) if table else []
        notes = [text for name, entry, text in updates if entry is None]
        path, written = write_fees(cfg, m, job, actual, updates, notes)
    L += ["## Into the fee table\n", *(f"- {w}" for w in written)] if written else ["## Into the fee table\n",
                                                                                   "Nothing written." + (
                                                                                       " ORDER.read failed." if bad else "")]
    if path is not None:
        L.append(f"\nTable: `{cfg.relative(path)}` – edakit cost takes per fee the newest value.")
    if notes:
        L += ["\nNot written:\n", *(f"- {n}" for n in notes)]
    (out / ACTUAL_MD).write_text("\n".join(L) + "\n", encoding="utf-8")
    rec = None if bad else complete_record(cfg, job, out, actual, {"estimate": est, "quote": q, "actual": a,
                                                                    "currency": cur})
    print(f"{'FAIL' if bad else 'ok  '} ORDER.read read, not made up: {'; '.join(bad) if bad else b4_text}")
    print(f"board {job['board']} at {m.name}: estimate {money(est)}, quote {money(q)}, actual {money(a)} {cur}")
    for w in written:
        print(f"  fee table: {w}")
    for n in notes:
        print(f"  not written: {n}")
    print(f"real cost: {cfg.relative(out / ACTUAL_MD)}" + (f"; order record: {cfg.relative(rec)}" if rec else ""))
    return 2 if bad else 0


def complete_record(cfg, job, out, actual, totals):
    """The order record of this job, completed with the order number and the three totals; None without one."""
    sha = sha_of(out / JOB)
    for path in sorted((cfg.root / ORDERS).glob(f"*-{job['board']}-{job['maker']['key']}.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("job_sha256") == sha:
            data.update(order_number=actual.get("order_number"), actual=totals)
            path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            return path
    return None


def totals_of(cfg, run):
    """[(board, maker, order number, estimate, quote, actual, currency)] of the run's orders with a real cost – for
    edakit release current."""
    out = []
    for f in sorted(cfg.reports.glob(f"{run}/fab/*/cart/*/{ACTUAL}")):
        board, maker = f.parent.parent.parent.name, f.parent.name
        try:
            a = json.loads(f.read_text(encoding="utf-8"))
            job = json.loads((f.parent / JOB).read_text(encoding="utf-8"))
            q = json.loads((f.parent / QUOTE).read_text(encoding="utf-8")) if (f.parent / QUOTE).exists() else {}
        except (OSError, json.JSONDecodeError):
            continue
        s = lambda lines: round(sum(float(x["amount"]) for x in lines or [] if x.get("kind") in ("pcb", "fee",  # noqa: E731
                                                                                                "parts")), 2)
        out.append((board, maker, a.get("order_number"), (job.get("estimate") or {}).get("total"),
                    s(q.get("prices")) if q else None, s(a.get("lines")), a.get("currency", "")))
    return out


def check(cfg, args):
    board, m, out, job, (quote, page) = load_order(cfg, args)
    cart = None
    if args.cart:
        if not (out / CART).exists():
            raise CartError(f"{cfg.relative(out / CART)} is not there – the skill reads the cart line back into it")
        cart = json.loads((out / CART).read_text(encoding="utf-8"))
    res = evaluate(cfg, out, job, quote, page, cart)
    if args.cart:
        bad, actual = check_cart(job, quote, cart)
        res.append(("cart", "fail" if bad else "pass", "; ".join(bad) if bad else actual))
    done = write_check(out, job, quote, res, cart)
    for cid, result, actual in res:
        print(f"{result.upper():<7} {cid} {CHECKS.get(cid, 'cart line')}: {actual}")
    if args.cart and done["passed"]:
        path = record(cfg, out, job, quote, cart, done)
        print(f"order record: {cfg.relative(path)}")
    print(f"check: {cfg.relative(out / CHECK)}")
    if any(r == "fail" for _, r, _ in res):
        print("The order stops: nothing into the cart (ORDER.form to ORDER.review must pass).")
        return 2
    if any(r == "open" for _, r, _ in res):
        print("ORDER.form to ORDER.finish passed – the regulatory review of the order is next (ORDER.review).")
        return 3
    return 0


# --- edakit cart compare -----------------------------------------------------------------------------------------------

def check_state(out):
    """Whether edakit cart check passed on the quote.json of this order folder: passed, passed with warnings, review
    open, findings, not checked – or not checked when check.json belongs to another quote.json."""
    if not (out / CHECK_JSON).exists():
        return "not checked"
    done = json.loads((out / CHECK_JSON).read_text(encoding="utf-8"))
    if done.get("quote_sha256") != sha_of(out / QUOTE):
        return "not checked (the quote changed)"
    results = [r.get("result") for r in done.get("results", [])]
    if "fail" in results:
        return "findings"
    if "open" in results:
        return "review open"
    return "passed, with warnings" if "warn" in results else "passed"


def compare_rows(cfg, run, board):
    """[{maker, name, state | quote figures}] – one row per maker of [cart] makers, in their order: the board total
    (PCB, assembly fees, parts) as quoted and in [cost] currency through [cost] rates, the order total where the page
    showed one, the lines the maker marked or did not match (ORDER.parts), the lead time as read, the check."""
    money = cfg.cost or {}
    home = money.get("currency", "USD")
    rates = {home: 1.0, **{k: float(v) for k, v in (money.get("rates") or {}).items()}}
    rows = []
    for key in makers.listed(cfg):
        m = makers.get(cfg, key)
        out = folder(cfg, run, board, key)
        row = {"maker": key, "name": m.name, "home_currency": home}
        if not (out / JOB).exists():
            rows.append({**row, "state": f"no job – edakit cart prepare --maker {key}"})
            continue
        job = json.loads((out / JOB).read_text(encoding="utf-8"))
        if not (out / QUOTE).exists():
            rows.append({**row, "state": f"no quote yet – the skill cart at {m.name}"})
            continue
        quote = json.loads((out / QUOTE).read_text(encoding="utf-8"))
        currency = quote.get("currency") or m.currency or ""
        total = round(sum(float(p["amount"]) for p in board_lines(quote)), 2)
        order = next((float(p["amount"]) for p in quote.get("prices", []) if p.get("kind") == "total"), None)
        bad, _ = b2(job, quote)
        rate = rates.get(currency)
        rows.append({**row, "currency": currency, "board_total": total,
                     "home_total": None if rate is None else round(total * rate, 2), "order_total": order,
                     "lines": len(job.get("bom", [])), "parts": bad,
                     "matching": "review" if job["maker"].get("matching") == "review" and not quote.get("parts")
                     else "page",
                     "lead_time": quote.get("lead_time") or "", "read": quote.get("read") or "",
                     "check": check_state(out)})
    return rows


def compare_table(rows):
    """The rows as text columns: maker, board total, in [cost] currency, order total, parts, lead time, check."""
    home = rows[0]["home_currency"] if rows else "USD"
    head = ["maker", "board total", f"in {home}", "order total", "parts", "lead time", "check"]
    out = []
    for r in rows:
        if "state" in r:
            out.append([r["name"], r["state"]])
            continue
        parts = ("matched after the cart" if r["matching"] == "review" else
                 f"{len(r['parts'])} of {r['lines']} lines" if r["parts"] else f"all {r['lines']} lines")
        out.append([r["name"], f"{r['board_total']:.2f} {r['currency']}".strip(),
                    "–" if r["home_total"] is None else f"{r['home_total']:.2f} {home}",
                    "–" if r["order_total"] is None else f"{r['order_total']:.2f} {r['currency']}".strip(),
                    parts, r["lead_time"] or "–", r["check"]])
    return head, out


def lowest(rows):
    """(name, board total, currency, total in [cost] currency) of the lowest board total among at least two quotes
    that compare – in [cost] currency; None otherwise."""
    have = [r for r in rows if r.get("home_total") is not None]
    if len(have) < 2:
        return None
    r = min(have, key=lambda x: x["home_total"])
    return r["name"], r["board_total"], r["currency"], r["home_total"]


def compare(cfg, args):
    """The quotes of every maker of [cart] makers for the board of the current release side by side (handbook 8.4):
    printed, and written to cart/compare.md of the run. Reads only what the skill cart and edakit cart check wrote –
    nothing is asked of a maker, nothing ordered."""
    from .release import gate
    board = cfg.board(args.board, made=True)
    cur = gate.current(cfg)
    if cur is None:
        raise CartError("no current release")
    run = cur[0]
    rows = compare_rows(cfg, run, board.name)
    head, table = compare_table(rows)
    width = [max(len(head[i]), *(len(r[i]) for r in table if len(r) > 2)) for i in range(len(head))]
    print(f"board {board.name}, current release {run} – the quotes as the skill cart read them; nothing ordered")
    print("  ".join(h.ljust(w) for h, w in zip(head, width)).rstrip())
    for r in table:
        print(("  ".join(c.ljust(w) for c, w in zip(r, width)) if len(r) > 2 else
               f"{r[0].ljust(width[0])}  {r[1]}").rstrip())
    notes = [f"  {r['name']} – {p}" for r in rows for p in r.get("parts", [])]
    if notes:
        print("parts the maker marked or did not match:")
        print("\n".join(notes))
    low = lowest(rows)
    if low:
        name, total, currency, home_total = low
        home = rows[0]["home_currency"]
        print(f"lowest board total: {name}, {total:.2f} {currency}" +
              ("" if currency == home else f" ({home_total:.2f} {home})"))
    when = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    L = [f"# Quotes compared – board {board.name}, run {run}\n",
         f"Written by edakit cart compare at {when}: the quote the skill cart read at each maker of [cart] makers, the "
         "board total in [cost] currency through [cost] rates, and whether edakit cart check passed on that very "
         "quote – nothing ordered.\n",
         "| " + " | ".join(h[:1].upper() + h[1:] for h in head) + " |", "|" + "---|" * len(head)]
    L += ["| " + " | ".join(r) + " |" if len(r) > 2 else f"| {r[0]} | {r[1]} |" + " |" * (len(head) - 2)
          for r in table]
    if notes:
        L += ["", "Parts the maker marked or did not match:", "", *(f"- {n.strip()}" for n in notes)]
    if low:
        L += ["", f"Lowest board total: {low[0]}, {low[1]:.2f} {low[2]}" +
              ("" if low[2] == rows[0]["home_currency"] else f" ({low[3]:.2f} {rows[0]['home_currency']})") + "."]
    path = folder(cfg, run, board.name, makers.planned(cfg)).parent / COMPARE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"compare: {cfg.relative(path)}")
    return 0


def main(cfg, args):
    try:
        if args.action == "fields":
            return fields(cfg, args)
        if args.action == "compare":
            return compare(cfg, args)
        if args.action == "prepare":
            return prepare(cfg, args)
        if args.action == "check":
            return check(cfg, args)
        if args.action == "confirm":
            return confirm_check(cfg, args)
        return actual_cost(cfg, args)
    except (CartError, makers.MakerError) as e:
        print(f"edakit cart: {e}", file=sys.stderr)
        return 1
