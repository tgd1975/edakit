"""Order cost from the BOM and the board: what `quantity` boards cost at the assembler, before the first quote and
after every change.

    edakit cost [--board B] [--json FILE]

Reads the graph (assembled parts: an LCSC number, not bom: false), the parts entries (joints = their pins, jlc_class,
`lead` for a through-hole part), the board files (outline → PCB size; [place] → the side of each part, a part not
placed sits on the first side of [release] assembly.sides), the stock snapshot of `edakit stock` (class, PCBA type,
MSL, X-ray, hand or reflow soldering, attrition, price breaks) and the fee table – edakit/fees/jlcpcb.json, every
value with its date and source, or the file in [cost] fees.

Per board:
  class   [release] assembly.pcba or its sides; parts on a second side and "Standard Only" parts raise it to Standard
          and are named
  PCB     [cost] pcb_price, else the fee table's price for the size – under Standard with the edge rails
  fees    Economic: setup and stencil per order, loading per Extended type, SMT joints. Standard: setup and stencil
          per assembled side, loading per type, SMT joints, packing. Both: joints soldered by hand plus the labour,
          through-hole reflow joints, X-ray per part, bake (MSL >= 5), large size. A Standard order Economic could
          assemble as well is topped up to the minimum difference (handling fee).
  parts   per line its need (Economic: the placements; Standard: with attrition, stock.need) at its price break
and beside it the other class: Standard for an Economic board, Economic for a Standard one – without the parts that
force Standard. For the order: shipping, coupon, VAT on the assembler's order ([cost]), items off the board
([[extra]]), the total in [cost] currency against the budget, the drivers, and the change since the last estimate
(<artifacts>/cost.json). Without a snapshot the parts have no price and only PCB and fees are estimated.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path

from . import stock
from .design import Design, natural_key

FEE_TABLE = Path(__file__).with_name("fees") / "jlcpcb.json"


class CostError(Exception):
    pass


def load_fee_table(cfg=None):
    path = cfg.resolve(cfg.cost["fees"]) if cfg is not None and (cfg.cost or {}).get("fees") else FEE_TABLE
    return json.loads(path.read_text(encoding="utf-8"))


def unit_price(spec, count):
    """A fee's price per unit: its value, or the tier the whole count falls in."""
    if "tiers" not in spec:
        return spec["value"]
    for lo, hi, price in spec["tiers"]:
        if lo <= count <= hi:
            return price
    return spec["tiers"][-1][2]


def mm(v):
    return f"{v:g}"


def pcb_price(fees, w, h, quantity):
    """(price, how) of a board w x h mm from the fee table: its own size, else by area between the priced sizes, above
    them extrapolated; below the smallest it is at most that price. (None, why) where the table has no answer."""
    table = fees["pcb"]
    if quantity != table["qty"]:
        return None, f"the fee table prices {table['qty']} boards, not {quantity} – [cost] pcb_price"
    pts = sorted(table["prices"], key=lambda p: p["w_mm"] * p["h_mm"])
    for p in pts:
        if sorted((p["w_mm"], p["h_mm"])) == sorted((w, h)):
            return p["value"], f"fee table: {mm(p['w_mm'])} × {mm(p['h_mm'])} mm, {p['date']}"
    area = w * h
    size = lambda p: f"{mm(p['w_mm'])} × {mm(p['h_mm'])} mm"  # noqa: E731
    if area <= pts[0]["w_mm"] * pts[0]["h_mm"]:
        return pts[0]["value"], f"at most the price of the smallest size in the fee table, {size(pts[0])} – [cost] pcb_price"
    lo, hi = next(((a, b) for a, b in zip(pts, pts[1:]) if area <= b["w_mm"] * b["h_mm"]), (pts[-2], pts[-1]))
    a0, a1 = lo["w_mm"] * lo["h_mm"], hi["w_mm"] * hi["h_mm"]
    price = lo["value"] + (hi["value"] - lo["value"]) * (area - a0) / (a1 - a0)
    return round(price, 2), f"interpolated by area between {size(lo)} and {size(hi)} of the fee table"


def klass(line):
    """basic, preferred or extended; a part of unknown class counts as Extended."""
    c = (line.get("class") or "").lower()
    return "basic" if "basic" in c else "preferred" if line.get("preferred") or "preferred" in c else "extended"


def price_at(breaks, qty):
    if not breaks:
        return None
    price = breaks[0][1]
    for start, p in sorted(breaks):
        if start <= qty:
            price = p
    return price


def few(refs, n=6):
    refs = sorted(refs, key=natural_key)
    return stock.refs_text(refs) if len(refs) <= n else f"{stock.refs_text(refs[:n])} and {len(refs) - n} more"


def price_class(fees, quantity, lines, cls, size_mm=None, pcb_override=None):
    """PCB, fees and parts of one board design under one PCBA class."""
    f, q = fees["pcba"], quantity
    out = []

    def add(key, item, amount):
        out.append({"key": key, "item": item, "amount": round(amount, 4)})
    pcb = {"size_mm": list(size_mm) if size_mm else None, "amount": None, "how": "no outline in the board file"}
    if size_mm:
        w, h = size_mm
        if cls == "standard":
            rail = 2 * f["standard_edge_rails_mm"]["value"]
            w, h = (w + rail, h) if w <= h else (w, h + rail)
        pcb["size_mm"] = [w, h]
        pcb["amount"], pcb["how"] = pcb_price(fees, w, h, q)
    if pcb_override is not None:
        pcb["amount"], pcb["how"] = float(pcb_override), "[cost] pcb_price"
    area_cm2 = pcb["size_mm"][0] * pcb["size_mm"][1] / 100 if pcb["size_mm"] else 0
    sides = sorted({s for ln in lines for s in ln["sides"].values()})
    joints = {m: sum(ln["joints"] * len(ln["refs"]) for ln in lines if (ln.get("mode") or "smt") == m)
              for m in ("smt", "manual", "reflow")}
    if lines and cls == "economic":
        add("setup", "setup, Economic", f["economic_setup"]["value"])
        add("stencil", "stencil, Economic", f["economic_stencil"]["value"])
        for ln in lines:
            if klass(ln) == "extended":
                add(f"loading {ln['lcsc']}", f"loading fee {ln['lcsc']}", f["economic_loading"]["value"])
        smt = f["economic_smt_joint"]
    elif lines:
        n = len(sides)
        add("setup", f"setup, {n} side{'s' if n > 1 else ''}", f["standard_setup"]["value"] * n)
        add("stencil", f"stencil, {n} side{'s' if n > 1 else ''}", f["standard_stencil"]["value"] * n)
        for ln in lines:
            add(f"loading {ln['lcsc']}", f"loading fee {ln['lcsc']}", f["standard_loading"]["value"])
        smt = f["standard_smt_joint"]
    if joints["smt"]:
        n = joints["smt"] * q
        add("smt joints", f"SMT joints, {joints['smt']} x {q}", n * unit_price(smt, n))
    if joints["manual"]:
        n = joints["manual"] * q
        add("manual joints", f"joints soldered by hand, {joints['manual']} x {q}", n * unit_price(f["manual_joint"], n))
        add("hand soldering", "hand-soldering labour", f["hand_soldering_labour"]["value"])
    if joints["reflow"]:
        n = joints["reflow"] * q
        add("reflow joints", f"through-hole reflow joints, {joints['reflow']} x {q}", n * unit_price(f["reflow_joint"], n))
    xray = sum(len(ln["refs"]) for ln in lines if ln.get("xray")) * q
    if xray:
        add("x-ray", f"X-ray, {xray} parts", xray * unit_price(f["xray"], xray))
    if lines and cls == "standard":
        add("packing", "packing", f["standard_packing"]["value"] + f["standard_packing"]["per_cm2"] * area_cm2 * q)
    if any((ln.get("msl") or 0) >= stock.BAKE_MSL for ln in lines):
        add("bake", "bake (MSL 5 or more)", f["bake"]["value"])
    if lines and area_cm2 > f["large_size"]["above_cm2"]:
        add("large size", f"large size ({area_cm2:.0f} cm²)", f["large_size"]["value"])
    parts = []
    for ln in lines:
        want = stock.need(len(ln["refs"]) * q, cls, ln)
        unit = price_at(ln.get("price_breaks"), want) if ln.get("listed") else None
        parts.append({"lcsc": ln["lcsc"], "refs": ln["refs"], "qty": want, "unit": unit,
                      "amount": round(want * unit, 4) if unit is not None else None})
    res = {"class": cls, "pcb": pcb, "fees": out, "parts": parts,
           "fees_total": round(sum(x["amount"] for x in out), 2),
           "parts_total": round(sum(p["amount"] or 0 for p in parts), 2),
           "unpriced": sum(p["amount"] is None for p in parts)}
    res["total"] = round((pcb["amount"] or 0) + res["fees_total"] + res["parts_total"], 2)
    return res


def estimate_board(fees, quantity, lines, declared, main_side="top", size_mm=None, pcb_override=None, name=""):
    """One board design: the class (declared, raised by what forces Standard), its PCB, fees and parts, the drivers,
    and the other class beside it. lines: stock snapshot rows plus lcsc, refs, sides {ref: side}, joints (per part)."""
    pcba, why = declared
    drivers, forced = [], set()
    for ln in lines:
        if ln.get("assembly_type") == stock.STANDARD_ONLY:
            drivers.append(f"{few(ln['refs'])} {ln['lcsc']} '{stock.STANDARD_ONLY}' – Standard PCBA")
            forced |= set(ln["refs"])
    off = {}
    for ln in lines:
        for ref, side in ln["sides"].items():
            if side != main_side:
                off.setdefault(side, []).append(ref)
    for side, refs in sorted(off.items()):
        drivers.append(f"{few(refs)} on {side} – both sides assembled, Standard PCBA")
        forced |= set(refs)
    cls = "standard" if pcba == "standard" or forced else "economic"
    res = price_class(fees, quantity, lines, cls, size_mm, pcb_override)
    if forced:
        rest = [{**ln, "refs": [r for r in ln["refs"] if r not in forced],
                 "sides": {r: s for r, s in ln["sides"].items() if r not in forced}} for ln in lines]
        alt = price_class(fees, quantity, [ln for ln in rest if ln["refs"]], "economic", size_mm, pcb_override)
        alt["without"] = sorted(forced, key=natural_key)
    else:
        alt = price_class(fees, quantity, lines, "economic" if cls == "standard" else "standard", size_mm, pcb_override)
        alt["without"] = []
    if cls == "standard" and not forced and lines:
        least = fees["pcba"]["handling_min_difference"]["value"]
        diff = (res["fees_total"] + res["parts_total"]) - (alt["fees_total"] + alt["parts_total"])
        if diff < least:
            res["fees"].append({"key": "handling", "item": "handling fee (Economic would be possible)",
                                "amount": round(least - diff, 4)})
            res["fees_total"] = round(res["fees_total"] + least - diff, 2)
            res["total"] = round(res["total"] + least - diff, 2)
    f = fees["pcba"]
    for ln in lines:
        who = f"{few(ln['refs'])} {ln['lcsc']}"
        if cls == "economic" and klass(ln) == "extended":
            drivers.append(f"{who} {ln.get('class') or 'class unknown, counted as Extended'} – "
                           f"{f['economic_loading']['value']:.2f} loading fee")
        if (ln.get("msl") or 0) >= stock.BAKE_MSL:
            drivers.append(f"{who} MSL {ln['msl']} – bake {f['bake']['value']:.2f} and 2 days")
        if ln.get("xray"):
            drivers.append(f"{who} X-ray – {unit_price(f['xray'], 1):.2f} per part and less in larger orders")
    if cls == "standard" and size_mm and res["pcb"]["size_mm"] != list(size_mm):
        drivers.append(f"edge rails: the PCB is priced as {mm(res['pcb']['size_mm'][0])} × {mm(res['pcb']['size_mm'][1])} mm")
    return {"name": name, "size_mm": list(size_mm) if size_mm else None, "why": why if not forced else f"{why}, raised by {len(forced)} part{'s' if len(forced) > 1 else ''}",
            **res, "drivers": drivers, "alternative": alt}


# --- the project ----------------------------------------------------------------------------------------------------

def board_lines(cfg, design, board, snap):
    sides = cfg.release.get("assembly", {}).get("sides", ["top", "bottom"])
    lines = []
    for lcsc, refs in stock.assembled(design, board.name).items():
        entry = design.parts.get(lcsc) or {}
        row = dict((snap or {}).get("parts", {}).get(lcsc) or {})
        if row.get("error"):
            row = {}
        lines.append({**row, "lcsc": lcsc, "refs": refs, "joints": len(entry.get("pins") or {}),
                      "sides": {r: board.place[r].side if r in board.place else sides[0] for r in refs},
                      "class": row.get("class") or entry.get("jlc_class"),
                      "mode": row.get("mode") or ("manual" if entry.get("lead") else "smt")})
    return lines


def converter(cfg, fees):
    cur, rates = (cfg.cost or {}).get("currency", "USD"), (cfg.cost or {}).get("rates", {})

    def rate(c):
        c = c or cur
        if c == cur:
            return 1.0
        if c not in rates:
            raise CostError(f"[cost] rates has no rate for {c} (the value of one {c} in {cur}, e.g. rates = "
                            f"{{ {c} = … }})")
        return float(rates[c])
    rate(fees["currency"])
    return cur, rate


def extra_lines(cfg, rate):
    out = []
    for e in cfg.extras:
        qty = math.ceil(e["per_set"] * cfg.quantity - 1e-9)
        price = e.get("unit_price")
        out.append({"item": e["item"], "supplier": e["supplier"], "qty": qty, "unit_price": price,
                    "currency": e.get("currency") or (cfg.cost or {}).get("currency", "USD"),
                    "amount": round(qty * price * rate(e.get("currency")), 2) if price is not None else None})
    return out


def order_total(boards, cost_cfg, rate=1.0, extras=()):
    """The order: the boards (converted with rate), shipping minus coupon, VAT on that, the items off the board."""
    boards_sum = sum(b["total"] for b in boards) * rate
    sub = boards_sum + float(cost_cfg.get("shipping", 0)) - float(cost_cfg.get("coupon", 0))
    vat = float(cost_cfg.get("vat_pct", 0)) / 100 * sub
    return {"boards_total": round(boards_sum, 2), "shipping": float(cost_cfg.get("shipping", 0)),
            "coupon": float(cost_cfg.get("coupon", 0)), "vat_pct": float(cost_cfg.get("vat_pct", 0)),
            "vat": round(vat, 2), "extras": list(extras),
            "total": round(sub + vat + sum(e["amount"] or 0 for e in extras), 2)}


def estimate(cfg, board=None):
    fees = load_fee_table(cfg)
    cur, rate = converter(cfg, fees)
    snap = stock.load(cfg)
    design = Design.from_config(cfg)
    sides = cfg.release.get("assembly", {}).get("sides", ["top", "bottom"])
    override = (cfg.cost or {}).get("pcb_price")
    boards = {}
    for b in ([cfg.board(board)] if board else cfg.boards.values()):
        size = None
        if b.outline:
            xs, ys = [p[0] for p in b.outline], [p[1] for p in b.outline]
            size = (round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2))
        price = override.get(b.name) if isinstance(override, dict) else override
        boards[b.name] = estimate_board(fees, cfg.quantity, board_lines(cfg, design, b, snap), cfg.pcba(),
                                        main_side=sides[0], size_mm=size, pcb_override=price, name=b.name)
    extras = extra_lines(cfg, rate)
    order = order_total(list(boards.values()), cfg.cost or {}, rate(fees["currency"]), extras)
    est = {"date": dt.date.today().isoformat(), "fees": {"date": fees["date"], "assembler": fees["assembler"]},
           "snapshot": (snap or {}).get("date"), "currency": cur, "quantity": cfg.quantity, "boards": boards,
           **order, "unpriced": sum(b["unpriced"] for b in boards.values()),
           "budget": (cfg.cost or {}).get("budget")}
    est["lines"] = flat(est, rate(fees["currency"]))
    return est


def flat(est, rate):
    """{key: {label, amount}} in the estimate's currency – what the change since the last estimate compares."""
    out = {}
    for name, b in est["boards"].items():
        if b["pcb"]["amount"] is not None:
            out[f"{name}/pcb"] = {"label": f"{name}: PCB", "amount": round(b["pcb"]["amount"] * rate, 2)}
        for f in b["fees"]:
            out[f"{name}/fee/{f['key']}"] = {"label": f"{name}: {f['item']}", "amount": round(f["amount"] * rate, 2)}
        for p in b["parts"]:
            if p["amount"] is not None:
                out[f"{name}/part/{p['lcsc']}"] = {"label": f"{name}: {p['lcsc']} x {p['qty']}",
                                                   "amount": round(p["amount"] * rate, 2)}
    for key in ("shipping", "vat"):
        out[key] = {"label": key, "amount": est[key]}
    out["coupon"] = {"label": "coupon", "amount": -est["coupon"]}
    for e in est["extras"]:
        if e["amount"] is not None:
            out[f"extra/{e['item']}"] = {"label": f"{e['item']} ({e['supplier']})", "amount": e["amount"]}
    return out


def changes(old, new):
    out = []
    for key in sorted(set(old) | set(new)):
        a, b = (old.get(key) or {}).get("amount", 0), (new.get(key) or {}).get("amount", 0)
        if abs(b - a) >= 0.005:
            status = "new" if key not in old else "gone" if key not in new else f"was {a:.2f}"
            out.append((b - a, (new.get(key) or old.get(key))["label"], status))
    return sorted(out, key=lambda c: -abs(c[0]))


# --- output ---------------------------------------------------------------------------------------------------------

def money(v):
    return "–" if v is None else f"{v:.2f}"


def print_board(b, cur_fee):
    w = 46
    size = b["size_mm"]
    print(f"board {b['name']}{', ' + ' × '.join(mm(v) for v in size) + ' mm' if size else ''}: "
          f"{b['class'].capitalize()} PCBA ({b['why']})")
    print(f"  {'PCB':<{w}} {money(b['pcb']['amount']):>9}  {b['pcb']['how']}")
    loading = [f for f in b["fees"] if f["key"].startswith("loading ")]
    for f in b["fees"]:
        if f["key"].startswith("loading "):
            if f is loading[0]:
                print(f"  {f'loading fee, {len(loading)} types':<{w}} {sum(x['amount'] for x in loading):>9.2f}")
            continue
        print(f"  {f['item']:<{w}} {f['amount']:>9.2f}")
    gap = [p["lcsc"] for p in b["parts"] if p["amount"] is None]
    print(f"  {'parts, ' + str(len(b['parts'])) + ' lines':<{w}} {b['parts_total']:>9.2f}"
          + (f"  no price: {', '.join(gap)} (edakit stock)" if gap else ""))
    print(f"  {'board ' + b['name']:<{w}} {b['total']:>9.2f} {cur_fee}")
    alt = b["alternative"]
    if alt["fees"]:
        label = f"as {alt['class'].capitalize()}" + (f" without {few(alt['without'])}" if alt["without"] else "")
        print(f"  {label + ':':<{w}} {alt['total']:>9.2f} {cur_fee} (fees {alt['fees_total']:.2f}, parts "
              f"{alt['parts_total']:.2f})")


def main(cfg, args):
    try:
        est = estimate(cfg, args.board)
    except CostError as e:
        print(f"edakit cost: {e}", file=sys.stderr)
        return 1
    fees = load_fee_table(cfg)
    cur = est["currency"]
    print(f"edakit cost: {cfg.quantity} boards – fee table {fees['assembler']} {fees['date']} ({fees['currency']}), "
          + (f"stock snapshot {est['snapshot']}" if est["snapshot"] else "no stock snapshot: parts without price "
             "(edakit stock)"))
    for b in est["boards"].values():
        print_board(b, fees["currency"])
    drivers = [d for b in est["boards"].values() for d in b["drivers"]]
    if drivers:
        print("what drives the cost:")
        for d in drivers:
            print(f"  {d}")
    if not args.board:
        print(f"order in {cur}: boards {est['boards_total']:.2f}"
              + (f", shipping {est['shipping']:.2f}" if est["shipping"] else "")
              + (f", coupon -{est['coupon']:.2f}" if est["coupon"] else "")
              + (f", VAT {est['vat_pct']:g} % {est['vat']:.2f}" if est["vat_pct"] else ""))
        for e in est["extras"]:
            print(f"  {e['item']} ({e['supplier']}): {e['qty']} x {money(e['unit_price'])} {e['currency']} = "
                  f"{money(e['amount'])}")
        print(f"total {est['total']:.2f} {cur}" + (f" – {est['unpriced']} part lines without price" if est["unpriced"]
                                                   else ""))
        f = cfg.artifact("cost.json")
        old = json.loads(f.read_text(encoding="utf-8")).get("lines", {}) if f.exists() else None
        f.write_text(json.dumps(est, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        if old is not None:
            diff = changes(old, est["lines"])
            print("since the last estimate: " + ("no change" if not diff else ""))
            for d, label, status in diff:
                print(f"  {d:+.2f} {cur}  {label} ({status})")
    if args.json:
        Path(args.json).write_text(json.dumps(est, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    budget = est["budget"]
    if budget is not None and not args.board and est["total"] > budget:
        print(f"WARNING cost: {est['total']:.2f} {cur} above the budget of {budget:.2f} {cur}")
        return 2
    return 0


def gate_rows(cfg):
    """The gate's row for [cost]: the estimate as information, above [cost] budget a warning to accept."""
    if cfg.cost is None:
        return []
    check = f"estimated order cost for {cfg.quantity} boards"
    try:
        est = estimate(cfg)
    except CostError as e:
        return [{"stage": "P", "id": "cost", "item": "order", "check": check, "actual": str(e), "expected": "",
                 "result": "fail"}]
    budget, cur = est["budget"], est["currency"]
    check += f" (fee table {est['fees']['date']}" + (f"; {est['unpriced']} part lines without price" if est["unpriced"]
                                                     else "") + ")"
    return [{"stage": "P", "id": "cost", "item": "order", "check": check, "actual": f"{est['total']:.2f} {cur}",
             "expected": f"at most {budget:.2f} {cur} ([cost] budget)" if budget is not None else "",
             "result": "warn" if budget is not None and est["total"] > budget else "info"}]
