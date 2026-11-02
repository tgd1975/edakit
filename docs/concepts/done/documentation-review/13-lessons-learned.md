# Review: chapter 13 Lessons learned (step D.5)

**Status:** built 2026-11-01 – chapter 13 is the history of edakit and holds what the other chapters moved out; for
the owner's review.

## What changed

- **Measures** (measure.py against HEAD): lines 112 → 255; own words 1073 → 2636; mean sentence 21.9 → 24.6 words;
  "the reference project"/"the user" 5 → 0; sections, paragraphs, bare references, dates: 0 → 0.
- **First paragraph:** for whom (anyone who wants to know where edakit comes from and why its rules are as they are)
  and what they find.
- **pytree described once**, in the second paragraph, linked to `docs/projects/pytree.md`: a project of about
  120 parts built in October 2026, with the board description that chapter 1 ("What it achieved") gave. Elsewhere
  "pytree" or "the project".
- **Words:** "the reference project" → "pytree"; "the user" → "someone" (13.2 items 2 and 8) and "the person who
  decided" (13.3, numbered decisions); "the owner's accounts/decision" → "our accounts", "Decided:" (the chapter speaks
  as "we").
- **Headings:** 13.1 to 13.6 unchanged. New: **13.7 After the first board, day by day** (a dated table, 22 Oct to
  1 Nov) and **13.8 How the chapters' details came about** with `###` per group of chapters.

## Where each history file went

| File | Passage | Now in |
|---|---|---|
| 01 | "All of these happened or nearly happened …" | 13.8, chapters 1 and 3 |
| 01 | "What it achieved": the board, five days 19–23 Oct, the redesign in a day, one order, no prototype round | intro (board, one order), 13.5 (19 to 23 October), 13.1 (redesign, already there) |
| 01 | the list of findings, "Each became a check" | 13.8 intro, merged with 14's "The rules of edakit are lessons" |
| 02 | nothing moved | – |
| 03 | `graph.json` until October 2026; the cathode found by the name "K" | 13.8, chapters 1 and 3 |
| 04 | dates of PARTS.library decision 8, `dc_bias` sheets, the six wrong symbols, the live run of 3.6 | 13.7 (31 Oct rows) |
| 04 | "some 30 searches"; the LED footprint story; the build using the bell's and pytree's calls | 13.8, chapters 4, 6 and 7 |
| 05 | three "as before" remnants | not taken – the file says they need no place (no fact of edakit's past) |
| 06 | template named after its page (LT-10, 2026-10-31) | 13.7 (31 Oct) |
| 06 | empty netlist saved; copySchematic copying the bell's ESP32 THT template | 13.8, chapters 4, 6 and 7 |
| 06 | timing 123 parts: placing 2.1 min, connecting 3.7 min | 13.2, step times (merged with the 6 min already there) |
| 06 | pin on two nets, "regenerating fixed it" | 13.2 item 6 (merged) |
| 07 | slide switch hour; geometry among the artifacts until October 2026; 70 of 178 open with the ground plane; 320 false DRC errors; Import Changes holding the gate in ten runs, once 2¾ h | 13.8, chapters 4, 6 and 7 |
| 07 | autorouter 1773 → 223 lines, a day of repairs converging nowhere | 13.4, "Freerouting from day one" (merged) |
| 07 | one GND link open three times after a part was recreated | 13.3, "Freerouting with our own DSN" (merged) |
| 08 | M-5 lesson; GEO.pour (45 % bare); looks row measured by hand; one-file edakit.toml until October 2026 | 13.8, chapter 8 |
| 08 | footprint geometry among the artifacts until October 2026 | merged with 07's into one item, 13.8 |
| 08 | decisions 2026-10-30 (nothing orders or pays; fee table, step 5), 2026-10-31 (no regulatory content; `[looks]` mark), 2026-11-01 (wishes to makers); stage E since 2026-10-31; the state line of 8.4 (step 0, cart live at four makers) | 13.7 |
| 08 | tooling holes found only in the quote | 13.4, merged into the existing item |
| 08 | four boards published as a draft by a script of its own | 13.6, as the bell's (see Assumptions) |
| 09 | opening paragraph (3.2.206, 1.4.0, 19–26 Oct; 3.2.209 on 1 Nov) | 13.8, chapter 9 |
| 09 | the dates out of the tables | 13.7, one row each (22 Oct, 26 Oct, 30 Oct, 31 Oct, 1 Nov) |
| 10 | decision of 2026-10-31 on `mark` | 13.7, merged with 08's same decision |
| 11 | "a week of daily use"; elektrotechniker/pcb-pruefer; coordination tool; agreements reach every session | 13.8, chapter 11 |
| 11 | parallel sessions normal; 20-minute run lost; 38 and 93 minutes waiting; 49 minutes for a click | 13.2 items 1 and 2 (merged; the 93 minutes are the table's connector swap) |
| 11 | the project went on growing after the extraction (0 Ω bridges, star LED, pour-only nets) | 13.4, "Generic from the start" |
| 12 | nothing moved | – |
| 14 | pcb-pruefer reviews rounds and signs M-5 | 13.8, chapter 11 (merged with 11.1's) |
| 14 | REQ.missing and REQ.missing:cc from the buzzer stage and USB-C input | 13.8, chapters 14, 16 and 17 (the CircuitSmith half stays in 14.6) |
| 15 | "as before" dropped | not taken (no fact) |
| 16 | the first parity run (/GND); two things learnt on `route all` | 13.8, chapters 14, 16 and 17 |
| 17 | the rename into codes and the re-sign-offs of the same day | 13.8, chapters 14, 16 and 17 |
| 18 | nothing moved | – |

## Merged

- The 31 Oct live run of 3.6 (from 4.5) and "Live on 2026-10-31 (step 3.6): the pads come back as built" (from 9.4)
  are one row.
- The `[looks]` mark decision (8.4 and 10.2) is one row with the electrical-hash decision of the same day.
- The 1 Nov 3.2.209 rename sentence of 9.3 went into the row of the live check on 3.2.209.

## Assumptions

1. **The four published boards are the bell's.** Chapter 8 said "The reference project built this as a script of its
   own first and published its four boards – the main board and the variants smd, tht and esp32". main, smd, tht and
   esp32 are the bell's variants (`docs/projects/christmas-bell.md`), pytree has one tree board, and commit a0bfb90
   names the bell's D-22. Chapter 13 puts it in 13.6 as the bell's. If it was pytree after all, move the item.
2. **The second paragraph's board** comes from chapter 1's "What it achieved" (MCU module, three LED driver ICs,
   about 30 LEDs, buttons, DIP switch, buzzer, concave outline, assembled by JLCPCB on one side); pytree's page agrees
   (RP2350-Zero, three LED drivers, 30 LEDs, back side assembled).
3. **"We" for the owner.** Decisions read "Decided:" and the maker accounts "our accounts"; the style guide keeps "the
   owner" off reader pages.
4. **"the user" → "someone"/"the person who decided"** rather than "you": these are past events, not instructions to the
   reader.
5. **"found the hard way" → "found by trial"** in the chapter 9 opening; "again the hard way" (11.5) → "learn them
   again by trial".
6. **13.7's title** "After the first board, day by day" although its first row (22 Oct, the DRC rule set) falls in
   pytree's week: the row is a date that stood in chapter 9, not part of 13.1's story. 13.1 is unchanged.
7. **Context sentences not taken:** 17.md's "The note names R-2 …" and the generic statements of 8.2 that the history
   files carried as context only stay in their chapters; 13.8 takes the story part.
8. **The stories inside 11.4** stay there (11.md: moving them changes the agreements and is the owner's decision).
9. **Mean sentence 24.6 words**: 13.2's step-time sentence (73 words, unchanged from before) and the facts of the
   slide switch keep it up; the sentence rule holds only for the entry pages.

## Findings

- `tests/test_style.py` RED lists `handbook/13-lessons-learned.md` under "words"; the chapter now meets the rule, so
  `words:handbook/13-lessons-learned.md` is XPASS(strict) and fails until it leaves RED (not changed here).
- Chapter 8's sentence on the four published boards (see Assumption 1) named the wrong project, if the assumption holds.
