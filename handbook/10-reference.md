# 10 Reference: edakit.toml and commands

## 10.1 edakit.toml

Lookup: `--config PATH`, `$EDAKIT_CONFIG`, then `edakit.toml` in the current directory or a parent. Relative paths
are relative to the file. Complete example: [the Christmas bell's edakit.toml](https://github.com/tgd1975/automatic_christmas_bell/blob/main/edakit.toml).

### [project]

| Key | Default | Meaning |
|---|---|---|
| `name` | – (required) | EasyEDA project (friendly name) |
| `graph` | `hardware/graph.json` | the hardware graph |
| `parts` | `hardware/parts` | parts database, one JSON per LCSC number |
| `artifacts` | `build/edakit` | caches, previews, routing files, exports, Gerber exports (not versioned) |
| `reports` | `build/release` | gate runs |
| `company` | `""` | title block of the schematics |
| `ground` | `GND` | name of the ground net |
| `quantity` | `5` | boards per order (stock check F-2) |
| `lock` | `auto` | EasyEDA claim between Claude sessions: `auto` (when `CLAUDE_CODE_SESSION_ID` is set) or `off` |

### [boards.&lt;name&gt;]

| Key | Default | Meaning |
|---|---|---|
| `title` | the board name | page name of the board schematic |
| `template` | `generated_<name>` | schematic generated from the graph |
| `schematic` | `layout_<name>` | board schematic (the PCB is linked to it) |
| `pcb` | `<name>` | PCB document in EasyEDA |
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
| `[[pours]]` | GND on both layers | `net`, `layers`, `plane` (bool), `stitch` (layer), `priority`, `line_mil` |
| `silk` | `{}` | `designators` (side), `hide` (sides), `label_h_mm` (1.0), `gap_mm` (0.25), `groups` {label: [refs]}, `priority` (["TP"]), `board_label` (`"{title} rev {revision}"`; also `{project}`, `{board}`; `""` = none), `board_label_corner` (`bottom-left`, seen from the printed side), `board_label_h_mm` (1.2), `[[art]]` ({`svg`, `x`, `y`, `width_mm`, `rot`, `side`}), `[[texts]]` ({`text`, `x`, `y`, `h_mm` (1.2), `rot`, `side`, `font` (`default` = stroke font, or a font family EasyEDA knows)}) |
| `[[loops]]` | `[]` | `a`, `b` (pads "D1.2"), `max_mm`, `what` – check L-11 |

`[boards.<name>.routing]`: `clearance_mil` (6.5), `signal_mil` (10), `via` ([24, 12]), `edge_clearance_um` (400),
`passes` (40), `attempts` (5), `layer_cost` ({TOP = [1.0, 1.8], BOTTOM = [1.5, 2.5]}), `classes`
({NAME = {width_mil, nets}}), `[[keepouts]]` ({layer, what = "wire"|"all", rect | polygon, windows, window_mm}),
`[[fixed_wires]]` ({net, layer, width_mil, points}).

### [net_classes]

`NAME = {min_a, width_mm}` – class by the largest simulated current, practical minimum width (default POWER ≥ 0.3 A
0.6 mm, SUPPLY ≥ 0.1 A 0.4 mm, SIGNAL 0.25 mm). `force = {NET = "CLASS"}` pins a net to a class (e.g. a switching node).

### [schematic]

`stub` (10): stub length of the template. `[schematic.layout]`: `rows` (rows → columns → blocks `{title, start}`),
`power_flags` ({NET = "Ground"|"Power"}), `near` ({CAP = "PART"}), `stacked` (blocks whose trees stand one below the
other), `[schematic.layout.notes]` ({block title = [lines]}), `[schematic.layout.pin_table]` (`component`, `block`,
`prefix`, `notes` {NET = "function"}).

### [sim]

`config` (`hardware/sim.json`, chapter 5), `plugin` (optional Python file with `MODELS` and `checks`).

### [checks]

`pin_locks` ({"U1.4" = "NET"}), `reverse_protect` (connectors that may be plugged the wrong way: G-10; also a power
input for the design hints), `doc_pin_table` ({`component`, `file`, `prefix`, `regex`}).

### [release]

`signoff` (`hardware/signoff.json`), `layout_files` (["edakit.toml"]; the footprint geometry is always added),
`state_files` (extra files in the circuit hash), `assembly` ({`sides`, `smd_only`}), `[[stages]]` ({`id`, `name`,
`cmd`, `advisory`, `timeout`, `about`}).

## 10.2 Commands

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
| `edakit schematic draw [--board] [--out F] [--force]` | – | graph, parts, `[schematic.layout]` if there | `schematic_<board>.svg` (or F) |
| `edakit pcb dump [--ref]` | ✓ | PCB | `pcb_geometry_<board>.json` (parts end at 0°/TOP) |
| `edakit pcb plan` | – | plan, geometry, net currents, graph (`layout`, L-12) | `pcb_plan_<board>.png/.json`, `pcb_netclasses_<board>.json` |
| `edakit pcb parts [--write]` | ✓ | board schematic, PCB, graph | PCB parts, UniqueIds, geometry |
| `edakit pcb nets [--write]` | ✓ | graph, PCB | pad nets |
| `edakit pcb apply [--verify-all]` | ✓ | plan, geometry | outline, holes, tooling, fixed parts |
| `edakit pcb autolayout` | ✓ | – | positions of unlocked parts |
| `edakit pcb tooling` / `pour` | ✓ | plan | tooling holes / pours (unfilled) |
| `edakit route all\|read\|dsn\|route\|check\|apply\|verify [--cleanup]\|pours\|reload\|drc\|save` | ✓ / – (dsn, route, check offline) | PCB, rules | `route/<board>_board.json`, `.dsn`, `.ses`, `_routing.png`, `_drc.json`; tracks, vias, pours |
| `edakit silk apply\|check` | ✓ | PCB, Gerber export | designators, `silk_<board>_<side>.png`, `gerber_<board>/` |
| `edakit export [--board]` | ✓ read | schematic, PCB, project file | `<artifacts>/export/` |
| `edakit gate [--easyeda]` | – / ✓ | everything | `<reports>/<run>/` |
| `edakit fab --board B --out DIR [--offline]` | ✓ / – | PCB, exports | `DIR/<board>/` |
| `edakit lock [status\|claim\|release\|yield CHAT\|hook] [--note]` | – | – | `~/.local/state/edakit/easyeda-lock.json` |
| `edakit proposal template [--feature]\|seal FILE [--out F]\|verify FILE` | – | a rule or feature proposal (no project needed) | seal: the issue body with its SHA-256 |
| `edakit doctor` | – | tool chain | – |

## 10.3 Files in a project

```text
edakit.toml                 project configuration
hardware/graph.json         the hardware graph (only source of parts and connections)
hardware/parts/C*.json      parts database
hardware/sim.json           simulation scenarios
hardware/signoff.json       manual checks and accepted warnings, bound to hashes
docs/decisions.md           numbered decisions (or wherever the project keeps them)
build/edakit/               artifacts (not versioned): caches, geometry, previews, routing, exports
build/release/<run>/        gate runs (archive the released one)
```
