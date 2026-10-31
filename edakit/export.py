"""Documentation and manufacturing files from EasyEDA into <artifacts>/export/<board>/ (not versioned).

    edakit export [--board B]

Per board (board schematic and PCB):
    schematic_<board>.pdf   the board schematic as vector PDF – needs the patched bridge (bridge-extension-patch.sh);
                            with the original bridge an image stitched from canvas tiles (+ .png)
    pcb_<board>.pdf         PCB, all layers
    gerber_<board>.zip      Gerber and drill files
    bom_<board>.csv         parts of the schematic, grouped by LCSC number
    cpl_<board>.xlsx        pick and place (EasyEDA delivers xlsx even when csv is asked for)
    nets_<board>.txt        netlist of the schematic, one net per line
    odb_<board>.zip         with a maker of [cart] makers that takes ODB++ (AISLER): EasyEDA's ODB++ export – needs the
                            patched server and bridge (easyeda_export_odb, handbook 2.5); on KiCad kicad-cli's
plus <project>.eprj2: a consistent copy of the project file (SQLite backup, state of the last save).

Orders are NOT placed with these files but with the checked ones of the release gate (`edakit gate --easyeda`).
What the bridge cannot do is replaced here: its PDF export always takes the PCB path (the first available function
is called, PCB_ManufactureData.getPdfFile), easyeda_bom_export writes no file and mixes all schematics of the
project, and the netlist export returns nothing.
"""

from __future__ import annotations

import csv
import io
import math
import sqlite3
import time
from pathlib import Path

from . import eda
from .design import natural_key
from .eda import PROJECT, MCPError, api

ZOOM = 200  # percent = pixels per 10 mil x 100 = dpi of the schematic image


def export(mcp, tool, path, **kw):
    res = mcp.call(tool, projectId=PROJECT, filePath=str(path), timeout=300, **kw)
    if res.get("exported") and path.exists() and path.stat().st_size:
        return path.stat().st_size / 1000
    print(f"  ! {path.name}: {res.get('error') or res}")
    return None


def write_bom(mcp, path):
    groups = {}
    for c in api(mcp, "SCH_PrimitiveComponent.getAll") or []:
        if c.get("componentType") != "part" or not c.get("addIntoBom"):
            continue
        g = groups.setdefault(c.get("supplierId") or c.get("manufacturerId"), {"refs": [], "c": c})
        g["refs"].append(c["designator"])
    with path.open("w", newline="", encoding="utf-8") as f:
        out = csv.writer(f)
        out.writerow(["Designator", "Quantity", "Manufacturer Part", "Manufacturer", "Footprint", "LCSC", "JLCPCB Part Class"])
        for g in sorted(groups.values(), key=lambda g: natural_key(min(g["refs"], key=natural_key))):
            c = g["c"]
            out.writerow([",".join(sorted(g["refs"], key=natural_key)), len(g["refs"]), c.get("manufacturerId"),
                          c.get("manufacturer"), (c.get("footprint") or {}).get("name"), c.get("supplierId"),
                          (c.get("otherProperty") or {}).get("JLCPCB Part Class", "")])
    return path.stat().st_size / 1000


def write_netlist(mcp, path, sheet):
    nets = mcp.call("easyeda_schematic_nets", projectId=PROJECT, scope="focused").get("nets", [])
    lines = [f"# netlist of {sheet} from EasyEDA: net: part.pin …"]
    for n in sorted(nets, key=lambda n: n["net_name"]):
        pins = sorted((f"{p['component_ref']}.{p['pin']}" for p in n.get("nodes", [])), key=natural_key)
        if pins:
            lines.append(f"{n['net_name']}: {' '.join(pins)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path.stat().st_size / 1000 if nets else None


def schematic_pdf(mcp, page_uuid, path):
    res = mcp.call("easyeda_export_pdf", projectId=PROJECT, scope="schematic", filePath=str(path), timeout=300)
    if res.get("exported") and path.exists() and path.stat().st_size:
        path.with_suffix(".png").unlink(missing_ok=True)
        return "vector"
    return f"image of {capture_sheet(mcp, page_uuid, path)} tiles (+ .png); vector needs the patched bridge"


def capture_sheet(mcp, page_uuid, path):
    """Capture the page in tiles and stitch them (PNG and PDF of the page size). zoomTo(x, y, zoom) centres on (x, y)
    at zoom/100 pixels per unit; its return value has a wrong 'bottom', so the visible area is computed from centre,
    zoom and image size."""
    from PIL import Image
    info = api(mcp, "DMT_Schematic.getSchematicPageInfo", page_uuid)["titleBlockData"]
    w, h = float(info["Width"]["value"]), float(info["Height"]["value"])
    ppu = ZOOM / 100
    sheet, cols, rows, i = None, 1, 1, 0
    while i < cols * rows:
        cx, cy = (i % cols + 0.5) * w / cols, h - (i // cols + 0.5) * h / rows
        api(mcp, "DMT_EditorControl.zoomTo", cx, cy, ZOOM)
        time.sleep(0.5)
        tile = Image.open(io.BytesIO(mcp.call_image("easyeda_canvas_capture"))).convert("RGB")
        if sheet is None:
            cols, rows = math.ceil(w * ppu / (tile.width * 0.95)), math.ceil(h * ppu / (tile.height * 0.95))
            sheet = Image.new("RGB", (round(w * ppu), round(h * ppu)), "white")
            if cols * rows > 1:
                continue  # first tile again with the right split
        tw, th = w / cols, h / rows
        x0, y0 = round(tile.width / 2 - tw / 2 * ppu), round(tile.height / 2 - th / 2 * ppu)
        sheet.paste(tile.crop((x0, y0, x0 + round(tw * ppu), y0 + round(th * ppu))),
                    (round((cx - tw / 2) * ppu), round((h - cy - th / 2) * ppu)))
        i += 1
    sheet.save(path.with_suffix(".png"), optimize=True)
    sheet.save(path, resolution=ZOOM)
    return cols * rows


def export_board(cfg, mcp, board, out, step=None):
    """step: eda.Steps of `export` – two per board."""
    step = step or (lambda _: None)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    step(f"{board.name}: schematic PDF, netlist, BOM")
    sch, pages = eda.find_pages(mcp, board.schematic)
    eda.focus_page(mcp, sch, pages[0])
    pdf = out / f"schematic_{board.name}.pdf"
    kind = schematic_pdf(mcp, pages[0], pdf)
    rows.append((f"{pdf.name} ({kind})", pdf.stat().st_size / 1000 if pdf.exists() else None))
    rows.append((f"nets_{board.name}.txt", write_netlist(mcp, out / f"nets_{board.name}.txt", board.schematic)))
    rows.append((f"bom_{board.name}.csv", write_bom(mcp, out / f"bom_{board.name}.csv")))
    step(f"{board.name}: PCB PDF, Gerber, pick and place")
    eda.open_pcb(mcp, board.pcb)
    eda.activate_pcb(mcp)
    rows.append((f"pcb_{board.name}.pdf", export(mcp, "easyeda_export_pdf", out / f"pcb_{board.name}.pdf", scope="board")))
    rows.append((f"gerber_{board.name}.zip", export(mcp, "easyeda_export_gerbers", out / f"gerber_{board.name}.zip",
                                                    drillFormat="millimeter", productionReview={"mode": "off"})))
    rows.append((f"cpl_{board.name}.xlsx", export(mcp, "easyeda_export_pick_place", out / f"cpl_{board.name}.xlsx",
                                                  format="csv")))
    from .release import fab
    if fab.odb_takers(cfg):     # a maker of [cart] makers that takes ODB++ (AISLER) – the patched server (2.5)
        rows.append((f"odb_{board.name}.zip", export(mcp, "easyeda_export_odb", out / f"odb_{board.name}.zip",
                                                     unit="mm")))
    for name, kb in rows:
        print(f"  {name:<40} {f'{kb:.0f} kB' if kb is not None else 'missing'}")
    return sum(kb is None for _, kb in rows)


def copy_project(mcp, out):
    """Consistent copy of the project file (SQLite backup, also while EasyEDA writes)."""
    info = api(mcp, "DMT_Project.getCurrentProjectInfo") or {}
    src = Path(info.get("teamUuid") or "") / f"{info.get('friendlyName')}.eprj2"
    if not src.is_file():
        print(f"  ! project file not found: {src}")
        return 1
    dst = out / src.name
    a, b = sqlite3.connect(f"file:{src}?mode=ro", uri=True), sqlite3.connect(dst)
    try:
        a.backup(b)
    finally:
        a.close()
        b.close()
    print(f"  {dst.name:<40} {dst.stat().st_size / 1e6:.1f} MB (copy of {src})")
    return 0


def main(cfg, args):
    from .toolchain import is_kicad
    if is_kicad(cfg):                 # the KiCad project: kicad-cli's exports and a copy of the project (handbook 16)
        from .toolchain.kicad import commands
        return commands.export_main(cfg, args)
    out = cfg.artifact("export", ".keep").parent
    boards = [cfg.board(args.board, made=True)] if args.board else list(cfg.made().values())
    step = eda.Steps(1 + 2 * len(boards) + (0 if args.board else 1))
    step("bridge and project")
    mcp = eda.connect(cfg, args.verbose, artifact_dir=out)  # the export tools write only into the server's ARTIFACT_DIR
    try:
        eda.open_project(mcp, cfg)
        missing = 0
        for board in boards:
            print(f"[{board.name}] -> {out / board.name}")
            missing += export_board(cfg, mcp, board, out / board.name, step)
        if not args.board:
            step("project file")
            missing += copy_project(mcp, out)
        return 2 if missing else 0
    except MCPError as e:
        return eda.die(str(e))
    finally:
        mcp.close()
