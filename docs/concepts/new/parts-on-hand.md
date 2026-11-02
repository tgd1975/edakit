# Parts on hand: the maker's bin as a source of parts, and only the rest ordered

Status 2026-11-02: concept, asked for by the owner the same day – PartsLedger (github.com/tgd1975/PartsLedger) "is
far from finished, but would be a fine complement to edakit: makers keep many parts at home and want to use those
when they solder a board themselves, and order only the difference; a concept for how that goes – optionally – into
the parts choice, what PartsLedger would have to be able to do, and whether it should get another, easier name".
PartsLedger read at its commit a7e9363 (2026-05-14). Nothing decided, nothing built: the decisions at the end wait
for a decision round in Claude Code's form, and every step starts on the owner's word.

## Why

edakit buys every part it does not have assembled. A part soldered by hand (`bom: false`), an item off the board
(`[[extra]]`), every part of a bought or hand-wired board: `edakit order` writes a cart line for each, need plus spares,
rounded up to the supplier's minimum and pack size (handbook 8.4). What lies in the maker's drawer is not asked. On
2026-11-02 the owner's first LCSC order went out that way – 26 lines of through-hole parts, LEDs, resistors and
headers for the tree and two bell variants (parts-order.md) – and nothing checked a single line against the bin.

The bell's variant `tht` shows the case: five bare boards, no assembly, 19 parts and two sockets per set soldered by
hand, every one of them in the carts. The owner's inventory in PartsLedger lists an electrolytic assortment with
five 1000 µF 16 V and a resistor set with 330 Ω and 4.7 kΩ. C1's five could have come from the drawer; the resistors
not – the graph wants 1/4 W metal film, the kit holds 1/8 W carbon film –, and nothing today can tell the two apart.

The other direction is as blind. An order's surplus – the spares, the rounding to a minimum (LCSC's BOM tool made 50
of 10 × 100 Ω on 2026-11-02), the reserve pytree added by hand – goes into the drawer and nobody writes it down, so
the next project orders the same LEDs again. PartsLedger exists for exactly that record, but has no input from edakit.

By the yardstick (`docs/concepts/done/design-as-text.md`), what the maker has and what an order left over live only in
someone's head today. Two words to keep apart from the start: **stock** is what the assembler has (`edakit stock`,
PARTS.stock, `hardware/stock.json`, JLCPCB's catalogue); the maker's own parts are **on hand**, in the **bin**.

## PartsLedger today

An inventory of a maker's parts bin as text, in its own repository, read on 2026-11-02:

- `inventory/INVENTORY.md`, one sectioned table (`Part | Qty | Description | Datasheet | Octopart | Source | Notes`)
  per class the maker chooses – MCUs, ICs, transistors, sensors, modules –, rows keyed by the part number as it is
  read off the part (`TL082CP`, `NE555N`), inserted alphabetically; `Source` says who wrote the row (`manual`,
  `camera`, open to other tokens); a doubt goes into `Notes` as a hedge ("likely LM358"), never into a third state.
- `inventory/parts/<id>.md`, optional prose pages for a hobbyist – what the part is, pinout, gotchas –, deliberately
  not machine-readable; family pages for marking variants (`TL082CF` and `TL082CP`), found by a heuristic on the
  part number (`partsledger.inventory.family`).
- "Bulk / kits": assortments recorded loose – "E12 set, about 10 pieces a value", "electrolytic assortment, 5 a value"
  – as headings and free tables, on purpose not catalogued per value.
- A Python package `partsledger` with one writer for the index (`inventory.writer.upsert_row(part_id, qty_delta,
  source=…)`: atomic, idempotent, linted before every write), a lint, the family heuristic, and a camera capture
  (viewfinder, no recognition yet); the skills `/inventory-add <part> <qty>` and `/inventory-page`. The camera path –
  DINOv2, a vision model, Nexar – is planned; its scope is through-hole parts, modules and DIP ICs, SMD marking codes
  are out. The skill path has no such limit: a reel's label says what it is.
- Its reader was to be CircuitSmith (`--prefer-inventory`: prefer parts the maker owns; a BOM with needed, in stock,
  to order). CircuitSmith is archived and its ideas went into edakit (handbook 14.6, maker-coverage.md), so that
  adapter has no reader. edakit is the reader now, and this concept is that adapter's place.
- Last commit 2026-05-14, concept stage, not on PyPI. What this concept needs of it – the index as a table – exists
  and works; the camera is not needed for any of it.

## Where the bin meets edakit

Three movements, in the order they pay off.

### 1. The order: only the rest

`edakit order` reads the bin and shortens every cart line by what is on hand: for a line that needs `n` pieces – need
plus spares as today – with `h` on hand, `min(h, n)` come from the bin and the rest is ordered, rounded to `moq` and
`step` as before; a rest of 0 writes no cart line. The comment of the line says so: `C1 (5 + 0, 5 from the bin)`.
`hand_assembly.md` gets a column "From" per part – `bin: 5` or `cart: 5` or both – and a list at the end, what to
take out of the drawer before the soldering starts. A basket across projects (`--with`, parts-order.md decision 1)
sums the lines first and applies the bin once, so two projects never take the same five pieces.

Nothing else changes: the assembler's BOM, PARTS.supplier, `edakit cost` (it prices the carts as written – the bin
parts cost nothing more), the LCSC cart of the skill cart (parts-order.md step 2 uploads the shortened file).

### 2. The choice: a part on hand first

For a part that is soldered by hand, or on a board without an assembly side, the bin is the first place to look. The
agent part-selector and the skill part-search list a candidate that is on hand with its count and the inventory's date
("on hand: 3, bin of 2026-11-02") and recommend it when it meets the requirement; the frame of part-search holds as it
is – a part in stock beats a better one that is not, and for a position JLCPCB assembles a part of its library beats
one from elsewhere; the bin does not count for an assembled position, JLCPCB places from LCSC's stock. The skill
circuit-design gets one line in its section 3: prefer parts on hand for hand-soldered positions.

`edakit bin` prints, for the current project, every hand-soldered part and extra against the bin – on hand, needed, to
order, and the "maybe" rows below –; `edakit bin QUERY` lists the rows whose part number or description match, for the
agent. Both name the bin's path and date; "a few" is not information here either (4.2).

A bin part that no distributor sells any more gets its entry as today: with the skill own-part (`own.what = "bin"`,
handbook 4.5), the row's datasheet link saving the search. One sold at LCSC gets it with `edakit part import`; the bin
only says that the drawer has it.

### 3. The way back: what was taken, what is left over

`edakit order` writes two more files beside the carts (their columns in the appendix):

- `from_bin.csv` – what the project takes out of the drawer: the row's part number as the bin spells it, the pieces,
  the project and the designators.
- `surplus.csv` – what the order brings in beyond the need: cart pieces minus need per line, with the entry's part
  number, manufacturer, LCSC number, package, kind, a description and the datasheet's address – everything a bin row
  needs, from the parts entry that was signed off already.

The booking is PartsLedger's: `partsledger take order/from_bin.csv` when the parts leave the drawer, `partsledger
import order/surplus.csv` when the order has arrived and the boards are soldered – the maker corrects the surplus by
what the assembly used up (a spare LED that was lost) before importing. Both on the maker's word, at the bench; edakit
writes no line of `INVENTORY.md`, PartsLedger imports no code of edakit: files between the two tools, the rule
PartsLedger set for itself with CircuitSmith kept both ways. The order record `hardware/orders/<date>-…json` (8.4)
gets the two lists, so the project keeps what it took and what it put back even when the run folder is gone.

## The match: which row is which part

A cart line knows its parts entry: `lcsc`, `mpn`, `manufacturer`, `kind`, `package`, the values and limits. A bin row
has a part number, a quantity, free text. The rules, in this order:

1. **By LCSC number** where the row carries one – `lcsc C439782` as a token in `Notes` (or a column, PartsLedger's
   choice, requirement 2). A row PartsLedger imported from `surplus.csv` always has it.
2. **By part number**: the row's `Part` text (the link text where the cell links a page) equals the entry's `mpn`, case
   and blanks ignored – the comparison PARTS.stock makes against JLCPCB's MPN. The package rides in the part number
   (`NE555P` is the DIP), so a match by MPN is a match of the package too.
3. **Family siblings** – `NE555P` for `NE555N`, `TL082CF` for `TL082CP`, by PartsLedger's own heuristic – are listed
   as "maybe in the bin", never counted: a suffix may hide another package or grade, and the maker decides at the
   drawer.
4. **Hedged rows** – `Notes` with one of the doubt phrases PartsLedger's lint knows ("likely", "?", "to confirm") –
   are listed as maybe too, until the maker edits the row.
5. **Kits** count once PartsLedger records them as data (requirement 3): kind, package, rating and value per row –
   `resistor, THT axial, 0.125 W, 330 Ω, ~10`. The match is on kind, package, the value within the entry's tolerance,
   and a rating at least the entry's (`p_max_w`, `v_max_v`); "about 10" is taken as 10 and marked estimated in
   `hand_assembly.md`. Without the data a kit is a note in `edakit bin` and nothing is subtracted.

What does not match is ordered as today. The safe side is always the full cart: a bin that is not there, a file that
does not parse, a row without a quantity shortens nothing and `edakit order` says why in one line.

## Where the bin is named

The bin is the maker's, not the project's: one inventory for all projects, outliving any of them. The project names
where it lies, as `edakit part own ../board` names a sibling repository (4.5):

```toml
[project]
bin = "../PartsLedger/inventory/INVENTORY.md"   # the maker's parts on hand; edakit order takes from it (8.4)
```

Relative to edakit.toml, or absolute. Without the key nothing changes anywhere – the whole concept is opt-in, as the
owner asked. With the key and no such file on this machine (another computer, CI) `edakit order` writes the full carts
and says so in a note, as SYNC.source does for a board whose project is not there. A split inventory (PartsLedger's
stage 3, one file per section) is read as PartsLedger plans it: every `inventory/*.md` but the master.

## What PartsLedger must offer

What edakit reads and writes, as requirements on PartsLedger – they go into its repository on the owner's word, as an
idea in its own task system, from a session there; none is built from here.

1. **The index as the contract.** The table with `Part` and `Qty` stays the shape edakit reads – a column edakit
   cannot find is the error, as PartsLedger prefers shape detection over a schema version. A quantity is a number in
   its row: "qty 1 of each unless noted" in prose above a table is not readable.
2. **A supplier code per row.** A place for `lcsc C439782` – a token in `Notes` is enough today, a column `Codes`
   tomorrow – written by the import and read before the part number.
3. **Kits as data.** An assortment as a table with kind, package, rating, value and pieces per value, under its
   heading in "Bulk / kits"; "~10" allowed and read as an estimate. Today's headings and free tables stay for the eye.
4. **`partsledger take FILE`.** Books out what `from_bin.csv` lists through the one writer (`upsert_row(part, -n,
   source="edakit")`); a row that is not there or would go below zero stops the file, nothing half booked – a take is
   not an undo, where the writer today lets a negative quantity pass.
5. **`partsledger import FILE`.** Books in what `surplus.csv` lists: a new row with `Source: edakit`, the LCSC token,
   description, datasheet and manufacturer from the file, placed in a section by kind (the maker's own headings, a
   map kind → section in PartsLedger), with the family check `/inventory-add` makes; an existing row gets its quantity
   bumped. SMD rows are rows like any other – the through-hole assumption of `/inventory-add` is the skill's, not the
   index's.
6. **Nothing to install for edakit.** edakit reads a file; the maker runs PartsLedger's commands in its checkout
   (`uv run partsledger …`). No package on PyPI needed, no import in either direction.

Not needed by edakit: the camera path, Nexar enrichment, the prose pages. The index alone carries the concept.

## What stays as it is

- `edakit stock`, PARTS.stock and the snapshot are the assembler's; the bin never answers for an assembled part.
- PARTS.supplier: a hand-soldered part without a supplier still warns – the bin is a place to take from, not a place
  to buy; a part the drawer has and nobody sells gets `own.what = "bin"` and the warning goes.
- No new check code. `edakit order` and `edakit bin` report; the gate's stage P stays as it is.
- The regulatory review: a bin part's compliance data come from its entry like every part's (`"rohs": "not known"`
  for a part of unknown origin, handbook 15 – support, not legal advice).
- The spares: `spare_pct` and `spare` are counted into the need before the bin is applied (decision 3).

## Why not inside edakit

A `hardware/bin.toml` per project would be the wrong place: the bin is one for all projects and lives longer than any
of them, and its upkeep – identifying a part, finding its datasheet, counting, one day the camera – is not a
circuit's job. PartsLedger has the writer, the lint and the skills for that, and git as the history of every
movement. edakit reads it as it reads a distributor's catalogue: a source it does not own.

## By the yardstick

Today: what the drawer holds and what an order left over are in the maker's head. After: the bin is text in
PartsLedger's repository, what a project took and put back is text in the project (`from_bin.csv`, `surplus.csv`, the
order record), nothing of it in EasyEDA. What stays by hand is the maker's own: taking the parts out of the drawer and
saying so to PartsLedger with its two commands.

## Risks

- **The bin lies** – a part taken without booking, a wrong count: the cart is short by that part. Rare once the take
  goes through PartsLedger; then one more small order or a part from a distributor, days not weeks. `hand_assembly.md`
  names what to take, so the gap shows at the drawer, not at the bench.
- **A sibling taken for the part** – excluded by rule 3: siblings are never counted.
- **A kit's package or rating wrong** – excluded by rule 5: a kit without the data is not counted at all.

## The name

"Ledger" is a bookkeeper's word; a maker says drawer, bin, box. The repository is `PartsLedger`, the package
`partsledger`, the environment prefix `PL_` – and nothing of it is published yet, so a rename costs an afternoon now
and more every month later. Checked on 2026-11-02 (PyPI by its JSON API, GitHub by name):

| Name | PyPI | GitHub | Says |
| --- | --- | --- | --- |
| `partbin` | free | four small repositories, none a parts inventory with users | the parts bin – what it is; `partbin add LM358N 5`, `partbin take …`; edakit's `[project] bin` and `edakit bin` read as "the partbin" |
| `partsbin` | free | `tanby-dynamics/partsbin`, "lets hobbyist electrical experimenters keep track of their components" – the same purpose, 5 stars; `markbastian/partsbin`, 30 stars | the same word, taken for the same thing |
| `onhand` | free | – | the purpose, not the thing; generic |
| `binlist` | taken | bank card BIN lists | no |
| `PartsLedger` | – | the owner's | known to the owner; the slogan "keeps the record" |

Recommended: `partbin`, before anything is published – repository, package, prefix (`PB_`); GitHub forwards the old
name. edakit's words follow in any case: the bin, parts on hand, never stock.

## Order of work

Each step on the owner's word; the first three in edakit, the fourth in PartsLedger, the fifth live.

1. **The order** (movement 1, the match rules 1 to 4, `[project] bin`, the two files, the order record):
   `edakit/order.py` and a reader `edakit/bin.py`, a fixture inventory in the shape of the owner's, tests for each
   rule and for a missing file; handbook 8.4, 10.1 and 3.1 (`supplier`'s neighbour), the glossary ("Bin",
   "On hand"); a fragment `patch` – no project must act.
2. **The choice** (movement 2): `edakit bin`, one paragraph each in part-search, part-selector and circuit-design.
3. **Kits** (rule 5) – after PartsLedger has the table shape of requirement 3.
4. **PartsLedger**: requirements 2 to 5 – `take` and `import` against the two files as the appendix fixes them, the
   kit table, the LCSC token –, and the rename if decided; an idea in its task system, written by a session there.
5. **A live run**: the bell's `tht` variant or the next parts order (parts-order.md step 2) against the owner's bin –
   the carts shortened, the take booked, the surplus imported; what the run finds goes into handbook 8.4.

## Decisions to take

The owner's, with the recommendation first; what Claude set itself is one closing question.

1. **Scope.** All three movements, in the order above – recommended; or the order alone (1), the choice and the way
   back later; or nothing of it.
2. **Where the bin is named.** `[project] bin` with a path, relative or absolute, missing on a machine a note –
   recommended, the project then says that its carts are short on purpose; or an environment variable alone
   (`EDAKIT_BIN`), nothing in the repository; or both, the variable winning.
3. **How much is taken.** Up to need plus spares – recommended, the spares are there to be used up; or the need
   alone and the spares bought; or a reserve kept per row, a `keep` column in PartsLedger – possible later, not now.
4. **Siblings and kits.** Siblings listed, never counted; kits counted once they are data, an estimate marked –
   recommended; or siblings counted when the maker names them equal in the row; or kits never counted.
5. **The way back.** `from_bin.csv` and `surplus.csv` from edakit, `take` and `import` in PartsLedger, on the maker's
   word – recommended, no tool writes the other's files; or edakit writes the index through PartsLedger's writer (an
   import of a package that is not published); or nothing goes back and the maker books with `/inventory-add`.
6. **The name.** `partbin` now – recommended; or `PartsLedger` stays; or another of the table.

Set by Claude, to confirm in one question: the words bin and on hand, stock left to the assembler; the key `bin` under
`[project]`; `edakit bin`; the match order LCSC number, part number, siblings and hedged rows as maybe, kits as data;
the two file names and their columns (appendix); the full cart as the safe side whenever the bin cannot be read; no
new check code; the requirements on PartsLedger carried over by a session there, not from here.

## Appendix: the two files

`from_bin.csv` – one line per bin row the project takes from:

| Column | Content |
| --- | --- |
| `Part` | the row's `Part` text as the bin spells it – PartsLedger finds its row by it |
| `Quantity` | pieces taken, a whole number |
| `Project` | the project's name, in a basket each project its own line |
| `Designators` | the components served, blank for an `[[extra]]` item |

`surplus.csv` – one line per cart line whose pieces exceed the need:

| Column | Content |
| --- | --- |
| `Part` | the entry's `mpn` |
| `Manufacturer` | the entry's `manufacturer` |
| `LCSC` | the LCSC number, blank for a part from another supplier |
| `Quantity` | cart pieces minus need – the maker corrects it by what the assembly used before importing |
| `Description` | the component's `label`, else kind and value |
| `Package` | the entry's `package` |
| `Kind` | the entry's `kind` – PartsLedger's map to its section |
| `Datasheet` | the entry's `datasheet.url`, else the address `edakit part fetch` recorded |
| `Project`, `Order` | the project and the order's date, for the row's `Notes` |
