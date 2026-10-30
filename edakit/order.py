"""Who supplies what for `quantity` sets: the assembler's BOM, one cart per other supplier, the hand-assembly list –
and check P-5 (every bought part has a supplier).

    edakit order [--out DIR]          default <artifacts>/order/

    bom_<board>.csv        the assembler's BOM, the file F-1 writes – none for a bought board (bought = true)
    cart_<supplier>.csv    LCSC in its BOM tool's columns "LCSC Part Number,Quantity,Comment"; any other supplier
                           "Code,Quantity,Item,Designators"
    hand_assembly.md       per board the parts fitted by hand (designator, part, side, supplier), and the items off the
                           board per set

The assembler places every component with an LCSC number that is not bom: false. Every other component that names a
part (an LCSC number or `part`) is bought separately: from the component's `supplier`, else the first supplier of
its parts entry's `order`, else LCSC when it has an LCSC number. A parts entry's `order` maps a supplier to its order
code or to {code, moq, step} – {"lcsc": {"moq": 20, "step": 20}, "berrybase": {"code": "OSM5DK7331A"}}; the LCSC code
defaults to the entry's number. Items off the board are [[extra]] of edakit.toml (item, supplier, code, per_set,
spare, moq, step, unit_price, currency) – the list `edakit cost` prices.

Pieces per cart line: ceil(per set x quantity x (1 + [project] spare_pct / 100)) + the components' or the item's
`spare`, at least `moq`, a multiple of `step`. Own parts (`own` in the entry) are made, not bought: no cart.

  P-5  a part bought separately (bom: false) has an LCSC number – not a C99… EasyEDA library number – or `order` in its
       parts entry (warning)
"""

from __future__ import annotations

import csv
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

from .design import Design, natural_key
from .stock import refs_text

ASSEMBLER = "jlcpcb"
LCSC_HEAD = ["LCSC Part Number", "Quantity", "Comment"]
OTHER_HEAD = ["Code", "Quantity", "Item", "Designators"]


class OrderError(Exception):
    pass


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


def write_cart(path, supplier, lines):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if supplier == "lcsc":
            w.writerow(LCSC_HEAD)
            for g in lines:
                who = " ".join(g["designators"]) or "per set"
                w.writerow([g["code"], g["qty"], f"{g['item']}: {who} ({g['need']} + {g['qty'] - g['need']})"])
        else:
            w.writerow(OTHER_HEAD)
            for g in lines:
                w.writerow([g["code"], g["qty"], g["item"], " ".join(g["designators"])])


def hand_assembly(cfg, design, lost):
    L = [f"# Hand assembly – {cfg.project}, {cfg.quantity} sets\n",
         "Fitted by hand on every board after the assembled boards have arrived; the parts come from the carts in this "
         "folder.\n"]
    hand = set(bought_by_hand(design))
    for b in cfg.boards.values():
        mine = sorted((d for d in hand if design.comps[d].get("board") == b.name), key=natural_key)
        L.append(f"## Board {b.name} ({b.title}){' – bought, nobody assembles it' if b.bought else ''}\n")
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
    """P-5: a part bought separately (bom: false) names where it comes from. A C99… number is no LCSC number."""
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


def main(cfg, args):
    from .release import fab
    design = Design.from_config(cfg)
    out = Path(args.out) if args.out else cfg.artifacts / "order"
    out.mkdir(parents=True, exist_ok=True)
    try:
        found, lost = carts(cfg, design)
    except OrderError as e:
        print(f"edakit order: {e}", file=sys.stderr)
        return 1
    for old in out.glob("cart_*.csv"):     # a supplier no line names any more leaves no cart behind
        old.unlink()
    for b in cfg.boards.values():
        if b.bought:              # nobody assembles it: no BOM; its parts are in the carts and hand_assembly.md
            (out / f"bom_{b.name}.csv").unlink(missing_ok=True)
            continue
        bom = fab.bom_rows(design, b)
        fab.write_bom(bom, out / f"bom_{b.name}.csv")
        print(f"bom_{b.name}.csv: {len(bom)} lines for the assembler ({cfg.quantity} boards)")
    for sup, lines in found.items():
        name = f"cart_{re.sub(r'[^A-Za-z0-9_-]+', '_', sup)}.csv"
        write_cart(out / name, sup, lines)
        print(f"{name}: {len(lines)} line{'s' if len(lines) != 1 else ''}, "
              + ", ".join(f"{g['code'] or g['item']} x {g['qty']}" for g in lines))
    (out / "hand_assembly.md").write_text(hand_assembly(cfg, design, lost), encoding="utf-8")
    print(f"hand_assembly.md: {len(bought_by_hand(design))} parts by hand, {len(cfg.extras)} items off the board")
    for d in lost:
        lcsc = design.comps[d].get("lcsc")
        print(f"WARNING {d}: no supplier – an LCSC number, `order` in its parts entry or `supplier`"
              + (f" ({lcsc} is an EasyEDA library number, LCSC does not sell it)" if lcsc else ""))
    print(f"→ {cfg.relative(out)}")
    return 0
