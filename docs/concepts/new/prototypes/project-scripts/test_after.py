"""`after`: several writers of one file or EasyEDA datum in a fixed order – green with after, red without."""
import re
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from verify import verify  # noqa: E402

ROOT = Path(os.environ.get("PYTREE_ROOT", "../pytree"))  # a checkout of the reference project
BASE = re.sub(r"\[scripts\.review\].*?(?=\n\[scripts\.mechanik\])", "", (Path(__file__).parent / "pytree.toml").read_text(),
              flags=re.S)
POST = ('\n[scripts.beschriftung]\nkind = "input"\ncmd = ["true"]\nabout = "Jahreszahl in die Baumgrafik"\n'
        'reads = ["hardware/art/baum_vorne.svg"]\nwrites = ["hardware/art/baum_vorne.svg"]\n')
LED = ('\n[scripts.led-bohrungen]\nkind = "easyeda"\ncmd = ["true"]\nabout = "Bohrung und Pad nach PAD_HOLES (D31)"\n'
       'writes = ["footprints:tree"]\n{a1}'
       '\n[scripts.led-plus]\nkind = "easyeda"\ncmd = ["true"]\nabout = "+ an der Anode des Sterns"\n'
       'writes = ["footprints:tree"]\n{a2}')

CASES = {
    "Nachbearbeitung mit after": (None, POST + 'after = ["baumgrafik"]\n'),
    "drei easyeda-Skripte als Kette": (None, LED.format(a1='after = ["led-footprints"]\n', a2='after = ["led-bohrungen"]\n')),
    "Nachbearbeitung ohne after": ("R4", POST),
    "easyeda-Skripte ohne after": ("R4", LED.format(a1="", a2="")),
    "after auf unbekanntes Skript": ("R9", "FW:baumgrafk"),
    "after auf sich selbst": ("R9", "FW:firmware"),
    "after widerspricht den Daten": ("R7", '\n[scripts.rahmen]\nkind = "input"\ncmd = ["true"]\nabout = "x"\n'
                                           'reads = ["hardware/art/baum_vorne.svg"]\nwrites = ["hardware/art/rahmen.svg"]\n'
                                           ),
}
ok = True
with tempfile.TemporaryDirectory() as d:
    for name, (rule, extra) in CASES.items():
        text = BASE + extra
        if extra.startswith("FW:"):                    # firmware shares no output: only R9 may fire
            text = BASE.replace('writes = ["firmware/board.py"]',
                                f'writes = ["firmware/board.py"]\nafter  = ["{extra[3:]}"]')
        if name == "after widerspricht den Daten":     # baumgrafik after rahmen, rahmen reads what baumgrafik writes
            text = text.replace('writes = ["hardware/art/baum_vorne.svg", "hardware/art/baum_hinten.svg"]',
                                'writes = ["hardware/art/baum_vorne.svg", "hardware/art/baum_hinten.svg"]\n'
                                'after  = ["rahmen"]')
            text = text.replace('[boards.tree]\n', '[boards.tree]\n', 1).replace(
                'art_assumed = ["hardware/art/baum_vorne.svg", "hardware/art/baum_hinten.svg"]',
                'art_assumed = ["hardware/art/baum_vorne.svg", "hardware/art/baum_hinten.svg", "hardware/art/rahmen.svg"]')
        p = Path(d) / "case.toml"
        p.write_text(text)
        findings, _, position, order = verify(p, ROOT)
        if rule is None:
            good = not findings
            print(f"{name:32} {'grün' if good else 'FALSCH: ' + '; '.join(findings)}")
            if good:
                part = [o for o in order if o.startswith("[")]
                print(f"{'':32} Skripte in Reihenfolge: {' → '.join(part)}")
                for n in ("led-footprints", "led-bohrungen", "led-plus"):
                    if n in position and "led-plus" in position:
                        print(f"{'':32} {n}: {position[n]}")
        else:
            hit = [f for f in findings if f.startswith(rule)]
            good = bool(hit) and len(hit) == len(findings)
            print(f"{name:32} {'rot, wie erwartet' if good else 'FALSCH'}: {hit[0] if hit else findings}")
        ok &= good
print("after: alle Fälle wie erwartet" if ok else "after: NICHT alle Fälle wie erwartet")
sys.exit(0 if ok else 1)
