# Adafruit Micro-Lipo Charger with USB Type C Jack – a published design, transcribed for edakit's tests

**Source:** Adafruit Industries (Limor Fried/Ladyada; the schematic's AUTHOR attribute K. Townsend),
*Adafruit-MicroLipo-PCB*, <https://github.com/adafruit/Adafruit-MicroLipo-PCB> at commit d8ab4b0
(d8ab4b0f00c69a9f337a8d697bd15e0b9bae2e25, 2022-11-10), the Eagle schematic `Adafruit USB C microlipo charger.sch`
(Eagle 9.5.0 XML, last changed in commit b06c550 of 2019-11-05) – the board Adafruit sells as product 4410,
"Adafruit Micro-Lipo Charger for LiPoly Batt with USB Type C Jack" (<https://www.adafruit.com/product/4410>) –, read
on 2026-11-03 from a read-only clone. The netlist was resolved from the schematic's XML (parts, nets, each device's
pin-to-pad connects) by a script outside this repository and checked against the board file
`Adafruit USB C microlipo charger.brd` of the same commit: all 44 pads of the 15 connected parts are on the same
signals there. The product page was read the same day for what the schematic does not say (the jumper's purpose, the
cells it is meant for).

**Licence and attribution:** the repository's README says "Designed by Limor Fried/Ladyada for Adafruit Industries.
Creative Commons Attribution/Share-Alike, all text above must be included in any redistribution. See license.txt for
additional information."; `license.txt` is the legal code of Creative Commons Attribution-ShareAlike 3.0 Unported.
Attribution: *Adafruit Micro-Lipo Charger with USB Type C Jack* (`Adafruit USB C microlipo charger.sch`) by Limor
Fried/Ladyada for Adafruit Industries, <https://github.com/adafruit/Adafruit-MicroLipo-PCB>, CC BY-SA 3.0
(<https://creativecommons.org/licenses/by-sa/3.0/>) – this transcription is an adaptation under the same licence.
Changes: the circuit's facts – parts, values, connections – are transcribed into edakit's graph, not the drawing;
the unnamed nets got names (PROG, PROG_500, STAT, LED_RED, LED_GREEN); the USB-C receptacle's paired pads are the
stand-in's single pins on the same nets; the parts stated below stand in; the parts entries are written from the
parts' datasheets. This is a reading of the repository's files, not legal advice. The text the README asks to travel
with the design follows in its own words, without the pictures and the list and heading markup:

> Adafruit MicroLipo and MiniLipo Charging Boards/Backpacks. Click to purchase from the Adafruit Shop: Adafruit
> Micro-Lipo Charger for LiPo/LiIon Batt w/MicroUSB Jack - v1 (https://www.adafruit.com/product/1904); Adafruit
> Micro Lipo - USB LiIon/LiPoly charger - v1 (https://www.adafruit.com/product/1304); Adafruit Mini Lipo w/Mini-B
> USB Jack - USB LiIon/LiPoly charger - v1 (https://www.adafruit.com/product/1905); Adafruit LiIon/LiPoly Backpack
> Add-On for Pro Trinket/ItsyBitsy (https://www.adafruit.com/product/2124); Adafruit Micro-Lipo Charger for LiPoly
> Batt with USB Type C Jack (https://www.adafruit.com/product/4410); Adafruit Micro Lipo - USB LiIon/LiPoly charger -
> v2 (https://www.adafruit.com/product/1304). Oh so handy, this little lipo charger is so small and easy to use you
> can keep it on your desk or mount it easily into any project! Simply plug it via any MicroUSB cable into a USB port
> and a 3.7V/4.2V lithium polymer or lithium ion rechargeable battery into the JST plug on the other end. There are
> two LEDs - one red and one green. While charging, the red LED is lit. When the battery is fully charged and ready
> for use, the green LED turns on. Seriously, it could not get more easy. These are the PCB files for the Adafruit
> Mini/MicroLipo battery chargers. The Format is EagleCAD schematic and board layout. License: Adafruit invests time
> and resources providing this open source design, please support Adafruit and open-source hardware by purchasing
> products from Adafruit (https://www.adafruit.com)! All text above must be included in any redistribution. Designed
> by Limor Fried/Ladyada for Adafruit Industries. Creative Commons Attribution/Share-Alike, all text above must be
> included in any redistribution. See license.txt for additional information.

**Why this design:** the first charger among edakit's test circuits – no reference circuit has one (`power` is three
AA cells beside USB), and no other open design charges a cell. It puts a linear Li-ion charger with its behaviour
model on a published board: the current R_PROG programs, held against the MCP73831's 500 mA and the cell's 1C
(LIM.i/charge, LIM.backfeed into the cell), the charger's heat at a low cell (LIM.t), a second charge current set by a
solder jumper, a LiPo pack whose JST plug can come reversed (PATH.reverse on a battery holder), two status LEDs on a
tri-state output – the domain power with a real charger, and HINT.lithium and HINT.charge_termination on a part
makers use. Makers build and copy it everywhere: the MCP73831 with a PROG
resistor, two LEDs and a JST PH socket is the charger of most hobby LiPo projects – Adafruit's Micro-Lipo boards, the
same circuit on Feathers and countless clones –, so a false alarm here would meet many.

**Transcribed:** the USB-C receptacle X2 – VBUS of both rows on 5V, CC1 and CC2 each through 5.1 kΩ (R6, R5) to GND,
D+ and D− of both rows joined and taken to the pads, SBU1/SBU2 and the shell open (the CUI part's four shell legs have
no pin in the symbol and no signal on the board) –, C1 (10 µF) on 5V; the MCP73831T-2ACI/OT U1 with VDD on 5V, VBAT
to the JST PH socket CN2 (pin 1 GND, pin 2 VBAT) and C2 (10 µF), PROG with R3 (10 kΩ) to GND – 100 mA – and R4
(2.2 kΩ) through the solder jumper SJ1, open as the board is made: closed, R3 ∥ R4 = 1.80 kΩ programs 555 mA (the
schematic's own note: "10K = 100mA, 5.0K = 200mA, 2.0K = 500mA, 1.0K = 1000mA"); STAT with the red LED1 from 5V
through R1 (470 Ω), lit while the cell charges, and the green LED2 through R2 (470 Ω) to GND, lit once the charge is
complete; the breakout pads JP4 (1 5V, 2 D−, 3 D+, 4 GND, 5 VBAT). Left out: the four mounting holes (no pins).

**Stand-ins:** the schematic names only the charger, MCP73831T-2ACI/OT: its entry is the library's C424093, the LCSC
number Adafruit's own Micro-Lipo v2 schematic in the same repository gives it. The receptacle, CUI's
CUSB31-CFM2AX-01-X, is on neither LCSC nor JLCPCB: HRO's TYPE-C-31-M-13C (C2848620, the Corne's entry) stands in,
its paired GND and VBUS pins on the same nets. The resistors are UNI-ROYAL 0603WAF parts of the values (470 Ω C23179,
10 kΩ C25804, 2.2 kΩ C4190, 5.1 kΩ C23186); the 10 µF capacitors Samsung's CL21A106KAYNNNE (C15850, the library's,
X5R 25 V 0805); the LEDs NationStar's NCD0805R1 (C84256, red) and KENTO's KT-0805G (C2297, green); the JST PH
right-angle socket JST's S2B-PH-SM4-TB (C295747), typed battery_holder so that the simulation's cell sits on it; SJ1
an entry of its own – two pads of copper, a switch that is not bought (bom false); JP4 a 1 × 5 header XFCN
PZ254V-11-05P (C492404), not fitted – Adafruit ships bare pads. The simulation's supply is a USB 2.0 port (4.75 …
5.25 V, 0.3 Ω, 500 mA – the 5.1 kΩ Rd ask a USB-C source for Default USB Power) and its cell Adafruit's 500 mAh LiPo
(product 1578, PKCELL Li-Polymer 503035 with protection circuit: 3.0 V end of discharge, 4.2 V charge, 1C = 500 mA
the most it may be charged with) at 3.0, 3.7 and 4.2 V, its 0.2 Ω assumed; the loads are SJ1 open (100 mA), SJ1 closed
(the 500 mA mode, "for when you'll only be charging batteries with 500mAh size or larger" – the product page) and the
cell full. Each parts entry names its datasheet, what was read in it and what is open (`verified`).

**What edakit finds** – and how each finding is judged – is in `findings.toml`, held by `tests/test_open_designs.py`.
The design showed one false alarm of edakit and one charge current edakit did not see, both fixed and held by
`tests/test_open_design_fixes.py`: the status LEDs behind their resistors taken for a floating net, and R4 behind the
solder jumper, which neither LIM.i/charge nor the charger model counted. Three known gaps are closed and held there
too: JP4 and the receptacle handing a reversed cell on from pin to pin (TD-124), SJ1 asked for a supplier as if it
were a part (TD-127, `own.what` `copper`), and STAT, which the charger model did not drive (TD-133).
