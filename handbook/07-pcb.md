# 7 PCB (stage L)

The PCB is generated in layers: parts and nets from the board schematic (without dialogs), a **placement plan** for
everything that matters (in edakit.toml), EasyEDA's auto-layout for the rest, **Freerouting** for the tracks, pours,
silkscreen. Every step can be repeated; every step checks itself.

```bash
edakit pcb parts --write     # parts of the board schematic -> PCB (no "Import Changes" dialog)
edakit pcb dump              # footprint geometry -> <artifacts>/pcb_geometry_<board>.json
edakit pcb plan              # offline: check the plan, preview PNG, net classes
edakit pcb apply             # outline, holes, tooling holes, fixed parts locked; pads verified
edakit pcb autolayout        # the unlocked small parts, waits until positions are stable
edakit route all             # Freerouting -> EasyEDA, pours, reload, DRC (exit 0 = DRC 0)
edakit silk apply            # designators where there is room, silkscreen check on the Gerber, DRC
```

## 7.1 Coordinates

- **Plan** (edakit.toml): mm, any origin you like, seen from the board's `view` side. `side` of a part is the EasyEDA
  side it sits on (`top`/`bottom`).
- **EasyEDA:** mil, y up, seen from the top. With `view = "bottom"` edakit mirrors x and turns rotations into
  180° − rotation – useful when the side people look at is the bottom (e.g. LEDs on the bottom, electronics on top,
  because EasyEDA's auto-layout only places on TOP).
- **Footprints on the bottom:** EasyEDA mirrors the local y of a footprint, then rotates. `Board.transform` does the
  same, and `pcb apply` compares the pads EasyEDA reports with the plan (largest deviation must be < 0.05 mm) – one part
  per footprint, side and rotation, or all with `--verify-all`.

## 7.2 Outline, holes, tooling holes

```toml
[boards.main.outline]
rect = [90, 40]            # or polygon = [[x, y], …] (only straight segments; arcs as point lists)
corner_radius = 2

[[boards.main.holes]]      # non-plated mounting holes, drawn as circles on the outline layer
x = 3.5
y = 3.5
d = 3.2
keep = 3.2                 # radius free of parts and copper (screw head)

[boards.main.tooling]      # JLCPCB Economic PCBA tooling holes
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

One case remains: when a part was freshly placed in the schematic from the library, the DRC shows "Netlist Error –
Import Changes" until the import view was opened once in the GUI. That is the one click to ask for (start skill,
section 3).

## 7.4 The placement plan

```toml
[boards.main.place]
U1 = { x = 29, y = 14.5, rot = 0, side = "top" }
J1 = { x = 84, y = 12, rot = 90, side = "top" }

[boards.main.near]       # must sit within near_mm of the host
C1 = "U2"
```

Fix everything the auto-layout must not decide: connectors and anything at the edge, controls, ICs with their
decoupling capacitors and pull resistors, LEDs and anything visible, parts with mechanical constraints. EasyEDA's
auto-layout places only unlocked parts, only on TOP, and knows nothing about belonging – it once put a decoupling
capacitor 24 mm from its IC.

`edakit pcb plan` checks offline: overlaps per side, outline (0.3 mm margin; `edge_ok` for connectors), keep-outs of
holes and tooling holes, THT pins of one side under parts of the other, `near` distances; it prints the airline length
of the fixed parts (a number to compare placements) and writes `<artifacts>/pcb_plan_<board>.png`. Look at the picture
before `apply`.

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

Rules in edakit.toml:

```toml
[boards.main.routing]
clearance_mil = 6.5          # above EasyEDA's DRC (pad 0.152 mm) and JLCPCB (0.127 mm); 8 mil left 18 links open
signal_mil = 10
via = [24, 12]               # diameter, drill
edge_clearance_um = 400
layer_cost = { TOP = [1.0, 1.8], BOTTOM = [2.2, 3.0] }   # preferred / against preferred direction: keep a side calm
classes = { POWER = { width_mil = 18, nets = ["VIN", "+5V"] }, GND = { width_mil = 18, nets = ["GND"] } }

[[boards.main.routing.keepouts]]   # no tracks (vias allowed) on a side or in an area
layer = "BOTTOM"
what = "wire"                      # or "all"
rect = [-80, 110, 80, 200]         # plan mm; windows = ["D1"] keeps those pads reachable

[[boards.main.routing.fixed_wires]] # protected tracks Freerouting routes around (e.g. a short switching loop)
net = "SW"
layer = "TOP"
width_mil = 24
points = [[10, 5], [14, 5]]

[[boards.main.pours]]
net = "V_LED"
layers = ["BOTTOM"]
plane = true                       # Freerouting connects this net's pads to a plane on that layer through vias
```

Class widths must be at least the minimum of the matching EasyEDA net class rule, or the DRC complains.

**Freerouting 2.4.1 pitfalls**, all handled in the DSN writer:

- Resolution `mil 1000` computes wrongly on a 170-mm board (unreachable pads, phantom violations) – edakit writes
  `mil 100`.
- A **concave outline as boundary**: nothing routed above a certain height. edakit uses a rectangle as boundary and
  the area outside the board (moved in by the edge clearance) as convex keep-out strips.
- `autoroute_settings` after the keep-outs: no parts read at all. A `plane` placed before the keep-outs: no
  connections read. Order matters.
- Fanout is on by default and puts a via at every SMD pad: `--router.fanout.enabled=false`.
- Layer costs in the DSN are partly overridden by Freerouting itself; the optimiser stops at score 999.98/1000.
- **Deterministic but order-dependent:** after one part was recreated (it moved to the end of EasyEDA's list), one GND
  link stayed open three times in a row with the same plan. edakit sorts parts, pins and nets, and reshuffles them
  reproducibly (seed = attempt) when nets stay open.
- With a whole side as wire keep-out and one power net on it as a plane, Freerouting routes everything on the other
  side and connects that net with vias – a calm visible side. With the ground net as the plane instead, 70 of 178
  connections stayed open; choose the net whose pads are spread over the side.

**Check before writing:** every net connected through pads, tracks and vias (planes count), every track and via at
least the clearance from foreign copper, nothing in keep-outs – independent of Freerouting's own score. Preview:
`<artifacts>/route/<board>_routing.png`, open connections dashed yellow. Nothing is written to EasyEDA until the check
passes.

**Writing into EasyEDA** (all copper is generated, so it is deleted first – deleting sometimes needs several passes):
points closer than 0.5 mil are snapped together (EasyEDA drops tiny pieces and connects track to track only through
coinciding ends), pieces are split at T junctions, straight continuations merged (EasyEDA does that anyway), pieces
inside a via dropped. Afterwards a **geometric** comparison plan ↔ PCB (counting is no check because EasyEDA merges),
and anything unplanned is deleted – old tracks have come back after a reload before.

**DRC only after reload:** right after API changes the DRC reported 320 false connection errors; saved and reloaded:
0. `route all` saves, closes and reopens the PCB before its DRC.

## 7.6 Pours

`[[boards.<b>.pours]]`: net, layers, `plane`, `stitch`. Filled with `easyeda_pcb_rebuild_copper` per net (status
`readback-mismatch` is harmless). With `stitch = "BOTTOM"` edakit fills once keeping islands, puts a via into every loose
island on that side where it overlaps the pour of the other side (with clearance), then fills again without islands.

## 7.7 Silkscreen

`edakit silk apply` hides the designators of the configured sides, exports Gerber (so the silk layer shows only the
footprints' own print), places every designator of the `designators` side at the first free spot (above, below, right,
left, then vertical, then at the corners; not on pads, footprint print, parts or other labels; over a tented via only as
last resort; test points first), then exports again and checks that no own silkscreen lies on a solder-mask opening
(JLCPCB cuts it off there) – target 0 mm² – and runs the DRC. Pictures per side in `<artifacts>/silk_<board>_<side>.png`.

Good to know:

- Minimum text height at JLCPCB: 1.0 mm; stroke ≥ 0.15 mm (a regular 1.5-mm font had 0.12 mm – use bold).
- On the bottom silk layer EasyEDA mirrors texts by itself (`mirror = false`), but **not** graphics – mirror fills and
  lines yourself.
- JLCPCB prints its order number somewhere unless you place the placeholder `JLCJLCJLCJLC` and choose
  "specify a location" when ordering.
- Run `silk apply` again after every auto-layout and routing – spots depend on parts and vias.

## 7.8 Export for documentation

`edakit export` writes per board the schematic as vector PDF (patched bridge; otherwise stitched canvas tiles), the PCB
PDF, Gerber, BOM, pick and place, netlist, plus a consistent copy of the project file (SQLite backup). Orders are made
from the gate's files, not from these.
