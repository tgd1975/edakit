# Decisions

Numbered, with reason and date. The example of handbook chapter 17 – the walkthrough tells when each one came up.

## D-1 Set up for edakit (2026-10-29)

One board `main`, JLCPCB Economic assembly on the top side, 5 sets, no budget. Built for oneself in the EU
(`purpose.use` "private"). No firmware, no documents that quote values. The requirements now, with the skill
requirements: N-1, N-2, R-1, R-2 in `hardware/requirements.toml`.

## D-2 A red LED instead of the block's green one (2026-10-29)

The block `led` brings a green 0805 LED (KT-0805G, Vf 2.6–3.1 V) with 150 Ω. On a coin cell that is too much forward
voltage: `edakit sim` gave 0.4 mA and 0.1 µA from a used cell (2.5 V) – R-1 asks for 1 mA. A red one (NCD0805R1,
C84256, Vf 1.5–2.6 V at 20 mA) gives 1.22 mA there and 10.7 mA from a fresh cell with the 150 Ω of the block. Its
symbol numbers the pins the other way round: pin 1 is the cathode.

The margin at a used cell (1.22 mA against 1 mA) rests on two assumed values, the LED's series resistance of 10 Ω
(the simulation's default) and the used cell's 40 Ω. R-1 holds anyway (M-1, note 2): a red AlGaInP die has a
junction voltage of about 1.9–2.0 V, so a part at 2.6 V at 20 mA carries the rest in a series resistance of 30 Ω or
more – 2.7 mA at a used cell.

## D-3 No reverse-polarity protection (2026-10-29)

BT1 takes a cell upside down, and PATH.reverse asks for a blocking part behind it. A Schottky diode in series costs
about 0.3 V – exactly the margin R-1 needs from a used cell; a P-MOSFET costs two parts on a board without an IC. A
reversed cell drives R1 and D1 backwards: D1 blocks, 3.2 V against its rated 5 V. The simulation shows it (extra
scenario `reversed/pressed`: LIM.v reverse voltage, SIM.state LED dark), and PATH.reverse is accepted on LED_SW with
that reason.

## D-4 BT1 soldered by hand (2026-10-29)

JLCPCB places the holder C70377 only under Standard PCBA ("Standard Only", PARTS.stock from `edakit stock`): 52.60 USD
for 5 boards instead of 20.65 USD with BT1 left out (`edakit cost`). Its two SMD tabs are easy to solder by hand
(`bom: false`; `edakit order` puts five into the LCSC cart). The same BS-6 holder by Lian Xin (C22363833) is
"Economic and Standard" on the same footprint – `edakit part diff C70377 C22363833` lays the pads on each other
unchanged – but its drawing does not say which pad is plus.

## D-5 Who uses it (2026-10-30)

Adults, at a desk; the board is kept out of the reach of small children. The holder keeps the CR2032 open and the cell
comes out by hand – a swallowed lithium coin cell burns. For a child the board would be a toy, with a holder that needs
a tool or a screwed cover (M-6, note 1). Given away it would be a gift, sold a sale: a new purpose and a new M-6.

## D-6 A round board (2026-10-31)

The owner wants it round. Ø 44 mm – `rect = [44, 44]` with `corner_radius = 22` in the board file, 48 chords, 45 µm
off the circle. The holder sits almost in the middle, the cell (Ø 20 mm) nearly concentric with the board, with 10 mm
above it to lever it out; button, LED and resistor below. The two tooling holes of the Economic assembly are
diagonally opposite. A layout decision: the circuit hash stays, and M-1 and M-6 keep counting.

## D-7 The cell's current: a press is short (2026-10-31)

A CR2032 is rated for 3 mA continuous and 15 mA in pulses (Jauch CR 2032 H2B, 15092025; Murata gives 20 mA for 2 s
pulses and calls more than 10 mA a high drain). `sim.json` holds the continuous value as `i_max_a` of the cell states
`fresh` and `used`, and LIM.i/cell reports SW1 held down: 10.7 mA from a fresh cell, 6.3 mA from a used one at the
LED's lowest forward voltage. The finding is accepted on BT1: SW1 is pressed for a moment, and held longer the cell
loses capacity and voltage, nothing worse – the voltage drop is in the simulation through the cell's `r`. A pulse limit
with a duration per load was the alternative; the owner judged it more than this board needs.
