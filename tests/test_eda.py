"""open_project never lets a command go on in another project (it once wrote a schematic into the wrong one)."""

import json

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
