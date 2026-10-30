# Maker pitfalls against edakit

The pitfalls behind [maker-coverage.md](maker-coverage.md), one row each: the pitfall with its numbers, what edakit does
about it today, the candidate of the concept that would cover it, and the source. Status 2026-10-30, edakit at
`bf7450a`.

**edakit today:** *covered* (the check or hint named), *with part facts* (an existing check finds it once the parts
entry carries the datasheet value), *partly*, *no*. **Source tags:** **r** read in the primary document, **x** from a
search engine's extract of the cited page, **v** to verify – not reachable from this environment, or from memory. A
value tagged x or v is read in its source before it goes into a catalog entry.

## LEDs, lighting and displays (32)

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

## Motors, motion, robotics, 3D printers and CNC (35)

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

## Power supplies, batteries and low-power nodes (32)

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

## MCU boards, buses, radio, keyboards and HATs (39)

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
| 14 | UART TX to TX, RX to RX; CH340 at 5 V into a 3.3 V RX; CH340 V3 pin | covered: G-5, G-4, G-3; RX to RX with a pull-up passes | CK-13 | QMK serial driver (r) |
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

## Audio, mains, high voltage, outdoor and measurement (35)

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
