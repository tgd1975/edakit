# 14 Designing a circuit: rules, hints and building blocks

Chapters 3 to 8 check a circuit. This chapter is about the step before: getting from "five LEDs, a servo, USB power"
to a graph – and about the knowledge the checks are made of.

## 14.1 Roles

| Role | Who | Does |
|---|---|---|
| circuit designer | a session with the skills `circuit-design` and `hardware-change` | asks for the requirements in one decision round, picks blocks and parts, computes values, writes the graph, works through `edakit check`, `edakit hints` and `edakit sim`, draws the schematic, writes the hand-over |
| electrical reviewer | agent `electrical-reviewer`, its own session | reads graph, hand-over, parts, simulation and datasheets, changes nothing, returns numbered findings – its result is the sign-off M-1 |
| PCB designer | a session of its own with the skill `pcb-round` | works from the hand-over: EasyEDA schematic, PCB, placement plan, routing, silkscreen; does not change the graph |
| EasyEDA operator | agent `easyeda-operator` | runs one long EasyEDA step for the PCB designer and returns only the result |
| PCB reviewer | agent `pcb-reviewer`, its own session | reads plan, hand-over, routing and manufacturing files, changes nothing – its result is the sign-off M-5 |
| decider | the user | answers the decision rounds: warnings, looks and operation, money, what becomes a check |

No role checks its own work: a second opinion from the session that made the decisions repeats the decisions; the
reviewer starts without them.

**The hand-over.** Circuit and layout are separate sessions, so what the layout must know is written down – the
PCB designer gets nothing else. It is `layout` in the graph: parts that are fixed (pressed, looked at), at the edge
(plugged in from outside), next to another part (a current-setting resistor at its pin), the hot loops of switching
regulators, and notes no program checks. The decoupling capacitor of every IC is derived from the graph.
`edakit handover` shows all of it together with the circuit's state and sign-offs, and L-12 holds the plan to it
(7.4). Because it is part of the graph, the hand-over is reviewed and signed with the circuit (M-1). A circuit change
the layout needs – another GPIO, another footprint – goes back as a written request in the decision log; the PCB
designer does not change the graph. A project without a PCB ends at the hand-over: the drawing is the schematic.

## 14.2 The rule catalog

`edakit/rules.json` holds every check edakit runs – P, G, E, S, L, F – with five things: a **title** (the words that
go next to the ID: "L-9 (hole fits the lead)"), the **rule** in one sentence, **why** it exists, **what to do** about a
finding, and the **sources**: a standard, an application note, a datasheet, or the lesson in this handbook the check
was born from.

```bash
edakit rules            # all checks and hints, one line each
edakit rules G-11 L-9   # the full entries
```

The catalog is where findings get explained: `edakit check` prints the entry of every check that failed below the
findings, and the gate protocol ends with "The rules behind the findings" for every check that failed or warned. A
test makes sure that every check ID the code can report has an entry.

**Check IDs are stable.** A check that is retired keeps its entry and its number is not reused – G-7 (polarity in the
graph) moved to the simulation and stays G-7, retired. A protocol from last year must still mean what it meant.

**Findings come only from code.** A check is a function with a negative test; Claude does not invent checks at
runtime. What Claude knows beyond the catalog goes into a review as a finding with its evidence, or into a check
candidate (14.4) – not into a finding that looks like a check.

## 14.3 Hints

Some knowledge has no rule a program could decide: whether a hot-plugged cable needs an electrolytic, whether a button
needs a hardware debounce, whether a connector is touched by people. These are **hints**: matched by the kinds of parts
in the graph or by a pattern, shown by `edakit hints`, never blocking.

| Hint | When | About |
|---|---|---|
| H-1 | a power input (battery holder, connector with a `vbus` pin, `[checks] reverse_protect`, a sim source) | bulk capacitor at the input against hot-plug ringing and load steps |
| H-2 | a MOSFET | gate series resistor against ringing |
| H-3 | a button, switch or DIP switch | debouncing |
| H-4 | a transistor switching a connector pin | flyback diode for an inductive load off the board |
| H-5 | a buck or boost regulator, an inductor | the hot loop – and L-11 to check it |
| H-6 | a battery holder | protection for lithium cells |
| H-7 | a signal line from a connector to an IC pin | ESD protection at the connector |

The designer handles each one and writes down how, in the graph:

```json
"hints": {"H-1": "C1 1000 µF next to J1 (D-8)", "H-3": "firmware debounces 20 ms"}
```

`edakit hints` then lists it as taken care of, and the reviewer checks whether the reason holds. `edakit check` names
the open ones in its last line.

**Notes in the parts database** are hints that belong to one part: `"hints": [...]` for the part and `"hint"` per pin,
from its datasheet – "ADC2: no analog reads while WiFi is on" on the ESP32's pins of ADC2, "keep BOOT0 low" on an STM32.
`edakit hints` shows them for the parts in the graph and their connected pins.

## 14.4 From a finding to a check

The checks of edakit are lessons: a footprint with '+' at the cathode, a switching loop across the board, holes too
small for header tails. Each one was found once by a person or a review agent, and each one became a check. The loop
is part of the workflow:

1. The reviewers mark every finding with the catalog check it falls under – then also why that check did not report
   it, which may be a bug – or as a **check candidate**: what a rule over graph, parts, simulation, plan or Gerber
   files would test to find this kind of fault again. Findings that need judgement are marked as such.
2. In the decision round the check candidates are one item: make it a check? The user decides. Nothing is filed
   anywhere by itself – whether a finding is knowledge worth keeping is a judgement, not something a program can tell.
3. Yes: a decision in the project's decision log, written so that it can be built later without the conversation –
   what the check would test, the finding with its numbers, the source, `edakit: open`.
4. **Proposal.** When the user asks for it, the skill `propose-rule` turns the decision into an issue in the edakit
   repository: a fixed text (`edakit proposal template`: kind, rule, why, finding, fix, sources, origin), shown to the
   user before it goes out – the issue is public – and sealed with `edakit proposal seal`, whose last line is the
   SHA-256 of the text. The decision gets the issue (`edakit: #12`).
5. **Triage.** The Action `proposals` of the edakit repository starts on every proposal of the repository owner
   and on the owner's answers, and runs the skill `triage-rule` in a session of its own. Correctly made: `edakit
   proposal verify` – every section filled in, the checksum matches; a body edited by hand fails on purpose. Does it
   make sense: new, the right kind, the sources hold, general rather than one project's choice, decidable by a program
   (else a hint), clear enough to build. The result is one of three, as a comment on the issue: **Accepted**,
   **Rejected** with a reason a person can check, or **Question** with the alternatives – everything between accepted
   and rejected is a question.
6. **Build.** An accepted proposal is built with the skill `add-rule` (a skill of the repository, in
   `.claude/skills/`, not part of the plugin): catalog entry (title, rule, why, fix, sources), the check, a negative
   test that builds the fault into the example and expects the check to fail, a run against real projects to rule out
   false alarms, and the table in this handbook. One commit per proposal, all of them in one open pull request from
   `rules/proposals`; the user merges it. The same skill adds hints, blocks and facts of single parts, and retires
   checks – also by hand in the repository, without an issue.
7. **Back in the project.** `propose-rule` follows the issue: it answers questions with the user, and after the merge
   the decision gets the check's ID (`edakit: G-15`) or `edakit: rejected (#12)`. From the next plugin update on the
   check runs on every project – the plugin pins no version, so every commit on `main` is an update.

Who may propose: only the repository owner – the Action does not start for anyone else, and GitHub's author field
says who wrote an issue. The checksum adds that the text is the one that was sealed. The Action needs the Claude
GitHub app on the repository and one of the secrets `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY`
(`/install-github-app` in the terminal Claude Code, or by hand: install github.com/apps/claude on the repository,
`claude setup-token`, `gh secret set CLAUDE_CODE_OAUTH_TOKEN`). From the Action only public projects can be cloned for the run against real
projects; the pull request names what could not be run, and that is run by hand before merging.

G-13 (flyback diode) and G-14 (USB-C termination) are the reference project's buzzer stage and USB-C input turned into
rules; G-11 (I2C pull-ups), G-12 (strapping pins) and the MCU output currents of E-2 come from CircuitSmith's rule
catalog (14.6).

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
| `reverse-pmos` | AO3401A reverse-polarity protection with its gate resistor |
| `usb-c-sink` | USB-C power input with 5.1 kΩ per CC pin and a polyfuse |

What `add` does: designators get the next free numbers (`R1` of the block becomes `R7`), internal nets get the
instance's name (`STATUS_ANODE`), each port joins the net given with `--connect` – or a new net, if the block knows its
voltage range – and `gnd` joins the project's ground. Missing parts entries are copied from the block library; an
existing entry must have the same pins. The graph file keeps its indentation. The block's notes say what is left to
decide: the LED current, the entries in sim.json, the connector in `[checks] reverse_protect`.

Every block passes `edakit check` and `edakit sim` and is drawn by `edakit schematic draw` once it is in the example
project – a test makes sure of that. That
makes a block a good start, not a sign-off: values, ratings and the review are still the project's. A project's own
blocks are JSON files of the same form, added with `--file`.

## 14.6 Where the ideas came from

CircuitSmith, a sibling project that draws schematics from declarative YAML and checks them against an ERC rule
catalog, brought in: the catalog with reason and source for every rule; the designer as an "electronics engineer" bound
to the parts library and to rules instead of memory, asking open questions in one batch; sub-blocks with ports; and the
checks for I2C pull-ups, strapping pins, input-only pins and the MCU's current budget. CircuitSmith's other goal, a
schematic without an EDA tool, edakit reached with what it had: the layout it computes for EasyEDA, drawn with symbols
from the parts database (6.5). Not taken: CircuitSmith's renderer and layout engine, and the KiCad netlist.
