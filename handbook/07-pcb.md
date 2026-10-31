# 7 PCB (stage L)

The PCB is generated in layers: parts and nets from the board schematic (without dialogs), a **placement plan** for
everything that matters (in the board file `hardware/boards/<name>.toml`, 10.2), EasyEDA's auto-layout for the rest –
its positions go into the plan as well (7.4) –, **Freerouting** for the tracks, pours, silkscreen. Every step can be
repeated; every step checks itself.
A bought board on a cable (`bought = true`) or a hand-wired one (`wired = true`, 4.5) has no PCB: `pcb`, `route`,
`silk`, `fab` and `export` refuse it with one line when `--board` names it, and without `--board` take the one made
board; `handover` and `export` over all boards leave it out.

```bash
edakit handover              # what the circuit hands over: state, sign-offs, what the plan must keep (14.1)
edakit pcb parts --write     # parts of the board schematic -> PCB (no "Import Changes" dialog)
edakit pcb dump              # footprint geometry -> hardware/boards/<board>.geometry.json, beside the board file
edakit pcb plan              # offline: check the plan, preview PNG, net classes, mechanical model
edakit pcb place --write     # offline: decoupling capacitors, pull and series resistors next to their host
edakit pcb apply             # outline, holes, tooling holes, fixed parts locked; pads verified
edakit pcb autolayout        # the parts without a row; once they stand still, their rows into [place]
edakit route all             # Freerouting -> EasyEDA, pours, reload, DRC (exit 0 = DRC 0)
edakit silk apply            # designators where there is room, silkscreen check on the Gerber, DRC
```

## 7.1 Coordinates

- **Plan** (board file): mm, any origin you like, seen from the board's `view` side. `side` of a part is the EasyEDA
  side it sits on (`top`/`bottom`).
- **EasyEDA:** mil, y up, seen from the top. With `view = "bottom"` edakit mirrors x and turns rotations into
  180° − rotation – useful when the side people look at is the bottom (e.g. LEDs on the bottom, electronics on top,
  because EasyEDA's auto-layout only places on TOP).
- **Footprints on the bottom:** EasyEDA mirrors the local y of a footprint, then rotates. `Board.transform` does the
  same, and `pcb apply` compares the pads EasyEDA reports with the plan (largest deviation must be < 0.05 mm) – one part
  per footprint, side and rotation, or all with `--verify-all`.

## 7.2 Outline, holes, tooling holes

```toml
[outline]
rect = [90, 40]            # or polygon = [[x, y], …] (only straight segments; arcs as point lists)
corner_radius = 2

[[holes]]                  # non-plated mounting holes, drawn as circles on the outline layer
x = 3.5
y = 3.5
d = 3.2
keep = 3.2                 # radius free of parts and copper (screw head)

[tooling]                  # JLCPCB Economic PCBA tooling holes
holes = [[3.5, 36.5], [86.5, 3.5]]
```

**Tooling holes:** JLCPCB's Economic assembly wants 2–3 non-plated holes of 1.152 mm with the solder mask 0.148 mm
larger, in opposite corners. Without them JLCPCB drills its own – maybe somewhere visible. edakit creates them as free
pads without copper ring (they land in the NPTH drill file). Two EasyEDA quirks: while a free pad is in the PCB, pour
fills fail – edakit takes them out before every fill and puts them back; and a pour polygon with a hole is not filled –
the pour gets a notch from the edge around each tooling hole instead.

## 7.3 Parts and nets without dialogs

`PCB_Document.importChanges` always opens EasyEDA's confirmation dialog. edakit does the same through the API:

- **`pcb nets [--write]`** sets every pad's net to the graph (`PCB_PrimitivePad.modify`). Enough for pure net changes.
- **`pcb parts [--write]`** compares the board schematic with the PCB: missing parts are created from the project
  library, swapped ones (other LCSC number or footprint) replaced, extra ones deleted, unlinked ones linked (the link is
  the UniqueId shared by schematic and PCB part), and properties copied **from the schematic** (otherwise the DRC still
  reports "Netlist Error"). New parts are parked next to the board (`park`), their geometry is measured, pad nets set,
  PCB and schematic saved.

**Before a swap** – another part for the same place, because the old one is out of stock or not in JLCPCB's library –
`edakit part diff OLD NEW` (LCSC numbers or parts-entry keys) compares the footprints without EasyEDA. The geometry is
the dump of a placed part, else the footprint data of the parts entry (4.5), else the library footprint of
`edakit part import`. Pads are matched by position only: for
each turn of 0, 90, 180 and 270° on the same side, and for the mirror image (the other side), the nearest assignment
after laying origins and centroids on each other, with the shift that lays the assigned pads over each other best. A
turn fits when every pad of OLD lies on the copper of its new pad (shape, size and rotation from the library; for a
dump without pad sizes within half the smallest pad distance). Every other fit within 0.05 mm RMS of the best one
with another map is reported – "symmetric: the numbers decide". The report:

- the turn and shift that lay NEW over OLD, the residual per pad, whether the mirror image fits as well – or "mirror
  image only – not on the same side", or "no turn fits"
- the map old → new by position, the roles of the two entries that change under it (`old 1 throw_a → new 3 throw_b`)
- the pitch per row, the hole or slot per pad old → new, and with `lead` in NEW's entry GEO.hole's verdict (`hole_ok`) and
  the 0.5 mm minimum for plated slots; the box w × h old → new
- the graph change it implies for every component that uses OLD (`SW5: BAT_SW 1 → 3`)

Exit 0 is a drop-in – same side, 0°, every pad keeps its number and role, holes fit (a shift is reported, the plan
moves the part); 2 is something to decide. It writes nothing but `--json F`. The reference project's slide switch
(XUNPU SS-12D11G9 for G-Switch SS-12D11-G090) gives: turned 180°, the mirror image fits equally (symmetric), map
1→3, 2→2, 3→1, 4→4, 5→5, pitch 4.70 → 4.80 mm, the 0.40 mm tab slots below 0.5 mm, `SW5: BAT_SW 1 → 3` – what took
an hour with both datasheet drawings and was first described as a turn when it is a mirror image.

The same matching of a board footprint against itself is GEO.formed (3.3): when the project's footprint moves holes away from the library's – leads formed for the board, a part fitted by hand – `edakit check` fails if a turn of 90°, 180° or 270° lays the formed holes onto themselves with a pin in another net's hole. Offset the leads so that none does: two in opposite directions, one only, or by different amounts.

A new project comes with one empty default board (Board1 = Schematic1 + PCB1). The first `edakit schematic layout`
renames it to the board of edakit.toml (board name, `schematic`, `pcb`) and fills the schematic from the graph; any
other board setup is left alone and must match edakit.toml.

One case remains: when a part was freshly placed in the schematic from the library, the DRC shows "Netlist Error –
Import Changes" until the import view was opened once in the GUI. That is the one click to ask for (start skill,
section 3).

## 7.4 The placement plan

```toml
[place]                  # hardware/boards/main.toml
U1 = { x = 29, y = 14.5, rot = 0, side = "top" }
J1 = { x = 84, y = 12, rot = 90, side = "top" }

[near]                   # the layout's own: fixed parts within near_mm of the host
C2 = "U1"
```

Fix everything the auto-layout must not decide: connectors and anything at the edge, controls, ICs with their
decoupling capacitors and pull resistors, LEDs and anything visible, parts with mechanical constraints. EasyEDA's
auto-layout places only unlocked parts, only on TOP, and knows nothing about belonging – it once put a decoupling
capacitor 24 mm from its IC. That is why `near` holds only between fixed parts: an entry for a part the auto-layout
places is a finding – `edakit pcb place` (below) gives such a part a spot next to its host.

**Geometry.** The plan works with footprint boxes and pads relative to the part origin: from `edakit pcb dump` once the
parts are in the PCB – the project's footprints as placed – and, for a planned part that is not in the dump yet, from
the footprint data of its parts entry (4.5), else from the library footprint `edakit part import <LCSC>` cached (4.2):
`pcb plan` names those parts ("footprint data of the parts entry", "library geometry") and takes their pad nets from
the graph. The dump wins. The dump keeps the hole of every through-hole pad (`hole` [w, l] in
mm, `plated`), and `pcb plan` runs GEO.hole on the plan's geometry: a hole that does not take its lead is a plan finding
(`GEO.hole D31 (pads 1, 2, 3, 4, library geometry …): hole 0.70 mm for diagonal 0.71 mm …`), a tight hole or a missing `lead`
is printed. A geometry file from before has no holes – dump again (it changes the layout hash once). Library and EasyEDA
Pro agree on the pads within 0.1 mil (eleven footprints of the reference project; one switch 1 mil); the boxes differ by
up to 0.3 mm, because EasyEDA Pro measures the silkscreen of the placed part. Without a dump and without a cached
footprint a planned part stays a finding.

The dump of a part whose parts entry has footprint data (4.5) gives every pad its shape, size, rotation and layer as
well (`shape`, `w`, `h` in mil, `rot`, `layer`, the form of the library cache), so that SYNC.footprint holds the copy to the
data; every other part is measured as before, and its lines in the file stay as they were.

The dump lies beside the board file, with its name: `hardware/boards/main.toml` has `hardware/boards/main.geometry.json`.
It is versioned with the board file and in the layout hash (8.2), so CI and a fresh clone have it – GEO.hole and GEO.formed judge
the project's footprints there too, and the layout hash is the same. Commit it with the board file. Until October 2026
`pcb dump` wrote it among the artifacts, `<artifacts>/pcb_geometry_<board>.json`, which are not versioned. Such a file
is still read – by the plan, the checks, stage L and the layout hash – until it is moved, and `edakit check` (a note to
GEO.hole), `pcb plan` and the gate say how:

```text
NOTE    GEO.hole  build/edakit/pcb_geometry_main.json: footprint geometry of board main among the artifacts, which are not
             versioned – move it beside the board file and commit it: mv build/edakit/pcb_geometry_main.json
             hardware/boards/main.geometry.json (the layout hash changes once, sign-offs with scope 'layout' lapse)
```

`pcb dump` moves it as well, and so does `pcb parts --write` when it measures new parts. When both files exist, the
one beside the board file counts.

**What the circuit hands over** (SYNC.plan) comes first. The circuit designer writes it into the graph, the PCB designer
keeps it (14.1); `edakit handover` lists it:

```json
"layout": {"fixed": ["SW1", "D2"], "edge": ["J1"], "near": {"R1": "U2"},
           "loops": [{"a": "C5.1", "b": "U3.2", "max_mm": 8, "what": "buck input loop"}],
           "notes": ["D2 to D9 form the bar: one row, in this order"]}
```

`fixed` parts need a position in `place`; `edge` parts also a box within `edge_mm` of the outline (default 1 mm);
`near` parts sit within `near_mm` of their host. Every IC with a supply pin gets a capacitor of its own from that
supply to ground within `near_mm` – derived from the graph, matched one capacitor per IC, so two ICs cannot share one
while another sits far away; an IC whose capacitor is elsewhere on purpose carries `accept: {"SYNC.plan": "…"}`. `loops`
join the board file's `[[loops]]` for GEO.loop on the routed board – REQ.missing wants one on every net of a switching
regulator's hot loop (its `hot_loop` pins and the net behind its diode), and `notes` are for the PCB designer and the
layout review. A requirement the plan cannot keep goes back to the circuit as a written request – the layout does not
change the graph.

`edakit pcb plan` checks offline: overlaps per side (under a module on pin headers only its pins, SMD parts within a
silkscreen tolerance: below), outline (0.3 mm margin; `edge_ok` for connectors), keep-outs of holes and tooling holes,
THT pins of one side under parts of the other, `near` distances, the circuit's layout requirements (SYNC.plan), **polarised
parts that point the same way** – by default LEDs side by side with their anode towards the same side (below) –,
**mated plugs** clear of the other parts and out through the outline (below); it prints the airline length of the
fixed parts (a number to compare placements) and writes `<artifacts>/pcb_plan_<board>.png` and the mechanical model
`<artifacts>/mech_<board>.json`. Look at the picture before `apply`.

**Polarised parts in one direction.** Whoever solders a bag of LEDs, diodes or buzzers by hand turns each one by its
"+" mark or flat side and should not have to turn every other one – the library footprints of one LED series may even
put the mark on different pads. `uniform` in the board file says, per `kind` of the parts entry, how the parts of that
kind are turned. The direction is read from the pin roles: the pin `anode` or `plus…` against the pin `cathode` or
`minus…`; a part with not exactly one of each (an RGB LED, a holder of several cells) is skipped, and `pcb plan`
names it once. `"row"` compares parts of the kind side by side on one side of the board (centres on one line within
1 mm, rows and columns): the plus pins point towards the same side. A direction – `"+x"`, `"-x"`, `"+y"`, `"-y"` in
plan coordinates – holds for every part of the kind on the whole board, alone or in a row: its cathode or minus pin
points that way, seen from the side the part sits on (a part on the other side than `view` is seen mirrored in x).
Without the key it is `{ led = "row" }`; a table names every kind it checks, so a table without `led` leaves the LEDs
alone. `pcb place` takes the check like every other: a part it places gets a rotation that keeps it.

```toml
view = "bottom"                                # the LED side is the front
uniform = { led = "+x", buzzer = "-x" }        # every LED cathode right seen from the front; the buzzer (on the
                                               # back) plus right seen from the back, its minus left
```

A part that points elsewhere reads `BZ1 (buzzer): minus points +x, uniform -x – turn it by 180° (rot = 0)`, with the
rotation for `[place]`; a row `diodes in a row (D2, D3): cathode of D3 points the other way than D2 – turn it by 180°`.
LEDs in a row keep their words: `LEDs in a row (…): anode of D3 points the other way than D2 – turn them by 180°`.

**Parts under a module on pin headers.** A module that stands on pin headers – a Pico, an RP2040-Zero – leaves the
board under it free but for the plastic of its headers. `on_headers` names such parts. An SMD part of the same side
may then sit under one, as long as its box stays `header_keep_mm` (1.27 mm, half the 2.54 mm pitch) clear of every
through-hole pin of the module, measured from the pin centre as a square. A through-hole part under it stays an
overlap; a part on the other side over its pins stays a finding (THT pins underneath). The boxes are the footprints'
bounding boxes from `pcb dump`, silkscreen included, so a project may set the keep-out smaller by its silkscreen
margin. Height is not checked: what sits under the module has to be lower than its headers lift it.

```toml
on_headers = ["U1"]          # in hardware/boards/<b>.toml, above the tables
header_keep_mm = 1.27        # the square around each through-hole pin of U1 that SMD parts stay out of
```

A part too close reads `D1: on the pins of U1 (top) – 0.00 mm from pin 5 (header_keep_mm 1.27)`: the gap between its
box and the nearest pin centre. An `on_headers` part whose footprint has no through-hole pins is a finding of its
own, and its overlaps count as usual.

**Silkscreen tolerance.** Because the boxes include the silkscreen, two small SMD parts whose pads lie well apart are
an overlap as soon as their printed outlines touch – a decoupling capacitor close to its IC, a base resistor next to
its transistor. `silk_overlap_mm` lets the boxes of two SMD parts of one side reach that far into each other. Per axis
the plan check measures how far one box has to move to clear the other; the pair is a finding only when both x and y
are beyond the tolerance. For parts side by side that is the width of the strip they share; a small part inside a
larger box lies as deep as its way out, so the tolerance does not hide it. If either part has through-hole pads, the
tolerance does not apply. Under a module in `on_headers`, its pins decide (above). The default 0 keeps every overlap a
finding. Keep the value within the silkscreen margin of the footprints in use: the pads themselves are not compared
here, but by `route check` and the gate – the clearance (GEO.spacing) and, on an assembled side, the paste gap (GEO.spacing, 7.5).

```toml
silk_overlap_mm = 0.8        # in hardware/boards/<b>.toml, above the tables
```

With the key, an overlap gives its depth: `R1 / R2: overlap (top) – 1.00 mm (silk_overlap_mm 0.8)`, or
`J1 / C1: overlap (top) – 0.30 mm (J1 through-hole: silk_overlap_mm does not apply)`.

**Mated plugs.** A connector's footprint box ends where the plug begins: the plug with its strain relief or overmould,
and the cable behind it, need room the footprint does not show. The parts entry of a connector can carry its mated
plug (`mate`, 4.1): a box in footprint mm, its height and the direction the cable leaves it. `pcb plan` turns and
places the box with the part and checks, for every placed part with `mate`:

- the plug runs into no other part's box on its side – into an SMD part's box at most `silk_overlap_mm`, as two SMD
  boxes may (the plug is a body without silkscreen, the other box has its margin) – and into no other part's plug
- a plug whose cable leaves sideways (`+x`, `-x`, `+y`, `-y` in footprint coordinates) reaches the outline in that
  direction, measured from the middle of its far end: a cable that leaves across the board is a finding

`edge_ok` lifts neither: it lets the connector's own box touch or overhang the outline, nothing more. A plug whose
cable is bent away from the board right behind it is `exit = "+z"`, with the bend in its box; then only the first
check applies.

```json
"mate": {"box": [-2.5, -6.6, 2.5, -4.6], "h_mm": 5.0, "exit": "-y"}
```

A finding reads `J1: mated plug reaches into U2 (top)` – with `silk_overlap_mm`, how deep: `J1: mated plug reaches
into D32 (top) – 1.01 mm (silk_overlap_mm 0.8)` –, `J1: mated plug reaches into the mated plug of J2 (top)`, or
`J1: mated plug leaves towards -x but ends 69.8 mm inside the outline` (a plan direction). A `body`, `lead`
`length_mm` or `mate` that is not as 4.1 says is named with its parts entry. Without `mate` nothing changes.

**The mechanical model.** `pcb plan` writes `<artifacts>/mech_<board>.json` on every run, for the project's own
mechanics check (a `[scripts.<name>]` of kind `check` or a `[[release.stages]]`, 8.1) and its enclosure scripts – they
read the board from it instead of keeping the part boxes, heights, plug sizes and the board thickness as constants of
their own. Plan coordinates in mm, as seen from `view`:

| Key | Content |
|---|---|
| `board`, `units` (`"mm"`), `view` | the board, and the side the coordinates are seen from (`bottom`: x mirrored) |
| `thickness_mm` | the board file's `thickness_mm` (default 1.6) |
| `outline` | the outline polygon `[[x, y], …]` |
| `holes`, `tooling` | `[{x, y, d}]` mounting holes and tooling holes |
| `parts` | per part in `[place]`: `side` (the side it sits on), `x`, `y`, `rot`, `box` `[x0, y0, x1, y1]` (the footprint's, silkscreen included) – and where its parts entry knows them: `h_mm` (`body`), `leads` (`[{pad, x, y, protrusion_mm}]` per through-hole pad with a lead `length_mm`; the protrusion is length − `thickness_mm`, out of the other side) with the largest as `protrusion_mm`, `mate` (`box` in plan mm, `h_mm`, `exit`: `+x`, `-x`, `+y`, `-y` in plan coordinates or `+z` away from the board; for a part turned by an angle that is no multiple of 90° the unit vector `[dx, dy]`) |
| `unplaced` | the parts the plan leaves to the auto-layout: the model does not know where they go |

Unknown values are left out, not guessed. The file holds no limits: how high a part may stand, how far a lead may
stick out, what the enclosure needs – that is the project's, from these numbers.

**Parts next to their host.** `edakit pcb place` works out a spot, offline, for every part that `[place]` lacks but
the circuit or the board file ties to a host: `layout.near` of the graph, `[near]` of the board file, and the
decoupling of SYNC.plan – an IC without a capacitor of its own within `near_mm` gets the first free capacitor between its
supply and ground that has no declared host of its own, matched one per IC as SYNC.plan matches them. Declared hosts come
first (graph, then board file, each by designator), then the decoupling; each placed part is an obstacle for the next.
The spot lies on the host's side, within `near_mm` of every host, at 0, 90, 180 or 270° on a 0.1 mm grid: the part's
pad on a net it shares with the host (ground only when that is all they share) as close as possible to the host's pin
on that net – for a decoupling capacitor its supply pad to the IC's supply pin, and within 0.1 mm of that the ground
pad nearest to the IC's ground pin. A spot counts only where the plan check (`check_plan` and SYNC.plan) reports nothing
new: `silk_overlap_mm`, `on_headers` with `header_keep_mm`, outline, hole and tooling keep-outs, THT pins of the
other side, `edge_mm` – as they are. Parts without a host stay with the auto-layout.

```text
$ edakit pcb place
  R1 = { x = 62.8, y = 21.9, rot = 90, side = "top", auto = true }   # next to U2: pad 1 1.3 mm from U2.15 (REXT)
  C1 = { x = 59.9, y = 21.0, rot = 180, side = "top", auto = true }   # decoupling of U2 on 3V3: pad 1 1.5 mm from U2.16 (3V3)
```

`--write` adds the rows as new lines at the end of `[place]`; every other line and comment stays as it is. A later run
may move a row with `auto = true` (its part is placed anew; one that has no host any more stays), never a row written
by hand – delete `auto = true` to keep a spot. To every other command an `auto` row is a fixed, locked part like any
other – the auto-layout writes such rows too (below). `--only C1,R1` places only those. A part without a spot is named
with its host and pin – `C1: no free spot within near_mm 6 of U2 (pin 16, 3V3)` – and the command exits 2. It reads
the geometry as `pcb plan` does: the dump of `pcb dump`, and for a part not yet in the PCB the library footprint
`edakit part import` cached (4.2).

**Every other part (`--rest`).** `edakit pcb place --rest` places every part of the board that has no row in
`[place]`, or a row with `auto = true` – not only the parts with a host. It works offline, from the board file, the
geometry and the graph, without EasyEDA. The parts with a host come first, as above. Then the part with the most pins
on nets of placed parts goes next, ground left out; a tie goes by designator. A part that names a placed part as its
host follows that part at once. An IC takes a spot only where its decoupling capacitor finds one next to it, and a
capacitor that may decouple an IC waits until the IC stands. The spots lie on the plan grid inside the outline, on a
side that is assembled (`[release] assembly sides`, top first; without the key both), at 0, 90, 180 or 270°. A spot
counts only where the plan check reports nothing new, as for the parts next to a host: overlaps, holes, tooling holes,
keep-outs, THT pins of the other side, the outline, `edge_mm`, mated plugs, `uniform`. Of these spots the part takes
the one where its pads add the least airline length: the minimum spanning tree of each net over its pads, the nets of
the graph, ground left out. Side, rotation, y and x break ties. The board is searched on a 0.5 mm grid first, then on
the 0.1 mm grid around the best spots.

An improvement pass follows. Each part placed by airline length moves to a spot where the airline length is shorter,
and each pair of them swaps rows where that shortens it – only where the plan check stays clean. A part that another
part was placed next to stays. The pass repeats until nothing changes, four times at most. No random numbers are
used: the same files give the same rows, and a second run changes nothing.

```text
$ edakit pcb place --rest
  R1 = { x = 62.8, y = 21.9, rot = 90, side = "top", auto = true }   # next to U2: pad 1 1.3 mm from U2.15 (REXT)
  R2 = { x = 59.7, y = 18.9, rot = 270, side = "top", auto = true }   # by airline length: adds 0.0 mm on 3V3, LED_OE
  D1 = { x = 20.9, y = 28.6, rot = 90, side = "top", auto = true }   # by airline length: adds 3.4 mm on +5V, VIN
  J1 = { x = 19.9, y = 34.2, rot = 180, side = "top", auto = true }   # by airline length: adds 3.4 mm on VIN
  improvement: no move or swap shortens the airline length (without GND) of 538.7 mm
  1 part next to its host, 3 by airline length – --write puts them into [place]
```

R2 adds nothing: its pads lie on the way from U1 to U2 on both its nets. The comment gives what a part adds to the
airline length of the finished plan, and the nets it shares with other parts. `--write` and `--only` work as above,
and an `auto` row without a host is placed anew as well. A part the circuit wants fixed (`layout.fixed`) gets a row
too, with the note `layout.fixed: check the spot, then drop auto = true`: whatever someone presses or looks at is the
PCB designer's choice, and only a row without `auto` stays where it is. A part without a spot is named with the first
new finding of its best spot, or with its box when no spot is free –
`SW1: no free spot on the top side – its box (60.0 x 30.0 mm) fits nowhere clear of the placed parts, the holes and
the outline` – and the command exits 2. The airline length is the only score so far; where routing shows that a plan
walls nets in (`edakit route diagnose`, 7.5), that may become a second one. `edakit pcb autolayout` (below) stays
until this placer has placed a real board that routed and passed the gate.

**The auto-layout's positions.** `edakit pcb autolayout` lets EasyEDA place the parts `pcb apply` left unlocked –
every part without a row – and waits until positions, rotations and sides stay the same for two readings. Then it
writes a row for every part of the board without one, where EasyEDA put it, as a new line at the end of `[place]`
with `auto = true`; every other line stays as it is, and the rows are read back:

```text
$ edakit pcb autolayout
   0.2 min: moving
   …
   1.4 min: stable
  D1 = { x = 75.0, y = 12.0, rot = 0, side = "top", auto = true }
  R2 = { x = 40.0, y = 30.0, rot = 0, side = "top", auto = true }
  2 rows written into hardware/boards/main.toml [place] with auto = true
```

From then on they are plan like any row: `pcb plan` checks them (overlaps, outline, `near`, `uniform`, mated plugs) and
puts them into the mechanical model, `pcb apply` puts them back after a dump and locks them, SYNC.plan holds the PCB to
them, and the layout hash covers them – commit them with the board file. The next auto-layout places only parts
without a row: delete a row to have its part placed anew, change it to move the part. `pcb place` may still move an
`auto` row next to the part's host. The rows are plan coordinates to 0.001 mm and 0.001° – what `pcb apply` writes
back is what EasyEDA reported. A part of the board that is not in the PCB is named (`! R2: not in the PCB – …`, exit
2); a part in the PCB that the graph does not put on the board gets no row (SYNC.pcb names it). Not settled within 20
minutes: nothing is written, exit 2.

**A board placed before.** A board placed by hand or by the auto-layout before edakit wrote its positions back – and
maybe routed – takes over its positions once:

```bash
edakit pcb takeover            # the rows it would write
edakit pcb takeover --write    # written into [place]
```

Every part of the board without a row gets a fixed row (no `auto`) where EasyEDA has it, so that `pcb apply` locks it
there and the tracks stay on its pads; a new auto-layout would move the parts off them. Rows the board file holds
stay as they are – SYNC.plan compares them with the PCB. Run it before any `pcb dump`: the dump turns every part to 0° on
TOP, and only the rows bring rotation and side back.

**Every part in the plan (SYNC.plan).** Stage L of the gate fails for every part the graph puts on the board that has no
row in `[place]` – by hand, from `pcb place`, or written back by the auto-layout. Parts on a bought or hand-wired
board (4.5) – off the made boards, at the far end of a cable – are on none of them and need no row.

`edakit pcb dump` turns every part it measures to 0° on TOP to read its geometry and **leaves it there** – run `apply`
afterwards: it puts every part with a row back; the auto-layout is needed again only for parts without one.

## 7.5 Routing with Freerouting

**Why not EasyEDA's autorouter:** it keeps its result only when the whole run succeeds – otherwise every track is
gone (1773 lines → 223); fixed 900 s limit; runs past the bridge timeout; sometimes does not start; leaves nets open;
routes nothing on nets that are partly routed. Trying to repair its leftovers (rip up, reconnect islands, route GND
first) cost a whole day and converged nowhere.

**Why our own DSN:** EasyEDA's DSN export returned null over the bridge, and its SES import needs a `File` object the
bridge cannot pass. edakit writes the Specctra DSN itself from pads and outline read through the API, runs Freerouting
headless, reads the SES, and creates every track and via through the API.

`edakit route all`, steps: read → dsn → route → check (up to `attempts` times with a reshuffled DSN) → apply → pours →
reload → drc. About 3–7 minutes for 120 parts.

Rules in the board file:

```toml
[routing]
clearance_mil = 6.5          # above EasyEDA's DRC (pad 0.152 mm) and JLCPCB (SMD pads 0.15 mm); 8 mil left 18 links open
signal_mil = 10
via = [24, 12]               # diameter, drill
edge_clearance_um = 400      # tracks and vias from the outline; the pours keep pour_inset_mm (7.6)
layer_cost = { TOP = [1.0, 1.8], BOTTOM = [2.2, 3.0] }   # preferred / against preferred direction: keep a side calm
classes = { POWER = { width_mil = 18, nets = ["VIN", "+5V"] }, GND = { width_mil = 18, nets = ["GND"] } }
widths = "classes"           # or "sim": every class at least the IPC-2221 width of the simulated currents (below)
hand_solder_keep_mm = 0.5    # GEO.spacing: vias and pads of other nets this far from hand-soldered joints (0 = off, below)

[[routing.keepouts]]               # no tracks (vias allowed) on a side or in an area
layer = "BOTTOM"
what = "wire"                      # or "all"
rect = [-80, 110, 80, 200]         # plan mm; windows = ["D1"] keeps those pads reachable

[[routing.fixed_wires]]            # protected tracks Freerouting routes around (e.g. a short switching loop)
net = "SW"
layer = "TOP"
width_mil = 24
points = [[10, 5], [14, 5]]

[[pours]]
net = "V_LED"
layers = ["BOTTOM"]
plane = true                       # the net's pads on BOTTOM (and through-hole pads) count as joined by the plane
fanout = true                      # its SMD pads on TOP get a via to the plane – Freerouting places none

[[pours]]
net = "GND"
layers = ["TOP"]
pour_only = true                   # no tracks: the pour between the tracks connects this net (7.6)
```

Class widths must be at least the minimum of the matching EasyEDA net class rule, or the DRC complains.

**EasyEDA's DRC rule set.** GEO.drc asks for a DRC without findings – with the rules EasyEDA holds, set in its GUI and in
no file. With `drc_rules = "check"` in `[routing]`, the gate reads the rule set the DRC ran with and holds it to the
board file, in a third row of GEO.drc (8.1) that names it:

- the clearance `clearance_mil` from track to track, pad and via, and from via to pad and via (EasyEDA's Safe Spacing);
  pads among themselves are the footprints' – GEO.spacing measures pads of different parts;
- the edge clearance `edge_clearance_um` of tracks and vias;
- the least width of every net's tracks: `width_mil` of its class in `classes`, `signal_mil` without one – a narrower
  fixed wire of the class lowers it, the board file prescribes it; with `widths = "sim"` the classes keep their
  `width_mil` here, wider tracks pass, and GEO.width holds each track to its current;
- the least via `via`, and the net classes of `classes` with their nets in the PCB.

Equal means within 1 µm – in every rule a net of the PCB uses, the default one too, and in every layer entry of a rule.
The row lists each difference with both numbers, e.g. `clearance Track–Track: EasyEDA 0.102 mm (Safe Spacing
'copperThickness1oz'), the board file 0.165 mm (clearance_mil 6.5)` – the reference project's DRC ran with that. Set
what it names in EasyEDA (Design → Design Rule: Safe Spacing, Track, Via Size, the net classes), or change
`[routing]`. The name in the row is the one EasyEDA reports, the template the rules came from – a write through the
API keeps it (9.4), so the name alone says nothing about the values. Without the key nothing is read and GEO.drc is as it
was. edakit does not write the rule set yet: the API takes it (9.4), the live probe of step 2.2 has not run.

**Widths from the simulation.** `widths = "classes"` (the default) writes the widths of `classes` and `signal_mil` into
the DSN as they are. With `widths = "sim"`, `route dsn`, `route` and `all` read `<artifacts>/sim/net_currents.json`
(`edakit sim`) and give every net at least its IPC-2221 width for 1.5 × its simulated current – the width GEO.width of the
gate asks for: a class is widened to the largest need of its nets, and a net outside the classes that needs more than
`signal_mil` gets a class of its own, named after the net. Widths are rounded up to 0.1 mil; `route dsn` prints what it
widened (`widths = "sim": class POWER: 18 -> 53.9 mil (+5V 2.00 A, VIN 2.00 A)`). Without the currents it stops. Fixed
wires keep their `width_mil` – the check names them (below). One source of widths then: the simulation, not a table
that drifts from it.

**Freerouting 2.4.1 pitfalls**, all handled in the DSN writer:

- Resolution `mil 1000` computes wrongly on a 170-mm board (unreachable pads, phantom violations) – edakit writes
  `mil 100`.
- A **concave outline as boundary**: nothing routed above a certain height. edakit uses a rectangle as boundary and
  the area outside the board (moved in by the edge clearance) as convex keep-out strips. The outline is moved in with
  round joins: around an inner corner (a notch) the keep-out is an arc of `edge_clearance_um`, in chords of at most
  16.875° (8 per quarter circle; an arc under 16.875° is one chord). It reaches at least 0.989 of the clearance into
  the board: 0.3957 mm with 0.4 mm, 4.3 µm short of the arc. Mitred joins reached d / sin(θ/2) into the board there –
  0.57 mm at a 90° corner, 1.3 mm at a 36° notch with 0.4 mm. Tracks that kept the clearance were reported, and
  Freerouting lost that room in every notch.
  `route check` and the fanout vias use the same strips. Every strip is kept, however small: at a sharp notch tip the
  cuts leave slices under 1 mil², and without them the keep-out reached only 0.3 mm into the board there. Freerouting
  skips a strip thinner than its 0.01 mil resolution with a warning ("Keepout zone … was skipped because its geometry
  is degenerate"); that is harmless, and `route check` still tests against it.
- `autoroute_settings` after the keep-outs: no parts read at all. A `plane` placed before the keep-outs: no
  connections read. Order matters.
- Fanout is on by default and puts a via at every SMD pad: `--router.fanout.enabled=false`. It does not connect an
  SMD pad to a plane on the other layer either – neither does the router: such a pad gets a track to another pad of
  its net, or stays open. edakit's `fanout` does it (below).
- Layer costs in the DSN are partly overridden by Freerouting itself; the optimiser stops at score 999.98/1000.
- **Deterministic but order-dependent:** after one part was recreated (it moved to the end of EasyEDA's list), one GND
  link stayed open three times in a row with the same plan. edakit sorts parts, pins and nets, and reshuffles them
  reproducibly (seed = attempt) when nets stay open.
- With a whole side as wire keep-out and one power net on it as a plane, Freerouting routes everything on the other
  side – a calm visible side. The plane joins the net's pads on its layer and its through-hole pads; its SMD pads on
  the routed side need `fanout = true`, or Freerouting routes them to another pad of the net with a track, and where
  a keep-out is in the way they stay open. With the ground net as the plane instead, 70 of 178 connections stayed
  open; choose the net whose pads are spread over the side.

**Fanout to a plane.** With `fanout = true` on a `plane` entry of `[[pours]]`, every SMD pad of the net on a layer
without its plane gets a via next to it and a stub from the pad's centre at the net's class width, written into the
DSN as protected wiring: Freerouting routes around them and keeps them, they come back in the SES, `route check`
counts them, and `apply` creates them like any routed via. The spot: the nearest distance first – half the pad's
larger side + via radius + clearance, then in 5 mil steps up to 60 mil further – and at each distance 16 directions
22.5° apart, the one closest to the direction away from the part's centre first. Via and stub keep the routing
clearance from foreign pads, fixed wires and other fanouts, and the fanout vias of a net one diameter + clearance
from each other; the via stays inside the edge clearance and off the keep-outs of mounting and tooling holes and of
`what = "all"`, the stub off those and off every keep-out on its layer (a `windows` entry keeps the pad's
surroundings free). A pad without a spot stops the DSN (`route dsn`, `route`, `all`) with its name: `R1.1 (V): no
room for a fanout via to the V plane – …`. Freerouting's own score counts a fanout via inside a wire keep-out as a
violation; edakit's check allows vias there, as `what = "wire"` says.

**Check before writing:** pads of different parts on different nets at least the clearance apart on every layer
both are on (GEO.spacing: pads of one part belong to the footprint; a pad without a net is a net of its own; `accept` GEO.spacing on a
part or net accepts a pair), SMD pads of different parts on different nets at least the paste gap apart on every side
that is assembled (GEO.spacing: `[release] assembly` – `sides`, `paste_gap_mm` 0.4 mm – so that the stencil keeps a web
between the two prints; through-hole pads get no paste; `accept` GEO.spacing), every net connected through pads, tracks and
vias (planes count, and the computed pour of a pour-only net, 7.6), every track and via at least the clearance from
foreign copper, nothing in keep-outs (the edge strips above: `edge_clearance_um` from the outline, in inner corners
too) – independent of Freerouting's own score. Freerouting cannot move a pad, so pads too close stop `route all` after
one attempt, without the reshuffled ones: move or turn one of the two parts in the plan. The gate measures the same on
the pads of the last `route read` (GEO.spacing, 8.1).

**Hand-soldered joints (GEO.spacing)** with `hand_solder_keep_mm` (0, off, by default): a joint soldered by hand gets an iron
and wire solder, not a stencil print of fixed volume, and a tented via or a foreign pad a few tenths of a millimetre
away can take a bridge that only shows at assembly. The joints are the pads of every part with `bom: false` in the
graph (8.4), each on its solder side – for a through-hole pad the copper layer its part does not sit on, for an SMD pad
its own layer, the side the part sits on: a tab soldered with an iron, such as a coin cell holder's, bridges to a via as
a through-hole joint does. On that side no via and no pad of another net comes closer than the keep, copper to copper;
a pad without a net is a net of its own, the part's own pads are not compared, and tracks do not count – they run under
the solder mask, between the pins of a 2.54 mm part too.
Pads too close stop `route all` like GEO.spacing (Freerouting cannot move them); a via gets the reshuffled attempts. `route
dsn` keeps vias away from the start: around every joint a via keep-out on its solder side, the pad grown by the keep
(Specctra `via_keepout`, which Freerouting reads) – it keeps out vias of the joint's own net as well, which reaches the
joint by track – and the fanout vias of a plane keep the same distance. `accept` GEO.spacing on the joint's part or net, or on
the other part or net, accepts a pair:

```text
hand-soldered joints (GEO.spacing): 2 on their solder side, 1 vias of other nets closer than hand_solder_keep_mm 0.5
    J1.1 (VIN) – via GND at (84.00, 9.70): 0.30 mm apart on BOTTOM, the solder side of J1, below hand_solder_keep_mm 0.5
```

At an SMD joint the line names the part's own side: `D1.2 (VIN) – via GND at (77.20, 13.45): 0.30 mm apart on TOP,
the side D1 sits on, below hand_solder_keep_mm 0.5`.

In the reference project the layout reviews found a via 0.25 mm from an LED joint, a via 0.26 mm between two
potentiometer pins and a resistor pad 0.37 mm from an LED joint, each after every check had passed; 0.5 mm finds all
three and passes the released board. The gate measures the same on the PCB (GEO.spacing, 8.1).
**Track widths (GEO.width offline)** with the gate's own widths (8.1): the narrowest SES track of every net and every
`[[routing.fixed_wires]]` entry against IPC-2221 for 1.5 × the simulated current – below it fails, and stops `route
all` before anything is written as open nets do (a new attempt routes no wider) – and against the practical width of
the net class (`[net_classes]`) – below it warns:

```text
    GEO.width (offline) VIN: 0.46 < 1.37 mm
    GEO.width (offline) fixed wire GND (84, 15)–(80, 15): 0.41 < 0.42 mm
    GEO.width (offline) 3V3: 0.30 < 0.40 mm – below the practical width of its class (warning)
```

Without `net_currents.json` one line says so and nothing fails. Tracks that pass GEO.width in the gate pass here.

**The visible side.** A front panel, a display side or a decorative board has a side people look at, and the means to
keep it calm are there – a wire keep-out over the side or part of it, a plane on it with `fanout`, layer costs. What
they lack is a target and a number. `[looks]` in the board file names the side; `route check` then prints the track
length per side of the SES and its vias, and the visible side's row – a via counts on both sides, it shows through:

```toml
[looks]
visible = "bottom"           # the side people look at: "top" or "bottom" (EasyEDA sides)
max_track_m = 0.1            # optional: more track on it is a warning
max_vias = 4                 # optional: more vias on the board is a warning
```

```text
tracks: TOP 0.04 m, BOTTOM 0.18 m; vias 2
BOTTOM (visible): 0.18 m of track, 2 vias
    BOTTOM (visible): 0.18 m of track, limit 0.1 m – warning
```

The lengths are those of the routing preview's titles. A warning changes no exit code: the routing is not wrong, the
look is not what the board file asked for. Stage L of the gate gives the same row from the PCB itself (8.1), and GEO.silk
holds the side's print to the board file (7.7). Without `[looks]` nothing is printed.
Preview: `<artifacts>/route/<board>_routing.png`, open connections dashed yellow. Nothing is written to EasyEDA until
the check passes.

**Why a connection stays open:** `edakit route diagnose [--net N]`, offline from `route/<board>_board.json`, the board
file's rules and the last SES – before rules are relaxed, parts moved or another long run started. A connection is
the closest pad pair between the largest group of an open net and each other group (the yellow airline). The net is
judged with its class width and the clearance, as Freerouting routes it; a pour-only net with its pour's `min_width_mm`
and `clearance_mm`, on its pour layers, without vias.

- **unreachable:** even on the empty board no way joins the two groups. The free area per layer is the board inside
  the edge clearance, without hole, tooling-hole and keep-out areas (a wire keep-out only for tracks) and every
  foreign pad grown by the clearance, shrunk by half the track width; vias join the layers wherever one fits on both.
  The line names what walls in the side that reaches less: `the edge`, a `hole at (x, y) mm`, a `keep-out K<i>` (the
  i-th `[[routing.keepouts]]` entry, counted from 0) with its layers, or the foreign `pads` around it.
- **blocked:** a way exists on the empty board, but not between the routed copper of the other nets. The line names
  the nets whose copper lies on the shortest way of the empty board (a raster of at most 0.1 mm, a via counted as 1 mm
  of way), and the highest congestion along it.
- **free way left:** the routed board still has room – Freerouting did not find it; more passes or another order.

```text
$ edakit route diagnose
[ 0.0 min] diagnose: 1 open connection in 1 net
    GND J1.2 – C2.2: unreachable – J1.2 enclosed by keep-out K0 (TOP, BOTTOM)
$ edakit route diagnose            # the origin, one-sided, with GND routed as tracks
    V_LED U1.23 – D32.1: blocked by GND_B1 – utilisation 0.04 at (-4, 2) mm
    U4_OUT7 U4.12 – D8.2: blocked by STAR_B_K, U4_OUT6 – utilisation 0.23 at (-6, 88) mm
```

**Congestion** (RUDY): each routed net's wire demand – half the perimeter of its pads' bounding box over its area – is
spread on a 1 mm grid and set against the capacity of each cell, the layers tracks may use there times cell / (signal
width + clearance); both are averaged over 3 × 3 mm, because single cells at the edge give outliers. Above 1 an area
needs more track than fits; a blocked connection at a low utilisation is a crossing, not a lack of room – a bridge,
the other layer or another placement, not more passes. `route/<board>_diagnose/` holds one cropped picture per open
connection (the net's free area on the empty board green, keep-outs red, the blocking nets' copper orange, the
shortest way yellow), `congestion.png` and `diagnose.json` (per connection `net`, `a`, `b`, `verdict`, `line`, and
`enclosed`, `enclosed_by` or `blocked_by`, `utilisation`, `at`, `way_mm`; the highest congestion). Exit 0 when nothing
is open, 2 when open connections are explained. No new key.

**Writing into EasyEDA** (all copper is generated, so it is deleted first – deleting sometimes needs several passes):
points closer than 0.5 mil are snapped together (EasyEDA drops tiny pieces and connects track to track only through
coinciding ends), pieces are split at T junctions, straight continuations merged (EasyEDA does that anyway), pieces
inside a via dropped. Afterwards a **geometric** comparison plan ↔ PCB (counting is no check because EasyEDA merges),
and anything unplanned is deleted – old tracks have come back after a reload before.

**DRC only after reload:** right after API changes the DRC reported 320 false connection errors; saved and reloaded:
0. `route all` saves, closes and reopens the PCB before its DRC.

**Import Changes.** After parts were placed in the schematic, EasyEDA's DRC reports "Netlist Error – Import
Changes" until its import view has been opened once – also when schematic and PCB are equal. `route drc` (and
`route all`, `silk apply`/`check`, the gate's GEO.drc) then compares them itself, as `pcb parts` and `pcb nets` do without
`--write`, writes the result to `route/<board>_netlist_diff.json` and says which case it is: no difference → "EasyEDA
waits for the import acknowledgement: open Design → Import Changes once, it shows no changes", exit **3** when that
is the only item; differences → the parts and pads with `pcb parts --write` or `pcb nets --write`, exit 2. In the
reference project the item alone held the gate at GEO.drc in ten runs, once for 2¾ h while the first diagnosis was
wrong.

## 7.6 Pours

`[[pours]]` of the board file: net, layers, `plane` (with `fanout`, 7.5), `stitch`, `pour_only`. Filled with
`easyeda_pcb_rebuild_copper` per net (status `readback-mismatch` is harmless for the fill). EasyEDA drops every piece of a
pour that touches no pad of its net: where the pour net has no pad, that side stays bare – it looks the same as a pour
that was never filled. The gate measures it in the Gerber files (GEO.pour): a copper-free circle above `[copper]
max_bare_mm` (5 mm) inside the pour outline of a poured layer warns, and so does a copper piece without pad, via or hole.
Give such an area a net that reaches it – a second pour net with `pour_regions` below, or a pad or via of the pour net. With `stitch = "BOTTOM"` edakit fills
once keeping islands, puts a via into every loose island on that side where it overlaps the pour of the other side
(with clearance), then fills again without islands.

**Distance from the edge.** Every pour gets the board outline set in by `pour_inset_mm` from the top of the board file
– without it by the tracks' `routing.edge_clearance_um` + 0.1 mm (0.5 mm with 400; EasyEDA itself keeps only about
0.26 mm). The computed pours below start from the same outline. The key keeps the pours further from the milled edge
than tracks that have to run along it, through a notch of the outline say; the tracks keep the edge clearance in the
DSN and in Freerouting either way:

```toml
pour_inset_mm = 0.55               # in hardware/boards/<b>.toml, above the tables; tracks 0.4 mm (edge_clearance_um)
```

**Pour-only nets.** On a board where ground is the pour between the tracks – all tracks on one side, say – a net with
`pour_only = true` gets no tracks: the DSN leaves it out of the network, so its pads are pins without a net that
Freerouting keeps clear of. `route check` computes the pour offline from the board file and the routes: the pour
outline of `pcb pour`, without the pads (also those without a net), tracks and vias of other nets on that layer grown
by `clearance_mm`, without necks narrower than `min_width_mm` (EasyEDA does not fill them). The net counts as connected
when one piece holds all its pads; pieces on two pour layers join through the net's through-hole pads and vias, and
its own tracks count as well. Otherwise it is reported like an open net, `GND (pour-only): 2 groups – C1.2 | C2.2`, and
the preview shows the computed pour. Fixed wires of the net (`routing.fixed_wires`) stay in the result although
Freerouting leaves a net outside the network out of its SES. A plane, by contrast, is taken as connected whatever
the tracks do to it – use it for a layer the net has to itself, reached through its through-hole pads and vias
(`fanout`, 7.5), not for a pour that tracks cut.

**Several nets on one layer.** `pcb pour` gives every pour the same outline, and where pours overlap EasyEDA fills only
the one with priority – a second net on a layer gets nothing. With `pour_regions = true` at the top of the board file,
each net on a layer that several nets pour on gets an outline of its own area instead:

```toml
pour_regions = true                # in hardware/boards/<b>.toml, above the tables

[[pours]]
net = "GND"
layers = ["BOTTOM"]
pour_only = true                   # priority 1: claims first

[[pours]]
net = "V_LED"
layers = ["BOTTOM"]
priority = 2
```

The nets claim their area in `priority` order (1 first, ties in the order of the file). A net takes the pieces of its
computed pour (as for pour-only nets, with its `clearance_mm` and `min_width_mm`) without what the nets before it
fill, kept away from that by its clearance – the pieces that hold its own copper (pads, tracks, vias; EasyEDA drops the
others as islands) and have more than `pour_min_piece_mm2` (2.0) outside that copper grown by the clearance; EasyEDA
would leave a smaller one empty. Its outlines are those pieces without their holes, grown by 0.2 mm, simplified by
0.03 mm, within the pour outline and without the outlines of the nets before it: one pour per outline
(`GND_BOTTOM_1`, `GND_BOTTOM_2`, …), with the entry's priority. A layer with one net keeps the full outline.

The outlines come from the board file and the SES, so `route pours` computes them (`route all` at its end); `pcb pour`
stops with a hint while there is no routing. EasyEDA does not fill an outline with a hole, so a piece of one net inside
the outline of another is an error naming the place – `GND_B BOTTOM: its pour at (10.0, 10.0) mm lies inside the pour
of GND` – and nothing is poured; `route check` reports it as a finding first, and `route all` tries another routing.
A pour-only net on a shared layer is connected by what it claims, not by the whole outline, and the preview draws the
outlines dashed. A plane takes the whole layer, so with `pour_regions` it needs a layer of its own.

Without `pour_regions`, the computed pour of a pour-only net assumes the layer to itself: when another net pours on
the same layer, `route check` says so. The gate's GEO.copper (connectivity) and GEO.pour (bare areas, loose copper) on the Gerber
copper have the last word either way.

## 7.7 Silkscreen

`edakit silk apply` hides the designators of the configured sides, exports Gerber (so the silk layer shows only the
footprints' own print), places every designator of the `designators` side at the first free spot (above, below, right,
left, then vertical, then at the corners; not on pads, footprint print, parts or other labels; over a tented via only as
last resort; test points first) or at its fixed spot (`[silk.place]`, below), then exports again and checks that no own
silkscreen lies on a solder-mask opening (JLCPCB cuts it off there) – target 0 mm² – and runs the DRC. Pictures per side
in `<artifacts>/silk_<board>_<side>.png`.

**A body larger than its footprint.** A part's box is its footprint, but a coin cell stands out of its holder. A
designator placed beside such a footprint lies under the body once the part is in. Where the
parts entry gives the body seen from above (`body.box`, 4.1), `silk apply` takes it as part of the part's box on its
side: the designator goes beside the body, and no other label or the board label goes under it. A fixed designator
(below) under a body is a finding – `R1: fixed designator under the body of R1 (top) – 2.36 mm² of its box, hidden
once the part is in (body.box of its parts entry)`. The gate warns about any print under the body beyond the footprint
box (GEO.silk, grade body, 8.1). The example's BT1 has no `body.box` (its entry gives the height only); the walkthrough
fixed its designator with `[silk.place]` (17.11).

The export stays in `<artifacts>/gerber_<board>/` (`edakit silk check` writes it again without placing anything): the
copper of every layer as EasyEDA filled it, which the layout review at the end of the round reads (skill pcb-round) –
the routing picture shows the pours edakit computed, not what EasyEDA made of them.

**Through-hole parts of the other side** are soldered from the `designators` side – LEDs on the front of a board whose
electronics and designators are on the back. With `solder_side = true` in `[silk]` they are labelled there too: next to
their box, where their solder joints are, by the same free-spot search, and their box blocks other labels like a part of
that side. A part's designator prints only on its own side, so the name is a free text in the designators' stroke font
and height, remembered and replaced like the board label. A part counts as through-hole with at least one through-hole
pad; SMD parts of the other side get no label. `hide = ["bottom"]` (or `"top"`) keeps the part's own side free of
designators. A large through-hole part there – a module on pin headers – blocks label spots over its whole box.

**Single designators at a fixed spot.** `[silk.place]` fixes a designator as `[place]` fixes a part: `x`, `y` in plan
mm (the centre of the text), `rot` (0; the rotation EasyEDA gets, as for `[[silk.texts]]`: 0 and 180 lie, 90 and 270
stand) and `side` (the side the name prints on; default the `designators` side). `silk apply` writes it there in the
designators' font and height and places the rest around it – the free-spot search, the group labels and the board label
keep clear of it. On the side its part sits on, the part's own designator moves there and shows, on a side in `hide`
too; on the other side the name is a free text, remembered and replaced like a group label, as with `solder_side`. It
prints there and nowhere else, and it leaves its group:

```toml
[silk.place]                                     # hardware/boards/main.toml
R4 = { x = 30, y = 41.5, rot = 90 }              # left of its part, standing
LED5 = { x = 30, y = 44, side = "bottom" }       # on the LED's solder side
```

No spot is searched for it, so `silk apply` checks it as the search checks a spot: on a pad (within 0.15 mm of a
solder-mask opening), beyond the printable board (the outline less 0.5 mm, the holes) or on a text (within 0.3 mm of a
`[[silk.texts]]` entry of its side, within 0.2 mm of another fixed designator) it is a finding – `R4: fixed designator
on a pad (top) – 0.42 mm² of its box within 0.15 mm of a solder-mask opening` – and the exit code is 2; it is written
all the same. A row for a designator the board does not have is a finding too. `edakit silk preview` draws the fixed
designators as blue boxes onto the last Gerber export and reports the same findings offline (exit 2), so a spot can be
tuned without EasyEDA. In the gate a fixed designator is edakit's print like any other (GEO.silk). A part of the
`designators` side whose name goes to the other side has none on its own side: GEO.silk warns unless `unlabelled` gives the
reason. With `[looks]`, GEO.silk does not know `[silk.place]` yet: a fixed designator on the visible side while
`designators` names the other side is a finding there – a part's own designator can be accepted on the part (`accept`
GEO.silk), a free text not.

It also prints the **board label** – title and revision, `"{title} rev {revision}"` by default – at the free spot
nearest to the bottom-left corner of the printed side (`board_label_corner`), clear of pads, parts, labels, vias and the
keep-outs of mounting and tooling holes. The revision comes from `revision` in the board file; without it there is no
label. edakit remembers the texts it created (`<artifacts>/silk_strings_<board>.json`) and replaces them on the next
run, so a board never carries two revisions.

The label goes on the `designators` side unless `board_label_side = "bottom"` (or `"top"`) names the other one. There it
keeps clear of that side's mask openings and print (+0.15 mm), the boxes of its parts, its artwork and texts, vias and
hole keep-outs. `board_label_region = [[x, y], …]` (plan mm) gives the part of the board it must lie in – the part a
stand or an enclosure covers, say; `board_label_corner` is then the corner of that region. Without a free spot there
the label is left out: "board label …: no free spot in board_label_region". Both keys leave the label as it was when
they are missing:

```toml
[silk]
designators = "top"
board_label_side = "bottom"                                # the LED side, without designators
board_label_region = [[0, 0], [60, 0], [60, 34], [0, 34]]  # the lower 34 mm, inside the stand
```

**Artwork and labels** come first: `[[silk.art]]` places an SVG (filled shapes and strokes, scaled to
`width_mm`, centred at `x`, `y` in plan mm) and `[[silk.texts]]` free texts – "START" at a button, "GND 5V
SIG" at a connector. edakit cuts the artwork free of pads and solder-mask openings (+0.15 mm), drops everything thinner
than 0.15 mm (JLCPCB does not print it) and mirrors graphics on the bottom side (EasyEDA does that only for texts).
Designators and the board label keep clear of artwork and texts. `edakit silk preview` draws them onto the last Gerber
export offline (`<artifacts>/silk_preview_<board>_<side>.png`), so a design can be tuned without EasyEDA. Draw motifs in
mm with lines of 0.2 mm or more; script text works as outlines (embolden it a little). The SVGs are in the layout hash
like the board file: a changed motif voids the sign-offs with scope `layout`, and M-5 with scope `fab` lapses with the
silkscreen of the next gate run (8.2).

Good to know:

- Minimum text height at JLCPCB: 1.0 mm; stroke ≥ 0.15 mm (a regular 1.5-mm font had 0.12 mm – use bold). All heights in
  the board file (`label_h_mm`, `board_label_h_mm`, `h_mm` of texts) are **printed capital heights**: EasyEDA's font
  size is the em height, and capitals print at about 0.69 of it – a size of 1.0 gave 0.71-mm letters including the
  stroke. edakit converts with 0.68 for some margin.
- Mounting holes: the pour leaves the `keep` circle free (screw head, washer); EasyEDA alone keeps only 0.26 mm.
- On the bottom silk layer EasyEDA mirrors texts by itself (`mirror = false`), but **not** graphics – mirror fills and
  lines yourself.
- JLCPCB prints its order number somewhere unless you place the placeholder `JLCJLCJLCJLC` and choose
  "specify a location" when ordering: a `[[silk.texts]]` entry of at least 0.8 mm and `mark = "specify"` in `[order]`
  of the board file – FILES.order checks that both are there (8.4). JLCPCB's help article reports the order number gone since
  May 2026: FILES.order warns about the placeholder until ordering step 0 has seen the form, and a 2D barcode or a serial
  number (`barcode`, `serial_number`) take its place. PCBWay's placeholder is `WayWayWay`; another maker's on the
  board is printed as text, and FILES.order finds it.
- The print colour follows the solder mask: JLCPCB prints white, on a white mask black. Artwork drawn for one colour
  says so with `silkscreen` next to `mask` in `[order]`; FILES.order fails a pair JLCPCB does not print (8.4).
- Run `silk apply` again after every auto-layout and routing – spots depend on parts and vias.

**In the gate** (GEO.silk, 8.1) the silkscreen is checked as the fab gets it. `silk apply` keeps the silk files of its first
export – the print it found before placing anything: footprints, and texts it did not make – in
`<artifacts>/silk_footprints_<board>/`; whatever else lies on a solder-mask opening is edakit's own print and fails
(run `silk apply` again). The footprints' print on an opening, print beyond the outline, a text height below 1.0 mm and
a part of the `designators` side without a visible designator are warnings. A part that is left without a designator on
purpose goes into `unlabelled` with the reason, so the warning does not come back with every run:

```toml
[silk]
designators = "top"
unlabelled = { R21 = "no room between the star tracks" }
```

With `[looks]` (7.5) the gate also holds the visible side to the board file (GEO.silk): its PCB texts are the board label of
that side, the `[[silk.texts]]` of that side and – when `designators` is that side – the designators and group
labels; and while `designators` names the other side, no part on the visible side shows its designator. A part placed
again after `silk apply` (a swap, a footprint rebuilt) comes back with its designator shown: run `silk apply` again.
A text placed by hand that belongs there goes into `[[silk.texts]]`; a designator wanted there is accepted on the part.

## 7.8 Export for documentation

`edakit export` writes per board the schematic as vector PDF (patched bridge; otherwise stitched canvas tiles), the PCB
PDF, Gerber, BOM, pick and place, netlist, plus a consistent copy of the project file (SQLite backup). Orders are made
from the gate's files, not from these.
