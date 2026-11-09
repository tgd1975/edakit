# Perfboard layout: the build plan of a hand-wired board, generated and checked

Status 2026-11-03: concept from an idea of the owner the same day ("nach dem Schema gibt es ja auch die prototypische
Umsetzung auf den Europlatinen … da braucht man auch eine Anordnung der Elemente und wo die Kabel laufen sollten …
das wäre doch auch eine Möglichkeit, das generieren zu lassen"), decided in a decision round the same day (decisions
1 to 5 the owner's, 6 to 10 Claude's and confirmed, at the end). Nothing built: every step starts on the owner's word.

A prototype on the bell (2026-11-09), to agree on what a plan looks like:
[prototypes/perfboard-layout/](prototypes/perfboard-layout/README.md) holds the bell's THT circuit as a plan, a
script that checks its nets against the graph and draws both views, the build and test lists, and the points the
prototype had to decide.

## Why

After step 7 a circuit is "enough to wire it by hand or to build it on a perfboard" (`docs/steps/README.md`). How is
left to the maker: where each part sits on the grid, which strips are cut, where the wires run, on which side. That
plan lives on squared paper or in someone's head – by the yardstick (`docs/concepts/done/design-as-text.md`) exactly
what should be text. And its mistakes are the classic ones of the build: a strip not cut, a cut in the wrong row, the
bottom side read the wrong way round, a wire to the neighbouring hole – found with the multimeter, after soldering.

edakit already holds what a plan needs: the graph has the nets of each board, the parts entries have pads, leads and
bodies (`footprint_data`, the library cache of `part import`, `lead`, `body`, handbook 4.2 and 4.5), a hand-wired
board is a board of its own (`wired = true`, handbook 10.2), and the hand-over says what is fixed, at the edge and near
its host (handbook 14.1). What is missing is the plan itself, a check of it against the graph, and its drawing.

Not to confuse with the breadboard view of `docs/concepts/done/wired-schematic.md` (decision 5, struck): that was a
look of the schematic. This is the build plan of a board – for a perfboard what the placement plan is for a PCB.

## A perfboard as data

One model covers every kind: a grid of holes at a pitch, and groups of holes the copper already joins. A cut splits a
group, a wire or a solder bridge joins two holes.

| Kind | Groups joined by copper | Typical use | Built first (decision 2) |
| --- | --- | --- | --- |
| Lochraster (a pad per hole) | none | every connection a wire or a solder bridge | yes |
| Lochstreifen (a pad over three holes) | runs of three holes | a part's lead and two wires share a pad | yes |
| Streifenraster (stripboard) | each row a strip | nets along the strips, cuts between them, links across | when a project asks |
| Breadboard pattern (5-hole columns, two rails per side) | columns and rails | a breadboard build moved onto solder | when a project asks |

The two the owner has come first, "keine Wissenschaft daraus machen": the model stays general, so another kind later
is a file of data, no new code.

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
kind = "pad-per-hole"        # edakit/perfboards/pad-per-hole.toml – or "3-hole-strips"
holes = [30, 20]             # the piece used: 30 columns (A to AD) × 20 rows
mounting = ["A1", "AD1", "A20", "AD20"]

[place]                      # the hole of pin 1, the rotation; axial parts their lead span in holes
U1 = { at = "H8", rot = 0 }              # DIP-8 in a socket
R1 = { at = "D4", rot = 90, span = 4 }   # 0207 lying flat: 10.16 mm
C1 = { at = "M6", rot = 0 }
J1 = { at = "A10", rot = 270 }

[[wire]]
net = "VCC"
path = ["D2", "D9"]          # straight between holes; more points for a bent run
side = "top"                 # top: insulated wire; bottom: straight solder bridges only (decision 11)

[[wire]]
net = "GND"
path = ["H11", "H12"]
side = "bottom"
kind = "bridge"              # a solder bridge between two neighbouring pads
```

On the bottom there are only straight solder bridges between neighbouring holes (decision 11): a bridge path along
one row or one column is a row of bridges, one per step, and never turns a corner. Everything else is an insulated
wire on top; each of its ends goes through
a free hole beside its pin and is joined to it by a bridge below, since a lead and a wire do not fit into one hole.

A kind with strips that are cut gets `cuts = [...]` in a section `[strips]` – not on the two kinds built first. Wire
colours follow the net (supply red, ground black) unless the plan names one.

## What edakit checks

The plan is the layout of a hand-wired board; its checks belong where the layout's checks are.

- **The nets.** From the holes, the copper groups minus the cuts, the wires and bridges and the pins in the holes,
  edakit builds the nets the plan makes and compares them with the graph's nets of that board: a connection missing,
  two nets shorted, a pin in no hole, two pins in one hole. The core of it – this is what goes wrong by hand.
- **The grid.** Every pad of a placed part lands on a hole, from the pads of its parts entry or the library cache. A
  part whose pins are off the 2.54 mm grid (a slide switch with terminals 2.0 mm apart, a terminal block at 3.5 mm) is
  an error beyond a tolerance that leads can be bent to, a value of the kind's data. An SMD part is an error: a
  perfboard takes through-hole parts only (decision 3).
- **Bodies.** Body boxes (footprint outline, `body.box`) do not overlap; an axial part's span is at least its body
  plus the bend of its leads; nothing sits on a mounting hole.
- **Wires.** On the bottom only bridges between neighbouring holes, straight along one row or one column – a corner
  within a row of bridges, or two rows ending at right angles in the same empty hole, is a finding naming that hole;
  where a hole joins two nets – a bridge, a wire's end, a lead –, the finding names that hole too. An insulated wire on top ends in free holes
  that no body covers and may cross others; each wire has its length.
- **Current.** A wire, a bridge or a strip carries its net's current – from the simulation where it has one, against
  the wire's gauge and the copper's rating from the kind's data.
- **The hand-over.** `fixed`, `edge` and `near` hold as on a PCB: a connector at the edge, the decoupling capacitor
  within `near_mm` of its IC.

## What edakit draws and writes

- **Top view:** parts with their designators and polarity, wires in their colours, hole names at the edges.
- **Bottom view in the orientation of the top view** (decision 12): seen through the board from above, A1 at the top
  left in both, so the two read alike. Soldered leads clearly stronger than empty holes, the bridges, the holes where
  a wire comes through from the top (strips and cuts on a kind that has them).
- **Build list:** the order of soldering from low to high – resistors, wires on top, diodes, sockets, capacitors,
  connectors, the bridges once the leads they join are in, modules last –, each with its holes and its polarity.
- **Test list for the multimeter:** per net the pairs of holes that must beep across each wire and bridge; next to
  each bridge the neighbouring pads of other nets that must not; supply to ground before the first
  power-up.
- **The order:** the board, wire and sockets as items off the board (`[[extra]]`, handbook 8.4), so `edakit order`
  puts them into the cart – and, once it is built, the parts on hand (`docs/concepts/done/parts-on-hand.md`) take what
  lies in the drawer off it.

The drawings are SVG, as `edakit schematic draw` writes them, and read in the light and the dark theme of the site.

## Who writes the plan

Claude, as for a PCB (decision 1): the same round, only that the board is a perfboard and a person solders it. Claude
takes the hand-over, writes `[perfboard]`, `[place]` and the wires as text, edakit checks and draws, Claude fixes the
findings until none is left and shows the drawings. The check makes a wrong plan visible, not the model's grid sense.

Two other ways were weighed and are not taken now:

| Way | How | Why not now |
| --- | --- | --- |
| edakit generates | `edakit perfboard place` and `route`: parts so that a net's pins come close, a maze router on the bottom grid, insulated wires as the fallback; fixed parts from the hand-over stay | the larger piece of work, a search with its own tuning; it comes piece by piece only where the rounds of Claude cost too much (decision 6) |
| [VeroRoute](https://appstream.ubuntu.com/noble/universe/metainfo/veroroute.html) | edakit writes a KiCad netlist (handbook 16), the maker lays out in VeroRoute – stripboard, perfboard, netlist import from KiCad, auto-routing, a connectivity check | the plan would live in a GUI program and its file, against the yardstick |

## Through-hole only

A perfboard takes through-hole parts (decision 3). A circuit designed in SMD for assembly – blinker-555 and
coin-cell-led are, but for blinker-555's battery holder and switch – is built on a perfboard as a variant: a project
of its own in a folder below the main project, reading its files and its own (handbook 3, 10.4), with a board
`wired = true`, through-hole parts entries and the plan. Its simulation, checks and requirements stay those of the
circuit. The bell has such variants already (`variants/tht`, `variants/esp32tht` of automatic_christmas_bell), as PCBs.

## Steps

| Step | What | Done when |
| --- | --- | --- |
| LR.1 (the kinds) | `edakit/perfboards/pad-per-hole.toml` and `3-hole-strips.toml`: pitch, hole, groups, sizes, copper rating with source | both read, a test per kind |
| LR.2 (plan and nets) | `[perfboard]`, `[place]` in holes, `[[wire]]` read from the board file of a board `wired = true`; the nets the plan makes against the graph's | open, short, pin without hole, two pins in a hole each a test |
| LR.3 (the other checks) | grid and bend tolerance, SMD, bodies and spans, bridges only below, current, the hand-over's `fixed`, `edge`, `near` | a negative test each |
| LR.4 (drawings and lists) | top view, bottom view in its orientation, build list, test list for the multimeter, the board and the wire as `[[extra]]` | SVGs read in both themes |
| LR.5 (stage L) | the plan in the layout hash of a hand-wired board, stage L runs LR.2 and LR.3, the agent pcb-reviewer's M-5 on it (decision 4) | the gate of a variant passes and fails as it should |
| LR.6 (the round) | the skill pcb-round with the perfboard round, the handbook's section (7 or 4.5) | handbook and skill name the same keys |
| LR.7 (the examples) | a perfboard variant of coin-cell-led and of blinker-555, each with a plan the tests hold | both pass the gate |
| LR.8 (the bell) | a perfboard variant of the bell from its THT parts, in the bell's repository by its session | the bell soldered on a perfboard from the plan |

## Decisions

The owner's answers of 2026-11-03 in a decision round, decisions 6 to 10 Claude's, confirmed by the owner the same day;
decisions 11 and 12 the owner's of 2026-11-09, on the prototype.

| # | Decision | Reason | Alternatives |
| --- | --- | --- | --- |
| 1 | Claude writes the plan, edakit checks and draws it – the round of a PCB | "das ist genauso wie PCB und Bestückung, nur dass es halt nicht PCB ist und maschinelle Bestückung" | edakit generates the plan; VeroRoute |
| 2 | First the two kinds the owner has: a pad per hole, and a pad over three holes; others as data when a project asks | "ich hab die mit den Einzelkupferflächen und die mit den drei Löcher überdeckenden Kupferflächen – ich würd da keine Wissenschaft daraus machen" | stripboard first; all four kinds |
| 3 | Through-hole only: an SMD part on a perfboard is an error, no adapter boards | "keine SMD … das sind offensichtlich ausschließlich THT" | an SMD part as a finding with an adapter board as its way out |
| 4 | The plan is stage L of a hand-wired board: in the layout hash, checked by the gate, M-5 by the pcb-reviewer | "warum nicht … wir wollen ja, dass unsere Pläne gut sind" | a drawing outside the gate |
| 5 | Tried on both examples and on the bell | "wir haben zwei Beispielschaltungen und die Glocke ist immer ein dankbarer Kandidat" | one circuit only |
| 6 | No generator of edakit's own for now; help like a `place --rest` only once the bell's rounds show too many iterations. When one comes: `pcb place --rest` places on the hole grid, a small router of edakit's own lays the wires hole to hole (a grid of 30 × 20 holes is small) – neither KiCad nor Freerouting | decision 1; the check is needed in every way, the generator only if the rounds cost too much. Asked "vielleicht in KiCad?": KiCad has no auto-layout – on its path edakit places itself and Freerouting routes, gridless, so its tracks would be pulled onto the holes afterwards, with shorts the check would have to catch | the generator in the first build; Freerouting tried once in LR.7; the generator through KiCad and Freerouting |
| 7 | The skill pcb-round carries the perfboard round, the agent pcb-reviewer reviews it – no new skill, no new agent | decision 1: the same role, the PCB designer of handbook 14.1 | a skill perfboard-round of its own |
| 8 | The examples get a variant each, `examples/coin-cell-led/variants/perfboard/` and `examples/blinker-555/variants/perfboard/`, their through-hole parts chosen with the skill part-search in LR.7 – blinker-555's switch with 2.54 mm terminals | decision 5; the tests hold a variant like the example | plans only in the tests' fixtures |
| 9 | The bell's perfboard build is a variant in automatic_christmas_bell, built by that repository's session after LR.7 | the bell's files are its repository's | a copy of the bell in edakit's tests |
| 10 | Holes named by column letter and row number, A1 at the top left seen from the top; the kinds `pad-per-hole` and `3-hole-strips` | as many Euro boards print them at their edges | coordinates in mm; numbers for both axes |
| 11 | On the bottom only straight solder bridges between neighbouring holes, never around a corner; everything else an insulated wire on top | "auf der Oberseite mit Kabeln und auf der Unterseite mit kurzen blanken Brücken, die nebeneinander liegende Punkte verbinden … keine Kabel auf der Unterseite – wie löte ich die denn gut an?"; "eine Brücke unten muss gerade sein … wenn sie schon so verwinkelt ist, warum sie dann nicht kurz oben führen?" | bare wire on the bottom along a row of pads (the prototype's first version) |
| 12 | The bottom view in the orientation of the top view, soldered leads clearly stronger than empty holes | "das muss gleich orientiert sein wie top … sonst tut man sich beim Lesen schwer"; "Pins, die gelötet sind, deutlich stärker als geschlossenes Loch" | the bottom view mirrored, seen from below (the concept until then) |

By the yardstick: nothing of the plan stays in someone's head – the board file holds it, edakit checks and draws it.
