"""T.25 of circuit-dsl-toolchain.md: the language server's functions – diagnostics, definition, hover, completion,
formatting – on the fixture, without the protocol; one smoke test over pipes where pygls is installed."""

import json
import subprocess
import sys

import pytest
from test_lang_use import step

from edakit.lang import server


def text_of(p):
    return p.graph_file.read_text(encoding="utf-8")


def at(text, needle, offset=0):
    """(line, col) of a needle, 0-based."""
    for k, ln in enumerate(text.splitlines()):
        if needle in ln:
            return k, ln.index(needle) + offset
    raise AssertionError(needle)


def test_diagnostics_of_a_clean_source_and_of_errors(project_circuit):
    text = text_of(project_circuit)
    assert [d for d in server.diagnostics(project_circuit.graph_file, text) if d["severity"] == "error"] == []
    bad = text.replace("U2.R-EXT R1.1", "U2.R-EXTRA R1.1")
    [d] = server.diagnostics(project_circuit.graph_file, bad)
    assert d["severity"] == "error" and "names no pin of U2" in d["message"] and d["line"] == at(bad, "net REXT")[0]


def test_a_finding_of_the_engines_at_its_statement(project_circuit):
    text = text_of(project_circuit).replace("net LED_LE 0..3.4 V U1.GP4 (locked) U2.LE(ED1)\n  accept LVL.undefined",
                                            "net LED_LE 0..3.4 V U1.GP4 (locked) U2.LE(ED1)\n  notes")
    found = server.diagnostics(project_circuit.graph_file, text)
    assert any(d["code"] == "LVL.undefined" and d["line"] == at(text, "net LED_LE")[0] for d in found), found


def test_definition(project_circuit, project):
    text = text_of(project_circuit)
    file, _ = server.definition(project_circuit.graph_file, text, *at(text, "U2.SDI", 1))
    assert file.endswith("C90107.json")
    path = step(project)
    t2 = path.read_text()
    assert server.definition(path, t2, *at(t2, "use led step1", 5)) == (str(path), at(t2, "def led")[0])
    line, col = at(text, "net LED_SDI", 5)
    assert server.definition(project_circuit.graph_file, text, line, col)[1] == line
    assert server.definition(project_circuit.graph_file, text, *at(text, "notes", 1)) is None


def test_hover(project_circuit):
    text = text_of(project_circuit)
    h = server.hover(project_circuit.graph_file, text, *at(text, "U1.GP3", 2))
    assert "**U1**" in h and "pin 5: GP3" in h and "net LED_SDI" in h
    h = server.hover(project_circuit.graph_file, text, *at(text, "net VIN", 5))
    assert h.startswith("**VIN** – 0 … 5.5 V")


def test_completion(project_circuit):
    text = text_of(project_circuit)
    line, col = at(text, "U2.SDI", 3)
    got = server.completion(project_circuit.graph_file, text, line, col)
    assert "SDI" in got and "CLK" in got
    lines = text.splitlines()
    lines.append("use ")
    t2 = "\n".join(lines)
    assert "led" in server.completion(project_circuit.graph_file, t2, len(lines) - 1, 4)
    assert "LIM.v" in server.completion(project_circuit.graph_file, "accept ", 0, 7)


def test_formatting(project_circuit):
    text = text_of(project_circuit)
    assert server.formatted(project_circuit.graph_file, text) == text
    assert server.formatted(project_circuit.graph_file, text.replace("part R2 ", "part  R2 ")) == text


def test_without_pygls_the_command_names_the_extra(capsys, monkeypatch):
    import builtins
    real = builtins.__import__

    def no_pygls(name, *a, **k):
        if name.startswith(("pygls", "lsprotocol")):
            raise ImportError(name)
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_pygls)
    assert server.main() == 1 and "extra lsp" in capsys.readouterr().err


def _pygls():
    try:
        import pygls  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _pygls(), reason="pygls is not installed (the extra lsp)")
def test_the_server_answers_over_pipes(project_circuit):
    proc = subprocess.Popen([sys.executable, "-m", "edakit.cli", "lsp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def send(obj):
        body = json.dumps(obj).encode()
        proc.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        proc.stdin.flush()

    def receive():
        head = b""
        while not head.endswith(b"\r\n\r\n"):
            head += proc.stdout.read(1)
        n = int(head.split(b"Content-Length:")[1].split(b"\r\n")[0])
        return json.loads(proc.stdout.read(n))
    uri = project_circuit.graph_file.resolve().as_uri()
    send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"capabilities": {}}})
    assert "capabilities" in receive()["result"]
    send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
    bad = text_of(project_circuit).replace("U2.R-EXT R1.1", "U2.R-EXTRA R1.1")
    send({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {
        "uri": uri, "languageId": "circuit", "version": 1, "text": bad}}})
    msg = receive()
    while msg.get("method") != "textDocument/publishDiagnostics":
        msg = receive()
    assert any("names no pin of U2" in d["message"] for d in msg["params"]["diagnostics"])
    send({"jsonrpc": "2.0", "id": 2, "method": "shutdown"})
    receive()
    send({"jsonrpc": "2.0", "method": "exit"})
    proc.wait(timeout=20)
