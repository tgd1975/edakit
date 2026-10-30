"""The engines (concept docs/concepts/new/rules-at-scale.md, section 2): few engines, much data. An engine decides one
kind of thing and knows no MOSFET and no LED; what makes a part what it is – which quantities it yields, which limits
its entry declares, what it requires on its pins – is data: the parts entry, catalog/needs.toml, catalog/levels.toml,
catalog/paths.toml and the tables.

    STRUCT    the graph is well-formed and names what exists            struct.py
    LIMITS    every quantity within its limit                           limits.py, the quantities: quantities.py
    LEVELS    every input defined at reset, no two drivers fight        levels.py
    REQUIRES  what a part requires on its pins is there and in range    requires.py
    PATHS     what a reversed, unfed or misplaced supply reaches        paths.py
    PARTS     parts entries complete: the facts the profile requires    parts.py
    HINT      patterns that need judgement, as notes                    hint.py
    SIM       the scenarios run and reach their states (stage E)        sim.py

run(design, cfg) gives the findings of stages P and G these engines decide, as a Report with severities from the
profile and the graph's accepts applied. A design in the form of before is converted in memory (convert.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import convert
from .. import profile as profiles
from ..findings import Report


@dataclass
class Context:
    """What every engine reads: the design (new form), its nets joined by 0 Ω bridges, the project, the simulation
    config (sources, ambient)."""
    design: object
    joined: object
    cfg: object = None
    sim: dict = field(default_factory=dict)
    profile: object = None

    @property
    def root(self):
        return self.cfg.root if self.cfg else "."


def is_converted(design):
    return not any("ratings" in p or "params" in p for p in design.parts.values()) \
        and not any("waive" in x for x in [*design.graph.get("components", []), *design.graph.get("nets", [])]) \
        and "hints" not in design.graph and "reverse_protect" not in (design.graph.get("checks") or {}) \
        and "pin_locks" not in (design.graph.get("checks") or {})


def converted(design):
    """The design in the form of the restructuring: itself, or converted in memory."""
    return design if is_converted(design) else convert.design(design)


def context(design, cfg=None, sim=None):
    from .. import rules
    d = converted(design)
    if sim is None and cfg is not None:
        sim = rules.load_sim(cfg)
    return Context(d, d.joined(), cfg, sim or {}, profiles.build(d, cfg))


def profile(design, cfg=None):
    """The project's profile (profile.py): its domains, their severities and switches."""
    return profiles.build(design, cfg)


def report(findings, prof, graph, notes=True):
    """The findings the profile reports – with the notes of domains the graph suggests and the project left out –,
    their severities resolved, the graph's accepts applied."""
    return Report([f for f in findings if prof.on(f)] + (prof.notes if notes else []), prof).resolve(graph)


def graph_findings(ctx):
    from . import hint, levels, limits, parts, paths, requires, struct
    out = []
    for engine in (struct, limits, levels, requires, paths, parts, hint):
        out += engine.run(ctx)
    return out


def run(design, cfg=None, sim=None):
    """The findings of the graph engines on a design (either form) as a resolved Report."""
    ctx = context(design, cfg, sim)
    return report(graph_findings(ctx), ctx.profile, ctx.design.graph)


def run_all(design, cfg=None, sim=None):
    """What edakit check checks: the graph engines, and with a project the checks beyond the graph (project.py)."""
    from . import project
    ctx = context(design, cfg, sim)
    found = graph_findings(ctx) + (project.run(design, cfg) if cfg is not None else [])
    return report(found, ctx.profile, ctx.design.graph)
