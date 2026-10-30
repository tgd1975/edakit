# 10 Reference: edakit.toml, the project files and the commands

## 10.1 edakit.toml

Lookup: `--config PATH`, `$EDAKIT_CONFIG`, then `edakit.toml` in the current directory or a parent. Relative paths
are relative to it. edakit.toml is the table of contents: what the project is, which boards it has, where their files
are. What one role decides lives in a file of its own, with one owner and one hash (8.2):

| File | Content | Written by | Hash |
|---|---|---|---|
| `edakit.toml` | project, boards with their EasyEDA documents, where the files are, release settings, the project's scripts and agents | new-project, the user | – |
| `hardware/requirements.toml` | what the circuit must do: needs and requirements with their evidence (3.6, 10.4), with `[project] requirements` | the skill requirements drafts, only the user accepts | circuit |
| `hardware/graph.json` | the circuit with its purpose, the hand-over to the layout, the ground net and the check settings (3.1) | circuit designer | circuit |
| `hardware/parts/`, `hardware/sim.json` | parts database (4), simulation scenarios (5) | part-selector, circuit designer | circuit |
| `hardware/schematic.toml` | arrangement of the schematic: blocks, notes, pin table (10.3) | circuit designer | – |
| `hardware/boards/<name>.toml` | one board: outline, holes, placement, routing, pours, silkscreen (10.2) | PCB designer | layout |
| `hardware/boards/<name>.geometry.json` | the footprint geometry of the board's parts as placed in the PCB: boxes, pads, holes (7.4) – beside the board file, with its name | `edakit pcb dump` | layout |
| the SVGs of `[[silk.art]]` | artwork on the silkscreen (7.7), drawn by hand or by a project script | PCB designer | layout |
| `hardware/signoff.json` | sign-offs and accepted warnings, each bound to the hash of its scope: circuit, layout or fab (8.2); an accepted warning with `parts` {designator: LCSC} also to those parts; `rehashed` records a change of the hash method (the gate writes it for `hash_ignore`) | reviewers, the user | – |
| `hardware/firmware.json` | the firmware contract, with `[firmware]` (3.5) | `edakit firmware` | – |
| `hardware/scripts.lock` | the stamps of the project scripts: per script its `cmd`, the script itself and the hashes of what it reads, at its last run; after an `easyeda` script ran through `edakit run`, what it changed and what is from before it (8.6) | `edakit run`, `edakit scripts stamp`, the steps that run an input first; `pcb dump` and `route all` take off what they made again | – |

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
| `agreements` | `true` | the working agreements of handbook 11.4, one line each, in the context of every Claude Code session in the project (plugin hook at session start); `false` turns them off – not the lines of the project's scripts and agents the hook adds after them (11.4) |
| `graph` | `hardware/graph.json` | the hardware graph |
| `parts` | `hardware/parts` | parts database, one JSON per part (LCSC number or manufacturer part number) |
| `sim` | `hardware/sim.json` | simulation config (chapter 5) |
| `sim_plugin` | – | optional Python file with `MODELS` and `checks` (5.1) |
| `schematic` | `hardware/schematic.toml` | the schematic file (10.3) |
| `signoff` | `hardware/signoff.json` | the sign-off file (8.2) |
| `requirements` | – | the requirements file (3.6, 10.4), e.g. `"hardware/requirements.toml"`; a variant names the main project's file and its own, `["../../hardware/requirements.toml", "hardware/requirements.toml"]`. With it `edakit req` lists the file, `edakit check` checks it (G-20 to G-23), the gate evaluates every requirement (8.7) and the circuit hash covers it. A file named here must exist and be valid, else `edakit req`, `edakit check` and the gate stop. Without the key no file is read and nothing changes |
| `artifacts` | `build/edakit` | caches, previews, routing files, exports, Gerber exports (not versioned) |
| `reports` | `build/release` | gate runs |
| `datasheets` | `<artifacts>/datasheets` | the datasheets `edakit part fetch` keeps, `<key>.pdf` and `<key>.json` (4.6); a folder in the repository versions them |
| `stock` | `hardware/stock.json` | the stock snapshot of `edakit stock` (P-4, 4.2); versioned, outside the circuit hash |
| `stock_margin_pct` | `0` | P-4 warns when the assembler's stock is below the need plus this margin |
| `stock_max_age_days` | `14` | an older snapshot (or snapshot row) is pending in P-4 – it blocks the release, not `edakit check` |
| `spare_pct` | `0` | `edakit order`: spares on every cart line, in % of `quantity` sets (rounded up) |
| `toolchain` | `easyeda` | the EDA tool the boards are drawn in: `easyeda` (EasyEDA Pro through the bridge) or `kicad` (KiCad 10: edakit writes one KiCad project per board into `<artifacts>/kicad/<board>/` and calls kicad-cli, chapter 16). With `kicad` the EasyEDA document names of `[boards.<name>]` are refused |

The name of the ground net is in the graph (`ground`, default `GND`), with the circuit it belongs to; nets that are
ground on purpose besides it (an analog ground) in `grounds` (3.1, G-16).

### [boards.&lt;name&gt;]

| Key | Default | Meaning |
|---|---|---|
| `title` | the board name | page name of the board schematic |
| `template` | `generated_<name>` | schematic generated from the graph (EasyEDA only) |
| `schematic` | `layout_<name>` | board schematic, the PCB is linked to it (EasyEDA only) |
| `pcb` | `<name>` | PCB document in EasyEDA (EasyEDA only – a KiCad board is `<artifacts>/kicad/<name>/`, 16.3) |
| `file` | `hardware/boards/<name>.toml` | the board file (10.2); while it does not exist the board has no layout yet – a file named here must exist |
| `bought` | `false` | `true`: a bought board on a cable (4.5) – in the graph, checks and simulation like any board, made by nobody: no `template`, `schematic`, `pcb`, `file` or board file (each an error); stages S and L/F, the manifest, the `fab` and the layout hash leave it out, layout commands refuse it with `--board` and skip it without, `edakit order` writes no BOM and `edakit cost` no PCB or assembly for it |

### [release]

`layout_files` (further files in the layout hash – the board files, their artwork and the footprint geometry are always
in it),
`state_files` (further files in the circuit hash), `hash_ignore` (`[]`: keys left out of the circuit hash at any depth
of the graph and the parts entries, e.g. `["notes", "sources", "description", "verified", "datasheet"]` – only keys no
check and no review reads; empty: the bytes are hashed, 8.2), `assembly` ({`sides` (both), `smd_only`, `paste_gap_mm`
(0.4: SMD pads of different parts on an assembled side, L-14), `pcba` (`"economic"` or `"standard"`: the assembler's
class of the order, P-4; default from `sides` – one side Economic, two Standard)}), `[[stages]]` ({`id`, `name`, `cmd`,
`advisory`, `timeout`, `about`}: project checks of phase export before S, 8.1).

### [cost]

Optional: the order estimate of `edakit cost` (8.4). Without the table the gate and every command are as before; with
it the gate has an information row "estimated order cost" in stage P, and above `budget` a warning to accept.

| Key | Default | Meaning |
|---|---|---|
| `fees` | `hardware/fees/<maker>.json` over the shipped `edakit/fees/jlcpcb.json` | the project's own fee table in the same form (every value with `date` and `source`; `pcb.board` the board its PCB prices are for – thickness, mask, silkscreen, finish –, without it the defaults of `[order]`): per fee the value with the newest date wins, from this table or the shipped one of the planned maker; `edakit cart actual` writes the real costs of the project's orders into it (8.4) |
| `budget` | – | the most the whole order may cost, in `currency`; above it `edakit cost` exits 2 and the gate warns |
| `currency` | `"USD"` | the currency of the estimate |
| `rates` | `{}` | the value of one unit of another currency in `currency`, e.g. `{ EUR = 1.15 }`; needed for the fee table's USD and for every `[[extra]]` in another currency |
| `shipping`, `coupon` | `0` | per order, in `currency` |
| `vat_pct` | `0` | import VAT on the assembler's order (boards + shipping − coupon) |
| `pcb_price` | the board line of a checked quote of the current release, else the fee table | the quoted price of the PCBs (all `quantity` of them) – a number, or `{ board = price }`; wins over the quote |

### [order]

The project's choice of order keys for every board – the keys of `[order]` of a board file (10.2) but the board's own
(`tab_zones`, `size_mm`, `layers`), e.g. `[order] mask = "black"` for all boards. A board file's `[order]` wins per
key. With the table every made board has an order form: `fab/<board>/order.md`, `order.json` and F-6.

### [cart]

Optional: the makers of the boards (8.4). Without the table the maker is JLCPCB, the makers are `["jlcpcb"]`, and
every check runs as before.

| Key | Default | Meaning |
|---|---|---|
| `maker` | `"jlcpcb"` | the maker the boards are planned for: its checks fail (P-4, F-2, F-6, P-12, F-7), its form is `order.md`, `[release] assembly.pcba` is one of its classes, `edakit cost` prices with its fee table |
| `makers` | `[maker]` | every maker whose checks and files the gate runs and writes; a finding for a maker other than `maker` is a warning, and `edakit cart prepare` for that maker stops on it |
| `ship_to` | – | the country the order goes to, as the form names it; `edakit cart prepare` needs it |
| `shipping` | `{}` | per maker, the name of its shipping method: `{ jlcpcb = "DHL Express" }` |
| `tolerance` | `0.10` | per price line, in the maker's currency, before B-3 warns |
| `profiles` | `{}` | a project's own maker profiles, `{ name = "hardware/makers/name.toml" }`, beside the shipped ones (`jlcpcb`, `pcbway`, `eurocircuits`, `aisler` in `edakit/makers/`) |

A maker's profile holds no defaults of the board: its form's labels and words for edakit's keys (`fields`), the
values it offers, its limits (`rules`: thicknesses, remark, placeholder, tooling holes per class), the files it takes,
its assembly `classes`, whose parts catalogue P-4 and F-2 ask (`catalogue`), the one cart button the skill cart may
press and the ones it must not touch, its seat and currency, its fee table. `recorded = false` marks a profile whose
words are not yet read off the form (ordering step 0); F-6 names it as information. No credentials anywhere: the
owner is logged in in their browser, edakit never sees an account.

### [[extra]]

Items off the board that belong to the order – a cable, feet, a module that is plugged in: `item`, `supplier`,
`per_set` (pieces per board set) – these three are required –, `code` (the supplier's order code), `spare` (pieces on
top), `moq` (the supplier's minimum), `step` (its pack size), `unit_price` and its `currency` (default
`[cost] currency`). `edakit order` puts each into the cart of its supplier, `edakit cost` prices the cart quantity:
ceil(`per_set` × `quantity` × (1 + `spare_pct`/100)) + `spare`, at least `moq`, a multiple of `step`.

### [firmware]

Opt-in: the board's firmware contract (3.5). Without the table `edakit firmware` exits 1 and nothing else changes.

| Key | Default | Meaning |
|---|---|---|
| `mcu` | the one part with pins of the role `gpio` | the MCU the contract describes |
| `out` | `hardware/firmware.json` | where `edakit firmware` writes it, relative to edakit.toml |
| `gpio` | `"(\\d+)"` | regex over the MCU pin's name, its first group is the GPIO number (`GP26_ADC0` → 26); no match: `null` |

### [docs]

Values quoted from the design data (6.6). Without the table no document is read; placeholders in the schematic notes
work without it.

| Key | Default | Meaning |
|---|---|---|
| `files` | `[]` | Markdown files with value blocks `<!--edakit SOURCE [FORMAT]-->value<!--/edakit-->`, relative to edakit.toml |
| `decimal` | `"."` | `","` writes quoted numbers with a decimal comma |

### [scripts.&lt;name&gt;]

Optional: a project script that touches edakit's flow – it writes a file edakit reads, derives something from
edakit's data, changes the project library in EasyEDA, or is a check of its own (8.6). `edakit check` and the gate
resolve the entries with edakit's steps into one order, report what keeps them from it, and compare each script's
stamp in `hardware/scripts.lock`: an input outdated or never run is an error, a derive or easyeda script a warning.
`edakit scripts` lists them. `edakit run` runs input, derive and easyeda scripts – an easyeda script only so, under the
EasyEDA claim – and records each run; the steps that read what an input writes run it first when it is outdated
(`--no-scripts`: none); `edakit scripts stamp` records a run made by hand. The gate runs the checks (8.1). Without the
table nothing changes.

| Key | For | Meaning |
|---|---|---|
| `kind` | every entry | `input`, `derive`, `easyeda` or `check` (8.6); the kind `sim` is `[project] sim_plugin` |
| `cmd` | every entry | the command as a list, run in the project directory – `python` or `python3` as its first word is edakit's own interpreter, where edakit runs the entry (8.6); a check gets `EDAKIT_RUN`, the gate run's folder (8.1) |
| `about` | every entry | one sentence why the script exists, citing a decision |
| `writes` | input, derive, easyeda (required) | what it makes: paths; an input also `board:<b>`; an easyeda script changes `project-library:<b>` (not `footprints:<b>`, the geometry `pcb dump` measures); `<b>` a made board |
| `reads` | every kind (optional) | what its result is made from: edakit's data (8.6, each with a hash; the project library has none), files and folders – the script itself, the first file `cmd` names, counts anyway |
| `after` | every kind (optional) | other entries of `[scripts]` this one runs after – needed when several write the same file or change the same data |
| `check` | input, derive, easyeda (optional) | an exact check command, when the stamp is not enough (not run yet) |
| `id` | check (required) | its ID in the protocol: no stage of the gate (P, G, E, S, L, F), no sign-off (M-…), no ID of the rule catalog, and none twice – `[[release.stages]]` included |
| `phase` | check (required) | `export`: a stage of the gate, its failure holds up the release; `order`: a line of the protocol's list after uploading, before paying, which M-2 works through; `acceptance`: a line of the acceptance list after delivery, which M-4 works through – neither of the two runs in the gate (8.1, 8.5) |
| `at` | check (optional) | phase `export` only: `"before S"` (default) – between E and S, where `[[release.stages]]` run – or `"after F"`: after stage F, only in `edakit gate --easyeda`, to read the run's manufacturing files (`gerber:<b>`, in `fab/<b>/` of `$EDAKIT_RUN`) |
| `advisory` | check (optional) | `true`: a failure is an advisory finding – listed in section 2 of the protocol, it does not hold up the release |

A field of another kind is a finding of `edakit check`, a key no kind has an error of edakit.toml.

### [agents.&lt;name&gt;]

Optional: an agent of the project – it signs a sign-off of its own, or takes over one of edakit's reviews (8.6).
`edakit check` and the gate check the entries (ID `agents`), the gate requires their sign-offs – each counts only when
`done_by` names its agent (8.2) –, and `edakit scripts` shows who reviews where, for the skills that start the agents.
Without the table nothing changes.

| Key | For | Meaning |
|---|---|---|
| `file` | every agent | the agent file, relative to edakit.toml, e.g. `.claude/agents/pcb-pruefer.md`: it exists, and the `name` in its front matter is the entry's name – the skills start the agent by it |
| `about` | every agent | one sentence what the agent checks |
| `signs` | every agent | the sign-off its OK is: an ID of its own, `M-<number>` (`M-7`), or edakit's review it takes over – `M-1`, `M-5`, `M-6` – with `replaces`; never the owner's `M-2` or `M-4`; one agent per sign-off |
| `replaces` | with `M-1`, `M-5`, `M-6` | the edakit agent it takes the place of, at each of its hook points: `electrical-reviewer` (M-1), `pcb-reviewer` (M-5 – the round reviews too), `regulatory-reviewer` (M-6) |
| `scope` | with an ID of its own | `circuit`, `layout` or `fab`: the hash its sign-off is bound to (8.2), and where it reviews – the circuit review before the layout, the round review after a layout round, the layout review between the two gate runs (8.6). edakit's review keeps the scope of the sign-off file |
| `phase` | every agent | `export`: the release waits for its sign-off; `acceptance`: a line of the acceptance list after delivery (8.5), whatever its scope. edakit's review: `export` |
| `after` | every agent (optional) | other entries of `[agents]` this one reviews after, at a hook point both review at; not one that reviews only later |

A key no agent has is an error of edakit.toml; what an entry signs and where it reviews is checked by `edakit check`.

## 10.2 The board file

`hardware/boards/<name>.toml`: what the PCB designer decides (14.1). The layout hash covers it, the SVGs its
`[[silk.art]]` places and the footprint geometry beside it (`<name>.geometry.json`, written by `pcb dump`, 7.4) – a
change voids the sign-offs with scope `layout`; the layout review M-5 with scope `fab` (8.2) lapses when the
manufacturing files change, or the settings of `[order]` that change the board as made: thickness, colours, finish,
mark. The keys stand at the top of the file, without a prefix (`[place]`, `[[holes]]`):

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
| `place` | `{}` | `REF = {x, y, rot, side, lock, auto}` every part of the board (L-20); `auto = true` marks a spot nobody designed, a row `pcb place` or `pcb autolayout` wrote – a later `pcb place` may move it, every other command treats it as any row (7.4) |
| `near` | `{}` | `PART = "HOST"` or a list – the layout's own, between fixed parts; the circuit's are `layout.near` of the graph |
| `uniform` | `{ led = "row" }` | polarised parts that point the same way, per `kind` of the parts entry: `"row"` – parts of the kind side by side on one line (centres within 1 mm) have their plus pin towards the same side; `"+x"`, `"-x"`, `"+y"`, `"-y"` – the cathode or minus pin of every part of the kind points that way, seen from the side the part sits on. A part counts with exactly one pin `anode` or `plus…` and one `cathode` or `minus…`; the table names every kind it checks – without `led` the LEDs are not compared (7.4) |
| `routing` | see below | Freerouting rules |
| `[[pours]]` | GND on both layers | `net`, `layers`, `plane` (bool), `fanout` (false: with `plane`, every SMD pad of the net on the other layer gets a protected via to the plane and a stub, 7.5), `stitch` (layer), `priority`, `line_mil`, `pour_only` (false: the net gets no tracks, its pour connects it; on every entry of the net, not with `plane`), `clearance_mm` (0.25: what the computed pour keeps from foreign copper – the EasyEDA copper-area rule), `min_width_mm` (0.25: the narrowest neck it fills); both also for every pour on a shared layer with `pour_regions` |
| `pour_regions` | `false` | nets that share a pour layer get outlines of their own area, claimed in `priority` order (7.6); no `plane` on such a layer |
| `pour_min_piece_mm2` | `2.0` | with `pour_regions`: the smallest piece (outside the net's own copper and clearance) that gets an outline |
| `pour_inset_mm` | edge clearance + 0.1 | how far the pours lie inside the outline (mm): the outline of `pcb pour` and `route pours` and every computed pour; without it `routing.edge_clearance_um` / 1000 + 0.1; the tracks keep `edge_clearance_um` either way (7.6) |
| `silk` | `{}` | `designators` (side), `hide` (sides), `label_h_mm` (1.0), `gap_mm` (0.25), `groups` {label: [refs]}, `unlabelled` ({designator = reason}, none: a part of the `designators` side without a visible designator or group label is an L-17 warning), `priority` (["TP"]), `solder_side` (`false`; `true`: the through-hole parts of the other side are labelled on the `designators` side too, 7.7), `place` (`{}`; `REF = {x, y, rot, side}`: a designator at a fixed spot, as `[place]` fixes a part – plan mm, the rotation EasyEDA gets, the side it prints on (the `designators` side); the rest is placed around it, and one on a pad, beyond the board or on a text is a finding, 7.7), `board_label` (`"{title} rev {revision}"`; also `{project}`, `{board}`; `""` = none), `board_label_corner` (`bottom-left`, seen from the printed side), `board_label_h_mm` (1.2), `board_label_side` (the `designators` side; `"top"` or `"bottom"`, 7.7), `board_label_region` (the whole board; a polygon `[[x, y], …]` in plan mm the label must lie in, `board_label_corner` then means its corner, 7.7), `[[art]]` ({`svg`, `x`, `y`, `width_mm`, `rot`, `side`}), `[[texts]]` ({`text`, `x`, `y`, `h_mm` (1.2), `rot`, `side`, `font` (`default` = stroke font, or a font family EasyEDA knows)}) |
| `[looks]` | – | the side people look at: `visible` (`"top"` or `"bottom"`, required in the table), `max_track_m` and `max_vias` (optional limits). `route check` prints the track length per side and the vias, and the visible side's row; stage L gives the row too; above a limit a warning (7.5, 8.1); stage L checks the side's print against the board file (L-19: the board label, `[[silk.texts]]` of the side and, with `[silk] designators` on it, designators and group labels; no designator shown there while `designators` is the other side, 7.7). Without the table nothing is reported |
| `[[loops]]` | `[]` | `a`, `b` (pads "D1.2"), `max_mm`, `what` – check L-11; the circuit's are `layout.loops` of the graph |
| `copper` | see below | copper per layer in the Gerber files, check L-15 |
| `order` | – | every field of the maker's order form as a key (below, 8.4), over `[order]` of edakit.toml; with the table – or with `[cart]` – the gate writes `fab/<board>/order.md` and runs F-6 |
| `thickness_mm` | `1.6` | board thickness (mm); the mechanical model `mech_<board>.json` takes the lead protrusion from it (lead `length_mm` − `thickness_mm`, 7.4), and with `order` the order form and the fab hash (8.2) – F-6 fails a thickness the maker's form does not have (JLCPCB, FR-4, 2 layers: 0.4, 0.6, 0.8, 1.0, 1.2, 1.6, 2.0) |
| `net_classes` | see below | track widths from the simulated currents |

`[routing]`: `clearance_mil` (6.5; also the least gap between pads of different parts, L-13), `signal_mil` (10), `via` ([24, 12]), `edge_clearance_um` (400: tracks and vias
from the outline, in the DSN and in Freerouting; the pours: `pour_inset_mm`), `passes` (40),
`attempts` (5), `layer_cost` ({TOP = [1.0, 1.8], BOTTOM = [1.5, 2.5]}), `classes` ({NAME = {width_mil, nets}}),
`widths` (`"classes"`: the DSN takes the widths of `classes` and `signal_mil`; `"sim"`: every class at least the
IPC-2221 width of its nets' simulated currents, a net outside the classes that needs more than `signal_mil` a class of
its own – needs `net_currents.json`, 7.5), `hand_solder_keep_mm` (0 = off: L-18, vias and pads of other nets at
least this far, in mm, from the through-hole pads of `bom: false` parts on their solder side; `route dsn` writes via
keep-outs around them, 7.5), `drc_rules` (none: L-3 as before; `"check"`: the gate reads the rule set of EasyEDA's DRC
with the DRC and L-3 holds it to these rules – clearance, edge clearance, track widths, via, classes, 7.5),
`[[routing.keepouts]]` ({layer, what = "wire"|"all", rect | polygon, windows, window_mm}), `[[routing.fixed_wires]]`
({net, layer, width_mil, points}).

`[copper]`: `max_bare_mm` (5: the largest copper-free circle inside the pour outline of a layer that `[[pours]]` pours;
above it L-15 warns), `min_cover` (`{TOP = %, BOTTOM = %}`, none: the least copper share of the board area per layer;
below it L-15 warns).

`[net_classes]`: `NAME = {min_a, width_mm}` – class by the largest simulated current, practical minimum width (default
POWER ≥ 0.3 A 0.6 mm, SUPPLY ≥ 0.1 A 0.4 mm, SIGNAL 0.25 mm). `force = {NET = "CLASS"}` pins a net to a class (e.g. a
switching node).

`[order]`: every question a maker's order form asks, as a key in edakit's words with edakit's default – the board
edakit assumes when nothing is said, the same for every maker (8.4). Three layers, the later one wins per key: these
defaults, `[order]` of edakit.toml (every board, 10.1), `[order]` of the board file. The maker's profile only
translates a value into its word (`edakit/makers/<maker>.toml`, `edakit cart fields`); a value the maker does not
offer is a finding of F-6 for that maker. "Board": the key changes the board as made – `fab/<board>/order.json` has
`thickness_mm`, `mask`, `silkscreen`, `finish` and `mark` whenever the board has `[order]`, and every other such key
where its value differs from the default; so a project that sets none of them keeps its fab hash (8.2).

| Key | Default | Values | Board |
|---|---|---|---|
| `material`, `tg` | `"FR-4"`, `"TG135"` | strings, the maker's words in its profile | ✓ |
| `layers`, `size_mm` | – (derived) | only to check: the copper layers and `[w, h]` of the run's Gerber files (F-6, ± 0.1 mm) | – |
| `quantity` | `[project] quantity` | PCBs ordered, a whole number | – |
| `delivery` | `"single"` | `"single"`, `"panel_by_maker"` with `panel = {x, y, rails_mm}`; `"panel_by_customer"` fails F-6 (edakit draws no panel) | ✓ |
| `mask`, `silkscreen` | `"green"`, the print on the mask (`"white"`, on a white mask `"black"`) | mask `"green"`, `"purple"`, `"red"`, `"yellow"`, `"blue"`, `"white"`, `"black"`; silkscreen `"white"`, `"black"` – F-6 fails a pair the maker does not print | ✓ |
| `finish` | `"LeadFree HASL"` | the maker's words (JLCPCB: `"HASL(with lead)"`, `"LeadFree HASL"`, `"ENIG"`) | ✓ |
| `copper_oz`, `inner_copper_oz` | `1`, `0.5` (inner: from 4 layers) | oz | ✓ |
| `vias` | `"tented"` | `"untented"`, `"plugged"`, `"epoxy_filled"` | ✓ |
| `outline_tolerance` | `"regular"` | `"precision"` | ✓ |
| `gold_fingers`, `castellated`, `edge_plating` | `false` | true or false | ✓ |
| `mark` | `"default"` | `"specify"`: at the maker's placeholder (JLCPCB: `JLCJLCJLCJLC`, PCBWay: `WayWayWay`), `"remove"` – the maker's order number; JLCPCB reports its own gone since May 2026, and F-6 warns about the placeholder | ✓ |
| `barcode`, `serial_number` | `"none"`, `false` | `"qr"`, `"datamatrix"`; true or false – for traceability, printed by the maker where there is room (JLCPCB since May 2026) | ✓ |
| `electrical_test`, `quality` | `"flying_probe"`, `"ipc2"` | the maker's words | – |
| `confirm_production_file`, `paper_between` | `false` | true or false | – |
| `packaging` | `"standard"` | the maker's words | – |
| `remark` | `""` | text to the maker (JLCPCB: at most 200 ASCII characters) | – |
| `tab_zones`, `tab_copper_mm` | `[]`, `1.0` | `{from = [x, y], to = [x, y]}`, two points on the outline in plan mm – the shorter stretch between them; no copper of either side within `tab_copper_mm` of it (F-6). Board file only | – |
| `pcba_quantity` | `quantity` | boards assembled, at most `quantity`; another number than `[project] quantity` warns (P-4 and F-2 count that many sets) | – |
| `confirm_placement` | `true` | edakit's choice: the maker shows its placement before it builds, a second look beside M-2 | – |
| `photo_confirmation`, `depanel`, `function_test` | `false` | true or false | – |
| `conformal_coating` | `false` | true or false | ✓ |
| `pcba_packaging` | `"antistatic_bag"` | the maker's words | – |

Not keys of `[order]`, but fields of the form all the same: the thickness (`thickness_mm` of the board file), the
assembly class and side (`[release] assembly`, the class one of the maker's `classes`), the tooling holes
(`[tooling]`: by the customer, else by the maker), bake (the stock snapshot, MSL ≥ 5), the parts not to place
(`bom: false`), the country and shipping method (`[cart]`). `edakit cart fields` prints them all with their source.

## 10.3 The schematic file

`hardware/schematic.toml`: `stub` (10): stub length of the template. `[layout]`: `rows` (rows → columns → blocks
`{title, start}`), `power_flags` ({NET = "Ground"|"Power"}), `near` ({CAP = "PART"}), `stacked` (blocks whose trees
stand one below the other), `[layout.notes]` ({block title = [lines]}), `[layout.pin_table]` (`component`, `block`,
`prefix`, `notes` {NET = "function"}). A note may quote the design data: `{graph:R1.value}`,
`{part:C90107.params.vrext_v}`, `{sim:max E-3 * D2 LED current*}`, optionally with a format, a requirement's text
`{req:R-1}` (6.6). It changes no hash – the drawing explains the circuit, it is not the circuit. Without the file
`edakit schematic draw` arranges the schematic by itself (6.5).

## 10.4 The requirements file

`hardware/requirements.toml`, named in `[project] requirements`: what the circuit must do (3.6) – only the circuit,
what firmware and mechanics must do stays in the project's own documents. `edakit req` lists it, `edakit check`
checks it (G-20 to G-23, 3.3), the gate evaluates every requirement's evidence (8.7), and the circuit hash covers it
byte for byte (8.2). A key edakit does not know is an error, as in edakit.toml. From the example of the tests
([tests/test_requirements.py](../tests/test_requirements.py), for the circuit of led-bar):

```toml
[[need]]
id = "N-1"
text = "The bar runs from a USB charger or from the USB port of a laptop."
who = "whoever uses the bar"
source = "README.md, sim.json J1"
status = "accepted"

[[requirement]]
id = "R-1"
text = "With all eight LEDs on, the board draws at most 500 mA from J1 at 4.75 to 5.25 V."
source = "sim.json: the note of source J1"
from = ["N-1", "USB 2.0: 500 mA per port"]
binding = "must"
verify = [{ rows = "E-3 * J1 current from the supply" },
          { accept = "on the USB port of a laptop: all eight LEDs on, the port stays on" }]
status = "accepted"
```

| Key | In | Meaning |
|---|---|---|
| `id` | both, required | `N-<n>` in a `[[need]]`, `R-<n>` in a `[[requirement]]`, without a leading zero; unique across the files of the project, a variant's own included; stable – a dropped entry keeps its number |
| `text` | both, required | a need in the words of those who want it; a requirement as one testable sentence: quantity with unit, limit, condition |
| `who` | need | who wants it |
| `source` | both | where it was found: a document, a decision; on a requirement next to `from`, which says where it comes from |
| `from` | requirement | a list of where it comes from: needs (`N-2`), decisions (`D-8`), a standard (`USB 2.0: 500 mA`), a sign-off (`M-6`) |
| `binding` | requirement, required | `must`, `should` or `may` |
| `verify` | requirement | a list of what tests it, one kind per entry: `{ rows = "…" }` rows of the gate protocol, a pattern over "ID scenario item check" as `accepted_warnings` match them (8.2); `{ signoff = "M-1" }` a manual check, which counts when its `note` names the requirement's ID; `{ script = "…" }` a project script of kind `check` or the id of a `[[release.stages]]` – it passes when the check passed in the gate's run, one of phase `order` or `acceptance` once M-2 or M-4 is signed; `{ accept = "…" }` a step of the acceptance test, on the list of protocol section 6. `edakit req` shows it as written, the gate evaluates it (8.7) |
| `status` | both | `draft` (written, not approved – also an entry without `status`), `accepted` (only the user sets it), `dropped`; a value that is written must be one of the three. A draft binds nothing yet: G-20 to G-23 only warn about it, the gate lists it and neither blocks nor asks for an acceptance (8.7); from `accepted` on, the findings are errors and the binding counts |
| `reason` | both | why; required with `dropped` |

A variant – a project of its own with its own edakit.toml in a folder below the main project – names the main
project's file and its own: `requirements = ["../../hardware/requirements.toml", "hardware/requirements.toml"]`.
`edakit req` lists both, in that order; an ID stands in only one of them.

## 10.5 Commands

All commands: `--config`, `-v` (MCP traffic). Exit codes: 0 ok, 2 findings, 1 error; 3 from `edakit lock` and from
`edakit run` of an easyeda script (another session holds EasyEDA) and from `route all|drc` and `silk apply|check` when
the DRC's only item is EasyEDA waiting for the import acknowledgement (schematic = PCB; *Design → Import Changes* once
– 7.5). With uv from snap inside Claude Code: `edakit … 2>&1 | cat`. The long commands – `route all`, `gate`,
`pcb apply`, `silk apply`, `export`, `schematic create|layout` – print `[x.x min] step n/m: <step>` before each step
(11.3). With `[scripts]`, `pcb place|parts|plan|apply`, `route all`, `silk apply|preview` and `gate` run the input
scripts that write what they read first, when those are outdated or never ran, and stop when one fails;
`--no-scripts` runs none (8.6).

| Command | EasyEDA | Reads | Writes |
|---|---|---|---|
| `edakit cart fields [--board B] [--maker M]` | – | `[order]` of edakit.toml and the board file, `thickness_mm`, `[release] assembly`, `[tooling]`, the stock snapshot, `[cart]`, the maker's profile; the Gerber files of the current release (else the newest run) for layers and size | – (prints every field of the maker's form: its label, the maker's word, where it comes from, edakit's key and value) |
| `edakit cart prepare [--board B] [--maker M]` | – | the current release (manifest, `makers.json`, the board's upload files and `order.json`), the circuit and layout hash now, the sign-off file (M-6), `[cart]`, the maker's profile, the estimate | `<reports>/<run>/fab/<board>/cart/<maker>/job.json`; exit 1 with the reason when the order cannot be placed against the release (8.4) |
| `edakit cart check [--board B] [--maker M] [--cart]` | – | `job.json`, `quote.json`, `quote_page.txt`, `regulatory.md`, with `--cart` `cart.json` of the order's folder; the manifest | `check.md`, `check.json`; with `--cart` and every check passed the order record `hardware/orders/<date>-<board>-<maker>.json`. Exit 0 passed, 2 a finding (B-1 to B-7), 3 B-1 to B-6 passed and the review of the order (B-7) is open |
| `edakit cart actual [--board B] [--maker M] [--from FILE]` | – | `job.json`, `quote.json`, `actual.json` and `actual_page.txt` of the order's folder – with `--from` a saved order page or invoice (HTML; PDF with pdftotext) whose text edakit reads itself; `[cost]`, the fee table | `actual.md`; the project's fee table (`[cost] fees`, else `hardware/fees/<maker>.json`) with what maps one to one; the order number and the totals in the order record. Exit 2 when B-4 fails – nothing written |
| `edakit check [--release] [--json F]` | – | graph, parts (pins, identity P-6), pin table; if there: footprint geometry and library footprints (P-7, P-8), library symbols (P-1), the footprint data of parts entries with the footprint geometry (P-9, P-10); `[scripts]`, `[[release.stages]]` and `sim_plugin` with the board files' `[[silk.art]]`, `hardware/scripts.lock` and what the scripts read (8.6); `[agents]` and the agent files (8.6); with `[project] requirements` the requirements files and the sign-off file's manual checks (G-20 to G-23; a file missing or not valid: exit 1) | – |
| `edakit rules [ID …]` | – | the rule catalog (no project needed) | – |
| `edakit hints [--json F]` | – | graph, parts, sim config | – |
| `edakit block list\|show NAME` | – | the block library (no project needed) | – |
| `edakit block add NAME --as I [--connect PORT=NET …] [--board B] [--file F] [--dry-run]` | – | graph, parts, block | graph (formatting kept), missing parts entries |
| `edakit part import LCSC [--update]` | – (internet) | EasyEDA's public component data of that number (4.2) | a new `hardware/parts/<LCSC>.json`, else nothing (`--update`: the fields it lacks); `<artifacts>/library/<LCSC>.json`, `<artifacts>/footprints/<footprint>.json`; exit 2 = the entry differs |
| `edakit part diff OLD NEW [--json F]` | – | geometry of both (the dump of a placed part, else the footprint data of the entry, else the library footprint of `part import`), their parts entries (roles, `lead`), graph | – (F: the comparison as JSON); exit 0 = drop-in, 2 = something to decide (7.3) |
| `edakit part footprint KEY [--board B] [--write]` | – | the footprint geometry of a placed part of KEY (`--board`: that board's), else the library footprint of `part import`; with the dump also the library footprint, for shapes and sizes (4.5) | – (prints the footprint as data); `--write`: `footprint_data` and a line of `sources` in the parts entry. Refused for an entry that has the data; exit 2 when P-9 finds something missing |
| `edakit part build KEY [--board B] [--write]` | – / ✓ with `--write` | the entry's `footprint_data`, `pins` and `symbol` (P-9 must pass), the graph (the parts of the board that use it); with `--write` the board's template in EasyEDA, where the carrier is placed (4.5) | – (prints what it would build); `--write`: the copy of the carrier in the project library – footprint, with `"symbol": "box"` symbol –, the project saved; with `[scripts]` the change of `project-library:<b>` in `hardware/scripts.lock` (8.6). Exit 2 when the copy read back differs from the data; not run against EasyEDA yet |
| `edakit part fetch KEY [--url U] \| --all` | – (internet) | the parts entry (`mpn`, `datasheet.url`, `lcsc`, `verified.datasheet_sha256`); the sources of 4.6 | `<datasheets>/<KEY>.pdf` and `.json` (a failed download keeps the earlier copy, exit 2; variant or changed since the sign-off: exit 2) |
| `edakit part search "KEYWORDS" [--basic] [--min-stock N] [--limit 25] [--json F]` | – (internet) | JLCPCB's public parts catalogue (4.2) | – (F: the hits); exit 2 = no hits |
| `edakit part datasheet [--connector C …] [--name N]` | – | graph, parts, sim config, board file (4.5) | `hardware/datasheet/<N>.json` and `.md`; without `--connector` every datasheet renewed |
| `edakit stock [--board B] [--refresh]` | – | graph, parts, the snapshot; JLCPCB's catalogue and part pages (network) – only with JLCPCB among `[cart] makers` (exit 1 otherwise) | `hardware/stock.json` (`[project] stock`): the parts missing, unread or older than `stock_max_age_days`, with `--refresh` all |
| `edakit stock --lcsc C…` | – | JLCPCB's catalogue and part pages (no project needed) | – (prints listed, class, stock, MSL, PCBA type, X-ray, attrition) |
| `edakit cost [--board B] [--json F]` | – | graph, parts, board files (outline, sides, `[order]`: `quantity` PCBs, `pcba_quantity` assembled), the stock snapshot, the fee table of the planned maker with the project's own over it (newest value per fee), the PCB price of a checked quote of the current release, `[cost]`, `[[extra]]` | `<artifacts>/cost.json` (the change since the last estimate is printed; `not_in_price` per board whose `[order]` differs from the fee table's board, 8.4); exit 2 above `budget`, exit 1 for a maker without a fee table |
| `edakit order [--out DIR]` | – | graph, parts (`order`), board files (side), `[[extra]]`, `spare_pct` | `<artifacts>/order/` or DIR: `bom_<board>.csv` (the F-1 BOM; none for a bought board), `cart_<supplier>.csv`, `hand_assembly.md` |
| `edakit part own PATH [--name N]` | – | the board's project at PATH: its datasheet, state, git, gate runs | `hardware/parts/<N>.json` |
| `edakit sim [--json F] [--keep DIR]` | – | graph, parts, sim config, plugin; with `copper` `route/<board>.ses`, `route/<board>_board.json` and the board file's pours | `<artifacts>/sim/net_currents.json`, `<artifacts>/sim/result.json` (the whole result with the hash of its inputs, 6.6); with `--keep` each netlist and ngspice log, for a transient run its waveforms (`<run>.dat`) |
| `edakit docs [--write]` | – | `[docs] files`, the schematic notes, graph, parts; for `sim:` the saved simulation result (or a new run); for `req:` the files of `[project] requirements` | with `--write` the value blocks of `[docs] files` |
| `edakit firmware [--check]` | – | graph, parts, `[firmware]`; for `state_sha256` the files of the circuit hash | `[firmware] out` (not with `--check`: exit 2 on drift) |
| `edakit req [ID …]` | – | the files of `[project] requirements` (10.4) | – (prints the needs and requirements with status, binding and `verify` as written – the gate evaluates it, 8.7; with IDs the chain of each, 3.6); exit 1 without the key, with a file missing or not valid, or an ID not in the files |
| `edakit scripts` | – | `[scripts]`, `[[release.stages]]`, `sim_plugin`, the board files' `[[silk.art]]`, `hardware/scripts.lock`, what the scripts read; `[agents]` and the agent files (8.6) | – (prints every script with kind, state – current, outdated, never run –, about, cmd and its last run; the order; with `[agents]` every agent with what it signs, and who reviews where – each hook point with its agents in the order to start them; exit 2 when a script is outdated or never ran or the entries of `[scripts]` or `[agents]` do not resolve, 1 when the lock cannot be read) |
| `edakit scripts stamp NAME …` | – | the same | `hardware/scripts.lock`: the stamp of each script named – it ran by hand; refused, writing nothing, for a check, entries that do not resolve, or a script whose `writes` are not there |
| `edakit run NAME …` | – (an easyeda script changes EasyEDA itself, under the claim) | the same | runs the scripts named in their order, in the project directory (`python` = edakit's), and records each run: its stamp; for an easyeda script also its change of `project-library:<b>` (8.6); `<artifacts>/scripts/<name>.log` per script. Refused for a check, a name not in `[scripts]`, entries that do not resolve; a failed script records nothing and stops the run; exit 2 when a script named is still outdated, 3 when another session holds EasyEDA |
| `edakit handover [--board B]` | – | graph, parts, sign-offs | – |
| `edakit schematic create [--board] [--only] [--dry-run] [--save] [--create-project] [--refresh-devices]` | ✓ | graph | template, `device_cache.json`, `schematic_map_<name>.json`; `--save` only when the netlist equals the graph (6.1) |
| `edakit schematic check [--schematic] [--no-pins] [--json F]` | ✓ read | graph, schematic | – |
| `edakit schematic copy [--source] [--target] [--save]` | ✓ | schematic | copy |
| `edakit schematic layout [--dry-run] [--reread] [--force] [--save]` | ✓ / – | graph, schematic, cached geometry | board schematic, `layout_preview_<name>.svg`; `--save` only when the netlist equals the graph (6.1) |
| `edakit schematic draw [--board] [--out F] [--force]` | – | graph, parts, the schematic file if there; for a `{sim:…}` note the saved simulation result | `schematic_<board>.svg` (or F) |
| `edakit pcb dump [--ref]` | ✓ | PCB; the parts entries (which have footprint data) | `hardware/boards/<board>.geometry.json`, beside the board file and versioned (parts end at 0°/TOP; through-hole pads with `hole` [w, l] mm and `plated`; the pads of a part whose entry has footprint data with `shape`, `w`, `h`, `rot`, `layer`); a `<artifacts>/pcb_geometry_<board>.json` from before is moved there (7.4) |
| `edakit pcb plan` | – | plan, geometry (the dump; for parts not in it the footprint data of their entry, else the library footprints of `part import`), net currents, graph (`layout`, L-12), parts entries (`body`, `lead` `length_mm`, `mate`) | `pcb_plan_<board>.png/.json`, `pcb_netclasses_<board>.json`, `mech_<board>.json` (7.4) |
| `edakit pcb place [--rest] [--write] [--only C1,R1]` | – | plan, geometry as `pcb plan` reads it, graph (`layout.near`, decoupling of L-12), `[near]`; with `--rest` also the graph's nets and `[release] assembly` sides | with `--write`: rows with `auto = true` at the end of `[place]` – with `--rest` for every part of the board without a row, or with an `auto` row: by airline length, then moves and swaps while it falls (7.4) |
| `edakit pcb parts [--write]` | ✓ | board schematic, PCB, graph | PCB parts, UniqueIds, geometry |
| `edakit pcb nets [--write]` | ✓ | graph, PCB | pad nets |
| `edakit pcb apply [--verify-all]` | ✓ | plan, geometry | outline, holes, tooling, fixed parts |
| `edakit pcb autolayout` | ✓ | graph, board file | positions of the unlocked parts; once they stand still, a row with `auto = true` at the end of `[place]` for every part of the board without one (7.4) |
| `edakit pcb takeover [--write]` | ✓ read | PCB, graph, board file | with `--write`: a fixed row at the end of `[place]` for every part of the board without one, where EasyEDA has it – once, for a board placed before (7.4) |
| `edakit pcb tooling` / `pour` | ✓ | plan; `pour` with `pour_regions`: board file and SES of `route` | tooling holes / pours (unfilled) |
| `edakit route all\|read\|dsn\|route\|check\|apply\|verify [--cleanup]\|pours\|reload\|drc\|save` | ✓ / – (dsn, route, check offline) | PCB, rules; `net_currents.json` (check: L-5 offline; `widths = "sim"`) | `route/<board>_board.json`, `.dsn`, `.ses`, `_routing.png`, `_drc.json`, `_netlist_diff.json` (with an Import Changes item); tracks, vias, pours |
| `edakit route diagnose [--net N]` | – | `route/<board>_board.json`, the board file's rules, the last SES | `route/<board>_diagnose/` (a PNG per open connection, `congestion.png`, `diagnose.json`), 7.5 |
| `edakit silk apply\|check` | ✓ | PCB, Gerber export | designators, `silk_<board>_<side>.png`, `gerber_<board>/`; apply: `silk_footprints_<board>/` (the print it found, for L-17) |
| `edakit silk preview` | – | board file, the last Gerber export (`gerber_<board>/`) | `silk_preview_<board>_<side>.png`: artwork, texts and the fixed designators of `[silk.place]` (exit 2 when one is in the way, 7.7) |
| `edakit export [--board]` | ✓ read | schematic, PCB, project file | `<artifacts>/export/`; with a maker that takes ODB++ also `odb_<board>.zip` (`easyeda_export_odb`, 2.5) |
| `edakit gate [--easyeda \| --eda]` | – / ✓ | everything; with `[project] requirements` the requirements files (8.7 – a file missing or not valid: exit 1 before a run) | `<reports>/<run>/`, with `stage_<id>.txt` the output of each project check that ran (8.1); a RELEASED run supersedes the earlier ones in their `fab/manifest.json` (8.3) |
| `edakit release current` | – | the manifests under `reports`; the real cost of its orders (`cart/<maker>/actual.json`) | – (with an order's real cost: estimate, quote and actual beside the release) |
| `edakit release withdraw RUN --reason TEXT` | – | the run's manifest | its `fab/manifest.json`: `status`, `withdrawn` {reason, by, date} |
| `edakit release verify FILE…\|DIR…` | – | the files (a folder: its `.zip` and `.csv` files), the manifests | – |
| `edakit fab --board B --out DIR [--offline]` | ✓ / – | PCB, exports, `route/<board>_board.json` (L-13, L-14, L-18), `silk_strings_<board>.json` and `silk_footprints_<board>/` (L-17), the stock snapshot (`order.md`), with `[routing] drc_rules` the rule set of EasyEDA's DRC (L-3) | `DIR/<board>/`, with `[order]` or `[cart]` also `order.md`, with `[order]` `order.json` (the settings in the fab hash), with `[routing] drc_rules` also `drc_rules.json`; with a maker of `[cart] makers` that matches by MPN `bom_<board>_mpn.csv`, with one that takes ODB++ `odb_<board>.zip` (F-7) |
| `edakit fab diff RUN_A RUN_B [--board B]` | – | `fab/<board>/` of two gate runs: Gerber layers, drill files, BOM, CPL, the order settings (`order.json`) | – |
| `edakit lock [status\|claim\|release\|yield CHAT\|hook] [--note]` | – | – (hook: tool name and, for `easyeda_api_call`, its `path`; library lookups of `READ_ONLY_TOOLS`/`READ_ONLY_API` pass without a claim, 11.2) | `~/.local/state/edakit/easyeda-lock.json` |
| `edakit proposal template [--feature]\|seal FILE [--out F]\|verify FILE` | – | a rule or feature proposal (no project needed) | seal: the issue body with its SHA-256 |
| `edakit doctor [--offline]` | ✓ read (not with `--offline`) | tool chain; `BRIDGE_TIMEOUT_MS` of the running easyeda-mcp-pro servers (`/proc/<pid>/environ`); with EasyEDA running, through an own server that claims nothing: `easyeda_bridge_status`, `easyeda_health_check` (connected, extension against server version, registry) and, while the claim is free or yours, `DMT_Project.getCurrentProjectInfo` (`[MaxDepth]` = the original extension) – 2.5, 12 | – |

With `toolchain = "kicad"` the commands marked ✓ run on the board's KiCad project and kicad-cli instead of EasyEDA –
what each does there is in 16.4; `pcb autolayout` and `lock` have no KiCad side, `KICAD_CLI` names another kicad-cli.

## 10.6 Files in a project

```text
edakit.toml                 the table of contents: project, boards, where the files are
hardware/requirements.toml  what the circuit must do: needs and requirements, if [project] requirements names it
hardware/graph.json         the hardware graph (only source of parts and connections), ground net, check settings
hardware/parts/*.json       parts database; an own footprint as data in its entry (footprint_data, 4.5)
hardware/datasheet/<name>.* the board as a part for other projects: parts entry and datasheet (edakit part datasheet)
hardware/sim.json           simulation scenarios
hardware/stock.json         what the assembler said about the parts, dated (edakit stock, P-4)
hardware/orders/*.json      the order records: run, hashes, maker, regulatory verdict, cart line, real cost
                            (edakit cart)
hardware/fees/<maker>.json  the project's fee table from its own orders (edakit cart actual); [cost] fees names another
hardware/makers/*.toml      a maker's profile of the project's own, named in [cart] profiles (edakit ships jlcpcb,
                            pcbway, eurocircuits and aisler in edakit/makers/)
hardware/schematic.toml     arrangement of the schematic
hardware/boards/<name>.toml one board: outline, holes, placement, routing, pours, silkscreen
hardware/boards/<name>.geometry.json
                            its footprint geometry, as edakit pcb dump measured it (in the layout hash)
hardware/signoff.json       manual checks and accepted warnings, bound to hashes
hardware/firmware.json      the firmware contract, if [firmware] is set (edakit firmware)
hardware/scripts.lock       the stamps of the project scripts and the changes of easyeda scripts, if [scripts] is set
                            (edakit run, edakit scripts stamp)
.claude/agents/<name>.md    the project's own agents; those that sign a sign-off are registered in [agents]
docs/decisions.md           numbered decisions (or wherever the project keeps them)
build/edakit/               artifacts (not versioned): caches, previews, routing, exports, cost.json;
                            library/ and footprints/: the library's symbols and footprints (edakit part import);
                            datasheets/: the datasheets edakit part fetch keeps (unless [project] datasheets names
                            another folder); scripts/: the output of each project script's last run (edakit run)
build/release/<run>/        gate runs (archive the released ones; fab/manifest.json says which one is current);
                            fab/<board>/cart/<maker>/ the files of an order: job, quote, page texts, screenshots,
                            regulatory review, check, cart line, real cost (edakit cart, 8.4)
```
