# Perfboard layout: the build plan of a hand-wired board, generated and checked

Status 2026-11-03: concept from an idea of the owner the same day ("nach dem Schema gibt es ja auch die prototypische
Umsetzung auf den Europlatinen … da braucht man auch eine Anordnung der Elemente und wo die Kabel laufen sollten …
das wäre doch auch eine Möglichkeit, das generieren zu lassen"), decided in a decision round the same day (decisions
1 to 5 the owner's, 6 to 10 Claude's and confirmed, at the end). Nothing built: every step starts on the owner's word.

On 2026-11-09 a prototype on the bell settled what a plan looks like – the owner: "jetzt passts".
[prototypes/perfboard-layout/](prototypes/perfboard-layout/README.md) holds the bell's THT circuit as a plan, a
script that checks its nets against the graph and draws both views, and the cut, build and test lists; it is the
reference for LR.1 to LR.4. Its rounds brought decisions 11 to 23: the owner's 11 to 15 and 22, Claude's 16 to 21 and
23, confirmed by the owner the same day.

In implementation since 2026-11-09, on the owner's word ("implementiere das perfboard concept"): LR.1 to LR.6 are
built in [#365](https://github.com/tgd1975/edakit/pull/365), edakit 1.2.1 – `edakit perfboard`, the codes PERF.*,
stage L, handbook 7.9; LR.7 and LR.8 are TD-155 and TD-156 in `TODO.md`.

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
group, a wire or a bridge joins two holes.

| Kind | Groups joined by copper | Typical use | Built first (decision 2) |
| --- | --- | --- | --- |
| Lochraster (a pad per hole) | none | every connection a wire or a bridge | yes |
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
are named by column letter and row number, as many Euro boards print them at their edges, A1 at the top left seen
from the top (decisions 10, 13). The position in mm follows from the pitch, so the drawing, the mechanical model and
the body checks work in mm as before. From the prototype on the bell:

```toml
[perfboard]
kind = "pad-per-hole"                       # edakit/perfboards/pad-per-hole.toml – or "3-hole-strips"
holes = [33, 22]                            # the piece used: 33 columns (A to AG) × 22 rows

[[holes]]                                   # mounting holes in mm, as on a PCB (decision 15)
x = 2.91
y = 3.44
d = 3.2

[place]
U1 = { at = "P9", rot = 270 }               # the hole of pin 1 and the rotation
R4 = { at = "H8", rot = 90, span = 5 }      # an axial part with its lead span in holes
LED3 = { anode = "L3", cathode = "L2" }     # a part with two leads by the holes of its roles (decision 14)

[[wire]]
net = "GND"
path = ["N16", "AF16"]                      # a straight row of bridges, one per step (decisions 11, 16)
side = "bottom"

[[wire]]
net = "LED_Y2"
path = ["K10", "Q10", "Q8", "P8"]           # an insulated wire: its ends, and the bends between them
side = "top"
color = "yellow"
```

- **Holes** are written as the board prints them, even where a hole and a part share the string – R8 is a hole and a
  resistor. The lists say which is meant: "R5 330 Ω in holes R8–R4" (decision 13).
- **A part** sits by the hole of its pin 1 and a rotation, counterclockwise as seen from the top in steps of 90°, or,
  with two leads, by the holes of its roles (`anode`/`cathode`, `plus`/`minus`): edakit derives the rotation, and a
  part whose leads do not span the holes named is a finding. By role, a yellow LED with its cathode on pin 1 and a
  green one with its anode there read alike; by `rot` they need 270 and 90 (decision 14).
- **Mounting holes** are `[[holes]]` with `x`, `y` and `d` in mm, as in a PCB's board file: x to the right and y up
  from the board's lower left corner seen from the top, the corner half a pitch outside the outer holes. A frame's
  holes rarely meet the 2.54 mm grid – the bell's are 78 × 49 mm apart, the grid gives 76.2 × 48.3 – so they are
  drilled between the holes, and the pads under the nut stay free (decision 15).
- **Wires.** On the bottom there are only straight bridges of bare wire between neighbouring holes (decision 11): a
  path along one row or one column is a row of bridges, one per step, never around a corner. Rows meet at a lead or in
  the middle of another row (decision 16). Everything else is an insulated wire on top; each end goes through a free
  hole beside its pin and is joined to it by a bridge below, since a lead and a wire do not fit into one hole
  (decision 17). Wires may cross; their colours follow the net (supply red, ground black) unless the plan names one.

A kind with strips that are cut gets `cuts = [...]` in a section `[strips]` – not on the two kinds built first.

Pins a part joins inside – a module's two GND pins, a button's pins 1/2 and 3/4 – count as one node. The parts entry
says so with a key `joined = [["4", "29"]]`; a button's pins that share a role keep counting as joined, as handbook
4 has it (decision 18).

## What edakit checks

The plan is the layout of a hand-wired board; its checks belong where the layout's checks are.

- **The nets.** From the holes, the copper groups minus the cuts, the bridges and wires, the pins in the holes and
  the pins a part joins inside, edakit builds the nets the plan makes and compares them with the graph's nets of that
  board: a connection missing, two nets shorted, a pin in no hole, two pins in one hole. Where a hole joins two nets –
  a bridge, a wire's end, a lead –, the finding names that hole: that is where the soldering iron goes. The core of
  it – this is what goes wrong by hand.
- **Plugged-in modules.** What a module on sockets joins inside joins the nets, but not the board alone: pins that
  meet the rest of their net only inside it are a note, and the test list measures without it (decision 19).
- **The grid.** Every pad of a placed part lands on a hole, from the pads of its parts entry or the library cache. A
  part whose pins are off the 2.54 mm grid (a slide switch with terminals 2.0 mm apart, a terminal block at 3.5 mm) is
  an error beyond a tolerance that leads can be bent to, a value of the kind's data; within it a note (the bell's
  buttons, 6.5 × 4.5 mm on 7.62 × 5.08 mm: 0.63 mm). An SMD part is an error: a perfboard takes through-hole parts
  only (decision 3).
- **Bodies.** Body boxes (footprint outline, `body.box`) do not overlap and cover no other part's lead and no wire's
  end; an axial part's span is at least its body plus the bend of its leads; nothing reaches into the nut of a
  mounting hole. A module on sockets is raised: wires on top may run under it, a part under it is a note
  (decision 19).
- **Wires.** Bridges run straight: a corner within a row of bridges, or two rows ending at right angles in the same
  empty hole, is a finding naming that hole. An insulated wire ends in free holes; each wire has its length.
- **Current.** A wire, a bridge or a strip carries its net's current – from the simulation where it has one, against
  the wire's gauge and the copper's rating from the kind's data.
- **The hand-over.** `fixed`, `edge` and `near` hold as on a PCB: a connector at the edge, the decoupling capacitor
  within `near_mm` of its IC, measured as the gap between the bodies' boxes (decision 20).

## What edakit draws and writes

- **Top view:** parts with their designators and polarity (an LED's flat and "+", a capacitor's stripe, a header's
  pin numbers), insulated wires in their colours with dots where they enter the board, a module on sockets drawn
  see-through over the wires beneath it, hole names at the edges, the nuts of the mounting holes.
- **Bottom view in the orientation of the top view** (decision 12): seen through the board from above, A1 at the top
  left in both, so the two read alike. Soldered leads clearly stronger than empty holes, the bridges as bars coloured
  by net, a ring where a wire comes through from the top (strips and cuts on a kind that has them).
- **Build list:** the order of soldering from low to high – resistors, wires on top, sockets, buttons, connectors,
  diodes, capacitors, then the bridges once the leads they join are in, the test, the module last (decision 21) –,
  each with its holes and its polarity.
- **Cut list** (decision 22), lengths rounded up to 5 mm: the insulated wires by colour, each with its length and
  the 5 mm stripped at its ends, and the pieces of bare wire grouped by length, so the maker cuts each length in one
  go. A straight row of bridges is one piece, laid over the pads and soldered at each; a single bridge beside a wire's
  end is that wire's stripped end, bent onto the lead's pad, and no piece of its own (decision 23). The allowances –
  board thickness, stripped end, slack, bare wire beyond the outer pads, the step – are values of the kind's data. The
  bell: 8 wires (445 mm in seven colours) and 17 bare pieces (11 × 5 mm, 3 × 10 mm, one each of 35, 45 and 50 mm).
- **Test list for the multimeter**, with the module not plugged in: supply to ground first, with what it should read
  – the bell's +5 V to GND about 50 Ω through R8 ∥ R9 once C1 has charged, 0 Ω a short –; per net the holes that
  must beep, in groups where a net is joined only inside the module; next to each bridge the neighbouring pads of
  other nets that must not.
- **The order:** the board, the wire by colour and length from the cut list and the sockets as items off the board
  (`[[extra]]`, handbook 8.4), so `edakit order` puts them into the cart – and, once it is built, the parts on hand
  (`docs/concepts/done/parts-on-hand.md`) take what lies in the drawer off it.

The drawings are SVG, as `edakit schematic draw` writes them: on a white ground of their own, so they read alike in
the light and the dark theme of the site.

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
| LR.1 (the kinds) | `edakit/perfboards/pad-per-hole.toml` and `3-hole-strips.toml`: pitch, hole, pad, groups, sizes, bend tolerances and copper rating with their source | both read, a test per kind |
| LR.2 (plan and nets) | `[perfboard]`, `[place]` by pin 1 and by role, `[[holes]]` in mm, `[[wire]]` read from the board file of a board `wired = true`; the parts entries' `joined`; the nets the plan makes against the graph's, the hole where two nets meet | open, short, pin without hole, two pins in a hole, a part by role off its holes each a test |
| LR.3 (the other checks) | grid and bend tolerance, SMD, bodies and spans, a raised module, mounting holes, straight bridges and corners, wire ends, current, the hand-over's `fixed`, `edge`, `near` | a negative test each |
| LR.4 (drawings and lists) | top view, bottom view in its orientation, cut list, build list, test list for the multimeter, the board and the wire as `[[extra]]` | the prototype's drawings and lists, read in both themes |
| LR.5 (stage L) | the plan in the layout hash of a hand-wired board, stage L runs LR.2 and LR.3, the agent pcb-reviewer's M-5 on it (decision 4) | the gate of a variant passes and fails as it should |
| LR.6 (the round) | the skill pcb-round with the perfboard round, the handbook's section (7 or 4.5) | handbook and skill name the same keys |
| LR.7 (the examples) | a perfboard variant of coin-cell-led and of blinker-555, each with a plan the tests hold | both pass the gate |
| LR.8 (the bell) | a perfboard variant of the bell from its THT parts, in the bell's repository by its session, starting from the prototype's plan | the bell soldered on a perfboard from the plan |

## Decisions

The owner's answers of 2026-11-03 in a decision round, decisions 6 to 10 Claude's, confirmed by the owner the same day.
Decisions 11 to 23 came from the prototype on 2026-11-09: 11 to 15 and 22 the owner's, 16 to 21 and 23 Claude's,
confirmed by the owner the same day.

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
| 11 | On the bottom only straight bridges of bare wire between neighbouring holes, never around a corner; everything else an insulated wire on top | "auf der Oberseite mit Kabeln und auf der Unterseite mit kurzen blanken Brücken, die nebeneinander liegende Punkte verbinden … keine Kabel auf der Unterseite – wie löte ich die denn gut an?"; "eine Brücke unten muss gerade sein … wenn sie schon so verwinkelt ist, warum sie dann nicht kurz oben führen?" | bare wire on the bottom along a row of pads (the prototype's first version) |
| 12 | The bottom view in the orientation of the top view, soldered leads clearly stronger than empty holes | "das muss gleich orientiert sein wie top … sonst tut man sich beim Lesen schwer"; "Pins, die gelötet sind, deutlich stärker als geschlossenes Loch" | the bottom view mirrored, seen from below (the concept until then) |
| 13 | Holes written as the board prints them, even where a hole and a part share the string; the lists say "hole R8", "holes R8–R4" | the owner's choice in a decision round: the board's print is what the builder reads | a separator ("R-8"); lowercase columns ("r8") |
| 14 | A part sits by pin 1 and `rot`, or with two leads by the holes of its roles (`anode = "L3", cathode = "L2"`); edakit derives the rotation | the owner's choice: by `rot`, the bell's yellow LEDs (cathode on pin 1) and green ones (anode on pin 1) need 270 and 90 for the same orientation – the trap the PCB had | `at` and `rot` only; roles only for polarized parts with two leads |
| 15 | Mounting holes in mm only, as `[[holes]]` of a PCB's board file: x right, y up from the lower left corner seen from the top | the owner's choice: the bell's frame has its M3 holes 78 × 49 mm apart, the grid gives 76.2 × 48.3 | hole names or mm; hole names only, with a new frame |
| 16 | Straight rows of bridges are allowed; they meet at a lead or in the middle of another row, never at right angles in an empty hole | decision 11 read for buses: ground and +5 V of the bell are such rows | one wire on top from member to member |
| 17 | An insulated wire ends in a free hole beside its pin, joined to it by a bridge below | a lead and a wire do not fit into one hole | the wire's end soldered onto the lead's pad |
| 18 | Pins a part joins inside count as one node: a key `joined` in the parts entry, a button's pins that share a role as before | the Nano's two GND pins and the buttons' 1/2 and 3/4; a shared role alone would join the Nano's gpio pins too | the rule of the shared role for every part |
| 19 | A module on sockets is raised: wires on top may run under it, a part under it is a note; what it joins inside joins the nets but not the test list, which measures without it | the bell's five wires under the Nano; its LED cathodes reach ground only through the Nano's second GND pin | the module's outline as a body on the board |
| 20 | `near` measured as on a PCB, the gap between the bodies' boxes | the same hand-over as for a PCB (`box_gap` in `edakit/pcb.py`) | the gap between pads |
| 21 | The build list solders the bridges once the leads they join are in, after the parts, before the test and the module | a bridge joins the solder of a lead to its neighbour | bridges first, as links on a stripboard |
| 22 | A cut list: the insulated wires on top (coloured, may turn corners) and the bridges of bare wire below (straight), lengths in steps of 5 mm | "cool wäre es, wenn dann noch eine Stückliste für die Kabeln (farbige Ummantelung, können um Ecken gehen, Oberseite) und Brücken (blanker Draht, nur gerade, Unterseite) ausgegeben wird. Längen in gröberen Schritten (z. B. 5 mm)" | the wire's total length in the material only |
| 23 | A straight row of bridges is one piece of bare wire; a single bridge beside a wire's end is that wire's stripped end, no piece of its own; the allowances are values of the kind's data | one piece is cut and soldered faster than a row of short ones; the stripped end lies on that pad anyway | a piece per bridge; the bridge beside a wire's end as a piece of its own |

By the yardstick: nothing of the plan stays in someone's head – the board file holds it, edakit checks and draws it.
