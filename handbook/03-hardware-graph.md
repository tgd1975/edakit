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

| Field | Meaning |
|---|---|
| `designator` | as on schematic, PCB and silkscreen |
| `type` | rough class for the generated template layout and the schematic blocks: `microcontroller`, `module`, `ic`, `transistor`, `connector`, `regulator`, `diode`, `led`, `resistor`, `capacitor`, `inductor`, `button`, `switch`, `potentiometer`, `audio`, `testpoint`, `battery_holder`, `fuse` |
| `lcsc` | the LCSC number – identifies symbol, footprint, parts entry and the BOM line |
| `part` | the manufacturer part number; without `lcsc` it names the parts entry (its `mpn`) – a part bought elsewhere (chapter 4); with `lcsc` it must name the entry's `mpn` too (STRUCT.identity) |
| `pins` | pin number → pin name, **with the pin numbers of the EasyEDA/LCSC symbol of exactly this part**. The names must equal the parts entry (STRUCT.entry). |
| `nc` | pins deliberately unconnected; every pin is in exactly one net or in `nc` |
| `board` | which board the part is on (a key of `[boards]` in edakit.toml); may be omitted with one board. On a bought board (`bought = true`, 4.5) every part has `bom: false` (STRUCT.board) |
| `value` | shown in the BOM ("10k", "100nF"); STRUCT.identity holds it to the entry's `value_ohm`, `value_f` or `value_h` |
| `bom: false` | the part is placed on the PCB but not in the BOM for assembly (hand-soldered, bought separately); `edakit order` puts it into the cart of its supplier (8.4) |
| `supplier` | for a part bought separately: the supplier whose cart it goes into (default: the first of its parts entry's `order`, else `lcsc` with an LCSC number) |
| `spare` | pieces ordered on top for the whole order (`edakit order`), e.g. `1` for an LED that is easily lost |
| `easyeda_device` | for parts without LCSC number (bare test pads): `{name, uuid, libraryUuid}` of an EasyEDA library device |
| `verify` | an open question about pins/polarity that the library does not settle; blocks the release (PARTS.verified) until resolved |
| `accept` | on a component or net: `{code: reason}` – a finding accepted on purpose, printed with its reason in every report; the key a code (`LVL.undefined`), a code with its grade (`LIM.i/margin`) or topic (`GEO.spacing:paste`) – 14.2 |
| `source` | `"reversible"` on a connector or holder that may be plugged in the wrong way round: PATH.reverse follows what it reaches reversed; it is also a power input for the hints |
| `off_board` | `true` on a connector whose wires leave the board without a cable in the graph – a terminal for a footswitch, a jack: its signal nets count as leaving the board, as a cable's do (REQ.missing/leave), and it suggests the domain cables |
| `notes` | free text; cite decision numbers here |
| net `v` | `[min, max]` voltage over **all** intended operating states (all supply variants, reversed supply, unloaded) |
| net `bus` | `"i2c"` marks SDA and SCL nets whose pins do not say so (MCU pins called GP4): REQ.missing checks them |
| net `fn` | the function the net needs from its MCU pin: `pwm`, `adc`, `spi.sck`, `spi.tx`, `spi.rx`, `spi.cs`, `i2c.sda`, `i2c.scl`, `uart.tx`, `uart.rx`, `i2s.bclk`, `i2s.ws`, `i2s.sd`, `can.tx`, `can.rx`, `onewire`, `usb.dp`, `usb.dn` – REQ.function holds it to the pin's `functions` (4.1); without `fn` the pin is a plain GPIO (bit-banged, PIO) |
| net `fn_bus` | a name the nets of one bus share (`"LED"` on SDI and CLK): REQ.function wants them on one peripheral instance (`spi0`, not `spi0` and `spi1`) |
| net `instrument`, `load_min_ohm` | an instrument comes in on the net – `"pickup"` or `"piezo"` – and the least load it wants (`1e6` for 1 MΩ, from the instrument's data): REQ.value/instrument holds the resistors and the inputs' `z_in_ohm` on it in parallel to it; the net suggests the domain guitar |
| net `signal` | `true`: the net is part of an analog signal path (audio, an effect, a measurement): in the simulation a switch, relay contact or pot whose sides are both on such nets – or on an `instrument` net – keeps them at one DC level, within 10 mV in every scenario (REQ.value/switch) |
| net `matrix` | `"row"` or `"col"` of a key matrix: every key reaches the other side through a diode, all diodes the same way (REQ.missing/matrix, REQ.forbidden/matrix) |
| net `pwm_hz` | the PWM frequency of a net with `fn: "pwm"` – a number, or `[min, max]` for one that changes (a buzzer playing notes): two PWM nets on one slice need the same fixed frequency (REQ.function) |
| `cables` | wires between boards: connector pins joined 1:1; the cable is no part. Its resistance per wire feeds the simulation: `r_ohm_per_wire`, or `length_m` with the wire's `awg` or `mm2` – copper at 20 °C, as the routed tracks (2 m of AWG 28: 0.42 Ω per wire, 50 mΩ without either); `l_nh_per_m` adds the wire's inductance, which a transient run sees (the LC spike when a cable is plugged in); its rating per wire (`i_max_a`, optional, from the cable's data – edakit derives none from the gauge) LIM.i; STRUCT.net checks the keys |
| `accept` (graph) | findings accepted for the whole graph, mostly hints taken care of: `{"HINT.bulk": "C1 1000 µF next to J1"}`, for one place only `{"HINT.bulk J2": "…"}` – chapter 14.3 |
| `layout` | the hand-over to the layout: `fixed`, `edge`, `near`, `loops`, `apart` (`[{a, b, min_mm, what}]`: two nets whose copper keeps at least `min_mm` apart on every layer, measured on the Gerber files – GEO.spacing/apart), `notes` – chapters 7.4 and 14.1; STRUCT.ref checks that the names exist |
| `purpose` | what the board is for: `use` (`private` – built for oneself, `gift` – given away, `sale` – sold, also in small series), `market` (`"EU"`), `notes` (what it is, who uses it), and for a part that transmits `radio`, optional – how its firmware uses it: `{"U1": {"bands_mhz": [[2412, 2472]], "max_dbm": 17, "notes": "Wi-Fi channels 1–13"}}` (the bands it keeps, each within the part's `bands_mhz` (4.1), and optionally the conducted power it keeps) or `{"U1": "off"}` (LIM.band, LIM.eirp) – it decides which rules the regulatory review applies (chapter 15); part of the circuit hash |
| `ground` | name of the ground net (default `GND`) – the checks, the simulation and the schematic's flags use it; STRUCT.ref checks that the net exists |
| `grounds` | further nets that are ground on purpose, `["AGND"]` – an analog ground joined at one point, an isolated side: their `ground` pins pass PATH.unfed (default: none) |
| `locks` | what the firmware relies on: `pins` (`{"U1.4": "LED_SDI"}` – pins on their nets, STRUCT.lock), `doc_pin_table` (`{component, file, prefix, regex}` – a pin table in the documentation, STRUCT.lock); part of the circuit hash, STRUCT.ref checks the names |

## 3.2 Conventions that save trouble

- **Pin numbers come from the EasyEDA symbol**, not from the datasheet. They usually agree; for LEDs and diodes they
  often do not (anode = 1 for one LED, = 2 for another of the same shape). `edakit part import C2297` reads them
  from the library without EasyEDA (4.2) and keeps the symbol, so STRUCT.entry compares the graph with it; inside EasyEDA,
  `edakit schematic create --only U3` and `easyeda_schematic_component_pins` show the placed symbol. Write the roles
  into the parts entry. Code that needs "the cathode" asks for the role, never for the pin name.
- **Net names are stable identifiers** used by firmware, simulation config and docs. Rename deliberately.
- **Voltage ranges are worst case.** `v` is what LIM.v compares with the pin limits and what the simulation checks every
  scenario against. Think about the unloaded supply, the reversed supply, a programming cable plugged in at the same time.
- **Decisions in the graph.** "Why 2 k?" – `notes: "D-9: I_OUT = 9.45 mA"`. The decision log has the reasoning.
- **One part, one LCSC number.** A footprint variant is a different part.

## 3.3 Rule checks (stages P and G)

`edakit check` runs in well under a second; put it into the pre-commit hook and CI. Every finding carries a code
`ENGINE.relation` – the engine that found it and the relation it found violated, `LIM.v` a voltage beyond its limit,
`REQ.missing` a part without what it requires – with a severity (error, warning, pending, note), sometimes a grade
(`margin`, `unknown`, …) and a topic (`REQ.missing:cc`); chapter 14.2 has the model. What a code holds, why, what to
do and the sources: `edakit rules` (the engines and their codes), `edakit explain LIM.v` (one code). Every code that
fails is explained once below the findings. `edakit domains` shows which domains of rules are on for the project
(14.2).

The codes of the graph engines – generated from the catalog, `edakit/catalog/codes.toml`; LIM and LVL judge the
simulation's values in stage E as well (5.3), the hints are in 14.3:

<!-- edakit:generated codes STRUCT LIM LVL REQ PATH PARTS DOCS -->
**`STRUCT.name`** – names unique (error; replaces G-1)  
Every designator and every net name occurs once in the graph.
- structure: unique designators and nets, every pin in exactly one net or `nc`, nets with ≥ 2 pins, a voltage range per net, a known board per part, `bom: false` on a bought board, nets across boards only through a cable; the names in `layout` and `locks`, the `ground` net, `purpose.use` – finds e.g.: a forgotten pin, a typo in a pin reference

**`STRUCT.pin`** – every pin in one net or nc (error; replaces G-1)  
Every pin of a part is in exactly one net or listed in the part's nc, a net names only pins the part has, and a pin in nc is in no net.

**`STRUCT.net`** – nets well-formed (error; replaces G-1)  
Every net has at least two pins and a voltage range v = [min, max]; a net that spans boards does so through a cable, and the two pins of a cable wire are on one net.

**`STRUCT.board`** – every part on a board (error; replaces G-1)  
Every part is on a board of edakit.toml [boards]; a part on a bought board stays out of the BOM (bom: false).

**`STRUCT.ref`** – settings name what exists (error; replaces G-1, G-16, G-25)  
Every name a setting of the graph uses – ground, grounds, locks, a reversible source, layout requirements, purpose.radio – is a part, pin or net of the graph.

**`STRUCT.purpose`** – purpose stated (error; replaces G-1, G-25)  
The graph states purpose.use – private, gift or sale – and purpose.radio, where given, is "off" or the bands (and power) the firmware keeps, each within the part's own bands.

**`STRUCT.lock`** – pins where the firmware expects them (error; replaces G-2)  
Every pin in locks.pins is on its net, and a pin table in a document (locks.doc_pin_table) lists exactly the connected pins.
- pin locks: pins the firmware relies on are on the expected nets (`locks.pins`); optionally a pin table in a Markdown document equals the graph (`locks.doc_pin_table`) – finds e.g.: firmware and hardware disagree

**`STRUCT.domain`** – suggested domains on (note)  
Every domain the graph suggests (edakit/domains, suggested_by) is named in [project] domains, when the project names its domains.

**`STRUCT.entry`** – graph pins = parts entry (error, symbol: error, declared: note; replaces P-1)  
Every part with an LCSC number or a part number has a parts entry, its pins (number and name) equal the entry's, no supply pin is in nc, and – with the library symbol cached by edakit part import – the pins equal that symbol (case and blanks ignored); the symbol gives no number to two pins and has a pin for every pad of its footprint (grade symbol). Pins the entry's symbol_differs names follow the datasheet against the symbol on purpose: left out of the comparison and named in a note with the reason (grade declared).
- graph pins (number and name) = parts entry; an entry exists for every LCSC number; no supply pin marked `nc`; with the library's symbol cached by `edakit part import`, graph pins = that symbol (case and blanks ignored, as SYNC.schematic; `accept` on the component) – not where the entry's footprint data builds the copy's symbol as a box (`"symbol": "box"`, 4.5): the carrier's library symbol is not the copy's; the cached symbol giving one number to two pins or no pin to a pad of its footprint is grade `symbol`; pins the entry names in `symbol_differs` (`{"<pin>": "reason from the datasheet"}`) are left out of the comparison and named in a note (grade `declared`) – finds e.g.: a wrong part number, pins shifted by one, an LED whose pin 1 is the cathode, a library symbol that numbers a data input like the ground pin

**`STRUCT.identity`** – graph and entry name the same part (error; replaces P-6)  
A component names the part of its entry: the entry's lcsc is its file name, the component's lcsc is no C99… user-library number (unless bom: false), its part names the entry's mpn, its value reads as the entry's value within 1 %, its type fits the entry's kind.
- part identity: the component and its parts entry name the same part – the entry's `lcsc` is its file name; the component's `lcsc` is no `C99…` user-library number (unless `bom: false`); its `part` names the entry's `mpn` (remarks in parentheses or after `;` left out, case ignored, a manufacturer before it allowed; a `part` that starts with a value, "330 Ω 0805", is compared as that value); its `value` reads as the entry's `value_ohm` / `value_f` / `value_h` within 1 % ("4k7", "100nF", "2R2"); its `type` fits the entry's `kind` (microcontroller, regulator: ic or module; transistor: npn, pnp, nmos, pmos; led: led, led_rgb; switch: switch, dip_switch; audio: buzzer; otherwise the same word); `accept` on the component. A designator prefix against the kind (R, C, L, D, Q, U, J, SW, F, BT, BZ, K, TP) is a warning – finds e.g.: C25789 written for a 74HC165 (a 464 kΩ resistor), R2 "1k" on a 10 kΩ entry, an LED that came in as U1

**`STRUCT.prefix`** – designator prefix fits the kind (warning; replaces P-6)  
The designator's letters fit the kind of its entry (R resistor, C capacitor, D diode or LED, Q transistor, U IC or module, J connector, SW switch, F fuse, BT battery holder, BZ buzzer, K relay, TP test point).

**`LIM.v`** – voltage within its limit (error, polarized: warning, inject: warning; replaces G-3, G-8, E-2, E-5)  
Every voltage a part sees stays within the limit of its entry: across a capacitor, reverse across a polarized capacitor (vr_max_v, grade polarized), an input above its own part's supply (vin_rel_max_v, grade inject), reverse across a diode or LED, VCE, VEB, VDS, VGS, on a pin (v_max_v; an active pin not below −0.3 V, a negative rail's supply pin – role vee – excepted; against the part's own ground pin where that is not the board's ground), on a fuse, switch, resistor or connector, and every limit a transient run sets on a net. Stage G takes the declared net ranges times the derating factor (1.5 on capacitors and semiconductors) – not the reverse voltage of a coupling capacitor in a signal path (a side on a net marked signal or instrument), whose range extremes never coincide –, stage E the simulated value against the derated limit.
- voltage domains: every net's range within `v_max_v` of every pin on it – finds e.g.: a 5-V signal on a 3.3-V GPIO
- voltage ratings with margin: capacitors (×1.5), diodes VRRM (×1.5), BJT VCEO, MOSFET VDS/VGS (×1.5), fuses, switches, connectors – finds e.g.: a 6.3-V capacitor on a 5-V rail
- stress of every part against its ratings with derating: resistor power ≤ 50 %, currents ≤ 80 %, capacitor/diode/transistor voltages ≤ 67 %, LED forward current and reverse voltage, fuse hold current at ambient, connector, switch and relay contact current, relay coil voltage, the current of every MCU output (`gpio_i_max_a`) and of all outputs together, sourced and sunk (`gpio_i_total_max_a`) – each pin may be fine and the sum beyond the package; the junction temperature of every part with `rth_ja_k_per_w` against its `tj_max_c`, and on a board of `touch_c` against the touch limit (5.3)
- transient limits: in every run of `transients` each limit of its `expect` – a net's lowest voltage ≥ `min_v`, highest ≤ `max_v`, a source's peak current ≤ `i_max_a` – and every MCU's supply pin, once it has reached its `vin_min_v` (`vsys_min_v`), never below it again before the run ends; actual value with the time it occurs ("2.985 V at 1.3 ms")

**`LIM.hazardous`** – hazardous voltage recognised, not checked (error)  
Every net's declared voltage range stays within the ES1 limit of IEC 62368-1 (60 V DC, catalog/tables/iec62368.toml); a net beyond it is hazardous voltage, and the finding says that edakit checks neither its spacing nor its isolation. An AC net is judged by its peak against the DC limit while the AC limit is not read.

**`LIM.i`** – current within its limit (error, margin: warning, cell: warning, supply_pin: warning, charge: warning; replaces G-17, E-2, E-3, E-5)  
Every current stays within its limit: through resistors, fuses (below the derated hold current), switches, connectors and cables, LEDs, diodes, collector and drain, an MCU's outputs per pin and together, a regulator's output, a supply's limit (sim.json sources); and what a fuse lets pass – its hold current at the lowest ambient – within every connector, switch and cable it protects. A linear charger's programmed current (values prog_v over the resistor from its PROG pin to ground) within its own i_out_max_a and the cell's i_charge_max_a – grade charge.
- fuse against what it protects: the hold current of every fuse (`i_hold_a`; at the lowest ambient `ambient_min_c` of sim.json from `i_hold_vs_temp`) is at most the `i_max_a` of every connector, switch and cable its current flows through – its own nets and on through fuses and switches; a trip current (`i_trip_a`) above it is a warning – finds e.g.: a 1.5-A polyfuse in front of a connector rated 1.25 A, an overload that heats the contacts instead of tripping the fuse

**`LIM.p`** – power within its limit (error; replaces E-2)  
Every part's dissipation stays within the derated p_max_w of its entry.

**`LIM.t`** – temperature within its limit (error; replaces E-2, E-3)  
Every part whose entry gives rth_ja_k_per_w stays at or below its junction limit (its tj_max_c, at most the criteria's) at the ambient of sim.json, and on a board people touch (touch_c) at or below the touch limit.

**`LIM.range`** – supplied inside the operating range (error, opamp: warning, gate: warning, adc: warning, clock: warning, min_load: warning; replaces E-3, E-5)  
Every part with an operating range – vdd_op_min_v … vdd_op_max_v, a pin's v_op, vin_min_v of a regulator, module or MCU, a relay's must-operate and must-release voltage, a driver output's knee – is supplied inside it in every scenario, measured at its own ground pin, and an MCU's supply never falls below its minimum again once it has reached it (transient runs). An op-amp's inputs stay inside its common-mode range (vicm_v) and its outputs inside their swing (vout_swing_v) unless it is a comparator – grade opamp. A MOSFET switch is off or on at a VGS its RDS(on) is specified at, not in between (rds_on_max_ohm as a table of VGS, vgs_th_v), the drive taken in the device's sense – VSG for a P-MOSFET, a gate driven the other way is off – grade gate. An ADC pin's voltage stays inside the converter's window (adc.range_v) – grade adc. A regulator that needs a minimum load to regulate (i_load_min_a – LM317, AMS1117) is loaded at least that much – grade min_load.

**`LIM.declared`** – net inside its declared range (error; replaces E-3)  
Every net's simulated voltage lies inside its declared range v (± the criteria's net_range_tol_v).

**`LIM.backfeed`** – no supply fed backwards (error; replaces E-3)  
The current into a source against its direction stays at or below its i_back_max_a, into a cell at or below its state's i_charge_max_a (default the criteria's blocking_max_a, 1 mA).

**`LIM.eirp`** – radio power within the band's limit (note, unknown: note; replaces G-24)  
A part that transmits stays within the e.i.r.p. limit of each EU band it transmits in (2400–2483.5 MHz 100 mW, 5150–5350 MHz 200 mW, 5470–5725 MHz 1 W): eirp_dbm, else max_dbm at the RF port + antenna_dbi, with the power the firmware keeps where purpose.radio states it. Over the limit, not known, or no bands stated: the firmware keeps the power – the severity follows the purpose.
- radio power within the band's limit: a part that transmits (`compliance.radio` with `bands_mhz`, 4.1) stays within the limit of each EU band it transmits in whose limit is an e.i.r.p. – the band's highest: 100 mW in 2400–2483.5 MHz, 200 mW in 5150–5350 MHz, 1 W in 5470–5725 MHz; its e.i.r.p. is `eirp_dbm`, else `max_dbm` (conducted, at the RF port) + `antenna_dbi`. Over the limit, not known without them, or no `bands_mhz`: graded by `purpose.use` (8.1): a warning for a board that is sold (`"sale"`), information for one built for oneself or given away, or without a purpose – the finding says what the firmware must keep ("the firmware must keep the conducted power at or below 17.0 dBm"); a radio value that is no number an error; `accept` on the component. A lower limit of a category of device, power density, duty cycle and the e.r.p. bands (433, 868 MHz) stay with the regulatory review M-6 (chapter 15 – support, not legal advice) – finds e.g.: an ESP32 module with an external 3-dBi antenna at its 20.5 dBm: 23.5 dBm e.i.r.p. where 20 are allowed

**`LIM.band`** – transmitter in the EU bands (error, firmware: note; replaces G-25)  
Every range a part transmits in lies within an EU licence-exempt band (433.05–434.79, 863–870, 2400–2483.5, 5150–5350, 5470–5725 MHz). A part that reaches into no EU band at all is an error; a range beyond the bands otherwise is the firmware's to keep (grade firmware, severity by purpose).
- transmitter in the EU bands: every range a part transmits in (`compliance.radio` `bands_mhz`, 4.1) lies within an EU licence-exempt band – 433.05–434.79, 863–870, 2400–2483.5, 5150–5350 or 5470–5725 MHz; where `purpose.radio` (3.1) states how the firmware uses the radio – `"off"`, or the bands it keeps, each within the entry's `bands_mhz` – the stated bands count. A part none of whose bands reaches into an EU band is an error – no firmware makes it comply –, unless `purpose.radio` keeps it off; a use edakit does not list (NFC at 13.56 MHz, a mobile network under the operator's licence) gets `accept` on the component with its allocation. Any other range beyond the EU bands is the firmware's to keep, graded by `purpose.use` (8.1): a warning for a board that is sold (`"sale"`), information for one built for oneself or given away, or without a purpose: `U1: 2412–2484 MHz (…) reaches beyond the EU band 2400–2483.5 MHz – the firmware must keep to 2400–2483.5 MHz (for Wi-Fi: channels 1–13)`. `purpose.radio` is optional; a statement within the EU bands ends the message, one that names no part with bands, a band the part lacks or a wrong shape is an error (chapter 15 – support, not legal advice) – finds e.g.: an ESP32 whose bands reach Wi-Fi channel 14 (2484 MHz), a LoRa module for 902–928 MHz – both passed `edakit check` without a word

**`LVL.undefined`** – input defined while the firmware is not running (error, nc: warning, open_drain: warning, analog: warning; replaces G-4)  
Every input has a driver or a pull resistor, an input that only MCU pins drive has a pull, a bipolar transistor has a base-emitter resistor and a MOSFET a resistor from its gate to its source or a rail. Graded as warnings while new: an input pin of an IC left in nc (nc), a net only open-drain or tri-state outputs drive – unless their enable pins are tied active – and that no resistor path holds (open_drain; a bridge output, drive bridge, defines its net), an analog node only capacitors reach (analog; a pin the part biases itself, biased = true, gives it its level).
- no floating input: an input needs a driver or a pull resistor; an input driven only by MCU pins needs a pull (floats until the firmware runs); every BJT needs a base-emitter resistor, every MOSFET a resistor from its gate to the source or a rail – finds e.g.: a floating OE or EN pin at power-up, a MOSFET half on while the MCU boots

**`LVL.contention`** – one driver per net (error; replaces G-5)  
At most one push-pull output or supply output drives a net.
- at most one push-pull output / supply output per net – finds e.g.: two outputs against each other

**`LVL.boot`** – strapping pins at their level at reset (error; replaces G-12)  
A pin whose entry gives strap high or low is at that level at reset: no pull, ground, supply or output on its net says otherwise, and something – an external pull or the pin's own pull – holds it there.
- strapping pins: a pin with `strap` in its parts entry is at that level at reset – no pull, rail or output on its net says otherwise, and something holds it (a pull, or the pin's internal `pull`) – finds e.g.: a pull-down on the ESP32's GPIO0, an I2C pull-up on GPIO12

**`LVL.threshold`** – logic levels reach the thresholds (error; replaces E-3)  
Every input with thresholds (vih/vil on the pin or in the values) sits at ≤ VIL or ≥ VIH in every scenario, and the high level of every MCU output reaches the VIH of what it drives.

**`LVL.direction`** – outputs only on pins that drive (error; replaces E-3)  
The simulation drives an MCU output only on a pin that can drive (output or bidirectional).

**`REQ.missing`** – what a part requires is there (error, pin: warning, balance: warning, usb_data: warning, leave: warning, matrix: warning, termination: warning, clamp: warning, feedback: warning; replaces G-6, G-11, G-13, G-14, G-18)  
What a part requires on its pins is in the graph: a capacitor to ground – or to a net of the graph's grounds – per supply pin (power_in), a pull-up per I2C line, a diode across a switched coil (cathode at its plus), Rd on each CC pin of a USB-C receptacle without controller, a layout.loops entry on each net of a hot loop (hot_loop), and what a pin's parts entry says it needs (needs: a capacitor to ground, a pull-up or pull-down, a series resistor, ground) – grade pin. Warnings while new: D+ and D− of a USB-C receptacle joined across both rows (usb_data), a series resistance on a signal net that leaves the board – through a cable, or on a connector the graph marks off_board (leave), a diode per key of a matrix (matrix), balancing resistors across capacitors in series (balance), a termination at each end of an RS-485 or CAN bus – the transceivers' pins with the roles rs485_a/rs485_b or canh/canl; one behind a switch or jumper counts closed (termination), diodes to the supply and from ground at an output without clamp diodes of its own (pin clamp = "none", the L298's bridges) that drives a winding or a connector (clamp), the divider of an adjustable regulator (values vref_v, a pin adj or fb – feedback).
- decoupling: per net at least one capacitor to ground per IC supply pin (`power_in`) – finds e.g.: the missing 100 nF
- I2C pull-ups: every I2C line has a pull-up to a supply between (V − 0.4 V) / 3 mA and 10 kΩ, parallel ones added up; a line is I2C by the net's `bus`, an SDA/SCL net name, a pin role `sda`/`scl` or a pin name with SDA/SCL (a role decides over the name); pins with `pull`/`pull_ohm` count (modules) – finds e.g.: a bus without pull-ups, 47 kΩ, a module's pull-ups plus your own below 1 kΩ
- flyback diode: a relay coil or a buzzer with `coil_ohm`, switched by a transistor or an output, has a diode across it with the cathode at its plus terminal – finds e.g.: a relay that kills its transistor at the first switch-off
- USB-C sink: a receptacle with `cc1`/`cc2` pins has its own 5.1 kΩ ± 10 % to ground on each CC pin; silent when an IC is on the CC lines. A module or breakout states its receptacle's termination in `values.usb_c` (4.1): `rd_5k1` or `controller` passes, `none` has its CC pins checked the same way and fails without them – finds e.g.: no 5 V from a USB-C charger, CC1 and CC2 on one resistor, a breakout without its two resistors
- hot loop in the hand-over: a part whose entry names its hot-loop pins (`hot_loop`, 4.1) has a `layout.loops` entry on every net of the loop – the nets of those pins and, one diode further, the net behind the rectifier on its switch node (`sw`); a buck or boost IC (`behavior`) without `hot_loop` is a warning; `accept` on the part, or on a net whose part of the loop closes over a pour – finds e.g.: a boost whose output loop was routed 61 mm across the board, passing every check because nobody listed it

**`REQ.value`** – what a part requires is in range (error, pin: warning, adc: warning, instrument: warning, gain: warning, termination: warning, failsafe: warning, window: warning, feedback: warning, switch: warning; replaces G-11, G-14)  
A required part has its value inside the range: an I2C pull-up (in parallel with the pins' own pulls) between (V − 0.4 V) / 3 mA and 10 kΩ, Rd 5.1 kΩ ± 10 % on a CC pin, what a pin needs inside the window its entry gives (grade pin), the source resistance an ADC pin sees (adc.r_source_max_ohm, unless a hold capacitor; grade adc), the DC load on an instrument input – a resistor in series into capacitors and high-impedance pins no load (net load_min_ohm; grade instrument), an op-amp's closed-loop gain against its minimum stable gain (gain_min_ratio; grade gain), a termination of an RS-485 or CAN bus of the cable's 120 Ω (grade termination), the idle voltage an RS-485 bias pair sets across the terminations at least 200 mV at the supply's lowest voltage, the far end's termination assumed where the graph holds one end (grade failsafe), a configuration pin that reads its setting by voltage window (pin windows, with the pin's own pull in the operating point) inside one window, not between two (grade window, stage E), the output an adjustable regulator's divider sets within the output net's declared range – VOUT = VREF × (1 + R2/R1) with ADJ, × (1 + R1/R2) with FB (grade feedback), and in the simulation the DC across a switch, relay contact or pot whose sides are both in a signal path (nets with signal or instrument) within 10 mV in every scenario (grade switch).

**`REQ.forbidden`** – what must stay apart is apart (error, pin: warning, address: warning, btl: warning, matrix: warning, termination: warning; replaces G-14)  
What a part forbids does not happen: CC1 and CC2 of a USB-C receptacle on one net (one resistor for both), a pin whose entry says never_to_ground on ground (grade pin), two devices on one bus at one address (grade address: base and address pins of the entries – a pin with four states, tied to low, high, SDA or SCL, adds what its entry gives for each), a bridge-tied output (roles out_p, out_n) on ground, on another part's net or on another channel's (grade btl), the diodes of a key matrix pointing both ways (grade matrix), more than two terminations on an RS-485 or CAN bus (grade termination).

**`REQ.function`** – pin functions (error, uart: warning; replaces G-15)  
A net's fn (pwm, adc, spi.sck, i2c.sda, uart.tx, …) is on a pin of a microcontroller or module whose entry lists it in functions – or that its GPIO matrix serves (entry matrix: the fn kinds routed to any GPIO; an output to a pin that drives, an input line also to an input-only pin) –, the nets of one fn_bus use one peripheral instance (not asked of a matrix), and PWM nets of one slice have one fixed pwm_hz and a channel each. A peripheral's own pin functions do not answer for the MCU. A UART line crosses: on uart.tx another part receives, on uart.rx another part transmits (grade uart).
- pin functions: a net with `fn` is on a pin whose parts entry lists that function (`functions`), the nets of one `fn_bus` on one peripheral instance, two PWM nets of one slice with the same fixed `pwm_hz` and a channel each; a net with `fn` on pins without `functions` is a note – finds e.g.: SPI data on the clock pin, an analog input without ADC, a buzzer on the PWM slice of an LED

**`PATH.reverse`** – reverse polarity blocked (error, polarized: warning; replaces G-10)  
What a reversed source (a battery holder, a source marked reversible) reaches through fuses, switches and connectors is only capacitors without polarity, holders, the anode of a blocking diode – on a negative rail (the protected net declared at or below 0 V) its cathode – or the drain of a PMOS whose source and gate are outside; a polarized capacitor it reaches is reverse biased (grade polarized).
- reverse polarity from the topology: what a reversed source (battery holders, `"source": "reversible"` on the component) reaches through fuses, switches and connectors may only be a capacitor, the anode of a diode whose cathode is outside, or the drain of a PMOS whose source and gate are outside – finds e.g.: the protection diode bypassed, an IC directly on the battery

**`PATH.unfed`** – every supply pin reached by a supply (error; replaces G-16)  
Every supply pin (power_in) is on a net a supply reaches – a power output, a battery holder, a connector with a vbus pin or marked as a source, a simulation source – directly or through fuses, switches, connectors, inductors, MOSFETs, resistors up to 100 Ω and diodes in forward direction – on a negative rail from cathode to anode.
- ground and supply pins: every `ground` pin on the ground net (or one joined to it by a 0 Ω bridge or an inductor, or in `grounds`); every `power_in` pin on a net that a supply reaches – a `power_output` pin, a battery holder, a connector with a `vbus` pin or in `"source": "reversible"` on the component, a simulation source – directly or through fuses, switches, connectors, inductors, MOSFETs, resistors up to 100 Ω and diodes in forward direction – finds e.g.: a rail split by a typo in its name, a ground pin on a net of its own, VDD swapped with a signal

**`PATH.ground`** – ground pins on ground (error; replaces G-16)  
Every ground pin is on the ground net (or one joined to it by an inductor, or in the graph's grounds), and no supply pin is on ground.

**`PARTS.verified`** – parts signed (pending, device: warning; replaces G-9)  
Every parts entry is verified against its datasheet (verified), no component has an open verify note, and every part is an LCSC part or an EasyEDA device.
- sign-off: every part `verified` against its datasheet, no open `verify` note (pending – blocks only the release) – finds e.g.: an unchecked part going into an order

**`PARTS.stock`** – parts orderable (error, margin: warning, stale: pending, unchecked: note, other_maker: warning; replaces P-4, F-2)  
For the maker of [cart] makers that orders from JLCPCB's catalogue – a failure for the planned maker, a warning for another one (grade other_maker), not run without such a maker (a note): every assembled part is listed at JLCPCB, in stock for [project] quantity boards with the assembler's attrition, under the MPN of its entry, not 'Standard Only' on an Economic order – from the snapshot of edakit stock. A thin margin, MSL 5 or more, another class: margin; an old snapshot: stale.
- parts orderable (4.2): every assembled part listed at JLCPCB, in stock for `quantity` boards (with the attrition under Standard), its entry's MPN, not "Standard Only" on an Economic order – from the snapshot of `edakit stock`; MSL ≥ 5, a thin margin, another class warn; an old snapshot is pending, none a note – finds e.g.: a part that is pre-order only, Standard-only or baked, found in the quote
- for the maker of `[cart] makers` that orders from JLCPCB's catalogue (fail as the planned maker, warning as another one, not run without it): every BOM line in JLCPCB's public assembly catalogue with stock for `quantity` boards (otherwise only pre-order), under the MPN of its parts entry; another class than `jlc_class` warns – PARTS.stock checks the same and more from the stock snapshot when the part is chosen

**`PARTS.supplier`** – supplier per part (warning; replaces P-5)  
Every part bought separately and fitted by hand (bom: false) has an LCSC number or an order entry in its parts entry ({supplier: code} or {supplier: {code, moq, step}}), so that edakit order can put it into a cart. A C99… number is an EasyEDA user-library entry, not an LCSC number: LCSC does not sell it. A warning.
- supplier per part: a part bought separately (`bom: false`) has an LCSC number – a `C99…` EasyEDA library number is none – or `order` in its parts entry (warning) – finds e.g.: a module or LED nobody wrote an order code for, found when the order list is written by hand

**`PARTS.fact`** – required facts given (note, lead: pending, functions: note, hot_loop: warning, radio: note, mpn: error, other_maker: warning; replaces P-7, G-15, G-18, P-11, P-12)  
Every fact a check needs and the profile requires is in the entry: lead for a through-hole part, functions on MCU pins a net's fn uses, hot_loop of a switching regulator, compliance.radio of a module or microcontroller, mpn and manufacturer of every assembled part with a maker of [cart] makers that matches the BOM by manufacturer part number (Eurocircuits; an error for the planned maker, a warning for another one, grade other_maker). The grade names the fact; its severity is the profile's.
- manufacturer part number (4.1): with a maker of `[cart] makers` that matches parts by manufacturer part number (Eurocircuits) every assembled part's entry names its `mpn` and its `manufacturer` – an error for the planned maker, a warning for another one – finds e.g.: a part the maker cannot match, found at its BOM upload
- radio stated: every part of graph type `module` or `microcontroller` has `compliance.radio` in its parts entry – its bands and power (4.1), or `"none"` when it does not transmit; missing is graded by `purpose.use` (8.1): a warning for a board that is sold (`"sale"`), information for one built for oneself or given away, or without a purpose – `accept` on one of its components –, other parts need it only if they transmit; a `radio` of another shape is an error. The entry is in the circuit hash: the statement renews M-1 and M-6 (8.2) – finds e.g.: an Arduino Nano whose entry says nothing about a radio – found by the regulatory review from the part's name; a plug-in board with an ESP32 its name does not show
- Eurocircuits, BOM requirements (MPN and designators required): https://www.eurocircuits.com/?p=9450 – search result of 2026-10-30, the page not reachable from the session (docs/concepts/new/ordering.md)
- Ordering at the manufacturer (docs/concepts/new/ordering.md, decided 2026-10-30): BOM with MPN and PARTS.fact/mpn, in stage P

**`PARTS.schema`** – parts entries well-formed (error; replaces G-14, G-18, G-24, P-11)  
Every field of a parts entry has the form its kind's schema gives (edakit part lint): known names with their unit, numbers where numbers belong, ranges with min ≤ max, pin roles the kind knows.

**`PARTS.library`** – copy of the parts library current (note, newer: note, draft: note)  
A parts entry copied from edakit's parts library (its field library) names the library version it was taken from: a library entry that has changed since is noted (grade newer), and so is a copy of an entry the owner has not signed (grade draft).

**`PARTS.footprint`** – footprint data complete (error; replaces P-9)  
A parts entry with footprint_data – an own footprint as text (handbook 4.5) – gives every pad its place, its shape (RECT, ELLIPSE or OVAL) and size, and a through-hole pad (MULTI) its hole; every pad number is a pin of the entry or the pad is marked mechanical, and every pin of the entry has a pad; lines, texts, polarity marks and the outline are well formed; a polarity mark '+' or '−' lies nearest to a pad whose pin role has that sign (GEO.mark's test, on the data); with "symbol": "box" the sides of the entry's symbol name pins of the entry, each once. Only where an entry of the project has footprint_data.
- footprint data complete – PARTS.footprint and SYNC.footprint only where a parts entry has `footprint_data` (4.5): every pad its place, its shape (`RECT`, `ELLIPSE`, `OVAL`) and size, a through-hole pad (`MULTI`) its hole; every pad a pin of the entry or `"mechanical": true`, every pin a pad; lines, texts, marks and outline well formed; a polarity mark nearest to a pad of its sign – GEO.mark's test (8.1) on the text; with `"symbol": "box"` the entry's `symbol` sides naming pins of the entry, each once. The same problem of several pads is one finding: `pads 1–24: shape missing` – finds e.g.: a pad the land pattern has and the entry's pins not, a "+" written next to the cathode

**`DOCS.quote`** – documents quote the design data (error; replaces G-19)  
Every value block in a Markdown file of [docs] files equals its source – a graph value, a parts entry field, the simulation result or the text of a need or requirement of [project] requirements (req:) – and every source quoted in a block or in a placeholder of the schematic notes exists; a need or requirement quoted is not dropped.
- documents quote the design data: every value block of `[docs] files` equals its source – a requirement's text too (`req:`, 3.6) –, every source of a block or a schematic-note placeholder exists, a quoted need or requirement is not dropped – run by `edakit docs` and the gate's stage G, not by `edakit check` (6.6) – finds e.g.: a description still on an old graph version, a current that changed with R1, a README with last month's R-4

**`DOCS.ref`** – requirement references resolve (error, margin: warning, draft: warning; replaces G-20)  
In the requirements file of [project] requirements, every reference of a requirement that is not dropped resolves: a need or requirement in from (N-…, R-…) stands in the files, a manual check in from or in verify signoff (M-…) is one of the sign-off file or one the gate requires, a rows pattern that starts with a code names a code of the catalog (one that starts with a check ID of before is a finding naming the codes that replace it), and verify script names an entry [scripts.<name>] of kind check or the id of a [[release.stages]]. A from that names a dropped need or requirement is a warning. About a draft – status draft, or no status – every finding is a warning in edakit check and information in the gate: a draft never blocks; it is an error once the user accepts the requirement.
- requirement references resolve – DOCS.ref to DOCS.draft only with `[project] requirements` (3.6), on every entry that is not dropped: a need or requirement in `from` (N-…, R-…) is in the files, a manual check in `from` or in `verify` `signoff` (M-…) is one of the sign-off file or a required one (8.2), a `rows` pattern that starts with a code names a code of the catalog – a check ID of before is a finding with the codes that replace it –, a `script` is an entry `[scripts.<name>]` of kind `check` or the id of a `[[release.stages]]`; a `from` that names a dropped need or requirement is a warning. Decisions, standards and words in `from` are not resolved. About a draft every finding is a warning – an error once the user accepts the requirement (3.6) – finds e.g.: `from = ["N-12"]` for N-2, `rows = "LIM.vv *"`, `rows = "E-3 *"`, `signoff = "M-7"`, a requirement that still comes from a dropped need

**`DOCS.need`** – accepted need has a requirement (error, draft: warning; replaces G-21)  
Every accepted need of the requirements file is named in from of at least one requirement that is not dropped.
- accepted need has a requirement: every accepted need is in `from` of a requirement that is not dropped – finds e.g.: a need the user accepted that no requirement made testable

**`DOCS.evidence`** – requirement has evidence (error, draft: warning; replaces G-22)  
Every requirement of the requirements file that is not dropped has evidence: at least one entry in verify – rows of the gate protocol, a manual check, a project script or a step of the acceptance test. For a draft – status draft, or no status – it is a warning in edakit check and information in the gate; an error once the user accepts the requirement.
- requirement has evidence: every requirement that is not dropped has `verify` – for a draft a warning, an error once accepted – finds e.g.: a requirement the gate has nothing to evaluate for

**`DOCS.draft`** – draft not approved (warning, draft: warning; replaces G-23)  
A need or requirement of the requirements file that is a draft – status draft, or no status – is a warning in edakit check until the user accepts it or drops it with a reason. In the gate it is information: a draft binds nothing yet – it never blocks the release and needs no acceptance; section 11 of the protocol lists a draft requirement with its evidence as evaluated.
- draft not approved: a need or requirement with `status = "draft"`, or without `status`, is a warning until the user accepts or drops it; in the gate information – a draft never blocks the release and needs no acceptance (8.7) – finds e.g.: a requirement Claude wrote and nobody approved, which the release is not held to
<!-- edakit:end -->

**0 Ω bridges.** A resistor whose parts entry has `value_ohm: 0` is copper – the usual way to cross a track on a board
with all tracks on one side. The nets it joins are one net for the engines LVL, REQ, PATH and the fuse limits of
LIM.i: a pull-up behind a bridge holds its input, a capacitor to a ground net behind a bridge decouples, two outputs
on either side clash. A finding names the joined net after the ground net if that is one of them, else after the
first of them in the graph; an `accept` on any of them counts. STRUCT, the voltages of LIM.v, PARTS and the hot loop
of REQ.missing see every net and the bridge as the graph has them (the pads of `layout.loops` lie on one net of the
graph).
`edakit check` lists the joined nets above its last line:
`joined by 0 Ω bridges, checked as one net: GND = GND_B (R11); 3V3 = 3V3_B = 3V3_C (R10, R13)`.

Severities: `error` (must be fixed), `warning` (the gate wants it accepted in the sign-off file, 8.2), `pending` (an
open sign-off, blocks only the release), `note` (information). A finding accepted in the graph – `accept` on the net
or the component, keyed by its code (3.1) – shows `(accepted)` with the reason. The profile of the project can raise
or lower a code's severity (14.2). Exit 1 on errors, with `--release` also on pending findings. The design hints
(HINT, chapter 14.3) are notes and never block.

**What went unchecked.** A code that needs a datasheet value skips a part without it: LIM.v a capacitor without
`v_max_v`, LIM.t every part without `rth_ja_k_per_w`, LVL.threshold an input without `vih`/`vil`, LIM.range an IC
without its operating range or an op-amp without `vicm_v`. `edakit check` names these gaps in one line above its last
(`not checked for lack of data: LIM.t 11 parts, LVL.threshold 1 part – edakit check --coverage`), `--coverage` lists
them per code with the designators and the field that is missing, and the gate protocol lists them in its section 2.
A gap is no finding – nothing was found, since nobody looked; it closes when the entry gets the value from its
datasheet.

Polarity (is the LED the right way round?) is not a graph rule but a simulation result: a reversed LED shows up in
stage E as "LED reversed" or as a dark LED (chapter 5), and SIM.driver makes sure no LED escapes it. G-7 was the graph's
polarity check before the codes; it was retired.

## 3.4 Working rules

1. Change the graph, never the schematic or the PCB. The hardware-change skill walks through the rest.
2. Every new LCSC number gets its parts entry first (part-search skill). A new function starts from a building block
   where one fits (`edakit block`, chapter 14.5).
3. `edakit check` and `edakit sim` before every commit that touches `hardware/` – the pre-commit hook does it.
4. A finding is fixed or accepted with a reason. Never edit a check to make a finding go away.
5. Generated files (firmware pin tables, the circuit description's parts list) are regenerated from the graph, never
   edited, and committed together with the graph change – the firmware contract with `edakit firmware` (3.5).

## 3.5 The firmware contract

Opt-in: with `[firmware]` in edakit.toml (10.1), `edakit firmware` writes what the firmware must know about the board
as neutral JSON (default `hardware/firmware.json`), and `edakit firmware --check` exits 2 when the committed file no
longer matches – for the pre-commit hook, next to `edakit check` and `edakit sim`. Without the table nothing changes.
It runs the other way round from STRUCT.lock: there the firmware is the reference and `locks.pins` hold the graph to it; here
the graph is the reference and the firmware follows. A project may use both.

| Key | Content |
|---|---|
| `graph_version`, `graph_date`, `state_sha256` | the circuit it was written from – `state_sha256` is the gate's circuit hash (8.2), so any change to graph, parts or sim config asks for `edakit firmware` again; `--check` lists what differs |
| `mcu` | the MCU it describes (`[firmware] mcu`, default the one part with pins of the role `gpio`) |
| `pins` | `{net: {pin, name, gpio, dir, pull, idle, active}}` for every connected `gpio` pin of the MCU. `gpio`: the number in the pin's name (`[firmware] gpio`). `dir`: `out` when it drives an input, an LED or a transistor's base or gate (directly or through one resistor), `in` when a button, a switch or an output drives the net, `inout` for both or only bidirectional pins, `null` when nothing says. `pull`: `{dir, by, ohm}` of the resistors to a rail or ground – on the net or behind one series resistor (a base resistor and its pull-down) –, `{dir, by: "internal"}` for a switch without one (the firmware switches the MCU's pull on), `{dir, by: "pin"}` for a pin's built-in `pull`. `idle`: the level of the pull. `active`: the level a switch gives when closed, the level that lights an LED on the pin (`leds`, with the side it is on), or for an output with a pull the opposite of `idle`. Copied from the net where they are set: `fn`, `fn_bus`, `pwm_hz` (REQ.function) |
| `pwm` | `{net: pwm_hz}` of the nets with `fn: "pwm"` |
| `inputs` | buttons and switches on MCU pins with their `active` level; a DIP switch as `bits` in the order of its roles `a1` … `aN` / `b1` … `bN` |
| `buses` | `{fn_bus: {fn: net}}`, and I2C lines by pin role `sda`/`scl` as `i2c` |
| `analog` | every MCU pin on a net with `fn` `"adc"`: `pin`, `gpio`, `channel` (the pin's functions `adc…`), the `divider` in front of it – the net one resistor from another net and one from ground: `from`, `top`, `top_ohm`, `bottom`, `bottom_ohm`, `ratio` –, or a lone `pull_up_ohm` / `pull_down_ohm` (a thermistor's partner); values from the resistors' entries |
| `devices` | `{"i2c": [{bus, address, part, how}]}` – every device on the MCU's I2C lines whose entry gives its `address` (4.1), at the address its pins decide, the bus named by its SDA net |
| `chains` | from an MCU net through the roles `sdi` → `sdo`: `data`, `parts` in shift order, `read_back` (the last `sdo` on an MCU pin), `common` (MCU nets every part of the chain shares: clock, latch, enable) and `first_bit_to` (the part fact `values.first_bit_to`, `"unknown"` without it) |
| `channels` | `{channel, chain, driver, output, pin, net, leds}` for every output with the role `out0` … `outN`, the LEDs traced as SIM.state/SIM.driver trace them: cathode on the output directly, behind 0 Ω bridges or behind a balancing resistor (5.3); `channel` = the outputs of the drivers before it in its chain + its number. A reversed LED is listed under `reversed` |

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

- **`edakit check`** (3.3) – and the gate's stage G – checks the file: every reference resolves (DOCS.ref), every accepted
  need has a requirement (DOCS.need), every requirement has evidence (DOCS.evidence), and a draft warns until the user decides
  (DOCS.draft).
- **A draft never blocks.** Every finding about a draft is a warning – a reference that does not resolve yet, no
  evidence yet –, so an unfinished file passes `edakit check` and the pre-commit hook; in the gate the findings are
  information. Errors and blocking start once the user has set `status = "accepted"`.
- **The gate** evaluates every requirement's evidence against its run (8.7): `must` without passing evidence blocks
  the release, `should` is a warning the owner accepts, `may` informs – for an accepted requirement; a draft is
  evaluated as well and binds nothing yet. Section 11 of the protocol lists every requirement with its evidence and
  the result, a draft marked as one; the acceptance steps (`accept`) join the list of section 6 that M-4 works
  through.
- **The circuit hash** covers the file byte for byte, `[release] hash_ignore` does not reach into it (8.2): a changed
  requirement voids M-1 and M-6 – the reviews read the requirements –, and with `[firmware]` the contract shows drift
  (3.5).
- **Documents quote it** by ID instead of copying the sentence: a value block
  `<!--edakit req:R-1-->…<!--/edakit-->` in a file of `[docs] files` (6.6). `edakit docs --write` fills in the
  entry's text; DOCS.quote – `edakit docs` and the gate's stage G – reports a quote that differs from the file, an ID that
  is not in it and an entry that is dropped, which no longer holds. A quote that went stale is DOCS.quote whatever the
  entry's status, a draft's too: `edakit docs --write` brings it along.
- A file the key names that is missing or not valid stops `edakit req`, `edakit check` and the gate alike.

A variant – a project of its own in a folder below the main project – reads the main project's file and its own; an
ID stands in only one of them (10.4). Both count in the variant's circuit hash.
