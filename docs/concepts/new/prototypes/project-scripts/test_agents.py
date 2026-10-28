"""[agents.*]: pytree's own reviewers – green as registered, red for every rule."""
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
PYTREE = '''
[agents.elektrotechniker]
file     = ".claude/agents/elektrotechniker.md"
about    = "Prüft Schaltung und Übergabe mit pytrees Wissen: Graph, Teile, Simulation, Datenblätter"
signs    = "M-1"
replaces = "electrical-reviewer"
phase    = "export"

[agents.pcb-pruefer]
file     = ".claude/agents/pcb-pruefer.md"
about    = "Prüft das Baum-PCB auf Herstellbarkeit, Mechanik, Bedienbarkeit und Optik"
signs    = "M-5"
replaces = "pcb-reviewer"
phase    = "export"
'''


def agent(name, **kv):
    return f"\n[agents.{name}]\n" + "".join(f"{k} = {v!r}\n".replace("'", '"') for k, v in kv.items())


OWN = dict(file=".claude/agents/pcb-pruefer.md", about="x", signs="M-7", scope="layout", phase="export")
CASES = {
    "pytrees zwei Agenten, mit replaces": (None, PYTREE),
    "eigenes Sign-off M-7": (None, agent("optik", **OWN)),
    "Datei fehlt": ("R10", agent("optik", **{**OWN, "file": ".claude/agents/optik.md"})),
    "Phase unbekannt": ("R10", agent("optik", **{**OWN, "phase": "spaeter"})),
    "Phase order (dort prueft der Besitzer)": ("R10", agent("optik", **{**OWN, "phase": "order"})),
    "scope fehlt beim eigenen Sign-off": ("R10", agent("optik", **{k: v for k, v in OWN.items() if k != "scope"})),
    "M-5 ohne replaces": ("R11", agent("optik", **{**OWN, "signs": "M-5"})),
    "replaces den falschen Agenten": ("R11", agent("optik", **{**OWN, "signs": "M-5", "replaces": "electrical-reviewer"})),
    "Sign-off eines Menschen": ("R11", agent("optik", **{**OWN, "signs": "M-2"})),
    "zwei Agenten, ein Sign-off": ("R11", agent("optik", **OWN) + agent("optik2", **OWN)),
    "replaces bei eigenem Sign-off": ("R11", agent("optik", **{**OWN, "replaces": "pcb-reviewer"})),
    "after auf unbekannten Agenten": ("R9", agent("optik", **{**OWN, "after": "optiker"})),
    "after im Kreis": ("R7", agent("a", **{**OWN, "after": "b"}) + agent("b", **{**OWN, "signs": "M-8", "after": "a"})),
}
ok = True
with tempfile.TemporaryDirectory() as d:
    for name, (rule, extra) in CASES.items():
        p = Path(d) / "case.toml"
        p.write_text(BASE + extra)
        findings, _, position, _ = verify(p, ROOT)
        if rule is None:
            good = not findings
            print(f"{name:36} {'grün' if good else 'FALSCH: ' + '; '.join(findings)}")
            for n in ("elektrotechniker", "pcb-pruefer", "optik"):
                if n in position and n in extra:
                    print(f"{'':36} {n}: {position[n]}")
        else:
            hit = [f for f in findings if f.startswith(rule)]
            good = bool(hit) and len(hit) == len(findings)
            print(f"{name:36} {'rot, wie erwartet' if good else 'FALSCH'}: {hit[0] if hit else findings}")
        ok &= good
print("Agenten: alle Fälle wie erwartet" if ok else "Agenten: NICHT alle Fälle wie erwartet")
sys.exit(0 if ok else 1)
