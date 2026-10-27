# 7 PCB (stage L)

The PCB is generated in layers: parts and nets from the board schematic (without dialogs), a **placement plan** for
everything that matters (in the board file `hardware/boards/<name>.toml`, 10.2), EasyEDA's auto-layout for the rest,
**Freerouting** for the tracks, pours, silkscreen. Every step can be repeated; every step checks itself.

```bash
edakit handover              # what the circuit hands over: state, sign-offs, what the plan must keep (14.1)
edakit pcb parts --write     # parts of the board schematic -> PCB (no "Import Changes" dialog)
edakit pcb dump              # footprint geometry -> <artifacts>/pcb_geometry_<board>.json
edakit pcb plan              # offline: check the plan, preview PNG, net classes
edakit pcb place --write     # offline: decoupling capacitors, pull and series resistors next to their host
edakit pcb apply             # outline, holes, tooling holes, fixed parts locked; pads verified
edakit pcb autolayout        # the unlocked small parts, waits until positions are stable
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
the dump of a placed part, else the library footprint of `edakit part import`. Pads are matched by position only: for
each turn of 0, 90, 180 and 270° on the same side, and for the mirror image (the other side), the nearest assignment
after laying origins and centroids on each other, with the shift that lays the assigned pads over each other best. A
turn fits when every pad of OLD lies on the copper of its new pad (shape, size and rotation from the library; for a
dump without pad sizes within half the smallest pad distance). Every other fit within 0.05 mm RMS of the best one
with another map is reported – "symmetric: the numbers decide". The report:

- the turn and shift that lay NEW over OLD, the residual per pad, whether the mirror image fits as well – or "mirror
  image only – not on the same side", or "no turn fits"
- the map old → new by position, the roles of the two entries that change under it (`old 1 throw_a → new 3 throw_b`)
- the pitch per row, the hole or slot per pad old → new, and with `lead` in NEW's entry L-9's verdict (`hole_ok`) and
  the 0.5 mm minimum for plated slots; the box w × h old → new
- the graph change it implies for every component that uses OLD (`SW5: BAT_SW 1 → 3`)

Exit 0 is a drop-in – same side, 0°, every pad keeps its number and role, holes fit (a shift is reported, the plan
moves the part); 2 is something to decide. It writes nothing but `--json F`. The reference project's slide switch
(XUNPU SS-12D11G9 for G-Switch SS-12D11-G090) gives: turned 180°, the mirror image fits equally (symmetric), map
1→3, 2→2, 3→1, 4→4, 5→5, pitch 4.70 → 4.80 mm, the 0.40 mm tab slots below 0.5 mm, `SW5: BAT_SW 1 → 3` – what took
an hour with both datasheet drawings and was first described as a turn when it is a mirror image.

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
the library footprint `edakit part import <LCSC>` cached (4.2): `pcb plan` names those parts ("library geometry") and
takes their pad nets from the graph. The dump wins. The dump keeps the hole of every through-hole pad (`hole` [w, l] in
mm, `plated`), and `pcb plan` runs P-7 on the plan's geometry: a hole that does not take its lead is a plan finding
(`P-7 D31 (pads 1, 2, 3, 4, library geometry …): hole 0.70 mm for diagonal 0.71 mm …`), a tight hole or a missing
`lead` is printed. A geometry file from before has no holes – dump again (it changes the layout hash once). Library and EasyEDA Pro agree on the pads within 0.1 mil (eleven
footprints of the reference project; one switch 1 mil); the boxes differ by up to 0.3 mm, because EasyEDA Pro measures the silkscreen of
the placed part. Without a dump and without a cached footprint a planned part stays a finding.

**What the circuit hands over** (L-12) comes first. The circuit designer writes it into the graph, the PCB designer
keeps it (14.1); `edakit handover` lists it:

```json
"layout": {"fixed": ["SW1", "D2"], "edge": ["J1"], "near": {"R1": "U2"},
           "loops": [{"a": "C5.1", "b": "U3.2", "max_mm": 8, "what": "buck input loop"}],
           "notes": ["D2 to D9 form the bar: one row, in this order"]}
```

`fixed` parts need a position in `place`; `edge` parts also a box within `edge_mm` of the outline (default 1 mm);
`near` parts sit within `near_mm` of their host. Every IC with a supply pin gets a capacitor of its own from that
supply to ground within `near_mm` – derived from the graph, matched one capacitor per IC, so two ICs cannot share one
while another sits far away; an IC whose capacitor is elsewhere on purpose carries `waive: {"L-12": "…"}`. `loops`
join the board file's `[[loops]]` for L-11 on the routed board – G-18 wants one on every net of a switching
regulator's hot loop (its `hot_loop` pins and the net behind its diode), and `notes` are for the PCB designer and the
layout review. A requirement the plan cannot keep goes back to the circuit as a written request – the layout does not
change the graph.

`edakit pcb plan` checks offline: overlaps per side (under a module on pin headers only its pins, SMD parts within a
silkscreen tolerance: below), outline (0.3 mm margin; `edge_ok` for connectors), keep-outs of holes and tooling holes,
THT pins of one side under parts of the other, `near` distances, the circuit's layout requirements (L-12), **polarised
parts that point the same way** – by default LEDs side by side with their anode towards the same side (below); it
prints the airline length of the fixed parts (a number to compare placements) and writes
`<artifacts>/pcb_plan_<board>.png`. Look at the picture before `apply`.

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
here, but by `route check` and the gate – the clearance (L-13) and, on an assembled side, the paste gap (L-14, 7.5).

```toml
silk_overlap_mm = 0.8        # in hardware/boards/<b>.toml, above the tables
```

With the key, an overlap gives its depth: `R1 / R2: overlap (top) – 1.00 mm (silk_overlap_mm 0.8)`, or
`J1 / C1: overlap (top) – 0.30 mm (J1 through-hole: silk_overlap_mm does not apply)`.

**Parts next to their host.** `edakit pcb place` works out a spot, offline, for every part that `[place]` lacks but
the circuit or the board file ties to a host: `layout.near` of the graph, `[near]` of the board file, and the
decoupling of L-12 – an IC without a capacitor of its own within `near_mm` gets the first free capacitor between its
supply and ground that has no declared host of its own, matched one per IC as L-12 matches them. Declared hosts come
first (graph, then board file, each by designator), then the decoupling; each placed part is an obstacle for the next.
The spot lies on the host's side, within `near_mm` of every host, at 0, 90, 180 or 270° on a 0.1 mm grid: the part's
pad on a net it shares with the host (ground only when that is all they share) as close as possible to the host's pin
on that net – for a decoupling capacitor its supply pad to the IC's supply pin, and within 0.1 mm of that the ground
pad nearest to the IC's ground pin. A spot counts only where the plan check (`check_plan` and L-12) reports nothing
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
other. `--only C1,R1` places only those. A part without a spot is named with its host and pin – `C1: no free spot
within near_mm 6 of U2 (pin 16, 3V3)` – and the command exits 2. It reads the geometry of `pcb dump`, so the parts must
be in the PCB once.

`edakit pcb dump` turns every part it measures to 0° on TOP to read its geometry and **leaves it there** – run `apply`
and the auto-layout afterwards.

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

**Widths from the simulation.** `widths = "classes"` (the default) writes the widths of `classes` and `signal_mil` into
the DSN as they are. With `widths = "sim"`, `route dsn`, `route` and `all` read `<artifacts>/sim/net_currents.json`
(`edakit sim`) and give every net at least its IPC-2221 width for 1.5 × its simulated current – the width L-5 of the
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
both are on (L-13: pads of one part belong to the footprint; a pad without a net is a net of its own; `waive` L-13 on a
part or net accepts a pair), SMD pads of different parts on different nets at least the paste gap apart on every side
that is assembled (L-14: `[release] assembly` – `sides`, `paste_gap_mm` 0.4 mm – so that the stencil keeps a web
between the two prints; through-hole pads get no paste; `waive` L-14), every net connected through pads, tracks and
vias (planes count, and the computed pour of a pour-only net, 7.6), every track and via at least the clearance from
foreign copper, nothing in keep-outs (the edge strips above: `edge_clearance_um` from the outline, in inner corners
too) – independent of Freerouting's own score. Freerouting cannot move a pad, so pads too close stop `route all` after
one attempt, without the reshuffled ones: move or turn one of the two parts in the plan. The gate measures the same on
the pads of the last `route read` (L-13, L-14, 8.1).
**Track widths (L-5 offline)** with the gate's own widths (8.1): the narrowest SES track of every net and every
`[[routing.fixed_wires]]` entry against IPC-2221 for 1.5 × the simulated current – below it fails, and stops `route
all` before anything is written as open nets do (a new attempt routes no wider) – and against the practical width of
the net class (`[net_classes]`) – below it warns:

```text
    L-5 (offline) VIN: 0.46 < 1.37 mm
    L-5 (offline) fixed wire GND (84, 15)–(80, 15): 0.41 < 0.42 mm
    L-5 (offline) 3V3: 0.30 < 0.40 mm – below the practical width of its class (warning)
```

Without `net_currents.json` one line says so and nothing fails. Tracks that pass L-5 in the gate pass here.

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
look is not what the board file asked for. Stage L of the gate gives the same row from the PCB itself (8.1). Without
`[looks]` nothing is printed.
Preview: `<artifacts>/route/<board>_routing.png`, open connections dashed yellow. Nothing is written to EasyEDA until
the check passes.

**Writing into EasyEDA** (all copper is generated, so it is deleted first – deleting sometimes needs several passes):
points closer than 0.5 mil are snapped together (EasyEDA drops tiny pieces and connects track to track only through
coinciding ends), pieces are split at T junctions, straight continuations merged (EasyEDA does that anyway), pieces
inside a via dropped. Afterwards a **geometric** comparison plan ↔ PCB (counting is no check because EasyEDA merges),
and anything unplanned is deleted – old tracks have come back after a reload before.

**DRC only after reload:** right after API changes the DRC reported 320 false connection errors; saved and reloaded:
0. `route all` saves, closes and reopens the PCB before its DRC.

## 7.6 Pours

`[[pours]]` of the board file: net, layers, `plane` (with `fanout`, 7.5), `stitch`, `pour_only`. Filled with
`easyeda_pcb_rebuild_copper` per net (status `readback-mismatch` is harmless for the fill). EasyEDA drops every piece of a
pour that touches no pad of its net: where the pour net has no pad, that side stays bare – it looks the same as a pour
that was never filled. The gate measures it in the Gerber files (L-15): a copper-free circle above `[copper]
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
the same layer, `route check` says so. The gate's L-2 (connectivity) and L-15 (bare areas, loose copper) on the Gerber
copper have the last word either way.

## 7.7 Silkscreen

`edakit silk apply` hides the designators of the configured sides, exports Gerber (so the silk layer shows only the
footprints' own print), places every designator of the `designators` side at the first free spot (above, below, right,
left, then vertical, then at the corners; not on pads, footprint print, parts or other labels; over a tented via only as
last resort; test points first), then exports again and checks that no own silkscreen lies on a solder-mask opening
(JLCPCB cuts it off there) – target 0 mm² – and runs the DRC. Pictures per side in `<artifacts>/silk_<board>_<side>.png`.
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
mm with lines of 0.2 mm or more; script text works as outlines (embolden it a little).

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
  of the board file – F-6 checks that both are there (8.4).
- Run `silk apply` again after every auto-layout and routing – spots depend on parts and vias.

**In the gate** (L-17, 8.1) the silkscreen is checked as the fab gets it. `silk apply` keeps the silk files of its first
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

## 7.8 Export for documentation

`edakit export` writes per board the schematic as vector PDF (patched bridge; otherwise stitched canvas tiles), the PCB
PDF, Gerber, BOM, pick and place, netlist, plus a consistent copy of the project file (SQLite backup). Orders are made
from the gate's files, not from these.
