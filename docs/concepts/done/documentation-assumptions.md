# The documentation concept built: the assumptions to review

Status 2026-11-01: built in one evening on the owner's word ("implement the whole documentation concept, without
stopping, commit along the way, at the end pull, merge and touch up the docs; tomorrow morning we review the
assumptions you made along the way"). This file lists every judgement call made while building
[documentation.md](documentation.md), steps D.2 to D.9, for that review. Per chapter of the handbook the review of
step D.5 – what was cut, merged, moved or reworded, with the places in code, skills and agents that name the section –
is in [documentation-review/](documentation-review/). The owner's review closed on 2026-11-02 with decision 7 of
[documentation-newcomer.md](../new/documentation-newcomer.md), and this file and the folder moved here with the
concept.

## How it was built

- **One branch, one commit per step and per chapter**, merged at the end – instead of one branch per step and per
  chapter, as the concept's steps had it. The owner's word ("commit along the way, merge at the end") was read as
  that.
- **The chapters were condensed by parallel agents**, one per chapter, each with the same brief: the rules of "What
  the automation reads", a statement list before and after, every phrase searched over code, skills, agents and tests
  before it changed, no edit of a heading, a generated section or 11.4. Each wrote its review file. The lead read the
  reports, committed each chapter and kept `tests/test_style.py` in step.
- **Not done: 1.0.0.** The concept ties edakit 1.0.0 to D.2 (versioning.md, V.6). The major number is the owner's
  (CLAUDE.md), and a tag is never moved: the merge is a patch version, and 1.0.0 waits for the owner's word.

## D.4 – the reference

- **The short kind is named `table`** in `edakit/catalog/handbook.py`; the kind `codes` with the full texts stays in
  the generator, used by no chapter now. Under each table one line points to `edakit explain CODE` and the catalog
  page.
- **The catalog's codes link to the engine's page** – `docs/catalog/<prefix>.html#<CODE>` – not to the index.
- **10.5:** one `### edakit <command>` per subcommand in the parser's order (31), with the generated synopsis and help
  line; under it, per action, the table's row as lines – the command as written in the table, "EasyEDA: no / ✓ …",
  **Reads:**, **Writes:** – word for word. `edakit --version` is an entry of its own above them, not generated (it is
  no subcommand). The synopsis leaves out `-h`, `--config` and `-v`, which the section's first paragraph names once.
- **The catalog split**: 35 pages – one per engine, the domains, tables, schema, a page per reference circuit and per
  open design (one page of all of them would be 480 and 640 KB), the candidates, the check IDs of before.
  `index.html` keeps every code's id and the old section ids, so a link `catalog/#LIM.range` still lands on a row.
  Engines whose name is their prefix are titled by the prefix alone.

## D.2 – the entry layer

- **The quickstart runs the example with uvx**, through an alias, and quotes five commands (`graph show D1`, `check`,
  `explain PATH.reverse`, `sim`, `schematic draw`); `tests/test_quickstart.py` runs each on a fresh copy and wants the
  quoted lines. It uses the example's JSON graph as it is – the example was not moved to TOML.
- **The pipeline drawing** is `docs/pictures/pipeline.svg`, drawn by hand in the brand's colours, light and dark by
  the reader's system setting (an SVG shown as an image does not follow the site's toggle).
- **The decision round on "How it works"** is shortened from the walkthrough's D-3, written in the form of the skill
  decision-round from the decision log – not a verbatim transcript of the session that took it, which is not in the
  repository.
- **"State"** is the README's "Status and limits", every statement kept, split into short sentences, with links to
  the handbook's sections instead of the concepts' plan steps.
- **The README** keeps "What it runs, sends, fetches" (outreach.md, K.2), the line on issues and the licences below
  its first screen. The skills-and-agents paragraph left it for table 11.1, so `tests/test_plugin.py` now holds 11.1
  alone. The update steps for Claude Code and VS Code moved into handbook 2.3, which had pointed back at the README.
  The bell's section moved to its project page with every statement.
- **"What it needs"** says "an account at the maker you order from" instead of the concept's "a JLCPCB account for
  stock": `edakit stock` reads JLCPCB's public pages, no account needed.
- **"Harness" on the README** reads "edakit specializes an agent harness for circuit design", linked to
  `docs/architecture.md`. The style test allows exactly one "harness" there; "GitHub Copilot" counts as a product's
  name, not as the buzzword.
- **The voice:** the style guide now says "the assistant" for the role and the assistant by name where it is meant –
  today "Claude" – as decision 8 of claude-independence.md amended decision 4. The pages keep "Claude", which is the
  assistant they mean today.

## D.3 – the site

- **The groups** are the concept's table, with one change: "Start" as a group of its own for the entry pages – the
  quickstart, How it works, the projects, the glossary – before "The circuit".
- **The concepts, skills and agents are behind an index each** in "Inside edakit", their pages off the navigation
  (reached from the index), so that every group stays at two levels and fourteen entries. The indexes are written by
  `docs/pages.py`, not kept as files.
- **The source line** is an admonition "A source" added by `docs/pages.py` under the title of every concept, skill,
  agent, the evals and CLAUDE.md – the sources' files stay untouched.
- **The footer** carries both the version line and the feedback line, through MkDocs' `copyright` field, so it is on
  every page without touching a page.
- **"Commands" and "Files and keys"** are one navigation entry, chapter 10, since MkDocs lists a page once.

## D.6 – the reader pages

- **"Working on edakit"** is a page of its own, linking `docs/organisation.md`, rather than an extension of
  organisation.md, which CLAUDE.md points sessions at for the kinds of content. The README's repository map was mostly
  in organisation.md's table already; the page has a short map of the main parts.
- **"Adding a rule"** says "the maintainer" for the one who merges – "the owner" stays on the developer pages.

## D.7 – the numbers

- **"What it costs"** on the start page quotes the one measured number there is: the six eval tasks of the baseline
  cost 0.55 USD together with Sonnet 5.5 and 1.48 USD with Opus 5.5, one run each. A gate run, a decision round and a
  whole circuit design have no measured token cost yet – open, for the evals with `--runs 3`. outreach.md's fact
  sheet (K.5) is not touched: outreach.md is to be revised anyway.

## D.8 – what changed

- **The changelog** is on the site under "Reference", as `CHANGELOG.md` rendered as it is.

## D.9 – the gallery

- **The bell's pictures** are copied from its repository at commit 49f3373 – the silkscreen, routing and placement
  pictures of main from release 20261101-142527 and the five drawn schematics –, not from the GitHub release's
  assets. The board's other layers (the pictures `<run>/pictures/` of section 12) are not in its repository yet; they
  come with its next gate run after the plugin update (its D-40).
- **The bell's "What edakit found"** holds the README's old "Where it stands" numbers, labelled as at its first
  release; the current runs differ (stitching vias of D-41).
- **pytree's pictures** the owner picked on 2026-11-02 (TD-82): the board and the schematic from the ordered release
  20261101-225744, the project's render of the tree in its hill – a photo of the delivered tree replaces it – and the
  copper review's before/after of the back. The sketch, the silkscreen art alone, the hill's drawings, the box and the
  booklet stay in the private repository. What the page says of the calendar stands before Christmas: the public
  repository pytree-adventskalender says the same.
- **The examples are cards** on the gallery's index with their top-side pictures, linked to their walkthroughs.

## D.5 – the chapters

- **No chapter came out a third shorter.** Every agent found the same: nearly every section is named by code, skills,
  agents or tests, and many sentences are shared word for word with docstrings, the catalog or skills – the brief's
  rule "a text found elsewhere stays" kept them. The statements won, as the concept says; what changed is the form –
  first paragraphs, subheadings every 80 lines, no paragraph over 120 words, shorter sentences, subjects in
  cross-references, "you" instead of "the user", the history out. The measure "a third fewer words" is unmet; a
  looser reading of rule 5 – a docstring that mirrors the handbook is no reader of it – would allow 10 to 15 % more.
  Decision for the owner: keep the strict reading, or loosen it per chapter.
- **The not-legal-advice line** stands once per page; the walkthroughs dropped their second and third mention.
- **Findings against the code**, collected in each review file, were not fixed: they are sources (codes.toml,
  docstrings, skills) or need a decision.
- **Chapters over 500 lines remain:** 4, 5, 7, 8, 10, 17 – the rule stays red for them.
- **Chapter 13 speaks as "we"**, as it did before; "the owner" there became "we". It describes pytree once, linked to
  its project page, and holds the other chapters' history in 13.7 (the days after the first board) and 13.8 (how the
  chapters' details came about). Chapter 8's "the reference project published its four boards – main, smd, tht,
  esp32" was the Christmas bell's: it moved to 13.6, the bell's section.
- **RED of `tests/test_style.py`** now holds what is left: chapters over 500 lines (4, 5, 7, 8, 10, 17), sections over
  80 lines in 10.7 (generated) and 11.4 (the agreements, quoted), dates in 8, 10 and 17 that statements rest on, and
  the examples' decision logs and READMEs, which were not touched.

## After the merge with main

- **`.github/merge.py`** had learnt meanwhile to regenerate a conflict in generated output, naming
  `docs/catalog/index.html`; since the split every page `docs/catalog/*.html` counts, `build.py` not.
- **`TODO.md`** goes through the notes lane after the merge: TD-29 to TD-35 ticked with the merge, the review of this
  file and the findings of the review files as one item for the owner, TD-79's mention of `docs/catalog/index.html`
  left to the session that holds TD-79.

## After the owner's first look (the same evening)

- **The README's links lead to the site**, not to the Markdown on GitHub, and the coin-cell example's schematic and
  board stand on the start page (#178).
- **pytree shows its board and schematic** (the owner: "pytree may show the schematic and so on"): the board drawn by
  edakit's `release/pictures.py` from the Gerber files of release 20261031-110510, front, back and all layers; the
  schematic drawn by `edakit schematic draw` from the graph at pytree's commit 8852d23, with today's edakit – pytree is
  pinned to an older one. The PNGs scaled to 1200 px for the page.
- **17.13 and 18.13 left the walkthroughs** (the owner: a walkthrough is no story of how edakit came about): their
  gaps are chapter 13's 13.9 and 13.10 now, the walkthroughs' references point there, and `edakit/part.py`'s docstring
  names 13.9. 18.13's "Open, noted for later" went to `TODO.md` as an item of its own.
