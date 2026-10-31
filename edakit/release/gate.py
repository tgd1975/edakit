"""Release gate: runs every stage and writes a test protocol. Only a run that says RELEASED may go to the manufacturer.

    edakit gate             P (parts), G (graph), E (simulation) and the project's checks before S; offline, seconds
    edakit gate --easyeda   plus S (schematic), L (board), F (manufacturing files) and the project's checks after F;
                            EasyEDA with the bridge, minutes

The project's checks ([[release.stages]] and [scripts.<name>] of kind check, scripts.gate_checks): phase export is a
stage each, with its id – stage_checks runs it; phase order and acceptance are lines of section 6, after the export.

Result: <reports>/<YYYYMMDD-hhmmss>/
    protocol.md            readable protocol: header with hashes, stages, findings with actual and expected value,
                           warnings and who accepted them, waivers, open sign-offs, manual checks, simulation table,
                           and the rule, reason and fix of every code that failed or warned (the catalog)
    graph_checks.json, sim.json, schematic_<board>.json   raw results
    fab/<board>/           Gerber ZIP, BOM and CPL in JLCPCB format plus raw data (stages L, F)
    fab/manifest.json      SHA-256 of every file to upload – the files of every maker of [cart] makers –, the
                           hashes of the checked state, the decision, and whether the run is the current release
                           (status: released, superseded, withdrawn)
    makers.json            per maker of [cart] makers its role (planned or other) and the findings of its checks
                           (PARTS.stock, FILES.order, PARTS.fact/mpn, SYNC.odb) – edakit cart prepare stops for another maker with one

RELEASED only if
  - every stage ran and no check failed,
  - every warning is accepted in the sign-off file (only a human accepts warnings – it is a decision),
  - every part is verified and every manual check of phase 'export' is signed – the second datasheet check M-1, the
    regulatory review M-6 and the layout review M-5 also when the sign-off file does not list them (REQUIRED), and so
    the sign-off of a project agent ([agents.<name>], handbook 8.6: its own ID, or edakit's review it replaces); such a
    sign-off counts only signed by its agent – done_by names it –, one of its own only in the phase and scope of the
    agent's entry (held); one of phase acceptance is a line of the acceptance list,
  - all of that for exactly this state: sign-offs count only for the hash of their scope – 'circuit' (graph with its
    check settings, parts database, simulation config), 'layout' (the board files with the artwork they place,
    further layout_files of [release], the footprint geometry, the footprint data of the parts entries – footprint.py,
    only where an entry has it) or 'fab' (what the manufacturer builds from: the
    Gerber layers rasterised, the drill hits, BOM and CPL rows, with [order] the order settings that change the board
    as made – known after stage F, fab.fab_layers; a run without stage F counts no sign-off of scope 'fab' and names
    the fab hash a signed one is bound to: stage F checks it, it is not open). An accepted warning with scope
    'decision' counts regardless of the hash and refers to a numbered decision in the docs; one that names its parts
    ({designator: LCSC}) counts only while they are the same parts.
  - with [project] requirements (requirements.py): every requirement 'must' has passing evidence in this run, and
    every 'should' without it is accepted like a warning – section 11 of the protocol lists them all, section 6 the
    acceptance steps. A draft binds nothing yet: it never blocks and needs no acceptance, the findings about it are
    information. The requirements files count in the circuit hash byte for byte, after its other files. A
    requirements file that is missing or not valid stops the gate before its first stage.
[release] hash_ignore leaves documentation keys (notes, sources, verified, …) out of the circuit hash: graph and parts
entries are hashed as canonical JSON without them. Turning it on is recorded in `rehashed` of the sign-off file when
the files are the signed ones.
Exit code: 0 = released, 2 = not released, 1 = tool error.

One current release: a RELEASED run supersedes every earlier released run of the project (their manifests say
"released": false, "status": "superseded", "superseded_by": <run>), and a released run can be withdrawn.

    edakit release current             the current release: run, time, git, graph version, files with SHA-256
    edakit release withdraw RUN --reason TEXT   the run is withdrawn – then there is no current release
    edakit release verify FILE…|DIR    the files about to be uploaded = the files of the current release?
    edakit release publish             what is ordered as a GitHub release (publish.py)

Gate runs are build output: they stay in <reports>, which git ignores, and nothing of them is committed – what is
ordered is published with the order (edakit release publish). [release] archive = "git" is the opt-in for a project
that commits its released runs: `release current` then names a released run git does not track yet, and the protocol
names the setting in its header.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import getpass
import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
from collections import Counter, defaultdict
from fnmatch import fnmatch
from pathlib import Path

from .. import catalog, docs, eda, requirements
from ..config import ConfigError
from ..design import KEYED, Design, graph_of_toml
from ..toolchain import is_kicad

STAGES = [
    ("P", "Parts", "parts database complete, graph pins = parts database, parts verified, parts orderable"),
    ("G", "Graph", "structure, pin locks, voltage domains, inputs, drivers, decoupling, ratings, reverse polarity"),
    ("E", "Simulation", "ngspice operating points of all scenarios, stress of every part, function limits"),
    ("S", "Schematic", "EasyEDA schematic = graph (parts, LCSC, nets, pins, no-connects)"),
    ("L", "Board", "PCB = graph and plan, copper from the Gerber files, DRC, footprints, track widths, holes"),
    ("F", "Manufacturing", "BOM from the graph = EasyEDA, JLCPCB stock, pick and place, Gerber set, outline, manifest"),
]
OFFLINE, WITH_EASYEDA = "PGE", "SLF"
PHASES = [("export", "before the export (condition of the release)"),
          ("order", "after uploading to the manufacturer, before paying"),
          ("acceptance", "after delivery, per board")]
SCOPE_KEY = {"circuit": "state_sha256", "layout": "layout_sha256", "fab": "fab_sha256"}
REQUIRED = {   # manual checks every release needs, also when an older sign-off file does not list them
    "M-1": {"phase": "export", "scope": "circuit",
            "text": "Critical parts checked a second time against their datasheets, independently – the agent "
                    "electrical-reviewer in its own session"},
    "M-6": {"phase": "export", "scope": "circuit",
            "text": "Regulatory review: circuit and parts against EU law for the stated purpose (RoHS, REACH, radio, "
                    "batteries, product safety) – the agent regulatory-reviewer in its own session; support, not "
                    "legal advice: no claim to correctness, nothing legally guaranteed"},
    "M-5": {"phase": "export", "scope": "fab",
            "text": "Layout reviewed independently (manufacturability, mechanics, operation, looks) on the "
                    "manufacturing files of a gate run – the agent pcb-reviewer. No finding 'block' open, every "
                    "'important' finding fixed or rejected by the owner"},
}
UPLOAD = ["gerber_{b}.zip", "bom_{b}.csv", "cpl_{b}.csv"]   # JLCPCB's; with [cart] the files of every maker (upload)
MAKERS = "makers.json"   # per maker of [cart] makers: its role in the run and its findings (edakit cart prepare)
WHEN = ("order", "acceptance")   # verified.open {text, when}: the phase whose manual checks answer the point
RESULT = {"pass": "passed", "fail": "FAILED", "warn": "warning", "info": "information", "advisory": "advisory",
          "waived": "waived", "pending": "open"}


def sh(cwd, *cmd, timeout=30):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


KEEP_WHOLE = ("purpose", "compliance")   # read whole by the regulatory review M-6: hash_ignore never reaches inside


def strip(data, ignore):
    """data without the keys in ignore, at any depth – except inside KEEP_WHOLE."""
    if isinstance(data, dict):
        return {k: v if k in KEEP_WHOLE else strip(v, ignore) for k, v in data.items() if k not in ignore}
    if isinstance(data, list):
        return [strip(v, ignore) for v in data]
    return data


def arranged(graph):
    """A graph with the arrangement of its form taken out: components sorted by designator, nets and cables by name,
    the pins of a net sorted – the order no check reads (circuit-language decision 2)."""
    out = dict(graph)
    for key, field in KEYED.items():           # graph_of_toml made each a list of tables
        if isinstance(out.get(key), list):
            out[key] = sorted(out[key], key=lambda row: str(row[field]))
    if isinstance(out.get("nets"), list):
        out["nets"] = [{**n, "pins": sorted(n["pins"], key=str)} if isinstance(n.get("pins"), list) else n
                       for n in out["nets"]]
    return out


def content(path, ignore=(), graph=False):
    """What the hash takes of a file: its bytes; with ignore, a JSON file as canonical JSON (sorted keys, no
    whitespace) without those keys. A file that is no valid JSON stays bytes. graph: the file is the project's graph –
    a TOML graph is read as data in any case and taken as canonical JSON, arranged, without the keys of ignore, so that
    a comment, a blank line and a table or pin moved count for nothing; one that does not load stays bytes. A JSON
    graph as any JSON file."""
    path = Path(path)
    if not path.exists():
        return b"<missing>"
    raw = path.read_bytes()
    if graph and path.suffix == ".toml":
        try:
            data = arranged(graph_of_toml(raw.decode("utf-8"), path))
        except (ConfigError, UnicodeDecodeError):
            return raw
    elif not ignore:
        return raw
    else:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return raw
    return json.dumps(strip(data, set(ignore)), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def file_hash(root, files, ignore=(), documented=(), extra=(), graph=None):
    """SHA-256 over the names and contents of files; the files in `documented` without the keys in ignore, the graph
    file `graph` as content() takes a graph. extra: [(name, bytes)] taken after the files the same way – none, and the
    hash is that of the files alone."""
    h = hashlib.sha256()
    documented = {Path(f) for f in documented}
    for f in files:
        h.update(str(Path(f).relative_to(root) if Path(f).is_relative_to(root) else f).encode() + b"\0"
                 + content(f, ignore if Path(f) in documented else (), graph is not None and Path(f) == Path(graph)))
    for name, data in extra:
        h.update(name.encode() + b"\0" + data)
    return h.hexdigest()


def state_files(cfg):
    files = [cfg.graph, cfg.sim_config, *sorted(cfg.parts.glob("*.json"))]
    if cfg.sim_plugin:
        files.append(cfg.sim_plugin)
    files += [cfg.resolve(f) for f in cfg.release.get("state_files", [])]
    return files + list(cfg.requirements)   # [project] requirements, last: without the key the hash stays as it was


def state_hash(cfg, ignore=None):
    """The circuit hash (state_sha256). [release] hash_ignore leaves its keys out of the graph and the parts entries;
    the simulation config (its `sources` are the supplies), the plugin, state_files and the requirements files stay
    bytes – the reviews read the requirements whole. A TOML graph counts with its data, a JSON graph with its bytes
    or, with hash_ignore, as canonical JSON (content)."""
    ignore = cfg.release.get("hash_ignore", []) if ignore is None else ignore
    return file_hash(cfg.root, state_files(cfg), ignore, [cfg.graph, *cfg.parts.glob("*.json")], graph=cfg.graph)


def layout_files(cfg):
    from ..pcb import geometry_file
    made = cfg.made()     # a bought or hand-wired board has no layout: no board file, no artwork, no footprint geometry
    files = [cfg.resolve(b.file) for b in made.values()]
    # the artwork the board files place ([[silk.art]]), each SVG once however often it is placed
    files += dict.fromkeys(cfg.resolve(a["svg"]) for b in made.values() for a in b.silk.get("art", [])
                           if "svg" in a)
    files += [cfg.resolve(f) for f in cfg.release.get("layout_files", [])]
    # the footprint geometry beside each board file; one not moved there yet where it lies (pcb.geometry_file)
    return files + [geometry_file(cfg, b) for b in made.values()]


def footprint_data(cfg):
    """[(name, bytes)] the layout hash takes after its files: the footprint data (4.5) of every parts entry that a
    part of a made board uses, as "footprint_data:<entry>" and canonical JSON without the keys of [release]
    hash_ignore, in the order of the entries – none where no entry has footprint data, so every project without it
    keeps its layout hash. The data is the copy's geometry before any dump: a changed pad voids the sign-offs of scope
    layout as a changed geometry does."""
    from ..footprint import has_data
    design = Design.from_config(cfg)
    if not has_data(design.parts):
        return []
    made = set(cfg.made())
    keys = {k for des, c in design.comps.items() if (c.get("board") in made or c.get("board") is None)
            and (k := design.entry_key(des)) and "footprint_data" in design.parts[k]}
    ignore = set(cfg.release.get("hash_ignore", []))
    return [(f"footprint_data:{k}", json.dumps(strip(design.parts[k]["footprint_data"], ignore), sort_keys=True,
                                               separators=(",", ":"), ensure_ascii=False).encode())
            for k in sorted(keys)]


def layout_hash(cfg):
    """The layout hash (layout_sha256): the files of layout_files and the footprint data of the made boards' parts."""
    return file_hash(cfg.root, layout_files(cfg), extra=footprint_data(cfg))


def header(cfg):
    from .. import __version__
    design = Design.from_config(cfg)
    mcp = re.search(r"EASYEDA_MCP_VERSION:-([\d.]+)",
                    (Path(__file__).resolve().parents[1] / "easyeda" / "mcp-server.sh").read_text())
    tools = {"python": platform.python_version(), "edakit": __version__,
             "ngspice": (re.findall(r"ngspice-[\d.]+", sh(cfg.root, "ngspice", "-v")) or ["ngspice ?"])[0],
             "easyeda-mcp-pro": mcp.group(1) if mcp else "?"}
    if is_kicad(cfg):                 # the tool chain the stages S, L and F ran with (handbook 16)
        from ..toolchain.kicad import cli
        try:
            tools["kicad"] = cli.version()
        except cli.CliError:
            tools["kicad"] = "?"
    return {
        "graph_sha256": hashlib.sha256(cfg.graph.read_bytes()).hexdigest(),
        "state_sha256": state_hash(cfg),
        "layout_sha256": layout_hash(cfg),
        "graph_version": design.version, "graph_date": design.graph.get("date"),
        "git_commit": sh(cfg.root, "git", "rev-parse", "--short", "HEAD"),
        "git_dirty": bool(sh(cfg.root, "git", "status", "--porcelain")),
        "time": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "tester": sh(cfg.root, "git", "config", "user.name") or getpass.getuser(),
        "tools": tools,
    }


def rehash(cfg, s, head):
    """The `rehashed` entry when only [release] hash_ignore changed since the sign-offs of scope 'circuit': the file's
    state_sha256 is the hash of the current files with the list recorded last (none: the bytes). Otherwise None."""
    now = list(cfg.release.get("hash_ignore", []))
    before = next((r["hash_ignore"] for r in reversed(s.get("rehashed", [])) if "hash_ignore" in r), [])
    signed = s.get("state_sha256")
    if not signed or signed == head.get("state_sha256") or sorted(before) == sorted(now):
        return None
    if state_hash(cfg, before) != signed:
        return None
    return {"date": dt.date.today().isoformat(), "by": "edakit gate",
            "why": f"[release] hash_ignore = {json.dumps(now)}" + (f" (was {json.dumps(before)})" if before else "")
                   + ": the circuit hash leaves these keys out; the files are the signed ones",
            "hash_ignore": now, "state_sha256": [signed, head["state_sha256"]]}


def lapsed(cfg, warns):
    """(acceptances that count, acceptances whose parts changed with 'lapsed': why). An acceptance with
    parts {designator: LCSC} counts only while every designator still has that number in the graph."""
    if not any("parts" in a for a in warns):
        return warns, []
    comps = Design.from_config(cfg).comps
    keep, gone = [], []
    for a in warns:
        named = a.get("parts")
        if named is None:
            keep.append(a)
            continue
        if not isinstance(named, dict):
            gone.append({**a, "lapsed": "parts is not {designator: LCSC}"})
            continue
        now = {des: comps[des].get("lcsc") or comps[des].get("part") for des in named if des in comps}
        why = [f"{des} is not in the graph" if des not in comps else f"{des} is now {now[des] or 'without an LCSC number'}"
               for des, num in named.items() if des not in comps or now[des] != num]
        if why:
            gone.append({**a, "lapsed": "; ".join(why)})
        else:
            keep.append(a)
    return keep, gone


def load_signoff(cfg, head, write=False):
    """Sign-offs and accepted warnings that count for the current hash of their scope. A required manual check the
    file does not list is added as open – also the sign-off of a project agent ([agents.<name>], required): it counts
    only signed by its agent (held). When only [release] hash_ignore changed, the circuit sign-offs keep counting and
    the old and new hash go into `rehashed` – into the file only with write (the gate). Without stage F (no fab_sha256
    in head) a signed manual check of scope 'fab' does not count either, but is not open: `unchecked` holds the file's
    fab_sha256 it is bound to and who signed it, for decide and the protocol."""
    from .. import scripts
    path = cfg.signoff
    missing = not path.exists()          # no file: nothing is signed, and every required check is open
    s = {} if missing else json.loads(path.read_text(encoding="utf-8"))
    notes = [f"{path.name} missing – no sign-offs; the required checks are open"] if missing else []
    valid = {"decision": True}
    if not missing and (entry := rehash(cfg, s, head)):
        old, new = entry["state_sha256"]
        s["state_sha256"] = new
        s.setdefault("rehashed", []).append(entry)
        notes.append(f"{path.name}: rehashed – {entry['why']}; state_sha256 {old[:12]}… → {new[:12]}…")
        if write:
            save_manifest(path, s, indent=2)
            print(f"  {notes[-1]}")
    used = {x.get("scope", "circuit") for x in [*s.get("manual", []), *s.get("accept", [])]}
    bound = s.get("fab_sha256") if head.get("fab_sha256") is None else None   # signed for a hash this run lacks
    for scope, key in SCOPE_KEY.items():
        if scope == "fab" and head.get(key) is None:   # known only after stage F
            valid[scope] = False
            if scope in used:
                notes.append(f"{path.name}: sign-offs with scope 'fab' are bound to fab {bound[:12]}… – a hash only "
                             "stage F computes: this run cannot check them, stage F does" if bound else
                             f"{path.name}: sign-offs with scope 'fab' are not checked in a run without stage F "
                             "(no fab_sha256) and do not count")
            continue
        valid[scope] = s.get(key) == head.get(key)
        if not (missing or valid[scope]) and (scope != "fab" or scope in used or key in s):
            notes.append(f"{path.name}: sign-offs with scope '{scope}' belong to another state ({key}) and do not count")
    team = scripts.agents(cfg)          # [agents.<name>]: what the project's agents sign, held to them
    manual = []
    for m in s.get("manual", []):
        unchecked = bound and m.get("scope", "circuit") == "fab" and m.get("done_by")
        m = held(m if valid.get(m.get("scope", "circuit")) or unchecked else {**m, "done_by": None},
                 team.signers.get(m.get("id")), path.name, notes)
        if unchecked and m.get("done_by"):  # it does not count here, and is not open: stage F holds it to its hash
            m = {**m, "done_by": None, "unchecked": {"fab_sha256": bound, "by": m["done_by"]}}
        manual.append(m)
    for sid, m in required(cfg, team).items():
        if sid not in {x.get("id") for x in manual}:
            agent = team.signers.get(sid)
            manual.append({"id": sid, **m, "done_by": None,
                           **({"agent": agent.name, "replaces": agent.replaces} if agent else {})})
            notes.append(f"{path.name}: {sid} is missing – added as open, " + (
                "every release needs it" if sid in REQUIRED else
                f"the project agent {agent.name} signs it ([agents.{agent.name}])"))
    warns, gone = lapsed(cfg, [a for a in s.get("accept", []) if valid.get(a.get("scope", "circuit"))])
    return {**s, "manual": manual, "accept": warns, "lapsed": gone}, notes


def key_of(item):
    """'GEO.hole main D2: hole tight …' – what an accept of the sign-off file is matched against: code, scenario, item
    and check; the item left out where the check starts with it (a finding of stage P or G names its place first)."""
    check = str(item.get("check", ""))
    keys = [k for k in ("id", "scenario", "item", "check") if item.get(k, "") != ""
            and not (k == "item" and check.startswith(str(item[k])))]
    return " ".join(str(item[k]) for k in keys)


def accepted(item, signoff):
    return next((a for a in signoff.get("accept", []) if fnmatch(key_of(item), a["match"])), None)


def datasheet_open(cfg):
    """Per parts entry of the graph: its designators, the open points of its datasheet sign-off (verified.open – a
    text, or {text, when} with the phase that answers it) and its sources marked as an assumption. Information for
    section 6 of the protocol; the decision does not read it. Returns ([{who, open: [(text, when)], assumptions}],
    notes)."""
    from ..design import natural_key
    from ..stock import refs_text
    design = Design.from_config(cfg)
    users = defaultdict(list)
    for des in design.comps:
        if key := design.entry_key(des):
            users[key].append(des)
    out, notes = [], []
    for key, refs in sorted(users.items(), key=lambda kv: natural_key(kv[0])):
        part, items = design.parts[key], []
        for o in (part.get("verified") or {}).get("open") or []:
            text, when = (str(o.get("text", "")), o.get("when")) if isinstance(o, dict) else (str(o), None)
            if when is not None and when not in WHEN:
                notes.append(f"{key}: open point with when {when!r} – known: {', '.join(WHEN)}; listed without a phase")
                when = None
            items.append((text, when))
        assumed = [s for s in part.get("sources") or [] if isinstance(s, str) and re.search(r"\bassumption", s, re.I)]
        if items or assumed:
            name = key + (f" {part['mpn']}" if part.get("mpn") and part["mpn"] != key else "")
            out.append({"who": f"{name} ({refs_text(sorted(refs, key=natural_key))})", "open": items,
                        "assumptions": assumed})
    return out, notes


def datasheet_list(found):
    """The list "Open from the datasheets" at the end of section 6; nothing when nothing is open."""
    if not found:
        return []
    title = dict(PHASES)
    L = ["\n**Open from the datasheets** (information – the release does not depend on it)\n"]
    for e in found:
        L.append(f"- {e['who']}")
        L += [f"  - open{', ' + title[w] if w else ''}: {t}" for t, w in e["open"]]
        L += [f"  - assumption: {s}" for s in e["assumptions"]]
    return L


RESULT_OF = {"error": "fail", "warning": "warn", "note": "info", "pending": "pending"}


def stage_graph(cfg, design):
    """Stages P and G: the findings of edakit check as rows – an accepted one with its reason, a note or a finding about
    a draft of the requirements file as information –, and a passed row for every code the profile has on without a
    finding of severity error or pending."""
    from .. import engines
    rep = engines.run_all(design, cfg)
    rows = []
    for f in rep.findings:
        if f.code in ("SYNC.scripts", "SYNC.agents"):
            continue          # the project's scripts and agents: rows of their own, with what passed (scripts.gate_rows)
        result = "waived" if f.accepted and f.severity != "pending" else \
            "info" if f.data.get("draft") and f.severity == "warning" else RESULT_OF[f.severity]
        rows.append({"stage": f.stage if f.stage in "PG" else "G", "id": f.code, "item": f.place, "check": f.text,
                     "result": result, **({"reason": f.accepted} if result == "waived" else {})})
    hit = {r["id"] for r in rows if r["result"] in ("fail", "pending")}
    prof = engines.profile(design, cfg)
    rows += [{"stage": "P" if code.startswith(("PARTS.", "STRUCT.entry", "STRUCT.identity")) else "G", "id": code,
              "item": "", "check": catalog.title(code), "result": "pass"} for code in executed(prof, cfg) if code not in hit]
    from .. import cost
    rows += cost.gate_rows(cfg)   # with [cost]: the estimate, above the budget a warning
    return rows, rep.to_dict()


def executed(prof, cfg):
    """The codes of stages P and G a run checks, each counted once as passed where it has no finding: those of the
    engines on the graph and of the checks beyond it that the profile has on – the footprint data's only where an
    entry has footprint data, the requirements file's only with [project] requirements, PARTS.stock only with a
    maker of [cart] makers that orders from JLCPCB's catalogue; no hint, no suggestion note."""
    from ..findings import Finding
    from ..checks import has_footprint_data
    graph = ("STRUCT.", "LIM.", "LVL.", "REQ.", "PATH.", "PARTS.")
    beyond = ["SYNC.source", "GEO.hole", "GEO.formed"]
    beyond += ["SYNC.footprint"] if has_footprint_data(cfg) else []
    beyond += ["DOCS.ref", "DOCS.need", "DOCS.evidence", "DOCS.draft"] if cfg.requirements else []
    from .. import makers
    skip = {"STRUCT.domain"} | (set() if has_footprint_data(cfg) else {"PARTS.footprint"})
    if not makers.with_catalogue(cfg, "jlcpcb"):
        skip.add("PARTS.stock")       # no maker of [cart] makers orders from JLCPCB's catalogue: it does not run
    return [c for c in catalog.codes() if (c.startswith(graph) or c in beyond) and c not in skip
            and prof.on(Finding(c, "G", "", ""))]


def stage_checks(cfg, outdir, project_checks, step=None):
    """The project's checks of phase export (scripts.gate_checks: [[release.stages]] and [scripts] of kind check), each
    a stage of its own. Its cmd runs in the project folder, with EDAKIT_RUN naming this run's folder – after stage F
    its fab/<board>/ holds the manufacturing files; python as the first word of a [scripts] cmd is edakit's own, a
    [[release.stages]] runs as written (Check.argv). stdout and stderr go to stage_<id>.txt there. The last stdout line
    may be a JSON list of [id, check, actual, expected, ok]; otherwise only the exit code counts, 0 passes. A failure
    of an advisory check is an advisory row: listed, it does not block. Returns (rows, the ids of the checks run);
    step: eda.Steps, one step per check."""
    rows, run = [], set()
    env = {**os.environ, "EDAKIT_RUN": str(outdir.resolve())}
    for c in project_checks:
        if step:
            step(f"{c.id} {c.title}")
        run.add(c.id)
        log = outdir / f"stage_{c.id}.txt"
        try:
            if not c.cmd:
                raise OSError("no cmd")
            res = subprocess.run(c.argv(), capture_output=True, text=True, cwd=cfg.root, timeout=c.timeout, env=env)
            log.write_text(res.stdout + res.stderr, encoding="utf-8")
        except (OSError, subprocess.TimeoutExpired) as e:
            rows.append({"stage": c.id, "id": c.id, "item": c.title, "check": f"not runnable: {e}", "result": "fail"})
            continue
        bad = "advisory" if c.advisory else "fail"
        try:
            items = json.loads(res.stdout.strip().splitlines()[-1])
            rows += [{"stage": c.id, "id": i[0], "item": c.title, "check": i[1], "actual": i[2], "expected": i[3],
                      "result": "pass" if i[4] else bad} for i in items]
        except (IndexError, json.JSONDecodeError, TypeError):
            rows.append({"stage": c.id, "id": c.id, "item": c.title, "check": " ".join(c.cmd),
                         "actual": f"exit {res.returncode}", "expected": "exit 0",
                         "result": "pass" if res.returncode == 0 else bad})
    return rows, run


def listed_checks(project_checks, phase):
    """The project's checks of a phase after the export, one unchecked line each for that phase's list in section 6 –
    the manual check of the phase (M-2, M-4) works through it: id, name, what it checks, its command. A check of phase
    export is a stage, no line."""
    return [f"- [ ] {c.id} {c.title}: {c.about} – `{shlex.join(c.cmd)}`" for c in project_checks
            if c.phase == phase and phase in WHEN]


def unmade_row(stage, sid, board):
    """The information row of a stage that leaves a bought or hand-wired board out."""
    return {"stage": stage, "id": sid, "item": board.name, "check": f"{board.unmade} board – no schematic, PCB or "
            "manufacturing files", "result": "info"}


def stage_schematic(cfg, outdir):
    from .. import schematic
    from ..toolchain import is_kicad
    rows = []
    for board in cfg.boards.values():
        if board.unmade:
            rows.append(unmade_row("S", "SYNC.schematic", board))
            continue
        if is_kicad(cfg):              # the schematic is the KiCad project's (handbook 16): name it by its file
            board = dataclasses.replace(board, template=f"{board.name}.kicad_sch")
        out = outdir / f"schematic_{board.name}.json"
        args = argparse.Namespace(board=board.name, schematic=None, no_pins=False, json=str(out), verbose=False, wait=90)
        code = schematic.check(cfg, args)
        if code == 1:
            rows.append({"stage": "S", "id": "SYNC.schematic", "item": board.template, "check": "comparison not runnable",
                         "result": "fail"})
            continue
        found = json.loads(out.read_text()) if out.exists() else {}
        for section, msgs in found.items():
            rows += [{"stage": "S", "id": "SYNC.schematic", "item": f"{board.template}: {section}", "check": m,
                      "result": "fail"}
                     for m in msgs]
        if code == 0:
            rows.append({"stage": "S", "id": "SYNC.schematic", "item": board.template, "check": "schematic = graph",
                         "result": "pass"})
    return rows


def upload(cfg, board):
    """The files of a board every maker of [cart] makers takes, in the order of the makers – JLCPCB's three without
    [cart]."""
    from .. import makers
    return list(dict.fromkeys(name for m in makers.all_of(cfg) for name in m.upload(board)))


def maker_findings(cfg, rows):
    """{maker: {name, role, findings}} of a run: the rows a check that holds the board to that maker failed, warned or
    left open (PARTS.stock, FILES.order, PARTS.fact/mpn, SYNC.odb – the row names its maker, or its text starts with it)."""
    from .. import makers
    out = {}
    for key in makers.listed(cfg):
        m = makers.get(cfg, key)
        tag = f"{m.name} (not the planned maker): "
        hits = [r for r in rows if r["result"] in ("fail", "warn", "pending") and (
            r.get("maker") == key or str(r.get("check", "")).startswith(tag) or str(r.get("actual", "")).startswith(tag))]
        out[key] = {"name": m.name, "role": "planned" if key == makers.planned(cfg) else "other",
                    "findings": [{k: r.get(k, "") for k in ("stage", "id", "item", "check", "actual", "expected",
                                                            "result")} for r in hits]}
    return out


def stage_fab(cfg, outdir, step=None):
    from . import fab
    rows = []
    d = outdir / "fab"
    d.mkdir(exist_ok=True)
    rows += [unmade_row("L", "L", b) for b in cfg.boards.values() if b.unmade]
    for board in cfg.made().values():
        if step:  # one step per board: with EasyEDA up to five minutes each
            step(f"L/F board and manufacturing files: {board.name}")
        else:
            print(f"    {board.name} …", flush=True)
        try:
            rows += fab.run(cfg, board, d)
        except (SystemExit, Exception) as e:  # one board failing must not hide the others
            rows.append({"stage": "L", "id": "L", "item": board.name, "check": f"fab stage not runnable: {e}",
                         "result": "fail"})
        files = upload(cfg, board.name)
        lost = [f for f in files if not (d / board.name / f).exists()]
        what = "(Gerber ZIP, BOM, CPL)" if files == [p.format(b=board.name) for p in UPLOAD] else \
            f"of [cart] makers ({', '.join(files)})"
        rows.append({"stage": "F", "id": "FILES.manifest", "item": board.name, "check": f"manufacturing files of this run complete "
                     f"{what}, checksums in the manifest", "actual": ", ".join(lost) or "complete",
                     "expected": "complete", "result": "fail" if lost else "pass"})
    return rows


def fab_hashes(cfg, outdir):
    """fab_method, fab_layers per board and fab_sha256 of this run's manufacturing files (stage F)."""
    from . import fab
    try:
        layers = {b: fab.fab_layers(outdir / "fab" / b, b) for b in cfg.made()}
    except Exception as e:   # unreadable files: FILES.manifest/FILES.set name them; the sign-offs with scope 'fab' then do not count
        print(f"  fab hash not computed: {e}", file=sys.stderr)
        return {}
    return {"fab_method": fab.FAB_METHOD, "fab_layers": layers, "fab_sha256": fab.fab_hash(layers)}


def decide(rows, sim_checks, signoff, stages_run, stages, reqs=()):
    """reqs: requirements.evaluate of this run – [] without [project] requirements."""
    reasons = []
    n_fail = sum(r["result"] == "fail" for r in rows) + sum(c["result"] == "fail" for c in sim_checks)
    if n_fail:
        reasons.append(f"{n_fail} check(s) failed (section 2)")
    open_warn = [c for c in [*sim_checks, *rows] if c["result"] == "warn" and not accepted(c, signoff)]
    if open_warn:
        reasons.append(f"{len(open_warn)} warning(s) not accepted (section 3)")
    pend = sum(r["result"] == "pending" for r in rows)
    if pend:
        reasons.append(f"{pend} open sign-off(s) (section 5)")
    export = [m for m in signoff.get("manual", []) if m.get("phase", "export") == "export" and not m.get("done_by")]
    open_manual = [m for m in export if not m.get("unchecked")]
    if open_manual:
        reasons.append(f"{len(open_manual)} manual check(s) before the export open: "
                       + ", ".join(m["id"] for m in open_manual) + " (section 6)")
    if unchecked := [m for m in export if m.get("unchecked")]:     # without stage F: signed for a fab hash
        reasons.append(f"{', '.join(m['id'] for m in unchecked)} signed for fab "
                       f"{unchecked[0]['unchecked']['fab_sha256'][:12]}… – checked by stage F (section 6)")
    missing = [f"{sid} ({name})" for sid, name, _ in stages if sid not in stages_run]
    if missing:
        reasons.append("stages not run: " + ", ".join(missing))
    reasons += requirements.reasons(reqs, signoff)   # [project] requirements: must blocks, should until accepted
    return ("RELEASED" if not reasons else "NOT RELEASED"), reasons


def write_manifest(cfg, outdir, head, decision):
    """fab/manifest.json of this run. A RELEASED run is the current release: every earlier run that says released is
    superseded by it."""
    fab = outdir / "fab"
    files = {}
    for b in cfg.made():
        for name in upload(cfg, b):
            f = fab / b / name
            if f.exists():
                files[str(f.relative_to(outdir))] = hashlib.sha256(f.read_bytes()).hexdigest()
    manifest = {"released": decision == "RELEASED", "decision": decision, "time": head["time"],
                "git": head["git_commit"] + (" + uncommitted changes" if head["git_dirty"] else ""),
                "graph_version": head.get("graph_version"),
                "graph_sha256": head["graph_sha256"], "state_sha256": head["state_sha256"],
                "layout_sha256": head["layout_sha256"], "files": files}
    if head.get("fab_sha256"):
        manifest.update(fab_method=head["fab_method"], fab_sha256=head["fab_sha256"], fab_layers=head["fab_layers"])
    if decision == "RELEASED":
        manifest["status"] = "released"
    fab.mkdir(exist_ok=True)
    save_manifest(fab / "manifest.json", manifest)
    if decision == "RELEASED":
        try:
            supersede(cfg, outdir.name)
        except ReleaseError as e:    # the run stays released; the protocol and `release current` still get written
            print(f"  earlier runs not superseded: {e}", file=sys.stderr)
    return files


# --- the sign-offs of the project's agents ([agents.<name>], handbook 8.6) --------------------------------------------

def required(cfg, team=None):
    """The manual checks every release needs (REQUIRED), then the sign-offs of the project's agents with an ID of their
    own (scripts.agents, team) in the phase and scope of their entry: {id: {phase, scope, text}}. An agent that takes
    over one of edakit's reviews (replaces) signs that one – REQUIRED has it."""
    from .. import scripts
    team = team or scripts.agents(cfg)
    return {**REQUIRED, **{sid: {"phase": a.phase, "scope": a.scope,
                                 "text": (f"{a.about} – " if a.about else "") + f"the project agent {a.name}, in its "
                                                                                 "own session"}
                           for sid, a in team.signers.items() if not a.replaces}}


def held(m, agent, name, notes):
    """A manual check of the sign-off file (its name) that a project agent signs: one of its own in the phase and scope
    of the agent's entry – signed for another binding it does not count –, and every one only signed by the agent:
    done_by names it (scripts.names_agent). The entry gets the agent and the edakit agent it replaces."""
    from .. import scripts
    if agent is None:
        return m
    m = {**m, "agent": agent.name, "replaces": agent.replaces}
    was = (m.get("phase", "export"), m.get("scope", "circuit"))
    if not agent.replaces and was != (agent.phase, agent.scope):
        if m.get("done_by"):
            notes.append(f"{name}: {m['id']} has phase {was[0]} and scope {was[1]}, [agents.{agent.name}] phase "
                         f"{agent.phase} and scope {agent.scope} – signed for another binding, it does not count")
        m.update(phase=agent.phase, scope=agent.scope, done_by=None)
    elif m.get("done_by") and not scripts.names_agent(m["done_by"], agent.name):
        notes.append(f"{name}: {m['id']} is signed by {m['done_by']} – [agents.{agent.name}]: the project agent "
                     f"{agent.name} signs it" + (f" in place of {agent.replaces}" if agent.replaces else "")
                     + "; it does not count")
        m["done_by"] = None
    return m


def signer(m):
    """Who signs an open manual check that a project agent signs, for its line in section 6 – nothing when its text
    names the agent already."""
    from .. import scripts
    if not m.get("agent") or m.get("done_by") or m.get("unchecked") or scripts.names_agent(m.get("text"), m["agent"]):
        return ""
    return f" – the project agent {m['agent']} signs it" + (f", in place of {m['replaces']}" if m.get("replaces") else "")


# --- one current release ------------------------------------------------------------------------------------------

class ReleaseError(Exception):
    pass


def save_manifest(path, manifest, indent=1):
    path.write_text(json.dumps(manifest, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8")


def runs(cfg):
    """Gate runs with a manifest, oldest first: [(run, manifest file, manifest)]."""
    out = []
    for m in sorted(cfg.reports.glob("*/fab/manifest.json")):
        try:
            out.append((m.parent.parent.name, m, json.loads(m.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError) as e:
            raise ReleaseError(f"{m}: not readable ({e})") from e
    return out


def current(cfg):
    """(run, manifest) of the current release – the newest run whose manifest says released – or None. Manifests from
    before superseding (no status) read the same way."""
    return next(((run, data) for run, _, data in reversed(runs(cfg)) if data.get("released")), None)


def status(data):
    """What a run is, in words: released, superseded by …, withdrawn: …, not released."""
    if data.get("withdrawn"):
        return f"withdrawn: {data['withdrawn'].get('reason')}"
    if data.get("superseded_by"):
        return f"superseded by {data['superseded_by']}"
    return "released" if data.get("released") else "not released"


def supersede(cfg, run):
    """Every earlier run that says released is superseded by run: [their names]."""
    done = []
    for name, path, data in runs(cfg):
        if name < run and data.get("released"):
            data.update(released=False, status="superseded", superseded_by=run)
            save_manifest(path, data)
            done.append(name)
    return done


def withdraw(cfg, run, reason, by=None):
    """The run is withdrawn: released false, status withdrawn, {reason, by, date}. Earlier runs that still say released
    (manifests from before superseding) are superseded by it, so that none of them becomes current instead."""
    path = cfg.reports / run / "fab" / "manifest.json"
    if not path.exists():
        raise ReleaseError(f"{run}: no gate run with a manifest in {cfg.reports}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("decision") != "RELEASED":
        raise ReleaseError(f"{run}: the gate did not release it ({data.get('decision')}) – nothing to withdraw")
    if data.get("withdrawn"):
        raise ReleaseError(f"{run}: already withdrawn ({data['withdrawn'].get('reason')})")
    by = by or sh(cfg.root, "git", "config", "user.name") or getpass.getuser()
    data.update(released=False, status="withdrawn",
                withdrawn={"reason": reason, "by": by, "date": dt.date.today().isoformat()})
    save_manifest(path, data)
    return supersede(cfg, run)


def archive(cfg):
    """[release] archive: "none" – gate runs are build output, nothing of them is committed – or "git"."""
    return cfg.release.get("archive", "none")


def untracked(cfg, run):
    """With [release] archive = "git": the run's folder, relative to the project, while git tracks none of its files –
    None when it does, with archive "none", or outside a git repository."""
    if archive(cfg) != "git":
        return None
    d = cfg.reports / run
    try:
        p = subprocess.run(["git", "ls-files", "--", str(d)], cwd=cfg.root, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return cfg.relative(d) if p.returncode == 0 and not p.stdout.strip() else None


def upload_files(paths):
    """The files to check: each FILE, and every .zip and .csv file in and below each DIR."""
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in (".zip", ".csv"))
        elif p.is_file():
            files.append(p)
        else:
            raise ReleaseError(f"{p}: not found")
    if not files:
        raise ReleaseError(f"no file to check in {', '.join(map(str, paths))} (a folder: its .zip and .csv files)")
    return files


def verify(cfg, paths):
    """Each file against the current release: [(file, ok, what)] – ok only for a file of the current release; another
    run's file is named with that run and its status, a file of no run is unknown."""
    known = defaultdict(list)            # SHA-256 -> [(run, path in the run, manifest)], oldest first
    for run, _, data in runs(cfg):
        for rel, sha in data.get("files", {}).items():
            known[sha].append((run, rel, data))
    cur = current(cfg)
    out = []
    for f in upload_files(paths):
        hits = known.get(hashlib.sha256(f.read_bytes()).hexdigest(), [])
        mine = [rel for run, rel, _ in hits if cur and run == cur[0]]
        if mine:
            out.append((f, True, f"current release {cur[0]} ({mine[0]})"))
        elif hits:
            run, rel, data = hits[-1]
            more = len({r for r, _, _ in hits}) - 1
            out.append((f, False, f"from run {run} ({status(data)})" + (f", also in {more} earlier run(s)" if more else "")
                        + " – " + (f"the current release is {cur[0]}" if cur else "there is no current release")))
        else:
            out.append((f, False, f"unknown – no gate run in {cfg.reports} has this file"))
    return cur, out


def main_release(cfg, args):
    try:
        if args.action == "current":
            cur = current(cfg)
            if not cur:
                last = next((f"{run} {status(d)}" for run, _, d in reversed(runs(cfg)) if d.get("decision") == "RELEASED"),
                            None)
                print("current release: none" + (f" (newest released run: {last})" if last else ""))
                return 2
            run, data = cur
            print(f"current release: {run} ({data.get('time')}), git {data.get('git') or '?'}"
                  + (f", graph {data['graph_version']}" if data.get("graph_version") else
                     f", graph sha256 {str(data.get('graph_sha256'))[:12]}"))
            for rel, sha in data.get("files", {}).items():
                print(f"  {rel}  {sha}")
            if folder := untracked(cfg, run):     # [release] archive = "git": the released run goes into git
                print(f"  not in git yet: git add -f {folder} – with the superseded manifests")
            from .. import cart
            for board, maker, number, est, quote, actual, cur in cart.totals_of(cfg, run):
                fmt = lambda v: "–" if v is None else f"{v:.2f}"  # noqa: E731
                print(f"  order {number} at {maker}, board {board}: estimate {fmt(est)}, quote {fmt(quote)}, actual "
                      f"{fmt(actual)} {cur}".rstrip())
            return 0
        if args.action == "withdraw":
            if len(args.items) != 1 or not args.reason:
                raise ReleaseError("withdraw RUN --reason TEXT: one run and why")
            run = args.items[0]
            also = withdraw(cfg, run, args.reason)
            print(f"{run} withdrawn: {args.reason}" + (f"; superseded as well: {', '.join(also)}" if also else ""))
            cur = current(cfg)
            print(f"current release: {cur[0] if cur else 'none'}")
            return 0
        cur, found = verify(cfg, args.items)
        for f, ok, what in found:
            print(f"{'ok  ' if ok else 'FAIL'} {f.name}: {what}  [{f}]")
        bad = sum(not ok for _, ok, _ in found)
        print(f"{len(found) - bad} of {len(found)} file(s) of the current release {cur[0] if cur else '(none)'}"
              + ("" if not bad else " – do not upload"))
        return 2 if bad else 0
    except ReleaseError as e:
        print(f"edakit release: {e}", file=sys.stderr)
        return 1


def write_protocol(cfg, outdir, head, rows, sim, signoff, notes, decision, reasons, stages_run, stages, files,
                   reqs=(), project_checks=()):
    """reqs: requirements.evaluate of this run; with [project] requirements the protocol gets section 11 and the
    acceptance steps in section 6 – without the key it is the protocol it always was. project_checks: the project's
    checks (scripts.gate_checks); those of phase order and acceptance are lines of section 6."""
    by_stage = defaultdict(Counter)
    for r in rows:
        by_stage[r["stage"]][r["result"]] += 1
    for c in sim["checks"]:
        by_stage["E"][c["result"]] += 1
    unmade = "".join(f"; {what}, not made: {', '.join(n for n, b in cfg.boards.items() if b.unmade == what)}"
                     for what in ("bought", "hand-wired") if any(b.unmade == what for b in cfg.boards.values()))
    L = [f"# Test protocol – release check {cfg.project}\n", "| | |\n|---|---|",
         f"| Date | {head['time']} |", f"| Run by | {head['tester']} |",
         f"| Object | `{cfg.relative(cfg.graph)}` v{head['graph_version']} ({head['graph_date']}), boards "
         f"{', '.join(cfg.made())} in "
         + (f"KiCad projects {cfg.relative(cfg.artifacts / 'kicad')}/<board>" if is_kicad(cfg) else
            f"EasyEDA project {cfg.project}")
         + f"{unmade} |",
         f"| SHA-256 graph | `{head['graph_sha256']}` |",
         f"| SHA-256 circuit | `{head['state_sha256']}` (graph, parts database, simulation config"
         f"{', requirements' if cfg.requirements else ''}) |",
         f"| SHA-256 layout | `{head['layout_sha256']}` (board files, artwork, layout files, footprint geometry"
         + (", footprint data" if footprint_data(cfg) else "") + ") |",
         *([f"| SHA-256 fab | `{head['fab_sha256']}` (what the manufacturer builds from: Gerber layers, drill hits, "
            f"BOM and CPL rows, with [order] the order settings – {head['fab_method']}) |"]
           if head.get("fab_sha256") else []),
         f"| Git | `{head['git_commit']}`{' + uncommitted changes' if head['git_dirty'] else ''} |",
         "| Archive | " + ("`git` ([release] archive): a released run is committed – `git add -f "
                           f"{cfg.relative(outdir)}` with the superseded manifests (8.3) |" if archive(cfg) == "git" else
                           "`none` ([release] archive): the run is build output, not committed – what is ordered is "
                           "published with the order, `edakit release publish` (8.3) |"),
         f"| Tools | Python {head['tools']['python']}, edakit {head['tools']['edakit']}, {head['tools']['ngspice']}, "
         + (f"KiCad {head['tools'].get('kicad', '?')} (kicad-cli) |" if "kicad" in head["tools"] else
          f"easyeda-mcp-pro {head['tools']['easyeda-mcp-pro']} |"),
         f"| **Result** | **{decision}** |\n"]
    if reasons:
        L += ["Reasons:\n", *[f"- {r}" for r in reasons], ""]
    L += ["## 1 Stages\n", "| Stage | Content | passed | failed | warning | waived | open | result |",
          "|---|---|---:|---:|---:|---:|---:|---|"]
    for sid, name, what in stages:
        c = by_stage[sid]
        res = ("not run" if sid not in stages_run else "**failed**" if c["fail"] else
               "passed with reservations" if c["warn"] or c["pending"] else
               "advisories (do not block)" if c["advisory"] else "passed")
        L.append(f"| {sid} {name} | {what} | {c['pass']} | {c['fail']} | {c['warn']} | {c['waived']} | {c['pending']} | {res} |")
    from .. import engines
    prof = engines.profile(Design.from_config(cfg), cfg)
    on = ["core", *prof.enabled]
    L += [f"\nIn P (parts) and G (graph) every code without a finding counts once as passed – the codes the "
          f"domain{'s' if len(on) > 1 else ''} {', '.join(on)} {'have' if len(on) > 1 else 'has'} on: "
          + ", ".join(executed(prof, cfg)) + ".\n",
          "## 2 Findings\n"]
    fails = [r for r in rows if r["result"] == "fail"] + [c | {"stage": "E"} for c in sim["checks"] if c["result"] == "fail"]
    advis = [r for r in rows if r["result"] == "advisory"]
    if advis:
        L += ["Advisories (do not block the release):\n",
              *[f"- {r['id']} {r['check']}: {r.get('actual', '')} (expected {r.get('expected', '')})" for r in advis], ""]
    if not fails:
        L.append("No check failed.\n")
    else:
        L += ["| Stage | Check | Scenario | Item | Step | Actual | Expected |", "|---|---|---|---|---|---|---|"]
        L += [f"| {f['stage']} | {catalog.label(f['id'])} | {f.get('scenario', '')} | {f['item']} | {f['check']} | "
              f"{f.get('actual', '')} | {f.get('expected', '')} |" for f in fails]
        L.append("")
    # the notes of stages P and G, as edakit check prints them – E lists its own in section 7, FILES.sheet and cost stand in 8
    infos = [r for r in rows if r["result"] == "info" and r["stage"] in ("P", "G")
             and r["id"] not in ("FILES.sheet", "cost")]
    from ..engines.coverage import coverage
    gaps = coverage(Design.from_config(cfg), prof, sim)     # the cables' currents from this run's simulation
    if gaps:
        L += ["Not checked for lack of data – no finding, nobody looked (`edakit check --coverage`):\n",
              *[f"- {g.line()}" for g in gaps], ""]
    if infos:
        L += ["Information (does not block the release, needs no acceptance):\n",
              *[f"- {catalog.label(r['id'])}: " + (f"{r['item']}: " if r["item"] and not str(r["check"]).startswith(
                  str(r["item"])) else "") + str(r["check"]) for r in infos], ""]
    L.append("## 3 Warnings\n")
    warns = [c for c in [*sim["checks"], *rows] if c["result"] == "warn"]
    gone = signoff.get("lapsed", [])

    def verdict(w):
        if a := accepted(w, signoff):
            return f"accepted by {a['by']} ({a['date']}): {a['reason']}"
        old = next((a for a in gone if fnmatch(key_of(w), a["match"])), None)
        if not old:
            return "**not accepted**"
        was = ", ".join(f"{d} = {n}" for d, n in old["parts"].items()) if isinstance(old["parts"], dict) else ""
        return (f"**not accepted** (lapsed: {old['lapsed']}; accepted by {old.get('by')} ({old.get('date')})"
                + (f" for {was}" if was else "") + ")")
    L += [f"- `{key_of(w)}` ({catalog.title(w['id']) or 'project check'}). Actual: {w.get('actual', '')}. "
          f"Expected: {w.get('expected', '')}. → " + verdict(w) for w in warns] or ["None."]
    if gone:
        L += ["\nAcceptances that lapsed – a part they name is another one now; judge again and update `parts`, or "
              "remove them:\n", *[f"- `{a['match']}`: {a['lapsed']}" for a in gone]]
    L.append("\n## 4 Accepted in the graph\n")
    L += [f"- {r['id']} {r['check']}  \n  reason: {r['reason']}" for r in rows if r["result"] == "waived"] + [
        f"- {c['id']} [{c['scenario']}] {c['item']}: {c['check']} {c.get('actual', '')}, expected {c.get('expected', '')}"
        f"  \n  reason: {c['reason']}" for c in sim["checks"] if c["result"] == "waived"] or ["None."]
    L.append("\n## 5 Open sign-offs\n")
    L += [f"- [ ] {r['check']}" for r in rows if r["result"] == "pending"] or ["None."]
    L.append("\n## 6 Manual checks\n")
    sheet, sheet_notes = datasheet_open(cfg)
    for phase, title in PHASES:
        items = [m for m in signoff.get("manual", []) if m.get("phase", "export") == phase]
        answered = [f"- [ ] {e['who']}: {t}" for e in sheet for t, w in e["open"] if w == phase]
        answered += requirements.acceptance(reqs) if phase == "acceptance" else []   # the requirements' steps
        answered += listed_checks(project_checks, phase)   # the project's checks of phase order and acceptance
        if items or answered:
            L.append(f"**{title}**\n")
            for m in items:
                by = (f" – {m['done_by']}, {m.get('date')}" + (f": {m['note']}" if m.get("note") else "")) if m.get("done_by") else ""
                if u := m.get("unchecked"):     # a run without stage F: the fab hash it is bound to is unknown here
                    by = f" – signed for fab {u['fab_sha256'][:12]}… by {u['by']}, {m.get('date')}: checked by stage F"
                L.append(f"- [{'x' if m.get('done_by') else ' '}] {m['id']} {m['text']}{signer(m)}{by}")
            L += answered
            L.append("")
    L += [f"- note: {n}" for n in notes + sheet_notes]
    L += datasheet_list(sheet)
    L += ["\n## 7 Simulation (stage E)\n", "| Scenario | Status | Nets | Supply current |", "|---|---|---|---|"]
    for s in sim["scenarios"]:   # a transient run (LIM.v): lowest … highest voltage, peak current
        hi = s.get("nets_max", {})
        nets = ", ".join(f"{n} {v:.3f}" + (f" … {hi[n]:.3f}" if n in hi else "") + " V" for n, v in s.get("nets", {}).items())
        src = ", ".join(f"{d} {'peak ' if s.get('transient') else ''}{i * 1e3:.0f} mA" for d, i in s.get("sources", {}).items())
        L.append(f"| {s['name']}{' (transient)' if s.get('transient') else ''} | {s['status']} | {nets} | {src} |")
    agg = defaultdict(Counter)
    for c in sim["checks"]:
        agg[(c["id"], re.sub(r" \(.*", "", c["check"]))][c["result"]] += 1
    L += ["\n| Check | Step | passed | failed | warning | info |", "|---|---|---:|---:|---:|---:|"]
    L += [f"| {cid} | {what} | {n['pass']} | {n['fail']} | {n['warn']} | {n['info']} |" for (cid, what), n in sorted(agg.items())]
    L.append("\nAll single values: `sim.json`.\n")
    shown = [r for r in rows if r["stage"] not in "PGE" or r["id"] in ("FILES.sheet", "cost")]
    L.append("## 8 Other stages\n")
    if shown:
        L += ["| Stage | Check | Item | Step | Actual | Expected | Result |", "|---|---|---|---|---|---|---|"]
        L += [f"| {r['stage']} | {r['id']} | {r['item']} | {r['check']} | {r.get('actual', '')} | {r.get('expected', '')} | "
              f"{RESULT.get(r['result'], r['result'])} |" for r in shown]
    else:
        L.append("Not run.")
    L.append("\n## 9 Release and manufacturing files\n")
    L.append(f"Decision of the gate: **{decision}**\n")
    if files and decision == "RELEASED":
        old = [run for run, _, d in runs(cfg) if d.get("superseded_by") == outdir.name]
        L.append("This run is the current release (`edakit release current`)"
                 + (f"; it supersedes {', '.join(old)}" if old else "") + ".\n")
    if files:
        L.append("Files for the manufacturer (SHA-256 in `fab/manifest.json`)"
                 + (":" if decision == "RELEASED" else " – **do not upload, state not released**:") + "\n")
        L += [f"- `{f}` `{h[:16]}…`" for f, h in files.items()]
    L.append("\n## 10 The rules behind the findings\n")
    explained = [i for i in dict.fromkeys(c["id"] for c in [*fails, *warns]) if catalog.code(i)]
    for i in explained:
        lines = catalog.explain(i, indent="")
        L += [f"**{lines[0]}**\n", *[f"- {line}" for line in lines[1:]], ""]
    if not explained:
        L.append("No code of the catalog failed or warned. Every code: `edakit rules`.")
    if cfg.requirements:    # [project] requirements: section 11, only then – every other section keeps its number
        L += ["\n## 11 Requirements\n",
              *requirements.section(reqs, signoff, [cfg.relative(p) for p in cfg.requirements])]
    (outdir / "protocol.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main(cfg, args):
    from .. import pcb as pcbmod
    from ..sim import copper
    from ..sim import run as simrun
    try:        # [project] requirements: a file named there that is missing or not valid stops the gate, before a run
        entries = requirements.load(cfg)
    except requirements.RequirementsError as e:
        print(f"edakit gate: {e}", file=sys.stderr)
        return 1
    head = header(cfg)
    outdir = cfg.reports / dt.datetime.fromisoformat(head["time"]).strftime("%Y%m%d-%H%M%S")
    outdir.mkdir(parents=True, exist_ok=True)
    design = Design.from_config(cfg)
    from .. import scripts     # the project's checks (8.1, 8.6): phase export a stage each, before S or after F
    project_checks = scripts.gate_checks(cfg)
    before = [c for c in project_checks if c.at == "before S"]
    after = [c for c in project_checks if c.at == "after F"]
    stages = STAGES[:3] + [(c.id, c.title, c.about) for c in before] + STAGES[3:] + [
        (c.id, c.title, c.about) for c in after]
    step = eda.Steps(2 + len(before) + (1 + len(cfg.made()) + len(after) if args.easyeda else 0))
    step("P/G parts and graph")
    rows, g_json = stage_graph(cfg, design)
    (outdir / "graph_checks.json").write_text(json.dumps(g_json, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    # project scripts (8.6), stage G: entries that do not resolve and an outdated input fail
    rows += scripts.gate_rows(cfg)
    rows += scripts.agent_rows(cfg)     # project agents (8.6), stage G: entries that do not resolve fail

    step("E simulation")
    sim_cfg, _ = simrun.load_sim_config(cfg)
    plugin = simrun.load_plugin(cfg.sim_plugin) if cfg.sim_plugin else None
    routing = copper.load_routing(cfg) if sim_cfg.get("copper") else None   # the routed copper, as it is now
    sim = simrun.run_all(Design.from_config(cfg), sim_cfg, plugin=plugin, routing=routing)
    simrun.write_net_currents(cfg, sim)
    rows += docs.stage_rows(cfg, design, sim)    # DOCS.quote: quoted values against this run's simulation
    (outdir / "sim.json").write_text(json.dumps(sim, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    stages_run = set(OFFLINE)
    if before:      # the checks before S, where [[release.stages]] always ran
        more, ran = stage_checks(cfg, outdir, before, step)
        rows += more
        stages_run |= ran
    files = {}
    if args.easyeda:
        step("S schematic against the graph")
        rows += stage_schematic(cfg, outdir)
        rows += stage_fab(cfg, outdir, step)
        stages_run |= set(WITH_EASYEDA)
        head.update(fab_hashes(cfg, outdir))

        if after:   # the checks after F: the run's manufacturing files are in fab/<board>/ of EDAKIT_RUN
            more, ran = stage_checks(cfg, outdir, after, step)
            rows += more
            stages_run |= ran
    signoff, notes = load_signoff(cfg, head, write=True)   # after stage F: sign-offs with scope 'fab' need its hash
    notes += pcbmod.move_notes(cfg)        # a footprint geometry still among the artifacts: how to move it
    reqs = requirements.evaluate(entries, [*sim["checks"], *rows], signoff, stages_run,
                                 project_checks)   # [] without the key; script: the checks of this run
    decision, reasons = decide(rows, sim["checks"], signoff, stages_run, stages, reqs)
    if args.easyeda:
        files = write_manifest(cfg, outdir, head, decision)
        (outdir / MAKERS).write_text(json.dumps(maker_findings(cfg, rows), indent=1, ensure_ascii=False) + "\n",
                                     encoding="utf-8")
    write_protocol(cfg, outdir, head, rows, sim, signoff, notes, decision, reasons, stages_run, stages, files, reqs,
                   project_checks)
    print(f"\n{decision}")
    for r in reasons:
        print(f"  - {r}")
    if cfg.requirements:
        print(requirements.summary(reqs))
    print(f"protocol: {outdir / 'protocol.md'}")
    return 0 if decision == "RELEASED" else 2
