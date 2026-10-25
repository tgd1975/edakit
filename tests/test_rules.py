"""The rule catalog: every check the code can report has an entry, hints match the graph, findings get explained."""

import argparse
import json
import re
from pathlib import Path

from edakit import checks, rules
from edakit.design import Design
from edakit.release import gate

CODE = Path(rules.__file__).parent


def ids_in_code():
    found = set()
    for f in CODE.rglob("*.py"):
        found |= set(re.findall(r'"([PGESLF]-\d+)"', f.read_text(encoding="utf-8")))
    return found


def test_every_check_of_the_code_is_in_the_catalog():
    assert ids_in_code() - set(rules.catalog()["checks"]) == set()


def test_catalog_entries_are_complete():
    c = rules.catalog()
    for cid, e in {**c["checks"], **c["hints"]}.items():
        for key in ("title", "why", "fix", "sources"):
            assert e.get(key), (cid, key)
        assert all(isinstance(s, str) and s.strip() for s in e["sources"]), cid
    assert all(e.get("rule") for e in c["checks"].values())
    assert rules.entry("G-7")["retired"] and "G-7" not in checks.EXECUTED   # a retired number is not reused
    assert all(rules.entry(cid) and not rules.entry(cid).get("retired") for cid in checks.EXECUTED)


def test_hint_conditions_are_known():
    kinds = {"resistor", "capacitor", "inductor", "fuse", "diode", "led", "led_rgb", "npn", "pnp", "pmos", "nmos",
             "switch", "dip_switch", "button", "potentiometer", "battery_holder", "buzzer", "relay", "connector", "ic",
             "module"}
    for hid, h in rules.catalog()["hints"].items():
        assert h["when"] and set(h["when"]) <= {"kinds", "match"}, hid
        assert set(h["when"].get("kinds", [])) <= kinds, hid
        assert h["when"].get("match", "power_input") in rules.MATCHERS, hid


def test_label_names_the_check_with_words():
    assert rules.label("L-9") == "L-9 (hole fits the lead)"
    assert rules.label("K-1") == "K-1"   # a project's own stage: no entry, the ID stays as it is
    lines = rules.explain("G-14")
    assert lines[0].startswith("G-14 (USB-C sink termination): ")
    assert any(line.strip().startswith("why:") for line in lines)


def test_hints_of_the_example(project):
    cfg = project.config()
    d = Design.from_config(cfg)
    assert rules.matching_hints(d, cfg, rules.load_sim(cfg)) == {"H-1": ["J1"], "H-3": ["SW1"]}


def test_hint_taken_care_of_is_not_open(project):
    g = project.graph()
    g["graph"]["hints"] = {"H-3": "firmware debounces for 20 ms"}
    project.save_graph(g)
    cfg = project.config()
    assert list(rules.open_hints(Design.from_config(cfg), cfg)) == ["H-1"]


def test_notes_of_the_parts_database(project):
    part = project.part("C41407547")
    part["hints"] = ["module note"]
    part["pins"]["4"]["hint"] = "pin note"       # GP2, connected (LED_SDI)
    part["pins"]["1"]["hint"] = "unused pin"     # GP0 is nc: not shown
    project.save_part("C41407547", part)
    notes = rules.part_notes(Design.from_config(project.config()))
    assert ("U1", "module note") in notes and ("U1.4 (GP2)", "pin note") in notes
    assert not any(n == "unused pin" for _, n in notes)


def test_hints_command(project, capsys):
    g = project.graph()
    g["graph"]["hints"] = {"H-1": "C2 22 µF next to the module", "H-9": "typo"}
    project.save_graph(g)
    out_file = project.root / "hints.json"
    assert rules.main_hints(project.config(), argparse.Namespace(json=str(out_file))) == 0
    out = capsys.readouterr().out
    assert "H-3 (debounce buttons and switches) – SW1" in out
    assert "taken care of: C2 22 µF next to the module" in out and "H-9: in the graph's hints but not" in out
    data = json.loads(out_file.read_text())
    assert list(data["open"]) == ["H-3"] and data["handled"]["H-1"]["applies_to"] == ["J1"]


def test_rules_command(capsys):
    assert rules.main_rules(argparse.Namespace(ids=[])) == 0
    assert "G-12  strapping pins" in capsys.readouterr().out
    assert rules.main_rules(argparse.Namespace(ids=["G-11", "X-99"])) == 1
    out = capsys.readouterr().out
    assert "UM10204" in out and "X-99: not in the catalog" in out


def test_protocol_names_and_explains_the_findings(project, tmp_path):
    cfg = project.config()
    head = {"time": "2026-10-25T20:00:00+01:00", "tester": "test", "graph_version": "1.0", "graph_date": "2026-10-25",
            "graph_sha256": "a", "state_sha256": "b", "layout_sha256": "c", "git_commit": "abc", "git_dirty": False,
            "tools": {"python": "3", "edakit": "0", "ngspice": "ngspice-45", "easyeda-mcp-pro": "1.4.0"}}
    rows = [{"stage": "L", "id": "L-9", "item": "main", "check": "hole takes the lead", "result": "fail"},
            {"stage": "L", "id": "L-5", "item": "main", "check": "track width >= class width", "result": "warn"},
            {"stage": "K", "id": "K-1", "item": "Mechanics", "check": "door fits", "result": "fail"}]
    gate.write_protocol(cfg, tmp_path, head, rows, {"checks": [], "scenarios": []}, {"manual": []}, [], "NOT RELEASED",
                        [], set("PGESLF"), gate.STAGES, {})
    text = (tmp_path / "protocol.md").read_text()
    assert "| L | L-9 (hole fits the lead) |" in text and "| K | K-1 |" in text
    assert "`L-5 main track width >= class width` (track width)" in text
    rules_part = text.split("## 10 The rules behind the findings")[1]
    assert "**L-9 (hole fits the lead):" in rules_part and "**L-5 (track width):" in rules_part
    assert "K-1" not in rules_part
