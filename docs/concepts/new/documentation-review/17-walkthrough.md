# Review: handbook/17-walkthrough.md (step D.5)

Status: condensed in place on branch `claude/amazing-newton-ygty8a` on 2026-11-01, not committed. Waiting for the
owner's review of the assumptions below. Every quoted output, command, code block, picture and the table of 17.1 is
unchanged, checked by a script that compares them with HEAD. Only the prose around them changed.

## Measures

| | before (HEAD) | after |
| --- | --- | --- |
| lines | 714 | 734 |
| own words (prose, without code, tables, quotes) | 3,848 | 3,679 (−4.4 %) |
| mean sentence | 23.8 words | 21.8 words |
| sections over 80 lines without a subheading | 3 | 0 |
| paragraphs over 120 words | 4 | 0 |
| bare cross-references | 0 | 0 |
| "the user" / "the reference project" in own sentences | 0 | 0 |
| dates in own sentences | 1 | 1 (kept, see below) |

`tests/test_style.py -k 17-walkthrough`: the rules **sections** and **paragraphs** now hold (XPASS(strict)), so the
chapter can leave both lists in `RED`. **chapters** (over 500 lines) and **dates** stay expected to fail.

The chapter does not lose a third of its words. Its statements win, as the brief allows. About 335 of its lines are
quoted outputs, commands and files that are held fixed, and the table of 17.1 is the evidence for the start page. The
prose is a narrative in which nearly every clause is a fact of the example. The cuts are restatements of a code block,
the history of 17.9, a repeated disclaimer and wording. The cross-references gained their subjects ("(working rules,
3.4)" instead of "(3.4)"), which costs about 40 words. The chapter grew by 20 lines: eight new `###` headings and the
reviewer's notes as a sub-list. Below 500 lines it cannot go without cutting quoted output.

## Sections the automation names

Found with `grep -rnoE "handbook 17(\.[0-9]+)?|handbook/17-walkthrough\.md" edakit skills agents .claude hooks bin`:

- **17.6**: `edakit/catalog/codes.toml:275` (LIM.p, the source text names D1's LIM.p rows). The statement that LIM.p
  holds D1's 14.75 mW to 32.5 mW, half its 65 mW, is unchanged. It is split off into a paragraph of its own.
- **17.11**: `edakit/catalog/codes.toml:968` (note 4, `hand_solder_keep_mm`), `:1048` (note 1, BT1's designator under
  the cell, `body.box`), `:1106` (note 3, `[order]` and the tooling holes). The four notes of step 5 are verbatim.
  The answer to note 4 keeps every statement, rewrapped.
- **17** (chapter): `edakit/part.py:862` (the certificate kept as the datasheet, 17.13, unchanged apart from the
  cross-reference); `codes.toml:1094` (FILES.order's why, the tooling holes of 17.11, kept); `codes.toml:987` (the via
  ring of protocol L). The chapter has never said anything about the via ring. That is a source reference to the run,
  not to a sentence.

`tests/test_walkthrough.py` reads the example, not the chapter. `tests/test_pages.py` names the chapter's file path
only. Both pass.

## Per section

- **Intro.** The first paragraph now says who the chapter is for. "The smallest board edakit makes" became "a board
  of four parts", because the style guide allows no superlative. The note that the order and the delivered boards are
  described, not shown, was merged into the sentence about the runs.
- **17.1.** The table is untouched, including the "Who" column. The sentence under the table was reworded into one
  sentence, with the same statements.
- **17.2.** "no scripts or agents of the project's own" became "no project scripts or agents" (the glossary term).
  The M-6 disclaimer stays here in full, as the chapter's one disclaimer.
- **17.3.** Reworded. The cross-reference to the requirements (3.6) moved to the word it explains.
- **17.4.** Reworded: "The library calls the holder's pins `1` and `2`; which is plus, the datasheet says."
- **17.5.** New `###` headings: "The checks" and "The simulation". The enumeration of the two hints was cut (bulk
  capacitor, lithium protection), because the output shows it.
- **17.6.** The four bold paragraph titles became `###` headings: "D-2: a red LED", "D-3: a cell upside down", "D-7:
  the cell's current", "The design hints". Their codes moved into the first sentence (SIM.state) or into the text
  (LIM.i/cell). The paragraph of 128 words about STRUCT.entry's fix and the LED's current was split in two. "just the
  margin" became "the margin".
- **17.7.** Reworded. The cross-reference to ordering (8.4) moved to the front of the sentence about the order form.
- **17.8.** Reworded. The cross-references got their subjects (DOCS.quote, 6.6; roles, 14.1).
- **17.9.** The electrical reviewer's five notes became a sub-list, so the item has fewer than 120 words. The
  regulatory reviewer's disclaimer sentence was cut, because 17.2 says it once (CLAUDE.md: "says once"). The decision
  round was reworded. The story of the re-sign-offs, "A day later … That happened once more the same day …", went to
  the history file. It is replaced by one paragraph with the same statements: the hash changed three more times
  (`edakit convert --write`, D-7 together with HINT.debounce's accept leaving, BT1's `body.box`), and both agents
  looked again and signed each time. M-1 checked the new accept's reason and found the hint of 17.13. The convert's
  details (`waive`/`hints` → `accept`, `ratings` → `limits`) are left only in the history file.
- **17.10.** The explanation of the table was split into two paragraphs, with no wording change beyond punctuation.
- **17.11.** New `###` headings: "The board file" and "In EasyEDA". Three sentences that restated the comments of the
  TOML block were cut. They said that a circle is a square whose corner radius is half its side, that the board file
  holds the outline, the tooling holes and a `[place]` row for every part, and that the "+" sits beside the holder
  because the footprint's ⊕ lies under its body. These statements are still in 17.11, in the comments of the quoted
  board file. D-6 now stands beside the wish for a round board. "`/edakit:start` …" now opens the EasyEDA part instead
  of being an aside.
- **17.12.** The paragraph about the gate was split: what the last stages check, then M-5 and RELEASED. The
  regulatory reviewer's disclaimer sentence at the order was cut (said once, in 17.2). The second "(8.3)" and "(8.4)"
  were dropped, because the same section is already referenced a sentence or the list's intro before. New `###`
  heading: "The order".
- **17.13.** Kept in full as the walkthrough's own record (part.py cites it). The round board's item lost "A corner
  radius of half the side makes a circle", which 17.11's board file already says.

## History file

`/tmp/claude-0/-home-user-edakit/82157d39-3f55-5034-b81b-e1cbfc4ad998/scratchpad/history/17.md`: the two passages of
17.9 about the rename into codes and the re-sign-offs "a day later" and "the same day", verbatim.

## Dates kept

- Intro: "The outputs are from real runs between 29 and 31 October 2026". This is the date of the measurements that
  the quoted outputs depend on: catalogue hits, stock figures, prices, the sign-off's date. The walkthrough's story
  needs it, so `dates` stays expected to fail.
- The dates inside the quoted outputs and files (2026-10-29 for the catalogue, the sign-off and the stock snapshot;
  2026-10-31 for the M-1 sign-off and the maker profile) are untouched, as quoted output.

## Findings

- `edakit/catalog/codes.toml`, the text of DOCS.draft (quoted in 17.5's check output): "a draft – the user has not
  approved it". The style guide wants "you" in reader text. This is catalog data, so the source changes or nothing
  does. Not changed.
- No sentence of the chapter was found to contradict the code. These were checked: `stock_max_age_days` 14
  (`edakit/config.py:72`) and the 72 hours of JLCPCB's confirmation (`edakit/makers/jlcpcb.toml:13`).

## Assumptions

1. **The third is not reached**: −4.4 % of the words. The statements and the fixed outputs win, as the brief allows.
2. **The disclaimer appears once.** The "support, not legal advice" sentence stays in 17.2 and was cut in 17.9 (the
   M-6 bullet) and in 17.12 (item 3 of the order), reading CLAUDE.md's "says once" as once per page. If you want it
   at each regulatory passage, two sentences go back.
3. **17.13 stays in the chapter.** It is history of edakit, but it is the walkthrough's own section, `edakit/part.py`
   cites it, and 17.9 links to it. It was not moved to the history file.
4. **The 17.9 re-sign-off story was condensed.** The days ("a day later", "the same day") and the convert's key
   renames went to the history file. One paragraph keeps the three hash changes and the agents' looks.
5. **TOML comments now carry three statements of 17.11.** The circle as a square with half-side corners, what the
   board file holds, and why the "+" sits beside the holder are now said only by the comments of the quoted board file
   in the same section.
6. **The 17.6 bold titles became `###` headings** of at most five words, with the decision number first. Their codes
   moved into the text. Eight new anchors in all, none removed.
7. **The electrical reviewer's notes are a sub-list.** This was the only way to bring the item under 120 words
   without dropping a note.
8. **"a board of four parts"** replaces the superlative "the smallest board edakit makes". The check output's "4
   components" backs it.
9. **The subjects added to cross-references** (working rules, rule checks, conventions, roles, ordering, hashes and
   sign-offs, the decision, parallel sessions, parts without dialogs, routing, the placement plan, the template,
   datasheets, DOCS.quote) are my reading of each section's title. "(the template, 6.1)" for creating the EasyEDA
   project by hand is the weakest: 6.1's step 2 says it.
10. **"no project scripts or agents"** for "no scripts or agents of the project's own", taking the glossary's term.
11. **The chapter stays over 500 lines** (734) and grew by 20, from the headings and the sub-list. Shrinking it means
    cutting quoted output, which the brief forbids.
