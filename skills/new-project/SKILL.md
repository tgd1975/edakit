---
name: new-project
description: Set up an edakit project in the current repository from an interview instead of the example's defaults – a new project, or one that moves to edakit with hardware files, scripts or agents of its own (then first the inventory by the agents project-surveyor and requirements-engineer, and the interview with their proposals as answers to confirm). Asks for boards, bought boards, variants, assembly, order, money, purpose, requirements, firmware, documents and the project's own tools, proposes every file and key with its reason and writes edakit.toml, graph, parts, simulation config, board file, sign-offs, decision log, git hook, CI and Claude Code settings only after the user's OK. Use when the user starts a new board ("new PCB", "set up edakit", "use the EasyEDA workflow here") or a project without edakit.toml moves to edakit ("move this project to edakit").
argument-hint: "<project name> [board name]"
---

# New edakit project

Project: $ARGUMENTS. The approach and why: `${CLAUDE_PLUGIN_ROOT}/handbook/01-approach.md`; every key:
`10-reference.md` (10.1). A complete small example to copy from: `${CLAUDE_PLUGIN_ROOT}/tests/fixtures/led-bar/`
(shipped with the plugin); a real one, taken through EasyEDA to the gate, with variants:
https://github.com/tgd1975/automatic_christmas_bell.

You set the project up the way this project needs it: every file and key from an answer, none left at the example's
value unasked. You propose each with its reason and write only after the user's OK – no silent change. You delete
none of the project's own skills or agents; a file of the project you change or remove – its hook, an MCP server of
its own – is a proposal like any other.

## 0. Which way

| The repository has | Way |
|---|---|
| no `edakit.toml` and no hardware of its own | **new:** the interview (section 2), then the files |
| no `edakit.toml`, but hardware files, scripts or agents – a graph or netlist, parts, a board, gate runs, `.claude/agents/`, scripts that drive EasyEDA | **moving:** the inventory first (section 1), then the interview with its proposals as answers to confirm, then the files |
| an `edakit.toml` | not this skill: the project is set up – `edakit check 2>&1 \| cat` shows where it stands, and a key it lacks is a change of its own (handbook 10.1) |

One repository per project – a project spread over several repositories is not covered; say so and set up the one
at hand.

## 1. Inventory (moving)

Two agents, each in its own context and side by side – both change nothing:

- **project-surveyor** – its prompt: "inventory", the repository, what the user said about the project. It returns
  numbered lists per place – hardware data, the EasyEDA project and released runs, scripts, agents, skills,
  documents with values, decisions, guard rails, the interview's answers, the documents with requirements – each
  candidate with where it was found, the proposal and its reason; at the end the contradictions, what it could not
  read and a count per place.
- **requirements-engineer** – its prompt: "inventory", what the user wants, the documents with requirements (the
  surveyor names them; start both at once with the ones you know). Its candidates are for the skill requirements
  (section 5), which starts from this inventory instead of making it again.

Read both before the interview. Each contradiction is a question of the interview, never resolved silently.

## 2. Interview

All topics in **one round**, in the order of the table. Where the tool offers a form – in Claude Code
`AskUserQuestion`, up to four questions per call – ask with it: the table's options as the choices, the recommended
one first, the user's own words for everything else; the names and numbers below as free text. Otherwise one
decision round in text (skill decision-round): one numbered item per topic with the options as a, b, c, the
recommendation first. Leave out what an earlier answer makes moot: assembly and order without a PCB.

- **New:** the recommended option is what the user already said, else the first of the table.
- **Moving:** the recommended option is the inventory's answer, its source in the option's text ("found:
  docs/order.md – Economic, top side"); a confirmation is enough. Where the inventory found two answers, both are
  options with their places.

| Topic | Question | Options – the first is the default | What it sets |
|---|---|---|---|
| board | A PCB, or a development board with wiring? | a PCB · a development board with wiring, no PCB | with a PCB `[boards.<name>]` with its EasyEDA documents (`template`, `schematic`, `pcb`, `file`, named after the board) and the board file; without one only a `title`, no board file and no EasyEDA (section 5) |
| boards | How many boards? Which are made, which bought on a cable? | one made board · several made boards · besides, a bought board on a cable (a breakout, a module in the enclosure) | one `[boards.<name>]` each; `bought = true` for a bought one – no `template`, `schematic`, `pcb` or `file` (handbook 4.5) |
| variants | Several builds of one circuit – another MCU, SMD or through-hole, assembled or not? | one build · several builds | per further build a project of its own, `variants/<v>/edakit.toml`, with its own graph, parts, simulation config, board file and sign-offs, its own board in the same EasyEDA project, reading the main project's files – the requirements file (`requirements = ["../../hardware/requirements.toml", …]`, handbook 10.4) and a shared script (`../../…`) –, as the Christmas bell's `variants/` |
| assembly | Who solders? | JLCPCB Economic, one side, SMD only · JLCPCB Standard, both sides · nobody: a bare board, all by hand | `[release] assembly`: `{ sides = ["top"], smd_only = true }`, `{ sides = ["top", "bottom"], pcba = "standard" }`, `{ sides = [] }`; the parts you solder yourself get `bom: false` in the graph (circuit-design) |
| order | How many sets? Finish, colours, thickness? | 5 sets, 1.6 mm, green mask, white print, lead-free HASL · other | `[project] quantity`; the board file's `[order]` (`finish`, `mask`, `silkscreen`, `mark`, `remark`) and `thickness_mm` – only what differs from JLCPCB's defaults (handbook 8.4) |
| money | A budget, a currency? | no budget · a budget: amount and currency | `[cost]`: `budget`, `currency` (USD), `rates` for a second currency (`{ EUR = 1.15 }`) |
| purpose | Private, a gift, or for sale? Where is it used? | private – built for oneself · gift – given away now and then · sale – sold, also in small series or as a kit | the graph's `purpose`: `use`, `market` (EU), `notes` – what it is, who uses it (children?). It decides how deep the regulatory review M-6 goes (handbook 15.1) – support, not legal advice: nothing in it is legally guaranteed, and it claims no correctness |
| requirements | What must the circuit do? | now, with the skill requirements · later | now: the skill requirements writes `hardware/requirements.toml` with the user, and `[project] requirements` names it (section 5); later: nothing yet |
| firmware | Does firmware follow the graph's pins? | it follows the graph · the firmware is the reference, the graph keeps its pins · no firmware that depends on the pins | `[firmware]` and `edakit firmware --check` in the hook (handbook 3.5); the other way round `checks.pin_locks` in the graph, the circuit designer's (G-2) |
| documents | Do documents quote values – currents, voltages, a part's value? | no · yes: these files | `[docs] files`, `decimal = ","` for a decimal comma, `edakit docs` in the hook (handbook 6.6) |
| own tools | Does the project bring scripts or agents? | none · as the inventory proposes | `[scripts.<name>]` for every script that touches edakit's flow, `[agents.<name>]` for every agent that signs what edakit releases (handbook 8.6); the project's skills are listed in the report, not registered |

**Names and numbers, as free text:** the project's name – the EasyEDA project, `[project] name` –, `company` for the
title block, each board's name and `title`, each variant's name, the board's size if known, the amount and currency
of a budget, the market and notes of the purpose, the documents with values, the distributors besides LCSC
(`[project] distributors`).

A question the user cannot answer yet stays open with its default, and the report names it. The answers are a
decision of the project: one numbered entry in its decision log (skill decision-round, section 3) – "D-1: set up for
edakit: one board main, JLCPCB Economic on top, 5 sets, a gift in the EU, no budget".

## 3. Files

From the answers – each file and key proposed with the answer that sets it, written after the OK:

| File | Content |
|---|---|
| `edakit.toml` | the table of contents (handbook 10.1), from `tests/fixtures/led-bar/edakit.toml` with its comments, every value from the answers: `[project]` (`name`, `company`, `quantity`, `distributors`), one `[boards.<name>]` per board, `[release] assembly`, and where the answers set them `[cost]`, `[firmware]`, `[docs]`, `[scripts.*]`, `[agents.*]`. Moving: `graph`, `parts`, `sim`, `signoff` name the project's files where they lie |
| `hardware/boards/<name>.toml` | per made board, when its size is known: from the example's board file, outline and holes, `[order]` and `thickness_mm` where they differ; leave `place` and `routing.classes` minimal until the parts exist. Otherwise the PCB designer starts it, and the order's answers wait in the decision log. None for a bought board, none without a PCB |
| `hardware/graph.json` | `{"graph": {"name", "version": "0.1", "date", "description", "purpose": {"use", "market", "notes"}, "components": [], "nets": [], "cables": []}}` – the purpose from the interview |
| `hardware/parts/` | empty; every LCSC number gets an entry through the part-search skill or the agent part-selector |
| `hardware/sim.json` | from the example: sources (the supply connector – of a bought board on a cable its connector, the cable in the path), supplies at min/nominal/max, loads, corners; with several sources `combine_sources` (handbook 5.2) |
| `hardware/signoff.json` | from the example: M-1 (critical parts, second check), M-6 (regulatory review), M-5 (layout review), M-2 (manufacturer preview), M-4 (acceptance); a project agent with `replaces` signs edakit's review in its place, the gate adds an agent's own sign-off by itself (handbook 8.6) |
| `hardware/requirements.toml` | optional: what the circuit must do – needs and requirements with their evidence, written with the user by the skill requirements and named in `[project] requirements` (handbook 3.6); the gate will require it once the Christmas bell and the reference project have theirs |
| `variants/<v>/` | per further build its own `edakit.toml` and files as above, a board of its own in the same EasyEDA project |
| `docs/decisions.md` | numbered decisions D-1, … with reason and date (the decision-round skill appends); the setup's answers are the first |
| `.gitignore` | `build/` |

**Moving.** The project's files stay where they lie and edakit.toml names them (working agreement 22). Converted are
only what the inventory proposes and the user accepts – a simulation config of the project's own into `sim.json`, a
sign-off file into edakit's scopes and phases, the board's geometry into the board file –, each with what changed in
the report. Its decision log keeps its place and its numbers. A `[scripts.*]` entry is written for a command that
exists as written; one still to be built by the project goes into the report instead. A change to a file in a hash –
the purpose in the graph, a converted simulation config – voids the sign-offs of that scope (handbook 8.2): the
report names them.

## 4. Guard rails

- Pre-commit hook (`.githooks/pre-commit`, `git config core.hooksPath .githooks`): when `hardware/` changed, run
  `edakit check` and `edakit sim`, with `[firmware]` also `edakit firmware --check` (handbook 3.5), with `[docs]`
  `edakit docs` (handbook 6.6); a failing check blocks the commit. Never bypass it with `--no-verify`. Moving: the
  project's hook keeps its other steps; its own graph check and simulation become edakit's, and a hint in it to
  bypass a failing check goes.
- CI: the same commands plus the project's tests on every pull request (`uvx --from git+<edakit repo> edakit …`).
- `.claude/settings.json` of the project, so every session in this repo has the plugin:
  ```json
  {"extraKnownMarketplaces": {"edakit": {"source": {"source": "github", "repo": "tgd1975/edakit"}}},
   "enabledPlugins": {"edakit@edakit": true}}
  ```
  Moving: an EasyEDA MCP server of the project's own (`.mcp.json`) goes – the plugin brings the pinned one, and two
  would run with every tool twice; agents and hooks that name its tools (`mcp__easyeda__…`) get the plugin's names
  (`mcp__plugin_edakit_easyeda__…`).

## 5. First run and hand-over

1. `edakit check 2>&1 | cat` and `edakit sim 2>&1 | cat` – on a new project the empty graph; on a moving one what
   edakit finds in the project's data. Findings go into the report and to the skill that owns them, not fixed
   silently here. With `[scripts]` or `[agents]` (a project without entries skips this): `edakit scripts 2>&1 | cat`
   shows that the entries resolve, before any script runs – "do not resolve", an error `scripts` or `agents` of
   `edakit check`, means an entry is wrong: a kind, a path, what it reads or writes, what an agent signs, its file. Fix
   the entry and name the fix in the report. Then each script that never ran, with the user's OK:
   `edakit run <name> 2>&1 | cat` runs and records it – an easyeda script under the claim, once the EasyEDA project
   exists –, and `edakit scripts stamp <name>` records one whose result is there from before (moving, handbook 8.6).
   An input that never ran fails `edakit check` until then.
2. Requirements "now": the skill requirements – it writes `hardware/requirements.toml` with the user, and
   circuit-design reads the file instead of asking.
3. Graph with the skill circuit-design: power input, MCU, the main functions – building blocks where they fit
   (`edakit block list`), other parts by LCSC number (part-search skill), nets with voltage ranges `v`. `edakit check`
   until 0 errors, `edakit hints` worked through, `edakit sim` – scenarios first at the supply limits. A moving
   project has its graph: circuit-design takes what `edakit check` found.
4. Without a PCB (a development board and hand wiring) the project stops here: `edakit schematic draw` gives the
   schematic, EasyEDA is not needed. With a PCB: the user creates the EasyEDA project once by hand (File → New →
   Project, named like `[project] name`) – the local desktop client refuses `DMT_Project.createProject`; a moving
   project has it already. Then the start skill.
5. Continue with the hardware-change skill for every further change of the circuit. The layout is the PCB designer's:
   skill pcb-round in a session of its own, starting from `edakit handover` (handbook 14.1).

## Report

- **Set up:** the files and keys, each with the answer that set it; moving: what was converted, and the sign-offs a
  change voided.
- **Open:** questions left at their default, contradictions not decided yet, what the agents could not read, parts
  without an entry, a missing outline, scripts still to be built.
- **Purpose:** as set, and what it means for the regulatory review M-6 – support, not legal advice: nothing in it is
  legally guaranteed, and it claims no correctness.
- **The project's own skills** that overlap edakit's (moving): each with its edakit counterpart and what it does
  beyond it – a script entry, a project agent, a line in the project's CLAUDE.md, a feature proposal. Keeping or
  deleting one is the user's decision, skill by skill; the setup deletes none.
- **Next:** the skill requirements if the file is still missing, circuit-design, and start once the EasyEDA project
  exists.
