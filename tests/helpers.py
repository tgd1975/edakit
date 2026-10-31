"""What the tests read of edakit check: its findings as (code, text) pairs by severity."""

from edakit import engines
from edakit.findings import names_place


def said(f):
    """'Q5: no resistor from …' – the place and what was found, as edakit check prints them."""
    return f.text if names_place(f.text, f.place) else f"{f.place}: {f.text}"


class Checked:
    """The findings of a run of the engines – errors, warnings, notes, pending as (code, text), accepted ones as (code,
    text, reason), findings about a draft of the requirements file in drafts –, and the report itself."""

    def __init__(self, report):
        self.report = report
        draft = [f for f in report.findings if f.data.get("draft")]
        self.errors = [(f.code, said(f)) for f in report.errors]
        self.warnings = [(f.code, said(f)) for f in report.warnings if f not in draft]
        self.notes = [(f.code, said(f)) for f in report.notes]
        self.pending = [(f.code, said(f)) for f in report.pending]
        self.waived = [(f.code, said(f), f.accepted) for f in report.accepted]
        self.drafts = [(f.code, said(f)) for f in draft]

    @property
    def findings(self):
        return self.report.findings


def check(design, cfg=None):
    """What edakit check finds: the graph engines, and with a project the checks beyond the graph."""
    return Checked(engines.run_all(design, cfg) if cfg is not None else engines.run(design))


def executed(cfg):
    """The codes of stages P and G the gate counts as passed when they have no finding."""
    from edakit.design import Design
    from edakit.release import gate
    return gate.executed(engines.profile(Design.from_config(cfg), cfg), cfg)
