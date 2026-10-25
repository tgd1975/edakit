"""The gate's decision: every reason for NOT RELEASED, and sign-offs only for their hash."""

import json

from edakit.release import gate

ALL = set("PGESLF")


def rows(*results):
    return [{"stage": "L", "id": f"L-{i}", "item": "main", "check": f"check {i}", "result": r} for i, r in enumerate(results)]


def signoff(manual=(), warnings=()):
    return {"manual": list(manual), "accepted_warnings": list(warnings)}


def test_released_when_everything_passes():
    d, reasons = gate.decide(rows("pass", "pass"), [], signoff(), ALL, gate.STAGES)
    assert d == "RELEASED" and not reasons


def test_failed_check():
    assert gate.decide(rows("pass", "fail"), [], signoff(), ALL, gate.STAGES)[0] == "NOT RELEASED"


def test_warning_needs_acceptance():
    r = rows("warn")
    assert gate.decide(r, [], signoff(), ALL, gate.STAGES)[0] == "NOT RELEASED"
    ok = signoff(warnings=[{"match": "L-0 main check 0", "scope": "decision", "reason": "D-1", "by": "x", "date": "y"}])
    assert gate.decide(r, [], ok, ALL, gate.STAGES)[0] == "RELEASED"


def test_open_manual_check_of_phase_export_blocks():
    m = [{"id": "M-1", "phase": "export", "done_by": None}, {"id": "M-2", "phase": "order", "done_by": None}]
    d, reasons = gate.decide(rows("pass"), [], signoff(m), ALL, gate.STAGES)
    assert d == "NOT RELEASED" and "M-1" in reasons[0] and "M-2" not in reasons[0]


def test_missing_stage_blocks():
    d, reasons = gate.decide(rows("pass"), [], signoff(), set("PGE"), gate.STAGES)
    assert d == "NOT RELEASED" and "S (Schematic)" in reasons[0]


def test_signoff_counts_only_for_its_hash(project):
    cfg = project.config()
    path = project.root / "hardware" / "signoff.json"
    s = json.loads(path.read_text())
    s["state_sha256"] = "abc"
    s["layout_sha256"] = "def"
    for m in s["manual"]:
        m["done_by"] = "agent"
    path.write_text(json.dumps(s))
    loaded, notes = gate.load_signoff(cfg, {"state_sha256": "abc", "layout_sha256": "OTHER"})
    by_id = {m["id"]: m["done_by"] for m in loaded["manual"]}
    assert by_id["M-1"] == "agent"          # scope circuit, hash matches
    assert by_id["M-5"] is None             # scope layout, hash differs
    assert any("layout" in n for n in notes)


def test_hashes_change_with_the_graph(project):
    cfg = project.config()
    h1 = gate.header(cfg)["state_sha256"]
    g = project.graph()
    g["graph"]["version"] = "1.1"
    project.save_graph(g)
    assert gate.header(project.config())["state_sha256"] != h1
