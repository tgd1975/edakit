# ESPurna-H – a published design, transcribed for edakit's tests

**Source:** Xose Pérez (tinkerman.cat), *ESPurna-H*, an ESP8266 wall switch with an HLK-PM01 and a power monitor,
<https://github.com/xoseperez/espurna-board> at commit f433874 (f43387465bcd7fee6e2e6ac7c699a5177faa2fcc,
2018-04-16), the Eagle schematic `espurna-h/v0.8/espurna-h.sch` (title block "ESPURNA-H", version 0.8.20171028; the same file as
`espurna-h/espurna-h.sch`), read on 2026-11-03 from a read-only clone. The bill of materials is the repository's
README. The netlist was resolved from the schematic's XML by a reader outside this repository and checked against the
board file `espurna-h/v0.8/espurna-h.brd`: all 142 pads of the schematic's 39 nets are on the same signals there.

**Licence and attribution:** the repository's README licenses the hardware design files (schematics and CAD) under
the Creative Commons Attribution-ShareAlike 3.0 Unported License (<https://creativecommons.org/licenses/by-sa/3.0/>);
the title block of the v0.8 schematic says "License: CC-BY-SA 4.0"
(<https://creativecommons.org/licenses/by-sa/4.0/>). This transcription is an adaptation offered under CC BY-SA 4.0,
which both allow (CC BY-SA 3.0, section 4(b): a later version with the same licence elements). Attribution:
*ESPurna-H* by Xose Pérez (tinkerman.cat), <https://github.com/xoseperez/espurna-board>. Changes: the circuit's facts –
parts, values, connections – are transcribed into edakit's graph, not the drawing; the schematic's unnamed nets (N$…)
got names after their function (RLY_COIL, V2P_D1 …, the Eagle name in each net's notes); the net labels A0 and GPIO16,
each on one pin only, are left open pins; the parts stated below stand in; the parts entries are written from the
parts' datasheets; each net got a voltage range. This is a reading of the repository's licence statements, not legal
advice.

**Why this design:** the only board here with mains on it – an HLK-PM01 behind a thermal fuse, a 500 mA fuse and a
varistor, a 10 A relay that switches the load, and an HLW8012 power monitor on a 1 mΩ shunt and a 5 × 470 kΩ divider
from neutral, whose 0 Ω resistor ties the low-voltage ground to the line. No reference circuit (`tests/reference.py`
has none with mains or a relay) and no other open design brings LIM.hazardous and the domain mains onto a real board,
nor a relay coil driven from a 3.3 V GPIO with its flyback diode; around them sit the low-voltage checks edakit does
make – the 2N7002's gate drive, the regulator, the ESP8266's levels and boot pins. An HLK-PM01, an ESP module and a
relay is the common recipe of a homemade mains smart switch, and ESPurna is a widely used open firmware for such
switches, so a false alarm here would meet many.

**Transcribed:** the mains terminals JP42 (1 NO, 2 NC, 3 LINE_I – the line in) and JP2 (neutral, both pins); the
supply branch from LINE_I through the thermal fuse F1 and the 500 mA fuse F2 (5 × 20 mm holder) to the HLK-PM01 U$1,
the varistor V11 (S10K250) across its input; its 5 V output (5V) with C11 (10 µF tantalum) to the AMS1117-3.3 IC1
(VOUT on the tab, pad 2 on no net) and C12 (10 µF tantalum) on 3V3. The ESP-12F IC2 with C21 (100 nF), CH_PD pulled
up by R21, RESET by R26 with C22 (100 nF) and the button RESET, GPIO0 and GPIO2 pulled up (R23, R24), GPIO15 pulled
down (R25), all 10 kΩ; the programming header JP21 (GPIO0, TXD, RXD, GND, 5V) and the external header JP22 (GND, LED,
GPIO4 with R22 10 kΩ up, 3V3, GND) – the LED driven by Q2 from GPIO2 (R27 22 Ω at the gate, R28 300 Ω from 5V at
the drain). The relay RLY1 (SRD-05VDC-SL-C) with its coil from 5V to the 2N7002 Q3, D3 (1N4148) across the coil,
Q3's gate from GPIO12 through R31 (1 kΩ) with R32 (10 kΩ) to GND; its common on LINE_L, NO and NC to JP42. The HLW8012 IC4 on 5V (C43 100 nF, C44 1 µF); the shunt R41 (1 mΩ, 2512) from LINE_I to LINE_L, R43/R44
(1 kΩ) with C41/C42 (33 nF) to V1P/V1N; R42 (0 Ω, 1206) from LINE_L to GND; R51–R55 (5 × 470 kΩ) from neutral to V2P
with R50 (1 kΩ) and C45 (100 nF) to GND; SEL pulled up to 5V by R49 (10 kΩ) and pulled low by the 2N7002 Q4 from
GPIO5; CF1 and CF through R45/R47 (10 kΩ) to GPIO13/GPIO14 with R46/R48 (15 kΩ) to GND. The board is non-isolated:
R42 puts the whole low-voltage side at mains potential, which the ESPurna README warns about (never connect the
board's ground to a computer, never flash it on mains). The mains nets are declared at the peak of 230 V + 10 %
(358 V) against GND; the simulation runs the low-voltage side from the HLK-PM01's 5 V and leaves mains out. What this
README and `findings.toml` say about mains is support, not legal advice – nothing legally guaranteed, without any
claim to correctness.

**Stand-ins:** the schematic names part numbers for the ESP-12, the HLK-PM01, the HLW8012, the SRD-05VDC-SL-C, the
AMS1117-3.3, the 2N7002, the 1N4148 (SOD80) and the S10K250; their LCSC parts are used – Ai-Thinker's ESP-12F
C82891, Hi-Link's HLK-PM01 C209903, Hiliwei's HLW8012 C83804, Songle's C35449, C6186 of edakit's library, CJ's
2N7002 C8545, Vishay's LL4148 C68883 (the 1N4148 in MiniMELF) and TDK's B72210S0251K101 C210499 (SIOV-S10K250). Q2
is drawn as an NPN without a part number, while the README's bill of materials lists the 2N7002 for Q2, Q3 and Q4:
CJ's 2N7002 sits in the NPN's SOT-23 pads – gate on the base's pad 1, source on the emitter's, drain on the
collector's –, a source follower. The bill of materials names an SF70E thermal fuse (73 °C), which LCSC does not
sell: Walter's TG113 (C435442, 113 °C, 15 A 250 V AC) stands in; its "500mA 250V fuse" is Littelfuse's fast-acting
0217.500MXP (C142795), the holder no entry; its "10uF 0805 tantalum" is Vishay's TMCP1A106MTRF (C1969735, 10 V),
plus at the supply – the schematic's symbol has no polarity. The resistors are UNI-ROYAL 0805W8F/1206W4F parts of
the values given, the shunt Vishay's WSL25121L000FEA18, the ceramics YAGEO and Samsung 0805 parts (the 100 nF and
1 µF of edakit's library), the screw terminals Kefa's KF301-5.0, the headers XFCN's PZ254V-11-05P, the button XKB's
TS-1187A of the library. The mains nets are AC nets (net `ac`), the terminals, the module's input and the varistor V11
(kind varistor) rated in V AC (`v_rms_max_v`). Each parts entry names its datasheet, what was read in it and what is open (`verified`).

**What edakit finds** – and how each finding is judged – is in `findings.toml`, held by `tests/test_open_designs.py`.
The design showed one false alarm of edakit, fixed and held by `tests/test_open_design_fixes.py` – a need on the
regulator's VOUT pin left open while its tab carries the output –, and the mains side edakit could not read: AC
ratings held against the peak as DC, the divider's taps judged against GND, no varistor kind, no mains supply input,
and GND tied to the line unseen (TD-128 to TD-131), each closed and held there too.
