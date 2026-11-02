# Review of step D.5: handbook/03-hardware-graph.md

Status: condensed in place on 2026-11-01, not reviewed yet – the assumptions below are for the owner.

## Measures

| | before | after |
| --- | --- | --- |
| lines | 456 | 499 |
| own words (prose, without tables and code) | 3616 | 3608 (±0 %) |
| all words outside code and the generated section (tables and headings included) | 6260 | 6264 (±0 %) |
| mean sentence | 29.4 | 21.7 |
| test_style violations | sections 2 (3.1: 194 lines, 3.3: 110 lines without a subheading), paragraphs 10 (up to 311 words), words 6 ("the user"), dates 1 ("October 2026") | none |

`tests/test_style.py` now passes `sections`, `paragraphs`, `words` and `dates` for the chapter (XPASS strict):
`handbook/03-hardware-graph.md` can leave those four sets of `RED` in `tests/test_style.py`.

**Why not a third fewer.** Every `##` section but 3.4 is named by the automation (below) – 3.1 alone 24 times, 3.6 14
times, 3.3 11 times – so every statement stays in its section, and the chapter is almost all qualifications: field
names, codes, commands, file paths, the order in which a pin word is read, the exit codes. The repetitions that could
go were few (a pointer sentence in 3.1, the date, one story). The words saved went into the new first paragraph,
subjects for cross-references, and full stops where one sentence carried three asides. The change is in the reading:
sentences of 21.7 words on average instead of 29.4, no paragraph over 120 words (the longest was 311), and 11 `###`
subheadings, so that Claude and a reader land on the topic. The statements won.

**The 500-line limit.** The chapter is at 499 lines and `chapters` is not in `RED` for it: one more line fails
`tests/test_style.py`. The next change of this chapter has to cut what it adds.

## Where the automation names the chapter

- the file: skills `requirements:9` (3.6), `circuit-design:9` ("the graph is the only source"); `tests/test_plugin.py:206`
  reads 3.6 and wants "a choice the maker made is a requirement" or "who stated it" in it (both kept);
  `tests/test_version.py:64` uses the path only.
- 3.1 (24): `edakit/graph_form.py:49` (the header of every TOML graph), `edakit/convert.py:257`, `edakit/block.py:284`,
  `edakit/release/publish.py:63,322` (`purpose.use`), `edakit/national.toml:3` (`purpose.country`), `codes.toml`
  (STRUCT.* sources, STRUCT.identity "component fields type, lcsc, part, value"), skills `hardware-change:30`,
  `circuit-design:81`, `own-part:85`, `part-search:33` (`easyeda_device`), `new-project:107,129`, agent
  `project-surveyor:62`, `.claude/skills/add-feature:30` (the place of new graph fields).
- 3.2 (1 + in codes.toml with 3.1): `codes.toml:171` (STRUCT.entry, with 4.1).
- 3.3 (11): `catalog/levels.toml`, `paths.toml`, `tables/derating.toml`, `codes.toml:145,219,408,912`,
  `engines/requires.py:669`, skills `pcb-round:90,166` (0 Ω bridges), `part-search:71` (0 Ω joins its nets).
- 3.5 (7): `edakit/firmware.py:11,434,498`, skills `hardware-change:66`, `circuit-design:136`, `new-project:71,129`.
- 3.6 (14): `edakit/requirements.py:13,22,35,713`, `edakit/docs.py:160`, `codes.toml:1346–1429` (DOCS.*), skills
  `requirements:45`, `circuit-design:19`, `new-project:112`.
- "handbook 3" (2): parts entries C5438445 and C910544 (net `fn` i2s lines – the `fn` row of the field table, kept).

## Per section

**Introduction (under the H1).** New first paragraph: for whom, what after. "The form every project had until October
2026" left for the history file; JSON is now "the older form", kept until the project converts. The rest kept,
split into shorter sentences.

**3.1 Format** (named; statements kept). Six `###` added by topic, statements where they were: "Tables, keys and
comments", "The JSON form", "Fields", "A pin by number, name or role", "The JSON generated beside a TOML graph",
"Moving a project to TOML" – the last three were bold paragraph titles before. Cut: the sentence "Nets, `nc`,
locks, loop ends and cables name pins by name or role (below)" (the subsection that follows says it), the pointer
"(the `pins` row below)", `[layout]` as a third example of a map table. Split into paragraphs: the pin rule (251
words → three paragraphs), the generated JSON (192 → two), the conversion (311 → three). Reworded, meaning kept:
"It writes no comment but the two lines at the top" → "Its only comments are the two lines at the top"; "both into
`rehashed`" → "the old and the new into `rehashed`" (as `edakit/convert.py:225` says); "what they read did not change,
only its hash" → "only the hash of what they read changed". The field table and the code examples are unchanged.

**3.2 Conventions that save trouble** (named). The first item split into two paragraphs of one list item (how to
write a pin; how to see the numbers); "Write the roles into the parts entry" moved up beside the sentence on code
that asks for "the cathode", in the same item. Asides turned into sentences. No statement cut.

**3.3 Rule checks** (named). Five `###` added: "The codes", "0 Ω bridges", "Severities", "What went unchecked",
"Polarity" (the first three titles were bold or "Severities:" before). The introduction of the generated table
reworded (allowed by the brief); the table itself untouched. "What went unchecked" (a paragraph of about 450 words)
split into five paragraphs: the data gaps and RGB LEDs, the one line and `--coverage`, what is not simulated over
time, cables without `i_max_a`, the line's numbers and where the currents come from. "Chapter 14.2 has the model" →
"the catalog (14.2) has the model". The sample output lines are kept verbatim.

**3.4 Working rules** (not named). Asides turned into sentences; the commands of items 3 and 5 kept although 3.1 and
3.5 state them too – a command is a statement, and the list is the one place that says what to do before a commit.

**3.5 The firmware contract** (named). The story of the origin project's exporter ("found a cathode by the name 'K'")
went to the history file; the rule "only roles decide" stays word for word. The table is unchanged.

**3.6 Requirements** (named; read by `tests/test_plugin.py`). "The user" (6) and "the owner" (2) in the chapter's own
sentences became "you". "Inputs, not outputs" (182 words), the paragraph on `source`/`from` (133) and "Who writes it"
(150) each split in two; nothing cut. "The roles: 14.1" stays.

## To the history file

`/tmp/claude-0/-home-user-edakit/82157d39-3f55-5034-b81b-e1cbfc4ad998/scratchpad/history/03.md`, verbatim with the
section each came from: the date "until October 2026" of the JSON form (introduction) and the exporter story of 3.5.

## Findings (not changed – sources)

- `edakit/catalog/codes.toml:219` (LIM.v sources) and `edakit/catalog/tables/derating.toml:6` cite "edakit handbook
  3.3 (the margins of the reference project)". Section 3.3 says nothing about margins or derating (5.3 does:
  `derating.p` of sim.json), and "the reference project" leaves the documentation. The source should name 5.3, or
  the project by its own record.
- `skills/pcb-round/SKILL.md:90` cites "handbook 3.3, 7.3" for "the assembly instruction's reference lead";
  `codes.toml:912` cites "handbook 3.3 (P-7)". Section 3.3 has neither a reference lead nor P-7 outside the generated
  table (where PARTS.fact "replaces P-7"). The skill's and the catalog's citation should probably name 7.3 alone, or
  4.1 for the lead facts.
- 3.3 names "decision 17 of rules-at-scale.md" and "decision 22" without a path; both are in
  `docs/concepts/done/rules-at-scale.md` (items 17 and 22). A link would let a reader follow them. Not changed: the
  brief adds no claims, and a link is the owner's call.
- The `purpose` row of the field table says "without it Germany's, as before" – "as before" is history in a table
  cell. Left, since the table was kept as it is.

No sentence was found that contradicts the code; spot checks: `--write` refuses a JSON graph and `--check` exits 2
(`edakit/graph_form.py:124–150`), the conversion's `rehashed` (`edakit/convert.py:225`).

## Assumptions

1. **The two big tables stay tables.** The field table of 3.1 (cells of up to about 220 words: `cables`, `purpose`,
   `config, states`) and the key table of 3.5 (`pins`, `bus_speed`) are the reference Claude reads when a skill says
   "handbook 3.1"; turned into prose they would scatter what is looked up by key, and no test or generator reads them.
   They are unchanged.
2. **G-7 stays.** "G-7, the graph's polarity check before the codes, is retired" reads as history, but the generated
   table lists every old number a code replaces, and a reader who looks for G-7 finds it here only. Kept, shortened.
3. **"You" for the one who accepts.** In 3.6 "`should` is a warning the owner accepts" became "a warning you accept",
   and "each marked inferred until the owner says yes" became "until you say yes" – "the owner" there is the
   project's owner, the reader of this chapter.
4. **The first paragraph** names three things a reader can do after the chapter (write the graph, read its findings,
   keep the firmware contract and the requirements file beside it); the conventions and the working rules are not
   named in it.
5. **`[layout]` dropped as an example** of a map table in 3.1 – one of three examples; `layout` stays in the field
   table.
6. **The 0 Ω and cable output lines stay inline code** across two lines, as before; a code block would hold one line
   of up to 190 characters.
7. **Cross-references with their subject** were added where the number stood after a list or a punctuation mark
   ("the working rules, 3.4", "the generated JSON, 3.1", "finding parts, 4.2", "the simulation's checks, 5.3", "the
   working agreements, 11.4", "configs, 4.1"); a number after a noun that names it ("the circuit hash (8.2)") was left.
8. **3.4 is left nearly as it was**, with its repetitions of 3.1 and 3.5, because each repeats a command.
