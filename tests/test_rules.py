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


def test_the_requirement_checks_are_in_the_catalog_and_run_only_with_the_key():
    """G-20 to G-23 (handbook 3.6) are complete entries, not in EXECUTED – a project without [project] requirements
    runs the checks it ran before – and no check has the letter of a need N-… or a requirement R-…."""
    from edakit import requirements
    assert all(rules.entry(cid) and not rules.entry(cid).get("retired") for cid in requirements.CHECKS)
    assert not set(requirements.CHECKS) & set(checks.EXECUTED)
    assert not [cid for cid in rules.catalog()["checks"] if cid[0] in "NR"]


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


def test_read_back_from_a_chain(project):
    from test_sim import read_back
    read_back(project)                            # U2's SDO to GP7; the MCU drives U2's SDI, CLK, LE and OE
    cfg = project.config()
    assert rules.matching_hints(Design.from_config(cfg), cfg)["H-9"] == ["U2 SDO to U1 GP7"]
    part = project.part("C90107")
    part["pins"]["14"].update(out_edge="rising", t_pd_ns=[12, 30])     # TI SLVS695D 7.7, VDD 3 V: tPLH4/tPHL4
    project.save_part("C90107", part)
    assert rules.matching_hints(Design.from_config(cfg), cfg)["H-9"] == [
        "U2 SDO to U1 GP7 (changes 12–30 ns after the rising clock edge)"]
    part["pins"]["14"]["t_pd_ns"] = [None, 32]                         # a datasheet without a minimum (STP08CP05)
    project.save_part("C90107", part)
    assert rules.matching_hints(Design.from_config(cfg), cfg)["H-9"] == [
        "U2 SDO to U1 GP7 (changes ≤ 32 ns after the rising clock edge)"]


def test_read_back_through_a_series_resistor(project):
    from test_sim import read_back
    read_back(project)
    g = project.graph()
    project.net(g, "LED_SDO")["pins"].remove("U1.10")
    g["graph"]["components"].append({"designator": "R3", "type": "resistor", "lcsc": "C17414", "value": "10k",
                                     "pins": {"1": "1", "2": "2"}})
    project.net(g, "LED_SDO")["pins"].append("R3.1")
    g["graph"]["nets"].append({"name": "GP7_IN", "pins": ["R3.2", "U1.10"], "v": [0, 3.4]})
    project.save_graph(g)
    cfg = project.config()
    assert rules.matching_hints(Design.from_config(cfg), cfg)["H-9"] == ["U2 SDO to U1 GP7"]


def test_no_read_back_without_the_mcu_driving_the_part(project):
    from test_sim import read_back
    read_back(project)
    part = project.part("C90107")
    for num in ("2", "3", "4", "13"):             # SDI, CLK, LE, OE: no input the MCU drives – an output, not a chain
        part["pins"][num]["type"] = "passive"
    project.save_part("C90107", part)
    cfg = project.config()
    assert "H-9" not in rules.matching_hints(Design.from_config(cfg), cfg)


def test_hint_taken_care_of_is_not_open(project):
    g = project.graph()
    g["graph"]["hints"] = {"H-3": "firmware debounces for 20 ms"}
    project.save_graph(g)
    cfg = project.config()
    assert list(rules.open_hints(Design.from_config(cfg), cfg)) == ["H-1"]


def test_notes_of_the_parts_database(project):
    part = project.part("C41407547")
    part["hints"] = ["module note"]
    part["pins"]["4"]["hint"] = "pin note"       # GP2, connected (LED_CLK)
    part["pins"]["1"]["hint"] = "unused pin"     # GP0 is nc: not shown
    project.save_part("C41407547", part)
    notes = rules.part_notes(Design.from_config(project.config()))
    assert ("U1", "module note") in notes and ("U1.4 (GP2)", "pin note") in notes
    assert not any(n == "unused pin" for _, n in notes)


def test_hints_command(project, capsys):
    g = project.graph()
    g["graph"]["hints"] = {"H-1": "C2 22 µF next to the module", "H-99": "typo"}
    project.save_graph(g)
    out_file = project.root / "hints.json"
    assert rules.main_hints(project.config(), argparse.Namespace(json=str(out_file))) == 0
    out = capsys.readouterr().out
    assert "H-3 (debounce buttons and switches) – SW1" in out
    assert "taken care of: C2 22 µF next to the module" in out and "H-99: in the graph's hints but not" in out
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


# --- H-8 two supplies on one net (rule proposal #48) -----------------------------------------------------------------
def h8(project):
    cfg = project.config()
    return rules.matching_hints(Design.from_config(cfg), cfg, rules.load_sim(cfg)).get("H-8", [])


def second_supply(project, path="pmos"):
    """J1 moves to BAT; USB-C (block usb-c-sink, J2) feeds USB_VBUS, a Schottky D10 from there to VIN; the cells reach
    VIN through `path`: one AO3401A Q10 switched off by USB_VBUS ("pmos"), two back-to-back with a common source
    ("pair"), or a second Schottky ("diode")."""
    from edakit import block
    for lcsc in ("C15127", "C17414", "C8678"):
        project.use_library_part(lcsc)
    g = json.loads(project.graph_file.read_text())
    nets = {n["name"]: n for n in g["graph"]["nets"]}
    comps = g["graph"]["components"]
    nets["VIN"]["pins"].remove("J1.1")
    nets["GND"]["pins"].append("R10.2")
    comps += [{"designator": "R10", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}},
              {"designator": "D10", "type": "diode", "lcsc": "C8678", "pins": {"1": "K", "2": "A"}}]
    g["graph"]["nets"] += [{"name": "BAT", "pins": ["J1.1"], "v": [-5.5, 5.5]},
                           {"name": "USB_VBUS", "pins": ["R10.1", "D10.2"], "v": [0, 5.5]}]
    nets["VIN"]["pins"].append("D10.1")
    q = {"type": "transistor", "lcsc": "C15127", "pins": {"1": "G", "2": "S", "3": "D"}}
    if path == "diode":
        comps.append({"designator": "D11", "type": "diode", "lcsc": "C8678", "pins": {"1": "K", "2": "A"}})
        g["graph"]["nets"][-2]["pins"].append("D11.2")
        nets["VIN"]["pins"].append("D11.1")
    elif path == "pmos":
        comps.append({"designator": "Q10", **q})
        g["graph"]["nets"][-2]["pins"].append("Q10.3")
        g["graph"]["nets"][-1]["pins"].append("Q10.1")
        nets["VIN"]["pins"].append("Q10.2")
    else:
        comps += [{"designator": "Q10", **q}, {"designator": "Q11", **q}]
        g["graph"]["nets"][-2]["pins"].append("Q10.3")
        g["graph"]["nets"][-1]["pins"] += ["Q10.1", "Q11.1"]
        g["graph"]["nets"].append({"name": "Q_MID", "pins": ["Q10.2", "Q11.2"], "v": [-0.5, 5.5]})
        nets["VIN"]["pins"].append("Q11.3")
    project.save_graph(g)
    block.add(project.config(), "usb-c-sink", "USB", {"vbus": "USB_VBUS"})


def test_h8_one_supply_does_not_match(project):
    assert h8(project) == []


def test_h8_a_single_pmos_is_no_block(project):
    """The reference project's first concept (D-44): the cells behind one P-MOSFET feed through its body diode."""
    second_supply(project)
    assert h8(project) == ["BAT (J1 unblocked, J2)", "VIN (J1 unblocked, J2)"]   # Q10 conducts both ways
    cfg = project.config()
    assert checks.run(Design.from_config(cfg), cfg).errors == []     # no check sees it


def test_h8_back_to_back_pair_or_a_diode_blocks(project):
    second_supply(project, "pair")
    assert h8(project) == []


def test_h8_a_diode_in_each_path_blocks(project):
    second_supply(project, "diode")
    assert h8(project) == []


def test_h8_module_vbus_pin_on_the_rail(project):
    """The Pico 2's VBUS pin (USB of the PC, no diode) on +5V, where J1 feeds through D1."""
    g = project.graph()
    project.comp(g, "U1")["nc"].remove("40")
    project.net(g, "+5V")["pins"].append("U1.40")
    project.save_graph(g)
    assert h8(project) == ["+5V (J1, U1 unblocked)"]
    g["graph"]["hints"] = {"H-8": "J1 unplugged while flashing (operating rule)"}
    project.save_graph(g)
    cfg = project.config()
    assert "H-8" not in rules.open_hints(Design.from_config(cfg), cfg, rules.load_sim(cfg))


def test_h8_simulation_sources_and_fuses(project):
    """A second sim source on +5V counts as a supply; a fuse in its path is no block."""
    project.use_library_part("C495353")
    g = project.graph()
    project.comp(g, "U1")["nc"].remove("40")
    g["graph"]["components"].append({"designator": "F1", "type": "fuse", "lcsc": "C495353", "pins": {"1": "1", "2": "2"}})
    g["graph"]["nets"].append({"name": "VBUS_U1", "pins": ["U1.40", "F1.1"], "v": [0, 5.5]})
    project.net(g, "+5V")["pins"].append("F1.2")
    project.save_graph(g)
    sim_file = project.root / "hardware" / "sim.json"
    sim = json.loads(sim_file.read_text())
    sim["sources"]["U1"] = {"plus": "40", "minus": "38", "r_ohm": 0.3, "i_max_a": 0.5}
    sim_file.write_text(json.dumps(sim))
    assert h8(project) == ["+5V (J1, U1 unblocked)", "VBUS_U1 (J1, U1 unblocked)"]
