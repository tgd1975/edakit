# Issue 6 – six EasyEDA library symbols that differ from their manufacturers' datasheets

Not for easyeda-mcp-pro: a report to the component library EasyEDA Standard serves and LCSC links to
(`https://easyeda.com/api/products/<LCSC>/components`, the data `edakit part import` reads), through the correction
channel the owner chooses. Not sent yet (2026-10-31).

### Title

```text
Symbol pins of C2874885, C5446, C81582, C41407547, C22451885, C719745 differ from the manufacturers' datasheets
```

### Report

```markdown
Six symbols in the EasyEDA component library differ from the manufacturer's datasheet in a way that a schematic drawn
from them wires the part wrongly. Each was compared with the manufacturer's datasheet and with the library's own
footprint for the same part (data read from https://easyeda.com/api/products/<LCSC>/components?version=6.4.19.5 on
2026-10-31).

1. **C2874885 – Worldsemi WS2812B-V5/W** (footprint LED-SMD_4P-L5.0-W5.0-TL-1, pads 1–4)
   - Symbol: pins 1 VDD, 2 DOUT, 3 VSS, **3 DIN** – two pins carry the number 3; there is no pin 4.
   - Datasheet: Worldsemi WS2812B-V5/W data sheet V6.1 (2022-09-08), page 2, "PIN Function": 1 VDD, 2 DOUT,
     3 VSS, **4 DIN**.
   - Effect: the data input joins ground on pad 3, pad 4 stays unconnected – the LED does not take data.

2. **C5446 – Torex XC6206P332MR-G** (footprint SOT-23-3)
   - Symbol: 1 GND, **2 Vin, 3 Vout**.
   - Datasheet: Torex XC6206 Series ETR0305_004b, page 2, "PIN ASSIGNMENT", SOT-23: 1 VSS, **2 VOUT, 3 VIN**.
   - Effect: a schematic wired by the symbol's names feeds the regulator from its output.

3. **C81582 – TI DRV8825PWPR** (footprint HTSSOP-28_L9.7-W4.4-P0.65-LS6.4-BL-EP, pads 1–29)
   - Symbol: 28 pins; the exposed-pad pin EP carries the number **28** like GND; there is no pin 29.
   - Datasheet: TI SLVSA73F (revised July 2014), page 3, "Pin Configuration and Functions" (PWP package with
     PowerPAD; GND on 14 and 28); page 18, typical application (PPAD to GND); section 11.3.2, page 23 (the pad
     must be connected to copper on the PCB).
   - Effect: pad 29, the PowerPAD, gets no net – neither ground nor the heat path the datasheet asks for.

4. **C41407547 – Raspberry Pi Pico 2** (footprint COMM-SMD_L51.0-W21.0-P2.54_SC0916, pads 1–43, TP1–TP6)
   - Symbol: the test pads TP2–TP6 carry the numbers **2–6**, the same as GP1, GND, GP2, GP3, GP4; the footprint
     names those pads TP2–TP6. Pin **41 is named SWDIO, 43 SWCLK**.
   - Datasheet: Raspberry Pi Pico 2 Datasheet (release of 03 July 2026, build d4e0f1799616): page 4, Figure 2 (debug
     pads SWCLK, GND, SWDIO from the side of pin 20 to the side of pin 21); page 8, Figure 4 (pins 1–40, the debug
     pads D1–D3, the test points TP1–TP7 as pads of their own); page 9 (the test points TP1–TP7). In the library's
     footprint pad 41 sits next to pin 20 and pad 43 next to pin 21: **41 is SWCLK, 43 SWDIO**.
   - Effect: TP2–TP6 (USB DM, USB DP, GPIO23, GPIO25/LED, BOOTSEL) join GPIO pins 2–6 in a netlist; the debug pins
     are wired crossed.

5. **C22451885 – Lite-On 6N138S-TA1-L** (footprint SMD-8)
   - Symbol: pin 2 named **"2"**, pin 3 named **"NC"**.
   - Datasheet: Lite-On 6N138-L / 6N139-L series, DS70-2009-0001 Rev A (04/12/2016), page 1/15, "1.3 Functional
     Diagram": 1 NC, **2 ANODE, 3 Cathode**, 4 NC, 5 GND, 6 VO, 7 VB, 8 VCC.
   - Effect: the numbers are right, but a schematic wired by the names leaves the LED's cathode unconnected as "NC".

6. **C719745 – Panasonic AQY212GS** (footprint SOP-4_L4.4-W4.3-P2.54-LS6.8-BL, pads 1–4)
   - Symbol: three pins, numbered 1, 2 and **4** (named "1", "2", "3"); no pin 3.
   - Datasheet: Panasonic PhotoMOS GU SOP 1 Form A High Capacity, ASCTB133E 202103, page 4, "Schematic and wiring
     diagrams": LED between pins 1 and 2, the output between pins **3 and 4**.
   - Effect: pad 3 stays unconnected – the output switch cannot be wired.
```

### Additional context

```markdown
Found while writing checked parts entries from the datasheets for edakit (https://github.com/tgd1975/edakit,
edakit/parts/); edakit now compares a cached library symbol with the parts entry and the footprint (a number given to
two pins, a pad without a pin) and reports such symbols. The data as the library answered it is recorded in
edakit's tests: tests/fixtures/easyeda/C2874885.json, C5446.json, C81582.json, C41407547.json, C22451885.json, and
for C719745 (the library refused the request that day) the symbol as cached earlier the same day,
tests/fixtures/library_cache/library/C719745.json.
```
