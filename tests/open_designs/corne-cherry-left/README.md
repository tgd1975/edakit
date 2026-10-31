# Corne keyboard v4, left half – a published design, transcribed for edakit's tests

**Source:** foostan, *Corne keyboard* (crkbd), <https://github.com/foostan/crkbd> at commit 63366fb
(63366fb7f51cf2a796462fdd90527e99dd126055), the sheet `pcbs/common/left.kicad_sch` ("Corne Left", rev 4.0.0,
2023-10-07) as the sheet "left" of `pcbs/corne-cherry/hotswap/corne-cherry.kicad_sch` ("Corne", rev 4.1.0, 2024-05-07),
read on 2026-10-31 from a read-only clone. The LCSC numbers come from the schematic's "JLCPCB Part #" fields and
`pcbs/corne-cherry/hotswap/jlcpcb/production_files/BOM-corne-cherry.csv`. The netlist was resolved from the schematic
(wires, junctions, labels, power symbols) by a reader outside this repository and checked against the board file
`pcbs/corne-cherry/hotswap/corne-cherry.kicad_pcb`: all 313 pins of the sheet are on the same nets there.

**Licence and attribution:** the repository's root holds two licence files, `LICENSE_CC` (Creative Commons
Attribution 4.0 International) and `LICENSE_MIT` (MIT, "Copyright (c) 2023 foostan"); neither its README nor the files
say which of them covers the PCB files. This transcription is offered under CC BY 4.0, the licence of the two that
asks for attribution and a note of changes, and keeps foostan's copyright notice. Attribution: *Corne keyboard* by
foostan, <https://github.com/foostan/crkbd>, CC BY 4.0. Changes: the circuit's facts – parts, values, connections –
are transcribed into edakit's graph, not the drawing; unnamed nets got names (LED_VDD, XIN, USB_DP, …); the parts
stated below are left out or stand in; the parts entries are written from the parts' datasheets. This is a reading of
the repository's files, not legal advice.

**No key matrix:** the Corne v4 wires each of its 23 keys from its own RP2040 GPIO to GND (QMK's direct pins) – no
rows, no columns, no diode per key. edakit's matrix rules (REQ.missing/matrix, REQ.forbidden/matrix) have nothing to
judge here. The older versions with a Pro Micro and a diode per key appear only in the build guides (the parts list
of `docs/corne-light/v2/buildguide_low_edition_en.md`: two Pro Micros, 42 diodes, all mounted the same way); their
schematics are not in the tree at 63366fb, and the clone holds only that commit.

**Transcribed:** the USB-C receptacle J1 (TYPE-C-31-M-13C) with R1/R2 (5.1 kΩ) on CC1/CC2, SBU open, the ESD array
U3 (TPD4E05U06, D+ and D− through its flow-through pins), the Schottky ZD1 (RB521S30T1G) from VBUS to +5V, C6
(10 µF), the regulator U2 (NCP1117LPST33T3G) to +3V3 with C7–C16; the RP2040 U1 with its core regulator on +1V1
(C3–C5), the 12 MHz crystal Y1 with C1/C2 (27 pF) and the damping resistor R3 (1 kΩ) at XOUT, R4/R5 (27 Ω) in D+ and
D−, the flash U4 (W25Q128JVSIQ) on the QSPI lines with the /CS pull-up R7 (10 kΩ), the BOOT button SMDSW1 with R6
(1 kΩ) on QSPI_SS and the RESET button SMDSW2 on RUN, the VBUS divider R8/R9 (5.6 kΩ / 10 kΩ) to GPIO13, GPIO21 on
+3V3 (this is the left half); the keys SW1–SW21 and EXSW1/EXSW2, each from its GPIO to GND; the 23 SK6812MINI-E
LED1–LED21, EXLED1, EXLED2 in one chain from GPIO10, fed from LED_VDD one diode (D1, 1N4148WT) below +5V; the TRS jack
J2 (tip +5V, ring the split link on GPIO12, sleeve GND); the OLED header J3 (SDA on GPIO6, SCL on GPIO7, +5V, GND) and
the SWD header J4.

**Left out and stand-ins:** the encoder positions EXSW1/EXSW2 are RotaryEncoder_Switch symbols; the BOM fits the key
socket there, so they are transcribed as fitted – the socket on the switch pads S1/S2, the encoder pads A, B, C empty,
which leaves GPIO5 (RE0A) open. JP1, a solder jumper drawn open between LED18's and LED21's data outputs, joins nothing
open and is left out, as are the breakaway tabs BT1–BT4 (no pins). The key switches themselves are the builder's: the
Kailh hot-swap socket of the BOM (CPG151101S11-16) stands for each key. J3 and J4 are not in the BOM: XFCN PZ254V-11
pin headers of 4 and 3 positions stand in (the 4-pin one without an LCSC number – LCSC's search refused the request).
The schematic's symbols for U3 (TPD4EUSB30) and ZD1 (ESD5Zxx) name other parts than its values and the BOM; the
values and the BOM are taken. Pin numbers are those of the KiCad symbols, which are the footprints' pads – for the
SK6812MINI-E the Corne's own footprint (1 VDD, 2 DOUT, 3 VSS, 4 DIN), not the datasheet's numbering.

**Voltages:** USB 4.75–5.25 V on VBUS; +5V behind the Schottky (the right half is fed from it through the jack, not
simulated); LED_VDD one 1N4148WT drop lower, so that the RP2040's 3.3 V data reaches the LEDs' VIH of 0.65 VDD; 3.3 V
from the NCP1117LP; 1.1 V from the RP2040's own regulator; the GPIOs at 3.3 V, the keys read with the pull-ups the
firmware enables. Each parts entry names its datasheet, what was read in it and what is open (`verified`).

**What edakit finds** – and how each finding is judged – is in `findings.toml`, held by `tests/test_open_designs.py`.
The design showed four false alarms of edakit, fixed and held by `tests/test_open_design_fixes.py`, and a drawing
that changed from run to run (the catalog page's test holds it).
