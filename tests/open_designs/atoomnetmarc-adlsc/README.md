# ADLSC, Atoomnet's Digital Led String Controller – a published design, transcribed for edakit's tests

**Source:** atoomnetmarc, *ADLSC, Atoomnet's Digital Led String Controller* ("ESP32 based 5V digital LED controller
build for use with WLED"), <https://github.com/atoomnetmarc/ADLSC> at commit 3aecf18
(3aecf18cfb2dffa2b83f3e08038c563ee9e2df65, 2026-01-23), the schematic `Kicad/ADLSC.kicad_sch` (title block rev V1.0,
2025-01-05, KiCad 8.0.7; the same drawing as `Kicad/ADLSC-schematic.pdf`) and the repository's `README.md` (power
supply, WLED configuration, wiring), read on 2026-11-03 from a read-only clone. The netlist was resolved from the
schematic (wires, junctions, labels, power symbols) by a reader outside this repository and checked against the board
file `Kicad/ADLSC.kicad_pcb` of the same commit: all 187 pads are on the same nets there.

**Licence and attribution:** *ADLSC* by atoomnetmarc, <https://github.com/atoomnetmarc/ADLSC>, Apache License 2.0
(<https://www.apache.org/licenses/LICENSE-2.0>) – the repository's `LICENSE` and the schematic's title block ("Apache
License 2.0"). A copy of the licence is in this folder's `LICENSE`, as its section 4(a) asks; the repository has no
NOTICE file and no copyright line of its own (its licence's appendix is left unfilled), so the attribution above is
the notice kept. Changes (section 4(b)): the circuit's facts – parts, values, connections – are transcribed into
edakit's graph, not the drawing or the board; the parts the schematic marks not fitted and the mounting holes are left
out; unnamed nets got names (Q2_G, U2_1Y, A1_5V, …); pin numbers follow the LCSC parts' entries (the DevKitC's J3 and
the green LEDs are numbered otherwise in ADLSC's symbols); the parts named below stand in; the parts entries are
written from the parts' datasheets; the simulation's supply and loads are this transcription's. This is a reading of
the repository's files, not legal advice.

**Why this design:** the WLED controller – the board makers build to drive addressable LED strips from an ESP32 at
several amperes: a 5 V supply of 10 A, the ESP32's 3.3 V data shifted to 5 V by a 74AHCT125 with 100 Ω in series,
the strips' power switched by the firmware and fused per output. No reference circuit has an LED-strip output, and of
the open designs the Corne feeds its SK6812s one diode below 5 V to make 3.3 V data reach them and the SparkFun
converter shifts levels with BSS138s; ADLSC brings the TTL-input buffer, a reverse-polarity N-MOSFET in the ground
return, a voltage supervisor on the ESP32's EN, P-MOSFET high-side switches driven from a GPIO through an NPN, glass
fuses with blown-fuse LEDs, a polyfuse, TVS diodes on every 5 V rail, and an ESP32 development board plugged in behind
a Schottky diode – real parts with their datasheets, in a class of board that WLED's users copy, where a false alarm
would meet many.

**Transcribed:** the push-in terminal J1 (+5V_IN on pin 2, 0V_IN on pin 1) for the Mean Well IRM-60-5ST the README
names, with the bidirectional TVS D4 (SMBJ5.0CA) across it, the reverse indicator D1 (red) with R1 (220 Ω) and the
power LED D2 (green) with R2 (10 kΩ); Q1 (AOD442) in the ground return – drain 0V_IN, source GND, gate +5V_IN; the
polyfuse F1 (0.5 A, 1812) from +5V_IN to +5V with its trip indicator D3 (red) and R3 (220 Ω) across it, the TVS D5 on
+5V and the bulk capacitor C2 (470 µF / 16 V); the supervisor U1 (MAX809M) on +5V, its RESET through R5 (100 Ω) to EN
of A1, the ESP32-DevKitC with ESP32-WROVER-E in 2 × 19 sockets, fed through the Schottky D14 (SS34) at its 5V pin; the
level shifter U2 (74AHCT125D, C1 100 nF) – DATA1_3V (GPIO25) and DATA2_3V (GPIO26) with the pull-downs R8/R14 (10 kΩ)
into gates A and B, their outputs through R12/R16 (100 Ω) to the data terminal J4, each with a green LED D9/D10
through 10 kΩ (R15/R18) to GND; gates C and D with their inputs and enables on GND, outputs open; the LED power: Q2 and Q4
(TSM160P02CS) from +5V_IN, their gates on Q2_G with R19 (10 kΩ) and C3 (100 nF) to +5V_IN and R20 (100 Ω) to the
collector of Q3 (MMBT2222), whose base R21 (1 kΩ) takes from POWER_ON (GPIO4); behind each P-MOSFET a 3 A slow-blow
5 × 20 mm fuse in clips (F2, F3) with its blown-fuse LED (D8, D11 red, R11/R22 220 Ω across it), the TVS D7/D13, the
output LED D6/D12 (green, 10 kΩ R10/R23) and the terminals J3 (+5V_LED1, GND) and J6 (+5V_LED2, GND). Left out: the
Pmod positions J2 and J5 with R4, R6 (4K7) and R7, R9, R13, R17 (100R), which the schematic crosses out as not fitted
and the README leaves to the builder – so the DevKitC's 3V3, IO5, IO18, IO19, IO21, IO22 and IO23 go nowhere; the
mounting holes H1–H4. The simulation feeds J1 with the IRM-60-5's 5 V ± 2.5 % through two wires of AWG 18 (0.02 Ω,
the length assumed) and runs three loads: standby (the LED power off), WLED's 5 A limit shared by both outputs, and each
output at its fuse's 3 A.

**Stand-ins:** the schematic names values, few order codes. Where it names a part number the LCSC part of that number
is used: 74AHCT125D (Nexperia 74AHCT125D,118), AOD442 (AOS), TSM160P02CS (TSM160P02CS RLG), SMBJ5.0CA (Littelfuse – the
datasheet the schematic links), SS34 (MDD, the library's), the Weidmüller 1824810000 of "1824810000 or 1760520000",
and ESP32-DevKitC + ESP32-WROVER-E (Espressif's ESP32-DEVKITC-VE). MAX809M is onsemi's MAX809MTRG (the schematic's
symbol is KiCad's TPS3839DBZ), MMBT2222 onsemi's MMBT2222LT1G. The "Polyfuse 0.5A >5V" is PTTC's SMD1812P050TF/30,
the "T3AL250V 5x20mm 3A slow blow fuse" Littelfuse's 0239003.MXP (the clips are not in the graph), the "16V 470uF" in
a 10 × 10.5 case HONORCAP's RVT1C471M1010; the red LEDs a NationStar NCD0805R1, the green ones a KENTO KT-0805G,
resistors and capacitors 0805 parts of the library. The SMBJ5.0CA is bidirectional: its pin 1 (the entry's cathode)
is put on the protected line whichever pad the drawing gives it, for the simulation's single-junction model. The
DevKitC's own circuit (AMS1117-3.3, EN network, Schottky from USB) is taken from the transcription in
`tests/open_designs/esp32-devkitc-v4`. Each parts entry names its datasheet, what was read in it and what is open
(`verified`).

**What edakit finds** – and how each finding is judged – is in `findings.toml`, held by `tests/test_open_designs.py`.
The design showed three false alarms of edakit, fixed and held by `tests/test_open_design_fixes.py`: Q1's gate taken
as floating, the low-side reverse-polarity N-MOSFET unknown to PATH.reverse (TD-125), and the bidirectional TVS D4
judged as one direction (TD-132).
