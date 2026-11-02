"""The language's own actions of `edakit graph`: fmt (T.5), and with the later steps derive, sysml, kerml.

    edakit graph fmt [--check] [FILE …]   the canonical layout of the project's source files, or of the files named;
                                          --check writes nothing and exits 2 naming the first file and line that
                                          would change
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


def main(cfg, args):
    return {"fmt": main_fmt}[args.action](cfg, args)
