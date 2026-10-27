# 10 Reference: edakit.toml, the project files and the commands

## 10.1 edakit.toml

Lookup: `--config PATH`, `$EDAKIT_CONFIG`, then `edakit.toml` in the current directory or a parent. Relative paths
are relative to it. edakit.toml is the table of contents: what the project is, which boards it has, where their files
are. What one role decides lives in a file of its own, with one owner and one hash (8.2):

| File | Content | Written by | Hash |
|---|---|---|---|
| `edakit.toml` | project, boards with their EasyEDA documents, where the files are, release settings | new-project, the user | – |
| `hardware/graph.json` | the circuit with its purpose, the hand-over to the layout, the ground net and the check settings (3.1) | circuit designer | circuit |
| `hardware/parts/`, `hardware/sim.json` | parts database (4), simulation scenarios (5) | part-selector, circuit designer | circuit |
| `hardware/schematic.toml` | arrangement of the schematic: blocks, notes, pin table (10.3) | circuit designer | – |
| `hardware/boards/<name>.toml` | one board: outline, holes, placement, routing, pours, silkscreen (10.2) | PCB designer | layout |
| `hardware/signoff.json` | sign-offs and accepted warnings (8.2) | reviewers, the user | – |

Complete example: [tests/fixtures/led-bar](../tests/fixtures/led-bar/). A key edakit does not know is an error with
the list of the known ones – a typo does not fall back to a default unnoticed. An edakit.toml that still holds the
board, the schematic or the checks (the earlier one-file form) is refused with a list of what goes where.

### [project]

| Key | Default | Meaning |
|---|---|---|
| `name` | – (required) | EasyEDA project (friendly name) |
| `company` | `""` | title block of the schematics |
| `quantity` | `5` | boards per order (stock checks P-4 and F-2) |
| `distributors` | `["lcsc"]` | where the agent part-selector searches, in this order: `lcsc`, `rs`, `farnell`, `mouser`, `digikey`, `reichelt` (chapter 4.2) |
| `lock` | `auto` | EasyEDA claim between Claude sessions: `auto` (when `CLAUDE_CODE_SESSION_ID` is set) or `off` |
| `agreements` | `true` | the working agreements of handbook 11.4, one line each, in the context of every Claude Code session in the project (plugin hook at session start); `false` turns it off |
| `graph` | `hardware/graph.json` | the hardware graph |
| `parts` | `hardware/parts` | parts database, one JSON per part (LCSC number or manufacturer part number) |
| `sim` | `hardware/sim.json` | simulation config (chapter 5) |
| `sim_plugin` | – | optional Python file with `MODELS` and `checks` (5.1) |
| `schematic` | `hardware/schematic.toml` | the schematic file (10.3) |
| `signoff` | `hardware/signoff.json` | the sign-off file (8.2) |
| `artifacts` | `build/edakit` | caches, previews, routing files, exports, Gerber exports (not versioned) |
| `reports` | `build/release` | gate runs |
| `datasheets` | `<artifacts>/datasheets` | the datasheets `edakit part fetch` keeps, `<key>.pdf` and `<key>.json` (4.6); a folder in the repository versions them |
| `stock` | `hardware/stock.json` | the stock snapshot of `edakit stock` (P-4, 4.2); versioned, outside the circuit hash |
| `stock_margin_pct` | `0` | P-4 warns when the assembler's stock is below the need plus this margin |
| `stock_max_age_days` | `14` | an older snapshot (or snapshot row) is pending in P-4 – it blocks the release, not `edakit check` |
| `spare_pct` | `0` | `edakit order`: spares on every cart line, in % of `quantity` sets (rounded up) |

The name of the ground net is in the graph (`ground`, default `GND`), with the circuit it belongs to; nets that are
ground on purpose besides it (an analog ground) in `grounds` (3.1, G-16).

### [boards.&lt;name&gt;]

| Key | Default | Meaning |
|---|---|---|
| `title` | the board name | page name of the board schematic |
| `template` | `generated_<name>` | schematic generated from the graph |
| `schematic` | `layout_<name>` | board schematic (the PCB is linked to it) |
| `pcb` | `<name>` | PCB document in EasyEDA |
| `file` | `hardware/boards/<name>.toml` | the board file (10.2); while it does not exist the board has no layout yet – a file named here must exist |

### [release]

`layout_files` (further files in the layout hash – the board files and the footprint geometry are always in it),
`state_files` (further files in the circuit hash), `assembly` ({`sides` (both), `smd_only`, `paste_gap_mm` (0.4: SMD
pads of different parts on an assembled side, L-14), `pcba` (`"economic"` or `"standard"`: the assembler's class of
the order, P-4; default from `sides` – one side Economic, two Standard)}), `[[stages]]` ({`id`, `name`, `cmd`, `advisory`, `timeout`,
`about`}).

### [cost]

Optional: the order estimate of `edakit cost` (8.4). Without the table the gate and every command are as before; with
it the gate has an information row "estimated order cost" in stage P, and above `budget` a warning to accept.

| Key | Default | Meaning |
|---|---|---|
| `fees` | the shipped `edakit/fees/jlcpcb.json` | another fee table in the same form (every value with `date` and `source`) |
| `budget` | – | the most the whole order may cost, in `currency`; above it `edakit cost` exits 2 and the gate warns |
| `currency` | `"USD"` | the currency of the estimate |
| `rates` | `{}` | the value of one unit of another currency in `currency`, e.g. `{ EUR = 1.15 }`; needed for the fee table's USD and for every `[[extra]]` in another currency |
| `shipping`, `coupon` | `0` | per order, in `currency` |
| `vat_pct` | `0` | import VAT on the assembler's order (boards + shipping − coupon) |
| `pcb_price` | from the fee table | the quoted price of the PCBs (all `quantity` of them) – a number, or `{ board = price }` |

### [[extra]]

Items off the board that belong to the order – a cable, feet, a module that is plugged in: `item`, `supplier`,
`per_set` (pieces per board set) – these three are required –, `code` (the supplier's order code), `spare` (pieces on
top), `moq` (the supplier's minimum), `step` (its pack size), `unit_price` and its `currency` (default
`[cost] currency`). `edakit order` puts each into the cart of its supplier, `edakit cost` prices the cart quantity:
ceil(`per_set` × `quantity` × (1 + `spare_pct`/100)) + `spare`, at least `moq`, a multiple of `step`.

## 10.2 The board file

`hardware/boards/<name>.toml`: what the PCB designer decides (14.1). The layout hash covers it – a change needs the
layout review again (M-5). The keys stand at the top of the file, without a prefix (`[place]`, `[[holes]]`):

| Key | Default | Meaning |
|---|---|---|
| `revision` | – | board revision, printed with the title (`silk.board_label`); without it no board label |
| `view` | `top` | side the plan is drawn from; `bottom` mirrors x and rotations |
| `edge_ok` | `[]` | parts that may touch or overhang the outline |
| `on_headers` | `[]` | parts that stand on pin headers: an SMD part of their side may sit under them, clear of `header_keep_mm` around each of their through-hole pins; a through-hole part under them stays an overlap (7.4) |
| `header_keep_mm` | `1.27` | half width of the square around each through-hole pin of an `on_headers` part that SMD parts of its side stay out of (mm) |
| `silk_overlap_mm` | `0` | how far the boxes (silkscreen included) of two SMD parts of one side may reach into each other, in x and in y, before the plan check reports them (mm); with a through-hole part it does not apply (7.4) |
| `near_mm` | `6` | maximum gap for `near` (of the plan and of the graph's `layout`) and the decoupling of L-12 |
| `edge_mm` | `1` | maximum distance from the outline for the graph's `layout.edge` (L-12) |
| `park` | `[10, -15]` | where new parts are dropped (mm, EasyEDA coordinates) |
| `outline` | – | `rect = [w, h]` (+ `origin`, `corner_radius`, `arc_steps`) or `polygon = [[x, y], …]` |
| `[[holes]]` | `[]` | `x`, `y`, `d` (3.2), `keep` (radius free of parts and copper) |
| `tooling` | – | `holes = [[x, y], …]`, `d` (1.152), `mask` (0.148), `keep` (1.5) |
| `place` | `{}` | `REF = {x, y, rot, side, lock}` fixed parts |
| `near` | `{}` | `PART = "HOST"` or a list – the layout's own, between fixed parts; the circuit's are `layout.near` of the graph |
| `routing` | see below | Freerouting rules |
| `[[pours]]` | GND on both layers | `net`, `layers`, `plane` (bool), `fanout` (false: with `plane`, every SMD pad of the net on the other layer gets a protected via to the plane and a stub, 7.5), `stitch` (layer), `priority`, `line_mil`, `pour_only` (false: the net gets no tracks, its pour connects it; on every entry of the net, not with `plane`), `clearance_mm` (0.25: what the computed pour keeps from foreign copper – the EasyEDA copper-area rule), `min_width_mm` (0.25: the narrowest neck it fills); both also for every pour on a shared layer with `pour_regions` |
| `pour_regions` | `false` | nets that share a pour layer get outlines of their own area, claimed in `priority` order (7.6); no `plane` on such a layer |
| `pour_min_piece_mm2` | `2.0` | with `pour_regions`: the smallest piece (outside the net's own copper and clearance) that gets an outline |
| `pour_inset_mm` | edge clearance + 0.1 | how far the pours lie inside the outline (mm): the outline of `pcb pour` and `route pours` and every computed pour; without it `routing.edge_clearance_um` / 1000 + 0.1; the tracks keep `edge_clearance_um` either way (7.6) |
| `silk` | `{}` | `designators` (side), `hide` (sides), `label_h_mm` (1.0), `gap_mm` (0.25), `groups` {label: [refs]}, `unlabelled` ({designator = reason}, none: a part of the `designators` side without a visible designator or group label is an L-17 warning), `priority` (["TP"]), `solder_side` (`false`; `true`: the through-hole parts of the other side are labelled on the `designators` side too, 7.7), `board_label` (`"{title} rev {revision}"`; also `{project}`, `{board}`; `""` = none), `board_label_corner` (`bottom-left`, seen from the printed side), `board_label_h_mm` (1.2), `board_label_side` (the `designators` side; `"top"` or `"bottom"`, 7.7), `board_label_region` (the whole board; a polygon `[[x, y], …]` in plan mm the label must lie in, `board_label_corner` then means its corner, 7.7), `[[art]]` ({`svg`, `x`, `y`, `width_mm`, `rot`, `side`}), `[[texts]]` ({`text`, `x`, `y`, `h_mm` (1.2), `rot`, `side`, `font` (`default` = stroke font, or a font family EasyEDA knows)}) |
| `[[loops]]` | `[]` | `a`, `b` (pads "D1.2"), `max_mm`, `what` – check L-11; the circuit's are `layout.loops` of the graph |
| `copper` | see below | copper per layer in the Gerber files, check L-15 |
| `order` | – | the order form fields of this board (8.4); with the table the gate writes `fab/<board>/order.md` and runs F-6: `finish` (`"LeadFree HASL"`), `mark` (`"default"`, `"specify"`: at the placeholder `JLCJLCJLCJLC`, `"remove"`), `remark` (`""`; at most 200 ASCII characters), `tab_zones` (`[]`: `{from = [x, y], to = [x, y]}`, two points on the outline in plan mm – the shorter stretch between them), `tab_copper_mm` (`1.0`: no copper of either side this close to a tab zone) |
| `net_classes` | see below | track widths from the simulated currents |

`[routing]`: `clearance_mil` (6.5; also the least gap between pads of different parts, L-13), `signal_mil` (10), `via` ([24, 12]), `edge_clearance_um` (400: tracks and vias
from the outline, in the DSN and in Freerouting; the pours: `pour_inset_mm`), `passes` (40),
`attempts` (5), `layer_cost` ({TOP = [1.0, 1.8], BOTTOM = [1.5, 2.5]}), `classes` ({NAME = {width_mil, nets}}),
`[[routing.keepouts]]` ({layer, what = "wire"|"all", rect | polygon, windows, window_mm}), `[[routing.fixed_wires]]`
({net, layer, width_mil, points}).

`[copper]`: `max_bare_mm` (5: the largest copper-free circle inside the pour outline of a layer that `[[pours]]` pours;
above it L-15 warns), `min_cover` (`{TOP = %, BOTTOM = %}`, none: the least copper share of the board area per layer;
below it L-15 warns).

`[net_classes]`: `NAME = {min_a, width_mm}` – class by the largest simulated current, practical minimum width (default
POWER ≥ 0.3 A 0.6 mm, SUPPLY ≥ 0.1 A 0.4 mm, SIGNAL 0.25 mm). `force = {NET = "CLASS"}` pins a net to a class (e.g. a
switching node).

## 10.3 The schematic file

`hardware/schematic.toml`: `stub` (10): stub length of the template. `[layout]`: `rows` (rows → columns → blocks
`{title, start}`), `power_flags` ({NET = "Ground"|"Power"}), `near` ({CAP = "PART"}), `stacked` (blocks whose trees
stand one below the other), `[layout.notes]` ({block title = [lines]}), `[layout.pin_table]` (`component`, `block`,
`prefix`, `notes` {NET = "function"}). It changes no hash – the drawing explains the circuit, it is not the circuit.
Without the file `edakit schematic draw` arranges the schematic by itself (6.5).

## 10.4 Commands

All commands: `--config`, `-v` (MCP traffic). Exit codes: 0 ok, 2 findings, 1 error. With uv from snap inside Claude
Code: `edakit … 2>&1 | cat`.

| Command | EasyEDA | Reads | Writes |
|---|---|---|---|
| `edakit check [--release] [--json F]` | – | graph, parts (pins, identity P-6), pin table; if there: footprint geometry and library footprints (P-7), library symbols (P-1) | – |
| `edakit rules [ID …]` | – | the rule catalog (no project needed) | – |
| `edakit hints [--json F]` | – | graph, parts, sim config | – |
| `edakit block list\|show NAME` | – | the block library (no project needed) | – |
| `edakit block add NAME --as I [--connect PORT=NET …] [--board B] [--file F] [--dry-run]` | – | graph, parts, block | graph (formatting kept), missing parts entries |
| `edakit part import LCSC [--update]` | – (internet) | EasyEDA's public component data of that number (4.2) | a new `hardware/parts/<LCSC>.json`, else nothing (`--update`: the fields it lacks); `<artifacts>/library/<LCSC>.json`, `<artifacts>/footprints/<footprint>.json`; exit 2 = the entry differs |
| `edakit part diff OLD NEW [--json F]` | – | geometry of both (the dump of a placed part, else the library footprint of `part import`), their parts entries (roles, `lead`), graph | – (F: the comparison as JSON); exit 0 = drop-in, 2 = something to decide (7.3) |
| `edakit part fetch KEY [--url U] \| --all` | – (internet) | the parts entry (`mpn`, `datasheet.url`, `lcsc`, `verified.datasheet_sha256`); the sources of 4.6 | `<datasheets>/<KEY>.pdf` and `.json` (a failed download keeps the earlier copy, exit 2; variant or changed since the sign-off: exit 2) |
| `edakit part search "KEYWORDS" [--basic] [--min-stock N] [--limit 25] [--json F]` | – (internet) | JLCPCB's public parts catalogue (4.2) | – (F: the hits); exit 2 = no hits |
| `edakit part datasheet [--connector C …] [--name N]` | – | graph, parts, sim config, board file (4.5) | `hardware/datasheet/<N>.json` and `.md`; without `--connector` every datasheet renewed |
| `edakit stock [--board B] [--refresh]` | – | graph, parts, the snapshot; JLCPCB's catalogue and part pages (network) | `hardware/stock.json` (`[project] stock`): the parts missing, unread or older than `stock_max_age_days`, with `--refresh` all |
| `edakit stock --lcsc C…` | – | JLCPCB's catalogue and part pages (no project needed) | – (prints listed, class, stock, MSL, PCBA type, X-ray, attrition) |
| `edakit cost [--board B] [--json F]` | – | graph, parts, board files, the stock snapshot, the fee table, `[cost]`, `[[extra]]` | `<artifacts>/cost.json` (the change since the last estimate is printed); exit 2 above `budget` |
| `edakit order [--out DIR]` | – | graph, parts (`order`), board files (side), `[[extra]]`, `spare_pct` | `<artifacts>/order/` or DIR: `bom_<board>.csv` (the F-1 BOM), `cart_<supplier>.csv`, `hand_assembly.md` |
| `edakit part own PATH [--name N]` | – | the board's project at PATH: its datasheet, state, git, gate runs | `hardware/parts/<N>.json` |
| `edakit sim [--json F] [--keep DIR]` | – | graph, parts, sim config, plugin | `<artifacts>/sim/net_currents.json` |
| `edakit handover [--board B]` | – | graph, parts, sign-offs | – |
| `edakit schematic create [--board] [--only] [--dry-run] [--save] [--create-project] [--refresh-devices]` | ✓ | graph | template, `device_cache.json`, `schematic_map_<name>.json` |
| `edakit schematic check [--schematic] [--no-pins] [--json F]` | ✓ read | graph, schematic | – |
| `edakit schematic copy [--source] [--target] [--save]` | ✓ | schematic | copy |
| `edakit schematic layout [--dry-run] [--reread] [--force] [--save]` | ✓ / – | graph, schematic, cached geometry | board schematic, `layout_preview_<name>.svg` |
| `edakit schematic draw [--board] [--out F] [--force]` | – | graph, parts, the schematic file if there | `schematic_<board>.svg` (or F) |
| `edakit pcb dump [--ref]` | ✓ | PCB | `pcb_geometry_<board>.json` (parts end at 0°/TOP; through-hole pads with `hole` [w, l] mm and `plated`) |
| `edakit pcb plan` | – | plan, geometry (the dump; library footprints of `part import` for parts not in it), net currents, graph (`layout`, L-12) | `pcb_plan_<board>.png/.json`, `pcb_netclasses_<board>.json` |
| `edakit pcb parts [--write]` | ✓ | board schematic, PCB, graph | PCB parts, UniqueIds, geometry |
| `edakit pcb nets [--write]` | ✓ | graph, PCB | pad nets |
| `edakit pcb apply [--verify-all]` | ✓ | plan, geometry | outline, holes, tooling, fixed parts |
| `edakit pcb autolayout` | ✓ | – | positions of unlocked parts |
| `edakit pcb tooling` / `pour` | ✓ | plan; `pour` with `pour_regions`: board file and SES of `route` | tooling holes / pours (unfilled) |
| `edakit route all\|read\|dsn\|route\|check\|apply\|verify [--cleanup]\|pours\|reload\|drc\|save` | ✓ / – (dsn, route, check offline) | PCB, rules | `route/<board>_board.json`, `.dsn`, `.ses`, `_routing.png`, `_drc.json`; tracks, vias, pours |
| `edakit silk apply\|check` | ✓ | PCB, Gerber export | designators, `silk_<board>_<side>.png`, `gerber_<board>/`; apply: `silk_footprints_<board>/` (the print it found, for L-17) |
| `edakit export [--board]` | ✓ read | schematic, PCB, project file | `<artifacts>/export/` |
| `edakit gate [--easyeda]` | – / ✓ | everything | `<reports>/<run>/` |
| `edakit fab --board B --out DIR [--offline]` | ✓ / – | PCB, exports, `route/<board>_board.json` (L-13, L-14), `silk_strings_<board>.json` and `silk_footprints_<board>/` (L-17), the stock snapshot (`order.md`) | `DIR/<board>/`, with `[order]` also `order.md` |
| `edakit lock [status\|claim\|release\|yield CHAT\|hook] [--note]` | – | – | `~/.local/state/edakit/easyeda-lock.json` |
| `edakit proposal template [--feature]\|seal FILE [--out F]\|verify FILE` | – | a rule or feature proposal (no project needed) | seal: the issue body with its SHA-256 |
| `edakit doctor` | – | tool chain | – |

## 10.5 Files in a project

```text
edakit.toml                 the table of contents: project, boards, where the files are
hardware/graph.json         the hardware graph (only source of parts and connections), ground net, check settings
hardware/parts/*.json       parts database
hardware/datasheet/<name>.* the board as a part for other projects: parts entry and datasheet (edakit part datasheet)
hardware/sim.json           simulation scenarios
hardware/stock.json         what the assembler said about the parts, dated (edakit stock, P-4)
hardware/schematic.toml     arrangement of the schematic
hardware/boards/<name>.toml one board: outline, holes, placement, routing, pours, silkscreen
hardware/signoff.json       manual checks and accepted warnings, bound to hashes
docs/decisions.md           numbered decisions (or wherever the project keeps them)
build/edakit/               artifacts (not versioned): caches, geometry, previews, routing, exports, cost.json;
                            library/ and footprints/: the library's symbols and footprints (edakit part import);
                            datasheets/: the datasheets edakit part fetch keeps (unless [project] datasheets names
                            another folder)
build/release/<run>/        gate runs (archive the released one)
```
