"""Dry run: edakit's build ops for the T-Display data against the calls tdisplay_device.py makes (read from the
script's own functions, which only compute: pin_xy, rect_poly – nothing of EasyEDA is called)."""
import importlib.util
import json
import sys
from pathlib import Path

from edakit import config, footprint
from edakit.design import Design
from edakit.release import gate

root = Path(sys.argv[1])            # the copy's variants/esp32
script = Path(sys.argv[2])          # the bell's tdisplay_device.py, imported for its pure functions only
sys.modules["edakit.eda"] = sys.modules.get("edakit.eda") or __import__("edakit.eda").eda
spec = importlib.util.spec_from_file_location("tdisplay_device", script)
td = importlib.util.module_from_spec(spec)
spec.loader.exec_module(td)
cfg = config.load(root / "edakit.toml")
d = Design.from_config(cfg)
e = d.parts["C18722937"]
ops = footprint.build_ops(e)
MIL = td.MIL
worst, shapes, holes = 0.0, [], []
for args in ops["pads"]:
    n = int(args[1])
    x, y = td.pin_xy(n)
    worst = max(worst, abs(args[2] - round(x * MIL, 2)), abs(args[3] - round(y * MIL, 2)))
    d_ = round(td.PAD * MIL, 2)
    want_shape = ["RECT", d_, d_, 0] if n in (1, 13) else ["ELLIPSE", d_, d_]
    shapes.append(args[5][0] == want_shape[0] and all(abs(a - b) < 0.01 for a, b in zip(args[5][1:], want_shape[1:])))
    holes.append(args[7][0] == "ROUND" and abs(args[7][1] - round(td.HOLE * MIL, 2)) < 0.01 and args[0] == 12)
print(f"pads: {len(ops['pads'])} created, largest difference to the script's position {worst:.3f} mil; shapes as the "
      f"script's: {all(shapes)}; holes and layer as the script's: {all(holes)}")
polys = [args for path, args in ops["print"] if path == "PCB_PrimitivePolyline.create"]
texts = [args for path, args in ops["print"] if path == "PCB_PrimitiveString.create"]
script_polys = [(3, td.rect_poly(*td.OUTLINE)), (3, td.rect_poly(*td.USB)), (48, td.rect_poly(*td.OUTLINE))]


def close(a, b):
    return len(a) == len(b) and all(x == y if isinstance(x, str) else abs(x - y) < 0.02 for x, y in zip(a, b))


print("polylines (layer, points) as the script's:",
      all(any(p[1] == layer and close(p[2]["$polygon"], q["$polygon"]) for p in polys) for layer, q in script_polys),
      f"– widths {sorted({p[3] for p in polys})} mil (script: 6)")
print("texts:", [(t[3], t[1], t[2], t[5], t[6], t[7]) for t in texts],
      f"(script: USB at 0, {round(-25.8 * MIL, 2)}; T-Display at 0, {round(18.3 * MIL, 2)}; size "
      f"{round(td.TEXT_MM * MIL, 2)}, width 6, align 5)")
rect, pins = ops["symbol"]
print(f"symbol box: rectangle {rect[:4]} (script: [-60, 65, 120, 130]), {len(pins)} pins, length 10; right side "
      f"top to bottom {[p[2] for p in sorted((p for p in pins if p[4] == 0), key=lambda p: -p[1])][:3]}…, left "
      f"{[p[2] for p in sorted((p for p in pins if p[4] == 180), key=lambda p: -p[1])][:3]}…")
dump = json.loads((root / "hardware/boards/esp32.geometry.json").read_text())["U1"]
box = [round(v * MIL, 2) for v in footprint.box(e["footprint_data"])]
print(f"box of the data {box} mil, the dump's {dump['bbox']} mil – largest difference "
      f"{max(abs(a - b) for a, b in zip(box, dump['bbox'])):.2f} mil")
diffs, unmeasured = footprint.copy_differences(e, dump)
print(f"P-10 on the dump: {diffs or 'no difference'}; not measured: {unmeasured}")
print("hashes:", json.dumps({"state_sha256": gate.state_hash(cfg), "layout_sha256": gate.layout_hash(cfg),
                             "layout files only": gate.file_hash(cfg.root, gate.layout_files(cfg)),
                             "footprint_data": [n for n, _ in gate.footprint_data(cfg)]}, indent=1))
