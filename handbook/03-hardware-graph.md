# 3 The hardware graph

For you when you write or change a project's circuit: after this chapter you can write the graph, read its findings, and
keep the firmware contract and the requirements file beside it. The short way: [Say what it must
do](../docs/steps/03-say-what-it-must-do.md) and [Design the circuit](../docs/steps/04-design-the-circuit.md).

**In short.** The graph, `hardware/graph.toml`, is the one place where parts, values and connections are decided:
components, nets with their voltage ranges, cables, every pin by name or role (the format, 3.1). `edakit check` checks
it in under a second; each finding has a code and a severity – an error is fixed, a warning accepted with its reason
(rule checks, 3.3). A change starts in the graph, never in the schematic or the PCB (working rules, 3.4). Beside the
graph stand what the firmware must know (the firmware contract, 3.5) and what the circuit must do, each requirement
approved by you (requirements, 3.6).

The graph is a pin-level netlist. It is the **only** place where parts, values and connections are decided. It is
TOML, `hardware/graph.toml`, with pins by name or role and comments where a reader needs the reason. The older form,
JSON in `hardware/graph.json`, is kept until the project converts; both read to the same graph. `[project] graph` in
edakit.toml names the file (10.1). Example: [the Christmas bell's
graph](https://github.com/tgd1975/automatic_christmas_bell/blob/main/hardware/graph.json) (JSON). The snippets below
come from the [test project](../tests/fixtures/led-bar/hardware/graph.json), in TOML as `edakit graph convert` writes
it, shortened.

## 3.1 Format

```toml
# The hardware graph (handbook 3.1): components, nets and cables keyed by designator and name, pins by name
# or role through the parts entries. edakit graph json writes the resolved graph beside it (graph.json).
name = "led-bar"
version = "1.0"
date = "2026-10-25"
description = """\
  Example for edakit: a Raspberry Pi Pico 2 drives eight LEDs through a TLC5916 constant-current sink; 5 V input \
  with reverse-polarity diode, one push button."""

[purpose]
use = "private"
market = "EU"
notes = "An example board for edakit, built for testing, not sold or given away."

[components.J1]
type = "connector"
label = "5 V input (JST PH, top entry)"
part = "B2B-PH-K-S(LF)(SN)"
lcsc = "C131337"
bom = false
source = "reversible"

[components.U2]
type = "ic"
label = "TLC5916 8-channel constant-current LED driver"
part = "TLC5916IDR"
lcsc = "C90107"
nc = ["SDO"]
notes = "I_OUT = 15 x 1.26 V / R1 = 9.45 mA per output."

[components.R2]
type = "resistor"
label = "OE pull-up 10 k: LEDs off until the firmware runs"
part = "0805W8F1002T5E"
lcsc = "C17414"
value = "10k"

[nets."+5V"]
pins = ["D1.cathode", "U1.VSYS", "C2.1", "D2.anode", "D3.anode", "D4.anode", "D5.anode", "D6.anode", "D7.anode",
        "D8.anode", "D9.anode"]
v = [0, 5.5]
notes = "Behind D1: module VSYS and all LED anodes."

[nets.GND]
pins = ["J1.2", "U2.GND", "R1.2", "C1.2", "C2.2", "SW1.C", "U1.GND", "U1.AGND"]
v = [0, 0]

# GP2 and GP3 shift into the driver on SPI0 (the pins locked below)
[nets.LED_CLK]
pins = ["U1.GP2", "U2.CLK"]
v = [0, 3.4]
fn = "spi.sck"
fn_bus = "LED"
accept."LVL.undefined" = """\
  Floating until the firmware runs, but harmless: R2 holds OE high, so no output can switch on."""

[cables.W1]          # a cable to a second board: J2 there, J1 here
from = "J2"
to = "J1"
pins = {1 = "1", 2 = "2"}
r_ohm_per_wire = 0.065

[locks.pins]
"U1.GP2" = "LED_CLK"
"U1.GP3" = "LED_SDI"
```

### Tables, keys and comments

Components, nets and cables are tables keyed by designator and name (`[components.U2]`), read in the order of the file;
a name with more than letters, digits, `_` and `-` stands in quotes (`[nets."+5V"]`). Every other key is the JSON's; a
map is a table of its own (`[purpose]`, `[locks.pins]`), inline (`pins = {1 = "1", 2 = "2"}`) or dotted keys
(`accept."LVL.undefined" = "…"`). A component states no `pins`: its parts entry gives numbers and names, and a pin map
is written only where the graph's differs. `#` starts a comment – the reason a reader needs beside the wiring.

A long text runs over several lines as `"""\`, where a line-ending backslash joins the next line with the blank before
it. A key or table twice is an error with its line, and TOML has no null. A net is one table with all its pins,
`[nets.GND]` once; an array of tables, `[[nets]]`, is refused. A graph without component or net tables has none yet,
as in a new project (2.7).

### The JSON form

The same graph in JSON, as a project that has not converted keeps it and as edakit generates it beside a TOML graph
(below) – there with pin numbers and every component's pin map:

```json
{"graph": {
  "name": "led-bar", "version": "1.0", "date": "2026-10-25", "description": "…",
  "components": [
    {"designator": "U2", "type": "ic", "label": "TLC5916 8-channel constant-current LED driver",
     "part": "TLC5916IDR", "lcsc": "C90107", "board": "main",
     "pins": {"1": "GND", "2": "SDI", "3": "CLK", "4": "LE(ED1)", "5": "OUT0", "…": "…", "16": "VDD"},
     "nc": ["14"], "notes": "I_OUT = 15 x 1.26 V / R1 (D-9)"},
    {"designator": "R2", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}},
    {"designator": "U1", "type": "microcontroller", "lcsc": "C41407547", "bom": false, "pins": {"…": "…"}},
    {"designator": "J1", "type": "connector", "lcsc": "C131337", "bom": false, "pins": {"1": "1", "2": "2"},
     "source": "reversible"}
  ],
  "nets": [
    {"name": "+5V", "pins": ["D1.1", "U1.39", "C2.1", "D2.1"], "v": [0, 5.5], "notes": "behind the reverse diode"},
    {"name": "LED_CLK", "pins": ["U1.4", "U2.3"], "v": [0, 3.4], "fn": "spi.sck", "fn_bus": "LED",
     "accept": {"LVL.undefined": "floating until the firmware runs, harmless: OE is pulled high"}}
  ],
  "cables": [
    {"name": "W1", "from": "J2", "to": "J1", "pins": {"1": "1", "2": "2"}, "r_ohm_per_wire": 0.065}
  ],
  "locks": {"pins": {"U1.4": "LED_CLK", "U1.5": "LED_SDI"}}
}}
```

### Fields

The fields are the same in both forms; the table writes them as the JSON does (`bom: false` is `bom = false` in TOML):

| Field | Meaning |
|---|---|
| `name`, `version`, `date`, `description` | the graph's name and state – the gate run, the firmware contract (3.5) and an own part's datasheet (4.5) cite `version` and `date` |
| `designator` | as on schematic, PCB and silkscreen; in TOML the key of the component's table |
| `type` | rough class for the generated template layout and the schematic blocks: `microcontroller`, `module`, `ic`, `transistor`, `connector`, `regulator`, `diode`, `led`, `resistor`, `capacitor`, `inductor`, `button`, `switch`, `potentiometer`, `audio`, `testpoint`, `battery_holder`, `fuse`; any other type is the parts entry's `kind` itself (`relay`, `motor`, `crystal` …) – STRUCT.identity holds the type to the kind |
| `label` | what the part does on the board, in a few words; `edakit schematic draw` titles its blocks with it, `edakit graph show` prints it |
| `lcsc` | the LCSC number – identifies symbol, footprint, parts entry and the BOM line |
| `part` | the manufacturer part number; without `lcsc` it names the parts entry (its `mpn`) – a part bought elsewhere (chapter 4); with `lcsc` it must name the entry's `mpn` too (STRUCT.identity) |
| `pins` | pin number → pin name, **with the pin numbers of the EasyEDA/LCSC symbol of exactly this part**; optional – without it the component takes its parts entry's numbers and names. Where it is written, the names must equal the parts entry (STRUCT.entry). A part without an entry and without `pins` takes the numbers its nets and `nc` use, and STRUCT.entry reports the missing entry |
| `nc` | pins deliberately unconnected, by number, name or role (below); every pin is in exactly one net or in `nc` |
| `board` | which board the part is on (a key of `[boards]` in edakit.toml); may be omitted with one board. On a bought board (`bought = true`) or a hand-wired one (`wired = true`, 4.5) every part has `bom: false` (STRUCT.board) |
| `value` | shown in the BOM ("10k", "100nF"); STRUCT.identity holds it to the entry's `value_ohm`, `value_f` or `value_h` |
| `bom: false` | the part is placed on the PCB but not in the BOM for assembly (hand-soldered, bought separately); `edakit order` puts it into the cart of its supplier (8.4) |
| `supplier` | for a part bought separately: the supplier whose cart it goes into (default: the first of its parts entry's `order`, else `lcsc` with an LCSC number) |
| `spare` | pieces ordered on top for the whole order (`edakit order`), e.g. `1` for an LED that is easily lost |
| `easyeda_device` | for parts without LCSC number (bare test pads): `{name, uuid, libraryUuid}` of an EasyEDA library device |
| `verify` | an open question about pins/polarity that the library does not settle; blocks the release (PARTS.verified) until resolved |
| `accept` | on a component or net: `{code: reason}` – a finding accepted on purpose, printed with its reason in every report; the key a code (`LVL.undefined`), a code with its grade (`LIM.i/margin`) or topic (`GEO.spacing:paste`) – 14.2 |
| `source` | `"reversible"` on a connector or holder that may be plugged in the wrong way round: PATH.reverse follows what it reaches reversed; it is also a power input for the hints |
| `config`, `states` | the configuration the part runs in – one of its entry's `configs` (4.1; STRUCT.entry) –, and where the simulation holds its outputs: `{"<pin number or name>": "high" | "low" | "off"}` over the pins' `state` in the entry, for a part with behaviour `logic` (5.1) – an alert asserted (`{"Alert": "low"}`), a modem line the host sets; only output and bidirectional pins, `high` not on an open-drain output (STRUCT.entry) |
| `off_board` | `true` on a connector whose wires leave the board without a cable in the graph – a terminal for a footswitch, a jack: its signal nets count as leaving the board, as a cable's do (REQ.missing/leave), and it suggests the domain cables |
| `strip` | on an LED strip (parts kind `led_strip`): its length, `{"length_m": 5}` or `{"pixels": 300}` – the pixels are length × the entry's `pixels_per_m`, rounded; STRUCT.entry/strip without it. The simulation makes a ladder of it (5.1); a strip off the board sits on a board of its own with `wired = true` (4.5), joined by cables |
| `notes` | free text; cite decision numbers here |
| net `v` | `[min, max]` voltage over **all** intended operating states (all supply variants, reversed supply, unloaded) |
| net `bus` | `"i2c"` marks SDA and SCL nets whose pins do not say so (MCU pins called GP4): REQ.missing checks them |
| net `fn` | the function the net needs from its MCU pin: `pwm`, `adc`, `spi.sck`, `spi.tx`, `spi.rx`, `spi.cs`, `i2c.sda`, `i2c.scl`, `uart.tx`, `uart.rx`, `i2s.bclk`, `i2s.ws`, `i2s.sd`, `can.tx`, `can.rx`, `onewire`, `usb.dp`, `usb.dn` – REQ.function holds it to the pin's `functions` (4.1); without `fn` the pin is a plain GPIO (bit-banged, PIO) |
| net `fn_bus` | a name the nets of one bus share (`"LED"` on SDI and CLK): REQ.function wants them on one peripheral instance (`spi0`, not `spi0` and `spi1`) |
| net `instrument`, `load_min_ohm` | an instrument comes in on the net – `"pickup"` or `"piezo"` – and the least load it wants (`1e6` for 1 MΩ, from the instrument's data): REQ.value/instrument holds the resistors and the inputs' `z_in_ohm` on it in parallel to it; the net suggests the domain guitar |
| net `signal` | `true`: the net is part of an analog signal path (audio, an effect, a measurement): in the simulation a switch, relay contact or pot whose sides are both on such nets – or on an `instrument` net – keeps them at one DC level, within 10 mV in every scenario (REQ.value/switch) |
| net `isolated` | `true` on a net of a loop of its own – a MIDI-in loop, the far side of an optocoupler: its range `v` is that loop's, not against the board's ground; LIM.v holds a pin there to it only where its part has a ground pin on an isolated net too, and the simulation does not compare the net with its range (LIM.declared) |
| net `ac` | `true` on a net that carries a sine around 0 V – the mains, its divider's taps: its `v` is the peaks (230 V + 10 %: `[-358, 358]`). AC nets move together, one source in phase: LIM.v holds a part or pin with an AC rating (`v_rms_max_v`, 4.1) there to the rms, peak / √2, in place of its DC rating, and a resistor or varistor between two AC nets to the difference of their like ends |
| net `matrix` | `"row"` or `"col"` of a key matrix: every key reaches the other side through a diode, all diodes the same way (REQ.missing/matrix, REQ.forbidden/matrix) |
| net `pwm_hz` | the PWM frequency of a net with `fn: "pwm"` – a number, or `[min, max]` for one that changes (a buzzer playing notes): two PWM nets on one slice need the same fixed frequency (REQ.function) |
| net `clock_hz` | the clock a bus runs at, on its clock line – `fn: "spi.sck"` or an I2C SCL line: at most the highest clock of every device on it (limits `f_sck_max_hz`, `f_scl_max_hz`) and, on I2C, the speed its pull-ups allow with the bus capacitance known (LIM.range/clock); the firmware contract carries it (3.5, `bus_speed`) |
| `cables` | wires between boards: connector pins joined 1:1; the cable is no part. Its resistance per wire feeds the simulation: `r_ohm_per_wire` (measured or from the cable's data, with or without `length_m`), or `length_m` with the wire's `awg` or `mm2` – copper at 20 °C, as the routed tracks (2 m of AWG 28: 0.42 Ω per wire, 50 mΩ without either); `l_nh_per_m` adds the wire's inductance, which a transient run sees (the LC spike when a cable is plugged in), `c_pf_per_m` its capacitance, which an I2C bus through it adds to its pins' (the bus speed its pull-ups allow, LIM.range/clock) and an AC run puts between each wire and the cable's ground wire (an instrument cable loading a pickup, 5.2, AC runs); its rating per wire (`i_max_a`, optional, from the datasheet of the wire itself – edakit derives none from the gauge) holds the simulated current of every wire (LIM.i/cable); a cable that carries current without it is named by `edakit check --coverage` with its highest current and the loss per metre of wire, I² × R (3.3); to an LED strip `at_m`, the place along the strip where the cable's wires land – each on the rail of the strip pin it names: an injection point (5.1); STRUCT.net checks the keys |
| `accept` (graph) | findings accepted for the whole graph, mostly hints taken care of: `{"HINT.bulk": "C1 1000 µF next to J1"}`, for one place only `{"HINT.bulk J2": "…"}` – chapter 14.3 |
| `layout` | the hand-over to the layout: `fixed`, `edge`, `near`, `loops`, `apart` (`[{a, b, min_mm, what}]`: two nets whose copper keeps at least `min_mm` apart on every layer, measured on the Gerber files – GEO.spacing/apart), `notes` – chapters 7.4 and 14.1; STRUCT.ref checks that the names exist |
| `purpose` | what the board is for: `use` (`private` – built for oneself, `gift` – given away, `sale` – sold, also in small series), `market` (`"EU"`), `country`, optional – the member state it is used in, ISO 3166-1 alpha-2 (`"AT"`), whose national rules the regulatory review names (15.6; without it Germany's; a code that is no member state of the EU is STRUCT.purpose) –, `notes` (what it is, who uses it), and for a part that transmits `radio`, optional – how its firmware uses it: `{"U1": {"bands_mhz": [[2412, 2472]], "max_dbm": 17, "notes": "Wi-Fi channels 1–13"}}` (the bands it keeps, each within the part's `bands_mhz` (4.1), and optionally the conducted power it keeps) or `{"U1": "off"}` (LIM.band, LIM.eirp) – it decides which rules the regulatory review applies (chapter 15); part of the circuit hash |
| `ground` | name of the ground net (default `GND`) – the checks, the simulation and the schematic's flags use it; STRUCT.ref checks that the net exists |
| `grounds` | further nets that are ground on purpose, `["AGND"]` – an analog ground joined at one point, an isolated side: their `ground` pins pass PATH.unfed (default: none) |
| `locks` | what the firmware relies on: `pins` (`{"U1.4": "LED_SDI"}` – pins on their nets, STRUCT.lock), `doc_pin_table` (`{component, file, prefix, regex}` – a pin table in the documentation, STRUCT.lock); part of the circuit hash, STRUCT.ref checks the names |
| `conventions` | how the graph is written, for whoever reads it: `pin_reference`, `v`, `accept` in the example – free text no check reads (3.2) |

### A pin by number, name or role

Wherever the graph names a pin – the `pins` of a net or a cable, `nc`, `locks.pins`, the ends of `layout.loops` – it
may write the symbol's number (`U1.9`), the name of the pin map (`U1.GP6`) or the role the parts entry gives for the
config the part runs in (`D2.anode`; configs, 4.1). edakit reads a word as the pin number first, then the name of one
pin, then the role of one pin. Last comes a name or role several pins share, which stands for all of them: `U1.GND`
is every GND pin of the Pico, wherever they stand in the net, `SW1.a` both pins of a button's side.

Where one pin is meant – a loop end, a cable's wire – a word that names several is STRUCT.pin. So is a word that names
no pin of its part, reported with the net or place it stands in; the rest is checked all the same. The checks, the
simulation, the schematic, the hand-over and the firmware contract read the numbers the words stand for.

A finding names a pin the other way: by the first of its name and role that names only this pin, the number in
brackets where they differ. The name comes first on an IC or a module, whose names are the datasheet's, the role
elsewhere – `D2.anode (1)`, since a symbol's name may mislead. It gives the number for a name with a blank (the Pico's
TP1, "GND (USB)"), a word that says no more than the number (`R4.1`, a connector's role `pin3`) and a shared name. A
name that misleads stays the symbol's, with a note: the Nano whose symbol labels pin 14 PB4, although D11 is PB3 on
the chip, is written `U1.PB4`. There is no alias per pin.

### The JSON generated beside a TOML graph

`edakit graph json` prints the resolved graph: `{"graph": …}` as a JSON graph has it, pin numbers wherever a pin is
named, every component's pin map (its entry's where the graph has none), the lists in the order of the file.
`edakit graph json --write` keeps it beside the TOML as `hardware/graph.json`, committed with it. A rewire through a
parts entry – a role corrected, `D2.anode` now on pad 2 – changes no line of the TOML but shows in the generated file
as pin numbers, in the diff the review M-1 reads.

So every edit of the circuit changes two files, as with the firmware contract (3.5): the TOML, then
`edakit graph json --write`. The pre-commit hook runs `edakit graph json --check`, which exits 2 with what differs,
keyed by designator and net, when the committed file no longer matches (the working rules, 3.4). The generated file is
derived and never edited; `--write` refuses to write over a JSON graph, which is the source itself. The circuit hash
(8.2) and the scripts' data name `graph` (8.6) take the TOML. Project scripts and tools that read the graph as JSON
read the generated file as before.

### Moving a project to TOML

`edakit graph convert` translates a JSON graph once; `--dry-run` prints the TOML and what would change. It writes
`hardware/graph.toml` – components, nets and cables keyed in the order of the JSON, pins by the word rule above (a
shared name, `U1.GND`, where all its pins stand in the net), pin maps left out where they equal the entries', long text
over several lines, the convention `pin_reference` rewritten (3.2). It sets `[project] graph` in edakit.toml, its
comment kept, and writes the resolved `hardware/graph.json` in place of the source.

A graph with null, a name twice or a pin that names none is refused with
what to fix in the JSON; `edakit check` names them too. Nothing is written unless the TOML reads back to the same
graph. Its only comments are the two lines at the top: the reasons stay in `notes`, comments come by hand.

The circuit hash changes once (8.2). Where the files were the signed ones, the sign-offs of scope `circuit` keep
counting: the new hash goes into the sign-off file, the old and the new into `rehashed`. Two things follow the new hash
once, by hand. With `[firmware]`, the contract's `state_sha256`: convert says so; run `edakit firmware` and commit the
contract, else its `--check` in the hook fails. The project scripts that read `graph` (8.6) show as outdated until
`edakit run <name>` runs them or `edakit scripts stamp <name>` records them as they are – only the hash of what they
read changed.

## 3.2 Conventions that save trouble

- **Pins by role or name, numbers from the EasyEDA symbol.** Write a pin as the datasheet and the firmware know it:
  the role where the part has one (`D2.anode`, `Q1.gate`), the name on an IC or a module (`U1.GP6`). A number looked
  up is where wrong pins and reversed LEDs come from. The parts entry says which number a word stands for, and the
  numbers are the EasyEDA symbol's, not the datasheet's. They usually agree; for LEDs and diodes they often do not
  (anode = 1 for one LED, = 2 for another of the same shape). Write the roles into the parts entry; code that needs
  "the cathode" asks for the role, never for the pin name.

  `edakit part import C2297` reads the numbers from the library without EasyEDA (finding parts, 4.2) and keeps the
  symbol, so STRUCT.entry compares the pins with it. Inside EasyEDA, `edakit schematic create --only U3` and
  `easyeda_schematic_component_pins` show the placed symbol.
- **The graph says how it names pins.** `conventions.pin_reference` tells a reader how to read `U1.GP6`. In a graph by
  names and roles it is the text `edakit graph convert` writes, `"'<designator>.<pin>' with the pin's name or role,
  else its symbol number – the parts entry says which pin that is"`; in a graph by numbers `"'<designator>.<pin>' with
  the pin numbers of the EasyEDA/LCSC symbol"`. No check reads it; it keeps the graph readable without this handbook.
- **Net names are stable identifiers** used by firmware, simulation config and docs. Rename deliberately.
- **Voltage ranges are worst case.** LIM.v compares `v` with the pin limits, and the simulation checks every scenario
  against it. Think of the unloaded supply, the reversed supply, a programming cable plugged in at the same time.
- **Decisions in the graph.** "Why 2 k?" – `notes = "D-9: I_OUT = 9.45 mA"`; the decision log has the reasoning. A
  `#` comment in a TOML graph says what a reader needs beside the wiring ("LED 1 of the bar"). No check reads it and
  the circuit hash leaves it out (8.2), so a decision or a statement for a review goes into `notes` or `purpose.notes`.
- **One part, one LCSC number.** A footprint variant is a different part.

## 3.3 Rule checks (stages P and G)

`edakit check` runs in well under a second; put it into the pre-commit hook and CI. Every finding carries a code
`ENGINE.relation`: the engine that found it and the relation it found violated – `LIM.v` a voltage beyond its limit,
`REQ.missing` a part without what it requires. It has a severity (error, warning, pending, note), sometimes a grade
(`margin`, `unknown`, …) and a topic (`REQ.missing:cc`); the catalog (14.2) has the model. What a code holds, why, what
to do and the sources: `edakit rules` for the engines and their codes, `edakit explain LIM.v` for one. Every code that
fails is explained once below the findings. `edakit domains` shows which domains of rules are on for the project (14.2).

### The codes

The codes of the graph engines, generated from the catalog (`edakit/catalog/codes.toml`). LIM and LVL judge the
simulation's values in stage E as well (the simulation's checks, 5.3); the hints are in 14.3:

<!-- edakit:generated table STRUCT LIM LVL REQ PATH PARTS DOCS -->
| Code | Title | Severity |
| --- | --- | --- |
| [`STRUCT.name`](../docs/catalog/struct.html#STRUCT.name) | names unique | error; replaces G-1 |
| [`STRUCT.pin`](../docs/catalog/struct.html#STRUCT.pin) | every pin in one net or nc | error; replaces G-1 |
| [`STRUCT.net`](../docs/catalog/struct.html#STRUCT.net) | nets well-formed | error; replaces G-1 |
| [`STRUCT.board`](../docs/catalog/struct.html#STRUCT.board) | every part on a board | error, wired: note; replaces G-1 |
| [`STRUCT.ref`](../docs/catalog/struct.html#STRUCT.ref) | settings name what exists | error; replaces G-1, G-16, G-25 |
| [`STRUCT.purpose`](../docs/catalog/struct.html#STRUCT.purpose) | purpose stated | error; replaces G-1, G-25 |
| [`STRUCT.lock`](../docs/catalog/struct.html#STRUCT.lock) | pins where the firmware expects them | error; replaces G-2 |
| [`STRUCT.domain`](../docs/catalog/struct.html#STRUCT.domain) | suggested domains on | note |
| [`STRUCT.edakit`](../docs/catalog/struct.html#STRUCT.edakit) | the edakit the project needs | note |
| [`STRUCT.entry`](../docs/catalog/struct.html#STRUCT.entry) | graph pins = parts entry | error, symbol: error, declared: note, strip: warning; replaces P-1 |
| [`STRUCT.identity`](../docs/catalog/struct.html#STRUCT.identity) | graph and entry name the same part | error; replaces P-6 |
| [`STRUCT.prefix`](../docs/catalog/struct.html#STRUCT.prefix) | designator prefix fits the kind | warning; replaces P-6 |
| [`LIM.v`](../docs/catalog/lim.html#LIM.v) | voltage within its limit | error, polarized: warning, inject: warning, powered: warning, order: warning; replaces G-3, G-8, E-2, E-5 |
| [`LIM.hazardous`](../docs/catalog/lim.html#LIM.hazardous) | hazardous voltage recognised, not checked | error |
| [`LIM.i`](../docs/catalog/lim.html#LIM.i) | current within its limit | error, margin: warning, cell: warning, supply_pin: warning, charge: warning, pin: warning, switching: warning, cc: warning, strip: warning, cable: warning; replaces G-17, E-2, E-3, E-5 |
| [`LIM.p`](../docs/catalog/lim.html#LIM.p) | power within its limit | error; replaces E-2 |
| [`LIM.t`](../docs/catalog/lim.html#LIM.t) | temperature within its limit | error; replaces E-2, E-3 |
| [`LIM.range`](../docs/catalog/lim.html#LIM.range) | supplied inside the operating range | error, opamp: warning, gate: warning, adc: warning, clock: warning, min_load: warning, photomos: warning, cc: warning, strip: warning; replaces E-3, E-5 |
| [`LIM.declared`](../docs/catalog/lim.html#LIM.declared) | net inside its declared range | error; replaces E-3 |
| [`LIM.backfeed`](../docs/catalog/lim.html#LIM.backfeed) | no supply fed backwards | error; replaces E-3 |
| [`LIM.eirp`](../docs/catalog/lim.html#LIM.eirp) | radio power within the band's limit | note, unknown: note; replaces G-24 |
| [`LIM.band`](../docs/catalog/lim.html#LIM.band) | transmitter in the EU bands | error, firmware: note; replaces G-25 |
| [`LVL.undefined`](../docs/catalog/lvl.html#LVL.undefined) | input defined while the firmware is not running | error, nc: warning, open_drain: warning, analog: warning; replaces G-4 |
| [`LVL.contention`](../docs/catalog/lvl.html#LVL.contention) | one driver per net | error; replaces G-5 |
| [`LVL.boot`](../docs/catalog/lvl.html#LVL.boot) | strapping pins at their level at reset | error; replaces G-12 |
| [`LVL.threshold`](../docs/catalog/lvl.html#LVL.threshold) | logic levels reach the thresholds | error; replaces E-3 |
| [`LVL.direction`](../docs/catalog/lvl.html#LVL.direction) | outputs only on pins that drive | error; replaces E-3 |
| [`REQ.missing`](../docs/catalog/req.html#REQ.missing) | what a part requires is there | error, pin: warning, balance: warning, usb_data: warning, leave: warning, matrix: warning, termination: warning, clamp: warning, feedback: warning; replaces G-6, G-11, G-13, G-14, G-18 |
| [`REQ.value`](../docs/catalog/req.html#REQ.value) | what a part requires is in range | error, pin: warning, adc: warning, instrument: warning, gain: warning, termination: warning, failsafe: warning, window: warning, feedback: warning, switch: warning, pd_request: warning, load: warning, min_load: warning, bias: warning, esr: warning, cc: warning; replaces G-11, G-14 |
| [`REQ.forbidden`](../docs/catalog/req.html#REQ.forbidden) | what must stay apart is apart | error, pin: warning, address: warning, btl: warning, matrix: warning, termination: warning; replaces G-14 |
| [`REQ.function`](../docs/catalog/req.html#REQ.function) | pin functions | error, uart: warning; replaces G-15 |
| [`PATH.reverse`](../docs/catalog/path.html#PATH.reverse) | reverse polarity blocked | error, polarized: warning; replaces G-10 |
| [`PATH.unfed`](../docs/catalog/path.html#PATH.unfed) | every supply pin reached by a supply | error; replaces G-16 |
| [`PATH.ground`](../docs/catalog/path.html#PATH.ground) | ground pins on ground | error; replaces G-16 |
| [`PARTS.verified`](../docs/catalog/parts.html#PARTS.verified) | parts signed | pending, device: warning; replaces G-9 |
| [`PARTS.stock`](../docs/catalog/parts.html#PARTS.stock) | parts orderable | error, margin: warning, stale: pending, unchecked: note, other_maker: warning; replaces P-4, F-2 |
| [`PARTS.supplier`](../docs/catalog/parts.html#PARTS.supplier) | supplier per part | warning; replaces P-5 |
| [`PARTS.fact`](../docs/catalog/parts.html#PARTS.fact) | required facts given | note, lead: pending, functions: note, hot_loop: warning, radio: note, rohs: note, mpn: error, other_maker: warning, pixels_per_m: warning, i_pixel_a: warning, r_vdd_ohm_per_m: warning, r_gnd_ohm_per_m: warning, reach: note; replaces P-7, G-15, G-18, P-11, P-12 |
| [`PARTS.schema`](../docs/catalog/parts.html#PARTS.schema) | parts entries well-formed | error; replaces G-14, G-18, G-24, P-11 |
| [`PARTS.library`](../docs/catalog/parts.html#PARTS.library) | copy of the parts library current | note, newer: note, draft: note |
| [`PARTS.footprint`](../docs/catalog/parts.html#PARTS.footprint) | footprint data complete | error; replaces P-9 |
| [`DOCS.quote`](../docs/catalog/docs.html#DOCS.quote) | documents quote the design data | error; replaces G-19 |
| [`DOCS.file`](../docs/catalog/docs.html#DOCS.file) | requirements file named | pending |
| [`DOCS.ref`](../docs/catalog/docs.html#DOCS.ref) | requirement references resolve | error, margin: warning, draft: warning; replaces G-20 |
| [`DOCS.need`](../docs/catalog/docs.html#DOCS.need) | accepted need has a requirement | error, draft: warning; replaces G-21 |
| [`DOCS.evidence`](../docs/catalog/docs.html#DOCS.evidence) | requirement has evidence | error, draft: warning; replaces G-22 |
| [`DOCS.draft`](../docs/catalog/docs.html#DOCS.draft) | draft not approved | warning, draft: warning; replaces G-23 |
| [`DOCS.derived`](../docs/catalog/docs.html#DOCS.derived) | requirement names who stated it | warning |

Rule, why, fix and sources of each: `edakit explain CODE`, or the code on its page of the catalog.
<!-- edakit:end -->

### 0 Ω bridges

A resistor whose parts entry has `value_ohm: 0` is copper – the usual way to cross a track on a board with all tracks
on one side. The nets it joins are one net for the engines LVL, REQ, PATH and the fuse limits of LIM.i: a pull-up
behind a bridge holds its input, a capacitor to a ground net behind a bridge decouples, two outputs on either side
clash. A finding names the joined net after the ground net if that is one of them, else after the first of them in
the graph; an `accept` on any of them counts.

STRUCT, the voltages of LIM.v, PARTS and the hot loop of REQ.missing see every net and the bridge as the graph has
them; the pads of `layout.loops` lie on one net of the graph. `edakit check` lists the joined nets above its last
line:
`joined by 0 Ω bridges, checked as one net: GND = GND_B (R11); 3V3 = 3V3_B = 3V3_C (R10, R13)`.

### Severities

A finding is an `error` (must be fixed), a `warning` (the gate wants it accepted in the sign-off file, 8.2), `pending`
(an open sign-off, blocks only the release) or a `note` (information). A finding accepted in the graph – `accept` on
the net or the component, keyed by its code (the fields, 3.1) – shows `(accepted)` with the reason. The profile of the
project can raise or lower a code's severity (14.2). Exit 1 on errors, with `--release` also on pending findings. The
design hints (HINT, chapter 14.3) are notes and never block.

### What went unchecked

A code that needs a datasheet value skips a part without it: LIM.v a capacitor without `v_max_v`, LIM.t every part
without `rth_ja_k_per_w`, LVL.threshold an input without `vih`/`vil`, LIM.range an IC without its operating range or
an op-amp without `vicm_v`, LIM.i a magnetic buzzer (`coil_ohm`) without `i_max_a`. An RGB LED is read per colour, as
the simulation holds it (5.1): each colour by its own `limits.<color>`, a colour without its own table by the entry's
limits. A gap names the colour that lacks the value (`LIM.i: D10 – no if_max_a for green – …`).

`edakit check` names these gaps in one line above its last (`not checked for lack of data: LIM.t 11 parts,
LVL.threshold 1 part – edakit check --coverage`). `--coverage` lists them per code with the designators and the field
that is missing, and the gate protocol lists them in its section 2. A gap is no finding – nothing was found, since
nobody looked; it closes when the entry gets the value from its datasheet.

The same list names what the simulation does not model over time (5.1): a charger, a cell's protection, a USB PD sink
– its end of charge, its release voltages and delays, its negotiation. They show as `not simulated` under SIM.state,
with the hint that names the risk, and end the one line (`…; not simulated over time: U3 (charger), U4 (protection) –
edakit check --coverage`). These gaps stay: decision 17 of rules-at-scale.md gives such behaviour no state model.

The list also names every cable without `i_max_a` that carries current in the simulation (decision 22). A wire's
rating comes from the wire's own datasheet, none from its gauge. What would pass unseen is a wire that heats while its
voltage drop and its connectors pass – 12–24 V at amperes, short thin leads, a thin wire in a contact rated for a
thicker one.

The line gives the cable's highest current over the scenarios, its wire and scenario, and the loss it causes in a metre
of the wire, I² × R of the wire's copper – a number, no verdict, no threshold. An example: `LIM.i: cable W1 – no i_max_a
– up to 2 A (wire 8, usb-max/all_on/vf-max), I² × R: 211.3 mW per metre of wire (AWG 22 copper at 20 °C) – its current
is not held to the wire's rating`.

With `r_ohm_per_wire` and no `length_m` the line gives the loss in the whole wire. The currents come from the simulation
`edakit sim` saved for this state; the gate uses its own run. `edakit check` runs none, and without a current one the
cable is named with its current not known. The one line ends with `cables without i_max_a: W1`.

### Polarity

Polarity – is the LED the right way round? – is not a graph rule but a simulation result. A reversed LED shows up in
stage E as "LED reversed" or as a dark LED (chapter 5), and SIM.driver makes sure no LED escapes it. G-7, the graph's
polarity check before the codes, is retired.

## 3.4 Working rules

1. Change the graph, never the schematic or the PCB – the file `[project] graph` names, beside a TOML graph never the
   generated `graph.json`. The hardware-change skill walks through the rest.
2. Every new LCSC number gets its parts entry first (part-search skill). A new function starts from a building block
   where one fits (`edakit block`, chapter 14.5).
3. `edakit check` and `edakit sim` before every commit that touches `hardware/`. The pre-commit hook runs them, with a
   TOML graph also `edakit graph json --check` (the generated JSON, 3.1).
4. A finding is fixed or accepted with a reason. Never edit a check to make a finding go away.
5. Generated files (firmware pin tables, the circuit description's parts list) are regenerated from the graph, never
   edited, and committed together with the graph change: the resolved `hardware/graph.json` beside a TOML graph with
   `edakit graph json --write` (3.1), the firmware contract with `edakit firmware` (3.5).

## 3.5 The firmware contract

Opt-in: with `[firmware]` in edakit.toml (10.1), `edakit firmware` writes what the firmware must know about the board
as neutral JSON (default `hardware/firmware.json`). `edakit firmware --check` exits 2 when the committed file no longer
matches – for the pre-commit hook, next to `edakit check` and `edakit sim`. Without the table nothing changes. It runs
the other way round from STRUCT.lock: there the firmware is the reference and `locks.pins` hold the graph to it; here
the graph is the reference and the firmware follows. A project may use both.

| Key | Content |
|---|---|
| `graph_version`, `graph_date`, `state_sha256` | the circuit it was written from – `state_sha256` is the gate's circuit hash (8.2), so any change to graph, parts or sim config asks for `edakit firmware` again; `--check` lists what differs |
| `mcu` | the MCU it describes (`[firmware] mcu`, default the one part with pins of the role `gpio`) |
| `pins` | `{net: {pin, name, gpio, dir, pull, idle, active}}` for every connected `gpio` pin of the MCU. `gpio`: the number in the pin's name (`[firmware] gpio`). `dir`: `out` when it drives an input, an LED or a transistor's base or gate (directly or through one resistor), `in` when a button, a switch or an output drives the net, `inout` for both or only bidirectional pins, `null` when nothing says. `pull`: `{dir, by, ohm}` of the resistors to a rail or ground – on the net or behind one series resistor (a base resistor and its pull-down) –, `{dir, by: "internal"}` for a switch without one (the firmware switches the MCU's pull on), `{dir, by: "pin"}` for a pin's built-in `pull`. `idle`: the level of the pull. `active`: the level a switch gives when closed, the level that lights an LED on the pin (`leds`, with the side it is on), or for an output with a pull the opposite of `idle`. Copied from the net where they are set: `fn`, `fn_bus`, `pwm_hz` (REQ.function), `clock_hz` (LIM.range/clock) |
| `pwm` | `{net: pwm_hz}` of the nets with `fn: "pwm"` |
| `inputs` | buttons and switches on MCU pins with their `active` level; a DIP switch as `bits` in the order of its roles `a1` … `aN` / `b1` … `bN` |
| `buses` | `{fn_bus: {fn: net}}`, and I2C lines by pin role `sda`/`scl` as `i2c` |
| `analog` | every MCU pin on a net with `fn` `"adc"`: `pin`, `gpio`, `channel` (the pin's functions `adc…`), the `divider` in front of it – the net one resistor from another net and one from ground: `from`, `top`, `top_ohm`, `bottom`, `bottom_ohm`, `ratio` –, or a lone `pull_up_ohm` / `pull_down_ohm` (a thermistor's partner); values from the resistors' entries |
| `devices` | `{"i2c": [{bus, address, part, how, f_max_hz}]}` – every device on the MCU's I2C lines whose entry gives its `address` (4.1), at the address its pins decide, the bus named by its SDA net, with the highest SCL its entry gives (`f_scl_max_hz`); `{"spi": [{bus, part, modes, f_max_hz}]}` – every device on an SPI clock line of the MCU (`fn: "spi.sck"`), the bus named by its `fn_bus`, with its modes (`spi_modes`) and highest SCK (`f_sck_max_hz`); `null` where the entry gives none |
| `bus_speed` | per SPI and I2C bus of the MCU: `clock_hz` (the net's, `null` without), `f_max_hz` and `by` – what limits the bus: the slowest device, or for I2C its pull-ups –, for SPI `modes` (the modes every device runs in; `[]` where they share none: `edakit firmware` says the firmware switches the mode per chip select), for I2C `pull_ups` (the slower line: `pull_up_ohm`, `c_bus_f`, `c_bus` – what the capacitance holds: the pins' `c_in_f`, the cables' `c_pf_per_m`, the pins without it; tracks are not counted –, `rise_ns` = 0.8473 · Rp · Cb, the fastest UM10204 `mode` whose rise time and Cb it keeps and its `f_max_hz`, or `why` not) |
| `chains` | from an MCU net through the roles `sdi` → `sdo`: `data`, `parts` in shift order, `read_back` (the last `sdo` on an MCU pin), `common` (MCU nets every part of the chain shares: clock, latch, enable) and `first_bit_to` (the part fact `values.first_bit_to`, `"unknown"` without it) |
| `channels` | `{channel, chain, driver, output, pin, net, leds}` for every output with the role `out0` … `outN`, the LEDs traced as SIM.state/SIM.driver trace them: cathode on the output directly, behind 0 Ω bridges or behind a balancing resistor (5.3); `channel` = the outputs of the drivers before it in its chain + its number. A reversed LED is listed under `reversed` |

Only roles decide which pin is a cathode, a data input or output 3 – never a pin name. The one exception is the GPIO
number, taken from the MCU pin's name. A driver in a chain whose outputs have only the role `out` is an error: the
channel order needs the numbers.

The contract has no firmware format. Turning it into source – a MicroPython module, a C header – is the project's own
script, which reads the JSON and runs after `edakit firmware`; MicroPython can also read the JSON as it is.

## 3.6 Requirements

The graph says what the circuit is, the decision log why it is so; the requirements file says what it must do.
`[project] requirements` in edakit.toml names it, usually `hardware/requirements.toml` (its format, 10.4). Every
project has one before it orders. Without the key DOCS.file is open, as a required sign-off is: `edakit check` reports
it and passes, so a project being set up still commits; `edakit check --release` and the gate do not release (8.7).
Two levels, along the gap between a wish and a circuit:

| Level | ID | Content | Example (the tests' led-bar) |
|---|---|---|---|
| need | N-… | what someone wants, in their words: who, in which situation, what for | N-1 "The bar runs from a USB charger or from the USB port of a laptop." |
| requirement | R-… | one statement of what the circuit must do, in the words and at the level of detail of who stated it, bound as `must`, `should` or `may` | R-1 "Runs from the USB port of a laptop with all eight LEDs on." |

**Inputs, not outputs.** A requirement is what someone involved states – the maker, a user, a standard or law the
maker chooses. It takes the customer's view and the level of detail they give it ("a servo must be driven" as much as
"pin X never above Y"). Nothing edakit generates or the circuit designer derives is one: not a simulated value, a
check result, the derating, a part's limit or a choice the design made on its own. The test is who stated it: a
choice the maker made is a requirement (the LED colours, two buttons, a module on headers); one the designer or edakit
made is not (the regulator, a series resistor's 330 Ω).

The numbers that follow – the current that keeps a power bank on, the voltage at a servo's start – stay in sim.json
and the graph's notes. They reach the requirement as its evidence (`rows`): R-1 above names no current, and its rows
`LIM.i * J1 current from the supply` test it against the 500 mA of USB 2.0. What edakit's catalog checks on every
board (the parts' limits, the levels, the radio law of M-6) needs no requirement – the gate fails on it anyway. A
project designed before its file gets inferred drafts: its parts lifted to what a person sees, presses, plugs in,
hears, each marked inferred until you say yes.

`source` says where an entry was found – a document, a decision. `from` says where a requirement comes from: a need, a
decision (D-8), a standard (USB 2.0: 500 mA), a sign-off (M-6). `verify` says what tests it: rows of the gate
protocol (their form and the simulation's: 10.4), a manual check, a project script, a step of the acceptance test. The file covers the circuit only – what the
boards must do and withstand; what firmware and mechanics must do stays in the project's own documents.

IDs are stable, as in the rule catalog: a requirement that no longer holds stays in the file with its `reason` and
`status = "dropped"`. Claude drafts with `status = "draft"`, which is also what an entry without `status` is; only you
set `accepted`. A change to an accepted requirement is a decision in the decision log.

**Who writes it.** The skill `requirements`, in the conversation with you. It collects what those involved state the
circuit must do and asks back in one decision round until vague words are your numbers and contradictions are
decided. It writes drafts and has you approve them – approving a requirement is one of your real decisions (the
working agreements, 11.4). It writes this file and the decision log, never the graph.

In a project with documents the agent `requirements-engineer` makes the inventory first. It reads every document in
its own context, changes nothing, and returns candidates with who stated them, what edakit already checks on every
board, contradictions, vague words and requirements without evidence; on a finished file it gives a second opinion.
The circuit designer reads the file instead of asking for the requirements (skill circuit-design), and a new function
starts with its requirement. Each reviewer judges the requirements its sign-off verifies (8.7); the roles: 14.1.

```bash
edakit req        # needs and requirements: status, binding, and the evidence as written in verify
edakit req R-1    # one chain: where R-1 comes from, the requirement, what verifies it
edakit req N-1    # the requirements a need leads to, with their evidence
```

`edakit req` shows the evidence as written; checks and gate do the rest, only in a project with the key:

- **`edakit check`** (3.3) – and the gate's stage G – checks the file: every reference resolves (DOCS.ref), every
  accepted need has a requirement (DOCS.need), every requirement has evidence (DOCS.evidence), and a draft warns until
  you decide (DOCS.draft). A requirement names someone who stated it (DOCS.derived): its `source` a decision, a need,
  a document of the project that is not design data, or a date – without `source` its `from` a need, a decision or a
  standard. One that names only graph, parts entries, `sim.json`, the sign-off file or a datasheet is derived from the
  design, not stated, and warns – for a draft as for an accepted requirement, in the gate too.
- **A draft never blocks.** Every finding about a draft is a warning – a reference that does not resolve yet, no
  evidence yet –, so an unfinished file passes `edakit check` and the pre-commit hook; in the gate the findings are
  information. Errors and blocking start once you have set `status = "accepted"`.
- **The gate** evaluates every requirement's evidence against its run (8.7). For an accepted requirement, `must`
  without passing evidence blocks the release, `should` is a warning you accept, `may` informs; a draft is evaluated
  as well and binds nothing yet. Section 11 of the protocol lists every requirement with its evidence and the result,
  a draft marked as one; the acceptance steps (`accept`) join the list of section 6 that M-4 works through.
- **The circuit hash** covers the file byte for byte, `[release] hash_ignore` does not reach into it (8.2): a changed
  requirement voids M-1 and M-6 – the reviews read the requirements –, and with `[firmware]` the contract shows drift
  (3.5).
- **Documents quote it** by ID instead of copying the sentence: a value block
  `<!--edakit req:R-1-->…<!--/edakit-->` in a file of `[docs] files` (6.6). `edakit docs --write` fills in the
  entry's text; DOCS.quote – `edakit docs` and the gate's stage G – reports a quote that differs from the file, an ID
  that is not in it and an entry that is dropped, which no longer holds. A quote that went stale is DOCS.quote whatever
  the entry's status, a draft's too: `edakit docs --write` brings it along.
- A file the key names that is missing or not valid stops `edakit req`, `edakit check` and the gate alike.

A variant – a project of its own in a folder below the main project – reads the main project's file and its own; an
ID stands in only one of them (10.4). Both count in the variant's circuit hash.
