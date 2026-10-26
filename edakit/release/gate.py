"""Release gate: runs every stage and writes a test protocol. Only a run that says RELEASED may go to the manufacturer.

    edakit gate             P (parts), G (graph), E (simulation) and the project's own stages; offline, seconds
    edakit gate --easyeda   plus S (schematic), L (board), F (manufacturing files); EasyEDA with the bridge, minutes

Result: <reports>/<YYYYMMDD-hhmmss>/
    protocol.md            readable protocol: header with hashes, stages, findings with actual and expected value,
                           warnings and who accepted them, waivers, open sign-offs, manual checks, simulation table,
                           and the rule, reason and fix of every check that failed or warned (rules.json)
    graph_checks.json, sim.json, schematic_<board>.json   raw results
    fab/<board>/           Gerber ZIP, BOM and CPL in JLCPCB format plus raw data (stages L, F)
    fab/manifest.json      SHA-256 of every file to upload, the hashes of the checked state, the decision

RELEASED only if
  - every stage ran and no check failed,
  - every warning is accepted in the sign-off file (only a human accepts warnings – it is a decision),
  - every part is verified and every manual check of phase 'export' is signed – the regulatory review M-6 also when
    the sign-off file does not list it,
  - all of that for exactly this state: sign-offs count only for the hash of their scope – 'circuit' (graph with its
    check settings, parts database, simulation config) or 'layout' (the board files, further layout_files of
    [release], the footprint geometry). An accepted
    warning with scope 'decision' counts regardless of the hash and refers to a numbered decision in the docs.
Exit code: 0 = released, 2 = not released, 1 = tool error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import hashlib
import json
import platform
import re
import subprocess
from collections import Counter, defaultdict
from fnmatch import fnmatch
from pathlib import Path

from .. import checks, rules
from ..design import Design

STAGES = [
    ("P", "Parts", "parts database complete, graph pins = parts database, parts verified"),
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
SCOPE_KEY = {"circuit": "state_sha256", "layout": "layout_sha256"}
REQUIRED = {   # manual checks every release needs, also when an older sign-off file does not list them
    "M-6": {"phase": "export", "scope": "circuit",
            "text": "Regulatory review: circuit and parts against EU law for the stated purpose (RoHS, REACH, radio, "
                    "batteries, product safety) – the agent regulatory-reviewer in its own session"},
}
UPLOAD = ["gerber_{b}.zip", "bom_{b}.csv", "cpl_{b}.csv"]
RESULT = {"pass": "passed", "fail": "FAILED", "warn": "warning", "info": "information", "advisory": "advisory",
          "waived": "waived", "pending": "open"}


def sh(cwd, *cmd, timeout=30):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def file_hash(root, files):
    h = hashlib.sha256()
    for f in files:
        h.update(str(Path(f).relative_to(root) if Path(f).is_relative_to(root) else f).encode() + b"\0"
                 + (Path(f).read_bytes() if Path(f).exists() else b"<missing>"))
    return h.hexdigest()


def state_files(cfg):
    files = [cfg.graph, cfg.sim_config, *sorted(cfg.parts.glob("*.json"))]
    if cfg.sim_plugin:
        files.append(cfg.sim_plugin)
    return files + [cfg.resolve(f) for f in cfg.release.get("state_files", [])]


def layout_files(cfg):
    files = [cfg.resolve(b.file) for b in cfg.boards.values()]
    files += [cfg.resolve(f) for f in cfg.release.get("layout_files", [])]
    return files + [cfg.artifacts / f"pcb_geometry_{b}.json" for b in cfg.boards]


def header(cfg):
    from .. import __version__
    design = Design.from_config(cfg)
    mcp = re.search(r"EASYEDA_MCP_VERSION:-([\d.]+)",
                    (Path(__file__).resolve().parents[1] / "easyeda" / "mcp-server.sh").read_text())
    return {
        "graph_sha256": hashlib.sha256(cfg.graph.read_bytes()).hexdigest(),
        "state_sha256": file_hash(cfg.root, state_files(cfg)),
        "layout_sha256": file_hash(cfg.root, layout_files(cfg)),
        "graph_version": design.version, "graph_date": design.graph.get("date"),
        "git_commit": sh(cfg.root, "git", "rev-parse", "--short", "HEAD"),
        "git_dirty": bool(sh(cfg.root, "git", "status", "--porcelain")),
        "time": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "tester": sh(cfg.root, "git", "config", "user.name") or getpass.getuser(),
        "tools": {"python": platform.python_version(), "edakit": __version__,
                  "ngspice": (re.findall(r"ngspice-[\d.]+", sh(cfg.root, "ngspice", "-v")) or ["ngspice ?"])[0],
                  "easyeda-mcp-pro": mcp.group(1) if mcp else "?"},
    }


def load_signoff(cfg, head):
    """Sign-offs and accepted warnings that count for the current hash of their scope. A required manual check the
    file does not list is added as open."""
    path = cfg.signoff
    if not path.exists():
        return {"manual": [], "accepted_warnings": []}, [f"{path.name} missing – no sign-offs"]
    s = json.loads(path.read_text(encoding="utf-8"))
    notes, valid = [], {"decision": True}
    for scope, key in SCOPE_KEY.items():
        valid[scope] = s.get(key) == head[key]
        if not valid[scope]:
            notes.append(f"{path.name}: sign-offs with scope '{scope}' belong to another state ({key}) and do not count")
    manual = [m if valid.get(m.get("scope", "circuit")) else {**m, "done_by": None} for m in s.get("manual", [])]
    for sid, m in REQUIRED.items():
        if sid not in {x.get("id") for x in manual}:
            manual.append({"id": sid, **m, "done_by": None})
            notes.append(f"{path.name}: {sid} is missing – added as open, every release needs it")
    warns = [a for a in s.get("accepted_warnings", []) if valid.get(a.get("scope", "circuit"))]
    return {**s, "manual": manual, "accepted_warnings": warns}, notes


def key_of(item):
    return " ".join(str(item.get(k, "")) for k in ("id", "scenario", "item", "check") if item.get(k, "") != "")


def accepted(item, signoff):
    return next((a for a in signoff.get("accepted_warnings", []) if fnmatch(key_of(item), a["match"])), None)


def stage_graph(cfg, design):
    rep = checks.run(design, cfg)
    rows = []
    stage_of = lambda c: "P" if c in ("P-1", "P-3", "G-9") else "G"  # noqa: E731
    for c, m in rep.errors:
        rows.append({"stage": stage_of(c), "id": c, "item": "", "check": m, "result": "fail"})
    for c, m, r in rep.waived:
        rows.append({"stage": stage_of(c), "id": c, "item": "", "check": m, "result": "waived", "reason": r})
    for c, m in rep.pending:
        rows.append({"stage": stage_of(c), "id": c, "item": "", "check": m, "result": "pending"})
    for c, m in rep.warnings:
        rows.append({"stage": stage_of(c), "id": c, "item": "", "check": m, "result": "warn"})
    for c, m in rep.notes:
        rows.append({"stage": stage_of(c), "id": c, "item": "", "check": m, "result": "info"})
    hit = {r["id"] for r in rows if r["result"] in ("fail", "pending")}
    rows += [{"stage": stage_of(c), "id": c, "item": "", "check": rules.title(c), "result": "pass"}
             for c in checks.EXECUTED if c not in hit]
    return rows, rep.to_dict()


def stage_custom(cfg, outdir):
    """[[release.stages]]: id, name, cmd (list), advisory. The command's last stdout line may be a JSON list of
    [id, check, actual, expected, ok]; otherwise only its exit code counts."""
    rows, run = [], set()
    for st in cfg.release.get("stages", []):
        run.add(st["id"])
        log = outdir / f"stage_{st['id']}.txt"
        try:
            res = subprocess.run(st["cmd"], capture_output=True, text=True, cwd=cfg.root, timeout=st.get("timeout", 900))
            log.write_text(res.stdout + res.stderr, encoding="utf-8")
        except (OSError, subprocess.TimeoutExpired) as e:
            rows.append({"stage": st["id"], "id": st["id"], "item": st["name"], "check": f"not runnable: {e}",
                         "result": "fail"})
            continue
        bad = "advisory" if st.get("advisory") else "fail"
        try:
            items = json.loads(res.stdout.strip().splitlines()[-1])
            rows += [{"stage": st["id"], "id": i[0], "item": st["name"], "check": i[1], "actual": i[2], "expected": i[3],
                      "result": "pass" if i[4] else bad} for i in items]
        except (IndexError, json.JSONDecodeError, TypeError):
            rows.append({"stage": st["id"], "id": st["id"], "item": st["name"], "check": " ".join(st["cmd"]),
                         "actual": f"exit {res.returncode}", "expected": "exit 0",
                         "result": "pass" if res.returncode == 0 else bad})
    return rows, run


def stage_schematic(cfg, outdir):
    from .. import schematic
    rows = []
    for board in cfg.boards.values():
        out = outdir / f"schematic_{board.name}.json"
        args = argparse.Namespace(board=board.name, schematic=None, no_pins=False, json=str(out), verbose=False, wait=90)
        code = schematic.check(cfg, args)
        if code == 1:
            rows.append({"stage": "S", "id": "S-2", "item": board.template, "check": "comparison not runnable",
                         "result": "fail"})
            continue
        found = json.loads(out.read_text()) if out.exists() else {}
        for section, msgs in found.items():
            rows += [{"stage": "S", "id": "S-2", "item": f"{board.template}: {section}", "check": m, "result": "fail"}
                     for m in msgs]
        if code == 0:
            rows.append({"stage": "S", "id": "S-2", "item": board.template, "check": "schematic = graph", "result": "pass"})
    return rows


def stage_fab(cfg, outdir):
    from . import fab
    rows = []
    d = outdir / "fab"
    d.mkdir(exist_ok=True)
    for board in cfg.boards.values():
        print(f"    {board.name} …", flush=True)
        try:
            rows += fab.run(cfg, board, d)
        except (SystemExit, Exception) as e:  # one board failing must not hide the others
            rows.append({"stage": "L", "id": "L", "item": board.name, "check": f"fab stage not runnable: {e}",
                         "result": "fail"})
        lost = [p.format(b=board.name) for p in UPLOAD if not (d / board.name / p.format(b=board.name)).exists()]
        rows.append({"stage": "F", "id": "F-4", "item": board.name, "check": "manufacturing files of this run complete "
                     "(Gerber ZIP, BOM, CPL), checksums in the manifest", "actual": ", ".join(lost) or "complete",
                     "expected": "complete", "result": "fail" if lost else "pass"})
    return rows


def decide(rows, sim_checks, signoff, stages_run, stages):
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
    open_manual = [m for m in signoff.get("manual", []) if m.get("phase", "export") == "export" and not m.get("done_by")]
    if open_manual:
        reasons.append(f"{len(open_manual)} manual check(s) before the export open: "
                       + ", ".join(m["id"] for m in open_manual) + " (section 6)")
    missing = [f"{sid} ({name})" for sid, name, _ in stages if sid not in stages_run]
    if missing:
        reasons.append("stages not run: " + ", ".join(missing))
    return ("RELEASED" if not reasons else "NOT RELEASED"), reasons


def write_manifest(cfg, outdir, head, decision):
    fab = outdir / "fab"
    files = {}
    for b in cfg.boards:
        for pattern in UPLOAD:
            f = fab / b / pattern.format(b=b)
            if f.exists():
                files[str(f.relative_to(outdir))] = hashlib.sha256(f.read_bytes()).hexdigest()
    manifest = {"released": decision == "RELEASED", "decision": decision, "time": head["time"],
                "git": head["git_commit"] + (" + uncommitted changes" if head["git_dirty"] else ""),
                "graph_sha256": head["graph_sha256"], "state_sha256": head["state_sha256"],
                "layout_sha256": head["layout_sha256"], "files": files}
    fab.mkdir(exist_ok=True)
    (fab / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return files


def write_protocol(cfg, outdir, head, rows, sim, signoff, notes, decision, reasons, stages_run, stages, files):
    by_stage = defaultdict(Counter)
    for r in rows:
        by_stage[r["stage"]][r["result"]] += 1
    for c in sim["checks"]:
        by_stage["E"][c["result"]] += 1
    L = [f"# Test protocol – release check {cfg.project}\n", "| | |\n|---|---|",
         f"| Date | {head['time']} |", f"| Run by | {head['tester']} |",
         f"| Object | `{cfg.graph.relative_to(cfg.root)}` v{head['graph_version']} ({head['graph_date']}), boards "
         f"{', '.join(cfg.boards)} in EasyEDA project {cfg.project} |",
         f"| SHA-256 graph | `{head['graph_sha256']}` |",
         f"| SHA-256 circuit | `{head['state_sha256']}` (graph, parts database, simulation config) |",
         f"| SHA-256 layout | `{head['layout_sha256']}` (layout files, footprint geometry) |",
         f"| Git | `{head['git_commit']}`{' + uncommitted changes' if head['git_dirty'] else ''} |",
         f"| Tools | Python {head['tools']['python']}, edakit {head['tools']['edakit']}, {head['tools']['ngspice']}, "
         f"easyeda-mcp-pro {head['tools']['easyeda-mcp-pro']} |",
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
    L += ["\nIn P (parts) and G (graph) every rule without a finding counts once as passed; executed: "
          + ", ".join(rules.label(k) for k in checks.EXECUTED) + ".\n", "## 2 Findings\n"]
    fails = [r for r in rows if r["result"] == "fail"] + [c | {"stage": "E"} for c in sim["checks"] if c["result"] == "fail"]
    advis = [r for r in rows if r["result"] == "advisory"]
    if advis:
        L += ["Advisories (do not block the release):\n",
              *[f"- {r['id']} {r['check']}: {r.get('actual', '')} (expected {r.get('expected', '')})" for r in advis], ""]
    if not fails:
        L.append("No check failed.\n")
    else:
        L += ["| Stage | Check | Scenario | Item | Step | Actual | Expected |", "|---|---|---|---|---|---|---|"]
        L += [f"| {f['stage']} | {rules.label(f['id'])} | {f.get('scenario', '')} | {f['item']} | {f['check']} | "
              f"{f.get('actual', '')} | {f.get('expected', '')} |" for f in fails]
        L.append("")
    L.append("## 3 Warnings\n")
    warns = [c for c in [*sim["checks"], *rows] if c["result"] == "warn"]
    L += [f"- `{key_of(w)}` ({rules.title(w['id']) or 'project check'}). Actual: {w.get('actual', '')}. "
          f"Expected: {w.get('expected', '')}. → "
          + (f"accepted by {a['by']} ({a['date']}): {a['reason']}" if (a := accepted(w, signoff)) else "**not accepted**")
          for w in warns] or ["None."]
    L.append("\n## 4 Waivers in the graph\n")
    L += [f"- {r['id']} {r['check']}  \n  reason: {r['reason']}" for r in rows if r["result"] == "waived"] or ["None."]
    L.append("\n## 5 Open sign-offs\n")
    L += [f"- [ ] {r['check']}" for r in rows if r["result"] == "pending"] or ["None."]
    L.append("\n## 6 Manual checks\n")
    for phase, title in PHASES:
        items = [m for m in signoff.get("manual", []) if m.get("phase", "export") == phase]
        if items:
            L.append(f"**{title}**\n")
            for m in items:
                by = (f" – {m['done_by']}, {m.get('date')}" + (f": {m['note']}" if m.get("note") else "")) if m.get("done_by") else ""
                L.append(f"- [{'x' if m.get('done_by') else ' '}] {m['id']} {m['text']}{by}")
            L.append("")
    L += [f"- note: {n}" for n in notes]
    L += ["\n## 7 Simulation (stage E)\n", "| Scenario | Status | Nets | Supply current |", "|---|---|---|---|"]
    for s in sim["scenarios"]:
        nets = ", ".join(f"{n} {v:.3f} V" for n, v in s.get("nets", {}).items())
        src = ", ".join(f"{d} {i * 1e3:.0f} mA" for d, i in s.get("sources", {}).items())
        L.append(f"| {s['name']} | {s['status']} | {nets} | {src} |")
    agg = defaultdict(Counter)
    for c in sim["checks"]:
        agg[(c["id"], re.sub(r" \(.*", "", c["check"]))][c["result"]] += 1
    L += ["\n| Check | Step | passed | failed | warning | info |", "|---|---|---:|---:|---:|---:|"]
    L += [f"| {cid} | {what} | {n['pass']} | {n['fail']} | {n['warn']} | {n['info']} |" for (cid, what), n in sorted(agg.items())]
    L.append("\nAll single values: `sim.json`.\n")
    shown = [r for r in rows if r["stage"] not in "PGE" or r["id"] == "P-2"]
    L.append("## 8 Other stages\n")
    if shown:
        L += ["| Stage | Check | Item | Step | Actual | Expected | Result |", "|---|---|---|---|---|---|---|"]
        L += [f"| {r['stage']} | {r['id']} | {r['item']} | {r['check']} | {r.get('actual', '')} | {r.get('expected', '')} | "
              f"{RESULT.get(r['result'], r['result'])} |" for r in shown]
    else:
        L.append("Not run.")
    L.append("\n## 9 Release and manufacturing files\n")
    L.append(f"Decision of the gate: **{decision}**\n")
    if files:
        L.append("Files for the manufacturer (SHA-256 in `fab/manifest.json`)"
                 + (":" if decision == "RELEASED" else " – **do not upload, state not released**:") + "\n")
        L += [f"- `{f}` `{h[:16]}…`" for f, h in files.items()]
    L.append("\n## 10 The rules behind the findings\n")
    explained = [i for i in dict.fromkeys(c["id"] for c in [*fails, *warns]) if rules.entry(i)]
    for i in explained:
        lines = rules.explain(i, indent="")
        L += [f"**{lines[0]}**\n", *[f"- {line}" for line in lines[1:]], ""]
    if not explained:
        L.append("No check of the catalog failed or warned. Every check: `edakit rules`.")
    (outdir / "protocol.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main(cfg, args):
    from ..sim import run as simrun
    head = header(cfg)
    outdir = cfg.reports / dt.datetime.fromisoformat(head["time"]).strftime("%Y%m%d-%H%M%S")
    outdir.mkdir(parents=True, exist_ok=True)
    signoff, notes = load_signoff(cfg, head)
    design = Design.from_config(cfg)
    custom = [(st["id"], st["name"], st.get("about", " ".join(st["cmd"]))) for st in cfg.release.get("stages", [])]
    stages = STAGES[:3] + custom + STAGES[3:]
    print("[P/G] parts and graph …", flush=True)
    rows, g_json = stage_graph(cfg, design)
    (outdir / "graph_checks.json").write_text(json.dumps(g_json, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("[E] simulation …", flush=True)
    sim_cfg, _ = simrun.load_sim_config(cfg)
    plugin = simrun.load_plugin(cfg.sim_plugin) if cfg.sim_plugin else None
    sim = simrun.run_all(Design.from_config(cfg), sim_cfg, plugin=plugin)
    simrun.write_net_currents(cfg, sim)
    (outdir / "sim.json").write_text(json.dumps(sim, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    stages_run = set(OFFLINE)
    if custom:
        print("[project stages] …", flush=True)
        more, ran = stage_custom(cfg, outdir)
        rows += more
        stages_run |= ran
    files = {}
    if args.easyeda:
        print("[S] schematic against the graph …", flush=True)
        rows += stage_schematic(cfg, outdir)
        print("[L/F] board and manufacturing files …", flush=True)
        rows += stage_fab(cfg, outdir)
        stages_run |= set(WITH_EASYEDA)
    decision, reasons = decide(rows, sim["checks"], signoff, stages_run, stages)
    if args.easyeda:
        files = write_manifest(cfg, outdir, head, decision)
    write_protocol(cfg, outdir, head, rows, sim, signoff, notes, decision, reasons, stages_run, stages, files)
    print(f"\n{decision}")
    for r in reasons:
        print(f"  - {r}")
    print(f"protocol: {outdir / 'protocol.md'}")
    return 0 if decision == "RELEASED" else 2
