"""What the circuit must do: the requirements file and `edakit req`.

    edakit req              needs and requirements with status, binding and the evidence written in verify
    edakit req R-4 [N-2 …]  the chain of each: where a requirement comes from, the requirement, what verifies it – for a
                            need, the requirements that follow from it

[project] requirements in edakit.toml names the file, relative to edakit.toml – none by default: no key, no file, no
change. A path, "hardware/requirements.toml", or a list: a variant names the main project's file and its own,
["../../hardware/requirements.toml", "hardware/requirements.toml"]. An ID is unique across all of them – a variant
adds entries, it does not change the main project's.

The file describes the circuit only: what the boards must do and withstand. What firmware and mechanics must do stays
in the project's own documents. Two levels (handbook 3.6, 10.4):

    [[need]]          what someone wants, in their words
      id              N-<n>; stable – a dropped need keeps its number
      text            the need
      who             who wants it (optional)
      source          where it was found: a document, a decision (optional)
      status          draft | accepted | dropped – the agent drafts, only the user accepts; without the key a draft
      reason          why (required when dropped)
    [[requirement]]   one testable sentence: quantity, limit, condition
      id              R-<n>
      text            the sentence
      source          where it was found, as for a need (optional)
      from            where it comes from: needs N-…, decisions D-…, a standard, a sign-off (a list, optional)
      binding         must | should | may
      verify          what tests it, a list of { rows = "<pattern over 'ID scenario item check'>" } (rows of the gate
                      protocol, matched as accepted_warnings are), { signoff = "M-…" } (a manual check),
                      { script = "<name>" } (a project script), { accept = "<step>" } (a step of the acceptance test)
      status, reason  as for a need

A key edakit does not know is an error, as in edakit.toml. edakit req prints verify as written; it does not evaluate it.

With the key, the file is part of the circuit (handbook 3.6, 8.7):
  edakit check   G-20 every reference resolves (from, the IDs in verify), G-21 every accepted need has a requirement,
                 G-22 every requirement has evidence, G-23 drafts warn – also in the gate's stage G
  edakit gate    evaluates each requirement's evidence against its run (evaluate): rows – at least one protocol row
                 matches and none failed; signoff – the manual check is signed for the current hash of its scope and
                 its note names the requirement's ID; accept – M-4 is signed, the step is on the acceptance list of
                 section 6; script – not evaluated yet. must without passing evidence blocks the release, should is
                 a warning to accept, may informs; what is tested only after the export does not hold it up.
                 Section 11 of the protocol lists every requirement with its evidence and the result.
  circuit hash   the files count byte for byte, [release] hash_ignore does not reach into them: a changed
                 requirement voids M-1 and M-6, and the firmware contract shows drift.
A file named in the key that is missing or not valid stops edakit check and the gate as it stops edakit req.
Exit codes: 0 = listed, 1 = error (no key, a file missing or not valid, an ID not in the files).
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

PREFIX = {"need": "N", "requirement": "R"}           # [[need]] N-<n>, [[requirement]] R-<n>
KEYS = {"need": ("id", "text", "who", "source", "status", "reason"),
        "requirement": ("id", "text", "source", "from", "binding", "verify", "status", "reason")}
STATUS = ("draft", "accepted", "dropped")
BINDING = ("must", "should", "may")
VERIFY = ("rows", "signoff", "script", "accept")
ENTRY_ID = re.compile(r"[NR]-[1-9]\d*")
CHECKS = ("G-20", "G-21", "G-22", "G-23")   # run with [project] requirements only: edakit check, the gate's stage G
SIGNOFF_ID = re.compile(r"M-[1-9]\d*")      # a manual check of the sign-off file
CHECK_ID = re.compile(r"[PGESLF]-\d+")      # a check of the catalog, as a rows pattern may start with it
ACCEPTANCE = "M-4"                          # the manual check that works through the acceptance list (section 6)


class RequirementsError(Exception):
    pass


@dataclass
class Entry:
    kind: str                   # "need" or "requirement"
    id: str                     # N-<n> or R-<n>
    text: str
    status: str                 # draft (also without the key), accepted, dropped
    file: Path                  # the requirements file it stands in
    who: str = ""               # need: who wants it
    source: str = ""            # where it was found: a document, a decision
    from_: list = field(default_factory=list)    # requirement: the needs, decisions, standards, sign-offs it comes from
    binding: str = ""           # requirement: must, should, may
    verify: list = field(default_factory=list)   # requirement: [(kind, text)] – rows, signoff, script, accept
    reason: str = ""            # why; required when dropped


def _either(words):
    return f"{', '.join(words[:-1])} or {words[-1]}"


def _text(raw, key, required=False):
    """What is wrong with a text field: missing (when required), not a string, or blank (when required)."""
    if key not in raw:
        return [f"{key} is missing"] if required else []
    if not isinstance(raw[key], str):
        return [f"{key} must be a text"]
    return [f"{key} is missing"] if required and not raw[key].strip() else []


def _choice(raw, key, choices, required=True):
    if key not in raw:
        return [f"{key} is missing ({_either(choices)})"] if required else []
    return [] if raw[key] in choices else [f"{key} must be {_either(choices)}, not {raw[key]!r}"]


def _verify(raw):
    """verify: a list of tables with one kind each and its text."""
    items = raw.get("verify", [])
    if not isinstance(items, list):
        return ['verify must be a list, e.g. [{ rows = "E-3 * J1 *" }]']
    out = []
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            out.append(f'verify {i}: a table with one kind, e.g. {{ rows = "E-3 * J1 *" }}')
            continue
        unknown = [k for k in item if k not in VERIFY]
        out += [f"verify {i}: unknown kind '{k}' (known: {', '.join(VERIFY)})" for k in unknown]
        if not unknown and len(item) != 1:
            out.append(f"verify {i}: one kind per entry ({', '.join(VERIFY)}) – several are several entries")
        out += [f"verify {i}: {k} needs a text" for k, v in item.items() if k in VERIFY and not (
            isinstance(v, str) and v.strip())]
    return out


def _entry(kind, i, raw, path):
    """One [[need]] or [[requirement]]: (Entry or None, its ID or None, problems – each starting with the ID)."""
    prefix = PREFIX[kind]
    if not isinstance(raw, dict):
        return None, None, [f"[[{kind}]] {i}: must be a table"]
    eid = raw.get("id")
    eid = eid if isinstance(eid, str) and ENTRY_ID.fullmatch(eid) and eid[0] == prefix else None
    bad = [] if eid else [f"id is missing ({prefix}-<n>)" if "id" not in raw else
                          f"id {raw['id']!r} – a {kind} is {prefix}-<n>, e.g. {prefix}-1"]
    bad += [f"unknown key '{k}' (known: {', '.join(KEYS[kind])})" for k in raw if k not in KEYS[kind]]
    bad += _text(raw, "text", required=True) + _text(raw, "source") + _text(raw, "reason")
    bad += _choice(raw, "status", STATUS, required=False)            # without the key a draft
    reason = raw.get("reason", "")
    if raw.get("status") == "dropped" and isinstance(reason, str) and not reason.strip():
        bad.append("dropped – it needs a reason")
    if kind == "need":
        bad += _text(raw, "who")
    else:
        bad += _choice(raw, "binding", BINDING) + _verify(raw)
        refs = raw.get("from", [])
        if not isinstance(refs, list) or not all(isinstance(r, str) and r.strip() for r in refs):
            bad.append('from must be a list of texts, e.g. ["N-2", "D-8"]')
    where = eid or f"[[{kind}]] {i}"
    problems = [f"{where}: {b}" for b in dict.fromkeys(bad)]
    if problems:
        return None, eid, problems
    return Entry(kind, eid, raw["text"], raw.get("status", "draft"), Path(path), who=raw.get("who", ""),
                 source=raw.get("source", ""), from_=list(raw.get("from", [])), binding=raw.get("binding", ""),
                 verify=[next(iter(v.items())) for v in raw.get("verify", [])], reason=raw.get("reason", "")), eid, []


def read(path):
    """(entries, problems) of one requirements file: the entries without a problem – the needs, then the requirements,
    each in file order – and what is wrong, each problem starting with the entry's ID ([[need]] 3 without one)."""
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        return [], [f"not valid TOML: {e}"]
    problems = [f"unknown key '{k}' (known: {', '.join(PREFIX)})" for k in data if k not in PREFIX]
    entries, seen = [], set()
    for kind in PREFIX:
        items = data.get(kind, [])
        if not isinstance(items, list):
            problems.append(f"{kind} must be an array of tables: [[{kind}]]")
            continue
        for i, raw in enumerate(items, 1):
            entry, eid, bad = _entry(kind, i, raw, path)
            if eid and eid in seen:
                bad.append(f"{eid}: twice in this file")
            seen.add(eid)
            problems += bad
            if entry and not bad:
                entries.append(entry)
    return entries, problems


def load(cfg):
    """Every entry of the files in [project] requirements, in their order. RequirementsError with every problem,
    grouped by file; an ID is unique across the files."""
    entries, home, out = [], {}, []
    for path in cfg.requirements:
        name = cfg.relative(path)
        if not path.is_file():
            out.append(f"{name}: not found – named in [project] requirements")
            continue
        found, bad = read(path)
        for e in found:
            if e.id in home:
                bad.append(f"{e.id}: already in {home[e.id]}")
            home.setdefault(e.id, name)
        entries += found
        if bad:
            out.append(f"{name}:\n  " + "\n  ".join(bad))
    if out:
        raise RequirementsError("\n".join(out))
    return entries


def counts(entries):
    """'4 needs, 1 requirement', 'no needs, no requirements'."""
    def n(k, word):
        return f"{k} {word}{'s' if k != 1 else ''}" if k else f"no {word}s"
    needs = sum(e.kind == "need" for e in entries)
    return f"{n(needs, 'need')}, {n(len(entries) - needs, 'requirement')}"


def state(e):
    """'need, accepted', 'requirement, must, draft'."""
    return ", ".join(x for x in (e.kind, e.binding, e.status) if x)


def evidence(e):
    """verify as written, one item each – not evaluated."""
    return [f"{kind} {text}" for kind, text in e.verify] or ["none"]


def labelled(label, items, indent):
    """The first item after the label, the others below it."""
    head = " " * indent + label
    return [head + items[0], *(" " * len(head) + x for x in items[1:])]


NEED_COLUMN, REQUIREMENT_COLUMN = 18, 26     # where the text starts in the list: after ID, status (and binding)


def listing(cfg, entries):
    """Every file with its needs and requirements: ID, status, binding, text; who, source, from, verify as written,
    the reason."""
    lines = []
    for path in cfg.requirements:
        mine = [e for e in entries if e.file == path]
        needs, reqs = [e for e in mine if e.kind == "need"], [e for e in mine if e.kind == "requirement"]
        lines.append(f"{cfg.relative(path)}: {counts(mine)}")
        for e in needs:
            lines.append(f"  {e.id:<5} {e.status:<9} {e.text}")
            said = "; ".join(f"{k}: {v}" for k, v in (("who", e.who), ("source", e.source)) if v)
            lines += labelled("", [said], NEED_COLUMN) if said else []
            lines += labelled("reason: ", [e.reason], NEED_COLUMN) if e.reason else []
        lines += [""] if needs and reqs else []
        for e in reqs:
            lines.append(f"  {e.id:<5} {e.status:<9} {e.binding:<7} {e.text}")
            lines += labelled("source: ", [e.source], REQUIREMENT_COLUMN) if e.source else []
            lines += labelled("from: ", [", ".join(e.from_) or "–"], REQUIREMENT_COLUMN)
            lines += labelled("verify: ", evidence(e), REQUIREMENT_COLUMN)
            lines += labelled("reason: ", [e.reason], REQUIREMENT_COLUMN) if e.reason else []
        lines.append("")
    lines.append("verify as written – not evaluated here: the gate does (section 11 of its protocol). One chain: "
                 "edakit req <ID> …")
    return lines


def chain(cfg, entries, eid):
    """The chain of one entry, None when it is not in the files. A requirement: where it comes from, the requirement,
    what verifies it – where it was found first, if it says. A need: who and where, the need, the requirements that
    name it in from with their verify."""
    by_id = {e.id: e for e in entries}
    e = by_id.get(eid)
    if e is None:
        return None
    lines = [f"{e.id}  {state(e)} – {cfg.relative(e.file)}"]
    if e.kind == "requirement":
        refs = [f"{r}  {state(by_id[r])}: {by_id[r].text}" if r in by_id else
                f"{r}  not in the requirements file" if ENTRY_ID.fullmatch(r) else r for r in e.from_]
        lines += labelled(f"{'source':<8}", [e.source], 2) if e.source else []
        lines += labelled(f"{'from':<8}", refs or ["–"], 2)
        lines += labelled(f"{'text':<8}", [e.text], 2)
        lines += labelled(f"{'reason':<8}", [e.reason], 2) if e.reason else []
        lines += labelled(f"{'verify':<8}", evidence(e), 2)
        lines += labelled("", [NOT_HERE], 10) if e.verify else []
        return lines
    lines += [line for k, v in (("who", e.who), ("source", e.source)) if v for line in labelled(f"{k:<8}", [v], 2)]
    lines += labelled(f"{'text':<8}", [e.text], 2)
    lines += labelled(f"{'reason':<8}", [e.reason], 2) if e.reason else []
    follow = [r for r in entries if r.kind == "requirement" and eid in r.from_]
    if not follow:
        return lines + ["  leads to  nothing – no requirement names it in from"]
    lines.append("  leads to")
    for r in follow:
        lines.append(f"{' ' * 10}{r.id}  {state(r)}: {r.text}")
        lines += labelled("verify ", evidence(r), 12 + len(r.id))
    return lines + labelled("", [NOT_HERE], 10)


NOT_HERE = "not evaluated here – edakit req shows verify as written; the gate evaluates it (section 11 of its protocol)"


# --- G-20 to G-23: the file in edakit check and in the gate's stage G -------------------------------------------------

def manual_checks(cfg):
    """(the IDs of the manual checks a requirement may name, the sign-off file as messages name it): the sign-off
    file's, then the ones every release needs (the gate's REQUIRED). A file that cannot be read lists none."""
    from .release.gate import REQUIRED
    try:
        manual = json.loads(cfg.signoff.read_text(encoding="utf-8")).get("manual", [])
    except (OSError, ValueError, AttributeError):
        manual = []
    ids = [m["id"] for m in manual if isinstance(m, dict) and isinstance(m.get("id"), str)]
    return list(dict.fromkeys(ids + list(REQUIRED))), cfg.relative(cfg.signoff)


def unresolved(kind, text, cfg, catalog, signoffs):
    """Why an entry of verify does not resolve, or None. rows: a check ID the pattern starts with is a check of the
    catalog and not retired – a wildcard or a project stage's ID only the gate run can tell; signoff: a manual check
    of the sign-off file or a required one; script: a [scripts.<name>] of kind check or a [[release.stages]] id;
    accept: a step in words, nothing to resolve."""
    ids, name = signoffs
    if kind == "rows":
        first = (text.split() or [""])[0]
        if CHECK_ID.fullmatch(first) and first not in catalog:
            return f"{first} is not a check of the catalog"
        if CHECK_ID.fullmatch(first) and catalog[first].get("retired"):
            return f"{first} is retired (edakit rules {first})"
    elif kind == "signoff" and text not in ids:
        return f"no manual check {text} in {name} ({', '.join(ids)})"
    elif kind == "script":
        entry = cfg.scripts.get(text)
        stages = cfg.release.get("stages", [])
        stages = {st.get("id") for st in stages if isinstance(st, dict)} if isinstance(stages, list) else set()
        if isinstance(entry, dict) and entry.get("kind") != "check":
            return f"[scripts.{text}] is of kind {entry.get('kind')}; evidence comes from a check"
        if entry is None and text not in stages:
            return f"no [scripts.{text}] of kind check and no [[release.stages]] id {text} in {cfg.path.name}"
    return None


def check(rep, cfg):
    """G-20 to G-23 on the files of [project] requirements, into rep (checks.Report): every reference resolves – a need
    or requirement in from (N-…, R-…), a manual check in from (M-…), the IDs in verify –, a from that names a dropped
    entry warns (G-20); every accepted need is in from of a requirement that is not dropped (G-21); every requirement
    has evidence (G-22); a draft warns (G-23). A dropped entry is history: it is not checked. Messages start with the
    entry's ID. RequirementsError for a file that is missing or not valid – edakit check and the gate stop on it
    before they get here."""
    from . import rules
    entries = load(cfg)
    by_id = {e.id: e for e in entries}
    live = [e for e in entries if e.status != "dropped"]
    reqs = [e for e in live if e.kind == "requirement"]
    files = "the requirements file" + ("s" if len(cfg.requirements) > 1 else "")
    signoffs, catalog = manual_checks(cfg), rules.catalog()["checks"]
    for e in reqs:
        for ref in e.from_:
            target = by_id.get(ref)
            if ENTRY_ID.fullmatch(ref) and target is None:
                rep.errors.append(("G-20", f"{e.id}: from {ref} – not in {files}"))
            elif target is not None and target.status == "dropped":
                rep.warnings.append(("G-20", f"{e.id}: from {ref} – dropped: {target.reason}"))
            elif SIGNOFF_ID.fullmatch(ref) and ref not in signoffs[0]:
                rep.errors.append(("G-20", f"{e.id}: from {ref} – no manual check {ref} in {signoffs[1]} "
                                           f"({', '.join(signoffs[0])})"))
        for kind, text in e.verify:
            if why := unresolved(kind, text, cfg, catalog, signoffs):
                rep.errors.append(("G-20", f"{e.id}: verify {kind} {repr(text) if kind == 'rows' else text} – {why}"))
    for n in live:
        if n.kind == "need" and n.status == "accepted" and not any(n.id in r.from_ for r in reqs):
            rep.errors.append(("G-21", f"{n.id}: accepted, but no requirement names it in from"))
    rep.errors += [("G-22", f"{r.id}: no evidence – verify names nothing that tests it") for r in reqs if not r.verify]
    rep.warnings += [("G-23", f'{e.id}: a draft – the user has not approved it (status "accepted", or "dropped" with '
                              "a reason)") for e in live if e.status == "draft"]


# --- the gate: each requirement's evidence against the run (handbook 8.7) ---------------------------------------------

FAILED = ("fail", "advisory")   # a protocol row that did not pass – an advisory finding does not block, it failed still
FAILS = {"must": "fail", "should": "warn", "may": "info"}   # binding: what a requirement without passing evidence is
WORDS = {"pass": "passed", "later": "open after the export", "unevaluated": "not evaluated yet", "info": "information",
         "warn": "warning", "fail": "FAILED", "dropped": "dropped"}


@dataclass
class Result:
    entry: Entry                # the requirement
    items: list                 # per entry of verify: (kind, text, state, what) – state pass, fail, later, unevaluated
    state: str                  # pass, later, unevaluated, info, warn, fail (from the items and the binding), dropped


def names(note, rid):
    """The note of a manual check names the requirement: R-4, not R-40."""
    return re.search(rf"(?<![\w-]){re.escape(rid)}(?!\w)", str(note or "")) is not None


def _rows(pattern, protocol_rows, stages_run):
    """At least one protocol row matches ("ID scenario item check", as accepted_warnings match) and none failed."""
    from .release.gate import RESULT, key_of
    hits = Counter(r["result"] for r in protocol_rows if fnmatch(key_of(r), pattern))
    if not hits:
        first = (pattern.split() or [""])[0]
        stage = first[0] if CHECK_ID.fullmatch(first) and first[0] not in stages_run else None
        return "fail", "no row of this run matches" + (f" – stage {stage} did not run" if stage else "")
    n = sum(hits.values())
    counts = ", ".join(f"{hits[k]} {word}" for k, word in RESULT.items() if hits[k])
    return ("fail" if any(hits[k] for k in FAILED) else "pass"), f"{n} row{'s' if n != 1 else ''}: {counts}"


def _signoff(sid, rid, signoff):
    """The manual check is signed for the current hash of its scope – load_signoff leaves done_by only then – and its
    note names the requirement. Not so: failed in phase export, open after the export in a later phase."""
    from .release.gate import PHASES
    m = next((x for x in signoff.get("manual", []) if x.get("id") == sid), None)
    if m is None:
        return "fail", f"no manual check {sid} in the sign-off file"
    phase = m.get("phase", "export")
    by = f"signed by {m.get('done_by')} ({m.get('date')})"
    if not m.get("done_by"):
        what = "not signed for this state" if phase == "export" else "not signed yet"
    elif names(m.get("note"), rid):
        return "pass", f"{by}, its note names {rid}"
    else:
        what = f"{by}, but its note does not name {rid}"
    if phase == "export":
        return "fail", f"{what} (section 6)"
    return "later", f"{what} – {dict(PHASES).get(phase, phase)}"


def _accept(signoff):
    """An acceptance step passes once M-4 is signed; until then it is open after delivery – it never holds up the
    release."""
    m = next((x for x in signoff.get("manual", []) if x.get("id") == ACCEPTANCE), None)
    if m and m.get("done_by"):
        return "pass", f"{ACCEPTANCE} signed by {m['done_by']} ({m.get('date')})"
    why = "not signed yet" if m else "is not in the sign-off file"
    return "later", f"after delivery: {ACCEPTANCE} {why} (section 6)"


def evaluate(entries, protocol_rows, signoff, stages_run):
    """Every requirement against a gate run: per entry of verify (kind, text, state, what), and the requirement's
    state. protocol_rows: every row of the run, the simulation's included; signoff: as load_signoff returns it. Any
    item failed, or no evidence: the binding decides – must fail, should warn, may info; else a script: unevaluated
    (warns, does not block); else an item after the export: later; else pass. A dropped requirement is listed, not
    evaluated."""
    out = []
    for e in (e for e in entries if e.kind == "requirement"):
        if e.status == "dropped":
            out.append(Result(e, [], "dropped"))
            continue
        items = []
        for kind, text in e.verify:
            if kind == "rows":
                found = _rows(text, protocol_rows, stages_run)
            elif kind == "signoff":
                found = _signoff(text, e.id, signoff)
            elif kind == "accept":
                found = _accept(signoff)
            else:   # script: project scripts do not run in the gate yet
                found = ("unevaluated", "not evaluated yet – the gate runs no project scripts so far")
            items.append((kind, text, *found))
        states = {state for _, _, state, _ in items}
        state = (FAILS[e.binding] if not items or "fail" in states else
                 next((s for s in ("unevaluated", "later") if s in states), "pass"))
        out.append(Result(e, items, state))
    return out


def accepted(result, signoff):
    """The accepted warning of the sign-off file that covers a should requirement without passing evidence – matched
    over "R-3 <its text>" like any warning – or None."""
    from .release.gate import accepted as acceptance
    return acceptance({"id": result.entry.id, "check": result.entry.text}, signoff)


def reasons(results, signoff):
    """Why the gate does not release, from the requirements: must without passing evidence; should without it and
    not accepted."""
    must = [r.entry.id for r in results if r.state == "fail"]
    should = [r.entry.id for r in results if r.state == "warn" and not accepted(r, signoff)]
    out = [f"{len(must)} requirement(s) must without passing evidence: {', '.join(must)} (section 11)"] if must else []
    if should:
        out.append(f"{len(should)} requirement(s) should without passing evidence, not accepted: {', '.join(should)} "
                   "(section 11)")
    return out


VERDICT = {"pass": "passed", "fail": "**FAILED** – blocks the release", "info": "information – no passing evidence",
           "unevaluated": "**not evaluated yet** – does not block the release",
           "later": "open after the export – does not block the release"}
SHOWN = {"rows": "rows `{}`", "signoff": "signoff {}", "script": "script `{}`", "accept": "accept: {}"}


def verdict(result, signoff):
    """A requirement's result as section 11 writes it."""
    if result.state == "warn":
        a = accepted(result, signoff)
        return "**warning** – " + (f"accepted by {a.get('by')} ({a.get('date')}): {a.get('reason')}" if a
                                   else "**not accepted**")
    if result.state == "dropped":
        return f"dropped: {result.entry.reason}"
    return VERDICT[result.state]


def section(results, signoff, files):
    """Section 11 of the protocol, below its heading: every requirement with its evidence and the result."""
    lines = [f"From {', '.join(f'`{f}`' for f in files)}, each requirement with its evidence in this run (handbook "
             "8.7): `must` without passing evidence blocks the release, `should` is a warning to accept, `may` "
             "informs; what is tested only after the export – an acceptance step (section 6), a sign-off of a later "
             "phase – does not hold it up.\n"]
    for r in results:
        e = r.entry
        lines.append(f"- **{e.id}** {e.binding}, {e.status}: {e.text} → {verdict(r, signoff)}")
        lines += [f"  - {SHOWN[kind].format(text)} – {what}" for kind, text, _, what in r.items]
    return lines if results else lines + ["No requirements yet."]


def acceptance(results):
    """The acceptance steps, one unchecked line each with the requirement's ID, for the list after delivery (section
    6) that M-4 works through."""
    return [f"- [ ] {r.entry.id}: {text}" for r in results for kind, text, _, _ in r.items if kind == "accept"]


def summary(results):
    """One line for the gate's output: how many requirements passed, are open, failed …"""
    n = Counter(r.state for r in results)
    counts = ", ".join(f"{n[s]} {WORDS[s]}" for s in WORDS if n[s]) or "none"
    return f"requirements: {counts} (section 11 of the protocol)"


def main(cfg, args):
    if not cfg.requirements:
        print("edakit req: no [project] requirements in edakit.toml – name the file, e.g. "
              'requirements = "hardware/requirements.toml" (handbook 3.6)', file=sys.stderr)
        return 1
    try:
        entries = load(cfg)
    except RequirementsError as e:
        print(f"edakit req: {e}", file=sys.stderr)
        return 1
    if not args.ids:
        print("\n".join(listing(cfg, entries)))
        return 0
    chains = {eid: chain(cfg, entries, eid) for eid in args.ids}
    shown = ["\n".join(lines) for lines in chains.values() if lines is not None]
    if shown:
        print("\n\n".join(shown))
    missing = [eid for eid, lines in chains.items() if lines is None]
    for eid in missing:
        print(f"{eid}: not in the requirements file")
    return 1 if missing else 0
