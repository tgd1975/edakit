# The documentation: who reads it, how it is organised, how it is written

Status 2026-10-31: decided – the eight decisions and what Claude decided itself accepted by the owner the same day, in a
decision round in Claude Code's form (the table at the end); nothing built; each step D.1 to D.7 starts on the owner's
word, one per branch, listed in `TODO.md`. Written against main at `8fba5f2`. Asked for by the owner: the pages are
comprehensive but confusing, so unreadable – a concept for how the documentation should look, be organised and be
written, who its readers are, the language and its style, what is missing for it to be understood, everything needed so
that others use edakit. With one condition the owner set while it was written: everything `docs/organisation.md` does
not list as documentation – skills, agents, CLAUDE.md, the catalog's and the domains' texts, the manifests, the concepts
– is data the automation reads; a change there may break something elsewhere or shift a meaning, so this concept leaves
it alone and says where documentation itself is read by the automation; and a rule for every change: when unsure, ask –
or check whether the text is generated or used elsewhere, which says to leave it as it is. The findings come from the
site built from main (`docs/pages.py`, MkDocs), the Markdown measured – words, sentence lengths, headings,
cross-references, the words that go unexplained – and the code and tests that read the documentation.

## The short answer

The documentation is complete and checked against the code, and it is written for one reader: the owner, who knows every
term, every project and every chapter number. 220,000 words on 63 pages – the handbook 107,000, the concepts 111,000 –
with no page of one screen that says what edakit is and for whom, no path to a first result under 50,000 words of
reading, no glossary, a navigation that lists sources (concepts, prompts) beside documentation and leaves two
documentation pages off the site, and chapters of up to 1,121 lines whose sections run 300 lines without a subheading
and whose sentences average 40 to 56 words. Four readers come to it and none is served: the newcomer who wants to know
whether it is for them, the maker who wants to build a board, the engineer who wants to add a rule, the developer who
wants to work on edakit. A fifth reader is served and must stay so: Claude in a session, for whom the handbook is
reference material named from 415 places in the code, the skills and the agents.

Proposed: three layers over the one source that exists. An **entry layer** written anew and short – a start page of one
screen, a quickstart to the first finding in fifteen minutes without EasyEDA, one page on how it works, a glossary –;
the **guides**, which are the handbook's chapters, kept under their numbers and file names but grouped by reader in the
navigation and trimmed in place – subheadings, shorter sentences, the generated code lists replaced by a table and a
link, the history and the private projects moved out, a status line where something is offline only – with the rule that
a statement the automation points at is shortened at most, never moved or changed; and the **reference**, generated
where the code knows it: the commands from the command line's own help, the catalog as one page per engine instead of
1.6 MB in one file. The sources – concepts, skills, agents, evals – stay readable on the site, but at its end under
"Inside edakit", with an index that says what a concept is and in which state each one is, and their texts untouched.
One style guide, `docs/style.md`, says how every layer is written and what it does not apply to, and a test holds what
can be counted. The files, chapter numbers and section numbers stay: 415 places name them, the SessionStart hook reads
section 11.4, and six tests hold the pages to the code.

Everything this concept adds is text in the repository; what it moves into text is what exists today only in the owner's
head: who the readers are and how the documentation is written.

## Who reads it

| Reader | Comes with | Wants to know | Finds today |
| --- | --- | --- | --- |
| The newcomer – has seen the name, has five minutes | a browser | what it is, whether it is for them, what it needs, what it costs, how to try it | a README of 2,300 words whose second sentence uses "sign-off" and whose third paragraph "hardware graph"; the requirements spread over the README, 2.2 and 16.2; the cost nowhere; the first run in chapter 17, 713 lines |
| The maker – wants a board | Claude Code, EasyEDA Pro or KiCad, an idea, little EDA routine | set up, describe a circuit, run the checks, read a finding, reach a board and an order; what Claude does, what they decide | chapters 2 to 8, 11, 12 and 16 – 5,000 lines; the handbook's reading path "first time" is 1 → 2 → 17 → the bell → 3 → 6 → 7 → 8, about 50,000 words before the first graph of their own |
| The engineer – wants to add a rule | electronics, maybe no Claude Code | what a rule is made of, how a check, hint, block or part fact is added and tested, how it is proposed | 14.2 to 14.4 inside the maker's chapter, the skill add-rule in `.claude/skills/` (not on the site), the skill propose-rule, `docs/organisation.md` (not on the site) |
| The developer – works on edakit | Python, git | how the repository is organised, the rules of a session, the concepts and their state, the tests, the site | `docs/organisation.md`, CLAUDE.md (neither on the site), 22 concept pages in path order, the READMEs under `tests/` |
| Claude in a session | the plugin | the chapter a skill names, section 11.4, the catalog | served: 415 references "handbook N.N" and chapter paths, `edakit explain` – the constraint on every change below |

## What the site is today

Measured on main at `8fba5f2`, the site built locally (`python3 docs/pages.py`, `mkdocs build --strict`):

- **Volume.** 63 pages, 13 MB. The Markdown behind them: 220,000 words – the handbook 107,000 in 7,560 lines, the
  concepts 111,000, the README 2,300. The catalog page is one HTML file of 1.6 MB.
- **Chapters.** Eight of the seventeen are longer than 400 lines; chapter 8 has 1,121 lines in seven sections, the
  longest 326 lines; chapters 3, 4, 5 and 7 have sections of 231 to 289 lines. Subheadings (`###`) exist in chapter 10
  only. On the site a chapter's table of contents is its seven section titles for 118 KB of text.
- **Sentences.** Prose outside tables and code: chapter 3 averages 56 words per sentence, 5 and 8 42, 4 36, 7 31, the
  README 31; chapters 1, 2, 6, 9 and 13 are between 16 and 26. The long ones are nested: an aside in an aside, three
  cross-references in one sentence, a list of five in the middle.
- **Cross-references.** By number alone – "(8.2)", "(10.4)", "see 7.4" –: 116 in chapter 3, 118 in 4, 150 in 5, 137 in
  7, 227 in 8, 188 in 10. A reader who does not know the numbering reads "(8.2)" as noise.
- **Generated lists.** The catalog's code texts are rendered into the chapters – 175 lines in chapter 3, 108 and 21 in
  8, 96 in 14, 37 in 4, 21 in 5 – and again on the catalog page: 458 lines of the same text in the chapter's flow, where
  a reader of the chapter wanted the next paragraph.
- **The navigation.** Six entries by source folder: Handbook, Rule catalog, Concepts, Skills, Agents, Evals. Concepts
  lists 22 pages in the order of their paths – `discarded/` first, `done/` and `new/` mixed, two prototype READMEs among
  them – with titles of up to seventeen words ("To be checked, clarified, fixed – what the walkthrough left open"). A
  reader cannot tell a plan from a decided concept from a discarded one without opening it.
- **Documentation and sources side by side.** `docs/organisation.md` says what is documentation and what a source; the
  site shows the sources and leaves two documentation pages off – `docs/organisation.md` itself and the brand page are
  not in `docs/pages.py`. An implementation plan's status paragraph ("phase 1 (1.1 to 1.8), 3.1 to 3.5, 3.7 and the
  follow-ups below are done; 2.1 to 2.4 …") is the second page of the Concepts group.
- **Written from inside.** "The reference project" – a private project – is named 30 times in the README and the
  handbook and described nowhere; "the bell" 21 times; "the owner" 32 times, "the user" 62 times – the skills' word for
  the person the reader is. Dates of October 2026 appear 47 times in the handbook, 17 in chapter 8 alone; chapter 9
  opens with "Everything here was found the hard way … between 19 and 26 October 2026". The history and the reference
  are one text.
- **No glossary.** Sign-off (143 mentions), M-1 to M-6 (201), stage, hand-over, claim, domain, engine, code, hint,
  block, gate run, release: each is explained where it is introduced, and a reader who arrives at chapter 8 by search
  has not been there.
- **The README.** 239 lines: a 50-line block of commands (the same as 10.5 and `edakit --help`), one paragraph of 17
  lines on skills and agents, a repository map of 15 rows for the developer, and "Status and limits" – the one section a
  newcomer needs – at the end.
- **Spelling.** British as the rule – colour 45, behaviour 28, centre 16, licence 8 – with exceptions (color 6, behavior
  14, license 5). "Catalogue" is JLCPCB's, "catalog" edakit's own: a distinction, not an inconsistency.
- **What works.** The sentences are true to the code: the review of 2026-10-31 checked them (1cf3237). The tone is even
  – no superlatives, no marketing. Chapter 17 is the one chapter written for a reader who starts at zero, and it is the
  best page of the site; chapter 12 is a table a reader in trouble can use; `handbook/README.md` says for each chapter
  when to read it. The site has search, dark mode, a mobile layout and the brand. The problem is the text and its order,
  not the generator.

## What the automation reads – and the rule for it

Claude reads the handbook. 274 places in `edakit/` – finding and fix texts, docstrings, the help of the command line –,
120 in `skills/`, 12 in `agents/` and 9 in `.claude/` say "handbook 8.6" or name a chapter file; 51 distinct sections
are named, every one exists today; a skill opens a chapter by path
(`${CLAUDE_PLUGIN_ROOT}/handbook/11-working-with-claude.md`, 31 such paths, `10-reference.md` and `02-setup.md` most);
`edakit/agreements.py` parses the numbered items of section 11.4 with their bold titles at every session start, so that
the digest cannot drift from the chapter. The tests read it too: `test_plugin.py` wants every skill and agent named in
the README and in table 11.1, `test_catalog.py` holds the generated sections to the catalog, `test_walkthrough.py` holds
chapter 17 to the example, `test_agreements.py` holds 11.4, `test_pages.py` the site, `test_catalog_page.py` the catalog
page. No test holds the 415 references themselves.

The other way round, the documentation quotes data: the catalog's rule, why and fix texts in the generated sections, the
domains' texts, the help lines of the command line, the skills' descriptions on their pages. They read like
documentation and are not – `docs/organisation.md` says so for the catalog, and the owner's condition extends it to
every source: a change there is a change of what the automation does.

The rules this concept holds to, for every step below:

- **Sources, data and code are not touched.** Skills, agents, CLAUDE.md, the catalog and the domains, the help texts in
  `edakit/cli.py`, the docstrings, the manifests, the concepts: not a word, not for style. Where the documentation needs
  a different word than a source uses, the documentation takes the source's word; where a source's text should change,
  that is a finding for the owner, as `docs/organisation.md` has it for the review – the stale "From a JSON hardware
  graph" in `.claude-plugin/plugin.json` is the first.
- **Unsure – ask, or check.** Before a sentence of the documentation changes: is it generated – between `<!--
  edakit:generated -->` markers, in a quote block of `edakit docs`, a skill's description rendered on its page –, then
  it changes in its source or not at all; is it used elsewhere – the phrase searched over `edakit/`, `skills/`,
  `agents/`, `tests/` and the other chapters –, then it stays as it is: a text found elsewhere is a hint that it is
  better left unchanged; still unsure, the owner is asked, in the decision round of the branch. Nothing is changed on a
  guess.
- **Where the automation reads documentation, the statements stay.** The chapter files the skills open, the sections the
  findings and the skills name (8.6, 4.1, 8.4, 3.1, 4.5, 5.1, 5.3 first), section 11.4 as the hook reads it, the README
  and table 11.1 as `test_plugin.py` reads them: a sentence there may be shortened, a long section may get subheadings,
  but no statement leaves the section that names it, none changes its meaning, and the numbered items of 11.4 with their
  bold titles stay as they are – they are the agreements, and a change of an agreement is the owner's.
- **Addresses stay.** Chapter files, chapter numbers and section numbers do not change. A new `###` adds an anchor and
  removes none. The navigation may call chapter 3 "Hardware graph"; the file keeps "3 The hardware graph".
- **The generated sections change only through their generator.** The short kind (a table of code, title, severity with
  the link to the catalog page) is one more kind of `edakit/catalog/handbook.py`, test first; the texts it leaves out
  are still what `edakit explain` and the catalog page give, from the same data.
- **A test holds the addresses**, new: `tests/test_references.py` – every "handbook N.N" and every chapter path named in
  `edakit/`, `skills/`, `agents/` and `.claude/` exists, and every path a skill opens exists. Red before a section
  disappears, not after a session finds the gap.
- **The review after each chapter reads for meaning.** Old and new text side by side; every statement that is gone,
  moved or reworded is listed with the places in code, skills and agents that name its section, and the skills that open
  the file are read once against the new text. The list goes to the owner with the branch.

## The proposal

### Three layers, one source

| Layer | For | Pages | Written |
| --- | --- | --- | --- |
| Entry | the newcomer, then everyone once | the start page, the quickstart, how it works, the glossary | anew, short, in the entry register of the style guide |
| Guides | the maker, the engineer, the developer | the handbook's chapters, grouped by reader; two reader pages added | in place: trimmed, not rewritten |
| Reference | everyone who looks something up | the project files and keys, the commands, the EasyEDA API, the catalog, the check IDs of before | generated where the code knows it, in entries, not tables of paragraphs |

The sources stay on the site, at its end, as "Inside edakit", untouched.

### The entry layer

- **Start** (`README.md`, the site's index): one screen. One sentence what edakit is; three lines for whom – the maker,
  the engineer, the developer – each with its link; what it needs (Claude Code; EasyEDA Pro desktop or KiCad 10; uv,
  ngspice; tested on Linux, Windows and macOS untested; a JLCPCB account for stock and ordering); what it is not (no
  editor of its own, two copper layers, DC operating points and a few transient runs); install in three lines; "try it
  in two minutes" – `uvx --from git+https://github.com/tgd1975/edakit edakit check` in `examples/coin-cell-led`, which
  takes 0.2 s and shows an accepted finding with its reason –; then the quickstart, the guides, the reference. The
  command block moves to the reference, the repository map to `docs/organisation.md`, "Status and limits" to "How it
  works". The test that wants every skill and agent in the README (`test_plugin.py`) is pointed at the page that lists
  them – the test changes with the page, on the same branch.
- **Quickstart** (`docs/quickstart.md`): the first project to the first finding and the first drawn schematic, in about
  fifteen minutes, without EasyEDA – install the plugin, a project from the example or from `/edakit:new-project`, a
  graph of four parts, `edakit check`, one finding read with `edakit explain`, `edakit sim`, `edakit schematic draw`,
  and where the EasyEDA or KiCad part begins (chapter 17 takes it from there). Every output from a real run, held by a
  test like chapter 17's (`tests/test_walkthrough.py`).
- **How it works** (`docs/how-it-works.md`, two screens): the pipeline as a drawing in the brand's colours instead of
  the ASCII line; the ten words – graph, parts entry, stage, code, finding, sign-off, gate run, release, domain, block,
  hand-over –, one paragraph each; what Claude does and what the person decides, the decision round shown once as a
  shortened transcript; what is text and what still exists only in EasyEDA – the README's "Status and limits", kept
  current as it is today.
- **Glossary** (`docs/glossary.md`): every term in one or two sentences, with the chapter that treats it, in the words
  the skills and the catalog use. The first use on an entry page links to it.

### The guides, by reader

The navigation, two levels, groups named after what the reader does:

| Group | Pages (the files as they are) |
| --- | --- |
| Use it | The approach (1), Setup (2), Working with Claude (11), Hardware graph (3), Parts (4), Simulation (5), Schematic (6), PCB (7), Release gate (8), KiCad (16), Regulatory review (15), Troubleshooting (12), Walkthrough (17), Lessons learned (13) |
| Extend the rules | Designing a circuit (14), *Adding a rule* (new: from 14.4, the skill add-rule and `docs/organisation.md` – the catalog's files, a code's fields, the negative test, the generated sections, the run against the reference circuits, the proposal from a project), Propose a rule, Propose a feature (the skills' pages) |
| Develop edakit | *Working on edakit* (new: `docs/organisation.md` on the site, extended by the concepts' lifecycle, the tests, the evals, how the site is built; CLAUDE.md beside it as a source page), Brand |
| Reference | Project files and keys (10.1–10.4, 10.6), Commands (10.5), EasyEDA API (9), Rule catalog (one page per engine, the domains, the tables, the reference circuits, the open designs), Check IDs of before (10.7) |
| Inside edakit | Concepts – an index, then new, done, discarded, each with one line of state –, Skills, Agents, Evals |

Chapters 9 and 10 move to the reference without changing their files: the navigation lists a file where the reader
looks, the file stays where the code looks.

What changes inside a chapter (step D.5), one chapter per branch, the documentation review after each, under the rules
above – every sentence checked first for being generated or used elsewhere, and the owner asked where that leaves a
doubt:

- The first paragraph says who the page is for and what they can do after it.
- A subheading at least every 80 lines; the long sections of 3, 4, 5, 7 and 8 get `###` by topic, their statements where
  they were.
- Sentences: one aside, one cross-reference, one list per sentence; a cross-reference names its subject – "the sign-off
  file (8.2)", not "(8.2)".
- The generated code lists become the short kind – code, title, severity, the link to the catalog page, which holds the
  full texts.
- The history leaves: dates, "found the hard way", what went wrong in which week go to chapter 13, which becomes the
  history of edakit – the reference project described there once, as a project of about 120 parts built in October 2026,
  and named nowhere else; the example and the open designs are the examples the guides use. The bell stays where it is
  cited, as the public example it is. A date a finding or a skill relies on (the law's state in chapter 15, the versions
  in chapter 2) is no history and stays.
- A status admonition at the top where something is built offline only or planned, one line, instead of the state woven
  into the prose.
- Tables whose cells are paragraphs become prose with a short table, or entries (definition lists).
- "The user" becomes "you", "the owner" leaves the reader pages – in the documentation's own sentences; a quoted skill,
  agreement or catalog text keeps its words.

### The reference, generated

- **Commands.** 10.5 is a table of 60 rows and four columns whose cells are paragraphs; on a phone it does not fit. It
  becomes one entry per command: the synopsis and the help line generated from the command line's own parser
  (`edakit/cli.py`, 31 subcommands with help texts) between generated markers and held by a test as the catalog's lists
  are, and under each the hand-written lines reads, writes, exit codes, EasyEDA – what the table holds today, as lines.
  The help texts are code: a help line that reads badly in the reference is changed in `cli.py` through a branch of its
  own, not by the documentation.
- **The catalog page.** `docs/catalog/build.py` writes one page per engine, one for the domains, the tables, the parts
  schema, the reference circuits and the open designs, and an index with the counters; the navigation lists them.
  `test_catalog_page.py` follows. The texts are the catalog's, as today.
- **The project files.** 10.1 to 10.4 stay hand-written – they are the reference that explains –, their tables kept to
  short cells, the explanation below the table.

### Sources on the site

Concepts, skills, agents and evals stay on the site – a reader of the developer page needs them, and a link into a
concept must land somewhere readable – but as the last group, "Inside edakit", with an index page that says what a
concept is, how it moves from `new/` to `done/` or `discarded/`, and lists each with the first sentence of its status
line. Prototype READMEs leave the navigation (their links still work). CLAUDE.md joins as a page rendered like a skill.
Every page of this group carries a one-line admonition at the top, added by `docs/pages.py` and not by an edit of the
source: this is a source – a concept, a prompt, the rules of a session –, read it as such. Nothing in the sources
changes for the site.

### The site itself

- The navigation as data in `docs/pages.py` – a table of file, group and short title – instead of the folder walk;
  `test_pages.py` holds it. Titles in the navigation have at most five words; the H1 of the file keeps its number.
- `docs/organisation.md` and `docs/brand/README.md` on the site – they are documentation.
- A line in the footer: built from main at `<commit>` on `<date>` – the site has no version, and a reader who reads
  "every commit on main is an update" should see which one they read.
- Material's features as they are: search, dark mode, the brand. Definition lists and admonitions are enabled and unused
  today; the reference, the status lines and the source line use them.
- A line at the foot of every page: something unclear or wrong – open an issue. An ordinary issue; the Action proposals
  reads the owner's sealed proposals only and stays as it is.

## How it is written: the style guide

`docs/style.md`, a documentation page, pointed at by `docs/organisation.md` where the review's style sits today. It
holds for the documentation – `README.md`, `handbook/`, `docs/` outside `concepts/`, the example's Markdown – and for
nothing else: the catalog's texts are data, the skills and agents are prompts, CLAUDE.md is the sessions' rules, the
help texts are code; each keeps its own words, and the documentation follows them.

**Registers.** Three, by layer:

| | Entry | Guides | Reference |
| --- | --- | --- | --- |
| sentence | at most 20 words on average, none over 35 | at most 25 on average | fragments allowed in entries and cells |
| paragraph | at most four sentences | one idea; a subheading every 80 lines at most | an entry per thing |
| asides | none – a second sentence instead | one per sentence, the en dash as written | – |
| cross-references | to the glossary and to one guide page, by name | the subject and the number: "the board file (10.2)" | by number and name |
| terms | introduced one per sentence, linked to the glossary at first use | used as the glossary has them | as the glossary has them |
| history | none | none – chapter 13 | none |
| state | a status admonition, one line | the same | the same |

**Words.** "You" for the reader, "Claude" for the session, "edakit" for the tool; "the plugin", "the command line", "the
handbook", "the catalog", "the site" for its parts. "The owner" on the developer page only – edakit's owner, who decides
–, "the user" nowhere in a reader page's own sentences. One word per thing, listed in the glossary and taken from the
skills and the catalog: hand-over, sign-off, tool chain, parts entry, board file, gate run, placement plan. British
spelling as written; "catalog" is edakit's own name, "catalogue" JLCPCB's. No superlatives, no "simply", no "just", no
"the hard way". Numbers with their unit and a space (0.2 mm, 5 V). Prose wrapped at 120 characters, as written.

**A page.** Its first paragraph says for whom and what they can do after it; the shortest path comes first, the details
after, the reasons at the end; a status admonition at the top where something is offline only or planned; headings of at
most five words in the navigation. Regulatory content says once that it is support, not legal advice (CLAUDE.md).

**Pictures.** One per guide page where a picture is faster than a paragraph – the pipeline, a drawn schematic, a
placement plan, a gate protocol –, SVG in the brand's colours; where edakit draws it (`schematic draw`, `pcb plan`)
generated and held by a test, as chapter 17's drawings are.

**Code and output.** A command and its output from a real run, shortened with `…`; held by a test where a test can
(`test_walkthrough.py` is the pattern).

**Held by a test.** What can be counted is counted, in edakit's own spirit: `tests/test_style.py` measures the entry
pages' sentence length, finds a section over 80 lines without a subheading, a bare "(N.N)", "the reference project" or
"the user" in a reader page's own sentences, a date outside chapter 13 and the status lines, a term in bold without a
glossary entry. It reads documentation only. The rest is the documentation review's (`docs/organisation.md`).

## What is missing, so that others use it

1. **The entry** – the start page, the quickstart, how it works, the glossary (above). Today the shortest way to a first
   result is chapter 17.
2. **"Is it for me"** – said once, plainly, on the start page: what it needs, what it costs (a gate run, a decision
   round, a circuit design in tokens – the evals' runs give numbers), what it is not, the licences of what it combines
   (the README has them, at the end).
3. **A session shown.** Nothing on the site shows what working with it looks like: what Claude asks in a decision round,
   what the person answers, what is written where. One shortened transcript on "How it works", from a real session, held
   by the review to the skill it shows.
4. **Try it without committing** – `uvx … edakit check` on the example: two minutes, no plugin, no EasyEDA. It works
   today and is one line in the README; it becomes the first thing the start page offers.
5. **Feedback** – the line at the foot of every page.
6. **What changed** – "every commit on main is an update" and no page says what. Optional: a page generated from the
   first lines of main's merge commits (`git log --first-parent`), newest first, by `docs/pages.py`. Decision 8.
7. **The marketplace text.** `.claude-plugin/plugin.json` says "From a JSON hardware graph" – the graph is TOML since
   L.8. The plugin's and the marketplace's descriptions are the first text a reader sees in `/plugin`. They are a
   source: the review reports them, the owner changes them.
8. **Contributing, said plainly** on the developer page: issues and pull requests are welcome and the owner merges; rule
   and feature proposals come from projects through the plugin, and only the owner's are triaged by the Action.

## Steps

| Step | What | Size | Waits for |
| --- | --- | --- | --- |
| D.1 | `docs/style.md` and `docs/glossary.md`; `docs/organisation.md` points at the style guide; `tests/test_style.py` for the countable rules, red on today's pages where it must be; `tests/test_references.py` for the addresses | M | the decisions |
| D.2 | The entry layer: the README as the start page, `docs/quickstart.md` with its test, `docs/how-it-works.md` with the pipeline drawing and the transcript; `test_plugin.py` pointed at the page that lists skills and agents | M | D.1 |
| D.3 | The site: the navigation as data, by reader, short titles; `organisation.md` and the brand page on it; "Inside edakit" with its index and the source line; the footer line; the feedback line; prototypes off the navigation; `test_pages.py` follows | S–M | D.2 |
| D.4 | The reference: 10.5 as entries with the generated synopsis; the catalog page split by `build.py`; the chapters' generated lists as the short kind of `catalog/handbook.py` | M | D.1 |
| D.5 | The chapters in place, worst first – 8, 3, 5, 7, 4, 10, then 2, 6, 11, 14, 15, 16, 17, 1 –, one per branch, the review for meaning after each; chapter 13 takes the history | L (M per large chapter) | D.1 |
| D.6 | The reader pages: "Adding a rule", "Working on edakit" with CLAUDE.md beside it | M | D.3 |
| D.7 | The "is it for me" numbers from the evals; the findings on sources (the plugin's descriptions) to the owner | S | – |
| D.8 | "What changed", if decided | S | D.3 |

D.1 to D.4 and D.6 to D.7 are about six sessions; D.5 is one session per large chapter and the review after it. The
first usable result is after D.3: a newcomer enters through the start page and the quickstart and reaches the guides
through a navigation that tells them where they are, with the chapters still as they are.

## Measures – done when

- A reader who has not seen edakit reaches the first finding on the example in under fifteen minutes with the quickstart
  alone, and without EasyEDA – tried by one person, and by Claude in a fresh session with the site as its only input, as
  an eval case (`evals/`).
- The entry pages: sentences at most 20 words on average; no page over two screens but the quickstart.
- The guides: no section over 80 lines without a subheading; sentences at most 25 words on average; no bare "(N.N)"; no
  "the reference project" and no "the user" in a reader page's own sentences; no date outside chapter 13, the status
  lines and the dates the automation relies on.
- The navigation: two levels, at most fourteen entries per group, titles of at most five words.
- The reference: no cell over 25 words; the commands' synopses equal the command line (test); no catalog page over 300
  KB.
- Nothing the automation reads has changed its meaning: the 415 references resolve (`test_references.py`), the hook's
  digest of 11.4 is the same, the six tests are green, the review's list of moved or reworded statements per chapter is
  empty for the sections the automation names, and `mkdocs build --strict` passes as today.

## Alternatives

- **A – a new structure, new files.** Tutorials, how-to guides, reference, explanation (Diátaxis), each chapter cut into
  pages of one kind. Cleanest on paper. It costs every address – the 415 references, the hook's section, the tests, the
  paths the skills open –, the text that is true today is rewritten and can drift, and it is weeks. Not recommended; the
  reader's order is had for less by the navigation.
- **B – the entry layer only.** One session; the newcomer gets in, and on the second page meets a section of 300 lines
  with sentences of 56 words. The maker is the reader with the most to read, and B leaves them the most.
- **C – this concept.** The entry layer, the navigation by reader, the chapters trimmed in place under the rules for
  what the automation reads, the reference generated, a style guide with a test. Recommended.
- **Another generator.** Sphinx, Docusaurus, mdBook: none of them fixes a sentence. MkDocs Material has what the
  proposal uses – search, dark mode, mobile, admonitions, definition lists, the brand – and stays.

## Costs and risks

- **Work.** About six sessions for D.1 to D.4, D.6 and D.7, one per large chapter for D.5 – ten –, each followed by the
  review. The owner's tokens.
- **A meaning shifts where the automation reads.** The largest risk, and the owner's condition. Held by the rules above:
  addresses fixed, statements of named sections in place, 11.4 untouched, the review reading old and new side by side
  with the places that name the section, `test_references.py` red before a section goes. What the rules do not catch – a
  shortened sentence that a skill read differently – is found by the review's reading of the skills against the new
  text, or by the first session that runs the skill; the first sessions after a trimmed chapter are watched for it.
- **Drift from the code.** A trimmed chapter can lose a true sentence. The review checks each chapter against the code
  after its branch (`docs/organisation.md`); the tests hold the quoted outputs; a correct sentence stays as it is,
  shortened only where it is nested.
- **Two registers on one site.** The entry pages short, the guides dense: a reader notices the seam at the first guide
  page. The first paragraph of each guide page – for whom, what after – is the bridge, and D.5 narrows the gap.
- **The catalog's and the skills' words bind the glossary.** A term the documentation would rather name differently
  stays as the sources have it; a better word is a finding for the owner and a change of the sources on their word.
- **Evidence leaves with the history.** "From the first graph to a released set in five days" is an argument for edakit;
  it moves to chapter 13 with the project described once, and the start page may quote the number with the link.

## Decisions

Taken by the owner on 2026-10-31, in a decision round in Claude Code's form; "accepted" is the owner's yes to the
recommendation.

| # | Question | Recommendation | Alternatives | Decision |
| --- | --- | --- | --- | --- |
| 1 | The structure | C: the entry layer, the navigation by reader, the chapters trimmed in place under the rules for what the automation reads, the reference generated; files and numbers stay | A: a new structure with new files; B: the entry layer only | accepted |
| 2 | The sources on the site | kept, as the last group "Inside edakit" with an index and a source line added by the site, the texts untouched | off the site, links to GitHub; as today | accepted |
| 3 | The spelling | British as written; "catalog" edakit's own name, "catalogue" JLCPCB's; the exceptions in documentation unified, sources as they are | American | accepted |
| 4 | The voice | "you" for the reader, "Claude" for the session; "the user" and "the owner" leave the reader pages' own sentences, quoted sources keep their words | as today | accepted |
| 5 | The history and the private projects | dates and the story leave the guides for chapter 13; "the reference project" described there once and named nowhere else; the example and the open designs are the examples; dates the automation relies on stay | stays inline, as today | accepted |
| 6 | The README | one screen: what, for whom, needs, not, install, try it, next; the command block to the reference, the repository map to organisation.md, "Status and limits" to "How it works"; `test_plugin.py` follows | as today, with a shorter head | accepted |
| 7 | The command reference | entries: the synopsis generated from the parser and held by a test, reads, writes and exit codes hand-written beneath; the help texts changed only in `cli.py` through a branch | the table as today; fully generated (loses reads and writes) | accepted |
| 8 | "What changed" from the merge commits on the site | not built until a reader asks: the commit messages are written for the owner | built with D.3 | accepted |

Decided by Claude and confirmed by the owner on 2026-10-31: MkDocs Material stays; chapter files and numbers stay;
sources, data and code untouched, with the rules of the section "What the automation reads"; `tests/test_references.py`;
a glossary in the sources' words; the style guide with its test; the navigation two levels deep; prototype READMEs off
the navigation; CLAUDE.md on the site as a source page; `organisation.md` and the brand page on the site; the quickstart
offline and held by a test; the first reader as an eval case; the pipeline drawing in the brand's colours; the paths
`docs/style.md`, `docs/glossary.md`, `docs/quickstart.md`, `docs/how-it-works.md`.

## Sources

- edakit at `8fba5f2`: [docs/pages.py](../../pages.py), [docs/organisation.md](../../organisation.md),
  [docs/catalog/build.py](../../catalog/build.py), [edakit/catalog/handbook.py](../../../edakit/catalog/handbook.py),
  [edakit/agreements.py](../../../edakit/agreements.py), [edakit/cli.py](../../../edakit/cli.py),
  [README.md](../../../README.md), [handbook/README.md](../../../handbook/README.md) and chapters 1 to 17,
  [tests/test_pages.py](../../../tests/test_pages.py), [tests/test_plugin.py](../../../tests/test_plugin.py),
  [tests/test_catalog.py](../../../tests/test_catalog.py),
  [tests/test_walkthrough.py](../../../tests/test_walkthrough.py),
  [tests/test_agreements.py](../../../tests/test_agreements.py),
  [tests/test_catalog_page.py](../../../tests/test_catalog_page.py),
  [.claude-plugin/plugin.json](../../../.claude-plugin/plugin.json), [CLAUDE.md](../../../CLAUDE.md).
- The site built from that commit with `python3 docs/pages.py` and `mkdocs build --strict` (mkdocs 1.6.1,
  mkdocs-material 9.6.23), read at 1440 and 390 px wide.
- The measures: words and sentences of the prose outside tables and code blocks, split at `.`, `!` and `?`; headings and
  section lengths by line; cross-references as "(N.N)" and bare "N.N"; the words counted by plain search over
  `README.md` and `handbook/`; the references to the handbook as `handbook N` and `handbook/NN-` over the `.py`, `.md`,
  `.toml`, `.sh` and `.json` files of `edakit/`, `skills/`, `agents/` and `.claude/`.
- `examples/coin-cell-led`: `edakit check` in 0.2 s, `edakit explain PATH.reverse`, on 2026-10-31.
