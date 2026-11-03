# Verification and validation: a handbook chapter for how edakit is tested

Status 2026-11-03: concept, asked for by the owner the same day – "I have the feeling our extensive V&V setup gets
lost in the documentation. Proposal: a chapter of its own in the handbook with the test setup, the reference circuits
included, and their description – why exactly these, what must be true to add another one, …". Written against main
at `dc561ef`; every number below counted there. Decided by the owner the same day in a decision round (decisions 1 to
4 as recommended, Claude's own decisions confirmed – "Decisions" at the end). VV.5 done the same day: TD-118 to
TD-121 in `TODO.md`. Built the same day on the owner's word ("Mach alle diese todos") and merged on the owner's
OK as edakit 1.1.4 (#281): VV.1 to VV.4 – handbook chapter 19 – and the four open designs TD-118 to TD-121; moved to
`done/`. The known gaps the new designs showed are TD-124 to TD-133.

## Why

edakit is tested in nine layers, from synthetic engine tests to published open designs, live runs at the makers and
evals with two models. A reader meets them in pieces:

| Where | What it says about the testing |
| --- | --- |
| `docs/working-on-edakit.md`, "Tests" and "Evals" | four sentences on the test layers, three on the evals, a list of the documentation's tests |
| `docs/adding-a-rule.md`, "Seen red once", "Against real circuits" | a new rule is seen red on led-bar and runs on the reference circuits and the open designs |
| handbook 14.3 | the drawing of the reference circuit `power` and one sentence: "Each domain has such a reference circuit" |
| handbook 14.4 | `edakit mutate` on led-bar (24 of 45 caught without the simulation, 43 with it) and one sentence on the seeded faults |
| handbook 5, 8, 16 | single tests by name: `test_sim.py`, `test_fab_run.py`, the CI job `kicad`, the live runs in `tests/fixtures/makers/LIVE.md` |
| catalog pages `circuits.html`, `open-designs.html` | the most complete view: every reference circuit drawn with its seeded faults, every open design with its judged findings – generated, without a reason for the choice |
| docstrings of `tests/reference.py`, `tests/test_open_designs.py` | the only list of the open designs with source and licence |
| `evals/README.md` | the cases and the baseline – a source, not documentation |
| `docs/concepts/done/rules-at-scale.md` section 7, `maker-coverage.md` FT-21, FT-24 and guardrail 5 | why the layers exist and which circuits were meant |

No page answers the questions a reader has: what a clean `edakit check` proves and what not; why these seven
reference circuits and these six designs; what the judgements real, lacks, criterion and known gap mean; what a new
reference circuit or open design must bring. By the yardstick (`docs/concepts/done/design-as-text.md`), the admission
rules exist only as assertions in `tests/test_reference.py` and `tests/test_open_designs.py` and, for the choice, in
someone's head.

## What exists

The inventory at `dc561ef`: 151 test files with about 2000 test functions, 9 eval cases.

| Layer | Where | What it proves | Kind |
| --- | --- | --- | --- |
| 1 Engine tests | `tests/test_engines.py` | every relation fires on its fault and on nothing else, on small synthetic circuits; LIMITS and PATHS hold their properties at random values | verification |
| 2 Seen red once | `tests/fixtures/led-bar` and `test_checks.py` (73), `test_sim*.py`, `test_gate.py` (35), `test_fab_run.py` (52), many more | every check fires on a fault built into a copy of the example, and the repaired copy is clean | verification |
| 3 Reference circuits | `tests/reference.py`, `tests/test_reference.py` | one circuit per domain, built onto led-bar, passes clean under its domains; each of its 15 seeded faults raises exactly its codes and no other (the overlap test) | verification |
| 4 Wrong judgements held | `test_false_alarms.py` (17), `test_wrong_judgements.py` (12), `test_open_design_fixes.py` (18) | each false alarm once found: the circuit where the finding was wrong stays quiet, the one where it is right still raises it | validation |
| 5 Open designs | `tests/open_designs/` (6), `tests/test_open_designs.py` | published designs transcribed as published; what check and sim find is exactly what `findings.toml` judges – 149 findings: 51 real, 58 lacks, 39 criterion, 1 known gap | validation |
| 6 Mutation sweep | `edakit mutate`, `test_mutate.py` | which built-in mistakes no code catches – a list for reading | validation |
| 7 Documentation held to the code | `test_walkthrough.py`, `test_walkthrough_kicad.py`, `test_quickstart.py`, `test_references.py`, `test_style.py`, `test_catalog*.py`, `test_pages.py` | what the walkthroughs and the quickstart quote still holds; every named section exists | verification |
| 8 Live against external tools | CI job `kicad` (`test_kicad_live.py`, KiCad 10), `tests/fixtures/makers/LIVE.md`, the EasyEDA live test of led-bar on 2026-10-31 | KiCad reads what edakit writes; the cart skill at four makers; the EasyEDA tool chain end to end | validation |
| 9 Evals | `evals/`, `claude plugin eval` | Claude with the plugin finds a seeded fault, reports the coverage, adds an LED – with Sonnet and with Opus | validation |

Verification asks whether edakit does what its rules say; validation whether the rules fit real circuits and the whole
helps a maker. The split is the chapter's spine: it tells a reader which layer answers which doubt.

Two observations from the inventory, for the chapter and not as faults:

- **The open designs are a tripwire.** A new rule that fires on one of them fails `test_open_designs.py` until the
  finding is judged. That is how "a new rule runs on the open designs" (`docs/adding-a-rule.md`) is enforced; the skill
  add-rule names only "the projects at hand" (step 6), which are the owner's projects outside the repository.
- **Some validation is not repeatable from the repository.** The owner's projects (the bell, pytree), the EasyEDA live
  test and the makers' live runs need the owner's machine or accounts. The chapter says which layer a reader can rerun.

### The reference circuits

All seven are edakit's own, shaped after common maker designs and built onto led-bar: parts from the block library's
checked entries, and test entries numbered `C91000xx` with "values for the reference circuit, not from a datasheet"
where the library lacks one. Synthetic on purpose: each fault must raise exactly its codes, which needs a circuit
that is clean without it.

| Circuit | Domain | The circuit | Seeded faults → codes |
| --- | --- | --- | --- |
| `motors` | motors | a 33 Ω motor switched low-side by an S8050, flyback diode SS14 | no flyback diode → REQ.missing; a 10 Ω winding → LIM.i, LIM.p |
| `audio` | audio | class-D amplifier fed from a PWM pin through a 1 kΩ / 10 nF low-pass, bridge-tied to an 8 Ω speaker; an AC run expects 15.9 kHz | an output on ground → REQ.forbidden; the filter capacitor ten times larger → SIM.response |
| `guitar` | guitar | instrument buffer: jack, 2.2 MΩ bias to a half-supply reference, op-amp follower, 1 µF / 100 kΩ output coupling at 1.6 Hz | bias 470 kΩ → REQ.value; reference above the input range → LIM.range; bypass switch to 0 V → REQ.value; coupling ten times smaller → SIM.response |
| `power` | power | three AA cells beside USB through an SS14 onto +5V | the cells' current limit → LIM.i; no diode → PATH.reverse |
| `cables` | cables | a button on a hand-wired remote board, 1 m of AWG 26, 1 kΩ series and 10 kΩ pull-up at the pin | no series resistor → REQ.missing |
| `usb` | usb | USB-C receptacle for data: Rd 5.1 kΩ on each CC, D+ and D− of both rows joined, 27 Ω to the MCU | D+ of one row only → REQ.missing; no Rd on CC2 → REQ.missing |
| `keyboard` | – (rules for every board) | 2 × 2 key matrix, a diode per key, cathodes to the rows | a key without its diode → REQ.missing; a diode turned round → REQ.forbidden |

`test_every_domain_has_a_reference_circuit` holds one per domain except `radio` (a transmitter's facts, no circuit of
its own – covered by the ESP32 DevKitC) and `mains` (recognised, not checked; its fault is built into the example in
`test_hazardous.py`).

### The open designs

| Design | Licence | What it brings that the reference circuits lack |
| --- | --- | --- |
| `esp32-devkitc-v4` | none stated – only the circuit's facts | usb, radio and power in one board; the only real transmitter |
| `sparkfun-logic-level-converter` | CC BY-SA 3.0 | four BSS138 channels, level shifting in both directions simulated |
| `corne-cherry-left` (v4) | CC BY 4.0 | RP2040 with USB-C, 23 keys on direct pins, a chain of 23 SK6812MINI-E one diode below 5 V |
| `corne-cherry-v3-left` | MIT | a real key matrix of 21 keys with a diode each, Pro Micro, 27 RGB LEDs |
| `guitarml-classic-boost` | MIT | a discrete common-emitter stage, its bias across the hFE spread (FT-17) |
| `guitarml-ts-rat-combo` | MIT | op-amp and JFET stages, a 3PDT order switch; a reversed electrolytic found real |

FT-21 (`maker-coverage.md`) named further candidates that are not built: a WLED controller, a Fuzz Face, a relay board
with an HLK-PM01, a LiPo charger.

## The chapter

**Handbook chapter 19, "Verification and validation: how edakit is tested"**, file `handbook/19-verification.md`,
in the group "Reference" of the handbook's index, read when "you want to know how far a finding or a clean check can
be trusted, or you add a reference circuit or an open design". Register: a guide (`docs/style.md`), at most 500
lines.

Why the handbook: `docs/organisation.md` keeps the handbook for those who use edakit, and the chapter's first question
is a user's – what does a clean check prove? The reference circuits are shown to users already (14.3, the catalog).
And the admission rules are needed by whoever proposes a circuit, a project with `/edakit:propose-feature` included.
The step-by-step for a session stays where sessions read it (`docs/working-on-edakit.md`, the skill add-feature), and
links to the chapter.

| Section | Content | Written |
| --- | --- | --- |
| 19.1 What the testing proves | what a clean check and a clean simulation mean, and their limits: findings rest on part facts (`--coverage`), the reference circuits' test entries are not real parts, a known gap is a known wrong judgement, the regulatory review is support and not legal advice (15) | by hand |
| 19.2 The layers | the table above, each layer with what it proves, verification or validation, where it runs (CI jobs `test` and `kicad`, by hand, evals) and whether a reader can rerun it | by hand |
| 19.3 The example led-bar | the base every fault is built into: 17 parts, 18 nets, MCU, LED driver, connector, reverse diode, button; why a fixture of its own beside the walkthrough examples of chapters 17 and 18 | by hand |
| 19.4 The reference circuits | one entry per circuit: what it adds, why this circuit for its domain, its seeded faults with their codes, a link to its drawing in the catalog | generated |
| 19.5 The open designs | one entry per design: source, licence, why chosen, its findings counted by judgement, its known gaps | generated |
| 19.6 How a finding is judged | real, lacks, criterion, known gap – what each means, and how a user reads the same words on their own findings | by hand |
| 19.7 Adding a reference circuit or an open design | the admission rules below, and the way in: a proposal from a project, or the skill add-feature in the repository | by hand |
| 19.8 The evals | what they measure, the cases, the baseline, how to read a score – one run is a reading, not a rate | by hand, the baseline quoted from `evals/README.md` |
| 19.9 What is not covered | radio and mains without a reference circuit, the open candidates of FT-21, the known gaps, what `edakit mutate` leaves on led-bar, the stages that only live runs reach | by hand, the counts generated |

**Generated, not copied.** 19.4 and 19.5 list values, faults and counts that change with every circuit, fault or
judgement. Copied by hand they drift, as the catalog's own pages would. They are generated, as the handbook's tables
of codes are, between `<!-- edakit:generated … -->` markers, from `tests/reference.py` (`REFERENCES`, `FAULTS`, the
docstrings) and from each design's `README.md` and `findings.toml`; a test fails when the chapter is out of date. The
"why" of each circuit and design moves into those sources (VV.1), so that the catalog page and the chapter say the
same.

### The admission rules

What a new one must bring – the chapter's 19.7, held by tests where they can be counted (VV.4).

**A reference circuit** (`tests/reference.py`):

1. **A gap of its own.** It brings a domain no reference circuit covers, or a family of codes of a covered domain that
   no seeded fault raises yet. A new domain needs one (held already).
2. **Built onto led-bar** as one function in `REFERENCES`: designators from 20, the MCU pins it uses freed, a block of
   its own in the drawing, the board titled "Reference: <name>".
3. **Its parts named honestly.** The block library's checked entries first; a test entry only where the library lacks
   one, numbered `C91000xx`, `verified.by = "reference circuit"`, its source "values for the reference circuit, not
   from a datasheet".
4. **Clean.** No error, warning or pending finding in check, no row of the simulation that fails or warns; its domain
   switched on by the graph alone (held already).
5. **Its faults exact.** At least one seeded fault per family of codes it is there for, each a mistake a maker makes,
   each raising exactly its declared codes (held already); a fault only the simulation shows where the domain has a
   rule of the simulation.
6. **Described.** The docstring says what the circuit is with its values; a `why` says why this circuit stands for
   its domain. Both are what 19.4 shows.
7. **Small enough to read.** Drawn on one page by `edakit schematic draw` (the catalog page).

**An open design** (`tests/open_designs/<name>/`):

1. **Published, and the licence allows it.** A schematic anyone can open; its `README.md` names the source with its
   commit or revision, the licence – a CC licence with its URI –, and every change; a row in `README.md`'s licence
   table (held already). Without a stated licence only the circuit's facts are transcribed, not the drawing.
2. **Something the others lack.** A domain or a circuit class no reference circuit and no open design covers, with
   real parts and their datasheets; preferably a design makers build and copy, so that a false alarm there would meet
   many.
3. **Transcribed as published.** Not repaired; a stand-in for an unnamed part named in the README; every parts entry
   names its datasheet and fits the schema (held already).
4. **Every finding judged.** Each finding of check and sim in `findings.toml` with its judgement and a reason (held
   already); a false alarm it shows is fixed and held in `test_open_design_fixes.py`, or kept as a known gap with the
   reason.
5. **Described.** A `why` line in its README: what it brings – what 19.5 shows.

## Steps

| Step | What | Where | Lane |
| --- | --- | --- | --- |
| VV.1 | The descriptions into the sources: a `why` for each of the seven reference circuits and six open designs, written from the tables above and checked against `maker-coverage.md` FT-21 | `tests/reference.py`, `tests/open_designs/*/README.md` | branch |
| VV.2 | The generator: 19.4, 19.5 and the counts of 19.9 written from the sources, a test that fails when the chapter is out of date | `docs/catalog/build.py` (it reads `tests/reference.py` and `tests/open_designs/` already), a test beside `tests/test_catalog_page.py` | branch |
| VV.3 | The chapter: the sections by hand; the handbook's index, `docs/pages.py` (`NAV`), `docs/organisation.md` ("chapters 1 to 19"), the glossary (reference circuit, open design, seeded fault, seen red once, the four judgements); `docs/working-on-edakit.md`, `docs/adding-a-rule.md`, handbook 14.3 and 14.4 link to it, their statements kept in their sections | `handbook/`, `docs/` | branch, a fragment `patch` – the handbook is outside `NO_VERSION` |
| VV.4 | The countable admission rules as tests: a test entry of a reference circuit numbered `C91000xx` and marked; a `why` for every reference circuit and every open design | `tests/test_reference.py`, `tests/test_open_designs.py` | with VV.1 |
| VV.5 | The open candidates of FT-21 – WLED controller, Fuzz Face, HLK-PM01 relay board, LiPo charger – each as an item in `TODO.md`, each built later through the admission rules – done 2026-11-03: TD-118 to TD-121 | `TODO.md` | notes lane |

VV.1 to VV.4 are one branch (TD-117); the chapter is the work, the generator keeps it true.

## Decisions

Taken by the owner on 2026-11-03 in a decision round, each as recommended; the alternatives stay for the record.

| # | Question | Decided | Not taken |
| --- | --- | --- | --- |
| 1 | Where the chapter goes | handbook chapter 19: the trust question is a user's, the reference circuits are shown to users already, and proposals come from projects | a reader page `docs/testing.md` beside `docs/working-on-edakit.md`, for developers only; a section 14.7 in "Designing a circuit" |
| 2 | How 19.4 and 19.5 are written | generated from the sources, the "why" moved into them: seven circuits and six designs with values, faults and counts drift when copied | by hand, held by a test that only checks every name appears |
| 3 | The admission rules | as above, held by tests where they can be counted | as text only; only what the tests hold today |
| 4 | FT-21's open candidates | named in 19.9 and listed in `TODO.md`, built later one by one | built with the chapter; dropped |

Decided by Claude and confirmed by the owner the same day: the number 19 and the file `handbook/19-verification.md`;
the group "Reference" in the handbook's index; the split verification / validation as the chapter's spine; the steps
VV.1 to VV.5, VV.1 to VV.4 one branch with a fragment `patch`; the step-by-step for sessions staying in
`docs/working-on-edakit.md` and the skill add-feature; VV.5 done at once as TD-118 to TD-121, the chapter's build as
TD-117.
