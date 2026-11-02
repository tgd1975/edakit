# 16 KiCad as the tool chain

For a project that draws its boards in KiCad ([concept](../docs/concepts/done/kicad-toolchain.md)). EasyEDA Pro is
the default – edakit was built around it and JLCPCB –, and KiCad is the other choice; 16.1 says when to take which.
After this chapter you can choose, set KiCad up, switch a project and know what each command and each gate stage does
on KiCad's files. The short way: [Lay out the board](../docs/steps/09-lay-out-the-board.md).

> **State 2026-10-31:** built; tested offline against a kicad-cli the tests fake, and in CI against KiCad 10 on the
> led-bar example (what is confirmed, 16.8). The first board released through it is the 555 blinker of chapter 18,
> with KiCad 10.0.6.

The graph, the parts database, the simulation, the board file with its plan, the routing with Freerouting and every
check of the gate are the same for both tool chains. Only the EDA project is the tool chain's: an EasyEDA project
driven through the bridge, or KiCad files that edakit writes and kicad-cli reads.

## 16.1 EasyEDA Pro or KiCad

Both give the same checks, the same gate and the same manufacturing files. They differ in how edakit reaches the EDA
project:

| | EasyEDA Pro, the default | KiCad 10 |
| --- | --- | --- |
| Take it when | you work in EasyEDA already, or want the tool chain edakit's projects were built on | you want open files, no bridge and no click, or a chain without a noncommercial licence |
| The EDA project | you create it once; edakit drives it through the bridge | edakit writes it; kicad-cli reads it |
| By hand | create the project, one *Import Changes* ([upstream](../upstream/README.md) lists each click) | nothing |
| Parallel sessions | one at a time per machine: the claim (11.2) | no limit: each board has its own files |
| Footprints | EasyEDA's library, which JLCPCB's assembly works from | the same LCSC data, cached by edakit (16.3) |
| Licence | EasyEDA Pro proprietary, easyeda-mcp-pro PolyForm Noncommercial | KiCad GPL-3.0 |
| Released on it | pytree, the Christmas bell, the coin cell of [walkthrough 17](17-walkthrough.md) | the 555 blinker of [walkthrough 18](18-walkthrough-kicad.md); CI against KiCad 10 (16.8) |

`/edakit:new-project` asks for it once; a project switches later as 16.7 says.

```toml
# edakit.toml
[project]
toolchain = "kicad"          # "easyeda" (the default) or "kicad"
```

Without the key a project draws in EasyEDA Pro, the default. One tool chain serves every board of a project. With
`"kicad"` every board is the KiCad project `<artifacts>/kicad/<board>/`, and the names of EasyEDA documents in
`[boards.<name>]` (`template`, `schematic`, `pcb`) are refused – there is nothing to name.

The KiCad side does without the bridge, the MCP server, Node, the EasyEDA claim (`edakit lock`), the agent
`easyeda-operator`, *Import Changes*, the reload before the DRC and the patched bridge for the schematic PDF. The
commands run kicad-cli in the session and take seconds.

## 16.2 Setup

KiCad 10, the newest for Ubuntu, comes from KiCad's PPA – Ubuntu's own packages are older:

```bash
sudo add-apt-repository ppa:kicad/kicad-10.0-releases
sudo apt update && sudo apt install kicad
edakit doctor                # "KiCad 10.0.x (kicad-cli: …)" instead of the Node, server and bridge lines
```

`kicad-cli` must be on the PATH, or `KICAD_CLI` names it. Freerouting and ngspice are installed as for EasyEDA (the
installation, 2.2). `doctor` warns on another major version: the files edakit writes are KiCad 8's format, which KiCad
10 reads, but the flags of kicad-cli are KiCad 10's.

## 16.3 The KiCad project

Like the EasyEDA project, it is generated, not versioned, and rewritten by the steps; `build/` is in the `.gitignore` of
a new project.

| File in `<artifacts>/kicad/<board>/` | Written by | From |
| --- | --- | --- |
| `<board>.kicad_pcb` | `pcb apply`/`parts`/`nets`/`tooling`, `route apply`/`pours`, `silk apply` | plan, graph, SES, silk placement |
| `<board>.kicad_pro`, `<board>.kicad_dru` | `pcb apply` | `[routing]` of the board file: clearance, edge, tracks, via, net classes |
| `<board>.pretty/`, `fp-lib-table` | `pcb apply`, `part build` | the parts database (below) |
| `<board>.kicad_sch`, `<board>.kicad_sym`, `sym-lib-table` | `schematic create` | the sheet of `schematic draw` |

`edakit export` keeps a copy of the folder as `kicad_<board>.zip`, as it keeps the `.eprj2` of an EasyEDA project.
Open the files in KiCad to look; a change made there is lost at the next run, as in EasyEDA. A part moved by hand keeps
its spot while it has no row in `[place]`, and `pcb takeover --write` writes it there.

### Footprints

Footprints come from the parts database: the entry's `footprint_data` (own parts, 4.5), else the geometry `edakit part
import` caches from the LCSC data – EasyEDA's footprint, which JLCPCB's assembly works from, so the CPL needs no
rotation offsets. KiCad's own library is not used: its footprints would need a correction of turn, origin and maybe
pad numbers for every part JLCPCB places (concept, decision 3). A part whose LCSC footprint is wrong or missing gets
`footprint_data`, started from the LCSC footprint by `edakit part footprint KEY --write`.

A part whose footprint is not cached yet is read from the library at the first `pcb place`, `pcb plan` or `pcb apply`
(cache only, the entry is not touched) – a new KiCad project places before its first apply. The cache holds the
library's silkscreen too – lines, circles, arcs, filled regions, the strokes of texts –, so polarity marks print as the
library draws them (GEO.mark). A cache from an older edakit lacks it and is read again.

Pads: `RECT` → rect, `ELLIPSE` → circle or oval, `OVAL` → oval, `POLYGON` → custom with its corners. Holes become round
or oval drills along the pad's long side; a hole not plated → `np_thru_hole`.

### Symbols

Symbols are those `schematic draw` draws (drawn without an EDA program, 6.5), one per part, turned as the sheet turns
it. Their pins are the drawing's pin tips, of length 0 and passive – edakit's checks of stage G reason about drivers,
not KiCad's ERC. Labels name the nets where the drawing writes a net name or a flag.

A pin in `nc` that the drawing shows gets KiCad's no-connect flag, and KiCad nets it on its own,
"unconnected-(SW1-Pad3)". `pcb apply` gives its pad that net, taken from kicad-cli's netlist export, so that the
schematic parity of the DRC finds it; read back, it is no net, as the graph has it.

### Frames

Inside, edakit computes in EasyEDA's frame, mil and y up (the coordinates, 7.1); a point (x, y) lies at (x/39.37 mm,
−y/39.37 mm) in the KiCad files – mil to mm, y turned down. A bottom-side part is mirrored in local y and turned as
EasyEDA does it (`Board.transform`). So every pad lies on the same spot in both tool chains, and the Gerber files of
both share their coordinates.

## 16.4 The flow

The commands are the same; what they do on KiCad:

| Command | KiCad |
| --- | --- |
| `schematic create` / `layout` | writes `<board>.kicad_sch` and checks it at once, as `schematic check` does; `copy` has nothing to do |
| `schematic check` | kicad-cli's netlist against the graph, and KiCad's ERC (errors only) |
| `pcb parts` / `nets` | the parts and pad nets of the file against the graph; `--write` writes the parts |
| `pcb apply`, `pcb tooling` | one writer: footprints at their rows (fixed ones locked), outline and mounting holes on Edge.Cuts, tooling holes, nets, rules; then every pad against the plan |
| `pcb dump` | the footprints measured from the file – nothing has to be turned first |
| `pcb place --rest` | edakit places the parts without a row (the placement plan, 7.4) – KiCad has no auto-layout |
| `pcb autolayout` | refused: `pcb place --rest` |
| `pcb pour`, `route pours` | zones of `[[pours]]` along the outline and a rule area around the keep circle of every mounting and tooling hole, filled by `kicad-cli pcb drc --refill-zones --save-board`; `stitch` is EasyEDA's |
| `route read` | `<board>_board.json` from the file, in the form EasyEDA's read has |
| `route dsn`/`route`/`check`/`diagnose` | unchanged |
| `route apply` | the SES as segments and vias – the pieces `route.segments` prepares for EasyEDA |
| `route reload`, `save` | nothing to do: the PCB is a file |
| `route drc` | KiCad's DRC with schematic parity |
| `silk apply` / `check` | the same placement (silkscreen, 7.7), written into the file; Gerber from kicad-cli |
| `export` | PDFs, netlist, BOM, Gerber ZIP, CPL, `kicad_<board>.zip` |
| `gate --eda` | stages S, L, F on KiCad's files |
| `part build --write` | the board's library and the part's footprints in the PCB from `footprint_data` |

## 16.5 kicad-cli

edakit calls (`edakit/toolchain/kicad/cli.py`; `-v` prints every call):

- `pcb drc --format json --units mm --severity-all [--schematic-parity] --output …` – findings in the form of EasyEDA's
  `drc.json`; with `--refill-zones --save-board` it fills the zones.
- `sch erc --format json --units mm --severity-all`, `sch export netlist --format kicadsexpr`, `sch export pdf`.
- `pcb export gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts --exclude-value
  --no-protel-ext`, `pcb export drill --format excellon --excellon-units mm --excellon-separate-th
  --excellon-oval-format alternate --drill-origin absolute`, `pcb export pos --format csv --units mm --side both`,
  `pcb export pdf`, `pcb render`.
- `pcb export odb --units mm --precision 4 --compression zip` – only with a maker of `[cart] makers` that takes ODB++
  (AISLER).

Four decimals are KiCad's most. With its default of two a pad at 62.825 mm is written at 62.82, and SYNC.odb sees the
step on copper, paste and mask. The step that is left, 0.1 µm against the Gerber's 1 nm, is one raster point at most,
which SYNC.odb takes as rounding. Every footprint carries `LCSC`, `MPN` and `Manufacturer` of its parts entry, and the
ODB++ takes them as properties of its components: AISLER assigns parts by MPN and knows no LCSC number.

The DRC checks whose subject edakit checks itself are off in `<board>.kicad_pro`: footprints against the library
(SYNC.footprint holds them to the parts database), courtyards (the plan), silkscreen overlaps and texts (GEO.silk on the
Gerber files). A pad needs one thermal spoke to its zone, not KiCad's default two: Freerouting knows no spokes and may
leave room for one, EasyEDA's DRC asks for none, and GEO.copper checks the connection. What KiCad's DRC reports beyond
that counts in GEO.drc.

## 16.6 The gate on KiCad

Stages P, G and E are unchanged. S, L and F read the same files, made from the KiCad project:

- **SYNC.schematic:** the netlist kicad-cli exports against the graph (`schematic.compare`), plus the errors of KiCad's
  ERC; the protocol names `<board>.kicad_sch`.
- **L:** `pcb.json` read from the file, `drc.json` from KiCad's DRC. GEO.drc has its KiCad rows: "KiCad DRC without
  findings (other kinds)", "schematic and PCB in sync (KiCad's schematic parity)", and with `drc_rules = "check"` the
  rules of `<board>.kicad_pro` against `[routing]`.
- **F:** kicad-cli's Gerber and drill files under the names the checks know (`gerber.FILES`). The plated holes of
  KiCad's PTH file are split into component holes and vias by the drill's X2 function (`ViaDrill`), else by the vias of
  the PCB. `FlyingProbeTesting.json` is made from the pads of `pcb.json`; it stays out of the ZIP, which holds only the
  Gerber and drill files. SYNC.bom compares the BOM with the schematic's (`bom_kicad.json`), SYNC.cpl the CPL with
  kicad-cli's position file (`cpl_kicad.csv`).
- **F, ODB++:** with a maker that takes ODB++ (AISLER), and with `[release] maker_files = "all"` (the default) for every
  board with an assembly side (8.4), `odb_<board>.zip` comes from `pcb export odb`, and SYNC.odb
  holds it to the run's files as it holds EasyEDA's. A failed export leaves kicad-cli's message in `odb_error.txt`,
  which SYNC.odb names. KiCad has no free pads, so a tooling hole is a footprint `TH<n>` (`board_only`, out of BOM and
  position file, `dnp`). Its ODB++ lists it as a component with the attribute `.no_pop`, and SYNC.odb lets it pass only
  so marked – a maker places no part that carries it. `edakit export` writes the same file.

The Gerber reader takes what KiCad writes: aperture macros (RoundRect, RotRect, Outline, FreePoly) and polygon
apertures become regions of their outline, X2 attributes are skipped; EasyEDA's files are read as before. The fab hash
is computed the same way; its value is the tool chain's, so a fab sign-off lapses when a project switches.

## 16.7 Switching a project

1. `toolchain = "kicad"` in `[project]`, the EasyEDA document names out of `[boards.<name>]`.
2. Every part needs a row in `[place]` (SYNC.plan): a board placed in EasyEDA has them after `pcb takeover --write`
   there; otherwise `pcb place --rest --write`.
3. `schematic create`, `pcb apply`, `route all`, `silk apply`, `gate --eda`.

The layout hash stays as long as `geometry.json` does; the sign-offs of scope `fab` lapse (the fab hash, 16.6).

## 16.8 What KiCad 10 confirmed, what is open

> **State:** the ODB++ confirmed with kicad-cli 10.0.6 on 2026-10-31; the carts in the live runs of the skill cart on
> 2026-11-01.

### In CI, on the led-bar example

The CI job `kicad` of tests.yml runs `tests/test_kicad_live.py` in KiCad's container image (KiCad 10.0) with
`EDAKIT_KICAD_LIVE=required`: a missing kicad-cli or another major version fails there. With kicad-cli of another major
version (KiCad 9, say) the live tests are skipped with the reason – they hold KiCad 10's behaviour, and a red run there
is no regression. The job confirmed:

- KiCad reads the schematic edakit writes (KiCad 8's format); its netlist is the graph, its ERC has no error.
- KiCad reads the PCB; `pcb drc --refill-zones --save-board` fills the zones; the DRC's JSON, with schematic parity, has
  only the connections the routing has not made yet. The schematic has global labels: local labels name a net
  "/GND", and the parity found every pad in conflict.
- The rule areas around the holes: KiCad leaves each keep circle free and fills the board right up to it, where the
  pours kept EasyEDA's square notch to the edge before – the 555 blinker's layout review, M-5 note 7
  (`test_kicad_fills_around_a_tooling_hole_and_keeps_its_circle_free`).
- The flags of kicad-cli (16.5) for Gerber, drill and position file; the file names of the export; the Gerber reader on
  KiCad's files. The position file's place and turn of every part against `pcb.json` (SYNC.cpl), on the bottom too: a
  part at 90° and one at 180° keep their turn in the position file (neither -a nor 180-a).
- The frames: KiCad's own Gerber copper lies at every pad edakit reads, also for turned parts and parts on the bottom.
- `route all` on KiCad: Freerouting routed all 18 nets of the example, edakit wrote 208 track pieces and 29 vias, KiCad
  filled the zones, its DRC found nothing. `pcb apply` and `silk apply` then rewrote the file KiCad had saved, again
  without a DRC finding. KiCad 10 names nets in items by name, and leaves out `(filled_areas_thickness no)`, which
  under KiCad 8's version gives a fill a stroke of `min_thickness`.
- Stages L and F of the gate on KiCad's export of the routed board: SYNC.pcb, GEO.copper (the copper of KiCad's Gerber
  files: every net connected, no short), GEO.drc, SYNC.footprint, SYNC.plan (every part with a row, every part where
  the plan puts it, measured by `pcb dump` from the file), GEO.hole, GEO.spacing, GEO.ring, GEO.pour, SYNC.bom, SYNC.cpl
  and FILES.set pass – JLCPCB's stock (PARTS.stock) and the track widths from the simulation (GEO.width) left out.
- The ODB++ of `pcb export odb` (kicad-cli, 16.5) against the files of the same run: SYNC.odb passes on every layer, the
  drill hits, the profile, the parts with place, rotation (ODB++ clockwise) and side – parts at 270° among them – and
  the nets; the tooling holes carry `.no_pop` (`test_kicad_odb_is_read_and_equals_the_runs_files`).

### On the 555 blinker

Confirmed on chapter 18's real project (KiCad 10.0.6):

- Footprints from the real LCSC data through `pcb apply`: through-hole pads, the plated slots of a switch's pegs, a
  SOIC-8, oval and rectangular pads, the library's silkscreen – a holder's outline and its poles. A through-hole part on
  the bottom, mirrored as EasyEDA mirrors it, its poles where the drawing has them.
- A pin the schematic marks no-connect gets KiCad's net on its pad (the symbols, 16.3), and a pad one thermal spoke (the
  DRC settings, 16.5).
- The gate `--eda` end to end with every sign-off up to RELEASED, and `export` with `kicad_main.zip`.
- A copy of that release in the carts of JLCPCB, PCBWay and Eurocircuits and up to AISLER's price, nothing ordered (the
  live runs of the skill cart, `tests/fixtures/makers/LIVE.md`; ordering at the manufacturer, 8.4).

### Open

- The led-bar example as a KiCad project looked at in KiCad, the placer on both tool chains, the Christmas bell – the
  steps are in the concept's [Live test](../docs/concepts/done/kicad-toolchain.md#live-test).
- Polygon pads, which the blinker's footprints do not have.
