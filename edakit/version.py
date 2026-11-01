"""edakit's version as one string, for `edakit --version` and the gate manifest's tools.edakit.

The number is `__version__` in edakit/__init__.py, written by .github/merge.py at every merge that changes edakit
(docs/concepts/done/versioning.md). Run from a git checkout away from that number's tag, the commit is added –
0.2.0+g1a2b3c4 –, so a manifest names the edakit that released a board even when it was not a version. The plugin's
cache and an install by uvx have no .git: there the number alone.
"""

import re
import subprocess
from pathlib import Path

from . import __version__

ROOT = Path(__file__).resolve().parents[1]


def _git(root, *args):
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def version(root=ROOT):
    """The number, and +g<commit> from a git checkout whose HEAD is not the number's tag."""
    if not (root / ".git").exists():
        return __version__
    if f"v{__version__}" in _git(root, "tag", "--points-at", "HEAD").split():
        return __version__
    sha = _git(root, "rev-parse", "--short=7", "HEAD")
    return f"{__version__}+g{sha}" if sha else __version__


CLAUSE = re.compile(r"^(>=|<=|==|>|<)\s*(\d+(?:\.\d+){0,2})$")


def parse(required):
    """[(operator, number)] of a requirement such as ">=0.4, <0.5" – [project] edakit in edakit.toml; ValueError when
    edakit cannot read it."""
    clauses = [c.strip() for c in str(required).split(",")]
    found = [CLAUSE.match(c) for c in clauses]
    if not str(required).strip() or not all(found):
        raise ValueError(f"{required!r}: comparisons such as \">=0.4\" or \">=0.4, <0.5\" (>=, >, <=, <, ==)")
    return [(m.group(1), m.group(2)) for m in found]


def _key(number):
    parts = tuple(int(x) for x in number.split("+")[0].split("."))
    return parts + (0,) * (3 - len(parts))


def meets(required, have=__version__):
    """True when the edakit `have` (0.4.11, 0.4.11+g1a2b3c4) meets the requirement."""
    h = _key(have)
    compare = {">=": h.__ge__, ">": h.__gt__, "<=": h.__le__, "<": h.__lt__, "==": h.__eq__}
    return all(compare[op](_key(n)) for op, n in parse(required))
