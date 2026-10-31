# GuitarML Tubescreamer/Rat combo – a published guitar pedal, transcribed for edakit's tests

**Source:** Keith Bloemer (GuitarML), *GuitarPedalPCBs*, <https://github.com/GuitarML/GuitarPedalPCBs> at commit e2fa7e1
(e2fa7e1e22f4939215cfbb1d5a3df2a66068275e, 2026-08-05, "Update README.md"), the pedal *TS_Rat_Combo_1590bb* ("Custom
Tubescreamer/Rat Combo with order switch", the repository's README; the board's silkscreen "Distortion Drive v1.0
9/3/2025 GuitarML"), the schematic `TS_Rat_Combo_1590bb/jack_pedal.kicad_sch` (KiCad 9), read on 2026-10-31 from a
read-only clone (the files' git blob hashes are those of the commit). The netlist was resolved from the schematic
(wires, labels, power symbols, the instances of project jack_pedal) by a reader outside this repository and checked
against the board file `TS_Rat_Combo_1590bb/jack_pedal.kicad_pcb` of the same commit, the footprints matched to the
symbols by their uuid: all 182 pins of the sheet are on the same nets there (the board's references of the wire pads
drop the schematic's numbers – In1 is In, InG3 is OutG, InG5 is InG, both swGnd pads are swGnd).

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

Attribution: *TS_Rat_Combo_1590bb* by Keith Bloemer (GuitarML), <https://github.com/GuitarML/GuitarPedalPCBs>.
Changes: the circuit's facts – parts, values, connections – are transcribed into edakit's graph, not the drawing; the
nets got names (VREF, TS_INN, RAT_CLIP, …); the parts wired to the pads by hand are added as a board of their own, as
stated below; the parts the schematic does not name stand in as stated below; the parts entries are written from
datasheets. This is a reading of the repository's files, not legal advice.

**Transcribed:** the board as drawn – the 9 V pad through the 1N5817 D2 to VCC with C12 (47 µF) and C3 (100 nF);
VREF from R7/R8 (10 kΩ / 10 kΩ) with C4 (47 µF); the TS: R9 (2.2 MΩ) at ts_in, C5 and R28 into the 2SC1815 emitter
follower Q1 (R10 510 kΩ from VREF, R16 10 kΩ), C13 into the gain stage U1A of the TL072 (R17 10 kΩ to VREF; R18
51 kΩ and the drive pot POT4 A500K with C14 51 pF and the anti-parallel 1N914 D8/D9 in the feedback; R29 4.7 kΩ and
C22 47 nF to VREF), the tone stage U1B (R19 1 kΩ, C15 220 nF, the tone pot POT5 W20K with C16 220 nF and R21 220 Ω,
R22 1 kΩ, R20 10 kΩ to VREF), C17, R23 and the level pot POT6 B100K on VREF, C18 into the 2SC1815 follower Q2 (R24
510 kΩ from VREF, R25 10 kΩ), R26 100 Ω and C19 10 µF to ts_out with R27 10 kΩ; the Rat: R1 (1 MΩ) at Rat_in, C1
22 nF, R2 1 MΩ to VREF, R3 1 kΩ and C2 1 nF into the LM301A U2 (C9 30 pF from pin 8 to pin 1; the distortion pot
POT1 A100K with C6 100 pF in the feedback; R4 47 Ω with C7 2.2 µF and R5 560 Ω with C8 4.7 µF to ground), C10
4.7 µF and R11 1 kΩ to the 1N914 D1/D3 to ground, the filter pot POT2 A100K with R12 1.5 kΩ and C11 3.3 nF, C20 22 nF
into the 2N5458 source follower JN1 (R13 1 MΩ, R14 10 kΩ), C21 1 µF to the volume pot POT3 A100K; the order switch S1,
a 3PDT FS57003PLT2B2M2QE on the board (throw a – lugs 1, 4, 7 – sends the input into the TS and the TS into the Rat,
throw b the other way round); R6 and R15 (4.7 kΩ) from the 9 V pad to the LED pads SW_TS and SW_RAT; the 18 wire pads
(TestPoint_THTPad, board 'main'). U2's pin 5 is open as drawn.

**Wired by hand (board 'wiring'):** the design shows only pads – the repository's README points to PedalPCB's build
documentation for the wiring (docs.pedalpcb.com, not reachable from here). Transcribed as the pads' names say, each
wire a cable from its pad: the DC jack J1 (9v1 to the barrel, InG1 to the centre pin: centre negative, the parts
list of the Classic Boost), the input jack J2 (In, InG) and the output jack J3 (Out, OutG), the TS footswitch SW2
and the Rat footswitch SW3 – each a 3PDT, pole 1 from send to in (on) or to the bypass link, pole 2 from return to
out (on) or to the link, pole 3 the LED's cathode to the swGnd pad (on) – and the LEDs D10, D11 from the SW_TS and
SW_RAT pads. The board is `wired = true`, hand-wired (rules-at-scale.md, decision 22).

**Stand-ins:** the schematic names types, not makers. TL072: TI TL072CP (C7236), LM301: TI LM301AN (C22505, its data
sheet the LM301A-N's SNOSBS0D – TI has no other), 1N914: onsemi 1N914 (C96325), 2SC1815: JSCJ's 2SC1815 of rank GR
(C23895; Toshiba's own data sheet was not reachable), 2N5458: onsemi 2N5458 (named by its MPN – no LCSC number of
onsemi's), 1N5817: onsemi 1N5817RLG (C232461); the resistors Uniroyal MFR 1/4 W (2.2 MΩ: Huaxing RI40), the film
capacitors KEMET R82, the picofarads KEMET Goldmax C0G, the electrolytics KEMET ESK (the footprints CP_Radial for C4,
C7, C8, C10, C12, C19: pad 1 the plus), the pots TT Electronics P160 (W20K: B20K – P160 has no W taper; the
simulation splits a pot linearly anyway), the footswitches the board's own FS57003PLT2B2M2QE, the jacks Neutrik
NMJ6HCD2 used mono, the DC jack edakit's PJ-102AH, the LEDs a red 5 mm TOGIALED. The 5 mm LEDs and the jacks are what
the Classic Boost's parts list names in words. Pin numbers are those of the KiCad symbols but for the 2N5458, whose
custom symbol numbers 1 G, 2 S, 3 D: here 1 D, 2 S, 3 G as onsemi's TO-92 style 5. Its footprint (2N5458:TO92)
numbers the pads the other way round than KiCad's TO-92_Inline beside it (pad 1 on the right of the flat side), so
the gate network meets lead 3, the gate, as long as onsemi's lead 1 sits on the left seen on the flat side – as KiCad's
footprint places it for the 2SC1815; edakit cannot see this (no layout), the board file was read for it. The
KiCad symbol of the LM301 names pin 1 BAL, 5 COMP, 8 C/B; TI's data sheet 1 BALANCE/COMPENSATION, 5 BALANCE, 8
COMPENSATION – C9 from 8 to 1 is the data sheet's 30 pF compensation.

**Voltages:** 9 V from a pedal supply at the DC jack (1 Ω source resistance assumed), VCC 8.73 V behind the
Schottky, VREF 4.35 V. No battery: the design has no battery pads and the enclosure (1590BB) is not said to hold one,
so no low-battery scenario. The AC runs drive the TS and the Rat each from its pad with a pickup in front – R and L
in series, C across: 6 kΩ, 2.5 H, 200 pF, the test's values, not a product's (FT-18 brings the makers' figures); they
are information (`info`): no source states the response the design intends, the bounds are the test's from the
schematic's values. Each parts entry names its datasheet, what was read in it and what is open (`verified`).

**What edakit finds** – and how each finding is judged – is in `findings.toml`, held by `tests/test_open_designs.py`.
Real: C19 is reverse-biased by 3 V (its plus at ts_out, 0 V; its minus at Q2's emitter); the LM301A runs below the
supply range its data sheet specifies. The design showed edakit four false alarms or blind spots and one thing it
could not describe – a base biased by resistors taken as floating, a coupling capacitor's voltage from extreme to
extreme, several wires of one net stopping the simulation, the contacts on nets through cables never judged, a switch
of three poles –, all fixed and held by `tests/test_open_design_fixes.py`. Outside these tests (no layout): the board
drills 0.8 mm for D2, the 1N5817's DO-41 leads are up to 0.86 mm (its entry's `lead`).
