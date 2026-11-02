# Review of step D.5: handbook/08-release-gate.md

**Status:** condensed in place on branch claude/amazing-newton-ygty8a, not committed; open for the owner's review.
Every statement kept, every `#`/`##` heading and section number unchanged. The chapter did not give a third fewer words
or 500 lines without losing statements – the statements won (reasons below).

## Measures

| | before | after |
| --- | --- | --- |
| lines | 1128 | 1253 |
| own words (prose, without tables and code) | 12226 | 11829 (−3 %) |
| mean sentence (words) | 30.8 | 26.6 |
| sections over 80 lines without a subheading | 5 | 0 |
| paragraphs over 120 words | 23 (up to 251) | 0 |
| "the user" / "the reference project" | 12 | 0 |
| dates outside a status line | 12 | 4 (kept, see Assumptions 1) |
| bare cross-references | 0 | 0 |

`tests/test_style.py -k 08-release-gate`: `sections`, `paragraphs` and `words` are now XPASS(strict) – the chapter can
leave those three sets of `RED` (not done here: `tests/test_style.py` is not this step's file). `dates` and `chapters`
stay expected failures.

**Why not a third fewer, and why more lines.**

- Every section but 8.5 is named by the automation (rule 4): 8.1 nine times, 8.2 six, 8.3 four, 8.4 twenty-three, 8.6
  thirty-nine, 8.7 six (places below). No statement could leave any of them, so the duplicates between 8.1 and 8.6
  (the interpreter of `cmd`, the 900 s / 15 minutes of a check) and between 8.2 and 8.6 (the project agents'
  sign-offs) stay in both.
- About 3,900 of the 12,200 own words sit in sentences that share ten or more words verbatim with code, skills, tests
  or other chapters (rule 5): `edakit/scripts.py` (most of 8.6), `edakit/release/publish.py` (the publish steps of
  8.3), `edakit/release/pictures.py`, `edakit/release/gate.py`, `edakit/cart.py` (the cart steps of 8.4),
  `edakit/cost.py`, `edakit/release/order_sheet.py`, `tests/test_agents.py`, `tests/test_script_runs.py`,
  `tests/test_fab_run.py`, `skills/release/SKILL.md`, `skills/pcb-round/SKILL.md`, `skills/requirements/SKILL.md`,
  handbook 3, 10 and 14. Those sentences were split from their paragraphs or turned into list items with their words,
  not reworded. The rest is dense specification text: few asides, repetitions or announcements to cut.
- Lines grew by 125: 28 new `###` subheadings with their blank lines, the long paragraphs split, four run-on
  sentences turned into lists (the four hashes' fab item, the pictures of section 12, the notes of `release publish`,
  the order form's fields and `order.md`). Reaching 500 lines would mean removing about 60 % of the chapter.

## Per section

### Introduction (before 8.1)

- **New first paragraph:** for you when a board goes to the manufacturer; what you know afterwards.
- "(8.3)" → "(one current release, 8.3)", "(11.3)" → "(the progress line, 11.3)". Otherwise unchanged.

### 8.1 Stages

Named by `edakit/catalog/codes.toml:741, 827, 962, 986`, `edakit/scripts.py:20, 883`, `skills/requirements/SKILL.md:128`,
`skills/release/SKILL.md:15, 45`.

- Subheadings added: "Stages S, L and F", "Seen red without EasyEDA", "Project checks" (the bold titles "Seen red."
  and "Project checks." became them).
- The stage table, the generated code table and the TOML example unchanged. The sentence introducing the generated
  table reworded: the three engines as one sentence with a verb each, then where each code runs, then "Their codes,
  generated from the catalog:".
- The looks row: three sentences instead of one with two asides; "In the reference project the layout review measured
  the LED side by hand …" to the history file.
- Polarity sheet: "Plus FILES.sheet: …" → "FILES.sheet draws a polarity sheet …"; "It is what the second check compares
  … and what you compare …" → "The second check compares it …, and you compare it …".
- Seen red: one paragraph split in three, words kept.
- Project checks: "the reference project's stand" → "a real project's stand"; "the reference project's camera test of
  every delivered tree" → "a real project's camera test of every delivered board"; the `order` check's double
  "after uploading, before paying" said once; "(8.5)" → "(acceptance, 8.5)".

### 8.2 Hashes and sign-offs

Named by `edakit/catalog/codes.toml:876, 958`, `skills/requirements/SKILL.md:125, 181`, `skills/release/SKILL.md:21`,
`skills/new-project/SKILL.md:122`.

- Subheadings added: "The four hashes", "What the circuit hash leaves out" (was a bold title), "The sign-off file",
  "Three required manual checks".
- The fab bullet (about 200 words) became a bullet with four sub-items, words kept; its tail (the manifest's
  `fab_layers`, what stays out of the fab hash) a paragraph after the list. "The circuit hash covers the data without
  more …" moved out of the layout bullet into its own paragraph right after the list, "the data" → "the footprint
  data" (Assumption 4).
- "(the owner's decision of 2026-10-31)", "(October 2026)" and "until October 2026" to the history file; the footprint
  geometry's old place now reads "older projects have it among the artifacts (…)".
- "The raw files differ …" got the lead "Why a fab hash:". "(10.1)" → "(the files of a project, 10.1)", "a corrected
  number (6.6)" → "a corrected quoted number (6.6)".
- The paragraphs on `hash_ignore`, a TOML graph and accepting a warning split at sentence ends, words kept; "A JSON
  graph keeps its hash as before" → "A JSON graph keeps its hash".
- New bold title "Accepting a warning." on the `match` paragraph. "until the owner judges it again and updates `parts`"
  → "until you judge it again and update `parts`"; "Only the owner accepts a warning" → "Only you accept a warning"
  (Assumption 2); "(chapter 11)" → "(working with Claude, chapter 11)".
- The M-6 exception of older sign-off files and the project agents' paragraph each split into shorter sentences.
- "The lesson behind M-5" → "Why M-5 is required.": the story of the first released run (switching regulator loop,
  45 % of one side bare) to the history file; kept: a run can pass every automatic check while nobody has looked at the
  layout as a whole, so M-5 is a condition of the release in the gate's own list; it ends every layout round; both
  reviewers give probability and cost (Assumption 3).

### 8.3 The decision

Named by `edakit/catalog/codes.toml:1073`, `edakit/release/pictures.py:1`, `edakit/release/publish.py:2`,
`skills/release/SKILL.md:73`.

- The release condition, one sentence of 80 words, became "A run is RELEASED only if" with three items; "every
  requirement `must` the user has accepted" → "… you have accepted".
- "Since 2026-10-31 … before, every comparison … (walkthrough-gaps.md)" to the history file; kept: "So a comparison of
  stage E whose finding is a warning does not fail the gate."
- Subheadings added: "The protocol and the run folder", "One current release", "Publishing what is ordered" (the last
  two were bold titles).
- Section 12's sentence of about 190 words became a list of four items, words kept. "(8.3)" (the chapter naming
  itself) → "(below)"; "(chapter 14.2)" → "(14.2)".
- "Gate runs are build output" split in two; "the reference project" → "a real project", the numbers (160 files, about
  5 MB) kept.
- The withdrawal paragraph: the parenthesis on older manifests became a sentence of its own.
- The notes of `release publish` (item 4, about 140 words) became sub-items, words kept. "The reference project built
  this as a script of its own first …" to the history file.

### 8.4 Ordering at the manufacturer (up to the cart; the owner orders and pays)

Named by `edakit/catalog/codes.toml:756, 1103, 1243, 1256, 1267, 1290`, `edakit/cart.py:1, 979`,
`edakit/fees/jlcpcb.json:5`, `edakit/makers.py:1`, `edakit/makers/aisler.toml:1`, `edakit/makers/jlcpcb.toml:1`,
`edakit/makers/eurocircuits.toml:1`, `edakit/cost.py:29, 212`, `edakit/easyeda/bridge-extension-patch.sh:46`,
`edakit/easyeda/odb-tool-patch.mjs:4`, `edakit/easyeda/mcp-server.sh:34`, `skills/pcb-round/SKILL.md:144`,
`skills/release/SKILL.md:89, 109`, `skills/new-project/SKILL.md:65, 67`. The heading keeps "the owner" (rule 1; the
glossary links its anchor six times).

- **State:** the paragraph "State 2026-11-01: …" became a `> **State:**` line at the top of the section, without its
  date (the dated fixture path stays); "the owner's accounts" → "real accounts at the makers". Its last clause, the
  ODB++ of `kicad-cli pcb export odb`, moved into the AISLER sentence of "Makers", which named kicad-cli already.
- Subheadings added: "The cost before the quote", "Carts and hand assembly", "The order form as data", "Up to the
  cart", "Makers", "Lessons from a real order", "Future work: wishes to makers" (all but "Lessons" were bold titles;
  "Everything else in the same go" became "Carts and hand assembly").
- Merged inside 8.4: the order form's "Every colour other than green takes two more days at JLCPCB (its quote form,
  read 2026-10-28); `edakit cost` prices the fee table's board …" with the same statement in the cost list – the
  source "(its quote form, read 2026-10-28)" moved into the cost item, the order form keeps a one-line pointer.
  `edakit/cost.py` quotes the cost item's wording, which is kept.
- Merged inside 8.4: the makers' paragraph's order-number sentences (JLCPCB's "Mark on PCB", `JLCJLCJLCJLC`,
  `WayWayWay`) with the lessons' "Order number" item – now two items, "Order number" (JLCPCB) and "Order number at
  PCBWay, and with `[looks]`"; and AISLER's "no cart … stops before Continue to Checkout" (said in step 4) → "AISLER
  has no cart (step 4)".
- The order form paragraph (about 420 words) split into five paragraphs and two lists (the board-dependent keys, the
  fields of `order.md`), words kept; "the board of the reference orders" → "the board of a real project's orders".
- The cart steps: steps 1, 4 and 5 split into a first sentence and indented continuation paragraphs, words kept. "the
  owner" → "you" in the up-to-the-cart paragraph, steps 3 and 5, the checklist fallback, PCBWay's submission, the three
  consents, `sale` in the EU, the M-2 tick and PCBWay's partner API (Assumption 2); "values from the owner's orders
  reach the shipped table" → "values from your orders …" (Assumption 5).
- Dates to the history file: "(the user's decision of 2026-10-30)", "(the owner's decision of 2026-10-30)", "(the
  owner's decision of 2026-10-31)", "(the owner's decision of 2026-11-01)"; also "– in the reference project they were
  found only in the quote".
- Kept with "a real project": the estimate within about 1 $ of the cart with its date and numbers ("USB tree" → "one
  board"), and the remark that was wrong three times – the catalog's sources cite both from 8.4
  (`edakit/catalog/codes.toml:1243, 1267`).
- "(5.8)" after the SOT-23 → "(live run 5.8)": it named the live run, not section 5.8.
- "Lessons from the reference order:" → the subheading "Lessons from a real order"; "The MCP server cannot order." kept.

### 8.5 Acceptance (M-4)

Not named by the automation. The list of section 6 became five items; "(8.2)" → "(open from the datasheets, 8.2)",
"(8.3)" → "(publishing, 8.3)". Nothing cut – each item is the place 8.1, 8.2, 8.6 and 8.7 point to.

### 8.6 Project scripts and agents

Named by `edakit/catalog/codes.toml:796, 801, 808, 812`, `edakit/cli.py:79`, `edakit/agreements.py:13, 49, 53`,
`edakit/config.py:131, 135`, `edakit/scripts.py:10, 613, 994, 1010, 1025, 1058, 1067, 1296, 1422, 1660, 1668`,
`edakit/requirements.py:581`, `edakit/release/gate.py:29, 729`, `skills/pcb-round/SKILL.md:44, 117, 125`,
`skills/hardware-change/SKILL.md:49, 83`, `skills/circuit-design/SKILL.md:170`, `skills/start/SKILL.md:47`,
`skills/release/SKILL.md:15, 38, 53`, `skills/new-project/SKILL.md:73, 111, 152`, `agents/project-surveyor.md:76, 132`.
The printed line "project scripts before edakit gate (handbook 8.6):" in a code block is the code's output and stays.

- Almost every sentence is shared with `edakit/scripts.py` or the tests (rule 5): structure only. Subheadings added:
  "Data names", "Resolving the entries", "Stamps", "Running the scripts", "Scripts of kind easyeda", "Project agents",
  "Checking the agents' entries", "The agents' sign-offs in the gate", "Who starts what" (four were bold titles).
- "**`[[release.stages]]` stay exactly as they are:**" now opens its own paragraph with the sentence that followed it.
- "An `easyeda` script under the EasyEDA claim." → "Under the EasyEDA claim." (under the new subheading), "claims
  EasyEDA for it" → "for an `easyeda` script"; "(11.2)" → "(the claim, 11.2)", "(9)" → "(chapter 9)", "(11.4)" →
  "(the working agreements, 11.4)".
- "the reference project's two reviewers", "… tree artwork" → "a real project's …" (Assumption 6).
- "the owner" → "you" in the outdated table (twice), the agents' checks (phase `order`; "never the owner's (M-2, M-4)"
  → "never yours") and the last row of "Who starts what".
- The exit paragraph split; "– the system font the bell's `make_art.py` draws with –, and the entry's `check` … does
  not run yet" → two sentences.

### 8.7 Requirements

Named by `edakit/requirements.py:513`, `skills/requirements/SKILL.md:182`, `skills/release/SKILL.md:60`,
`agents/pcb-reviewer.md:71`, `agents/electrical-reviewer.md:67`, `agents/regulatory-reviewer.md:59`.

- Subheadings added: "Evidence and binding", "Section 11 of the protocol". The `verify` table kept as it is (its cells
  are shared with `skills/requirements/SKILL.md` and `edakit/requirements.py`; Assumption 7).
- "until the owner accepts it" → "until you accept it"; "once the user has set" → "once you have set" (the sentence is
  shared with handbook 3; Assumption 6). The passage on passing evidence in a reviewer's note, which three agents
  name, is unchanged.

## What went to the history file

`/tmp/claude-0/-home-user-edakit/82157d39-3f55-5034-b81b-e1cbfc4ad998/scratchpad/history/08.md`, verbatim with its
section: the looks row's hand measurement (8.1); the electrical hash's decision date, the one-file edakit.toml's date,
the footprint geometry's "until October 2026", the lesson behind M-5 (8.2); the stage E comparisons before 2026-10-31,
the first publish as a script with four boards (8.3); the decision dates of the cart, the fee table, the mark and the
wishes, the state line as it stood, the tooling holes found only in the quote (8.4).

## Findings

Not changed – for the owner.

1. `edakit/catalog/codes.toml:958` (a source of GEO.spacing) reads "0.4 mm: the reference project's decision after its
   layout review (M-5, edakit handbook 8.2), 2026-10-25". Section 8.2 has never held a 0.4 mm decision; it defines M-5.
   The source would be clearer naming the project's decision log, with 8.2 only for M-5.
2. Several catalog sources still say "the reference project" / "the reference order" and cite chapter 8 for it
   (`edakit/catalog/codes.toml:1243`, `:1267`, ORDER.form's why). They are data and keep their words; the chapter now
   says "a real project", which the reader can match, but the wording differs.
3. `skills/release/SKILL.md:33` says "**Only the user accepts a warning**"; the chapter now says "Only you accept a
   warning". The skill's word is its own (a prompt); listed in case the owner wants one word across both.
4. The heading of 8.4 keeps "the owner orders and pays" (rule 1) while the section's sentences now say "you". Renaming
   it would move an anchor the glossary links six times – a decision for the owner, with a redirect or the glossary
   changed in the same commit.

## Assumptions

1. **Four dates stay.** "read 2026-10-28" (JLCPCB's quote form: two more days for a colour), "2026-10-25" (the estimate
   within about 1 $ – a dated measurement with "the fees of that day", cited by `edakit/catalog/codes.toml:1267`), "read
   2026-11-01" (the makers' RoHS and REACH statements) and "since May 2026" (JLCPCB prints no order number; also in
   handbook 10 and `skills/release/SKILL.md:106`). They date the external facts the statements rest on, as the law's
   state in chapter 15 – so `dates` stays red for the chapter.
2. **"The owner" → "you"** in the chapter's own sentences, also in sentences shared verbatim elsewhere (rule 5), as the
   one exception to "leave it as it is": a word swap the style guide asks for, no change of meaning. In "Only you accept
   a warning", "the tick is yours" and "never yours (M-2, M-4)" the reader is the person, not Claude – as chapters 10
   and 17 already write "only you accept".
3. **"Why M-5 is required"** generalises the M-5 story into one sentence ("A run can pass every automatic check while
   nobody has looked at the layout as a whole"); the story itself is in the history file. Check that this keeps the
   reason a reader needs.
4. **"The circuit hash covers the footprint data without more"** – moved out of the layout bullet to the paragraph after
   the list, and "the data" made explicit as "the footprint data", which the bullet's context meant.
5. **"values from your orders reach the shipped table through `edakit proposal`"** – the original said "the owner's
   orders"; read as the project's orders, since proposals come from projects (on the owner's word, CLAUDE.md). If
   edakit's own owner's orders were meant, the sentence should say so.
6. **"The reference project" → "a real project"** inside shared sentences too (8.1, 8.6 "tree artwork", 8.7 "the user"
   in a sentence shared with handbook 3): a word swap, as in Assumption 2.
7. **Tables kept as tables**: the stage table of 8.1 and the `verify` table of 8.7 have paragraph-long cells. Turning
   them into entries would add counted prose and touch text shared with `skills/requirements/SKILL.md` and
   `edakit/requirements.py`; left for a later step if wanted.
8. **The State line** at the top of 8.4 drops "2026-11-01" and keeps the dated fixture path
   (`tests/fixtures/makers/aisler/step0b_2026-11-01.md`), which is a file name.
9. **Merges inside 8.4** (the colour delay into the cost list, the order-number sentences into the lessons, AISLER's
   checkout into step 4) dropped the second wording of each statement, also where that wording was shared with
   `edakit/catalog/codes.toml` – the shared phrase survives in the kept wording ("is printed as text at every maker:
   FILES.order warns about it").
10. **New subheadings**: 28 `###` headings, none renamed, none linked yet; "Up to the cart" and "Future work: wishes to
    makers" were shortened from the bold titles to stay near five words.
