"""Project scripts: the entries [scripts.<name>] of edakit.toml and edakit's own steps, resolved into one order, and the
stamps that tell an outdated script. Project agents: the entries [agents.<name>] – what each signs, where it reviews
(agents, at the end).

    edakit scripts               every script with its about and state – current, outdated, never run – and the order;
                                 with [agents] every agent and who reviews at each hook point
    edakit run NAME …            runs scripts in their order and records their stamps – an easyeda script under the
                                 EasyEDA claim; a check is the gate's (main_run)
    edakit scripts stamp NAME …  records the run of scripts that ran by hand: their stamps in hardware/scripts.lock
    edakit check, edakit gate    report what keeps the entries from resolving and every outdated script (handbook 8.6)
    edakit pcb place|parts|plan|apply, route all, silk apply|preview, gate
                                 run the outdated inputs they read first (before_step, decision 7); --no-scripts runs
                                 none. pcb dump and route all take their data off what an easyeda script left from
                                 before it (after_step)

A project registers the scripts that touch edakit's flow: a script writes a file edakit reads, derives something from
edakit's data, changes the project library in EasyEDA, or holds up the release as a check of its own. Its entry says
what it reads and writes; when it runs follows from that and from edakit's steps in their fixed order (STEPS). edakit
runs an input before the step that reads it and every script on command (edakit run); the gate runs the checks, as
gate_checks gives them (handbook 8.1).

  kind     when                                                     what it writes
  input    before the first edakit step that reads what it writes   a file edakit reads: the board file (board:<b>),
                                                                    an SVG of [[silk.art]], the simulation plugin
  derive   before edakit check, where its result is to be current;  files no edakit step reads
           before the gate when it reads what comes after edakit check
           – no step runs it: edakit run
  easyeda  on command only: edakit run, under the EasyEDA claim     project-library:<b> in EasyEDA
  check    phase export: a stage of the gate, before S or at        nothing
           "after F"; phase order and acceptance: a line of the
           protocol's list of its phase (gate_checks)
  sim      inside edakit sim: [project] sim_plugin                  nothing
[[release.stages]] are checks of phase export before S.

Names of edakit's data in reads and writes: graph, parts, sim (written by hand, edakit block, edakit part), board:<b>
(the board file), project-library:<b> (EasyEDA's project library: schematic create, easyeda scripts, part build –
recorded like an easyeda script's change, record_library_change), footprints:<b>
(<b>.geometry.json: pcb dump), mech:<b> (pcb plan), routing:<b> (route), gerber:<b> and release (the gate),
firmware (edakit firmware, with [firmware]); <b> is a made board – a bought one has none of them. Anything else is a
path relative to edakit.toml: a folder holds the files in it, and an edakit file named by its path is its data
(hardware/boards/<b>.toml is board:<b>, route/<b>.ses routing:<b>, a gate run's fab/<b>/ gerber:<b>). Each name has a
hash of what edakit has of it offline (data_hash) – the project library, which is in EasyEDA only, the last change
edakit run saw an easyeda script make, none before.

The stamp of a script (input, derive, easyeda) in hardware/scripts.lock: its cmd, the script itself – the first word of
cmd that names a file (script_file) – and the hash of everything it reads, at its last run (input_hash: a name's
data_hash, a file's bytes, a folder's files). A script is
  current    every hash as stamped
  outdated   cmd changed, a hash changed, reads names what the stamp lacks, or it comes after a script – through after,
             or reading what that one writes – that is outdated or never ran
  never run  no stamp
What is absent here – build/ in the CI or a fresh clone, a file outside the project – and the project library before
any change edakit run saw are not compared, whatever the stamp says: a note names them. Outdated or never run, an input
is an error (the gate: a failed check of stage G), a derive or easyeda script a warning; a check has no stamp, its
result is the gate's protocol. After an easyeda script ran through edakit run, the lock also keeps what it changed –
project-library:<b> – and what is from before it: the parts in the PCB with their geometry, and the routing, until
edakit pcb dump and edakit route all made them again; a warning until then (open_changes).

The entries resolve when (docs/concepts/new/project-scripts.md, "Checking the TOML", its rules 1 to 9; 10 and 11 are
about agents, see agents):
  1  kind is input, derive, easyeda or check, the fields of the kind are there, and no field of another kind
  2  every data name is edakit's, with a made board of [boards]; firmware only with [firmware]
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

import datetime as dt
import getpass
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import textwrap
import time
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
           "project-library": "edakit schematic create, changed by easyeda scripts and edakit part build",
           "footprints": "edakit pcb dump",
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
    before: dict    # name of a [scripts] entry -> the entries it comes after: through after, or reading what they write
    sequence: list  # order with the easyeda scripts, each before the first step that reads what it changes – the
                    # order edakit run runs scripts in


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
        from .pcb import geometry_home, unmoved_geometry
        self.cfg = cfg
        own = {cfg.graph: ("graph", None), cfg.sim_config: ("sim", None)}
        for b, board in cfg.made().items():        # a bought board has no layout: none of a board's data
            own[cfg.resolve(board.file)] = ("board", b)
            own[geometry_home(cfg, board)] = ("footprints", b)        # beside the board file, where pcb dump writes
            if old := unmoved_geometry(cfg, board):                   # the one from before, read until it is moved
                own[old] = ("footprints", b)
            own[cfg.artifacts / f"mech_{b}.json"] = ("mech", b)
            for f in (f"{b}.ses", f"{b}_stitch.json"):     # the tracks and vias of edakit route, its stitching vias
                own[cfg.artifacts / "route" / f] = ("routing", b)
        if cfg.firmware is not None:
            own[cfg.resolve(cfg.firmware["out"])] = ("firmware", None)
        self.own = {self.path(p): key for p, key in own.items()}
        self.parts = self.path(cfg.parts)
        self.reports = self.path(cfg.reports)

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
            if self.cfg.boards[board].bought:
                return (kind, board), (f"{board} is a bought board (bought = true): edakit makes none of its data – "
                                       f"<name>:<b> names a made board ({', '.join(self.cfg.made()) or 'none'})")
            return (kind, board), None
        if m and m[2] is not None:
            return None, ("no data name of edakit (graph, parts, sim, release, firmware; board, project-library, "
                          "footprints, mech, routing, gerber with :<b>)")
        p = self.path(spelling)
        if p in self.own:
            return self.own[p], None
        if p == self.parts or p.startswith(self.parts + "/"):
            return ("parts", None), None
        run = p[len(self.reports) + 1:].split("/") if p.startswith(self.reports + "/") else []
        if len(run) > 2 and run[1] == "fab" and run[2] in self.cfg.made():   # <reports>/<run>/fab/<b>/…: a gate run's
            return ("gerber", run[2]), None                                   # manufacturing files of the board
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


def _keys(cfg, names, spec, boards):
    """The keys of what a step of STEPS reads or writes (spec), for these made boards."""
    made, out = cfg.made(), set()
    for n in spec:
        if n == "plugin":
            out |= {("file", names.path(cfg.sim_plugin))} if cfg.sim_plugin else set()
        elif n == "art:<b>":
            out |= {("file", names.path(a["svg"])) for b in boards
                    for a in (made[b].silk.get("art") if isinstance(made[b].silk.get("art"), list) else [])
                    if isinstance(a, dict) and isinstance(a.get("svg"), str)}
        elif n.endswith(":<b>"):
            out |= {(n[:-4], b) for b in boards}
        else:
            out.add((n, None))
    return out


def _step_data(cfg, names):
    """Per step of STEPS: the keys it reads and the keys it writes, for every made board."""
    boards = list(cfg.made())
    return [_keys(cfg, names, r, boards) for _, r, _ in STEPS], [_keys(cfg, names, w, boards) for _, _, w in STEPS]


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
    return _resolve(cfg)[0]


def _resolve(cfg):
    """(Resolution, the entries as _entries read them, _Names)."""
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
    before = {e.label: [a.label for a in entries if a.node[0] == "script" and e.node in edges.get(a.node, {})]
              for e in entries if e.node[0] == "script"}
    # an easyeda script has no edge to the steps – it runs on command –, but edakit run runs it before the first step
    # that reads what it changes: before schematic layout and pcb parts
    feeds = {e.node: min((i for i, read in enumerate(reads_of) if any(_overlap(k, r) for _, k in e.writes
                                                                      for r in read)), default=len(STEPS))
             for e in entries if e.kind == "easyeda"}
    sequence = _order(steps, entries, edges, labels, feeds) if not found else []
    on_command = {e.label for e in entries if e.kind == "easyeda"}
    return Resolution(found, [n for n in sequence if n not in on_command], before, sequence), entries, names


def _order(steps, entries, edges, labels, feeds):
    """One order that keeps every edge: each script just before the first of edakit's steps it comes before – an
    easyeda script at the latest before the step feeds names."""
    nodes = steps + [e.node for e in entries]
    first = {}

    def first_step(n):
        if n[0] == "step":
            return n[1]
        if n not in first:
            first[n] = min([first_step(m) for m in edges.get(n, {})] + [feeds.get(n, len(STEPS))])
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
    return [labels[n] for n in out]


# --- the hash of each name ------------------------------------------------------------------------------------------

def data_hash(cfg, name):
    """The hash of one of edakit's data, by its name as reads and writes spell it (an edakit file named by its path is
    its data): the SHA-256 of what edakit has of it offline, ABSENT while the data does not exist. A name that is not
    edakit's data: ValueError; a manifest that is not readable: gate.ReleaseError, as in edakit release.

      project-library:<b> the project library is in EasyEDA only: what changes it is an easyeda script, and running
                          the script is what tells edakit – the hash of its last change edakit run recorded in
                          hardware/scripts.lock (which script, when); None before any
      graph, parts, sim   the files as the circuit hash reads them – graph and parts without [release] hash_ignore
      board:<b>           the board file
      footprints:<b>      the geometry edakit pcb dump measures, beside the board file (<b>.geometry.json) – one
                          from before among the artifacts (pcb_geometry_<b>.json) until it is moved
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
        change = load_changes(cfg).get(_spell(key))
        return _change_hash(change) if change else None
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


# --- stamps: what each script's result was made from, at its last run -----------------------------------------------

LOCK = "hardware/scripts.lock"           # versioned, in no hash
STAMPED = ("input", "derive", "easyeda")  # a check's result is the gate's protocol, sim_plugin runs inside edakit sim
LEVEL = {"input": "error", "derive": "warning", "easyeda": "warning"}   # of a script outdated or never run
RESULT = {"error": "fail", "warning": "warn", "note": "info"}          # the gate's row for a level
SKIP = ("__pycache__",)                   # left out of a folder's hash, with every name that starts with a dot (.git,
SKIP_SUFFIXES = (".pyc", ".pyo")          # .venv, editor files) and compiled Python
ABOUT_LOCK = ("The stamps of the project scripts ([scripts.<name>] of edakit.toml): per script, at its last run, "
              "its cmd, the script itself and the hash of everything it reads; after an easyeda script ran, what it "
              "changed in EasyEDA and what is from before it (changed). edakit run and edakit scripts stamp write it, "
              "edakit check and the gate compare it (handbook 8.6). Commit it with what the scripts wrote.")


class StampError(Exception):
    """hardware/scripts.lock cannot be read, or a stamp cannot be recorded."""


class State(NamedTuple):
    name: str           # the [scripts] name; [[release.stages]] <id>, sim_plugin
    kind: str
    about: str
    cmd: list
    script: str | None  # the script itself (script_file); None when cmd names no file
    state: str          # current, outdated, never run – "" when nothing was compared: a kind without a stamp, entries
                        # that do not resolve, a lock that cannot be read
    why: list           # what makes it outdated
    unseen: list        # what was not compared, and why
    stamp: dict | None  # its stamp in the lock
    place: str = ""     # a kind without a stamp: where it runs


def lock_name(cfg, spelling, names=None):
    """How a stamp names what a script reads: a name of edakit's data by its name, also when the entry gives its path
    (hardware/boards/main.toml is board:main); a path relative to edakit.toml – one outside the project as written, so
    that the lock reads the same on every machine."""
    key, _ = (names or _Names(cfg)).parse(spelling)
    if key is not None and key[0] != "file":
        return _spell(key)
    p = Path(os.path.normpath(cfg.resolve(spelling)))
    if p.is_relative_to(cfg.root):
        return p.relative_to(cfg.root).as_posix()
    return Path(os.path.normpath(spelling)).as_posix()


def script_file(cfg, cmd):
    """The script itself: the first word of cmd that names a file – relative to edakit.toml, or inside the project when
    it is absolute, since a program of the system is no script of the project –, as a stamp names it. None when cmd
    names no such file – a program on PATH (make, python -m …): then only reads count, and the script's files belong in
    reads."""
    names = _Names(cfg)
    for word in cmd:
        p = Path(word)
        if word.startswith("-") or p.is_absolute() and not p.is_relative_to(cfg.root):
            continue
        if cfg.resolve(word).is_file() and names.parse(word)[0] is not None:   # not a word:word such as host:port
            return lock_name(cfg, word, names)
    return None


def input_hash(cfg, spelling, names=None):
    """The hash of what reads may name, as a stamp holds it: a name of edakit's data (also by its path) its data_hash –
    None for the project library –, a file its bytes, a folder every file below it with its path in the folder, without
    __pycache__, *.pyc, *.pyo, names that start with a dot and the lock itself, which a stamp would change. ABSENT when
    there is nothing. ValueError for a name that is not edakit's."""
    key, why = (names or _Names(cfg)).parse(spelling)
    if key is None or why:
        raise ValueError(f"{spelling}: {why}")
    if key[0] != "file":
        return data_hash(cfg, spelling)
    p = cfg.resolve(key[1])
    if p.is_file():
        return hashlib.sha256(p.read_bytes()).hexdigest()
    files = [f for f in _files(p) if p / f != cfg.root / LOCK] if p.is_dir() else []
    if not files:
        return ABSENT
    h = hashlib.sha256()
    for rel in files:
        h.update(rel.encode() + b"\0" + hashlib.sha256((p / rel).read_bytes()).digest())
    return h.hexdigest()


def _files(folder):
    """The files below folder, as sorted paths relative to it – without caches and hidden names."""
    out = []
    for top, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP]
        rel = Path(top).relative_to(folder)
        out += [(rel / f).as_posix() for f in files if not f.startswith(".") and not f.endswith(SKIP_SUFFIXES)]
    return sorted(out)


def load_lock(cfg):
    """The stamps of hardware/scripts.lock, {name: stamp}; {} while there is no file. StampError when it is not a lock
    as edakit scripts stamp writes it."""
    path = cfg.root / LOCK
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise StampError(f"{LOCK}: not readable ({e})") from None
    stamps = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(stamps, dict) or not all(isinstance(s, dict) and isinstance(s.get("cmd"), list)
                                               and isinstance(s.get("hashes"), dict) for s in stamps.values()):
        raise StampError(f"{LOCK}: not readable (no table scripts of stamps, each with cmd and hashes)")
    return stamps


def save_lock(cfg, stamps, changed=None):
    """Writes the stamps and what easyeda scripts changed – changed None keeps what the lock has; a lock without any
    change has no table changed."""
    path = cfg.root / LOCK
    changed = load_changes(cfg) if changed is None else changed
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"about": ABOUT_LOCK, "scripts": {n: stamps[n] for n in sorted(stamps)}}
    if changed:
        data["changed"] = {n: changed[n] for n in sorted(changed)}
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def load_changes(cfg):
    """What easyeda scripts changed in EasyEDA, as edakit run recorded it in hardware/scripts.lock: {data name, e.g.
    project-library:main: {script, at, by, from_before: [footprints:<b>, routing:<b>, …]}}; {} without – or with a
    lock that cannot be read, which load_lock reports."""
    path = cfg.root / LOCK
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    changed = data.get("changed") if isinstance(data, dict) else None
    return {n: c for n, c in changed.items() if isinstance(c, dict) and isinstance(c.get("script"), str)
            and isinstance(c.get("at"), str) and isinstance(c.get("from_before", []), list)} \
        if isinstance(changed, dict) else {}


def _change_hash(change):
    """The hash of a change of the project library: which script made it, when – what a stamp compares."""
    return hashlib.sha256(json.dumps({"script": change["script"], "at": change["at"]}, sort_keys=True)
                          .encode()).hexdigest()


def _user(cfg):
    from .release import gate
    return gate.sh(cfg.root, "git", "config", "user.name") or getpass.getuser()


def _inputs(cfg, names, e):
    """(the script itself, {name in the stamp: hash} of the script and of everything the entry reads)."""
    script = script_file(cfg, e.raw.get("cmd") or [])
    now = {script: input_hash(cfg, script, names)} if script else {}
    for spelling, _ in e.reads:
        now.setdefault(lock_name(cfg, spelling, names), input_hash(cfg, spelling, names))
    return script, now


def _compare(stamp, cmd, script, now):
    """(why, unseen): what makes the stamp outdated; what was not compared – absent here, or without an offline hash."""
    moved = stamp["cmd"] != cmd
    why, unseen, old = ["cmd changed"] if moved else [], [], stamp["hashes"]
    for k, h in now.items():
        if h is None:
            unseen.append(f"{k} has no offline hash")
        elif h == ABSENT:
            if old.get(k) != ABSENT:
                unseen.append(f"{k} absent here")
        elif k not in old:
            if not (moved and k == script):        # another cmd runs another script: cmd changed says it
                why.append(f"{k} new in reads")
        elif old[k] != h:
            why.append(f"{k} changed")
    if stamp.get("script") and stamp["script"] not in now and not moved:
        unseen.append(f"{stamp['script']} absent here")       # the script of the same cmd is gone
    return why, unseen


def _place(e):
    """Where a kind without a stamp runs."""
    from .requirements import WORKS_THROUGH
    if e.kind == "sim":
        return "the simulation plugin, it runs inside edakit sim"
    if e.phase == "export":
        return f"a check, phase export {e.at or 'before S'}: the gate runs it" + (
            " with --easyeda, on the run's manufacturing files" if e.at == "after F" else "")
    if e.phase in WORKS_THROUGH:
        where = "the acceptance list after delivery" if e.phase == "acceptance" else \
            "the list after uploading, before paying"
        return f"a check, phase {e.phase}: a line of {where} (protocol section 6), {WORKS_THROUGH[e.phase]} works " \
               "through it"
    return "a check without a valid phase (edakit check)"


def review(cfg):
    """(resolution, states, problem): the entries resolved with edakit's steps; the state of every entry – [scripts] in
    the order of edakit.toml, then [[release.stages]] and sim_plugin; what kept the stamps from being compared (a lock
    that cannot be read), else None. Stamps are compared only when the entries resolve."""
    return _review(cfg)[:3]


def _review(cfg):
    """review, and the entries and names it resolved with."""
    from .release import gate
    res, entries, names = _resolve(cfg)
    stamps, problem = {}, None
    try:            # only a project with scripts to stamp reads the lock
        stamps = load_lock(cfg) if any(e.kind in STAMPED for e in entries) else {}
    except StampError as e:
        problem = f"{e} – nothing compared; fix it, or delete it and stamp every script again"
    compare = not res.findings and problem is None
    scripts, memo = {e.label: e for e in entries if e.node[0] == "script"}, {}

    def state(e):
        if e.label not in memo:
            cmd = list(e.raw.get("cmd") or [])
            s = stamps.get(e.label) if e.kind in STAMPED else None
            out = State(e.label, e.kind, str(e.raw.get("about") or e.raw.get("name") or ""), cmd,
                        script_file(cfg, cmd) if e.kind in STAMPED else None, "", [], [], s,
                        _place(e) if e.kind not in STAMPED else "")
            if compare and e.kind in STAMPED and s is None:
                out = out._replace(state="never run")
            elif compare and e.kind in STAMPED:
                script, now = _inputs(cfg, names, e)
                why, unseen = _compare(s, cmd, script, now)
                for b in res.before.get(e.label, []):        # a script it comes after that is not current
                    if scripts[b].kind in STAMPED and (prior := state(scripts[b]).state) != "current":
                        why.append(f"after {b}, which " + ("never ran" if prior == "never run" else "is outdated"))
                out = out._replace(script=script, state="outdated" if why else "current", why=why, unseen=unseen)
            memo[e.label] = out
        return memo[e.label]
    try:
        states = [state(e) for e in entries]
    except gate.ReleaseError as e:          # a script reads the release or Gerber data, and a manifest is not readable
        problem, compare, memo = f"{e} – nothing compared", False, {}
        states = [state(e) for e in entries]
    if cfg.sim_plugin:
        states = [s._replace(about=f"{cfg.relative(cfg.sim_plugin)} – MODELS and checks for edakit sim (5.1)")
                  if s.kind == "sim" else s for s in states]
    return res, states, problem, entries, names


def _findings(res, states, problem):
    out = [("error", f.msg) for f in res.findings]
    if problem:
        out.append(("error", problem))
    for s in states:
        if s.state == "outdated":
            out.append((LEVEL[s.kind], f"{s.name} outdated: {', '.join(s.why)} – {s.about}"))
        elif s.state == "never run":
            out.append((LEVEL[s.kind], f"{s.name} never run: no stamp in {LOCK} – {s.about}"))
        if s.unseen:
            out.append(("note", f"{s.name}: not compared – {', '.join(s.unseen)}"))
    return out


def _change_findings(cfg, problem, res, entries):
    """A warning per change of a project library with something from before it (open_changes), with the scripts made
    from that – none while the lock cannot be read."""
    return [] if problem or not cfg.scripts else [
        ("warning", _change_said(n, c, () if res.findings else _made_from(res, entries, c))) for n, c in open_changes(cfg)]


def findings(cfg):
    """What edakit check and the gate report with the ID scripts, [(level, message)] with level error, warning or note:
    what keeps the entries from one order (nothing is compared then), a lock that cannot be read, every script outdated
    or never run – an input an error, a derive or easyeda script a warning –, what was not compared, and what is from
    before a change an easyeda script made – a warning."""
    res, states, problem, entries, _ = _review(cfg)
    return _findings(res, states, problem) + _change_findings(cfg, problem, res, entries)


def gate_rows(cfg):
    """The rows of stage G with the ID scripts: an error fails, a warning wants accepting – or the script run, the step
    made again –, a note informs, and a current script passes. A project without [scripts], [[release.stages]] and
    sim_plugin gets none."""
    res, states, problem, entries, _ = _review(cfg)
    rows = [{"stage": "G", "id": "scripts", "item": "", "check": msg, "result": RESULT[level]}
            for level, msg in _findings(res, states, problem) + _change_findings(cfg, problem, res, entries)]
    return rows + [{"stage": "G", "id": "scripts", "item": "", "check": f"{s.name} current – {s.about}",
                    "result": "pass"} for s in states if s.state == "current"]


# --- the checks in the gate (handbook 8.1) ----------------------------------------------------------------------------

TIMEOUT = 900       # seconds a check may run in the gate – of a [[release.stages]] its timeout, this by default
PYTHON = ("python", "python3")   # the first word of a [scripts] cmd that stands for edakit's own interpreter


def command(cmd):
    """What edakit runs for the cmd of a [scripts] entry: cmd stays free, and python or python3 as its first word is
    edakit's own interpreter (sys.executable), whatever python the PATH holds – so that the script can import edakit
    (concept project-scripts, decision 6)."""
    cmd = list(cmd)
    return [sys.executable, *cmd[1:]] if cmd and cmd[0] in PYTHON and sys.executable else cmd


class Check(NamedTuple):
    """A check of the project as the gate takes it: a [scripts.<name>] of kind check, or a [[release.stages]]."""
    name: str           # what verify = script names: the [scripts] name, the id of a [[release.stages]]
    id: str             # its stage in the protocol
    title: str          # its name in the protocol: the [scripts] name, the name of a [[release.stages]]
    about: str          # what it checks – of a [[release.stages]] without about its cmd
    cmd: list           # as written – the protocol shows it so
    phase: str          # export, order, acceptance
    at: str             # phase export: "before S" or "after F"; "" in the phases after the export
    advisory: bool      # a failure is listed and does not block
    timeout: float
    release_stage: bool = False   # a [[release.stages]]: its cmd runs exactly as written

    def argv(self):
        """What the gate runs: of a [scripts] entry its cmd with python as edakit's own (command); of a
        [[release.stages]] the cmd exactly as written – their python is the PATH's, as projects rely on it."""
        return list(self.cmd) if self.release_stage else command(self.cmd)


def gate_checks(cfg):
    """The project's checks, in the order edakit scripts shows: [[release.stages]], each a check of phase export before
    S, and the entries of [scripts] of kind check – these only when the entries resolve into one order: edakit refuses
    them otherwise, and stage G says why. A [[release.stages]] without an id is a finding of stage G, no check.

      phase export, before S   a stage of the gate between E and S, where [[release.stages]] always ran
      phase export, after F    a stage after stage F, with --easyeda: it reads the run's manufacturing files
      order, acceptance        no stage: a line of the protocol's list of its phase (section 6), which the manual
                               check of the phase works through – M-2 at the manufacturer, M-4 after delivery"""
    res, entries, _ = _resolve(cfg)
    rank = {label: i for i, label in enumerate(res.order)}
    out = []
    for e in entries:
        s = e.raw
        if e.kind != "check" or e.node[0] == "script" and res.findings:
            continue
        if e.node[0] == "stage":
            if not s.get("id"):
                continue
            cmd = s.get("cmd", [])
            check = Check(str(s["id"]), str(s["id"]), str(s.get("name", "")), s.get("about", " ".join(cmd)), cmd,
                          "export", "before S", bool(s.get("advisory")), s.get("timeout", TIMEOUT), release_stage=True)
        else:
            check = Check(e.label, s["id"], e.label, s["about"], list(s["cmd"]), s["phase"],
                          (s.get("at") or "before S") if s["phase"] == "export" else "", bool(s.get("advisory")),
                          TIMEOUT)
        out.append((rank.get(e.label, len(rank)), check))
    return [c for _, c in sorted(out, key=lambda rc: rc[0])]


def stamp(cfg, names, ran=False):
    """Records the run of each script of names – it ran by hand, or edakit run ran it (ran): its stamp in
    hardware/scripts.lock; the stamps of scripts no longer in [scripts] are dropped. Returns (the new stamps, the names
    dropped). StampError with what keeps a script from its stamp: then nothing is written. A stamp records no change of
    the project library – only edakit run sees an easyeda script change it (main_run)."""
    if not names:
        raise StampError("name the scripts that ran: edakit scripts stamp NAME …")
    if unknown := [n for n in names if n not in cfg.scripts]:
        raise StampError(f"no [scripts.{unknown[0]}] in {cfg.path.name} ({', '.join(cfg.scripts) or 'none'})")
    res, entries, nm = _resolve(cfg)
    if res.findings:
        raise StampError("the entries do not resolve into one order – edakit check names what keeps them; nothing "
                         "stamped")
    stamps = load_lock(cfg)
    entry = {e.label: e for e in entries if e.node[0] == "script"}
    when = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    by = _user(cfg)
    new = {}
    for name in dict.fromkeys(names):
        e = entry[name]
        if e.kind not in STAMPED:
            raise StampError(f"{name} is a check: its result is the gate's protocol, not a file – a check has no stamp")
        if gone := [s for s, _ in e.writes if input_hash(cfg, s, nm) == ABSENT]:
            are = "is" if len(gone) == 1 else "are"
            raise StampError(f"{name} ran, but {', '.join(gone)} {are} not there – its cmd does not write what writes "
                             "names; nothing recorded" if ran else
                             f"{name} writes {', '.join(gone)}, which {are} not there – run it first; nothing stamped")
        script, now = _inputs(cfg, nm, e)
        new[name] = {"stamped": when, "by": by, "cmd": list(e.raw["cmd"]), "script": script,
                     "hashes": dict(sorted(now.items()))}
    dropped = [n for n in stamps if n not in cfg.scripts]
    save_lock(cfg, {**{n: s for n, s in stamps.items() if n in cfg.scripts}, **new})
    return new, dropped


def _said(s):
    """The state as edakit scripts shows it."""
    if s.place:
        return f"no stamp – {s.place}"
    if not s.state:
        return "–"
    return (f"outdated: {', '.join(s.why)}" if s.state == "outdated" else s.state) + \
        (f" – not compared: {', '.join(s.unseen)}" if s.unseen else "")


def listing(cfg, res, states, problem, changes=()):
    """edakit scripts: every entry with kind, state, about, cmd and its last run; the order, or what keeps the entries
    from it; what is from before a change of the project library; what is to run."""
    lines = [f"The project's scripts – [scripts.<name>] of {cfg.path.name}, their stamps in {LOCK} (handbook 8.6)", ""]
    if not cfg.scripts:
        lines += [f"none – {cfg.path.name} has no [scripts.<name>]", ""]
    width = max([len(s.name) for s in states] or [0])
    pad = " " * (width + 11)
    for s in states:
        lines.append(f"{s.name:<{width}}  {s.kind:<7}  {_said(s)}")
        lines += [pad + s.about] if s.about else []
        if s.cmd:
            lines.append(pad + " ".join(s.cmd) + (" – it names no file of the project: only reads count"
                                                  if s.kind in STAMPED and not s.script else ""))
        if s.stamp:
            lines.append(pad + f"stamped {str(s.stamp.get('stamped', '?'))[:16].replace('T', ' ')} by "
                               f"{s.stamp.get('by', '?')}")
    lines.append("")
    if res.findings:
        lines += ["The entries do not resolve into one order (edakit check, handbook 8.6):",
                  *[f"  {f.msg}" for f in res.findings]]
    else:
        lines += textwrap.wrap("order: " + " → ".join(res.order), 120, subsequent_indent=" " * 7,
                               break_long_words=False, break_on_hyphens=False)
        if on_command := [s.name for s in states if s.kind == "easyeda"]:
            lines.append(f"on command only: {', '.join(on_command)}")
    if problem:
        lines += ["", problem]
    if changes:
        lines += ["", *changes]
    if todo := [s for s in states if s.state in ("outdated", "never run")]:
        lines += [""] + textwrap.wrap(
            f"{len(todo)} to run: edakit run {' '.join(s.name for s in todo)}"
            + (" – an easyeda script under the EasyEDA claim" if any(s.kind == "easyeda" for s in todo) else "")
            + "; an input also runs by itself before the step that reads it (handbook 8.6)", 120,
            subsequent_indent="  ", break_long_words=False, break_on_hyphens=False)
    elif any(s.state == "current" for s in states):
        lines += ["", "every script current"]
    return lines


def main(cfg, args):
    """edakit scripts [stamp NAME …]. Exit 0: every script current, or stamped; 2: one is outdated or never ran,
    something is from before a change of the project library, or the entries – of [scripts] or of [agents] – do not
    resolve; 1: the lock cannot be read, or a stamp was refused. With [agents] the listing ends with the project's
    agents and who reviews at each hook point."""
    if args.action == "stamp":
        try:
            new, dropped = stamp(cfg, args.names)
        except StampError as e:
            print(f"edakit scripts stamp: {e}", file=sys.stderr)
            return 1
        for name, s in new.items():
            print(f"{name}: stamped in {LOCK} – {' '.join(s['cmd'])}")
            for k, h in s["hashes"].items():
                print(f"  {k}  " + ("no offline hash" if h is None else h if h == ABSENT else h[:16] + "…"))
        if dropped:
            print(f"dropped the stamps of {', '.join(dropped)} – no such [scripts.<name>] any more")
        _, states, _ = review(cfg)
        for s in states:
            if s.name in new and s.state != "current":
                print(f"{s.name} still {s.state}: {', '.join(s.why)}")
        print(f"Commit {LOCK} with what the scripts wrote.")
        return 0
    res, states, problem, entries, _ = _review(cfg)
    changes = [msg for _, msg in _change_findings(cfg, problem, res, entries)]
    print("\n".join(listing(cfg, res, states, problem, changes)))
    team = agents(cfg) if cfg.agents else None        # [agents]: who reviews where (handbook 8.6)
    if team:
        print("\n".join(agent_listing(cfg, team)))
    if problem:
        return 1
    return 2 if res.findings or any(s.state in ("outdated", "never run") for s in states) or team and team.findings \
        or changes else 0


# --- running the scripts: edakit run, and the inputs before the steps that read them (handbook 8.6) -------------------
#
# edakit runs input scripts itself, easyeda scripts on command only (decision 7). edakit run NAME … runs input, derive
# and easyeda scripts in their order and records each run as edakit scripts stamp does; a check is the gate's. A step
# that reads what an input writes runs the outdated inputs first (before_step); a derive or easyeda script it does not
# run, it names. Each script's output goes to <artifacts>/scripts/<name>.log, a line with its about to the terminal.

HOOKED = {   # the commands that run the outdated inputs they read first – with the step of STEPS whose reads count
    ("pcb", "place"): "edakit pcb place", ("pcb", "parts"): "edakit pcb parts", ("pcb", "plan"): "edakit pcb plan",
    ("pcb", "apply"): "edakit pcb apply", ("route", "all"): "edakit route all", ("silk", "apply"): "edakit silk apply",
    ("silk", "preview"): "edakit silk apply",       # it shows what silk apply places
    ("gate", None): "edakit gate",
}
REMADE = {("pcb", "dump"): "footprints", ("route", "all"): "routing"}   # what these steps make again for their board
FROM_BEFORE = {   # what is from before a change of the project library until the step of REMADE made it again
    "footprints": "the parts in the PCB, which keep their old copy until deleted and recreated (edakit pcb parts "
                  "--write, then edakit pcb dump)",
    "routing": "the routing (edakit route all)",
}
RUNNING = "EDAKIT_SCRIPT"   # set for a script edakit runs, to its name: a step inside it runs no script
TAIL = 40                   # lines of a failed script's output shown – all of it is in the log
FOOTER = "output in {}/<name>.log – commit " + LOCK + " with what the scripts wrote"


class Ran(NamedTuple):
    code: int | None    # its exit code; None when it did not start or was stopped
    seconds: float
    why: str            # what kept it from starting or ending: "" when it ended by itself
    output: str         # stdout and stderr, as in the log
    log: Path


def _execute(cfg, name, cmd, renew=None):
    """Runs the cmd of the script name in the project folder – python as its first word is edakit's own (command) –,
    with EDAKIT_SCRIPT = the name and EDAKIT_CONFIG = this edakit.toml, no input. Its output goes to
    <artifacts>/scripts/<name>.log after a head with time and cmd. It may run TIMEOUT seconds; renew is called about
    every minute while it runs (the EasyEDA claim of an easyeda script)."""
    log = cfg.artifact("scripts", f"{name}.log")
    argv = command(cmd)
    log.write_text(f"{name} – {dt.datetime.now().astimezone().isoformat(timespec='seconds')}\ncmd: {shlex.join(cmd)}\n"
                   + (f"runs: {shlex.join(argv)}\n" if argv != list(cmd) else "") + "\n", encoding="utf-8")
    start = log.stat().st_size
    env = {**os.environ, RUNNING: name, "EDAKIT_CONFIG": str(cfg.path)}
    t0, code, why = time.monotonic(), None, ""
    with open(log, "a", encoding="utf-8") as out:
        try:
            proc = subprocess.Popen(argv, cwd=cfg.root, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                    env=env)
        except OSError as e:
            why = f"cannot run: {e}"
        else:
            while code is None and not why:
                try:
                    code = proc.wait(timeout=max(0.1, min(60.0, t0 + TIMEOUT - time.monotonic())))
                except subprocess.TimeoutExpired:
                    if time.monotonic() - t0 >= TIMEOUT:
                        proc.kill()
                        proc.wait()
                        why = f"stopped after {TIMEOUT} s"
                    elif renew:
                        renew()
        seconds = time.monotonic() - t0
    output = log.read_bytes()[start:].decode("utf-8", errors="replace")
    with open(log, "a", encoding="utf-8") as out:
        out.write(f"\n{why or f'exit {code}'} after {seconds:.1f} s\n")
    return Ran(code, seconds, why, output, log)


def _run_one(cfg, name, indent=""):
    """Runs one script and records its run – the stamp, and for an easyeda script what it changed (_record_change):
    (the config read again – the script may have written a board file –, whether it ran and is recorded). Prints its
    line, or what failed and the end of its output (stderr)."""
    from . import config
    e = cfg.scripts[name]
    ran = _execute(cfg, name, list(e["cmd"]), _renew(cfg) if e["kind"] == "easyeda" else None)
    if ran.code != 0:
        lines = ran.output.splitlines()
        shown = [f"… {len(lines) - TAIL} lines before"] * (len(lines) > TAIL) + lines[-TAIL:] or ["(no output)"]
        print("\n".join([f"{indent}{name} failed ({ran.why or f'exit {ran.code}'}, {ran.seconds:.1f} s) – nothing "
                         f"recorded; its output, also in {cfg.relative(ran.log)}:",
                         *(f"{indent}  {line}" for line in shown)]), file=sys.stderr)
        return cfg, False
    cfg = config.load(cfg.path)
    try:
        changes = _record_change(cfg, name) if e["kind"] == "easyeda" else []
        stamp(cfg, [name], ran=True)
    except StampError as err:
        print(f"{indent}{err}", file=sys.stderr)
        return cfg, False
    print(f"{indent}{name} ran ({ran.seconds:.1f} s) – {e.get('about', '')}")
    if changes:
        res, entries, _ = _resolve(cfg)
        for n, c in changes:
            print(f"{indent}  {_change_said(n, c, () if res.findings else _made_from(res, entries, c))}")
    return cfg, True


def _claim(cfg, names):
    """Claims EasyEDA for easyeda scripts, as every edakit command that touches EasyEDA does: in a Claude session, with
    [project] lock = "auto" (lock.claim_for_script). None, or why not – another session holds it."""
    from . import lock
    try:
        lock.claim_for_script(note=f"edakit run {' '.join(names)}"[:80], mode=cfg.lock)
    except SystemExit as e:
        return str(e.code)
    return None


def _renew(cfg):
    from . import lock

    def renew():        # every minute while an easyeda script runs: the claim expires after 15 minutes without access
        try:
            lock.claim_for_script(renew=True, mode=cfg.lock)
        except SystemExit:
            pass        # taken over meanwhile – the script runs on; edakit lock says who holds EasyEDA
    return renew


def main_run(cfg, args):
    """edakit run NAME …: the named scripts in the order edakit scripts shows – an easyeda script before the steps that
    read the project library –, each recorded after it ran (stamp; an easyeda script also what it changed), a failed one
    shown and nothing recorded; the scripts after it do not run. An easyeda script runs under the EasyEDA claim. Only
    the named scripts run. Exit 0: each ran and is current; 2: one is still not current – it comes after a script that
    is not; 1: refused – a name not in [scripts], a check, entries that do not resolve, a lock that cannot be read –, or
    a script failed; 3: another session holds EasyEDA."""
    def refuse(why):
        print(f"edakit run: {why}", file=sys.stderr)
        return 1
    names = list(dict.fromkeys(args.names))
    if unknown := [n for n in names if n not in cfg.scripts]:
        return refuse(f"no [scripts.{unknown[0]}] in {cfg.path.name} ({', '.join(cfg.scripts) or 'none'})")
    if (running := os.environ.get(RUNNING)) in names:
        return refuse(f"{running} is running – it does not run itself")
    res, entries, _ = _resolve(cfg)
    if res.findings:
        return refuse("the entries do not resolve into one order – edakit check names what keeps them; nothing ran")
    entry = {e.label: e for e in entries if e.node[0] == "script"}
    if checks := [n for n in names if entry[n].kind == "check"]:
        return refuse(f"{checks[0]} is {_place(entry[checks[0]])} – edakit run runs input, derive and easyeda scripts")
    try:
        load_lock(cfg)
    except StampError as e:
        return refuse(f"{e} – nothing ran; fix it, or delete it and stamp every script again")
    todo = [n for n in res.sequence if n in names]
    if easyeda := [n for n in todo if entry[n].kind == "easyeda"]:
        if why := _claim(cfg, easyeda):
            print(f"edakit run: {why} – nothing ran", file=sys.stderr)
            return 3
    for n in todo:
        cfg, ok = _run_one(cfg, n)
        if not ok:
            return 1
    print(FOOTER.format(cfg.relative(cfg.artifacts / "scripts")))
    res, states, _ = review(cfg)
    stale = {s.name for s in states if s.state in ("outdated", "never run")}
    still = [s for s in states if s.name in names and s.name in stale]
    for s in still:
        first = [n for n in res.sequence if n in stale and n in _upstream(res, [s.name])]
        print(f"{s.name} still {_said(s)} – edakit run {' '.join(first + [s.name])}")
    return 2 if still else 0


def _upstream(res, names):
    """The scripts names come after, through after or reading what they write – and those before them."""
    seen, todo = set(), list(names)
    while todo:
        for b in res.before.get(todo.pop(), []):
            if b not in seen:
                seen.add(b)
                todo.append(b)
    return seen


class Due(NamedTuple):
    problem: str | None     # why no input can run first: the entries do not resolve, the lock cannot be read
    run: list               # [State]: the inputs the step reads – directly or through another input –, outdated or
                            # never run, in their order
    report: list            # [str]: the derive and easyeda scripts before the step that are not current, which no step
                            # runs


def _due(cfg, step, boards):
    """What runs before the step of STEPS for these boards, and what it names."""
    res, states, problem, entries, names = _review(cfg)
    if res.findings:
        return Due("the entries do not resolve into one order – edakit check names what keeps them", [], [])
    if problem:
        return Due(problem, [], [])
    state = {s.name: s for s in states}
    by = {e.label: e for e in entries if e.node[0] == "script"}
    reads = _keys(cfg, names, next(r for name, r, _ in STEPS if name == step), boards)
    direct = [n for n, e in by.items() if e.kind == "input" and any(_overlap(k, r) for _, k in e.writes for r in reads)]
    need = set(direct) | _upstream(res, direct)
    stale = {n for n, s in state.items() if s.state in ("outdated", "never run")}
    run = [state[n] for n in res.sequence if n in need and n in stale and by[n].kind == "input"]
    libraries = {("project-library", b) for b in boards}
    report = []
    for n in res.sequence[:res.sequence.index(step)]:
        e = by.get(n)
        if e is None or n not in stale:
            continue
        if e.kind == "derive":
            report.append(f"{n} {_said(state[n])} – a derive, no step runs it: edakit run {n}")
        elif e.kind == "easyeda" and any(k in libraries for _, k in e.writes):
            report.append(f"{n} {_said(state[n])} – an easyeda script, on command only: edakit run {n} (under the "
                          "EasyEDA claim)")
    return Due(None, run, report)


def before_step(cfg, args):
    """Decision 7: before a command of HOOKED – for its board; the gate for every made board – the inputs that write
    what its step reads, directly or through another input, run when they are outdated or never ran, in their order,
    each recorded as edakit run records it; a derive or easyeda script before the step that is not current is named, not
    run. Returns (an exit code – an input failed: the step does not run –, or None to go on; the config, read again
    after a script ran). Nothing happens without [scripts], for another command, or inside a script edakit runs
    (EDAKIT_SCRIPT): it would run itself. --no-scripts names what it does not run; entries that do not resolve and a
    lock that cannot be read run nothing, the step goes on – edakit check and the gate fail on them."""
    from .config import ConfigError
    action = getattr(args, "action", None)
    step = HOOKED.get((args.command, action))
    if step is None or not cfg.scripts or os.environ.get(RUNNING):
        return None, cfg
    try:
        boards = list(cfg.made()) if args.command == "gate" else [cfg.board(args.board, made=True).name]
    except ConfigError:
        return None, cfg        # the step says why
    me = " ".join(["edakit", args.command] + ([action] if action else []))
    head = f"project scripts before {me} (handbook 8.6):"
    due = _due(cfg, step, boards)
    if due.problem or getattr(args, "no_scripts", False) or not due.run:
        lines = [f"none run: {due.problem}"] if due.problem else [
            f"{s.name} {_said(s)} – not run (--no-scripts): the step reads what is there" for s in due.run
        ] if getattr(args, "no_scripts", False) else []
        if lines := lines + due.report:
            print("\n".join([head, *(f"  {line}" for line in lines)]))
        return None, cfg
    print(head)
    for s in due.run:
        cfg, ok = _run_one(cfg, s.name, "  ")
        if not ok:
            print(f"{me}: not run – {s.name} failed; fix it, or --no-scripts runs the step with the files as they are",
                  file=sys.stderr)
            return 1, cfg
    after = _due(cfg, step, boards)
    lines = [f"{s.name} still {_said(s)}" for s in after.run] + after.report
    print("\n".join(f"  {line}" for line in [*lines, FOOTER.format(cfg.relative(cfg.artifacts / "scripts"))]))
    return None, cfg


# --- what an easyeda script changed: project-library:<b>, and what is from before it ------------------------------
def _change(cfg, by, board, when=None):
    """A change of a board's project library made by `by` (an easyeda script, or edakit part build), now."""
    return {"script": by, "at": when or dt.datetime.now().astimezone().isoformat(timespec="seconds"), "by": _user(cfg),
            "from_before": [f"{d}:{board}" for d in FROM_BEFORE]}


def _record_change(cfg, name):
    """The easyeda script name ran through edakit run: each project library it writes changed now. Its hash is this
    change (data_hash), and from before it are the parts in the PCB with their geometry, and the routing of its board,
    until edakit pcb dump and edakit route all made them again (after_step). Returns [(data name, change)]."""
    changed, out = load_changes(cfg), []
    nm, when = _Names(cfg), dt.datetime.now().astimezone().isoformat(timespec="seconds")
    for spelling in cfg.scripts[name].get("writes", []):
        key, why = nm.parse(spelling)
        if key is not None and not why and key[0] in IN_EASYEDA:
            change = _change(cfg, name, key[1], when)
            changed[_spell(key)] = change
            out.append((_spell(key), change))
    save_lock(cfg, load_lock(cfg), changed)
    return out


def record_library_change(cfg, board, by):
    """edakit part build rebuilt a copy in the project library of a made board (handbook 4.5): recorded as edakit run
    records an easyeda script – project-library:<b> changed by `by`, its hash this change, and the parts in the PCB
    with their geometry and the routing from before it until edakit pcb dump and edakit route all made them again.
    Only with [scripts]: nothing else reads the lock (8.6). -> the message to print, or None. StampError when the lock
    cannot be read."""
    if not cfg.scripts:
        return None
    changed, name = load_changes(cfg), f"project-library:{board}"
    changed[name] = _change(cfg, by, board)
    save_lock(cfg, load_lock(cfg), changed)
    res, entries, _ = _resolve(cfg)
    return _change_said(name, changed[name], () if res.findings else _made_from(res, entries, changed[name]))


def open_changes(cfg):
    """[(data name, change)]: the changes of a made board's project library with something still from before them."""
    made = cfg.made()
    return [(n, c) for n, c in load_changes(cfg).items() if n.partition(":")[2] in made and c.get("from_before")]


def _before_it(change):
    return "; ".join(FROM_BEFORE[d.partition(":")[0]] for d in change.get("from_before", [])
                     if d.partition(":")[0] in FROM_BEFORE)


AFTER = {"footprints": ("footprints", "mech", "routing", "gerber"), "routing": ("routing", "gerber")}   # made from it


def _made_from(res, entries, change):
    """The input and derive scripts made from what is still from before a change – they read the board's footprints,
    mechanical model, routing or Gerber data made from it, or come after such a script –, in their order: the tree
    artwork of the reference project. Their stamps tell them outdated once the steps made the data again."""
    b = next(iter(change.get("from_before", [])), "").partition(":")[2]
    keys = {(k, b) for d in change.get("from_before", []) for k in AFTER.get(d.partition(":")[0], ())}
    kind = {e.label: e.kind for e in entries if e.node[0] == "script"}
    made = {e.label for e in entries if kind.get(e.label) in ("input", "derive") and any(k in keys for _, k in e.reads)}
    todo = list(made)
    while todo:
        n = todo.pop()
        for m, before in res.before.items():
            if n in before and m not in made and kind.get(m) in ("input", "derive"):
                made.add(m)
                todo.append(m)
    return [n for n in res.sequence if n in made]


def _change_said(name, change, made=()):
    """project-library:main changed by lib (2026-10-28 21:40) – from before it: the parts in the PCB …; the routing …;
    and what is made from them: baumgrafik"""
    return (f"{name} changed by {change['script']} ({change['at'][:16].replace('T', ' ')}) – from before it: "
            f"{_before_it(change)}" + (f"; and what is made from them: {', '.join(made)}" if made else ""))


def after_step(cfg, args, code):
    """A step of REMADE made its data of the board again – edakit pcb dump of every part (no --ref), edakit route all
    that wrote its routing into EasyEDA (exit 0; 2: DRC findings; 3: the import acknowledgement pending): it is no
    longer from before the last change of the board's project library – the lock says so. Returns code."""
    from .config import ConfigError
    made = REMADE.get((args.command, getattr(args, "action", None)))
    if made is None or not cfg.scripts or code not in ((0,) if made == "footprints" else (0, 2, 3)) or \
            getattr(args, "ref", None):
        return code
    try:
        b = cfg.board(args.board, made=True).name
    except ConfigError:
        return code
    changed, name, data = load_changes(cfg), f"project-library:{b}", f"{made}:{b}"
    if data not in (change := changed.get(name) or {}).get("from_before", []):
        return code
    change["from_before"] = [d for d in change["from_before"] if d != data]
    try:
        save_lock(cfg, load_lock(cfg), changed)
    except StampError:
        return code     # edakit check names the lock that cannot be read
    left = _before_it(change)
    print(f"{LOCK}: {data} made again after {name} changed ({change['script']}) – "
          + (f"from before it: {left}" if left else "nothing from before it any more") + "; commit the lock")
    return code


# --- project agents: [agents.<name>] of edakit.toml (handbook 8.6) ----------------------------------------------------
#
# An agent delivers a sign-off, and a sign-off is bound to a hash: an agent of the project signs a sign-off of its own
# (M-7), or takes over one of edakit's reviews – explicitly, with replaces (decision 10). Where it reviews follows from
# that, at the four hook points of the flow. Skills are not registered (decision 11).

REVIEWS = {"M-1": "electrical-reviewer", "M-6": "regulatory-reviewer", "M-5": "pcb-reviewer"}   # edakit's reviews
REVIEW_WORDS = {"M-1": "electrical review", "M-6": "regulatory review", "M-5": "layout review"}
OWNER = {"M-2": "the owner's check at the manufacturer, after uploading",     # signed by a human, never by an agent
         "M-4": "the owner's acceptance test after delivery"}
SIGNOFF = re.compile(r"M-[1-9]\d*")             # a manual check of the sign-off file
AGENT_NEEDS = ("file", "about", "signs", "phase")
AGENT_PHASES = ("export", "acceptance")         # order: the owner checks at the manufacturer, no agent gets there
SCOPES = ("circuit", "layout", "fab")           # the hashes of the gate (gate.SCOPE_KEY)
HOOKS = {   # where agents review, in the order of the flow, with the skill that starts them
    "circuit": "circuit review – before the layout (skills circuit-design, hardware-change)",
    "round": "round review – after a layout round that changed placement, routing or pours (skill pcb-round)",
    "release": "layout review – between the first and the second gate run (skill release)",
    "delivery": "after delivery – a line of the acceptance list, which M-4 works through (section 6 of the protocol)",
}
HOOK_AT = {"circuit": "at the circuit review", "round": "at the round review", "release": "at the layout review",
           "delivery": "after delivery"}
REVIEWED = {   # edakit's reviews at their hook points, and what each looks at there
    "M-1": {"circuit": "M-1: the circuit and its hand-over",
            "release": "M-1: the critical parts again, with the polarity sheet"},
    "M-6": {"circuit": "M-6: circuit and parts against the rules for the purpose"},
    "M-5": {"round": "the round's Gerber export – findings, no sign-off",
            "release": "M-5: the gate run's manufacturing files"},
}
OWN_HOOK = {"circuit": "circuit", "layout": "round", "fab": "release"}   # a sign-off of its own, phase export: by scope


class Agent(NamedTuple):
    """A project agent whose sign-off is clear: what the gate binds and the skills start."""
    name: str           # the [agents] name – the skills start it by it, done_by names it
    file: str
    about: str
    signs: str          # the sign-off its OK is
    replaces: str       # the edakit agent it takes the place of; "" for a sign-off of its own
    scope: str          # a sign-off of its own: the hash it is bound to; "" with replaces – the sign-off file's counts
    phase: str          # export: the release waits for it; acceptance: after delivery
    hooks: tuple        # where it reviews (HOOKS), in the order of the flow
    after: tuple        # the project agents it reviews after


class Agents(NamedTuple):
    findings: list      # [Finding]: what keeps the entries from resolving – the concept's rules 7, 9, 10, 11
    signers: dict       # sign-off -> Agent: what the project's agents sign – the gate requires it, held to done_by
    at: dict            # hook point -> [(who, what)]: who reviews there, in the order to start them – edakit's agents
                        # (edakit:<name>) and the project's, one that replaces an edakit agent in its place


def names_agent(text, name):
    """done_by names the agent (handbook 11.4, agreement 4): its name as a word, in any case – "Agent pcb-pruefer (own
    session)" names pcb-pruefer, "agent pcb-pruefer-2" does not."""
    return bool(text) and re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", str(text), re.I) is not None


def _agent_file(cfg, file):
    """(why, the name in its front matter): what is wrong with an agent's file – it does not exist, cannot be read –,
    or None; the name the file gives the agent, None without one."""
    path = cfg.resolve(file)
    if not path.is_file():
        return f"file {file} does not exist", None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return f"file {file} cannot be read ({e})", None
    head = text.split("---", 2)[1] if text.startswith("---") and text.count("---") > 1 else ""
    named = re.search(r"^name:\s*(.+?)\s*$", head, re.M)
    return None, named[1].strip("'\"") if named else None


def agents(cfg) -> Agents:
    """The project's agents ([agents.<name>] of cfg): what keeps their entries from resolving, what they sign, and who
    reviews at each hook point. The rules (docs/concepts/new/project-scripts.md, "Checking the TOML"):
      10  file – it exists and is the agent of this name (name in its front matter) –, about, signs and phase export or
          acceptance; with an ID of its own also scope (circuit, layout, fab); with edakit's review neither scope – the
          sign-off file gives it its scope – nor phase acceptance; not the name of an edakit agent
      11  signs is a sign-off (M-<n>), used once per project; edakit's review (M-1, M-5, M-6) only with replaces = the
          agent that signs it otherwise, and replaces only so; never the owner's (M-2, M-4)
       9  after names other entries of [agents]
       7  after makes no cycle at a hook point, and names no agent that reviews only later
    An entry whose sign-off is not clear – signs, replaces, scope or phase wrong, or a sign-off of two – signs nothing
    here: the gate requires nothing of it, stage G fails on the finding."""
    found = []

    def finding(rule, msg):
        found.append(Finding(rule, msg))
    entries, sound, by_sid = cfg.agents, {}, defaultdict(list)
    for name, a in entries.items():
        sid, repl, scope, phase = a.get("signs"), a.get("replaces"), a.get("scope"), a.get("phase")
        clear = bool(sid and phase)      # its sign-off is clear: what it signs, in which phase, bound to which hash
        if missing := [f for f in AGENT_NEEDS if not a.get(f)]:
            finding(10, f"{name}: {', '.join(missing)} missing – an agent needs file, about, signs and phase")
        if a.get("file"):
            why, front = _agent_file(cfg, a["file"])
            if why:
                finding(10, f"{name}: {why}")
            elif front not in (None, name):
                finding(10, f"{name}: {a['file']} is the agent {front} (name in its front matter) – the skills start an "
                            f"agent by that name, and done_by names it: [agents.{front}]")
        if name in REVIEWS.values():
            finding(10, f"{name}: the name of edakit's agent – a project agent needs a name of its own, so that "
                        "done_by tells the two apart")
        if phase and phase not in AGENT_PHASES:
            finding(10, f'{name}: phase = "{phase}" – export or acceptance' + (
                "; in phase order the owner checks at the manufacturer, no agent gets there" if phase == "order" else ""))
            clear = False
        if not sid:
            pass
        elif not SIGNOFF.fullmatch(sid):
            finding(11, f'{name}: signs = "{sid}" – a sign-off is M-<number>, e.g. M-7')
            clear = False
        elif sid in OWNER:
            finding(11, f"{name}: signs {sid} – {OWNER[sid]}: no agent signs it")
            clear = False
        elif sid in REVIEWS:
            if repl != REVIEWS[sid]:
                finding(11, f"{name}: signs {sid}, edakit's {REVIEW_WORDS[sid]} – only with replaces = "
                            f'"{REVIEWS[sid]}", the agent that signs it otherwise'
                            + (f' (replaces = "{repl}")' if repl else ""))
                clear = False
            if scope is not None:
                finding(10, f"{name}: scope belongs to a sign-off of its own – {sid} keeps the scope the sign-off file "
                            "gives it")
                clear = False
            if phase == "acceptance":
                finding(10, f'{name}: {sid} is a review before the release – phase = "export"')
                clear = False
        else:
            if repl is not None:
                finding(11, f'{name}: replaces = "{repl}", but {sid} is no review of edakit – replaces goes with M-1, '
                            "M-5 or M-6")
                clear = False
            if scope is None:
                finding(10, f"{name}: scope missing – a sign-off of its own is bound to the hash of its scope: circuit, "
                            "layout or fab")
                clear = False
            elif scope not in SCOPES:
                finding(10, f'{name}: scope = "{scope}" – circuit, layout or fab')
                clear = False
        if sid and SIGNOFF.fullmatch(sid) and sid not in OWNER:      # a sign-off an agent may sign: one agent each
            by_sid[sid].append(name)
        if clear:
            hooks = (tuple(REVIEWED[sid]) if sid in REVIEWS else ("delivery",) if phase == "acceptance"
                     else (OWN_HOOK[scope],))
            sound[name] = Agent(name, a.get("file", ""), a.get("about", ""), sid, repl or "",
                                "" if sid in REVIEWS else scope, phase, hooks, tuple(a.get("after", [])))
    for sid, names in by_sid.items():
        if len(names) > 1:
            finding(11, f"{', '.join(names)}: {'both' if len(names) == 2 else 'all'} sign {sid} – a sign-off has one "
                        "agent")
            for n in names:
                sound.pop(n, None)

    # rules 9 and 7: after names other agents; at a hook point both review at it orders them, and an agent that
    # reviews only later cannot come before
    edges = {h: defaultdict(dict) for h in HOOKS}
    rank = {h: i for i, h in enumerate(HOOKS)}
    for name, a in entries.items():
        for b in a.get("after", []):
            if b == name:
                finding(9, f"{name}: after names itself")
            elif b not in entries:
                finding(9, f"{name}: after names {b} – there is no [agents.{b}]")
            elif name in sound and b in sound:
                for h in sound[name].hooks:
                    if h in sound[b].hooks:
                        edges[h][b][name] = "after"
                    elif all(rank[x] > rank[h] for x in sound[b].hooks):
                        finding(7, f"{name}: after {b}, which reviews later – {b} first {HOOK_AT[sound[b].hooks[0]]}, "
                                   f"{name} {HOOK_AT[h]}")
    seen = set()
    for h in HOOKS:
        for n in [x for x in sound if h in sound[x].hooks]:
            if cycle := _cycle(n, edges[h]):
                group = frozenset(m for m in _reach(n, edges[h]) if n in _reach(m, edges[h]))
                if group not in seen:
                    seen.add(group)
                    finding(7, f"{n}: in a cycle {HOOK_AT[h]} – " + " –[after]→ ".join(cycle))

    # who reviews where: edakit's reviews in their order, each by its agent or the one that replaces it, then the
    # project's own sign-offs; after orders them at a hook point
    at = {h: [] for h in HOOKS}
    instead = {a.replaces: a for a in sound.values() if a.replaces}

    def also(a, h):
        before = [b for b in a.after if b in sound and h in sound[b].hooks]
        return f", after {', '.join(before)}" if before else ""
    for sid, agent in REVIEWS.items():
        for h, what in REVIEWED[sid].items():
            a = instead.get(agent)
            at[h].append((a.name, f"{what} – in place of {agent}{also(a, h)}") if a else (f"edakit:{agent}", what))
    for a in sound.values():
        if not a.replaces:
            h = a.hooks[0]
            at[h].append((a.name, f"{a.signs} on the {a.scope} hash{also(a, h)}"))
    return Agents(found, {a.signs: a for a in sound.values()},
                  {h: _in_order(items, edges[h]) for h, items in at.items()})


def _in_order(items, edges):
    """items (who, what), each after the ones edges put before it; otherwise as they come – a cycle (rule 7) keeps
    them so."""
    out, rest = [], list(items)
    while rest:
        waiting = {w for w, _ in rest}
        pick = next((it for it in rest if not any(it[0] in edges.get(b, {}) for b in waiting)), rest[0])
        out.append(pick)
        rest.remove(pick)
    return out


def agent_rows(cfg):
    """The rows of stage G with the ID agents: every finding fails – edakit refuses the entries –; when there is none,
    each agent passes with what it signs. A project without [agents] gets none."""
    if not cfg.agents:
        return []
    review = agents(cfg)
    if review.findings:
        return [{"stage": "G", "id": "agents", "item": "", "check": f.msg, "result": "fail"} for f in review.findings]
    return [{"stage": "G", "id": "agents", "item": "", "check": f"{name}: {_agent_said(a, phase=False)} – "
                                                                f"{a.get('about', '')}", "result": "pass"}
            for name, a in cfg.agents.items()]


def _agent_said(a, phase=True):
    """What an entry signs, as edakit scripts shows it: signs M-5 in place of pcb-reviewer, signs M-7 on the layout
    hash."""
    how = f" in place of {a['replaces']}" if a.get("replaces") else f" on the {a['scope']} hash" if a.get("scope") else ""
    return f"signs {a.get('signs') or '?'}{how}" + (f", phase {a.get('phase') or '?'}" if phase else "") + (
        f"; after {', '.join(a['after'])}" if phase and a.get("after") else "")


def agent_listing(cfg, review):
    """edakit scripts, with [agents]: each agent with what it signs, its about and its file; who reviews at each hook
    point – or what keeps the entries from resolving."""
    lines = ["", f"The project's agents – [agents.<name>] of {cfg.path.name} (handbook 8.6)", ""]
    width = max(len(n) for n in cfg.agents)
    pad = " " * (width + 2)
    for name, a in cfg.agents.items():
        lines.append(f"{name:<{width}}  {_agent_said(a)}")
        lines += [pad + a[k] for k in ("about", "file") if a.get(k)]
    lines.append("")
    if review.findings:
        return lines + ["The agents' entries do not resolve (edakit check, handbook 8.6):",
                        *[f"  {f.msg}" for f in review.findings]]
    who = max(len(w) for items in review.at.values() for w, _ in items)
    lines.append("Who reviews where – each in its own session; a project agent in place of the edakit agent it "
                 "replaces:")
    for h, title in HOOKS.items():
        lines.append(f"  {title}")
        lines += [f"    {w:<{who}}  {what}" for w, what in review.at[h]] or ["    none"]
    return lines
