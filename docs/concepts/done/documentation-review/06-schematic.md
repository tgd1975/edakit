# Documentation review: handbook/06-schematic.md (step D.5)

**Status:** condensed on branch claude/amazing-newton-ygty8a, not committed; open for the owner's review. Every
statement kept; the chapter did not give a third fewer words without losing statements.

## Measures

| | before | after |
| --- | --- | --- |
| lines | 260 | 285 |
| own words | 2546 | 2599 |
| mean sentence (words) | 25.2 | 19.8 |
| paragraphs over 120 words | 4 (179, 139, 335, 133) | 0 |
| sections over 80 lines without a subheading | 0 | 0 |
| "the reference project" | 2 (lines 43, 47) | 0 |
| bare references, dates | 0 | 0 |

`tests/test_style.py`: `paragraphs:handbook/06-schematic.md` and `words:handbook/06-schematic.md` now XPASS(strict) –
the chapter meets both rules and can leave `RED["paragraphs"]` and `RED["words"]`. The other rules were met before and
still are.

Why no third fewer: the text was a dense specification with little repetition, and most of it is named or mirrored
from outside.

- 6.6 is named by `edakit/docs.py:307`, `edakit/catalog/codes.toml:1331` (DOCS.quote), `skills/new-project/SKILL.md:72,130`,
  `skills/requirements/SKILL.md:183`, `skills/hardware-change/SKILL.md:64`.
- 6.5 is named by `skills/new-project/SKILL.md:63` (the drawing style); `agents/project-surveyor.md:30` opens the file
  for 6.5 and 6.6.
- The whole chapter is named by `edakit/catalog/codes.toml:671` (SYNC.schematic, "edakit handbook 6 and 13.2") and by
  the error of `edakit/schematic_layout.py:824` for a schematic file without `[layout] rows`.
- Many sentences are word for word in docstrings of `edakit/schematic_draw.py`, `edakit/schematic_layout.py`,
  `edakit/schematic.py`, `edakit/eda.py`, `edakit/docs.py` and `tests/test_schematic_draw.py`, and in other chapters
  (the bought/wired sentence in 3, 7, 8; the project-folder sentence in 2). Rule 5 of the brief kept them as written.

What went: the history (below). What came: the first paragraph, subjects for cross-references, a numbered list for
the steps of 6.1, a list for the three styles. The shorter sentences took their words back.

## Per section

- **H1 and its first paragraph** – new first paragraph: for whom, what works after the chapter. "for the documentation,
  for a look at a design before EasyEDA is involved" stays; "from the graph and the parts database alone" left the
  intro, as 6.5 says it. The aside "(the PCB would lose its schematic)" became an en-dash aside. Cross-reference "(6.5)"
  became "(the drawing, 6.5)". The table and the bought/wired paragraph are unchanged (used in chapters 3, 7, 8).
  Named from outside as "handbook 6" (codes.toml:671, schematic_layout.py:824): no statement left.
- **6.1 Generate the template** – the 179-word step paragraph became a numbered list of nine steps, every step, file,
  option and reason kept (blocks of 40, "bigger blocks crashed EasyEDA" as the reason). The story of the first run in a
  new project ("LED bar template", panel `generated_main`) and "in the reference project, and the script saved it"
  went to the history file; the rules stay: the name read again and put back, a panel of the template's name named in
  the output and not touched, an empty netlist read ten times. The reason for the ten reads stays as "EasyEDA can
  return an empty netlist after many writes". "Timing in the reference project" became "Timing on real projects",
  numbers unchanged. The save paragraph is unchanged (its message is asserted in `tests/test_eda.py:112` against the
  code, its wording mirrored in `edakit/eda.py:498`).
- **6.2 Check against the graph** – split into three paragraphs; "Read only (it activates the pages, though)" kept
  (docstring `edakit/schematic.py:423`). "A template once had a pin on two nets …; regenerating fixed it" became "a
  template can get a pin on two nets without anyone writing to it, and generating it again fixes that"; the original to
  the history file.
- **6.3 Copy and lay out** – "Once `copySchematic` … copied another project's schematic … now such a copy is deleted"
  became "`copySchematic` can copy another project's schematic instead – the bell's ESP32 THT template, 19 parts for a
  graph of 17", followed by what the run does, in three sentences; the original to the history file. The `layout` list
  is unchanged but for "four-branch crossings, which EasyEDA refuses" out of a parenthesis.
- **6.4 What made this hard (and is handled)** – unchanged list; "Details: chapter 9.3" became "The API calls behind
  each: 9.3 Schematic".
- **6.5 Drawn without EasyEDA** – named by `skills/new-project/SKILL.md:63` and `agents/project-surveyor.md:30`; no
  statement left, none moved out. The first sentence now says the drawing is a result on its own, without EasyEDA or
  KiCad (see Assumptions); the paragraph "A project without a PCB … never needs EasyEDA … For a PCB, EasyEDA's board
  schematic stays the one that counts" moved up from the end of the labelled part into this opening, so it is said
  once. Cross-references got subjects: "(the gate protocol's section 12, 8.3)", "(copy and lay out, 6.3)", "the names
  the check holds (6.2)", "(the parts fields, 4.1)". The symbol table is unchanged (no test or generator reads it). The
  `symbol` sides rule left its parenthesis as a sentence. **Wired through:** the three styles became a list; the
  335-word paragraph became a list of the four changes and three paragraphs (placement, router, colours and dots),
  every number and condition kept – costs 1/4/12/1/12, 180°, ten colours, the rails. The paragraph of measured
  crossings was split from the check's paragraph; "The check then tells …" kept word for word (docstring of
  `edakit/schematic_draw.py`).
- **6.6 Values quoted from the design data (DOCS.quote)** – named by code, catalog and three skills; only the 133-word
  requirements paragraph was split in two, at "Without `[project] requirements`", and "reads as if it did – DOCS.quote
  names it" became two sentences. Nothing else changed.

## History file

`/tmp/claude-0/-home-user-edakit/82157d39-3f55-5034-b81b-e1cbfc4ad998/scratchpad/history/06.md`, verbatim with its
section: the first-run naming story (6.1), the empty netlist the script once saved (6.1), the timing line with "the
reference project" (6.1, its numbers kept in the chapter), the drifted template (6.2), the copied bell template with
"Once … now" (6.3).

## Findings

Not changed – for the owner:

1. **6.5, colours of the wired drawing:** the chapter says "the supplies red and orange"; `SUPPLY_COLOURS` in
   `edakit/schematic_draw.py:85` holds four (red, orange, a dark yellow, a pink), and the module docstring says
   "supplies red". The chapter is not wrong for two supplies, but understates it beyond.
2. **6.5, "For a PCB, EasyEDA's board schematic stays the one that counts":** with `[project] toolchain = "kicad"`
   (chapter 16) it is the KiCad schematic. The sentence predates the KiCad tool chain; a source to check is chapter 16
   and `edakit/schematic_draw.py:1319` ("the KiCad schematic always does" have a frame).
3. **Docstrings that mirror the chapter** (`edakit/eda.py:432` keeps the first-run story with its date, LT-10): fine as
   code comments; noted because a later wording change in the chapter will not reach them.

## Assumptions

1. Sentences found word for word in code docstrings (not in tests that read the chapter) were treated as "used
   elsewhere" and left as written – this is the main reason the chapter did not get shorter.
2. 6.5's opening "a result on its own, without EasyEDA or KiCad": the section said "no EasyEDA, no bridge" and "the
   graph and the parts database are enough"; `edakit/schematic_draw.py` imports nothing of EasyEDA or KiCad, so
   "or KiCad" is a consequence, not a new claim. "A result on its own" is backed by the section's own sentences: the
   schematic for a project without a PCB, the build document of a hand-wired board, the drawing beside every gate
   protocol – while for a PCB the board schematic stays the one that counts.
3. Moving "A project without a PCB … the PCB hangs on it" to the start of 6.5 (same section, statements unchanged).
4. "a template once had a pin on two nets" → "a template can get a pin on two nets": the general form, as the
   catalog's SYNC.schematic `why` puts it ("EasyEDA can lose or move things").
5. "`copySchematic` can copy another project's schematic instead" for "Once … copied": the bell stays as the public
   example it is.
6. "Timing on real projects" keeps a dated measurement's numbers without its date: a reader plans with them. The 13-part
   figure may come from another project than the 123-part one; "real projects" covers both.
7. "A panel of the template's name is named in the output, not touched": "named" read as "reported" after
   `keep_schematic_name` in `edakit/eda.py`.
8. The section heading "6.4 What made this hard (and is handled)" kept as it is (rule 1), though it reads like history;
   its list is EasyEDA's behaviour today, no history.
9. No `> **State:**` line: nothing in the chapter is built offline only or planned.
