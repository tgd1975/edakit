# Decisions

The perfboard variant of coin-cell-led. D-1 to D-7 of the example ([../../docs/decisions.md](../../docs/decisions.md))
hold here too; this log goes on from D-8.

## D-8 Through-hole parts (2026-11-10)

A perfboard takes only through-hole parts (handbook 7.9). Each part of the example gets its through-hole counterpart
at LCSC, chosen with the skill part-search; the circuit, its values and its nets stay as they are.

| | Example | Here | Why |
| --- | --- | --- | --- |
| BT1 | CR2032-BS-6-1 (C70377), SMD | KH-CR2032-2-1 (C5365915), Kinghelm | lies flat as the example's holder does; pins 20 mm apart, 8 holes with the leads bent by 0.16 mm. The upright holders CR2032-BS-5-1 (C70379) and XDBS-CR2032-5 (C48687404) were dropped: their pins are 3.7 mm apart across, which fits no 2.54 mm grid |
| SW1 | TS-1187A-B-A-B (C318884), SMD | K2-1102DP-C4SW-04 (C110153), 6 × 6 mm | the Christmas bell's THT button, its entry signed there |
| R1 | 150 Ω 0805 (C17471) | MFR0W4F1500A50 (C58668), 1/4 W axial | the same value; the series of the bell's resistors |
| D1 | NCD0805R1 (C84256), red 0805 | XL-504SURD (C2895493), red 5 mm | the bell's red LED, its entry signed there; Vf 1.8–2.4 V at 20 mA, so 150 Ω still gives 1.9 mA from a used cell (R-1) |

D1's reverse voltage of 5 V, which D-3 relies on, is the datasheet's test condition (IR ≤ 10 µA at VR = 5 V). The
holder fits both ways round: its + end, the one with the metal clip, goes on hole D10 – the drawing and the build list
mark it.

## D-9 The plan on 14 × 15 holes (2026-11-10)

A perfboard with a pad per hole, 14 × 15 holes (35.6 × 38.1 mm). The button at the top left, the LED beside it at the
top right with its resistor between them, the holder below. The two connections to the holder run as insulated wires
on top down the left and right edges; under the holder only bridges on the bottom. `edakit perfboard`: 0 errors.
