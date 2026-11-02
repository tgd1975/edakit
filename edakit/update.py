"""`edakit version`: which edakit runs, which the plugin installed per scope, the newest version on GitHub, what the
changelog says in between – its **When updating:** lines first –, and where the project pins edakit (handbook 2.3).

Everything is read, nothing is changed: the update itself is `claude plugin update`, on the owner's word (the skill
version). The functions take data and return data; `main` reads the files, the tags (`git ls-remote`) and the newest
changelog (raw.githubusercontent.com) – without network, or with `--offline`, the newest version stays unknown.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .version import ROOT, _key, meets, version

REPO = "tgd1975/edakit"
PLUGIN = "edakit@"                     # edakit@edakit, or edakit from another marketplace
UPDATE = "claude plugin marketplace update edakit && claude plugin update edakit@edakit"
TAG = re.compile(r"^refs/tags/v(\d+\.\d+\.\d+)(\^\{\})?$")
SECTION = re.compile(r"^## (\d+\.\d+\.\d+)(?:\s+[–-]\s+(\S+))?\s*$")
WHEN = "- **When updating:**"
PINNED = re.compile(r"tgd1975/edakit(?:\.git)?@([^\s\"'#)]+)")
GIT_URL = re.compile(r"git\+https://github\.com/tgd1975/edakit(?:\.git)?(?:@([^\s\"'#)]+))?")
FOLLOW = {"main", "HEAD", "master"}    # a ref that follows the newest version: no pin
SCOPES = {"local": 0, "project": 1, "user": 2, "managed": 3}   # the most specific installation wins
TEXT_MAX = 200_000
RUNS = {".sh", ".bash", ".zsh", ".yml", ".yaml", ".ps1", ".bat", ".cmd"}      # files that start edakit, not documents
RUNS_NAMED = {"Makefile", "justfile", "Dockerfile", "pyproject.toml"}


# --- the plugin's installations -----------------------------------------------------------------------------------

def plugins_file():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(base) / "plugins" / "installed_plugins.json"


def installed(data, project):
    """[{scope, project, version, path, here}] of edakit in Claude Code's installed_plugins.json; `here` marks the
    installation that a session in `project` uses: local or project scope of that folder, else the user scope."""
    plugins = (data or {}).get("plugins", data or {})
    out = []
    for name, entries in plugins.items():
        if not name.startswith(PLUGIN) or not isinstance(entries, list):
            continue
        for e in entries:
            out.append({"scope": e.get("scope", "?"), "project": e.get("projectPath"), "version": e.get("version"),
                        "path": e.get("installPath"), "here": False})
    project = str(project) if project else None
    mine = [x for x in out if x["project"] is None or x["project"] == project]
    if mine:
        min(mine, key=lambda x: SCOPES.get(x["scope"], 9))["here"] = True
    return out


# --- the versions on GitHub ---------------------------------------------------------------------------------------

def tags(ls_remote):
    """{commit: number} of the version tags in `git ls-remote --tags` output; an annotated tag's commit too."""
    out = {}
    for line in ls_remote.splitlines():
        sha, _, ref = line.partition("\t")
        m = TAG.match(ref.strip())
        if m:
            out[sha.strip()] = m.group(1)
    return out


def newest(tagmap):
    return max(tagmap.values(), key=_key, default=None)


def between(changelog, after, upto):
    """The changelog's sections of the versions newer than `after`, up to `upto`, newest first:
    [{number, date, lines}] – a bullet's wrapped lines joined into one."""
    out, cur = [], None
    for raw in changelog.splitlines():
        m = SECTION.match(raw)
        if m:
            cur = {"number": m.group(1), "date": m.group(2), "lines": []}
            if _key(after) < _key(cur["number"]) <= _key(upto):
                out.append(cur)
            continue
        if cur is None or raw.startswith("#"):
            continue
        if raw.startswith("- "):
            cur["lines"].append(raw.rstrip())
        elif raw.strip() and cur["lines"]:
            cur["lines"][-1] += " " + raw.strip()
    return out


def todo(sections):
    """[(number, text)] of the **When updating:** lines – what a project must do, newest first."""
    return [(s["number"], line[len(WHEN):].strip()) for s in sections for line in s["lines"] if line.startswith(WHEN)]


# --- where the project pins edakit --------------------------------------------------------------------------------

def _files(root):
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout:
            return sorted(root / f for f in r.stdout.split("\0") if f)
    except (OSError, subprocess.TimeoutExpired):
        pass
    skip = {".git", ".venv", "node_modules", "build", "__pycache__"}
    return sorted(p for p in root.rglob("*") if p.is_file() and not skip & set(p.relative_to(root).parts))


def _runs(path, root):
    rel = path.relative_to(root)
    return (path.suffix in RUNS or path.name in RUNS_NAMED or rel.parts[0] in (".github", ".githooks")
            or "hooks" in rel.parts[:-1])


def _resolve(ref, text):
    """`$NAME` or `${NAME}` – the value of `NAME=…` in the same file, as pytree's hardware/edakit.sh sets it."""
    m = re.fullmatch(r"\$\{?(\w+)\}?", ref)
    if not m:
        return ref
    v = re.search(rf"^\s*(?:export\s+)?{m.group(1)}=[\"']?([^\s\"'#]+)", text, re.M)
    return v.group(1) if v else ref


def ref_version(ref, tagmap):
    """The version a ref names: v1.0.3 → 1.0.3, a commit with a version tag → its number, else None."""
    m = re.fullmatch(r"v?(\d+\.\d+\.\d+)", ref)
    if m:
        return m.group(1)
    if re.fullmatch(r"[0-9a-f]{7,40}", ref):
        return next((n for sha, n in tagmap.items() if sha.startswith(ref)), None)
    return None


def pins(root, tagmap):
    """[{where, ref, version}]: the ref of edakit's marketplace in .claude/settings.json, and every
    tgd1975/edakit@<ref> in the files that start edakit – CI, hooks, scripts, YAML, Makefile, pyproject.toml; no
    document – with a `$NAME` read from the same file."""
    root = Path(root)
    out = []
    for name in ("settings.json", "settings.local.json"):
        f = root / ".claude" / name
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ref = (((data.get("extraKnownMarketplaces") or {}).get("edakit") or {}).get("source") or {}).get("ref")
        if ref:
            out.append({"where": f".claude/{name}", "ref": ref, "version": ref_version(ref, tagmap)})
    for f in _files(root):
        if not _runs(f, root):
            continue
        try:
            if f.stat().st_size > TEXT_MAX:
                continue
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "tgd1975/edakit" not in text:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for m in PINNED.finditer(line):
                ref = _resolve(m.group(1), text)
                if ref.startswith("$") or ref in FOLLOW:   # $(…), a variable set elsewhere, main: no pin
                    continue
                out.append({"where": f"{f.relative_to(root)}:{i}", "ref": ref, "version": ref_version(ref, tagmap)})
    return out


def required(root):
    """[(file, requirement)] of [project] edakit in the repository's edakit.toml files."""
    import tomllib
    out = []
    for f in _files(Path(root)):
        if f.name != "edakit.toml":
            continue
        try:
            asked = (tomllib.loads(f.read_text(encoding="utf-8")).get("project") or {}).get("edakit")
        except (OSError, ValueError):
            continue
        if asked:
            out.append((str(f.relative_to(root)), asked))
    return out


# --- pin and unpin ---------------------------------------------------------------------------------------------

def _project_key(text, value):
    """edakit.toml's text with [project] edakit = value – the line replaced, or added at the table's end."""
    m = re.search(r"^\[project\][^\n]*\n", text, re.M)
    if not m:
        return f'[project]\nedakit = "{value}"\n\n' + text
    nxt = re.search(r"^\[", text[m.end():], re.M)
    end = m.end() + (nxt.start() if nxt else len(text) - m.end())
    section = text[m.end():end]
    k = re.search(r"^(\s*edakit\s*=\s*)(\"[^\"]*\"|'[^']*')", section, re.M)
    if k:
        section = section[:k.start(2)] + f'"{value}"' + section[k.end(2):]
    else:
        body = section.rstrip("\n")
        section = (body + "\n" if body else "") + f'edakit = "{value}"\n' + "\n" * (len(section) - len(body) - 1
                                                                                  if body else 0)
    return text[:m.end()] + section + text[end:]


def _asked(text):
    m = re.search(r"^\[project\][^\n]*\n(.*?)(?=^\[|\Z)", text, re.M | re.S)
    k = m and re.search(r"^\s*edakit\s*=\s*[\"']([^\"']*)[\"']", m.group(1), re.M)
    return k.group(1) if k else None


def _settings_without_ref(root):
    out = []
    for name in ("settings.json", "settings.local.json"):
        f = root / ".claude" / name
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            source = data["extraKnownMarketplaces"]["edakit"]["source"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if "ref" in source:
            ref = source.pop("ref")
            out.append({"file": f".claude/{name}", "text": json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        "what": [f"the marketplace's ref {ref} taken out – a ref there holds the plugin for every "
                                 "project on the machine, not for this one (handbook 2.3)"]})
    return out


def _calls(root, number):
    """The changes of the files that start edakit: every git+…/tgd1975/edakit call at v<number>, or without a ref
    for None – a `$NAME` changed where it is set."""
    out = []
    for f in _files(root):
        if not _runs(f, root):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "tgd1975/edakit" not in text:
            continue
        new, what = text, []
        for m in reversed(list(GIT_URL.finditer(text))):
            ref, line = m.group(1), text.count("\n", 0, m.start()) + 1
            var = re.fullmatch(r"\$\{?(\w+)\}?", ref or "")
            if var:
                setter = re.compile(rf"^(\s*(?:export\s+)?{var.group(1)}=)[\"']?([^\s\"'#]+)[\"']?", re.M)
                s = setter.search(new)
                want = f"v{number}" if number else "main"
                if s and s.group(2) != want:
                    new = new[:s.start()] + s.group(1) + want + new[s.end():]
                    what.append(f"{var.group(1)}={want} (was {_short(s.group(2))})")
                continue
            if ref and ref.startswith("$"):
                continue                                   # $(…): reads a pin elsewhere
            pinned = ref and ref not in FOLLOW
            if number and ref != f"v{number}":
                url = m.group(0).split("@")[0] + f"@v{number}"
            elif not number and pinned:
                url = m.group(0).split("@")[0]
            else:
                continue
            new = new[:m.start()] + url + new[m.end():]
            what.append(f"line {line}: " + (f"at v{number}" if number else "follows the newest")
                        + (f" (was {_short(ref)})" if pinned else ""))
        if new != text:
            out.append({"file": str(f.relative_to(root)), "text": new, "what": list(reversed(what))})
    return out


def _tomls(root, change):
    out = []
    for f in _files(root):
        if f.name != "edakit.toml":
            continue
        text = f.read_text(encoding="utf-8")
        value = change(_asked(text))
        if value and value != _asked(text):
            was = _asked(text)
            out.append({"file": str(f.relative_to(root)), "text": _project_key(text, value),
                        "what": [f'[project] edakit = "{value}"' + (f' (was "{was}")' if was else "")]})
    return out


def pin(root, number):
    """The changes that pin the project at edakit <number>: [project] edakit = "==<number>" in every edakit.toml, every
    call in CI and scripts at v<number>, the settings' ref out – [{file, text, what}]."""
    root = Path(root)
    return _tomls(root, lambda _: f"=={number}") + _calls(root, number) + _settings_without_ref(root)


def unpin(root):
    """The changes that let the project follow the updates: "==x" becomes ">=x", the calls lose their ref."""
    root = Path(root)

    def lower(asked):
        m = re.fullmatch(r"\s*==\s*(\d+(?:\.\d+){0,2})\s*", asked or "")
        return f">={m.group(1)}" if m else None
    return _tomls(root, lower) + _calls(root, None) + _settings_without_ref(root)


def apply(root, changes):
    for c in changes:
        (Path(root) / c["file"]).write_text(c["text"], encoding="utf-8")


# --- the report ---------------------------------------------------------------------------------------------------

def _short(ref):
    return ref[:7] if re.fullmatch(r"[0-9a-f]{8,40}", ref) else ref


def report(state):
    """(lines, findings) of a state {running, path, installed, newest, changes, pins, required, offline?}; a finding
    is what the project should act on – an edakit behind the newest, pins that disagree, a requirement not met."""
    lines = [f"edakit {state['running']} runs ({state['path']})"]
    findings = []
    here = next((x for x in state["installed"] if x["here"]), None)
    if state["installed"]:
        lines.append("plugin:")
        for x in state["installed"]:
            where = "user" if x["scope"] == "user" else f"{x['scope']} {x['project']}"
            lines.append(f"  {where}: {x['version']}" + (" (in effect here)" if x["here"] else ""))
    else:
        lines.append("plugin: not installed in Claude Code (edakit runs from a clone or uvx)")
    have = here["version"] if here and here.get("version") else state["running"]
    have = min(have, state["running"].split("+")[0], key=_key)
    top = state.get("newest")
    if not top:
        lines.append(f"newest: unknown ({state.get('offline') or 'no network'})")
    elif _key(have) >= _key(top):
        lines.append(f"newest: {top} – up to date")
    else:
        lines.append(f"newest: {top}")
        findings.append(f"edakit {have} is behind {top}")
    for p in state["pins"]:
        named = p["version"] or "no version tag"
        lines.append(f"pinned: {p['where']} {_short(p['ref'])} ({named})")
    named = {p["version"] or _short(p["ref"]) for p in state["pins"]}
    if len(named) > 1:
        findings.append("the pins disagree: " + ", ".join(f"{p['where']} {p['version'] or _short(p['ref'])}"
                                                           for p in state["pins"]))
    elif state["pins"] and named != {state["running"].split("+")[0]}:
        findings.append(f"the project pins {named.pop()}, {state['running']} runs")
    for where, asked in state["required"]:
        try:
            ok = meets(asked, state["running"])
        except ValueError:
            ok = True                              # edakit check names a requirement it cannot read
        lines.append(f"[project] edakit in {where}: {asked!r} – {'met' if ok else 'not met'}")
        if not ok:
            findings.append(f'{where}: [project] edakit asks for "{asked}", {state["running"]} runs')
    changes = state.get("changes") or []
    if changes:
        must = todo(changes)
        lines += ["", f"When updating from {have} to {top} – what the project must do:"]
        lines += [f"  {n}: {t}" for n, t in must] or ["  nothing beyond the update itself"]
        lines += ["", "What changed:"]
        for s in changes:
            lines.append(f"  {s['number']} – {s['date'] or ''}".rstrip(" –"))
            lines += [f"    {x}" for x in s["lines"]]
    if top and _key(have) < _key(top):
        scope = here["scope"] if here and here["scope"] != "user" else None
        lines += ["", "update: " + UPDATE + (f" --scope {scope}" if scope else "")
                  + (f" (in {here['project']})" if scope else "") + ", then /reload-plugins or a new session"]
    if findings:
        lines += ["", *[f"FINDING {f}" for f in findings]]
    return lines, findings


# --- reading and the command --------------------------------------------------------------------------------------

def _ls_remote():
    r = subprocess.run(["git", "ls-remote", "--tags", f"https://github.com/{REPO}"], capture_output=True, text=True,
                       timeout=20)
    if r.returncode:
        raise OSError(r.stderr.strip() or "git ls-remote failed")
    return r.stdout


def _changelog(number):
    req = urllib.request.Request(f"https://raw.githubusercontent.com/{REPO}/v{number}/CHANGELOG.md",
                                 headers={"User-Agent": "edakit"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8")


def _project_root(cwd):
    try:
        r = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                           timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    return Path(cwd)


def gather(cwd, offline=False):
    root = _project_root(cwd)
    try:
        data = json.loads(plugins_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    state = {"running": version(), "path": str(ROOT), "installed": installed(data, root), "newest": None,
             "changes": [], "pins": [], "required": required(root) if (root / ".git").exists() else [],
             "root": str(root)}
    tagmap = {}
    if offline:
        state["offline"] = "--offline"
    else:
        try:
            tagmap = tags(_ls_remote())
            state["newest"] = newest(tagmap)
            state["tags"] = tagmap
        except (OSError, subprocess.TimeoutExpired) as e:
            state["offline"] = f"no network: {e}"
    if (root / ".git").exists():
        state["pins"] = pins(root, tagmap)
    here = next((x for x in state["installed"] if x["here"]), None)
    have = min(here["version"] if here and here.get("version") else state["running"],
               state["running"].split("+")[0], key=_key)
    if state["newest"] and _key(have) < _key(state["newest"]):
        try:
            state["changes"] = between(_changelog(state["newest"]), have, state["newest"])
        except (OSError, urllib.error.URLError) as e:
            state["changes_error"] = str(e)
    return state


def _target(state, target):
    """The number `pin` names: current – the edakit in effect here –, latest – the newest tag –, or a number."""
    here = next((x for x in state["installed"] if x["here"]), None)
    if target in (None, "current"):
        return (here or {}).get("version") or state["running"].split("+")[0]
    if target == "latest":
        if not state.get("newest"):
            raise ValueError(f"the newest version is unknown ({state.get('offline') or 'no network'})")
        return state["newest"]
    m = re.fullmatch(r"v?(\d+\.\d+\.\d+)", target)
    if not m:
        raise ValueError(f"{target!r}: current, latest or a version such as 1.0.9")
    if state.get("tags") and m.group(1) not in state["tags"].values():
        raise ValueError(f"{m.group(1)}: no such version tag on GitHub (newest {state.get('newest')})")
    return m.group(1)


def main_pin(args, state):
    root = Path(state["root"])
    try:
        changes = unpin(root) if args.action == "unpin" else pin(root, number := _target(state, args.target))
    except ValueError as e:
        print(f"edakit version {args.action}: {e}", file=sys.stderr)
        return 1
    head = "follow the updates" if args.action == "unpin" else f"pin edakit {number}"
    if not changes:
        print(f"{head}: nothing to change")
        return 0
    print(f"{head}:")
    for c in changes:
        for w in c["what"]:
            print(f"  {c['file']}: {w}")
    if args.write:
        apply(root, changes)
        print("written – then edakit check, and commit" + ("" if args.action == "unpin" else
              "; the plugin keeps following its own updates: the session start and edakit check name a mismatch"))
    else:
        print("dry run – nothing written; --write writes it")
    return 0


def main(args):
    if getattr(args, "action", None):
        return main_pin(args, gather(Path.cwd(), offline=args.offline))
    state = gather(Path.cwd(), offline=args.offline)
    lines, findings = report(state)
    if state.get("changes_error"):
        lines.append(f"changelog not read: {state['changes_error']}")
    print("\n".join(lines))
    if args.json:
        Path(args.json).write_text(json.dumps({**state, "findings": findings}, indent=1, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
    return 2 if findings else 0
