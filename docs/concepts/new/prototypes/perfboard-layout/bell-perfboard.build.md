# christmas-bell-tht on a perfboard – check, build list, test list

Written by `perfboard.py` from [bell-perfboard.toml](bell-perfboard.toml) and the graph of `tht`; the drawings are [top](bell-perfboard.top.svg) and [bottom](bell-perfboard.bottom.svg), both seen from above. A prototype – see the [README](README.md).

## Check

0 errors, 3 warnings and notes.

- **note** `PERF.grid` – S1: leads bent by 0.63 mm into the 2.54 mm grid (allowed 0.8 mm)
- **note** `PERF.grid` – S2: leads bent by 0.63 mm into the 2.54 mm grid (allowed 0.8 mm)
- **note** `PERF.inside` – GND: LED1.cathode in R2, LED2.cathode in O2, LED3.cathode in L2, LED4.cathode in I2, LED5.cathode in F2, U1.GND in M9 join the rest only inside the plugged-in module

## Build list – from low to high

1. **Resistors ¼ W, lying flat:** R1 330Ω: O8–O4; R2 330Ω: L8–L4; R3 330Ω: I8–I4; R4 330Ω: H8–H3; R5 330Ω: R8–R4; R6 4.7kΩ: X20–X16; R7 4.7kΩ: S20–S16.
2. **Resistors 1 W, 1–2 mm above the board:** R8 100Ω: N22–N16; R9 100Ω: Q22–Q16.
3. **Insulated wires on top – each end through its hole, bent onto the pad below:** black M4–M8 GND (26 mm); red M16–M22 +5V (31 mm); red AC22–AE17 +5V (31 mm); yellow K10–P8 LED_Y2 (39 mm); white J10–S8 LED_R (49 mm); blue F10–AG18 SERVO (105 mm); orange C10–T19 BTN_START (82 mm); violet B10–Y19 BTN_RESET (97 mm).
4. **Sockets:** two 1×15 female headers for U1: B9–P9 and B15–P15.
5. **Buttons:** S1 (start button): 1 in W22, 2 in T22, 3 in W20, 4 in T20; S2 (reset button): 1 in AB22, 2 in Y22, 3 in AB20, 4 in Y20.
6. **Pin header:** J1: pin 1 (GND, brown) in AF16, pin 3 (signal) in AF18.
7. **LEDs:** LED1 red: anode (long lead) in R3, cathode (flat) in R2; LED2 yellow: anode (long lead) in O3, cathode (flat) in O2; LED3 yellow: anode (long lead) in L3, cathode (flat) in L2; LED4 green: anode (long lead) in I3, cathode (flat) in I2; LED5 green: anode (long lead) in F3, cathode (flat) in F2.
8. **Electrolytic capacitor:** C1 1000uF 16V: plus in AC17, minus (stripe) in AC15.
9. **Solder bridges on the bottom, once the leads are in – 76 in all:** F2 … R2 GND (12); M2 … M4 GND (2); M8–M9 GND; O15–O16 GND; N16 … AF16 GND (18); AC15–AC16 GND; M15–M16 +5V; M22 … AC22 +5V (16); AC17 … AF17 +5V (3); F3 … H3 LED_G1_A (2); I3–I4 LED_G2_A; L3–L4 LED_Y1_A; O3–O4 LED_Y2_A; R3–R4 LED_R_A; H8–H9 LED_G1; I8–I9 LED_G2; L8–L9 LED_Y1; K9–K10 LED_Y2; P8–O8 LED_Y2; J9–J10 LED_R; S8–R8 LED_R; F9–F10 SERVO; AG18–AF18 SERVO; C9–C10 BTN_START; T19–T20 BTN_START; S20–T20 BTN_START; B9–B10 BTN_RESET; Y19–Y20 BTN_RESET; X20–Y20 BTN_RESET.
10. **Test:** the test list below, before U1 is plugged in.
11. **Module:** plug U1 into its sockets, USB socket at the left edge.

## Test list – multimeter in beep mode, U1 not plugged in

1. **Before the first power-up:** +5V (AF17) to GND (AF16) reads about 50 Ω (R8 ∥ R9) once C1 has charged – 0 Ω is a short.
2. **Each net beeps** from its first hole to every other:

| Net | From | To |
| --- | --- | --- |
| +5V | M15 (U1.5V) | AC17 (C1.plus), AF17 (J1.2), N22 (R8.1), Q22 (R9.1), T22 (S1.2), W22 (S1.1), Y22 (S2.2), AB22 (S2.1) |
| GND (1) | O15 (U1.GND) | AC15 (C1.minus), N16 (R8.2), Q16 (R9.2), S16 (R7.2), X16 (R6.2), AF16 (J1.1) |
| GND (2) | F2 (LED5.cathode) | I2 (LED4.cathode), L2 (LED3.cathode), O2 (LED2.cathode), R2 (LED1.cathode), M9 (U1.GND) |
| | | GND (1) and (2) are joined inside U1: they beep once it is plugged in |
| SERVO | F9 (U1.PB0) | AF18 (J1.3) |
| BTN_START | C9 (U1.PB4) | S20 (R7.1), T20 (S1.4), W20 (S1.3) |
| BTN_RESET | B9 (U1.PB3) | X20 (R6.1), Y20 (S2.4), AB20 (S2.3) |
| LED_G1 | H8 (R4.1) | H9 (U1.PD6) |
| LED_G1_A | F3 (LED5.anode) | H3 (R4.2) |
| LED_G2 | I8 (R3.1) | I9 (U1.PD5) |
| LED_G2_A | I3 (LED4.anode) | I4 (R3.2) |
| LED_Y1 | L8 (R2.1) | L9 (U1.PD2) |
| LED_Y1_A | L3 (LED3.anode) | L4 (R2.2) |
| LED_Y2 | O8 (R1.1) | K9 (U1.PD3) |
| LED_Y2_A | O3 (LED2.anode) | O4 (R1.2) |
| LED_R | R8 (R5.1) | J9 (U1.PD4) |
| LED_R_A | R3 (LED1.anode) | R4 (R5.2) |

3. **Next to each bridge nothing else beeps** – the neighbouring pads of other nets:

<details><summary>27 pairs of neighbouring holes</summary>

| Nets | Holes |
| --- | --- |
| +5V / GND | AC16–AC17, AD16–AD17, AE16–AE17, AF16–AF17, M16–N16 |
| +5V / SERVO | AF17–AF18 |
| BTN_RESET / BTN_START | B10–C10, B9–C9, W20–X20 |
| GND / LED_G1_A | F2–F3, G2–G3, H2–H3 |
| GND / LED_G2_A | I2–I3 |
| GND / LED_R_A | R2–R3 |
| GND / LED_Y1 | L8–M8, L9–M9 |
| GND / LED_Y1_A | L2–L3, L3–M3, L4–M4 |
| GND / LED_Y2_A | O2–O3 |
| LED_G1 / LED_G2 | H8–I8, H9–I9 |
| LED_G1_A / LED_G2_A | H3–I3 |
| LED_G2 / LED_R | I9–J9 |
| LED_R / LED_Y2 | J10–K10, J9–K9 |
| LED_Y1 / LED_Y2 | K9–L9 |

</details>

## Material

- Perfboard, a pad per hole: 33 × 22 holes (83.8 × 55.9 mm), cut from a Euro board 160 × 100 mm; four holes drilled to 3.2 mm.
- Insulated wire, solid core, in the plan's colours: 46 cm; solder for 76 bridges.
- Two female headers 1×15 for U1 – already an `[[extra]]` of the bell's tht variant.
