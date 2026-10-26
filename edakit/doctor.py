"""`edakit doctor`: is the tool chain ready? Each line OK, WARN or FAIL with what to do. Changes nothing.

Bridge and server problems are almost always one of: Node is not 24.x, an orphaned easyeda-mcp-pro still holds the
bridge port 49620, EasyEDA runs throttled (window covered -> DRC, pours and exports time out), or EasyEDA sits on its
start page with no project open. See handbook/12-troubleshooting.md.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

from . import lock
from .eda import MCP_SERVER


def run(*cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def main(cfg, args):
    bad = 0

    def line(level, what, hint=""):
        nonlocal bad
        bad += level == "FAIL"
        print(f"{level:<5} {what}" + (f"\n      -> {hint}" if hint else ""))
    error = getattr(args, "config_error", "")
    line("OK" if cfg else "FAIL", f"edakit.toml: {cfg.path if cfg else 'refused' if error else 'not found'}",
         "" if cfg else error.replace("\n", "\n         ") if error and "no edakit.toml found" not in error
         else "create one (/edakit:new-project, handbook/10-reference.md)")
    line("OK" if sys.version_info >= (3, 11) else "FAIL", f"Python {sys.version.split()[0]}")
    code, out = run("node", "-v")
    major = re.match(r"v(\d+)", out or "")
    line("OK" if major and major.group(1) == "24" else "FAIL", f"Node {out or 'missing'}",
         "" if major and major.group(1) == "24" else "easyeda-mcp-pro 1.4.0 needs Node 24.x (nvm install 24)")
    version = re.search(r'EASYEDA_MCP_VERSION:-([\d.]+)', MCP_SERVER.read_text()).group(1)
    runtime = os.environ.get("EASYEDA_MCP_RUNTIME_DIR") or os.path.expanduser(f"~/.easyeda-mcp-pro/runtime/{version}")
    installed = os.path.exists(os.path.join(runtime, "node_modules/easyeda-mcp-pro/dist/index.js"))
    line("OK" if installed else "WARN", f"easyeda-mcp-pro {version} in {runtime}",
         "" if installed else "installs itself on the first start of mcp-server.sh")
    code, ps = run("ps", "-eo", "args")
    easyeda = [p for p in ps.splitlines() if "easyeda-pro" in p and "grep" not in p]
    line("OK" if easyeda else "WARN", f"EasyEDA Pro running: {'yes' if easyeda else 'no'}",
         "" if easyeda else "start it (handbook/02-setup.md, unthrottled launcher)")
    if easyeda:
        throttled = not any("disable-background-timer-throttling" in p for p in easyeda)
        line("WARN" if throttled else "OK", "EasyEDA unthrottled" if not throttled else "EasyEDA runs THROTTLED",
             "save, quit and start it with --disable-background-timer-throttling --disable-renderer-backgrounding "
             "--disable-backgrounding-occluded-windows (handbook/02-setup.md)" if throttled else "")
    servers = [p for p in ps.splitlines() if "easyeda-mcp-pro" in p and "node" in p]
    line("OK" if len(servers) <= 3 else "WARN", f"{len(servers)} easyeda-mcp-pro server process(es)",
         "orphans keep port 49620: pgrep -af easyeda-mcp-pro, end the stale ones" if len(servers) > 3 else "")
    code, ss = run("ss", "-ltnp")
    port = [x for x in ss.splitlines() if ":49620" in x]
    line("OK" if port else "WARN", f"bridge port 49620: {'listening' if port else 'not listening'}",
         "" if port else "normal while no server runs; the first easyeda tool call starts one")
    if os.environ.get("ELECTRON_RUN_AS_NODE"):
        line("WARN", "ELECTRON_RUN_AS_NODE is set in this shell",
             "EasyEDA started from here behaves like Node ('bad option: --no-sandbox'): env -u ELECTRON_RUN_AS_NODE …")
    line("OK" if shutil.which("ngspice") else "FAIL", f"ngspice: {shutil.which('ngspice') or 'missing'}",
         "" if shutil.which("ngspice") else "sudo apt install ngspice (stage E)")
    from .route import FR_BIN
    fr = os.environ.get("FREEROUTING_BIN") or os.environ.get("FREEROUTING_JAR") or (str(FR_BIN) if FR_BIN.exists() else "")
    line("OK" if fr else "WARN", f"Freerouting: {fr or 'not yet downloaded'}",
         "" if fr else "`edakit route route` downloads the pinned release on Linux x64; elsewhere set FREEROUTING_JAR")
    line("OK" if shutil.which("uv") else "WARN", f"uv: {shutil.which('uv') or 'missing'}")
    with lock.state() as s:
        print("INFO  " + lock.status_text(s, os.environ.get("CLAUDE_CODE_SESSION_ID")).replace("\n", "\n      "))
    return 1 if bad else 0
