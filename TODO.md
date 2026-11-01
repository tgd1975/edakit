# TODO

Open work that needs the owner's computer, a maker or the owner's word. The state of every step is in the concepts
and plans the sections name; this list is what is left to do of them, in the order it can be done. No item is deleted.

**Layout.** Every item, in every section, open or closed, is a line with a checkbox and an ID unique in this file,
counted up and never reused – whoever adds an item takes the next free ID and counts it up here. Next free ID: TD-60.

- Open: `- [ ] TD-<n> - **Title:** what and why.` – a step's own name after the dash (`- [ ] TD-31 - **D.4** …`).
- Done: ticked, the commit that did it, the date at the end, moved to [Closed todos](#closed-todos), newest first –
  by whichever session learns it; a dropped one says so: `- [x] TD-<n> - **Title:** what came of it (commit). [date]`.
- For the owner: what only the owner can do – an account, a payment, an OK, hardware in hand, a click in Claude
  Code – goes into a section "For the owner" at the top, one line each, the session at the end:
  `- [ ] TD-<n> - **What:** command or link – why. *(session)*`. An item further down that waits for the owner
  stays where its step is.
- One item, one piece of work: one thing to do, by one hand, at one time, done when one statement is true – no
  collecting tank. Short and plain: what, why, where; history and details stay in the file the section names. A
  part that waits for something else or is someone else's is an item of its own.
- Headings group open items; once none is left under one, the heading and its text go, and it comes back with the
  next item that belongs there.

**Taking an item.** Several sessions work on edakit at once. Before a session starts an item, it lists the others
(`ListAgents`, `git worktree list`), asks each running edakit session which item it holds, and takes one that nobody
holds and whose files no open branch touches – the concepts' tables name each step's files. An item that waits for
another (W.4 after W.2) is agreed with the session holding that one and merged after it. Each item gets a worktree of
its own beside the main clone, named for it (`../edakit-w4`, branch `wired-w4`), so `git worktree list` shows who
holds what; the main clone belongs to whoever has it checked out, and its uncommitted changes are not anyone else's
to touch.

## For the owner

- [ ] TD-59 - **OK for #129, #130, #131:** <https://github.com/tgd1975/edakit/pull/129> (TD-37, no click on Import
      Changes), <https://github.com/tgd1975/edakit/pull/130> (TD-38, the DRC reloads only on Connection Errors),
      <https://github.com/tgd1975/edakit/pull/131> (TD-39, local projects through the API) – each checked live on 1.6.0;
      on the OK `merge.py` merges them one after the other. *(edakit-35)*
- [ ] TD-57 - **The real cost of the first order:** once an order the skill cart put into a maker's cart is paid,
      `/edakit:cart actual` on its order page or saved invoice – `edakit cart actual` (handbook 8.4, step 5) has run
      on recorded data only; the real cost, the project's fee table and the order record come from it. *(edakit-80)*

## What edakit needs from EasyEDA Pro and easyeda-mcp-pro ([upstream/README.md](upstream/README.md))

E-1 to E-16 on EasyEDA Pro and M-1 to M-9 on easyeda-mcp-pro, checked live on EasyEDA Pro 3.2.209 and posted on
2026-11-01; what each asks and where it stands is in upstream/README.md – the items here say only what is left to do.

### Live in EasyEDA – edakit's own work

At the owner's computer, in this order; each change checked live before it is built.

- [ ] TD-52 - **The switch to 1.6.0:** on main as edakit 0.4.0 (#121), the self-test and the example's gate green; left:
      the plugin updated in pytree and the bell and their servers restarted; handbook 2's "Tested with" in #131.
- [ ] TD-37 - **E-2, the one click goes:** the Channel ID written into the schematic parts (`edakit/pcb.py`), built and
      checked live – #129, waits for TD-59.
- [ ] TD-38 - **E-3 and E-7, the PCB tab and the DRC:** the probe's error as "inactive", the reload only on Connection
      Errors (`edakit/eda.py`, `route.py`), built and checked live – #130, waits for TD-59; a full routing run without
      reload is the next project's.
- [ ] TD-39 - **E-9, local projects through the API:** `getAllProjectsUuid` per project folder (`edakit/eda.py`), built
      and checked live – #131, waits for TD-59.
- [ ] TD-40 - **E-10, E-11 and E-13 taken up:** `edakit part build` modifies the symbol's pins instead of creating them
      anew (`SCH_PrimitivePin.modify` is saved on 3.2.209); `clear_orphan_attributes` kept as a cheap check or dropped;
      tooling holes stay on the board while the pours fill, and a hole in a pour becomes a `NO_POURS` region instead of
      the notch – each checked live first.

### Waiting for upstream

Nothing to do until there is an answer or a release; whichever session learns of one takes it.

- [ ] TD-26 - **easyeda-mcp-pro, #792 to #805** (M-1 to M-5, M-7, M-9; no answer yet): answer review comments on the
      fork's branches, rebase when `main` moves; the comment "I agree to the Contributor Permission v1 in
      CONTRIBUTOR-LICENSING.md" from the owner when the maintainer asks. When a release brings M-2 to M-4: the pin
      raised, the original extension, `bridge-extension-patch.sh` and `odb-tool-patch.mjs` removed, handbook 2.4, 2.5
      and 9.1 follow; with M-9 `place` in `edakit/schematic.py` passes `addIntoBom` on create again, handbook 9.3.
- [ ] TD-36 - **EasyEDA, #45 to #51 and our comments to #36 and #38:** answer questions; when a release fixes one,
      check it live, take it up and say so in upstream/README.md. EasyEDA's first answer is often "update to the latest
      version".

## Versions and branch protection ([versioning.md](docs/concepts/new/versioning.md))

Decided on 2026-11-01: 0.2.0 first; the major number the owner's to release, minor and patch by one question (minor
when a project must act); every merge that changes edakit a version of its own, numbered by `.github/merge.py`; the
notes lane for concepts and TODO.md; the rulesets on main as text; the projects on the newest version, unpinned. Each
step starts on the owner's word.

- [ ] TD-47 - **V.4** The rulesets as text in `.github/rulesets/`, applied with `gh api` on the owner's word, the
      checks not strict, with CLAUDE.md (the protection) and the skills triage, add-rule and add-feature (a fragment per
      change) in the same branch – README, handbook 2.3, the merging rule and the notes lane came with TD-45 and TD-46.
      Checked then: the admin role as a bypass on a personal repository.
- [ ] TD-48 - **V.5** Branches left lying around: 9 `claude/*` and 2 `ccr-*` on origin, the local ones and the
      worktrees – listed, then merged or deleted on the owner's word; other sessions' branches named with their session.
- [ ] TD-49 - **V.6** 1.0.0 on the owner's word once D.2 is built (`merge.py <n> --major`).
- [ ] TD-50 - **V.7** Later, on the owner's word: `edakit = ">=0.4"` under `[project]` in `edakit.toml`, noted by
      `edakit check` and the SessionStart hook when the running edakit does not meet it.

## The documentation for its readers ([documentation.md](docs/concepts/new/documentation.md))

Decided on 2026-10-31; D.1 (the style guide, the glossary and their tests) built the same day. D.2 to D.7 not before
the other todos in this list are done: the documentation describes what they leave behind.

Each step starts on the owner's word, one per branch, under the concept's rules for what the automation reads –
sources, data and code untouched; a text that is generated or used elsewhere stays; unsure, ask:

- [ ] TD-29 - **D.2** The entry layer: the README as the start page of one screen with the case for edakit (what you
      bring, what edakit brings, the walkthrough's count), `docs/quickstart.md` with its test, `docs/how-it-works.md`
      with the pipeline drawing, a transcript, the state and the future work (two items); `test_plugin.py` pointed at
      the page that lists skills and agents.
- [ ] TD-30 - **D.3** The site: the navigation as data, by reader and by station (The circuit, The board), short titles;
      `organisation.md` and the brand page on it; "Inside edakit" with its index and the source line; the footer and
      feedback lines; prototypes off the navigation.
- [ ] TD-31 - **D.4** The reference: 10.5 as entries with the generated synopsis; the catalog page split; the chapters'
      generated lists as the short kind.
- [ ] TD-32 - **D.5** The chapters in place, condensed to a third fewer words with no statement lost, worst first – 8,
      3, 5, 7, 4, 10, then the rest –, the review for meaning after each; chapter 13 takes the history.
- [ ] TD-33 - **D.6** The reader pages "Adding a rule" and "Working on edakit".
- [ ] TD-34 - **D.7** The "is it for me" numbers from the evals; the findings on sources (the plugin's descriptions say
      "JSON hardware graph") to the owner.
- [ ] TD-35 - **D.9** `docs/projects/`, the gallery: the index with a card per project – the examples' cards lead to
      chapters 17 and 18 –; the bell's page – what it is, the circuit with its drawn schematic and its blocks explained,
      the board as made, what edakit found, its variants main, smd, tht and esp32 side by side, what it changed in
      edakit – from the pictures of its current release (section 12 of the protocol; where the release has none, the
      bell's session draws them at its next gate run); pytree's page with the information and the pictures the owner
      picks (needs the owner – the repository stays private); a later project's page once it has a result with edakit,
      nothing planned on the gallery; the style guide's project page and `test_style.py` follow.

## Closed todos

Done or dropped, newest first, each with its date and the commit that closed it. What closed before 2026-11-01 is
taken from the history of this file; an item rewritten on its way is listed once, in its last form.

- [x] TD-44 - **The Claude GitHub app uninstalled:** dropped on the owner's word – the app is Claude Code on the web's
      access to the repositories; the proposals Action no longer fetches its token (0.3.1), and main's ruleset (TD-47)
      keeps it off main. [2026-11-01]
- [x] TD-58 - **OK for #121, easyeda-mcp-pro 1.6.0:** given, merged as edakit 0.4.0 (5ae332d). [2026-11-01]
- [x] TD-54 - **M-6, the BOM's duplicates:** on 1.6.0 each part listed once; the removal went, SYNC.bom reports a
      designator listed twice – edakit 0.4.0 (#121). [2026-11-01]
- [x] TD-53 - **M-6, all pages at once:** dropped – `all_pages` answers with the parts of every open schematic, the
      template's included, without their page; edakit stays page by page, recorded in upstream/README.md – edakit 0.4.0
      (#121). [2026-11-01]
- [x] TD-43 - **P.6, the live test of the proposals pipeline:** the setting for pull requests on; three sealed test
      proposals – #108 broken seal: the workflow's question, no Claude run; #109 covered: rejected as LIM.range and
      closed; #110 asks to change triage-rule: rejected at "Safe?", no commit –; a batch of six real ones (#112–#117)
      triaged once each, #112, #114, #115 and #116 built into #122 by the workflow's token. Found and fixed: a
      left-over commit (#103's 9aad156) conflicting only in the catalog page (#111, 0.3.2); a result written before
      its commit and a placeholder left in the pull request (#125). [2026-11-01]
- [x] TD-42 - **P.1 to P.5, the proposals pipeline:** Claude reads with the workflow's own token, a fixed job checks
      the commit against PIPELINE before the push, the queue triages once and takes adopted issues of others (#105,
      edakit 0.3.1). [2026-11-01]
- [x] TD-51 - **The bridge extension 1.6.0 in EasyEDA:** imported by the owner; `edakit doctor` and the self-test:
      extension 1.6.0 = server 1.6.0. [2026-11-01]
- [x] TD-46 - **V.3** The notes lane: `.github/notes.py` lands a session's edits of concepts and TODO.md on the newest
  main without an OK – the diff, three-way, from any worktree; a pull request from notes/<topic>, merged by the script
  once green, no GitHub auto-merge; `paths` holds notes/* to the lane; this tick its first run (#107, 897ae0d).
  [2026-11-01]
- [x] TD-56 - **4.5** A project without a requirements file does not release: DOCS.file, open like a required
  sign-off – `edakit check` passes, `--release` and the gate do not; built before the bell's D-39 on the owner's word,
  the bell has its file (#106, edakit 0.3.0). [2026-11-01]
- [x] TD-45 - **V.1 and V.2** edakit 0.2.0, the first version: the number in `edakit/__init__.py`, `edakit --version`
  and the manifest's `tools.edakit`, the changelog from 2026-11-01 on, the fragments in `changes/`, `.github/merge.py`
  (merges while main keeps its number – not strict), the checks `paths` and `version`, `release.yml` (tag v0.2.0 and the
  GitHub release set); CLAUDE.md "A merge is a version", README, handbook 2.3, 10.5, 14.4, the glossary (#104, 1cb2d68).
  [2026-11-01]
- [x] TD-25 - **easyeda-mcp-pro 1.6.0 prepared:** branch `mcp-160`, the pin raised, both patches applied, the patched
  extension built to `~/.easyeda-mcp-pro/easyeda-bridge-extension-1.6.0.eext`; on the way 1.6.0's one break for
  edakit – the PCB lists refuse projectId "current" – met in `list_pcb_components` (branch `mcp-160`, not merged).
  *(edakit-e4)* [2026-11-01]
- [x] TD-55 - **4.4** The tree moved to edakit before its order instead (its EK-5 lifted EK-1), in pytree: D-50 to
  D-54, merged on its main with pytree#34 – `hardware/boards/tree.toml` written by its script `baumplan`, its scripts
  under `[scripts]` (`review_paket.py` only reads the release), `elektrotechniker` and `pcb-pruefer` deleted rather
  than kept with `replaces` – edakit's reviewers signed M-1, M-5 and M-6 –, `hardware/requirements.toml` accepted.
  [2026-11-01]
- [x] TD-28 - **When a release brings M-2 to M-4:** merged into TD-26 – the second half of following the same pull
  requests; TD-25 split into TD-25 and TD-51 to TD-54 at the same time. *(edakit-e4)* [2026-11-01]
- [x] TD-41 - **M-9 (was E-15):** reproduced live on 3.2.209 with the bridge of 1.4.0 (code unchanged on 1.6.0) – not
  "Invalid device": the bridge drops `mirror`, `addIntoBom` and `addIntoPcb` of a placed part and reports `applied`;
  posted as #804 with the pull request #805 from the fork's `fix/place-component-flags`; edakit's `place` takes every
  part with `bom: false` out of the BOM afterwards, not only those with an LCSC number (cb9ddc7). *(edakit-e4)*
  [2026-11-01]
- [x] TD-27 - **On the owner's word – post:** E-1 to E-16 checked live on EasyEDA Pro 3.2.209 and against the JSDoc of
  its types, then posted: #45 to #51 at easyeda/easyeda-api-sdk and comments to #36 and #38; E-3 watched, E-2's Channel
  ID, E-7 to E-10 and E-13 ours, documented or met, E-14 by design, E-15 moved to M-9 (5d2ee55). *(edakit-e4)*
  [2026-11-01]
- [x] TD-2 - **Read the circuit-language sketch in peace:** read by the owner; the sketch itself was closed on
  2026-10-31 (bd227e3) and lives on in circuit-language-plan.md and circuit-dsl.md (6df3b09). *(edakit-29)* [2026-11-01]
- [x] TD-1 - **Update the edakit plugin:** the owner updated it to 8c6652c and reloaded (aec84ee).
  *(edakit-be, automatic-christmas-bell-b3)* [2026-11-01]
- [x] TD-24 - **The check candidates of the review at the order (5.5):** decided and built – FILES.order/lead,
  PARTS.fact/rohs, the makers' RoHS and REACH statements (2f659d6). [2026-11-01]
- [x] TD-23 - **5.11, the makers' interfaces:** dropped – future work, nobody asks the makers (the owner's
  decision); handbook 8.4 names them (545ee3a). [2026-11-01]
- [x] TD-22 - **Step 0 (5.0), the makers' forms:** the four profiles recorded, JLCPCB's order number gone, PCBWay's
  upload after "Save to Cart", Eurocircuits' "Add to basket", AISLER without a cart; branch makers-step0 merged
  (dcc0dfb, ce3e897). [2026-11-01]
- [x] TD-21 - **Step 0b (5.0), EasyEDA's ODB++ on a probe board:** component layers with package, pins and MPN,
  turned as F-7 assumes; SYNC.odb's RoundRect mask openings fixed (6062591, ce3e897). [2026-11-01]
- [x] TD-20 - **5.7, 5.12:** the skill cart live at JLCPCB and PCBWay, into the cart, nothing ordered (ce3e897).
  [2026-11-01]
- [x] TD-19 - **5.8:** the skill cart live at Eurocircuits, into the basket, nothing ordered (ce3e897). [2026-11-01]
- [x] TD-18 - **5.10:** AISLER live, stopped before "Continue to Checkout", nothing ordered (ce3e897). [2026-11-01]
- [x] TD-17 - **CPL rotations per maker:** `[cpl] zero` and `[cpl.turns]` in the makers' profiles (ce3e897).
  [2026-11-01]
- [x] TD-16 - **JLCPCB's customs "Product Description":** the key `customs` of `[order]` (ce3e897). [2026-11-01]
- [x] TD-15 - **The ODB++ export upstream (M-4):** branch feat/odb-export built in the fork (2395015), issue and
  pull request posted as #798/#799 with M-1 to M-3; following them is the open item above. [2026-11-01]
- [x] TD-14 - **The example coin-cell-led at its next `edakit gate --easyeda`:** routed and released again, A4, A5,
  B1, B3, B7 and C4 hold, M-5 signed for the new fab hash (e3e1290). [2026-11-01]
- [x] TD-13 - **LT-9, the led-bar example on real footprints:** the placement plan fits its LCSC footprints, the
  Pico 2's pins in `symbol_differs` (dc07193). [2026-11-01]
- [x] TD-12 - **The KiCad live test with the owner:** all seven steps, LT-1 to LT-11 in the concept (4dbf4fc).
  [2026-11-01]
- [x] TD-11 - **The bell's L.9 and its T-Display on the data path:** done in the bell's session, its branch
  edakit-current (2dd5f55). [2026-11-01]
- [x] TD-10 - **The notices after the merge into main:** the bell and pytree-27 told of F-6's placeholder warning
  and the walkthrough gaps' changes to their gate; the plugin follows main at 868e942 (59b62db). [2026-10-31]
- [x] TD-9 - **Live runs of design as text:** 2.2 (`[routing] drc_rules` "write"), 3.6 (the way back into the
  PCB), M-6 not voided by a footprint, and what was found on the way – built (bc44fa7). [2026-10-31]
- [x] TD-8 - **The owner's look at the footprint in EasyEDA:** looked at, the throwaway projects edakit-probe-*
  deleted (14e98bc). [2026-10-31]
- [x] TD-7 - **B2, the hole unit of `PCB_PrimitivePad.create`:** read back in live run 3.6 (59e0939). [2026-10-31]
- [x] TD-6 - **W.2 to W.5, the wired schematic:** merged into main, the concept done (81cd5f2, 2d475fc, d379775,
  868e942). [2026-10-31]
- [x] TD-5 - **D.1, the style guide and the glossary:** with test_style.py and test_references.py (2b37669).
  [2026-10-31]
- [x] TD-4 - **Walkthrough 2, the 555 blinker on KiCad:** the run up to RELEASED (123389b); boards not ordered –
  the owner's decision at the release (7999d5a). [2026-10-31]
- [x] TD-3 - **ODB++ on the KiCad tool chain:** `kicad-cli` exports it for a maker that takes it (82039a8). [2026-10-31]
