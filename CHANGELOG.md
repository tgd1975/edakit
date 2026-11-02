# Changelog

What changed in each version of edakit, newest first – for a maker who updates the plugin. Every merge that changes
edakit is a version of its own: the minor number goes up when a project must act, and its lines begin with **When
updating:**; the patch number goes up otherwise; the major number marks a milestone of edakit itself. Each section is
written once, by `.github/merge.py`, from the fragments in [changes/](changes/README.md) – the rule is in
[versioning.md](docs/concepts/done/versioning.md). Update with `claude plugin marketplace update edakit && claude plugin
update edakit@edakit`, then `/reload-plugins` or a new session; `edakit version` names the version that runs and what an
update brings.

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

- `edakit order --with CONFIG` puts the carts of several projects into one set of files – one line per supplier and code, the pieces summed, the comment naming each project – for one parts order for several boards (docs/concepts/new/parts-order.md, decision 1).

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
