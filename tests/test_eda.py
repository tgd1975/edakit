"""open_project never lets a command go on in another project (it once wrote a schematic into the wrong one)."""

import json
import re

import pytest

from edakit import eda


class FakeEasyEDA:
    """Answers easyeda_api_call like the bridge: one project open, createProject as the local desktop client does, the
    local projects listed per project folder (folders: {path: [project names]}), none without the folder."""

    def __init__(self, open_name, create_returns=None, opens=True, folders=None):
        self.open_name, self.create_returns, self.opens = open_name, create_returns, opens
        self.folders = folders if folders is not None else {"/home/u/EasyEDA-Pro/projects": [open_name]}
        self.calls = []

    def call(self, tool, timeout=130, **args):
        path, a = args["path"], args["args"]
        assert args.get("maxDepth") == eda.API_DEPTH         # deep answers asked of the bridge (M-3)
        self.calls.append(path)
        if path == "DMT_Project.getCurrentProjectInfo":
            return {"ok": True, "result": {"friendlyName": self.open_name, "uuid": f"uuid-{self.open_name}"}}
        if path == "DMT_Team.getAllTeamsInfo":
            return {"ok": True, "result": [{"itemType": "Team", "name": f, "uuid": f, "identity": 0} for f in self.folders]}
        if path == "DMT_Project.getAllProjectsUuid":     # only with the folder as teamUuid, as the local client does
            return {"ok": True, "result": [f"uuid-{n}" for n in self.folders.get(a[0] if a else None, [])]}
        if path == "DMT_Project.getProjectInfo":
            return {"ok": True, "result": {"friendlyName": a[0].removeprefix("uuid-"), "uuid": a[0]}}
        if path == "DMT_Project.createProject":     # since 1.7.0 a create that returns null is an error (M-5)
            if self.create_returns is None:
                return {"ok": False, "error": 'EasyEDA returned null for "DMT_Project.createProject": nothing was created.'}
            return {"ok": True, "result": self.create_returns}
        if path == "DMT_Project.openProject":
            if self.opens:
                self.open_name = a[0].removeprefix("uuid-")
            return {"ok": True, "result": True}
        if path == "DMT_Board.getAllBoardsInfo":
            return {"ok": True, "result": [{"name": "Board1"}]}
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
    with pytest.raises(eda.MCPError, match="in none of EasyEDA's project folders"):
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


# --- reads of the focused page: the BOM of gate --eda (walkthrough-gaps B7) ---------------------------------------

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


# --- found in the live runs of 2026-10-31 ----------------------------------------------------------------------------

def test_a_project_never_opened_is_found_in_easyedas_project_folders(cfg):
    """E-9: getAllProjectsUuid lists the local projects of a folder given as teamUuid (getAllTeamsInfo) – so edakit
    opens a project made by hand without asking for it to be opened once."""
    mcp = FakeEasyEDA("other", folders={"/a": ["other"], "/b": ["x", cfg.project]})
    assert eda.local_project_uuid(mcp, cfg.project) == f"uuid-{cfg.project}"
    assert eda.open_project(mcp, cfg) == f"uuid-{cfg.project}"
    assert json.loads(cfg.artifact("easyeda_project.json").read_text())["uuid"] == f"uuid-{cfg.project}"


def test_a_project_in_no_folder_is_not_opened(cfg):
    mcp = FakeEasyEDA("other", folders={"/a": ["other"]})
    assert eda.local_project_uuid(mcp, cfg.project) is None
    with pytest.raises(eda.MCPError, match="in none of EasyEDA's project folders"):
        eda.open_project(mcp, cfg)
    assert "DMT_Project.openProject" not in mcp.calls


class SlowDocs(FakeEasyEDA):
    """Right after openProject EasyEDA lists no board for a few calls (the live run: ensure_board saw none)."""

    def __init__(self, *a, empty=3, **k):
        super().__init__(*a, **k)
        self.empty = empty

    def call(self, tool, timeout=130, **args):
        if args["path"] == "DMT_Board.getAllBoardsInfo":
            self.calls.append(args["path"])
            self.empty -= 1
            return {"ok": True, "result": [] if self.empty >= 0 else [{"name": "Board1"}]}
        return super().call(tool, timeout, **args)


def test_open_project_waits_for_the_documents(cfg):
    cfg.artifact("easyeda_project.json").write_text(json.dumps({"name": cfg.project, "uuid": f"uuid-{cfg.project}"}))
    mcp = SlowDocs("other", empty=3)
    eda.open_project(mcp, cfg)
    assert mcp.calls.count("DMT_Board.getAllBoardsInfo") == 4      # three empty answers, then the board


class PanelRename:
    """modifySchematicName that renames the project's panel instead – what the live run left in edakit-probe-fp
    ("Panel1" named generated_esp32)."""

    def __init__(self):
        self.panel, self.renamed_back = "Panel1", None

    def call(self, tool, timeout=130, **args):
        if tool == "easyeda_schematic_sheet_info":
            return {"sheet": {"parentSchematicUuid": "s1"}}
        path, a = args["path"], args["args"]
        if path == "DMT_Schematic.getAllSchematicsInfo":
            return {"ok": True, "result": [{"uuid": "s1"}]}
        if path == "DMT_Schematic.getSchematicInfo":
            return {"ok": True, "result": {"name": "Schematic2"}}
        if path == "DMT_Project.getCurrentProjectInfo":
            return {"ok": True, "result": {"data": [{"itemType": "Panel", "uuid": "p1", "name": self.panel}]}}
        if path == "DMT_Schematic.modifySchematicName":
            self.panel = a[1]
            return {"ok": True, "result": True}
        if path == "DMT_Panel.modifyPanelName":
            self.panel, self.renamed_back = a[1], a[1]
            return {"ok": True, "result": True}
        raise AssertionError(path)


def test_a_rename_that_reaches_the_panel_is_undone_and_reported(cfg):
    mcp = PanelRename()
    with pytest.raises(eda.MCPError, match="renamed the panel 'Panel1' instead"):
        eda.rename_schematic(mcp, "s1", "generated_esp32")
    assert mcp.renamed_back == "Panel1"


# --- schematic copy and create in the KiCad live test of 2026-10-31 (LT-10, LT-11) -----------------------------------

def ok(result):
    return {"ok": True, "result": result}


class FakeDocs:
    """EasyEDA's documents as schematic copy and create see them: schematics with their pages, the parts of each page,
    the project's panels, the active page. foreign = (page name, company, version, parts, project): what copySchematic
    put into the copy in the live run – another project's schematic; without it the copy is the source's."""

    def __init__(self, parts=("C1", "R1", "U1"), version="graph v1.0", panel="Panel1", foreign=None):
        self.sch = {"s-tpl": {"name": "generated_main", "board": None, "project": "uuid-proj",
                              "pages": {"p-tpl": {"name": "LED bar template", "parts": list(parts),
                                                  "tb": {"Company": "edakit example", "Version": version}}}}}
        self.panels, self.foreign = {"pn1": panel}, foreign
        self.active, self.deleted, self.renames = "p-tpl", [], []

    def parent(self, page):
        return next(u for u, s in self.sch.items() if page in s["pages"])

    def names(self):
        return {s["name"] for s in self.sch.values()}

    def call(self, tool, timeout=130, **args):
        if tool == "easyeda_schematic_sheet_info":
            return {"sheet": {"uuid": self.active, "parentSchematicUuid": self.parent(self.active)}}
        if tool == "easyeda_schematic_components":
            parts = self.sch[self.parent(self.active)]["pages"][self.active]["parts"]
            off, n = args.get("offset", 0), args.get("limit", 500)
            return {"components": [{"reference": r, "primitiveId": f"id-{r}"} for r in parts][off:off + n],
                    "total": len(parts)}
        path, a = args["path"], args["args"]
        if path == "DMT_Schematic.getAllSchematicsInfo":
            return ok([{"uuid": u, "parentBoardName": s["board"], "page": [{"uuid": p} for p in s["pages"]]}
                       for u, s in self.sch.items()])
        if path == "DMT_Schematic.getSchematicInfo":
            s = self.sch[a[0]]
            return ok({"uuid": a[0], "name": s["name"], "parentBoardName": s["board"], "parentProjectUuid": s["project"],
                       "page": [{"uuid": p, "name": pg["name"],
                                 "titleBlockData": {k: {"value": v} for k, v in pg["tb"].items()}}
                                for p, pg in s["pages"].items()]})
        if path == "DMT_Project.getCurrentProjectInfo":
            return ok({"uuid": "uuid-proj", "data": [{"itemType": "Panel", "uuid": u, "name": n}
                                                     for u, n in self.panels.items()]})
        if path == "DMT_Schematic.copySchematic":
            src, project = self.sch[a[0]], "uuid-proj"
            pages = {f"p-copy{i}": json.loads(json.dumps(pg)) for i, pg in enumerate(src["pages"].values())}
            if self.foreign:
                name, company, version, parts, project = self.foreign
                pages = {"p-copy0": {"name": name, "parts": list(parts), "tb": {"Company": company, "Version": version}}}
            self.sch["s-copy"] = {"name": f"{src['name']}_Copy", "board": None, "project": project, "pages": pages}
            return ok("s-copy")
        if path == "DMT_Schematic.deleteSchematic":
            self.deleted.append(a[0])
            del self.sch[a[0]]
            return ok(True)
        if path == "DMT_EditorControl.openDocument":
            self.active = a[0]
            return ok(True)
        if path == "DMT_Schematic.modifySchematicName":        # acts on the ACTIVE schematic, as EasyEDA's does
            self.sch[self.parent(self.active)]["name"] = a[1]
            self.renames.append(a[1])
            return ok(True)
        raise AssertionError(path)

    def close(self):
        pass


def run_copy(cfg, monkeypatch, mcp):
    from types import SimpleNamespace

    from edakit import schematic
    monkeypatch.setattr(schematic.eda, "start", lambda cfg, verbose=False: mcp)
    monkeypatch.setattr(schematic.eda, "wait_for_bridge", lambda mcp, wait: True)
    monkeypatch.setattr(schematic.eda, "open_project", lambda mcp, cfg, create=False: "uuid-proj")
    return schematic.copy(cfg, SimpleNamespace(board=None, source=None, target=None, verbose=False, wait=0,
                                               save=False))


BELL = ("Christmas bell ESP32 THT template", "Christmas bell", "graph v0.1", ["C1", "J9", "LED1", "R1", "U1"])


def test_a_copy_with_the_parts_of_its_source_is_renamed(cfg, monkeypatch, capsys):
    mcp = FakeDocs()
    assert run_copy(cfg, monkeypatch, mcp) == 0
    assert mcp.sch["s-copy"]["name"] == "layout_main" and mcp.deleted == []
    assert "'generated_main' -> 'layout_main': 1 page(s), 3 parts" in capsys.readouterr().out


def test_a_copy_of_another_schematic_is_deleted_and_named_never_renamed(cfg, monkeypatch, capsys):
    """LT-11: copySchematic on the template's UUID made a copy of the bell's ESP32 THT template (19 parts for a graph
    of 17), and edakit renamed it to layout_main. Now the copy's parts are held to the source's first."""
    mcp = FakeDocs(foreign=(*BELL, "uuid-proj"))
    assert run_copy(cfg, monkeypatch, mcp) == 1
    assert mcp.deleted == ["s-copy"] and mcp.renames == [] and "layout_main" not in mcp.names()
    err = capsys.readouterr().err
    assert "5 parts instead of 3" in err and "J9, LED1" in err
    assert "'Christmas bell ESP32 THT template'" in err and "'Christmas bell'" in err and "'graph v0.1'" in err
    assert "the copy is deleted, nothing renamed" in err


def test_a_wrong_copy_outside_the_open_project_is_left_and_named(cfg, monkeypatch, capsys):
    mcp = FakeDocs(foreign=(*BELL, "uuid-bell"))
    assert run_copy(cfg, monkeypatch, mcp) == 1
    assert mcp.deleted == [] and mcp.renames == []
    assert "s-copy is left – not a free schematic of this project" in capsys.readouterr().err


def test_a_template_of_an_older_graph_is_named_before_it_is_copied(cfg, monkeypatch, capsys):
    mcp = FakeDocs(version="graph v0.9")
    assert run_copy(cfg, monkeypatch, mcp) == 0
    assert "! 'generated_main' was drawn from graph v0.9, the graph is v1.0" in capsys.readouterr().out


class FakeUnreadable(FakeDocs):
    """#337: on desk-led, a new EasyEDA Pro 3.2.209 project, getSchematicInfo of the template just generated threw
    "TypeError: Cannot read properties of undefined (reading 'Symbol')" in schematic copy, after its name had been
    read – the name lookup swallows the error, the reads of the template's title block and parts did not."""

    def call(self, tool, timeout=130, **args):
        if args.get("path") == "DMT_Schematic.getSchematicInfo" and self.names_read:
            return {"ok": False, "error": "TypeError: Cannot read properties of undefined (reading 'Symbol')"}
        if args.get("path") == "DMT_Schematic.getSchematicInfo":
            self.names_read = True
        return super().call(tool, timeout, **args)

    names_read = False


def test_a_template_easyeda_cannot_read_names_the_way_without_a_copy(cfg, monkeypatch, capsys):
    mcp = FakeUnreadable()
    assert run_copy(cfg, monkeypatch, mcp) == 1
    assert mcp.deleted == [] and mcp.renames == [] and "s-copy" not in mcp.sch
    err = capsys.readouterr().err
    assert "EasyEDA cannot read the template 'generated_main'" in err
    assert "reading 'Symbol'" in err and "`edakit schematic layout --save`" in err


def test_a_template_the_page_rename_renamed_is_named_back(cfg, capsys):
    """LT-10: the first schematic create in a new project left the template named "LED bar template" – the title of
    its page – and a panel named generated_main. The name is read again after the title block and put back; a panel
    of that name is named, not touched."""
    mcp = FakeDocs(panel="generated_main")
    mcp.sch["s-tpl"]["name"] = "LED bar template"
    assert eda.keep_schematic_name(mcp, "s-tpl", "generated_main", "p-tpl", panels=True) is True
    assert mcp.sch["s-tpl"]["name"] == "generated_main" and mcp.panels == {"pn1": "generated_main"}
    out = capsys.readouterr().out
    assert "is named 'LED bar template', not 'generated_main' – renaming it back" in out
    assert "a panel of the project is named 'generated_main' (pn1)" in out


def test_a_template_that_kept_its_name_is_left_alone(cfg, capsys):
    mcp = FakeDocs()
    assert eda.keep_schematic_name(mcp, "s-tpl", "generated_main", "p-tpl", panels=True) is False
    assert mcp.renames == [] and capsys.readouterr().out == ""


class FakeTitleBlock:
    """The bridge for label_sheet: the page active, a frame on it; EasyEDA Pro 3.2.209 refuses a title block item
    without boolean showTitle and showValue (INVALID_TITLE_BLOCK_ITEM, #116)."""

    def __init__(self):
        self.items = None

    def call(self, tool, timeout=130, **args):
        if tool == "easyeda_schematic_sheet_info":
            return {"sheet": {"uuid": "page"}}
        path, a = args["path"], args["args"]
        if path == "SCH_PrimitiveComponent.getAll":
            return {"ok": True, "result": ["frame"]}
        if path == "DMT_Schematic.modifySchematicPageTitleBlock":
            for name, item in a[1].items():
                if not (isinstance(item.get("showTitle"), bool) and isinstance(item.get("showValue"), bool)):
                    return {"ok": False, "error": {"code": "INVALID_TITLE_BLOCK_ITEM", "item": name}}
            self.items = a[1]
            return {"ok": True, "result": True}
        if path == "DMT_Schematic.modifySchematicPageName":
            return {"ok": True, "result": True}
        raise AssertionError(path)


def test_the_title_block_items_carry_boolean_visibility(cfg):
    mcp = FakeTitleBlock()
    eda.label_sheet(mcp, cfg, "page", "main", 3, {"Page Size": "A3", "Width": 1654, "Height": 1170})
    shown = {k: (v["showTitle"], v["showValue"]) for k, v in mcp.items.items()}
    assert shown == {"Company": (True, True), "Version": (True, True), "Drawn": (True, True),
                     "Reviewed": (True, True), "Page Size": (True, True), "Width": (False, False),
                     "Height": (False, False)}
    assert mcp.items["Version"]["value"] == "graph v3" and mcp.items["Width"]["value"] == "1654"


class FakePcbList:
    """easyeda_pcb_components as easyeda-mcp-pro 1.6.0 answers it: only for the focused PCB and the exact UUID of its
    project (readProjectScoped) – "current" is refused. EasyEDA has switched to the schematic on its own."""

    def __init__(self):
        self.active, self.parts = "sch-1", [{"designator": f"R{i}"} for i in range(1, 251)]

    def call(self, tool, timeout=130, **args):
        if tool == "easyeda_pcb_components":
            if self.active != "pcb-1" or args["projectId"] != "proj-1":
                raise eda.MCPError("PCB project identity mismatch: requested project UUID must match the focused PCB")
            page = self.parts[args["offset"]:args["offset"] + args["limit"]]
            return {"components": page, "total": len(self.parts)}
        path, a = args["path"], args["args"]
        if path == "DMT_SelectControl.getCurrentDocumentInfo":
            return {"ok": True, "result": {"uuid": self.active}}
        if path == "DMT_EditorControl.openDocument":
            self.active = a[0]
            return {"ok": True, "result": True}
        if path == "DMT_Project.getCurrentProjectInfo":
            return {"ok": True, "result": {"uuid": "proj-1", "friendlyName": "demo"}}
        raise AssertionError(path)


def test_the_pcb_parts_are_listed_with_the_pcb_focused_and_the_projects_uuid(cfg, monkeypatch):
    monkeypatch.setattr(eda, "PCB", {"name": "main", "uuid": "pcb-1"})
    mcp = FakePcbList()
    assert [c["designator"] for c in eda.list_pcb_components(mcp)] == [f"R{i}" for i in range(1, 251)]
    assert mcp.active == "pcb-1"


# --- E-3 and E-7 on 3.2.209 (TD-38) ------------------------------------------------------------------------------------

def test_the_probe_throwing_counts_as_an_inactive_pcb_tab(monkeypatch):
    """With the schematic active, 3.2.209 throws on the PCB probe instead of answering empty: activate_pcb switches."""
    answers = iter([eda.MCPError("PCB_Drc.getCurrentRuleConfigurationName: 指定的主题消息在对应的画布内没有相关订阅"), "Custom"])
    switched = []

    def api(mcp, path, *args, **kw):
        if path == "PCB_Drc.getCurrentRuleConfigurationName":
            a = next(answers)
            if isinstance(a, Exception):
                raise a
            return a
        switched.append(path)
    monkeypatch.setattr(eda, "api", api)
    monkeypatch.setattr(eda, "open_pcb", lambda mcp, name: switched.append("open_pcb"))
    monkeypatch.setattr(eda.time, "sleep", lambda s: None)
    monkeypatch.setattr(eda, "PCB", {"name": "main", "uuid": "pcb-1"})
    eda.activate_pcb(None)
    assert switched == ["DMT_EditorControl.openDocument", "open_pcb"]


@pytest.mark.parametrize("first, reloads", [([], 0), ([{"errorType": "Clearance Error"}], 0),
                                            ([{"errorType": "Connection Error"}] * 3, 1)])
def test_the_drc_reloads_the_pcb_only_on_connection_errors(monkeypatch, first, reloads):
    runs, done = iter([first, []]), []
    monkeypatch.setattr(eda, "drc", lambda mcp, out=None: next(runs))
    monkeypatch.setattr(eda, "reload_pcb", lambda mcp: done.append("reload"))
    found = eda.drc_reloading(None, say=lambda s: None)
    assert len(done) == reloads and found == ([] if reloads else first)


# --- stage S reads the schematic as saved, other schematics left open (#117, M-11) -------------------------------------

class FakeSaved:
    """Two schematics of one project, both open in tabs: the template and the board's schematic, its copy. Until
    easyeda-mcp-pro 1.9.0 the bridge listed one pin of the template on a second net while the board's schematic was
    open (M-11, pytree's U4.11 on V_LED with layout_tree open); `leak` keeps that bridge, to show the check no longer
    closes the other schematic against it. Records the calls in order."""

    def __init__(self, comps, nets, extra, unsaved=False, other_unsaved=False, leak=False):
        self.comps, self.drawn, self.extra, self.leak = comps, nets, extra, leak
        self.tabs = [{"tabId": "t-tpl1", "title": "generated_main", "isUnSaved": unsaved,
                      "data": {"sch": True, "data-schematic-uuid": "s-template"}},
                     {"tabId": "t-lay1", "title": "layout_main", "isUnSaved": other_unsaved,
                      "data": {"sch": True, "data-schematic-uuid": "s-layout"}},
                     {"tabId": "t-pcb", "title": "main", "data": {}}]
        self.calls = []

    def leaking(self):
        return self.leak and any(tab["tabId"] == "t-lay1" for tab in self.tabs)

    def call(self, tool, timeout=130, **args):
        if tool == "easyeda_schematic_sheet_info":
            return {"sheet": {"uuid": "tpl1", "parentSchematicUuid": "s-template"}}
        if tool == "easyeda_schematic_components":
            self.calls.append(tool)
            return {"components": self.comps, "total": len(self.comps)}
        if tool == "easyeda_schematic_nets":
            self.calls.append(tool)
            nets = {n: list(p) + ([self.extra[1]] if n == self.extra[0] and self.leaking() else [])
                    for n, p in self.drawn.items()}
            return {"nets": [{"net_name": n, "nodes": [{"component_ref": p.split(".")[0], "pin": p.split(".")[1]}
                                                       for p in pins]} for n, pins in nets.items()]}
        path = args["path"]
        self.calls.append(path)
        if path == "DMT_Schematic.getAllSchematicsInfo":
            return {"ok": True, "result": [{"uuid": "s-template", "page": [{"uuid": "tpl1"}]}]}
        if path == "DMT_Schematic.getSchematicInfo":
            return {"ok": True, "result": {"name": "generated_main"}}
        if path == "DMT_EditorControl.getSplitScreenTree":
            return {"ok": True, "result": [{"tabs": list(self.tabs)}]}
        if path == "DMT_EditorControl.closeDocument":
            self.tabs = [tab for tab in self.tabs if tab["tabId"] != args["args"][0]]
            return {"ok": True, "result": True}
        if path == "DMT_EditorControl.openDocument":
            if not any(tab["tabId"] == "t-tpl1" for tab in self.tabs):
                self.tabs.insert(0, {"tabId": "t-tpl1", "title": "generated_main", "isUnSaved": False,
                                     "data": {"sch": True, "data-schematic-uuid": "s-template"}})
            return {"ok": True, "result": True}
        raise AssertionError(path)


def saved_template(cfg, unsaved=False, other_unsaved=False, leak=False):
    from edakit.design import Design
    design = Design.from_config(cfg)
    board = cfg.board(None)
    comps, nets = design.board_comps(board.name), design.board_nets(board.name)
    first, second = sorted(nets)[:2]
    pin = nets[first][0]
    sch = [{"reference": d, "lcsc": c.get("lcsc"), "primitiveId": f"p-{d}"} for d, c in comps.items()]
    return (FakeSaved(sch, nets, (second, pin), unsaved, other_unsaved, leak),
            f"{first}: {pin} is on {sorted([first, second])}")


def run_check(cfg, monkeypatch, mcp, tmp_path):
    from argparse import Namespace

    from edakit import schematic
    monkeypatch.setattr(eda, "start", lambda cfg, verbose=False: type("M", (), {"call": mcp.call,
                                                                               "close": lambda self: None})())
    monkeypatch.setattr(eda, "wait_for_bridge", lambda mcp, wait: True)
    monkeypatch.setattr(eda, "open_project", lambda mcp, cfg, create=False: "uuid")
    out = tmp_path / "check.json"
    args = Namespace(board=None, schematic=None, no_pins=True, json=str(out), verbose=False, wait=1)
    return schematic.check(cfg, args), json.loads(out.read_text())


def test_stage_s_leaves_the_other_schematics_open(cfg, monkeypatch, tmp_path):
    """#117, M-11 fixed in easyeda-mcp-pro 1.9.0: the check closes only the template's saved tabs, to read it from
    the save; the board's schematic and the PCB stay open, and the template matches."""
    mcp, _ = saved_template(cfg)
    code, found = run_check(cfg, monkeypatch, mcp, tmp_path)
    assert code == 0 and found == {}
    assert [tab["tabId"] for tab in mcp.tabs] == ["t-tpl1", "t-lay1", "t-pcb"]
    assert mcp.calls.count("DMT_EditorControl.closeDocument") == 1


def test_a_bridge_before_1_9_shows_the_leak_again(cfg, monkeypatch, tmp_path):
    """With a bridge older than 1.9.0 the pin of the template on a second net comes back – the check reports it,
    it does not hide it by closing other schematics."""
    mcp, finding = saved_template(cfg, leak=True)
    code, found = run_check(cfg, monkeypatch, mcp, tmp_path)
    assert code == 2 and found["nets"] == [finding]


def test_another_schematic_with_unsaved_changes_is_no_finding(cfg, monkeypatch, tmp_path):
    """Another schematic with unsaved changes stays open, as every other one does, and is no finding: its nets do not
    show in this one's."""
    mcp, _ = saved_template(cfg, other_unsaved=True)
    code, found = run_check(cfg, monkeypatch, mcp, tmp_path)
    assert code == 0 and found == {}


def test_a_template_with_unsaved_changes_is_not_closed_and_named(cfg, monkeypatch, tmp_path):
    """Closing a tab with unsaved changes would throw them away: it stays open, its drawing is read, and the check
    names that it did not read the saved state."""
    mcp, _ = saved_template(cfg, unsaved=True)
    code, found = run_check(cfg, monkeypatch, mcp, tmp_path)
    assert [tab["tabId"] for tab in mcp.tabs] == ["t-tpl1", "t-lay1", "t-pcb"]
    assert code == 2 and list(found) == ["saved"]
    assert found["saved"][0].startswith("generated_main: unsaved changes in EasyEDA – read as drawn in this session")


def test_create_save_reads_the_template_again_from_its_save(cfg, capsys):
    """`schematic create --save` reads the saved template again against the graph; the board's schematic stays."""
    from edakit import schematic
    from edakit.design import Design
    mcp, _ = saved_template(cfg)
    design = Design.from_config(cfg)
    board = cfg.board(None)
    comps, nets = design.board_comps(board.name), design.board_nets(board.name)
    assert schematic.check_reopened(mcp, "generated_main", comps, nets) == 0
    assert "opened again from the save: matches the graph" in capsys.readouterr().out
    assert "t-lay1" in [tab["tabId"] for tab in mcp.tabs]


# --- a project script that focuses the PCB before opening it (#339) ----------------------------------------------------

@pytest.mark.parametrize("call", [eda.ensure_pcb_focus, eda.activate_pcb, eda.save_pcb])
def test_focusing_the_pcb_before_open_pcb_says_to_open_it_first(monkeypatch, call):
    """An easyeda script that calls ensure_pcb_focus (or what relies on it) before open_pcb in the session: the module
    has no PCB yet – a message naming open_pcb, not KeyError: 'uuid'. The bridge is never asked."""
    monkeypatch.setattr(eda, "PCB", {})
    asked = []
    monkeypatch.setattr(eda, "api", lambda mcp, path, *a, **kw: asked.append(path))
    monkeypatch.setattr(eda, "pcb_answers", lambda mcp: False)
    monkeypatch.setattr(eda.time, "sleep", lambda s: None)
    with pytest.raises(SystemExit) as e:
        call(None)
    assert "open_pcb(mcp, board.pcb)" in str(e.value) and asked == []


# --- projectId: the open project's UUID, not "current" (easyeda-mcp-pro 1.9.0, #884) -------------------------------

def test_the_client_sends_the_open_projects_uuid_as_project_id(monkeypatch):
    """Since easyeda-mcp-pro 1.9.0 the schematic and PCB reads refuse projectId "current"
    (current-project-uuid-mismatch): the client reads the open project's UUID once and sends it; open_project sets it."""
    sent = []

    def request(self, method, params, timeout):
        sent.append(params["arguments"])
        if params["arguments"].get("path") == "DMT_Project.getCurrentProjectInfo":
            return {"structuredContent": {"ok": True, "result": {"uuid": "u-open"}}}
        return {"structuredContent": {"ok": True}}

    monkeypatch.setattr(eda.MCPClient, "_request", request)
    monkeypatch.setattr(eda.lock, "claim_for_script", lambda **k: None)
    mcp = object.__new__(eda.MCPClient)
    mcp.project_uuid, mcp.lock_mode = None, "off"
    mcp.call("easyeda_schematic_components", projectId=eda.PROJECT)
    mcp.call("easyeda_schematic_nets", projectId=eda.PROJECT, scope="focused")
    mcp.call("easyeda_schematic_search_device", query="C5613")
    assert [a.get("projectId") for a in sent] == [None, "u-open", "u-open", None]
    mcp.project_uuid = "u-other"                      # open_project opened another project
    mcp.call("easyeda_pcb_components", projectId=eda.PROJECT)
    assert sent[-1]["projectId"] == "u-other"
