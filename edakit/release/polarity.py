"""Polarity sheet per board (P-2, M-2): every polarised part drawn from the exported Gerber data, with pad number,
pin role from the parts database and net from the graph.

Meant for the comparison with the datasheet drawing (link in the parts entry) and with JLCPCB's assembly preview.
Parts on the bottom side are drawn as seen from below (mirrored). Bright: pads, muted: tracks and pours, white:
silkscreen. Framed in red: parts with an open 'verify' note.
"""

from __future__ import annotations

import json

from PIL import Image, ImageDraw, ImageFont

from .. import gerber

POLAR = ("led", "led_rgb", "diode", "battery_holder", "buzzer", "connector", "npn", "pnp", "pmos", "nmos", "ic",
         "module", "switch", "dip_switch")
MM = 0.0254
TILE, HEAD, COLS = 420, 46, 4
BG, PAD, COPPER, SILK = (18, 58, 32), (236, 170, 70), (120, 85, 40), (245, 245, 245)


def font(size):
    for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_ops(dr, ops, px, scale, colors):
    pad, other = colors
    for kind, dat in ops:
        if kind == "region":
            for c in dat:
                if len(c) >= 3:
                    dr.polygon([px(*p) for p in c], fill=other)
        elif kind == "flash":
            (k, a, b), x, y = dat
            cx, cy = px(x, y)
            bx = [cx - a / 2 * scale, cy - b / 2 * scale, cx + a / 2 * scale, cy + b / 2 * scale]
            bx = [min(bx[0], bx[2]), bx[1], max(bx[0], bx[2]), bx[3]]
            if k == "C":
                dr.ellipse(bx, fill=pad)
            elif k == "R":
                dr.rectangle(bx, fill=pad)
            else:
                dr.rounded_rectangle(bx, radius=min(a, b) / 2 * scale, fill=pad)
        else:
            (_, a, _), pts = dat
            dr.line([px(*p) for p in pts], fill=other, width=max(1, round(a * scale)))


def tile(ref, comp, part, pcb_comp, layers, pin_net):
    pads = pcb_comp["pads"]
    xs, ys = [p["X"] * MM for p in pads], [p["Y"] * MM for p in pads]
    m = 3.0
    x0, x1, y0, y1 = min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m
    mirror = pcb_comp["layer"] == 2
    scale = min(TILE / (x1 - x0), (TILE - HEAD) / (y1 - y0))
    ox = (TILE - (x1 - x0) * scale) / 2
    oy = HEAD + (TILE - HEAD - (y1 - y0) * scale) / 2

    def px(x, y):
        return ox + ((x1 - x) if mirror else (x - x0)) * scale, oy + (y1 - y) * scale
    img = Image.new("RGB", (TILE, TILE), BG)
    dr = ImageDraw.Draw(img)
    cu, silk = layers["B" if mirror else "T"]
    draw_ops(dr, cu, px, scale, (PAD, COPPER))
    draw_ops(dr, silk, px, scale, (SILK, SILK))
    f = font(13)
    at = [px(p["X"] * MM, p["Y"] * MM) for p in pads]
    dense = len(at) > 1 and min(abs(a[0] - b[0]) + abs(a[1] - b[1]) for i, a in enumerate(at) for b in at[i + 1:]) < 95
    order = {i: k for k, i in enumerate(sorted(range(len(pads)), key=lambda i: at[i]))}
    for i, p in enumerate(pads):
        info = (part.get("pins") or {}).get(p["PadNumber"], {})
        role = info.get("role") or info.get("name") or ""
        net = pin_net.get(f"{ref}.{p['PadNumber']}", "–")
        cx, cy = at[i]
        if dense:
            cy += -30 if order[i] % 2 == 0 else 22
        cx, cy = min(max(cx, 45), TILE - 45), min(max(cy, HEAD + 10), TILE - 22)
        label = f"{p['PadNumber']} {role}".strip()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            dr.text((cx + dx, cy + dy), label, font=f, fill=(0, 0, 0), anchor="mm")
            dr.text((cx + dx, cy + 14 + dy), net, font=font(11), fill=(0, 0, 0), anchor="mm")
        dr.text((cx, cy), label, font=f, fill=(255, 255, 120), anchor="mm")
        dr.text((cx, cy + 14), net, font=font(11), fill=(170, 220, 255), anchor="mm")
    dr.rectangle([0, 0, TILE, HEAD], fill=(0, 0, 0))
    dr.text((8, 6), f"{ref}  {part.get('mpn', comp.get('part', ''))}", font=font(16), fill=(255, 255, 255))
    dr.text((8, 26), f"{part.get('lcsc', '')} · {'bottom (mirrored)' if mirror else 'top'}"
            + (" · verify open" if comp.get("verify") else ""), font=font(12), fill=(200, 200, 200))
    if comp.get("verify"):
        dr.rectangle([1, 1, TILE - 2, TILE - 2], outline=(230, 40, 40), width=4)
    return img


def sheet(cfg, board, design, d):
    data = {c["designator"]: c for c in json.loads((d / "pcb.json").read_text())["components"] if c.get("designator")}
    g = d / "gerber"
    layers = {"T": (gerber.parse_gerber(g / gerber.FILES["top"]), gerber.parse_gerber(g / gerber.FILES["top_silk"])),
              "B": (gerber.parse_gerber(g / gerber.FILES["bottom"]), gerber.parse_gerber(g / gerber.FILES["bottom_silk"]))}
    def polar(part):  # electrolytic and tantalum capacitors count as well
        return part.get("kind") in POLAR or (part.get("kind") == "capacitor" and part.get("params", {}).get("polarized"))
    comps = [c for c in design.board_comps(board.name).values() if c["designator"] in data
             and polar(design.part(c["designator"]) or {})]
    comps.sort(key=lambda c: (not c.get("verify"), design.part(c["designator"])["kind"], c["designator"]))
    tiles = [tile(c["designator"], c, design.part(c["designator"]), data[c["designator"]], layers, design.pin_net)
             for c in comps]
    rows = max(1, (len(tiles) + COLS - 1) // COLS)
    img = Image.new("RGB", (COLS * TILE, rows * TILE), (0, 0, 0))
    for i, t in enumerate(tiles):
        img.paste(t, ((i % COLS) * TILE, (i // COLS) * TILE))
    out = d.parent / f"polarity_{board.name}.png"
    img.save(out)
    return out, len(tiles)
