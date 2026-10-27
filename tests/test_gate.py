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
    assert by_id["M-4"] is None             # scope layout, hash differs
    assert by_id["M-5"] is None             # scope fab: no stage F, no fab hash
    assert any("layout" in n for n in notes)


def test_hashes_change_with_the_graph(project):
    cfg = project.config()
    h1 = gate.header(cfg)["state_sha256"]
    g = project.graph()
    g["graph"]["version"] = "1.1"
    project.save_graph(g)
    assert gate.header(project.config())["state_sha256"] != h1


def test_each_hash_covers_its_files(project):
    """The table of contents and the schematic arrangement are in no hash, the board file is the layout's, the check
    settings in the graph are the circuit's."""
    h = gate.header(project.config())
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("quantity = 5", "quantity = 10"))
    (project.root / "hardware" / "schematic.toml").write_text("stub = 12\n")
    h2 = gate.header(project.config())
    assert (h2["state_sha256"], h2["layout_sha256"]) == (h["state_sha256"], h["layout_sha256"])
    board = project.root / "hardware" / "boards" / "main.toml"
    board.write_text(board.read_text().replace('C2 = "U1"', 'C2 = "U2"'))
    assert gate.header(project.config())["layout_sha256"] != h["layout_sha256"]
    g = project.graph()
    g["graph"]["checks"]["reverse_protect"] = []
    project.save_graph(g)
    assert gate.header(project.config())["state_sha256"] != h["state_sha256"]


def test_regulatory_review_is_required_also_when_the_file_lacks_it(project):
    path = project.root / "hardware" / "signoff.json"
    s = json.loads(path.read_text())
    s["manual"] = [m for m in s["manual"] if m["id"] != "M-6"]   # a sign-off file from before M-6
    path.write_text(json.dumps(s))
    loaded, notes = gate.load_signoff(project.config(), {"state_sha256": None, "layout_sha256": None})
    m6 = next(m for m in loaded["manual"] if m["id"] == "M-6")
    assert m6["phase"] == "export" and m6["scope"] == "circuit" and m6["done_by"] is None
    assert any("M-6 is missing" in n for n in notes)
    d, reasons = gate.decide(rows("pass"), [], loaded, ALL, gate.STAGES)
    assert d == "NOT RELEASED" and "M-6" in reasons[0]


def gate_run(project, monkeypatch):
    """`edakit gate` offline on the project; the protocol."""
    from edakit import cli
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["gate"]) == 2
    return (sorted((project.root / "build" / "release").iterdir())[-1] / "protocol.md").read_text()


def section(text, n):
    return text.split(f"## {n} ")[1].split("\n## ")[0]


def decision(text):
    return text.split("## 1 Stages")[0].split("| **Result** |")[1]


def no_open_points(project):
    for f in (project.root / "hardware" / "parts").glob("*.json"):
        e = json.loads(f.read_text())
        e["sources"] = [s for s in e.get("sources", []) if "assumption" not in s]
        if e.get("verified"):
            e["verified"]["open"] = []
        f.write_text(json.dumps(e, indent=1))


def test_open_datasheet_points_in_the_protocol(project, monkeypatch):
    """#42: section 6 ends with the open points of the datasheet sign-offs and the sources marked as an assumption –
    information only, the decision and its reasons stay."""
    text = gate_run(project, monkeypatch)
    six = section(text, 6)
    listed = six.split("**Open from the datasheets** (information – the release does not depend on it)\n")[1]
    assert ("- C2297 KT-0805G (D2–D9)\n  - open: VR not specified – 5 V assumed\n"
            "  - assumption: VR_max = 5 V: usual LED value, assumption without datasheet evidence\n") in listed
    assert "- C45783 CL21A226MAQNNNE (C2)\n  - open: DC bias loss at 5 V – affects buffering, not safety\n" in listed
    no_open_points(project)
    empty = gate_run(project, monkeypatch)
    assert decision(empty) == decision(text)
    assert "datasheets" not in section(empty, 6) and "- [ ] C" not in section(empty, 6)   # section 6 as before


def test_an_open_point_with_its_phase_is_a_manual_check(project, monkeypatch):
    """#42: {text, when: "acceptance"} is an unchecked line under "after delivery, per board", after M-4."""
    e = project.part("C2297")
    e["verified"]["open"] = [{"text": "VR not specified – 5 V assumed", "when": "acceptance"}]
    project.save_part("C2297", e)
    six = section(gate_run(project, monkeypatch), 6)
    after = six.split("**after delivery, per board**\n")[1].split("\n\n")[0]
    assert after.splitlines() == [
        "", "- [ ] M-4 Acceptance test of every delivered board: visual check, supply current, every LED, the button",
        "- [ ] C2297 KT-0805G (D2–D9): VR not specified – 5 V assumed"]
    assert "  - open, after delivery, per board: VR not specified – 5 V assumed\n" in six


def test_an_open_point_with_an_unknown_phase_is_named(project, monkeypatch):
    e = project.part("C2297")
    e["verified"]["open"] = [{"text": "VR not specified – 5 V assumed", "when": "delivery"}]
    project.save_part("C2297", e)
    six = section(gate_run(project, monkeypatch), 6)
    assert "- note: C2297: open point with when 'delivery' – known: order, acceptance; listed without a phase" in six
    assert "  - open: VR not specified – 5 V assumed\n" in six
