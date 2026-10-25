---
name: add-rule
description: Turn knowledge into edakit – a new check, a design hint, a building block, a part fact, or a retired check – with catalog entry, code, negative test, handbook, and a run against real projects. Use in the edakit repository when the user asks to add a rule ("make D-17 of the bell a check", "a hint for …", "a block for …", "retire G-…"), and from triage-rule for an accepted rule proposal. Only on the user's request – what becomes knowledge is the user's decision.
argument-hint: "<the rule, hint or block – a project decision with 'edakit: open' – or an accepted proposal issue>"
---

# Add knowledge to edakit

Wanted: $ARGUMENTS. How catalog, hints and blocks fit together: `handbook/14-design.md`.

Nothing here starts by itself. A check candidate from a review or a project decision (`edakit: open`) becomes edakit
knowledge when the user asks – here, or by proposing it from the project (plugin skill propose-rule), which the
Action rule-proposals triages with the skill triage-rule and builds with this one. If the request leaves open what
exactly the rule says, ask before building; for a proposal, that is a **Question** of the triage.

## 1. What kind of knowledge

| It is … | It goes into |
|---|---|
| decidable by a program from graph, parts database, simulation, plan or Gerber files, without false alarms on real projects | a **check** (P, G, E, L, F) |
| worth a reminder but needs judgement; tied to kinds of parts or a pattern | a **hint** (H) |
| a fact from one part's datasheet: strapping level, built-in pull, a warning, a rating | that **parts entry** (`strap`, `pull`, `pull_ohm`, `hint`, `hints`, ratings) – in the project, and in `edakit/blocks/parts/` if a block uses the part |
| a small circuit worth reusing, with checked parts | a **block** |

In doubt between check and hint: a hint. A check that has to guess produces waivers instead of findings.

## 2. A check

1. **ID:** the next free number of its stage in `edakit/rules.json`, never a retired one (G-7). IDs are public:
   protocols, waivers and accepted warnings refer to them.
2. **Catalog entry:** `title` (the words next to the ID), `rule` (one sentence), `why`, `fix`, `sources`. Every source
   opened and read – document number, revision, section; for a lesson of a project the handbook section or the
   project's decision. A source that was not checked does not go in. `tests/test_rules.py` fails until the entry is
   complete and every ID of the code has one.
3. **Code:** P and G in `edakit/checks.py` (a function, its call in `run()`, the ID in `EXECUTED`, the module
   docstring), E in `edakit/sim/run.py` (and `netlist.py` if the model needs it), L and F in `edakit/release/fab.py`.
   The message starts with designator or net, gives the numbers and says what is wrong; `waive` on the net or the
   component accepts a finding with its reason.
4. **Seen red once:** build the fault into the example (`tests/fixtures/led-bar`; helpers in `tests/conftest.py`,
   checked parts with `project.use_library_part`) and expect exactly this check, then the repaired circuit without it.
   `test_example_is_clean` stays green.
5. **Real projects, read only:** run it on the projects at hand. `edakit check` and `edakit hints` write nothing; for
   the simulation call `run_all` from Python – `edakit sim` writes `net_currents.json` into the project. A project
   without edakit.toml gets one in the scratchpad that points at its graph and parts. Every new finding there is a
   real fault (tell the user) or a false alarm (fix the check before going on).
6. **Handbook:** the check table (3.3 for P and G, 5.3 for E, 8.1 for L and F), new fields in 3.1 or 4.1, the skills
   that name the fields (part-search), chapter 14 if the way of working changes.
7. **Close the loop:** the project's decision that held the candidate gets the ID (`edakit: G-15`) – in that
   project's repository, with the user's OK. For a proposal the triage comment says it and propose-rule does it in
   the project.

## 3. A hint

An entry under `hints` in `edakit/rules.json`: `title`, `when`, `why`, `fix`, `sources`. `when` is `kinds` of parts or
`match` with a function in `MATCHERS` of `edakit/rules.py` (a new function gets a test in `tests/test_rules.py`). Run
`edakit hints` on the real projects: a hint that fires where it makes no sense gets ignored everywhere. Table in
handbook 14.3.

## 4. A block

`edakit/blocks/<name>.json` after the pattern of an existing block: `ports` (the nets that connect outside; `gnd`
joins the ground), components with `{as}` in their labels, nets with `v` (a range or `"@port"`), `covers` (the checks
and hints it takes care of), `notes` (what is left to decide). Its parts entries go to `edakit/blocks/parts/`: checked
against the datasheet, in English. Add the block to `CONNECT` in `tests/test_block.py` – the tests then make sure that
it passes `edakit check` and `edakit sim` in the example. Table in handbook 14.5.

## 5. Retiring a check

Keep its entry and add `retired` (what checks it now); take the ID out of `EXECUTED` and the code out of the run. The
number stays taken.

## 6. Finish

```bash
uv run --group dev pytest -q
uvx ruff check edakit tests
cd tests/fixtures/led-bar && uv run --project ../../.. edakit check && uv run --project ../../.. edakit sim
```

Commit as the repository does (code with tests, then the handbook); push only when the user says so. A proposal
built by triage-rule is one commit, pushed to `rules/proposals`.
