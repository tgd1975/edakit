# Project setup

Status 2026-10-28: proposal; nothing of it is built, all six decisions are taken (table at the end), and it is
step 3.7 of the [implementation plan](implementation-plan.md). The findings come from
edakit at `f04dee5` and the repositories of the reference project and the Christmas bell.

## Goal

One entry point the user calls at the start. It sets up an edakit project the way this project needs it – a new one,
or one that moves to edakit – and then hands over to the skills that design.

Two questions show whether it works:

1. **After the setup, does every file and key fit the project,** without the user editing a template afterwards?
2. **After a move, has everything the project did by hand or with its own tools found its place** – a script, an
   agent, a requirement, a document – or a stated reason why not?

## Where it stands

| What | Covers | Does not cover |
| --- | --- | --- |
| skill `new-project` | the files from the example `led-bar`: `edakit.toml`, graph, parts, simulation, board file, sign-offs, decision log; the guard rails (pre-commit hook, CI, the plugin in `.claude/settings.json`); the first run | it asks "only for what you cannot sensibly default" and assumes a new project |
| skill `start` | EasyEDA, the bridge and the claim, once files exist | the project's files |
| skill `requirements`, agent `requirements-engineer` | needs and requirements with the user; the inventory of a project's documents (step 3.4) | everything else a project brings |
| `[scripts.*]`, `[agents.*]` | registering a project's scripts and agents (concept [project-scripts.md](project-scripts.md)) | finding them in a repository |
| `[firmware]`, `[docs]`, `[order]`, `[cost]`, `bought`, variants | the keys for firmware (#70), documents that quote values (#71), the order (#40, 1.7), the budget, bought boards (#82), variants as in the bell | asking whether a project needs them |

## The gap

- **Defaults instead of the project.** `new-project` copies the example's keys: one board, Economic assembly on one
  side, SMD only. The Christmas bell has four configurations (main, esp32, smd, tht), one of them assembled by
  nobody. A project with a bought board on a cable, with firmware that follows the graph or with documents that quote
  values gets the matching key only if someone remembers it.
- **Moving is not covered.** The reference project brings to edakit, by its own concept (EK-1, after its order):
  - eleven skills of its own, several with an edakit counterpart: `easyeda-start` – `start`, `entscheidungsrunde` –
    `decision-round`, `hardware-aenderung` – `hardware-change`, `pcb-iteration` – `pcb-round`, `teil-suchen` –
    `part-search`, `freigabe` and `release` – `release`. A replaced skill can lose a step: `pcb-iteration` runs
    `baum_druck.py` after every routing, `pcb-round` does not – the reason the project-scripts concept exists;
  - six agents, two of which do edakit's reviews (`elektrotechniker`, `pcb-pruefer`);
  - eight scripts that touch edakit's flow (the inventory in [project-scripts.md](project-scripts.md));
  - requirements spread over six documents (the inventory in [requirements.md](requirements.md));
  - an EasyEDA project and released runs of its own.

  Nobody turns these into edakit's entries today.
- **Late settings.** The purpose of the device (`use`: private, gift or sale – it decides how deep the regulatory
  review M-6 goes), the order settings and the budget come up when the release asks, not at the start.

## Proposal: a guided setup

As for the requirements, a skill in the conversation and an agent in its own context, because an agent cannot ask
the user.

- **Skill `new-project`** becomes the one entry point, with two ways:
  - **New:** an interview, then the files.
  - **Moving:** a repository without `edakit.toml` but with hardware files, scripts or agents. First the inventory,
    then the interview with the inventory's proposals as answers to confirm, then the files.

  It proposes every file and key with its reason and writes only after the user's OK. It ends with a report: what is
  set up, what is open, which skill comes next.
- **Agent `project-surveyor`**, read-only. For a project that moves it reads the repository and returns, per edakit
  place, candidates with the place it found them. The requirements it leaves to the `requirements-engineer`, which
  the skill runs beside it.

## The interview

| Topic | Question | What it sets |
| --- | --- | --- |
| board | A PCB, or a development board with wiring? | `[boards.<name>]` with its EasyEDA documents, or only a `title` |
| boards | How many boards? Which are made, which bought on a cable? | one `[boards.<name>]` each, `bought = true` (#82) |
| variants | Several builds of one circuit? | `variants/<v>/edakit.toml`, reading the main project's files, as in the bell |
| assembly | Who solders: JLCPCB Economic or Standard, which sides, or by hand? | `[release] assembly` (`sides`, `pcba`, `smd_only`) |
| order | How many sets? Finish, colours, thickness? | `[project] quantity`, `[order]` |
| money | A budget, a currency? | `[cost]` |
| purpose | Private, a gift, or for sale? Where is it used? | the graph's `purpose` (`use`, `market`) |
| requirements | What must the circuit do? | the skill `requirements`, `[project] requirements` |
| firmware | Does firmware follow the graph's pins? | `[firmware]`, and `edakit firmware --check` in the hook |
| documents | Do documents quote values such as currents or voltages? | `[docs] files` |
| own tools | Does the project bring scripts or agents? | `[scripts.*]`, `[agents.*]`, from the inventory |

A question the user cannot answer yet stays open with its default, and the report names it.

## The inventory of a project that moves

| Found | Proposed |
| --- | --- |
| scripts (Python, shell, Makefile targets) | one `[scripts.<name>]` per script that touches edakit's flow, with `kind`, `reads`, `writes` and `about`; the others are named as the project's business (project-scripts, "What is registered") |
| agents | `[agents.<name>]` with `signs`; `replaces` where one does an edakit review |
| skills | per skill its edakit counterpart, and what the project's skill does that edakit's does not: a script entry, a project agent, a line in the project's CLAUDE.md, or a feature proposal to edakit. Skills are not registered (project-scripts, decision 11) |
| hardware data | what goes into `graph.json`, the parts database and the board file, and what stays as it is |
| EasyEDA project, released runs | `[project] name`, the boards' documents; released runs stay as history |
| documents with values | `[docs] files` |
| decisions | the decision log, keeping its numbers |
| requirements | the `requirements-engineer`'s inventory |

The agent returns numbered lists per place: the candidate, where it was found, the proposal and its reason. It ends
with contradictions between the project's documents and with what it could not read.

## Order of the setup

1. When moving: the inventory.
2. The interview, as one decision round.
3. The files and keys, as `new-project` writes them today, but from the answers instead of the example's defaults.
4. The guard rails: the pre-commit hook (`check` and `sim`, plus `firmware --check` and `docs` where set), CI and the
   plugin in `.claude/settings.json`.
5. The report, and the hand-over: `requirements` if the file is still missing, `circuit-design`, and `start` once the
   user has created the EasyEDA project.

## Trial

- **New:** a project like `led-bar`, set up from scratch. No value of the example stays unasked.
- **Moving:** the reference project's move, step 4.4 of the [implementation plan](implementation-plan.md): the
  takeover of its positions (2.1), seven scripts, two agents with `replaces`, its requirements file and its eleven
  skills mapped.

## Scope

- The EasyEDA project is still created by hand; the local client refuses `DMT_Project.createProject`. The setup says
  so at the right moment.
- No silent change: the setup proposes, the user decides.
- The setup deletes none of the project's own skills. The report says which overlap with edakit's.
- One repository per project. A project spread over several repositories is not covered.

## Order

1. The interview in `new-project` and the table from answers to keys – small.
2. The agent `project-surveyor` – medium.
3. The second way of `new-project`, moving – medium.
4. The trial on the reference project, as part of step 4.4.

## Decisions

All taken on 2026-10-28. "Accepted" is the user's yes to the recommendation; "decided by Claude" marks a
technical point the user left to Claude and then confirmed.

| # | Question | Recommendation | State |
| --- | --- | --- | --- |
| 1 | One entry point, or a new skill for moving beside `new-project`? | one: `new-project` with two ways | accepted |
| 2 | Name of the agent | `project-surveyor` | decided by Claude |
| 3 | A command `edakit init` that writes the skeleton? | not for now: the skill writes the files, as today; a command once two projects show the same writing errors | decided by Claude |
| 4 | The interview as a form with options, or as text? | a form where the tool offers one (options, free text for the rest), otherwise a decision round in text | accepted |
| 5 | The project's own skills that overlap edakit's | the report lists each with what it does beyond edakit's; keeping or deleting it is the user's decision, skill by skill | accepted |
| 6 | Trial | first on the reference project's move; the setup comes before step 4.4 in the plan | decided by Claude |

## Sources

- edakit at `f04dee5`: skills [new-project](../../../skills/new-project/SKILL.md),
  [start](../../../skills/start/SKILL.md) and [requirements](../../../skills/requirements/SKILL.md), agent
  [requirements-engineer](../../../agents/requirements-engineer.md), handbook [10](../../../handbook/10-reference.md)
  (10.1 the files), the concepts [project-scripts.md](project-scripts.md) (the inventory of the reference project,
  decisions 10 and 11) and [requirements.md](requirements.md).
- The reference project: `.claude/skills/`, `.claude/agents/`, `docs/concepts/offen/edakit.md` (EK-1).
- The Christmas bell: `variants/` (esp32, smd, tht).
