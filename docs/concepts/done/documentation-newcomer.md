# The documentation for a newcomer: two manuals, ten steps, a navigation that shows them

Status 2026-11-02: built, and moved to `done/` on the owner's word – N.1 to N.5 built, N.6 dropped; the gaps of both runs' `MISSING:` lines (below) closed with #267 (edakit 1.1.2): the smallest edakit.toml by hand (handbook 2.7), a 9 V snap and a slide switch in the parts library and how to list it by kind (4.1), a switch's `open` and a 9 V block as a cell state (5.1, 5.2), `bin/edakit` named by every skill where the session lacks it on the PATH, a refused write of `.claude/settings.json` or `core.hooksPath` named for the owner instead of failing silently, the form of a row a requirement's `rows` takes (10.4). The measure of six pages was not met – thirteen and fourteen pages opened; a new run would say whether the gaps closed it. Decided before: the seven decisions taken by the owner the same day in a decision round in Claude Code's
form (the table at the end): six as recommended, the newcomer's test as the eval alone, without a person – and
decision 6 taken again the same day after the eval's runs: no folding, ever; what Claude
had set itself – the budgets, the shape of a steps page, the ten pages, the tabs, the order of the steps – confirmed.
N.1 and N.3 built the same day on the owner's word (#215); N.2, N.4 and N.5's eval case built the same day on the
owner's word (#222, edakit 1.0.1); the eval's run waits for a cloud session – on this machine the Bash sandbox cannot
start (Ubuntu restricts user namespaces), and a first try stopped after two pages without a shell. Two cloud runs on
2026-11-02 did not count (TD-102): as root 0.33, as the user `eval` 0.83 – in both Bash could not write the workspace,
which the harness keeps under `TMPDIR` while denying writes to `/tmp`. The run that counts, the same day with
`TMPDIR=/srv/evaltmp` and the case as fixed for TD-103 (`d3485c3`): 0.875 (Sonnet, 0.88 USD, 32 turns) – `DONE: 6
components, 5 nets, 5 parts entries; 3 note, 6 accepted; requirements: 1 need, 1 requirement`; a graph of its own, the
clean check, the DONE line, `edakit check` run, two LEDs and no read of edakit's code passed; `few-pages` failed:
thirteen pages opened (twelve counted; `handbook/02-setup.md` read from an offset after a Grep) – `site/README.md`,
`docs/quickstart.md`, `docs/steps/README.md`, the steps `01` to `04`, and the handbook's chapters 14, 3, 2, 4, 10 and
5. Its `MISSING:` line: no page shows a minimal `edakit.toml` for a hand-wired circuit; the parts library has no 9 V
battery and no switch, and no page says to write the entries by hand; how a switch opens in `sim.json` and how to
model a 9 V cell are only implied; how to accept PATH.reverse for a keyed connector is not described; where `edakit`
lives when the plugin is not active is not said. It wrote every file by hand from the handbook and ran no skill,
taking the prompt's bar on edakit's code for one on the skills too; a second run with that bar lifted from the skills
(`382fc62`, #236): 0.875 (0.76 USD, 40 turns), the skills new-project, requirements and circuit-design run, `DONE: 7
components, 6 nets, 6 parts entries; 10 note; requirements: 1 need, 1 requirement`, fourteen pages – the start page,
the quickstart, the steps index and the steps `01` to `07`, the handbook's chapters 2, 3, 4 and 10 (eleven counted: 4
and 10 read through grep) –, and as missing: `edakit` not on PATH though the docs say the plugin puts it there; no way
shown to list the parts library by kind; no toggle or slide switch and no 9 V connector in it; whether `[boards.main]`
with a title alone is enough without a board; the writes of `.claude/settings.json` and the git hook path failed
without a fallback; which `rows` patterns `SIM.state` evidence takes. Asked for by the
owner the day after the documentation concept was built ("I am still not happy with the documentation; it is more
compact after the revision, but when somebody new looks at it, they run away – think about what we could do so that it
is not so overwhelming, and write a concept"). Written against main at `37a0745`, with
[documentation.md](documentation.md) as built (#174) and its review
([documentation-assumptions.md](documentation-assumptions.md), closed with decision 7); checked against
`530252a` (edakit 1.0.0): How it works gained a paragraph on the first order and has 1,705 words now, nothing else in
the table below moved.

## The short answer

The first round gave the site an entry – a start page of one screen, a quickstart, How it works, a glossary – and a
form for the chapters. It did not make the documentation smaller. The handbook has 119,000 words in 18 chapters, five
of them between 9,700 and 17,100 words, and the navigation shows all 39 pages of the site on every page. The first
click after the quickstart lands in the deep end: the walkthrough has 6,500 words, the handbook's own reading path to
a first circuit 36,000. The chapters could not be condensed – the statements won (D.5) – because the handbook has a
second reader who needs every one of them: the assistant in a session, which names it from 459 places. One text
serves two readers, and so the person reads the machine's manual.

Proposed: say that out loud and build the site on it. Two manuals from one source of truth. The **handbook**,
complete, is the assistant's and the look-up reader's, kept exactly as it is. **The steps**, the person's manual, are
new: ten pages of at most 400 words, one per thing you do or decide on the way from an idea to an ordered board, each
ending with the walkthrough's step and the chapter that has everything. A navigation in tabs by reader, so that a page
shows eight entries, not 39. The entry pages lightened: fewer words before the first picture, fewer terms before the
first command. And a measure that is the owner's sentence: a newcomer – a fresh session, the site its only input –
reaches a checked circuit of their own, or the eval says where it stopped.

What this moves into text that is in someone's head today: that the handbook is the assistant's manual, that the
person's manual is a different and short one, and the budgets that keep it short.

## What a newcomer sees today

Measured on main at `37a0745`: words by file, sentences of the prose outside tables, lists, code and headings, terms
as the glossary's 55 headings found on a page.

| Where | What they meet | Measure |
| --- | --- | --- |
| GitHub, the README | one screen: what it is, the case, two pictures, three doors; below it install, try it, what it runs and fetches, the licences | 1,249 words; about 200 before the first picture, about 400 before the first command; 15 terms |
| GitHub, the root | 23 entries – agents, bin, changes, evals, hooks, skills, upstream, TODO.md, CLAUDE.md among them | a workshop, and it stays one: the plugin's folders lie where Claude Code wants them, the handbook where 31 skill paths open it; the README is the door |
| The site, every page | the sidebar with every group expanded | 7 groups, 39 entries, on every page |
| Start → Quickstart | the example to its first finding and its drawing – the best entry there is | 746 words, 10 terms, held by a test |
| Start → How it works | the drawing, the stations, who does what, eleven words explained, the state, future work | 1,688 words, 29 terms – a glossary inside the entry |
| The quickstart's "Next" | "install the plugin and run `/edakit:new-project`"; what happens then stands on no page – the next links are the walkthrough and the handbook | the walkthrough 6,491 words; chapters 3 and 14 7,665 and 6,178 |
| The handbook | 18 chapters | 118,837 words, 9,161 lines; chapters 4, 5, 7, 8 and 10 between 9,657 and 17,083 words; sentences of 19 to 31 words on average in the guides, 34 in the reference |
| The handbook's reading paths | "first time": quickstart, 1, 2, 17, 3, 6, 7, 8; "new circuit": 14, 3, 4, 5 | 51,000 words; 36,000 words |

What works: the entry pages have short sentences (12 to 15 words on average), are true to the code and held by tests;
the quickstart gets a reader to a finding in a quarter of an hour; the gallery shows real boards. The wall stands
behind the entry, and the navigation puts it in view from the first page.

## Why the first round did not take the wall down

- **The handbook has two readers, and one of them needs everything.** 459 places in `edakit/`, `skills/`, `agents/`
  and `.claude/` name a section or open a chapter file; the SessionStart hook reads 11.4; six tests hold pages to the
  code. The skills lean on it – new-project names it 25 times, pcb-round 26. The agents that condensed the chapters
  found nearly every section named and many sentences shared word for word with docstrings, the catalog or skills,
  and the rule "a text found elsewhere stays" kept them ([documentation-assumptions.md](documentation-assumptions.md),
  "D.5 – the chapters"). That is not the rule failing. It is the handbook doing its job for its first reader.
- **The person's part is small, and no page says so.** Of the walkthrough's 14 steps the person acts in six: answer
  the interview, say what the board must do, decide on what the checks found, create the EasyEDA project, order and
  pay, hold the boards (17.1). The person does not operate edakit; the assistant does. A manual for the person is a
  manual for a conversation – what to say, what you will be asked, what you decide, what you get – and such a manual
  is short by nature. The site has no such manual. It has the machine's.
- **The navigation lists the repository.** `navigation.sections` renders every group expanded. A newcomer on the
  quickstart sees "Release gate", "EasyEDA API" and "Rules of a session" before reading a line.
- **The entry explains too much at once.** How it works introduces eleven terms in a row – the concept's "ten words";
  the README carries the versions, the trust statement and the licences, each in its place and all on the first page.

## The proposal

### 1. Two manuals from one source of truth

| | The handbook | The steps |
| --- | --- | --- |
| For | the assistant in a session; the engineer, the developer and whoever looks something up | the person who makes a circuit or a board with the assistant |
| Says | what edakit does: every case, every key, every finding | what you do, what you will be asked, what you decide, what you get |
| Size | 119,000 words today, no target any more | ten pages, at most 400 words each, at most 4,000 in all |
| Changes | under the rules of documentation.md: addresses, statements and 11.4 stay, the review reads for meaning | freely: nothing in `edakit/`, `skills/`, `agents/` or `.claude/` may name a steps page, and a test holds that |
| Held by | `test_references.py`, `test_style.py`, the six tests of the code | a test per quoted output (the quickstart's pattern); the review reads each page against the skill it describes |

The handbook is declared what it is. Its index says so in its first line – the complete handbook: what edakit does,
every case and every key; what the assistant reads in a session; the short way is the steps – and every chapter's
first paragraph gets one sentence, "The short way: <the step>". Nothing else in a chapter changes for this concept.
TD-81's question whether to loosen rule 5 is answered by decision 7: it stays strict, the handbook no longer has to
shrink for anybody, and TD-81 is closed.

### 2. The steps – the person's manual

`docs/steps/`, ten pages and an index, in the order of the walkthrough's table 17.1, in two groups:

| | Page | What it says | From |
| --- | --- | --- | --- |
| | Index | the ten in one table with who acts; one sentence on the three texts: the steps say what you do, the walkthrough shows it once on a real board, the handbook has everything | 17.1, How it works |
| 1 | Install | the plugin in Claude Code, uv, ngspice; EasyEDA Pro or KiCad only when a board comes | 2.2, 2.3 |
| 2 | Start a project | what `/edakit:new-project` asks and what it writes after your OK | the skill new-project, 2.7 |
| 3 | Say what it must do | the requirements round: your words, the assistant's questions until they are numbers, what you accept | the skill requirements, 3.6 |
| 4 | The circuit | the assistant designs; the checks and the simulation run; what you see | 14, 3, 5 |
| 5 | Decide on what was found | the decision round: a finding, its alternatives, the recommendation first, your answer in the decision log | the skill decision-round, 17.6 |
| 6 | Parts, stock, cost | what the assistant looks up and what you decide: assembly, distributors, quantity | 4.2, 17.7 |
| 7 | The drawing and the hand-over | the circuit as a result: the drawn schematic, the hand-wired board, the hand-over to the board | 6.5, 14.1, 17.8 |
| 8 | Reviews and sign-offs | who reviews what, M-1 to M-6 in one table, what you sign | 8.2, 17.9 |
| 9 | The board | EasyEDA Pro or KiCad; the one click; the PCB round in its own session; what you decide – looks, size, holes | 7, 16, 17.11 |
| 10 | Release and order | the gate, the release, the cart at the maker; you order and pay; the acceptance with the boards in hand | 8.3, 8.4, 8.5, 17.12 |

Steps 1 to 7 are the group "A circuit", 8 to 10 "A board" – the two stations of decision 9. A page has the shape of
the quickstart. Its first line says what you have at its end. Then what you do – the command, or the words to the
assistant –, what you will be asked, quoted as the skill asks it, what you decide, what you have, and two links at the
end: the walkthrough's step and the chapter. A command's output comes from a real run on the example, and a test holds
it (`tests/test_steps.py`, the quickstart's pattern). A question comes from the skill's text, and the documentation
review reads the page against the skill. A steps page states no limit, no number and no rule of its own – those are
the handbook's, linked – so that nothing can drift but the order of the steps.

### 3. The navigation shows the reader's way

Material's `navigation.tabs`: the groups become tabs across the top, the sidebar shows the current tab alone.

| Tab | Sidebar |
| --- | --- |
| Start | the start page, Quickstart, How it works, Projects, Glossary |
| A circuit | the steps' index, steps 1 to 7 |
| A board | steps 8 to 10 |
| Extend | Adding a rule, Propose a rule, Propose a feature |
| Develop | Working on edakit, edakit as a meta-harness, Organisation, Style guide, Brand |
| Handbook | its index, the chapters 1 to 18 by their numbers – the index says which to read when (decision 3, changed) |
| Reference | an overview pointing to 10, 9, the catalog and the glossary; the rule catalog's index, Changelog (decision 3, changed) |
| Inside edakit | its overview, the indexes of concepts, skills, agents and evals, the rules of a session (decision 3, changed) |

Eight entries in a sidebar at most, the handbook's excepted – its index says when to read which chapter. The sources –
concepts, skills, agents, evals, the rules of a session – have the last tab, "Inside edakit": its overview and their
indexes in the sidebar, the pages themselves out of the navigation but on the site and in the search, and every link
into them lands as today; the overview's old address sends the reader on (decision 2 of documentation.md stands). The
rule catalog leaves Start; it is reference. On a phone Material folds the tabs into the drawer as collapsed groups.
`docs/pages.py`'s table and `tests/test_pages.py` follow; no file moves.

### 4. The entry, lightened

- **The start page.** The first screen: one sentence what it is, the two pictures, the two-minute command, the three
  doors – at most 120 words before the first picture. The case stays as decision 11 has it, after the pictures; the
  harness keyword stays at the start (decision 14); the not-legal-advice line stays with "What it is not". The
  paragraph on versions moves to the "State" of How it works. The trust statement, the issue line and the licences
  stay below, as decided.
- **How it works.** "The words" – eleven terms, one paragraph each – moves to the head of the glossary as "The ten
  words first", and How it works links it. The page keeps the drawing, the two stations, who does what, how it is
  checked, the decision round, the state and the future work. Measure: at most 1,100 words and 15 terms.
- **A term budget.** A steps page links at most three glossary entries and uses no term it does not link; How it
  works has at most 15 terms; the quickstart keeps its six links. The budget is a rule of `docs/style.md` and a count
  of `tests/test_style.py`.

### 5. The newcomer's test

The eval `first-reader` runs a fresh session with the start page, the entry pages and the example as its only input
and asks for the example's first finding. A second case takes the whole site as built and a one-line idea – "a 9 V
battery, a switch, two LEDs" – and asks for a checked graph of its own, without EasyEDA. It passes when the graph
checks clean or every finding is accepted with a reason, and it records the pages opened; the result goes into this
concept's status line. The owner's sentence – "they run away" – becomes a number: whether the session got there, and
through how many pages. A person's try is not part of it (decision 5): the owner's own look stands in for it.

### 6. Later, if the chapters still deter: fold what is looked up

Chapters 4, 7 and 8 hold long reference blocks in their flow: every field of a parts entry (4.1, 350 lines), the
placement plan's keys (7.4, 360 lines), a project's scripts and agents (8.6, 375 lines). Material's collapsible blocks
(`???`, enabled in `docs/pages.py` already) would fold them under their heading. The text stays in the file, in its
section, with its anchors – the assistant reads the same Markdown –, and the rendered page shows the chapter's way
first. A presentation change, not a trim; one chapter per branch, the review as for D.5. Not now: the steps are tried
first, and this comes only if the eval's second case still fails or needs a chapter to pass (decision 6). Decided
against on 2026-11-02, after the runs: the owner does not want folding – the reference blocks stay as they are.

## How a steps page is written

The entry register of the style guide holds, with these additions, into `docs/style.md` and `tests/test_style.py`:

- **A budget.** At most 400 words; the index at most 300. A page that needs more is two steps.
- **A title with a verb** – what you do – and a first line that says what you have at the end.
- **Three terms at most**, each linked to the glossary at its first use; no bold term without a link.
- **No aside.** A second sentence instead of an en dash; at most 20 words per sentence on average, none over 30.
- **Two links at the end**, the walkthrough's step and the chapter; no other cross-reference by number.
- **Quoted, not restated.** A command and its output from a real run, held by a test; a question in the skill's
  words; a number only as the output shows it.

## Steps

| Step | What | Size | Waits for |
| --- | --- | --- | --- |
| N.1 | The tabs: `docs/pages.py`'s navigation as the table above, `navigation.tabs`, Inside edakit behind one page under Develop, the catalog out of Start; `test_pages.py` follows; checked at 1440 and 390 px, light and dark | S | the decisions |
| N.2 | The steps: `docs/steps/` with its index and ten pages, `tests/test_steps.py`, the test that nothing in `edakit/`, `skills/`, `agents/` and `.claude/` names them; the style guide's section and the counts in `test_style.py` | M–L, two sessions | N.1 |
| N.3 | The entry lightened: the start page's first screen, How it works without "The words", the glossary's "ten words first", the term budget counted | S | the decisions |
| N.4 | The handbook declared complete: the line on its index, "The short way" in each chapter's first paragraph | S | N.2 |
| N.5 | The newcomer's test: the second eval case, its numbers into the status line | S | N.2 |
| N.6 | Folded reference blocks in 4, 7 and 8, if N.5 still fails or needs a chapter – dropped, decision 6 of 2026-11-02: no folding | – | – |

N.1 and N.3 are one session and change what a newcomer sees first; N.2 is the substance. About four sessions to N.5.
Each step starts on the owner's word and comes into `TODO.md` when it does; N.1 and N.3 were built on 2026-11-02
(#215), N.2, N.4 and N.5's case the same day (#222). The steps' test is `tests/test_steps_pages.py` –
`tests/test_steps.py` holds the progress lines of the EasyEDA commands.

## Measures – done when

- The sidebar of any page shows at most eight entries, the handbook's tab excepted.
- The steps: at most ten pages and an index, no page over 400 words, at most 4,000 words in all, at most three
  glossary links per page, no aside, no cross-reference by number but the two at the end; every quoted output held by
  a test.
- The reading from the start page to a checked circuit of one's own – the first screen, the quickstart, steps 1 to 5
  – is under 3,000 words; to an ordered board under 6,000.
- The start page: at most 120 words before the first picture, the two-minute command on the first screen. How it
  works: at most 1,100 words and 15 glossary terms.
- No path under `docs/steps/` is named in `edakit/`, `skills/`, `agents/` or `.claude/`.
- The eval's second case reaches a checked graph of its own with the site alone and opens at most six pages; its
  result stands in the status line.
- The handbook: unchanged in meaning, the tests of documentation.md green. Its size is no measure any more.

## Alternatives

- **Trim the handbook further** (TD-81: loosen rule 5). The agents put the gain at 10 to 15 %; chapter 8 would still
  have 14,000 words, and the person would still read the machine's manual. Not the way in; the owner may loosen the
  rule for the look-up reader regardless (decision 7).
- **One page "The steps"** with ten sections instead of ten pages. Fewer clicks, but 4,000 words on one page is a
  wall again, and the navigation cannot show where the reader stands. Not recommended.
- **Split the walkthrough into the steps.** The walkthrough is the story of one board, held by a test to the example;
  the steps are generic and link the story. Both are needed.
- **Collapsible groups instead of tabs** – `navigation.sections` off, the current group expanded only. Cheaper by a
  line, but a tab says for whom it is where a collapsed group says nothing. Tabs recommended.
- **The handbook off the site**, for the assistant alone, search only. It is also the engineer's and the developer's
  reference, and the links from 459 places must land. It stays, in its own tab.
- **A second site for the handbook.** Two sites to build and to link; tabs do the same on one.

## Costs and risks

- **Work.** About four sessions, the owner's tokens.
- **Drift between the steps and the handbook.** A steps page could say what a chapter no longer does. Held by: no
  number or rule of its own on a steps page, every quoted output under a test, the review reading each page against
  its skill. Likely once a year, then ten minutes.
- **A third place to change when a step changes** – the skill, the chapter, the steps page. The steps say what you do
  and decide, which changes rarely; a changed interview changes one page. A few times a year, then a short branch.
- **The sources lose the navigation.** A developer reaches the concepts through Develop and the search; the index
  pages stay. A complaint once, then a link added.
- **Tabs on a phone.** Material folds them into the drawer. Checked in N.1 at 390 px, light and dark.

## Decisions

Taken by the owner on 2026-11-02 in a decision round in Claude Code's form, the recommendation first; six of seven as
recommended.

| # | Question | Recommendation | Alternatives | Decision |
| --- | --- | --- | --- | --- |
| 1 | Two manuals | the handbook declared the complete one and kept as it is; the steps as the person's manual, ten pages under 400 words | trim the handbook further (TD-81, rule 5 loosened); both | 2026-11-02: as recommended |
| 2 | The steps' shape | ten pages and an index in two groups, A circuit and A board, each page one step of 17.1 | one page with ten sections; the walkthrough split into pages | 2026-11-02: as recommended |
| 3 | The navigation | tabs by reader, eight entries a sidebar, the handbook its own tab, Inside edakit behind one page under Develop, the catalog out of Start | collapsible groups as today with the steps added; the handbook off the navigation, search only | 2026-11-02: as recommended; changed by the owner the same day – Inside edakit a tab of its own, its indexes in the sidebar: behind one page under Develop the skills were two clicks away (#239); then, on the owner's word: the handbook tab by number, 1 to 18 – in reading order the numbers looked jumbled (#242, #244) –, and every page's address under its tab, the files left where they are, each old address sending the reader on (#244) |
| 4 | The entry | the first screen with the pictures and the two-minute command, at most 120 words before the first picture; "The words" to the glossary's head; a term budget of three per steps page | the pages as decided in documentation.md, the steps added only | 2026-11-02: as recommended |
| 5 | The newcomer's test | the eval's second case and one person picked by the owner, the result in the status line | the eval alone; no test, the owner's own look | 2026-11-02: the eval alone – no person's try, the owner's own look stands in for it |
| 6 | Folding the reference blocks of 4, 7 and 8 | later, only if the newcomer's test still stops in a chapter | with N.2; never | 2026-11-02: as recommended – later, on the owner's word, if the eval's second case still fails or needs a chapter; the same day, after the runs: never – the owner does not want folding |
| 7 | TD-81's rule 5 | kept strict: the handbook is the assistant's and the look-up reader's and no longer has to shrink | loosened per chapter for 10 to 15 % | 2026-11-02: as recommended – kept strict, TD-81 closed with it |

What Claude had set itself was confirmed the same day: the budgets – a steps page of at most 400 words, the index
300, 4,000 in all, three glossary terms a page, sentences of 20 words on average and none over 30; How it works 1,100
words; the start page 120 words before the first picture –, the shape of a steps page, the ten pages in the order of
17.1 and the tabs' names, the test that nothing in `edakit/`, `skills/`, `agents/` and `.claude/` names a steps page,
and the order N.1 and N.3, then N.2, N.4, N.5 – with N.1 and N.3 started at once.

## Sources

- edakit at `37a0745`: `README.md`, `docs/quickstart.md`, `docs/how-it-works.md`, `docs/glossary.md`,
  `docs/style.md`, `docs/organisation.md`, `docs/pages.py` (`NAV`, the theme's `features`), `handbook/README.md`,
  chapters 1 to 18, `skills/*/SKILL.md`, `evals/first-reader/`, `tests/test_quickstart.py`, `tests/test_style.py`,
  `tests/test_pages.py`.
- [documentation.md](documentation.md) as built (#174) and its decisions 2, 9, 11 and 14;
  [documentation-assumptions.md](documentation-assumptions.md), "D.5 – the chapters"; `TODO.md`, TD-81 to TD-83.
- The measures: words by `wc -w` per file; sentences of the prose outside tables, lists, code and headings, split at
  `.`, `!` and `?`; glossary terms as the headings of `docs/glossary.md` found in a page; the handbook's references as
  "handbook N.N" and chapter paths over `edakit/`, `skills/`, `agents/` and `.claude/`; the reading paths summed from
  the chapters' words. The script ran in the session's scratchpad and is not kept.
- MkDocs Material 9.6.23: `navigation.tabs`, `navigation.indexes`, `pymdownx.details`.
