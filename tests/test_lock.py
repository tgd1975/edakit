import json

import pytest

from edakit import lock


@pytest.fixture(autouse=True)
def state_file(tmp_path, monkeypatch):
    monkeypatch.setenv("EDAKIT_LOCK_FILE", str(tmp_path / "lock.json"))


def test_claim_refuse_release():
    with lock.state() as s:
        assert lock.claim(s, "A", "route") is None
        assert "held by" in lock.claim(s, "B", "short")
        assert lock.release(s, "B") is None          # not B's claim
        assert lock.release(s, "A") == "EasyEDA free"
        assert lock.claim(s, "B") is None


def test_expired_claim_is_taken_over():
    with lock.state() as s:
        lock.claim(s, "A")
        s["claim"]["renewed"] = "2000-01-01T00:00:00+00:00"
        assert lock.claim(s, "B") is None
        assert s["claim"]["chat"] == "B"


def test_yield_returns_to_the_holder():
    with lock.state() as s:
        lock.claim(s, "A", "long run")
        c, err = lock.yield_to(s, "A", "B", "2 min")
        assert err is None and c["chat"] == "B"
        assert lock.claim(s, "C") is not None        # a third session cannot snatch the gap
        assert lock.release(s, "B").startswith("EasyEDA back to")
        assert s["claim"]["chat"] == "A"


def test_expired_guest_goes_back():
    with lock.state() as s:
        lock.claim(s, "A")
        lock.yield_to(s, "A", "B")
        s["claim"]["renewed"] = "2000-01-01T00:00:00+00:00"
        assert lock.valid_claim(s)["chat"] == "A"


def test_hook_denies_and_allows(capsys, monkeypatch):
    with lock.state() as s:
        lock.claim(s, "A")
    for tool, denied in (("mcp__plugin_edakit_easyeda__easyeda_pcb_tracks", True),
                         ("mcp__easyeda__easyeda_pcb_tracks", True),
                         ("mcp__easyeda__easyeda_bridge_status", False),
                         ("mcp__other__thing", False)):
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO(json.dumps({"session_id": "B", "tool_name": tool})))
        lock.hook()
        out = capsys.readouterr().out
        assert ('"deny"' in out) == denied, tool


def run_hook(monkeypatch, capsys, session, tool, tool_input=None):
    data = {"session_id": session, "tool_name": tool}
    if tool_input is not None:
        data["tool_input"] = tool_input
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(json.dumps(data)))
    lock.hook()
    return '"deny"' in capsys.readouterr().out


def test_library_lookups_pass_a_held_claim(capsys, monkeypatch):
    with lock.state() as s:
        lock.claim(s, "A", "route all")
        renewed = s["claim"]["renewed"] = "2026-10-25T10:00:00+02:00"
    monkeypatch.setattr(lock, "now", lambda: __import__("datetime").datetime.fromisoformat("2026-10-25T10:05:00+02:00"))
    api = "mcp__plugin_edakit_easyeda__easyeda_api_call"
    for tool, tool_input, denied in (
            ("mcp__plugin_edakit_easyeda__easyeda_schematic_search_device", {"key": "C165948"}, False),
            ("mcp__easyeda__easyeda_schematic_search_device", None, False),
            (api, {"path": "LIB_Device.search", "args": ["C165948"]}, False),
            (api, {"path": "LIB_Device.get", "args": ["u", "l"]}, False),
            (api, {"path": "LIB_Device.getByLcscIds", "args": [["C165948"]]}, False),   # prefix "LIB_Device.get"
            (api, {"path": "lib_Device.search"}, False),                                # the bridge's lower-case form
            (api, {"path": "PCB_PrimitivePour.create"}, True),
            (api, {"path": "LIB_Device.create"}, True),
            (api, {"path": "LIB_Footprint.openInEditor"}, True),                        # opens a tab
            (api, {"path": "DMT_Project.getCurrentProjectInfo"}, True),
            (api, None, True),
            ("mcp__plugin_edakit_easyeda__easyeda_pcb_add_track", {}, True)):
        assert run_hook(monkeypatch, capsys, "B", tool, tool_input) == denied, (tool, tool_input)
    with lock.state() as s:
        assert s["claim"]["chat"] == "A" and s["claim"]["renewed"] == renewed


def test_library_lookup_takes_no_claim(capsys, monkeypatch):
    assert not run_hook(monkeypatch, capsys, "B", "mcp__easyeda__easyeda_schematic_search_device", {"key": "PMOS"})
    assert not run_hook(monkeypatch, capsys, "B", "mcp__easyeda__easyeda_api_call", {"path": "LIB_Device.search"})
    with lock.state() as s:
        assert s["claim"] is None and s["log"] == []


def test_read_only_lists_are_data():
    assert "schematic_search_device" in lock.READ_ONLY_TOOLS
    assert set(lock.READ_ONLY_API) == {"LIB_Device.search", "LIB_Device.get"}
    assert lock.read_only("easyeda_schematic_search_device")                  # edakit's own client names
    assert lock.read_only("easyeda_api_call", {"path": "LIB_Device.search"})
    assert not lock.read_only("easyeda_api_call", {"path": "LIB_DeviceX.search"})
    assert not lock.read_only("easyeda_pcb_tracks")


def test_edakit_client_skips_the_claim_for_lookups(monkeypatch):
    from edakit import eda
    claims = []
    monkeypatch.setattr(lock, "claim_for_script", lambda **kw: claims.append(kw))
    client = object.__new__(eda.MCPClient)
    client.lock_mode = "auto"
    monkeypatch.setattr(client, "_request", lambda *a, **kw: {"structuredContent": {"ok": True, "devices": []}},
                        raising=False)
    client.call("easyeda_schematic_search_device", key="C165948")
    client.call("easyeda_api_call", path="LIB_Device.search", args=["C165948"], confirmWrite=True)
    assert claims == []
    client.call("easyeda_api_call", path="DMT_Project.getCurrentProjectInfo", args=[], confirmWrite=True)
    client.call("easyeda_pcb_tracks")
    assert len(claims) == 2
