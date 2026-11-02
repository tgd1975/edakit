# Review of step D.5: handbook/14-design.md

Status: condensed in place on 2026-11-01, not reviewed yet – the assumptions below are for the owner.

## Measures

| | before | after |
| --- | --- | --- |
| lines | 399 | 453 |
| own words (prose, without tables and code) | 3596 | 4054 (+13 %) |
| all words outside code and the generated section (tables included) | 5168 | 5170 (±0 %) |
| mean sentence | 26.4 | 20.5 |
| test_style violations | sections 1 (14.2: 99 lines without a subheading), paragraphs 6 (136–204 words), words 10 ("the user" 8, "the reference project" 2) | none |

`tests/test_style.py` now passes `sections`, `paragraphs` and `words` for the chapter (XPASS strict):
`handbook/14-design.md` can leave those three sets of `RED` in `tests/test_style.py`.

**Why not a third fewer.** Every `##` section but 14.6 is named by the automation (below), so every statement stays
in its section, and the chapter is mostly qualifications: key names, codes, commands, paths, part numbers, the
pipeline's paths and checks. The "own words" rose because the roles table of 14.1 – cells of up to 110 words – became
a list of entries, which the measure counts as prose and the table was not; counted with its tables the chapter is as
long as before. The cuts (examples, repetitions, one history paragraph) are paid for by the new first paragraph, the
subjects added to cross-references and the domain table's headers. The statements won. Lines grew because table rows
became wrapped entries and five `###` were added; the chapter stays below 500 lines.

## Where the automation names the chapter

- the file: skills `circuit-design:10` ("how rules, hints and blocks fit together"), `propose-rule:9` ("the whole
  loop", 14.4), `.claude/skills/add-rule:9` (14.2); `tests/test_pages.py:34–43` and `tests/test_proposal.py:233` use
  the path only, not the text.
- `handbook 14.1`: `edakit/handover.py:2`, skills `pcb-round:11`, `hardware-change:14`, `new-project:166`; README.md
  line 183 links `#141-roles`; glossary (Agent, Hand-over, Station).
- `handbook 14.2`: `edakit/convert.py:219`, skill `new-project:82` (the domains a part suggests), `.claude/skills/
  add-rule:9`; README.md line 231; glossary (Catalog, Code, Domain, Engine, Finding, Grade, Severity, Topic and more).
- 14.3: glossary (Hint); chapters 3 (lines 156, 239, 309).
- `handbook 14.4`: `edakit/proposal.py:6`, skills `circuit-design:76`, `propose-feature:10`, agent
  `electrical-reviewer:46`, `.claude/skills/triage-rule:9`, `.github/workflows/proposals.yml:3`; README.md line 188
  links `#144-from-a-finding-to-a-rule`; glossary (Proposal); chapters 11 and 15.
- `handbook 14.5`: `tests/test_block_keys.py:1`, `.claude/skills/add-rule:102` ("Table in handbook 14.5"); chapter 10.

No `#` or `##` heading changed; the generated HINT table is byte for byte the same; the existing `###` "The proposals
Action" kept its text (no link to it found).

## Per section

**First paragraph.** Says for whom (you, designing a circuit or adding knowledge) and keeps the old two sentences;
the list of the chapter's topics I drafted was cut again as a restatement of the headings.

**14.1 Roles** (named). The table became a list of entries, one per role, each cell split into sentences; no statement
dropped or moved out of the section. "The user" became "you" (surveyor, requirements engineer, decider); "the
decider's browser" stays for the order. The example of the project reviewer – "the reference project's pcb-pruefer
reviews the rounds and signs M-5" – went to the history file; the statement it illustrates (in place of the edakit
reviewer it replaces) stays. The hand-over paragraph was split in two. Cross-references got subjects: "(a project,
2.7)", "(requirements, 3.6)", "(finding parts, 4.2)", "(project scripts and agents, 8.6)", "(ordering, 8.4)",
"(requirements at the gate, 8.7)", "(the project files, 10.1)".

**14.2 The catalog** (named). Three `###` added by topic, statements where they were: "Engines and codes", "Accepting",
"Domains and purpose" – the bold lead-ins **Engines.** and **Accepting.** and **Domains.** became these headings,
**Codes.**, **Purpose.** and **Findings come only from code.** stay bold. The code examples went from three to two
(`LVL.boot` cut). The domains paragraph (204 words) became a table domain / switches on / suggested by, followed by
the rest of the paragraph; the sentence "A part in the graph suggests the domain it needs – a USB-C receptacle `usb`,
a part that transmits `radio`" was merged into the table and the note sentence ("A domain a part suggests that is left
out of an explicit list gives one note, `STRUCT.domain`: no silent gap"). The `mains` row says "no check" in its
column – see Assumptions.

**14.3 Hints** (named via glossary and chapter 3). The three examples of knowledge without a rule became one (the
debounce); the sentence introducing the generated table now says "The catalog's hints:". The parts-database notes kept
the ESP32 example and dropped the STM32 one. The sentence with "a JSON graph has the same keys" stays as it was – the
formula recurs in chapters 7 and in the skill circuit-design.

**14.4 From a finding to a rule** (named). Of the three lessons in the introduction one example stays. Item 1 was split
into two paragraphs (156 words before); its "a fact (a limit, a default, a table row)" now points to the kinds in step
5, where the same list stands. Item 6 was split in two. "The user" became "you" in items 2, 4 and 7; in item 6 "the
user merges it" became "the repository owner merges" – see Assumptions. The paragraph "REQ.missing (flyback diode) and
REQ.missing:cc … the reference project's buzzer stage …" went to the history file; its CircuitSmith half is already in
14.6. In "### The proposals Action" "the owner" became "the repository owner" or "they/their", the queue paragraph got
shorter sentences. Every check, path, kind, command and condition of the pipeline stays.

**14.5 Building blocks** (named). Two `###` added, statements where they were: "What add writes" and "Keys of a block".
The 196-word paragraph on `add` became two (and a third for the `graph json --write` line and the block's notes); the
`test` table's keys became a list. "drafts until the owner signs them (4.1)" became "drafts until they are signed there
(the parts library, 4.1)". The blocks table is unchanged.

**14.6 Where the ideas came from.** Unchanged but for "(drawn without EasyEDA, 6.5)". It is history by nature but owns
a `##` address; chapter 13 may take it over later, the address staying.

## History file

`/tmp/claude-0/-home-user-edakit/82157d39-3f55-5034-b81b-e1cbfc4ad998/scratchpad/history/14.md`: the pcb-pruefer
example from 14.1, the paragraph on the reference project's buzzer stage and USB-C input from 14.4, and (for reference,
not history) the two cut lesson examples of 14.4.

## Findings

- **"the maker's numbers"** (14.1, the requirements engineer; the same words in chapter 3 line 415 and table 11.1):
  the glossary defines Maker as the manufacturer (JLCPCB, PCBWay, …), but here it means the person who builds the
  board ("until vague words are the maker's numbers"). The skill `requirements` says "until vague words are numbers",
  chapter 17 "your numbers". Left as it is, because the phrase is used elsewhere; one word for both would need the
  glossary and three chapters.
- **The engines table of 14.2** repeats `decides` of `[engines.*]` in `edakit/catalog/codes.toml` word for word but is
  hand-written; it could be a generated kind of `edakit/catalog/handbook.py`, so that a new engine cannot be missed.
  Note also that the catalog's engine keys are `LIMITS`, `LEVELS`, `REQUIRES`, `PATHS` while the table uses the
  prefixes `LIM`, `LVL`, `REQ`, `PATH` – correct for the codes, but a reader who looks into `codes.toml` finds other
  names.
- **The `mutate` numbers** of 14.4 (led-bar: 24 of 45 without the simulation, 43 with `--sim`) are a measurement from
  rules-at-scale step 7 that no test holds; `tests/test_mutate.py` asserts only the R-EXT case. They may drift as
  codes are added.
- **The `mains` domain** switches nothing on (`[switch] on = []` in `edakit/domains/mains.toml`); LIM.hazardous belongs
  to `core`. 14.2 was always consistent with that, but only implicitly; the new table makes it explicit (Assumptions).

## Assumptions

1. The roles table of 14.1 became a list of entries, as the concept asks for tables whose cells are paragraphs. Its
   price is the "own words" measure going up; with tables counted, the length is unchanged.
2. The domain table in 14.2 (`mains`: "no check – spacing and isolation stay unchecked …") states that the domain
   switches on no code; the old text said only that LIM.hazardous recognises the net and spacing and isolation stay
   unchecked. True to `edakit/domains/mains.toml`, but a sharper wording than before.
3. "The user merges it" (14.4, item 6) became "the repository owner merges" – in the edakit repository the user of the
   skill add-rule is the owner, as CLAUDE.md says ("the owner merges").
4. "The owner" in the proposals subsection became "the repository owner" (and "they/their" after it), the term of the
   skill propose-rule; it names a condition of the pipeline (whose issues start it), so it could not become "you".
5. "Drafts until the owner signs them" (14.5) became "drafts until they are signed there (the parts library, 4.1)":
   who signs is in chapter 4.
6. The project reviewer's example (pcb-pruefer) and the buzzer/USB-C provenance paragraph left 14.1 and 14.4 as
   history, although those sections are named: neither carries a statement the automation relies on, and the
   CircuitSmith half is in 14.6.
7. Examples cut to one: three code examples to two, three lessons to one, three hint examples to one, two parts-note
   examples to one.
8. Five `###` added ("Engines and codes", "Accepting", "Domains and purpose", "What add writes", "Keys of a block");
   the bold lead-ins they replace were not linked from anywhere.
9. 14.6 kept as it is: history by nature, but its `##` address stays until chapter 13 is rewritten.
