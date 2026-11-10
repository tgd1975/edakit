# Build it on a perfboard

After this step you have the plan of your circuit on a perfboard, checked against the circuit, and the lists to
solder it from.

!!! note "State"
    Built and checked offline; no prototype has been soldered from such a plan yet.

A prototype comes after [Draw and hand over](07-draw-and-hand-over.md), before a board or instead of one. No EDA
program takes part.

## What you do

Say that you build the board by hand on a perfboard, and which kind: a pad per hole, or a pad over three holes. The
board becomes a [hand-wired board](../glossary.md#hand-wired-board). Its parts must be through-hole, so a circuit in
SMD first gets through-hole parts.

Claude writes the [perfboard plan](../glossary.md#perfboard-plan): each part on the grid, bare wire below, insulated
wires on top. edakit holds it to the circuit and draws both sides:

```text
$ edakit perfboard
tht: Lochraster, a pad per hole, 33 × 22 holes, 19 parts, 8 wires, 76 bridges
  note     PERF.grid/bent   S1: leads bent by 0.63 mm into the 2.54 mm grid (allowed 0.8 mm)
  …
  0 errors; -> build/edakit/perfboard/tht/top.svg, build/edakit/perfboard/tht/bottom.svg, build/edakit/perfboard/tht/build.md
```

![The Christmas bell's THT circuit on a perfboard, top view, drawn by edakit perfboard](../pictures/perfboard-top.svg)

![The same board's bottom side, seen through the board from above](../pictures/perfboard-bottom.svg)

## What you are asked

What the plan must keep, as for a board: the parts you touch or look at, the size of the piece you cut. Claude fixes
every error itself and runs the check again.

## What you decide

Whether the drawings read right before you solder. The reviewer pcb-reviewer reads the plan as it reads a board, for
the check M-5 of [Have it reviewed](08-have-it-reviewed.md).

## What you have

The two drawings and four lists in `build.md`. The cut list gives each wire with its length. The build list goes from
low parts to high. The test list says what the multimeter must read, and the material list what to buy. `edakit gate`
checks the plan as the layout, without EasyEDA.

Then you solder and test. A board from the same circuit: [Have it reviewed](08-have-it-reviewed.md).

## Read on

- The handbook: [A perfboard](../../handbook/07-pcb.md#79-a-perfboard)
- The keys: [The plan of a perfboard](../../handbook/10-reference.md#the-plan-of-a-perfboard)
