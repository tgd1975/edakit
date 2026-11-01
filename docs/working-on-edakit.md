# Working on edakit

For developers who change edakit itself – its code, its catalog, its documentation. After this page you know how the
repository is organised, how a change gets onto main, how the tests and the evals hold it, and how the site is built.
What edakit is as a system is on the [architecture page](architecture.md).

## The repository

[Organisation](organisation.md) lists every path with its kind: documentation, source, code, data, generated or test
data. The kind decides how a file changes. Documentation is kept true to the code. Code changes test first. Data – the
catalog, domains, blocks, parts, makers – changes through the skills add-rule and add-feature, on the owner's word. A
generated file is never edited by hand: its source changes and the script runs again.

The main parts:

| Path | What it holds |
| --- | --- |
| `edakit/` | the Python package and command line: checks, simulation, the EasyEDA and KiCad tool chains, PCB, routing, Gerber analysis, the gate, ordering |
| `edakit/catalog/`, `edakit/domains/` | the engines' codes with rule, why, fix and sources; the tables; the domains of rules |
| `edakit/blocks/`, `edakit/parts/`, `edakit/makers/` | building blocks and their checked parts; the makers' profiles |
| `skills/`, `agents/`, `hooks/`, `bin/` | the Claude Code plugin |
| `handbook/`, `docs/`, `README.md` | the documentation; `docs/concepts/` the concepts |
| `tests/`, `evals/` | the negative tests and their fixtures; the evals for `claude plugin eval` |
| `upstream/` | what edakit needs from EasyEDA Pro and easyeda-mcp-pro, as requirements |

## The rules of a session

A session in this repository works by [CLAUDE.md](../CLAUDE.md). In short:

- **Concepts go on main** through the notes lane (`python3 .github/notes.py`), and so does every change of `TODO.md`.
  A concept starts in `docs/concepts/new/`, moves to `done/` once it is decided and built, to `discarded/` when the
  owner rejects it. The [concepts' index](concepts/README.md) shows each with its state.
- **Everything else goes through a branch**, onto main only with the owner's OK.
- **A merge is a version.** A branch that changes what a project reads carries a fragment `changes/<branch>.md`:
  `minor` when a project must act on the update, `patch` otherwise. `python3 .github/merge.py <pr>` numbers it, waits
  for the checks and merges; `release.yml` sets the tag. The major number is the owner's.
- **main is protected**: only pull requests with the checks test, kicad, build, paths and version green.
- **No click in EasyEDA because its API falls short**, and no patch of easyeda-mcp-pro of edakit's own: what edakit
  needs goes upstream ([upstream](../upstream/README.md)).

## Tests

Every check is seen red once: a fault built into a copy of an example, the code expected, the repaired circuit
without it. `tests/fixtures/led-bar` is the project the tests build their faults into; `tests/reference.py` holds a
reference circuit per domain with its seeded faults; `tests/open_designs/` holds published open designs with every
finding judged. Stages L and F run on a written export (`tests/test_fab_run.py`).

The documentation has tests of its own:

- `tests/test_references.py` – every handbook section and chapter file that code, skills and agents name exists;
- `tests/test_style.py` – the countable rules of the [style guide](style.md);
- `tests/test_walkthrough.py`, `tests/test_walkthrough_kicad.py`, `tests/test_quickstart.py` – what the walkthroughs
  and the quickstart quote still holds;
- `tests/test_catalog.py`, `tests/test_catalog_page.py`, `tests/test_agreements.py`, `tests/test_plugin.py`,
  `tests/test_pages.py` – the generated sections, the catalog's pages, section 11.4, the plugin's lists, the site.

```bash
uv run --group dev pytest -q
uvx ruff check edakit tests
```

## Evals

`evals/` holds typical tasks on the reference circuits – find a seeded fault, report the coverage, add an LED – for
`claude plugin eval`, graded by a judge model. They measure whether Claude with the plugin does the job, not whether
the code is right; the tests do that. The baseline and how to run them: [evals](../evals/README.md).

## The site

`docs/pages.py` assembles the site into `build/pages`, MkDocs Material builds it, and the workflow `pages.yml`
publishes it from main. The navigation is data: the table `NAV` in `docs/pages.py`, a group per reader. The sources –
concepts, skills, agents, evals, CLAUDE.md – are shown at the end as "Inside edakit", each marked as a source.

```bash
python3 docs/pages.py
uvx --with mkdocs-material==9.6.23 --from mkdocs==1.6.1 mkdocs build --strict -f build/pages/mkdocs.yml
```

The rule catalog's pages are written by `docs/catalog/build.py`, the handbook's generated sections by
`python -m edakit.catalog.handbook --write`.

## Contributing

Issues and pull requests are welcome; the owner merges. A question, a bug or a board built with edakit has its form
under [issues](https://github.com/tgd1975/edakit/issues/new/choose).

Rules and features also come from projects: `/edakit:propose-rule` and `/edakit:propose-feature` open a sealed issue.
The Action proposals triages the owner's sealed proposals only – it runs on the owner's credentials. An issue by
someone else becomes a proposal when the owner adopts it with a sealed comment. Accepted proposals are built into one
pull request each, and the owner merges ([adding a rule](adding-a-rule.md)).
