"""Long EasyEDA commands print `[x.x min] step n/m: …` before each step (#77): pcb apply, silk apply, export,
schematic create and schematic layout, each against a stand-in for EasyEDA – the count m is the number of steps run."""

import re
from types import SimpleNamespace

import pytest

from edakit import eda

STEP = re.compile(r"^\[ *\d+\.\d min\] step (\d+)/(\d+): (.*)$")


def steps(out):
    return [(int(m[1]), int(m[2]), m[3]) for m in map(STEP.match, out.splitlines()) if m]


def numbered(found):
    """1..m of m, in order."""
    m = len(found)
    return [(n, total) for n, total, _ in found] == [(n, m) for n in range(1, m + 1)]


class FakeMCP:
    def call(self, tool, timeout=130, **args):
        return {"errors": 0, "warnings": 0} if tool == "easyeda_erc_run" else {}

    def close(self):
        pass


def test_pcb_apply(project, monkeypatch, capsys):
    from edakit import pcb
    cfg = project.config()
    board = cfg.board()
    monkeypatch.setattr(pcb, "load_geometry", lambda cfg, board: {r: {"footprint": "fp", "pads": {}} for r in board.place})
    monkeypatch.setattr(pcb, "plan", lambda cfg, board: [])
    monkeypatch.setattr(pcb.eda, "list_pcb_components", lambda mcp: [{"designator": r, "primitiveId": f"id{r}"}
                                                                      for r in [*board.place, "X9"]])
    monkeypatch.setattr(pcb, "api", lambda mcp, path, *a, **k: [])
    monkeypatch.setattr(pcb, "ensure_pcb_focus", lambda mcp: None)
    monkeypatch.setattr(pcb, "tooling", lambda cfg, board, mcp: None)
    step = eda.Steps(pcb.APPLY_STEPS)
    step("bridge and PCB")                                     # what pcb.main prints before EasyEDA
    assert pcb.apply(cfg, board, None, step=step) == 0
    found = steps(capsys.readouterr().out)
    assert numbered(found) and len(found) == pcb.APPLY_STEPS
    assert [s for _, _, s in found][1:] == ["plan and geometry", "fixed parts", "unlock the other parts",
                                            "outline and holes", "tooling holes", "pad check"]


def test_silk_apply_with_its_check(project, monkeypatch, capsys):
    from shapely.geometry import Polygon

    from edakit import gerber, silk
    cfg = project.config()
    board = cfg.board()
    monkeypatch.setattr(silk, "api", lambda mcp, path, *a: [])
    monkeypatch.setattr(silk, "ensure_pcb_focus", lambda mcp: None)
    monkeypatch.setattr(silk, "export_gerber", lambda cfg, board, mcp: project.root)
    monkeypatch.setattr(silk, "gerber", SimpleNamespace(FILES=gerber.FILES, parse_gerber=lambda p: None,
                                                        shape=lambda g: Polygon()))
    monkeypatch.setattr(silk, "silk_on_openings", lambda folder, layer, own: (0.0, Polygon()))
    monkeypatch.setattr(silk, "picture", lambda *a, **k: None)
    monkeypatch.setattr(silk.eda, "save_pcb", lambda mcp: None)
    monkeypatch.setattr(silk.eda, "drc", lambda mcp: {})
    monkeypatch.setattr(silk.pcb, "drc_report", lambda cfg, board, mcp, drc: 0)
    step = eda.Steps(silk.APPLY_STEPS)
    step("bridge and PCB")
    assert silk.apply(cfg, board, None, step) == 0
    found = steps(capsys.readouterr().out)
    assert numbered(found) and len(found) == silk.APPLY_STEPS
    assert found[-1][2] == "DRC"


def test_export(project, monkeypatch, capsys):
    from edakit import cli, export
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    monkeypatch.setattr(export.eda, "connect", lambda cfg, verbose=False, artifact_dir=None: FakeMCP())
    for name in ("open_project", "focus_page", "open_pcb", "activate_pcb"):
        monkeypatch.setattr(export.eda, name, lambda *a, **k: None)
    monkeypatch.setattr(export.eda, "find_pages", lambda mcp, name: ("sch", ["page"]))
    monkeypatch.setattr(export, "schematic_pdf", lambda mcp, page, path: "vector")
    monkeypatch.setattr(export, "write_netlist", lambda mcp, path, sheet: 1.0)
    monkeypatch.setattr(export, "write_bom", lambda mcp, path: 1.0)
    monkeypatch.setattr(export, "export", lambda mcp, tool, path, **kw: 1.0)
    monkeypatch.setattr(export, "copy_project", lambda mcp, out: 0)
    assert cli.main(["export"]) == 2                                           # the stand-in writes no PDF file
    found = steps(capsys.readouterr().out)
    assert numbered(found) and [s for _, _, s in found] == [
        "bridge and project", "main: schematic PDF, netlist, BOM", "main: PCB PDF, Gerber, pick and place",
        "project file"]
    assert cli.main(["export", "--board", "main"]) == 2
    assert [m for _, m, _ in steps(capsys.readouterr().out)] == [3, 3, 3]     # one board: no project file


@pytest.mark.parametrize("save", [False, True])
def test_schematic_create(project, monkeypatch, capsys, save):
    from edakit import cli, schematic
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    monkeypatch.setattr(schematic.eda, "start", lambda cfg, verbose=False: FakeMCP())
    monkeypatch.setattr(schematic.eda, "easyeda_memory", lambda: "EasyEDA ?")
    for name in ("wait_for_bridge", "open_project", "label_sheet", "save_if_matching"):
        monkeypatch.setattr(schematic.eda, name, lambda *a, **k: True)
    monkeypatch.setattr(schematic.eda, "verify_nets", lambda mcp, nets, placed: 0)
    for name in ("prepare_schematic", "close_other_schematic_tabs", "mark_nc"):
        monkeypatch.setattr(schematic, name, lambda *a, **k: None)
    monkeypatch.setattr(schematic, "resolve_devices", lambda cfg, mcp, comps, refresh: {})
    monkeypatch.setattr(schematic, "place", lambda mcp, comps, devices, positions: {d: {} for d in comps})
    monkeypatch.setattr(schematic, "check_symbol_pins", lambda mcp, comps, placed: 0)
    monkeypatch.setattr(schematic, "connect", lambda mcp, nets, placed, stub: 0)
    monkeypatch.setattr(schematic, "repair", lambda mcp, nets, placed, stub: 0)
    monkeypatch.setitem(schematic.FOCUS, "page", "page")                        # prepare_schematic sets it
    assert cli.main(["schematic", "create", *(["--save"] if save else [])]) == 0
    found = steps(capsys.readouterr().out)
    assert numbered(found) and len(found) == 10 + save and found[0][2] == "bridge"
    assert found[-1][2] == ("save" if save else "ERC")


class FakeLayout:
    def __init__(self, *args):
        self.warnings, self.pin_net, self.nets, self.placed = [], {}, {}, []

    def build(self):
        return SimpleNamespace(box=(0, 0, 10, 10), wires=[], flags=[], comps=[], frames=[], texts=[]), ("A4", 1170, 825)


@pytest.mark.parametrize("argv, m", [([], 12), (["--save"], 13), (["--dry-run", "--reread"], 3), (["--dry-run"], 2)])
def test_schematic_layout(project, monkeypatch, capsys, argv, m):
    from edakit import cli
    from edakit import schematic_layout as sl
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    monkeypatch.setattr(sl.eda, "start", lambda cfg, verbose=False: FakeMCP())
    monkeypatch.setattr(sl.eda, "easyeda_memory", lambda: "EasyEDA ?")
    for name in ("wait_for_bridge", "open_project", "ensure_board", "focus_page", "label_sheet", "save_if_matching"):
        monkeypatch.setattr(sl.eda, name, lambda *a, **k: True)
    monkeypatch.setattr(sl.eda, "find_pages", lambda mcp, name: ("sch", ["page"]))
    monkeypatch.setattr(sl.eda, "list_sheet_parts", lambda mcp: [])
    monkeypatch.setattr(sl.eda, "verify_nets", lambda mcp, nets, placed: 0)
    for name in ("sync_parts", "sync_nc", "write_svg", "clear_sheet", "batch_write", "ensure_focus"):
        monkeypatch.setattr(sl, name, lambda *a, **k: None)
    monkeypatch.setattr(sl, "read_geometry", lambda mcp, comps: {})
    monkeypatch.setattr(sl, "check_geometry", lambda sheet, geo, pin_net: [])
    monkeypatch.setattr(sl, "Layout", FakeLayout)
    monkeypatch.setitem(sl.FOCUS, "page", "page")
    cache = project.config().artifact("layout_geometry_layout_main.json")
    cache.write_text("{}")                                        # a cached geometry: --dry-run needs no EasyEDA
    assert cli.main(["schematic", "layout", *argv]) == 0
    found = steps(capsys.readouterr().out)
    assert numbered(found) and len(found) == m, found
