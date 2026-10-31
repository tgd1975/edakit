# Two tool chains: EasyEDA Pro and KiCad

Status 2026-10-30: built on the branch of decision 6 (steps T.1 to T.10 and T.12, the table under Order) and merged into
main the same day, before the live tests, at the user's word; tested offline against a kicad-cli the tests fake and in
CI against KiCad 10 on the led-bar example (handbook 16.8). Open: the live tests with the user. On 2026-10-30 the user
decided: edakit places the parts in both tool chains (gap K-1, now the section
[Placement](#placement-edakit-places-for-both-tool-chains)), and decisions 1, 4, 5, 6 and 7. The user left decision 2 to
Claude. Claude took decision 3 as recommended because the user left it open; the user accepted the reason the same day.
The findings come from reading edakit at `bf7450a`. The KiCad facts are from KiCad's documentation and release pages for
KiCad 10. Anything marked **(probe)** has not been run.

## Goal

edakit drives one EDA tool today: EasyEDA Pro, through the patched bridge and easyeda-mcp-pro. A project chooses a
second one, KiCad, with one key. It gets the same graph, the same checks, the same simulation, the same gate and the
same manufacturing files for JLCPCB. Nothing a project holds as text changes with the tool chain. Only the generated
EDA project does.

Two questions decide every piece, as in [design-as-text.md](design-as-text.md):

1. **Shared or per tool chain?** Everything that reads only edakit's own files is shared. Only what reads or writes
   the EDA project belongs to a tool chain.
2. **Same check, same result?** A check that holds for EasyEDA has to hold for KiCad with the same ID, the same
   tolerance and the same negative test. A check that cannot be carried over is named, not dropped silently.

## Why KiCad

| | EasyEDA Pro | KiCad |
| --- | --- | --- |
| Access | extension API inside the running editor, through a WebSocket bridge and an MCP server | text files (S-expressions) and `kicad-cli`, no GUI |
| Parallel sessions | one EasyEDA per machine: the claim (`lock.py`), and runs lost when a tab is pulled away | no claim needed: each board has its own files |
| CI | not possible (desktop app, bridge, unthrottled window) | `kicad-cli` runs headless, so stages S, L and F can run in GitHub Actions |
| Manual steps | creating the project, one *Import Changes* | none: edakit writes the schematic, the PCB and the link between them |
| DRC rule set | set in the GUI; read back and compared (`drc_rules.py`, step 2.2) | text: the board setup in `.kicad_pro`, custom rules in `.kicad_dru` |
| Footprints for JLCPCB assembly | EasyEDA's library is JLCPCB's: origin and rotation match the CPL | KiCad's library differs from JLCPCB's orientation for many packages, unless the footprints come from the same LCSC data (decision 3) |
| Licence of the chain | EasyEDA proprietary; easyeda-mcp-pro PolyForm Noncommercial | KiCad GPL-3.0, nothing noncommercial in the chain |
| Version risk | an undocumented API that changes with EasyEDA's releases (handbook 9: ~25 behaviours) | a documented file format with a version stamp; a newer KiCad reads older files |

The gain is not the editor. With KiCad the EDA step becomes as offline, reproducible and parallel as the rest of
edakit already is, and the README's "Not text yet" list has nothing left on the KiCad side. Placement is no longer a
difference between the two: edakit places for both (next section).

## Where it stands: what is tied to EasyEDA

About 2 500 of the 23 900 lines in `edakit/` call EasyEDA: these are the functions that take an MCP connection or
call `eda.*` (counted at `bf7450a`). The rest already runs offline, and most of it is the reason edakit exists.

**Shared, unchanged.** None of these touch EasyEDA:

| Area | Modules |
| --- | --- |
| Graph, rules, hints, blocks | `design.py`, `checks.py`, `rules.py`, `rules.json`, `block.py`, `handover.py` |
| Parts | `part.py` (import, diff, fetch, search, datasheet, own), `stock.py`, `footprint.py` (data, P-9) |
| Simulation | `sim/` (operating points, transients, copper from the routing) |
| Requirements, firmware, documents, cost, order | `requirements.py`, `firmware.py`, `docs.py`, `cost.py`, `order.py`, `release/order_sheet.py` |
| Project scripts and agents | `scripts.py` (except kind `easyeda`), `proposal.py`, `agreements.py` |
| Gate offline | `gate.py` stages P, G, E, the hashes, sign-offs, manifest, release |

**Offline core inside EasyEDA modules.** The computation is shared; only reading and writing belong to EasyEDA:

| Module | Offline part (shared) | EasyEDA part (per tool chain) |
| --- | --- | --- |
| `pcb.py` | plan, place, plan checks, mech model, net classes | dump, parts, nets, apply, tooling, pour, takeover; autolayout (to go, see Placement) |
| `route.py` | DSN, Freerouting, SES, check, diagnose, pour regions | read, apply, pours, reload, DRC |
| `schematic_layout.py` | `Layout`: blocks, placement by topology, wires, short check | sync, clear, apply on the sheet |
| `schematic.py` | `plan_template`, `compare` | create, check, copy, repair |
| `silk.py` | spots, board label, artwork shapes, findings | apply, Gerber export |
| `release/fab.py` | L-1 … L-20, F-1 … F-6 on `pcb.json`, Gerber, BOM, CPL | `collect`: read the PCB, DRC, export |
| `footprint.py` | P-9, P-10, `take_over` | `build` of the project's copy |
| `gerber.py` | raster, copper, nets from the graph | a parser limited to what EasyEDA writes |

**EasyEDA only:** `eda.py`, `lock.py`, `export.py`, `drc_rules.py` (EasyEDA's rule format), `doctor.py` (bridge
part), `edakit/easyeda/`, the hook in `hooks/hooks.json`, the agent `easyeda-operator`, handbook 9.

The data already has the seam. The offline core works on JSON in fixed units, written by the EasyEDA side:
`<board>_board.json` (`route read`), `pcb.json` (`fab collect`), `<board>.geometry.json` (`pcb dump`), the cached
library geometry (`part import`) and the symbol geometry of `schematic layout`. All of it is in mil, y up, relative to
the part origin at 0° on TOP. A second tool chain fills the same files, and the offline core does not notice.

## Placement: edakit places, for both tool chains

The user decided gap K-1 on 2026-10-30. KiCad has no auto-placer, and EasyEDA's is not wanted either: what it
optimises is not documented, and its result cannot be reproduced. edakit places every part itself, in both tool
chains.

**Today:** `edakit pcb place` puts every part that has a host next to that host. A host comes from `layout.near`,
`[near]` or the decoupling of L-12 (`auto_place`, `spot_candidates`, `find_spot` in `pcb.py`). It tries spots on the
plan grid at 0/90/180/270°, takes a spot only where the plan check reports nothing new, and writes the result as
`auto = true` rows. EasyEDA's auto-layout (`pcb autolayout`) places the other parts, and step 2.1 writes its result
back. That auto-layout places only unlocked parts and only on TOP, and it knows nothing about which part belongs to
which.

**Proposal:** `pcb place --rest` also places the parts without a host, by the same rules:

1. **Order.** Parts with a host come first, as today. After them, the part with the most pad connections to what is
   already placed goes next; ties go by designator in natural order.
2. **Spots.** The plan grid inside the outline, on an assembled side (`[release] assembly`, TOP first), at
   0/90/180/270°. A spot counts only where the plan check reports nothing new, as for today's spots: overlaps, holes,
   tooling holes, keep-outs, THT pins of the other side, the outline, mated plugs, `uniform` polarity.
3. **Score.** The airline length the part adds: the minimum spanning tree per net that `wirelength` computes, with
   ground left out as it is there. Rotation, y and x break ties. No random numbers: the same files give the same rows.
4. **Improvement.** A pass afterwards moves and swaps `auto` rows while the total airline length falls and the plan
   check stays clean. It stops when a pass changes nothing, after a fixed number of passes at most.

Fixed rows stay where they are, and `auto = true` rows may move on the next run, as today. `edakit route diagnose`
already shows where a plan walls nets in, and its congestion map could become a second score later if routing shows
the need. The first version does not use it.

**EasyEDA's auto-layout goes:** `pcb autolayout` stays until the placer has placed a real board that routed and
passed the gate. After that the command goes, together with its part of handbooks 7 and 9, and `--rest` becomes what
`pcb place` does. `pcb takeover` stays: boards placed before, such as the bell and the reference project, keep their
positions as fixed rows. Step 2.1's live run still checks the takeover and L-20. Its auto-layout part matters only for
as long as `pcb autolayout` exists. This closes gap 1 of design-as-text in another way: the positions are written
before the EDA tool sees the board, not read back from it afterwards.

Once every position is in the board file, both tool chains build the board from the same rows.

## Design

### The key

```toml
# edakit.toml
[project]
toolchain = "kicad"          # "easyeda" (default) or "kicad"
```

Without the key a project stays as it is ("no key, no change"). One tool chain serves all boards of a project
(decision 1). With `"kicad"`, edakit refuses the EasyEDA document names of `[boards.<b>]` (`template`, `schematic`,
`pcb`) and says that this tool chain does not need them.

**The KiCad project is handled like the EasyEDA project (decision 5).** It is generated, kept out of the repository
and rewritten by the steps. Each board gets one KiCad project in `<artifacts>/kicad/<board>/`. The default is
`build/edakit/kicad/<board>/`, which the `.gitignore` of `new-project` already leaves out. It holds
`<board>.kicad_pro`, `.kicad_sch`, `.kicad_pcb` and `.kicad_dru`, the board's library `<board>.kicad_sym` and
`<board>.pretty/`, and the library tables that point to them. `edakit export` keeps a copy, `kicad_<board>.zip`, as it
keeps the `.eprj2` of the EasyEDA project. The project can be opened in KiCad to look at it. Anything changed there is
lost at the next run, as in EasyEDA.

Each step owns sections of the files, as each EasyEDA step owns its primitives:

- `pcb apply` owns the footprints, the outline and the holes.
- `route all` owns the tracks, vias and zones.
- `silk apply` owns the designator positions and the silkscreen texts and shapes.

A step replaces its own sections and keeps the others.

### A back end with one interface

Each command calls the operations of the table below instead of `eda.*`, and `select(cfg)` picks the tool chain.
The EasyEDA side calls the functions where they are today (`eda.py`, `route.read_board`, `route.apply_ses`,
`fab.collect`, …); nothing is moved. The reason is decision 6: the KiCad work runs on a branch of its own while the
live runs of 2.1 to 2.4 and 3.6 still change that code, and a thin dispatch keeps the rebase small. Moving the EasyEDA
code into `toolchain/easyeda.py` is a cleanup for later, not a step of this concept.

As built, the dispatch is one branch at the top of each command (`is_kicad(cfg)`), and the EasyEDA side needs no
module of its own:

```text
edakit/toolchain/
  __init__.py     is_kicad(cfg), only_easyeda(cfg, what, instead)
  kicad/
    commands.py   the KiCad side of pcb, route's EasyEDA steps, export
    silk.py       silk apply|check: silk.py's placement written into the KiCad PCB
    fab.py        stages L and F: the files fab.collect gets from EasyEDA, from KiCad's exports
    sexp.py       read and write S-expressions (route.py's sexp and find become this module)
    library.py    .kicad_sym and .pretty from the parts database
    schematic.py  .kicad_sch from schematic_layout.Layout
    board.py      .kicad_pcb: read into board.json, pcb.json, geometry.json; write parts, tracks, vias, zones, silkscreen
    cli.py        kicad-cli: ERC, DRC with zone fill, netlist, BOM, Gerber, drill, position file, PDF, render
```

| Operation | Used by | EasyEDA | KiCad |
| --- | --- | --- | --- |
| `schematic_write(board, layout)` | schematic create/layout | template and board schematic through the API | one `.kicad_sch` from `Layout`, symbols embedded |
| `schematic_read(board)` | S-2, `schematic check` | API netlist | `kicad-cli sch export netlist` |
| `erc(board)` | stage S | API | `kicad-cli sch erc`, JSON report |
| `library_write(board)` | part build, pcb parts | project library copies (`build_copy`) | the board's `.kicad_sym` and `.pretty/` |
| `board_read(board)` | route read, fab collect, pcb dump | API → `board.json`, `pcb.json`, `geometry.json` | parse `.kicad_pcb` → the same three files |
| `board_write_parts(board, plan)` | pcb parts, nets, apply, tooling | API, *Import Changes* | footprints with nets, position, side, lock; outline on `Edge.Cuts`; holes |
| `board_write_copper(board, ses, pours)` | route apply, pour | delete, create, compare | `segment`, `via`, `zone` in `.kicad_pcb`; fill by `kicad-cli pcb drc --refill-zones --save-board` |
| `board_write_silk(board, labels, art)` | silk apply | attributes, strings, fills | designator positions of the footprints, `gr_text`, `gr_poly` on `F/B.SilkS` |
| `drc(board)` | route all, silk, stage L (L-3) | API after save and reload | `kicad-cli pcb drc`, JSON report, schematic parity |
| `drc_rules(board)` | L-3 with `drc_rules` | read and compare | written from `[routing]`: nothing to compare |
| `export(board, out)` | stage F, `export` | Gerber ZIP, CPL xlsx, BOM, PDFs | `kicad-cli pcb export gerbers/drill/pos`, `sch export bom/pdf`, `pcb export pdf` |

Every operation in the table returns or writes edakit's units (mil, y up). The conversion to KiCad's mm, y down, its
sense of rotation and the mirroring of bottom-side footprints happens in `kicad/board.py` and nowhere else, with one
test per direction.

### Files written, not an API

KiCad has three ways in:

- the files;
- the `pcbnew` Python module, which is SWIG, bound to KiCad's own Python, and to be removed in KiCad 11 according to
  KiCad's developer documentation;
- the IPC API, built for plugins that talk to a running KiCad.

**Decision 2 (left to Claude): edakit writes the files and calls `kicad-cli`, and uses nothing else.**

- edakit already writes and reads S-expressions: its own Specctra DSN and the SES (`route.py`). A `.kicad_pcb` uses
  the same syntax.
- There is no running editor, no claim and no bridge timeout. The reasons for `lock.py`, `easyeda-operator` and half
  of handbook 12 do not arise.
- Principle 2 of the handbook ("generated content may be deleted") becomes literal: each step rewrites its sections of
  the files.
- The zone fill is the one thing the files cannot do. KiCad 10's manual lists `kicad-cli pcb drc --refill-zones`,
  which fills the zones, and `--save-board`, which keeps the result **(probe)**. That leaves no use for `pcbnew`.

### Library: where the pads come from

When edakit writes a KiCad footprint, the pads have to come from somewhere. There are two sources, and choosing
between them is decision 3:

- **The LCSC data.** This is the geometry `edakit part import` already reads for every LCSC number, or the entry's
  `footprint_data`. It is EasyEDA's footprint, and JLCPCB's assembly works from EasyEDA's library, so origin and
  rotation in the CPL match without a correction. It works for every part with an LCSC number, and nobody has to
  choose a footprint.
- **KiCad's own library**, for example `Resistor_SMD:R_0603_1608Metric`. These footprints follow KiCad's library
  rules (KLC): courtyard, fabrication layer, 3D model. But someone has to choose one for every part, its pads differ
  slightly from the LCSC footprint, and for some packages JLCPCB places it turned unless the CPL is corrected.

**Taken by Claude, because the user left it open:** every part uses the LCSC data. A part whose LCSC footprint is
wrong or missing gets its own footprint as text, `footprint_data` in its parts entry (handbook 4.5): `edakit part
footprint KEY --write` starts it from the LCSC footprint, in its axes and turn, and the datasheet corrects it. It works
in both tool chains; P-9 checks that it is complete, P-10 that the board has it.

On 2026-10-30 the user asked why the KiCad tool chain does not use KiCad's library, and accepted the reason: KiCad is
the tool, the parts come from the assembler. In EasyEDA the tool's library and JLCPCB's are the same; in KiCad they
are not, and edakit takes the assembler's in both. A footprint from KiCad's library would need a correction of turn
and often of origin (KiCad puts the origin of a through-hole footprint on pin 1, JLCPCB places by the centre) for
every part, and its pad numbers can differ from the LCSC symbol's (in KiCad, pad 1 of a diode is the cathode).
Without assembly by JLCPCB, KiCad's library would be the obvious choice.

A choice of KiCad's library per parts entry (`kicad_footprint`, with a CPL correction `jlc_offset`) was planned and is
dropped, the user's choice of 2026-10-30. The same entry would give one footprint in EasyEDA and another in KiCad, so
switching the tool chain would change the board; every such part would need its correction of turn and origin in the
CPL, a check of it in F-3 and a map of its pad numbers; and the footprint would come from the KiCad installation,
which an update changes. Should a part ever need a footprint from KiCad's library, it is imported once into
`footprint_data`, turned and shifted onto the LCSC footprint by the fit of `edakit part diff`, its pad numbers checked.
After that it takes the way every other part takes. That import is built when a part needs it.

The footprint maps one to one:

- pads with shape (`rect`, `oval`, `circle`, `roundrect`), drill and slot;
- silkscreen lines, texts and polarity marks;
- the body outline (`F.CrtYd`, `F.Fab`).

Paste and mask follow KiCad's defaults for the pad type. The symbol is a box with the entry's pins, as
`schematic draw` draws one today (`"symbol"` in the entry chooses the sides). Resistors, capacitors, diodes, LEDs and
transistors get the shapes of `schematic_draw.py`.

P-9, P-10 and L-10 apply unchanged: the generated footprint is measured back from the `.kicad_pcb`, as `pcb dump`
measures EasyEDA's.

### Schematic

Today `schematic_layout.Layout` computes the blocks, positions, rotations, wires and flags and hands them to EasyEDA;
the SVG of `schematic draw` comes from the same plan. The KiCad writer takes the same plan and writes one `.kicad_sch`
with:

- symbols from the generated library (embedded in `lib_symbols`);
- `wire`, `junction`, `label` and power symbols;
- the sheet frame with title, revision and graph version.

For units, the plan's 10 mil grid becomes KiCad's 1.27 mm (50 mil) grid: 1 plan unit = 0.254 mm, snapped. Whether
the pins of the generated symbols land on KiCad's grid is a **(probe)**.

There is no template schematic. EasyEDA needed two schematics because a PCB hangs on one and `copy` must not cut it
off. In KiCad the link is the symbol's UUID path in the footprint. edakit writes both sides with the same UUIDs,
derived from the designator so that they stay the same from run to run. *Import Changes* does not exist on this side.

Stage S compares `kicad-cli sch export netlist` with the graph (S-2, through `schematic.compare` as today) and runs
`kicad-cli sch erc` (S-3).

### PCB

`pcb apply`, `parts`, `nets` and `tooling` collapse into one writer. It writes:

- the outline polygon on `Edge.Cuts`;
- mounting holes as footprints of their own, with the geometry from the board file;
- tooling holes as NPTH pads;
- every part of the board with its position from `[place]`, its side, and `locked` for the fixed ones;
- every pad with its net from the graph.

`pcb dump` becomes a reader of the written file and the generated footprints. No part has to be turned to 0° to be
measured.

**Routing** stays with Freerouting and edakit's own DSN. `route read` fills `<board>_board.json` from the
`.kicad_pcb`. Steps 2 to 4 (`dsn`, `route`, `check`) and `diagnose` run unchanged, and `apply` writes the SES as
`segment` and `via` entries. The reload (step 7) is not needed.

**Pours:** each entry of `[[pours]]` becomes a `zone` with the net, layer, clearance and thermal settings of the board
file. With `pour_regions`, edakit already computes the outlines. KiCad fills the zones through `kicad-cli` (K-3).

**DRC rules:** from `[routing]` edakit writes the board setup into `.kicad_pro`: clearance, track width, via, and the
net classes with their nets. Where the board file asks for more, such as the hand-solder keep-outs of L-18, it writes
custom rules into `.kicad_dru`. The rule set is text, so `drc_rules = "check"` has nothing to compare and is accepted
silently.

**Silkscreen:** designator positions are properties of the footprint; the board label and `[[silk.texts]]` become
`gr_text`, and the artwork becomes `gr_poly` fills, the shapes `silk.py` computes from the SVG today. The checks stay
on the Gerber files.

### Gate

Stages P, G and E do not change. Stages S, L and F run the same checks on the same intermediate files; only
`fab.collect` gets those files from the tool chain.

| Check | KiCad side |
| --- | --- |
| L-1, L-4, L-7, L-10, L-12, L-13, L-14, L-18, L-20 | on `pcb.json` and `geometry.json`, filled from the `.kicad_pcb`; unchanged |
| L-2, L-8, L-15, L-16, L-17, F-5 | on the Gerber files; need the parser for KiCad's Gerber (K-2) |
| L-3 | KiCad's DRC report instead of EasyEDA's; schematic parity replaces the *Import Changes* item |
| L-5, L-11 | on the tracks of `pcb.json`; unchanged |
| F-1 | the BOM from the graph against `kicad-cli sch export bom` instead of `easyeda_bom_generate` |
| F-2, F-6 | unchanged |
| F-3 | CPL from `kicad-cli pcb export pos`, turned into JLCPCB's format; no offsets: every footprint is the LCSC data or the entry's `footprint_data` (decision 3) |

The rule IDs stay. The texts of `rules.json` that name EasyEDA (L-3, F-1 and some fixes) say "the EDA tool" and name
the tool chain in a second sentence. The negative tests run per tool chain wherever the check reads an EDA file: the
led-bar fixture gets a KiCad export of its input stage beside the EasyEDA one (`tests/fixtures/led-bar/`).

**Hashes:**

- **Circuit hash:** unchanged.
- **Layout hash:** the board file, the artwork and `geometry.json`, as today. The generated KiCad files are outputs and
  are not hashed.
- **Fab hash:** unchanged in method, but its value differs between the tool chains, so a fab sign-off (M-5) lapses
  when a project switches. That is right: the files that go to the manufacturer are new.

### Plugin, skills, agents

- The MCP server `easyeda` and the hook on its tools stay; in a KiCad project they are idle. `agreements.py` tells a
  session which tool chain the project uses.
- The skills `start`, `pcb-round`, `release`, `own-part` and `new-project` branch wherever they name EasyEDA steps
  (the claim, *Import Changes*, the operator agent). `new-project` asks for the tool chain in its interview.
- The agent `easyeda-operator` is EasyEDA's only. On the KiCad side the commands run in the session, because they
  take seconds, not minutes.
- `pcb-reviewer` gets its pictures from `kicad-cli pcb render` and `pcb export svg` instead of canvas captures. Its
  views and resolution are a **(probe)**.
- `edakit doctor` checks that `kicad-cli` is on the PATH and is major version 10, plus Freerouting and ngspice. It has
  no bridge lines.
- Project scripts: the kind `easyeda` stays EasyEDA's. A KiCad project has no project library outside its files, so
  its scripts are `input` or `derive`, and no kind `kicad` is needed.

## Gaps on the KiCad side

| # | Gap | Proposal | State |
| --- | --- | --- | --- |
| K-1 | KiCad has no auto-placer | edakit places in both tool chains: the section [Placement](#placement-edakit-places-for-both-tool-chains), step T.1 | decided by the user |
| K-2 | `gerber.py` reads only EasyEDA's subset | Extend the parser to the aperture macros KiCad writes (`RoundRect`, `Outline`, `FreePoly`, `RotRect`), ignore the X2 attributes, and read Excellon in mm with KiCad's header. The pad positions of `FlyingProbeTesting.json` come from `pcb.json` instead. Nets still come from the graph. | accepted |
| K-3 | Zone fill | `kicad-cli pcb drc --refill-zones --save-board` in KiCad 10 **(probe in T.7)**. L-2 and L-15 check the fill on the Gerber files either way. | accepted |
| K-4 | JLCPCB's rotation for KiCad library footprints | No footprint comes from KiCad's library (decision 3), so there is nothing to correct | closed by decision 3 |
| K-5 | Vector PDF of the schematic | `kicad-cli sch export pdf`. Today's EasyEDA path needs the patched bridge, so this is a gain, not a gap. | – |

## Scope

In:

- the tool chain key and the back-end interface;
- edakit's placer for both tool chains;
- KiCad writers and readers for the schematic, library, PCB, routing, pours, silkscreen and DRC rules;
- gate stages S, L and F on KiCad;
- doctor, skills and handbook.

Out:

- importing an existing KiCad design into a graph (`project-surveyor` lists it as hardware data; that needs a concept
  of its own);
- KiCad's interactive router and push-and-shove;
- more than two copper layers (edakit's limit, not KiCad's);
- a GUI plugin inside KiCad;
- manufacturers other than JLCPCB.

## Order

The KiCad work ran on a branch of its own (decision 6), without waiting for the live runs of 2.1 to 2.4 and 3.6, and
went to main on 2026-10-30. Each step is built with add-feature, test first, as in
[implementation-plan.md](../new/implementation-plan.md). Each step leaves a project without `toolchain = "kicad"` as it
is: T.1 changes nothing until `--rest` is given.

| Step | What | Size | Needs | Waits for | State |
| --- | --- | --- | --- | --- | --- |
| T.1 | `pcb place --rest`: edakit places every part without a row, deterministically, for both tool chains | M–L | – | – | built (b66c249); a real board is open |
| T.2 | `edakit/toolchain/`: dispatch at the commands, EasyEDA behind it where it is; every test passes as before and offline runs stay byte-identical | M | – | – | built (b2852f2, 6222f1f) |
| T.3 | `[project] toolchain`, the KiCad folder `<artifacts>/kicad/<board>/`, config checks, `doctor` per tool chain | S | – | T.2 | built (b2852f2, de2e95d) |
| T.4 | `kicad/sexp.py`, `kicad/library.py`: footprints and symbols from the parts database; both footprint sources side by side for the fixture's parts (decision 3) | M | – | – | built (b2852f2, ca16159); the side-by-side is dropped: decision 3 stands |
| T.5 | `kicad/board.py` reads `.kicad_pcb` into `board.json`, `pcb.json` and `geometry.json`, rounded as the EasyEDA side rounds; round-trip tests | M | – | T.4 | built (b2852f2) |
| T.6 | `gerber.py` for KiCad's Gerber and drill files (K-2), on a recorded KiCad export of the fixture | M | KiCad once | – | built on files written as KiCad writes them (6222f1f); a recorded export is open |
| T.7 | `kicad/board.py` writes outline, holes, parts, nets and the rule set; the SES as tracks and vias; zones filled through `kicad-cli`; the silkscreen | L | KiCad (probe) | T.5 | built (b2852f2, 6222f1f, 37e3335); probe open |
| T.8 | `kicad/schematic.py` from `Layout`; S-2 through `kicad-cli` (netlist and ERC) | M | KiCad | T.4 | built (ca16159) |
| T.9 | `kicad/cli.py`: ERC, DRC, exports; stages L and F on KiCad; `export` with `kicad_<board>.zip` | M | KiCad | T.6, T.7, T.8 | built (6222f1f, 37e3335) |
| T.10 | Skills, agents, hook, handbook (new chapter 16, 2 setup, 10 reference), README | M | – | T.9 | built |
| T.11 | Comparison run: one project through both tool chains, `fab diff` of the two gate runs | – | – | – | dropped (decision 7) |
| T.12 | CI: the fixture's stages S, L and F with `kicad-cli` in a container with KiCad 10 | S | KiCad | T.9 | built: the job `kicad` in tests.yml, `tests/test_kicad_live.py` |

T.1, T.2, T.4 and T.6 have no predecessor and can run in parallel. `pcb autolayout` goes after T.1 has placed a real
board that routed and passed the gate.

## Live test

The steps for the first session with a real KiCad 10 and EasyEDA, after CI has run them on the led-bar example with
test footprints (handbook 16.8). Each on a scratch copy; the bell's repository does not change.

1. **Setup.** KiCad 10 from KiCad's PPA (handbook 16.2); in a KiCad project `edakit doctor 2>&1 | cat` shows
   "KiCad 10.0.x (kicad-cli: …)" and no bridge lines.
2. **The example as a KiCad project.** A copy of `tests/fixtures/led-bar` with `toolchain = "kicad"` in `[project]` and
   without `template`, `schematic`, `pcb` in `[boards.main]`. `edakit schematic create`: "schematic = graph: yes"; open
   `build/edakit/kicad/main/main.kicad_sch` in KiCad and look at it – symbols, labels, notes, readability.
3. **The PCB.** `edakit pcb apply`: every footprint read from the LCSC library at first (network), no pad off the plan;
   open `main.kicad_pcb` – the footprints' silkscreen and polarity marks as EasyEDA shows them, the parts on their rows.
   `edakit pcb dump`, `edakit check`: P-10 where an entry has footprint data.
4. **Routing.** `edakit route all 2>&1 | cat`: Freerouting, tracks and vias into the file, zones filled, KiCad's DRC
   0. `edakit silk apply`: designators placed, the pictures `silk_main_*.png`.
5. **Gate.** `edakit gate --eda 2>&1 | cat`: every row of L and F runs (not released: the sign-offs are the example's).
   Look at L-2, L-8, L-15, L-17, F-1, F-3, F-5 and the polarity sheet; `edakit export`: `kicad_main.zip`.
6. **Placer (T.1).** On copies with rows taken out of `[place]`: `edakit pcb place --rest --write`, then `pcb plan` –
   once on a copy without `toolchain` (EasyEDA, and `route all` there), once on the KiCad copy.
7. **The bell**, a scratch copy of its main board, steps 2 to 5.

## Decisions

| # | Question | Decision | Status |
| --- | --- | --- | --- |
| K-1 | Who places the parts without a host | edakit, in both tool chains; EasyEDA's auto-layout goes after T.1 | the user's choice, 2026-10-30 |
| 1 | Tool chain per project or per board | per project | the user's choice, 2026-10-30 |
| 2 | Files plus `kicad-cli`, `pcbnew` Python, or the IPC API | files plus `kicad-cli`, including the zone fill, so no `pcbnew` | decided by Claude; the user left it to Claude |
| 3 | Footprints from the LCSC data or from KiCad's library | the LCSC data; a part whose LCSC footprint is wrong or missing gets `footprint_data`. No choice of KiCad's library per entry: `kicad_footprint` and `jlc_offset` are dropped | decided by Claude because the user left it open; the user accepted the reason and dropped `kicad_footprint`, 2026-10-30 (section "Library") |
| 4 | Least KiCad version | KiCad 10, the newest for Ubuntu: 10.0.x from KiCad's PPA `ppa:kicad/kicad-10.0-releases` (Ubuntu 24.04). Ubuntu's own packages are older, and KiCad recommends the PPA. `doctor` checks the major version; a new major version is a step of its own | the user's choice ("the latest available for Ubuntu"), 2026-10-30 |
| 5 | Is the KiCad project versioned | like the EasyEDA project: no. It is generated into `<artifacts>/kicad/<board>/`, and `edakit export` keeps a copy | the user's choice ("mirror EasyEDA"), 2026-10-30 |
| 6 | Order relative to the open steps of the implementation plan | a branch of its own that does not wait for the live runs; T.2 is a thin dispatch so the rebase stays small | the user's choice, 2026-10-30 |
| 7 | A comparison run – one project through both tool chains, `fab diff` of the two gate runs – as a check of the gate or as the acceptance test of the KiCad writers | none. The KiCad tool chain stands on the gate's checks of what KiCad exports, as the EasyEDA tool chain does on EasyEDA's, and edakit's KiCad code on its tests (offline, and in CI with KiCad 10). Whether the two tool chains give the same files is no criterion | the user's choice, 2026-10-30 |

## Sources

- edakit at `bf7450a`:
  - EasyEDA client and claim: [eda.py](../../../edakit/eda.py), [lock.py](../../../edakit/lock.py),
    [hooks.json](../../../hooks/hooks.json).
  - PCB and routing: [pcb.py](../../../edakit/pcb.py) (`auto_place`, `spot_candidates`, `find_spot`, `wirelength`,
    `autolayout`, `takeover`), [route.py](../../../edakit/route.py) (`read_board`, `write_dsn`, `read_ses`,
    `apply_ses`, `sexp`).
  - Schematic: [schematic.py](../../../edakit/schematic.py),
    [schematic_layout.py](../../../edakit/schematic_layout.py),
    [schematic_draw.py](../../../edakit/schematic_draw.py).
  - Silkscreen and parts: [silk.py](../../../edakit/silk.py), [footprint.py](../../../edakit/footprint.py),
    [part.py](../../../edakit/part.py) (`library_part`, which names a KiCad library as its possible replacement;
    `part diff`'s fit).
  - Files and export: [gerber.py](../../../edakit/gerber.py), [drc_rules.py](../../../edakit/drc_rules.py),
    [export.py](../../../edakit/export.py), [config.py](../../../edakit/config.py) (`BOARD_KEYS`, `artifacts`).
  - Gate: [gate.py](../../../edakit/release/gate.py), [fab.py](../../../edakit/release/fab.py) (`collect`, the L and
    F checks).
  - Skill [new-project](../../../skills/new-project/SKILL.md) (`.gitignore`).
- Handbook [1](../../../handbook/01-approach.md), [7](../../../handbook/07-pcb.md),
  [8](../../../handbook/08-release-gate.md), [9](../../../handbook/09-easyeda-api.md).
- Concepts [design-as-text.md](design-as-text.md) (gaps 1–3, decision 4),
  [parallel-easyeda.md](../new/parallel-easyeda.md), [implementation-plan.md](../new/implementation-plan.md) (2.1 and
  its live run).
- KiCad:
  - 10.0, released in March 2026, with the Ubuntu PPA and its install steps:
    [kicad.org/download/ubuntu](https://www.kicad.org/download/ubuntu/).
  - The command-line reference: [docs.kicad.org/10.0/en/cli/cli.html](https://docs.kicad.org/10.0/en/cli/cli.html).
    It covers `sch erc`, `sch export netlist/bom/pdf`, `pcb drc` with `--refill-zones` and `--save-board`,
    `pcb export gerbers/drill/pos/pdf/svg` and `pcb render`.
  - The SWIG module to be removed in KiCad 11:
    [dev-docs.kicad.org/en/apis-and-binding/pcbnew](https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/).
  - The S-expression file formats (`.kicad_sch`, `.kicad_pcb`, `.kicad_sym`, `.kicad_mod`, `.kicad_dru`).
  - Points marked (probe) are not verified; the flags and report formats of `kicad-cli` are checked against an
    installed KiCad 10 in T.3.
