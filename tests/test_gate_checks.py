"""The project's checks in the gate (handbook 8.1, 8.6): a [scripts.<name>] of kind check runs as a stage of its own,
with its id – phase export before S, where [[release.stages]] run, or with at = "after F" after stage F, on this run's
manufacturing files; a failure blocks the release, with advisory = true it is listed only. Checks of phase order and
acceptance do not run in the gate: they are lines on the lists of section 6. A check has no stamp – it runs in every
gate. On the example, with the reference project's mechanik (stage K) and abnahme (A, after delivery) as models."""

import sys

import test_scripts as ts
from test_gate import decision, gate_run, section

from edakit import cli, scripts

# A project check of the tests: its verdict from its first argument; what it saw of the run's folder in its output.
FITS = '''\
"""The board fits the stand: slot, hill, cable, feet – the verdict comes from the first argument."""
import json, os, sys
print("run folder:", os.environ.get("EDAKIT_RUN", "none"))
if sys.argv[1:2] == ["exit"]:
    sys.exit(int(sys.argv[2]))
print(json.dumps([["K-1", "slot width", "1.62 mm", "1.6 to 1.7 mm", sys.argv[1] == "pass"]]))
'''
# A check after F: what this run's manufacturing files hold, read through EDAKIT_RUN.
ZIP = '''\
"""The Gerber ZIP of this gate run is there."""
import json, os, pathlib
path = pathlib.Path(os.environ["EDAKIT_RUN"]) / "fab" / "main" / "gerber_main.zip"
seen = path.read_text() if path.is_file() else "missing"
print(json.dumps([["X-1", "Gerber ZIP of this run", seen, "main", seen == "main"]]))
'''
ABOUT = "The board fits the stand: slot, hill, cable, feet (D-36)"


def write(project, path, text):
    p = project.root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def mechanik(verdict="pass", **more):
    """The reference project's mechanik as a check of the example: stage K, phase export."""
    return ts.entry("mechanik", kind="check", id="K", cmd=[sys.executable, "hardware/checks/fits.py", *verdict.split()],
                    about=ABOUT, phase="export", **more)


ABNAHME = ts.entry("abnahme", kind="check", id="A", cmd=["uv", "run", "simulator/pico/pruefstand.py", "mitlesen"],
                   about="Camera test of every board after delivery: each LED at its place", phase="acceptance")
PREVIEW = ts.entry("vorschau", kind="check", id="V", cmd=["python3", "hardware/checks/preview.py"],
                   about="JLCPCB's placement file of the order = the CPL of the release", phase="order")


def with_checks(project, entries):
    write(project, "hardware/checks/fits.py", FITS)
    write(project, "hardware/checks/zip.py", ZIP)
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + entries)
    assert scripts.resolve(project.config()).findings == []


def stage(text, sid):
    """The line of a stage in section 1."""
    return next(line for line in section(text, 1).splitlines() if line.startswith(f"| {sid} "))


def run_folder(project):
    return sorted((project.root / "build" / "release").iterdir())[-1]


# --- phase export, before S -------------------------------------------------------------------------------------------
def test_a_check_runs_in_the_gate_as_a_stage_of_its_own(project, monkeypatch, capsys):
    """Red before step 3.1: the gate ran [[release.stages]] only. mechanik runs between E and S, in the project folder,
    and gets the run's folder in EDAKIT_RUN; its output is stage_K.txt, its rows go into the protocol."""
    with_checks(project, mechanik())
    text = gate_run(project, monkeypatch)
    assert stage(text, "K") == f"| K mechanik | {ABOUT} | 1 | 0 | 0 | 0 | 0 | passed |"
    one = section(text, 1)
    assert one.index("| E Simulation") < one.index("| K mechanik") < one.index("| S Schematic")
    assert "| K | K-1 | mechanik | slot width | 1.62 mm | 1.6 to 1.7 mm | passed |" in section(text, 8)
    assert "K (mechanik)" not in decision(text)                                     # it ran
    run = run_folder(project)
    assert (run / "stage_K.txt").read_text().startswith(f"run folder: {run.resolve()}\n")
    assert "step 3/3: K mechanik" in capsys.readouterr().out


def test_a_failing_check_blocks_the_release(project, monkeypatch):
    with_checks(project, mechanik("fail"))
    text = gate_run(project, monkeypatch)
    assert stage(text, "K").endswith("| 0 | 1 | 0 | 0 | 0 | **failed** |")
    assert "| K | K-1 |  | mechanik | slot width | 1.62 mm | 1.6 to 1.7 mm |" in section(text, 2)
    assert "- 1 check(s) failed (section 2)" in decision(text)


def test_without_a_json_line_its_exit_code_counts(project, monkeypatch):
    with_checks(project, mechanik("exit 3"))
    text = gate_run(project, monkeypatch)
    cmd = f"{sys.executable} hardware/checks/fits.py exit 3"
    assert f"| K | K | mechanik | {cmd} | exit 3 | exit 0 | FAILED |" in section(text, 8)
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace('"exit", "3"', '"exit", "0"'))
    assert stage(gate_run(project, monkeypatch), "K").endswith("| 1 | 0 | 0 | 0 | 0 | passed |")


def test_a_check_that_cannot_run_fails(project, monkeypatch):
    with_checks(project, mechanik().replace(sys.executable, "/no/such/python"))
    text = gate_run(project, monkeypatch)
    assert "| K | K | mechanik | not runnable: [Errno 2] No such file or directory" in section(text, 8)
    assert "- 1 check(s) failed (section 2)" in decision(text)


def test_an_advisory_check_is_listed_and_does_not_block(project, monkeypatch):
    """The reference project's mechanik: the stand is adapted after delivery anyway (D-37)."""
    with_checks(project, mechanik("fail", advisory=True))
    text = gate_run(project, monkeypatch)
    assert stage(text, "K").endswith("| 0 | 0 | 0 | 0 | 0 | advisories (do not block) |")
    assert ("Advisories (do not block the release):\n\n- K-1 slot width: 1.62 mm (expected 1.6 to 1.7 mm)"
            in section(text, 2))
    assert "check(s) failed" not in decision(text)


def test_checks_run_in_the_order_edakit_scripts_shows(project, monkeypatch, capsys):
    """after orders two checks; [[release.stages]] run at the same place, as before."""
    lage = ts.entry("lage", kind="check", id="P2", cmd=[sys.executable, "hardware/checks/fits.py", "pass"],
                    about="The parts sit inside the stand's opening", phase="export", after=["mechanik"])
    with_checks(project, lage + mechanik() + '\n[[release.stages]]\nid = "R"\nname = "firmware build"\n'
                                             f'cmd = ["{sys.executable}", "-c", "print(1)"]\n')
    order = scripts.resolve(project.config()).order
    assert ts.before(order, "mechanik", "lage", "[[release.stages]] R", "edakit gate")
    gate_run(project, monkeypatch)
    out = capsys.readouterr().out
    assert [line.split(": ", 1)[1] for line in out.splitlines() if "] step " in line] == [
        "P/G parts and graph", "E simulation", "K mechanik", "P2 lage", "R firmware build"]


def test_a_release_stage_gets_the_run_folder_too(project, monkeypatch):
    """[[release.stages]] keep working as before – a check of phase export before S, with EDAKIT_RUN as well."""
    with_checks(project, '\n[[release.stages]]\nid = "R"\nname = "firmware build"\n'
                         f'cmd = ["{sys.executable}", "hardware/checks/fits.py", "pass"]\n')
    text = gate_run(project, monkeypatch)
    assert "| R | K-1 | firmware build | slot width | 1.62 mm | 1.6 to 1.7 mm | passed |" in section(text, 8)
    run = run_folder(project)
    assert (run / "stage_R.txt").read_text().startswith(f"run folder: {run.resolve()}\n")


def test_entries_that_do_not_resolve_run_no_check_of_theirs(project, monkeypatch):
    """edakit refuses entries that do not resolve: stage G fails and names why, mechanik does not run; a
    [[release.stages]] runs as before."""
    with_checks(project, mechanik() + '\n[[release.stages]]\nid = "R"\nname = "firmware build"\n'
                                      f'cmd = ["{sys.executable}", "-c", "print(1)"]\n')
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + ts.entry("x", kind="input", **ts.X, writes=["build/x.json"]))
    text = gate_run(project, monkeypatch)
    assert "| K mechanik" not in section(text, 1) and not (run_folder(project) / "stage_K.txt").exists()
    assert stage(text, "R").endswith("| passed |")
    assert "| G | scripts |  |  | x: an input, but no edakit step reads what it writes" in section(text, 2)


# --- phase export, after F --------------------------------------------------------------------------------------------
GERBER = ts.entry("gerber", kind="check", id="X", cmd=[sys.executable, "hardware/checks/zip.py"],
                  about="The Gerber ZIP of this run is there", phase="export", at="after F", reads=["gerber:main"])


def test_a_check_after_f_does_not_run_offline(project, monkeypatch):
    """Without stage F there are no manufacturing files of this run: the check is a stage not run, as S, L and F."""
    with_checks(project, GERBER)
    text = gate_run(project, monkeypatch)
    assert stage(text, "X") == "| X gerber | The Gerber ZIP of this run is there | 0 | 0 | 0 | 0 | 0 | not run |"
    one = section(text, 1)
    assert one.index("| F Manufacturing") < one.index("| X gerber")
    assert "- stages not run: S (Schematic), L (Board), F (Manufacturing), X (gerber)" in decision(text)
    assert not (run_folder(project) / "stage_X.txt").exists()


def easyeda_offline(monkeypatch):
    """Stages S and L/F without EasyEDA: the schematic agrees, fab.run writes the files to upload, each holding the
    board's name – as test_bought.py does."""
    from edakit import schematic
    from edakit.release import fab, gate

    def fab_run(cfg, board, out, offline=False, verbose=False):
        for pattern in gate.UPLOAD:
            f = out / board.name / pattern.format(b=board.name)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(board.name)
        return []
    monkeypatch.setattr(schematic, "check", lambda cfg, args: 0)
    monkeypatch.setattr(fab, "run", fab_run)
    monkeypatch.setattr(fab, "fab_layers", lambda d, board: {f"{board}.gbr": "0"})


def test_a_check_after_f_reads_the_runs_manufacturing_files(project, monkeypatch, capsys):
    with_checks(project, GERBER + mechanik())
    easyeda_offline(monkeypatch)
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["gate", "--easyeda"]) == 2                    # M-1, M-5, M-6 open, as in the example
    text = (run_folder(project) / "protocol.md").read_text()
    assert stage(text, "X").endswith("| 1 | 0 | 0 | 0 | 0 | passed |")
    assert "| X | X-1 | gerber | Gerber ZIP of this run | main | main | passed |" in section(text, 8)
    assert "stages not run" not in decision(text)
    steps = [line.split(": ", 1)[1] for line in capsys.readouterr().out.splitlines() if "] step " in line]
    assert steps == ["P/G parts and graph", "E simulation", "K mechanik", "S schematic against the graph",
                     "L/F board and manufacturing files: main", "X gerber"]


# --- phases order and acceptance: lines of section 6 ------------------------------------------------------------------
def test_checks_after_the_export_are_lines_of_section_6(project, monkeypatch):
    """abnahme can only run after delivery: it goes onto the acceptance list that M-4 works through; vorschau checks
    the order at JLCPCB, on the list M-2 works through. Neither runs in the gate."""
    with_checks(project, ABNAHME + PREVIEW)
    text = gate_run(project, monkeypatch)
    six = section(text, 6)
    order = six.split("**after uploading to the manufacturer, before paying**\n")[1].split("\n\n")[0]
    assert order.splitlines()[-1] == ("- [ ] V vorschau: JLCPCB's placement file of the order = the CPL of the release "
                                      "– `python3 hardware/checks/preview.py`")
    after = six.split("**after delivery, per board**\n")[1].split("\n\n")[0]
    assert after.splitlines()[1:] == [
        "- [ ] M-4 Acceptance test of every delivered board: visual check, supply current, every LED, the button",
        "- [ ] A abnahme: Camera test of every board after delivery: each LED at its place – "
        "`uv run simulator/pico/pruefstand.py mitlesen`"]
    assert "| A " not in section(text, 1) and "| V " not in section(text, 1)
    assert "stages not run: S (Schematic), L (Board), F (Manufacturing)\n" in decision(text)
    assert not list(run_folder(project).glob("stage_*.txt"))


def test_edakit_scripts_says_where_a_check_runs(project, monkeypatch, capsys):
    with_checks(project, mechanik() + GERBER + ABNAHME + PREVIEW)
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    cli.main(["scripts"])
    lines = capsys.readouterr().out.splitlines()
    assert "mechanik  check    no stamp – a check, phase export before S: the gate runs it" in lines
    assert ("gerber    check    no stamp – a check, phase export after F: the gate runs it with --easyeda, on the "
            "run's manufacturing files") in lines
    assert ("abnahme   check    no stamp – a check, phase acceptance: a line of the acceptance list after delivery "
            "(protocol section 6), M-4 works through it") in lines
    assert ("vorschau  check    no stamp – a check, phase order: a line of the list after uploading, before paying "
            "(protocol section 6), M-2 works through it") in lines


def test_without_checks_nothing_changes(project):
    """led-bar has no [scripts] and no [[release.stages]]: no check, no stage."""
    assert scripts.gate_checks(project.config()) == []


def test_the_checks_as_the_gate_takes_them(project):
    with_checks(project, ABNAHME + mechanik(advisory=True) + GERBER
                + '\n[[release.stages]]\nid = "R"\nname = "firmware build"\ncmd = ["make"]\n')
    got = {c.name: (c.id, c.title, c.phase, c.at, c.advisory) for c in scripts.gate_checks(project.config())}
    assert got == {"mechanik": ("K", "mechanik", "export", "before S", True),
                   "R": ("R", "firmware build", "export", "before S", False),
                   "gerber": ("X", "gerber", "export", "after F", False),
                   "abnahme": ("A", "abnahme", "acceptance", "", False)}
