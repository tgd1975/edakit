# GuitarML Classic Boost v2 – a published guitar pedal, transcribed for edakit's tests

**Source:** Keith Bloemer (GuitarML), *GuitarPedalPCBs*, <https://github.com/GuitarML/GuitarPedalPCBs> at commit e2fa7e1
(e2fa7e1e22f4939215cfbb1d5a3df2a66068275e, 2026-08-05), the pedal *ClassicBoost_1590a* ("A simple boost circuit
(compare to LPB-1 by Electro-Harmonix)", its README with the parts list), the schematic
`ClassicBoost_1590a/ClassicBoost_v2.kicad_sch`, read on 2026-10-31 from a read-only clone. The netlist was resolved
from the schematic (the instances of project LPB1_Boost) by a reader outside this repository and checked against the
board file `ClassicBoost_1590a/ClassicBoost_v2.kicad_pcb` of the same commit: all 32 pins of the sheet are on the same
nets there.

**Licence and attribution:** the repository's root holds one licence file, `LICENSE`, the MIT licence, "Copyright (c)
2023 Keith Bloemer". The MIT licence asks that its notice travel with copies and substantial portions:

> MIT License – Copyright (c) 2023 Keith Bloemer. Permission is hereby granted, free of charge, to any person obtaining
> a copy of this software and associated documentation files (the "Software"), to deal in the Software without
> restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
> and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the
> following conditions: The above copyright notice and this permission notice shall be included in all copies or
> substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
> NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
> SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Attribution: *ClassicBoost_1590a* by Keith Bloemer (GuitarML), <https://github.com/GuitarML/GuitarPedalPCBs>.
Changes: the circuit's facts – parts, values, connections – are transcribed into edakit's graph, not the drawing; the
nets got names (BASE, COL, …); the parts wired to the pads by hand are added as a board of their own; the parts the
schematic does not name stand in as stated below; the parts entries are written from datasheets. This is a reading
of the repository's files, not legal advice.

**Why both pedals:** the combo's transistors are followers – their bias hardly depends on the gain. The boost is the
one stage whose operating point the transistor's spread moves: a common-emitter stage, its base held by a divider,
its gain set by the collector and emitter resistors – the case of FT-17's corners and of a gain an AC run can show. It
also has no IC at all: nothing types its supply and ground, which is what showed the first false alarm below.

**Transcribed:** the board as drawn – the 9 V pad through the 1N5817 D1 to VCC (the pad SW); the input pad In through
C1 (100 nF) to the base of Q2, a 2N5088 (the schematic's value; its symbol is the 2N3904's, 1 E, 2 B, 3 C), with R1
(430 kΩ) from VCC and R2 (43 kΩ) to ground, R3 (10 kΩ) from the collector to VCC, R4 (390 Ω) from the emitter to
ground; C2 (100 nF) from the collector to the volume pot POT1 (100K, the parts list's A100K), its wiper at the output
pad O; LED1 on a two-pin header of the board, from ground through R5 (4.7 kΩ) to the pad SwG; the wire pads 9v, Gnd,
In, InG, O, OG, SW, SwG (references 9v1, Gnd1, In1, InG1, Out1, OutG1, SW1, swGnd1).

**Wired by hand (board 'wiring'):** the README's wiring labels – InG input jack ground, In input jack signal, SW
switch connection to the footswitch, SwG "ground connection to footswitch", O output, OG output ground, Gnd power jack
ground, 9v positive 9 V – and its reference to PedalPCB's build documentation (not reachable from here). Transcribed,
each wire a cable from its pad: the DC jack J1 (centre negative, as the parts list says), the input jack J2 and the
output jack J3, and the 3PDT footswitch SW2 – pole 1 from the input jack to In (on) or to the bypass link, pole 2
from the output jack to O (on) or to the link, pole 3 from SW (VCC) to SwG (on: the LED lights through R5). The pad
SwG is no ground: the board ties it to R5, the LED's resistor, and SW to VCC – the footswitch closes the two. The
board is `bought = true` until edakit has a key for a hand-wired board (rules-at-scale.md, decision 22).

**Stand-ins:** 2N5088: onsemi 2N5088BU (C3201780); 1N5817: onsemi 1N5817RLG (C232461); the resistors Uniroyal MFR
1/4 W (430 kΩ: Huaxing RI40 – the MFR has none); the capacitors KEMET R82; the pot TT Electronics P160 (A100K); the
LED a red 5 mm TOGIALED ("5mm LED (color of choice)"); the footswitch E-Switch's FS57003PLT2B2M2QE (the combo's;
the parts list says "3DPDT footswitch"), the jacks Neutrik NMJ6HCD2 used mono ("1/4" Mono Audio Jack"), the DC jack
edakit's PJ-102AH ("9 volt power jack (center negative)"). Device:LED's pins (1 K, 2 A) are the entry's 2 and 1.

**Voltages:** 9 V from a pedal supply at the DC jack (1 Ω source resistance assumed), VCC 8.78 V behind the
Schottky. No battery ("No space for battery in 1590a enclosure", the README), so no low-battery scenario. The AC run
drives the input pad with a pickup in front – 6 kΩ, 2.5 H, 200 pF, the test's values, not a product's (FT-18 brings
the makers' figures) – and reads the collector; it is information (`info`): no source states the gain the design
intends, the bounds are the test's from R3/R4. Each parts entry names its datasheet, what was read in it and what is
open (`verified`).

**What edakit finds** – and how each finding is judged – is in `findings.toml`, held by `tests/test_open_designs.py`:
nothing real. The simulation puts the stage at 0.36 mA, the collector at 5.2 V (5.0 V and 5.6 V at the ends of the
2N5088's hFE, 900 and 300), and the gain at 1 kHz at 24 dB into the collector. The design showed one false alarm –
the base held by its divider taken as floating –, fixed and held by `tests/test_open_design_fixes.py`. Outside these
tests (no layout): the board drills 0.8 mm for D1, the 1N5817's DO-41 leads are up to 0.86 mm (its entry's `lead`).
