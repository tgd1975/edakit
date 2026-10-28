"""Project scripts resolve into one order with edakit's steps (handbook 8.6): the entries of the concept green, every
rule of the concept (docs/concepts/new/project-scripts.md, "Checking the TOML") seen red once – one fault per copy of
the reference project's entries in the example, and the fault finds exactly its rule."""

import argparse
import json

import pytest

from edakit import checks, scripts

# The reference project as the concept writes it, without review (decision 8); platine writes its sections into the
# tree's board file (decision 4). In the example the board main is named tree.
TREE = """
[firmware]

[scripts.platine]
kind   = "input"
cmd    = ["uv", "run", "hardware/easyeda/pcb_layout.py", "platine"]
about  = "Outline, holes, LED spots and fixed tracks are computed (fixed tracks: D-48)"
reads  = ["hardware/easyeda/bahnen_hinten.py", "versionen.toml"]
writes = ["board:tree"]

[scripts.baumgrafik]
kind   = "input"
cmd    = ["uv", "run", "hardware/easyeda/baum_druck.py", "svg"]
about  = "Tree artwork on the silkscreen, clear of pads and vias"
reads  = ["hardware/easyeda/pcb_layout.py", "footprints:tree", "routing:tree"]
writes = ["hardware/art/baum_vorne.svg", "hardware/art/baum_hinten.svg"]

[scripts.led-footprints]
kind   = "easyeda"
cmd    = ["uv", "run", "hardware/easyeda/led_footprints.py", "apply"]
about  = "The same polarity print on every LED footprint (owner, 2026-10-25)"
reads  = ["hardware/easyeda/pcb_layout.py"]
writes = ["footprints:tree"]

[scripts.firmware]
kind   = "derive"
cmd    = ["uv", "run", "hardware/graph/export_firmware.py"]
about  = "Pins, driver chain, channels and LED spots for the firmware"
reads  = ["firmware", "hardware/easyeda/pcb_layout.py"]
writes = ["firmware/board.py"]
check  = ["uv", "run", "hardware/graph/export_firmware.py", "--check"]

[scripts.sockel]
kind   = "derive"
cmd    = ["uv", "run", "hardware/sockel/sockel.py"]
about  = "Print model of the hill, fitting the board (D-36)"
reads  = ["hardware/sockel/huegel.py", "hardware/easyeda/pcb_layout.py", "footprints:tree"]
writes = ["hardware/sockel/stl/"]

[scripts.mechanik]
kind     = "check"
id       = "K"
cmd      = ["uv", "run", "hardware/sockel/sockel.py", "--pruefen"]
about    = "The tree fits the stand: slot, hill, cable, feet (D-36)"
phase    = "export"
advisory = true

[scripts.abnahme]
kind  = "check"
id    = "A"
cmd   = ["uv", "run", "simulator/pico/pruefstand.py", "mitlesen"]
about = "Camera test of every tree after delivery: each LED at its place, the chain in order"
phase = "acceptance"
"""
TREE_ART = ("hardware/art/baum_vorne.svg", "hardware/art/baum_hinten.svg")
REVIEW = """
[scripts.review]
kind   = "derive"
cmd    = ["uv", "run", "hardware/review/review_paket.py"]
about  = "Review package for circuit experts from the last released run"
reads  = ["graph", "parts", "release"]
writes = ["build/review/"]
"""

# The Christmas bell: kunst on the main board, tdisplay in the variant esp32
KUNST = """
[scripts.kunst]
kind   = "input"
cmd    = ["python", "hardware/art/make_art.py"]
about  = "Bell, greeting, star and snowflake as shapes for the silkscreen"
writes = ["hardware/art/bell.svg", "hardware/art/greeting.svg", "hardware/art/small_bell.svg",
          "hardware/art/chevron.svg", "hardware/art/star.svg", "hardware/art/snowflake.svg"]
"""
BELL_ART = ("hardware/art/bell.svg", "hardware/art/greeting.svg", "hardware/art/small_bell.svg",
            "hardware/art/chevron.svg", "hardware/art/star.svg")
TDISPLAY = """
[scripts.tdisplay]
kind   = "easyeda"
cmd    = ["python", "hardware/lib/tdisplay_device.py"]
about  = "Symbol and footprint of the LILYGO T-Display, rebuilt from the stand-in C18722937 (D-13)"
writes = ["footprints:esp32"]
"""


def resolve(project, entries="", board="main", art=()):
    """The example with these entries at the end of its edakit.toml, its board named `board`, and the SVGs `art`
    placed by [[silk.art]] in its board file."""
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("[boards.main]", f"[boards.{board}]") + entries)
    if art:
        f = project.root / "hardware" / "boards" / "main.toml"
        f.write_text(f.read_text() + "".join(f'\n[[silk.art]]\nsvg = "{a}"\nx = 20\ny = 20\nwidth_mm = 10\n'
                                             for a in art))
    return scripts.resolve(project.config())


def tree(project, extra="", base=TREE, art=TREE_ART):
    return resolve(project, base + extra, board="tree", art=art)


def entry(name, **fields):
    return f"\n[scripts.{name}]\n" + "".join(f"{k} = {json.dumps(v)}\n" for k, v in fields.items())


def before(order, *names):
    return all(order.index(a) < order.index(b) for a, b in zip(names, names[1:]))


# --- green ------------------------------------------------------------------------------------------------------------
def test_no_scripts_no_change(project):
    """Without [scripts] edakit's steps are the order, and nothing is found."""
    res = resolve(project)
    assert res.findings == []
    assert res.order == [step for step, _, _ in scripts.STEPS]


def test_reference_project_resolves(project):
    res = tree(project)
    assert res.findings == []
    o = res.order
    assert before(o, "platine", "edakit pcb place")                                   # the board file before its readers
    assert before(o, "edakit route all", "baumgrafik", "edakit silk apply")           # the artwork after the routing
    assert before(o, "edakit firmware", "firmware", "edakit check")                   # its stamp in edakit check
    assert before(o, "edakit pcb dump", "sockel", "edakit gate")                      # its stamp in the gate
    assert before(o, "mechanik", "edakit gate", "abnahme")                            # stage K; after delivery
    assert "led-footprints" not in o                                                  # easyeda: on command only


def test_bell_main_resolves(project):
    res = resolve(project, KUNST, art=BELL_ART)
    assert res.findings == [] and before(res.order, "kunst", "edakit silk apply")


def test_bell_esp32_resolves(project):
    res = resolve(project, TDISPLAY, board="esp32")
    assert res.findings == [] and "tdisplay" not in res.order


def test_easyeda_script_changes_the_project_library(project):
    """The concept's second finding: what led-footprints and tdisplay change is the project library."""
    res = resolve(project, TDISPLAY.replace("footprints:esp32", "project-library:esp32"), board="esp32")
    assert res.findings == []


def test_after_orders_a_post_processing(project):
    """beschriftung reads and writes the artwork after baumgrafik: it gets baumgrafik's version."""
    res = tree(project, entry("beschriftung", kind="input", cmd=["true"], about="the year into the tree artwork",
                              reads=["hardware/art/baum_vorne.svg"], writes=["hardware/art/baum_vorne.svg"],
                              after=["baumgrafik"]))
    assert res.findings == []
    assert before(res.order, "baumgrafik", "beschriftung", "edakit silk apply")


def test_after_orders_three_easyeda_scripts(project):
    """led_footprints.py changes the same LED footprints with apply, bohrungen and plus – as a chain."""
    res = tree(project, entry("led-bohrungen", kind="easyeda", cmd=["true"], about="hole and pad (D31)",
                              writes=["footprints:tree"], after=["led-footprints"])
               + entry("led-plus", kind="easyeda", cmd=["true"], about="+ at the anode", writes=["footprints:tree"],
                       after=["led-bohrungen"]))
    assert res.findings == []


def test_old_keys_are_a_check_and_the_sim_kind(project):
    """[[release.stages]] is a check of phase export before S, [project] sim_plugin the kind sim."""
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace('sim = "hardware/sim.json"',
                                             'sim = "hardware/sim.json"\nsim_plugin = "hardware/sim_plugin.py"')
                    + '\n[[release.stages]]\nid = "K"\nname = "Mechanics"\ncmd = ["true"]\n')
    res = scripts.resolve(project.config())
    assert res.findings == []
    assert before(res.order, "sim_plugin", "edakit sim") and before(res.order, "[[release.stages]] K", "edakit gate")


def test_input_writes_the_simulation_plugin(project):
    """edakit sim reads the plugin: an input may write it."""
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace('sim = "hardware/sim.json"',
                                             'sim = "hardware/sim.json"\nsim_plugin = "hardware/sim_plugin.py"'))
    res = resolve(project, entry("models", kind="input", cmd=["true"], about="models from the datasheet table",
                                 writes=["hardware/sim_plugin.py"]))
    assert res.findings == [] and before(res.order, "models", "sim_plugin", "edakit sim")


def test_a_folder_holds_the_files_in_it(project):
    """An input that writes the art folder writes the SVGs [[silk.art]] places from it."""
    res = resolve(project, KUNST.split("writes")[0] + 'writes = ["hardware/art/"]\n', art=BELL_ART)
    assert res.findings == [] and before(res.order, "kunst", "edakit silk apply")


# --- every rule seen red ------------------------------------------------------------------------------------------
X = {"cmd": ["true"], "about": "x"}
FAULTS = {
    # rule 1: kind is input, derive, easyeda or check, and the fields of that kind are there
    "kind unknown": (1, entry("x", kind="build", **X), "x: kind = \"build\""),
    "kind sim": (1, entry("x", kind="sim", **X), "x: kind = \"sim\" – the simulation plugin is [project] sim_plugin"),
    "field missing": (1, entry("x", kind="derive", cmd=["true"], writes=["build/x.json"]), "x: about missing"),
    "field of another kind": (1, entry("x", kind="derive", **X, writes=["build/x.json"], phase="export"),
                              "x: no field of a derive script: phase"),
    # rule 2: every data name is edakit's, a board name names a board of [boards]
    "board unknown": (2, entry("x", kind="derive", **X, reads=["routing:baum"], writes=["build/x"]),
                      "x: reads routing:baum – no board baum in [boards] (tree)"),
    "data name unknown": (2, entry("x", kind="derive", **X, reads=["library:tree"], writes=["build/x"]),
                          "x: reads library:tree – no data name of edakit"),
    "data name in another case": (2, entry("x", kind="derive", **X, reads=["Footprints:tree"], writes=["build/x"]),
                                  "x: reads Footprints:tree – no data name of edakit"),
    "data name without its board": (2, entry("x", kind="derive", **X, reads=["routing"], writes=["build/x"]),
                                    "x: reads routing – "),
    # rule 3: only edakit writes its data and graph, parts, sim; a script writes files, an easyeda script EasyEDA
    "script writes edakit's data": (3, entry("x", kind="derive", **X, writes=["routing:tree"]),
                                    "x: writes routing:tree – made by edakit route"),
    "script writes the graph by its path": (3, entry("x", kind="input", **X, writes=["hardware/graph.json"]),
                                            "x: writes hardware/graph.json (graph)"),
    "easyeda script writes a file": (3, entry("x", kind="easyeda", **X, writes=["hardware/art/x.svg"]),
                                     "x: writes hardware/art/x.svg – an easyeda script changes"),
    # rule 4: several writers of one file in a fixed order through after
    "two writers of one file": (4, entry("x", kind="input", **X, writes=["hardware/art/baum_vorne.svg"]),
                                "baumgrafik, x: both write hardware/art/baum_vorne.svg"),
    "two inputs write the board file": (4, entry("x", kind="input", **X, writes=["board:tree"]),
                                        "platine, x: both write board:tree"),
    # rule 5: what an input writes is read by an edakit step
    "input read by no step": (5, entry("x", kind="input", **X, writes=["build/x.json"]),
                              "x: an input, but no edakit step reads what it writes (build/x.json)"),
    # rule 6: what a derive writes is read by no edakit step
    "derive read by a step": (6, entry("x", kind="derive", **X, writes=["hardware/boards/main.toml"],
                                       after=["platine"]),
                              "x: a derive, but edakit pcb place needs what it writes (hardware/boards/main.toml)"),
    # rule 7: no cycle
    "input reads what comes later": (7, entry("x", kind="input", **X, reads=["routing:tree"], writes=["board:tree"],
                                              after=["platine"]),
                                     "x: in a cycle – x –[board:tree]→ edakit route all –[routing:tree]→ x"),
    "derive reads the release": (7, REVIEW, "review: in a cycle – review –[stamp]→ edakit gate –[release]→ review"),
    # rule 8: a check has an id of its own, a phase, and reads gerber:<b> only at "after F"
    "id of a gate stage": (8, entry("x", kind="check", **X, id="S", phase="export"), "x: id S is a stage of the gate"),
    "id of a sign-off": (8, entry("x", kind="check", **X, id="M-5", phase="export"), "x: id M-5 is a sign-off"),
    "id twice": (8, entry("x", kind="check", **X, id="K", phase="export"), "mechanik, x: the same id K"),
    "id of an old stage twice": (8, '\n[[release.stages]]\nid = "A"\nname = "Acceptance"\ncmd = ["true"]\n',
                                 "abnahme, [[release.stages]] A: the same id A"),
    "phase unknown": (8, entry("x", kind="check", **X, id="X", phase="later"), "x: phase = \"later\""),
    "check reads gerber before S": (8, entry("x", kind="check", **X, id="X", phase="export", reads=["gerber:tree"]),
                                    "x: reads gerber:tree, which the gate makes in stage F"),
    # rule 9: after names other registered scripts
    "after an unknown script": (9, entry("x", kind="derive", **X, writes=["build/x"], after=["baumgrafk"]),
                                "x: after names baumgrafk – there is no [scripts.baumgrafk]"),
    "after itself": (9, entry("x", kind="derive", **X, writes=["build/x"], after=["x"]), "x: after names itself"),
}


@pytest.mark.parametrize("fault", FAULTS)
def test_every_rule_seen_red(project, fault):
    rule, extra, msg = FAULTS[fault]
    res = tree(project, extra)
    assert {f.rule for f in res.findings} == {rule}, res.findings
    assert any(f.msg.startswith(msg) for f in res.findings), res.findings
    assert res.order == []                              # it does not resolve


def test_after_against_the_data_is_a_cycle(project):
    """rahmen reads baumgrafik's artwork, and baumgrafik runs after rahmen."""
    base = TREE.replace('writes = ["hardware/art/baum_vorne.svg", "hardware/art/baum_hinten.svg"]',
                        'writes = ["hardware/art/baum_vorne.svg", "hardware/art/baum_hinten.svg"]\nafter  = ["rahmen"]')
    res = tree(project, entry("rahmen", kind="input", **X, reads=["hardware/art/baum_vorne.svg"],
                              writes=["hardware/art/rahmen.svg"]), base=base, art=TREE_ART + ("hardware/art/rahmen.svg",))
    assert [(f.rule, f.msg) for f in res.findings] == [
        (7, "baumgrafik: in a cycle – baumgrafik –[hardware/art/baum_vorne.svg]→ rahmen –[after]→ baumgrafik")]


def test_three_easyeda_scripts_without_after(project):
    res = tree(project, entry("led-bohrungen", kind="easyeda", **X, writes=["footprints:tree"])
               + entry("led-plus", kind="easyeda", **X, writes=["footprints:tree"]))
    assert [(f.rule, f.msg) for f in res.findings] == [
        (4, "led-footprints, led-bohrungen, led-plus: all change footprints:tree, but after sets no order between them")]


def test_firmware_needs_its_table(project):
    """The contract exists only with [firmware]: without it the reference project's firmware reads nothing."""
    res = tree(project, base=TREE.replace("[firmware]\n", ""))
    assert [(f.rule, f.msg) for f in res.findings] == [
        (2, "firmware: reads firmware – edakit.toml has no [firmware]: edakit firmware writes no contract")]


def test_check_after_f_reads_gerber(project):
    res = tree(project, entry("x", kind="check", **X, id="X", phase="export", at="after F", reads=["gerber:tree"]))
    assert res.findings == [] and before(res.order, "edakit gate", "x")


def test_old_stage_without_its_fields(project):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + '\n[[release.stages]]\nid = "K"\ncmd = ["true"]\n')
    assert [(f.rule, f.msg) for f in scripts.resolve(project.config()).findings] == [
        (1, "[[release.stages]] K: name missing – the gate runs a project stage by id, name and cmd")]


# --- edakit check ---------------------------------------------------------------------------------------------------
def test_edakit_check_reports_the_findings(project, capsys, tmp_path):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + entry("x", kind="input", **X, writes=["build/x.json"]))
    out = tmp_path / "check.json"
    assert checks.main(project.config(), argparse.Namespace(release=False, json=str(out))) == 1
    text = capsys.readouterr().out
    assert "ERROR   scripts  x: an input, but no edakit step reads what it writes (build/x.json)" in text
    assert "handbook 8.6" in text and "; 1 errors, 3 waived" in text
    errors = json.loads(out.read_text())["errors"]
    assert [e["check"] for e in errors] == ["scripts"] and errors[0]["msg"].startswith("x: an input")


def test_edakit_check_with_entries_that_resolve(project, capsys):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + KUNST.replace("hardware/art/bell.svg", "hardware/art/x.svg"))
    f = project.root / "hardware" / "boards" / "main.toml"
    f.write_text(f.read_text() + '\n[[silk.art]]\nsvg = "hardware/art/x.svg"\nx = 20\ny = 20\nwidth_mm = 10\n')
    assert checks.main(project.config(), argparse.Namespace(release=False, json=None)) == 0
    assert "scripts" not in capsys.readouterr().out
