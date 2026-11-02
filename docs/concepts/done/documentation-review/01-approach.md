# Review of step D.5: handbook/01-approach.md

Status: condensed in place on 2026-11-01, not reviewed yet – the assumptions below are for the owner.

## Measures

| | before | after |
| --- | --- | --- |
| lines | 106 | 104 |
| own words (prose, without tables and code) | 1069 | 969 (−9 %) |
| mean sentence | 23.8 | 23.1 |
| test_style violations | paragraphs 1 (182 words), words 1 ("The reference project"), dates 1 ("19–23 October 2026") | none |

`tests/test_style.py` now passes `paragraphs`, `words` and `dates` for the chapter (XPASS strict): the chapter can
leave those three sets of `RED`.

**Why not a third fewer.** The chapter has no section numbers and nothing names a section of it; two skills open the
file for the "why" (`skills/hardware-change/SKILL.md:10`, `skills/new-project/SKILL.md:9`). Most of its prose is the ten
principles, each already two or three sentences of statements. A new first paragraph (27 words) was added. Without the
history paragraph's detail and the asides, 969 words is what is left without dropping a statement; the statements won.

## Per section

- **(new) first paragraph** – for whom and what after: why edakit works as it does; the pipeline, the ten principles,
  what it cannot promise.
- **The idea in one paragraph** – the 182-word paragraph split in two: the idea (118 words) and a second paragraph on
  a project without a PCB and on KiCad. "the bill of materials" → "the BOM"; "that go to the manufacturer" dropped
  (implied by the Gerber files and the diagram); "only a run that says RELEASED" → "only a RELEASED run". "(chapter 16)"
  now names its subject. "Nobody draws a wire by hand" kept word for word (the README uses it).
- **Why not just draw it in EasyEDA?** – the three examples kept; "the project this toolkit comes from" → "a real
  project" (the original sentence to the history file). In the bullets: one example check instead of three (see
  Assumptions); "A JSON file with pins and nets" → "pins and nets" (see Findings); the regeneration bullet's "That is
  what makes the EasyEDA side safe" → "That makes EasyEDA safe".
- **Principles** – all ten kept with their bold titles; asides shortened ("(or a later you)" dropped), "The human is
  asked" → "You are asked", the two bare "(chapter 14)" / "(14.1)" now name their subjects ("designing a circuit,
  chapter 14", "roles, 14.1").
- **What it achieved** – the reference project's description and its dates went to the history file; kept, dateless:
  a real project of about 120 parts, five days from the first graph to released files, a power redesign in one more
  day, one order and no prototype round, the four findings and the layout review agent's finding, each became a check,
  with a link to chapter 13. "What it does not give you" kept word for word (the start page links it).
- **How the rest of this handbook is organised** – unchanged.

## To the history file

`/tmp/claude-0/-home-user-edakit/82157d39-3f55-5034-b81b-e1cbfc4ad998/scratchpad/history/01.md`: the sentence "All of
these happened … in the project this toolkit comes from …" and both paragraphs of "What it achieved" as they stood
(board description, 98 nets, 19–23 October 2026, "fixed by swapping the nets in the graph", "late").

## Findings

- "A JSON file with pins and nets is something a language model reads reliably" (Principles' preamble, old line 33):
  the graph is TOML now, JSON only in a project not yet converted (the chapter's own first paragraph). Reworded to "pins
  and nets" without a format – the owner may want to check the wording.
- The chapter table at the end repeats `handbook/README.md`'s table with other words (contents here, "read it when"
  there) – one of them could link the other. Left as it is.

## Assumptions

1. The dateless "real project" achievement (five days, one more day, about 120 parts, the findings) stays in chapter 1
   as the evidence for the approach; only the description, the dates and the asides went to history. Alternative: move
   all of "What it achieved" except "What it does not give you" to chapter 13.
2. One example check instead of three in "Claude can reason about the circuit": "every IC supply pin has a capacitor"
   kept; "every input has a driver or a pull resistor" and "a reversed supply reaches only the anode of a blocking
   diode" dropped as further examples of the same statement.
3. The 18-mil example in principle 7 stays (an illustration, not a dated story).
4. The chapter table stays (navigation; tables are not counted as prose).
5. The heading "Why not just draw it in EasyEDA?" keeps its "just" – headings are addresses.
