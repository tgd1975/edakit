# Prototype: the bell on a perfboard

Written on 2026-11-09 for the concept [perfboard-layout.md](../../perfboard-layout.md), on the owner's request for an
example board "damit wir wissen, dass wir vom gleichen reden". Its first version led to the concept's decisions 11
(on the bottom only solder bridges between neighbouring holes, everything longer an insulated wire on top) and 12 (the
bottom view in the orientation of the top view, soldered leads clearly marked); this version follows both.

Nothing of the steps LR.1 to LR.8 is built. A script does the check and the drawings, as the scripts of
[footprint-data](../footprint-data/README.md) do; it is no edakit code, and edakit's pytest does not collect it.

| File | What | Stands in for |
| --- | --- | --- |
| [bell-perfboard.toml](bell-perfboard.toml) | The plan as text: `[perfboard]`, `[place]`, `[near]`, `[[wire]]`. It is for the bell's THT circuit (`automatic_christmas_bell`, `variants/tht`), whose graph and parts stay unchanged. | The board file of a hand-wired variant (LR.8) |
| [pad-per-hole.toml](pad-per-hole.toml) | The kind as data: pitch, pads, the tolerances for bending leads | LR.1 |
| [perfboard.py](perfboard.py) | Builds the nets the plan makes and compares them with the graph's. Checks the grid, the bodies, the wires, the mounting holes and `near`, then draws and writes the lists. | LR.2 to LR.4 |
| [bell-perfboard.build.md](bell-perfboard.build.md) | Its output: the findings, the build list from low to high, the test list for the multimeter and the material | LR.4 |

```bash
python3 perfboard.py bell-perfboard.toml <automatic_christmas_bell>/variants/tht
```

![Top view](bell-perfboard.top.svg)

![Bottom side, in the orientation of the top view](bell-perfboard.bottom.svg)

## The layout in short

The board is 33 × 22 holes, which is the size of the bell's 85 × 56 mm PCB, cut from a Euro board.

- **Nano:** on the left with its USB socket at the edge, as on the THT PCB.
- **LED row:** along the back edge in countdown order (R-13). The cathodes sit in row 2 and are joined by a row of
  bridges, the anodes in row 3. Each series resistor stands upright below its LED, bridged to the anode above and to
  the Nano's pin below.
- **Wires under the Nano:** the Nano's pins D6, D5, D4, D3 and D2 carry G1, G2, R, Y2 and Y1, which is not the
  countdown order G1, G2, Y1, Y2, R. So Y2 and R go as wires on top, under the Nano between its sockets, and come up
  at its right end. The servo signal and the two button lines take the same way.
- **Power:** below the Nano, ground runs as a row of bridges along row 16 and +5 V along row 22. R8, R9, the two
  pull-downs and the buttons stand across or on them; C1 and J1 sit at the right end. A short wire on top brings
  +5 V from the Nano's 5V pin down to row 22, another one joins the LED cathodes to the Nano's GND (pin 4).
- **In all:** 7 insulated wires (43 cm) and 81 solder bridges, 45 of them in the three long rows (cathodes, ground,
  +5 V).

## What the check says

On the plan it finds no error and gives three notes:

- the buttons' leads (6.5 × 4.5 mm) are bent by 0.63 mm into the 7.62 × 5.08 mm grid;
- the LED cathodes reach the rest of ground only inside the Nano (its GND pins 4 and 29). The test list therefore
  shows ground as two groups that beep together once U1 is plugged in.

A copy of the plan with three typical mistakes: the bridge L8–L9 forgotten, the ground row started one hole too early
(M16 instead of N16, where the +5 V wire comes through), and LED3 turned like the green LEDs:

```text
error   PERF.short     +5V (9 pins) and GND (12 pins) and LED_Y1_A (LED3.anode in L2) in one piece of copper
error   PERF.short     GND (LED3.cathode in L3) and LED_Y1_A (R2.2 in L4) in one piece of copper
error   PERF.open      GND is open between 12 pins | LED3.cathode in L3
error   PERF.open      LED_Y1 is open between R2.1 in L8 | U1.PD2 in L9
error   PERF.open      LED_Y1_A is open between LED3.anode in L2 | R2.2 in L4
error   PERF.meet      L2 joins GND bridges F2 … R2 with LED3.anode (LED_Y1_A)
error   PERF.meet      L3 joins LED_Y1_A bridge L3–L4 with LED3.cathode (GND)
error   PERF.meet      M16 joins GND bridges M16 … AF16 with +5V bridge M15–M16 with +5V wire M16–M22
```

`PERF.meet` names the hole where two nets touch, which is where the soldering iron goes. The codes `PERF.*` are the
prototype's own names, not edakit's.

## What the prototype had to decide

The concept leaves these points open, or they could be read another way:

1. **Rows of bridges.** Decision 11 allows bridges between neighbouring holes only; the prototype takes a path of
   them along a row or a column as allowed, one bridge per step. Ground and +5 V are such rows. The alternative is
   one wire on top from member to member, with a bridge at each end.
2. **Hole names and designators are the same strings.** R8 is a hole and a resistor, and so are C1, J1, S1 and U1.
   The build list reads "R5 330Ω: R8–R4". The prototype keeps decision 10 as it is.
3. **`at` is the hole of pin 1, and `rot` turns counterclockwise as seen from the top, in steps of 90°.** The yellow
   LEDs have their cathode on pin 1, the green and red ones their anode. So two LEDs that sit the same way need
   `rot = 270` and `rot = 90`. This is the same trap as on the PCB ("yellow footprint has its + on pad 2"). For a
   part with two leads, holes named by role would avoid it: `LED3 = { anode = "L3", cathode = "L2" }`.
4. **Pins a part joins itself count:** the Nano's two GND pins, and the button's pins 1/2 and 3/4. The prototype takes
   this from the same pin name, or on a button from the same role. The parts entry has no key for it; only the
   button's notes mention it. What a plugged-in module joins inside does not count for the test list.
5. **The mounting holes miss the frame.** The bell's frame has its M3 holes 78 × 49 mm apart. On the grid, B2 to AF21
   is 76.2 × 48.3 mm. A hole name cannot hit the frame's spacing. So either `mounting` takes positions in mm, drilled
   between holes, or the frame gets new holes. The prototype does not check this; it matters for LR.8.
6. **A module on sockets has a raised body.** Wires under it on top are allowed: five run there. A part under it would
   be a note, given the 8.5 mm sockets.
7. **The tolerances in pad-per-hole.toml are assumptions:** 0.8 mm for bending a lead, 1.5 mm of straight lead for
   an axial part, and no copper rating.

The prototype does not cover:

- the current per wire and bridge;
- the kind `3-hole-strips`;
- stage L: the layout hash, the gate and M-5;
- the `[[extra]]` items for `edakit order`;
- the hand-over's `edge`.

The footprints are a table in the script, not `footprint_data` or the library cache. `near` is measured as on a PCB,
the gap between the parts' body boxes.
