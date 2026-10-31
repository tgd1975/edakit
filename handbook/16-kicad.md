# 16 KiCad as the tool chain

A project draws its boards in EasyEDA Pro or in KiCad – one key in edakit.toml decides
([concept](../docs/concepts/done/kicad-toolchain.md)). The graph, the parts database, the simulation, the board file
with its plan, the routing with Freerouting and every check of the gate are the same for both. Only the EDA project is
the tool chain's: an EasyEDA project driven through the bridge, or KiCad files that edakit writes and kicad-cli reads.

**State 2026-10-30:** built; tested offline against a kicad-cli the tests fake, and in CI against KiCad 10 (the job
`kicad` of tests.yml, KiCad's container image, `tests/test_kicad_live.py`) on the led-bar example. No board has gone
through it to a release yet; 16.8 says what is confirmed and what is open. On a machine with kicad-cli of another major
version (KiCad 9, say) the live tests are skipped with the reason – they hold KiCad 10's behaviour, and a red run there
is no regression; the CI job sets `EDAKIT_KICAD_LIVE=required`, so a missing kicad-cli or another major fails there.

## 16.1 Choosing it

```toml
# edakit.toml
[project]
toolchain = "kicad"          # "easyeda" (default) or "kicad"
```

Without the key a project is an EasyEDA project, exactly as before. One tool chain serves every board of a project.
With `"kicad"` the names of EasyEDA documents in `[boards.<name>]` (`template`, `schematic`, `pcb`) are refused: there
is nothing to name, every board is the KiCad project `<artifacts>/kicad/<board>/`.

What the KiCad side does without: the bridge, the MCP server, Node, the EasyEDA claim (`edakit lock`), the agent
`easyeda-operator`, *Import Changes*, the reload before the DRC, the patched bridge for the schematic PDF. The commands
run kicad-cli in the session; they take seconds.

## 16.2 Setup

KiCad 10, the newest for Ubuntu, from KiCad's PPA – Ubuntu's own packages are older:

```bash
sudo add-apt-repository ppa:kicad/kicad-10.0-releases
sudo apt update && sudo apt install kicad
edakit doctor                # "KiCad 10.0.x (kicad-cli: …)" instead of the Node, server and bridge lines
```

`kicad-cli` must be on the PATH, or `KICAD_CLI` names it. Freerouting and ngspice as for EasyEDA (2.2). `doctor` warns
on another major version: the files edakit writes are KiCad 8's format, which KiCad 10 reads; the flags of kicad-cli
are KiCad 10's.

## 16.3 The KiCad project

Like the EasyEDA project it is generated, not versioned, and rewritten by the steps – `build/` is in the `.gitignore` of
a new project:

| File in `<artifacts>/kicad/<board>/` | Written by | From |
| --- | --- | --- |
| `<board>.kicad_pcb` | `pcb apply`/`parts`/`nets`/`tooling`, `route apply`/`pours`, `silk apply` | plan, graph, SES, silk placement |
| `<board>.kicad_pro`, `<board>.kicad_dru` | `pcb apply` | `[routing]` of the board file: clearance, edge, tracks, via, net classes |
| `<board>.pretty/`, `fp-lib-table` | `pcb apply`, `part build` | the parts database (below) |
| `<board>.kicad_sch`, `<board>.kicad_sym`, `sym-lib-table` | `schematic create` | the sheet of `schematic draw` |

`edakit export` keeps a copy of the folder as `kicad_<board>.zip`, as it keeps the `.eprj2` of an EasyEDA project.
Open the files in KiCad to look at them; whatever is changed there is lost at the next run, as in EasyEDA. A part
moved by hand keeps its spot while it has no row in `[place]`, and `pcb takeover --write` writes it there.

**Footprints** come from the parts database: the entry's `footprint_data` (4.5), else the geometry `edakit part import`
caches from the LCSC data – EasyEDA's footprint, the one JLCPCB's assembly works from, so the CPL needs no rotation
offsets. KiCad's own library is not used: a footprint from it would need a correction of turn and origin, and maybe of
its pad numbers, for every part JLCPCB places (concept, decision 3). A part whose LCSC footprint is wrong or missing
gets `footprint_data`, started by `edakit part footprint KEY --write` from the LCSC footprint (4.5). A part whose
footprint is not cached yet is read from the library at the first `pcb apply` (cache only, the entry is not touched).
The cache holds the library's silkscreen too – lines, circles, arcs, filled regions, the strokes of texts – so polarity
marks print as the library draws them (GEO.mark). A cache from an older edakit lacks it and is read again. Pads: `RECT`
→ rect, `ELLIPSE` → circle or oval, `OVAL` → oval, `POLYGON` → custom with its corners; holes as round or oval drills
along the pad's long side, not plated → `np_thru_hole`.

**Symbols** are the ones `schematic draw` draws (6.5), one per part, turned as the sheet turns it; their pins are the
drawing's pin tips, of length 0 and passive – edakit's checks of stage G reason about drivers, not KiCad's ERC. Nets are
named by labels where the drawing writes a net name or a flag.

**Frames:** inside, edakit computes in EasyEDA's frame (mil, y up, 7.1); a point (x, y) lies at (x mm, −y mm) in the
KiCad files. A bottom-side part is mirrored in local y and turned as EasyEDA does it (`Board.transform`), so every pad
lies on the same spot in both tool chains, and the Gerber files of both share their coordinates.

## 16.4 The flow

The commands are the same; what they do on KiCad:

| Command | KiCad |
| --- | --- |
| `schematic create` / `layout` | writes `<board>.kicad_sch` and checks it at once (16.6); `copy` has nothing to do |
| `schematic check` | kicad-cli's netlist against the graph, and KiCad's ERC (errors only) |
| `pcb parts` / `nets` | the parts and pad nets of the file against the graph; `--write` writes the parts |
| `pcb apply`, `pcb tooling` | one writer: footprints at their rows (fixed ones locked), outline and mounting holes on Edge.Cuts, tooling holes, nets, rules; then every pad against the plan |
| `pcb dump` | the footprints measured from the file – nothing has to be turned first |
| `pcb place --rest` | edakit places the parts without a row (7.4) – KiCad has no auto-layout |
| `pcb autolayout` | refused: `pcb place --rest` |
| `pcb pour`, `route pours` | zones of `[[pours]]`, filled by `kicad-cli pcb drc --refill-zones --save-board`; `stitch` is EasyEDA's |
| `route read` | `<board>_board.json` from the file, in the form EasyEDA's read has |
| `route dsn`/`route`/`check`/`diagnose` | unchanged |
| `route apply` | the SES as segments and vias – the pieces `route.segments` prepares for EasyEDA |
| `route reload`, `save` | nothing to do: the PCB is a file |
| `route drc` | KiCad's DRC with schematic parity |
| `silk apply` / `check` | the same placement (7.7), written into the file; Gerber from kicad-cli |
| `export` | PDFs, netlist, BOM, Gerber ZIP, CPL, `kicad_<board>.zip` |
| `gate --eda` | stages S, L, F on KiCad (`--easyeda` is the same flag) |
| `part build --write` | the board's library and the part's footprints in the PCB from `footprint_data` |

## 16.5 kicad-cli

edakit calls (`edakit/toolchain/kicad/cli.py`, `-v` prints every call):

- `pcb drc --format json --units mm --severity-all [--schematic-parity] --output …` – findings in the form of EasyEDA's
  `drc.json`; with `--refill-zones --save-board` it fills the zones.
- `sch erc --format json --units mm --severity-all`, `sch export netlist --format kicadsexpr`, `sch export pdf`.
- `pcb export gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts --exclude-value
  --no-protel-ext`, `pcb export drill --format excellon --excellon-units mm --excellon-separate-th
  --excellon-oval-format alternate --drill-origin absolute`, `pcb export pos --format csv --units mm --side both`,
  `pcb export pdf`, `pcb render`.
- `pcb export odb --units mm --precision 4 --compression zip` – only with a maker of `[cart] makers` that takes ODB++
  (AISLER). Four decimals, KiCad's most: with its default of two a pad at 62.825 mm is written at 62.82, and SYNC.odb
  sees the step on copper, paste and mask.

The DRC checks whose subject edakit checks itself are off in `<board>.kicad_pro`: footprints against the library
(SYNC.footprint holds them to the parts database), courtyards (the plan), silkscreen overlaps and texts (GEO.silk on the
Gerber files). What KiCad's DRC reports beyond that counts in GEO.drc.

## 16.6 The gate on KiCad

Stages P, G, E: unchanged. S, L, F read the same files, made from the KiCad project:

- **SYNC.schematic:** the netlist kicad-cli exports against the graph (`schematic.compare`), plus the errors of KiCad's
  ERC; the protocol names `<board>.kicad_sch`.
- **L:** `pcb.json` read from the file; `drc.json` from KiCad's DRC. GEO.drc has its KiCad rows: "KiCad DRC without
  findings (other kinds)", "schematic and PCB in sync (KiCad's schematic parity)", and with `drc_rules = "check"` the
  rules of `<board>.kicad_pro` against `[routing]`.
- **F:** kicad-cli's Gerber and drill files under the names the checks know (`gerber.FILES`): the plated holes of
  KiCad's PTH file are split into component holes and vias by the drill's X2 function (`ViaDrill`), else by the vias of
  the PCB; `FlyingProbeTesting.json` is made from the pads of `pcb.json` – it stays out of the ZIP, which holds only
  the Gerber and drill files. SYNC.bom compares the BOM with the schematic's (`bom_kicad.json`), SYNC.cpl the CPL with
  kicad-cli's position file (`cpl_kicad.csv`). With a maker that takes ODB++ (AISLER), `odb_<board>.zip` comes from
  `pcb export odb` and SYNC.odb holds it to the run's files as it holds EasyEDA's; a failed export leaves kicad-cli's
  message in `odb_error.txt`, which SYNC.odb names. KiCad has no free pads, so a tooling hole is a footprint `TH<n>`
  (`board_only`, out of BOM and position file, `dnp`): its ODB++ lists it as a component with the attribute `.no_pop`,
  and SYNC.odb lets it pass only so marked – a maker places no part that carries it. `edakit export` writes the same
  file.

The Gerber reader takes what KiCad writes: aperture macros (RoundRect, RotRect, Outline, FreePoly) and polygon
apertures become regions of their outline, X2 attributes are skipped; EasyEDA's files are read as before. The fab hash
is computed the same way; its value is the tool chain's, so a fab sign-off lapses when a project switches.

## 16.7 Switching a project

1. `toolchain = "kicad"` in `[project]`, the EasyEDA document names out of `[boards.<name>]`.
2. Every part needs a row in `[place]` (SYNC.plan): a board placed in EasyEDA has them after `pcb takeover --write`
   there; otherwise `pcb place --rest --write`.
3. `schematic create`, `pcb apply`, `route all`, `silk apply`, `gate --eda`.

The layout hash stays as long as `geometry.json` does; the sign-offs of scope `fab` lapse.

## 16.8 What KiCad 10 confirmed, what is open

Confirmed by the CI job `kicad` on the led-bar example (KiCad 10.0, its container image):

- KiCad reads the schematic edakit writes (KiCad 8's format); its netlist is the graph, its ERC has no error;
- KiCad reads the PCB; `pcb drc --refill-zones --save-board` fills the zones; the DRC's JSON, with schematic parity,
  has nothing but the connections the routing has not made yet. The first run found every pad in conflict with the
  schematic: local labels name a net "/GND" – the schematic has global labels since;
- the flags of 16.5 for Gerber, drill and position file; the file names of the export; the Gerber reader on KiCad's
  files; the position file's place and turn of every part against `pcb.json` (SYNC.cpl), on the bottom too: a part at
  90° and one at 180° keep their turn in the position file (neither -a nor 180-a);
- the frames: KiCad's own Gerber copper lies at every pad edakit reads, also for turned parts and parts on the bottom;
- `route all` on KiCad: Freerouting routed all 18 nets of the example, edakit wrote 208 track pieces and 29 vias, KiCad
  filled the zones, its DRC found nothing. Then `pcb apply` and `silk apply` wrote the file KiCad had saved again –
  two things had to be learnt there: KiCad 10 names nets in items by name, and leaves out
  `(filled_areas_thickness no)`, which under KiCad 8's version gives a fill a stroke of `min_thickness` – and the DRC
  found nothing again;
- stages L and F of the gate on KiCad's export of the routed board: SYNC.pcb, GEO.copper (the copper of KiCad's Gerber
  files: every net connected, no short), GEO.drc, SYNC.footprint, SYNC.plan (every part with a row, every part where
  the plan puts it, measured by `pcb dump` from the file), GEO.hole, GEO.spacing, GEO.ring, GEO.pour, SYNC.bom, SYNC.cpl
  and FILES.set pass – JLCPCB's stock (PARTS.stock) and the track widths from the simulation (GEO.width) left out;
- the ODB++ of `pcb export odb` (16.5) against the files of the same run: SYNC.odb passes on every layer, the drill
  hits, the profile, the parts with place, rotation (ODB++ clockwise) and side – parts at 270° among them – and the nets;
  the tooling holes carry `.no_pop` (kicad-cli 10.0.6, 2026-10-31; `test_kicad_odb_is_read_and_equals_the_runs_files`).

Open – the first runs on a real project, the led-bar example as a KiCad project, then the Christmas bell (the steps
are in the concept, "Live test"):

- footprints from the real LCSC data (the tests use footprints of their own): silkscreen, polygon pads, slots;
- the gate `--eda` end to end with the sign-offs, `export`.
