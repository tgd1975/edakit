"""The EDA tool the boards of a project are drawn in: [project] toolchain of edakit.toml (handbook 16).

    easyeda   EasyEDA Pro through the patched bridge and easyeda-mcp-pro (edakit/eda.py) – the default
    kicad     KiCad 10: edakit writes one KiCad project per board into <artifacts>/kicad/<board>/ and calls kicad-cli
              for what files cannot do – ERC, DRC with the zone fill, the exports (edakit/toolchain/kicad/)

Everything that reads only edakit's own files is shared: graph, parts, simulation, plan, placement, DSN, Freerouting,
the checks of the gate. A command that reads or writes the EDA project asks is_kicad(cfg) and takes the KiCad side; the
EasyEDA side stays where it is (docs/concepts/done/kicad-toolchain.md, decision 6). A step without a counterpart says
so with only_easyeda.
"""

from __future__ import annotations

import sys


def is_kicad(cfg):
    """True when the project's boards are KiCad projects (toolchain = "kicad")."""
    return getattr(cfg, "toolchain", "easyeda") == "kicad"


def only_easyeda(cfg, what, instead):
    """None for an EasyEDA project; for a KiCad project the message why `what` has no KiCad side and what to do
    instead, and exit code 1."""
    if not is_kicad(cfg):
        return None
    print(f"edakit {what}: EasyEDA only – the project's tool chain is KiCad ([project] toolchain = \"kicad\"); "
          f"{instead}", file=sys.stderr)
    return 1
