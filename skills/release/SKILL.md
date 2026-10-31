---
name: release
description: Release a hardware state for manufacturing with the edakit release gate – all stages (P parts, G graph, E simulation, project checks, S schematic, L board, F manufacturing files), sign-offs bound to hashes, manifest, test protocol, the order files published as a GitHub release (edakit release publish), the order checklist – the skill cart puts the released board into the maker's cart. Use before an order, for "release", "gate", "test protocol", "manufacturing files", "Gerber", "BOM", "publish the release".
---

# Release for manufacturing

Goal: **the board is correct when it goes to the manufacturer, and the tooling – not a gut feeling – makes sure.**
Concept: `${CLAUDE_PLUGIN_ROOT}/handbook/08-release-gate.md`.

## Procedure

1. **Offline** (seconds): `edakit stock 2>&1 | cat` when the snapshot is older than `stock_max_age_days` (PARTS.stock is
   pending then), then `edakit gate 2>&1 | cat` – P, G, E and the project's checks of phase export before S (their
   `at`, handbook 8.1). Before it, with `[scripts]` in edakit.toml (handbook 8.6): `edakit scripts 2>&1 | cat`, and a
   derive script made from the layout – it reads the footprints, the mechanical model or the routing: the stand that
   fits the board, a picture of it – that is outdated or never ran runs before the gate with
   `edakit run <name> 2>&1 | cat`; the gate only warns on it, and runs the inputs it reads itself. A project
   without entries skips this. A footprint geometry that still lies among the artifacts (a note of `edakit check` and
   in section 6 of the protocol) is moved first, as the note says, and committed: the move changes the layout hash
   once, and a sign-off with scope `layout` recorded before it would lapse (handbook 8.2).
2. **With EasyEDA** (start skill, claim EasyEDA, reference schematic checked) – or on KiCad (`toolchain = "kicad"`,
   handbook 16: no start skill, no claim, `--eda` is the same flag): `edakit gate --easyeda 2>&1 | cat` in the
   background (minutes). Adds S, L and F per board: read the PCB, save and reload, DRC, export Gerber and pick-and-place,
   BOM from the graph, JLCPCB stock, copper connectivity from the Gerber files, holes against leads, outline, tooling
   holes, polarity sheet; then the project's checks with `at = "after F"`, on this run's manufacturing files. Files in
   `<reports>/<run>/fab/<board>/`.
3. Read `<reports>/<run>/protocol.md`. Summarise per stage passed / failed / warning / open, then the findings with
   actual and expected value. Always name stages and checks with their short name next to the letter: "stage L
   (board)", "GEO.hole (hole fits the lead)" – nobody remembers the letters; the names come from the catalog
   (`edakit rules`), and section 10 of the protocol explains every check that failed or warned.
4. **Fix causes, do not define findings away.** The cause is in the graph, the parts database, the plan or the
   project's mechanics → hardware-change or pcb-round skill. **Only the user accepts a warning** – it is a decision.
   Propose the entry for the sign-off file (`accept`: `match` as fnmatch pattern over "ID scenario item
   step" as shown in section 3 of the protocol, `scope`, `reason`, `by`, `date`, and `parts` {designator: LCSC} for
   a warning about particular parts – it lapses when one of them is swapped) and add it after their OK. A lapsed
   acceptance (section 3) goes back to the user: judge again, then update `parts` or remove it. A row `scripts` of
   stage G is a project script (handbook 8.6). An input the gate reads runs by itself before it ("project scripts
   before edakit gate" in its output) – one that failed stops the gate: fix it, never `--no-scripts` for a release
   run. A derive or easyeda script outdated or never run: `edakit run <name> 2>&1 | cat` – an easyeda script claims
   EasyEDA, so start skill first –, then the gate again. "project-library:<b> changed by …": the parts in the PCB keep
   their old footprint until deleted and recreated – skill pcb-round (`pcb parts --write`, `pcb dump`, `route all`),
   or the user accepts the warning. Commit `hardware/scripts.lock` with what the scripts wrote; entries that do not
   resolve – fix `[scripts]` in edakit.toml. A project check is a stage of its own, its `id` the stage letter
   (handbook 8.1): what it printed is `<reports>/<run>/stage_<id>.txt`; a failed one is a finding like any other, an
   advisory one is listed and does not block.
5. **Manual checks an agent can do are signed by the agent's result** (no checklist for the user; M-1, M-6 and M-5 are
   required – the gate adds them as open when the sign-off file lacks them): M-1 – agent electrical-reviewer checks the
   critical parts again against their datasheets with the polarity sheet; M-6 – agent regulatory-reviewer checks circuit
   and parts against the rules for the purpose in the graph (usually done at the hand-over already; it counts as long as
   the circuit hash is the same) – support, not legal advice, and you say so when you report it; M-5 – agent
   pcb-reviewer checks the layout on the manufacturing files of this run. With `[agents.<name>]` in edakit.toml
   (handbook 8.6), `edakit scripts 2>&1 | cat` shows who reviews where: a project agent signs the review it replaces
   (`replaces`) in place of edakit's agent, and a project agent's sign-off of its own of phase export – scope `fab` at
   this review, `circuit` and `layout` at their hook point and here again once lapsed – is required like M-5: the gate
   adds it as open. A sign-off a project agent signs counts only when `done_by` names that agent ("agent pcb-pruefer");
   signed by edakit's agent, or for another scope than the agent's entry gives, it is open (a note in section 6 says
   why). OK → `done_by` = the agent, date, note – with `[project] requirements` the note names every requirement the
   check found met, as the agent's line gives them ("requirements met: R-4, R-5"; `verify = [{ signoff = "M-1" }]`,
   handbook 8.7) –, and the hash of its scope from the protocol header into the sign-off file – for scope `fab` (M-5,
   M-2) the `fab_sha256` of the run whose files were reviewed; a later run with the same files – and the same thickness,
   colours, finish and mark of `[order]` – keeps it. When it lapsed: `edakit fab diff <reviewed run> <new run>` shows
   what changed, and the review looks at that. Not OK → fix the cause and check again. What changes looks or operation
   is the user's call (decision-round skill).
6. **RELEASED:** `fab/manifest.json` says `"released": true`, and the run is the current release – the gate marked
   every earlier released run as superseded (`edakit release current` shows it). The run is build output: it stays in
   `<reports>/`, which git ignores, and nothing of it is committed – what is ordered is published in step 7 (handbook
   8.3). Only with `[release] archive = "git"` in edakit.toml: archive the folder in git together with the superseded
   manifests through the project's git workflow – `edakit release current` names a released run git does not track
   yet ("not in git yet: git add -f …"). A released run that must not be uploaded after all (a review found
   something): `edakit release withdraw <run> --reason "…"` – then there is no current release until the next
   RELEASED run.
7. **Publish what is ordered** (handbook 8.3), once every board of the project – and of every variant below it – has
   its current release: `edakit release publish --dry-run 2>&1 | cat` stages the files in `build/publish/<tag>/` and
   writes the notes (`notes.md`: per board the gate run, its git state, the fab hash, changed or unchanged since the
   previous release, with `[release] publish.decisions` the decisions since then, the purpose). Show the user the
   notes; on their OK `edakit release publish 2>&1 | cat` makes the GitHub release `<YYYY-MM-DD>` – a pre-release on
   HEAD, as public as the repository. It needs `gh`, logged in, and refuses with exit 1 while the working tree has
   uncommitted changes or HEAD is not pushed – the tag must name the state the files were made from: commit and push
   through the project's git workflow first. Exit 2: `release verify` refused a file or a project has no current
   release – nothing was staged or uploaded; fix the cause (a new gate run, the variant's release), do not leave the
   board out. `--draft` is a test only the account sees, no tag and no guards: delete it afterwards with
   `gh release delete <tag> --yes`. Firmware is not published.

## Order (up to the cart; ordering and paying are the user's)

The released board goes into the maker's cart with the skill cart (`/edakit:cart`): `edakit cart prepare` from the
current release, the form filled and read back with Claude in Chrome, `edakit cart check` (ORDER.form to ORDER.review) with the
regulatory review of the order, then the maker's cart button – nothing ordered or paid (handbook 8.4). Without Claude
in Chrome the skill prints the job as a checklist and `edakit cart check` checks what the user filled in. The MCP
server cannot order on purpose. The checklist below is what the skill and its checks cover, and what stays the
user's:

- [ ] Upload from `build/publish/<tag>/`, the staging of step 7 – per made board `gerber_<b>.zip`, `bom_<b>.csv`,
      `cpl_<b>.csv` (a bought board, `bought = true`, has none): publish verified each against its project's current
      release, and `sha256sum -c SHA256SUMS` there shows that none changed since. Files from anywhere else:
      `edakit release verify <the files about to be uploaded>` says every file is of the current release (exit 0)
- [ ] Assembly type matches `[release] assembly` (Economic: one side, SMD; two SMD sides or a "Standard Only" part
      need Standard PCBA – `assembly.pcba`, PARTS.stock); bake set when PARTS.stock warns about MSL ≥ 5
- [ ] The form as `fab/<b>/order.md` of the released run says (with `[order]` in the board file; FILES.order checked it):
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
with its command), the project agents of phase acceptance (`- [ ] M-8 … – the project agent kamera`: start it in its
own session, its OK signs the line, `done_by` = the agent) and, with `[project] requirements`, the acceptance steps of
the requirements (`- [ ] R-4: …`); M-4's note names the requirements it tested. Once a board of a published release
passed it: `edakit release publish --built <tag> 2>&1 | cat` – the release is no longer a pre-release.
