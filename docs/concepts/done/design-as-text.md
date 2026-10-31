# Circuit design as text

Status 2026-10-28: being built; all decisions are taken (table at the end), and the state of each step is in
[implementation-plan.md](../new/implementation-plan.md). The findings come from reading edakit at `a8b6011` (with PRs
#78 and #79) and the repositories of the reference project and the Christmas bell.

## Goal

Everything needed to create, edit and change a circuit is text in the repository, and every step runs through an LLM.
edakit is close. Two things exist only in EasyEDA today: the positions the auto-layout sets, and own footprints and
symbols. Three smaller ones come on top: the rule set of EasyEDA's DRC, three order settings (thickness, mask and print
colour) and the position of single designators.

Every piece of a project has to pass two questions:

1. **Text:** Is it in a file in the repository that an LLM can read and write – not only in EasyEDA, in a picture or
   in someone's head?
2. **Executable:** Can Claude do the step with a command, a script or an MCP call, without a hand on the mouse?

Generated content need not be text: the schematic and the PCB in EasyEDA, the Gerber files and the pictures are
outputs. Everything that determines them has to be text.

## Where it stands

A project holds ten kinds of sources as text today, each with one writer and one check. Not in the repository, because
generated: the EasyEDA project, Gerber, BOM, CPL and the pictures for the reviews.

| Source | File | Written by | Checked by |
| --- | --- | --- | --- |
| Circuit: parts, pins, nets with voltage ranges, purpose, hand-over to the layout | `hardware/graph.json` | Claude as circuit designer | rules P and G, simulation E, circuit hash |
| Parts data from datasheets, with sources | `hardware/parts/*.json` | agent part-selector, skill own-part | rules P, circuit hash |
| Operating cases of the simulation | `hardware/sim.json` | Claude | stage E, circuit hash |
| Arrangement of the schematic | `hardware/schematic.toml` | Claude | stage S |
| Board: outline, holes, plan, routing rules, pours, silkscreen, order form | `hardware/boards/<name>.toml` | Claude as PCB designer, `edakit pcb place --write` | stage L, F-6, layout hash |
| Silkscreen artwork | SVG, often from a generator | Claude | layout hash (sign-offs of scope `layout`), and the fab hash through the gate run's silkscreen (M-5) |
| Project steps edakit cannot do | project scripts | Claude | nothing yet (concept [project-scripts.md](project-scripts.md)) |
| Project, boards, gate | `edakit.toml` | Claude | checked on loading |
| Decisions | `docs/decisions.md` | Claude writes, the owner decides | – |
| Sign-offs | `hardware/signoff.json` | review agents | count only for the hash they checked |

edakit also writes two versioned files that are derived, not sources: `hardware/stock.json` (the stock snapshot, P-4)
and `hardware/firmware.json` (the firmware contract, #70).

The knowledge lives in edakit: rule catalog, building blocks, handbook, skills and agents. New knowledge comes in
through `propose-rule` and `propose-feature`. Library parts are dependencies by their LCSC number. `edakit part import`
(#32) reads their symbol pins and footprint without EasyEDA into a cache; P-1 and the plan use it. The layout hash
takes only the geometry `pcb dump` measures in EasyEDA.

## Gap 1: positions from the auto-layout

What EasyEDA's auto-layout places is in no file. The fab hash sees it at the next gate run, through the CPL rows and
the Gerber layers; the layout hash does not. Proposal: edakit writes these positions into the plan of the board file
after the auto-layout.

**Today:**

- `edakit pcb autolayout` lets EasyEDA place the unlocked parts and waits until their positions stand still
  ([pcb.py](../../../edakit/pcb.py), `autolayout`). It writes nothing. In the reference project the auto-layout places
  every part except the fixed ones.
- `edakit pcb place --write` (#57) already puts every part with a host – `layout.near`, `[near]`, decoupling – into
  `[place]`, marked `auto = true`; a later run may move those rows. The auto-layout places the rest.
- `pcb dump` turns every part to 0° and TOP to measure it and leaves it so. Afterwards `pcb apply` and the auto-layout
  have to run again, and the auto-layout may place the parts differently.
- The layout hash covers the board files, `[release] layout_files` and the footprint geometry
  ([gate.py](../../../edakit/release/gate.py), `layout_files`). The geometry measures each part relative to its own
  origin (`measure`), without its position. A new auto-layout changes the board. Since #65 the fab hash sees that, so
  M-5 with its scope `fab` lapses at the next gate run. Only an M-5 listed with scope `layout` would still count; the
  Christmas bell binds its M-5 to the fab hash of the run its reviewer checked (D-20).
- L-7 holds only the parts in `[place]` to the plan. For parts from the auto-layout there is nothing to hold them to.
  The same goes for the direction of polarised parts (`uniform`, #60), the mated plugs (`mate`, #62) and the
  mechanical model: they see only `[place]`.
- The handbook already knows the way out for a single part: a part in the way is taken into `[place]`
  ([12](../../../handbook/12-troubleshooting.md)).

**Proposal:**

1. After the positions stand still, `edakit pcb autolayout` writes position, rotation and side of every part it placed
   as an entry in `[place]` of the board file, next to the entries by hand (decision 3). The entry carries
   `auto = true`, as the rows of `pcb place` do: a reader sees that nobody designed it.
2. Everything that holds for fixed parts then holds for these: `pcb apply` puts them back after a dump, L-7 holds them
   to the plan, the plan check sees overlaps and `near`, the direction and plug checks and the mechanical model see
   them, and the layout hash covers them.
3. From then on the auto-layout only runs for parts without an entry. To have a part placed anew, delete its entry; to
   move it, change it.
4. A new check in stage L: every part of the graph has an entry in the plan, as an error, not a hint. That makes
   "everything as text" checkable for the placement. A board placed before, with its routing, gets its positions once
   from a command that reads them in EasyEDA and writes them into `[place]` as fixed entries; a new auto-layout would
   move the parts off their tracks. The reference project needs that when it moves to edakit. The bell has all 19
   parts in `[place]`, on all four boards.

Effort: small. The loop already reads the positions while it waits, the conversion from EasyEDA to plan coordinates
exists (`Board.from_eda`), and `write_place_rows` already writes rows into `[place]`.

## Gap 2: own footprints and symbols

Symbol and footprint of an own part exist only in EasyEDA; the repository knows them only as a UUID. Proposal: pads,
outline and print go into the parts entry as data, and edakit builds the project's copy from them.

**Today:**

- A part without an LCSC number carries an `easyeda_device` with `uuid` and `libraryUuid` in the graph, a pointer into
  an EasyEDA library. The skill own-part asks for a footprint from the user's library – drawn in the GUI or by a
  script.
- The projects help themselves with scripts that drive the API directly:
  - The Christmas bell rebuilds the project's copy of a 2×12 female header into the T-Display: 24 pins, 24 pads,
    outline and labels, 180 lines of Python. A device created through the API cannot be placed in the local client;
    the copy of a system part can.
  - The reference project rebuilds the RP2040-Zero into the RP2350-Zero. A second script makes the polarity print of
    all LED footprints the same and changes holes and pad positions.
- The parts entry names the footprint and knows its leads (`lead`), the body height (`body.h_mm`) and the box of a
  mated plug (`mate`) – but no pads, no outline and no print. The symbol it knows only as the pins' split onto its
  sides, for `schematic draw`.
- `pcb dump` measures the geometry in EasyEDA. For an own part it measures what a script or a hand put there before.
  `edakit part import` (#32) reads the footprint of an LCSC part without EasyEDA – pads with number, position, shape,
  size, rotation and hole – into a cache. An own part has no such source.

**Proposal:**

1. The parts entry gets a footprint as data: origin, pads in the form `part import` caches them (number, position,
   shape, size, rotation, hole), outline and print (lines, texts, polarity mark), in mm. The symbol follows from `pins`
   and `symbol`, as the drawing does today.
2. An edakit command builds the project's copy from it: a system part is placed as the carrier, then symbol and
   footprint of the copy are rebuilt. Both scripts already go this way.
3. A check holds the copy to the data: pins and pads in EasyEDA equal the parts entry. A pad without a pin in the entry
   is a finding, and so is the reverse.
4. To change a library footprint, edakit writes its measured geometry into the entry as data. From then on it is an own
   footprint, and the change is a line of text.
5. The footprint data counts in the layout hash. A changed footprint voids the sign-offs of scope `layout` as a changed
   geometry does today, and the fab hash sees it at the next gate run.

Effort: medium. Two projects have tried the API path, and the pad format exists in the import cache. New are the
command, the check and the handbook.

## Fixed tracks: no gap

The board file can already prescribe tracks: `[[routing.fixed_wires]]` with net, layer, width and points in plan mm
([7](../../../handbook/07-pcb.md)). edakit writes them into the DSN as protected wiring; Freerouting routes around them
and keeps them.

What remains: a fixed track lies on one layer, and the format has no fixed layer change. edakit writes fixed vias only
for the fanout of a pour. The reference project still lays its track skeleton (D-48) with a script of its own.

## Smaller findings

Three smaller things are also outside text. None of them stops a board, but each has to be known or set up outside the
repository today.

| Finding | Today | Proposal | Effort |
| --- | --- | --- | --- |
| Rule set of EasyEDA's DRC | L-3 asks for a DRC without findings, with the rule set the project holds. edakit does not set it; the handbook advises setting track rules in the GUI ([9](../../../handbook/09-easyeda-api.md)). | edakit writes the rules from the board file through the API (`overwriteNetRules`) – or reads them and checks them against the board file. | small to medium |
| Order settings | Since #40 finish, mark, remark and tab zones are in `[order]` of the board file; every gate run writes `order.md`, and F-6 checks it. The thickness (`thickness_mm`) feeds only the mechanical model; mask and print colour are in no file. | `[order]` gets mask and print colour and takes the thickness from `thickness_mm`. | small |
| Position of single designators | `silk apply` places designators where there is room, steered by groups, priority and gap. A single one cannot be fixed. | A position per designator in `[silk]`, as `[place]` does for parts. | small |

## Scope

Decisions, the order (M-2) and the acceptance after delivery (M-4) stay with a person on purpose. That does not
contradict the goal: Claude prepares, the owner decides, and the decisions are text in the repository too.

Not part of the goal:

- **Headless, CI:** EasyEDA Pro as a desktop program with MCP is enough.
- **The two clicks in EasyEDA:** creating the project by hand and one *Import Changes*. They go once the API allows it
  ([upstream issue 4](../../../upstream/issue-4-create-project.md)); until then they do not stand in the way.

The concept [project-scripts.md](project-scripts.md) serves the same goal: which script runs when is then checked text
in `edakit.toml` instead of a sentence in a project's README. Gap 2 would replace two of today's scripts, the
T-Display's and the LED footprints'. The concept [requirements.md](requirements.md) covers what the circuit should
do, which today is spread over READMEs, decisions and chats.

## README

The README advertises circuit design as code, the name the user chose (decision 1); "hardware as text" was the
alternative.

Draft for the head of the README:

```markdown
**Circuit design as code.** Everything a board is made of is text in your repository: the circuit, the parts with
their datasheet sources, placement, routing rules, copper pours and silkscreen per board, every decision and every
review sign-off. Claude Code does every step from there – checks, simulation, schematic, PCB, routing, release –
through edakit and EasyEDA Pro. A change is a diff, and the release gate checks it on the files that go to the
manufacturer.
```

The paragraph is fully true only once the gaps and findings above are closed. It goes in now anyway, with the open
points under "Status and limits"; each closed point removes a line there (decision 2).

## Further: a language of its own

A small language for the circuit makes the graph readable without touching the chain of checks. edakit translates it
into today's JSON, and every check keeps running on that.

**What is cryptic about the JSON**, on the Christmas bell's graph:

- Pins are numbers of the EasyEDA symbol: `U1.9` instead of `PD6`.
- The names mislead: pin 1 of LED5 is called "C" in the symbol but is the anode. Only the role in the parts entry says
  so.
- A path through the circuit falls apart: step 1 (D6 → 330 Ω → green LED → GND) is spread over three nets, two
  components and a pin lock.
- JSON has no comments. Reasons live in `notes` fields.

Today, step 1 shortened:

```json
{"designator": "R4", "type": "resistor", "part": "330 Ω 0805", "lcsc": "C17630", "value": "330Ω", "pins": {"1": "1", "2": "2"}},
{"designator": "LED5", "type": "led", "part": "XL-504UGD", "lcsc": "C2895549", "bom": false, "pins": {"2": "A", "1": "C"}},
{"name": "LED_G1", "pins": ["U1.9", "R4.1"], "v": [0, 5.5]},
{"name": "LED_G1_A", "pins": ["R4.2", "LED5.1"], "v": [0, 5.5]},
{"name": "GND", "pins": ["U1.4", "U1.29", "LED5.2", "…"], "v": [0, 0]},
"pin_locks": {"U1.9": "LED_G1", "…": "…"}
```

A sketch with the same meaning:

```text
part R4   resistor 330Ω 0805  lcsc C17630
part LED5 led XL-504UGD       lcsc C2895549  no-bom   # 5 mm, green, countdown step 1

# step 1: D6 → 330 Ω → green LED → GND
net LED_G1    0..5.5 V  U1.PD6 R4.1  locked
net LED_G1_A  0..5.5 V  R4.2 LED5.anode
net GND       0 V       U1.GND LED5.cathode …
```

**What it costs:** a parser, a formatter and a translator into the JSON, error messages with line numbers, and a
handbook chapter Claude reads in every session. Tools that write the graph today (`edakit block add`, skill own-part)
then write the language. Touchstone: both projects translate there and back without a difference.

**A smaller step with most of the gain:** address pins in today's graph by name or role (`U1.PD6`, `LED5.anode`) and
use TOML instead of JSON for the comments. That needs no parser.

**Models:** atopile with a language of its own, SKiDL in Python. What counts for edakit is that the language maps the
graph exactly – voltage ranges, waivers with their reason, the hand-over to the layout, the purpose – so every check
stays.

Decided: first write the whole Christmas bell down both ways, as a language and as TOML with names, then choose which
to build (decision 8).

The sketch is [circuit-language.md](../new/circuit-language.md): the bell both ways, a translator that takes all four
configurations there and back without a difference, what each form costs, and the decisions to take. Reviewed on
2026-10-31: the gains are independent of a language of its own and are built in any case – pins by name or role, the
pin map from the parts entry, the hash rule, `edakit graph json` –; the language is deferred until it offers what a
format cannot, which its section "Review 2026-10-31" spells out. Decided the same day: TOML with names as the form,
`hardware/graph.toml`, with the resolved `graph.json` generated beside it (its decisions 1–7); what both forms share
has a plan of its own, [circuit-language-plan.md](../new/circuit-language-plan.md).

## Order

First the small things, then gap 2, the language last. Each step is useful on its own.

1. **README** with the open points under "Status and limits" – small, now.
2. **Gap 1:** write the positions back and check "every part in the plan" – small; trying it needs EasyEDA.
3. **The remaining order settings** and **single designators** – small each, without EasyEDA.
4. **Rule set of EasyEDA's DRC** – small to medium; first find out what the API carries.
5. **Gap 2:** footprints as data – medium.
6. **Language:** first the sketch of the whole bell, then the decision, then building it – medium to large.

A fixed layer change in `fixed_wires` comes when a project needs one.

## Decisions

All taken on 2026-10-28, 7 by #40. "Accepted" is the user's yes to the recommendation; "decided by Claude" marks a
technical point the user left to Claude and then confirmed.

| # | Question | Decision | Status |
| --- | --- | --- | --- |
| 1 | Name in the README | "circuit design as code" | accepted |
| 2 | README now with its limits, or only after the gaps | now, with its limits | accepted |
| 3 | Gap 1: where the positions go | into `[place]` of the board file, marked `auto = true` like the rows of `pcb place` | the user's choice; a file of their own beside the board file (`<b>.auto.toml`) was weighed and not taken |
| 4 | Gap 1: check "every part in the plan" | an error in the gate, not only a hint; a board placed before takes over its positions once | accepted |
| 5 | Gap 2: where the footprint data goes | into the parts entry; a change then voids the circuit reviews too – right for M-1, which checks polarity | decided by Claude |
| 6 | Rule set of EasyEDA's DRC | write it if the API carries it; otherwise read and check it | decided by Claude: reading works, net rules can be written (`overwriteNetRules`); step 4 finds out about the whole set |
| 7 | Where the order settings go | `[order]` in the board file (#40); mask and print colour join it | settled by #40 |
| 8 | A language, or TOML with names | first sketch both on the Christmas bell; after the review of 2026-10-31 the language is deferred and the form decided: TOML with names, the resolved JSON beside it (circuit-language.md, decisions 1–7) | accepted |
| 9 | The order settings in the fab hash and the estimate | thickness, colours, finish and mark count in the fab hash, the remark does not; `edakit cost` names an order it does not price | the user's choice on 2026-10-28, built as a follow-up of step 1.7 |

## Sources

- edakit at `a8b6011`: [pcb.py](../../../edakit/pcb.py) (`autolayout`, `measure`, `dump`, `auto_place`,
  `write_place_rows`), [part.py](../../../edakit/part.py) (`part import`, `footprint_geometry`),
  [gate.py](../../../edakit/release/gate.py) (`layout_files`), [fab.py](../../../edakit/release/fab.py) (L-3, L-7,
  `fab_layers`), [order_sheet.py](../../../edakit/release/order_sheet.py) (F-6),
  [route.py](../../../edakit/route.py) (`fixed_wires`, `write_dsn`), [config.py](../../../edakit/config.py)
  (`Placement`, board file keys), [schematic.py](../../../edakit/schematic.py) (`easyeda_device`),
  [silk.py](../../../edakit/silk.py), skills [own-part](../../../skills/own-part/SKILL.md) and
  [pcb-round](../../../skills/pcb-round/SKILL.md), handbook [4](../../../handbook/04-parts-database.md) (`lead`,
  `body`, `mate`), [7](../../../handbook/07-pcb.md), [8](../../../handbook/08-release-gate.md) (8.2 hashes),
  [9](../../../handbook/09-easyeda-api.md), [10](../../../handbook/10-reference.md),
  [12](../../../handbook/12-troubleshooting.md).
- The Christmas bell: `hardware/graph.json`, `hardware/parts/C2895549.json`,
  `variants/esp32/hardware/lib/tdisplay_device.py`.
- The reference project: `hardware/README.md`, `hardware/easyeda/led_footprints.py`,
  `hardware/easyeda/bahnen_hinten.py`, `docs/bestellung/`.
