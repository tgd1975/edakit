"""Prototype: are the [scripts.*] entries of an edakit.toml resolvable as a DAG together with edakit's own steps?

    python3 verify.py <edakit.toml> --root <project directory>

Rules (each violation is a finding, exit 1):
  R1  kind is input, derive, easyeda or check; the fields that kind needs are there
  R2  every data name (footprints:tree …) is known and names an existing board
  R3  only edakit writes its data and the sources (graph, parts, sim); a script writes files.
      easyeda scripts change data in EasyEDA: they "modify" it and make every step that reads it stale
  R4  several writers of one file (or modifiers of one EasyEDA datum) only in a fixed order: `after` chains them;
      a writer that also reads the file gets the version of the writer before it
  R5  an input is read by an edakit step (board file, [[silk.art]]); otherwise it is a derive
  R6  a derive is read by no edakit step; otherwise it is an input
  R7  the whole graph – edakit's steps in their fixed order, scripts, reads, writes and `after` – has no cycle;
      a cycle is printed with the data on its edges
  R8  a check has an id that is not an edakit stage, a phase, and reads gerber only with at = "after F"
  R9  `after` names other registered scripts only (an agent: other registered agents)
  R10 an agent entry: its file exists, about, signs, phase export or acceptance; scope for an own sign-off
  R11 signs: once per project; an edakit review (M-1, M-5, M-6) only with replaces = the edakit agent that signs it,
      never a sign-off of a human (M-2, M-4)
"""
import argparse
import os
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

SOURCES = ("graph", "parts", "sim")
BOARD_DATA = ("board", "art", "library", "footprints", "routing", "gerber", "release")
# edakit's own steps in their fixed order; <b> = every board
STEPS = [
    ("edakit check", ["graph", "parts"], []),
    ("edakit sim", ["graph", "parts", "sim"], []),
    ("edakit handover", ["graph"], []),
    ("edakit schematic create", ["graph", "parts"], ["library:<b>"]),
    ("edakit schematic layout", ["graph", "library:<b>"], []),
    ("edakit pcb parts", ["board:<b>", "library:<b>"], []),
    ("edakit pcb dump", [], ["footprints:<b>"]),
    ("edakit pcb plan", ["board:<b>", "footprints:<b>", "graph"], []),
    ("edakit pcb apply", ["board:<b>", "footprints:<b>"], []),
    ("edakit route all", ["board:<b>"], ["routing:<b>"]),
    ("edakit silk apply", ["board:<b>", "art:<b>", "footprints:<b>", "routing:<b>"], []),
    ("edakit gate", ["graph", "parts", "sim", "board:<b>", "art:<b>", "footprints:<b>", "routing:<b>"],
     ["gerber:<b>", "release:<b>"]),
]
CHECK_STEP, GATE_STEP = 0, len(STEPS) - 1
EDAKIT_IDS = {"P", "G", "E", "S", "L", "F"}
EDAKIT_AGENTS = {"M-1": ("electrical-reviewer", "circuit"), "M-5": ("pcb-reviewer", "layout"),
                 "M-6": ("regulatory-reviewer", "circuit")}
HUMAN_SIGNOFFS = {"M-2", "M-4"}
REVIEW_POINT = {("circuit", "export"): "Review der Schaltung, vor dem Layout",
                ("layout", "export"): "Review des Layouts, zwischen dem 1. und 2. Gate-Lauf"}


def expand(names, boards):
    return [n.replace("<b>", b) if "<b>" in n else n for n in names for b in (boards if "<b>" in n else [None])]


def as_list(v):
    return [v] if isinstance(v, str) else list(v or [])


def load(cfg_path, root):
    cfg = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    boards, board_files, art = list(cfg.get("boards", {})), {}, defaultdict(set)
    for b, entry in cfg.get("boards", {}).items():
        files = as_list(entry.get("file", f"hardware/boards/{b}.toml"))
        board_files[b] = {os.path.normpath(f) for f in files}
        for f in files:
            if (root / f).exists():
                for a in tomllib.loads((root / f).read_text(encoding="utf-8")).get("silk", {}).get("art", []):
                    if "svg" in a:
                        art[b].add(os.path.normpath(a["svg"]))
        art[b] |= {os.path.normpath(a) for a in entry.get("art_assumed", [])}   # test only: a board file not written yet
    return cfg, boards, board_files, art


def verify(cfg_path, root):
    cfg, boards, board_files, art = load(cfg_path, root)
    scripts = cfg.get("scripts", {})
    findings, notes, position, nodes_extra = [], [], {}, []

    def datum(n):
        """'footprints:tree' -> ('footprints', 'tree'); 'graph' -> ('graph', None); a path -> ('file', path)."""
        if ":" in n and not n.startswith((".", "/")) and n.split(":")[0] in BOARD_DATA + SOURCES:
            return tuple(n.split(":", 1))
        if n in SOURCES:
            return n, None
        return "file", os.path.normpath(n)

    # R1–R3, R9: the entries one by one
    writers = defaultdict(list)     # datum -> scripts that write a file or modify EasyEDA data
    after = {}
    for name, s in scripts.items():
        kind = s.get("kind")
        need = {"input": ("cmd", "about", "writes"), "derive": ("cmd", "about", "writes"),
                "easyeda": ("cmd", "about", "writes"), "check": ("cmd", "about", "id", "phase")}.get(kind)
        if need is None:
            findings.append(f"R1 {name}: kind = {kind!r} – input, derive, easyeda or check")
            continue
        findings += [f"R1 {name}: {f} fehlt" for f in need if f not in s]
        after[name] = as_list(s.get("after"))
        findings += [f"R9 {name}: after = {a!r} – kein anderes registriertes Skript"
                     for a in after[name] if a not in scripts or a == name]
        for n in s.get("reads", []) + s.get("writes", []):
            k, b = datum(n)
            if k in BOARD_DATA and b not in boards:
                findings.append(f"R2 {name}: {n} – keine Platine {b!r} in [boards]")
        for w in s.get("writes", []):
            k, b = datum(w)
            if kind == "easyeda" and k == "file":
                findings.append(f"R3 {name}: easyeda ändert Daten in EasyEDA, keine Datei ({w})")
            elif kind != "easyeda" and k != "file":
                findings.append(f"R3 {name}: schreibt {w} – das schreibt nur edakit")
            else:
                writers[(k, b)].append(name)

    # R4: several writers of one datum need a fixed order through `after`
    def reaches(a, b, seen=None):
        """a comes before b through `after` (b names a, directly or through others)."""
        seen = seen or set()
        return any(x == a or (x not in seen and reaches(a, x, seen | {x})) for x in after.get(b, []))
    chain = {}
    for d, ws in writers.items():
        ordered = sorted(ws, key=lambda w: sum(reaches(o, w) for o in ws))
        if len(ws) > 1 and not all(reaches(x, y) for x, y in zip(ordered, ordered[1:])):
            what = d[1] if d[0] == "file" else ":".join(d)
            findings.append(f"R4 {what}: mehrere Skripte schreiben es ({', '.join(ws)}), aber after legt keine "
                            f"Reihenfolge fest")
        chain[d] = ordered

    def producer(d, reader=None):
        """Who wrote what reader reads: an edakit step, the last script of the chain – or, for a script of the
        chain itself, the one before it."""
        if d in chain and d[0] == "file":
            c = chain[d]
            if reader in c:
                i = c.index(reader)
                return ("script", c[i - 1]) if i else None
            return ("script", c[-1])
        for i, (_, _, writes) in enumerate(STEPS):
            if d in [datum(w) for w in expand(writes, boards)]:
                return ("step", i)
        return None

    def consumers_of_file(f):
        """edakit steps that read file f: a board file or an [[silk.art]] svg."""
        return [i for i, (_, reads, _) in enumerate(STEPS)
                if any((datum(r)[0] == "board" and f in board_files.get(datum(r)[1], ()))
                       or (datum(r)[0] == "art" and f in art.get(datum(r)[1], ())) for r in expand(reads, boards))]

    # the graph: edges with the datum (or rule) that forces them
    edges = defaultdict(dict)
    for i in range(len(STEPS) - 1):
        edges[("step", i)][("step", i + 1)] = "Reihenfolge von edakit"
    for d in [d for d in chain if d[0] == "file"]:
        for i in consumers_of_file(d[1]):
            edges[producer(d)][("step", i)] = d[1]
    for name, s in scripts.items():
        kind, node = s.get("kind"), ("script", name)
        if name not in after:
            continue
        for a in after[name]:
            if a in scripts and a != name:
                edges[("script", a)][node] = "after"
        if kind == "easyeda":
            stale = sorted({i for w in s.get("writes", []) for i, (_, reads, _) in enumerate(STEPS)
                            if w in expand(reads, boards)})
            position[name] = ("auf Befehl" + (f", nach {', '.join(after[name])}" if after[name] else "")
                              + (f"; danach veraltet ab {STEPS[stale[0]][0]}" if stale else ""))
            continue
        for r in s.get("reads", []):
            k, b = datum(r)
            p = producer((k, b), name)
            if p:
                edges[p][node] = r
            elif k == "file" and not (root / b).exists():
                notes.append(f"{name}: liest {b} – gibt es nicht und niemand schreibt es")
        written = [datum(w)[1] for w in s.get("writes", []) if datum(w)[0] == "file"]
        read_by = sorted({i for f in written for i in consumers_of_file(f)})
        if kind == "input":
            if not read_by:
                findings.append(f"R5 {name}: input, aber kein edakit-Schritt liest {', '.join(written)} – derive?")
            else:
                position[name] = f"vor {STEPS[read_by[0]][0]}"
                edges[node][("step", read_by[0])] = ", ".join(written)
        if kind == "derive":
            if read_by:
                findings.append(f"R6 {name}: derive, aber {STEPS[read_by[0]][0]} liest es – input?")
            checker = GATE_STEP if any(datum(r)[0] in BOARD_DATA for r in s.get("reads", [])) else CHECK_STEP
            edges[node][("step", checker)] = "Stempel"
            position[name] = f"Stempel geprüft von {STEPS[checker][0]}"
        if kind == "check":
            sid = str(s.get("id", ""))
            if sid in EDAKIT_IDS or sid.startswith("M-"):
                findings.append(f"R8 {name}: id {sid!r} ist eine Stufe von edakit oder ein Sign-off")
            if s.get("phase") not in ("export", "order", "acceptance"):
                findings.append(f"R8 {name}: phase {s.get('phase')!r} – export, order oder acceptance")
            if s.get("phase") == "export":
                if s.get("at") == "after F":
                    edges[("step", GATE_STEP)][node] = "Stufe nach F"
                    position[name] = "im Gate nach F"
                else:
                    edges[node][("step", GATE_STEP)] = "Stufe zwischen E und S"
                    position[name] = "im Gate zwischen E und S"
            else:
                position[name] = f"Phase {s.get('phase')}, nach dem Gate"
    ids = [str(s.get("id")) for s in scripts.values() if s.get("kind") == "check"]
    findings += [f"R8 id {i!r} mehrfach" for i in sorted({i for i in ids if ids.count(i) > 1})]

    # R10, R11, R9: agents
    agents = cfg.get("agents", {})
    signs = defaultdict(list)
    for name, a in agents.items():
        node = ("agent", name)
        findings += [f"R10 {name}: {f} fehlt" for f in ("file", "about", "signs", "phase") if f not in a]
        if "file" in a and not (root / a["file"]).exists():
            findings.append(f"R10 {name}: file {a['file']} gibt es nicht")
        sid, repl, scope = str(a.get("signs", "")), a.get("replaces"), a.get("scope")
        signs[sid].append(name)
        if sid in HUMAN_SIGNOFFS:
            findings.append(f"R11 {name}: {sid} signiert ein Mensch")
        elif sid in EDAKIT_AGENTS:
            if repl != EDAKIT_AGENTS[sid][0]:
                findings.append(f"R11 {name}: {sid} ist edakits Review – nur mit replaces = "
                                f"{EDAKIT_AGENTS[sid][0]!r}")
            scope = EDAKIT_AGENTS[sid][1]
        else:
            if repl:
                findings.append(f"R11 {name}: replaces = {repl!r}, aber {sid} ist kein Review von edakit")
            scope = a.get("scope")
            if scope not in ("circuit", "layout"):
                findings.append(f"R10 {name}: scope {scope!r} – circuit oder layout")
        phase = a.get("phase")
        if phase not in ("export", "acceptance"):      # order: the owner checks at JLCPCB, no agent gets there
            findings.append(f"R10 {name}: phase {phase!r} – export oder acceptance")
        position[name] = (REVIEW_POINT.get((scope, phase)) or {"acceptance": "nach der Lieferung"}.get(phase, "?")
                          ) + (f", statt {repl}" if repl else "")
        for x in as_list(a.get("after")):
            if x not in agents or x == name:
                findings.append(f"R9 {name}: after = {x!r} – kein anderer registrierter Agent")
            else:
                edges[("agent", x)][node] = "after"
        nodes_extra.append(node)
    findings += [f"R11 {sid} signieren mehrere Agenten ({', '.join(ns)})" for sid, ns in signs.items() if len(ns) > 1]

    # R7: a cycle, printed with the data on its edges; otherwise one valid order
    def label(n):
        return STEPS[n[1]][0] if n[0] == "step" else n[1]
    nodes = [("step", i) for i in range(len(STEPS))] + [("script", n) for n in scripts if n in after] + nodes_extra
    color, stack, cycle = {}, [], None

    def dfs(n):
        nonlocal cycle
        color[n] = 1
        stack.append(n)
        for m in edges.get(n, {}):
            if cycle:
                return
            if color.get(m) == 1:
                cyc = stack[stack.index(m):] + [m]
                cycle = label(cyc[0]) + "".join(f" –[{edges[a][b]}]→ {label(b)}" for a, b in zip(cyc, cyc[1:]))
                return
            if not color.get(m):
                dfs(m)
        stack.pop()
        color[n] = 2
    for n in nodes:
        if not color.get(n) and not cycle:
            dfs(n)
    order = []
    if cycle:
        findings.append(f"R7 Zyklus: {cycle}")
    else:
        # each script right before the first edakit step that needs it; scripts with the same step in their order
        def first_step(n, seen=frozenset()):
            hits = [m[1] if m[0] == "step" else first_step(m, seen | {m}) for m in edges.get(n, {}) if m not in seen]
            hits = [h for h in hits if h is not None]
            return min(hits) if hits else None
        anchored = defaultdict(list)
        for n in nodes:
            if n[0] == "script" and scripts[n[1]].get("kind") != "easyeda":   # easyeda: on command, no place
                anchored[first_step(n)].append(n)

        def topo(group):
            out, rest = [], list(group)
            while rest:
                n = next(n for n in rest if not any(n in edges.get(m, {}) for m in rest if m != n))
                out.append(n)
                rest.remove(n)
            return out
        for i in range(len(STEPS)):
            order += [f"[{n[1]}]" for n in topo(anchored.get(i, []))] + [STEPS[i][0]]
        order += [f"[{n[1]}]" for n in topo(anchored.get(None, []))]
    return findings, notes, position, order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--root", required=True)
    a = ap.parse_args()
    findings, notes, position, order = verify(Path(a.config), Path(a.root))
    print(f"== {a.config}")
    for name, pos in position.items():
        print(f"  {name:15} {pos}")
    for n in notes:
        print(f"  Hinweis: {n}")
    for f in findings:
        print(f"  BEFUND {f}")
    if order:
        print("  Reihenfolge: " + " → ".join(order))
    print("  auflösbar" if not findings else f"  NICHT auflösbar: {len(findings)} Befund(e)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
