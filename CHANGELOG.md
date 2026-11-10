# Changelog

What changed in each version of edakit, newest first – for a maker who updates the plugin. Every merge that changes
edakit is a version of its own: the minor number goes up when a project must act, and its lines begin with **When
updating:**; the patch number goes up otherwise; the major number marks a milestone of edakit itself. Each section is
written once, by `.github/merge.py`, from the fragments in [changes/](changes/README.md) – the rule is in
[versioning.md](docs/concepts/done/versioning.md). Update with `claude plugin marketplace update edakit && claude plugin
update edakit@edakit`, then `/reload-plugins` or a new session; `edakit version` names the version that runs and what an
update brings.

## 1.2.4 – 2026-11-10

- The perfboard in the documentation: the site's tab "A prototype" between "A circuit" and "A board" with the page "Build it on a perfboard", the perfboard plan in the glossary, its drawing on the start page, and the handbook's index pointing to 7.9.
- coin-cell-led gets a perfboard variant, `examples/coin-cell-led/variants/perfboard/`: through-hole parts, the plan on 14 × 15 holes, M-1, M-6 and M-5 signed (LR.7).
- `edakit perfboard`: the drawing at least 100 mm wide, so a small board's legend fits; `+` and `−` at the ends of a holder or connector and no "(stripe)" in its build row; the build list says a wire's stripped end is soldered with the lead or bridges in its pad; the wires' colours as in the cut list; the legend names only the marks the board has.

## 1.2.3 – 2026-11-10

- `edakit schematic copy` names the template EasyEDA cannot read and the way without a copy, `edakit schematic layout --save`, instead of ending on EasyEDA's bare TypeError (#337).
- A `[[silk.art]]` entry without `svg`, or with a key it does not take, is an error of the board file when edakit loads it – entry, key and the keys it takes –, not a KeyError in `silk apply` once it has reached EasyEDA (#338).
- An `easyeda` script that calls `eda.ensure_pcb_focus`, `activate_pcb` or `save_pcb` before `eda.open_pcb` is told to open the board's PCB first, not left with `KeyError: 'uuid'`; handbook 8.6 names the order (#339).

## 1.2.2 – 2026-11-10

- GEO.pour measures the copper-free circle and pieces on every seen face, not only on a poured one: a face that `[looks] visible` names – both faces without `[looks]` – and that the board file does not pour warns above `[copper] max_bare_mm` and `max_bare_mm2`, saying that the board file pours nothing there (#340).

## 1.2.1 – 2026-11-10

- The plan of a hand-wired board on a perfboard (handbook 7.9): a board with `wired = true` may have a board file with `[perfboard]`, `[place]` by hole or by role, `[[holes]]` in mm and `[[wire]]` – bridges on the bottom, insulated wires on top. `edakit perfboard` builds the nets the plan makes and holds them to the graph (PERF.net), checks places, grid, bodies, mounting holes, wires and current (PERF.place, .grid, .body, .mount, .wire, .current) and the hand-over (SYNC.plan), and draws the top view, the bottom view in the top's orientation and the cut, build and test lists. Two kinds as data, `edakit/perfboards/pad-per-hole.toml` and `3-hole-strips.toml`; a parts entry's `joined` names the pins a part joins inside. The plan is stage L of the gate, in the layout hash, its drawings and lists the run's manufacturing files under M-5; a project whose boards are all bought or hand-wired, with a plan, runs S, L and F without `--eda`. SYNC.footprint no longer notes the parts of a bought or hand-wired board as not dumped – there is no copy in EasyEDA to compare.

## 1.2.0 – 2026-11-09

- **When updating:** easyeda-mcp-pro is pinned to 1.11.0 (was 1.8.0), and server and bridge extension must have the
  same version. Copy the extension out of the pinned server (`bash <plugin>/edakit/easyeda/mcp-server.sh extension
  --copy .`), in EasyEDA uninstall the old "MCP Pro Bridge", import the new one, allow "External Interaction", restart
  EasyEDA, then end every running `easyeda-mcp-pro` server (`pgrep -af easyeda-mcp-pro`; Claude Code's restarts with
  `/mcp`). `edakit doctor` then shows "bridge extension 1.11.0 = server 1.11.0" (handbook 2.4, 2.5).
- `schematic check` and stage S close only their own schematic's tabs before they read; the other schematics stay
  open. easyeda-mcp-pro 1.9.0 reads the nets of the focused page only (M-11, our #865), so a net flag of another open
  schematic no longer puts a pin on a second net (#117). Another schematic with unsaved changes is no longer a
  finding `saved`.
- edakit sends the open project's UUID as `projectId` to easyeda-mcp-pro's tools instead of `"current"`, which its
  schematic and PCB reads refuse since 1.9.0 (`current-project-uuid-mismatch`).

## 1.1.17 – 2026-11-04

- The explorative DSL, a beta: a project that sets `[beta] dsl = true` in edakit.toml may write its graph as
  `hardware/graph.circuit` in the circuit language – definitions, usages, loops, parameters, aliases, includes,
  derivation rules and variants –, its requirements as `hardware/requirements.circuit`, and use `edakit graph
  fmt|derive|sysml|kerml`, `graph convert --to circuit`, `graph json --map`, `block add --set/--part` and `edakit lsp`
  with the VS Code extension of `editors/vscode/`. Without the switch nothing changes: such a file, a list of parts
  folders and those commands are refused with one line that names the switch, every other command line and its
  errors are as before. The site has a tab "Explorative DSL" (docs/dsl/); the codes of the DSL – DEF.derive,
  SYNC.graph – run only with the switch and are not in the catalog, `edakit explain` names them.
- `edakit graph fmt --check FILE …` takes its files after the option on Python 3.11 and 3.12 as well.

## 1.1.16 – 2026-11-03

- The parts library: C5274290 (LESD5D5.0CT1G) is a bidirectional TVS (`values.tvs = "bidirectional"`, its datasheet's symbol and I–V curve) – LIM.v holds it to VRWM in both directions, PATH.reverse lets a reversed source past it.

## 1.1.15 – 2026-11-03

- circuit-design: an error or a warning the circuit keeps goes into the decision round; its accept is written only
  after the user answers (working agreement 4, handbook 11.4).

## 1.1.14 – 2026-11-03

- Parts on hand: an inventory – a table with `ID` and `Quantity` in `.md`, `.html`, `.csv`, `.xlsx` or `.ods`, named in
  the new `edakit.local.toml` beside edakit.toml (in `.gitignore`) – is taken from first by `edakit order`: only the
  rest is ordered, `hand_assembly.md` says what comes out of the drawer; edakit never lowers a quantity. `edakit
  inventory` compares the project's hand-soldered parts with it, `edakit inventory template FILE` starts one (handbook
  8.4, 10.1; docs/concepts/done/parts-on-hand.md). Without the file nothing changes.

## 1.1.13 – 2026-11-03

- `edakit order check` finds a number written with its unit right after it, as LCSC's cart writes the weight ("1,500g"); before, ORDER.basket reported the weight as not in the page text. The LCSC profile is recorded (2026-11-03) with the BOM tool's steps "Create BOM" and the dialog of "Add to Cart" (keys `mapping`, `cart_dialog`), "Submit BOM" and "Secure Checkout" among the buttons never pressed; the skill cart's mode parts follows them.

## 1.1.12 – 2026-11-03

- The known gaps of the open designs closed (TD-124 to TD-133): a connector no longer hands a reversed source on from pin to pin (PATH.reverse); a low-side N-MOSFET in the ground return cuts a reversed source off ground (`[reverse] cuts` in catalog/paths.toml); `values.tvs: "bidirectional"` for a TVS that blocks both ways.
- Mains: net `ac` (a sine, its range the peaks) and the AC rating `v_rms_max_v` of a part or pin – LIM.v holds the rms there, and a resistor between two AC nets the difference of their like ends; kind `varistor` (VRMS, VDC); a connector pin of role `line` or `neutral` is a supply input (PATH.unfed); LIM.hazardous/ground names a board ground tied to a mains terminal.
- `values.adjust: "trimmer"` leaves a potentiometer set at the bench out of REQ.value/switch; `own.what: "copper"` – a solder jumper, a test pad – asks no supplier, no compliance fact and no EasyEDA device; the charger model drives its status output (role `stat`).

## 1.1.11 – 2026-11-03

- Handbook 19.4 and 19.5 show a thumbnail of each reference circuit's and open design's drawing beside its entry, linked to its catalog page; the site's link rewriting (`docs/pages.py`) now also handles links in HTML tags.

## 1.1.10 – 2026-11-03

- The parts-order concept is done and moved to docs/concepts/done/parts-order.md; the paths in edakit order, edakit cart, the LCSC profile, ORDER.basket's sources and the skill cart follow it.

## 1.1.9 – 2026-11-03

- The handbook (16.1, 17.11) and step 9 no longer name *Design → Import Changes* as a click that always comes: since E-2 edakit writes the Channel ID itself, and the click is asked for only if EasyEDA's DRC still waits for the import.

## 1.1.8 – 2026-11-03

- Handbook 5.5 links the test layers of chapter 19; Working on edakit and Adding a rule point to chapter 19 instead of restating the test layers and the evals.

## 1.1.7 – 2026-11-03

- The parts library: the 9 V battery snap C70374 and the slide switch SS-12D00-G3 (C22355741) signed by the owner – a
  copy taken with `edakit part add` no longer counts as a draft (PARTS.library).

## 1.1.6 – 2026-11-03

- The circuit language of 1.1.3 is withdrawn from main on the owner's word: it continues as a beta, the
  explorative DSL, outside the released plugin. A project's graph is JSON or TOML as before 1.1.3; no project had
  moved to a `.circuit` graph.

## 1.1.5 – 2026-11-03

- The parts at LCSC with the skill cart (`/edakit:cart parts`): `edakit order` writes `basket.json`, the supplier profile `edakit/suppliers/lcsc.toml` (provisional), and `edakit order check` holds LCSC's cart as the skill read it back to the basket – the new code ORDER.basket; lines already in the cart are listed, never touched.
- The combined shipment (`/edakit:cart combine`): a job at JLCPCB whose basket has LCSC lines carries LCSC's warehouse address and the conditions; `edakit order check` prints both carts' weights and the routes to compare, and after combining the cheapest of LCSC's methods that arrives by the new key `[cart] needed_by`. On the owner's choice the skill enters that address at JLCPCB's checkout – the one field of a checkout it sets (docs/concepts/done/parts-order.md, steps 2 and 3).

## 1.1.4 – 2026-11-03

- Handbook chapter 19, "Verification and validation: how edakit is tested": what a clean check proves and what it does not, the test layers, the reference circuits and the open designs – each with why it is there –, how a finding on them is judged, and what a new reference circuit or open design must bring. Its lists are generated (`python -m edakit.catalog.handbook --write`, kinds `references`, `designs`, `tally`); the catalog's pages show the same why.
- Four more open designs: a WLED controller (atoomnetmarc's ADLSC), a Fuzz Face (whbeers' Random Input), a mains relay board with an HLK-PM01 (ESPurna-H) and a LiPo charger (Adafruit's USB-C Micro-Lipo) – every finding judged.
- LIM.i/charge and the simulation's charger count a PROG resistor behind a switch or solder jumper: LIM.i/charge in the position that programs the most, the simulation in the position the load closes.
- LVL.undefined: a tri-state output whose net holds only LEDs behind their series resistors is their load, not a floating net (a charger's STAT); a base or gate held to the net the supply comes in on – a sim.json source's plus, a reversible source's pins – is defined although no pin types that net a supply.
- REQ.missing/REQ.value: a need on a pin left open is judged at a connected pin of the same name, the same terminal inside the part (a regulator's VOUT on its tab).

## 1.1.3 – 2026-11-03

- The circuit language, step T.1 of circuit-dsl-toolchain.md: quantities with units, ranges and tolerances
  (`edakit/lang/units.py`) and the E-series E6 to E96 of IEC 60063 as a catalog table (`tables/series.toml`).
- T.2: the reader of the circuit language – `edakit/lang/tokens.py`, `model.py`, `reader.py` and the attribute
  table `schema.py`: every statement of language 5 with its file and line, every error at once.
- T.3: the attribute table held to handbook 3.1 by a test; an unknown key names the nearest known one.
- T.4: a `.circuit` graph is compiled wherever a graph is read – `edakit check`, `sim`, the gate, the circuit hash
  (its compiled data, as a TOML graph's) and `edakit graph json --write|--check`, which writes and checks the
  resolved graph.json beside it; `--map FILE` writes where each part and net was written. New: SYNC.graph, an
  error of stage G when the generated graph.json beside a TOML or a .circuit graph no longer is what its source
  resolves to; `edakit hook` runs `graph json --check` for a .circuit graph as for a TOML one.
- T.5: `edakit graph fmt [--check] [FILE …]` lays a `.circuit` source out canonically, comments kept.
- T.6: `edakit graph convert --to circuit` moves a JSON or TOML project to `hardware/graph.circuit`: flat
  statements, read back before anything is written, `[project] graph` and `edakit` set, the resolved graph.json
  beside it, the sign-offs of scope circuit carried over.
- T.7: the block library's source is `edakit/blocks/<name>.circuit`, definitions of the language; the JSON
  `block add` reads is generated from it (`python -m edakit.lang.blocks --write`) and gains `params` and
  `derivations` – led, i2c-pullups and battery-sense; `block add` reads them only with `--set` (T.8).
- T.8: derivation rules (`series_resistor`, `divider`, `pullup`, `rc`); `edakit block add --set PARAM=VALUE`
  derives a block's values and writes the record into the graph's `derivations`, `--part DES=KEY` takes an
  entry inside the window; `edakit graph derive [--write]`; `edakit graph show` lists a part's records. New
  engine DEF: DEF.derive, a warning when a part's value lies outside its record's window or the record's inputs
  changed since (grade inputs). Handbook chapter 20 begins.
- T.9: a TextMate grammar for `.circuit` files and VS Code's language configuration (`editors/vscode/`).
- T.10: handbook chapter 20, the circuit language: its forms, words and quantities, statements, definitions,
  derivations, the compiler, the hash and the commands; 3.1, 2.7 and 10 name the `.circuit` form.
- T.11: `use DEF INSTANCE (PARAM = VALUE) PORT = NET … PART = DES …` – a definition of the project's or of
  edakit's block library expanded into parts and nets, its derivations evaluated into the graph's records.
- T.12: `for VAR in A..B` – parts, nets, usages, locks, cables and layout once per value, `{n}`, `{n+k}` put in.
- T.13: `param NAME = QUANTITY`, `alias NAME = PINWORD` checked against the entry, `include PATH` – one
  namespace over the main file and the files it includes.
- T.14: variants – `variant NAME of PATH` with redefinitions and additions over its base, in a chain;
  `[project] parts` may be a list of folders, and the circuit hash of such a project takes the entries its graph
  uses; a project with one folder hashes as before.
- T.15: requirements may be written in the notation (`hardware/requirements.circuit`); a requirement gains
  `subject` and `require`, a part or net `satisfies` and `decision` – DOCS.ref resolves all four.
- T.16: `edakit block add` on a `.circuit` graph writes a `use` statement after the parts and the resolved graph.json.
- T.17: the test project led-bar-circuit – led-bar in the circuit language – for the tests and the evals.
- `edakit graph fmt --check FILE …` takes its files after the option on Python 3.11 and 3.12 as well.
- `edakit graph fmt` writes a `set` whose JSON does not fit the line one member to a line, compact where a member
  fits, the closing brackets at the end of the last line; the block library's sources are laid out so.
- T.18: the skills circuit-design, hardware-change and new-project and the agent project-surveyor know the
  circuit language; handbook 20 describes usages, loops, parameters, variants and requirements in the notation.
- T.20–T.23: `edakit graph sysml` and `edakit graph kerml` export a project as SysML v2 and KerML, textual and
  as JSON, with the electrical library `edakit/lang/library/Electrical.sysml`; the requirements with it. The
  optional dependency group `sysml` (systree) and the CI job sysml read them with a standard reader.
- The SysML v2 export writes a requirement's `from` as a `#derivation connection` of the standard's
  RequirementDerivation library; KerML keeps a `dependency` per pair.
- T.24–T.27: the source map places a finding at its statement; `edakit lsp`, the language server (the extra
  `lsp`, pygls): errors and findings as they are typed, go to definition, hover, completion, formatting; the VS
  Code extension in `editors/vscode/`; the CI job vscode compiles it.

## 1.1.2 – 2026-11-02

- The parts library has a slide switch, SS-12D00-G3 (C22355741), and a 9 V battery snap with leads (C70374), both
  drafts from their datasheets; handbook 4.1 says how `edakit part add` lists the library by kind and how an entry the
  library lacks is written.
- `edakit hook install` names a step the session may not do – the hook's write, `git config core.hooksPath` – as a
  line `failed: …` with the command to run by hand, and exits 1; before, a refused `git config` was reported as done.
  The skill new-project goes on without them and puts them in its report.
- Every skill that runs `edakit` names `${CLAUDE_PLUGIN_ROOT}/bin/edakit` for a session that does not find it on the
  PATH – before the project has an edakit.toml, the session start does not.
- The handbook: the smallest edakit.toml for a circuit without a board of its own (2.7, 10.1); a switch closed unless
  the load lists it in `open`, a 9 V block as one cell state (5.1, 5.2); the form of the rows a requirement's `verify`
  names, SIM.state's among them (10.4). The newcomer's eval of documentation-newcomer.md found these missing.

## 1.1.1 – 2026-11-02

- A pin of the template on a second net while another schematic of the project is open is easyeda-mcp-pro's, not EasyEDA's: its net reading takes the net flags of every open schematic but the wires of the focused one (M-11, checked live on pytree, TD-105). SYNC.schematic's reason, the `saved` finding of `schematic check` and handbook 6.2 and 12 say so; the check still closes the other schematics first.

## 1.1.0 – 2026-11-02

- **When updating:** easyeda-mcp-pro is pinned to 1.8.0 (was 1.6.0), and server and bridge extension must have the
  same version. Copy the extension out of the pinned server (`bash <plugin>/edakit/easyeda/mcp-server.sh extension
  --copy .`), in EasyEDA uninstall the old "MCP Pro Bridge" – also the patched one named "MCP Pro Bridge (depth 12,
  schematic PDF, ODB++)" –, import the new one, allow "External Interactions", restart EasyEDA, then end every running
  `easyeda-mcp-pro` server (`pgrep -af easyeda-mcp-pro`; Claude Code's restarts with `/mcp`). `edakit doctor` then
  shows "bridge extension 1.8.0 = server 1.8.0" and "return depth: answers deeper …" (handbook 2.4, 2.5).
- edakit's two patches of easyeda-mcp-pro are gone (`bridge-extension-patch.sh`, `odb-tool-patch.mjs`): 1.7.0 brings
  their fixes – `maxDepth` for `easyeda_api_call` (edakit asks 12 levels), the schematic PDF, `easyeda_export_odb` (in
  edakit's own servers, profile `experimental`). The pick-and-place export comes as csv (`cpl_easyeda.csv`, an xlsx of
  an older extension read as well), hand-soldered parts leave the BOM on create, and a net's pours fill in one call
  (upstream M-1 to M-10, TD-26, TD-84). easyeda-mcp-pro is MIT licensed since 1.7.0.

## 1.0.14 – 2026-11-02

- `schematic check` and stage S close every saved schematic tab before they read, not only their own: EasyEDA lists a pin of the template on a second net while the board's schematic is open (E-18, #117 – live on pytree). Another schematic with unsaved changes stays open and is named in the finding `saved`.

## 1.0.13 – 2026-11-02

- The pre-commit hook's edakit block holds under the project's `set -euo pipefail`: without edakit on the PATH it still reaches the plugin, and a failing step still blocks with its exit code. A block of 1.0.11 counts as older; the session start names it, `edakit hook install` renews it.
- `edakit hook run` takes the file of `doc_pin_table` as one of the configuration's inputs – under `locks` or `checks`, also in a JSON graph wrapped in `graph` – so a change to the documented pin table runs `edakit check` (pytree's `docs/hardware.md`).

## 1.0.12 – 2026-11-02

- The handbook's long guide chapters – 3, 4, 5, 7, 8 and 14 – open with a summary, **In short.**, of their core
  statements, each with the section that owns it; `tests/test_style.py` holds it for every guide chapter over 450 lines.

## 1.0.11 – 2026-11-02

- `edakit version pin [current|latest|X.Y.Z]` and `unpin`: one version in every edakit.toml (`[project] edakit = "==X"`) and in every edakit call of CI and scripts, or following the updates again (`>=X`, the calls without a ref); listed first, written with `--write`. The marketplace's `ref` in `.claude/settings.json` goes – it held the plugin for every project on the machine, not for one; handbook 2.3 no longer advises it.
- `edakit hook install|check|run`: edakit's block in the project's pre-commit hook – written or renewed by `install`, the project's own steps kept, `core.hooksPath` set –, which finds edakit itself (a commit by hand needs no wrapper script) and runs the steps of every configuration whose files are staged. The session start says in one line when the hook is missing, has no block or an older one, or git does not run it (handbook 2.7).

## 1.0.10 – 2026-11-02

- Handbook 17 and 18 show the routed board of both walkthroughs, from the Gerber files of a gate run (TD-104).

## 1.0.9 – 2026-11-02

- `edakit version` and the skill `/edakit:version`: which edakit runs, the plugin's installation per scope with the one in effect here, the newest version on GitHub and the changelog's sections in between – their **When updating:** lines first –, and where the project pins edakit (`.claude/settings.json`, CI, scripts), with whether the pins agree; the update command for the scope in effect, run on the owner's word (handbook 2.3).

## 1.0.8 – 2026-11-02

- The handbook follows the code where the chapters' reviews found it did not (TD-83): a regulator's `i_load_min_a` is
  checked, not added as a load (5.1); transient runs are judged by LIM.v, LIM.i and LIM.range (5); the drawing's four
  supply colours (6.5); DOCS.derived in the requirement checks (10.1, 10.4, 10.5); the lock file's
  `$XDG_STATE_HOME` and `EDAKIT_LOCK_FILE` (11.2); KiCad's coordinates converted from mil (16.3); the REACH fact's
  grade in 15.3; footprint data's live run and the slot direction (4.5); every server's `BRIDGE_TIMEOUT_MS` the same
  (2.4); the permission "External Interaction" (2.5); "your numbers" for what the requirements skill asks back
  (3.6, 11.1, 14.1). The `compliance` field says it is support, not legal advice.
  Section 8.4 is "you order and pay". The engines table of 14.2 is generated from the catalog, and ORDER's `decides`
  names `read` and `confirm`.
- Sources name the section that holds what they cite: LIM.v and the derating table 5.3, PARTS.fact's lead 4.1, the
  rule files KiCad gets 7.5 and 16.5, SYNC.odb's fix 16.6, the RoHS and REACH grades 15.3; the catalog names pytree
  and the bell where it said "the reference project".

## 1.0.7 – 2026-11-02

- Handbook 1: the pipeline is a Mermaid diagram, drawn on GitHub and on the site; the site's handbook sidebar lists the
  chapters by number.
- Chapter 17 is the "Walkthrough on EasyEDA", beside chapter 18, the "Walkthrough on KiCad".
- Handbook 4 shows symbol pictures: the pins by role, the limits and values of four kinds, and the footprint that
  prints "+" at the cathode with its fix in the graph (4.4).

## 1.0.6 – 2026-11-02

- `schematic check` and the gate's stage S read a schematic as saved: its tab is closed and its pages opened again
  first, so the result no longer depends on whether stage F of an earlier gate closed the template's tab. A tab with
  unsaved changes stays open and is named in a finding `saved`. `schematic create --save` reads the save opened again
  and exits 2 when it differs from the graph (E-18, #117).

## 1.0.5 – 2026-11-02

- The handbook shows six more diagrams: the graph and the files around it (2.7), what `edakit sim` computes (5.2), the
  way from the current release to the boards (8.4), roles and sessions (14.1) and how a proposal becomes a change
  (14.4); the architecture page shows edakit's three layers.

## 1.0.4 – 2026-11-02

- KiCad is described as the other choice beside EasyEDA Pro, the default: handbook 16.1 "EasyEDA Pro or KiCad" says
  when to take which, setup 2.2 lists both side by side, chapters 2, 6, 7, 8 and 10 carry one line "On KiCad", and
  chapter 18 is the "Walkthrough on KiCad". `/edakit:new-project` gives each tool chain its reason.
- `edakit gate --eda` is the flag's name for both tool chains; `--easyeda`, the old name, still works.
- The handbook shows pictures: diagrams of what talks to what on both tool chains (2.1), the gate's stages (8.1) and
  the four hashes with their sign-offs (8.2); the drawn schematic in both styles (6.5), the placement plan, the
  routing and the silkscreen of a real board (7.4, 7.5, 7.7), a domain's reference circuit (14.2).

## 1.0.3 – 2026-11-02

- `edakit cart actual`: the fee table's PCB price row of a bare order is for the Gerber outline the form names, not the estimate's size with the edge rails of its assembly class (the bell's tht: ordered bare as 85 × 56 mm, estimated Standard as 85 × 66).

## 1.0.2 – 2026-11-02

- `edakit cart confirm` and the skill cart's mode `confirm`: what the maker asks to confirm after the order – the production file as released, the placement as the maker's engineer adjusted it, part by part against the polarity sheet (ORDER.confirm) – checked, and M-2 written into the sign-off file on `--sign`, the owner's word; the JLCPCB profile's `[confirm]` (the two buttons, the viewer, its marks). After the order, `confirm` and `actual` read the run the order was placed against when a newer release has no job for the board.

## 1.0.1 – 2026-11-02

- The steps: ten short pages from the plugin's install to the ordered board – what you do, what Claude asks, what you
  decide – in the site's new tabs "A circuit" and "A board"; each handbook chapter names its step as the short way.

## 1.0.0 – 2026-11-02

- **1.0.0.** The first boards are ordered: pytree's tree, assembled, from the JLCPCB cart the skill cart filled and
  checked, and the Christmas bell's two through-hole variants, bare, in the same order with the parts from LCSC. The
  documentation's entry layer – start page, quickstart, how it works – is built. Nothing a project has to do.

## 0.6.2 – 2026-11-02

- The JLCPCB fee table names its sources without the order and customer numbers of the reference carts.

## 0.6.1 – 2026-11-02

- `edakit order --with CONFIG` puts the carts of several projects into one set of files – one line per supplier and code, the pieces summed, the comment naming each project – for one parts order for several boards (docs/concepts/done/parts-order.md, decision 1).

## 0.6.0 – 2026-11-02

- **When updating:** a sign-off's note is passing evidence for a requirement only where it names the ID after
  "requirements met:" (up to the next `;` or `.`) – an ID elsewhere in the note, "R-4 not met" too, counts for nothing
  (handbook 8.7). The reviewer agents have written that clause since requirements came; a note of another form gets it
  in the sign-off file – `edakit gate` lists a requirement whose note no longer names it.
- KiCad: the pours follow the outline, and a rule area keeps each mounting and tooling hole's keep circle free – no
  square notch to the edge any more (`pcb pour`, `route pours`); GEO.pour and the computed pours of `route check`
  measure the area the pours really fill, without the notch, on EasyEDA too.
- An LED's `values.vf_vs_if`, `[[A, V], …]` read off the datasheet's IV curve, sets the simulation's ideality (2
  without); `edakit part lint` holds the points to their form.

## 0.5.0 – 2026-11-02

- An `easyeda` script may change the copper in the PCB: `writes = ["pcb:<b>", <files>]` – vias and a pour placed after the pours, with the list of what it placed beside. It runs after what it reads (`routing:<b>`: after `route all`) and before the scripts that read its files; `edakit run` records the change, and `route all` and `route pours` mark it gone in `hardware/scripts.lock`, so the script is outdated until it ran again. EasyEDA's DRC checks this copper, `route check` does not (handbook 8.6, #113).
- Every board with an assembly side gets `odb_<board>.zip` and `bom_<board>_mpn.csv` in stage F, whatever the makers of `[cart] makers` – a release can be quoted at AISLER, Eurocircuits or PCBWay as it is; SYNC.odb holds that ODB++ to the run as a note, neither file enters the fab hash, both are in the manifest for `edakit release verify` (`[release] maker_files`, #153).
- **When updating:** nothing has to change, and no sign-off lapses; the next gate run makes one more EasyEDA export per assembled board and shows a SYNC.odb note on a bridge without the ODB++ patch (`edakit doctor`, handbook 2.5). To keep the behaviour of before, set `[release] maker_files = "cart"`.

## 0.4.18 – 2026-11-02

- The tests run in parallel (pytest-xdist in the group `dev`): `uv run --group dev pytest -q -n auto`. From the next version on, an update that moves only the dev tools is no version (`.github/versions.py`).

## 0.4.17 – 2026-11-02

- edakit cart: a bare board at JLCPCB passes ORDER.form and ORDER.files – its quote page has no "Product Description" (now a checkout field without assembly, profile `fields.<key>.assembly`) and names no upload (`unshown_bare`: the cart line names the Gerber); "PCB Assembly" and "Stencil" are in the profile's ignore, and the job says "bare" instead of "5 assembled" (live run 2026-11-01).

## 0.4.16 – 2026-11-01

- Issues by others in the edakit repository: the Action wrap posts every text by others on them again – plain text, numbered within the issue, sealed –, and the repository owner answers with `review`, `accept` or `reject`; the skills propose-rule and propose-feature name the commands (handbook 14.4).

## 0.4.15 – 2026-11-01

- The walkthroughs end with their story: what the coin-cell board and the 555 blinker changed in edakit is chapter 13's
  13.9 and 13.10 now; pytree's page in the gallery shows its board and schematic.

## 0.4.14 – 2026-11-01

- The documentation by reader (docs/concepts/new/documentation.md, steps D.2 to D.9): a start page of one screen,
  a quickstart to the first finding without EasyEDA (`docs/quickstart.md`), how it works with the pipeline, the loops,
  the words, the state and the future work (`docs/how-it-works.md`), a gallery of the projects built with edakit
  (`docs/projects/`), reader pages for adding a rule, working on edakit and the architecture; the site's navigation by
  reader – the circuit, the board, the reference, the sources last as "Inside edakit".
- The handbook's chapters condensed in place: a first paragraph each, subheadings, shorter sentences and paragraphs,
  the history in chapter 13; chapter files and section numbers unchanged. The chapters' lists of codes are short
  tables linked to the catalog, whose page is split into one page per engine; 10.5 is one entry per command, its
  synopsis generated from the command line.

## 0.4.13 – 2026-11-01

- A project can say which edakit it needs: `edakit = ">=0.4"` under `[project]` in edakit.toml. When the
  running edakit does not meet it, `edakit check` notes STRUCT.edakit and the session hook says so; the working
  agreements' first line names the edakit that runs (handbook 2.3, 10.1).

## 0.4.12 – 2026-11-01

- `edakit cart compare` puts the quotes of every maker of `[cart] makers` side by side – the board total as quoted and in `[cost] currency`, the order total, the lines a maker marked or did not match, the lead time, whether `edakit cart check` passed on that very quote – names the lowest board total and writes `cart/compare.md` of the release; the skill cart can collect the quotes of several makers before one cart is filled (handbook 8.4).

## 0.4.11 – 2026-11-01

- Nothing changes for a project: the concept of edakit's versions moved to `docs/concepts/done/`, and the
  path in a docstring follows.

## 0.4.10 – 2026-11-01

- EasyEDA's pours follow the outline and keep every mounting and tooling hole free with a NO_POURS region instead of a notch to the edge, and the tooling holes stay on the board while the pours fill (E-13) – the copper of a board changes at its next `route all|pours`, so its layout sign-off M-5 is asked for again.
- `part build` modifies the pins of a symbol box in place instead of deleting and creating them (E-11); the orphan-attribute sweep of `schematic layout` stays as a cheap check (E-10).

## 0.4.9 – 2026-11-01

- `route all|pours` fills one fresh pour per call instead of a net per call and stops when the bridge refuses: easyeda-mcp-pro 1.6.0 refuses every copper rebuild after one it could not verify – the second pour of a net in one call was such a case – until EasyEDA restarts; before, edakit went on with empty pours (M-10).

## 0.4.8 – 2026-11-01

- `edakit release publish` ends the release notes with "Released with edakit X.Y.Z" and the link to that version; `[release] publish.credit = false` leaves the line out (handbook 8.3).
- The plugin's texts in `/plugin` say "circuit design as code", for EasyEDA Pro or KiCad; the README says what edakit runs, sends and fetches, and how to ask a question or report a bug.

## 0.4.7 – 2026-11-01

- `schematic create` and every rename through EasyEDA's API need the project tree of EasyEDA's left panel shown once after EasyEDA starts – EasyEDA renames only what that tree lists (E-17); edakit's message says so when a rename fails, the start skill asks for the click.

## 0.4.6 – 2026-11-01

- The DRC of `route all`, `silk apply` and the gate runs at once and reloads the PCB only when it reports Connection Errors, then runs once more (E-7) – `route all` no longer reloads before it unless `[routing] drc_rules = "write"`; the PCB tab's probe throwing on 3.2.209 counts as an inactive tab (E-3).

## 0.4.5 – 2026-11-01

- `edakit route` stitches islands that no `pour_regions` entry holds (#112).
- Pours keep the copper distance of a tab zone (#114).
- `[[silk.art]] fit = "viewbox"` places an SVG artwork by its viewBox, so it stays in its frame (#115).
- `edakit schematic create` writes the title block under EasyEDA Pro 3.2.209 (#116).

## 0.4.4 – 2026-11-01

- No click on *Design → Import Changes* any more (E-2): `pcb parts --write` writes the PCB part's Channel ID into the schematic part as it does the UniqueId, and `route all|drc` and `silk apply|check` write it into parts linked before when the DRC reports "Netlist Error – Import Changes" with schematic and PCB equal, reload the PCB and run the DRC once more – exit 3 only if the item is still there.

## 0.4.3 – 2026-11-01

- GEO.pour finds every bare area above `[copper] max_bare_mm2` on each side, not only the largest circle (#103).

## 0.4.2 – 2026-11-01

- A project never opened is found by its name through EasyEDA's API – `getAllProjectsUuid` with each project folder of `DMT_Team.getAllTeamsInfo` (E-9) – instead of reading EasyEDA's `config.json` and `.eprj2` files; `EDAKIT_EASYEDA_HOME` is gone.

## 0.4.1 – 2026-11-01

- The concept of the proposals pipeline moved to docs/concepts/done/; comments and links follow it.

## 0.4.0 – 2026-11-01

- **When updating:** in EasyEDA Pro uninstall the old bridge extension, import `~/.easyeda-mcp-pro/easyeda-bridge-extension-1.6.0.eext` (built by `bridge-extension-patch.sh`, handbook 2.5), allow "External Interactions", restart EasyEDA and every MCP server – easyeda-mcp-pro is pinned to 1.6.0 now, and since 1.5.1 a server whose extension has another version refuses every write, export and `easyeda_api_call`.
- The PCB's parts are read with the PCB focused and its project's exact UUID – 1.6.0 refuses projectId "current".
- EasyEDA's BOM is no longer cleaned of designators listed twice – since 1.6.0 it lists each part once, and SYNC.bom reports a designator listed twice (TD-54).

## 0.3.3 – 2026-11-01

- The proposals Action waits for its tests before a result and lists each proposal as one item in the pull request,
  with no placeholder left in it (TD-43).

## 0.3.2 – 2026-11-01

- The proposals Action carries over a commit an earlier triage pushed after its pull request was merged even when the
  generated catalog page conflicts – the page is written again – and the new pull request names it (TD-43).

## 0.3.1 – 2026-11-01

- The proposals Action judges with a token that cannot write, and a fixed job checks each build against the
  pipeline's paths before anything is pushed: the pipeline never changes through itself. The queue triages a proposal
  once even when several are filed together. Issues by others are welcome – the owner hands one over with a sealed
  proposal as a comment (`propose-rule`, `propose-feature`) (TD-42, docs/concepts/done/proposals-pipeline.md).

## 0.3.0 – 2026-11-01

- **When updating:** a project without `[project] requirements` writes its requirements file with `/edakit:requirements` and names it in `edakit.toml` before its next release – DOCS.file is open until then: `edakit check` passes, `edakit check --release` and the gate do not release (handbook 3.6, 8.7).

## 0.2.0 – 2026-11-01

- **When updating:** nothing beyond the update itself – 0.2.0 is edakit's first number. From now on the
  plugin comes from the version's tag, and `edakit --version` and the gate manifest's `tools.edakit` name the version
  (from a git checkout with its commit: `0.2.0+g1a2b3c4`). A project that sets the new `purpose.country` (below)
  changes its circuit hash and signs M-6 again.
- What came on 2026-11-01, before the first number:
  - **New checks:** PARTS.fact/reach – a part's SVHC when the board is given or sold (#95); DOCS.derived – a
    requirement names who stated it (#98); GEO.formed/counter – formed leads in one row (#100); GEO.pour – every bare
    area above `[copper] max_bare_mm2` on each side (#103); PARTS.fact/rohs for every BOM part and FILES.order/lead at
    the release; LIM.i holds a magnetic buzzer's coil current to its rating (#90).
  - **New:** `purpose.country` – the country whose law the regulatory review applies, DE and AT (#94); a touch limit
    with its own ambient in `touch_c` (#93); an RGB LED's limits per colour in `edakit check --coverage` (#91); pictures
    in the release protocol, and the board's layers over each other with stage F (#99); CPL rotations per maker
    (`[cpl] zero`, `[cpl.turns]`, SYNC.cpl); JLCPCB's customs description as `[order] customs`; the makers' RoHS and
    REACH statements in their profiles; AISLER matches the parts by MPN, which the KiCad footprints now carry;
    Eurocircuits' BOM import and basket; the skill cart stops at every consent.
  - **Fixed:** stage L finds a part bought elsewhere by the MPN its `part` names (GEO.hole, GEO.mark,
    SYNC.footprint, #88); GEO.mark takes a "+" as artwork only on an artwork's shapes (#92); SYNC.odb takes an edge one
    raster point off as rounding; `silk apply` no longer doubles the print on a fresh clone; no `fab/<board>/current`
    left beside a run's files; `place` takes every part with `bom: false` out of the BOM (M-9); what the KiCad live
    test found (LT-1 to LT-8, LT-10, LT-11); the skill requirements writes the maker's inputs, not edakit's outputs
    (#97).
