---
name: part-search
description: Find a part at LCSC/JLCPCB, check stock and assembly, and create its parts-database entry (hardware/parts/<LCSC>.json) with pins, roles, ratings and a datasheet sign-off. Use when a new part is needed, a part must be replaced (stock, variant, package), an LCSC number is mentioned or the graph check reports a missing entry (P-1).
argument-hint: "<part, requirement or LCSC number>"
---

# Find a part and enter it

Wanted: $ARGUMENTS. Fields of an entry: `${CLAUDE_PLUGIN_ROOT}/handbook/04-parts-database.md`.

## Frame

- If the boards are assembled by JLCPCB, a part that must be bought and soldered separately is no option unless the
  user says so. A part in stock beats a "better" one that is not.
- Basic parts first (no feeder fee), extended when needed. When the user declares something a must, keep searching
  instead of switching to an alternative. Where it does not matter to them, decide and give the reason.

## Search

1. `easyeda_schematic_search_device` with `key: "<LCSC number or manufacturer part number>"`. It returns footprint,
   manufacturer number, basic/extended and `otherProperty` (parameters). **Take only hits whose `supplierId` equals the
   LCSC number** – the search is full text (`C5613` also finds `C5613331`). `C99…` numbers are user libraries, not
   orderable. Free text ("led 5mm red") gives mostly noise; manufacturer series names work (handbook 04).
2. Stock and price: `https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=Cxxxx` (stock, price breaks,
   parameters). LCSC's full-text search blocks automated requests (403).
3. Report stock as a number with the date ("1 902 pcs at LCSC, 2026-10-25"), not as "few". JLCPCB's assembly stock
   differs from LCSC's; the release gate checks it (F-2).
4. Datasheet from the LCSC/JLCPCB part page or the manufacturer; note its revision.

## Entry

- `hardware/parts/<LCSC>.json` after the pattern of a similar part: `kind`, `pins` (names identical to the graph,
  `type`, `role`, `vmax`), `params`, `ratings`, `spice` for diodes/transistors, `lead` for through-hole parts,
  `sources` (mark every assumption as "assumption").
- Check against the datasheet: pinout, polarity at the footprint (which pad is pin 1 / anode / +), package, every
  rating. Library footprints are sometimes wrong (a "+" printed at the cathode pad) – the polarity sheet of the gate
  and the second check M-1 exist for that. Then `verified` with by, date, datasheet revision, `checked`, `open`.
- Record the choice in the decision log (alternatives and why they were dropped).

Then `edakit check` (P-1, G-9), and the hardware-change skill if the part goes into the graph.
