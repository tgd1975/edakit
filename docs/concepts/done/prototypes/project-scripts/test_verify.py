"""Every rule seen red: one fault per copy of the pytree TOML (without review), the expected rule must fire."""
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

FAULTS = {
    "R1 unbekannte Art": ("R1", '\n[scripts.x]\nkind = "build"\ncmd = ["true"]\nabout = "x"\n'),
    "R1 Feld fehlt": ("R1", '\n[scripts.x]\nkind = "derive"\ncmd = ["true"]\nwrites = ["build/x.json"]\n'),
    "R2 Platine unbekannt": ("R2", '\n[scripts.x]\nkind = "derive"\ncmd = ["true"]\nabout = "x"\n'
                                    'reads = ["routing:baum"]\nwrites = ["build/x"]\n'),
    "R3 Skript schreibt edakit-Daten": ("R3", '\n[scripts.x]\nkind = "derive"\ncmd = ["true"]\nabout = "x"\n'
                                              'writes = ["routing:tree"]\n'),
    "R3 easyeda schreibt Datei": ("R3", '\n[scripts.x]\nkind = "easyeda"\ncmd = ["true"]\nabout = "x"\n'
                                        'writes = ["hardware/art/x.svg"]\n'),
    "R4 zwei Schreiber": ("R4", '\n[scripts.x]\nkind = "input"\ncmd = ["true"]\nabout = "x"\n'
                                'writes = ["hardware/art/baum_vorne.svg"]\n'),
    "R5 input liest niemand": ("R5", '\n[scripts.x]\nkind = "input"\ncmd = ["true"]\nabout = "x"\n'
                                     'writes = ["build/x.json"]\n'),
    "R6 derive wird gelesen": ("R6", '\n[scripts.x]\nkind = "derive"\ncmd = ["true"]\nabout = "x"\n'
                                     'writes = ["hardware/boards/tree.toml"]\n'),
    "R7 Eingabe braucht Spaeteres": ("R7", '\n[scripts.x]\nkind = "input"\ncmd = ["true"]\nabout = "x"\n'
                                           'reads = ["routing:tree"]\nwrites = ["hardware/boards/tree.toml"]\n'),
    "R7 Pruefung liest Gerber": ("R7", '\n[scripts.x]\nkind = "check"\nid = "X"\ncmd = ["true"]\nabout = "x"\n'
                                       'phase = "export"\nreads = ["gerber:tree"]\n'),
    "R8 id einer edakit-Stufe": ("R8", '\n[scripts.x]\nkind = "check"\nid = "S"\ncmd = ["true"]\nabout = "x"\n'
                                       'phase = "export"\n'),
    "R8 Phase unbekannt": ("R8", '\n[scripts.x]\nkind = "check"\nid = "X"\ncmd = ["true"]\nabout = "x"\n'
                                 'phase = "spaeter"\n'),
}

ok = True
with tempfile.TemporaryDirectory() as d:
    clean = Path(d) / "clean.toml"
    clean.write_text(BASE)
    findings, _, _, _ = verify(clean, ROOT)
    print(f"{'ohne Fehler (pytree ohne review)':34} {'grün' if not findings else 'ROT: ' + '; '.join(findings)}")
    ok &= not findings
    for name, (rule, extra) in FAULTS.items():
        p = Path(d) / "fault.toml"
        p.write_text(BASE + extra)
        findings, _, _, _ = verify(p, ROOT)
        hit = [f for f in findings if f.startswith(rule)]
        other = [f for f in findings if not f.startswith(rule)]
        print(f"{name:34} {'rot, wie erwartet' if hit and not other else 'FALSCH'}: {hit[0] if hit else findings}")
        ok &= bool(hit) and not other
print("alle Regeln einmal rot gesehen" if ok else "NICHT alle Regeln greifen")
sys.exit(0 if ok else 1)
