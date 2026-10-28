"""What the assembler says about the parts – a dated snapshot – and check P-4 (parts orderable), offline.

    edakit stock [--board B] [--refresh]   ask JLCPCB about every assembled part, write the snapshot
    edakit stock --lcsc C2297 [C…]         print what JLCPCB says about these parts, write nothing (part search)

The snapshot ([project] stock, default hardware/stock.json) is versioned and outside the circuit hash – it records
what the assembler said on a day, not what the circuit is:

    {"date": "2026-10-27", "source": "…", "parts": {"C2297": {"date", "listed", "class", "preferred", "stock", "mpn",
     "assembly_type", "msl", "xray", "mode", "attrition", "min_qty", "price_breaks"}}}

Two public sources, each read by one function: JLCPCB's assembly catalogue, the one F-2 asks (`fab.jlc_part` →
`from_catalogue`: listed, class, stock, MPN, attrition `lossNumber`, minimum `leastPatchNumber`, price breaks), and
the part page jlcpcb.com/partdetail/<C…> (`fetch_part_page` → `from_part_page`: PCBA type "Economic and Standard" or
"Standard Only", MSL, X-ray, machine or hand soldering). Without --refresh only the parts that are missing, unread or
older than [project] stock_max_age_days are asked again.

  P-4  every assembled part (an LCSC number, not bom: false) is in the snapshot and listed, in stock for `quantity`
       boards – under Standard PCBA with the assembler's attrition, max(n + attrition, min_qty) – named as its parts
       entry names it (MPN, case and blanks ignored), and not "Standard Only" on an Economic order (fail). MSL >= 5
       (bake), stock below need x (1 + stock_margin_pct / 100) and another class than the entry's jlc_class warn. A
       part the snapshot lacks or could not read, and a snapshot older than stock_max_age_days, is pending (blocks
       the release only); no snapshot at all is a note.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
import sys
from collections import defaultdict

from .design import Design, natural_key

SOURCE = "JLCPCB assembly catalogue (selectSmtComponentList) and part pages (jlcpcb.com/partdetail/<LCSC>)"
PART_PAGE = "https://jlcpcb.com/partdetail/{}"
CLASS = {"base": "Basic Part", "expand": "Extended Part"}
MODE = {"smtWeld": "smt", "manualWeld": "manual", "furnaceWeld": "reflow"}   # machine, hand, through-hole reflow
STANDARD_ONLY = "Standard Only"
BAKE_MSL = 5        # JLCPCB bakes from MSL 5 on: a fee and two days more


# --- the sources ----------------------------------------------------------------------------------------------------

def from_catalogue(hit):
    """Snapshot fields from the catalogue entry of a part."""
    prices = sorted([int(p["startNumber"]), float(p["productPrice"])] for p in hit.get("componentPrices") or [])
    return {"listed": True, "class": CLASS.get(hit.get("componentLibraryType"), hit.get("componentLibraryType")),
            "preferred": bool(hit.get("preferredComponentFlag")), "stock": int(hit.get("stockCount") or 0),
            "mpn": hit.get("componentModelEn"), "attrition": int(hit.get("lossNumber") or 0),
            "min_qty": int(hit.get("leastPatchNumber") or 0), "price_breaks": prices}


def fetch_part_page(lcsc, timeout=30):
    import urllib.request
    req = urllib.request.Request(PART_PAGE.format(lcsc), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def from_part_page(text, lcsc):
    """Snapshot fields from the part page: the "PCBA Type" cell, and from the page data the part's own record
    (componentCode = lcsc) with moistureSensitivityLevelEn, xrayFlag and assemblyMode."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', text)
    data = "".join(json.loads(c) for c in chunks)
    record = None
    for m in re.finditer(r'"componentCode":"' + re.escape(lcsc) + '"', data):
        nxt = data.find('"componentCode":', m.end())
        part = data[m.end():nxt if nxt > 0 else len(data)]
        if '"moistureSensitivityLevelEn"' in part:
            record = part
            break
    cell = re.search(r">PCBA Type</dt>\s*<dd[^>]*>(?:\s*<[^>]+>)*\s*([^<]+?)\s*<", text)
    if record is None or cell is None:
        raise ValueError(f"{PART_PAGE.format(lcsc)}: no {'record of ' + lcsc if record is None else 'PCBA Type'} "
                         "on the page – has the page changed?")

    def field(name):
        m = re.search(rf'"{name}":(null|true|false|"[^"]*")', record)
        return json.loads(m.group(1)) if m else None
    msl = re.search(r"MSL\s*(\d)", field("moistureSensitivityLevelEn") or "")
    return {"assembly_type": cell.group(1), "msl": int(msl.group(1)) if msl else None, "xray": field("xrayFlag"),
            "mode": MODE.get(field("assemblyMode"), field("assemblyMode"))}


def read_part(lcsc, today=None):
    """One snapshot row, from both sources (network). A part the catalogue does not list is {listed: false}; what
    could not be read is in `error`."""
    from .release import fab
    row = {"date": today or dt.date.today().isoformat()}
    try:
        hit = fab.jlc_part(lcsc)
    except Exception as e:  # network, a changed answer
        return {**row, "error": f"catalogue: {str(e)[:160]}"}
    if not hit:
        return {**row, "listed": False}
    row |= from_catalogue(hit)
    try:
        row |= from_part_page(fetch_part_page(lcsc), lcsc)
    except Exception as e:
        row["error"] = f"part page: {str(e)[:160]}"
    return row


# --- what the project orders ----------------------------------------------------------------------------------------

def assembled(design, board=None):
    """{LCSC number: [designators]} of the parts the assembler places (an LCSC number, not bom: false)."""
    out = defaultdict(list)
    for des, c in design.comps.items():
        if c.get("lcsc") and c.get("bom") is not False and (board is None or c.get("board") == board):
            out[c["lcsc"]].append(des)
    return {k: sorted(v, key=natural_key) for k, v in sorted(out.items(), key=lambda kv: natural_key(kv[0]))}


def need(n, pcba, row):
    """Parts the assembler takes for n placements: exactly n under Economic; under Standard n plus its attrition,
    at least its minimum (the quotes of 2026-10-24 and -25)."""
    if pcba != "standard":
        return n
    return max(n + int(row.get("attrition") or 0), int(row.get("min_qty") or 0))


def refs_text(refs):
    """D2, D3, …, D9 -> 'D2–D9'; runs of three or more designators with one prefix are joined."""
    out, run = [], []

    def flush():
        if len(run) >= 3:
            out.append(f"{run[0][0]}{run[0][1]}–{run[-1][0]}{run[-1][1]}")
        else:
            out.extend(f"{p}{n}" for p, n in run)
    for r in refs:
        m = re.fullmatch(r"(.*?)(\d+)", r)
        if m and run and m.group(1) == run[-1][0] and int(m.group(2)) == run[-1][1] + 1:
            run.append((m.group(1), int(m.group(2))))
            continue
        flush()
        run = [(m.group(1), int(m.group(2)))] if m else []
        if not m:
            out.append(r)
    flush()
    return ", ".join(out)


def same_mpn(a, b):
    norm = lambda s: re.sub(r"\s+", "", str(s or "")).lower()  # noqa: E731
    return norm(a) == norm(b)


def class_differs(catalogue_class, preferred, entry_class):
    """The catalogue's class against the entry's jlc_class ("Basic Part", "Extended Part", "Preferred Extended …").
    An entry that says Extended matches a Preferred Extended part; one that says Preferred needs the flag."""
    if not entry_class or not catalogue_class:
        return False
    e, c = entry_class.lower(), catalogue_class.lower()
    if "basic" in e or "basic" in c:
        return ("basic" in e) != ("basic" in c)
    return "preferred" in e and not preferred


def load(cfg):
    if not cfg.stock or not cfg.stock.exists():
        return None
    return json.loads(cfg.stock.read_text(encoding="utf-8"))


def write(cfg, snap):
    rows = snap["parts"]
    snap = {"date": min((r["date"] for r in rows.values()), default=dt.date.today().isoformat()), "source": SOURCE,
            "parts": {k: rows[k] for k in sorted(rows, key=natural_key)}}
    cfg.stock.parent.mkdir(parents=True, exist_ok=True)
    cfg.stock.write_text(json.dumps(snap, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return snap


def age_days(row, today=None):
    return ((today or dt.date.today()) - dt.date.fromisoformat(row["date"])).days


# --- P-4 ------------------------------------------------------------------------------------------------------------

def check(design, rep, cfg):
    """P-4 on the snapshot, offline."""
    lines = assembled(design)
    if not lines:
        return
    snap = load(cfg)
    where = cfg.relative(cfg.stock) if cfg.stock else "hardware/stock.json"
    if snap is None:
        rep.notes.append(("P-4", f"no stock snapshot ({where}) – edakit stock asks JLCPCB about the {len(lines)} "
                                 "assembled parts"))
        return
    pcba, why = cfg.pcba()
    old = []
    for lcsc, refs in lines.items():
        who = f"{refs_text(refs)} {lcsc}"
        waive = next((w for d in refs if (w := design.comps[d].get("waive")) and "P-4" in w), None)
        row = snap.get("parts", {}).get(lcsc)
        if row is None:
            rep.pending.append(("P-4", f"{who}: not in the stock snapshot – edakit stock"))
            continue
        if row.get("error"):
            rep.pending.append(("P-4", f"{who}: not read on {row.get('date')} ({row['error']}) – edakit stock"))
            continue
        if age_days(row) > cfg.stock_max_age_days:
            old.append(row)
        if not row.get("listed"):
            rep.error("P-4", f"{who}: not in JLCPCB's assembly catalogue on {row['date']} – pre-order only", waive)
            continue
        entry = design.parts.get(lcsc) or {}
        n = len(refs) * cfg.quantity
        want = need(n, pcba, row)
        how = f"{len(refs)} x {cfg.quantity} boards" + (f", attrition {row.get('attrition', 0)}, minimum "
                                                         f"{row.get('min_qty', 0)}" if want != n else "")
        stock = int(row.get("stock") or 0)
        margin = math.ceil(want * (1 + cfg.stock_margin_pct / 100))
        if stock < want:
            rep.error("P-4", f"{who}: {stock} in stock at JLCPCB on {row['date']}, {want} needed ({how})", waive)
        elif stock < margin:
            rep.warnings.append(("P-4", f"{who}: {stock} in stock at JLCPCB on {row['date']}, below {want} needed + "
                                        f"{cfg.stock_margin_pct:g} % ({margin})"))
        if entry.get("mpn") and row.get("mpn") and not same_mpn(entry["mpn"], row["mpn"]):
            rep.error("P-4", f"{who}: JLCPCB names it {row['mpn']}, the parts entry {entry['mpn']}", waive)
        name = f"{who} {row.get('mpn') or entry.get('mpn', '')}".rstrip()
        if row.get("assembly_type") == STANDARD_ONLY and pcba == "economic":
            rep.error("P-4", f"{name}: '{STANDARD_ONLY}' at JLCPCB, the order is Economic ({why}) – solder it by hand "
                             "(bom: false), take another part, or order Standard (assembly.pcba)", waive)
        if (row.get("msl") or 0) >= BAKE_MSL:
            rep.warnings.append(("P-4", f"{name}: MSL {row['msl']} at JLCPCB – baked before assembly (fee and 2 days "
                                        "more)"))
        if class_differs(row.get("class"), row.get("preferred"), entry.get("jlc_class")):
            rep.warnings.append(("P-4", f"{who}: JLCPCB lists it as {row['class']}, the parts entry as "
                                        f"{entry['jlc_class']}"))
    if old:
        oldest = max(age_days(r) for r in old)
        rep.pending.append(("P-4", f"{where}: {len(old)} of {len(lines)} parts read {oldest} days ago "
                                   f"(stock_max_age_days {cfg.stock_max_age_days}) – edakit stock"))


# --- edakit stock ---------------------------------------------------------------------------------------------------

def describe(lcsc, row, refs=None, want=None):
    if row.get("error"):
        return f"{lcsc:<11} not read: {row['error']}"
    if not row.get("listed"):
        return f"{lcsc:<11} not in the assembly catalogue (pre-order only)"
    bits = [row.get("mpn") or "", (row.get("class") or "") + (" (preferred)" if row.get("preferred") else ""),
            f"stock {row.get('stock')}" + (f" / {want} needed" if want is not None else ""),
            f"MSL {row['msl']}" if row.get("msl") is not None else "MSL –", row.get("assembly_type") or "",
            "X-ray" if row.get("xray") else "", "hand-soldered" if row.get("mode") == "manual" else "",
            f"attrition {row.get('attrition', 0)}, min {row.get('min_qty', 0)}"]
    return f"{lcsc:<11} " + (f"{refs_text(refs):<12} " if refs else "") + ", ".join(b for b in bits if b)


def main_lcsc(numbers):
    for i, lcsc in enumerate(numbers, 1):
        print(f"[{i}/{len(numbers)}] {lcsc} …", file=sys.stderr)
        print(describe(lcsc, read_part(lcsc)))
    return 0


def main(cfg, args):
    from .checks import Report
    design = Design.from_config(cfg)
    lines = assembled(design, cfg.board(args.board).name if args.board else None)
    snap = load(cfg) or {"parts": {}}
    rows = snap.setdefault("parts", {})
    todo = [c for c in lines if args.refresh or c not in rows or rows[c].get("error")
            or age_days(rows[c]) > cfg.stock_max_age_days]
    for i, lcsc in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {lcsc} …", flush=True)
        rows[lcsc] = read_part(lcsc)
    snap = write(cfg, snap)
    pcba, why = cfg.pcba()
    print(f"{cfg.relative(cfg.stock)}: {len(todo)} of {len(lines)} assembled parts asked, {pcba} PCBA ({why}), "
          f"{cfg.quantity} boards")
    for lcsc, refs in lines.items():
        row = snap["parts"][lcsc]
        print("  " + describe(lcsc, row, refs, need(len(refs) * cfg.quantity, pcba, row) if row.get("listed") else None))
    rep = Report()
    check(design, rep, cfg)
    for c, m in rep.errors:
        print(f"ERROR   {c}  {m}")
    for c, m, reason in rep.waived:
        print(f"WAIVED  {c}  {m}\n                 reason: {reason}")
    for c, m in rep.pending:
        print(f"PENDING {c}  {m}")
    for c, m in rep.warnings:
        print(f"WARNING {c}  {m}")
    return 2 if rep.errors else 0
