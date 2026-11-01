# Review of step D.5: handbook/10-reference.md

Status: condensed in place on 2026-11-01, not reviewed yet – the assumptions below are for the owner.

The chapter is the reference (register "reference" of `docs/style.md`): fragments in entries and cells, one entry per
thing, as long as the things it lists. 10.5 had been converted by the lead before this step (one entry per command,
generated synopsis blocks); 10.7 is generated. Neither generated block nor any `#`/`##` heading was touched.

## Measures

| | before (f2cc4fe) | after |
| --- | --- | --- |
| lines | 1240 | 1402 |
| own words (prose, without tables, code and generated text) | 5503 | 7120 |
| all words outside the generated blocks (tables included) | 11188 | 11439 (+2 %) |
| mean sentence | 18.4 | 17.9 |
| test_style violations | sections 2, paragraphs 8 (235, 300, 135, 225, 193, 131, 129, 149 words), words 5 ("the user"), dates 3 | sections 1 (10.7), dates 2 ("May 2026", twice) |

`tests/test_style.py` now passes `paragraphs` and `words` for the chapter (XPASS strict): the chapter can leave those
two sets of `RED`. It stays in `sections` (10.7: 95 lines of the generated map of before – only a heading inside the
generated block would split it), `chapters` (1402 lines; 10.5 alone, mostly generated synopses and one entry per
command, is about 720 lines) and `dates` (see Assumptions 1).

**Why the words did not fall by a third, and why own words and lines rose.** The task for 10.1 to 10.4 was "their
tables kept to short cells, the explanation below the table" (concept, "The reference, generated"). That moves text out
of table cells – which the test does not count – into entries below the table, which it does count, and gives each
explanation its own lines. Counted over everything outside the generated blocks the chapter is about 2 % longer: the
new first paragraph, the subheadings and a lead-in per list. A reference's sentences are keys, defaults and conditions;
I found no restatement to cut without dropping a statement, so the statements won (brief rule 6).

## Per section

- **(new) first paragraph** – for whom and what after: you setting up or changing a project, Claude looking something
  up; every key of the four project files, what each command reads and writes, where a project keeps its files.
- **10.1 edakit.toml** (named: `edakit/agreements.py:8`, `edakit/config.py:4`, `edakit/config.py:1021`,
  `edakit/makers.py:1`, `tests/test_gate.py:446`, `skills/new-project/SKILL.md:10,25,105`,
  `agents/project-surveyor.md:27`). The lookup sentence and "What one role decides lives in a file of its own, with one
  owner and one hash" kept word for word (quoted by `edakit/config.py:4`). File table: every row kept; the cells of
  `hardware/signoff.json` and `hardware/scripts.lock` shortened, their detail as two entries under the table (scopes,
  `parts`, `rehashed`; the stamp's content, `pcb dump`/`route all` taking off their changes). `graph.toml` cell
  reworded: "in a project that has not converted `hardware/graph.json`, the same graph as JSON" → "before `edakit graph
  convert`, the same graph as `hardware/graph.json`". "the user" → "you" (twice). `[project]`: every key row kept; the
  long cells of `agreements`, `graph`, `requirements`, `domains`, `toolchain` cut to a short meaning, the rest as entries
  below the table, every statement kept. One duplicate dropped: the variant's example path list
  (`["../../hardware/requirements.toml", …]`) stands in 10.4 only; 10.1 says a variant names both files and points to
  the requirements file (10.4). `[boards.<name>]`: `bought`/`wired` cells shortened, detail as entries ("made by nobody",
  "hand-wired, no PCB" kept word for word – they stand in `edakit/config.py`, `edakit/order.py` and tests).
  `[release]`: the 235-word paragraph is now one entry per key (`layout_files`, `state_files`, `hash_ignore`,
  `assembly`, `[[stages]]`, `archive`, `publish`), every value and default kept. `[cost]`: the `fees` cell shortened,
  its rule (newest date per fee, `pcb.qty`, `pcb.board`, `cart actual`, no shipped table → not priced) as a paragraph
  under the table. `[cart]`: the 300-word profile paragraph is now a list by topic (form, files, BOM/CPL, assembly,
  cart) plus a short list of the three field flags (`more`, `when`, `checkout`); "the owner is logged in in their
  browser" → "you are logged in in your browser". `[scripts]`: the intro paragraph split in two; the `phase` and `at`
  cells shortened, their detail as entries. `[agents]`: "never the owner's `M-2` or `M-4`" → "never your `M-2` or
  `M-4`"; the `scope` cell shortened, where each scope reviews as a sentence below – the pairing (circuit → circuit
  review, layout → round review, fab → layout review) checked against `OWN_HOOK` in `edakit/scripts.py:1451`.
- **10.2 The board file** (named: `edakit/config.py:80`, `edakit/makers.py:5`, the four profiles
  `edakit/makers/*.toml:2`, `skills/pcb-round/SKILL.md:13`, `agents/project-surveyor.md:27`; "handbook 10" in
  `edakit/catalog/codes.toml:933` for `clearance_mm`/`min_width_mm` 0.25 – kept). New `###`: "Keys of the board file",
  "[silk]", "[routing], [copper], [net_classes]", "[order] of the board file" (no section went over 80 lines before
  them: 103). Every key row kept; the long cells of `place`, `uniform`, `[[pours]]`, `pour_inset_mm`, `[looks]`,
  `thickness_mm` cut, their detail as entries under the table; the `silk` cell (about 230 words) became the list under
  "### [silk]". `[routing]` (225 words) and `[copper]` became one entry per key; `[net_classes]` unchanged. The
  `[order]` paragraph (193 words) split into three: the layers (the sentence "the board edakit assumes when nothing is
  said, the same for every maker … Three layers, the later one wins per key" kept, quoted by `edakit/config.py:80`),
  the `[looks]` default of `mark` ("decided in the files and so in the fab hash before the gate and M-5" kept), the
  profile and the "Board" column. In the `[order]` table the cells of `mark`, `tab_zones` and `customs` shortened, their
  detail as entries; `customs` "the owner's" → "yours", "asks the owner" → "asks you". "an GEO.silk warning" → "a".
- **10.3 The schematic file** (named: `skills/circuit-design/SKILL.md:138`, `skills/new-project/SKILL.md:108`,
  `agents/project-surveyor.md:31,103`). The 131-word paragraph is one entry per key; "it changes no hash" and "without
  the file `edakit schematic draw` arranges the schematic by itself" moved to the top of the section.
- **10.4 The requirements file** (named: `skills/requirements/SKILL.md:10,101`, `edakit/release/publish.py:13`,
  `tests/test_publish.py:98`; `tests/test_plugin.py:206` wants "who stated it" in it – kept). `verify` and `status`
  cells shortened; the four kinds of `verify` as entries, the rule of a draft as a paragraph ("A draft binds nothing
  yet" kept word for word – it stands in `edakit/release/gate.py` and chapter 8). "the user" → "you" (twice), "the
  owner confirms" → "you confirm".
- **10.5 Commands** (named: `edakit/design.py:190`). Generated blocks and `### edakit …` headings untouched. The
  129-word intro is a list: exit codes, uv from snap, progress lines, project scripts. `graph convert`: its 149-word
  Writes line split into Writes, Refused, Left by hand – same words. `part sign`: "the owner's signature" → "the
  signature of NAME" (the `--by NAME` of its synopsis). The KiCad paragraph at the end: "is in 16.4" → "is in the KiCad
  chapter (16.4)", and the missing blank line before "## 10.6" added. No other Reads/Writes line changed.
- **10.6 Files in a project** – unchanged.
- **10.7 Check IDs of before** – unchanged.

## History file

`(the owner's decision of 2026-10-31)` from the `[order]` paragraph of 10.2, verbatim with its context, in
`/tmp/claude-0/-home-user-edakit/82157d39-3f55-5034-b81b-e1cbfc4ad998/scratchpad/history/10.md`. Nothing else in the
chapter is history.

## Findings

Not changed – for the owner.

1. **DOCS.derived is missing in the chapter's lists of requirement checks.** 10.1 (`requirements`: "`edakit check`
   checks it (DOCS.ref to DOCS.draft)") and 10.5 (`edakit check` Reads: "DOCS.ref, DOCS.need, DOCS.evidence,
   DOCS.draft") stop at DOCS.draft; `edakit/requirements.py:76` runs `DOCS.derived` too, and 10.4 says "DOCS.ref to
   DOCS.derived". 10.4's "A draft binds nothing yet: DOCS.ref to DOCS.draft only warn about it" is right as far as it
   goes – DOCS.derived warns for a draft too (`edakit/requirements.py:40`).
2. **"✓ yes, – no" in the intro of 10.5** does not match the entries, which write "EasyEDA: no" and "EasyEDA: ✓"
   (and "– / ✓" where both occur). The intro sentence is outside the generated blocks; the entries are the lead's
   conversion. One of the two should follow the other.
3. **`distributors` … "(chapter 4.2)"** names a section as a chapter – a nit, left as is.
4. The catalog's rule of DOCS.ref (`edakit/catalog/codes.toml:1353`) says "once the user accepts the requirement" – a
   source text with "the user", rendered on the catalog page, not in this chapter.

## Assumptions

1. **"since May 2026" stays** (twice: `mark` entry, `barcode` row). It is a dated fact about JLCPCB's form that
   `skills/release/SKILL.md:106`, `edakit/release/order_sheet.py:27`, `edakit/makers/jlcpcb.toml:87` and the sources of
   FILES.order (`edakit/catalog/codes.toml:1113`) rely on – "a date a finding or a skill relies on stays". The chapter
   therefore stays in `RED["dates"]`. The alternative is to drop the date ("JLCPCB prints none") and leave it to the
   catalog page.
2. **The variant's example path list dropped from 10.1**, kept in 10.4, which owns the variant; 10.1 keeps the
   statement that a variant names both files. `skills/new-project/SKILL.md` reads 10.1 for variants – it gets the
   statement and the pointer.
3. **Table cells end with "– below"** where their detail moved under the table, so a reader of the table knows there
   is more. Each costs a word; without them the entries would still be found by their key.
4. **Lists under tables** use the form "- `key` – …" (an entry per key), not definition lists; `docs/style.md` asks for
   "entries", and plain Markdown lists render on GitHub and the site alike.
5. **10.5 left as the lead converted it**, apart from the intro list, the `graph convert` split (the only Reads/Writes
   item over 120 words) and "the owner's signature". Other long Reads/Writes lines (`edakit check`, `graph json`,
   `cart check`) are lists of files and codes without nesting to undo.
6. **The `[agents] scope` pairing** is now stated per scope (circuit → circuit review, layout → round review, fab →
   layout review); before, the three scopes and the three reviews were listed side by side. The pairing is the code's
   (`OWN_HOOK`), so this is a reading, not a new claim – but worth a look.
7. **10.6 not shortened** although its descriptions overlap the file table of 10.1: 10.1 has the columns "Written by"
   and "Hash", 10.6 the whole tree including `build/`; both are lookup places.
8. **Length.** No attempt at 500 lines: the reference register says "as long as the things it lists", and 10.5 and 10.7
   alone exceed it. The chapter stays in `RED["chapters"]` and `RED["sections"]` (10.7, generated).
