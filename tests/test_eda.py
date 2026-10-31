"""open_project never lets a command go on in another project (it once wrote a schematic into the wrong one)."""

import json
import re

import pytest

from edakit import eda


class FakeEasyEDA:
    """Answers easyeda_api_call like the bridge: one project open, createProject as the local desktop client does."""

    def __init__(self, open_name, create_returns=None, opens=True):
        self.open_name, self.create_returns, self.opens = open_name, create_returns, opens
        self.calls = []

    def call(self, tool, timeout=130, **args):
        path, a = args["path"], args["args"]
        self.calls.append(path)
        if path == "DMT_Project.getCurrentProjectInfo":
            return {"ok": True, "result": {"friendlyName": self.open_name, "uuid": f"uuid-{self.open_name}"}}
        if path == "DMT_Project.getAllProjectsUuid":
            return {"ok": True, "result": []}           # local projects are never listed
        if path == "DMT_Project.createProject":
            return {"ok": True, "result": self.create_returns}
        if path == "DMT_Project.openProject":
            if self.opens:
                self.open_name = a[0].removeprefix("uuid-")
            return {"ok": True, "result": True}
        raise AssertionError(path)


@pytest.fixture
def cfg(project, monkeypatch):
    monkeypatch.setattr(eda.time, "sleep", lambda s: None)
    return project.config()


def test_create_project_refused_stops_before_any_write(cfg):
    mcp = FakeEasyEDA("other", create_returns=None)
    with pytest.raises(eda.MCPError, match="create it by hand"):
        eda.open_project(mcp, cfg, create=True)
    assert "DMT_Project.openProject" not in mcp.calls
    assert not cfg.artifact("easyeda_project.json").exists()


def test_unknown_project_is_not_opened(cfg):
    with pytest.raises(eda.MCPError, match="open it in EasyEDA once"):
        eda.open_project(FakeEasyEDA("other"), cfg)


def test_reopens_the_remembered_project(cfg):
    cfg.artifact("easyeda_project.json").write_text(json.dumps({"name": cfg.project, "uuid": f"uuid-{cfg.project}"}))
    mcp = FakeEasyEDA("other")
    assert eda.open_project(mcp, cfg) == f"uuid-{cfg.project}"
    assert mcp.open_name == cfg.project


def test_wrong_project_after_open_is_an_error(cfg):
    cfg.artifact("easyeda_project.json").write_text(json.dumps({"name": cfg.project, "uuid": f"uuid-{cfg.project}"}))
    with pytest.raises(eda.MCPError, match="did not open .*'other'"):
        eda.open_project(FakeEasyEDA("other", opens=False), cfg)


# --- schematic create|layout --save: only a netlist that equals the graph is saved (#69) ----------------------------

class FakeNetlist:
    """Answers easyeda_schematic_nets with the given nets ({name: [(ref, pin)]}) and records the tool calls."""

    def __init__(self, nets):
        self.nets, self.tools = nets, []

    def call(self, tool, timeout=130, **args):
        self.tools.append(tool)
        if tool == "easyeda_schematic_nets":
            return {"nets": [{"net_name": n, "nodes": [{"component_ref": r, "pin": p} for r, p in nodes]}
                             for n, nodes in self.nets.items()]}
        if tool == "easyeda_project_save":
            return {"ok": True}
        raise AssertionError(tool)


GRAPH_NETS = {"VIN": ["J1.1", "D1.2"], "GND": ["J1.2", "C2.2"]}
PLACED = {d: {"ref": d} for d in ("J1", "D1", "C2")}
ALL_PINS = {"VIN": [("J1", "1"), ("D1", "2")], "GND": [("J1", "2"), ("C2", "2")]}


def save_step(mcp, **more):
    diffs = eda.verify_nets(mcp, GRAPH_NETS, PLACED)
    return eda.save_if_matching(mcp, diffs, **more)


def test_a_matching_netlist_is_saved(cfg):
    mcp = FakeNetlist(ALL_PINS)
    assert save_step(mcp) == 0
    assert "easyeda_project_save" in mcp.tools


def test_a_pin_missing_from_the_netlist_is_not_saved(cfg, capsys):
    mcp = FakeNetlist({"VIN": [("J1", "1"), ("D1", "2")], "GND": [("J1", "2")]})
    assert save_step(mcp) == 2
    assert "easyeda_project_save" not in mcp.tools
    assert "not saved: 1 differing nets, 0 failed connections, 0 pin mismatches" in capsys.readouterr().out


def test_an_empty_netlist_on_every_read_is_not_saved(cfg):
    mcp = FakeNetlist({})
    assert save_step(mcp) == 2
    assert mcp.tools.count("easyeda_schematic_nets") == 10 and "easyeda_project_save" not in mcp.tools


def test_failed_connections_and_pin_mismatches_hold_the_save_too(cfg, capsys):
    mcp = FakeNetlist(ALL_PINS)
    assert save_step(mcp, failures=1, pin_problems=2, skipped=1) == 2
    assert "easyeda_project_save" not in mcp.tools
    assert "1 failed connections, 2 pin mismatches, 1 parts skipped" in capsys.readouterr().out


def test_steps_print_n_of_m_with_minutes(capsys):
    from edakit import eda
    t = iter([0.0, 30.0, 150.0, 400.0])
    steps = eda.Steps(3, clock=lambda: next(t))
    for name in ("read", "route", "write"):
        steps(name)
    lines = capsys.readouterr().out.splitlines()
    assert lines == ["[ 0.5 min] step 1/3: read", "[ 2.5 min] step 2/3: route", "[ 6.7 min] step 3/3: write"]


def test_steps_go_to_the_stream_given(capsys):
    import sys

    from edakit import eda
    eda.Steps(1, out=sys.stderr)("export")
    cap = capsys.readouterr()
    assert cap.out == "" and "step 1/1: export" in cap.err


def test_progress_with_a_total_numbers_its_phases(capsys, monkeypatch):
    from edakit import eda
    monkeypatch.setattr(eda, "easyeda_memory", lambda: "EasyEDA 1.00 GB")
    phase = eda.Progress(2)
    phase("bridge")
    phase("place")
    phase(None)
    out = capsys.readouterr().out
    assert re.search(r"^\[ *\d+\.\d min\] step 1/2: bridge$", out, re.M)
    assert re.search(r"^\[ *\d+\.\d min\] step 2/2: place$", out, re.M)
    assert "  (place: " in out                                    # the duration of each phase stays


# --- reads of the focused page: the BOM of gate --easyeda (walkthrough-gaps B7) ---------------------------------------

class FakeTabs:
    """Two schematics with their pages in tabs, one active: easyeda_bom_generate answers for the ACTIVE page, as the
    bridge does. switch: {call number of easyeda_bom_generate: page} – EasyEDA makes that page active while the BOM
    is read (it switches tabs on its own). The template's tab is open from stage S."""

    BOM = {"lay1": [{"lcsc": "C1", "reference": "R1"}], "lay2": [{"lcsc": "C2", "reference": "D1"}],
           "tpl1": [{"lcsc": "C1", "reference": "R1"}, {"lcsc": "C9", "reference": "D1"}]}

    def __init__(self, switch=None, unsaved=False):
        self.sch = {"s-layout": ("layout_main", ["lay1", "lay2"]), "s-template": ("generated_main", ["tpl1"])}
        self.active, self.switch, self.reads = "tpl1", dict(switch or {}), 0
        self.tabs = [{"tabId": "t-tpl1", "title": "generated_main", "isUnSaved": unsaved,
                      "data": {"sch": True, "data-schematic-uuid": "s-template"}},
                     {"tabId": "t-pcb", "title": "main", "data": {"pcb": True}}]
        self.closed = []

    def call(self, tool, timeout=130, **args):
        if tool == "easyeda_schematic_sheet_info":
            return {"sheet": {"uuid": self.active, "parentSchematicUuid": self.parent(self.active)}}
        if tool == "easyeda_bom_generate":
            self.reads += 1
            bom = self.BOM[self.active]
            self.active = self.switch.pop(self.reads, self.active)
            return {"entries": bom}
        path, a = args["path"], args["args"]
        if path == "DMT_Schematic.getAllSchematicsInfo":
            return {"ok": True, "result": [{"uuid": u, "page": [{"uuid": p} for p in pages]}
                                           for u, (_, pages) in self.sch.items()]}
        if path == "DMT_Schematic.getSchematicInfo":
            return {"ok": True, "result": {"name": self.sch[a[0]][0]}}
        if path == "DMT_EditorControl.openDocument":
            self.active = a[0]
            return {"ok": True, "result": True}
        if path == "DMT_EditorControl.getSplitScreenTree":
            return {"ok": True, "result": [{"tabs": self.tabs}]}
        if path == "DMT_EditorControl.closeDocument":
            self.closed.append(a[0])
            return {"ok": True, "result": True}
        raise AssertionError(path)

    def parent(self, page):
        return next(u for u, (_, pages) in self.sch.items() if page in pages)


R1 = {"lcsc": "C1", "reference": "R1", "quantity": 1}
D1 = {"lcsc": "C2", "reference": "D1", "quantity": 1}


def test_the_bom_is_read_from_every_page_of_the_boards_schematic(cfg):
    """easyeda_bom_generate lists the parts of the focused page: each page of the board's schematic in turn, merged –
    and the template's tab, open since stage S, is closed first, so EasyEDA cannot switch to it."""
    from edakit.release import fab
    mcp = FakeTabs()
    assert fab.board_bom(mcp, cfg.board()) == [R1, D1]
    assert mcp.closed == ["t-tpl1"]


def test_a_page_that_loses_the_focus_while_its_bom_is_read_is_read_again(cfg, capsys):
    """The bell's report of 2026-10-30: the BOM tool mixed tabs. EasyEDA switches to the template while page 2's BOM
    is read, and the answer is the template's (D1 as C9), not page 2's: that read does not count, the page is read
    again. An unsaved template tab stays open."""
    from edakit.release import fab
    mcp = FakeTabs(switch={2: "tpl1"}, unsaved=True)
    assert fab.board_bom(mcp, cfg.board()) == [R1, D1]
    assert mcp.reads == 3 and mcp.closed == []
    assert "page lay2 lost the focus while it was read – reading it again" in capsys.readouterr().out


def test_a_page_that_never_holds_the_focus_stops_the_read(cfg):
    from edakit.release import fab
    mcp = FakeTabs(switch={2: "tpl1", 3: "tpl1", 4: "tpl1"}, unsaved=True)
    with pytest.raises(eda.MCPError, match="page lay2: another tab became active while it was read, 3 times"):
        fab.board_bom(mcp, cfg.board())
