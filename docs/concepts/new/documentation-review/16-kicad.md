# Review of step D.5: handbook/16-kicad.md

Status: condensed in place on 2026-11-01, not reviewed yet – the assumptions below are for the owner.

## Measures

| | before | after |
| --- | --- | --- |
| lines | 202 | 225 |
| own words (prose, without tables and code) | 1937 | 1898 (−2 %) |
| mean sentence | 26.2 | 21.3 |
| test_style violations | paragraphs 2 (190 and 170 words), dates 2 (2026-10-31, 2026-11-01 in 16.8) | none |

`tests/test_style.py` now passes `paragraphs` and `dates` for the chapter (XPASS strict): `handbook/16-kicad.md` can
leave those two sets of `RED` in `tests/test_style.py`.

**Why not a third fewer.** The chapter is almost all qualifications: kicad-cli flags, file names, codes, key names,
numbers of a live run (18 nets, 208 track pieces, 29 vias, 62.825 mm, 0.1 µm). Six of its eight sections are named by
the automation (below), so every statement stays in its section. The new first paragraph, the subjects added to the
cross-references and the CI paragraph moved into 16.8 add about 50 words; the cuts are the repetitions and the story.
The statements won. The line count grew because long paragraphs were split, list items became sentences, and four
`###` were added – the chapter stays far below 500 lines.

## Where the automation names the chapter

- `handbook 16` (whole chapter): `edakit/part.py:598`, `agreements.py:157`, `config.py:56`, `config.py:989`,
  `export.py:163`, `gerber.py:12`, `route.py:2271`, `release/gate.py:271`, `release/gate.py:574`, `doctor.py:258`,
  `silk.py:740`, `pcb.py:2468`, `schematic.py:424`, `schematic.py:542`, `toolchain/__init__.py:1`,
  `toolchain/kicad/__init__.py:1`, `toolchain/kicad/commands.py:1`; skills `pcb-round:19`, `start:11`, `release:23`,
  `new-project:61`.
- `handbook 16.3`: `edakit/toolchain/kicad/library.py:1`; `tests/test_kicad_live.py:130` ("The frames").
- `handbook 16.4`: `edakit/toolchain/kicad/board.py:2`, `board.py:416`, `toolchain/kicad/silk.py:1`;
  `handbook/README.md:33` names "table 16.4" – kept as a table.
- `handbook 16.5`: `edakit/toolchain/kicad/cli.py:1`, `edakit/catalog/codes.toml:763` (SYNC.odb's fix).
- `handbook 16.6`: `edakit/release/fab.py:2036`, `edakit/toolchain/kicad/fab.py:1`, `tests/test_kicad_fab.py:1`.
- `handbook 16.8`: `tests/test_kicad_live.py:2`; `(16.8)` in `edakit/toolchain/kicad/board.py:132` (the
  `filled_areas_thickness` fact – kept in 16.8).

No skill opens the chapter file by path.

## Per section

- **(new) first paragraph** – for whom (a project drawing its boards in KiCad instead of EasyEDA Pro) and what after
  (switch, set up, what each command and gate stage does). The concept link moved up into it; "one key in edakit.toml
  decides" left the intro, as 16.1 shows the key.
- **State line** – now a block quote `> **State 2026-10-31:** …`, one line of facts: built, tested offline against a
  faked kicad-cli and in CI against KiCad 10 on the led-bar example, first release the 555 blinker with KiCad 10.0.6,
  link to 16.8. The CI details (job `kicad` of tests.yml, container image, `tests/test_kicad_live.py`,
  `EDAKIT_KICAD_LIVE=required`, the skip on another major such as KiCad 9 and why a red run there is no regression)
  moved to 16.8, where the CI confirmation is described – merged with 16.8's own "Confirmed by the CI job `kicad` on the
  led-bar example (KiCad 10.0, its container image)", which said the same job and image a second time.
- **16.1 Choosing it** – "exactly as before" → "as before"; the two sentences about refused document names merged
  (same statements: `template`, `schematic`, `pcb` refused, nothing to name, every board the KiCad project). The list
  of what the KiCad side does without unchanged in content.
- **16.2 Setup** – unchanged in content; "(2.2)" → "(the installation, 2.2)"; "; the flags" → ", but the flags".
- **16.3 The KiCad project** (named) – no statement left. The bold run-in titles **Footprints**, **Symbols**,
  **Frames:** became `###` headings (new anchors, none removed). The 190-word footprints paragraph was split into three
  (source, cache and silkscreen, pads). Wording: "a footprint from it would need a correction of turn and origin, and
  maybe of its pad numbers" → "its footprints would need a correction of turn, origin and maybe pad numbers"; "Open the
  files in KiCad to look at them; whatever is changed there" → "Open the files in KiCad to look; a change made there";
  "Nets are named by labels where …" → "Labels name the nets where …". Cross-references now name their subject (own
  parts 4.5, drawn without EasyEDA 6.5, the coordinates 7.1). The second "(4.5)" after `edakit part footprint` was
  dropped – the first one in the same paragraph points there.
- **16.4 The flow** (named; table) – kept as a table. Cells: `schematic create` "checks it at once (16.6)" → "checks it
  at once, as `schematic check` does" (checked in `edakit/toolchain/kicad/schematic.py:356-372`: create runs the same
  `check` as `schematic check`); "(7.4)" → "(the placement plan, 7.4)"; "(7.7)" → "(silkscreen, 7.7)".
- **16.5 kicad-cli** (named) – the flag lists unchanged. The ODB++ item's reasons (four decimals, the 62.825 mm
  example, 0.1 µm against 1 nm, MPN/LCSC properties for AISLER) left the list item and became a paragraph of their own
  directly after the list, in the same section, wording unchanged but split into sentences. The DRC paragraph
  unchanged.
- **16.6 The gate on KiCad** (named) – no statement left. The 170-word F item was split: **F:** (Gerber and drill
  files, PTH split, flying probe file, SYNC.bom, SYNC.cpl) and **F, ODB++:** (SYNC.odb, `odb_error.txt`, tooling hole
  `TH<n>` with `.no_pop`, `edakit export`). "Stages P, G, E: unchanged." → "Stages P, G and E are unchanged."
- **16.7 Switching a project** – the steps unchanged; "the sign-offs of scope `fab` lapse" now points to the fab hash
  (16.6), which says the same thing for the gate.
- **16.8 What KiCad 10 confirmed, what is open** (named by `tests/test_kicad_live.py`) – three `###` added: "In CI, on
  the led-bar example", "On the 555 blinker", "Open". List items are now sentences. The two dates (2026-10-31 for the
  ODB++ with kicad-cli 10.0.6, 2026-11-01 for the cart runs) moved from the items into a `> **State:**` line at the top
  of the section; the items keep the test name and `tests/fixtures/makers/LIVE.md`. "The first run found every pad in
  conflict … global labels since" → "The schematic has global labels: local labels name a net "/GND", and the parity
  found every pad in conflict." "two things had to be learnt there:" dropped, both KiCad 10 facts kept. "Confirmed on a
  real project, the 555 blinker of chapter 18" → "Confirmed on chapter 18's real project". The open points became a
  list; "the steps are in the concept, "Live test"" now links `../docs/concepts/done/kicad-toolchain.md#live-test`.

Phrases found elsewhere and kept word for word: "generated, not versioned", "keeps its spot", "cache only", "places
before its first apply", "pin tips", "unconnected-(SW1-Pad3)", "KiCad has no auto-layout", "one writer", "one raster
point", "knows no LCSC", "one thermal spoke", "KiCad has no free pads", "filled_areas_thickness", "square notch",
"nothing ordered".

## History file

Moved verbatim to the history file for chapter 13 (both from 16.8): "The first run found every pad in conflict with
the schematic: local labels name a net "/GND" – the schematic has global labels since" and "… wrote the file KiCad had
saved again – two things had to be learnt there: …". The facts stay in 16.8 in present tense.

## Findings

Not changed – for the owner:

1. **16.3 Frames, "a point (x, y) lies at (x mm, −y mm)"** reads as if the number stayed the same. The code converts mil
   to mm: `edakit/toolchain/kicad/board.py:16-17` and `to_kicad` (line 72) give (x/39.37 mm, −y/39.37 mm). The sentence
   should say "(x, −y) converted to mm" or give the factor.
2. **`edakit/catalog/codes.toml:763`** (SYNC.odb's fix) sends a reader to "handbook 16.5" for `odb_error.txt`; the
   chapter has `odb_error.txt` in 16.6, not 16.5. The catalog's reference should say 16.6 (catalog text is data – not
   changed).
3. **`edakit/toolchain/kicad/board.py:416`** writes into every `<board>.kicad_dru` "GEO.spacing's keep-outs are
   Freerouting's and the gate's (handbook 16.4)"; 16.4 says nothing about keep-outs or the DRC rule file. 16.5 (the DRC
   checks that are off) is the nearer section; neither names GEO.spacing.
4. **`edakit/toolchain/kicad/board.py:405`** cites "handbook 18" for the one thermal spoke; the statement is in 16.5
   (and 16.8). Not wrong – chapter 18 mentions it too – but 16.5 owns it.
5. **16.2 "KiCad 10, the newest for Ubuntu"** is a claim that will age; kept as a dated fact with the tool versions.

## Assumptions

1. The CI paragraph of the old intro (job, container, `EDAKIT_KICAD_LIVE=required`, skip on another major) moved into
   16.8 – the chapter as a whole is what `handbook 16` names, and 16.8 is where `tests/test_kicad_live.py` points for
   the live tests.
2. The intro's "16.8 says what is confirmed and what is open" became "(what is confirmed, 16.8)" in the State line.
3. The two dates in 16.8 are dated measurements a statement depends on (what kicad-cli 10.0.6 confirmed, when the cart
   runs took place); they stay, moved into the section's `> **State:**` line instead of the items. The chapter's top
   State line keeps its date 2026-10-31.
4. "The first run found every pad in conflict" is treated as history; its fact (global labels, because local ones name
   "/GND") stays in 16.8 rather than moving to 16.3, since 16.8 is named by a test.
5. "KiCad 10 names nets in items by name, and leaves out `(filled_areas_thickness no)`" kept in 16.8 because
   `board.py:132` points there with "(16.8)".
6. The ODB++ reasons left the list item of 16.5 and became a paragraph after the list – same section, same words.
7. `### Footprints`, `### Symbols`, `### Frames` replace bold run-in titles in 16.3; `### In CI, on the led-bar
   example`, `### On the 555 blinker`, `### Open` are new in 16.8. No existing anchor removed.
8. In the 16.4 cell for `schematic create` the cross-reference "(16.6)" was replaced by "as `schematic check` does",
   checked against the code; the following row says what `schematic check` does.
9. "the 555 blinker of chapter 18" stays named as a real project – it is a public example (`examples/blinker-555`),
   not the private reference project.
10. "exactly as before" shortened to "as before" – a compatibility statement, kept, not treated as history.
