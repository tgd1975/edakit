"""EasyEDA claim: one Claude session at a time drives EasyEDA on this machine.

Every script and most MCP tools switch EasyEDA's active tab. A second session working at the same time pulls the tab
away and breaks the first session's run, or writes into the wrong document. (In the project this toolkit comes from,
a 20-minute routing run was lost that way.) So EasyEDA is claimed per session, separately from anything git does:

    edakit lock                       who holds EasyEDA (exit 3 if another session does)
    edakit lock claim --note "route"  before a series of runs (renews an own claim)
    edakit lock release               afterwards, also after an abort
    edakit lock yield <chat>          let a short run of another session in between two own runs; when that session
                                      releases (or its claim expires) EasyEDA goes back to this one, not to a third
    edakit lock hook                  PreToolUse hook for the easyeda MCP tools (reads the hook JSON from stdin)

The first EasyEDA access of a session claims automatically – the hook for MCP tools, `edakit` commands for scripts –
and every access renews it. A claim expires after 15 minutes without EasyEDA access. Tools that only ask about the
server or the connection are allowed without a claim. Sessions are told apart by CLAUDE_CODE_SESSION_ID (or the
hook's session_id); without one (a terminal) nothing is claimed.

State: $XDG_STATE_HOME/edakit/easyeda-lock.json (default ~/.local/state/edakit/), guarded with flock – one file for
the whole machine, because there is one EasyEDA per machine, whatever project it has open.
Exit codes: 0 = ok, 3 = held by another session / denied, 1 = error.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import json
import os
import sys
from pathlib import Path

EXPIRE_MIN = 15
LOG_MAX = 100
# MCP tools that only query the server and the connection – allowed without a claim
FREE = ("bridge_status", "health_check", "get_capabilities", "get_feature_flags", "get_server_config",
        "get_tool_profiles", "api_inventory", "catalog_list", "observability_report")


def state_file():
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    return Path(os.environ.get("EDAKIT_LOCK_FILE") or base / "edakit" / "easyeda-lock.json")


def now():
    return dt.datetime.now().astimezone()


def age_min(stamp):
    return (now() - dt.datetime.fromisoformat(stamp)).total_seconds() / 60


def short(session):
    return (session or "?")[:8]


@contextlib.contextmanager
def state():
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        try:
            s = json.loads(path.read_text()) if path.exists() else {}
        except json.JSONDecodeError:
            s = {}
        s.setdefault("claim", None)
        s.setdefault("log", [])
        yield s
        path.write_text(json.dumps(s, indent=1, ensure_ascii=False))


def log(s, session, text):
    entry = {"t": now().isoformat(timespec="seconds"), "chat": short(session), "session": session, "text": text}
    s["log"] = (s["log"] + [entry])[-LOG_MAX:]


def valid_claim(s):
    """The current claim, or None if there is none or it expired. An expired claim of a yielded run goes back."""
    c = s["claim"]
    if not c:
        return None
    if age_min(c["renewed"]) <= EXPIRE_MIN:
        return c
    if c.get("back"):
        return give_back(s, "claim of the guest expired")
    return None


def give_back(s, why):
    c = s["claim"]
    back = c.pop("back")
    t = now().isoformat(timespec="seconds")
    s["claim"] = {**back, "renewed": t}
    log(s, c["chat"], f"EasyEDA back to {short(back['chat'])} ({why})")
    return s["claim"]


def describe(c, me=None):
    if not c:
        return "free"
    who = "you" if c["chat"] == me else short(c["chat"])
    text = f"held by {who} since {c['since'][11:16]}, last access {c['renewed'][11:16]}"
    if c.get("note"):
        text += f" – {c['note']}"
    if c.get("cwd"):
        text += f" ({c['cwd']})"
    if c.get("back"):
        text += f"; goes back to {short(c['back']['chat'])} afterwards"
    return text


def claim(s, session, note=None, auto=False, cwd=None):
    """Claim or renew. Returns None or the reason for refusing."""
    c = valid_claim(s)
    if c and c["chat"] != session:
        return (f"EasyEDA is {describe(c, session)}. Wait for its `edakit lock release` (or 15 min without EasyEDA "
                "access), or ask that session (ListAgents -> SendMessage) whether it lets you in with `edakit lock "
                "yield`.")
    t = now().isoformat(timespec="seconds")
    if c:
        c["renewed"] = t
        if note and not auto:
            c["note"] = note
        return None
    old = s["claim"]
    if old and old["chat"] != session:
        log(s, session, f"took over an expired claim ({describe(old, session)})")
    s["claim"] = {"chat": session, "since": t, "renewed": t, "note": note, "cwd": cwd or os.getcwd()}
    log(s, session, "EasyEDA claimed" + (" (automatic)" if auto else "") + (f": {note}" if note else ""))
    return None


def release(s, session, note=None):
    c = valid_claim(s)
    if c and c["chat"] != session and (c.get("back") or {}).get("chat") == session:
        del c["back"]  # the one who yielded gives up: after the guest EasyEDA becomes free
        log(s, session, f"gives up EasyEDA after {short(c['chat'])}")
        return f"EasyEDA becomes free after {short(c['chat'])}"
    if c and c["chat"] != session:
        return None
    if c and c.get("back"):
        back = give_back(s, "done" + (f": {note}" if note else ""))
        return f"EasyEDA back to {short(back['chat'])}"
    if s["claim"]:
        s["claim"] = None
        log(s, session, "EasyEDA released" + (f": {note}" if note else ""))
    return "EasyEDA free"


def yield_to(s, session, other, note=None):
    c = valid_claim(s)
    if not c or c["chat"] != session:
        return None, "you do not hold EasyEDA"
    if c.get("back"):
        return None, "EasyEDA is already lent"
    t = now().isoformat(timespec="seconds")
    s["claim"] = {"chat": other, "since": t, "renewed": t, "note": note or "short run", "cwd": None,
                  "back": {"chat": session, "since": c["since"], "note": c.get("note"), "cwd": c.get("cwd")}}
    log(s, session, f"lets {short(other)} in" + (f": {note}" if note else ""))
    return s["claim"], None


def status_text(s, session):
    lines = [f"EasyEDA: {describe(valid_claim(s), session)}"]
    for e in s["log"][-8:]:
        lines.append(f"  {e['t'][5:16].replace('T', ' ')} {e['chat']}: {e['text']}")
    return "\n".join(lines)


def tool_name(tool):
    """mcp__easyeda__easyeda_x or mcp__plugin_edakit_easyeda__easyeda_x -> x."""
    return tool.split("__", 2)[-1].removeprefix("easyeda_") if tool.startswith("mcp__") else tool


def is_easyeda_tool(tool):
    if not tool.startswith("mcp__"):
        return False
    server = tool.split("__")[1]
    return server == "easyeda" or server.endswith("_easyeda")


def hook():
    data = json.load(sys.stdin)
    session, tool = data.get("session_id"), data.get("tool_name", "")
    if not session or not is_easyeda_tool(tool) or tool_name(tool) in FREE:
        return 0
    with state() as s:
        reason = claim(s, session, tool_name(tool), auto=True, cwd=data.get("cwd"))
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": f"edakit lock: {reason}"}}))
    return 0


_RENEWED = [0.0]


def claim_for_script(renew=False, note=None, mode="auto"):
    """Called by edakit before it touches EasyEDA. Exits with the reason if another session holds EasyEDA."""
    import time
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if mode == "off" or not session:
        return
    if renew and time.monotonic() - _RENEWED[0] < 60:
        return
    _RENEWED[0] = time.monotonic()
    note = note or " ".join(["edakit", *sys.argv[1:3]])[:80]
    with state() as s:
        reason = claim(s, session, note, auto=True)
    if reason:
        raise SystemExit(f"edakit lock: {reason}")


def main(args):
    if args.action == "hook":
        return hook()
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    with state() as s:
        if args.action == "status":
            print(status_text(s, session))
            c = valid_claim(s)
            return 3 if c and c["chat"] != session else 0
        if not session:
            print("no CLAUDE_CODE_SESSION_ID – nothing claimed (terminal use). " + status_text(s, None))
            return 0
        if args.action == "claim":
            reason = claim(s, session, args.note)
            print(f"HELD: {reason}" if reason else f"OK: EasyEDA {describe(s['claim'], session)}")
            return 3 if reason else 0
        if args.action == "release":
            msg = release(s, session, args.note)
            if msg is None:
                print(f"not your claim: EasyEDA {describe(valid_claim(s), session)}")
                return 3
            print(f"OK: {msg}")
            return 0
        if args.action == "yield":
            if not args.chat:
                print("yield needs the session id (prefix) of the other chat")
                return 1
            other = next((e["session"] for e in reversed(s["log"]) if (e.get("session") or "").startswith(args.chat)),
                         args.chat)
            c, err = yield_to(s, session, other, args.note)
            print(f"refused: {err}" if err else f"OK: EasyEDA lent to {short(other)}, comes back afterwards")
            return 3 if err else 0
    return 1


if __name__ == "__main__":  # the plugin hook runs this file directly (stdlib only, no uv start-up per tool call)
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("action", nargs="?", default="status", choices=["status", "claim", "release", "yield", "hook"])
    ap.add_argument("chat", nargs="?")
    ap.add_argument("--note")
    ap.add_argument("--auto", action="store_true")
    sys.exit(main(ap.parse_args()))
