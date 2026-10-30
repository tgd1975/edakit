"""edakit silk apply|check on a KiCad project (handbook 16.4): the same placement as for EasyEDA – silk.py computes
where designators, the board label, texts and artwork go –, written into the KiCad PCB with board.write_silk, the
Gerber files from kicad-cli, the DRC KiCad's.

The steps follow silk.apply: hide the designators of the placed side and of [silk] hide, drop edakit's own print of
the last run, export Gerber (the footprints' own print, kept for L-17), artwork and texts, designators, the board
label, then the check on a second export. Sizes: KiCad's text size is the height of a capital, the height edakit asks
for (EasyEDA's em size is converted, silk.font_size; KiCad needs none).
"""

from __future__ import annotations

import shutil

from shapely.geometry import Point, box
from shapely.ops import unary_union

from ... import gerber
from ...config import BOTTOM, MIL_PER_MM, TOP
from ...design import natural_key
from ...silk import (GERBER_KEYS, SIDE, art_shapes, board_label_area, board_label_text, board_shape, corner_spot,
                     fixed_findings, fixed_labels, footprint_print, label_box, label_parts, label_size, picture,
                     place_labels, polygons, printable, side_obstacles, silk_on_openings, silk_texts)
from . import board as kb
from . import cli
from . import commands
from . import fab as kfab

SIDE_NAME = {TOP: "top", BOTTOM: "bottom"}


def export_gerber(cfg, board, verbose=False):
    """kicad-cli's Gerber and drill files under the names silk.py and the gate read, into <artifacts>/gerber_<b>/."""
    out = cfg.artifact(f"gerber_{board.name}", ".keep").parent
    raw = out / "kicad_export"
    shutil.rmtree(raw, ignore_errors=True)
    pcb = kb.paths(cfg, board)["pcb"]
    cli.gerbers(pcb, raw, verbose)
    cli.drill(pcb, raw, verbose)
    for name, text in kfab.normalize(raw, kb.vias(cfg, board)).items():
        (out / name).write_text(text)
    return out


def apply(cfg, board, step=None, verbose=False):
    step = step or (lambda _: None)
    step("hide designators, remove the last run's print")
    s = board.silk
    side = s.get("designators", "top")
    h, gap = float(s.get("label_h_mm", 1.0)), float(s.get("gap_mm", 0.25))
    layer = SIDE[side]
    hide = {SIDE[x] for x in s.get("hide", [])} | {layer}   # the placed side is hidden first, then shown at its spot
    hide_sides = {SIDE_NAME[x] for x in hide}
    kb.write_silk(cfg, board, {}, [], [], hide_sides)
    step("Gerber export: the footprints' own print")
    folder = export_gerber(cfg, board, verbose)
    kept = footprint_print(cfg, board)
    kept.mkdir(parents=True, exist_ok=True)
    for key in ("top_silk", "bottom_silk"):              # kept for the gate: what is not in it is edakit's (L-17)
        if (folder / gerber.FILES[key]).exists():
            shutil.copy(folder / gerber.FILES[key], kept / gerber.FILES[key])
    mask_key, silk_key = GERBER_KEYS[layer]
    openings = gerber.shape(gerber.parse_gerber(folder / gerber.FILES[mask_key]))
    fp_silk = gerber.shape(gerber.parse_gerber(folder / gerber.FILES[silk_key]))
    solder_side = s.get("solder_side", False)
    data = kb.pcb_json(cfg, board)
    comps = {c["designator"]: c for c in data["components"]}
    tht = {r for r, c in comps.items() if any(p["tht"] for p in c["pads"])} if solder_side else set()
    boxes = kb.part_boxes(cfg, board)
    parts = {ref: boxes[ref] for ref in label_parts({r: (c["layer"], r in tht) for r, c in comps.items()}, layer,
                                                     solder_side) if ref in boxes}
    other = [r for r in parts if comps[r]["layer"] != layer]   # solder_side: printed as free texts
    blocked = unary_union([openings.buffer(0.15), fp_silk.buffer(0.15)] + [box(*bb) for bb in parts.values()])
    vias = unary_union([Point(x / MIL_PER_MM, y / MIL_PER_MM).buffer(d / MIL_PER_MM / 2 + 0.1)
                        for x, y, d, _ in kb.vias(cfg, board)])
    area = board_shape(board).buffer(-0.5)
    label_layer = SIDE[s.get("board_label_side", side)]
    label_art = None
    texts_out, fills_out = [], []
    step("artwork and texts")
    for art_side, art_layer in SIDE.items():
        art = art_shapes(cfg, board, art_side)
        texts = silk_texts(board, art_side)
        if art.is_empty and not texts:
            continue
        side_openings = openings if art_layer == layer else gerber.shape(
            gerber.parse_gerber(folder / gerber.FILES[GERBER_KEYS[art_layer][0]]))
        art = printable(art, area, side_openings)
        for p in polygons(art):
            fills_out.append((art_side, [list(p.exterior.coords)] + [list(i.coords) for i in p.interiors]))
        texts_out += [(text, x, y, rot, th, art_side) for text, x, y, rot, th, _ in texts]
        if art_layer in (layer, label_layer):  # designators and the board label keep clear of it
            boxes_t = [label_box(x, y, rot, *label_size(t, th)) for t, x, y, rot, th, _ in texts]
            keep = unary_union([art.buffer(0.3), *[b.buffer(0.3) for b in boxes_t]])
            if art_layer == layer:
                blocked = unary_union([blocked, keep])
            else:
                label_art = keep
        print(f"  {art_side}: artwork {len(polygons(art))} shapes ({art.area:.0f} mm²), {len(texts)} texts")
    step("designators")
    fixed = fixed_labels(board)
    far = "bottom" if side == "top" else "top"
    here = {r: (x, y, rot) for r, (x, y, rot, on) in fixed.items() if r in comps and on == side}
    there = {r: (x, y, rot) for r, (x, y, rot, on) in fixed.items() if r in comps and on != side}
    findings = [f"{r}: in [silk] place, but no part of this board" for r in sorted(fixed, key=natural_key)
                if r not in comps]
    findings += fixed_findings(here, h, area, openings, silk_texts(board, side), side)
    if there:
        findings += fixed_findings(there, h, area, gerber.shape(gerber.parse_gerber(
            folder / gerber.FILES[GERBER_KEYS[SIDE[far]][0]])), silk_texts(board, far), far)
    placed, grouped, missing = place_labels({r: bb for r, bb in parts.items() if r not in there}, blocked, vias, area,
                                            h, gap, s.get("groups"), tuple(s.get("priority", ["TP"])), here)
    labels = [(name, spot, layer) for name, spot in placed.items()] + [(r, v, SIDE[far]) for r, v in there.items()]
    designators = {}
    for name, (x, y, rot), on in labels:
        if name in comps and comps[name]["layer"] == on:
            designators[name] = (x, y, rot, SIDE_NAME[on], h)
        else:     # group label, or a part of the other side: a free text in the same font
            texts_out.append((name, x, y, rot, h, SIDE_NAME[on]))
    step("board label, save")
    text = board_label_text(cfg, board)
    if text:
        lh = float(s.get("board_label_h_mm", 1.2))
        lw, _ = label_size(text, lh)
        if label_layer == layer:
            near = [blocked, *[label_box(x, y, rot, *label_size(name, h)).buffer(0.3) for name, (x, y, rot) in
                               placed.items()]]
        else:
            mk, sk = GERBER_KEYS[label_layer]
            near = [side_obstacles(gerber.shape(gerber.parse_gerber(folder / gerber.FILES[mk])),
                                   gerber.shape(gerber.parse_gerber(folder / gerber.FILES[sk])),
                                   [boxes[r] for r, c in comps.items() if c["layer"] == label_layer and r in boxes],
                                   label_art)]
            near += [label_box(x, y, rot, *label_size(r, h)).buffer(0.3) for r, (x, y, rot) in there.items()]
        keeps = [Point(*board.eda_point(hl["x"], hl["y"])).buffer(hl["keep"]) for hl in board.holes]
        keeps += [Point(*board.eda_point(x, y)).buffer(board.tooling_keep) for x, y in board.tooling]
        corner = s.get("board_label_corner", "bottom-left")
        if label_layer == BOTTOM:  # seen from the bottom, left and right swap
            corner = corner.replace("left", "@").replace("right", "left").replace("@", "right")
        spot = corner_spot(board_label_area(board, area), unary_union([*near, vias, *keeps]), lw, lh, corner)
        where = f" on the {s['board_label_side']}" if label_layer != layer else ""
        if spot:
            texts_out.append((text, *spot, 0, lh, SIDE_NAME[label_layer]))
            print(f"  board label '{text}'{where} at ({spot[0]:.1f}, {spot[1]:.1f}) mm")
        else:
            print(f"  ! board label '{text}': no free spot"
                  + (" in board_label_region" if s.get("board_label_region") else "") + where)
    elif board.revision is None:
        print(f"  ! no board label: set revision in {board.file}")
    kb.write_silk(cfg, board, designators, texts_out, fills_out, hide_sides)
    print(f"  {side}: {sum(1 for n in placed if n in comps)} of {len((set(parts) - set(there)) | set(here))} "
          "designators placed"
          + (f" ({sum(1 for n in placed if n in other)} of {len(other)} through-hole parts of the other side)"
             if solder_side else "")
          + (f", fixed: {', '.join(sorted(here, key=natural_key))}" if here else "")
          + (f", groups {', '.join(g for g in (s.get('groups') or {}) if g in placed)}" if grouped else "")
          + f"; without room: {', '.join(missing) or '–'}")
    for finding in findings:
        print(f"  ! {finding}")
    code = check(cfg, board, fp_silk, step, verbose)
    return 2 if findings else code


def check(cfg, board, footprint_silk=None, step=None, verbose=False):
    step = step or (lambda _: None)
    step("Gerber export: silkscreen on mask openings")
    folder = export_gerber(cfg, board, verbose)
    bad = 0
    for side, layer in SIDE.items():
        silk = gerber.shape(gerber.parse_gerber(folder / gerber.FILES[GERBER_KEYS[layer][1]]))
        own = silk.difference(footprint_silk.buffer(0.02)) if footprint_silk is not None and layer == SIDE[
            board.silk.get("designators", "top")] else silk
        hit, openings = silk_on_openings(folder, layer, own)
        img = cfg.artifact(f"silk_{board.name}_{side}.png")
        picture(silk, openings, board_shape(board), img, mirror=layer == BOTTOM)
        print(f"  {side}: silkscreen on mask openings {hit:.3f} mm² (target 0), picture -> {img}")
        bad += hit > 0.001
    step("DRC")
    pcb = kb.paths(cfg, board)["pcb"]
    code = commands.drc_report(cli.drc(pcb, cfg.artifact("route", f"{board.name}_drc.kicad.json"), verbose=verbose))
    return 2 if bad else code
