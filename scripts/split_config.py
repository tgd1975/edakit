"""Move a project from the one-file edakit.toml to its files (handbook 10.1) – once. Delete this script when the
known projects have moved.

    uv run --project <edakit> python <edakit>/scripts/split_config.py [PATH/edakit.toml] [--dry-run]

  1. [boards.<b>.*] and the physical keys of [boards.<b>] -> hardware/boards/<b>.toml, word for word without the
     prefix, comments included; [net_classes] goes into every board file.
  2. [schematic.*] -> hardware/schematic.toml, without the prefix.
  3. [checks] -> "checks" of the graph; [project] ground, when it is not GND, -> "ground" of the graph.
  4. [sim] config, plugin -> [project] sim, sim_plugin and [release] signoff -> [project] signoff, left out where they
     are the default; edakit.toml leaves [release] layout_files.
  5. Before anything is written, old and new are read back and compared value by value: one difference stops it.
  6. Sign-offs: where signoff.json holds the hashes of today's files – the sign-offs count now – it gets the hashes of
     the new files and an entry in "rehashed". Sign-offs that do not count now do not count afterwards either.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edakit import config  # noqa: E402
from edakit.release import gate  # noqa: E402

BARE = re.compile(r"^[A-Za-z0-9_-]+$")
HEADER = re.compile(r"^(\s*\[\[?[^\]#]*\]\]?)(\s*)(#.*)?$")
DEFAULT = {"sim": "hardware/sim.json", "signoff": "hardware/signoff.json", "schematic": "hardware/schematic.toml"}


def header_path(line):
    """[boards.main.place] -> ('boards', 'main', 'place'), [[boards.main.holes]] -> ('boards', 'main', 'holes')."""
    node, path = tomllib.loads(line), []
    while isinstance(node, (dict, list)) and node:
        if isinstance(node, list):
            node = node[-1]
            continue
        (key, node), = node.items()
        path.append(key)
    return tuple(path)


def items(text):
    """The file as [kind, lines, key]: "table" with its key path, "pair" (key = value, also over several lines) with
    its first key, "trivia" for blank lines and comments."""
    lines = text.splitlines(keepends=True)
    out, i = [], 0
    while i < len(lines):
        s = lines[i].strip()
        if not s or s.startswith("#"):
            out.append(["trivia", [lines[i]], None])
            i += 1
        elif s.startswith("["):
            out.append(["table", [lines[i]], header_path(lines[i])])
            i += 1
        else:
            for j in range(i, len(lines)):
                try:
                    pair = tomllib.loads("".join(lines[i:j + 1]))
                    break
                except tomllib.TOMLDecodeError:
                    pass
            else:
                sys.exit(f"cannot read the value in line {i + 1}: {s}")
            out.append(["pair", lines[i:j + 1], next(iter(pair))])
            i = j + 1
    return out


def renamed(line, path):
    """The header line for the key path in the new file; a comment keeps its column."""
    m = HEADER.match(line.rstrip("\n"))
    if not m:
        sys.exit(f"cannot read the table header {line.strip()}")
    name = ".".join(k if BARE.match(k) else json.dumps(k) for k in path)
    new = f"[[{name}]]" if line.strip().startswith("[[") else f"[{name}]"
    if not m.group(3):
        return new + "\n"
    return new + " " * max(1, len(m.group(1)) + len(m.group(2)) - len(new)) + m.group(3) + "\n"


def tidy(lines):
    """No blank line at the start, at most one blank line in a row, one newline at the end."""
    out = []
    for line in lines:
        if not line.strip() and (not out or not out[-1].strip()):
            continue
        out.append(line)
    return "".join(out).rstrip("\n") + "\n"


def split(text, name):
    """The one-file edakit.toml -> (manifest, {board: text}, schematic text, checks, ground, dropped comment lines)."""
    raw = tomllib.loads(text)
    project = raw.get("project", {})
    manifest, boards = [], {b: {"root": [], "tables": []} for b in raw.get("boards", {})}
    schematic_root, schematic, net_classes, dropped = [], [], [], []
    extra = [f'{key} = {json.dumps(raw["sim"][old])}\n' for key, old in (("sim", "config"), ("sim_plugin", "plugin"))
             if raw.get("sim", {}).get(old, DEFAULT.get(key)) != DEFAULT.get(key)]
    if raw.get("release", {}).get("signoff", DEFAULT["signoff"]) != DEFAULT["signoff"]:
        extra.append(f'signoff = {json.dumps(raw["release"]["signoff"])}\n')
    declared, pending, table, project_end = set(), [], None, None

    def drop(lines):
        dropped.extend(x.strip() for x in lines if x.strip().startswith("#") or "#" in x)

    for kind, lines, key in items(text):
        if kind == "trivia":
            pending += lines
            continue
        if kind == "table":
            table = key
            if table[0] == "boards" and len(table) == 2:
                declared.add(table[1])
                manifest += pending + lines
            elif table[0] == "boards":
                boards[table[1]]["tables"] += pending + [renamed(lines[0], table[2:])]
            elif table == ("schematic",):
                schematic_root += pending
            elif table[0] == "schematic":
                schematic += pending + [renamed(lines[0], table[1:])]
            elif table[0] == "net_classes":
                net_classes += pending + lines
            elif table[0] in ("checks", "sim"):
                drop(pending + lines)
            else:
                manifest += pending + lines
            pending = []
            continue
        if table is None:
            sys.exit(f"{name}: a key outside of any table ({key}) – move it by hand")
        if table[0] == "boards" and len(table) == 2:
            target = boards[table[1]]["root"] if key in config.BOARD_FILE_KEYS else manifest
        elif table[0] == "boards":
            target = boards[table[1]]["tables"]
        elif table == ("schematic",):
            target = schematic_root
        elif table[0] == "schematic":
            target = schematic
        elif table[0] == "net_classes":
            target = net_classes
        elif table[0] in ("checks", "sim") or (table == ("project",) and key == "ground") \
                or (table == ("release",) and key == "signoff"):
            drop(pending + lines)
            pending = []
            continue
        elif table == ("release",) and key == "layout_files":
            keep = [f for f in raw["release"]["layout_files"] if f != name]
            drop(lines)
            lines = [f"layout_files = {json.dumps(keep)}\n"] if keep else []
            target = manifest
        else:
            target = manifest
        target += pending + lines
        pending = []
        if table == ("project",):
            project_end = len(manifest)
    manifest += pending
    if extra:
        manifest[project_end:project_end] = extra
    for b in sorted(set(boards) - declared):       # a board declared only through its sub-tables
        manifest += ["\n", f"[boards.{b}]\n"]
    texts = {}
    for b, parts in boards.items():
        head = [f"# Board {b} of {project.get('name', '')}: outline, holes, placement, routing, pours, silk – the PCB "
                f"designer's file,\n", "# in the layout hash (edakit handbook 10.2)\n", "\n"]
        texts[b] = tidy(head + parts["root"] + ["\n"] + parts["tables"] + ["\n"] + net_classes)
    schematic_text = tidy([f"# Schematic of {project.get('name', '')}: blocks, notes, pin table (edakit handbook "
                           "10.3)\n", "\n"] + schematic_root + ["\n"] + schematic) if "schematic" in raw else None
    return tidy(manifest), texts, schematic_text, raw.get("checks"), project.get("ground", "GND"), dropped


def view_old(raw, name):
    """Every value of the one-file form, in the place it has afterwards."""
    p = {k: v for k, v in raw.get("project", {}).items() if k != "ground"}
    rel = {k: v for k, v in raw.get("release", {}).items() if k != "signoff"}
    if "layout_files" in rel:
        rel["layout_files"] = [f for f in rel["layout_files"] if f != name]
        if not rel["layout_files"]:
            del rel["layout_files"]
    sim = raw.get("sim", {})
    nc = {"net_classes": raw["net_classes"]} if "net_classes" in raw else {}
    return {"project": p, "sim": sim.get("config", DEFAULT["sim"]), "sim_plugin": sim.get("plugin"),
            "signoff": raw.get("release", {}).get("signoff", DEFAULT["signoff"]), "release": rel,
            "boards": {b: ({k: v for k, v in e.items() if k not in config.BOARD_FILE_KEYS},
                           {**{k: v for k, v in e.items() if k in config.BOARD_FILE_KEYS}, **nc})
                       for b, e in raw.get("boards", {}).items()},
            "schematic": raw.get("schematic", {}), "checks": raw.get("checks", {}),
            "ground": raw.get("project", {}).get("ground", "GND"),
            "other": {k: v for k, v in raw.items() if k not in ("project", "boards", "release", "schematic", "checks",
                                                               "net_classes", "sim")}}


def view_new(manifest, boards, schematic, graph):
    p = dict(manifest.get("project", {}))
    sim, plugin, signoff = p.pop("sim", DEFAULT["sim"]), p.pop("sim_plugin", None), p.pop("signoff", DEFAULT["signoff"])
    return {"project": p, "sim": sim, "sim_plugin": plugin, "signoff": signoff, "release": manifest.get("release", {}),
            "boards": {b: (e, boards[b]) for b, e in manifest.get("boards", {}).items()},
            "schematic": schematic, "checks": graph.get("checks", {}), "ground": graph.get("ground", "GND"),
            "other": {k: v for k, v in manifest.items() if k not in ("project", "boards", "release")}}


def old_hashes(raw, root):
    """The hashes as edakit computed them for the one-file form (gate.state_files and layout_files before the move)."""
    def r(f):
        return Path(f) if Path(f).is_absolute() else root / f
    p, sim, rel = raw.get("project", {}), raw.get("sim", {}), raw.get("release", {})
    state = [r(p.get("graph", "hardware/graph.json")), r(sim.get("config", DEFAULT["sim"])),
             *sorted(r(p.get("parts", "hardware/parts")).glob("*.json"))]
    if sim.get("plugin"):
        state.append(r(sim["plugin"]))
    state += [r(f) for f in rel.get("state_files", [])]
    layout = [r(f) for f in rel.get("layout_files", ["edakit.toml"])]
    layout += [r(p.get("artifacts", "build/edakit")) / f"pcb_geometry_{b}.json" for b in raw.get("boards", {})]
    return gate.file_hash(root, state), gate.file_hash(root, layout)


def dump_like(path, data):
    """JSON in the indent the file has, UTF-8 characters as they are (like edakit block add)."""
    m = re.search(r"^( +)\S", path.read_text(encoding="utf-8"), re.M)
    return json.dumps(data, indent=len(m.group(1)) if m else 1, ensure_ascii=False) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("config", nargs="?", help="edakit.toml (default: search upwards from the current directory)")
    ap.add_argument("--dry-run", action="store_true", help="compare and report, write nothing")
    args = ap.parse_args(argv)
    path = Path(args.config).resolve() if args.config else config.find_config()
    root, text = path.parent, path.read_text(encoding="utf-8")
    raw = tomllib.loads(text)
    if not config._one_file_form(raw, path.name):
        print(f"{path}: nothing to move – it is in the split form already")
        return 0
    manifest, boards, schematic, checks, ground, dropped = split(text, path.name)

    p = raw.get("project", {})
    graph_path = root / p.get("graph", "hardware/graph.json")
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    inner = data.get("graph", data)
    if ("checks" in inner and checks) or ("ground" in inner and ground != "GND"):
        sys.exit(f"{graph_path}: has checks or ground already – merge by hand")
    if checks:
        inner["checks"] = checks
    if ground != "GND":
        inner["ground"] = ground
    graph_text = dump_like(graph_path, data)
    targets = {root / f"hardware/boards/{b}.toml": t for b, t in boards.items() if tomllib.loads(t)}
    if schematic:
        targets[root / p.get("schematic", DEFAULT["schematic"])] = schematic
    for t in targets:
        if t.exists():
            sys.exit(f"{t} exists already – move by hand")

    new_graph = json.loads(graph_text)
    old, new = view_old(raw, path.name), view_new(tomllib.loads(manifest), {b: tomllib.loads(t) for b, t in boards.items()},
                                                 tomllib.loads(schematic) if schematic else {},
                                                 new_graph.get("graph", new_graph))
    if old != new:
        for k in old:
            if old[k] != new.get(k):
                print(f"  differs: {k}\n    before {old[k]}\n    after  {new.get(k)}")
        sys.exit("not moved: the files would not hold the same values")

    signoff_path = root / raw.get("release", {}).get("signoff", DEFAULT["signoff"])
    signoff = json.loads(signoff_path.read_text(encoding="utf-8")) if signoff_path.exists() else None
    old_state, old_layout = old_hashes(raw, root)
    valid = {"state_sha256": signoff is not None and signoff.get("state_sha256") == old_state,
             "layout_sha256": signoff is not None and signoff.get("layout_sha256") == old_layout}

    print(f"{path.name}: {len(text.splitlines())} -> {len(manifest.splitlines())} lines")
    for t, content in targets.items():
        print(f"  new  {t.relative_to(root)}: {len(content.splitlines())} lines")
    if checks or ground != "GND":
        print(f"  graph {graph_path.relative_to(root)}: + " + ", ".join(
            k for k, v in (("checks", checks), ("ground", ground != "GND")) if v))
    for line in dropped:
        print(f"  comment not carried over: {line}")
    for key, ok in valid.items():
        print(f"  sign-offs {key}: " + ("count today – they move along" if ok else "do not count today – unchanged"))
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    before = {path: text, graph_path: graph_path.read_text(encoding="utf-8")}
    try:
        path.write_text(manifest, encoding="utf-8")
        graph_path.write_text(graph_text, encoding="utf-8")
        for t, content in targets.items():
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_text(content, encoding="utf-8")
        cfg = config.load(path)
    except (config.ConfigError, OSError) as e:
        for f, content in before.items():
            f.write_text(content, encoding="utf-8")
        for t in targets:
            t.unlink(missing_ok=True)
        sys.exit(f"not moved, everything restored: {e}")
    if signoff is not None and any(valid.values()):
        hashes = {"state_sha256": gate.file_hash(cfg.root, gate.state_files(cfg)),
                  "layout_sha256": gate.file_hash(cfg.root, gate.layout_files(cfg))}
        entry = {"date": dt.date.today().isoformat(), "by": "edakit scripts/split_config.py",
                 "why": "edakit.toml split into board, schematic and graph files (handbook 10.1); every value read "
                        "back unchanged"}
        for key, ok in valid.items():
            if ok:
                entry[key] = [signoff[key], hashes[key]]
                signoff[key] = hashes[key]
        signoff.setdefault("rehashed", []).append(entry)
        signoff_path.write_text(dump_like(signoff_path, signoff), encoding="utf-8")
        print(f"  {signoff_path.relative_to(root)}: new hashes for " + ", ".join(k for k, ok in valid.items() if ok))
    print("moved – now edakit check, edakit handover and one commit for the move")
    return 0


if __name__ == "__main__":
    sys.exit(main())
