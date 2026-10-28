# 8 The release gate

Only the gate creates the files that go to the manufacturer, and only the current release may be uploaded: the run
whose manifest says `"released": true` – a newer released run supersedes it (8.3). The gate runs every check, on the
files themselves, and writes a test protocol.

```bash
edakit gate              # P, G, E and the project's checks before S – offline, seconds
edakit gate --easyeda    # plus S, L, F and the project's checks after F – EasyEDA with the bridge, minutes
```

Before each stage – each project check, and with `--easyeda` each board of stages L/F – the gate prints
`[x.x min] step n/m: <stage>` (11.3).

"Guaranteed correct" is not reachable with any tool chain. Reachable is:

1. Every known error class has an automatic check, and every check was seen red once.
2. What cannot be automated is a manual check in the sign-off file, signed for exactly the checked state.
3. After delivery an acceptance test of every board checks the assumptions by measurement.

## 8.1 Stages

| Stage | What | Checks |
|---|---|---|
| P – Parts | parts database complete and signed, every part named by its entry, through-hole leads fitting their holes and, formed for the board, fitting only one way round, own parts equal to their source, parts orderable, a supplier per part | P-1, P-3, P-4, P-5, P-6, P-7, P-8, G-9 (chapter 3, 4) |
| G – Graph | rule checks; with quoted values (6.6) G-19 on this run's simulation; with `[project] requirements` the requirements file (3.6); the project scripts: their entries resolve into one order, their results are current (8.6) | G-1 … G-23 (chapter 3), `scripts` |
| E – Simulation | operating points, stress, function, every LED checked, transient runs; with sim.json `copper` on the routing of `edakit route` as it is | E-1 … E-5 (chapter 5) |
| *project checks* | e.g. K – the board fits its stand | `[scripts.<name>]` of kind `check`, phase `export`, and `[[release.stages]]` – see below |
| S – Schematic | EasyEDA schematic = graph | S-2 per board |
| L – Board | PCB = graph and plan, copper from the Gerber files, the circuit's hand-over kept, pads apart, silkscreen as printed, hand-soldered joints clear, the visible side's print as the board file puts it | L-1 … L-19 |
| F – Manufacturing | BOM, stock, pick and place, Gerber set, order settings | F-1 … F-6 |
| *project checks after F* | e.g. a check of this run's Gerber files | `[scripts.<name>]` with `at = "after F"` – see below |

A bought board on a cable (`bought = true`, 4.5) is in stages P, G and E like any board. Stages S and L/F leave it out
with one information row each (`S-2` and `L`: "bought board – no schematic, PCB or manufacturing files"); F-4, the
manifest and the protocol header ("bought, not made: usb") count the made boards only.

**Stage L** (per board, `edakit fab`):

| Check | What | Why it exists |
|---|---|---|
| L-1 | parts in the PCB = graph; every pad carries the graph's net; every graph pin has a pad | the import may lose or mismatch parts |
| L-2 | copper from the **Gerber files**, rasterised at 0.02 mm, layers joined through plated holes, pads from FlyingProbeTesting.json, nets from the graph: every net connected, no short, every pad present | do not trust EasyEDA – check what goes to the factory |
| L-3 | EasyEDA DRC 0 (after save and reload), two rows: other kinds; schematic and PCB in sync – an Import Changes item with no difference in `netlist_diff.json` is "EasyEDA waits for the import acknowledgement" (still a fail, one click), otherwise the differences and `pcb parts --write` / `pcb nets --write` | |
| L-4 | footprint per part = parts database | a swapped footprint variant |
| L-5 | track width ≥ IPC-2221 for 1.5 × the simulated current (fail), ≥ class width (warn), voltage drop upper bound (info); `route check` measures the same on the SES and the fixed wires before writing (7.5) | power tracks too thin |
| L-7 | fixed parts in the PCB = plan (± 0.02 mm, rotation, side); the plan itself without findings | a part moved by hand or by the auto-layout |
| L-8 | every "+" and "−" of the silkscreen next to a pad of that sign: the PCB texts "+", "−", and the "+" a footprint draws as two crossing strokes in the **silk Gerber files** (each 0.3–2 mm, as long as the other, at right angles, middles within 0.1 mm). Each is compared with the nearest pad on its side whose role has a sign – `anode…`, `plus…`, `vbus` "+", `cathode…`, `minus…` "−". Strokes of a PCB text with a "+" are that text (a "+5V" is a label); a cross inside the box of a `[[silk.art]]` item is artwork. `waive: {"L-8": "…"}` on the nearest part lists its sign as waived | the footprint of a 5-mm LED printed "+" at the cathode: L-8 read only PCB texts and gave the cathode no sign, so nothing saw it; a review did, before five boards would have been assembled with the LED turned (4.4) |
| L-9 | every through hole takes its lead at nominal size (lead data in the parts database); worst case (hole −0.08 mm, lead + tolerance) below 0.05 mm play or plated slots narrower than 0.5 mm: warning per part. P-7 runs the same test before the layout, on the footprint geometry (3.3) | two parts whose leads would not have fitted the library holes |
| L-10 | every pad sits where the library footprint has the pad with that number (`pad_map` for intended swaps) | a pad swap that was reset by EasyEDA |
| L-11 | short current loops (`[[loops]]` of the board file and `layout.loops` of the graph): shortest path over tracks per pad pair within its limit | a switching regulator loop routed 61 mm around the board |
| L-12 | the plan keeps the circuit's hand-over: `layout.fixed`, `.edge`, `.near` of the graph, a decoupling capacitor of its own next to every IC (7.4) | the auto-layout put a decoupling capacitor 24 mm from its IC; what the circuit designer knew got lost on the way to the layout |
| L-13 | pads of different parts on different nets at least the routing clearance (`clearance_mil`) apart on every copper layer both are on; a pad without a net counts as a net of its own, pads of one part are not compared. Measured as `route check` measures it (7.5), on the pads of `route read` (`<artifacts>/route/<board>_board.json`) – pcb.json has no pad shapes –, and only while every pad there sits where the PCB has it, on its layer and net; otherwise L-13 fails and asks for `route read`. `waive: {"L-13": "…"}` on one of the two parts or nets lists the pair as waived | two resistors stood with their pads 0.09 mm apart: the plan compares boxes, `route check` measured only tracks and vias, and only EasyEDA's DRC could have seen it, after the copper was written |
| L-14 | on every side that is assembled (`[release] assembly` `sides`), SMD pads of different parts on different nets at least the paste gap (`paste_gap_mm`, 0.4 mm) apart, so that the stencil keeps a web between their prints; a pad without a net counts as a net of its own, pads of one part, through-hole pads and pads on a side that is not assembled are not compared. Measured on the pads of `route read` like L-13, and only while they are the PCB's. `waive: {"L-14": "…"}` on one of the two parts or nets lists the pair as waived | the paste of a ground pad and a transistor base pad of neighbouring parts was 0.06 mm apart: above every copper rule, a bridge in reflow that the bare-board test cannot see; the layout review found it |
| L-15 | copper per layer on L-2's raster of the **Gerber files**, widened to the outline: the copper share of the board area (without mounting and NPTH holes) and the largest copper-free circle inside the pour outline (the outline `pcb pour` pours, 7.6) – information; on a layer the board file pours (`[[pours]]`, default GND on both) a circle above `[copper] max_bare_mm` (5 mm) warns, a share below `[copper] min_cover` warns, and on every layer a copper piece that touches no pad (FlyingProbeTesting.json), via or plated hole warns, with its area and place. Copper inside an NPTH or mounting hole is drilled away. One row per layer, so an accepted warning covers its layer | EasyEDA drops every pour piece without a pad of its net: half the back of a released board stayed bare (47 % copper, a copper-free circle of Ø 9.7 mm) where ground had no pads, with DRC 0 and every check passed; it was seen by eye before the order |
| L-16 | every plated hole keeps JLCPCB's annular ring on TOP and BOTTOM (2 layers, 1 oz): a component hole 0.18 mm, below 0.20 mm a warning per part, a via 0.05 mm (via Ø ≥ hole + 0.1 mm) – measured in the **Gerber files** from the hole's edge to the nearest point without copper, so a pad, a track or a pour around the hole counts alike; and every two plated holes, also two of one part, keep JLCPCB's hole-to-hole spacing edge to edge: 0.45 mm when a component hole is one of them, 0.2 mm between two vias. Vias are the holes of the via drill file, the other plated holes are named by the through-hole pad of pcb.json at their place. Within 0.001 mm counts as kept (EasyEDA keeps mil and writes mm). `waive: {"L-16": "…"}` on a part or net lists its holes as waived | an RGB LED at 1.25 mm pitch had its holes widened for its legs (L-9) to 0.80 mm with pads of 1.06 mm: a ring of 0.13 mm, below the fab's minimum of 0.18 mm, passed the gate; via pairs 0.47 mm apart were flagged by a review against a figure from memory, where the fab's table allows 0.2 mm |
| L-17 | the silkscreen from the **Gerber files** (silk, mask, outline), per side. edakit's own print on a solder-mask opening fails: the designators, texts and artwork of `silk apply`, i.e. what is not in the print `silk apply` found before it placed anything (it keeps that in `<artifacts>/silk_footprints_<board>/`). Warnings: other print on an opening, one per part (the part of the nearest pad); print beyond the board outline, one per side; a part of the `designators` side without a visible designator (read with the PCB), group label (`[silk] groups`) or line in `[silk] unlabelled`; a text height edakit prints below 1.0 mm (`label_h_mm`, `board_label_h_mm`, `h_mm` of `[[silk.texts]]`). Spots below 0.0005 mm² are rounding; a side or part counts from 0.001 mm² | designators lost after reroutes and a test point never labelled were found on pictures or in a review; the released board passed the gate with footprint print on the mask openings of 11 parts, which JLCPCB clips, and 3.3 mm² of print beyond its outline |
| L-18 | with `[routing] hand_solder_keep_mm` (0 = off): on the solder side of every through-hole pad of a part with `bom: false` – the layer the part does not sit on – no via and no pad of another net closer than the keep, copper to copper; a pad without a net counts as a net of its own, the part's own pads are not compared, tracks do not count. Pads as `route read` saw them, like L-13; vias from the via drill file, with the net of the tracks of pcb.json that end on them – a via no track ends on counts as another net's ('via (no track, net unknown)'). `route check` measures the same before writing, and `route dsn` keeps vias away (7.5). `waive: {"L-18": "…"}` on the joint's part or net, or on the other part or net, lists the pair as waived | the layout review found a via 0.25 mm from a hand-soldered LED joint – a bridge would have put 5 V without its resistor on an LED –, a via 0.26 mm between potentiometer pins and a resistor pad 0.37 mm from an LED joint; every check had passed |
| L-19 | with `[looks]` (7.5): every PCB text on the silkscreen of the visible side (pcb.json `strings`) is one the board file puts there – the board label when its side (`board_label_side`, default the `designators` side) is the visible one, the text of a `[[silk.texts]]` entry of that side, and, when `[silk] designators` is that side, a designator of the board or a key of `[silk] groups`; while `[silk] designators` names the other side, no part on the visible side shows its designator (read with the PCB, as L-17). One fail per text or part, with side, text and position: `BOTTOM (visible): D31 shows its designator – [silk] designators is top`, `TOP (visible): text 'TEST' at (15.0, 3.0) mm is neither the board label nor a [[silk.texts]] entry of this side`. The footprints' own print is no PCB text (L-8, L-17), artwork is fills; a "+" placed by hand as a text goes into `[[silk.texts]]`, where L-8 still reads it. `waive: {"L-19": "…"}` on a part lists its designator as waived | a part placed again after `silk apply` (a footprint change) came back with its designator on the LED side, whose rule was designators off and the version line as the only text; every check passed and the layout review rated it "block" |

With `[looks]` in the board file (7.5), stage L adds a row of its own (ID `L`, no check of the catalog): the visible
side's track length from pcb.json, every layer's in brackets, and the vias of the via drill file – information, and
a warning per limit (`max_track_m`, `max_vias`) the side exceeds, accepted or fixed like any warning – and runs
L-19 on the side's print. In the reference
project the layout review measured the LED side by hand at every round; the row has the numbers in the protocol.

**Stage F:**

| Check | What |
|---|---|
| F-1 | BOM generated **from the graph** in JLCPCB format = EasyEDA's BOM per designator; every LCSC number in the parts database; parts with `bom: false` left out on purpose |
| F-2 | every BOM line in JLCPCB's public assembly catalogue with stock for `quantity` boards (otherwise only pre-order), under the MPN of its parts entry; another class than `jlc_class` warns – P-4 checks the same and more from the stock snapshot when the part is chosen |
| F-3 | pick and place: every BOM part exactly once, side and rotation = PCB; sides and SMD-only as `[release] assembly` says (Economic PCBA: one side, SMD only; two SMD sides need Standard PCBA) |
| F-4 | Gerber ZIP, BOM and pick and place from the same run; `fab/manifest.json` with SHA-256 per file, the state hashes and the fab hash (8.2) |
| F-5 | Gerber set complete (a missing file is named here, and L-2, L-8, L-9 and L-17, which read it, report it as not checked); outline and mounting holes from the outline layer = plan (± 0.2 mm); tooling holes in the NPTH file, mask open, no copper in the opening |
| F-6 | only with `[order]` in the board file (8.4): the remark at most 200 characters, ASCII (fail); `thickness_mm` a thickness of JLCPCB's form – 0.4, 0.6, 0.8, 1.0, 1.2, 1.6 or 2.0 mm (fail); the silkscreen colour the one JLCPCB prints on the mask colour – black on white, white on every other (fail); `mark = "specify"` with the placeholder `JLCJLCJLCJLC` on a silkscreen layer of pcb.json, at least 0.8 mm high in `[[silk.texts]]` (fail; no height there: warning); the placeholder with another mark (warning); Economic PCBA with fewer than 2 tooling holes (warning: JLCPCB drills its own); no copper of either side within `tab_copper_mm` of a declared tab zone, measured on the Gerber copper against the Gerber outline (fail, with the distance and the position); the outline stretches free of copper (information) |

Plus P-2: a **polarity sheet** per board – every polarised part drawn from the Gerber data with copper, silkscreen,
pad numbers, pin roles and nets, bottom parts mirrored as seen from below. It is what the second check compares with
the datasheet drawings, and what you compare with JLCPCB's assembly preview.

**Seen red.** No EasyEDA run is needed to test stages L and F. `tests/test_fab_run.py` cuts the example down to its
input stage (J1, D1, C2 on a 30 × 20 mm board) and writes the export for it: the files `edakit fab` collects, the
footprint geometry, the net currents and the board as `route read` saw it (pads with their shapes, for L-13, L-14 and
L-18).
`edakit fab --offline` on that export passes every row. Then each entry of
`FAULTS` builds one fault into a copy: a pad net, a part moved or turned, a short or an open net in the Gerber copper,
a hole too small in the drill file, a changed LCSC number, a part missing from the pick-and-place file, a tooling
hole missing from the NPTH file. The check that should find the fault fails (or warns) and names the part, net or
file. Each test lists every row that fails or warns, so a check that also fires is noticed too. Most faults hit
one check. A few hit two, because the fault touches both: a part turned by 90° (L-7, F-3), a through-hole pad
without its hole (L-9, and GND open in L-2), a copper dot in a tooling hole's opening (F-5, and a loose piece in
L-15), a plated slot 1.2 mm long in a round pad of 1.4 mm (L-9, and its ring of 0.1 mm in L-16). A new check of L or F
gets its fault there.

**Project checks.** A project holds up the release with checks of its own: a script registered in edakit.toml as
`[scripts.<name>]` of kind `check` (8.6, 10.1), or the older `[[release.stages]]` – `{id = "K", name = "Mechanics",
cmd = ["uv", "run", "mech/check.py", "--json"], advisory = true}` –, which counts as a check of phase `export` before
S. Every check of phase `export` is a stage of its own, with its `id` – the reference project's stand:

```toml
[scripts.mechanik]
kind     = "check"
id       = "K"
cmd      = ["uv", "run", "hardware/sockel/sockel.py", "--pruefen"]
about    = "The tree fits the stand: slot, hill, cable, feet (D-36)"
phase    = "export"
advisory = true             # the stand is adapted after delivery anyway (D-37)
```

- **Where it runs:** `at = "before S"`, the default, between E and S, where `[[release.stages]]` always ran – in the
  order `edakit scripts` shows, `after` orders checks among each other; `at = "after F"` after stage F, to read this
  run's manufacturing files – only in `edakit gate --easyeda`: the offline gate lists it as a stage not run, as S, L
  and F.
- **What it gets:** its `cmd` runs in the project folder, with the gate's environment and `EDAKIT_RUN`, the absolute
  path of this run's folder `<reports>/<run>/` – its `sim.json` and `graph_checks.json`, after F `fab/<board>/` with
  `gerber/`, `gerber_<board>.zip`, `bom_<board>.csv` and `cpl_<board>.csv`. It may take 900 s; a
  `[[release.stages]]` sets its own with `timeout`.
- **Its result:** stdout and stderr go to `stage_<id>.txt` in the run's folder. The last stdout line may be a JSON
  list of `[id, check, actual, expected, ok]`, one row each; otherwise one row with the exit code, and 0 passes. The
  rows stand in section 8 of the protocol, the stage with its counts in section 1, a failed row in section 2.
- **A failure** blocks the release. With `advisory = true` it is an advisory finding instead: section 2 lists it
  under "Advisories (do not block the release)", and nobody accepts it.
- **No stamp:** a check runs in every gate; its `reads` only order it among the scripts (8.6).
- **After the export** nothing runs in the gate. A check of phase `order` – the owner runs it at the manufacturer,
  after uploading, before paying – is an unchecked line of section 6 under "after uploading to the manufacturer,
  before paying", which M-2 works through; one of phase `acceptance` – the reference project's camera test of every
  delivered tree – a line of the acceptance list "after delivery, per board", which M-4 works through (8.5). Each line
  has the check's id, name, `about` and command.
- **Entries that do not resolve** (8.6) run none of their checks: stage G fails and names why. `[[release.stages]]`
  run as before.

A mechanics check reads the board – outline, holes, part boxes, heights, lead protrusion, mated plugs – from
`<artifacts>/mech_<board>.json`, which `edakit pcb plan` writes (7.4); the gate does not run the plan, so a check that
needs the file current runs `edakit pcb plan` first.

## 8.2 Hashes and sign-offs

Every run records two hashes in the protocol header, and a run with stage F a third:

- **circuit** (`state_sha256`): graph (with its ground net and check settings), parts database, simulation config
  (and plugin, `[release] state_files`), and the requirements files of `[project] requirements` (3.6, 8.7) – a
  changed requirement voids M-1 and M-6, as a new purpose does: the reviews read the requirements
- **layout** (`layout_sha256`): the board files with the artwork they place (`[[silk.art]]`) and the footprint
  geometry beside them (`<board>.geometry.json`, 7.4), and `[release] layout_files` – of the made boards; a bought
  board has none
- **fab** (`fab_sha256`): what the manufacturer builds from, per made board – every Gerber layer of
  `fab/<board>/gerber/` rasterised at 0.02 mm as L-2 does, in the frame of the board outline (documentation and
  drill-drawing layers left out: nobody builds from them), the drill hits (both ends, diameter) rounded to 1 µm and
  sorted, the rows of `bom_<b>.csv` and `cpl_<b>.csv` sorted; with `[order]` in the board file (8.4) also the order
  settings that change the board as made – the thickness as ordered (`thickness_mm`), the colours of mask and
  silkscreen, the finish and the order-number mark, which stage F writes to `fab/<board>/order.json`; with the method
  (`fab_method`, "raster 0.02 mm v1"), so that a new method shows. The manifest has it with the hash per board and
  file (`fab_layers`). The remark and the tab zones stay out: the remark is free text to JLCPCB, and the tab zones
  reach it only through the remark – neither changes the board as made. A board without `[order]` has no order
  settings in the hash and keeps the fab hash it had.

The raw files differ on every export (a date comment, other aperture numbers, another order of objects), the layout
hash changes with a comment in a board file and does not change when edakit's code, a router option or EasyEDA's pour
fill changes the copper. The fab hash changes exactly when what the factory builds changes – down to one raster point
(0.02 mm, below the manufacturer's tolerance), or a colour, the thickness, the finish or the mark the board is ordered
with. A Pillow update that draws edges differently changes it too: the sign-offs then lapse, a change never passes
unseen.

Each file belongs to one of them or to none (10.1): edakit.toml, the schematic file and the documents of `[docs] files`
are in no hash, so a new order quantity, a note in the schematic or a corrected number (6.6) voids no review. A project
that moved from the one-file edakit.toml (October 2026) records the hashes before and after in `rehashed` of its
sign-off file: the move changed files, not what they say.

**The footprint geometry in the repository.** The hash takes each file with its path, so CI and a fresh clone compute
the same hash only from versioned files. The footprint geometry lay among the artifacts until October 2026
(`<artifacts>/pcb_geometry_<board>.json`, not versioned); `pcb dump` now writes it beside the board file (7.4). A
geometry not moved yet is hashed where it lies, so nothing lapses before the move; `edakit check`, `pcb plan` and the
gate (a note in section 6) give the `mv` command. The move changes the layout hash once – the path, not the content:
sign-offs with scope `layout` are signed again, nothing is rehashed. The circuit and the fab hash stay, so M-1, M-6 and
M-5 with its default scope `fab` keep counting.

**What the circuit hash leaves out.** By default it takes the files byte by byte: a corrected note, a source added
or the `verified` record a datasheet check writes voids M-1 and M-6. `[release] hash_ignore` lists keys that are
documentation, e.g. `["notes", "sources", "description", "verified", "datasheet"]`: the graph and every parts entry
are then hashed as canonical JSON (keys sorted, no whitespace) without these keys, at any depth. A pin, a value, a
rating or an LCSC number still changes the hash. Only keys that no check and no review reads belong in the list.
Two things stay whole whatever the list says: `purpose` of the graph and `compliance` of a parts entry (the
regulatory review M-6 reads them, `purpose.notes` included), and the simulation config, the plugin, `state_files` and
the requirements files stay bytes – the simulation config's `sources` are its supplies, not references, and the
reviews read a requirement whole, its `source` and `reason` included. Turning the list on (or changing
it) changes the hash once: when the sign-off file's `state_sha256` is the hash of the current files with the list
before (none: the bytes), nothing but the method changed – the gate counts the sign-offs, writes the new hash into the
file and records both in `rehashed` (`by` "edakit gate", `hash_ignore`, `state_sha256` [old, new]). When the circuit
changed as well, nothing is rehashed and the sign-offs of scope `circuit` are done again.

The sign-off file (`[project] signoff`, [example](https://github.com/tgd1975/automatic_christmas_bell/blob/main/hardware/signoff.json)) holds manual checks and
accepted warnings. Each counts only if the hash of its scope (`circuit`, `layout`, `fab`) equals the current one. The
fab hash is known only after stage F: in a run without it (the offline gate) sign-offs with scope `fab` are listed as
not checked and do not count.

```json
{
  "state_sha256": "<from the protocol header>",
  "layout_sha256": "<from the protocol header>",
  "fab_sha256": "<from the protocol header of the run whose files were reviewed>",
  "manual": [
    {"id": "M-1", "phase": "export", "scope": "circuit", "text": "critical parts checked again …",
     "done_by": "agent electrical-reviewer (own session)", "date": "2026-10-24", "note": "…"},
    {"id": "M-5", "phase": "export", "scope": "fab", "text": "layout reviewed on the manufacturing files …",
     "done_by": "agent pcb-reviewer", "date": "2026-10-25", "note": "…"}
  ],
  "accepted_warnings": [
    {"match": "L-5 main track width >= practical width*", "scope": "decision",
     "reason": "D-38: 18 mil is above IPC for 1.5 x the current; wider tracks left 16 links open", "by": "owner",
     "date": "2026-10-22"},
    {"match": "L-9 main D2: hole tight*", "scope": "decision", "parts": {"D2": "C2297"},
     "reason": "D-40: 0.09 mm play at nominal size, measured on the part", "by": "owner", "date": "2026-10-22"}
  ]
}
```

| Phase | When | Blocks the release |
|---|---|---|
| `export` | before the files are released (M-1 second datasheet check, M-6 regulatory review, M-5 layout review) | yes |
| `order` | after uploading, before paying (M-2: JLCPCB's assembly preview, BOM tool, price) | no |
| `acceptance` | after delivery (M-4: acceptance test of every board) | no |

Scope `fab` suits what is checked on the manufacturing files: the layout review M-5 and the manufacturer's preview
M-2 (the example and new projects use it). A later gate run whose files and order settings are the same keeps the
sign-off, whatever changed upstream; a run whose files differ, or a board now ordered black or 1.0 mm thick, voids it.
Existing sign-off files keep `circuit` and `layout` as they are. What changed between two runs:

```bash
edakit fab diff 20261025-205344 20261025-224607 [--board B]   # run folder names under reports, or their paths
```

per board and file `equal` or `changed`: for a Gerber layer the area added and removed and the largest changed spots
(XOR of the two rasters, labelled as in L-2) with their bounding box in Gerber coordinates, spots under 0.01 mm² only
counted and summed; drill hits and BOM/CPL rows removed (−) and added (+); the order settings (`order.json`) one by
one, `- mask = "green"` and `+ mask = "black"`. Exit 0 when everything is equal, 2 otherwise.

`match` is an fnmatch pattern over "ID scenario item step" as section 3 of the protocol prints it – for a warning of
the graph checks the ID and the message, e.g. `"P-3 M1 ring: ../ring is not released*"` for an own board that is
not released (4.5). Scope `decision` counts regardless of the hash and must refer to a numbered decision. An
acceptance about particular parts names them in `parts` ({designator: LCSC number}, or the `part` of a component
without one): it counts only while every one of them is still that part in the graph. After a swap section 3 of the
protocol lists it as lapsed ("lapsed: D2 is now C2895549", "D2 is not in the graph") and the warning is not accepted
until the owner judges it again and updates `parts`. Without `parts` an acceptance counts as before. **Only the
owner accepts a warning** – it is a decision. **A manual check an agent can do is signed by the agent's result** (chapter 11): OK → signed with the agent
as `done_by`; not OK → fix the cause, check again.

**Open from the datasheets.** Section 6 of the protocol ends with a list per parts entry of the graph – its
designators, the `open` points of its `verified` sign-off and its `sources` with the word "assumption" (4.1). A point
with `when` (`order`, `acceptance`) is also an unchecked line under that phase's manual checks, e.g. "- [ ] C2297
KT-0805G (D2–D9): VR not specified – 5 V assumed" after M-4, so the acceptance list carries it without copying. The
list is information: it changes neither the decision nor its reasons, and a project without open points gets none.

**Three manual checks are required** even when the sign-off file does not list them: the gate adds each one as open
("M-5 is missing – added as open, every release needs it"), and the run is NOT RELEASED until it is signed. There is
no key to switch them off.

| Check | Phase | Scope | What |
|---|---|---|---|
| M-1 | export | circuit | the critical parts checked a second time against their datasheets – agent electrical-reviewer |
| M-6 | export | circuit | the regulatory review (chapter 15) – agent regulatory-reviewer |
| M-5 | export | fab | the layout review on the manufacturing files of a gate run – agent pcb-reviewer |

A sign-off file that lists one of them keeps its own phase, scope and text (an older M-5 with scope `layout` stays
so). Not everything that can be ordered may be sold or even operated in the EU, and nothing else in the gate looks at
that (M-6).

The lesson behind M-5: the first released run of the reference project had passed every automatic check, and nobody
had looked at the layout as a whole. The layout review agent then found a switching regulator loop routed across the
whole board (now L-11) and that the visible side was crowded with tracks. Since then the layout review is a condition
of the release, not a tool you may use – in the gate's own list, so that a project whose sign-off file never had it
is held to it too. It also ends every layout round that changed placement, routing or pours (skill pcb-round), on the
round's Gerber export, so its findings come before the gate rather than after it: later in the same project a run was
released with about 45 % of one side bare – EasyEDA had dropped pour islands without a pad, and gate, DRC and layout
review all passed it, because none of their inputs showed the copper as filled (now L-15). Both reviewers give every
finding its probability and its cost; a deviation without a realistic consequence is not a finding.

## 8.3 The decision

RELEASED only if every stage ran, no check failed, every warning is accepted, every part is signed, every manual check
of phase `export` is signed – all for the current hashes – and, with `[project] requirements`, every requirement
`must` the user has accepted has passing evidence and every accepted `should` without it is accepted like a warning
(8.7); a draft binds nothing yet. Otherwise NOT RELEASED with the reasons. Exit 0 / 2. Every project check of phase `export` is a stage (8.1): it has to run – one after F runs only
with `--easyeda` – and pass, unless it is advisory; a check of phase `order` or `acceptance` does not hold up the
release, it is a line of section 6.

The protocol names every check with its words next to the ID ("L-9 (hole fits the lead)"), and its section 10, "The
rules behind the findings", gives rule, reason, fix and sources of every check that failed or warned – from the rule
catalog (chapter 14.2), so that the protocol can be read without this handbook. With `[project] requirements` a
section 11, "Requirements", follows it (8.7).

Result folder `<reports>/<YYYYMMDD-hhmmss>/`: `protocol.md`, `graph_checks.json`, `sim.json`, `schematic_<board>.json`,
`fab/<board>/` (Gerber ZIP, BOM, CPL, raw data, with `[order]` the order form `order.md` and the order settings
`order.json`), `fab/polarity_<board>.png`,
`fab/manifest.json`. Archive a released folder in git (`git add -f`) – it is the record of what was ordered.

**One current release.** A project has at most one run that may be uploaded. When the gate decides RELEASED, it
marks every earlier manifest under `[project] reports` that says `"released": true` as superseded by the new run:
`"released": false`, `"status": "superseded"`, `"superseded_by": "<run>"`; `decision` keeps what the gate decided.
The archived folders change – commit them together with the new run. A released run that must not be uploaded after
all (a review found something, the files were wrong) is withdrawn:

```bash
edakit release current                                  # the run, its time, git commit, graph version, files + SHA-256
edakit release withdraw 20261025-205344 --reason "back copper missing"   # "status": "withdrawn", {reason, by, date}
edakit release verify ~/upload/                         # the files about to be uploaded = the current release?
```

After a withdrawal there is no current release until the next RELEASED run; earlier runs stay superseded (manifests
from before this – without `status` – that still say released are superseded by the withdrawn run, so that none of
them becomes current instead). A manifest without `status` reads as before: the newest one that says released is
current, and nothing is rewritten until the next RELEASED run. Whatever reads `released` – `edakit part own` for
the release of an own board (4.5) – skips superseded and withdrawn runs.

`release verify` takes files or folders (a folder: every `.zip` and `.csv` file in and below it) and compares the
SHA-256 of each with the manifests: a file of the current release passes; a file of another run is named with that
run and its status ("from run 20261025-205344 (superseded by 20261025-232212)"); a file of no run is unknown – an
edited CSV, a renamed export. Exit 0 when every file is of the current release, 2 otherwise, 1 for a file that is not
there.

## 8.4 Ordering at JLCPCB (the owner does it)

**The cost before the quote.** `edakit cost` estimates the order for `quantity` boards from the graph, the parts
entries, the board files, the stock snapshot (4.2) and a dated fee table (`edakit/fees/jlcpcb.json`: JLCPCB's
assembly fees with the page and the day they were read, bake, edge rails and PCB prices from real carts):

- the class per board – `[release] assembly.pcba` or its sides, raised to Standard by parts on a second side
  (`side` in `[place]`; a part not placed sits on the first side of `assembly.sides`) and by "Standard Only" parts;
- the PCB at its size (under Standard with 5 mm edge rails on the long edges) or the quoted `[cost] pcb_price`;
- the fees line by line: Economic setup and stencil per order and 3.07 $ per Extended type; Standard setup and
  stencil per assembled side and 1.53 $ per type, Basic included, plus packing; SMT joints; joints JLCPCB solders by
  hand plus the labour per order; through-hole reflow joints; X-ray per placed part; the bake for MSL ≥ 5; a Standard
  order Economic could also assemble is topped up to the handling fee's 14.93 $ difference;
- the parts at their price break – Economic exactly the placements, Standard with JLCPCB's attrition;
- shipping, coupon and VAT (`[cost]`), the items off the board (`[[extra]]`), the budget;
- what drives the cost (the part or side that forces Standard, each Extended type, a bake, an X-ray part, the edge
  rails), the other class beside it, and the change since the last estimate;
- per board whose `[order]` orders another board than the fee table prices (`pcb.board`: 1.6 mm, green mask, white
  silkscreen, lead-free HASL), the settings that differ, as not in the price – JLCPCB may charge extra for another
  thickness or finish, and a colour other than green takes about two days longer:
  `not in the price: thickness 1 mm, mask black ([order]; the fee table prices 1.6 mm, green mask, white silkscreen,
  LeadFree HASL)`. edakit prices neither; without `[order]`, or with its defaults, there is no such line.

Without a stock snapshot the parts have no price. On the reference project the estimate came within about 1 $ of
the cart (USB tree, 2026-10-25: 71.53 $ with the fees of that day against 72.58 $); the fees JLCPCB does not itemise
(bake, X-ray, hand soldering, packing) are values of their own in the table. Run it when a part, a side or the class
changes, not after the first quote.

**Everything else in the same go.** `edakit order` writes, for `quantity` sets, the assembler's BOM (the file F-1
writes), one cart per other supplier and `hand_assembly.md`. A part bought separately (`bom: false`) goes to the
component's `supplier`, else the first supplier of its entry's `order`, else LCSC; items off the board are
`[[extra]]`. Every cart line gets the spares (`[project] spare_pct`, `spare` on the component or item) and is rounded
up to the supplier's minimum and pack size (`moq`, `step` in `order` or the item). The LCSC cart has the columns of its
BOM tool ("LCSC Part Number, Quantity, Comment"), the others "Code, Quantity, Item, Designators". A `C99…` number is
an EasyEDA library entry that LCSC does not sell: no cart line. P-5 warns about a part bought separately that names no
supplier – also one that has only such a number. A bought board (`bought = true`, 4.5) gets no BOM: its parts are in
the carts and in `hand_assembly.md` under the board, marked bought; `edakit cost` prices no PCB and no assembly for it.

**The order form as data.** The form fields that depend on the board go into `[order]` of the board file (10.2):
`finish`, `mark` (`"default"` – JLCPCB prints its number anywhere, `"specify"` – at the placeholder, `"remove"`),
`remark`, the tab zones (`tab_zones`, stretches of the outline in plan mm, with `tab_copper_mm`) and the colours:
`mask` (JLCPCB's "PCB Color": green, purple, red, yellow, blue, white or black) and `silkscreen`. The thickness is
the board file's `thickness_mm`, the value the mechanical model takes (7.4). Without these keys the form's defaults
hold: 1.6 mm, green, white print. JLCPCB prints white on every mask but white, and black on white – `silkscreen`
states the colour the artwork is drawn for, and F-6 fails it on a mask that gets the other one, as it fails a
thickness the form does not offer (FR-4, 2 layers: 0.4, 0.6, 0.8, 1.0, 1.2, 1.6 or 2.0 mm). Every colour other than
green takes two more days at JLCPCB (its quote form, read 2026-10-28); `edakit cost` prices the fee table's board –
green, 1.6 mm, lead-free HASL – and names the settings of `[order]` that differ from it as not in the price. The board
file is in the layout hash, so a changed remark, colour or thickness voids the sign-offs of scope `layout`; the
settings that change the board as made – thickness, colours, finish and mark – are in the fab hash as well (8.2), so
the layout review M-5 of scope `fab` lapses with them too, while a new remark or tab zone leaves it standing. Every
gate run then writes `fab/<board>/order.md` next to the upload files – layers, size, quantity, thickness, the
colours of mask and silkscreen, finish, the mark at the placeholder, the remark; PCBA type and side from
`[release] assembly`, tooling holes "Added by Customer" when the board has `[tooling]`, bake "Yes" when the stock
snapshot gives a BOM part MSL ≥ 5; the tab zones with their nearest copper and every outline stretch with no copper
within `tab_copper_mm` (Gerber coordinates, what JLCPCB sees); the parts bought separately with their supplier
(`edakit order`) – and `fab/<board>/order.json` with the settings the fab hash takes; F-6 checks the settings
against the files. Fill the form from order.md of the released run – with M-5 of scope `fab` its settings are the
ones the review signed – and write tab zones only on stretches it lists as free.

The MCP server cannot order. Lessons from the reference order:

- Upload `gerber_<b>.zip`, `bom_<b>.csv`, `cpl_<b>.csv` of the current release only: `edakit release verify` on the
  files you are about to upload, right before the upload.
- **Economic PCBA** assembles one side, SMD only; a second SMD side or certain parts (large battery holders, some
  modules – "Standard Only" on their JLCPCB part page) need Standard PCBA with a higher setup fee per side. Plan the
  board so the cheap option works (through-hole parts you solder yourself get `bom: false`); P-4 fails a "Standard
  Only" part on an Economic order as soon as `edakit stock` has read it.
- **Tooling holes:** with your own (chapter 7.2) choose "added by customer"; otherwise JLCPCB adds rails or holes.
  F-6 warns about an Economic order with fewer than two – in the reference project they were found only in the quote.
- **Moisture-sensitive parts:** JLCPCB bakes MSL ≥ 5 parts for a fee and includes the 48 h in the lead time; its MSL
  classification may differ from the manufacturer's datasheet – P-4 warns with JLCPCB's value from the stock snapshot.
- **Tented vias** if a side is visible (open vias are holes and tin dots).
- **Order number:** "specify a location" when a placeholder is printed (`mark = "specify"`; the reference cart still
  said "Remove Mark").
- **Remarks** (max. 200 characters, F-6): where panel tabs may and may not go, no V-cut on visible edges. The
  reference remark was written by hand and wrong three times: tabs where a track ran 0.45 mm from the edge, then 202
  characters, then a "1.17 mm free" that a new pour 0.55 mm from the edge made false.
- **M-2** in the assembly preview: rotation and polarity of every polarised part on both sides (compare with the
  polarity sheet), no part missing in the BOM tool, then pay.
- If JLCPCB's DFM check reports something the layout review already accepted or a waiver of the gate names (e.g. an
  annular ring the fab confirmed, L-16), it is in the checklist so nobody panics. L-16 holds rings and hole spacing to
  JLCPCB's table, so a via pair 0.47 mm apart is no finding there.

## 8.5 Acceptance (M-4)

After delivery every board gets a short acceptance test: visual check (polarity of every polarised part), supply
current at the nominal voltage against the simulated value, every LED/output, every input, the firmware's self-test.
Deviation beyond tolerance → find the cause (model, firmware, assembly) before the board is used.

The list is section 6 of the protocol, "after delivery, per board": M-4, the datasheet points with `when =
"acceptance"` (8.2), with `[project] requirements` every acceptance step of a requirement with its ID, and the
project's checks of phase `acceptance` (8.1), each with its command:

```text
- [ ] M-4 Acceptance test of every delivered board: visual check, supply current, every LED, the button
- [ ] R-1: on the USB port of a laptop: all eight LEDs on, the port stays on
- [ ] A abnahme: Camera test of every board after delivery: each LED at its place – `uv run simulator/pico/pruefstand.py mitlesen`
```

M-4 works through it and names the requirements it tested in its note; signed, it lets their acceptance steps pass,
and the requirements whose evidence is such a check (8.7). The list "after uploading to the manufacturer, before
paying" works the same way for M-2: the datasheet points with `when = "order"` and the checks of phase `order`.

## 8.6 Project scripts

A project registers in edakit.toml the scripts that touch edakit's flow (`[scripts.<name>]`, 10.1): one that writes a
file edakit reads, derives something from edakit's data, changes the project library in EasyEDA, or holds up the
release as a check of its own. A script that only reads what edakit made – a review package from the release – stays
unregistered, like every other script of the project. Each entry says what its script reads and writes; when it runs
follows from that and from edakit's steps in their fixed order, so nobody has to write that rule into a skill.

| Kind | What it writes | Its place |
|---|---|---|
| `input` | a file edakit reads: the board file (`board:<b>`, its own sections – every writer keeps the lines of the others, as `pcb place --write` does), an SVG of `[[silk.art]]`, the simulation plugin | before the first step that reads it |
| `derive` | files no edakit step reads: the firmware's pin table, pictures, the enclosure | before `edakit check`, where its result is to be current – before the gate when the script reads what comes after `edakit check` (footprints, routing) |
| `easyeda` | changes in EasyEDA: the project library, `project-library:<b>` | on command only |
| `check` | – | phase `export`: a stage of the gate (8.1), before S, or with `at = "after F"` after stage F on the run's manufacturing files; phase `order` and `acceptance`: a line of section 6, after the export |
| `sim` | – | `[project] sim_plugin`, inside `edakit sim` (5.1) |

`[[release.stages]]` (8.1) take part as checks of phase export before S. The names of edakit's data in `reads` and
`writes`, each with a hash of what edakit has of it offline – `<b>` is a made board; a bought one (4.5) has none of
this data:

| Name | What | Made by | Hash of |
|---|---|---|---|
| `graph`, `parts`, `sim` | graph, parts database, simulation scenarios | by hand, `edakit block`, `edakit part` | the files as the circuit hash reads them – graph and parts without the keys of `hash_ignore` (8.2) |
| `board:<b>` | the board file | by hand, `edakit pcb place --write`, `input` scripts | the board file |
| `project-library:<b>` | the project library in EasyEDA, which `pcb parts` takes the parts from | `edakit schematic create`, `easyeda` scripts | – (in EasyEDA only) |
| `footprints:<b>` | footprint geometry with pads, as `pcb dump` measures it in the PCB: `<b>.geometry.json` beside the board file – one not moved yet in `<artifacts>/pcb_geometry_<b>.json` (7.4) | `edakit pcb dump` | the file it is read from |
| `mech:<b>` | the board as a mechanical model (`mech_<b>.json`, 7.4) | `edakit pcb plan` | the file |
| `routing:<b>` | tracks and vias | `edakit route` | the routing session `route/<b>.ses` and the stitching vias of `route pours` (`route/<b>_stitch.json`) |
| `gerber:<b>` | the gate run's manufacturing files | `edakit gate` | the board's `fab_layers` (8.2) in the last run with stage F – with one board the run's fab hash |
| `release` | the current release (8.3) | `edakit gate`, `edakit release withdraw` | its `fab/manifest.json` |
| `firmware` | the firmware contract, with `[firmware]` (3.5) | `edakit firmware` | the file `[firmware] out` |

Anything else is a path relative to edakit.toml. A folder holds the files in it, and an edakit file named by its path
is its data: `hardware/boards/main.toml` is `board:main`, `hardware/boards/main.geometry.json` `footprints:main`,
`build/edakit/route/main.ses` `routing:main`, the files of a gate run's `fab/main/` `gerber:main`.

Data that does not exist yet – no board file, no geometry, no routing, no gate run with stage F, no current release –
hashes as `absent` until it is made. A run from before the fab hash has no `fab_layers` in its manifest: they are
computed from its files, as `edakit fab diff` does. The project library has no hash: it is in EasyEDA only, and edakit
cannot read it offline. What changes it is an `easyeda` script, and that the script ran is what will tell edakit. So
an `easyeda` script writes `project-library:<b>`, never `footprints:<b>`: the geometry is edakit's own data, measured
anew from the PCB by `pcb dump`.

`edakit check` resolves the entries with edakit's steps into one order and reports what keeps them from it, as errors
with the ID `scripts`:

- `kind` and the fields of the kind are there, and no field of another kind
- every data name is edakit's, with a made board of `[boards]`; `firmware` only with `[firmware]`
- a script writes files, an input also `board:<b>`, an `easyeda` script changes `project-library:<b>`; graph, parts,
  sim and edakit's other data – `footprints:<b>` too – are written by edakit or by hand
- scripts that write the same file or change the same data run in a fixed order through `after`; a script that writes
  what it reads gets the version of the one before it
- an edakit step needs what an input writes – directly or through another input – and nothing a derive writes
- the steps, the data and `after` make no cycle; the message names the cycle with the data on each edge. Read-backs
  of a later round do not count: `edakit check` reads the footprints (P-7), `edakit sim` the routing (`copper`),
  `pcb place` the footprints
- a check has an `id` of its own – no stage of the gate, no sign-off, no ID of the rule catalog, none twice with
  `[[release.stages]]` –, a `phase`, and reads `gerber:<b>` only at `"after F"`
- `after` names other entries of `[scripts]`

```text
ERROR   scripts  review: in a cycle – review –[stamp]→ edakit gate –[release]→ review
```

A derive that reads the release cannot be checked by the gate that writes it. The gate reports the same in stage G,
with the ID `scripts`: entries that do not resolve fail it – edakit refuses them.

**Stamps.** For every script of kind `input`, `derive` and `easyeda`, `hardware/scripts.lock` keeps what its result was
made from at its last run: its `cmd`, the script itself and the hash of everything it `reads`. The file is versioned,
so that the CI sees the stamps too, and it is in no hash (8.2).

- **The script itself** is the first word of `cmd` that names a file – relative to edakit.toml, or inside the project
  when it is absolute: `hardware/art/make_art.py` of `["python", "hardware/art/make_art.py"]`, also
  `../../hardware/art/make_art.py` of a variant. Options (`-…`) and the system's programs do not count. A `cmd` that
  names no file – `make art`, `python -m art` – stamps its `reads` only; the script's files then belong in `reads`.
- **What it reads** hashes as its name says (table above), a file as its bytes, a folder as every file below it with
  its path in the folder – without `__pycache__`, `*.pyc`, `*.pyo` and names that start with a dot (`.git`, editor
  files).

Compared with its stamp, a script is

| State | When |
|---|---|
| current | every hash as stamped |
| outdated | `cmd` changed, a hash changed, `reads` names something the stamp lacks, or it comes after a script that is outdated or never ran – through `after`, or because it reads what that script writes |
| never run | it has no stamp |

What is absent here is not compared, whatever the stamp says: the routing, the mechanical model, the Gerber data and
the release live in `build/`, which a fresh clone and the CI do not have, and a file outside the project – a system
font – may be missing on another machine. A note names it, and the stamp counts again where the data is; data made
since a stamp that found it absent is a change. The project library has no offline hash: a script that reads
`project-library:<b>` is not compared there either – that an `easyeda` script ran will tell, once edakit runs them
(`edakit run`, not built yet).

| Kind | Outdated or never run: `edakit check` | the gate, stage G |
|---|---|---|
| `input` | error | fails |
| `derive`, `easyeda` | warning | a warning: the script runs, or the owner accepts it (`"match": "scripts sockel outdated*"`, 8.2) |
| `check`, `sim` | – (no stamp: a check runs in every gate and its result is the gate's protocol, 8.1; the plugin runs inside `edakit sim`) | |

```text
ERROR   scripts  kunst outdated: hardware/art/make_art.py changed – Bell, greeting, star and snowflake as shapes for the silkscreen
NOTE    scripts  baumgrafik: not compared – routing:tree absent here
```

A current script is a passed row of stage G. **No command runs an `input`, `derive` or `easyeda` script yet** – the
gate runs the checks (8.1): run it by hand – its `cmd`, in the project directory –, then record the run, and commit
the lock with what the script wrote:

```bash
edakit scripts                 # every script: kind, state, about, cmd, last run; the order, and what is to run
edakit scripts stamp kunst     # kunst ran: its stamp into hardware/scripts.lock
```

```text
kunst  input    outdated: hardware/art/make_art.py changed
                Bell, greeting, star and snowflake as shapes for the silkscreen
                python hardware/art/make_art.py
                stamped 2026-10-28 21:33 by tobias

order: edakit firmware → edakit check → edakit sim → … → edakit route all → kunst → edakit silk apply → edakit gate
```

`edakit scripts` exits 0 when every script is current, 2 when one is outdated or never ran or the entries do not
resolve, 1 when the lock cannot be read. `stamp` refuses – and writes nothing – a name that is not in `[scripts]`, a
check, entries that do not resolve, and a script whose `writes` are not there ("run it first"); it drops the stamps of
scripts no longer in `[scripts]`. What the author leaves out of `reads` is not noticed – the system font the bell's
`make_art.py` draws with –, and the entry's `check`, an exact check for when the stamp is not enough, does not run yet.

## 8.7 Requirements

With `[project] requirements` (3.6) the gate holds the circuit to what it must do. A file the key names that is
missing or not valid stops the gate before its first stage (exit 1, no run folder), as it stops `edakit check`. Stage
G runs G-20 to G-23 on the file (3.3); a finding about a draft is information there. After the stages, every
requirement's evidence is evaluated against this run:

| `verify` | passes when | otherwise |
|---|---|---|
| `rows` | at least one row of the protocol matches – a pattern over "ID scenario item check", matched as `accepted_warnings` match (8.2), the rows of the simulation included – and none of them failed. An advisory finding of a project check did not pass; a warning, a waiver or an open sign-off is no failure | no passing evidence; when no row matches because the pattern's stage did not run – S, L and F in the offline gate –, the protocol says so |
| `signoff` | the manual check is signed for the current hash of its scope – only then does it count at all (8.2) – and its `note` names the requirement's ID, e.g. `"note": "OK for state 1a2d…; R-4: R2 holds LED_OE high until the firmware drives it"` (R-40 does not name R-4) | phase `export`: no passing evidence; a later phase (M-2, M-4): open after the export |
| `accept` | M-4 is signed | open after delivery; the step is on the acceptance list of section 6 (8.5) |
| `script` | the project's check (8.1) – a `[scripts]` name, the `id` of a `[[release.stages]]` – passed in this run: it ran, and no row of its stage failed; an advisory finding did not pass either. A check of phase `order` or `acceptance` counts like an `accept` step: M-2 or M-4 is signed | phase `export`: no passing evidence – also when the check did not run (one after F in the offline gate) or is not part of the run (entries that do not resolve: stage G says why); phase `order` or `acceptance`: open after the export, the check is a line of section 6 |

What an accepted requirement without passing evidence does to the release, its binding says:

| Binding | Without passing evidence |
|---|---|
| `must` | blocks the release: "1 requirement(s) must without passing evidence: R-4 (section 11)" |
| `should` | a warning – it holds up the release until the owner accepts it in `accepted_warnings`, matched over "R-3 <its text>": `{"match": "R-3 *", "scope": "decision", "reason": "D-9: …", "by": "owner", "date": "…"}` |
| `may` | information |

What is only tested after the export does not hold up the release: as long as nothing else failed, an acceptance
step that M-4 has not signed yet, a project check of phase `order` or `acceptance` whose list is not signed yet, or a
sign-off of phase `order` or `acceptance` that is still open, leaves the requirement "open after the export".

**A draft binds nothing yet** (`status = "draft"`, or no `status`). It is evaluated like any requirement and listed in
section 11 with its evidence, marked as a draft – `→ draft, not binding yet – no passing evidence` –, but it never
blocks the release and needs no acceptance in the sign-off file, whatever its binding. What G-20 to G-23 find about it
is information in stage G (`edakit check` warns about it, 3.6). Errors and blocking start once the user has set
`status = "accepted"`. A dropped requirement is listed, not evaluated.

**Section 11 "Requirements"** of the protocol lists every requirement with binding and status, each piece of evidence
with what it found, and the result; the gate's output has it in one line (`requirements: 2 passed, 1 open after the
export, 1 draft`) – a draft counts as a draft, whatever its evidence did. It follows section 10, so that every other
section keeps its number, and a project without the key has none. From the tests' led-bar
(`tests/test_requirements.py`), offline:

```markdown
- **R-1** must, accepted: With all eight LEDs on, the board draws at most 500 mA from J1 at 4.75 to 5.25 V. → open after the export – does not block the release
  - rows `E-3 * J1 current from the supply` – 12 rows: 12 passed
  - accept: on the USB port of a laptop: all eight LEDs on, the port stays on – after delivery: M-4 not signed yet (section 6)
- **R-4** must, draft: From power-up until the firmware drives LED_OE low, no LED carries more than 10 µA. → draft, not binding yet – no passing evidence
  - rows `E-3 * D? LED dark` – 48 rows: 48 passed
  - signoff M-1 – not signed for this state (section 6)
```

Accepted as it stands, R-4 would block the release until M-1 is signed with a note that names it.

A requirement whose evidence is a project check – the rule watcher of the tests, a check `W` of phase `export`
(`tests/test_requirement_checks.py`) – passes or fails with the check's rows in this run:

```markdown
- **R-5** must, accepted: Until the firmware drives LED_OE low, no LED lights. → passed
  - script `rule-watcher` – check W: 1 row: 1 passed
```

**Signing for a requirement.** A reviewer whose check a requirement names in `verify` – the agent electrical-reviewer
for `signoff = "M-1"`, regulatory-reviewer for `"M-6"`, pcb-reviewer for `"M-5"` – judges it and names the
requirements it found met in the note it signs with; its result gives the line,
`M-1: OK for state 1a2d…; requirements met: R-4, R-5`. An ID in the note is passing evidence, so a requirement the
review did not find met stays out of the note and is a finding of the review. The sign-off file needs no other field.
Because the requirements files are in the circuit hash (8.2), a changed requirement voids M-1 and M-6, and the next
signature names it again.
