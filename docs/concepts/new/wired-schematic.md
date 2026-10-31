# The schematic with every connection drawn through

Status 2026-10-31: concept, asked for by the owner – "a different way of drawing the schematics: today we have these
excerpts with named nets, which is what people who do this often use; the maker scene, for smaller circuits, prefers
a drawing as Fritzing draws it; it will reach its limits soon, let us see how far we get". Written against main at
`6139c4c`, the jukebox of anTONIEa at `63aa3b7` and the Christmas bell at `021f2ae`, with a prototype that draws
every project at hand this way and measures what it costs
([prototypes/wired-schematic](prototypes/wired-schematic/README.md)); checked the same day against main at
`b15a3ac` – L.1 to L.8 of circuit-language-plan built since (pins by name or role, the pin map from the parts entry,
the graph as TOML), the drawing code unchanged, the measures the same. Nothing of it is built in edakit; what the
owner asked for on the side the same day – the frame of the SVG optional – is built on the branch
`claude/friendly-carson-20hhbg` and waits for the OK. The decisions are at the end, open.

## The short answer

The drawing the owner means is Fritzing's schematic view: one sheet, every connection a wire from pin to pin, no net
labels, no power symbols, a colour per wire, the module with all its pins as the board shows them. edakit's drawing
is the other school: blocks with titles and notes, trees of parts on the pins of the modules, a labelled stub where a
net leaves the block, flags for ground and the supplies. The difference is not the parts or the arrangement – the
prototype keeps edakit's arrangement and only replaces the stubs and the flags by wires – but what a reader does: in
the wired drawing the eye follows the wire, in the labelled one it reads the name twice.

How far it goes was measured, not guessed. Drawn through, the bell (19 parts, 52 pin connections) has 5 crossings on
0.8 m of wire; the guitar boost pedal (19 parts) 1; the LED bar (17 parts, 61 connections) 12; the logic level
converter (14 parts, 40 connections, dense) 16 – all readable, each in under two seconds. The ESP32 DevKitC (33
parts, 157 connections, a module whose pins go to two 19-pin headers) is a mesh of 261 crossings, the Corne keyboard
half (73 parts, a key matrix) 221. The limit is not the number of parts: the Tubescreamer/Rat pedal with 86 parts
routes with 44 crossings. It is the structure – headers that mirror a module, buses, a matrix. A mixed style that
keeps the labels for those nets and wires everything else brings the DevKitC to 28 crossings and leaves the matrix
unreadable (155). So the proposal is a third style beside the two, chosen per board by what the drawing measures
about itself, and overridable by a key: wires through for the maker-size circuit, labels for the pass-throughs and
buses, today's drawing for the rest. It is one plan drawn three ways – the SVG, EasyEDA's board schematic and the
KiCad schematic all draw the same plan –, so the style reaches all of them.

Everything stays text in the repository: the style is a key of the schematic file, the drawing is generated from the
graph and regenerated on every change, nothing lives in a drawing tool. An export to Fritzing, which would give its
breadboard view and its part pictures, is set aside: a file edited there holds what the repository does not.

## What the owner means

Two drawings of the owner's, both made by hand in Fritzing:

- **The jukebox** (anTONIEa, `hardware/circuits/tinyjukebox.fzz`, its picture `tinyjukebox_circuit.png`): a
  Raspberry Pi Zero as a box of 40 pins, each named "BCM 17", "Ground", "3V3 Power"; an RFID reader, an amplifier
  with its speaker, four buttons with their pull-ups, an RGB LED with a transistor, a power bank with a switch. 22
  parts, 124 wire pieces in the schematic view (every bend is a piece of its own in Fritzing's file), ten wire
  colours, values at the resistors, no net name anywhere, 3V3 and 5V drawn as wires like everything else.
- **The bell's original** (`docs/old/weihnachtsglocke_Schaltplan.png` of the bell's repository, before edakit): the
  Nano as a box with every pin named as the board prints it – D2 … D13/SCK, A0 … A7, 5V, 3V3, GND –, five LED
  steps, two buttons, the servo as a three-pin header named gnd/Vcc/pulse, the LEDs with colour and wavelength.
  5V and GND run as long wires around the drawing.

What the two have in common, against edakit's drawing of the bell (handbook 6.5, 20 wires, 19 flags, two blocks and
a notes block on 254 x 272 mm):

| | Fritzing's schematic view | edakit's drawing |
| --- | --- | --- |
| a net | one wire, from pin to pin, with bends and junction dots | a wire inside a block; a labelled stub to another block; a flag for a power net |
| ground, supply | wires like any other, often a long one around the sheet | ground symbols and supply flags at every pin |
| the module | every pin, as the board shows them, the unused ones too | the connected pins only, as on a DIP package |
| pin names | the board's print (D2, BCM 17) | the symbol's (PD2 – the Nano's library symbol names the ATmega ports; handbook 6.2: names follow the symbol) |
| colours | a colour per wire, chosen by hand | one colour for every wire |
| structure | none: one sheet | blocks with titles and notes, a GPIO table |
| who draws | a person, with the mouse | the graph, in a second |

The first three rows are what the owner calls the Fritzing style. The fourth is a data question of its own (the
parts entry has no print name per pin; decision 6 of
[circuit-language.md](../done/circuit-language.md) kept aliases out of the graph's form – the drawing is another
matter). The last row is the one edakit must keep: a drawing nobody draws by hand.

## Where it would be used

- **`edakit schematic draw`**, the drawing without EasyEDA (6.5): the skills circuit-design and hardware-change show
  it to the user after every change ("the circuit as a drawing for the user to look at"), new-project names it as
  the end of a project without a PCB, the walkthrough embeds it in the README (17.8), and the catalog draws every
  reference circuit and every block with it (`docs/catalog/build.py`) – all of them maker-size.
- **A hand-wired board** (`wired = true`, 4.5): panel parts, jacks, pots, a strip on a cable. edakit refuses to draw
  it today ("has no schematic", 6.5) – though it is the one board whose only build document is a drawing of what
  goes to what. The guitar pedals' `wiring` boards are the case: 4 and 7 parts, 14 and 26 connections.
- **The board schematic in EasyEDA** (`schematic layout`, 6.3) and **the KiCad schematic** (16.3): both are drawn from
  the same plan as the SVG (`schematic_layout.Layout`, `schematic_draw.drawing`); the style reaches them once the
  plan has it, with one probe each (below).
- **Not** the template schematic (`schematic create`: stubs with net labels, "exact, ugly", rebuilt on every run) and
  not the reference project with 123 parts: that one is what labels are for.

## What exists

**In edakit.** The plan (`schematic_layout.py`): blocks from `[layout] rows` of the schematic file or, without it,
one block per module, IC, connector, relay and battery holder, power inputs first; inside a block, parts attach to
the pins of the block's start part by breadth-first search over the signal nets, every child turned so that its pin
points at the parent's, stacked and spread without overlaps; a pin whose net goes on elsewhere ends in a stub of the
net's name, a power net in a flag. The drawing (`schematic_draw.py`): the symbols from the parts database, the page,
the title block, the check that no wire touches another net or a foreign pin and that every connected pin ends in a
wire or a flag. EasyEDA's `SCH_PrimitiveWire.create` refuses a crossing with four branches (6.3), and the geometry
check takes two nets' wires touching for a short – a crossing without a junction, which the wired style lives on,
is not told apart from a T today.

**Fritzing.** The app's source is GPL v3, its documentation and part designs CC BY-SA 3.0 (the repository's README;
the parts repository's licence file says "all graphics and documentation"). A `.fzz` is a zip with one XML file:
instances of parts by module id with a position per view – breadboard, schematic, PCB – and wires as instances of
their own, one per straight piece, with a colour; the jukebox's modules without a Fritzing part are "mystery parts",
a SIP of n pins with a label. Nothing of this reads a hardware graph; fritzing.org was not reachable from this
session, so its current version and its documentation were not read.

**The other school.** EasyEDA and KiCad draw either way: a wire is a wire, a label joins what has the same name, a
junction dot says that crossing wires connect. The labelled drawing is what edakit generates today; the wired one is
the same editors' other mode.

## The prototype

`prototypes/wired-schematic/wired.py` takes edakit's plan and draws it through. It changes nothing in edakit:

- a pin without a child gets a lead of one grid cell instead of a labelled stub, a power net no flag; the blocks
  stand twice as far apart – the gaps are the channels – and lose their frames;
- a module shows every pin, as on the board, the unused ones grey;
- a router on the schematic grid (10 mil x 10, 2.54 mm cells) joins every net: the ground along a rail below the
  drawing, the supplies along rails above, the rest by the cheapest path – a step 1, a bend 4, a crossing of another
  net 12, running beside one 1; never through a part, never along another net's wire, never through its ends, bends
  or pin tips. A rail that gathers fewer than two drops is taken away again;
- every net gets a colour – ground black, supplies red – chosen so that nets that cross or run side by side differ
  where ten colours allow it;
- the mixed style (`--mixed`): a net stays a labelled stub when nothing but modules, ICs and connectors hang on it –
  a pin passed through to a header, a bus line – or when it has six pins or more – a key matrix, a shared line;
- it measures: wire length, crossings, bends, pieces it could not join, colour clashes, page size, time.

The measures of every project at hand, both styles, are the table of its README. The short of it:

| board | parts | pin connections | crossings, wires through | crossings, mixed (nets labelled) | wire m | page mm |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| coin-cell-led | 4 | 8 | 0 | 0 (0) | 0.0 | 122 x 95 |
| the bell | 19 | 52 | 5 | 2 (1) | 0.8 | 221 x 213 |
| boost pedal, main | 19 | 32 | 1 | 1 (0) | 1.0 | 355 x 283 |
| boost pedal, hand-wired | 4 | 14 | 1 | 1 (0) | 0.5 | 203 x 179 |
| logic level converter | 14 | 40 | 16 | 11 (1) | 1.3 | 188 x 245 |
| LED bar | 17 | 61 | 12 | 7 (3) | 2.2 | 185 x 343 |
| ESP32 DevKitC | 33 | 157 | 261, 4 unrouted | 28 (31) | 10.4 / 4.4 | 409 x 431 |
| Corne v3, left half | 73 | 219 | 221 | 155 (33) | 19.8 / 10.8 | 655 x 739 |
| Corne, left half | 84 | 301 | 227 | 73 (36) | 25.3 / 11.6 | 719 x 982 |
| TS/Rat pedal, main | 86 | 181 | 44 | 44 (2) | 11.1 | 856 x 586 |

What the drawings show (the README has them; the bell three ways – Fritzing's, edakit's, the prototype's):

1. **Maker-size circuits come out readable, unaided.** The bell's drawing is the owner's old one with the rails
   outside: LED steps on the Nano's left, the buttons with their pull-downs below, the servo and its capacitor on
   5V. Nothing was tuned per project – the same code draws the pedal, the LED bar and the coin cell.
2. **The limit is the structure, not the count.** A hub with chains of passives on its pins routes at 86 parts; a
   module with headers that mirror its pins, or a matrix, does not route at 33. The measure that says so is the
   number of crossings against the number of nets: below one per net the drawing reads, at five per net it is a
   mesh. The DevKitC's four unrouted pieces are the same thing: no channel was left.
3. **The mixed style is the natural middle.** Labels for the nets that are nothing but pass-throughs and buses, wires
   for the circuit around the module: 31 of the DevKitC's 48 nets are labelled and the rest draws through. A key
   matrix stays a mesh either way – it wants a drawing of its own kind (rows and columns as buses), which is the
   labelled style.
4. **Placement decides the rest.** The prototype keeps edakit's arrangement – blocks in rows – so every wire between
   blocks goes around; a module in the middle with its neighbours by connection would shorten the long loops of the
   LED bar and the level converter. The numbers of the table are an upper bound.
5. **The page does not grow.** The wired bell is 221 x 213 mm against edakit's 254 x 272 (the notes block is gone),
   the DevKitC 409 x 431 against 404 x 389. Wire length is the cost: 0.8 m for the bell, 10 m for the DevKitC.
6. **A hand-wired board draws like any other** – the prototype does not go through the board filter that refuses it.

What it does not do: the pin names (the symbol's), the notes and the pin table of the schematic file, the check of
the drawing, speed (half a minute for a keyboard half in plain Python).

## What to build

One plan, three styles, chosen per board. The style is data – a key of the schematic file, as the add-feature skill
asks –, and without the key the drawing chooses by its own measure and says so in its output line.

| step | what | where | size (estimate) |
| --- | --- | --- | --- |
| W.1 | **The frame optional.** `--no-frame`, or `frame = false` in the schematic file: no sheet border, no title block, the page the drawing and its margin – for a drawing embedded in a document. | `schematic_draw` (`fit`, `render`), `config.SCHEMATIC_KEYS`, `cli`, a test, handbook 6.5 and 10.3 | built on the branch, 30 lines |
| W.2 | **The wired style in the plan.** `style = "wires" \| "mixed" \| "labels"` in `hardware/schematic.toml`; the leads, rails, router and colours of the prototype as part of `schematic_layout`/`schematic_draw`; the geometry check learns to tell a crossing from a T; the output line reports crossings and wire length; the measure chooses without the key (crossings ≤ nets: wires; else mixed if that gets there; else labels), and the title block names the style. A hand-wired board is drawn (`made=True` of `schematic draw` goes). Tests on led-bar and the bell's graph; the catalog's reference circuits drawn through where the measure allows. SVG only. | `schematic_layout.py`, `schematic_draw.py`, `config.py`, `cli.py`, `tests/test_schematic_draw.py`, handbook 6.5, 10.3, 14.5 | ~500 lines with tests, one session |
| W.3 | **Placement for wires.** The module in the middle, the other blocks around it by the nets they share, channels as wide as the wires that must pass; the prototype's table as the test – fewer crossings, less wire, no bigger page. | `schematic_layout.py` | ~200 lines, one session |
| W.4 | **EasyEDA and KiCad.** Probe on a scratch sheet (agreement 18): two wires of different nets crossing without a junction stay two nets after `SCH_PrimitiveWire.create`, save and reload (6.1 saves only a netlist equal to the graph – the safety net); then `schematic layout` takes the style key; the KiCad schematic gets the same plan through `drawing()`, its ERC and the netlist compared by SYNC.schematic (16.6). **(probe)** | `schematic_layout.apply`, `toolchain/kicad/schematic.py` | half a session plus the owner's EasyEDA |
| W.5 | **Pin names as the board prints them.** A key per pin of a module's parts entry – `"print": "D2"` – that the drawing writes beside the symbol's name, nowhere else; the Nano's and the Pico's entries get them from their pinout pages; `edakit part lint` holds the key to the schema. | `catalog/kinds.toml`, `schematic_draw.box`, the entries, handbook 4.1 | 50 lines plus the data |
| W.6 | **The breadboard or perfboard view.** The physical drawing Fritzing is known for: THT parts and modules on a 2.54 mm hole grid as their footprint outline with pads (the data is in the parts entries and footprints, 4.1, 4.5), wires as straight lines from hole to hole, a colour per net; for a hand-wired board and for a THT variant like the bell's; SMD parts have no place on it. A placer of its own on the grid, a wire drawer, a check (one wire per hole, every pin in a hole) – the size of `schematic_draw` again. | new module | ~700 lines, two sessions; deferred |
| – | **Export to Fritzing.** Set aside: it needs a Fritzing part per edakit part (the core library's generic parts would do for resistors, LEDs, buttons, transistors and "mystery" modules, not for the boards), and a file edited in Fritzing holds positions and bends the repository does not – against the yardstick of design as text. Revisit if a project needs Fritzing's part pictures. | – | – |

Order: W.1 is done; W.2 and W.3 together give the owner the drawing; W.5 is independent and small; W.4 when the
owner's EasyEDA is at hand; W.6 only when a hand-wired project asks for it.

## Costs and risks

- **A crossing taken for a connection.** The convention – a dot connects, a crossing does not – is every editor's,
  and the wired style multiplies crossings. The router keeps crossings away from ends, bends and pin tips, the
  drawing dots every junction; the geometry check of W.2 refuses a crossing at a junction. Likelihood of a misread
  by a reader: low with the dots; cost: a wrong assumption while hand-wiring, caught by `edakit check` only if the
  wrong wire is also in the graph – it never is, the graph is the source.
- **A drawing nobody can improve by hand.** As today: whoever wants a different arrangement changes the schematic
  file (`rows`, `near`, `style`), not the drawing. For the wired style the file gets no new way to pin a wire's
  route – a route by hand would be the one thing outside the generator.
- **Time.** The prototype's router is plain Python: a second for the bell, a minute for a keyboard half. W.2 keeps
  the grid but drops the per-cell dicts for arrays; the measure that chooses the style runs the router once.
- **Taste.** Which style a reader prefers is theirs; the key decides per board, the default by the measure. The
  catalog pages would mix styles across circuits – acceptable, each reads best its own way.

## Decisions

Open; the recommendation first, as the skill decision-round asks them.

| # | Question | Recommendation | Alternative | Status |
| --- | --- | --- | --- | --- |
| 1 | Build the wired style as a third style of the one plan (W.2, W.3)? | Yes: the measured drawings of the maker-size circuits read as the owner's old ones, and the plan reaches SVG, EasyEDA and KiCad alike | a separate drawer for the SVG only – less code, and the board schematic in EasyEDA stays labelled | open |
| 2 | How is the style chosen? | By the measure after routing when the schematic file says nothing – crossings against nets –, `style` in the file overrides; the output line and the title block say which | always labels unless the file says otherwise – predictable, and every maker project has to set the key | open |
| 3 | Pin names as the board prints them (W.5)? | A `print` key per pin in the parts entry, drawn beside the symbol's name, used nowhere else – decision 6 of circuit-language.md stays (the graph names pins as the symbol does) | leave it: the symbol's names and a note, as the bell has today | open |
| 4 | A hand-wired board gets the drawing? | Yes, in W.2: the board filter of `schematic draw` is the only thing in the way, and the drawing is that board's build document | – | open |
| 5 | The breadboard or perfboard view (W.6)? | Later, when a hand-wired or THT project asks; the wired schematic covers "what goes to what", the physical view is a second drawing of the size of the first | now, together with W.2 | open |
| 6 | An export to Fritzing? | No: a second drawing tool, a part mapping to maintain, and a file whose hand edits live outside the repository | an export that is only ever generated, never edited | open |

## Sources

- edakit at `6139c4c`, checked at `b15a3ac`: [schematic_draw.py](../../edakit/schematic_draw.py), [schematic_layout.py](../../edakit/schematic_layout.py)
  (`Layout`, `Drawing`, `check_geometry`, `apply`), [toolchain/kicad/schematic.py](../../edakit/toolchain/kicad/schematic.py)
  (`write`, the global labels from `net_labels` and the flags), [config.py](../../edakit/config.py) (`SCHEMATIC_KEYS`,
  `Config.board(made=True)`), [docs/catalog/build.py](../catalog/build.py), handbook [6](../../handbook/06-schematic.md)
  (6.2 names follow the symbol, 6.3 `SCH_PrimitiveWire.create` and four-branch crossings, 6.5), [4.5](../../handbook/04-parts-database.md)
  (hand-wired boards), [10.3](../../handbook/10-reference.md), [16.3](../../handbook/16-kicad.md), [17.8](../../handbook/17-walkthrough.md),
  skills [circuit-design](../../skills/circuit-design/SKILL.md), [hardware-change](../../skills/hardware-change/SKILL.md),
  [new-project](../../skills/new-project/SKILL.md), [.claude/skills/add-feature](../../.claude/skills/add-feature/SKILL.md)
  ("prefer data over options"); the open designs and fixtures under `tests/` as the measured projects.
- The prototype and its measures: [prototypes/wired-schematic](prototypes/wired-schematic/README.md).
- anTONIEa at `63aa3b7`: `hardware/circuits/tinyjukebox.fzz` (read as XML: 22 parts, 124 wire pieces in the
  schematic view, ten colours, the mystery parts), `tinyjukebox_circuit.png`, `hardware/README.md`.
- The Christmas bell at `021f2ae`: `docs/old/weihnachtsglocke_Schaltplan.png` and `weihnachtsglocke.fzz`,
  `hardware/graph.json` (19 parts, 15 nets, 52 pin connections), `hardware/schematic.toml`; converted to the current
  form of the graph in a scratch copy for the prototype (`edakit convert --write`), the repository untouched.
- Fritzing: the READMEs of `github.com/fritzing/fritzing-app` and `fritzing-parts` and the latter's `LICENSE.txt`,
  read through the session's proxy on 2026-10-31; fritzing.org did not resolve from the session.
