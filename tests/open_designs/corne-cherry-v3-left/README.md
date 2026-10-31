# Corne Cherry keyboard v3, left half – a published design, transcribed for edakit's tests

**Source:** foostan, *Corne Cherry* v3 (crkbd), <https://github.com/foostan/crkbd> at commit b473521
(b473521c92c2959997fea41be72e061f3e77797f, 2023-10-18, "Update directory trees", the parent of af19c6d), the
schematic `corne-cherry/pcb/corne-cherry.kicad_sch` ("Corne Cherry", rev 3.0.1, 2020-09-28), read on 2026-10-31 from
the git objects of a read-only clone. The sheet holds both halves side by side; transcribed is the half whose nets
carry no `_r` (the right half's are `row0_r`, `col0_r`, … on VDD and GNDA) – U1, J1, J2, RSW1, SW1–SW21, D1–D21,
LED1–LED27. The netlist was resolved from the schematic by a reader outside this repository and checked against the
board file `corne-cherry/pcb/corne-cherry.kicad_pcb` of the same commit: all 452 pins of the sheet are on the same
nets there. The parts follow the build guide `corne-cherry/doc/v3/buildguide_en.md` of that commit.

**Licence and attribution:** at b473521 the repository's root holds one licence file, `LICENSE`, the MIT licence,
"Copyright (c) 2019 foostan" (the CC BY 4.0 file of the current tree came later). The MIT licence asks that its notice
travel with copies and substantial portions:

> MIT License – Copyright (c) 2019 foostan. Permission is hereby granted, free of charge, to any person obtaining a
> copy of this software and associated documentation files (the "Software"), to deal in the Software without
> restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
> and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the
> following conditions: The above copyright notice and this permission notice shall be included in all copies or
> substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
> NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
> SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Attribution: *Corne Cherry* v3 by foostan, <https://github.com/foostan/crkbd>. Changes: the circuit's facts – parts,
connections – of one half are transcribed into edakit's graph, not the drawing; unnamed nets got names (`D1_A`,
`LED3_DOUT`, …); the rows and columns are marked as a key matrix; the parts the schematic does not name stand in as
stated below; the parts entries are written from datasheets. This is a reading of the repository's files, not legal
advice.

**The key matrix:** 21 keys in 4 rows × 6 columns on the Pro Micro – rows `row0`–`row3` on D4, C6, D7, E6, columns
`col0`–`col5` on F4, F5, F6, F7, B1, B3 – each key from its column through its own diode to its row, the cathode at the
row (current from column to row: QMK's COL2ROW). `row3` holds the three thumb keys. edakit's matrix rules find the
matrix well formed; `tests/test_open_designs.py` holds that, seeds faults into it (a key without its diode, a diode
turned round, all diodes turned round) and simulates a scan: with row0 low and SW1 pressed col0 reads 0.57 V, and with
SW1, SW2 and SW7 pressed while row1 is scanned col1 stays high – no ghost.

**Transcribed:** the Pro Micro U1 on headers (VCC, GND, RST, the matrix pins, TX0/D3 to the LED chain, RX1/D2 the
split link, D1/D0 SDA/SCL); the reset button RSW1 on RST; the TRRS jack J1 (tip `data`, ring GND, ring 2 VCC, sleeve
open); the OLED socket J2 (SDA, SCL, VCC, GND); the 21 keys SW1–SW21 with D1–D21; one LED chain on VCC from TX0/D3:
the six WS2812B LED1–LED6 (underglow) and the 21 SK6812MINI-E LED7–LED27 (per key), LED19 its end. The board has no
capacitor at all.

**Stand-ins:** the schematic names symbols, the build guide parts without numbers. The Pro Micro is SparkFun's
DEV-12640 (5V/16MHz), its entry from SparkFun's graphical datasheet, design files and hookup guide and the ATmega32U4
datasheet; the keys are the Kailh hot-swap socket CPG151101S11-16 (the build guide: sockets "compatible with Kailh
and Gateron"), the diodes the 1N4148W of edakit's library (SOD-123, as the build guide asks), the WS2812B the
WS2812B-V5/W of the library, the SK6812MINI-E the v4 design's entry, the reset switch the v4 BOM's tact switch, the
TRRS jack (MJ-4PP-9, "compatible with PJ320A") SparkFun's 4UCON 20153, the OLED socket a 4-pin XFCN header. Pin
numbers are those of the KiCad symbols; the jack's contacts are read from its symbol's drawing.

**Voltages:** USB 4.75–5.25 V at the Pro Micro, whose VCC follows USB through its 500 mA PTC (the closed jumper of the
5 V board) and feeds everything on the half – and the right half through the jack (not simulated). The ATmega32U4,
its I/O and the LEDs run at VCC.

**What edakit finds** – and how each finding is judged – is in `findings.toml`, held by `tests/test_open_designs.py`.
The design showed one false alarm and one thing the simulation could not express – a row released while another is
scanned –, both fixed and held by `tests/test_open_design_fixes.py`. Not in edakit: the direction the firmware scans
in (QMK's `DIODE_DIRECTION`) is not in the schematic, so the static rules hold the diodes to one direction only; the
scan load's expectations hold the direction the firmware needs.
