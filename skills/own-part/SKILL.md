---
name: own-part
description: Create the parts entry of a part nobody sells and no edakit project describes – a board of your own (perfboard, an older PCB), a part from the bin that is no longer made, something made by hand – with pins, supply range and current from the user's documents or from measurement, every value with its source, and the sign-off against those notes. Use when a part has no LCSC or manufacturer number to search for, P-1 reports a missing entry for it, or the user calls it self-made, from the drawer, salvaged or hand-wound. A board designed with edakit does not need it: edakit part datasheet in its project, edakit part own here (handbook 4.5).
argument-hint: "<the part: what it is and where it comes from>"
---

# An own part without a datasheet

Wanted: $ARGUMENTS. Fields of an entry: `${CLAUDE_PLUGIN_ROOT}/handbook/04-parts-database.md` (4.1, 4.5).

## 0. Which way

- It has an edakit project (an edakit.toml)? Not this skill: `edakit part datasheet --connector …` in that project,
  `edakit part own <path>` here – the entry then comes from its graph and simulation (handbook 4.5).
- Still made, only not at the project's distributors? Skill part-search, with another distributor.
- Otherwise this skill: the user is the datasheet.

## 1. Ask once

One round of questions (skill decision-round), with what is already known filled in:

1. What it is and where it comes from: own board (perfboard, an older PCB), from the bin (marking, photo), made by
   hand.
2. Its connections, pin by pin: the number as on its connector or pads, a name, what the pin does – supply in, supply
   out, ground, signal in, signal out, I2C.
3. Supply: the voltage it needs (from … to), the current it draws – idle and at most –, what it gives out.
4. Signals: their level (3.3 V, 5 V), pull resistors on the part, what drives what.
5. Documents: a schematic, photos, notes of the project it came from.

Nothing is filled in by guessing: what the user does not know is measured (2) or written as "assumption: …" with the
reason.

## 2. Measure what is open

Short instructions for the user, each with the range to expect and what the result decides:

- current: multimeter in series in the supply line, idle and in the heaviest function (all LEDs on, radio sending,
  motor starting)
- supply range: the lowest and the highest voltage at which it still works (lab supply, slowly)
- pull resistors: resistance from the pin to the supply pin and to ground, unpowered
- output level: an output's high level with its load

Each result with date, instrument and conditions – they become `sources`.

## 3. The entry

`hardware/parts/<name>.json`, the name short and stable – the component names it in `part`:

- `mpn` = the name, `manufacturer` ("own" or who made it), `kind` (`module` for a board), and
  `own`: `{"what": "pcb" | "bin" | "handmade", "notes": "where it comes from"}` – P-3 knows these three
- `pins`: `name`, `type`, `role`, `vmax`, `pull`/`pull_ohm` (handbook 4.1 – the types decide G-3 to G-6, G-11, G-12)
- `params`: behaviour `current` with `i_a`, the largest measured current – the simulation draws it from the supply
  pin
- `ratings`: `vin_min`, `vin_max` – the measured or documented supply range; E-3 holds the host to it
- `compliance`: what is known of its parts; of an own board whose parts nobody knows, `"rohs": "not known"` – the
  regulatory review reports it as open (handbook 15)
- `sources`: every value with its origin – "measured 2026-11-02, multimeter UT61E, all LEDs on: 182 mA", "from the
  schematic of …", "assumption: …"
- `verified`: only after the user checked the entry against the notes – `by`, `date`, `datasheet` ("measurement
  notes of <date>" or the document), `checked`, `open`

## 4. Into the graph

The component: `"part": "<name>"`, `"bom": false`, the pins as in the entry, and an `easyeda_device` – a symbol with
these pin names and a footprint from the user's EasyEDA library. Then `edakit check` (P-1, P-3, G-9) and
`edakit sim`. A part on a cable is not on the host's PCB: its connector gets the current as an `external` load
instead (handbook 5.1).

## 5. Record

In the project's decision log: what the part is, where its values come from, what is still an assumption.
