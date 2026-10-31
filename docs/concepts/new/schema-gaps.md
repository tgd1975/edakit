# Schema gaps found while writing the parts library

Status 2026-10-31: decided (rules-at-scale.md, decisions 10 and 11) and built – the state per item at the end. While writing the 51 library drafts in `edakit/parts/` from their datasheets
(rules-at-scale.md, decision 8), seven agents reported facts the parts schema (`edakit/catalog/kinds.toml`) has no
field for, and places where edakit's checks judge a correct circuit wrongly. They are grouped here, with how many of
the seven groups (modules, LEDs and displays, power, switching, sensors, buses, audio) met each, and a proposal per
theme. The six block agents that built BL-1 to BL-18 on these entries added theirs (section I).

Fixed already on the way: a threshold `[min, null, max]` that crashed the gate check, the flyback finding on drivers
that clamp their windings themselves (pin `clamp`), the fix text for an unbiased RS-485 B line, the supply current
fields `icc_a` and `i_a`; and twelve false alarms the block agents met (tests/test_false_alarms.py): a negative rail's
series diode (PATH.reverse, PATH.unfed), simulation noise against a limit of 0, a V− supply pin against the −0.3 V
floor, a tristate output with its enable tied active and a net held through a resistor chain (LVL.undefined), a
termination behind a switch and the failsafe bias at the supply's minimum, an input tied to a rail, decoupling to a
net of `grounds`, a P-MOSFET's gate drive in its own sense, HINT.esd, HINT.gate, HINT.debounce, HINT.cable_line and
HINT.lithium where they did not fit, the load on an instrument input through a series resistor.

## A. Findings that are wrong – first

| # | Gap | Met by | Effect today | Proposal |
|---|---|---|---|---|
| A1 | PWM (and UART, I2C …) routable to any GPIO through a matrix (ESP32, S3, C3) | modules | a net with `fn: pwm` on these modules: a false REQ.function error | an entry field `matrix = ["pwm", "uart", "i2c", "spi"]` – functions every GPIO of the part offers |
| A2 | a bridge output (drives high, low or off) | switching | typed tristate: LVL.undefined/open_drain on every motor net | pin `drive = "bridge"`: defines its net while enabled, contention like a push-pull output |
| A3 | an analog pin biased inside the part (PAM8403 INL/INR) | audio | LVL.undefined/analog through its coupling capacitor | pin `biased = true` |
| A4 | address pins with four states (GND, VS, SDA, SCL – INA219, INA226) | sensors | a pin tied to SDA reads as high: a wrong address, a false REQ.forbidden/address | `address.pins` maps a pin to its four values |
| A5 | a peripheral's bus pins with functions | audio | listed functions would hide an MCU pin that cannot do I2S | REQ.function counts only the functions of microcontroller and module pins |
| A6 | `vin_rel_max_v` per part | power, LEDs, buses | flags pins rated above the supply (TP4056 CE, CH224K CFG1); never holds outputs and bidirectional pins | per pin `v_rel_max_v` with the pin it refers to (B1) |
| A7 | a multiplexed LED matrix driver (MAX7219) | LEDs | LEDs between segment and digit pins fail SIM.driver | a behaviour `matrix_driver`, or the LEDs exempted from SIM.driver with the reason |

## B. Limits relative to a pin

| # | Gap | Met by | Proposal |
|---|---|---|---|
| B1 | thresholds as ratios and limits above a supply refer to a named supply pin – VLOGIC (MPU-6050), VDDIO (BME280), VCC | sensors, LEDs, buses, power | pin field `ref = "<pin name>"` for `vih_ratio`, `vil_ratio`, `v_rel_max_v`; default the part's supply as today |
| B2 | one supply never above another (VLOGIC ≤ VDD) | sensors | an entry field `supply_order = [["VLOGIC", "VDD"]]`, judged on the declared ranges |
| B3 | a limit only while powered (RP2350 fault-tolerant 5.5 V) | modules | `v_max_v` stays the unpowered value; `v_max_powered_v` beside it |

## C. Per-pin currents and negative limits

| # | Gap | Met by | Proposal |
|---|---|---|---|
| C1 | current per pin (PCF8574 25 mA, MAX7219 500 mA digit sink, AVR 40 mA) and per group of pins (AVR ports) | LEDs, modules, buses | pin `i_max_a`, entry `i_group_max_a = {"name": [pins, A]}` – LIM.i on the simulated pin currents |
| C2 | negative limit per pin (RS-485 −7.5 V, ACS712 −0.1 V) | buses | pin `v_min_v` |
| C3 | injection current through the protection diodes (PCF8574 400 µA) | LEDs | pin `i_inject_max_a`, with LIM.v/inject |
| C4 | minimum load resistance, maximum load capacitance of an output (ACS712, amplifiers) | buses, audio | pin `r_load_min_ohm`, `c_load_max_f` |

## D. What a pin needs

| # | Gap | Met by | Proposal |
|---|---|---|---|
| D1 | a capacitor between two pins (charge pumps CP–VCP, thermocouple T+–T−, VCP to VM) | LEDs, switching, buses | `needs.capacitor.to = "<pin>"` beside the default ground |
| D2 | a crystal with its load capacitors (CH340G) | buses | `needs.crystal = {f_hz, tol_ppm, c_load_f}` and a kind crystal |
| D3 | tie to a supply (BME280 CSB to VDDIO), no external pull-up (DS3231 RST), must not float, never a series resistor | sensors, buses | `needs.tie`, `needs.no_pull`, `float_ok = false` for bidirectional pins, `needs.no_series` |
| D4 | the voltage rating a required capacitor needs (MPU-6050 CPOUT 50 V) | sensors | `needs.capacitor.v_min_v` |
| D5 | an upper bound local to a pin when the net carries more (DS3231 0.1–1 µF) | sensors | the window judged on the capacitors within the pin's layout.near, not the net's sum |

## E. Behaviour in the simulation

| # | Gap | Met by | Proposal |
|---|---|---|---|
| E1 | a sensor, transceiver or USB-UART draws its supply current | sensors, buses, audio, LEDs | the entries use behaviour `logic` with `icc_a` (the field exists since the merge of FT-21); a pass over the drafts |
| E2 | bridge drivers (DRV8833, TB6612, L298 …) | switching | behaviour `bridge`: outputs follow their inputs, `r_out_ohm` high and low side |
| E3 | linear chargers: CC/CV, termination, precondition, UVLO | power | behaviour `charger` (FT-4's rest), fields from the TP4056 and MCP73831 datasheets |
| E4 | a cell protection IC and a dual MOSFET (DW01A with FS8205A) | power | behaviour `protection` with its thresholds; a kind `dual_nmos` with both channels |
| E5 | a USB PD sink (CH224K) with its VDD shunt regulator | power | behaviour `pd_sink`; until then `sim: false` for blocks that use it |
| E6 | a buck-boost regulator (the Pico's RT6150) | modules | `buck_boost` in the regulator enum |

## F. Modes and configurations

| # | Gap | Met by | Proposal |
|---|---|---|---|
| F1 | supply configurations (CH340 at 5 V or 3.3 V, CP2102's three) | buses | entry `configs = {name: {pins and ranges}}`, the graph names the one it uses |
| F2 | pin roles that depend on the interface mode (SSD1306 D0/D1 as SCL/SDA) | LEDs | the same `configs` |
| F3 | needs that hold only in one mode (DS18B20 parasite power, DS3231 VBAT, HX711 VBG, INA226 Alert) | sensors | `needs.when = "<config>"` |

## G. Values of single kinds of parts

Fields that one group met, for later: amplifier gain settings, minimum load and required series inductance; a
current sensor's sensitivity and isolation, and its conductor path inside the part (the simulation sees IP+ and IP−
unconnected); the clock limit of any part on a bus (`f_max_hz` is read for MCUs only); a PWM frequency limit and a
supply ramp rate; `r_out_ohm` high and low side, a bipolar output's saturation drop; ambient against junction
temperature; ADC unit and channel apart, the ADC window per attenuation; a smart LED's colour and per-channel current;
an unclocked chained output's delay; storage temperature.

## H. Errors in the EasyEDA library data

The agents compared every pinout with the EasyEDA symbol that `edakit part import` caches, and found four that differ
from the manufacturer's datasheet. The library entries follow the datasheet (or keep the symbol's names with the
datasheet's roles and a hint, where handbook 4.4 asks for the symbol's names); STRUCT.entry compares a graph with the
cached symbol. A project that draws its schematic from these symbols gets a wrong netlist:

- WS2812B-V5/W (C2874885): DIN numbered 3 like VSS – DIN lands on ground, pad 4 open.
- XC6206P332MR-G (C5446): pin 2 named Vin, pin 3 Vout – Torex: pin 2 VOUT, pin 3 VIN; the regulator fed backwards.
- DRV8825PWPR (C81582): no pin for the PowerPAD (footprint pad 29).
- Raspberry Pi Pico 2 (C41407547): pins 2–6 named TP2–TP6, 41 and 43 swapped. The example project carried the swap
  of 41 and 43 as well; it is corrected (41 SWCLK, 43 SWDIO).

## I. From the blocks

| # | Gap | Met by | Proposal |
|---|---|---|---|
| I1 | LIM.v judges a part's pins against GND, not against the part's own ground pin (DW01A on the cell's minus) | power blocks | `pin_voltages` takes each part's ground net, as stage E's `at_pin` does |
| I2 | a sim.json source has one plus and one minus – a ±12 V header cannot feed both rails | Eurorack | a source with several outputs `{plus: [pins], minus}` |
| I3 | a relay with two contact sets (DPDT) – the simulation switches the first only | guitar | roles per set (`common_2`, `no_2`, `nc_2`) |
| I4 | a photo-MOS (a resistance both ways when lit), an optocoupler's detector supply, a pass-gate translator (PCA9306), a multi-diode ESD array | guitar, interfaces, MCU/USB | behaviours `photomos`, `pass_gate`; the ESD array as a kind with its lines |
| I5 | a net isolated from board ground (a MIDI in loop) | interfaces | a net key `isolated = true` that the ground checks skip |
| I6 | a relay contact's minimum switching load (gold contacts), a DIP switch's switching against carrying current, a connector's current per contact | guitar, interfaces, MCU/USB | contact fields `min_load_a`, `i_switch_max_a`, `i_contact_max_a` |
| I7 | LIM.v/polarized in stage G pairs the top of one net's range with the bottom of the other's across a coupling electrolytic – states that never coincide | guitar | judged on the operating points of stage E only, or a grade the domain audio lowers |
| I8 | a block cannot set graph keys (`grounds`), mark a part or port optional, or remove a supply in its test | all blocks | block keys `graph`, `optional`; the test's `sim` merged deeply |
| I9 | an accept on a net cannot name one designator or place – a port net's accept covers the project's rail | MCU/USB, Eurorack | accept keys `code place` on a net, as on the graph |

## Order proposed

A first – each is a finding that is wrong today –, with I1 and I7. Then B1, C1 and D1, which several groups met and
which make checks of existing codes hold on more pins. E1 is a pass over the drafts with fields that exist. E2 to E6, F and G when a
project needs them. H goes to the owner: whether edakit should check a cached symbol against its entry beyond the pin
names (STRUCT.entry), and whether the four symbols are reported to EasyEDA/LCSC.

## State after the build (2026-10-31)

Built in seven worktrees (W1–W7) and merged; each item with a test that is red without it.

| Items | State | Where |
|---|---|---|
| A1–A5, A7 | built | entry `matrix`, pin `drive = "bridge"`, pin `biased`, address pins `{low, high, sda, scl}`, REQ.function on MCU and module pins only, behaviour `matrix_driver` (W1) |
| A6, B1–B3, C1–C4 | built | pin `ref`, `rel_ref`, `v_rel_max_v`, `v_max_powered_v`, `v_min_v`, `i_max_a`, `i_inject_max_a`, `r_load_min_ohm`, `c_load_max_f`; entry `supply_order`, `i_group_max_a`; grades LIM.v/powered, LIM.v/order, LIM.i/pin, REQ.value/load (W2) |
| D1, D2, D4, D5 | built | `needs.capacitor.to`, `needs.crystal` and kind `crystal`, `needs.capacitor.v_min_v`, a capacitor window on the parts layout.near places (W3) |
| D3 | in part | `needs.tie`, `no_pull`, `no_series`, `float_ok = false` built; the BME280's CSB and SDO, which hold only in I2C mode, wait for an entry with `configs` (F1 exists now) |
| E1 | in part | `logic` with `icc_a` on AT24C32D, INA219, DS18B20; the model holds every output low, so parts with outputs wait for a `logic` that lets released outputs go |
| E2, E3, E4, E6 | built | behaviours `bridge`, `charger`, `protection`, `buck_boost`; roles `gate_2`/`source_2`/`drain_2` for a dual MOSFET (W4) – not modelled: a charger's termination, the DW01A's hysteresis and delays |
| E5 | in part | behaviour `pd_sink` with REQ.value/pd_request (W5) – PG, the CC lines and the negotiation not modelled |
| F1–F3 | built | entry `configs`, `config_default`, a component's `config`, needs with `when` (W6) |
| I1, I7 | built | LIM.v against a part's own ground pin; LIM.v/polarized leaves signal coupling to stage E (W1) |
| I2–I4 | built | sim.json source with `outputs`, relay roles per contact set, behaviours `photomos`, `pass_gate`, kind `esd_array` (W5) |
| I5, I6, I8, I9 | built | net `isolated`, `i_contact_max_a`, `i_switch_max_a`, `min_load_a`, block keys `graph`, `optional`, `block add --without`, accepts `"code place"` (W6) |
| H | built | STRUCT.entry/symbol and `symbol_differs` (W7); the report `upstream/issue-6-easyeda-symbols.md`, not sent – the owner sends it |
| G | open | not part of decision 10 |

Decided on the owner's behalf (rules-at-scale.md, decisions 13–15): the MPU-6050's SCL/SDA stay held to
VLOGIC + 0.5 V; the 10 µA a contact in a signal path may need at most stays, sourced to the Hongfa HFD4's
minimum applicable load; the INA226's Alert is held to VS + 0.3 V like SCL.