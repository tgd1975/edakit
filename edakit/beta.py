"""What is switched on before it is part of edakit: `[beta]` of edakit.toml. One entry so far – `dsl`, the explorative
DSL, the circuit language (docs/dsl/README.md). Without it a project is edakit's JSON or TOML one and nothing of the
DSL is read, offered or checked; with it a `.circuit` graph is the project's source.

    dsl_of(path)        is the DSL switched on in the project of a file or folder – the edakit.toml found upward?
    refusal(what)       the one line a command answers where the DSL is not switched on
"""

from __future__ import annotations

import tomllib
from pathlib import Path

DOC = "docs/dsl/README.md"
LIBRARY = Path(__file__).resolve().parent / "blocks"      # edakit's own block sources – always the DSL's form


def dsl_of(path):
    """True where the edakit.toml found upward from path sets [beta] dsl = true, and for a source of edakit's own
    block library; False without an edakit.toml, without the key, or in a file that does not parse."""
    path = Path(path).resolve()
    if LIBRARY in (path, *path.parents):
        return True
    for d in ([path] if path.is_dir() else []) + list(path.parents):
        toml = d / "edakit.toml"
        if toml.is_file():
            try:
                return tomllib.loads(toml.read_text(encoding="utf-8")).get("beta", {}).get("dsl") is True
            except (tomllib.TOMLDecodeError, AttributeError):
                return False
    return False


def refusal(what):
    return (f"{what}: the explorative DSL, a beta – a project switches it on with [beta] dsl = true in edakit.toml "
            f"({DOC})")
