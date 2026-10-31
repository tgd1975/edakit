# Decisions

Numbered, with reason and date. The example of handbook chapter 18 – the walkthrough tells when each one came up.

## D-1 Set up for edakit (2026-10-31)

One board `main`, drawn in KiCad 10 (`toolchain = "kicad"`), the graph as TOML from the start. JLCPCB Economic
assembly of the SMD parts on the top side, the 2×AAA holder and the slide switch through-hole and soldered by hand
(`bom = false`), the holder on the bottom. 5 sets, edakit's defaults for the order, no budget. Built for oneself in the
EU (`purpose.use` "private"). No firmware, no documents that quote values, no scripts or agents of the project's own.
The requirements now, with the skill requirements. From the concept `docs/concepts/new/walkthrough-kicad-555.md`,
decisions 1, 2, 5 and 6.

## D-2 What it must do (2026-10-31)

N-1, N-2 and R-1 to R-4 accepted as drafted (`hardware/requirements.toml`), every number as proposed: the end voltage
1.0 V per alkaline AAA cell, 2.0 V for the pair – at 1.0 V a cell has given about 90 % of its capacity –; at least
1 mA through D1 while it is lit, as R-1 of chapter 17; 48 to 72 flashes a minute, ±20 % around once a second,
reachable with 1 % resistors, an X7R capacitor and the timing error of a CMOS 555; at most 1 µA with SW1 off (8.8 mAh
a year), at most 5 mA with D1 lit (`should`). Not taken: 1.1 V or 0.9 V per cell, 0.5 or 2 mA, a window of ±10 %, a
budget of 3 or 10 mA.

## D-3 A low-current LED; R-1 at 0.5 mA down to 1.1 V per cell (2026-10-31)

`edakit sim` gave D1 (NCD0805R1, the red LED of chapter 17, VF 1.5–2.6 V at 20 mA) 7.8 µA from cells at 2.0 V at its
highest forward voltage (SIM.state) – R-1 asked for 1 mA. No red LED reaches 1 mA there by its datasheet with a
series resistor without breaking R-4: the current from fresh cells at the LED's lowest VF is about ten times the
current at the end voltage at its highest, and R-4 allows five. The owner chose a low-current LED and a new number
for R-1: D1 is Kingbright APTD2012LSURCK (C5366382), specified at 2 mA – VF 1.5–2.1 V, Iv 60–150 mcd (20–50 mcd to
CIE127) –, at 0.5 mA brighter on axis than the NCD0805R1 at 1 mA (2.5–11.5 mcd), in a narrower beam: 40° against
130°, so off axis the two are about equal (M-1, note 7). R-1 now asks for at least 0.5 mA down to
1.1 V per cell, 2.2 V for the pair (`sim.json`: cell `used` 2.2 V, `criteria.led_on_min_a` 0.0005).

R2 is 200 Ω (C17540, Basic) – Claude's correction of the 220 Ω proposed in the round, which gave 0.498 mA: from
cells at 2.2 V D1 takes 0.52 mA at its highest VF and 2.0 mA at its lowest. The current from fresh cells is D-9's. Not taken: the same LED with 0.1 mA down to 2.0 V (dim at the
end); the NCD0805R1 with 1 mA down to 1.4 V per cell (half the capacity unused).

R-3 and R-4 got the rows that test them: the current from the cells in the loads `off` and `on`
(`LIM.i */off/* BT1 …`, `LIM.i */on/* BT1 …`) – the patterns of the first draft named no row edakit writes.

## D-4 Reverse polarity: a P-MOSFET behind SW1 (2026-10-31)

PATH.reverse: two cells upside down put −3.2 V on U1, rated −0.3 V – about 4 A through its substrate diode, and U1
is gone. The owner chose the block reverse-pmos with an AO3415A (C133233) instead of the block's AO3401A: its RDS(on)
is specified from VGS −1.8 V (65 mΩ), so it is fully on down to the end voltage; drain towards SW1, source towards
VDD, gate through R3 (10 kΩ) to ground. Simulated (extra scenario `reversed/on`): Q1 blocks, 4 pA flow, VDD sits at
−0.15 V where U1's substrate diode holds Q1's leakage, D1 is dark. Not taken: a Schottky diode in series (0.15–0.25 V
of the end voltage, about 30 % of D1's current there); no protection.

## D-5 R1 = 750 kΩ: the blink rate (2026-10-31)

U1 runs as the CMOS 555's 50 % astable: R1 from OUT charges and discharges C2 between 1/3 and 2/3 of VDD, and DIS is
free for D1. With the thresholds at 1/3 and 2/3, t_high = t_low = ln 2 · R1 · C2, independent of the supply:

    T = 2 ln 2 · R1 · C2 = 1.386 · 750 kΩ · 1 µF = 1.040 s → f = 0.962 Hz, 57.7 flashes a minute, 50 % lit

The spread, as worst case: R1 ±1 % (C17817), C2 ±10 % (C28323, X7R; its DC bias at 3.2 V on a 50 V part below 1 %),
U1's thresholds from the datasheet's timing accuracy at 1.5 V (monostable 1.1·RC: 0.9–1.25 ms for 1.1 ms, i.e. the
upper threshold between 0.593 and 0.713 of VDD): T between 0.798 and 1.204 times the nominal, 47.9 to 72.3 flashes a
minute – both edges of R-2's window of 48 to 72 touched; no R1 fits the whole stack (M-1, note 6). The datasheet gives no astable accuracy below 5 V and no trigger spread tied to the
threshold's; the count at the acceptance (R-2, M-4) is the evidence. With 680 kΩ (Extended, preferred – no loading
fee) the nominal is 63.7 and the worst case reaches 80 a minute; the owner chose 750 kΩ (Extended, a loading fee of
about 3 USD per order).

The first period after switch-on is longer: C2 starts at 0 V, OUT is high and D1 dark for ln 3 · R1 · C2 = 0.82 s
instead of 0.52 s.

## D-6 Hints accepted; C4 ceramic (2026-10-31)

HINT.bulk: no cable and no plug – the cells sit in BT1 on the board; C1 100 nF and C4 1 µF at U1, as the LMC555
datasheet asks (10: 0.1 µF in parallel with 1 µF), C4 a ceramic (C28323, the part of C2) instead of an electrolytic.
HINT.lithium: two alkaline AAA cells, nothing charges them. HINT.thermal_copper on U1: it dissipates below 1 mW.
Decided by Claude, confirmed by the owner.

## D-7 What edakit does not evaluate: the dark phase and the mean current (2026-10-31)

The simulation holds U1 in the phase in which D1 is lit (OUTPUT low, DC low, the component's `states`) – a DC
operating point per scenario, no time (concept, decision 3). The dark phase, by hand:

- OUTPUT high, DC released: D1 and R2 carry only D1's leakage (≤ 10 µA at 5 V reverse, here about 0 V across it);
  R1 carries C2's charging current, at most (VDD − VDD/3) / 750 kΩ = 2.8 µA at 3.2 V; U1 at most 250 µA (its maximum
  at 5 V; 150 µA at 1.5 V).
- The cells' mean current over a period, half lit and half dark: (7.6 + 0.25) / 2 = 3.9 mA from fresh cells at D1's
  lowest VF and U1's discharge pin at 15 Ω, about 3 mA with a typical LED (M-1, finding 1) – some 260 to 330 hours,
  eleven to fourteen days, of blinking from alkaline AAA cells of about 1000 mAh down to 1.1 V. N-2 is met; it is not
  a requirement with a number.
- The edges and U1's current spikes when its output switches are not simulated; C1 and C4 supply them.

The blink rate, the duty cycle and the start-up are in D-5; R-2's evidence is the count at the acceptance.

## D-8 The layout (2026-10-31)

The board is 60 × 28 mm, about the holder's size: BT1 on the bottom with its body 0.7 … 53.8 mm under the board and
its PC pins at the right end, soldered on the top; SW1 flush with the right edge, its knob over it, its joints on the
bottom beside BT1's body; D1 beside SW1 on top. `edakit pcb place --rest` put the 555 and its parts around BT1's pins;
moved by hand 5 mm to the left and rearranged, so that `[routing] hand_solder_keep_mm = 1` keeps other nets' pads 1 mm
from BT1's and SW1's joints. Freerouting routed all 10 nets (76 track pieces, 4 vias), KiCad filled the ground pours,
its DRC found nothing.

GEO.silk "silkscreen inside the board outline" is accepted for the outline of SW1's knob, which the library footprint
draws beyond the body: the knob stands over the edge on purpose (`edge_ok`), and the maker prints nothing beyond the
outline. A layout decision by Claude: the circuit hash stays.

## D-9 The review M-1: R-4 at 8 mA, and what it corrected (2026-10-31)

The agent electrical-reviewer found nothing that blocks and one important finding: R-4's rows passed only because U1's
discharge pin was simulated at 150 Ω – the LMC555's maximum at 1.5 V (VDIS ≤ 150 mV at 1 mA). At 3.2 V it is
stronger; the datasheet's typical part at 5 V has 15 Ω. U1's entry now gives `r_out_ohm` [15, 50, 150], taken at the
simulation's spread corner (`sim.json` spread min and max): from fresh cells at D1's lowest VF the cells give 7.6 mA.
R-1 (0.5 mA at 2.2 V) and 5 mA cannot both hold with a series resistor. The owner chose R-4 at 8 mA with R2 at 200 Ω.
Not taken: R2 390 Ω with R-1 down to 1.2 V per cell; R2 390 Ω with R-1 at 0.3 mA.

What Claude corrected after the review, confirmed by the owner: the hand-over note (C2 at TRIG and TH, C3 at CV), the
numbers in the accepted reasons, Q1's model (KP 25: 52 mΩ at −1.8 V), D-5's worst case (47.9 to 72.3), "brighter on
axis, in a narrower beam" for D1. On the top silkscreen '+' and '−' beside BT1's pins and "2x AAA 1.5 V" – AAA-sized
Li-ion cells (10440, 3.7 V each) would put 8.4 V on Q1's gate (8 V) and overload R2 and D1 (M-1, note 8). Not
changed: R-1's margin rests on D1's VF at 25 °C (±0.1 V tolerance, −1.9 mV/K – M-1, note 2).
