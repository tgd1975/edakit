# Two tool chains: EasyEDA Pro and KiCad

Status 2026-10-30: proposal. Nothing is built, nothing has been tried with KiCad. The findings come from reading
edakit at `bf7450a`. What KiCad's command line and file formats do is stated from their documentation for KiCad 9
and marked **(probe)** where a live run has to confirm it before a step relies on it.

## Goal

edakit drives one EDA tool today: EasyEDA Pro, through the patched bridge and easyeda-mcp-pro. A project chooses a
second one, KiCad, with one key – and gets the same graph, the same checks, the same simulation, the same gate and
the same manufacturing files for JLCPCB. Nothing a project holds as text changes with the tool chain; only the
generated EDA project does.

Two questions decide every piece, as in [design-as-text.md](design-as-text.md):

1. **Shared or per tool chain?** Everything that reads only edakit's own files is shared. Only what reads or writes
   the EDA project belongs to a tool chain.
2. **Same check, same result?** A check that holds for EasyEDA must hold for KiCad with the same ID, the same
   tolerance and the same negative test. A check that cannot be carried over is named, not dropped silently.

## Why KiCad

| | EasyEDA Pro | KiCad |
| --- | --- | --- |
| Access | extension API inside the running editor, through a WebSocket bridge and an MCP server | text files (S-expressions) and `kicad-cli`, no GUI |
| Parallel sessions | one EasyEDA per machine – the claim (`lock.py`), lost runs when a tab is pulled away | none needed: each project has its own files |
| CI | not possible (desktop app, bridge, unthrottled window) | `kicad-cli` runs headless, a container image exists – stages S, L, F could run in GitHub Actions |
| Manual steps | creating the project, one *Import Changes* | none: edakit writes the schematic and the PCB, and with them the link between them |
| DRC rule set | in the GUI; read back and compared (`drc_rules.py`, step 2.2) | text: board setup in `.kicad_pro`, custom rules in `.kicad_dru` |
| Positions of the auto-layout | EasyEDA places, edakit writes back (step 2.1) | KiCad has no auto-placer – edakit places (gap K-1) |
| Footprints for JLCPCB assembly | EasyEDA's library is JLCPCB's: orientation and origin match the CPL | KiCad's library differs from JLCPCB's orientation for many packages – unless the footprints come from the same LCSC data (decision 3) |
| Licence of the chain | EasyEDA proprietary; easyeda-mcp-pro PolyForm Noncommercial | KiCad GPL-3.0, nothing noncommercial in the chain |
| Version risk | an undocumented API that changes with EasyEDA releases (handbook 9: ~25 behaviours) | file format with a version stamp, documented; old files are read by newer KiCad |

The gain is not the editor. It is that the EDA step becomes as offline, reproducible and parallel as the rest of
edakit already is – and the README's "Not text yet" list shrinks to nothing on the KiCad side.

## Where it stands: what is tied to EasyEDA

About 2 500 of the 23 900 lines of `edakit/` call EasyEDA (functions that take an MCP connection or call `eda.*`;
counted at `bf7450a`). The rest is offline already, and most of it is the reason edakit exists.

**Shared, unchanged** – no EasyEDA anywhere:

| Area | Modules |
| --- | --- |
| Graph, rules, hints, blocks | `design.py`, `checks.py`, `rules.py`, `rules.json`, `block.py`, `handover.py` |
| Parts | `part.py` (import, diff, fetch, search, datasheet, own), `stock.py`, `footprint.py` (data, P-9) |
| Simulation | `sim/` (operating points, transients, copper from the routing) |
| Requirements, firmware, documents, cost, order | `requirements.py`, `firmware.py`, `docs.py`, `cost.py`, `order.py`, `release/order_sheet.py` |
| Project scripts and agents | `scripts.py` (except kind `easyeda`), `proposal.py`, `agreements.py` |
| Gate offline | `gate.py` stages P, G, E, the hashes, sign-offs, manifest, release |

**Offline core inside EasyEDA modules** – the computation is shared, only reading and writing are EasyEDA's:

| Module | Offline part (shared) | EasyEDA part (per tool chain) |
| --- | --- | --- |
| `pcb.py` | plan, place, plan checks, mech model, net classes | dump, parts, nets, apply, tooling, pour, autolayout, takeover |
| `route.py` | DSN, Freerouting, SES, check, diagnose, pour regions | read, apply, pours, reload, DRC |
| `schematic_layout.py` | `Layout`: blocks, placement by topology, wires, short check | sync, clear, apply on the sheet |
| `schematic.py` | `plan_template`, `compare` | create, check, copy, repair |
| `silk.py` | spots, board label, artwork shapes, findings | apply, Gerber export |
| `release/fab.py` | L-1 … L-20, F-1 … F-6 on `pcb.json`, Gerber, BOM, CPL | `collect`: read PCB, DRC, export |
| `footprint.py` | P-9, P-10, `take_over` | `build` of the project's copy |
| `gerber.py` | raster, copper, nets from the graph | parser limited to what EasyEDA writes |

**EasyEDA only:** `eda.py`, `lock.py`, `export.py`, `drc_rules.py` (EasyEDA's rule format), `doctor.py` (bridge
part), `edakit/easyeda/`, the hook in `hooks/hooks.json`, the agent `easyeda-operator`, handbook 9.

The seam already exists in the data: the offline core works on JSON in fixed units, written by the EasyEDA side –
`<board>_board.json` (`route read`), `pcb.json` (`fab collect`), `<board>.geometry.json` (`pcb dump`), the cached
library geometry (`part import`), the symbol geometry of `schematic layout`. All in mil, y up, relative to the part
origin at 0° on TOP. A second tool chain fills the same files; the offline core does not notice.

## Design

### The key

```toml
# edakit.toml
[project]
toolchain = "kicad"          # "easyeda" (default) or "kicad"

[boards.main]
title = "Main board"
kicad = "kicad/main"         # folder of the KiCad project of this board (default kicad/<board>)
```

Without the key a project is what it is today ("no key, no change"). `template`, `schematic` and `pcb` of
`[boards.<b>]` are EasyEDA document names; with `toolchain = "kicad"` they are refused with what replaces them.
One tool chain per project, not per board (decision 1).

### A back end with one interface

A package `edakit/toolchain/` with one module per tool chain and one small interface. `eda.py` moves behind it
unchanged; the commands call the interface instead of `eda.*`.

```text
edakit/toolchain/
  __init__.py     select(cfg) -> EasyEDA | KiCad; the interface below
  easyeda.py      today's calls from eda.py, pcb.py, route.py, schematic*.py, silk.py, fab.collect, export.py
  kicad/
    sexp.py       read and write S-expressions (route.py's sexp/find become this module)
    library.py    .kicad_sym and .pretty from the parts database
    schematic.py  .kicad_sch from schematic_layout.Layout
    board.py      .kicad_pcb: read into board.json / pcb.json, write plan, tracks, vias, zones, silkscreen
    cli.py        kicad-cli: ERC, DRC, netlist, BOM, Gerber, drill, position file, PDF, render
```

| Operation | Used by | EasyEDA | KiCad |
| --- | --- | --- | --- |
| `schematic_write(board, layout)` | schematic create/layout | template + board schematic through the API | one `.kicad_sch` from `Layout`, symbols embedded |
| `schematic_read(board)` | S-2, `schematic check` | API netlist | `kicad-cli sch export netlist` |
| `erc(board)` | stage S | API | `kicad-cli sch erc --format json` |
| `library_write(board)` | part build, pcb parts | project library copies (`build_copy`) | project library `<board>.kicad_sym`, `<board>.pretty/` |
| `board_read(board)` | route read, fab collect, pcb dump | API → `board.json`, `pcb.json`, `geometry.json` | parse `.kicad_pcb` → the same three files |
| `board_write_parts(board, plan)` | pcb parts, nets, apply, tooling | API, *Import Changes* | footprints with nets, position, side, lock; outline on `Edge.Cuts`; holes |
| `board_write_copper(board, ses, pours)` | route apply, pour | delete, create, compare | `segment`, `via`, `zone` in `.kicad_pcb` |
| `board_write_silk(board, labels, art)` | silk apply | attributes, strings, fills | `fp_text`/`property` positions, `gr_text`, `gr_poly` on `F/B.SilkS` |
| `drc(board)` | route all, silk, stage L (L-3) | API after save + reload | `kicad-cli pcb drc --format json --schematic-parity` |
| `drc_rules(board)` | L-3 with `drc_rules` | read, compare | written from `[routing]`: nothing to compare |
| `export(board, out)` | stage F, `export` | Gerber ZIP, CPL xlsx, BOM, PDFs | `kicad-cli pcb export gerbers/drill/pos`, `sch export bom/pdf`, `pcb export pdf` |
| `place_rest(board)` | pcb autolayout | EasyEDA's auto-layout | edakit's own placer (gap K-1) |

Everything in the table returns or writes edakit's units (mil, y up). Conversion – KiCad's mm, y down, rotation
sense and the mirror of bottom-side footprints – happens in `kicad/board.py` and nowhere else, with one test per
direction.

### Files written, not an API

KiCad offers three ways in: the files, the `pcbnew` Python module (SWIG, bound to KiCad's own Python, deprecated
since KiCad 9 in favour of the IPC API), and the IPC API (needs a running KiCad, PCB editor only in KiCad 9).
Proposal: **edakit writes the files and calls `kicad-cli`** (decision 2).

- edakit already writes and reads S-expressions: its own Specctra DSN and the SES (`route.py`). A `.kicad_pcb` is
  the same syntax.
- No running KiCad, no claim, no bridge timeouts – the reasons for `lock.py`, `easyeda-operator` and half of
  handbook 12 do not arise.
- Principle 2 of the handbook ("generated content may be deleted") becomes literal: the KiCad folder is written from
  scratch on every run, apart from what KiCad itself keeps (zone fills, see below).

What the files cannot do – fill zones – goes to `kicad-cli` or, failing that, to a `pcbnew` call in a subprocess
(gap K-3).

### Library: from the same data as today

The parts database is the source; the KiCad library is generated, per board, into the KiCad folder:

- **Footprint:** `footprint_data` of the parts entry where there is one; otherwise the geometry `edakit part import`
  caches from the LCSC data. Both are EasyEDA's – that is, JLCPCB's – geometry, so origin and rotation match
  JLCPCB's assembly, and F-3 holds as it does today. Pads, holes, slots, silkscreen lines, texts, polarity marks and
  the body outline map one to one (`pad` with `rect`/`oval`/`circle`/`roundrect`, `drill`, `fp_line`, `fp_poly`,
  `F.CrtYd`/`F.Fab`). Paste and mask layers follow KiCad's defaults for the pad type.
- **Symbol:** a box with the entry's pins, as `schematic draw` draws one today (`"symbol"` of the entry chooses the
  sides); resistors, capacitors, diodes, LEDs and transistors with the shapes of `schematic_draw.py`.
- **Optional:** `kicad_footprint = "Resistor_SMD:R_0603_1608Metric"` in a parts entry takes a footprint of KiCad's
  library instead (decision 3). L-10 then compares its pads with the LCSC geometry, and F-3 needs a rotation offset
  for JLCPCB, written in the entry (`jlc_rotation`), not guessed.

P-9, P-10 and L-10 apply unchanged: the generated footprint is measured back from the `.kicad_pcb` as `pcb dump`
measures EasyEDA's.

### Schematic

`schematic_layout.Layout` computes blocks, positions, rotations, wires and flags today and hands them to EasyEDA; the
SVG of `schematic draw` comes from the same plan. The KiCad writer takes the same plan and writes one `.kicad_sch`:
symbols from the generated library (embedded in `lib_symbols`), `wire`, `junction`, `label`, power symbols, the
sheet frame with title, revision and graph version. Units: the plan's 10 mil grid becomes KiCad's 1.27 mm (50 mil)
grid – 1 plan unit = 0.254 mm, snapped (probe: whether pins of the generated symbols land on KiCad's grid).

There is no template schematic. EasyEDA needed two schematics because a PCB hangs on one and `copy` must not cut it
off; in KiCad the link is the symbol's UUID path in the footprint, and edakit writes both sides with the same UUIDs –
derived from the designator, stable over runs. *Import Changes* does not exist on this side.

Stage S: `kicad-cli sch export netlist` against the graph (S-2, with `schematic.compare` as today) and
`kicad-cli sch erc` (S-3).

### PCB

`pcb apply`, `parts`, `nets`, `tooling` collapse into one writer: outline polygon on `Edge.Cuts`, mounting holes as
footprints of their own (`MountingHole` geometry from the board file), tooling holes as NPTH pads, every part of the
board with its position from `[place]`, its side, `locked` for the fixed ones, every pad with its net from the graph.
`pcb dump` becomes a reader of the written file plus the generated footprints – no part has to be turned to 0° to be
measured.

**Routing** stays Freerouting with edakit's own DSN: `route read` fills `<board>_board.json` from the `.kicad_pcb`,
steps 2 to 4 (`dsn`, `route`, `check`) and `diagnose` run unchanged, `apply` writes the SES as `segment` and `via`
lines. Reload (step 7) is not needed.

**Pours:** `[[pours]]` becomes `zone` with the net, layer, clearance and thermal settings of the board file. With
`pour_regions` edakit computes the outlines already; the fill is KiCad's (gap K-3).

**DRC rules:** from `[routing]` edakit writes the board setup (`.kicad_pro`: clearance, track width, via, net
classes with their nets) and, where the board file asks for more (hand-solder keep-outs, L-18), `.kicad_dru`
custom rules. The rule set is text; `drc_rules = "check"` has nothing to compare and is accepted silently.

**Silkscreen:** designator positions as properties of the footprint, board label and `[[silk.texts]]` as `gr_text`,
artwork as `gr_poly` fills – the shapes `silk.py` computes from the SVG today. The checks stay on the Gerber files.

### Gate

Stages P, G, E: unchanged. Stages S, L, F: the same checks on the same intermediate files; `fab.collect` gets them
from the tool chain.

| Check | KiCad side |
| --- | --- |
| L-1, L-4, L-7, L-10, L-12, L-13, L-14, L-18, L-20 | on `pcb.json` and `geometry.json`, filled from the `.kicad_pcb` – unchanged |
| L-2, L-8, L-15, L-16, L-17, F-5 | on the Gerber files – need the parser for KiCad's Gerber (gap K-2) |
| L-3 | KiCad's DRC JSON instead of EasyEDA's; schematic parity from `--schematic-parity` replaces the *Import Changes* item |
| L-5, L-11 | on the tracks of `pcb.json` – unchanged |
| F-1 | BOM from the graph against `kicad-cli sch export bom` instead of `easyeda_bom_generate` |
| F-2, F-6 | unchanged |
| F-3 | CPL from `kicad-cli pcb export pos` (mm, y up, KiCad's rotation) turned into JLCPCB's format; with the generated library no offsets |

The rule IDs stay. The texts of `rules.json` that name EasyEDA (L-3, F-1 and some fixes) say "the EDA tool" and name
the tool chain in a second sentence. The negative tests run per tool chain where the check reads an EDA file: the
led-bar fixture gets a KiCad export of its input stage beside the EasyEDA one (`tests/fixtures/led-bar/`).

**Hashes:** circuit hash – unchanged. Layout hash – the board file, artwork and `geometry.json` as today; the
generated KiCad files are outputs and are not hashed. Fab hash – unchanged in method; its value differs between the
tool chains, so a fab sign-off (M-5) lapses when a project switches. That is right: the files to the manufacturer
are new.

### Plugin, skills, agents

- The MCP server `easyeda` and the hook on its tools stay; they are idle in a KiCad project. `agreements.py` tells a
  session which tool chain the project uses.
- Skills `start`, `pcb-round`, `release`, `own-part`, `new-project` branch where they name EasyEDA steps (claim,
  *Import Changes*, the operator agent). `new-project` asks for the tool chain in its interview.
- Agent `easyeda-operator`: EasyEDA only. On the KiCad side the commands run in the session – they take seconds,
  not minutes.
- `pcb-reviewer` gets its pictures from `kicad-cli pcb render` and `pcb export svg` instead of canvas captures
  (probe: views and resolution).
- `edakit doctor`: `kicad-cli` on the PATH and its version, Freerouting, ngspice; no bridge lines.
- Project scripts: kind `easyeda` stays EasyEDA's; a KiCad project has no project library outside its files, so its
  scripts are `input` or `derive`. A kind `kicad` is not needed.

## Gaps on the KiCad side

| # | Gap | Proposal |
| --- | --- | --- |
| K-1 | No auto-placer in KiCad | Every part needs a row in `[place]` anyway (L-20, design-as-text decision 4). `pcb place` covers parts with a host; a new `pcb place --rest` puts the others – greedy on airline length within the outline, then the plan checks. A starting position, written with `auto = true` like today's write-back. |
| K-2 | `gerber.py` reads only EasyEDA's subset | Extend the parser: aperture macros KiCad writes (`RoundRect`, `Outline`, `FreePoly`, `RotRect`), X2 attributes ignored, Excellon in mm with KiCad's header. The pad positions of `FlyingProbeTesting.json` come from `pcb.json` instead (or IPC-D-356 from `kicad-cli`, probe). Nets keep coming from the graph. |
| K-3 | Zone fill | `kicad-cli pcb drc --refill-zones` and the plot option to refill before export (probe, KiCad 9); otherwise a `pcbnew` subprocess with `ZONE_FILLER`. The fill is checked by L-2 and L-15 on the Gerber files either way. |
| K-4 | JLCPCB's rotation for KiCad library footprints | Only for `kicad_footprint` entries: `jlc_rotation` in the entry, checked by F-3 against the CPL and seen by M-5 on JLCPCB's assembly preview. |
| K-5 | Vector PDF of the schematic | `kicad-cli sch export pdf` – better than today's EasyEDA path, which needs the patched bridge. No gap, a gain. |

## Differential run

With both tool chains in edakit, the same project can go through both and `edakit fab diff` compares the Gerber
rasters of the two gate runs. The differences that remain are the tools' (fill style, aperture choice, text font) –
everything else is a bug in one of the writers. That is the acceptance test of the KiCad side, before any board is
ordered from it: the led-bar fixture and the Christmas bell, both through both chains, differences explained.

## Scope

In: tool chain key, back-end interface, KiCad writers and readers for schematic, library, PCB, routing, pours,
silkscreen, DRC rules; gate stages S, L, F on KiCad; doctor, skills, handbook; differential run on the fixture and
the bell.

Out: importing an existing KiCad design into a graph (the `project-surveyor` lists it as hardware data; that is a
concept of its own); KiCad's interactive router or push-and-shove; more than two copper layers (edakit's limit, not
KiCad's); a GUI plugin inside KiCad; manufacturers other than JLCPCB.

## Order

Each step is one branch, built with add-feature, test first, as in [implementation-plan.md](implementation-plan.md).

| Step | What | Size | KiCad needed | Waits for |
| --- | --- | --- | --- | --- |
| K.1 | Interface `edakit/toolchain/`, EasyEDA behind it; no behaviour change – every test as before, `--offline` runs byte-identical | L | no | – |
| K.2 | `[project] toolchain`, `[boards.<b>] kicad`, config checks; `doctor` per tool chain | S | no | K.1 |
| K.3 | `kicad/sexp.py` from `route.py`; `kicad/library.py` – footprints and symbols from the parts database; tests on the fixture's parts | M | no | K.1 |
| K.4 | `kicad/board.py` read: `.kicad_pcb` → `board.json`, `pcb.json`, `geometry.json`; round-trip tests | M | no | K.3 |
| K.5 | `gerber.py` for KiCad's output (K-2), on a recorded KiCad export of the fixture | M | once, to record | – |
| K.6 | `kicad/board.py` write: outline, holes, parts, nets, rules; SES as tracks; zones; silkscreen | L | probe | K.4 |
| K.7 | `kicad/schematic.py` from `Layout`; S-2 and S-3 via `kicad-cli` | M | yes | K.3 |
| K.8 | `kicad/cli.py`: ERC, DRC, export; stage L and F on KiCad, `fab.collect` per tool chain | M | yes | K.5, K.6, K.7 |
| K.9 | `pcb place --rest` (K-1) | M | no | – |
| K.10 | Skills, agents, hook, handbook (new chapter 16, 2 setup, 10 reference); README | M | no | K.8 |
| K.11 | Differential run: fixture and bell through both chains, `fab diff`, differences explained in this file | M | yes | K.8, K.9 |
| K.12 | CI job: the fixture's stages S, L, F with `kicad-cli` in a container | S | yes | K.8 |

K.1 is the largest single step and the only one that touches the EasyEDA side. It can go to main on its own and
changes nothing for the bell or the reference project. K.3, K.4, K.5 and K.9 run offline and in parallel.

## Decisions

| # | Question | Recommendation |
| --- | --- | --- |
| 1 | Tool chain per project or per board | per project: one graph, one library, one schematic tool. Per board would mix exports in one gate run for no project that needs it |
| 2 | Files plus `kicad-cli`, `pcbnew` Python, or IPC API | files plus `kicad-cli`; `pcbnew` only as fallback for the zone fill (K-3) |
| 3 | Footprints from the LCSC data or from KiCad's library | from the LCSC data by default (JLCPCB's orientation, one geometry for both chains); `kicad_footprint` as an opt-in per entry |
| 4 | Least KiCad version | 9: `kicad-cli` with ERC/DRC JSON, BOM, schematic parity. 8 only if a probe shows the same commands |
| 5 | Is the generated KiCad folder versioned | no, like the EasyEDA project – an output, written from scratch; `.gitignore` in the template. A project may version it for review diffs, edakit does not read it back as a source |
| 6 | Order relative to the open steps of the implementation plan | after 2.1–2.4 and 3.6 had their live runs: K.1 moves the code those steps touch |
| 7 | Differential run as a gate check | no – a step of K.11 and a tool for later changes to the writers, not a condition of a release |

## Sources

- edakit at `bf7450a`: [eda.py](../../../edakit/eda.py), [lock.py](../../../edakit/lock.py),
  [pcb.py](../../../edakit/pcb.py), [route.py](../../../edakit/route.py) (`read_board`, `write_dsn`, `read_ses`,
  `apply_ses`, `sexp`), [schematic.py](../../../edakit/schematic.py),
  [schematic_layout.py](../../../edakit/schematic_layout.py), [schematic_draw.py](../../../edakit/schematic_draw.py),
  [silk.py](../../../edakit/silk.py), [footprint.py](../../../edakit/footprint.py), [part.py](../../../edakit/part.py)
  (`library_part`, which names a KiCad library as its possible replacement), [gerber.py](../../../edakit/gerber.py),
  [drc_rules.py](../../../edakit/drc_rules.py), [export.py](../../../edakit/export.py),
  [config.py](../../../edakit/config.py) (`BOARD_KEYS`), [gate.py](../../../edakit/release/gate.py),
  [fab.py](../../../edakit/release/fab.py) (`collect`, L and F checks), [hooks.json](../../../hooks/hooks.json).
- Handbook [1](../../../handbook/01-approach.md), [7](../../../handbook/07-pcb.md),
  [8](../../../handbook/08-release-gate.md), [9](../../../handbook/09-easyeda-api.md).
- Concepts [design-as-text.md](design-as-text.md) (gaps 1–3, decision 4), [parallel-easyeda.md](parallel-easyeda.md),
  [implementation-plan.md](implementation-plan.md).
- KiCad 9 documentation: `kicad-cli` (sch erc/export netlist/bom/pdf, pcb drc/export gerbers/drill/pos/pdf/svg,
  pcb render), the S-expression file formats (`.kicad_sch`, `.kicad_pcb`, `.kicad_sym`, `.kicad_mod`, `.kicad_dru`),
  the IPC API. Points marked (probe) are not verified.
