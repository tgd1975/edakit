---
name: start
description: Get EasyEDA Pro and the MCP bridge ready, watch long EasyEDA runs and recover cleanly after a crash. Use before any work in EasyEDA (schematic, PCB, edakit commands that touch EasyEDA), when the bridge does not answer, the easyeda MCP server is missing, EasyEDA crashed or hangs, or a run needs a click in EasyEDA's GUI.
---

# EasyEDA ready, long runs, crashes

Background and every API quirk: `${CLAUDE_PLUGIN_ROOT}/handbook/02-setup.md`, `09-easyeda-api.md`,
`12-troubleshooting.md`. Here only the procedure.

## 1. Readiness

1. `edakit doctor 2>&1 | cat` – Node 24, easyeda-mcp-pro, EasyEDA running **unthrottled**, bridge port, ngspice,
   Freerouting, who holds EasyEDA. Fix every FAIL before going on.
2. **Unthrottled:** if doctor says "THROTTLED", DRC, pour fills and exports time out as soon as another window covers
   EasyEDA. Save, quit EasyEDA and start it with `--disable-background-timer-throttling --disable-renderer-backgrounding
   --disable-backgrounding-occluded-windows` (handbook 02, the desktop launcher). From a shell started by VS Code or
   Claude Code always `env -u ELECTRON_RUN_AS_NODE setsid <easyeda-pro> --no-sandbox …` – the variable makes EasyEDA
   behave like Node. Restarting EasyEDA yourself is fine; save first.
3. **Bridge:** `easyeda_bridge_status` must say `connected: true`. The first call starts the server, Auto-Connect then
   connects within seconds, also after an EasyEDA crash. Only if that fails, ask the user once to click
   *MCP Bridge → Connect* (the patched bridge sometimes shows no menu; then restart EasyEDA – Auto-Connect stays on).
4. **MCP tools missing in this session:** orphaned servers? `pgrep -af easyeda-mcp-pro`, `ss -ltnp | grep 4962`. End
   stale ones (tell other sessions first). The user reconnects with `/mcp` → easyeda; Claude cannot do that itself.
5. **Project open:** `easyeda_api_call` `DMT_Project.getCurrentProjectInfo` (`confirmWrite: true`, also for reads).
   Focus `tab_page1` = start page, every `DMT_*` returns null. edakit reopens the project by the UUID it remembered
   (`<artifacts>/easyeda_project.json`); the very first time the user opens it once.
6. **Claim EasyEDA** before a series of runs: `edakit lock claim --note "<what>"`, afterwards `edakit lock release`
   (also after an abort). The plugin hook claims automatically on the first EasyEDA MCP tool and refuses tools while
   another session holds it; edakit commands do the same. **Never run two EasyEDA jobs at the same time**, not even
   from one session – they switch the active tab and write into the wrong document. A run under 5 minutes on another
   document may be let in between two runs of the holder: the holder runs `edakit lock yield <session>`; when the
   guest releases, EasyEDA goes back to the holder.
7. **Reference schematic still equal to the graph** (seconds): `edakit schematic check 2>&1 | cat`. A generated
   template once drifted (one pin suddenly on two nets) without anyone touching it; regenerating fixed it. Check before
   every gate run, not only at the start.

## 2. Long runs

- Start runs that take minutes in the background and show progress (step n/m, minutes, which step takes longest).
  Do not poll; wait for the notification or watch the log with a Monitor.
- **Waiting for a running process:** never `pgrep -f <pattern>` in a loop – the loop's own shell matches the pattern
  and it never ends (cost 10 minutes several times). Write PID and an end line instead:
  `( edakit route all 2>&1 | cat > $LOG; echo "END exit ${PIPESTATUS[0]}" >> $LOG ) & echo $! > $LOG.pid`, and wait with
  `until grep -q "^END exit" $LOG || ! kill -0 $(cat $LOG.pid) 2>/dev/null; do sleep 15; done`.
- **Route only with `edakit route all`** (Freerouting, exit 0 = DRC 0), never with EasyEDA's autorouter: it throws away
  its whole result when anything fails.
- **DRC only after save and reload** (`edakit route reload`): right after API changes it reports false connection errors.
- Auto-layout and pour fills keep running after the bridge timeout; judge the end by stable numbers
  (`edakit pcb autolayout` does that).
- A canvas capture may show a stale state. If an image is byte-identical to the previous one, do not trust it.
- `uv` installed as a snap: `edakit … 2>&1 | cat`, otherwise it exits 120 without output inside Claude Code.

## 3. Dialogs in EasyEDA's GUI

Some things only a human can click (e.g. after parts were newly placed in the schematic, the DRC shows "Netlist Error –
Import Changes" until the import view was opened once). Avoid dialogs: parts go into the PCB with
`edakit pcb parts --write`, nets with `edakit pcb nets --write`. edakit compares schematic and PCB when the DRC has
that item: "EasyEDA waits for the import acknowledgement" (exit 3 of `route all|drc` and `silk apply|check`, a fail
row of L-3) means nothing differs and only the click is left; a list of parts or pads means fix those first, do not
ask for the click. If a click is unavoidable:

1. Prepare everything so that the click is a plain **OK** – never ask the user to read, copy or judge dialog contents.
2. Do all other work first; the click comes last.
3. Tell the user in one line what will be needed and ask them to say when they are there. Do not ask for the click yet.
4. `edakit lock release --note "waiting for a click: <what>"` – no DRC every minute meanwhile, that would hold EasyEDA.
5. When the user answers: claim again (or ask the holder to let you in), then "click now: <tab> → <button>".

Reason: a click while another session's script runs brings another tab to the front, and the script may write into
the wrong document.

## 4. After a crash

Known causes: V8 out-of-memory on long runs and big `batch_write` blocks (edakit writes 40 operations per call), many
read calls in a row.

1. Start EasyEDA yourself (1.2), let edakit reopen the project, wait for Auto-Connect. Then section 1.
2. **Find out the state, do not guess.** Unsaved work is gone. Count: `easyeda_schematic_components`,
   `easyeda_pcb_components`, `easyeda_pcb_tracks`; `edakit schematic check`, `edakit pcb nets`.
3. Resume: edakit commands are idempotent and replace what they draw. Run the broken step completely again, not from
   its middle. Exception: `edakit pcb dump` turns every part to 0°/TOP – afterwards always `pcb apply` and the
   auto-layout.
4. Second crash in the same step: smaller blocks or split the step, instead of a third try.
5. Save after success and report the state in 2–3 lines.
