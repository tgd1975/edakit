# Parts on hand: the maker's inventory, and only the rest ordered

Status 2026-11-03: decided and built – steps 1 and 2 in edakit (`edakit/inventory.py`, `edakit order`, `edakit
inventory`, handbook 8.4 and 10.1); left is step 3, the live run against the owner's inventory, in `TODO.md`. Rewritten
on the owner's word the same day – "wir beginnen KISS": one document with a table of fixed columns, in whatever format
the maker keeps it, named in `edakit.local.toml`, read and never written – and decided in a decision round (decisions 9
to 19). The first version of 2026-11-02 (PartsLedger as the source, a match by sibling and kit, the way back to
PartsLedger, the survey of other tools) is in this file's history; its decisions are at the end, marked where the
rewrite replaces them.

## Why

edakit buys every part it does not have assembled. A part soldered by hand (`bom: false`), an item off the board
(`[[extra]]`), every part of a bought or hand-wired board: `edakit order` writes a cart line for each, need plus spares,
rounded up to the supplier's minimum and pack size (handbook 8.4). What lies in the maker's drawer is not asked. On
2026-11-02 the owner's first LCSC order went out that way – 26 lines of through-hole parts, LEDs, resistors and
headers (`docs/concepts/done/parts-order.md`) – and nothing checked a single line against what was at home.

By the yardstick (`docs/concepts/done/design-as-text.md`), what the maker has lives in their head or in a file edakit
does not know. Two words to keep apart: **stock** is what the assembler has (`edakit stock`, PARTS.stock, JLCPCB's
catalogue); the maker's own parts are **on hand**, listed in the **inventory**.

## The inventory: one table, any format

The inventory is a document with a table of named columns. edakit reads these formats, by the file's extension:

| Format | Which tables count | Read with |
| --- | --- | --- |
| `.md` | every pipe table whose header row has the required columns | edakit's own parser; a cell's link text counts (`[NE555N](parts/ne555n.md)` is `NE555N`) |
| `.html`, `.htm` | every `<table>` whose first row has the required columns | the standard library's `html.parser` |
| `.csv` | the file is the table | the standard library; `,`, `;` or tab, UTF-8 with or without BOM – what Excel and LibreOffice write |
| `.xlsx` | every sheet whose first non-empty row has the required columns | openpyxl, a dependency already (EasyEDA's pick-and-place file) |
| `.ods` | the same, OpenDocument Spreadsheet – LibreOffice Calc's format | `zipfile` and `xml.etree` of the standard library, no new dependency |

Every other table, sheet and column is ignored – a sheet of notes, a column "Fach" or "Bestellt am" bothers nobody.
Column names are compared without case and surrounding blanks.

The columns, by their default names:

| Column | Content | Needed by edakit |
| --- | --- | --- |
| `ID` | the maker's name for the row – the part number read off the part (`NE555N`), or anything (`R-330-THT`) | **required** |
| `Quantity` | pieces on hand, a whole number ≥ 0 | **required** |
| `LCSC` | the LCSC number (`C439782`) | optional – the first key of the match |
| `Name`, `Description`, `Link` | for the maker; edakit shows them in its report | optional |

A row is a part when it matches a parts entry of the project, in this order:

1. **By LCSC number** – from the row's `LCSC` column, else from the LCSC map by the row's `ID` (below) – equal to the
   entry's `lcsc`.
2. **By part number** – the row's `ID` equal to the entry's `mpn`, case and blanks ignored, the comparison PARTS.stock
   makes against JLCPCB's MPN.

Nothing else: no family siblings, no kits by value, no guess from the description. A resistor assortment counts only
where the maker gives its rows an LCSC number or an MPN – their statement that this is the part. The same part in
several rows, tables, sheets or files is summed: parts of one type may lie in more than one place.

**The LCSC map.** Who does not want an `LCSC` column in their inventory keeps a second table beside it, with the
columns `ID` and `LCSC`, in any of the formats above. The inventory stays untouched; the map translates its IDs. An ID
mapped to two LCSC numbers is an error.

## Where it is named: `edakit.local.toml`

The inventory is the maker's and private – it belongs in no project's repository, and nobody else's checkout has it.
Its paths go into `edakit.local.toml` beside `edakit.toml`, a file of this checkout that git ignores – as Claude
Code's `settings.local.json` –, never into `edakit.toml` itself:

```toml
# edakit.local.toml – this checkout's, in .gitignore
[inventory]
files = [                                    # the parts on hand; edakit order takes from them (8.4)
  "~/Dokumente/Teile/inventory.xlsx",
  "~/Dokumente/Teile/inventory_*.md",        # a glob: every file it matches
]
lcsc_map = "~/Dokumente/Teile/lcsc.csv"      # optional: ID → LCSC, the inventory left as it is

[inventory.columns]                          # optional: the maker's own column names
id = "Teil"
quantity = "Anzahl"
lcsc = "LCSC-Nr."
```

`files` is one path or a list of paths and globs, formats mixed: an inventory split into `inventory_ics.md` and
`inventory_leds.md` is two entries or one glob – the hierarchy named explicitly, no link followed, so no question what
is part of it and what a link outward (decision 18). The column map lies beside the paths, since it describes the same
local files. `~` and relative paths are resolved against the project's folder.

The file is per checkout: each project names its inventory once, and a second machine has its own. `edakit inventory
template` adds `edakit.local.toml` to the project's `.gitignore`, as the skill new-project does for a new project;
`edakit order` and `edakit inventory` say in a note when git tracks the file after all.

**What happens:**

| Settings | edakit does |
| --- | --- |
| no `edakit.local.toml`, or no `[inventory]` in it | nothing changes anywhere – the whole concept is opt-in; CI and another maker's machine never see it |
| a path, no such file; a glob that matches nothing | error, stop: `inventory: ~/Dokumente/Teile/inventory.xlsx not found (edakit.local.toml)` |
| a file without a matching table, each file on its own | error, stop: the required columns, and the headers it found per table or sheet |
| a quantity that is no whole number (`~10`, `ein paar`, empty) | error, stop: file, table or sheet, row |
| an extension edakit cannot read | error, stop, naming the formats it reads |

An error stops `edakit order` before it writes a cart: an order computed past a broken inventory would be the wrong
one.

## What edakit does with it

**It checks, it does not book.** edakit reads the inventory and compares; it never lowers a quantity when it orders.
What really leaves the drawer is decided at the bench – a part lost, a value changed, a board not built after all.
No reservation, no look-ahead stock keeping: two orders a week apart may count the same five pieces, and the maker sees
it at the drawer.

- **`edakit order`** – for every cart line that needs `n` pieces (need plus spares, as today) with `h` on hand: `min(h,
  n)` come from the inventory and the rest is ordered, rounded to `moq` and `step` as before; a rest of 0 writes no
  cart line. The line's comment says so: `C1 (5 + 0, 3 on hand)`. `hand_assembly.md` gets a column "From" per part –
  `on hand`, `cart` or `on hand + cart` – and at its end the list "Out of the drawer": each inventory row, its place
  and the pieces to take before soldering. A basket across projects (`--with`) sums the lines first and applies the
  inventory of the project it runs in once.
- **`edakit inventory`** – for the current project every hand-soldered part and extra against the inventory: needed,
  on hand, short; the inventory's paths and their file dates first. `edakit inventory QUERY` lists the rows
  whose ID, name or description match – for the maker and for the agent.
- **`edakit inventory template FILE`** – a new empty inventory: the header row with the columns as the settings name
  them (the defaults without a column map), as `.md`, `.xlsx` or `.ods`; it never overwrites a file, writes the path
  into `edakit.local.toml` when that names none yet, and adds the file to `.gitignore`.

The inventory does not count for an assembled position: JLCPCB places from LCSC's stock, not from the maker's drawer.

## What stays as it is

- `edakit stock`, PARTS.stock and the snapshot are the assembler's; the inventory never answers for an assembled part.
- PARTS.supplier: a hand-soldered part without a supplier still warns – the inventory is a place to take from, not a
  place to buy; a part nobody sells any more gets its entry with the skill own-part (`own.what = "bin"`, handbook 4.5).
- No new check code: `edakit order` and `edakit inventory` report; the gate's stage P stays as it is.
- The regulatory review: a part from the drawer has its compliance data from its entry like every part (`"rohs": "not
  known"` for one of unknown origin, handbook 15 – support, not legal advice).
- `spare_pct` and `spare` are counted into the need before the inventory is applied.

## By the yardstick

Before: what the drawer holds is in the maker's head. After: it is a table in a file of the maker's – text or a
spreadsheet, outside every project on purpose, since it is private and outlives any of them. The project gains nothing
that exists only in EasyEDA; what an order took from the drawer is in `hand_assembly.md` of its run. What stays by hand
is the maker's own: keeping the table true.

## Risks

- **The inventory lies** – a part used without lowering its count: the cart is short by that part. Then one small
  order more, days not weeks; `hand_assembly.md` names what to take, so the gap shows at the drawer, not at the bench.
- **A wrong LCSC number in the map** – the maker's 1/8 W resistor counted as the graph's 1/4 W one. The maker's
  statement, as any entry they write; `edakit inventory` shows the row's name and description beside the match, so a
  look catches it.

## Order of work

Each step on the owner's word; 1 and 2 built on 2026-11-03.

1. **Reading and the order** (built): `edakit.local.toml`, a reader `edakit/inventory.py` for the five formats and
   the LCSC map, the match, the errors, `edakit order` and `hand_assembly.md`, `edakit inventory`; a fixture per
   format, tests for each match rule and each error; handbook 8.4, 10.1, the glossary ("Inventory", "On hand"); a
   fragment `patch` – no project must act.
2. **The template** (built): `edakit inventory template` for `.md`, `.xlsx`, `.ods`.
3. **A live run**: the next parts order against the owner's inventory – the carts shortened, `hand_assembly.md` naming
   what to take; what the run finds goes into handbook 8.4.

**Later, each on its own word:**

- **Lowering on command** – `edakit inventory take`: a command of its own, never part of ordering, that lowers the
  quantities by what a run's `hand_assembly.md` took. The hard part is the write: a cell changed in place in `.md`,
  `.html`, `.xlsx` and `.ods` without touching the rest, and which row gives when the part lies in several.
- **The choice** – part-search, part-selector and circuit-design look into the inventory first for a hand-soldered
  position, with `edakit inventory QUERY`.
- **Other sources** – PartsLedger, InvenTree, Part-DB, Binner, PartsBox (surveyed in the first version, this file's
  history). PartsLedger's `INVENTORY.md` is read today as any markdown inventory with a column map (`id = "Part"`,
  `quantity = "Qty"`); how it would write the inventory itself – a part in several places, what is a replacement and
  what an increase – is PartsLedger's question, open. Its name (decision 6) goes with it.

## Decisions

Taken by the owner on 2026-11-02 in a decision round (TD-99) – 1 to 8 – and by the owner's rewrite of 2026-11-03 – 9
on.

1. **Scope: the order and the choice, "edakit ist Konsument".** Holds: edakit reads, the way back to PartsLedger is
   dropped. The choice is a later step since 2026-11-03; lowering on command a later option of its own.
2. ~~`[project] bin` with a path; missing on a machine, a note and the full carts.~~ Replaced 2026-11-03: the path in
   a local settings file; set and missing is an error.
3. **Up to need plus spares** come from the inventory: `min(h, n)`, the rest ordered.
4. ~~Siblings listed, never counted; kits counted once they are data.~~ Replaced 2026-11-03: the match by LCSC
   number and MPN only.
5. – (dropped by 1)
6. **The name: open** – PartsLedger's, with PartsLedger out of this concept.
7. – (dropped by 1)
8. ~~Profiles `partsledger`, `csv` and `xlsx`.~~ Replaced 2026-11-03: the formats `.md`, `.html`, `.csv`, `.xlsx`,
   `.ods`, no profile per tool.
9. **KISS: one document, a table of fixed columns**, in `.md`, `.html`, `.csv`, `.xlsx` or `.ods`; in a workbook every
   sheet, in a page every table with the right column names; other columns ignored; the column names mappable.
10. **The word is inventory** – the internationally plainest; "bin" goes.
11. **Check, never book**: edakit compares and lowers nothing; lowering only as a command of its own, later.
12. **Local settings**: the inventory's path in a file in no repository. Not set, ignored; set and missing, or without
    a matching table, an error that stops.
13. **An LCSC map** beside the inventory as the alternative to an `LCSC` column, the inventory left untouched.
14. **A template** for `.md`, `.xlsx` and `.ods`.
15. **Later**: lowering on command, PartsLedger and other inventory tools.
16. **`edakit.local.toml` per project**, beside `edakit.toml` and in `.gitignore` – not a file per machine.
17. **Required: `ID` and `Quantity`**; the match by the `LCSC` column, else the LCSC map, else `ID` as the MPN.
18. **Several files as a list of paths and globs** in `edakit.local.toml`, with step 1 – no link followed.
19. **`edakit order` shortens the cart** by what is on hand, `min(h, n)`; the inventory itself stays as it is.

Set by Claude and confirmed the same day: the default column names in English, compared without case; the LCSC map a
table with `ID` and `LCSC` in any of the five formats; one part in several rows or files summed; a quantity that is
no whole number an error that stops; the match by LCSC number or `ID` as the MPN and nothing else; the template
writing `edakit.local.toml` and `.gitignore`, a note when git tracks the file; the choice a later step.
