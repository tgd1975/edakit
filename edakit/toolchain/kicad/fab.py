"""Stages L and F on KiCad (handbook 16.6): what release/fab.collect reads from EasyEDA, made from the KiCad project
and kicad-cli – the same files in the same form, so that every check of the gate runs unchanged.

    pcb.json                 board.pcb_json: components with pads, tracks, texts, designators
    drc.json                 cli.drc: KiCad's DRC with schematic parity, as findings (L-3)
    gerber_<board>.zip       Gerber and drill files of kicad-cli under the names the checks know (gerber.FILES):
                             the plated holes of KiCad's PTH file split into component holes and vias by the drill's
                             X2 function (ViaDrill), else by the vias of the PCB
    gerber/                  the ZIP unpacked, plus FlyingProbeTesting.json made from pcb.json – the pad positions
                             gerber.Copper labels the copper with (EasyEDA exports one; KiCad has none, so it stays out
                             of the ZIP)
    cpl_kicad.csv            kicad-cli's position file in the columns of EasyEDA's CPL (F-3)
    bom_kicad.json           the schematic's parts per LCSC number from kicad-cli's netlist, as EasyEDA's BOM (F-1)
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path

from ... import gerber
from ...config import MIL_PER_MM
from ...design import natural_key
from . import board as kb
from . import cli

LAYER_FILES = [("F_Cu", "top"), ("B_Cu", "bottom"), ("F_Silkscreen", "top_silk"), ("F_SilkS", "top_silk"),
               ("B_Silkscreen", "bottom_silk"), ("B_SilkS", "bottom_silk"), ("F_Mask", "top_mask"),
               ("B_Mask", "bottom_mask"), ("Edge_Cuts", "outline"), ("F_Paste", "top_paste"),
               ("B_Paste", "bottom_paste")]
PASTE = {"top_paste": "Gerber_TopPasteMaskLayer.GTP", "bottom_paste": "Gerber_BottomPasteMaskLayer.GBP"}
PROBE_FIELDS = ["PIN_NAME", "PIN_X", "PIN_Y", "NET_NAME", "PIN_TYPE", "LAYER", "PAD_SIZEX", "PAD_SIZEY"]


def file_name(key):
    return gerber.FILES.get(key) or PASTE[key]


def collect(cfg, board, d, verbose=False):
    """Everything stages L and F read, into d (the board's folder of the gate run)."""
    p = kb.paths(cfg, board)
    if not p["pcb"].exists():
        raise SystemExit(f"no KiCad PCB of board {board.name} ({cfg.relative(p['pcb'])}) – edakit pcb apply first")
    for stale in ("netlist_diff.json", "drc_rules.json", "bom_easyeda.json", "cpl_easyeda.xlsx"):
        (d / stale).unlink(missing_ok=True)
    data = kb.pcb_json(cfg, board)
    (d / "pcb.json").write_text(json.dumps(data, indent=1))
    found = cli.drc(p["pcb"], d / "drc_kicad.json", verbose=verbose)
    (d / "drc.json").write_text(json.dumps(found, indent=1, ensure_ascii=False))
    raw = d / "kicad_export"
    shutil.rmtree(raw, ignore_errors=True)
    cli.gerbers(p["pcb"], raw, verbose)
    cli.drill(p["pcb"], raw, verbose)
    files = normalize(raw, kb.vias(cfg, board))
    with zipfile.ZipFile(d / f"gerber_{board.name}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in sorted(files.items()):
            z.writestr(name, text)
    shutil.rmtree(d / "gerber", ignore_errors=True)
    with zipfile.ZipFile(d / f"gerber_{board.name}.zip") as z:
        z.extractall(d / "gerber")
    (d / "gerber" / gerber.FILES["probe"]).write_text(json.dumps(probe(data)))
    write_cpl(cli.pos(p["pcb"], raw / "pos.csv", verbose), data, d / "cpl_kicad.csv")
    if p["sch"].exists():
        _, comps = cli.netlist(p["sch"], raw / "netlist.net", verbose)
    else:                                 # no schematic yet: the PCB's parts (S-2 says the schematic is missing)
        comps = {c["designator"]: {"LCSC": lcsc_of(cfg, board, c["designator"]), "value": c["deviceName"]}
                 for c in data["components"]}
    (d / "bom_kicad.json").write_text(json.dumps(bom(comps), indent=1, ensure_ascii=False))


def lcsc_of(cfg, board, ref):
    fp = kb.load(cfg, board).footprint(ref)
    return (kb.prop(fp, "LCSC") or "") if fp is not None else ""


def normalize(raw, vias):
    """KiCad's Gerber and drill files (folder raw) -> {name the checks know: text}."""
    out = {}
    for f in sorted(Path(raw).glob("*.gbr")):
        stem = f.stem.rsplit("-", 1)[-1] if "-" in f.stem else f.stem
        key = next((k for token, k in LAYER_FILES if stem == token), None)
        if key:
            out[file_name(key)] = f.read_text()
    for f in sorted(Path(raw).glob("*.drl")):
        text = f.read_text()
        if re.search(r"NPTH", f.name, re.I):
            out[gerber.FILES["npth"]] = text
        else:
            parts, via = split_vias(text, vias)
            out[gerber.FILES["pth"]], out[gerber.FILES["vias"]] = parts, via
    lost = [gerber.FILES[k] for k in ("top", "bottom", "top_silk", "bottom_silk", "top_mask", "bottom_mask", "outline",
                                      "pth") if gerber.FILES[k] not in out]
    if lost:
        names = ", ".join(sorted(f.name for f in Path(raw).iterdir()))
        print(f"  kicad-cli exported {names or 'nothing'} – missing for the checks: {', '.join(lost)}")
    return out


def split_vias(text, vias, tol_mm=0.01):
    """One Excellon file of plated holes -> (component holes, vias) as two Excellon files with the same header. A
    tool is a via tool when KiCad's X2 comment before it says ViaDrill; without such comments a hole is a via where the
    PCB has a via (vias: [(x mil, y mil, …)])."""
    lines = text.splitlines()
    head_end = next((i for i, ln in enumerate(lines) if ln.strip() == "%"), None)
    if head_end is None:
        return text, "M48\n%\nM30\n"
    head, body = lines[:head_end], lines[head_end + 1:]
    tools, func = {}, None
    for ln in head:
        if "AperFunction" in ln:
            func = ln
        elif m := re.match(r"^T(\d+)C([\d.]+)", ln):
            tools[int(m.group(1))] = (ln, func)
            func = None
    marked = any(f for _, f in tools.values())
    via_at = {(round(x / MIL_PER_MM, 2), round(y / MIL_PER_MM, 2)) for x, y, *_ in vias}
    hits = defaultdict(list)            # (tool, via?) -> coordinate lines
    cur = None
    for ln in body:
        if m := re.match(r"^T(\d+)$", ln.strip()):
            cur = int(m.group(1))
        elif (m := re.match(r"^X(-?[\d.]+)Y(-?[\d.]+)", ln.strip())) and cur is not None:
            if marked:
                is_via = "ViaDrill" in (tools.get(cur, ("", ""))[1] or "")
            else:
                x, y = float(m.group(1)), float(m.group(2))
                is_via = any(abs(x - vx) <= tol_mm and abs(y - vy) <= tol_mm for vx, vy in via_at)
            hits[(cur, is_via)].append(ln.strip())

    def excellon(want_via):
        used = sorted({t for (t, v) in hits if v == want_via})
        keep = [ln for ln in head if not re.match(r"^T\d+C", ln) and "AperFunction" not in ln]
        out = keep + [tools[t][0] for t in used if t in tools] + ["%", "G90", "G05"]
        for t in used:
            out += [f"T{t}", *hits[(t, want_via)]]
        return "\n".join(out + ["M30"]) + "\n"
    return excellon(False), excellon(True)


def probe(data):
    """FlyingProbeTesting.json as EasyEDA exports it, from pcb.json: every pad with its place (mil, the Gerber
    frame), net, type, layer and size – the size from the footprint geometry is not in pcb.json, so 20 mil."""
    rows = []
    for c in data["components"]:
        for p in c["pads"]:
            rows.append([f"{c['designator']}_{p['PadNumber']}", p["X"], p["Y"], p.get("Net") or "",
                         "THT" if p.get("tht") else "SMD", "B" if p.get("Layer") == 2 else "T", 20, 20])
    return {"pins": {"fields": PROBE_FIELDS, "rows": rows}, "source": "edakit from the KiCad PCB (pcb.json)"}


def write_cpl(rows, data, out):
    """kicad-cli's position rows -> the CPL in the columns of EasyEDA's (Designator, Mid X, Mid Y, Layer T/B,
    Rotation, SMD Yes/No): the place and turn of every part as the manufacturer reads them."""
    tht = {c["designator"]: any(p.get("tht") for p in c["pads"]) for c in data["components"]}
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation", "SMD"])
        for r in sorted(rows, key=lambda r: natural_key(r["ref"])):
            w.writerow([r["ref"], f"{r['x']:.4f}mm", f"{r['y']:.4f}mm", "B" if r["side"] == "bottom" else "T",
                        f"{r['rot'] % 360:g}", "No" if tht.get(r["ref"]) else "Yes"])


def read_cpl(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def bom(comps):
    """The schematic's parts per LCSC number, as fab.merge_bom gives EasyEDA's: [{lcsc, value, reference, quantity}];
    a part KiCad excludes from the BOM is left out."""
    merged = {}
    for ref, fields in sorted(comps.items(), key=lambda kv: natural_key(kv[0])):
        if any(k.lower() in ("exclude_from_bom", "dnp") for k in fields):
            continue
        lcsc = fields.get("LCSC") or fields.get("lcsc") or ""
        m = merged.setdefault(lcsc or fields.get("value", ""), {"lcsc": lcsc, "value": fields.get("value", ""),
                                                                "reference": [], "quantity": 0})
        m["reference"].append(ref)
        m["quantity"] += 1
    return [{**m, "reference": ", ".join(m["reference"])} for m in merged.values()]
