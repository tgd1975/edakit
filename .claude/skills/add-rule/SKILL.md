---
name: add-rule
description: Turn knowledge into edakit – a fact (a limit or value of a part, a default, a table row), a relation (a new code of an engine, a hint too), a domain setting (a severity, a required fact, a reviewer's question), a building block, or a retired code – with catalog entry, engine, negative test, generated handbook, and a run against real projects. Use in the edakit repository when the user asks to add a rule ("make D-17 of the bell a rule", "a hint for …", "a block for …", "retire GEO.…"), and from triage-rule for an accepted rule proposal. Only on the user's request – what becomes knowledge is the user's decision.
argument-hint: "<the rule, fact, hint or block – a project decision with 'edakit: open' – or an accepted proposal issue>"
---

# Add knowledge to edakit

Wanted: $ARGUMENTS. How engines, codes, data and domains fit together: `handbook/14-design.md` (14.2).

Nothing here starts by itself. A candidate from a review or a project decision (`edakit: open`) becomes edakit
knowledge when the user asks – here, or by proposing it from the project (plugin skill propose-rule), which the
Action proposals triages with the skill triage-rule and builds with this one. If the request leaves open what
exactly the rule says, ask before building; for a proposal, that is a **Question** of the triage.

## 1. What kind of knowledge

Ask first: which engine decides it, and from which data? Most lessons are a number a part or a table did not have.

| It is … | Kind | It goes into |
|---|---|---|
| a number or a property of one part: a limit, a value, a strapping level, a built-in pull, a pin function, a datasheet warning | fact | that parts entry (`limits`, `values`, pin fields, `hints`) – in the project, and in `edakit/parts/` if a block uses the part |
| what every part of a kind or role requires, a level at reset, a part a supply passes | fact | a default in `edakit/catalog/needs.toml`, `levels.toml` or `paths.toml` |
| a number of a standard or a manufacturer | fact | a row of `edakit/catalog/tables/<name>.toml`, with `source` and tag `r` |
| a field a kind may give | fact | `edakit/catalog/kinds.toml` (limits named `<quantity>_max_<unit>` are held by LIM without new code) |
| a relation no code finds, decidable by a program without false alarms on real projects | relation | a code `ENGINE.relation` in `edakit/catalog/codes.toml` and its place in the engine |
| worth a reminder but needs judgement; tied to kinds of parts or a pattern | relation | a hint, `HINT.<name>` |
| how severe a code is in an area, a fact a kind must give there, a question a reviewer asks | domain | `edakit/domains/<name>.toml` |
| a small circuit worth reusing, with checked parts | block | `edakit/blocks/<name>.json` |
| a code that no longer holds or that another one now covers | retire | `[retired]` of `codes.toml` |

A fact before a relation; in doubt between a code and a hint: a hint. A code that has to guess produces accepts
instead of findings.

## 2. A fact

1. **The data:** the field with its unit in its name (`v_max_v`, `i_max_a`, `tj_max_c` – the units in
   `kinds.toml [units]`), the value as the source gives it, and the source in the entry's `sources` or the row's
   `source` – document number, revision, section, page. A value not read from its source does not go in.
2. **Lint:** `edakit part lint` holds parts entries to `kinds.toml`; `tests/test_catalog.py` holds every table row to
   a source tagged `r`.
3. **What it changes:** run `edakit check` and `edakit sim` on the example and the real projects (step 6 of 3) – a
   new limit or default may raise findings there; each is a real fault (tell the user) or a wrong number.

## 3. A relation (a code)

1. **Name:** `ENGINE.relation` – the engine that decides it (`edakit rules` lists them), the relation in one or two
   words of the engine's vocabulary. A name in `[retired]` is not used again. A part of a code that a domain switches
   or a person accepts on its own is a topic (`REQ.missing:cc`), not a code; a sub-case with its own severity is a
   grade (`LIM.i/margin`).
2. **Catalog entry** in `codes.toml`: `title` (the words next to the code), `rule` (one sentence), `why`, `fix`,
   `severity` – a new code starts as `warning`; it becomes `error` by a later change; a regulatory one as section 5
   says –, `grades` if it has sub-cases,
   `sources`: every source opened and read; for a lesson of a project the handbook section or the project's decision.
   Optional `details`: lines the handbook shows under the rule. `catalog.lint()` fails until the entry is complete.
3. **Engine:** the graph engines in `edakit/engines/` (STRUCT `struct.py`, LIM `limits.py` with its producers in
   `quantities.py`, LVL `levels.py`, REQ `requires.py`, PATH `paths.py`, PARTS `parts.py`, HINT `hint.py`), the
   simulation's in `edakit/engines/sim.py` (a quantity with its limit, or a state check), the footprint checks of stage P
   in `edakit/checks.py`, SYNC, GEO and FILES of stages L and F in `edakit/release/fab.py`, DOCS in `edakit/docs.py` and
   `edakit/requirements.py`. A finding is `Finding(code, stage, place, text, source=…, fix=…)`: the place a designator,
   pin or net, the text with the numbers and what is wrong. A code of stage P or G beyond the graph engines goes into
   `executed()` of `edakit/release/gate.py`. `accept` on the net or the component accepts a finding with its reason.
4. **Domain:** a code for every board is core's and on by itself; one of an area goes into that domain's `[switch] on`.
5. **Seen red once:** build the fault into the example (`tests/fixtures/led-bar`; helpers in `tests/conftest.py` and
   `tests/helpers.py`, checked parts with `project.use_library_part`) and expect exactly this code, then the repaired
   circuit without it; an engine's own tests in `tests/test_engines.py`. `test_example_is_clean` stays green. L and F:
   one more entry in `FAULTS` of `tests/test_fab_run.py`, the written export of the example's input stage (handbook
   8.1).
6. **Real projects, read only:** run it on the projects at hand. `edakit check` writes nothing; for the simulation call
   `run_all` from Python – `edakit sim` writes `net_currents.json` into the project. A project without edakit.toml gets
   one in the scratchpad that points at its graph and parts. Every new finding there is a real fault (tell the user)
   or a false alarm (fix the code before going on).

## 4. A hint

A code `HINT.<name>` in `codes.toml` with `when`: `kinds` of parts, or `match` with a function in `MATCHERS` of
`edakit/engines/hint.py` (a new function gets a test in `tests/test_hints.py`); severity `note`. It is applied by the
domain that lists it in `[hints] apply` – core's for every board. Run `edakit check` on the real projects: a hint that
fires where it makes no sense gets ignored everywhere.

## 5. A domain setting

`edakit/domains/<name>.toml`: `[severity]` (`"LIM.range" = "warning"`, per purpose under `[severity.sale]`),
`[switch] on` (codes or `code:topic` only this domain reports), `[facts]` (per kind or graph type the facts an entry
must give – a missing one is `PARTS.fact`), `[hints] apply`, `[review]` (questions per reviewer: `electrical`,
`regulatory`, `pcb`; a question names the codes that cover part of its class). A new domain gets `[domain]` with
`name`, `about` and `suggested_by` (kinds, roles, values or radio). `tests/test_domains.py` holds the files to the
catalog; `edakit domains --review electrical` shows the questions.

**A regulatory topic is graded by the purpose** (handbook 15.4). What the firmware or a data entry can settle – the
channels, the transmit power, a missing compliance fact – is a `note` (a grade of the code, as `LIM.band/firmware`)
and a `warning` under `[severity.sale]` of its domain; an `error` only where the hardware cannot be made to comply, a
part made for another region's band. Not stricter because the law is: the law stays in chapter 15, only edakit's
grading follows its job.

## 6. A block

`edakit/blocks/<name>.json` after the pattern of an existing block: `ports` (the nets that connect outside; `gnd`
joins the ground), components with `{as}` in their labels, nets with `v` (a range or `"@port"`), `covers` (the codes
it takes care of), `notes` (what is left to decide). Its parts entries go to `edakit/parts/`: checked against
the datasheet, in English, passing `edakit part lint`. Add the block to `CONNECT` in `tests/test_block.py` – the tests
then make sure that it passes `edakit check` and `edakit sim` in the example. Table in handbook 14.5.

## 7. Retiring a code

Take it out of its engine and out of `codes.toml`, and add it to `[retired]` with what holds it now
(`"GEO.old" = "GEO.spacing holds it now"`). `edakit explain` then says so, and the lint keeps the name from being used
again. Accepts and requirements that name it: tell the user which projects carry them.

## 8. Handbook and finish

The lists of codes (3.3, 5.3, 8.1, 14.3), the parts schema (4.1) and the map of before (10.7) are generated:

```bash
uv run python -m edakit.catalog.handbook --write
uv run --group dev pytest -q
uvx ruff check edakit tests
cd tests/fixtures/led-bar && uv run --project ../../.. edakit check && uv run --project ../../.. edakit sim
```

New fields by hand in 3.1 or 4.1, the skills that name the fields (part-search), chapter 14 if the way of working
changes. Close the loop: the project's decision that held the candidate gets the code (`edakit: REQ.function`) – in
that project's repository, with the user's OK. For a proposal the triage comment says it and propose-rule does it in
the project.

Commit as the repository does (code with tests, then the handbook); push only when the user says so. A proposal
built by triage-rule is one commit, pushed to `rules/proposals`.
