---
name: new-project
description: Set up a new hardware project for the edakit workflow – edakit.toml (the table of contents), an empty hardware graph, parts database, simulation config, board file, sign-off file, git hooks and Claude Code settings – in the current repository. Use when the user starts a new board ("new PCB", "set up edakit", "use the EasyEDA workflow here") or an existing project has no edakit.toml yet.
argument-hint: "<project name> [board name]"
---

# New edakit project

Project: $ARGUMENTS. The approach and why: `${CLAUDE_PLUGIN_ROOT}/handbook/01-approach.md`. A complete small example
to copy from: `${CLAUDE_PLUGIN_ROOT}/tests/fixtures/led-bar/` (shipped with the plugin); a real one, taken through
EasyEDA to the gate: https://github.com/tgd1975/automatic_christmas_bell.

## 1. Files

Create in the repository root (ask only for what you cannot sensibly default):

| File | Content |
|---|---|
| `edakit.toml` | from `tests/fixtures/led-bar/edakit.toml`: `[project] name` = the EasyEDA project, one `[boards.<name>]` with its EasyEDA documents – the table of contents that points to the files below (handbook 10.1); `[release] assembly` (sides, `pcba`) and, when the user names one, `[cost] budget` |
| `hardware/boards/<name>.toml` | when the board's size is known: from the example's board file, outline and holes; leave `place` and `routing.classes` minimal until the parts exist. Otherwise the PCB designer starts it |
| `hardware/graph.json` | `{"graph": {"name", "version": "0.1", "date", "description", "purpose": {"use", "market", "notes"}, "components": [], "nets": [], "cables": []}}` – `use` is `private`, `gift` or `sale` (circuit-design asks) |
| `hardware/parts/` | empty; every LCSC number gets an entry through the part-search skill |
| `hardware/sim.json` | from the example: sources (the supply connector), supplies at min/nominal/max, loads, corners |
| `hardware/signoff.json` | from the example: M-1 (critical parts, second check), M-6 (regulatory review), M-5 (layout review), M-2 (manufacturer preview), M-4 (acceptance) |
| `docs/decisions.md` | numbered decisions D-1, … with reason and date (the decision-round skill appends) |
| `.gitignore` | `build/` |

## 2. Guard rails

- Pre-commit hook (`.githooks/pre-commit`, `git config core.hooksPath .githooks`): when `hardware/` changed, run
  `edakit check` and `edakit sim`; a failing check blocks the commit. Never bypass it with `--no-verify`.
- CI: the same two commands plus the project's tests on every pull request (`uvx --from git+<edakit repo> edakit …`).
- `.claude/settings.json` of the project, so every session in this repo has the plugin:
  ```json
  {"extraKnownMarketplaces": {"edakit": {"source": {"source": "github", "repo": "tgd1975/edakit"}}},
   "enabledPlugins": {"edakit@edakit": true}}
  ```

## 3. First run

1. Graph skeleton with the skill circuit-design: power input, MCU, the main functions – building blocks where they fit
   (`edakit block list`), other parts by LCSC number (part-search skill), nets with voltage ranges `v`. `edakit check`
   until 0 errors, `edakit hints` worked through.
2. `edakit sim` – scenarios first at the supply limits.
3. Without a PCB (a development board and hand wiring) the project stops here: `edakit schematic draw` gives the
   schematic, EasyEDA is not needed, and `edakit.toml` needs only `[project] name` and a `[boards.<name>]` with a
   `title`. With a PCB: the user creates the EasyEDA project once by hand (File → New → Project, named like
   `[project] name`) – the local desktop client refuses `DMT_Project.createProject`. Then the start skill.
4. Continue with the hardware-change skill for every further change of the circuit. The layout is the PCB
   designer's: skill pcb-round in a session of its own, starting from `edakit handover` (handbook 14.1).

Report: which files were created, what is still open (parts without entry, missing outline, first decisions).
