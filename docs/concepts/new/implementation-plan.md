# Implementation plan: requirements, design as text, project scripts

Status 2026-10-29: plan; phase 1 (1.1 to 1.8), 3.1 to 3.5, 3.7 and the follow-ups below are done; 2.1 to 2.4 are built
and wait for their live run in EasyEDA; the offline part of 3.6 and 4.3 are being built. It builds the three concepts of
this folder after the user took their decisions on 2026-10-28 (e5caf42, 301fd90): [requirements.md](requirements.md),
[design-as-text.md](design-as-text.md) and [project-scripts.md](project-scripts.md). Each step starts when the user asks
for it.

## Ground rules

- **One step, one branch.** A step is built with the skill add-feature, a new check with add-rule: a failing test
  first, then the interface, the code, the handbook, `pytest` and `ruff`. It goes to main when the user says so, after
  a notice to pytree-27; then the shared tree follows, and the plugin when skills or code changed.
- **No key, no change.** Every new key, file and check leaves a project without it as it is. The bell and the
  reference project change only at the user's request, in their own repositories.
- **Hashes are named.** A step that changes a hash says which one, and for which sign-offs (table at the end).
- **The bell is told.** All sessions run the edakit of the shared tree. The user decided on 2026-10-28 not to wait for
  the bell's order: a step goes to main when it is ready, and one that changes the bell's gate result or hashes is
  announced to the bell's session first.
- **EasyEDA steps in one sitting.** Steps that need EasyEDA take its claim, probe on a throwaway document (working
  agreement 18) and run together while EasyEDA is free.
- **This file is the list.** The state of each step is in the overview; a finished step names its commit.

## Overview

| Step | What | Concept, decision | Size | EasyEDA | Waits for | State |
| --- | --- | --- | --- | --- | --- | --- |
| 1.1 | README: "circuit design as code", with "Status and limits" | design-as-text 1, 2 | S | no | – | done (ef6b2aa) |
| 1.2 | Read `[scripts.*]` and check that they resolve into a DAG | project-scripts block 1, decision 1 | M | no | – | done (37376e8) |
| 1.3 | Names for edakit's data, each with a hash | project-scripts block 2 | S | no | 1.2 | done (74279e8) |
| 1.4 | Stamps in `hardware/scripts.lock`; `edakit scripts` | project-scripts block 3, decision 2 | M | no | 1.3 | done (af6d0b9) |
| 1.5 | Requirements: format, parser, `edakit req` | requirements order 1, decisions 1–3 | M | no | – | done (ba4d28b, f7adcf4) |
| 1.6 | Requirements: checks, protocol section, `accept` lines, circuit hash | requirements order 2, decisions 4, 6, 8 | M | no | 1.5 | done (384385e) |
| 1.7 | `[order]`: mask and print colour, thickness from `thickness_mm` | design-as-text, smaller findings | S | no | – | done (80c750e) |
| 1.8 | The footprint geometry in the repository | project-scripts block 5, decision 5 | S | no | – | done (d63a81a) |
| 2.1 | Positions of the auto-layout as text, one-time takeover, every part in the plan | design-as-text gap 1, decisions 3, 4 | M | yes | – | built offline (5d8a5df), live run open |
| 2.2 | Rule set of EasyEDA's DRC | design-as-text decision 6 | S–M | yes | – | built offline (a71567f), live probe open |
| 2.3 | Positions of single designators in `[silk]` | design-as-text, smaller findings | S | yes | – | built offline (112de3a), live run open |
| 2.4 | Outdated inputs run first; `edakit run` | project-scripts block 4, decision 7 | M | yes | 1.4 | built (47ae793), live check open |
| 3.1 | Checks in the gate: `at`, phase `acceptance`; then `verify = script` | project-scripts block 6 | M | no | 1.2, 1.6 | done (9e63afd) |
| 3.2 | Project agents: `[agents.*]`, `replaces`, their sign-offs required | project-scripts block 7, decisions 10, 11 | M | no | 1.2 | done (8d3cc15) |
| 3.3 | Skills and the SessionStart hook use `edakit scripts` | project-scripts block 8 | S–M | no | 2.4, 3.2 | done (9b4d834, 834f623) |
| 3.4 | Skill `requirements`, agent `requirements-engineer`, reviewers read the file | requirements order 3, decision 7 | M | no | 1.6 | done (0099ee3) |
| 3.5 | `req:` as a source of value blocks | requirements order 4 | S | no | 1.5 | done (abf40d4) |
| 3.6 | Own footprints as data in the parts entry | design-as-text gap 2, decision 5 | L | yes | 1.8 | offline part being built |
| 3.7 | Project setup: `new-project` with two ways, agent `project-surveyor` | project-setup, decisions 1–6 | M | no | 3.2, 3.4 | done (92db89f) |
| 4.1 | Bell: requirements file | requirements order 5, decision 9 | M | no | 3.4, the bell's order | open |
| 4.2 | Bell: entries for `kunst` and `tdisplay` | project-scripts example | S | no | 2.4 | open |
| 4.3 | Bell: the circuit as a language and as TOML with names, then the choice | design-as-text decision 8 | M | no | – | being written |
| 4.4 | Tree: its positions, scripts, agents and requirements | all three | M | yes | the tree's move, 2.1, 3.7 | open |
| 4.5 | The requirements file becomes required | requirements decision 5 | S | no | 4.1, 4.4 | open |

S, M and L are the sizes the concepts give: small, medium, large.

Follow-ups the user decided on 2026-10-28, done: a draft requirement only warns and never blocks (1.6, b885376); the
order settings that change the made board join the fab hash (b5af0c6), and `edakit cost` names an order that deviates
from the board it prices (5a51877) (1.7). `edakit cost` no longer fails on a board nobody assembles (09f591d). Further,
on the user's word: the regulatory review says everywhere that it is support and not legal advice (0fddac4); `python` in
a project check is edakit's own (cfe053c); a missing sign-off file leaves the required checks open (2bb219f).

```mermaid
flowchart LR
  subgraph P1["1 · offline"]
    s11["1.1 README"]
    s12["1.2 script entries, DAG"] --> s13["1.3 data names"] --> s14["1.4 stamps"]
    s15["1.5 requirements file"] --> s16["1.6 requirement checks"]
    s17["1.7 order settings"]
    s18["1.8 geometry in the repo"]
  end
  subgraph P2["2 · with EasyEDA"]
    s21["2.1 positions as text"]
    s22["2.2 DRC rules"]
    s23["2.3 designators"]
    s24["2.4 scripts run"]
  end
  subgraph P3["3 · larger pieces"]
    s31["3.1 checks in the gate"]
    s32["3.2 project agents"]
    s33["3.3 skills, session"]
    s34["3.4 requirements engineer"]
    s35["3.5 req: in value blocks"]
    s36["3.6 footprints as data"]
    s37["3.7 project setup"]
  end
  subgraph P4["4 · in the projects"]
    s41["4.1 bell: requirements"]
    s42["4.2 bell: scripts"]
    s43["4.3 bell: language sketch"]
    s44["4.4 tree moves"]
    s45["4.5 requirements required"]
  end
  s14 --> s24 --> s33
  s12 --> s31
  s16 --> s31
  s12 --> s32 --> s33
  s16 --> s34 --> s41
  s15 --> s35
  s18 --> s36
  s24 --> s42
  s32 --> s37
  s34 --> s37
  s21 --> s44
  s37 --> s44
  s41 --> s45
  s44 --> s45
```

## Phase 1: offline

**1.1 README.** The paragraph of design-as-text ("Circuit design as code. Everything a board is made of …") goes to
the head of `README.md`. "Status and limits" lists what is not text yet: the positions of the auto-layout (2.1), own
footprints (3.6), the DRC rule set (2.2), mask and print colour (1.7), single designators (2.3), and the two clicks
in EasyEDA. Each later step removes its line. Documentation only, so it may go to main at once.

**1.2 Script entries.** `edakit/config.py` reads `[scripts.<name>]` with the fields of the concept; a new module
resolves them together with edakit's fixed steps and reports R1–R9 in `edakit check`. `[[release.stages]]` and
`sim_plugin` count as the kinds `check` and `sim`, and the old keys keep working. Tests: one fault per rule, as the
concept's prototype did with 28 copies. The prototype is kept in
[prototypes/project-scripts](prototypes/project-scripts/); its README names what the decisions changed since.
Its rules and cases become `tests/test_scripts.py`.

**1.3 Data names.** `graph`, `parts`, `sim`, `board:<b>`, `footprints:<b>`, `routing:<b>`, `mech:<b>`, `gerber:<b>`,
`release` and `firmware`, each with its hash; `gerber:<b>` takes `fab_layers` of the fab hash. To settle on the way:
the name for the project library that `easyeda` scripts change (the concept proposes `project-library:<b>`).

**1.4 Stamps.** `hardware/scripts.lock` holds per script the hashes of its `reads` and of the script itself at its
last run, as `edakit sim` stamps its result (`inputs_sha256`). A difference is a finding in `edakit check` and in the
gate, with the `about` sentence. `edakit scripts` lists every script with `about` and its state: current, outdated,
never run.

**1.5 Requirements file.** `[project] requirements` (default: none) names `hardware/requirements.toml`; a variant
names the main project's file and its own. The parser reads `[[need]]` and `[[requirement]]`: `id`, `text`, `from`,
`binding`, `verify`, `status`, `reason`. `edakit req` lists them with status and evidence; `edakit req R-4` shows one
chain. The file covers only the circuit (decision 3). Test in `led-bar` with a small file.

**1.6 Requirement checks.** New catalog checks with add-rule: every reference resolves, every accepted need has a
requirement, every requirement has evidence, drafts warn. `must` without passing evidence blocks the release,
`should` warns, `may` informs. The gate protocol gets a section "Requirements"; `accept` steps join the acceptance
list of section 6 with their ID; the file joins the circuit hash byte for byte. The catalog letter for the new checks
must not be R or N, the prefixes of the requirement IDs. `verify = script` reports "not evaluated yet" until 3.1.

**1.7 Order settings.** `[order]` gets the colours of solder mask and silkscreen; the thickness comes from
`thickness_mm`, which feeds only the mechanical model today. F-6 and `order.md` name them.

**1.8 Geometry in the repository.** `pcb_geometry_<b>.json` moves from `build/` to a versioned place, so CI and a
fresh clone can compute the layout hash. The path counts in the hash, so the layout hash changes once and sign-offs
with scope `layout` are recorded again. The bell's M-5 has scope `fab` (D-20) and keeps counting.

## Phase 2: with EasyEDA

**2.1 Positions as text.** In this order:

1. `edakit pcb autolayout` writes position, rotation and side of every part it placed as `auto = true` rows into
   `[place]` of the board file, with `write_place_rows` from #57 (decision 3).
2. A one-time takeover reads the positions of a board placed before from EasyEDA and writes them as fixed rows,
   without a new auto-layout.
3. A check in stage L, as an error: every part of the graph has a row (decision 4). `led-bar` lacks D1 and R2 and
   gets them first; the bell has all 19 parts on all four boards.

The bell's session is told first, since board files change.

**2.2 DRC rules.** First a probe on a throwaway document of what `PCB_Drc` carries. Reading works
(`getCurrentRuleConfiguration`, with the bridge's return depth 12), and net rules can be written
(`overwriteNetRules`). If a whole rule set can be written, edakit writes it from the board file; otherwise it reads it
and checks it against the board file (decision 6).

Found without EasyEDA (handbook 9.4): the format, from the reference project's read of 2026-10-22 on 3.2.206
(`tests/fixtures/easyeda/drc_rules_3.2.206.json`); the signatures, from the client's `pro-api/0.3.50…/api-types.d.ts`;
and from its editor bundle that `overwriteCurrentRuleConfiguration` and `overwriteNetRules` put what they get into the
PCB's rules without a check and answer true, and that the net classes are the `netClass` entries of the net rules.
Built on the branch, for every project without effect until it opts in: `edakit/drc_rules.py` (the board file's rule
set, the differences to EasyEDA's, what edakit would write), `eda.read_drc_rules` and `eda.write_drc_rules` (the
second not run), and a third row of L-3 with `[routing] drc_rules = "check"`.

The live probe, in one sitting with the EasyEDA claim; EasyEDA unthrottled, the patched bridge (`edakit doctor`):

1. **Throwaway document** (agreement 18): a project `edakit-probe-drc` made by hand (File → New → Project), its PCB open
   and active. Three free pads put nets into it: `PCB_PrimitivePad.create(1, "1", 0, 0, 0, ["ELLIPSE", 60, 60], "VIN",
   null, 0, 0, 0, false, 0)`, the same with `"2"`, `0, 200`, `"+5V"` and `"3"`, `0, 400`, `"GND"`. Tracks of 10 mil on
   TOP (`PCB_PrimitiveLine.create(net, 1, x1, y1, x2, y2, 10, false)`): VIN 1000,0 → 2000,0 and +5V 1000,15.9 →
   2000,15.9 – 0.150 mm apart; VIN 1000,300 → 2000,300; and on BOTTOM (layer 2) VIN 1000,500 → 2000,500.
2. **Read and keep:** `eda.read_drc_rules` (or the three `easyeda_api_call`s) into the scratchpad as the restore
   point, and `getCurrentRuleConfigurationName`, `getAllRuleConfigurations(true)` (the names),
   `getDefaultRuleConfigurationName`. Expected: no `[MaxDepth]`, likely the name "JLCPCB Capability(Two Layers
   Board)" (the types' note for a PCB that never had other rules), the kinds and row/column lists of the recording, a
   Track–Track value below 0.15 mm. `PCB_Drc.check(true, false, true)` → DRC A.
3. **Write one value:** the configuration with Track–Track of the default Safe Spacing rule at 0.2 mm,
   `overwriteCurrentRuleConfiguration(config)` (the inner `config`) → true; read back: 0.2, the name unchanged, the
   named configurations unchanged; Design → Design Rule shows 0.2 mm. DRC B: a Clearance Error between VIN and +5V
   that A did not have – the DRC uses what was written, at once.
4. **Kept:** save, close, open the PCB again (`eda.reload_pcb`), read back: still 0.2 mm (agreement 16). A second PCB
   of the throwaway project (made by hand) still reads the value of 2: the rules are the PCB's own.
5. **Classes and track rules:** `createNetClass("POWER", ["VIN", "+5V"], null)` → true; `getNetRules` shows the class
   with VIN and +5V under `sub` – which rules do the moved nets keep? A Track rule `POWER` (min 0.4572 mm, entries
   "1" and "2") through `drc_rules.config_for`, the net rules through `drc_rules.net_rules_for`, written as in 3. DRC C:
   a width finding on both 10-mil VIN tracks, TOP and BOTTOM. With only the entry "1" in the rule: is the BOTTOM track
   still found? (What a lone "1" covers.) Then save, reload, read back.
6. **edakit's way:** a board file in the scratchpad with led-bar's `[routing]` and an edakit.toml naming the throwaway
   project; `eda.write_drc_rules(mcp, drc_rules.wanted(board))` → `[]`; `eda.reload_pcb`; `drc_rules.differences`
   on a new read → `[]`; DRC D: the board file's rules at work – the 10-mil VIN tracks found (class POWER, 18 mil),
   the gap of 0.150 mm found (clearance 6.5 mil = 0.165 mm).
7. **Restore and clean up:** `overwriteCurrentRuleConfiguration` and `overwriteNetRules` with the restore point,
   `deleteNetClass` for what was made, read back = the restore point; the named configurations and the default name
   as in 2; the throwaway project deleted by hand.

What decides: if 3 and 4 hold and 5 and 6 hold, edakit writes the rule set (a value `"write"` of `drc_rules`: `route
all` writes it before its DRC; the gate goes on checking, it changes nothing). If the configuration holds (3, 4) but
classes or net rules do not (5), edakit writes the configuration and checks the classes. If a written value does not
survive the reload, the DRC ignores it, or it reaches another PCB or a named configuration, edakit only reads and checks
– the row of L-3 as built. The answer goes into handbook 9.4 and this step's line.

**2.3 Single designators.** A position per designator in `[silk]`, as `[place]` has one per part; `silk apply` keeps
it.

**2.4 Scripts run.** `pcb apply`, `silk apply` and `gate` run the outdated `input` scripts they read first
(decision 7). `edakit run <name>` runs one script; an `easyeda` script runs only so, under the EasyEDA claim, and what
it changes makes the steps after it outdated.

### Live runs of phase 2

2.1 to 2.4 are built and tested without EasyEDA; their EasyEDA part waits for a session with the user. Claim EasyEDA
first (`edakit lock claim --note "live runs"`), with EasyEDA unthrottled and the patched bridge (skill `start`), and
release it at the end. 2.2's probe is written out above.

**2.1 Positions as text** (`pcb autolayout` writes `auto = true` rows, `pcb takeover` takes a placed board, L-20):

1. On a scratch copy of the bell with all `[place]` rows deleted: `edakit pcb takeover` in main and in
   `variants/esp32`, `smd` and `tht` shows 19 rows per board, without `auto`, each equal to the real board file's
   row; nothing is written.
2. In a throwaway led-bar project (made by hand once) without the rows of D1 and R2: `schematic create --save`,
   `schematic layout --save`, `pcb parts --write`, `pcb dump`, `pcb apply` (two parts unlocked), then
   `pcb autolayout`. It writes two `auto = true` rows at the end of `[place]` and nothing else; a second run writes
   nothing; `pcb dump` and `pcb apply` bring D1 and R2 back to their rows.
3. After `route all`, delete every row but U1, U2, J1 and SW1: `pcb takeover` shows 13 rows, `--write` writes them
   fixed, `pcb apply` leaves the parts on their tracks (pad check about 0), `route drc` finds nothing new.
4. `edakit gate --easyeda` shows L-20 with every part in a row and L-7 passing.

**2.3 Single designators** (`[silk.place]`), on a throwaway or led-bar, e.g. `R1 = { x = 59, y = 20, rot = 90 }`,
then `edakit silk apply`:

1. R1's designator stands at the given spot and rotation, centred and visible; the summary says "fixed: R1"; the
   other designators and the board label keep clear of it.
2. 90, 180 and 270 read as expected, and an angle such as 45 prints as the turned box.
3. A row on the other side of its part gives a free text there (mirrored on the bottom), the part's own designator
   is hidden, and a second `silk apply` replaces the text instead of doubling it.
4. A row on a pad prints the finding and exits 2; the Gerber check after the run reports the overlap.
5. `edakit gate --easyeda` shows the expected L-17 rows; on a board with `view = "bottom"`, check whether `rot`
   reads right from below.

**2.4 Scripts run** (`edakit run`, inputs before the steps):

1. `edakit run <easyeda script>` in a Claude session: `edakit lock status` names the run, the script reaches EasyEDA
   under that claim, and a second session gets exit 3; a run over a minute keeps the claim.
2. Afterwards: delete the affected parts in the PCB, `pcb parts --write` (recreated with the new footprint, tracks
   kept?), `pcb dump` and `route all`; the warning about the changed project library clears.
3. `pcb parts`, `pcb apply`, `route all`, `silk apply` and `gate --easyeda` with an outdated input: the input runs
   before the EasyEDA work.

## Phase 3: the larger pieces

**3.1 Checks in the gate.** A `check` script gets its place (`at`: before S, or after F to see the run's Gerber data)
and its phase (`export`, `order`, `acceptance`); `advisory` only warns. With this, `verify = script` of the
requirements counts.

**3.2 Project agents.** `[agents.<name>]` with `file`, `about`, `signs`, `replaces`, `scope`, `phase`, `after`, and
the rules R10 and R11. The gate requires their sign-offs. With `replaces`, a project's agent signs M-1, M-5 or M-6 in
place of edakit's and takes over the round review too.

**3.3 Skills and the session.** `start`, `pcb-round`, `hardware-change`, `release` and `new-project` call
`edakit scripts` at their steps and start project agents at their hook points. The SessionStart hook (#74) lists the
scripts with their `about`.

**3.4 Requirements engineer.** The skill `requirements` collects in the conversation, asks back in a decision round,
writes drafts and has them approved. The agent `requirements-engineer` makes the inventory and gives a second opinion;
it changes nothing. `circuit-design` §1 reads the file. The electrical reviewer judges the requirements with
`signoff = "M-1"`, the PCB reviewer those with M-5, the regulatory reviewer those with M-6. The plugin test that lets
the reviewer prompts name only catalog IDs learns N- and R-.

**3.5 `req:` in value blocks.** Documents in `[docs] files` quote a requirement by its ID, and G-19 finds a stale
quote (#71).

**3.6 Footprints as data.** The parts entry gets a footprint as data: origin, pads as `part import` caches them,
outline and print. A command builds the project's copy (a system part as carrier, then rebuilt), a check holds the
copy to the data, and a library footprint can become an own one. The data counts in the circuit hash, because M-1
checks polarity, and in the layout hash (decision 5). It would replace the bell's `tdisplay_device.py` and the tree's
`led_footprints.py`.

## Phase 4: in the projects

Each at the user's request, in the project's repository.

**4.1 Bell: requirements.** After its order: the agent's inventory, a decision round (the servo supply, D-3 against
the README), the file, only for the circuit. M-1 and M-6 open again, as decision 9 expects.

**4.2 Bell: scripts.** `kunst` for all four configurations and `tdisplay` for esp32, as in the concept's example.

**4.3 Bell: language sketch.** The whole bell written down twice, as a language of its own and as TOML with pin
names; then the user chooses (decision 8). Building the language would be a step of its own, size L.

**4.4 The tree moves.** When the reference project moves to edakit after its order (EK-1 of its concept): the
takeover of its positions (2.1), seven of its eight scripts – `review` only reads the release (decision 8) – with
`platine` writing into `tree.toml` (decision 4), its agents `elektrotechniker` and `pcb-pruefer` with `replaces`, and
its requirements file.

**4.5 Requirements required.** Once the bell and the tree have a file, a project without one fails the gate
(decision 5).

## Hashes and gate results

| Step | Circuit hash | Layout hash | Gate result |
| --- | --- | --- | --- |
| 1.6 | adds `requirements.toml`, where a project names it | – | new rows; `must` without evidence blocks, only in projects with the file |
| 1.8 | – | changes once (the geometry's path) | – |
| 2.1 | – | changes when rows are written | a new error for parts without a row |
| 3.2 | – | – | a project agent's sign-off is required, where a project registers one |
| 3.6 | changes where footprint data is added | changes likewise | a new check: the copy equals the data |
| 4.5 | – | – | a missing requirements file blocks |

## Working in parallel

Three tracks can run side by side, each in its own worktree:

- project scripts: 1.2 → 1.3 → 1.4 → 2.4 → 3.1, 3.2 → 3.3;
- requirements: 1.5 → 1.6 → 3.4 → 3.5;
- design as text: 1.1, 1.7, 1.8, 2.1–2.3, 3.6.

They meet in `edakit/release/gate.py` (1.6, 1.8, 3.1, 3.2, 4.5) and `edakit/config.py` (1.2, 1.5, 1.7, 2.3, 3.2).
Steps that share one of these files go to main one after the other, and the next one is rebased first.

## Start

1. 1.1, the README: documentation only, may go to main at once.
2. 1.2 and 1.5 side by side on branches. They need neither EasyEDA nor the bell.
3. Each step goes to main when it is ready; then 1.8 and 2.1.
