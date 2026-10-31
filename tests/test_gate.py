"""The gate's decision: every reason for NOT RELEASED, and sign-offs only for their hash."""

import json
import re

import pytest

from edakit.release import gate

ALL = set("PGESLF")


def rows(*results):
    return [{"stage": "L", "id": f"L-{i}", "item": "main", "check": f"check {i}", "result": r} for i, r in enumerate(results)]


def signoff(manual=(), warnings=()):
    return {"manual": list(manual), "accept": list(warnings)}


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
    project.comp(g, "J1").pop("source")
    project.save_graph(g)
    assert gate.header(project.config())["state_sha256"] != h["state_sha256"]


SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="{w}" height="10"/></svg>\n'


def add_art(project, *names):
    """One [[silk.art]] in the board file per name; each SVG once in hardware/art/."""
    art = project.root / "hardware" / "art"
    art.mkdir(exist_ok=True)
    board = project.root / "hardware" / "boards" / "main.toml"
    text = board.read_text()
    for i, name in enumerate(names):
        if not (art / name).exists():
            (art / name).write_text(SVG.format(w=10))
        text += f'\n[[silk.art]]\nsvg = "hardware/art/{name}"\nx = {5 + 10 * i}\ny = 5\nwidth_mm = 4\n'
    board.write_text(text)
    return art


def test_layout_hash_covers_the_artwork(project):
    """The SVGs of [[silk.art]] are the layout's, each once after the board files however often it is placed: a
    changed motif voids the layout review like a changed board file, and the circuit's sign-offs keep counting."""
    art = add_art(project, "star.svg", "tree.svg", "star.svg")
    cfg = project.config()
    board = project.root / "hardware" / "boards" / "main.toml"
    assert gate.layout_files(cfg)[:3] == [board, art / "star.svg", art / "tree.svg"]
    assert gate.layout_files(cfg).count(art / "star.svg") == 1
    h = gate.header(cfg)
    (art / "tree.svg").write_text(SVG.format(w=5))
    h2 = gate.header(project.config())
    assert h2["layout_sha256"] != h["layout_sha256"]
    assert h2["state_sha256"] == h["state_sha256"]


def test_a_board_without_artwork_keeps_its_layout_hash(project):
    """Without [[silk.art]] the layout hash covers the same files in the same order as before the artwork joined it:
    the board file, then the footprint geometry beside it (step 1.8)."""
    cfg = project.config()
    assert gate.layout_files(cfg) == [project.root / "hardware" / "boards" / "main.toml",
                                      project.root / "hardware" / "boards" / "main.geometry.json"]


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


def test_without_a_sign_off_file_every_required_check_is_open(project):
    """No hardware/signoff.json at all: nothing is signed, and M-1, M-5 and M-6 are open as with a file that lacks them
    – a missing file must not let a release past its required checks."""
    (project.root / "hardware" / "signoff.json").unlink()
    loaded, notes = gate.load_signoff(project.config(), {"state_sha256": None, "layout_sha256": None})
    assert {m["id"]: m["done_by"] for m in loaded["manual"]} == {"M-1": None, "M-5": None, "M-6": None}
    assert any("signoff.json missing" in n for n in notes)
    d, reasons = gate.decide(rows("pass"), [], loaded, ALL, gate.STAGES)
    assert d == "NOT RELEASED" and all(sid in " ".join(reasons) for sid in ("M-1", "M-5", "M-6"))


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


def test_information_of_stages_p_and_g_in_the_protocol(project, monkeypatch):
    """A note of stage P or G – the example has GEO.hole without a footprint geometry and PARTS.stock without a stock snapshot – is
    listed at the end of section 2: information, which neither blocks nor needs acceptance; section 3 stays empty."""
    from edakit import catalog
    text = gate_run(project, monkeypatch)
    two = section(text, 2)
    assert two.startswith("Findings\n\nNo check failed.\n")
    listed = two.split("Information (does not block the release, needs no acceptance):\n\n")[1]
    assert f"- {catalog.label('GEO.hole')}: not run: no footprint geometry – edakit pcb dump once the parts" in listed
    assert f"- {catalog.label('PARTS.stock')}: no stock snapshot (hardware/stock.json) – edakit stock asks JLCPCB" in listed
    assert section(text, 3).strip() == "Warnings\n\nNone."


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


HEAD = {"state_sha256": "s", "layout_sha256": "l", "fab_sha256": "f"}


def signed(project, drop=()):
    """The example's sign-off file signed for HEAD, without the manual checks in drop."""
    path = project.root / "hardware" / "signoff.json"
    s = json.loads(path.read_text())
    s.update(HEAD)
    s["manual"] = [{**m, "done_by": "agent", "date": "2026-10-27"} for m in s["manual"] if m["id"] not in drop]
    path.write_text(json.dumps(s))
    return gate.load_signoff(project.config(), HEAD)


@pytest.mark.parametrize("sid, scope", [("M-1", "circuit"), ("M-5", "fab")])
def test_second_datasheet_check_and_layout_review_are_required(project, sid, scope):
    """M-1 and M-5 are conditions of every release, as M-6 is: a sign-off file without them gets them as open."""
    loaded, notes = signed(project, drop=(sid,))
    m = next(m for m in loaded["manual"] if m["id"] == sid)
    assert (m["phase"], m["scope"], m["done_by"]) == ("export", scope, None)
    assert any(f"{sid} is missing" in n for n in notes)
    d, reasons = gate.decide(rows("pass"), [], loaded, ALL, gate.STAGES)
    assert d == "NOT RELEASED" and sid in reasons[0]


def test_released_with_every_required_check_signed(project):
    loaded, notes = signed(project)
    assert {"M-1", "M-5", "M-6"} <= {m["id"] for m in loaded["manual"] if m["done_by"]}
    assert not any("missing" in n for n in notes)
    assert gate.decide(rows("pass"), [], loaded, ALL, gate.STAGES) == ("RELEASED", [])


# --- what the circuit hash covers, and acceptances bound to their parts (#66) --------------------------------------

def ignore(project, keys):
    toml = project.root / "edakit.toml"
    text = re.sub(r"hash_ignore = .*\n", "", toml.read_text())
    toml.write_text(text.replace("[release]\n", f"[release]\nhash_ignore = {json.dumps(keys)}\n"))
    return project.config()


def state(project):
    return gate.header(project.config())["state_sha256"]


def edit(project, change):
    g = project.graph()
    change(g)
    project.save_graph(g)


def test_without_hash_ignore_every_byte_counts(project):
    """The default hashes the files as they are: existing sign-offs keep their hash."""
    cfg = project.config()
    assert gate.state_hash(cfg) == gate.file_hash(cfg.root, gate.state_files(cfg))
    h = state(project)
    edit(project, lambda g: project.comp(g, "D2").update(notes="checked again"))
    assert state(project) != h


def test_hash_ignore_leaves_documentation_keys_out(project):
    ignore(project, ["notes"])
    h = state(project)
    edit(project, lambda g: project.comp(g, "D2").update(notes="checked again"))
    assert state(project) == h
    edit(project, lambda g: project.comp(g, "D2")["pins"].update({"2": "C"}))      # a pin is the circuit
    assert state(project) != h


def test_hash_ignore_in_the_parts_entries(project):
    ignore(project, ["verified", "sources"])
    h = state(project)
    part = project.part("C2297")
    part["verified"]["open"] = []
    part["sources"].append("datasheet p. 3 read again")
    project.save_part("C2297", part)
    assert state(project) == h
    part["limits"]["if_max_a"] = 0.02
    project.save_part("C2297", part)
    assert state(project) != h


def test_what_a_check_or_review_reads_stays_in_the_hash(project):
    """`purpose` (M-6) is hashed whole, and the simulation config byte by byte: its `sources` are the supplies."""
    ignore(project, ["notes", "sources", "note"])
    h = state(project)
    edit(project, lambda g: g["graph"]["purpose"].update(notes="a toy for small children"))
    assert state(project) != h
    h = state(project)
    sim = project.root / "hardware" / "sim.json"
    s = json.loads(sim.read_text())
    s["sources"]["J1"]["i_max_a"] = 1.0
    sim.write_text(json.dumps(s, indent=1))
    assert state(project) != h


def test_turning_hash_ignore_on_rehashes_the_signed_state(project):
    """The sign-off file signed the bytes; with hash_ignore the gate records old and new hash in `rehashed`, and the
    sign-offs keep counting – only when nothing else changed."""
    cfg = project.config()
    old = gate.state_hash(cfg)
    path = project.root / "hardware" / "signoff.json"
    s = json.loads(path.read_text())
    s["state_sha256"] = old
    s["manual"] = [{**m, "done_by": "agent", "date": "2026-10-27"} for m in s["manual"]]
    path.write_text(json.dumps(s, indent=2))
    cfg = ignore(project, ["notes"])
    new = gate.state_hash(cfg)
    assert new != old
    loaded, notes = gate.load_signoff(cfg, {"state_sha256": new, "layout_sha256": None})
    assert next(m for m in loaded["manual"] if m["id"] == "M-1")["done_by"] == "agent"
    assert any("rehashed" in n for n in notes)
    assert json.loads(path.read_text())["state_sha256"] == old          # read only unless the gate writes
    gate.load_signoff(cfg, {"state_sha256": new, "layout_sha256": None}, write=True)
    written = json.loads(path.read_text())
    assert written["state_sha256"] == new
    assert written["rehashed"][-1]["state_sha256"] == [old, new]
    assert written["rehashed"][-1]["hash_ignore"] == ["notes"]
    # a further key later: the old hash is the one with the list recorded last
    cfg = ignore(project, ["notes", "sources"])
    newer = gate.state_hash(cfg)
    loaded, _ = gate.load_signoff(cfg, {"state_sha256": newer, "layout_sha256": None}, write=True)
    assert json.loads(path.read_text())["rehashed"][-1]["state_sha256"] == [new, newer]


def test_no_rehash_when_the_circuit_changed_as_well(project):
    cfg = project.config()
    path = project.root / "hardware" / "signoff.json"
    s = json.loads(path.read_text())
    s["state_sha256"] = gate.state_hash(cfg)
    s["manual"] = [{**m, "done_by": "agent", "date": "2026-10-27"} for m in s["manual"]]
    path.write_text(json.dumps(s, indent=2))
    edit(project, lambda g: project.comp(g, "D2")["pins"].update({"2": "C"}))
    cfg = ignore(project, ["notes"])
    loaded, notes = gate.load_signoff(cfg, {"state_sha256": gate.state_hash(cfg), "layout_sha256": None}, write=True)
    assert next(m for m in loaded["manual"] if m["id"] == "M-1")["done_by"] is None
    assert "rehashed" not in json.loads(path.read_text())


WARN = {"stage": "L", "id": "GEO.hole", "item": "main", "check": "D2: hole tight at the lower tolerance", "result": "warn"}
ACCEPT = {"match": "GEO.hole main D2: hole tight*", "scope": "decision", "reason": "D-1", "by": "owner", "date": "2026-10-27"}


def accept(project, **extra):
    path = project.root / "hardware" / "signoff.json"
    s = json.loads(path.read_text())
    s["accept"] = [{**ACCEPT, **extra}]
    path.write_text(json.dumps(s, indent=2))
    return gate.load_signoff(project.config(), {"state_sha256": None, "layout_sha256": None})


def test_an_acceptance_naming_its_parts_counts_while_they_are_the_same(project):
    loaded, _ = accept(project, parts={"D2": "C2297"})
    assert gate.accepted(WARN, loaded) and not loaded["lapsed"]
    assert not any("warning" in r for r in gate.decide([WARN], [], loaded, ALL, gate.STAGES)[1])


def test_an_acceptance_lapses_when_its_part_changes(project, tmp_path):
    edit(project, lambda g: project.comp(g, "D2").update(lcsc="C2895549"))
    loaded, _ = accept(project, parts={"D2": "C2297"})
    assert not gate.accepted(WARN, loaded)
    assert loaded["lapsed"][0]["lapsed"] == "D2 is now C2895549"
    _, reasons = gate.decide([WARN], [], loaded, ALL, gate.STAGES)
    assert any("1 warning(s) not accepted" in r for r in reasons)
    edit(project, lambda g: g["graph"].update(components=[c for c in g["graph"]["components"]
                                                          if c["designator"] != "D2"]))
    loaded, _ = accept(project, parts={"D2": "C2297"})
    assert loaded["lapsed"][0]["lapsed"] == "D2 is not in the graph"


def test_without_parts_an_acceptance_works_as_before(project):
    edit(project, lambda g: project.comp(g, "D2").update(lcsc="C2895549"))
    loaded, _ = accept(project)
    assert gate.accepted(WARN, loaded) and not loaded["lapsed"]


def test_the_protocol_lists_a_lapsed_acceptance(project, monkeypatch):
    edit(project, lambda g: project.comp(g, "D2").update(lcsc="C2895549"))
    loaded, notes = accept(project, parts={"D2": "C2297"})
    cfg = project.config()
    out = cfg.reports / "run"
    out.mkdir(parents=True)
    head = {"time": "2026-10-27T10:00:00+01:00", "tester": "t", "graph_version": "1", "graph_date": "d",
            "graph_sha256": "g", "state_sha256": "s", "layout_sha256": "l", "git_commit": "c", "git_dirty": False,
            "tools": {"python": "3", "edakit": "0", "ngspice": "n", "easyeda-mcp-pro": "m"}}
    sim = {"checks": [], "scenarios": []}
    gate.write_protocol(cfg, out, head, [WARN], sim, loaded, notes, "NOT RELEASED", [], set("PGE"), gate.STAGES, {})
    text = (out / "protocol.md").read_text()
    assert "**not accepted** (lapsed: D2 is now C2895549" in text


STEP = re.compile(r"^\[ *\d+\.\d min\] step (\d+)/(\d+): ")


def test_gate_prints_step_n_of_m(project, monkeypatch, capsys):
    """Offline: one line per stage run, numbered 1..m before the stage – P/G, E and the project's own stages."""
    protocol = gate_run(project, monkeypatch)
    out = capsys.readouterr().out
    steps = [STEP.match(line) for line in out.splitlines() if STEP.match(line)]
    assert [(int(m[1]), int(m[2])) for m in steps] == [(1, 2), (2, 2)], out
    assert "P/G parts and graph" in out and "E simulation" in out
    assert "## 1 Stages" in protocol and "NOT RELEASED" in decision(protocol)   # protocol and exit (2) as before


def test_gate_counts_the_project_stages(project, monkeypatch, capsys):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + '\n[[release.stages]]\nid = "X"\nname = "firmware build"\n'
                    'cmd = ["python3", "-c", "print(1)"]\n')
    gate_run(project, monkeypatch)
    out = capsys.readouterr().out
    steps = [(m[1], m[2]) for m in map(STEP.match, out.splitlines()) if m]
    assert steps == [("1", "3"), ("2", "3"), ("3", "3")] and "step 3/3: X firmware build" in out


def test_gate_with_the_graph_outside_the_project(project, monkeypatch, tmp_path):
    """A path in edakit.toml may be absolute (handbook 10.1): the protocol names a graph outside the project in full."""
    shared = tmp_path / "shared" / "graph.json"
    shared.parent.mkdir()
    project.graph_file.rename(shared)
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace('graph = "hardware/graph.json"', f'graph = "{shared}"'))
    assert f"| Object | `{shared}` v" in gate_run(project, monkeypatch)
