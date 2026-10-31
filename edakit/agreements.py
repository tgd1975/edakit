"""The working agreements of handbook 11.4 at the start of every Claude Code session in an edakit project, and the
project's own scripts and agents.

    python3 edakit/agreements.py      SessionStart hook of the plugin (reads the hook JSON from stdin)

The agreements are how Claude works with edakit – read back before reporting, probes on a throwaway document, fix
your own choices. A new project's memory starts empty, so without this every project met each of them again the hard
way. The hook looks for the project's edakit.toml as edakit does (handbook 10.1): $EDAKIT_CONFIG, then the session's
directory (`cwd` of the hook JSON) and its parents. None: no output, the session is unchanged. Found, and
`[project] agreements` is not false: one line per agreement – its number and bold title, read from 11.4 itself so the
digest cannot drift from the handbook – and the path of the chapter, as additionalContext of the session.

After them, the project's own scripts and agents ([scripts.<name>] and [agents.<name>] of edakit.toml, handbook 8.6):
a head that says where each kind runs and points to edakit scripts, then one line per script – its name, kind and
about, a check also with its id and phase – and one per agent – its name, what it signs and whom it replaces, as edakit
scripts says it, and its about –, in the order of edakit.toml. So every session knows what the project registered and
why, also once the skill that ran a script is gone (concept project-scripts). [[release.stages]] and sim_plugin are not
listed: the gate and edakit sim run them, nobody starts them by hand. Without entries the agreements are all, exactly
as before.

No state – current, outdated, never run –: it is the hash of everything a script reads, from the board files and the
footprint geometry to the routing and a gate run's Gerber files, compared with hardware/scripts.lock, and computing it
needs edakit's own modules with their dependencies. A session must start at once, so the hook reads edakit.toml and
nothing else; edakit scripts gives the state, and the skills call it at their steps.

`[project] agreements = false` turns off the agreements, not the list: the list is the project's own data, registered
so that every session knows it – a project that keeps working agreements of its own still needs it. Without tomllib
(python3 older than 3.11) or in a file that does not parse the entries cannot be read; one line then says that the
project registers some and that edakit scripts lists them.

Last, where `edakit` is not on PATH, one line with the path of the plugin's bin/edakit – a session finds its command line
without searching for it.

Stdlib only and run with python3 directly, like `lock.py hook`: no uv start-up when a session starts. It never stops
a session: whatever goes wrong, it exits 0 (the reason on stderr).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

CHAPTER = Path(__file__).resolve().parents[1] / "handbook" / "11-working-with-claude.md"
SECTION = "11.4"
TABLE = re.compile(r"^[ \t]*\[[ \t]*(scripts|agents)[ \t]*\.", re.M)    # a [scripts.<name>] or [agents.<name>] table
SCRIPTS_HEAD = ("The project's scripts – [scripts.<name>] of edakit.toml (handbook 8.6): an input runs by itself "
                "before the step that reads it, a derive or easyeda script with `edakit run <name>` – an easyeda script "
                "on command only, under the EasyEDA claim –, a check in the gate or on the protocol's list of its "
                "phase. Their state – current, outdated, never run – and the order: `edakit scripts`")
AGENTS_HEAD = ("The project's agents – [agents.<name>] of edakit.toml (handbook 8.6): each reviews in its own session "
               "at its hook point, one with replaces in place of that edakit agent; its sign-off counts only when "
               "done_by names it. Who reviews where: `edakit scripts`")
UNREAD = ("The project registers scripts or agents – [scripts.<name>], [agents.<name>] of edakit.toml (handbook "
          "8.6): `edakit scripts` lists them with their state and who reviews where")


def find_project(cwd):
    """edakit.toml of the session: $EDAKIT_CONFIG, then cwd and its parents; None outside an edakit project."""
    env = os.environ.get("EDAKIT_CONFIG")
    if env and Path(env).is_file():
        return Path(env).resolve()
    here = Path(cwd).resolve()
    for d in (here, *here.parents):
        if (d / "edakit.toml").is_file():
            return d / "edakit.toml"
    return None


def read(path):
    """edakit.toml as the hook reads it: (wanted, entries). wanted is False only for `agreements = false` in
    [project]. entries are [(table, name, entry)] – each [scripts.<name>] and [agents.<name>] as written, in the file's
    order –, or None when the file has such tables and they cannot be read here: without tomllib, where the one key
    is read by hand, or in a file that does not parse – still an edakit project, edakit check reports what is wrong
    with it."""
    text = path.read_text(encoding="utf-8", errors="replace")
    unread = None if TABLE.search(text) else []
    try:
        import tomllib
    except ImportError:          # Python < 3.11 as python3: the one key by hand
        project = re.search(r"^\[project\][^\n]*\n(.*?)(?=^\[|\Z)", text, re.M | re.S)
        return not (project and re.search(r"^\s*agreements\s*=\s*false\b", project.group(1), re.M)), unread
    try:
        data = tomllib.loads(text)
    except ValueError:           # tomllib.TOMLDecodeError
        return True, unread
    return data.get("project", {}).get("agreements", True) is not False, [
        (table, name, entry) for table in ("scripts", "agents") if isinstance(data.get(table), dict)
        for name, entry in data[table].items() if isinstance(entry, dict)]     # not a table: edakit check reports it


def agreements(chapter=CHAPTER):
    """[(number, title)] – the numbered items of 11.4 with their bold titles."""
    text = chapter.read_text(encoding="utf-8")
    body = re.search(rf"^## {re.escape(SECTION)} .*?\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not body:
        raise ValueError(f"{chapter}: no section {SECTION}")
    return [(int(n), title.strip()) for n, title in re.findall(r"^(\d+)\. \*\*(.+?)\*\*", body.group(1), re.M)]


def digest(chapter=CHAPTER):
    head = (f"edakit project – the working agreements of handbook {SECTION} apply in this session; the reason and the "
            f"incident behind each are in {chapter}")
    return "\n".join([head] + [f"{n}. {title}" for n, title in agreements(chapter)])


def _said(value):
    """A field as one line of text; "" for none."""
    return " ".join(str(value).split()) if value not in (None, "") else ""


def _kind(e):
    """input; check K, phase export"""
    kind = _said(e.get("kind")) or "?"
    if kind == "check":
        kind = " ".join(filter(None, (kind, _said(e.get("id"))))) + (f", phase {_said(e['phase'])}"
                                                                      if e.get("phase") else "")
    return kind


def _signs(a):
    """What an agent signs, as edakit scripts says it (scripts._agent_said): signs M-5 in place of pcb-reviewer, phase
    export; signs M-7 on the layout hash, phase export; after pcb-pruefer."""
    how = (f" in place of {a['replaces']}" if a.get("replaces") else
           f" on the {a['scope']} hash" if a.get("scope") else "")
    after = a.get("after") if isinstance(a.get("after"), list) else []
    return f"signs {a.get('signs') or '?'}{how}, phase {a.get('phase') or '?'}" + (
        f"; after {', '.join(map(str, after))}" if after else "")


def registered(entries):
    """The lines of the project's scripts and agents: per table that has entries its head and one line each – none
    without entries; one line that edakit scripts lists them when they cannot be read here (None)."""
    if entries is None:
        return [UNREAD]
    lines = []
    for table, head, what in (("scripts", SCRIPTS_HEAD, _kind), ("agents", AGENTS_HEAD, _signs)):
        rows = [(name, e) for t, name, e in entries if t == table]
        if rows:
            lines.append(head)
        for name, e in rows:
            about = _said(e.get("about"))
            lines.append(f"- {name} ({what(e)})" + (f" – {about}" if about else ""))
    return lines


def command():
    """The line that says where edakit is when it is not on PATH: the plugin's bin/edakit."""
    import shutil
    if shutil.which("edakit"):
        return []
    return [f"The edakit command line is {Path(__file__).resolve().parents[1] / 'bin' / 'edakit'} – it is not on PATH."]


def hook(data):
    """The hook's output for the hook JSON `data`, or None for no output."""
    path = find_project(data.get("cwd") or os.getcwd())
    if path is None:
        return None
    wanted, entries = read(path)
    lines = ([digest()] if wanted else []) + registered(entries) + command()
    if not lines:
        return None
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n".join(lines)}}


def main():
    try:
        try:
            data = json.load(sys.stdin)
        except ValueError:
            data = {}
        out = hook(data if isinstance(data, dict) else {})
        if out:
            print(json.dumps(out, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 – a session must start whatever happens here
        print(f"edakit agreements: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
