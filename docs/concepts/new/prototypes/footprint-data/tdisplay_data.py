"""Dry run, scratchpad only: the T-Display's footprint as data in the copy of the bell's esp32 variant – the pads'
places as tdisplay_device.py builds them (rows 22.86 mm apart, pitch 2.54 mm, first pin 13.97 mm below the origin),
pad 1.7 mm, hole 1.1 mm, square pads 1 and 13, the outline and the USB box on the silkscreen and as the shape, the
two texts – all from variants/esp32/hardware/lib/tdisplay_device.py – and the symbol as a box (the entry's sides)."""
import json
import sys
from pathlib import Path

f = Path(sys.argv[1])
e = json.loads(f.read_text(encoding="utf-8"))
ROW_X, PITCH, PAD, HOLE, W = 11.43, 2.54, 1.7, 1.1, 0.1524          # tdisplay_device.py; W = its 6 mil lines
OUTLINE = (-12.83, -30.2, 12.83, 21.9)
USB = (-4.6, -29.9, 4.6, -27.9)


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


pads = {}
for n in range(1, 25):
    x = ROW_X if n <= 12 else -ROW_X
    y = round(-5.5 * PITCH + ((n - 1) % 12) * PITCH, 3)
    pads[str(n)] = {"x": x, "y": y, "shape": "RECT" if n in (1, 13) else "ELLIPSE", "w": PAD, "h": PAD,
                    "hole": [HOLE, HOLE]}
e["footprint_data"] = {
    "symbol": "box",
    "origin": [0, 0],
    "pads": pads,
    "lines": [{"points": rect(*OUTLINE), "width": W}, {"points": rect(*USB), "width": W}],
    "texts": [{"text": "USB", "x": 0, "y": -25.8, "size": 1.5, "width": W},
              {"text": "T-Display", "x": 0, "y": 18.3, "size": 1.5, "width": W}],
    "outline": rect(*OUTLINE)[:-1],
}
e["sources"] = [s for s in e["sources"] if not s.startswith("footprint_data:")] + [
    "footprint_data: variants/esp32/hardware/lib/tdisplay_device.py (pads 1.7 mm, holes 1.1 mm, rows 22.86 mm apart, "
    "pitch 2.54 mm, square pads 1 and 13 at the USB end, outline 25.66 x 52.1 mm, USB box, texts USB and T-Display, "
    "lines 6 mil), the dry run of step 3.6"]
f.write_text(json.dumps(e, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{f}: footprint_data with {len(pads)} pads")
