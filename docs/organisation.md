# How the repository is organised

What each part of the repository is, who keeps it, how it changes – and which files a review of the documentation
may change and which it only reads. For everyone working on edakit itself; the handbook is for those who use it.
The working rules for sessions in this repository are in [CLAUDE.md](../CLAUDE.md).

## Kinds of content

| Kind | What it is | How it changes |
|---|---|---|
| **Documentation** | Text for the reader of edakit: what it does, how and why | Kept true to the code; a review of the documentation corrects it |
| **Source** | Working material that the documentation and the work draw on: rules for sessions, open work, concepts, prompts of skills and agents, the workflows | Only by the work it belongs to and the owner's word – never by a review of the documentation, which only reads it and reports what it finds |
| **Code** | The Python package, the plugin's entry points | Through a branch, test first |
| **Data** | Catalog, domains, blocks, parts, makers, fees – knowledge as text | Through the skills add-rule and add-feature, on the owner's word |
| **Generated** | Written by a script from code or data | Never by hand: the source changes, the script runs again |
| **Test data** | Projects, fixtures and recordings the tests read | With the tests that use them |

## The repository, path by path

| Path | Kind | Content |
|---|---|---|
| [README.md](../README.md) | Documentation | The start page – also of the site |
| [handbook/](../handbook/README.md) | Documentation | The handbook, chapters 1 to 18 |
| [docs/](.) | Documentation | Documentation beside the handbook: the entry pages – the [quickstart](quickstart.md), [how it works](how-it-works.md), the [projects](projects/README.md) with their pictures, the [glossary](glossary.md) –, the reader pages [adding a rule](adding-a-rule.md), [working on edakit](working-on-edakit.md) and [architecture](architecture.md), the [style guide](style.md), [brand/](brand/README.md) (logo, colours, type), `pictures/` and this page – all of `docs/` except `concepts/`, `catalog/` and `pages.py` |
| [examples/coin-cell-led/](../examples/coin-cell-led/README.md) | Documentation | The project of the walkthrough (handbook 17): its README and `docs/decisions.md` are documentation, its `edakit.toml` and `hardware/` project data the tests hold to the chapter |
| [examples/blinker-555/](../examples/blinker-555/README.md) | Documentation | The project of the KiCad walkthrough (handbook 18): its README and `docs/decisions.md` are documentation, its `edakit.toml` and `hardware/` project data the tests hold to the chapter |
| [docs/concepts/](concepts/) | Source | Concepts – documents with a short life: `new/` what is open, `done/` what is settled and built, `discarded/` what the owner rejected; how a concept moves is in CLAUDE.md |
| [docs/catalog/](catalog/build.py) | Generated | The catalog as pages – an index, one page per engine, the domains, tables, schema, reference circuits and open designs, `circuits/*.svg` –, written by `docs/catalog/build.py` from the catalog – never edited by hand |
| [docs/pages.py](pages.py) | Code | Assembles the site |
| [CLAUDE.md](../CLAUDE.md) | Source | The working rules for sessions in this repository |
| [CHANGELOG.md](../CHANGELOG.md) | Generated | What changed in each version of edakit, for a maker who updates – a section per version, written once by `.github/merge.py` from the fragments |
| [changes/](../changes/README.md) | Source | The fragments: one file per branch, what it changes for a project and whether a project must act (`minor`) or not (`patch`); empty on main but for its README |
| [TODO.md](../TODO.md) | Source | Open work that needs the owner's computer, a maker or the owner's word, at the top what only the owner can do ("For the owner"); an item is ticked off with the commit that does it |
| [skills/](../skills/), [agents/](../agents/) | Source | The plugin's skills and agents: prompts that steer Claude in a project |
| `.claude/` | Source | The skills of this repository (add-rule, add-feature, triage-rule, triage-feature, triage-request) |
| `.claude-plugin/` | Source | Plugin and marketplace manifests |
| `.github/` | Source | The workflows: tests, the site, proposals and the wrapping of texts by others on issues, the checks of a pull request, versions; `merge.py` and `versions.py`, which number a version, and `notes.py`, the notes lane for concepts and TODO.md; the protection of main as text, `rulesets/` and `rulesets.py` (docs/concepts/done/versioning.md) |
| [evals/](../evals/README.md) | Source | Tasks and graders for `claude plugin eval` |
| [upstream/](../upstream/README.md) | Source | What edakit needs from EasyEDA Pro and easyeda-mcp-pro – the requirements, their state upstream, drafts of issues and pull requests, posted only on the owner's word |
| [edakit/](../edakit/) (without the folders below), [bin/](../bin/), [hooks/](../hooks/hooks.json) | Code | The Python package and command line, the plugin's command and hooks |
| [edakit/catalog/](../edakit/catalog/), [edakit/domains/](../edakit/domains/), [edakit/blocks/](../edakit/blocks/), [edakit/parts/](../edakit/parts/), [edakit/makers/](../edakit/makers/), [edakit/fees/](../edakit/fees/) | Data | Codes and tables, domains, building blocks, parts entries, the makers' profiles, the fee table |
| [tests/](../tests/) | Code, test data | The tests; `tests/fixtures/` and `tests/open_designs/` – their READMEs included – are test data |

Generated parts inside documentation: the sections of the handbook between `<!-- edakit:generated … -->` and
`<!-- edakit:end -->` come from `edakit/catalog/codes.toml` and `kinds.toml` (`python -m edakit.catalog.handbook
--write`; `tests/test_catalog.py` fails when they differ). Values between `<!--edakit …-->` and `<!--/edakit-->` are
quoted from the design data and filled in by `edakit docs --write`.

## The site

[docs/pages.py](pages.py) assembles the site on every push and `.github/workflows/pages.yml` publishes it from main:
the README, the handbook, the concepts, the skills, the agents, the evals' README and the catalog page. That a file is
on the site makes it readable there, not documentation: concepts, skills, agents and evals stay sources.

## A review of the documentation

- **Changes:** the files of kind documentation above – `README.md`, `handbook/`, `docs/` without `concepts/`, `catalog/`
  and `pages.py`, the Markdown of `examples/coin-cell-led/` and `examples/blinker-555/` – outside generated sections and
  quote blocks. A new document in `docs/` is documentation unless it is listed here as something else.
- **Reads:** everything else, the code above all: a claim that can be checked is checked against it. What is wrong in
  a source, in data or in a generated section goes to the owner as a finding with its path and line – a generated
  section is fixed in its source, through the skill add-rule or add-feature, on the owner's word.
- **Catalog texts are data.** The rule, why, fix and details of `edakit/catalog/*.toml` and the texts of
  `edakit/domains/*.toml` read like documentation – in the handbook's generated sections, in `edakit explain`, on the
  catalog page – but they are data. A review of the documentation never changes them, not even when asked during the
  review: it reports them, and a correction is a piece of work of its own.
- **Style:** the [style guide](style.md) – registers, words, what a page starts with, what `tests/test_style.py`
  counts – and the words of the [glossary](glossary.md). A correct sentence stays as it is.
- **Not legal advice:** regulatory content says once that it is support, not legal advice (CLAUDE.md).
