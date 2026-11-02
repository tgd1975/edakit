# Review of step D.5: handbook/07-pcb.md

**Status:** condensed in place on branch claude/amazing-newton-ygty8a, not committed; open for the owner's review.
Every statement kept, every `#`/`##` heading and section number unchanged. The chapter did not give a third fewer words
or 500 lines without losing statements – the statements won (reasons below).

## Measures

| | before | after |
| --- | --- | --- |
| lines | 904 | 1057 |
| own words (prose, without tables and code) | 10508 | 10242 (−2.5 %) |
| mean sentence (words) | 29.3 | 26.5 |
| sections over 80 lines without a subheading | 4 (up to 300 lines) | 0 |
| paragraphs over 120 words | 36 | 0 |
| "the user" / "the reference project" | 4 | 0 |
| dates outside a status line | 1 | 0 |
| bare cross-references | 0 | 0 |
| chapter over 500 lines | yes | yes |

`tests/test_style.py -k 07-pcb`: `sections`, `words` and `dates` are now XPASS(strict) – the chapter can leave those
three sets of `RED` (not done here: `tests/test_style.py` is not this step's file). `paragraphs` passes outright, see
Findings 1. `chapters` stays an expected failure.

**Why not a third fewer, and why more lines.**

- Every section from 7.3 to 7.7 is named by the automation (rule 4), and the chapter as a whole by
  `edakit/catalog/codes.toml` ("handbook 7") and opened by path by `skills/pcb-round/SKILL.md` and
  `agents/pcb-reviewer.md`. So no statement could leave a section, and the duplicates across sections stay – the
  geometry sources in 7.3 and 7.4, GEO.spacing in 7.4 and 7.5, the order mark in 7.5 and 7.7 (which chapter 8 owns).
  Inside a section, repeated lists were merged (below).
- About 4,000 of the 10,500 own words sit in sentences that share eight or more words verbatim with code, skills,
  tests or other chapters (rule 5): `edakit/pcb.py` (most of 7.4), `edakit/route.py` (the notch strips, fanout,
  hand-soldered joints, diagnose and congestion, pour regions), `edakit/part.py`, `edakit/drc_rules.py`,
  `edakit/silk.py`, `edakit/checks.py`, `edakit/handover.py`, `edakit/eda.py`, `edakit/export.py`,
  `edakit/release/fab.py`, `edakit/catalog/codes.toml`, `tests/test_pcb.py`, `tests/test_route.py`,
  `tests/test_silk.py`, `tests/test_fab_run.py`, `tests/test_part_diff.py`, `skills/pcb-round/SKILL.md`,
  `skills/circuit-design/SKILL.md`, `agents/pcb-reviewer.md` and chapters 3, 6, 8, 9, 10 and 12. Those sentences were
  kept, split from their paragraphs or turned into list items with their words. The rest is specification text in
  which nearly every clause is a key, a number, a condition or a command: few asides, announcements or repetitions to
  cut.
- Lines grew by 153: 36 new `###` subheadings with their blank lines, 36 long paragraphs split, three run-on sentences
  turned into lists (the checks of `pcb plan`, the check before writing, the steps of `silk apply`), the paragraph of
  `pcb place --rest` turned into four items, and the cell-paragraph of the mechanical model's table turned into a list.
  Reaching 500 lines would mean removing about half of the chapter.

## Per section

The automation names: 7.3 once (`skills/hardware-change/SKILL.md:40`); 7.4 ten times (`skills/pcb-round/SKILL.md`
69, 75, 77, 85, 95, 99; `skills/circuit-design/SKILL.md:143`; `edakit/catalog/codes.toml` 706, 725, 727); 7.5 eight
times (`skills/pcb-round/SKILL.md` 153, 159, 164, 165, 172; `codes.toml` 953, 967, 1047); 7.6 four times
(`skills/pcb-round/SKILL.md` 141, 146, 167; `codes.toml` 929); 7.7 twice (`skills/pcb-round/SKILL.md:104`;
`codes.toml` 1042, 1047); the chapter four times (`codes.toml` 685, 723, 842, 1088). `docs/glossary.md:207` links the
anchor `#74-the-placement-plan`, unchanged. The skills that open the file (`pcb-round`, `pcb-reviewer`) were read
against the new text: every statement they cite with "handbook 7.x" is still in that section.

- **Top of the chapter (no number).** New first paragraph: for whom, what after. The layers paragraph shortened ("each
  repeatable and each checking itself"); the bought-board sentence kept verbatim (shared with chapters 3, 6, 8); the
  bought and KiCad sentences made paragraphs of their own; "(16.4)" names its subject ("the KiCad flow, 16.4").
- **7.1 Coordinates** – "any origin you like" → "any origin"; the bottom-view aside made a reason; "must be < 0.05 mm"
  → "below 0.05 mm".
- **7.2 Outline, holes, tooling holes** – the tooling paragraph tightened and split in two; "(handbook 18)" →
  "(chapter 18)", "(8.4)" → "(ordering, 8.4)".
- **7.3 Parts and nets without dialogs** (named) – the default board and the Channel ID paragraphs moved up, after the
  list of `pcb nets`/`pcb parts`, still in 7.3; new `### Swapping a part` (part diff) and `### Formed leads
  (GEO.formed)`, the GEO.formed paragraph split in two with its words. The example "The reference project's slide
  switch" → "On a real project, … for the slide switch"; its story to the history file.
- **7.4 The placement plan** (named) – thirteen new `###`: Footprint geometry, What the circuit hands over, The plan
  check, Polarised parts, Parts under a module, Overlaps and pad spacing, Mated plugs, The mechanical model, Parts next
  to their host, Every other part (--rest), The auto-layout's positions, A board placed before, Every part in the plan.
  Merged inside 7.4: the GEO.spacing details of the `pcb plan` list now stand once, in "Pads of different parts"; the
  sentence "The pads themselves are compared on their own … (GEO.spacing, below)" merged into that paragraph; the
  geometry sources of `pcb place` → "as `pcb plan` does (footprint geometry, above)"; the list of checks a spot of
  `pcb place` and `--rest` must pass → "every check above", with the keys named and "mated plugs, `uniform` and
  GEO.spacing included"; the list of checks of the auto-layout rows → "`pcb plan` checks them". The silkscreen
  tolerance's key block and depth findings moved before GEO.spacing, to the paragraph they belong to. The `[layout]`
  paragraph and the `--rest` paragraph became lists with their words. "The airline length is the only score so far" and
  "`pcb autolayout` stays until this placer has placed a real board that routed and passed the gate" became the
  `> **State:**` line of `--rest`; "that may become a second one" stays in the prose. The `parts` row of the mechanical
  model's table (a paragraph in a cell) became a list under the table (no test or generator reads it). "the reference
  project" → "a real project" (the library/EasyEDA agreement, which `codes.toml:706` cites). "Until October 2026 …" →
  "An older `pcb dump` …", the dated sentence to the history file.
- **7.5 Routing with Freerouting** (named) – twelve new `###`: Why Freerouting, Rules in the board file, EasyEDA's DRC
  rule set, Widths from the simulation, Freerouting 2.4.1 pitfalls, Fanout to a plane, The check before writing,
  Hand-soldered joints (GEO.spacing), Track widths (GEO.width offline), The visible side, Why a connection stays open,
  Writing into EasyEDA. Where a heading took a bold lead-in's words, the lead-in went. "Check before writing" became
  a list with its words; "Preview: … Nothing is written to EasyEDA until the check passes" moved there from the end of
  the visible side (both in 7.5). Import Changes' two cases became a list. "(9.4)" → "(the PCB API, 9.4)", "(7.7)" →
  "(silkscreen, 7.7)", "(8.1)" → "(stages, 8.1)". "the reference project" twice → "a real project" (the DRC row
  example; the three spacing findings that justify 0.5 mm, which `codes.toml:946` quotes). History out: "(1773 lines →
  223)", the day spent repairing the autorouter, the recreated part and its open GND link, "70 of 178 connections",
  "320 false connection errors", the ten gate runs and 2¾ h.
- **7.6 Pours** (named) – three new `###`: Distance from the edge, Pour-only nets, Several nets on one layer; the
  `stitch = "BOTTOM"` sentence moved up next to the filling it describes, the GEO.pour sentence restructured ("Inside
  the pour outline … it warns about …"); long paragraphs split; "KiCad (16)" → "KiCad (chapter 16)".
- **7.7 Silkscreen** (named) – six new `###`: Bodies and the solder side, Fixed designators, The board label, Artwork
  and texts, Good to know, In the gate. The one-sentence description of `silk apply` became a numbered list with its
  words; long paragraphs split; "(17.11)" → "(the walkthrough's layout, 17.11)", "(8.2)" → "(sign-offs, 8.2)",
  "(7.5)" → "(the visible side, 7.5)".
- **7.8 Export for documentation** – unchanged.

## History file

Moved verbatim, with their sections, to the scratchpad history file for chapter 13
(`/tmp/claude-0/-home-user-edakit/82157d39-3f55-5034-b81b-e1cbfc4ad998/scratchpad/history/07.md`): the hour spent on
the slide switch (7.3), "Until October 2026" (7.4), the autorouter's 1773 → 223 lines and the day of repairs, the
recreated part's open GND link, the ground plane's 70 of 178 open connections, the 320 false DRC errors, the ten gate
runs held at Import Changes (all 7.5).

## Findings

1. `tests/test_style.py`, `RED["paragraphs"]`: `{f"handbook/{c}.md" for c in ("07-pcb")}` has no trailing comma, so
   it iterates the characters of "07-pcb" and puts `handbook/0.md`, `handbook/7.md` … into the set instead of chapter
   7. The chapter now meets the rule, so the test passes – it would be XPASS(strict) with the comma. The entry can go
   with the other three.
2. No sentence was found wrong against the code in the places checked (`near_mm` 6, `edge_mm` 1, `header_keep_mm`,
   `silk_overlap_mm` 0, `max_bare_mm` 5, `max_bare_mm2` 20, `tab_copper_mm` + 0.05 mm in `edakit/config.py` and
   `edakit/pcb.py`); the chapter was not checked against the code sentence by sentence.
3. Many of the chapter's sentences exist a second time as docstrings in `edakit/pcb.py` and `edakit/route.py`. Rule 5
   froze them here; if the owner wants the chapter shorter, the decision is whether a docstring that repeats the
   handbook binds the handbook's wording.

## Assumptions

1. **Rule 5 read as "keep the words of the shared part".** A sentence that shares eight or more words with code,
   skills, tests or other chapters kept its words; where such a sentence stood in an over-long paragraph, the
   paragraph was split or the sentence made a list item, without rewording. Output strings in backticks (findings,
   command output) were never touched.
2. **Order inside a section changed** in four places, statements staying in their section: 7.3 (default board and
   Channel ID before the part diff), 7.4 (silkscreen tolerance's key block before GEO.spacing), 7.5 (the routing
   preview into "The check before writing"), 7.6 (`stitch = "BOTTOM"` next to the filling).
3. **"On a real project"** replaces "the reference project" in four places where a number depends on it (the slide
   switch diff, the 0.1 mil agreement of eleven footprints, the DRC row example, the three spacing findings behind
   0.5 mm). These are the measured cases the statements rest on, so they stayed.
4. **Kept as non-history:** "On 3.2.209 not seen (E-7)" and "live on 3.2.209: clean" (an EasyEDA version a statement
   depends on), "easyeda-mcp-pro 1.6.0" and "Freerouting 2.4.1" (tool versions), "it once put a decoupling capacitor
   24 mm from its IC" (the reason for `near`, quoted by `codes.toml:718`), "Mitred joins reached … Tracks that kept
   the clearance were reported" (the reason for round joins, shared with `edakit/route.py`), the round board of
   chapter 17 (an example), "a regular 1.5-mm font had 0.12 mm" and "a size of 1.0 gave 0.71-mm letters" (the
   measurements behind the advice and the factor 0.68).
5. **Code-block comment left:** `# … 8 mil left 18 links open` in the `[routing]` example is a story of one run, but
   it is a comment in a code block and the reason for 6.5 mil; it stays.
6. **Reworded history residue:** "Deterministic but order-dependent: a part recreated in EasyEDA moves to the end of
   its list, and the same plan can then leave a link open on every run" generalises "three times in a row" from
   determinism; "the DRC once reported false connection errors that a save and reload cleared" keeps the event without
   the count.
7. **State line:** the `--rest` placer's "only score so far" and "the auto-layout stays until this placer has placed a
   real board that routed and passed the gate" became one `> **State:**` line at the top of its subsection.
8. **More `###` than the 80-line rule needs** (36): one per topic a reader looks for, at the price of lines. Fewer
   would bring the chapter nearer its original 904 lines.
9. **First paragraph names "the assistant"**, as `docs/style.md` has it, for the PCB designer who may be a session.
