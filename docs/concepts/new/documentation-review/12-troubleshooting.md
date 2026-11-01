# Review of step D.5: handbook/12-troubleshooting.md

Status: words and references fixed in place on 2026-11-01, not reviewed yet – the assumptions below are for the owner.

## Measures

| | before | after |
| --- | --- | --- |
| lines | 67 | 68 |
| own words (prose, without the table) | 3 | 32 |
| mean sentence | 3.0 | 10.7 |
| test_style violations | words 1 ("the user", line 8) | none |

`tests/test_style.py` now passes `words` for the chapter (XPASS strict): it can leave that set of `RED`.

**Why no third fewer.** The chapter is one table a reader in trouble scans by symptom, and the whole chapter is named
by the automation as "handbook 12" or by path: `edakit/eda.py:682`, `edakit/route.py:2210` ("handbook 12, M-10"),
`edakit/doctor.py:5`, `:67`, `:81`, `:137`, `edakit/schematic.py:487`, `skills/start/SKILL.md:9`. Its rows quote
messages as edakit prints them. So the table stays a table, every row stays, and only words and cross-references
changed. The own words grew by the new first paragraph.

## Per section

The chapter has no `##` section.

- **Opening** – "Start with `edakit doctor`." kept; before it a first paragraph: for you when a command, a check or
  EasyEDA fails; find the symptom, often the printed message, and the table gives cause and fix.
- **Rows, words** – "only the user can reconnect" → "only you can reconnect, not Claude" (MCP tools missing); "the
  owner gives the consent or signs in" → "you give the consent or sign in" (the skill cart stops at a field).
- **Rows, cross-references** – each now names its subject: "(chapter 2.6)" → "(EasyEDA without background throttling,
  2.6)", "(chapter 2.5)" → "(the bridge extension, patched, 2.5)", "(2.5)" → "(the bridge extension, 2.5)", "(chapter
  9.3)" → "(the schematic API, 9.3)", "(E-17, 9.2)" → "(E-17; the editor state, 9.2)", "(6.3)" → "(copy and lay out,
  6.3)", "(6.1)" → "(generate the template, 6.1)", "(7.5)" → "(routing with Freerouting, 7.5)", "(4.4)" → "(library
  footprints, 4.4)", "(7.4)" → "(the placement plan, 7.4)", "(chapter 11.3)" → "(long runs, 11.3)", "(8.4)" →
  "(ordering at the manufacturer, 8.4)". "(start skill, section 4)" already named its subject.
- No cell rewritten otherwise; quoted messages, commands and codes unchanged.

## To the history file

Nothing (`/tmp/claude-0/-home-user-edakit/82157d39-3f55-5034-b81b-e1cbfc4ad998/scratchpad/history/12.md` says so).

## Findings

- `edakit/doctor.py:67`, `:81`, `:137` and the other places point to "handbook 12" as a whole; with about 60 rows a
  reader has to search. An anchor per topic (`###` groups: bridge and server, editor, schematic, routing and pours,
  silkscreen, ordering) would let a message name its row. Not done – a heading inside the table would split it, and
  the brief keeps the table whole.
- Several cells are paragraphs (GEO.ring, GEO.spacing at hand-soldered joints, the skill cart's stop). They are the
  table a reader in trouble uses; left as they are.

## Assumptions

1. "only you can reconnect, not Claude" says what "only the user" meant: the person at the keyboard, not the session.
2. "you give the consent or sign in" – the person running the skill cart, who is the project's owner; the chapter's
   own sentences no longer use "the owner".
3. "reported 320 → 0" stays: the measurement behind the DRC remedy, not history.
4. The message quoting "Christmas bell ESP32 THT template" stays – a quoted output, and the bell is the public example.
