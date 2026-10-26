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
board, the schematic or the checks (the earlier one-file form) is refused with a list of what goes where;
`scripts/split_config.py` of edakit moves such a project once and takes its valid sign-offs along – in the project:
`uv run --project <edakit> python <edakit>/scripts/split_config.py --dry-run`, then without `--dry-run`.

### [project]

| Key | Default | Meaning |
|---|---|---|
| `name` | – (required) | EasyEDA project (friendly name) |
| `company` | `""` | title block of the schematics |
| `quantity` | `5` | boards per order (stock check F-2) |
| `distributors` | `["lcsc"]` | where the agent part-selector searches, in this order: `lcsc`, `rs`, `farnell`, `mouser`, `digikey`, `reichelt` (chapter 4.2) |
| `lock` | `auto` | EasyEDA claim between Claude sessions: `auto` (when `CLAUDE_CODE_SESSION_ID` is set) or `off` |
| `graph` | `hardware/graph.json` | the hardware graph |
| `parts` | `hardware/parts` | parts database, one JSON per part (LCSC number or manufacturer part number) |
| `sim` | `hardware/sim.json` | simulation config (chapter 5) |
| `sim_plugin` | – | optional Python file with `MODELS` and `checks` (5.1) |
| `schematic` | `hardware/schematic.toml` | the schematic file (10.3) |
| `signoff` | `hardware/signoff.json` | the sign-off file (8.2) |
| `artifacts` | `build/edakit` | caches, previews, routing files, exports, Gerber exports (not versioned) |
| `reports` | `build/release` | gate runs |

The name of the ground net is in the graph (`ground`, default `GND`), with the circuit it belongs to.

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
`state_files` (further files in the circuit hash), `assembly` ({`sides`, `smd_only`}), `[[stages]]` ({`id`, `name`,
`cmd`, `advisory`, `timeout`, `about`}).

## 10.2 The board file

`hardware/boards/<name>.toml`: what the PCB designer decides (14.1). The layout hash covers it – a change needs the
layout review again (M-5). The keys stand at the top of the file, without a prefix (`[place]`, `[[holes]]`):

| Key | Default | Meaning |
|---|---|---|
| `revision` | – | board revision, printed with the title (`silk.board_label`); without it no board label |
| `view` | `top` | side the plan is drawn from; `bottom` mirrors x and rotations |
| `edge_ok` | `[]` | parts that may touch or overhang the outline |
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
| `silk` | `{}` | `designators` (side), `hide` (sides), `label_h_mm` (1.0), `gap_mm` (0.25), `groups` {label: [refs]}, `priority` (["TP"]), `board_label` (`"{title} rev {revision}"`; also `{project}`, `{board}`; `""` = none), `board_label_corner` (`bottom-left`, seen from the printed side), `board_label_h_mm` (1.2), `[[art]]` ({`svg`, `x`, `y`, `width_mm`, `rot`, `side`}), `[[texts]]` ({`text`, `x`, `y`, `h_mm` (1.2), `rot`, `side`, `font` (`default` = stroke font, or a font family EasyEDA knows)}) |
| `[[loops]]` | `[]` | `a`, `b` (pads "D1.2"), `max_mm`, `what` – check L-11; the circuit's are `layout.loops` of the graph |
| `net_classes` | see below | track widths from the simulated currents |

`[routing]`: `clearance_mil` (6.5), `signal_mil` (10), `via` ([24, 12]), `edge_clearance_um` (400: tracks and vias
from the outline, in the DSN and in Freerouting; the pours: `pour_inset_mm`), `passes` (40),
`attempts` (5), `layer_cost` ({TOP = [1.0, 1.8], BOTTOM = [1.5, 2.5]}), `classes` ({NAME = {width_mil, nets}}),
`[[routing.keepouts]]` ({layer, what = "wire"|"all", rect | polygon, windows, window_mm}), `[[routing.fixed_wires]]`
({net, layer, width_mil, points}).

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
| `edakit check [--release] [--json F]` | – | graph, parts, pin table | – |
| `edakit rules [ID …]` | – | the rule catalog (no project needed) | – |
| `edakit hints [--json F]` | – | graph, parts, sim config | – |
| `edakit block list\|show NAME` | – | the block library (no project needed) | – |
| `edakit block add NAME --as I [--connect PORT=NET …] [--board B] [--file F] [--dry-run]` | – | graph, parts, block | graph (formatting kept), missing parts entries |
| `edakit sim [--json F] [--keep DIR]` | – | graph, parts, sim config, plugin | `<artifacts>/sim/net_currents.json` |
| `edakit handover [--board B]` | – | graph, parts, sign-offs | – |
| `edakit schematic create [--board] [--only] [--dry-run] [--save] [--create-project] [--refresh-devices]` | ✓ | graph | template, `device_cache.json`, `schematic_map_<name>.json` |
| `edakit schematic check [--schematic] [--no-pins] [--json F]` | ✓ read | graph, schematic | – |
| `edakit schematic copy [--source] [--target] [--save]` | ✓ | schematic | copy |
| `edakit schematic layout [--dry-run] [--reread] [--force] [--save]` | ✓ / – | graph, schematic, cached geometry | board schematic, `layout_preview_<name>.svg` |
| `edakit schematic draw [--board] [--out F] [--force]` | – | graph, parts, the schematic file if there | `schematic_<board>.svg` (or F) |
| `edakit pcb dump [--ref]` | ✓ | PCB | `pcb_geometry_<board>.json` (parts end at 0°/TOP) |
| `edakit pcb plan` | – | plan, geometry, net currents, graph (`layout`, L-12) | `pcb_plan_<board>.png/.json`, `pcb_netclasses_<board>.json` |
| `edakit pcb parts [--write]` | ✓ | board schematic, PCB, graph | PCB parts, UniqueIds, geometry |
| `edakit pcb nets [--write]` | ✓ | graph, PCB | pad nets |
| `edakit pcb apply [--verify-all]` | ✓ | plan, geometry | outline, holes, tooling, fixed parts |
| `edakit pcb autolayout` | ✓ | – | positions of unlocked parts |
| `edakit pcb tooling` / `pour` | ✓ | plan; `pour` with `pour_regions`: board file and SES of `route` | tooling holes / pours (unfilled) |
| `edakit route all\|read\|dsn\|route\|check\|apply\|verify [--cleanup]\|pours\|reload\|drc\|save` | ✓ / – (dsn, route, check offline) | PCB, rules | `route/<board>_board.json`, `.dsn`, `.ses`, `_routing.png`, `_drc.json`; tracks, vias, pours |
| `edakit silk apply\|check` | ✓ | PCB, Gerber export | designators, `silk_<board>_<side>.png`, `gerber_<board>/` |
| `edakit export [--board]` | ✓ read | schematic, PCB, project file | `<artifacts>/export/` |
| `edakit gate [--easyeda]` | – / ✓ | everything | `<reports>/<run>/` |
| `edakit fab --board B --out DIR [--offline]` | ✓ / – | PCB, exports | `DIR/<board>/` |
| `edakit lock [status\|claim\|release\|yield CHAT\|hook] [--note]` | – | – | `~/.local/state/edakit/easyeda-lock.json` |
| `edakit proposal template [--feature]\|seal FILE [--out F]\|verify FILE` | – | a rule or feature proposal (no project needed) | seal: the issue body with its SHA-256 |
| `edakit doctor` | – | tool chain | – |

## 10.5 Files in a project

```text
edakit.toml                 the table of contents: project, boards, where the files are
hardware/graph.json         the hardware graph (only source of parts and connections), ground net, check settings
hardware/parts/*.json       parts database
hardware/sim.json           simulation scenarios
hardware/schematic.toml     arrangement of the schematic
hardware/boards/<name>.toml one board: outline, holes, placement, routing, pours, silkscreen
hardware/signoff.json       manual checks and accepted warnings, bound to hashes
docs/decisions.md           numbered decisions (or wherever the project keeps them)
build/edakit/               artifacts (not versioned): caches, geometry, previews, routing, exports
build/release/<run>/        gate runs (archive the released one)
```
