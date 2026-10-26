---
name: part-search
description: Find a part at the distributors the project buys from (LCSC/JLCPCB by default; RS, Farnell, Mouser, DigiKey, Reichelt with a profile each), check stock and assembly, and create its parts-database entry (hardware/parts/<LCSC number or manufacturer part number>.json) with pins, roles, ratings, compliance data and a datasheet sign-off. Use when a new part is needed, a part must be replaced (stock, variant, package, distributor), an LCSC or order number is mentioned or the graph check reports a missing entry (P-1). For a search across several distributors use the agent part-selector, which follows this skill in its own context.
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

At every distributor the project buys from – `[project] distributors` in edakit.toml, default `["lcsc"]` – as its
profile says: `${CLAUDE_PLUGIN_ROOT}/skills/part-search/distributors/<name>.md` (`lcsc`, `rs`, `farnell`, `mouser`,
`digikey`, `reichelt`). The profile tells how to search there, what loads without a key and what the page states.

- Report stock as a number with the date ("1 902 pcs at LCSC, 2026-10-25"), not as "few".
- Datasheet from the distributor's part page or the manufacturer; note its revision.
- A part from outside LCSC is hand-soldered (`bom: false`) or goes to another assembler; in EasyEDA it needs a
  footprint – the `easyeda_device` of a part in the same package (handbook 3.1).
- A part nobody sells is no search: a board of an edakit project comes with `edakit part datasheet` in its project
  and `edakit part own <path>` here (handbook 4.5).

## Entry

- `hardware/parts/<LCSC>.json` – from another distributor `hardware/parts/<manufacturer part number>.json` with
  `mpn` set and `order` for the order numbers (`{"rs": "223-0562"}`); the graph names it in `part`. After the
  pattern of a similar part: `kind`, `pins` (names identical to the graph, `type`, `role`, `vmax`), `params`,
  `ratings`, `spice` for diodes/transistors, `lead` for through-hole parts, `sources` (mark every assumption as
  "assumption"). The block library (`edakit/blocks/parts/` of the plugin) has checked entries to copy from.
- What the checks read from the datasheet besides the limits: input-only pins `type: input`; strapping pins
  `"strap": "high"|"low"` with the internal `"pull"` at reset (G-12); built-in pull resistors `"pull": "up"`,
  `"pull_ohm"` (I2C modules, G-11); roles `sda`/`scl` (G-11) and `cc1`/`cc2` on a USB-C receptacle (G-14); MCU output
  current `gpio_i_max_a` per pin and `gpio_i_total_max_a` for all together (E-2); a 0 Ω jumper `value_ohm: 0` with
  its maximum resistance `r_max_ohm` (it joins its nets, handbook 3.3); a pin `hint` or part `hints` for what the
  datasheet warns about (shown by `edakit hints`).
- `compliance` for the regulatory review (M-6, handbook 15): `rohs` (true, false or the exemption), `reach` (the
  supplier's SVHC statement), for a part that transmits `radio` (`bands_mhz`, `max_dbm`, `doc` = URL of the EU
  declaration of conformity), and `source` (page and date). Take it from the distributor's part page or the
  manufacturer's declaration; what nobody states stays out – the reviewer reports it as open, not as fine.
- Check against the datasheet: pinout, polarity at the footprint (which pad is pin 1 / anode / +), package, every
  rating. Library footprints are sometimes wrong (a "+" printed at the cathode pad) – the polarity sheet of the gate
  and the second check M-1 exist for that. Then `verified` with by, date, datasheet revision, `checked`, `open`.
- Record the choice in the decision log (alternatives and why they were dropped).

Then `edakit check` (P-1, G-9), and the hardware-change skill if the part goes into the graph.
