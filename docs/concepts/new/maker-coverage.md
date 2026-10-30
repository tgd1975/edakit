# Coverage of typical maker projects

Status 2026-10-30: research and analysis, nothing is built. What becomes a check, a hint, a block or a part fact is the
owner's decision (handbook 14.4), and every candidate below still needs its sources opened and read before it gets a
catalog entry (skill add-rule, step 2). Basis: edakit at `bf7450a`, seven research clusters with 249 pitfalls from
about 80 maker project types and the guitar's pedals, instrument and amplifiers, and the owner's 21 repositories. Of the
249, 50 are covered, 11 covered once the parts entry carries the datasheet value, 69 partly and 119 not – some of
those judgement or out of scope. Every pitfall with its numbers, its source and what covers it:
[the appendix](#appendix-the-pitfalls). The concept is a backlog, not a build list (section "Keeping the catalog
stable").

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
      no word for: speaker, optocoupler, motor, heater;
  11. guitar circuits – the input impedance a pickup needs, op-amps at 9 V, DC at switches and pots, the bias spread of
      discrete stages.
- **Stability:** today the catalog is quiet – 0–1 waiver per board on the bell, 7 for the reference project's 84
  parts. Built one by one, the candidates would about double it, mostly without a real project to test them against.
  Seven mechanisms cover 91 of the 128 open maker pitfalls; with a coverage report, domains per project and a project
  as the trigger for every build, it stays stable (section "Keeping the catalog stable").
- **Recommendation:** first the coverage report (FT-19) and domains (FT-20), then load steps in transients (FT-1), pin
  requirements from the parts entry (CK-13) together with a library of checked entries for the parts makers use most
  (PF), and the pin semantics (CK-1 to CK-3): they cover the most findings per line of code. Mains and high voltage
  only if edakit is to take such boards; until then one warning that says edakit does not check them (CK-22).

## Basis and limits

- Seven research agents, one cluster each: LEDs and displays (32 pitfalls), motors and robotics (35), power and
  batteries (32), MCU boards, buses, radio and keyboards (39), audio, mains, high voltage and measurement (35), guitar
  effect pedals (37), and the guitar's instrument, amplifiers, DI boxes and switching (39). Each pitfall comes with its
  numbers, the project types, the usual fix, what would detect it and its source. The guitar clusters read
  ElectroSmash's circuit analyses in a GitHub archive (mstratman/electrosmash-pdf-backups) and the FV-1, TL07x and
  CA3080 datasheets in GitHub repositories; most other guitar sources were search extracts (x).
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
| system-engineering-fuer-kids | kits: tone generator, active speaker with amplifier, sound-book module | workshop, no PCB | HT-8, HT-13, HT-1 – the active speaker played the sound module's sound with no connection between the two (topic "Audio") |
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

## Topics in depth

The owner's questions during the analysis, each answered against the code.

### Communication between ICs

edakit checks the electrical side of a link between ICs, not its protocol or its timing.

| Link | Checked today | Missing |
| --- | --- | --- |
| every link | G-15: a net's `fn` (`spi.sck`, `spi.tx`, `spi.rx`, `spi.cs`, `i2c.sda`, `i2c.scl`, `uart.tx`, `uart.rx`, `pwm`, `adc`) on a pin that has the function, the nets of one `fn_bus` on one peripheral instance; G-3 and E-3 levels between the parts; G-4 a select or enable input that only the MCU drives has a pull; G-5 two push-pull outputs on one net | `fn` for I2S, CAN, 1-Wire and USB (FT-15) |
| SPI | H-9 the read-back edge; the firmware contract: chain order (`first_bit_to`), read-back | MISO shared by several devices fails G-5 unless typed `bidirectional`, and a device that never releases MISO is not found (CK-2); SPI mode and maximum clock per device (FT-16); SPI on a ribbon cable (HT-1 – tinyjukebox's RC522 in the lid) |
| I2C | G-11 the pull-up window, the pull-ups of modules summed | addresses (CK-3); bus capacitance and speed (CK-3 with FT-2); the speed of level shifters (BL-9) |
| UART | G-5 TX on TX; G-4 RX on RX without a pull | RX on RX with a pull-up passes (CK-26); a 5 V TX into a 3.3 V RX is G-3 |
| open-drain lines | I2C only | INT, ALERT, 1-Wire, a fan's tach, a wired-OR reset without pull-up (CK-2) |
| differential | – | RS-485 and CAN termination and bias (CK-17); USB-C D± in both rows (CK-12); USB series resistors (CK-13) |

### Cables and off-board parts

A cable is a connection between two boards (`cables` in the graph): `r_ohm_per_wire` gives the simulation its voltage
drop, each board with a ground of its own, and `i_max_a` per wire holds G-17. A length, a capacitance, an inductance,
coupling and ESD on the cable are not known; H-7 (ESD at connectors), H-4 (inductive load at a connector) and H-3
(debouncing) touch the subject.

The pedal's LEDs at 30 cm and more from the board show what matters:

1. **DC is no issue:** 30 cm of AWG26 is about 0.04 Ω – 0.4 mV at 10 mA.
2. **Where the series resistor sits:** on the board. Soldered to the LED's leg, a wire pinched against the enclosure
   shorts the GPIO to ground; nothing checks that today (CK-16, FT-8).
3. **ESD** through the LED's bezel and the footswitch reaches the GPIO over the wire; H-7 reminds, it checks nothing.
4. **Emission,** for a board that is sold (asp_pro): PWM edges on 30 cm wires radiate – slow edges at the source, the
   return wire next to the signal.
5. **Inputs on long wires** – the footswitches – catch interference: the build guide's 10 kΩ pull-ups are there for
   it, RC with a Schmitt-trigger input and debouncing (H-3) go with them.

Modelled today: the panel parts – LEDs, footswitches, jacks – on a board of their own with `bought = true`, joined by
`cables`; the simulation then checks every LED's polarity and current, and H-7 sees the lines. `bought` means "no PCB"
here, which the word does not say (FT-2). Candidates: FT-2, CK-16, FT-8, HT-1, CK-3 for I2C on a cable.

### Audio: hum, transmitter, receiver

The simulation knows DC operating points and supply transients; frequency response, noise and coupling it does not
know. There is no part kind for a speaker – the graph type `audio` maps to the kind `buzzer` – and no op-amp model, so
an op-amp preamp is not simulated at all. G-6, G-8, E-2 and the hot-loop check (G-18, L-11, where a class-D amplifier's
entry gives `hot_loop`) apply as anywhere.

| Class | Mechanism | Decidable | Candidate |
| --- | --- | --- | --- |
| hum | ground loop between devices – amplifier, PC on USB, earthed equipment | no: it forms outside the board | HT-8 |
| hum | returns of the output stage, LED PWM, a servo or a Wi-Fi burst through the input's reference ground | as a layout requirement | HT-8, reviewer |
| hum | ripple of switching loads on the amplifier's supply (PSRR) | partly, from the topology | HT-8 |
| hum | an analog input without a DC path floats and catches 50 Hz | yes | CK-25 |
| transmitter | filterless class-D (PAM8403, MAX98357A, PAM8302) drives a square wave of several hundred kHz onto the speaker leads | with the lead length and the datasheet's limit | HT-13, FT-2 |
| transmitter | PWM and clock lines on cables | – | HT-1 |
| receiver | RF rectified at the first junction of an audio input – the board's own Wi-Fi or BLE bursts, a mobile phone, the PWM speaker leads of a device nearby | partly: a board with a radio and an audio input without RC low-pass | HT-8 |
| receiver | high-impedance inputs on long leads – guitar 1 MΩ, piezo, electret | – | HT-1 |
| receiver | magnetic coupling – a speaker's magnet, coils next to leads and sensors (tinyjukebox's README) | no | reviewer |

Beyond these: bridge-tied outputs (CK-8), DC on a speaker (FT-6), the pop at power-up (`strap` with G-12, CK-20), an
op-amp's operating point (FT-3), outputs on jacks shorted while a plug goes in (CK-16, HT-7); level, impedance and
frequency response only with AC analysis (FT-12).

**The owner's case – the steering wheel of system-engineering-fuer-kids.** The active speaker (a DIY kit from Conrad)
played the sound module's donkey with no connection between the two: each ran from a battery of its own, no wire, no
common ground. Shorter and shielded cables – and luck – made it work. Without a conductive path only fields couple:

- **electric (capacitive):** sound-book modules drive their speaker directly, often with PWM or a bridge output, so the
  module's speaker leads swing with steep edges; an input cable lying next to them picks up a few pF of it, and the
  amplifier's first junction rectifies the carrier back into audio;
- **magnetic (inductive):** the audio current in the module's speaker coil and leads induces a voltage in the loop of
  the amplifier's input cable – the larger the loop and the closer, the more.

A shielded cable stops the electric field, a shorter and twisted one has less loop for the magnetic one; distance helps
both. Separate batteries do not help at all. What edakit can decide sits on each side alone: on the receiver an input
without RC low-pass or ferrite (HT-8), on the transmitter a PWM speaker output on leads (HT-13), and cables as such
(HT-1, FT-2). The coupling between two devices that share nothing is no check: it stays judgement.

### Guitar electronics

Two more research clusters: effect pedals (37 pitfalls) and the instrument, amplifiers, DI boxes and switching (39).

- **The audio band at its operating point only.** Most of it is analog in the audio band, which edakit's DC-first
  simulation sees at its operating point. The bias of discrete stages – fuzz, boosts, phasers – rests on the spread of
  the transistors (AC128 gain 45–165, r; J201 IDSS 0.2–1.0 mA, r); the simulation has corners for the LEDs' forward
  voltage only (FT-17).
- **Impedance is the guitar's main topic.** A passive pickup wants about 1 MΩ, a piezo 10 MΩ and more; LM386 inputs,
  codecs and passive DI boxes load it to 10–300 kΩ (CK-27, FT-18).
- **Op-amps at 9 V** run out of swing and common-mode range (TL07x: 1.5–3 V short of each rail, r), and the Klon's
  charge pump puts 27 V across one – 36 V from a 12 V outlet (r): FT-3, and E-3 with the op-amp's `vdd_op_max` and a
  12 V supply corner.
- **Pops and scratches are DC where it should not be:** across switches, relay contacts and pots, and polarized
  capacitors around the 4.5 V reference in every state (CK-30, CK-7).
- **The pedalboard is a system:** outlets with a current each, positive-ground and AC pedals, daisy chains as ground
  loops (HT-18), charge pumps and PWM in the audio band (HT-16).
- **Layout:** input and output of a high-gain stage apart, a charge pump or a converter's switch node away from inputs,
  the PT2399's two grounds joined short (CK-31).
- **Covered already:** pinouts of regulators and transistors (P-1, L-10: 78L05 against 7805, BS170 against 2N7000),
  a regulator's temperature (E-3), capacitor ratings at 18 V (G-8 with the supply corner), flyback diodes and pull-in of
  relays (G-13, E-3), reverse polarity (G-10).
- **Out of scope:** tube amplifiers – B+ of 250–500 V, heaters, output transformers, and tube models that do not hold at
  low anode voltage – as long as edakit takes no hazardous voltage (FT-7).

## Candidates

The kinds are those of add-rule: a **check** where a program decides without guessing, a **hint** where it takes
judgement, a **block** for a circuit worth reusing, a **part fact** for one part's datasheet, and a **feature** where
edakit lacks the capability (add-feature). "Seen" names the clusters of the pitfalls list: LED, MOT (motors), PWR
(power), MCU, AUD (audio, mains, high voltage, measurement), GTP (guitar pedals), GTI (guitar instrument, amplifiers,
DI, switching), OWN (the owner's projects).

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
| FT-15 | **`fn` for I2S, CAN, 1-Wire and USB** (`i2s.bclk`, `i2s.ws`, `i2s.sd`, `can.tx`, `can.rx`, `onewire`, `usb.dp`, `usb.dn`): G-15 then holds them to the pin functions as it does SPI, I2C and UART. | topic "Communication between ICs" |
| FT-16 | **Bus parameters in the firmware contract:** per SPI device its mode and maximum clock, per I2C device its address and the bus speed its pull-ups allow, from the parts entries; drift reported as for the pins. | topic "Communication between ICs"; H-9 |
| FT-17 | **Corners of transistor parameters:** hFE, leakage (doubling per 10 °C), IDSS and VGS(off), VGS(th) – min and max from the entry as corners of the simulation, as the LEDs' forward voltage is today; with expected windows on nets (FT-11) the bias of fuzz, boost and phaser stages is checked. | GTP 1, 5, 6, 12, 13, 18 |
| FT-18 | **Source models for the audio band:** a passive pickup (inductance, resistance, capacitance), a piezo (voltage source behind its capacitance), a cable's capacitance per metre – for FT-12 and the loading of CK-27. | GTI 1–5, 10, 12; GTP 3 |
| FT-19 | **Coverage report:** per check what it could not check for lack of data – "E-3: U4.3, U4.5 without thresholds" – in `edakit check` and the gate protocol. The first step before any check that depends on part facts (section "Keeping the catalog stable"). | stability |
| FT-20 | **Domains:** `[project] domains` – audio, motors, radio, mains – switch domain checks and hints on; `edakit rules` and `edakit hints` show what applies to the project. | stability |

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
| CK-25 | G | **Analog nodes have a DC path:** a net with an `analog` input that reaches no resistor or driver to a defined level – only capacitors – floats: it picks up hum, and a switch on it pops. The analog sibling of G-4. | – | AUD 13 |
| CK-26 | G | **UART lines cross:** a net with `fn` `uart.tx` or `uart.rx` has exactly one output (a TX) and at least one input (an RX); a net with inputs only is an error, also with a pull-up – G-4 lets it pass then. | – | MCU 14; topic "Communication between ICs" |
| CK-27 | G | **Instrument inputs load their source within its limit:** a connector input declared for a passive pickup (guideline 1 MΩ, x) or a piezo (10 MΩ and more, x) sees the shunt resistors and the first active input's impedance in parallel above that; tuners and other branches on the node count. | `z_in_ohm` on input pins; `source` on the connector pin | GTI 1, 10, 15, 33, 34; GTP 3, 14, 19, 26 |
| CK-28 | G | **Amplifiers inside their stable gain:** the closed-loop gain from the feedback network is at least the part's minimum stable gain (LM1875: 10, x), and a part that needs external compensation has its capacitor (LM308: 30 pF across pins 1 and 8, r). | `gain_min`, `requires_ext_comp` | GTI 19; GTP 11 |
| CK-29 | G | **Series capacitors share their voltage:** two or more capacitors in series across a supply have balancing resistors (2 × 450 V in a tube supply, supercapacitor stacks). | – | GTI 21; PWR 23 |
| CK-30 | E | **No DC where signals are switched:** both sides of a switch, relay contact or pot in a signal path sit at the same DC level within a few mV in every state (the pop, the scratchy pot), and a contact that carries signal currents is rated for them (gold, minimum load 10 µA / 1 mV, x). | nets marked as signal path; `min_load` of contacts | GTP 31, 37; GTI 31; AUD 13 |
| CK-31 | L | **Nets kept apart:** pairs the hand-over names (`layout.apart`: two nets, a distance, a parallel length) keep them on the board – input and output of a high-gain stage (2.5 mm, x), a charge pump or switch node against high-impedance inputs, a crystal against noisy lines. The same measurement serves CK-9 and CK-11. | `layout.apart` | GTP 10, 22, 23, 25, 33; GTI 16, 26, 29; MCU 6, 7 |

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
| HT-13 | a filterless class-D output at a connector | ferrite or LC filter above the datasheet's lead length – a check with FT-2 and the length in the entry | AUD 1–3; OWN horn |
| HT-14 | a relay whose contacts switch an off-board load | the rating is resistive; LED drivers and switch-mode supplies draw tens of amps at start, inductive loads need a snubber | AUD 20 |
| HT-15 | a battery whose minus reaches ground through a jack's ring | a cable left plugged drains it, a TRS cable leaves the circuit off; the DC jack's switch lug must break battery plus (EMG: about 80 µA per pickup, x) | GTI 8; GTP 32 |
| HT-16 | a charge pump, a converter with a light-load mode, or PWM on a board with an audio path | switching in the audio band: ICL7660 and TC1044 at about 10 kHz with a 5 kHz subharmonic (x), boost converters bursting at light load, LED and tap-tempo PWM – above 20 kHz or filtered | GTI 29, 38; GTP 17, 34; AUD 12 |
| HT-17 | a class-2 ceramic (X7R, Y5V) in a signal path | it distorts; C0G or film (r) | GTI 36; GTP 24 |
| HT-18 | a pedal's supply input | positive-ground and AC pedals need an isolated outlet; a series part in the DC jack's ground leg is bypassed by the audio cables; daisy chains form ground loops | GTP 2, 35; GTI 32, 38 |
| HT-19 | an instrument's string ground, a capacitor from mains to chassis | the bridge ground ties the player to the amplifier's ground: a line-to-chassis capacitor (death cap) is Y-class or gone – the amplifier's side is CK-10 | GTI 7, 27 |

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
| BL-16 | instrument buffer: 1 MΩ JFET or op-amp input, 100 Ω–1 kΩ output resistor, RF filter at the jack (series resistor, then 47–100 pF) | GTI 1, 2, 39; GTP 14 |
| BL-17 | pedal power entry: 9 V centre-negative jack, series Schottky or P-MOSFET, 100 Ω and 100 µF, 4.5 V reference with ≥ 10 µF | GTP 9, 34, 36; AUD 11 |
| BL-18 | relay bypass with mute: signal relay with gold contacts, transistor coil drive with flyback diode, photo-MOS mute window (35 ms, r) | GTP 31; GTI 30, 31 |

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

## Keeping the catalog stable

The owner's question: with all these rules, does edakit stay stable, or does it confuse more than it helps?

**Today the catalog is quiet.** 66 active checks (G-7 is retired) and 9 hints, 983 tests; every check was seen red
once and ran against real projects before its merge. On the owner's boards it costs little: the bell needs 0–1 waived
finding and 0–1 accepted warning per variant (19 parts each), the reference project 7 waived findings for 84 parts and
77 nets and one accepted warning. Where the reference project lost time was EasyEDA, waiting and dead ends against the
API (handbook 13.2) – not the rules.

**Built one by one, the candidates of this concept would make it worse:**

1. The catalog would about double – the findings, `edakit rules`, the handbook's tables.
2. Most candidates come from research, not from a project's lesson. add-rule's run against real projects (step 5)
   cannot show their false alarms while no project of the owner has audio, mains or a guitar circuit – and a check that
   guesses produces waivers instead of findings.
3. Most of them need new fields in parts entries: work and a source of errors per part, and each one to sign (G-9).
4. Checks that need data pass silently without it: E-3 checks only inputs with thresholds, G-12 only pins with
   `strap`. More such checks are more coverage on paper; nothing says which part went unchecked.
5. Every open hint stands in the last line of `edakit check`; 25 hints on a board where five matter teach to ignore
   all of them.

**Guardrails that keep it stable:**

1. **Mechanisms, not rules.** Seven mechanisms cover 91 of the 128 maker pitfalls of the first five clusters that are
   not fully covered: requirements from parts entries (38: CK-13, CK-14, CK-20, CK-12, CK-21, CK-23, CK-3, PF), loads
   over time (16: FT-1, FT-8, FT-11, CK-18), analog windows (13: CK-5, CK-6, CK-25, FT-3), pin semantics (10: CK-1,
   CK-2, CK-26), cables (10: FT-2, CK-16, CK-17, HT-1), hazardous voltage and RF geometry (9: FT-7, CK-9, CK-10, CK-11,
   CK-22, CK-24), switching parts and polarity (7: CK-4, CK-7, CK-8, CK-15). The guitar clusters fall into the same
   mechanisms, plus CK-27 and CK-30. The knowledge goes into parts entries as data, as `strap` and `pull` do today –
   not into new check IDs.
2. **Coverage visible first (FT-19).** Before a check that depends on data is added, `edakit check` and the gate
   protocol say per check what it could not check. Silent passes become open points.
3. **Domains (FT-20).** A project states its domains; domain checks and hints run only there, and `edakit rules` lists
   what applies. A board without audio never sees an audio hint.
4. **A project triggers the build.** A candidate is built when a project has the case or plans it – asp_pro's MIDI
   and battery, tinyjukebox's amplifier – so that add-rule's run on a real project means something. Until then it is a
   row in this concept.
5. **New checks start as warnings,** graded as P-11, G-24 and G-25 are, and become errors after two projects without a
   false alarm.
6. **Hints sparingly:** only with a trigger that decides when one applies; judgement without such a trigger goes into
   the reviewers' questions.

## Priority

Ordered by how often the pitfall appeared across the clusters, what it costs when it happens, and how much it takes –
within the guardrails above:

| # | Candidate | Why first |
| --- | --- | --- |
| 0 | FT-19 coverage report, FT-20 domains | the frame every later check runs in; they make the existing catalog's gaps visible and keep domain rules off boards that do not need them |
| 1 | FT-1 load steps | in all five maker clusters and in both guitar clusters; the most frequent "it resets when the motor starts"; the bell's servo |
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
(jacks with a supply), FT-4 (asp_pro's battery), CK-11 (ESP32 boards). For a guitar circuit: CK-27 (input impedance),
FT-3 (op-amps at 9 V), CK-30 (DC at switches), FT-17 (bias of discrete stages), BL-16 to BL-18.

Mains and high voltage (FT-7, CK-9, CK-10, CK-24) prevent the most expensive faults – shock and fire – but none of the
owner's projects has them. CK-22 says honestly what edakit does not check and costs a few lines; the rest follows when
edakit is to take such boards.

## Out of scope

- Radiated emission and immunity as field strengths, transmission lines – the hints and the reviewers cover them.
- Settings that live in firmware only: SPI mode, motor PWM frequency, debounce times, brown-out levels – hints, the
  firmware contract, and H-9 where a part of the circuit decides.
- Certification itself: the regulatory review (M-6) is support, not a test lab.
- Tube amplifiers: B+ of 250–500 V, heaters, output transformers, tube models that do not hold at low anode voltage –
  as long as edakit takes no hazardous voltage.
- The pinball machine (owner's decision).

## Open decisions

1. Whether the guardrails hold (section "Keeping the catalog stable"): this concept as a backlog that a project
   triggers, FT-19 and FT-20 first.
2. Which candidates become proposals – one issue each through `/edakit:propose-rule` and `/edakit:propose-feature`,
   or built directly with add-rule and add-feature.
3. Whether edakit takes boards with mains or high voltage (FT-7, CK-9, CK-10), or only says that it does not check them
   (CK-22).
4. Whether a library of checked entries for popular parts (PF) belongs into edakit – who signs them, and how a project
   takes one over (today: `edakit/blocks/parts/`, copied by `edakit block add`).
5. Whether AC analysis (FT-12) fits edakit's DC-first approach at all.
6. The network policy: the vendor hosts the sources need (ti.com, st.com, espressif.com, microchip.com, analog.com,
   nxp.com, pololu.com, adafruit.com, onsemi.com, diodes.com, vishay.com, infineon.com, allegromicro.com, midi.org,
   usb.org) are allowed in the environment, or the sources are read on a machine that reaches them.

## Sources

Per pitfall with its tag in [the appendix](#appendix-the-pitfalls). The documents read in full (r):

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
- Guitar: ElectroSmash's circuit analyses (Fuzz Face, germanium fuzz, Rangemaster, Big Muff, Tube Screamer, Klon,
  ProCo RAT, 1Wamp, Dyna Comp, Phase 90, CE-2, Crybaby, PT2399, MN3007, Back Talk, JRC4558) in
  `mstratman/electrosmash-pdf-backups`; Spin FV-1 datasheet SPN1001-DS-170829, ST TL074 datasheet DocID2297 Rev 5 and
  the Intersil CA3080 datasheet, each in a GitHub repository; PJRC Audio library (`control_sgtl5000.cpp`,
  `gui/index.html`); `mstratman/relay-bypass`; `tardate/LittleArduinoProjects` (Little Gem, Ruby); `jonnor/piezopro`;
  `wagiminator/ADuM3160-USB-Isolator`; `DIYSynthMNL/Eurorack-PT2399-Delay`; `flpvsk/pt-workshop`;
  `ElectricCanary/Bontempo`; `Eight4aWish/eurorack_electronics` (PCM3060 notes); `hed0rah/partinfo`

## Appendix: the pitfalls

One row per pitfall: the pitfall with its numbers, what edakit does about it today, the candidate that would cover it, and the source.

**edakit today:** *covered* (the check or hint named), *with part facts* (an existing check finds it once the parts entry carries the datasheet value), *partly*, *no*. **Source tags:** **r** read in the primary document, **x** from a search engine's extract of the cited page, **v** to verify – not reachable from this environment, or from memory. A value tagged x or v is read in its source before it goes into a catalog entry.

### LEDs, lighting and displays (32)

| # | Pitfall | edakit today | Candidate | Source |
| --- | --- | --- | --- | --- |
| 1 | 3.3 V data into a 5 V pixel: VIH 0.7 × VDD = 3.5 V (WS2812B V1.0), 0.63 (V5), 0.55 (V6), SK6812 and APA102 0.7, WS2815B 2.7 V at 12 V | with part facts: E-3 | PF, BL-1 | WS2812B V1.0, V5, V6, SK6812mini, APA102C, WS2815B datasheets (x) |
| 2 | level shifter of the HC family (CMOS VIH ≈ 0.7 × VCC) instead of HCT/AHCT (VIH 2.0 V); shifter fed from 3.3 V; OE and unused inputs floating | with part facts: E-3; floating `nc` inputs: no | CK-1, BL-1 | TI SN74AHCT125 (x) |
| 3 | BSS138 shifter with 10 kΩ too slow for 800 kbit/s: 2.2·R·C ≈ 1.1–2.2 µs against T0H 0.4 µs | no – the simulation knows no edges | BL-1, HT-1 | forum threads (x) |
| 4 | no series resistor on the data line (Adafruit: 300–500 Ω); unbuffered runs beyond 1–2 m | no | BL-1, HT-1 | Adafruit NeoPixel best practices (x) |
| 5 | data high while the strip is unpowered: DIN abs. max VDD + 0.5 V, current through the clamp, first pixel dies | no | CK-5, FT-8 | WS2812B V1.0 (x); Adafruit (x) |
| 6 | no bulk capacitor at the strip (500–1000 µF), no 100 nF per LED | covered: H-1, G-6 | BL-1 | Adafruit (x); WS2812B application circuit (x) |
| 7 | current budget: up to 60 mA per pixel at white, 300 pixels = 18 A | covered where modelled: E-3 source `i_max_a`, `current` model | FT-13 | Adafruit powering guide (x) |
| 8 | LEDs fed through the MCU board's regulator or USB (NCP1117 dissipation, 500 mA USB, ESP32 brown-outs) | covered: E-3 module LDO, source limit; the burst: no | FT-1 | Arduino and ESP32 forums (x) |
| 9 | voltage drop along the strip: 5 m at 60 LEDs/m, 2.5 V at the far end; blue fails below about 3.3 V | partly: `external` load at a connector | FT-13 | QuinLED injection guide (x); Hackaday (x) |
| 10 | wire gauge of feeds: 22 AWG ≈ 53 mΩ/m, 2 m at 3.6 A drops 0.76 V | partly: `cables` `r_ohm_per_wire` | FT-2 | QuinLED (x); WLED wiring (x) |
| 11 | no fuse between a 300 W supply and thin wiring | covered: G-17 for a modelled cable; a missing fuse: no | FT-2 | QuinLED fuses (x); Hackaday (x) |
| 12 | data reference: shared ground missing or thin (5 A through 1 m 22 AWG lifts 0.26 V) | covered: per-board ground with the cable's resistance, E-3 levels to the part's own ground | FT-2 | Adafruit (x) |
| 13 | WS2815 backup input BI of the first pixel floating | G-4 in a net; `nc`: no | CK-1 | WLED forum (x) |
| 14 | pin states at boot: ESP32 GPIO 1, 3, 5, 14, 15 toggle; GPIO 12 strap; gate without pull-down | covered: G-12, G-4; toggling pins as a pin `hint` | PF | Espressif (x); WLED forum (x) |
| 15 | footprint pinout and orientation (SK6812 MINI-E datasheets disagree, reverse mount) | covered: P-1, L-10, L-8, P-2, G-9 | – | Fritzing forum, KiCad MR (x) |
| 16 | LED supply tracks too narrow (IPC-2221, 10 °C: 3 A ≈ 1.37 mm, 5 A ≈ 2.8 mm) | covered: L-5 | – | IPC-2221 formula |
| 17 | strip MOSFET not logic-level: IRF520 and IRFZ44N specified at VGS 10 V; TIP120 drops about 2 V | partly: E-2 with the SPICE model, no threshold corner | CK-4, BL-2 | Adafruit RGB strips (x); datasheets (x) |
| 18 | PWM flicker: IEEE 1789 – 100 % modulation needs ≥ 1250 Hz (low risk), ≥ 3 kHz (no effect); Arduino 490 Hz | no | HT-9 | US DOE summary; Finelite white paper (x) |
| 19 | constant-current buck sized wrong (PT4115: I = 0.1 V / RS, RS ≥ 0.082 Ω; inductor table; VIN above ΣVf) | no model | FT-14 | PT4115, AL8860 datasheets (x) |
| 20 | power LED without heat sink: θ ≤ (Tj − Ta) / P | partly: E-2 `rth_ja_k_per_w` of the part alone | HT-11 | star LED datasheets (x) |
| 21 | MAX7219 at 3.3 V logic: VIH 3.5 V; common-cathode displays only | with part facts: E-3 | PF | MAX7219 datasheet (x) |
| 22 | MAX7219 RSET, about 1 W dissipation, 10 µF + 0.1 µF at the chip | partly: G-6 | PF | MAX7219 table 11 (x) |
| 23 | 74HC595 driving LEDs: ±35 mA per output, 70 mA through VCC or GND | no | CK-21 | TI CD74HC595 (x) |
| 24 | multiplexed commons on MCU pins (8 × 15 mA); charlieplexing reverses LEDs | covered: E-2 GPIO current per scenario, LED `vr_max` | – | Arduino pin limits (x) |
| 25 | TLC5940 headroom heat; PCA9685 25 mA sink | covered: `cc_sink`, E-3 driver temperature; PCA9685 limits: no | CK-21 | TI TLC5940, NXP PCA9685 (x) |
| 26 | SPI TFT: 5 V logic into 3.3 V inputs, backlight 40–70 mA from a GPIO | covered: G-3, E-2 GPIO current | – | display vendor pages (x) |
| 27 | SSD1306 module: pull-ups to 5 V, addresses 0x3C/0x3D only, pull-ups stacked | covered: G-3, G-11; the address: no | CK-3 | module datasheets (x) |
| 28 | PCF8574 backpack: VIH 0.7 × VCC; 0x27 (PCF8574) or 0x3F (PCF8574A); contrast bias at 3.3 V | with part facts: E-3; address: no | CK-3 | NXP PCF8574 (x) |
| 29 | e-paper booster: sense resistor per panel, booster part ratings | partly: G-8 | PF | Waveshare wiki (x) |
| 30 | Nixie 170–180 V boost: switch, diode, capacitor ratings; anode resistor; 74141 off-state about 55–60 V | covered: G-8, E-2; the spacing: no | CK-22, CK-9 | builder reports (x) |
| 31 | high-voltage clearance: IPC-2221 151–250 V, outer uncoated 1.25 mm | no | CK-9 | IPC-2221 via KiCad (r) |
| 32 | VFD: filament, grid voltage, driver range, filament bias | partly: G-8, E-3 | – | MAX6921 (x) |

### Motors, motion, robotics, 3D printers and CNC (35)

| # | Pitfall | edakit today | Candidate | Source |
| --- | --- | --- | --- | --- |
| 1 | L298N drop 1.8 V typ, 3.2 V max at 1 A; 1.8–3.2 W per bridge | no model | FT-6, BL-14 | ST L298 (x) |
| 2 | bipolar bridge (L298, L293 non-D) without clamp diodes | no | CK-15 | ST L298 application circuits (v) |
| 3 | VM rating against a full LiPo: DRV8833 10.8 V, TB6612 15 V abs. max, 3S = 12.6 V | covered with part facts: E-3 `vdd_op_max` with full cells, G-3 | PF | Toshiba TB6612 (x); Pololu forum (x) |
| 4 | stall and start current above the driver's rating (I = V / R_winding) | partly: a constant fault case | FT-1, FT-6, BL-14 | L9110, TB6612 datasheets (x) |
| 5 | no bulk capacitor at VM; a series diode lets the motor pump VM up (12 V, 1 mH, 2 A into 10 µF → 23 V) | no | HT-12, BL-14 | TI DRV8833 (v) |
| 6 | brush noise; capacitors on PWM outputs trip over-current | no – judgement | – | Pololu (v) |
| 7 | PWM at 490 Hz: whine and ripple | no – firmware | – | Arduino `analogWrite` reference (r) |
| 8 | shunt sized for value, not power (0.5 Ω at 2 A = 2 W); sense through shared ground | covered: E-2 resistor power; Kelvin: no | reviewer question | DRV8833 (v) |
| 9 | VMOT LC spike at hot-plug: up to about 2× the supply, above the A4988's 35 V; ≥ 47 µF electrolytic | partly: H-1; E-5 has no inductance | FT-2, HT-12 | Pololu A4988 product page (x) |
| 10 | Vref formula by board: A4988 I = VREF / (8 · R_CS), R_CS 0.068, 0.050 or 0.1 Ω | no | PF, FT-10 | Pololu (x); BTT TMC2209 wiki (x) |
| 11 | driver heat through the exposed pad: A4988 about 1 A per coil without cooling | partly: E-2 `rth_ja_k_per_w` | HT-11 | Klipper TMC drivers (r) |
| 12 | motor connected or disconnected under power; coil pairs mixed up | no – judgement | – | Pololu (x); Klipper (r) |
| 13 | A4988 VIH 0.7 · VDD at VDD 5 V against a 3.3 V MCU | with part facts: E-3 | PF | Allegro A4988 (x) |
| 14 | A4988 RESET floating; TB6612 STBY and DRV8833 nSLEEP pulled down; TMC UART wiring and addresses | G-4 in a net; `nc`, addresses: no | CK-1, CK-3 | Marlin `Configuration_adv.h` (r); Pololu forum (x) |
| 15 | TMC driver loses its settings when VM drops; logic inputs feed the unpowered driver | no | CK-5, FT-8 | Klipper (r) |
| 16 | servo stall on the MCU's rail: MG996R 2.5 A, Uno polyfuse 500 mA, AVR BOD 2.7 V, ESP32 2.43 V | partly: constant currents | FT-1, BL-13 | MG996R (x); ArduinoCore `boards.txt` (r); ESP-IDF `Kconfig.system` (r) |
| 17 | back-driven servos push the rail above 5.7 V | no | FT-1 | ArduPilot "Powering the Pixhawk" (r) |
| 18 | BECs in parallel; linear BEC 7.6 W at 3S, 1 A; ESC signal without ground | covered: G-5, H-8, E-3 | – | ArduPilot (r) |
| 19 | LiPo range; battery divider beyond the ADC window (ESP32 150–2450 mV at 11/12 dB) | partly: E-3 with cell states; the window: no | CK-6 | ArduPilot (r); ESP-IDF ADC (r) |
| 20 | fuse, switch, connectors, copper in the high-current path (MicroFit 5 A per contact) | covered: G-17, E-2 contact current, L-5 | – | Voron documentation (r) |
| 21 | coils without clamp; coils on a GPIO | covered: G-13 (relays, buzzers), H-4, E-2; solenoids and motors on the board: no | CK-15, FT-6 | v |
| 22 | 5 V relay module (LED anode at 5 V) on a 3.3 V MCU: does not release, pin pulled to 5 V | covered where modelled: G-3, E-3 relay release | – | judgement |
| 23 | 4-pin PWM fan: open-drain PWM input pulled to 5 V, open-collector tach | partly: G-3; open-drain: no | CK-2 | Linux `pwm-fan` binding (r); Intel fan specification (v) |
| 24 | 12 V fans and loads on 24 V; supplies without a common 0 V | covered: G-3, E-3, G-16 | – | Marlin (r); Voron (r) |
| 25 | heater MOSFET IRF520 (RDS(on) 0.27 Ω only at 10 V) from 5 or 3.3 V | partly: E-2 with the SPICE model | CK-4, BL-2 | IRF520, IRLZ44N (v) |
| 26 | gates without pull-down; ESP32 pins with PWM at boot, GPIO 12 strap | covered: G-4, G-12; boot activity as a pin `hint` | PF | Espressif hardware design guidelines (r) |
| 27 | bed current through terminals and polyfuses (RAMPS 11 A) | covered: E-2, G-17, L-5 with an `external` load | FT-6 | Voron (r); RepRap (v) |
| 28 | 12 V parts on 24 V: a heater gives 4× the power, NCP1117 20 V abs. max | covered: G-3, G-8, E-3; the heater as a load: no | FT-6 | v |
| 29 | thermistor input: firmware assumes 4.7 kΩ, 5 V pull-up on a 3.3 V ADC, no filter | partly: G-3; window and firmware constant: no | CK-6, FT-10 | Marlin `Configuration.h` (r); Klipper (r) |
| 30 | heater switch fails closed, firmware cannot stop it | no | HT-10 | Marlin, Klipper, Voron (r) |
| 31 | endstops on long leads, probes at 12–24 V into 3.3 V pins, NO switches fail silently | covered: G-3, G-4; the cable: no | HT-1, BL-12 | Marlin (r); Voron (r) |
| 32 | encoders: open-collector outputs without pull-ups, RC slower than the edges | partly; open-drain: no | CK-2 | Bourns PEC11R (v) |
| 33 | HC-SR04 echo at 5 V into a 3.3 V pin | covered: G-3 | – | v |
| 34 | TCRT5000 LED current (60 mA abs. max) | covered: E-2 LED current where modelled | – | Vishay (v) |
| 35 | motor or servo start pulls the logic rail below brown-out (4 × AA 0.6–1 Ω; AMS1117 1.1 V dropout; 16 MHz AVR needs about 3.8 V) | no | FT-1, CK-23 | ESP-IDF (r); MiniCore (r) |

### Power supplies, batteries and low-power nodes (32)

| # | Pitfall | edakit today | Candidate | Source |
| --- | --- | --- | --- | --- |
| 1 | TP4056 with R_PROG 1.2 kΩ charges at 1 A – 2 to 6.7 C on a 150–500 mAh cell; MCP73831 I = 1000 / R_PROG(kΩ) mA | no | FT-4, BL-4 | TP4056, MCP73831, NCR18650B datasheets (x) |
| 2 | load on the cell while charging: termination at C/10 never reached | no | HT-5, BL-4 | Microchip AN1149 (x) |
| 3 | linear charger dissipation: TP4056 at 1 A from 5 V into 3.0 V = 2 W | no model | FT-4 | MCP73831 thermal example (x) |
| 4 | charger's TEMP/NTC pin grounded: charging below 0 °C | no | PF | TP4056 (x); Battery University (x) |
| 5 | protection IC thresholds against the cell (DW01A 2.4 V); no undervoltage cut-off | partly: H-6 | BL-4 | DW01A (x) |
| 6 | coin cell: CR2032 3 mA continuous, pulses 15–30 mA, internal resistance tens of Ω | partly: cell `r`; a limit: no | CK-18, FT-1 | Energizer CR2032 (x); TI SWRA349 (x) |
| 7 | JST-PH battery polarity differs between vendors | partly: G-10 for connectors in `reverse_protect` | HT-6 | Adafruit (x) |
| 8 | AMS1117 dropout 1.1–1.3 V on a LiPo or behind a Schottky | covered: `ldo` model, E-3 | – | AMS1117 (x) |
| 9 | LDO output capacitor outside its window (AMS1117: 22 µF tantalum, ESR) | no | CK-14, CK-13 | AMS1117 (x); LM2596 (x) |
| 10 | sleep current of the board: AMS1117 5 mA, power LED, CP2102 (DevKitC 3.8 mA in deep sleep) | partly: the simulation's currents, no budget | FT-11 | ESP32 datasheet (x); Spiess #193 (x) |
| 11 | low-Iq LDOs: MCP1700 250 mA, 6 V input; ESP32 needs ≥ 500 mA | covered: E-3, G-3 | BL-5 | MCP1700, HT7333, XC6206 (x) |
| 12 | linear regulator headroom and heat: 7805 2 V dropout, 12 → 5 V at 0.5 A = 3.5 W | covered: `ldo` model, E-3 | – | L7805 (x) |
| 13 | buck module at an unknown trimmer setting, no reverse protection | no | FT-5 | MP1584 (x); LM2596 (x) |
| 14 | feedback divider (VREF 1.25, 1.23, 0.8, 0.6 V); LM317 needs 10 mA load | no | FT-5 | onsemi LM317 (x) |
| 15 | non-synchronous boost passes VIN − about 0.3 V with EN low (MT3608) | no | HT-4, FT-5 | TI SLVA191 (x); EEVblog (x) |
| 16 | ceramic DC bias: 4.7 µF, 6.3 V, 0603 X5R at 5 V ≈ 0.33 µF | no | FT-9 | ADI tutorial 5527 (x); Nordic (x) |
| 17 | battery divider: 100 k + 100 k draws 21 µA; MΩ dividers against the ATmega's 10 kΩ | no | CK-6, BL-6, FT-11 | ATmega328P §23.6.1 (x); ESP-IDF ADC (x) |
| 18 | Wi-Fi bursts 240–335 mA against the supply's impedance: brown-out | partly: E-3 at `i_core_a` | FT-1, BL-7 | Espressif schematic checklist (x) |
| 19 | brown-out and clock against the supply: ATmega328P at 16 MHz needs about 3.78 V | no | CK-23 | ESP-IDF `Kconfig.system` (x); Microchip (x) |
| 20 | back-powering through I/O pins into a switched-off rail (TI: ±2 mA) | no | CK-5, FT-8 | TI SLAA689 (x) |
| 21 | 6 V panel straight into a TP4056 (VIN 4–8 V, panel Voc about 7.5 V) | partly: G-3, E-3 | – | TP4056 (x); CN3791 (x) |
| 22 | reverse current into the panel at night | covered: E-3 back-feed into sources | – | x |
| 23 | supercapacitors: 2.7 V per cell, balancing | partly: G-8 | – | Würth ANP090 (x) |
| 24 | supercapacitor ESR (about 50 Ω for 0.47 F coin parts) and inrush | partly: E-5 plug-in | – | Eaton KR (x) |
| 25 | USB budget: 500 mA (USB 2.0), 900 mA (USB 3), Type-C 1.5 or 3 A only when advertised | partly: E-3 against the `i_max_a` set by hand | HT-2 | Microchip; Infineon (x) |
| 26 | USB-C CC resistors missing or shared | covered: G-14 | – | Hackaday; kernel.org (x) |
| 27 | PD trigger asks for 20 V (CH224K with CFG1 open) | partly: G-3 when the net's range is right | CK-20 | CH224K (x) |
| 28 | inrush into capacitance: USB 2.0 allows 10 µF at attach | partly: E-5 peak current | HT-3 | USB 2.0 §7.2.4.1 via Maxim (x) |
| 29 | several supplies on one rail; a LiPo on the 3V3 pin (4.2 V > 3.6 V) | covered: H-8, E-3, G-3 | – | Espressif DevKitC (x) |
| 30 | high-side P-MOSFET driven from a 3.3 V GPIO on 5 or 12 V | no | CK-4, BL-3 | x |
| 31 | soft-power latches that latch, drop or leak | no | FT-1 (partly) | Circuit Cellar (x) |
| 32 | reverse polarity at a barrel jack or battery input; Boss centre-negative | covered: G-10 for listed inputs | HT-6, CK-7 | TI SLVA139 (x) |

### MCU boards, buses, radio, keyboards and HATs (39)

| # | Pitfall | edakit today | Candidate | Source |
| --- | --- | --- | --- | --- |
| 1 | ESP32 EN without RC: 10 kΩ and 1 µF; tSTBL 50 µs after VDD | no | CK-13, BL-7 | ESP32 HDG §3.3 (r) |
| 2 | auto-program circuit: RTS straight to EN, no EN capacitor (1–10 µF), large capacitor on GPIO0 | no | BL-7, CK-13 | esptool boot mode selection (r) |
| 3 | loads on strapping pins (ESP32 GPIO 0, 2, 12, 15; S3 GPIO 0, 45, 46; C3 GPIO 8, 9) | with part facts: G-12 | PF | esptool (r); ESP32 and ESP32-S3 HDG (r) |
| 4 | flash and PSRAM pins, input-only GPIO 34–39 without pulls, ADC2 with Wi-Fi, USB pins | with part facts: G-15, E-3, pin `hint` | PF | ESP-IDF GPIO and ADC (r) |
| 5 | 3.3 V supply too weak: Espressif asks for ≥ 500 mA and 10 µF | partly: E-3 at DC | FT-1, BL-5 | ESP32 HDG §3.2 (r) |
| 6 | module antenna over copper: over the edge or ≥ 15 mm clear | no | CK-11 | ESP32 HDG §4.2 (r) |
| 7 | crystal load capacitors: C = 2 · (CL − Cstray), Cstray 3–5 pF; gain margin ≥ 5 | no | CK-13 | ST AN2867 (r); RP2040 HDG (r) |
| 8 | USB full speed: series resistors (RP2040 27 Ω), D+ pull-up 1.5 kΩ (Blue Pill 10 kΩ), 90 Ω pair, ESD at the connector | no | CK-13, BL-8 | RP2040 HDG §2.4 (r); USB 2.0 (v) |
| 9 | USB-C: D+ and D− of both rows joined; CC per pin | CC covered: G-14; D±: no | CK-12 | USB Type-C specification (v) |
| 10 | STM32 VCAP 2 × 2.2 µF, BOOT0, NRST 100 nF, VDDA, VBAT | no | CK-13 | ST AN4488 Rev 7 (r) |
| 11 | no way back after bad firmware: SWD without NRST, no BOOTSEL, UPDI loaded | no | CK-13 | AN4488 (r); RP2040 HDG (r); AVR-Guidance (r) |
| 12 | ATmega AVCC unconnected; AREF tied to VCC | partly: G-16 for AVCC | CK-13 | ATmega328P datasheet (v) |
| 13 | Arduino auto-reset (100 nF, 10 kΩ); modules on D0/D1 behind the 16U2's 1 kΩ | partly: G-5 | CK-13 | Uno Rev3 schematic (v) |
| 14 | UART TX to TX, RX to RX; CH340 at 5 V into a 3.3 V RX; CH340 V3 pin | covered: G-5, G-4, G-3; RX to RX with a pull-up passes | CK-26, CK-13 | QMK serial driver (r) |
| 15 | I2C address clashes: DS3231 and MPU-6050 at 0x68, PCA9685 and INA219 at 0x40, PCF8574 against PCF8574A, All-Call 0x70 | no | CK-3 | RobTillaart READMEs (r); datasheets (v) |
| 16 | pull-ups too weak for the bus: tr = 0.8473 · Rp · Cb, 400 pF; Rp ≤ 2.95 kΩ (100 kHz), 885 Ω (400 kHz) | partly: G-11 with a fixed 10 kΩ | CK-3, FT-2 | NXP UM10204 §7.1 (r) |
| 17 | too many pull-ups in parallel: Rp ≥ 967 Ω at 3.3 V | covered: G-11 | – | UM10204 (r) |
| 18 | 5 V I2C modules on a 3.3 V bus | covered: G-3, E-3 | BL-9 | UM10204 (r) |
| 19 | wrong level shifter: BSS138 with 10 kΩ too slow for 400 kHz, TXB0108 with pull-ups | no | BL-9 | SparkFun BOB-12009 (r); TI TXB0108 (v) |
| 20 | open-drain INT and ALERT without pull-up; DS3231 module charges a CR2032 | no; charging a primary cell: E-3 where modelled | CK-2 | RobTillaart PCF8574 (r); ESP-IDF GPIO (r) |
| 21 | DS18B20 without 4.7 kΩ; parasite power wired wrong | no | CK-2, CK-13 | Arduino-Temperature-Control-Library (r) |
| 22 | sensor output beyond the ADC (ACS712 0.5–4.5 V around 2.5 V; 10 kΩ NTC at 80 °C) | no | CK-6 | ESP32 HDG §3.11 (r); arduino-esp32 ADC (r); RobTillaart ACS712 (r) |
| 23 | ADC source impedance (ATmega 10 kΩ; ESP32 0.1 µF at the pin) | no | CK-6, FT-3 | ESP32 HDG (r); ATmega328P (v) |
| 24 | resistive soil probes corrode; NE555 (4.5 V min) at 3.3 V | partly: E-3 with part facts | PF | v |
| 25 | HX711: AVDD headroom, ±20 mV full scale, RATE strap | partly: E-3 with part facts | CK-13, CK-20 | bogde/HX711 (r) |
| 26 | 5 V outputs into pins that are not 5 V tolerant | covered: G-3 | – | QMK RP2040 (r); RadioLib (r) |
| 27 | RP2350 erratum E9: inputs latch at about 2.1 V with the internal pull-down | with part facts: a pin `hint` | PF | Hackster (x) |
| 28 | RS-485: more than two 120 Ω, no fail-safe bias, DE floating at reset, 5 V RO into 3.3 V | partly: G-4 (DE), G-3 (RO) | CK-17, BL-10 | TI SLLA272 (v) |
| 29 | CAN: termination, TJA1050 at 5 V, 8 MHz crystal against a 16 MHz library default | partly: G-3 | CK-17 | autowp/arduino-mcp2515 (r); arduino-CAN (r) |
| 30 | MIDI: input without opto or with a slow one, no reverse diode, pin 2 grounded; output resistors not for 3.3 V | no | BL-11, FT-6 | MIDI CA-033 (v) |
| 31 | nRF24L01 bursts; bulk capacitor at the module | partly: G-6 | FT-1 | RF24 `COMMON_ISSUES.md` (r) |
| 32 | LoRa SX127x: 3.3 V only, 120 mA bursts, antenna before the first TX | covered: G-3; the burst: no | FT-1 | arduino-LoRa (r); RadioLib (r) |
| 33 | keyboard matrix: diode direction against the firmware (QMK COL2ROW, ZMK default row2col) | no | CK-19 | QMK (r); ZMK (r) |
| 34 | split keyboards: TRRS with VCC not hot-pluggable; pull-ups of the link | partly: G-11 | HT-7, CK-2 | QMK split keyboard (r) |
| 35 | per-key RGB: VIH 3.5 V, 70 LEDs × 60 mA against 500 mA USB | with part facts: E-3 | BL-1, HT-2 | QMK RGB matrix (r) |
| 36 | Raspberry Pi HAT: back-powering without ideal diode, ID EEPROM on GPIO 0/1 with 3.9 kΩ | partly: H-8, E-3 back-feed | CK-13 | raspberrypi/hats design guide (r) |
| 37 | Arduino shield logic on 5 V instead of IOREF | covered: G-3 where modelled | – | v |
| 38 | floating CMOS inputs, unused gates, unused op-amp halves | partly: G-4 for nets; `nc`: no | CK-1, FT-3 | TI SCBA004 (v); ESP32 HDG §3.10 (r) |
| 39 | SPI: CS floating at reset; modules whose buffer never releases MISO | partly: G-4 for CS; tri-state: no | CK-2 | judgement |

### Audio, mains, high voltage, outdoor and measurement (35)

| # | Pitfall | edakit today | Candidate | Source |
| --- | --- | --- | --- | --- |
| 1 | bridge-tied class-D outputs grounded, shared between channels or fed onward (PAM8403, PAM8302, MAX98357A, TPA3116D2) | no | CK-8, HT-13 | PAM8403 (v); Adafruit MAX98357A (v) |
| 2 | supply or speaker impedance outside the window (PAM8403 2.5–5.5 V; TPA3116D2 RL ≥ 3.2 Ω BTL) | partly: E-3 with part facts; the speaker: no | FT-6 | TPA3116D2 operating conditions (r) |
| 3 | amplifier supply budget (2 × 3 W into 4 Ω ≈ 1.4 A at 5 V) and local decoupling | partly: G-6, E-3 with a `current` model | FT-1 | TPA3116D2 layout (r) |
| 4 | pop at power-up: shutdown pin tied or floating | partly: G-4 floating; the level at start: `strap` with G-12 | CK-20, PF | PAM8403 (v) |
| 5 | configuration pins by voltage window: MAX98357A SD_MODE < 0.16 / 0.77 / 1.4 V; INMP441 L/R floating | partly: G-12 knows high and low only | CK-20 | Adafruit MAX98357A pinouts (r); ADMP441 (r) |
| 6 | microphone bias against the ADC window (ESP32 0 dB: 100–950 mV); Wi-Fi noise on the microphone's rail | no | CK-6, HT-8, FT-3 | ESP-IDF ADC (r) |
| 7 | coupling capacitor too small (32 Ω with 10 µF: 497 Hz) or reverse-biased | no | CK-7, FT-12 | first-order high-pass; TI headphone amplifiers (v) |
| 8 | ground loops, shared return copper, Y-capacitor noise of switch-mode supplies | no – judgement | HT-8 | OpenEnergyMonitor (r) |
| 9 | linear supply at high mains (25 V AC → about 42 V unloaded) against capacitors and the LM3886 | covered: G-8, G-3 when the net's range holds the high line | – | OpenEnergyMonitor (r); LM3886 (v) |
| 10 | Eurorack: reversed 10-pin ribbon swaps ±12 V, 16-pin offset, shunt diodes short the supply | partly: G-10 for a 2-pin reversal | FT-8, CK-7, BL-15 | elby-designs (r); EuroBusboard (r) |
| 11 | pedals: 9 V centre-negative (Boss), series Schottky | covered: G-10 for listed inputs | HT-6 | Boss PSA (v) |
| 12 | charge pumps: ICL7660 10 V max, 10 kHz whine, doubled rail against 16 V capacitors | covered: E-3, G-8; the whine: judgement | – | TC1044S, LT1054 (v) |
| 13 | true-bypass pop: switched audio nodes without a DC path | no | CK-25 | R.G. Keen, The Technology of Pops (v) |
| 14 | mains to SELV: IEC 60664-1 at 230 V, OVC II, PD 2 – clearance 1.5 / 3.0 mm, creepage 2.5 / 5.0 mm (basic / reinforced), slots from 1 mm | no | CK-9, FT-7 | KiCad `iec60664.cpp` (r) |
| 15 | spacing between mains nets from RMS instead of peak: 325 V peak → IPC-2221 2.5 mm outer uncoated | no | CK-9 | KiCad IPC-2221 (r) |
| 16 | parts on the barrier rated basic only (relay 1500 VAC coil to contact; ACS712 184 V peak reinforced) | no | CK-10 | HLK datasheet (r); Allegro ACS712 (v) |
| 17 | non-isolated supplies (capacitive dropper, Sonoff) with programming or sensor ports | no | CK-10 | Tasmota (r) |
| 18 | mains input: fuse first, MOV and X capacitor after it, bleeder, Y-class across the barrier | no | CK-10 | HLK (r); IEC 62368-1 §5.5.2.2 (v) |
| 19 | copper for 10 A: 4.7 mm at 20 °C rise on 1 oz | covered: L-5 with a declared current; AC loads are not simulated | – | KiCad track width (r) |
| 20 | relay contacts: resistive rating against inrush of LED drivers and inductive loads | no – judgement | HT-14 | Songle, Mean Well (v) |
| 21 | TRIAC dimmer: zero-cross optotriac for phase control, VDRM 400 V, gate resistor, snubber | no | PF | ESPHome `ac_dimmer` (r); onsemi MOC302x (v) |
| 22 | resistor voltage in mains and high-voltage chains (1206: 200 V) | partly: G-8 against the highest net voltage | – | Yageo RC (v) |
| 23 | optocoupler LED sized for 5 V driven from 3.3 V (PZEM's 1 kΩ) | no | FT-6 | Tasmota PZEM (r) |
| 24 | current transformer without burden (SCT-013-000: 22 Ω at 3.3 V); bias network | no | CK-13 | OpenEnergyMonitor (r) |
| 25 | protective earth and equipment class | no – judgement, M-6 for a sale | – | IEC 61140 (v) |
| 26 | Nixie 170–200 V and Geiger 400 V: switch, diode, capacitor ratings; 1.25 / 2.5 mm spacing | covered: G-8, E-2; spacing: no | CK-9, CK-22 | KiCad IPC-2221 (r) |
| 27 | capacitor banks (flash 5–9 J, coilgun 320 J) without bleeder | no | CK-24 | KiCad IEC 60664 F.2 (r) |
| 28 | ESD and surge on pins to a cable: IEC 61000-4-2 8 kV contact; emonTx 1 kΩ and TVS | partly: H-7 | CK-16, BL-12 | OpenEnergyMonitor (r); IEC 61000-4-2 (v) |
| 29 | reed switches on cables: pull-ups, 100 ms debounce, vane voltages 30 mV apart | partly: H-3; the ADC: no | HT-1, CK-6 | SparkFun Weather Meter Kit library (r) |
| 30 | buses on long wires: I2C bus capacitance, 1-Wire, RS-485 terminations and bias | partly: G-11 | CK-3, CK-17, FT-2 | ESPHome I2C and 1-Wire (r); UM10204 (v) |
| 31 | INA219 26 V, INA226 36 V common mode; shunt full scale and power | covered with part facts: G-3, E-3, E-2 | PF | Tasmota (r); TI INA219, INA226 (v) |
| 32 | Kelvin connection of shunts: 1 mΩ of shared copper is 10 % on 10 mΩ | no | reviewer question | v |
| 33 | thermocouple: MAX6675 T− to ground, MAX31855 T− never to ground, 10 nF across | no | CK-13 | Analog Devices MAX31855, MAX6675 (x) |
| 34 | ADC window and source impedance (ESP32 per attenuation; ESP8266 0–1 V; ACS712-05B 3.43 V at +5 A) | no | CK-6 | ESP-IDF (r); ESPHome ADC (r) |
| 35 | measurement front ends on mains: CAT II 300 V → 2.5 kV impulse, clearance 3.0 / 5.5 / 8.0 mm for 4 / 6 / 8 kV | no | CK-9, CK-10 | KiCad IEC 60664 F.1, F.2 (r) |

### Guitar effect pedals (37)

| # | Pitfall | edakit today | Candidate | Source |
| --- | --- | --- | --- | --- |
| 1 | germanium Fuzz Face bias: the fixed parts need Q1 gain 70–80 and Q2 110–130; AC128 spans 45–165; leakage doubles every 10 °C | no – no transistor corners | FT-17, FT-11 | ElectroSmash Fuzz Face, germanium fuzz (r) |
| 2 | PNP positive ground: the jack sleeves sit on +9 V and short a shared supply | no | HT-18 | ElectroSmash germanium fuzz, Rangemaster (r) |
| 3 | Fuzz Face input 5.2–8.4 kΩ, output 15 kΩ (about 125 kΩ at mid volume: 2.1 kHz with 600 pF of cable) | no | CK-27, FT-18, FT-12 | ElectroSmash Fuzz Face (r) |
| 4 | AM radio in high-gain transistor stages: the base–emitter junction rectifies; 100 pF base–collector, base stopper | no | HT-8 | ElectroSmash germanium fuzz (r); forums (x) |
| 5 | Big Muff: 48.6 dB in two clipping stages, 470 pF Miller capacitors for stability, bias windows | no | FT-17, FT-11, CK-31 | ElectroSmash Big Muff (r) |
| 6 | Tone Bender MKII self-biases through leakage; the bias target is disputed | no | FT-17 | forums (x) |
| 7 | op-amps at 9 V: TL07x swing 1.5–3 V short of each rail, common mode 3–4 V above V−; phase reversal | no model | FT-3 | ST TL07x (r); ElectroSmash Klon (r) |
| 8 | clipping diodes against the swing: an LED (1.5–1.7 V) in a 9 V feedback loop; octave rectifiers need matched diodes | no | FT-3, FT-12 | ElectroSmash Tube Screamer, Klon, Big Muff (r) |
| 9 | 4.5 V reference: loads ≥ 10 × the divider, 47–100 µF, 0.5 s settling thump | partly: G-6 | FT-11, BL-17 | ElectroSmash Klon, Tube Screamer (r) |
| 10 | Klon charge pump +18/−9 V: 27 V across an op-amp; from 12 V about 36 V, the TL07x maximum | with part facts: E-3 `vdd_op_max` with a 12 V supply corner | PF, CK-31 | ElectroSmash Klon (r); ST TL07x (r) |
| 11 | LM308 needs 30 pF across pins 1 and 8; slew rate 0.3 V/µs | no | CK-28 | ElectroSmash ProCo RAT (r) |
| 12 | JFET spread (J201 IDSS 0.2–1.0 mA, VGS(off) −0.3…−1.5 V): drain between about 5.2 and 8.2 V with fixed resistors | no | FT-17 | ElectroSmash 1Wamp (r) |
| 13 | BS170 is D-G-S, 2N7000 S-G-D; VGS(th) 0.8–3.0 V; gate unprotected | covered: P-1, L-10 for the pinout; the spread: no | FT-17 | forums (x); partinfo (r) |
| 14 | input impedance against 1 MΩ (Tube Screamer 446k, RAT 494k, V847 wah 69.5k); input high-pass; series resistor against ESD | no | CK-27, BL-16, HT-8 | ElectroSmash analyses (r) |
| 15 | output impedance and minimum load: PT2399 output wants > 100 kΩ, FV-1 ≥ 10 kΩ, PCM3060 ≥ 10 kΩ | no | CK-13 | ElectroSmash PT2399 (r); FV-1 datasheet (r) |
| 16 | OTA compressors: CA3080 bias current ≤ 2 mA, differential input ≤ 5 V, about 100 mVpp linear range | no model | CK-13, FT-3 | CA3080 datasheet (r); ElectroSmash Dyna Comp (r) |
| 17 | LFO and tap-tempo ticks through supply and ground (vactrol LED 20–40 mA; 1 kHz PWM into a PT2399) | no | HT-16, HT-8 | ElectroSmash CE-2 (r); Bontempo (r) |
| 18 | phaser: 2N5952 VGS(off) −1.3…−3.5 V, matched FETs, trimmer range | no | FT-17 | ElectroSmash Phase 90 (r) |
| 19 | wah: V847 input 69.5 kΩ; the 500 mH inductor picks up the amplifier's transformer field | no | CK-27; reviewer question | ElectroSmash Crybaby (r) |
| 20 | 5 V regulators for PT2399 (30 mA) and Belton (60–100 mA): 78L05 at about 200 °C/W; 78L05 OUT-GND-IN against 7805 IN-GND-OUT | covered: E-3 regulator temperature with `rth_ja_k_per_w`, P-1 and L-10 for the pinout | – | ElectroSmash PT2399 (r); forums (x) |
| 21 | PT2399 pin 6 below 2 kΩ during the first 400 ms latches the chip | no | CK-13 | ElectroSmash PT2399 (r); DIYSynthMNL (r) |
| 22 | PT2399 noise: pins 3 and 4 joined short; filter capacitors per delay; input 0.5–1 Vrms, clips above 1.3 Vrms | no | CK-13, CK-31 | ElectroSmash PT2399 (r) |
| 23 | BBDs: MN3007 −10…−15 V, MN3207 +5…+10 V (a 12 V outlet exceeds it); clock pins about 700 pF; clock filter | with part facts: E-3 supply range | PF, CK-31 | ElectroSmash MN3007, CE-2 (r) |
| 24 | FV-1: 3.3 V, abs. max 3.5 V; every pin −0.5 V … VDD + 0.5 V, so pots go to 3.3 V; T0 and T1 tied; input RC; output load ≥ 10 kΩ | partly: G-3, E-3 | CK-5, CK-13 | FV-1 datasheet (r) |
| 25 | FV-1 crystal 32.768 kHz: short leads, 15 pF on X2; EEPROM solder joints | no | CK-13, CK-31 | FV-1 datasheet (r) |
| 26 | converter full scale and input impedance against the guitar: SGTL5000 0.24–3.12 Vpp, PCM3060 10 kΩ, Daisy Seed 3.6 Vpp at 13.6–30 kΩ | no | CK-6, CK-27, BL-16 | PJRC Audio library (r); PCM3060 via a GitHub transcription (r) |
| 27 | anti-aliasing: pedalSHIELD first order near 5 kHz; RP2040 ADC about 8.7 effective bits | no | FT-12 | x |
| 28 | 3.3 V and 9 V domains: a 4.5 V bias into 3.3 V parts; 9 V live while the 3.3 V rail is still 0 V | partly: G-3 | CK-5, FT-8 | FV-1 datasheet (r); ST TL07x (r) |
| 29 | digital pedals against the outlet: FV-1 40–70 mA, an ESP32 asks for ≥ 500 mA, outlets 100–500 mA | covered: E-3 source `i_max_a`; the bursts: no | FT-1 | FV-1 datasheet (r); Espressif HDG (r) |
| 30 | power-up and brown-out: reset held until VDD is valid; the DC step at the output; relay state | partly: E-5 supply ramps | FT-1, FT-11 | ElectroSmash Back Talk (r); relay-bypass (r) |
| 31 | relay bypass: a latching relay keeps its state when power is lost – silence; coil 20–34 mA; mute 35 ms | partly: G-13, E-3 pull-in | BL-18, CK-30 | relay-bypass (r) |
| 32 | battery switched through the input jack's ring; the DC jack's lug must break battery plus | no | HT-15 | ElectroSmash (r); forums (x) |
| 33 | layout oscillation: input and output closer than 2.5 mm along a run; shared return paths | no | CK-31 | forums (x); ElectroSmash 1Wamp (r) |
| 34 | supply filtering against current (47 Ω at 30 mA drops 1.4 V); switch-mode adapter noise | partly: E-3 voltage at the part | HT-16, BL-17 | ElectroSmash (r) |
| 35 | daisy chains, AC and centre-positive pedals; a series part in the DC jack's ground leg bypassed by the cable shields | no | HT-18 | ElectroSmash CE-2 (r); x |
| 36 | 12 and 18 V outlets: 16 V electrolytics marginal; a 9.1 V shunt Zener on 12 or 18 V; a shunt reverse diode | covered: G-8 with the supply corner, G-10, E-2 for the Zener | – | ElectroSmash Crybaby, Dyna Comp (r) |
| 37 | electrolytic polarity around the 4.5 V reference in every state; DC across pots | no | CK-7, CK-30 | forums (x) |

### Guitar instrument, amplifiers, DI and switching (39)

| # | Pitfall | edakit today | Candidate | Source |
| --- | --- | --- | --- | --- |
| 1 | pickup loaded by a low input impedance: LM386 50 kΩ, Daisy Seed 13.6–30 kΩ, SGTL5000 about 29 kΩ, passive DI 140–290 kΩ | no | CK-27, BL-16, FT-18 | x |
| 2 | cable 66–164 pF/m; an op-amp buffer oscillates into the cable without a series resistor (about 100 Ω) | no | CK-16, FT-2, FT-18 | x |
| 3 | pot load and taper: 500k ∥ 500k ∥ 1 MΩ = 200 kΩ; "A" is log in the US and linear in Europe; 25k for EMG | no | PF, FT-12 | x |
| 4 | treble loss with the volume turned down (about R/4 = 125 kΩ: 2.1 kHz with 600 pF); treble-bleed values | no | FT-12, FT-18 | x |
| 5 | humbucker colour codes, phase and coil split | no – judgement | FT-18 | x |
| 6 | cavity shielding not grounded; copper tape shorting the jack | partly: L-15 finds floating copper on a board | – | x |
| 7 | the string ground ties the player to the amplifier's ground; an RC in it needs a Y-class capacitor | no | HT-19 | x |
| 8 | battery switched through the output jack's ring; EMG about 80 µA per pickup | no | HT-15, FT-11 | x |
| 9 | headroom at 9 V against 18 V: TL072 about 1.5 V from each rail | no model | FT-3 | x |
| 10 | piezo needs 10–20 MΩ and more; a charge amplifier needs its feedback resistor | no | CK-27, CK-25 | x; piezopro (r) |
| 11 | op-amp bias current through a bias resistor of megohms: NE5532 200–800 nA × 10 MΩ = 2–8 V offset | no model | FT-3 | x |
| 12 | passive DI: the input impedance is the preamp's input × n² (12:1 gives 216–288 kΩ) | no | FT-12, FT-18 | x |
| 13 | 48 V phantom power reaching the circuit through 6.81 kΩ, 10 mA; hot-plug surges to −25…−30 V | partly: G-8 when the net's range holds 48 V | FT-8, CK-13 | x |
| 14 | XLR pin 1 on signal ground (the pin-1 problem) | no | CK-13 | x |
| 15 | LM386: inputs 50 kΩ to ground and ground-referenced; DC coupling from a biased stage | no | CK-27, FT-3 | x; tardate Ruby (r) |
| 16 | LM386 oscillation: Zobel 10 Ω + 47 nF at pin 5, bypass at pin 7, decoupling at pin 6 | partly: G-6 | CK-13, CK-31 | x; tardate Little Gem (r) |
| 17 | LM386 supply (N-1 and N-3 4–12 V, N-4 5–18 V), output capacitor 220–250 µF, a 9 V battery's internal resistance | partly: E-3 supply range, cell `r` | FT-1, FT-12 | x |
| 18 | TDA2003 18 V maximum; TDA7052 bridge-tied with a fixed 40 dB | partly: E-3, G-3 | CK-8 | x |
| 19 | LM1875 and TDA2050: tab at V− on a grounded heat sink; stable only at a gain of 10 or more | partly: E-2 temperature with `rth_ja_k_per_w` | CK-28, HT-11 | x |
| 20 | headphone amplifiers: 1 V into 32 Ω is 31 mA; TL072 wants ≥ 2 kΩ; a divider as virtual ground | no model | FT-3 | x |
| 21 | tube filter capacitors below the unloaded B+ (330 VAC: 467 V, 513 V at +10 % mains); series capacitors without balancing | partly: G-8 when the net's range holds it | CK-29, FT-7 | x |
| 22 | bleeders and standby: the charge stays with the tubes pulled; standby ahead of the reservoir | no | CK-24 | x |
| 23 | heater supply: reference, elevation (12AX7 Vhk 180 V), 6.3 VAC too low for an LM317 | no | out of scope | x |
| 24 | output transformer without a load: plate spikes arc | no | out of scope | x |
| 25 | fuses: primary at most V / R_primary, slow-blow; an HT fuse | partly: G-17 | CK-10 | x |
| 26 | tube amplifier ground returns; grid stoppers at the pin | no | CK-31; out of scope | x |
| 27 | death cap and ground switch: 0.047 µF from line to chassis | no | CK-10, HT-19 | x |
| 28 | starved-plate 12AX7 at 9–24 V: models do not hold; heater 300 mA, cold inrush 2.5–7 × | partly: E-3 source current, with a heater (FT-6) | FT-1, FT-6 | x |
| 29 | high-voltage boost in pedals (12 → 200–300 V): MOSFET ≥ 400 V, light-load bursts in the audio band | partly: G-8 | CK-22, HT-16, CK-31 | x |
| 30 | relay coils on the pedalboard supply (TQ2-9V 15.5 mA, eight relays 124 mA); relays on the MCU's rail cause brown-outs | covered: E-3 pull-in, G-13; the dip: no | FT-1, BL-18 | x; relay-bypass (r) |
| 31 | relay contacts at signal level need gold (minimum load 10 µA / 1 mV); DC across the contact pops | no | CK-30, BL-18 | x; relay-bypass (r) |
| 32 | ground loops between loops, amplifiers and supplies | no – judgement | HT-18 | x |
| 33 | a tuner or analyser loads the pickup | no | CK-27 | x |
| 34 | codec line inputs against guitar level (120–850 mV peak); a TL072 does not work on 3.3 or 5 V | no | CK-6, CK-27, FT-3 | PJRC Audio library (r); x |
| 35 | the MCU's ADC as guitar input: ESP32 windows, bias at the window's centre, anti-aliasing | no | CK-6, FT-12 | ESP-IDF ADC (r); PJRC (r) |
| 36 | codec outputs: SGTL5000 HP_VGND never to ground; out-of-band noise; X7R and Y5V distort | no | CK-13, HT-17 | x; PJRC (r) |
| 37 | USB audio: ground loop with the PC; ADuM3160 full speed only; its isolated converter needs 10 % load | partly: E-3 minimum load of a source | FT-5, HT-8 | ADuM3160 USB isolator repository (r) |
| 38 | pedalboard power: shared returns; charge pumps at about 10 kHz | no | HT-16, HT-18 | x |
| 39 | RF at high-impedance inputs: a series resistor first, then 47–100 pF at the jack | partly: H-7 | HT-8, BL-16 | x |
