"""Needs and requirements in the notation of the circuit language (T.15, language 5.11): a file of
`[project] requirements` with the extension `.circuit`, read to the entries of edakit/requirements.py.

    read(path)   (entries, problems) – as requirements.read gives them for a TOML file
"""

from __future__ import annotations

from pathlib import Path

from . import model as m
from .reader import read as read_source

STATUS = ("draft", "accepted", "dropped")


def read(path):
    """(entries, problems) of a .circuit requirements file: the needs, then the requirements, each in file order."""
    from ..requirements import ENTRY_ID, Entry
    path = Path(path)
    src = read_source(path.read_text(encoding="utf-8"), path.name, "requirements")
    problems = [f"line {e.line}: {e.text}" for e in src.errors]
    needs, reqs, seen = [], [], set()
    for st in src.statements:
        if not isinstance(st, (m.Need, m.Requirement)):
            continue
        kind, prefix = ("need", "N") if isinstance(st, m.Need) else ("requirement", "R")
        bad = []
        if not (ENTRY_ID.fullmatch(st.id or "") and st.id[0] == prefix):
            bad.append(f"id {st.id!r} – a {kind} is {prefix}-<n>, e.g. {prefix}-1")
        if st.id in seen:
            bad.append("twice in this file")
        seen.add(st.id)
        if st.status and st.status not in STATUS:
            bad.append(f"status must be {', '.join(STATUS)}, not {st.status!r}")
        if st.status == "dropped" and not st.reason.strip():
            bad.append("dropped – it needs a reason")
        if not st.text.strip():
            bad.append("text is missing")
        if bad:
            problems += [f"{st.id or kind}: {b}" for b in bad]
            continue
        if kind == "need":
            needs.append(Entry("need", st.id, st.text, st.status or "draft", path, who=st.who, source=st.source,
                               reason=st.reason))
        else:
            reqs.append(Entry("requirement", st.id, st.text, st.status or "draft", path, source=st.source,
                              from_=list(st.frm), binding=st.binding, verify=list(st.verify), reason=st.reason,
                              subject=st.subject, require=st.require))
    return needs + reqs, problems
