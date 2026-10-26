---
name: add-feature
description: Build a feature into edakit that a project lacked – a false finding fixed, a part of the circuit the simulation now covers, a routing, pour, plan or silkscreen capability, a missing test – test first, with its interface in edakit.toml, the projects at hand unchanged, and the handbook. Use in the edakit repository when the user asks for it ("close the gap …", "edakit should be able to …"), and from triage-feature for an accepted feature proposal. Only on the user's request.
argument-hint: "<the capability – or an accepted feature proposal issue>"
---

# Add a feature to edakit

Wanted: $ARGUMENTS. A check, a hint, a block or a part fact is knowledge, not a feature: skill add-rule.

If the request leaves open what exactly edakit should do, ask before building; for a proposal, that is a
**Question** of the triage.

## 1. Red first

Show the gap in a test before changing the code, with today's edakit:

- in the example `tests/fixtures/led-bar` (helpers in `tests/conftest.py`, checked parts with
  `project.use_library_part`): the pattern built in, the command that fails or reports wrongly
- or on the module's functions with a small input: the board file for routing (`tests/test_route.py`), the plan
  (`test_pcb.py`), Gerber files (`test_fab.py`, `test_silk.py`), the netlist (`test_sim.py`)

The test fails for the reason the proposal gives. If it does not, the gap is not what the proposal says: stop and ask.

## 2. Interface

New keys in `edakit/config.py` with a default that leaves every existing project as it is (no key, no change), a
test in `tests/test_config.py`. Graph and parts fields: the reader that takes them, and their place in handbook 3.1
or 4.1. Prefer data over options: what differs between projects goes into edakit.toml, not into a switch in the code.

## 3. Code

In the module of the stage: `checks.py` (P, G), `sim/` (E), `pcb.py`, `route.py`, `silk.py`, `release/fab.py` (L, F).
What needs EasyEDA stays a thin call around a function that takes data and returns data – that function gets the
tests. Messages start with designator or net and give the numbers, like the rest of edakit.

## 4. Green

The test of step 1 passes, and its counterpart: the same example without the pattern behaves as before.

## 5. The projects at hand, unchanged

- `tests/fixtures/led-bar`: `edakit check`, `edakit sim`, `edakit gate` (offline) report what they did before
- the Christmas bell (`https://github.com/tgd1975/automatic_christmas_bell`) and other projects at hand, read only:
  `edakit check` and `edakit hints` write nothing; for the simulation call `run_all` from Python, for routing and
  plan the offline steps (`route dsn`, `route check`, `pcb plan`) into the scratchpad
- the origin, if it can be cloned: the gap command shows it closed. A private origin: write down the commands that
  show it, for the pull request

Every change in a project's report is either the gap closed or a regression – fix a regression before going on.

## 6. Handbook

- `handbook/10-reference.md`: new keys, fields, options, commands
- the chapter of the stage (3 graph, 5 simulation, 7 PCB, 8 gate) where the behaviour is described
- the skills that name what changed (pcb-round, hardware-change, release)

## 7. Finish

```bash
uv run --group dev pytest -q
uvx ruff check edakit tests
cd tests/fixtures/led-bar && uv run --project ../../.. edakit check && uv run --project ../../.. edakit sim
```

Commit as the repository does; push only when the user says so. A proposal built by triage-feature is one commit,
pushed to `features/proposals`.
