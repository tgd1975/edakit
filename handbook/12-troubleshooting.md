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
| pour status `readback-mismatch` | harmless for the fill | look at the number of filled areas per layer; L-15 of the gate measures what the fill left |
| "focus lost" / "获取器件关联的所有引脚失败" (pins not readable) | another tab became active (a click, another script) | scripts get the tab back or abort; never run two EasyEDA jobs at once; claim EasyEDA |
| schematic texts come back after a reload | `SCH_PrimitiveText.delete` is not saved | edakit deletes through another primitive class (chapter 9.3) |
| renaming a schematic renamed another one | `modifySchematicName` acts on the active schematic | edakit activates first and checks every name; never delete on a mismatch |
| `edakit schematic check` suddenly reports a pin on two nets in the template | drift of unknown cause in a generated schematic | regenerate the template (`schematic create --save`) |
| `copy` refuses: "belongs to board" | the PCB is linked to the target | correct: use `edakit schematic layout`, which syncs in place |
| Freerouting leaves nets open | order dependence, crowded pads, rules | `route all` retries reshuffled; more passes; more room in the plan; a power plane; lower clearance only within EasyEDA's DRC |
| `route check`: a plane net open, its SMD pads on the other side in groups of their own | Freerouting connects no pad to a plane with a via | `fanout = true` on the plane in `[[pours]]` (7.5) |
| `route check` / L-13: "R22.2 (N3) – R37.1 (N2): 0.090 mm apart on TOP, below the clearance …" | two parts placed with their pads closer than the routing clearance; Freerouting cannot move a pad | move or turn one of them in `[place]` (fix it there if the auto-layout put it), then `pcb apply` and `route all` again |
| `route check` / L-14: "C2.2 (GND) – D1.2 (VIN): 0.300 mm apart on TOP, below the paste gap 0.400 mm" | SMD pads of two parts on an assembled side so close that the stencil leaves only a thin web between their prints – the paste can bridge in reflow | spread or turn one of them in `[place]`, then `pcb apply` and `route all` again; a pair close on purpose gets `waive` L-14 with the reason |
| L-15: "TOP: 47 % copper, largest copper-free circle Ø 9.7 mm at (-19.0, 111.7) mm" | EasyEDA dropped the pour pieces that touch no pad of the pour net, or the pour was not filled (again) after the last copper change | give the area a net that reaches it (a second pour net with `pour_regions`, or a pad or via of the pour net there), `route pours`, export and gate again; bare on purpose: accept the warning with its reason |
| L-15: "TOP: 1 piece without pad, via or hole: 16.2 mm² around (10.5, 4.5) mm" | an island kept by a fill with islands (stitching) whose second fill did not run, or copper drawn by hand | connect it with a via or a track, or delete it; fill the pours again without islands |
| L-16: "D31.1: 0.130 mm on TOP and BOTTOM (hole Ø 0.80 mm)" | the pad leaves less copper around the hole than JLCPCB's minimum ring (0.18 mm; a via 0.05 mm) – often a hole widened for the lead (L-9) on a footprint whose pitch has no room for a larger pad | a larger pad or a smaller hole as far as L-9 allows; at a tight pitch another footprint or part; a ring the fab confirmed: `waive` L-16 on the part with the reason |
| L-16: "J1.2 – via at (3.00, 12.05): 0.398 mm apart, below 0.45 mm" | two plated holes closer edge to edge than JLCPCB's hole-to-hole spacing (0.45 mm with a component hole, 0.2 mm between vias) | move the via or the part, or a smaller hole where L-9 still passes |
| L-13 / L-14: "… is not the PCB any more – … moved or changed since" | a part moved, turned or got another net after the last `route read` | `edakit route read` (or `route all`), then the gate again |
| `route dsn` stops: "… no room for a fanout via" | foreign pads, the edge, a hole or a keep-out around that pad | more room next to the pad in the plan, or a `windows` entry for its part in the keep-out |
| `pcb pour` stops: "pour_regions – the outlines … come from the routing" | `pour_regions` and no board file or SES yet | `edakit route all` (it pours at its end), or `route read` and `route route` first |
| "… its pour at (x, y) mm lies inside the pour of …" | a net's area is enclosed by another net's area on a shared layer – that outline would need a hole | the preview shows where: route so that the outer net does not enclose it, or leave the inner net's pour off that layer |
| `route check`: a pour-only net open in groups | tracks of other nets cut its pour into islands | the preview shows the computed pour and where it is cut: a wire keep-out on that layer where the tracks cut it, or more room between the pads there |
| Freerouting routes nothing in part of the board | concave outline as boundary | edakit uses a rectangle + keep-outs; if you write your own DSN, do the same |
| tracks appear where a wire keep-out should be | stale DSN | `route` writes the DSN fresh every time; `route check` uses the same config |
| "outline contains arcs" | outline drawn by hand with arcs | draw it with `edakit pcb apply` (arcs as point lists) |
| `uv run …` exits 120 without output inside Claude Code | uv from snap cannot write to the file Claude Code hands it | `… 2>&1 \| cat` |
| a wait loop never ends | `pgrep -f` matches its own shell | wait for an end line or the PID (chapter 11.3) |
| EasyEDA crashed during a long run | V8 out of memory | restart, find the state, rerun the whole step; second crash: smaller blocks (start skill, section 4) |
| JLCPCB BOM tool: part missing | not in the assembly catalogue / no stock | gate check F-2 asks the catalogue before the upload |
