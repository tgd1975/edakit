"""The working agreements of handbook 11.4 at the start of every Claude Code session in an edakit project.

    python3 edakit/agreements.py      SessionStart hook of the plugin (reads the hook JSON from stdin)

The agreements are how Claude works with edakit – read back before reporting, probes on a throwaway document, fix
your own choices. A new project's memory starts empty, so without this every project met each of them again the hard
way. The hook looks for the project's edakit.toml as edakit does (handbook 10.1): $EDAKIT_CONFIG, then the session's
directory (`cwd` of the hook JSON) and its parents. None: no output, the session is unchanged. Found, and
`[project] agreements` is not false: one line per agreement – its number and bold title, read from 11.4 itself so the
digest cannot drift from the handbook – and the path of the chapter, as additionalContext of the session.

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


def wanted(path):
    """False only for `agreements = false` in [project]. A file that does not parse is still an edakit project –
    edakit check reports what is wrong with it."""
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        import tomllib
        return tomllib.loads(text).get("project", {}).get("agreements", True) is not False
    except ImportError:          # Python < 3.11 as python3: the one key by hand
        project = re.search(r"^\[project\][^\n]*\n(.*?)(?=^\[|\Z)", text, re.M | re.S)
        return not (project and re.search(r"^\s*agreements\s*=\s*false\b", project.group(1), re.M))
    except ValueError:           # tomllib.TOMLDecodeError
        return True


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


def hook(data):
    """The hook's output for the hook JSON `data`, or None for no output."""
    path = find_project(data.get("cwd") or os.getcwd())
    if path is None or not wanted(path):
        return None
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": digest()}}


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
