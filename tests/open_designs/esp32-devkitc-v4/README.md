# ESP32-DevKitC V4 – a published design, transcribed for edakit's tests

**Source:** Espressif Systems, schematic *ESP32_DevKitc_V4*, Rev V4, dated 2017-12-06, one sheet –
<https://dl.espressif.com/dl/schematics/esp32_devkitc_v4-sch.pdf>, read on 2026-10-31. Espressif publishes it as the
reference of its development board; the PDF states no licence. What is here are the circuit's facts – parts,
values, connections – transcribed for testing edakit, not the drawing.

**Transcribed:** micro-USB J1 (VBUS, D−, D+, ID open, GND and shell) with the ESD diodes D4–D6 (LESD5D5.0CT1G), the
Schottky D3 (BAT760-7) from VBUS to EXT_5V, the AMS1117-3.3 U2 with C1 and C3 (22 µF / 10 V), the power LED D1 with R2
(2 kΩ); the CP2102N-A01-GQFN28 U1 with C19, C20, the VBUS divider R25/R26 (22.1 kΩ / 47.5 kΩ), the RSTb pull-up R24
(2 kΩ), the 0 Ω links R17/R18 to the module's UART0, the auto-program circuit Q1/Q2 (SS8050) with R21/R22 (10 kΩ);
the ESP32-WROOM-32 D2 with C21/C22, the EN delay R11 (10 kΩ) / C9 (100 nF); the buttons SW1 (IO0) and SW2 (EN) with
C15/C14; the headers J2/J3 (1 × 19). Left out as the schematic marks them not fitted: R23 (10 kΩ, NC) and U3
(ESP32-WROVER, NC).

**Stand-ins:** the schematic names values, not order numbers. Where it names a part number (AMS1117-3.3, CP2102N,
BAT760-7, LESD5D5.0CT1G, ESP-WROOM-32) the LCSC part of that number is used; SS8050-G is CJ's SS8050 (C2150); the
"RED LED" a NationStar NCD0805R1; resistors and capacitors 0805 parts of the values and ratings the schematic gives;
the micro-USB receptacle, the buttons and the headers parts of the same function. Each parts entry names its
datasheet, what was read in it and what is open (`verified`).

**What edakit finds** – and how each finding is judged – is in `findings.toml`, held by `tests/test_open_designs.py`.
