"""Step 1.8: the footprint geometry of `edakit pcb dump` lies beside the board file (hardware/boards/<b>.geometry.json),
versioned with it – CI and a fresh clone compute the layout hash. A geometry from before, in
<artifacts>/pcb_geometry_<b>.json, is read until it is moved: edakit check, pcb plan and the gate say how, the layout
hash takes it where it lies, and pcb dump moves it."""

import json
import shutil

from helpers import check

from edakit import checks, cli, config, pcb, scripts
from edakit.design import Design
from edakit.release import gate

MIL = 1000 / 25.4
OLD = "build/edakit/pcb_geometry_main.json"      # where pcb dump wrote the geometry before
NEW = "hardware/boards/main.geometry.json"       # beside hardware/boards/main.toml
BOARD = "hardware/boards/main.toml"


def geometry(refs, hole=0.9):
    """The geometry pcb dump measures: 2 x 2 mm and one pad per part; J1's two pads plated, with `hole` (mm)."""
    geo = {r: {"footprint": "X", "bbox": [-MIL, -MIL, MIL, MIL],
               "pads": {"1": {"x": 0, "y": 0, "net": "", "tht": False}}} for r in refs}
    geo["J1"] = {"footprint": "CONN-TH_B2B-PH-K-S", "bbox": [-3 * MIL, -2.3 * MIL, 3 * MIL, 2.3 * MIL],
                 "pads": {n: {"x": x * MIL, "y": 0, "net": "", "tht": True, "hole": [hole, hole], "plated": True}
                          for n, x in (("1", 1.0), ("2", -1.0))}}
    return geo


def in_the_pcb(monkeypatch, geo):
    """EasyEDA's PCB holds the parts of geo, and pcb dump measures each as geo has it."""
    monkeypatch.setattr(pcb.eda, "list_pcb_components", lambda mcp: [{"designator": r} for r in geo])
    monkeypatch.setattr(pcb, "measure", lambda mcp, c: geo[c["designator"]])


def from_before(project, geo):
    """A geometry that pcb dump wrote before it was versioned: in <artifacts>."""
    f = project.root / OLD
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(geo, indent=1, ensure_ascii=False))
    return f


def layout_hash(cfg):
    return gate.file_hash(cfg.root, gate.layout_files(cfg))


def p7(cfg):
    rep = check(Design.from_config(cfg), cfg)
    return [m for c, m in rep.errors if c == "GEO.hole"], [m for c, m in rep.notes if c == "GEO.hole"]


def test_dump_writes_the_geometry_beside_the_board_file(project, monkeypatch):
    cfg = project.config()
    geo = geometry(cfg.board().place)
    in_the_pcb(monkeypatch, geo)
    pcb.dump(cfg, cfg.board(), None)
    assert json.loads((project.root / NEW).read_text()) == geo
    assert not (project.root / OLD).exists()
    assert gate.layout_files(cfg) == [project.root / BOARD, project.root / NEW]


def test_a_fresh_clone_computes_the_layout_hash(project, monkeypatch, tmp_path):
    """What git checks out – the project without build/ – has the geometry and so the same layout hash."""
    cfg = project.config()
    in_the_pcb(monkeypatch, geometry(cfg.board().place))
    pcb.dump(cfg, cfg.board(), None)
    clone = tmp_path / "clone"
    shutil.copytree(project.root, clone, ignore=shutil.ignore_patterns("build"))
    assert layout_hash(config.load(clone / "edakit.toml")) == layout_hash(cfg)
    assert p7(config.load(clone / "edakit.toml")) == p7(cfg) == ([], [])     # GEO.hole judges the holes in the clone too


def test_the_geometry_lies_beside_a_board_file_of_another_name(project, monkeypatch):
    (project.root / "pcb").mkdir()
    (project.root / BOARD).rename(project.root / "pcb" / "led.toml")
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace(f'file = "{BOARD}"', 'file = "pcb/led.toml"'))
    cfg = project.config()
    in_the_pcb(monkeypatch, geometry(cfg.board().place))
    pcb.dump(cfg, cfg.board(), None)
    assert gate.layout_files(cfg) == [project.root / "pcb" / "led.toml", project.root / "pcb" / "led.geometry.json"]


def test_a_geometry_from_before_is_read_until_it_is_moved(project, capsys):
    """Read from <artifacts> while it lies only there – GEO.hole judges it, the layout hash is the one before –, and edakit
    check, which writes nothing, says how to move it. The move changes the layout hash once: the path counts."""
    cfg = project.config()
    old = from_before(project, geometry(cfg.board().place, hole=0.65))      # a hole too small for J1's lead
    before = gate.file_hash(project.root, [project.root / BOARD, old])        # the layout hash so far
    errors, notes = p7(cfg)
    assert errors == ["J1 (pads 1, 2, pcb dump): hole 0.65 mm for diagonal 0.71 mm, play -0.06 mm, worst case "
                      "-0.14 mm, manufacturer 0.7 mm"]
    assert notes == [f"{OLD}: footprint geometry of board main among the artifacts, which are not versioned – move "
                     f"it beside the board file and commit it: mv {OLD} {NEW} (the layout hash changes once, sign-offs "
                     "with scope 'layout' lapse)"]
    assert layout_hash(cfg) == before
    assert cli.main(["check", "--config", str(project.root / "edakit.toml")]) == 1     # GEO.hole fails, as it should
    assert f"GEO.hole – hole fits the lead: 1 note\n  P  {notes[0]}" in capsys.readouterr().out
    pcb.plan(cfg, cfg.board())
    assert f"  {notes[0]}" in capsys.readouterr().out.splitlines()
    assert old.exists() and not (project.root / NEW).exists()                 # nothing moved on its own

    (project.root / NEW).write_bytes(old.read_bytes())                        # the move, as the note says
    old.unlink()
    cfg = project.config()
    assert p7(cfg) == (errors, [])
    assert layout_hash(cfg) not in (before, gate.file_hash(project.root, [project.root / BOARD, old]))
    pcb.plan(cfg, cfg.board())
    assert OLD not in capsys.readouterr().out


def test_a_geometry_copied_rather_than_moved_counts_beside_the_board_file(project):
    cfg = project.config()
    old = from_before(project, geometry(cfg.board().place, hole=0.65))
    (project.root / NEW).write_text(json.dumps(geometry(cfg.board().place)))
    assert p7(cfg) == ([], [])
    assert gate.layout_files(cfg) == [project.root / BOARD, project.root / NEW]
    assert old.exists()


def test_dump_moves_a_geometry_from_before(project, monkeypatch, capsys):
    """A dump of single parts adds them to the geometry from before and writes the whole beside the board file; the
    file in <artifacts> goes."""
    cfg = project.config()
    geo = geometry(cfg.board().place)
    old = from_before(project, geo)
    j1 = {**geo["J1"], "bbox": [-4 * MIL, -2.3 * MIL, 4 * MIL, 2.3 * MIL]}  # measured anew
    in_the_pcb(monkeypatch, {**geo, "J1": j1})
    pcb.dump(cfg, cfg.board(), None, ["J1"])
    assert json.loads((project.root / NEW).read_text()) == {**geo, "J1": j1}
    assert not old.exists()
    assert f"{OLD} moved beside the board file: commit {NEW}" in capsys.readouterr().out


def test_the_gate_notes_a_geometry_not_moved(project, monkeypatch):
    """The offline gate: the layout hash the one before, and a note in section 6 next to the sign-off notes."""
    cfg = project.config()
    old = from_before(project, geometry(cfg.board().place))
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["gate"]) == 2
    text = (sorted((project.root / "build" / "release").iterdir())[-1] / "protocol.md").read_text()
    assert f"| SHA-256 layout | `{gate.file_hash(project.root, [project.root / BOARD, old])}`" in text
    six = text.split("## 6 ")[1].split("\n## ")[0]
    assert f"- note: {OLD}: footprint geometry of board main among the artifacts, which are not versioned" in six


def test_footprints_are_the_geometry_edakit_reads(project):
    """footprints:<b> of the project scripts: the file the plan and the checks read – in <artifacts> until it is
    moved – hashed with its path; the place beside the board file is edakit's data, which no script writes."""
    cfg = project.config()
    assert scripts.data_hash(cfg, "footprints:main") == scripts.ABSENT
    old = from_before(project, {})
    assert scripts.data_hash(cfg, "footprints:main") == gate.file_hash(project.root, [old])
    (project.root / NEW).write_bytes(old.read_bytes())
    old.unlink()
    assert scripts.data_hash(cfg, "footprints:main") == gate.file_hash(project.root, [project.root / NEW])
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + f'\n[scripts.x]\nkind = "input"\ncmd = ["x"]\nabout = "x"\nwrites = ["{NEW}"]\n')
    assert [f.rule for f in scripts.resolve(project.config()).findings if "footprints:main" in f.msg] == [3]
