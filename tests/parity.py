"""Parity of the restructuring (rules-at-scale.md, section 7): while the engines are built beside the checks of before,
both run on every design the tests check – led-bar and every fault seeded into it – and must yield the same findings
under the map old ID -> code: per check ID of before and severity the same number. The map is each finding's `old`.
Removed at the switch-over (step 5), with the checks of before."""

from collections import Counter

from edakit import catalog, engines, rules

# the checks of before the engines of step 2 replace
COVERED = {"G-1", "G-2", "G-3", "G-4", "G-5", "G-6", "G-8", "G-10", "G-11", "G-12", "G-13", "G-14", "G-15", "G-16",
           "G-17", "G-18", "G-24", "G-25", "P-1", "P-6", "P-11"}


def old_counts(rep):
    out = Counter()
    for sev, items in (("error", rep.errors), ("warning", rep.warnings), ("note", rep.notes),
                       ("pending", rep.pending), ("accepted", rep.waived)):
        for item in items:
            if item[0] in COVERED:
                out[(item[0], sev)] += 1
    return out


def new_counts(report):
    return Counter((f.old, "accepted" if f.accepted and f.severity != "pending" else f.severity)
                   for f in report.findings if f.old in COVERED)


def compare(design, cfg, rep):
    """'' when the engines agree with the report of before, else what differs."""
    new = engines.run(design, cfg)
    a, b = old_counts(rep), new_counts(new)
    lines = [f"{f.code}{'/' + f.grade if f.grade else ''}: no code or grade of the catalog" for f in new.findings
             if not catalog.code(f.code) or (f.grade and f.grade not in (catalog.code(f.code).get("grades") or {}))]
    if a != b:
        for key in sorted(set(a) | set(b)):
            if a[key] != b[key]:
                lines.append(f"{key[0]} {key[1]}: before {a[key]}, engines {b[key]}")
        olds = [f"  before {c}: {m}" for c, m in rep.errors + rep.warnings + rep.notes + rep.pending if c in COVERED]
        olds += [f"  before {c} (waived): {m}" for c, m, _ in rep.waived if c in COVERED]
        lines += olds + [f"  engines {f.old} -> {f.code} {f.severity}{' accepted' if f.accepted else ''}: {f.place}: "
                         f"{f.text}" for f in new.findings if f.old in COVERED]
    sim = rules.load_sim(cfg) if cfg else None
    before = {(h, place) for h, places in rules.open_hints(design, cfg, sim).items() for place in places}
    after = {(f.old, f.place) for f in new.findings if f.code.startswith("HINT.") and not f.accepted}
    if before != after:
        lines.append(f"hints: before {sorted(before - after)}, engines {sorted(after - before)}")
    return "\n".join(lines)


def compare_sim(out):
    """'' when the engine SIM agrees with the simulation checks of before: per check ID and scenario the same number of
    failures as errors."""
    unknown = [f["code"] + "/" + f.get("grade", "") for f in out.get("findings", []) if not catalog.code(f["code"])
               or (f.get("grade") and f["grade"] not in (catalog.code(f["code"]).get("grades") or {}))]
    if unknown:
        return "no code or grade of the catalog: " + ", ".join(unknown)
    a = Counter((c["id"], c["scenario"]) for c in out["checks"] if c["result"] == "fail")
    b = Counter((f["old"], f.get("scenario", "")) for f in out.get("findings", [])
                if f["severity"] == "error" and not f.get("accepted"))
    if a == b:
        return ""
    lines = [f"{k[0]} {k[1]}: before {a[k]}, engines {b[k]}" for k in sorted(set(a) | set(b)) if a[k] != b[k]]
    lines += [f"  before {c['id']} {c['scenario']} {c['item']} {c['check']}: {c['actual']} (expected {c['expected']})"
              for c in out["checks"] if c["result"] == "fail"]
    lines += [f"  engines {f['old']} -> {f['code']} {f.get('scenario', '')} {f['place']}: {f['text']}"
              for f in out.get("findings", []) if f["severity"] == "error"]
    return "\n".join(lines)
