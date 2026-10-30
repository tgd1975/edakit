# Rules at scale

Status 2026-10-30: final for the owner's decision; built on this branch only after an explicit go. Nothing is built.

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

**Scheme.** A code is `ENGINE.relation`. It says what kind of finding it is, without a lookup. Draft vocabulary,
fixed in build step 1:

| Engine | Relations |
| --- | --- |
| STRUCT | `pin`, `net`, `name`, `ref`, `identity`, `purpose` |
| SYNC | `schematic`, `pcb`, `footprint`, `plan`, `files`, `source` |
| LIM | `v`, `i`, `p`, `t`, `band`, `range` (a supply outside its operating range) |
| LVL | `undefined`, `boot`, `contention`, `threshold`, `direction` |
| REQ | `missing`, `value`, `conflict`, `forbidden`, `address` |
| PATH | `reverse`, `unfed`, `backfeed`, `exposed`, `hazard`, `isolation` |
| SIM | `config`, `converge`, `state` |
| GEO | `copper`, `spacing`, `width`, `ring`, `hole`, `loop`, `silk`, `drc` |
| FILES | `set`, `order`, `sheet`, `manifest` |
| PARTS | `verified`, `fact`, `stock`, `supplier`, `source` |
| DOCS | `quote`, `ref`, `evidence`, `draft` |
| HINT | `bulk`, `gate`, `debounce`, `inductive`, `hot_loop`, `lithium`, `esd`, `readback`, … |

About 50 codes for today's 76 checks and hints and maker-coverage's candidates together (estimate). Today's IDs are
retired without aliases (decided). A table old ID → new code goes into the handbook once, for reading old protocols.

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
| 6 | maker-coverage's candidates enter as data per domain, new codes as warnings – one domain at a time | per domain |
| 7 | reference circuits, seeded-fault suite per domain, overlap test, mutation sweep | large, incremental |
| 8 | eval with Sonnet on the reference circuits | medium |

Steps 1 to 4 change no finding on any board; the parity test says so. Step 5 is the cut.

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

Still open, to settle in step 1: the exact relation vocabulary; whether `ratings` and `params` keep their names or
become `limits` and `values`; the mutation sweep in CI or on demand (step 7).
