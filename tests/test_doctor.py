"""edakit doctor asks the running bridge what it is: classifiers on canned answers, the bridge part with a fake
server, and --offline."""

import pytest

from edakit import doctor, eda, lock

HEALTH = {"status": "ok", "version": "1.4.0", "bridge_connected": True, "easyeda_version": "3.2.206",
          "extension_version": "1.4.0", "extension_version_mismatch": False, "registry_mismatch": False}
STATUS = {"connected": True, "bridge_version": "1.4.0", "easyeda_version": "3.2.206"}
# DMT_Project.getCurrentProjectInfo: root, data[], board, schematic, page[], page – the original bridge cuts level 6
PAGES = {"uuid": "p1", "friendlyName": "led-bar", "data": [{"name": "Board1", "schematic": {
    "name": "Schematic1", "page": [{"name": "P1", "uuid": "s1"}, {"name": "P2", "uuid": "s2"}]}}]}
CUT = {"uuid": "p1", "friendlyName": "led-bar", "data": [{"name": "Board1", "schematic": {
    "name": "Schematic1", "page": ["[MaxDepth]", "[MaxDepth]"]}}]}


@pytest.fixture(autouse=True)
def state_file(tmp_path, monkeypatch):
    monkeypatch.setenv("EDAKIT_LOCK_FILE", str(tmp_path / "lock.json"))


def levels(lines):
    return [lv for lv, _, _ in lines]


def test_health_check_classifier():
    assert levels(doctor.bridge_lines(STATUS, HEALTH)) == ["OK", "OK", "OK"]
    lines = doctor.bridge_lines(STATUS, {**HEALTH, "registry_mismatch": True})
    assert "WARN" in levels(lines) and any("registry" in t for _, t, _ in lines)
    lines = doctor.bridge_lines(STATUS, {**HEALTH, "extension_version": "1.3.0", "extension_version_mismatch": True})
    warn = [t for lv, t, _ in lines if lv == "WARN"]
    assert len(warn) == 1 and "1.3.0" in warn[0] and "1.4.0" in warn[0]
    lines = doctor.bridge_lines({"connected": False}, {**HEALTH, "bridge_connected": False, "extension_version": None})
    assert levels(lines) == ["WARN"] and "not connected" in lines[0][1]


def test_depth_classifier():
    lv, text, hint = doctor.depth_line(CUT)
    assert lv == "WARN" and "original extension" in text and "bridge-extension-patch.sh" in hint
    assert doctor.depth_line(PAGES)[0] == "OK"
    assert doctor.depth_line(None)[0] == "INFO"                            # start page: no project open
    assert doctor.depth_line({"uuid": "p1", "data": []})[0] == "INFO"      # too shallow to tell


def test_timeout_classifier():
    lv, text, hint = doctor.timeout_line({101: {"BRIDGE_TIMEOUT_MS": "15000"}, 202: {"BRIDGE_TIMEOUT_MS": "120000"}})
    assert lv == "WARN" and "101" in text and "202" in text and "15000" in text and "120000" in text
    lv, text, _ = doctor.timeout_line({101: {}, 202: {"BRIDGE_TIMEOUT_MS": "120000"}})
    assert lv == "WARN" and "15000" in text                                 # the server's default
    assert doctor.timeout_line({101: {"BRIDGE_TIMEOUT_MS": "120000"}, 202: {"BRIDGE_TIMEOUT_MS": "120000"}})[0] == "OK"
    assert doctor.timeout_line({})[0] == "INFO"
    lv, text, _ = doctor.timeout_line({101: {"BRIDGE_TIMEOUT_MS": "120000"}, 202: None})
    assert lv == "OK" and "202" in text                                     # unreadable: named, not guessed


def test_server_environ_from_proc(tmp_path):
    (tmp_path / "4711").mkdir()
    (tmp_path / "4711" / "environ").write_bytes(b"HOME=/h\0BRIDGE_TIMEOUT_MS=120000\0")
    assert doctor.read_environ(4711, proc=tmp_path) == {"HOME": "/h", "BRIDGE_TIMEOUT_MS": "120000"}
    assert doctor.read_environ(4712, proc=tmp_path) is None


PS = ("    PID COMMAND\n"
      "   1000 /opt/apps/easyeda-pro/easyeda-pro --no-sandbox --disable-background-timer-throttling\n"
      "   2001 node /home/u/.easyeda-mcp-pro/runtime/1.4.0/node_modules/easyeda-mcp-pro/dist/index.js\n")


class FakeMCP:
    def __init__(self, project=PAGES):
        self.calls, self.project, self.closed = [], project, False

    def call(self, tool, timeout=130, **args):
        self.calls.append((tool, args.get("path")))
        if tool == "easyeda_bridge_status":
            return STATUS
        if tool == "easyeda_health_check":
            return HEALTH
        if tool == "easyeda_api_call":
            return {"ok": True, "result": self.project}
        raise AssertionError(tool)

    def close(self):
        self.closed = True


def run_doctor(monkeypatch, capsys, argv, fake=None, easyeda_running=True):
    monkeypatch.setattr(doctor, "run", lambda *cmd: (0, PS if easyeda_running else "    PID COMMAND\n")
                        if cmd[0] == "ps" else (0, "v24.1.0") if cmd[0] == "node" else (0, ""))
    monkeypatch.setattr(doctor, "read_environ", lambda pid, proc=None: {"BRIDGE_TIMEOUT_MS": "120000"})
    started = []

    def start(cfg, verbose=False, artifact_dir=None, lock_mode=None):
        started.append(lock_mode)
        if fake is None:
            raise AssertionError("no server may start")
        return fake
    monkeypatch.setattr(eda, "start", start)
    from edakit import cli
    code = cli.main(argv)
    return code, capsys.readouterr().out, started


def test_offline_starts_no_server(project, monkeypatch, capsys):
    monkeypatch.chdir(project.root)
    code, out, started = run_doctor(monkeypatch, capsys, ["doctor", "--offline"])
    assert started == []
    assert code == (1 if "FAIL" in out else 0)                              # exit as today: 1 only for a FAIL
    assert "BRIDGE_TIMEOUT_MS" in out and "1 easyeda-mcp-pro server process(es)" in out
    assert "extension" not in out and "return depth" not in out


def test_no_easyeda_no_server(project, monkeypatch, capsys):
    monkeypatch.chdir(project.root)
    code, out, started = run_doctor(monkeypatch, capsys, ["doctor"], easyeda_running=False)
    assert started == [] and "bridge not asked" in out


def test_bridge_part_reports_and_claims_nothing(project, monkeypatch, capsys):
    monkeypatch.chdir(project.root)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "me")
    fake = FakeMCP(CUT)
    code, out, started = run_doctor(monkeypatch, capsys, ["doctor"], fake=fake)
    assert started == ["off"] and fake.closed
    assert "OK    bridge connected" in out and "original extension" in out
    assert ("easyeda_api_call", "DMT_Project.getCurrentProjectInfo") in fake.calls
    with lock.state() as s:
        assert s["claim"] is None                                           # doctor takes no claim


def test_depth_not_probed_while_another_session_holds(project, monkeypatch, capsys):
    monkeypatch.chdir(project.root)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "me")
    with lock.state() as s:
        lock.claim(s, "other-session", "route all")
    fake = FakeMCP()
    code, out, started = run_doctor(monkeypatch, capsys, ["doctor"], fake=fake)
    assert [t for t, _ in fake.calls] == ["easyeda_bridge_status", "easyeda_health_check"]
    assert "return depth not probed: EasyEDA held by other-s" in out
    with lock.state() as s:
        assert s["claim"]["chat"] == "other-session"


def test_depth_probed_under_own_claim(project, monkeypatch, capsys):
    monkeypatch.chdir(project.root)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "me")
    with lock.state() as s:
        lock.claim(s, "me", "pcb round")
    code, out, _ = run_doctor(monkeypatch, capsys, ["doctor"], fake=FakeMCP())
    assert "OK    patched extension" in out
