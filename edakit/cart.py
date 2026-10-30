"""The order at the maker: what edakit prepares for the skill cart and checks of what it brings back (handbook 8.4).

    edakit cart fields  [--board B] [--maker M]          every field of the maker's form: value, where it comes from
    edakit cart prepare [--board B] [--maker M]          the job of the skill cart, from the current release
    edakit cart check   [--board B] [--maker M] [--cart] B-1 to B-7 on what the skill brought back; --cart: the cart line
    edakit cart actual  [--board B] [--maker M] [--from FILE]   the real cost of the order

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
        regulatory.md     the agent regulatory-reviewer on the order, unchanged (B-7)
        check.md          the result of edakit cart check
        cart.json         the cart line as read back after the cart button (--cart)
        actual.json, actual_page.txt, actual.md   the real cost after the owner ordered and paid

Exit codes: 0 = ok, 2 = findings (the order stops), 1 = error.
"""

from __future__ import annotations

import sys

from . import makers
from .design import Design


class CartError(Exception):
    pass


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


def main(cfg, args):
    try:
        if args.action == "fields":
            return fields(cfg, args)
        raise CartError(f"edakit cart {args.action}: not built yet")
    except (CartError, makers.MakerError) as e:
        print(f"edakit cart: {e}", file=sys.stderr)
        return 1
