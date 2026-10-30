# Coverage of typical maker projects

Status 2026-10-30: research and analysis, nothing is built. What becomes a check, a hint, a block or a part fact is the
owner's decision (handbook 14.4), and every candidate below still needs its sources opened and read before it gets a
catalog entry (skill add-rule, step 2). Basis: edakit at `bf7450a`, five research clusters with 173 pitfalls from about
80 project types, and the owner's 21 repositories. Every pitfall with its numbers, its source and what covers it:
[maker-coverage-pitfalls.md](maker-coverage-pitfalls.md).

## Question

Do the checks, hints and blocks of edakit cover what typical maker projects get wrong – and what is missing?

## Short answer

- **Covered:** the class edakit grew from – boards supplied from USB or cells, with an MCU module, LEDs, buttons, a
  servo or buzzer, I2C and a radio module for the EU. Supply path, reverse polarity, back-feed between sources, voltage
  domains, logic levels with known thresholds, decoupling, strapping pins, I2C pull-ups, flyback diodes on the board,
  USB-C CC, junction and touch temperature, the board and the manufacturing files.
- **Covered only with part facts:** many frequent faults are found by existing checks once the parts entry carries the
  datasheet fact – the VIH ratio of a WS2812B (E-3), the strapping pins of an ESP32 (G-12), pin functions (G-15), GPIO
  limits (E-2). edakit ships 15 checked entries, all of them parts of its blocks. The fault found in the owner's pedal
  (below) is of this kind.
- **Not covered:**
  1. load over time – a servo or motor starting, a Wi-Fi burst, a coin cell's pulse: transients vary only the supplies;
  2. pin semantics – open-drain and tri-state outputs, unused inputs left `nc`, bus addresses;
  3. analog – ADC window and source impedance, op-amps (no model), polarized capacitors;
  4. switching parts – MOSFETs that are not logic-level, high-side P-MOSFETs driven from 3.3 V;
  5. inputs above their own supply – back-powering through clamp diodes;
  6. cables as more than a resistance – length, gauge, capacitance, inductance;
  7. audio – bridge-tied outputs, speakers, amplifier leads;
  8. hazardous voltage – spacing, isolation and input topology of mains and high-voltage boards;
  9. RF placement – the antenna keep-out of modules;
  10. support circuits a datasheet asks for (EN RC, VCAP, crystal load, USB series resistors), and kinds the graph has
      no word for: speaker, optocoupler, motor, heater.
- **Recommendation:** first load steps in transients (FT-1), pin requirements from the parts entry (CK-13) together
  with a library of checked entries for the parts makers use most (PF), and the pin semantics (CK-1 to CK-3): they
  cover the most findings per line of code. Mains and high voltage only if edakit is to take such boards; until then
  one warning that says edakit does not check them (CK-22).

## Basis and limits

- Five research agents, one cluster each: LEDs and displays (32 pitfalls), motors and robotics (35), power and
  batteries (32), MCU boards, buses, radio and keyboards (39), audio, mains, high voltage and measurement (35). Each
  pitfall comes with its numbers, the project types, the usual fix, what would detect it and its source.
- Sources are tagged **r** (read in the primary document), **x** (from a search engine's extract of the cited page)
  and **v** (to verify: the host was not reachable, or the value is from memory). The environment's network policy
  blocked most vendor hosts (ti.com, st.com, espressif.com, microchip.com, analog.com, nxp.com, pololu.com, adafruit.com
  and others); documents on GitHub were read directly – ESP-IDF, esptool, Espressif's hardware design guidelines,
  KiCad's tables of IEC 60664-1 and IPC-2221, QMK, ZMK, raspberrypi/hats, Marlin, Klipper, ArduPilot. A **v** value
  does not go into a catalog entry before it is read.
- The edakit side was read in the code, not only in the handbook: `edakit/checks.py`, `edakit/rules.py`,
  `edakit/sim/run.py`, `edakit/sim/netlist.py`, `edakit/release/polarity.py`.
- Out of scope by the owner's decision: the pinball machine (FlipperWiki).
- All 77 issues of the repository are closed, every one of them a proposal; none of the candidates below is pending.

## The owner's projects

| Project | Hardware | edakit | What of this concept applies |
| --- | --- | --- | --- |
| pytree | RP2350-Zero, 30 through-hole LEDs on three LED drivers, RGB star (common anode), magnetic buzzer, DIP switch, 3 × AA and USB-C ORed | reference project | most checks come from it; nothing new |
| automatic_christmas_bell, variants THT, SMD, ESP32 | Nano carrier (ESP32 variant: LILYGO T-Display), servo, five LEDs, two buttons, USB | released | FT-1: D-3 simulates the servo as constant 0.3 A and 0.7 A, not its start; CK-11 for the ESP32 variant: copper of the carrier under the module's antenna |
| tinyjukebox, anTONIEa | Raspberry Pi 3, RC522 (SPI, 3.3 V) in the lid on a ribbon cable, I2S class-D amplifier SHIM with speaker, four buttons with 2.2 kΩ pull-ups, RGB LED with a shunt transistor, power bank behind switch S8 | Fritzing drawing | CK-8 (bridge-tied output), FT-2 and HT-1 (SPI on a ribbon cable), E-3 `i_min_a` (power bank), E-2 contact current of S8; the README's warning about the speaker's magnet near the wiring is a reviewer question |
| AwesomeStudioPedal | NodeMCU-32S (ESP32-WROOM-32), five buttons or footswitches with 10 kΩ pull-ups, five LEDs, USB or a LiPo with regulator; nRF52840 Feather variant | wiring from CircuitSmith | G-12 with an ESP32 entry (finding below); LEDs and footswitches 30 cm and more from the board: FT-2, HT-1, CK-16; FT-4 and H-6 for the LiPo |
| asp_pro | concept: BLE-HID gateway for existing footswitches, ESP32 or nRF52840, MIDI out on DIN or TRS at 3.3 V, battery, to be sold | concept | `purpose.use = "sale"`: P-11, G-24, G-25 as warnings; BL MIDI in/out, FT-6 optocoupler, HT-6 (TRS-MIDI type A or B), HT-7 (jacks that carry a supply: expression pedal), FT-4 charger, CK-16 outputs on jacks; battery transport and battery law in M-6 |
| bustaferl | ESP32 DevKit, Waveshare 4.2″ e-paper on SPI, deep sleep, USB | firmware only | nothing new; the e-paper module is a black box (reviewer question exists); CS on GPIO 5 idles high, the strap's default level |
| system-engineering-fuer-kids | kits: tone generator, active speaker with amplifier, sound-book module | workshop, no PCB | CK-25, HT-8 – the README notes the active speaker playing with its cables not connected |
| CircuitSmith (archived) | rule catalog E1–E22 | taken over | E9, reverse protection at every power input, is opt-in in edakit (`checks.reverse_protect`): HT-6 |

Software only: FehlerJagd, agent-chat-ui, signal-backup-extract, AwesomeTaskSystem, test, antoniea-testbed, PartsLedger
(concept), and the forks easyeda-mcp-pro, rfid-2-mqtt and rpi-mfrc522 (RC522 on a Raspberry Pi over SPI).

**Finding outside edakit.** AwesomeStudioPedal's `docs/builders/BUILD_GUIDE.md` asks for a 10 kΩ pull-up to 3V3 on
every button pin, and `src/esp32/include/builder_config.h` puts button B on GPIO 12. GPIO 12 (MTDI) is a strapping pin
of the ESP32: high at reset, it sets the flash supply VDD_SDIO to 1.8 V, and a WROOM-32 with 3.3 V flash does not boot
(esptool, boot mode selection, r). Fix: another pin – GPIO 32 or 33 – or no external pull-up there, or the
flash-voltage eFuse burnt. G-12 finds it, given an ESP32 entry whose GPIO 12 has `strap: "low"`.

## What edakit covers today

| Area | Checks and hints |
| --- | --- |
| supply path | G-10 reverse polarity (topology), G-16 supply and ground pins, G-17 fuse against what it protects, H-1 bulk capacitor, H-8 two supplies on one net, E-3 regulators, minimum load, back-feed into sources and cells, E-5 plug, unplug and switch-over |
| levels and states | G-3 `vmax`, E-3 VIH/VIL and supply range where the entry gives them, G-4 floating inputs and gate/base resistors, G-5 one driver per net, G-12 strapping pins |
| stress and heat | G-8 voltage ratings, E-2 currents, power, LED current, GPIO current per pin and in total, junction and touch temperature |
| buses | G-11 I2C pull-ups, G-15 pin functions and peripheral instances, H-9 read-back edge |
| inductive loads | G-13 relay coils and magnetic buzzers on the board, H-4 a load at a connector |
| USB, radio | G-14 USB-C CC, P-11, G-24, G-25 radio statement, power and bands |
| board and files | L-1 to L-20, F-1 to F-6: copper from the Gerber files, clearances between pads, track width from the simulated current (L-5), hot loops (G-18, L-11), holes, silkscreen, manufacturing files |

## Gaps found in the code

| Gap | Where | Consequence |
| --- | --- | --- |
| G-4 looks at nets only; P-1 catches only supply pins in `nc` | `checks.py:353`, `checks.py:1158` | an unused CMOS input, a WS2815's BI pin or an A4988's RESET left `nc` passes |
| no open-drain or tri-state notion among the pin types | handbook 4.1 | INT, ALERT, 1-Wire or a fan's tach without pull-up passes; two SPI devices sharing MISO fail G-5 unless typed `bidirectional` |
| transients vary the supplies only; loads are constant | `sim/run.py:762` | a brown-out from a servo starting or a Wi-Fi burst is not simulated |
| cells have a charge limit only | `sim/run.py:545` | a CR2032 at 20 mA passes |
| G-10 counts every capacitor as harmless on a reversed source | `checks.py:137` (`REVERSE_OK`) | an electrolytic in front of the reverse protection is reverse-biased; `params.polarized` exists, only the polarity sheet reads it (`release/polarity.py:105`) |
| no check of a polarized capacitor's DC polarity in the simulation | `sim/run.py` | a coupling capacitor between stages or on ±12 V the wrong way round passes |
| G-11's upper bound is a fixed 10 kΩ | `checks.py:140` | 400 kHz and the bus capacitance of a cable are not considered |
| `fn` knows pwm, adc, spi, i2c, uart | `checks.py:144` | no I2S, CAN, 1-Wire or USB |
| behaviour models: ldo, buck, boost, mcu, cc_sink, logic, current, none | handbook 5.1 | op-amps, chargers, motor drivers and audio amplifiers are not simulated |
| part kinds without speaker, optocoupler, motor, heater | handbook 4.1 | a speaker, a MIDI input's optocoupler, a motor on the board have no model and no check |
| no I2C address, ADC window, antenna area, or spacing for hazardous voltage | – | see CK-3, CK-6, CK-11, CK-9 |
| G-8's catalog text names capacitors, diodes, transistors, MOSFETs, fuses, switches and connectors; the code also holds resistors, potentiometers, buttons, DIP switches and buzzers to `v_max` | `checks.py:443`, `rules.json` G-8 | the catalog understates the check – a text fix |

## Candidates

The kinds are those of add-rule: a **check** where a program decides without guessing, a **hint** where it takes
judgement, a **block** for a circuit worth reusing, a **part fact** for one part's datasheet, and a **feature** where
edakit lacks the capability (add-feature). "Seen" names the clusters of the pitfalls list: LED, MOT (motors), PWR
(power), MCU, AUD (audio, mains, high voltage, measurement), OWN (the owner's projects).

### Features

| ID | What | Seen |
| --- | --- | --- |
| FT-1 | **Load steps in transients.** An `external` load, an MCU's `i_core_a` and the outputs of a `current` model as `[t, A]` points in a run: a servo starting or stalling, a Wi-Fi burst (20 → 350 mA within 1 µs for 1–5 ms), a motor's start current V/R, a radio pulse from a coin cell. E-5's rule that an MCU's supply stays above `vin_min` then finds the brown-out. | MOT 16, 35; PWR 6, 18; MCU 5, 31, 32; AUD 3; LED 8; OWN bell |
| FT-2 | **Cables with length and gauge.** `length_m` and `awg` or `mm2` give `r_ohm_per_wire` (copper at temperature) and `i_max_a`; optional `c_pf_per_m` and `l_nh_per_m` feed CK-3's bus capacitance, the LC spike at hot-plug (FT-1, E-5) and HT-1. Hand-wired panel parts get a board without a PCB – today that is `bought = true`, a misleading word for it. | LED 4, 9, 10; MOT 9, 31; AUD 28–30; MCU 16; OWN pedal |
| FT-3 | **Op-amp model.** Output limited to the rails minus the swing of the datasheet, input common-mode range; E-3 holds both. | AUD 6; MCU 23, 38 |
| FT-4 | **Charger model.** Linear Li-ion charger: constant current from R_PROG (TP4056: 1200 V / R_PROG, x), 4.2 V, termination current; E-3 already holds every cell to its `i_charge_max_a`, E-2 the charger's temperature. | PWR 1–4; OWN asp_pro |
| FT-5 | **Adjustable regulators and enable.** Output from the feedback divider and `vref_v` instead of a declared `vout_v`; a regulator's minimum load (LM317 10 mA, x); a boost converter's output with EN low (VIN − VD). | PWR 13–15 |
| FT-6 | **Part kinds speaker, optocoupler, motor, heater**, and `coil_ohm` on any inductive part. Speaker: impedance, power, no DC (CK-8). Optocoupler: its LED's current at the driver's level (a PZEM's 1 kΩ at 3.3 V, x; MIDI input). Motor: winding resistance and start current. Heater: resistance, so V²/R. | AUD 1, 2, 23; MCU 30; MOT 1, 4, 21, 25–28 |
| FT-7 | **Voltage domains.** Nets above the ES1 limits of IEC 62368-1 (60 V DC, 30 V RMS AC, v) are hazardous; nets with a galvanic path from L or N are mains. The basis of CK-9, CK-10, CK-22, CK-24. | AUD 14–18, 26, 35; LED 30, 31 |
| FT-8 | **Generated fault scenarios.** A reversed supply as a DC scenario (beyond G-10's topology: shunt-diode designs, a swapped Eurorack ribbon), each wire of a cable shorted to ground at its far end, one supply off while the others are on (CK-5). | AUD 10, 11; PWR 20; MOT 15 |
| FT-9 | **DC bias of ceramic capacitors.** Capacitance against voltage in the entry; the effective value counts in CK-14 and in transients (4.7 µF, 6.3 V, 0603 X5R at 5 V: about 0.33 µF, x). | PWR 16 |
| FT-10 | **Analog constants in the firmware contract.** Divider ratios, pull-up values (a thermistor's 4.7 kΩ that Marlin and Klipper assume, r), sense resistors and ADC channels into `edakit firmware`, with drift reported. | MOT 29; MCU 22; PWR 17 |
| FT-11 | **Expectations for DC loads.** `expect` per load as transients have it: a source's current in the load "sleep" against a budget – evidence for a battery-life requirement. | PWR 10, 17 |
| FT-12 | **AC analysis** (ngspice `.ac`, `.noise`) with expected gain and corner frequency. Later: it goes against edakit's DC first. | AUD 7 |
| FT-13 | **LED strip model** with resistance per segment and injection points. | LED 9–12 |
| FT-14 | **Constant-current LED buck** (PT4115, AL8860): output current V_sense / R_S (PT4115: 0.1 V, x), headroom against the LEDs' forward voltage. | LED 19 |

### Checks

| ID | Stage | What it tests | Needs | Seen |
| --- | --- | --- | --- | --- |
| CK-1 | G | **Unused inputs are not left open:** an `input` pin in `nc` is an error unless its entry gives an internal pull or allows it to float. | `float_ok` on a pin | MCU 38; LED 13; MOT 14; gap above |
| CK-2 | G | **Open-drain and tri-state outputs:** a net whose drivers are all open-drain has a pull-up (G-11 does it for I2C only); open-drain outputs and tri-state outputs on a shared line do not clash in G-5; an output that never releases the line on a shared line does. | `open_drain`, `tristate` on pins | MCU 20, 21, 34, 39; MOT 23, 32 |
| CK-3 | G | **Unique addresses on a bus:** each device's address from its entry and the levels of its address pins; two equal ones on one bus are an error. Covers I2C (DS3231 and MPU-6050 at 0x68; PCF8574 0x20–0x27 against PCF8574A 0x38–0x3F; PCA9685's All-Call 0x70) and addressed UARTs (TMC2209: MS1/MS2). With FT-2, G-11's upper bound from the bus capacitance: Rp ≤ tr / (0.8473 · Cb) – 2.95 kΩ at 100 kHz and 885 Ω at 400 kHz for 400 pF (UM10204, r). | `address` with pins and extra addresses | MCU 15–17; LED 27, 28; MOT 14 |
| CK-4 | E | **MOSFET switch states:** on, the gate drive the circuit gives reaches a VGS at which the entry specifies RDS(on) (IRF520: only at 10 V, v); off, a P-MOSFET's gate reaches its source within \|VGS(th)\| min (a 3.3 V GPIO cannot switch off a P-MOSFET on 5 V or 12 V). | `rds_on: [[vgs, ohm], …]`, `vgs_th` | LED 17; MOT 25, 26; PWR 30 |
| CK-5 | E | **No input above its own supply:** every input stays within its part's supply plus the margin of the absolute maximum, also while that part's supply is off, and the current into its clamp within the injection limit (WS2812B DIN ≤ VDD + 0.5 V, x; ±2 mA in TI SLAA689, x). | `vin_rel_max_v`, `i_inject_max_a`; FT-8 | LED 5; PWR 20; MOT 15; MCU 26 |
| CK-6 | E | **ADC inputs:** the voltage at a pin of a net with `fn: adc` lies within the ADC's window in every scenario (ESP32 at 11/12 dB: 150–2450 mV, r; ESP8266 0–1 V, r), and the source resistance the pin sees is within the ADC's limit unless a hold capacitor sits at the pin (ATmega328P 10 kΩ, x; ESP32 0.1 µF, r). | `adc: {range_v, r_source_max_ohm, c_hold_min_f}` | PWR 17; MOT 19, 29; MCU 22, 23; AUD 6, 34 |
| CK-7 | G, E | **Polarized capacitors:** G-10 no longer counts a capacitor with `params.polarized` as harmless; E-2 holds V(+) − V(−) in every scenario to the reverse voltage the series allows. | pin roles `plus`, `minus` on polarized capacitors | AUD 7, 10, 11; gap above |
| CK-8 | G | **Bridge-tied outputs:** neither pin of a BTL pair on ground, on a net with another driver or another channel's pin, or on another part's input; the load between them is a speaker. | roles `out_p`, `out_n`, `btl`; FT-6 | AUD 1; OWN tinyjukebox |
| CK-9 | L | **Spacing of hazardous voltage:** between domains, clearance and creepage of IEC 60664-1 – at 230 V, overvoltage category II, pollution degree 2: clearance 1.5 mm basic and 3.0 mm reinforced, creepage 2.5 mm basic and 5.0 mm reinforced, a slot counting from 1 mm width (KiCad's tables, r); within a domain IPC-2221 by peak voltage – 230 V RMS is 325 V peak, 2.5 mm between uncoated outer conductors (r); a Nixie's 170 V: 1.25 mm (r). | FT-7 | AUD 14, 15, 26, 35; LED 31 |
| CK-10 | G | **Isolation and mains input:** a part with pins in two domains states its isolation (basic or reinforced, V RMS); an off-board connector in a non-isolated mains domain is an error; the first series part from L is a fuse, MOV and X capacitor sit behind it, an X capacitor above 0.1 µF has a bleeder, a capacitor across the barrier is Y-class. | FT-7; `isolation`, `safety_class` | AUD 16–18 |
| CK-11 | L | **Antenna keep-out:** no copper, via or part within the antenna area a module's entry gives, on any layer, and the antenna at or over the board edge (Espressif: over the edge, or ≥ 15 mm clear around it, r); for a module plugged over a carrier, the carrier's copper counts. | `antenna: {keepout, edge}` | MCU 6; OWN bell ESP32 variant |
| CK-12 | G | **USB-C data in both orientations:** a receptacle's D+ (A6, B6) and D− (A7, B7) are joined in pairs, or none is used; extends G-14. | roles `dp`, `dn` per contact | MCU 9 |
| CK-13 | G | **What a pin needs from the circuit**, from the parts entry: a capacitor to ground in a range, a pull-up or pull-down in a range, a series resistor, "to ground" or "never to ground". One mechanism for ESP32 EN 10 kΩ and 1 µF (r), STM32 VCAP, BOOT0, NRST, VDDA, VBAT (AN4488, r), ATmega AVCC and AREF, USB series resistors (RP2040 27 Ω, r) and the D+ pull-up, RP2040 QSPI_SS, DS18B20 DQ 4.7 kΩ (r), MAX6675 T− to ground against MAX31855 T− never to ground (x), a regulator's output capacitor. | `needs` on a pin | MCU 1, 2, 8, 10–14, 21; AUD 33; PWR 9 |
| CK-14 | G | **Capacitors a regulator needs for stability:** input and output capacitance at least the datasheet's minimum, after DC bias, and the ESR within its window (AMS1117: 22 µF tantalum, x). Can be part of CK-13. | `c_out_min_f`, `esr_ohm`; FT-9 | PWR 9, 16; MCU 5 |
| CK-15 | G | **Inductive loads beyond relays and buzzers:** G-13 for every part with `coil_ohm` and the kinds motor and solenoid; an IC's bridge output without internal clamp diodes (L298, v) at a connector has diodes to VS and GND. | FT-6; `clamp: none` | MOT 2, 21 |
| CK-16 | G | **Pins that leave the board** reach the connector through a series resistance on their own board, or the part is rated for it – a short on the wire or an ESD strike then does not hit the pin directly (emonTx: 1 kΩ and TVS, r). Warning; `waive` for USB, I2C and the like. | `short_proof` | AUD 28; MOT 31; OWN pedal |
| CK-17 | G, E | **Termination of RS-485 and CAN:** exactly two 120 Ω on the bus across all boards, RS-485 fail-safe bias where the receivers need it (idle ≥ 200 mV). | roles `a`, `b`, `canh`, `canl` | MCU 28, 29; AUD 30 |
| CK-18 | E | **Cell current:** every cell within its continuous discharge current in every scenario and within its pulse current in transients (CR2032: 3 mA continuous, x). | `i_max_a` per cell state | PWR 6; gap above |
| CK-19 | G | **Keyboard matrix:** every switch has a diode, all pairs point the same way to rows and columns, and as the firmware contract says (QMK `COL2ROW`; ZMK defaults to `row2col`, r). | roles row, column | MCU 33 |
| CK-20 | E | **Configuration pins with voltage windows:** `strap` as a table of windows, checked in the operating point with the internal pull (MAX98357A SD_MODE: < 0.16 V off, up to 0.77 V mix, up to 1.4 V right, above left, r; CH224K asks for 20 V with CFG1 open, x); extends G-12. | `strap` as windows | AUD 5; PWR 27 |
| CK-21 | E | **Supply-pin current of logic ICs:** the sum of the output currents within the supply pin's limit, as E-2 does it for MCUs (74HC595: 70 mA through VCC or GND, x). | `i_supply_pin_max_a` | LED 23 |
| CK-22 | G | **Hazardous voltage without a spacing check:** a net above the ES1 limits is a warning that edakit does not check creepage and clearance – the first step before FT-7 and CK-9. | net `v` | AUD 14–27; LED 30, 31 |
| CK-23 | E | **MCU clock against its supply:** the maximum clock at the lowest supply from the entry's curve (ATmega328P at 16 MHz needs about 3.78 V, from 10 MHz at 2.7 V and 20 MHz at 4.5 V, v). | `f_max_vs_v`, the crystal's frequency | PWR 19; MOT 35 |
| CK-24 | G | **Capacitor banks above the hazardous limit discharge:** a resistor across them brings them below 60 V within 60 s. | FT-7 | AUD 27 |
| CK-25 | G | **Analog nodes have a DC path:** a net with an `analog` input that reaches no resistor or driver to a defined level – only capacitors – floats: it picks up hum, and a switch on it pops. The analog sibling of G-4. | – | AUD 13; OWN horn |

### Hints

| ID | When | About | Seen |
| --- | --- | --- | --- |
| HT-1 | a line on a cable (with FT-2: from a length on) | inputs: pull-up of 10 kΩ or less, RC with a Schmitt-trigger input, TVS; outputs: series resistor at the source, slow edges; data and clocks: series termination, return wire beside the signal, twisted pair | MOT 31; AUD 28–30; LED 4; MCU 16; OWN pedal |
| HT-2 | a connector with a `vbus` pin | USB current budget: 500 mA (USB 2.0), 900 mA (USB 3), 1.5 A or 3 A only when the CC advertisement is read (x) | PWR 25; LED 7, 8; MCU 35 |
| HT-3 | more than 10 µF on VBUS ahead of a soft start | USB 2.0 §7.2.4.1 limits a device to 10 µF at attach (x) – against H-1's bulk capacitor; the hint names both | PWR 28 |
| HT-4 | a boost converter with EN on a GPIO | without load disconnect its output stays at VIN − VD with EN low (MT3608, x) | PWR 15 |
| HT-5 | a charger whose BAT net feeds the load | without a power path the charge never terminates (Microchip AN1149, x) | PWR 2 |
| HT-6 | a power input that is not keyed and not in `checks.reverse_protect` | no polarity standard: JST-PH batteries differ between vendors (x), barrel jacks are centre-positive or, after Boss, centre-negative; also TRS-MIDI type A or B | PWR 7, 32; AUD 11; CircuitSmith E9 |
| HT-7 | a jack whose pin carries a supply | plugging shorts tip, ring and sleeve: series resistor or PTC, no hot-plug (QMK on TRRS links, r) | MCU 34; OWN asp_pro |
| HT-8 | an audio input or output | ground loops through USB or mains earth, returns of large currents under the input's reference, the amplifier's supply shared with switching loads or a radio (filter), RF rectified at inputs on a board with a radio (RC low-pass, ferrite) | AUD 6, 8; OWN horn |
| HT-9 | `pwm_hz` on a net that switches LEDs | flicker after IEEE 1789: 100 % modulation needs ≥ 1250 Hz for low risk and ≥ 3 kHz for no observable effect; Arduino's 490 Hz allows 39 % (x) | LED 18 |
| HT-10 | a heater (FT-6) switched by one MOSFET or SSR | a second, independent interruption: thermal fuse, relay, PSU enable (Marlin, Klipper, Voron, r) | MOT 30 |
| HT-11 | a part with `rth_ja_k_per_w` | Rth(j-a) holds for the datasheet's copper; the layout must give it (hand-over) | MOT 11; PWR 3, 12; LED 20 |
| HT-12 | a motor driver | bulk capacitor at VM per driver (Pololu: ≥ 47 µF, x); a series diode in front of VM blocks the motor's returned energy | MOT 5, 9 |
| HT-13 | a filterless class-D output at a connector | ferrite or LC filter above the datasheet's lead length – a check with FT-2 and the length in the entry | AUD 1–3 |
| HT-14 | a relay whose contacts switch an off-board load | the rating is resistive; LED drivers and switch-mode supplies draw tens of amps at start, inductive loads need a snubber | AUD 20 |

### Blocks

| ID | Content | Seen |
| --- | --- | --- |
| BL-1 | addressable LED input: 74AHCT1G125 at 5 V, 330 Ω series resistor, 1000 µF | LED 1–6 |
| BL-2 | logic-level N-MOSFET low-side switch (AO3400 class, specified at 2.5 V) with gate resistor, pull-down and an optional flyback diode – `npn-switch` stops at about 100 mA | LED 17; MOT 25 |
| BL-3 | high-side P-MOSFET switch with an NPN or N-MOSFET level shift | PWR 30 |
| BL-4 | Li-ion charger with protection (MCP73831 or TP4056, DW01A, FS8205) and load sharing | PWR 1–5 |
| BL-5 | 3.3 V LDO with low quiescent current and its capacitors, rated ≥ 500 mA for an ESP32 | PWR 8–11; MCU 5 |
| BL-6 | battery voltage measurement: switched divider with hold capacitor | PWR 17 |
| BL-7 | ESP32 module support: EN 10 kΩ and 1 µF, BOOT button, auto-program with two NPN, 10 µF and 0.1 µF | MCU 1, 2, 5 |
| BL-8 | USB-C with data: D± of both rows joined, USBLC6-2, 5.1 kΩ per CC pin, polyfuse | MCU 8, 9 |
| BL-9 | I2C level shift (BSS138 at 100 kHz, or PCA9306) | MCU 18, 19 |
| BL-10 | RS-485 at 3.3 V (MAX3485 class) with switchable termination, bias, DE pull-down | MCU 28 |
| BL-11 | MIDI in (6N138, 220 Ω, 1N4148, pin 2 open) and MIDI out (220 Ω/220 Ω at 5 V, 33 Ω/10 Ω at 3.3 V, v) | MCU 30; OWN asp_pro |
| BL-12 | cable input: pull-up, RC, TVS | AUD 28, 29; MOT 31 |
| BL-13 | servo connector with bulk capacitor | MOT 16 |
| BL-14 | DC motor driver (DRV8833 or TB6612) with VM capacitors | MOT 1–5 |
| BL-15 | Eurorack power entry: keyed 10- or 16-pin header, series Schottky per rail, 10 µF | AUD 10 |

### Part facts

The checks of the catalog fire only where entries carry the datasheet: `strap`, `functions`, `vih_ratio`, `vdd_op_min`,
`rth_ja_k_per_w`, the GPIO limits. A library of checked entries for the parts makers use most turns on G-12, G-15, E-2
and E-3 without a line of code – and then CK-3, CK-6, CK-13 and CK-20 where they are built:

- modules: ESP32-WROOM-32, ESP32-S3 and ESP32-C3 modules (straps, input-only and flash pins, ADC2, peak current,
  radio, antenna area), NodeMCU-32S, Wemos D1 mini, Arduino Nano, RP2040 and RP2350 boards (the Pico 2 is in the
  example);
- LEDs and displays: WS2812B per revision (VIH 0.7, 0.63 or 0.55 × VDD, x), SK6812, APA102, SSD1306 module, PCF8574 and
  PCF8574A backpacks, MAX7219;
- power: AMS1117-3.3, a low-quiescent LDO, TP4056, MCP73831, DW01A with FS8205, MT3608, CH224K;
- switching and drivers: AO3400, IRLZ44N, IRF520 (as the counter-example), DRV8833, TB6612, L298N, A4988, DRV8825,
  TMC2209;
- sensors and buses: DS3231 (with the module's AT24C32), MPU-6050, BME280, INA219, INA226, DS18B20, HX711, ACS712,
  HC-SR04, MAX31855, MAX6675, CH340, CP2102, MAX485, MAX3485;
- audio: MAX98357A, PAM8403, INMP441.

### Reviewer questions

What stays judgement goes into the questions of the reviewers, as "Not covered by a check yet" does today:

- electrical-reviewer – **audio and analog:** ground loops, shared returns under references, supply filtering for
  amplifiers and microphones, RF rectification at inputs; **cables:** length, what is on them, what a short or an ESD
  strike at the far end reaches;
- pcb-reviewer – **RF:** antenna areas of modules and of modules plugged over the board; **hazardous voltage:** spacing
  between domains, slots; **thermal pads:** copper and vias under exposed pads.

## Priority

Ordered by how often the pitfall appeared across the clusters, what it costs when it happens, and how much it takes:

| # | Candidate | Why first |
| --- | --- | --- |
| 1 | FT-1 load steps | in all five clusters; the most frequent "it resets when the motor starts"; the bell's servo |
| 2 | CK-13 with PF | one mechanism for about 15 pitfalls; the knowledge stays in parts entries, as `strap` and `pull` do |
| 3 | CK-1, CK-2 | small changes to G-4 and G-5; floating inputs and missing pull-ups recur in four clusters |
| 4 | CK-3 | fully decidable, frequent in sensor stacks |
| 5 | CK-4 | IRF520 modules and high-side P-MOSFETs: a hot part or a load that never switches off |
| 6 | CK-6 | in four clusters; every battery, thermistor and current measurement |
| 7 | CK-7 | a gap in G-10 itself; audio and ±12 V |
| 8 | CK-5 with FT-8 | dead first pixels, half-powered drivers |
| 9 | CK-11 | a board respin when it is missed |
| 10 | FT-2 with HT-1, CK-16 | the owner's pedal; cable length is a question that comes back |

For the owner's projects in particular: CK-8 (tinyjukebox), BL-11 and FT-6's optocoupler (asp_pro's MIDI), HT-7
(jacks with a supply), FT-4 (asp_pro's battery), CK-11 (ESP32 boards).

Mains and high voltage (FT-7, CK-9, CK-10, CK-24) prevent the most expensive faults – shock and fire – but none of the
owner's projects has them. CK-22 says honestly what edakit does not check and costs a few lines; the rest follows when
edakit is to take such boards.

## Out of scope

- Radiated emission and immunity as field strengths, transmission lines – the hints and the reviewers cover them.
- Settings that live in firmware only: SPI mode, motor PWM frequency, debounce times, brown-out levels – hints, the
  firmware contract, and H-9 where a part of the circuit decides.
- Certification itself: the regulatory review (M-6) is support, not a test lab.
- The pinball machine (owner's decision).

## Open decisions

1. Which candidates become proposals – one issue each through `/edakit:propose-rule` and `/edakit:propose-feature`,
   or built directly with add-rule and add-feature.
2. Whether edakit takes boards with mains or high voltage (FT-7, CK-9, CK-10), or only says that it does not check them
   (CK-22).
3. Whether a library of checked entries for popular parts (PF) belongs into edakit – who signs them, and how a project
   takes one over (today: `edakit/blocks/parts/`, copied by `edakit block add`).
4. Whether AC analysis (FT-12) fits edakit's DC-first approach at all.
5. The network policy: the vendor hosts the sources need (ti.com, st.com, espressif.com, microchip.com, analog.com,
   nxp.com, pololu.com, adafruit.com, onsemi.com, diodes.com, vishay.com, infineon.com, allegromicro.com, midi.org,
   usb.org) are allowed in the environment, or the sources are read on a machine that reaches them.

## Sources

Per pitfall with its tag in [maker-coverage-pitfalls.md](maker-coverage-pitfalls.md). The documents read in full (r):

- Espressif: ESP32 Hardware Design Guidelines (schematic checklist, PCB layout), ESP32-S3 Hardware Design Guidelines
  v1.2, esptool `docs/en/advanced-topics/boot-mode-selection.rst` and `troubleshooting.rst`, ESP-IDF GPIO and ADC
  documentation (v4.4 and current), ESP-IDF `Kconfig.system` (brown-out levels)
- Raspberry Pi: "Hardware design with RP2040", `raspberrypi/hats` design guide
- ST AN2867 Rev 5 (oscillator design), ST AN4488 Rev 7 (STM32F4 hardware), NXP UM10204 Rev 7.0 (I2C)
- KiCad `pcb_calculator`: IEC 60664-1 tables (F.1, F.2, F.5) and IPC-2221 spacing and track width
- QMK `docs/config_options.md`, `how_a_matrix_works.md`, `features/split_keyboard.md`, `drivers/serial.md`,
  `platformdev_rp2040.md`; ZMK `docs/config/kscan.md`
- Marlin `Configuration.h` and `Configuration_adv.h`; Klipper `docs/TMC_Drivers.md`, `Config_Reference.md`; ArduPilot
  "Powering the Pixhawk"; Voron documentation, electrical
- OpenEnergyMonitor CT and AC-AC documentation; Tasmota "Getting Started" and PZEM-0XX; ESPHome I2C, 1-Wire, ADC and
  AC dimmer documentation
- SparkFun Weather Meter Kit library, SparkFun BOB-12009 schematic; RF24 `COMMON_ISSUES.md`; RadioLib troubleshooting;
  RobTillaart PCF8574, INA219, INA226 and ACS712 READMEs; bogde/HX711 and olkal/HX711_ADC; autowp/arduino-mcp2515;
  sandeepmistry arduino-CAN and arduino-LoRa; Arduino `analogWrite` reference; ArduinoCore-avr `boards.txt`; MiniCore
