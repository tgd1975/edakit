"""Who supplies what for `quantity` sets: the assembler's BOM, one cart per other supplier, the hand-assembly list –
and check PARTS.supplier (every bought part has a supplier).

    edakit order [--out DIR] [--with CONFIG ...]    default <artifacts>/order/
    edakit order check [--out DIR] [--supplier S]   ORDER.basket: the supplier's cart as the skill cart read it back

    bom_<board>.csv        the assembler's BOM, the file SYNC.bom writes – none for a bought board (bought = true) or a
                           hand-wired one (wired = true)
    cart_<supplier>.csv    LCSC in its BOM tool's columns "LCSC Part Number,Quantity,Comment"; any other supplier
                           "Code,Quantity,Item,Designators"
    hand_assembly.md       per board the parts fitted by hand (designator, part, side, supplier), and the items off the
                           board per set
    basket.json            every cart's lines with their need – what edakit order check holds the supplier's cart to

The assembler places every component with an LCSC number that is not bom: false. Every other component that names a
part (an LCSC number or `part`) is bought separately: from the component's `supplier`, else the first supplier of
its parts entry's `order`, else LCSC when it has an LCSC number. A parts entry's `order` maps a supplier to its order
code or to {code, moq, step} – {"lcsc": {"moq": 20, "step": 20}, "berrybase": {"code": "OSM5DK7331A"}}; the LCSC code
defaults to the entry's number. Items off the board are [[extra]] of edakit.toml (item, supplier, code, per_set,
spare, moq, step, unit_price, currency) – the list `edakit cost` prices.

Pieces per cart line: ceil(per set x quantity x (1 + [project] spare_pct / 100)) + the components' or the item's
`spare`, at least `moq`, a multiple of `step`. Own parts (`own` in the entry) are made, not bought: no cart.

--with (several times) puts the carts of other projects – their edakit.toml, each with its own quantity and spares –
into the same files: one line per supplier and code, the pieces summed, the comment naming each project with its
pieces, part and designators ("pytree: 20 XL-504SURD: D18 D22 (10 + 10) | christmas-bell (tht): 5 …"); each other
project's hand-assembly list is written beside as hand_assembly_<project>.md. One order for several projects
(docs/concepts/new/parts-order.md, decision 1).

  PARTS.supplier  a part bought separately (bom: false) has an LCSC number – not a C99… EasyEDA library number – or `order` in its
       parts entry (warning)

The supplier's cart (docs/concepts/new/parts-order.md, decisions 3 and 5): a supplier with a profile –
edakit/suppliers/<supplier>.toml, LCSC – is filled by the skill cart from cart_<supplier>.csv, every line read back into
<out>/<supplier>/cart.json with the page text cart_page.txt beside it, and the skill stops before the checkout.
`edakit order check` holds that cart to basket.json (ORDER.basket) and writes <out>/<supplier>/check.md:

    cart.json   {"supplier": "lcsc", "read": "…", "currency": "USD", "weight_g": 1500,
                 "before": [{"code": "C25804", "quantity": 100}],     the lines in the cart before the upload
                 "lines": [{"code": "C2895471", "quantity": 40, "stock": 12000, "price": 1.23, "mark": ""}]}
    shipping.json  after the combined shipment, LCSC's methods as recalculated – {"methods": [{"method": "DHL Express",
                 "amount": 68.40, "days": "2-5 working days"}], "currency": "USD"}, the page text shipping_page.txt

With the weights read – cart.json's weight_g, quote.json's weight_g of the planned maker's job – the check prints the
parcel together and the routes to compare before the maker's checkout; with shipping.json the methods by price and the
cheapest that arrives by [cart] needed_by.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import tomllib
import re
import sys
from collections import defaultdict
from pathlib import Path

from . import config
from .design import Design, natural_key
from .stock import refs_text

ASSEMBLER = "jlcpcb"
LCSC_HEAD = ["LCSC Part Number", "Quantity", "Comment"]
OTHER_HEAD = ["Code", "Quantity", "Item", "Designators"]


SUPPLIERS = Path(__file__).with_name("suppliers")
SUPPLIER_KEYS = ("name", "recorded", "start", "currency", "formats", "max_lines", "columns", "upload", "cart", "never",
                 "rounds", "combine")
COMBINE_TEXT = ("maker", "page", "read")      # [combine]: besides these, conditions, express_above_g and the address
CODE, TITLE = "ORDER.basket", "the supplier's cart = the basket"
BASKET, CART_JSON, CART_PAGE, SHIPPING, SHIPPING_PAGE, CHECK = (
    "basket.json", "cart.json", "cart_page.txt", "shipping.json", "shipping_page.txt", "check.md")


class OrderError(Exception):
    pass


def supplier(key):
    """The profile of a supplier whose cart the skill cart fills (edakit/suppliers/<key>.toml); None without one."""
    path = SUPPLIERS / f"{key}.toml"
    if not path.exists():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    bad = [f"unknown key '{k}'" for k in data if k not in SUPPLIER_KEYS]
    c = data.get("combine")
    if c is not None and not (isinstance(c, dict) and all(isinstance(c.get(k), str) and c[k] for k in COMBINE_TEXT)
                              and isinstance(c.get("conditions", []), list)):
        bad.append("combine needs maker, page and read, each a string")
    if bad:
        raise OrderError(f"supplier {key} ({path}): " + "; ".join(bad))
    return data


def address(combine):
    """The fields of the warehouse address in [combine], in the profile's order: {label: value}."""
    return {k: v for k, v in combine.items() if isinstance(v, str) and k not in COMBINE_TEXT}


def codes(entry, lcsc=None):
    """{supplier: {code, moq, step}} of a parts entry's `order`; a plain string is the code."""
    out = {}
    for sup, v in (entry.get("order") or {}).items():
        v = {"code": v} if isinstance(v, str) else dict(v or {})
        code = v.get("code") or ((lcsc or entry.get("lcsc")) if sup == "lcsc" else None)
        out[sup] = {"code": code, "moq": int(v.get("moq", 1)), "step": int(v.get("step", 1))}
    return out


def pieces(per_set, quantity, spare_pct=0.0, spare=0, moq=1, step=1):
    """Pieces to order: per set x quantity plus spare_pct, plus spare, at least moq, a multiple of step."""
    n = math.ceil(per_set * quantity * (1 + spare_pct / 100) - 1e-9) + int(spare or 0)
    n = max(n, int(moq or 1))
    step = int(step or 1)
    return math.ceil(n / step) * step


def assembled(c):
    return bool(c.get("lcsc")) and c.get("bom") is not False


def orderable(lcsc):
    """An LCSC number LCSC sells – C99… numbers are EasyEDA user-library entries (handbook 4.2)."""
    return bool(lcsc) and not str(lcsc).startswith("C99")


def source(design, des):
    """(supplier, {code, moq, step}) of a component bought separately; (None, None) when nothing names one."""
    c, entry = design.comps[des], design.part(des) or {}
    offers = codes(entry, c.get("lcsc") if orderable(c.get("lcsc")) else None)
    sup = c.get("supplier") or next(iter(offers), None) or ("lcsc" if orderable(c.get("lcsc")) else None)
    if sup is None:
        return None, None
    offer = offers.get(sup) or {"moq": 1, "step": 1, "code": None}
    if not offer.get("code") and sup == "lcsc":
        offer = {**offer, "code": next((x for x in (c.get("lcsc"), entry.get("lcsc")) if orderable(x)), None)}
    return sup, offer


def bought_by_hand(design):
    """Designators of the components bought separately and fitted by hand (not own parts, not bare pads)."""
    return [d for d, c in design.comps.items() if not assembled(c) and (c.get("lcsc") or c.get("part"))
            and not (design.part(d) or {}).get("own")]


def carts(cfg, design):
    """{supplier: [line]} and the designators without a supplier. A line: code, qty, need, item, designators."""
    groups, lost = {}, []
    for des in sorted(bought_by_hand(design), key=natural_key):
        sup, offer = source(design, des)
        if sup is None:
            lost.append(des)
            continue
        c, entry = design.comps[des], design.part(des) or {}
        key = (sup, offer["code"] or entry.get("mpn") or c.get("part") or des)
        g = groups.setdefault(key, {"supplier": sup, "code": offer["code"] or "", "moq": offer["moq"],
                                    "step": offer["step"], "item": entry.get("mpn") or c.get("part") or "",
                                    "designators": [], "spare": 0})
        g["designators"].append(des)
        spare = c.get("spare", 0)
        if isinstance(spare, bool) or not isinstance(spare, int) or spare < 0:
            raise OrderError(f"{des}: spare must be a whole number >= 0, not {spare!r}")
        g["spare"] += spare
    out = defaultdict(list)
    for g in groups.values():
        need = len(g["designators"]) * cfg.quantity
        g["qty"] = pieces(len(g["designators"]), cfg.quantity, cfg.spare_pct, g["spare"], g["moq"], g["step"])
        g["need"] = need
        out[g["supplier"]].append(g)
    for e in cfg.extras:
        qty = extra_pieces(cfg, e)
        out[e["supplier"]].append({"supplier": e["supplier"], "code": e.get("code", ""), "item": e["item"],
                                   "designators": [], "qty": qty, "need": math.ceil(e["per_set"] * cfg.quantity - 1e-9),
                                   "per_set": e["per_set"]})
    return dict(sorted(out.items())), lost


def extra_pieces(cfg, e):
    return pieces(e["per_set"], cfg.quantity, cfg.spare_pct, e.get("spare", 0), e.get("moq", 1), e.get("step", 1))


def label(cfg, others=()):
    """The name a project goes by in a basket: its project name, with its boards where another config has the same."""
    if any(o.project == cfg.project for o in others if o is not cfg):
        return f"{cfg.project} ({', '.join(b.name for b in cfg.boards.values() if not b.unmade) or cfg.path.parent.name})"
    return cfg.project


def note(g):
    """The comment of a cart line: part, designators, need + spare."""
    return f"{g['item']}: {' '.join(g['designators']) or 'per set'} ({g['need']} + {g['qty'] - g['need']})"


def basket(projects):
    """[(label, {supplier: [line]})] -> {supplier: [line]}: one line per supplier and code (or item without one), the
    pieces and the need summed, `parts` the projects' own lines – (label, line) – for the comment."""
    merged = {}
    for name, found in projects:
        for sup, lines in found.items():
            for g in lines:
                key = (sup, g["code"] or g["item"])
                m = merged.setdefault(key, {"supplier": sup, "code": g["code"], "item": g["item"], "designators": [],
                                            "qty": 0, "need": 0, "parts": []})
                m["qty"] += g["qty"]
                m["need"] += g["need"]
                m["designators"] += [f"{name}:{d}" for d in g["designators"]]
                m["parts"].append((name, g))
    out = defaultdict(list)
    for m in merged.values():
        out[m["supplier"]].append(m)
    return dict(sorted(out.items()))


def write_cart(path, supplier, lines):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if supplier == "lcsc":
            w.writerow(LCSC_HEAD)
            for g in lines:
                text = (" | ".join(f"{name}: {x['qty']} {note(x)}" for name, x in g["parts"]) if g.get("parts")
                        else note(g))
                w.writerow([g["code"], g["qty"], text])
        else:
            w.writerow(OTHER_HEAD)
            for g in lines:
                w.writerow([g["code"], g["qty"], g["item"], " ".join(g["designators"])])


def write_basket(out, cfg, others, found):
    """basket.json: the projects and every cart's lines with code, pieces, need and comment – ORDER.basket's measure."""
    cfgs = [cfg] + [o for o, _ in others]
    data = {"made": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "projects": [{"label": label(c, cfgs), "config": str(c.path), "quantity": c.quantity} for c in cfgs],
            "suppliers": {sup: [{"code": g["code"], "qty": g["qty"], "need": g["need"], "item": g["item"],
                                 "comment": (" | ".join(f"{n}: {x['qty']} {note(x)}" for n, x in g["parts"])
                                             if g.get("parts") else note(g))} for g in lines]
                          for sup, lines in found.items()}}
    (out / BASKET).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


HEADING = {"bought": " – bought, nobody assembles it", "hand-wired": " – hand-wired, no PCB"}


def hand_assembly(cfg, design, lost):
    L = [f"# Hand assembly – {cfg.project}, {cfg.quantity} sets\n",
         "Fitted by hand on every board after the assembled boards have arrived; the parts come from the carts in this "
         "folder.\n"]
    hand = set(bought_by_hand(design))
    for b in cfg.boards.values():
        mine = sorted((d for d in hand if design.comps[d].get("board") == b.name), key=natural_key)
        L.append(f"## Board {b.name} ({b.title}){HEADING.get(b.unmade, '')}\n")
        if not mine:
            L.append("Nothing by hand.\n")
            continue
        L += ["| Designator | Part | Side | Supplier |", "|---|---|---|---|"]
        for d in mine:
            c, entry = design.comps[d], design.part(d) or {}
            part = entry.get("mpn") or c.get("part") or c.get("value") or ""
            if c.get("lcsc"):
                part += f" ({c['lcsc']})"
            side = b.place[d].side if d in b.place else "–"
            L.append(f"| {d} | {part} | {side} | {'–' if d in lost else source(design, d)[0]} |")
        L.append("")
    if cfg.extras:
        L += ["## Per set, off the board\n", "| Item | Pieces | Supplier |", "|---|---|---|"]
        L += [f"| {e['item']} | {e['per_set']:g} | {e['supplier']} |" for e in cfg.extras]
        L.append("")
    return "\n".join(L)


def check(design, rep, cfg=None):
    """PARTS.supplier: a part bought separately (bom: false) names where it comes from. A C99… number is no LCSC number."""
    by_entry = defaultdict(list)
    for des, c in design.comps.items():
        if c.get("bom") is not False or orderable(c.get("lcsc")) or not (c.get("lcsc") or c.get("part")):
            continue          # assembled, from LCSC, or a bare pad with nothing to buy
        entry = design.part(des) or {}
        if entry.get("own") or entry.get("order"):
            continue
        by_entry[(entry.get("mpn") or c.get("part") or c["lcsc"], c.get("lcsc"))].append(des)
    for (mpn, lcsc), refs in sorted(by_entry.items(), key=lambda kv: natural_key(kv[1][0])):
        rep.warnings.append(("PARTS.supplier", f"{refs_text(sorted(refs, key=natural_key))} {mpn}: bought separately (bom: false), "
                                    "but neither an LCSC number nor `order` in its parts entry"
                                    + (f" ({lcsc} is an EasyEDA library number, LCSC does not sell it)" if lcsc else "")
                                    + " – name the supplier and its order code"))


# --- edakit order check ----------------------------------------------------------------------------------------------

def digits(text):
    """The page text with thousands separators gone, for finding a quantity as read ("1,000" is 1000)."""
    return re.sub(r"(?<=\d)[,\u202f\u00a0'](?=\d{3}\b)", "", text)


def on_page(page, value):
    """Whether a value read is in the page text: a number as a number of its own (5 is not the 5 of $0.5 or C25,
    68.4 is 68.40), any other value as text, case ignored."""
    v = str(value).strip()
    if not v:
        return False
    if re.fullmatch(r"\d+(\.\d+)?", v):
        tail = "0*" if "." in v else r"(?:\.0+)?"
        return bool(re.search(rf"(?<![\d.,]){re.escape(v)}{tail}(?![\d])", digits(page)))
    return v.casefold() in page.casefold()


def amount(x):
    return f"{x:g}" if isinstance(x, (int, float)) else str(x)


def basket_check(basket, cart, page):
    """ORDER.basket on one supplier's cart: (findings, notes). Every basket line in the cart by its code, as many pieces
    or more (more is the supplier's rounding), none out of stock or marked; no line that is neither the basket's nor
    there before the upload; every code, quantity and stock of cart.json in the page text. The lines there before are
    the owner's: listed, never a finding."""
    bad, notes = [], []
    lines = cart.get("lines") or []
    before = {str(b.get("code")): b for b in cart.get("before") or []}
    got = {}
    for g in lines:
        got.setdefault(str(g.get("code")), g)
    want = {str(b["code"]): b for b in basket if b.get("code")}
    for code, b in want.items():
        g = got.get(code)
        if g is None:
            bad.append(f"{code} ({b['item']}, {b['qty']} pieces) is not in the cart")
            continue
        q = g.get("quantity")
        if not isinstance(q, (int, float)) or q < b["qty"]:
            bad.append(f"{code}: {amount(q)} in the cart, the basket asks {b['qty']} (need {b['need']})")
        elif q > b["qty"]:
            notes.append(f"{code}: {amount(q)} instead of {b['qty']} – the supplier's rounding")
        stock = g.get("stock")
        if isinstance(stock, (int, float)) and isinstance(q, (int, float)) and stock < q:
            bad.append(f"{code}: {amount(stock)} in stock, {amount(q)} in the cart")
        if g.get("mark"):
            bad.append(f"{code}: marked \"{g['mark']}\"")
        if code in before:
            notes.append(f"{code}: in the cart before the upload too ({amount(before[code].get('quantity'))}) – "
                         "the owner decides which quantity stays")
    for code, g in got.items():
        if code not in want and code not in before:
            bad.append(f"{code} ({amount(g.get('quantity'))}): in the cart, not in the basket and not there before – a "
                       "replacement, or a line of another order")
    without = [b for b in basket if not b.get("code")]
    if without:
        bad.append("lines without a code cannot go into the cart: " + ", ".join(b["item"] for b in without))
    for g in lines:
        lost = [str(g.get(k)) for k in ("code", "quantity", "stock") if g.get(k) is not None
                and not on_page(page, amount(g[k]))]
        if lost:
            bad.append(f"{g.get('code')}: {', '.join(lost)} not in the page text – read, not made up")
    if cart.get("weight_g") is not None and not on_page(page, amount(cart["weight_g"])):
        bad.append(f"weight {amount(cart['weight_g'])} g not in the page text")
    if before:
        notes.append("in the cart before, not touched: " + ", ".join(
            f"{c} x {amount(b.get('quantity'))}" for c, b in before.items()))
    return bad, notes


def working_days(start, n):
    """The date n working days (Monday to Friday) after start."""
    d = start
    while n > 0:
        d += dt.timedelta(days=1)
        n -= d.weekday() < 5
    return d


def arrival(days, today):
    """The latest arrival of a shipping method's lead time ("2-5 working days", "7–15 days"); None when not read."""
    m = re.search(r"(\d+)\s*(?:[-–to]+\s*(\d+))?\s*(working|business)?\s*days?", str(days or ""), re.I)
    if not m:
        return None
    n = int(m.group(2) or m.group(1))
    return working_days(today, n) if m.group(3) else today + dt.timedelta(days=n)


def shipping_choice(ship, page, needed_by, today):
    """(lines, findings) for LCSC's methods after combining: by price, each with its latest arrival, and the cheapest
    that arrives by needed_by – or the cheapest of all without a date."""
    bad, rows = [], []
    for s in ship.get("methods") or []:
        lost = [str(s.get(k)) for k in ("method", "amount") if s.get(k) is not None and not on_page(page, amount(s[k]))]
        if lost:
            bad.append(f"shipping {s.get('method')}: {', '.join(lost)} not in the page text")
        rows.append((s.get("amount") if isinstance(s.get("amount"), (int, float)) else float("inf"), s,
                     arrival(s.get("days"), today)))
    rows.sort(key=lambda r: r[0])
    cur = ship.get("currency", "")
    out = [f"  {s.get('method')}: {amount(s.get('amount'))} {cur}, {s.get('days') or 'lead time not read'}"
           + (f" – by {a.isoformat()}" if a else "") for _, s, a in rows]
    fit = [r for r in rows if needed_by is None or (r[2] is not None and r[2] <= needed_by)]
    if fit:
        _, s, a = fit[0]
        out.append(f"→ cheapest{f' that arrives by {needed_by.isoformat()}' if needed_by else ''}: {s.get('method')}, "
                   f"{amount(s.get('amount'))} {cur} – choose it before paying (2026-11-02: DHL Express was paid "
                   "instead of the cheapest express)")
    elif rows:
        out.append(f"→ no method arrives by {needed_by.isoformat()} – the owner chooses")
    return out, bad


def weights(cfg, cart, combine):
    """The parcel before the maker's checkout: the supplier's weight, each made board's weight on its quote at the
    combine maker, and what follows. Lines to print; [] without a weight."""
    from . import cart as maker_cart
    w = cart.get("weight_g")
    boards = []
    for b in cfg.boards.values():
        if b.unmade:
            continue
        run, _, _ = maker_cart.run_folder(cfg, b.name)
        q = maker_cart.folder(cfg, run, b.name, combine["maker"]) / maker_cart.QUOTE if run else None
        if q and q.exists():
            g = json.loads(q.read_text(encoding="utf-8")).get("weight_g")
            if isinstance(g, (int, float)):
                boards.append((b.name, g))
    if not isinstance(w, (int, float)) and not boards:
        return []
    out = ["Shipment – the owner's choice before the maker's checkout (the address cannot be changed after it):"]
    out.append(f"  {combine['maker']}: " + (", ".join(f"{n} {amount(g)} g" for n, g in boards) or
                                           "weight not read – quote.json weight_g, from Quote & Order"))
    out.append(f"  parts cart: {amount(w) + ' g' if isinstance(w, (int, float)) else 'weight not read (cart.json weight_g)'}")
    if isinstance(w, (int, float)) and boards:
        total = w + sum(g for _, g in boards)
        limit = combine.get("express_above_g")
        out.append(f"  together {amount(total)} g" + (f" – above {amount(limit)} g LCSC offered express only "
                                                      "(2026-11-02)" if limit and total > limit else ""))
    out.append("  compare: the maker direct (its quote's shipping), the parts alone (the cart's cheapest), combined (its "
               "prices only after the maker is paid) – on 2026-11-02 combining cost 74.94 USD against 48.94 for the two "
               "cheapest separate routes: it buys speed and one parcel, not a lower price")
    return out


def check_main(cfg, args):
    out = Path(args.out) if args.out else cfg.artifacts / "order"
    key = args.supplier or "lcsc"
    prof = supplier(key)
    if prof is None:
        raise OrderError(f"no profile for supplier {key} – edakit ships {', '.join(p.stem for p in SUPPLIERS.glob('*.toml'))}")
    if not (out / BASKET).exists():
        raise OrderError(f"{cfg.relative(out / BASKET)} is not there – edakit order [--with …] writes it")
    basket = json.loads((out / BASKET).read_text(encoding="utf-8"))
    lines = basket["suppliers"].get(key) or []
    if not lines:
        raise OrderError(f"the basket has no {prof['name']} lines")
    d = out / key
    for f in (CART_JSON, CART_PAGE):
        if not (d / f).exists():
            raise OrderError(f"{cfg.relative(d / f)} is not there – the skill cart reads the cart back into it")
    cart = json.loads((d / CART_JSON).read_text(encoding="utf-8"))
    page = (d / CART_PAGE).read_text(encoding="utf-8")
    bad, notes = basket_check(lines, cart, page)
    report = [f"# {CODE} – {prof['name']}'s cart against the basket\n",
              f"Basket {cfg.relative(out / BASKET)} ({', '.join(p['label'] for p in basket['projects'])}), "
              f"{len(lines)} lines; cart read {cart.get('read', '–')}.\n"]
    report += ["## Findings\n", *(f"- {x}" for x in bad or ["none"]), "", "## Notes\n", *(f"- {x}" for x in notes or ["none"]), ""]
    say = []
    if prof.get("combine") and cfg.boards:
        say = weights(cfg, cart, prof["combine"])
    if (d / SHIPPING).exists():
        ship = json.loads((d / SHIPPING).read_text(encoding="utf-8"))
        spage = (d / SHIPPING_PAGE).read_text(encoding="utf-8") if (d / SHIPPING_PAGE).exists() else ""
        rows, sbad = shipping_choice(ship, spage, makers_of(cfg).get("needed_by"), dt.date.today())
        bad += sbad
        say += ["Shipping after combining (shipping.json):", *rows]
    if say:
        report += ["## Shipment\n", *say, ""]
    (d / CHECK).write_text("\n".join(report), encoding="utf-8")
    print(f"{'FAIL' if bad else 'PASS':<7} {CODE} {prof['name']}'s cart = basket: "
          + (f"{len(bad)} finding{'s' if len(bad) != 1 else ''}" if bad else f"{len(lines)} lines"))
    for x in bad:
        print(f"  {x}")
    for x in notes:
        print(f"  note: {x}")
    for x in say:
        print(x)
    print(f"check: {cfg.relative(d / CHECK)}")
    if bad:
        print("The parts order stops: nothing further in the cart; the findings to the owner.")
        return 2
    print("The cart is the basket's. Checkout and payment are the owner's – never "
          + ", ".join(prof.get("never", [])) + ".")
    return 0


def makers_of(cfg):
    from . import makers
    return makers.of(cfg)


def main(cfg, args):
    if getattr(args, "action", None) == "check":
        try:
            return check_main(cfg, args)
        except (OrderError, OSError, json.JSONDecodeError) as e:
            print(f"edakit order check: {e}", file=sys.stderr)
            return 1
    from .release import fab
    design = Design.from_config(cfg)
    out = Path(args.out) if args.out else cfg.artifacts / "order"
    out.mkdir(parents=True, exist_ok=True)
    try:
        found, lost = carts(cfg, design)
        others = []
        for path in getattr(args, "with_", None) or []:
            o = config.load(path)
            others.append((o, Design.from_config(o)))
    except (OrderError, config.ConfigError) as e:
        print(f"edakit order: {e}", file=sys.stderr)
        return 1
    if others:
        cfgs = [cfg] + [o for o, _ in others]
        try:
            found = basket([(label(cfg, cfgs), found)] + [(label(o, cfgs), carts(o, d)[0]) for o, d in others])
        except OrderError as e:
            print(f"edakit order: {e}", file=sys.stderr)
            return 1
    for old in out.glob("cart_*.csv"):     # a supplier no line names any more leaves no cart behind
        old.unlink()
    for b in cfg.boards.values():
        if b.unmade:              # nobody assembles it: no BOM; its parts are in the carts and hand_assembly.md
            (out / f"bom_{b.name}.csv").unlink(missing_ok=True)
            continue
        bom = fab.bom_rows(design, b)
        fab.write_bom(bom, out / f"bom_{b.name}.csv")
        print(f"bom_{b.name}.csv: {len(bom)} lines for the assembler ({cfg.quantity} boards)")
    write_basket(out, cfg, others, found)
    for sup, lines in found.items():
        name = f"cart_{re.sub(r'[^A-Za-z0-9_-]+', '_', sup)}.csv"
        write_cart(out / name, sup, lines)
        print(f"{name}: {len(lines)} line{'s' if len(lines) != 1 else ''}, "
              + ", ".join(f"{g['code'] or g['item']} x {g['qty']}" for g in lines))
    (out / "hand_assembly.md").write_text(hand_assembly(cfg, design, lost), encoding="utf-8")
    for o, d in others:
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", label(o, [cfg] + [x for x, _ in others])).strip("_")
        (out / f"hand_assembly_{name}.md").write_text(hand_assembly(o, d, carts(o, d)[1]), encoding="utf-8")
        n = len(bought_by_hand(d))
        print(f"hand_assembly_{name}.md: {n} part{'s' if n != 1 else ''} by hand – {o.path}")
        for x in carts(o, d)[1]:
            print(f"WARNING {label(o, [cfg] + [y for y, _ in others])} {x}: no supplier")
    hand, extras = len(bought_by_hand(design)), len(cfg.extras)
    print(f"hand_assembly.md: {hand} part{'s' if hand != 1 else ''} by hand, {extras} item{'s' if extras != 1 else ''} "
          "off the board")
    for d in lost:
        lcsc = design.comps[d].get("lcsc")
        print(f"WARNING {d}: no supplier – an LCSC number, `order` in its parts entry or `supplier`"
              + (f" ({lcsc} is an EasyEDA library number, LCSC does not sell it)" if lcsc else ""))
    print(f"→ {cfg.relative(out)}")
    return 0
