# The circuit as a language, or as TOML with names

Status 2026-10-31: sketch of step 4.3 of the [implementation plan](implementation-plan.md), for decision 8 of
[design-as-text.md](design-as-text.md), written on 2026-10-29 against edakit at `75d5c32` and the bell at `f56b463`,
reviewed on 2026-10-31 against main at `075574e`. The owner's conclusion from the review is in the section
[Review 2026-10-31](#review-2026-10-31): what is worth building is independent of a language of its own and is built
in any case; the language is deferred until it offers what a format cannot. The decisions at the end were taken the
same day: TOML with names as the form, the pin map from the parts entry, the hash over the form's canonical data, a
resolved `graph.json` generated beside the form, four complete variants, the symbol's names and the roles, no net in
fragments; what both forms share has a plan of its own, [circuit-language-plan.md](circuit-language-plan.md). Since
the sketch, the cut of rules at scale (`4982d35`) has changed the graph's keys and the codes; the examples below and
the prototype still use the old ones, and the review lists what to bring along. The Christmas bell's main
configuration is written down both ways in
[prototypes/circuit-language](prototypes/circuit-language/): as a language,
[bell.circuit](prototypes/circuit-language/bell.circuit), and as TOML with pin names,
[bell.toml](prototypes/circuit-language/bell.toml). The translator `translate.py` takes all four configurations
there and back without a difference, at the state of `75d5c32`.

## Goal

Decision 8: write the whole bell down both ways, then choose which one edakit builds. The concept names four things
that make the JSON cryptic: pin numbers instead of names, names that mislead (LED5's pin 1 is "C" but is the anode),
a path through the circuit that falls apart, and no comments. Its touchstone: translate there and back without a
difference, so that every check keeps running on today's graph.

## The two forms

**The language** (`.circuit`) has one statement per part and per net. A net is a line with its voltage range. A path
is a few net lines in a row, with the pin lock at its pin. Comments start with `#`. Quoted text may run over several
lines.

**TOML with names** is today's graph in TOML. Components, nets and cables are tables keyed by designator and net
name. It has the same fields as the JSON, with comments and multi-line strings.

Both write a pin by role or name (`LED5.anode`, `U1.PD6`) and resolve it through the parts entries. Both take a
part's pin map from its parts entry, and both keep the order of parts, nets and pins, so the JSON comes back with
the same lists in the same order.

The extension `.circuit` says what the file holds. SPICE netlists use `.cir`, `.ckt` and `.net`, and edakit writes
`.cir` for the simulation; KiCad netlists use `.net`, Logisim `.circ`, atopile `.ato`. `[project] graph` names the file,
so a project would have `hardware/graph.circuit`.

## Side by side

### The Nano

JSON, 65 lines in the file (pin map and `nc` shortened here):

```json
{"designator": "U1", "type": "module", "label": "Arduino Nano 3 (plugged in)", "part": "Arduino Nano V3",
 "lcsc": "C9900187880", "bom": false,
 "pins": {"1": "TXD", "2": "RXD", "3": "RESET", "4": "GND", "5": "PD2", "…": "…", "29": "GND", "30": "VIN"},
 "nc": ["1", "2", "3", "10", "12", "13", "16", "17", "18", "19", "…", "28", "30"],
 "waive": {"P-1": "VIN stays free: the Nano runs from its USB socket"},
 "notes": "Plugs into two 1x15 female headers, …"}
```

Language, 7 lines:

```text
part U1    module     "Arduino Nano V3"   lcsc C9900187880  no-bom      "Arduino Nano 3 (plugged in)"
  nc     TXD RXD RESET PD7 PB1 PB2 PB5 3V3 AREF PC0 PC1 PC2 PC3 PC4 PC5 ADC6 ADC7 PC6 VIN
  waive  P-1 "VIN stays free: the Nano runs from its USB socket"
  notes  "Plugs into two 1x15 female headers, pitch 2.54 mm (hand-soldered, not in the graph). Powered through its
         USB socket; …"
```

TOML, 14 lines:

```toml
[components.U1]
type = "module"
label = "Arduino Nano 3 (plugged in)"
part = "Arduino Nano V3"
lcsc = "C9900187880"
bom = false
nc = ["TXD", "RXD", "RESET", "PD7", "PB1", "PB2", "PB5", "3V3", "AREF", "PC0", "PC1", "PC2", "PC3", "PC4", "PC5",
      "ADC6", "ADC7", "PC6", "VIN"]
waive.P-1 = "VIN stays free: the Nano runs from its USB socket"
notes = """\
  Plugs into two 1x15 female headers, pitch 2.54 mm (hand-soldered, not in the graph). Powered through its USB \
  socket; …"""
```

In both forms the pin map comes from the parts entry `C9900187880`. Its two GND pins are `U1.GND` where they stand
together in a net. One name misleads and no role helps: the symbol swaps the labels of pins 14 and 15, so `U1.PB4`
is D11 (PB3 on the chip). The form cannot know; both files say it in a comment.

### Step 1: D6 → 330 Ω → green LED → GND

JSON, 48 lines in four places of the file (shortened here):

```json
{"designator": "LED5", "type": "led", "label": "5 mm LED, green, countdown step 1", "part": "XL-504UGD",
 "lcsc": "C2895549", "bom": false, "pins": {"2": "A", "1": "C"}},
{"designator": "R4", "type": "resistor", "label": "Series resistor LED5", "part": "330 Ω 0805", "lcsc": "C17630",
 "value": "330Ω", "pins": {"1": "1", "2": "2"}},
{"name": "LED_G1", "pins": ["U1.9", "R4.1"], "v": [0, 5.5]},
{"name": "LED_G1_A", "pins": ["R4.2", "LED5.1"], "v": [0, 5.5]},
{"name": "GND", "pins": ["U1.4", "U1.29", "C1.2", "J1.1", "R6.2", "R7.2", "LED5.2", "…"], "v": [0, 0]},
"pin_locks": {"U1.9": "LED_G1", "…": "…"}
```

Language: two lines in the parts table, and the path in one piece:

```text
part LED5  led        XL-504UGD           lcsc C2895549     no-bom      "5 mm LED, green, countdown step 1"
part R4    resistor   "330 Ω 0805"        lcsc C17630       value 330Ω  "Series resistor LED5"
…
# Step 1: D6 → R4 → green LED5 → GND
net LED_G1     0..5.5 V  U1.PD6 (locked) R4.1
net LED_G1_A   0..5.5 V  R4.2 LED5.anode
net GND                  LED5.cathode
```

TOML: two component tables, two net tables; the cathode stays in the GND table, the lock in `[checks.pin_locks]`:

```toml
[components.LED5]
type = "led"
label = "5 mm LED, green, countdown step 1"
part = "XL-504UGD"
lcsc = "C2895549"
bom = false

[components.R4]
type = "resistor"
label = "Series resistor LED5"
part = "330 Ω 0805"
lcsc = "C17630"
value = "330Ω"

# Step 1: D6 → R4 → green LED5
[nets.LED_G1]
v = [0, 5.5]
pins = ["U1.PD6", "R4.1"]

[nets.LED_G1_A]
v = [0, 5.5]
pins = ["R4.2", "LED5.anode"]

# in [nets.GND]:            "LED5.cathode", "LED4.cathode", …
# in [checks.pin_locks]:    "U1.PD6" = "LED_G1"    # D6
```

The misleading "C" appears in neither form: an LED is written by its roles.

### A waiver

The bell waives on one component only, the Nano's P-1 above; none of its nets has a waiver. A net waiver as in
edakit's example led-bar:

```json
{"name": "LED_CLK", "pins": ["U1.4", "U2.3"], "v": [0, 3.4], "fn": "spi.sck", "fn_bus": "LED",
 "waive": {"G-4": "Floating until the firmware runs, but harmless: R2 holds OE high, so no output can switch on."}}
```

```text
net LED_CLK 0..3.4 V U1.GP2 (locked) U2.CLK
  fn spi.sck fn_bus LED
  waive G-4 "Floating until the firmware runs, but harmless: R2 holds OE high, so no output can switch on."
```

```toml
[nets.LED_CLK]
v = [0, 3.4]
pins = ["U1.GP2", "U2.CLK"]
waive.G-4 = "Floating until the firmware runs, but harmless: R2 holds OE high, so no output can switch on."
fn = "spi.sck"
fn_bus = "LED"
```

### The servo

The bell has no `cables` entry: the servo brings its own cable and plugs into J1 (hint H-7 of the variants). In the
graph it is J1, the net SERVO and J1's pins in +5V and GND. Language:

```text
part J1    connector  PZ254V-11-03P       lcsc C2937625     no-bom      "Servo (GND, +5 V, signal)"
  notes  "Standard servo plug: brown = GND (1), red = +5 V (2), orange = signal (3)."
…
# Servo on D8. Its own cable plugs into J1: brown GND, red +5 V, orange signal. C1 takes its start-up peaks.
net +5V                  C1.plus J1.2
net GND                  C1.minus J1.1
net SERVO      0..5.5 V  U1.PB0 (locked) J1.3
```

In TOML, J1 is a table like LED5 above, SERVO is `pins = ["U1.PB0", "J1.3"]`, and J1's other pins stand in the
arrays of +5V and GND, each with a comment. J1's pins stay numbers: its roles `pin1` … `pin3` say no more. A real
cable, as in handbook 3.1, would be `cable W1 J2 J1 1=1 2=2 r_ohm_per_wire 0.065` in the language and a table
`[cables.W1]` in TOML.

### purpose

```json
"purpose": {"use": "private", "market": "EU",
            "notes": "Automatic Christmas bell for the owner's home, built and used by the owner – not sold or given away (D-16). Powered from a USB port or power bank through the Nano's USB; no battery holder, no mains, no radio."}
```

```text
purpose private market EU
  notes "Automatic Christmas bell for the owner's home, built and used by the owner – not sold or given away (D-16).
    Powered from a USB port or power bank through the Nano's USB; no battery holder, no mains, no radio."
```

```toml
[purpose]
use = "private"
market = "EU"
notes = """\
  Automatic Christmas bell for the owner's home, built and used by the owner – not sold or given away (D-16). \
  Powered from a USB port or power bank through the Nano's USB; no battery holder, no mains, no radio."""
```

The content is the same in all three. The regulatory review M-6 reads `purpose` whole, as today (`KEEP_WHOLE` in
`gate.py`), and it stays in the circuit hash under either hash rule below. M-6 is support, not legal advice: nothing
in it is legally guaranteed, and it makes no claim to being correct.

## Every field of the graph

| Field | Language | TOML with names |
| --- | --- | --- |
| `name`, `version`, `date` | `graph christmas-bell version 0.3 date 2026-10-25` | `name = "christmas-bell"`, … |
| `description` | `description "…"` | `description = """…"""` |
| `purpose` | `purpose private market EU` and `notes "…"` | `[purpose]` |
| `conventions`, `hints` | `convention v "…"`, `hint H-1 "…"` | `[conventions]`, `[hints]` |
| `ground`, `grounds` | `ground GND`, `grounds AGND` | `ground = "GND"`, `grounds = ["AGND"]` |
| component: `designator`, `type`, `part` | `part R4 resistor "330 Ω 0805"`; `-` for a missing one | `[components.R4]`, `type`, `part` |
| `lcsc`, `value`, `board`, `supplier`, `spare` | `lcsc C17630 value 330Ω board main supplier rs spare 1` | keys of the table |
| `bom: false` | `no-bom` | `bom = false` |
| `label` | the quoted text at the end of the part's line, or `label "…"` | `label = "…"` |
| `pins` (pin map) | from the parts entry; `pins 1=TXD 2=RXD …` only where the graph differs | the same; `pins = {…}` |
| `nc` | `nc TXD RXD …`, pins by name or role | `nc = ["TXD", "RXD", …]` |
| `waive` | `waive P-1 "…"`, one line each | `waive.P-1 = "…"` |
| `verify`, `notes` | `verify "…"`, `notes "…"` | keys |
| net: `name`, `v` | `net LED_G1 0..5.5 V`; `0 V` for `[0, 0]` | `[nets.LED_G1]`, `v = [0, 5.5]` |
| net: `pins` | the words after the range; a later `net GND LED5.cathode` adds pins | `pins = ["U1.PD6", "R4.1"]` |
| `fn`, `fn_bus`, `bus`, `pwm_hz` | `fn spi.sck fn_bus LED` | keys |
| `cables` | `cable W1 J2 J1 1=1 2=2 r_ohm_per_wire 0.065` | `[cables.W1]` |
| `layout` | `layout fixed …`, `layout edge J1`, `layout near R1 U2`, `layout loop C5.1 U3.2 max_mm 8 "…"`, `layout note "…"` | `[layout]`; loop ends by name |
| `checks.pin_locks` | `(locked)` after the pin in its net; `lock PIN NET` for a pin on another net | `[checks.pin_locks]`, keys by name |
| `checks.reverse_protect` | `reverse_protect J1` | `reverse_protect = ["J1"]` |
| anything else | `set KEY JSON`, e.g. `set easyeda_device {…}`, `set checks.doc_pin_table {…}` | written as TOML |

## Rules the round trip needs

| Case | Example | Rule |
| --- | --- | --- |
| A pin has a role of its own | LED5 pin 1: name "C", role `anode` | The role first, except on ICs and modules: `LED5.anode`. The misleading name never appears. |
| A name of one pin | Nano pin 9: PD6 | `U1.PD6`; on ICs and modules the name comes first, their names are the datasheet's. |
| Pins share a name | Nano pins 4 and 29: GND | The name stands for all of them, in the entry's order, where they follow each other in a list: `U1.GND`. Elsewhere the number: `U1.4`. |
| Pins share a name, one is used | T-Display pins 12 and 13: 3V3, 13 not connected | The number: `U1.12`, `nc 13`. |
| Pins share a role | a button's pins 1 and 2: role `a` | As a shared name: `S1.a` stands for both. |
| A word that says no more than the number | resistor pin "1", connector role `pin3` | The number: `R4.1`, `J1.3`. |
| A name that is no word | the Pico's TP1, "GND (USB)" | The number: `U1.TP1`. |
| A name misleads and no role helps | Nano pin 14: "PB4", really D11 = PB3 | `U1.PB4`, and a comment. The translator cannot know. |
| Reading a word | | The pin number first, then the name of one pin, then the role of one pin, then a name or role several pins share. The writer takes the first word that reads back as exactly the pins it means, else the number. |
| Pin map | | From the parts entry; written only where the graph's differs. In all four configurations it equals the entry. |
| Order | | Parts, nets and the pins of a net come back in the order written. Free arrangement is only possible within that order: `bell.circuit` puts the parts first and then the wiring in blocks. |
| A net over several lines (language) | `net GND LED5.cathode` | A later line adds pins, and attributes the net does not have yet; a range or attribute twice is an error. |
| Pin locks | `U1.PD6 (locked)` | At the pin in its net. A lock on a pin that sits on another net (a G-2 finding): `lock PIN NET`. |
| A value without a form of its own | `easyeda_device`, the empty `cables` | `set KEY JSON` in the language (`set cables []`). TOML holds every JSON value as it is. |
| null | | TOML has none; the TOML writer refuses a graph with one. None of the graphs has one. |
| A broken graph | two parts R4, a pin `U1.99` | Both writers refuse it with the reason: G-1 reports it; fix the JSON first. |
| The wrapper | `{"graph": {…}}` | The forms hold the inner graph; the JSON comes back with the wrapper, as every edakit project has it. |
| Text over several lines | | Language: a line break inside quotes reads as one space. TOML: a line-ending backslash in `"""…"""`. |

## The round trip

`test_translate.py` runs graph JSON → form → JSON for both forms and compares canonical JSON (keys sorted, every list
in its order). `BELL_ROOT=<checkout of the bell> python3 test_translate.py`; without `BELL_ROOT` the bell's cases are
skipped, and edakit's pytest does not collect the folder.

| Case | JSON | TOML | Language | Result |
| --- | --- | --- | --- | --- |
| bell, main | 515 | 240 | 63 | equal, both forms |
| bell, smd | 518 | 245 | 73 | equal, both forms |
| bell, tht | 531 | 256 | 68 | equal, both forms |
| bell, esp32 | 519 | 265 | 87 | equal, both forms |
| led-bar, edakit's example | 610 | 252 | 75 | equal, both forms |
| led-bar with every field the bell does not use | 696 | 304 | 102 | equal, both forms |
| `bell.circuit`, `bell.toml`, written by hand | 515 | 281 | 114 | equal to the bell's `hardware/graph.json` |

The numbers are lines. In the first six rows the forms are what the translator writes. The sixth case adds cables,
layout loops, `ground` and `grounds`, hints, an own pin map, a part without parts entry, a lock off its net, values
that are no strings, quotes, backslashes and line breaks.

## Line counts

| The bell, main configuration | Lines | Without comments and blank lines | Bytes |
| --- | --- | --- | --- |
| `hardware/graph.json` | 515 | 515 | 9 294 |
| TOML, written by the translator | 240 | 201 | 5 829 |
| TOML by hand, `bell.toml` | 281 | 211 | 8 283 |
| Language, written by the translator | 63 | 59 | 4 422 |
| Language by hand, `bell.circuit` | 114 | 72 | 7 608 |

The JSON's length is mostly line breaks: one value per line. In bytes, which is what Claude reads, the translator's
language takes about half of the JSON and its TOML about two thirds. Comments and arrangement make the hand-written
language 72 percent larger than the translator's, the hand-written TOML 42 percent.

## The variants

Today the bell has four complete graphs, each a project of its own (`variants/<v>/edakit.toml`) with its own parts,
simulation, boards and sign-offs. They differ in parts and texts; the wiring is mostly the same. Changed lines against
main, as the translator writes them:

| Variant | JSON | TOML | Language | Its nets |
| --- | --- | --- | --- | --- |
| smd | 117 | 83 | 40 | JSON: GND, LED_Y1_A and LED_Y2_A differ. Both forms: only GND, the order of R8 and R9 |
| tht | 92 | 74 | 37 | identical in all three |
| esp32 | 350 | 225 | 116 | all differ: another module, another supply |

Roles do this. The 0805 LEDs of smd have the anode on pin 1, the yellow 5 mm LEDs of main on pin 2: two pin numbers in
JSON, one `LED3.anode` in both forms.

A variant could also list only its differences: `use ../../hardware/graph.circuit` and the statements that replace
the main file's, by designator and net name. SMD would be 26 lines of content instead of 69, THT 26 instead of 64;
ESP32 changes 37 of its 45 statements and gains nothing. TOML has no include; edakit would define one (`base = "…"`
and tables replaced by key). Either way the variant's circuit then depends on the main file: a change there changes
the variant's hash and voids its sign-offs, where today the four are independent. Not built in the prototype.

## What each form costs

### Parser and formatter

The prototype, `translate.py`, in lines of code without comments and blank lines:

| Part | Language | TOML with names |
| --- | --- | --- |
| Pins by role or name, shared | 89, and 33 of helpers | the same |
| Reading | 242: scanner, statements, every field, errors with lines | `tomllib` from the standard library, and 35 to resolve names |
| Writing from the graph (moving a project, the tests) | 166 | 99: the standard library has no TOML writer |
| A formatter that keeps comments and arrangement | not built; needed for `edakit graph fmt` | none needed for reading; tools that edit need a comment-keeping editor (tomlkit, a dependency) or a line editor of their own |

Built into edakit with validation per statement, tests and messages, the language may come to two or three times
that. TOML stays near its prototype.

### Error messages

| | Language | TOML with names |
| --- | --- | --- |
| A typo in a pin | `line 93: 'LED5.anod': no pin of that number, name or role on LED5` | `line 233: …` the same, the line found by searching the text for the word |
| A syntax error | with its line | with line and column (`tomllib`) |
| A wrong shape | `0..5,5 V`: `line 93: net LED_G1_A: '0..5,5 V' is no voltage range` | `v = [0, 5,5]` is valid TOML, three numbers; G-1 reports it later with the net's name, no line |
| A range twice | `line 110: net GND: v given twice` | a key twice: a TOML error |

Today a JSON syntax error has its line and column, and G-1 names nets and pins, not lines. Both forms keep that for
the checks.

### Handbook

The language needs a chapter with its syntax and rules, read before every edit of the graph: the skills
circuit-design and hardware-change point to it, and the reviewers read the graph. About a page; it costs context
each time, against the half of the JSON's bytes the language saves. TOML needs a section in chapter 3: tables by
key, pins by role or name. Claude and every editor know TOML; GitHub and editors highlight it. Nothing highlights
`.circuit`.

### Tools that write the graph

| Writer | Today | Language | TOML with names |
| --- | --- | --- | --- |
| `edakit block add` (`block.py`) | reads and writes the JSON itself | appends the block's statements: its parts, its nets, `net GND C5.minus` for pins on an existing net, `bus i2c` in such a line | new tables at the end; pins and attributes for existing nets go into their tables: an editor that keeps comments |
| New: `edakit graph convert`, `edakit graph json` | – | convert a project once (the translator's writer); print the graph as JSON | the same |
| New: `edakit graph fmt` | – | spacing and columns, keeping comments and arrangement | not needed |
| Skills | circuit-design (§5), hardware-change (§1), own-part (§4), new-project (the empty `hardware/graph.json`) | examples and wording to the language | to TOML; smaller changes, the structure stays |
| Agents | electrical-reviewer, regulatory-reviewer, project-surveyor, requirements-engineer read the graph | read the chapter | read TOML |
| Handbook | chapters 3, 7, 10, 14 and 15 show the graph's JSON or its path | to the language | to TOML |
| `load_graph()` (`design.py`) | reads JSON | reads `.circuit` by its extension; JSON stays | reads `.toml` by its extension; JSON stays |

No key, no change: a project keeps `hardware/graph.json` until it converts. The bell's own mentions of `graph.json`
(`hardware/README.md`, `docs/decisions.md`, a comment in the esp32 firmware) change in the bell, at the user's request.

### `edakit check` and the hashes

**The checks keep running on today's graph, in both forms.** `load_graph()` returns the same dict as from the JSON;
every check, the simulation, the schematic, the hand-over and the firmware contract read it unchanged. Two things
move:

- P-1 compares the graph's pins with the parts entry. Where the form takes the pin map from the entry, that half has
  nothing left to compare. The comparison with the library's symbol from `part import` stays.
- Findings name pins by number (`U1.9 (PD6) is neither connected nor nc`). They should name them as the form does;
  the writer's rule gives the word.

**The circuit hash.** Today it covers `graph.json` as bytes, or as canonical JSON without the keys of
`[release] hash_ignore`. `content()` in `gate.py` keeps a file that is no JSON as bytes, so `hash_ignore` would stop
reaching into the graph without a word. Two ways, the same for both forms:

- the translated graph as canonical JSON: comments, line breaks and the arrangement count for nothing, every change
  of data does, and `hash_ignore` works as today;
- the bytes of the form: every comment and every rearrangement voids M-1 and M-6.

`graph_sha256` in the gate protocol names the form's bytes either way. The parts entries are in the hash already, and
the names resolve through them.

**A rewire through a parts entry.** A corrected role moves the connection without a change in the form: if LED5's
anode were found on pad 2, `LED5.anode` would now mean pin 2. Today the graph keeps `LED5.1`, and the simulation
reports a reversed LED until someone changes the graph. With a form the board follows the entry. The hash sees the
entry's change and M-1 lapses; the form's diff does not show it, `edakit graph json` before and after does.

## Recommendation

The recommendation of the sketch, 2026-10-29. The review below weighs the same facts differently, and the owner
followed the review: the language is deferred.

Build the language.

1. It is the only form that fixes all four points of the concept. TOML fixes three: its paths keep the cathode in
   GND and the lock in `[checks.pin_locks]`.
2. The cost is medium. The prototype reads every field in 242 lines and writes it in 166. Pins by role or name,
   `load_graph()` and the hash rule are needed by both forms and can be built first.
3. Tools write it by appending. `block add` appends statements; TOML needs an editor that keeps comments, or a
   dependency.
4. Every error has its line, and the parser checks shapes (a range is two numbers) before any check runs.
5. It is short where review happens: a part is a line, a net is a line, and the bell's circuit is 72 lines of
   content against 211 in TOML.

Against it: a syntax nobody knows yet, read from the handbook before every edit; nothing highlights it; a net may be
spread over several lines (GND over nine in `bell.circuit`); and a parser to maintain. If that weighs more, TOML with
names keeps most of the gain, and the shared part is the same.

Order, if decided so: pins by role or name with `load_graph()`, the hash rule and `edakit graph json` first (both
forms need them, size M); then the parser, `edakit graph convert` and `fmt`, the chapter and the skills (size M); the
bell converts last, in its repository.

## Review 2026-10-31

Reviewed against main at `075574e`, with the prototype run on edakit's led-bar. The bell's four configurations were
not run again: the bell's repository was not reachable from the session; a checkout with `BELL_ROOT` does it. The
owner's conclusion, in their words: the single ideas are worth it, and they are all independent of a language to be
created; the language itself gives no visible gain today beyond the wish to have one. Two qualifications the owner
took along: a path as a block is the one thing only a language does well, and the language's gain is small, not nil.

Against the yardstick: nothing in the sketch leaves anything only in EasyEDA or only in someone's head. What moves is
where a pin number is decided, from the graph to the parts entry – a matter of what a diff shows, not of text.

### What held

- The round trip on today's led-bar is equal in both forms, 76 lines as a language and 250 as TOML; the line counts
  of the prototype above are right; `content()` keeps a file that is no JSON as bytes, so `hash_ignore` would stop
  reaching into a `.circuit` or `.toml` graph without a word; `graph_sha256` takes the file's bytes.
- The sizes, read as what Claude reads: the bell's language by hand is 7 608 bytes against 9 294 of the JSON, 18
  percent less; the TOML by hand 11 percent less. The translator's 52 percent hold for a file without comments, which
  nobody reads. The argument the other way is as weak: a handbook page for the language costs little next to chapter
  3, which circuit-design and hardware-change read already and which is 52 KB with its generated code list. Context
  decides nothing here; readability and the error rate of an edit do.

### Stale since `75d5c32`

- The graph's keys: `waive` is `accept` keyed by codes, `hints` is `accept` on the graph, `checks.pin_locks` and
  `checks.doc_pin_table` are `locks.pins` and `locks.doc_pin_table`, `checks.reverse_protect` is `source = "reversible"`
  on the component; `old_form()` in `design.py` refuses the old keys. The field table, the examples, `bell.circuit`
  (`waive P-1`) and `bell.toml` (`[checks.pin_locks]`) still write them; `test_translate.py` stops on today's led-bar
  with `KeyError: 'checks'`. The translator still runs, but writes the new keys as `set accept {…}` on every net,
  `set source "reversible"` and `set locks {…}` with pin numbers in place of `(locked)`.
- The codes: P-1 is STRUCT.entry; G-1 is STRUCT.name, STRUCT.pin, STRUCT.net, STRUCT.board, STRUCT.ref and
  STRUCT.purpose; G-2 is STRUCT.lock, G-4 is LVL.undefined, S-2 is SYNC.schematic. M-1 and M-6 stay.
- The bell was pushed after the cut; whether its graph is converted was not checked. The plan calls building the
  language size L, this sketch two steps of size M.

### Findings on the rules

1. A shared name is written only for a run of all pins of that name. The Pico of led-bar has eight GND pins, and AGND
   (pin 33) stands between them in the GND net, so the writer gives nine numbers: `U1.3 U1.8 … U1.AGND U1.38 U1.42`.
   The cause is the touchstone's "every list in its order", although the order of pins in a net means nothing to any
   check. Pins in a net are compared sorted, and `U1.GND` means all GND pins wherever they stand.
2. Under hash rule 1, "the arrangement counts for nothing" holds for comments and line breaks, not for a part or a net
   moved: `part R1` and `part R2` swapped give another canonical JSON. Today's JSON hash has the same property. The
   canonical form sorts components by designator, nets by name and the pins of a net, so that arrangement counts for
   nothing; the only order the engines read is the name of a net joined by bridges, after the first of them in the
   graph, which is cosmetic.
3. A name that is no word can only be written as its number: `U1."GND (USB)"` is refused, quotes read only in `pins`
   lines, and a `#` in a name starts a comment. That leaves out the pins a name helps most with, active-low ones such
   as `RST#` or `CS#`. Quoted references, or `#` as a comment only after white space.
4. The TOML form was given the JSON's structure as it is. `[[nets]]` as an array of tables may repeat a name, and
   edakit joins the fragments as a later `net GND …` line does: a path as a block in TOML too, three lines a fragment.
   Point 1 of the recommendation, "the only form that fixes all four points", does not hold against that form.
5. A lock stays a statement of its own. `(locked)` in the net, or a marker in the pin word, travels with the pin when
   an edit moves it, and STRUCT.lock has nothing left to find; `locks.pins` names the net the firmware expects apart
   from where the pin stands, which is what the check needs. The lock elsewhere is therefore no part of the third of
   the four points; only the cathode in GND is.
6. Loading hangs on the parts directory: `load_graph()` needs the entries, and a part without an entry and without a
   `pins` line is a parse error, where today a missing entry is a STRUCT.entry finding with everything else still
   checked. The reader should keep such a part's pins by number and leave the finding to the check.
7. A rewire through a parts entry means the graph is no longer the only place where connections are decided
   (handbook 3). Decision 4's second option, a generated `graph.json` committed and checked in the pre-commit hook, is
   the pattern of `firmware.json` and `stock.json`; "two files change with every edit" is true of the firmware
   contract today. M-1 reads diffs, so that option weighs more than the sketch gave it.
8. Under hash rule 1 a `#` comment never reaches the hash: regulatory statements stay in `purpose.notes`, which
   `KEEP_WHOLE` reads whole for M-6 – support, not legal advice.
9. Converting a project changes the circuit hash. `carry_signoffs` in `convert.py` and the gate's `rehashed` entry
   carry the sign-offs over when the files were the signed ones; the conversion does the same.
10. `edakit graph fmt` is needed by no step; the KiCad tool chain reads the Design, not the file; the conventions
    text `pin_reference` of a converted project is rewritten, as `convert.py` rewrites the `waive` convention today.

### Built in any case

Independent of the form, and of the language:

1. **Pins by name or role**, `U1.PD6`, `LED5.anode`, resolved through the parts entries with the reading rule of the
   table above: the number first, then the name of one pin, then the role of one pin, then a name or role several pins
   share, which stands for all of them. This is the correctness gain of the whole sketch: a model knows PD6 and anode
   from the datasheet and the firmware, while a symbol pin number is looked up, which is where wrong pins and reversed
   LEDs come from; and it makes the variants alike. `pins_by_role` and `pin_info` of the Design class are where it
   goes; findings name pins by the same rule.
2. **The pin map from the parts entry**, written only where the graph's differs; a part without an entry keeps its
   pins by number, and STRUCT.entry reports it (decision 3).
3. **The circuit hash over the data of the form as canonical JSON**, `hash_ignore` applied, names unresolved – the
   entries are in the hash already, so a rewire through an entry changes it –, components, nets and the pins of a net
   sorted (decision 2). Comments and arrangement count for nothing; regulatory text stays in `purpose.notes`.
4. **`edakit graph json`** prints the resolved graph with pin numbers, which is where a rewire through an entry
   shows; **`edakit graph convert`** moves a project once and carries its sign-offs over as `edakit convert` does.
5. **The lock stays `locks.pins`** (finding 5).

What remains of decision 1 is the form: TOML with names, or names and roles in today's JSON. TOML gives comments, a
third of the lines and a format every model and editor knows, at the price of a line editor for `block add` as
`write_place_rows` is one for `[place]`; JSON gives no new format and no comments.

### Hard without a language

What only a language does well; none of it is a correctness gain:

- a path as a block: a net written in pieces where the circuit goes, `net GND LED5.cathode` after the LED's step –
  in TOML only as `[[nets]]` fragments of three lines each, in JSON not at all;
- a part and a net as one line of bare words, `U1.PD6 R4.1` instead of `["U1.PD6", "R4.1"]`: the bell's circuit in 72
  lines of content against 211 in TOML;
- a shape error with its line before any check: `0..5,5 V` is refused at its line, `v = [0, 5,5]` is valid TOML and a
  STRUCT.net finding without one;
- `block add` by appending statements, where TOML needs an editor that keeps comments and arrays.

### What a language would need to be worth it

A language earns its cost through what a format cannot give. The sketch's language is a serialisation of the graph
with a nicer syntax, so it is a second format for the same data. It would be worth building when it has:

1. **Abstraction.** A building block as a statement, `use led STATUS in=GP8_LED gnd=GND`, expanded when the graph is
   loaded instead of copied in by `block add` – a change to the block then reaches every use, with what that does to
   the hash and the sign-offs written down; repetition, eight LEDs on `OUT0` … `OUT7` as one statement; values with
   their unit checked when read, `330Ω`, `0..5.5 V`; and variants as differences, `use ../../hardware/graph.circuit`
   with the statements that replace the main file's, with a hash model that says what a change of the main file does
   to a variant's sign-offs (decision 5).
2. **A schema that stands still.** Every key of the graph has a statement and `set KEY JSON` is not needed. Since
   `75d5c32` the graph gained `accept`, `locks`, `source`, `instrument`, `load_min_ohm`, `matrix` and
   `purpose.radio`; in a format a new key is free, in a language each is a syntax decision.
3. **Evidence.** `evals/add-led` in the language and in the form, three runs each with Sonnet (maker-coverage
   FT-24): the language is edited at least as reliably.
4. **The tooling a format gets for free**, as preconditions rather than costs: highlighting on GitHub and in
   editors, a formatter, line-exact errors, one reader every tool uses and one writer for everything that writes the
   graph.

Thought further on the owner's request in [circuit-dsl.md](circuit-dsl.md): whether a fitting language exists
already, what one of edakit's own would have to be able to do, on which basis, and when.

## Decisions

Taken on 2026-10-31 in a decision round after the review. "Accepted" is the owner's yes to the recommendation;
"decided by Claude" marks what the owner left to Claude and confirmed. The language itself is deferred – the owner's
conclusion of the review – until it offers what a format cannot (the section Review 2026-10-31 says what that is).

| # | Question | Decision | Status |
| --- | --- | --- | --- |
| 1 | Which form edakit builds for the circuit | TOML with names, `hardware/graph.toml`: comments, a third of the lines, a format every model knows and GitHub highlights; `block add` gets a line editor that keeps comments and arrays, as `write_place_rows` is one for `[place]`; names and roles in today's JSON was the alternative | accepted |
| 2 | What the circuit hash covers | the data of the form as canonical JSON, `hash_ignore` applied, names unresolved (the parts entries are in the hash already), components by designator, nets by name and the pins of a net sorted: comments and arrangement count for nothing, every change of data does; regulatory text stays in `purpose.notes` | accepted |
| 3 | Where a part's pin map comes from | from its parts entry; the form states it only where the graph differs; a part without an entry keeps its pins by number, and STRUCT.entry reports it instead of a loading error | accepted |
| 4 | A resolved JSON beside the form | yes: generated, committed and checked in the pre-commit hook as `firmware.json` is, so that every rewire through a parts entry shows as pin numbers in the diff M-1 reads; two files change with every edit | accepted |
| 5 | How the variants are written | four complete files, as today; a variant that names the main file and lists its differences is something a later language would have to offer with its hash model | accepted |
| 6 | Which pin names a form may use | the symbol's names and the roles, as STRUCT.entry and SYNC.schematic hold them; the Nano's swapped labels get a comment; no alias per pin | accepted |
| 7 | A net in fragments (review, finding 4) | no: a net is one table, `[nets.GND]` once with all its pins, one way to write a net and one place a reviewer reads it; a path as a block stays the task of a later language | accepted |

Decided by Claude, confirmed: (1) a pin word is read as the number first, then the name of one pin, then the role of
one pin, then a name or role several pins share, which stands for all of them; the writer takes the first word that
reads back as exactly the pins it means, else the number; findings name pins by the same rule. (2) The pins of a net
are compared sorted; `U1.GND` means all GND pins wherever they stand. (3) Doubled names and unknown pins are refused
when the graph is loaded, not translated; a part without an entry keeps its numbers for STRUCT.entry to report.
(4) TOML keys components, nets and cables by designator and name and has no null; `locks.pins` stays a table of its
own. (5) The source is `hardware/graph.toml`, named by `[project] graph`; the generated, resolved file keeps the name
`hardware/graph.json`, with pin numbers and the wrapper `{"graph": …}`, so that project scripts that read the graph as
JSON keep running. (6) `edakit graph convert` translates a project once, carries its sign-offs over as `edakit convert`
does and rewrites the convention `pin_reference`; `edakit graph json` prints the resolved graph; `edakit graph fmt` is
dropped. Deferred with the language: the extension `.circuit`, `(locked)` and `lock PIN NET`, `set KEY JSON`, a later
net line that adds pins, quoted text over several lines.

What both forms share has a plan of its own, [circuit-language-plan.md](circuit-language-plan.md): nine steps, built
with add-feature when the owner asks for them. The prototypes of this folder stay the record of the sketch at
`75d5c32`; the round trip they ran moves into the plan's tests.

## Sources

- edakit at `75d5c32`: [design.py](../../../edakit/design.py) (`load_graph`, `entry_key`),
  [checks.py](../../../edakit/checks.py) (`check_structure`, G-1), [gate.py](../../../edakit/release/gate.py)
  (`content`, `state_files`, `state_hash`, `KEEP_WHOLE`, `header`), [block.py](../../../edakit/block.py) (`add`,
  `plan`, `write_json`), [scripts.py](../../../edakit/scripts.py) (the data name `graph`),
  [sim/run.py](../../../edakit/sim/run.py) (`.cir`), handbook [3](../../../handbook/03-hardware-graph.md) and
  [4](../../../handbook/04-parts-database.md) (pins, roles), the skills
  [circuit-design](../../../skills/circuit-design/SKILL.md),
  [hardware-change](../../../skills/hardware-change/SKILL.md), [own-part](../../../skills/own-part/SKILL.md) and
  [new-project](../../../skills/new-project/SKILL.md), the example `tests/fixtures/led-bar`.
- The Christmas bell at `f56b463`: `hardware/graph.json` and `hardware/parts/`, `variants/{smd,tht,esp32}/hardware/`
  with their `parts/`, `src/firmware/buttons.ino` (the Arduino pins D2 … D12).
- The prototype: [prototypes/circuit-language](prototypes/circuit-language/) – `translate.py`, `test_translate.py`,
  `bell.circuit`, `bell.toml`.
