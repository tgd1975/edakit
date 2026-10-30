"""SYNC, GEO, FILES, PARTS, DOCS before the layout: what `edakit check` checks beyond the graph – own parts against
their source and footprint copies against their data (SYNC), holes and formed leads on the footprint geometry (GEO),
stock, supplier, footprint data and the sign-off of every part (PARTS), the requirements file (DOCS), the project's
scripts and agents (SYNC) – and the gate's rows of stages S, L and F (row_code).

The checks are where they were (part.py, stock.py, order.py, footprint.py, checks.py, requirements.py, scripts.py,
release/fab.py); they report into a Recorder, which gives every report its code and grade (MAP): the regrouping of
build step 4 is naming and the finding format (concept rules-at-scale.md, section 10).
"""

from __future__ import annotations

import re

from ..findings import Finding

# check ID of before -> (code, {class of before: grade}); class: error, warning, pending, note
MAP = {
    "P-2": ("FILES.sheet", {}),
    "P-3": ("SYNC.source", {"warning": "margin", "pending": "stale", "note": "unchecked"}),
    "P-4": ("PARTS.stock", {"warning": "margin", "pending": "stale", "note": "unchecked"}),
    "P-5": ("PARTS.supplier", {}),
    "P-7": ("GEO.hole", {"warning": "margin", "note": "unknown"}),
    "P-8": ("GEO.formed", {"note": "unknown"}),
    "P-9": ("PARTS.footprint", {}),
    "P-10": ("SYNC.footprint", {"note": "unknown"}),
    "G-9": ("PARTS.verified", {}),
    "G-19": ("DOCS.quote", {}),
    "G-20": ("DOCS.ref", {"warning": "margin", "draft": "draft"}),
    "G-21": ("DOCS.need", {"draft": "draft"}),
    "G-22": ("DOCS.evidence", {"draft": "draft"}),
    "G-23": ("DOCS.draft", {"draft": ""}),
    "scripts": ("SYNC.scripts", {"warning": "margin", "note": "unchecked"}),
    "agents": ("SYNC.agents", {}),
    # the gate's rows of stages S, L, F
    "S-2": ("SYNC.schematic", {}), "L-1": ("SYNC.pcb", {}), "L-2": ("GEO.copper", {}), "L-3": ("GEO.drc", {}),
    "L-4": ("SYNC.footprint", {}), "L-5": ("GEO.width", {}), "L-7": ("SYNC.plan", {}), "L-8": ("GEO.mark", {}),
    "L-9": ("GEO.hole", {}), "L-10": ("SYNC.footprint", {}), "L-11": ("GEO.loop", {}), "L-12": ("SYNC.plan", {}),
    "L-13": ("GEO.spacing", {}), "L-14": ("GEO.spacing", {}), "L-15": ("GEO.pour", {}), "L-16": ("GEO.ring", {}),
    "L-17": ("GEO.silk", {}), "L-18": ("GEO.spacing", {}), "L-19": ("GEO.silk", {}), "L-20": ("SYNC.plan", {}),
    "F-1": ("SYNC.bom", {}), "F-2": ("PARTS.stock", {}), "F-3": ("SYNC.cpl", {}), "F-4": ("FILES.manifest", {}),
    "F-5": ("FILES.set", {}), "F-6": ("FILES.order", {}),
}
# a report of before that goes to another code than its check's: (check ID, class, words in the message) -> code/grade
SPECIAL = [
    ("P-7", "pending", "lead", ("PARTS.fact", "lead")),
    ("G-9", "pending", "neither an LCSC part nor an EasyEDA device", ("PARTS.verified", "device")),
    ("G-9", "waived", "neither an LCSC part nor an EasyEDA device", ("PARTS.verified", "device")),
    ("L-16", None, "hole-to-hole", ("GEO.spacing", "")),
]
PLACE = re.compile(r"^([A-Za-z][\w.+-]*?)(?:[:\s(]|$)")


def code_of(old, cls, msg=""):
    """(code, grade) of a report of before: its check ID, its class, its message."""
    for cid, c, words, out in SPECIAL:
        if cid == old and c in (None, cls) and words in msg:
            return out
    code, grades = MAP[old]
    return code, grades.get(cls, "")


def row_code(row):
    """The code of a row of the gate protocol (stages S, L, F, and the project's own): its check ID mapped, the row's
    result its severity; None for a row of a project check whose ID is its own."""
    if row.get("id") not in MAP:
        return None
    return code_of(row["id"], {"warn": "warning"}.get(row.get("result"), row.get("result")), row.get("check", ""))[0]


class Recorder:
    """The report interface of before (checks.Report), recording findings: error(), and the lists errors, pending,
    warnings, notes, waived, drafts – each append becomes a finding with its code and grade."""

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
        self.notes, self.waived, self.drafts = Into("note"), Into("waived"), Into("draft")

    def error(self, cid, msg, waive=None):
        if waive and cid in waive:
            self.add("waived", cid, msg, waive[cid])
        else:
            self.add("error", cid, msg)

    def add(self, cls, cid, msg, reason=""):
        code, grade = code_of(cid, cls, msg)
        m = PLACE.match(msg)
        f = Finding(code, self.stage, m.group(1) if m else cid, msg, grade=grade, old=cid, accepted=reason)
        if cls == "draft":
            f.data["draft"] = True
        self.findings.append(f)


def run(design, cfg):
    """The findings of the checks beyond the graph, for a project (cfg)."""
    from .. import checks, footprint, order, part, requirements, scripts, stock
    rec = Recorder()
    part.check(design, rec, cfg)
    if not checks.check_holes(design, rec, checks.footprint_geometry(design, cfg)):
        rec.notes.append(("P-7", "not run: no footprint geometry – edakit pcb dump once the parts are in the PCB, or "
                                 "edakit part import <LCSC> for the library's"))
    from ..pcb import move_notes
    rec.notes += [("P-7", note) for note in move_notes(cfg)]
    checks.check_formed(design, rec, cfg)
    if checks.has_footprint_data(cfg, design):
        footprint.check(design, rec, cfg)
    stock.check(design, rec, cfg)
    order.check(design, rec, cfg)
    checks.check_signoff(design, rec)
    if cfg.requirements:
        requirements.check(rec, cfg)
    for level, msg in scripts.findings(cfg):
        rec.add(level, "scripts", msg)
    for f in (scripts.agents(cfg).findings if cfg.agents else []):
        rec.add("error", "agents", f.msg)
    for f in rec.findings:
        f.stage = "G" if f.code.startswith(("DOCS.", "SYNC.scripts", "SYNC.agents")) else "P"
    return rec.findings
