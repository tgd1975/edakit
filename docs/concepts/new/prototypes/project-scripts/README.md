# Prototype: project scripts as a DAG

The prototype behind [project-scripts.md](../../project-scripts.md), section "Checking the TOML", written on
2026-10-27 outside edakit. It checks the `[scripts.*]` and `[agents.*]` entries of an `edakit.toml` against the
rules R1–R11 and prints the resolved order:

```bash
python3 verify.py glocke-main.toml --root <checkout of the Christmas bell>
```

- `glocke-main.toml`, `glocke-esp32.toml` and `pytree.toml` are the Christmas bell and the reference project as the
  concept wrote them on 2026-10-27.
- `test_verify.py` sees every rule red, one fault per copy of the pytree TOML; `test_after.py` covers chains with
  `after`, `test_agents.py` the rules for agents. They are scripts, not pytest tests, and need a checkout of the
  reference project: `PYTREE_ROOT=<path> python3 test_verify.py`. edakit's pytest does not collect them.

The prototype predates the decisions of 2026-10-28. Step 1.2 of the [implementation plan](../../implementation-plan.md)
builds the real check from it, with these differences:

- The board file stays one file (decision 4): an `input` script may write `board:<b>`, which R3 here still reports,
  and `pytree.toml` still splits the board file with `file = […]`.
- An `easyeda` script changes `project-library:<b>` (decision 12, step 1.3). `pytree.toml` and `glocke-esp32.toml`
  still write `footprints:<b>`, which edakit reports under R3.
- edakit's messages are English; the prototype's are German.
- `art_assumed` is a key of the prototype only. It stands in for the `[[silk.art]]` of a board file that does not
  exist yet.
