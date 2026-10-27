---
name: release
description: Release a hardware state for manufacturing with the edakit release gate – all stages (P parts, G graph, E simulation, project stages, S schematic, L board, F manufacturing files), sign-offs bound to hashes, manifest, test protocol, order checklist for JLCPCB. Use before an order, for "release", "gate", "test protocol", "manufacturing files", "Gerber", "BOM".
---

# Release for manufacturing

Goal: **the board is correct when it goes to the manufacturer, and the tooling – not a gut feeling – makes sure.**
Concept: `${CLAUDE_PLUGIN_ROOT}/handbook/08-release-gate.md`.

## Procedure

1. **Offline** (seconds): `edakit stock 2>&1 | cat` when the snapshot is older than `stock_max_age_days` (P-4 is
   pending then), then `edakit gate 2>&1 | cat` – P, G, E and the project's own stages.
2. **With EasyEDA** (start skill, claim EasyEDA, reference schematic checked): `edakit gate --easyeda 2>&1 | cat` in the
   background (minutes). Adds S, L and F per board: read the PCB, save and reload, DRC, export Gerber and pick-and-place,
   BOM from the graph, JLCPCB stock, copper connectivity from the Gerber files, holes against leads, outline, tooling
   holes, polarity sheet. Files in `<reports>/<run>/fab/<board>/`.
3. Read `<reports>/<run>/protocol.md`. Summarise per stage passed / failed / warning / open, then the findings with
   actual and expected value. Always name stages and checks with their short name next to the letter: "stage L
   (board)", "L-9 (hole fits the lead)" – nobody remembers the letters; the names come from the rule catalog
   (`edakit rules`), and section 10 of the protocol explains every check that failed or warned.
4. **Fix causes, do not define findings away.** The cause is in the graph, the parts database, the plan or the
   project's mechanics → hardware-change or pcb-round skill. **Only the user accepts a warning** – it is a decision.
   Propose the entry for the sign-off file (`accepted_warnings`: `match` as fnmatch pattern over "ID scenario item
   step" as shown in section 3 of the protocol, `scope`, `reason`, `by`, `date`) and add it after their OK.
5. **Manual checks an agent can do are signed by the agent's result** (no checklist for the user): M-1 – agent
   electrical-reviewer checks the critical parts again against their datasheets with the polarity sheet; M-6 – agent
   regulatory-reviewer checks circuit and parts against the rules for the purpose in the graph (usually done at the
   hand-over already; it counts as long as the circuit hash is the same); M-5 – agent pcb-reviewer checks the layout
   on the manufacturing files of this run. OK → `done_by` = the agent, date, note, and the hash of its scope from the
   protocol header into the sign-off file. Not OK → fix the cause and check again. What changes looks or operation is
   the user's call (decision-round skill).
6. **RELEASED:** `fab/manifest.json` says `"released": true`. Archive the folder in git (`git add -f`) through the
   project's git workflow. Upload only from that folder.

## Order (done by the user)

The MCP server cannot order on purpose. Checklist for the user:

- [ ] Per board: `gerber_<b>.zip`, `bom_<b>.csv`, `cpl_<b>.csv` from the released folder, checksums as in the manifest
- [ ] Assembly type matches `[release] assembly` (Economic: one side, SMD; two SMD sides or a "Standard Only" part
      need Standard PCBA – `assembly.pcba`, P-4); bake set when P-4 warns about MSL ≥ 5
- [ ] Tooling holes "added by customer" when the board has its own (otherwise JLCPCB drills theirs, maybe visibly)
- [ ] Order number position: "specify a location" if the silkscreen has a placeholder (`JLCJLCJLCJLC`)
- [ ] Remarks field (max. 200 characters) for panel tabs or V-cuts that must avoid visible edges
- [ ] M-2: in JLCPCB's assembly preview the rotation and polarity of every polarised part (compare with
      `polarity_<b>.png`), no missing part in the BOM tool, price; then sign M-2
- [ ] The cart against `edakit cost` – class, fees and parts; a difference of more than a few dollars has a reason
- [ ] Parts that do not come from JLCPCB (hand-soldered, cables, enclosure) ordered in the same go: `edakit order`
      writes a cart per supplier and `hand_assembly.md` for all sets, with spares and minimum quantities

After delivery: acceptance test of every board (M-4).
