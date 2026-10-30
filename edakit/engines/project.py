"""SYNC, GEO, PARTS and DOCS before the layout: what `edakit check` checks beyond the graph – own parts against their
source and footprint copies against their data (SYNC.source, SYNC.footprint), holes and formed leads on the
footprint geometry (GEO.hole, GEO.formed), stock, supplier, footprint data and the sign-off of every part (PARTS.*),
the requirements file (DOCS.*), the project's scripts and agents (SYNC.scripts, SYNC.agents).

These checks live with what they read (part.py, stock.py, order.py, footprint.py, checks.py, requirements.py,
scripts.py) and report into a Recorder: an error, a warning, a pending point, a note or a draft of the requirements
file – the class gives the finding its grade where the code has one for it (GRADES), so that its severity is the
profile's (catalog/codes.toml, edakit/domains).
"""

from __future__ import annotations

import re

from ..findings import Finding

# code -> {class of a report: grade}; class: error, warning, pending, note, draft
GRADES = {
    "SYNC.source": {"warning": "margin", "pending": "stale", "note": "unchecked"},
    "PARTS.stock": {"warning": "margin", "pending": "stale", "note": "unchecked"},
    "GEO.hole": {"warning": "margin", "note": "unknown"},
    "GEO.formed": {"note": "unknown"},
    "SYNC.footprint": {"note": "unknown"},
    "DOCS.ref": {"warning": "margin", "draft": "draft"},
    "DOCS.need": {"draft": "draft"},
    "DOCS.evidence": {"draft": "draft"},
    "DOCS.draft": {"draft": ""},
    "SYNC.scripts": {"warning": "margin", "note": "unchecked"},
}
PLACE = re.compile(r"^([A-Za-z][\w.+-]*?)(?:[:\s(]|$)")


class Recorder:
    """The report interface the checks beyond the graph write to: error(code, msg, accept), add(class, code, msg,
    reason, grade), and the lists errors, pending, warnings, notes, waived, drafts – each entry a finding with its
    code and grade; its place the message's first word."""

    def __init__(self, stage="P"):
        self.stage, self.findings = stage, []
        recorder = self

        class Into(list):
            def __init__(self, cls):
                super().__init__()
                self.cls = cls

            def append(self, item):
                recorder.add(self.cls, *item)

            def __iadd__(self, items):
                for item in items:
                    self.append(item)
                return self
        self.errors, self.pending, self.warnings = Into("error"), Into("pending"), Into("warning")
        self.notes, self.waived, self.drafts = Into("note"), Into("accepted"), Into("draft")

    def error(self, code, msg, accept=None):
        grade = GRADES.get(code, {}).get("error", "")
        reason = next((accept[k] for k in ([f"{code}/{grade}"] if grade else []) + [code] if k in (accept or {})), "")
        self.add("error", code, msg, reason)

    def add(self, cls, code, msg, reason="", grade=None):
        m = PLACE.match(msg)
        f = Finding(code, self.stage, m.group(1) if m else code, msg,
                    grade=GRADES.get(code, {}).get(cls, "") if grade is None else grade, accepted=reason or "")
        f.data["class"] = cls
        if cls == "draft":
            f.data["draft"] = True
        self.findings.append(f)

    @property
    def codes(self):
        return [f.code for f in self.findings]


def run(design, cfg):
    """The findings of the checks beyond the graph, for a project (cfg)."""
    from .. import checks, footprint, order, part, requirements, scripts, stock
    rec = Recorder()
    part.check(design, rec, cfg)
    if not checks.check_holes(design, rec, checks.footprint_geometry(design, cfg)):
        rec.notes.append(("GEO.hole", "not run: no footprint geometry – edakit pcb dump once the parts are in the PCB, "
                                      "or edakit part import <LCSC> for the library's"))
    from ..pcb import move_notes
    rec.notes += [("GEO.hole", note) for note in move_notes(cfg)]
    checks.check_formed(design, rec, cfg)
    if checks.has_footprint_data(cfg, design):
        footprint.check(design, rec, cfg)
    stock.check(design, rec, cfg)
    order.check(design, rec, cfg)
    checks.check_signoff(design, rec)
    if cfg.requirements:
        requirements.check(rec, cfg)
    for level, msg in scripts.findings(cfg):
        rec.add(level, "SYNC.scripts", msg)
    for f in (scripts.agents(cfg).findings if cfg.agents else []):
        rec.add("error", "SYNC.agents", f.msg)
    for f in rec.findings:
        f.stage = "G" if f.code.startswith(("DOCS.", "SYNC.scripts", "SYNC.agents")) else "P"
    return rec.findings
