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

A key edakit does not know is an error, as in edakit.toml. Whether the evidence passes is not evaluated here: edakit req
prints verify as written.
Exit codes: 0 = listed, 1 = error (no key, a file missing or not valid, an ID not in the files).
"""

from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PREFIX = {"need": "N", "requirement": "R"}           # [[need]] N-<n>, [[requirement]] R-<n>
KEYS = {"need": ("id", "text", "who", "source", "status", "reason"),
        "requirement": ("id", "text", "source", "from", "binding", "verify", "status", "reason")}
STATUS = ("draft", "accepted", "dropped")
BINDING = ("must", "should", "may")
VERIFY = ("rows", "signoff", "script", "accept")
ENTRY_ID = re.compile(r"[NR]-[1-9]\d*")


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
    lines.append("verify as written – the evidence is not evaluated. One chain: edakit req <ID> …")
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
        lines += labelled("", ["not evaluated – edakit req shows verify as written"], 10) if e.verify else []
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
    return lines + labelled("", ["not evaluated – edakit req shows verify as written"], 10)


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
