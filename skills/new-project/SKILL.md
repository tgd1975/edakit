---
name: new-project
description: Set up a new hardware project for the edakit workflow – edakit.toml, an empty hardware graph, parts database, simulation config, sign-off file, git hooks and Claude Code settings – in the current repository. Use when the user starts a new board ("new PCB", "set up edakit", "use the EasyEDA workflow here") or an existing project has no edakit.toml yet.
argument-hint: "<project name> [board name]"
---

# New edakit project

Project: $ARGUMENTS. The approach and why: `${CLAUDE_PLUGIN_ROOT}/handbook/01-approach.md`. A complete small example
to copy from: `${CLAUDE_PLUGIN_ROOT}/examples/led-bar/`.

## 1. Files

Create in the repository root (ask only for what you cannot sensibly default):

| File | Content |
|---|---|
| `edakit.toml` | from `examples/led-bar/edakit.toml`: `[project] name` = the EasyEDA project, one `[boards.<name>]` with outline and holes as far as known; leave `place`, `routing.classes` and `schematic.layout.rows` minimal until the parts exist |
| `hardware/graph.json` | `{"graph": {"name", "version": "0.1", "date", "description", "components": [], "nets": [], "cables": []}}` |
| `hardware/parts/` | empty; every LCSC number gets an entry through the part-search skill |
| `hardware/sim.json` | from the example: sources (the supply connector), supplies at min/nominal/max, loads, corners |
| `hardware/signoff.json` | from the example: M-1 (critical parts, second check), M-5 (layout review), M-2 (manufacturer preview), M-4 (acceptance) |
| `docs/decisions.md` | numbered decisions D-1, … with reason and date (the decision-round skill appends) |
| `.gitignore` | `build/` |

## 2. Guard rails

- Pre-commit hook (`.githooks/pre-commit`, `git config core.hooksPath .githooks`): when `hardware/` changed, run
  `edakit check` and `edakit sim`; a failing check blocks the commit. Never bypass it with `--no-verify`.
- CI: the same two commands plus the project's tests on every pull request (`uvx --from git+<edakit repo> edakit …`).
- `.claude/settings.json` of the project, so every session in this repo has the plugin:
  ```json
  {"extraKnownMarketplaces": {"easyeda-automation": {"source": {"source": "github", "repo": "tgd1975/easyEDAAutomation"}}},
   "enabledPlugins": {"edakit@easyeda-automation": true}}
  ```

## 3. First run

1. Graph skeleton: power input, MCU, the main functions – parts by LCSC number (part-search skill), nets with voltage
   ranges `v`. `edakit check` until 0 errors.
2. `edakit sim` – scenarios first at the supply limits.
3. EasyEDA: the user creates the project once by hand (File → New → Project, named like `[project] name`) – the
   local desktop client refuses `DMT_Project.createProject`. Then the start skill.
4. Continue with the hardware-change skill for every further change and pcb-round for the layout.

Report: which files were created, what is still open (parts without entry, missing outline, first decisions).
