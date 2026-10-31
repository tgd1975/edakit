# 14 Designing a circuit: rules, hints and building blocks

Chapters 3 to 8 check a circuit. This chapter is about the step before: getting from "five LEDs, a servo, USB power"
to a graph – and about the knowledge the checks are made of.

## 14.1 Roles

| Role | Who | Does |
|---|---|---|
| project surveyor | the agent `project-surveyor` in its own context, for the skill `new-project` | for a project that moves to edakit: reads the repository – hardware data, scripts, agents, skills, documents, decisions, hooks – and returns per place candidates with where it found them, a proposal and its reason; changes nothing – the skill asks the user in its interview and writes after the OK (2.7) |
| requirements engineer | a session with the skill `requirements`, and the agent `requirements-engineer` in its own context | the skill collects with the user what the circuit must do, asks back in a decision round until vague words are numbers, writes drafts into the requirements file and has the user approve them – never the graph; the agent reads every document of the project, changes nothing, and returns candidates with their source, contradictions, vague words and requirements without evidence: the first inventory and a second opinion (3.6) |
| circuit designer | a session with the skills `circuit-design` and `hardware-change` | reads the requirements file – without one, asks for the requirements in one decision round –, picks blocks and parts, computes values, writes the graph with its check settings and the schematic file, works through `edakit check` and `edakit sim`, draws the schematic, writes the hand-over |
| part selector | agent `part-selector`, its own context | finds parts for the circuit designer at the project's distributors (one profile each), compares stock, price, lifecycle and compliance data, recommends one and writes its parts entry; never touches the graph (chapter 4.2) |
| electrical reviewer | agent `electrical-reviewer`, its own session | reads graph, hand-over, parts, simulation and datasheets, changes nothing, returns numbered findings with probability and cost – before the first layout, before every hand-over that changes parts or the power path, and as the sign-off M-1 |
| regulatory reviewer | agent `regulatory-reviewer`, its own session | checks circuit and parts against EU law for the purpose in the graph (RoHS, REACH, radio, batteries, product safety), changes nothing, returns numbered findings with their sources – its result is the sign-off M-6 (chapter 15), support and not legal advice |
| PCB designer | a session of its own with the skill `pcb-round` | works from the hand-over: EasyEDA schematic, PCB, and in its board file `hardware/boards/<name>.toml` placement plan, routing, silkscreen; does not change the graph |
| EasyEDA operator | agent `easyeda-operator` | runs one long EasyEDA step for the PCB designer and returns only the result |
| PCB reviewer | agent `pcb-reviewer`, its own session | reads plan, hand-over, routing and the copper of every layer from the Gerber files, changes nothing, returns numbered findings with probability and cost – at the end of every layout round that changed placement, routing or pours, and on the gate run's files as the sign-off M-5 |
| project reviewer | an agent of the project (`[agents.<name>]` in edakit.toml, 8.6), its own session | reviews with the project's own knowledge and changes nothing: in place of the edakit reviewer it replaces (`replaces`) – the reference project's pcb-pruefer reviews the rounds and signs M-5 –, or for a sign-off of its own (M-7) at its hook point; its sign-off counts only signed by it |
| decider | the user | answers the decision rounds: warnings, requirements, looks and operation, money, what becomes a check |

No role checks its own work: a second opinion from the session that made the decisions repeats the decisions; the
reviewer starts without them. With a requirements file each reviewer also judges the requirements whose `verify` names
its sign-off and names the ones it found met in the note it signs with (8.7).

**The hand-over.** Circuit and layout are separate sessions, so what the layout must know is written down – the
PCB designer gets nothing else. It is `layout` in the graph: parts that are fixed (pressed, looked at), at the edge
(plugged in from outside), next to another part (a current-setting resistor at its pin), the hot loops of switching
regulators, and notes no program checks. The decoupling capacitor of every IC is derived from the graph.
`edakit handover` shows all of it together with the circuit's state and sign-offs, and SYNC.plan holds the plan to it
(7.4). Because it is part of the graph, the hand-over is reviewed and signed with the circuit (M-1). A circuit change
the layout needs – another GPIO, another footprint – goes back as a written request in the decision log; the PCB
designer does not change the graph. A project without a PCB ends at the hand-over: the drawing is the schematic.

**Files.** Each role writes its own (10.1): the requirements engineer the requirements file, the circuit designer the
graph, the simulation config and the schematic file, the part selector the parts database, the PCB designer the board
files. A file has one owner, and its hash says which sign-offs a change voids – a new placement voids the layout
review, not the circuit's.

## 14.2 The catalog: engines, codes, data and domains

What edakit knows about circuits is data in one catalog; the code reads it. Five things carry it:

| Thing | Where | Holds |
|---|---|---|
| engines and codes | `edakit/catalog/codes.toml` | twelve engines, each deciding one kind of relation, and their codes: title, rule, why, what to do, severity and grades, sources, the check IDs of before it replaces |
| parts schema | `edakit/catalog/kinds.toml` | per kind the limits and values an entry may give, every name with its unit (4.1); `edakit part lint` holds the entries to it |
| defaults | `edakit/catalog/needs.toml`, `levels.toml`, `paths.toml` | what a pin or part of a kind requires unless its entry says otherwise (decoupling per `power_in`, a pull-up per I2C line, a diode per coil, Rd per CC pin), the levels at reset, the parts a supply passes through |
| tables | `edakit/catalog/tables/` | the numbers with their source: EU radio bands, USB, I2C, derating, JLCPCB's capabilities, IPC-2221, the audio band's source models (pickups, piezo discs, electret capsules as their makers state them) |
| domains | `edakit/domains/` | which codes are on and how severe, the facts a kind must give, the hints, the reviewers' questions |

**Engines.** Each decides one kind of relation, on the graph, the parts, the simulation, the plan or the files:

| Engine | Decides |
|---|---|
| STRUCT | the graph is well-formed and names what exists |
| SYNC | every artifact equals the graph and the plan |
| LIM | every quantity within its limit |
| LVL | every input defined in every state, no two drivers fight |
| REQ | what a part requires on its pins is present and in range |
| PATH | what a reversed, unfed or misplaced supply reaches |
| SIM | the scenarios run, are complete and reach the states they expect |
| GEO | copper, holes, print, widths and distances on plan and Gerber files |
| FILES | manufacturing files and sheets complete and consistent |
| PARTS | parts entries complete, well-formed, verified, orderable |
| DOCS | documents and requirements quote the design |
| HINT | patterns that need judgement, as notes |

LIM does not compute anything itself. Producers give it quantities – the declared ranges of the graph times a
derating factor in stage G, the simulated values in stage E – and it compares each with the limit of that name in the
parts entry (`v_max_v`, `i_max_a`, `p_max_w`, `tj_max_c`), derated where the table says so. A new limit in a parts
entry is checked without new code.

**Codes.** A finding's code is `ENGINE.relation`: `LIM.v` a voltage beyond its limit, `REQ.missing` a part without
what it requires, `LVL.boot` a strapping pin at the wrong level. The code says what kind of finding it is without a
lookup. A finding carries code, stage, place, text, source and fix, and where it applies a grade and a topic:

- **severity** – `error` (blocks `edakit check`), `warning` (the gate wants it accepted in the sign-off file),
  `pending` (blocks the release, cannot be accepted: an unverified part, a missing stock snapshot), `note`. The
  catalog gives each code its default; the profile of the project may set another.
- **grade** – a sub-case with its own severity: `margin` (inside the limit, in its margin), `unknown` (a value
  missing), `stale`, `unchecked`, `draft`, `firmware` (the firmware keeps it), or a missing fact (`PARTS.fact/lead`).
  A profile sets `"LIM.i/margin" = "error"` like any code.
- **topic** – the part of a code one domain switches on or one acceptance names: `REQ.missing:cc` (USB-C
  termination), `GEO.spacing:paste`, `SYNC.plan:handover`.

```bash
edakit rules                 # the engines and their codes, one line each
edakit explain REQ.missing   # rule, why, what to do, severity, sources
edakit explain G-8           # a check ID of before: the codes that replace it (10.7)
```

The catalog explains the findings: `edakit check` prints what to do for every code that failed below the findings, the
gate protocol ends with "The rules behind the findings", and the handbook's lists of codes (3.3, 5.3, 8.1) and the
parts schema (4.1) are generated from it – `python -m edakit.catalog.handbook --write`, and a test fails while they
differ. Tests make sure that every code the engines can report has an entry and that the catalog passes its lint: every
code with engine, title, rule, why and fix, every table row with its source.

**Accepting.** One mechanism for everything a person has seen and answered: `accept` with a reason, keyed by the
code – `"accept": {"LVL.undefined": "floating until the firmware runs, harmless: OE is pulled high"}` on the net or the
component, `{"HINT.bulk": "C1 1000 µF next to J1 (D-8)"}` on the graph, a code and a place (`"HINT.bulk J2"`) for one
place only. A key may name a grade or a topic: `LIM.i/margin`, `GEO.spacing:paste`. In the graph it is part of the
circuit hash and renews M-1. Warnings for the release are accepted in the sign-off file under `accept` (8.2).
Pending findings cannot be accepted.

**Domains.** A profile of rules per area of electronics. `core` is always on: structure, artifacts, limits and levels
of the basic kinds, parts, files, documents. `usb` switches on the USB-C termination and its data in both orientations, `radio` the e.i.r.p.
and the bands of parts that transmit, `audio` bridge-tied outputs and the hints of hum and switching noise, `guitar`
the instrument input's load and the pedal's supply, `motors` the hints of motor supplies and heaters, `power` those of
cells, converters and polarity, `cables` the lines on a lead. Each is suggested by what the graph has: a USB-C
receptacle, a part that transmits, a speaker, an instrument net, a motor, a battery holder, a cable; `mains` by a
net above the ES1 limits, which LIM.hazardous recognises – spacing and isolation stay unchecked (rules-at-scale.md,
decision 7). The interview of a new project asks for no domain: there is no graph yet, and the graph decides
(skill new-project). A domain file sets severities (also per purpose: `[severity.sale]`), switches codes or
topics on, names the facts a kind must give (a missing one is `PARTS.fact`), the hints that apply and the questions
the reviewers ask. A project names its domains in edakit.toml:

```toml
[project]
domains = ["usb"]        # core is always on; without the key every domain the graph suggests is on
```

A part in the graph suggests the domain it needs – a USB-C receptacle `usb`, a part that transmits `radio`. Left out of
an explicit list, it gives one note, `STRUCT.domain`: no silent gap. `edakit domains` shows the domains on, off and
suggested, and the reviewers' questions of the domains on. Domain files live in edakit only.

**Purpose.** `purpose.use` of the graph (private, gift, sale) is a dimension of the profile: what the firmware or a
parts entry can settle – a radio band, a radio nobody stated – is a warning for a board that is sold and a note
otherwise (8.1, chapter 15).

N and R are no engines: N-… and R-… are the needs and requirements of a project's requirements file (3.6), and a
protocol names both. The codes on that file are DOCS.ref, DOCS.need, DOCS.evidence and DOCS.draft.

**Findings come only from code.** A code is reported by an engine with a negative test; Claude does not invent checks
at runtime. What Claude knows beyond the catalog goes into a review as a finding with its evidence, or into a proposal
(14.4) – not into a finding that looks like a code.

## 14.3 Hints

Some knowledge has no rule a program could decide: whether a hot-plugged cable needs an electrolytic, whether a button
needs a hardware debounce, whether a connector is touched by people. These are **hints**, the engine HINT: matched by
the kinds of parts in the graph or by a pattern, shown by `edakit check` as notes, never blocking. Generated from the
catalog:

<!-- edakit:generated codes HINT -->
**`HINT.datasheet`** – notes of the parts entries (note)  
A parts entry's own warnings – hints of the part, hint of a connected pin (an ESP32 pin of ADC2: no analog reads while Wi-Fi is on) – are shown for every part and pin of the graph they belong to.

**`HINT.bulk`** – bulk capacitor at the power input (note; replaces H-1)  
Bulk capacitor at the power input: consider it where it applies.

**`HINT.gate`** – MOSFET gate resistor (note; replaces H-2)  
MOSFET gate resistor: consider it where it applies.

**`HINT.debounce`** – debounce buttons and switches (note; replaces H-3)  
Debounce buttons and switches: consider it where it applies.

**`HINT.inductive`** – inductive load off the board (note; replaces H-4)  
Inductive load off the board: consider it where it applies.

**`HINT.switcher`** – switching regulator layout (note; replaces H-5)  
Switching regulator layout: consider it where it applies.

**`HINT.lithium`** – lithium cells need protection (note; replaces H-6)  
Lithium cells need protection: consider it where it applies.

**`HINT.esd`** – ESD at external connectors (note; replaces H-7)  
ESD at external connectors: consider it where it applies.

**`HINT.two_supplies`** – two supplies on one net (note; replaces H-8)  
Two supplies on one net: consider it where it applies.

**`HINT.readback`** – read-back of a serial output (note; replaces H-9)  
Read-back of a serial output: consider it where it applies.

**`HINT.motor_supply`** – motor supply: bulk capacitor and returned energy (note)  
A motor on the board: consider the bulk capacitor at its driver's motor supply and where its returned energy goes.

**`HINT.heater`** – a heater needs a second interruption (note)  
A heater on the board: consider a second, independent way to switch it off.

**`HINT.audio_ground`** – audio: ground loops and shared returns (note)  
A speaker or an analog path on the board: consider where its ground returns and what shares it.

**`HINT.class_d`** – filterless class-D output on a cable (note)  
A bridge-tied output reaches a connector: consider a filter at the output.

**`HINT.audio_switching`** – switching in the audio band (note)  
A switching regulator, a charge pump or a PWM net on a board with an audio path: consider what it puts into the audio band.

**`HINT.signal_ceramic`** – class-2 ceramic in a signal path (note)  
A class-2 ceramic capacitor (X5R, X7R, Y5V …) on a net with an analog pin: consider whether it sits in the signal path.

**`HINT.jack_battery`** – battery switched by the input jack (note)  
A battery on a board with an instrument input: consider how it is switched off.

**`HINT.pedal_supply`** – a pedal's supply among others (note)  
An instrument board with a supply input: consider the other pedals and amplifiers on the same supply and ground.

**`HINT.string_ground`** – the player on the amplifier's ground (note)  
An instrument input: consider what ties the player to ground.

**`HINT.jack_supply`** – a supply on a jack contact (note)  
A jack whose tip, ring or a switch contact carries a supply (roles tip, ring, sleeve, tip_switch, ring_switch, sleeve_switch): consider what happens while a plug goes in and comes out.

**`HINT.relay_load`** – relay contacts switching a load off the board (note)  
A relay whose contacts (common, no, nc) reach a connector or run through a cable: consider the load they switch.

**`HINT.flicker`** – LED flicker from PWM (note)  
A net with pwm_hz lights LEDs: consider whether its frequency flickers.

**`HINT.boost_enable`** – a boost converter switched off by its enable (note)  
A boost converter whose enable an MCU drives: consider what its output does with EN low.

**`HINT.usb_budget`** – the current a USB port gives (note)  
A USB receptacle that powers the board: consider what the port gives – 100 mA before the device is configured, 500 mA after (USB 2.0), 900 mA on USB 3.2 single lane, 1.5 A or 3 A only where a Type-C source advertises it on CC and the board reads the advertisement.

**`HINT.usb_inrush`** – more than 10 µF on USB VBUS (note)  
A USB receptacle whose VBUS net carries more than 10 µF directly (the capacitors' value_f): consider a soft start or less capacitance ahead of it – USB 2.0 allows a device 10 µF at attach; HINT.bulk asks for a bulk capacitor at the same input, and the two meet here.

**`HINT.power_path`** – a load on the charging cell (note)  
A charger (behaviour charger) whose battery pin feeds a load – an IC's supply pin, an LED, a motor – with nothing between that the input switches off: consider a power path. The graph shows one as a MOSFET whose gate the charger's input holds (AN1149's P-MOSFET), or as a diode onto a rail the input feeds as well; a charger with a system output of its own keeps the load off its battery pin. The cell's protection IC and a divider into an input are no load.

**`HINT.charge_termination`** – a charger's end of charge is not simulated (note)  
A linear charger (behaviour charger): consider the end of its charge cycle – the termination, the recharge and the status outputs that follow them; the simulation charges while the cell is below the float voltage and never terminates.

**`HINT.protection_timing`** – a cell protection's release and delays are not simulated (note)  
A cell protection IC (behaviour protection): consider its release voltages and its detection delays – the simulation switches the cell off and on at the detection thresholds, the moment the cell crosses them.

**`HINT.pd_negotiation`** – a USB PD sink's negotiation is not simulated (note)  
A USB PD sink (behaviour pd_sink): consider the board at 5 V before the negotiation and at the requested voltage after it, and what PG and the CC lines do – the simulation takes VBUS at the voltage a scenario's source gives.

**`HINT.input_polarity`** – a power input without a polarity check (note)  
A supply connector the graph does not mark as reversible: consider whether it can be plugged the wrong way round. Not a battery holder – PATH.reverse checks every one as a source that may be reversed.

**`HINT.thermal_copper`** – thermal resistance needs its copper (note)  
A part whose temperature rests on rth_ja_k_per_w: consider whether the layout gives the copper that figure assumes.

**`HINT.cable_line`** – a signal line on a cable (note)  
A signal net runs through a cable: consider what the cable's length and the world at its end do to it.
<!-- edakit:end -->

The designer handles each one and writes down how, in the graph (a JSON graph has the same keys,
`"accept": {"HINT.bulk": "…"}`, 3.1):

```toml
[accept]
"HINT.bulk" = "C1 1000 µF next to J1 (D-8)"
"HINT.debounce" = "firmware debounces 20 ms"
```

`edakit check` then lists it as accepted, with the reason, and the reviewer checks whether the reason holds.

**Notes in the parts database** are hints that belong to one part: `"hints": [...]` for the part and `"hint"` per pin,
from its datasheet – "ADC2: no analog reads while WiFi is on" on the ESP32's pins of ADC2, "keep BOOT0 low" on an
STM32. `edakit check` shows them as `HINT.datasheet` for the parts in the graph and their connected pins.

## 14.4 From a finding to a rule

The rules of edakit are lessons: a footprint with '+' at the cathode, a switching loop across the board, holes too
small for header tails. Each one was found once by a person or a review agent, and each one became a code, a fact or a
domain setting. The loop is part of the workflow:

1. The reviewers mark every finding with the code it falls under – then also why that code did not report it: a
   bug, or a fact missing in a parts entry – or as a **candidate**: which engine and which data would find this kind
   of fault again – a fact (a limit, a default, a table row), a new relation, or a domain setting. Findings that need
   judgement are marked as such. The classes no code covers fully yet are the reviewers' questions in the domain files
   (`[review]` in `edakit/domains/`, shown by `edakit domains`: several sources, back-feed and the switch-over gap, MCU
   pin functions, supply range and input levels of the other ICs, read-back edges, junction and touch temperature, what
   an off-board module brings), so every review asks them instead of finding them by chance; each question names the
   codes that cover part of its class (REQ.function, LIM.backfeed, LIM.range, LVL.threshold, LIM.t, REQ.missing:cc,
   HINT.two_supplies, HINT.readback).
2. In the decision round the candidates are one item: make it edakit knowledge? The user decides. Nothing is filed
   anywhere by itself – whether a finding is knowledge worth keeping is a judgement, not something a program can tell.
3. Yes: a decision in the project's decision log, written so that it can be built later without the conversation –
   what the rule would find, the finding with its numbers, the source, `edakit: open`.
4. **Proposal.** When the user asks for it, the skill `propose-rule` turns the decision into an issue in the edakit
   repository: a fixed text (`edakit proposal template`: kind, rule, why, finding, fix, sources, origin), shown to the
   user before it goes out – the issue is public – and sealed with `edakit proposal seal`, whose last line is the
   SHA-256 of the text. The decision gets the issue (`edakit: #12`).
5. **Triage.** The Action `proposals` of the edakit repository starts on every proposal of the repository owner
   and on the owner's answers, and runs the skill `triage-rule` in a session of its own. Each run takes along every
   proposal still without a result, one after another, so proposals filed at the same time are not lost when GitHub
   cancels their waiting runs. Correctly made: `edakit proposal verify` – every section filled in, the checksum
   matches; a body edited by hand fails on purpose. Does it make sense: new, the right kind, the sources hold,
   general rather than one project's choice, which engine and which data – a fact before a new relation, a relation
   only where a program decides it (else a hint) –, clear enough to build. The kinds: `fact` (a row of data: a part
   fact, a default, a table row), `relation` (a new code, a hint too), `domain` (a severity, a required fact, a
   reviewer's question), `block`, `retire`; a proposal sealed before the codes says `check`, `hint` or `part` and is
   read as relation or fact. The result
   is one of three, as a comment on the issue: **Accepted**, **Rejected** with a reason a person can check, or
   **Question** with the alternatives – everything between accepted and rejected is a question.
6. **Build.** An accepted proposal is built with the skill `add-rule` (a skill of the repository, in
   `.claude/skills/`, not part of the plugin): a fact as a row with its source (a parts entry of the block library, a
   default, a table); a relation as a code in `codes.toml` (title, rule, why, fix, severity, sources) and its place in
   an engine – a new code starts as a warning; a domain change in its domain file; then a negative test that builds
   the fault into the example and expects the code, a run against real projects to rule out false alarms, and the
   generated lists of this handbook (`python -m edakit.catalog.handbook --write`). One commit per proposal, all of
   them in one open pull request from `rules/proposals`; the user merges it. The same skill adds blocks and retires
   codes – also by hand in the repository, without an issue.
7. **Back in the project.** `propose-rule` follows the issue: it answers questions with the user, and after the merge
   the decision gets the code (`edakit: REQ.function`) or `edakit: rejected (#12)`. From the next plugin update on the
   rule runs on every project – the plugin pins no version, so every commit on `main` is an update.

Who may propose: only the repository owner – the Action does not start for anyone else, and GitHub's author field
says who wrote an issue. The checksum adds that the text is the one that was sealed. The Action needs the Claude
GitHub app on the repository and one of the secrets `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY`
(`/install-github-app` in the terminal Claude Code, or by hand: install github.com/apps/claude on the repository,
`claude setup-token`, `gh secret set CLAUDE_CODE_OAUTH_TOKEN`). A token that no longer holds shows in the step *Why
Claude stopped* as `401 Invalid bearer token`; with a new one, `gh workflow run proposals.yml` triages what is
waiting. From the Action only public projects can be cloned for the run against real projects; the pull request
names what could not be run, and that is run by hand before merging.

REQ.missing (flyback diode) and REQ.missing:cc (USB-C termination) are the reference project's buzzer stage and USB-C input turned into
rules; REQ.missing (I2C pull-ups), LVL.boot (strapping pins) and the MCU output currents of LIM come from CircuitSmith's rule
catalog (14.6).

**What no code catches.** `edakit mutate` builds mistakes into a copy of the design one at a time and lists those no code reports. On the example, without the simulation 24 of 45 are caught; with `--sim` 43 – the two left are R-EXT and the OE pull-up a hundred times larger: the LEDs dim with R-EXT, and nothing says how bright they should be (a load's `expect` would). The list is for reading, not a list of faults; a class of mistakes it shows again and again is a candidate (14.4). The reference circuits per domain (`tests/reference.py`) carry the seeded faults each domain must catch with exactly its codes.

## 14.5 Building blocks

A block is a piece of graph with checked parts: components with LCSC numbers, nets, and ports – the nets that connect
to the rest of the circuit.

```bash
edakit block list
edakit block show usb-c-sink
edakit block add usb-c-sink --as USB --connect vbus=+5V --dry-run
edakit block add led --as STATUS --connect in=LED_STATUS
```

| Block | Content |
|---|---|
| `led` | series resistor and LED from a signal to ground |
| `button` | push button to ground with a 10 kΩ pull-up |
| `i2c-pullups` | 4.7 kΩ on SDA and SCL, marks both nets as I2C |
| `npn-switch` | S8050 low-side switch with base and base-emitter resistor and a flyback diode |
| `power-input-jst` | JST PH input, SS34 against reverse polarity, 22 µF |
| `power-or-pmos` | two supplies ORed onto one rail: USB through an SS34, cells or a second input through two AO3401A back-to-back that USB switches off – neither supply is fed backwards (HINT.two_supplies) |
| `reverse-pmos` | AO3401A reverse-polarity protection with its gate resistor |
| `usb-c-sink` | USB-C power input with 5.1 kΩ per CC pin and a polyfuse |
| `addressable-led-input` | 74AHCT1G125 level shift from 3.3 V to a 5 V pixel's data input, 330 Ω series resistor, 1000 µF at the strip's supply (BL-1) |
| `nmos-switch` | AO3400A low-side switch, specified at 2.5 V gate drive, with gate resistor, pull-down and a flyback diode (BL-2) |
| `pmos-high-side` | AO3401A high-side switch with an S8050 level shift (BL-3) |
| `lipo-charger` | MCP73831 charger, DW01A and FS8205A cell protection, load sharing after Microchip AN1149 (BL-4) |
| `ldo-3v3` | RT9080 3.3 V LDO, 600 mA and 2 µA quiescent, for an ESP32 (BL-5) |
| `battery-sense` | battery voltage through a 1:2 divider a P-MOSFET switches on, hold capacitor at the ADC (BL-6) |
| `esp32-wroom-32e` | ESP32-WROOM-32E with EN 10 kΩ and 1 µF, BOOT button, the auto-program circuit and a CH340C (BL-7) |
| `usb-c-data` | USB-C with USB 2.0 data (both rows joined), USBLC6-2SC6, 5.1 kΩ per CC pin, polyfuse (BL-8) |
| `i2c-level-shift` | two BSS138 with pull-ups on both sides, 100 kHz (BL-9) |
| `rs485` | MAX3485 at 3.3 V with switchable 120 Ω termination, idle bias and DE pull-down (BL-10) |
| `midi` | MIDI in through a 6N138 and MIDI out for a 3.3 V MCU on 5-pin DIN (BL-11) |
| `cable-input` | an input on a long lead: pull-up, series resistor and capacitor, TVS at the connector (BL-12) |
| `servo-connector` | hobby servo header with a bulk capacitor (BL-13) |
| `dc-motor-drv8833` | DRV8833 for two DC motors with its VM, VCP and VINT capacitors (BL-14) |
| `eurorack-power` | keyed 10-pin Eurorack header, a series Schottky per rail, 10 µF per rail (BL-15) |
| `instrument-buffer` | OPA991 follower with a 1.1 MΩ input, RF filter at the jack, 100 Ω output, an AC expectation (BL-16) |
| `pedal-power` | 9 V centre-negative jack, Schottky, 100 Ω and 100 µF, a 4.5 V reference (BL-17) |
| `relay-bypass` | true bypass with a gold-contact signal relay, transistor coil drive and a photo-MOS mute (BL-18) |

What `add` does: designators get the next free numbers (`R1` of the block becomes `R7`), internal nets get the
instance's name (`STATUS_ANODE`), each port joins the net given with `--connect` – or a new net, if the block knows its
voltage range – and `gnd` joins the project's ground. Missing parts entries are copied from the block library; an
existing entry must have the same pins. A JSON graph keeps its indentation. A TOML graph (`graph` in 10.1) keeps its
comments and arrangement: each new part and net is a table after the last of its kind, a pin on an existing net goes at
the end of its `pins` array as the array is written – inline, or on a line of its own –, the block's `accept` becomes
keys of the table (`accept."LIM.v" = "…"`), and a part's pin map is left out where its parts entry gives it; what would
not read back as the graph a JSON file would get is not written. `edakit graph json --write` follows, as after every
change of a TOML graph (3.1). The block's notes say what is left to decide: the LED
current, the entries in sim.json, `"source": "reversible"` on the connector.

A block may carry keys of the graph and say what can go:

- `graph` – keys for the project's graph: `{"grounds": ["cell_n"]}` adds the block's net (under its instance name,
  `CHG_CELL_N`) to the graph's `grounds` (3.1) – the lipo-charger's cell minus, the DW01A's own ground.
- `optional` – `{"parts": ["R3"], "ports": ["dout"]}`: parts `--without R3` leaves out, and ports that may stay
  unconnected. A pin left alone on a net by a missing part goes into its component's `nc` when the net is an optional
  port that `--connect` does not name (addressable-led-input without its second series resistor); a net left with no
  pin is not created. `--without` refuses a part that is not optional. The flyback diode of the nmos-, npn- and
  pmos-switches (no winding to drive) and the bias pair of rs485 (a bus biased elsewhere) are optional.
- `accept` on a block's net or component may name a place – `{"LIM.v D1": "…"}` –; `add` renames the designator in
  the key as it renames the part (3.1).

Every block passes `edakit check` and `edakit sim` and is drawn by `edakit schematic draw` once it is in the example
project – a test makes sure of that; where in the example it goes, and what its simulation needs, stands in the block's
own `test` table: `connect` (its ports in the example), `sim` (the block's own sim.json keys, merged deeply into the
example's – an MCU's outputs, loads –, or `false` where the example's rails, not the block, keep it from simulating),
`remove_supplies` (supply cases of the example the block cannot meet, the example's +5V behind its diode at USB
minimum), `without` (optional parts the test leaves out); `sim: false` and `remove_supplies` need a `why`.
Their parts come from the parts library and are drafts until the owner signs them (4.1). That
makes a block a good start, not a sign-off: values, ratings and the review are still the project's. A project's own
blocks are JSON files of the same form, added with `--file`.

## 14.6 Where the ideas came from

CircuitSmith, a sibling project that draws schematics from declarative YAML and checks them against an ERC rule
catalog, brought in: the catalog with reason and source for every rule; the designer as an "electronics engineer" bound
to the parts library and to rules instead of memory, asking open questions in one batch; sub-blocks with ports; and the
checks for I2C pull-ups, strapping pins, input-only pins and the MCU's current budget. CircuitSmith's other goal, a
schematic without an EDA tool, edakit reached with what it had: the layout it computes for EasyEDA, drawn with symbols
from the parts database (6.5). Not taken: CircuitSmith's renderer and layout engine, and the KiCad netlist.
