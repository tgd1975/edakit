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
| `part` | the manufacturer part number; without `lcsc` it names the parts entry (its `mpn`) – a part bought elsewhere (chapter 4) |
| `pins` | pin number → pin name, **with the pin numbers of the EasyEDA/LCSC symbol of exactly this part**. The names must equal the parts entry (P-1). |
| `nc` | pins deliberately unconnected; every pin is in exactly one net or in `nc` |
| `board` | which board the part is on (a key of `[boards]` in edakit.toml); may be omitted with one board |
| `value` | shown in the BOM ("10k", "100nF") |
| `bom: false` | the part is placed on the PCB but not in the BOM for assembly (hand-soldered, bought separately) |
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
  often do not (anode = 1 for one LED, = 2 for another of the same shape). Read them once from EasyEDA
  (`edakit schematic create --only U3` and `easyeda_schematic_component_pins`) and write the roles into the parts
  entry. Code that needs "the cathode" asks for the role, never for the pin name.
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
| G-1 | structure: unique designators and nets, every pin in exactly one net or `nc`, nets with ≥ 2 pins, a voltage range per net, a known board per part, nets across boards only through a cable; the names in `layout` and `checks`, the `ground` net, `purpose.use` | a forgotten pin, a typo in a pin reference |
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
| P-1 | graph pins (number and name) = parts entry; an entry exists for every LCSC number; no supply pin marked `nc` | a wrong part number, pins shifted by one |
| P-3 | own parts (4.5): a board copied with `edakit part own` is its project's current datasheet, copied from a commit (pending otherwise); a board not released at that state is a warning; the project's own datasheets are of its current state | a board changed after it was copied into the host |
| G-9 | sign-off: every part `verified` against its datasheet, no open `verify` note (pending – blocks only the release) | an unchecked part going into an order |

**0 Ω bridges.** A resistor whose parts entry has `value_ohm: 0` is copper – the usual way to cross a track on a board
with all tracks on one side. The nets it joins are one net for G-4, G-5, G-6 and G-10 to G-17: a pull-up behind a
bridge holds its input, a capacitor to a ground net behind a bridge decouples, two outputs on either side clash. A
finding names the joined net after the ground net if that is one of them, else after the first of them in the graph;
a waiver on any of them counts. G-1, G-2, G-3, G-8, P-1 and G-9 see every net and the bridge as the graph has them.
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
   edited, and committed together with the graph change.
