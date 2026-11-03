"""`edakit hook`: the project's pre-commit hook (handbook 2.7). edakit owns one block of it – `install` writes and
renews that block and sets core.hooksPath, the project's own steps around it stay –, `check` says what is missing for
the session start, and `run`, which the block calls, runs the steps of every configuration whose files are staged:
`edakit check`, `edakit sim`, with a TOML or a .circuit graph `edakit graph json --check`, with [firmware] `edakit firmware --check`,
with [docs] `edakit docs`. A failing step blocks the commit; never bypass it with --no-verify.

The block finds edakit itself: $EDAKIT, else `edakit` on the PATH (inside Claude Code), else the plugin installation in
effect for the repository (a commit by hand) – so no project needs a script of its own for it.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

FORMAT = 1
BEGIN = f"# >>> edakit hook {FORMAT} >>>"
END = "# <<< edakit hook <<<"
DEFAULT_DIR = ".githooks"
SHEBANG = "#!/usr/bin/env bash"

# The plugin installation in effect for the repository: local or project scope of this folder, else the user scope
# (edakit/update.py, installed) – read by the block in plain Python, edakit may not be importable there.
FIND = r"""import json, os, sys
base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
try:
    d = json.load(open(os.path.join(base, "plugins", "installed_plugins.json")))
except (OSError, ValueError):
    sys.exit()
rank = {"local": 0, "project": 1, "user": 2, "managed": 3}
mine = [e for n, es in d.get("plugins", d).items() if n.startswith("edakit@") and isinstance(es, list) for e in es
        if e.get("projectPath") in (None, sys.argv[1])]
if mine:
    print(os.path.join(min(mine, key=lambda e: rank.get(e.get("scope"), 9)).get("installPath", ""), "bin", "edakit"))"""

assert "'" not in FIND                 # it goes into the block between single quotes

BLOCK = f"""{BEGIN}
# Written by `edakit hook install`, renewed by it – the project's own steps go outside this block (handbook 2.7).
# edakit check, sim and the other steps of each configuration whose files are staged; a failure blocks the commit.
cd "$(git rev-parse --show-toplevel)" || exit 1
ek=${{EDAKIT:-}}
[ -n "$ek" ] || ek=$(command -v edakit 2>/dev/null || true)
[ -n "$ek" ] || ek=$(python3 -c '{FIND}' "$PWD" 2>/dev/null || true)
if [ -z "$ek" ] || [ ! -x "$ek" ]; then
  echo "pre-commit: edakit not found – set EDAKIT=/path/to/edakit, put it on the PATH or install the Claude Code plugin"
  exit 1
fi
# through cat: uv from snap prints nothing and exits 120 when its output goes into a file
# – and safe under the project's set -euo pipefail
rcf=$(mktemp); {{ "$ek" hook run 2>&1 && echo 0 >"$rcf" || echo $? >"$rcf"; }} | cat; rc=$(cat "$rcf"); rm -f "$rcf"
[ "$rc" = 0 ] || exit "$rc"
{END}
"""


def _git(root, *args):
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def toplevel(start):
    top = _git(start, "rev-parse", "--show-toplevel")
    return Path(top) if top else None


def hooks_dir(root):
    """(directory, active): core.hooksPath when set, else .githooks – active when git runs hooks from there."""
    set_to = _git(root, "config", "core.hooksPath")
    if set_to:
        return Path(root) / set_to, True
    return Path(root) / DEFAULT_DIR, False


def _block(text):
    m = re.search(rf"^{re.escape(BEGIN.rsplit(' ', 2)[0])} \d+ >>>\n.*?^{re.escape(END)}\n?", text, re.M | re.S)
    return m


# --- check and install --------------------------------------------------------------------------------------------

def check(root):
    """[{what, text}] of what keeps the hook from running edakit's steps: missing, no block, outdated, inactive."""
    folder, active = hooks_dir(root)
    f = folder / "pre-commit"
    rel = os.path.relpath(f, root)
    if not f.is_file():
        return [{"what": "missing", "text": f"{rel} is missing"}]
    text = f.read_text(encoding="utf-8", errors="replace")
    m = _block(text)
    if not m:
        return [{"what": "no block", "text": f"{rel} has no edakit block"}]
    out = []
    if m.group(0).rstrip("\n") != BLOCK.rstrip("\n"):
        out.append({"what": "outdated", "text": f"{rel}: edakit's block is of an older edakit"})
    if not active:
        out.append({"what": "inactive", "text": f"git does not run {rel} (core.hooksPath is not set)"})
    elif not os.access(f, os.X_OK):
        out.append({"what": "inactive", "text": f"{rel} is not executable"})
    return out


# a call of edakit – `edakit sim`, `hardware/edakit.sh check`, `$EK check` is not seen –, not a message or a log name
EDAKIT_CALL = re.compile(r"(?:^|[\s;&|(])(?:\S*/)?edakit(?:\.sh)?\s+(?:check|sim|graph\s+json|firmware|docs)\b")
SAYS = re.compile(r"^\s*(?:echo|printf)\b")


FAILED = "failed: "        # the start of a line of install() for a step that could not be done


def install(root):
    """Write or renew edakit's block, make the hook executable and set core.hooksPath -> [what was done]. A step the
    session may not do – Claude Code guards git's configuration, a sandbox refuses a write – is a line that starts with
    FAILED and names the command to run by hand; the steps after it are not tried."""
    root = Path(root)
    folder, active = hooks_dir(root)
    f = folder / "pre-commit"
    rel = os.path.relpath(f, root)
    done, outside = [], []
    if f.is_file():
        text = f.read_text(encoding="utf-8")
        m = _block(text)
        if m and m.group(0).rstrip("\n") == BLOCK.rstrip("\n"):
            done.append("edakit's block is current")
            new = text
        elif m:
            new = text[:m.start()] + BLOCK + text[m.end():]
            done.append(f"{rel}: edakit's block renewed")
        else:
            lines = text.splitlines(keepends=True)
            head = 0
            while head < len(lines) and (lines[head].startswith("#") or not lines[head].strip()):
                head += 1                                  # after the shebang and the header comment
            new = "".join(lines[:head]) + BLOCK + "".join(lines[head:])
            done.append(f"{rel}: edakit's block added after the header")
        rest = new.replace(BLOCK, "")
        for i, line in enumerate(rest.splitlines(), 1):
            if not line.lstrip().startswith("#") and not SAYS.match(line) and EDAKIT_CALL.search(line):
                outside.append(f"{rel} line {i} outside the block runs edakit itself – `{line.strip()[:70]}`: the "
                               "block does that now, take the line out")
    else:
        new = f"{SHEBANG}\n# Pre-commit hook (edakit handbook 2.7). Never bypass it with --no-verify.\n{BLOCK}"
        done.append(f"{rel} written")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        if not f.is_file() or new != f.read_text(encoding="utf-8"):
            f.write_text(new, encoding="utf-8")
        mode = f.stat().st_mode
        if not mode & stat.S_IXUSR:
            f.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            done.append(f"{rel} made executable")
    except OSError as e:
        return [f"{FAILED}{rel} not written ({e.strerror or e}) – run `edakit hook install` in a terminal of your own"]
    done += outside
    if not active:
        hooks = os.path.relpath(folder, root)
        if _git(root, "config", "core.hooksPath", hooks) is None:
            done.append(f"{FAILED}git config core.hooksPath {hooks} refused – run it in a terminal of your own")
        else:
            done.append(f"git config core.hooksPath {hooks}")
    return done


# --- run ----------------------------------------------------------------------------------------------------------

def configs(root):
    """[{path, dir, inputs, generated_graph, firmware, docs}] of the repository's edakit.toml files, paths relative."""
    from .config import ConfigError, load
    root = Path(root)
    listed = _git(root, "ls-files", "--cached", "--others", "--exclude-standard", "*edakit.toml", "edakit.toml")
    out = []
    for name in sorted(set((listed or "").splitlines())):
        if Path(name).name != "edakit.toml":
            continue
        try:
            cfg = load(root / name)
        except ConfigError:                            # edakit check names what is wrong – it runs all the same
            d = str(Path(name).parent)
            out.append({"path": name, "dir": "" if d == "." else d, "inputs": [], "generated_graph": False,
                        "firmware": False, "docs": False})
            continue
        inputs = [cfg.graph, cfg.parts, cfg.sim_config, *cfg.requirements, *cfg.docs]
        inputs += [cfg.resolve(f) for f in _pin_tables(cfg.graph)]
        rel = []
        for p in inputs:
            p = cfg.resolve(p)
            if p.is_relative_to(root):
                rel.append(str(p.relative_to(root)))
        d = str(Path(name).parent)
        out.append({"path": name, "dir": "" if d == "." else d, "inputs": rel,
                    "generated_graph": cfg.graph.suffix in (".toml", ".circuit"),
                    "firmware": cfg.firmware is not None, "docs": bool(cfg.docs)})
    return out


def _pin_tables(graph):
    """The files of doc_pin_table in a graph – under locks, or checks in the older form; {file: …} or a path."""
    import tomllib
    try:
        if graph.suffix == ".circuit":                 # compiled, as every reader of the graph reads it
            from .config import ConfigError
            from .design import load_graph
            try:
                data = load_graph(graph)
            except ConfigError:
                return []
        else:
            text = graph.read_text(encoding="utf-8")
            data = tomllib.loads(text) if graph.suffix == ".toml" else json.loads(text)
    except (OSError, ValueError):
        return []
    data = data.get("graph", data) if isinstance(data, dict) else {}    # as design.py reads it
    out = []
    for where in ("locks", "checks"):
        t = (data.get(where) or {}).get("doc_pin_table") if isinstance(data.get(where), dict) else None
        f = t.get("file") if isinstance(t, dict) else t
        if isinstance(f, str) and f:
            out.append(f.split("#")[0])
    return out


def _touches(path, c):
    prefix = f"{c['dir']}/" if c["dir"] else ""
    if path == f"{prefix}edakit.toml" or path.startswith(f"{prefix}hardware/") or path.startswith("hardware/"):
        return True
    return any(path == i or path.startswith(i.rstrip("/") + "/") for i in c["inputs"])


def plan(staged, cfgs):
    """[(config, [steps])] for the staged paths: a configuration runs when its edakit.toml, its hardware/, the main
    project's hardware/ (every variant reads it) or a file it names is staged."""
    out = []
    for c in cfgs:
        if not any(_touches(p, c) for p in staged):
            continue
        steps = [["check"], ["sim"]]
        if c["generated_graph"]:
            steps.append(["graph", "json", "--check"])
        if c["firmware"]:
            steps.append(["firmware", "--check"])
        if c["docs"]:
            steps.append(["docs"])
        out.append((c["path"], steps))
    return out


def _step(cfg, step):
    r = subprocess.run([sys.executable, "-m", "edakit.cli", *step, "--config", cfg], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)


def run(root):
    root = Path(root)
    staged = (_git(root, "diff", "--cached", "--name-only") or "").splitlines()
    todo = plan(staged, configs(root))
    fail = 0
    for cfg, steps in todo:
        name = "main" if Path(cfg).parent == Path(".") else Path(cfg).parent.name
        for step in steps:
            label = f"{name}: edakit {' '.join(step)}"
            rc, out = _step(cfg, step)
            if rc:
                print(f"pre-commit: {label} failed (exit {rc})")
                print("\n".join(out.rstrip().splitlines()[-25:]))
                fail = 1
            else:
                print(f"pre-commit: {label} ok")
    if fail:
        print("pre-commit: commit blocked – fix the findings (edakit explain <code>), stage again")
    return 2 if fail else 0


def main(args):
    root = toplevel(Path.cwd())
    if root is None:
        print("edakit hook: not in a git repository", file=sys.stderr)
        return 1
    if args.action == "run":
        return run(root)
    if args.action == "install":
        lines = install(root)
        for line in lines:
            print(line)
        return 1 if any(line.startswith(FAILED) for line in lines) else 0
    problems = check(root)
    for p in problems:
        print(f"{p['what']}: {p['text']}")
    if problems:
        print("edakit hook install writes or renews it (handbook 2.7)")
    else:
        print("the pre-commit hook runs edakit's steps")
    return 2 if problems else 0
