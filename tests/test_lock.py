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
