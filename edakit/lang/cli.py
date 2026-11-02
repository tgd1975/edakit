"""The language's own actions of `edakit graph`: fmt (T.5), derive (T.8), and with the later steps sysml, kerml.

    edakit graph fmt [--check] [FILE …]   the canonical layout of the project's source files, or of the files named;
                                          --check writes nothing and exits 2 naming the first file and line that
                                          would change
    edakit graph derive [--write]         every derivation record evaluated again with the entries and nets as they
                                          are now; --write rewrites the records of a JSON graph
"""

from __future__ import annotations

import sys
from pathlib import Path

from .reader import CompileError


def source_files(cfg):
    """The project's source set: the main .circuit file (its includes and the variant chain with T.13 and T.14)."""
    graph = Path(cfg.graph)
    return [graph] if graph.suffix == ".circuit" else []


def main_fmt(cfg, args):
    from .fmt import format
    files = [Path(f) for f in ([args.name] if args.name else []) + list(getattr(args, "files", []) or [])]
    files = files or source_files(cfg)
    if not files:
        print(f"edakit graph fmt: {cfg.relative(cfg.graph)} is no .circuit file – nothing to format", file=sys.stderr)
        return 1
    code = 0
    for f in files:
        rel = cfg.relative(f) if cfg is not None and f.is_absolute() else f.as_posix()
        text = f.read_text(encoding="utf-8")
        try:
            out = format(text, rel, role="block" if f.parent.name == "blocks" else None)
        except CompileError as e:
            print(f"edakit graph fmt: {e}", file=sys.stderr)
            return 1
        if out == text:
            continue
        if args.check:
            a, b = text.splitlines(), out.splitlines()
            line = next((k for k, (x, y) in enumerate(zip(a, b), 1) if x != y), min(len(a), len(b)) + 1)
            print(f"{rel}:{line}: not in the canonical layout (edakit graph fmt)")
            code = 2
            continue
        f.write_text(out, encoding="utf-8")
        print(f"{rel} formatted")
    if code == 0 and args.check:
        print(f"{len(files)} file{'s' if len(files) != 1 else ''} in the canonical layout")
    return code


def main_derive(cfg, args):
    """edakit graph derive [--write]: every derivation record of the graph evaluated again with the entries and nets
    as they are now; --write rewrites the records of a JSON graph."""
    import json

    from ..block import write_json
    from ..design import Design
    from .rules import RuleError, refresh
    suffix = Path(cfg.graph).suffix
    design = Design.from_config(cfg)
    records = [r for r in design.graph.get("derivations") or [] if isinstance(r, dict)]
    if not records:
        print("no derivation records in the graph")
        return 0
    new, stale = [], 0
    for rec in records:
        try:
            fresh, changes = refresh(rec, design, records)
        except RuleError as e:
            print(f"{rec.get('part')}: {e}", file=sys.stderr)
            return 1
        new.append(fresh)
        if changes:
            stale += 1
            print(f"{rec.get('part')}: {rec.get('rule')} ({rec.get('from')}) – {', '.join(changes)}: derived "
                  f"{(rec.get('derived') or {}).get('value')} → {fresh['derived']['value']} "
                  f"{fresh['derived']['unit']}, window {fresh['series']['window']}")
    if not stale:
        print(f"{len(records)} record{'s' if len(records) != 1 else ''} current")
        return 0
    if not args.write:
        return 0
    if suffix == ".circuit":
        print("edakit graph derive: a .circuit source derives its records when it compiles – edakit graph json --write",
              file=sys.stderr)
        return 1
    if suffix == ".toml":
        print("edakit graph derive: the records of a TOML graph are its [[derivations]] tables – edit them there, or "
              "write the block again (edakit block add --set)", file=sys.stderr)
        return 1
    data = json.loads(Path(cfg.graph).read_text(encoding="utf-8"))
    g = data.get("graph", data)
    g["derivations"] = new
    write_json(cfg.graph, data)
    print(f"{cfg.relative(cfg.graph)}: {stale} record{'s' if stale != 1 else ''} written again")
    return 0


def main(cfg, args):
    return {"fmt": main_fmt, "derive": main_derive}[args.action](cfg, args)
