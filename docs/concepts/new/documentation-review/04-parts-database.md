# Documentation review: chapter 4, the parts database (step D.5)

**Status:** condensed in place on branch `claude/amazing-newton-ygty8a`, 2026-11-01, not committed – for the owner's
review. Headings `#`/`##`, section numbers, the file name and the generated `kinds` table are unchanged.

## Measures

Measured with the rules of `tests/test_style.py` (own words: prose without tables, code, generated text and quotes).

| | before (HEAD) | after |
|---|---|---|
| lines | 671 | 776 |
| own words | 7344 | 7569 |
| all words outside code and generated text (tables included) | 11285 | 11478 |
| mean sentence (words) | 32.9 | 28.6 |
| sentences over 35 words | 89 | 85 |
| sections over 80 lines without a subheading | 3 | 0 |
| paragraphs over 120 words | 22 | 0 |
| bare cross-references | 0 | 0 |
| "the user" / "the reference project" | 5 | 0 |
| dates in own sentences | 6 | 0 |
| chapter over 500 lines | yes | yes |

The rules the chapter now meets, each an `XPASS(strict)` in `tests/test_style.py`: `sections`, `paragraphs`, `words`,
`dates`. `chapters` (over 500 lines) is still failing, as expected.

**The third fewer words was not reached, and the chapter got longer.** Why, so that the owner can judge it:

- Every section of the chapter is named from outside, not only 4.1 and 4.5: `handbook 4` (`edakit/part.py:108`,
  `edakit/parts/A000005.json`, `edakit/design.py:17`), 4.1 (25 places), 4.2 (5), 4.3 (6), 4.4 (6), 4.5 (20), 4.6 (1),
  and the skills own-part and part-search open the file. So no statement could leave any section.
- An 8-word overlap scan of the chapter against `edakit/`, `skills/`, `agents/`, `tests/`, `.claude/` and the other
  chapters found about 100 shared phrases – docstrings of `footprint.py`, `part.py`, `pcb.py`, `sim/netlist.py`, the
  catalog's details in `codes.toml` and `kinds.toml`, `skills/part-search`, `skills/own-part`,
  `skills/part-search/distributors/lcsc.md`, `tests/test_bought.py`, `tests/test_hand_wired.py`. Under rule 5 of the
  brief every sentence holding such a phrase was left as written. That is most of the long sentences.
- What is left is a reference of fields whose clauses are qualifications – a key, a unit, a code, a grade, an example
  part. Rule 6 keeps them.
- The lines grew from the structure: the `pins` cell (one table line of about 1100 words) became a table of 20 keys and
  two paragraphs on pin needs; nine `###` headings; long list items split so that none passes 120 words.

## Per section

### Introduction (under the H1) – named as "handbook 4"

- New first paragraph: for whom, what after.
- The file naming became a list of three cases; "characters a file name cannot hold replaced by `_`" (what
  `edakit/part.py:108` cites) and "a part bought from another distributor" (what `A000005.json` cites) kept word for
  word.

### 4.1 Fields – named by code, catalog, skills and agents (25 places, e.g. `codes.toml` 119, 564, 576, 702, 1161,
1168, 1187, 1203, 1216, 1442; `design.py` 110, 226, 351; `schema.py` 207; `engines/struct.py` 284; `sim/netlist.py`
180; `firmware.py` 284; `checks.py` 90; `skills/own-part` 56; `skills/part-search` 53, 69, 74)

- **Field table:** kept, cells unchanged in substance; semicolon chains split into sentences in `lcsc`, `order`,
  `configs`, `matrix`. The `pins` cell now points to the new table.
- **New `### Pin keys`:** the keys of the old `pins` cell, one row each, in their old order; the clauses with shared
  phrases (`clamp`, `windows`, `biased`) word for word. `needs` became two paragraphs, "Pin needs", with every
  `what`, bound, grade, example and `when` of the cell.
- **Pin types, Pin functions:** unchanged (`codes.toml` cites "pin types ground, power_in, power_output").
- **`### Pin roles`:** the bold lead-in became a heading; the table unchanged (the `led_rgb` common-anode rule that
  `sim/netlist.py:180` cites is there).
- **`### Limits and values`:** heading; the sentence before the generated table reworded, the table untouched.
- **What the names do not say:** the 31 items regrouped by topic under three headings – `### Supplies, pins and heat`,
  `### Passive parts and contacts`, `### Transistors and ICs` – each item whole, inside 4.1. Items over 120 words
  split: `vin_rel_max_v` (the IC's limit / a pin's own `v_rel_max_v`), pin limits (voltage / currents and loads),
  contacts (ratings / `min_load_a`), the class-2 ceramic (curve / its use in the checks / `esr_ohm`), the LED strip
  (currents and copper / supply range and library), the transistor spread (BJT and MOSFET / JFET / model and library),
  the charger (`prog_v` / `behavior: "charger"`), the logic IC (`icc_a` / output rest state).
- **`### The parts library`:** heading; split into two paragraphs. "counts once the owner has signed it" became
  "counts once it is signed in edakit" (see assumptions). The citation of `rules-at-scale.md`, decision 8, kept; its
  date went to the history.
- **Audio sources:** the sentence on the capsule's load resistor moved up one paragraph to stay under 120 words.

### 4.2 Finding parts – named by `codes.toml` 1145, 1147, `part.py` 459, `engines/struct.py` 347, `order.py` 71

- First paragraph split in two; the aside "datasheets and distributor pages do not fill the design session" kept.
- "(weeks, fees – the user's decision)" → "– weeks and fees, your decision".
- "What an agent can reach (tried in October 2026)" became a state line above the table, the date kept: the table is
  a dated measurement and its statements depend on it.
- New `### At LCSC and JLCPCB` for the list. Items split: `part search` (exit codes moved into its first item), the
  full-text hint, the three routes; `part import` (what it writes / the cache / the endpoint); `edakit stock` (the
  snapshot / PARTS.stock / without JLCPCB).
- **Merged:** the three `C99…` statements of 4.2 (dropped by `part search`, refused by `part import` because nobody
  sells them though the library returns them, refused by STRUCT.identity in the BOM) into one item. The `C99…` clause
  in the 4.1 `order` row stays in 4.1. `struct.py:347` and `order.py:71` cite 4.2 for "a part of an EasyEDA user
  library – nobody sells it": that statement is in the merged item.
- "which took the reference project some 30 searches" → history.

### 4.3 Signing off a part – named by `codes.toml` 1121, 1129, `part.py` 444, 757, 996, 1043

- Unchanged, but "(8.2)" now names its subject ("hashes and sign-offs, 8.2").

### 4.4 Library footprints are not always right – named by `codes.toml` 703, 883, 891, 1059, 1231, `parts/C5446.json`

- The LED case: "In the reference project …" → "A real project had a 5 mm LED whose EasyEDA footprint printed "+"
  next to pad 1 …". `codes.toml:1231` cites 4.4 for exactly this case and `codes.toml:883` for the fix – both kept;
  "the fix was" → "the fix is". The original wording went to the history.
- The polarity-sheet sentence made its own paragraph (the first passed 120 words).
- The six wrong symbols became a list; the date of their finding → history; the pointer to
  `upstream/issue-6-easyeda-symbols.md` moved from the end to the sentence that introduces them. The Pico 2 line
  (shared with `tests/fixtures/led-bar/hardware/parts/C41407547.json`) word for word.
- `symbol_differs` its own paragraph; its JSON example no longer wrapped inside the code span.

### 4.5 Own parts – named by 20 places (`codes.toml` 789, 1221; `part.py` 28, 37; `eda.py` 758; `scripts.py` 1342;
`engines/struct.py` 123; `footprint.py` 1, 605, 611, 811; `domains/usb.toml` 18; `skills/pcb-round`,
`hardware-change`, `own-part`, `part-search`, `new-project`; `agents/electrical-reviewer`)

- The three steps and the SYNC.source table unchanged.
- New `### Bought and hand-wired boards` (bought boards, the cable breakout, the hand-wired board) and `### Without an
  edakit project`; the long bought-board and hand-wired paragraphs split, no sentence changed except "REQ.missing:cc
  checks a USB-C receptacle …" (active voice) and "the user is the datasheet" → "you are the datasheet". The example
  source "measured 2026-11-02, …" kept, now on one line so that the test reads it as a quotation.
- `### Own footprints as data` kept word for word (the skill own-part names it). New state line at its top from the
  last sentence of "Not covered yet" ("the reference project's scripts" → "a real project's scripts").
- "**The symbol**" split in two paragraphs. "**The way:**" became `### Building the copy`; steps 1 and 3 split into
  paragraphs inside the step. The date of the live run in step 4 → history.
- "**Checks** (3.3)" became `### Footprint checks`, its paragraph split into an opening sentence, PARTS.footprint,
  SYNC.footprint and stage L; no clause changed.

### 4.6 Datasheets kept with the project – named by `skills/part-search/distributors/lcsc.md:40`

- The paragraph on following a page split before "Only a complete PDF counts". Otherwise unchanged: its phrases are
  shared with `edakit/part.py` and `tests/test_part_fetch.py`.

## What went to the history file

Seven pieces, verbatim, in the scratchpad history file for chapter 13: the date of decision 8 (4.1, library), the
date of the dc-bias sheet attempt (4.1), "some 30 searches" of the reference project (4.2), the reference project's
LED footprint as it was told (4.4), the date of the six wrong symbols (4.4), the date of the live run of 3.6 (4.5),
the old wording of the build's state (4.5).

## Findings – not changed

1. **4.5, "Own footprints as data", is stale against the implementation plan.** The chapter says the build "has not run
   against EasyEDA yet (implementation plan, live run of 3.6)" and that the slot direction is something "the live run
   of step 3.6 has to show". `docs/concepts/done/implementation-plan.md`, row 3.6, says "live run 2026-10-31: 3–6
   hold", and step 4 of the chapter itself cites that live run. The same phrase is in an `edakit/footprint.py`
   docstring. Kept as written, now as the section's state line; the owner or the next session should update chapter
   and docstring from the live run's record.
2. **4.5, "Footprint checks":** "data = dump in SYNC.footprint, dump = PCB in SYNC.footprint" reads like a
   leftover of the code merge – SYNC.footprint replaces L-4, L-10 and P-10 (`codes.toml`), so both relations really
   are SYNC.footprint and the parenthesis says nothing any more. A rewording would touch a sentence shared with
   `codes.toml` (the 0.05 mm detail), so it stays.
3. **4.1, field `compliance`:** regulatory content (RoHS, REACH, radio e.i.r.p.) reaches the reader here without the
   "support, not legal advice" line that CLAUDE.md asks for wherever regulatory content reaches a reader. Chapter 15
   carries it; whether a field description needs it too is the owner's call. Not added (it would be a new statement).
4. **The brief named only 4.1 and 4.5 as read by the automation;** every section of chapter 4 is (list above). The
   brief's rule held for all of them.

## Assumptions – for the owner to look at

1. **Verbatim where a phrase is shared.** A sentence with an 8-word phrase found in code, catalog, a skill or a test
   was kept as written, even where the phrase is only a docstring written from the same text. This is the main reason
   the chapter is not a third shorter.
2. **Length over the 500-line limit.** Splitting the `pins` cell into a table and paragraphs, and long items into
   several, made the chapter longer in lines (671 → 776) for the sake of the paragraph and section rules and of
   readability. The alternative was to keep the 1100-word table cell.
3. **Regrouping inside 4.1.** The items of "what the names do not say" were reordered into three topics; every item
   stays in 4.1 and whole. The brief says "statements staying where they were" – read here as "in their section".
4. **"The owner has signed it" → "it is signed in edakit"** (the parts library, 4.1). The code (`edakit/library.py`)
   says the owner signs; the chapter no longer says who, only where (`edakit/parts/signed.toml`) and with which
   command.
5. **"The fix was in the graph" → "the fix is in the graph"** (4.4): the case became a rule in the present tense,
   matching the fix text of GEO.mark in `codes.toml`.
6. **The October 2026 date in 4.2 stays** as a state line: the reachability table is a dated measurement.
7. **The dates of decision 8, of the dc-bias sheets and of the six symbols left the chapter** although each dates a
   finding; none of them is a date a check or a skill relies on, so they went to the history.
8. **Pin key `v_max_v`** has no row of its own in the new pin table; the sentence above the table names it as a key
   every pin has, and "Limits and values" says what a pin's `v_max_v` does.
9. **"a pin of such an IC with a limit of its own"** (4.1, supplies): the old sentence said "A pin with a limit of its
   own" inside the item on ICs whose pins must not rise above their supply; the split item names that context.
10. **The bell's T-Display example and its JSON** stay unchanged as the public example.
