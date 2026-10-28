"""Stamps of the project scripts (handbook 8.6): hardware/scripts.lock keeps per script what its result was made from at
its last run – its cmd, the script itself and the hash of everything it reads –, and edakit check and the gate tell an
outdated script with its about sentence: an input fails, a derive or easyeda script warns. edakit scripts lists every
script with its state and the order, edakit scripts stamp records a run made by hand. The bell's kunst on the example:
never run, stamped, current, its make_art.py changed – outdated."""

import argparse
import hashlib
import json
import shutil

import pytest
import test_gate as tg
import test_scripts as ts

from edakit import checks, cli, scripts

LOCK = "hardware/scripts.lock"
MAKE_ART = '"""Bell, greeting, star and snowflake for the silkscreen -> SVG files in this folder."""\nprint("drawn")\n'
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10">'
       '<rect width="10" height="10"/></svg>\n')
ART = [f"hardware/art/{n}.svg" for n in ("bell", "greeting", "small_bell", "chevron", "star", "snowflake")]
ABOUT = "Bell, greeting, star and snowflake as shapes for the silkscreen"
BILD = ts.entry("bild", kind="derive", cmd=["python", "docs/bild.py"], about="The board as a picture for the README",
                reads=["board:main"], writes=["docs/board.png"])
LIB = ts.entry("lib", kind="easyeda", cmd=["python", "hardware/lib/device.py"], about="The module's footprint (D-13)",
               writes=["project-library:main"])
JAHR = ts.entry("jahr", kind="input", cmd=["python", "hardware/art/year.py"], about="The year into the bell",
                reads=["hardware/art/bell.svg"], writes=["hardware/art/bell.svg"], after=["kunst"])


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write(project, path, text):
    p = project.root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def bell(project, entries=ts.KUNST):
    """The example with the bell's kunst and further entries: make_art.py and the six SVGs it writes, five of them
    placed by [[silk.art]]."""
    write(project, "hardware/art/make_art.py", MAKE_ART)
    for a in ART:
        write(project, a, SVG)
    res = ts.resolve(project, entries, art=ts.BELL_ART)
    assert res.findings == [], res.findings
    return project.config()


def edakit(project, monkeypatch, capsys, *argv):
    """An edakit command in the project: (exit code, what it printed)."""
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    code = cli.main(list(argv))
    out = capsys.readouterr()
    return code, out.out + out.err


def check(project, capsys):
    """edakit check: (exit code, its lines with the ID scripts)."""
    code = checks.main(project.config(), argparse.Namespace(release=False, json=None))
    return code, [line for line in capsys.readouterr().out.splitlines() if line.split()[1:2] == ["scripts"]]


def stamp(project, monkeypatch, capsys, *names):
    code, out = edakit(project, monkeypatch, capsys, "scripts", "stamp", *names)
    assert code == 0, out
    return json.loads((project.root / LOCK).read_text())["scripts"]


# --- the bell's kunst: never run, stamped, current, outdated --------------------------------------------------------
def test_a_script_nobody_ran_is_never_run(project, capsys):
    """Red before the stamps: kunst resolves, and edakit check said nothing about it."""
    bell(project)
    assert check(project, capsys) == (1, [f"ERROR   scripts  kunst never run: no stamp in {LOCK} – {ABOUT}"])


def test_stamped_current_then_outdated(project, monkeypatch, capsys):
    """The stamp holds the cmd, the script itself and the hashes; a changed make_art.py makes kunst outdated."""
    bell(project)
    s = stamp(project, monkeypatch, capsys, "kunst")["kunst"]
    assert s["cmd"] == ["python", "hardware/art/make_art.py"] and s["script"] == "hardware/art/make_art.py"
    assert s["hashes"] == {"hardware/art/make_art.py": sha(MAKE_ART)}       # kunst reads nothing but its script
    assert {"stamped", "by"} <= set(s)
    assert check(project, capsys) == (0, [])
    write(project, "hardware/art/make_art.py", MAKE_ART + "# the star gets six points\n")
    assert check(project, capsys) == (1, [
        f"ERROR   scripts  kunst outdated: hardware/art/make_art.py changed – {ABOUT}"])
    stamp(project, monkeypatch, capsys, "kunst")
    assert check(project, capsys) == (0, [])


def test_edakit_scripts_lists_every_script_with_its_state_and_the_order(project, monkeypatch, capsys):
    bell(project, ts.KUNST + BILD + LIB + ts.entry("lage", kind="check", cmd=["true"], about="The board fits",
                                                    id="X", phase="export"))
    write(project, "docs/board.png", "png")
    stamp(project, monkeypatch, capsys, "bild")
    code, out = edakit(project, monkeypatch, capsys, "scripts")
    assert code == 2, out
    lines, pad = out.splitlines(), " " * 16
    assert lines[0] == f"The project's scripts – [scripts.<name>] of edakit.toml, their stamps in {LOCK} (handbook 8.6)"
    kunst = lines.index("kunst  input    never run")
    assert lines[kunst + 1:kunst + 3] == [pad + ABOUT, pad + "python hardware/art/make_art.py"]
    bild = lines.index("bild   derive   current")
    assert lines[bild + 2] == pad + "python docs/bild.py – it names no file of the project: only reads count"
    assert lines[bild + 3].startswith(pad + "stamped 20")
    assert "lib    easyeda  never run" in lines
    assert "lage   check    no stamp – a check, phase export before S: the gate runs it" in lines
    order = " ".join(line.strip() for line in out.split("\norder: ")[1].split("\non command only")[0].splitlines())
    assert order.endswith("edakit route all → kunst → edakit silk apply → bild → lage → edakit gate")
    assert "on command only: lib" in lines
    assert " ".join(line.strip() for line in out.rstrip().split("\n\n")[-1].splitlines()) == (
        "2 to run: edakit run kunst lib – an easyeda script under the EasyEDA claim; an input also runs by itself "
        "before the step that reads it (handbook 8.6)")


def test_edakit_scripts_without_scripts(project, monkeypatch, capsys):
    code, out = edakit(project, monkeypatch, capsys, "scripts")
    assert code == 0 and "none – edakit.toml has no [scripts.<name>]" in out
    assert "order: edakit firmware → edakit check → edakit sim" in out


# --- what a stamp holds -----------------------------------------------------------------------------------------------
def test_reads_by_name_by_path_and_by_folder(project, monkeypatch, capsys):
    """A name of edakit's data, a file, a folder: each change is named, in the order of reads."""
    bell(project, ts.KUNST.replace("writes", 'reads  = ["graph", "hardware/art/palette.toml", "hardware/art/fonts/"]'
                                             "\nwrites"))
    write(project, "hardware/art/palette.toml", "white = 1\n")
    write(project, "hardware/art/fonts/script.otf", "a font")
    s = stamp(project, monkeypatch, capsys, "kunst")["kunst"]
    assert list(s["hashes"]) == ["graph", "hardware/art/fonts", "hardware/art/make_art.py", "hardware/art/palette.toml"]
    assert s["hashes"]["hardware/art/palette.toml"] == sha("white = 1\n")
    assert s["hashes"]["graph"] == scripts.data_hash(project.config(), "graph")
    g = project.graph()
    g["graph"]["description"] = "a bar of eight LEDs, and a bell"
    project.save_graph(g)
    write(project, "hardware/art/palette.toml", "white = 2\n")
    write(project, "hardware/art/fonts/serif.otf", "another font")
    assert check(project, capsys)[1] == [
        "ERROR   scripts  kunst outdated: graph changed, hardware/art/palette.toml changed, hardware/art/fonts "
        f"changed – {ABOUT}"]


def test_a_folder_hashes_its_files_without_caches(project):
    """Every file below the folder with its path in it – not __pycache__, *.pyc, *.pyo and names that start with a
    dot. A folder without files is absent."""
    cfg = project.config()
    assert scripts.input_hash(cfg, "hardware/sockel/") == scripts.ABSENT
    write(project, "hardware/sockel/huegel.py", "hill = 1\n")
    first = scripts.input_hash(cfg, "hardware/sockel/")
    assert scripts.input_hash(cfg, "hardware/sockel") == first != scripts.ABSENT
    for cache in ("__pycache__/huegel.cpython-313.pyc", ".huegel.py.swp", "stand.pyc", "stand.pyo", ".git/HEAD"):
        write(project, f"hardware/sockel/{cache}", "cached")
    assert scripts.input_hash(cfg, "hardware/sockel/") == first
    write(project, "hardware/sockel/stl/feet.toml", "feet = 3\n")
    second = scripts.input_hash(cfg, "hardware/sockel/")
    assert second != first
    (project.root / "hardware/sockel/huegel.py").rename(project.root / "hardware/sockel/hill.py")
    assert scripts.input_hash(cfg, "hardware/sockel/") not in (first, second)


def test_a_folder_with_the_lock_in_it(project, monkeypatch, capsys):
    """The lock is no input: a script that reads hardware/ is current after its stamp went into the lock there."""
    bell(project, ts.KUNST.replace("writes", 'reads  = ["hardware/"]\nwrites'))
    stamp(project, monkeypatch, capsys, "kunst")
    assert check(project, capsys) == (0, [])
    write(project, "hardware/art/palette.toml", "white = 1\n")
    assert check(project, capsys)[1] == [f"ERROR   scripts  kunst outdated: hardware changed – {ABOUT}"]


@pytest.mark.parametrize("cmd, script", [
    (["python", "hardware/art/make_art.py"], "hardware/art/make_art.py"),
    (["uv", "run", "--project", "../..", "python", "./hardware/art/make_art.py", "--out", "hardware/art/"],
     "hardware/art/make_art.py"),
    (["hardware/art/make_art.py", "svg"], "hardware/art/make_art.py"),
    (["python", "../shared/make_art.py"], "../shared/make_art.py"),      # a variant runs the main project's script
    (["make", "art"], None),                                             # a program on PATH
    (["python", "-m", "make_art"], None),
    (["sh", "hardware/art"], None),                                      # a folder is no script
    (["nc", "host:80", "hardware/art/make_art.py"], "hardware/art/make_art.py"),   # a file host:80 is no script
])
def test_the_script_itself_is_the_first_file_cmd_names(project, tmp_path, cmd, script):
    write(project, "hardware/art/make_art.py", MAKE_ART)
    write(project, "host:80", "not a script")
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "make_art.py").write_text(MAKE_ART)
    assert scripts.script_file(project.config(), cmd) == script


def test_another_cmd_or_a_new_read_makes_it_outdated(project, monkeypatch, capsys):
    bell(project)
    stamp(project, monkeypatch, capsys, "kunst")
    toml = project.root / "edakit.toml"
    before = toml.read_text()
    toml.write_text(before.replace('"hardware/art/make_art.py"]', '"hardware/art/make_art.py", "--stars", "6"]'))
    assert check(project, capsys)[1] == [f"ERROR   scripts  kunst outdated: cmd changed – {ABOUT}"]
    toml.write_text(before.replace('writes = ["hardware/art/bell.svg"', 'reads  = ["hardware/art/palette.toml"]\n'
                                                                       'writes = ["hardware/art/bell.svg"'))
    write(project, "hardware/art/palette.toml", "white = 1\n")
    assert check(project, capsys)[1] == [
        f"ERROR   scripts  kunst outdated: hardware/art/palette.toml new in reads – {ABOUT}"]


def test_absent_data_is_not_compared(project, monkeypatch, capsys):
    """The routing lives in build/: the CI and a fresh clone have none. A stamp recorded with the routing stays current
    without it, and edakit check notes what it did not compare; routing made since a stamp that found none is a
    change."""
    bell(project, ts.KUNST.replace("writes", 'reads  = ["routing:main"]\nwrites'))
    write(project, "build/edakit/route/main.ses", "(session main)\n")
    assert stamp(project, monkeypatch, capsys, "kunst")["kunst"]["hashes"]["routing:main"] != scripts.ABSENT
    shutil.rmtree(project.root / "build")
    assert check(project, capsys) == (0, ["NOTE    scripts  kunst: not compared – routing:main absent here"])
    assert stamp(project, monkeypatch, capsys, "kunst")["kunst"]["hashes"]["routing:main"] == scripts.ABSENT
    assert check(project, capsys) == (0, [])
    write(project, "build/edakit/route/main.ses", "(session main)\n")
    assert check(project, capsys) == (1, [f"ERROR   scripts  kunst outdated: routing:main changed – {ABOUT}"])


def test_the_project_library_is_not_compared(project, monkeypatch, capsys):
    """It is in EasyEDA only: its stamp has no hash, and edakit check notes it."""
    bell(project, ts.KUNST.replace("writes", 'reads  = ["project-library:main"]\nwrites'))
    assert stamp(project, monkeypatch, capsys, "kunst")["kunst"]["hashes"]["project-library:main"] is None
    assert check(project, capsys) == (0, ["NOTE    scripts  kunst: not compared – project-library:main has no offline "
                                          "hash"])


def test_after_an_outdated_script(project, monkeypatch, capsys):
    """jahr writes the year into kunst's bell: once kunst is outdated, jahr is as well – before kunst ran again."""
    bell(project, ts.KUNST + JAHR)
    write(project, "hardware/art/year.py", "print(2026)\n")
    stamp(project, monkeypatch, capsys, "kunst", "jahr")
    assert check(project, capsys) == (0, [])
    write(project, "hardware/art/make_art.py", MAKE_ART + "# the star gets six points\n")
    assert check(project, capsys)[1] == [
        f"ERROR   scripts  kunst outdated: hardware/art/make_art.py changed – {ABOUT}",
        "ERROR   scripts  jahr outdated: after kunst, which is outdated – The year into the bell"]
    write(project, "hardware/art/bell.svg", SVG.replace("<rect", "<circle"))      # kunst ran by hand
    stamp(project, monkeypatch, capsys, "kunst")
    assert check(project, capsys)[1] == [
        "ERROR   scripts  jahr outdated: hardware/art/bell.svg changed – The year into the bell"]
    stamp(project, monkeypatch, capsys, "jahr")
    assert check(project, capsys) == (0, [])


# --- the levels, in edakit check and in the gate ----------------------------------------------------------------------
def test_an_input_fails_a_derive_or_easyeda_script_warns(project, capsys):
    cfg = bell(project, ts.KUNST + BILD + LIB)
    assert check(project, capsys) == (1, [
        f"ERROR   scripts  kunst never run: no stamp in {LOCK} – {ABOUT}",
        f"WARNING scripts  bild never run: no stamp in {LOCK} – The board as a picture for the README",
        f"WARNING scripts  lib never run: no stamp in {LOCK} – The module's footprint (D-13)"])
    rows = scripts.gate_rows(cfg)
    assert [(r["stage"], r["id"], r["item"], r["result"], r["check"].split(":")[0]) for r in rows] == [
        ("G", "scripts", "", "fail", "kunst never run"), ("G", "scripts", "", "warn", "bild never run"),
        ("G", "scripts", "", "warn", "lib never run")]


def test_entries_that_do_not_resolve_fail_the_gate(project):
    """The user's decision: edakit refuses entries that do not resolve – stage G fails, and no stamp is compared."""
    ts.resolve(project, ts.entry("x", kind="input", **ts.X, writes=["build/x.json"]))
    rows = scripts.gate_rows(project.config())
    assert [(r["stage"], r["id"], r["result"]) for r in rows] == [("G", "scripts", "fail")]
    assert rows[0]["check"].startswith("x: an input, but no edakit step reads what it writes (build/x.json)")


def test_the_gate_reports_the_scripts_in_stage_g(project, monkeypatch, capsys):
    """Offline, with --no-scripts – else the gate runs kunst first (test_script_runs.py): kunst never ran – a failed
    check in section 2; bild a warning to accept in section 3; a current script passes."""
    bell(project, ts.KUNST + BILD + LIB)
    write(project, "hardware/lib/device.py", "print('footprint')\n")
    stamp(project, monkeypatch, capsys, "lib")
    code, _ = edakit(project, monkeypatch, capsys, "gate", "--no-scripts")
    assert code == 2
    text = (sorted((project.root / "build" / "release").iterdir())[-1] / "protocol.md").read_text()
    assert f"| G | scripts |  |  | kunst never run: no stamp in {LOCK} – {ABOUT} |  |  |" in tg.section(text, 2)
    assert (f"- `scripts bild never run: no stamp in {LOCK} – The board as a picture for the README` (project check). "
            "Actual: . Expected: . → **not accepted**") in tg.section(text, 3)
    stages = tg.section(text, 1)
    assert "| G Graph |" in stages and "1 check(s) failed (section 2)" in text


# --- what keeps a stamp from being recorded --------------------------------------------------------------------------
def test_stamp_refuses(project, monkeypatch, capsys):
    bell(project, ts.KUNST + ts.entry("lage", kind="check", cmd=["true"], about="The board fits", id="X",
                                      phase="export"))
    for argv, said in [
            ((), "edakit scripts stamp: name the scripts that ran"),
            (("nope",), "no [scripts.nope] in edakit.toml (kunst, lage)"),
            (("lage",), "lage is a check: its result is the gate's protocol, not a file – a check has no stamp")]:
        code, out = edakit(project, monkeypatch, capsys, "scripts", "stamp", *argv)
        assert code == 1 and said in out, out
    (project.root / "hardware/art/snowflake.svg").unlink()
    code, out = edakit(project, monkeypatch, capsys, "scripts", "stamp", "kunst")
    assert code == 1 and "kunst writes hardware/art/snowflake.svg, which is not there – run it first" in out, out
    assert not (project.root / LOCK).exists()                                        # nothing written
    write(project, "hardware/art/snowflake.svg", SVG)
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + ts.entry("x", kind="input", **ts.X, writes=["build/x.json"]))
    code, out = edakit(project, monkeypatch, capsys, "scripts", "stamp", "kunst")
    assert code == 1 and "the entries do not resolve into one order – edakit check names what keeps them" in out
    assert not (project.root / LOCK).exists()


def test_a_lock_edakit_cannot_read(project, monkeypatch, capsys):
    bell(project)
    write(project, LOCK, "{")
    code, found = check(project, capsys)
    assert code == 1 and len(found) == 1
    assert found[0].startswith(f"ERROR   scripts  {LOCK}: not readable (") and "nothing compared" in found[0]
    code, out = edakit(project, monkeypatch, capsys, "scripts", "stamp", "kunst")
    assert code == 1 and (project.root / LOCK).read_text() == "{"


def test_without_scripts_the_lock_is_not_read(project, capsys):
    """No key, no change: a project without [scripts] checks as before, whatever lies at hardware/scripts.lock."""
    write(project, LOCK, "{")
    assert check(project, capsys) == (0, [])
    assert scripts.gate_rows(project.config()) == []


def test_a_stamp_of_a_script_no_longer_registered_is_dropped(project, monkeypatch, capsys):
    bell(project, ts.KUNST + JAHR)
    write(project, "hardware/art/year.py", "print(2026)\n")
    stamp(project, monkeypatch, capsys, "kunst", "jahr")
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace(JAHR, ""))
    assert list(stamp(project, monkeypatch, capsys, "kunst")) == ["kunst"]
