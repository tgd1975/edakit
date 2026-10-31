---
name: own-part
description: Create the parts entry of a part nobody sells and no edakit project describes – a board of your own (perfboard, an older PCB), a part from the bin that is no longer made, something made by hand – with pins, supply range and current from the user's documents or from measurement, its footprint as data, every value with its source, and the sign-off against those notes. Use when a part has no LCSC or manufacturer number to search for, STRUCT.entry reports a missing entry for it, or the user calls it self-made, from the drawer, salvaged or hand-wound. A board designed with edakit does not need it: edakit part datasheet in its project, edakit part own here (handbook 4.5).
argument-hint: "<the part: what it is and where it comes from>"
---

# An own part without a datasheet

Wanted: $ARGUMENTS. Fields of an entry: `${CLAUDE_PLUGIN_ROOT}/handbook/04-parts-database.md` (4.1, 4.5; the
footprint as data: 4.5, "Own footprints as data").

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
5. Its footprint: how it sits on the board – pin header, pads, holes; pitch, row spacing, hole and pad size, the
   outline, where pin 1 and the polarity are; a drawing or a library footprint that has it already.
6. Documents: a schematic, photos, notes of the project it came from.

Nothing is filled in by guessing: what the user does not know is measured (2) or written as "assumption: …" with the
reason.

## 2. Measure what is open

Short instructions for the user, each with the range to expect and what the result decides:

- current: multimeter in series in the supply line, idle and in the heaviest function (all LEDs on, radio sending,
  motor starting)
- footprint: calliper on the pins – pitch, row spacing, the pin's cross-section (it gives `lead` and the hole, GEO.hole) –
  and on the body's outline; pin 1 and the polarity from a photo
- supply range: the lowest and the highest voltage at which it still works (lab supply, slowly)
- pull resistors: resistance from the pin to the supply pin and to ground, unpowered
- output level: an output's high level with its load

Each result with date, instrument and conditions – they become `sources`.

## 3. The entry

`hardware/parts/<name>.json`, the name short and stable – the component names it in `part`:

- `mpn` = the name, `manufacturer` ("own" or who made it), `kind` (`module` for a board), and
  `own`: `{"what": "pcb" | "bin" | "handmade", "notes": "where it comes from"}` – SYNC.source knows these three
- `pins`: `name`, `type`, `role`, `v_max_v`, `pull`/`pull_ohm` (handbook 4.1 – the types decide LIM.v, LVL and REQ)
- `values`: behaviour `current` with `i_a`, the largest measured current – the simulation draws it from the supply
  pin
- `limits`: `vin_min_v`, `vin_max_v` – the measured or documented supply range; LIM.range holds the host to it
- `compliance`: what is known of its parts; of an own board whose parts nobody knows, `"rohs": "not known"` – the
  regulatory review reports it as open (handbook 15); `radio` with its bands and power when something on it
  transmits, `"none"` when nothing does – a host that uses it as a module asks for one of the two (PARTS.fact)
- `sources`: every value with its origin – "measured 2026-11-02, multimeter UT61E, all LEDs on: 182 mA", "from the
  schematic of …", "assumption: …"
- `verified`: only after the user checked the entry against the notes – `by`, `date`, `datasheet` ("measurement
  notes of <date>" or the document), `checked`, `open`

## 4. The footprint as data

The footprint goes into the entry as `footprint_data` (handbook 4.5), not only into an EasyEDA library: pads with
place, shape, size and hole in mm, the outline, the print with a polarity mark next to the pin of its sign, and for a
board or module `"symbol": "box"` – edakit then builds the symbol from `pins` and `symbol`. Measured values with their
source in `sources`. A footprint the user's EasyEDA library or a library part already has is taken over once the part
is placed and dumped: `edakit part footprint <name> --write`, then completed.

`edakit check` holds the data together (PARTS.footprint: every pad a pin or `"mechanical": true`, every pin a pad, every
through-hole pad its hole, the mark at the right pole). The copy in EasyEDA needs a carrier – a part of the system
library the copy is rebuilt from, ideally with the same pins (a pin header of the same count): its LCSC number in
`lcsc` (with `"bom": false`) or its device in `easyeda_device`. A device created through the API cannot be placed in
the local client; a system part's copy can.

## 5. Into the graph

The component: `"part": "<name>"` (or the carrier's `lcsc`), `"bom": false`, the pins as in the entry, and an
`easyeda_device` – the carrier, or a symbol with these pin names and a footprint from the user's EasyEDA library.
Then `edakit check` (STRUCT.entry, SYNC.source, PARTS.footprint, PARTS.verified) and `edakit sim`, and `edakit part build <name>` shows what the copy will be.
The layout round (skill pcb-round) builds it: `edakit schematic create` places the carrier, `edakit part build <name>
--write` (under the claim) rebuilds its copy from the data, `edakit pcb parts --write` and `edakit pcb dump` bring it
into the PCB, and `edakit check` holds it to the data (SYNC.footprint). A part on a cable is not on the host's PCB: its connector
gets the current as an `external` load instead (handbook 5.1) and needs no footprint.

## 6. Record

In the project's decision log: what the part is, where its values come from, what is still an assumption.
