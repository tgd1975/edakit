"""edakit's version as one string, for `edakit --version` and the gate manifest's tools.edakit.

The number is `__version__` in edakit/__init__.py, written by .github/merge.py at every merge that changes edakit
(docs/concepts/new/versioning.md). Run from a git checkout away from that number's tag, the commit is added –
0.2.0+g1a2b3c4 –, so a manifest names the edakit that released a board even when it was not a version. The plugin's
cache and an install by uvx have no .git: there the number alone.
"""

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
