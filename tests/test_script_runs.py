"""Project scripts run (handbook 8.6): edakit run runs registered scripts in the order edakit scripts shows and records
their stamps – an easyeda script only under the EasyEDA claim, a check is the gate's –; a step that reads what an input
writes runs the outdated inputs first (decision 7), reports a derive or easyeda script it does not run, and
--no-scripts runs none. After an easyeda script ran, hardware/scripts.lock records what it changed in EasyEDA and what
is from before it, until edakit pcb dump and edakit route all made them again. EasyEDA is never touched: the steps that
need it are fakes, the claim is a lock file of the test."""

import json
import re
import shutil
import sys
from pathlib import Path

import pytest
import test_script_stamps as ss
import test_scripts as ts

from edakit import lock, pcb, route, scripts, silk

LOCK, ABOUT, SVG, ART = ss.LOCK, ss.ABOUT, ss.SVG, ss.ART
LOG = "build/edakit/scripts"
FOOTER = f"output in {LOG}/<name>.log – commit {LOCK} with what the scripts wrote"
DRAW = f'''"""Bell, greeting, star and snowflake for the silkscreen -> SVG files in this folder."""
from pathlib import Path

for name in ("bell", "greeting", "small_bell", "chevron", "star", "snowflake"):
    (Path(__file__).parent / f"{{name}}.svg").write_text({SVG!r})
print("drawn")
'''
YEAR = ('from pathlib import Path\np = Path("hardware/art/bell.svg")\n'
        'p.write_text(p.read_text().replace("</svg>", "<!-- 2026 --></svg>"))\n')
DEVICE = 'from pathlib import Path\nPath("build").mkdir(exist_ok=True)\nPath("build/device.txt").write_text("1")\n'
RAHMEN = ts.entry("rahmen", kind="input", cmd=["python", "hardware/boards/rahmen.py"],
                  about="Revision and outline from the enclosure drawing", writes=["board:main"])
RAHMEN_PY = '''from pathlib import Path
p = Path("hardware/boards/main.toml")
rows = [row for row in p.read_text().splitlines() if not row.startswith("revision = ")]
p.write_text('revision = "B"\\n' + "\\n".join(rows) + "\\n")
'''
PINS = ts.entry("pins", kind="derive", cmd=["python", "docs/pins.py"], about="The pin table for the README",
                reads=["graph"], writes=["docs/pins.md"])
HEAD = "project scripts before edakit {} (handbook 8.6):"
CHANGE = ("project-library:main changed by lib ({when}) – from before it: the parts in the PCB, which keep their old copy "
          "until deleted and recreated (edakit pcb parts --write, then edakit pcb dump); the routing (edakit route all)")


@pytest.fixture(autouse=True)
def claim(tmp_path, monkeypatch):
    """The EasyEDA claim of the test: a lock file of its own, no Claude session unless a test names one, no script
    running."""
    monkeypatch.setenv("EDAKIT_LOCK_FILE", str(tmp_path / "easyeda-lock.json"))
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("EDAKIT_SCRIPT", raising=False)


def bell(project, entries=ts.KUNST, draw=DRAW):
    """The bell's kunst on the example (test_script_stamps.bell), its make_art.py drawing the six SVGs – none drawn
    yet; the further entries' scripts written."""
    cfg = ss.bell(project, entries)
    ss.write(project, "hardware/art/make_art.py", draw)
    ss.write(project, "hardware/art/year.py", YEAR)
    ss.write(project, "hardware/lib/device.py", DEVICE)
    ss.write(project, "hardware/boards/rahmen.py", RAHMEN_PY)
    ss.write(project, "docs/pins.py", 'from pathlib import Path\nPath("docs/pins.md").write_text("| pin |")\n')
    for a in ART:
        (project.root / a).unlink()
    return cfg


def drawn(project):
    return all((project.root / a).exists() for a in ART)


def stamps(project):
    f = project.root / LOCK
    return json.loads(f.read_text())["scripts"] if f.exists() else {}


def fake(monkeypatch, project, module, code=0):
    """The step's own work, EasyEDA left alone: what it was handed – its config, and whether the art was drawn."""
    seen = []

    def main(cfg, args):
        seen.append((cfg, drawn(project)))
        return code
    monkeypatch.setattr(module, "main", main)
    return seen


def ran(name, about, indent="  "):
    """The line of a script that ran: in a step's block indented, of edakit run not."""
    return re.compile(rf"{indent}{re.escape(name)} ran \(\d+\.\d s\) – {re.escape(about)}")


# --- edakit run -------------------------------------------------------------------------------------------------------
def test_edakit_run_runs_the_script_and_records_its_stamp(project, monkeypatch, capsys):
    bell(project)
    code, out = ss.edakit(project, monkeypatch, capsys, "run", "kunst")
    assert code == 0, out
    lines = out.splitlines()
    assert ran("kunst", ABOUT, "").fullmatch(lines[0]) and lines[1:] == [FOOTER], out
    assert drawn(project)
    assert stamps(project)["kunst"]["hashes"] == {"hardware/art/make_art.py": ss.sha(DRAW)}
    log = (project.root / LOG / "kunst.log").read_text()
    assert "cmd: python hardware/art/make_art.py" in log and "\ndrawn\n" in log and "\nexit 0 after " in log
    assert ss.check(project, capsys) == (0, [])


def test_python_is_edakits_own(project, monkeypatch, capsys):
    """Decision 6: python as the first word of cmd is the interpreter edakit runs in – the script imports edakit."""
    bell(project, draw="import sys\nimport edakit\nprint(sys.executable, edakit.__file__)\n" + DRAW)
    assert ss.edakit(project, monkeypatch, capsys, "run", "kunst")[0] == 0
    log = (project.root / LOG / "kunst.log").read_text()
    assert f"{sys.executable} {Path(scripts.__file__).parent / '__init__.py'}" in log


def test_a_failed_run_records_nothing_and_shows_its_output(project, monkeypatch, capsys):
    bell(project, draw='print("drawing the bell")\n1 / 0\n')
    code, out = ss.edakit(project, monkeypatch, capsys, "run", "kunst")
    assert code == 1
    assert re.search(rf"kunst failed \(exit 1, \d+\.\d s\) – nothing recorded; its output, also in {LOG}/kunst.log:",
                     out), out
    assert "  drawing the bell" in out and "  ZeroDivisionError: division by zero" in out
    assert not (project.root / LOCK).exists()
    assert "ZeroDivisionError" in (project.root / LOG / "kunst.log").read_text()


def test_a_run_that_does_not_write_what_it_names(project, monkeypatch, capsys):
    bell(project, draw='print("nothing drawn")\n')
    code, out = ss.edakit(project, monkeypatch, capsys, "run", "kunst")
    assert code == 1
    assert ("kunst ran, but hardware/art/bell.svg, hardware/art/greeting.svg, hardware/art/small_bell.svg, "
            "hardware/art/chevron.svg, hardware/art/star.svg, hardware/art/snowflake.svg are not there – its cmd does "
            "not write what writes names; nothing recorded") in out, out
    assert not (project.root / LOCK).exists()


def test_named_scripts_run_in_their_order(project, monkeypatch, capsys):
    """jahr writes the year into kunst's bell: named first, it still runs after kunst."""
    bell(project, ts.KUNST + ss.JAHR)
    code, out = ss.edakit(project, monkeypatch, capsys, "run", "jahr", "kunst")
    assert code == 0, out
    lines = out.splitlines()
    assert ran("kunst", ABOUT, "").fullmatch(lines[0]) and ran("jahr", "The year into the bell", "").fullmatch(
        lines[1]), out
    assert "<!-- 2026 -->" in (project.root / "hardware/art/bell.svg").read_text()
    assert set(stamps(project)) == {"kunst", "jahr"} and ss.check(project, capsys) == (0, [])


def test_a_script_still_outdated_after_its_run(project, monkeypatch, capsys):
    """jahr alone: it runs, and is still outdated while kunst never ran – edakit run says so, exit 2."""
    bell(project, ts.KUNST + ss.JAHR)
    ss.write(project, "hardware/art/bell.svg", SVG)
    code, out = ss.edakit(project, monkeypatch, capsys, "run", "jahr")
    assert code == 2
    assert "jahr still outdated: after kunst, which never ran – edakit run kunst jahr" in out, out


def test_edakit_run_refuses(project, monkeypatch, capsys):
    bell(project, ts.KUNST + ts.entry("lage", kind="check", cmd=["true"], about="The board fits", id="X",
                                      phase="export"))
    for argv, said in [
            (("nope",), "edakit run: no [scripts.nope] in edakit.toml (kunst, lage)"),
            (("lage",), "edakit run: lage is a check, phase export before S: the gate runs it – edakit run runs input, "
                        "derive and easyeda scripts")]:
        code, out = ss.edakit(project, monkeypatch, capsys, "run", *argv)
        assert code == 1 and said in out, out
    monkeypatch.setenv("EDAKIT_SCRIPT", "kunst")              # kunst's own cmd calls edakit run kunst
    code, out = ss.edakit(project, monkeypatch, capsys, "run", "kunst")
    assert code == 1 and "edakit run: kunst is running – it does not run itself" in out
    monkeypatch.delenv("EDAKIT_SCRIPT")
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + ts.entry("x", kind="input", **ts.X, writes=["build/x.json"]))
    code, out = ss.edakit(project, monkeypatch, capsys, "run", "kunst")
    assert code == 1 and ("edakit run: the entries do not resolve into one order – edakit check names what keeps "
                          "them; nothing ran") in out
    assert not drawn(project) and not (project.root / LOCK).exists()


# --- an easyeda script: under the EasyEDA claim, and what it changed ----------------------------------------------
def holds(session):
    with lock.state() as s:
        lock.claim(s, session, "route all")


def holder():
    with lock.state() as s:
        c = lock.valid_claim(s)
    return c and (c["chat"], c["note"])


def test_an_easyeda_script_runs_under_the_claim(project, monkeypatch, capsys):
    """Another session holds EasyEDA: lib does not run, exit 3 as edakit lock says. Free: edakit run claims it for
    the session, as every edakit command that touches EasyEDA does, and keeps it after the run."""
    bell(project, ts.KUNST + ss.LIB)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "me-session")
    holds("other-session")
    code, out = ss.edakit(project, monkeypatch, capsys, "run", "lib")
    assert code == 3 and "edakit run: edakit lock: EasyEDA is held by other-se since" in out and "nothing ran" in out
    assert not (project.root / "build/device.txt").exists() and not (project.root / LOCK).exists()
    with lock.state() as s:
        lock.release(s, "other-session")
    code, out = ss.edakit(project, monkeypatch, capsys, "run", "lib")
    assert code == 0, out
    assert ran("lib", "The module's footprint (D-13)", "").fullmatch(out.splitlines()[0]), out
    assert holder() == ("me-session", "edakit run lib")
    assert (project.root / "build/device.txt").exists() and "lib" in stamps(project)


@pytest.mark.parametrize("session, mode", [(None, None), ("me-session", "off")])
def test_without_a_claim_to_take(project, monkeypatch, capsys, session, mode):
    """In a terminal – no Claude session – and with [project] lock = "off" nothing is claimed, as for every edakit
    command (handbook 11.2): the script runs."""
    bell(project, ts.KUNST + ss.LIB)
    if session:
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", session)
    if mode:
        toml = project.root / "edakit.toml"
        toml.write_text(toml.read_text().replace('[project]\n', f'[project]\nlock = "{mode}"\n'))
    holds("other-session")
    assert ss.edakit(project, monkeypatch, capsys, "run", "lib")[0] == 0
    assert holder() == ("other-session", "route all") and (project.root / "build/device.txt").exists()


def when(project):
    at = json.loads((project.root / LOCK).read_text())["changed"]["project-library:main"]["at"]
    return at[:16].replace("T", " ")


def test_after_an_easyeda_script_the_lock_says_what_is_from_before(project, monkeypatch, capsys):
    """lib changed the project library: the parts in the PCB, their geometry and the routing are from before it, until
    edakit pcb dump of every part and edakit route all ran; a script that reads the library is outdated by it."""
    reads = ts.KUNST.replace("writes", 'reads  = ["project-library:main"]\nwrites')
    bell(project, reads + ss.LIB)
    assert ss.edakit(project, monkeypatch, capsys, "run", "kunst")[0] == 0
    assert ss.check(project, capsys) == (0, [
        f"WARNING scripts  lib never run: no stamp in {LOCK} – The module's footprint (D-13)",
        "NOTE    scripts  kunst: not compared – project-library:main has no offline hash"])
    code, out = ss.edakit(project, monkeypatch, capsys, "run", "lib")
    assert code == 0, out
    change = CHANGE.format(when=when(project))
    assert out.splitlines()[1] == "  " + change
    rec = json.loads((project.root / LOCK).read_text())["changed"]["project-library:main"]
    assert rec["script"] == "lib" and rec["from_before"] == ["footprints:main", "routing:main"] and rec["by"]
    assert scripts.data_hash(project.config(), "project-library:main") not in (None, scripts.ABSENT)
    assert ss.check(project, capsys) == (1, [f"ERROR   scripts  kunst outdated: project-library:main changed – {ABOUT}",
                                             f"WARNING scripts  {change}"])
    code, out = ss.edakit(project, monkeypatch, capsys, "scripts")
    assert code == 2 and change in out.splitlines()
    assert ss.edakit(project, monkeypatch, capsys, "run", "kunst")[0] == 0
    assert ss.check(project, capsys) == (0, [f"WARNING scripts  {change}"])

    # the steps that make them again – EasyEDA left alone: a dump of some parts is not one
    fake(monkeypatch, project, pcb)
    fake(monkeypatch, project, route, code=3)       # the routing is in the PCB, the import acknowledgement pending
    code, out = ss.edakit(project, monkeypatch, capsys, "pcb", "dump", "--ref", "C1")
    assert code == 0 and out == "" and ss.check(project, capsys)[1] == [f"WARNING scripts  {change}"]
    code, out = ss.edakit(project, monkeypatch, capsys, "pcb", "dump")
    assert code == 0 and out == (f"{LOCK}: footprints:main made again after project-library:main changed (lib) – "
                                 "from before it: the routing (edakit route all); commit the lock\n")
    assert ss.check(project, capsys)[1] == [
        f"WARNING scripts  project-library:main changed by lib ({when(project)}) – from before it: the routing "
        "(edakit route all)"]
    code, out = ss.edakit(project, monkeypatch, capsys, "route", "all")
    assert code == 3 and out == (f"{LOCK}: routing:main made again after project-library:main changed (lib) – "
                                 "nothing from before it any more; commit the lock\n")
    assert ss.check(project, capsys) == (0, [])         # kunst stays current: the library has not changed since
    rows = scripts.gate_rows(project.config())
    assert [r["result"] for r in rows] == ["pass", "pass"]


def test_the_change_names_what_is_made_from_the_parts_and_the_routing(project, monkeypatch, capsys):
    """The artwork of the reference project reads footprints and routing: the change names it with the parts and the
    routing it is made from – its stamp tells it outdated once pcb dump and route all made them again."""
    bell(project, ts.KUNST.replace("writes", 'reads  = ["footprints:main", "routing:main"]\nwrites') + ss.LIB)
    code, out = ss.edakit(project, monkeypatch, capsys, "run", "lib")
    change = CHANGE.format(when=when(project)) + "; and what is made from them: kunst"
    assert code == 0 and out.splitlines()[1] == "  " + change, out

    def said():
        return [m for level, m in scripts.findings(project.config()) if m.startswith("project-library:main")]
    assert said() == [change]
    fake(monkeypatch, project, pcb)
    fake(monkeypatch, project, route)
    ss.edakit(project, monkeypatch, capsys, "pcb", "dump")
    assert said() == [f"project-library:main changed by lib ({when(project)}) – from before it: the routing (edakit route "
                      "all); and what is made from them: kunst"]
    ss.edakit(project, monkeypatch, capsys, "route", "all")
    assert said() == []


def test_the_change_is_a_warning_of_the_gate(project, monkeypatch, capsys):
    bell(project, ts.KUNST + ss.LIB)
    assert ss.edakit(project, monkeypatch, capsys, "run", "kunst", "lib")[0] == 0
    rows = scripts.gate_rows(project.config())
    assert [(r["result"], r["check"]) for r in rows if r["result"] != "pass"] == [
        ("warn", CHANGE.format(when=when(project)))]


def test_a_stamp_by_hand_records_no_change(project, monkeypatch, capsys):
    """edakit scripts stamp records the run of a script run by hand – also long ago, when a project registers it: its
    change is in the PCB since. Only edakit run sees an easyeda script change EasyEDA."""
    bell(project, ts.KUNST + ss.LIB)
    ss.stamp(project, monkeypatch, capsys, "lib")
    assert "changed" not in json.loads((project.root / LOCK).read_text())
    assert scripts.data_hash(project.config(), "project-library:main") is None


# --- the steps run the outdated inputs they read first (decision 7) ------------------------------------------------
@pytest.mark.parametrize("action", ["apply", "preview"])
def test_silk_runs_the_art_first(project, monkeypatch, capsys, action):
    """silk apply places the art, silk preview shows it: kunst never ran – it runs first, then the step."""
    bell(project)
    seen = fake(monkeypatch, project, silk)
    code, out = ss.edakit(project, monkeypatch, capsys, "silk", action)
    assert code == 0 and [d for _, d in seen] == [True]
    lines = out.splitlines()
    assert lines[0] == HEAD.format(f"silk {action}") and ran("kunst", ABOUT).fullmatch(lines[1]), out
    assert lines[2:] == ["  " + FOOTER]
    assert ss.check(project, capsys) == (0, [])
    code, out = ss.edakit(project, monkeypatch, capsys, "silk", action)
    assert code == 0 and out == "" and len(seen) == 2              # current: nothing to run, nothing said


def test_pcb_plan_runs_what_writes_the_board_file(project, monkeypatch, capsys):
    """rahmen writes the board file, kunst the art: pcb plan reads the board file only – and the one rahmen wrote."""
    bell(project, ts.KUNST + RAHMEN)
    seen = fake(monkeypatch, project, pcb)
    code, out = ss.edakit(project, monkeypatch, capsys, "pcb", "plan")
    assert code == 0 and len(seen) == 1
    assert seen[0][0].board("main").revision == "B"          # the step's config read after rahmen ran
    assert ran("rahmen", "Revision and outline from the enclosure drawing").fullmatch(out.splitlines()[1]), out
    assert "kunst" not in out and not drawn(project)


@pytest.mark.parametrize("argv, step", [(("pcb", "place"), "pcb place"), (("pcb", "parts"), "pcb parts"),
                                        (("pcb", "apply"), "pcb apply"), (("route", "all"), "route all")])
def test_the_steps_that_read_the_board_file(project, monkeypatch, capsys, argv, step):
    bell(project, ts.KUNST + RAHMEN)
    seen = fake(monkeypatch, project, pcb if argv[0] == "pcb" else route)
    code, out = ss.edakit(project, monkeypatch, capsys, *argv)
    assert code == 0 and seen[0][0].board("main").revision == "B"
    assert out.splitlines()[0] == HEAD.format(step) and "rahmen ran" in out


@pytest.mark.parametrize("argv", [("pcb", "dump"), ("pcb", "nets"), ("pcb", "autolayout"), ("route", "dsn"),
                                  ("silk", "check")])
def test_the_other_actions_run_no_script(project, monkeypatch, capsys, argv):
    bell(project, ts.KUNST + RAHMEN)
    fake(monkeypatch, project, pcb if argv[0] == "pcb" else route if argv[0] == "route" else silk)
    assert ss.edakit(project, monkeypatch, capsys, *argv) == (0, "")
    assert not stamps(project)


def test_the_gate_runs_a_stale_input_first(project, monkeypatch, capsys):
    """kunst never ran: the gate runs it, then reads the art – stage G finds it current."""
    bell(project)
    code, out = ss.edakit(project, monkeypatch, capsys, "gate")
    assert code == 2                                                     # not released, as the example
    lines = out.splitlines()
    assert lines[0] == HEAD.format("gate") and ran("kunst", ABOUT).fullmatch(lines[1]), out
    assert drawn(project) and "kunst" in stamps(project)
    run = sorted((project.root / "build" / "release").iterdir())[-1]
    text = (run / "protocol.md").read_text()
    assert "kunst never run" not in text and "| G | scripts |" not in text


def test_inputs_run_in_their_order(project, monkeypatch, capsys):
    """jahr writes the year into kunst's bell: before silk apply kunst runs, then jahr."""
    bell(project, ts.KUNST + ss.JAHR)
    fake(monkeypatch, project, silk)
    code, out = ss.edakit(project, monkeypatch, capsys, "silk", "apply")
    lines = out.splitlines()
    assert code == 0 and ran("kunst", ABOUT).fullmatch(lines[1]) and ran("jahr", "The year into the bell").fullmatch(
        lines[2]), out
    assert ss.check(project, capsys) == (0, [])


def test_a_derive_and_an_easyeda_script_are_reported_not_run(project, monkeypatch, capsys):
    bell(project, ts.KUNST + PINS + ss.LIB)
    seen = fake(monkeypatch, project, pcb)
    code, out = ss.edakit(project, monkeypatch, capsys, "pcb", "plan")
    assert code == 0 and len(seen) == 1
    assert out.splitlines() == [
        HEAD.format("pcb plan"),
        "  pins never run – a derive, no step runs it: edakit run pins",
        "  lib never run – an easyeda script, on command only: edakit run lib (under the EasyEDA claim)"]
    assert not (project.root / "docs/pins.md").exists() and not (project.root / "build/device.txt").exists()


def test_no_scripts(project, monkeypatch, capsys):
    """--no-scripts: the step runs with the files as they are, and says what it did not run."""
    bell(project)
    seen = fake(monkeypatch, project, silk)
    code, out = ss.edakit(project, monkeypatch, capsys, "silk", "apply", "--no-scripts")
    assert code == 0 and [d for _, d in seen] == [False] and not stamps(project)
    assert out.splitlines() == [HEAD.format("silk apply"),
                                "  kunst never run – not run (--no-scripts): the step reads what is there"]


def test_a_failed_input_stops_the_step(project, monkeypatch, capsys):
    bell(project, draw="1 / 0\n")
    seen = fake(monkeypatch, project, silk)
    code, out = ss.edakit(project, monkeypatch, capsys, "silk", "apply")
    assert code == 1 and seen == [] and not stamps(project)
    assert "kunst failed (exit 1" in out and "ZeroDivisionError" in out
    assert ("edakit silk apply: not run – kunst failed; fix it, or --no-scripts runs the step with the files as they "
            "are") in out


def test_entries_that_do_not_resolve_run_no_input(project, monkeypatch, capsys):
    """Without one order no input can run first: the step says so and runs – edakit check and the gate fail on it."""
    bell(project)
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + ts.entry("x", kind="input", **ts.X, writes=["build/x.json"]))
    seen = fake(monkeypatch, project, silk)
    code, out = ss.edakit(project, monkeypatch, capsys, "silk", "apply")
    assert code == 0 and [d for _, d in seen] == [False]
    assert out.splitlines() == [HEAD.format("silk apply"),
                                "  none run: the entries do not resolve into one order – edakit check names what keeps "
                                "them"]


def test_inside_a_script_no_step_runs_one(project, monkeypatch, capsys):
    """A script that calls an edakit step: the step runs no script – kunst would run itself."""
    bell(project)
    monkeypatch.setenv("EDAKIT_SCRIPT", "kunst")
    seen = fake(monkeypatch, project, silk)
    assert ss.edakit(project, monkeypatch, capsys, "silk", "apply") == (0, "") and [d for _, d in seen] == [False]


def test_an_input_of_another_board(project, monkeypatch, capsys):
    """vorne writes the board file of the board front: pcb plan of main does not run it, the gate does."""
    shutil.copy(project.root / "hardware/boards/main.toml", project.root / "hardware/boards/front.toml")
    vorne = RAHMEN.replace("rahmen", "vorne").replace("board:main", "board:front")
    bell(project, ts.KUNST + RAHMEN + vorne + '\n[boards.front]\ntitle = "Front"\ntemplate = "generated_front"\n'
                                              'schematic = "layout_front"\npcb = "front"\n'
                                              'file = "hardware/boards/front.toml"\n')
    ss.write(project, "hardware/boards/vorne.py", RAHMEN_PY.replace("main.toml", "front.toml"))
    fake(monkeypatch, project, pcb)
    code, out = ss.edakit(project, monkeypatch, capsys, "pcb", "plan", "--board", "main")
    assert code == 0 and "rahmen ran" in out and "vorne" not in out
    code, out = ss.edakit(project, monkeypatch, capsys, "gate")
    assert "vorne ran" in out and "rahmen" not in out and set(stamps(project)) == {"rahmen", "vorne", "kunst"}


def test_without_scripts_the_steps_say_nothing(project, monkeypatch, capsys):
    """No key, no change: the example has no [scripts] – the steps print what they printed before."""
    for module in (pcb, route, silk):
        fake(monkeypatch, project, module)
    for argv in (("pcb", "place"), ("pcb", "parts"), ("pcb", "plan"), ("pcb", "apply"), ("pcb", "dump"),
                 ("route", "all"), ("silk", "apply"), ("silk", "preview")):
        assert ss.edakit(project, monkeypatch, capsys, *argv) == (0, ""), argv
    code, out = ss.edakit(project, monkeypatch, capsys, "gate")
    assert "project scripts" not in out and not (project.root / LOCK).exists()
