---
name: release
description: Release a hardware state for manufacturing with the edakit release gate – all stages (P parts, G graph, E simulation, project checks, S schematic, L board, F manufacturing files), sign-offs bound to hashes, manifest, test protocol, order checklist for JLCPCB. Use before an order, for "release", "gate", "test protocol", "manufacturing files", "Gerber", "BOM".
---

# Release for manufacturing

Goal: **the board is correct when it goes to the manufacturer, and the tooling – not a gut feeling – makes sure.**
Concept: `${CLAUDE_PLUGIN_ROOT}/handbook/08-release-gate.md`.

## Procedure

1. **Offline** (seconds): `edakit stock 2>&1 | cat` when the snapshot is older than `stock_max_age_days` (P-4 is
   pending then), then `edakit gate 2>&1 | cat` – P, G, E and the project's checks before S. A footprint geometry that
   still lies among the artifacts (a note of `edakit check` and in section 6 of the protocol) is moved first, as the
   note says, and committed: the move changes the layout hash once, and a sign-off with scope `layout` recorded before
   it would lapse (handbook 8.2).
2. **With EasyEDA** (start skill, claim EasyEDA, reference schematic checked): `edakit gate --easyeda 2>&1 | cat` in the
   background (minutes). Adds S, L and F per board: read the PCB, save and reload, DRC, export Gerber and pick-and-place,
   BOM from the graph, JLCPCB stock, copper connectivity from the Gerber files, holes against leads, outline, tooling
   holes, polarity sheet; then the project's checks after F. Files in `<reports>/<run>/fab/<board>/`.
3. Read `<reports>/<run>/protocol.md`. Summarise per stage passed / failed / warning / open, then the findings with
   actual and expected value. Always name stages and checks with their short name next to the letter: "stage L
   (board)", "L-9 (hole fits the lead)" – nobody remembers the letters; the names come from the rule catalog
   (`edakit rules`), and section 10 of the protocol explains every check that failed or warned.
4. **Fix causes, do not define findings away.** The cause is in the graph, the parts database, the plan or the
   project's mechanics → hardware-change or pcb-round skill. **Only the user accepts a warning** – it is a decision.
   Propose the entry for the sign-off file (`accepted_warnings`: `match` as fnmatch pattern over "ID scenario item
   step" as shown in section 3 of the protocol, `scope`, `reason`, `by`, `date`, and `parts` {designator: LCSC} for
   a warning about particular parts – it lapses when one of them is swapped) and add it after their OK. A lapsed
   acceptance (section 3) goes back to the user: judge again, then update `parts` or remove it. A row `scripts` of
   stage G is a project script (handbook 8.6): outdated or never run – run it (its `cmd`, `edakit scripts` shows it),
   then `edakit scripts stamp <name>`, and commit `hardware/scripts.lock` with what it wrote; entries that do not
   resolve – fix `[scripts]` in edakit.toml. A project check is a stage of its own, its `id` the stage letter
   (handbook 8.1): what it printed is `<reports>/<run>/stage_<id>.txt`; a failed one is a finding like any other, an
   advisory one is listed and does not block.
5. **Manual checks an agent can do are signed by the agent's result** (no checklist for the user; M-1, M-6 and M-5
   are required – the gate adds them as open when the sign-off file lacks them): M-1 – agent
   electrical-reviewer checks the critical parts again against their datasheets with the polarity sheet; M-6 – agent
   regulatory-reviewer checks circuit and parts against the rules for the purpose in the graph (usually done at the
   hand-over already; it counts as long as the circuit hash is the same); M-5 – agent pcb-reviewer checks the layout
   on the manufacturing files of this run. OK → `done_by` = the agent, date, note – with `[project] requirements` the
   note names every requirement the check found met, as the agent's line gives them ("requirements met: R-4, R-5";
   `verify = [{ signoff = "M-1" }]`, handbook 8.7) –, and the hash of its scope from the protocol header into the
   sign-off file – for scope `fab` (M-5, M-2) the `fab_sha256` of the run whose files were reviewed; a later run with
   the same files – and the same thickness, colours, finish and mark of `[order]` – keeps it. When it lapsed:
   `edakit fab diff <reviewed run> <new run>` shows what changed, and the review looks at that. Not OK → fix the
   cause and check again. What changes looks or operation is the user's call (decision-round skill).
6. **RELEASED:** `fab/manifest.json` says `"released": true`, and the run is the current release – the gate marked
   every earlier released run as superseded (`edakit release current` shows it). Archive the folder in git
   (`git add -f`) together with the superseded manifests through the project's git workflow. A released run that must
   not be uploaded after all (a review found something): `edakit release withdraw <run> --reason "…"` – then there is
   no current release until the next RELEASED run.

## Order (done by the user)

The MCP server cannot order on purpose. Checklist for the user:

- [ ] `edakit release verify <the files about to be uploaded>` says every file is of the current release (exit 0) –
      per made board `gerber_<b>.zip`, `bom_<b>.csv`, `cpl_<b>.csv` (a bought board, `bought = true`, has none)
- [ ] Assembly type matches `[release] assembly` (Economic: one side, SMD; two SMD sides or a "Standard Only" part
      need Standard PCBA – `assembly.pcba`, P-4); bake set when P-4 warns about MSL ≥ 5
- [ ] The form as `fab/<b>/order.md` of the released run says (with `[order]` in the board file; F-6 checked it):
      thickness, mask and silkscreen colour, tooling holes "added by customer" when the board has its own, order
      number "specify position" at the placeholder, the remark (≤ 200 ASCII characters, tabs only on stretches
      order.md lists as free), bake. Without `[order]`: thickness, colours, tooling holes, order number position and
      remark by hand as in handbook 8.4
- [ ] M-2: in JLCPCB's assembly preview the rotation and polarity of every polarised part (compare with
      `polarity_<b>.png`), no missing part in the BOM tool, price, and the datasheet points and the project's checks
      section 6 lists under "after uploading" (a check: run its command); then sign M-2
- [ ] The cart against `edakit cost` – class, fees and parts; a difference of more than a few dollars has a reason
      (a thickness, colour or finish `edakit cost` names as not in the price is one)
- [ ] Parts that do not come from JLCPCB (hand-soldered, cables, enclosure, a bought board and what is soldered onto
      it) ordered in the same go: `edakit order`
      writes a cart per supplier and `hand_assembly.md` for all sets, with spares and minimum quantities

After delivery: acceptance test of every board (M-4), with the datasheet points section 6 of the protocol lists
under "after delivery, per board" (`verified.open` with `when`), the project's checks of phase acceptance there (each
with its command) and, with `[project] requirements`, the acceptance steps of the requirements (`- [ ] R-4: …`);
M-4's note names the requirements it tested.
