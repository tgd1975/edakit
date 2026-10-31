"""`edakit doctor`: is the tool chain ready? Each line OK, WARN or FAIL with what to do. Changes nothing.

Bridge and server problems are almost always one of: Node is not 24.x, an orphaned easyeda-mcp-pro still holds the
bridge port 49620, EasyEDA runs throttled (window covered -> DRC, pours and exports time out), or EasyEDA sits on its
start page with no project open. See handbook/12-troubleshooting.md.

With EasyEDA running (and without --offline) doctor also asks the bridge what it is, through an own server started
without a claim: connected, extension version against the server's, the method registry (easyeda_bridge_status,
easyeda_health_check – both free in the claim), and the return depth (DMT_Project.getCurrentProjectInfo: [MaxDepth]
means the original extension; probed only while the claim is free or the caller's). The servers' BRIDGE_TIMEOUT_MS
come from /proc/<pid>/environ – the server holding the bridge port drops requests after its own timeout.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import eda, lock
from .eda import MCP_SERVER
from .toolchain import is_kicad

PROC = Path("/proc")
DEFAULT_TIMEOUT_MS = 15000  # easyeda-mcp-pro 1.4.0 without BRIDGE_TIMEOUT_MS (src/config/env.ts:68)
ORIGINAL_DEPTH = 5          # levels the original bridge extension returns (normalizeValue(result, 5))
PATCH_HINT = ("build the patched extension of the pinned server (bash edakit/easyeda/bridge-extension-patch.sh), "
              "uninstall the old one in EasyEDA, import, restart EasyEDA (handbook 2.5)")


def run(*cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def read_environ(pid, proc=PROC):
    """The environment of a process from /proc/<pid>/environ, None if it cannot be read."""
    try:
        raw = (Path(proc) / str(pid) / "environ").read_bytes()
    except OSError:
        return None
    return dict(item.split("=", 1) for item in raw.decode(errors="replace").split("\0") if "=" in item)


def timeout_line(envs):
    """(level, text, hint) for the BRIDGE_TIMEOUT_MS of the running servers; envs: pid -> environment or None."""
    if not envs:
        return "INFO", "BRIDGE_TIMEOUT_MS: no easyeda-mcp-pro server running", ""
    values = {pid: env.get("BRIDGE_TIMEOUT_MS") or str(DEFAULT_TIMEOUT_MS) for pid, env in envs.items() if env is not None}
    unread = sorted(pid for pid, env in envs.items() if env is None)
    tail = f"; not readable: pid {', '.join(map(str, unread))}" if unread else ""
    if len(set(values.values())) > 1:
        listing = ", ".join(f"pid {pid} {ms}" + ("" if envs[pid].get("BRIDGE_TIMEOUT_MS") else " (default)")
                            for pid, ms in sorted(values.items()))
        return ("WARN", f"BRIDGE_TIMEOUT_MS differs between the easyeda-mcp-pro servers: {listing}{tail}",
                "the server holding the bridge port drops pending requests after ITS timeout (stale sweep): end the "
                "ones with the other value (pgrep -af easyeda-mcp-pro – tell the other sessions first); they restart "
                "through mcp-server.sh with 120000 (handbook 12)")
    if values:
        return "OK", f"BRIDGE_TIMEOUT_MS {next(iter(values.values()))} ms in all {len(values)} server(s){tail}", ""
    return "INFO", f"BRIDGE_TIMEOUT_MS not compared{tail}", ""


def bridge_lines(status, health):
    """(level, text, hint) lines from easyeda_bridge_status and easyeda_health_check."""
    if not status.get("connected", health.get("bridge_connected")):
        why = status.get("status_error") or health.get("status_error")
        owner = status.get("owner_pid") or health.get("owner_pid")
        return [("WARN", "bridge not connected" + (f": {why}" if why else "") + (f" (port held by pid {owner})" if owner
                                                                                  else ""),
                 "EasyEDA with the project open and Auto-Connect on? Otherwise MCP Bridge -> Connect; without the menu "
                 "restart EasyEDA (handbook 12)")]
    lines = [("OK", f"bridge connected: EasyEDA {status.get('easyeda_version') or health.get('easyeda_version') or '?'}",
              "")]
    server, ext = health.get("version") or "?", health.get("extension_version")
    if health.get("extension_version_mismatch"):
        lines.append(("WARN", f"bridge extension {ext} against server {server}", PATCH_HINT))
    elif ext:
        lines.append(("OK", f"bridge extension {ext} = server {server}", ""))
    else:
        lines.append(("INFO", f"bridge extension version unknown (server {server})", ""))
    if health.get("registry_mismatch"):
        lines.append(("WARN", "method registry of the bridge extension differs from the server's", PATCH_HINT))
    else:
        lines.append(("OK", "method registry of extension and server match", ""))
    return lines


def nesting(o):
    if isinstance(o, dict):
        return 1 + max((nesting(v) for v in o.values()), default=0)
    if isinstance(o, list):
        return 1 + max((nesting(v) for v in o), default=0)
    return 0


def depth_line(answer):
    """(level, text, hint) for the answer of DMT_Project.getCurrentProjectInfo: [MaxDepth] = the original extension."""
    if "[MaxDepth]" in json.dumps(answer, ensure_ascii=False):
        return ("WARN", f"original extension: answers cut after {ORIGINAL_DEPTH} levels ([MaxDepth]), DRC details "
                "unreadable", PATCH_HINT)
    if nesting(answer) > ORIGINAL_DEPTH:
        return "OK", f"patched extension: answers deeper than {ORIGINAL_DEPTH} levels (DRC details readable)", ""
    if not answer:
        return "INFO", "return depth not shown: no project open (EasyEDA on its start page)", "open the project, run again"
    return "INFO", "return depth not shown: the project's answer is too shallow to tell", ""


def wait_connected(mcp, seconds=20):
    """A fresh server needs a few seconds until the bridge connects (Auto-Connect or as follower of a running one)."""
    deadline = time.monotonic() + seconds
    while True:
        status = mcp.call("easyeda_bridge_status")
        if status.get("connected") or time.monotonic() > deadline:
            return status
        time.sleep(2)


def bridge_part(cfg, line, verbose=False):
    """Ask the running bridge through an own server that claims nothing; the depth probe only under a free or own
    claim."""
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    with tempfile.TemporaryDirectory(prefix="edakit-doctor-") as tmp:
        try:
            mcp = eda.start(cfg, verbose=verbose, artifact_dir=tmp, lock_mode="off")
        except (eda.MCPError, OSError) as e:
            line("WARN", f"bridge not asked: the own easyeda-mcp-pro did not start ({e})",
                 "bash edakit/easyeda/mcp-server.sh doctor (handbook 12)")
            return
        try:
            status = wait_connected(mcp)
            for level, text, hint in bridge_lines(status, mcp.call("easyeda_health_check")):
                line(level, text, hint)
            if not status.get("connected"):
                return
            with lock.state() as s:
                c = lock.valid_claim(s)
            if c and c["chat"] != session:
                line("INFO", f"return depth not probed: EasyEDA {lock.describe(c, session)}")
            else:
                line(*depth_line(eda.api(mcp, "DMT_Project.getCurrentProjectInfo", timeout=60)))
        except eda.MCPError as e:
            line("WARN", f"bridge: {e}")
        finally:
            mcp.close()


def kicad_line(line):
    """kicad-cli on the PATH (or KICAD_CLI) and its major version: KiCad 10, from KiCad's PPA for Ubuntu."""
    from .toolchain.kicad import cli
    try:
        version = cli.version()
    except cli.CliError as e:
        line("FAIL", "kicad-cli: missing", f"{e}")
        return
    ok = cli.major(version) == cli.MAJOR
    line("OK" if ok else "WARN", f"KiCad {version} (kicad-cli: {cli.binary()})",
         "" if ok else f"edakit writes and reads for KiCad {cli.MAJOR}: sudo add-apt-repository "
         f"ppa:kicad/kicad-{cli.MAJOR}.0-releases && sudo apt install kicad (handbook 2)")


ODB_TOOL = "name: 'easyeda_export_odb'"     # the tool odb-tool-patch.mjs adds to the server (handbook 2.5)


def odb_line(cfg, runtime, installed):
    """(level, text, hint) for the ODB++ export: the tool in the installed server – needed only with a maker of
    [cart] makers that takes ODB++ (AISLER, SYNC.odb); the bridge's handler is in the extension bridge-extension-patch.sh
    builds, and SYNC.odb names an extension without it."""
    from .release import fab
    need = cfg is not None and bool(fab.odb_takers(cfg))
    tools = Path(runtime) / "node_modules/easyeda-mcp-pro/dist/tools/L1_export.js"
    has = installed and tools.exists() and ODB_TOOL in tools.read_text(encoding="utf-8", errors="replace")
    if has:
        return "OK", "ODB++ export: easyeda_export_odb in the server; the bridge needs the extension with ODB++ " \
                     "(bridge-extension-patch.sh)", ""
    return ("WARN" if need else "INFO", "ODB++ export: easyeda_export_odb not in the server"
            + (" – a maker of [cart] makers takes ODB++ (SYNC.odb)" if need else ""),
            "mcp-server.sh patches it in on its next start (odb-tool-patch.mjs); then build and import the bridge "
            "extension with ODB++ (bash edakit/easyeda/bridge-extension-patch.sh, handbook 2.5)" if need else "")


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
    kc = cfg is not None and is_kicad(cfg)
    if kc:                            # the KiCad tool chain: kicad-cli instead of Node, server, bridge and EasyEDA
        easyeda = []
        kicad_line(line)
    else:
        code, out = run("node", "-v")
        major = re.match(r"v(\d+)", out or "")
        line("OK" if major and major.group(1) == "24" else "FAIL", f"Node {out or 'missing'}",
             "" if major and major.group(1) == "24" else "easyeda-mcp-pro 1.4.0 needs Node 24.x (nvm install 24)")
        version = re.search(r'EASYEDA_MCP_VERSION:-([\d.]+)', MCP_SERVER.read_text()).group(1)
        runtime = os.environ.get("EASYEDA_MCP_RUNTIME_DIR") or os.path.expanduser(f"~/.easyeda-mcp-pro/runtime/{version}")
        installed = os.path.exists(os.path.join(runtime, "node_modules/easyeda-mcp-pro/dist/index.js"))
        line("OK" if installed else "WARN", f"easyeda-mcp-pro {version} in {runtime}",
             "" if installed else "installs itself on the first start of mcp-server.sh")
        line(*odb_line(cfg, runtime, installed))
        code, ps = run("ps", "-eo", "pid,args")
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
        if PROC.is_dir():
            pids = [int(p.split()[0]) for p in servers if p.split()[0].isdigit()]
            line(*timeout_line({pid: read_environ(pid) for pid in pids}))
        else:
            line("INFO", "BRIDGE_TIMEOUT_MS not compared: no /proc on this system")
        code, ss = run("ss", "-ltnp")
        port = [x for x in ss.splitlines() if ":49620" in x]
        line("OK" if port else "WARN", f"bridge port 49620: {'listening' if port else 'not listening'}",
             "" if port else "normal while no server runs; the first easyeda tool call starts one")
        if os.environ.get("ELECTRON_RUN_AS_NODE"):
            line("WARN", "ELECTRON_RUN_AS_NODE is set in this shell",
                 "EasyEDA started from here behaves like Node ('bad option: --no-sandbox'): env -u ELECTRON_RUN_AS_NODE …")
    line("OK" if shutil.which("ngspice") else "FAIL", f"ngspice: {shutil.which('ngspice') or 'missing'}",
         "" if shutil.which("ngspice") else "sudo apt install ngspice (stage E)")
    pdftotext = shutil.which("pdftotext")
    line("OK" if pdftotext else "WARN", f"pdftotext: {pdftotext or 'missing'}",
         "" if pdftotext else "sudo apt install poppler-utils – without it edakit part fetch keeps datasheets "
         "unchecked (text layer, part number)")
    from .route import FR_BIN
    fr = os.environ.get("FREEROUTING_BIN") or os.environ.get("FREEROUTING_JAR") or (str(FR_BIN) if FR_BIN.exists() else "")
    line("OK" if fr else "WARN", f"Freerouting: {fr or 'not yet downloaded'}",
         "" if fr else "`edakit route route` downloads the pinned release on Linux x64; elsewhere set FREEROUTING_JAR")
    line("OK" if shutil.which("uv") else "WARN", f"uv: {shutil.which('uv') or 'missing'}")
    if not getattr(args, "offline", False) and not kc:
        if easyeda:
            bridge_part(cfg, line, getattr(args, "verbose", False))
        else:
            line("INFO", "bridge not asked: EasyEDA does not run")
    with lock.state() as s:
        print("INFO  " + lock.status_text(s, os.environ.get("CLAUDE_CODE_SESSION_ID")).replace("\n", "\n      "))
    return 1 if bad else 0
