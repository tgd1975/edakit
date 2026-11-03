# Random Input (whbeers) – a published Fuzz Face, transcribed for edakit's tests

**Source:** whbeers, *Random Input Fuzz Effect (Based on Fuzz Face)*, <https://github.com/whbeers/random_input> at
commit 723a89d (723a89dc1e80f91f0c3cb20f7c51139a3609353c, 2023-03-27), the schematic `hardware/random_input.kicad_sch`
(KiCad 7, rev v0.27, 2023-03-04), read on 2026-11-03 from a read-only clone. The repository's README calls it "a
re-creation of the original Dallas Arbiter Fuzz Face effect circuit" that "emphasizes the ability to easily fine-tune
the bias of each transistor … Besides this emphasis, it remains true to the original"; by its versioning a v0.XX design
has been "produced, tested". The netlist was resolved from the schematic (wires, labels, power symbols) by a reader
outside this repository and checked against the board file `hardware/random_input.kicad_pcb` of the same commit: all
39 pins of the 17 parts are on the same 12 nets there. The board is the effect board of the author's *Noise Floor*
platform, <https://github.com/whbeers/noise_floor> at commit d0fd4e7 (d0fd4e7e6e0613f3478bcc411c881ca6a524d33f,
2023-03-30, schematic `hardware/noise_floor.kicad_sch` rev v0.32), whose IO board feeds it at its connector E1; its
schematic and board file were read for the supply only.

**Licence and attribution:** both repositories hold one licence file, `LICENSE`, the Creative Commons legal code "CC0
1.0 Universal" (<https://creativecommons.org/publicdomain/zero/1.0/>): the author waives copyright and related rights
in the work, to the extent the law allows, for any purpose, commercial ones included; CC0 asks for no attribution and
no notice. Given anyway: *Random Input* and *Noise Floor* by whbeers, <https://github.com/whbeers/random_input>,
<https://github.com/whbeers/noise_floor>. Changes: the circuit's facts – parts, values, connections – are transcribed
into edakit's graph, not the drawing; two nets the schematic leaves unnamed got names (C2_IN, OUT_TAP); the parts the
schematic does not name stand in as stated below; the parts entries are written from datasheets; the 3D models the
repositories credit to others are not used. This is a reading of the repositories' files, not legal advice.

**Why this design:** the Fuzz Face is the two-transistor circuit whose bias makers fight with: Q1's collector drives
Q2's base directly and Q2's emitter feeds back to Q1's base through 100 kΩ, so the operating point rests on both
transistors' gain and leakage – and they pull it in opposite directions, the case of the spread's corners per part
(FT-17, handbook 5.2). No reference circuit has a direct-coupled pair, and the open designs' stages are a divider-held
common emitter (the Classic Boost) and followers (the combo). This one names its bias targets on the schematic – TP2,
Q2's collector, at 5.0 V, TP1 at 500–700 mV – and replaces the collector resistors with trimmers to reach them, so the
simulation can hold the bias to the design's own window, show how far the spread moves it at one setting, and show the
trimmers' range covering it. It is also a board without an IC, fed through a connector from another board, and its fuzz
control carries DC. Makers build the Fuzz Face as one of the first fuzzes: a dozen parts, a sound tied to the
transistors, and the reputation for picky bias.

**Transcribed:** the effect board as drawn – the connector J1 (E1, a Molex PicoBlade 53047-0410: 1 EFFECT_OUT, 2 9V0,
3 GND, 4 EFFECT_IN); the input volume POT1 (A100K) with its end and wiper on EFFECT_IN, a variable resistor in series,
into C2 (2u2, polarized, plus at Q1's base); Q1 and Q2 ("NPN Ge", Device:Q_NPN_EBC, 1 E, 2 B, 3 C, footprint TO-5-3),
Q1's emitter on ground, its collector on Q2's base (TP1, Q1C) and through TRIM1 (100K, "Q1 Bias", wiper and end joined)
to 9V0; R3 (100K) from Q2's emitter back to Q1's base; Q2's emitter to ground through the fuzz pot POT2 (B1K), its
wiper through C3 (22u, plus at the wiper) to ground; Q2's collector (TP2, Q2C) through TRIM2 (50K, "Q2 Bias", wiper and
end joined) to the output tap and through R2 (470R) on to 9V0; C4 (10n) from the tap to the volume POT3 (A250K), its
wiper on EFFECT_OUT; the ground test points TP3 and TP4. The schematic's notes: "Designed for medium gain NPN Germanium
transistors Example: 2N1306 … For PNP transistors, provide -9V and swap polarity of electrolytic caps", and the bias
procedure – "Start without input signal with circuit powered. Q1: Adjust TRIM1 while probing TP1 DC voltage (target of
500-700mV to get in the ballpark) Q2: Adjust TRIM2 while probing TP2 DC voltage (target of 5.0 V)", then fine tuning
with a sine on a scope. Those targets are the expectations of the load `trimmed` (sim.json), TP2's with ±0.5 V, the
test's tolerance.

**Not transcribed:** the Noise Floor's IO and switch boards (DC jack, battery clip, input and output jacks, the 3PDT
footswitch with its LED), a design of their own. The IO board switches the supply's minus through the input jack: its
sleeve contacts carry the battery's and the DC jack's minus, its ring contact ground, and only a mono plug's sleeve
joins them – a plug in a jack is nothing edakit's graph can describe, so the simulation would find the board unpowered.
What the IO board gives the effect board is the source in sim.json: 9V0 from a 9 V supply or battery through its
B5817WS (D1) and 47 Ω (R5), with 100 µF and 100 nF – 8.8 V behind 47 Ω (the Schottky's drop assumed). E1's pins are
mirrored between the boards (IO side: 1 input, 2 GND, 3 9V0, 4 output), so the cable between them crosses them, pin n
to pin 5 − n; without the IO board edakit cannot see that.

**Stand-ins:** Q1 and Q2: the schematic names no transistor – "NPN Ge", "Example: 2N1306" –, the repository's README
"a variety of NPN transistors (germanium or silicon)". No germanium data sheet could be read from here (Central
Semiconductor's 2N1302-series sheet and NTE's NTE101 were refused by the network; maker-coverage GTP 1), so the silicon
2N3904 (onsemi 2N3904BU, C124482, edakit's library entry) stands in, its `hfe_min` taken at 0.1 mA (40), where these
stages run, instead of the library's 70 at 1 mA. With silicon, TP1 cannot reach the germanium window (findings.toml).
The resistors Uniroyal MFR 1/4 W; C4 a KEMET R82; C2 and C3 KEMET ESK (D5 mm – the board has 4 mm footprints, a matter
of the layout); the trimmers Bourns 3296W (the footprint's, the order codes 3296W-1-104LF, C48084, and 3296W-1-503LF,
C83686); the pots TT Electronics P160 with PC pins (P160KN-0QC15A100K and P160KN-0QC15A250K built by the data sheet's
scheme, no LCSC number; P160KN-0QC15B1K, C6249449) – the board's own footprint for its 16 mm pots names no part (its
3D model is an Alpha RV16AF); J1 Molex 530470410 (C504989), as the footprint names it; the test points pads of the
board.

**Voltages:** 8.8 V at E1 behind 47 Ω, about 0.8–1.1 mA drawn. With the trimmers set for the typical 2N3904 (TRIM1 at
half, TRIM2 at 5.05 kΩ), Q2's collector sits at 5.0 V, Q1's at 1.34 V; a pair at the low end of hFE puts Q2's
collector at 3.8 V, at the high end at 5.1 V (the leakage of the corner max, 50 nA at 25 °C, adds 27 mV; at 60 °C
0.2 V), Q1 low with Q2 high at 3.4 V, Q1 high with Q2 low at 5.2 V. Retrimmed, each pair reaches 5.0 V with TRIM2
between 3.4 and 5.4 kΩ, a tenth of its 50 kΩ (the loads `retrimmed_…` hold TP2's window). Each parts entry names its
datasheet, what was read in it and what is open (`verified`).

**What edakit finds** – and how each finding is judged – is in `findings.toml`, held by `tests/test_open_designs.py`.
Real: the bias leaves its window when the pair changes and the trimmers stay (the trimmers are the design's answer),
and the fuzz control carries Q2's emitter current. The silicon stand-in cannot reach TP1's germanium window (lacks).
The design showed two false alarms, fixed and held by `tests/test_open_design_fixes.py`: Q2's base, held by TRIM1
from a supply that comes in at a connector, taken as floating, and the trimmer TRIM2 held to a panel pot's rule
(TD-126) – the trimmers' entries say `adjust: "trimmer"`.
