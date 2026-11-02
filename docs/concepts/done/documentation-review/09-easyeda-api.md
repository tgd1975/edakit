# Review of step D.5: handbook/09-easyeda-api.md

Status: condensed in place on 2026-11-01, not reviewed yet – the assumptions below are for the owner.

## Measures

| | before | after |
| --- | --- | --- |
| lines | 102 | 103 |
| own words (prose, without tables and code) | 208 | 208 |
| mean sentence | 17.3 | 13.9 |
| test_style violations | words 2 ("the reference project", "the user" – in "user preferences"), dates 14 | none |

`tests/test_style.py` now passes `words` and `dates` for the chapter (XPASS strict): it can leave those two sets of
`RED`.

**Why not a third fewer.** Chapter 9 is reference by the style guide's registers ("as long as the things it lists"):
almost all of it is the four tables, one row per behaviour, and the prose outside them is the opening and the Gerber
list. Sections 9.2 and 9.4 are named by the automation – `edakit/eda.py:411`, `:427`, `:741`, `edakit/pcb.py:2221`,
`edakit/footprint.py:71`, `edakit/drc_rules.py:9`, `:284`, `edakit/catalog/codes.toml:705` ("'Footprints in the
project': placed parts keep their embedded copy until deleted and recreated"), `skills/start/SKILL.md:32`, `:35`,
`tests/test_footprint_data.py:761`, `tests/test_drc_rules.py:7` –, 9.3 is linked by anchor from
`handbook/06-schematic.md:130`, and `skills/start/SKILL.md:8` opens the file for "every API quirk". The rows were left
as they were except for the dates, two merged duplicates and the cross-references; no row became prose or an entry, so
that every statement stays in the row and section that names it.

## Per section

- **Opening** – the dated "found the hard way" paragraph to the history file. New first paragraph: for whom (calling
  the API directly, or wondering why edakit's code looks as it does) and what after. The versions stay as the state the
  statements rely on: EasyEDA Pro 3.2.206 (Linux) with easyeda-mcp-pro 1.4.0, the "3.2.209:" sentences from the live
  check, each call checked against the JSDoc first. The pointer "(upstream/README.md)" after "JSDoc" was dropped – the
  next sentence links the same file. The two lines on `easyeda_api_call` and `easyeda_api_inventory` unchanged.
- **9.1 Server and bridge** – ODB++ row: date out of "Live on 2026-11-01 (…)"; "(8.4, SYNC.odb)" → "(ordering at the
  manufacturer, 8.4; SYNC.odb)".
- **9.2 Editor state** (named by `edakit/eda.py:427`, `skills/start/SKILL.md:32`, `:35`) – Active tab row: the date
  after "the bell reported the BOM tool mixing tabs" out. Nothing else changed; "Not run live yet." stays in its row
  (a section-wide state line would mislead – it is one row's state).
- **9.3 Schematic** – Renaming row: "Once (2026-10-31, after hours of runs)" → "Once, after hours of runs,"; "3.2.209
  (2026-11-01):" → "3.2.209:".
- **9.4 PCB** (named by the places above) – dates out of The one click left, DRC rule set, DRC after API changes,
  Pours, Footprints in the project. DRC rule set: "Read on 3.2.206 on 2026-10-22 (the reference project; …)" → "Read
  on 3.2.206 from a real project (…)", the fixture path kept; "the user preferences (`web.db`)" → "the client's
  preferences (`web.db`)". Merged: the two "3.2.209: `SCH_PrimitivePin.modify` … is saved" sentences of Footprints in
  the project into one (E-11, #49 kept); "`LIB_Footprint.getDocumentSource` hung for minutes" moved from Footprints in
  the project to the Footprint geometry row, before the 3.2.209 statement on the same call (#50) – same section.
  "(7.5)" twice → "(routing, 7.5)", "(4.5)" → "(own parts, 4.5)".
- **9.5 Gerber export** – unchanged.

## To the history file

`/tmp/claude-0/-home-user-edakit/82157d39-3f55-5034-b81b-e1cbfc4ad998/scratchpad/history/09.md`: the opening paragraph
verbatim (19–26 October 2026, 1 November 2026, "found the hard way") and each dated phrase taken out of the tables, as
it stood.

## Findings

- `edakit/drc_rules.py:9` and `edakit/eda.py:741` carry the date of the DRC-rule live check (2026-10-31) with "handbook
  9.4"; the chapter no longer gives the date. The statement is still in 9.4 – the docstrings are not wrong, only more
  detailed. Not changed (code).
- `edakit/catalog/codes.toml:705` cites "the reference project's hardware/easyeda/led_footprints.py" with a date – data,
  not touched; the words of the chapter's style guide do not reach it.
- 9.3 Renaming holds two "3.2.209:" observations that read against each other at first sight ("renames the schematic
  passed" vs. "answer false when [the UUID] is not [in the tree]"). Both are true by the text; the date that told them
  apart is gone. The owner may want one sentence that joins them.

## Assumptions

1. The dates of the live checks are history; the version numbers and "live" marks carry the state a reader needs. No
   skill or finding relies on a date of this chapter (grep over `edakit/`, `skills/`, `agents/`, `.claude/`).
2. The plan steps "ordering step 0b", "step 2.2", "step 3.6" stay – they name the probe, not a time.
3. The tables stay tables (reference register; the rows are what 9.2 and 9.4 are named for). Their long cells – DRC
   rule set, Pours, Footprints in the project, Renaming – could become entries under `###` subheadings in a later step.
4. "the user preferences" is EasyEDA's own name for `web.db`; "the client's preferences" says the same without the
   counted word.
5. The Christmas bell stays where it is cited (9.2, 9.4).
