# edakit as a meta-harness

For developers who want to know what kind of system edakit is before they change it. After this page you know its
three layers, the loops that hold it, what is bound to Claude Code and what carries over, and the rules that follow
for a change. This is the one page of the site that uses the word "harness"; the reader pages describe what happens
instead.

## The term, by three properties

An agent harness is the program around a language model that gives it a loop, tools, permissions and context – Claude
Code is one. edakit is a meta-harness in three senses, each checkable in the repository:

1. **It is built on an agent harness and specializes it** – Claude Code first. The plugin gives the session skills,
   agents, hooks, working agreements and an MCP server for EasyEDA; the checking core gives it checks that are not
   Claude.
2. **Projects extend it.** A project adds scripts and agents of its own – `[scripts.<name>]` and `[agents.<name>]` in
   edakit.toml – that the gate runs and whose sign-offs it requires
   ([project scripts and agents, 8.6](../handbook/08-release-gate.md)).
3. **It changes through its own use.** A finding in a project becomes a proposal (`/edakit:propose-rule`,
   `/edakit:propose-feature`), the Action proposals builds the accepted ones with Claude, and the owner merges.

## Three layers

| Layer | What it brings | Bound to |
| --- | --- | --- |
| Claude Code | the loop, the tools, permissions, sub-agents, hooks | Claude Code |
| The plugin | skills, agents, hooks, the working agreements (handbook 11.4), the EasyEDA MCP server | Claude Code's plugin format |
| The checking core | the command line, the catalog, the engines, the simulation, the gate | nothing – it runs without Claude Code |

The core decides; the plugin steers; the harness runs. A step that matters ends in a command of the core whose result
is a file and an exit code, never in a judgement of the session alone.

## Five loops

Each loop has a signal, a stop condition and a step back. The files that set them:

| Loop | Signal | Stops when | Steps back to | Set in |
| --- | --- | --- | --- | --- |
| Check loop | a finding of `edakit check`, a failed scenario of `edakit sim` | no error, every warning fixed or accepted with a reason | the graph | `skills/circuit-design/SKILL.md`, "Check loop" |
| Review loop | a reviewer agent's numbered findings | each one fixed or decided, the sign-off written | the design, or the person for a decision | working agreement 4 in handbook 11.4 |
| PCB round | DRC, the route check, the round's review | a clean board its reviewer agrees to | placement and routing | `skills/pcb-round/SKILL.md` |
| The gate | a stage of the release gate that fails | every stage passes, the files released | the stage that failed | `skills/release/SKILL.md`, [chapter 8](../handbook/08-release-gate.md) |
| Across projects | a finding a rule could have found | the proposal accepted and merged, or rejected | edakit's catalog and code | `skills/propose-rule`, the triage skills, the Action proposals |

Where a decision is the person's – money, purpose, looks, a trade-off –, the loop leaves through a decision round
(skill decision-round) and comes back with the answer in the project's decision log.

## What is bound to Claude Code, what carries over

Bound: the formats of skills, hooks and agents in the plugin; the question form of a decision round
(AskUserQuestion); Claude in Chrome for the order at a maker's page; the names of the MCP tools. Carried over to any
harness: the command line and every check, the catalog and its data, the MCP server, the skills as text. What it takes
to run in other assistants and with self-hosted models is worked out in
[claude-independence](concepts/new/claude-independence.md).

## Rules for a change

- **A capability without a check is a prompt.** Every new step brings its check, seen red once in a test.
- **Knowledge goes into data** – the catalog, the domains, blocks, parts entries –, not into a skill's text, where no
  test holds it and no other harness reads it.
- **Skills name handbook sections**, and `tests/test_references.py` holds every name to a section that exists.
- **The person gets decisions, not checklists.** What Claude can decide itself, it decides and lists; what is the
  person's goes into a decision round with a recommendation.
- **What exists only in EasyEDA or only in someone's head is a gap.** Circuit design as code means every step is text
  in the repository and can be done by an assistant
  ([design-as-text](concepts/done/design-as-text.md)).
