# Perfboard layout: the build plan of a hand-wired board, generated and checked

Status 2026-11-03: concept from an idea of the owner the same day ("nach dem Schema gibt es ja auch die prototypische
Umsetzung auf den Europlatinen … da braucht man auch eine Anordnung der Elemente und wo die Kabel laufen sollten …
das wäre doch auch eine Möglichkeit, das generieren zu lassen"). Nothing decided, nothing built; the open decisions
are at the end.

## Why

After step 7 a circuit is "enough to wire it by hand or to build it on a perfboard" (`docs/steps/README.md`). How is
left to the maker: where each part sits on the grid, which strips are cut, where the wires run, on which side. That
plan lives on squared paper or in someone's head – by the yardstick (`docs/concepts/done/design-as-text.md`) exactly
what should be text. And its mistakes are the classic ones of the build: a strip not cut, a cut in the wrong row, the
bottom view drawn without mirroring, a wire to the neighbouring hole – found with the multimeter, after soldering.

edakit already holds what a plan needs: the graph has the nets of each board, the parts entries have pads, leads and
bodies (`footprint_data`, the library cache of `part import`, `lead`, `body`, handbook 4.2 and 4.5), a hand-wired
board is a board of its own (`wired = true`, handbook 10.2), and the hand-over says what is fixed, at the edge and near
its host (handbook 14.1). What is missing is the plan itself, a check of it against the graph, and its drawing.

Not to confuse with the breadboard view of `docs/concepts/done/wired-schematic.md` (decision 5, struck): that was a
look of the schematic. This is the build plan of a board – for a perfboard what the placement plan is for a PCB.

## A perfboard as data

One model covers every kind: a grid of holes at a pitch, and groups of holes the copper already joins. A cut splits a
group, a wire or a solder bridge joins two holes.

| Kind | Groups joined by copper | Typical use |
| --- | --- | --- |
| Lochraster (pad per hole) | none | every connection a wire or a solder bridge |
| Streifenraster (stripboard) | each row a strip | nets along the strips, cuts between them, links across |
| Lochstreifen (3-hole strips and the like) | short runs of n holes | between the two above |
| Breadboard pattern (5-hole columns, two rails per side) | columns and rails | a breadboard build moved onto solder |

Each kind is a file of data beside the makers' profiles, `edakit/perfboards/<kind>.toml`: pitch (2.54 mm), hole
diameter, the pattern of its groups, single- or double-sided, the usual sizes (Europlatine 160 × 100 mm, half
Euro 100 × 80 mm) and what a strip carries – width and copper thickness, and a current only with its source (the
board's datasheet), never a guess. A board the maker cuts from a larger one gives its size in holes.

## The plan as text

In the board file of the hand-wired board, `hardware/boards/<name>.toml`, as the placement plan is for a PCB. Holes
are named by column letter and row number, as many Euro boards print them at their edges – the position in mm follows
from the pitch, so the drawing, the mechanical model and the body checks work in mm as before:

```toml
[perfboard]
kind = "stripboard"          # edakit/perfboards/stripboard.toml
holes = [30, 20]             # the piece used: 30 columns (A to AD) × 20 rows; strips along the rows
mounting = ["A1", "AD1", "A20", "AD20"]

[place]                      # the hole of pin 1, the rotation; axial parts their lead span in holes
U1 = { at = "H8", rot = 0 }              # DIP-8 across rows 8 to 11: the strips under it are cut in column J
R1 = { at = "D4", rot = 90, span = 4 }   # 0207 lying flat: 10.16 mm
C1 = { at = "M6", rot = 0 }
J1 = { at = "A10", rot = 270 }

[strips]
cuts = ["J8", "J9", "J10", "J11", "P4"]  # cut at the hole, with the spot-face cutter

[[wire]]
net = "VCC"
path = ["D2", "D9"]          # straight between holes; more points for a bent run
side = "top"                 # top: insulated wire; bottom: bare wire or a solder bridge
```

On a Lochraster board a solder bridge between two neighbouring holes is a wire of length one on the bottom
(`kind = "bridge"`). Wire colours follow the net (supply red, ground black) unless the plan names one.

## What edakit checks

The plan is the layout of a hand-wired board; its checks belong where the layout's checks are.

- **The nets.** From the holes, the copper groups minus the cuts, the wires and bridges and the pins in the holes,
  edakit builds the nets the plan makes and compares them with the graph's nets of that board: a connection missing,
  two nets shorted, a pin in no hole, two pins in one hole. The core of it – this is what goes wrong by hand.
- **The grid.** Every pad of a placed part lands on a hole, from the pads of its parts entry or the library cache. A
  part whose pins are off the 2.54 mm grid (a slide switch with terminals 2.0 mm apart, a terminal block at 3.5 mm) is
  a finding, within a tolerance that leads can be bent to as a value of the kind's data; an SMD part is a finding with
  its way out – a through-hole part, or an adapter board as a bought board.
- **Bodies.** Body boxes (footprint outline, `body.box`) do not overlap; an axial part's span is at least its body
  plus the bend of its leads; nothing sits on a mounting hole.
- **Wires.** Bare wires and bridges on the bottom do not cross and touch no foreign pad; insulated wires on top may
  cross; each wire has its length.
- **Current.** A strip or a wire carries its net's current – from the simulation where it has one, against the
  strip's rating from the kind's data and the wire's gauge.
- **The hand-over.** `fixed`, `edge` and `near` hold as on a PCB: a connector at the edge, the decoupling capacitor
  within `near_mm` of its IC.

## What edakit draws and writes

- **Top view:** parts with their designators and polarity, wires in their colours, hole names at the edges.
- **Bottom view, mirrored** and labelled "seen from below": strips, cuts, bridges, bare wires – the mirror is drawn by
  edakit, never by the maker.
- **Build list:** the order of soldering from low to high – bridges and links, resistors, diodes, sockets,
  capacitors, connectors, modules –, each with its holes and its polarity.
- **Test list for the multimeter:** per net the pairs of holes that must beep across each cut, wire and bridge; at
  each cut the two neighbouring strips that must not; supply to ground before the first power-up.
- **The order:** the board, wire and sockets as items off the board (`[[extra]]`, handbook 8.4), so `edakit order`
  puts them into the cart – and, once it is built, the parts on hand (`docs/concepts/new/parts-on-hand.md`) take what
  lies in the drawer off it.

The drawings are SVG, as `edakit schematic draw` writes them, and read in the light and the dark theme of the site.

## Who generates the plan

| Way | How | For | Against |
| --- | --- | --- | --- |
| **A. Claude writes, edakit checks** | Claude writes `[perfboard]`, `[place]`, cuts and wires as text, edakit checks and draws, Claude fixes the findings until none is left – as with the PCB placement plan | small to build: data, parser, check, drawing; nothing outside the repository; the check makes a wrong plan visible, not the model's grid sense | a model places on a grid poorly by itself – several rounds on a board of 20 parts, tokens each time |
| **B. edakit generates** | `edakit perfboard place` and `route`: on stripboard nets onto strips, parts so that a net's pins share a strip, cuts between, links for the rest; on Lochraster a maze router on the bottom grid, insulated wires as the fallback; fixed parts from the hand-over stay | a good plan at the first go, the same result every run | the larger piece of work; a search with its own tuning |
| **C. VeroRoute** | edakit writes a KiCad netlist (handbook 16), the maker lays out in [VeroRoute](https://appstream.ubuntu.com/noble/universe/metainfo/veroroute.html) – stripboard, perfboard, netlist import from KiCad, auto-routing and a connectivity check | exists, open source | the plan lives in a GUI program and its file – against the yardstick unless edakit reads that file back |

Recommended: A first – the check and the drawing are needed in every way, and with them a plan Claude writes is safe
–, then B piece by piece where the rounds of A cost too much (a `place --rest` for the parts without a hole first).
C only to compare the quality of A and B on the same circuit.

## Circuits designed for assembly

A board designed for JLCPCB's assembly is SMD: blinker-555 has everything in 0805, SOIC-8 and SOT-23 but the battery
holder and the switch, and the switch's terminals are 2.0 mm apart. Its perfboard build is the same circuit with other
parts – through-hole resistors, a DIP-8 555, a 5 mm LED. edakit has the place for it: a variant, a project of its own
in a folder below the main project that reads the main project's files and its own (handbook 3, 10.4). Its graph swaps
the parts entries; its simulation, its checks and its requirements stay those of the circuit.

## Open decisions

| # | Question | Alternatives (recommendation first) |
| --- | --- | --- |
| 1 | Who generates the plan? | A, then B piece by piece · B straight away · C (VeroRoute) |
| 2 | Which kinds first? | stripboard and Lochraster · stripboard only · all four of the table |
| 3 | A circuit designed in SMD on a perfboard? | a variant with through-hole parts · a second board in the same graph · not supported, a finding only |
| 4 | Where in the gate? | stage L of a hand-wired board: its plan in the layout hash, the pcb-reviewer's M-5 on it · outside the gate, a drawing only |
| 5 | The first circuit to try it on? | a through-hole variant of blinker-555, as an example the tests hold · a real project of the owner |

By the yardstick: nothing of the plan stays only in EasyEDA or in someone's head – the board file holds it, edakit
draws and checks it; with C the plan would live in VeroRoute's file.
