# How the documentation is written

For everyone who writes or changes edakit's documentation – a session in this repository included. After this page you
know which files it covers, how each kind of page is written, what you must not touch, and what
`tests/test_style.py` counts. The words themselves are in the [glossary](glossary.md).

## What it covers

The documentation as [organisation.md](organisation.md) lists it: `README.md`, `handbook/`, `docs/` outside
`concepts/` and `catalog/`, and the Markdown of `examples/coin-cell-led/` and `examples/blinker-555/`. Nothing else.

The sources keep their own words, and the documentation follows them:

- the catalog's and the domains' texts are data;
- the skills and agents are prompts;
- CLAUDE.md holds the rules of a session;
- the help texts of the command line and the docstrings are code;
- the concepts are sources.

Where the documentation needs a different word than a source uses, it takes the source's word. Where a source's text
should change, that is a finding for the owner, with its path and line.

## What you must not touch

The automation reads the handbook. Code, skills and agents name its sections ("handbook 8.6") and open its chapter
files, the SessionStart hook reads section 11.4, and six tests hold pages to the code. So:

- **Addresses stay.** Chapter files, chapter numbers and section numbers do not change. A new `###` adds an anchor and
  removes none. `tests/test_references.py` fails when a named section or file is gone.
- **Statements stay in their section.** In a section the automation names, a sentence may be shortened and a long
  section may get subheadings. No statement leaves the section, none changes its meaning.
- **Section 11.4 stays as it is.** Its numbered items with their bold titles are the working agreements, and a change
  of an agreement is the owner's.
- **Generated text changes in its generator.** Between `<!-- edakit:generated … -->` and `<!-- edakit:end -->`, between
  `<!--edakit …-->` and `<!--/edakit-->`, and a skill's description on its page: the source changes, the script runs
  again.
- **Unsure – check, then ask.** Before a sentence changes, search the phrase over `edakit/`, `skills/`, `agents/`,
  `tests/` and the other chapters. A text found elsewhere is a hint to leave it as it is. Still unsure, ask the owner in
  the branch's decision round. Nothing changes on a guess.

## Registers

Three, by layer. The entry pages are the start page, the quickstart, "How it works", the glossary and the project
pages; the guides are the handbook's chapters and the reader pages; the reference is chapter 10, chapter 9 and the
catalog pages.

| | Entry | Guides | Reference |
| --- | --- | --- | --- |
| Sentence | at most 20 words on average, none over 35 | at most 25 words on average | fragments allowed in entries and cells |
| Paragraph | at most four sentences | one idea, at most 120 words; a subheading every 80 lines at most | one entry per thing |
| Length | a page of at most two screens; the quickstart longer | a chapter of at most 500 lines; the same statements in a third fewer words than before its trim | as long as the things it lists |
| Asides | none – a second sentence instead | one per sentence, with the en dash | – |
| Cross-references | to the glossary and to one guide page, by name | the subject and the number: "the board file (10.2)" | by number and name |
| Terms | one new term per sentence, linked to the glossary at first use; the budgets below | as the glossary has them | as the glossary has them |
| History | none | none – it belongs in chapter 13 | none |
| State | a status admonition, one line | the same | the same |

A cross-reference names its subject. "The sign-off file (8.2)" tells a reader who does not know the numbering what is
there; "(8.2)" alone does not.

## Budgets

The lightest pages have a count, so that a newcomer meets the words one at a time
([documentation-newcomer](concepts/new/documentation-newcomer.md), decision 4):

- The start page: at most 120 words before the first picture, the two-minute command within its first 40 lines.
- How it works: at most 1,100 words and 15 glossary terms – a term counts when the page uses it, linked or not. The
  ten words the site rests on are the glossary's first section, and How it works links it.
- The quickstart: at most six glossary links. A steps page (`docs/steps/`): at most three, and no term it does not
  link.

## Dense

Every statement once, at the place that owns it. Everywhere else a link, not a paraphrase: the README's command block,
the commands of the reference (10.5) and `edakit --help` are one list in one place.

- One example where one shows it.
- No sentence that announces another.
- No restatement of a code block or a table in prose.
- No history in a guide.

Short sentences and dense text are not opposites. The words that go are the asides, the repetitions and the
enumerations, not the statements. A qualification – a number, a condition, an exception – is a statement and stays. A
shorter wording never trades a meaning: in a section the automation names, the wording gets shorter and nothing leaves.

## Words

- "You" for the reader, "edakit" for the tool. "The assistant" for the role the session plays; the assistant by name
  where it is meant – today "Claude", in Claude Code. "The plugin", "the command line", "the handbook", "the catalog",
  "the site" for its parts.
- "The owner" – edakit's owner, who decides – on the developer pages only. "The user" in no reader page's own sentence.
  A quoted skill, agreement or catalog text keeps its words.
- One word per thing, as the [glossary](glossary.md) has it and the skills and the catalog use it: hand-over, sign-off,
  tool chain, parts entry, board file, gate run, placement plan.
- British spelling, as written: colour, behaviour, centre, licence. "Catalog" is edakit's own name, "catalogue"
  JLCPCB's.
- No superlatives, no "simply", no "just", no "the hard way".
- No buzzwords – "harness", "agentic", "AI-powered", "copilot" and their kind. A page says what happens, not what it
  is called. The README names "harness" once, as a keyword linked to [architecture](architecture.md), which defines
  it; no other page uses it. A product's name, such as GitHub Copilot, is no buzzword.
- A number with its unit and a space: 0.2 mm, 5 V, 100 nF.
- An en dash ` – ` for an aside, plain declarative sentences.
- Prose wrapped at 120 characters.

## A page

- The first paragraph says for whom the page is and what they can do after it.
- The shortest path comes first, the details after it, the reasons at the end.
- A status admonition at the top where something is built offline only or planned – one line, not the state woven into
  the prose.
- A heading has at most five words where the navigation shows it. A chapter's H1 keeps its number.
- A table whose cells are paragraphs becomes prose with a short table, or entries.
- The history – dates, what went wrong in which week – goes to chapter 13. A date a finding or a skill relies on stays:
  the state of the law in chapter 15, the versions in chapter 2.
- Regulatory content says once that it is support, not legal advice, nothing legally guaranteed (CLAUDE.md).

## A project page

A page of the gallery (`docs/projects/`) is written in the entry register, its length set by its pictures. It explains
the project to a reader who has never seen it: what it is, the circuit with its drawn schematic and its blocks, the
board as made, what edakit found, its variants, what it changed in edakit. The pictures are the release's, copied with
its tag, never drawn by hand; the numbers name their release. The gallery shows what is built, nothing planned.

## A steps page

The steps (`docs/steps/`) are the person's manual: what you do, what you are asked, what you decide and what you get,
one page per step of the walkthrough's table. The handbook is the complete one, for the assistant and for looking
things up ([documentation-newcomer](concepts/new/documentation-newcomer.md)). A steps page is written in the entry
register, with these additions:

- **A budget.** At most 400 words, the index at most 300, all of them together at most 4,000. A page that would take
  more is two steps.
- **A title with a verb**, what you do, and a first line that says what you have after the step.
- **Three terms at most,** each linked to the glossary at its first use. A word the glossary has counts as a term,
  linked or not, so a page says "the shop" where it does not link "maker".
- **No aside.** A second sentence instead of an en dash; at most 20 words a sentence on average, none over 30.
- **Two links at the end,** under "Read on": the walkthrough's step and the chapter. No other link into the handbook,
  and no cross-reference by number.
- **Quoted, not restated.** A command's output comes from a real run on the example, and a test runs it again; a
  question stands in a block quote in the skill's own words; a number only as an output or the walkthrough shows it.
  A steps page states no limit and no rule of its own: those are the handbook's.

Nothing the automation reads – `edakit/`, `skills/`, `agents/`, `.claude/` – names a steps page, so the steps can
change freely. `tests/test_steps_pages.py` holds their shape, budgets, outputs, questions and that rule.

## Pictures, code and output

- One picture per guide page where it is faster than a paragraph: the pipeline, a drawn schematic, a placement plan, a
  gate protocol. SVG in the brand's colours ([brand](brand/README.md)). Where edakit draws it – `schematic draw`,
  `pcb plan` – it is generated and held by a test, as chapter 17's drawings are.
- A command and its output come from a real run, shortened with `…`, and a test holds them where it can
  (`tests/test_walkthrough.py` is the pattern).

## What the test counts

`tests/test_style.py` reads the documentation only. A page's own sentences are its text without generated sections,
code, block quotes, phrases in quotation marks and section 11.4. In them it counts:

- on the entry pages, the average and the longest sentence;
- a section over 80 lines without a subheading;
- a chapter of the handbook over 500 lines, and a paragraph over 120 words;
- a bare cross-reference: a parenthesis of section numbers only at the start of a paragraph or after a punctuation
  mark, or "see 8.2" – whether the word before "(8.2)" is its subject is the review's to judge;
- "the reference project" and "the user";
- a date outside chapter 13, chapter 15 (the state of the law), a decision log and the status lines;
- on the entry pages, a term in bold that the glossary does not have – a bold title of a paragraph or an item is no
  term;
- a buzzword outside [architecture](architecture.md) and the README's one "harness";
- the budgets: the start page's words before the first picture and the line of its two-minute command, the words and
  the glossary terms of How it works, the glossary links of the quickstart and of a steps page;
- on a steps page, a glossary term it does not link, a sentence over 30 words and an aside.

A page that does not meet a rule today is listed in the test as expected to fail, and the test fails once the page
meets it, so that the entry leaves the list. A new page meets every rule from the start. The rest – meaning, order, the
right word – is the documentation review's ([organisation.md](organisation.md)).
