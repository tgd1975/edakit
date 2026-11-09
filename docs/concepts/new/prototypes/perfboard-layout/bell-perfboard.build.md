# christmas-bell-tht on a perfboard – check, build list, test list

Written by `perfboard.py` from [bell-perfboard.toml](bell-perfboard.toml) and the graph of `tht`; the drawings are [top](bell-perfboard.top.svg) and [bottom, mirrored](bell-perfboard.bottom.svg). A prototype – see the [README](README.md).

## Check

0 errors, 3 warnings and notes.

- **note** `PERF.grid` – S1: leads bent by 0.63 mm into the 2.54 mm grid (allowed 0.8 mm)
- **note** `PERF.grid` – S2: leads bent by 0.63 mm into the 2.54 mm grid (allowed 0.8 mm)
- **note** `PERF.inside` – GND: U1.GND in O15 joins the net only inside the plugged-in module

## Build list – from low to high

1. **Solder bridges (bottom):** AC13–AD13 GND; M15–M16 +5V; F3–F4 LED_G1_A; I3–I4 LED_G2_A; L3–L4 LED_Y1_A; O3–O4 LED_Y2_A; R3–R4 LED_R_A; I8–I9 LED_G2; L8–L9 LED_Y1; C9–C10 BTN_START; P18–Q18 BTN_START; T18–U18 BTN_START; B9–B10 BTN_RESET; V18–W18 BTN_RESET; Z18–AA18 BTN_RESET.
2. **Bare wires (bottom, tinned copper 0.6 mm):** F2 → AD2 → AD22 → H22 GND (172 mm); M2 → M9 GND (22 mm); AB9 → AD9 GND (9 mm); H16 → AB16 → AB11 +5V (68 mm); F8 → H8 → H9 LED_G1 (12 mm); K9 → K10 → Q10 → Q8 → O8 LED_Y2 (32 mm); J9 → J11 → R11 → R8 LED_R (37 mm); F9 → F12 → AA12 → AA13 SERVO (68 mm).
3. **Resistors ¼ W, lying flat:** R1 330Ω: O8–O4; R2 330Ω: L8–L4; R3 330Ω: I8–I4; R4 330Ω: F8–F4; R5 330Ω: R8–R4; R6 4.7kΩ: AA18–AA22; R7 4.7kΩ: U18–U22.
4. **Resistors 1 W, 1–2 mm above the board:** R8 100Ω: H16–H22; R9 100Ω: K16–K22.
5. **Sockets:** two 1×15 female headers for U1: B9–P9 and B15–P15.
6. **Buttons:** S1 (start button): 1 in Q16, 2 in T16, 3 in Q18, 4 in T18; S2 (reset button): 1 in W16, 2 in Z16, 3 in W18, 4 in Z18.
7. **Pin header:** J1: pin 1 (GND, brown) in AC13, pin 3 (signal) in AA13.
8. **LEDs:** LED1 red: anode (long lead) in R3, cathode (flat) in R2; LED2 yellow: anode (long lead) in O3, cathode (flat) in O2; LED3 yellow: anode (long lead) in L3, cathode (flat) in L2; LED4 green: anode (long lead) in I3, cathode (flat) in I2; LED5 green: anode (long lead) in F3, cathode (flat) in F2.
9. **Electrolytic capacitor:** C1 1000uF 16V: plus in AB11, minus (stripe) in AB9.
10. **Insulated wires (top):** orange C10 → P18 BTN_START (73 mm, along C13 Q13 Q15 P16); violet B10 → V18 BTN_RESET (87 mm, along B14 R14 R15 V15).
11. **Module:** plug U1 into its sockets, USB socket at the left edge.

## Test list – multimeter in beep mode, U1 not plugged in

1. **Before the first power-up:** +5V (AB13) to GND (AC13) reads about 50 Ω (R8 ∥ R9) once C1 has charged – 0 Ω is a short.
2. **Each net beeps** from its first hole to every other:

| Net | From | To |
| --- | --- | --- |
| +5V | AB11 (C1.plus) | AB13 (J1.2), M15 (U1.5V), H16 (R8.1), K16 (R9.1), Q16 (S1.1), T16 (S1.2), W16 (S2.1), Z16 (S2.2) |
| GND | F2 (LED5.cathode) | I2 (LED4.cathode), L2 (LED3.cathode), O2 (LED2.cathode), R2 (LED1.cathode), M9 (U1.GND), AB9 (C1.minus), AC13 (J1.1), H22 (R8.2), K22 (R9.2), U22 (R7.2), AA22 (R6.2); not yet O15 (U1.GND) – joined inside the module |
| SERVO | F9 (U1.PB0) | AA13 (J1.3) |
| BTN_START | C9 (U1.PB4) | Q18 (S1.3), T18 (S1.4), U18 (R7.1) |
| BTN_RESET | B9 (U1.PB3) | W18 (S2.3), Z18 (S2.4), AA18 (R6.1) |
| LED_G1 | F8 (R4.1) | H9 (U1.PD6) |
| LED_G1_A | F3 (LED5.anode) | F4 (R4.2) |
| LED_G2 | I8 (R3.1) | I9 (U1.PD5) |
| LED_G2_A | I3 (LED4.anode) | I4 (R3.2) |
| LED_Y1 | L8 (R2.1) | L9 (U1.PD2) |
| LED_Y1_A | L3 (LED3.anode) | L4 (R2.2) |
| LED_Y2 | O8 (R1.1) | K9 (U1.PD3) |
| LED_Y2_A | O3 (LED2.anode) | O4 (R1.2) |
| LED_R | R8 (R5.1) | J9 (U1.PD4) |
| LED_R_A | R3 (LED1.anode) | R4 (R5.2) |

3. **Next to each bridge and bare wire nothing else beeps** – the neighbouring pads of other nets:

<details><summary>44 pairs of neighbouring holes</summary>

| Nets | Holes |
| --- | --- |
| +5V / GND | AB13–AC13, O15–O16 |
| +5V / SERVO | AA12–AB12, AA13–AB13 |
| BTN_RESET / BTN_START | B10–C10, B9–C9, U18–V18 |
| GND / LED_G1_A | F2–F3 |
| GND / LED_G2_A | I2–I3 |
| GND / LED_R_A | R2–R3 |
| GND / LED_Y1 | L8–M8, L9–M9 |
| GND / LED_Y1_A | L2–L3, L3–M3, L4–M4 |
| GND / LED_Y2 | M10–M9 |
| GND / LED_Y2_A | O2–O3 |
| LED_G1 / LED_G2 | H8–I8, H9–I9 |
| LED_G1 / SERVO | F8–F9 |
| LED_G2 / LED_R | I9–J9 |
| LED_R / LED_Y2 | J10–K10, J9–K9, K10–K11, L10–L11, M10–M11, N10–N11, O10–O11, P10–P11, Q10–Q11, Q10–R10, Q8–R8, Q9–R9 |
| LED_R / SERVO | J11–J12, K11–K12, L11–L12, M11–M12, N11–N12, O11–O12, P11–P12, Q11–Q12, R11–R12 |
| LED_Y1 / LED_Y2 | K9–L9, L10–L9 |

</details>

## Material

- Perfboard, a pad per hole: 33 × 22 holes (83.8 × 55.9 mm), cut from a Euro board 160 × 100 mm; four holes drilled to 3.2 mm.
- Bare tinned copper wire 0.6 mm: 42 cm; insulated wire (two colours): 16 cm.
- Two female headers 1×15 for U1 – already an `[[extra]]` of the bell's tht variant.
