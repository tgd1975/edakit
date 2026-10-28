"""Project scripts: the entries [scripts.<name>] of edakit.toml and edakit's own steps, resolved into one order.

    edakit check     reports what keeps the entries from resolving (handbook 8.6)

A project registers the scripts that touch edakit's flow: a script writes a file edakit reads, derives something from
edakit's data, changes the project library in EasyEDA, or holds up the release as a check of its own. Its entry says
what it reads and writes; when it runs follows from that and from edakit's steps in their fixed order (STEPS). Nothing
is run here.

  kind     when                                                     what it writes
  input    before the first edakit step that reads what it writes   a file edakit reads: the board file (board:<b>),
                                                                    an SVG of [[silk.art]], the simulation plugin
  derive   before edakit check, where its result is to be current;  files no edakit step reads
           before the gate when it reads what comes after edakit check
  easyeda  on command only                                          project-library:<b> in EasyEDA
  check    phase export: in the gate before S, or at "after F";     nothing
           phase order and acceptance: after the gate
  sim      inside edakit sim: [project] sim_plugin                  nothing
[[release.stages]] are checks of phase export before S.

Names of edakit's data in reads and writes: graph, parts, sim (written by hand, edakit block, edakit part), board:<b>
(the board file), project-library:<b> (EasyEDA's project library: schematic create, easyeda scripts), footprints:<b>
(pcb_geometry_<b>.json: pcb dump), mech:<b> (pcb plan), routing:<b> (route), gerber:<b> and release (the gate),
firmware (edakit firmware, with [firmware]). Anything else is a path relative to edakit.toml: a folder holds the files
in it, and an edakit file named by its path is its data (hardware/boards/<b>.toml is board:<b>). Each name has a hash
of what edakit has of it offline (data_hash) – the project library none, it is in EasyEDA only.

The entries resolve when (docs/concepts/new/project-scripts.md, "Checking the TOML", its rules 1 to 9; 10 and 11 are
about agents):
  1  kind is input, derive, easyeda or check, the fields of the kind are there, and no field of another kind
  2  every data name is edakit's, with a board of [boards]; firmware only with [firmware]
  3  a script writes files, an input also board:<b>; an easyeda script changes project-library:<b> – footprints:<b> is
     the geometry pcb dump measures, edakit's own data like the others
  4  scripts that write the same file or change the same data run in a fixed order through after
  5  an edakit step needs what an input writes, directly or through another input
  6  no edakit step needs what a derive writes
  7  edakit's steps, the data and after make no cycle – read-backs of a later round are not counted: edakit check
     reads the footprints (P-7), edakit sim the routing (copper), pcb place the footprints
  8  a check has an id of its own, a phase, and reads gerber:<b> only at "after F"
  9  after names other entries of [scripts]
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from . import rules

KINDS = ("input", "derive", "easyeda", "check")      # of a [scripts.*] entry; the kind sim is [project] sim_plugin
NEEDS = {"input": ("cmd", "about", "writes"), "derive": ("cmd", "about", "writes"),
         "easyeda": ("cmd", "about", "writes"), "check": ("cmd", "about", "id", "phase")}
MAKER = ("kind", "cmd", "about", "reads", "writes", "after", "check")
FIELDS = {"input": MAKER, "derive": MAKER, "easyeda": MAKER,
          "check": ("kind", "cmd", "about", "reads", "after", "id", "phase", "at", "advisory")}
PHASES = ("export", "order", "acceptance")           # of a check, as of the gate's manual checks
PLACES = ("before S", "after F")                     # at: where a check of phase export runs in the gate
GATE_STAGES = ("P", "G", "E", "S", "L", "F")
SOURCES = ("graph", "parts", "sim")                  # written by hand, edakit block, edakit part
ONCE = ("release", "firmware")                       # one per project
PER_BOARD = ("board", "project-library", "footprints", "mech", "routing", "gerber")   # <name>:<b>
IN_EASYEDA = ("project-library",)                    # what an easyeda script changes
MADE_BY = {"graph": "hand or edakit block", "parts": "hand or edakit part", "sim": "hand",
           "project-library": "edakit schematic create, changed by easyeda scripts", "footprints": "edakit pcb dump",
           "mech": "edakit pcb plan", "routing": "edakit route", "gerber": "the gate", "release": "the gate",
           "firmware": "edakit firmware"}
ABSENT = "absent"      # data_hash of data that does not exist yet: no gate run, no geometry, no routing, no contract
NAME = re.compile(r"([A-Za-z][\w-]*)(?::([^/\\]*))?")   # graph, routing:tree; a word:word that is none is a typo

# edakit's steps in their fixed order, with what each reads and writes. <b> stands for every board, art:<b> for the
# SVGs of the board files' [[silk.art]], plugin for [project] sim_plugin. Left out are the read-backs of a later round:
# edakit check reads the footprints (P-7), edakit sim the routing (with copper), pcb place the footprints.
STEPS = (
    ("edakit firmware", ("graph", "parts", "sim", "plugin"), ("firmware",)),
    ("edakit check", ("graph", "parts", "sim"), ()),
    ("edakit sim", ("graph", "parts", "sim", "plugin"), ()),
    ("edakit handover", ("graph", "parts"), ()),
    ("edakit schematic create", ("graph", "parts"), ("project-library:<b>",)),
    ("edakit schematic layout", ("graph", "project-library:<b>"), ()),
    ("edakit pcb place", ("graph", "parts", "board:<b>"), ("board:<b>",)),
    ("edakit pcb parts", ("graph", "board:<b>", "project-library:<b>"), ()),
    ("edakit pcb dump", (), ("footprints:<b>",)),
    ("edakit pcb plan", ("graph", "parts", "board:<b>", "footprints:<b>"), ("mech:<b>",)),
    ("edakit pcb apply", ("board:<b>", "footprints:<b>"), ()),
    ("edakit route all", ("graph", "board:<b>", "footprints:<b>"), ("routing:<b>",)),
    ("edakit silk apply", ("board:<b>", "art:<b>", "footprints:<b>", "routing:<b>"), ()),
    ("edakit gate", ("graph", "parts", "sim", "plugin", "board:<b>", "art:<b>", "footprints:<b>", "routing:<b>"),
     ("gerber:<b>", "release")),
)
CHECK, SIM, GATE = 1, 2, len(STEPS) - 1


class Finding(NamedTuple):
    rule: int       # the concept's rule, 1 to 9 – for the tests; edakit prints only msg
    msg: str        # starts with the script's name


class Resolution(NamedTuple):
    findings: list  # [Finding]
    order: list     # edakit's steps and the scripts in one order that keeps every edge – easyeda scripts run on
                    # command and have no place in it; empty when the entries do not resolve


@dataclass
class _Entry:
    node: tuple                 # ("script", name), ("stage", i) of [[release.stages]], ("sim", None) of sim_plugin
    label: str                  # how a message names it
    kind: str
    raw: dict
    reads: list = field(default_factory=list)      # (spelling, key)
    writes: list = field(default_factory=list)     # (spelling, key)
    after: list = field(default_factory=list)      # names of other entries of [scripts]
    phase: str | None = None    # a check's phase and place
    at: str | None = None
    flawed: bool = False        # a field or a name is wrong: rule 5 would only repeat it


class _Names:
    """Data names and paths as keys: ("graph", None), ("board", "tree"), ("file", "hardware/art/x.svg")."""

    def __init__(self, cfg):
        self.cfg = cfg
        own = {cfg.graph: ("graph", None), cfg.sim_config: ("sim", None)}
        for b, board in cfg.boards.items():
            own[cfg.resolve(board.file)] = ("board", b)
            own[cfg.artifacts / f"pcb_geometry_{b}.json"] = ("footprints", b)
            own[cfg.artifacts / f"mech_{b}.json"] = ("mech", b)
        if cfg.firmware is not None:
            own[cfg.resolve(cfg.firmware["out"])] = ("firmware", None)
        self.own = {self.path(p): key for p, key in own.items()}
        self.parts = self.path(cfg.parts)

    def path(self, p):
        """A path as entries are compared: relative to the project when inside it, normalised, without a final /."""
        p = Path(os.path.normpath(self.cfg.resolve(p)))
        return p.relative_to(self.cfg.root).as_posix() if p.is_relative_to(self.cfg.root) else p.as_posix()

    def parse(self, spelling):
        """(key, why): the key of a data name or a path; why says what is wrong with a name of edakit's data. The key
        keeps the kind of data also then, so that what a script may write is judged first."""
        m = NAME.fullmatch(spelling)
        if m and m[1] in SOURCES + ONCE + PER_BOARD:
            kind, board = m[1], m[2]
            if kind not in PER_BOARD:
                return (kind, None), None if board is None else f"{kind} has no board – there is one per project"
            if not board:
                return (kind, None), f"{kind} is data of a board: {kind}:<b>"
            if board not in self.cfg.boards:
                return (kind, board), f"no board {board} in [boards] ({', '.join(self.cfg.boards)})"
            return (kind, board), None
        if m and m[2] is not None:
            return None, ("no data name of edakit (graph, parts, sim, release, firmware; board, project-library, "
                          "footprints, mech, routing, gerber with :<b>)")
        p = self.path(spelling)
        if p in self.own:
            return self.own[p], None
        if p == self.parts or p.startswith(self.parts + "/"):
            return ("parts", None), None
        return ("file", p), None


def _spell(key):
    """A key as a message names it: the data name or the path."""
    kind, arg = key
    return arg if kind == "file" else f"{kind}:{arg}" if arg is not None else kind


def _overlap(a, b):
    """Two keys name the same data: equal, or a folder and a file in it."""
    return a == b or a[0] == b[0] == "file" and (a[1].startswith(b[1] + "/") or b[1].startswith(a[1] + "/"))


def _a(kind):
    return ("an " if kind[0] in "aeiou" else "a ") + kind


def _reach(start, edges):
    """The nodes reachable from start (start itself only through a cycle)."""
    seen, todo = set(), list(edges.get(start, {}))
    while todo:
        n = todo.pop()
        if n not in seen:
            seen.add(n)
            todo += edges.get(n, {})
    return seen


def _cycle(start, edges):
    """The shortest path from start back to start, or None."""
    parent, todo = {start: None}, deque([start])
    while todo:
        n = todo.popleft()
        for m in edges.get(n, {}):
            if m == start:
                path = [n]
                while parent[path[-1]] is not None:
                    path.append(parent[path[-1]])
                return path[::-1] + [start]
            if m not in parent:
                parent[m] = n
                todo.append(m)
    return None


def _step_data(cfg, names):
    """Per step of STEPS: the keys it reads and the keys it writes, for every board."""
    art = {("file", names.path(a["svg"])) for board in cfg.boards.values()
           for a in (board.silk.get("art") if isinstance(board.silk.get("art"), list) else [])
           if isinstance(a, dict) and isinstance(a.get("svg"), str)}
    plugin = {("file", names.path(cfg.sim_plugin))} if cfg.sim_plugin else set()

    def keys(spec):
        out = set()
        for n in spec:
            if n == "plugin":
                out |= plugin
            elif n == "art:<b>":
                out |= art
            elif n.endswith(":<b>"):
                out |= {(n[:-4], b) for b in cfg.boards}
            else:
                out.add((n, None))
        return out
    return [keys(r) for _, r, _ in STEPS], [keys(w) for _, _, w in STEPS]


def _entries(cfg, names, finding):
    """[scripts.*], [[release.stages]] and sim_plugin as entries, each checked on its own: kind and fields (rule 1),
    data names (2), what it may write (3), a check's phase and place (8), after (9)."""
    entries = []
    for name, s in cfg.scripts.items():
        kind = s.get("kind")
        if kind not in KINDS:
            finding(1, f"{name}: kind is missing – a script is input, derive, easyeda or check" if kind is None else
                    f'{name}: kind = "{kind}" – ' + ("the simulation plugin is [project] sim_plugin; " if kind == "sim"
                                                     else "") + "a script is input, derive, easyeda or check")
            continue
        e = _Entry(("script", name), name, kind, s, phase=s.get("phase"), at=s.get("at"))
        entries.append(e)
        if missing := [f for f in NEEDS[kind] if not s.get(f)]:
            finding(1, f"{name}: {', '.join(missing)} missing – {_a(kind)} script needs {', '.join(NEEDS[kind])}")
            e.flawed = True
        if foreign := [f for f in s if f not in FIELDS[kind]]:
            finding(1, f"{name}: no field of {_a(kind)} script: {', '.join(foreign)}")
        if kind == "check":
            if e.phase is not None and e.phase not in PHASES:
                finding(8, f'{name}: phase = "{e.phase}" – export, order or acceptance')
            if e.at is not None and e.at not in PLACES:
                finding(8, f'{name}: at = "{e.at}" – "before S" or "after F"')
            elif e.at is not None and e.phase in ("order", "acceptance"):
                finding(8, f'{name}: at = "{e.at}" is a place in the gate – a check of phase {e.phase} runs after it')
        for spelling in s.get("reads", []):
            key, why = names.parse(spelling)
            if why is None and key == ("firmware", None) and cfg.firmware is None:
                why = "edakit.toml has no [firmware]: edakit firmware writes no contract"
            if why:
                finding(2, f"{name}: reads {spelling} – {why}")
                e.flawed = True
            elif kind == "check" and key[0] == "gerber" and e.phase == "export" and e.at in (None, "before S"):
                finding(8, f'{name}: reads {spelling}, which the gate makes in stage F – the check needs at = "after F"')
            else:
                e.reads.append((spelling, key))
        for spelling in s.get("writes", []) if kind != "check" else ():
            key, why = names.parse(spelling)
            what = spelling if key is None or key[0] == "file" or _spell(key) == spelling \
                else f"{spelling} ({_spell(key)})"
            if key is not None and kind == "easyeda" and key[0] not in IN_EASYEDA:
                made = f"made by {MADE_BY[key[0]]}; " if key[0] in MADE_BY else ""
                board = key[1] if key[0] != "file" and key[1] in cfg.boards else "<b>"
                finding(3, f"{name}: writes {what} – {made}an easyeda script changes the project library in EasyEDA: "
                           f"project-library:{board}")
                e.flawed = True
            elif key is not None and kind != "easyeda" and key[0] not in ("file", "board"):
                finding(3, f"{name}: writes {what} – made by {MADE_BY[key[0]]}; a script writes files, an input also "
                           "board:<b>")
                e.flawed = True
            elif why:
                finding(2, f"{name}: writes {spelling} – {why}")
                e.flawed = True
            else:
                e.writes.append((spelling, key))
        for a in s.get("after", []):
            if a == name:
                finding(9, f"{name}: after names itself")
            elif a not in cfg.scripts:
                finding(9, f"{name}: after names {a} – there is no [scripts.{a}]")
            else:
                e.after.append(a)
    stages = cfg.release.get("stages", [])
    for i, st in enumerate(stages if isinstance(stages, list) else [], 1):
        if isinstance(st, dict):
            label = f"[[release.stages]] {st.get('id') or i}"
            entries.append(_Entry(("stage", i), label, "check", st, phase="export"))
            if missing := [f for f in ("id", "name", "cmd") if not st.get(f)]:
                finding(1, f"{label}: {', '.join(missing)} missing – the gate runs a project stage by id, name and "
                           "cmd")
    if cfg.sim_plugin:
        p = names.path(cfg.sim_plugin)
        entries.append(_Entry(("sim", None), "sim_plugin", "sim", {}, reads=[(p, ("file", p))]))
    ids = defaultdict(list)
    for e in entries:
        if e.kind == "check" and e.raw.get("id"):
            sid = str(e.raw["id"])
            ids[sid].append(e.label)
            why = ("a stage of the gate" if sid in GATE_STAGES else "a sign-off" if sid.startswith("M-") else
                   "an ID of the rule catalog" if rules.entry(sid) else None)
            if why:
                finding(8, f"{e.label}: id {sid} is {why} – a check needs an id of its own")
    for sid, labels in ids.items():
        if len(labels) > 1:
            finding(8, f"{', '.join(labels)}: the same id {sid} – each check needs an id of its own")
    return entries


def resolve(cfg) -> Resolution:
    """The entries of cfg with edakit's steps: what keeps them from resolving, and else one order."""
    found = []

    def finding(rule, msg):
        found.append(Finding(rule, msg))
    names = _Names(cfg)
    entries = _entries(cfg, names, finding)
    after = {e.label: e.after for e in entries if e.node[0] == "script"}
    before = {}
    for n in after:                                     # the scripts that run before n through after
        before[n], todo = set(), list(after[n])
        while todo:
            if (m := todo.pop()) not in before[n]:
                before[n].add(m)
                todo += after.get(m, [])

    def earlier(a, b):
        return a.node[0] == b.node[0] == "script" and a.label in before[b.label]

    # rule 4: scripts that write the same file or change the same data, in a fixed order through after
    unordered = {}
    writers = [e for e in entries if e.writes]
    for i, a in enumerate(writers):
        for b in writers[i + 1:]:
            if earlier(a, b) or earlier(b, a):
                continue
            for ka in [k for _, k in a.writes]:
                for kb in [k for _, k in b.writes if _overlap(ka, k)]:
                    shared = max(_spell(ka), _spell(kb), key=len)
                    verb, who = unordered.setdefault(shared, ["change" if a.kind == "easyeda" else "write", []])
                    who += [n for n in (a.label, b.label) if n not in who]
    for shared, (verb, who) in unordered.items():
        finding(4, f"{', '.join(who)}: {'both' if len(who) == 2 else 'all'} {verb} {shared}, but after sets no order "
                   "between them")

    # the graph: edakit's steps in their order, the data, after, and where checks, stamps and the plugin hang
    edges = defaultdict(dict)

    def edge(a, b, why):
        if a != b:
            edges[a].setdefault(b, why)
    steps = [("step", i) for i in range(len(STEPS))]
    for a, b in zip(steps, steps[1:]):
        edge(a, b, "")
    reads_of, writes_of = _step_data(cfg, names)
    makers = [e for e in entries if e.kind in ("input", "derive")]   # what they write, the others read

    def writes(e, key):
        return any(_overlap(key, k) for _, k in e.writes)
    for e in entries:          # a script reads from the scripts and the step that make it; one that writes what it
        if e.kind == "easyeda":    # reads gets the version of the writers before it. easyeda: on command, no place
            continue
        for spelling, key in e.reads:
            own = writes(e, key)
            for w in makers:
                if w is not e and writes(w, key) and (not own or earlier(w, e)):
                    edge(w.node, e.node, spelling)
            for i, made in enumerate(writes_of):
                if not own and any(_overlap(key, k) for k in made):
                    edge(steps[i], e.node, spelling)
    for w in makers:           # a step reads what scripts write
        for spelling, key in w.writes:
            for i, read in enumerate(reads_of):
                if any(_overlap(key, k) for k in read):
                    edge(w.node, steps[i], spelling)
    scripts = {e.label: e for e in entries if e.node[0] == "script"}
    for e in entries:
        for a in e.after:
            if a in scripts:
                edge(scripts[a].node, e.node, "after")
        if e.kind == "sim":
            edge(e.node, steps[SIM], "plugin")
        elif e.kind == "check" and e.phase == "export" and e.at in (None, "before S"):
            edge(e.node, steps[GATE], "before S")
        elif e.kind == "check" and e.phase == "export" and e.at == "after F":
            edge(steps[GATE], e.node, "after F")
        elif e.kind == "check" and e.phase in ("order", "acceptance") and e.at is None:
            edge(steps[GATE], e.node, f"phase {e.phase}")
    later = _reach(steps[CHECK], edges)     # a derive among what comes after edakit check: its stamp waits for the gate
    for e in entries:
        if e.kind == "derive":
            edge(e.node, steps[GATE] if e.node in later else steps[CHECK], "stamp")

    # rules 5 and 6: what an input writes, an edakit step needs – directly or through another input; a derive not
    def needs(keys, seen):
        out = set()
        for key in keys:
            out |= {i for i, read in enumerate(reads_of) if any(_overlap(key, k) for k in read)}
            for r in entries:
                if r.kind == "input" and r.node not in seen and any(_overlap(key, k) for _, k in r.reads):
                    out |= needs([k for _, k in r.writes], seen | {r.node})
        return out
    for e in entries:
        if e.kind == "input" and not e.flawed and not needs([k for _, k in e.writes], {e.node}):
            finding(5, f"{e.label}: an input, but no edakit step reads what it writes "
                       f"({', '.join(s for s, _ in e.writes)}) – a derive? edakit reads the board file (board:<b>), "
                       "the SVGs of [[silk.art]] and [project] sim_plugin")
        if e.kind == "derive":
            hits = {s: hit for s, k in e.writes if (hit := needs([k], {e.node}))}
            if hits:
                first = min(min(i) for i in hits.values())
                finding(6, f"{e.label}: a derive, but {STEPS[first][0]} needs what it writes ({', '.join(hits)}) – "
                           "an input?")

    # rule 7: no cycle – each one named once, from its first script, with the data on its edges
    labels = {**{s: STEPS[s[1]][0] for s in steps}, **{e.node: e.label for e in entries}}
    cyclic = set()
    for e in entries:
        if e.node not in cyclic and (cycle := _cycle(e.node, edges)):
            cyclic |= {n for n in _reach(e.node, edges) if e.node in _reach(n, edges)}
            finding(7, f"{e.label}: in a cycle – " + labels[cycle[0]] + "".join(
                (f" –[{edges[a][b]}]→ " if edges[a][b] else " → ") + labels[b] for a, b in zip(cycle, cycle[1:])))
    return Resolution(found, _order(steps, entries, edges, labels) if not found else [])


def _order(steps, entries, edges, labels):
    """One order that keeps every edge: each script just before the first of edakit's steps it comes before."""
    nodes = steps + [e.node for e in entries]
    first = {}

    def first_step(n):
        if n[0] == "step":
            return n[1]
        if n not in first:
            first[n] = min((first_step(m) for m in edges.get(n, {})), default=len(STEPS))
        return first[n]
    rank = {n: (first_step(n), n[0] == "step", i) for i, n in enumerate(nodes)}
    count = defaultdict(int)
    for a in edges:
        for b in edges[a]:
            count[b] += 1
    ready, out = [n for n in nodes if not count[n]], []
    while ready:
        n = min(ready, key=rank.__getitem__)
        ready.remove(n)
        out.append(n)
        for m in edges.get(n, {}):
            count[m] -= 1
            if not count[m]:
                ready.append(m)
    on_command = {e.node for e in entries if e.kind == "easyeda"}
    return [labels[n] for n in out if n not in on_command]


# --- the hash of each name ------------------------------------------------------------------------------------------

def data_hash(cfg, name):
    """The hash of one of edakit's data, by its name as reads and writes spell it (an edakit file named by its path is
    its data): the SHA-256 of what edakit has of it offline, ABSENT while the data does not exist. None for
    project-library:<b>: the project library is in EasyEDA only and has no offline hash – what changes it is an easyeda
    script, and running the script is what tells edakit. A name that is not edakit's data: ValueError; a manifest that
    is not readable: gate.ReleaseError, as in edakit release.

      graph, parts, sim   the files as the circuit hash reads them – graph and parts without [release] hash_ignore
      board:<b>           the board file
      footprints:<b>      pcb_geometry_<b>.json, the geometry edakit pcb dump measures
      mech:<b>            mech_<b>.json of edakit pcb plan
      routing:<b>         the tracks and vias of edakit route: route/<b>.ses, and route/<b>_stitch.json where route
                          pours stitched islands with vias
      gerber:<b>          the board's fab_layers in the last gate run with manufacturing files, hashed with their
                          method as fab_hash hashes a run – with one board the run's fab_sha256
      release             fab/manifest.json of the current release
      firmware            the contract, [firmware] out"""
    from .release import gate
    names = _Names(cfg)
    key, why = names.parse(name)
    if key is None or key[0] == "file" or why:
        raise ValueError(f"{name}: " + (why or "a path, not a name of edakit's data"))
    kind, b = key
    if kind == "project-library":
        return None
    if kind == "gerber":
        return _gerber_hash(cfg, b)
    route = cfg.artifacts / "route"
    if kind == "parts":
        files = sorted(cfg.parts.glob("*.json"))
    elif kind == "routing":       # the stitching vias count only with the routing they belong to
        files = [route / f"{b}.ses", route / f"{b}_stitch.json"] if (route / f"{b}.ses").is_file() else []
    elif kind == "release":
        cur = gate.current(cfg)
        files = [cfg.reports / cur[0] / "fab" / "manifest.json"] if cur else []
    else:                         # graph, sim, board, footprints, mech, firmware: the one file that is the data
        files = [cfg.resolve(p) for p, k in names.own.items() if k == key]
    files = [f for f in files if f.is_file()]
    ignore = cfg.release.get("hash_ignore", []) if kind in ("graph", "parts") else ()
    return gate.file_hash(cfg.root, files, ignore, files) if files else ABSENT


def _gerber_hash(cfg, b):
    """gerber:<b>: the board's fab_layers of the last gate run with manufacturing files – from its manifest, for a run
    from before the fab hash (#65) from its files, as edakit fab diff reads them. ABSENT without such a run, or when it
    has no files of the board."""
    from .release import fab, gate
    runs = gate.runs(cfg)
    if not runs:
        return ABSENT
    _, manifest, data = runs[-1]
    layers, method = (data.get("fab_layers") or {}).get(b), data.get("fab_method")
    if layers is None and (manifest.parent / b).is_dir():
        layers, method = fab.fab_layers(manifest.parent / b, b), fab.FAB_METHOD
    if not layers:
        return ABSENT
    return hashlib.sha256(json.dumps({"method": method, "boards": {b: layers}}, sort_keys=True).encode()).hexdigest()
