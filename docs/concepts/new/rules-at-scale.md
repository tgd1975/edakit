# Rules at scale

Status 2026-10-30: proposed; the owner has taken the four decisions at the end, nothing is built. It answers the owner's concern that the rule catalog does not scale –
electrically (are the rules consistent, free of contradiction, correct?) and in use (many rules, most of them
irrelevant to a given project, too much context for the model, which must work with Sonnet). It builds on
[maker-coverage.md](maker-coverage.md) (what is missing) and [circuit-language.md](circuit-language.md) (the graph's
form). Numbers are measured at edakit `bf7450a` unless marked as estimates.

## The problem

Today one lesson becomes one check ID: a function, a negative test, a catalog entry, a handbook row, often a reviewer
question. 67 checks and 9 hints came out of two projects. maker-coverage lists about 110 more candidates. Scaled the
same way, three things break:

- **Electrically.** Rules overlap (G-4 and an `nc` input, G-11 and other open-drain lines, G-12 and voltage-window
  straps) and contradict (H-1 asks for a bulk capacitor at a power input, USB allows 10 µF at attach). Each number sits
  in a rule's prose, where no program can compare it with another rule's.
- **Correctness.** One negative test proves that a rule can fire. It does not prove that the rule never fires wrongly.
  The run against real projects covers the owner's boards – none of them has audio, mains or a guitar circuit.
- **In use.** `edakit rules` prints 27.5 KB. The handbook repeats every check in a table by hand. Hints and reviewer
  questions grow with every domain and reach every board. A session reads rules it does not need.

## The proposal

Few engines, much data, a profile per project.

- A **check** is no longer a function per lesson. It is one of about ten **engines**, each applying one kind of typed
  data: limits a part declares, requirements a part makes on its pins, the states an input must be defined in, the
  paths a reversed or hazardous voltage can take, the distances a voltage class needs.
- **New knowledge is a row of data with a source**, not code. A new finding code only for a new relation.
- A project declares its **domains**. A domain is a profile – data, not code – that switches finding codes on, sets
  their severity, names the part facts it requires, its hints, its reviewer questions and its reference circuits.
- **The model sees findings, never rules.**
- **Correctness is tested at the engine level:** reference circuits that pass clean, seeded faults that are found, and
  an automatic mutation sweep that measures what the catalog misses.

## 1. Engines

Illustrative mapping of today's checks; fixed when built.

| Engine | Decides | Absorbs | Reads |
| --- | --- | --- | --- |
| STRUCT | the graph is well-formed and names what exists | G-1, G-2, P-1, P-6, P-9 | graph, parts entries |
| SYNC | every artifact equals the graph and the plan | S-2, L-1, L-4, L-7, L-10, L-12, L-20, P-3, P-10, F-1, F-3, F-4, F-5 | schematic, PCB, plan, files |
| LIMITS | every quantity stays within the limit its part or a table declares | G-3, G-8, G-17, G-24, G-25, E-2, E-3 (ranges), E-5, L-5, L-16 | declared ranges, simulation, geometry; `ratings`, tables |
| LEVELS | every input is defined in every state – reset, firmware not running, each scenario, a rail off | G-4, G-5, G-12, E-3 (input levels) | pin types, `strap`, `pull`, thresholds |
| REQUIRES | what a part requires on its pins is present in the circuit | G-6, G-11, G-13, G-14, G-18 | `needs` in parts entries, built-in defaults per kind and role |
| PATHS | what a reversed, backfed or hazardous voltage reaches | G-10, G-16, H-8's matcher | pass-through sets, voltage domains |
| SIM | the scenarios run and are complete | E-1, E-4 | sim.json |
| GEOMETRY | copper, holes, print and distances on plan and Gerber files | L-2, L-3, L-8, L-9, L-11, L-13, L-14, L-15, L-17, L-18, L-19, P-7, P-8 | plan, geometry, Gerber files; distance classes |
| FILES | the manufacturing files and sheets are complete and consistent | P-2, F-6 | gate run |
| SOURCING | parts are identified, verified, stated and orderable | G-9, P-4, P-5, P-11, F-2 | parts entries, stock |
| DOCS | documents and requirements quote the design | G-19 to G-23 | docs, requirements file |

**Finding codes.** Decided: today's IDs stay valid, and a new scheme may replace them where it makes sense. Proposed
scheme: a code names its engine and its relation – `LIM.v` (a voltage above a limit), `LIM.i`, `LIM.p`, `LIM.t`,
`LIM.band`, `REQ.missing` (a requirement a part makes is not met), `REQ.conflict`, `LVL.undefined` (an input without a
level in a state), `LVL.contention`, `PATH.reverse`, `PATH.unfed`, `GEO.spacing`, `GEO.copper`, `SYNC.pcb` – about
forty codes for today's 67 checks and the candidates together (estimate). A code says what kind of finding it is
without a lookup, which serves the model as much as the user. Today's IDs become permanent aliases in the catalog, as
the retired G-7 keeps its entry today: `edakit explain G-8` resolves to `LIM.v`, and `waive`, accepted warnings and the
`rows` patterns of the requirements file accept both. The stage (P, G, E, S, L, F) is a property of the finding – where
it was computed –, not of the code: LIMITS fires in stage G on declared ranges, in E on the simulation, in L on the
geometry, and the gate's protocol still groups by stage. New knowledge of an existing relation is a row of data; a new
code only for a new relation. Where a code of today maps to several relations (E-3 holds supply ranges, input levels
and back-feed), the alias names them all. The exact vocabulary is fixed in step 1.

**One finding format**, so that every message says the same four things – where, measured against what, from which
source, what to do:

```text
LIM.v  G  C1: 7.5 V across, rated 6.3 V (needs × 1.5 = 9.5 V)   ratings.v_max of C439782 (datasheet p. 2)   → a 16 V part
```

Code, stage, location, measured against what, source, fix – the same six for every finding.

## 2. Data

Knowledge lives in three places, each with a source per value.

| Place | Content | Checked by |
| --- | --- | --- |
| parts entry | ratings, thresholds, `strap`, `pull`, `needs` (what the part requires on a pin: a capacitor to ground in a range, a pull in a range, a series resistor, a unique address on its bus, a pin never grounded, a pair joined, a termination count) | a schema per kind: field names with units (`_v`, `_a`, `_ohm`, `_f`), ranges, required fields per domain – `edakit part lint` |
| tables | IEC 60664-1 distances, IPC-2221 widths and spacings, USB and Type-C numbers, EU radio bands | one file each with its source; LIMITS and GEOMETRY read them |
| built-in defaults | what every part of a kind or role requires – decoupling per `power_in`, pull-ups per I2C line, a diode per coil, Rd per CC pin: today G-6, G-11, G-13, G-14 | the same `needs` vocabulary, so a parts entry can refine or override them |

Two consequences for consistency:

- **A contradiction becomes a data conflict, and data conflicts are detectable.** H-1 against USB's 10 µF becomes
  one requirement on a VBUS input with a minimum and a maximum; a range is non-empty or it is not. Two rules on one
  quantity become one limit with two sources, and the lint names the second.
- **A number has one home.** It stands in the entry or the table, once, with its source and tag (r, x, v as in
  maker-coverage). A value tagged x or v does not pass `part lint` for a release.

The data burden is real: more fields per part, each to sign (G-9). Against it: templates per kind that ask only for
the kind's fields, `edakit part import` from the library where it has the value, a library of checked entries for the
parts makers use most (maker-coverage PF), and the second check of the electrical reviewer (M-1) as today.

## 3. Profiles: domains

```toml
# edakit.toml of a project
[project]
domains = ["usb", "radio"]        # core is always on
```

```toml
# edakit/domains/audio.toml – one file per domain, data; domain files live in edakit only (decided)
[domain]
name = "audio"
about = "amplifiers, speakers, line and instrument inputs"
suggested_by = ["speaker", "opamp"]        # kinds in the graph that suggest the domain

[severity]                                  # finding codes the domain switches on, and how hard
CK-8 = "error"                              # bridge-tied outputs
CK-27 = "warning"                           # input impedance against the source
CK-30 = "warning"                           # DC where signals are switched

[facts]                                     # part facts the domain requires; missing ones are "not checked"
opamp = ["ratings.vdd_op_min", "ratings.vdd_op_max", "params.vicm_v", "params.vout_swing_v"]
speaker = ["params.impedance_ohm", "ratings.p_max_w"]

[hints]
apply = ["HT-8", "HT-13", "HT-16", "HT-17"]

[review]
electrical = ["ground loops through USB or mains earth", "RF rectified at inputs on a board with a radio"]

[fixtures]
clean = ["tests/fixtures/pam8403-speaker", "tests/fixtures/tube-screamer"]
```

- **Core** holds what every board needs: STRUCT, SYNC, the LIMITS and LEVELS of the basic kinds, SOURCING, FILES.
- **Purpose** (private, gift, sale) is a dimension of the profile, as P-11, G-24 and G-25 grade by it today.
- **Severity is profile, not code.** A new code starts as a warning in its domain and becomes an error by a change
  of the domain file – after it has run on the reference circuits and on boards without a false alarm.
- **Suggested domains.** A speaker in the graph with `audio` off gives one note: "parts of domain audio present,
  domain not enabled". No silent gap, no forced noise.
- `edakit rules` lists the engines and, per enabled domain, the codes; `edakit hints` only the domain's hints; the
  reviewers get only the domain's questions.

## 4. Testing consistency and correctness

| Test | What it proves | Today |
| --- | --- | --- |
| catalog lint | every code has engine, title, fix; every limit and table has a source tagged r; ranges non-empty; severity files name existing codes | `tests/test_rules.py` checks that every ID has an entry |
| reference circuits per domain pass clean | no false alarm on a known-good design | the example `led-bar`, and the owner's two boards by hand |
| seeded faults | every code is found at least once per domain it applies to – "seen red once", per domain | one negative test per check |
| overlap | every seeded fault produces exactly the declared code or codes | – |
| mutation sweep | generated faults on every fixture – remove each capacitor, cut each pull, reverse each diode, swap two pins of a part, a value × 10, a net joined with its neighbour; the report lists what no code caught, per operator and domain: the catalog's own coverage number | – |
| numbers traced | a limit without a source tagged r does not merge | the catalog's `sources` by hand |

The reference circuits are well-known open designs as edakit graphs in the test fixtures (maker-coverage FT-21): an
ESP32 DevKitC, a WLED controller, a QMK keyboard, a Tube Screamer, a Fuzz Face, a relay board with an HLK-PM01, a LiPo
charger. They also serve the eval with Sonnet (section 5). Decided: they come after the restructuring and after the
integration of maker-coverage's candidates. Until then a new code is tested as today – a seeded fault in `led-bar`, the
run on the owner's projects – and starts as a warning in its domain; the reference circuits and the mutation sweep then
validate the whole catalog at once, and a code that proves wrong there is corrected before it becomes an error.

## 5. The model

- **Findings are the interface.** `edakit check` prints domains, one coverage line ("not checked: 2 parts without
  thresholds – `--coverage`"), the findings grouped by code with a count and the first five, and the summary. Details
  go to a file. No command prints more than a screen by default.
- **Rules by code.** `edakit rules` is about 2 KB (engines and the enabled codes, title only); `edakit explain G-8` or
  `edakit explain <finding>` gives rule, why, fix, source.
- **No rule knowledge in prompts.** Skills say: run, read the findings, fix, explain by code. Reviewer questions come
  from the domain files, not from a growing prose list.
- **One source for the handbook.** The check tables of chapters 3, 5 and 8 are generated from the catalog through
  `edakit docs` blocks – the mechanism G-19 already holds documents to.
- **Short reads.** Skills with one task and short sentences (the plugin's skills average 33 words per sentence today);
  the handbook by section; the graph by query (`edakit graph show U1`) or in the compact form of circuit-language.md,
  not 65 KB whole.
- **Measured.** Typical tasks on the reference circuits – add an LED, swap a part, find a seeded fault, review a board
  – run with Sonnet and with Opus on every change to skills, prompts, catalog and domain files (maker-coverage FT-24).

## 6. What stays

The proposal loop (issue, triage, add-rule), the negative test per code, waivers with a reason on net or component,
accepted warnings in the sign-off file, the hashes and the sign-offs, the stable IDs, the gate's stages. add-rule's
step 5 runs against the reference circuits of the domain as well as against the projects at hand.

## 7. Migration, each step shippable

Order as proposed; the owner has no preference except that the reference circuits come last.

| Step | Content | Size (estimate) |
| --- | --- | --- |
| 1 | the code scheme: `engine` and `code` per entry in `rules.json`, today's IDs as aliases; findings in the format of section 1; `edakit rules` grouped and short; `edakit explain` | small to medium |
| 2 | parts schema per kind; `edakit part lint`; the coverage line ("not checked: …") | medium |
| 3 | `[project] domains`; domain files `core`, `usb`, `radio` in edakit from today's checks; severity from the profile; required facts per domain (needs step 2's field names); suggested domains; hints and reviewer questions filtered | medium |
| 4 | the `needs` vocabulary; REQUIRES with built-in defaults equal to G-6, G-11, G-13, G-14 – no behaviour changes | medium to large |
| 5 | handbook check tables generated from the catalog | small to medium |
| 6 | maker-coverage's candidates enter as data per domain, new codes as warnings – one domain at a time | per domain |
| 7 | reference circuits, seeded-fault suite per domain, overlap test, mutation sweep | large, incremental |
| 8 | eval with Sonnet on the reference circuits; a baseline on `led-bar` and the bell can run earlier | medium |

Steps 1 to 3 change no finding on any board. Step 2 before step 3 because the domain files name the schema's fields.
Step 5 early because it is cheap and stops the handbook's tables from drifting during the restructuring.

## 8. Costs and risks

- **Generic engines, less specific messages** – unless every finding carries field, value, source and fix. The
  format in section 1 is the condition, not an option.
- **More data per part.** Section 2 names the mitigations; the burden does not go away.
- **A configuration layer.** Domains must default right: core on, everything else off, suggestions from the kinds.
- **Migration touches 983 tests.** Grouping instead of renumbering keeps most of them; step 4 rewrites the tests of
  four checks.
- **An engine too generic for an exception** – G-10's rule that a PMOS blocks only with source and gate outside. The
  engines carry small vocabularies, and exceptions are data (pass-through sets, roles), not code per case.
- **Estimates.** The code counts and step sizes are judgement; the mutation sweep's value shows only once it runs.

## Decisions

Taken by the owner on 2026-10-30:

1. **IDs.** Today's IDs stay valid; a new ID scheme and methodology are welcome where they make sense. The scheme of
   section 1 (`ENGINE.relation`, old IDs as permanent aliases, the stage as a property of the finding) is the proposal
   for it – to be confirmed with step 1.
2. **Domains** live in edakit only; a project's own profile is not foreseen. To be re-evaluated if a need arises.
3. **Reference circuits** come after the restructuring and after the integration of maker-coverage's candidates (steps
   7 and 8 of the migration).
4. **Order:** no preference beyond 3; the order of section 7 stands until something speaks against it.

Still open: the relation vocabulary of the codes (step 1), the mutation sweep in CI on every change or on demand (step
7), and which published designs become the reference circuits (step 7).
