# The documentation concept built: the assumptions to review

Status 2026-11-01: built in one evening on the owner's word ("implement the whole documentation concept, without
stopping, commit along the way, at the end pull, merge and touch up the docs; tomorrow morning we review the
assumptions you made along the way"). This file lists every judgement call made while building
[documentation.md](documentation.md), steps D.2 to D.9, for that review. Per chapter of the handbook the review of
step D.5 – what was cut, merged, moved or reworded, with the places in code, skills and agents that name the section –
is in [documentation-review/](documentation-review/). Once the owner has gone through it, this file and the folder
move to `docs/concepts/done/` with the concept.

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
