# Adding a rule

For engineers who know a fault edakit does not find yet. After this page you know what a rule is made of, where each
kind of knowledge goes, how it is tested, and how a project proposes one. You need electronics, not Claude Code; the
work itself is the skill add-rule, in a session in this repository, or a pull request by hand.

## What a rule is made of

edakit's knowledge is data, read by small engines. A rule is one of five kinds:

| Kind | What it is | Where it goes |
| --- | --- | --- |
| fact | a number or property of a part, a default for a kind, a row of a standard's table | the parts entry; `edakit/catalog/needs.toml`, `levels.toml`, `paths.toml`; `edakit/catalog/tables/<name>.toml` |
| relation | a check a program can decide without false alarms, or a hint that needs judgement | a code `ENGINE.relation` in `edakit/catalog/codes.toml` and its place in the engine; a hint `HINT.<name>` |
| domain setting | how severe a code is in an area, a fact a kind must give there, a reviewer's question | `edakit/domains/<name>.toml` |
| block | a small circuit worth reusing, with checked parts | `edakit/blocks/<name>.json`, its parts in `edakit/parts/` |
| retirement | a code that no longer holds or that another one covers | `[retired]` of `codes.toml` |

A fact comes before a relation: most lessons are a number a part or a table did not have. In doubt between a code and
a hint, a hint – a code that has to guess produces accepts instead of findings. How engines, codes, data and domains
fit together is in [the catalog (14.2)](../handbook/14-design.md#142-the-catalog-engines-codes-data-and-domains).

## A code's fields

A code in `codes.toml` has a `title` – the words next to the code –, a `rule` in one sentence, `why`, `fix`, a
`severity` and its `sources`, every one opened and read. A new code starts as a warning. Optional: `grades` for
sub-cases with their own severity, `details` for lines the catalog shows under the rule. `catalog.lint()` fails until
the entry is complete. Every code explains itself with `edakit explain` and on the [rule catalog](catalog/index.html).

## Seen red once

Every check is tested on a fault built into a copy of an example: the test expects exactly this code, then the
repaired circuit without it. The example is `tests/fixtures/led-bar`, with helpers in `tests/conftest.py` and
`tests/helpers.py`; a fault of the manufacturing files goes into `FAULTS` of `tests/test_fab_run.py`. A rule that has
never failed a test is a guess.

## Against real circuits

A new rule runs on the reference circuits – one per domain in `tests/reference.py`, each with its seeded faults – and
on the published open designs in `tests/open_designs/`, every finding there judged. A finding on a real design is a
real fault or a false alarm; a false alarm is fixed before the rule goes in. The circuits and how a finding there is
judged: [How edakit is tested](../handbook/19-verification.md) (handbook 19).

## The generated sections

The handbook's tables of codes, the parts schema and the map of old check IDs are generated from the catalog, and so
are the catalog's pages:

```bash
uv run python -m edakit.catalog.handbook --write
uv run python docs/catalog/build.py
uv run --group dev pytest -q
```

`tests/test_catalog.py` and `tests/test_catalog_page.py` fail while either is out of date.

## Proposing a rule from a project

What a project teaches goes back with `/edakit:propose-rule`: a part fact, a check or hint, a domain setting, a block
or a retirement, as an issue in this repository sealed with its SHA-256. The Action proposals triages the
maintainer's sealed proposals: accepted and built into one pull request, rejected with the reason, or a question back.
An issue by someone else becomes a proposal when the maintainer adopts it with a sealed comment. The way from a
finding to a rule is in [handbook 14.4](../handbook/14-design.md#144-from-a-finding-to-a-rule).

A rule of the regulatory review is graded by the board's purpose: what the firmware or a data entry can settle is a
note, a warning for a board that is sold, an error only where the hardware cannot comply
([the regulatory review, 15.4](../handbook/15-regulatory.md)). It is support, not legal advice.

## Where to read on

- The skill add-rule, step by step: [`.claude/skills/add-rule/SKILL.md`](../.claude/skills/add-rule/SKILL.md).
- How the repository is organised: [organisation](organisation.md).
- The designer's view of checks, hints and blocks: [designing a circuit](../handbook/14-design.md).
