"""The quickstart (docs/quickstart.md) on the example of the walkthrough: every command it shows, run on a fresh copy
of examples/coin-cell-led, prints the lines the page quotes. A line cut with "…" counts up to the cut."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "quickstart.md"
EXAMPLE = ROOT / "examples" / "coin-cell-led"


def shown():
    """[(command, [quoted lines])] – each text block of the page that starts with `$ edakit …`."""
    out = []
    for block in re.findall(r"```text\n(.*?)```", PAGE.read_text(encoding="utf-8"), re.S):
        lines = block.rstrip("\n").splitlines()
        if lines and lines[0].startswith("$ edakit "):
            out.append((lines[0][2:], [ln for ln in lines[1:] if ln.strip() and ln.strip() != "…"]))
    return out


def test_the_page_shows_the_steps_it_names():
    assert [c for c, _ in shown()] == ["edakit graph show D1", "edakit check", "edakit explain PATH.reverse",
                                       "edakit sim", "edakit schematic draw"]


@pytest.mark.parametrize("command,lines", shown(), ids=[c for c, _ in shown()])
def test_the_command_prints_what_the_page_quotes(tmp_path, command, lines):
    if command == "edakit sim" and not shutil.which("ngspice"):
        pytest.skip("ngspice not installed")
    work = tmp_path / "coin-cell-led"
    shutil.copytree(EXAMPLE, work, ignore=shutil.ignore_patterns("build"))
    run = subprocess.run([sys.executable, "-c", "import sys; from edakit.cli import main; sys.exit(main())",
                          *command.split()[1:]], cwd=work, capture_output=True, text=True)
    printed = run.stdout + run.stderr
    missing = [ln for ln in lines if ln.split("…")[0].rstrip() not in printed]
    assert missing == [], printed
