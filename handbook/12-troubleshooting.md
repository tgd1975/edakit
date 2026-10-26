# 12 Troubleshooting

Start with `edakit doctor`.

| Symptom | Cause | Fix |
|---|---|---|
| `easyeda_bridge_status`: not connected | no server ran yet, or EasyEDA was restarted | the first tool call starts the server; Auto-Connect connects within seconds. Otherwise *MCP Bridge → Connect*; with the patched bridge the menu may be missing – restart EasyEDA, Auto-Connect stays on |
| MCP tools missing in the session | the server did not start (Node not 24, npm failed) | `bash edakit/easyeda/mcp-server.sh doctor`; then `/mcp` → easyeda (only the user can reconnect) |
| port 49620 busy, "address in use" | an orphaned server (started through npx, or a crashed session) | `pgrep -af easyeda-mcp-pro`, `ss -ltnp \| grep 4962`, end the stale one (tell other sessions) |
| "timed out after 15000ms" or "expired (stale sweep)" | the server holding the port runs with the default 15 s | end all easyeda-mcp-pro processes; they restart with `BRIDGE_TIMEOUT_MS=120000` from mcp-server.sh |
| DRC, pour fill or export hang; EasyEDA hardly busy | EasyEDA runs throttled because its window is covered | save, quit, start unthrottled (chapter 2.6); `edakit doctor` shows it |
| "bad option: --no-sandbox" when starting EasyEDA | `ELECTRON_RUN_AS_NODE` inherited from VS Code | `env -u ELECTRON_RUN_AS_NODE …` |
| every `DMT_*` call returns null | EasyEDA shows its start page (focus `tab_page1`) | open the project; edakit reopens it by its remembered UUID |
| "project is not open and EasyEDA does not list local projects" | edakit never saw the project open | open it once in EasyEDA |
| answers contain `[MaxDepth]`, DRC details empty | original bridge extension | build and import the patched one (chapter 2.5): uninstall old, import, restart |
| `PCB_Drc.check` returns null / undefined | the PCB tab counts as inactive | edakit switches to the start page and back; or click the PCB tab once |
| DRC: many "Connection Error" right after routing | DRC on the unsaved state after many API changes | `edakit route reload`, then DRC – reported 320 → 0 |
| DRC: "Netlist Error – Import Changes" | a part was freshly placed in the schematic | open *Design → Import Changes* once in the GUI (shows "no changes") – the one click |
| pour fill fails: "Cannot read properties of undefined (reading 'length')" | a free pad (tooling hole) is in the PCB | edakit removes tooling holes before filling; by hand: `edakit pcb tooling` after the fill |
| pour status `readback-mismatch` | harmless | look at the number of filled areas per layer |
| "focus lost" / "获取器件关联的所有引脚失败" (pins not readable) | another tab became active (a click, another script) | scripts get the tab back or abort; never run two EasyEDA jobs at once; claim EasyEDA |
| schematic texts come back after a reload | `SCH_PrimitiveText.delete` is not saved | edakit deletes through another primitive class (chapter 9.3) |
| renaming a schematic renamed another one | `modifySchematicName` acts on the active schematic | edakit activates first and checks every name; never delete on a mismatch |
| `edakit schematic check` suddenly reports a pin on two nets in the template | drift of unknown cause in a generated schematic | regenerate the template (`schematic create --save`) |
| `copy` refuses: "belongs to board" | the PCB is linked to the target | correct: use `edakit schematic layout`, which syncs in place |
| Freerouting leaves nets open | order dependence, crowded pads, rules | `route all` retries reshuffled; more passes; more room in the plan; a power plane; lower clearance only within EasyEDA's DRC |
| `route check`: a pour-only net open in groups | tracks of other nets cut its pour into islands | the preview shows the computed pour and where it is cut: a wire keep-out on that layer where the tracks cut it, or more room between the pads there |
| Freerouting routes nothing in part of the board | concave outline as boundary | edakit uses a rectangle + keep-outs; if you write your own DSN, do the same |
| tracks appear where a wire keep-out should be | stale DSN | `route` writes the DSN fresh every time; `route check` uses the same config |
| "outline contains arcs" | outline drawn by hand with arcs | draw it with `edakit pcb apply` (arcs as point lists) |
| `uv run …` exits 120 without output inside Claude Code | uv from snap cannot write to the file Claude Code hands it | `… 2>&1 \| cat` |
| a wait loop never ends | `pgrep -f` matches its own shell | wait for an end line or the PID (chapter 11.3) |
| EasyEDA crashed during a long run | V8 out of memory | restart, find the state, rerun the whole step; second crash: smaller blocks (start skill, section 4) |
| JLCPCB BOM tool: part missing | not in the assembly catalogue / no stock | gate check F-2 asks the catalogue before the upload |
