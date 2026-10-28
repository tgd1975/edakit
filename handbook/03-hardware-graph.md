# 3 The hardware graph

The graph is a pin-level netlist in JSON. It is the **only** place where parts, values and connections are decided.
Example: [the Christmas bell's graph](https://github.com/tgd1975/automatic_christmas_bell/blob/main/hardware/graph.json); the snippets below come from the
[test project](../tests/fixtures/led-bar/hardware/graph.json).

## 3.1 Format

```json
{"graph": {
  "name": "led-bar", "version": "1.0", "date": "2026-10-25", "description": "…",
  "components": [
    {"designator": "U2", "type": "ic", "label": "TLC5916 8-channel constant-current LED driver",
     "part": "TLC5916IDR", "lcsc": "C90107", "board": "main",
     "pins": {"1": "GND", "2": "SDI", "3": "CLK", "4": "LE(ED1)", "5": "OUT0", "…": "…", "16": "VDD"},
     "nc": ["14"], "notes": "I_OUT = 15 x 1.26 V / R1 (D-9)"},
    {"designator": "R2", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}},
    {"designator": "U1", "type": "microcontroller", "lcsc": "C41407547", "bom": false, "pins": {"…": "…"}}
  ],
  "nets": [
    {"name": "+5V", "pins": ["D1.1", "U1.39", "C2.1", "D2.1"], "v": [0, 5.5], "notes": "behind the reverse diode"},
    {"name": "LED_CLK", "pins": ["U1.4", "U2.3"], "v": [0, 3.4], "fn": "spi.sck", "fn_bus": "LED",
     "waive": {"G-4": "floating until the firmware runs, harmless: OE is pulled high"}}
  ],
  "cables": [
    {"name": "W1", "from": "J2", "to": "J1", "pins": {"1": "1", "2": "2"}, "r_ohm_per_wire": 0.065}
  ],
  "checks": {"reverse_protect": ["J1"], "pin_locks": {"U1.4": "LED_CLK", "U1.5": "LED_SDI"}}
}}
```

| Field | Meaning |
|---|---|
| `designator` | as on schematic, PCB and silkscreen |
| `type` | rough class for the generated template layout and the schematic blocks: `microcontroller`, `module`, `ic`, `transistor`, `connector`, `regulator`, `diode`, `led`, `resistor`, `capacitor`, `inductor`, `button`, `switch`, `potentiometer`, `audio`, `testpoint`, `battery_holder`, `fuse` |
| `lcsc` | the LCSC number – identifies symbol, footprint, parts entry and the BOM line |
| `part` | the manufacturer part number; without `lcsc` it names the parts entry (its `mpn`) – a part bought elsewhere (chapter 4); with `lcsc` it must name the entry's `mpn` too (P-6) |
| `pins` | pin number → pin name, **with the pin numbers of the EasyEDA/LCSC symbol of exactly this part**. The names must equal the parts entry (P-1). |
| `nc` | pins deliberately unconnected; every pin is in exactly one net or in `nc` |
| `board` | which board the part is on (a key of `[boards]` in edakit.toml); may be omitted with one board. On a bought board (`bought = true`, 4.5) every part has `bom: false` (G-1) |
| `value` | shown in the BOM ("10k", "100nF"); P-6 holds it to the entry's `value_ohm`, `value_f` or `value_h` |
| `bom: false` | the part is placed on the PCB but not in the BOM for assembly (hand-soldered, bought separately); `edakit order` puts it into the cart of its supplier (8.4) |
| `supplier` | for a part bought separately: the supplier whose cart it goes into (default: the first of its parts entry's `order`, else `lcsc` with an LCSC number) |
| `spare` | pieces ordered on top for the whole order (`edakit order`), e.g. `1` for an LED that is easily lost |
| `easyeda_device` | for parts without LCSC number (bare test pads): `{name, uuid, libraryUuid}` of an EasyEDA library device |
| `verify` | an open question about pins/polarity that the library does not settle; blocks the release (G-9) until resolved |
| `waive` | `{check id: reason}` – a finding accepted on purpose; printed with its reason in every report |
| `notes` | free text; cite decision numbers here |
| net `v` | `[min, max]` voltage over **all** intended operating states (all supply variants, reversed supply, unloaded) |
| net `bus` | `"i2c"` marks SDA and SCL nets whose pins do not say so (MCU pins called GP4): G-11 checks them |
| net `fn` | the function the net needs from its MCU pin: `pwm`, `adc`, `spi.sck`, `spi.tx`, `spi.rx`, `spi.cs`, `i2c.sda`, `i2c.scl`, `uart.tx`, `uart.rx` – G-15 holds it to the pin's `functions` (4.1); without `fn` the pin is a plain GPIO (bit-banged, PIO) |
| net `fn_bus` | a name the nets of one bus share (`"LED"` on SDI and CLK): G-15 wants them on one peripheral instance (`spi0`, not `spi0` and `spi1`) |
| net `pwm_hz` | the PWM frequency of a net with `fn: "pwm"` – a number, or `[min, max]` for one that changes (a buzzer playing notes): two PWM nets on one slice need the same fixed frequency (G-15) |
| `cables` | wires between boards: connector pins joined 1:1; the cable is no part, its resistance (`r_ohm_per_wire`) feeds the simulation, its rating per wire (`i_max_a`, optional) G-17 |
| `hints` | design hints that are taken care of, `{"H-1": "C1 1000 µF next to J1"}` – chapter 14.3 |
| `layout` | the hand-over to the layout: `fixed`, `edge`, `near`, `loops`, `notes` – chapters 7.4 and 14.1; G-1 checks that the names exist |
| `purpose` | what the board is for: `use` (`private` – built for oneself, `gift` – given away, `sale` – sold, also in small series), `market` (`"EU"`), `notes` (what it is, who uses it) – it decides which rules the regulatory review applies (chapter 15); part of the circuit hash |
| `ground` | name of the ground net (default `GND`) – the checks, the simulation and the schematic's flags use it; G-1 checks that the net exists |
| `grounds` | further nets that are ground on purpose, `["AGND"]` – an analog ground joined at one point, an isolated side: their `ground` pins pass G-16 (default: none) |
| `checks` | settings of the graph checks: `pin_locks` (`{"U1.4": "LED_SDI"}` – pins the firmware relies on, G-2), `doc_pin_table` (`{component, file, prefix, regex}` – a pin table in the documentation, G-2), `reverse_protect` (connectors that may be plugged in the wrong way round, G-10; also a power input for the design hints); part of the circuit hash, G-1 checks the names |

## 3.2 Conventions that save trouble

- **Pin numbers come from the EasyEDA symbol**, not from the datasheet. They usually agree; for LEDs and diodes they
  often do not (anode = 1 for one LED, = 2 for another of the same shape). `edakit part import C2297` reads them
  from the library without EasyEDA (4.2) and keeps the symbol, so P-1 compares the graph with it; inside EasyEDA,
  `edakit schematic create --only U3` and `easyeda_schematic_component_pins` show the placed symbol. Write the roles
  into the parts entry. Code that needs "the cathode" asks for the role, never for the pin name.
- **Net names are stable identifiers** used by firmware, simulation config and docs. Rename deliberately.
- **Voltage ranges are worst case.** `v` is what G-3 compares with the pin limits and what the simulation checks every
  scenario against. Think about the unloaded supply, the reversed supply, a programming cable plugged in at the same time.
- **Decisions in the graph.** "Why 2 k?" – `notes: "D-9: I_OUT = 9.45 mA"`. The decision log has the reasoning.
- **One part, one LCSC number.** A footprint variant is a different part.

## 3.3 Rule checks (stages P and G)

`edakit check` runs in well under a second; put it into the pre-commit hook and CI. What each check is about, why it
exists, what to do and the sources: the rule catalog, `edakit rules` (list) and `edakit rules G-4` (one entry). Every
check that fails is explained once below the findings (chapter 14.2).

| Check | What | Finds e.g. |
|---|---|---|
| G-1 | structure: unique designators and nets, every pin in exactly one net or `nc`, nets with ≥ 2 pins, a voltage range per net, a known board per part, `bom: false` on a bought board, nets across boards only through a cable; the names in `layout` and `checks`, the `ground` net, `purpose.use` | a forgotten pin, a typo in a pin reference |
| G-2 | pin locks: pins the firmware relies on are on the expected nets (`checks.pin_locks`); optionally a pin table in a Markdown document equals the graph (`checks.doc_pin_table`) | firmware and hardware disagree |
| G-3 | voltage domains: every net's range within `vmax` of every pin on it | a 5-V signal on a 3.3-V GPIO |
| G-4 | no floating input: an input needs a driver or a pull resistor; an input driven only by MCU pins needs a pull (floats until the firmware runs); every BJT needs a base-emitter resistor, every MOSFET a resistor from its gate to the source or a rail | a floating OE or EN pin at power-up, a MOSFET half on while the MCU boots |
| G-5 | at most one push-pull output / supply output per net | two outputs against each other |
| G-6 | decoupling: per net at least one capacitor to ground per IC supply pin (`power_in`) | the missing 100 nF |
| G-8 | voltage ratings with margin: capacitors (×1.5), diodes VRRM (×1.5), BJT VCEO, MOSFET VDS/VGS (×1.5), fuses, switches, connectors | a 6.3-V capacitor on a 5-V rail |
| G-10 | reverse polarity from the topology: what a reversed source (battery holders, `checks.reverse_protect`) reaches through fuses, switches and connectors may only be a capacitor, the anode of a diode whose cathode is outside, or the drain of a PMOS whose source and gate are outside | the protection diode bypassed, an IC directly on the battery |
| G-11 | I2C pull-ups: every I2C line has a pull-up to a supply between (V − 0.4 V) / 3 mA and 10 kΩ, parallel ones added up; a line is I2C by the net's `bus`, an SDA/SCL net name, a pin role `sda`/`scl` or a pin name with SDA/SCL (a role decides over the name); pins with `pull`/`pull_ohm` count (modules) | a bus without pull-ups, 47 kΩ, a module's pull-ups plus your own below 1 kΩ |
| G-12 | strapping pins: a pin with `strap` in its parts entry is at that level at reset – no pull, rail or output on its net says otherwise, and something holds it (a pull, or the pin's internal `pull`) | a pull-down on the ESP32's GPIO0, an I2C pull-up on GPIO12 |
| G-13 | flyback diode: a relay coil or a buzzer with `coil_ohm`, switched by a transistor or an output, has a diode across it with the cathode at its plus terminal | a relay that kills its transistor at the first switch-off |
| G-14 | USB-C sink: a receptacle with `cc1`/`cc2` pins has its own 5.1 kΩ ± 10 % to ground on each CC pin; silent when an IC is on the CC lines. A module or breakout states its receptacle's termination in `params.usb_c` (4.1): `rd_5k1` or `controller` passes, `none` has its CC pins checked the same way and fails without them | no 5 V from a USB-C charger, CC1 and CC2 on one resistor, a breakout without its two resistors |
| G-15 | pin functions: a net with `fn` is on a pin whose parts entry lists that function (`functions`), the nets of one `fn_bus` on one peripheral instance, two PWM nets of one slice with the same fixed `pwm_hz` and a channel each; a net with `fn` on pins without `functions` is a note | SPI data on the clock pin, an analog input without ADC, a buzzer on the PWM slice of an LED |
| G-16 | ground and supply pins: every `ground` pin on the ground net (or one joined to it by a 0 Ω bridge or an inductor, or in `grounds`); every `power_in` pin on a net that a supply reaches – a `power_output` pin, a battery holder, a connector with a `vbus` pin or in `checks.reverse_protect`, a simulation source – directly or through fuses, switches, connectors, inductors, MOSFETs, resistors up to 100 Ω and diodes in forward direction | a rail split by a typo in its name, a ground pin on a net of its own, VDD swapped with a signal |
| G-17 | fuse against what it protects: the hold current of every fuse (`i_hold_a`; at the lowest ambient `ambient_min_c` of sim.json from `i_hold_vs_temp`) is at most the `i_max_a` of every connector, switch and cable its current flows through – its own nets and on through fuses and switches; a trip current (`i_trip_a`) above it is a warning | a 1.5-A polyfuse in front of a connector rated 1.25 A, an overload that heats the contacts instead of tripping the fuse |
| G-18 | hot loop in the hand-over: a part whose entry names its hot-loop pins (`hot_loop`, 4.1) has a `layout.loops` entry on every net of the loop – the nets of those pins and, one diode further, the net behind the rectifier on its switch node (`sw`); a buck or boost IC (`behavior`) without `hot_loop` is a warning; `waive` on the part, or on a net whose part of the loop closes over a pour | a boost whose output loop was routed 61 mm across the board, passing every check because nobody listed it |
| G-19 | documents quote the design data: every value block of `[docs] files` equals its source, every source of a block or a schematic-note placeholder exists – run by `edakit docs` and the gate's stage G, not by `edakit check` (6.6) | a description still on an old graph version, a current that changed with R1 |
| G-20 | requirement references resolve – G-20 to G-23 only with `[project] requirements` (3.6), on every entry that is not dropped: a need or requirement in `from` (N-…, R-…) is in the files, a manual check in `from` or in `verify` `signoff` (M-…) is one of the sign-off file or a required one (8.2), a `rows` pattern that starts with a check ID names a check of the catalog that is not retired, a `script` is an entry `[scripts.<name>]` of kind `check` or the id of a `[[release.stages]]`; a `from` that names a dropped need or requirement is a warning. Decisions, standards and words in `from` are not resolved | `from = ["N-12"]` for N-2, `rows = "E-30 *"`, `signoff = "M-7"`, a requirement that still comes from a dropped need |
| G-21 | accepted need has a requirement: every accepted need is in `from` of a requirement that is not dropped | a need the user accepted that no requirement made testable |
| G-22 | requirement has evidence: every requirement that is not dropped has `verify` | a requirement the gate has nothing to evaluate for |
| G-23 | draft not approved: a need or requirement with `status = "draft"`, or without `status`, is a warning until the user accepts or drops it | a requirement Claude wrote and nobody approved, on its way into a release |
| P-1 | graph pins (number and name) = parts entry; an entry exists for every LCSC number; no supply pin marked `nc`; with the library's symbol cached by `edakit part import`, graph pins = that symbol (case and blanks ignored, as S-2; `waive` on the component) | a wrong part number, pins shifted by one, an LED whose pin 1 is the cathode |
| P-6 | part identity: the component and its parts entry name the same part – the entry's `lcsc` is its file name; the component's `lcsc` is no `C99…` user-library number (unless `bom: false`); its `part` names the entry's `mpn` (remarks in parentheses or after `;` left out, case ignored, a manufacturer before it allowed; a `part` that starts with a value, "330 Ω 0805", is compared as that value); its `value` reads as the entry's `value_ohm` / `value_f` / `value_h` within 1 % ("4k7", "100nF", "2R2"); its `type` fits the entry's `kind` (microcontroller, regulator: ic or module; transistor: npn, pnp, nmos, pmos; led: led, led_rgb; switch: switch, dip_switch; audio: buzzer; otherwise the same word); `waive` on the component. A designator prefix against the kind (R, C, L, D, Q, U, J, SW, F, BT, BZ, K, TP) is a warning | C25789 written for a 74HC165 (a 464 kΩ resistor), R2 "1k" on a 10 kΩ entry, an LED that came in as U1 |
| P-3 | own parts (4.5): a board copied with `edakit part own` is its project's current datasheet, copied from a commit (pending otherwise); a board not released at that state is a warning; the project's own datasheets are of its current state | a board changed after it was copied into the host |
| P-4 | parts orderable (4.2): every assembled part listed at JLCPCB, in stock for `quantity` boards (with the attrition under Standard), its entry's MPN, not "Standard Only" on an Economic order – from the snapshot of `edakit stock`; MSL ≥ 5, a thin margin, another class warn; an old snapshot is pending, none a note | a part that is pre-order only, Standard-only or baked, found in the quote |
| P-5 | supplier per part: a part bought separately (`bom: false`) has an LCSC number – a `C99…` EasyEDA library number is none – or `order` in its parts entry (warning) | a module or LED nobody wrote an order code for, found when the order list is written by hand |
| P-7 | through-hole leads known and fitting the footprint, before the layout: L-9's test (8.1) on the holes of the footprint geometry – the board's `pcb dump`, else the library footprint of `edakit part import`; plated holes without `lead` in the entry pending, a hole that does not take the lead an error (`waive` on the component), tight in the worst case or a plated slot below 0.5 mm a warning; without geometry a note | a library footprint drilling 0.70 mm for □0.5 mm legs, found before anything is placed |
| P-8 | formed leads fit only one way round: a part whose plated holes the board's footprint (`pcb dump`) moves away from the library footprint of `edakit part import` – a hole more than 0.05 mm (L-10's tolerance) from the library's hole of its number, the two laid on each other by their numbers –, with three or more of them, is not laid onto itself by a turn of 90°, 180° or 270°, every hole within 0.25 mm of a hole, with a pin in the hole of a pin on another net; pins on one net do not count, two holes and a part on its library pattern are not judged (its orientation is the print's job, L-8). The pads are matched as `part diff` matches them (7.3). The finding names the turn and the pins: `D31: its formed holes lie on each other turned by 180° – pin 1 (V_LED) in the hole of pin 3 (STAR_G_K), pin 2 (STAR_R_K) in the hole of pin 4 (STAR_B_K)`; `waive` on the component; without the library footprint a note | an RGB star LED with two legs bent the same way, which went in turned by 180° as easily – anode in a cathode's hole, the star dark –, with a "+" at the anode and every check passed |
| G-9 | sign-off: every part `verified` against its datasheet, no open `verify` note (pending – blocks only the release) | an unchecked part going into an order |

**0 Ω bridges.** A resistor whose parts entry has `value_ohm: 0` is copper – the usual way to cross a track on a board
with all tracks on one side. The nets it joins are one net for G-4, G-5, G-6 and G-10 to G-17: a pull-up behind a
bridge holds its input, a capacitor to a ground net behind a bridge decouples, two outputs on either side clash. A
finding names the joined net after the ground net if that is one of them, else after the first of them in the graph;
a waiver on any of them counts. G-1, G-2, G-3, G-8, G-18, P-1 and G-9 see every net and the bridge as the graph has
them (G-18: the pads of `layout.loops` lie on one net of the graph).
`edakit check` lists the joined nets above its last line:
`joined by 0 Ω bridges, checked as one net: GND = GND_B (R11); 3V3 = 3V3_B = 3V3_C (R10, R13)`.

Results: `ERROR` (must be fixed), `WAIVED` (accepted in the graph with a reason), `PENDING` (open sign-off), `WARNING`
(the gate wants it accepted in the sign-off file, 8.2), `NOTE` (information). Exit 1 on errors, with `--release` also
on pending sign-offs. The last line also names the design hints that are still open
(`edakit hints`, chapter 14.3); they never block.

Polarity (is the LED the right way round?) is not a graph rule but a simulation result: a reversed LED shows up in
stage E as "LED reversed" or as a dark LED (chapter 5), and E-4 makes sure no LED escapes it. G-7 was the graph's
polarity check; it is retired and its number is not used again.

## 3.4 Working rules

1. Change the graph, never the schematic or the PCB. The hardware-change skill walks through the rest.
2. Every new LCSC number gets its parts entry first (part-search skill). A new function starts from a building block
   where one fits (`edakit block`, chapter 14.5).
3. `edakit check` and `edakit sim` before every commit that touches `hardware/` – the pre-commit hook does it.
4. A finding is fixed or waived with a reason. Never edit a check to make a finding go away.
5. Generated files (firmware pin tables, the circuit description's parts list) are regenerated from the graph, never
   edited, and committed together with the graph change – the firmware contract with `edakit firmware` (3.5).

## 3.5 The firmware contract

Opt-in: with `[firmware]` in edakit.toml (10.1), `edakit firmware` writes what the firmware must know about the board
as neutral JSON (default `hardware/firmware.json`), and `edakit firmware --check` exits 2 when the committed file no
longer matches – for the pre-commit hook, next to `edakit check` and `edakit sim`. Without the table nothing changes.
It runs the other way round from G-2: there the firmware is the reference and `pin_locks` hold the graph to it; here
the graph is the reference and the firmware follows. A project may use both.

| Key | Content |
|---|---|
| `graph_version`, `graph_date`, `state_sha256` | the circuit it was written from – `state_sha256` is the gate's circuit hash (8.2), so any change to graph, parts or sim config asks for `edakit firmware` again; `--check` lists what differs |
| `mcu` | the MCU it describes (`[firmware] mcu`, default the one part with pins of the role `gpio`) |
| `pins` | `{net: {pin, name, gpio, dir, pull, idle, active}}` for every connected `gpio` pin of the MCU. `gpio`: the number in the pin's name (`[firmware] gpio`). `dir`: `out` when it drives an input, an LED or a transistor's base or gate (directly or through one resistor), `in` when a button, a switch or an output drives the net, `inout` for both or only bidirectional pins, `null` when nothing says. `pull`: `{dir, by, ohm}` of the resistors to a rail or ground – on the net or behind one series resistor (a base resistor and its pull-down) –, `{dir, by: "internal"}` for a switch without one (the firmware switches the MCU's pull on), `{dir, by: "pin"}` for a pin's built-in `pull`. `idle`: the level of the pull. `active`: the level a switch gives when closed, the level that lights an LED on the pin (`leds`, with the side it is on), or for an output with a pull the opposite of `idle`. Copied from the net where they are set: `fn`, `fn_bus`, `pwm_hz` (G-15) |
| `pwm` | `{net: pwm_hz}` of the nets with `fn: "pwm"` |
| `inputs` | buttons and switches on MCU pins with their `active` level; a DIP switch as `bits` in the order of its roles `a1` … `aN` / `b1` … `bN` |
| `buses` | `{fn_bus: {fn: net}}`, and I2C lines by pin role `sda`/`scl` as `i2c` |
| `chains` | from an MCU net through the roles `sdi` → `sdo`: `data`, `parts` in shift order, `read_back` (the last `sdo` on an MCU pin), `common` (MCU nets every part of the chain shares: clock, latch, enable) and `first_bit_to` (the part fact `params.first_bit_to`, `"unknown"` without it) |
| `channels` | `{channel, chain, driver, output, pin, net, leds}` for every output with the role `out0` … `outN`, the LEDs traced as E-3/E-4 trace them: cathode on the output directly, behind 0 Ω bridges or behind a balancing resistor (5.3); `channel` = the outputs of the drivers before it in its chain + its number. A reversed LED is listed under `reversed` |

Only roles decide which pin is a cathode, a data input or output 3 – never a pin name (in the origin project an
exporter once found a cathode by the name "K" and nearly wrote a wrong channel table). The one exception is the GPIO
number, taken from the MCU pin's name. A driver in a chain whose outputs have only the role `out` is an error: the
channel order needs the numbers.

The contract has no firmware format. Turning it into source – a MicroPython module, a C header – is the project's own
script, which reads the JSON and runs after `edakit firmware` (MicroPython can also read the JSON as it is).

## 3.6 Requirements

The graph says what the circuit is, the decision log why it is so; the requirements file says what it must do. It is
opt-in: `[project] requirements` in edakit.toml names it, usually `hardware/requirements.toml` (format: 10.4). Two
levels, along the gap between a wish and a circuit:

| Level | ID | Content | Example (the tests' led-bar) |
|---|---|---|---|
| need | N-… | what someone wants, in their words: who, in which situation, what for | N-1 "The bar runs from a USB charger or from the USB port of a laptop." |
| requirement | R-… | one testable sentence with quantity, limit and condition, bound as `must`, `should` or `may` | R-1 "With all eight LEDs on, the board draws at most 500 mA from J1 at 4.75 to 5.25 V." |

`source` says where an entry was found – a document, a decision –, `from` where a requirement comes from: a need, a
decision (D-8), a standard (USB 2.0: 500 mA), a sign-off (M-6). `verify` says what tests it: rows of the gate
protocol, a manual check, a project script, a step of the acceptance test. The file covers the circuit only – what the
boards must do and withstand; what firmware and mechanics must do stays in the project's own documents. IDs are
stable, as in the rule catalog: a requirement that no longer holds stays in the file with `status = "dropped"` and its
`reason`. Claude drafts – `status = "draft"`, which is also what an entry without `status` is –, only the user sets
`accepted`; a change to an accepted requirement is a decision in the decision log.

**Who writes it.** The skill `requirements`, in the conversation with the user: it collects what the circuit must do,
asks back in one decision round until vague words are numbers and contradictions are decided, writes drafts and has
the user approve them – approving a requirement is one of the user's real decisions (11.4). It writes this file and
the decision log, never the graph. In a project with documents the agent `requirements-engineer` makes the inventory
first: it reads every document in its own context, changes nothing, and returns candidates with the place it found
them, contradictions, vague words and requirements without evidence; on a finished file it gives a second opinion.
The circuit designer reads the file instead of asking for the requirements (skill circuit-design), a new function
starts with its requirement, and each reviewer judges the requirements its sign-off verifies (8.7). The roles: 14.1.

```bash
edakit req        # needs and requirements: status, binding, and the evidence as written in verify
edakit req R-1    # one chain: where R-1 comes from, the requirement, what verifies it
edakit req N-1    # the requirements a need leads to, with their evidence
```

`edakit req` shows the evidence as written; checks and gate do the rest, only in a project with the key:

- **`edakit check`** (3.3) – and the gate's stage G – checks the file: every reference resolves (G-20), every accepted
  need has a requirement (G-21), every requirement has evidence (G-22), and a draft warns until the user decides
  (G-23).
- **The gate** evaluates every requirement's evidence against its run (8.7): `must` without passing evidence blocks
  the release, `should` is a warning the owner accepts, `may` informs. Section 11 of the protocol lists every
  requirement with its evidence and the result; the acceptance steps (`accept`) join the list of section 6 that M-4
  works through.
- **The circuit hash** covers the file byte for byte, `[release] hash_ignore` does not reach into it (8.2): a changed
  requirement voids M-1 and M-6 – the reviews read the requirements –, and with `[firmware]` the contract shows drift
  (3.5).
- A file the key names that is missing or not valid stops `edakit req`, `edakit check` and the gate alike.

A variant – a project of its own in a folder below the main project – reads the main project's file and its own; an
ID stands in only one of them (10.4). Both count in the variant's circuit hash.
