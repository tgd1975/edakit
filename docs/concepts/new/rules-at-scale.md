# Rules at scale

Status 2026-10-30: the owner gave the go; built on this branch step by step (section 10, "Build log").

It answers the owner's concern that the rule catalog does not scale – electrically (are the rules consistent, free of
contradiction, correct?) and in use (many rules, most of them irrelevant to a given project, too much context for the
model, which must work with Sonnet). It builds on [maker-coverage.md](maker-coverage.md) (what is missing) and is
compatible with [circuit-language.md](circuit-language.md) (the graph's form). Decided by the owner: no regard for
what exists today – IDs, file formats and keys may change; the owner's projects are converted once. Numbers are
measured at edakit `bf7450a` unless marked as estimates.

## The problem

Today one lesson becomes one check ID: a function, a negative test, a catalog entry, a handbook row, often a reviewer
question. 67 checks and 9 hints came out of two projects. maker-coverage lists about 110 more candidates. Scaled the
same way, three things break.

- **Electrically.** Rules overlap and contradict. H-1 asks for a bulk capacitor at a power input; USB allows 10 µF at
  attach. Each number sits in a rule's prose, where no program can compare it with another rule's.
- **Correctness.** One negative test proves that a rule can fire. It does not prove that the rule never fires wrongly.
- **In use.** `edakit rules` prints 27.5 KB. The handbook repeats every check by hand. Hints and reviewer questions
  grow with every domain and reach every board. A code like G-8 says nothing without a lookup.

## The design

Few engines, much data, a profile per project. Findings as the only interface.

- Everything the checks compare is one of five things: a **quantity** (a voltage, a current, a distance), a **limit**
  on it, a **requirement** a part makes on a pin, the **level** of an input in a state, or a **path** through the
  circuit. About ten **engines** work on these five, and nothing else. An engine knows no MOSFET and no LED.
- What makes a MOSFET a MOSFET is **data**: which quantities its model yields, which limits its entry declares, what it
  requires on its gate. New knowledge is a row of data with a source. A new code only for a new relation.
- A project declares its **domains**. A domain is a profile – data in edakit – that switches codes on, sets their
  severity, names required part facts, hints, reviewer questions and, later, reference circuits.
- **The model sees findings, never rules.** A finding carries code, stage, place, value against limit, source and fix.

## 1. Five things and their producers

| Thing | Produced by | Consumed by |
| --- | --- | --- |
| quantity: `(place, name, value, stage, scenario)` – `C1.v`, `U1.3.i`, `R7.p`, `U2.tj`, `track(+5V).width_mm`, `J1.cc1.v` | the graph's declared ranges (stage G), the simulation (E), the geometry and the Gerber files (L, F) | LIMITS |
| limit: `(kind or part, name, min, max, factor, source)` | parts entries (`ratings`), tables (IEC, IPC, USB, radio bands), the domain | LIMITS |
| requirement: `(pin or role, what, params, source)` – a capacitor to ground within a range, a pull to a rail within a range, a series resistor, a diode across, a unique address on the bus, never grounded, a pair joined, a termination count | parts entries (`needs`), built-in defaults per kind and role | REQUIRES |
| level: `(input, state) → high, low, driven, undefined` – states: reset, firmware not running, each scenario, each rail off | pin types, `strap`, `pull`, thresholds, the simulation | LEVELS |
| path: reachability through pass-through classes – a reversed source, a supply, a hazardous domain, a pin to a connector | the graph with roles | PATHS |

The engines join. LIMITS joins quantities with limits by place and name; it reports where the value is outside. It
does not care whether the value came from a declared range or from ngspice – the finding says which (the stage).
Kinds matter only in the producers (which quantities a MOSFET yields) and in the schema (which limits a MOSFET
declares).

## 2. Engines

| Engine | Decides | Today's checks it replaces |
| --- | --- | --- |
| STRUCT | the graph is well-formed and names what exists | G-1, G-2, P-1, P-6, P-9 |
| SYNC | every artifact equals the graph and the plan | S-2, L-1, L-4, L-7, L-10, L-12, L-20, P-3, P-10, F-1, F-3, F-4, F-5 |
| LIMITS | every quantity within its limit | G-3, G-8, G-17, G-24, G-25, E-2, E-3 (ranges, back-feed), E-5 |
| LEVELS | every input defined in every state, no two drivers fight | G-4, G-5, G-12, E-3 (input levels) |
| REQUIRES | what a part requires on its pins is present and in range | G-6, G-11, G-13, G-14, G-18 |
| PATHS | what a reversed, unfed or hazardous voltage reaches | G-10, G-16, H-8 |
| SIM | the scenarios run and are complete | E-1, E-4 |
| GEO | copper, holes, print, widths and distances on plan and Gerber files | L-2, L-3, L-5, L-8, L-9, L-11, L-13 to L-19, P-7, P-8 |
| FILES | manufacturing files and sheets complete and consistent | P-2, F-6 |
| PARTS | parts entries complete, verified, orderable | G-9, P-4, P-5, P-11, F-2 – and the coverage: a required fact missing |
| DOCS | documents and requirements quote the design | G-19 to G-23 |
| HINT | patterns that need judgement, as notes | H-1 to H-7, H-9 |

Twelve engines; GEO is the largest and may split. Each is a module with its own tests (section 7).

## 3. Codes and findings

**Scheme.** A code is `ENGINE.relation`. It says what kind of finding it is, without a lookup. The vocabulary as
fixed in build step 1 (`edakit/catalog/codes.toml`):

| Engine | Relations |
| --- | --- |
| STRUCT | `name`, `pin`, `net`, `board`, `ref`, `purpose`, `lock`, `domain`, `entry`, `identity`, `prefix` |
| SYNC | `schematic`, `pcb`, `footprint`, `plan`, `bom`, `cpl`, `source`, `scripts`, `agents` |
| LIM | `v`, `i`, `p`, `t`, `range`, `declared`, `backfeed`, `eirp`, `band` |
| LVL | `undefined`, `contention`, `boot`, `threshold`, `direction` |
| REQ | `missing`, `value`, `forbidden`, `function` |
| PATH | `reverse`, `unfed`, `ground` |
| SIM | `config`, `converge`, `state`, `driver`, `copper` |
| GEO | `copper`, `drc`, `width`, `loop`, `mark`, `formed`, `pour`, `spacing`, `ring`, `hole`, `silk` |
| FILES | `sheet`, `manifest`, `set`, `order` |
| PARTS | `verified`, `stock`, `supplier`, `fact`, `schema`, `footprint` |
| DOCS | `quote`, `ref`, `need`, `evidence`, `draft` |
| HINT | `datasheet`, `bulk`, `gate`, `debounce`, `inductive`, `switcher`, `lithium`, `esd`, `two_supplies`, `readback` |

80 codes for today's 66 checks and 9 hints – 82 since step 3 (`STRUCT.domain`, `HINT.datasheet` for the notes of the parts entries) –, more than the estimate of 50: the hints keep a code each, and where one
check of today held two things a person accepts separately (G-1, G-14, G-16), they became two codes. Today's IDs are
retired without aliases (decided); every code lists the IDs it replaces (`replaces`), and `edakit explain G-8` names
them, for reading old protocols.

**Format.** Every finding, in every command and in the protocol:

```text
LIM.v    G  C1: 7.5 V across, rated 6.3 V, needs × 1.5 = 9.5 V     ratings.v_max of C439782 (datasheet p. 2)   → a 16 V part
REQ.missing  G  U2.16 (VDD): no capacitor to ground within 100 nF–10 µF   needs of C90107 (datasheet 9.1)             → 100 nF at the pin
LVL.boot     G  U1.12 (GPIO12): pulled high at reset, must be low           strap of ESP32-WROOM-32 (datasheet 2.4)     → another pin, or no pull
```

Code, stage, place, value against what, source, fix. Grouped by code with a count; the first five per code; the rest
in a file.

**Severity** is set by the profile, not by the code: `error` (blocks `edakit check`), `warning` (the gate wants it
accepted), `note` (information), `pending` (blocks the release and cannot be accepted – an unverified part, a missing
stock snapshot). A new code starts as `warning` in its domain and becomes `error` by a change of the domain file.
A finding may carry a **grade** – a sub-case with its own severity: `margin` (inside the limit but in its margin: a
fuse's trip current above a contact rating, a tight hole), `firmware` (the firmware keeps it: a radio band), the name
of a missing fact (`PARTS.fact/lead`). The catalog gives each code its default severity and those of its grades; a
profile sets `"LIM.i/margin" = "error"` like any code.

**Acceptance** is one mechanism for everything a person has seen and answered: `accept` with a reason, keyed by code
and, where needed, by name – `"accept": {"LIM.v": "7.5 V only in the fault case servo-stalled (D-3)"}`. Errors and
notes are accepted in the graph, on the net or component (circuit scope: part of the circuit hash, renews M-1).
Warnings are accepted in the sign-off file (release scope), as today. `waive`, `hints` and `accepted_warnings` go.

## 4. Data

| Place | Content | Checked by |
| --- | --- | --- |
| parts entry | `ratings` (limits), `params` (values for the models), per pin `type`, `role`, `strap`, `pull`, thresholds, `needs`; every value with its source | a schema per kind: field names carry their unit (`_v`, `_a`, `_w`, `_ohm`, `_f`, `_h`, `_c`, `_hz`, `_dbm`, `_mm`), ranges, required fields per domain – `edakit part lint` |
| tables | IEC 60664-1 distances, IPC-2221 widths and spacings, USB and Type-C numbers, EU radio bands, derating | one file each with its source and tag |
| defaults | what every part of a kind or role requires: decoupling per `power_in`, pull-ups per I2C line, a diode per coil, Rd per CC pin, a bulk capacitor at a power input | the same `needs` vocabulary; an entry refines or overrides a default |
| the graph | parts, nets, `accept`, `layout`, `purpose`; settings that are facts move to pins and parts (`reverse_protect` becomes a role of the connector pin) | STRUCT |

Consequences:

- **A contradiction becomes a data conflict, and data conflicts are detectable.** H-1 against USB's 10 µF becomes one
  requirement on a VBUS input with a minimum and a maximum; the lint rejects an empty range (`REQ.conflict`). Two
  limits on one quantity with different values from two sources: the lint names both.
- **A number has one home**, with its source and tag – r (read), x (extract), v (to verify). A value tagged x or v
  blocks the release of the part's project (`PARTS.verified`) until read.
- **The data burden is real.** Mitigations: templates per kind ask only for the kind's fields; `edakit part import`
  takes what the library has; a library of checked entries for the parts makers use most (maker-coverage PF); the
  second check of the electrical reviewer (M-1), as today.

## 5. Domains

```toml
# edakit.toml of a project
[project]
domains = ["usb", "radio"]        # core is always on
```

```toml
# edakit/domains/audio.toml – domain files live in edakit only (decided)
[domain]
name = "audio"
about = "amplifiers, speakers, line and instrument inputs"
suggested_by = ["speaker", "opamp"]          # kinds in the graph that suggest the domain

[severity]
"REQ.forbidden" = "error"                    # a bridge-tied output grounded
"LIM.range" = "warning"
"LVL.undefined" = "warning"                  # an analog input without a DC path

[facts]                                      # required per kind; a missing one is PARTS.fact: "not checked"
opamp = ["ratings.vdd_op_min_v", "ratings.vdd_op_max_v", "params.vicm_v", "params.vout_swing_v"]
speaker = ["params.impedance_ohm", "ratings.p_max_w"]

[hints]
apply = ["HINT.ground_loop", "HINT.class_d_leads", "HINT.audio_band_switching"]

[review]
electrical = ["ground loops through USB or mains earth", "RF rectified at inputs on a board with a radio"]

[fixtures]                                   # reference circuits, after the integration (decided)
clean = []
```

- **Core** holds what every board needs: STRUCT, SYNC, LIMITS and LEVELS of the basic kinds, PARTS, FILES, DOCS.
- **Purpose** (private, gift, sale) is a dimension of the profile, as P-11, G-24 and G-25 grade by it today.
- **Suggested domains.** A speaker in the graph with `audio` off gives one note. No silent gap, no forced noise.
- `edakit rules` lists the engines and the enabled codes with their titles; `edakit hints` is gone – hints are
  findings; the reviewers get the enabled domains' questions.

## 6. One catalog

The catalog is the single source: codes (engine, relation, title, why, fix), domain files, tables, schemas. Generated
from it, never written by hand: the explanations below `edakit check`, `edakit explain <code>`, the handbook's check
tables (today chapters 3.3, 5.3, 8.1) and its field reference (today 4.1), the reviewers' question lists, the
protocol's section "The rules behind the findings". The G-19 mechanism, which holds documents to the design data,
holds the handbook to the catalog.

## 7. Tests

| Test | Proves |
| --- | --- |
| engine tests | each engine on small synthetic inputs: every relation fires on its fault and on nothing else; property tests on LIMITS (a value inside its limit never fires, at random values and limits) and PATHS (a pass-through set never leaks) |
| seeded faults | every code is seen red once on `led-bar`, as today – per domain once the domain has a fixture |
| clean fixtures | `led-bar` and the bell pass clean under their domains; the owner's reference project by hand |
| parity | during the rebuild, old and new run on `led-bar` and the bell and yield the same findings under the map old ID → code; the old code is deleted when parity holds |
| catalog lint | every code has engine, title, fix; every limit, default and table row a source tagged r; every range non-empty; every domain file names existing codes and schema fields |
| overlap | every seeded fault produces exactly the declared code or codes |
| later | reference circuits per domain, a seeded-fault suite per domain, a mutation sweep that reports what no code catches (maker-coverage FT-21) – after the integration of the candidates (decided) |

## 8. The model

- Findings are the interface. `edakit check` prints the enabled domains, one coverage line ("not checked: 2 parts
  without thresholds – `--coverage`"), the findings grouped by code, the summary. No command prints more than a screen
  by default.
- Codes explain themselves; `edakit explain` gives rule, why, fix and source for one code, about 1 KB.
- No rule knowledge in prompts. Skills say: run, read the findings, fix, explain by code. Reviewer questions come from
  the domain files.
- Short reads: skills with one task and short sentences (today 33 words per sentence on average); the handbook by
  section; the graph by query (`edakit graph show U1`) or in the compact form of circuit-language.md.
- Measured: typical tasks run with Sonnet and with Opus on every change to skills, prompts, catalog and domain files –
  a baseline on `led-bar` and the bell first, the full suite on the reference circuits later (maker-coverage FT-24).

## 9. The proposal loop

Stays: an issue sealed by `edakit proposal`, the triage, one pull request. The kinds change with the design: `fact` (a
row of data – a part fact, a default, a table row), `relation` (a new code), `domain` (a profile change: severity, a
required fact, a question), `block`, `retire`. Most of maker-coverage's candidates are facts and domain changes; the
triage's question "decidable by a program?" becomes "which engine, which data?".

## 10. Build plan

Not a migration: a rebuild beside the old code, switched over on parity, the old deleted. Each step shippable.

| Step | Content | Size (estimate) |
| --- | --- | --- |
| 1 | the data model: catalog format, code scheme and vocabulary, finding format, severities and `accept`; parts schema per kind with unit suffixes; `edakit part lint`; tables as files; `edakit rules` and `edakit explain` | medium |
| 2 | LIMITS, LEVELS, REQUIRES, PATHS, STRUCT, SIM, HINT as modules beside `checks.py` and `sim/run.py`; the producers of quantities; parity test on `led-bar` and the bell | large |
| 3 | domain files `core`, `usb`, `radio`; `[project] domains`; severity from the profile; suggested domains; reviewers read the domain files | medium |
| 4 | SYNC, GEO, FILES, PARTS, DOCS regrouped – mostly naming and the finding format | medium |
| 5 | switch-over: the old checks deleted, the owner's projects converted once (graph keys, parts fields, waivers), handbook tables and field reference generated, chapter 14 rewritten | medium |
| 6 | maker-coverage's candidates enter as data per domain, new codes as warnings – one domain at a time; first the producers many domains need (load steps FT-1, cables FT-2, the op-amp model FT-3), then the domains in maker-coverage's order | per domain |
| 7 | reference circuits, seeded-fault suite per domain, overlap test, mutation sweep | large, incremental |
| 8 | eval with Sonnet on the reference circuits | medium |

Steps 1 to 4 change no finding on any board; the parity test says so. Step 5 is the cut.

### Build log

| Step | State | What exists |
| --- | --- | --- |
| 1 | built | `edakit/catalog/`: `codes.toml` (80 codes, 12 engines, each with the IDs it replaces), `kinds.toml` (the parts schema per kind), `tables/` (EU radio bands, USB, I2C, derating, JLCPCB, IPC-2221 – each row with source and tag); `edakit/findings.py` (finding, profile, severity, grade, accept, the grouped format); `edakit/convert.py` (old → new in memory, `edakit convert`); `edakit part lint`, `edakit rules`, `edakit explain`; `tests/test_catalog.py`. No finding of `edakit check` changed. |
| 2 | built | `edakit/engines/`: STRUCT, LIMITS (with the producers of stage G in `quantities.py`), LEVELS, REQUIRES, PATHS, HINT, SIM (the simulation as a producer, beside `sim/run.py` on the same ngspice result); their data `catalog/levels.toml`, `needs.toml`, `paths.toml`; the pure graph helpers moved from `checks.py` to `circuit.py` and `radio.py`, the hint matchers to `engines/hint.py`. Parity (`tests/parity.py`, run on every check of the test suite): per check ID of before and severity the same number of findings – 180 graph runs with 1141 findings and 171 simulation runs with 458 failures in the seeded faults of `led-bar`, and the bell, agree. `tests/test_engines.py`: every relation on synthetic circuits, property tests of LIMITS and PATHS. |
| 3 | built | `edakit/domains/`: `core` (always on: severities by purpose, the facts every module and microcontroller states – `compliance.radio`, today's P-11 –, the nine hints, the reviewers' questions), `usb` (the CC termination, `REQ.*:cc`), `radio` (`LIM.eirp`, `LIM.band`, purpose.radio; graded by purpose); `edakit/profile.py`: the profile from `[project] domains` – without the key every domain the graph suggests, so no project of today changes; with it a suggested domain left out is a note `STRUCT.domain`; severities of several domains: the strictest wins; `code:topic` switches part of a code (`REQ.missing:cc`). `edakit domains [--review R]`; the electrical and regulatory reviewers read their questions from it, the lists left their prompts. The engine PARTS checks the facts the profile requires. Parity holds, P-11 included. |
| 4 | built | `edakit/engines/project.py`: the checks beyond the graph – own parts and footprint copies (SYNC), holes and formed leads (GEO), stock, supplier, footprint data, sign-off (PARTS), the requirements file (DOCS), scripts and agents (SYNC) – report through a recorder that gives each report its code and grade (`MAP`, a few by their words: a missing lead is `PARTS.fact/lead`); the gate's rows of stages S, L and F get their codes by the same table (`row_code`). `engines.run_all` is what `edakit check` will print. Parity now over every check of `edakit check`. One deviation, on purpose: a part that is neither an LCSC part nor an EasyEDA device was pending and could be waived; pending cannot be accepted (section 3), so it is `PARTS.verified/device`, a warning to accept. |
| 5 | built | The cut. Deleted: `rules.json`, `rules.py`, the parity test; `checks.py` from 1208 to 250 lines (what is left reads the footprint geometry: GEO.hole, GEO.formed, the sign-off of parts), `sim/run.py` from 1082 to 501 (the transient runs; the DC evaluation is `engines/sim.py`). `edakit check`, the gate and `edakit sim` print findings by code; `edakit hints` is gone. Data in the new form: `led-bar`, the blocks and their parts, and the bell's four projects by `edakit convert --write` – same findings under the map old ID → code; the Nano's `i_gpio_max_a`, which no code read, is `gpio_i_max_a` now (150 more simulation rows, passed). `convert` keeps each file's indent and, where the files were the signed ones, carries the circuit sign-offs over (`rehashed`, as for `hash_ignore`). Generated: the handbook's lists of codes (3.3, 5.3, 8.1, 14.3), the parts schema (4.1) and the map of before (10.7) by `python -m edakit.catalog.handbook --write`, held by a test – a test, not DOCS.quote, since the handbook is no project document. Chapter 14 rewritten; handbook, skills, agents and blocks name codes. Proposal kinds `fact`, `relation`, `domain`, `block`, `retire` (`check`, `hint`, `part` of before still verify); `[retired]` in `codes.toml` keeps a retired name taken. The concept documents keep the IDs of their time. |
| 6 | built, in part | Without network access to datasheets (the hosts were blocked), what needs no new number: the producers – load steps in transient runs (FT-1), cables with length and gauge (FT-2; no current rating from the gauge), the op-amp model (FT-3) –; what went unchecked for lack of data (FT-19, `edakit check --coverage`); new relations as grades that start as warnings: what a pin needs from its entry (CK-13, CK-14), IC inputs in nc (CK-1), open-drain lines (CK-2), bus addresses (CK-3), MOSFETs half on (CK-4, from the AO3401A's existing RDS(on) table), inputs above their supply (CK-5), ADC windows (CK-6), polarized capacitors (CK-7), bridge-tied outputs (CK-8), USB-C data (CK-12), windings (CK-15), lines on a cable (CK-16), cell current (CK-18), a key matrix (CK-19), a driver's supply pin (CK-21), the clock against the supply (CK-23), analog nodes without a DC path (CK-25), UART lines (CK-26), instrument loading (CK-27), stable gain (CK-28), series capacitors (CK-29); fn for I2S, CAN, 1-Wire, USB (FT-15); a load's expect (FT-11); the kinds motor, solenoid, speaker, heater, optocoupler (FT-6); the domains audio, guitar, motors, power, cables and the hints HT-1, 4, 6, 8–13, 15–19. Then, still without data: `edakit graph show` (FT-23); the hints HINT.jack_supply (HT-7, jack roles tip, ring, sleeve and their switches) and HINT.relay_load (HT-14); REQ.value/switch – no DC across a switch, relay contact or pot between nets marked `signal` (CK-30, without the contacts' minimum load); `layout.apart` measured on the Gerber copper as GEO.spacing/apart (CK-31); `antenna.keepout_mm` of an entry held to the board's copper as the new code GEO.keepout, radios without it in the coverage report (CK-11, without the board edge); connectors marked `off_board` for REQ.missing/leave (CK-16); analog inputs (channel, divider, pull) and the I2C devices with their addresses in the firmware contract (FT-10, FT-16 without SPI mode and bus speed); sim.json `fault_scenarios` – a reversed source, a cable wire shorted, one source off, the parts' limits as warnings (FT-8, and CK-5 with one supply off); the pcb reviewer's questions on antenna areas and exposed pads. Not built: mains (the ES1 limit of IEC 62368-1 is tagged to verify, open decision 3), CK-9, 10, 17, 20, 22, 24, FT-4, 5, 7, 9, 12–14, 17, 18, HT-2, 3, 5, the blocks and the library of part facts – they need datasheets read. |
| 7 | built | `tests/reference.py`: a reference circuit per domain added to `led-bar`, clean under its domains, with seeded faults that raise exactly their codes (`tests/test_reference.py`); edakit's own circuits, values chosen for the test – the published open designs of FT-21 join them once their schematics can be read. `edakit mutate` lists what no code catches (led-bar: 24 of 45 mistakes caught without the simulation, 43 with it; R-EXT ×100 stays unseen). The reference circuits found three faults in edakit: a pull to a divider's middle counted as none (LVL.undefined), a floating sub-net let ngspice fall back to a wrong operating point (rshunt), a net without pins crashed the simulation. |
| 8 | built | `evals/`: six cases for `claude plugin eval` on the reference circuits – find a seeded fault (four), name what went unchecked, add an LED. Baseline 2026-10-31, one run per case: Sonnet 5.5 five of six, Opus 5.5 six of six (`evals/README.md`); the runs led to four fixes in edakit (uv cache, sim artifacts, the path in the hook, the flyback wording). |

State of the candidates after step 8 and the candidates without data (`maker-coverage-status.toml`, one entry per
candidate): of 92 numbered candidates 46 built, 10 in part, 36 open – features 12/3/9, checks 18/7/6, hints 16/0/3,
blocks 0/0/18 –, the library of 49 parts and 1 of 5 reviewer topics open. What is open needs datasheets or standards this environment could not reach, or waits
for open decisions 3 (mains), 4 (parts library) and 5 (AC analysis).

The catalog as one page – every code with rule, why, fix and sources, the domains, the tables, the parts schema, the
reference circuits drawn and their seeded faults, the candidates' state: `docs/catalog/index.html` and
`docs/catalog/circuits/*.svg`, written by `docs/catalog/build.py`; `tests/test_catalog_page.py` fails while they differ
from the catalog.

Merged with main on 2026-10-31, before the merge into main (the owner's decision): main had brought the KiCad tool chain
and ordering at the maker meanwhile, its new checks written as check IDs. They became codes: P-12 → `PARTS.fact/mpn`;
F-6, now per maker → `FILES.order`; F-7 → `SYNC.odb` (the ODB++ against the released files, beside SYNC.bom and
SYNC.cpl); B-1 to B-7 → a 13th engine `ORDER` (`ORDER.form`, `.parts`, `.quote`, `.read`, `.files`, `.finish`,
`.review` – the order at the maker against the release). A finding for a maker of `[cart] makers` that is not the
planned one is a warning of grade `other_maker`; `ORDER.finish` is graded by purpose in the domain core.

### When maker-coverage's candidates are built

After the cut (step 5), not before – decided by the owner. Three reasons:

1. **Most candidates are data in the new model, not code.** Of maker-coverage's 31 check candidates about 12–15
   become new relations (estimate); the rest are facts, defaults and domain profiles, which do not exist in today's
   model. Built as checks of today they would be written twice: once as a function with its catalog entry, negative
   test and handbook row, and after the cut again as data.
2. **They would move the parity target.** The rebuild runs beside the old code and must yield the same findings on
   `led-bar` and the bell. Every new check during the rebuild moves what the new engines must match.
3. **Without domains they would reach every board.** Audio or guitar rules without a profile bring exactly the noise
   this concept is meant to avoid.

**The exception: the producers.** FT-1 (load steps in transients), FT-2 (cables with length and gauge) and FT-3 (the
op-amp model) are no rules but producers of quantities. They can be built as soon as step 2's engines exist, since they
feed the new LIMITS and LEVELS and touch nothing old. In step 6 they come first, because many domains depend on them.

**A fault of today.** A check of today that fails a project before the cut – a false alarm or a missed fault – is fixed
where it is, with its test, and carried over to its engine.

## 11. Costs and risks

- **Generic engines, less specific messages** – unless every finding carries value, limit, source and fix. The format
  of section 3 is the condition, not an option; the engine tests assert it.
- **More data per part** (section 4). The burden does not go away; the templates and the library reduce it.
- **A configuration layer.** Core on, everything else off, suggestions from the kinds. Wrong defaults make silent
  gaps or noise; the suggestion note is the guard.
- **A rebuild of 23,900 lines' core.** The parity test and the per-engine tests are the safety net; 983 tests today,
  most of them rewritten against engines.
- **An engine too generic for an exception** – G-10's rule that a PMOS blocks only with source and gate outside. The
  engines carry small vocabularies; exceptions are data (pass-through classes, roles), not code per case.
- **Estimates.** Code counts and step sizes are judgement; the mutation sweep's value shows only once it runs.

## Decisions

Taken by the owner on 2026-10-30:

1. **IDs:** a new scheme and methodology – `ENGINE.relation` (section 3); no aliases, no regard for existing
   protocols and waivers; the owner's projects are converted once.
2. **Domains** live in edakit only. To be re-evaluated if a need arises.
3. **Reference circuits** come after the restructuring and after the integration of maker-coverage's candidates.
4. **Order:** no preference beyond 3; the plan of section 10 stands until something speaks against it.
5. **Branch:** built on this branch (`ccr-f80e23dc-ak6668`), after an explicit go.
6. **maker-coverage's candidates** are built after the cut (step 5); the producers FT-1, FT-2 and FT-3 may start
   with step 2. Section 10, "When maker-coverage's candidates are built".

Settled in step 1 (2026-10-30), after the go, as proposed: the relation vocabulary of section 3; `ratings` and
`params` become `limits` and `values`, every name with its unit (`vrrm` → `vr_max_v`, a pin's `vmax` → `v_max_v`) –
`edakit/convert.py` holds the table, `edakit convert --write` converts a project once at the cut. Still open: the
mutation sweep in CI or on demand (step 7; proposed: on demand).

Taken by the owner on 2026-10-31 – maker-coverage's open decisions 3 to 5, through a form, each as proposed:

7. **Mains and hazardous voltage** (maker-coverage decision 3): edakit recognises them and does not check them. A
   domain `mains` finds a net above the ES1 limit of IEC 62368-1 – the value read from a source, not from memory – and
   says that edakit checks neither spacing nor isolation there (CK-22); an **error** that a project may accept with
   its reason in the sign-off file ("power supply bought, only safety extra-low voltage on the board"). No creepage or
   clearance is measured: edakit makes no safety statement others could rely on. FT-7, CK-9, CK-10 and CK-24 stay out.
   Built the same day: `LIM.hazardous` is core's, always on – a project that names its domains cannot leave it out –
   and the domain `mains` is suggested by such a net and carries the reviewers' questions. The DC limit (60 V) is read
   from TI's seminar paper SLUP421; the AC limit is not read yet, so an AC net is judged by its peak against the DC
   limit.
8. **Library of checked parts entries** (decision 4): in edakit, `edakit/parts/` – the entries `edakit/blocks/parts/`
   holds today move there, the blocks use the same ones. A project takes an entry over with `edakit part add <part>`
   as a **copy** into its parts folder, which names the library entry and its version; `edakit check` notes when the
   library holds a newer version, and the project takes it over on purpose. An entry is written from its datasheet
   (source with revision) and counts only once the **owner** has signed it (`verified`); until then it is a draft.
9. **AC analysis** (decision 5): opt-in – ngspice `.ac` (and `.noise`) only where `sim.json` names an expectation
   (gain at a frequency, the −3 dB corners), in the domains audio and guitar; without an expectation nothing runs. Its
   codes start as **warnings**, like every new code of step 6. FT-18 (source models in the audio band) builds on it.
   Built the same day: `ac` in sim.json (sim/ac.py) – the input net driven with 1 V AC through 1 F behind a source
   resistance or a source model (R and L in series, C across), the gain and the −3 dB corners against `expect`,
   SIM.response (grades gain, corner) switched on by audio and guitar, SIM.config/off where neither is on; the audio
   and guitar reference circuits expect their RC corners and fail with the capacitor a decade off.

Taken by the owner on 2026-10-31, through a form, after the library and the blocks:

10. **Schema extension** (docs/concepts/new/schema-gaps.md): all of it that the form offered – the wrong judgements
    (A, I1, I7), the limits, currents and needs (B, C, D), the supply currents of the library drafts (E1), and the
    models and modes (E2–E6, F, I2–I6). Built in parallel worktrees, merged on this branch.
11. **EasyEDA symbols that differ from their datasheets:** checked and reported – STRUCT.entry compares the cached symbol
    with the entry beyond the names, and `upstream/` holds the report the owner sends to LCSC/EasyEDA.
12. **Merge into main** after the schema extension, not before.

